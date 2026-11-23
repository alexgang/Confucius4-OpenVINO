"""Reclaim a stale bgkeep machine lock, with PROOF that the owner is dead.

Two evidence paths, in order:
  A) an owner PID file exists (shared/bgkeep/.e2e_owner.pid) -> use the project
     dead test: ctypes OpenProcess + GetExitCodeProcess.
       - OpenProcess err == 87 (ERROR_INVALID_PARAMETER) -> PID does not exist -> DEAD
       - OpenProcess succeeds -> GetExitCodeProcess: 259 = STILL_ACTIVE -> ALIVE
       - any probe failure -> treat as ALIVE (fail-closed)
  B) no PID file (older run) -> APP-127-style three-condition check:
       1) lock content starts with "app bgkeep e2e"
       2) ports 8765/8766 have no listener
       3) no python process running ext.bridge / bgkeep_e2e.py
     All three must hold.

Never uses tasklist /FI (Git Bash treats it as a path -- it once caused another
module's live lock to be reclaimed).
"""
import ctypes
import ctypes.wintypes as wt
import os
import socket
import subprocess
import sys

LOCK = r"C:\Users\Trekker-PTL\shared\MACHINE_LOCK"
PIDFILE = r"C:\Users\Trekker-PTL\shared\bgkeep\.e2e_owner.pid"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype = wt.HANDLE
GetExitCodeProcess = kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
GetExitCodeProcess.restype = wt.BOOL
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def probe_pid(pid):
    """-> (alive: bool|None, evidence: str)"""
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    err = ctypes.get_last_error()
    if not h:
        if err == 87:
            return False, "OpenProcess err=87 (ERROR_INVALID_PARAMETER) => PID %d does not exist => DEAD" % pid
        return None, "OpenProcess failed err=%d => probe failure => treat as ALIVE" % err
    code = wt.DWORD()
    if not GetExitCodeProcess(h, ctypes.byref(code)):
        return None, "GetExitCodeProcess failed => probe failure => treat as ALIVE"
    if code.value == STILL_ACTIVE:
        return True, "exit code 259 (STILL_ACTIVE) => ALIVE"
    return False, "exit code %d => DEAD" % code.value


def port_free(port):
    for fam, typ in ((socket.AF_INET, socket.SOCK_STREAM),):
        s = socket.socket(fam, typ)
        try:
            s.settimeout(1.0)
            s.connect(("127.0.0.1", port))
            s.close()
            return False
        except OSError:
            pass
        finally:
            try:
                s.close()
            except OSError:
                pass
    return True


def python_procs():
    """Enumerate running python.exe processes (existence only).

    APP-127 only requires "no live_dub_ext ext.bridge / bgkeep_e2e.py python
    process for 10 minutes" and explicitly says "只看进程存在与否，不打印完整命令行".
    `wmic` is unavailable on this machine, so use the Toolhelp32 snapshot via
    ctypes. We cannot see the command line, so we apply the CONSERVATIVE rule:
    if ANY python.exe is running we treat the lock as held (alive).
    """
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
            ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
            ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_char * 260),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateToolhelp32Snapshot = k32.CreateToolhelp32Snapshot
    CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    CreateToolhelp32Snapshot.restype = wt.HANDLE
    Process32First = k32.Process32First
    Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    Process32First.restype = wt.BOOL
    Process32Next = k32.Process32Next
    Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    Process32Next.restype = wt.BOOL
    CloseHandle = k32.CloseHandle
    CloseHandle.argtypes = [wt.HANDLE]
    CloseHandle.restype = wt.BOOL

    snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1 or snap == 0xFFFFFFFF:
        return None, "CreateToolhelp32Snapshot failed err=%d" % ctypes.get_last_error()
    pe = PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
    me = os.getpid()
    found = []
    try:
        ok = Process32First(snap, ctypes.byref(pe))
        while ok:
            name = pe.szExeFile.decode("ascii", "replace")
            pid = int(pe.th32ProcessID)
            # exclude this probe process itself
            if name.lower() == "python.exe" and pid != me:
                found.append(pid)
            ok = Process32Next(snap, ctypes.byref(pe))
    finally:
        CloseHandle(snap)
    return found, ""


if not os.path.exists(LOCK):
    print("RESULT: no lock present")
    sys.exit(0)

content = open(LOCK, encoding="utf-8", errors="replace").read()
print("lock content: %r" % content)

if not content.startswith("app bgkeep e2e"):
    print("RESULT: lock is not ours -> NOT removing")
    sys.exit(3)

alive = None
evidence = []

if os.path.exists(PIDFILE):
    try:
        pid = int(open(PIDFILE, encoding="ascii").read().strip())
        print("owner pid file -> %d" % pid)
        alive, ev = probe_pid(pid)
        evidence.append(ev)
        print("  %s" % ev)
    except Exception as e:  # noqa: BLE001
        alive, ev = None, "pid file unreadable: %s => treat as ALIVE" % e
        evidence.append(ev)
        print("  %s" % ev)
else:
    print("no owner pid file -> APP-127-style three-condition check")
    p1 = port_free(8765) and port_free(8766)
    evidence.append("ports 8765/8766 free = %s" % p1)
    print("  %s" % evidence[-1])
    procs, perr = python_procs()
    if procs is None:
        alive, ev = None, "process probe failed: %s => treat as ALIVE" % perr
    else:
        p2 = (len(procs) == 0)
        evidence.append("no python.exe process running = %s (%d found: %s)"
                        % (p2, len(procs), procs))
        print("  %s" % evidence[-1])
        p3 = content.startswith("app bgkeep e2e")
        evidence.append("lock content is ours = %s" % p3)
        if p1 and p2 and p3:
            alive = False
            ev = "all three conditions hold => DEAD"
        else:
            alive = True
            ev = "conditions not all met => treat as ALIVE"
        evidence.append(ev)
        print("  %s" % ev)

# 🔴 fail-CLOSED: only an explicit False (proven dead) may reclaim.
# `None` means "probe failed" => treat as alive => keep the lock.
if alive is not False:
    print("RESULT: lock NOT reclaimed (owner not proven dead)")
    sys.exit(2)

os.remove(LOCK)
print("RESULT: lock removed (stale, owner proven dead)")
print("EVIDENCE:")
for e in evidence:
    print("  -", e)
