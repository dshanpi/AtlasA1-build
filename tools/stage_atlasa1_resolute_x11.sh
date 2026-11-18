#!/usr/bin/env bash
# Add the LightDM/Xfce profile to a freshly prepared board overlay.
set -euo pipefail
root=$(realpath -e "${1:?expected the media overlay directory}")
[[ $root != / && -f "$root/etc/modules-load.d/atlasa1-pvr.conf" ]]
project=$(cd "$(dirname "$0")/.." && pwd)
profile="$project/config/gpu-v10"
display="$project/userpatches/config/t736-display"
install -Dm644 "$profile/20-t736-modesetting-1080p.conf" "$root/etc/X11/xorg.conf.d/20-atlasa1.conf"
install -Dm644 "$display/30-t736-x11-blank.conf" "$root/etc/X11/xorg.conf.d/30-t736-x11-blank.conf"
install -Dm755 "$profile/t736-hdmi-session-init.sh" "$root/usr/local/sbin/t736-hdmi-session-init"
install -d "$root/usr/local/bin" "$root/etc/lightdm/lightdm.conf.d" "$root/usr/share/xsessions"
cat > "$root/usr/local/bin/atlasa1-x11-run" <<'EOF'
#!/bin/sh
set -eu
case "${1:-}" in
    xorg) shift; set -- /usr/lib/xorg/Xorg "$@";;
    xfce) shift; set -- /usr/bin/startxfce4 "$@";;
    *) exit 2;;
esac
ddk=/opt/t736-img-ddk-24.2-x11
if [ -d /sys/module/pvrsrvkm ] && [ -r "$ddk/runtime-gles/libEGL.so.1" ]; then
    . "$ddk/session.env"
    export GDK_BACKEND=x11 GDK_DISABLE=gl-api,glx,vulkan GSK_RENDERER=gl
fi
exec "$@"
EOF
cat > "$root/usr/local/sbin/atlasa1-x11-display" <<'EOF'
#!/bin/sh
# LightDM runs this once on its X server before the greeter starts.
xset s off || :
xset -dpms || :
exec /usr/local/sbin/t736-hdmi-session-init
EOF
chmod 0755 "$root/usr/local/bin/atlasa1-x11-run" "$root/usr/local/sbin/atlasa1-x11-display"
cat > "$root/etc/lightdm/lightdm.conf.d/90-atlasa1-x11.conf" <<'EOF'
[Seat:*]
user-session=atlasa1-xfce
xserver-command=/usr/local/bin/atlasa1-x11-run xorg
display-setup-script=/usr/local/sbin/atlasa1-x11-display
EOF
cat > "$root/usr/share/xsessions/atlasa1-xfce.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=AtlasA1 Xfce
Exec=/usr/local/bin/atlasa1-x11-run xfce
TryExec=/usr/bin/startxfce4
DesktopNames=XFCE
EOF
