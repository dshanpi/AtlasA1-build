#!/usr/bin/env python3
"""Package the v47 source-build output for the GNOME image installer."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('build', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    release = '6.18.63-t736-gnome-v47'
    tree = args.build.resolve(strict=True) / 'boot-candidate'
    image = tree / 'boot' / ('Image-' + release)
    if image.read_bytes()[56:60] != b'ARM\x64':
        cli.error('Expected an ARM64 v47 Image')
    if args.output.exists():
        cli.error('Output must be new')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent, prefix='.kernel-deb-') as tmp:
        root = Path(tmp)
        shutil.copytree(tree / 'usr', root / 'usr', symlinks=True)
        (root / 'boot').mkdir()
        shutil.copy2(image, root / 'boot' / ('vmlinuz-' + release))
        shutil.copy2(tree / 'boot' / ('config-' + release), root / 'boot' / ('config-' + release))
        dtb = root / 'usr/lib' / ('linux-image-' + release) / 'allwinner/t736-pcie-v32.dtb'
        dtb.parent.mkdir(parents=True)
        shutil.copy2(tree / 'boot/t736-gnome-v47.dtb', dtb)
        (root / 'DEBIAN').mkdir()
        (root / 'DEBIAN/control').write_text(
            f'Package: linux-image-{release}\nVersion: 6.18.63-47\n'
            'Architecture: arm64\nMaintainer: AtlasA1 board project\n'
            'Depends: kmod, initramfs-tools\n'
            'Description: AtlasA1 GNOME kernel with HDMI, PowerVR, Cedar and NVMe support\n')
        env = dict(os.environ, SOURCE_DATE_EPOCH='1795046400')
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', root, args.output.resolve()],
                       env=env, check=True)


if __name__ == '__main__':
    main()
