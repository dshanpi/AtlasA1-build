#!/usr/bin/env python3
"""Install AtlasA1 userpatches and the upstream family-menu compatibility fix."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FILES = ['config/boards/atlasa1.conf', 'config/sources/families/atlasa1.conf',
         'config/kernel/linux-atlasa1-current.config', 'extensions/atlasa1.sh']
REVISION = '2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fix_family_menu(framework):
    patch = ROOT/'patches/armbian/menu-user-family.patch'
    command = ['git', '-C', str(framework), 'apply']
    applied = subprocess.run([*command, '--reverse', '--check', str(patch)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if applied.returncode == 0:
        return
    subprocess.run([*command, '--check', str(patch)], check=True)
    subprocess.run([*command, str(patch)], check=True)


def install(framework):
    if not (framework/'lib/single.sh').is_file():
        raise ValueError('Expected official Armbian build sources')
    if subprocess.check_output(['git','-C',framework,'rev-parse','HEAD'],text=True).strip()!=REVISION:
        raise ValueError('Use the documented official Armbian revision: '+REVISION)
    user = framework/'userpatches';user.mkdir(exist_ok=True)
    state = user/'.atlasa1-managed.json'
    old = json.loads(state.read_text()) if state.exists() else {}
    preserved = set()
    for name in FILES:
        source = ROOT/'userpatches'/name;target = user/name
        if target.exists() and digest(target) not in (digest(source),old.get(name)):
            if name == 'config/kernel/linux-atlasa1-current.config':
                preserved.add(name)
                print('Keeping user kernel configuration: '+str(target))
                continue
            raise ValueError('Preserving modified user file: '+str(target))
    fix_family_menu(framework)
    link = user/'atlasa1-release'
    if link.exists() or link.is_symlink():
        if link.resolve()!=ROOT:
            raise ValueError('Existing recipe path differs: '+str(link))
    else:link.symlink_to(ROOT,target_is_directory=True)
    for name in FILES:
        if name in preserved:
            continue
        target=user/name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.resolve()!=(ROOT/'userpatches'/name).resolve():
            shutil.copyfile(ROOT/'userpatches'/name,target)
    state.write_text(json.dumps({name:old.get(name) if name in preserved else digest(ROOT/'userpatches'/name)
                               for name in FILES},indent=2)+'\n')
    print('AtlasA1 installed. Run ./compile.sh or ./compile.sh BOARD=atlasa1 BRANCH=current kernel-config')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('armbian',type=Path)
    install(parser.parse_args().armbian.resolve(strict=True))
