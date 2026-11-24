#!/usr/bin/env bash
# Enter the official Armbian menus with AtlasA1 board support installed.
set -euo pipefail
recipe=$(cd "$(dirname "$0")" && pwd -P)
cache=${ATLAS_DOWNLOAD_CACHE:-$HOME/.cache/atlasa1}
framework=${ATLAS_ARMBIAN_DIR:-$recipe/output/armbian}
for command in python3 git curl zstd; do
    if ! command -v "$command" >/dev/null; then
        sudo apt-get update >&2
        sudo apt-get install -y python3 git curl zstd ca-certificates >&2
        break
    fi
done
if [[ ! -f $framework/lib/single.sh ]]; then
    [[ ! -e $framework ]] || { echo "Not an Armbian checkout: $framework" >&2; exit 2; }
    mkdir -p "$cache" "$(dirname "$framework")"
    exec 9>"$cache/.download.lock"
    flock 9
    python3 "$recipe/tools/fetch_atlasa1_inputs.py" "$recipe/config/clean-build/inputs.lock.json" "$cache" \
        --asset atlasa1-upstream-sources-v2.tar.zst >&2
    staging=$(mktemp -d "$(dirname "$framework")/.armbian.XXXXXXXX")
    tar --no-same-owner -I zstd -xf "$cache/atlasa1-upstream-sources-v2.tar.zst" -C "$staging" \
        --strip-components=2 source-inputs-v1/armbian
    [[ $(git -C "$staging" rev-parse HEAD) == 2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736 ]]
    mkdir -p "$staging/cache/tools"
    tar --no-same-owner -I zstd -xf "$cache/atlasa1-upstream-sources-v2.tar.zst" -C "$staging/cache/tools" \
        --strip-components=2 source-inputs-v1/host-tools
    mv -T "$staging" "$framework"
    flock -u 9
    exec 9>&-
fi
python3 "$recipe/tools/install_atlasa1_armbian.py" "$framework" >&2
cd "$framework"
export PREFER_DOCKER=${PREFER_DOCKER:-no}
exec bash ./compile.sh "$@"
