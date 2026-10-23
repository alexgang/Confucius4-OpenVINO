"""diag_overlay_shot.py —— 屏幕字幕窗口截图（两栏 + 拖拽把手）。

给 APP-007 第 3、4 项留证据：字幕窗口只有**两行**
（定稿译文青 #5fd7d7 / 实时识别黄 #ffd75e）+ 左上角独立拖拽把手。

跑法（需要显示器）：
    .venv\\Scripts\\python.exe live_caption\\diag_overlay_shot.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diag_layout_gui import _capture  # 复用纯 ctypes 抓屏


def main():
    import tkinter as tk
    from live_caption_app import CaptionOverlay

    root = tk.Tk()
    root.geometry('900x700+40+40')
    root.update_idletasks()

    ov = CaptionOverlay(root, 26, click_through=True)
    # 放到屏幕**左上角**：那里通常是空白桌面，避免被别的置顶窗口
    # （托盘/任务栏/其他应用）盖住 ⇒ 截图才看得到拖拽把手。
    ov.move_to(60, 80)
    ov.show('这是定稿译文（青色行）：会议讨论本季度的增长目标与交付节奏。',
            '这是实时识别（黄色行）：the team will review the roadmap next week')
    root.update_idletasks()
    root.update()
    time.sleep(0.5)
    root.update()

    shot = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'results', 'app', 'overlay_two_rows.png'))
    os.makedirs(os.path.dirname(shot), exist_ok=True)

    # 抓**整个屏幕**再裁出字幕窗区域（字幕窗是独立置顶 Toplevel，
    # 不在 root 的 DC 里，只能走屏幕 DC）。
    # ⚠️ 字幕窗有 WS_EX_LAYERED ⇒ PrintWindow 对它无效 ⇒ 必须抓屏幕。
    #    拖拽把手在字幕窗左上角**上方偏外** ⇒ 裁剪范围要往上一扩。
    ov.win.update_idletasks()
    ov.win.update()
    x = ov.win.winfo_rootx() - 60
    y = ov.win.winfo_rooty() - 60
    w = ov.win.winfo_width() + 80
    h = ov.win.winfo_height() + 80
    ok = _capture_screen(shot, clip=(x, y, w, h))
    print(f'  截图：{shot}  ok={ok}  clip=({x},{y},{w},{h})')

    ov.destroy()
    root.destroy()
    return 0 if ok else 1


def _capture_screen(path, clip=None):
    """抓屏幕（GetDC(NULL) + BitBlt），可选裁剪区域 clip=(x,y,w,h)。"""
    import ctypes

    u32 = ctypes.windll.user32
    g32 = ctypes.windll.gdi32
    sw = u32.GetSystemMetrics(0)
    sh = u32.GetSystemMetrics(1)
    hdc = u32.GetDC(0)
    hdc_mem = g32.CreateCompatibleDC(hdc)
    hbm = g32.CreateCompatibleBitmap(hdc, sw, sh)
    old = g32.SelectObject(hdc_mem, hbm)
    g32.BitBlt(hdc_mem, 0, 0, sw, sh, hdc, 0, 0, 0x00CC0020)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32),
            ('biHeight', ctypes.c_int32), ('biPlanes', ctypes.c_uint16),
            ('biBitCount', ctypes.c_uint16), ('biCompression', ctypes.c_uint32),
            ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_int32),
            ('biYPelsPerMeter', ctypes.c_int32), ('biClrUsed', ctypes.c_uint32),
            ('biClrImportant', ctypes.c_uint32)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = sw
    bi.biHeight = -sh
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(sw * sh * 4)
    got = g32.GetDIBits(hdc_mem, hbm, 0, sh, buf, ctypes.byref(bi), 0)
    g32.SelectObject(hdc_mem, old)
    g32.DeleteObject(hbm)
    g32.DeleteDC(hdc_mem)
    u32.ReleaseDC(0, hdc)
    if not got:
        return False

    if clip:
        cx, cy, cw, ch = clip
        cx = max(0, min(cx, sw - 1))
        cy = max(0, min(cy, sh - 1))
        cw = min(cw, sw - cx)
        ch = min(ch, sh - cy)
    else:
        cx, cy, cw, ch = 0, 0, sw, sh

    raw = buf.raw
    rows = []
    for y in range(cy, cy + ch):
        line = bytearray(b'\x00')
        base = y * sw * 4
        for x in range(cx, cx + cw):
            o = base + x * 4
            line += bytes((raw[o + 2], raw[o + 1], raw[o]))
        rows.append(bytes(line))
    w, h = cw, ch

    import struct
    import zlib

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(b''.join(rows), 6))
    out += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(out)
    return True


if __name__ == '__main__':
    sys.exit(main())
