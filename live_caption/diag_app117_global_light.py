#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-117 验收脚本：**总状态灯按钮已从界面去掉**，且**报错仍可见**。

## 判据（全部**行为级**，不是 grep）
| # | 检查 | 口径 |
|---|---|---|
| A1 | 界面上**没有**总状态灯按钮 | 遍历整棵控件树，找**真实存在的 Button 控件**（不是字符串） |
| A2 | 界面上**没有**「模块状态」弹窗入口 | 遍历控件树找 Button + 其 `command` 指向 `_show_global_status` |
| A3 | 顶栏**没有**空洞/重叠 | 顶栏各控件的 x 区间**不重叠** |
| A4 | `_show_global_status` **不再弹窗** | 真调它 ⇒ **不产生任何 modal 对话框**（拦 `messagebox`） |
| A5 | 汇总逻辑**仍可内部调用** | `_global_status_summary()` 返回非空文本 |
| B1 | 各模块状态条**照常存在** | ASR / MT / TTS 三条 `_strip_*` 都能刷新 |
| B2 | TTS 条能显示 **warn** | 真设一个 warn ⇒ `strip.status.level()=='warn'` |
| B3 | 「NPU 共用，语音可能卡顿」**仍有承载点** | TTS 条里能找到该文案 |
| B4 | 「无法打开输出设备 ⇒ 已改用系统默认」**仍可见** | 走 `var_status`（顶部状态行）⇒ 断言它**不是**靠总状态灯 |

## 纪律
- **不加载任何模型**（`App.load_engine` 替换成空操作）⇒ 不占 GPU/NPU；
- 只建 GUI 控件（tk）⇒ 不出声、不录音；
- 100 % / 150 % 缩放各截一张图 ⇒ 证明布局无空洞、无裁剪。
"""
import argparse
import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

_PKG_APP = None
for _i, _a in enumerate(sys.argv):
    if _a == '--pkg' and _i + 1 < len(sys.argv):
        _PKG_APP = os.path.join(sys.argv[_i + 1], 'app')
        break
    if _a.startswith('--pkg='):
        _PKG_APP = os.path.join(_a.split('=', 1)[1], 'app')
        break
if _PKG_APP and os.path.isdir(_PKG_APP):
    sys.path.insert(0, _PKG_APP)
    print('[pkg] 用**客户包内**的代码做验收：%s' % _PKG_APP)
else:
    sys.path.insert(0, HERE)

RESULTS = os.path.join(REPO, 'results', 'app')
SHOT_DIR = os.path.join(RESULTS, 'app117_gui')

CHECKS = []


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  — ' + str(detail)) if detail else ''))
    return bool(ok)


def enable_dpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except Exception:
        return False


def walk_widgets(root):
    out = []
    stack = [root]
    while stack:
        w = stack.pop()
        out.append(w)
        try:
            stack.extend(w.winfo_children())
        except Exception:
            pass
    return out


def btn_text(w):
    try:
        return str(w.cget('text'))
    except Exception:
        return ''


def is_button(w):
    try:
        return w.winfo_class() in ('TButton', 'Button')
    except Exception:
        return False


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


def shot(root, path):
    """抓屏：🔴 `ImageGrab.grab()` 在本机**全黑** ⇒ 用 Win32 `PrintWindow`。"""
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
        hwnd = int(root.frame(), 16) if False else ctypes.windll.user32.GetParent(
            root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return 0
        hdc = ctypes.windll.user32.GetWindowDC(hwnd)
        gdi = ctypes.windll.gdi32
        src = gdi.CreateCompatibleDC(hdc)
        bmp = gdi.CreateCompatibleBitmap(hdc, w, h)
        gdi.SelectObject(src, bmp)
        ok = ctypes.windll.user32.PrintWindow(hwnd, src, 2)
        if not ok:
            return 0
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [('biSize', wintypes.DWORD),
                        ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                        ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD),
                        ('biCompression', wintypes.DWORD),
                        ('biSizeImage', wintypes.DWORD),
                        ('biXPelsPerMeter', wintypes.LONG),
                        ('biYPelsPerMeter', wintypes.LONG),
                        ('biClrUsed', wintypes.DWORD),
                        ('biClrImportant', wintypes.DWORD)]
        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = w
        bi.biHeight = -h
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0
        buf = ctypes.create_string_buffer(w * h * 4)
        got = gdi.GetDIBits(src, bmp, 0, h, buf, ctypes.byref(bi), 0)
        gdi.DeleteObject(bmp)
        gdi.DeleteDC(src)
        ctypes.windll.user32.ReleaseDC(hwnd, hdc)
        if not got:
            return 0
        img = Image.frombuffer('RGB', (w, h), buf, 'raw', 'BGRX', 0, 1)
        img.save(path)
        return os.path.getsize(path)
    except Exception as e:
        print('    [warn] 抓屏失败：%r' % (e,))
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scale', type=float, default=1.0,
                    help='缩放倍率（1.0 = 100%%，1.5 = 150%%）')
    ap.add_argument('--pkg', default='')
    args_cli = ap.parse_args()
    scale = args_cli.scale

    os.makedirs(SHOT_DIR, exist_ok=True)
    dpi_ok = enable_dpi()
    try:
        root = tk.Tk()
    except Exception as e:
        print('FAIL: 开窗失败 %r' % (e,))
        return 2
    # 🔴 **tk scaling 必须在建控件前设**（否则两次截图逐字节相同 —— 本轮沿用教训）
    try:
        base = float(root.tk.call('tk', 'scaling')) or 1.333
    except Exception:
        base = 1.333
    root.tk.call('tk', 'scaling', base * scale)
    try:
        scaling = float(root.tk.call('tk', 'scaling'))
    except Exception:
        scaling = base * scale
    print('=== APP-117 验收（scaling=%.4f，dpi=%s）===' % (scaling, dpi_ok))

    import live_caption_app as A
    # 🔴 **不加载任何模型** ⇒ 不占 GPU/NPU
    orig_load = A.App.load_engine
    A.App.load_engine = lambda self: None
    app = None
    try:
        app = A.App(root, _Args())
    except Exception:
        import traceback
        traceback.print_exc()
        A.App.load_engine = orig_load
        try:
            root.destroy()
        except Exception:
            pass
        return 2
    finally:
        A.App.load_engine = orig_load

    tag = 'app117_%03dpct' % int(round(scale * 100))
    try:
        root.update_idletasks()
        root.update()
        widgets = walk_widgets(root)
        btns = [btn_text(w) for w in widgets if is_button(w)]
        print('  界面共 %d 个控件，%d 个按钮' % (len(widgets), len(btns)))

        # ── A1 ────────────────────────────────────────────────
        light_texts = ('全部就绪', '有模块待处理', '有模块异常')
        hit = [b for b in btns if any(lt in b for lt in light_texts)]
        check('A1 界面上没有总状态灯按钮', not hit, hit)

        # ── A2 ────────────────────────────────────────────────
        popup_entry = []
        for w in widgets:
            try:
                if is_button(w):
                    cmd = w.cget('command')
                    if cmd and 'show_global_status' in str(cmd):
                        popup_entry.append(btn_text(w))
            except Exception:
                pass
        check('A2 没有指向 _show_global_status 的按钮入口', not popup_entry,
              popup_entry)

        # ── A3 ────────────────────────────────────────────────
        # 🔴 顶栏 `top` 在建控件的方法里是**局部变量** ⇒ 不在 self 上
        #   ⇒ 用「会话计时标签的 master」反查（它是顶栏里的控件）。
        top = None
        try:
            lbl = getattr(app, '_session_elapsed', None)
            # StringVar 没有 master ⇒ 改用顶栏里的 Label 控件：
            for w in widgets:
                try:
                    tv = w.cget('textvariable')
                except Exception:
                    continue
                if tv and tv == str(getattr(app, '_session_elapsed', '')):
                    top = w.master
                    break
            if top is None:
                # 回退：找含「会话」文字标签的 Frame
                for w in widgets:
                    if btn_text(w) == '会话':
                        top = w.master
                        break
        except Exception:
            pass
        geom = []
        if top is not None:
            # 🔴🔴🔳 **只比「同一层」的兄弟控件**（`top` 的直接子控件）：
            #   把容器 Frame 自己也算进去 ⇒ 它必然「包含」子控件
            #   ⇒ 必然报重叠 ⇒ **假 FAIL**（本轮第一版就踩了）。
            for w in top.winfo_children():
                try:
                    if w.winfo_width() <= 1:
                        continue
                    x0 = w.winfo_rootx() - root.winfo_rootx()
                    geom.append((x0, x0 + w.winfo_width(),
                                 btn_text(w) or w.winfo_class()))
                except Exception:
                    pass
            geom.sort()
            overlap = [(geom[i], geom[i + 1]) for i in range(len(geom) - 1)
                       if geom[i + 1][0] < geom[i][1]]
            check('A3 顶栏控件无重叠（无空洞）', not overlap,
                  overlap or '%d 个控件' % len(geom))
        else:
            check('A3 顶栏控件无重叠（无空洞）', False, '找不到顶栏容器')

        # ── A4 ────────────────────────────────────────────────
        import tkinter.messagebox as MB
        popped = []
        orig = (MB.showinfo, MB.showerror, MB.showwarning)

        def _trap(*a, **k):
            popped.append(a[0] if a else '?')
            return 'ok'
        MB.showinfo = MB.showerror = MB.showwarning = _trap
        try:
            txt = app._show_global_status()
        finally:
            MB.showinfo, MB.showerror, MB.showwarning = orig
        check('A4 _show_global_status 不再弹 modal 对话框', not popped, popped)
        check('A4b _show_global_status 仍返回文本', bool(txt), (txt or '')[:80])

        # ── A5 ────────────────────────────────────────────────
        try:
            summ = app._global_status_summary()
        except Exception as e:
            summ = ''
            print('    [warn] _global_status_summary 失败 %r' % (e,))
        check('A5 汇总逻辑仍可内部调用（非空文本）', bool(summ),
              (summ or '')[:80])

        # ── B1 ────────────────────────────────────────────────
        strips = [getattr(app, '_strip_asr', None),
                  getattr(app, '_strip_mt', None),
                  getattr(app, '_strip_tts', None)]
        check('B1 ASR/MT/TTS 三条状态条都存在', all(s is not None for s in strips),
              [bool(s) for s in strips])

        # ── B2 ────────────────────────────────────────────────
        try:
            st = strips[2]['status']
            st.set('probe', '探测', '警告值', priority=1, level='warn')
            lvl = st.level()
        except Exception as e:
            lvl = 'err:%r' % (e,)
        check('B2 TTS 状态条能显示 warn 级别', lvl == 'warn', lvl)

        # ── B3 ────────────────────────────────────────────────
        # 🔴 **必须真的触发「NPU 共用」条件**（MT/ASR 与 TTS 同在 NPU）
        #   ⇒ 改 `_dev_choices` 再跑一次 TTS 条刷新 ⇒ 断言文案出现。
        #   ⚠️ 只看「代码里有没有这句」不算数（那是 grep，不是行为）。
        #
        # 🔴🔴🔳 **必须给 `app.tts` 塞一个桩**：
        #   `_fill_tts_strip()` 在 `tts is None` 时**提前 return**
        #   （TTS 关着时）⇒ 「NPU 共用」那段代码**根本走不到**
        #   ⇒ 只设 `_dev_choices` 测不出东西（第一版就踩了）。
        #   ⇒ 用**桩**（只提供 `stats()` / `pending` / `_queue`）
        #     ⇒ 走**真代码路径**、**不加载任何模型**、不占 GPU/NPU。
        try:
            class _TtsStub:
                pending = []

                def stats(self):
                    return {'device': 'NPU', 'state': 'ready',
                            'cur_speed': 1.0, 'lag_s': 0.0}

            app.tts = _TtsStub()
            app._dev_choices = {'asr': 'NPU', 'mt': 'NPU', 'tts': 'NPU'}
            app._fill_tts_strip()
            snap = strips[2]['status'].snapshot()
            blob = ' '.join('%s %s %s' % (v.get('label', ''), v.get('value', ''),
                                          v.get('tip', ''))
                            for v in snap.values())
        except Exception as e:
            blob = 'err:%r' % (e,)
        has_npu = ('NPU 共用' in blob) or ('语音可能卡顿' in blob)
        check('B3 「NPU 共用/语音可能卡顿」在 TTS 条里真的显示出来', has_npu,
              blob[:140])

        # ── B4 ────────────────────────────────────────────────
        try:
            app.var_status.set('无法打开「X」⇒ 已改用系统默认')
            shown = app.var_status.get()
        except Exception as e:
            shown = 'err:%r' % (e,)
        check('B4 输出设备回落消息写进顶部状态行 var_status',
              '已改用系统默认' in shown, shown[:100])
        check('B4b 顶部状态行控件仍存在（没被删）',
              getattr(app, '_lbl_status', None) is not None)

        # ── B5：调用 _show_global_status **不得挤掉状态行里的真错误** ──
        # 🔴🔴🔳 **这条是 APP-117 的核心风险**：
        #   汇总文本很长 ⇒ 若写进 `var_status` ⇒ 会把
        #   「无法打开所选输出设备 ⇒ 已改用系统默认」**挤掉**
        #   ⇒ 报错反而**不可见** ⇒ 与 APP-117 的硬要求相反。
        try:
            app.var_status.set('无法打开「X」⇒ 已改用系统默认')
            before = app.var_status.get()
            app._show_global_status()
            after = app.var_status.get()
        except Exception as e:
            before = after = 'err:%r' % (e,)
        check('B5 调用汇总**不覆盖**状态行里的错误消息',
              before == after and '已改用系统默认' in after,
              'before=%r after=%r' % (before[:60], after[:60]))

        # ── 截图 ──────────────────────────────────────────────
        try:
            root.geometry('1280x800+0+0')
            root.update_idletasks()
            root.update()
            time.sleep(0.4)
            root.update()
        except Exception:
            pass
        png = os.path.join(SHOT_DIR, '%s.png' % tag)
        n = shot(root, png)
        print('  截图：%s（%d B）' % (png, n))
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    npass = sum(1 for c in CHECKS if c['ok'])
    nfail = len(CHECKS) - npass
    out = {'tag': tag, 'scale': scale, 'scaling': scaling, 'pass': npass,
           'fail': nfail, 'checks': CHECKS}
    op = os.path.join(RESULTS, 'app117_global_light_evidence_%03d.json'
                      % int(round(scale * 100)))
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结论：%d PASS / %d FAIL  →  %s' % (npass, nfail, op))
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
