#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：修最后两处 150 % 下的轻微截断。

① 顶栏「有模块待处理」按钮：`width=16` 仍不够（150 % 下中文更宽）
   ⇒ 改成 `width=18`。
② ① 组说明文字「采集麦克风（重采样到 16 kHz）」在 150 % + 物理宽 1080 下
   末尾被裁 ⇒ 再缩短成「采集麦克风（16 kHz）」。
   ⚠️ 说明文字**已移到 column 3**（独立列）⇒ 不会再撑宽设备控件列。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

reps = [
    ("""            # 🔴🔴🔴 APP-065 A：`width=12` 在 **150 % 缩放**下不够
            #   ⇒ 「有模块待处理」被**裁掉**（实测截图）
            #   ⇒ 改成 16（150 % 下也不裁）。
            width=16,""",
     """            # 🔴🔴🔴 APP-065 A：`width=12` 在 **150 % 缩放**下不够
            #   ⇒ 「有模块待处理」被**裁掉**（实测截图）
            #   ⇒ 改成 18（150 % 下也不裁）。
            width=18,"""),
    ("self.var_source_note.set('采集麦克风（重采样到 16 kHz）')",
     "self.var_source_note.set('采集麦克风（16 kHz）')"),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:70]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 顶栏按钮 width=18 ＋ ① 组说明文字再缩短')
