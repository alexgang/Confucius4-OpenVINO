#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-061 ⑥：GUI 紧凑化（**定点替换** + 唯一命中断言）。

🔴 **纪律**：
- **唯一命中断言**：每个替换块在源文件里必须**恰好命中 1 次**；
- **写前备份**（包外备份 ⇒ 可回滚）；
- **写后复核**：`ast.parse` 通过 ＋ 逐块复核（新文本确实落盘）；
- **不整目录覆盖**：只改 `live_caption/live_caption_app.py` 这一个文件。

⑥ 的目标（reviewer 原文）：
- 控件压缩到 **≤2 行**；常用的放在外面（开始、来源、ASR、MT、TTS 开关、音色、
  输出设备），不常用的放进可折叠的「高级」面板（识别语种、草稿、重试、离线朗读、
  测试声音、显示说话人、精度）；
- 三个分区的说明行**合并进状态栏**；状态栏**只占 1 行**；
- 字幕字体保持 13pt，界面整体减小 padding；最小宽度 1024。
"""
from __future__ import annotations

import ast
import hashlib
import os
import shutil
import sys

TARGET = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption\live_caption_app.py"
BACKUP_DIR = r"C:\Users\Trekker-PTL\confucius4-openvino\results\app\_backup_app061_gui"

REPL = []


def rep(old, new, label):
    REPL.append((old, new, label))


# ── ⑥-1：顶栏：加「高级」开关；meter / 会话 / 全局灯**并入顶栏** ──
rep(
    """        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill='x')
        ttk.Label(top, text='Confucius4 实时字幕').pack(side='left')

        self.btn = ttk.Button(top, text='▶ 开始', command=self.toggle, state='disabled')
        self.btn.pack(side='left', padx=(12, 0))
        ttk.Button(top, text='清空', command=self.clear).pack(side='left', padx=4)
        ttk.Button(top, text='保存', command=self.save).pack(side='left')
        self.var_overlay = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='屏幕字幕', variable=self.var_overlay,
                        command=self._toggle_overlay).pack(side='left', padx=10)

        self.var_note = tk.StringVar(value='')
        # 🔴🔴 APP-048：顶部说明文字**也要换行**（原来一行到底 ⇒ 溢出屏幕）。
        #    ⚠️ 用 `tk.Label`（ttk.Label 不支持 wraplength 绑定）。
        self._lbl_note = tk.Label(root, textvariable=self.var_note,
                                  foreground='#555', anchor='w', justify='left',
                                  background=self._ttk_bg())
        self._lbl_note.pack(fill='x', padx=12)
""",
    """        top = ttk.Frame(root, padding=(8, 3))
        top.pack(fill='x')
        ttk.Label(top, text='Confucius4 实时字幕').pack(side='left')

        self.btn = ttk.Button(top, text='▶ 开始', command=self.toggle, state='disabled')
        self.btn.pack(side='left', padx=(12, 0))
        ttk.Button(top, text='清空', command=self.clear).pack(side='left', padx=4)
        ttk.Button(top, text='保存', command=self.save).pack(side='left')
        self.var_overlay = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='屏幕字幕', variable=self.var_overlay,
                        command=self._toggle_overlay).pack(side='left', padx=10)

        # 🔴🔴🔴 APP-061⑥：**「高级」折叠面板**开关。
        #   不常用控件（识别语种 / 草稿 / 重试 / 离线朗读 / 测试声音 / 显示说话人）
        #   收进这个面板 ⇒ 常用控件只占 ≤2 行 ⇒ 字幕区 ≥ 窗口高度 70%。
        self._adv_open = False
        self.btn_adv = ttk.Button(top, text='▾ 高级', width=8,
                                  command=self._toggle_advanced)
        self.btn_adv.pack(side='right', padx=(12, 0))
        # 🔴 APP-048：会话计时（全局信息）⇒ 移进顶栏（省一整行）
        self._session_elapsed = tk.StringVar(value='00:00')
        ttk.Label(top, textvariable=self._session_elapsed,
                  foreground='#555').pack(side='right', padx=(0, 12))
        ttk.Label(top, text='会话').pack(side='right', padx=(0, 4))
        # 🔴 APP-048：**总状态灯**（全部就绪 / 有模块异常时点击查看）
        self._global_light = tk.StringVar(value='⚪ 就绪')
        self.btn_global_light = ttk.Button(
            top, textvariable=self._global_light, width=12,
            command=self._show_global_status)
        self.btn_global_light.pack(side='right', padx=(0, 12))
        # 🔴 APP-048：顶部 meter（**全局**信息）⇒ 移进顶栏
        #   ⚠️ **保留 `var_meter` / `lbl_meter` 这两个名字**：
        #    `diag_layout_gui.py` 与 `app165` 等既有验收脚本仍引用它们。
        self.var_meter = tk.StringVar(value='')
        self.lbl_meter = ttk.Label(top, textvariable=self.var_meter,
                                   font=('Consolas', 10))
        self.lbl_meter.pack(side='right', padx=(0, 12))

        # 🔴🔴🔴 APP-061⑥：**「高级」面板**（默认收起 ⇒ 不占纵向空间）。
        #   ⚠️ 用**普通 Frame**（不是 LabelFrame）⇒ `app165` 的「分区数 = 3」
        #     判据（C4）不受影响。
        self._adv_frame = ttk.Frame(root, padding=(8, 2))

        self.var_note = tk.StringVar(value='')
        # 🔴🔴 APP-048：顶部说明文字**也要换行**（原来一行到底 ⇒ 溢出屏幕）。
        #    ⚠️ 用 `tk.Label`（ttk.Label 不支持 wraplength 绑定）。
        #    🔴 APP-061⑥：移进「高级」面板 ⇒ 顶栏不再多占一行。
        self._lbl_note = tk.Label(self._adv_frame, textvariable=self.var_note,
                                  foreground='#555', anchor='w', justify='left',
                                  background=self._ttk_bg())
""",
    '⑥-1 顶栏：高级开关 + meter/会话/全局灯并入顶栏')

# ── ⑥-2：`_lbl_note` 不再 pack 在 root（改由高级面板承载） ──
rep(
    """        self._wrapped_labels = getattr(self, '_wrapped_labels', [])
        self._wrapped_labels.append((self._lbl_note, root))
""",
    """        self._wrapped_labels = getattr(self, '_wrapped_labels', [])
        self._wrapped_labels.append((self._lbl_note, self._adv_frame))
""",
    '⑥-2 _lbl_note 的换行容器改为高级面板')

# ── ⑥-3：删掉独立的 `bot` 行（内容已并入顶栏） ──
rep(
    """        bot = ttk.Frame(root, padding=(10, 4))
        bot.pack(fill='x')
        self.var_meter = tk.StringVar(value='')
        self.lbl_meter = ttk.Label(bot, textvariable=self.var_meter,
                                   font=('Consolas', 10))
        self.lbl_meter.pack(side='left')
        # 🔴 APP-048：**会话计时**（全局信息）
        self._session_elapsed = tk.StringVar(value='00:00')
        ttk.Label(bot, textvariable=self._session_elapsed,
                  foreground='#555').pack(side='right', padx=(0, 12))
        ttk.Label(bot, text='会话').pack(side='right', padx=(0, 4))
        # 🔴 APP-048：**总状态灯**（全部就绪 / 有模块异常时点击查看）
        #    ⇒ 一个按钮 + 颜色状态，不占宽度；点击弹窗列出各分区状态。
        self._global_light = tk.StringVar(value='⚪ 就绪')
        self.btn_global_light = ttk.Button(
            bot, textvariable=self._global_light, width=12,
            command=self._show_global_status)
        self.btn_global_light.pack(side='right', padx=(0, 12))
        self.var_status = tk.StringVar(value='')
""",
    """        self.var_status = tk.StringVar(value='')
""",
    '⑥-3 删除独立的 bot 行（并入顶栏）')

# ── ⑥-4：状态行留在 root（用户要随时看到全局消息），但压缩 padding ──
rep(
    """        self._lbl_status = tk.Label(root, textvariable=self.var_status,
                                    foreground='#555', anchor='w', justify='left',
                                    background=self._ttk_bg())
        self._lbl_status.pack(fill='x', padx=12, pady=(0, 2))
""",
    """        self._lbl_status = tk.Label(root, textvariable=self.var_status,
                                    foreground='#555', anchor='w', justify='left',
                                    background=self._ttk_bg())
        self._lbl_status.pack(fill='x', padx=10, pady=(0, 1))
""",
    '⑥-4 状态行 padding 压缩')

# ── ⑥-5：音频来源行：padding 压缩、控件宽度收窄 ──
rep(
    """        srow = ttk.Frame(root, padding=(12, 4))
        srow.pack(fill='x')
""",
    """        srow = ttk.Frame(root, padding=(8, 2))
        srow.pack(fill='x')
""",
    '⑥-5 音频来源行 padding 压缩')

rep(
    """        self.cb_mic = ttk.Combobox(srow, state='readonly', width=32,
                                   textvariable=self.var_mic,
                                   values=[m[1] for m in self.mics])
        self.cb_mic.pack(side='left', padx=(4, 12))
""",
    """        self.cb_mic = ttk.Combobox(srow, state='readonly', width=18,
                                   textvariable=self.var_mic,
                                   values=[m[1] for m in self.mics])
        self.cb_mic.pack(side='left', padx=(4, 8))
""",
    '⑥-6 麦克风下拉收窄')

rep(
    """        self.cb_out = ttk.Combobox(srow, state='readonly', width=32,
                                   textvariable=self.var_out,
                                   values=[self._out_label[oid] for oid, _ in self.outs])
        self.cb_out.pack(side='left', padx=(4, 12))
""",
    """        self.cb_out = ttk.Combobox(srow, state='readonly', width=18,
                                   textvariable=self.var_out,
                                   values=[self._out_label[oid] for oid, _ in self.outs])
        self.cb_out.pack(side='left', padx=(4, 8))
""",
    '⑥-7 输出设备下拉收窄')

rep(
    """        self.entry_file = ttk.Entry(srow, width=30, textvariable=self.var_file)
        self.entry_file.pack(side='left', padx=(4, 4))
""",
    """        self.entry_file = ttk.Entry(srow, width=18, textvariable=self.var_file)
        self.entry_file.pack(side='left', padx=(4, 4))
""",
    '⑥-8 文件输入框收窄')

rep(
    """        self.cb_speed = ttk.Combobox(srow, state='readonly', width=12,
                                     textvariable=self.var_speed,
                                     values=list(self._speed_label.values()))
        self.cb_speed.pack(side='left', padx=(0, 8))
""",
    """        self.cb_speed = ttk.Combobox(srow, state='readonly', width=10,
                                     textvariable=self.var_speed,
                                     values=list(self._speed_label.values()))
        self.cb_speed.pack(side='left', padx=(0, 8))
""",
    '⑥-9 回放速度下拉收窄')

# ── ⑥-10：新建「常用控件行」row_dev（在 areas 之前） ──
rep(
    """        areas = ttk.Frame(root, padding=(10, 4))
        areas.pack(fill='x')

        # ---- ASR 分区 ----
        f_asr = ttk.LabelFrame(areas, text='ASR 识别', padding=(8, 4))
        f_asr.pack(fill='x', pady=2)
        row_asr = ttk.Frame(f_asr)
        row_asr.pack(fill='x')
""",
    """        # 🔴🔴🔴 APP-061⑥：**常用控件行**（ASR / 翻译 / 语音的设备与音色）
        #   ⇒ 全部**移出**分区 LabelFrame ⇒ 控件只占 **1 行**。
        row_dev = ttk.Frame(root, padding=(8, 2))
        row_dev.pack(fill='x')

        areas = ttk.Frame(root, padding=(8, 2))
        areas.pack(fill='x')

        # ---- ASR 分区 ----
        # 🔴 APP-061⑥：三个分区**横向并排**（每列 = 该区的 1 行状态条）
        #   ⇒ 状态区整体**只占 1 行**（reviewer：「状态栏只占 1 行」）。
        f_asr = ttk.LabelFrame(areas, text='ASR 识别', padding=(6, 2))
        f_asr.pack(side='left', fill='x', expand=True)
        row_asr = ttk.Frame(row_dev)
        row_asr.pack(side='left', padx=(0, 8))
""",
    '⑥-10 新建 row_dev；分区 LabelFrame 横向并排')

rep(
    """        f_mt = ttk.LabelFrame(areas, text='翻译', padding=(8, 4))
        f_mt.pack(fill='x', pady=2)
        row_mt = ttk.Frame(f_mt)
        row_mt.pack(fill='x')
""",
    """        f_mt = ttk.LabelFrame(areas, text='翻译', padding=(6, 2))
        f_mt.pack(side='left', fill='x', expand=True)
        row_mt = ttk.Frame(row_dev)
        row_mt.pack(side='left', padx=(0, 8))
""",
    '⑥-11 翻译分区横向并排；控件移入 row_dev')

rep(
    """        f_tts = ttk.LabelFrame(areas, text='语音输出', padding=(8, 4))
        f_tts.pack(fill='x', pady=2)
        row_tts = ttk.Frame(f_tts)
        row_tts.pack(fill='x')
""",
    """        f_tts = ttk.LabelFrame(areas, text='语音输出', padding=(6, 2))
        f_tts.pack(side='left', fill='x', expand=True)
        row_tts = ttk.Frame(row_dev)
        row_tts.pack(side='left')
""",
    '⑥-12 语音分区横向并排；控件移入 row_dev')

# ── ⑥-13：ASR 的「识别语种」→ 高级面板 ──
rep(
    """        ttk.Label(row_asr, text='识别语种').pack(side='left', padx=(0, 4))
        self.cb_asr_lang = ttk.Combobox(
            row_asr, state='readonly', width=12, textvariable=self.var_asr_lang,
            values=[self._asr_lang_label[k] for k in self._asr_lang_keys])
        self.cb_asr_lang.pack(side='left', padx=(0, 8))
""",
    """        # 🔴🔴🔴 APP-061⑥：「识别语种」属**不常用** ⇒ 移进「高级」面板
        self.cb_asr_lang = ttk.Combobox(
            self._adv_frame, state='readonly', width=12,
            textvariable=self.var_asr_lang,
            values=[self._asr_lang_label[k] for k in self._asr_lang_keys])
""",
    '⑥-13 识别语种移进高级面板')

# ── ⑥-14：MT 的「草稿译文 / 重试」→ 高级面板 ──
rep(
    """        self.var_mt_draft = tk.BooleanVar(value=_init_draft_flag(args))
        self.chk_mt_draft = ttk.Checkbutton(
            row_mt, text='草稿译文 Draft', variable=self.var_mt_draft,
            command=self._on_mt_draft_toggled)
        self.chk_mt_draft.pack(side='left', padx=(0, 8))
        # 重试按钮：翻译模型加载失败时（状态栏显示「失败」）一键重试，
        # 不用重启整个程序。加载中时禁用。
        self.btn_mt_retry = ttk.Button(row_mt, text='↻ 重试翻译 Retry', width=16,
                                       command=self._retry_mt, state='disabled')
        self.btn_mt_retry.pack(side='left', padx=(0, 8))
""",
    """        self.var_mt_draft = tk.BooleanVar(value=_init_draft_flag(args))
        # 🔴🔴🔴 APP-061⑥：「草稿译文」「重试翻译」属**不常用** ⇒ 高级面板
        self.chk_mt_draft = ttk.Checkbutton(
            self._adv_frame, text='草稿译文 Draft', variable=self.var_mt_draft,
            command=self._on_mt_draft_toggled)
        # 重试按钮：翻译模型加载失败时（状态栏显示「失败」）一键重试，
        # 不用重启整个程序。加载中时禁用。
        self.btn_mt_retry = ttk.Button(self._adv_frame, text='↻ 重试翻译 Retry',
                                       width=16,
                                       command=self._retry_mt, state='disabled')
""",
    '⑥-14 草稿译文/重试翻译移进高级面板')

# ── ⑥-15：TTS 的「显示说话人 / 测试声音 / 耳机提示」处理 ──
rep(
    """        self.var_show_spk = tk.BooleanVar(value=True)
        cb_show_spk = ttk.Checkbutton(
            row_tts, text='显示说话人', variable=self.var_show_spk)
        cb_show_spk.pack(side='left', padx=(0, 8))
""",
    """        self.var_show_spk = tk.BooleanVar(value=True)
        # 🔴🔴🔴 APP-061⑥：「显示说话人」属**不常用** ⇒ 高级面板
        cb_show_spk = ttk.Checkbutton(
            self._adv_frame, text='显示说话人', variable=self.var_show_spk)
""",
    '⑥-15 显示说话人移进高级面板')

rep(
    """        self.btn_tts_test = ttk.Button(row_tts, text='🔊 测试声音', width=12,
                                       command=self._on_tts_test_sound)
        self.btn_tts_test.pack(side='left', padx=(0, 8))
""",
    """        # 🔴🔴🔴 APP-061⑥：「测试声音」属**不常用** ⇒ 高级面板
        self.btn_tts_test = ttk.Button(self._adv_frame, text='🔊 测试声音',
                                       width=12,
                                       command=self._on_tts_test_sound)
""",
    '⑥-16 测试声音移进高级面板')

rep(
    """        ttk.Label(row_tts, text='⚠️ 请佩戴耳机，避免回授',
                  foreground='#b26a00').pack(side='left', padx=(4, 0))
""",
    """        # 🔴🔴🔴 APP-061⑥：耳机提示**缩短**（宽度敏感）⇒ 完整说明在高级面板
        ttk.Label(row_tts, text='⚠️ 戴耳机',
                  foreground='#b26a00').pack(side='left', padx=(4, 0))
""",
    '⑥-17 耳机提示缩短')

# ── ⑥-18：三个分区的说明行 → 高级面板（状态条 tooltip 里仍可看全文） ──
rep(
    """        self._lbl_asr_note = self._bind_wrap(
            ttk.Label(f_asr, textvariable=self.var_asr_note, foreground='#555'),
            f_asr, self.var_asr_note)
""",
    """        # 🔴🔴🔴 APP-061⑥：分区的**说明行合并进状态栏**
        #   ⇒ 说明文字移进「高级」面板，同时**并入状态条的 tooltip**。
        self._lbl_asr_note = self._bind_wrap(
            ttk.Label(self._adv_frame, textvariable=self.var_asr_note,
                      foreground='#555'),
            self._adv_frame, self.var_asr_note)
""",
    '⑥-18 ASR 说明行移进高级面板')

rep(
    """        self._lbl_mt_note = self._bind_wrap(
            ttk.Label(f_mt, textvariable=self.var_mt_note, foreground='#555'),
            f_mt, self.var_mt_note)
""",
    """        self._lbl_mt_note = self._bind_wrap(
            ttk.Label(self._adv_frame, textvariable=self.var_mt_note,
                      foreground='#555'),
            self._adv_frame, self.var_mt_note)
""",
    '⑥-19 翻译说明行移进高级面板')

rep(
    """        self._lbl_tts_note = self._bind_wrap(
            ttk.Label(f_tts, textvariable=self.var_tts_note, foreground='#555'),
            f_tts, self.var_tts_note)
""",
    """        self._lbl_tts_note = self._bind_wrap(
            ttk.Label(self._adv_frame, textvariable=self.var_tts_note,
                      foreground='#555'),
            self._adv_frame, self.var_tts_note)
""",
    '⑥-20 语音说明行移进高级面板')

# ── ⑥-21：离线朗读行 → 高级面板 ──
rep(
    """        row_tts2 = ttk.Frame(f_tts)
        row_tts2.pack(fill='x')
        self.btn_offline = ttk.Button(
            row_tts2, text='📖 离线朗读…', width=14,
            command=self._open_offline_reader)
        self.btn_offline.pack(side='left', padx=(0, 8))
""",
    """        # 🔴🔴🔴 APP-061⑥：「离线朗读」属**不常用** ⇒ 高级面板
        row_tts2 = ttk.Frame(self._adv_frame)
        row_tts2.pack(fill='x')
        self.btn_offline = ttk.Button(
            row_tts2, text='📖 离线朗读…', width=14,
            command=self._open_offline_reader)
        self.btn_offline.pack(side='left', padx=(0, 8))
""",
    '⑥-21 离线朗读移进高级面板')

rep(
    """        self._lbl_tts_note2 = self._bind_wrap(
            ttk.Label(row_tts2, textvariable=self.var_tts_note2,
                      foreground='#555'),
            row_tts2, self.var_tts_note2)
""",
    """        self._lbl_tts_note2 = self._bind_wrap(
            ttk.Label(row_tts2, textvariable=self.var_tts_note2,
                      foreground='#555'),
            row_tts2, self.var_tts_note2)
        # 🔴🔴🔴 APP-061⑥：高级面板里的说明**顺序**（可折叠 ⇒ 默认不占空间）
        ttk.Label(self._adv_frame, text='⚠️ 请佩戴耳机，避免 TTS 声音被 ASR '
                  '回采造成回授。', foreground='#b26a00').pack(
                      side='left', padx=(8, 0))
""",
    '⑥-22 高级面板里的耳机完整说明')

# ── ⑥-23：窗口尺寸：最小宽度 1024；字幕区保持 13pt ──
rep(
    """        root.geometry('1080x820')
""",
    """        root.geometry('1080x820')
        # 🔴🔴🔴 APP-061⑥：**最小宽度 1024**（reviewer：「最小宽度 1024，
        #   最小高度另定」）⇒ 用户把窗口拉窄时控件不会被压到重叠。
        root.minsize(1024, 640)
""",
    '⑥-23 最小宽度 1024')

rep(
    """        self.txt = scrolledtext.ScrolledText(root, wrap='word', font=('Microsoft YaHei UI', 13),
                                             relief='flat', padx=12, pady=10, spacing3=6,
                                             height=10)
        self.txt.pack(fill='both', expand=True, padx=10, pady=(4, 4))
""",
    """        # 🔴🔴🔴 APP-061⑥：字幕字体**保持 13pt**（reviewer 明文），
        #   padding 略收；`height=10` 保持不变（ScrolledText 默认请求 718 px，
        #   会把状态栏压成 1 px —— 见上面的注释）。
        self.txt = scrolledtext.ScrolledText(root, wrap='word', font=('Microsoft YaHei UI', 13),
                                             relief='flat', padx=10, pady=8, spacing3=6,
                                             height=10)
        self.txt.pack(fill='both', expand=True, padx=8, pady=(2, 4))
""",
    '⑥-24 字幕区 padding 压缩（字体仍 13pt）')

# ── ⑥-25：新增「高级」面板的折叠开关方法（放在 `_make_status_strip` 之前） ──
rep(
    """    def _make_status_strip(self, parent, key):
""",
    """    def _toggle_advanced(self):
        \"\"\"🔴🔴🔴 APP-061⑥：**折叠/展开「高级」面板**。

        🔴 **为什么要有**：不常用控件（识别语种 / 草稿译文 / 重试翻译 /
          离线朗读 / 测试声音 / 显示说话人 / 三个分区的说明行）全部塞进来
          ⇒ 常用控件只占 **2 行** ⇒ 字幕区 ≥ 窗口高度 **70 %**。
        ⚠️ 面板默认**收起** ⇒ 不占纵向空间。
        \"\"\"
        self._adv_open = not getattr(self, '_adv_open', False)
        if self._adv_open:
            self._adv_frame.pack(fill='x', before=self.txt)
            self.btn_adv.configure(text='▴ 收起')
        else:
            self._adv_frame.pack_forget()
            self.btn_adv.configure(text='▾ 高级')

    def _make_status_strip(self, parent, key):
""",
    '⑥-25 新增 _toggle_advanced')

# ── ⑥-26：分区说明**并入状态条 tooltip**（状态栏「合并说明行」） ──
rep(
    """    def _strip_update(self, strip, max_px=None):
        \"\"\"把状态条重画一次（内容没变 ⇒ **不动控件**）。\"\"\"
        text, level, tip = strip['status'].render(max_px=max_px,
                                                  measure=strip.get('measure'))
""",
    """    def _strip_update(self, strip, max_px=None, extra_tip=''):
        \"\"\"把状态条重画一次（内容没变 ⇒ **不动控件**）。

        🔴🔴🔴 APP-061⑥：`extra_tip` = 该分区的**说明行**全文
          ⇒ 说明行「合并进状态栏」（悬停即见）⇒ 界面不再另占一行。
        \"\"\"
        text, level, tip = strip['status'].render(max_px=max_px,
                                                  measure=strip.get('measure'))
        if extra_tip:
            tip = (tip + '\\n' + extra_tip) if tip else extra_tip
""",
    '⑥-26 状态条支持附加说明')

rep(
    """            for s in (self._strip_asr, self._strip_mt, self._strip_tts):
""",
    """            # 🔴🔴🔴 APP-061⑥：把三个分区的**说明行全文**并进状态条 tooltip
            for s, note_var in ((self._strip_asr, getattr(self, 'var_asr_note', None)),
                                (self._strip_mt, getattr(self, 'var_mt_note', None)),
                                (self._strip_tts, getattr(self, 'var_tts_note', None))):
""",
    '⑥-27 _update_strips 带上说明行')

rep(
    """                self._strip_update(s, max_px=min(fw, 810))
""",
    """                try:
                    _extra = note_var.get() if note_var is not None else ''
                except Exception:
                    _extra = ''
                self._strip_update(s, max_px=min(fw, 810), extra_tip=_extra)
""",
    '⑥-28 传入说明行文本')


def main() -> int:
    if not os.path.exists(TARGET):
        print('[FAIL] 目标不存在')
        return 1
    with open(TARGET, 'rb') as f:
        raw = f.read()
    src = raw.decode('utf-8')
    before_sha = hashlib.sha256(raw).hexdigest()

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bpath = os.path.join(BACKUP_DIR, 'live_caption_app.py.before')
    with open(bpath, 'wb') as f:
        f.write(raw)

    # ── 先做全部命中检查（**任何一处不唯一 ⇒ 整体中止，不写盘**）──
    for old, new, label in REPL:
        n = src.count(old)
        if n != 1:
            print('[ABORT] %s：命中 %d 次（需恰好 1）' % (label, n))
            return 2

    for old, new, label in REPL:
        src = src.replace(old, new, 1)
        print('[OK] %s' % label)

    # ── 写前复核：语法 ──
    try:
        ast.parse(src)
    except SyntaxError as e:
        print('[ABORT] 替换后语法错误：%r' % e)
        return 3

    if src.count('\ufffd'):
        print('[ABORT] 替换后出现 U+FFFD 乱码')
        return 4

    tmp = TARGET + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(src.encode('utf-8'))
    os.replace(tmp, TARGET)

    with open(TARGET, 'rb') as f:
        after = f.read()
    print('\n[OK] 改前 SHA256 %s / %d B' % (before_sha, len(raw)))
    print('[OK] 改后 SHA256 %s / %d B' % (hashlib.sha256(after).hexdigest(),
                                          len(after)))
    print('[OK] 备份：%s' % bpath)
    # ── 写后逐块复核：新文本确实落盘 ──
    miss = [label for old, new, label in REPL if new not in src]
    if miss:
        print('[FAIL] 写后复核未命中：%r' % miss)
        return 5
    print('[OK] 写后逐块复核：%d/%d 命中' % (len(REPL), len(REPL)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
