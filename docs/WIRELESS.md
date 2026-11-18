# T736 板载 Wi‑Fi / 蓝牙适配状态

当前补丁已经打开无线公共框架和常见总线驱动：

- `cfg80211`、`mac80211`、`rfkill`
- Bluetooth BR/EDR、RFCOMM、BNEP、HIDP
- Bluetooth HCI UART H4/H5/3-wire 和 USB HCI
- Broadcom SDIO `brcmfmac`
- Realtek `rtl8723bs` / `rtl8xxxu`
- `MMC_SUNXI` SDIO 主机驱动

这还不能算板载无线已经验收。现有 T736 公开设备树只描述了 UART0、eMMC、USB、HDMI 和以太网，没有记录无线模块型号、SDIO 控制器编号、UART 号、WL_REG_ON/BT_REG_ON、32 kHz 时钟或电源 GPIO。没有这些信息，不能安全地把某个模块写死进设备树；错误的电源或复位脚会影响整板启动。

在板上确认模块后，需要补三部分：

1. 在设备树加入对应 SDIO 节点、非易失电源时序、`cap-sdio-irq` 和模块 compatible。
2. 在设备树加入蓝牙 HCI UART、波特率、`host-wake`/`device-wake` 和 rfkill 电源控制。
3. 将对应固件放入 `/lib/firmware`，并用 `rfkill`, `iw`, `bluetoothctl`, `hciconfig` 验收冷启动、扫描、连接和重启恢复。

目前没有把未确认的芯片型号或 GPIO 猜进单一公开补丁。先在板上执行以下命令可确定下一版设备树：

```sh
uname -a
lsusb -nn
lspci -nn
ip link
rfkill list
dmesg | grep -Ei 'mmc|sdio|wlan|wifi|bluetooth|hci|firmware|rfkill'
```
