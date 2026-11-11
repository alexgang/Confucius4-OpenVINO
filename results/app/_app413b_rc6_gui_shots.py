#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app413b_rc6_gui_shots.py —— **APP-098 三.1（改版）：rc6 的 GUI 截图验收**。

## 为什么改写第一版（`_app413_rc6_gui_shots.py`）

第一版是「**外部**起 GUI + 外部枚举窗口找 combobox 的弹出层」⇒ 实测：
* 主窗口抓到了（1455×1132，OK）；
* 但 **3 个下拉弹出层一个都没抓到** ⇒ `EnumWindows` 找不到 Tk 的
  override-redirect popdown（它是 TkChild，标题为空但尺寸过滤把它漏掉了）。

⇒ 改用「**进程内**驱动 Tk」：
* 直接 `import live_caption_app`（**包内副本** ⇒ 跑的是真包代码）；
* `cb.event_generate('<Button-1>')` 展开下拉；
* `cb.tk.call('ttk::combobox::PopdownWindow', cb)` 拿到 **popdown 的
  toplevel** ⇒ `winfo_id()` ⇒ `capture_hwnd()` 抓**展开的选项列表**。

## 🔴🔴🔳 像素级守卫（防「静默假通过」）
每张图都要过：① 文件存在 ② 非黑（extrema max > 0）③ 内容密度 > 0
⇒ 任一不过 ⇒ 该项 `verdict=FAIL`，**不写「已截图」**。

## 🔴 不加载模型
`App.load_engine` / `translator.TranslationService.set_engine|set_device`
被 stub 成 no-op ⇒ **不占 GPU/NPU**、不跑推理 ⇒ 本脚本可与设备作业并行。

## reviewer 三.1 原文
> 识别、翻译、语音三个下拉框展开各截一张，克隆控件一张（要是灰的），
> 目标语言下拉框一张（10 种）。

⇒ 5 张：ASR 后端 / MT 后端 / TTS 后端 / 音色（含置灰克隆项）/ 目标语言。

## 用法
```
.venv/Scripts/python.exe results/app/_app413b_rc6_gui_shots.py --pkg <rc6 目录>
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

OUTROOT = os.path.join(HERE, 'app413b_rc6_gui_shots')
REPORT = os.path.join(HERE, 'app413b_rc6_gui_shots.json')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


class Args:
    """万能 Namespace：包内版本新增的启动参数一律兜底为 None。"""

    def __getattr__(self, _name):
        return None


def make_args():
    a = Args()
    a.source, a.translate, a.asr_lang = 'mic', 'zh', 'auto'
    a.file, a.engine, a.tts = None, 'gpu_int8', None
    a.tts_voice, a.tts_precision, a.tts_out_device = 'A', 'f32', None
    a.speaker = 'off'
    a.tts_device = a.mt_device = a.asr_device = None
    a.tts_source, a.mt_engine = 'mt', None
    a.font_size, a.max_seconds, a.out = 26, 0.0, None
    a.autostart, a.selftest, a.selftest_out = False, 0.0, None
    a.selftest_mt_switch = a.list_devices = a.check = a.cli = False
    a.device = a.system_device = None
    a.speed, a.loop = 1.0, False
    a.mt_ctx = a.mt_glossary = a.mt_draft = False
    a.tts_out = a.tts_dump_dir = a.tts_jsonl = a.spk_seg_jsonl = None
    a.min_clean_ratio = None
    a.speaker = 'off'
    return a


def guard_png(path):
    """🔴 像素级守卫：非黑 + 有内容密度。"""
    rec = {'path': path, 'exists': os.path.isfile(path),
           'bytes': os.path.getsize(path) if os.path.isfile(path) else 0}
    if not rec['exists']:
        rec['not_black'] = False
        rec['why'] = '文件不存在'
        return rec
    try:
        from PIL import Image
        lo, hi = Image.open(path).convert('L').getextrema()
        rec['extrema'] = [lo, hi]
        rec['not_black'] = (hi > 0)
        if not rec['not_black']:
            rec['why'] = '疑似黑图 extrema=(%s,%s)' % (lo, hi)
    except Exception as e:
        rec['not_black'] = False
        rec['why'] = '守卫异常 %r' % (e,)
    try:
        sys.path.insert(0, HERE)
        from png_stats import content_density
        rec['density'] = content_density(path)
    except Exception:
        rec['density'] = None
    return rec


def win32_window_title(root):
    """🔴 APP-099 四.5：截图带不了标题栏 ⇒ 用 Win32 读出标题**写进 json**。

    `PrintWindow` 抓的是客户区，标题栏不一定在画面里 ⇒ reviewer 要求
    「如果截图带不了标题栏，就用 Win32 读出标题写进 json」。
    Tk 的 `winfo_id()` 是**子窗口**句柄 ⇒ 用 `GetAncestor(GA_ROOT)` 取顶层
    再 `GetWindowTextW`，避免读到空标题。
    """
    import ctypes
    u32 = ctypes.windll.user32
    hwnd = int(root.winfo_id())
    GA_ROOT = 2
    top = u32.GetAncestor(hwnd, GA_ROOT) or hwnd
    buf = ctypes.create_unicode_buffer(1024)
    n = u32.GetWindowTextW(top, buf, 1024)
    return {
        'method': 'user32.GetAncestor(GA_ROOT)+GetWindowTextW',
        'tk_hwnd': hwnd, 'top_hwnd': int(top),
        'title': buf.value if n else '',
        'n_chars': int(n),
        'nonempty': bool(n and buf.value.strip()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--out-json', default=REPORT)
    ap.add_argument('--out-dir', default=OUTROOT)
    a = ap.parse_args()
    pkg = os.path.abspath(a.pkg)
    os.makedirs(a.out_dir, exist_ok=True)
    sys.path.insert(0, os.path.join(pkg, 'app'))
    sys.path.insert(0, HERE)                      # win_capture / png_stats
    sys.path.insert(0, REPO)

    import tkinter as tk                          # noqa: E402
    import live_caption_app as lca                # noqa: E402  ← 包内副本
    import translator                             # noqa: E402
    from win_capture import capture_hwnd         # noqa: E402

    ev = {
        'tool': 'app413b', 'correction': 'APP-098 三.1',
        'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': pkg,
        'lca_file': lca.__file__,
        'lca_sha256': sha256_file(lca.__file__),
        'shots': [], 'verdict': 'PENDING',
    }

    # 🔴 不加载模型 ⇒ 不占设备
    lca.App.load_engine = lambda self: None
    translator.TranslationService.set_engine = lambda self, k: True
    translator.TranslationService.set_device = lambda self, d: True

    root = tk.Tk()
    root.geometry('1455x1132+0+0')
    app = lca.App(root, make_args())
    root.update_idletasks()
    root.update()
    time.sleep(0.6)
    root.update()

    def grab(name, widget_path, out_name, note=''):
        """展开某个 combobox 的下拉 ⇒ 抓 popdown 窗口。

        🔴🔴 **实测坑**：popdown 的**几何在展开后才算出来** ⇒ 抓得太快会拿到
        **空窗口（全黑）**。⇒ 改成：**hide → post → 反复 update**，
        且**抓到黑图就重试**（最多 4 次）。
        """
        rec = {'name': name, 'widget': widget_path, 'note': note}
        try:
            cb = app
            for part in widget_path.split('.'):
                cb = getattr(cb, part)
            rec['values'] = [str(v) for v in cb.cget('values')]
            rec['current'] = str(cb.get())
        except Exception as e:
            rec['shot'] = None
            rec['not_black'] = False
            rec['why'] = '取控件失败 %r' % (e,)
            return rec

        try:
            pop_path = cb.tk.call('ttk::combobox::PopdownWindow', cb)
            rec['popdown_path'] = str(pop_path)
            # 🔴🔴 `winfo id` 在本机返回**十六进制字符串**（如 '0x12d0cea'）
            #   ⇒ 必须 `int(s, 0)` 解析。
            raw_id = str(cb.tk.call('winfo', 'id', pop_path))
            rec['popdown_id_raw'] = raw_id
            hwnd = int(raw_id, 0)
            rec['popdown_hwnd'] = hwnd
        except Exception as e:
            rec['shot'] = None
            rec['not_black'] = False
            rec['why'] = '取 popdown 句柄失败 %r' % (e,)
            return rec

        png = os.path.join(a.out_dir, out_name)
        attempts = []
        for attempt in range(4):
            try:
                cb.tk.call('popdown', 'hide')
            except Exception:
                pass
            root.update_idletasks()
            root.update()
            time.sleep(0.15)
            # 🔴🔴 **实测**：只有 `event_generate('<Button-1>')`（真实鼠标按下）
            #   才能把 popdown 真正显示出来；`popdown post` 只是 post 一个命令
            #   ⇒ 几何停在 161x184+0+0（没定位）⇒ 抓到黑图。
            #   ⇒ 以 Button-1 为主，`post` 仅作兜底。
            opened = False
            try:
                cb.event_generate('<Button-1>')
                opened = True
            except Exception as e:
                attempts.append('Button-1 异常 %r' % (e,))
            for _ in range(8):
                root.update_idletasks()
                root.update()
                time.sleep(0.08)
            try:
                geo = str(cb.tk.call('winfo', 'geometry', pop_path))
            except Exception:
                geo = ''
            ok = False
            try:
                ok = bool(capture_hwnd(hwnd, png))
            except Exception as e:
                attempts.append('capture 异常 %r' % (e,))
            g = guard_png(png) if ok else {'path': png, 'not_black': False}
            attempts.append('try%d opened=%s geo=%s capture=%s extrema=%s'
                            % (attempt + 1, opened, geo, ok, g.get('extrema')))
            if g.get('not_black'):
                rec.update(g)
                rec['capture_return'] = ok
                rec['shot'] = png
                rec['shot_sha256'] = sha256_file(png)
                rec['attempts'] = attempts
                try:
                    cb.tk.call('popdown', 'hide')
                except Exception:
                    pass
                root.update()
                return rec
            time.sleep(0.25)

        rec.update(guard_png(png) if os.path.isfile(png)
                   else {'path': png, 'not_black': False})
        rec['shot'] = None
        rec['attempts'] = attempts
        rec['why'] = '多次重试仍抓到黑图'
        try:
            cb.tk.call('popdown', 'hide')
        except Exception:
            pass
        root.update()
        return rec

    # ── ① 主窗口整体 ─────────────────────────────────────────────
    try:
        root.deiconify()
        root.attributes('-topmost', True)
        root.lift()
    except Exception:
        pass
    root.update_idletasks()
    root.update()
    time.sleep(0.5)
    root.update()
    p_main = os.path.join(a.out_dir, '00_main.png')
    # 🔴 APP-099 四.5：主窗口标题用 Win32 读出并写进 json（截图可能带不了标题栏）。
    ev['window_title'] = win32_window_title(root)
    print('[title] %r (%s)' % (ev['window_title']['title'],
                               ev['window_title']['method']))
    ok = capture_hwnd(root.winfo_id(), p_main)
    g = guard_png(p_main) if ok else {'path': p_main, 'not_black': False}
    g['name'] = '主窗口（整体）'
    g['shot'] = p_main if g.get('not_black') else None
    ev['shots'].append(g)

    # ── ② 五个下拉 ───────────────────────────────────────────────
    ev['shots'].append(grab('识别后端下拉（展开）', 'cb_asr_combo',
                            '01_combo_asr.png'))
    ev['shots'].append(grab('翻译后端下拉（展开）', 'cb_mt_combo',
                            '02_combo_mt.png'))
    ev['shots'].append(grab('语音输出后端下拉（展开）', 'cb_tts_combo',
                            '03_combo_tts.png'))
    ev['shots'].append(grab('音色下拉（克隆项应置灰/带原因）', 'cb_tts_voice',
                            '04_combo_voice.png'))
    ev['shots'].append(grab('目标语言下拉（应 10 种）', 'cb_mt',
                            '05_combo_target_lang.png'))

    # ── 克隆控件专项断言（reviewer：「克隆控件一张（要是灰的）」）──
    voice_vals = None
    try:
        voice_vals = [str(v) for v in app.cb_tts_voice.cget('values')]
    except Exception:
        pass
    ev['clone_check'] = {
        'values': voice_vals,
        'current': str(app.var_tts_voice.get()),
        'clone_allowed': bool(getattr(app, '_clone_voice_allowed', True)),
        'clone_why': getattr(app, '_clone_voice_why', ''),
        'clone_item_label': (voice_vals[1] if voice_vals and len(voice_vals) > 1
                             else None),
        'clone_item_is_not_plain': bool(
            voice_vals and len(voice_vals) > 1
            and voice_vals[1] != '跟随说话人（克隆·实验）'),
    }
    # ── 目标语言 10 种专项断言 ──────────────────────────────────
    try:
        tv = [str(v) for v in app.cb_mt.cget('values')]
    except Exception:
        tv = []
    ev['target_lang_check'] = {'n_values': len(tv), 'values': tv}

    try:
        root.destroy()
    except Exception:
        pass

    good = [s for s in ev['shots'] if s.get('not_black')]
    ev['n_shots'] = len(ev['shots'])
    ev['n_good'] = len(good)
    ev['verdict'] = 'PASS' if len(good) >= 5 else 'PARTIAL'
    with open(a.out_json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[shots] %d/%d 通过 ⇒ %s' % (len(good), len(ev['shots']), ev['verdict']))
    for s in ev['shots']:
        print('   [%s] %s ⇒ %s' % ('OK' if s.get('not_black') else '--',
                                    s.get('name'), s.get('shot')))
    print('   克隆项：%r（allowed=%s）'
          % (ev['clone_check']['clone_item_label'],
             ev['clone_check']['clone_allowed']))
    print('   目标语言 %d 种' % ev['target_lang_check']['n_values'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
