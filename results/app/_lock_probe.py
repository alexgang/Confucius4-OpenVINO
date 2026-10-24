import ctypes, ctypes.wintypes as wt, os

LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
out = {"lock_exists": os.path.exists(LOCK)}
if out["lock_exists"]:
    txt = open(LOCK, encoding='utf-8', errors='replace').read()
    out["lock_content"] = txt
    pid = None
    for line in txt.splitlines():
        if line.lower().startswith('pid:'):
            try: pid = int(line.split(':', 1)[1].strip())
            except Exception: pid = None
    out["pid"] = pid
    if pid is None:
        out["verdict"] = "UNKNOWN_FAIL_CLOSED(ALIVE)"
    else:
        k32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if h:
            code = wt.DWORD()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            k32.CloseHandle(h)
            out["openprocess"] = "ok"
            out["get_exit_code_ok"] = bool(ok)
            out["exitcode"] = int(code.value)
            out["verdict"] = "ALIVE" if code.value == 259 else "DEAD"
        else:
            err = ctypes.get_last_error()
            out["openprocess"] = "failed"
            out["getlasterror"] = err
            out["verdict"] = "DEAD" if err == 87 else "UNKNOWN_FAIL_CLOSED(ALIVE)"
print(out)
