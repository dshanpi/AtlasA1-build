#!/usr/bin/env python3
"""Export the open-source T736 Armbian integration as one unified patch.

The resulting patch adds only Armbian userpatches: board/family metadata,
Linux/U-Boot source patches, and the kernel configuration. It deliberately
does not embed licensed GPU/codec/DDR binaries or the private vendor hook.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    (ROOT / "userpatches/config/boards/t736-mainline.conf", "userpatches/config/boards/t736-mainline.conf"),
    (ROOT / "userpatches/config/sources/families/t736-mainline.conf", "userpatches/config/sources/families/t736-mainline.conf"),
    (ROOT / "userpatches/t736-media-acceptance.py", "userpatches/t736-media-acceptance.py"),
    (ROOT / "userpatches/linux-t736-mainline-current.config", "userpatches/config/linux-t736-mainline-current.config"),
]
for path in sorted((ROOT / "userpatches/kernel/t736-mainline-6.18").glob("*.patch")):
    FILES.append((path, f"userpatches/kernel/t736-mainline-6.18/{path.name}"))
for path in sorted((ROOT / "userpatches/u-boot/u-boot-t736-mainline").glob("*.patch")):
    FILES.append((path, f"userpatches/u-boot/u-boot-t736-mainline/{path.name}"))


def patch_for(source: Path, target: str) -> str:
    raw = source.read_bytes()
    if b"\0" in raw:
        raise SystemExit(f"binary input is not allowed in the open patch: {source}")
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    out = [
        f"diff --git a/{target} b/{target}\n",
        "new file mode 100644\n",
        f"index 0000000..{hashlib.sha1(raw).hexdigest()[:7]}\n",
        "--- /dev/null\n",
        f"+++ b/{target}\n",
        f"@@ -0,0 +1,{len(lines)} @@\n",
    ]
    for line in lines:
        out.append("+" + line if line.endswith("\n") else "+" + line + "\n")
    if not raw.endswith(b"\n"):
        out.append("\\ No newline at end of file\n")
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "patches/t736-armbian-open-source.patch")
    args = parser.parse_args()
    missing = [str(source) for source, _ in FILES if not source.is_file()]
    if missing:
        raise SystemExit("missing patch input:\n" + "\n".join(missing))
    patch = "".join(patch_for(source, target) for source, target in FILES)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Write bytes so a Windows exporter produces the same LF patch as Linux.
    patch_text = (
        "# T736 open-source Armbian integration patch.\n"
        "# Apply at the root of the pinned Armbian build checkout with: git apply <file>\n"
        "# Licensed GPU/codec/DDR binaries are intentionally excluded.\n\n" + patch
    )
    args.output.write_bytes(patch_text.encode("utf-8"))
    print(f"wrote {args.output} ({len(FILES)} files, {len(patch.encode())} patch bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
