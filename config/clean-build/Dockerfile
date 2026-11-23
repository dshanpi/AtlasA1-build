FROM scratch
# Official Ubuntu 24.04 amd64 OCI filesystem; download and SHA-256 verification
# are handled by the entry script, so Docker Hub access is not required.
ADD ubuntu-24.04-amd64-rootfs.tar.gz /
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc-aarch64-linux-gnu g++-aarch64-linux-gnu gcc-arm-linux-gnueabi \
    binutils-aarch64-linux-gnu binutils-arm-linux-gnueabi python3 python3-venv \
    python3-setuptools git curl wget ca-certificates sudo rsync file patch xz-utils \
    zstd gzip pigz cpio tar unzip zip bc bison flex device-tree-compiler libssl-dev \
    libelf-dev dwarves pkg-config patchelf cmake meson ninja-build autoconf automake \
    libtool libtool-bin gawk gettext jq fakeroot dpkg-dev qemu-user-static \
    binfmt-support arch-test debootstrap mmdebstrap e2fsprogs dosfstools fdisk parted util-linux \
    uuid-runtime locales whiptail dialog apt-utils gnupg psmisc debian-archive-keyring \
    ubuntu-keyring kmod lz4 tree expect pv aria2 openssh-client acl attr \
    && rm -rf /var/lib/apt/lists/*
RUN id ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash -u 1000 ubuntu
RUN printf 'ubuntu ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/atlas-builder \
    && chmod 0440 /etc/sudoers.d/atlas-builder
WORKDIR /work
