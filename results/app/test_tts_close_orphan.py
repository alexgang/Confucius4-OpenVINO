#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_close_orphan.py —— 确认 `close()` 后是否留下**孤儿 worker 进程**。

桩 worker 会把自己的 PID 写进一个 pidfile，方便事后核对存活情况。
"""
import os, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
import tts_service  # noqa: E402

PIDFILE = os.path.join(HERE, '_stub_pids.txt')
STUB = r'''
import sys, json, os
pidfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_stub_pids.txt")
with open(pidfile, "a", encoding="utf-8") as f:
    f.write(str(os.getpid()) + "\n")
print(json.dumps({"kind":"ready","device":"STUB","voice":"A"}), flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if msg.get("cmd") == "quit":
        sys.exit(0)
'''
STUB_PATH = os.path.join(HERE, '_stub_worker.py')
with open(STUB_PATH, 'w', encoding='utf-8') as f:
    f.write(STUB)
if os.path.exists(PIDFILE):
    os.remove(PIDFILE)
tts_service._WORKER = STUB_PATH

def alive(pid):
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except Exception:
        return None

logs = []
svc = tts_service.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc.start()
t0 = time.time()
while svc.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
print('state =', svc.state)
pid1 = svc.proc.pid
print('worker#1 pid =', pid1)

svc.close()
time.sleep(1.5)

pids = [int(x) for x in open(PIDFILE).read().split() if x.strip()]
print('桩 worker 起过的 pid 列表 =', pids)
for p in pids:
    print(f'  pid {p} alive={alive(p)}')

orphans = [p for p in pids if p != pid1 and alive(p)]
print()
print(f'close() 后新起的 worker 数 = {len(pids) - 1}')
print(f'其中仍存活的孤儿 = {orphans}')
print(f'n_restart = {svc.n_restart}')
print(f'self.proc = {svc.proc}')
print()
print('结论：' + ('FAIL —— 存在孤儿 worker 进程泄漏' if orphans else 'PASS —— 无孤儿'))

# 清理孤儿
import subprocess, signal
for p in orphans:
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(p)], capture_output=True)
    except Exception:
        pass
try:
    os.remove(STUB_PATH)
except Exception:
    pass
sys.exit(1 if orphans else 0)
