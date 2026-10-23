#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_restart_regression.py —— §21 修复的**反向验证**：

修复 `close()` 的孤儿泄漏**不能**破坏 C-101 的「worker 崩溃自动重启一次」：
- worker **异常退出**（不是 close 触发）⇒ 必须**仍然自动重启**；
- worker 连续崩两次 ⇒ 必须进入 error（不再无限重启）；
- `close()` 后再 `start()` ⇒ 必须能**正常起新 worker**（闸门要复位）。

桩 worker（stub，无推理）。用**实例计数文件**区分第几次启动
（不能用环境变量 —— 环境变量对所有实例相同）。
"""
import os, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
import tts_service  # noqa: E402

FAIL = []
def check(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        FAIL.append(name)

CNT = os.path.join(HERE, '_stub2_count.txt')
STUB = r'''
import sys, json, os
here = os.path.dirname(os.path.abspath(__file__))
cntf = os.path.join(here, "_stub2_count.txt")
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
if mode == "crash" and n <= 2:
    # 第 1、2 次启动都立刻崩溃 ⇒ 应触发「重启一次后仍失败 ⇒ error」
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
STUB_PATH = os.path.join(HERE, '_stub_worker2.py')
with open(STUB_PATH, 'w', encoding='utf-8') as f:
    f.write(STUB)
tts_service._WORKER = STUB_PATH

def reset_count():
    if os.path.exists(CNT):
        os.remove(CNT)

print('=' * 70)
print('§21 修复反向验证：崩溃重启语义未受影响（桩 worker）')
print('=' * 70)

# ── 场景 A：worker 异常退出 ⇒ 必须自动重启一次 ──────────────────────
print()
print('[A] worker 异常退出 ⇒ 应自动重启一次（重启后存活 ⇒ state=ready）')
os.environ['STUB_MODE'] = 'crash1'
reset_count()
# STUB_MODE=crash1: 只第 1 次崩
os.environ['STUB_MODE'] = 'crash1'
src = open(STUB_PATH, encoding='utf-8').read()
src = src.replace('mode == "crash" and n <= 2', 'mode == "crash1" and n <= 1')
open(STUB_PATH, 'w', encoding='utf-8').write(src)
logs = []
svc = tts_service.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc.start()
t0 = time.time()
while svc.state not in ('ready', 'error') and time.time() - t0 < 20:
    time.sleep(0.05)
time.sleep(1.5)
print('  logs =', logs)
check('A1 崩溃后 n_restart == 1', svc.n_restart == 1, f'n_restart={svc.n_restart}')
check('A2 重启后回到 ready', svc.state == 'ready', f'state={svc.state}')
check('A3 未进入 error', svc.err is None, f'err={svc.err}')
svc.close()

# ── 场景 B：close() 后再 start() ⇒ 闸门必须复位 ────────────────────
print()
print('[B] close() 后再 start() ⇒ 应能正常起新 worker（闸门复位）')
os.environ['STUB_MODE'] = 'alive'
reset_count()
logs2 = []
svc2 = tts_service.TTSService(device='STUB', voice='A', auto=False, on_log=logs2.append)
svc2.start()
t0 = time.time()
while svc2.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
check('B1 首次 start 到 ready', svc2.state == 'ready', f'state={svc2.state}')
svc2.close()
check('B2 close 后 _closing 已复位', svc2._closing is False, f'_closing={svc2._closing}')
svc2.start()
t0 = time.time()
while svc2.state not in ('ready', 'error') and time.time() - t0 < 15:
    time.sleep(0.05)
check('B3 二次 start 仍能到 ready', svc2.state == 'ready', f'state={svc2.state}')
check('B4 二次 start 后 n_restart 仍为 0', svc2.n_restart == 0, f'n_restart={svc2.n_restart}')
svc2.close()

# ── 场景 C：连续崩溃两次 ⇒ 进入 error（不无限重启）─────────────────
print()
print('[C] worker 崩溃 ⇒ 重启后的 worker 再崩 ⇒ 应进入 error')
src = open(STUB_PATH, encoding='utf-8').read()
src = src.replace('mode == "crash1" and n <= 1', 'mode == "crash" and n <= 2')
open(STUB_PATH, 'w', encoding='utf-8').write(src)
os.environ['STUB_MODE'] = 'crash'
reset_count()
logs3 = []
svc3 = tts_service.TTSService(device='STUB', voice='A', auto=False, on_log=logs3.append)
svc3.start()
t0 = time.time()
while svc3.state != 'error' and time.time() - t0 < 25:
    time.sleep(0.1)
print('  logs =', logs3)
print('  实例启动次数 =', open(CNT).read().strip())
check('C1 最终 state == error', svc3.state == 'error', f'state={svc3.state}')
check('C2 err 有值', svc3.err is not None, f'err={svc3.err}')
check('C3 n_restart == 1（只重启一次）', svc3.n_restart == 1, f'n_restart={svc3.n_restart}')
svc3.close()

print()
print(f'结论：{"PASS" if not FAIL else "FAIL " + str(FAIL)}')
for f_ in (STUB_PATH, CNT):
    try:
        os.remove(f_)
    except Exception:
        pass
sys.exit(0 if not FAIL else 1)
