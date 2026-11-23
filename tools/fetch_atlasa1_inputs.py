#!/usr/bin/env python3
"""Download immutable build inputs; never accept a partial or mismatched asset."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def fetch(lock, directory):
    data = json.loads(lock.read_text())
    directory.mkdir(parents=True, exist_ok=True)
    for item in data['assets']:
        name = item['name']
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Invalid asset name')
        target = directory / name
        def valid(p):
            return p.is_file() and p.stat().st_size == item['size'] and sha(p) == item['sha256']
        if valid(target):
            print('Verified cached input: ' + name, flush=True)
            continue
        if target.exists():
            raise RuntimeError('Cached input has wrong hash; remove it explicitly: ' + str(target))
        partial = target.with_name(name + '.partial')
        if valid(partial):
            partial.replace(target)
            print('Recovered verified download: ' + name, flush=True)
            continue
        subprocess.run(['curl', '--fail', '--location', '--retry', '5', '--retry-all-errors', '--retry-delay', '3',
                        '--connect-timeout', '30', '--continue-at', '-', '--output', str(partial),
                        item['url']], check=True)
        if not valid(partial):
            raise RuntimeError('Downloaded input hash/size mismatch: ' + name)
        partial.replace(target)
        print('Downloaded and verified: ' + name, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('lock', type=Path)
    p.add_argument('cache', type=Path)
    a = p.parse_args()
    fetch(a.lock, a.cache)
