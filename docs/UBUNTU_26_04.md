# AtlasA1 / T736 · Armbian Ubuntu 26.04 LTS

本配方从官方 Armbian 的固定提交生成 arm64 Ubuntu 26.04（Resolute）根文件系统和板级软件包，交叉编译 Linux、PowerVR 内核模块、SPL、TF-A、U-Boot 和原生播放器，再按 AtlasA1 的 eMMC 布局生成 8 GiB 磁盘镜像。固定 LPDDR4x 参数随源码提供。[发行镜像与校验文件](https://github.com/dshanpi/AtlasA1-build/releases)

## 从官方 Armbian 开始

构建机使用大小写敏感的 Linux 文件系统。准备官方 Armbian 支持的构建环境、sudo、支持运行 arm64 chroot 的 QEMU/binfmt，以及 AArch64 和 ARM soft-float 交叉工具链。本次基准工具链为 Ubuntu 24.04 上的 GCC 13 和 binutils 2.42。源码包构建还用到 python3、git、make、patch、curl、cpio、device-tree-compiler、dpkg-dev、libssl-dev、libelf-dev、bc、bison、flex、pkg-config、patchelf、qemu-user-static、rsync、kmod、e2fsprogs、fdisk、xz-utils 和 zstd。构建与出镜像的目录需要容纳展开的 Linux、根文件系统和 8 GiB 原始镜像。

下载与目标发行版相同版本的 `atlasa1-resolute-armbian.patch`，然后在 Bash 中运行以下命令。这个示例固定到 2026-11-18 发布候选版。[单文件补丁](https://github.com/dshanpi/AtlasA1-build/blob/v2026.11.18-ubuntu26.04-rc1/patches/atlasa1-resolute-armbian.patch)

```sh
git clone https://github.com/armbian/build.git armbian-build
cd armbian-build
git checkout --detach 2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736
curl -fL -o /tmp/atlasa1-resolute-armbian.patch \
  https://raw.githubusercontent.com/dshanpi/AtlasA1-build/v2026.11.18-ubuntu26.04-rc1/patches/atlasa1-resolute-armbian.patch
git apply --whitespace=nowarn --check /tmp/atlasa1-resolute-armbian.patch
git apply --whitespace=nowarn /tmp/atlasa1-resolute-armbian.patch

export ATLAS_TINA_SDK=/srv/tina
bash userpatches/atlasa1-release/tools/build_atlasa1_resolute.sh "$PWD" /srv/atlas-output
```

`/srv/atlas-output` 是新目录。补丁在官方框架下添加板级配置和 `userpatches/atlasa1-release` 中的源代码、测试及构建工具。若已克隆对应版本的 AtlasA1-build，可直接运行 `bash tools/build_atlasa1_resolute.sh /src/armbian-build /srv/atlas-output`。这两种方式调用同一套脚本。

Ubuntu 和 Armbian 的软件包镜像可分别通过 `CUSTOM_UBUNTU_MIRROR_PORTS` 和上游 `LOCAL_MIRROR` 选项配置。构建记录中的根文件系统由这次运行新建的 Ubuntu 基础系统生成，更换下载镜像后继续了同一轮桌面安装。

## 厂家输入和公开编译依赖

| 输入 | 来源与用途 |
| --- | --- |
| `ATLAS_TINA_SDK` | 已配置的 T736 Tina SDK，含 `bsp/` 显示与 IMG BXM 内核源、`brandy/dramlib/sun60iw2p1/spl_libdram/libdram` 和 `out/t736/demo_aiot/buildroot/buildroot/{host,build/libcedarc}`。DDR 库 SHA-256 为 `5361d148fa097ccc14e15a173523783d0eb1a71969bc76d57eb8e1229ddc6d90`。 |
| IMG X11 和 Cedar/OMX 运行库 | 总入口从上述 SDK 提取匹配的 GPU 固件、IMG 用户态和编解码库。若已有配套的包，可同时设置 `ATLAS_IMG_DEB` 与 `ATLAS_CEDAR_WC` 复用它们。最终叠加源码重新生成的 4K OMX 解码库和解码服务。 |
| SDL2 开发根 | 默认从 Debian 下载 arm64 的 `libsdl2-dev` 和 `libsdl2-2.0-0` 2.32.4，校验 SHA-256 后解包，并交叉编译一个链接 SDL2 的小程序。可用 `ATLAS_SDL_SYSROOT` 指向已准备的相同开发根。 |

AtlasA1 成品镜像经项目方授权随镜像发布 LPDDR4x 训练库、PowerVR 用户态和 Cedar 编解码库。从源码重建时，由具有相应权限的构建方提供 Tina SDK。Ubuntu 软件包从已配置的 APT 仓库获取，仓库更新或编译工具链不同会改变生成文件的字节和 SHA-256。需要单独复核输入时，可运行下面两项构建。

```sh
recipe=$PWD/userpatches/atlasa1-release/tools
bash "$recipe/build_atlasa1_resolute_vendor.sh" "$ATLAS_TINA_SDK" /srv/atlas-vendor
bash "$recipe/prepare_atlasa1_sdl_sysroot.sh" /srv/atlas-sdl2-arm64
```

## 构建和核验

| 阶段 | 来源及结果 |
| --- | --- |
| 启动链 | U-Boot v2026.10、社区 TF-A 固定提交 `7d322909`、固定 DDR 库及本板源码。生成 eGON SPL、stage64、BL31、U-Boot 和含每段 CRC 的启动包。 |
| 内核和 GPU | Linux v6.18.63、264 个经 SHA-256 核对的 Tina 显示输入、板级补丁及 PowerVR 24.2 DDK，生成 `linux-image-6.18.63-t736-media-v30`、DTB 和对应 vermagic 的 `pvrsrvkm.ko`。 |
| 视频 | FFmpeg 7.1.5、Cedar 服务及板级 OMX 补丁，生成 `atlasa1-player_0.1-5~resolute1_arm64.deb`。播放器自带配套 FFmpeg 库，保留 Ubuntu 的系统 FFmpeg。 |
| 系统 | 官方 `compile.sh rootfs`、`armbian-bsp-cli` 和 `armbian-base-files`，生成 Ubuntu 26.04 桌面根文件系统，再安装板级包、初始化镜像和桌面配置。 |
| 镜像 | 板级打包器核对 GPT 分区、SPL、启动包、第四分区 ext4，并从镜像内回读 kernel、initrd 和 DTB。镜像同目录含 `.manifest.json` 及压缩文件的 `SHA256SUMS`。 |

```sh
cd /srv/atlas-output
sha256sum -c SHA256SUMS
xz -t Armbian_26.11_AtlasA1_Ubuntu-26.04_Desktop_arm64.img.xz
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
openixcli raw t736-tina-fes-loader.img Armbian_26.11_AtlasA1_Ubuntu-26.04_Desktop_arm64.img --mode command --device-location "<USB位置>" --post-action none
```

OpenixSuit / LYNX 对应选项为 raw、command、开启校验，loader 和 raw 固件分别选择上述两个文件。`eMMC boot0 from image` 保持关闭，扇区偏移由工具处理。等待写入和校验成功后再断电重启。这个写入流程此前已在本板完整写入并校验 8 GiB，新版 Ubuntu 的冷启动状态以该版 Release 记录为准。

较大容量的 eMMC 也按这个固定布局启动。第 4 分区后面还有两个分区，用户区 LBA 40960 保存 GPT 副本，因此本版关闭了 Armbian 的通用首次启动自动扩容。

## 桌面与硬件状态

默认进入 LightDM 的 **AtlasA1 Xfce（X11）** 会话，使用与 Tina PowerVR 用户态库配套的 X11 路径。Xorg 配置优先选择 HDMI 1920×1080，会话启动时关闭 X11 屏保与 DPMS。本次 arm64 根文件系统实测包含 Xfce 4.20、GNOME Shell 50.1、原生 Firefox 160 和系统 FFmpeg 8.0.1。[根文件系统构建与软件版本](https://github.com/dshanpi/AtlasA1-build/blob/v2026.11.18-ubuntu26.04-rc1/evidence/atlasa1-ubuntu-resolute-rootfs-20261118.json)

切换到 GNOME 时，运行 `sudo dpkg-reconfigure gdm3`，选择 GDM，然后重启。恢复默认桌面可运行 `sudo dpkg-reconfigure lightdm`，选择 LightDM 后重启。桌面账号为 `t736`，初始密码为 `1234`。root 初始密码为 `1234`，首次登录按提示更换。

原生播放器支持从桌面打开本地 H.264 / HEVC 文件。本次在运行 v30 的 AtlasA1 上只读挂载最终镜像，直接执行镜像内的 Ubuntu 用户态程序。

- SDL 离屏 GLES 四种颜色全部读回正确，渲染器为 `PowerVR B-Series BXM-4-64`，OpenGL ES 3.2 驱动版本为 `24.2@6603887`。直接使用 GBM 的测试还验证了 60 帧、每帧四个象限的颜色。
- 25 秒的 3840×2160 HEVC 30 fps + AAC 片源经当前运行系统的 v30 Cedar 服务解出 750/750 帧，Cedar 硬件中断增加 750 次。Ubuntu FFplay 收到的画面尺寸为 1920×1080。该轮使用虚拟音视频输出，耗时 25.480 秒。

## RC1 整盘烧录后的实测

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
