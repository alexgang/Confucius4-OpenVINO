"""machine_lock.py — 共享机器锁（EXT 铁律）

EXT-001 总原则：
  "计时作业持 C:\\Users\\Trekker-PTL\\shared\\MACHINE_LOCK（只能排队，不能删别人的锁）"

铁律（来自巡检 prompt）：
  * 计时或测速作业开始前创建锁，结束后删除；
  * 锁已存在就等待；
  * **回收锁前必须用 ctypes 的 OpenProcess + GetExitCodeProcess 确认 PID 真死，
    探测失败一律视为存活**（Git Bash 下 tasklist /FI 会被当路径，曾误回收他人活锁）。

本模块提供两个 API：
    hold(module_name)   —— 上下文管理器：抢锁 → 做事 → 释放
    probe_pid_alive(pid) —— 用 ctypes 确认 PID 是否真死
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import time
from contextlib import contextmanager
from typing import Optional

LOCK_PATH = r"C:\Users\Trekker-PTL\shared\MACHINE_LOCK"

# ── Win32 进程存活探测（ctypes，绕开 tasklist 的路径陷阱） ─────────
_kernel32 = None
if os.name == "nt":
    try:
        _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                          wintypes.DWORD]
        _kernel32.OpenProcess.restype = wintypes.HANDLE
        _kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                                 ctypes.POINTER(wintypes.DWORD)]
        _kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        _kernel32.CloseHandle.restype = wintypes.BOOL
    except Exception:  # pragma: no cover
        _kernel32 = None

STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _pid_exists_via_psutil(pid: int) -> Optional[bool]:
    """用 psutil 确认 PID 是否存在。

    Returns
    -------
    bool or None
        True = 存在；False = 确认不存在；None = 无法确认（psutil 不可用/异常）。
    """
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return None


def probe_pid_alive(pid: int) -> bool:
    """用 OpenProcess + GetExitCodeProcess 确认 PID 是否**真的**还活着。

    ★ 铁律：探测失败 ⇒ **一律视为存活**（宁可等，也不误回收别人的锁）。

    但要区分两种「拿不到句柄」的情况（实测踩坑）：
      * 进程**已完全消失** ⇒ OpenProcess 返回 NULL，句柄拿不到
      * 进程**活着但权限不足** ⇒ OpenProcess 也可能返回 NULL
    两者在 Win32 层面无法区分 ⇒ 用 **psutil.pid_exists** 二次确认：
      * psutil 说**不存在** ⇒ 确认已死 ⇒ 可以回收锁
      * psutil 说**存在**或**无法确认** ⇒ 视为存活 ⇒ 继续等待

    Returns
    -------
    bool
        True = 确认还活着（或无法确认）；False = 确认已死。
    """
    if _kernel32 is None:
        # ctypes 不可用 ⇒ 只能退回 psutil；psutil 也不可用 ⇒ 视为存活
        exists = _pid_exists_via_psutil(pid)
        return True if exists is None else (not exists)
    try:
        h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            # 拿不到句柄 ⇒ 用 psutil 区分「已死」与「权限不足」
            exists = _pid_exists_via_psutil(pid)
            if exists is False:
                return False        # 确认进程已不存在
            return True             # 存在或无法确认 ⇒ 保守视为存活
        try:
            code = wintypes.DWORD()
            if not _kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
                return True   # 探测失败 ⇒ 视为存活
            return code.value == STILL_ACTIVE
        finally:
            _kernel32.CloseHandle(h)
    except Exception:
        return True          # 任何异常 ⇒ 视为存活


def read_lock() -> Optional[dict]:
    """读取锁文件内容，解析出 {module, pid, started}。"""
    if not os.path.isfile(LOCK_PATH):
        return None
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except Exception:
        return None
    if not raw:
        return None
    parts = raw.split()
    info = {"raw": raw, "module": parts[0] if parts else "?",
            "pid": None, "started": " ".join(parts[1:])}
    for tok in parts[1:]:
        if tok.isdigit():
            info["pid"] = int(tok)
            break
    return info


@contextmanager
def hold(module_name: str, *, wait_timeout: float = 600.0,
         poll_sec: float = 2.0, log=print):
    """抢共享机器锁（上下文管理器）。

    行为：
      * 锁不存在 ⇒ 创建（内容：模块名 PID 开始时间），做事，退出时删除；
      * 锁存在且持有者**确认已死** ⇒ 回收（打印回收说明），再创建；
      * 锁存在且持有者**还活着或无法确认** ⇒ **等待**（轮询），不抢。

    绝不删除别人的活锁 —— 这是铁律。
    """
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    deadline = time.time() + wait_timeout
    created = False

    while True:
        if not os.path.exists(LOCK_PATH):
            try:
                with open(LOCK_PATH, "x", encoding="utf-8") as f:
                    f.write(f"{module_name} {os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')}")
                created = True
                log(f"[lock] 已取得共享锁：{module_name} PID={os.getpid()}")
                break
            except FileExistsError:
                continue

        info = read_lock() or {}
        pid = info.get("pid")
        if pid is None:
            log(f"[lock] 锁内容无法解析 PID（{info.get('raw')!r}）⇒ 保守等待")
        else:
            alive = probe_pid_alive(pid)
            if not alive:
                log(f"[lock] 持有者 PID={pid} 已确认死亡 ⇒ 回收锁并接管")
                try:
                    os.remove(LOCK_PATH)
                except Exception as e:
                    log(f"[lock] 回收失败：{e}")
                continue
            log(f"[lock] 锁被 {info.get('module')} PID={pid} 持有（存活）⇒ 等待")

        if time.time() > deadline:
            raise TimeoutError(f"等待共享锁超时（{wait_timeout}s）：{info.get('raw')!r}")
        time.sleep(poll_sec)

    try:
        yield
    finally:
        if created:
            try:
                os.remove(LOCK_PATH)
                log("[lock] 已释放共享锁")
            except Exception as e:
                log(f"[lock] 释放锁失败：{e}")


if __name__ == "__main__":
    import sys
    info = read_lock()
    if info is None:
        print("当前无共享锁")
    else:
        alive = probe_pid_alive(info["pid"]) if info.get("pid") else None
        print(f"锁内容: {info['raw']}")
        print(f"模块={info['module']} PID={info['pid']} 存活={alive}")
