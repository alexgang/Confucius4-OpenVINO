#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A 修两处：

① `_adv_frame`（高级组的内容容器）**从未 pack** ⇒ 展开「⑤ 高级」是**空的**
   （实测：高级组 h=1，内容不可见）⇒ 现在 pack 进 `_adv_group`。
② `cb_source`（音频来源）用了 `width=12` ⇒ 与其它组的控件**不同宽**
   （实测 107 px vs 233 px）⇒ 违反 reviewer 的「控件列左对齐、**同宽**」
   ⇒ 改成 `_GRID_CTRL_CHARS`。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

reps = [
    # ① pack 高级组内容容器
    ("        self._adv_frame = ttk.Frame(self._adv_group, padding=(0, 2))",
     "        self._adv_frame = ttk.Frame(self._adv_group, padding=(0, 2))" + _EOL +
     "        # 🔴🔴🔴 APP-065 A：**必须 pack 进 `_adv_group`**" + _EOL +
     "        #   ⇒ 否则展开「⑤ 高级」时**内容是空的**（实测 h=1）。" + _EOL +
     "        self._adv_frame.pack(fill='x')"),
    # ② 音频来源下拉与其它组同宽
    ("        self.cb_source = ttk.Combobox(" + _EOL +
     "            g_in, state='readonly', width=12,",
     "        self.cb_source = ttk.Combobox(" + _EOL +
     "            g_in, state='readonly', width=_GRID_CTRL_CHARS,"),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 高级组内容已 pack ＋ 音频来源下拉已统一宽度')
