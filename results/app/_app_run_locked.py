#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app_run_locked.py —— **持机器锁**跑一条外部命令的小跑道。

🔴 纪律（shared/MACHINE_LOCK）：
  · 锁存在 ⇒ **排队等待**，不抢锁；
  · 回收锁前**必须**用 ctypes 的 `OpenProcess` + `GetExitCodeProcess`
    确认 PID **真死**；**探测失败一律视为存活**（fail-closed）
    ⇒ Git Bash 下 `tasklist /FI` 会被当路径，曾误回收他人活锁；
  · 锁内容：``模块名 PID 开始时间``；
  · 跑完**删锁**。

用法：
    python _app_run_locked.py <模块名> <日志文件> <cmd> [args...]
退出码：
    0  = 命令跑完（命令自身的 rc 见日志末尾的 ``__RC__=`` 行）
    10 = 锁被别人**活着**持有 ⇒ 本次不跑（调用方应排队/退出）
    11 = 锁探测失败（fail-closed）⇒ 本次不跑
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

STILL_ACTIVE = 259


def _open_process(pid):
    """返回 (handle, exit_code)；**任何异常 ⇒ 视为存活**（fail-closed）。"""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                              False, int(pid))
    if not h:
        # 🔴 87 = ERROR_INVALID_PARAMETER ⇒ 进程已死；其它错误 ⇒ 不确定
        err = ctypes.get_last_error()
        if err == 87:
            return None, None          # 确证已死
        return None, 'unknown'         # 探测失败 ⇒ 视为存活
    code = wt.DWORD()
    ok = kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    if not ok:
        return None, 'unknown'
    if code.value == STILL_ACTIVE:
        return h, 'alive'
    return h, code.value               # 具体退出码 ⇒ 已死


def lock_holder():
    """读锁文件 ⇒ (pid, 原文)；读不到 ⇒ (None, None)。"""
    try:
        with open(LOCK, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read().strip()
    except Exception:
        return None, None
    if not raw:
        return None, raw
    parts = raw.split()
    try:
        return int(parts[1]), raw
    except Exception:
        return None, raw


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    module, logf = sys.argv[1], sys.argv[2]
    cmd = sys.argv[3:]

    # ── 1) 锁是否可占 ──
    pid, raw = lock_holder()
    if pid is not None:
        h, state = _open_process(pid)
        if state == 'alive':
            print('[lock] 锁被 PID %d 持有（活着）⇒ 不抢锁，退出 10\n%s'
                  % (pid, raw), flush=True)
            return 10
        if state == 'unknown':
            print('[lock] 锁 PID %d 探测失败 ⇒ fail-closed 视为存活，退出 11'
                  % pid, flush=True)
            return 11
        print('[lock] 锁 PID %d 已死（exit=%s）⇒ 回收' % (pid, state),
              flush=True)
        try:
            os.remove(LOCK)
        except Exception as e:
            print('[lock] 回收失败: %r' % (e,), flush=True)
            return 11

    # ── 2) 占锁（写自己的 PID）──
    me = os.getpid()
    with open(LOCK, 'w', encoding='utf-8') as f:
        f.write('%s %d %s\n' % (module, me,
                                time.strftime('%Y-%m-%d %H:%M:%S')))
    print('[lock] 已占锁：%s PID=%d' % (module, me), flush=True)

    # ── 3) 跑命令 ──
    t1 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        rc, so, se = p.returncode, (p.stdout or ''), (p.stderr or '')
    except subprocess.TimeoutExpired as e:
        rc = -1
        so = (e.stdout or '') if isinstance(e.stdout, str) else \
            (e.stdout or b'').decode('utf-8', 'replace')
        se = (e.stderr or '') if isinstance(e.stderr, str) else \
            (e.stderr or b'').decode('utf-8', 'replace')
        se += '\n[timeout 7200s]\n'
    el = round(time.time() - t1, 1)

    os.makedirs(os.path.dirname(os.path.abspath(logf)), exist_ok=True)
    with open(logf, 'w', encoding='utf-8') as f:
        f.write('CMD: %r\n' % (cmd,))
        f.write('ELAPSED_S: %s\n' % el)
        f.write('__RC__=%d\n' % rc)
        f.write('--- STDOUT ---\n%s\n--- STDERR ---\n%s\n' % (so, se))

    # ── 4) 删锁 ──
    try:
        os.remove(LOCK)
        print('[lock] 已删锁', flush=True)
    except Exception as e:
        print('[lock] 删锁失败: %r' % (e,), flush=True)

    print('__RC__=%d elapsed=%ss log=%s' % (rc, el, logf), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
