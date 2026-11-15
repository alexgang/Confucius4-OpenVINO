#!/bin/bash
# _app583_locked_run.sh —— **持 MACHINE_LOCK** 跑一个长作业（10 分钟整链）。
#
# 用法： bash _app583_locked_run.sh <py脚本名> <日志名> <pid文件名>
#
# 🔴 锁规则（跨模块共用设备）：
#   · 锁文件 C:/Users/Trekker-PTL/shared/MACHINE_LOCK，内容 =「模块名 PID 开始时间」；
#   · **锁已存在就等待**（不抢锁）；等之前先判断锁里的 PID 是否真死
#     （ctypes OpenProcess + GetExitCodeProcess）—— **探测失败一律视为存活**；
#   · 259 = STILL_ACTIVE ⇒ **仍存活**（0 才是死）⇒ 不可回收；
#   · 收尾回收锁前**再验一次**自己的 PID。
# 🔴 **不删任何东西**（本机安全删除 shim 会失败）⇒ 锁文件用 `rm -f` 删单个文件。
set -u
LOCK="C:/Users/Trekker-PLT_TMP"
LOCK="C:/Users/Trekker-PTL/shared/MACHINE_LOCK"
RES="C:/Users/Trekker-PTL/confucius4-openvino/results/app"
PY="C:/Users/Trekker-PTL/.workbuddy/binaries/python/versions/3.13.12/python.exe"

SCRIPT="$1"; LOG="$2"; PIDFILE="$3"
if [ -z "$SCRIPT" ] || [ -z "$LOG" ] || [ -z "$PIDFILE" ]; then
  echo "用法: bash _app583_locked_run.sh <py脚本> <日志> <pid文件>"
  exit 2
fi

# ── 取锁（等，不抢）──
"$PY" - "$LOCK" <<'PYEOF'
import ctypes, os, sys, time
from ctypes import wintypes
LOCK = sys.argv[1]
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k.OpenProcess.restype = wintypes.HANDLE

def alive(pid):
    h = k.OpenProcess(0x1000, False, pid)
    err = ctypes.get_last_error()
    if not h:
        return None, err          # None = 探测失败 ⇒ 视为存活
    code = wintypes.DWORD()
    k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return (code.value == 259), 0

for attempt in range(160):        # 最多等 160 * 10 s = 26 min
    if not os.path.exists(LOCK):
        break
    txt = open(LOCK, encoding='utf-8', errors='replace').read().strip()
    parts = txt.split()
    pid = None
    for p in parts:
        if p.isdigit():
            pid = int(p); break
    if pid:
        st, err = alive(pid)
        if st is False:
            print('锁里的 PID %d 已死 ⇒ 回收陈旧锁' % pid, flush=True)
            os.remove(LOCK)
            break
        if st is None:
            print('锁里的 PID %d 探测失败(err=%s) ⇒ 视为存活，继续等' % (pid, err),
                  flush=True)
    else:
        print('锁内容无法解析（%r）⇒ 视为存活，继续等' % txt[:80], flush=True)
    print('锁存在，等待中（%d/160）：%s' % (attempt, txt[:80]), flush=True)
    time.sleep(10)
else:
    print('等待超时 ⇒ 不抢锁，放弃本次作业', flush=True)
    sys.exit(11)
PYEOF
if [ $? -ne 0 ]; then
  echo "取锁失败 ⇒ 退出"
  exit 11
fi

echo "app $$ $(date '+%Y-%m-%d %H:%M:%S')" > "$LOCK"
echo $$ > "$RES/$PIDFILE"
echo "已取锁：$(cat "$LOCK")"

"$PY" "$RES/$SCRIPT" > "$RES/$LOG" 2>&1
rc=$?
echo "exit=$rc" >> "$RES/$LOG"

# ── 回收锁：先验 PID 真死 ──
"$PY" - "$LOCK" "$RES/$PIDFILE" <<'PYEOF'
import ctypes, os, sys
from ctypes import wintypes
LOCK = sys.argv[1]; PIDFILE = sys.argv[2]
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k.OpenProcess.restype = wintypes.HANDLE
pid = int(open(PIDFILE).read().strip())
h = k.OpenProcess(0x1000, False, pid)
err = ctypes.get_last_error()
if h:
    code = wintypes.DWORD()
    k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    if code.value == 259:
        print('锁：PID 仍存活 ⇒ 保留')
    else:
        os.remove(LOCK); print('锁：PID 已退出 ⇒ 已回收')
else:
    if err == 87:
        os.remove(LOCK); print('锁：PID 不存在(err=87) ⇒ 已回收')
    else:
        print('锁：探测失败 err=%s ⇒ 视为存活，保留' % err)
PYEOF
exit $rc
