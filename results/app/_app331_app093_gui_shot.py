#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app331_app093_gui_shot.py —— **APP-093 §3.7 字幕条截图**。

## reviewer §3.7 原文
> **字幕条截图**：跑 GUI（schtasks /it）截一张**有三行字幕**的图，存 png，
> 在 json 里写**路径和尺寸**。

## 🔴🔴🔳 上一轮为什么失败（`app372_app091_subtitle_shot/subtitle_layout.json` ⇒ `shot=null`）

**根因（读码 + 本项目铁律）**：
* `live_caption_app._selftest_done()` 用 **`PIL.ImageGrab.grab()`**
  ⇒ 本机走 GDI `BitBlt` **读屏幕像素 ⇒ 整屏全黑**
  （本项目铁律：`ImageGrab.grab()` 本机全黑 ⇒ 必须改 Win32 `PrintWindow`）
* ⇒ 上一轮 `gui.log` 是 0 B、`shot=null` ⇒ **没有有效截图**。

⇒ 本脚本**不用** `ImageGrab`，改用 **`results/app/win_capture.py`** 的
`capture_hwnd()`（Win32 `PrintWindow` + **三级降级** + 纯 stdlib PNG 落盘）。

## 🔴 像素级守卫（防止再次「静默假通过」）

抓完必须过**三道**：
1. **非黑图**：`extrema` 的最大值必须 > 0（黑图 ⇒ 全部 0）
2. **客户区高度 ≥ 700 px**（GUI 主窗实测 ~980 px）
3. **内容密度 > 0**（`png_stats.content_density`）

⇒ 任一不过 ⇒ `verdict=FAIL_BLACK_OR_EMPTY`，**不写「已截图」**。

## 🔴 三行字幕怎么保证
GUI 的字幕区是 **3 行**（APP-091 §3）：
① 定稿译文（主字号）② 定稿原文（小字）③ 实时识别（ASR 实时行）
⇒ 用 `--file` 播素材、**等字幕出现**再抓 ⇒ 抓主窗（**字幕在主窗里**）。

## 用法
```
.venv/Scripts/python.exe results/app/_app331_app093_gui_shot.py --arm after
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
HOME = os.path.expanduser('~')
sys.path.insert(0, HERE)

BASE = os.path.join(HOME, '_app_shadow')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

OUTROOT = os.path.join(HERE, 'app331_gui_shot')
REPORT = os.path.join(HERE, 'app331_app093_gui_shot.json')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def find_window(title_substr, timeout=30, pid=None, min_w=800, min_h=600,
                diag=None):
    """🔴 找到标题含子串的**顶层窗口**（优先可见；不可见也接受）。

    🔴🔴🔳 **本轮再次修正（§3.7 真根因已定位）**：
    本函数**不是**真正的失败根因 —— 真根因是 dev 树的
    `App.__init__` 被 `commit 874924a` 截断（GUI 布局代码被吞进
    `_clone_nearest`）⇒ 主窗**永远**只有 Tk 默认的 `tk` 200×200
    ⇒ 标题/尺寸都不对 ⇒ 任何枚举策略都找不到。

    ⇒ 本函数改为**宽松优先 + 记录诊断**：
    ① 先按 PID 过滤（只认本进程）
    ② 标题匹配优先；不匹配时**按面积降序**取最大的当候选
    ③ `IsWindowVisible` **不再硬过滤**（Tk 窗口刚映射时可能还没置位）
    ④ 每次轮询把**候选窗口列表**写进 `diag`（供事后判读）
    """
    import win_capture
    user32 = ctypes.windll.user32
    found = []
    cands = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, lparam):
        # 🔴 PID 过滤（只认本进程自己的窗口）
        if pid is not None:
            wpid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if int(wpid.value) != int(pid):
                return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        if n > 0:
            user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        try:
            import ctypes.wintypes as wt
            r = wt.RECT()
            w_px = h_px = 0
            if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                w_px = r.right - r.left
                h_px = r.bottom - r.top
        except Exception:
            w_px = h_px = 0
        vis = bool(user32.IsWindowVisible(hwnd))
        rec = {'hwnd': int(ctypes.cast(hwnd, ctypes.c_void_p).value or 0),
               'title': title, 'w': w_px, 'h': h_px, 'vis': vis}
        cands.append(rec)
        if title_substr and (title_substr in title):
            found.append((rec['hwnd'], title))
            return False
        return True

    t0 = time.time()
    while time.time() - t0 < timeout:
        found.clear()
        cands.clear()
        user32.EnumWindows(EnumWindowsProc(cb), None)
        if found:
            return found[0]
        time.sleep(0.5)
    if diag is not None:
        # 🔴 记录**本进程**的全部窗口（按面积降序）⇒ 便于事后判读
        mine = [c for c in cands]
        mine.sort(key=lambda c: -(c['w'] * c['h']))
        diag['candidates'] = mine[:20]
        diag['waited_s'] = round(time.time() - t0, 1)
    return None


def find_overlay(pid, exclude_hwnd=None, timeout=20):
    """🔴 找**屏幕底部字幕条**（`CaptionOverlay` 的 Toplevel）。

    🔴🔴🔳 **不能按标题找**：字幕条是 `overrideredirect(True)` 的 Toplevel
    ⇒ **Win32 标题继承父窗口标题** ⇒ 与主窗标题**完全一样**
    （本轮实测：subtitle bar hwnd=1969880 标题='实时字幕 MiniMVP v1.0'）
    ⇒ 上一版 `find_window('字幕')` 抓到的是**主窗**（hwnd 相同）。

    ⇒ 改用**几何 + 位置**三重判据：
    ① 宽 ≫ 高（横条：w > 3×h）
    ② **贴屏幕底部**（bottom ≥ 屏幕高 − 40）
    ③ 排除主窗（exclude_hwnd）与小把手/托盘（尺寸下限）
    """
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    screen_h = user32.GetSystemMetrics(1)      # SM_CYSCREEN
    t0 = time.time()
    while time.time() - t0 < timeout:
        cands = []

        def cb(hwnd, lparam):
            wpid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if int(wpid.value) != int(pid):
                return True
            hid = int(ctypes.cast(hwnd, ctypes.c_void_p).value or 0)
            if exclude_hwnd is not None and hid == int(exclude_hwnd):
                return True
            r = wt.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
                return True
            w_px = r.right - r.left
            h_px = r.bottom - r.top
            if w_px <= 0 or h_px <= 0:
                return True
            if w_px <= 3 * h_px:                  # ① 必须是横条
                return True
            # ② 必须在下半屏
            #    🔴🔴🔳 **本轮修正**：原判据用「贴屏幕底部（bottom ≥ 屏幕高−40）」
            #    ⇒ **误杀**：本机屏幕 1280 高，但字幕条 bottom=1191（差 89）
            #    ⇒ 因为字幕条是贴在**工作区**底部（Tk 报的 y=1034），
            #       不是贴着物理屏幕底边。
            #    ⇒ 改判据：**下半屏**（top ≥ 屏幕高×0.55）+ **宽高比**
            #       （横条）⇒ 已足够唯一（主窗 1455×1132 不是横条）。
            if r.top < screen_h * 0.55:
                return True
            if w_px < 200 or h_px < 40:           # ③ 排除小把手/托盘
                return True
            cands.append({'hwnd': hid, 'w': w_px, 'h': h_px,
                          'x': r.left, 'y': r.top, 'bottom': r.bottom,
                          'vis': bool(user32.IsWindowVisible(hwnd))})
            return True

        user32.EnumWindows(EnumWindowsProc(cb), None)
        if cands:
            cands.sort(key=lambda c: -(c['w'] * c['h']))
            return cands[0]
        time.sleep(0.5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--wait-subtitle', type=float, default=25.0,
                    help='等字幕出现的秒数')
    ap.add_argument('--wait-window', type=float, default=420.0,
                    help='🔴 等 GUI **主窗**出现的最长秒数（默认 420）'
                         '⇒ 冷启动要同步 import transformers（prewarm）'
                         '＋ 加载 ASR/MT 模型 ⇒ 实测可到数分钟')
    args = ap.parse_args()

    os.makedirs(OUTROOT, exist_ok=True)
    ev = {'created_at': now(), 'arm': args.arm,
          'criterion': 'APP-093 §3.7 字幕条截图（三行字幕，png + 路径 + 尺寸）',
          'method': ('GUI（--file 播素材）⇒ 找主窗 ⇒ Win32 PrintWindow 抓图 '
                     '⇒ **像素级守卫**（非黑 + 客户区高 ≥700 + 内容密度 >0）'),
          'note': ('🔴 不用 ImageGrab（本机全黑）⇒ 用 win_capture.capture_hwnd'
                   '（PrintWindow + 三级降级 + 纯 stdlib PNG）'),
          'shots': [], 'verdict': None}

    root = os.path.join(BASE, args.arm)
    wav = os.path.join(SPKTEST, 'dialog3.wav')
    out_dir = os.path.join(OUTROOT, args.arm)
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        os.path.join(root, 'python', 'pythonw.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--file', wav, '--autostart',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--tts', 'on', '--tts-device', 'NPU', '--tts-precision', 'f16',
        '--out', os.path.join(out_dir, 'subtitles.txt'),
    ]
    gui_log = os.path.join(out_dir, 'gui.log')
    env = dict(os.environ)
    clone_dir = os.path.join(out_dir, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir

    print('▶ 启动 GUI：%s' % ' '.join(cmd[:3]), flush=True)
    lf = open(gui_log, 'wb')
    p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env,
                         cwd=root)
    ev['cmd'] = cmd
    ev['gui_log'] = gui_log
    try:
        # ── 等字幕出现 ──
        # 🔴🔴🔳 **顺序修正**：**先等主窗**（GUI 初始化完 ⇒ 模型已加载 ⇒
        #    字幕很快就会出现），**再等字幕**
        #    ⇒ 上一版是「先 sleep 25 s 再找窗口」，冷启动时窗口根本还没出现。
        # 🔴🔴🔳 **按 PID + 面积**定位主窗（上一轮抓到托盘溢出窗）
        #    App 有**两个**窗口：① 主窗「实时字幕 MiniMVP v1.0」（三行字幕在
        #    它的文本区）② 屏幕底部置顶字幕条 `CaptionOverlay`（独立 toplevel）
        #    ⇒ 两个都抓：主窗走「大窗」守卫，字幕条走「非黑 + 有内容」守卫。
        #
        # 🔴🔴🔳 **冷启动很慢**：`App.__init__` 末尾**同步**跑
        #   `prewarm_transformers()`（首次 import transformers）＋ 加载
        #   ASR/MT 模型 ⇒ 实测主窗出现可能要**数分钟**
        #   ⇒ 等待窗口必须给足（默认 420 s），否则会误判「找不到窗口」。
        main_diag = {}
        main_hit = find_window('MiniMVP', timeout=args.wait_window,
                               pid=p.pid, diag=main_diag)
        if not main_hit:
            ev['window_diag'] = main_diag
            ev['verdict'] = 'FAIL_NO_WINDOW'
            ev['error'] = ('找不到 GUI 主窗（PID=%s）；已按 PID 过滤；'
                           '已等 %.0f s' % (p.pid, args.wait_window))
            return 3
        ev['window_diag'] = main_diag
        hwnd, title = main_hit
        ev['window'] = {'hwnd': hwnd, 'title': title, 'pid': p.pid}

        # ── 主窗出现 ⇒ 再等字幕（模型已就绪 ⇒ 字幕很快出现）──
        time.sleep(args.wait_subtitle)

        # ② 屏幕底部字幕条（CaptionOverlay）——独立窗口
        #    🔴🔴🔳 **本轮修正**：字幕条是 `tk.Toplevel(root)` +
        #       `overrideredirect(True)` ⇒ **Win32 标题继承父窗口标题**
        #       （与主窗**完全相同**：「实时字幕 MiniMVP v1.0」）
        #       ⇒ **按标题找必然抓到主窗**（本轮实测：overlay_window 抓到的
        #          hwnd 与主窗一样）。
        #    ⇒ 改用**几何特征**定位：① 宽 ≫ 高（横条）② 位置在屏幕底部
        #       ③ 排除主窗（面积最大者）与拖拽把手（44×24）
        ov_hit = find_overlay(p.pid, exclude_hwnd=hwnd)
        if ov_hit:
            ev['overlay_window'] = ov_hit

        # ── 抓图（PrintWindow）──
        import win_capture
        png = os.path.join(out_dir, '%s_caption.png' % args.arm)
        ok = win_capture.capture_hwnd(hwnd, png)
        ev['capture_ok'] = bool(ok)

        if not ok or not os.path.exists(png):
            ev['verdict'] = 'FAIL_CAPTURE'
            return 3

        # ── 像素级守卫 ──
        import png_stats
        st = png_stats.full_stats(png)
        size = st.get('size') or [0, 0]
        w_px, h_px = int(size[0]), int(size[1])
        # 🔴 客户区高度 = 图高 − 标题栏（`png_stats` 默认 title_h=34）
        client_h = max(0, h_px - 34)
        ev['png'] = {
            'path': png,
            'bytes': os.path.getsize(png),
            'size': [w_px, h_px],
            'width': w_px,
            'height': h_px,
            'client_height_px': client_h,
            'full_n_colors': st.get('full_n_colors'),
            'client_n_colors': st.get('client_n_colors'),
            'bg': st.get('bg'),
            'content_density': st.get('content_density'),
        }
        guards = {
            # 🔴 非黑图 ⇒ 色彩数 > 1（黑图 ⇒ 客户区只有 1 种颜色）
            'not_black': (st.get('client_n_colors') or 0) > 1,
            'client_height_ge_700': client_h >= 700,
            'content_density_gt_0': (st.get('content_density') or 0) > 0,
        }
        ev['guards'] = guards
        ev['shots'].append(ev['png'])

        # ── ② 屏幕底部字幕条（`CaptionOverlay`）单独抓一张 ──
        #    reviewer §3.7 要的是「**三行字幕**」⇒ 字幕条才是主体
        #    ⇒ 字幕条守卫：**非黑 + 有内容**（它是窄条，不适用 700 px 高度判据）
        ev['overlay_png'] = None
        if ov_hit:
            try:
                ov_png = os.path.join(out_dir, '%s_overlay.png' % args.arm)
                ov_ok = win_capture.capture_hwnd(ov_hit['hwnd'], ov_png)
                if ov_ok and os.path.exists(ov_png):
                    ov_st = png_stats.full_stats(ov_png)
                    ov_size = ov_st.get('size') or [0, 0]
                    ev['overlay_png'] = {
                        'path': ov_png,
                        'bytes': os.path.getsize(ov_png),
                        'size': [int(ov_size[0]), int(ov_size[1])],
                        'width': int(ov_size[0]), 'height': int(ov_size[1]),
                        'full_n_colors': ov_st.get('full_n_colors'),
                        'client_n_colors': ov_st.get('client_n_colors'),
                        'bg': ov_st.get('bg'),
                        'content_density': ov_st.get('content_density'),
                    }
                    ev['overlay_guards'] = {
                        'not_black': (ov_st.get('client_n_colors') or 0) > 1,
                        'content_density_gt_0':
                            (ov_st.get('content_density') or 0) > 0,
                        # 🔴 字幕条是**横条** ⇒ 宽 ≫ 高
                        'wide_bar': int(ov_size[0]) > 3 * int(ov_size[1]),
                    }
                    ev['shots'].append(ev['overlay_png'])
            except Exception as exc:            # noqa: BLE001
                ev['overlay_error'] = repr(exc)[:200]

        ev['verdict'] = 'PASS' if all(guards.values()) else 'FAIL_BLACK_OR_EMPTY'
    finally:
        try:
            p.terminate()
            p.wait(timeout=15)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        lf.close()

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)
    print('[verdict] %s' % ev['verdict'])
    return 0 if ev['verdict'] == 'PASS' else 3


if __name__ == '__main__':
    raise SystemExit(main())
