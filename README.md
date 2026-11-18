# AtlasA1-build

Armbian build integration for the DshanPI AtlasA1 (Allwinner T736).

Apply `patches/t736-armbian-open-source.patch` to the official Armbian revision in `config/sources.lock.json`, then select `BOARD=t736-mainline`. The patch supplies the board definition, Linux and U-Boot patches, kernel configuration, display defaults, and a board-side media test. The framework fetches its pinned upstream sources.

The accelerated GNOME image also needs the board's matching LPDDR4x training stage, GPU module and userspace, and Cedar runtime. The build hook verifies the supplied archive, installs the desktop dependencies, indexes the target kernel modules and enables the decoder socket. A clean public-patch build has yet to reproduce the complete image running on the board. [Build commands and matching inputs](docs/ARMBIAN_REBUILD.md)

Cedar integration and playback measurements are maintained in [AtlasA1-media](https://github.com/dshanpi/AtlasA1-media). Kernel candidates are maintained in [AtlasA1-linux](https://github.com/dshanpi/AtlasA1-linux).
