#!/usr/bin/env python3
"""Create and verify the AtlasA1 eMMC layout inside Armbian image files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import uuid
import zlib

SECTOR = 512
SECTORS = 16777216
ROOT_ID = 'a0085546-4166-744a-a353-fca9272b8e48'
LAYOUT = [('boot-resource', 73728, 65536), ('env', 139264, 32768),
          ('boot', 172032, 196608), ('rootfs', 368640, 15239680),
          ('private', 15608320, 32768), ('UDISK', 15641088, SECTORS-15641088-34)]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(*args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()


def tables():
    entries = bytearray()
    for i, (name, start, size) in enumerate(LAYOUT):
        entries.extend(struct.pack('<16s16sQQQ72s',
            uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7').bytes_le,
            uuid.UUID(f'a0085546-4166-744a-a353-fca9272b8e{0x45+i:02x}').bytes_le,
            start, start+size-1, 1 << 63, name.encode('utf-16-le')))
    def header(current, backup, table):
        data = bytearray(struct.pack('<8sIIIIQQQQ16sQIII', b'EFI PART', 0x10000, 92, 0, 0,
            current, backup, 73728, SECTORS-34, uuid.UUID('ab6f3888-569a-4926-9668-80941dcb40bc').bytes_le,
            table, len(LAYOUT), 128, zlib.crc32(entries)))
        struct.pack_into('<I', data, 16, zlib.crc32(data))
        return data+bytes(SECTOR-len(data))
    mbr = bytearray(SECTOR)
    struct.pack_into('<B3sB3sII', mbr, 446, 0, b'\0\2\0', 0xee, b'\xff\xff\xff', 1, SECTORS-1)
    mbr[510:] = b'\x55\xaa'
    array = entries+bytes(-len(entries) % SECTOR)
    return bytes(mbr)+header(1, SECTORS-1, 2)+array, array+header(SECTORS-1, 1, SECTORS-3)


def image_file(path):
    path = Path(path).absolute()
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or path.stat().st_size != SECTORS*SECTOR:
        raise ValueError('Expected a regular 8 GiB image file')
    return path


def verify_table(path):
    primary, backup = tables()
    with Path(path).open('rb') as stream:
        for offset, expected in [(0, primary), (40960*SECTOR, primary),
                                 (SECTORS*SECTOR-len(backup), backup)]:
            stream.seek(offset)
            if stream.read(len(expected)) != expected:
                raise ValueError(f'AtlasA1 GPT differs at offset {offset}')
    parsed = json.loads(command('sfdisk', '--json', path))['partitiontable']['partitions']
    if [(p['name'], p['start'], p['size']) for p in parsed] != LAYOUT:
        raise ValueError('Partition map differs')
    if parsed[3]['uuid'].lower() != ROOT_ID:
        raise ValueError('Root PARTUUID differs')
    command('sfdisk', '--verify', path)


def partition(path):
    image = image_file(path)
    primary, backup = tables()
    with image.open('r+b') as stream:
        for offset, data in [(0, primary), (40960*SECTOR, primary),
                             (SECTORS*SECTOR-len(backup), backup)]:
            stream.seek(offset)
            stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    verify_table(image)


def parse_package(data):
    if struct.unpack_from('<IIII', data) != (0x36333754, 0x314c5053, 1, 3):
        raise ValueError('Unexpected boot package')
    header = bytearray(data[:512]); expected = struct.unpack_from('<I', header, 16)[0]
    struct.pack_into('<I', header, 16, 0)
    if zlib.crc32(header) != expected:
        raise ValueError('Boot header CRC differs')
    components = []
    for i, address in enumerate((0x47000000, 0x48000000, 0x52000000)):
        lba, load, length, crc = struct.unpack_from('<IIII', data, 32+16*i)
        offset = (lba-24576)*512
        if load != address or offset < 512 or length <= 0 or offset+length > len(data):
            raise ValueError('Invalid boot component')
        blob = data[offset:offset+length]
        if zlib.crc32(blob) != crc:
            raise ValueError('Boot payload CRC differs')
        components.append(hashlib.sha256(blob).hexdigest())
    return components


def write_boot(device, bundle):
    device = Path(device)
    if not device.name.startswith('loop') or not stat.S_ISBLK(device.lstat().st_mode):
        raise ValueError('Only an Armbian loop device is accepted')
    row = json.loads(command('losetup', '--json', '--output', 'NAME,BACK-FILE,OFFSET,SIZELIMIT', device))['loopdevices'][0]
    image = image_file(row['back-file'])
    if int(row['offset']) != 0 or int(row['sizelimit']) not in (0, SECTORS*SECTOR):
        raise ValueError('Loop does not span the whole image')
    verify_table(image)
    record = json.loads((bundle/'atlasa1-boot.json').read_text())
    spl = bundle/'atlasa1-spl.bin'; package = bundle/'atlasa1-package.bin'
    if sha(spl) != record['spl_sha256'] or sha(package) != record['boot_package_sha256']:
        raise ValueError('Boot package checksum differs')
    components = parse_package(package.read_bytes())
    if components != [item['sha256'] for item in record['components']]:
        raise ValueError('Boot components differ from the manifest')
    if components[-1] != sha(bundle/'u-boot.bin') or record['root_partuuid'] != ROOT_ID:
        raise ValueError('U-Boot does not match this image')
    if spl.stat().st_size > (24576-16)*512 or package.stat().st_size > (32800-24576)*512:
        raise ValueError('Boot data exceeds reserved sectors')
    with device.open('r+b', buffering=0) as stream:
        for lba, source in [(16, spl), (24576, package)]:
            data = source.read_bytes();stream.seek(lba*512);stream.write(data)
        os.fsync(stream.fileno())
        for lba, source in [(16, spl), (24576, package)]:
            data = source.read_bytes();stream.seek(lba*512)
            if stream.read(len(data)) != data:
                raise ValueError('Boot write readback differs')
    verify_table(image)


def boot_files(root):
    releases = [p.name for p in (root/'usr/lib/modules').iterdir() if p.is_dir() and p.name.endswith('-current-atlasa1')]
    if len(releases) != 1:
        raise ValueError('Expected one AtlasA1 kernel')
    release = releases[0]
    image = root/'boot'/('vmlinuz-'+release)
    initrd = root/'boot'/('initrd.img-'+release)
    dtb = root/'usr/lib'/('linux-image-'+release)/'allwinner/t736-pcie-v32.dtb'
    for path in (image, initrd, dtb):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing boot file: '+str(path))
    manifests = list((root/'usr/lib').glob('linux-u-boot-*/atlasa1-boot.json'))
    if len(manifests) != 1:
        raise ValueError('Expected one installed AtlasA1 boot package')
    bundle = manifests[0].parent
    manifest = json.loads(manifests[0].read_text())
    payloads = {}
    for filename, lba, key in [('atlasa1-spl.bin', 16, 'spl_sha256'),
                               ('atlasa1-package.bin', 24576, 'boot_package_sha256')]:
        path = bundle/filename
        if sha(path) != manifest[key]:
            raise ValueError('Installed boot package checksum differs')
        payloads[filename] = {'lba': lba, 'bytes': path.stat().st_size, 'sha256': manifest[key]}
    import gzip
    data = image.read_bytes()
    if data[56:60] != b'ARM\x64':
        raise ValueError('Expected an uncompressed ARM64 Image')
    compressed = image.with_name(image.name+'.atlasa1.gz')
    packed = gzip.compress(data, compresslevel=6, mtime=0)
    if len(data) > 10 * len(packed) or gzip.decompress(packed) != data:
        raise ValueError('Image exceeds the U-Boot decompression bound or gzip verification failed')
    compressed.write_bytes(packed)
    aliases = {'vmlinuz-6.18.63-t736-armbian': compressed.name,
               'initrd.img-6.18.63-t736-armbian': initrd.name}
    for name, target in aliases.items():
        link = root/'boot'/name
        if link.is_symlink():link.unlink()
        elif link.exists():raise ValueError('Boot alias is a regular file')
        link.symlink_to(target)
    destination = root/'boot/dtb/allwinner/t736-mainline-bringup.dtb'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(dtb.read_bytes())
    output = root/'usr/share/atlasa1/image-boot-files.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'kernel_release':release, 'payloads':payloads, 'files':{
        str(path.relative_to(root)):sha(path) for path in (compressed, initrd, destination)}},indent=2)+'\n')


def verify(image):
    image = image_file(image);verify_table(image)
    loop = command('losetup', '--find', '--show', '--read-only', '--offset', 368640*512,
                   '--sizelimit', LAYOUT[3][2]*512, image)
    try:
        subprocess.run(['e2fsck', '-fn', loop], check=True)
        with tempfile.TemporaryDirectory(prefix='atlasa1-readback-') as folder:
            folder = Path(folder);record_file = folder/'boot.json'
            command('debugfs', '-R', f'dump /usr/share/atlasa1/image-boot-files.json {record_file}', loop)
            record = json.loads(record_file.read_text())
            with image.open('rb') as stream:
                for name, payload in record['payloads'].items():
                    stream.seek(payload['lba']*SECTOR)
                    data = stream.read(payload['bytes'])
                    if hashlib.sha256(data).hexdigest() != payload['sha256']:
                        raise ValueError('Final boot payload readback differs: '+name)
                    if name == 'atlasa1-package.bin':
                        parse_package(data)
            for i, (name, expected) in enumerate(record['files'].items()):
                target = folder/str(i)
                command('debugfs', '-R', f'dump /{name} {target}', loop)
                if sha(target) != expected:raise ValueError('Boot file readback differs: '+name)
    finally:
        subprocess.run(['losetup', '-d', loop], check=True)
    result = {'image':image.name, 'bytes':image.stat().st_size, 'sha256':sha(image),
              'gpt':'passed', 'e2fsck':'passed', 'boot_files':record,
              'build_framework':'official Armbian compile.sh', 'hardware_boot':'not tested'}
    image.with_suffix('.atlasa1.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    for name in ('partition','verify'):
        command_parser=commands.add_parser(name);command_parser.add_argument('--image',type=Path,required=True)
    command_parser=commands.add_parser('boot');command_parser.add_argument('--device',type=Path,required=True);command_parser.add_argument('--bundle',type=Path,required=True)
    command_parser=commands.add_parser('boot-files');command_parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='partition':partition(args.image)
    elif args.action=='boot':write_boot(args.device,args.bundle)
    elif args.action=='boot-files':boot_files(args.root.resolve(strict=True))
    else:verify(args.image)
