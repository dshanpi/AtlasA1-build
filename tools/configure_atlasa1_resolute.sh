#!/bin/bash
# Install the AtlasA1 board support into a fresh official Armbian Resolute desktop rootfs.
set -euo pipefail
if [[ ${1:-} != --private-mounts ]]; then
    exec unshare --mount --propagation private bash "$0" --private-mounts "$@"
fi
shift
[[ ( $# == 6 || $# == 7 ) && $(id -u) == 0 ]] || { echo "Usage (root): $0 ROOTFS KERNEL_DEB PVR_KO MEDIA_OVERLAY GPU_DEB PLAYER_DEB [FIREFOX_CEDAR_DEB]" >&2; exit 2; }
root=$(realpath -e "$1")
kernel=$(realpath -e "$2")
pvr=$(realpath -e "$3")
overlay=$(realpath -e "$4")
gpu=$(realpath -e "$5")
player=$(realpath -e "$6")
board_debs=("$kernel" "$gpu" "$player")
if [[ $# == 7 ]]; then
    firefox=$(realpath -e "$7")
    [[ $(dpkg-deb -f "$firefox" Package) == atlasa1-firefox-cedar ]]
    case $(dpkg-deb -f "$firefox" Version) in 8.0.1-1~resolute1|8.0.1-1~resolute1+panel2) ;; *) exit 2 ;; esac
    board_debs+=("$firefox")
fi
[[ "$root" != / && "$overlay" != / && "$root" != "$overlay" ]]
for sub in dev proc sys run; do
    if [[ -L "$root/$sub" ]] || mountpoint -q "$root/$sub"; then
        echo "target $sub is a symlink or already mounted" >&2
        exit 2
    fi
done
grep -qx 'VERSION_ID="26.04"' "$root/usr/lib/os-release"
grep -q t736-mainline "$root/etc/armbian-release"
package=$(dpkg-deb -f "$kernel" Package)
case "$package" in
    linux-image-6.18.63-t736-media-v30) board_dtb=t736-gpu-candidate.dtb ;;
    linux-image-6.18.63-t736-hw-v34|linux-image-6.18.63-t736-gnome-v47) board_dtb=t736-pcie-v32.dtb ;;
    *) echo "Unsupported AtlasA1 kernel package: $package" >&2; exit 2 ;;
esac
release=${package#linux-image-}
[[ $(dpkg-deb -f "$player" Package) == atlasa1-player ]]
[[ $(modinfo -F vermagic "$pvr" | cut -d' ' -f1) == "$release" ]]
work=$(mktemp -d)
pkg=$(mktemp -d "$root/var/tmp/atlas-packages.XXXXXXXX")
chmod 0755 "$pkg"
cleanup() {
    for sub in run sys proc dev; do
        if mountpoint -q "$root/$sub"; then umount -R "$root/$sub"; fi
    done
    for name in etc/resolv.conf usr/sbin/policy-rc.d; do
        if [[ -e "$work/$(basename "$name").changed" ]]; then
            rm -f "$root/$name"
            if [[ -e "$work/$(basename "$name")" || -L "$work/$(basename "$name")" ]]; then
                mv -T "$work/$(basename "$name")" "$root/$name"
            fi
        fi
    done
    rm -rf -- "$pkg" "$work"
}
trap cleanup EXIT
for sub in dev proc sys run; do
    mkdir -p "$root/$sub"
done
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs -o ro sysfs "$root/sys"
mount -t tmpfs -o nosuid,nodev tmpfs "$root/run"
for name in etc/resolv.conf usr/sbin/policy-rc.d; do
    if [[ -e "$root/$name" || -L "$root/$name" ]]; then mv -T "$root/$name" "$work/$(basename "$name")"; fi
    touch "$work/$(basename "$name").changed"
done
cp -L /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 0755 "$root/usr/sbin/policy-rc.d"
target() { chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive LC_ALL=C "$@"; }

install -d "$root/etc/initramfs-tools/conf.d"
printf 'MODULES=list\nCOMPRESS=gzip\n' > "$root/etc/initramfs-tools/conf.d/atlas-emmc"
printf 'RESUME=none\n' > "$root/etc/initramfs-tools/conf.d/resume"
printf 'PARTUUID=a0085546-4166-744a-a353-fca9272b8e48 / ext4 defaults,noatime,errors=remount-ro 0 1\n' > "$root/etc/fstab"
if ! target id t736 >/dev/null 2>&1; then target useradd -m -U -s /bin/bash t736; fi
target usermod -aG sudo,video,audio,render,input t736
target getent group t736-cedar >/dev/null || target groupadd --system t736-cedar
target id t736-cedar >/dev/null 2>&1 || target useradd -r -g t736-cedar -G t736 -d /nonexistent -s /usr/sbin/nologin t736-cedar
printf 'root:1234\nt736:1234\n' | target chpasswd
# Preserve Armbian's first-login password change for the public root account.
target chage -d 0 root
packages=(initramfs-tools plymouth plymouth-themes fonts-ubuntu ffmpeg gstreamer1.0-tools
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad)
for deb in "${board_debs[@]}"; do
    [[ $(dpkg-deb -f "$deb" Architecture) == arm64 ]]
    install -m 0644 "$deb" "$pkg/"
    packages+=("${pkg#"$root"}/$(basename "$deb")")
done
# A freshly prepared rootfs may already contain every runtime dependency.
if ! target apt-get --print-uris --no-install-recommends --assume-yes install "${packages[@]}" >"$work/uris" 2>&1 ||
    grep -Eq "^'(https?|ftp):" "$work/uris"; then
    target apt-get -o Acquire::Retries=3 -o Acquire::IndexTargets::deb::Contents-deb::DefaultEnabled=false \
        -o Acquire::IndexTargets::deb::Contents-deb-legacy::DefaultEnabled=false \
        -o Acquire::IndexTargets::deb::DEP-11::DefaultEnabled=false -o Acquire::Languages=none update
fi
target apt-get -y --no-install-recommends install "${packages[@]}"
rsync -a --chown=root:root "$overlay/" "$root/"
install -D -m 0644 "$pvr" "$root/lib/modules/$release/extra/pvrsrvkm.ko"
target depmod -a "$release"
target modinfo -k "$release" -F vermagic pvrsrvkm | grep -F "$release "
install -Dm755 "$(dirname "$0")/../config/initramfs/wait-for-root" "$root/usr/lib/atlasa1/wait-for-root"
install -Dm755 "$(dirname "$0")/../config/initramfs/atlasa1-root-wait" "$root/etc/initramfs-tools/hooks/atlasa1-root-wait"
install -Dm644 "$(dirname "$0")/../config/initramfs/50-atlasa1-boot-status.conf" "$root/etc/systemd/system.conf.d/50-atlasa1-boot-status.conf"
bash "$(dirname "$0")/stage_atlasa1_plymouth.sh" "$root"
install -D -m 0644 "$root/usr/lib/linux-image-$release/allwinner/$board_dtb" \
    "$root/boot/dtb/allwinner/t736-mainline-bringup.dtb"
if [[ -s "$root/boot/initrd.img-$release" ]]; then
    target update-initramfs -u -k "$release"
else
    target update-initramfs -c -k "$release"
fi
python3 "$(dirname "$0")/prepare_atlasa1_boot_kernel.py" \
    "$root/boot/vmlinuz-$release" "$root/boot/vmlinuz-$release.atlasa1.gz"
ln -sfn "vmlinuz-$release.atlasa1.gz" "$root/boot/vmlinuz-6.18.63-t736-armbian"
[[ -s "$root/boot/initrd.img-$release" ]]
ln -sfn "initrd.img-$release" "$root/boot/initrd.img-6.18.63-t736-armbian"
target systemctl --no-reload enable t736-cedar.socket serial-getty@ttyS0.service
target systemctl is-enabled t736-cedar.socket
# eMMC does not expose SMART. Keep the daemon available for add-on drives.
install -d "$root/etc/systemd/system/smartmontools.service.d" "$root/etc/systemd/system/run-rpc_pipefs.mount.d"
printf '[Service]\nExecStart=\nExecStart=/usr/sbin/smartd -n --quit=never $smartd_opts\n' \
    > "$root/etc/systemd/system/smartmontools.service.d/atlasa1-emmc.conf"
# Ubuntu pulls in nfs-common; mount rpc_pipefs only on a kernel with SUNRPC.
printf '[Unit]\nConditionPathExists=|/sys/module/sunrpc\nConditionPathExistsGlob=|/usr/lib/modules/%%v/kernel/net/sunrpc/sunrpc.ko*\n' \
    > "$root/etc/systemd/system/run-rpc_pipefs.mount.d/atlasa1-sunrpc.conf"
target dpkg --audit > "$work/dpkg-audit"
[[ ! -s "$work/dpkg-audit" ]] || { cat "$work/dpkg-audit" >&2; exit 1; }
target apt-get check
target apt-get clean
# Recreate the APT indexes from the configured distribution mirrors after deployment.
find "$root/var/lib/apt/lists" -mindepth 1 -maxdepth 1 ! -name lock -exec rm -rf -- {} +
install -d "$root/usr/share/doc/atlasa1"
target dpkg-query -W -f='${binary:Package}\t${Version}\n' > "$root/usr/share/doc/atlasa1/installed-packages.tsv"
# Generate a distinct machine identity and SSH host keys at first boot.
truncate -s 0 "$root/etc/machine-id"
rm -f "$root"/etc/ssh/ssh_host_{rsa,ecdsa,ed25519}_key{,.pub} "$root/var/lib/systemd/random-seed"
if [[ -d "$root/var/lib/dbus" ]]; then ln -sfn /etc/machine-id "$root/var/lib/dbus/machine-id"; fi
for user_home in "$root/root" "$root"/home/*; do
    [[ ! -f "$user_home/.ssh/authorized_keys" && ! -f "$user_home/.bash_history" ]]
done
