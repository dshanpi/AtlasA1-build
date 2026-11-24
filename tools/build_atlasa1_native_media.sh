#!/usr/bin/env bash
# Build userspace packages for an Armbian-selected kernel and desktop.
set -euo pipefail
[[ $# == 5 ]] || { echo 'Usage: INPUTS NEW_WORK PVR_MODULE KERNEL_RELEASE DESKTOP' >&2; exit 2; }
inputs=$(realpath -e "$1")
out=$(realpath -m "$2")
pvr=$(realpath -e "$3")
release=$4
desktop=$5
tools=$(cd "$(dirname "$0")" && pwd)
sdk="$inputs/inputs"
export ATLAS_SOURCE_CACHE="$inputs/source-inputs-v1" JOBS=${JOBS:-6}
mkdir -- "$out"
bash "$tools/build_atlasa1_resolute_vendor.sh" "$sdk" "$out/vendor"
bash "$tools/prepare_atlasa1_sdl_sysroot.sh" "$out/sdl"
mkdir "$out/player-source"
tar -xf "$ATLAS_SOURCE_CACHE/ffmpeg.tar.xz" -C "$out/player-source" --strip-components=1
bash "$tools/build_atlasa1_resolute_player.sh" "$out/player-source" "$out/sdl" "$out/player"
if [[ $desktop == gnome ]]; then
    export ATLAS_FIREFOX_PANEL_CANDIDATE=1
    python3 "$tools/build_gpu_userspace.py" --tina "$sdk" --platform wayland --work "$out/wayland"
fi
bash "$tools/browser/build_firefox_resolute_ffmpeg.sh" "$ATLAS_SOURCE_CACHE/firefox/ffmpeg_8.0.1-3ubuntu2.dsc" "$out/firefox"
export T736_TINA_SDK="$sdk/out/t736/demo_aiot/buildroot/buildroot/host"
bash "$tools/browser/omx_scale_candidate/build_omx_panel.sh" "$tools/browser" --service-only "$out/service"
python3 "$tools/build_cedar_4k_omx.py" --tina "$sdk" --output "$out/omx"
python3 "$tools/prepare_atlasa1_resolute_media.py" --wc-archive "$out/vendor/t736-cedar-wc-v5.tar.gz" \
    --service-build "$out/service" --omx-vdec "$out/omx/libOmxVdec.so" --pvr-module "$pvr" \
    --kernel-release "$release" --gpu-deb "$out/vendor/t736-img-userspace-candidate_24.2.6603887-2_arm64.deb" --output "$out/overlay"
if [[ $desktop == xfce ]]; then bash "$tools/stage_atlasa1_resolute_x11.sh" "$out/overlay"; fi
touch "$out/complete"
