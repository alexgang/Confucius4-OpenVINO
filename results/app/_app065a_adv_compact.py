#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：把「⑤ 高级」里的 4 条**提示文字**从「独占一行」改为
「**与控件同行（column 2）**」⇒ 高级组从 13 行压到 9 行（499 px → ~350 px）。

🔴 reviewer 要求：「高级里的每一项要有一句话提示说明作用。」
   ⇒ 提示**保留**，只是**不再独占一行**（横向排布）。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

reps = [
    # ① 区分说话人（克隆）
    ("""        ttk.Label(g_adv, text='检测谁在说话，换人时重新克隆音色；'
                  '只在音色=跟随说话人时生效',
                  foreground='#555').grid(row=7, column=1, sticky='w',
                                          padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='检测谁在说话，换人时重新克隆音色；'
                  '只在音色=跟随说话人时生效',
                  foreground='#555').grid(row=6, column=2, sticky='w',
                                          padx=(8, 0), pady=1)"""),
    # ② 离线朗读
    ("""        ttk.Label(g_adv, text='上传音频或输入文本直接播报，不经过识别与翻译',
                  foreground='#555').grid(row=9, column=1, sticky='w',
                                          padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='上传音频或输入文本直接播报，不经过识别与翻译',
                  foreground='#555').grid(row=7, column=2, sticky='w',
                                          padx=(8, 0), pady=1)"""),
    # ③ 测试声音
    ("""        ttk.Label(g_adv, text='播放 1 秒测试音，验证输出设备与播放链路',
                  foreground='#555').grid(row=11, column=1, sticky='w',
                                          padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='播放 1 秒测试音，验证输出设备与播放链路',
                  foreground='#555').grid(row=8, column=2, sticky='w',
                                          padx=(8, 0), pady=1)"""),
    # ④ 耳机提示
    ("""        ttk.Label(g_adv, text='避免 TTS 声音被 ASR 回采造成回授',
                  foreground='#b26a00').grid(row=12, column=1, sticky='w',
                                           padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='避免 TTS 声音被 ASR 回采造成回授',
                  foreground='#b26a00').grid(row=9, column=2, sticky='w',
                                           padx=(8, 0), pady=1)"""),
    # 行号顺延：离线朗读 8→7、测试声音 10→8、耳机 12→9
    ("""        ttk.Label(g_adv, text='离线朗读',
                  width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=8, column=0, sticky='e',
                                   padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='离线朗读',
                  width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=7, column=0, sticky='e',
                                   padx=(0, 8), pady=1)"""),
    ("""        self.btn_offline = ttk.Button(
            g_adv, text='📖 离线朗读…', width=16,
            command=self._open_offline_reader)
        self.btn_offline.grid(row=8, column=1, sticky='w', pady=1)""",
     """        self.btn_offline = ttk.Button(
            g_adv, text='📖 离线朗读…', width=16,
            command=self._open_offline_reader)
        self.btn_offline.grid(row=7, column=1, sticky='w', pady=1)"""),
    ("""        ttk.Label(g_adv, text='测试声音',
                  width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=10, column=0, sticky='e',
                                   padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='测试声音',
                  width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=8, column=0, sticky='e',
                                   padx=(0, 8), pady=1)"""),
    ("""        self.btn_tts_test = ttk.Button(g_adv, text='🔊 测试声音', width=14,
                                       command=self._on_tts_test_sound)
        self.btn_tts_test.grid(row=10, column=1, sticky='w', pady=1)""",
     """        self.btn_tts_test = ttk.Button(g_adv, text='🔊 测试声音', width=14,
                                       command=self._on_tts_test_sound)
        self.btn_tts_test.grid(row=8, column=1, sticky='w', pady=1)"""),
    ("""        ttk.Label(g_adv, text='⚠️ 戴耳机',
                  width=_GRID_LABEL_CHARS,
                  anchor='e', foreground='#b26a00').grid(
                      row=12, column=0, sticky='e', padx=(0, 8), pady=1)""",
     """        ttk.Label(g_adv, text='⚠️ 戴耳机',
                  width=_GRID_LABEL_CHARS,
                  anchor='e', foreground='#b26a00').grid(
                      row=9, column=0, sticky='e', padx=(0, 8), pady=1)"""),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)

# 高级组需要 column 2（提示列）
a = "        g_adv.columnconfigure(1, weight=1)"
b = ("        g_adv.columnconfigure(1, weight=0)" + _EOL +
     "        g_adv.columnconfigure(2, weight=1)")
assert txt.count(a) == 1, txt.count(a)
txt = txt.replace(a, b)

ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 高级组提示文字已改为同行（13 行 → 10 行）')
