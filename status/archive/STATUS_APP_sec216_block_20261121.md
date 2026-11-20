> 🔴 本文件是 `status/app/STATUS_APP.md` 里 **§216 一节**（标题行＋正文）的**整块逐字归档**（write-once）。
> 活文档对应位置只留**一行指针**；**原文一字未删、未改**。
> §216 的**完整正文**另见 companion `status/app/STATUS_APP_sec216_detail_20261120.md`（12 644 B）。

## §216 APP-116：输出设备 / 预设 B 男声 / GUI 去 4 选项（2026-11-20 10:29）

> 正文见 companion：`status/app/STATUS_APP_sec216_detail_20261120.md`

- **§1** 根因 = GUI 反查表 `_out_label_back` 推导式**变量写反** ⇒ 反查恒 None
  ⇒ `--out-device` 从未传给 worker ⇒ 落回默认设备。已修（逐跳日志＋不静默回落
  ＋运行中切设备只重开播放流）；**A 机实测 21/21 PASS**。
- **§2** 预设 B（男声）由 `Qwen3-TTS-12Hz-0.6B-CustomVoice`（Apache-2.0）**模型生成**
  （24 kHz/单声道/10.0 s/无真人素材）；GUI 显示「预设 A（女声）」「预设 B（男声）」。
  🔴 **用户点头前不进包**。
- **§3** GUI 去 4 个选项（默认值不变）；布局无空洞/无重叠；100 %/150 % 截图已落盘。
- **§5** v2.5 见 companion。未结：⓿抽听＋CER/WER ⓿A 机听感 ⓿是否打 zip（不通知不打）。
- 纪律：只改 App 文件；未改 `CORRECTIONS_APP.md`；未碰 SpecialMVP/MiniMVP；`31e5c67`。

