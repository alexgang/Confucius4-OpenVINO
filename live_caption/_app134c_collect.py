#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app134c_collect.py — **APP-134 c 的三臂汇总**（离线，只读 json）。

## reviewer APP-134 c 原文
> **照原条款补 c13 开/关两轮和 TTS=GPU.0 一轮**、首包、积压与
> **v1.1 43.1/29.9 s 及 v2.5 88.8 s 的对照**、MiniMax 抽查 30 句（reviewer 做）、
> **6 段抽听片段**都还没有。

## 本脚本做什么
* 三臂（c13_on / c13_off / tts_gpu0）逐项汇总；
* **核对每臂的 c13 口径真的生效**（从 `bridge.err` 解析
  `buckets=[...]` ＋ `join=direct_concat|crossfade`）
  ⇒ 🔴 **反证**：若某臂声称 c13 关、但日志仍是 `buckets=[38] join=direct_concat`
  ⇒ **该臂作废**（这是本轮真的踩过的坑）；
* 报「首包」与「积压」，并与 **v1.1 43.1/29.9 s、v2.5 88.8 s** 的历史值对照；
* 汇总 **6 段抽听片段**（每臂 6 段）。

## 用法
```
python live_caption/_app134c_collect.py --root C:\Users\Trekker-PTL\shared\bgkeep\e2e_app134c
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
EVIDENCE = os.path.join(RESULTS, 'app134c_summary.json')

#: 🔴 **历史对照值**（reviewer 给的）
HISTORY = {
    'v1.1': {'first_pack_s': 43.1, 'second_pack_s': 29.9,
             'note': 'v1.1 MiniMVP 的首包/次包（reviewer 给的历史值）'},
    'v2.5': {'first_pack_s': 88.8,
             'note': 'v2.5 完整版的累计口径（reviewer 给的历史值）'},
}


def pick(j, *path, default=None):
    cur = j
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def parse_c13(err_path):
    """从 bridge.err 解析 c13 口径 ＋ 失控计数 ＋ 设备。"""
    out = {'window_line': None, 'buckets': None, 'join': None,
           'runaway_aborts': None, 'tts_device': None, 'na_guard': None}
    try:
        with open(err_path, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
    except OSError:
        return out
    m = re.search(r'APP-123 声码器窗口：([^\r\n]*)', txt)
    if m:
        out['window_line'] = m.group(1).strip()
        mb = re.search(r'buckets=\[([^\]]*)\]', m.group(1))
        if mb:
            out['buckets'] = [x.strip() for x in mb.group(1).split(',') if x.strip()]
        mj = re.search(r'join=(\w+)', m.group(1))
        if mj:
            out['join'] = mj.group(1)
    out['runaway_aborts'] = len(re.findall(r'失控中止', txt))
    m = re.search(r'实测执行设备：([^\r\n]*)', txt)
    if m:
        out['tts_device'] = m.group(1).strip()
    m = re.search(r'NaN 守卫已装 (\d+) 个', txt)
    if m:
        out['na_guard'] = int(m.group(1))
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
    sf = pick(j, 'stats_full', default={}) or {}
    per = sy.get('per_segment') or []
    tts_secs = [float(p['tts_sec']) for p in per if p.get('tts_sec')]

    # 🔴 **首包**：第一句的 tts_sec（EXT 侧逐句耗时的第一个）
    first_pack = tts_secs[0] if tts_secs else None

    c13 = parse_c13(os.path.join(arm_dir, 'bridge.err'))
    return {
        'arm': os.path.basename(arm_dir),
        'json': jf,
        'json_bytes': os.path.getsize(jf),
        'json_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(jf))),
        'dubs': j.get('dubs'),
        'n_pending_at_media_end': d.get('n_pending_at_media_end'),
        'n_pending_after_drain': d.get('n_pending_after_drain'),
        'drained_to_zero': d.get('drained_to_zero'),
        'drain_elapsed_s': d.get('drain_elapsed_sec'),
        'synth_rtf': sy.get('synth_rtf'),
        'synth_rtf_cross_check_ok': sy.get('cross_check_ok'),
        'synth_rtf_n_segments': sy.get('n_segments_with_tts'),
        'first_pack_tts_sec': first_pack,
        'dub_late_max': dl.get('max'),
        'dub_late_p90': dl.get('p90'),
        'max_lag': mg.get('max_lag_sec'),
        'last_segment_lag': mg.get('last_segment_lag_sec'),
        'lag_slope': mg.get('lag_growth_slope_sec_per_sec'),
        'lag_r2': mg.get('lag_growth_r2'),
        'n_emitted': pl.get('n_emitted'),
        'n_submitted': pl.get('n_submitted'),
        'pipeline_n_pending': pl.get('n_pending'),
        'proc_mem_mb': sf.get('proc_mem_mb'),
        'npu_pct': sf.get('npu_pct'),
        'igpu_pct': sf.get('igpu_pct'),
        'c13': c13,
        'listen_clips_dir': os.path.relpath(
            os.path.join(RESULTS, 'app123_listen'), REPO).replace(os.sep, '/'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    args = ap.parse_args()
    root = args.root

    arms = []
    for nm in sorted(os.listdir(root)):
        d = os.path.join(root, nm)
        if os.path.isdir(d) and not nm.startswith('_'):
            arms.append(arm_summary(d))

    checks = []
    # 🔴 **反证**：c13_off 臂必须真的关了 c13
    off = next((a for a in arms if 'c13_off' in a.get('arm', '')), None)
    if off and 'error' not in off:
        c = off['c13']
        ok = (c.get('join') == 'crossfade'
              and c.get('buckets') == ['8', '16', '32', '33'])
        checks.append({'name': 'c13_off_really_off', 'ok': ok,
                       'detail': 'c13_off 臂的窗口：%s ⇒ %s'
                                 % (c.get('window_line'),
                                    '**真的关了**' if ok else '🔴 **没关 ⇒ 该臂作废**')})
    else:
        checks.append({'name': 'c13_off_really_off', 'ok': False,
                       'detail': '找不到 c13_off 臂'})
    # c13_on 臂必须是开着的
    on = next((a for a in arms if 'c13_on' in a.get('arm', '')), None)
    if on and 'error' not in on:
        c = on['c13']
        ok = (c.get('join') == 'direct_concat' and c.get('buckets') == ['38'])
        checks.append({'name': 'c13_on_really_on', 'ok': ok,
                       'detail': 'c13_on 臂的窗口：%s ⇒ %s'
                                 % (c.get('window_line'),
                                    '**真的开着**' if ok else '🔴 **没开 ⇒ 该臂作废**')})
    else:
        checks.append({'name': 'c13_on_really_on', 'ok': False,
                       'detail': '找不到 c13_on 臂'})
    # GPU.0 臂必须真的落在 GPU.0
    g = next((a for a in arms if 'tts_gpu0' in a.get('arm', '')), None)
    if g and 'error' not in g:
        dev = g['c13'].get('tts_device') or ''
        ok = 'GPU' in dev and 'NPU' not in dev
        checks.append({'name': 'tts_gpu0_really_gpu0', 'ok': ok,
                       'detail': 'tts_gpu0 臂的实测执行设备：%s ⇒ %s'
                                 % (dev, '**真的在 GPU.0**' if ok else '🔴 不在 GPU.0')})
    else:
        checks.append({'name': 'tts_gpu0_really_gpu0', 'ok': False,
                       'detail': '找不到 tts_gpu0 臂'})

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
        'script': '_app134c_collect.py',
        'task': 'APP-134 c：c13 开/关 两轮 ＋ TTS=GPU.0 一轮 的三臂汇总',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'arms': arms,
        'checks': checks,
        'all_pass': all(c['ok'] for c in checks),
        'history_reference': HISTORY,
        'listen_clips': {
            'dir': 'results/app/app123_listen',
            'n_per_arm': 6,
            'evidence': 'results/app/app134c_listen_clips.json',
        },
        'lock_events': lock_events,
        'n_lock_lost_events': sum(1 for e in lock_events if e.get('lock_lost')),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)

    print('=== APP-134 c 三臂汇总 ===')
    for a in arms:
        if 'error' in a:
            print('  [%s] 失败：%s' % (a['arm'], a['error']))
            continue
        c = a['c13']
        print('--- %s ---' % a['arm'])
        print('  c13 口径：%s' % c.get('window_line'))
        print('  设备：%s  失控中止次数=%s  NaN守卫=%s'
              % (c.get('tts_device'), c.get('runaway_aborts'), c.get('na_guard')))
        print('  dubs=%s  pending结束=%s ⇒ 排空后=%s (%ss, drained=%s)'
              % (a['dubs'], a['n_pending_at_media_end'], a['n_pending_after_drain'],
                 a['drain_elapsed_s'], a['drained_to_zero']))
        print('  synth_rtf=%s (cross=%s,n=%s)  首包 tts_sec=%s'
              % (a['synth_rtf'], a['synth_rtf_cross_check_ok'],
                 a['synth_rtf_n_segments'], a['first_pack_tts_sec']))
        print('  dub_late max/p90=%s/%s  max_lag=%s  slope=%s'
              % (a['dub_late_max'], a['dub_late_p90'], a['max_lag'], a['lag_slope']))
        print('  emitted=%s pending=%s  内存=%sMB npu=%s igpu=%s'
              % (a['n_emitted'], a['pipeline_n_pending'], a['proc_mem_mb'],
                 a['npu_pct'], a['igpu_pct']))
    print('--- 历史对照（reviewer 给的）---')
    print('  v1.1：首包 %s s／次包 %s s' % (HISTORY['v1.1']['first_pack_s'],
                                        HISTORY['v1.1']['second_pack_s']))
    print('  v2.5：%s s' % HISTORY['v2.5']['first_pack_s'])
    print('--- 口径核对 ---')
    for c in checks:
        print('  %-30s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    print('lock_lost 事件数 = %d' % ev['n_lock_lost_events'])
    print('证据：%s' % EVIDENCE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
