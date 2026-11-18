#!/usr/bin/env bash
# Rebuild AtlasA1 eMMC media on an Armbian-supported Linux build host.
set -euo pipefail
if [[ $# != 2 ]]; then
    echo "Usage: $0 OFFICIAL_ARMBIAN_CHECKOUT NEW_OUTPUT_DIRECTORY" >&2
    echo "Set ATLAS_TINA_SDK to the configured T736 Tina SDK (see docs/UBUNTU_26_04.md)." >&2
    exit 2
fi
framework=$(realpath -e "$1")
out=$(realpath -m "$2")
tools=$(cd "$(dirname "$0")" && pwd -P)
tina=$(realpath -e "${ATLAS_TINA_SDK:?set the configured T736 Tina SDK path}")
ddr="$tina/brandy/dramlib/sun60iw2p1/spl_libdram/libdram"
test -x "$tina/out/t736/demo_aiot/buildroot/buildroot/host/bin/aarch64-none-linux-gnu-gcc"
git -C "$framework" cat-file -e '2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736^{commit}'
check_file() { printf '%s  %s\n' "$1" "$2" | sha256sum --check --status; }
check_file 5361d148fa097ccc14e15a173523783d0eb1a71969bc76d57eb8e1229ddc6d90 "$ddr"
mkdir -- "$out"
mkdir -- "$out/sources"
if [[ -n ${ATLAS_IMG_DEB:-} || -n ${ATLAS_CEDAR_WC:-} ]]; then
    gpu=$(realpath -e "${ATLAS_IMG_DEB:?set both cached vendor input paths}")
    wc=$(realpath -e "${ATLAS_CEDAR_WC:?set both cached vendor input paths}")
else
    bash "$tools/build_atlasa1_resolute_vendor.sh" "$tina" "$out/vendor"
    gpu="$out/vendor/t736-img-userspace-candidate_24.2.6603887-2_arm64.deb"
    wc="$out/vendor/t736-cedar-wc-v5.tar.gz"
fi
if [[ -n ${ATLAS_SDL_SYSROOT:-} ]]; then
    sdl=$(realpath -e "$ATLAS_SDL_SYSROOT")
else
    sdl="$out/sdl-sysroot"
    bash "$tools/prepare_atlasa1_sdl_sysroot.sh" "$sdl"
fi
cd "$out/sources"

git clone --depth=1 --branch v2026.10 https://github.com/u-boot/u-boot.git u-boot
git -C u-boot archive --format=tar.gz -o "$out/sources/u-boot.tar.gz" 5508406582f6f7120dce0c4b3059819a41788db2
check_file af3cca26c2ea2a352efc05980d991b7310959dc431c427ad3250e832a221abd8 u-boot.tar.gz
curl --fail --location --retry 3 -o tf-a.tar.gz \
    https://codeload.github.com/InfernoEmbedded/arm-trusted-firmware/tar.gz/7d322909068fc4bb4ee35e9e43c78ed68d98619b
python3 "$tools/build_atlasa1_release_boot.py" --work "$out/boot" \
    --uboot-archive "$out/sources/u-boot.tar.gz" --tfa-archive "$out/sources/tf-a.tar.gz" --ddr-library "$ddr"

git clone --depth=1 --branch v6.18.63 https://github.com/gregkh/linux.git linux
bash "$tools/build_atlasa1_release_kernel.sh" "$out/sources/linux" "$tina" "$out/kernel"
kernel="$out/kernel/linux-image-6.18.63-t736-media-v30_6.18.63-30_arm64.deb"
pvr="$out/kernel/pvr-out/target_aarch64/kbuild/pvrsrvkm.ko"

curl --fail --location --retry 3 -o ffmpeg.tar.xz https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz
check_file de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
bash "$tools/build_atlasa1_resolute_player.sh" "$out/sources/ffmpeg-7.1.5" "$sdl" "$out/player"
player="$out/player/atlasa1-player_0.1-5~resolute1_arm64.deb"
export T736_TINA_SDK="$tina/out/t736/demo_aiot/buildroot/buildroot/host"
bash "$tools/browser/omx_scale_candidate/build_omx_panel.sh" "$tools/browser" --service-only "$out/service"
python3 "$tools/build_cedar_4k_omx.py" --tina "$tina" --output "$out/omx"
python3 "$tools/prepare_atlasa1_resolute_media.py" --wc-archive "$wc" --service-build "$out/service" \
    --omx-vdec "$out/omx/libOmxVdec.so" --pvr-module "$pvr" --gpu-deb "$gpu" --output "$out/media"
bash "$tools/stage_atlasa1_resolute_x11.sh" "$out/media"

bash "$tools/build_atlasa1_resolute_rootfs.sh" "$framework" "$out/ubuntu"
root="$out/ubuntu/rootfs"
sudo bash "$tools/configure_atlasa1_resolute.sh" "$root" "$kernel" "$pvr" "$out/media" "$gpu" "$player"
sudo bash "$tools/verify_atlasa1_resolute.sh" "$root"
image="$out/Armbian_26.11_AtlasA1_Ubuntu-26.04_Desktop_arm64.img"
sudo python3 "$tools/pack_atlasa1_resolute.py" --rootfs "$root" --boot "$out/boot/payload" --output "$image"
# xz preserves file ownership and returns a warning status for a root-owned input.
sudo chown --reference="$out" -- "$image" "${image%.img}.manifest.json"
xz -T4 -6 --keep "$image"
xz -t "$image.xz"
cd "$out"
sha256sum "$(basename "$image").xz" > SHA256SUMS
printf 'Image: %s.xz\nManifest: %s.manifest.json\n' "$image" "${image%.img}"
