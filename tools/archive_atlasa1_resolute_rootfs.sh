#!/usr/bin/env bash
# Archive the public Ubuntu userspace before device accounts, firmware and kernel integration.
set -euo pipefail
if (( EUID != 0 || $# != 2 )); then
    echo "Usage: sudo bash $0 PREPARED_ROOT NEW_ARCHIVE_DIRECTORY" >&2
    exit 2
fi
root=$(realpath -e "$1")
output=$(realpath -m "$2")
[[ "$root" != / && "$output/" != "$root/"* ]]
grep -qx 'VERSION_CODENAME=resolute' "$root/usr/lib/os-release"
[[ $(chroot "$root" dpkg --print-architecture) == arm64 ]]
[[ ! -s "$root/etc/machine-id" && $(readlink "$root/var/lib/dbus/machine-id") == /etc/machine-id ]]
[[ $(readlink "$root/etc/resolv.conf") == /run/systemd/resolve/stub-resolv.conf ]]
[[ ! -e "$root/var/lib/systemd/random-seed" && ! -s "$root/etc/apt/auth.conf" ]]
[[ ! -e "$root/opt/atlasa1-player" && ! -e "$root/opt/t736-cedar" ]]
[[ -z $(find "$root/boot" -name 'vmlinuz*' -print -quit) ]]
[[ -z $(find "$root/etc/ssh" -name 'ssh_host_*' -print -quit) ]]
for path in home root/.ssh etc/ssl/private etc/NetworkManager/system-connections etc/apt/auth.conf.d; do
    if [[ -d "$root/$path" && -n $(find "$root/$path" -type f -size +0 -print -quit) ]]; then
        echo "Unexpected content under $path in public root filesystem" >&2
        exit 1
    fi
done
for shadow in "$root"/etc/shadow{,-}; do
    [[ ! -e "$shadow" ]] || awk -F: '$2 !~ /^[!*]+$/ { exit 1 }' "$shadow"
done
[[ -z $(chroot "$root" dpkg --audit) ]]
mkdir -- "$output"
cd "$output"
# shellcheck disable=SC2016 # dpkg-query expands the package fields.
chroot "$root" dpkg-query -W -f='${binary:Package}\t${Version}\n' | LC_ALL=C sort > rootfs-packages.tsv
name=AtlasA1_Ubuntu-26.04_arm64_public-rootfs.tar.zst
tar --one-file-system --acls --xattrs --xattrs-include='*' --sparse --numeric-owner -C "$root" -cf - . |
    zstd -T4 -8 -q -o "$name.part"
zstd -tq "$name.part"
mv -- "$name.part" "$name"
sha256sum "$name" rootfs-packages.tsv > SHA256SUMS-rootfs
cat SHA256SUMS-rootfs
