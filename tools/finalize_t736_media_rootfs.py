#!/usr/bin/env python3
"""Index the installed target PVR module and enable manifest-supplied media units."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


def finalize(root: Path) -> None:
    root = root.resolve(strict=True)
    manifest = json.loads((root / "etc/t736/vendor-manifest.json").read_text())
    modules = [item for item in manifest["files"] if item["role"] == "pvr_module"]
    if len(modules) != 1:
        raise SystemExit("expected one PVR module in the T736 vendor manifest")
    module = modules[0]
    match = re.fullmatch(r"/(?:usr/)?lib/modules/([0-9][A-Za-z0-9._+-]*)/extra/pvrsrvkm\.ko", module["target"])
    if not match or manifest.get("kernel_release", match[1]) != match[1]:
        raise SystemExit("PVR target does not match the manifest kernel release")
    release = match[1]
    installed = root / module["target"].lstrip("/")
    if hashlib.sha256(installed.read_bytes()).hexdigest() != module["sha256"].lower():
        raise SystemExit("installed PVR module differs from the manifest")
    # The .ko alone can create a plausible directory for an uninstalled kernel.
    if not (root / "lib/modules" / release / "modules.builtin").is_file():
        raise SystemExit(f"kernel module tree for {release} is missing modules.builtin")
    subprocess.run(["depmod", "-b", root, "-a", release], check=True)
    info = ["modinfo", "-b", root, "-k", release]
    indexed = subprocess.check_output([*info, "-n", "pvrsrvkm"], text=True).strip()
    vermagic = subprocess.check_output([*info, "-F", "vermagic", "pvrsrvkm"], text=True).split()
    if not installed.samefile(indexed) or vermagic[:1] != [release]:
        raise SystemExit(f"modinfo did not resolve the installed pvrsrvkm for {release}")

    units = set()
    for item in manifest["files"]:
        path = PurePosixPath(item["target"])
        if (item["role"] in {"codec_service", "browser_service"} and
                path.parent == PurePosixPath("/etc/systemd/system") and path.suffix in {".service", ".socket"}):
            units.add(path.name)
    systemctl = ["systemctl", "--root", root]
    for unit in sorted(units):
        if unit.endswith(".service") and unit.removesuffix(".service") + ".socket" in units:
            # Clear a boot-time enablement left by an earlier image.
            subprocess.run([*systemctl, "disable", unit], check=True)
        else:
            subprocess.run([*systemctl, "enable", unit], check=True)
            subprocess.run([*systemctl, "is-enabled", "--quiet", unit], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    finalize(parser.parse_args().root)
