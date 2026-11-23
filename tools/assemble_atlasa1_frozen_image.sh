#!/usr/bin/env bash
# Assemble only newly compiled components and a newly bootstrapped package tree.
set -euo pipefail
[[ $EUID == 0 && $# == 4 ]] || { echo 'Usage (root): RECIPE COMPONENT_BUILD ROOTFS OUTPUT' >&2; exit 2; }
recipe=$(realpath -e "$1")
build=$(realpath -e "$2")
root=$(realpath -e "$3")
out=$(realpath -m "$4")
tools="$recipe/tools"
release=6.18.63-t736-gnome-v47
mkdir -- "$out"
bash "$tools/configure_atlasa1_resolute.sh" "$root" \
    "$build/kernel/linux-image-${release}_6.18.63-47_arm64.deb" \
    "$build/kernel/pvr-out/target_aarch64/kbuild/pvrsrvkm.ko" "$build/media" \
    "$build/vendor/t736-img-userspace-candidate_24.2.6603887-2_arm64.deb" \
    "$build/player/atlasa1-player_0.1-6~resolute1_arm64.deb" \
    "$build/firefox/atlasa1-firefox-cedar_8.0.1-1.resolute1_arm64.deb"
bash "$tools/configure_atlasa1_gnome_release.sh" "$root" \
    "$build/wayland/atlasa1-img-wayland_24.2.6603887-3_arm64.deb"
# Never ship the transient, build-only localhost APT repository.
rm -f "$root/etc/apt/sources.list"
install -d "$root/etc/apt/sources.list.d"
cat > "$root/etc/apt/sources.list.d/ubuntu.sources" <<'EOF'
Types: deb
URIs: https://ports.ubuntu.com/ubuntu-ports
Suites: resolute resolute-updates resolute-security resolute-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
if grep -R -E '127\.0\.0\.1:18765|/work/|/repo/' "$root/etc/apt/sources.list.d"; then
    echo 'Build-only APT source leaked into rootfs' >&2; exit 1
fi
chroot "$root" dpkg-query -W -f='${binary:Package}\t${Version}\n' | LC_ALL=C sort > "$out/installed-packages.tsv"
LC_ALL=C sort "$recipe/config/clean-build/packages-arm64.tsv" > "$out/expected-packages.tsv"
diff -u "$out/expected-packages.tsv" "$out/installed-packages.tsv" > "$out/package-comparison.diff" || {
    cat "$out/package-comparison.diff" >&2; echo 'Package versions differ from the locked board' >&2; exit 1;
}
bash "$tools/verify_atlasa1_resolute.sh" "$root" "$release" --require-firefox-cedar
image="$out/Armbian_26.11_AtlasA1_Ubuntu-26.04_GNOME_clean_arm64.img"
python3 "$tools/pack_atlasa1_resolute.py" --rootfs "$root" --boot "$build/boot/payload" --output "$image"
xz -T4 -6 --keep "$image"
xz -t "$image.xz"
cd "$out"
sha256sum "$(basename "$image")" "$(basename "$image").xz" > SHA256SUMS
printf 'CLEAN_IMAGE_ASSEMBLY_PASSED\n'
