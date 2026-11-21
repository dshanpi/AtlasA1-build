# AtlasA1-build

AtlasA1 / T736 的 Armbian Ubuntu 26.04 LTS（arm64）eMMC 镜像。使用 `--gnome-v47` 构建 GNOME Wayland / GDM 版本，包含 PowerVR、Cedar、Firefox 硬解入口和原生播放器。旧版 Xfce 配方保留。镜像下载、校验和与逐项验收范围见 [Releases](https://github.com/dshanpi/AtlasA1-build/releases)。

从官方 Armbian 源码重建时，应用一份发行版补丁，指定已配置的 T736 Tina SDK，然后执行总入口。它会从 SDK 中准备 IMG/Cedar 运行库，获取公开交叉编译依赖，构建固定 LPDDR4x 启动链、Linux 与 PowerVR 内核模块、播放器及 Ubuntu 根文件系统，并打包成完整磁盘镜像。[Ubuntu 26.04 构建步骤](docs/UBUNTU_26_04.md) · [单文件补丁](patches/atlasa1-resolute-armbian.patch)

板级源码按组件备份，可分别检查启动链、内核与播放器。本仓库还保留原有通用 Armbian 板级补丁及此前 Debian 开发镜像的集成记录。[U-Boot / SPL / TF-A](https://github.com/dshanpi/AtlasA1-uboot) · [Linux / PowerVR](https://github.com/dshanpi/AtlasA1-linux) · [Cedar / 播放器](https://github.com/dshanpi/AtlasA1-media) · [早期 Armbian 适配](docs/ARMBIAN_REBUILD.md)

主分支包含双格式 Cedar 服务和适用于 Firefox 160 的 FFmpeg 8.0.1 适配。构建时追加 `--pcie-v34` 可选择已在 J58 空槽实测的 PCIe 根端口、SDIO 主控和蓝牙 UART。无线芯片的 SDIO 枚举和蓝牙 HCI 响应仍待打通。[浏览器实测](evidence/atlasa1-firefox160-ffmpeg8-20261118.json) · [4K HEVC 与 1080p H.264 切换](evidence/atlasa1-cedar-format-switch-20261118.json) · [v34 整盘打包检查](evidence/atlasa1-v34-image-integration-20261118.json)

GNOME 50 / Wayland 候选已接通 PowerVR 和 Firefox 硬件 WebRender，恢复八核调度后用户确认桌面可以正常使用。实板已设置并验证 GNOME 冷启动；HEVC 4K30 片源在 1080p 屏上硬件缩放播放通过，1080p60 仍有少量丢帧。GNOME 新整盘镜像尚未发布，现有 Release 默认 Xfce。[候选构建、实测与限制](docs/GNOME_WAYLAND.md)
