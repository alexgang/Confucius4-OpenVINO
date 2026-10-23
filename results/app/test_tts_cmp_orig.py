#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_cmp_orig.py —— 把**修复后**与**修复前（HEAD）**的 tts_service
放在一起跑同一套场景，判定 §21 修复是「修复」还是「回归」。

场景：
  C1 连续崩溃两次 ⇒ 应进入 error
  D  close() 后是否留下孤儿 worker

修复前的代码从 `git show HEAD:live_caption/tts_service.py` 取出。
"""
import os, sys, time, json, importlib.util, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

HERE_DIR = os.path.join(HERE, '_cmp')
os.makedirs(HERE_DIR, exist_ok=True)
CNT = os.path.join(HERE_DIR, 'count.txt')

STUB = r'''
import sys, json, os
here = os.path.dirname(os.path.abspath(__file__))
cntf = os.path.join(here, "count.txt")
mode = os.environ.get("STUB_MODE", "alive")
n = 0
if os.path.exists(cntf):
    try:
        n = int(open(cntf).read().strip() or "0")
    except Exception:
        n = 0
n += 1
with open(cntf, "w") as f:
    f.write(str(n))
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
STUB_PATH = os.path.join(HERE_DIR, 'stub.py')
with open(STUB_PATH, 'w', encoding='utf-8') as f:
    f.write(STUB)

ORIG = os.path.join(HERE, '_orig_mod', 'tts_service_orig.py')

def load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m._WORKER = STUB_PATH
    return m

def reset():
    if os.path.exists(CNT):
        os.remove(CNT)

def run_c(mod, label):
    os.environ['STUB_MODE'] = 'crash2'
    reset()
    logs = []
    svc = mod.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
    svc.start()
    t0 = time.time()
    while svc.state != 'error' and time.time() - t0 < 20:
        time.sleep(0.1)
    time.sleep(1.0)
    cnt = open(CNT).read().strip() if os.path.exists(CNT) else '?'
    print(f'  [{label}] state={svc.state} n_restart={svc.n_restart} err={svc.err} 实例启动次数={cnt}')
    print(f'  [{label}] logs={logs}')
    try:
        svc.close()
    except Exception:
        pass
    return dict(state=svc.state, n_restart=svc.n_restart, count=cnt)

def run_d(mod, label):
    os.environ['STUB_MODE'] = 'alive'
    reset()
    logs = []
    svc = mod.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
    svc.start()
    t0 = time.time()
    while svc.state not in ('ready', 'error') and time.time() - t0 < 15:
        time.sleep(0.05)
    svc.close()
    time.sleep(1.2)
    cnt = open(CNT).read().strip() if os.path.exists(CNT) else '?'
    print(f'  [{label}] close() 后实例启动次数={cnt} n_restart={svc.n_restart}')
    print(f'  [{label}] logs={logs}')
    return dict(count=cnt, n_restart=svc.n_restart, logs=logs)

print('=' * 72)
print('§21 修复前 / 修复后 对照（桩 worker，无推理）')
print('=' * 72)

orig = load('ts_orig', ORIG)
new = load('ts_new', os.path.join(REPO, 'live_caption', 'tts_service.py'))

print()
print('[场景 C] 连续崩溃两次 ⇒ 期望 state=error')
c_orig = run_c(orig, '修复前')
c_new = run_c(new, '修复后')

print()
print('[场景 D] close() ⇒ 期望不重启（实例启动次数=1）')
d_orig = run_d(orig, '修复前')
d_new = run_d(new, '修复后')

print()
print('=' * 72)
print('对照结论')
print('=' * 72)
print(f'C 场景 state: 修复前={c_orig["state"]}  修复后={c_new["state"]}')
print(f'C 场景 启动次数: 修复前={c_orig["count"]}  修复后={c_new["count"]}')
print(f'D 场景 启动次数: 修复前={d_orig["count"]}  修复后={d_new["count"]}')
print(f'D 场景 n_restart: 修复前={d_orig["n_restart"]}  修复后={d_new["n_restart"]}')

shutil.rmtree(HERE_DIR, ignore_errors=True)
