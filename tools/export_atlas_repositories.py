#!/usr/bin/env python3
"""Export the public T736 sources into the four AtlasA1 repositories.

The workspace contains historical build products and private inputs alongside
the source tree. This exporter uses an allow-list of source directories and
never copies generated artifacts, credentials, or vendor binaries. It creates
clean staging directories that can be reviewed and pushed independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
GENERATED = {
    "AtlasA1-build": """# AtlasA1-build\n\nPublic Armbian integration for the T736 Aurora/AtlasA1 board.\n\n## Build\n\n1. Clone the pinned Armbian framework listed in `config/sources.lock.json`.\n2. Apply `patches/t736-armbian-open-source.patch` at the framework root, or copy the checked-in `userpatches/` tree to `USERPATCHES_PATH`.\n3. Fetch the matching Linux and U-Boot sources and apply the patches from the AtlasA1-linux and AtlasA1-uboot repositories.\n4. Run the commands in `docs/ARMBIAN_REBUILD.md` on a case-sensitive Linux build host.\n\nThe build repository contains source and configuration only. It does not contain Tina, DDR, GPU, or codec binaries. Those authorised inputs must be supplied separately and checked against the recorded hashes before a board image is assembled.\n\nMedia support is maintained in AtlasA1-media. Its public source and patches can be built independently, while the licensed runtime remains an external input.\n""",
    "AtlasA1-linux": """# AtlasA1-linux\n\nLinux 6.18 board, Ethernet, GPU-kernel, and configuration sources for the T736 Aurora/AtlasA1 board.\n\nApply the patches to the pinned Linux commit in `config/sources.lock.json`, then use the build instructions in AtlasA1-build. Hardware acceptance records are kept with the build repository and state the scope of each result.\n""",
    "AtlasA1-uboot": """# AtlasA1-uboot\n\nU-Boot, TF-A, SPL, and LPDDR4x boot sources for the T736 Aurora/AtlasA1 board.\n\nThe board uses a fixed LPDDR4x training input supplied outside this public repository. The source tree documents the expected interface and checks, but does not redistribute the authorised vendor training binary. Build and payload instructions are in AtlasA1-build.\n""",
    "AtlasA1-media": """# AtlasA1-media\n\nCedar/OMX/PVR media integration and browser transport sources for the T736 Aurora/AtlasA1 board.\n\nThis repository contains public source, patches, tests, and manifests. Vendor codec/GPU libraries remain external inputs. Media acceptance commands and the exact limits of each result are documented in the validation files.\n""",
}

EXCLUDED_NAMES = {"__pycache__", ".git", "build", "output", "tmp", "private"}
EXCLUDED_SUFFIXES = {".pyc", ".o", ".a", ".so", ".ko", ".bin", ".img", ".deb", ".raw", ".png"}


class ExportError(RuntimeError):
    pass


def _safe_source(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    if any(part in EXCLUDED_NAMES for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def _copy(destination_root: Path, source: Path, relative: Path, records: dict[str, tuple[Path, str]]) -> None:
    if not _safe_source(source):
        return
    rel = relative.as_posix()
    previous = records.get(rel)
    if previous and previous[0] != source:
        raise ExportError(f"two sources map to {rel}: {previous[0]} and {source}")
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    records[rel] = (source, "source")


def _tree(source_base: Path, destination_root: Path, source_rel: str, destination_rel: str, records: dict[str, tuple[Path, str]], suffixes: set[str] | None = None) -> None:
    source_root = source_base / source_rel
    if not source_root.is_dir():
        raise ExportError(f"missing source directory: {source_root}")
    for source in sorted(source_root.rglob("*")):
        if not _safe_source(source):
            continue
        if suffixes is not None and source.suffix.lower() not in suffixes:
            continue
        relative = source.relative_to(source_root)
        _copy(destination_root, source, Path(destination_rel) / relative, records)


def _glob(source_base: Path, destination_root: Path, pattern: str, destination_prefix: str, records: dict[str, tuple[Path, str]], *, required: bool = True) -> None:
    matches = sorted(source_base.glob(pattern))
    if not matches and required:
        raise ExportError(f"pattern matched no files: {pattern}")
    for source in matches:
        if not _safe_source(source):
            continue
        _copy(destination_root, source, Path(destination_prefix) / source.name, records)


def _file(source_base: Path, destination_root: Path, source_rel: str, destination_rel: str, records: dict[str, tuple[Path, str]]) -> None:
    source = source_base / source_rel
    if not source.is_file():
        raise ExportError(f"missing source file: {source}")
    _copy(destination_root, source, Path(destination_rel), records)


def _add_generated(destination: Path, repo: str, records: dict[str, tuple[Path, str]]) -> None:
    target = destination / "README.md"
    target.write_text(GENERATED[repo], encoding="utf-8", newline="\n")
    records["README.md"] = (Path(f"generated:{repo}/README.md"), "generated")
    (destination / ".gitignore").write_text(
        "# Generated build products and private inputs\n"
        "output/\n"
        "build/\n"
        "tmp/\n"
        "private/\n"
        "*.img\n*.raw\n*.deb\n*.bin\n*.so\n*.ko\n*.o\n*.a\n*.pyc\n"
        "__pycache__/\n",
        encoding="utf-8",
        newline="\n",
    )
    records[".gitignore"] = (Path(f"generated:{repo}/.gitignore"), "generated")


def _export_build(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    for rel in (
        "config/board-facts.json", "config/boot-policy.json", "config/independent-boot-plan.json",
        "config/patch-ledger.json", "config/reference-components.json", "config/source-v10-inputs.json",
        "config/source-v11-inputs.template.json", "config/sources.lock.json", "config/t736-vendor-inputs.example.json",
        "config/desktop-v7-packages.txt",
    ):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("config/desktop-v7", "config/gpu-v10"):
        _tree(ROOT, destination, rel, rel, records)
    # Keep board-side host tests and the canonical CMA configuration
    # self-contained in the build repository.  The same source is also
    # distributed in the component repositories where it is consumed.
    _tree(ROOT, destination, "boards", "boards", records)
    for rel in ("userpatches/config",):
        _tree(ROOT, destination, rel, rel, records)
    _file(ROOT, destination, "userpatches/linux-t736-mainline-current.config", "userpatches/linux-t736-mainline-current.config", records)
    _file(ROOT, destination, "userpatches/t736-media-acceptance.py", "userpatches/t736-media-acceptance.py", records)
    for rel in ("docs/ARMBIAN_REBUILD.md", "docs/BUILD.md", "docs/BOOT_CHAIN.md", "docs/CODE_MAP.md", "docs/ETHERNET.md", "docs/HARDWARE_MAP.md", "docs/VALIDATION.md", "docs/WIRELESS.md", "docs/ATLAS_REPOSITORY_LAYOUT.md"):
        _file(ROOT, destination, rel, rel, records)
    _tree(ROOT, destination, "tests", "tests", records)
    for source in sorted((ROOT / "tools").glob("*.py")) + sorted((ROOT / "tools").glob("*.sh")):
        if source.name in {"export_atlas_repositories.py", "build_media_v29_candidate.py", "build_media_v28_candidate.py"}:
            continue
        _copy(destination, source, Path("tools") / source.name, records)
    for rel in ("tools/build_media_v29_candidate.py", "tools/validation/update_t736_media_v29.py"):
        _file(ROOT, destination, rel, rel, records)
    _file(ROOT, destination, "tools/export_atlas_repositories.py", "tools/export_atlas_repositories.py", records)
    for rel in ("tools/validation/README.md",):
        _file(ROOT, destination, rel, rel, records)
    _file(ROOT, destination, "patches/t736-armbian-open-source.patch", "patches/t736-armbian-open-source.patch", records)
    return records


def _export_linux(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    _tree(ROOT, destination, "userpatches/kernel", "userpatches/kernel", records)
    for source in sorted((ROOT / "userpatches").glob("linux-t736-*.config")):
        _copy(destination, source, Path("userpatches") / source.name, records)
    _tree(ROOT, destination, "patches/linux", "patches/linux", records)
    for source in sorted((ROOT / "patches").glob("pvr-*.patch")):
        _copy(destination, source, Path("patches") / source.name, records)
    for source in sorted((ROOT / "tools").glob("build_*kernel.sh")):
        _copy(destination, source, Path("tools") / source.name, records)
    for rel in ("tools/build_gpu_module.sh", "tools/check_kernel_config.py", "tools/check_ethernet_patch_series.py", "tools/prepare_linux.sh"):
        _file(ROOT, destination, rel, rel, records)
    return records


def _export_uboot(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    _tree(ROOT, destination, "userpatches/u-boot", "userpatches/u-boot", records)
    _tree(ROOT, destination, "patches/u-boot", "patches/u-boot", records)
    _tree(ROOT, destination, "patches/tf-a", "patches/tf-a", records)
    for rel in ("config/u-boot-source-v6.config", "config/t736-lp4-radxa-dram-overlay.fex", "config/t736-lp4x-fixed.fex"):
        _file(ROOT, destination, rel, rel, records)
    _tree(ROOT, destination, "spl", "spl", records)
    for source in sorted((ROOT / "tools").glob("build_source_uboot*.sh")):
        _copy(destination, source, Path("tools") / source.name, records)
    for rel in ("tools/build_tfa_independent_candidate.sh", "tools/build_t736_emmc_spl.py", "tools/build_t736_vendor_ddr.py", "tools/check_lpddr4_components.py", "tools/check_lpddr4_timing.py", "tools/check_spl_emmc.py", "tools/pack_t736_source_boot.py"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("docs/BOOT_CHAIN.md", "docs/FES_RAW.md", "docs/BACKUP_SOURCE_V6.md"):
        _file(ROOT, destination, rel, rel, records)
    return records


def _export_media(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    _tree(ROOT, destination, "patches/cedar", "patches/cedar", records)
    _tree(ROOT, destination, "tools/browser", "tools/browser", records)
    for pattern in ("tools/build_cedar*.py", "tools/build_media*.py", "tools/prepare_media*.py"):
        _glob(ROOT, destination, pattern, "tools", records)
    for rel in ("tools/install_t736_media_runtime.py", "tools/port_media_iommu.py", "tools/prepare_media_kernel.py"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("tools/validation/update_t736_media_v29.py", "tools/validation/audit_media_v29_package.py"):
        _file(ROOT, destination, rel, rel, records)
    for pattern in ("tools/validation/media_*.py", "tools/validation/browser_*.py", "tools/validation/cedar_*.py", "tools/validation/*nv21*.py", "tools/validation/*omx*.py", "tools/validation/decode_*.py", "tools/validation/build_h264_*.py"):
        # The OMX probe is optional because the current public tree has no
        # standalone *omx*.py validator.  Keep the export deterministic while
        # allowing the repository to grow that probe later.
        required = pattern != "tools/validation/*omx*.py"
        _glob(ROOT, destination, pattern, "tools/validation", records, required=required)
    for rel in ("docs/CEDAR_BRIDGE.md", "docs/BACKUP_MEDIA_V28_20261117.md"):
        _file(ROOT, destination, rel, rel, records)
    return records


EXPORTERS = {
    "AtlasA1-build": _export_build,
    "AtlasA1-linux": _export_linux,
    "AtlasA1-uboot": _export_uboot,
    "AtlasA1-media": _export_media,
}


def _manifest(destination: Path, repo: str, records: dict[str, tuple[Path, str]]) -> None:
    entries = []
    for relative, (source, kind) in sorted(records.items()):
        target = destination / relative
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        entries.append({"path": relative, "kind": kind, "source": str(source), "size": target.stat().st_size, "sha256": digest})
    for entry in entries:
        if entry["kind"] == "source":
            entry["source"] = f"mainline/{entry['path']}"
        else:
            entry["source"] = f"generated/{repo}/{entry['path']}"
    (destination / "SOURCE-MANIFEST.json").write_text(json.dumps({"schema": 1, "repository": repo, "generated_from": "workspace/mainline", "files": entries}, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--allow-existing", action="store_true", help="permit existing empty repository directories")
    args = parser.parse_args()
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for repo, exporter in EXPORTERS.items():
        destination = root / repo
        if destination.exists() and any(destination.iterdir()) and not args.allow_existing:
            raise SystemExit(f"refusing non-empty destination: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        records = exporter(destination)
        _add_generated(destination, repo, records)
        _manifest(destination, repo, records)
        print(f"{repo}: {len(records)} files -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
