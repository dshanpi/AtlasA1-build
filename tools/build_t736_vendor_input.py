#!/usr/bin/env python3
"""Assemble a private, hash-locked T736 vendor input tree.

The public Armbian patch contains only source code.  This helper combines the
licensed GPU/Cedar/FFmpeg artifacts that are already available to the builder
into the private input format consumed by ``build_t736_armbian_image.py``.
It never downloads binaries and it never changes the public source tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import Iterable

from write_t736_image_boot import load_boot_files


PROJECT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_lf(path: Path, text: str) -> None:
    """Write shell/systemd/udev payloads with Linux LF line endings on Windows."""
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def require_file(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"{label} does not exist or is not a file: {path}")
    return path


def require_module_release(path: Path, kernel_release: str) -> None:
    """Reject a PVR module whose vermagic cannot load into this kernel."""
    payload = path.read_bytes()
    marker = b"vermagic="
    start = payload.find(marker)
    if start < 0:
        raise SystemExit(f"{path} has no vermagic string; provide an uncompressed module")
    value = payload[start + len(marker):].split(b"\0", 1)[0].decode("ascii", "replace")
    if not value.startswith(kernel_release + " "):
        raise SystemExit(
            f"PVR module vermagic {value!r} does not match --kernel-release {kernel_release!r}"
        )


def safe_member(name: str) -> PurePosixPath:
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts:
        raise SystemExit(f"unsafe archive member: {name}")
    return member


def archive_prefix(archive: Path, expected_name: str | None = None) -> str:
    with tarfile.open(archive, "r:*") as stream:
        tops = {safe_member(info.name).parts[0] for info in stream.getmembers()
                if safe_member(info.name).parts}
    if len(tops) != 1:
        raise SystemExit(f"archive must have one top-level directory: {archive}")
    prefix = next(iter(tops))
    if expected_name and prefix != expected_name:
        raise SystemExit(f"unexpected archive prefix {prefix!r}, expected {expected_name!r}")
    return prefix


def extract_runtime(archive: Path, root: Path, prefix: str,
                    allowed: set[str] | None = None) -> list[tuple[Path, PurePosixPath]]:
    """Extract regular runtime files and return (payload, relative path)."""
    files: list[tuple[Path, PurePosixPath]] = []
    with tarfile.open(archive, "r:*") as stream:
        for info in stream.getmembers():
            rel = safe_member(info.name)
            if not info.isfile():
                continue
            if not rel.parts or rel.parts[0] != prefix:
                continue
            if allowed is not None and str(rel) not in allowed:
                continue
            destination = root.joinpath(*rel.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = stream.extractfile(info)
            if source is None:
                raise SystemExit(f"cannot read archive member: {info.name}")
            with destination.open("wb") as output:
                shutil.copyfileobj(source, output)
            os.chmod(destination, 0o755 if "/bin/" in f"/{rel}/" else 0o644)
            files.append((destination, rel))
    if not files:
        raise SystemExit(f"no runtime files found in {archive} under {prefix}/")
    return files


def copy_payload(source: Path, root: Path, relative: str, mode: int | None = None) -> Path:
    destination = root.joinpath(*safe_member(relative).parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if mode is not None:
        os.chmod(destination, mode)
    return destination


def entry(payload: Path, target: str, role: str, kind: str = "file",
          mode: str | None = None, source: str | None = None) -> dict:
    target_path = PurePosixPath(target)
    if not target_path.is_absolute() or ".." in target_path.parts:
        raise SystemExit(f"unsafe rootfs target: {target}")
    item = {
        "source": source if source is not None else payload.name,
        "target": target_path.as_posix(),
        "kind": kind,
        "role": role,
        "sha256": sha256(payload),
    }
    if mode:
        item["mode"] = mode
    return item


def add_archive_entries(manifest: list[dict], files: Iterable[tuple[Path, PurePosixPath]],
                        root_prefix: str, target_prefix: str, role: str) -> None:
    source_prefix = PurePosixPath(root_prefix)
    for payload, relative in files:
        suffix = relative.relative_to(source_prefix)
        target = PurePosixPath(target_prefix, *suffix.parts)
        mode = "0755" if "/bin/" in f"/{relative}/" else "0644"
        manifest.append(entry(payload, target.as_posix(), role, mode=mode,
                              source=relative.as_posix()))


def make_launcher(path: Path) -> None:
    write_lf(path,
        """#!/bin/sh
set -eu
profile=${T736_CEDAR_PROFILE:-${HOME}/.mozilla/t736-cedar-candidate}
mkdir -p "$profile"
if [ ! -s "$profile/user.js" ] || ! grep -q 'dom.ipc.forkserver.enable' "$profile/user.js"; then
    printf '%s\\n' 'user_pref("dom.ipc.forkserver.enable", false);' >> "$profile/user.js"
fi
export T736_CEDAR_ENABLE=1
export LD_LIBRARY_PATH=/opt/t736-browser-ffmpeg-v7/lib:/opt/t736-cedar-transport-v2/lib:/opt/t736-cedar-browser-backend-v5:/opt/t736-cedar-wc-v5/lib:/opt/t736-img-ddk-24.2-x11/runtime-gles${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export LIBGL_DRIVERS_PATH=${LIBGL_DRIVERS_PATH:-/opt/t736-img-ddk-24.2-x11/lib/dri}
export MOZ_X11_EGL=1
export LD_PRELOAD=/opt/t736-cedar-transport-v2/lib/libt736_cedar_client.so:/opt/t736-browser-ffmpeg-v7/lib/libavutil.so.59:/opt/t736-browser-ffmpeg-v7/lib/libavcodec.so.61${LD_PRELOAD:+:$LD_PRELOAD}
unset T736_CEDAR_TEST_CLIENT
exec /usr/lib/firefox-esr/firefox-esr --no-remote --profile "$profile" "$@"
""",
    )
    os.chmod(path, 0o755)


def make_service(path: Path) -> None:
    write_lf(path,
        """[Unit]
Description=T736 Cedar hardware decoder broker
After=local-fs.target systemd-udev-settle.service t736-cedar.socket
Requires=t736-cedar.socket
ConditionPathExists=/dev/cedar_dev

[Service]
Type=simple
User=t736-cedar
Group=t736
UMask=0007
ExecStart=/opt/t736-cedar-transport-v2/bin/cedar-service
Restart=on-failure
RestartSec=1
TimeoutStopSec=15
KillMode=control-group
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateNetwork=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX
DevicePolicy=closed
DeviceAllow=/dev/cedar_dev rw
DeviceAllow=/dev/dma_heap/t736-ve rw
MemoryMax=512M
TasksMax=64
BindReadOnlyPaths=/opt/t736-cedar-transport-v2/config/cedarc.conf:/etc/cedarc.conf

[Install]
WantedBy=multi-user.target
""",
    )


def make_cedar_service(path: Path) -> None:
    write_lf(path,
        """#!/bin/sh
set -eu
root=/opt/t736-cedar-transport-v2
for device in /dev/cedar_dev /dev/dma_heap/t736-ve; do
    if [ ! -c "$device" ] || [ ! -r "$device" ] || [ ! -w "$device" ]; then
        printf 'CEDAR_SERVICE: dedicated decoder device unavailable: %s\\n' "$device" >&2
        exit 1
    fi
done
# Keep the tested private parser stack ahead of the distro plugins when it is
# installed, while still allowing a minimal image that only has the distro
# GStreamer parser package.  The selected directory is optional by design.
parser_root=/opt/t736-gst-parser-v27
if [ -d "$parser_root/selected" ]; then
    export GST_PLUGIN_SYSTEM_PATH_1_0="$parser_root/selected:/usr/lib/aarch64-linux-gnu/gstreamer-1.0"
else
    export GST_PLUGIN_SYSTEM_PATH_1_0=/usr/lib/aarch64-linux-gnu/gstreamer-1.0
fi
old_ld=${LD_LIBRARY_PATH:-}
export LD_LIBRARY_PATH=/opt/t736-cedar-browser-backend-v5:/opt/t736-cedar-wc-v5/lib
if [ -d "$parser_root/usr/lib/aarch64-linux-gnu" ]; then
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$parser_root/usr/lib/aarch64-linux-gnu"
fi
if [ -n "$old_ld" ]; then
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$old_ld"
fi
export GST_PLUGIN_PATH_1_0=/opt/t736-cedar-wc-v5/lib/gstreamer-1.0
export GST_OMX_CONFIG_DIR="$root/config"
export GST_REGISTRY_1_0=/run/t736-cedar/registry.bin
export GST_REGISTRY_FORK=no
unset GST_AW_OMX_DEFAULT_ARM_AFBC AW_AFBC_MODE
allowed_uid=$(id -u t736 2>/dev/null || true)
case "$allowed_uid" in
    ''|*[!0-9]*|0) printf 'CEDAR_SERVICE: desktop account t736 is unavailable\\n' >&2; exit 1 ;;
esac
exec "$root/bin/cedar-broker" "$allowed_uid"
""",
    )
    os.chmod(path, 0o755)


def make_socket(path: Path) -> None:
    write_lf(path,
        """[Unit]
Description=T736 Cedar decoder socket
Before=t736-cedar.service

[Socket]
ListenStream=/run/t736-cedar/decoder.sock
Service=t736-cedar.service
DirectoryMode=0755
SocketUser=root
SocketGroup=t736
SocketMode=0660
RemoveOnStop=true

[Install]
WantedBy=sockets.target
""",
    )


def make_rules(path: Path) -> None:
    write_lf(path,
        """# Keep raw Cedar devices private to the broker service.
SUBSYSTEM=="misc", KERNEL=="cedar_dev", OWNER="t736-cedar", GROUP="t736-cedar", MODE="0600"
SUBSYSTEM=="dma_heap", KERNEL=="t736-ve", OWNER="t736-cedar", GROUP="t736-cedar", MODE="0600"
""",
    )


def make_profile(path: Path) -> None:
    write_lf(path,
        """# T736 candidate browser launcher. Use t736-firefox-cedar explicitly.
export T736_CEDAR_BROWSER=/usr/local/bin/t736-firefox-cedar
""",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="private vendor directory to create")
    parser.add_argument("--archive", type=Path,
                        help="optional .tar.gz archive made from the directory")
    parser.add_argument("--gpu-deb", type=Path, required=True)
    parser.add_argument("--pvr-module", type=Path, required=True)
    parser.add_argument("--wc-archive", type=Path, required=True)
    parser.add_argument("--transport-archive", type=Path, required=True)
    parser.add_argument("--backend-archive", type=Path, required=True)
    parser.add_argument("--ffmpeg-archive", type=Path, required=True)
    parser.add_argument("--ddr-boot", type=Path, required=True, help="fixed v4 eGON LPDDR4x SPL")
    parser.add_argument("--boot-package", type=Path, required=True, help="matching stage64/TF-A/U-Boot package")
    parser.add_argument("--kernel-release", default="6.18.63-t736-armbian")
    args = parser.parse_args()

    for name in ("gpu_deb", "pvr_module", "wc_archive", "transport_archive",
                 "backend_archive", "ffmpeg_archive", "ddr_boot", "boot_package"):
        setattr(args, name, require_file(getattr(args, name), f"--{name.replace('_', '-')}") )
    require_module_release(args.pvr_module, args.kernel_release)
    try:
        load_boot_files(args.ddr_boot, args.boot_package)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    root = args.output.expanduser().resolve()
    root.mkdir(parents=True)
    manifest: list[dict] = []

    gpu = copy_payload(args.gpu_deb, root, "gpu/t736-img-userspace.deb")
    manifest.append(entry(gpu, "/tmp/t736-vendor/gpu-userspace.deb", "gpu_userspace", "deb",
                          source="gpu/t736-img-userspace.deb"))
    pvr = copy_payload(args.pvr_module, root, "gpu/pvrsrvkm.ko")
    manifest.append(entry(pvr, f"/lib/modules/{args.kernel_release}/extra/pvrsrvkm.ko", "pvr_module",
                          mode="0644", source="gpu/pvrsrvkm.ko"))
    ddr = copy_payload(args.ddr_boot, root, "boot/t736-ddr-spl.bin")
    manifest.append(entry(ddr, "/usr/lib/u-boot/t736-ddr-spl.bin", "ddr_boot", "boot", "0644",
                          source="boot/t736-ddr-spl.bin"))
    boot_package = copy_payload(args.boot_package, root, "boot/t736-source-package.bin")
    manifest.append(entry(boot_package, "/usr/lib/u-boot/t736-source-package.bin", "boot_package", "boot",
                          "0644", source="boot/t736-source-package.bin"))

    wc = extract_runtime(args.wc_archive, root, "t736-cedar-wc-v5")
    add_archive_entries(manifest, wc, "t736-cedar-wc-v5", "/opt/t736-cedar-wc-v5", "codec_userspace")
    transport_allowed = {"t736-cedar-transport-v2/bin/cedar-broker",
                         "t736-cedar-transport-v2/lib/libt736_cedar_client.so"}
    transport = extract_runtime(args.transport_archive, root, "t736-cedar-transport-v2", transport_allowed)
    add_archive_entries(manifest, transport, "t736-cedar-transport-v2", "/opt/t736-cedar-transport-v2", "codec_userspace")
    backend = extract_runtime(args.backend_archive, root, "t736-cedar-browser-backend-v5")
    add_archive_entries(manifest, backend, "t736-cedar-browser-backend-v5", "/opt/t736-cedar-browser-backend-v5", "codec_backend")
    ffmpeg_prefix = archive_prefix(args.ffmpeg_archive)
    ffmpeg = extract_runtime(args.ffmpeg_archive, root, ffmpeg_prefix)
    add_archive_entries(manifest, ffmpeg, ffmpeg_prefix, "/opt/t736-browser-ffmpeg-v7", "codec_userspace")

    # The browser service consumes these two files from its own prefix.
    gst_config = copy_payload(PROJECT / "tools/browser/gstomx.conf", root, "media/gstomx.conf")
    cedarc_config = copy_payload(PROJECT / "tools/browser/cedarc.conf", root, "media/cedarc.conf")
    manifest.append(entry(gst_config, "/opt/t736-cedar-transport-v2/config/gstomx.conf", "codec_config",
                          mode="0644", source="media/gstomx.conf"))
    manifest.append(entry(cedarc_config, "/opt/t736-cedar-transport-v2/config/cedarc.conf", "codec_config",
                          mode="0644", source="media/cedarc.conf"))

    launcher = root / "browser" / "t736-firefox-cedar"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    make_launcher(launcher)
    manifest.append(entry(launcher, "/usr/local/bin/t736-firefox-cedar", "browser_bridge", mode="0755",
                          source="browser/t736-firefox-cedar"))
    browser_profile = root / "browser" / "t736-cedar-browser.sh"
    make_profile(browser_profile)
    manifest.append(entry(browser_profile, "/etc/profile.d/t736-cedar-browser.sh", "browser_service", mode="0644",
                          source="browser/t736-cedar-browser.sh"))

    service = root / "media" / "t736-cedar.service"
    service.parent.mkdir(parents=True, exist_ok=True)
    make_service(service)
    manifest.append(entry(service, "/etc/systemd/system/t736-cedar.service", "codec_service", mode="0644",
                          source="media/t736-cedar.service"))
    socket = root / "media" / "t736-cedar.socket"
    make_socket(socket)
    manifest.append(entry(socket, "/etc/systemd/system/t736-cedar.socket", "codec_service", mode="0644",
                          source="media/t736-cedar.socket"))
    cedar_service = root / "media" / "cedar-service"
    make_cedar_service(cedar_service)
    manifest.append(entry(cedar_service, "/opt/t736-cedar-transport-v2/bin/cedar-service", "codec_service",
                          mode="0755", source="media/cedar-service"))
    rules = root / "media" / "70-t736-cedar.rules"
    make_rules(rules)
    manifest.append(entry(rules, "/etc/udev/rules.d/70-t736-cedar.rules", "device_rules", mode="0644",
                          source="media/70-t736-cedar.rules"))

    data = {
        "schema": 1,
        "board": "t736-mainline",
        "description": "Private licensed T736 GPU/Cedar/FFmpeg runtime assembled locally.",
        "kernel_release": args.kernel_release,
        "archive_layout": "manifest.json plus payload files at files[].source",
        "private": True,
        "files": manifest,
        "acceptance": "pending",
        "notes": [
            "This tree contains vendor binaries and must not be committed to the public source repository.",
            "Plugin loading and native replay are not browser, 4K, encoder, zero-copy, or long-run acceptance.",
            "The board must be tested with the matching kernel, device rules and hardware after image creation.",
        ],
    }
    (root / "manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    readme = root / "README.txt"
    readme.write_text(
        "T736 private vendor input\n\n"
        "Built by tools/build_t736_vendor_input.py. Keep this directory private.\n"
        "The manifest is hash-locked and accepted by build_t736_armbian_image.py.\n"
        "Hardware acceptance remains pending until real-board decode/encode tests pass.\n",
        encoding="utf-8",
    )
    if args.archive:
        archive = args.archive.expanduser().resolve()
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:gz") as stream:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    stream.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
    print(json.dumps({"output": str(root), "archive": str(args.archive.resolve()) if args.archive else None,
                      "files": len(manifest), "roles": sorted({item["role"] for item in manifest})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
