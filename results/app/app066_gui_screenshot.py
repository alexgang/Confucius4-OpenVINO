#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-066：GUI 冒烟**截图**（补 APP-018 第 4 条的「截图路径」）。

## 为什么单独写这个

`app063` 的 GUI 冒烟是**无头 Tk 装配**检查（只验控件、不开真窗口）
⇒ 拿不到截图 ⇒ STATUS §49.10 只能写「未截图」。
reviewer 要的是「日志**和截图**路径」⇒ 必须补一张**真实窗口**的截图。

## 做法（不加载任何模型）

1. 用**客户包 python** 起 `app/live_caption_app.py`（GUI 主程序）；
   🔴 GUI 只有在用户点「开始」后才加载 ASR/MT/TTS 模型
   ⇒ 只起窗口 + 截图 = **零推理、零 GPU/NPU 占用**（守纪律）。
2. 等窗口出现（轮询 `EnumWindows` 找标题含「Confucius」/「R2T2」的顶层窗口）。
3. 用 `PrintWindow`（GDI）**只抓该窗口**（不抓整个桌面 ⇒ 不泄露桌面其它内容）。
4. 存 PNG 到仓库外，然后**关掉**进程。

## 纪律

- 🔴 **不持机器锁**：本脚本零推理、零 GPU ⇒ 不需要锁；
  但**打包/计时期间不要跑**（起 Tk 窗口会短暂占 CPU）。
- 🔴 截图只含**本程序窗口**（`PrintWindow`，不是全屏）⇒ 不泄露用户桌面。
- 🔴 产物写**仓库外**（`C:\\Users\\Trekker-PTL\\abba_out\\`）。

用法：
    python results/app/app066_gui_screenshot.py
    python results/app/app066_gui_screenshot.py --keep-open   # 不自动关闭
"""
from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v1.5')
PY = os.path.join(PKG, 'python', 'python.exe')
APP = os.path.join(PKG, 'app', 'live_caption_app.py')
OUTDIR = os.path.join(HOME, 'abba_out')
OUTPNG = os.path.join(OUTDIR, 'app066_gui_smoke.png')

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# ⚠️ 必须显式设 argtypes/restype（否则 HANDLE 被截断成 32 位 ⇒ 静默失败）
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p), ctypes.c_void_p]
user32.EnumWindows.restype = ctypes.c_bool
user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
user32.IsWindowVisible.restype = ctypes.c_bool
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_long * 4)]
user32.GetWindowRect.restype = ctypes.c_bool
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_ulong)]
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
user32.GetWindowDC.argtypes = [ctypes.c_void_p]
user32.GetWindowDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
user32.PrintWindow.restype = ctypes.c_bool

# 🔴🔴 **GDI 也必须显式设 argtypes/restype**：
#   不设的话 HDC/HBITMAP 是 64 位指针，会被当成 32 位 int 传 ⇒
#   `ArgumentError: OverflowError: int too long to convert`（本轮实测踩过）。
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                         ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.restype = ctypes.c_bool
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.restype = ctypes.c_bool
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                            ctypes.c_uint, ctypes.c_void_p,
                            ctypes.c_void_p, ctypes.c_uint]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                         ctypes.c_int, ctypes.c_int, ctypes.c_uint]
gdi32.BitBlt.restype = ctypes.c_bool
user32.GetDC.argtypes = [ctypes.c_void_p]
user32.GetDC.restype = ctypes.c_void_p

# 🔴 窗口可能在屏幕外（实测 rect=(205,1069,1843,1191) ⇒ 高度只有 122）
#   ⇒ 先摆到可见位置再抓，否则抓到的是被裁剪/空白
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = ctypes.c_bool
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.ShowWindow.restype = ctypes.c_bool
SW_RESTORE = 9
HWND_TOP = 0
SWP_SHOWWINDOW = 0x0040


def find_app_windows(pid: int):
    """找出**属于该进程**的可见顶层窗口 ⇒ [(hwnd, title, (l,t,r,b))]。"""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _cb(hwnd, lparam):
        wpid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        rc = (ctypes.c_long * 4)()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        found.append((hwnd, buf.value, (rc[0], rc[1], rc[2], rc[3])))
        return True

    user32.EnumWindows(_cb, None)
    return found


def _is_blank(png_path: str) -> bool:
    """截图是不是空白（纯色）—— 用来判定 `PrintWindow` 是否失败。

    🔴 实测：Tk 窗口用 `PrintWindow(..., 2)` 会拿到**全白**图（917 B）
    ⇒ **必须**校验非空白，不能「文件写成功了就算成功」。
    """
    try:
        import numpy as np
        import PIL.Image as Image
        a = np.asarray(Image.open(png_path).convert('L'), dtype=np.float32)
        return float(a.std()) < 3.0
    except Exception:
        return True


def _grab_printwindow(hwnd, rect, flag: int, out: str) -> bool:
    """用 `PrintWindow` 抓单个窗口（`flag`：0=传统、2=RENDERFULLCONTENT）。"""
    from ctypes import wintypes
    l, t, r, b = rect
    w, h = max(r - l, 1), max(b - t, 1)

    hdc_win = user32.GetWindowDC(hwnd)
    if not hdc_win:
        return False
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)
    ok = bool(user32.PrintWindow(hwnd, hdc_mem, flag))
    got = 0
    if ok:
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                        ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                        ('biBitCount', wintypes.WORD),
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
        got = gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)
        if got:
            import numpy as np
            import PIL.Image as Image
            arr = np.frombuffer(buf.raw, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]
            Image.fromarray(arr[:, :, ::-1]).save(out)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)
    return bool(ok and got)


def _grab_desktop_rect(rect, out: str) -> bool:
    """兜底：从**桌面 DC** 拷该矩形（窗口已被移到左上角并置顶）。

    ⚠️ 这会带上该矩形内的**其它窗口**内容 ⇒ 所以先把窗口移到 (60,60) 并置顶，
       截图前用户桌面的该区域应是本程序窗口。
    """
    from ctypes import wintypes
    l, t, r, b = rect
    w, h = max(r - l, 1), max(b - t, 1)
    hdc_screen = user32.GetDC(None)
    if not hdc_screen:
        return False
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)
    SRCCOPY = 0x00CC0020
    ok = bool(gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, l, t, SRCCOPY))
    got = 0
    if ok:
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                        ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                        ('biBitCount', wintypes.WORD),
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
        got = gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)
        if got:
            import numpy as np
            import PIL.Image as Image
            arr = np.frombuffer(buf.raw, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]
            Image.fromarray(arr[:, :, ::-1]).save(out)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_screen)
    return bool(ok and got)


def grab_window(hwnd, rect, out: str = None) -> bool:
    """三级兜底：PrintWindow(2) → PrintWindow(0) → 桌面矩形。

    🔴 每级都要**校验非空白**（`_is_blank`）⇒ 不能「文件写了就算成功」。
    """
    out = out or OUTPNG
    for flag in (2, 0):
        if _grab_printwindow(hwnd, rect, flag, out) and not _is_blank(out):
            print('[gui] 抓取方式：PrintWindow(flag=%d)' % flag)
            return True
        print('[gui] PrintWindow(flag=%d) 空白/失败 ⇒ 换方式' % flag)
    if _grab_desktop_rect(rect, out) and not _is_blank(out):
        print('[gui] 抓取方式：桌面矩形（BitBlt）')
        return True
    return False


def _grab_window_old(hwnd, rect) -> bool:
    """（旧实现，保留仅为对照）`PrintWindow(..., 2)` 单次抓取。"""
    from ctypes import wintypes
    l, t, r, b = rect
    w, h = max(r - l, 1), max(b - t, 1)

    hdc_win = user32.GetWindowDC(hwnd)
    if not hdc_win:
        return False
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)

    ok = bool(user32.PrintWindow(hwnd, hdc_mem, 2))

    # BITMAPINFOHEADER（40 字节）
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                    ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG),
                    ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h            # 负数 ⇒ 自顶向下
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0        # BI_RGB

    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)

    if not ok or got == 0:
        return False

    import numpy as np
    arr = np.frombuffer(buf.raw, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]
    import PIL.Image as Image
    Image.fromarray(arr[:, :, ::-1]).save(OUTPNG)   # BGR → RGB
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=60.0)
    ap.add_argument('--keep-open', action='store_true')
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    if not os.path.isfile(APP):
        print('!! 找不到 %s' % APP)
        return 1

    print('[gui] 启动 %s' % APP)
    # 🔴 不传 --start / 不点「开始」⇒ 不加载任何模型
    env = dict(os.environ)
    env['LIVECAP_PKG'] = PKG
    proc = subprocess.Popen([PY, APP], cwd=PKG, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    t0 = time.time()
    win = None
    try:
        while time.time() - t0 < args.timeout:
            if proc.poll() is not None:
                print('!! GUI 进程已退出（rc=%s）' % proc.returncode)
                out = proc.stdout.read().decode('utf-8', 'replace')
                print(out[-2000:])
                return 2
            wins = find_app_windows(proc.pid)
            if wins:
                # 🔴🔴 **不能取第一个**：实测同一进程有 3 个可见窗口
                #   · 1638x122 底部**字幕条**
                #   · 44x24   一个小部件
                #   · 1096x859 **主窗口**（(156,156)）
                #   ⇒ 按**面积最大**选主窗口；其余留作字幕条截图。
                wins.sort(key=lambda w: (w[2][2] - w[2][0]) * (w[2][3] - w[2][1]),
                          reverse=True)
                win = wins[0]
                break
            time.sleep(1.0)
        if not win:
            print('!! %.0f s 内没等到窗口' % args.timeout)
            return 3

        hwnd, title, rect = win
        print('[gui] 窗口：hwnd=%s title=%r rect=%s' % (hwnd, title, rect))
        # 🔴 先确保窗口在可见位置且已恢复（实测可能被摆到屏幕外/最小化）
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetWindowPos(hwnd, HWND_TOP, 60, 60, 0, 0,
                            SWP_SHOWWINDOW | 0x0001)   # NOSIZE
        time.sleep(1.5)
        rc = (ctypes.c_long * 4)()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        rect = (rc[0], rc[1], rc[2], rc[3])
        print('[gui] 摆正后 rect=%s（%dx%d）'
              % (rect, rect[2] - rect[0], rect[3] - rect[1]))
        # 🔴 等窗口**定型**：实测刚起时只有 122 px 高（还没排完版）
        t1 = time.time()
        while time.time() - t1 < 25:
            rc = (ctypes.c_long * 4)()
            user32.GetWindowRect(hwnd, ctypes.byref(rc))
            if (rc[3] - rc[1]) >= 400:
                break
            time.sleep(0.5)
        rect = (rc[0], rc[1], rc[2], rc[3])
        print('[gui] 定型后 rect=%s（%dx%d）'
              % (rect, rect[2] - rect[0], rect[3] - rect[1]))
        time.sleep(2.0)                    # 让 Tk 画完
        if not grab_window(hwnd, rect, OUTPNG):
            print('!! 截图失败（PrintWindow 返回 False）')
            return 4
        print('[gui] ✅ 主窗口截图：%s（%d B）'
              % (OUTPNG, os.path.getsize(OUTPNG)))
        # ── 顺带抓**底部字幕条**（同一进程的另一个窗口，很宽很扁）──
        for w2 in wins[1:]:
            r2 = w2[2]
            wpx, hpx = r2[2] - r2[0], r2[3] - r2[1]
            if wpx >= 800 and hpx <= 200:
                out2 = os.path.join(OUTDIR, 'app066_gui_captionbar.png')
                user32.ShowWindow(w2[0], SW_RESTORE)
                user32.SetWindowPos(w2[0], HWND_TOP, 60, 300, 0, 0,
                                    SWP_SHOWWINDOW | 0x0001)
                time.sleep(1.0)
                rc2 = (ctypes.c_long * 4)()
                user32.GetWindowRect(w2[0], ctypes.byref(rc2))
                if grab_window(w2[0], (rc2[0], rc2[1], rc2[2], rc2[3]), out2):
                    print('[gui] ✅ 字幕条截图：%s（%d B）'
                          % (out2, os.path.getsize(out2)))
                break
        return 0
    finally:
        if not args.keep_open:
            try:
                proc.terminate()
                proc.wait(timeout=15)
                print('[gui] 已关闭 GUI 进程')
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


if __name__ == '__main__':
    sys.exit(main())
