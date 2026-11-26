#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app245_extract_samples.py — **APP-148 §1c 抽听样片**（§245 版，改用 numpy 读大文件）。

## 为什么另写一份
`_app148_extract_samples.py` 用 `array` + **Python float 列表**读 `player_mix.wav`：
10 分钟 / 48 kHz / 立体声 = 2 880 万帧 ⇒ 纯列表转换在**本轮实测里直接静默退出**
（rc=127，无 traceback；同一条命令 `--help` 正常 ⇒ 死在 `read_wav`）。
本脚本用 **numpy** 读/转/写，内存 ~230 MB（int16 原始 + float32 单声道）。

## 口径（与 reviewer 原文一致）
* 样片必须来自**播放端真正听到的混音** ⇒ 切 `player_mix.wav`（不是 `dubs.npz`）；
* 每段 **30–60 s**，编码 **OGG ≤ 1 MB**（包内 python 的 soundfile / libsndfile 1.2.2，不用 ffmpeg）；
* 优先「男女声切换」段 —— 🔴 本轮**没有逐段性别标签**（`n_gender_splits=4` 只有计数、无时刻）
  ⇒ 按**早/中/晚等距**取 3 段并在证据里如实写明，**不假装挑到了切换段**；
* 附带统计：**synth 撞 39 s 上限的句数**、**含 NaN/Inf 的句数**、**削波**（混音里 |x|≥0.999 的采样点）。

## 用法
```
<包内 python> live_caption/_app245_extract_samples.py \
    --arm-dir <clone 臂目录> --out results\app\app245_listen
```
"""
import argparse
import json
import os
import time
import wave

import numpy as np

TARGET_BYTES = 1000000
CLIP_SEC = 40.0


def read_mix(path):
    """读 wav ⇒ (sr, float32 单声道, 原始帧数, 声道数)"""
    with wave.open(path, 'rb') as w:
        nch, sw, sr, nf = (w.getnchannels(), w.getsampwidth(),
                           w.getframerate(), w.getnframes())
        raw = w.readframes(nf)
    if sw != 2:
        raise RuntimeError('只支持 16-bit wav，实际 sampwidth=%d' % sw)
    a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    if nch > 1:
        a = a.reshape(-1, nch).mean(axis=1)
    return sr, a, nf, nch


def write_wav16(path, sr, x):
    y = np.clip(x, -1.0, 1.0)
    y = (y * 32767.0).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())


def to_ogg(wav_path, ogg_path, sr, x):
    """wav → **Ogg/Opus**（libsndfile）。

    🔴 §245 实测：本机 libsndfile 1.2.2 的 **VORBIS 编码器会爆栈**
    （单次 `sf.write` 样本数 ≳ 4.8e5 即 `stack overflow` / rc=3221225725；
    10 s@48k 可以、20 s@48k 崩、16k 30 s 可以、16k 40 s 崩；**OPUS 40 s@16k 正常**）。
    证据：`results/app/app245_ogg_threshold.json`。
    所以这里走 **OPUS @16 kHz**：语音抽听够用，40 s ≈ 120 KB ≪ 1 MB。
    """
    import soundfile as sf
    attempts = []
    step = max(1, int(round(sr / 16000.0)))
    y = x if step == 1 else x[:len(x) // step * step].reshape(-1, step).mean(axis=1)
    osr = int(sr / step) if step > 1 else sr
    targets = [(osr, 'OPUS'), (8000, 'VORBIS')]
    for rate, subtype in targets:
        z = y if rate == osr else y[::max(1, int(round(osr / float(rate))))]
        try:
            sf.write(ogg_path, z, rate, format='OGG', subtype=subtype)
        except Exception as e:
            attempts.append({'subtype': subtype, 'sr': rate, 'error': str(e)})
            continue
        size = os.path.getsize(ogg_path)
        attempts.append({'subtype': subtype, 'sr': rate, 'bytes': size})
        if size <= TARGET_BYTES:
            return ogg_path, attempts
    return (ogg_path if os.path.isfile(ogg_path) else None), attempts


def synth_stats(arm_dir):
    """撞 39 s 上限 / NaN·Inf / 语速倍率：以 `margin.json` 的 per_segment 为准。"""
    out = {'source': None}
    mp = os.path.join(arm_dir, 'margin.json')
    if not os.path.isfile(mp):
        return out
    with open(mp, encoding='utf-8') as fh:
        j = json.load(fh)
    segs = j.get('per_segment') or []
    n39 = n_nan = 0
    sp_max, speeds = None, []
    tts_max = None
    for s in segs:
        for k in ('tts_sec', 'speech_sec', 'proc_sec'):
            v = s.get(k)
            if isinstance(v, float) and (v != v or v in (float('inf'), float('-inf'))):
                n_nan += 1
                break
        t = s.get('tts_sec')
        if isinstance(t, (int, float)) and t == t:
            tts_max = t if tts_max is None else max(tts_max, t)
            if t >= 39.0:
                n39 += 1
        for k in ('speed', 'adapt_speed'):
            v = s.get(k)
            if isinstance(v, (int, float)) and v == v:
                speeds.append(float(v))
    if speeds:
        sp_max = max(speeds)
    out.update({'source': mp, 'n_segments': len(segs),
                'n_synth_ge_39s': n39, 'n_nan_or_inf_segments': n_nan,
                'tts_sec_max': None if tts_max is None else round(tts_max, 3),
                'speed_max': None if sp_max is None else round(sp_max, 3),
                'note': '撞上限按 per_segment.tts_sec ≥ 39.0；NaN/Inf 按 tts_sec/'
                        'speech_sec/proc_sec 任一非有限；语速取 speed/adapt_speed 最大'})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm-dir', required=True)
    ap.add_argument('--out', default=r'C:\Users\Trekker-PTL\confucius4-openvino'
                                    r'\results\app\app245_listen')
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--clip-sec', type=float, default=CLIP_SEC)
    a = ap.parse_args()

    mix = os.path.join(a.arm_dir, 'player_mix.wav')
    if not os.path.isfile(mix):
        print('找不到 player_mix.wav：%s' % mix)
        return 2
    t0 = time.time()
    sr, data, nf, nch = read_mix(mix)
    total = len(data) / float(sr)
    print('player_mix.wav：%d Hz / %d ch / %d 帧 / %.1f s（读入 %.1f s）'
          % (sr, nch, nf, total, time.time() - t0))

    seg_len = int(a.clip_sec * sr)
    n = a.n
    starts = [int(((total - a.clip_sec) * (i + 0.5) / n) * sr) for i in range(n)]

    # 能量优先（等距起点之间不动，只挑能量高的 ⇒ 不会三段挤在一起）
    energies = [float(np.sqrt(np.mean(np.square(data[p:p + seg_len]))))
                if p + seg_len <= len(data) else 0.0 for p in starts]
    chosen = list(range(n))

    os.makedirs(a.out, exist_ok=True)
    clips = []
    for idx, ci in enumerate(chosen, 1):
        pos = starts[ci]
        seg = data[pos:pos + seg_len]
        wav_p = os.path.join(a.out, 'app245_listen_clone_%d.wav' % idx)
        write_wav16(wav_p, sr, seg)
        ogg_p = wav_p[:-4] + '.ogg'
        got, attempts = to_ogg(wav_p, ogg_p, sr, seg)
        peak = float(np.max(np.abs(seg))) if seg.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(seg)))) if seg.size else 0.0
        clipped = int(np.sum(np.abs(seg) >= 0.999))
        clips.append({
            'idx': idx, 'wav': wav_p, 'ogg': got,
            'ogg_bytes': os.path.getsize(ogg_p) if os.path.isfile(ogg_p) else None,
            'start_sec': round(pos / float(sr), 2),
            'duration_sec': round(len(seg) / float(sr), 2),
            'rms': round(rms, 5), 'peak': round(peak, 5),
            'n_clipped_samples': clipped,
            'clipped_ratio': round(clipped / max(1, seg.size), 8),
            'encode_attempts': attempts,
        })
        print('  片段 %d：%.1f s @ %.1f s，rms=%.4f peak=%.3f，ogg %s B'
              % (idx, clips[-1]['duration_sec'], clips[-1]['start_sec'],
                 rms, peak, clips[-1]['ogg_bytes']))

    st = synth_stats(a.arm_dir)
    mix_clipped = int(np.sum(np.abs(data) >= 0.999))
    payload = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'script': '_app245_extract_samples.py',
        'task': 'APP-148 §1c：抽听样片（保留背景音开 + clone 那轮的播放端混音）',
        'source_mix': mix, 'sample_rate': sr, 'channels': nch,
        'total_sec': round(total, 2),
        'clips': clips,
        'mix_clipping': {'n_samples_ge_0999': mix_clipped,
                         'n_samples': int(data.size),
                         'ratio': round(mix_clipped / max(1, data.size), 8)},
        'synth_stats': st,
        'note': ('🔴 只切片段、不做音质判定（质量由 reviewer/用户抽听）；'
                 '🔴 无逐段性别标签 ⇒ 早/中/晚等距取段，未定向挑「男女声切换」段。'),
    }
    p = os.path.join(a.out, 'app245_listen.json')
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print('\nsynth 统计：%s' % json.dumps(st, ensure_ascii=False))
    print('混音削波：%s' % json.dumps(payload['mix_clipping'], ensure_ascii=False))
    print('\n落盘 ->', p)
    ok = all(c['ogg_bytes'] and c['ogg_bytes'] <= TARGET_BYTES for c in clips)
    print('OGG ≤1MB 全部达标：%s' % ('YES' if ok else 'NO'))
    return 0 if ok else 3


if __name__ == '__main__':
    raise SystemExit(main())
