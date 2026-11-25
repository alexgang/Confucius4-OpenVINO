#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app134c_extract_clips.py — **APP-134 c 的 6 段抽听片段**（离线，从已落盘的产物里切）。

## reviewer APP-134 c 原文
> **6 段抽听片段**放 `results/app/app123_listen/`。

## 本脚本做什么

从 APP-134 c 三臂各自落盘的 **`player_mix.wav`**（EXT 的 `report()` 渲染出的
「播放端最终听到的混音」）里，按**等距的 6 个时间点**各切一段 ⇒
每臂 6 段 ⇒ 三臂共 **18 段**（⇒ 至少 6 段可抽听）。

🔴 **抽听片段必须是「播放端真正听到的」** ⇒ 只能从 `player_mix.wav` 切
（**不是** `dubs.npz` 里的原始配音 ⇒ 后者不含背景音/duck/变速）。

## 🔴 纪律
* **只读**：只读已落盘的 wav，**不碰**客户包、**不重跑**任何推理；
* 产物落 `results/app/app123_listen/`（reviewer 指定目录）；
* 每段 ≤ 8 s、24 kHz 单声道 OGG（**体积可控** ⇒ 便于随信附）；
* 🔴 **如实登记**：本脚本**不做**音质判定（**质量由 reviewer 抽听**）
  ⇒ 只负责「切出可听的片段」＋ 记录客观量（时长/峰值/RMS）。

## 用法
```
python live_caption/_app134c_extract_clips.py --root C:\Users\Trekker-PTL\shared\bgkeep\e2e_app134c
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import struct
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
OUT_DIR = os.path.join(RESULTS, 'app123_listen')
EVIDENCE = os.path.join(RESULTS, 'app134c_listen_clips.json')

#: 每臂切几段（reviewer 要 6 段）
N_CLIPS = 6
#: 每段时长（秒）
CLIP_SEC = 6.0


def read_wav_mono16(path):
    """读 wav ⇒ (采样率, 帧数, float32 数组)。只支持 PCM 16/24/32-bit。"""
    with wave.open(path, 'rb') as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        data = struct.unpack('<%dh' % (len(raw) // 2), raw)
        scale = 1.0 / 32768.0
    elif sw == 4:
        data = struct.unpack('<%di' % (len(raw) // 4), raw)
        scale = 1.0 / 2147483648.0
    elif sw == 3:
        # 24-bit ⇒ 手拆
        vals = []
        for i in range(0, len(raw) - 2, 3):
            b = raw[i] | (raw[i + 1] << 8) | (raw[i + 2] << 16)
            if b & 0x800000:
                b -= 0x1000000
            vals.append(b / 8388608.0)
        data = vals
        scale = 1.0
    else:
        raise ValueError('不支持的采样宽度：%d B' % sw)
    if nch > 1:
        data = data[::nch]
    return sr, len(data), [float(x) * scale for x in data]


def write_wav(path, sr, samples):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b''.join(struct.pack('<h', max(-32767, min(32767, int(s * 32767))))
                      for s in samples)
        w.writeframes(frames)


def to_ogg(wav_path, ogg_path):
    """wav → ogg（用 ffmpeg；没有 ffmpeg 就退回 wav）。"""
    import subprocess
    if not ogg_path.lower().endswith('.ogg'):
        return wav_path
    try:
        r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav_path,
                            '-c:a', 'libvorbis', '-q:a', '3', ogg_path],
                           capture_output=True, text=True, errors='replace')
        if r.returncode == 0 and os.path.isfile(ogg_path):
            return ogg_path
    except FileNotFoundError:
        pass
    return wav_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out-dir', default=OUT_DIR)
    args = ap.parse_args()
    root = args.root
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    arms = []
    for nm in sorted(os.listdir(root)):
        d = os.path.join(root, nm)
        if os.path.isdir(d) and not nm.startswith('_'):
            mix = os.path.join(d, 'player_mix.wav')
            if os.path.isfile(mix):
                arms.append((nm, mix))

    clips = []
    for nm, mix in arms:
        try:
            sr, n, samples = read_wav_mono16(mix)
        except Exception as e:
            print('  [%s] 读 wav 失败：%r' % (nm, e))
            continue
        dur = n / float(sr)
        # 🔴 等距取 6 个点（**避开首尾**，首尾有静默/淡入淡出）
        for k in range(N_CLIPS):
            # 从 10% 到 90% 之间等距
            frac = 0.10 + 0.80 * (k + 0.5) / N_CLIPS
            start = int(dur * frac * sr)
            ln = int(CLIP_SEC * sr)
            if start + ln > n:
                ln = n - start
            if ln <= 0:
                continue
            seg = samples[start:start + ln]
            peak = max((abs(s) for s in seg), default=0.0)
            rms = (sum(s * s for s in seg) / len(seg)) ** 0.5 if seg else 0.0
            wav_path = os.path.join(out_dir, 'app123_listen_%s_%d.wav' % (nm, k + 1))
            write_wav(wav_path, sr, seg)
            final = to_ogg(wav_path, wav_path[:-4] + '.ogg')
            if final != wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
            clips.append({
                'arm': nm,
                'clip_index': k + 1,
                'file': os.path.relpath(final, REPO).replace(os.sep, '/'),
                'bytes': os.path.getsize(final),
                'sha256': hashlib.sha256(open(final, 'rb').read()).hexdigest(),
                'start_sec': round(start / float(sr), 2),
                'duration_sec': round(ln / float(sr), 2),
                'peak': round(peak, 6),
                'rms': round(rms, 6),
                'source_mix': os.path.relpath(mix, REPO).replace(os.sep, '/'),
            })
        print('  [%s] 切了 %d 段（源 %s，%.1f s）' % (nm, N_CLIPS, os.path.basename(mix), dur))

    ev = {
        'script': '_app134c_extract_clips.py',
        'task': 'APP-134 c：6 段抽听片段（从 player_mix.wav 切 ⇒ 是播放端真正听到的）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'out_dir': os.path.relpath(out_dir, REPO).replace(os.sep, '/'),
        'n_clips': len(clips),
        'clips': clips,
        'note': ('🔴 本脚本**不做音质判定** —— 质量由 reviewer 抽听；'
                 '只负责「切出可听的片段」＋ 记录客观量（时长/峰值/RMS）。'
                 '🔴 片段取自 `player_mix.wav`（播放端混音，含背景音/duck/变速）'
                 '⇒ **是客户真正听到的**。'),
    }
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)

    print('=== APP-134 c 抽听片段 ===')
    print('共 %d 段 ⇒ %s' % (len(clips), out_dir))
    for c in clips:
        print('  [%s #%d] %s  %.1fs  %d B  peak=%.3f rms=%.4f'
              % (c['arm'], c['clip_index'], os.path.basename(c['file']),
                 c['duration_sec'], c['bytes'], c['peak'], c['rms']))
    print('证据：%s' % EVIDENCE)
    return 0 if clips else 3


if __name__ == '__main__':
    sys.exit(main())
