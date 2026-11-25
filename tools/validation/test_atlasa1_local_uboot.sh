#!/usr/bin/env bash
# Verify source-cache selection without network access.
set -euo pipefail
framework=$(realpath "${1:?Pass the patched Armbian source directory}")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export SRC="$work/framework"
BOOTSOURCE="$work/board-source"
BOOTSOURCEDIR=u-boot-worktree/atlasa1-v47
OFFLINE_WORK=no
GIT_ORAS_TARBALLS_SHALLOW_BASE_REF=unused.example
git init -q -b atlasa1-v47 "$BOOTSOURCE"
git -C "$BOOTSOURCE" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m initial
expected=$(git -C "$BOOTSOURCE" rev-parse HEAD)
function run_host_command_logged() { "$@"; }
function git_ensure_safe_directory() { :; }
function display_alert() { printf '%s\n' "$*"; }
function git_oras_tree_prepare_from_gitball() {
    [[ $BOOTSOURCE == https://example.invalid/upstream.git ]]
    remote_called=yes
}
source "$framework/lib/functions/compilation/uboot-git-oras.sh"
for attempt in first repeated; do
    uboot_prepare_bare_repo
    [[ $uboot_git_bare_tree == "$SRC/cache/git-bare/u-boot-local" ]]
    [[ $(git -C "$uboot_git_bare_tree" rev-parse master) == "$expected" ]]
    [[ $(git -C "$uboot_git_bare_tree" rev-parse atlasa1-v47) == "$expected" ]]
    [[ ! -e "$uboot_git_bare_tree/.git/armbian-bare-tree-done-oras" ]]
done
git -C "$uboot_git_bare_tree" worktree add --no-checkout "$work/checkout" master
git -C "$work/checkout" checkout --detach atlasa1-v47
[[ $(git -C "$work/checkout" rev-parse HEAD) == "$expected" ]]
legacy="$SRC/cache/git-bare/u-boot"
git clone -q --no-checkout "$BOOTSOURCE" "$legacy"
git -C "$legacy" worktree add --detach "$SRC/cache/sources/$BOOTSOURCEDIR" HEAD
uboot_prepare_bare_repo
[[ $uboot_git_bare_tree == "$legacy" ]]
[[ $(git -C "$SRC/cache/sources/$BOOTSOURCEDIR" rev-parse HEAD) == "$expected" ]]
BOOTSOURCE=https://example.invalid/upstream.git
remote_called=no
uboot_prepare_bare_repo
[[ $remote_called == yes ]]
[[ $uboot_git_bare_tree == "$SRC/cache/git-bare/u-boot" ]]
echo 'PASS: empty cache, repeated preparation, worktree checkout, legacy worktree reuse, and upstream fallback.'
