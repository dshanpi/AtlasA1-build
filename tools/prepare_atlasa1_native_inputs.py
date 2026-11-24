#!/usr/bin/env python3
"""Fetch verified sources for the official Armbian build framework."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from fetch_atlasa1_inputs import fetch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ['atlasa1-build-inputs-v1.tar.zst', 'atlasa1-upstream-sources-v2.tar.zst']


def prepare(cache, work):
    cache.mkdir(parents=True, exist_ok=True)
    lock = ROOT / 'config/clean-build/inputs.lock.json'
    identity = hashlib.sha256(lock.read_bytes()).hexdigest()
    with (cache / '.download.lock').open('a') as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        fetch(lock, cache, ASSETS)
        work.mkdir(parents=True, exist_ok=True)
        with (work / '.prepare.lock').open('a') as prepare_lock:
            fcntl.flock(prepare_lock, fcntl.LOCK_EX)
            target = work / ('inputs-' + identity[:16])
            marker = target / 'verified-inputs.json'
            if marker.exists():
                if json.loads(marker.read_text())['lock_sha256'] != identity:
                    raise ValueError('Input cache identity differs')
                return target
            if target.exists():
                raise ValueError('Incomplete input cache: ' + str(target))
            with tempfile.TemporaryDirectory(prefix='.inputs-', dir=work) as temp:
                staging = Path(temp) / 'payload'
                staging.mkdir()
                for name in ASSETS:
                    subprocess.run(['tar', '--no-same-owner', '-I', 'zstd', '-xf', cache/name,
                                    '-C', staging], check=True)
                staging.rename(target)
            # Relocation records contain absolute toolchain paths.
            subprocess.run(['python3', ROOT/'tools/relocate_atlasa1_build_inputs.py',
                            target/'inputs'], check=True)
            marker.write_text(json.dumps({'lock_sha256': identity, 'assets': ASSETS}, indent=2)+'\n')
            return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path(os.environ.get('ATLAS_DOWNLOAD_CACHE', '~/.cache/atlasa1')).expanduser())
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.cache.resolve(), args.work.resolve())
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(str(result)+'\n')
