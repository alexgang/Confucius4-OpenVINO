#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：修 150 % 缩放下实测到的**两处横向截断**。

① **① 音频输入组的说明文字被右边界截断**
   根因：`lbl_source_note` 用 `pack(side='left')` 放在 `_g_in_dev`（设备控件容器）里
   ⇒ 它的 `reqwidth` 会**把整个 column 2 撑宽** ⇒ 超出窗口 ⇒ 被裁。
   ⇒ 修法：**把说明文字移出设备容器**（放到 ① 组的 **column 3**）
      ＋ **缩短文案**（缩短后不会撑宽 column 3）。
      ⇒ 设备控件列（column 2）恢复自适应宽度。

② **顶栏「有模块待处理」按钮文字被裁**
   根因：`width=12`（字符数）在 150 % 下不够。
   ⇒ 修法：`width=16`。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

reps = [
    # ② 顶栏按钮加宽
    ("""        self.btn_global_light = ttk.Button(
            top, textvariable=self._global_light, width=12,
            command=self._show_global_status)""",
     """        self.btn_global_light = ttk.Button(
            top, textvariable=self._global_light,
            # 🔴🔴🔴 APP-065 A：`width=12` 在 **150 % 缩放**下不够
            #   ⇒ 「有模块待处理」被**裁掉**（实测截图）
            #   ⇒ 改成 16（150 % 下也不裁）。
            width=16,
            command=self._show_global_status)"""),
    # ① 说明文字移出设备容器
    ("""        self.var_source_note = tk.StringVar(value='')
        self.lbl_source_note = ttk.Label(self._g_in_dev,
                                         textvariable=self.var_source_note,
                                         foreground='#555')
        self.lbl_source_note.pack(side='left', padx=(10, 0))""",
     """        self.var_source_note = tk.StringVar(value='')
        # 🔴🔴🔴 APP-065 A：说明文字**放在 ① 组的 column 3**（**不放**设备容器里）
        #   ⇒ 否则它的 `reqwidth` 会把 column 2 撑宽 ⇒ **右侧被裁**（150 % 实测）。
        #   ⚠️ 文案已缩短（见 `_sync_source_widgets`）⇒ 不会撑宽 column 3。
        self.lbl_source_note = ttk.Label(g_in,
                                         textvariable=self.var_source_note,
                                         foreground='#555')
        self.lbl_source_note.grid(row=0, column=3, sticky='w',
                                  padx=(12, 0), pady=1)"""),
    # ① 组增加 column 3
    ("""        g_in.columnconfigure(0, weight=0, uniform='lbl', minsize=_GRID_LABEL_PX)
        g_in.columnconfigure(1, weight=0)
        g_in.columnconfigure(2, weight=1)""",
     """        g_in.columnconfigure(0, weight=0, uniform='lbl', minsize=_GRID_LABEL_PX)
        g_in.columnconfigure(1, weight=0)
        g_in.columnconfigure(2, weight=0)
        g_in.columnconfigure(3, weight=1)"""),
    # ① 文案缩短
    ("self.var_source_note.set('采集麦克风；设备原生采样率会重采样到 16 kHz')",
     "self.var_source_note.set('采集麦克风（重采样到 16 kHz）')"),
    ("self.var_source_note.set('采集系统正在播放的声音（WASAPI 回环），不占用麦克风')",
     "self.var_source_note.set('采集系统声音（WASAPI 回环）')"),
    ("self.var_source_note.set('未找到可回环的输出设备（需要 Windows WASAPI）')",
     "self.var_source_note.set('未找到可回环的输出设备')"),
    ("self.var_source_note.set('回放本地音频文件；可按实时速度播放')",
     "self.var_source_note.set('回放本地音频文件（可调速）')"),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 两处横向截断已修（① 组说明文字移到 column 3 + 文案缩短；顶栏按钮加宽）')
