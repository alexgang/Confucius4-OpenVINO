# -*- coding: utf-8 -*-
"""🔴 APP-075 根因复核：**独立重测**「混合 wav」各段的实测 F0。

## 为什么必须独立重测
reviewer 的 APP-071 表格说 `male_01_seg5 / male_02_seg2 / male_03_seg4`
三段的「源说话人 F0 = 118 Hz（男声 S2）」，
而上一轮的 `app293` 逐段实测说 **seg2 的实测 F0 = 175.82 Hz（女声）**。
⇒ 两者**矛盾** ⇒ 必须**独立重算**，否则整个修复方向会建立在错误前提上。

## 口径
* 用 **app246 的 `f0_autocorr`**（同一把尺，含八度误差修正）
* 输入：`shared/app_listen/v23_clone/SPE_mix_3303_3603.wav`（切片内时间轴）
* 段区间取自 `app250_device_out/tts_on_clone_1.seg.jsonl`（设备实测段表）

## 输出
`_app295_f0_verify.json`
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')
MIX = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone',
                    'SPE_mix_3303_3603.wav')
SEG = os.path.join(HERE, 'app250_device_out', 'tts_on_clone_1.seg.jsonl')
EV = os.path.join(HERE, '_app293_label_overlap.json')
OUT = os.path.join(HERE, '_app295_f0_verify.json')

F0_MALE_MAX = 160.0
F0_FEMALE_MIN = 170.0


def load_app246():
    p = os.path.join(HERE, 'app246_app067_spk_gender_segment.py')
    spec = importlib.util.spec_from_file_location('app246_mod', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m246 = load_app246()
    a, sr, nf = m246.read_wav(MIX)

    rows = []
    with open(SEG, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get('t0') is not None and r.get('t1') is not None:
                rows.append(r)
    rows.sort(key=lambda r: float(r['t0']))

    old = {}
    if os.path.isfile(EV):
        d = json.load(open(EV, encoding='utf-8'))
        for r in d.get('per_seg', []):
            old[int(r['seg'])] = r

    out = {'script': os.path.basename(__file__),
           'correction': 'APP-075 根因复核（独立重测 F0）',
           'mix_wav': {'path': MIX, 'bytes': os.path.getsize(MIX),
                       'sr': sr, 'dur_s': round(nf / float(sr), 3)},
           'f0_criterion': {'male_max_hz': F0_MALE_MAX,
                            'female_min_hz': F0_FEMALE_MIN},
           'segments': []}

    for r in rows:
        seg = int(r['seg'])
        t0, t1 = float(r['t0']), float(r['t1'])
        f0s = m246.segment_f0(a, sr, t0, t1)
        vals = sorted(f0s)
        med = vals[len(vals) // 2] if vals else 0.0
        if med and med < F0_MALE_MAX:
            cls = 'male'
        elif med and med >= F0_FEMALE_MIN:
            cls = 'female'
        else:
            cls = 'mid_or_none'
        o = old.get(seg) or {}
        out['segments'].append({
            'seg': seg, 't0': t0, 't1': t1,
            'spk': r.get('spk'), 'spk_conf': r.get('spk_conf'),
            'measured_f0_median': round(med, 2),
            'measured_class': cls,
            'n_voiced_frames': len(vals),
            'app293_f0_median': o.get('measured_f0_median'),
            'app293_class': o.get('measured_class'),
            'agrees_with_app293': (abs(float(o.get('measured_f0_median') or 0)
                                       - med) < 1.0) if o else None,
        })

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('seg  spk  conf      f0(new)  class    f0(app293)  class(app293)  agree')
    for s in out['segments'][:20]:
        print('%3d  %-4s %-8s %7.2f  %-8s  %10s  %-12s  %s'
              % (s['seg'], s['spk'], s['spk_conf'], s['measured_f0_median'],
                 s['measured_class'], s['app293_f0_median'],
                 s['app293_class'], s['agrees_with_app293']))
    print('\n[evidence] %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
