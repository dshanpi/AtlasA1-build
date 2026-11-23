#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 && -d /assets && -d /recipe && -d /work ]]
[[ ! -e /work/inputs && ! -e /work/build ]] || { echo 'Use an empty output directory' >&2; exit 2; }
# Ubuntu's qemu-user-static ships systemd binfmt rules, not the database used
# by update-binfmts. Register the pinned container emulator directly and test
# ARM64 execution before spending time compiling the source components.
if ! mountpoint -q /proc/sys/fs/binfmt_misc; then mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc; fi
if [[ -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]]; then
    printf '%s\n' -1 > /proc/sys/fs/binfmt_misc/qemu-aarch64
fi
test -x /usr/libexec/qemu-binfmt/aarch64-binfmt-P
grep '^:qemu-aarch64:' /usr/lib/binfmt.d/qemu-aarch64.conf > /proc/sys/fs/binfmt_misc/register
grep -q '^flags:.*F' /proc/sys/fs/binfmt_misc/qemu-aarch64
arch-test arm64
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
python3 /recipe/tools/build_atlasa1_frozen_rootfs.py --packages /work/packages \
    --bsp /work/bsp/output/debs --output /work/ubuntu --recipe /recipe
bash /recipe/tools/assemble_atlasa1_frozen_image.sh /recipe /work/build /work/ubuntu/rootfs /work/image
cp /recipe/config/clean-build/inputs.lock.json /work/image/
printf 'FRESH_HOST_BUILD_COMPLETE\n'
