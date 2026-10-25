#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-042：更新客户包 `app/MANIFEST.json` 的 `notes`（v1.5 第（7）条改写 + 新增第（10）条）。

🔴 为什么必须改：
   第（7）条原文写「**语音分区新增 CUDA 选项** …… 集显上 7/7 成功」，
   这是 §32 的口径。本轮实测把它推翻了：
     - **ASR** 的 CUDA 选项仍然保留（另一种后端），但要说明「包内未随附 audio.cpp/GGUF」；
     - **TTS** 的 NVIDIA 选项已**移除**（7 个 IR 只过 3 个 ⇒ 引擎整体加载失败）；
     - **集显 f16** 能编过但**合成失控** ⇒ 也移除；集显 f32 可用但极慢。
   ⇒ 留着旧 note 就是「随包文档说谎」。

🔴 纪律：只改 `notes` 字符串，`files` / `bytes` / `version` / `packages` **一律不动**；
   格式保持原样（`ensure_ascii=False`、`indent=1`）。
"""
from __future__ import annotations

import io
import json
import os
import sys

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5"
P = os.path.join(PKG, 'app', 'MANIFEST.json')

NEW7 = (
    '（7）**ASR 语音分区新增 CUDA 选项 + 去重** —— NVIDIA 设备只在 **ASR** 列表里'
    '单列一条「NVIDIA GPU（CUDA）」（另一种后端：audio.cpp + GGUF）；原先同一块'
    '物理显卡还被 OpenVINO 档重复列成「NVIDIA 独显 · INT8」⇒ v1.5 已去重'
    '（**保留 CUDA 那条**，按物理设备而非 label 判定）。'
    '⚠️ 诚实警示：本包**未随附** audio.cpp 运行包与 GGUF 模型（包内无 cuda/ 目录），'
    '该选项在另行部署前不可用。'
)

NEW10 = (
    '（10）**语音输出只列「实测真的能用」的设备 × 精度组合** —— 实测（真实 INT8 IR '
    '+ 真实音色）：**Intel NPU · F16 可用**（7/7 编译；5.52 s 音频 / 6.4 s 合成）；'
    'Intel 集显 · F32 可用但**很慢**（5.68 s 音频需 88.7 s）；'
    '**Intel 集显 · F16 能编过但合成失控**（talker 不发结束符 ⇒ 跑满 512 帧 '
    '⇒ 40.96 s 削波音频 peak=1.000）；**NVIDIA 独显仅 3/7 编译**，且 F32 与 F16 '
    '失败**完全相同** ⇒ 引擎整体加载失败。'
    '⇒ 不可用组合**不再列出**（原因写在说明行，不静默隐藏）。'
    '同时修掉两个隐藏缺陷：① GUI 的「精度 F32/F16」下拉**从未生效**'
    '（make_engine 没有 precision 形参 → worker 不传 → BabelVox 自建 ov.Core 不传 '
    'property）⇒ 现已注入 INFERENCE_PRECISION_HINT；'
    '② GUI **完全不监视 TTS 状态** ⇒ 加载失败时界面零提示 ⇒ 现已加状态跟踪。'
)


def main() -> int:
    if not os.path.isfile(P):
        print('!! 找不到', P)
        return 2
    with io.open(P, 'r', encoding='utf-8') as f:
        d = json.load(f)
    s = d.get('notes') or ''
    if '（10）**语音输出只列' in s and '（7）**ASR 语音分区新增 CUDA 选项 + 去重**' in s:
        print('已是最新（幂等）：无需改动')
        return 0

    i7 = s.find('（7）')
    i8 = s.find('（8）', i7 if i7 >= 0 else 0)
    if i7 < 0 or i8 < 0:
        print('!! notes 里找不到（7）/（8）边界，拒绝盲改')
        return 3
    s = s[:i7] + NEW7 + s[i8:]

    if '（10）**语音输出只列' not in s:
        anchor = s.find('v1.4 修订')
        if anchor < 0:
            s = s.rstrip() + ' ' + NEW10
        else:
            s = s[:anchor] + NEW10 + s[anchor:]

    d['notes'] = s
    with io.open(P, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('notes 已更新：len=%d；files=%s bytes=%s version=%s'
          % (len(s), d.get('files'), d.get('bytes'), d.get('version')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
