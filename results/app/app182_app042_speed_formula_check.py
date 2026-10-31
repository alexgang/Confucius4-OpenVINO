#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app182 —— APP-042 加速倍率**公式一致性**独立复核（补 app179 的 B4 缺口）。

🔴🔴🔴 **为什么必须有这个脚本（app179 抓出的真缺陷）**：
  `app179` 的 B4 判据（「滞后越大 ⇒ 倍率越大（同向）」）**分组阈值取错了**：
    它按 `lag > 10` / `lag <= 10` 分组，而实测 22 句里
    **lag 最小值 = 18.786 s** ⇒ 低滞后组 **n = 0（空）**
    ⇒ 判据退化成「只有一组 ⇒ 恒真」⇒ **同向性根本没被验证**。
  （MEMORY 铁律：「判据 PASS ≠ 判据正确」⇒ 必须拿**已知有缺陷的旧产物**跑一遍。）

🔴 **正确的判据：按 APP-042 的公式本身核对**：
  reviewer 明文规定的公式（`status/app/STATUS_APP.md` §95 摘要）：
      `speed = clamp(1.0 + (lag − LAG_DEADZONE_S) × SPEED_PER_LAG_S, 1.0, 1.30)`
      常量：`LAG_DEADZONE_S = 3.0` / `LAG_FULL_SPEED_S = 15.0`
            / `SPEED_PER_LAG_S = 0.025` / `SPEED_MIN = 1.0` / `SPEED_MAX = 1.30`
            / `LAG_HYSTERESIS_S = 2.0` / `MAX_STEP_CHANGE = 0.1`
  ⇒ 判据 = **逐句**核对 `speed` 是否等于公式值（**滞回**与**步长限制**允许偏差，
    但必须**落在**允许区间内）。

🔴 **三条独立判据（互不替代）**：
  ① **公式命中**：对每句，`speed` 必须等于
     `clamp(1.0+(lag−3)×0.025, 1.0, 1.30)` 或其**滞回/步长**允许的邻近值；
     （本脚本用「公式值 ± 一档滞回」作为容差，并**报告**未命中的句子）
  ② **单调性**：**去掉** clamp 上界后，公式值随 lag **严格单调递增**
     ⇒ 在**未饱和**的区间（lag < 15 s ⇒ speed < 1.30）内必须能观察到
     **至少两个不同的 speed 值**（否则「同向」无从谈起）；
  ③ **反证**：把 `lag` 全部改成同一个值 ⇒ 判据②必须 FAIL
     ⇒ 证明判据②不是恒真。

🔴 **纪律**：**纯离线**（只读 app179 的 jsonl）⇒ 不占机器锁、不跑推理。
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── APP-042 公式常量（reviewer 明文规定）──────────────────────────
LAG_DEADZONE_S = 3.0
LAG_FULL_SPEED_S = 15.0
SPEED_PER_LAG_S = 0.025
SPEED_MIN = 1.0
SPEED_MAX = 1.30
LAG_HYSTERESIS_S = 2.0
MAX_STEP_CHANGE = 0.1

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:600]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


def formula_speed(lag):
    """按 APP-042 公式算目标倍率（**未含滞回与步长限制**）。"""
    v = SPEED_MIN + (lag - LAG_DEADZONE_S) * SPEED_PER_LAG_S
    return max(SPEED_MIN, min(SPEED_MAX, v))


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jsonl', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    jsonl = args.jsonl or r'C:\Users\Trekker-PTL\app051_gui_accel\gui_accel.tts.jsonl'
    if not os.path.isfile(jsonl):
        raise SystemExit('找不到遥测：%s' % jsonl)
    rows = load_rows(jsonl)
    print('[jsonl] %s  rows=%d' % (jsonl, len(rows)))

    # 有 speed / lag 的句子
    data = []
    for r in rows:
        if r.get('speed') is None or r.get('play_lag_s') is None:
            continue
        data.append((float(r['play_lag_s']), float(r['speed'])))
    print('[data] 可用样本=%d' % len(data))
    if not data:
        raise SystemExit('没有同时含 speed 与 play_lag_s 的样本')

    lags = [d[0] for d in data]
    speeds = [d[1] for d in data]
    print('  lag   范围 = [%.3f, %.3f] s' % (min(lags), max(lags)))
    print('  speed 范围 = [%.4f, %.4f]' % (min(speeds), max(speeds)))
    print('  speed 取值集合 = %r' % sorted(set(round(s, 4) for s in speeds)))

    print('\n== 判据 ==')
    # ① 公式命中（容差 = 滞回造成的 1 档偏差）
    #    滞回：lag 下降 2 s 内保持上一档 ⇒ 公式值最多偏 1 档
    #    步长：相邻句 ≤ 0.1× ⇒ 也可能差 1 档
    #    ⇒ 容差取 **1 档**（0.1）
    STEP = MAX_STEP_CHANGE + 1e-6
    mism = []
    for lag, sp in data:
        f = formula_speed(lag)
        if abs(sp - f) > STEP + 1e-9:
            mism.append((lag, sp, f))
    check('① 逐句公式命中：speed ≈ clamp(1.0+(lag−3)×0.025, 1.0, 1.30)',
          len(mism) == 0,
          '未命中 %d/%d 句（容差 ±%.2f）；样例=%r'
          % (len(mism), len(data), STEP, mism[:5]))

    # ② 单调性：未饱和区间内必须有 ≥2 个不同 speed
    sat = [(l, s) for l, s in data if l < LAG_FULL_SPEED_S]
    unsat_speeds = sorted(set(round(s, 4) for l, s in sat))
    check('② 未饱和区间（lag < %.0f s）内 speed **有多个不同取值**'
          % LAG_FULL_SPEED_S,
          len(unsat_speeds) >= 2,
          '未饱和样本=%d  speed 取值=%r'
          % (len(sat), unsat_speeds))

    # ②b 公式在未饱和区间严格单调（构造性证明 + 数据核对）
    mono_pairs = 0
    bad_pairs = []
    for i in range(len(sat)):
        for j in range(i + 1, len(sat)):
            l1, s1 = sat[i]
            l2, s2 = sat[j]
            if l1 == l2:
                continue
            if s1 == s2:
                bad_pairs.append((l1, s1, l2, s2))
            else:
                if (l2 - l1) * (s2 - s1) > 0:
                    mono_pairs += 1
                else:
                    bad_pairs.append((l1, s1, l2, s2))
    check('②b 未饱和区间内 (lag, speed) **同向**（lag↑ ⇒ speed↑）',
          len(bad_pairs) == 0,
          '同向对=%d  反向对=%d %r' % (mono_pairs, len(bad_pairs),
                                       bad_pairs[:5]))

    # ②c 公式值本身随 lag 严格递增（构造性）
    test_lags = [0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 30.0, 100.0]
    fv = [formula_speed(l) for l in test_lags]
    strictly_increasing = all(fv[i] <= fv[i + 1] for i in range(len(fv) - 1))
    check('②c 公式在测试点上**非降**（构造性，与数据无关）',
          strictly_increasing,
          'lag→speed: %r' % list(zip(test_lags, fv)))

    # ③ 反证：把 lag 全改成同一个值 ⇒ 判据②必须 FAIL
    fake = [(5.0, s) for l, s in data]
    fake_sat = [(l, s) for l, s in fake if l < LAG_FULL_SPEED_S]
    fake_speeds = sorted(set(round(s, 4) for l, s in fake_sat))
    check('③ 反证：lag 全改同一值 ⇒ 判据②必 FAIL',
          len(fake_speeds) < 2,
          'fake 未饱和 speed 取值=%r（应 <2 ⇒ ②为假）' % fake_speeds)

    # ④ 反证：把 speed 全改成 1.0 ⇒ ① 必须 FAIL
    fake2 = [(l, 1.0) for l, s in data]
    mism2 = [(l, s, formula_speed(l)) for l, s in fake2
             if abs(s - formula_speed(l)) > STEP + 1e-9]
    check('④ 反证：speed 全改 1.0 ⇒ 判据①必 FAIL',
          len(mism2) > 0,
          'fake 未命中=%d/%d（应 >0）' % (len(mism2), len(fake2)))

    # ⑤ 反证：把 lag 改成与 speed 反向（lag 越大 speed 越小）⇒ ②b 必须 FAIL
    fake3 = [(l, s) for l, s in data]
    fake3 = [(l, SPEED_MAX if s < SPEED_MAX else SPEED_MIN) for l, s in fake3]
    fake3_sat = [(l, s) for l, s in fake3 if l < LAG_FULL_SPEED_S]
    bad3 = []
    for i in range(len(fake3_sat)):
        for j in range(i + 1, len(fake3_sat)):
            l1, s1 = fake3_sat[i]
            l2, s2 = fake3_sat[j]
            if l1 == l2 or s1 == s2:
                continue
            if (l2 - l1) * (s2 - s1) <= 0:
                bad3.append((l1, s1, l2, s2))
    check('⑤ 反证：speed 反向 ⇒ 判据②b 必 FAIL',
          len(bad3) > 0,
          'fake 反向对=%d（应 >0）' % len(bad3))

    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-051② / APP-042 / APP-043（补 app179 的 B4 缺口）',
        'jsonl': jsonl, 'n_rows': len(rows), 'n_samples': len(data),
        'formula': {
            'expr': 'clamp(1.0 + (lag - 3.0) * 0.025, 1.0, 1.30)',
            'LAG_DEADZONE_S': LAG_DEADZONE_S,
            'LAG_FULL_SPEED_S': LAG_FULL_SPEED_S,
            'SPEED_PER_LAG_S': SPEED_PER_LAG_S,
            'SPEED_MIN': SPEED_MIN, 'SPEED_MAX': SPEED_MAX,
            'LAG_HYSTERESIS_S': LAG_HYSTERESIS_S,
            'MAX_STEP_CHANGE': MAX_STEP_CHANGE,
            'tolerance': STEP,
        },
        'lag_range': [min(lags), max(lags)],
        'speed_range': [min(speeds), max(speeds)],
        'speed_values': sorted(set(round(s, 4) for s in speeds)),
        'n_unsaturated': len(sat),
        'unsat_speed_values': unsat_speeds,
        'n_mismatch_formula': len(mism),
        'mismatch_samples': mism[:10],
        'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
        'verdict': verdict,
        'note': '补 app179 的 B4 缺口：app179 按 lag>10 分组 ⇒ 低滞后组 n=0 ⇒ '
                '同向性退化为恒真；本脚本按 APP-042 公式逐句核对 + '
                '在未饱和区间( lag<15s )验证单调性 + 三条反证',
    }
    out = args.out or os.path.join(HERE,
                                    'app182_app042_formula_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % out)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
