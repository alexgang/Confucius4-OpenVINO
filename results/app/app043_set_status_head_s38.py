#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-043：把 `STATUS_APP.md` 头部 4 个字段行改写为 §38 的内容，
并把「最近更新」列表裁到 ≤ `MAX_LINES` 行。

🔴 纪律（同 APP-041）：
  - **只动头部块**（第 2~5 行 + `## 最近更新` 之后那一段），章节正文零改动；
  - `io.open(..., newline='')` 保住原行尾（本文件实测纯 LF）；
  - **幂等**：按「时间 + 节号」前 10 字符去重；
  - 头部「阻塞」项必须与最新章节（§37 / §38）一致 ——
    §38 已把 v1.5 重打完成 ⇒ 头部不能还写「⏳ 待重打」。
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
    '更新时间: 2026-10-25 18:27',
    ('当前任务: **巡检（APP-017）+ 用户两条反馈闭环（§37）+ v1.5 持锁重打完成（§38）**：'
     '① ✅ **ASR 设备重复**已修 —— OV 档遍历所有设备（含 `GPU.1`）而 `cuda` 档又单列一条 '
     '⇒ 同一物理卡两次；修法 = OV 档跳过 CUDA 设备、**保留 CUDA 那条**（按**物理设备**而非 label 去重）'
     '⇒ 实测 ASR 6 项、重复 NVIDIA **0**、CUDA **2**；'
     '② ✅ **「语音输出无法工作」**已修（三条真因全实测）：OV **官方发行版压根不带 CUDA plugin**；'
     '`GPU.1` 由 Intel GPU plugin 枚举且 **f32/f16 失败完全相同（均 3/7）** ⇒ 与精度无关，'
     '而 BabelVox 把 7 个 IR 全编到同一设备 ⇒ 一个编不过即整体失败；'
     '**集显 f16 能编过但合成失控**（跑满 512 帧 ⇒ 40.96 s 削波 audio，peak=1.000）；'
     '另修掉 GUI「精度下拉从未生效」+「零状态监视」；'
     '⇒ 修后 TTS 只列 **2 个实测可用组合**：`Intel NPU · F16`（首选）/ `Intel GPU（集显） · F32`（慢，已警告）；'
     '③ ✅ **v1.5 已持锁重打**：md5 `07513403e049a8e475168410dff9ac72`、'
     '11 216 072 487 B、13 979 条目、内容**逐字节一致**、**PASS**；zip 内 4 个修复文件 SHA256 与包目录/HEAD 一致、'
     '**方案 C 残留 0**；打包前自检 **PASS 48 / 0**（口径已改为「基准 = HEAD」）；'
     'README 中英 + MANIFEST notes（7）改写 + 新增（10）随行为同步'),
    ('阻塞 / 待用户决定: '
     '① 🟢 ~~APP-017 持锁重打 v1.5~~ ⇒ **§38 已完成**（PASS + 原子改名）；'
     '② ⛔ **APP-017 的「检查点 3（TTS 实时性 + ABBA）」**由另一个 App 并行会话在做（`app037_cp3_abba_v15.py`）'
     '⇒ 本会话**不重复跑、不抢锁**；'
     '③ ⛔ **APP-012② / APP-017 的 WER +2.6pp 主因**仍未定位（接缝去重只值 ≈3%）；'
     '④ ⛔ **APP-015 方案 C** 仍是工作区在制品（验收 18/21 FAIL）⇒ **v1.5 明确不带**；'
     '⑤ ⛔ **APP-009②** 的 MT UNIT 方案 A/B/C/D 仍在 v4 复算 ⇒ 渲染层三处**仍未改**；'
     '⑥ ⛔ **包体 10.45 GiB** 优化未做；⑦ ⛔ **V7 残句代价**待用户确认；'
     '⑧ ⛔ **集显 F32 的 TTS 很慢**（RTF≈15.6）⇒ 若要「集显也能实时朗读」需另做优化（当前不承诺）'),
]

NEW_UPDATES = [
    '- 18:27 §38 ✅ **v1.5 已持锁重打**：md5 `07513403e049a8e475168410dff9ac72`、11 216 072 487 B、13 979 条目、内容**逐字节一致**、**PASS**',
    '- 18:27 §38 ✅ **zip 内修复已核实**：4 个修复文件 SHA256 与包目录/HEAD 一致、修法标记齐全、**方案 C 残留 0**',
    '- 18:27 §38 🔴 **自检口径修正**：`app014b_v15_preship_check.py` 基准从「工作区」改为 **`git show HEAD:`**（否则会逼着并行会话的在制品进包）⇒ 自检 **PASS 48 / 0**',
    '- 18:27 §38 ✅ **README（中英）+ MANIFEST notes 随行为同步**：notes（7）改为「ASR 新增 CUDA + 去重」、新增（10）「语音输出只列实测可用组合」',
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
        return s[:10]          # '- 18:27 §38' ⇒ 前 10 字符
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
