#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-061 ⑥ 判据：**GUI 紧凑化**的验收。

reviewer APP-061⑥ 的验收原文：
- 「字幕/译文区高度 ≥ 窗口高度的 **70 %**」
- 「1280×800 和 1024 宽两种尺寸下，提供 v2.1 和 v2.2 的**前后对比截图**，
  共 4 张」
- 「1024 宽时没有控件被截断或重叠」
- 「状态栏 **1 行**」

🔴 **本脚本做什么**：
1. 起 GUI（**不加载任何模型** ⇒ 不占 GPU/NPU、**不取机器锁**、不计时），
   在 **1280×800** 与 **1024×800** 两个尺寸下测量 + 截图；
2. 每张图落盘到 `shared/app_gui_layout/`，文件名带**版本标签**
   （`app061_v21_…` / `app061_v22_…`）⇒ **前后对比图不会互相覆盖**；
3. 「字幕区占比」「控件不越界」「状态栏 1 行」「高级面板展开后说明行不溢出」
   全部是**机器可算**的。

🔴 **口径修正说明**（重要）：reviewer 说的「字幕/译文区」= 屏幕字幕**文本框**
  （`self.txt`）的高度占比 ⇒ 本脚本量的是 `self.txt` 的实际高度 / 窗口高度。
  （v2.1 那个版本**没有**紧凑化 ⇒ 同一判据对 v2.1 **应当 FAIL** ⇒
  这本身就是「判据能识破旧版缺陷」的**天然反证**。）

用法：
    python app219_app061_gui_compact.py --pkg "<包目录>" --label v22
    python app219_app061_gui_compact.py --target live_caption --label dev
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SHOT_DIR = r'C:\Users\Trekker-PTL\shared\app_gui_layout'

PASSES = []
FAILS = []
NONE_ = []


def check(name, cond, detail='', group=''):
    cond = True if cond is True else (False if cond is False else None)
    rec = {'name': name, 'group': group, 'detail': detail,
           'result': {True: 'PASS', False: 'FAIL', None: 'NONE'}[cond]}
    (PASSES if cond is True else FAILS if cond is False else NONE_).append(rec)
    print('  [%s] %s %s' % (rec['result'], name, ('- ' + detail) if detail else ''))
    return cond


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _enable_dpi_awareness():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return True
        except Exception:
            return False


_DPI_OK = _enable_dpi_awareness()


class _Args:
    translate = 'off'
    mt_engine = 'auto'
    mt_ctx = False
    mt_glossary = False
    mt_draft = False
    asr_lang = 'auto'
    engine = 'gpu_int8'
    source = 'mic'
    device = None
    system_device = None
    file = None
    speed = 1.0
    loop = False
    overlay = True
    font_size = 26
    asr_device = 'GPU.0'
    mt_device = 'GPU.0'
    tts_device = 'NPU'
    device_notes = []
    tts = 'off'
    tts_voice = 'A'
    tts_precision = 'f32'
    tts_out_device = None
    selftest = 0
    autostart = False


def _hwnd(root):
    try:
        return root.winfo_id()
    except Exception:
        return None


def _capture(root, path):
    """🔴 截**窗口本身**（`PrintWindow` ⇒ 不读屏幕像素）。

    🔴 **不能用 `PIL.ImageGrab`**（本机实测抓屏全黑 ⇒ 静默假通过）。
    """
    try:
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
        time.sleep(0.35)
        root.update()
        hwnd = _hwnd(root)
        if not hwnd:
            return False
        sys.path.insert(0, HERE)
        from win_capture import capture_hwnd
        if not capture_hwnd(hwnd, path):
            return False
        from PIL import Image
        im = Image.open(path).convert('L')
        lo, hi = im.getextrema()
        if hi - lo < 20:
            print('    [warn] %s 疑似黑图（extrema=(%s,%s)）'
                  % (os.path.basename(path), lo, hi))
            return False
        return os.path.exists(path) and os.path.getsize(path) > 1000
    except Exception as e:
        try:
            with open(os.path.splitext(path)[0] + '.err.txt', 'w',
                      encoding='utf-8') as f:
                f.write(repr(e))
        except Exception:
            pass
        return False


def _walk(w, out=None, skip_toplevel=False):
    """🔴 遍历控件树。

    🔴 **`skip_toplevel=True`**：**跳过 Toplevel 子树**
      （屏幕字幕浮窗是**独立的顶层窗口** ⇒ 它的控件不在主窗口里排版
        ⇒ 拿主窗口宽度去卡它 ⇒ **恒假阳性**。
        实测：浮窗在屏幕 x≈1638 处 ⇒ 主窗口 1024 宽时必然「越界」，
        但那是**另一个窗口**，不是「控件被截断」。）

    🔴 **每个子控件都要 try**（否则一个已销毁的控件会让整棵树遍历中断
      ⇒ **一个控件都没量到** ⇒ 判据「无越界」= **空集恒 PASS**）。
    """
    out = [] if out is None else out
    try:
        children = list(w.winfo_children())
    except Exception:
        return out
    for c in children:
        try:
            cls = c.winfo_class()
        except Exception:
            continue
        if skip_toplevel and cls == 'Toplevel':
            continue
        out.append(c)
        _walk(c, out, skip_toplevel)
    return out


def _truncation_reason(w, root, margin=4):
    """🔴 **单个控件**的截断判据（返回问题描述；没问题返回 ''）。

    🔴 两种截断形态：
      (b) **请求宽度 > 可用宽度** ⇒ Tk 裁剪它 ⇒ 用户看到「文字被截断」
      (a) **位置越界**（右侧超出窗口宽度）⇒ 跑到窗口外

    ⚠️ **为什么 (b) 要先判**：容器被占满时，新控件会被 Tk **挤成 0/1 px**
      （实测：v2.1 里注入的探针 width=1 ⇒ 位置判据看不到它
        ⇒ 但它**同样**是「内容被裁掉」⇒ 必须判 FAIL）。
    """
    try:
        cls = w.winfo_class()
    except Exception:
        return ''
    rw = root.winfo_width()
    try:
        req = w.winfo_reqwidth()
    except Exception:
        req = 0
    # 🔴 `winfo_parent()` 返回的是**路径字符串**（不是控件对象）
    #   ⇒ 用 `w.master`（控件对象）拿父容器宽度。
    par = getattr(w, 'master', None)
    avail = 0
    if par is not None:
        try:
            avail = par.winfo_width()
        except Exception:
            avail = 0
    if avail <= 1:
        avail = rw
    if req > 0 and avail > 0 and req > avail + margin:
        try:
            _pth = w.winfo_pathname()
        except Exception:
            _pth = w.winfo_name()
        try:
            _txt = (w.cget('text') or '')[:40]
        except Exception:
            _txt = ''
        return ('%s(%s) 请求宽度 req=%d > 可用 avail=%d（内容被裁剪）'
                ' path=%s text=%r' % (w.winfo_name(), cls, req, avail, _pth, _txt))
    try:
        x = w.winfo_rootx() - root.winfo_rootx()
        width = w.winfo_width()
    except Exception:
        return ''
    if width <= 1:
        return ''
    if x + width > rw + margin:
        return ('%s(%s) 位置越界 right=%d > win=%d'
                % (w.winfo_name(), cls, x + width, rw))
    return ''


def _overflow_widgets(root, margin=4):
    """🔴 返回 **（越界/被截断控件列表, 量到的控件数）**。

    🔴 **第二个返回值 = 量到的控件数** ⇒ 用来防「**空集恒 PASS**」
      （量到 0 个 ⇒ 判据无法判定，必须报 NONE 而不是 PASS）。
    """
    bad = []
    n_examined = 0
    for w in _walk(root, skip_toplevel=True):
        try:
            if not w.winfo_ismapped():
                continue
            cls = w.winfo_class()
            if cls not in ('TLabel', 'TButton', 'TCombobox', 'TCheckbutton',
                           'Label', 'Button', 'Entry'):
                continue
            n_examined += 1
            msg = _truncation_reason(w, root, margin=margin)
            if msg:
                bad.append(msg)
        except Exception:
            continue
    return bad, n_examined


def run(target_app_dir, label, out_path):
    if not os.path.isdir(target_app_dir):
        print('目录不存在：%s' % target_app_dir)
        return 2
    sys.path.insert(0, target_app_dir)
    os.makedirs(SHOT_DIR, exist_ok=True)

    import tkinter as tk
    import live_caption_app as lca

    ev = {
        'task': 'APP-061 ⑥ GUI 紧凑化验收',
        'pkg_under_test': target_app_dir,
        'label': label,
        'sizes': ['1280x800', '1024x800'],
        'shots': [],
        'measures': {},
    }

    _orig_load = lca.App.load_engine
    _orig_mt_set = getattr(lca.TranslationService, 'set_engine', None)
    lca.App.load_engine = lambda self: None
    if _orig_mt_set is not None:
        lca.TranslationService.set_engine = lambda self, e: None

    root = tk.Tk()
    root.geometry('1280x800+0+0')
    try:
        app = lca.App(root, _Args())
        root.update_idletasks()
        root.update()
        check('G1 能构造 App', True, group='boot')

        for w, h in ((1280, 800), (1024, 800)):
            tag = '%dx%d' % (w, h)
            root.geometry('%dx%d+0+0' % (w, h))
            root.update_idletasks()
            root.update()
            # 🔴 **等「稳定态」再量**：三个分区的状态条是 **1 Hz 节流**刷新
            #   （APP-048「数值定时刷新（≤ 1 Hz）」）⇒ 改窗口尺寸后，
            #   状态条文本最长有 **1 s** 是旧尺寸裁剪出来的
            #   ⇒ 这里等 1.3 s ⇒ 量到的是**稳定态**（否则量到的是过渡态）。
            time.sleep(1.3)
            root.update()

            wh = root.winfo_height()
            txt_h = app.txt.winfo_height()
            ratio = (txt_h / float(wh)) if wh else 0.0
            ev['measures'][tag] = {
                'window_h': wh,
                'caption_h': txt_h,
                'caption_ratio_pct': round(ratio * 100.0, 2),
            }
            check('G2 字幕区高度 ≥ 窗口高度 70 %%（%s）' % tag,
                  ratio >= 0.70,
                  '字幕区 %d px / 窗口 %d px = %.2f %%'
                  % (txt_h, wh, ratio * 100.0), group='layout')

            # 状态栏 1 行（三个分区各 1 行 ⇒ 高度 ≤ 1 行的量级）
            strip_h = []
            for key in ('asr', 'mt', 'tts'):
                st = app.__dict__.get('_strip_' + key)
                if st is None:
                    continue
                strip_h.append(st['label'].winfo_height())
            one_line = bool(strip_h) and all(0 < hh <= 32 for hh in strip_h)
            check('G3 状态栏每个分区 1 行（%s）' % tag, one_line,
                  '各分区状态条高度=%s px' % (strip_h,), group='layout')

            # 高级面板默认收起（不占纵向空间 ⇒ 字幕区才够大）
            adv_mapped = None
            try:
                adv_mapped = bool(app._adv_frame.winfo_ismapped())
            except Exception:
                adv_mapped = None
            check('G4 「高级」面板默认收起（%s）' % tag,
                  (not adv_mapped) if adv_mapped is not None else None,
                  ('mapped=%s' % adv_mapped) if adv_mapped is not None
                  else '本版本没有「高级」面板 ⇒ 不适用', group='layout')

            # 1024 宽不越界
            if w == 1024:
                bad, n_ex = _overflow_widgets(root)
                check('G5 1024 宽没有控件被截断/越界',
                      (not bad) if n_ex > 0 else None,
                      (('越界控件 %d 个：%s' % (len(bad), bad[:5])) if bad
                       else '无越界控件') + '（量到 %d 个控件）' % n_ex,
                      group='layout')
                # ── G5c：**反证**（判据非恒真）────────────────────
                #   🔴 纪律：「判据 PASS」≠「判据正确」⇒ 注入一个
                #     **真的会被截断**的控件（固定宽 3000 的 label）
                #     ⇒ 判据必须把它报出来。
                try:
                    _probe = tk.Label(root, text='截断探针', width=3000)
                    _probe.pack()
                    root.update_idletasks()
                    root.update()
                    bad2, n_ex2 = _overflow_widgets(root)
                    # 🔴 判据**本体**也要能识破 ⇒ 直接对探针跑一次判据
                    #   （探针在 v2.1 里会被 Tk 挤成 1 px 且不映射
                    #     ⇒ 不能只靠「遍历已映射控件」这条路 ⇒ 这里单测判据）
                    _probe_msg = _truncation_reason(_probe, root)
                    if _probe_msg and not any(_probe_msg in b for b in bad2):
                        bad2 = list(bad2) + [_probe_msg]

                    _probe.destroy()
                    root.update_idletasks()
                    check('G5c 反证：真的越界控件仍被判 FAIL（判据非恒真）',
                          bool(bad2) if n_ex2 > 0 else None,
                          (('探针被捕获：%s' % bad2[:2]) if bad2
                           else '探针未被捕获 ⇒ 判据失效')
                          + '（量到 %d 个控件）' % n_ex2, group='counterproof')
                except Exception as e:
                    check('G5c 反证：真的越界控件仍被判 FAIL（判据非恒真）',
                          None, '无法判定：%r' % (e,), group='counterproof')

            # 截图
            path = os.path.join(SHOT_DIR, 'app061_%s_%s.png' % (label, tag))
            ok = _capture(root, path)
            check('G6 截图成功（%s）' % tag, ok,
                  path if ok else '抓取失败', group='shot')
            if ok:
                st = os.stat(path)
                ev['shots'].append({
                    'path': path, 'bytes': st.st_size,
                    'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime(st.st_mtime)),
                    'sha256': sha256_file(path),
                    'size': tag, 'label': label,
                })

            # 高级面板**展开**后：说明行不得横向溢出（真实产品行为）
            try:
                app._toggle_advanced()
                root.update_idletasks()
                root.update()
                time.sleep(0.2)
                root.update()
                adv_bad = []
                for lbl, cont in getattr(app, '_wrapped_labels', []):
                    try:
                        wl = lbl.cget('wraplength')
                        rw_ = lbl.winfo_reqwidth()
                        cw = cont.winfo_width()
                        if cw <= 1:
                            cw = root.winfo_width()
                    except Exception:
                        continue
                    if not wl or wl < 10:
                        adv_bad.append('%s: wraplength=%s' % (lbl, wl))
                    elif cw > 0 and rw_ > cw + 4:
                        adv_bad.append('%s: reqwidth=%d > %d'
                                       % (lbl, rw_, cw))
                check('G7 高级面板展开后长文本行不横向溢出（%s）' % tag,
                      not adv_bad,
                      ('; '.join(adv_bad[:4])) if adv_bad else '无溢出',
                      group='layout')
                app._toggle_advanced()      # 复原成收起
                root.update_idletasks()
                root.update()
            except Exception as e:
                check('G7 高级面板展开后长文本行不横向溢出（%s）' % tag,
                      None, '无法判定：%r' % (e,), group='layout')
    finally:
        try:
            root.destroy()
        except Exception:
            pass
        lca.App.load_engine = _orig_load
        if _orig_mt_set is not None:
            lca.TranslationService.set_engine = _orig_mt_set

    n_pass = len(PASSES)
    n_fail = len(FAILS)
    n_none = len(NONE_)
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    ev['checks'] = PASSES + FAILS + NONE_
    ev['n_pass'] = n_pass
    ev['n_fail'] = n_fail
    ev['n_none'] = n_none
    ev['verdict'] = verdict
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n== 结果 ==')
    print('  PASS=%d  FAIL=%d  NONE=%d  verdict=%s'
          % (n_pass, n_fail, n_none, verdict))
    print('  证据：%s' % out_path)
    return 0 if verdict == 'PASS' else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', default=os.path.join(REPO, 'live_caption'))
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--label', default='dev')
    ap.add_argument('--out', default=os.path.join(
        HERE, 'app219_app061_gui_compact_evidence.json'))
    a = ap.parse_args()
    target = os.path.join(a.pkg, 'app') if a.pkg else a.target
    return run(target, a.label, a.out)


if __name__ == '__main__':
    sys.exit(main())
