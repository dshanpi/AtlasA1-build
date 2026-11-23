# 全新主机构建与版本锁定

目标：只拉取 AtlasA1-build，在新 Ubuntu 24.04 x86_64 主机执行一个入口，自动生成包含 GNOME、PowerVR、Cedar、播放器和 Firefox 适配的完整 eMMC 镜像。不需要用户准备 Tina SDK、私有压缩包或旧工作目录。

**2026-11-23：完整入口从空目录重建通过，退出码 0，用时 61 分 42 秒。** 启动链、Linux v47、PowerVR 内核模块、GPU 用户态包、Cedar/OMX、播放器、Firefox 适配、Armbian BSP、全新 Ubuntu 根文件系统及完整镜像均由同一入口生成。[完整验收记录](../evidence/clean-build-20261123/full-clean-build.json) · [构建日志](../evidence/clean-build-20261123/full-clean-build.log)

本次在现有 Ubuntu 24.04 构建机上使用空输出目录和固定断网容器，只挂载配方、经校验的公开输入缓存及新输出目录；没有挂载旧 SDK 或旧 rootfs。不是新装虚拟机的整机安装测试。四个输入包另行通过了从空缓存的匿名完整下载与 SHA-256 校验。新生成镜像尚未重新烧录实板，既有硬件验收结论不能自动转移给新产物。

## 构建入口

使用固定备份标签，避免后续主分支修改影响复现：

```sh
git clone --branch backup-20261123-clean-build-v1 --depth 1 https://github.com/dshanpi/AtlasA1-build.git
cd AtlasA1-build
bash build.sh
```

支持 Ubuntu 24.04 amd64，需 sudo、网络、8 GiB 内存与至少 35 GiB 空闲空间。入口自动安装缺失的 Docker、下载工具和压缩工具，按 SHA-256 校验并装载固定构建环境；编译容器断网运行。可用 `bash build.sh /absolute/path/new-output` 指定新的输出目录。

如果新主机尚未安装 Git，先执行 `sudo apt-get update && sudo apt-get install -y git`，再执行上面的克隆与构建命令。源码和输出目录应放在大小写敏感的 Linux 文件系统上。

所需输入的版本、大小、下载地址和 SHA-256 都在 `config/clean-build/inputs.lock.json`。入口自动获取约 2.3 GB 输入；缓存位置为 `~/.cache/atlasa1`，可用 `ATLAS_DOWNLOAD_CACHE` 更改。预先准备好校验一致的输入缓存后，编译本身不访问网络。首次安装主机依赖仍需 Ubuntu 软件源。

也可保留“官方 Armbian 源码加一份补丁”的操作方式。使用官方提交 `2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736`，应用本仓库的 `patches/atlasa1-resolute-armbian.patch` 后，在官方源码目录执行：

```sh
bash userpatches/atlasa1-release/build.sh /absolute/path/new-output
```

两种入口使用相同的固定输入与构建配方。补丁包含自动构建入口和板级源码；体积较大的第三方输入由入口自动下载、校验，不需要另行手动配置 SDK。不要把任意未来的 Armbian 提交当作已验证基线。

| 输入 | 内容 |
| --- | --- |
| build-inputs | 固定 LPDDR4x DDR 库、264 个显示源码、PowerVR 内核源码及用户态、Cedar 原始源码和运行库、最小 sysroot 与 SDK 交叉工具链 |
| upstream-sources | 固定提交的 Armbian、Linux、U-Boot、TF-A、FFmpeg 源码和少量构建工具 |
| arm64-packages | 当前系统 1,404 个发行版软件包的精确版本与哈希 |
| builder | 固定 Ubuntu 24.04 amd64 Docker 构建环境 |

另外 7 个板级包在构建时重新生成。OMX 使用 6 个原始 C 源文件重新编译，不复用旧 `.o`、`.lo`、`.la` 或配置后构建目录。厂家闭源 DDR/GPU/解码库依然是必要输入，自动获取并不表示已将它们开源替代。

## 输出和校验

输出目录中的 `image/` 应包含镜像、压缩镜像、SHA256SUMS、磁盘布局清单和精确软件包对照；根目录保存构建日志和输入锁定清单。软件包差异、缺失库、内核模块版本不匹配或构建失败都会中断，不能静默省略 GPU/视频。

本轮通过了 1,411 个软件包的精确版本对照、149 个 GNOME/GDM 资源文件对照、用户态库及 Firefox 入口检查、GPU 模块版本检查、GPT、ext4 fsck、启动文件回读和 XZ 完整性校验。根文件系统不携带构建机的 ARM64 模拟器、机器 ID 或 SSH 主机私钥。

镜像等价指相同软件版本、板级配置和功能，不承诺镜像 SHA-256 逐字节相同。ext4 随机量、构建路径和时间字段尚未全部规范化。新镜像的完整冷启动/媒体实板验收结果须单独记录，不能以编译成功替代。

当前已知限制保持公开：Wi-Fi/蓝牙、物理音频、Chromium Cedar 和严格视频零丢帧尚未通过。新主机构建不会把这些未完成项标记为已支持。

## 源码备份校验

四个仓库均有 `SOURCE-MANIFEST.json`。校验 Git 提交对象可以避免 Windows 换行转换的影响：

`AtlasA1-build` 是完整构建入口，包含这一版本需要的板级源码和补丁；`AtlasA1-linux`、`AtlasA1-uboot`、`AtlasA1-media` 按组件保留对应源码备份。复现时只需克隆 build 仓库，不需要手动拼装四个工程，也不会自动跟随其他仓库主分支的未来改动。维护者修改组件后，应同步构建仓库的对应源码并发布新的版本清单。

```sh
python3 tools/verify_source_manifest.py . --git-ref HEAD
```

维护者输入提取脚本 `package_atlasa1_build_inputs.py` 仅用于生成版本附件；普通用户不需要它，也不需要厂家 SDK。
