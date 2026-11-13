#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app541_patch_readme_special.py —— 修正 Special MVP README 里的**过时口径**（定点替换 + 唯一命中断言）。

要改的（都是 rc11 的旧口径，与本包不符）：
  ① 「翻译设备默认 **GPU.0**」⇒ 本包 MT 默认 **NPU**；
  ② 「A 机实测」整链那行（rc11 的 ASR=GPU.0/MT=GPU.0/TTS=NPU 数字）⇒ 换成本包
     **ASR=GPU.0／MT=NPU／TTS=CUDA** 的实测数字；
  ③ 「克隆音色（MiniMVP 禁用…）」⇒ Special MVP 禁用。
"""
import os
import sys

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1"

# ── zh 版 ──
p = os.path.join(PKG, 'README_zh.md')
txt = open(p, encoding='utf-8').read()
orig_len = len(txt.encode('utf-8'))

REPL = [
    # ① MT 默认设备
    ('⇒ **本包只带 INT8-CW，不再带 INT4**（APP-107）；翻译设备默认 **GPU.0**。',
     '⇒ **本包只带 INT8-CW，不再带 INT4**（APP-107）；**翻译设备默认 Intel NPU**。'),
    # ③ 克隆音色措辞
    ('**克隆音色**（MiniMVP 禁用 ⇒ 只有内置预设音色）',
     '**克隆音色**（Special MVP 禁用 ⇒ 只有内置预设音色 A）'),
]
for old, new in REPL:
    n = txt.count(old)
    if n != 1:
        sys.exit('锚点命中 %d 次（应恰好 1 次）：%r' % (n, old[:70]))
    txt = txt.replace(old, new)

# ② 整链实测行：整行替换（以行首定位 ⇒ 只改这一行）
lines = txt.split('\n')
hit = 0
for i, ln in enumerate(lines):
    if ln.startswith('> · **本包出厂默认（ASR=GPU.0 / MT=GPU.0（INT8-CW）/ TTS=NPU）的包目录整链**'):
        lines[i] = (
            '> · **本包出厂默认（ASR=GPU.0 / MT=NPU（INT8-CW）/ TTS=CUDA）的包目录整链**'
            '（A 机 RTX 5050，2026-11-13，10 分钟片段）：'
            '**ASR RTF 0.522**（600 s 音频 / 墙钟 600.5 s / 出字延迟中位 292 ms / 93 段）；'
            '**翻译落点 NPU**：句数 163 / 延迟中位 **898.8 ms** / P95 **1273.5 ms** / '
            '首字 **535.4 ms** / **31.2 tok/s**；'
            '**TTS 由 NVIDIA RTX 5050 合成**（torch 2.11.0+cu128 / bfloat16）：'
            '**提交 152 / 播完 142 / 丢弃 10**，**首包 0.44 s**，'
            '产出 **612.84 s @ 24 000 Hz**（逐句时间线与积压曲线同落盘）')
        hit += 1
if hit != 1:
    sys.exit('整链实测行命中 %d 次（应恰好 1 次）' % hit)
txt = '\n'.join(lines)

# 追加：CUDA 首次加载提示（放「首次启动」那段之后）
anchor = '> **磁盘**：首次运行约需 **8 GB**（编译缓存）。'
add = (anchor + '\n'
       '> **Special MVP 的 CUDA 语音**：首次启动时**边车要加载 0.6B 模型**'
       '（实测 **58.7 s**，含 warmup 1.9 s）⇒ **第一次出声会明显慢**；'
       '之后常驻，不再重复加载。')
if txt.count(anchor) != 1:
    sys.exit('磁盘行命中异常')
txt = txt.replace(anchor, add)

open(p, 'w', encoding='utf-8', newline='\n').write(txt)
print('README_zh.md：%d B -> %d B（6 处定点替换，全部唯一命中）'
      % (orig_len, len(txt.encode('utf-8'))))

# ── en 版（若存在同样口径的行）──
pe = os.path.join(PKG, 'README_en.md')
if os.path.isfile(pe):
    t = open(pe, encoding='utf-8').read()
    changed = 0
    for old, new in (
        ('TTS=Intel NPU', 'TTS=CUDA (NVIDIA RTX 5050)'),
        ('MT=Intel GPU', 'MT=Intel NPU'),
    ):
        if t.count(old) == 1:
            t = t.replace(old, new)
            changed += 1
    if changed:
        open(pe, 'w', encoding='utf-8', newline='\n').write(t)
    print('README_en.md：改了 %d 处（只改**唯一命中**的）' % changed)
