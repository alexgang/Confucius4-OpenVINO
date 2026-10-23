"""diag_layout_gui.py —— APP-007 GUI 主面板布局冒烟 + 截屏。

验证用户提的 4 项 GUI 改造里，**主面板**相关的两项：

  ① **状态信息位置**：底部状态栏迁到「三个配置分区上方、顶栏之下，固定一行」
     ⇒ 在**非全屏**（1080x700，小窗口）下也必须可见，且高度 > 10px。
     ⚠️ 以前不可见的真实原因不是「全屏」，是 **pack 挤压**：
        ScrolledText 默认请求 718px，pack 优先满足它 ⇒ 状态栏被压成 1px。
        ⇒ 现在状态栏排在 self.txt **之前** pack，且 self.txt 固定 height=10。

  ② **配置面板分区**：ASR / 翻译 / 语音三个 LabelFrame 各自独立，
     每个分区**只有一个**「设备+精度」组合下拉。

顺带：截一张图存盘（evidence 用）。

跑法（需要显示器，会真的弹窗 2 秒）：
    .venv\\Scripts\\python.exe live_caption\\diag_layout_gui.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILS = []


def check(name, cond, detail=''):
    print(f'  [{"PASS" if cond else "FAIL"}] {name}' + (f'  {detail}' if detail else ''))
    if not cond:
        FAILS.append(name)


class _Args:
    translate = 'off'
    mt_engine = 'auto'
    mt_ctx = False
    mt_glossary = False
    mt_draft = False
    asr_lang = 'auto'
    engine = 'gpu_int8'
    source = 'mic'
    device = None
    system_device = None
    file = None
    speed = 1.0
    loop = False
    overlay = True
    font_size = 26
    asr_device = 'GPU.0'
    mt_device = 'GPU.0'
    tts_device = 'NPU'
    device_notes = []
    tts = 'off'
    tts_voice = 'A'
    tts_precision = 'f32'
    tts_out_device = None
    selftest = 0
    autostart = False


def _measure(root, app, w, h):
    """把窗口调整到 w×h 并返回各关键控件的实际几何。"""
    root.geometry(f'{w}x{h}+40+40')
    root.update_idletasks()
    root.update()
    time.sleep(0.2)
    root.update()
    return {
        'meter': (app.lbl_meter.winfo_width(), app.lbl_meter.winfo_height()),
        'status': app.var_status.get(),
        'txt': (app.txt.winfo_width(), app.txt.winfo_height()),
        'root_h': root.winfo_height(),
    }


def main():
    import tkinter as tk
    from live_caption_app import App

    root = tk.Tk()
    # ⚠️ App.__init__ 末尾会调 load_engine()（后台线程真去加载 ASR 模型）。
    #    本脚本只测**布局**，不测推理 ⇒ 在构造前把它替换成空操作，
    #    避免起模型编译进程（那会占 GPU/NPU 并拖慢测量）。
    import live_caption_app as lca
    _orig_load = lca.App.load_engine
    lca.App.load_engine = lambda self: None
    try:
        app = App(root, _Args())
    finally:
        lca.App.load_engine = _orig_load
    root.update_idletasks()

    print('== ① 状态栏在非全屏窗口下可见 ==')
    for w, h in ((1080, 820), (1080, 700), (900, 600), (800, 500)):
        m = _measure(root, app, w, h)
        mh = m['meter'][1]
        check(f'{w}x{h}: 状态栏高度 > 10px（不再被压成 1px）',
              mh > 10, f"meter={m['meter']} txt={m['txt']}")
        check(f'{w}x{h}: 主文本区仍有高度', m['txt'][1] > 40,
              f"txt={m['txt']}")

    print('\n== ② 状态栏位于三个分区上方（顶栏之下）==')
    root.geometry('1080x700+40+40')
    root.update_idletasks()
    root.update()
    # 状态栏 Label 的 y 坐标应**小于**三个分区 LabelFrame 的 y 坐标
    # （即状态栏在分区上方）。分区 Frame 是 areas 的子控件。
    areas = None
    for w in root.winfo_children():
        # areas 是 ttk.Frame，三个 LabelFrame 在里面
        for c in w.winfo_children():
            if 'Labelframe' in c.winfo_class():
                areas = w
                break
        if areas is not None:
            break
    check('找到三个分区容器', areas is not None)
    if areas is not None:
        lfs = [c for c in areas.winfo_children()
               if 'Labelframe' in c.winfo_class()]
        check('分区数 = 3（ASR / 翻译 / 语音）', len(lfs) == 3, str(len(lfs)))
        titles = [str(c.cget('text')) for c in lfs]
        check('分区标题正确', titles == ['ASR 识别', '翻译', '语音输出'], str(titles))
        meter_y = app.lbl_meter.winfo_rooty()
        area_y = areas.winfo_rooty()
        check('状态栏在分区上方', meter_y < area_y,
              f'meter_y={meter_y} areas_y={area_y}')

    print('\n== ③ 每个分区只有一个组合下拉 ==')
    for role, cbname in (('asr', 'cb_asr_combo'),
                         ('mt', 'cb_mt_combo'),
                         ('tts', 'cb_tts_combo')):
        check(f'{role}: 组合下拉存在', hasattr(app, cbname))
        check(f'{role}: 旧的独立设备下拉已删除',
              not any(hasattr(app, n) for n in
                      (f'cb_dev_{role}', f'var_dev_{role}')))
    check('三个分区都存在组合下拉',
          all(hasattr(app, n) for n in
              ('cb_asr_combo', 'cb_mt_combo', 'cb_tts_combo')))

    print('\n== ④ 截屏 ==')
    # 先给状态栏一条内容（真实运行时是「RTF / 状态」），否则截图里看不到它
    app.var_status.set('状态栏测试：ASR 就绪 · 翻译 INT8-CW · 语音关闭')
    app.var_meter.set('RTF 0.42  积压 0.0s  段 3')
    root.geometry('1080x820+40+40')
    root.update_idletasks()
    root.update()
    shot = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'results', 'app', 'gui_layout_1080x820.png')
    shot = os.path.abspath(shot)
    os.makedirs(os.path.dirname(shot), exist_ok=True)
    try:
        root.update()
        time.sleep(0.4)
        root.update()
        ok = _capture(root, shot)
        check('截屏成功', ok, shot)
    except Exception as e:
        check('截屏成功', False, f'{type(e).__name__}: {e}')

    try:
        app.quit()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass

    print()
    if FAILS:
        print(f'ALL FAIL ({len(FAILS)}): ' + ', '.join(FAILS))
        return 1
    print('ALL PASS')
    return 0


def _capture(root, path):
    """用纯 ctypes + GDI 抓窗口内容到 PNG（不依赖 pywin32/PIL）。

    走 ``PrintWindow``（PW_RENDERFULLCONTENT）⇒ 能抓到**被遮挡**的窗口，
    比屏幕 BitBlt 可靠。
    """
    import ctypes
    import struct
    import zlib

    u32 = ctypes.windll.user32
    g32 = ctypes.windll.gdi32

    hwnd = int(root.winfo_id())
    parent = u32.GetParent(hwnd)
    if parent:
        hwnd = parent

    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                    ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

    r = RECT()
    if not u32.GetWindowRect(hwnd, ctypes.byref(r)):
        return False
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return False

    hdc_win = u32.GetWindowDC(hwnd)
    hdc_mem = g32.CreateCompatibleDC(hdc_win)
    hbm = g32.CreateCompatibleBitmap(hdc_win, w, h)
    old = g32.SelectObject(hdc_mem, hbm)
    # PW_RENDERFULLCONTENT = 2
    ok = u32.PrintWindow(hwnd, hdc_mem, 2)
    if not ok:
        g32.BitBlt(hdc_mem, 0, 0, w, h, hdc_win, 0, 0, 0x00CC0020)

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
    bi.biWidth = w
    bi.biHeight = -h            # 负数 = 自上而下
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = g32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bi), 0)

    g32.SelectObject(hdc_mem, old)
    g32.DeleteObject(hbm)
    g32.DeleteDC(hdc_mem)
    u32.ReleaseDC(hwnd, hdc_win)
    if not got:
        return False

    raw = buf.raw
    rows = []
    for y in range(h):
        line = bytearray(b'\x00')
        base = y * w * 4
        for x in range(w):
            o = base + x * 4
            line += bytes((raw[o + 2], raw[o + 1], raw[o]))   # BGR → RGB
        rows.append(bytes(line))
    png = _png_bytes(w, h, b''.join(rows))
    with open(path, 'wb') as f:
        f.write(png)
    return True


def _png_bytes(w, h, raw):
    """把 RGB 裸数据打包成 PNG（纯 stdlib）。"""
    import struct
    import zlib

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 6))
    out += chunk(b'IEND', b'')
    return out


if __name__ == '__main__':
    sys.exit(main())
