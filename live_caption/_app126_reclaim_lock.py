"""Reclaim the App bgkeep e2e v5 machine lock, but only after PROVING the owner is dead.

Rule (project discipline):
  * the dead test is ctypes OpenProcess + GetExitCodeProcess (never tasklist /FI)
  * OpenProcess err == 87 (ERROR_INVALID_PARAMETER) => the PID does not exist => dead
  * any probe failure => treat as ALIVE => do NOT reclaim
  * OpenProcess succeeds => GetExitCodeProcess: 259 = STILL_ACTIVE => ALIVE (do not reclaim)

This lock was created by THIS session's own run (content starts with "app bgkeep e2e v5"),
and the owning PowerShell PID was 29456. The background task was killed by the tool
timeout, so its finally block never released the lock.
"""
import ctypes
import ctypes.wintypes as wt
import os

LOCK = r"C:\Users\Trekker-PTL\shared\MACHINE_LOCK"
OWNER_PID = 29456

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype = wt.HANDLE

GetExitCodeProcess = kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
GetExitCodeProcess.restype = wt.BOOL

STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, OWNER_PID)
err = ctypes.get_last_error()
print("OpenProcess(handle=%s) err=%d" % (h, err))

alive = None
if not h:
    if err == 87:
        print("=> PID %d does not exist (err=87) => DEAD" % OWNER_PID)
        alive = False
    else:
        print("=> probe failed (err=%d) => treat as ALIVE" % err)
        alive = True
else:
    code = wt.DWORD()
    ok = GetExitCodeProcess(h, ctypes.byref(code))
    if not ok:
        print("=> GetExitCodeProcess failed => treat as ALIVE")
        alive = True
    else:
        print("=> exit code = %d" % code.value)
        alive = (code.value == STILL_ACTIVE)
        print("=> %s" % ("ALIVE (STILL_ACTIVE)" if alive else "DEAD"))

if alive:
    print("RESULT: lock NOT reclaimed (owner considered alive)")
    raise SystemExit(2)

# owner is dead -> safe to reclaim our own lock
if os.path.exists(LOCK):
    content = open(LOCK, encoding="utf-8", errors="replace").read()
    print("lock content: %r" % content)
    if not content.startswith("app bgkeep e2e"):
        print("RESULT: lock is NOT ours -> NOT removing")
        raise SystemExit(3)
    os.remove(LOCK)
    print("RESULT: lock removed (own stale lock, owner proven dead)")
else:
    print("RESULT: lock already absent")
