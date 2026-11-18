#!/usr/bin/env bash
# Build an Ubuntu 26.04 GNOME userspace and the matching AtlasA1 Armbian BSP.
# Usage: bash build_atlasa1_resolute_rootfs.sh OFFICIAL_ARMBIAN_CHECKOUT NEW_WORK_DIR
set -euo pipefail
if (( $# != 2 )); then
    echo "Usage: bash $0 OFFICIAL_ARMBIAN_CHECKOUT NEW_WORK_DIR" >&2
    exit 2
fi
source_tree=$(realpath -e "$1")
work=$(realpath -m "$2")
tools=$(cd -- "$(dirname -- "$0")" && pwd -P)
revision=2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736
patchfile="$tools/../patches/t736-armbian-open-source.patch"
git -C "$source_tree" cat-file -e "$revision^{commit}"
mkdir -- "$work"
git clone --no-checkout -- "$source_tree" "$work/framework"
cd "$work/framework"
git checkout --detach "$revision"
git remote set-url origin https://github.com/armbian/build.git
git apply --check "$patchfile"
git apply "$patchfile"
params=(ARCH=arm64 RELEASE=resolute BUILD_MINIMAL=no ARTIFACT_IGNORE_CACHE=yes MANAGE_ACNG=no SHARE_LOG=no)
if [[ -n ${CUSTOM_UBUNTU_MIRROR_PORTS:-} ]]; then
    params+=("CUSTOM_UBUNTU_MIRROR_PORTS=$CUSTOM_UBUNTU_MIRROR_PORTS")
fi
if [[ -n ${LOCAL_MIRROR:-} ]]; then
    params+=("LOCAL_MIRROR=$LOCAL_MIRROR")
fi
sudo env GIT_TERMINAL_PROMPT=0 ./compile.sh rootfs "${params[@]}" BUILD_DESKTOP=yes \
    DESKTOP_ENVIRONMENT=gnome DESKTOP_TIER=mid ROOTFS_COMPRESSION_RATIO=3
for package in armbian-bsp-cli armbian-base-files; do
    sudo env GIT_TERMINAL_PROMPT=0 ./compile.sh "$package" "${params[@]}" BOARD=t736-mainline \
        BRANCH=current EXPERT=yes BUILD_DESKTOP=no
done
shopt -s nullglob
archives=(cache/rootfs/rootfs-arm64-resolute-gnome-desktop-mid_*.tar.zst)
[[ ${#archives[@]} == 1 ]] || { echo "Expected one freshly built Resolute GNOME rootfs" >&2; exit 1; }
sudo bash "$tools/prepare_t736_resolute_rootfs.sh" "${archives[0]}" "$work/rootfs" output/debs
(
    cd "$work"
    sha256sum framework/cache/rootfs/*.tar.zst framework/output/debs/armbian-bsp-cli-t736-mainline-current*.deb \
        framework/output/debs/extra/resolute-utils/base-files*.deb > rootfs-build.sha256
    sudo chroot rootfs dpkg-query -W -f='${binary:Package}\t${Version}\n' |
        LC_ALL=C sort > rootfs-packages.tsv
)
printf 'Resolute GNOME root filesystem ready at %s/rootfs\n' "$work"
