#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：把「⑤ 高级」**剩余** 2 条提示文字也移到 **column 2**（同行）。

现状：4 条提示里只有 2 条移到了 column 2；另 2 条（测试声音 / 耳机）
     仍**独占一行**（row 11 / row 12）⇒ 高级组多占 2 行。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

reps = [
    ("""        ttk.Label(g_adv, text='播放 1 秒测试音，验证输出设备与播放链路',
                  foreground='#555').grid(row=11, column=1, sticky='w',
                                          padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='播放 1 秒测试音，验证输出设备与播放链路',
                  foreground='#555').grid(row=8, column=2, sticky='w',
                                          padx=(8, 0), pady=1)"""),
    ("""        ttk.Label(g_adv, text='避免 TTS 声音被 ASR 回采造成回授',
                  foreground='#b26a00').grid(row=12, column=1, sticky='w',
                                           padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='避免 TTS 声音被 ASR 回采造成回授',
                  foreground='#b26a00').grid(row=9, column=2, sticky='w',
                                           padx=(8, 0), pady=1)"""),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 高级组剩余 2 条提示已移到 column 2')
