#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-041：把 `STATUS_APP.md` **头部 4 个字段行**改写为 §37 的内容，
并把「最近更新」列表裁到 ≤ `MAX_LINES` 行。

🔴 纪律（照抄 MEMORY）：
  - **只动头部块**（第 2~5 行 + `## 最近更新` 之后的那一段），**章节正文零改动**；
  - `io.open(..., newline='')` 保住原行尾（本文件实测 **纯 LF，CRLF=0**）；
  - **幂等**：重复执行不会重复插入，只会把同一批条目保持在最前；
  - 头部「阻塞」项必须与最新章节（§37）一致。

用法：`python app041_set_status_head.py`
"""
from __future__ import annotations

import io
import os
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
MAX_LINES = 15          # APP-001：头部「最近更新」≤ 15 行
MARK = '## 最近更新'

NEW_HEAD = [
    'last_ack: APP-017',
    '更新时间: 2026-10-25 18:09',
    ('当前任务: **巡检（`CORRECTIONS_APP.md` 1 条新条目 **APP-017**）+ 用户两条反馈闭环（§37）**：'
     '① ✅ **ASR 设备重复**已修 —— 根因是 `kind==\'ov\'` 档遍历所有设备（含 `GPU.1`）'
     '而 `kind==\'cuda\'` 档又单列一条 ⇒ 同一块物理显卡出现两次；'
     '修法 = OV 档 `continue` 跳过 CUDA 设备、**保留 CUDA 那条**（按**物理设备**去重，不是按 label）'
     '⇒ 实测 ASR 6 个选项、重复 NVIDIA **0 条**、CUDA **2 条**（Q8_0/Q4_K）；'
     '② 🔴🔴 **「语音输出无法工作」**已修 —— 三条真因全部实测：'
     '(a) **OV 官方发行版压根不带 CUDA plugin**（在 `openvino_contrib`，需自编译）⇒ 旧 note 的「装一下就能用」是错的承诺；'
     '(b) `GPU.1` 是被 **Intel GPU plugin** 枚举的，`f32`/`f16` 失败**完全相同（均 3/7）**'
     '⇒ 与精度无关，而 BabelVox 把 7 个 IR 全编到同一设备 ⇒ **引擎整体加载失败**；'
     '(c) 🔴 **Intel 集显 f16 能编过但合成失控**（talker 跑满 `MAX_DECODER_FRAMES=512` ⇒ 40.96 s 削波音频 peak=1.000）；'
     '④ GUI 的**精度下拉从未生效**（`make_engine` 没 `precision` 形参 → worker 不传 → BabelVox 自建 `ov.Core` 不传 property）⇒ 已三处打通 + `_ov_precision` 注入 `INFERENCE_PRECISION_HINT`；'
     '⑤ GUI **零状态监视** ⇒ 新增 `_track_tts_state()`。'
     '修后 TTS 下拉**只剩 2 个实测可用组合**：`Intel NPU · F16`（首选）+ `Intel GPU（集显） · F32`（慢）；'
     '⏳ **v1.5 zip 生成于修复之前 ⇒ 需重打**（APP-017 要求）'),
    ('阻塞 / 待用户决定: '
     '① ⏳ **APP-017 要求持锁重打 v1.5 zip**（现包内容已更新，旧 zip **不含**本轮修复）；'
     '② ⛔ **APP-017 的「检查点 3（TTS 实时性 + ABBA）」**由另一个 App 并行会话在做（`app037_cp3_abba_v15.py`）'
     '⇒ 本会话**不重复跑、不抢锁**；'
     '③ ⛔ **APP-012② / APP-017 的 WER +2.6pp 主因**仍未定位（接缝去重只值 ≈3%）；'
     '④ ⛔ **APP-015 方案 C** 仍是工作区在制品（验收 18/21 FAIL）⇒ **v1.5 明确不带**；'
     '⑤ ⛔ **APP-009②** 的 MT UNIT 方案 A/B/C/D 仍在 v4 复算 ⇒ 渲染层三处**仍未改**；'
     '⑥ ⛔ **包体 10.45 GiB** 优化未做；⑦ ⛔ **V7 残句代价**待用户确认'),
]

NEW_UPDATES = [
    '- 18:09 §37 ✅ **ASR 设备去重**：OV 档跳过 CUDA 设备、**保留 CUDA**（按物理设备而非 label）⇒ 实测重复 NVIDIA **0** 条 / CUDA **2** 条',
    '- 18:09 §37 🔴🔴 **「语音输出无法工作」已修**：三条真因（OV 不带 CUDA plugin / 集显 f16 合成失控 / 精度下拉从未生效）+ GUI 零状态监视 ⇒ 5 处修法',
    '- 18:09 §37 🔴 **决定性实测**：`GPU.1` 的 `f32` 与 `f16` 失败**完全相同（均 3/7）** ⇒ 与精度无关；`GPU.0` f32 **7/7** 且合成 PASS（5.68 s / peak .555）但**很慢**（RTF≈15.6）',
    '- 18:09 §37 🔴🔴 **方法论**：`played` 不能当验收判据（后台无音频消费 ⇒ 3 s 环形缓冲必然超时，NPU 也被误判 FAIL）⇒ 必须拆开测合成',
    '- 18:09 §37 ✅ **验证**：GUI 冒烟**全 PASS**（ASR 6 / MT 6 / TTS 2）、包内与仓库三文件**逐字节一致**、包内**不含方案 C**、闸门 **PASS**',
    '- 18:09 §37 ⏳ **v1.5 zip 已过期**（生成于修复之前）⇒ 需重打',
]


def main() -> int:
    if not os.path.isfile(P):
        print('!! 找不到', P)
        return 2
    with io.open(P, 'r', encoding='utf-8', newline='') as f:
        lines = f.read().split('\n')      # 纯 LF ⇒ 用 \n 切，末尾保留空串

    # ── ① 头部 4 个字段行（第 2~5 行 ⇒ index 1..4）──
    if lines[0].strip() != '# STATUS_APP':
        print('!! 首行不是 # STATUS_APP，拒绝改写', repr(lines[0]))
        return 3
    for i, new in enumerate(NEW_HEAD):
        idx = 1 + i
        old = lines[idx]
        # 只允许改这 4 个前缀
        expect = ('last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:')[i]
        if not old.startswith(expect):
            print('!! 第 %d 行不是 %r 开头，拒绝改写：%r'
                  % (idx + 1, expect, old[:40]))
            return 4
        lines[idx] = new

    # ── ② 最近更新：保留最新 MAX_LINES 条 ──
    try:
        m = lines.index(MARK)
    except ValueError:
        print('!! 找不到 %r' % MARK)
        return 5
    # 跳过 mark 之后的空行
    j = m + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    k = j
    while k < len(lines) and lines[k].startswith('- '):
        k += 1
    old_items = lines[j:k]

    # 幂等：先剔掉与 NEW_UPDATES 同「时间+节号」前缀的旧条目
    def key(s):
        return s[:9]          # '- 18:09 §37 ...' 的前 9 字符
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
