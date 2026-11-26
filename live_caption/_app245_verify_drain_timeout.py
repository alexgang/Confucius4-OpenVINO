#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app245_verify_drain_timeout.py — **§245 排空超时语义改动的行为级验证**。

## 要证明的事（4 条，全 PASS 才算成立）

| # | 判据 | 期望 |
|---|---|---|
| 1 | `tolerate_one_timeout_then_drain` | 第一次 `stats` 不回、之后回 `n_pending=0` ⇒ **排空成功**、`n_timeouts=1`、`disconnected is None` |
| 2 | `old_code_fails_same_scenario` | **反证**：把 §245 的 `continue` 还原成 `break`（旧逻辑）⇒ 同一场景 **排空失败** ⇒ 证明判据有鉴别力 |
| 3 | `hard_cap_still_enforced` | `stats` **永远不回** ⇒ 仍在 `hard_cap` 附近退出（`drain_hard_cap_hit=True`）⇒ APP-143 b ② 没被破坏 |
| 4 | `real_disconnect_exits_fast` | 非超时的**真断连**（`ConnectionResetError`）⇒ **立即**退出、`n_timeouts=0`（原行为不变） |

## 做法
**不连真桥接、不占机器锁**：用**假 ws 对象**（`send()` 里按剧本回/不回/抛异常），
直接真跑 `_app137_e2e_drain.drain_until_zero()`（APP-143 b 抽出来的独立函数）。

## 纪律
🔴 不碰客户包；🔴 不占机器锁（纯内存 + 本地计时）。
"""
from __future__ import annotations

import asyncio
import copy
import importlib.util
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app245_drain_timeout_verify.json')
DRAIN = os.path.join(HERE, '_app137_e2e_drain.py')


class Args(object):
    def __init__(self, drain_cap=30.0, stats_timeout_s=1.0, poll_sec=0.2):
        self.drain_cap = drain_cap
        self.stats_timeout_s = stats_timeout_s
        self.poll_sec = poll_sec


class SilentWS(object):
    """第一次 `stats` 不回（模拟桥接应答慢），之后回 `n_pending=0`。"""
    def __init__(self, got):
        self.got = got
        self.n = 0

    async def send(self, raw):
        self.n += 1
        if self.n == 1:
            return                      # 🔴 故意不回 ⇒ 客户端要靠自己的超时发现
        self.got['stats'] = {'type': 'stats',
                             'pipeline': {'n_pending': 0, 'n_emitted': 3,
                                          'n_submitted': 3}}
        self.got['_last_stats_at'] = time.perf_counter()


class DeadWS(object):
    """`stats` 永远不回（模拟真卡死的桥接）。"""
    async def send(self, raw):
        return


class BrokenWS(object):
    """发 `stats` 就断连（不是超时）。"""
    async def send(self, raw):
        raise ConnectionResetError('模拟对端断开')


def _load_drain(name, path=None):
    p = path or DRAIN
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _old_source():
    """把 §245 的新分支还原成旧分支（`continue` → `break`），得到**旧逻辑**源码。"""
    with io.open(DRAIN, encoding='utf-8', newline='') as fh:
        src = fh.read()
    anchor = ("                if time.perf_counter() - drain_start >= hard_cap:\n"
              "                    got['drain_hard_cap_hit'] = True\n"
              "                    disconnected = last_timeout\n"
              "                    break\n"
              "                await asyncio.sleep(a.poll_sec)\n"
              "                continue")
    old = ("                disconnected = last_timeout\n"
           "                break")
    assert src.count(anchor) == 1, '已还原过？锚点命中 %d 次' % src.count(anchor)
    return src.replace(anchor, old, 1)


async def _run(mod, ws_factory, args, npend_end=2):
    """🔴 `ws_factory(got)` ⇒ 假 ws 必须写**同一份** `got`（否则读不到统计）。"""
    got = {}
    ws = ws_factory(got)
    t0 = time.perf_counter()
    res = await mod.drain_until_zero(ws, got, args, t0, npend_end)
    return round(time.perf_counter() - t0, 2), res, got


def main():
    checks = []
    detail = {}
    drain_new = _load_drain('drain_app245_new')

    # ── 1) 新逻辑：一次超时后仍排空 ──────────────────────────────────
    args = Args(drain_cap=30.0, stats_timeout_s=1.0, poll_sec=0.2)
    el1, res1, got1 = asyncio.run(_run(drain_new, SilentWS, args))
    _series, drained1, dis1, npend1, sto, hc, nto1 = res1
    checks.append({'name': 'tolerate_one_timeout_then_drain',
                   'ok': drained1 is True and nto1 == 1 and dis1 is None and npend1 == 0,
                   'detail': 'drained=%s n_timeouts=%s disconnected=%r n_pending=%s '
                             'elapsed=%.2fs hard_cap=%.1fs'
                             % (drained1, nto1, dis1, npend1, el1, hc)})
    detail['case1_timeout_events'] = got1.get('drain_timeout_events')

    # ── 2) 反证：旧逻辑（超时即 break）在同一场景必须失败 ────────────
    tmp = os.path.join(RESULTS, '_app245_old_drain.py')
    os.makedirs(RESULTS, exist_ok=True)
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(_old_source())
    try:
        drain_old = _load_drain('drain_app245_old', tmp)
        el2, res2, _got2 = asyncio.run(_run(drain_old, SilentWS, copy.copy(args)))
        _s2, drained2, dis2, npend2, _sto2, _hc2, nto2 = res2
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    checks.append({'name': 'old_code_fails_same_scenario',
                   'ok': drained2 is False and nto2 == 1 and npend2 == 2,
                   'detail': 'old: drained=%s n_timeouts=%s n_pending=%s disconnected=%r '
                             'elapsed=%.2fs（新逻辑同场景 drained=True）'
                             % (drained2, nto2, npend2, dis2, el2)})

    # ── 3) 硬上限兜底：永远不回 ⇒ 仍在 hard_cap 附近退出 ─────────────
    a3 = Args(drain_cap=1.0, stats_timeout_s=0.5, poll_sec=0.2)
    el3, res3, got3 = asyncio.run(_run(drain_new, lambda g: DeadWS(), a3))
    _s3, drained3, dis3, _np3, _sto3, hc3, nto3 = res3
    ok3 = (drained3 is False and got3.get('drain_hard_cap_hit') is True
           and el3 <= hc3 + 1.5)
    checks.append({'name': 'hard_cap_still_enforced', 'ok': ok3,
                   'detail': 'drained=%s hard_cap_hit=%s n_timeouts=%s '
                             'elapsed=%.2fs ≤ hard_cap %.1fs + 1.5s'
                             % (drained3, got3.get('drain_hard_cap_hit'), nto3,
                                el3, hc3)})

    # ── 4) 真断连：立即退出，不算超时 ────────────────────────────────
    el4, res4, _got4 = asyncio.run(_run(drain_new, lambda g: BrokenWS(), copy.copy(args)))
    _s4, drained4, dis4, _np4, _sto4, _hc4, nto4 = res4
    checks.append({'name': 'real_disconnect_exits_fast',
                   'ok': (drained4 is False and nto4 == 0 and dis4 is not None
                          and el4 < 2.0),
                   'detail': 'drained=%s n_timeouts=%s disconnected=%r elapsed=%.2fs'
                             % (drained4, nto4, dis4, el4)})

    # ── 5) 字段透传：`drain{}` 里要有 drain_timeout_events ────────────
    with io.open(DRAIN, encoding='utf-8', newline='') as fh:
        src = fh.read()
    checks.append({'name': 'field_passthrough_drain_timeout_events',
                   'ok': "'drain_timeout_events': got.get('drain_timeout_events', [])" in src,
                   'detail': 'run_drain 的 drain{} 字典含该字段'})

    ok = all(c['ok'] for c in checks)
    ev = {
        'script': '_app245_verify_drain_timeout.py',
        'task': '§245：单次 stats 超时不再中止排空（APP-150 §2 门禁可判）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'target': DRAIN,
        'cases': checks,
        'case1_detail': detail,
        'all_pass': ok,
        'note': '🔴 假 ws（内存），不连桥接、不占机器锁；反证组＝把 continue 还原成 break。',
    }
    with io.open(EVIDENCE + '.tmp', 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(EVIDENCE + '.tmp', EVIDENCE)

    print('=== §245 排空超时语义验证 ===')
    for c in checks:
        print('  %-38s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    print('证据：%s' % EVIDENCE)
    print('ALL PASS' if ok else 'FAIL')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
