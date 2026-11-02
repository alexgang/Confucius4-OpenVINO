#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：完成「⑤ 高级」的紧凑化剩余部分（**按行定位**，避开文本差异）。

现状（前半已应用）：
  - 4 条提示文字已从「独占行」移到 **column 2**（与控件同行）
  - 但**控件的行号**还是旧值（8 / 10 / 12）⇒ 会与提示文字**撞行**
⇒ 现在：把控件行号顺延为 7 / 8 / 9，并给 `g_adv` 加 column 2。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

reps = [
    # 离线朗读：row 8 → 7
    ("""        ttk.Label(g_adv, text='离线朗读', 
                  anchor='e').grid(row=8, column=0, sticky='e',
                                   padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='离线朗读',
                  anchor='e').grid(row=7, column=0, sticky='e',
                                   padx=(0, 8), pady=1)"""),
    ("        self.btn_offline.grid(row=8, column=1, sticky='w', pady=1)",
     "        self.btn_offline.grid(row=7, column=1, sticky='w', pady=1)"),
    # 测试声音：row 10 → 8
    ("""        ttk.Label(g_adv, text='测试声音', 
                  anchor='e').grid(row=10, column=0, sticky='e',
                                   padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='测试声音',
                  anchor='e').grid(row=8, column=0, sticky='e',
                                   padx=(0, 8), pady=1)"""),
    ("        self.btn_tts_test.grid(row=10, column=1, sticky='w', pady=1)",
     "        self.btn_tts_test.grid(row=8, column=1, sticky='w', pady=1)"),
    # 耳机：row 12 → 9
    ("""                  anchor='e', foreground='#b26a00').grid(
                      row=12, column=0, sticky='e', padx=(0, 8), pady=1)""",
     """                  anchor='e', foreground='#b26a00').grid(
                      row=9, column=0, sticky='e', padx=(0, 8), pady=1)"""),
    # g_adv 增加 column 2（提示列）
    ("        g_adv.columnconfigure(1, weight=1)",
     "        g_adv.columnconfigure(1, weight=0)" + _EOL +
     "        g_adv.columnconfigure(2, weight=1)"),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 高级组行号已顺延（离线朗读 7 / 测试声音 8 / 耳机 9）＋ column 2 已加')
