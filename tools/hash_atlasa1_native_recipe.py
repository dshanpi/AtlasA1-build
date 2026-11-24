#!/usr/bin/env python3
"""Include external helper sources in Armbian artifact cache identities."""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'kernel': ['tools/build_atlasa1_native_pvr.sh', 'patches/linux/media-v30-pvr-replay/*',
               'patches/linux/gnome-media-20261119/v42-pvr-trace-api.patch'],
    'boot': ['tools/build_atlasa1_release_boot.py', 'tools/build_t736_emmc_spl.py',
             'tools/build_t736_source_handoff.py', 'tools/atlasa1_native_image.py',
             'spl/**/*', 'boards/t736-uboot-cpuclock*.c', 'patches/tf-a/*',
             'config/t736-lp4x-fixed.fex', 'config/u-boot-source-v6.config'],
}


def identity(component):
    paths = {ROOT/'config/clean-build/inputs.lock.json'}
    for pattern in INPUTS[component]:
        paths.update(path for path in ROOT.glob(pattern) if path.is_file() and not path.is_symlink())
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes())
    return digest.hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=INPUTS)
    print(identity(parser.parse_args().component))
