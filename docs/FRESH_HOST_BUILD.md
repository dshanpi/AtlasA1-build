# 全新主机构建与版本锁定

目标：只拉取 AtlasA1-build，在新 Ubuntu 24.04 x86_64 主机执行一个入口，自动生成包含 GNOME、PowerVR、Cedar、播放器和 Firefox 适配的完整 eMMC 镜像。不需要用户准备 Tina SDK、私有压缩包或旧工作目录。

**2026-11-23：完整镜像仍在隔离构建验收中，暂不宣称一键复现通过。** 已通过：断网容器从固定输入重建启动链、Linux v47、PowerVR 内核模块、GPU 用户态包、Cedar/OMX、原生播放器、Firefox 解码适配、Armbian BSP 和 base-files。全新根文件系统正在组装。

## 构建入口

入口及依赖锁定正在本次备份中交付。依赖 Release 发布、完整构建通过后，使用：

```sh
git clone https://github.com/dshanpi/AtlasA1-build.git
cd AtlasA1-build
bash build.sh
```

支持 Ubuntu 24.04 amd64，需 sudo、网络、8 GiB 内存与至少 35 GiB 空闲空间。入口自动安装缺失的 Docker、下载工具和压缩工具，按 SHA-256 校验并装载固定构建环境；编译容器断网运行。可用 `bash build.sh /absolute/path/new-output` 指定新的输出目录。

所需输入的版本、大小、下载地址和 SHA-256 都在 `config/clean-build/inputs.lock.json`。入口自动获取约 2.3 GB 输入；缓存位置为 `~/.cache/atlasa1`，可用 `ATLAS_DOWNLOAD_CACHE` 更改。预先准备好校验一致的输入缓存后，编译本身不访问网络。首次安装主机依赖仍需 Ubuntu 软件源。

| 输入 | 内容 |
| --- | --- |
| build-inputs | 固定 LPDDR4x DDR 库、264 个显示源码、PowerVR 内核源码及用户态、Cedar 原始源码和运行库、最小 sysroot 与 SDK 交叉工具链 |
| upstream-sources | 固定提交的 Armbian、Linux、U-Boot、TF-A、FFmpeg 源码和少量构建工具 |
| arm64-packages | 当前系统 1,404 个发行版软件包的精确版本与哈希 |
| builder | 固定 Ubuntu 24.04 amd64 Docker 构建环境 |

另外 7 个板级包在构建时重新生成。OMX 使用 6 个原始 C 源文件重新编译，不复用旧 `.o`、`.lo`、`.la` 或配置后构建目录。厂家闭源 DDR/GPU/解码库依然是必要输入，自动获取并不表示已将它们开源替代。

## 输出和校验

输出目录中的 `image/` 应包含镜像、压缩镜像、SHA256SUMS、磁盘布局清单和精确软件包对照；根目录保存构建日志和输入锁定清单。软件包差异、缺失库、内核模块版本不匹配或构建失败都会中断，不能静默省略 GPU/视频。

镜像等价指相同软件版本、板级配置和功能，不承诺镜像 SHA-256 逐字节相同。ext4 随机量、构建路径和时间字段尚未全部规范化。新镜像的完整冷启动/媒体实板验收结果须单独记录，不能以编译成功替代。

当前已知限制保持公开：Wi-Fi/蓝牙、物理音频、Chromium Cedar 和严格视频零丢帧尚未通过。新主机构建不会把这些未完成项标记为已支持。

## 源码备份校验

四个仓库均有 `SOURCE-MANIFEST.json`。校验 Git 提交对象可以避免 Windows 换行转换的影响：

```sh
python3 tools/verify_source_manifest.py . --git-ref HEAD
```

维护者输入提取脚本 `package_atlasa1_build_inputs.py` 仅用于生成版本附件；普通用户不需要它，也不需要厂家 SDK。
