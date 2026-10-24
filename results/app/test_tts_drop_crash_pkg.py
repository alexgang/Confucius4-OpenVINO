#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_drop_crash_pkg.py —— §29 修复在**客户包内那份**上的独立验收。

## 缺陷（§29 修）

### 缺陷 ①：`_update_backlog()` 丢句后 `_inflight` **不注销** ⇒ 泄漏 + 崩溃时计数双记

`tts_service.TTSService._update_backlog()` 因积压超限丢弃最旧的未播句时：

```python
for jid in drop_ids:
    self.pending.pop(jid, None)      # ← 只清了 pending，_inflight 没清
...
for jid in drop_ids:
    self._send({'cmd': 'cancel', 'id': jid})
self.n_dropped += len(drop_ids)      # ← 这里已经计过一次丢句
```

但 **`self._inflight` 里这些 jid 没有被 `discard`** ⇒

1. **`_inflight` 集合无界增长**（每丢一句就多一个常驻 int）
   ⇒ 长时间会议下内存单调增长；
2. 🔴🔴 **worker 崩溃时丢句被**双记**：`§22` 引入的 `_on_worker_exit()` 会
   `lost = sorted(self._inflight)` ⇒ 把**早已被丢弃**的句子再算一次。

**实测反证**：提交 8 句 → 积压丢弃 1 句（`n_dropped=1`）→ 杀 worker
⇒ 修复前 `n_dropped` 变成 **9**（真实丢 8 句，却统计成 9）
⇒ **破坏「每句只算一次」的不变式**。

### 缺陷 ②：`cancel()` 也不从 `_inflight` 注销

`tts_service.TTSService.cancel()` 同样只 `pending.pop(jid, None)`，
`_inflight` 里的 jid 留着 ⇒ 与缺陷 ① 同源。

### 缺陷 ③：`_send()` 写 stdin 失败 ⇒ **句子永久挂在 `_inflight`**

`_send()` 捕获异常后**只记日志**、**不返回成败** ⇒ 调用方
（`submit()` / `_flush_queue()`）以为命令已下发 ⇒ 登记了 `_inflight`
⇒ 但 worker 永远收不到 ⇒ `pending[jid]` 与 `_inflight` 永久悬挂
⇒ `drain()` 必超时（GUI 30 s / CLI 120 s 白等）。

**反证**：把 worker 的 stdin 关掉（worker 仍活着但再也收不到命令）
⇒ `submit()` 后 `pending` 永久悬挂、`drain()` 返 False。

## 判定口径

- **REAL** 组：修复后必须全 PASS；
- **BUG** 组：每条都在**断言「缺陷仍然存在」**
  ⇒ 修复前命中（= 缺陷复现成功，是**反证证据**）
  ⇒ 修复后必须**全部落空**。
- 总判定 = REAL 全过 **且** BUG 全落空。

## 关键不变式（REAL 组的核心判据）

> **worker 崩溃后，每一句提交过的句子必须被恰好统计一次**
> （要么 `n_played`，要么 `n_dropped`）⇒ `n_played + n_dropped == n_submitted`。

缺陷 ① 破坏的正是这条不变式。

## 本脚本测什么（**桩 worker，不在 CPU 上跑推理**）

- REAL-1 积压丢句后 `_inflight` 不含该 jid
- REAL-2 崩溃后「每句恰好算一次」不变式成立
- REAL-3 `cancel()` 后 `_inflight` 不含该 jid
- REAL-4 命令送不出去时 `drain()` 能排空（不超时）
- BUG-1/BUG-2 反证：丢句 / cancel 后 `_inflight` 的幽灵 jid
- BUG-3 反证：命令送不出去时 `pending` 永久悬挂 + `drain()` 超时

用法
----
    python results/app/test_tts_drop_crash.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4\app')

import tts_service  # noqa: E402

STUB_PATH = os.path.join(HERE, '_stub_drop_worker.py')

# 桩 worker：启动即 emit ready；收到 synth **不回 played**（模拟「在途 / 卡住」）。
# ⚠️ **stdin EOF 后必须继续活着**（否则 worker 退出 ⇒ 触发重启 ⇒ 掩盖缺陷③）。
STUB = r'''
import sys, json, time
sys.stdout.write(json.dumps({"kind":"ready","device":"STUB","voice":"A"}) + "\n")
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
    if cmd == "synth":
        # 故意**不**回 played ⇒ 句子永远在途
        pass
# stdin 关了也**不退出** ⇒ 模拟「worker 还活着但收不到任何命令」
while True:
    time.sleep(0.2)
'''

REAL_FAIL = []
BUG_HIT = []


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


def bug(name, cond, detail=''):
    """断言「缺陷仍然存在」——命中 = 缺陷复现（反证证据）。"""
    print(f"  [{'BUG ' if cond else 'gone'}] {name}" + (f' — {detail}' if detail else ''))
    if cond:
        BUG_HIT.append(name)


def wait_state(svc, want, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def new_service(logs):
    return tts_service.TTSService(device='STUB', voice='A', auto=False,
                                  on_log=logs.append)


def main():
    with open(STUB_PATH, 'w', encoding='utf-8') as f:
        f.write(STUB)
    tts_service._WORKER = STUB_PATH

    old_max = tts_service.BACKLOG_MAX_S

    print('=' * 72)
    print('§29 修复验收：积压丢句 / cancel / 发送失败 不得留下 _inflight 幽灵')
    print('（桩 worker，无推理；不跑测速、不占 GPU）')
    print('=' * 72)

    # ── [A] 积压丢句 ⇒ _inflight 必须注销 ─────────────────────────────
    print()
    print('[A] 积压超限丢句 ⇒ 该 jid 不得留在 _inflight（幽灵）')
    logs_a = []
    svc = new_service(logs_a)
    svc.start()
    real('A0 worker 到 ready', wait_state(svc, ('ready',)), f'state={svc.state}')

    # 先把阈值抬高，保证 submit 期间**不触发**丢句（得到干净的起点）
    tts_service.BACKLOG_MAX_S = 999.0
    for i in range(8):
        svc.submit('积压测试第 %d 句，这句话故意写得很长很长很长很长' % i, seg=i)
    t0 = time.time()
    while time.time() - t0 < 10 and len(svc.pending) < 8:
        time.sleep(0.05)
    real('A1 8 句全部在途（此刻还没有丢句）',
         len(svc.pending) == 8 and svc.n_dropped == 0,
         f'pending={len(svc.pending)} n_dropped={svc.n_dropped} '
         f'inflight={sorted(svc._inflight)}')

    # 调低阈值 ⇒ 手动触发丢句
    tts_service.BACKLOG_MAX_S = 1.0
    n_drop_before = svc.n_dropped
    with svc.lock:
        pending_before = list(svc.pending.keys())
    svc._update_backlog()
    time.sleep(0.2)

    real('A2 确实发生了丢句（n_dropped 增加）', svc.n_dropped > n_drop_before,
         f'n_dropped {n_drop_before} -> {svc.n_dropped}')
    real('A3 pending 已减少', len(svc.pending) < len(pending_before),
         f'pending {len(pending_before)} -> {len(svc.pending)}')

    dropped_ids = [j for j in pending_before if j not in svc.pending]
    real('A4 能定位被丢掉的 jid', len(dropped_ids) > 0, f'dropped_ids={dropped_ids}')

    ghost = [j for j in dropped_ids if j in svc._inflight]
    bug('A5 反证·缺陷①：被丢的 jid 仍留在 _inflight（幽灵）', len(ghost) > 0,
        f'ghost={ghost} inflight={sorted(svc._inflight)}')
    real('A6 缺陷①已修：被丢的 jid 已从 _inflight 注销', len(ghost) == 0,
         f'ghost={ghost} inflight={sorted(svc._inflight)}')
    svc.close()

    # ── [C] 丢句后崩溃 ⇒ 每句恰好算一次 ─────────────────────────────
    print()
    print('[C] 丢句后 worker 崩溃 ⇒ 「每句恰好算一次」不变式')
    logs_c = []
    svc2 = new_service(logs_c)
    svc2.start()
    wait_state(svc2, ('ready',))
    tts_service.BACKLOG_MAX_S = 999.0
    for i in range(8):
        svc2.submit('崩溃计数测试第 %d 句，这句话故意写得很长很长很长很长' % i, seg=i)
    t0 = time.time()
    while time.time() - t0 < 10 and len(svc2.pending) < 8:
        time.sleep(0.05)
    tts_service.BACKLOG_MAX_S = 1.0
    svc2._update_backlog()
    time.sleep(0.2)
    n_sub = svc2.n_submitted
    dropped_after = svc2.n_dropped
    try:
        svc2.proc.kill()
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < 15 and svc2.state != 'error' and svc2.n_restart < 1:
        time.sleep(0.05)
    time.sleep(1.0)
    accounted = svc2.n_played + svc2.n_dropped
    real('C1 不变式：n_played + n_dropped == n_submitted',
         accounted == n_sub,
         f'played={svc2.n_played} dropped={svc2.n_dropped} '
         f'sum={accounted} submitted={n_sub} '
         f'（修复前 dropped 会被算两遍 ⇒ sum > submitted）')
    real('C2 崩溃后 _inflight 已清空', len(svc2._inflight) == 0,
         f'inflight={sorted(svc2._inflight)}')
    try:
        svc2.close()
    except Exception:
        pass

    # ── [D] cancel() 后 _inflight 必须注销 ───────────────────────────
    print()
    print('[D] cancel() ⇒ 该 jid 必须从 _inflight 注销')
    logs_d = []
    svc3 = new_service(logs_d)
    svc3.start()
    wait_state(svc3, ('ready',))
    # 🔴 抬高阈值：本组要测「cancel 注销 _inflight」，**不能**被积压丢句干扰
    tts_service.BACKLOG_MAX_S = 999.0
    svc3.submit('待取消的句子', seg=0)
    t0 = time.time()
    while time.time() - t0 < 10 and 0 not in svc3._inflight:
        time.sleep(0.05)
    real('D1 句子已在途', 0 in svc3._inflight, f'inflight={sorted(svc3._inflight)}')
    svc3.cancel(0)
    time.sleep(0.2)
    bug('D2 反证·缺陷②：取消后 jid 仍在 _inflight', 0 in svc3._inflight,
        f'inflight={sorted(svc3._inflight)}')
    real('D3 缺陷②已修：cancel 后 _inflight 不含该 jid', 0 not in svc3._inflight,
         f'inflight={sorted(svc3._inflight)}')
    svc3.close()

    # ── [E] 命令送不出去 ⇒ 不得永久悬挂 ─────────────────────────────
    print()
    print('[E] worker 收不到命令（stdin 已关）⇒ 句子不得永久挂在 pending')
    logs_e = []
    svc4 = new_service(logs_e)
    svc4.start()
    wait_state(svc4, ('ready',))
    # 🔴 抬高阈值：本组要测的是「命令送不出去」，**不能**被积压丢句干扰
    tts_service.BACKLOG_MAX_S = 999.0
    # 关掉 worker 的 stdin ⇒ worker 仍活着但**再也收不到任何命令**
    try:
        svc4.proc.stdin.close()
    except Exception:
        pass
    time.sleep(0.2)
    svc4.submit('送不出去的一句', seg=0)
    time.sleep(0.5)
    bug('E1 反证·缺陷③：句子永久挂在 pending', len(svc4.pending) > 0,
        f'pending={list(svc4.pending)} inflight={sorted(svc4._inflight)}')
    t_drain = time.time()
    drained = svc4.drain(timeout=6.0)
    drain_s = time.time() - t_drain
    bug('E2 反证·缺陷③：drain 超时返回 False', not drained,
        f'drained={drained} 用时 {drain_s:.1f}s')
    real('E3 缺陷③已修：drain 能排空（不超时）', drained,
         f'drained={drained} 用时 {drain_s:.1f}s')
    try:
        svc4.close()
    except Exception:
        pass

    tts_service.BACKLOG_MAX_S = old_max

    print()
    print('=' * 72)
    ok = (not REAL_FAIL) and (not BUG_HIT)
    print(f'REAL 未通过：{REAL_FAIL if REAL_FAIL else "无"}')
    print(f'BUG 仍命中（应为无）：{BUG_HIT if BUG_HIT else "无"}')
    print(f'结论：{"PASS" if ok else "FAIL"}')
    print('=' * 72)
    try:
        os.remove(STUB_PATH)
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
