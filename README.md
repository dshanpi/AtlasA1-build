# AtlasA1-build

AtlasA1 / T736 的 Armbian Ubuntu 26.04 LTS（arm64）eMMC 镜像。使用 `--gnome-v47` 构建 GNOME Wayland / GDM 版本，包含 PowerVR、Cedar、Firefox 硬解入口和原生播放器。旧版 Xfce 配方保留。镜像下载、校验和与逐项验收范围见 [Releases](https://github.com/dshanpi/AtlasA1-build/releases)。

新主机构建入口为 `bash build.sh`，按版本清单自动获取所需输入，不再要求用户准备 Tina SDK。2026-11-23 已通过断网容器内的启动链、内核、GPU、多媒体与 Armbian BSP 源码重建；完整镜像仍在验收，状态和使用条件见 [新主机构建](docs/FRESH_HOST_BUILD.md)。原有手工配方与 [单文件补丁](patches/atlasa1-resolute-armbian.patch) 保留。

板级源码按组件备份，可分别检查启动链、内核与播放器。本仓库还保留原有通用 Armbian 板级补丁及此前 Debian 开发镜像的集成记录。[U-Boot / SPL / TF-A](https://github.com/dshanpi/AtlasA1-uboot) · [Linux / PowerVR](https://github.com/dshanpi/AtlasA1-linux) · [Cedar / 播放器](https://github.com/dshanpi/AtlasA1-media) · [早期 Armbian 适配](docs/ARMBIAN_REBUILD.md)

主分支包含双格式 Cedar 服务和适用于 Firefox 160 的 FFmpeg 8.0.1 适配。构建时追加 `--pcie-v34` 可选择已在 J58 空槽实测的 PCIe 根端口、SDIO 主控和蓝牙 UART。无线芯片的 SDIO 枚举和蓝牙 HCI 响应仍待打通。[浏览器实测](evidence/atlasa1-firefox160-ffmpeg8-20261118.json) · [4K HEVC 与 1080p H.264 切换](evidence/atlasa1-cedar-format-switch-20261118.json) · [v34 整盘打包检查](evidence/atlasa1-v34-image-integration-20261118.json)

GNOME 50 / Wayland v47 完整镜像已发布，并于 2026-11-22 完成 eMMC 整盘写入、8 GiB SHA-256 回读和断电启动。PowerVR WebRender 与 Cedar 硬解已接通，但不能宣称浏览器 1080p60 或全链路零丢帧通过。主分支另修复首次显示配置与自动校时；已发布 RC1 镜像保持原始字节，安装后修复和实测限制见 [发行记录](https://github.com/dshanpi/AtlasA1-build/releases/tag/v2026.11.21-ubuntu26.04-gnome-v47-rc1)。
