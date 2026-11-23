#!/usr/bin/env python3
"""Bootstrap the locked ARM64 package set, not a previously built rootfs."""
import argparse
import functools
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import threading


def run(*args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def build(packages, bsp, output, recipe):
    output.mkdir()
    repo = output / 'repo'
    repo.mkdir()
    # Link immutable inputs; the local HTTP server reads their verified bytes.
    def link(src, dst):
        try:
            Path(dst).hardlink_to(src)
        except OSError:
            Path(dst).symlink_to(Path(src).resolve())
    shutil.copytree(packages / 'pool', repo / 'pool', copy_function=link)
    board = list(bsp.glob('armbian-bsp-cli-t736-mainline-current_*_arm64__*.deb'))
    base = list(bsp.glob('extra/resolute-utils/base-files_*resolute_arm64__*.deb'))
    if len(board) != 1 or len(base) != 1:
        raise ValueError('Expected freshly compiled BSP and base-files packages')
    for p in board + base:
        link(p, repo / 'pool' / p.name)
    with (repo / 'Packages').open('wb') as f:
        run('dpkg-scanpackages', '--multiversion', 'pool', '/dev/null', cwd=repo, stdout=f,
            stderr=subprocess.PIPE)
    # mmdebstrap selects Essential packages by suite/codename even for a flat
    # repository. Without Release it silently selects an empty bootstrap set.
    with (repo / 'Release').open('wb') as f:
        run('apt-ftparchive', '-o', 'APT::FTPArchive::Release::Suite=resolute',
            '-o', 'APT::FTPArchive::Release::Codename=resolute',
            '-o', 'APT::FTPArchive::Release::Architectures=arm64',
            'release', '.', cwd=repo, stdout=f)
    manifest = json.loads((packages / 'PACKAGE-MANIFEST.json').read_text())
    includes = [p['package'] + '=' + p['version'] for p in manifest['packages']]
    for p in board + base:
        name = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Package'], text=True).strip()
        version = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Version'], text=True).strip()
        includes.append(name + '=' + version)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 18765), functools.partial(Quiet, directory=str(repo)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    root = output / 'rootfs'
    try:
        run('mmdebstrap', '--architectures=arm64', '--variant=minbase', '--format=directory',
            '--dpkgopt=force-unsafe-io',
            '--aptopt=APT::Install-Recommends "false"',
            '--aptopt=Acquire::Languages "none"', '--include=' + ','.join(includes),
            'resolute', root, 'deb [trusted=yes] http://127.0.0.1:18765 ./')
        # The same release configuration used by the original Armbian image.
        run('bash', recipe / 'tools/prepare_t736_resolute_rootfs.sh', root, root, bsp)
    finally:
        server.shutdown()
        server.server_close()
    (output / 'ROOTFS-BOOTSTRAP.json').write_text(json.dumps({
        'schema': 1, 'source': 'frozen distribution debs and freshly rebuilt Armbian BSP',
        'copied_existing_rootfs': False, 'package_specs': sorted(includes)}, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('packages', 'bsp', 'output', 'recipe'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    build(*(getattr(a, name).resolve() for name in ('packages', 'bsp', 'output', 'recipe')))
