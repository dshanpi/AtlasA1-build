#!/usr/bin/env bash
# Select the tested GNOME session in a new offline release rootfs.
set -euo pipefail
[[ $EUID == 0 && $# == 2 ]] || { echo 'Usage: ROOTFS WAYLAND_GPU_DEB' >&2; exit 2; }
root=$(realpath -e "$1")
gpu=$(realpath -e "$2")
tools=$(cd "$(dirname "$0")" && pwd)
[[ $root != / && ! -s $root/etc/machine-id ]]
[[ $(dpkg-deb -f "$gpu" Package) == atlasa1-img-wayland ]]
[[ $(dpkg-deb -f "$gpu" Version) == 24.2.6603887-3 ]]
# Dependencies are installed by the official GNOME rootfs stage.
pkg=$(mktemp "$root/var/tmp/atlasa1-wayland.XXXXXXXX.deb")
trap 'rm -f -- "$pkg"' EXIT
install -m644 "$gpu" "$pkg"
chroot "$root" dpkg -i "${pkg#"$root"}"
bash "$tools/stage_atlasa1_gnome_wayland.sh" "$root"
install -d "$root/var/lib/AccountsService/users" "$root/etc/gdm3"
cat > "$root/var/lib/AccountsService/users/t736" <<'EOF'
[User]
Session=atlasa1-gnome
XSession=atlasa1-gnome
SessionType=wayland
SystemAccount=false
EOF
chmod 600 "$root/var/lib/AccountsService/users/t736"
cat > "$root/etc/gdm3/custom.conf" <<'EOF'
[daemon]
WaylandEnable=true
AutomaticLoginEnable=false
DefaultSession=atlasa1-gnome.desktop
EOF
printf '/usr/sbin/gdm3\n' > "$root/etc/X11/default-display-manager"
ln -sfn /usr/lib/systemd/system/gdm.service "$root/etc/systemd/system/display-manager.service"
cat > "$root/usr/share/glib-2.0/schemas/99_atlasa1.gschema.override" <<'EOF'
[org.gnome.desktop.session]
idle-delay=uint32 0
[org.gnome.desktop.screensaver]
lock-enabled=false
[org.gnome.settings-daemon.plugins.power]
sleep-inactive-ac-type='nothing'
EOF
chroot "$root" glib-compile-schemas /usr/share/glib-2.0/schemas
chroot "$root" apt-get check
chroot "$root" dpkg-query -W -f='${binary:Package}\t${Version}\n' > "$root/usr/share/doc/atlasa1/installed-packages.tsv"
test -x "$root/usr/libexec/mutter-x11-frames.atlasa1-real"
test -r "$root/opt/atlasa1-firefox/lib/browser-panel-enabled"
