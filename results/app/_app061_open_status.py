#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-061 开工：改 STATUS_APP.md 头部（last_ack / 更新时间 / 当前任务 / 阻塞）。

🔴 纪律：
- **只动头部 4 行**（行号 3..6），**旧正文一字未删**；
- 🔴 头部第 6 行含**真实 VT 控制符**（`\v`）⇒ **不能用字符串匹配**（Read 工具会把它显示成
  `ext_listenv21`）⇒ 本脚本按**行号 + 行首前缀**定位，并做**唯一命中断言**；
- 🔴 写文件**先写临时文件再原子替换**（`open(p,'w')` 中途异常 ⇒ 目标被清空且无法恢复）。
"""
from __future__ import annotations

import hashlib
import os
import sys

STATUS = r"C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md"

NEW_TASK = (
    "当前任务: **§127 🔄 APP-061 执行中**（`last_ack` APP-060 → **APP-061**；"
    "APP-061 明文要求「开工前先写 last_ack 和一行最近更新」）—— **BLOCKING**："
    "用户实测 v2.1 反馈 6 个问题（CUDA 语音无声／离线「无参考音色」／卡顿／克隆每 10 s 一次／"
    "男声被女声播出／界面不紧凑）⇒ 根因已由 reviewer 定位 ⇒ **在开发版 `live_caption/` 修，"
    "打新版本 v2.2**（v2.1 目录与 zip **一个字节都不许改**）。"
    "① **TTS CUDA 无声** = `tts_worker.py` CUDA 分支只设 `_preset_ref_path`、**未设 `_preset_name`**"
    "（恒 `None`）＋ 回落路径清空 `speaker_name` ⇒ `synth()` 报「没有可用的音色」"
    "② **离线「无参考音色」** = 同根因（离线朗读器走同一 `synth()` 音色检查）"
    "③ **卡顿** = MT+TTS 同在 NPU 使合成慢 25–30 %（1.31 vs 1.00–1.05）；"
    "主因是「合成吞吐 ≤ 播放消耗」⇒ 环形缓冲欠载（`underflow_delta` 6.7–10.8 次/s）"
    "④ **克隆每 10 s 一次** = v2.1 里**两套克隆机制并存**（旧 APP-027 定时采集器 + 新的按句绑定）"
    "⑤ **男声被女声播出** = GUI 漏传 `clone=`（worker `clone_mode=False`）"
    "＋ `_retry_spk_labels` 丢 `is_new`（新说话人永不取样）＋ 标签未到一律回落预设 A"
    "⑥ **界面不紧凑** = 字幕区 < 55 % 窗口高、控件挤成多行"
)

NEW_BLOCK = (
    "阻塞 / 待用户决定: 🔴 **APP-061 的 D1–D4 由 reviewer 明确「线程不要自己定，"
    "由主会话转达后再做」** ⇒ 本轮**不实现**，只按「用户决定之前的默认实现」处理"
    "（② 检测不到边车 ⇒ 下拉框置灰 CUDA ＋ 显示原因；⑤-d 旁路关时明确提示、不允许静默退回定时克隆）："
    "**D1** 说话人旁路窗口 10 s 能否缩短（涉及 ASR 侧 `asr052_spk_runtime.WIN_S` 常量）"
    "｜**D2** 选「跟随说话人（克隆）」时是否**自动打开**说话人旁路"
    "｜**D3** 客户包是否保留 TTS=CUDA 选项（依赖包外 `_fq3tts_env`，客户机不存在）"
    "｜**D4** MT 与 TTS 同选 NPU 时只黄色警告还是直接禁止"
)

NEW_RECENT = (
    "- 2026-11-01 22:23 **§127 APP-061 开工**（`last_ack` APP-060 → **APP-061**）⇒ "
    "**BLOCKING**：用户实测 v2.1 的 6 个问题（CUDA 无声／离线无参考音色／卡顿／克隆每 10 s 一次／"
    "男声被女声播出／界面不紧凑）⇒ reviewer 已定位根因 ⇒ 在开发版 `live_caption/` 修 ⇒ "
    "**打新版本 v2.2**（v2.1 目录与 zip 一个字节都不许改）"
)


def main() -> int:
    if not os.path.exists(STATUS):
        print("[FAIL] STATUS 不存在")
        return 1
    with open(STATUS, "rb") as f:
        raw = f.read()
    before = hashlib.sha256(raw).hexdigest()
    nbytes = len(raw)
    lines = raw.split(b"\n")

    def find_line(prefix: bytes) -> int:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit("[ABORT] 行首前缀 %r 命中 %d 次（需恰好 1）" % (prefix, len(hits)))
        return hits[0]

    i_ack = find_line(b"last_ack: ")
    i_time = find_line(b"\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4: ")  # 更新时间:
    i_task = find_line(b"\xe5\xbd\x93\xe5\x89\x8d\xe4\xbb\xbb\xe5\x8a\xa1: ")  # 当前任务:
    i_block = find_line(b"\xe9\x98\xbb\xe5\xa1\x9e ")  # 阻塞

    lines[i_ack] = "last_ack: APP-061".encode("utf-8")
    lines[i_time] = "更新时间: 2026-11-01 22:23".encode("utf-8")
    lines[i_task] = NEW_TASK.encode("utf-8")
    lines[i_block] = NEW_BLOCK.encode("utf-8")

    # 「最近更新」区块的第一条之前插入新条目（保留条目之间的空行结构）
    hits = [i for i, ln in enumerate(lines)
            if ln.startswith(b"## ") and "最近更新".encode("utf-8") in ln]
    if len(hits) != 1:
        raise SystemExit("[ABORT] 「## 最近更新」命中 %d 次（需恰好 1）" % len(hits))
    i_recent = hits[0]
    j = i_recent + 1
    while j < len(lines) and not lines[j].startswith(b"- "):
        j += 1
    lines.insert(j, NEW_RECENT.encode("utf-8"))

    out = b"\n".join(lines)

    tmp = STATUS + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, STATUS)

    with open(STATUS, "rb") as f:
        after_raw = f.read()
    print("[OK] 开工前 SHA256 %s / %d B" % (before, nbytes))
    print("[OK] 改后   SHA256 %s / %d B" % (hashlib.sha256(after_raw).hexdigest(), len(after_raw)))
    print("[OK] last_ack=APP-061 已写入；最近更新已插入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
