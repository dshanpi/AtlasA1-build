#!/usr/bin/env python3
"""Extract the board-tested RAM-only FES loader from matching T736 Tina firmware."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile

from pack_armbian_raw_v6 import make_loader
from pack_boot_validation import read_package


EXPECTED = {
    "fes1.fex": (225728, "ab8618a40c51e381d2904dfb12ced567f3b2016bbb50e805980a463402a97994"),
    "u-boot.fex": (1245184, "cdeb0be64b063a089797e9c385f0c6a20f70548e5540de3453308c53a4b546fd"),
    "config.fex": (5120, "c6ca514a4f8088f0ba0ac20b6909433ef882d1a54bc55cc7c72fc0b87fb95d82"),
    "board.fex": (1024, "ab1d5b1e29bc04511d1fc6942ae365f3202d5795fa06e3699acfae987fafb245"),
}
LOADER_SHA = "565436e6d6f4370d05788afa3397a7e2368b5d5d2cef9a6490700b9b944cee08"


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("firmware", type=Path, help="Matching T736 LPDDR4x Tina recovery firmware (IMAGEWTY)")
    cli.add_argument("output", type=Path, help="New RAM-loader image file")
    args = cli.parse_args()
    header, entries = read_package(args.firmware)
    payloads = {}
    with args.firmware.open("rb") as source:
        for name, (length, expected) in EXPECTED.items():
            if name not in entries or entries[name][2] != length:
                cli.error(f"wrong loader component {name}")
            source.seek(entries[name][1])
            data = source.read(length)
            if hashlib.sha256(data).hexdigest() != expected:
                cli.error(f"unexpected contents for {name}")
            payloads[name] = data
    with tempfile.TemporaryDirectory(dir=args.output.parent) as work:
        staged = Path(work)/"loader.img"
        manifest = make_loader(header, entries, payloads, staged)
        if manifest["sha256"] != LOADER_SHA:
            cli.error("container differs from the verified board loader")
        os.link(staged, args.output)
    print(f"{LOADER_SHA}  {args.output}")


if __name__ == "__main__":
    main()
