#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app134b_collect.py — **APP-134 b 的对照**（离线，只读 json）。

## reviewer APP-134 b 原文
> APP-130 不变差：同一个 10 分钟片段、TTS=NPU、bgkeep 关，
> **自检加 NaN 守卫打开 vs 关闭**（用环境开关，或者**临时换回 21f7c39 之前的
> tts_engine 跑一轮**），各跑一轮，比较 **synth_rtf 中位/P90 和 max_lag**
> （**差值 ≤5% 就算不变差**）。把 bridge.err 里的自检数字补进 §229 §3。

## 本脚本做什么
* 取两臂的 `synth_rtf`（EXT `RTF_out`）**中位 / P90** 与 `max_lag`；
* 算**相对差值** ⇒ 判「≤5% ⇒ 不变差」；
* 把 `bridge.err` 里的**自检数字**抽出来（cp_decode / cp_prefill 的耗时与余弦）、
  以及 **NaN 守卫装了几个**（`guard_off` 臂应当 **0 个**）⇒ 反证「两臂真的不同」。

## 🔴 反证（**判据承重**）
`guard_off` 臂若 `bridge.err` 里仍出现「NaN 守卫已装 N 个」⇒ 说明**影子包没换成功**
⇒ 本脚本报 **FAIL**（因为那样两臂就不是「开 vs 关」）。

## 用法
```
python live_caption/_app134b_collect.py --root C:\Users\Trekker-PTL\shared\bgkeep\e2e_app134b
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app134b_summary.json')

#: reviewer 判据：**差值 ≤5% 就算不变差**
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


def parse_selfcheck(err_path):
    """抽 `bridge.err` 里的自检数字（reviewer 要求「补进 §229 §3」）。"""
    out = {'na_guard_installed': None, 'cp_decode_selfcheck': None,
           'cp_prefill_selfcheck': None, 'cp_decode_cos': None,
           'cp_prefill_cos': None}
    try:
        with open(err_path, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
    except OSError:
        return out
    m = re.search(r'NaN 守卫已装 (\d+) 个', txt)
    if m:
        out['na_guard_installed'] = int(m.group(1))
    m = re.search(r'cp_decode: NPU 自检通过（耗时 ([^，)]*)[，]?(?:用例 )?(\[[^\]]*\])?', txt)
    if m:
        out['cp_decode_selfcheck'] = m.group(1).strip()
        if m.group(2):
            out['cp_decode_cos'] = m.group(2).strip()
    m = re.search(r'cp_prefill: NPU 自检通过（耗时 ([^，)]*)[，]?(?:用例 )?(\[[^\]]*\])?', txt)
    if m:
        out['cp_prefill_selfcheck'] = m.group(1).strip()
        if m.group(2):
            out['cp_prefill_cos'] = m.group(2).strip()
    return out


def arm_summary(arm_dir):
    jf = os.path.join(arm_dir, 'bgkeep_e2e.json')
    if not os.path.isfile(jf):
        return {'arm': os.path.basename(arm_dir), 'error': 'no bgkeep_e2e.json'}
    with open(jf, encoding='utf-8') as fh:
        j = json.load(fh)
    d = j.get('drain') or {}
    dl = j.get('dub_late_final_summary') or {}
    sy = j.get('synth_rtf') or {}
    mg = pick(j, 'stats_full', 'margin', default={}) or {}
    pl = pick(j, 'stats_full', 'pipeline', default={}) or {}
    per = sy.get('per_segment') or []
    rtfs = sorted(float(p['rtf']) for p in per if p.get('rtf') is not None)
    n = len(rtfs)
    p50 = (rtfs[n // 2] if n % 2 else (rtfs[n // 2 - 1] + rtfs[n // 2]) / 2.0) if n else None
    p90 = None
    if n:
        # 与 numpy.percentile 的线性插值口径一致
        idx = 0.9 * (n - 1)
        lo = int(idx)
        frac = idx - lo
        p90 = rtfs[lo] + (rtfs[lo + 1] - rtfs[lo]) * frac if lo + 1 < n else rtfs[lo]
    return {
        'arm': os.path.basename(arm_dir),
        'json': jf,
        'json_bytes': os.path.getsize(jf),
        'json_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(jf))),
        'pkg': pick(j, 'stats_full', 'client_source', default=None),
        'dubs': j.get('dubs'),
        'n_pending_at_media_end': d.get('n_pending_at_media_end'),
        'n_pending_after_drain': d.get('n_pending_after_drain'),
        'drained_to_zero': d.get('drained_to_zero'),
        'drain_elapsed_s': d.get('drain_elapsed_sec'),
        # ── reviewer 要比的两个量 ──────────────────────────────
        'synth_rtf_ext': sy.get('synth_rtf'),
        'synth_rtf_p50_median': p50,
        'synth_rtf_p90': p90,
        'synth_rtf_n_segments': sy.get('n_segments_with_tts'),
        'synth_rtf_cross_check_ok': sy.get('cross_check_ok'),
        'max_lag': mg.get('max_lag_sec'),
        'last_segment_lag': mg.get('last_segment_lag_sec'),
        'lag_slope': mg.get('lag_growth_slope_sec_per_sec'),
        'lag_r2': mg.get('lag_growth_r2'),
        'dub_late_max': dl.get('max'),
        'dub_late_p90': dl.get('p90'),
        'bg_late_blocks': j.get('bg_late_blocks'),
        'proc_mem_mb': pick(j, 'stats_full', 'proc_mem_mb'),
        'selfcheck': parse_selfcheck(os.path.join(arm_dir, 'bridge.err')),
        'devices': {
            'asr': None, 'mt': None, 'tts': None,
        },
    }


def parse_devices(err_path):
    try:
        with open(err_path, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
    except OSError:
        return {}
    out = {}
    for key, pat in [('asr', r'ASR 就绪（([^）]*)）'),
                     ('mt', r'MT 就绪（([^）]*)）'),
                     ('tts', r'TTS 就绪（([^）]*)）')]:
        m = re.search(pat, txt)
        if m:
            out[key] = m.group(1).strip()
    return out


def rel_diff(a, b):
    """相对差值 |a-b| / max(|a|,|b|)（**0 都当 0**）。"""
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    m = max(abs(a), abs(b))
    if m == 0:
        return 0.0
    return abs(a - b) / m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    args = ap.parse_args()
    root = args.root

    arms = []
    for nm in sorted(os.listdir(root)):
        d = os.path.join(root, nm)
        if os.path.isdir(d) and not nm.startswith('_'):
            a = arm_summary(d)
            a['devices'] = parse_devices(os.path.join(d, 'bridge.err'))
            arms.append(a)

    # 🔴 **分组用 `arm_config`**（驱动器写入的配置名）⇒ **不靠目录名猜**
    #    （臂目录名已加序号后缀 `_1`/`_2`…）
    def cfg_of(a):
        c = a.get('arm_config')
        if c:
            return c
        return 'guard_on' if 'guard_on' in a.get('arm', '') else 'guard_off'

    on = next((a for a in arms if cfg_of(a) == 'guard_on'), None)
    off = next((a for a in arms if cfg_of(a) == 'guard_off'), None)

    verdict = None
    checks = []
    if on and off and 'error' not in on and 'error' not in off:
        for key, label in [('synth_rtf_p50_median', 'synth_rtf 中位'),
                           ('synth_rtf_p90', 'synth_rtf P90'),
                           ('max_lag', 'max_lag')]:
            rd = rel_diff(on.get(key), off.get(key))
            checks.append({'name': 'rel_diff_%s' % key, 'value': rd,
                           'ok': (rd is not None and rd <= TOLERANCE),
                           'detail': '%s：on=%s off=%s ⇒ 相对差 %.2f%%（判据 ≤5%%）'
                                     % (label, on.get(key), off.get(key),
                                        (rd or 0) * 100)})
        # 🔴 **反证**：guard_off 臂的 NaN 守卫必须是 0 个
        ng_off = (off.get('selfcheck') or {}).get('na_guard_installed')
        ng_on = (on.get('selfcheck') or {}).get('na_guard_installed')
        checks.append({'name': 'guard_off_has_no_nan_guard',
                       'ok': (ng_off in (0, None)) and (ng_on is not None and ng_on > 0),
                       'detail': 'guard_on 装 %s 个 / guard_off 装 %s 个'
                                 '（⇒ 两臂确实「开 vs 关」）' % (ng_on, ng_off)})
        all_ok = all(c['ok'] for c in checks)
        verdict = 'NOT_WORSE（不变差，差值 ≤5%）' if all_ok else 'DIFFERENT（超出 5% 或两臂不可比）'
    else:
        checks.append({'name': 'both_arms_present', 'ok': False,
                       'detail': '两臂不齐：%s' % [a.get('arm') for a in arms]})

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
        'script': '_app134b_collect.py',
        'task': 'APP-134 b：自检+NaN 守卫「开 vs 关」的对照（synth_rtf 中位/P90 与 max_lag）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'tolerance': TOLERANCE,
        'arms': arms,
        'checks': checks,
        'verdict': verdict,
        'lock_events': lock_events,
        'n_lock_lost_events': sum(1 for e in lock_events if e.get('lock_lost')),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)

    print('=== APP-134 b 对照（判据：差值 ≤5%%）===')
    for a in arms:
        if 'error' in a:
            print('  [%s] 失败：%s' % (a['arm'], a['error']))
            continue
        print('--- %s ---' % a['arm'])
        print('  pkg=%s' % a.get('pkg'))
        print('  synth_rtf: ext=%s  中位=%s  P90=%s  (n=%s, cross_check=%s)'
              % (a['synth_rtf_ext'], a['synth_rtf_p50_median'], a['synth_rtf_p90'],
                 a['synth_rtf_n_segments'], a['synth_rtf_cross_check_ok']))
        print('  max_lag=%s  last_lag=%s  slope=%s (r2=%s)'
              % (a['max_lag'], a['last_segment_lag'], a['lag_slope'], a['lag_r2']))
        print('  排空: pending 结束=%s ⇒ 排空后=%s (%ss, drained=%s)'
              % (a['n_pending_at_media_end'], a['n_pending_after_drain'],
                 a['drain_elapsed_s'], a['drained_to_zero']))
        print('  自检: %s' % json.dumps(a['selfcheck'], ensure_ascii=False))
        print('  设备: %s' % json.dumps(a['devices'], ensure_ascii=False))
    print('--- 对照 ---')
    for c in checks:
        print('  %-34s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c.get('detail', '')))
    print('判定：%s' % verdict)
    print('lock_lost 事件数 = %d' % ev['n_lock_lost_events'])
    print('证据：%s' % EVIDENCE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
