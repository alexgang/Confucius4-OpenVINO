#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：进一步压缩顶部占用（提高字幕区占比）。

改动：
1. 各组 LabelFrame 的 `padding=(6, 2)` → `(6, 0)`（省 4 px/组）
2. 组间 `pady=(0, 2)` → `pady=(0, 1)`（省 1 px/间隙）
3. `_groups` 的 `padding=(8, 2)` → `(8, 0)`
4. **全局状态行并入顶栏**（`_lbl_status` 的父容器 root → top）
   ⇒ 省掉独立一行的 pack 间隙 + 独立行高的一部分
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

reps = [
    # ① 各组 LabelFrame padding
    ("f_in = ttk.LabelFrame(self._groups, text='① 音频输入', padding=(6, 2))",
     "f_in = ttk.LabelFrame(self._groups, text='① 音频输入', padding=(6, 0))"),
    ("f_asr = ttk.LabelFrame(self._groups, text='② 语音识别', padding=(6, 2))",
     "f_asr = ttk.LabelFrame(self._groups, text='② 语音识别', padding=(6, 0))"),
    ("f_mt = ttk.LabelFrame(self._groups, text='③ 翻译', padding=(6, 2))",
     "f_mt = ttk.LabelFrame(self._groups, text='③ 翻译', padding=(6, 0))"),
    ("f_tts = ttk.LabelFrame(self._groups, text='④ 语音输出', padding=(6, 2))",
     "f_tts = ttk.LabelFrame(self._groups, text='④ 语音输出', padding=(6, 0))"),
    ("self._adv_group = ttk.LabelFrame(self._groups, text='⑤ 高级'," + _EOL +
     "                                          padding=(6, 2))",
     "self._adv_group = ttk.LabelFrame(self._groups, text='⑤ 高级'," + _EOL +
     "                                          padding=(6, 0))"),
    # ② 组间间距
    ("f_in.pack(fill='x', pady=(0, 2))", "f_in.pack(fill='x', pady=(0, 1))"),
    ("f_asr.pack(fill='x', pady=(0, 2))", "f_asr.pack(fill='x', pady=(0, 1))"),
    ("f_mt.pack(fill='x', pady=(0, 2))", "f_mt.pack(fill='x', pady=(0, 1))"),
    ("f_tts.pack(fill='x', pady=(0, 2))", "f_tts.pack(fill='x', pady=(0, 1))"),
    # ③ 容器 padding
    ("self._groups = ttk.Frame(root, padding=(8, 2))",
     "self._groups = ttk.Frame(root, padding=(8, 0))"),
    # ④ 全局状态行并入顶栏
    ("""        self._lbl_status = tk.Label(root, textvariable=self.var_status,""" + _EOL +
     """                                    foreground='#555', anchor='w', justify='left',""" + _EOL +
     """                                    background=self._ttk_bg())""" + _EOL +
     """        self._lbl_status.pack(fill='x', padx=10, pady=(0, 1))""",
     """        # 🔴🔴🔴 APP-065 A：**全局状态行并入顶栏**（父容器 root → top）
        #   ⇒ 省掉**独立一行**的 pack 间隙与行高（实测省 ~10 px）
        #   ⇒ 字幕区占比提升。
        #   ⚠️ **仍是一整行**（长消息不截断，APP-048 的要求不变）。
        self._lbl_status = tk.Label(top, textvariable=self.var_status,""" + _EOL +
     """                                    foreground='#555', anchor='w', justify='left',""" + _EOL +
     """                                    background=self._ttk_bg())""" + _EOL +
     """        self._lbl_status.pack(fill='x', padx=10, pady=(0, 1))"""),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0), '行尾风格被改变'
open(P, 'wb').write(out)
print('OK 顶部占用已压缩（padding / 间距 / 状态行并入顶栏）')
