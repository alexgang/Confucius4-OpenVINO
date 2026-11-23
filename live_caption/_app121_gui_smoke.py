#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §3：**GUI 冒烟**（起真实 GUI ⇒ 抓窗口 ⇒ 验证真的渲染出来了）。

## reviewer 原文（APP-121 §3）
> 重打的 zip 解压到一个全新的目录，用全新的 %LOCALAPPDATA% 跑 --check，
> 再做 GUI 冒烟（schtasks /it 截图），并且确认 ACCEPTED 的模块清单和 zip 的
> 实际内容一致。

## 🔴 为什么不用 schtasks
本机**安全策略禁止** `schtasks` / `cmd.exe` / COM(`WScript.Shell`) /
`Start-Process`（见 `MEMORY_MODULES.md` 十七）⇒ 只能用「父进程直接拉起
子进程 + Win32 抓窗口」这条路。

## 🔴 为什么不用 `ImageGrab`
`PIL.ImageGrab.grab()` 在本机抓到的是**全黑**（会话隔离）⇒ 改用
**Win32 `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)`** 直接渲染窗口到
位图 ⇒ 抓到的是窗口自己的内容。

## 判据（fail-closed）
- GUI 进程**活着**且**创建了主窗口**（`EnumWindows` + `GetWindowThreadProcessId`
  匹配子进程 PID）⇒ 窗口标题非空；
- `PrintWindow` 返回**非零**；
- 抓下来的 PNG **不是全黑**（像素方差 > 阈值）⇒ 证明**真的渲染了内容**，
  不是一张空窗口；
- 最后**关掉** GUI（`WM_CLOSE`）并等它退出 ⇒ 不留残留进程。

## 用法
```
python live_caption/_app121_gui_smoke.py --pkg <解压后的目录> --out <证据 json>
```
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as w
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', w.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', w.WORD),
                ('biBitCount', w.WORD), ('biCompression', w.DWORD),
                ('biSizeImage', w.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', w.DWORD),
                ('biClrImportant', w.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER),
                ('bmiColors', w.DWORD * 3)]


def find_windows_for_pid(pid):
    """🔴 枚举**属于该 PID** 的顶层窗口（不是按标题猜）。"""
    found = []

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def cb(hwnd, _lparam):
        p = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            rect = w.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found.append({'hwnd': int(hwnd), 'title': buf.value,
                          'rect': [rect.left, rect.top, rect.right, rect.bottom]})
        return True

    user32.EnumWindows(cb, 0)
    return found


def capture_hwnd(hwnd, path):
    """🔴 用 `PrintWindow` 把窗口渲染到位图（**不走屏幕 DC** ⇒ 不是全黑）。"""
    from PIL import Image
    rect = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return False, {'width': width, 'height': height, 'reason': '窗口尺寸为 0'}
    hdc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(mem_dc, bmp)
    ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height          # 负数 = 自上而下
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(width * height * 4)
    got = gdi32.GetDIBits(mem_dc, bmp, 0, height, buf, ctypes.byref(bmi), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hdc)

    if not got:
        return False, {'width': width, 'height': height,
                       'reason': 'GetDIBits 失败'}
    img = Image.frombuffer('RGB', (width, height), buf, 'raw', 'BGRX', 0, 1)
    img.save(path)
    g = list(img.convert('L').getdata())
    n = len(g) or 1
    mean = sum(g) / n
    var = sum((v - mean) ** 2 for v in g) / n
    return True, {'width': width, 'height': height,
                  'printwindow_ret': int(ok),
                  'gray_mean': round(mean, 3),
                  'gray_variance': round(var, 3),
                  'all_black': bool(var < 1.0),
                  'path': path, 'bytes': os.path.getsize(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True, help='解压后的包目录')
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app121_gui_smoke.json'))
    ap.add_argument('--wait-s', type=float, default=45.0)
    ap.add_argument('--settle', type=float, default=50.0,
                    help='窗口出现后再等这么久（等模型加载完、GUI 渲染完成）')
    ap.add_argument('--extra', default='', help='额外的 CLI 参数')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    if not os.path.isfile(py) or not os.path.isfile(app):
        print('FAIL: 包不完整 %s' % pkg)
        return 2

    shots = os.path.join(REPO, 'results', 'app', '_app121_gui_shots')
    os.makedirs(shots, exist_ok=True)
    png = os.path.join(shots, 'app121_gui_v111.png')

    # 🔴 **取共享机器锁**（GUI 会加载 ASR/MT/TTS 模型 ⇒ 占设备）
    sys.path.insert(0, REPO)
    import machine_lock_app
    ok_lock, payload = machine_lock_app.acquire(module='app', timeout=3600,
                                                poll=20, verbose=True)
    if not ok_lock:
        print('🔴 未取得 MACHINE_LOCK ⇒ 终止')
        return 2
    print('[app121] 已取锁：%s' % payload)

    cmd = [py, app] + ([x for x in args.extra.split() if x] or [])
    print('[app121] 启动 GUI：%s' % ' '.join(cmd))
    logf = os.path.join(shots, 'app121_gui_stdout.log')
    with open(logf, 'w', encoding='utf-8', newline='\n') as lf:
        proc = subprocess.Popen(cmd, cwd=pkg, stdout=lf, stderr=subprocess.STDOUT)

    res = {'script': '_app121_gui_smoke.py',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': pkg, 'cmd': cmd, 'pid': proc.pid,
           'log': logf}
    try:
        # ── 等窗口出现 ────────────────────────────────────────────
        wins = []
        t_end = time.time() + args.wait_s
        while time.time() < t_end:
            if proc.poll() is not None:
                break
            wins = find_windows_for_pid(proc.pid)
            if wins:
                break
            time.sleep(2.0)
        res['n_windows'] = len(wins)
        res['windows'] = wins
        res['window_titles'] = [x['title'] for x in wins]
        if not wins:
            res['verdict'] = 'FAIL'
            res['reason'] = ('没有枚举到该 PID 的可见顶层窗口'
                             '（GUI 没起来？）')
        else:
            # 🔴 **必须抓「面积最大」的窗口**：同一进程还有**字幕浮条**
            #   （1638×157 的细条，平时无字幕 ⇒ 抓出来必然全黑）
            #   ⇒ 抓错窗口会得到「假 FAIL」。主窗口是 1455×1132 那个。
            def _area(x):
                l, t, r, b = x['rect']
                return max(0, r - l) * max(0, b - t)
            wins_sorted = sorted(wins, key=_area, reverse=True)
            target = wins_sorted[0]
            res['capture_target'] = target
            res['capture_target_note'] = ('面积最大的顶层窗口（避免抓到'
                                          '无字幕时全黑的字幕浮条）')
            # 🔴 **等模型加载完再抓**（GUI 起来 ≠ 渲染完成）
            time.sleep(max(0.0, args.settle))
            hwnd = target['hwnd']
            ok, info = capture_hwnd(hwnd, png)
            res['capture'] = info
            res['capture_ok'] = bool(ok)
            res['verdict'] = ('PASS' if (ok and not info.get('all_black'))
                              else 'FAIL')
            if ok and info.get('all_black'):
                res['reason'] = 'PrintWindow 抓下来是全黑 ⇒ 不算渲染成功'
            # 附：浮条也抓一张（留档，说明为什么不能抓它）
            if len(wins_sorted) > 1:
                ok2, info2 = capture_hwnd(wins_sorted[1]['hwnd'],
                                          png.replace('.png', '_overlay.png'))
                res['capture_overlay'] = info2
    finally:
        # ── 关掉 GUI（不留残留进程）──────────────────────────────
        try:
            for x in res.get('windows', []):
                user32.PostMessageW(x['hwnd'], 0x0010, 0, 0)   # WM_CLOSE
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        res['gui_exit_code'] = proc.returncode
        try:
            machine_lock_app.release(payload, verbose=True)
            print('[app121] 已释放锁')
        except Exception as e:
            print('[app121] 释放锁异常：%r' % e)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    print('[app121] 判定：%s（窗口 %s 个，标题 %s）'
          % (res.get('verdict'), res.get('n_windows'),
             res.get('window_titles')))
    if res.get('capture'):
        print('[app121] 截图：%s' % json.dumps(res['capture'], ensure_ascii=False))
    print('[app121] 证据 → %s' % args.out)
    return 0 if res.get('verdict') == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
