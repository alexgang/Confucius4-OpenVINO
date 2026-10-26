#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app086 — §57 的**验收 + 反证**脚本。

## 本轮修的缺陷类别：**「同一个 jid 的丢弃计数只能加一次」在 `cancel()` 路径上没实现**

### 缺陷：`TTSService.cancel()` 无条件 `n_dropped += 1`

§30 已经把这条写成铁律并在**句子级 error** 路径上实现了
（`tts_service.py` L918-921：`already = msg_id in self._dropped_ids`
⇒ 已在丢弃集合里 ⇒ 本次**不再重复计丢句**）。

🔴🔴 但 `cancel()`（L853-879）**没有**这道闸门：

```python
def cancel(self, jid: int):
    self._send({'cmd': 'cancel', 'id': jid})
    with self.lock:
        self.pending.pop(jid, None)
        self._inflight.discard(jid)
        self._dropped_ids.add(jid)
    self.n_dropped += 1          # ← 无条件 +1
```

⇒ 只要**同一个 jid 被 cancel 两次**，就 `n_dropped += 2`
⇒ 不变式 `n_played + n_dropped == n_submitted` 被破坏（sum > submitted）。

### 真实触发路径（不是理论构造）

`live_caption/offline_reader.py` 的 `OfflineReader.stop()` 与 `_loop()` 的 `finally`
**各调一次** `_cancel_pending()`：

```python
def stop(self, cancel_pending: bool = True):
    self.stopped = True
    self._stop.set()
    if cancel_pending:
        self._cancel_pending()      # ← 第 1 次

def _loop(self):
    ...
    finally:
        if self.stopped:
            self._cancel_pending()  # ← 第 2 次
```

而 `_cancel_pending()` 的实现是「**先在锁内快照 victims，再在锁外逐个 `svc.cancel()`**」：

```python
with svc.lock:
    victims = [jid for jid, it in svc.pending.items() if ...]
for jid in victims:
    svc.cancel(jid)          # ← 锁外
```

⇒ **两个线程各自的快照都可能在对方 cancel 完之前拿到同一批 jid**
⇒ 两边都调 `svc.cancel(jid)` ⇒ **同一句被计两次丢句**。

时间线（stop() 由 GUI 线程调，`_loop` 在独立线程）：

| 时刻 | GUI 线程（`stop()`） | reader 线程（`_loop`） |
|---|---|---|
| T0 | `stopped=True`；`_stop.set()` | — |
| T1 | `_cancel_pending()` → **快照 victims=[1,2,3]**（锁内） | — |
| T2 | 锁外开始 `svc.cancel(1)` | 醒来看到 `_stop` ⇒ break ⇒ finally ⇒ `_cancel_pending()` → **快照 victims=[1,2,3]**（GUI 还没全 cancel 完） |
| T3 | `cancel(1)` `cancel(2)` `cancel(3)` ⇒ `n_dropped=3` | `cancel(1)` `cancel(2)` `cancel(3)` ⇒ **`n_dropped=6`** |

⇒ 3 句提交 ⇒ `n_dropped=6` ⇒ **sum(6) ≠ submitted(3)**。

### 为什么「迟到的 `played` 也救不回来」

§30 的补救机制是：收到迟到的 `played` 时 `n_dropped -= 1` + `n_played += 1`
⇒ 一次「丢了又播」被**改记**为「已播」，sum 不变。

🔴 但**双记**不是一次「丢了又播」，而是**同一句被丢了两次**：
`n_dropped` 已经是 2 ⇒ 迟到的 `played` 只能把它减回 1
⇒ 最终 `n_played=1, n_dropped=1` ⇒ **sum=2 ≠ submitted=1** ⇒ **仍然破坏**。

⇒ 所以这个缺陷**不能**靠 §30 的「改记」机制自愈 ⇒ 必须修 `cancel()` 本身。

## 判定口径

- **REAL** 组：修复后必须全 PASS；
- **反证**组：用**修复前的固定 commit** 在**子进程**里跑同样的场景
  ⇒ 必须**复现**不变式被破坏 ⇒ 证明缺陷**曾真实存在**（不是嘴说）；
- 总判定 = REAL 全过 **且** 反证全命中。

⚠️ 反证基线**不能用 `HEAD`**（提交后 HEAD 就是修复版 ⇒ 反证永远落空）
⇒ 用固定 commit SHA `8d6bcc1`（= §56 的提交，**本缺陷仍未修**）。

## 纪律

- **桩 worker**：不跑推理、不测速、不占 GPU、不取机器锁；
- `tts_service` 只 import stdlib ⇒ 安全；
- 不调 MiniMax；质量判定交 reviewer。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

REAL_FAIL = []
EVIDENCE = {}
STUB = os.path.join(HERE, '_stub_app086_worker.py')

# 🔴 **反证基线**：§56 的提交（本缺陷类别**尚未**修）
BASELINE_COMMIT = '8d6bcc1'

# 桩 worker：ready 之后**不回 played**（句子永远在途）
# 🔴 stdin EOF 后必须继续活着 ⇒ 否则 worker 退出 ⇒ 触发自动重启
STUB_ALIVE = r'''
import sys, json, time
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
    if msg.get("cmd") == "quit":
        sys.exit(0)
    if msg.get("cmd") == "synth":
        pass          # 故意**不**回 played ⇒ 句子永远在途
while True:
    time.sleep(0.2)
'''


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def wait_for(fn, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False


def make_svc():
    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    wait_state(svc, ('ready',), 25.0)
    return svc


def invariant(svc):
    """🔴 正确的「守恒」判据。

    ⚠️ **不能**只写 `n_played + n_dropped == n_submitted` ——
    句子还**在途**（`pending` 里）时两边都会少算 ⇒ 那是正常的，不是缺陷。
    ⇒ 正确判据：**每一句提交过的句子，恰好处于「在途 / 已播 / 已丢」三者之一**：

        n_played + n_dropped + len(pending) == n_submitted

    ⇒ 等价地：`sum(已定案) <= submitted`（已定案 = 已播 + 已丢），
      且全部定案后 `sum == submitted`。
    """
    with svc.lock:
        n_pending = len(svc.pending)
    return (svc.n_played + svc.n_dropped + n_pending) == svc.n_submitted


def sums(svc):
    with svc.lock:
        n_pending = len(svc.pending)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                sum=svc.n_played + svc.n_dropped,
                invariant=invariant(svc))


# ══════════════════════════════════════════════════════════════════════
# [A] 缺陷：`cancel()` 对同一个 jid 记两次丢句
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print()
    print('[A] 同一个 jid 被 cancel 两次 ⇒ 只能计一次丢句')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = make_svc()
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)
    real('A0 前置：3 句已提交且在途',
         svc.n_submitted == 3 and len(svc.pending) == 3,
         f'submitted={svc.n_submitted} pending={len(svc.pending)}')

    # 🔴 **同一句 cancel 两次**（离线朗读 stop() + _loop.finally 的竞态形态）
    svc.cancel(0)
    real('A1 第一次 cancel 后不变式成立', invariant(svc), str(sums(svc)))
    real('A2 第一次 cancel 计了 1 句丢句',
         svc.n_dropped == 1 and svc.n_played == 0, str(sums(svc)))

    svc.cancel(0)
    real('A3 第二次 cancel 同一 jid 后不变式**仍**成立',
         invariant(svc), str(sums(svc)))
    real('A4 第二次 cancel **没有**重复计丢句（n_dropped 仍为 1）',
         svc.n_dropped == 1 and svc.n_played == 0, str(sums(svc)))
    real('A5 jid 0 已在 _dropped_ids 里（说明它确实被丢过）',
         0 in svc._dropped_ids, f'_dropped_ids={sorted(svc._dropped_ids)}')
    EVIDENCE['A_cancel_twice'] = sums(svc)

    # 🔴🔴 **迟到的 `played` 也救不回来**（双记 ≠ 一次「丢了又播」）
    svc._handle_event({'kind': 'played', 'id': 0})
    real('A6 迟到 played 后不变式仍成立（改记只减 1）', invariant(svc),
         str(sums(svc)))
    real('A7 迟到 played 被改记为已播（n_played=1 / n_dropped=0）',
         svc.n_played == 1 and svc.n_dropped == 0, str(sums(svc)))
    svc.close()


# ══════════════════════════════════════════════════════════════════════
# [B] 真实路径复现：OfflineReader 的 stop() + _loop.finally 双快照
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print()
    print('[B] 真实路径：OfflineReader.stop() 与 _loop.finally 各 cancel 一次')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    import offline_reader as OR

    svc = make_svc()
    segs = ['第一段译文。', '第二段译文。', '第三段译文。']
    reader = OR.OfflineReader(svc, on_log=lambda m: None)
    reader.start(segs)
    wait_for(lambda: len(svc.pending) >= 1, 10.0)
    # 强制把 3 段都放进 pending（模拟都已提交）
    with svc.lock:
        for i in range(3):
            svc.pending.setdefault(i, dict(seg=OR.OFFLINE_SEG_BASE - i,
                                           text=segs[i % 3], t=0.0))
        svc.n_submitted = 3
    real('B0 前置：3 段离线译文在途',
         len(svc.pending) == 3 and svc.n_submitted == 3, str(sums(svc)))

    reader.stop(cancel_pending=True)
    wait_for(lambda: reader.done, 10.0)
    time.sleep(0.3)
    real('B1 停止后不变式成立（每句只计一次丢句）', invariant(svc), str(sums(svc)))
    real('B2 丢句数 ≤ 提交数（没有双记）',
         svc.n_dropped <= svc.n_submitted,
         f'n_dropped={svc.n_dropped} submitted={svc.n_submitted}')
    EVIDENCE['B_offline_stop'] = sums(svc)
    svc.close()


# ══════════════════════════════════════════════════════════════════════
# [C] 正常路径**不得回归**
# ══════════════════════════════════════════════════════════════════════
def group_c():
    print()
    print('[C] 正常路径：一次 cancel 仍计 1 句丢句；played 正常计数')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = make_svc()
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)
    svc.cancel(1)
    real('C1 一次 cancel ⇒ n_dropped=1 / n_played=0',
         svc.n_dropped == 1 and svc.n_played == 0, str(sums(svc)))
    real('C2 不变式成立', invariant(svc), str(sums(svc)))
    for i in (0, 2):
        svc._handle_event({'kind': 'played', 'id': i})
    real('C3 其余 2 句播了 ⇒ n_played=2 / n_dropped=1',
         svc.n_played == 2 and svc.n_dropped == 1, str(sums(svc)))
    real('C4 不变式成立', invariant(svc), str(sums(svc)))
    EVIDENCE['C_normal'] = sums(svc)
    svc.close()


# ══════════════════════════════════════════════════════════════════════
# [D] 反证：修复前的固定 commit **确实**破坏不变式
# ══════════════════════════════════════════════════════════════════════
PROBE = r'''
import importlib.util, json, os, sys, time
from importlib.machinery import SourceFileLoader
mod_path, worker = sys.argv[1], sys.argv[2]
loader = SourceFileLoader("old_tts_service", mod_path)
spec = importlib.util.spec_from_loader("old_tts_service", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
m._WORKER = worker
m.BACKLOG_MAX_S = 1e9

def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False

def wait_for(fn, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False

out = {}

def inv(svc):
    with svc.lock:
        n_pending = len(svc.pending)
    return (svc.n_played + svc.n_dropped + n_pending) == svc.n_submitted

def snap(svc):
    with svc.lock:
        n_pending = len(svc.pending)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                sum=svc.n_played + svc.n_dropped,
                broken=(not inv(svc)))

# ── 场景 1：同一 jid cancel 两次 ──────────────────────────────────
svc = m.TTSService(device="STUB", voice="A", on_log=lambda x: None)
wait_state(svc, ("ready",))
for i in range(3):
    svc.submit("s%d" % i, seg=i)
wait_for(lambda: len(svc.pending) == 3)
svc.cancel(0)
svc.cancel(0)
out["cancel_twice"] = snap(svc)
# 迟到的 played 只能减 1 ⇒ 仍然破坏
svc._handle_event({"kind": "played", "id": 0})
out["cancel_twice_after_late_played"] = snap(svc)
svc.close()
print(json.dumps(out, ensure_ascii=False))
'''


def group_d():
    print()
    print('[D] 反证：修复前的固定 commit **确实**破坏不变式（缺陷曾真实存在）')

    old_src = None
    try:
        r = subprocess.run(
            ['git', 'show', '%s:live_caption/tts_service.py' % BASELINE_COMMIT],
            cwd=REPO, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=180)
        if r.returncode == 0:
            old_src = r.stdout
    except Exception as e:
        print(f'  [skip] 取不到修复前源码: {e}')

    if not old_src:
        real('D0 反证：修复前源码可取', False, '取不到 %s' % BASELINE_COMMIT)
        return

    old_mod = os.path.join(HERE, '_old_tts_service_s57.py')
    probe = os.path.join(HERE, '_probe_old_s57.py')
    with open(old_mod, 'w', encoding='utf-8', newline='') as f:
        f.write(old_src)
    with open(probe, 'w', encoding='utf-8') as f:
        f.write(PROBE)
    try:
        r = subprocess.run([sys.executable, probe, old_mod, STUB],
                           capture_output=True, text=True, timeout=180)
        try:
            out = json.loads((r.stdout or '').strip().splitlines()[-1])
        except Exception:
            out = {}
            print('  [warn] 反证探针无输出：', (r.stdout or '')[-500:],
                  (r.stderr or '')[-500:])
        a = out.get('cancel_twice') or {}
        b = out.get('cancel_twice_after_late_played') or {}
        # ⚠️ 这两条是「证明缺陷曾经存在」⇒ 命中是**预期**的
        real('D1 修复前：同一 jid cancel 两次 **确实**破坏不变式（反证）',
             a.get('broken') is True,
             f'修复前 sum={a.get("sum")} submitted={a.get("n_submitted")}')
        real('D2 修复前：迟到的 played 也**救不回来**（反证）',
             b.get('broken') is True,
             f'修复前 sum={b.get("sum")} submitted={b.get("n_submitted")}')
        EVIDENCE['D_baseline'] = dict(commit=BASELINE_COMMIT,
                                      cancel_twice=a,
                                      cancel_twice_after_late_played=b)
    finally:
        for p in (old_mod, probe):
            try:
                os.remove(p)
            except Exception:
                pass


def main():
    old_max = tts_service.BACKLOG_MAX_S
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(STUB_ALIVE)

    print('=' * 74)
    print('§57 验收：cancel() 的「丢弃计数只能加一次」（不变式不得被破坏）')
    print('（桩 worker，无推理；不跑测速、不占 GPU、不调 MiniMax）')
    print('=' * 74)

    try:
        group_a()
        group_b()
        group_c()
        group_d()
    finally:
        tts_service.BACKLOG_MAX_S = old_max

    print()
    print('=' * 74)
    ok = not REAL_FAIL
    print(f'REAL 失败项：{REAL_FAIL if REAL_FAIL else "无"}')
    print('总判定：' + ('PASS —— REAL 全过' if ok else 'FAIL'))

    ev_path = os.path.join(HERE, 'app086_tts_cancel_double_count_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, evidence=EVIDENCE,
                       baseline_commit=BASELINE_COMMIT,
                       verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
