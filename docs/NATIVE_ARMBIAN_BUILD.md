# Armbian 原生构建入口

原生入口：`compile.sh`。旧版 `build.sh` 继续用于固定软件版本的 GNOME 镜像重建。
新入口调用官方 Armbian 菜单、编译器流程、Debian 打包和根文件系统构建。
完整 GNOME 和 Xfce 镜像已构建并通过离线检查，尚未实板启动。
原生路线的软件包随官方软件源更新。固定版本重建继续使用 `bash build.sh`。

## 从 AtlasA1-build 进入

使用 Ubuntu 24.04 amd64 主机。准备至少 100 GiB 可用空间。
以普通用户执行，Armbian 按需调用 sudo。

```bash
git clone --branch armbian-native-20261124 https://github.com/dshanpi/AtlasA1-build.git
cd AtlasA1-build
./compile.sh
```

选择 `AtlasA1 / T736`、`current`、`resolute`。
桌面暂支持 GNOME 和 Xfce，也支持无桌面镜像。
框架下载至 `output/armbian`；构建产物位于其 `output` 目录。
同一构建目录只允许一个 AtlasA1 构建进程。第二次启动会明确退出，不会清理正在编译的文件。
需要并行构建时，使用独立的仓库和 `output/armbian` 目录。
PowerVR 在内核源码目录外的独立临时目录编译，结束后自动清理。

已有仓库先执行 `git pull --ff-only`。再执行 `./compile.sh BOARD=atlasa1 KERNEL_CONFIGURE=no`。
依次选择 `current`、`resolute`、桌面镜像、GNOME 或 Xfce、软件包档位。
`KERNEL_CONFIGURE=yes` 表示编辑内核选项，不是桌面配置开关。
官方菜单也会显示其他发行版和桌面；本板目前仅支持上述组合。

软件包档位使用新版 Armbian 的 `DESKTOP_TIER`：

| 档位 | 官方桌面软件集合 |
| --- | --- |
| `minimal` | 桌面和登录管理器 |
| `mid` | 增加浏览器、文件管理器和媒体应用 |
| `full` | 再增加办公、创作和开发工具 |

板级适配仍会加入 GPU、Cedar、播放器和适配的 Firefox。
目前完整镜像验证使用 `minimal`。其他档位尚未完整构建验证。
镜像固定为 8 GiB；扩展软件超过根分区容量时，构建会明确报错。

## 自定义预装软件

先运行一次入口，生成 `output/armbian`。然后创建配置文件：

```bash
cat > output/armbian/userpatches/config-myimage.conf <<'EOF'
BOARD=atlasa1
BRANCH=current
RELEASE=resolute
BUILD_DESKTOP=yes
BUILD_MINIMAL=no
KERNEL_CONFIGURE=no
function user_config() {
    add_packages_to_image vim git htop
}
EOF
./compile.sh myimage
```

此命令继续显示桌面和软件包档位菜单。
修改 `add_packages_to_image` 后面的 Ubuntu 软件包名称即可增减自定义清单。
把这份配置文件保存到自己的备份中。安装器不会覆盖它。
旧的 `PACKAGE_LIST_ADDITIONAL` 不是此版本的配置接口。

## 指定构建参数

直接指定 GNOME：

```bash
./compile.sh BOARD=atlasa1 BRANCH=current RELEASE=resolute \
  BUILD_DESKTOP=yes BUILD_MINIMAL=no DESKTOP_ENVIRONMENT=gnome DESKTOP_TIER=minimal \
  KERNEL_CONFIGURE=no
```

打开内核配置菜单：

```bash
./compile.sh BOARD=atlasa1 BRANCH=current kernel-config
```

构建 Xfce / X11 / LightDM 镜像：

```bash
./compile.sh BOARD=atlasa1 BRANCH=current RELEASE=resolute \
  BUILD_DESKTOP=yes BUILD_MINIMAL=no DESKTOP_ENVIRONMENT=xfce DESKTOP_TIER=minimal \
  KERNEL_CONFIGURE=no
```

Xfce 使用对应的 X11 GPU 用户态，包含 Cedar、Firefox 适配和播放器。
GNOME 与 Xfce 输出不同文件名，不需要覆盖已有镜像。

配置保存在 `output/armbian/userpatches/config/kernel/linux-atlasa1-current.config`。
后续构建保留这份配置。备份此文件即可保存自己的内核选项。

单独编译组件：

```bash
./compile.sh BOARD=atlasa1 BRANCH=current kernel
./compile.sh BOARD=atlasa1 BRANCH=current uboot
```

## 官方源码加单文件补丁

```bash
git clone https://github.com/armbian/build.git
cd build
git checkout 2d3dd98fb4a86d4d884cec4fc2f5de28a37a8736
git apply --whitespace=nowarn /path/to/atlasa1-resolute-armbian.patch
./compile.sh PREFER_DOCKER=no
```

补丁直接安装 `userpatches` 板型、配置和扩展。无需替换官方 `compile.sh`。
补丁也修正官方菜单的板族查找路径，使其读取 `userpatches` 中的配置。
安装器重复运行时会识别已应用的修复。
另一个兼容修复让 U-Boot 从已校验的本地源码创建工作区缓存。
因此 AtlasA1 不再额外下载约 391 MB 的通用 U-Boot OCI 源码包。
远程 U-Boot 源码仍使用官方原有流程。
公开输入自动下载并按 SHA-256 校验，不需要本地 Tina SDK。
这些输入包含厂家 DDR、GPU 和 Cedar 库，构建仍需要网络获取依赖。

固定的官方提交用于限制兼容范围。其他 Armbian 提交尚未验证。
发行版仅支持 Ubuntu 26.04 Resolute。文件系统仅支持 ext4。

## 构建内容

- 官方内核阶段编译板级内核；PowerVR 模块随同内核包生成。
- 官方 U-Boot 阶段生成本次 U-Boot；启动包加入源码 SPL、TF-A 和 DDR 库。
- 官方根文件系统阶段安装所选桌面及软件包。
- 板级扩展构建 Cedar、播放器和 Firefox 适配，安装匹配的 GPU 用户态。
- 镜像阶段生成 8 GiB eMMC 布局，检查启动区读回、GPT 和 ext4。

内核配置会改变实际输出。关闭板卡必需驱动可能导致启动或显示失败。
本入口不自动烧录。eMMC 烧录继续使用匹配的 FES loader 和完整原始镜像。

## 验证边界

配置识别、补丁安装及辅助工具测试通过，并不表示新镜像已经实板启动。
官方内核、PowerVR 模块和 U-Boot 编译打包已通过。
单文件补丁重建的 Linux、U-Boot 和 PowerVR 源码树与原生构建输入完全一致。
`kernel-config` 菜单已实测保存退出，保存的配置通过重装保留检查。
Wi-Fi、蓝牙及浏览器高帧率播放的现有限制不会因更换构建入口而消失。
完整 GNOME 构建退出码为 0。根文件系统包含 1,278 个已安装软件包。
GPT、ext4、启动区读回、启动文件和 initramfs 检查通过。
GNOME 50.1、Firefox 160、PowerVR 和 Cedar 文件检查通过。
默认用户为 `t736`，密码为 `1234`。root 密码为 `1234`，首次登录需修改。
这些结果不能代替实板启动、GPU 渲染和视频播放验收。
[镜像布局](../evidence/native-armbian-20261124/native-image-layout.json) · [内容检查](../evidence/native-armbian-20261124/native-image-content.json) · [构建日志](../evidence/native-armbian-20261124/gnome-build.log)

镜像位于 `output/armbian/output/images/`：

```text
Armbian-unofficial_26.11.0-trunk_Atlasa1_resolute_current_6.18.63_gnome_desktop.img
SHA256: c26339b1007143028b23f10fd551dfbb95df26043e252e4fd1864e8885208a32
```

该哈希仅对应本次产物。原生构建的软件包更新和生成时间会改变镜像哈希。

2026-11-25 的 Xfce 构建退出码为 0，包含 1,219 个已安装软件包。
Xfce 4.20、LightDM、X11 GPU、Cedar、Firefox 160 和播放器的镜像内容检查通过。
LightDM 与图形启动目标已启用。GPT、ext4、启动区读回及 initramfs 检查通过。
这份 Xfce 镜像尚未实板启动，不能据此确认图形加速或视频播放性能。
[Xfce 布局](../evidence/native-armbian-20261124/xfce/image-layout.json) · [内容检查](../evidence/native-armbian-20261124/xfce/image-content.json) · [构建日志](../evidence/native-armbian-20261124/xfce/build.log)

```text
Armbian-unofficial_26.11.0-trunk_Atlasa1_resolute_current_6.18.63_xfce_desktop.img
SHA256: ee49b8a7aefc8a297d812622e21161621ac580bc764298059109c2a42642fab9
```

本次验证使用独立构建目录，并复用校验过的公开下载缓存。
GitHub 连接缓慢，部分官方输入由另一台主机下载、校验后传入。
后续验证使用 `OFFLINE_WORK=yes` 复用源码缓存；根文件系统安装仍访问软件源。
正常入口会自动联网获取这些输入，无需另一台主机或私有 SDK。
无缓存主机全程无人值守构建尚未验证。
