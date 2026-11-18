#!/usr/bin/env python3
"""Place the board's two source-boot payloads in an existing fixed-layout build image."""
import argparse
import os
from pathlib import Path
import stat

from pack_armbian_raw_v6 import gpt, LAYOUT, SECTORS, SECTOR
from pack_t736_media_v28_boot import BASE_LBA, LIMIT_LBA, SPL_V4_SHA, parse, sha


def load_boot_files(spl_path, package_path):
    spl = Path(spl_path).read_bytes()
    if sha(spl) != SPL_V4_SHA:
        raise ValueError("expected the fixed LPDDR4x v4 eGON SPL, not a source boot package")
    package = Path(package_path).read_bytes()
    if sha(package) != "4742e0d36c2f35c9b58e4b70fad657fb7d265248451c3f618b46ab07b84385f0":
        raise ValueError("expected the media-v28 stage64/BL31/U-Boot source package")
    return spl, package, parse(package)


def at(stream, sector, size):
    stream.seek(sector * SECTOR)
    return stream.read(size)


def check_loop(loop, image):
    device = Path(loop).stat()
    if not stat.S_ISBLK(device.st_mode):
        raise ValueError("Armbian target is not a build loop device")
    devno = f"{os.major(device.st_rdev)}:{os.minor(device.st_rdev)}"
    sysfs = Path("/sys/dev/block") / devno
    backing = Path((sysfs / "loop/backing_file").read_text().rstrip("\n"))
    if (not image.samefile(backing) or int((sysfs / "loop/offset").read_text()) != 0 or
            int((sysfs / "loop/sizelimit").read_text()) != 0 or
            int((sysfs / "queue/logical_block_size").read_text()) != SECTOR):
        raise ValueError("loop does not map the exact build image with 512-byte sectors")


def install(image, spl, package, entries, uboot):
    if sha(Path(uboot).read_bytes()) != entries[2]["sha256"]:
        raise ValueError("Armbian U-Boot differs from the U-Boot in the board boot package")
    primary, backup = gpt()
    mirror = 40960
    spl_lba = 16
    if not (len(primary) <= spl_lba * SECTOR and
            spl_lba * SECTOR + len(spl) <= BASE_LBA * SECTOR and
            BASE_LBA * SECTOR + len(package) < LIMIT_LBA * SECTOR <= mirror * SECTOR and
            mirror * SECTOR + len(primary) <= LAYOUT[0][1] * SECTOR):
        raise ValueError("T736 boot slots overlap the reserved disk layout")
    # A target-side package upgrade must never write the live eMMC device.
    if not stat.S_ISREG(image.lstat().st_mode):
        raise ValueError("expected a regular build image")
    with image.open("r+b", buffering=0) as stream:
        state = os.fstat(stream.fileno())
        if not stat.S_ISREG(state.st_mode) or state.st_size != SECTORS * SECTOR:
            raise ValueError("expected the 8 GiB source-image layout")
        for sector, data in ((0, primary), (mirror, primary), (SECTORS - len(backup) // SECTOR, backup)):
            if at(stream, sector, len(data)) != data:
                raise ValueError(f"T736 GPT or compatibility mirror differs at LBA {sector}")
        regions = [(BASE_LBA, package), (spl_lba, spl)]
        for sector, data in regions:
            existing = at(stream, sector, len(data))
            if existing != data and existing != bytes(len(data)):
                raise ValueError(f"occupied boot slot at LBA {sector}")
        # The complete package must reach storage before the ROM-visible SPL.
        for sector, data in regions:
            if at(stream, sector, len(data)) == data:
                continue
            stream.seek(sector * SECTOR)
            if stream.write(data) != len(data):
                raise OSError(f"short write at LBA {sector}; discard partial build image")
            os.fsync(stream.fileno())
            if at(stream, sector, len(data)) != data:
                raise OSError(f"boot readback failed at LBA {sector}; discard partial build image")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "spl", "package", "uboot"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--loop", type=Path, required=True)
    args = parser.parse_args()
    try:
        check_loop(args.loop, args.image)
        install(args.image, *load_boot_files(args.spl, args.package), args.uboot)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"T736 boot image: {exc}\n")
