#!/usr/bin/env python3
"""Check an installed AtlasA1 image against its disk image manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def run(*argv, check=True):
    return subprocess.run(argv, capture_output=True, text=True, timeout=30, check=check,
                          env=dict(os.environ, LC_ALL='C')).stdout.strip()


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def emmc_readback(manifest):
    records = {}
    with open('/dev/mmcblk0', 'rb', buffering=0) as disk:
        for item in manifest['components']:
            disk.seek(512 * item['sector'])
            buf = disk.read(item['bytes'])
            checksum = hashlib.sha256(buf).hexdigest()
            records[str(item['sector'])] = checksum == item['sha256'] and len(buf) == item['bytes']
        disk.seek(512 * 16)
        header = disk.read(32)
        length = int.from_bytes(header[16:20], 'little')
        if header[4:12] != b'eGON.BT0' or not 0 < length <= 512 * 1024:
            records['spl'] = False
        else:
            disk.seek(512 * 16)
            records['spl'] = hashlib.sha256(disk.read(length)).hexdigest() == manifest['spl_sha256']
    return records


def filesystem_test():
    payload = os.urandom(4 * 1024 * 1024)
    with tempfile.NamedTemporaryFile(dir='/var/tmp') as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
        if hasattr(os, 'posix_fadvise'):
            os.posix_fadvise(f.fileno(), 0, len(payload), os.POSIX_FADV_DONTNEED)
        f.seek(0)
        return f.read() == payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if os.geteuid() or b'allwinner,t736' not in Path('/proc/device-tree/compatible').read_bytes().split(b'\x00'):
        parser.error('expected root on the AtlasA1 board')
    root = run('findmnt', '-n', '-o', 'SOURCE', '/')
    if root != '/dev/mmcblk0p4':
        parser.error('expected the fourth eMMC partition as root')
    partuuid = run('blkid', '-s', 'PARTUUID', '-o', 'value', root)
    if partuuid.lower() != manifest['root_partuuid']:
        parser.error('root PARTUUID does not match the supplied manifest')
    kernel = os.uname().release
    images = [name.removeprefix('boot/vmlinuz-').removesuffix('.atlasa1.gz') for name in manifest['boot_files']
              if name.startswith('boot/vmlinuz-')]
    if len(images) != 1:
        parser.error('expected one versioned Linux image in the manifest')
    boots = {name: digest(Path('/')/name) == checksum
             for name, checksum in manifest['boot_files'].items()}
    storage = emmc_readback(manifest)
    display_manager = Path('/etc/systemd/system/display-manager.service').resolve().name
    if display_manager not in ('gdm.service', 'lightdm.service'):
        parser.error('unsupported display manager')
    units = {unit: run('systemctl', 'is-active', unit, check=False) for unit in
             ('serial-getty@ttyS0.service', display_manager, 'NetworkManager.service',
              'systemd-udevd.service', 't736-cedar.socket', 'ssh.service')}
    hdmi = {}
    for connector in Path('/sys/class/drm').glob('card*-HDMI-*'):
        hdmi[connector.name] = {n: (connector/n).read_text().strip()
                                for n in ('status', 'enabled') if (connector/n).is_file()}
    modes = []
    for state in Path('/sys/kernel/debug/dri').glob('[0-9]*/state'):
        for crtc in re.split(r'(?m)^crtc\[', state.read_text())[1:]:
            if re.search(r'(?m)^\s*active=1$', crtc):
                modes.extend(re.findall(r'(?m)^\s*mode:\s*([^\n]+)', crtc))
    os_release = Path('/usr/lib/os-release').read_text()
    hosts = list(Path('/etc/ssh').glob('ssh_host_*_key'))
    failed = run('systemctl', '--failed', '--plain', '--no-legend', '--no-pager')
    record = dict(kernel=kernel, root_device=root, root_partuuid=partuuid,
                  rootfs_uuid=run('blkid', '-s', 'UUID', '-o', 'value', root),
                  kernel_command_line=Path('/proc/cmdline').read_text().strip(),
                  release_files=boots, emmc_boot_components=storage, services=units,
                  failed_units=failed.splitlines(), hdmi=hdmi, active_drm_modes=modes,
                  desktop_sessions=run('loginctl', 'list-sessions', '--no-legend').splitlines(),
                  alsa_cards=Path('/proc/asound/cards').read_text().strip()
                  if Path('/proc/asound/cards').exists() else '',
                  display_manager=display_manager, package_audit=run('dpkg', '--audit'))
    record['checks'] = dict(ubuntu_resolute='VERSION_CODENAME=resolute' in os_release,
                            released_kernel=kernel == images[0],
                            boot_files=all(boots.values()), raw_boot_stages=all(storage.values()),
                            rootfs_uuid=record['rootfs_uuid'] == manifest['rootfs_uuid'],
                            emmc_file_fsync_readback=filesystem_test(),
                            initialized_identity=len(Path('/etc/machine-id').read_text().strip()) == 32,
                            generated_ssh_host_keys=bool(hosts),
                            display_manager=units[display_manager] == 'active',
                            hdmi_connector_enabled=any(s.get('status') == 'connected' and
                                                       s.get('enabled') == 'enabled' for s in hdmi.values()),
                            cedar_socket=units['t736-cedar.socket'] == 'active',
                            powervr_render_node=any(p.joinpath('device/driver/module').resolve().name == 'pvrsrvkm'
                                                    for p in Path('/sys/class/drm').glob('renderD*')),
                            package_db_clean=not record['package_audit'])
    print(json.dumps(record, indent=2))
    return 0 if all(record['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
