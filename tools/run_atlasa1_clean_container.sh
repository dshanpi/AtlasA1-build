#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 && -d /assets && -d /recipe && -d /work ]]
[[ ! -e /work/inputs && ! -e /work/build ]] || { echo 'Use an empty output directory' >&2; exit 2; }
tar -I zstd -xf /assets/atlasa1-build-inputs-v1.tar.zst -C /work
tar -I zstd -xf /assets/atlasa1-upstream-sources-v2.tar.zst -C /work
tar -I zstd -xf /assets/atlasa1-arm64-packages-v1.tar.zst -C /work
python3 /recipe/tools/relocate_atlasa1_build_inputs.py /work/inputs
chown -R ubuntu:ubuntu /work
export ATLAS_TINA_SDK=/work/inputs ATLAS_SOURCE_CACHE=/work/source-inputs-v1
export ATLAS_COMPONENTS_ONLY=1 JOBS=${JOBS:-6}
sudo -u ubuntu --preserve-env=ATLAS_TINA_SDK,ATLAS_SOURCE_CACHE,ATLAS_COMPONENTS_ONLY,JOBS \
    bash /recipe/tools/build_atlasa1_resolute.sh "$ATLAS_SOURCE_CACHE/armbian" /work/build --gnome-v47
sudo -u ubuntu bash /recipe/tools/build_atlasa1_frozen_bsp.sh "$ATLAS_SOURCE_CACHE" /work/bsp /recipe
if ! mountpoint -q /proc/sys/fs/binfmt_misc; then mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc; fi
# Register this image's fixed QEMU binary even if the host has an older entry.
update-binfmts --disable qemu-aarch64
update-binfmts --enable qemu-aarch64
python3 /recipe/tools/build_atlasa1_frozen_rootfs.py --packages /work/packages \
    --bsp /work/bsp/output/debs --output /work/ubuntu --recipe /recipe
bash /recipe/tools/assemble_atlasa1_frozen_image.sh /recipe /work/build /work/ubuntu/rootfs /work/image
cp /recipe/config/clean-build/inputs.lock.json /work/image/
printf 'FRESH_HOST_BUILD_COMPLETE\n'
