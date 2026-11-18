#!/usr/bin/env bash
set -euo pipefail

# Armbian calls this hook with SDCARD pointing at the staged rootfs. The
# Python entry point exports a verified private vendor tree; no binary is
# fetched implicitly.
: "${SDCARD:?Armbian did not set SDCARD}"
: "${T736_VENDOR_ROOT:?run build_t736_armbian_image.py so the verified vendor tree is available}"
: "${T736_VENDOR_MANIFEST:?missing vendor manifest}"
: "${T736_PROJECT_ROOT:?missing T736 project root}"

root="${SDCARD}"
vendor="${T736_VENDOR_ROOT}"
manifest="${T736_VENDOR_MANIFEST}"
install -d "${root}/etc/t736" "${root}/usr/share/doc/t736"
install -m 0644 "${manifest}" "${root}/etc/t736/vendor-manifest.json"

# Install only manifest entries. The manifest is checked by the host-side
# entry point and checked again here so an edited staging tree cannot silently
# receive a different binary.
python3 - "${root}" "${vendor}" "${manifest}" <<'PY'
import hashlib, json, os, pathlib, shutil, sys
root, vendor, manifest_path = map(pathlib.Path, sys.argv[1:])
data = json.loads(manifest_path.read_text())
if data.get("schema") != 1 or data.get("board") != "t736-mainline":
    raise SystemExit("invalid T736 vendor manifest")
required = {
    "gpu_userspace", "pvr_module", "codec_backend", "codec_service",
    "codec_userspace", "codec_config", "browser_bridge",
    "browser_service", "device_rules", "ddr_boot",
}
roles = {item.get("role") for item in data.get("files", [])}
missing = sorted(required - roles)
if missing:
    raise SystemExit("incomplete T736 media vendor manifest; missing roles: " + ", ".join(missing))
role_targets = {}
for item in data.get("files", []):
    source = pathlib.PurePosixPath(item["source"])
    target = pathlib.PurePosixPath(item["target"])
    if source.is_absolute() or ".." in source.parts or not target.is_absolute() or ".." in target.parts:
        raise SystemExit(f"unsafe vendor path: {source} -> {target}")
    src = vendor / pathlib.Path(*source.parts)
    if not src.is_file():
        raise SystemExit(f"vendor file missing: {src}")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if item.get("sha256", "").lower() != digest:
        raise SystemExit(f"vendor hash mismatch: {source}")
    dst = root / pathlib.Path(*target.parts[1:])
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if item.get("mode"):
        os.chmod(dst, int(item["mode"], 8))
    role_targets.setdefault(item.get("role"), []).append(str(target))
(root / "etc/t736/vendor-roles.json").write_text(
    json.dumps(role_targets, indent=2, sort_keys=True) + "\n")
PY

deb_dir="${root}/tmp/t736-vendor"
if compgen -G "${deb_dir}/*.deb" >/dev/null 2>&1; then
    chroot "${root}" dpkg --unpack /tmp/t736-vendor/*.deb
    chroot "${root}" dpkg --configure -a
fi

if [ "${T736_INSTALL_DESKTOP:-yes}" = yes ]; then
    chroot "${root}" apt-get update
    mapfile -t packages < "${T736_PROJECT_ROOT}/config/desktop-v7-packages.txt"
    chroot "${root}" apt-get install -y --no-install-recommends "${packages[@]}"
fi

# Requested lab default. Override privately with T736_ROOT_PASSWORD.
if [ "${T736_SET_ROOT_PASSWORD:-yes}" = yes ]; then
    password="${T736_ROOT_PASSWORD:-1234}"
    [ -n "${password}" ] || { echo "empty root password refused" >&2; exit 1; }
    printf 'root:%s\n' "${password}" | chroot "${root}" chpasswd
fi

install -d "${root}/etc/modprobe.d" "${root}/etc/udev/rules.d"
cat > "${root}/etc/modprobe.d/t736-media.conf" <<'EOF'
# T736 vendor PVR/VE modules are loaded by their package/service.
EOF
# The verified vendor device rule is authoritative. Do not add a later broad
# video-group rule: it would override the dedicated-service 0600 rule.

if ! chroot "${root}" getent group t736-cedar >/dev/null 2>&1; then
    chroot "${root}" groupadd --system t736-cedar
fi
if ! chroot "${root}" getent group t736 >/dev/null 2>&1; then
    chroot "${root}" groupadd --system t736
fi
# The desktop account must be able to connect to the root-owned socket unit.
# Keep raw Cedar devices private to t736-cedar; this group is only for the
# AF_UNIX endpoint and never receives udev access to /dev/cedar_dev.
if chroot "${root}" getent passwd t736 >/dev/null 2>&1; then
    chroot "${root}" usermod --append --groups t736 t736
fi
if ! chroot "${root}" getent passwd t736-cedar >/dev/null 2>&1; then
    chroot "${root}" useradd --system --gid t736-cedar --groups t736 \
        --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin t736-cedar
fi
# The systemd socket is root-owned and group-readable. Add the board's
# desktop account to the dedicated access group when that account exists.
if chroot "${root}" getent passwd t736 >/dev/null 2>&1; then
    chroot "${root}" usermod --append --groups t736 t736
fi

if [ -f "${root}/etc/systemd/system/t736-cedar-broker.service" ]; then
    chroot "${root}" systemctl enable t736-cedar-broker.service || true
fi
# Enable only service units explicitly supplied by the verified manifest.
python3 - "${root}" <<'PY'
import json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
roles = json.loads((root / "etc/t736/vendor-roles.json").read_text())
for role in ("codec_service", "browser_service"):
    for target in roles.get(role, []):
        if target.startswith("/etc/systemd/system/") and target.endswith(".service"):
            subprocess.run(["chroot", str(root), "systemctl", "enable",
                            pathlib.PurePosixPath(target).name], check=False)
PY
if [ -d "${root}/lib/modules" ]; then
    chroot "${root}" depmod -a || true
fi

install -d "${root}/usr/share/xsessions" "${root}/usr/local/bin" "${root}/usr/local/sbin"
# Keep the explicit headless media acceptance entry point in complete images.
# It reports pending when fixtures, OMX elements, or encoder/zero-copy proof are absent.
install -m 0755 "${T736_PROJECT_ROOT}/tools/validation/media_acceptance.py" \
    "${root}/usr/local/sbin/t736-media-acceptance.py"
install -m 0644 "${T736_PROJECT_ROOT}/config/gpu-userspace-gnome.desktop" \
    "${root}/usr/share/xsessions/t736-img.desktop"
install -m 0644 "${T736_PROJECT_ROOT}/config/gpu-userspace-x11.env" \
    "${root}/etc/t736/gpu-userspace-x11.env"
install -m 0755 "${T736_PROJECT_ROOT}/config/gpu-userspace-run.sh" \
    "${root}/usr/local/bin/t736-img-run"

cat > "${root}/etc/t736/build-info" <<EOF
board=t736-mainline
vendor_manifest_sha256=$(sha256sum "${manifest}" | awk '{print $1}')
gpu_media_acceptance=pending
EOF
