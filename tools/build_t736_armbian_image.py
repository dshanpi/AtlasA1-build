#!/usr/bin/env python3
"""Prepare and optionally run a reproducible T736 Armbian build.

Only reviewed board, kernel and U-Boot inputs are copied into an official
Armbian checkout. GPU/media functionality requires a separately supplied,
hash-locked vendor tree; it is never silently omitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import shlex
import subprocess
import time

PROJECT = Path(__file__).resolve().parents[1]
LOCK = PROJECT / "config" / "sources.lock.json"
BOARD_TEMPLATE = PROJECT / "userpatches" / "config" / "boards" / "t736-mainline.wip"
FAMILY_TEMPLATE = PROJECT / "userpatches" / "config" / "sources" / "families" / "t736-mainline.conf"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def fail(message: str) -> None:
    raise SystemExit(f"t736 build: {message}")


def validate_armbian(path: Path) -> str:
    if not (path / "compile.sh").is_file() or not (path / "config" / "boards").is_dir():
        fail(f"{path} is not an Armbian build checkout")
    try:
        return run("git", "rev-parse", "HEAD", cwd=path).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unversioned"


def expected_commit() -> str:
    data = json.loads(LOCK.read_text())
    return next(item["commit"] for item in data["components"] if item["name"] == "armbian-build")


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def stage_userpatches(armbian: Path) -> dict[str, str]:
    up = armbian / "userpatches"
    (up / "config" / "boards").mkdir(parents=True, exist_ok=True)
    (up / "config" / "sources" / "families").mkdir(parents=True, exist_ok=True)
    (up / "kernel").mkdir(exist_ok=True)
    (up / "u-boot").mkdir(exist_ok=True)
    shutil.copy2(BOARD_TEMPLATE, up / "config" / "boards" / "t736-mainline.conf")
    shutil.copy2(FAMILY_TEMPLATE, up / "config" / "sources" / "families" / "t736-mainline.conf")
    copy_tree(PROJECT / "userpatches" / "kernel" / "t736-mainline-6.18", up / "kernel" / "t736-mainline-6.18")
    copy_tree(PROJECT / "userpatches" / "u-boot" / "u-boot-t736-mainline", up / "u-boot" / "u-boot-t736-mainline")
    config = up / "config" / "linux-t736-mainline-current.config"
    shutil.copy2(PROJECT / "userpatches" / "linux-t736-mainline-current.config", config)
    return {
        "board": sha256(up / "config" / "boards" / "t736-mainline.conf"),
        "family": sha256(up / "config" / "sources" / "families" / "t736-mainline.conf"),
        "kernel_config": sha256(config),
    }


def read_vendor(vendor: Path, stage: Path) -> tuple[Path, dict]:
    if not vendor.exists():
        fail(f"vendor input does not exist: {vendor}")
    if vendor.is_dir():
        root = vendor
    else:
        root = stage / "vendor"
        root.mkdir(parents=True, exist_ok=True)
        listing = subprocess.run(["tar", "--list", "--file", str(vendor)], text=True, capture_output=True, check=False)
        if listing.returncode:
            fail(f"cannot inspect vendor archive: {listing.stderr.strip()}")
        for name in listing.stdout.splitlines():
            member = Path(name)
            if member.is_absolute() or ".." in member.parts:
                fail(f"unsafe vendor archive member: {name}")
        result = subprocess.run(
            ["tar", "--extract", "--file", str(vendor), "--directory", str(root), "--no-same-owner"],
            text=True, capture_output=True,
        )
        if result.returncode:
            fail(f"cannot extract vendor archive: {result.stderr.strip()}")
    manifest = root / "manifest.json"
    if not manifest.is_file():
        fail(f"vendor input must contain {manifest}")
    data = json.loads(manifest.read_text())
    if data.get("schema") != 1 or data.get("board") != "t736-mainline" or not data.get("private"):
        fail("vendor manifest must declare schema=1, board=t736-mainline and private=true")
    # A complete media image needs both the Cedar service and the browser-side
    # bridge/runtime. Installing only a broker or a GStreamer plugin cannot
    # make Firefox use hardware decode.
    required_roles = {
        "gpu_userspace", "pvr_module", "codec_backend", "codec_service",
        "codec_userspace", "codec_config", "browser_bridge",
        "browser_service", "device_rules", "ddr_boot",
    }
    roles = {item.get("role") for item in data.get("files", [])}
    missing_roles = sorted(required_roles - roles)
    if missing_roles:
        fail("vendor manifest is not a complete image input; missing roles: " + ", ".join(missing_roles))
    for item in data.get("files", []):
        source = PurePosixPath(item["source"])
        if source.is_absolute() or ".." in source.parts:
            fail(f"unsafe vendor source path: {source}")
        target = PurePosixPath(item.get("target", ""))
        if not target.is_absolute() or ".." in target.parts:
            fail(f"unsafe vendor target path: {target}")
        payload = root.joinpath(*source.parts)
        if not payload.is_file():
            fail(f"vendor payload missing: {source}")
        actual = sha256(payload)
        if len(str(item.get("sha256", ""))) != 64 or item["sha256"].lower() != actual:
            fail(f"vendor hash mismatch: {source} ({actual})")
    return root, data


def write_customize(armbian: Path, vendor_root: Path, manifest: Path) -> None:
    up = armbian / "userpatches"
    target = up / "customize-image.sh"
    shutil.copy2(PROJECT / "tools" / "t736-customize-image.sh", target)
    target.chmod(0o755)
    (up / "t736-vendor.env").write_text(
        f"export T736_PROJECT_ROOT={shlex.quote(str(PROJECT))}\n"
        f"export T736_VENDOR_ROOT={shlex.quote(str(vendor_root))}\n"
        f"export T736_VENDOR_MANIFEST={shlex.quote(str(manifest))}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--armbian", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROJECT / "build" / "t736-armbian")
    parser.add_argument("--vendor-input", type=Path, help="private vendor tree or tar(.zst) containing manifest.json")
    parser.add_argument("--release", default="trixie")
    parser.add_argument("--branch", default="current")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--run", action="store_true", help="run Armbian compile.sh after preparation")
    args = parser.parse_args()
    if args.run and not args.vendor_input:
        fail("--run requires --vendor-input; GPU/media must not be silently omitted")
    armbian = args.armbian.resolve()
    commit = validate_armbian(armbian)
    expected = expected_commit()
    if commit not in ("unversioned", expected):
        fail(f"Armbian commit {commit} does not match pinned {expected}")
    stage = args.output.resolve()
    stage.mkdir(parents=True, exist_ok=True)
    hashes = stage_userpatches(armbian)
    vendor_root = vendor_manifest = vendor_data = None
    if args.vendor_input:
        vendor_root, vendor_data = read_vendor(args.vendor_input.resolve(), stage)
        vendor_manifest = vendor_root / "manifest.json"
        write_customize(armbian, vendor_root, vendor_manifest)
    elif not args.check_only:
        fail("a private vendor input is required for a complete image")
    record = {
        "schema": 1,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project": str(PROJECT), "armbian": str(armbian),
        "armbian_commit": commit, "armbian_commit_expected": expected,
        "release": args.release, "branch": args.branch, "jobs": args.jobs,
        "userpatches_sha256": hashes,
        "vendor_manifest_sha256": sha256(vendor_manifest) if vendor_manifest else None,
        "vendor_file_count": len(vendor_data.get("files", [])) if vendor_data else 0,
        "gpu_media_complete": bool(vendor_data), "hardware_acceptance": "pending",
        "image_output": str(armbian / "output"),
    }
    (stage / "t736-build-inputs.json").write_text(json.dumps(record, indent=2) + "\n")
    if args.check_only:
        print(json.dumps(record, indent=2))
        return 0
    env = os.environ.copy()
    env.update({"T736_PROJECT_ROOT": str(PROJECT), "T736_VENDOR_ROOT": str(vendor_root), "T736_VENDOR_MANIFEST": str(vendor_manifest)})
    command = ["./compile.sh", "BOARD=t736-mainline", f"BRANCH={args.branch}", f"RELEASE={args.release}",
               "BUILD_DESKTOP=yes", "DESKTOP_APPGROUPS_SELECTED=gnome", "EXPERT=yes",
               "BUILD_MINIMAL=no", "SHARE_LOG=no", f"JOBS={args.jobs}"]
    print("running:", " ".join(command))
    subprocess.run(command, cwd=armbian, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
