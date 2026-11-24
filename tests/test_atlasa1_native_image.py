"""Check boot layout compatibility and reject corrupt boot payloads."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import atlasa1_native_image as native
from pack_armbian_raw_v6 import gpt


class NativeImageTests(unittest.TestCase):
    def test_proven_layout(self):
        self.assertEqual(native.tables(), gpt())

    def test_payload_crc(self):
        data = bytearray(512)
        struct.pack_into('<IIII', data, 0, 0x36333754, 0x314c5053, 1, 3)
        hashes = []
        for i, address in enumerate((0x47000000, 0x48000000, 0x52000000)):
            blob = bytes([i+1])*512
            struct.pack_into('<IIII', data, 32+16*i, 24576+len(data)//512,
                             address, len(blob), zlib.crc32(blob))
            data.extend(blob)
            hashes.append(hashlib.sha256(blob).hexdigest())
        struct.pack_into('<I', data, 16, zlib.crc32(data[:512]))
        self.assertEqual(native.parse_package(data), hashes)
        data[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'payload CRC'):
            native.parse_package(data)

    def test_reject_wrong_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'short.img'
            path.write_bytes(bytes(512))
            with self.assertRaisesRegex(ValueError, '8 GiB'):
                native.partition(path)
            self.assertEqual(path.read_bytes(), bytes(512))

    def test_boot_aliases_use_actual_kernel(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = '6.18.63-current-atlasa1'
            (root/'usr/lib/modules'/release).mkdir(parents=True)
            (root/'boot').mkdir()
            data = bytearray(bytes(range(256))*4)
            data[56:60] = b'ARM\x64'
            (root/'boot'/('vmlinuz-'+release)).write_bytes(data)
            (root/'boot'/('initrd.img-'+release)).write_bytes(b'initrd')
            dtb = root/'usr/lib'/('linux-image-'+release)/'allwinner/t736-pcie-v32.dtb'
            dtb.parent.mkdir(parents=True)
            dtb.write_bytes(b'dtb')
            bundle = root/'usr/lib/linux-u-boot-atlasa1-current'
            bundle.mkdir()
            (bundle/'atlasa1-spl.bin').write_bytes(b'spl')
            (bundle/'atlasa1-package.bin').write_bytes(b'package')
            (bundle/'atlasa1-boot.json').write_text(json.dumps({
                'spl_sha256': hashlib.sha256(b'spl').hexdigest(),
                'boot_package_sha256': hashlib.sha256(b'package').hexdigest()}))
            native.boot_files(root)
            alias = root/'boot/vmlinuz-6.18.63-t736-armbian'
            self.assertTrue(alias.is_symlink())
            self.assertEqual(gzip.decompress(alias.read_bytes()), data)
            self.assertEqual((root/'boot/dtb/allwinner/t736-mainline-bringup.dtb').read_bytes(), b'dtb')


if __name__ == '__main__':
    unittest.main()
