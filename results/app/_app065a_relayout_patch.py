#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""APP-065 A：把 App GUI 从「一行控件 + 3 个横排 LabelFrame」重排成
**按处理链竖排的 5 组 GroupBox**（①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级）。

🔴 **定点替换**（不是整目录覆盖）：
   - 定位靠**唯一锚点**（起点 / 终点各 1 个）⇒ 命中数必须 == 1，否则 abort。
   - 替换后 `ast.parse` 必须通过。
   - 写盘走**临时文件 + os.replace**（原子）。
   - 写后**逐字节复核**（行尾未被改动：原文件是 CRLF ⇒ 新内容也要 CRLF）。
"""
from __future__ import annotations

import ast
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
APP = os.path.join(REPO, 'live_caption', 'live_caption_app.py')

START_ANCHOR = "        # 音频来源单独一行：三种输入（麦克风 / 系统声音 / 音频文件）"
END_ANCHOR = "        # ⚠️ height=10（行）：**这是状态栏可见的关键**。"

NEW_BLOCK = r'''        # ── APP-065 A：按处理链分 5 组（竖排）──────────────────────
        #   reviewer 原文：「按处理链分组，从上到下：①音频输入 ②语音识别 ③翻译
        #     ④语音输出（开关、输出设备、音色）⑤高级。每组一个 GroupBox，
        #     组内用统一网格：标签列右对齐、等宽，控件列左对齐、同宽；
        #     **所有组的标签列宽度一致，行高一致**。」
        #   🔴 **统一网格**：每组内用 `grid`（不是 pack）⇒ 才有「标签列 / 控件列」
        #     两列对齐。`_GRID_LABEL_CHARS` / `_GRID_CTRL_CHARS` /
        #     `_GRID_ROW_H` 是**所有组共用**的常量 ⇒ 宽度/行高一致由单一数据源保证。
        #   ⚠️ **控件宽度统一** ⇒ 所有 Combobox 用 `width=_GRID_CTRL_CHARS`。
        #   ⚠️ `ttk.Label` 的 `width` 以**字符数**计 ⇒ 中英文混排仍会略不齐
        #      ⇒ 标签列额外用 `sticky='e'`（右对齐）＋ **等宽的空白填充**
        #      ⇒ 视觉上标签列右边缘一致。

        # ---- ① 音频输入 ----
        f_in = ttk.LabelFrame(self._groups, text='① 音频输入', padding=(6, 2))
        f_in.pack(fill='x', pady=(0, 2))
        g_in = ttk.Frame(f_in)
        g_in.pack(fill='x')
        g_in.columnconfigure(0, weight=0, uniform='lbl')
        g_in.columnconfigure(1, weight=1)
        self.source_keys = ['mic', 'system', 'file']
        self._src_label = {k: audio_source.SOURCES[k] for k in self.source_keys}
        self._src_label_back = {v: k for k, v in self._src_label.items()}
        self.var_source = tk.StringVar(value=self._src_label[args.source])
        ttk.Label(g_in, text='音频来源', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=0, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.cb_source = ttk.Combobox(
            g_in, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_source,
            values=[self._src_label[k] for k in self.source_keys])
        self.cb_source.grid(row=0, column=1, sticky='w', pady=1)
        self.cb_source.bind('<<ComboboxSelected>>', self._on_source_changed)
        # 🔴 第 2 行的**控件列容器**（设备控件互斥显示 ⇒ 内部仍用 pack）
        self._g_in_dev = ttk.Frame(g_in)
        self._g_in_dev.grid(row=1, column=1, sticky='w')
        ttk.Label(g_in, text='输入设备', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=1, column=0, sticky='e',
                                   padx=(0, 8), pady=1)

        # ASR 识别语种：'auto' = 自动检测（不注入语种提示），其余是模型
        # support_languages 里的英文名。
        # ⚠️ APP-007：这个下拉属于**识别行为** ⇒ 放在 ② 语音识别 组里
        #    （APP-065 A：凡是用户正常使用要选的**不得**放进高级）。
        self._asr_lang_keys = [ASR_LANG_AUTO] + list(ASR_LANGS)
        self._asr_lang_label = {k: asr_lang_label(k) for k in self._asr_lang_keys}
        self._asr_lang_label_back = {v: k for k, v in self._asr_lang_label.items()}
        init_lang = getattr(args, 'asr_lang', ASR_LANG_AUTO) or ASR_LANG_AUTO
        if init_lang not in self._asr_lang_keys:
            init_lang = ASR_LANG_AUTO
        self.var_asr_lang = tk.StringVar(value=self._asr_lang_label[init_lang])

        # 麦克风设备
        self.mics = list_input_devices()
        self.var_mic = tk.StringVar(
            value=self.mics[0][1] if self.mics else '（未找到输入设备）')
        self.cb_mic = ttk.Combobox(
            self._g_in_dev, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_mic, values=[m[1] for m in self.mics])
        self.cb_mic.pack(side='left', padx=(0, 8))

        # 系统输出设备（loopback 目标）
        self.outs = list_output_devices()          # [(wasapi_id, 显示名), ...]
        self._out_label = {oid: name for oid, name in self.outs}
        self._out_label_back = {name: oid for name, oid in self._out_label.items()}
        dflt_out = default_output_device_id()
        init_out = dflt_out if dflt_out in self._out_label else \
            (self.outs[0][0] if self.outs else None)
        self.var_out = tk.StringVar(
            value=self._out_label.get(init_out, '（未找到输出设备）'))
        self.cb_out = ttk.Combobox(
            self._g_in_dev, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_out,
            values=[self._out_label[oid] for oid, _ in self.outs])
        self.cb_out.pack(side='left', padx=(0, 8))

        # 音频文件
        self.var_file = tk.StringVar(value=args.file or '')
        self.entry_file = ttk.Entry(self._g_in_dev, width=_GRID_CTRL_CHARS,
                                    textvariable=self.var_file)
        self.entry_file.pack(side='left', padx=(0, 4))
        self.btn_pick_file = ttk.Button(self._g_in_dev, text='选择…',
                                        command=self._pick_file)
        self.btn_pick_file.pack(side='left', padx=(0, 8))

        # 文件回放速度（0=全速跑批，1.0=实时）与循环播放
        self._speed_label = {0.0: '全速', 0.5: '0.5×', 1.0: '1.0×（实时）',
                             1.5: '1.5×', 2.0: '2.0×'}
        self._speed_back = {v: k for k, v in self._speed_label.items()}
        self.var_speed = tk.StringVar(value=self._speed_label[1.0])
        self.cb_speed = ttk.Combobox(
            self._g_in_dev, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_speed,
            values=list(self._speed_label.values()))
        self.cb_speed.pack(side='left', padx=(0, 8))
        self.var_loop = tk.BooleanVar(value=False)
        self.cb_loop = ttk.Checkbutton(self._g_in_dev, text='循环',
                                       variable=self.var_loop)
        self.cb_loop.pack(side='left', padx=(0, 8))

        self.var_source_note = tk.StringVar(value='')
        self.lbl_source_note = ttk.Label(self._g_in_dev,
                                         textvariable=self.var_source_note,
                                         foreground='#555')
        self.lbl_source_note.pack(side='left', padx=(10, 0))

        # ---- ② 语音识别 ----
        # 🔴 APP-065 A：识别语种（语言）属**正常使用要选的** ⇒ 在本组，
        #   **不放高级**。
        f_asr = ttk.LabelFrame(self._groups, text='② 语音识别', padding=(6, 2))
        f_asr.pack(fill='x', pady=(0, 2))
        g_asr = ttk.Frame(f_asr)
        g_asr.pack(fill='x')
        g_asr.columnconfigure(0, weight=0, uniform='lbl')
        g_asr.columnconfigure(1, weight=1)
        ttk.Label(g_asr, text='识别语种', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=0, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.cb_asr_lang = ttk.Combobox(
            g_asr, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_asr_lang,
            values=[self._asr_lang_label[k] for k in self._asr_lang_keys])
        self.cb_asr_lang.grid(row=0, column=1, sticky='w', pady=1)
        self.cb_asr_lang.bind('<<ComboboxSelected>>', self._on_asr_lang_changed)
        self.var_asr_note = tk.StringVar(value='')
        # 🔴 APP-048：**ASR 分区自己的紧凑状态条**
        #    （设备 / 模型+精度 / 加载状态 / RTF / 说话人开关与状态 / 当前说话人）
        self._strip_asr = self._make_status_strip(f_asr, 'asr')
        # 🔴🔴🔴 APP-061⑥：分区的**说明行合并进状态栏**
        self._lbl_asr_note = self._bind_wrap(
            ttk.Label(self._adv_frame, textvariable=self.var_asr_note,
                      foreground='#555'),
            self._adv_frame, self.var_asr_note)

        # ---- ③ 翻译 ----
        f_mt = ttk.LabelFrame(self._groups, text='③ 翻译', padding=(6, 2))
        f_mt.pack(fill='x', pady=(0, 2))
        g_mt = ttk.Frame(f_mt)
        g_mt.pack(fill='x')
        g_mt.columnconfigure(0, weight=0, uniform='lbl')
        g_mt.columnconfigure(1, weight=1)
        ttk.Label(g_mt, text='目标语言', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=0, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.mt_keys = list(TARGETS)
        self.var_mt = tk.StringVar(value=TARGET_LABELS[args.translate])
        self.cb_mt = ttk.Combobox(
            g_mt, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_mt,
            values=[TARGET_LABELS[k] for k in self.mt_keys])
        self.cb_mt.grid(row=0, column=1, sticky='w', pady=1)
        self.cb_mt.bind('<<ComboboxSelected>>', self._on_mt_changed)
        self.var_mt_note = tk.StringVar(value='')
        # 🔴 APP-048：**翻译分区自己的紧凑状态条**
        self._strip_mt = self._make_status_strip(f_mt, 'mt')
        self._lbl_mt_note = self._bind_wrap(
            ttk.Label(self._adv_frame, textvariable=self.var_mt_note,
                      foreground='#555'),
            self._adv_frame, self.var_mt_note)
        self.mt.set_draft(self.var_mt_draft.get())

        # ---- ④ 语音输出 ----
        f_tts = ttk.LabelFrame(self._groups, text='④ 语音输出', padding=(6, 2))
        f_tts.pack(fill='x', pady=(0, 2))
        g_tts = ttk.Frame(f_tts)
        g_tts.pack(fill='x')
        g_tts.columnconfigure(0, weight=0, uniform='lbl')
        g_tts.columnconfigure(1, weight=1)
        # 🔴 **TTS 默认开启**（APP-014：TTS 已转为正式功能）
        #    ⚠️ 兼容：命令行显式给了 `--tts off` 时仍按 off；
        #       没给（`None`）⇒ 按**默认开启**处理。
        _tts_arg = getattr(args, 'tts', None)
        self.var_tts_on = tk.BooleanVar(
            value=(True if _tts_arg is None else _tts_arg == 'on'))
        ttk.Label(g_tts, text='开关', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=0, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.chk_tts = ttk.Checkbutton(
            g_tts, text='开启语音输出', variable=self.var_tts_on,
            command=self._on_tts_toggled)
        self.chk_tts.grid(row=0, column=1, sticky='w', pady=1)
        self._tts_opts = build_tts_options(self._dev_avail)
        self._tts_opt_by_id = {o['id']: o for o in self._tts_opts}
        self.var_tts_combo = tk.StringVar(value='')
        ttk.Label(g_tts, text='音色', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=1, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        # 🔴🔴 **只保留音色 A**（APP-007 交付修正，2026-10-23）。
        #    客户包只带 `models/qwen3tts/voices/preset_A.wav`（BRIEF 硬要求：
        #    同事音色 B / 克隆音色 C 一律不进包）。
        #    ⚠️ 之前这里写死 ['A','B','clone'] 是**错的**：
        #      - 选 B ⇒ tts_worker._setup_babelvox_voice 回落 preset_voice_path()
        #        ⇒ **实际发的是音色 A 的声音**（静默错标，用户无从察觉）；
        #      - 选 clone ⇒ 需要 voices/clone_C.npz + torch ⇒ 包内两者都没有
        #        ⇒ 失败回落内置 speaker cindy。
        #    ⇒ 列出来只会让用户选了却拿不到对应的音色。
        #
        # 🔴🔴 APP-022：**新增「跟随说话人（克隆）」选项**（接口预留）。
        #   ⚠️ **默认仍是「预设 A」**（APP-022 明文：「默认仍是预设 A」）。
        # 🔴🔴🔴 APP-027⑤：**本轮真正接入**「跟随说话人（克隆）」
        #   ⇒ 采集器在 `App._collect_clone_pcm` ⇒ 每 30 s 或累计 ≥6 s 新语音
        #      把最近 3–10 s 语音发给 worker ⇒ 换 x-vector（BabelVox）或换边车
        #      参考音频（CUDA）⇒ **下一句起生效**。
        #   ⚠️ **仍保留一条铁律**：克隆**失败**时**显式回落预设 A** + 写日志
        #      ⇒ 绝不静默（§42 的教训）。
        #   ⚠️ **GUI 上显示的是「当前实际使用的音色」**（`_clone_voice_label`）
        #      ⇒ **而不是**用户选的那一项 ⇒ 用户能看见真实状态。
        self.tts_voices = ['A', 'follow_speaker']
        # 🔴🔴 APP-039：**克隆模式标注「实验」**
        #   APP-039 明文：「克隆模式先标'实验'」
        #   ⇒ 用户对它不满意的正是这里（音色切换滞后 >10 s / 换人时渐变 /
        #     后台一直采样）⇒ 正确设计（音色按句绑定 spk + 检测到换人才取样）
        #     **要等 ASR 的说话人旁路接口（ASR-029）** ⇒ 在按新设计重做完之前，
        #     界面必须如实告诉用户它是**实验性**的，不能让默认状态看起来像成品。
        self._tts_voice_label = {'A': '预设 A',
                                 'follow_speaker': '跟随说话人（克隆·实验）'}
        self._tts_voice_back = {v: k for k, v in self._tts_voice_label.items()}
        self.var_tts_voice = tk.StringVar(
            value=self._tts_voice_label.get(args.tts_voice, '预设 A'))
        self.cb_tts_voice = ttk.Combobox(
            g_tts, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_tts_voice,
            values=[self._tts_voice_label[k] for k in self.tts_voices])
        self.cb_tts_voice.grid(row=1, column=1, sticky='w', pady=1)
        self.cb_tts_voice.bind('<<ComboboxSelected>>', self._on_tts_voice_changed)
        # 🔴🔴 APP-027⑤：**当前实际使用的音色**（独立标签，不在下拉里）
        #   ⇒ 用户随时能看见「现在到底在用预设 A 还是克隆」。
        self.var_tts_voice_now = tk.StringVar(value='预设 A')
        ttk.Label(g_tts, textvariable=self.var_tts_voice_now,
                  foreground='#1565c0').grid(row=1, column=2, sticky='w',
                                             padx=(8, 0), pady=1)
        ttk.Label(g_tts, text='输出设备', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=2, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        # 复用 App 已有的输出设备列表（MME/WASAPI）—— C-101 P4 第 4 条
        self.var_tts_out = tk.StringVar(
            value=self._out_label.get(init_out, '（未找到输出设备）'))
        self.cb_tts_out = ttk.Combobox(
            g_tts, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_tts_out,
            values=[self._out_label[oid] for oid, _ in self.outs])
        self.cb_tts_out.grid(row=2, column=1, sticky='w', pady=1)
        # 🔴🔴🔴 APP-021⑤：**输出设备下拉**必须绑变更事件。
        #   旧行为：`cb_tts_out` **没有**绑 `<<ComboboxSelected>>`
        #   ⇒ 改了下拉**完全没有效果** ⇒ 用户以为换了设备，声音还是从旧设备出。
        self.cb_tts_out.bind('<<ComboboxSelected>>', self._on_tts_out_changed)
        self.var_tts_note = tk.StringVar(value='')
        # 🔴 APP-048：**语音输出分区自己的紧凑状态条**
        self._strip_tts = self._make_status_strip(f_tts, 'tts')
        self._lbl_tts_note = self._bind_wrap(
            ttk.Label(self._adv_frame, textvariable=self.var_tts_note,
                      foreground='#555'),
            self._adv_frame, self.var_tts_note)

        # ---- ⑤ 高级（不常用项）----
        # 🔴🔴🔴 APP-065 A：「高级」**只放用户平时不需要动的东西**，
        #   且**每一项要有一句话提示说明作用**。
        #   ⚠️ 设备选择（GPU/NPU/CPU）属**不常用** ⇒ 三个后端下拉都在高级里。
        #   ⚠️ **正常使用要选的（输入源 / 语言 / 是否配音 / 音色）一律不在高级**
        #     ⇒ 分别在 ①②③④ 组里（上方）。
        # 🔴 **设备下拉的初值设置**由 `_init_combo_values` 完成（在本函数末尾）。
        g_adv = ttk.Frame(self._adv_frame)
        g_adv.pack(fill='x')
        g_adv.columnconfigure(0, weight=0, uniform='lbl')
        g_adv.columnconfigure(1, weight=1)
        ttk.Label(g_adv, text='识别后端', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=0, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self._asr_opts = build_asr_options(self._dev_avail)
        self._asr_opt_by_id = {o['id']: o for o in self._asr_opts}
        self.var_asr_combo = tk.StringVar(value='')
        self.cb_asr_combo = ttk.Combobox(
            g_adv, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_asr_combo,
            values=[o['label'] for o in self._asr_opts])
        self.cb_asr_combo.grid(row=0, column=1, sticky='w', pady=1)
        self.cb_asr_combo.bind('<<ComboboxSelected>>', self._on_asr_combo_changed)
        ttk.Label(g_adv, text='翻译后端', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=1, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self._mt_opts = build_mt_options(self._dev_avail)
        self._mt_opt_by_id = {o['id']: o for o in self._mt_opts}
        self.var_mt_combo = tk.StringVar(value='')
        self.cb_mt_combo = ttk.Combobox(
            g_adv, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_mt_combo,
            values=[o['label'] for o in self._mt_opts])
        self.cb_mt_combo.grid(row=1, column=1, sticky='w', pady=1)
        self.cb_mt_combo.bind('<<ComboboxSelected>>', self._on_mt_combo_changed)
        ttk.Label(g_adv, text='语音后端', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=2, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.cb_tts_combo = ttk.Combobox(
            g_adv, state='readonly', width=_GRID_CTRL_CHARS,
            textvariable=self.var_tts_combo,
            values=[o['label'] for o in self._tts_opts])
        self.cb_tts_combo.grid(row=2, column=1, sticky='w', pady=1)
        self.cb_tts_combo.bind('<<ComboboxSelected>>', self._on_tts_combo_changed)
        # 草稿译文开关：默认**关闭**，只翻已经定稿的文本。勾上后还会实时翻译
        # 还没定稿的那句，但会占翻译算力、抬高 ASR 积压。
        self.var_mt_draft = tk.StringVar(value=_init_draft_flag(args))
        ttk.Label(g_adv, text='草稿译文', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=3, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.chk_mt_draft = ttk.Checkbutton(
            g_adv, text='Draft', variable=self.var_mt_draft,
            command=self._on_mt_draft_toggled)
        self.chk_mt_draft.grid(row=3, column=1, sticky='w', pady=1)
        # 重试按钮：翻译模型加载失败时（状态栏显示「失败」）一键重试，
        # 不用重启整个程序。加载中时禁用。
        ttk.Label(g_adv, text='重试翻译', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=4, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.btn_mt_retry = ttk.Button(
            g_adv, text='↻ 重试翻译 Retry', width=18,
            command=self._retry_mt, state='disabled')
        self.btn_mt_retry.grid(row=4, column=1, sticky='w', pady=1)
        # 🔴🔴🔴 APP-022：字幕上**可以选择显示说话人标签**（S1、S2…）。
        # 🔴🔴🔴 APP-040④：**默认改为打开**
        #   APP-040④ 明文：「GUI 加一个开关，**默认打开**」
        self.var_show_spk = tk.BooleanVar(value=True)
        ttk.Label(g_adv, text='显示说话人', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=5, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        cb_show_spk = ttk.Checkbutton(
            g_adv, text='在字幕上显示 S1/S2', variable=self.var_show_spk)
        cb_show_spk.grid(row=5, column=1, sticky='w', pady=1)
        # 🔴🔴🔴 APP-054：**说话人旁路开关**（**默认关闭**）
        #   ⇒ v1.13 的阻断级回归：旁路**默认开着**且**同步阻塞 ASR 主循环**
        #     ⇒ 用户实测：墙钟 838.5 s / 300 s 音频（最大积压 195.1 s）。
        #   ⇒ 现在旁路**默认关闭** ⇒ 字幕/语音行为与 **v1.12 逐字一致**。
        #   ⚠️ 勾选**只影响后续会话**（旁路线程在会话开始时建立）。
        # 🔴🔴🔴 APP-065 B（2026-11-02）：**改名 + 移出 TTS 区**。
        #   reviewer 原文：「GUI 上"说话人识别"改为在"音色"下拉选
        #     "跟随说话人（克隆）"时自动启用的内部功能，
        #     **不再作为一个独立的用户开关出现在 TTS 区**；
        #     如保留，放进高级并命名为"区分说话人（用于克隆）"，
        #     带提示"检测谁在说话，换人时重新克隆音色；只在音色=跟随说话人时生效"。」
        #   ⇒ 现在：**在高级里** ＋ 改名「区分说话人（用于克隆）」
        #     ＋ 带一句话提示 ＋ 绑定 `command`（APP-063 ② (c)：取消勾选 ⇒
        #       音色切回 A 并提示 ⇒ 不再出现「界面勾了但没生效」）。
        #   ⚠️ **变量名 `var_speaker` 保持不变**（`app227` 的 D2 判据
        #     要求 `_enable_speaker_for_clone` 的 AST 里含 `var_speaker`；
        #     `app204` 的快照也读 `var_speaker`）⇒ 只改**显示文案**。
        self.var_speaker = tk.BooleanVar(value=bool(self._speaker_enabled))
        ttk.Label(g_adv, text='区分说话人', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=6, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.cb_speaker = ttk.Checkbutton(
            g_adv, text='区分说话人（用于克隆）',
            variable=self.var_speaker,
            command=self._on_speaker_toggled)
        self.cb_speaker.grid(row=6, column=1, sticky='w', pady=1)
        # 🔴 **提示**（APP-065 A：高级里每一项要有一句话说明作用）
        ttk.Label(g_adv, text='检测谁在说话，换人时重新克隆音色；'
                  '只在音色=跟随说话人时生效',
                  foreground='#555').grid(row=7, column=1, sticky='w',
                                          padx=(0, 8), pady=1)
        # 🔴 **离线朗读入口**（用户需求：上传文件 / 对话框输入文本 ⇒ 直接播报）
        ttk.Label(g_adv, text='离线朗读', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=8, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.btn_offline = ttk.Button(
            g_adv, text='📖 离线朗读…', width=16,
            command=self._open_offline_reader)
        self.btn_offline.grid(row=8, column=1, sticky='w', pady=1)
        ttk.Label(g_adv, text='上传音频或输入文本直接播报，不经过识别与翻译',
                  foreground='#555').grid(row=9, column=1, sticky='w',
                                          padx=(0, 8), pady=1)
        # 🔴 **测试声音**按钮（APP-021④）：把「播放链路」与「TTS 合成」拆开。
        #   走**同一个 worker 的 Player** 播 1 s 440 Hz 正弦波。
        ttk.Label(g_adv, text='测试声音', width=_GRID_LABEL_CHARS,
                  anchor='e').grid(row=10, column=0, sticky='e',
                                   padx=(0, 8), pady=1)
        self.btn_tts_test = ttk.Button(g_adv, text='🔊 测试声音', width=14,
                                       command=self._on_tts_test_sound)
        self.btn_tts_test.grid(row=10, column=1, sticky='w', pady=1)
        ttk.Label(g_adv, text='播放 1 秒测试音，验证输出设备与播放链路',
                  foreground='#555').grid(row=11, column=1, sticky='w',
                                          padx=(0, 8), pady=1)
        # ⚠️ **耳机提示**（APP-014：TTS 转正式功能 ⇒ 默认开启）
        #   TTS 从**系统输出设备**播放，而 ASR 可能采**系统回环**⇒
        #     不戴耳机会把 TTS 的声音**再采回去** ⇒ 自激 / 回声 / 重复词。
        ttk.Label(g_adv, text='⚠️ 戴耳机', width=_GRID_LABEL_CHARS,
                  anchor='e', foreground='#b26a00').grid(
                      row=12, column=0, sticky='e', padx=(0, 8), pady=1)
        ttk.Label(g_adv, text='避免 TTS 声音被 ASR 回采造成回授',
                  foreground='#b26a00').grid(row=12, column=1, sticky='w',
                                           padx=(0, 8), pady=1)
        # 🔴 **全局说明文字**（APP-048：顶部说明也要换行）
        self._lbl_note.pack(fill='x', padx=4, pady=(2, 0))
        # 🔴 **离线朗读用途说明**（APP-052 ②：独立变量 ⇒ 不与设备说明重复）
        #   ⚠️ 保留 `_lbl_tts_note2` 这个属性名（既有验收脚本可能引用）。
        self.var_tts_note2 = tk.StringVar(value='')
        self._lbl_tts_note2 = self._bind_wrap(
            ttk.Label(g_adv, textvariable=self.var_tts_note2, foreground='#555'),
            g_adv, self.var_tts_note2)

'''


def main():
    with open(APP, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-8')
    n_crlf = raw.count(b'\r\n')
    lf_only = raw.count(b'\n') - n_crlf
    print('原文件：CRLF=%d LF-only=%d' % (n_crlf, lf_only))
    use_crlf = n_crlf > lf_only

    i_start = text.find(START_ANCHOR)
    i_end = text.find(END_ANCHOR)
    if i_start < 0:
        print('[ABORT] 找不到起点锚点'); return 2
    if i_end < 0:
        print('[ABORT] 找不到终点锚点'); return 2
    if text.find(START_ANCHOR, i_start + 1) >= 0:
        print('[ABORT] 起点锚点不唯一'); return 2
    if text.find(END_ANCHOR, i_end + 1) >= 0:
        print('[ABORT] 终点锚点不唯一'); return 2
    if i_end <= i_start:
        print('[ABORT] 锚点顺序错'); return 2

    old = text[i_start:i_end]
    print('替换区间：第 %d–%d 行（%d 字符）'
          % (text[:i_start].count('\n') + 1, text[:i_end].count('\n') + 1,
             len(old)))

    new_text = text[:i_start] + NEW_BLOCK + text[i_end:]
    # 行尾归一化（写回时还原原行尾）
    if use_crlf:
        new_text = new_text.replace('\r\n', '\n').replace('\n', '\r\n')
    # 语法校验
    try:
        ast.parse(new_text)
    except SyntaxError as e:
        print('[ABORT] 替换后语法错误：%r' % (e,)); return 2
    print('替换后 ast.parse 通过')

    # 原子写盘
    tmp = APP + '.tmp_app065a'
    with open(tmp, 'wb') as f:
        f.write(new_text.encode('utf-8'))
    with open(tmp, 'rb') as f:
        chk = f.read()
    if chk != new_text.encode('utf-8'):
        print('[ABORT] 临时文件逐字节复核不一致'); return 2
    os.replace(tmp, APP)
    # 写后复核
    with open(APP, 'rb') as f:
        after = f.read()
    if after != new_text.encode('utf-8'):
        print('[ABORT] 写盘后逐字节复核不一致'); return 2
    n2 = after.count(b'\r\n')
    l2 = after.count(b'\n') - n2
    print('写后：CRLF=%d LF-only=%d 字节=%d' % (n2, l2, len(after)))
    if (n2 > 0) != (n_crlf > 0):
        print('[ABORT] 行尾风格被改变'); return 2
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
