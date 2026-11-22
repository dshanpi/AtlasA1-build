#!/usr/bin/env bash
# Finish the official Armbian Resolute ARM64 rootfs for AtlasA1 image assembly.
# Usage: sudo bash prepare_t736_resolute_rootfs.sh ROOTFS.tar.zst NEW_ROOT BSP_OUTPUT_DEBS
set -euo pipefail

if (( EUID != 0 || $# != 3 )); then
    echo "Usage: sudo bash $0 ROOTFS.tar.zst NEW_ROOT BSP_OUTPUT_DEBS" >&2
    exit 2
fi
if [[ ${T736_PRIVATE_MOUNT_NAMESPACE:-} != yes ]]; then
    exec unshare --mount --propagation private env T736_PRIVATE_MOUNT_NAMESPACE=yes bash "$0" "$@"
fi
archive=$(realpath -e "$1")
root=$(realpath -m "$2")
debs=$(realpath -e "$3")
shopt -s nullglob
bsp=("$debs"/armbian-bsp-cli-t736-mainline-current_*_arm64__*.deb)
base=("$debs"/extra/resolute-utils/base-files_*resolute_arm64__*.deb)
[[ ${#bsp[@]} == 1 && ${#base[@]} == 1 ]] || { echo "Expected one BSP and one Resolute base-files package" >&2; exit 1; }
mkdir -- "$root"
tar --xattrs --acls --numeric-owner -I zstd -xf "$archive" -C "$root"
grep -q '^VERSION_CODENAME=resolute$' "$root/usr/lib/os-release"
[[ $(chroot "$root" dpkg --print-architecture) == arm64 ]]
mount -t proc proc "$root/proc"
mount --rbind /dev "$root/dev"
mount -t sysfs -o ro sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
scratch=$(mktemp -d "$root/tmp/atlas-bsp-XXXXXXXX")
mkdir -p "$scratch/saved"
preserve() {
    if [[ -e "$root/$1" || -L "$root/$1" ]]; then
        mv -- "$root/$1" "$scratch/saved/${1##*/}"
    fi
}
restore() {
    rm -f -- "$root/$1"
    if [[ -e "$scratch/saved/${1##*/}" || -L "$scratch/saved/${1##*/}" ]]; then
        mv -- "$scratch/saved/${1##*/}" "$root/$1"
    fi
}
preserve etc/resolv.conf
preserve usr/sbin/policy-rc.d
cleanup() {
    restore etc/resolv.conf
    restore usr/sbin/policy-rc.d
    rm -rf -- "$scratch"
}
trap cleanup EXIT
cp -L /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 0755 "$root/usr/sbin/policy-rc.d" "$scratch"
cp "${bsp[0]}" "$scratch/bsp.deb"
cp "${base[0]}" "$scratch/base.deb"
inside=${scratch#"$root"}
run() { chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive LC_ALL=C "$@"; }
run apt-get -o Acquire::Retries=3 -o Acquire::Languages=none \
    -o Acquire::IndexTargets::deb::Contents-deb::DefaultEnabled=false \
    -o Acquire::IndexTargets::deb::Contents-deb-legacy::DefaultEnabled=false update
# The rootfs repository may already contain a newer Armbian base-files build.
# Install the package made from this checkout, as the framework's image stage does.
run apt-get -o Acquire::Retries=3 -y --allow-downgrades --no-install-recommends install "$inside/base.deb"
printf '%s\n' 'gdm3 shared/default-x-display-manager select lightdm' 'lightdm shared/default-x-display-manager select lightdm' |
    run debconf-set-selections
run apt-get -o Acquire::Retries=3 -y --no-install-recommends install \
    "$inside/bsp.deb" armbian-config openssh-server network-manager netplan.io systemd-resolved systemd-timesyncd \
    gdm3 gnome-session gnome-shell gnome-control-center nautilus \
    rtkit at-spi2-core evolution-data-server python3-gi libxcb-dri2-0 \
    lightdm lightdm-gtk-greeter xfce4-session xfce4-panel xfwm4 xfdesktop4 thunar \
    xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-libinput x11-xserver-utils \
    firefox ffmpeg gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad pipewire-audio fonts-noto-cjk fonts-ubuntu
[[ -x "$root/usr/lib/firefox/firefox" || -x "$root/opt/firefox/firefox" ]]
test -x "$root/usr/sbin/lightdm"
printf '/usr/sbin/lightdm\n' > "$root/etc/X11/default-display-manager"
install -d "$root/etc/lightdm/lightdm.conf.d"
printf '[Seat:*]\nuser-session=xfce\ngreeter-session=lightdm-gtk-greeter\n' > "$root/etc/lightdm/lightdm.conf.d/50-atlasa1-session.conf"
run systemctl --no-reload enable --force lightdm.service NetworkManager.service systemd-resolved.service systemd-timesyncd.service serial-getty@ttyS0.service armbian-firstrun.service ssl-cert.service
run systemctl --no-reload set-default graphical.target
# The board uses a fixed fourth partition and a vendor GPT copy at LBA 40960.
run systemctl --no-reload mask armbian-resize-filesystem.service
install -d -m 0755 "$root/etc/netplan"
printf 'network:\n  version: 2\n  renderer: NetworkManager\n' > "$root/etc/netplan/90-atlasa1-desktop.yaml"
chmod 0600 "$root/etc/netplan/90-atlasa1-desktop.yaml"
run netplan generate
printf 'atlasa1\n' > "$root/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 atlasa1\n::1 localhost ip6-localhost ip6-loopback\n' > "$root/etc/hosts"
run apt-get check
audit=$(run dpkg --audit)
[[ -z "$audit" ]] || { echo "$audit" >&2; exit 1; }
test -f "$root/usr/share/wayland-sessions/gnome.desktop"
test -f "$root/usr/share/xsessions/xfce.desktop"
test -f "$root/etc/armbian-release"
run apt-get clean
find "$root/var/lib/apt/lists" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
find "$root/etc/ssh" -maxdepth 1 -type f -name 'ssh_host_*' -delete
rm -f -- "$root/etc/ssl/certs/ssl-cert-snakeoil.pem" "$root/etc/ssl/private/ssl-cert-snakeoil.key"
: > "$root/etc/machine-id"
ln -sfn /etc/machine-id "$root/var/lib/dbus/machine-id"
rm -f -- "$root/var/lib/systemd/random-seed"
run dpkg-query -W -f='${binary:Package}\t${Version}\n' base-files armbian-config \
    armbian-bsp-cli-t736-mainline-current gnome-shell gdm3 xfce4-session ffmpeg
trap - EXIT
cleanup
ln -sfn /run/systemd/resolve/stub-resolv.conf "$root/etc/resolv.conf"
# The upstream cache leaves service startup blocked until its image stage.
for service_tool in /sbin/initctl /sbin/start-stop-daemon; do
    if [[ $(run dpkg-divert --listpackage "$service_tool") == LOCAL ]]; then
        rm -f -- "$root$service_tool"
        run dpkg-divert --quiet --local --rename --remove "$service_tool"
    fi
done
rm -f -- "$root/usr/sbin/policy-rc.d"
run start-stop-daemon --version
