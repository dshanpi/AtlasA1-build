#!/usr/bin/env python3
"""Prepare board source repositories for Armbian's normal compiler stages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DISPLAY_PATCHES = ['v36-vblank.patch', 'v38-rcq-poll.patch', 'v40-cedar-import.patch',
                   'v41-prime-scanout.patch', 'v42-trace-api.patch', 'v46-mmc-tuning-log.patch']
HARDWARE_PATCHES = ['atlasa1-wireless-v31.patch', 'atlasa1-pcie-v32.patch',
                    'atlasa1-wireless-dldo5-v33.patch', 'atlasa1-wireless-reset-v33.patch',
                    'atlasa1-pcie-combo1-v33.patch', 'atlasa1-pcie-pipe-map-v34.patch',
                    'atlasa1-pcie-dma-v43.patch', 'atlasa1-pcie-aspm-v45.patch']


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def kernel_config():
    settings = {}
    for filename in ['patches/linux/media-v30-replay/kernel.config',
                     'boards/wireless-v31/kernel.config', 'boards/pcie-v32/pcie.config']:
        for line in (ROOT/filename).read_text().splitlines():
            match = re.match(r'(?:# )?(CONFIG_[A-Z0-9_]+)(?:=| is not set)', line)
            if match:
                settings[match[1]] = line
    changes = {'LOCALVERSION': '""', 'LOCALVERSION_AUTO': 'n', 'PCIEPORTBUS': 'y',
               'PREEMPT_DYNAMIC': 'n', 'PREEMPT': 'n', 'PREEMPT_NONE': 'y',
               'PREEMPT_NONE_BUILD': 'y', 'FTRACE': 'y', 'FUNCTION_TRACER': 'y',
               'FUNCTION_GRAPH_TRACER': 'y', 'CONSOLE_LOGLEVEL_DEFAULT': '5'}
    for key, value in changes.items():
        name = 'CONFIG_'+key
        settings[name] = f'# {name} is not set' if value == 'n' else f'{name}={value}'
    return '\n'.join(settings.values())+'\n'


def fingerprint():
    h = hashlib.sha256()
    for directory in ('patches/linux', 'patches/u-boot/media-v28-replay', 'boards/wireless-v31',
                      'boards/pcie-v32'):
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file():
                h.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes())
    for filename in ('tools/prepare_atlas_release_sources.py', 'tools/prepare_atlasa1_native_sources.py',
                     'tools/build_atlasa1_release_boot.py', 'config/clean-build/inputs.lock.json'):
        h.update((ROOT/filename).read_bytes())
    return h.hexdigest()


def patch(tree, filename):
    run('patch', '--batch', '--forward', '--fuzz=0', '-d', tree, '-p1', '-i', ROOT/filename)


def init_git(path, branch):
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-11-23T00:00:00Z', GIT_COMMITTER_DATE='2026-11-23T00:00:00Z')
    run('git', 'init', '-q', '-b', branch, path)
    run('git', '-C', path, 'add', '-f', '.')
    run('git', '-C', path, '-c', 'user.name=AtlasA1 Build', '-c', 'user.email=build@atlasa1.invalid',
        'commit', '-qm', 'Prepare verified AtlasA1 board sources', env=env)


def prepare(inputs, work):
    import fcntl
    identity = fingerprint()
    work.mkdir(parents=True, exist_ok=True)
    with (work/'.sources.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        target = work/('sources-'+identity[:16])
        marker = target/'native-sources.json'
        if marker.exists():
            if json.loads(marker.read_text())['recipe_sha256'] != identity:
                raise ValueError('Source cache differs')
            return target
        target.mkdir()
        upstream = inputs/'source-inputs-v1'
        sdk = inputs/'inputs'
        helper = ROOT/'tools/prepare_atlas_release_sources.py'
        for component, archive in [('linux', 'linux.tar.gz'), ('u-boot', 'u-boot.tar.gz')]:
            run('python3', helper, component, '--archive', upstream/archive, '--tina', sdk,
                '--output', target/component)
        run('python3', helper, 'pvr', '--tina', sdk, '--output', target/'pvr')
        for name in DISPLAY_PATCHES:
            patch(target/'linux', 'patches/linux/gnome-media-20261119/'+name)
        for name in HARDWARE_PATCHES:
            patch(target/'linux', 'patches/linux/'+name)
        patch(target/'pvr', 'patches/linux/gnome-media-20261119/v42-pvr-trace-api.patch')
        (target/'kernel.config').write_text(kernel_config())
        from build_atlasa1_release_boot import release_boot_command
        config = (target/'u-boot/.config.atlasa1').read_text()
        config, count = re.subn(r'^CONFIG_BOOTCOMMAND=.*$',
            lambda _: 'CONFIG_BOOTCOMMAND='+json.dumps(release_boot_command()), config, flags=re.M)
        if count != 1:
            raise ValueError('Missing boot command')
        (target/'u-boot/configs/atlasa1_defconfig').write_text(config)
        for component in ('linux', 'u-boot'):
            init_git(target/component, 'atlasa1-v47')
        record = {'recipe_sha256': identity, 'upstream': json.loads((ROOT/'config/clean-build/inputs.lock.json').read_text())['sources'],
                  'linux': subprocess.check_output(['git', '-C', target/'linux', 'rev-parse', 'HEAD'], text=True).strip(),
                  'u-boot': subprocess.check_output(['git', '-C', target/'u-boot', 'rev-parse', 'HEAD'], text=True).strip()}
        marker.write_text(json.dumps(record, indent=2)+'\n')
        return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', action='store_true')
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--result', type=Path)
    args = parser.parse_args()
    if args.identity:
        print(fingerprint())
        raise SystemExit(0)
    if not all((args.inputs, args.work, args.result)):
        parser.error('--inputs, --work and --result are required')
    args.result.write_text(str(prepare(args.inputs.resolve(), args.work.resolve()))+'\n')
