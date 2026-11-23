#!/usr/bin/env bash
# Replay the non-APT desktop configuration from the locked armbian-config deb.
set -euo pipefail
if [[ ${ATLAS_DESKTOP_PRIVATE_MOUNTS:-} != yes ]]; then
    exec unshare --mount --propagation private env ATLAS_DESKTOP_PRIVATE_MOUNTS=yes bash "$0" "$@"
fi
[[ $EUID == 0 && $# == 2 ]] || { echo 'Usage (root): ROOTFS RECIPE' >&2; exit 2; }
root=$(realpath -e "$1")
recipe=$(realpath -e "$2")
[[ $root != / && -f $root/usr/lib/armbian-config/config.desktops.sh ]]
for path in proc sys run; do
    [[ -d "$root/$path" && ! -L "$root/$path" ]]
done
mount -t proc proc "$root/proc"
mount -t sysfs -o ro sysfs "$root/sys"
mount -t tmpfs -o nosuid,nodev tmpfs "$root/run"
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive CI=true bash -e <<'EOF'
declare -A module_options
desktops_dir=/usr/share/armbian-config/desktops
DESKTOP_DM=gdm3
mode=build
debug_log() { printf '%s\n' "$*"; }
dialog_infobox() { printf '%s\n' "$*"; }
srv_enable() { systemctl --no-reload enable "$@"; }
srv_disable() { systemctl --no-reload disable "$@"; }
source /usr/lib/armbian-config/config.desktops.sh
_module_desktops_write_apt_pin
module_desktop_branding gnome
_module_desktops_configure_networking
_module_desktops_configure_fprintd
_module_desktops_configure_psd build
_module_desktops_configure_boot_services
systemctl --no-reload mask systemd-firstboot.service
EOF
# These are selection metadata, not a copied rootfs. The package versions are
# independently locked and compared after all board packages are installed.
install -Dm644 "$recipe/config/clean-build/gnome.packages" "$root/etc/armbian/desktop/gnome.packages"
printf 'mid\n' > "$root/etc/armbian/desktop/gnome.tier"
test -s "$root/etc/dconf/db/local"
test -s "$root/usr/share/gdm/dconf/95-armbian-login"
test -s "$root/etc/apt/preferences.d/armbian-desktops"
test -s "$root/etc/NetworkManager/conf.d/00-armbian-readme.conf"
test -s "$root/usr/share/backgrounds/armbian/armbian18-Dre0x-Minum-light-3840x2160.jpg"
[[ $(readlink "$root/etc/systemd/system/systemd-firstboot.service") == /dev/null ]]
rm -f "$root/etc/apt/apt.conf.d/99mmdebstrap"
printf 'FROZEN_ARMBIAN_DESKTOP_CONFIGURED\n'
