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
release=${2:-6.18.63-t736-media-v30}
[[ $release == 6.18.63-t736-media-v30 || $release == 6.18.63-t736-hw-v34 || $release == 6.18.63-t736-gnome-v47 ]]
[[ $# -le 2 || ( $# == 3 && $3 == --require-firefox-cedar ) ]]
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
if [[ ${3:-} == --require-firefox-cedar || -e $root/usr/bin/atlasa1-firefox ]]; then
    case $(target dpkg-query -W -f='${db:Status-Abbrev} ${Version}' atlasa1-firefox-cedar) in 'ii  8.0.1-1~resolute1'|'ii  8.0.1-1~resolute1+panel2') ;; *) exit 1 ;; esac
    chroot --userspec="$(target id -u t736):$(target id -g t736)" "$root" \
        /usr/bin/env -i HOME=/tmp PATH=/usr/bin:/bin LC_ALL=C XDG_CURRENT_DESKTOP=XFCE \
        /usr/bin/python3 - < "$(dirname "$0")/browser/verify_firefox_resolute.py"
fi
[[ -r "$root/usr/share/xsessions/xfce.desktop" && -r "$root/usr/share/wayland-sessions/gnome.desktop" ]]
[[ -r "$root/usr/share/xsessions/atlasa1-xfce.desktop" ]]
grep -qx 'user-session=atlasa1-xfce' "$root/etc/lightdm/lightdm.conf.d/90-atlasa1-x11.conf"
if [[ $release == 6.18.63-t736-gnome-v47 ]]; then
    [[ $(basename "$(readlink "$root/etc/systemd/system/display-manager.service")") == gdm.service ]]
    grep -qx 'AutomaticLoginEnable=false' "$root/etc/gdm3/custom.conf"
    grep -qx 'Session=atlasa1-gnome' "$root/var/lib/AccountsService/users/t736"
    test -r "$root/opt/atlasa1-img-wayland/runtime-gles/libEGL.so.1"
    test -x "$root/usr/libexec/mutter-x11-frames.atlasa1-real"
    test -r "$root/opt/atlasa1-firefox/lib/browser-panel-enabled"
    grep -qx 'video/mp4=atlasa1-player.desktop;' "$root/etc/xdg/gnome-mimeapps.list"
else
    [[ $(basename "$(readlink "$root/etc/systemd/system/display-manager.service")") == lightdm.service ]]
fi
target systemctl is-enabled t736-cedar.socket
target systemctl is-enabled serial-getty@ttyS0.service
target modinfo -k "$release" -F vermagic pvrsrvkm | grep -F "$release "
[[ -s "$root/boot/initrd.img-6.18.63-t736-armbian" ]]
[[ $(target readlink -f /boot/vmlinuz-6.18.63-t736-armbian) == "/boot/vmlinuz-$release.atlasa1.gz" ]]
[[ $(target readlink -f /boot/initrd.img-6.18.63-t736-armbian) == "/boot/initrd.img-$release" ]]
python3 - "$root/boot/vmlinuz-$release" "$root/boot/vmlinuz-$release.atlasa1.gz" <<'PY'
import gzip, sys
from pathlib import Path
source = Path(sys.argv[1]).read_bytes()
if source[:2] == b'\x1f\x8b':
    source = gzip.decompress(source)
assert source[56:60] == b'ARM\x64'
assert gzip.decompress(Path(sys.argv[2]).read_bytes()) == source
PY
target lsinitramfs /boot/initrd.img-6.18.63-t736-armbian | grep -x init
relocations=$(target env LD_LIBRARY_PATH="$libs" ldd -r "$player" 2>&1)
if grep -Ei 'not found|undefined symbol' <<<"$relocations"; then exit 1; fi
target env LD_LIBRARY_PATH="$libs" "$player" -hide_banner -h full 2>&1 | grep -F -- '-wait_video_start'
target gst-inspect-1.0 --version
bash "$(dirname "$0")/verify_atlasa1_resolute_media.sh" "$root" "$release"
echo "AtlasA1 Ubuntu userspace checks passed"
