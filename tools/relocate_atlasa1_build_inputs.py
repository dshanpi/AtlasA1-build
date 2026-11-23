#!/usr/bin/env python3
"""Prepare relocatable SDK compatibility paths from the versioned input bundle."""
import argparse
import json
import os
from pathlib import Path

HOST = Path('out/t736/demo_aiot/buildroot/buildroot/host')


def prepare(root):
    root = root.resolve(strict=True)
    host = root / HOST
    sysroot = host / 'aarch64-buildroot-linux-gnu/sysroot'
    binary = host / 'bin'
    for name, command in (('meson', '/usr/bin/meson'), ('ninja', '/usr/bin/ninja'), ('pkgconf', '/usr/bin/pkg-config')):
        path = binary / name
        path.write_text('#!/bin/sh\nexec ' + command + ' "$@"\n')
        path.chmod(0o755)
    path = binary / 'pkg-config'
    path.write_text('''#!/bin/sh
set -eu
sdk=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
sysroot=$sdk/aarch64-buildroot-linux-gnu/sysroot
export PKG_CONFIG_SYSROOT_DIR=${PKG_CONFIG_SYSROOT_DIR:-$sysroot}
export PKG_CONFIG_LIBDIR=${PKG_CONFIG_LIBDIR:-$sysroot/usr/lib/pkgconfig:$sysroot/usr/share/pkgconfig}
exec /usr/bin/pkg-config "$@"
''')
    path.chmod(0o755)
    # Meson uses the supplied paths; no developer home directory is consulted.
    def quote(value):
        return "'" + str(value).replace('\\', '\\\\').replace("'", "\\'") + "'"
    cross = host / 'etc/meson/cross-compilation.conf'
    cross.parent.mkdir(parents=True, exist_ok=True)
    lines = ['[binaries]']
    for key, name in [('c', 'gcc'), ('cpp', 'g++'), ('ar', 'gcc-ar'), ('strip', 'strip')]:
        lines.append(key + ' = ' + quote(binary / ('aarch64-none-linux-gnu-' + name)))
    lines += ['pkgconfig = ' + quote(binary / 'pkg-config'),
              '[built-in options]', "c_args = ['-D_LARGEFILE_SOURCE', '-D_LARGEFILE64_SOURCE', '-D_FILE_OFFSET_BITS=64', '-Os', '-g0', '-D_FORTIFY_SOURCE=1']",
              "wrap_mode = 'nodownload'", '[properties]', 'needs_exe_wrapper = true',
              'sys_root = ' + quote(sysroot), 'pkg_config_libdir = ' + quote(str(sysroot / 'usr/lib/pkgconfig') + ':' + str(sysroot / 'usr/share/pkgconfig')),
              '[host_machine]', "system = 'linux'", "cpu_family = 'aarch64'", "cpu = 'cortex-a76'", "endian = 'little'"]
    cross.write_text('\n'.join(lines) + '\n')
    old = '/home/ubuntu/t736-aiot/tina'
    changed = []
    for path in sysroot.rglob('*'):
        if not path.is_symlink() and path.is_file() and path.suffix in ('.pc', '.la', '.cmake'):
            text = path.read_text()
            if old in text:
                path.write_text(text.replace(old, str(root)))
                changed.append(path.relative_to(root).as_posix())
    (root / 'RELOCATION.json').write_text(json.dumps({'root': str(root), 'rewritten_metadata': changed}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    prepare(parser.parse_args().inputs)
