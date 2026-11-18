#!/usr/bin/env python3
"""Pack the media-v28 boot-command candidate without touching board media.

The package replaces only the third (U-Boot) payload in the already deployed
CPU-D source boot package. SPL, TF-A, payload addresses, LBAs and padding are
checked byte-for-byte before a new package and manifest are written.
"""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

BASE_LBA = 24576
LIMIT_LBA = 32800
BASELINE_SHA = "f2ea2157acc3b65b2cc7416dfdba39650e7daa6679693c558fbbdcc30ef9780a"
SPL_V4_SHA = "a1d821eaee602fdf8b481c38cf4790d0f8a6f31539dd9fc6c1a714c1e92bd0ea"
PINNED = [
    (24577, 0x47000000, 5040, "44aeb8e56f64f2ccd80a1cd286460eda6d0232f9cc1e82618866826b23298535"),
    (24587, 0x48000000, 53924, "81f53c1d1f571c74bd907317d813a5ed56c64382479caa75edd3cec43ada6dc6"),
    (24693, 0x52000000, 265256, "3ee3a5710c5c13c9ab11b274c6b076447ab346fc7622a1d64b5aaa692f877cdf"),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse(data):
    if len(data) < 512 or len(data) % 512:
        raise ValueError("package must be 512-byte aligned")
    header = bytearray(data[:512])
    words = struct.unpack("<128I", header)
    if words[:4] != (0x36333754, 0x314C5053, 1, 3):
        raise ValueError("unexpected source package header")
    struct.pack_into("<I", header, 16, 0)
    if zlib.crc32(header) != words[4]:
        raise ValueError("header CRC mismatch")
    entries = []
    previous = BASE_LBA + 1
    for i, maximum in enumerate((8192, 0x200000, 0x100000)):
        sector, address, length, crc = words[8 + i * 4:12 + i * 4]
        if address != PINNED[i][1] or not 0 < length <= maximum:
            raise ValueError("image address/size violates contract")
        count = (length + 511) // 512
        if sector != previous or sector + count >= LIMIT_LBA:
            raise ValueError("image sector bounds violate contract")
        offset = (sector - BASE_LBA) * 512
        if offset + count * 512 > len(data):
            raise ValueError("truncated image")
        image = data[offset:offset + length]
        if zlib.crc32(image) != crc or any(data[offset + length:offset + count * 512]):
            raise ValueError("image CRC/padding mismatch")
        entries.append({"sector": sector, "address": hex(address), "bytes": length,
                        "crc32": f"{crc:08x}", "sha256": sha(image), "offset": offset})
        previous = sector + count
    if len(data) != (previous - BASE_LBA) * 512:
        raise ValueError("unexpected trailing bytes")
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--uboot", type=Path, required=True)
    ap.add_argument("--build-record", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    manifest_path = args.output.with_suffix(".manifest.json")
    if args.output.exists() or manifest_path.exists():
        raise ValueError("candidate or manifest already exists")
    baseline = args.baseline.read_bytes()
    if sha(baseline) != BASELINE_SHA:
        raise ValueError("baseline package differs from fixed CPU-D package")
    old = parse(baseline)
    for entry, expected in zip(old, PINNED):
        if (entry["sector"], int(entry["address"], 16), entry["bytes"], entry["sha256"]) != expected:
            raise ValueError("baseline component differs from pinned CPU-D chain")
    uboot = args.uboot.read_bytes()
    record_data = args.build_record.read_bytes()
    record = json.loads(record_data)
    if record.get("variant") != "media-v28-bootcmd" or record.get("payload_sha256") != sha(uboot):
        raise ValueError("U-Boot does not match media-v28 build record")
    if record.get("payload_size") != len(uboot) or not 0 < len(uboot) <= 0x100000:
        raise ValueError("invalid U-Boot payload size")
    offset = old[2]["offset"]
    package = bytearray(baseline[:offset])
    package.extend(uboot)
    package.extend(bytes((-len(uboot)) % 512))
    struct.pack_into("<II", package, (8 + 2 * 4 + 2) * 4, len(uboot), zlib.crc32(uboot))
    struct.pack_into("<I", package, 16, 0)
    struct.pack_into("<I", package, 16, zlib.crc32(package[:512]))
    new = parse(package)
    if package[512:offset] != baseline[512:offset] or new[:2] != old[:2]:
        raise ValueError("non-U-Boot payload changed")
    allowed = set(range(16, 20)) | set(range(72, 80))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(baseline[:512], package[:512]))):
        raise ValueError("header changed outside length/CRC fields")
    manifest = {
        "variant": "media-v28-boot-package", "hardware_tested": False,
        "path": args.output.name, "bytes": len(package), "sha256": sha(package),
        "sector_bytes": 512, "start_lba": BASE_LBA, "sector_count": len(package) // 512,
        "end_lba_exclusive": BASE_LBA + len(package) // 512, "required_end_below_lba": LIMIT_LBA,
        "baseline": {"path": args.baseline.name, "bytes": len(baseline), "sha256": BASELINE_SHA},
        "build_record": {"path": str(args.build_record), "sha256": sha(record_data)},
        "images": new,
        "changes": ["third payload U-Boot", "third payload length and CRC", "header CRC"],
        "unchanged": ["stage64 bytes and padding", "TF-A bytes and padding", "all payload LBAs and load addresses"],
        "required_existing_spl": {"variant": "v4", "sha256": SPL_V4_SHA, "modified": False},
        "scope": "Candidate only; no storage writes performed. Media-v28 aliases/DTB must be staged separately.",
        "acceptance": "Back up/read back the current bounded boot range before any write; then cold-boot verify v28, HS400 200MHz, GPU and recovery path.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(package)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    if sha(args.output.read_bytes()) != manifest["sha256"]:
        raise IOError("candidate verification failed")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
