# -*- coding: utf-8 -*-
"""APP-071(c) 门槛选型探针（**纯 CPU / 只读**，不加载模型、不占设备）。

## 目的
APP-071 (c) 要求：「只用 spk_conf ≥ 阈值且该说话人**连续**干净 ≥ 2.5 s 的音频登记
（阈值写进 STATUS，并说明依据）；切换边界前后 0.5 s 不取」。

⇒ 本探针用 **app250 设备实测的 seg 表**（45 段，含 `spk` / `spk_conf` / `t0` / `t1`）
   回答两个问题：
   1. 各阈值下，**每个 spk 的最长「连续合格段」**有多长？
      ⇒ 能不能满足「连续 ≥ 2.5 s」？
   2. **错误登记**（用切换边界那一段登记）是否被阈值挡住？
      ⇒ S2 的首现段（seg 1，9.6–19.2 s，`spk_conf=0.1292`）在哪个阈值下被排除？

## 口径说明（必须写进 STATUS）
- 段的「干净区间」用该段的 `[t0, t1)` 近似（ASR 侧 `clean_ranges` 是段内
  `p_speech>=0.5` 的连续子区间 ⊂ 段跨度 ⇒ 本探针取**上界**）。
- 「连续」= 时间轴上**相邻且都合格**的段连成的一整段（中间不夹不合格段）。
- 切换边界取「相邻两段 spk 不同」处的**中点**（保守）。

## 输出
`_app292_threshold_probe.json`（供 STATUS 引用）
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SEG = os.path.join(REPO, 'results', 'app', 'app250_device_out',
                   'tts_on_clone_1.seg.jsonl')
OUT = os.path.join(HERE, '_app292_threshold_probe.json')

THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
REG_MIN_S = 2.5
BOUNDARY_GUARD_S = 0.5


def load_rows():
    rows = []
    with open(SEG, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get('spk') and r.get('t0') is not None \
                    and r.get('t1') is not None:
                rows.append(r)
    rows.sort(key=lambda r: (float(r['t0']), int(r['seg'])))
    return rows


def switch_points(rows):
    """相邻两段 spk 不同 ⇒ 切换点 = 两段交界的中点。"""
    pts = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if a['spk'] != b['spk']:
            pts.append(round((float(a['t1']) + float(b['t0'])) / 2.0, 4))
    return pts


def longest_qualified_run(rows, spk, thr, pts):
    """该 spk 在阈值 thr 下**最长连续合格段**（秒）+ 明细。"""
    qs = [r for r in rows if r['spk'] == spk
          and (r.get('spk_conf') or 0.0) >= thr]
    qs.sort(key=lambda r: float(r['t0']))
    runs = []
    cur = []
    for r in qs:
        if cur:
            prev = cur[-1]
            gap = float(r['t0']) - float(prev['t1'])
            # 中间夹了别的段 ⇒ 不连续
            if gap > 1e-6:
                runs.append(cur)
                cur = []
        cur.append(r)
    if cur:
        runs.append(cur)

    best = None
    for run in runs:
        # 边界守卫：切换点前后 0.5 s 不取
        total = 0.0
        detail = []
        for r in run:
            a, b = float(r['t0']), float(r['t1'])
            for p in pts:
                if p - BOUNDARY_GUARD_S < b and a < p + BOUNDARY_GUARD_S:
                    if a < p - BOUNDARY_GUARD_S:
                        total += max(0.0, (p - BOUNDARY_GUARD_S) - a)
                        detail.append((r['seg'], round(a, 3),
                                       round(p - BOUNDARY_GUARD_S, 3)))
                    if b > p + BOUNDARY_GUARD_S:
                        total += max(0.0, b - (p + BOUNDARY_GUARD_S))
                        detail.append((r['seg'], round(p + BOUNDARY_GUARD_S, 3),
                                       round(b, 3)))
                    a = max(a, p + BOUNDARY_GUARD_S)
                    b = min(b, p - BOUNDARY_GUARD_S)
                    if b <= a:
                        break
            if b > a:
                total += (b - a)
                detail.append((r['seg'], round(a, 3), round(b, 3)))
        if best is None or total > best[0]:
            best = (total, [d[0] for d in detail], detail)
    return best or (0.0, [], [])


def main():
    rows = load_rows()
    pts = switch_points(rows)
    out = {
        'script': os.path.basename(__file__),
        'correction': 'APP-071 (c) 门槛选型（纯 CPU 只读探针）',
        'seg_jsonl': {'path': SEG, 'n_rows': len(rows)},
        'criteria': {
            'reg_min_cont_s': REG_MIN_S,
            'boundary_guard_s': BOUNDARY_GUARD_S,
            'thresholds': THRESHOLDS,
        },
        'switch_points': pts,
        'per_spk': {},
    }
    spks = sorted(set(r['spk'] for r in rows))
    for thr in THRESHOLDS:
        per = {}
        for spk in spks:
            rs = [r for r in rows if r['spk'] == spk]
            total, segs, detail = longest_qualified_run(rows, spk, thr, pts)
            per[spk] = {
                'n_segments': len(rs),
                'first_seg': rs[0]['seg'] if rs else None,
                'first_seg_conf': rs[0].get('spk_conf') if rs else None,
                'conf_max': max((r.get('spk_conf') or 0.0) for r in rs)
                if rs else None,
                'longest_cont_s': round(total, 3),
                'meets_reg_min': bool(total >= REG_MIN_S),
                'used_segs': segs,
            }
        out['per_spk'][str(thr)] = per

    # 阈值能否挡住「错误登记」：S2 首现段（切换边界那一段）
    bad = {}
    for spk in spks:
        rs = [r for r in rows if r['spk'] == spk]
        if not rs:
            continue
        first = rs[0]
        # 首现段是否**就是**切换边界那一段（前一段 spk 不同）
        idx = rows.index(first)
        is_boundary = idx > 0 and rows[idx - 1]['spk'] != spk
        bad[spk] = {
            'first_seg': first['seg'],
            'first_seg_conf': first.get('spk_conf'),
            'first_seg_is_switch_boundary': bool(is_boundary),
            'excluded_at': [t for t in THRESHOLDS
                            if (first.get('spk_conf') or 0.0) < t],
        }
    out['first_appearance'] = bad

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('== 阈值 × 每 spk 最长连续合格段（秒）｜门槛 %.1f s ==' % REG_MIN_S)
    hdr = 'thr   ' + ''.join('%-22s' % s for s in spks)
    print(hdr)
    for thr in THRESHOLDS:
        line = '%-5.1f ' % thr
        for spk in spks:
            v = out['per_spk'][str(thr)][spk]
            line += '%-22s' % ('%.2f%s' % (v['longest_cont_s'],
                                          '*' if v['meets_reg_min'] else ' '))
        print(line)
    print('\n* = 达到 2.5 s 连续门槛')
    print('\n== 首现段（错误登记风险点）==')
    for spk, v in bad.items():
        print('  %s first_seg=%s conf=%s 切换边界=%s 阈值>=%.1f 时被排除'
              % (spk, v['first_seg'], v['first_seg_conf'],
                 v['first_seg_is_switch_boundary'],
                 max(v['excluded_at']) if v['excluded_at'] else -1))
    print('\nOUT = %s' % OUT)


if __name__ == '__main__':
    main()
