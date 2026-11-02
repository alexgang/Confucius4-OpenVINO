#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""APP-065 A 的 GUI 冒烟 + **布局度量**（不加载模型、不占 GPU）。

输出：
- 5 个 GroupBox 的标题与几何
- 每组的**标签列右边缘**与**控件列左边缘**（⇒ 「所有组的标签列宽度一致」）
- 每组的**行高**（⇒ 「行高一致」）
- 控件 → 所在组的清单（reviewer 要求交付的「控件→所在组」清单）
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tkinter as tk                      # noqa: E402
import live_caption_app as lca             # noqa: E402
import translator                          # noqa: E402

OUT = os.path.join(HERE, 'app231_app065a_layout_evidence.json')


class A:
    pass


def build(root):
    args = A()
    args.source = 'mic'
    args.translate = 'en'
    args.asr_lang = 'auto'
    args.file = None
    args.engine = 'gpu_int8'
    args.tts = None
    args.tts_voice = 'A'
    args.tts_precision = 'f32'
    args.tts_out_device = None
    args.speaker = 'off'
    args.tts_device = None
    args.mt_device = None
    args.asr_device = None
    args.tts_source = 'mt'
    args.mt_engine = None
    args.font_size = 26
    args.max_seconds = 0.0
    args.out = None
    args.autostart = False
    args.selftest = 0.0
    args.selftest_out = None
    args.selftest_mt_switch = False
    args.list_devices = False
    args.check = False
    args.cli = False
    args.device = None
    args.system_device = None
    args.speed = 1.0
    args.loop = False
    args.mt_ctx = False
    args.mt_glossary = False
    args.tts_out = None
    args.tts_dump_dir = None
    args.tts_jsonl = None
    lca.App.load_engine = lambda self: None
    translator.TranslationService.set_engine = lambda self, k: True
    translator.TranslationService.set_device = lambda self, d: True
    return lca.App(root, args)


def main():
    root = tk.Tk()
    root.geometry('1280x800+0+0')
    app = build(root)
    root.update_idletasks()
    root.update()
    time_sleep = 1.0
    import time
    time.sleep(time_sleep)
    root.update()

    groups = []
    for w in app._groups.winfo_children():
        try:
            title = w.cget('text')
        except Exception:
            title = ''
        groups.append((w, title))

    info = {'window': [root.winfo_width(), root.winfo_height()],
            'groups': [], 'controls': []}

    for w, title in groups:
        gi = {'title': title,
              'class': w.winfo_class(),
              'x': w.winfo_x(), 'y': w.winfo_y(),
              'w': w.winfo_width(), 'h': w.winfo_height(),
              'mapped': bool(w.winfo_ismapped()),
              'label_right_edges': [], 'ctrl_left_edges': [],
              'row_heights': []}
        # 找该组内的标签列右边缘与控件列左边缘
        for sub in w.winfo_children():
            for c in sub.winfo_children() if sub.winfo_class() == 'TFrame' \
                    else []:
                try:
                    txt = c.cget('text')
                except Exception:
                    continue
                if not txt:
                    continue
                # 标签：column 0（用 grid_info 判断）
                gi0 = c.grid_info()
                col = gi0.get('column')
                if col == 0:
                    gi['label_right_edges'].append(
                        c.winfo_x() + c.winfo_width())
                elif col == 1:
                    gi['ctrl_left_edges'].append(c.winfo_x())
                gi['row_heights'].append(c.winfo_height())
        info['groups'].append(gi)

    # 控件 → 所在组 的清单
    for w, title in groups:
        for c in w.winfo_children():
            for d in (c.winfo_children() if c.winfo_class() == 'TFrame'
                      else []):
                try:
                    txt = c.cget('text')
                except Exception:
                    txt = ''
                cls = c.winfo_class()
                if cls in ('TCombobox', 'TButton', 'TCheckbutton', 'TEntry'):
                    info['controls'].append(
                        {'group': title, 'widget': cls,
                         'text': txt, 'x': c.winfo_x(), 'y': c.winfo_y(),
                         'w': c.winfo_width(), 'h': c.winfo_height()})

    # 高级组（默认收起）
    info['advanced_mapped'] = bool(app._adv_group.winfo_ismapped())
    app._toggle_advanced()
    root.update_idletasks()
    root.update()
    info['advanced_mapped_after_toggle'] = bool(
        app._adv_group.winfo_ismapped())
    app._toggle_advanced()
    root.update_idletasks()
    root.update()

    # 字幕区占比
    info['caption_ratio_pct'] = round(
        app.txt.winfo_height() / float(root.winfo_height()) * 100.0, 2)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print('窗口 %s' % (info['window'],))
    for gi in info['groups']:
        print('  [%s] %-12s y=%-4d h=%-4d mapped=%s 标签列右边缘=%s 控件列左边缘=%s'
              % (gi['class'], gi['title'], gi['y'], gi['h'], gi['mapped'],
                 sorted(set(gi['label_right_edges'])),
                 sorted(set(gi['ctrl_left_edges']))))
    print('高级组默认 mapped=%s（展开后=%s）'
          % (info['advanced_mapped'], info['advanced_mapped_after_toggle']))
    print('字幕区占比 = %s %%' % info['caption_ratio_pct'])
    print('控件清单 %d 项 → %s' % (len(info['controls']), OUT))
    root.destroy()
    return 0


if __name__ == '__main__':
    sys.exit(main())
