"""diag_overlay_gui.py —— 屏幕字幕真 Tk 冒烟（两栏 / 鼠标穿透 / 拖拽把手）。

APP-007 第 3、4 项的验证脚本。⚠️ 需要显示器（会真的弹出一个字幕窗）。

🔴 穿透验证**必须用 WindowFromPoint**，不能用 WM_NCHITTEST
   （实测设了 WS_EX_TRANSPARENT 后它仍返回 HTCLIENT），
   也不能用 Tk 的 event_generate（合成事件绕过系统命中测试，仍会送达）
   ⇒ 这两种方法都会给**假阳性**。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILS = []


def check(name, cond, detail=''):
    print(f'  [{"PASS" if cond else "FAIL"}] {name}' + (f'  {detail}' if detail else ''))
    if not cond:
        FAILS.append(name)


class _E:
    """伪造一个 Tk 事件对象（只带 x_root / y_root）。"""

    def __init__(self, x, y):
        self.x_root = x
        self.y_root = y


def main():
    import tkinter as tk
    import win_clickthrough as wct
    from live_caption_app import CaptionOverlay

    root = tk.Tk()
    root.geometry('900x700+50+50')
    root.update_idletasks()

    ov = CaptionOverlay(root, 26)
    root.update_idletasks()
    root.update()

    # ── ① 只有两行（定稿译文 + 实时识别）────────────────────────────
    check('① 只有 mt / partial 两个 Label（删掉了定稿原文与草稿预览）',
          hasattr(ov, 'mt') and hasattr(ov, 'partial')
          and not hasattr(ov, 'final') and not hasattr(ov, 'draft')
          and not hasattr(ov, 'draft_label'))
    check('① 译文行颜色 = 青 #5fd7d7',
          str(ov.mt.cget('fg')).lower() in ('#5fd7d7',),
          str(ov.mt.cget('fg')))
    check('① 实时行颜色 = 黄 #ffd75e',
          str(ov.partial.cget('fg')).lower() in ('#ffd75e',),
          str(ov.partial.cget('fg')))

    # ── ② show() 两参 ────────────────────────────────────────────────
    ov.show('这是定稿译文', '这是实时识别')
    root.update_idletasks()
    check('② show 两参：译文行有内容', '这是定稿译文' in str(ov.mt.cget('text')),
          str(ov.mt.cget('text')))
    check('② show 两参：实时行有内容', '这是实时识别' in str(ov.partial.cget('text')),
          str(ov.partial.cget('text')))

    # ── ③ 鼠标穿透（EXSTYLE 位 + WindowFromPoint）────────────────────
    h = wct.hwnd_of(ov.win)
    check('③ 取到顶层 hwnd', bool(h), f'hwnd={h}')
    ex = wct.get_exstyle(h)
    check('③ EXSTYLE 含 WS_EX_TRANSPARENT',
          bool(ex & wct.WS_EX_TRANSPARENT), hex(ex))
    check('③ EXSTYLE 含 WS_EX_NOACTIVATE',
          bool(ex & wct.WS_EX_NOACTIVATE), hex(ex))

    px = ov.win.winfo_rootx() + 30
    py = ov.win.winfo_rooty() + 15
    at = wct.window_at(px, py)
    check('③ WindowFromPoint 不再命中字幕窗口（穿透真实生效）',
          not wct.belongs_to(at, h), f'at={at} overlay={h}')

    # ── ④ 把手窗口：不穿透、能接到鼠标 ────────────────────────────────
    hh = wct.hwnd_of(ov.handle)
    check('④ 把手窗口存在', bool(hh), f'hwnd={hh}')
    check('④ 把手未被设为穿透（是唯一的拖拽入口）',
          not (wct.get_exstyle(hh) & wct.WS_EX_TRANSPARENT),
          hex(wct.get_exstyle(hh)))
    hat = wct.window_at(ov.handle.winfo_rootx() + 8,
                         ov.handle.winfo_rooty() + 8)
    check('④ WindowFromPoint 命中把手',
          wct.belongs_to(hat, hh), f'at={hat} handle={hh}')

    # ── ⑤ 拖把手 ⇒ 字幕窗口跟着动，且相对位置不变 ────────────────────
    x0, y0 = ov.win.winfo_x(), ov.win.winfo_y()
    hx0, hy0 = ov.handle.winfo_x(), ov.handle.winfo_y()
    ov._press_handle(_E(hx0 + 5, hy0 + 5))
    ov._drag_handle(_E(hx0 + 105, hy0 + 45))
    root.update_idletasks()
    nx, ny = ov.win.winfo_x(), ov.win.winfo_y()
    check('⑤ 拖把手后字幕窗口移动了', (nx, ny) != (x0, y0),
          f'({x0},{y0}) -> ({nx},{ny})')
    check('⑤ 把手与字幕窗口保持绑定（相对位置不变）',
          abs((ov.handle.winfo_x() - ov.win.winfo_x()) - ov._h_off[0]) <= 2
          and abs((ov.handle.winfo_y() - ov.win.winfo_y()) - ov._h_off[1]) <= 2,
          f'handle=({ov.handle.winfo_x()},{ov.handle.winfo_y()}) '
          f'win=({ov.win.winfo_x()},{ov.win.winfo_y()}) off={ov._h_off}')

    # ── ⑥ 降级路径：关掉穿透后，字幕窗口仍能直接拖 ───────────────────
    ov._toggle_click_through()
    root.update_idletasks()
    check('⑥ 可以关掉穿透', not ov.click_through, str(ov.click_through))
    check('⑥ 关掉后 WindowFromPoint 重新命中字幕窗口',
          wct.belongs_to(wct.window_at(ov.win.winfo_rootx() + 30,
                                        ov.win.winfo_rooty() + 15), h))
    ov._toggle_click_through()
    root.update_idletasks()
    check('⑥ 可以重新打开穿透', ov.click_through, str(ov.click_through))

    # ── ⑦ 兜底拖动（穿透失败时用的那条路径）仍可用 ────────────────────
    bx, by = ov.win.winfo_x(), ov.win.winfo_y()
    ov._press(_E(bx + 10, by + 10))
    ov._drag(_E(bx + 60, by + 40))
    root.update_idletasks()
    check('⑦ 兜底拖动路径可用（字幕窗口直接拖）',
          (ov.win.winfo_x(), ov.win.winfo_y()) != (bx, by),
          f'({bx},{by}) -> ({ov.win.winfo_x()},{ov.win.winfo_y()})')

    ov.destroy()
    root.destroy()

    print()
    if FAILS:
        print('ALL FAIL (' + str(len(FAILS)) + '): ' + ', '.join(FAILS))
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
