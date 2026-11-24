#!/usr/bin/env bash
# Build PowerVR against the kernel selected by Armbian.
set -euo pipefail
[[ $# == 4 ]] || { echo 'Usage: PVR_SOURCE KERNEL_TREE MODULE_INSTALL_ROOT COMPILER_PREFIX' >&2; exit 2; }
source=$(realpath -e "$1")
kernel=$(realpath -e "$2")
target=$(realpath -e "$3")
compiler=$4
release=$(cat "$kernel/include/config/kernel.release")
# The vendor makefile prunes directories whose names start with a dot.
out="$kernel/atlasa1-pvr-build"
src="$kernel/atlasa1-pvr-source"
if [[ ! -d $src ]]; then cp -a "$source" "$src"; fi
kbuild="$out/target_aarch64/kbuild"
cd "$src"
while IFS= read -r -d '' path; do
    mkdir -p "$kbuild/$(dirname "$path")"
    ln -sfn "$src/$path" "$kbuild/$path"
done < <(find . -path ./build -prune -o -name '*.c' -type f -print0)
make -C build/linux/sunxi_linux -j"${JOBS:-6}" ARCH=arm64 CROSS_COMPILE="$compiler" \
    LOCALVERSION=-current-atlasa1 KERNELDIR="$kernel" OUT="$out" \
    KERNEL_CC="${compiler}gcc" KERNEL_LD="${compiler}ld" KERNEL_NM="${compiler}gcc-nm" \
    KERNEL_OBJCOPY="${compiler}objcopy" GPU_BUILD_TYPE=release BUILD=release \
    SUPPORT_LINUX_DVFS=0 SUPPORT_PDVFS=0 SUPPORT_DMA_FENCE=1 SUPPORT_BUFFER_SYNC=1
[[ $(modinfo -F vermagic "$kbuild/pvrsrvkm.ko") == "$release "* ]]
install -Dm644 "$kbuild/pvrsrvkm.ko" "$target/lib/modules/$release/extra/pvrsrvkm.ko"
"${compiler}strip" --strip-debug "$target/lib/modules/$release/extra/pvrsrvkm.ko"
depmod -b "$target" "$release"
