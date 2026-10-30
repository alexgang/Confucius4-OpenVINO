#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在 §114 草稿里补入「§112 归档」与「独立复核 17 PASS」两行。"""
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_sec114_body.md')
t = open(P, encoding='utf-8').read()

OLD = '- 🔴 **本条需等 reviewer 复核**：'
ADD = (
    '- 🔴🔴 **为满足 APP-049 限额（STATUS ≤ 40 KB / ≤ 300 行 / 每节 ≤ 60 行），'
    '本轮把 §112 正文移入只读归档** `status/archive/STATUS_APP_sec109_113_upto_20261030.md`'
    '（**内容一字未删** ⇒ 独立复核 V11 锚点 5/5 全中）⇒ STATUS 内 §112 改为**一行指针**'
    '（V12：§112 段 928 B）⇒ 现 **37 974 B / 229 行**（追加前 33 971 B / 204 行；'
    '只追加 + 归档 ⇒ 净增 4 003 B）。\n'
    '- ✅ **独立复核 `results/app/app169_status_selfcheck.py` ⇒ 17 PASS / 0 FAIL**'
    '（V11/V12/V13 为本轮**新增**：归档内容一字未删 / §112 确为指针 / '
    '**§114 声明的判据数 == 证据 JSON 内 `n_pass`** ⇒ 直接堵住'
    '「判据 PASS 却没有落进证据」的自指缺口）。\n'
)

assert OLD in t, '§114 草稿：未找到插入点'
assert ADD not in t, '§114 草稿：已插入过（不要重复）'
t = t.replace(OLD, ADD + OLD, 1)
open(P, 'w', encoding='utf-8', newline='').write(t)

raw = open(P, 'rb').read()
print('OK bytes=%d lines=%d' % (len(raw), len(raw.decode('utf-8').split('\n'))))
