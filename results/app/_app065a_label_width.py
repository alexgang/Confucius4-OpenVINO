#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：把标签列宽从「字符数」改成「**像素 minsize**」。

🔴 **为什么**：`ttk.Label(width=N)` 的 N 是**字符数** ⇒ 实际像素宽随
   **字体/缩放**变化 ⇒ 「标签列宽度一致」这个不变量在**不同缩放下不可比**
   （实测：100% 时右边缘 44 px、150% 时 92 px）。
   ⇒ 改成：`grid_columnconfigure(0, minsize=像素)` ＋ 标签**不设 width**
   ⇒ 标签列宽由**列 minsize**决定 ⇒ **所有组共用同一个值**
   ⇒ 组间**恒等**（且缩放时按比例变化，符合直觉）。
"""
import ast
import re

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

# ① 标签不再设 width（宽度由列 minsize 决定）
n = txt.count("width=_GRID_LABEL_CHARS,")
txt = txt.replace("width=_GRID_LABEL_CHARS,", "")
print('去掉 width 的标签数 =', n)

# ② 常量：字符数 → 像素（基准缩放 1.0 下的像素宽）
a = """# 🔴 **标签列宽（字符数）**：用 `tkfont` 度量最宽标签 ⇒ **每组等宽**。
#   ⚠️ 不用固定像素 ⇒ 换字体/换缩放（DPI）时**自动跟随**，不会错位。
_GRID_LABEL_CHARS = 8"""
b = """# 🔴 **标签列宽（像素）**：由 `grid_columnconfigure(0, minsize=…)` 统一控制。
#   ⚠️ **不用 `ttk.Label(width=N)`**（N 是**字符数** ⇒ 像素宽随字体/缩放变
#      ⇒ 不同缩放下不可比，APP-065 A 的「标签列宽度一致」会失效；
#      实测 100% 时右边缘 44 px、150% 时 92 px）。
#   ⇒ 标签**不设 width**；宽度 = 列 minsize ⇒ **所有组共用同一个像素值**
#      ⇒ 组间**恒等**，且随缩放按比例变化（符合直觉）。
_GRID_LABEL_PX = 64"""
assert txt.count(a) == 1, txt.count(a)
txt = txt.replace(a, b)

# ③ 每个组的 columnconfigure(0) 加 minsize
a = "g_in.columnconfigure(0, weight=0, uniform='lbl')"
b = "g_in.columnconfigure(0, weight=0, uniform='lbl', minsize=_GRID_LABEL_PX)"
assert txt.count(a) == 1
txt = txt.replace(a, b)
for g in ('g_asr', 'g_mt', 'g_tts', 'g_adv'):
    a = "%s.columnconfigure(0, weight=0, uniform='lbl')" % g
    b = ("%s.columnconfigure(0, weight=0, uniform='lbl',"
         " minsize=_GRID_LABEL_PX)" % g)
    assert txt.count(a) == 1, (g, txt.count(a))
    txt = txt.replace(a, b)

ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 标签列宽已改为像素 minsize（所有组共用 _GRID_LABEL_PX）')
