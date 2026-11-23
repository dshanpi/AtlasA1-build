#!/usr/bin/env bash
# Build the official Armbian BSP and base-files with frozen upstream inputs.
set -euo pipefail
[[ $# == 3 ]] || { echo 'Usage: SOURCE_CACHE NEW_WORK RECIPE_ROOT' >&2; exit 2; }
sources=$(realpath -e "$1")
work=$(realpath -m "$2")
recipe=$(realpath -e "$3")
mkdir -- "$work"
cp -a "$sources/armbian/." "$work/"
git -C "$work" apply --check "$recipe/patches/t736-armbian-open-source.patch"
git -C "$work" apply "$recipe/patches/t736-armbian-open-source.patch"
mkdir -p "$work/cache/tools"
cp -a "$sources/host-tools/." "$work/cache/tools/"
# Keep the official base-files transformation. Replace only discovery of the
# latest Ubuntu package with our immutable, SHA-verified upstream package.
python3 - "$work" "$sources" <<'PY'
from pathlib import Path
import sys
work, sources = map(Path, sys.argv[1:])
p = work / 'lib/functions/artifacts/artifact-armbian-base-files.sh'
text = p.read_text()
anchor = '\tsleep_seconds="15" do_with_retries 10 apt_find_upstream_package_version_and_download_url "base-files"'
assert text.count(anchor) == 1
replacement = '''\tfound_package_version=14ubuntu6
\tfound_package_filename=base-files_14ubuntu6_arm64.deb
\tfound_package_down_url="file://''' + str(sources) + '''/base-files_14ubuntu6_arm64.deb"'''
p.write_text(text.replace(anchor, replacement))
PY
cd "$work"
params=(ARCH=arm64 RELEASE=resolute BOARD=t736-mainline BRANCH=current EXPERT=yes
    BUILD_DESKTOP=no OFFLINE_WORK=yes ARTIFACT_IGNORE_CACHE=yes MANAGE_ACNG=no
    SHARE_LOG=no SKIP_EXTERNAL_TOOLCHAINS=yes IGNORE_UPDATES=yes PREFER_DOCKER=no REVISION=26.11.0-trunk)
for package in armbian-bsp-cli armbian-base-files; do
    bash compile.sh "$package" "${params[@]}"
done
