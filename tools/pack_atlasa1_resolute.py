#!/usr/bin/env python3
"""Build the fixed AtlasA1 eMMC layout from a completed Ubuntu 26.04 rootfs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_atlasa1_release_boot import BL31_SHA, ROOT_ID, SPL_SHA, STAGE_SHA
from pack_armbian_raw_v6 import LAYOUT, SECTOR, SECTORS, gpt
from pack_t736_media_v28_boot import BASE_LBA, parse


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def text(*argv):
    return subprocess.check_output(argv, text=True).strip()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--rootfs', required=True, type=Path)
    cli.add_argument('--boot', required=True, type=Path, help='directory from build_atlasa1_release_boot.py')
    cli.add_argument('--output', required=True, type=Path)
    args = cli.parse_args()
    root, boot, output = args.rootfs.resolve(strict=True), args.boot.resolve(strict=True), args.output.absolute()
    manifest = output.with_suffix('.manifest.json')
    if output.exists() or manifest.exists() or output.is_symlink() or manifest.is_symlink():
        cli.error('output paths must be new')
    identity = (root/'usr/lib/os-release').read_text()
    if 'VERSION_ID="26.04"' not in identity or 'ID=ubuntu' not in identity or 'resolute' not in identity:
        cli.error('expected Ubuntu 26.04 Resolute')
    if 't736-mainline' not in (root/'etc/armbian-release').read_text():
        cli.error('missing AtlasA1 Armbian BSP')
    if f'PARTUUID={ROOT_ID}' not in (root/'etc/fstab').read_text():
        cli.error('root partition does not match the U-Boot boot command')
    expected_boot_files = {}
    for name in ('vmlinuz-6.18.63-t736-armbian', 'initrd.img-6.18.63-t736-armbian',
                 'dtb/allwinner/t736-mainline-bringup.dtb'):
        path = (root/'boot'/name).resolve(strict=True)
        if not path.is_relative_to(root/'boot') or not 0 < path.stat().st_size < 48 * 1024**2:
            cli.error(f'invalid boot file {name}')
        expected_boot_files[str(path.relative_to(root))] = sha(path)
    spl, package = boot/'emmc-spl.bin', boot/'boot-package.bin'
    record = json.loads((boot/'boot-manifest.json').read_text())
    if sha(spl) != SPL_SHA or sha(package) != record['boot_package_sha256'] or record['root_partuuid'] != ROOT_ID:
        cli.error('SPL or boot package differs from its build record')
    entries = parse(package.read_bytes())
    if [i['sha256'] for i in entries] != [STAGE_SHA, BL31_SHA, sha(boot/'u-boot.bin')]:
        cli.error('stage64/BL31/U-Boot payload mismatch')
    primary, backup = gpt()
    regions = [(0, primary), (16, spl.read_bytes()), (BASE_LBA, package.read_bytes()),
               (40960, primary), (SECTORS - len(backup)//SECTOR, backup)]
    root_lba, root_sectors = LAYOUT[3][1:]
    # Only a new regular file is opened. Loop access is read-only and bounded to p4.
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.atlas-image-') as tmp:
        image = Path(tmp)/'disk.img'
        with image.open('xb') as stream:
            stream.truncate(SECTORS * SECTOR)
        features = ('none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,'
                    'sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum')
        subprocess.run(['mke2fs', '-q', '-F', '-t', 'ext4', '-b', '4096', '-I', '256',
                        '-m', '1', '-L', 'rootfs', '-O', features, '-E',
                        f'offset={root_lba*SECTOR},nodiscard,lazy_itable_init=0,lazy_journal_init=0',
                        '-d', root, image, str(root_sectors*SECTOR//4096)], check=True)
        with image.open('r+b') as stream:
            for lba, data in regions:
                stream.seek(lba * SECTOR)
                stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            for lba, data in regions:
                stream.seek(lba * SECTOR)
                if stream.read(len(data)) != data:
                    raise ValueError(f'boot data readback mismatch at LBA {lba}')
        subprocess.run(['sfdisk', '--verify', image], check=True)
        partitions = json.loads(text('sfdisk', '--json', image))['partitiontable']['partitions']
        if ([(p['name'], p['start'], p['size']) for p in partitions] != LAYOUT
                or partitions[3]['uuid'].lower() != ROOT_ID or image.stat().st_size != SECTORS * SECTOR):
            raise ValueError('incorrect output GPT or image size')
        loop = text('losetup', '--find', '--show', '--read-only', '--offset', str(root_lba*SECTOR),
                    '--sizelimit', str(root_sectors*SECTOR), image)
        try:
            subprocess.run(['e2fsck', '-fn', loop], check=True)
            for name, expected in expected_boot_files.items():
                extracted = Path(tmp)/Path(name).name
                subprocess.run(['debugfs', '-R', f'dump /{name} {extracted}', loop], check=True)
                if sha(extracted) != expected:
                    raise ValueError(f'packed ext4 differs from source for {name}')
            fs_uuid = text('blkid', '-s', 'UUID', '-o', 'value', loop)
            env = dict(os.environ, LC_ALL='C')
            header = subprocess.check_output(['dumpe2fs', '-h', loop], env=env,
                                             text=True, stderr=subprocess.DEVNULL)
            numbers = dict(line.split(':', 1) for line in header.splitlines() if ':' in line)
            block_size = int(numbers['Block size'])
            user_free = (int(numbers['Free blocks']) - int(numbers['Reserved block count'])) * block_size
        finally:
            subprocess.run(['losetup', '-d', loop], check=True)
        details = dict(image=output.name, bytes=image.stat().st_size, sha256=sha(image),
                       format='AtlasA1 eMMC raw disk image', distribution='Ubuntu 26.04', root_partuuid=ROOT_ID,
                       rootfs_uuid=fs_uuid, rootfs_lba=root_lba, boot_files=expected_boot_files,
                       root_partition_bytes=root_sectors*SECTOR, rootfs_user_available_bytes=user_free,
                       spl_sha256=SPL_SHA, boot_package_sha256=record['boot_package_sha256'],
                       components=entries, e2fsck='passed', gpt='passed', hardware_boot='unverified')
        pending_manifest = Path(tmp)/'manifest.json'
        pending_manifest.write_text(json.dumps(details, indent=2)+'\n')
        image.chmod(0o644)
        os.link(image, output)
        os.link(pending_manifest, manifest)
        print(json.dumps(details))


if __name__ == '__main__':
    main()
