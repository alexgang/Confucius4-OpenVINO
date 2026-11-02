#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：把各组 grid 行的 `pady=1` 收到 `pady=0`
⇒ 每行省 2 px ⇒ 4 组 × 平均 1.5 行 ≈ 12 px ⇒ 字幕区 +1.5 %。

🔴 只动**行间距**，不动控件高度与标签列宽 ⇒
   「标签列宽度一致」「控件列同宽」「行高一致」三个不变量**不受影响**。
"""
import ast
import re

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

# 只在 **grid(...) 调用** 里的 pady=1 ⇒ 改成 pady=0
n = len(re.findall(r'pady=1\)', txt))
txt2 = re.sub(r'(grid\([^)]*?)pady=1\)', r'\1pady=0)', txt)
# 跨行的 grid 调用（padx 在上一行、pady 在下一行）也要改
n2 = len(re.findall(r'pady=1\)', txt2))
txt2 = txt2.replace('pady=1)', 'pady=0)')
ast.parse(txt2)
out = txt2.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK pady=1 → pady=0（%d 处）' % n)
