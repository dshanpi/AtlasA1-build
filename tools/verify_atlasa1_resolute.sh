#!/bin/bash
# Run the release checks against a mounted Ubuntu image on AArch64 or with binfmt.
set -euo pipefail
if [[ ${1:-} != --private-mounts ]]; then
    exec unshare --mount --propagation private bash "$0" --private-mounts "$@"
fi
shift
root=$(realpath -e "${1:?mounted rootfs required}")
[[ $(id -u) == 0 && "$root" != / ]]
for path in dev proc sys run tmp; do
    [[ -d "$root/$path" && ! -L "$root/$path" ]]
done
if ! mountpoint -q "$root/dev"; then
    mount --rbind /dev "$root/dev"
    mount --make-rslave "$root/dev"
fi
mountpoint -q "$root/proc" || mount -t proc proc "$root/proc"
mountpoint -q "$root/sys" || mount -t sysfs -o ro sysfs "$root/sys"
for path in run tmp; do
    mountpoint -q "$root/$path" || mount -t tmpfs -o nosuid,nodev,mode=1777 tmpfs "$root/$path"
done
release=6.18.63-t736-media-v30
player=/opt/atlasa1-player/bin/ffplay
libs=/opt/atlasa1-player/lib
target() { chroot "$root" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C HOME=/tmp "$@"; }
grep -E '^(ID|VERSION_ID|VERSION_CODENAME)=' "$root/usr/lib/os-release"
grep -E '^(BOARD|BOARD_NAME|VERSION)=' "$root/etc/armbian-release"
[[ $(target dpkg --print-architecture) == arm64 && ! -s "$root/etc/machine-id" ]]
[[ -z $(find "$root/etc/ssh" -maxdepth 1 -name 'ssh_host_*_key' -print -quit) ]]
[[ -z $(target dpkg --audit) ]]
target dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package} ${Version}\n' \
    "linux-image-$release" t736-img-userspace-candidate atlasa1-player \
    armbian-bsp-cli-t736-mainline-current xfce4-session lightdm gnome-shell gdm3 firefox ffmpeg
target ffmpeg -version | sed -n '1p'
target gnome-shell --version
firefox_version=$(target dpkg-query -W -f='${Version}' firefox)
[[ "$firefox_version" != *snap* ]]
[[ -e "$root/usr/lib/firefox/firefox" || -e "$root/opt/firefox/firefox" ]]
[[ -r "$root/usr/share/xsessions/xfce.desktop" && -r "$root/usr/share/wayland-sessions/gnome.desktop" ]]
[[ -r "$root/usr/share/xsessions/atlasa1-xfce.desktop" ]]
grep -qx 'user-session=atlasa1-xfce' "$root/etc/lightdm/lightdm.conf.d/90-atlasa1-x11.conf"
[[ $(basename "$(readlink "$root/etc/systemd/system/display-manager.service")") == lightdm.service ]]
target systemctl is-enabled t736-cedar.socket
target systemctl is-enabled serial-getty@ttyS0.service
target modinfo -k "$release" -F vermagic pvrsrvkm | grep -F "$release "
[[ -s "$root/boot/initrd.img-6.18.63-t736-armbian" ]]
for name in vmlinuz initrd.img; do
    [[ $(target readlink -f "/boot/$name-6.18.63-t736-armbian") == "/boot/$name-$release" ]]
done
lsinitramfs "$root/boot/initrd.img-6.18.63-t736-armbian" | grep -x init
relocations=$(target env LD_LIBRARY_PATH="$libs" ldd -r "$player" 2>&1)
if grep -Ei 'not found|undefined symbol' <<<"$relocations"; then exit 1; fi
target env LD_LIBRARY_PATH="$libs" "$player" -hide_banner -h full 2>&1 | grep -F -- '-wait_video_start'
target gst-inspect-1.0 --version
bash "$(dirname "$0")/verify_atlasa1_resolute_media.sh" "$root"
echo "AtlasA1 Ubuntu userspace checks passed"
