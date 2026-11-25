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
    "AtlasA1-build": """# AtlasA1-build

AtlasA1 / T736 的 Armbian Ubuntu 26.04 LTS（arm64）eMMC 镜像。使用 `bash build.sh` 构建 GNOME Wayland / GDM 版本，包含 PowerVR、Cedar、Firefox 硬解入口和原生播放器。镜像下载、校验和与逐项验收范围见 [Releases](https://github.com/dshanpi/AtlasA1-build/releases)。

新主机构建入口为 `bash build.sh`，按版本清单自动获取所需输入，不再要求用户准备 Tina SDK。2026-11-23 已从空目录完整重建 GNOME 镜像：断网容器、1,411 个软件包版本一致、149 个桌面资源一致，镜像及压缩包检查通过。固定版本为 `backup-20261123-clean-build-v1`；条件、完整记录和实板验收边界见 [新主机构建](docs/FRESH_HOST_BUILD.md)。原有手工配方与 [单文件补丁](patches/atlasa1-resolute-armbian.patch) 保留。

板级源码按组件备份，可分别检查启动链、内核与播放器。本仓库还保留原有通用 Armbian 板级补丁及此前 Debian 开发镜像的集成记录。[U-Boot / SPL / TF-A](https://github.com/dshanpi/AtlasA1-uboot) · [Linux / PowerVR](https://github.com/dshanpi/AtlasA1-linux) · [Cedar / 播放器](https://github.com/dshanpi/AtlasA1-media) · [早期 Armbian 适配](docs/ARMBIAN_REBUILD.md)

主分支包含双格式 Cedar 服务和适用于 Firefox 160 的 FFmpeg 8.0.1 适配。新入口固定使用 GNOME v47；旧版 Xfce、`--pcie-v34` 和手工 SDK 配方保留在维护者脚本中。无线芯片的 SDIO 枚举和蓝牙 HCI 响应仍待打通。[浏览器实测](evidence/atlasa1-firefox160-ffmpeg8-20261118.json) · [4K HEVC 与 1080p H.264 切换](evidence/atlasa1-cedar-format-switch-20261118.json) · [v34 整盘打包检查](evidence/atlasa1-v34-image-integration-20261118.json)
""",
    "AtlasA1-linux": """# AtlasA1-linux

Linux board patches, kernel configurations, Ethernet support, GPU module integration and Cedar driver changes for the DshanPI AtlasA1.

The GNOME image recipe selects v47 with `build_gnome_media_candidate.sh --boot-fast`. It combines the tested 400 MHz PowerVR profile, display submission fixes, eMMC tuning, PCIe DMA mapping and reduced boot logging. Wireless register experiments remain separate diagnostic sources. AW869C / AIC8800D80 Wi-Fi and Bluetooth are not working yet. [GNOME changes](docs/GNOME_MEDIA.md) · [Wireless investigation](evidence/wireless-path-20261120/RUNTIME-TRIALS-20261121.md)

The v30 candidate adds the boot parameter `t736_cedar_wc.heap_limit_mib` to the v29 512 MiB CMA configuration. Its default is 128 MiB, with a 256 MiB upper bound. A one-shot eMMC boot at 256 MiB produced 3840×2160 hardware output. The first Firefox measurement presented 3 of 599 frames. The driver keeps retired imported buffers pinned until reboot. [Build recipe](tools/build_media_v30_candidate.sh) · [Package and module checksums](evidence/media-v30-heap-budget-build-20261118.json) · [Board measurement](evidence/media-v30-4k-browser-hardware-20261118.json)

For the complete GNOME image, use `bash build.sh` in [AtlasA1-build](https://github.com/dshanpi/AtlasA1-build). Its [fresh-host workflow](https://github.com/dshanpi/AtlasA1-build/blob/main/docs/FRESH_HOST_BUILD.md) automatically fetches the pinned public inputs; no locally prepared Tina SDK is required. This repository preserves the matching kernel component sources.

The release replay recipe starts from the pinned upstream Git tree. It imports the board's Tina display sources by SHA-256, applies the complete board delta and checks the resulting 317 board files. [Clean-source build instructions](patches/linux/media-v30-replay/README.md)

The kernel-only build option `--pcie-v34` includes the J58 PCIe host, the four-bit COMBO1 PIPE route and the SDIO/UART transports. After a cold boot the built-in driver registered the root port at `0000:00:00.0`, and an empty-slot rescan completed. The later GNOME v45 candidate adds the DMA window and disables unsupported ASPM on COMBO1. An Intel SSD now cold-enumerates and passes independent read-only comparisons; Gen1 x1 remains the validated link rate. See the board README for the uutils direct-I/O caveat and evidence. [Build and test](boards/pcie-v32/README.md) · [Clean build](evidence/atlasa1-hw-v34-kernel-replay-20261118.json) · [Board measurement](evidence/atlasa1-pcie-v34-coldboot-20261118.json)
""",
    "AtlasA1-uboot": """# AtlasA1-uboot\n\nU-Boot, TF-A, SPL and fixed LPDDR4x boot sources for the AtlasA1 board. The component-level boot packer takes the DDR training library as a separate input. For the complete image, [AtlasA1-build/build.sh](https://github.com/dshanpi/AtlasA1-build/blob/main/docs/FRESH_HOST_BUILD.md) fetches and verifies that public input automatically; users do not need to supply a private SDK. This repository preserves the matching boot component sources.\n\n[Reconstruct the tested CPU-D U-Boot tree](patches/u-boot/media-v28-replay/README.md) · [Build the Ubuntu release boot chain](tools/build_atlasa1_release_boot.py)\n""",
    "AtlasA1-media": """# AtlasA1-media\n\nCedar/OMX/PVR media integration for AtlasA1 / T736. The Ubuntu 26.04 native player builds its FFmpeg 7.1.5 libraries in a private prefix and uses the system SDL2 ABI. The media overlay installs the matching Cedar service and PowerVR firmware. [Player builder](tools/build_atlasa1_resolute_player.sh) · [Overlay builder](tools/prepare_atlasa1_resolute_media.py) · [Ubuntu 26.04 build instructions](https://github.com/dshanpi/AtlasA1-build/blob/main/docs/UBUNTU_26_04.md)\n\nFor a complete image on a fresh host, use [AtlasA1-build/build.sh](https://github.com/dshanpi/AtlasA1-build/blob/main/docs/FRESH_HOST_BUILD.md). It automatically fetches the fixed public libraries and rebuilds this media integration; no private SDK path is required.\n\nEarlier board measurements cover Cedar hardware decoding and the PowerVR GLES2 renderer. [Native player](tools/player/README.md) · [Playback measurements and display status](docs/PLAYBACK.md)\n""",
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
    # Git stores the public text sources with LF. Hash those same bytes on
    # every build host, including a Windows checkout with core.autocrlf.
    data = destination.read_bytes()
    if source.suffix.lower() != '.log' and b"\r\n" in data and b"\0" not in data:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            destination.write_bytes(data.replace(b"\r\n", b"\n"))
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
    # Preserve captured UART/progress bytes. Git's platform newline conversion
    # must not invalidate the hashes of archived hardware evidence.
    attributes = destination / '.gitattributes'
    attributes.write_text('* text=auto eol=lf\n*.log -text\n*.gz -text\n*.xz -text\n*.zst -text\n', encoding='utf-8', newline='\n')
    records['.gitattributes'] = (Path(f'generated:{repo}/.gitattributes'), 'generated')
    _file(ROOT, destination, 'tools/verify_source_manifest.py', 'tools/verify_source_manifest.py', records)
    target = destination / "README.md"
    readme = GENERATED[repo]
    if repo == 'AtlasA1-build':
        readme = readme.replace('# AtlasA1-build\n', '# AtlasA1-build\n\n原生 Armbian 入口：运行 `./compile.sh`，在官方菜单选择 `AtlasA1 / T736`。内核配置使用 `./compile.sh BOARD=atlasa1 BRANCH=current kernel-config`。完整 GNOME 镜像已通过官方流程构建及离线检查，包含 PowerVR、Cedar、Firefox 适配和播放器；新镜像尚未实板启动。支持范围、非交互命令和官方源码加单文件补丁的方法见 [原生构建说明](docs/NATIVE_ARMBIAN_BUILD.md)。\n', 1)
    if repo in {'AtlasA1-build', 'AtlasA1-media'}:
        readme += '\nGNOME 50 / Wayland v47 完整镜像已发布，并于 2026-11-22 完成 eMMC 整盘写入、8 GiB SHA-256 回读和断电启动。PowerVR WebRender 与 Cedar 硬解已接通，但不能宣称浏览器 1080p60 或全链路零丢帧通过。主分支另修复首次显示配置与自动校时；已发布 RC1 镜像保持原始字节，安装后修复和实测限制见 [发行记录](https://github.com/dshanpi/AtlasA1-build/releases/tag/v2026.11.21-ubuntu26.04-gnome-v47-rc1)。\n'
    target.write_text(readme, encoding="utf-8", newline="\n")
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


def _export_gnome_wayland(destination: Path, records: dict[str, tuple[Path, str]]) -> None:
    for rel in ('config/gpu-userspace-wayland.env', 'config/gpu-userspace-wayland-run.sh',
                'tools/stage_atlasa1_gnome_wayland.sh', 'tools/activate_atlasa1_gnome.sh',
                'docs/GNOME_WAYLAND.md', 'docs/GNOME_MEDIA.md',
                'docs/CHROMIUM.md', 'tools/validation/chromium_playback.py',
                'docs/BOOT_SPLASH.md', 'tools/stage_atlasa1_plymouth.sh',
                'tools/prepare_atlasa1_boot_kernel.py',
                'tools/validation/wayland_present.c', 'tools/validation/gnome_wayland_browser.py',
                'tools/validation/firefox_renderer_probe.py',
                'tools/validation/ffplay_wayland_present.c',
                'tools/validation/sdl_texture_ring.c', 'tools/validation/sdl_packed_yuv.c',
                'tools/validation/sdl_packed_yuv_planes.c', 'tools/validation/cedar_gpu_import.c',
                'tools/validation/cedar_frame_export_probe.c', 'tools/validation/cedar_gnome_dmabuf_player.c',
                'tools/validation/run_gnome_dmabuf_probe.sh',
                'tools/validation/summarize_dmabuf_timing.py',
                'tools/validation/run_gnome_display_trace.sh',
                'tools/build_gnome_media_probes.sh',
                'evidence/atlasa1-gnome-wayland-20261119.json'):
        _file(ROOT, destination, rel, rel, records)
    _tree(ROOT, destination, 'config/gnome-wayland', 'config/gnome-wayland', records)
    _tree(ROOT, destination, 'config/plymouth', 'config/plymouth', records)
    _tree(ROOT, destination, 'config/initramfs', 'config/initramfs', records)
    _tree(ROOT, destination, 'evidence/boot-and-cleanup-20261120', 'evidence/boot-and-cleanup-20261120', records)
    _tree(ROOT, destination, 'evidence/bootfast-20261120', 'evidence/bootfast-20261120', records)
    _tree(ROOT, destination, 'tools/browser/chromium156', 'tools/browser/chromium156', records)
    _tree(ROOT, destination, 'evidence/gnome-wayland-20261119', 'evidence/gnome-wayland-20261119', records)
    _tree(ROOT, destination, 'evidence/gnome-media-20261119', 'evidence/gnome-media-20261119', records)


def _export_build(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    _file(ROOT, destination, 'build.sh', 'build.sh', records)
    _file(ROOT, destination, 'compile.sh', 'compile.sh', records)
    _file(ROOT, destination, 'docs/NATIVE_ARMBIAN_BUILD.md', 'docs/NATIVE_ARMBIAN_BUILD.md', records)
    _file(ROOT, destination, 'tools/validation/firefox_media_debug_snapshot.js',
          'tools/validation/firefox_media_debug_snapshot.js', records)
    _tree(ROOT, destination, 'userpatches/extensions', 'userpatches/extensions', records)
    _tree(ROOT, destination, 'evidence/clean-build-20261123', 'evidence/clean-build-20261123', records)
    _tree(ROOT, destination, 'evidence/native-armbian-20261124', 'evidence/native-armbian-20261124', records)
    _tree(ROOT, destination, 'evidence/independent-host-build-20261124', 'evidence/independent-host-build-20261124', records)
    _file(ROOT, destination, 'docs/FRESH_HOST_BUILD.md', 'docs/FRESH_HOST_BUILD.md', records)
    _tree(ROOT, destination, 'evidence/gnome-release-20261121', 'evidence/gnome-release-20261121', records)
    _tree(ROOT, destination, 'evidence/wireless-path-20261120', 'evidence/wireless-path-20261120', records)
    _export_gnome_wayland(destination, records)
    for rel in (
        "config/board-facts.json", "config/boot-policy.json", "config/independent-boot-plan.json",
        "config/patch-ledger.json", "config/reference-components.json", "config/source-v10-inputs.json",
        "config/source-v11-inputs.template.json", "config/sources.lock.json", "config/t736-vendor-inputs.example.json",
        "config/desktop-v7-packages.txt", "config/gpu-userspace-gnome.desktop",
        "config/gpu-userspace-x11.env", "config/gpu-userspace-run.sh",
    ):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("config/desktop-v7", "config/gpu-v10", "config/clean-build"):
        _tree(ROOT, destination, rel, rel, records)
    # Keep board-side host tests and the canonical CMA configuration
    # self-contained in the build repository.  The same source is also
    # distributed in the component repositories where it is consumed.
    _tree(ROOT, destination, "boards", "boards", records)
    _tree(ROOT, destination, "patches/cedar", "patches/cedar", records)
    for rel in ("spl", "patches/u-boot", "patches/tf-a", "patches/linux/media-v30-replay",
                "patches/linux/media-v30-pvr-replay", "patches/linux/gnome-media-20261119"):
        _tree(ROOT, destination, rel, rel, records)
    for rel in ("config/u-boot-source-v6.config", "config/t736-lp4x-fixed.fex", "evidence/source-uboot-backup-audit-20261115.json",
                "config/atlasa1-resolute-vendor-files.json", "tools/validation/gpu_userspace_probe.c",
                "tools/validation/gpu_runtime_view.py", "tools/validation/cedar-env",
                "tools/validation/atlasa1_sdl_gles_smoke.c",
                "evidence/atlasa1-ubuntu26-release-replay-checks-20261118.json",
                "evidence/atlasa1-ubuntu-resolute-rootfs-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-image-manifest-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-fes-coldboot-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-installed-validation-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-hardware-trial-boots-20261118.json",
                "evidence/atlasa1-v34-image-integration-20261118.json",
                "evidence/atlasa1-v34-firefox-image-20261119.json",
                "evidence/atlasa1-v34-public-downloads-20261119.json",
                "evidence/atlasa1-rc1-installed-broker-update-20261118.json",
                "evidence/atlasa1-armbian-v34-patch-replay-20261119.json",
                "evidence/atlasa1-cedar-format-switch-20261118.json",
                "tools/validation/atlasa1_resolute_live.py", "tools/validation/atlasa1_finalize_gpt.py",
                "tools/validation/atlasa1_io_inventory.py",
                "evidence/atlasa1-ubuntu26-rc1-board-media-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-packages-20261118.tsv",
                "evidence/atlas-ubuntu26-board-rebuild-20261118.json",
                "evidence/atlasa1-clean-source-replay-20261118.json"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("userpatches/config", "userpatches/kernel/t736-mainline-6.18",
                "userpatches/u-boot/u-boot-t736-mainline"):
        _tree(ROOT, destination, rel, rel, records)
    _file(ROOT, destination, "userpatches/linux-t736-mainline-current.config", "userpatches/linux-t736-mainline-current.config", records)
    _file(ROOT, destination, "userpatches/t736-media-acceptance.py", "userpatches/t736-media-acceptance.py", records)
    for rel in ("tools/browser/cedarc.conf", "tools/browser/gstomx.conf",
                "tools/browser/cedar_backend.c", "tools/browser/cedar_backend.h",
                "tools/browser/copy_candidate/cedar_parallel_copy.h",
                "patches/cedar/backend-parallel-direct-slot.patch"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("docs/ARMBIAN_REBUILD.md", "docs/UBUNTU_26_04.md", "docs/BUILD.md", "docs/BOOT_CHAIN.md", "docs/CODE_MAP.md", "docs/ETHERNET.md", "docs/HARDWARE_MAP.md", "docs/VALIDATION.md", "docs/WIRELESS.md", "docs/ATLAS_REPOSITORY_LAYOUT.md"):
        _file(ROOT, destination, rel, rel, records)
    _tree(ROOT, destination, "tests", "tests", records)
    _tree(ROOT, destination, "tools/player", "tools/player", records)
    _tree(ROOT, destination, "tools/browser/shm_v2", "tools/browser/shm_v2", records)
    _tree(ROOT, destination, "tools/browser/omx_scale_candidate", "tools/browser/omx_scale_candidate", records)
    for rel in ("tools/browser/build_browser_ffmpeg.py", "tools/browser/ffmpeg_cedar.c",
                "tools/browser/build_firefox_resolute_ffmpeg.sh", "tools/browser/firefox-resolute",
                "tools/browser/firefox_panel_mode.py", "tools/browser/test_firefox_panel_mode.py",
                "tools/browser/firefox-resolute-source.sha256", "tools/browser/firefox-resolute-copyright",
                "tools/browser/copy_candidate/firefox-dr1-output.patch", "tools/browser/verify_firefox_resolute.py",
                "tools/browser/copy_candidate/firefox-stage-timing.patch",
                "tools/browser/copy_candidate/firefox-panel-output.patch",
                "tools/browser/copy_candidate/firefox-panel-client.patch",
                "tools/browser/FIREFOX_RESOLUTE.md", "evidence/atlasa1-firefox160-ffmpeg8-20261118.json",
                "evidence/atlasa1-firefox-image-integration-20261119.json",
                "tools/browser/panel_candidate/private-1080p-panel.patch",
                "tools/browser/panel_candidate/prefer-omx-panel.patch",
                "tools/browser/panel_candidate/cedar_panel.h",
                "tools/browser/cedar_client.h"):
        _file(ROOT, destination, rel, rel, records)
    for source in sorted((ROOT / "tools").glob("*.py")) + sorted((ROOT / "tools").glob("*.sh")):
        if source.name in {"export_atlas_repositories.py", "build_media_v29_candidate.py", "build_media_v28_candidate.py"}:
            continue
        _copy(destination, source, Path("tools") / source.name, records)
    for rel in ("tools/build_media_v29_candidate.py", "tools/validation/update_t736_media_v29.py"):
        _file(ROOT, destination, rel, rel, records)
    _file(ROOT, destination, "tools/export_atlas_repositories.py", "tools/export_atlas_repositories.py", records)
    for rel in ("tools/validation/README.md", "tools/validation/ffplay_offscreen.py", "tools/validation/ffplay_present_trace.c",
                "tools/validation/ffplay_start_sync.md", "tools/validation/ffplay_start_sync_probe.c",
                "tools/validation/firefox_headless_playback.py", "tools/validation/media_acceptance.py"):
        _file(ROOT, destination, rel, rel, records)
    _file(ROOT, destination, "patches/t736-armbian-open-source.patch", "patches/t736-armbian-open-source.patch", records)
    _file(ROOT, destination, "patches/atlasa1-resolute-armbian.patch", "patches/atlasa1-resolute-armbian.patch", records)
    for rel in ("patches/linux/media-v30-cedar-heap-quota.patch", "patches/linux/atlasa1-wireless-v31.patch",
                "patches/linux/atlasa1-wireless-dldo5-v33.patch", "patches/linux/atlasa1-pcie-v32.patch",
                "patches/linux/atlasa1-wireless-reset-v33.patch",
                "patches/linux/atlasa1-pcie-combo1-v33.patch",
                "patches/linux/atlasa1-pcie-pipe-map-v34.patch",
                "patches/linux/atlasa1-pcie-dma-v43.patch",
                "patches/linux/atlasa1-pcie-aspm-v45.patch",
                "evidence/atlasa1-pcie-v32-empty-slot-20261118.json",
                "evidence/atlasa1-pcie-v33-pipe-route-20261118.json",
                "evidence/atlasa1-hw-v34-kernel-replay-20261118.json",
                "evidence/atlasa1-pcie-v34-coldboot-20261118.json",
                "evidence/atlasa1-wireless-v31-rebuild-20261118.json",
                "evidence/atlasa1-wireless-v33-hardware-20261118.json",
                "patches/ffmpeg/ffplay-refresh-budget.patch",
                "patches/ffmpeg/ffplay-first-picture-audio.patch",
                "evidence/ffplay-first-picture-sync-qemu-20261118.json",
                "evidence/atlasa1-player-armbian-rootfs-20261118.json",
                "evidence/atlasa1-player-panel-package-20261118.json",
                "evidence/atlasa1-player-preferred-panel-package-20261118.json",
                "evidence/atlasa1-player-start-sync-package-20261118.json",
                "patches/cedar/omx-4k-broker-buffers.patch",
                "evidence/armbian-source-boot-layout-test-20261118.json",
                "evidence/media-v30-heap-budget-build-20261118.json",
                "evidence/media-v30-4k-browser-hardware-20261118.json",
                "evidence/media-v30-4k-wc-parallel-20261118.json",
                "evidence/media-v30-parallel-slot-build-20261118.json",
                "evidence/media-v30-gnome-display-idle-20261118.json",
                "evidence/media-v30-4k-firefox-dr1-20261118.json",
                "evidence/atlas-display-media-v29-reboot-20261118.json"):
        _file(ROOT, destination, rel, rel, records)
    return records


def _export_linux(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    _tree(ROOT, destination, 'evidence/wireless-path-20261120', 'evidence/wireless-path-20261120', records)
    _tree(ROOT, destination, 'evidence/bootfast-20261120', 'evidence/bootfast-20261120', records)
    _file(ROOT, destination, "tools/build_gnome_media_candidate.sh", "tools/build_gnome_media_candidate.sh", records)
    _file(ROOT, destination, "docs/GNOME_MEDIA.md", "docs/GNOME_MEDIA.md", records)
    _tree(ROOT, destination, "evidence/gnome-media-20261119", "evidence/gnome-media-20261119", records)
    _tree(ROOT, destination, "userpatches/kernel", "userpatches/kernel", records)
    for source in sorted((ROOT / "userpatches").glob("linux-t736-*.config")):
        _copy(destination, source, Path("userpatches") / source.name, records)
    _tree(ROOT, destination, "patches/linux", "patches/linux", records)
    _tree(ROOT, destination, "boards/wireless-v31", "boards/wireless-v31", records)
    _tree(ROOT, destination, "boards/pcie-v32", "boards/pcie-v32", records)
    for filename in ("atlasa1-pcie-v32-build-20261118.json", "atlasa1-pcie-v32-empty-slot-20261118.json",
                     "atlasa1-hw-v33-build-20261118.json", "atlasa1-pcie-v33-pipe-route-20261118.json",
                     "atlasa1-hw-v34-kernel-replay-20261118.json", "atlasa1-pcie-v34-coldboot-20261118.json"):
        _file(ROOT, destination, f"evidence/{filename}", f"evidence/{filename}", records)
    _file(ROOT, destination, "docs/WIRELESS.md", "docs/WIRELESS.md", records)
    _file(ROOT, destination, "evidence/atlasa1-wireless-v31-rebuild-20261118.json", "evidence/atlasa1-wireless-v31-rebuild-20261118.json", records)
    _file(ROOT, destination, "evidence/atlasa1-wireless-v33-hardware-20261118.json", "evidence/atlasa1-wireless-v33-hardware-20261118.json", records)
    _file(ROOT, destination, "tools/prepare_atlas_release_sources.py", "tools/prepare_atlas_release_sources.py", records)
    for rel in ("tools/build_media_v30_candidate.sh", "tools/build_atlasa1_release_kernel.sh", "evidence/atlas-ubuntu26-board-rebuild-20261118.json",
                "evidence/media-v30-heap-budget-build-20261118.json",
                "evidence/media-v30-4k-browser-hardware-20261118.json", "config/sources.lock.json",
                "evidence/atlasa1-clean-source-replay-20261118.json"):
        _file(ROOT, destination, rel, rel, records)
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
    _glob(ROOT, destination, "boards/t736-uboot-cpuclock*.c", "boards", records)
    for rel in ("tools/prepare_atlas_release_sources.py", "tools/build_atlasa1_release_boot.py",
                "evidence/atlasa1-ubuntu26-rc1-fes-coldboot-20261118.json",
                "evidence/atlas-ubuntu26-board-rebuild-20261118.json",
                "tools/build_t736_source_handoff.py", "evidence/source-uboot-backup-audit-20261115.json",
                "evidence/atlasa1-clean-source-replay-20261118.json"):
        _file(ROOT, destination, rel, rel, records)
    for source in sorted((ROOT / "tools").glob("build_source_uboot*.sh")):
        _copy(destination, source, Path("tools") / source.name, records)
    for rel in ("tools/build_tfa_independent_candidate.sh", "tools/build_t736_emmc_spl.py", "tools/build_t736_vendor_ddr.py", "tools/check_lpddr4_components.py", "tools/check_lpddr4_timing.py", "tools/check_spl_emmc.py", "tools/pack_t736_source_boot.py"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("docs/BOOT_CHAIN.md", "docs/FES_RAW.md", "docs/BACKUP_SOURCE_V6.md"):
        _file(ROOT, destination, rel, rel, records)
    return records


def _export_media(destination: Path) -> dict[str, tuple[Path, str]]:
    records: dict[str, tuple[Path, str]] = {}
    _export_gnome_wayland(destination, records)
    _tree(ROOT, destination, "patches/cedar", "patches/cedar", records)
    _tree(ROOT, destination, "tools/browser", "tools/browser", records)
    _tree(ROOT, destination, "tools/player", "tools/player", records)
    _file(ROOT, destination, "tools/build_atlasa1_resolute_player.sh", "tools/build_atlasa1_resolute_player.sh", records)
    _file(ROOT, destination, "tools/prepare_atlasa1_resolute_media.py", "tools/prepare_atlasa1_resolute_media.py", records)
    for rel in ("tools/verify_atlasa1_resolute_media.sh", "evidence/atlas-ubuntu26-board-rebuild-20261118.json",
                "evidence/atlasa1-firefox160-ffmpeg8-20261118.json",
                "evidence/atlasa1-firefox-image-integration-20261119.json",
                "evidence/atlasa1-rc1-installed-broker-update-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-installed-validation-20261118.json",
                "tools/build_atlasa1_rc1_broker_update.sh", "evidence/atlasa1-cedar-format-switch-20261118.json",
                "evidence/atlasa1-ubuntu26-rc1-board-media-20261118.json",
                "tools/build_atlasa1_resolute_vendor.sh", "tools/prepare_atlasa1_sdl_sysroot.sh",
                "tools/build_gpu_userspace.py", "config/atlasa1-resolute-vendor-files.json",
                "config/gpu-userspace-x11.env", "config/gpu-userspace-run.sh", "config/gpu-userspace-gnome.desktop",
                "tools/validation/gpu_userspace_probe.c", "tools/validation/gpu_runtime_view.py",
                "tools/validation/cedar-env", "tools/validation/atlasa1_sdl_gles_smoke.c"):
        _file(ROOT, destination, rel, rel, records)
    for pattern in ("tools/build_cedar*.py", "tools/build_media*.py", "tools/prepare_media*.py"):
        _glob(ROOT, destination, pattern, "tools", records)
    for rel in ("tools/install_t736_media_runtime.py", "tools/port_media_iommu.py", "tools/prepare_media_kernel.py",
                "evidence/media-v30-heap-budget-build-20261118.json",
                "patches/linux/media-v30-cedar-heap-quota.patch", "tools/build_media_v30_candidate.sh"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("tools/validation/update_t736_media_v29.py", "tools/validation/audit_media_v29_package.py"):
        _file(ROOT, destination, rel, rel, records)
    for rel in ("tools/validation/README.md", "tools/validation/firefox_headless_playback.py", "tools/validation/ffplay_offscreen.py", "tools/validation/ffplay_present_trace.c",
                "tools/validation/ffplay_start_sync.md", "tools/validation/ffplay_start_sync_probe.c",
                "tests/test_ffmpeg_cedar_dr1.c", "tests/test_cedar_backend.c", "tests/test_cedar_shm_transport.c",
                "tests/test_cedar_parallel_direct.c", "tools/build_cedar_parallel_slot.sh",
                "evidence/media-v30-4k-browser-hardware-20261118.json",
                "evidence/media-v30-4k-wc-parallel-20261118.json",
                "evidence/media-v30-parallel-slot-build-20261118.json",
                "evidence/media-v30-gnome-display-idle-20261118.json",
                "evidence/media-v30-4k-firefox-dr1-20261118.json",
                "tests/test_cedar_shm_seals.c", "tests/test_cedar_shm_client_fork.c",
                "evidence/cedar-direct-slot-build-20261118.json",
                "evidence/atlas-display-media-v29-reboot-20261118.json",
                "evidence/firefox-headless-hevc1080p60-v8-first-20261118.json"):
        _file(ROOT, destination, rel, rel, records)
    _glob(ROOT, destination, "evidence/firefox-hevc1080p60-v8-*-20261118.json", "evidence", records)
    for rel in ("evidence/media-v30-4k-firefox-parallel-20261118.json",
                "evidence/media-v30-4k-native-playback-20261118.json",
                "evidence/media-v30-4k-omx-panel-20261118.json",
                "evidence/media-v30-1080-playback-20261118.json",
                "evidence/cedar-peer-roles-build-20261118.json",
                "patches/ffmpeg/ffplay-refresh-budget.patch", "tools/build_ffplay_refresh_pair.sh",
                "patches/ffmpeg/ffplay-first-picture-audio.patch",
                "evidence/ffplay-first-picture-sync-qemu-20261118.json",
                "tools/build_atlasa1_player.py", "tests/test_atlasa1_player.py",
                "evidence/atlasa1-native-player-package-20261118.json",
                "evidence/atlasa1-player-panel-package-20261118.json",
                "evidence/atlasa1-player-preferred-panel-package-20261118.json",
                "evidence/atlasa1-player-start-sync-package-20261118.json",
                "evidence/ffplay-refresh-budget-build-20261118.json"):
        _file(ROOT, destination, rel, rel, records)
    for pattern in ("tools/validation/media_*.py", "tools/validation/browser_*.py", "tools/validation/cedar_*.py", "tools/validation/*nv21*.py", "tools/validation/*omx*.py", "tools/validation/decode_*.py", "tools/validation/build_h264_*.py"):
        # The OMX probe is optional because the current public tree has no
        # standalone *omx*.py validator.  Keep the export deterministic while
        # allowing the repository to grow that probe later.
        required = pattern != "tools/validation/*omx*.py"
        _glob(ROOT, destination, pattern, "tools/validation", records, required=required)
    for rel in ("docs/PLAYBACK.md", "docs/CEDAR_BRIDGE.md", "docs/BACKUP_MEDIA_V28_20261117.md"):
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
