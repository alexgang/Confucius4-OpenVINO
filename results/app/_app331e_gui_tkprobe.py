#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app331e_gui_tkprobe.py —— 直接问 Tk 自己：主窗标题/尺寸到底是什么。

## 为什么
已确认两件互斥的事实：
  ① faulthandler：主线程已在 `tkinter/__init__.py:1505 mainloop`
     ⇒ `App.__init__` 已返回 ⇒ 2468 行 `root.title('实时字幕 MiniMVP v1.0')`
        与 2487 行 `root.geometry(...)` 都**已执行**；
  ② Win32 `EnumWindows`（PID 过滤后）：只有 `TkTopLevel vis=True 216x239 title='tk'`。

⇒ 「Tk 说已设标题」与「Win32 说还是 tk/216×239」冲突。
   可能：枚举拿到的**不是** root（另有第二个 Tk 进程/窗口）、或 title 被后续覆盖、
   或 Tk 用的是**独立线程**的 Tcl 解释器导致 winfo 与 Win32 不同步。

⇒ 本脚本**不枚举**，直接 `tkinter` 内部状态取真值：
   - patch `tkinter.Tk` ⇒ 抓住实例
   - patch `Tk.title` / `Tk.geometry` ⇒ 记录所有调用
   - `after(N)` 打印 `winfo_toplevel().title()` / `winfo_width/height` /
     `winfo_ismapped()` / `wm_geometry()`
   - 同时用 Win32 对**该实例的 winfo_id()** 查 GetWindowRect ⇒ 与 Tk 内部值对照
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import runpy
import sys
import tkinter

HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '_app_shadow')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')

STATE = {}


def _dump(root, tag):
    try:
        top = root.winfo_toplevel()
        wid = top.winfo_id()
        r = wt.RECT()
        user32 = ctypes.windll.user32
        ok = user32.GetWindowRect(wintypes_hwnd(wid), ctypes.byref(r))
        print('[%s] title=%r  winfo_toplevel.title=%r' % (tag, root.title(),
                                                        top.title()), flush=True)
        print('     winfo_width=%s winfo_height=%s  wm_geometry=%r  '
              'ismapped=%s  winfo_id=%s' % (top.winfo_width(),
                                            top.winfo_height(),
                                            top.wm_geometry(),
                                            top.winfo_ismapped(), wid),
              flush=True)
        print('     WIN32 GetWindowRect ok=%s rect=%s' % (
            ok, (r.left, r.top, r.right, r.bottom) if ok else None), flush=True)
        n = user32.GetWindowTextLengthW(wintypes_hwnd(wid))
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(wintypes_hwnd(wid), buf, n + 1)
        print('     WIN32 title=%r  visible=%s' % (
            buf.value, bool(user32.IsWindowVisible(wintypes_hwnd(wid)))),
            flush=True)
    except Exception as exc:                                # noqa: BLE001
        print('[%s] dump err %r' % (tag, exc), flush=True)


def wintypes_hwnd(hwnd):
    from ctypes import wintypes
    return wintypes.HWND(hwnd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--probe-after', type=float, default=20.0)
    args = ap.parse_args()

    root_dir = os.path.join(BASE, args.arm)
    out_dir = os.path.join(BASE, 'gui_probe_out')
    os.makedirs(out_dir, exist_ok=True)
    clone = os.path.join(out_dir, 'clone_voices')
    os.makedirs(clone, exist_ok=True)
    os.environ['LIVECAP_CLONE_VOICES_DIR'] = clone
    os.environ.setdefault('PYTHONUNBUFFERED', '1')

    _orig_tk = tkinter.Tk
    _orig_title = tkinter.Tk.title
    _orig_geometry = tkinter.Tk.geometry

    def patched_title(self, title=None):
        if title is not None:
            print('[call] Tk.title(%r)' % title, flush=True)
        return _orig_title(self, title)

    def patched_geometry(self, geometry=None):
        if geometry is not None:
            print('[call] Tk.geometry(%r)' % geometry, flush=True)
        return _orig_geometry(self, geometry)

    class TkProbe(_orig_tk):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            STATE['root'] = self
            print('[call] Tk() created id=%s' % id(self), flush=True)
            self.after(int(args.probe_after * 1000),
                       lambda: _dump(self, 'T+%.0fs' % args.probe_after))

    tkinter.Tk.title = patched_title
    tkinter.Tk.geometry = patched_geometry
    tkinter.Tk = TkProbe

    app_py = os.path.join(root_dir, 'app', 'live_caption_app.py')
    sys.argv = [
        app_py,
        '--file', os.path.join(SPKTEST, 'dialog3.wav'),
        '--autostart',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--tts', 'on', '--tts-device', 'NPU', '--tts-precision', 'f16',
        '--out', os.path.join(out_dir, 'subtitles.txt'),
    ]
    os.chdir(root_dir)
    sys.path.insert(0, os.path.join(root_dir, 'app'))
    print('[probe] start', flush=True)
    try:
        runpy.run_path(app_py, run_name='__main__')
    except SystemExit:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
