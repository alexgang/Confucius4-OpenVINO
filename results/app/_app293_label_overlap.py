# -*- coding: utf-8 -*-
"""APP-071 根因定位（**纯 CPU / 只读**）：App 的 ASR 说话人标签 vs 地面真值。

## 目的
APP-071 (b) 要求「S2 克隆音色对原声 S2 的余弦必须高于对 S1/S3 的余弦」。
在动登记逻辑之前，必须先回答一个前置问题：

> **App 自己打的说话人标签**（`spk_voice` 段表里的 `S1..S4`）
> 与**地面真值**（`mix_segment_manifest.json` 的 `S1..S5`）是不是同一套编号？

若两套编号**不是同一套**（哪怕都叫 "S2"），则
「克隆音色对原声 S2 的余弦」这条判据的**参照物本身就是错的**
⇒ 必须先把「谁是男声」这件事查清楚，才知道该修哪一层。

## 口径
- 地面真值段（`app246`）用**源 wav 绝对时刻**；切片起点 `3302.72` ⇒
  **相对时刻 = 绝对时刻 − 3302.72**。
- App 的 ASR 段表（`app250` 的 `seg.jsonl`）用的是**切片内相对时刻**。
- 两者都映射到「切片内相对时刻」后再比较。

## 输出
`_app293_label_overlap.json`（供 STATUS §140 引用）
"""
from __future__ import annotations

import json
import math
import os
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SEG_JSONL = os.path.join(REPO, 'results', 'app', 'app250_device_out',
                         'tts_on_clone_1.seg.jsonl')
APP246 = os.path.join(REPO, 'results', 'app',
                      'app246_app067_spk_gender_segment_evidence.json')
MANIFEST = (r'C:\Users\Trekker-PTL\shared\app_listen\v23_clone'
            r'\mix_segment_manifest.json')
OUT = os.path.join(HERE, '_app293_label_overlap.json')

SR = 16000
FRAME_MS = 40
HOP_MS = 10
F0_MIN = 60.0
F0_MAX = 400.0
MALE_MAX_HZ = 160.0
FEMALE_MIN_HZ = 170.0


def read_wav_mono16(path: str):
    import numpy as np
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        nf = w.getnframes()
        raw = w.readframes(nf)
    a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    if nch > 1:
        a = a.reshape(-1, nch)[:, 0]
    return a, sr


def f0_autocorr(frame, sr, fmin=F0_MIN, fmax=F0_MAX) -> float:
    """自相关法基频（**逐字复用 app246/app283 的实现** ⇒ 口径一致）。"""
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
    m = 1 << int(math.ceil(math.log2(2 * n)))
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
    peaks = []
    for i in range(1, seg.size - 1):
        v = float(seg[i])
        if v >= float(seg[i - 1]) and v > float(seg[i + 1]):
            peaks.append((lag_min + i, v))
    if not peaks:
        return 0.0
    gmax = max(v for _, v in peaks)
    if gmax < 0.25:
        return 0.0
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
        if float(np.sqrt(np.mean(fr * fr))) < 0.01:
            continue
        f0 = f0_autocorr(fr, sr)
        if f0 > 0 and f0 < 0.97 * F0_MAX:
            out.append(f0)
    return out


def median(vals):
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def load_app_segs():
    rows = []
    with open(SEG_JSONL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get('spk') and r.get('t0') is not None:
                rows.append(r)
    rows.sort(key=lambda r: (float(r['t0']), int(r['seg'])))
    return rows


def main():
    import numpy as np
    man = json.load(open(MANIFEST, encoding='utf-8'))
    win = man['window']
    cut_start = float(man['cut_wav']['sample_offset_in_source']) / float(SR)
    mix_path = man['cut_wav']['path']
    gt = json.load(open(APP246, encoding='utf-8'))

    # 地面真值段（绝对 → 切片内相对）
    gt_segs = []
    for s in gt['segments_in_window']:
        gt_segs.append(dict(
            id=s['id'],
            t0=float(s['t_start']) - cut_start,
            t1=float(s['t_end']) - cut_start,
            gt_spk=s['spk'],
            gt_f0_median=s.get('f0_median'),
            n_voiced=s.get('n_voiced_frames')))
    gt_segs.sort(key=lambda s: s['t0'])

    app_rows = load_app_segs()
    a, sr = read_wav_mono16(mix_path)

    # 逐 App 段：测该段真实 F0（切片音频）＋ 找地面真值重叠
    per_seg = []
    for r in app_rows:
        t0, t1 = float(r['t0']), float(r['t1'])
        f0s = segment_f0(a, sr, t0, t1)
        med = median(f0s)
        ov = [g for g in gt_segs
              if min(t1, g['t1']) - max(t0, g['t0']) > 0.25]
        ov.sort(key=lambda g: -min(t1, g['t1']) + max(t0, g['t0']))
        ov.sort(key=lambda g: (min(t1, g['t1']) - max(t0, g['t0'])),
                reverse=True)
        per_seg.append(dict(
            seg=r['seg'], app_spk=r['spk'], app_conf=r.get('spk_conf'),
            t0=round(t0, 3), t1=round(t1, 3),
            measured_f0_median=round(med, 2) if med else None,
            measured_class=('male' if med and med < MALE_MAX_HZ else
                            ('female' if med and med > FEMALE_MIN_HZ
                             else 'mid_or_none')),
            gt_overlap=[dict(gt_spk=g['gt_spk'],
                             gt_f0_median=g['gt_f0_median'],
                             ov_s=round(min(t1, g['t1']) - max(t0, g['t0']), 2))
                        for g in ov[:3]]))

    # 汇总：App 的每个 spk ⇒ 它覆盖的音频真实 F0 分布
    per_app_spk = {}
    for s in per_seg:
        if s['measured_f0_median'] is None:
            continue
        d = per_app_spk.setdefault(s['app_spk'], dict(
            n_segments=0, f0s=[], gt_counter={}, segs=[]))
        d['n_segments'] += 1
        d['f0s'].append(s['measured_f0_median'])
        d['segs'].append(s['seg'])
        for g in s['gt_overlap']:
            d['gt_counter'][g['gt_spk']] = \
                d['gt_counter'].get(g['gt_spk'], 0) + 1

    summary = {}
    for spk, d in sorted(per_app_spk.items()):
        med = median(d['f0s'])
        summary[spk] = dict(
            n_segments=d['n_segments'],
            measured_f0_median=round(med, 2) if med else None,
            measured_class=('male' if med and med < MALE_MAX_HZ else
                            ('female' if med and med > FEMALE_MIN_HZ
                             else 'mid_or_none')),
            f0_min=round(min(d['f0s']), 2),
            f0_max=round(max(d['f0s']), 2),
            gt_spk_overlap=d['gt_counter'],
            segs=d['segs'])

    # 关键交叉表：地面真值「男声段」被 App 打成了哪个 spk
    male_gt = [g for g in gt_segs
               if g['gt_f0_median'] is not None
               and g['gt_f0_median'] < MALE_MAX_HZ]
    male_map = {}
    for g in male_gt:
        hits = [s for s in per_seg
                if min(g['t1'], s['t1']) - max(g['t0'], s['t0']) > 0.25]
        if not hits:
            continue
        hits.sort(key=lambda s: (min(g['t1'], s['t1']) - max(g['t0'], s['t0'])),
                  reverse=True)
        h = hits[0]
        male_map.setdefault(h['app_spk'], []).append(
            dict(gt_id=g['id'], app_seg=h['seg'], app_conf=h['app_conf'],
                 gt_f0_median=g['gt_f0_median'],
                 app_measured_f0=h['measured_f0_median']))

    out = dict(
        script=os.path.basename(__file__),
        correction='APP-071 根因定位（标签体系对齐 + 逐段实测 F0）',
        mode='cpu_readonly',
        cut_start_s=cut_start,
        mix_wav=dict(path=mix_path, bytes=os.path.getsize(mix_path),
                     sr=sr, dur_s=round(a.size / float(sr), 3)),
        n_app_segs=len(app_rows),
        n_gt_segs=len(gt_segs),
        n_gt_male_segs=len(male_gt),
        per_app_spk=summary,
        male_gt_to_app_spk={k: dict(n=len(v), items=v[:12])
                            for k, v in male_map.items()},
        per_seg=per_seg,
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('== App spk ⇒ 切片内实测 F0（该 spk 覆盖的音频）==')
    for spk, v in summary.items():
        print('  %s: n=%-3d F0med=%-8s class=%-6s gt_overlap=%s'
              % (spk, v['n_segments'], v['measured_f0_median'],
                 v['measured_class'], v['gt_spk_overlap']))
    print('\n== 地面真值男声段 ⇒ App 打成了哪个 spk ==')
    for spk, v in male_map.items():
        print('  %s: n=%d  e.g. %s'
              % (spk, len(v),
                 ', '.join('gt%s/seg%s(conf=%s,实测F0=%s)'
                           % (x['gt_id'], x['app_seg'], x['app_conf'],
                              x['app_measured_f0']) for x in v[:5])))
    print('\nOUT = %s' % OUT)


if __name__ == '__main__':
    main()
