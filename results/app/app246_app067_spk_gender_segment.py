#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app246 — APP-067 ② 的**前置**：从 SPE 语料里挑一段「至少一男一女」的片段。

## 为什么需要这一步（reviewer 原文，APP-067 ②）
> SPE 前 5 分钟基本只有一个说话人（这次只检测到 S1），不符合"至少一男一女"的要求。
> 请另选一段有男有女的 SPE 片段（**先写明起止时间**），做完第 1 项后再交。

## 口径（**必须写清楚，不能靠猜**）
* 语料里**没有**性别标注 ⇒ 本脚本用**基频 F0**（自相关法）做**客观测量**，
  再按经验阈值给出「低频/高频」两类的**推定**。
* 🔴 **这是推定，不是标注** ⇒ 输出里同时给出每个说话人的 F0 中位数 / IQR /
  帧数，让 reviewer 自己裁定阈值。
* 阈值 `F0_MALE_MAX = 160.0 Hz`（经验中值：男声 85–155 / 女声 165–255）。

## 输出
* `results/app/app246_app067_spk_gender_segment_evidence.json`
* 选中的窗口：`start_s` / `end_s`（**源 wav 的绝对时间轴**）+ 参与者列表。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

SRC_WAV = os.path.join(REPO, 'test_audio', '260902_SPE_audio.wav')
REF_JSON = os.path.join(HOME, 'shared', 'spe_qa_spk.json')
OUT_JSON = os.path.join(HERE, 'app246_app067_spk_gender_segment_evidence.json')

F0_MALE_MAX = 160.0          # Hz；低于此判「低频（男声推定）」
F0_MIN = 60.0                # Hz；低于此不是人声基频
F0_MAX = 400.0               # Hz；高于此不是人声基频
FRAME_MS = 40.0
HOP_MS = 20.0
MIN_VOICE_FRAMES = 8        # 一段至少要有这么多有声帧才采信


def read_wav(path):
    with wave.open(path, 'rb') as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nf = w.getnframes()
        assert sw == 2, '只处理 16-bit PCM（实测 sw=%d）' % sw
        assert nch == 1, '只处理单声道（实测 nch=%d）' % nch
        raw = w.readframes(nf)
    import numpy as np
    a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    return a, sr, nf


def f0_autocorr(frame, sr, fmin=F0_MIN, fmax=F0_MAX):
    """自相关法基频（返回 0.0 = 无有效基频）。

    🔴🔴 **八度误差（octave error）是本方法的头号坑**：自相关在
    `2τ、3τ…` 处也有峰 ⇒ 「取第一个超过阈值的峰」会把 **F0 翻倍**
    （男声 120 Hz 被测成 240 Hz）⇒ 实测第一版在**已知男声**控制组上
    就给出 122–224 Hz 的中位（明显偏高）⇒ 判定不可用。

    ⇒ 修法：**先找全局峰 M，再取「最小的 lag 的局部峰，且 ≥ 0.85·M」**
    ⇒ 优先落在基频而不是它的二倍频。
    """
    import numpy as np
    x = frame - float(frame.mean())
    n = x.size
    if n < 64:
        return 0.0
    w = np.hanning(n).astype(np.float32)
    xw = x * w
    energy = float(np.dot(xw, xw))
    if energy <= 1e-8:
        return 0.0
    # FFT 自相关（O(n log n)）
    m = 1 << int(np.ceil(np.log2(2 * n)))
    f = np.fft.rfft(xw, m)
    ac = np.fft.irfft(f * np.conj(f), m)[:n]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    lag_min = max(2, int(sr / fmax))
    lag_max = min(n - 1, int(sr / fmin))
    if lag_max <= lag_min:
        return 0.0
    seg = ac[lag_min:lag_max + 1]
    # 局部峰
    peaks = []
    for i in range(1, seg.size - 1):
        v = float(seg[i])
        if v >= float(seg[i - 1]) and v > float(seg[i + 1]):
            peaks.append((lag_min + i, v))
    if not peaks:
        return 0.0
    gmax = max(v for _, v in peaks)
    if gmax < 0.25:                 # 自相关峰太弱 ⇒ 不是浊音
        return 0.0
    # 🔴 取**最小 lag** 的、且 ≥ 0.85·全局峰的局部峰 ⇒ 基频优先
    for lag, v in peaks:
        if v >= 0.85 * gmax:
            return sr / float(lag)
    return sr / float(peaks[0][0])


def segment_f0(a, sr, t0, t1):
    import numpy as np
    i0 = max(0, int(t0 * sr))
    i1 = min(a.size, int(t1 * sr))
    if i1 - i0 < int(0.3 * sr):
        return []
    seg = a[i0:i1]
    flen = int(FRAME_MS * sr / 1000.0)
    hop = int(HOP_MS * sr / 1000.0)
    out = []
    for s in range(0, max(0, seg.size - flen), hop):
        fr = seg[s:s + flen]
        if float(np.sqrt(np.mean(fr * fr))) < 0.01:      # 太安静 ⇒ 跳过
            continue
        f0 = f0_autocorr(fr, sr)
        # 🔴 贴住 F0_MAX 上限的帧 = 估计不可信（多半是清音/噪声）⇒ 丢弃
        if f0 > 0 and f0 < 0.97 * F0_MAX:
            out.append(f0)
    return out


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--window-s', type=float, default=300.0,
                    help='候选窗口长度（秒）')
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': 'app246_app067_spk_gender_segment.py',
           'correction': 'APP-067 ②（前置：选一段至少一男一女的 SPE 片段）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args),
           'criterion': {
               'method': 'autocorrelation_f0 (lowest-lag peak >= 0.85*global)',
               'frame_ms': FRAME_MS, 'hop_ms': HOP_MS,
               'f0_range_hz': [F0_MIN, F0_MAX],
               'male_max_hz': F0_MALE_MAX,
               'note': ('语料无性别标注 ⇒ 本文件给的是**基频实测值 + 推定分类**，'
                        '不是人工标注；阈值来源=F0_MALE_MAX，reviewer 可裁定'),
           }}

    # ── 判据自检（**鉴别力**）：控制组 = SPE 前 5 分钟切片 ──────────
    #   历史纠偏原文（APP-0xx V3）：「用 SPE 前 5 分钟切片（**单一男声**）」
    #   ⇒ 控制组的中位 F0 **必须落在男声区间** ⇒ 否则判据本身不可信。
    ctrl_path = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
    ctrl = {'path': ctrl_path, 'expect': 'single male voice (history correction)',
            'male_max_hz': F0_MALE_MAX}
    if os.path.isfile(ctrl_path):
        ca, csr, cnf = read_wav(ctrl_path)
        cframes = []
        for t0 in range(5, 240, 10):
            cframes.extend(segment_f0(ca, csr, t0, t0 + 10))
        cmed = pct(cframes, 50)
        ctrl['n_voiced_frames'] = len(cframes)
        ctrl['f0_median_hz'] = round(cmed, 2) if cmed else None
        ctrl['f0_p25_hz'] = round(pct(cframes, 25), 2) if cframes else None
        ctrl['f0_p75_hz'] = round(pct(cframes, 75), 2) if cframes else None
        ctrl['ok'] = bool(cmed and cmed < F0_MALE_MAX)
        print('=== 判据自检（控制组 = 已知单一男声切片）===')
        print('  控制组 F0 中位 = %s Hz（阈值 %s）⇒ %s'
              % (ctrl['f0_median_hz'], F0_MALE_MAX,
                 'OK' if ctrl['ok'] else '🔴 不可信'))
    else:
        ctrl['ok'] = False
        ctrl['why'] = '控制组切片不存在'
        print('!! 控制组不存在：%s' % ctrl_path)
    out['criterion_selftest'] = ctrl
    if not ctrl.get('ok'):
        out['verdict'] = 'ESTIMATOR_UNRELIABLE'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[evidence] %s' % args.out)
        return 0

    if not os.path.isfile(SRC_WAV):
        print('!! 找不到源 wav：%s' % SRC_WAV)
        return 2
    ref = json.load(open(REF_JSON, encoding='utf-8'))
    segs = ref['segments']
    print('源 wav =', SRC_WAV)
    print('参照   =', REF_JSON, '（%d 段 / %d 说话人）' % (len(segs), ref['n_speakers']))

    a, sr, nf = read_wav(SRC_WAV)
    out['src_wav'] = {'path': SRC_WAV, 'sr': sr, 'n_frames': nf,
                      'dur_s': round(nf / float(sr), 3),
                      'bytes': os.path.getsize(SRC_WAV)}
    print('源 wav  = %d 帧 / %.1f s / %d B' % (nf, nf / float(sr),
                                            os.path.getsize(SRC_WAV)))

    # ── 逐段测 F0 ──────────────────────────────────────────────
    per_spk = {}
    seg_rows = []
    for s in segs:
        spk = s.get('spk')
        if not spk or s.get('skip'):
            continue
        f0s = segment_f0(a, sr, s['t_start'], s['t_end'])
        med = pct(f0s, 50)
        seg_rows.append({'id': s['id'], 't_start': s['t_start'],
                         't_end': s['t_end'], 'spk': spk,
                         'dur_s': s.get('dur_s'),
                         'n_voiced_frames': len(f0s),
                         'f0_median': round(med, 2) if med else None,
                         'f0_p25': round(pct(f0s, 25), 2) if f0s else None,
                         'f0_p75': round(pct(f0s, 75), 2) if f0s else None})
        per_spk.setdefault(spk, {'frames': [], 'seg_ids': []})
        per_spk[spk]['frames'].extend(f0s)
        per_spk[spk]['seg_ids'].append(s['id'])

    spk_rows = []
    for spk in sorted(per_spk):
        fr = per_spk[spk]['frames']
        med = pct(fr, 50)
        cls = 'low_f0_male_presumed' if (med and med < F0_MALE_MAX) \
            else 'high_f0_female_presumed'
        spk_rows.append({
            'spk': spk, 'n_voiced_frames': len(fr),
            'n_segments': len(per_spk[spk]['seg_ids']),
            'f0_median_hz': round(med, 2) if med else None,
            'f0_p25_hz': round(pct(fr, 25), 2) if fr else None,
            'f0_p75_hz': round(pct(fr, 75), 2) if fr else None,
            'presumed_class': cls,
        })
    out['per_speaker'] = spk_rows
    print('\n=== 逐说话人基频 ===')
    for r in spk_rows:
        print('  %s: F0 中位 %s Hz (P25 %s / P75 %s)  帧 %d  段 %d  ⇒ %s'
              % (r['spk'], r['f0_median_hz'], r['f0_p25_hz'], r['f0_p75_hz'],
                 r['n_voiced_frames'], r['n_segments'], r['presumed_class']))

    male = [r['spk'] for r in spk_rows
            if r['presumed_class'] == 'low_f0_male_presumed']
    female = [r['spk'] for r in spk_rows
              if r['presumed_class'] == 'high_f0_female_presumed']
    out['male_spk'] = male
    out['female_spk'] = female
    print('推定男声 =', male, ' 推定女声 =', female)

    if not male or not female:
        out['verdict'] = 'NO_MIXED_GENDER_WINDOW'
        print('\n[verdict] NO_MIXED_GENDER_WINDOW ⇒ 无法满足「至少一男一女」')
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[evidence] %s' % args.out)
        return 0

    # ── 找窗口：覆盖男女双方 + 换人次数尽量多 ────────────────────
    win = float(args.window_s)
    usable = [s for s in seg_rows if s['f0_median']]
    cands = []
    starts = sorted({round(s['t_start'], 2) for s in usable})
    for st in starts:
        en = st + win
        inside = [s for s in usable if s['t_start'] >= st and s['t_end'] <= en]
        spks = sorted({s['spk'] for s in inside})
        if not (set(male) & set(spks)) or not (set(female) & set(spks)):
            continue
        # 换人次数 = 相邻段 spk 变化
        seq = sorted(inside, key=lambda x: x['t_start'])
        n_sw = sum(1 for i in range(1, len(seq)) if seq[i]['spk'] != seq[i - 1]['spk'])
        cands.append({'start_s': st, 'end_s': en, 'n_segments': len(inside),
                      'speakers': spks, 'n_switch': n_sw,
                      'male_in_window': sorted(set(male) & set(spks)),
                      'female_in_window': sorted(set(female) & set(spks))})
    cands.sort(key=lambda c: (-c['n_switch'], c['start_s']))
    out['n_candidates'] = len(cands)
    out['candidates_top10'] = cands[:10]
    if not cands:
        out['verdict'] = 'NO_MIXED_GENDER_WINDOW'
        print('\n[verdict] NO_MIXED_GENDER_WINDOW')
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[evidence] %s' % args.out)
        return 0

    best = cands[0]
    out['chosen_window'] = best
    out['segments_in_window'] = [s for s in usable
                                  if s['t_start'] >= best['start_s']
                                  and s['t_end'] <= best['end_s']]
    out['verdict'] = 'PASS'
    print('\n=== 选中窗口 ===')
    print('  start_s = %.2f  end_s = %.2f  （源 wav 绝对时间轴）' %
          (best['start_s'], best['end_s']))
    print('  说话人 =', best['speakers'], ' 换人 =', best['n_switch'],
          ' 段数 =', best['n_segments'])
    print('  男(推定) =', best['male_in_window'], ' 女(推定) =', best['female_in_window'])
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
