#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 ④ 语音输出组恢复为**唯一标签列**（column 0）+ 3 行控件。

🔴 **CRLF 陷阱**：文件是 CRLF ⇒ `read().decode()` 后每行末尾仍有 `\r`
   ⇒ 用 `\n` 拼的多行匹配串**匹配不上** ⇒ 必须**按行处理**或用 `\r\n`。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'
print('EOL = CRLF' if _EOL=='\r\n' else 'EOL = LF')

reps = [
    ("self.cb_tts_voice.grid(row=0, column=3, sticky='w', pady=1)",
     "self.cb_tts_voice.grid(row=1, column=1, sticky='w', pady=1)"),
    ("foreground='#1565c0').grid(row=0, column=4, sticky='w',",
     "foreground='#1565c0').grid(row=1, column=2, sticky='w',"),
    ("text='输出设备', width=_GRID_LABEL_CHARS," + _EOL +
     "                  anchor='e').grid(row=1, column=0, sticky='e',",
     "text='输出设备', width=_GRID_LABEL_CHARS," + _EOL +
     "                  anchor='e').grid(row=2, column=0, sticky='e',"),
    ("self.cb_tts_out.grid(row=1, column=1, sticky='w', pady=1)",
     "self.cb_tts_out.grid(row=2, column=1, sticky='w', pady=1)"),
    ("grid_row=0, grid_col=5,", "grid_row=0, grid_col=3,"),
    ("                                                   grid_rowspan=2)",
     "                                                   grid_rowspan=3)"),
    ("        g_tts.columnconfigure(2, weight=0, uniform='lbl2')" + _EOL +
     "        g_tts.columnconfigure(3, weight=0)" + _EOL +
     "        g_tts.columnconfigure(4, weight=0)" + _EOL +
     "        g_tts.columnconfigure(5, weight=1)",
     "        g_tts.columnconfigure(2, weight=0)" + _EOL +
     "        g_tts.columnconfigure(3, weight=1)"),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:70]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0), '行尾风格被改变'
open(P, 'wb').write(out)
print('OK ④ 组已恢复为唯一标签列（3 行控件）')
