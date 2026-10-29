# -*- coding: utf-8 -*-
"""app133 —— 孤儿锁探测（三路一致，fail-closed）。

🔴 **为什么必须用 ctypes**：
   - `tasklist /FI` 在 Git Bash 下会被当路径；
   - `Get-Process` / `Get-CimInstance` 只看**当前快照**，
     而 PID 可能刚被回收复用 ⇒ 会把**别人的活锁**误判成死锁。
   ⇒ 权威判据 = `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` +
     `GetExitCodeProcess` ⇒ `err == 87`（ERROR_INVALID_PARAMETER）
     ⇒ **该 PID 确定不存在** ⇒ 可回收。

三路一致才回收：
   ① ctypes `OpenProcess` ⇒ err=87；
   ② `machine_lock_app.lock_state()` ⇒ `stale_pid`；
   ③ 进程表里**没有**该 PID / 没有 python 进程。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, REPO)

import machine_lock_app as ml  # noqa: E402

LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'


def ctypes_pid_alive(pid: int):
    """返回 (alive: bool, err: int)。

    ⚠️ **必须用 `WinDLL('kernel32', use_last_error=True)`**：
       `ctypes.windll.kernel32`（不带 use_last_error）**不会**把 Win32 的
       last-error 同步进 ctypes 的线程局部槽 ⇒ `ctypes.get_last_error()`
       读到的是**陈旧值（0）** ⇒ 会把「确定已死」误判成「活着」。
       （本轮实测踩过：同一 PID 两个探针给出矛盾结论 ⇒ 根因在此。）
    ⚠️ 另一种正确写法 = 直接调 Win32 的 `GetLastError()`（产品代码
       `machine_lock_app._pid_alive` 就是这么写的 ⇒ 它是对的）。
    """
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int,
                                      ctypes.c_void_p]
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        err = ctypes.get_last_error()
        # err=87 ⇒ 该 PID **确定不存在**
        return (err != 87), err
    code = ctypes.c_ulong()
    ok = kernel32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
    kernel32.CloseHandle(ctypes.c_void_p(h))
    if not ok:
        return True, -1          # 探测失败 ⇒ **视为存活**
    alive = (code.value == 259)  # STILL_ACTIVE
    return alive, 0


def main():
    out = {'lock_path': LOCK, 'exists': os.path.exists(LOCK)}
    if not out['exists']:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    with open(LOCK, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read().strip()
    out['raw'] = raw
    print('raw =', repr(raw))

    state, info = ml.lock_state(LOCK)
    out['lock_state'] = state
    out['lock_info'] = {k: str(v) for k, v in (info or {}).items()}
    print('lock_state =', state)
    print('lock_info  =', out['lock_info'])

    pid = None
    try:
        pid = int((info or {}).get('pid') or 0) or None
    except Exception:
        pid = None
    if pid is None:
        for cand in (info or {}).get('pid_candidates', []) or []:
            try:
                pid = int(cand)
                break
            except Exception:
                pass
    out['pid'] = pid
    print('pid =', pid)

    if pid is not None:
        alive, err = ctypes_pid_alive(pid)
        out['ctypes_alive'] = alive
        out['ctypes_err'] = err
        print('ctypes: alive=%s err=%s' % (alive, err))

    try:
        pids = ml.external_python_pids()
    except Exception as e:
        pids = ['<error: %s>' % e]
    out['external_python_pids'] = list(pids)
    print('external python pids =', pids)

    out['reclaimable'] = bool(
        pid is not None
        and out.get('ctypes_err') == 87
        and state in ('stale_pid', 'stale_boot')
        and not out['external_python_pids'])
    print('reclaimable =', out['reclaimable'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
