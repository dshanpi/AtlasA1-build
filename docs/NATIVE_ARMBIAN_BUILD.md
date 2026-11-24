# Armbian 原生构建入口

开发中的入口：`compile.sh`。旧版 `build.sh` 继续用于固定软件版本的 GNOME 镜像重建。
新入口调用官方 Armbian 菜单、编译器流程、Debian 打包和根文件系统构建。
完整新镜像尚在构建验证，不能替代已通过实板验收的发行版。
原生路线的软件包随官方软件源更新。固定版本重建继续使用 `bash build.sh`。

## 从 AtlasA1-build 进入

使用 Ubuntu 24.04 amd64 主机。准备至少 100 GiB 可用空间。
以普通用户执行，Armbian 按需调用 sudo。

```bash
./compile.sh
```

选择 `AtlasA1 / T736`、`current`、`resolute`。
桌面暂支持 GNOME 和 Xfce，也支持无桌面镜像。
框架下载至 `output/armbian`；构建产物位于其 `output` 目录。

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
本次原生构建记录将单独列出，旧版镜像验收不能代替它。

本次验证使用独立构建目录，并复用校验过的公开下载缓存。
GitHub 连接缓慢，部分官方输入由另一台主机下载、校验后传入。
后续验证使用 `OFFLINE_WORK=yes` 复用源码缓存；根文件系统安装仍访问软件源。
正常入口会自动联网获取这些输入，无需另一台主机或私有 SDK。
无缓存主机全程无人值守构建尚未验证。
