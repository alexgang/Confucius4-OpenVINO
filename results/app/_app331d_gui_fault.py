#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app331d_gui_fault.py —— 用 **python.exe**（有 stdout）跑 GUI，并在 N 秒后
用 `faulthandler.dump_traceback_later(..., exit=True)` 打印**所有线程**栈并退出。

## 为什么
- `pythonw.exe` 的 stdout 是 None ⇒ App 里的 `print` 全丢 ⇒ gui.log 恒 0 B
  ⇒ 无法从日志判断卡点。
- 上一轮那份「栈在 mainloop」的 faulthandler 证据很可能取自**别的进程**
  （pythonw 看不到 stdout，且 dump 走 stderr）。

⇒ 本脚本：`faulthandler.dump_traceback_later(N, exit=True)` ⇒ 栈写到 **stdout**
   （因为是 python.exe）⇒ 落盘可读。
"""
from __future__ import annotations

import argparse
import faulthandler
import os
import runpy
import sys

HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '_app_shadow')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--fault-after', type=float, default=90.0)
    args = ap.parse_args()

    root = os.path.join(BASE, args.arm)
    out_dir = os.path.join(BASE, 'gui_probe_out')
    os.makedirs(out_dir, exist_ok=True)
    clone = os.path.join(out_dir, 'clone_voices')
    os.makedirs(clone, exist_ok=True)
    os.environ['LIVECAP_CLONE_VOICES_DIR'] = clone
    os.environ.setdefault('PYTHONUNBUFFERED', '1')

    app_py = os.path.join(root, 'app', 'live_caption_app.py')
    sys.argv = [
        app_py,
        '--file', os.path.join(SPKTEST, 'dialog3.wav'),
        '--autostart',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--tts', 'on', '--tts-device', 'NPU', '--tts-precision', 'f16',
        '--out', os.path.join(out_dir, 'subtitles.txt'),
    ]
    os.chdir(root)
    sys.path.insert(0, os.path.join(root, 'app'))

    print('[fault] dump_traceback_later(%.0fs, exit=True)' % args.fault_after,
          flush=True)
    faulthandler.dump_traceback_later(args.fault_after, exit=True)
    try:
        runpy.run_path(app_py, run_name='__main__')
    except SystemExit:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
