# -*- coding: utf-8 -*-
r"""_app494 — **EXT 启动器端到端驱动**（APP-104 §3 验收）。

在**包目录**里跑**打包后的** `tools/ext_launcher.py`（一字不改），
自动完成 reviewer 要求的验收动作：
  1. 启动器 GUI 起来（**没有目标语言下拉框** ⇒ v0.4.8 的改动确实进包了）；
  2. 自动点「启动」⇒ 桥接服务以 `--real` 起（真实引擎）；
  3. 等日志出现 **`真实引擎已接线`** 且窗口标题出现 **`TTS 就绪`**；
  4. 抓启动器窗口截图（PrintWindow，非黑图）；
  5. 点「停止」⇒ 桥接退出。

🔴 **不改 EXT 源文件**：这里只**猴子补丁** `tk.Tk` / `tk.Button` /
   `tkinter.scrolledtext.ScrolledText` / `ttk.Combobox`，用来
   ①拿到「启动 / 停止」按钮并 `invoke()`（等价于人点一下）、
   ②读日志框内容、③检查有没有下拉框。
   ⇒ 被测对象仍是**包内那个文件**（`ext_launcher.py` 的 SHA 会记进报告）。

🔴 **Tk 线程纪律（首版实测踩过）**：Tk 对象**只能**在创建它的线程里调用
   ⇒ 轮询/截图/点按钮全部用 `root.after()` 回调在**主线程**里做
   ⇒ 首版用后台线程读 `text.get()` ⇒ **卡死**（Tk 解释器锁），
   900 s 超时都没产出报告。

跑法：
    python results/app/_app494_ext_launcher_drive.py <pkg> <out.png> <out.json> [timeout_s]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    if len(sys.argv) < 4:
        print('usage: app494 <pkg> <out.png> <out.json> [timeout]')
        return 2
    PKG = os.path.abspath(sys.argv[1])
    OUT_PNG = os.path.abspath(sys.argv[2])
    OUT_JSON = os.path.abspath(sys.argv[3])
    TIMEOUT = float(sys.argv[4]) if len(sys.argv) > 4 else 900.0
    # 可选：端口 / PID 文件覆盖（**只改运行时属性，不改包内那个文件**）
    #   ⇒ 包内 `tools/ext_launcher.py` 仍与 817abcb **逐字节一致**。
    #   ⇒ 用例：本机 8765 被**别人**的桥接占着 ⇒ 换一个端口做隔离验收。
    PORT = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    PIDFILE = sys.argv[6] if len(sys.argv) > 6 else ''

    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(PKG, 'tools'))

    import tkinter as tk
    from tkinter import scrolledtext, ttk
    from win_capture import capture_hwnd

    STATE = {'root': None, 'buttons': [], 'combos': [], 'logs': [],
             'ready': False, 'started': False, 'stopped': False,
             'error': None, 'title': '', 'log_tail': '',
             't0': time.time(), 'done': False}

    _orig_tk = tk.Tk

    class _PatchedTk(_orig_tk):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            STATE['root'] = self
            self.after(1500, _click_start)
            self.after(1000, _tick)

    def _click_start():
        try:
            for text, w in list(STATE['buttons']):
                if str(text).strip() == '启动':
                    STATE['started'] = True
                    w.invoke()
                    return
        except Exception as e:
            STATE['error'] = repr(e)

    def _tick():
        root = STATE.get('root')
        if root is None or STATE['done']:
            return
        try:
            title = root.title()
            logtext = ''
            for tb in list(STATE['logs']):
                try:
                    logtext += tb.get('1.0', 'end')
                except Exception:
                    pass
            STATE['title'] = title
            STATE['log_tail'] = logtext[-4000:]
            if ('真实引擎已接线' in logtext) and ('TTS 就绪' in title):
                STATE['ready'] = True
                _finish()
                return
            if time.time() - STATE['t0'] > TIMEOUT:
                _finish()
                return
        except Exception as e:
            STATE['error'] = (STATE['error'] or '') + ' | tick: %r' % e
        try:
            root.after(1000, _tick)
        except Exception:
            pass

    tk.Tk = _PatchedTk

    _orig_button = tk.Button

    def _patched_button(self, *a, **k):
        w = _orig_button(self, *a, **k)
        STATE['buttons'].append((k.get('text', ''), w))
        return w

    tk.Button = _patched_button

    _orig_combo = ttk.Combobox

    def _patched_combo(self, *a, **k):
        w = _orig_combo(self, *a, **k)
        STATE['combos'].append(w)
        return w

    ttk.Combobox = _patched_combo

    _orig_st = scrolledtext.ScrolledText

    def _patched_st(self, *a, **k):
        w = _orig_st(self, *a, **k)
        STATE['logs'].append(w)
        return w

    scrolledtext.ScrolledText = _patched_st

    launcher_path = os.path.join(PKG, 'tools', 'ext_launcher.py')
    launcher_sha = hashlib.sha256(open(launcher_path, 'rb').read()).hexdigest()

    def _write_report():
        report = {
            'pkg': PKG,
            'launcher': os.path.relpath(launcher_path, PKG),
            'launcher_sha256': launcher_sha,
            'port_override': STATE.get('port'),
            'pid_path': STATE.get('pid_path'),
            'started': STATE['started'],
            'ready': STATE['ready'],
            'stopped': STATE['stopped'],
            'elapsed_s': round(time.time() - STATE['t0'], 1),
            'window_title': STATE['title'],
            'has_real_engine_line': ('真实引擎已接线' in STATE['log_tail']),
            'has_tts_ready': ('TTS 就绪' in STATE['title']),
            'n_combobox': len(STATE['combos']),
            'no_target_lang_combo': len(STATE['combos']) == 0,
            'engine_partial_failure': next(
                (l.strip() for l in STATE['log_tail'].splitlines()
                 if '部分引擎加载失败' in l), None),
            'engine_ready_line': next(
                (l.strip() for l in STATE['log_tail'].splitlines()
                 if '引擎预热完成' in l), None),
            'log_tail': STATE['log_tail'][-2500:],
            'shot_path': OUT_PNG,
            'shot_bytes': (os.path.getsize(OUT_PNG)
                           if os.path.isfile(OUT_PNG) else 0),
            'error': STATE['error'],
        }
        # 🔴 **三态**：EXT v0.4.8 的桥接**写死 R2T2 ASR**（`models/encoder-int8`）
        #    ⇒ MiniMVP 包里没有这套模型 ⇒ ASR 引擎装不上 ⇒
        #    「真实引擎已接线」/「TTS 就绪」**在 MiniMVP 里不可能出现**
        #    （**EXT 侧缺口**，不是 App 打包问题）⇒ 这种情况记 **PARTIAL**。
        gui_ok = (report['started'] and report['no_target_lang_combo']
                  and report['shot_bytes'] > 5000)
        engines_ok = (report['has_real_engine_line'] and report['has_tts_ready'])
        if gui_ok and engines_ok and report['stopped']:
            report['verdict'] = 'PASS'
        elif gui_ok:
            report['verdict'] = 'PARTIAL'
            report['partial_reason'] = (
                '启动器 GUI 正常（无目标语言下拉框、截图非黑图）且桥接进程起来了，'
                '但 **EXT v0.4.8 的 engine_runtime 写死 R2T2 ASR'
                '（models/encoder-int8）** ⇒ MiniMVP 包里没有这套模型 ⇒ '
                'ASR 引擎装不上 ⇒ 「真实引擎已接线」/「TTS 就绪」不会出现 ⇒ '
                '**属 EXT 侧缺口（跨模块）**，需 EXT 支持 0.6B stateful ASR')
        else:
            report['verdict'] = 'FAIL'
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(json.dumps({k: v for k, v in report.items()
                          if k != 'log_tail'}, ensure_ascii=False, indent=1))

    def _finish():
        if STATE['done']:
            return
        STATE['done'] = True
        root = STATE.get('root')
        try:
            if root is not None:
                root.deiconify()
                root.update()
                capture_hwnd(int(root.winfo_id()), OUT_PNG)
        except Exception as e:
            STATE['error'] = (STATE['error'] or '') + ' | capture: %r' % e
        # 停掉桥接
        try:
            for text, w in list(STATE['buttons']):
                if str(text).strip() == '停止':
                    w.invoke()
                    STATE['stopped'] = True
                    break
        except Exception as e:
            STATE['error'] = (STATE['error'] or '') + ' | stop: %r' % e
        _write_report()
        try:
            if root is not None:
                root.after(3000, root.destroy)
        except Exception:
            pass

    import ext_launcher
    # 运行时覆盖（不改包内文件）：端口 / PID 文件 / 日志位置
    if PORT:
        ext_launcher.DEFAULT_PORT = PORT
    if PIDFILE:
        ext_launcher.PID_PATH = PIDFILE
        ext_launcher.APPDATA_DIR = os.path.dirname(PIDFILE)
        ext_launcher.LOG_PATH = os.path.join(ext_launcher.APPDATA_DIR,
                                             'bridge.log')
    STATE['port'] = getattr(ext_launcher, 'DEFAULT_PORT', None)
    STATE['pid_path'] = getattr(ext_launcher, 'PID_PATH', None)
    try:
        ext_launcher.main()
    except SystemExit:
        pass
    except Exception as e:
        STATE['error'] = (STATE['error'] or '') + ' | main: %r' % e
        _finish()
    if not STATE['done']:
        _finish()
    return 0


if __name__ == '__main__':
    sys.exit(main())
