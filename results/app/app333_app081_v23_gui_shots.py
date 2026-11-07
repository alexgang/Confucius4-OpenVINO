#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app333 — APP-081 4d：在**v2.3 包内源码**上构造真 GUI，拍 100% / 150% 两张图，
并判「没有克隆入口」（不能有克隆选项，也不能有灰掉的选项）。

由仓库 `.venv/Scripts/python.exe` 运行（有 PIL / pywin32 / openvino）；
`sys.path` 指向干净解压目录的 `app/` ⇒ import 的是**包内**代码，不是 dev。
抓图用 `win_capture.capture_hwnd`（PrintWindow），不用 ImageGrab（本机全黑）。
不加载模型、不占 GPU/NPU。
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
REPO = os.path.dirname(os.path.dirname(HERE))


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
    a.source, a.translate, a.asr_lang = 'mic', 'en', 'auto'
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
    return a


def all_widget_texts(w, out):
    try:
        cls = w.winfo_class()
        if cls in ('TLabel', 'TCheckbutton', 'TButton', 'Label', 'Checkbutton'):
            out.append(str(w.cget('text')))
        if cls == 'TCombobox':
            try:
                out.extend([str(x) for x in w.cget('values')])
            except Exception:
                pass
    except Exception:
        pass
    try:
        for c in w.winfo_children():
            all_widget_texts(c, out)
    except Exception:
        pass
    return out


def shot(root, path, capture_hwnd):
    root.update_idletasks(); root.update()
    try:
        root.deiconify(); root.attributes('-topmost', True); root.lift()
    except Exception:
        pass
    root.update_idletasks(); root.update(); time.sleep(0.4); root.update()
    try:
        ok = capture_hwnd(root.winfo_id(), path)
    except Exception as e:
        return False, 'capture exception: %r' % (e,)
    if not ok or not os.path.isfile(path):
        return False, 'capture_hwnd 未产出文件'
    try:
        from PIL import Image
        lo, hi = Image.open(path).convert('L').getextrema()
        if hi - lo < 20:
            return False, '疑似黑图 extrema=(%s,%s)' % (lo, hi)
    except Exception as e:
        return False, '黑图守卫异常: %r' % (e,)
    return True, 'OK'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args()
    pkg = os.path.abspath(a.pkg)
    os.makedirs(a.out_dir, exist_ok=True)
    sys.path.insert(0, os.path.join(pkg, 'app'))
    sys.path.insert(0, HERE)          # win_capture
    sys.path.insert(0, REPO)

    import tkinter as tk                       # noqa: E402
    import live_caption_app as lca             # noqa: E402   ← 包内副本
    import translator                          # noqa: E402
    from win_capture import capture_hwnd       # noqa: E402

    ev = {'tool': 'app333', 'app': 'APP-081 4d GUI',
          'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'pkg': pkg,
          'lca_file': lca.__file__,
          'lca_sha256': sha256_file(lca.__file__),
          'runs': []}
    runs = []
    for scale in (1.0, 1.5):
        rec = {'scaling': scale}
        try:
            root = tk.Tk()
            root.geometry('%dx%d+0+0' % (int(1080 * scale), int(820 * scale)))
            root.tk.call('tk', 'scaling', scale)
            rec['tk_scaling_actual'] = float(root.tk.call('tk', 'scaling'))
            lca.App.load_engine = lambda self: None
            translator.TranslationService.set_engine = lambda self, k: True
            translator.TranslationService.set_device = lambda self, d: True
            app = lca.App(root, make_args())
            root.update_idletasks(); root.update(); time.sleep(0.5); root.update()
            texts = all_widget_texts(root, [])
            rec['tts_voices'] = list(getattr(app, 'tts_voices', []))
            rec['n_widget_texts'] = len(texts)
            rec['clone_texts'] = [t for t in texts if '克隆' in t]
            rec['follow_speaker_texts'] = [t for t in texts
                                           if 'follow_speaker' in t or '跟随说话人' in t]
            png = os.path.join(a.out_dir, 'v23_gui_scaling%03d.png'
                               % int(round(scale * 100)))
            ok, why = shot(root, png, capture_hwnd)
            rec['shot'] = png if ok else None
            rec['shot_why'] = why
            if ok:
                rec['shot_bytes'] = os.path.getsize(png)
                rec['shot_sha256'] = sha256_file(png)
            rec['window'] = [root.winfo_width(), root.winfo_height()]
            rec['verdict'] = ('PASS' if ok and rec['tts_voices'] == ['A']
                              and not rec['clone_texts']
                              and not rec['follow_speaker_texts'] else 'FAIL')
            try:
                root.destroy()
            except Exception:
                pass
        except Exception as e:
            rec['verdict'] = 'FAIL'
            rec['exception'] = repr(e)
        runs.append(rec)
        print('  [gui] scale=%.1f %s clone_texts=%r tts_voices=%r'
              % (scale, rec['verdict'], rec.get('clone_texts'),
                 rec.get('tts_voices')))
    ev['runs'] = runs
    ev['verdict'] = 'PASS' if all(r['verdict'] == 'PASS' for r in runs) else 'FAIL'
    with open(a.out_json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[%s] %s' % (ev['verdict'], a.out_json))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
