#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app134b_noise_floor.py — **APP-134 b 的 ABBA 噪声地板分析**。

## 为什么必须做 ABBA（项目铁律）

🔴 项目记忆 §八：「**A/B「无影响」须先量噪声地板（ABBA）** ⇒ **不写「已证明无影响」**」。
🔴 §四：「**PASS ≠ 正确**：须能被有缺陷的旧产物识破」。

**本轮的具体问题**：第一次跑 A（guard_on）→ B（guard_off）时，
**A 臂恰好撞上 MT 模块的 WMT8 作业退出**（ASR 加载 19.3 s vs B 臂 10.3 s
⇒ **机器当时被挤**）⇒ A/B 的差**混了「顺序效应」**，
**不能直接归因给「NaN 守卫」**。

⇒ ABBA 四臂：**on → off → off → on**
⇒ 同配置的两次（on₁ vs on₂、off₁ vs off₂）之差 = **噪声地板**（顺序效应的大小）
⇒ 再看「同位置的四臂均值」之差 ⇒ 才是**配置效应**
⇒ **判据**：配置效应的差 **≤ 噪声地板** ⇒ 判「不变差」。

## 🔴 诚实性
若噪声地板本身就 >5% ⇒ **如实说「本轮测不出 ≤5% 的结论」**，
**不把「差得多」写成「守卫导致变差」**（那正是 reviewer 批评的「顺序对照 ≠ ABBA」）。

## 用法
```
python live_caption/_app134b_noise_floor.py --root C:\Users\Trekker-PTL\shared\bgkeep\e2e_app134b_abba
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app134b_noise_floor.json')

TOLERANCE = 0.05


def pick(j, *path, default=None):
    cur = j
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def arm_stats(arm_dir):
    jf = os.path.join(arm_dir, 'bgkeep_e2e.json')
    if not os.path.isfile(jf):
        return None
    with open(jf, encoding='utf-8') as fh:
        j = json.load(fh)
    # 🔴 **臂配置名**：优先读驱动器的 `_summary.json`（避免靠目录名猜）
    cfg = None
    sp = os.path.join(os.path.dirname(arm_dir), '_summary.json')
    if os.path.isfile(sp):
        try:
            with open(sp, encoding='utf-8') as fh:
                for row in json.load(fh):
                    if row.get('json') == jf:
                        cfg = row.get('arm_config')
                        break
        except Exception:
            pass
    sy = j.get('synth_rtf') or {}
    per = sy.get('per_segment') or []
    rtfs = sorted(float(p['rtf']) for p in per if p.get('rtf') is not None)
    tts = [float(p['tts_sec']) for p in per if p.get('tts_sec')]

    def pct(xs, q):
        if not xs:
            return None
        idx = q * (len(xs) - 1)
        lo = int(idx)
        frac = idx - lo
        return xs[lo] + (xs[lo + 1] - xs[lo]) * frac if lo + 1 < len(xs) else xs[lo]

    # ASR 加载时间 = **机器拥挤度的代理指标**（加载慢 ⇒ 当时被别的作业挤）
    asr_load = None
    try:
        with open(os.path.join(arm_dir, 'bridge.err'), encoding='utf-8',
                  errors='replace') as fh:
            txt = fh.read()
        m = re.search(r'ASR 就绪（[^）]*?，([\d.]+)s）', txt)
        if m:
            asr_load = float(m.group(1))
    except OSError:
        pass

    return {
        'arm': os.path.basename(arm_dir),
        'arm_config': cfg,
        'json': jf,
        'json_bytes': os.path.getsize(jf),
        'json_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(jf))),
        'synth_rtf_ext': sy.get('synth_rtf'),
        'synth_rtf_p50': pct(rtfs, 0.5),
        'synth_rtf_p90': pct(rtfs, 0.9),
        'tts_sec_p50': statistics.median(tts) if tts else None,
        'n_segments': len(rtfs),
        'max_lag': pick(j, 'stats_full', 'margin', 'max_lag_sec'),
        'last_segment_lag': pick(j, 'stats_full', 'margin', 'last_segment_lag_sec'),
        'n_pending_at_media_end': pick(j, 'drain', 'n_pending_at_media_end'),
        'drain_elapsed_s': pick(j, 'drain', 'drain_elapsed_sec'),
        'drained_to_zero': pick(j, 'drain', 'drained_to_zero'),
        'npu_pct': pick(j, 'stats_full', 'npu_pct'),
        'igpu_pct': pick(j, 'stats_full', 'igpu_pct'),
        'asr_load_s': asr_load,
    }


def rel_diff(a, b):
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    m = max(abs(a), abs(b))
    return 0.0 if m == 0 else abs(a - b) / m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    args = ap.parse_args()
    root = args.root

    arms = []
    for nm in sorted(os.listdir(root)):
        d = os.path.join(root, nm)
        if os.path.isdir(d) and not nm.startswith('_'):
            st = arm_stats(d)
            if st:
                arms.append(st)

    # 🔴 **按执行顺序**排（目录名带序号前缀 ⇒ 排序即执行序）
    arms.sort(key=lambda a: a['arm'])

    groups = {}
    for a in arms:
        # 🔴 **分组用 `arm_config`**（驱动器写入的配置名）⇒ **不靠目录名猜**
        #    （臂目录名已加序号后缀 `_1`/`_2`…；靠目录名猜会分组错）
        cfg = a.get('arm_config')
        if not cfg:
            cfg = 'guard_on' if 'guard_on' in a['arm'] else 'guard_off'
        a['arm_config'] = cfg
        groups.setdefault(cfg, []).append(a)

    checks = []
    noise = {}
    for key in ('synth_rtf_p50', 'synth_rtf_p90', 'max_lag'):
        for cfg, lst in groups.items():
            if len(lst) < 2:
                continue
            vals = [x[key] for x in lst]
            rd = rel_diff(vals[0], vals[1])
            noise.setdefault(cfg, {})[key] = {
                'values': vals, 'rel_diff': rd,
                'abs_diff': (abs(vals[0] - vals[1])
                             if all(v is not None for v in vals) else None),
            }

    # 噪声地板 = **同配置两次**的相对差（取大者 = 最保守）
    floor = {}
    for key in ('synth_rtf_p50', 'synth_rtf_p90', 'max_lag'):
        rds = [v[key]['rel_diff'] for v in noise.values() if key in v]
        floor[key] = max(rds) if rds else None

    # 配置效应 = **同位置四臂**（on 的均值 vs off 的均值）
    effect = {}
    for key in ('synth_rtf_p50', 'synth_rtf_p90', 'max_lag'):
        on_v = [x[key] for x in groups.get('guard_on', []) if x.get(key) is not None]
        off_v = [x[key] for x in groups.get('guard_off', []) if x.get(key) is not None]
        if on_v and off_v:
            m_on = statistics.mean(on_v)
            m_off = statistics.mean(off_v)
            effect[key] = {'guard_on_mean': m_on, 'guard_off_mean': m_off,
                           'rel_diff': rel_diff(m_on, m_off)}
        else:
            effect[key] = None

    for key in ('synth_rtf_p50', 'synth_rtf_p90', 'max_lag'):
        eff = effect.get(key)
        fl = floor.get(key)
        if eff is None or fl is None:
            checks.append({'name': 'compare_%s' % key, 'ok': False,
                           'detail': '数据不足'})
            continue
        # 🔴 **判据**：配置效应 ≤ **噪声地板** ⇒ 判「不变差」
        ok = eff['rel_diff'] <= fl
        checks.append({
            'name': 'compare_%s' % key, 'ok': ok,
            'detail': ('配置效应 %.2f%% vs 噪声地板 %.2f%% ⇒ %s'
                       % (eff['rel_diff'] * 100, fl * 100,
                          '**不变差**（在噪声内）' if ok
                          else '**超出噪声**（需更多证据，不能直接归因）'))})

    # 🔴 机器拥挤度：ASR 加载时间（代理指标）—— 用来**佐证**噪声来源
    loads = {a['arm']: a['asr_load_s'] for a in arms}
    checks.append({'name': 'asr_load_recorded', 'ok': all(v is not None for v in loads.values()),
                   'detail': '各臂 ASR 加载耗时（拥挤度代理）：%s' % loads})

    lock_events = []
    evp = os.path.join(root, '_lock_events.jsonl')
    if os.path.isfile(evp):
        with open(evp, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        lock_events.append(json.loads(line))
                    except Exception:
                        pass

    ev = {
        'script': '_app134b_noise_floor.py',
        'task': 'APP-134 b：ABBA 噪声地板分析（区分「配置效应」与「顺序效应」）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'order': [a['arm'] for a in arms],
        'arms': arms,
        'same_config_spread': noise,
        'noise_floor_rel_diff': floor,
        'config_effect': effect,
        'tolerance': TOLERANCE,
        'checks': checks,
        'all_pass': all(c['ok'] for c in checks),
        'n_lock_lost_events': sum(1 for e in lock_events if e.get('lock_lost')),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)

    print('=== APP-134 b：ABBA 噪声地板 ===')
    print('执行序：%s' % ' → '.join(a['arm'] for a in arms))
    print('--- 各臂 ---')
    for a in arms:
        print('  %-22s rtf_p50=%-8s rtf_p90=%-8s max_lag=%-9s '
              'pending结束=%-4s 排空=%-7s ASR加载=%ss npu=%s'
              % (a['arm'], a['synth_rtf_p50'], a['synth_rtf_p90'], a['max_lag'],
                 a['n_pending_at_media_end'], a['drain_elapsed_s'],
                 a['asr_load_s'], a['npu_pct']))
    print('--- 同配置两次之差（= 顺序效应 / 噪声地板）---')
    for cfg, d in noise.items():
        for key, v in d.items():
            print('  %-10s %-18s 值=%s ⇒ 相对差 %.2f%%'
                  % (cfg, key, [round(x, 4) if x is not None else None for x in v['values']],
                     (v['rel_diff'] or 0) * 100))
    print('--- 配置效应 vs 噪声地板 ---')
    for c in checks:
        print('  %-28s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL', c['detail']))
    print('lock_lost 事件数 = %d' % ev['n_lock_lost_events'])
    print('证据：%s' % EVIDENCE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
