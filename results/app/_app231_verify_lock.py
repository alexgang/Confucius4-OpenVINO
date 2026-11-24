#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-132 补漏：**独立复核**生产打包路径的机器锁修法（行为级真跑）。

## 为什么必须"行为级真跑"而不是"看代码对不对"

MEMORY §四：「**判据改成「行为级真跑」才是定论**」＋「PASS ≠ 正确：须能被
有缺陷的旧产物识破」。⇒ 本脚本：

1. **真的**把 `live_caption/_app116_build_v25.py` 的锁函数**指向临时锁文件**
   （**不动**真 `shared\\MACHINE_LOCK` ⇒ 不影响别的模块；
   本轮**不跑推理·不测速**⇒ 纯 CPU 逻辑测试 ⇒ 按纪律不占机器锁）；
2. 🔴 **判据①（确定性）**：N 个进程**同一瞬间**（文件栅栏）并发调
   `_create_lock_exclusive` ⇒ 断言**恰好一个**返回 True（独占）；
3. 🔴 **反证组**：同一测试跑在**旧实现**（`os.replace` 非原子）上
   ⇒ 断言旧实现**返回多个 True** ⇒ 证明缺陷真实可复现、且本判据**能识破**
   有缺陷的旧代码（否则"判据恒 PASS"＝假 PASS）；
4. 🔴 **判据②（端到端重叠）**：两个进程并发走完整 `acquire_lock`
   ⇒ 持锁期间**轮询锁内容** ⇒ 断言**没有**"我持锁时锁被别人改写"
   （= 同时两把锁并存）；
5. 断言「别人先建锁 ⇒ 我方 CreateNew **失败**且**不覆盖**别人的锁内容」；
6. 断言看门狗在「锁被抢」时**记 `lock_lost` 事件**且**不覆盖**别人的锁；
7. 断言放锁**只删自己的**。

## 🔴 本轮实测踩到的两个判据坑（写进注释防复发）

- **坑①**：「两个进程都拿到锁」**不等于**「两把锁并存」—— 进程 A 可能
  **先放锁再轮到 B** ⇒ 那是**合法串行**，不是违规。
  ⇒ 判据必须测「**持锁期间锁内容被别人改写**」这个**重叠**现象，
  而不是简单数「拿到锁的进程数」。
- **坑②**：`spawn` 上下文**不能 pickle 局部函数** ⇒ 子进程目标函数必须
  在**模块级**（否则 `AttributeError: Can't get local object`）。

## 纪律
- 🔴 **纯 CPU 逻辑测试**：不跑推理、不测速、**不碰真机器锁**；
- 🔴 用**临时目录**做锁 ⇒ 与其它模块零干扰；
- 🔴 本脚本**入库**（§222：证据 json 入库 ⇒ 其产生脚本也要入库）。
"""
from __future__ import annotations

import importlib.util
import json
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(REPO, 'live_caption', '_app116_build_v25.py')

RESULTS = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(RESULTS, 'app231_lock_verify.json')


def load_module(lock_path, events_path):
    """按路径加载成包脚本（**不执行 main**），并把锁/事件指到临时路径。"""
    spec = importlib.util.spec_from_file_location(
        '_app116_probe_%d_%d' % (os.getpid(), int(time.time() * 1000) % 100000),
        TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LOCK = lock_path
    mod.RESULTS = os.path.dirname(events_path)
    mod.LOG = os.path.join(os.path.dirname(events_path), 'probe.log')
    mod._LOCK_EVENTS = events_path
    return mod


def _legacy_create_factory(mod):
    """🔴 **反证组**：把原子建锁换成旧实现（`os.replace` ⇒ 非原子 ⇒ 可被覆盖）。"""
    def legacy_create(content):
        tmpf = mod.LOCK + '.tmp_legacy'
        with open(tmpf, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmpf, mod.LOCK)
        return True
    return legacy_create


# ── 子进程①：同一瞬间并发原子建锁（栅栏 = go 文件）─────────────────
def worker_create(lock_path, res_dir, tag, legacy, go_file):
    p = os.path.join(res_dir, 'create_%s.json' % tag)
    ev = os.path.join(res_dir, 'ev_%s.jsonl' % tag)
    mod = load_module(lock_path, ev)
    if legacy:
        mod._create_lock_exclusive = _legacy_create_factory(mod)
    try:
        # 栅栏：等 go 文件出现 ⇒ 大家一起冲
        deadline = time.time() + 30
        while not os.path.exists(go_file):
            if time.time() > deadline:
                break
            time.sleep(0.005)
        content = 'app %d %s race-%s' % (os.getpid(), time.time(), tag)
        ok = mod._create_lock_exclusive(content)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'tag': tag, 'created': bool(ok), 'content': content}, f)
    except Exception as e:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'tag': tag, 'error': repr(e)}, f)


# ── 子进程②：端到端 acquire_lock + 持锁期间查重叠 ────────────────
def worker_hold(lock_path, res_dir, tag, go_file):
    p = os.path.join(res_dir, 'hold_%s.json' % tag)
    ev = os.path.join(res_dir, 'ev_%s.jsonl' % tag)
    mod = load_module(lock_path, ev)
    try:
        deadline = time.time() + 30
        while not os.path.exists(go_file):
            if time.time() > deadline:
                break
            time.sleep(0.005)
        content = mod.acquire_lock('hold-%s' % tag)
        got = content is not None
        overlapped = False
        seen = []
        if got:
            for _ in range(30):           # 持锁 ~3 s，每 100 ms 查一次内容
                time.sleep(0.1)
                try:
                    with open(lock_path, encoding='utf-8') as f:
                        cur = f.read().strip()
                except Exception:
                    cur = ''
                if cur and cur != content.strip():
                    overlapped = True
                    seen.append(cur[:60])
                    break
            mod.release_lock(content)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'tag': tag, 'got': got, 'overlapped': overlapped,
                       'seen': seen}, f)
    except Exception as e:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'tag': tag, 'error': repr(e)}, f)


def _spawn_and_wait(target, args_list, res_dir, prefix, timeout=60):
    ctx = mp.get_context('spawn')
    prs = []
    for a in args_list:
        pr = ctx.Process(target=target, args=a)
        pr.start()
        prs.append(pr)
    for pr in prs:
        pr.join(timeout=timeout)
    out = []
    for a in args_list:
        tag = a[2]
        p = os.path.join(res_dir, '%s_%s.json' % (prefix, tag))
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                out.append(json.load(f))
        else:
            out.append({'tag': tag, 'error': 'no result file'})
    return out


def run_create_race(tag, legacy, n=6):
    """N 进程同一瞬间并发原子建锁 ⇒ 返回 True 的个数。"""
    tmp = tempfile.mkdtemp(prefix='app231_create_%s_' % tag)
    try:
        lock = os.path.join(tmp, 'MACHINE_LOCK')
        res_dir = os.path.join(tmp, 'res')
        os.makedirs(res_dir, exist_ok=True)
        go = os.path.join(tmp, 'GO')
        args = [(lock, res_dir, 'T%d' % i, legacy, go) for i in range(n)]
        ctx = mp.get_context('spawn')
        prs = []
        for a in args:
            pr = ctx.Process(target=worker_create, args=a)
            pr.start()
            prs.append(pr)
        time.sleep(1.5)                 # 让所有子进程就位、卡在栅栏
        with open(go, 'w', encoding='utf-8') as f:
            f.write('go')
        for pr in prs:
            pr.join(timeout=60)
        kids = []
        for i in range(n):
            p = os.path.join(res_dir, 'create_T%d.json' % i)
            if os.path.isfile(p):
                with open(p, encoding='utf-8') as f:
                    kids.append(json.load(f))
            else:
                kids.append({'tag': 'T%d' % i, 'error': 'no result file'})
        n_created = sum(1 for k in kids if k.get('created'))
        return {'n_created': n_created, 'children': kids}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_hold_race(tag):
    """两进程端到端 acquire_lock ⇒ 检查是否出现「两把锁并存」。"""
    tmp = tempfile.mkdtemp(prefix='app231_hold_%s_' % tag)
    try:
        lock = os.path.join(tmp, 'MACHINE_LOCK')
        res_dir = os.path.join(tmp, 'res')
        os.makedirs(res_dir, exist_ok=True)
        go = os.path.join(tmp, 'GO')
        args = [(lock, res_dir, t, go) for t in ('A', 'B')]
        ctx = mp.get_context('spawn')
        prs = []
        for a in args:
            pr = ctx.Process(target=worker_hold, args=a)
            pr.start()
            prs.append(pr)
        time.sleep(1.5)
        with open(go, 'w', encoding='utf-8') as f:
            f.write('go')
        for pr in prs:
            pr.join(timeout=90)
        kids = []
        for t in ('A', 'B'):
            p = os.path.join(res_dir, 'hold_%s.json' % t)
            if os.path.isfile(p):
                with open(p, encoding='utf-8') as f:
                    kids.append(json.load(f))
            else:
                kids.append({'tag': t, 'error': 'no result file'})
        n_overlap = sum(1 for k in kids if k.get('overlapped'))
        return {'n_overlap': n_overlap, 'children': kids}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_events(events_path):
    if not os.path.isfile(events_path):
        return []
    out = []
    with open(events_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    checks = []

    def chk(name, ok, detail=''):
        checks.append({'check': name, 'pass': bool(ok), 'detail': detail})
        print('%-4s %s %s' % ('PASS' if ok else 'FAIL', name, detail))

    # ── 判据①（确定性）：并发原子建锁 ⇒ 恰好一个成功 ──────────────
    new_c = run_create_race('new', legacy=False, n=6)
    chk('并发原子建锁（6 进程同瞬间）：**恰好 1 个**成功（新实现）',
        new_c['n_created'] == 1,
        'n_created=%d %r' % (new_c['n_created'], new_c['children']))

    # ── 反证组：旧实现 ⇒ 多个成功（缺陷可复现）────────────────────
    old_c = run_create_race('old', legacy=True, n=6)
    chk('反证组：旧实现（os.replace 非原子）多个进程都「建锁成功」⇒ 缺陷可复现',
        old_c['n_created'] >= 2,
        'old n_created=%d' % old_c['n_created'])
    chk('判据能识破有缺陷的旧实现（新=%d，旧=%d）'
        % (new_c['n_created'], old_c['n_created']),
        new_c['n_created'] == 1 and old_c['n_created'] >= 2,
        'new=%d old=%d' % (new_c['n_created'], old_c['n_created']))

    # ── 判据②（端到端重叠）：两进程走完整 acquire_lock ────────────
    hold = run_hold_race('new')
    chk('端到端并发 acquire_lock：持锁期间**没有**锁被别人改写（无两把锁并存）',
        hold['n_overlap'] == 0,
        'n_overlap=%d %r' % (hold['n_overlap'], hold['children']))

    # ── 别人先建锁 ⇒ 我方独占创建失败且**不覆盖** ─────────────────
    tmp = tempfile.mkdtemp(prefix='app231_c3_')
    try:
        lock = os.path.join(tmp, 'MACHINE_LOCK')
        events = os.path.join(tmp, 'events.jsonl')
        mod = load_module(lock, events)
        other = 'app 999999 2026-11-24 00:00:00 other-module'
        with open(lock, 'w', encoding='utf-8') as f:
            f.write(other)
        ok = mod._create_lock_exclusive('app 12345 mine')
        after = open(lock, encoding='utf-8').read()
        chk('别人先建锁 ⇒ 我方独占创建失败', ok is False, 'ok=%r' % (ok,))
        chk('别人先建锁 ⇒ 锁内容**未被覆盖**', after == other,
            'after=%r' % (after[:80],))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── 看门狗：锁被抢 ⇒ 记 lock_lost 且不覆盖别人的锁 ─────────────
    tmp = tempfile.mkdtemp(prefix='app231_c4_')
    try:
        lock = os.path.join(tmp, 'MACHINE_LOCK')
        events = os.path.join(tmp, 'events.jsonl')
        mod = load_module(lock, events)
        mine = 'app %d 2026-11-24 00:00:00 mine' % os.getpid()
        with open(lock, 'w', encoding='utf-8') as f:
            f.write(mine)
        mod.start_lock_watchdog(mine)
        time.sleep(0.3)
        stolen = 'app 999999 2026-11-24 00:00:00 other-module'
        with open(lock, 'w', encoding='utf-8') as f:
            f.write(stolen)
        time.sleep(22)               # 看门狗周期 20 s ⇒ 等它跑一轮
        mod.stop_lock_watchdog()
        time.sleep(0.5)
        after = open(lock, encoding='utf-8').read()
        kinds = [e.get('event') for e in read_events(events)]
        chk('看门狗：锁被抢 ⇒ 记 lock_lost 事件', 'lock_lost' in kinds,
            'events=%r' % (kinds,))
        chk('看门狗：锁被抢 ⇒ **不覆盖**别人的锁', after == stolen,
            'after=%r' % (after[:80],))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── 放锁：只删自己的 ──────────────────────────────────────────
    tmp = tempfile.mkdtemp(prefix='app231_c5_')
    try:
        lock = os.path.join(tmp, 'MACHINE_LOCK')
        events = os.path.join(tmp, 'events.jsonl')
        mod = load_module(lock, events)
        stolen = 'app 999999 2026-11-24 00:00:00 other-module'
        with open(lock, 'w', encoding='utf-8') as f:
            f.write(stolen)
        mod.release_lock('app 12345 not-mine')
        after = open(lock, encoding='utf-8').read()
        chk('放锁：内容不是自己的 ⇒ 不删别人的锁', after == stolen,
            'after=%r' % (after[:80],))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_pass = sum(1 for c in checks if c['pass'])
    rep = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'target': TARGET,
           'checks': checks, 'n_pass': n_pass, 'n_fail': len(checks) - n_pass,
           'race_create_new': new_c, 'race_create_old': old_c,
           'race_hold': hold}
    os.makedirs(RESULTS, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('\n%d/%d PASS  ⇒ %s' % (n_pass, len(checks), OUT))
    return 0 if n_pass == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
