# -*- coding: utf-8 -*-
"""_app459_lock_reclaim.py — 按 fail-closed 判活规则安全回收 MACHINE_LOCK。

纪律（MEMORY）：
  * 探测失败（OpenProcess 失败 / 拿不到 PID）⇒ 一律视为**存活** ⇒ 不回收；
  * `GetExitCodeProcess` 返回 **259 = STILL_ACTIVE ⇒ 活**（只有 **0 才是死**）；
  * 只按**精确 PID** 判，不按 `python.exe` 通配。
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
import time

LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'


def probe(pid):
    """返回 (exit_code, last_error)。

    🔴 必须用 ``use_last_error=True`` 才能拿到**真实**的 GetLastError：
       默认的 ``ctypes.windll`` 不保存 last-error ⇒ 取到的永远是 0。
    判据（MEMORY）：
       * ``OpenProcess`` 失败 + err==**87**（ERROR_INVALID_PARAMETER）⇒ PID 不存在 ⇒ **死**；
       * 探测失败（其它 err / 拿不到句柄）⇒ **fail-closed ⇒ 视为存活**；
       * ``GetExitCodeProcess`` 得到 **259**（STILL_ACTIVE）⇒ **活**；只有 **0** 才是死。
    """
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return None, ctypes.get_last_error()
    c = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(c))
    if not ok:
        return None, ctypes.get_last_error()
    return c.value, 0


def main():
    if not os.path.isfile(LOCK):
        print('LOCK NOT_PRESENT')
        return 0
    text = open(LOCK, encoding='utf-8', errors='replace').read()
    print('--- lock content ---')
    print(text.strip())
    m = re.search(r'^pid:\s*(\d+)', text, re.M)
    if not m:
        print('🔴 解析不出 PID ⇒ fail-closed ⇒ 视为存活 ⇒ 不回收')
        return 2
    pid = int(m.group(1))
    code, err = probe(pid)
    print('pid=%d exit_code=%s err=%s' % (pid, code, err))
    if code is None:
        if err == 87:
            print('✅ OpenProcess err=87（ERROR_INVALID_PARAMETER）⇒ PID 不存在 ⇒ 死 ⇒ 回收锁')
            os.remove(LOCK)
            print('LOCK REMOVED')
            return 0
        print('🔴 探测失败（err=%s）⇒ fail-closed ⇒ 视为存活 ⇒ 不回收' % err)
        return 2
    if code != 0:
        print('🔴 exit_code=%d ≠ 0 ⇒ STILL_ACTIVE ⇒ 活 ⇒ 不回收' % code)
        return 2
    print('✅ exit_code==0 ⇒ PID 真死 ⇒ 回收锁')
    os.remove(LOCK)
    print('LOCK REMOVED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
