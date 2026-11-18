#!/usr/bin/env python3
"""Collect board I/O enumeration without changing radio, link or power state."""
import json
import os
from pathlib import Path


def read(path):
    try:
        return path.read_text().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def driver(device):
    link = device / 'driver'
    return link.resolve().name if link.is_symlink() else None


def fields(device, names):
    return {name: read(device / name) for name in names}


def main():
    if b'allwinner,t736' not in Path('/proc/device-tree/compatible').read_bytes().split(b'\x00'):
        raise SystemExit('Expected an AtlasA1 / T736 device')
    mmc = {}
    for entry in sorted(Path('/sys/class/mmc_host').glob('mmc*')):
        mmc[entry.name] = dict(host_driver=driver(entry/'device'),
                               cards=[dict(type=read(card/'type'), name=read(card/'name'))
                                      for card in entry.glob('mmc*:*')])
    sdio = {f.name: dict(driver=driver(f), **fields(f, ('vendor', 'device', 'class', 'modalias')))
            for f in sorted(Path('/sys/bus/sdio/devices').glob('*'))}
    wifi = {n.name: dict(phy=(n/'phy80211').resolve().name, driver=driver(n/'device'),
                         state=read(n/'operstate')) for n in sorted(Path('/sys/class/net').glob('*'))
            if (n/'phy80211').is_symlink()}
    bluetooth = {b.name: dict(driver=driver(b/'device'), transport=b.resolve().parent.name)
                 for b in sorted(Path('/sys/class/bluetooth').glob('hci*'))}
    rfkill = [fields(i, ('name', 'type', 'soft', 'hard')) for i in sorted(Path('/sys/class/rfkill').glob('rfkill*'))]
    pci = {p.name: dict(driver=driver(p), **fields(p, ('vendor', 'device', 'class',
               'current_link_speed', 'current_link_width', 'max_link_speed', 'max_link_width')))
           for p in sorted(Path('/sys/bus/pci/devices').glob('*'))}
    controllers = {p.name: driver(p) for p in Path('/sys/bus/platform/devices').glob('*')
                   if 'pcie' in p.name.lower() or 'combo-phy' in p.name.lower()}
    print(json.dumps(dict(kernel=os.uname().release, mmc_hosts=mmc, sdio=sdio, wireless_interfaces=wifi,
                          bluetooth_controllers=bluetooth, rfkill=rfkill,
                          pci_host_devices=controllers, pci_functions=pci,
                          nvme_namespaces=sorted(x.name for x in Path('/sys/block').glob('nvme*n*'))), indent=2))


if __name__ == '__main__':
    main()
