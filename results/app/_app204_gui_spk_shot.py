#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app204_gui_spk_shot.py —— 【APP-053 ③】GUI 侧「字幕里出现不同说话人标签」取图。

## 做什么

在**影子包**（`shared/app053054_shadow`）上起 GUI：
- `--source file --file <SPE 5 分钟切片>`（音频文件回放，不用麦克风）；
- `--speaker on`（**APP-054 新增的 GUI 开关** ⇒ 旁路开）；
- `--engine gpu_int8 --asr-device GPU.0`（**不跑 CPU 推理**）。

🔴 **自动开始会话**：`App(root, args)` 之后用 `root.after(...)` 调**真实的**
   `app.start()` ⇒ 不改产品代码、不模拟点击 ⇒ 测的是真链路。

🔴 **不改用户正在测试的安装目录**（APP-054 ⑤）⇒ 只跑影子包。

## 输出

`shared/app_gui_spk/app204_gui_spk.png`（截图）＋
`results/app/app204_app053_gui_shot_evidence.json`（证据）

## 用法

    python results/app/_app204_gui_spk_shot.py [--wait-s 70]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def find_repo_root(start: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent


GUI_RUNNER = r'''
# -*- coding: utf-8 -*-
"""影子包 GUI 自动启动器（**测试用**，不改产品代码）。

🔴 用**真实**的 `main()`（自己解析 argv）＋ 只包一层 `App`：
   构造完就 `root.after(..., app.start)` ⇒ **调真实的 start()**
   ⇒ 不模拟点击、不改产品代码 ⇒ 测的是真链路。
"""
import os
import sys
import time

app_dir = sys.argv[1]
wav = sys.argv[2]
sys.path.insert(0, app_dir)

import live_caption_app as L   # noqa: E402

_RealApp = L.App


class _AutoStartApp(_RealApp):
    """构造完立刻安排一次 `start()`（**真实**方法）。"""

    def __init__(self, root, args):
        super().__init__(root, args)
        root.after(4000, self.start)


L.App = _AutoStartApp

# 🔴 走**真实** main()（argparse 自己解析 argv）
sys.argv = ['live_caption_app.py',
            '--source', 'file', '--file', wav,
            '--speaker', 'on', '--engine', 'gpu_int8',
            '--asr-device', 'GPU.0', '--max-seconds', '300']
L.main()
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wait-s', type=float, default=70.0)
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    shadow = os.path.join(os.path.expanduser('~'), 'shared',
                          'app053054_shadow')
    wav = os.path.join(os.path.expanduser('~'), 'shared',
                       'SPE_0000_0500.wav')
    outdir = os.path.join(os.path.expanduser('~'), 'shared', 'app_gui_spk')
    os.makedirs(outdir, exist_ok=True)
    shot = os.path.join(outdir, 'app204_gui_spk.png')

    pkg_python = os.path.join(
        os.path.expanduser('~'), 'Confucius4_LiveCaption_v1.13',
        'python', 'pythonw.exe')
    runner_py = os.path.join(outdir, '_gui_runner.py')
    with open(runner_py, 'w', encoding='utf-8') as f:
        f.write(GUI_RUNNER)

    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['LIVECAP_PKG'] = shadow

    print('[gui] 启动影子包 GUI（speaker=on, source=file）…')
    proc = subprocess.Popen([pkg_python, runner_py,
                             os.path.join(shadow, 'app'), wav],
                            env=env, cwd=os.path.join(shadow, 'app'))
    try:
        time.sleep(args.wait_s)
        # ── 截图（用仓库既有的 win_capture / png_stats）──
        sys.path.insert(0, os.path.join(repo, 'results', 'app'))
        from win_capture import capture_hwnd    # noqa: E402
        from png_stats import content_density   # noqa: E402
        import ctypes
        import ctypes.wintypes as wt

        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def _enum(hwnd, _):
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
            t = buf.value
            if '实时字幕' in t and ctypes.windll.user32.IsWindowVisible(hwnd):
                pid = wt.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd,
                                                              ctypes.byref(pid))
                found.append((hwnd, t, int(pid.value)))
            return True

        ctypes.windll.user32.EnumWindows(_enum, 0)
        info = {'windows': [{'hwnd': int(h), 'title': t, 'pid': p}
                            for h, t, p in found],
                'launched_pid': proc.pid, 'shot': shot,
                'wait_s': args.wait_s}
        # 🔴 **必须取「本轮启动的那个进程」的窗口** ⇒ 机器上可能有**上一次
        #    测试残留的同名窗口** ⇒ 取 `found[0]` 会拍到**旧窗口**（本轮实测：
        #    拍到的是上一轮残留，字幕区是旧文本）⇒ 拍到「不是本轮的证据」。
        mine = [x for x in found if x[2] == proc.pid]
        info['window_of_this_run'] = bool(mine)
        if mine:
            # 🔴 同一进程有多个顶层窗口（主 GUI ＋ 屏幕字幕浮窗）⇒
            #    取**面积最大**的那个（= 主 GUI）⇒ 浮窗只有一行文字。
            sizes = []
            for h, _t, _p in mine:
                r = wt.RECT()
                ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
                sizes.append((int(r.right - r.left) * int(r.bottom - r.top),
                               int(h)))
            sizes.sort(reverse=True)
            info['window_sizes'] = [s for s, _ in sizes]
            hwnd = sizes[0][1]
            ok = capture_hwnd(hwnd, shot)
            info['capture_ok'] = bool(ok)
            info['captured_hwnd'] = int(hwnd)
            if ok:
                info['density'] = content_density(shot)

        # 🔴🔴 **更强的证据**：GUI 自己会把字幕转写文本落盘
        #   （`App` 里的 `{engine}_gui.txt`）⇒ 直接查里面的 `[S\d+]` 标签
        #   ⇒ 比「截图里有没有星号」更可复核。
        gui_txt = None
        for root_dir, _dirs, files in os.walk(
                os.path.join(os.path.expanduser('~'), 'AppData', 'Local',
                             'Confucius4LiveCaption')):
            for fn in files:
                if fn.endswith('_gui.txt'):
                    p = os.path.join(root_dir, fn)
                    gui_txt = max((gui_txt, p), key=lambda x: os.path.getmtime(x)
                                  ) if gui_txt else p
        if gui_txt and os.path.isfile(gui_txt):
            with open(gui_txt, 'r', encoding='utf-8', errors='replace') as f:
                body = f.read()
            import re as _re
            labels = _re.findall(r'\[(S\d+)\]', body)
            info['gui_transcript'] = gui_txt
            info['gui_transcript_bytes'] = os.path.getsize(gui_txt)
            info['gui_transcript_mtime'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(gui_txt)))
            info['gui_n_lines'] = len([x for x in body.splitlines() if x.strip()])
            info['gui_n_spk_labels'] = len(labels)
            info['gui_distinct_spk'] = sorted(set(labels))
            info['gui_label_sample'] = [
                x.strip()[:100] for x in body.splitlines()
                if _re.search(r'\[S\d+\]', x)][:8]
        out = os.path.join(HERE, 'app204_app053_gui_shot_evidence.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
        print('[gui] %s' % json.dumps(info, ensure_ascii=False))
        print('[gui] 证据 = %s' % out)
        return 0 if info.get('capture_ok') else 1
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(1.0)
        try:
            os.remove(runner_py)
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(main())
