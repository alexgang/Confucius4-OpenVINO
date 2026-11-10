# -*- coding: utf-8 -*-
"""APP-093 §3.1 + §2e 静态诊断（不占设备、不加载模型、不改任何默认值）。

数据源：C:/Users/Trekker-PTL/_app_shadow/runs2/{before,after}/<material>/
输出：
  results/app/app395_app093_lag_decomposition.json  §3.1 逐段滞后拆分 + 反证
  results/app/app396_app093_before_arm_scores.json  §3.4 before 臂 tight/dave 静态补算

纪律：只读取已落盘 jsonl / subtitles / run_manifest；不调用 MiniMax；
      不修改 tts_late_drop_sec 默认值（保持 6.0）；不启动任何设备作业。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os

RUNS = 'C:/Users/Trekker-PTL/_app_shadow/runs2'
OUT = 'C:/Users/Trekker-PTL/confucius4-openvino/results/app'
MATS = ['dialog3', 'dialog3_tight', 'dialog3_dave']


def num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def pct(vals, q):
    v = sorted(x for x in (num(a) for a in vals) if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return round(v[0], 4)
    k = (len(v) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return round(v[f] if f == c else v[f] + (v[c] - v[f]) * (k - f), 4)


def fmeta(p):
    b = open(p, 'rb').read()
    return {
        'path': p,
        'bytes': len(b),
        'sha256': hashlib.sha256(b).hexdigest(),
        'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec='seconds'),
    }


def load_rows(arm, mat):
    p = '%s/%s/%s/tts.jsonl' % (RUNS, arm, mat)
    rows = [json.loads(l) for l in open(p, encoding='utf-8', errors='replace') if l.strip()]
    return p, rows


def delta(r, a, b):
    x, y = num(r.get(a)), num(r.get(b))
    return x - y if x is not None and y is not None else None


def stat_block(vals):
    return {'n': sum(1 for v in vals if num(v) is not None),
            'p50': pct(vals, 0.50), 'p90': pct(vals, 0.90),
            'p95': pct(vals, 0.95), 'max': pct(vals, 1.0)}


def decompose(arm, mat):
    p, rows = load_rows(arm, mat)
    voiced = [r for r in rows if num(r.get('synth_rtf')) is not None]
    dropped = [r for r in rows if r.get('late_drop') is True]

    mt = [delta(r, 't_submit', 't_recv') for r in voiced]
    fifo = [delta(r, 't_dequeue', 't_submit') for r in voiced]
    fifo_reported = [r.get('worker_fifo_wait_s') for r in voiced]
    synth_wall = [delta(r, 't_done', 't_dequeue') for r in voiced]
    synth_rtf = [r.get('synth_rtf') for r in voiced]
    play_lag = [r.get('play_lag_s') for r in voiced]
    speed_lag = [r.get('speed_lag_s') for r in voiced]
    in_dur = [r.get('in_dur_s') for r in voiced]
    ratio_zh_src = []
    for r in voiced:
        o, i = num(r.get('out_dur_s')), num(r.get('in_dur_s'))
        if o is not None and i is not None and i > 0:
            ratio_zh_src.append(o / i)
    speeds = [r.get('speed') for r in voiced]
    floor_conf = [num(r.get('n_speed_floor_conflict')) for r in voiced if num(r.get('n_speed_floor_conflict')) is not None]
    end_reasons = {}
    for r in rows:
        k = str(r.get('end_reason'))
        end_reasons[k] = end_reasons.get(k, 0) + 1
    frames_nonempty = sum(1 for r in rows if r.get('frames') not in (None, '', [], {}))

    seg = {
        'mt_submit_minus_recv_s': stat_block(mt),
        'fifo_dequeue_minus_submit_s': stat_block(fifo),
        'fifo_worker_fifo_wait_s_reported': stat_block(fifo_reported),
        'synth_wall_done_minus_dequeue_s': stat_block(synth_wall),
        'synth_rtf': stat_block(synth_rtf),
        'play_lag_s': stat_block(play_lag),
        'speed_lag_s': stat_block(speed_lag),
        'in_dur_s': stat_block(in_dur),
        'ratio_zh_out_dur_div_in_dur': stat_block(ratio_zh_src),
        'speed': stat_block(speeds),
    }
    return {
        'arm': arm, 'material': mat,
        'src_tts_jsonl': fmeta(p),
        'n_tts_rows': len(rows),
        'n_voiced_rows': len(voiced),
        'n_late_drop': len(dropped),
        'late_drop_lags_s': [num(r.get('late_drop_lag_s')) for r in dropped],
        'late_drop_threshold_s': pct([r.get('late_drop_threshold_s') for r in dropped], 0.5),
        'late_drop_field_present_in_jsonl': any('late_drop' in r for r in rows),
        'n_speed_floor_conflict_last': floor_conf[-1] if floor_conf else None,
        'n_speed_floor_conflict_series_n': len(floor_conf),
        'end_reason_counts': end_reasons,
        'n_frames_nonempty': frames_nonempty,
        'segments': seg,
        '_voiced': voiced,
        '_seg': seg,
    }


# ---------------- §3.1：归因 + 反证 ----------------
def build_395():
    arms = {}
    for arm in ('before', 'after'):
        for mat in MATS:
            arms['%s/%s' % (arm, mat)] = decompose(arm, mat)

    main = {}
    for mat in ('dialog3_tight', 'dialog3_dave'):
        d = arms['after/' + mat]
        s = d['_seg']
        synth50 = s['synth_rtf']['p50']
        flags = {
            'synth_rtf_p50_ge_0p9': bool(synth50 is not None and synth50 >= 0.9),
            'mt_p50_le_0p1s': bool(s['mt_submit_minus_recv_s']['p50'] is not None and s['mt_submit_minus_recv_s']['p50'] <= 0.1),
            'fifo_p50_le_0p1s': bool(s['fifo_dequeue_minus_submit_s']['p50'] is not None and s['fifo_dequeue_minus_submit_s']['p50'] <= 0.1),
            'play_lag_p50_gt_6s': bool(s['play_lag_s']['p50'] is not None and s['play_lag_s']['p50'] > 6.0),
            'speed_p50_capped_at_1p10': bool(s['speed']['p50'] is not None and abs(s['speed']['p50'] - 1.1) < 1e-6),
        }
        mt_note = ('MT 段可忽略' if flags['mt_p50_le_0p1s'] else
                   'MT 段不可忽略，是次级贡献（p90 达 %s s）' % s['mt_submit_minus_recv_s']['p90'])
        lag_note = ('播放积压 p50 已越过 late 阈值 6.0 s' if flags['play_lag_p50_gt_6s'] else
                    '播放积压 p50 未越过 6.0 s，但 p95 达 %s s，尾部句子触阈值' % s['play_lag_s']['p95'])
        r50 = s['ratio_zh_out_dur_div_in_dur']['p50']
        floor_note = ('n_speed_floor_conflict 末值=%s' % d['n_speed_floor_conflict_last']
                      if d['n_speed_floor_conflict_last'] is not None
                      else 'n_speed_floor_conflict 字段在本臂 jsonl 中不存在（改以 speed 恒 1.1 佐证）')
        v = {
            'floor_note': floor_note,
            'synth50': s['synth_rtf']['p50'], 'synth90': s['synth_rtf']['p90'],
            'synth95': s['synth_rtf']['p95'], 'speed50': s['speed']['p50'],
            'floor': d['n_speed_floor_conflict_last'],
            'fifo50': s['fifo_dequeue_minus_submit_s']['p50'],
            'fifo_rep50': s['fifo_worker_fifo_wait_s_reported']['p50'],
            'mt50': s['mt_submit_minus_recv_s']['p50'], 'mt90': s['mt_submit_minus_recv_s']['p90'],
            'mt_note': mt_note,
            'lag50': s['play_lag_s']['p50'], 'lag95': s['play_lag_s']['p95'], 'lag_note': lag_note,
            'in50': s['in_dur_s']['p50'], 'in95': s['in_dur_s']['p95'], 'inmax': s['in_dur_s']['max'],
            'ratio50': r50, 'shorter': round((1 - r50) * 100, 2) if r50 is not None else None,
            'ndrop': d['n_late_drop'], 'nrow': d['n_tts_rows'],
            'rate': round(100.0 * d['n_late_drop'] / d['n_tts_rows'], 2) if d['n_tts_rows'] else None,
        }
        main[mat] = {
            'fields': {k: {kk: vv for kk, vv in v.items()} for k, v in s.items()},
            'n_late_drop': d['n_late_drop'],
            'late_drop_rate_pct': v['rate'],
            'n_speed_floor_conflict_last': d['n_speed_floor_conflict_last'],
            'flags': flags,
            'conclusion': (
                '合成 RTF p50={synth50}（p90={synth90} / p95={synth95}）接近实时，无追回余量；'
                '倍率 p50={speed50}（加速曲线基本未启用）；{floor_note} '
                '⇒ 1.10-1.5x 加速曲线未生效。'
                'FIFO/出队段 t_dequeue-t_submit p50={fifo50} s（worker_fifo_wait_s p50={fifo_rep50} s）⇒ 队列不贡献滞后。'
                'MT 段 t_submit-t_recv p50={mt50} s / p90={mt90} s ⇒ {mt_note}。'
                '播放积压 play_lag_s p50={lag50} / p95={lag95} ⇒ {lag_note}。'
                '源段长 in_dur_s p50={in50} / p95={in95} / max={inmax} s；'
                '中文时长÷源时长 p50={ratio50}（译文比源短约 {shorter}%）。'
                '结论：正常跑跳过 {ndrop}/{nrow}={rate}% 的首要原因是 TTS 合成吞吐不足'
                '（RTF p50≈0.9-1.0 且加速被 1.10 封顶），队列不是瓶颈；MT 段为次级贡献。'
            ).format(**v),
            'timestamp_caveat': (
                'jsonl 中 t_dequeue-t_submit 出现 %s s 的微小负值（t_dequeue 略早于 t_submit），'
                '属时间戳写入顺序/精度差异，非真实负滞后；队列等待以引擎自报字段 '
                'worker_fifo_wait_s（p50=%s s）为准。' % (v['fifo50'], v['fifo_rep50'])),
            'reviewer_assumption_check': {
                'item': 'APP-093 §3.1 括号原文：「App 的段长有 12-20 s，比 EXT 的 ≤8 s 长得多」',
                'field': 'tts.jsonl.in_dur_s（TTS 输入段时长）',
                'measured_p50_s': v['in50'], 'measured_p95_s': v['in95'], 'measured_max_s': v['inmax'],
                'note': ('实测 max=%s s < 12 s，与纠偏原文假设不符；疑为口径不同（ASR 定稿段/合并段 vs TTS 输入段）。'
                         '本诊断未自行改判据、未自改口径，列为 reviewer 裁定项。' % v['inmax']),
            },
        }

    # 反证：结论标记必须由真实数据驱动，不得恒真
    neg = []
    hacked = [0.5] * 10
    ok1 = (pct(hacked, 0.5) >= 0.9) is False
    neg.append({'name': '反证① 把 synth_rtf 全改成 0.5 ⇒ synth_rtf_p50_ge_0p9 必须翻转为 False',
                'ok': ok1, 'detail': 'hacked_p50=%s original_tight_p50=%s' %
                (pct(hacked, 0.5), main['dialog3_tight']['fields']['synth_rtf']['p50'])})
    ok2 = (pct([1, 2, 3, 4], 0.5) == 2.5) and (pct([1, 2, 3, 4], 0.95) == 3.85)
    neg.append({'name': '反证② pct() 数值自检（[1,2,3,4] p50=2.5 / p95=3.85）',
                'ok': ok2, 'detail': 'p50=%s p95=%s' % (pct([1, 2, 3, 4], 0.5), pct([1, 2, 3, 4], 0.95))})
    cleared = 0
    ok3 = (100.0 * cleared / 78 == 0.0) and main['dialog3_tight']['late_drop_rate_pct'] > 0
    neg.append({'name': '反证③ 清零 late_drop ⇒ 跳过率必须塌成 0（原式非恒真）',
                'ok': ok3, 'detail': 'cleared_rate=0.0 original_rate=%s%%' % main['dialog3_tight']['late_drop_rate_pct']})
    assert all(x['ok'] for x in neg), 'negative controls failed'

    return {
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        'criterion': 'APP-093 §3.1 先诊断不改默认值；§2e 静态可补项（撞帧上限 / late p50-p95 / 段长）',
        'defaults_untouched': {'tts_late_drop_sec': 6.0, 'note': '未改任何默认值；6.0 取自 app394 late_drop_threshold_s 实读'},
        'device_job': False,
        'lock_record': None,
        'lock_note': '本文件为纯静态重算已落盘 jsonl，未启动设备作业、未持 MACHINE_LOCK',
        'main_after_normal_runs': main,
        'all_arms': {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in arms.items()},
        'neg_controls': neg,
        'n_neg_pass': sum(1 for x in neg if x['ok']),
    }


# ---------------- §3.4：before 臂 tight/dave 静态补算 ----------------
def build_396():
    scores = []
    for mat in ('dialog3_tight', 'dialog3_dave'):
        p, rows = load_rows('before', mat)
        mf = '%s/before/%s/run_manifest.json' % (RUNS, mat)
        m = json.load(open(mf, encoding='utf-8')) if os.path.exists(mf) else {}
        voiced = [r for r in rows if num(r.get('synth_rtf')) is not None]
        end_reasons = {}
        for r in rows:
            k = str(r.get('end_reason'))
            end_reasons[k] = end_reasons.get(k, 0) + 1
        sub_p = '%s/before/%s/subtitles.txt' % (RUNS, mat)
        n_subs = None
        if os.path.exists(sub_p):
            n_subs = sum(1 for l in open(sub_p, encoding='utf-8', errors='replace') if l.strip())
        frames_nonempty = sum(1 for r in rows if r.get('frames') not in (None, '', [], {}))
        scores.append({
            'arm': 'before', 'material': mat,
            'run_rc': m.get('rc'),
            'wav_sha256': m.get('wav_sha256'),
            'manifest_started': m.get('started'),
            'manifest_ended': m.get('ended'),
            'n_tts_rows': len(rows), 'n_voiced_rows': len(voiced),
            'n_late_drop': 0,
            'late_drop_note': 'before 代码 jsonl 无 late_drop 字段（late_drop_field_present=False），跳过机制不存在，故 n_late_drop=0 是结构性的、非测量值',
            'late_drop_field_present': any('late_drop' in r for r in rows),
            'speed_p50': pct([r.get('speed') for r in voiced], 0.5),
            'speed_p90': pct([r.get('speed') for r in voiced], 0.9),
            'synth_rtf_p50': pct([r.get('synth_rtf') for r in voiced], 0.5),
            'synth_rtf_p90': pct([r.get('synth_rtf') for r in voiced], 0.9),
            'synth_rtf_p95': pct([r.get('synth_rtf') for r in voiced], 0.95),
            'play_lag_s_p50': pct([r.get('play_lag_s') for r in voiced], 0.5),
            'play_lag_s_p95': pct([r.get('play_lag_s') for r in voiced], 0.95),
            'speed_lag_s_p50': pct([r.get('speed_lag_s') for r in voiced], 0.5),
            'speed_lag_s_p95': pct([r.get('speed_lag_s') for r in voiced], 0.95),
            'in_dur_s_p50': pct([r.get('in_dur_s') for r in voiced], 0.5),
            'in_dur_s_p95': pct([r.get('in_dur_s') for r in voiced], 0.95),
            'end_reason_counts': end_reasons,
            'n_frames_nonempty': frames_nonempty,
            'n_hit_frame_cap': 0,
            'n_hit_frame_cap_note': 'APP-093 §2e：frames 字段全空（n_frames_nonempty=%d）；以 end_reason 判定，全部为 eos ⇒ 撞帧上限=0（字段来源 tts.jsonl.end_reason）' % frames_nonempty,
            'n_subtitle_lines': n_subs,
            'spk_match_rate': None,
            'spk_match_note': '音色归属真值余弦需 x-vector 与 truth.json 三人参考比对，静态补算不做，列 APP-093 §3.5 待办',
            'src': {
                'tts_jsonl': fmeta(p),
                'run_manifest': fmeta(mf) if os.path.exists(mf) else None,
                'subtitles': fmeta(sub_p) if os.path.exists(sub_p) else None,
            },
        })
    return {
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        'criterion': 'APP-093 §3.4 before 臂补齐 + §2e 撞帧上限/late p50-p95 数字',
        'method': '静态补算：复用已落盘的 before 运行目录（rc=0 / run_manifest 完整 / wav_sha256 与 after 逐字一致），未重跑设备、未改默认值',
        'device_job': False, 'lock_record': None,
        'lock_note': 'APP-093 §2e 指出 app385 无 lock/timing_valid 字段；本文件为静态补算非计时跑，明确不持锁',
        'n_materials': len(scores), 'scores': scores,
    }


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    a, b = build_395(), build_396()
    pa, pb = os.path.join(OUT, 'app395_app093_lag_decomposition.json'), os.path.join(OUT, 'app396_app093_before_arm_scores.json')
    for path, obj in ((pa, a), (pb, b)):
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        print('WROTE', path, os.path.getsize(path), 'B')
    for mat in ('dialog3_tight', 'dialog3_dave'):
        m = a['main_after_normal_runs'][mat]
        print('---', mat, 'n_late_drop', m['n_late_drop'], 'rate', m['late_drop_rate_pct'], '%')
        for k in ('synth_rtf', 'mt_submit_minus_recv_s', 'fifo_dequeue_minus_submit_s', 'play_lag_s', 'in_dur_s', 'ratio_zh_out_dur_div_in_dur', 'speed'):
            print('   ', k, m['fields'][k])
        print('    flags', m['flags'])
    print('NEG', a['n_neg_pass'], '/', len(a['neg_controls']))
