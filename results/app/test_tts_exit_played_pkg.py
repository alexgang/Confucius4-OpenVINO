#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_exit_played.py —— §30 的**验收 + 反证**脚本。

## 本轮修的两个缺陷（都在 `live_caption/tts_service.py`）

### 缺陷 ①：`played` 事件对**已被丢弃**的句子仍 `n_played += 1` ⇒ **双记**

`submit()` → `_update_backlog()` 因积压超限丢弃该句（`n_dropped += 1`，
并给 worker 发 `cancel`）。但 worker 的 `synth()` 线程**可能已经越过
自己的取消检查**（`tts_worker.py` L537）⇒ 合成完成 ⇒ 仍然 `emit('played')`。

主进程收到这个 `played` 时（旧实现）**无条件** `self.n_played += 1`
⇒ 同一句被**丢了又播** ⇒ `n_played + n_dropped` 比 `n_submitted` **多 1**
⇒ 破坏 §29 建立的**「每句恰好算一次」不变式**。

🔴 真实后果：GUI/CLI 底栏的「丢句 / 已播」两个数**加起来超过提交数**
⇒ 用户看到的统计自相矛盾；`drain()` 的判定 `n_done >= n_sub` 也失去意义。

### 缺陷 ②：「已重启过一次仍崩溃」分支 ⇒ **不清 pending** ⇒ `drain()` 必超时

`_on_worker_exit()` 的第一个分支：

```python
if self._restarted:
    self.state = 'error'
    self.err = RuntimeError(...)
    return          # ← 直接返回，pending / _inflight / _queue 全都没清
```

此时 worker **不会再重启**（判死）⇒ 所有「已下发未回结果」的句子
**永远等不到 `played`/`error`** ⇒ `pending` 永久悬挂
⇒ `drain()` 必定超时（GUI 白等 30 s / CLI 白等 120 s）
⇒ 同时 `n_played + n_dropped != n_submitted`（少算）。

（对比：§21/§22/§29 只修了「第一次崩溃」路径，**第二次崩溃**路径漏了。）

## 判定口径

- **REAL** 组：修复后必须全 PASS；
- **BUG** 组：每条都在**断言「缺陷仍然存在」**
  ⇒ 修复前命中（缺陷复现 = 反证证据）⇒ 修复后必须**全部落空**；
- 总判定 = REAL 全过 **且** BUG 全落空。

## 关键不变式

> **每一句提交过的句子必须被恰好统计一次**
> ⇒ `n_played + n_dropped == n_submitted`。

## 本脚本测什么（**桩 worker，不在 CPU 上跑推理**）

- REAL-1 第二次崩溃 ⇒ `pending` 清空、`_inflight` 清空
- REAL-2 第二次崩溃 ⇒ 不变式成立
- REAL-3 第二次崩溃 ⇒ `drain()` 能排空（不超时）
- REAL-4 「丢了又播」的句子只算一次（且算作**已播**）
- BUG-1/BUG-2 反证：缺陷②（pending 悬挂 + drain 超时 + 少算）
- BUG-3 反证：缺陷①（双记 ⇒ sum > submitted）

用法
----
    python results/app/test_tts_exit_played.py
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
import sys as _sys
_sys.path.insert(0, r'C:\Users\Trekker-PTL\confucius4-openvino')
import pkg_paths as _pkg_paths

# 🔴🔴 §48：**不写死包版本** ⇒ 自动发现最大版本（`pkg_paths` 单一数据源）
REPO = _pkg_paths.pkg_app_dir()
sys.path.insert(0, REPO)

import tts_service  # noqa: E402

REAL_FAIL = []
BUG_HIT = []
EVIDENCE = {}

STUB_ALIVE = os.path.join(HERE, '_stub_exit_worker.py')
CNT_FILE = os.path.join(HERE, '_stub_exit_count.txt')

# ── 桩 worker A：**前两次启动会崩溃**（第 3 次起常驻）────────────────────
# 用**实例计数文件**区分第几次启动（环境变量对所有实例相同，不可靠）。
STUB_CRASH_TWICE = r'''
import sys, json, os, time
here = os.path.dirname(os.path.abspath(__file__))
cntf = os.path.join(here, "_stub_exit_count.txt")
n = 0
if os.path.exists(cntf):
    try:
        n = int(open(cntf).read().strip() or "0")
    except Exception:
        n = 0
n += 1
with open(cntf, "w") as f:
    f.write(str(n))
sys.stdout.write(json.dumps({"kind": "ready", "device": "STUB", "voice": "A"}) + "\n")
sys.stdout.flush()
if n <= 2:
    # 前两次启动：起来就崩（模拟「模型加载后立刻挂」）
    time.sleep(0.6)
    os._exit(9)
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
    if msg.get("cmd") == "synth":
        # 故意**不**回 played ⇒ 句子永远在途
        pass
while True:
    time.sleep(0.2)
'''

# ── 桩 worker B：**无视 cancel**，合成完照样回 `played` ────────────────
# 用来复现缺陷①：主进程已按积压丢弃（并发了 cancel），
# 但 worker 仍然把这句话播了出来 ⇒ 主进程「丢了 + 播了」双记。
STUB_IGNORE_CANCEL = r'''
import sys, json, os, time
sys.stdout.write(json.dumps({"kind": "ready", "device": "STUB", "voice": "A"}) + "\n")
sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    cmd = msg.get("cmd")
    if cmd == "quit":
        sys.exit(0)
    if cmd == "cancel":
        # 🔴 **故意无视 cancel** ⇒ 模拟「worker 已越过自己的取消检查」
        continue
    if cmd == "synth":
        time.sleep(0.35)
        sys.stdout.write(json.dumps({"kind": "played", "id": msg.get("id")}) + "\n")
        sys.stdout.flush()
while True:
    time.sleep(0.2)
'''


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


def bug(name, cond, detail=''):
    """断言「缺陷仍然存在」——命中 = 缺陷复现（反证证据）。"""
    print(f"  [{'BUG ' if cond else 'gone'}] {name}" + (f' — {detail}' if detail else ''))
    if cond:
        BUG_HIT.append(name)


def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def wait_for(fn, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False


def reset_count():
    if os.path.exists(CNT_FILE):
        os.remove(CNT_FILE)


def main():
    old_max = tts_service.BACKLOG_MAX_S

    print('=' * 72)
    print('§30 修复验收：第二次崩溃清理 pending + 「丢了又播」不双记')
    print('（桩 worker，无推理；不跑测速、不占 GPU）')
    print('=' * 72)

    # ── [A] 连续崩溃两次 ⇒ pending 必须清干净、drain 必须能排空 ────────
    print()
    print('[A] worker 连续崩溃两次 ⇒ 第二次崩溃后不得留下悬挂句子')
    with open(STUB_ALIVE, 'w', encoding='utf-8') as f:
        f.write(STUB_CRASH_TWICE)
    reset_count()
    tts_service._WORKER = STUB_ALIVE

    logs_a = []
    svc = tts_service.TTSService(device='STUB', voice='A', auto=False,
                                 on_log=logs_a.append)
    svc.start()
    real('A0 首次到 ready', wait_state(svc, ('ready',)), f'state={svc.state}')

    # 🔴 本组要测「崩溃清理」，**不能**被积压丢句干扰 ⇒ 抬高阈值
    tts_service.BACKLOG_MAX_S = 999.0
    for i in range(3):
        svc.submit('第一次崩溃前提交的第 %d 句，这句话写得比较长' % i, seg=i)
    wait_for(lambda: len(svc.pending) >= 3)
    real('A1 3 句在途（worker 不回 played）', len(svc.pending) == 3,
         f'pending={list(svc.pending)}')

    # 等第 1 次崩溃 ⇒ 触发重启
    real('A2 第一次崩溃后已重启一次',
         wait_for(lambda: svc.n_restart >= 1 and svc.state == 'ready', 30),
         f'n_restart={svc.n_restart} state={svc.state}')

    # 第 2 次启动：再提交几句，等它再崩 ⇒ 走「已重启过一次」分支
    for i in range(2):
        svc.submit('第二次崩溃前提交的第 %d 句，这句话写得比较长' % i, seg=100 + i)
    wait_for(lambda: len(svc.pending) >= 2)
    real('A3 第 2 次崩溃后进入 error（不再重启）',
         wait_for(lambda: svc.state == 'error', 30),
         f'state={svc.state} err={svc.err} n_restart={svc.n_restart}')
    time.sleep(0.6)

    n_sub = svc.n_submitted
    pending_left = len(svc.pending)
    inflight_left = len(svc._inflight)
    accounted = svc.n_played + svc.n_dropped

    bug('A4 反证·缺陷②：第二次崩溃后 pending 仍有悬挂句子', pending_left > 0,
        f'pending={list(svc.pending)}')
    real('A5 缺陷②已修：pending 已清空', pending_left == 0,
         f'pending={list(svc.pending)}')
    real('A6 缺陷②已修：_inflight 已清空', inflight_left == 0,
         f'inflight={sorted(svc._inflight)}')
    bug('A7 反证·缺陷②：不变式被破坏（少算）', accounted != n_sub,
        f'played={svc.n_played} dropped={svc.n_dropped} sum={accounted} '
        f'submitted={n_sub}')
    real('A8 缺陷②已修：不变式成立（每句恰好算一次）', accounted == n_sub,
         f'played={svc.n_played} dropped={svc.n_dropped} sum={accounted} '
         f'submitted={n_sub}')

    t_drain = time.time()
    drained = svc.drain(timeout=8.0)
    drain_s = time.time() - t_drain
    bug('A9 反证·缺陷②：drain 超时返回 False', not drained,
        f'drained={drained} 用时 {drain_s:.1f}s')
    real('A10 缺陷②已修：drain 能排空（不超时）', drained,
         f'drained={drained} 用时 {drain_s:.1f}s')

    EVIDENCE['A'] = dict(n_submitted=n_sub, n_played=svc.n_played,
                         n_dropped=svc.n_dropped, accounted=accounted,
                         pending_left=pending_left, inflight_left=inflight_left,
                         drained=drained, drain_s=round(drain_s, 2),
                         n_restart=svc.n_restart, state=svc.state)
    try:
        svc.close()
    except Exception:
        pass

    # ── [B] 「丢了又播」⇒ 只能算一次 ───────────────────────────────────
    print()
    print('[B] 句子被积压丢弃后 worker 仍播了出来 ⇒ 不得双记')
    stub_b = os.path.join(HERE, '_stub_ignore_cancel.py')
    with open(stub_b, 'w', encoding='utf-8') as f:
        f.write(STUB_IGNORE_CANCEL)
    tts_service._WORKER = stub_b

    logs_b = []
    svc2 = tts_service.TTSService(device='STUB', voice='A', auto=False,
                                  on_log=logs_b.append)
    svc2.start()
    real('B0 worker 到 ready', wait_state(svc2, ('ready',)), f'state={svc2.state}')

    # 🔴 本组要测「双记」，**不能**被其它丢句路径干扰 ⇒ 先抬高阈值提交，
    #    再单独调低阈值触发积压丢句。
    tts_service.BACKLOG_MAX_S = 999.0
    svc2.submit('这句会被积压丢弃但 worker 照样会播出来', seg=0)
    wait_for(lambda: len(svc2.pending) >= 1)
    real('B1 句子已在途', len(svc2.pending) == 1,
         f'pending={list(svc2.pending)} inflight={sorted(svc2._inflight)}')

    # 调低阈值 ⇒ 触发积压丢句（主进程计一次丢句）
    tts_service.BACKLOG_MAX_S = 1.0
    svc2._update_backlog()
    time.sleep(0.3)
    real('B2 已发生丢句（n_dropped == 1）', svc2.n_dropped == 1,
         f'n_dropped={svc2.n_dropped} pending={list(svc2.pending)}')

    # 等 worker 把「无视 cancel」的那句播出来 ⇒ 主进程收到 played
    wait_for(lambda: svc2.n_played >= 1, 10)
    time.sleep(0.3)
    n_sub2 = svc2.n_submitted
    sum2 = svc2.n_played + svc2.n_dropped
    bug('B3 反证·缺陷①：同一句既记丢又记播（双记）', sum2 > n_sub2,
        f'played={svc2.n_played} dropped={svc2.n_dropped} sum={sum2} '
        f'submitted={n_sub2}')
    real('B4 缺陷①已修：每句恰好算一次（sum == submitted）', sum2 == n_sub2,
         f'played={svc2.n_played} dropped={svc2.n_dropped} sum={sum2} '
         f'submitted={n_sub2}')
    real('B5 缺陷①已修：确实播出来了 ⇒ 记作「已播」而非「丢弃」',
         svc2.n_played == 1 and svc2.n_dropped == 0,
         f'played={svc2.n_played} dropped={svc2.n_dropped}')
    real('B6 pending 已清空', len(svc2.pending) == 0,
         f'pending={list(svc2.pending)}')

    EVIDENCE['B'] = dict(n_submitted=n_sub2, n_played=svc2.n_played,
                         n_dropped=svc2.n_dropped, sum=sum2,
                         pending_left=len(svc2.pending))
    try:
        svc2.close()
    except Exception:
        pass

    tts_service.BACKLOG_MAX_S = old_max

    ev = os.path.join(HERE, 'test_tts_exit_played_evidence.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, bug_hit=BUG_HIT,
                       evidence=EVIDENCE), f, ensure_ascii=False, indent=2)
    print(f'\n证据已落盘: {ev}')

    print()
    print('=' * 72)
    ok = (not REAL_FAIL) and (not BUG_HIT)
    print(f'REAL 未通过：{REAL_FAIL if REAL_FAIL else "无"}')
    print(f'BUG 仍命中（应为无）：{BUG_HIT if BUG_HIT else "无"}')
    print(f'结论：{"PASS" if ok else "FAIL"}')
    print('=' * 72)
    for f_ in (STUB_ALIVE, CNT_FILE, stub_b):
        try:
            os.remove(f_)
        except OSError:
            pass
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
