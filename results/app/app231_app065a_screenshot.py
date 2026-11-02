#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""APP-065 A：界面重排的**截图 + 「控件→所在组」清单**（交 reviewer）。

reviewer 原文：
    「交 reviewer：100% 和 150% 缩放下各一张截图（启动后、配音开启后），
      以及一张"控件→所在组"的清单。**截图先交 reviewer，通过后才打包。**」

## 本脚本产出

1. **4 张截图**（100% / 150% × 启动后 / 配音开启后）
   - 缩放用 Tk 的 `tk scaling`（= Windows 显示缩放对 Tk 字体/控件的等比放大）
   - 抓图用 `results/app/win_capture.py` 的 `capture_hwnd`
     （**不用** `PIL.ImageGrab` —— 本机实测抓屏全黑 ⇒ 静默假通过）
2. **「控件→所在组」清单**（JSON + 文本）：每个交互控件属于哪一组
3. **布局度量**：各组标签列右边缘 / 控件列左边缘 / 行高
   ⇒ 证明「所有组的标签列宽度一致、行高一致」

🔴 **不加载模型、不占 GPU/NPU** ⇒ **不需要 MACHINE_LOCK**（纯 GUI 布局）。
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
sys.path.insert(0, HERE)

import tkinter as tk                      # noqa: E402
import live_caption_app as lca             # noqa: E402
import translator                          # noqa: E402
from win_capture import capture_hwnd       # noqa: E402

SHOT_DIR = os.path.join(HERE, 'app065a_shots')
os.makedirs(SHOT_DIR, exist_ok=True)
OUT_JSON = os.path.join(HERE, 'app231_app065a_screenshot_evidence.json')
OUT_TXT = os.path.join(HERE, 'app231_app065a_control_group_map.txt')


class A:
    pass


def make_args(tts_voice='A'):
    args = A()
    args.source = 'mic'
    args.translate = 'en'
    args.asr_lang = 'auto'
    args.file = None
    args.engine = 'gpu_int8'
    args.tts = None
    args.tts_voice = tts_voice
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
    return args


def build(root, tts_voice='A'):
    lca.App.load_engine = lambda self: None
    translator.TranslationService.set_engine = lambda self, k: True
    translator.TranslationService.set_device = lambda self, d: True
    return lca.App(root, make_args(tts_voice))


def shot(root, path):
    """抓**窗口本身**（`PrintWindow`）⇒ 不读屏幕像素（本机全黑）。"""
    root.update_idletasks()
    root.update()
    try:
        root.deiconify()
        root.attributes('-topmost', True)
        root.lift()
    except Exception:
        pass
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    hwnd = None
    try:
        hwnd = root.winfo_id()
    except Exception:
        pass
    if not hwnd:
        return False
    ok = False
    try:
        ok = capture_hwnd(hwnd, path)
    except Exception:
        ok = False
    if ok:
        try:
            from PIL import Image
            im = Image.open(path).convert('L')
            lo, hi = im.getextrema()
            if hi - lo < 20:
                print('    [warn] %s 疑似黑图（extrema=(%s,%s)）'
                      % (os.path.basename(path), lo, hi))
                return False
        except Exception:
            pass
    return bool(ok)


def group_of(app):
    """返回 [(组标题, 组控件), ...]（按界面上从上到下）。"""
    out = []
    for w in app._groups.winfo_children():
        try:
            title = w.cget('text')
        except Exception:
            title = ''
        ctrls = []
        for sub in w.winfo_children():
            kids = sub.winfo_children() \
                if sub.winfo_class() == 'TFrame' else [sub]
            for c in kids:
                cls = c.winfo_class()
                if cls not in ('TCombobox', 'TButton', 'TCheckbutton',
                               'TEntry', 'TLabel'):
                    continue
                try:
                    txt = c.cget('text')
                except Exception:
                    txt = ''
                ctrls.append({'widget': cls, 'text': txt,
                               'x': c.winfo_x(), 'y': c.winfo_y(),
                               'w': c.winfo_width(), 'h': c.winfo_height()})
        out.append((title, w, ctrls))
    return out


def measure(app):
    """布局度量：标签列右边缘 / 控件列左边缘 / 各行高。"""
    res = []
    for title, w, _c in group_of(app):
        if not w.winfo_ismapped():
            continue
        lbl_right, ctrl_left, row_h = [], [], []
        for sub in w.winfo_children():
            if sub.winfo_class() != 'TFrame':
                continue
            for c in sub.winfo_children():
                try:
                    txt = c.cget('text')
                except Exception:
                    continue
                if not txt:
                    continue
                gi = c.grid_info()
                if gi.get('column') == 0:
                    lbl_right.append(c.winfo_x() + c.winfo_width())
                elif gi.get('column') == 1:
                    ctrl_left.append(c.winfo_x())
                row_h.append(c.winfo_height())
        res.append({'title': title,
                    'label_right_edges': sorted(set(lbl_right)),
                    'ctrl_left_edges': sorted(set(ctrl_left)),
                    'row_heights': sorted(set(row_h)),
                    'group_h': w.winfo_height()})
    return res


def run_one(tag, scale, tts_on):
    root = tk.Tk()
    # 🔴🔴🔴 **150 % 缩放必须保持「逻辑尺寸」不变**
    #   ⇒ 窗口**物理**尺寸 = 逻辑尺寸 × scaling
    #   （真实场景：Windows 150 % ⇒ 屏幕逻辑宽 = 物理宽/1.5）
    #   ⚠️ 旧实现物理宽固定 1080 ⇒ 150 % 时逻辑宽只剩 720
    #      ⇒ 比真实场景**苛刻得多**（控件被截断不是产品的错，是测法错）。
    LOGIC_W, LOGIC_H = 1080, 820
    root.geometry('%dx%d+0+0' % (int(LOGIC_W * scale),
                                  int(LOGIC_H * scale)))
    # 🔴 **每次运行都要重设 `tk scaling`**：它是**进程级全局**设置，
    #   而 `tk.Tk()` 会把它**重置**回系统值
    #   ⇒ 只在第一次运行前设 ⇒ 后面的运行**静默不生效**（本轮实测踩过：
    #   startup 150% 生效、tts_on 150% 没生效）。
    #   ⚠️ 必须在**控件创建之前**设（字体在创建时按当时的 scaling 度量）。
    try:
        root.tk.call('tk', 'scaling', scale)
        _now = float(root.tk.call('tk', 'scaling'))
        if abs(_now - scale) > 0.01:
            print('    [warn] scaling 未生效（请求 %.2f 实际 %.3f）'
                  % (scale, _now))
    except Exception as e:
        print('    [warn] 设置 scaling 失败：%r' % (e,))
    app = build(root, 'A')
    root.update_idletasks()
    root.update()
    time.sleep(0.5)
    root.update()
    # 🔴 **「启动后」与「配音开启后」必须真的不同** ⇒ 显式设置开关状态。
    #   `args.tts=None` ⇒ 默认**开启** ⇒ 两张图会一样（实测踩过）。
    try:
        app.var_tts_on.set(bool(tts_on))
        app._on_tts_toggled()
    except Exception as e:
        print('    [warn] 切 TTS 开关异常：%r' % (e,))
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    path = os.path.join(SHOT_DIR, 'app065a_%s_scaling%03d.png'
                        % (tag, int(round(scale * 100))))
    ok = shot(root, path)
    meas = measure(app)
    cap_ratio = round(app.txt.winfo_height()
                      / float(root.winfo_height()) * 100.0, 2)
    info = {'tag': tag, 'scaling': scale, 'tts_on': tts_on,
            'tts_state': bool(app.var_tts_on.get()),
            'shot': path if ok else None,
            'shot_bytes': os.path.getsize(path) if ok and
            os.path.exists(path) else 0,
            'groups': meas,
            'caption_ratio_pct': cap_ratio,
            'window': [root.winfo_width(), root.winfo_height()]}
    try:
        root.destroy()
    except Exception:
        pass
    return info


def main():
    runs = []
    for tag, scale, tts_on in (('startup', 1.0, False),
                               ('startup', 1.5, False),
                               ('tts_on', 1.0, True),
                               ('tts_on', 1.5, True)):
        print('== 截图 %s scaling=%.1f tts_on=%s' % (tag, scale, tts_on))
        runs.append(run_one(tag, scale, tts_on))

    # ── 「控件→所在组」清单 ──
    root = tk.Tk()
    root.geometry('1080x820+0+0')
    app = build(root, 'A')
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    lines = ['# APP-065 A：控件 → 所在组（reviewer 要求的清单）', '']
    cmap = []
    for title, w, ctrls in group_of(app):
        mapped = bool(w.winfo_ismapped())
        lines.append('## %s%s' % (title or '(无标题)',
                                  '' if mapped else '（默认收起）'))
        if not mapped:
            lines.append('   （该组默认收起 ⇒ 展开后可见）')
        for c in ctrls:
            desc = c['text'] or '(无文字)'
            lines.append('   - %-12s %s' % (c['widget'], desc))
            cmap.append({'group': title, 'widget': c['widget'],
                         'text': c['text'], 'mapped': mapped})
        lines.append('')
    lines.append('# 说明')
    lines.append('# ① ①音频输入 / ②语音识别 / ③翻译 / ④语音输出 = 常用组（永远可见）')
    lines.append('# ② ⑤高级 = 不常用组（默认收起；设备选择 / 草稿 / 重试 / 离线朗读 /')
    lines.append('#    测试声音 / 显示说话人 / 区分说话人（用于克隆））')
    lines.append('# ③ 每组内：**唯一标签列**（右对齐、等宽）＋ 控件列（左对齐、同宽）')
    lines.append('#    ⇒ 所有组的标签列右边缘一致（见 evidence 的 groups[].label_right_edges）')
    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    try:
        root.destroy()
    except Exception:
        pass

    ev = {'script': os.path.basename(__file__),
          'shot_dir': SHOT_DIR,
          'runs': runs,
          'control_group_map': cmap,
          'map_txt': OUT_TXT}
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)

    print('\n== 截图结果 ==')
    for r in runs:
        print('  %-8s scaling=%.1f tts_on=%-5s (实际开关=%s) shot=%s 字幕区=%.2f%%'
              % (r['tag'], r['scaling'], r['tts_on'], r.get('tts_state'),
                 'OK' if r['shot'] else 'FAIL', r['caption_ratio_pct']))
        for g in r['groups']:
            print('      [%s] 标签列右边缘=%s 控件列左边缘=%s 行高=%s'
                  % (g['title'], g['label_right_edges'],
                     g['ctrl_left_edges'], g['row_heights']))
    print('\n控件→所在组清单：%s（%d 项）' % (OUT_TXT, len(cmap)))
    print('证据：%s' % OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
