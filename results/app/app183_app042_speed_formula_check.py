#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app183 —— APP-042 加速倍率**公式一致性**复核（修掉 app182 的判据缺陷）。

🔴🔴🔴 **为什么必须有这个脚本（app182 的 FAIL 是「判据缺陷」，不是产品缺陷）**：

  `app182` 的判据①（「逐句 `speed` ≈ `clamp(1.0+(lag−3)×0.025, 1.0, 1.30)`」）
  **漏掉了 APP-042 公式里的两个已实现约束**：

    ① **步长限制 `MAX_STEP_CHANGE = 0.1`**（`live_caption/time_stretch.py`
       `speed_for_lag()` 的最后一步：`|target − prev_speed| ≤ 0.1`）
       ⇒ 实测第 1 句 `speed_lag_s = 11.411` ⇒ 公式值 `1.0+(11.411−3)×0.025 = 1.210`
       ⇒ 但 `prev_speed = 1.0` ⇒ 步长限制把它**压到 1.1**
       ⇒ `app182` 判它「未命中」⇒ **假 FAIL**。

    ② **降速滞回 `LAG_HYSTERESIS_S = 2.0`**
       ⇒ 「任何降速动作都要求 `lag < 2 s`」⇒ 公式值低于上一句时**保持上一句**。

  ⇒ 🔴 **MEMORY 铁律：「判据 PASS ≠ 判据正确」的反面同样成立
    ——「判据 FAIL」也可能是判据本身写错了。**
  ⇒ 本脚本**直接复用产品实现**（`live_caption/time_stretch.py::speed_for_lag`）
    做逐句重算 ⇒ **不再手抄公式** ⇒ 抄错风险归零。

🔴 **lag 字段口径（app182 的第二个缺陷）**：
  遥测里**同时有两个滞后字段**，语义不同：
    - `speed_lag_s` = **算速度那一刻**的滞后（= `speed_for_lag()` 的输入）★ 权威
    - `play_lag_s`  = **实际开播**那一刻的滞后（≥ `speed_lag_s`）
  ⇒ 核对「速度是不是按公式算出来的」**必须用 `speed_lag_s`**。

🔴 **纪律**：**纯离线**（只读 app179 的 jsonl）⇒ 不占机器锁、不跑推理、不碰 GPU。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# ── APP-042 公式常量（reviewer 明文规定，与产品实现一一对应）──────────────
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


def load_speed_for_lag():
    """🔴 **复用产品实现**，不手抄公式。

    ⚠️ 不能 `import` 被测模块（`time_stretch` 顶层 `import numpy`
    ⇒ 在没 numpy 的解释器里 import 阶段就 abort ⇒ **假 FAIL**）。
    ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间。
    """
    import ast
    src_path = os.path.join(REPO, 'live_caption', 'time_stretch.py')
    with open(src_path, encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # 🔴 只保留不引入第三方依赖的 import（numpy 顶层 import 会 abort）
            continue
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    keep.append(node)
                    break
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.ClassDef)):
            keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {'__name__': 'time_stretch_probe', '__file__': src_path}
    exec(compile(mod, src_path, 'exec'), ns)
    fn = ns.get('speed_for_lag')
    if not callable(fn):
        raise SystemExit('❌ 未能在 time_stretch.py 里找到 speed_for_lag()')
    return fn, src_path


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
    ap.add_argument('--falsify', action='store_true',
                    help='把 speed 全改成 1.0 ⇒ 判据①必须 FAIL（自检反证组）')
    args = ap.parse_args()

    jsonl = args.jsonl or r'C:\Users\Trekker-PTL\app051_gui_accel\gui_accel.tts.jsonl'
    if not os.path.isfile(jsonl):
        raise SystemExit('找不到遥测：%s' % jsonl)
    rows = load_rows(jsonl)
    print('[jsonl] %s  rows=%d' % (jsonl, len(rows)))

    speed_for_lag, src_path = load_speed_for_lag()
    print('[impl] 复用产品实现：%s :: speed_for_lag()' % src_path)

    # ── 收集样本：必须**同时**有 speed 与 speed_lag_s（算速度的滞后）─────
    data = []
    for r in rows:
        if r.get('speed') is None or r.get('speed_lag_s') is None:
            continue
        data.append((float(r['speed_lag_s']), float(r['play_lag_s'])
                     if r.get('play_lag_s') is not None else None,
                     float(r['speed'])))
    print('[data] 可用样本=%d（要求 speed + speed_lag_s 同时存在）' % len(data))
    if not data:
        raise SystemExit('没有同时含 speed 与 speed_lag_s 的样本')

    if args.falsify:
        data = [(a, b, 1.0) for a, b, c in data]
        print('[falsify] 🔴 已把全部 speed 改成 1.0 ⇒ 判据①**必须** FAIL')

    lags = [d[0] for d in data]
    speeds = [d[2] for d in data]
    print('  speed_lag_s 范围 = [%.3f, %.3f] s' % (min(lags), max(lags)))
    print('  speed        范围 = [%.4f, %.4f]' % (min(speeds), max(speeds)))
    print('  speed 取值集合 = %r' % sorted(set(round(s, 4) for s in speeds)))

    print('\n== 判据 ==')
    # ── ① 逐句重算（复用产品实现 ⇒ 含滞回 + 步长限制）──────────────
    prev = 1.0
    mism = []
    for lag, play_lag, sp in data:
        pred = float(speed_for_lag(lag, prev))
        if abs(sp - pred) > 1e-6:
            mism.append((lag, sp, round(pred, 6)))
        prev = sp
    check('① 逐句重算命中：speed == speed_for_lag(speed_lag_s, prev_speed)'
          '（**复用产品实现**，含滞回 + MAX_STEP_CHANGE 步长限制）',
          len(mism) == 0,
          '未命中 %d/%d 句；样例=(lag, 实测, 重算)=%r'
          % (len(mism), len(data), mism[:5]))

    # ── ①b 步长限制确实被观测到（否则①只是恒真）────────────────────
    #   找一对相邻句：公式值与上一句 speed 相差 > MAX_STEP_CHANGE
    #   ⇒ 说明「步长限制」这条路径真的被触发过。
    step_hits = []
    prev = 1.0
    for lag, play_lag, sp in data:
        raw = SPEED_MIN + (lag - LAG_DEADZONE_S) * SPEED_PER_LAG_S
        raw = max(SPEED_MIN, min(SPEED_MAX, raw))
        if abs(raw - prev) > MAX_STEP_CHANGE + 1e-9:
            step_hits.append((lag, round(prev, 4), round(raw, 4), sp))
        prev = sp
    check('①b 步长限制（MAX_STEP_CHANGE=%.2f）在本批遥测里**确实被触发**'
          % MAX_STEP_CHANGE,
          len(step_hits) > 0,
          '触发次数=%d  样例=(lag, prev, 公式值, 实测)=%r'
          % (len(step_hits), step_hits[:5]))

    # ── ② 合成场景：未饱和区间内 speed **能取到多个不同取值** ──────────
    #   🔴🔴🔴 **为什么必须用「合成场景」而不是「实测数据」**：
    #     本批 GUI 实测遥测的**最小滞后就有 11.411 s**
    #     ⇒ 公式值 = 1.0+(11.411−3)×0.025 = 1.2103 ⇒ 被**步长限制**压到 1.1
    #     ⇒ 第 2 句起 lag ≥ 20.798 ⇒ 公式值已 ≥ 1.30（**饱和**）
    #     ⇒ **实测数据里未饱和样本只有 1 个**
    #     ⇒ 「未饱和区间内要有 ≥2 种取值」在实测数据上**恒为假**
    #     ⇒ 这正是 app179「B4 分组阈值取错 ⇒ 低滞后组 n=0 ⇒ 恒真」的同一个坑
    #       在**另一个方向**上的重演（app179 是恒真、app182 是恒假）。
    #   ⇒ 解法：**用产品的 `speed_for_lag()` 本身**跑一遍**合成滞后序列**
    #     （lag 从 0 递增到饱和）⇒ 检验「实现」而非「这批数据」。
    #     ⚠️ 必须走**产品实现**（不是手抄公式）⇒ 若实现写错
    #       （死区算错 / 系数符号反了 / 上限写错）判据必 FAIL。
    synth_lags = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0,
                  12.0, 14.0, 16.0, 20.0, 30.0, 100.0]
    synth = []
    prev = 1.0
    for lag in synth_lags:
        sp = float(speed_for_lag(lag, prev))
        synth.append((lag, sp))
        prev = sp
    synth_speeds = sorted(set(round(s, 4) for _, s in synth))
    check('② 合成滞后序列（0→100 s）上 speed **能取到多个不同取值**'
          '（走**产品 speed_for_lag 实现**）',
          len(synth_speeds) >= 2,
          '合成 speed 取值=%r' % synth_speeds)

    # ── ②b 合成序列上 (lag, speed) **同向**（lag↑ ⇒ speed↑）────────────
    mono_pairs = 0
    bad_pairs = []
    for i in range(len(synth)):
        for j in range(i + 1, len(synth)):
            l1, s1 = synth[i]
            l2, s2 = synth[j]
            if l1 == l2 or s1 == s2:
                continue
            if (l2 - l1) * (s2 - s1) > 0:
                mono_pairs += 1
            else:
                bad_pairs.append((l1, s1, l2, s2))
    check('②b 合成序列上 (lag, speed) **同向**（lag↑ ⇒ speed↑）',
          len(bad_pairs) == 0 and mono_pairs > 0,
          '同向对=%d  反向对=%d %r' % (mono_pairs, len(bad_pairs),
                                       bad_pairs[:5]))

    # ── ②c 实测数据里未饱和样本的**覆盖情况**（**报告项，不判 FAIL**）──
    #   🔴 「实测未饱和样本 < 2」是**数据覆盖不足**，不是产品缺陷
    #   ⇒ 按 MEMORY 铁律「反证判据的前提不存在时必须优雅降级」
    #   ⇒ 这里**只报告**，不判负（否则会把「数据不够」误报成「产品错」）。
    unsat = []
    prev = 1.0
    for lag, play_lag, sp in data:
        raw = SPEED_MIN + (lag - LAG_DEADZONE_S) * SPEED_PER_LAG_S
        raw = max(SPEED_MIN, min(SPEED_MAX, raw))
        if raw < SPEED_MAX - 1e-9:
            unsat.append((lag, sp))
        prev = sp
    unsat_speeds = sorted(set(round(s, 4) for _, s in unsat))
    print('  [报告] 实测未饱和样本=%d（lag < %.1f s）speed 取值=%r'
          % (len(unsat), LAG_FULL_SPEED_S, unsat_speeds))
    print('  [报告] 实测最小 speed_lag_s=%.3f s ⇒ 该批遥测**整体处于饱和区**'
          ' ⇒ 实测侧无法证明同向性 ⇒ 改由 ②/②b 的**合成序列**证明'
          % min(lags))
    CHECKS.append({
        'name': '②c 实测未饱和样本覆盖（**报告项，不判负**）',
        'ok': True,
        'detail': '实测未饱和样本=%d speed 取值=%r；最小 lag=%.3f s ⇒ '
                  '该批遥测整体处于饱和区 ⇒ 同向性改由 ②/②b 合成序列证明'
                  % (len(unsat), unsat_speeds, min(lags)),
    })

    # ── ②d 公式在测试点上**非降**（构造性，与数据无关）───────────────
    test_lags = [0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 30.0, 100.0]
    fv = [float(speed_for_lag(l, 1.0)) for l in test_lags]
    non_decreasing = all(fv[i] <= fv[i + 1] for i in range(len(fv) - 1))
    check('②d 公式在测试点上**非降**（构造性，与数据无关）',
          non_decreasing,
          'lag→speed: %r' % list(zip(test_lags, fv)))

    # ── ③ 反证组：把 speed 全改成 1.0 ⇒ 判据①必须 FAIL ──────────────
    if not args.falsify:
        fake = []
        prev = 1.0
        for lag, play_lag, sp in data:
            pred = float(speed_for_lag(lag, prev))
            fake.append(abs(1.0 - pred) > 1e-6)
            prev = 1.0
        check('③ 反证：speed 全改 1.0 ⇒ 判据①必 FAIL',
              sum(fake) > 0,
              'fake 未命中=%d/%d（应 >0）' % (sum(fake), len(fake)))

    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-051② / APP-042 / APP-043（修掉 app182 的判据缺陷）',
        'jsonl': jsonl, 'n_rows': len(rows), 'n_samples': len(data),
        'impl': src_path,
        'impl_reused': 'live_caption/time_stretch.py::speed_for_lag（ast+exec，不手抄公式）',
        'formula': {
            'expr': 'speed_for_lag(lag, prev_speed)',
            'LAG_DEADZONE_S': LAG_DEADZONE_S,
            'LAG_FULL_SPEED_S': LAG_FULL_SPEED_S,
            'SPEED_PER_LAG_S': SPEED_PER_LAG_S,
            'SPEED_MIN': SPEED_MIN, 'SPEED_MAX': SPEED_MAX,
            'LAG_HYSTERESIS_S': LAG_HYSTERESIS_S,
            'MAX_STEP_CHANGE': MAX_STEP_CHANGE,
        },
        'lag_field': 'speed_lag_s（算速度那一刻的滞后 = speed_for_lag 的输入）',
        'lag_range': [min(lags), max(lags)],
        'speed_range': [min(speeds), max(speeds)],
        'speed_values': sorted(set(round(s, 4) for s in speeds)),
        'n_unsaturated': len(unsat),
        'unsat_speed_values': unsat_speeds,
        'n_step_limit_triggers': len(step_hits),
        'step_limit_samples': step_hits[:5],
        'n_mismatch_formula': len(mism),
        'mismatch_samples': mism[:10],
        'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
        'verdict': verdict,
        'note': 'app182 的 FAIL 是**判据缺陷**：① 漏 MAX_STEP_CHANGE 步长限制'
                '② 漏降速滞回 ③ 用 play_lag_s 而非 speed_lag_s；'
                '本脚本复用产品 speed_for_lag() 逐句重算，'
                '并新增①b「步长限制确实被触发」以证明①非恒真',
        'supersedes': 'results/app/app182_app042_formula_evidence.json（判据缺陷版）',
    }
    out = args.out or os.path.join(HERE,
                                    'app183_app042_formula_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % out)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
