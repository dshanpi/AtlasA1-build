import crypt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

image = Path(sys.argv[1]).resolve(strict=True)
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)

def run(*args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

loop = run('losetup', '--find', '--show', '--read-only', '--offset', 368640*512,
           '--sizelimit', 15239680*512, image)
try:
    with tempfile.TemporaryDirectory(prefix='atlasa1-content-') as folder:
        root = Path(folder)
        subprocess.run(['mount', '-t', 'ext4', '-o', 'ro,noload', loop, root], check=True)
        try:
            release = '6.18.63-current-atlasa1'
            required = [
                'usr/bin/gnome-shell', 'usr/sbin/gdm3',
                'usr/share/wayland-sessions/atlasa1-gnome.desktop',
                'usr/local/bin/atlasa1-gnome-session',
                'usr/libexec/mutter-x11-frames.atlasa1-real',
                'opt/atlasa1-img-wayland/runtime-gles/libEGL.so.1',
                'usr/bin/atlasa1-player', 'opt/atlasa1-player/bin/ffplay',
                'opt/atlasa1-player/lib/libavcodec.so.61',
                'opt/atlasa1-firefox/lib/libavcodec.so.62',
                'opt/atlasa1-firefox/lib/browser-panel-enabled',
                'opt/t736-cedar-transport-v2/bin/cedar-broker',
                'opt/t736-cedar-wc-v5/lib/libOmxVdec.so',
                'etc/udev/rules.d/70-t736-cedar.rules',
                f'usr/lib/modules/{release}/extra/pvrsrvkm.ko',
            ]
            hashes = {}
            for name in required:
                path = root/name
                assert path.is_file() and path.stat().st_size, name
                hashes[name] = sha(path)
            for name in ('opt/atlasa1-player/lib/libavcodec.so.61',
                         'opt/atlasa1-firefox/lib/libavcodec.so.62'):
                data = (root/name).read_bytes()
                assert b'h264_cedar\0' in data and b'hevc_cedar\0' in data, name
            assert b't736_broker_4k_buffers' in (root/'opt/t736-cedar-wc-v5/lib/libOmxVdec.so').read_bytes()
            vermagic = run('modinfo', '-F', 'vermagic', root/f'usr/lib/modules/{release}/extra/pvrsrvkm.ko')
            assert vermagic.startswith(release+' '), vermagic
            passwd = {line.split(':')[0]: line.split(':') for line in (root/'etc/passwd').read_text().splitlines()}
            user = passwd['t736']
            home = root/user[5].lstrip('/')
            assert home.is_dir() and home.stat().st_uid == int(user[2])
            shadow = {line.split(':')[0]: line.split(':')[1] for line in (root/'etc/shadow').read_text().splitlines()}
            assert all(crypt.crypt('1234', shadow[name]) == shadow[name] for name in ('root', 't736'))
            assert (root/'etc/systemd/system/armbian-resize-filesystem.service').readlink() == Path('/dev/null')
            assert (root/'etc/systemd/system/display-manager.service').readlink() == Path('/usr/lib/systemd/system/gdm.service')
            assert (root/'etc/systemd/system/sockets.target.wants/t736-cedar.socket').is_symlink()
            packages = run('dpkg-query', '--admindir='+str(root/'var/lib/dpkg'), '-W',
                           '-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n')
            assert not run('dpkg', '--admindir='+str(root/'var/lib/dpkg'), '--audit')
            (output/'native-installed-packages.tsv').write_text(packages+'\n')
            installed = {parts[0].split(':')[0]: parts[1] for line in packages.splitlines()
                         if len(parts := line.split('\t')) == 3 and parts[2].startswith('ii')}
            names = ['gnome-shell', 'gdm3', 'firefox', 'atlasa1-player', 'atlasa1-firefox-cedar',
                     'atlasa1-img-wayland', 't736-img-userspace-candidate',
                     'libreoffice-writer', 'gimp', 'inkscape', 'audacity', 'code',
                     'gnome-calendar', 'gnome-clocks', 'gnome-contacts',
                     'linux-image-current-atlasa1', 'linux-dtb-current-atlasa1', 'linux-u-boot-atlasa1-current']
            versions = {name: installed[name] for name in names}
            assert 'snap' not in versions['firefox']
            initrd = set(run('lsinitramfs', root/f'boot/initrd.img-{release}').splitlines())
            initrd_required = ['usr/sbin/wait-for-root', 'usr/lib/atlasa1/start-plymouth',
                               'etc/plymouth/atlasa1-enabled', 'scripts/init-premount/atlasa1-plymouth']
            assert set(initrd_required) <= initrd, set(initrd_required)-initrd
            result = dict(image=image.name, required_file_sha256=hashes, installed_packages=len(installed),
                          package_versions=versions, pvr_vermagic=vermagic, t736_home_preserved=True,
                          default_passwords_match=True, initrd_files=initrd_required,
                          dpkg_audit_clean=True,
                          cedar_decoders_present=True, gdm_selected=True, cedar_socket_enabled=True,
                          hardware_boot='not tested')
            (output/'native-image-content.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result, indent=2))
        finally:
            subprocess.run(['umount', root], check=True)
finally:
    subprocess.run(['losetup', '-d', loop], check=True)
