#!/usr/bin/env bash
# Install board services into the rootfs created by official Armbian.
set -euo pipefail
[[ $# == 5 && $EUID == 0 ]] || { echo 'Usage: ROOTFS INPUTS CACHE BUILD_DESKTOP DESKTOP' >&2; exit 2; }
root=$(realpath -e "$1")
inputs=$(realpath -e "$2")
cache=$(realpath -e "$3")
desktop_enabled=$4
desktop=$5
[[ $root != / ]]
tools=$(cd "$(dirname "$0")" && pwd)
target() { chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive LC_ALL=C "$@"; }
grep -qx 'VERSION_ID="26.04"' "$root/usr/lib/os-release"
mapfile -t releases < <(find "$root/usr/lib/modules" -mindepth 1 -maxdepth 1 -type d -name '*-current-atlasa1' -printf '%f\n')
[[ ${#releases[@]} == 1 ]]
release=${releases[0]}
pvr="$root/usr/lib/modules/$release/extra/pvrsrvkm.ko"
[[ $(modinfo -F vermagic "$pvr") == "$release "* ]]
install -d "$root/etc/initramfs-tools/conf.d" "$root/etc/systemd/system" "$root/usr/share/doc/atlasa1"
printf 'MODULES=list\nCOMPRESS=gzip\n' > "$root/etc/initramfs-tools/conf.d/atlas-emmc"
printf 'RESUME=none\n' > "$root/etc/initramfs-tools/conf.d/resume"
install -Dm755 "$tools/../config/initramfs/wait-for-root" "$root/usr/lib/atlasa1/wait-for-root"
install -Dm755 "$tools/../config/initramfs/atlasa1-root-wait" "$root/etc/initramfs-tools/hooks/atlasa1-root-wait"
install -Dm644 "$tools/../config/initramfs/50-atlasa1-boot-status.conf" "$root/etc/systemd/system.conf.d/50-atlasa1-boot-status.conf"
ln -sfn /dev/null "$root/etc/systemd/system/armbian-resize-filesystem.service"
if ! target id t736 >/dev/null 2>&1; then target useradd -m -U -s /bin/bash t736; fi
target usermod -aG sudo,video,audio,render,input t736
printf 'root:1234\nt736:1234\n' | target chpasswd
target chage -d 0 root
if [[ $desktop_enabled == yes ]]; then
    work=$(mktemp -d "$cache/media.XXXXXXXX")
    bash "$tools/build_atlasa1_native_media.sh" "$inputs" "$work/components" "$pvr" "$release" "$desktop"
    components="$work/components"
    pkg=$(mktemp -d "$root/var/tmp/atlasa1-packages.XXXXXXXX")
    trap 'rm -rf -- "$pkg"' EXIT
    install -m644 "$components/vendor/t736-img-userspace-candidate_24.2.6603887-2_arm64.deb" "$pkg/"
    install -m644 "$components/player/atlasa1-player_0.1-6~resolute1_arm64.deb" "$pkg/"
    install -m644 "$components/firefox/atlasa1-firefox-cedar_8.0.1-1.resolute1_arm64.deb" "$pkg/"
    packages=()
    for deb in "$pkg/"*.deb; do packages+=("${deb#"$root"}"); done
    target apt-get -y --no-install-recommends install plymouth-themes "${packages[@]}"
    case $(target dpkg-query -W -f='${Version}' firefox) in
        *snap*) echo 'AtlasA1 requires the Firefox Debian package from Armbian.' >&2; exit 1 ;;
    esac
    test -r "$root/usr/lib/firefox/libxul.so"
    target getent group t736-cedar >/dev/null || target groupadd --system t736-cedar
    target id t736-cedar >/dev/null 2>&1 || target useradd -r -g t736-cedar -G t736 -d /nonexistent -s /usr/sbin/nologin t736-cedar
    rsync -a --chown=root:root "$components/overlay/" "$root/"
    target depmod -a "$release"
    target systemctl --no-reload enable t736-cedar.socket
    if [[ $desktop == gnome ]]; then
        # The helper checks this before installing the GNOME session.
        truncate -s 0 "$root/etc/machine-id"
        bash "$tools/configure_atlasa1_gnome_release.sh" "$root" "$components/wayland/atlasa1-img-wayland_24.2.6603887-3_arm64.deb"
    fi
    bash "$tools/stage_atlasa1_plymouth.sh" "$root"
fi
target systemctl --no-reload enable serial-getty@ttyS0.service
install -d "$root/etc/systemd/system/smartmontools.service.d" "$root/etc/systemd/system/run-rpc_pipefs.mount.d"
printf '[Service]\nExecStart=\nExecStart=/usr/sbin/smartd -n --quit=never $smartd_opts\n' \
    > "$root/etc/systemd/system/smartmontools.service.d/atlasa1-emmc.conf"
printf '[Unit]\nConditionPathExists=|/sys/module/sunrpc\nConditionPathExistsGlob=|/usr/lib/modules/%%v/kernel/net/sunrpc/sunrpc.ko*\n' \
    > "$root/etc/systemd/system/run-rpc_pipefs.mount.d/atlasa1-sunrpc.conf"
target dpkg --audit > "$cache/dpkg-audit.txt"
[[ ! -s $cache/dpkg-audit.txt ]]
target apt-get check
install -d "$root/usr/share/doc/atlasa1"
target dpkg-query -W -f='${binary:Package}\t${Version}\n' > "$root/usr/share/doc/atlasa1/installed-packages.tsv"
truncate -s 0 "$root/etc/machine-id"
rm -f "$root"/etc/ssh/ssh_host_{rsa,ecdsa,ed25519}_key{,.pub}
