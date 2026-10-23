#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §21 验收（客户包版）：对**客户包内**的 `tts_service.py` 跑同一套生命周期断言。

为什么单独跑一遍：
  仓库 ⇄ 客户包是两份独立副本 ⇒ 「仓库里测过」**不等于**「包里的那份是对的」
  （长期记忆铁律 + C-138 事故教训）。

断言：
  L1 close() 后**不留孤儿 worker**（实例启动次数 = 1，孤儿数 = 0）
  L2 close() **不触发**自动重启（n_restart == 0）
  L3 worker 崩溃 ⇒ **真的自动重启**（实例启动次数 = 2）
  L4 连续崩溃两次 ⇒ state == 'error'，err 有值
  L5 close() 后再 start() ⇒ 闸门复位，能正常起新 worker

🔴 不跑真 TTS 推理（桩 worker，纯 stdio）⇒ 不在 CPU 上跑推理。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import time

PKG_APP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4\app'
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, '_pkg_lifecycle')
os.makedirs(WORK, exist_ok=True)
CNT = os.path.join(WORK, 'count.txt')

STUB = r'''
import sys, json, os
here = os.path.dirname(os.path.abspath(__file__))
cntf = os.path.join(here, "count.txt")
mode = os.environ.get("STUB_MODE", "alive")
n = 0
if os.path.exists(cntf):
    try: n = int(open(cntf).read().strip() or "0")
    except Exception: n = 0
n += 1
open(cntf, "w").write(str(n))
if mode == "crash2" and n <= 2:
    print(json.dumps({"kind":"ready","device":"STUB","voice":"A"}), flush=True)
    os._exit(7)
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
STUB_PATH = os.path.join(WORK, 'stub.py')
with open(STUB_PATH, 'w', encoding='utf-8') as f:
    f.write(STUB)

TARGET = os.path.join(PKG_APP, 'tts_service.py')
if not os.path.isfile(TARGET):
    raise SystemExit(f'!! 客户包内找不到 {TARGET}')
spec = importlib.util.spec_from_file_location('ts_pkg', TARGET)
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)
ts._WORKER = STUB_PATH

FAIL = []
def check(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        FAIL.append(name)

def reset():
    if os.path.exists(CNT):
        os.remove(CNT)

def count():
    return open(CNT).read().strip() if os.path.exists(CNT) else '0'

print('=' * 72)
print(f'APP §21 客户包验收：{TARGET}')
print('=' * 72)

# ── L1/L2：close() 不留孤儿、不重启 ───────────────────────────────────
print()
print('[L1/L2] close() ⇒ 不重启、不留孤儿')
os.environ['STUB_MODE'] = 'alive'
reset()
logs = []
svc = ts.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc.start()
t0 = time.time()
while svc.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
check('L0 worker 到 ready', svc.state == 'ready', f'state={svc.state}')
svc.close()
time.sleep(1.2)
n_started = int(count())
check('L1 close() 后 worker 实例启动次数 == 1', n_started == 1, f'count={n_started}')
check('L2 close() 未触发自动重启', svc.n_restart == 0, f'n_restart={svc.n_restart}')
check('L2b close() 后 self.proc is None', svc.proc is None, f'proc={svc.proc}')

# ── L3：崩溃 ⇒ 真的自动重启 ──────────────────────────────────────────
print()
print('[L3] worker 崩溃 ⇒ 应真的自动重启')
os.environ['STUB_MODE'] = 'crash2'
reset()
logs = []
svc = ts.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc.start()
t0 = time.time()
while svc.state != 'error' and time.time() - t0 < 20:
    time.sleep(0.1)
time.sleep(0.8)
n_started = int(count())
print(f'  logs = {logs}')
check('L3 worker 实例启动次数 == 2（真的重启了）', n_started == 2, f'count={n_started}')
check('L3b n_restart == 1', svc.n_restart == 1, f'n_restart={svc.n_restart}')

# ── L4：连续崩两次 ⇒ error ───────────────────────────────────────────
print()
print('[L4] 连续崩溃两次 ⇒ state == error')
check('L4 state == error', svc.state == 'error', f'state={svc.state}')
check('L4b err 有值', svc.err is not None, f'err={svc.err}')

# ── L5：close() 后再 start() ⇒ 闸门复位 ──────────────────────────────
print()
print('[L5] close() 后再 start() ⇒ 闸门复位')
os.environ['STUB_MODE'] = 'alive'
reset()
svc2 = ts.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc2.start()
t0 = time.time()
while svc2.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
check('L5a 首次 start 到 ready', svc2.state == 'ready', f'state={svc2.state}')
svc2.close()
check('L5b close 后 _closing 已复位', svc2._closing is False, f'_closing={svc2._closing}')
svc2.start()
t0 = time.time()
while svc2.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
check('L5c 二次 start 到 ready', svc2.state == 'ready', f'state={svc2.state}')
svc2.close()

print()
print(f'结论：{"PASS" if not FAIL else "FAIL " + str(FAIL)}')
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(0 if not FAIL else 1)
