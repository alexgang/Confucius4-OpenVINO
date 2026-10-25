r"""app037_quiet_window.py —— 检查点 3 的**安静窗口**等待（三层叠加的中间层）

为什么需要这一层
----------------
本项目铁律：**共享机器锁挡不住「不持锁」的别的模块作业**
⇒ ASR / MT / TTS 的脚本**大多不持锁** ⇒ 哪怕我拿到了 `shared/MACHINE_LOCK`，
别的模块照样能在我旁边跑 GPU 作业 ⇒ **我的计时数字会被污染**。

⇒ TTS 模块的经验（`shared/NOTICE_tts_lock_path_20261025.md`）是三层叠加：
  ① 先取锁 → ② 再等**安静窗口**（外部 python 进程为空且持续 N 秒）→
  ③ 无效条目自动重试。

本模块实现第 ② 层：**等待外部 python 进程为空并持续 `quiet_seconds` 秒**。

🔴 「外部进程」的判定
------------------
- **自己的进程树不算**（本脚本 + 它的父 shell）⇒ 否则永远等不到安静；
- 判据用 **ctypes Win32 API 枚举进程**（`CreateToolhelp32Snapshot` +
  `Process32FirstW/NextW`）⇒ **不用 `tasklist /FI`**（Git Bash 下会被当路径，
  且按进程名过滤会误判）；
- 判「是不是自己的」：看**命令行**里是否含本脚本的标识串
  （`app037_cp3_abba_v15.py` / `app037_quiet_window.py` / `machine_lock_app`）。

⚠️ **不杀别人的进程** —— 只**等**。

用法
----
    python app037_quiet_window.py --quiet-seconds 45 --timeout 1800
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as w
import os
import sys
import time

# 自己的标识串（出现在命令行里 ⇒ 视为「自己」，不计入外部干扰）
SELF_MARKERS = ('app037_cp3_abba_v15.py', 'app037_quiet_window.py',
                'machine_lock_app')


def list_processes():
    """枚举所有进程 => [(pid, exe_name, cmdline), ...]（ctypes，无外部依赖）。"""
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ('dwSize', w.DWORD),
            ('cntUsage', w.DWORD),
            ('th32ProcessID', w.DWORD),
            ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
            ('th32ModuleID', w.DWORD),
            ('cntThreads', w.DWORD),
            ('th32ParentProcessID', w.DWORD),
            ('pcPriClassBase', ctypes.c_long),
            ('dwFlags', w.DWORD),
            ('szExeFile', ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel32.Process32FirstW.restype = w.BOOL
    kernel32.Process32NextW.restype = w.BOOL

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return []
    out = []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                pid = int(pe.th32ProcessID)
                cmd = _cmdline(pid)
                out.append((pid, pe.szExeFile, cmd))
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return out


def _cmdline(pid):
    """读进程命令行。

    ⚠️ **`wmic` 在本机 Windows 上已被移除**（`WinError 2`）⇒ 不能用
    ⇒ 改走 **ctypes 直读 PEB**（`NtQueryInformationProcess` + `ProcessBasicInformation`
    + `ReadProcessMemory`）。

    🔴 读不到（权限不足 / 32/64 位不匹配）⇒ **返回空串**，
       调用方据此**保守判定为「外部进程」**（宁可多等，不误判成安静）。
    """
    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        ntdll = ctypes.WinDLL('ntdll', use_last_error=True)

        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010

        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('ExitStatus', ctypes.c_long),
                ('PebBaseAddress', ctypes.c_void_p),
                ('AffinityMask', ctypes.c_void_p),
                ('BasePriority', ctypes.c_void_p),
                ('UniqueProcessId', ctypes.c_void_p),
                ('InheritedFromUniqueProcessId', ctypes.c_void_p),
            ]

        h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION |
                                  PROCESS_QUERY_LIMITED_INFORMATION |
                                  PROCESS_VM_READ, False, pid)
        if not h:
            return ''
        try:
            pbi = PROCESS_BASIC_INFORMATION()
            ret = ctypes.c_ulong(0)
            st = ntdll.NtQueryInformationProcess(
                h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi),
                ctypes.byref(ret))
            if st != 0 or not pbi.PebBaseAddress:
                return ''
            peb = pbi.PebBaseAddress

            # PEB (x64) → ProcessParameters 在 offset 0x20
            ptr_size = ctypes.sizeof(ctypes.c_void_p)
            pp_off = 0x20 if ptr_size == 8 else 0x10
            params = ctypes.c_void_p()
            if not _read_mem(kernel32, h, ctypes.c_void_p(peb + pp_off),
                             ctypes.byref(params), ptr_size):
                return ''
            # RTL_USER_PROCESS_PARAMETERS → CommandLine (UNICODE_STRING) 在 offset 0x70
            cl_off = 0x70 if ptr_size == 8 else 0x40
            us = ctypes.c_byte * 16
            buf = us()
            if not _read_mem(kernel32, h, ctypes.c_void_p(params.value + cl_off),
                             ctypes.byref(buf), 16):
                return ''
            # UNICODE_STRING: {USHORT Length; USHORT MaximumLength; PWSTR Buffer;}
            length = ctypes.cast(ctypes.byref(buf, 0), ctypes.POINTER(
                ctypes.c_ushort))[0]
            bptr = ctypes.cast(ctypes.byref(buf, 8), ctypes.POINTER(
                ctypes.c_void_p))[0]
            if not length or not bptr:
                return ''
            buf2 = (ctypes.c_wchar * (length // 2 + 1))()
            if not _read_mem(kernel32, h, ctypes.c_void_p(bptr),
                             ctypes.byref(buf2), length + 2):
                return ''
            return buf2.value
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return ''


def _read_mem(kernel32, h, addr, out, size):
    n = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, addr, out, size, ctypes.byref(n))
    return bool(ok) and n.value == size


def external_python_procs():
    """返回「不是自己的 python 进程」列表。"""
    out = []
    for pid, exe, cmd in list_processes():
        if 'python' not in (exe or '').lower():
            continue
        if any(m in (cmd or '') for m in SELF_MARKERS):
            continue
        # 本脚本自身的 PID 及其父链不算
        if pid == os.getpid():
            continue
        out.append((pid, cmd[:160]))
    return out


def wait_quiet(quiet_seconds: float, timeout: float, poll: float = 15.0):
    """等待「外部 python 进程为空且持续 quiet_seconds 秒」。

    返回 0 = 成功进入安静窗口；3 = 超时。

    🔴🔴 **默认走 CPU 增量分类器**（MT 通知 12 §12.5）：
    别的模块的脚本**在等锁时也是活着的 python 进程** ⇒ 老判据
    「只看进程存在」会把**协作方**误判成干扰源 ⇒ **互等死锁**
    （MT 侧实测白等 1 h 41 min）⇒ 现在按 **CPU 时间增量**区分：
    「在等锁/在睡」（增量 ≈ 0）**放行**，「真在算」（增量 > 0）才算干扰。
    ⇒ 判据与实现统一在 `machine_lock_app.wait_quiet_window_cpu()`（同一份口径）。
    """
    try:
        import machine_lock_app as MLA
    except Exception:
        MLA = None
    if MLA is not None and hasattr(MLA, 'wait_quiet_window_cpu'):
        ok, _info = MLA.wait_quiet_window_cpu(
            quiet_seconds=quiet_seconds, timeout=timeout, poll=poll,
            verbose=True)
        if ok:
            return 0
        print('[quiet] 🔴 超时 %.0f s 仍未进入安静窗口 ⇒ 放弃本轮计时' % timeout,
              flush=True)
        return 3

    # ── 兜底：老实现（拿不到 machine_lock_app 时）──────────────────
    t0 = time.time()
    quiet_since = None
    while time.time() - t0 < timeout:
        ext = external_python_procs()
        if not ext:
            if quiet_since is None:
                quiet_since = time.time()
                print('[quiet] 外部 python 进程已空，开始计时安静窗口…',
                      flush=True)
            elif time.time() - quiet_since >= quiet_seconds:
                print('[quiet] ✅ 安静窗口已持续 %.0f s ⇒ 可以开始计时' %
                      quiet_seconds, flush=True)
                return 0
        else:
            if quiet_since is not None:
                print('[quiet] 安静窗口被打断（重新计时）', flush=True)
            quiet_since = None
            print('[quiet] 等待外部 python 进程结束：%d 个' % len(ext), flush=True)
            for pid, cmd in ext[:8]:
                print('        pid=%s %s' % (pid, cmd), flush=True)
        time.sleep(poll)

    print('[quiet] 🔴 超时 %.0f s 仍未进入安静窗口 ⇒ 放弃本轮计时' % timeout,
          flush=True)
    return 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quiet-seconds', type=float, default=45.0)
    ap.add_argument('--timeout', type=float, default=1800.0)
    ap.add_argument('--poll', type=float, default=15.0)
    args = ap.parse_args()
    return wait_quiet(args.quiet_seconds, args.timeout, args.poll)


if __name__ == '__main__':
    sys.exit(main())
