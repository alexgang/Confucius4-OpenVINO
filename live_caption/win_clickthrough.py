"""win_clickthrough.py —— Windows 鼠标穿透 + 扩展样式读写（纯 ctypes，无第三方依赖）。

背景
----
屏幕字幕是 ``tk.Toplevel``，要求「默认完全鼠标穿透」（不影响其后方桌面元素
操作）+「独立拖拽把手」（窄条区域可拖动）。

🔴 核心技术矛盾
----------------
Windows 上给窗口加 ``WS_EX_TRANSPARENT`` 之后，窗口**收不到鼠标消息**
⇒ 现有 Tk 的 ``<ButtonPress-1>`` / ``<B1-Motion>`` 拖动必然失效。
⇒ 解法：**字幕主窗口完全穿透，另建一个不穿透的小 Toplevel「拖拽把手」**，
   拖动把手时同步更新主窗口的 ``geometry('+x+y')``。
   （不用 WM_NCHITTEST 覆写、不用 SetWindowsHookEx 全局钩子 ——
     后者需要更高权限，且在别的进程上不可靠。）

⚠️ 四个必须记住的实现要点（都是本机实测结论，不是推测）
----------------------------------------------------------
1. **Tk 的 ``winfo_id()`` 是子窗口**，真正的顶层窗口要取
   ``GetParent(winfo_id())``。扩展样式必须设在**顶层**上 ——
   设在子窗口上**完全不生效而且不报错**（最坑的坑）。
2. **``SetWindowLongW`` 的返回值不能当成功判据** —— 失败返回 0，
   而旧样式值也可能是 0（合法的旧值）；且失败时 ``GetLastError()==0``。
   ⇒ 唯一可靠判据是**回读 ``GetWindowLongW`` 校验目标位是否已置上**。
3. Tk 的 ``attributes('-alpha', ...)`` **本身就会置上 ``WS_EX_LAYERED``**
   （实测 EXSTYLE 含 0x00080000），所以只需要追加
   ``WS_EX_TRANSPARENT | WS_EX_NOACTIVATE``；
   且之后再改 ``-alpha`` **不会**清掉 TRANSPARENT（实测保持）。
4. **验证穿透必须用 ``WindowFromPoint``** ——
   - ``WM_NCHITTEST`` **不可靠**：设了 TRANSPARENT 后它仍返回 ``HTCLIENT``；
   - Tk 的 ``event_generate`` **也不可靠**：合成事件绕过系统命中测试，
     照样会送达穿透窗口。
   ⇒ 这两种方法都会给出**假阳性**（看起来没穿透，其实有）。

降级路径
--------
``enable_click_through()`` 返回 False（平台不是 Windows / API 不可用 /
回读校验失败）⇒ 调用方**保持字幕窗口可交互**（老式直接拖动），
并把原因写进状态栏。**本模块永不向调用方抛异常。**
"""

from __future__ import annotations

import sys

# ── Win32 常量 ──────────────────────────────────────────────────────
GWL_EXSTYLE = -20

WS_EX_TRANSPARENT = 0x00000020      # 鼠标穿透（不接收鼠标消息）
WS_EX_LAYERED = 0x00080000          # 分层窗口（Tk 的 -alpha 已经会置上）
WS_EX_NOACTIVATE = 0x08000000       # 点击不激活、不抢焦点
WS_EX_TOOLWINDOW = 0x00000080       # 不在任务栏显示

# 需要一起置上/清掉的位
_TRANSPARENT_BITS = WS_EX_TRANSPARENT | WS_EX_NOACTIVATE

_MASK32 = 0xFFFFFFFF


def _user32():
    """拿 user32.dll 并声明好 argtypes/restype。

    ⚠️ 64 位下**必须声明 argtypes/restype**，否则指针/句柄会被截断。
    范式抄 `live_caption/replay_c134_mt.py:58-68`。
    """
    import ctypes
    import ctypes.wintypes as wt
    dll = ctypes.WinDLL('user32', use_last_error=True)
    dll.SetWindowLongW.restype = wt.LONG
    dll.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
    dll.GetWindowLongW.restype = wt.LONG
    dll.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    dll.GetParent.restype = wt.HWND
    dll.GetParent.argtypes = [wt.HWND]
    dll.WindowFromPoint.restype = wt.HWND
    dll.WindowFromPoint.argtypes = [wt.POINT]
    return dll


def _is_windows() -> bool:
    return sys.platform.startswith('win')


def hwnd_of(widget) -> int:
    """Tk 控件 -> **顶层**窗口句柄（int；失败返回 0）。

    ⚠️ Tk 的 ``winfo_id()`` 返回的是**子窗口**；Toplevel 的真实顶层
    要再取一次 ``GetParent``。实测：不取 GetParent 时设置扩展样式
    完全不生效（且不报错）。
    """
    if not _is_windows():
        return 0
    try:
        u = _user32()
        wid = widget.winfo_id()
        parent = u.GetParent(wid)
        return int(parent or wid)
    except Exception:
        return 0


def get_exstyle(hwnd: int) -> int:
    """读窗口扩展样式（int；失败返回 0）。"""
    if not hwnd:
        return 0
    try:
        return int(_user32().GetWindowLongW(int(hwnd), GWL_EXSTYLE)) & _MASK32
    except Exception:
        return 0


def set_exstyle(hwnd: int, style: int) -> bool:
    """写窗口扩展样式。

    返回**回读校验是否通过**（不是 API 返回值 —— 见模块 docstring 要点 2）。
    校验失败时**回滚到原样式**，绝不留半吊子状态。
    """
    if not hwnd:
        return False
    try:
        u = _user32()
        cur = get_exstyle(hwnd)
        u.SetWindowLongW(int(hwnd), GWL_EXSTYLE, int(style) & _MASK32)
        if (get_exstyle(hwnd) & _MASK32) == (int(style) & _MASK32):
            return True
        # 回滚
        u.SetWindowLongW(int(hwnd), GWL_EXSTYLE, cur)
        return False
    except Exception:
        return False


def enable_click_through(widget) -> bool:
    """把 Tk 窗口设为**完全鼠标穿透**。

    返回 True = 穿透已生效；False = **未生效**（调用方须降级）。
    **永不抛异常。**
    """
    if not _is_windows():
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False
    try:
        cur = get_exstyle(hwnd)
        if (cur & _TRANSPARENT_BITS) == _TRANSPARENT_BITS:
            return True                       # 已经穿透
        want = (cur | WS_EX_LAYERED | _TRANSPARENT_BITS) & _MASK32
        return set_exstyle(hwnd, want)        # 失败会自己回滚
    except Exception:
        return False


def disable_click_through(widget) -> bool:
    """恢复可交互（去掉 TRANSPARENT / NOACTIVATE）。返回是否成功。"""
    if not _is_windows():
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False
    try:
        cur = get_exstyle(hwnd)
        if not (cur & _TRANSPARENT_BITS):
            return True
        return set_exstyle(hwnd, cur & ~_TRANSPARENT_BITS & _MASK32)
    except Exception:
        return False


def is_click_through(widget) -> bool:
    """当前是否处于穿透状态。"""
    return bool(get_exstyle(hwnd_of(widget)) & WS_EX_TRANSPARENT)


def window_at(x: int, y: int) -> int:
    """屏幕坐标 (x, y) 处的**顶层窗口句柄**（0 = 没有）。

    ⚠️ 这是**验证鼠标穿透的正确工具**（见模块 docstring 要点 4）。
    """
    if not _is_windows():
        return 0
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = _user32()
        return int(u.WindowFromPoint(wt.POINT(int(x), int(y))) or 0)
    except Exception:
        return 0


def belongs_to(hwnd: int, root_hwnd: int) -> bool:
    """hwnd 是否属于 root_hwnd 这棵窗口树（沿 GetParent 上溯）。"""
    if not hwnd or not root_hwnd:
        return False
    try:
        u = _user32()
        cur = int(hwnd)
        while cur:
            if cur == int(root_hwnd):
                return True
            cur = int(u.GetParent(cur) or 0)
    except Exception:
        pass
    return False


if __name__ == '__main__':
    # 自检：不需要显示器，只验证 API 可用性与常量。
    print('platform      :', sys.platform)
    print('user32 可用   :', bool(_user32()) if _is_windows() else 'N/A')
    print('WS_EX_*       :', hex(WS_EX_TRANSPARENT), hex(WS_EX_LAYERED),
          hex(WS_EX_NOACTIVATE))
    print('window_at(0,0):', window_at(0, 0))
