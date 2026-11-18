#!/usr/bin/env python3
"""Install the private manifest's local Debian packages in the target rootfs."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile

PLAYER_TARGET = '/tmp/t736-vendor/atlasa1-player.deb'
PLAYER_FILES = {
    'opt/atlasa1-player/bin/ffplay': 0o755,
    'opt/atlasa1-player/lib/libavcodec.so.61': 0o644,
    'opt/atlasa1-player/lib/libavutil.so.59': 0o644,
    'opt/atlasa1-player/lib/libt736_cedar_client.so': 0o644,
    'usr/bin/atlasa1-player': 0o755,
    'usr/share/applications/atlasa1-player.desktop': 0o644,
}


def inspect_player(deb):
    fields = subprocess.check_output(['dpkg-deb', '--show', '--showformat=${Package}\t${Architecture}\t${Version}', deb],
                                     text=True).split('\t')
    if len(fields) != 3 or fields[:2] != ['atlasa1-player', 'arm64'] or not fields[2]:
        raise ValueError('expected the arm64 atlasa1-player Debian package')
    payload = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', deb])
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        members = {str(PurePosixPath(m.name)): m for m in archive}
        for path, mode in PLAYER_FILES.items():
            member = members.get(path)
            if not member or not member.isfile() or (member.uid, member.gid, member.mode & 0o7777) != (0, 0, mode):
                raise ValueError('missing or incorrect player payload: /' + path)
            if path.startswith('opt/atlasa1-player/'):
                with archive.extractfile(member) as source:
                    header = source.read(20)
                if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != (183).to_bytes(2, 'little'):
                    raise ValueError('expected a little-endian AArch64 ELF: /' + path)
    return fields[2]


def install(root):
    manifest = json.loads((root/'etc/t736/vendor-manifest.json').read_text())
    packages = []
    player_version = None
    for item in manifest['files']:
        target = PurePosixPath(item['target'])
        player = item.get('role') == 'native_player'
        if player and (str(target) != PLAYER_TARGET or item.get('kind') != 'deb'):
            raise ValueError('invalid native_player package target or kind')
        if target.parent != PurePosixPath('/tmp/t736-vendor') or target.suffix != '.deb':
            continue
        if str(target) in packages or (str(target) == PLAYER_TARGET and not player):
            raise ValueError('conflicting Debian package target: ' + str(target))
        package = root / target.relative_to('/')
        if hashlib.sha256(package.read_bytes()).hexdigest() != item['sha256'].lower():
            raise ValueError('staged Debian package differs from manifest: ' + str(target))
        if player:
            player_version = inspect_player(package)
        packages.append(str(target))
    if packages:
        subprocess.run(['chroot', root, 'apt-get', 'install', '-y', '--reinstall', '--no-install-recommends', *packages],
                       check=True)
    if player_version:
        query = ['chroot', root, 'dpkg-query', '-W', '-f=${Status}\t${Architecture}\t${Version}', 'atlasa1-player']
        if subprocess.check_output(query, text=True) != 'install ok installed\tarm64\t'+player_version:
            raise ValueError('target package database did not confirm atlasa1-player installation')
        for path, mode in PLAYER_FILES.items():
            st = (root/path).lstat()
            if not stat.S_ISREG(st.st_mode) or (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (0,0,mode):
                raise ValueError('incorrect installed player file: /' + path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    install(parser.parse_args().root.resolve(strict=True))
