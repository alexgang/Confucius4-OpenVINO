# -*- coding: utf-8 -*-
r"""app196_app053_batching_fix_test.py —— APP-053 的**单测 + 反证**（重写版）。

## 🔴 为什么重写（2026-11-01）

本脚本的**初版**是并发会话（08:15–11:50 未入库的在制品）留下的，它断言的
是「`SpeakerBridge.feed()` **自己**攒整窗」（检查 `b._feed_buf` /
`b._batching`）。

⇒ 但 APP-054 的修法把攒批**搬进了后台工作线程**
  （`feed()` 只入队 ⇒ **永不阻塞主循环**；攒批在 `_worker_loop()` 里做）。

⇒ 于是初版的断言对象**已经不存在** ⇒ 复跑时直接
  `TypeError: object of type 'NoneType' has no len()`
  ⇒ **脚本崩溃、证据不落盘**（这正是「判据自身过期」的典型形态）。

⇒ 重写后，本脚本只测**仍然存在、且确实属于 APP-053 的语义**：
**「段自身区间」的时间对齐口径**（`span_for_segment()`）
—— 即 APP-053 ①a「SpeakerTracker 的时间对齐：句子的 [start,end] 与
pyannote 段时间是不是同一时间基准」这条要求的落点。

## 它验证什么

APP-053 要求把「只往前借 2.5 s」的取值规则改成
**「段自身区间」**（起点 = 上一段的末）。

离线复算（同一 5 min 切片、同一套断句、ASR-029 的两道门槛）
⇒ 打标率 **41/46 = 89.13%** → **44/46 = 95.65%**（= ASR 真值）
（证据：`results/app/app193_app053_spk_frame_audit.json`）。

本脚本验证**规则本身**：

1. **T1 段自身区间**：`(prev_end, t_end)` 原样返回（不借、不猜）。
2. **T2 首段兜底**：`prev_end` 未知 ⇒ 退回「往前借」口径（**不猜**）。
3. **T3 倒退/越界**：口径不可信 ⇒ 退回借用（**不猜**）。
4. **T4 太短兜底**：段自身区间 < `min_s` ⇒ 退回借用。
5. **T5 反证**：**旧规则**（永远只借）**必然**给不出段自身区间
   ⇒ 判据必须能识破它。
6. **T6 反证**：`prev_end=None` 时**不得**返回 `(None, t_end)`
   （那会让 ASR 侧拿不到区间 ⇒ 永远打不上标签）。

## 🔴 纪律

* **不 import 被测模块的顶层**（顶层 numpy 会让 import 阶段 abort）
  ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间。
* **不跑推理、不占 GPU、不持机器锁**（纯逻辑单测）。
"""
from __future__ import annotations

import ast
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TARGET = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
OUT = os.path.join(REPO, 'results', 'app',
                   'app196_app053_batching_fix_evidence.json')

SR = 16000
MIN_S = 2.5          # `span_for_final` 的默认借用长度
SPAN_MIN_S = 2.5     # ASR 侧 `min_dur_s` 口径


def load_module():
    """用 `ast` + `exec` 把 `speaker_tracker.py` 载进独立命名空间。"""
    src = open(TARGET, encoding='utf-8').read()
    tree = ast.parse(src)
    body = [n for n in tree.body
            if not (isinstance(n, ast.ImportFrom)
                    and n.module == '__future__')]
    mod = ast.Module(body=body, type_ignores=[])
    ns = {'__name__': 'speaker_tracker_probe'}
    exec(compile(mod, TARGET, 'exec'), ns)
    return ns


def main():
    ns = load_module()
    checks = []

    span_final = ns['span_for_final']
    span_seg = ns.get('span_for_segment')

    checks.append(dict(
        name='T0 `span_for_segment()` 存在（APP-053 的时间对齐落点）',
        ok=(callable(span_seg)),
        detail=dict(has_span_for_segment=callable(span_seg))))

    if not callable(span_seg):
        n_pass = sum(1 for c in checks if c['ok'])
        out = dict(script='app196_app053_batching_fix_test.py',
                   correction='APP-053', target=TARGET, checks=checks,
                   n_pass=n_pass, n_fail=len(checks) - n_pass, verdict='FAIL')
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('结果：%d PASS / %d FAIL ⇒ FAIL' % (n_pass, len(checks) - n_pass))
        return 1

    # ── T1 段自身区间：原样返回（不借、不猜）────────────────────
    got = span_seg(30.0, prev_end=12.5)
    checks.append(dict(
        name='T1 段自身区间（起点 = 上一段末）原样返回',
        ok=(got == (12.5, 30.0)),
        detail=dict(got=list(got), expected=[12.5, 30.0])))

    # ── T2 首段兜底：`prev_end` 未知 ⇒ 退回借用（**不猜**）────────
    got2 = span_seg(30.0, prev_end=None)
    exp2 = span_final(30.0)
    checks.append(dict(
        name='T2 首段（prev_end 未知）退回「往前借」口径（不猜）',
        ok=(got2 == exp2 and got2[0] < got2[1]),
        detail=dict(got=list(got2), borrow=list(exp2))))

    # ── T3 倒退 / 越界 ⇒ 退回借用 ─────────────────────────────────
    got3 = span_seg(30.0, prev_end=35.0)      # 倒退
    got3b = span_seg(30.0, prev_end=-1.0)     # 越界
    checks.append(dict(
        name='T3 口径不可信（倒退/越界）⇒ 退回借用（不猜）',
        ok=(got3 == span_final(30.0) and got3b == span_final(30.0)),
        detail=dict(reversed_case=list(got3), invalid_case=list(got3b))))

    # ── T4 段自身区间太短 ⇒ 退回借用 ─────────────────────────────
    got4 = span_seg(30.0, prev_end=29.0)      # 只有 1.0 s < min_s
    checks.append(dict(
        name='T4 段自身区间 < min_s ⇒ 退回借用（保证 ≥ ASR 门槛）',
        ok=(got4 == span_final(30.0)
            and (got4[1] - got4[0]) >= SPAN_MIN_S - 1e-6),
        detail=dict(got=list(got4), borrow=list(span_final(30.0)),
                    min_s=SPAN_MIN_S)))

    # ── T5 反证：**旧规则**（永远只借）给不出段自身区间 ──────────
    old = span_final(30.0)                     # 旧实现：永远走借用口径
    old_pass = (old == (12.5, 30.0))
    checks.append(dict(
        name='T5 反证：旧规则（永远只借）必须 FAIL 同一判据',
        ok=(not old_pass),
        detail=dict(old_got=list(old), expected=[12.5, 30.0],
                    old_would_pass=old_pass)))

    # ── T6 反证：`prev_end=None` 时不得返回 `(None, t_end)` ───────
    null_case = (got2[0] is None or got2[1] is None)
    checks.append(dict(
        name='T6 反证：prev_end=None ⇒ 不得返回含 None 的区间',
        ok=(not null_case),
        detail=dict(got=list(got2), contains_none=null_case)))

    n_pass = sum(1 for c in checks if c['ok'])
    out = dict(
        script='app196_app053_batching_fix_test.py',
        correction='APP-053',
        purpose='验证「段自身区间」时间对齐口径（APP-053 ①a）'
                '＋ 2 条反证（旧规则必须 FAIL）',
        rewritten='2026-11-01：初版断言的「feed 自己攒整窗」已被 APP-054 '
                  '的「后台线程攒批」取代 ⇒ 断言对象过期 ⇒ 重写为'
                  '「时间对齐口径」这条仍然有效的语义',
        target=TARGET,
        load_method='ast + exec（不 import ⇒ 顶层 numpy 不会 abort）',
        constants=dict(SR=SR, MIN_S=MIN_S, SPAN_MIN_S=SPAN_MIN_S),
        checks=checks, n_pass=n_pass, n_fail=len(checks) - n_pass,
        verdict=('PASS' if n_pass == len(checks) else 'FAIL'),
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('=== APP-053 时间对齐口径单测（纯逻辑，不跑推理）===')
    for c in checks:
        print('  [%s] %s  %s' % ('PASS' if c['ok'] else 'FAIL',
                                  c['name'], c['detail']))
    print('结果：%d PASS / %d FAIL ⇒ %s'
          % (n_pass, len(checks) - n_pass, out['verdict']))
    print('产物 = %s' % OUT)
    return 0 if n_pass == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
