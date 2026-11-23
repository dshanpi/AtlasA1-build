#!/usr/bin/env bash
# One entry point for a fresh Ubuntu 24.04 amd64 host. No Tina SDK required.
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd -P)
if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash build.sh [NEW_OUTPUT_DIRECTORY]'
    echo 'Requires Ubuntu 24.04 amd64, sudo, Internet, 8 GiB RAM and 35 GiB free disk.'
    echo 'Inputs are SHA-256 locked; compilation runs in an offline container.'
    exit 0
fi
[[ $# -le 1 && $(uname -m) == x86_64 ]] || { echo 'Use an x86_64 Linux host' >&2; exit 2; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo 'Supported host: Ubuntu 24.04 amd64' >&2; exit 2; }
out=$(realpath -m "${1:-$repo/output/clean-gnome}")
[[ ! -e $out ]] || { echo "Output already exists: $out; choose a new directory" >&2; exit 2; }
sudo -v
# A slow asset download must not turn an unattended build into a second sudo
# password prompt. Keep this invocation's sudo timestamp alive, then stop it.
while sleep 60; do sudo -n true || exit; done &
sudo_keepalive=$!
trap 'kill "$sudo_keepalive" 2>/dev/null || true' EXIT
if ! command -v docker >/dev/null || ! command -v zstd >/dev/null || ! command -v curl >/dev/null || ! command -v python3 >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends docker.io zstd curl python3 ca-certificates
fi
sudo systemctl start docker
cache=${ATLAS_DOWNLOAD_CACHE:-$HOME/.cache/atlasa1}
mkdir -p "$cache" "$(dirname "$out")"
exec 9>"$cache/.download.lock"
flock 9
python3 "$repo/tools/fetch_atlasa1_inputs.py" "$repo/config/clean-build/inputs.lock.json" "$cache"
builder=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["builder_image_id"])' "$repo/config/clean-build/inputs.lock.json")
if ! sudo docker image inspect "$builder" >/dev/null 2>&1; then
    zstd -dc "$cache/atlasa1-builder-v3.tar.zst" | sudo docker load
fi
sudo docker image inspect "$builder" >/dev/null
flock -u 9
available=$(df --output=avail -B1 "$(dirname "$out")" | tail -1)
(( available >= 35 * 1024 * 1024 * 1024 )) || { echo 'Need at least 35 GiB free for a fresh build' >&2; exit 1; }
mkdir -- "$out"
cp "$repo/config/clean-build/inputs.lock.json" "$out/"
git -C "$repo" rev-parse HEAD > "$out/recipe-commit.txt" 2>/dev/null || printf 'patch export\n' > "$out/recipe-commit.txt"
sudo docker run --rm --privileged --network none --hostname atlas-builder \
    --mount "type=bind,src=$(realpath "$cache"),dst=/assets,readonly" \
    --mount "type=bind,src=$repo,dst=/recipe,readonly" \
    --mount "type=bind,src=$out,dst=/work" \
    -e "JOBS=${JOBS:-6}" "$builder" bash /recipe/tools/run_atlasa1_clean_container.sh \
    2>&1 | tee "$out/build.log"
sudo chown -R "$(id -u):$(id -g)" "$out/image"
printf '\nImage and checksums: %s/image\n' "$out"
