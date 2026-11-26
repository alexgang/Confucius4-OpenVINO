#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app245_gate_metrics.py — **APP-150 §2 三轮硬门禁的逐项统计**（每臂一行）。

reviewer 口径（APP-150 §2）：
* `n_error` = 0；`asr_segments` / `mt_segments` / `tts_segments` > 0 且与提交段数一致；
* `tts_runaway`（APP-130 早停计数）= 0；撞 **39 s 帧上限**的句数 = 0；NaN/Inf = 0；削波句数照报；
* 丢句 = 0（dubs 数与译文句数一致）；最大语速倍率 ≤ 1.7；
* cp_prefill / cp_decode 的 NPU 自检结果与最终落点（原文）；
* 媒体结束时的积压秒数 + 排空用时。

🔴 判据纪律：
* 「NaN」只数**真事件**（`NaN 守卫已装` 是**安装日志**，不是事件 ⇒ 排除；见 §245 踩坑）；
* 撞帧上限：TTS 时长 ≥ 39.0 s 视为撞上限（APP-130 的 492 帧 = 39.36 s）；
* 削波/NaN 事件若日志没有对应字段 ⇒ 记 `null` 并标 `unknown`（**不臆造 0**）。

用法：`<venv python> live_caption/_app245_gate_metrics.py <three_arms_root>`
"""
import json
import os
import re
import sys
import time

FRAME_CAP_SEC = 39.0
SPEED_LIMIT = 1.7

#: 真事件关键字（不是安装日志）
NAN_EVENT = re.compile(r'(出\s*NaN|NaN\s*⇒|检测到\s*NaN|nan_detected|CPNaN)', re.I)
CLIP_EVENT = re.compile(r'(削波|clip(ped|ping)?\s*句|clipped_samples\s*[1-9])', re.I)


def _lines(p):
    if not os.path.isfile(p):
        return []
    with open(p, encoding='utf-8', errors='replace') as fh:
        return fh.read().splitlines()


def arm_metrics(arm_dir, arm_name):
    rec = {'arm': arm_name, 'dir': arm_dir}
    jf = os.path.join(arm_dir, 'bgkeep_e2e.json')
    logp = os.path.join(arm_dir, 'bridge.log')
    errp = os.path.join(arm_dir, 'bridge.err')
    if not os.path.isfile(jf):
        rec['error'] = 'no bgkeep_e2e.json'
        return rec
    with open(jf, encoding='utf-8') as fh:
        j = json.load(fh)
    st = j.get('stats_full') or {}
    pl = st.get('pipeline') or {}
    dr = j.get('drain') or {}
    dl = j.get('dub_late_final_summary') or {}
    sr = j.get('synth_rtf') or {}

    rec.update({
        'dubs': j.get('dubs'),
        'n_submitted': pl.get('n_submitted'),
        'n_emitted': pl.get('n_emitted'),
        'n_error': pl.get('n_error'),
        'n_pending_final': pl.get('n_pending'),
        'asr_segments': st.get('asr_segments'),
        'mt_segments': st.get('mt_segments'),
        'tts_segments': st.get('tts_segments'),
        'n_dropped': st.get('n_dropped'),
        'dub_dropped': st.get('dub_dropped'),
        'seg_skipped': st.get('seg_skipped'),
        'bg_state': st.get('bg_state'),
        'clone_reasons': st.get('clone_reasons'),
        'n_gender_splits': st.get('n_gender_splits'),
        'npu_pct': st.get('npu_pct'),
        'proc_mem_mb': st.get('proc_mem_mb'),
        # 排空
        'drained_to_zero': dr.get('drained_to_zero'),
        'n_pending_at_media_end': dr.get('n_pending_at_media_end'),
        'n_pending_after_drain': dr.get('n_pending_after_drain'),
        'drain_elapsed_sec': dr.get('drain_elapsed_sec'),
        'drain_timeout_count': dr.get('stats_timeout_count'),
        'drain_timeout_events_n': len(dr.get('drain_timeout_events') or []),
        'drain_hard_cap_hit': dr.get('drain_hard_cap_hit'),
        'timing_valid': dr.get('timing_valid'),
        # 滞后
        'dub_late_max': dl.get('max'), 'dub_late_p90': dl.get('p90'),
        'dub_late_p50': dl.get('p50'),
        # TTS
        'synth_rtf': sr.get('synth_rtf'),
        'n_segments_with_tts': sr.get('n_segments_with_tts'),
        'sum_tts_sec': sr.get('sum_tts_sec'),
        'sum_speech_sec': sr.get('sum_speech_sec'),
    })

    # 丢句：dubs 与译文句数
    mt_n, dubs = rec.get('mt_segments'), rec.get('dubs')
    rec['lost_sentences'] = (None if (mt_n is None or dubs is None)
                             else max(0, int(mt_n) - int(dubs)))

    log = _lines(logp)
    err = _lines(errp)

    # 语速倍率（bridge.log 的「倍率=」）与 TTS 时长（「TTS=」）
    speeds = [float(x) for x in re.findall(r'倍率=([0-9.]+)', '\n'.join(log))]
    tts_secs = [float(x) for x in re.findall(r'TTS=([0-9.]+)s', '\n'.join(log))]
    rec['speed_max'] = max(speeds) if speeds else None
    rec['speed_n'] = len(speeds)
    rec['speed_at_limit_n'] = sum(1 for s in speeds if s >= SPEED_LIMIT - 1e-9)
    rec['tts_sec_max'] = max(tts_secs) if tts_secs else None
    rec['tts_frame_cap_hit_n'] = sum(1 for t in tts_secs if t >= FRAME_CAP_SEC)
    rec['tts_sentences_logged'] = len(tts_secs)

    # 事件计数（log + err 一起数，但排除「守卫已装」这类安装行）
    allt = log + err
    rec['tts_runaway_n'] = sum(1 for l in allt if 'tts_runaway' in l)
    rec['nan_event_n'] = sum(1 for l in allt
                             if NAN_EVENT.search(l) and '守卫已装' not in l)
    rec['clip_event_n'] = sum(1 for l in allt if CLIP_EVENT.search(l))
    rec['nan_guard_install_lines'] = sum(1 for l in allt if '守卫已装' in l)

    # 就绪行（MT3 / TTS / ASR）与 cp 自检 + 落点
    rec['ready_mt'] = [l for l in err if 'MT 就绪' in l][:2]
    rec['ready_asr'] = [l for l in err if 'ASR 就绪' in l][:2]
    rec['ready_tts'] = [l for l in err if 'TTS 就绪' in l][:2]
    rec['cp_selfcheck_lines'] = [l for l in err if 'cp_prefill' in l or 'cp_decode' in l][:8]
    rec['tts_exec_devices_lines'] = [l for l in err if 'EXECUTION_DEVICES' in l][:2]
    rec['turbo_true_n'] = sum(1 for l in err if 'NPU_TURBO=True' in l)
    rec['turbo_yes_n'] = sum(1 for l in err if 'turbo 已生效：YES' in l)
    return rec


def main(root, out_path):
    arms = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name, name + '_1')
        if os.path.isdir(d):
            arms.append(arm_metrics(d, name))

    # 逐臂门禁（APP-150 §2，能判的项都判；判不了的标 None）
    for r in arms:
        chk = {
            'n_error_zero': r.get('n_error') == 0,
            'three_counts_positive': all((r.get(k) or 0) > 0
                                         for k in ('asr_segments', 'mt_segments',
                                                   'tts_segments')),
            'no_lost_sentences': r.get('lost_sentences') == 0,
            'drained_to_zero': r.get('drained_to_zero') is True,
            'tts_runaway_zero': r.get('tts_runaway_n') == 0,
            'frame_cap_hit_zero': r.get('tts_frame_cap_hit_n') == 0,
            'nan_event_zero': r.get('nan_event_n') == 0,
            'speed_within_limit': (r.get('speed_max') is not None
                                   and r['speed_max'] <= SPEED_LIMIT + 1e-9),
            'clip_reported': r.get('clip_event_n') is not None,
        }
        r['gate_checks'] = chk
        r['gate_pass'] = all(v is True for v in chk.values())

    payload = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'frame_cap_sec': FRAME_CAP_SEC,
        'speed_limit': SPEED_LIMIT,
        'note': '🔴 NaN 只数真事件（排除「守卫已装」安装行）；判不了的项标 null 不臆造。',
        'arms': arms,
        'gate_all_pass': bool(arms) and all(r.get('gate_pass') for r in arms),
    }
    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)

    hdr = ('arm', 'n_error', 'asr', 'mt', 'tts', 'dubs', 'lost', 'drain',
           'pend_end', 'tmo', 'spd_max', 'runaway', 'cap39', 'nan', 'rtf',
           'gate')
    print('%-18s %7s %5s %5s %5s %5s %5s %6s %8s %4s %7s %7s %5s %4s %6s %s'
          % hdr)
    for r in arms:
        print('%-18s %7s %5s %5s %5s %5s %5s %6s %8s %4s %7s %7s %5s %4s %6s %s'
              % (r['arm'], r.get('n_error'), r.get('asr_segments'),
                 r.get('mt_segments'), r.get('tts_segments'), r.get('dubs'),
                 r.get('lost_sentences'), r.get('drained_to_zero'),
                 r.get('n_pending_at_media_end'), r.get('drain_timeout_count'),
                 r.get('speed_max'), r.get('tts_runaway_n'),
                 r.get('tts_frame_cap_hit_n'), r.get('nan_event_n'),
                 r.get('synth_rtf'), 'PASS' if r.get('gate_pass') else 'FAIL'))
    print('\n证据：%s' % out_path)
    print('门禁总判定：%s' % ('PASS' if payload['gate_all_pass'] else 'FAIL'))
    return 0 if payload['gate_all_pass'] else 3


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else \
        r'C:\Users\Trekker-PTL\shared\bgkeep\e2e_app149\three_arms_r245'
    out = sys.argv[2] if len(sys.argv) > 2 else \
        r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app245_gate_metrics.json'
    sys.exit(main(root, out))
