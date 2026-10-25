#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-048：把 `STATUS_APP.md` 头部 4 个字段行改写为 §40 的内容，
并把「最近更新」列表裁到 <= 15 行。

🔴 纪律（同 APP-041 / APP-043）：
  - **只动头部块**（第 2~5 行 + `## 最近更新` 之后那一段），章节正文零改动；
  - `io.open(..., newline='')` 保住原行尾（本文件实测纯 LF）；
  - **幂等**：按「时间 + 节号」前 10 字符去重；
  - 头部「阻塞」项必须与最新章节（§39）一致 ——
    §40 已把 CUDA 路径跑通 ⇒ 头部必须带上「待用户决定怎么落」。
"""
from __future__ import annotations

import io
import os
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
MAX_LINES = 15
MARK = '## 最近更新'

NEW_HEAD = [
    'last_ack: APP-017',
    '更新时间: 2026-10-25 20:55',
    ('当前任务: **巡检（APP-017，无新条目）+ §39 修掉「语音输出无声」并重打 v1.5'
     '+ §40 CUDA 路径实测跑通**：'
     '① 🔴 **用户追问「CUDA 是独立的，faster-qwen3-tts 不是能跑吗」⇒ 用户是对的** —— '
     '§39.5 的「不可用」只说 **OpenVINO 的 CUDA plugin**，不等于本机 CUDA 不可用；'
     '② ✅ **PyTorch+CUDA 路径实测跑通**（独立 venv，不进包）：`torch 2.11.0+cu128` / CUDA 12.8 / '
     '`RTX 5050 Laptop` (sm_120) ⇒ 流式 **TTFA 0.547 s**、首块 0.640 s、非流式 **RTF 0.892**'
     '（5.563 s 合成 6.240 s 音频）、RMS 0.1149 / peak 0.5469；'
     '**首包比现网 NPU（6.964 s）快 12.7×**；'
     '③ 🔴 **必须钉 `transformers==5.15.1`** —— 5.20.2 加载即崩（`MimiConfig` 无 `rope_theta`）；'
     '④ 💰 **体积代价 ≈ +5.7 GB**（torch 4 211 MB + 依赖 ≈500 MB + HF 权重 2 400 MB）'
     '⇒ 客户包 11.2 GB → ≈17 GB；且与包内 transformers 4.57.6 **冲突**（需独立 env）；'
     '⑤ ⚠️ **§40 数字为无锁参考**（跑时 asr PID=38236 持锁）⇒ `timing_valid=false`，持锁复测待锁空闲；'
     '⑥ ✅ v1.5 包（md5 `f8475ce5…`）已含 §39 播放修复，13 979 条目、逐字节一致、自检 **PASS 49/0**'),
    ('阻塞 / 待用户决定: '
     '① 🔴 **待用户决定 CUDA 后端怎么落**（§40.7）：'
     '(a) 只做本机可选后端（GUI 第三项、检测不到自动隐藏）⇒ **包体不变**；'
     '(b) 进客户包 ⇒ **+5.7 GB / 需独立 env 解决 transformers 5.15.1 冲突**；'
     '(c) 先做 CUDA vs NPU 音质抽听再定；'
     '② ⛔ **OV 的 CUDA plugin 不引入**（§39.5 依据不变）；'
     '③ ⛔ **APP-017 的「检查点 3」**由另一个 App 并行会话在做 ⇒ 本会话不重复跑、不抢锁；'
     '④ ⛔ **WER +2.6pp 主因**仍未定位；⑤ ⛔ **APP-015 方案 C** 仍在制品（18/21 FAIL）；'
     '⑥ ⛔ 包体 10.45 GiB 优化未做；⑦ ⛔ V7 残句代价待确认；'
     '⑧ ⛔ 集显 F32 TTS 很慢（首包 33.9 s）'),
]

NEW_UPDATES = [
    '- 20:50 §40 🔴 **用户追问成立**：PyTorch+CUDA 路径实测跑通 —— `torch 2.11.0+cu128` / sm_120 / **TTFA 0.547 s**、**RTF 0.892**（首包比 NPU 6.964 s 快 **12.7×**）',
    '- 20:50 §40 🔴 **订正表述边界**：§39.5 的「不可用」只指 **OV 的 CUDA plugin**；**本机 CUDA 完全可用**（matmul 实测通过）',
    '- 20:50 §40 🔴 **钉版坑**：faster-qwen3-tts 必须 `transformers==5.15.1`，装 5.20.2 会 `MimiConfig` 无 `rope_theta` 直接崩',
    '- 20:50 §40 💰 **代价实测**：torch 4 211 MB + 依赖 ≈500 MB + HF 权重 2 400 MB ⇒ **+5.7 GB**（包体 ≈17 GB）；与包内 transformers 4.57.6 冲突',
    '- 20:50 §40 ⚠️ **口径**：无锁参考（asr 持锁）⇒ `timing_valid=false`；持锁复测待锁空闲',
    '- 19:50 §39.9 ✅ **v1.5 已持锁重打（含播放修复）**：md5 `f8475ce511efef7d13209bf9b64b5b95`、11 216 075 157 B、13 979 条目、**逐字节一致 PASS**',
]


def main() -> int:
    if not os.path.isfile(P):
        print('!! 找不到', P)
        return 2
    with io.open(P, 'r', encoding='utf-8', newline='') as f:
        lines = f.read().split('\n')

    if lines[0].strip() != '# STATUS_APP':
        print('!! 首行不是 # STATUS_APP，拒绝改写', repr(lines[0]))
        return 3
    expect = ('last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:')
    for i, new in enumerate(NEW_HEAD):
        idx = 1 + i
        if not lines[idx].startswith(expect[i]):
            print('!! 第 %d 行不是 %r 开头，拒绝改写：%r'
                  % (idx + 1, expect[i], lines[idx][:40]))
            return 4
        lines[idx] = new

    try:
        m = lines.index(MARK)
    except ValueError:
        print('!! 找不到 %r' % MARK)
        return 5
    j = m + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    k = j
    while k < len(lines) and lines[k].startswith('- '):
        k += 1
    old_items = lines[j:k]

    def key(s):
        return s[:10]          # '- 19:50 §39.9' -> 前 10 字符
    newkeys = {key(x) for x in NEW_UPDATES}
    kept = [x for x in old_items if key(x) not in newkeys]
    items = (NEW_UPDATES + kept)[:MAX_LINES]

    out = lines[:j] + items + lines[k:]
    with io.open(P, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(out))

    print('头部 4 行已改写；最近更新 %d -> %d 行（MAX=%d）'
          % (len(old_items), len(items), MAX_LINES))
    return 0


if __name__ == '__main__':
    sys.exit(main())
