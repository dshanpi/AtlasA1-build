# AtlasA1 / T736 · Armbian Ubuntu 26.04 LTS

2026-11-23：新主机使用自动下载、版本锁定的入口，不需要手动准备 Tina SDK。当前完整构建验收进度和适用条件见 [全新主机构建](FRESH_HOST_BUILD.md)。

本配方从官方 Armbian 的固定提交生成 arm64 Ubuntu 26.04（Resolute）根文件系统和板级软件包，交叉编译 Linux、PowerVR 内核模块、SPL、TF-A、U-Boot 和原生播放器，再按 AtlasA1 的 eMMC 布局生成 8 GiB 磁盘镜像。固定 LPDDR4x 参数随源码提供。[发行镜像与校验文件](https://github.com/dshanpi/AtlasA1-build/releases)

## 从官方 Armbian 开始

构建机使用 Ubuntu 24.04 amd64、大小写敏感的 Linux 文件系统、sudo、网络、至少 8 GiB 内存及 35 GiB 空闲磁盘。入口自动安装主机所需工具，并加载固定的 Docker 构建环境；交叉工具链、QEMU 和发行版软件包均随校验过的输入自动取得。

以下命令下载主分支的单文件补丁，并在固定的官方 Armbian 提交上应用。复现 2026-11-18 的原始 RC1 时，从该版本的 Release 页面下载同名补丁。[主分支补丁](https://github.com/dshanpi/AtlasA1-build/blob/main/patches/atlasa1-resolute-armbian.patch) · [RC1 发布页面](https://github.com/dshanpi/AtlasA1-build/releases/tag/v2026.11.18-ubuntu26.04-rc1)

```sh
git clone https://github.com/armbian/build.git armbian-build
cd armbian-build
git checkout --detach 2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736
curl -fL -o /tmp/atlasa1-resolute-armbian.patch \
  https://raw.githubusercontent.com/dshanpi/AtlasA1-build/main/patches/atlasa1-resolute-armbian.patch
git apply --whitespace=nowarn --check /tmp/atlasa1-resolute-armbian.patch
git apply --whitespace=nowarn /tmp/atlasa1-resolute-armbian.patch

bash userpatches/atlasa1-release/build.sh /srv/atlas-output
```

该入口构建 GNOME Wayland / GDM 镜像，使用 v47 内核、配套 PowerVR Wayland 包、Firefox panel2 和原生播放器 0.1-6。内核包含 CPU、eMMC、显示、Cedar 和 PCIe 修复。首次登录的新账户优先使用显示器支持的 1080p60；已有显示配置予以保留。账户 `t736` 的密码为 `1234`，不启用自动登录。root 初始密码同为 `1234`，保留首次登录改密机制。

Wi-Fi / 蓝牙目前仍未通过：AW869C 即 AIC8800D80，SDIO 未枚举芯片，不能宣称驱动已可用。PMIC 和原理图排查记录见 [无线诊断](../evidence/wireless-path-20261120/RUNTIME-TRIALS-20261121.md)。诊断用寄存器实验不进入发行内核。Chromium 仅接通 GPU 绘制，尚未接通 Cedar 视频解码。Firefox 的 4K HEVC 路径缩放到 1080p 显示，不能作为原生 4K HDMI 验收。每个成品镜像的实测范围以 Release 附件为准。

维护者旧脚本 `tools/build_atlasa1_resolute.sh` 仍保留 v30 / Xfce 和 `--pcie-v34` 配方，需要手工准备 SDK。新入口 `build.sh` 固定构建 GNOME。以下 RC1 / v34 记录属于历史版本。

11 月 19 日的 v34 硬件预览复用 RC1 根文件系统，在可写叠加层安装 v34 内核、配套 PowerVR 模块、双格式 Cedar 服务和 Firefox 160 的 Cedar 硬解入口。8 GiB 原始镜像的 SHA-256 为 `80975eb72bf80e53e549e7d4351600719cdc2d09113e30790a03df24e1636622`。离线检查通过了 GPT、ext4 和启动文件回读，并以普通用户核对了 Firefox 入口及 H.264、HEVC 解码器。该预览整盘仍待 FES 重刷和冷启动验证。已通过 FES 整盘烧录的是 RC1，v34 内核的冷启动使用该板 eMMC 上的独立启动文件。[最终预览镜像记录](../evidence/atlasa1-v34-firefox-image-20261119.json) · [实板启动记录](../evidence/atlasa1-ubuntu26-rc1-hardware-trial-boots-20261118.json)

11 月 18 日的早期 v34 整盘也通过了 GPT、ext4 和启动文件回读检查，当时镜像保留了原装 Firefox。[早期镜像记录](../evidence/atlasa1-v34-image-integration-20261118.json)

`/srv/atlas-output` 必须是新目录。补丁在官方框架下添加板级配置和 `userpatches/atlasa1-release` 中的源代码、测试及构建工具。若已克隆对应版本的 AtlasA1-build，可直接运行 `bash build.sh /srv/atlas-output`。两种方式调用同一套固定输入脚本。

新入口从锁定版本的 Ubuntu / Armbian 软件包新建根文件系统，不复制旧 rootfs，也不在编译阶段访问滚动更新的软件源。装入镜像的 APT 配置恢复为正常的公开软件源，便于用户安装和更新软件。

## 2026-11-21 GNOME v47 构建

已从新建的官方 Armbian / Ubuntu 26.04 根文件系统生成 GNOME Wayland 完整镜像，未复制旧板卡根文件系统。原始镜像 8,589,934,592 字节，压缩包 1,041,712,836 字节。离线 rootfs 配置、GPT、ext4 fsck、启动文件回读哈希和 XZ 完整性检查均通过。

- 原始镜像 SHA-256：`dcd1018a25c267d0541b7715320fcef57d5cf4d7ebe61c0ed47d8f741ca0dadd`
- `.img.xz` SHA-256：`09482419cae81d4fb33577d9771fa4587b99be8f3e4925ce72764d667b4b2f54`

**2026-11-22 已完成新镜像整盘写入、完整 8 GiB SHA-256 回读及断电启动。** 本轮 FES 在 RAM loader 的 USB 重连阶段两次失败，尚未写入磁盘；随后通过 U-Boot 一次性启动 RAM 维护系统，将原始 Release 镜像写入 eMMC，写入和回读共 509.679 秒。断电 5 秒后，48.915 秒内到达新系统串口登录界面。13 项在线检查通过，启动组件、内核、initrd、DTB、根分区标识与 manifest 一致。NVMe 未挂载、未写入。备份 GPT 已迁至物理 eMMC 末端，六个分区条目保持不变。

新镜像实际启动暴露了两项配置缺陷：GNOME 50 跳过带旧式 `X-GNOME-Autostart-Phase` 的显示自启动项，首次桌面与登录界面仍为 1440p；镜像缺少自动校时服务。主分支已修复，实板修复后用户桌面与 GDM 均为 1080p60，NTP 已同步。**原始 RC1 下载文件保持不变，不包含这些安装后修复。** 主分支重新构建会包含修复。已安装 RC1 可在板上克隆本仓库后执行以下命令，保存工作后重启：

```sh
sudo bash tools/stage_atlasa1_gnome_wayland.sh /
sudo apt-get update
sudo apt-get install systemd-timesyncd
sudo systemctl enable --now systemd-timesyncd
sudo reboot
```

PowerVR WebRender 已确认。本地播放器硬解 1080p60 的 1500 帧、4K30 的 750 帧，播放器零丢帧，但 Wayland 合成器分别显示 1456 和 749 帧，严格验收未通过。Firefox 空闲预热后 1080p60 约 59.39 fps、丢 12 帧；4K HEVC 硬件缩放到 1080p 约 29.92 fps、丢 1 帧，同样未达到零丢帧标准。前几轮测试与后台 APT 有重叠，不作为隔离性能基准。未枚举 ALSA 声卡，测试使用虚拟音频。

[11 月 22 日整盘与多媒体验收](../evidence/gnome-release-20261121/gnome-hardware-validation-20261122.json) · [原始日志](../evidence/gnome-release-20261121/hardware-20261122/) · [打包时历史验收范围](../evidence/gnome-release-20261121/release-validation.json) · [构建组件](../evidence/gnome-release-20261121/component-build.json) · [安装包清单](../evidence/gnome-release-20261121/installed-packages.tsv)。原始 manifest 的 `hardware_boot=unverified` 是打包时状态，最新启动结论见日期标注的新增记录。

## 维护者旧配方与厂家输入

以下仅说明历史手动构建脚本。普通用户使用上面的 `build.sh`，所需内容已经整理为公开 Release 输入并由入口自动下载、校验。

| 输入 | 来源与用途 |
| --- | --- |
| `ATLAS_TINA_SDK` | 已配置的 T736 Tina SDK，含 `bsp/` 显示与 IMG BXM 内核源、`brandy/dramlib/sun60iw2p1/spl_libdram/libdram` 和 `out/t736/demo_aiot/buildroot/buildroot/{host,build/libcedarc}`。DDR 库 SHA-256 为 `5361d148fa097ccc14e15a173523783d0eb1a71969bc76d57eb8e1229ddc6d90`。 |
| IMG X11 和 Cedar/OMX 运行库 | 总入口从上述 SDK 提取匹配的 GPU 固件、IMG 用户态和编解码库。若已有配套的包，可同时设置 `ATLAS_IMG_DEB` 与 `ATLAS_CEDAR_WC` 复用它们。最终叠加源码重新生成的 4K OMX 解码库和解码服务。 |
| SDL2 开发根 | 默认从 Debian 下载 arm64 的 `libsdl2-dev` 和 `libsdl2-2.0-0` 2.32.4，校验 SHA-256 后解包，并交叉编译一个链接 SDL2 的小程序。可用 `ATLAS_SDL_SYSROOT` 指向已准备的相同开发根。 |

旧脚本须提供上表的 Tina SDK；新的单补丁自动入口无需手动提供。成品镜像经授权包含链接了 LPDDR4x 训练库的 SPL、配套 PowerVR 模块与用户态、Cedar 运行库。固定输入保证软件版本一致，但时间戳、文件系统 UUID 等仍会使生成镜像的 SHA-256 不同。维护者需要重新提取输入时，可运行下面两项构建。

```sh
recipe=$PWD/userpatches/atlasa1-release/tools
bash "$recipe/build_atlasa1_resolute_vendor.sh" "$ATLAS_TINA_SDK" /srv/atlas-vendor
bash "$recipe/prepare_atlasa1_sdl_sysroot.sh" /srv/atlas-sdl2-arm64
```

## 构建和核验

| 阶段 | 来源及结果 |
| --- | --- |
| 启动链 | U-Boot v2026.10、社区 TF-A 固定提交 `7d322909`、固定 DDR 库及本板源码。生成 eGON SPL、stage64、BL31、U-Boot 和含每段 CRC 的启动包。 |
| 内核和 GPU | Linux v6.18.63、264 个经 SHA-256 核对的 Tina 显示输入、板级补丁及 PowerVR 24.2 DDK，GNOME 选项生成 `linux-image-6.18.63-t736-gnome-v47`、DTB 和对应 vermagic 的 `pvrsrvkm.ko`。 |
| 视频 | FFmpeg 7.1.5、Cedar 服务及板级 OMX 补丁，生成 `atlasa1-player_0.1-6~resolute1_arm64.deb`。播放器自带配套 FFmpeg 库，保留 Ubuntu 的系统 FFmpeg。 |
| 浏览器 | 主分支从 Ubuntu 源码包构建 FFmpeg 8 Cedar 解码库，并随镜像安装 `atlasa1-firefox-cedar`。打包前以桌面用户检查应用菜单入口、FFmpeg ABI 和 H.264、HEVC 的默认解码器。 |
| 系统 | 固定发行版包通过 mmdebstrap 从零安装；官方 Armbian `armbian-bsp-cli` 和 `armbian-base-files` 从源码重建，再安装板级包、初始化镜像和桌面配置。软件包版本与基准系统逐项比较。 |
| 镜像 | 板级打包器核对 GPT 分区、SPL、启动包、第四分区 ext4，并从镜像内回读 kernel、initrd 和 DTB。镜像同目录含 `.manifest.json` 及压缩文件的 `SHA256SUMS`。 |

```sh
cd /srv/atlas-output/image
sha256sum -c SHA256SUMS
xz -t Armbian_26.11_AtlasA1_Ubuntu-26.04_GNOME_clean_arm64.img.xz
```

本次 RC1 的文件摘要如下。第 4 分区中普通用户可用 3,671,642,112 字节，系统软件包清单共 1,402 项。[镜像内核、DTB、启动包与 GPT 校验](https://github.com/dshanpi/AtlasA1-build/blob/v2026.11.18-ubuntu26.04-rc1/evidence/atlasa1-ubuntu26-rc1-image-manifest-20261118.json) · [软件包明细](https://github.com/dshanpi/AtlasA1-build/blob/v2026.11.18-ubuntu26.04-rc1/evidence/atlasa1-ubuntu26-rc1-packages-20261118.tsv)

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| 下载的 `.img.xz` | 1,004,564,592 | `a5b882423f308f7d7b9218ba011beef8ccfb51cdc27979d6526c66af6f5d3d25` |
| 解压后的 `.img` | 8,589,934,592 | `01235d344087d299e70cf4581d18385b76db1cac02cf3a9471055bc0ca9c1232` |

## 用 Openix 写入板载 eMMC

先备份 eMMC 上的数据。解压后的 `.img` 是从物理扇区 0 开始的完整 **eMMC 用户区**镜像，长度应为 8,589,934,592 字节。实测板卡的 `EXT_CSD PARTITION_CONFIG=0x00`，两个硬件 boot 分区均为空。上电后 Boot ROM 从用户区 LBA 16 读取 SPL，第二阶段启动包位于 LBA 24576，根系统在第四分区。SD 卡启动另需对应的板级支持。

先校验下载文件，再用 `xz -dk <镜像名>.img.xz` 或 7-Zip 解压。Openix 的另一个输入是本板的 RAM-only FES loader。已有的匹配 loader 应为 1,482,752 字节，SHA-256 为 `565436e6d6f4370d05788afa3397a7e2368b5d5d2cef9a6490700b9b944cee08`。也可以从自己持有的 Tina LPDDR4x 恢复固件提取，工具会核对四个输入组件及输出哈希。

```sh
python3 userpatches/atlasa1-release/tools/extract_atlasa1_fes_loader.py \
  "$ATLAS_TINA_SDK/out/t736_lpddr4_emmc_armbian13_uart0.img" t736-tina-fes-loader.img
```

连接 OTG 数据线，按住 FEL 并短按 RESET，再松开 FEL。使用 OpenixCLI 0.2.11 查看设备，按扫描返回的 USB 位置选择这块板。以下为 Windows 命令，`<USB位置>` 需替换为实际值。

```powershell
openixcli scan --detailed
openixcli raw t736-tina-fes-loader.img Armbian_26.11_AtlasA1_Ubuntu-26.04_GNOME_arm64.img --mode command --device-location "<USB位置>" --post-action none
```

OpenixSuit / LYNX 对应选项为 raw、command、开启校验，loader 和 raw 固件分别选择上述两个文件。`eMMC boot0 from image` 保持关闭，扇区偏移由工具处理。等待写入和校验成功后再断电重启。这个写入流程此前已在本板完整写入并校验 8 GiB，新版 Ubuntu 的冷启动状态以该版 Release 记录为准。

较大容量的 eMMC 也按这个固定布局启动。第 4 分区后面还有两个分区，用户区 LBA 40960 保存 GPT 副本，因此本版关闭了 Armbian 的通用首次启动自动扩容。

## 早期 RC1 桌面与硬件记录

早期 RC1 默认进入 LightDM 的 **AtlasA1 Xfce（X11）** 会话，使用与 Tina PowerVR 用户态库配套的 X11 路径。Xorg 配置优先选择 HDMI 1920×1080，会话启动时关闭 X11 屏保与 DPMS。本次 arm64 根文件系统实测包含 Xfce 4.20、GNOME Shell 50.1、原生 Firefox 160 和系统 FFmpeg 8.0.1。[根文件系统构建与软件版本](https://github.com/dshanpi/AtlasA1-build/blob/v2026.11.18-ubuntu26.04-rc1/evidence/atlasa1-ubuntu-resolute-rootfs-20261118.json)

从应用菜单选择 **Firefox (AtlasA1 Cedar)** 可启用浏览器硬解。主分支的镜像构建默认安装此入口，原始 RC1 镜像可安装 Release 中的同名配套 deb。该入口和解码器已在 Ubuntu 26.04 成品根文件系统中以 `t736` 用户核验。浏览器在 1080p60 片源的独立 X11 虚拟显示测试中呈现约 38.54 fps。[浏览器接入与测试](../tools/browser/FIREFOX_RESOLUTE.md) · [镜像用户态验收](../evidence/atlasa1-firefox-image-integration-20261119.json)

切换到 GNOME 时，运行 `sudo dpkg-reconfigure gdm3`，选择 GDM，然后重启。恢复默认桌面可运行 `sudo dpkg-reconfigure lightdm`，选择 LightDM 后重启。桌面账号为 `t736`，初始密码为 `1234`。root 初始密码为 `1234`，首次登录按提示更换。

原生播放器支持从桌面打开本地 H.264 / HEVC 文件。本次在运行 v30 的 AtlasA1 上只读挂载最终镜像，直接执行镜像内的 Ubuntu 用户态程序。

- SDL 离屏 GLES 四种颜色全部读回正确，渲染器为 `PowerVR B-Series BXM-4-64`，OpenGL ES 3.2 驱动版本为 `24.2@6603887`。直接使用 GBM 的测试还验证了 60 帧、每帧四个象限的颜色。
- 25 秒的 3840×2160 HEVC 30 fps + AAC 片源经当前运行系统的 v30 Cedar 服务解出 750/750 帧，Cedar 硬件中断增加 750 次。Ubuntu FFplay 收到的画面尺寸为 1920×1080。该轮使用虚拟音视频输出，耗时 25.480 秒。

## RC1 整盘烧录后的实测

板端安装双格式服务后再次启动默认 v30，连续播放 4K HEVC、1080p60 H.264、4K HEVC 三段文件，实际提交帧数分别为 750、1,500 和 750，播放器均记录零丢帧。计入进程启动，第一段 25 秒视频耗时 29.821 秒，超出实时门槛；后两段分别耗时 25.640 秒和 25.466 秒。使用 PowerVR 离屏呈现和 SDL 虚拟音频。[默认系统更新后复测](../evidence/atlasa1-rc1-installed-broker-update-20261118.json)

FES 已向板载 eMMC 写入并提交完整 8 GiB，工具校验成功。断电 5 秒后，固定 LPDDR4x SPL、TF-A、U-Boot 和 Linux 6.18.63 自动引导 Ubuntu 26.04。串口登录和 SSH 登录成功。从 eMMC 回读的启动组件、内核、initrd、DTB 和根分区标识均与 Release 清单一致。HDMI 的 DRM 和 LightDM XRandR 均报告 1920×1080、60 Hz；测试时屏幕处于登录界面。以普通用户运行的 PowerVR SDL 和 GBM 图像读回通过。以太网协商为 100 Mbps 全双工，通过 DNS 和 HTTPS 访问 Ubuntu 镜像站。

| 本地播放器输入 | PowerVR 离屏提交 | 首次打开至退出 | 复播至退出 | 复播音画时差 P95 |
| --- | --- | --- | --- | --- |
| H.264，1920×1080，60 fps，25 秒 | 1500/1500 帧，零丢帧 | 28.40 秒 | 25.54 秒 | 38 ms |
| HEVC，3840×2160，30 fps，25 秒；硬件缩放至 1920×1080 | 750/750 帧，零丢帧 | 29.69 秒 | 25.52 秒 | 29 ms |

两项首次测试分别在干净启动后执行。RC1 的 Cedar 服务仅保留一种解码格式；从上述 4K HEVC 切到 1080p H.264 会退回软件解码，25 秒片段实测耗时 43.31 秒。发行版原装 Firefox 的离屏 H.264 1080p60 测试共计 1187 帧、丢 527 帧，Cedar 中断增量为零。RC1 未枚举 ALSA 声卡，音画计时使用 SDL 虚拟音频。物理扬声器、原生 4K HDMI 扫描输出和硬件编码仍待实测。[完整实板报告](../evidence/atlasa1-ubuntu26-rc1-installed-validation-20261118.json)

本板 eMMC 容量为 58.2 GiB。整盘写入后，备份 GPT 初始位于 8 GiB 镜像末端。板上运行以下命令可备份原 GPT、迁移副本到实际介质末端，并同步 LBA 40960 的厂家镜像。脚本校验主备 CRC 和全部六个分区条目；此次操作后根分区保持原大小。

```sh
sudo python3 tools/validation/atlasa1_finalize_gpt.py /path/to/release.manifest.json --apply
```

首次启动另有两个 systemd 单元报错。RC1 内核缺少 `rpc_pipefs`，板载 eMMC 也不提供 SMART。仓库中的根文件系统配置为前者添加了启动条件，并让 `smartd` 在没有 SMART 磁盘时继续运行。两项修改已在烧录后的板上验证。[FES 与首次冷启动记录](../evidence/atlasa1-ubuntu26-rc1-fes-coldboot-20261118.json)
