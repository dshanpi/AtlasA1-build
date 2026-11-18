# T736 Armbian 重建入口

如果你只想自己操作，直接使用 [`patches/t736-armbian-open-source.patch`](../patches/t736-armbian-open-source.patch)。它是一个普通 unified patch，不需要 Python 入口、私有目录或厂家输入。

```sh
git clone https://github.com/armbian/build.git
cd build
git checkout 2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736
git apply /path/to/t736/mainline/patches/t736-armbian-open-source.patch
./compile.sh BOARD=t736-mainline BRANCH=current RELEASE=trixie \
  BUILD_DESKTOP=yes DESKTOP_APPGROUPS_SELECTED=gnome EXPERT=yes SHARE_LOG=no
```

这个补丁增加公开的 board/family 配置、Linux/U-Boot 补丁、内核配置和一份板上媒体验收脚本。内核配置打开了 DMA-BUF/CMA、512 MiB 默认 CMA 区、通用 DRM/V4L2 框架、STMMAC/Realtek PHY 依赖，以及 Wi‑Fi/蓝牙公共框架、SDIO/常见 Broadcom/Realtek 驱动和 HCI UART。512 MiB 是 HEVC 1080p/4K 连续 DMA 缓冲的默认预算，启动参数中的 `cma=<size>` 仍会覆盖内核配置，实板验收必须记录 `/proc/meminfo` 的 `CmaTotal`/`CmaFree` 和 dma-heap 分配结果。补丁中的 `userpatches/t736-media-acceptance.py` 只做显式 OMX/GStreamer 测试并输出 JSON，不会把软件回退或插件枚举写成硬件通过。板载无线模块的设备树、电源 GPIO、UART/SDIO 连接仍按 [`docs/WIRELESS.md`](WIRELESS.md) 待确认，不能把“驱动已编译”当成无线已通过。

构建机需要 Linux、aarch64 交叉工具链、QEMU/binfmt 和 Armbian 的依赖。`config/sources.lock.json` 锁定了 Armbian、Linux 和 U-Boot 的期望版本。补丁应用后，媒体验收脚本位于 Armbian checkout 的 `userpatches/t736-media-acceptance.py`，复制到板卡后可直接运行。

如果需要自动校验版本并复制补丁，也可以使用 `tools/build_t736_armbian_image.py`；它是辅助脚本，不是应用 T736 补丁的必需依赖。

## 准备厂家输入

GPU 用户态、PVR 内核模块、Cedar/OMX/WC、匹配固件和 DDR 启动库属于授权厂家输入，公开仓库不分发。将它们放在私有目录或 tar/tar.zst 中，并在根目录放置 `manifest.json`。字段格式见 [`config/t736-vendor-inputs.example.json`](../config/t736-vendor-inputs.example.json)。每个文件必须有相对 payload 路径、绝对 rootfs 目标路径、角色和 SHA256；入口会要求 `gpu_userspace`、`pvr_module`、`codec_backend`、`codec_service`、`device_rules`、`ddr_boot` 六类输入齐全，hash 不匹配时停止。

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
  --ddr-boot /private/t736-source-boot-package-media-v28.bin \
  --kernel-release 6.18.63-t736-media-v29
```

PVR 内核模块的 `vermagic` 必须与实际启动的内核完全一致。上面的 media-v29 示例只适用于配套的 `6.18.63-t736-media-v29` 内核候选。
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

如果你拥有授权厂家输入，原来的完整镜像辅助入口仍可使用，但它不是单 patch 方案的必要条件：

```sh
python3 /path/to/t736/mainline/tools/build_t736_armbian_image.py \
  --armbian /src/armbian/build \
  --vendor-input /private/t736-vendor-input.tar.zst \
  --output /tmp/t736-armbian-prep --run
```

`--run` 调用官方 `compile.sh`，构建结果在 Armbian 的 `output/`。入口会安装 GNOME、Xorg、Firefox 和桌面依赖，并通过 `customize-image.sh` 安装已校验的 GPU/media 文件、udev 规则、Cedar broker 服务和 PVR 模块；root 密码默认按当前实验约定为 `1234`，私有构建可用 `T736_ROOT_PASSWORD` 覆盖。GDM 自动登录保持关闭。

## 结果边界

构建成功只证明源码、输入和打包步骤完成。`t736-build-inputs.json` 会记录输入 hash，输出镜像仍标记 `hardware_acceptance=pending`。需要在实板上另外验收 LPDDR4x 启动、HDMI、GNOME GPU、1080p60/4K 解码、编码、DMA 生命周期、千兆网和冷启动恢复；当前已确认的 Bilibili 结果只有约 30fps 硬解零丢帧，不能写成 60fps 或 4K 已通过。

公开补丁的 `CONFIG_CMA_SIZE_MBYTES=512` 只定义默认池大小。若 U-Boot 或发行版启动项带有较小的 `cma=` 参数，运行时值优先，必须在媒体验收前移除或提高该参数。media-v29 的独立构建入口同样把 v28 的 256 MiB 配置升级到 512 MiB，并在候选包检查中拒绝较小值。更改仅完成源码和构建链同步，需重建匹配的内核/PVR 包后再进行实板 HEVC 1080p/4K 测试。
