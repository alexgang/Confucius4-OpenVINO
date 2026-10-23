#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_close_leak.py —— 验证 `TTSService.close()` 是否会**重启 worker**（进程泄漏）。

假设：`close()` 发 quit 后 worker 退出 ⇒ stdout 关闭 ⇒ `_read_loop` 线程醒来
⇒ `self.state` 此刻仍是 'ready'（`close()` 是在 `p.wait()` **之后**才置 'idle'）
⇒ 走 `_on_worker_exit()` ⇒ **`self.start()` 重新起一个 worker**
⇒ `close()` 返回后 `self.proc` 指向**新进程**，且它永远收不到 quit
⇒ **孤儿 worker 进程泄漏**（占着 GPU/NPU + 音频输出流）。

用**桩 worker**（stub，不做任何推理）验证 ⇒ 不在 CPU 上跑真实推理。
"""
import os
import sys
import time
import json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

STUB = r'''
import sys, json, time
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
        print(json.dumps({"kind":"log","message":"stub bye"}), flush=True)
        sys.exit(0)
'''

STUB_PATH = os.path.join(HERE, '_stub_worker.py')
with open(STUB_PATH, 'w', encoding='utf-8') as f:
    f.write(STUB)

tts_service._WORKER = STUB_PATH

FAIL = []
def check(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        FAIL.append(name)

print('=' * 70)
print('TTSService.close() 进程泄漏测试（桩 worker，无推理）')
print('=' * 70)

logs = []
svc = tts_service.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc.start()
t0 = time.time()
while svc.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
print(f'state after start = {svc.state}')
check('worker 达到 ready', svc.state == 'ready')

pid_before = svc.proc.pid
print(f'worker pid (before close) = {pid_before}')

t1 = time.time()
svc.close()
elapsed = time.time() - t1
print(f'close() 用时 {elapsed:.2f}s')
print(f'logs = {logs}')

check('close() 未触发 worker 重启', svc.n_restart == 0,
      f'n_restart={svc.n_restart} logs={logs}')
check('close() 后 self.proc 为 None', svc.proc is None,
      f'proc={svc.proc}')
check('close() 后 state == idle', svc.state == 'idle', f'state={svc.state}')

# 确认旧进程真的没了
time.sleep(0.8)
rc = None
try:
    import psutil
    alive = psutil.pid_exists(pid_before)
except Exception:
    alive = None
print(f'原 pid {pid_before} 是否仍存活: {alive}')

print()
print(f'结论：{"PASS" if not FAIL else "FAIL " + str(FAIL)}')
try:
    os.remove(STUB_PATH)
except Exception:
    pass
sys.exit(0 if not FAIL else 1)
