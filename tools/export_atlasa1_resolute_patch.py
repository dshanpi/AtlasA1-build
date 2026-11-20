#!/usr/bin/env python3
"""Export the board definition and Ubuntu 26.04 release recipe as one Armbian Git patch."""
import argparse
import hashlib
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
PREFIX = 'userpatches/atlasa1-release'
BOARD_PATCH = 'patches/t736-armbian-open-source.patch'
INPUTS = (
    'docs/GNOME_WAYLAND.md', 'config/gnome-wayland/*',
    'docs/CHROMIUM.md', 'tools/validation/chromium_playback.py',
    'docs/GNOME_MEDIA.md', 'evidence/gnome-media-20261119/*.json', 'evidence/gnome-media-20261119/*.log',
    'tools/build_gnome_media_candidate.sh', 'patches/linux/gnome-media-20261119/*',
    'tools/validation/sdl_texture_ring.c', 'tools/validation/sdl_packed_yuv.c',
    'tools/validation/sdl_packed_yuv_planes.c', 'tools/validation/cedar_gpu_import.c',
    'tools/validation/cedar_frame_export_probe.c', 'tools/validation/cedar_gnome_dmabuf_player.c',
    'tools/validation/run_gnome_dmabuf_probe.sh',
    'tools/validation/summarize_dmabuf_timing.py',
    'tools/validation/run_gnome_display_trace.sh',
    'tools/build_gnome_media_probes.sh',
    'config/gpu-userspace-wayland.env', 'config/gpu-userspace-wayland-run.sh',
    'tools/stage_atlasa1_gnome_wayland.sh', 'tools/activate_atlasa1_gnome.sh',
    'tools/validation/wayland_present.c',
    'tools/validation/ffplay_wayland_present.c', 'tools/validation/ffplay_offscreen.py',
    'tools/validation/ffplay_present_trace.c', 'tests/test_atlasa1_player.py',
    'tools/validation/gnome_wayland_browser.py', 'tools/validation/firefox_renderer_probe.py',
    'tools/validation/firefox_media_debug_snapshot.js',
    'evidence/atlasa1-gnome-wayland-20261119.json', 'evidence/gnome-wayland-20261119/*',
    BOARD_PATCH, 'docs/UBUNTU_26_04.md',
    'tools/validation/atlasa1_finalize_gpt.py', 'tools/validation/atlasa1_io_inventory.py',
    'tools/validation/atlasa1_resolute_live.py', 'tools/build_atlasa1_rc1_broker_update.sh',
    'evidence/atlasa1-ubuntu26-rc1-installed-validation-20261118.json',
    'evidence/atlasa1-ubuntu26-rc1-fes-coldboot-20261118.json',
    'config/t736-lp4x-fixed.fex', 'config/u-boot-source-v6.config',
    'config/atlasa1-resolute-vendor-files.json', 'config/gpu-userspace-x11.env',
    'config/gpu-userspace-run.sh', 'config/gpu-userspace-gnome.desktop',
    'config/gpu-v10/20-t736-modesetting-1080p.conf', 'config/gpu-v10/t736-hdmi-session-init.sh',
    'userpatches/config/t736-display/30-t736-x11-blank.conf', 'evidence/source-uboot-backup-audit-20261115.json',
    'patches/linux/media-v30-replay/*', 'patches/linux/media-v30-pvr-replay/*',
    'patches/linux/atlasa1-wireless-v31.patch', 'boards/wireless-v31/kernel.config', 'docs/WIRELESS.md',
    'evidence/atlasa1-wireless-v33-hardware-20261118.json', 'boards/wireless-v31/diagnostics/*',
    'evidence/atlasa1-hw-v34-kernel-replay-20261118.json', 'evidence/atlasa1-pcie-v34-coldboot-20261118.json',
    'evidence/atlasa1-ubuntu26-rc1-hardware-trial-boots-20261118.json',
    'evidence/atlasa1-v34-image-integration-20261118.json',
    'evidence/atlasa1-rc1-installed-broker-update-20261118.json',
    'evidence/atlasa1-cedar-format-switch-20261118.json', 'evidence/atlasa1-firefox160-ffmpeg8-20261118.json',
    'evidence/atlasa1-firefox-image-integration-20261119.json', 'tools/validation/firefox_headless_playback.py',
    'patches/linux/atlasa1-pcie-v32.patch', 'boards/pcie-v32/pcie.config',
    'patches/linux/atlasa1-wireless-dldo5-v33.patch',
    'patches/linux/atlasa1-wireless-reset-v33.patch',
    'patches/linux/atlasa1-pcie-combo1-v33.patch',
    'patches/linux/atlasa1-pcie-pipe-map-v34.patch',
    'patches/linux/atlasa1-pcie-dma-v43.patch',
    'patches/linux/atlasa1-pcie-aspm-v45.patch',
    'boards/pcie-v32/hw-v34-inputs.sha256', 'boards/pcie-v32/verify-slot.sh', 'boards/pcie-v32/check-nvme-readonly.py',
    'patches/u-boot/t736-source-boot.patch', 'patches/u-boot/t736-cpu-d.patch',
    'patches/tf-a/0001-t736-bl31-dram-layout.patch', 'patches/cedar/*.patch',
    'patches/ffmpeg/ffplay-refresh-budget.patch', 'patches/ffmpeg/ffplay-first-picture-audio.patch',
    'boards/t736-uboot-cpuclock.c', 'boards/t736-uboot-cpuclock-d.c',
    'spl/cpuclock/*.[ch]', 'spl/early/*.[ch]', 'spl/lpddr4/axp8191.[ch]',
    'spl/peripheral/board_power.[ch]', 'spl/storage/emmc.[ch]',
    'spl/vendor_ddr/*.S', 'spl/vendor_ddr/*.c', 'spl/vendor_ddr/*.ld',
    'tools/build_atlasa1_resolute.sh', 'tools/build_atlasa1_release_boot.py',
    'tools/build_t736_emmc_spl.py', 'tools/build_t736_source_handoff.py', 'tools/build_source_uboot_cpu_d.sh',
    'tools/prepare_atlas_release_sources.py', 'tools/build_atlasa1_release_kernel.sh',
    'tools/build_atlasa1_resolute_rootfs.sh', 'tools/prepare_t736_resolute_rootfs.sh',
    'tools/extract_atlasa1_fes_loader.py',
    'tools/build_atlasa1_resolute_player.sh', 'tools/build_atlasa1_player.py',
    'tools/build_atlasa1_resolute_vendor.sh', 'tools/prepare_atlasa1_sdl_sysroot.sh',
    'tools/build_gpu_userspace.py', 'tools/build_cedar_bridge.py', 'tools/build_cedar_wc_candidate.py',
    'tools/validation/gpu_userspace_probe.c', 'tools/validation/gpu_runtime_view.py', 'tools/validation/cedar-env',
    'tools/validation/atlasa1_sdl_gles_smoke.c',
    'tools/player/*', 'tools/browser/shm_v2/*', 'tools/browser/omx_scale_candidate/*',
    'tools/browser/copy_candidate/cedar_parallel_copy.h', 'tools/browser/cedar_backend.[ch]',
    'tools/browser/gstomx.conf', 'tools/browser/cedarc.conf', 'tools/browser/ffmpeg_cedar.c',
    'tools/browser/build_firefox_resolute_ffmpeg.sh', 'tools/browser/firefox-resolute', 'tools/browser/cedar_client.h',
    'tools/browser/firefox_panel_mode.py', 'tools/browser/test_firefox_panel_mode.py',
    'tools/browser/FIREFOX_RESOLUTE.md',
    'tools/browser/firefox-resolute-copyright', 'tools/browser/firefox-resolute-source.sha256',
    'tools/browser/copy_candidate/firefox-dr1-output.patch', 'tools/browser/verify_firefox_resolute.py',
    'tools/browser/copy_candidate/firefox-stage-timing.patch',
    'tools/browser/copy_candidate/firefox-panel-output.patch',
    'tools/browser/copy_candidate/firefox-panel-client.patch',
    'tools/browser/panel_candidate/private-1080p-panel.patch', 'tools/browser/panel_candidate/prefer-omx-panel.patch',
    'tools/browser/panel_candidate/cedar_panel.h', 'tools/browser/build_browser_ffmpeg.py',
    'tools/build_cedar_4k_omx.py', 'tools/prepare_atlasa1_resolute_media.py', 'tests/test_cedar_shm_transport.c',
    'tools/stage_atlasa1_resolute_x11.sh', 'tools/configure_atlasa1_resolute.sh',
    'tools/verify_atlasa1_resolute.sh', 'tools/verify_atlasa1_resolute_media.sh', 'tools/pack_atlasa1_resolute.py',
    'tools/pack_armbian_raw_v6.py', 'tools/pack_boot_validation.py', 'tools/pack_t736_media_v28_boot.py',
)


def sources():
    paths = set()
    for pattern in INPUTS:
        matched = [p for p in BASE.glob(pattern) if p.is_file() and not p.is_symlink()]
        if not matched:
            raise ValueError(f'Missing recipe input {pattern}')
        paths.update(matched)
    return sorted(paths)


def export(output):
    with output.open('wb') as patch:
        patch.write((BASE / BOARD_PATCH).read_bytes().replace(b'\r\n', b'\n'))
        for path in sources():
            rel = path.relative_to(BASE).as_posix()
            name = f'{PREFIX}/{rel}'
            data = path.read_bytes().replace(b'\r\n', b'\n')
            if b'\x00' in data:
                raise ValueError(f'Unexpected binary input {rel}')
            blob = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
            mode = '100755' if data.startswith(b'#!') else '100644'
            patch.write(f'diff --git a/{name} b/{name}\nnew file mode {mode}\n'.encode())
            patch.write(f'index {"0" * 40}..{blob}\n'.encode())
            if data:
                lines = data.split(b'\n')
                if lines[-1] == b'':
                    lines.pop()
                patch.write(f'--- /dev/null\n+++ b/{name}\n@@ -0,0 +1,{len(lines)} @@\n'.encode())
                for line in lines:
                    patch.write(b'+' + line + b'\n')
                if not data.endswith(b'\n'):
                    patch.write(b'\\ No newline at end of file\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    export(args.output)
