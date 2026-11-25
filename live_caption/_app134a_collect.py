#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app134a_collect.py — **APP-134 a 的两臂结果汇总**（离线，只读 json）。

## reviewer APP-134 a 要求
> 至少重跑 **bgkeep_on（TTS=NPU）** 和 **bgkeep_on（AUTO，即 Start_Bridge 的
> 实际配置）** 两轮。每轮报：
> dubs、n_submitted/n_emitted/n_pending（**媒体结束时和排空后各一次**）、
> dub_late max/p90、last_segment_lag、斜率、synth_rtf、bg_late_blocks、
> **峰值内存**、解析出来的实际设备。

## 本脚本做的事
把两个臂的 `bgkeep_e2e.json` 汇总成**一张对照表** ＋ **口径对照**
（reviewer 指出的「丢句 0／收尾积压 0」在新口径下是多少）。

## 🔴 关键：**不把「排空」说成「零积压」**
排空后 `n_pending=0` 只说明「**最终都配上了音**」，
**不等于**「播放时没滞后」⇒ 报告里**必须同时给**：
* 媒体结束时的 `n_pending`（= 那一刻还没配上的句子数）
* 排空耗时（= 这些句子晚了多久才配上）
* `dub_late` 分布 ＋ 滞后斜率

## 用法
```
python live_caption/_app134a_collect.py --root C:\Users\Trekker-PTL\shared\bgkeep\e2e_app134a
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app134a_summary.json')


def pick(j, *path, default=None):
    cur = j
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def arm_summary(arm_dir: str) -> dict:
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
    out = {
        'arm': os.path.basename(arm_dir),
        'json': jf,
        'json_bytes': os.path.getsize(jf),
        'json_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(jf))),
        'media': j.get('media'),
        'duration_s': j.get('duration_s'),
        # ── reviewer 逐项要的字段 ────────────────────────────────
        'dubs': j.get('dubs'),
        'n_submitted_at_media_end': d.get('n_submitted_at_media_end'),
        'n_emitted_at_media_end': d.get('n_emitted_at_media_end'),
        'n_pending_at_media_end': d.get('n_pending_at_media_end'),
        'n_submitted_after_drain': d.get('n_submitted_after_drain'),
        'n_emitted_after_drain': d.get('n_emitted_after_drain'),
        'n_pending_after_drain': d.get('n_pending_after_drain'),
        'drained_to_zero': d.get('drained_to_zero'),
        'drain_elapsed_s': d.get('drain_elapsed_sec'),
        'drain_disconnected': d.get('disconnected'),
        'dub_late_max': dl.get('max'),
        'dub_late_p90': dl.get('p90'),
        'dub_late_p50': dl.get('p50'),
        'dub_late_n': dl.get('n'),
        'last_segment_lag': mg.get('last_segment_lag_sec'),
        'lag_slope_sec_per_sec': mg.get('lag_growth_slope_sec_per_sec'),
        'lag_r2': mg.get('lag_growth_r2'),
        'synth_rtf': sy.get('synth_rtf'),
        'synth_rtf_cross_check_ok': sy.get('cross_check_ok'),
        'synth_rtf_n_segments': sy.get('n_segments_with_tts'),
        'speech_over_src': sy.get('ext_speech_over_src'),
        'tts_over_src': sy.get('ext_tts_over_src'),
        'bg_late_blocks': j.get('bg_late_blocks'),
        'proc_mem_mb': pick(j, 'stats_full', 'proc_mem_mb'),
        'sep_device': pick(j, 'stats_full', 'sep_device'),
        'npu_pct': pick(j, 'stats_full', 'npu_pct'),
        'igpu_pct': pick(j, 'stats_full', 'igpu_pct'),
        'clone_reasons': pick(j, 'stats_full', 'clone_reasons'),
        'n_gender_splits': pick(j, 'stats_full', 'n_gender_splits'),
        'devices_parsed': parse_devices(os.path.join(arm_dir, 'bridge.err')),
    }
    return out


def parse_devices(err_path):
    """从 bridge.err 解析**实际设备**（reviewer 明确要求这一项）。"""
    import re
    dev = {}
    try:
        with open(err_path, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
    except OSError:
        return dev
    pats = [
        ('asr', r'ASR 就绪（([^）]*)）'),
        ('mt', r'加载翻译模型（([^）]*)）'),
        ('tts_exec_devices', r'实测执行设备：([^\r\n]*)'),
        ('tts_load_device', r'加载模型：device=(\S*)'),
        ('cp_decode_selfcheck', r'cp_decode: NPU 自检通过（耗时 ([^）]*)'),
        ('cp_prefill_selfcheck', r'cp_prefill: NPU 自检通过（耗时 ([^）]*)'),
        ('vocoder_window', r'APP-123 声码器窗口：([^\r\n]*)'),
        ('decoder', r'使用 (MultiDecoderBabelVox[^（]*)'),
        ('na_guard', r'NaN 守卫已装 (\d+) 个'),
    ]
    for key, pat in pats:
        m = re.search(pat, txt)
        if m:
            dev[key] = m.group(1).strip()
    return dev


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

    # ── 锁事件 ────────────────────────────────────────────────────
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
    lock_lost = [e for e in lock_events if e.get('lock_lost')]

    # ── 🔴 口径对照（reviewer 指出的「丢句 0／收尾积压 0」） ────────
    caliber = []
    for a in arms:
        if 'error' in a:
            continue
        npend_me = a.get('n_pending_at_media_end')
        nsub_me = a.get('n_submitted_at_media_end')
        rate = (npend_me / nsub_me * 100.0) if (npend_me is not None and nsub_me) else None
        caliber.append({
            'arm': a['arm'],
            '旧口径「丢句 0／收尾积压 0」': '不成立',
            '媒体结束时未配音句数_n_pending': npend_me,
            '占总句数_pct': round(rate, 1) if rate is not None else None,
            '排空耗时_s': a.get('drain_elapsed_s'),
            '排空后_n_pending': a.get('n_pending_after_drain'),
            '最终是否都配上音': a.get('drained_to_zero'),
            '滞后是否回落（斜率≤0 且 r² 高 ⇒ 不回落）':
                ('否（线性增长）' if (a.get('lag_slope_sec_per_sec') or 0) < 0
                 and (a.get('lag_r2') or 0) > 0.8 else '见斜率'),
            'dub_late_max_s': a.get('dub_late_max'),
        })

    ev = {
        'script': '_app134a_collect.py',
        'task': 'APP-134 a：两臂（bgkeep_on TTS=NPU / bgkeep_on AUTO）结果汇总',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'arms': arms,
        'caliber_correction': caliber,
        'lock_events': lock_events,
        'n_lock_lost_events': len(lock_lost),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)

    print('=== APP-134 a 两臂汇总 ===')
    for a in arms:
        if 'error' in a:
            print('  [%s] 失败：%s' % (a['arm'], a['error']))
            continue
        print('--- %s ---' % a['arm'])
        print('  dubs=%s  媒体结束: sub=%s emit=%s **pending=%s**'
              % (a['dubs'], a['n_submitted_at_media_end'],
                 a['n_emitted_at_media_end'], a['n_pending_at_media_end']))
        print('  排空后: sub=%s emit=%s pending=%s  drained=%s  耗时=%ss'
              % (a['n_submitted_after_drain'], a['n_emitted_after_drain'],
                 a['n_pending_after_drain'], a['drained_to_zero'],
                 a['drain_elapsed_s']))
        print('  dub_late: n=%s max=%s p90=%s p50=%s'
              % (a['dub_late_n'], a['dub_late_max'], a['dub_late_p90'],
                 a['dub_late_p50']))
        print('  滞后: last=%s slope=%s r2=%s'
              % (a['last_segment_lag'], a['lag_slope_sec_per_sec'], a['lag_r2']))
        print('  synth_rtf=%s (cross_check=%s, n=%s)  speech/src=%s tts/src=%s'
              % (a['synth_rtf'], a['synth_rtf_cross_check_ok'],
                 a['synth_rtf_n_segments'], a['speech_over_src'], a['tts_over_src']))
        print('  bg_late_blocks=%s  峰值内存=%sMB' % (a['bg_late_blocks'],
                                                a['proc_mem_mb']))
        print('  实际设备: %s' % json.dumps(a['devices_parsed'], ensure_ascii=False))
    print('--- 口径对照 ---')
    for c in caliber:
        print('  [%s] 媒体结束 pending=%s (%s%%) ⇒ 排空 %ss ⇒ 排空后 %s；'
              '斜率回落=%s'
              % (c['arm'], c['媒体结束时未配音句数_n_pending'],
                 c['占总句数_pct'], c['排空耗时_s'], c['排空后_n_pending'],
                 c['滞后是否回落（斜率≤0 且 r² 高 ⇒ 不回落）']))
    print('lock_lost 事件数 = %d' % len(lock_lost))
    print('证据：%s' % EVIDENCE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
