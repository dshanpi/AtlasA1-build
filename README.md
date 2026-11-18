# AtlasA1-build

Public Armbian integration for the T736 Aurora/AtlasA1 board.

## Build

1. Clone the pinned Armbian framework listed in `config/sources.lock.json`.
2. Apply `patches/t736-armbian-open-source.patch` at the framework root, or copy the checked-in `userpatches/` tree to `USERPATCHES_PATH`.
3. Fetch the matching Linux and U-Boot sources and apply the patches from the AtlasA1-linux and AtlasA1-uboot repositories.
4. Run the commands in `docs/ARMBIAN_REBUILD.md` on a case-sensitive Linux build host.

The build repository contains source and configuration only. It does not contain Tina, DDR, GPU, or codec binaries. Those authorised inputs must be supplied separately and checked against the recorded hashes before a board image is assembled.

Media support is maintained in AtlasA1-media. Its public source and patches can be built independently, while the licensed runtime remains an external input.
