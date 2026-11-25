# SPDX-License-Identifier: GPL-2.0-only
# AtlasA1 hooks for the official Armbian build framework.

function atlasa1_acquire_build_lock() {
    [[ ${CONFIG_DEFS_ONLY:-no} != yes ]] || return 0
    [[ ${ATL_BUILD_LOCK_HELD:-no} != yes ]] || return 0
    exec {ATL_BUILD_LOCK_FD}>"${SRC}/.atlasa1-build.lock"
    flock -n "$ATL_BUILD_LOCK_FD" || exit_with_error \
        'Another AtlasA1 build is running in this directory. Wait for it to finish or use a separate checkout.'
    declare -g ATL_BUILD_LOCK_HELD=yes
}

function post_family_config__atlasa1() {
    atlasa1_acquire_build_lock
    declare -g ATL_NAME="AtlasA1"
    declare -g ATL_RECIPE="${USERPATCHES_PATH}/atlasa1-release"
    [[ -f "$ATL_RECIPE/tools/prepare_atlasa1_native_inputs.py" ]] || exit_with_error 'Install the AtlasA1 recipe first.'
    declare -g ATL_CACHE="${SRC}/cache/atlasa1"
    local input_identity
    input_identity=$(sha256sum "$ATL_RECIPE/config/clean-build/inputs.lock.json")
    # Offline builds skip host_dependencies_ready, but still need the cached input path.
    declare -g ATL_INPUTS="$ATL_CACHE/inputs-${input_identity:0:16}"
    declare -g ATL_IDENTITY
    ATL_IDENTITY=$(python3 "$ATL_RECIPE/tools/prepare_atlasa1_native_sources.py" --identity)
    declare -g ATL_SOURCES="$ATL_CACHE/sources-${ATL_IDENTITY:0:16}"
    KERNELSOURCE="$ATL_SOURCES/linux"
    BOOTSOURCE="$ATL_SOURCES/u-boot"
    UBOOT_HASH_EXTRA=$(python3 "$ATL_RECIPE/tools/hash_atlasa1_native_recipe.py" boot)
    PACKAGE_LIST_FAMILY+=" initramfs-tools python3 plymouth fonts-ubuntu"
    if [[ ${BUILD_DESKTOP:-no} == yes ]]; then
        PACKAGE_LIST_FAMILY+=" ffmpeg gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad libsdl2-2.0-0 libdrm2 libgbm1"
    fi
}

function extension_prepare_config__atlasa1() {
    [[ -z ${RELEASE:-} || $RELEASE == resolute ]] || exit_with_error 'AtlasA1 currently supports RELEASE=resolute.'
    [[ ${ROOTFS_TYPE:-ext4} == ext4 ]] || exit_with_error 'AtlasA1 requires ext4.'
    [[ ${BUILD_DESKTOP:-no} != yes || ${DESKTOP_ENVIRONMENT:-} == gnome || ${DESKTOP_ENVIRONMENT:-} == xfce ]] ||
        exit_with_error 'AtlasA1 supports GNOME, Xfce, or a console image.'
    [[ ${CRYPTROOT_ENABLE:-no} != yes && ${BOOTSIZE:-0} == 0 ]] || exit_with_error 'AtlasA1 uses its fixed eMMC boot layout.'
}

function add_host_dependencies__atlasa1() {
    EXTRA_BUILD_DEPS+=(zstd python3 meson ninja-build pkg-config gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
        gcc-arm-linux-gnueabi libncurses-dev libssl-dev libelf-dev device-tree-compiler rsync)
}

function host_dependencies_ready__atlasa1() {
    mkdir -p "$ATL_CACHE"
    local cache="${ATLAS_DOWNLOAD_CACHE:-${SUDO_USER:+/home/$SUDO_USER/}.cache/atlasa1}"
    [[ -n ${SUDO_USER:-} ]] || cache="${ATLAS_DOWNLOAD_CACHE:-$HOME/.cache/atlasa1}"
    run_host_command_logged python3 "$ATL_RECIPE/tools/prepare_atlasa1_native_inputs.py" \
        --cache "$cache" --work "$ATL_CACHE" --result "$ATL_CACHE/inputs.path"
    declare -g ATL_INPUTS
    ATL_INPUTS=$(cat "$ATL_CACHE/inputs.path")
    run_host_command_logged python3 "$ATL_RECIPE/tools/prepare_atlasa1_native_sources.py" \
        --inputs "$ATL_INPUTS" --work "$ATL_CACHE" --result "$ATL_CACHE/sources.path"
    [[ $(cat "$ATL_CACHE/sources.path") == "$ATL_SOURCES" ]] || exit_with_error 'AtlasA1 source identity differs.'
    # Populate Armbian's ordinary worktree cache from the verified local source.
    local bare="$SRC/cache/git-bare/shallow-kernel-6.18"
    if [[ ! -d "$bare/.git" ]]; then
        run_host_command_logged git clone --no-checkout "$KERNELSOURCE" "$bare"
        run_host_command_logged git -C "$bare" branch master atlasa1-v47
        touch "$bare/.git/armbian-bare-tree-done"
    fi
}

function pre_package_kernel_image__atlasa1() {
    [[ ${KERNEL_COMPILER:-} != clang ]] || exit_with_error 'AtlasA1 PowerVR currently requires GCC.'
    run_host_command_logged env JOBS="${CTHREADS#-j}" bash "$ATL_RECIPE/tools/build_atlasa1_native_pvr.sh" \
        "$ATL_SOURCES/pvr" "$kernel_work_dir" "${tmp_kernel_install_dirs[INSTALL_MOD_PATH]}" "$KERNEL_COMPILER"
}

function artifact_kernel_version_parts__atlasa1() {
    local identity
    identity=$(python3 "$ATL_RECIPE/tools/hash_atlasa1_native_recipe.py" kernel)
    artifact_version_parts["ATL"]="${identity:0:12}"
    artifact_version_part_order+=("0085-ATL")
}

function post_uboot_custom_postprocess__atlasa1() {
    local work
    work=$(mktemp -d "$ATL_CACHE/boot.XXXXXXXX")
    local sources="$ATL_INPUTS/source-inputs-v1" sdk="$ATL_INPUTS/inputs"
    run_host_command_logged python3 "$ATL_RECIPE/tools/build_atlasa1_release_boot.py" \
        --work "$work/build" --uboot-archive "$sources/u-boot.tar.gz" --tfa-archive "$sources/tf-a.tar.gz" \
        --ddr-library "$sdk/brandy/dramlib/sun60iw2p1/spl_libdram/libdram" --uboot-binary "$PWD/u-boot.bin"
    cp "$work/build/payload/emmc-spl.bin" atlasa1-spl.bin
    cp "$work/build/payload/boot-package.bin" atlasa1-package.bin
    cp "$work/build/payload/boot-manifest.json" atlasa1-boot.json
    cp "$ATL_RECIPE/tools/atlasa1_native_image.py" atlasa1-image.py
}

function pre_prepare_partitions__atlasa1() {
    mkopts[ext4]='-q -m 1 -b 4096 -I 256 -O none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum'
}

function prepare_image_size__atlasa1() {
    FIXED_IMAGE_SIZE=${FIXED_IMAGE_SIZE:-8192}
    [[ $FIXED_IMAGE_SIZE == 8192 ]] || exit_with_error 'AtlasA1 currently requires FIXED_IMAGE_SIZE=8192.'
    (( rootfs_size < 7000 )) || exit_with_error 'Selected software does not fit the AtlasA1 root partition.'
    USE_HOOK_FOR_PARTITION=yes
    rootpart=4
    sfdisk_version_num=0
}

function create_partition_table__atlasa1() {
    run_host_command_logged python3 "$ATL_RECIPE/tools/atlasa1_native_image.py" partition --image "${SDCARD}.raw"
}

function post_repo_customize_image__atlasa1() {
    [[ -f "$ATL_INPUTS/verified-inputs.json" ]] || exit_with_error 'AtlasA1 inputs are missing. Run once online to prepare them.'
    run_host_command_logged bash "$ATL_RECIPE/tools/configure_atlasa1_native_rootfs.sh" "$SDCARD" \
        "$ATL_INPUTS" "$ATL_CACHE" "${BUILD_DESKTOP:-no}" "${DESKTOP_ENVIRONMENT:-console}"
}

function pre_umount_final_image__atlasa1() {
    run_host_command_logged python3 "$ATL_RECIPE/tools/atlasa1_native_image.py" boot-files --root "$MOUNT"
}

function post_build_image__atlasa1() {
    run_host_command_logged python3 "$ATL_RECIPE/tools/atlasa1_native_image.py" verify --image "$FINAL_IMAGE_FILE"
}
