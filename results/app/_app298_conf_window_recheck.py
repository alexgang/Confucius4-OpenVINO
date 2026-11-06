# -*- coding: utf-8 -*-
"""APP-075(c)：**用第二份材料复验 `REG_CONF_MIN` 的可行窗口**。

## 为什么需要（reviewer 原话）
> (c) 门限依据只来自单个 5 分钟样本（0.3217<th≤0.6）。
>     请再用第二份材料（另一段 SPE 或中英混合）复验窗口，或在 STATUS 注明这是单样本结论；

## 本脚本做什么（**纯 CPU / 只读 / 不占设备**）
用 **ASR-122 的 900 s 评测集**（3 clip / 136 段 / 26 换人点）复验：

1. **首现段（`is_new_spk=True`）的 `spk_conf` 分布**
   ⇒ 原样本的结论「必须 > 0.3217 才能挡住三处高危首现段」
   ⇒ 在这份材料里**是否仍成立**？
2. **窗口上界**：门槛再高，该 spk 是否**永远攒不够 2.5 s 连续合格音频**
   ⇒ 原样本的结论「必须 ≤ 0.6」
   ⇒ 在这份材料里**是否仍成立**？
3. **下限的可证伪性**：门槛取值 `th` ⇒ 能挡住的「高危首现段」数 / 放过的数。

## 🔴 口径声明（必须诚实）
本材料 `asr122_asr050_regression.json` 的 rows **只有 `spk_conf` / `n_clean_ranges`**，
**没有 `clean_ranges` 的具体区间** ⇒
⇒ **本脚本只能复验「conf 门槛」这一个维度**，
⇒ **不能**用它复验「连续 ≥2.5 s」与「切换点守卫」（那需要真实 clean 区间）。
⇒ 结论只能写成「**conf 维度**在第二份材料上复验通过/不通过」。

## 用法
```
python results/app/_app298_conf_window_recheck.py
```
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import speaker_voice as sv                                  # noqa: E402

ASR122 = (r'C:\Users\Trekker-PTL\qwen3asr_06b\results\pyannote_seg'
          r'\asr122_asr050_regression.json')
OUT = os.path.join(HERE, '_app298_conf_window_recheck.json')

# 🔴 第一份材料的结论（`results/app/_app292_threshold_probe.json` 的口径）
BASE_MIN = 0.3217        # 必须 > 它 ⇒ 才能挡住全部三处高危首现段
BASE_MAX = 0.6           # 必须 ≤ 它 ⇒ 否则该 spk 永远攒不够 2.5 s
CUR = sv.REG_CONF_MIN     # = 0.5


def main():
    if not os.path.isfile(ASR122):
        print('[MISSING] %s' % ASR122)
        return 2
    d = json.load(open(ASR122, encoding='utf-8'))
    rows = d['rows']
    out = {
        'script': os.path.basename(__file__),
        'correction': 'APP-075(c) 第二份材料复验 conf 门槛窗口',
        'input': {
            'path': ASR122,
            'n_rows': len(rows),
            'n_clips': len(d.get('per_clip', [])),
            'summary': d.get('summary', {}),
            'scope': d.get('scope', {}),
        },
        'caveat': ('rows 无 clean_ranges 具体区间 ⇒ 本脚本**只复验 conf 维度**；'
                   '「连续≥2.5s」「切换点守卫」**不能**用它复验。'),
        'criteria': {
            'base_window_min_exclusive': BASE_MIN,
            'base_window_max_inclusive': BASE_MAX,
            'current_reg_conf_min': CUR,
        },
    }

    # ── ① 首现段（is_new_spk=True）的 conf ─────────────────────
    firsts = [r for r in rows if r.get('is_new_spk')
              and r.get('spk_conf') is not None]
    first_cf = sorted(round(float(r['spk_conf']), 4) for r in firsts)
    out['first_appear_conf'] = {
        'n': len(first_cf),
        'sorted': first_cf,
        'min': first_cf[0] if first_cf else None,
        'max': first_cf[-1] if first_cf else None,
    }

    # ── ② 「高危首现段」= 换人边界那一段（前一段 spk 不同）──────
    by_clip = {}
    for r in rows:
        by_clip.setdefault(r['clip_id'], []).append(r)
    switch_first = []
    for cid, rs in by_clip.items():
        rs.sort(key=lambda x: x['seg_id'])
        for i in range(1, len(rs)):
            if rs[i].get('spk') != rs[i - 1].get('spk'):
                if rs[i].get('spk_conf') is not None:
                    switch_first.append(dict(
                        clip_id=cid, seg_id=rs[i]['seg_id'],
                        spk=rs[i]['spk'],
                        conf=round(float(rs[i]['spk_conf']), 4),
                        dur_s=rs[i].get('dur_s')))
    sw_cf = sorted(x['conf'] for x in switch_first)
    out['switch_boundary_first_conf'] = {
        'n': len(sw_cf), 'sorted': sw_cf,
        'detail': switch_first,
    }

    # ── ③ 窗口复验 ────────────────────────────────────────────
    #  判据 A（下界）：th > BASE_MIN ⇒ 能挡住**所有**高危首现段？
    #    ⇒ 「高危」= 首现段里 conf 最低的那几处（真人换人点的第一段）
    #  判据 B（上界）：th > BASE_MAX ⇒ 会不会让某个 spk 永远攒不够？
    #    ⇒ 这里用「段时长」近似：`dur_s ≥ REG_MIN_CONT_S` 的段数占比
    #       （真实判据要 clean 区间 ⇒ 本材料给不了 ⇒ 只能给「代理指标」）
    durs = [float(r.get('dur_s') or 0.0) for r in rows]
    n_long = sum(1 for x in durs if x >= sv.REG_MIN_CONT_S)
    out['dur_proxy'] = {
        'n_rows': len(durs),
        'n_dur_ge_reg_min_cont': n_long,
        'ratio': round(n_long / max(1, len(durs)), 4),
        'note': ('代理指标（无 clean_ranges ⇒ 只能用段时长近似）；'
                 '真实判据需 clean 区间 ⇒ 不能在本材料上复验。'),
    }

    # 扫描阈值
    scan = []
    for th in [0.2, 0.3, 0.3217, 0.4, 0.5, 0.6, 0.7, 0.8]:
        n_blocked = sum(1 for c in first_cf if c < th)
        n_pass = sum(1 for c in first_cf if c >= th)
        scan.append(dict(th=th, firsts_blocked=n_blocked,
                         firsts_passed=n_pass))
    out['threshold_scan'] = scan

    # ── ④ 判据 ────────────────────────────────────────────────
    checks = []

    def add(name, verdict, detail):
        checks.append(dict(name=name, verdict=bool(verdict), detail=detail))

    # 判据①：当前阈值 0.5 在第二份材料上**不是恒真**（有段被挡住）
    n_blocked_at_cur = sum(1 for c in first_cf if c < CUR)
    add('当前 REG_CONF_MIN=0.5 在第二份材料上**确实挡住了一些首现段**'
        '（判据非恒真）',
        n_blocked_at_cur > 0,
        {'n_blocked': n_blocked_at_cur, 'n_firsts': len(first_cf),
         'blocked_list': [c for c in first_cf if c < CUR]})

    # 判据②：**换人边界首现段**里，有没有 conf ≥ 0.5 的？
    #   ⇒ 若有 ⇒ 说明 conf 门槛**挡不住**边界段（与第一份材料同结论）
    sw_high = [x for x in switch_first if x['conf'] >= CUR]
    add('第二份材料：换人边界首现段里存在 conf ≥ 0.5 的段 '
        '⇒ **conf 门槛挡不住边界段**（与第一份材料结论一致）',
        len(sw_high) > 0,
        {'n_switch_boundary': len(switch_first),
         'n_conf_ge_current': len(sw_high),
         'examples': sw_high[:8]})

    # 判据③：**下界 0.3217 的普适性** ——
    #   第一份材料的结论是「必须 > 0.3217 才能挡住三处高危首现段」。
    #   在第二份材料里，把 conf < 0.3217 的首现段列出来 ⇒ 看它们是否
    #   **都**落在「换人边界」（即真·高危）上 ⇒ 若有非边界的低 conf 首现段
    #   ⇒ 说明「低 conf = 边界高危」这个**推论**在第二份材料上**不成立**
    #   ⇒ 0.3217 这个下界**只对第一份材料有效**。
    low_first = [r for r in firsts if float(r['spk_conf']) < BASE_MIN]
    sw_keys = {(x['clip_id'], x['seg_id']) for x in switch_first}
    low_is_boundary = [r for r in low_first
                       if (r['clip_id'], r['seg_id']) in sw_keys]
    add('第二份材料：conf < 0.3217 的首现段**是否全**落在换人边界上'
        '（检验「低 conf ⇒ 边界高危」的可外推性）',
        len(low_first) > 0 and len(low_is_boundary) == len(low_first),
        {'n_low_firsts': len(low_first),
         'n_on_boundary': len(low_is_boundary),
         'off_boundary': [{'clip_id': r['clip_id'], 'seg_id': r['seg_id'],
                           'spk': r['spk'],
                           'conf': round(float(r['spk_conf']), 4)}
                          for r in low_first
                          if (r['clip_id'], r['seg_id']) not in sw_keys]})

    out['checks'] = checks
    out['n_pass'] = sum(1 for c in checks if c['verdict'])
    out['n_fail'] = sum(1 for c in checks if not c['verdict'])
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for c in checks:
        print('[%s] %s  %s' % ('PASS' if c['verdict'] else 'FAIL',
                               c['name'],
                               json.dumps(c['detail'], ensure_ascii=False)[:500]))
    print('\n结果：%d PASS / %d FAIL ⇒ %s'
          % (out['n_pass'], out['n_fail'], out['verdict']))
    print('[evidence] %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
