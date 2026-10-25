#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-046：把 `STATUS_APP.md` 头部 4 个字段行改写为 §39 的内容，
并把「最近更新」列表裁到 <= 15 行。

🔴 纪律（同 APP-041 / APP-043）：
  - **只动头部块**（第 2~5 行 + `## 最近更新` 之后那一段），章节正文零改动；
  - `io.open(..., newline='')` 保住原行尾（本文件实测纯 LF）；
  - **幂等**：按「时间 + 节号」前 10 字符去重；
  - 头部「阻塞」项必须与最新章节（§39）一致 ——
    §39 已把「语音输出无声」修完并重打 v1.5 ⇒ 头部不能还写「待重打」。
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
    '更新时间: 2026-10-25 19:52',
    ('当前任务: **第 20 次巡检（`CORRECTIONS_APP.md` 无新条目）+ 用户两条反馈闭环（§39）'
     '+ v1.5 持锁重打完成（§39.9）**：'
     '① 🔴🔴 **「语音输出无论 NPU/GPU 都听不到声音」已修** —— 真因是 `RingBuffer.write()` 要求'
     '**整句一次装下**（`count + n > cap`），而容量 `sr*3` = **72 000 样本（3.00 s）**、'
     '一句合成出 **138 240 样本（5.76 s）** ⇒ **条件恒真 ⇒ 每句都等满 30 s 超时被丢弃**'
     '（与设备/精度/驱动**全无关**）；'
     '修法 = `write()` **按空位分片推进**（不丢样本不断句）+ `n_read`/`stall_s` 让「缓冲满但有消费」'
     '与「根本没人消费」分流 + 无人消费时 5 s 内给出人话诊断 + `n_cb` 回调计数 + 启动日志；'
     '② ⛔ **NV CUDA 经查「不可用」⇒ 未加入语音输出选项**（`openvino/libs` 无 CUDA 组件、'
     '`nvidia-smi` 正常说明不是缺驱动、但 `cmake`/`nvcc`/CUDA Toolkit/MSVC 全缺、'
     '官方 README 明确「不含在 Intel 发行版、须自编译、仅在 Ubuntu 20.04 验证」；'
     '`GPU.1` 的 f32/f16 失败完全相同（3/7）⇒ 是 Intel GPU plugin 枚举，不是 CUDA 设备）；'
     '③ ✅ **v1.5 已持锁重打**：md5 `f8475ce511efef7d13209bf9b64b5b95`、11 216 075 157 B、'
     '13 979 条目、逐字节一致、**PASS**；zip 内 `tts_worker.py` md5 `77e1d988…` 含全部播放修复、'
     'README 第（11）条与 MANIFEST 第（11）条都在包内、**方案 C 残留 0**；'
     '④ ✅ 打包前自检 **PASS 49 / 0**（新增 MANIFEST 第（11）条断言）'),
    ('阻塞 / 待用户决定: '
     '① 🟢 ~~「语音输出听不到声音」~~ ⇒ **§39 已修 + 已重打进包**（NPU·F16 6.96 s / 集显·F32 33.9 s 均实测出声）；'
     '② ⛔ **NV CUDA 方案未加入**（不可用，依据见 §39.5）⇒ 用户若要「真用 NVIDIA 跑」需另立项目（自编译 plugin）；'
     '③ ⛔ **APP-017 的「检查点 3（TTS 实时性 + ABBA）」**由另一个 App 并行会话在做'
     '⇒ 本会话**不重复跑、不抢锁**；'
     '④ ⛔ **APP-012② / APP-017 的 WER +2.6pp 主因**仍未定位（接缝去重只值 ≈3%）；'
     '⑤ ⛔ **APP-015 方案 C** 仍是工作区在制品（验收 18/21 FAIL）⇒ **v1.5 明确不带**；'
     '⑥ ⛔ **APP-009②** 的 MT UNIT 方案 A/B/C/D 仍在 v4 复算 ⇒ 渲染层三处**仍未改**；'
     '⑦ ⛔ **包体 10.45 GiB** 优化未做；⑧ ⛔ **V7 残句代价**待用户确认；'
     '⑨ ⛔ **集显 F32 的 TTS 很慢**（首包 33.9 s，RTF≈15.6）⇒ 不承诺实时朗读'),
]

NEW_UPDATES = [
    '- 19:50 §39.9 ✅ **v1.5 已持锁重打（含播放修复）**：md5 `f8475ce511efef7d13209bf9b64b5b95`、11 216 075 157 B、13 979 条目、**逐字节一致 PASS**',
    '- 19:50 §39.9 ✅ **zip 内核实**：`app/tts_worker.py` md5 `77e1d988…`（== 包目录 == HEAD）、播放修复 6 个标记齐全、README/MANIFEST 第（11）条在包内、**方案 C 残留 0**',
    '- 19:35 §39 🔴🔴 **「语音输出无论 NPU/GPU 都听不到声音」已修**：真因 = `RingBuffer.write()` 要求「整句一次装下」，容量 72 000 样本（3 s）< 一句 138 240 样本（5.76 s）⇒ 条件恒真 ⇒ **每句都超时被丢**（与设备/精度无关）',
    '- 19:35 §39 🔴 **探针 `app044` 三段证据**：A 无消费者（报容量）/ **A2 有消费者仍超时**（证伪「环境问题」）/ B 真实流 0.5 s 响、5.76 s 挂 ⇒ 修后 A2 OK 2.81 s、B 5.76 s OK 2.76 s',
    '- 19:35 §39 ⛔ **NV CUDA 不可用 ⇒ 未加入语音输出选项**：libs 无 CUDA 组件 / cmake-nvcc-CUDA Toolkit-MSVC 全缺 / 官方 README「须自编译、仅 Ubuntu 20.04 验证」 / `GPU.1` 是 Intel GPU plugin 枚举',
    '- 19:35 §39 ✅ **两设备端到端出声**：NPU·F16 `first_packet_s=6.964` / 集显·F32 `33.883`，均 `n_played=1`、`n_dropped=0`；⚠️ 集显很慢',
    '- 19:35 §39 🔴 **方法论**：`pop_outbox()` 恒空（`_emit()` 从未被调用）⇒ 端到端观测必须用 `stats()`；「有消费者就不会超时」的假设被 A2 证伪',
    '- 19:31 §39 ✅ **文档同步**：README 中英补第（11）条（含「仍听不到怎么自查」）、MANIFEST notes 第（11）条、自检新增断言 ⇒ **PASS 49 / 0**',
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
