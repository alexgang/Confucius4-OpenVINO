#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app090 — §60 的**验收 + 反证**脚本。

## 本轮修的缺陷类别：**丢句「判定」与「计数」不原子 ⇒ `n_dropped` 双记**

### 不变式（本项目长期口径）

    n_played + n_dropped + len(pending) == n_submitted

🔴 **双记（同一个 jid 被计两次丢句）会破坏它** ⇒
底栏「丢句 + 已播」超过「提交」⇒ 用户看到的统计自相矛盾。

### 缺陷（§60 修的就是这一类）

`submit()` / `_flush_queue()` 里，丢句的**判定**与**计数**被拆开了：

```python
elif action == 'dead':
    with self.lock:
        self.pending.pop(jid, None)     # ← 判定：把这句话摘掉
    self.n_dropped += 1                 # ← 计数：**无条件** +1（锁外）
```

而「worker 级 error 的孤儿清理」做的是：

```python
with self.lock:
    orphan = sorted(self.pending.keys())
    self.pending.clear()
    ...
self.n_dropped += len(orphan)          # ← 锁外
```

⇒ **只要两者交错**，同一句会被计**两次**：

| 时刻 | 线程 | 动作 |
|---|---|---|
| t1 | App | `submit()` 写入 `pending[jid]`、`n_submitted += 1` |
| t2 | 事件 | worker 级 error ⇒ 孤儿清理把 `jid` 算进 `orphan` ⇒ 计 1 |
| t3 | App | `submit()` 的丢句分支：`pending.pop` 返回 `None`（已被清掉）⇒ **但仍无条件 `n_dropped += 1`** ⇒ **计 2** |

🔴 **为什么这不是「理论构造」**：真实世界里 worker 级 error（模型加载失败 /
   播放设备打不开）随时可能发生，而 `submit()` 是**每句都调**的
   ⇒ 只要用户在 worker 故障的同一瞬间提交新句，就命中。

### 修法

**统一原子口径**：新增 `_drop_one(jid, register_dropped=False)` ⇒
「摘除（`pending.pop`）+ 注销 `_inflight` + 计数」**全部在同一把锁内**完成
⇒ **只有「这一句此刻确实还在 `pending` 里」才计丢句**。

### 怎么**确定性**复现（不靠概率）

真实世界里那个窗口只有几微秒宽 ⇒ 靠「多跑几千次」抓不到。
⇒ 本脚本用**可注入的锁包装器**：在 `submit()` 的**第一个临界区释放之后**
   （= 窗口的精确位置）**同步**触发 worker 级 error
   ⇒ 每次都必现 ⇒ 证据可复现。

⚠️ 触发点必须在**释放锁之后**：`_handle_event('error')` 自己要取锁
   ⇒ 若在持锁时调用 ⇒ 直接自死锁（那正是修复后的**正确**行为）。

### 判定口径

- **REAL** 组：修复后必须全 PASS；
- **反证**组：用**修复前的固定 commit** 在**子进程**里跑同样的场景
  ⇒ 必须**复现双记** ⇒ 证明缺陷**曾真实存在**（不是嘴说）；
- 总判定 = REAL 全过 **且** 反证全命中。

⚠️ 反证基线**不能用 `HEAD`**（提交后 HEAD 就是修复版 ⇒ 反证永远落空）
⇒ 用**提交前的固定 commit** `b3c5ebb`（= §59 的 docs 提交，
   `tts_service.py` 内容与 §59 的 `36e3d1e` 一致 ⇒ **本缺陷类别尚未修**）。

## 纪律

- **不起 worker 子进程**（`auto=False`）⇒ 不跑推理、不测速、不占 GPU、
  **不取机器锁**、不碰声卡；
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

# 🔴 **包内模式**：用 `--pkg <客户包目录>` ⇒ 直接 import **包内那份**
#   `tts_service.py`（而不是仓库那份）⇒ 验证「包里的那份也是修好的」。
#   ⚠️ 必须**在 import 之前**改 `sys.path` ⇒ 否则 import 到的是仓库那份。
_PKG = None
for _i, _a in enumerate(sys.argv):
    if _a == '--pkg' and _i + 1 < len(sys.argv):
        _PKG = sys.argv[_i + 1]
    elif _a.startswith('--pkg='):
        _PKG = _a.split('=', 1)[1]
if _PKG:
    sys.path.insert(0, os.path.join(_PKG, 'app'))
    print('🔴 包内模式：%s' % os.path.join(_PKG, 'app', 'tts_service.py'))
else:
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

REAL_FAIL = []
EVIDENCE = {}

# 🔴 **反证基线**：§59 的 docs 提交（本缺陷类别**尚未**修）
BASELINE_COMMIT = 'b3c5ebb'


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


def snap(svc):
    with svc.lock:
        n_pending = len(svc.pending)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                n_queue=len(svc._queue),
                inflight=sorted(svc._inflight),
                sum=svc.n_played + svc.n_dropped,
                invariant=(svc.n_played + svc.n_dropped + n_pending)
                          == svc.n_submitted,
                over=(svc.n_played + svc.n_dropped) > svc.n_submitted)


def make_gate(svc, fire):
    """返回一个锁包装器：在**第一个临界区释放之后**调用 `fire()`。

    🔴 **为什么在释放之后**：`_handle_event('error')` 自己要取锁
       ⇒ 若在持锁时调用 ⇒ 自死锁（那是修复后的**正确**行为）。
       ⇒ 而「释放锁之后」正是真实世界里 worker 级 error 落进窗口的位置。

    ⚠️ 包装器**不改变**锁的语义（仍是同一个 `threading.Lock`）
       ⇒ 被测代码拿到的仍是**非可重入**锁 ⇒ 死锁检测依然有效。
    """

    class _Gate:
        def __init__(self, inner):
            self._inner = inner
            self._n = 0
            self._fired = False

        def __enter__(self):
            self._inner.acquire()
            self._n += 1
            return self

        def __exit__(self, *a):
            self._inner.release()
            if self._n == 1 and not self._fired:
                self._fired = True
                fire()
            return False

        def __getattr__(self, n):
            return getattr(self._inner, n)

    return _Gate(svc.lock)


def new_svc():
    """造一个**不起 worker 子进程**的服务实例。

    🔴 `auto=False` ⇒ 不 spawn 任何进程 ⇒ 不占 CPU/GPU/声卡 ⇒
       不需要机器锁（本轮**不做**任何计时/测速作业）。
    """
    return tts_service.TTSService(device='STUB', voice='A',
                                   on_log=lambda m: None, auto=False)


def fire_worker_error(svc):
    """注入一次 **worker 级** error（不带 id）⇒ 触发「孤儿清理」。"""
    svc._handle_event({'kind': 'error', 'message': '注入的 worker 级故障'})


# ══════════════════════════════════════════════════════════════════════
# [A] submit() 的「worker 已故障」分支 与 孤儿清理 交错 ⇒ 不得双记
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print()
    print('[A] submit() 的 dead 分支 与 worker 级 error 的孤儿清理交错 ⇒ 不得双记')

    svc = new_svc()
    try:
        # 🔴 前置：worker 已故障 ⇒ `submit()` 走 `action == 'dead'`
        svc.state = 'error'

        fired = []

        def fire():
            fired.append(1)
            fire_worker_error(svc)

        svc.lock = make_gate(svc, fire)
        svc.submit('故障期提交句', seg=0)
        svc.lock = svc.lock._inner
        time.sleep(0.2)

        real('A1 注入点确实命中（第一个临界区之后触发了 worker 级 error）',
             len(fired) == 1, 'fired=%d' % len(fired))

        s = snap(svc)
        real('A2 丢句数恰好 1（**不得**双记）', svc.n_dropped == 1, str(s))
        real('A3 不变式成立', s['invariant'], str(s))
        real('A4 不得出现「已播 + 丢句 > 提交」', not s['over'], str(s))
        real('A5 没有悬挂（pending 已清空）', s['n_pending'] == 0, str(s))
        EVIDENCE['A_dead_race'] = s
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [B] submit() 的「发送失败」分支 与 孤儿清理 交错 ⇒ 不得双记
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print()
    print('[B] submit() 的发送失败分支 与 worker 级 error 的孤儿清理交错 ⇒ 不得双记')

    svc = new_svc()
    try:
        # 🔴 前置：worker 「ready」⇒ `submit()` 走 `action == 'send'`
        #   但 `svc.proc is None` ⇒ `_send()` 必然失败 ⇒ 走发送失败分支。
        svc.state = 'ready'

        fired = []

        def fire():
            fired.append(1)
            fire_worker_error(svc)

        svc.lock = make_gate(svc, fire)
        svc.submit('发送失败句', seg=0)
        svc.lock = svc.lock._inner
        time.sleep(0.2)

        real('B1 注入点确实命中', len(fired) == 1, 'fired=%d' % len(fired))

        s = snap(svc)
        real('B2 丢句数恰好 1（**不得**双记）', svc.n_dropped == 1, str(s))
        real('B3 不变式成立', s['invariant'], str(s))
        real('B4 不得出现「已播 + 丢句 > 提交」', not s['over'], str(s))
        real('B5 没有悬挂', s['n_pending'] == 0, str(s))
        EVIDENCE['B_sendfail_race'] = s
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [C] 无交错时**不得漏计**（防「修成不计数」）
# ══════════════════════════════════════════════════════════════════════
def group_c():
    print()
    print('[C] 无交错：worker 已故障时提交 ⇒ 必须计 1 句丢句（不得漏计）')

    svc = new_svc()
    try:
        svc.state = 'error'
        svc.submit('故障期提交句', seg=0)
        time.sleep(0.1)
        s = snap(svc)
        real('C1 丢句数恰好 1', svc.n_dropped == 1, str(s))
        real('C2 不变式成立', s['invariant'], str(s))
        real('C3 pending 已清空', s['n_pending'] == 0, str(s))
        EVIDENCE['C_no_race'] = s
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [D] worker 级 error 后的「迟到句子级 error」不得重复计（回归 §47）
# ══════════════════════════════════════════════════════════════════════
def group_d():
    print()
    print('[D] 回归：worker 级 error 后的迟到句子级 error 不得重复计丢句')

    svc = new_svc()
    try:
        svc.state = 'ready'
        # 🔴 **手工**造一个「在途」句子（**不**走 `submit()`）。
        #   理由：`submit()` 在 `proc is None` 时会走「发送失败」路径，
        #   提前把这句定案 ⇒ 就构造不出「在途」状态了。
        with svc.lock:
            svc.pending[0] = dict(seg=0, text='将被孤儿清理的句',
                                  t=time.perf_counter())
            svc._inflight.add(0)
            svc.n_submitted += 1
        s0 = snap(svc)
        real('D0 前置：1 句在途', s0['n_pending'] == 1, str(s0))

        fire_worker_error(svc)
        time.sleep(0.1)
        s1 = snap(svc)
        real('D1 孤儿清理计了 1 句丢句', svc.n_dropped == 1, str(s1))

        # 🔴 worker 仍活着（worker 级 error 不会让它退出）⇒ 它可能回句子级 error
        svc._handle_event({'kind': 'error', 'id': 0, 'message': '迟到的句子级错误'})
        time.sleep(0.1)
        s2 = snap(svc)
        real('D2 迟到句子级 error **不得**重复计丢句',
             svc.n_dropped == 1, str(s2))
        real('D3 不变式仍成立', s2['invariant'], str(s2))
        EVIDENCE['D_late_sentence_error'] = s2
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [E] 回归：`_flush_queue()` 补发失败 ⇒ 必须计丢句（不得漏计）
# ══════════════════════════════════════════════════════════════════════
def group_e():
    print()
    print('[E] 回归：_flush_queue() 补发失败 ⇒ 必须计 1 句丢句')

    svc = new_svc()
    try:
        svc.state = 'ready'
        # 🔴 **手工**造一个「在待发队列里」的句子（**不**走 `submit()`）。
        #   理由同上：`submit()` 在 `proc is None` 时会走「发送失败」路径。
        with svc.lock:
            svc.pending[0] = dict(seg=0, text='补发失败句',
                                  t=time.perf_counter())
            svc.n_submitted += 1
            svc._queue.append({'cmd': 'synth', 'id': 0, 'text': '补发失败句'})
            svc._queued_ids.add(0)
        # 🔴 `svc.proc is None` ⇒ `_send()` 失败
        svc._flush_queue()
        time.sleep(0.1)
        s = snap(svc)
        real('E1 补发失败计了 1 句丢句', svc.n_dropped == 1, str(s))
        real('E2 不变式成立', s['invariant'], str(s))
        real('E3 待发队列已清空', s['n_queue'] == 0, str(s))
        EVIDENCE['E_flush_fail'] = s
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [F] 反证：修复前的固定 commit **确实**双记（缺陷曾真实存在）
# ══════════════════════════════════════════════════════════════════════
PROBE = r'''
import importlib.util, json, os, sys, time
from importlib.machinery import SourceFileLoader
mod_path = sys.argv[1]
loader = SourceFileLoader("old_tts_service", mod_path)
spec = importlib.util.spec_from_loader("old_tts_service", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


def snap(svc):
    with svc.lock:
        n_pending = len(svc.pending)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                sum=svc.n_played + svc.n_dropped,
                over=(svc.n_played + svc.n_dropped) > svc.n_submitted)


def make_gate(svc, fire):
    class _Gate:
        def __init__(self, inner):
            self._inner = inner
            self._n = 0
            self._fired = False
        def __enter__(self):
            self._inner.acquire()
            self._n += 1
            return self
        def __exit__(self, *a):
            self._inner.release()
            if self._n == 1 and not self._fired:
                self._fired = True
                fire()
            return False
        def __getattr__(self, n):
            return getattr(self._inner, n)
    return _Gate(svc.lock)


out = {}

# ── 场景 A：dead 分支 与 孤儿清理 交错 ─────────────────────────────
svc = m.TTSService(device="STUB", voice="A", on_log=lambda x: None, auto=False)
svc.state = "error"
svc.lock = make_gate(svc, lambda: svc._handle_event(
    {"kind": "error", "message": "注入的 worker 级故障"}))
svc.submit("故障期提交句", seg=0)
svc.lock = svc.lock._inner
time.sleep(0.2)
out["A"] = snap(svc)

# ── 场景 B：发送失败分支 与 孤儿清理 交错 ──────────────────────────
svc2 = m.TTSService(device="STUB", voice="A", on_log=lambda x: None, auto=False)
svc2.state = "ready"
svc2.lock = make_gate(svc2, lambda: svc2._handle_event(
    {"kind": "error", "message": "注入的 worker 级故障"}))
svc2.submit("发送失败句", seg=0)
svc2.lock = svc2.lock._inner
time.sleep(0.2)
out["B"] = snap(svc2)

print(json.dumps(out, ensure_ascii=False))
'''


def group_f():
    print()
    print('[F] 反证：修复前的固定 commit **确实**双记（缺陷曾真实存在）')

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
        real('F0 反证：修复前源码可取', False, '取不到 %s' % BASELINE_COMMIT)
        return

    old_mod = os.path.join(HERE, '_old_tts_service_s60.py')
    probe = os.path.join(HERE, '_probe_old_s60.py')
    with open(old_mod, 'w', encoding='utf-8', newline='') as f:
        f.write(old_src)
    with open(probe, 'w', encoding='utf-8') as f:
        f.write(PROBE)
    try:
        r = subprocess.run([sys.executable, probe, old_mod],
                           capture_output=True, text=True, timeout=240)
        try:
            out = json.loads((r.stdout or '').strip().splitlines()[-1])
        except Exception:
            out = {}
            print('  [warn] 反证探针无输出：', (r.stdout or '')[-500:],
                  (r.stderr or '')[-500:])
        a = out.get('A') or {}
        b = out.get('B') or {}
        # ⚠️ 这两条是「证明缺陷曾经存在」⇒ 命中是**预期**的
        real('F1 修复前：dead 分支 **双记**（反证）',
             a.get('n_dropped') == 2 and a.get('over') is True,
             f'修复前 n_dropped={a.get("n_dropped")} '
             f'sum={a.get("sum")} submitted={a.get("n_submitted")}')
        real('F2 修复前：发送失败分支 **双记**（反证）',
             b.get('n_dropped') == 2 and b.get('over') is True,
             f'修复前 n_dropped={b.get("n_dropped")} '
             f'sum={b.get("sum")} submitted={b.get("n_submitted")}')
        EVIDENCE['F_baseline'] = dict(commit=BASELINE_COMMIT, A=a, B=b)
    finally:
        for p in (old_mod, probe):
            try:
                os.remove(p)
            except Exception:
                pass


def main():
    old_max = tts_service.BACKLOG_MAX_S
    tts_service.BACKLOG_MAX_S = 1e9

    print('=' * 74)
    print('§60 验收：丢句「判定 + 计数」必须原子 ⇒ 不得双记')
    print('（不起 worker 子进程；无推理、不测速、不占 GPU、不调 MiniMax）')
    print('=' * 74)

    try:
        group_a()
        group_b()
        group_c()
        group_d()
        group_e()
        group_f()
    finally:
        tts_service.BACKLOG_MAX_S = old_max

    print()
    print('=' * 74)
    ok = not REAL_FAIL
    print(f'REAL 失败项：{REAL_FAIL if REAL_FAIL else "无"}')
    print('总判定：' + ('PASS —— REAL 全过' if ok else 'FAIL'))

    ev_path = os.path.join(HERE, 'app090_tts_drop_double_count_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, evidence=EVIDENCE,
                       baseline_commit=BASELINE_COMMIT,
                       verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
