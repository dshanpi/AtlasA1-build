#!/usr/bin/env python3
"""Maintainer: freeze exact installed distribution packages from verified APT indexes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def freeze(inventory, cache, output):
    data = json.loads(inventory.read_text())
    if data['missing']:
        raise ValueError('Missing exact package versions: ' + str(data['missing']))
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    repo = output / 'packages'
    pool = repo / 'pool'
    pool.mkdir(parents=True)
    candidates = list(cache.glob('*.deb'))
    with ThreadPoolExecutor(max_workers=4) as executor:
        cached = dict(executor.map(lambda p: (sha(p), p), candidates))

    def download(item):
        name, record = item
        expected = record['SHA256']
        dest = pool / (expected[:16] + '-' + Path(record['Filename']).name)
        prefix = record['index'].split('_dists_', 1)[0].replace('_', '/')
        urls = ['https://' + prefix.rstrip('/') + '/' + record['Filename'].lstrip('/')]
        if 'ubuntu' in prefix:
            urls.append('https://ports.ubuntu.com/' + record['Filename'].lstrip('/'))
        origin = 'verified-local-apt-cache'
        if expected in cached:
            shutil.copyfile(cached[expected], dest)
        else:
            last = None
            for attempt in range(3):
                for url in urls:
                    try:
                        with urllib.request.urlopen(url, timeout=60) as source, dest.open('wb') as target:
                            shutil.copyfileobj(source, target, 1024 * 1024)
                        if dest.stat().st_size != int(record['Size']) or sha(dest) != expected:
                            raise ValueError('Downloaded package hash mismatch: ' + name)
                        origin = url
                        break
                    except (OSError, ValueError) as exc:
                        last = exc
                else:
                    time.sleep(attempt + 1)
                    continue
                break
            else:
                raise RuntimeError('Cannot freeze ' + name) from last
        if dest.stat().st_size != int(record['Size']) or sha(dest) != expected:
            raise ValueError('Package verification failed: ' + name)
        return {'package': name, 'version': record['Version'], 'architecture': record['Architecture'],
                'file': dest.relative_to(repo).as_posix(), 'size': dest.stat().st_size,
                'sha256': expected, 'origin': origin}

    records = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(download, item) for item in data['records'].items()]
        for future in as_completed(futures):
            records.append(future.result())
            if len(records) % 100 == 0:
                print(f'Verified {len(records)}/{len(futures)} exact package versions', flush=True)
    with (repo / 'Packages').open('wb') as stream:
        subprocess.run(['dpkg-scanpackages', '--multiversion', 'pool', '/dev/null'], cwd=repo,
                       stdout=stream, stderr=subprocess.PIPE, check=True)
    (repo / 'Packages.gz').write_bytes(gzip.compress((repo / 'Packages').read_bytes(), mtime=0))
    manifest = {'schema': 1, 'kind': 'atlasa1-frozen-arm64-packages',
                'rebuilt_separately': data['excluded_rebuilt'],
                'packages': sorted(records, key=lambda r: r['package'])}
    (repo / 'PACKAGE-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = output / 'atlasa1-arm64-packages-v1.tar.zst'
    subprocess.run(['tar', '--sort=name', '--owner=0', '--group=0', '--numeric-owner',
                    '--mtime=@1795392000', '-I', 'zstd -T4 -3', '-cf', str(archive),
                    '-C', str(output), 'packages'], check=True)
    result = {'archive': archive.name, 'sha256': sha(archive), 'size': archive.stat().st_size,
              'package_count': len(records), 'manifest_sha256': sha(repo / 'PACKAGE-MANIFEST.json')}
    (output / 'archive.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--apt-cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    freeze(args.inventory, args.apt_cache, args.output)
