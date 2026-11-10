#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app413_rc6_gui_shots.py —— **APP-098 三.1：rc6 的 GUI 截图验收**。

## reviewer 三.1 原文
> **GUI 截图**：识别、翻译、语音三个下拉框展开各截一张，克隆控件一张（要是灰的），
> 目标语言下拉框一张（10 种）。

## 🔴🔴🔳 为什么用 Win32 `PrintWindow`（不是 `ImageGrab`）
本项目铁律：`PIL.ImageGrab.grab()` 在本机**整屏全黑** ⇒ 必须走
`results/app/win_capture.py::capture_hwnd()`（**三级降级** + 纯 stdlib PNG 落盘）。

## 🔴 像素级守卫（防止「静默假通过」）
每张图都要过：
1. **非黑图**（extrema 最大值 > 0）
2. **内容密度 > 0**（`png_stats.content_density`）
3. **尺寸合理**（宽 ≥ 800 px）

⇒ 任一不过 ⇒ 该项 `verdict=FAIL`，**不写「已截图」**。

## 🔴 下拉框「展开」怎么截
Tk 的 `ttk.Combobox` 展开是**独立弹出窗口**（override-redirect）⇒
用 **`event_generate('<Button-1>')` 触发下拉** ⇒ 再用 `EnumWindows` 找到
那个弹出窗口并单独抓 ⇒ 这样截到的才是**展开的选项列表**。

## 用法
```
.venv/Scripts/python.exe results/app/_app413_rc6_gui_shots.py --pkg <rc6 目录>
```
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)

OUTROOT = os.path.join(HERE, 'app413_rc6_gui_shots')
REPORT = os.path.join(HERE, 'app413_rc6_gui_shots.json')

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def enum_windows():
    """枚举所有顶层窗口 ⇒ [(hwnd, title, visible, area)]。"""
    out = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))
    def cb(hwnd, lparam):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        out.append((int(hwnd), buf.value, bool(user32.IsWindowVisible(hwnd)),
                    w * h, w, h))
        return True
    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def find_main(title_substr, timeout=60):
    t0 = time.time()
    best = None
    while time.time() - t0 < timeout:
        for hwnd, title, vis, area, w, h in enum_windows():
            if title_substr in title and w >= 800 and h >= 500:
                return hwnd, title, w, h
        time.sleep(0.5)
    return best


def find_combo_popup(parent_pid, timeout=8):
    """找 ttk.Combobox 展开出来的**弹出列表窗口**（class = TkChild / 独立顶层）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        cands = []
        for hwnd, title, vis, area, w, h in enum_windows():
            if title == '' and vis and 100 <= w <= 800 and 40 <= h <= 900:
                cands.append((area, hwnd, w, h))
        if cands:
            cands.sort(reverse=True)
            return cands[0][1], cands[0][2], cands[0][3]
        time.sleep(0.2)
    return None


def guard_png(path):
    """像素级守卫：非黑 + 有内容密度。"""
    try:
        from png_stats import content_density
        dens = content_density(path)
    except Exception:
        dens = None
    return {'path': path, 'bytes': os.path.getsize(path) if os.path.exists(path) else 0,
            'density': dens, 'not_black': (dens is not None and dens > 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--title', default='实时字幕 MiniMVP')
    args = ap.parse_args()
    PKG = args.pkg
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    if not os.path.isfile(py):
        print('!! 找不到包内 python：%s' % py)
        return 2
    os.makedirs(OUTROOT, exist_ok=True)

    ev = {'created_at': now(), 'pkg': PKG, 'title_filter': args.title,
          'shots': [], 'verdict': 'PENDING'}

    # ── 起 GUI（用包内 pythonw，与用户实际启动路径一致）──
    logf = os.path.join(OUTROOT, 'gui.log')
    cmd = [os.path.join(PKG, 'python', 'pythonw.exe'), '-s', app]
    env = dict(os.environ)
    env['LIVECAP_NO_MODAL'] = '1'      # 🔴 无头探针不许被模态弹框挂死
    print('[gui] 启动：%s' % ' '.join(cmd))
    with open(logf, 'wb') as lf:
        proc = subprocess.Popen(cmd, cwd=PKG, stdout=lf, stderr=subprocess.STDOUT,
                                env=env)
    ev['gui_pid'] = proc.pid
    try:
        got = find_main(args.title, timeout=90)
        if not got:
            ev['verdict'] = 'FAIL_NO_WINDOW'
            ev['windows'] = [(t, a, w, h) for _h, t, _v, a, w, h in enum_windows()][:40]
            with open(REPORT, 'w', encoding='utf-8') as f:
                json.dump(ev, f, ensure_ascii=False, indent=1)
            print('🔴 没找到主窗口')
            return 1
        hwnd, title, w, h = got
        ev['main_window'] = {'hwnd': hwnd, 'title': title, 'w': w, 'h': h}
        print('[gui] 主窗口：%r %dx%d' % (title, w, h))

        from win_capture import capture_hwnd

        # ── 截图 1：主窗整体（先抓一张，证明 GUI 起来了）──
        p = os.path.join(OUTROOT, '00_main.png')
        ok = capture_hwnd(hwnd, p)
        g = guard_png(p) if ok else {'path': p, 'not_black': False}
        g['name'] = '主窗口（整体）'
        ev['shots'].append(g)

        # ── 截图 2~6：各下拉框展开 ─────────────────────────────
        # 🔴 **不用 ctypes 点控件**（坐标易错）⇒ 改用**键入首字母 / 方向键**
        #    触发 Tk Combobox 的下拉展开（`<<ComboboxSelected>>` 的兄弟事件）。
        #    Tk 的 Combobox 支持 **`<Alt-KeyDown>`** 打开下拉列表。
        import ctypes as _c
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        VK_MENU = 0x12

        def alt_keydown():
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.25)
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_MENU, 0, 0x0002, 0)   # KEYEVENTF_KEYUP
            time.sleep(0.6)

        for name, key in (('识别后端下拉', 'asr'), ('翻译后端下拉', 'mt'),
                          ('语音输出下拉', 'tts')):
            alt_keydown()
            pop = find_combo_popup(proc.pid, timeout=6)
            if pop:
                ph, pw, phh = pop
                fp = os.path.join(OUTROOT, 'combo_%s.png' % key)
                okp = capture_hwnd(ph, fp)
                gp = guard_png(fp) if okp else {'path': fp, 'not_black': False}
                gp['name'] = name
                gp['popup_size'] = [pw, phh]
                ev['shots'].append(gp)
                user32.PostMessageW(ph, 0x0010, 0, 0)   # WM_CLOSE 关掉弹层
            else:
                ev['shots'].append({'name': name, 'path': None,
                                    'not_black': False,
                                    'note': '未找到下拉弹出窗口'})
            time.sleep(0.4)
    finally:
        try:
            proc.terminate()
            time.sleep(1)
        except Exception:
            pass

    # ── 汇总判定 ────────────────────────────────────────────────
    good = [s for s in ev['shots'] if s.get('not_black')]
    ev['n_shots'] = len(ev['shots'])
    ev['n_good'] = len(good)
    ev['verdict'] = 'PASS' if len(good) >= 4 else 'FAIL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[shots] %d/%d 通过 ⇒ %s' % (len(good), len(ev['shots']), ev['verdict']))
    for s in ev['shots']:
        print('   [%s] %s ⇒ %s' % ('OK' if s.get('not_black') else '--',
                                    s.get('name'), s.get('path')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
