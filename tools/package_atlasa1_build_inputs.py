#!/usr/bin/env python3
"""Maintainer tool: capture the exact minimal SDK inputs for automatic builds.

This packages third-party source, runtime libraries and a compiler, not a built
kernel/rootfs and not previously compiled OMX objects. Never point it at a home
directory or publish an unreviewed output: the manifest identifies every input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HOST = Path('out/t736/demo_aiot/buildroot/buildroot/host')
CEDAR = Path('platform/allwinner/multimedia/libcedarc_v2.0')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(tina, output):
    tina = tina.resolve(strict=True)
    output = output.absolute()
    if output.exists() or output.is_relative_to(tina):
        raise ValueError('Output must be a new directory outside SDK')
    output.mkdir(parents=True)
    stage = output / 'inputs'
    stage.mkdir()

    def copy(relative, source_only=False):
        src, dst = tina / relative, stage / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            dst.symlink_to(os.readlink(src))
        elif src.is_dir():
            dst.mkdir(exist_ok=True)
            for child in sorted(src.iterdir()):
                if child.name.startswith('binary_') or child.name in ('.git', '.svn', '.libs', '.deps', '__pycache__'):
                    continue
                if source_only and (child.suffix in ('.o', '.a', '.so', '.lo', '.la', '.ko', '.pyc') or '.so.' in child.name):
                    continue
                copy(child.relative_to(tina), source_only)
        else:
            shutil.copy2(src, dst)

    ddr = Path('brandy/dramlib/sun60iw2p1/spl_libdram/libdram')
    if digest(tina / ddr) != '5361d148fa097ccc14e15a173523783d0eb1a71969bc76d57eb8e1229ddc6d90':
        raise ValueError('Unexpected DDR library')
    copy(ddr)
    display = json.loads((ROOT / 'patches/linux/media-v30-replay/tina-display-inputs.json').read_text())
    for entry in display:
        if digest(tina / entry['source']) != entry['sha256']:
            raise ValueError('Unexpected display source: ' + entry['source'])
        copy(Path(entry['source']))
    copy(Path('bsp/modules/gpu/img-bxm/linux/rogue_km'), source_only=True)
    gpu = Path('platform/allwinner/display/libgpu/img-bxm/gcc-arm-10.3-2021.07-x86_64-aarch64-none-linux-gnu')
    for platform in ('x11', 'wayland'):
        for sub in ('usr/lib', 'usr/local/lib', 'lib/firmware', 'powervr_icd.json'):
            copy(gpu / platform / sub)
    copy(CEDAR, source_only=True)
    # An immutable target feature header, not a configured build directory.
    copy(Path('out/t736/demo_aiot/buildroot/buildroot/build/libcedarc/config.h'))
    copy(Path('debian/packages/arm64/libcedarc/libcedarc-dev_2.0.0_arm64.deb'))
    copy(Path('buildroot/buildroot-202205/dl/gst-omx/gst-omx-1.20.1.tar.xz'))
    recipe = Path('buildroot/buildroot-202205/package/gstreamer1/gst-omx')
    for path in sorted((tina / recipe).glob('*.patch')):
        copy(path.relative_to(tina))
    copy(HOST / 'opt/ext-toolchain')
    copy(HOST / 'bin/toolchain-wrapper')
    for path in sorted((tina / HOST / 'bin').glob('aarch64-none-linux-gnu-*')):
        copy(path.relative_to(tina))
    sysroot = HOST / 'aarch64-buildroot-linux-gnu/sysroot'
    for relative in ('lib', 'lib64', 'usr/include', 'usr/lib', 'usr/lib64', 'usr/share/pkgconfig'):
        if (tina / sysroot / relative).exists() or (tina / sysroot / relative).is_symlink():
            copy(sysroot / relative)
    # Sysroot absolute links refer to the target root, never to host /usr/lib.
    for path in sorted((stage / sysroot).rglob('*')):
        if path.is_symlink() and os.readlink(path).startswith('/'):
            target = stage / sysroot / os.readlink(path).lstrip('/')
            path.unlink()
            path.symlink_to(os.path.relpath(target, path.parent))
    files = []
    for path in sorted(stage.rglob('*')):
        if path.is_symlink():
            target = path.resolve()
            if not target.is_relative_to(stage.resolve()):
                raise ValueError('Input symlink escapes package: ' + str(path))
            files.append({'path': path.relative_to(stage).as_posix(), 'link': os.readlink(path)})
        elif path.is_file():
            files.append({'path': path.relative_to(stage).as_posix(), 'size': path.stat().st_size, 'sha256': digest(path)})
    manifest = {'schema': 1, 'kind': 'atlasa1-minimal-build-inputs', 'display_files': len(display),
                'configured_omx_objects_included': False, 'files': files}
    (stage / 'INPUT-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = output / 'atlasa1-build-inputs-v1.tar.zst'
    subprocess.run(['tar', '--sort=name', '--owner=0', '--group=0', '--numeric-owner',
                    '--mtime=@1795392000', '-I', 'zstd -T4 -6', '-cf', str(archive),
                    '-C', str(output), 'inputs'], check=True)
    result = {'archive': archive.name, 'size': archive.stat().st_size,
              'sha256': digest(archive), 'input_manifest_sha256': digest(stage / 'INPUT-MANIFEST.json'),
              'files': len(files), 'display_files': len(display)}
    (output / 'archive.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tina', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    package(args.tina, args.output)
