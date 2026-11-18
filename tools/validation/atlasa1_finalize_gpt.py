#!/usr/bin/env python3
"""Verify AtlasA1 GPT copies; --apply relocates the RC1 backup to the eMMC end."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import uuid
import zlib

SECTOR = 512
DISK = Path('/dev/mmcblk0')
MIRROR = 40960


def require(ok, message):
    if not ok:
        raise ValueError(message)


def region(disk, lba, size):
    disk.seek(lba * SECTOR)
    data = disk.read(size)
    require(len(data) == size, 'short read at LBA '+str(lba))
    return data


def table(disk, lba, sectors):
    header = bytearray(region(disk, lba, SECTOR))
    size, crc = struct.unpack_from('<II', header, 12)
    require(header[:8] == b'EFI PART' and size == 92, 'unexpected GPT header')
    struct.pack_into('<I', header, 16, 0)
    require(zlib.crc32(header[:size]) == crc, 'GPT header checksum')
    here, other, first, last = struct.unpack_from('<QQQQ', header, 24)
    array, count, stride, checksum = struct.unpack_from('<QIII', header, 72)
    require(here == lba and 0 < other < sectors and first <= last < sectors, 'GPT sector bounds')
    require((count, stride) == (6, 128) and array in (2, lba-2), 'unexpected AtlasA1 partition array')
    entries = region(disk, array, count * stride)
    require(zlib.crc32(entries) == checksum, 'partition entries checksum')
    return other, first, last, bytes(header[56:72]), entries


def backup_pair(disk, sectors):
    alternate, first, last, guid, entries = table(disk, 1, sectors)
    require(table(disk, alternate, sectors) == (1, first, last, guid, entries), 'GPT copies disagree')
    return alternate, entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    require(os.geteuid() == 0 and b'allwinner,t736' in Path('/proc/device-tree/compatible').read_bytes().split(b'\0'),
            'expected root on the T736 board')
    require(Path('/sys/block/mmcblk0/device/type').read_text().strip() == 'MMC' and
            subprocess.check_output(['findmnt','-no','SOURCE','/'], text=True).strip() == '/dev/mmcblk0p4',
            'unexpected disk or root partition')
    sectors = int(Path('/sys/block/mmcblk0/size').read_text())
    image_end = manifest['bytes'] // SECTOR - 1
    require(manifest['bytes'] % SECTOR == 0 and image_end < sectors, 'wrong image or device size')
    with DISK.open('r+b' if args.apply else 'rb', buffering=0) as disk:
        before, entries = backup_pair(disk, sectors)
        require(before in (image_end, sectors-1), 'unexpected backup location')
        root_guid = uuid.UUID(bytes_le=entries[3*128+16:3*128+32])
        root_start = struct.unpack_from('<Q', entries, 3*128+32)[0]
        require(str(root_guid) == manifest['root_partuuid'] and root_start == manifest['rootfs_lba'],
                'root partition does not match the manifest')
        primary = region(disk, 0, 16*SECTOR)
        mirror = region(disk, MIRROR, len(primary))
        changed = False
        if args.apply and (before != sectors-1 or primary != mirror):
            directory = Path(tempfile.mkdtemp(prefix='atlas-gpt-before-', dir='/root'))
            for name, data in [('primary', primary), ('vendor-mirror', mirror),
                               ('image-end', region(disk,image_end-33,34*SECTOR)),
                               ('device-end', region(disk,sectors-34,34*SECTOR))]:
                with (directory/(name+'.bin')).open('xb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            os.sync()
            if before != sectors-1:
                require(primary == mirror, 'unexpected vendor mirror before relocation')
                subprocess.run(['sfdisk', '--no-reread', '--no-tell-kernel', '--relocate', 'gpt-bak-std',
                                str(DISK)], check=True, stdout=subprocess.DEVNULL)
            require(backup_pair(disk,sectors) == (sectors-1, entries), 'relocated GPT verification failed')
            primary = region(disk, 0, 16*SECTOR)
            disk.seek(MIRROR*SECTOR)
            require(disk.write(primary) == len(primary), 'short vendor mirror write')
            os.fsync(disk.fileno())
            changed = True
        after, final_entries = backup_pair(disk, sectors)
        matches = region(disk, MIRROR, len(primary)) == region(disk, 0, len(primary))
        record = dict(before_backup_lba=before, after_backup_lba=after, disk_last_lba=sectors-1,
                      primary_and_backup_crc_valid=True, vendor_mirror_matches=matches,
                      partition_entries_unchanged=entries == final_entries, changed=changed,
                      partition_array_sha256=hashlib.sha256(entries).hexdigest())
        print(json.dumps(record, indent=2))
        return 0 if after == sectors-1 and matches else 1


if __name__ == '__main__':
    raise SystemExit(main())
