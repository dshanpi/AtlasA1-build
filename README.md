# AtlasA1-build

AtlasA1 / T736 的 Armbian Ubuntu 26.04 LTS（arm64）eMMC 镜像。默认桌面是 LightDM + Xfce X11，另含 GNOME / GDM。原生播放器使用 Cedar 解码和 PowerVR GLES。镜像下载、校验和与本版验收范围见 [Releases](https://github.com/dshanpi/AtlasA1-build/releases)。

从官方 Armbian 源码重建时，应用一份发行版补丁，指定已配置的 T736 Tina SDK，然后执行总入口。它会从 SDK 中准备 IMG/Cedar 运行库，获取公开交叉编译依赖，构建固定 LPDDR4x 启动链、Linux 与 PowerVR 内核模块、播放器及 Ubuntu 根文件系统，并打包成完整磁盘镜像。[Ubuntu 26.04 构建步骤](docs/UBUNTU_26_04.md) · [单文件补丁](patches/atlasa1-resolute-armbian.patch)

板级源码按组件备份，可分别检查启动链、内核与播放器。本仓库还保留原有通用 Armbian 板级补丁及此前 Debian 开发镜像的集成记录。[U-Boot / SPL / TF-A](https://github.com/dshanpi/AtlasA1-uboot) · [Linux / PowerVR](https://github.com/dshanpi/AtlasA1-linux) · [Cedar / 播放器](https://github.com/dshanpi/AtlasA1-media) · [早期 Armbian 适配](docs/ARMBIAN_REBUILD.md)
