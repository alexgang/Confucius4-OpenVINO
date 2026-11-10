#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app331c_gui_probe2.py —— APP-093 §3.7 定位探针（增强版）。

## 为什么需要 v2
v1 探针（`_app331b_gui_probe.py`）只枚举 **IsWindowVisible 且标题非空** 的窗口，
5 分钟内只看到 `(14551996, 23832, 216, 239, 'tk')`
⇒ **无法区分**下列三种情况：
  ① `App.__init__` 卡住（根本没走到 `root.title()`），
  ② 标题已设但窗口**不可见**（`IsWindowVisible` 过滤掉了），
  ③ 枚举函数本身有 bug（hwnd 被截断 / PID 过滤错）。

⇒ v2 枚举**全部**顶层窗口（**不过滤可见性**、不过滤标题），
   打印 `hwnd / pid / class / title / rect / visible`，
   并**持续跟踪 gui.log 尾部**（看 App 自己停在哪一行日志）。

## 用法
```
.venv/Scripts/python.exe results/app/_app331c_gui_probe2.py --arm after --seconds 900
```
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import time

HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '_app_shadow')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')


def enum_all():
    """枚举**所有**顶层窗口（含不可见、空标题）。"""
    user32 = ctypes.windll.user32
    out = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, lparam):
        try:
            wpid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cbuf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cbuf, 256)
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            out.append({
                'hwnd': int(ctypes.cast(hwnd, ctypes.c_void_p).value or 0),
                'pid': int(wpid.value),
                'cls': cbuf.value,
                'title': buf.value,
                'w': r.right - r.left,
                'h': r.bottom - r.top,
                'vis': bool(user32.IsWindowVisible(hwnd)),
            })
        except Exception:
            pass
        return True

    user32.EnumWindows(proc(cb), None)
    return out


def tail(path, n=6):
    try:
        with open(path, 'rb') as f:
            data = f.read()
        lines = [x for x in data.decode('utf-8', 'replace').splitlines() if x.strip()]
        return lines[-n:]
    except Exception as exc:
        return ['<log err %r>' % (exc,)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--seconds', type=float, default=900.0)
    args = ap.parse_args()

    root = os.path.join(BASE, args.arm)
    wav = os.path.join(SPKTEST, 'dialog3.wav')
    out_dir = os.path.join(BASE, 'gui_probe_out')
    os.makedirs(out_dir, exist_ok=True)
    gui_log = os.path.join(out_dir, 'gui.log')

    cmd = [
        os.path.join(root, 'python', 'pythonw.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--file', wav, '--autostart',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--tts', 'on', '--tts-device', 'NPU', '--tts-precision', 'f16',
        '--out', os.path.join(out_dir, 'subtitles.txt'),
    ]
    env = dict(os.environ)
    env['LIVECAP_CLONE_VOICES_DIR'] = os.path.join(out_dir, 'clone_voices')
    os.makedirs(env['LIVECAP_CLONE_VOICES_DIR'], exist_ok=True)

    lf = open(gui_log, 'wb')
    p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=root)
    print('spawn pid', p.pid, flush=True)

    t0 = time.time()
    last_sig = None
    try:
        while time.time() - t0 < args.seconds:
            time.sleep(5.0)
            el = time.time() - t0
            wins = [w for w in enum_all() if w['pid'] == p.pid]
            sig = tuple(sorted((w['w'], w['h'], w['title'], w['vis']) for w in wins))
            if sig != last_sig:
                print('--- t=%.0fs ---' % el, flush=True)
                for w in wins:
                    print('   hwnd=%-10d %-22s vis=%-5s %dx%-4d title=%r'
                          % (w['hwnd'], w['cls'], w['vis'], w['w'], w['h'],
                             w['title']), flush=True)
                last_sig = sig
            tl = tail(gui_log)
            print('   [log %dB] %s' % (os.path.getsize(gui_log) if os.path.exists(gui_log) else -1,
                                       ' | '.join(tl)), flush=True)
            if any('MiniMVP' in w['title'] for w in wins):
                print('MAIN WINDOW READY at t=%.0fs' % el, flush=True)
                break
    finally:
        try:
            p.terminate()
            p.wait(timeout=10)
        except Exception:
            pass
        lf.close()
    print('done', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
