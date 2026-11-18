# T736 Armbian 重建入口

在锁定版本的官方 Armbian build 上执行下面的 `git apply` 即可加入公开板级支持。复现实板的 LPDDR4x 启动、PVR 加速桌面和 Cedar 硬解还需要对应的厂家组件，获取与安装要求见下文。[下载公开补丁](../patches/t736-armbian-open-source.patch)

**公开补丁可以用于构建组件。** 完整镜像还缺把官方 Armbian 分区阶段接到实板 GPT 的适配，以及与启动包一致的 U-Boot 构建配置。实板 8 GiB 镜像要求第 4 分区为 rootfs、LBA 16 为 eGON SPL、LBA 24576 为 stage64/TF-A/U-Boot 启动包，还在 LBA 40960 保存 GPT 镜像。通用分区方案在创建镜像前停止。写入函数再次核对主、备、镜像三份 GPT、两个输入、内嵌 U-Boot 与当前构建的一致性，以及目标 loop 绑定的普通镜像文件。[实板镜像打包布局](../tools/pack_t736_source_boot.py) · [Armbian family](../userpatches/config/sources/families/t736-mainline.conf)

```sh
git clone https://github.com/armbian/build.git
cd build
git checkout 2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736
git apply /path/to/t736/mainline/patches/t736-armbian-open-source.patch
./compile.sh kernel BOARD=t736-mainline BRANCH=current RELEASE=trixie EXPERT=yes SHARE_LOG=no
```

这个补丁增加公开的 board/family 配置、Linux/U-Boot 补丁、内核配置和一份板上媒体验收脚本。内核配置打开了 DMA-BUF/CMA、512 MiB 默认 CMA 区、通用 DRM/V4L2 框架、STMMAC/Realtek PHY 依赖，以及 Wi‑Fi/蓝牙公共框架、SDIO/常见 Broadcom/Realtek 驱动和 HCI UART。512 MiB 是 HEVC 1080p/4K 连续 DMA 缓冲的默认预算，启动参数中的 `cma=<size>` 仍会覆盖内核配置，实板验收必须记录 `/proc/meminfo` 的 `CmaTotal`/`CmaFree` 和 dma-heap 分配结果。补丁中的 `userpatches/t736-media-acceptance.py` 只做显式 OMX/GStreamer 测试并输出 JSON，不会把软件回退或插件枚举写成硬件通过。板载无线模块的设备树、电源 GPIO、UART/SDIO 连接仍按 [`docs/WIRELESS.md`](WIRELESS.md) 待确认，不能把“驱动已编译”当成无线已通过。

构建机需要 Linux、aarch64 交叉工具链、QEMU/binfmt 和 Armbian 的依赖。`config/sources.lock.json` 锁定了 Armbian、Linux 和 U-Boot 的期望版本。补丁应用后，媒体验收脚本位于 Armbian checkout 的 `userpatches/t736-media-acceptance.py`，复制到板卡后可直接运行。

如果需要自动校验版本并复制补丁，也可以使用 `tools/build_t736_armbian_image.py`；它是辅助脚本，不是应用 T736 补丁的必需依赖。

## 准备厂家输入

GPU 用户态、PVR 内核模块、Cedar/OMX/WC、匹配固件和 DDR 启动库属于授权厂家输入，公开仓库不分发。将它们放在私有目录或 tar/tar.zst 中，并在根目录放置 `manifest.json`。字段格式见 [`config/t736-vendor-inputs.example.json`](../config/t736-vendor-inputs.example.json)。每个文件必须有相对 payload 路径、绝对 rootfs 目标路径、角色和 SHA256；入口会要求 `gpu_userspace`、`pvr_module`、`codec_backend`、`codec_service`、`device_rules`、`ddr_boot` 和 `boot_package` 输入齐全，hash 不匹配时停止。

完整媒体输入现在还要求浏览器侧桥接和服务配置：`codec_userspace`、`codec_config`、`browser_bridge`、`browser_service`。入口会拒绝只含 Cedar broker/OMX 插件的半成品 manifest，避免把“插件能枚举”误报为 Firefox 硬解完成。设备规则必须保持专用 `t736-cedar` 服务账号的 0600 权限，不能用后置的 `video` 组规则覆盖它。

如果这些私有构建产物已经在本地，可以用 `tools/build_t736_vendor_input.py`
把它们组装成一个完整的、带 SHA-256 清单的输入目录。这个步骤只复制本地
文件，不下载或推送任何厂家库：

```sh
python3 tools/build_t736_vendor_input.py \
  --output /private/t736-vendor-input \
  --archive /private/t736-vendor-input.tar.gz \
  --gpu-deb /private/t736-img-userspace-candidate_arm64.deb \
  --pvr-module /private/pvrsrvkm.ko \
  --wc-archive /private/t736-cedar-wc-v5.tar.gz \
  --transport-archive /private/t736-cedar-transport-v2.tar.gz \
  --backend-archive /private/t736-cedar-browser-backend-v5.tar.gz \
  --ffmpeg-archive /private/t736-browser-ffmpeg-v7.tar.gz \
  --ddr-boot /private/emmc-spl-v4/emmc-spl.bin \
  --boot-package /private/t736-source-boot-package-media-v28.bin \
  --kernel-release 6.18.63-t736-media-v29
```

PVR 内核模块的 `vermagic` 必须与实际启动的内核完全一致。上面的 media-v29 示例只适用于配套的 `6.18.63-t736-media-v29` 内核候选。
要在 GNOME 镜像里提供「打开方式 → AtlasA1 播放器」，在 Linux 上组装私有输入时追加
`--player-deb /private/atlasa1-player_0.1-2_arm64.deb`。构建器读取软件包的真实名称、架构和文件权限，
把它的 SHA-256 加入清单。镜像定制阶段安装清单中的本地软件包，核对目标软件包数据库和播放器入口。
该参数可省略。已在 arm64 Trixie GNOME 根文件系统内通过定制脚本将播放器从 0.1-1 升至 0.1-2，校验了私有解码库和桌面入口。[根文件系统实测](../evidence/atlasa1-player-armbian-rootfs-20261118.json) · [播放器和硬解要求](../tools/player/README.md)
公开 patch 默认产生 `6.18.63-t736-armbian`，它不会自动生成或改写厂商 PVR 模块。

生成的目录或 tar.gz 可以直接传给 `build_t736_armbian_image.py --vendor-input`。
脚本会把 GStreamer OMX/WC、Cedar broker/client、浏览器 FFmpeg、PVR 和 udev
规则放进同一份清单，并明确把硬件验收标为 pending。它不会把插件枚举或软件
回退写成浏览器 1080p60、4K、编码或零拷贝通过。
`--pvr-module` 必须是与 `--kernel-release` 完全相同 vermagic 的模块。公开
Armbian 内核没有 PVR 源码，不能用另一个实验内核的 `pvrsrvkm.ko` 冒充匹配模块。

## 检查并构建

先做检查：

```sh
python3 /path/to/t736/mainline/tools/build_t736_armbian_image.py \
  --armbian /src/armbian/build --check-only
```

## GPU、编解码和启动边界

单一公开补丁不能包含没有源码授权的 PVR GPU 用户态、Cedar/OMX/WC 二进制、匹配固件或 LPDDR4x 厂家训练库。应用这个补丁可以重建公开的内核、U-Boot、设备树和 Armbian 桌面；没有这些厂家组件时，GPU/编解码只能使用系统软件路径，不能得到当前板上已经运行的私有硬件加速组合。

准备私有输入与 GNOME 根文件系统定制时，可以先核验清单并生成 Armbian 构建目录：

```sh
python3 /path/to/t736/mainline/tools/build_t736_armbian_image.py \
  --armbian /src/armbian/build \
  --vendor-input /private/t736-vendor-input.tar.zst \
  --output /tmp/t736-armbian-prep --check-only
```

`--run` 调用官方 `compile.sh` 构建 GNOME。分区阶段要求匹配实板的 8 GiB 自定义 GPT。旧私有包常把第二阶段启动包命名为 `t736-ddr-spl.bin`，需用独立的 eGON SPL 和第二阶段包重新生成清单。根文件系统定制入口从 `userpatches/t736-private/` 安装 GPU、媒体和桌面依赖，再按清单内核版本重建模块索引，核对 `pvrsrvkm` 的路径和 `vermagic`。桌面通过 `t736-cedar.socket` 按需启动解码服务。实验镜像的 root 密码默认为 `1234`，私有构建可用 `T736_ROOT_PASSWORD` 覆盖。

## 结果边界

构建成功只证明源码、输入和打包步骤完成。`t736-build-inputs.json` 会记录输入 hash，输出镜像仍标记 `hardware_acceptance=pending`。需要在实板上另外验收 LPDDR4x 启动、HDMI、GNOME GPU、1080p60/4K 解码、编码、DMA 生命周期、千兆网和冷启动恢复；当前已确认的 Bilibili 结果只有约 30fps 硬解零丢帧，不能写成 60fps 或 4K 已通过。

公开补丁默认设置 `CONFIG_CMA_SIZE_MBYTES=512`。U-Boot 或发行版启动项中的 `cma=` 优先，板测应读取实际的 `CmaTotal`。v29 从 eMMC 重启后确认有 512 MiB CMA。一次 4K HEVC 测试在 Cedar 自有的 128 MiB 配额内保留了 123,863,040 字节，提交 64 个输入，硬件输出为 0 帧。v30 从 eMMC 一次性启动，启用 256 MiB 配额后已输出完整 4K 硬件帧。该次 Firefox 离屏测量计入 599 帧、丢弃 596 帧。[v29 实板记录](../evidence/atlas-display-media-v29-reboot-20261118.json) · [v30 实测](../evidence/media-v30-4k-browser-hardware-20261118.json)
