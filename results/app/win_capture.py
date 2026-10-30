"""🔴 Windows 窗口抓图（**不依赖屏幕合成**）—— APP-048 截图工具。

## 为什么需要这个

实测（2026-10-30）：本机 `PIL.ImageGrab.grab()`（走 GDI `BitBlt` 屏幕）
**抓到的整屏是全黑**（`extrema=(0,126)`，采样点全 `(0,0,0)`），
⇒ 之前 APP-048 的三张截图**全是黑图**（92 KB 的 PNG，内容无效），
而 60 个判据全在**逻辑层** ⇒ **静默假通过**。

`EnumWindows` 能枚举到 12 个可见窗口（含浏览器、WorkBuddy 主窗口）
⇒ **桌面会话正常**、不是没有交互桌面
⇒ 问题是**屏幕像素读不出来**（远程/虚拟桌面下 GDI `BitBlt` 屏幕常为黑）。

## 解法：`PrintWindow` + `PW_RENDERFULLCONTENT`

`PrintWindow(hwnd, hdcMem, 2)` 让窗口**自己把内容画进**我们给的内存 DC
⇒ **不需要读屏幕像素** ⇒ 不受黑屏 / 遮挡 / 屏幕尺寸限制。

- `PW_RENDERFULLCONTENT`(=2) ⇒ 连 DWM 合成的部分（半透明/无边框控件）也能拿到
  （Tk 窗口是传统 GDI 绘制，其实 flag=0 也行，但 2 更保险）。

## 已知限制

- 窗口若**最小化**，抓出来是空白 ⇒ 调用前先 `deiconify()`。
- Tk 的 `Canvas`/图片在 `PW_RENDERFULLCONTENT` 下偶尔丢 ⇒ 实测本项目
  （纯 Label/Button 布局）**不丢**。

## 用法

    from win_capture import capture_hwnd
    ok = capture_hwnd(hwnd, path)
"""

import ctypes
import ctypes.wintypes as w

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
PW_RENDERFULLCONTENT = 0x00000002

user32.SetProcessDPIAware()


def capture_hwnd(hwnd, path, flags=PW_RENDERFULLCONTENT):
    """抓 hwnd 窗口内容存 PNG。成功返回 True。"""
    import os

    rect = w.RECT()
    if not user32.GetWindowRect(wintypes_hwnd(hwnd), ctypes.byref(rect)):
        return False
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return False

    win_dc = user32.GetWindowDC(hwnd)
    if not win_dc:
        return False
    mem_dc = gdi32.CreateCompatibleDC(win_dc)
    bmp = gdi32.CreateCompatibleBitmap(win_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bmp)
    ok = False
    try:
        # 🔴 PrintWindow：让窗口自绘进 mem_dc（不读屏幕像素）
        if user32.PrintWindow(hwnd, mem_dc, flags):
            ok = _save_bmp(mem_dc, bmp, path, width, height)
        if not ok:
            # 兜底：BitBlt 窗口 DC
            gdi32.BitBlt(mem_dc, 0, 0, width, height, win_dc, 0, 0, SRCCOPY)
            ok = _save_bmp(mem_dc, bmp, path, width, height)
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, win_dc)
    return ok and os.path.exists(path) and os.path.getsize(path) > 1000


def _save_bmp(mem_dc, bmp, path, width, height):
    try:
        from PIL import Image
    except Exception:
        return False
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', w.DWORD), ('biWidth', w.LONG), ('biHeight', w.LONG),
            ('biPlanes', w.WORD), ('biBitCount', w.WORD), ('biCompression', w.DWORD),
            ('biSizeImage', w.DWORD), ('biXPelsPerMeter', w.LONG),
            ('biYPelsPerMeter', w.LONG), ('biClrUsed', w.DWORD),
            ('biClrImportant', w.DWORD),
        ]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = width
    bi.biHeight = -height          # 🔴 负数 = 自上而下
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(width * height * 4)
    got = gdi32.GetDIBits(mem_dc, bmp, 0, height, buf, ctypes.byref(bi), 0)
    if not got:
        return False
    img = Image.frombuffer('RGBA', (width, height), buf, 'raw', 'BGRA', 0, 1)
    img.convert('RGB').save(path)
    return True


def wintypes_hwnd(hwnd):
    """把 int 转成 HWND（c_void_p）。"""
    return w.HWND(hwnd)
