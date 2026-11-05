#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app247 — 把 app246 选中的「男+女混合 SPE 片段」**切成一个 wav**，供设备级实测。

## 为什么（APP-067 ②）
> 请另选一段有男有女的 SPE 片段（**先写明起止时间**），做完第 1 项后再交。

## 产物
* `shared/app_listen/v23_clone/SPE_mix_<start>_<end>.wav`（16 kHz 单声道 16-bit）
* `shared/app_listen/v23_clone/mix_segment_manifest.json`
  （源 wav 的路径 / 起止时间 / SHA256 / 切片后 SHA256 / 字节数 / 参与者）

## 🔴 口径
* 切片**不改采样率、不重采样**（逐样本拷贝）⇒ 源 wav 与切片**逐样本等价**。
* 起止时间取自 `app246` 的证据 json（**不重新推断**）⇒ 唯一事实来源是 app246。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

SRC_WAV = os.path.join(REPO, 'test_audio', '260902_SPE_audio.wav')
EV_JSON = os.path.join(HERE, 'app246_app067_spk_gender_segment_evidence.json')
OUT_DIR = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ev', default=EV_JSON)
    ap.add_argument('--out-dir', default=OUT_DIR)
    args = ap.parse_args()

    ev = json.load(open(args.ev, encoding='utf-8'))
    win = ev['chosen_window']
    t0, t1 = float(win['start_s']), float(win['end_s'])
    print('选中窗口（app246 证据）: %.2f – %.2f s' % (t0, t1))
    print('参与者: %s  换人 %d  段 %d'
          % (win['speakers'], win['n_switch'], win['n_segments']))

    os.makedirs(args.out_dir, exist_ok=True)
    out_wav = os.path.join(
        args.out_dir, 'SPE_mix_%d_%d.wav' % (int(round(t0)), int(round(t1))))

    with wave.open(SRC_WAV, 'rb') as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        i0 = int(round(t0 * sr))
        i1 = int(round(t1 * sr))
        w.setpos(i0)
        raw = w.readframes(i1 - i0)
        n = len(raw) // sw

    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(nch)
        w.setsampwidth(sw)
        w.setframerate(sr)
        w.writeframes(raw)

    man = {
        'created_by': 'app247_app067_make_mix_segment.py',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'correction': 'APP-067 ②',
        'source_wav': {'path': SRC_WAV, 'bytes': os.path.getsize(SRC_WAV),
                       'sha256': sha256(SRC_WAV), 'sr': sr, 'nch': nch,
                       'sampwidth': sw,
                       'dur_s': round(os.path.getsize(SRC_WAV) / (sr * nch * sw), 3)},
        'window': {'start_s': t0, 'end_s': t1, 'dur_s': round(t1 - t0, 3),
                   'speakers': win['speakers'],
                   'male_presumed': win['male_in_window'],
                   'female_presumed': win['female_in_window'],
                   'n_switch': win['n_switch'],
                   'n_segments': win['n_segments']},
        'cut_wav': {'path': out_wav, 'bytes': os.path.getsize(out_wav),
                    'sha256': sha256(out_wav), 'sr': sr, 'nch': nch,
                    'sampwidth': sw, 'n_samples': n,
                    'dur_s': round(n / float(sr), 3),
                    'sample_offset_in_source': i0},
        'note': ('切片是源 wav 的**逐样本拷贝**（不重采样）⇒ 切片内 t 秒 '
                 '= 源 wav 内 (start_s + t) 秒 ⇒ 原声参考片段可按此换算'),
        'evidence_from': os.path.basename(args.ev),
        'per_speaker_f0': ev.get('per_speaker'),
        'criterion_selftest': ev.get('criterion_selftest'),
    }
    man_path = os.path.join(args.out_dir, 'mix_segment_manifest.json')
    with open(man_path, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1)

    print('切片 =', out_wav)
    print('  %d B / %d 样本 / %.3f s / sha=%s'
          % (man['cut_wav']['bytes'], n, man['cut_wav']['dur_s'],
             man['cut_wav']['sha256'][:16]))
    print('清单 =', man_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
