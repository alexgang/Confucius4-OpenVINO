#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-052：音频**回环自检** —— 程序播出去的声音，操作系统混音器到底收到没有？

为什么要有这个探针（用户反馈「语音输出听不到任何声音」）：
  `n_played=1` 只证明**音频回调把样本取走了**，不证明「声音进了系统混音器」，
  更不证明「用户能听到」。三个层次必须分开：

    ① App → PortAudio 输出流（回调在消费）      ← `n_played`
    ② 系统混音器收到（回环里能录到同样的波形）  ← **本探针**
    ③ 用户耳朵听到（终点设备/音量/插孔）        ← 只能人听

判据：
  - ② 的 RMS 明显 > 0 ⇒ App 侧链路没问题，问题在 ③（设备/音量/插孔/HDMI）；
  - ② 的 RMS ≈ 0     ⇒ 播到了「没有真实端点」的设备（或系统静音到混音器之前）。

做法：用 `soundcard` 打开「默认扬声器的 loopback」录音，同时用 `sounddevice`
在**同名**设备上播放，然后比对 RMS。

用法（客户包 python）：
    python results/app/app052_audio_loopback_probe.py
    python results/app/app052_audio_loopback_probe.py --sd-device 3
    # 🔴 一次跑多例（**证据累加、不再互相覆盖**）：
    python results/app/app052_audio_loopback_probe.py \
        --case 440Hz \
        --case CUDA=results/app/app040_synth_CUDA_bf16.wav \
        --case NPU=results/app/app040_synth_NPU_f16.wav

⚠️ 历史坑：本脚本**第一版**只保留「最后一次」结果 ⇒ 连跑三例后 json 只剩一例，
   证据链断裂（220:14 的 json 只留下 NPU 那一例）。现在改成 `cases` 数组累加。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app052_audio_loopback_probe.json')


def tone(sr, sec=1.0, freq=440.0, amp=0.3):
    import numpy as np
    n = int(sr * sec)
    t = np.arange(n, dtype='float32') / sr
    fade = np.minimum(1.0, np.minimum(np.arange(n), np.arange(n)[::-1]) / (sr * 0.02))
    return (amp * fade * np.sin(2 * math.pi * freq * t)).astype('float32')


def pick_speaker(sc, sd, sd_device):
    """把 sounddevice 的设备索引映射到 soundcard 的扬声器（按名字匹配）。"""
    name = sd.query_devices(sd_device, 'output')['name']
    spk = sc.all_speakers()
    for s in spk:
        if s.name and (s.name == name or name in s.name or s.name in name):
            return s, name
    for s in spk:
        if s.is_default:
            return s, name
    return (spk[0] if spk else None), name


def load_case(spec, sr_default=48000):
    """`LABEL` 或 `LABEL=path.wav` ⇒ (label, 波形 float32, 采样率, wav 路径或 None)。"""
    import numpy as np
    label, wav = (spec.split('=', 1) + [None])[:2] if '=' in spec else (spec, None)
    if wav is None:
        return label, tone(sr_default, 1.2), sr_default, None
    import wave as _w
    with _w.open(wav, 'rb') as _f:
        _sr, _n = _f.getframerate(), _f.getnframes()
        _raw = _f.readframes(_n)
    a = (np.frombuffer(_raw, dtype='<i2').astype('float32') / 32768.0)
    if _sr != sr_default:              # 简单线性重采样（只为测能量，不求音质）
        idx = np.linspace(0, len(a) - 1, int(len(a) * sr_default / _sr)).astype('int64')
        a = a[idx]
    return label, a, sr_default, wav


def run_case(a, sr, spk, sc, sd, dev):
    """回环录一遍，返回该例的测量值。"""
    import numpy as np
    sec = len(a) / sr
    # 🔴 soundcard 版本差异：`Speaker` 本身不一定带 `.recorder()`
    #   ⇒ 统一走 `get_microphone(id, include_loopback=True)` 拿回环麦克风
    mic = sc.get_microphone(str(spk.id), include_loopback=True)
    with mic.recorder(samplerate=sr, channels=1) as mic:
        time.sleep(0.2)
        sd.play(a, sr, device=dev)
        buf = mic.record(numframes=int((sec + 0.6) * sr))
        sd.wait()
    x = np.asarray(buf, dtype='float32').reshape(-1)
    rms = float(np.sqrt((x * x).mean())) if x.size else 0.0
    peak = float(np.abs(x).max()) if x.size else 0.0
    # 只保留「播放窗口」内的能量（前 0.2 s + 后 0.4 s 是静音）
    i0 = int(0.2 * sr)
    i1 = min(len(x), i0 + int(sec * sr))
    w = x[i0:i1]
    rms_w = float(np.sqrt((w * w).mean())) if w.size else 0.0
    return {'sec': round(sec, 3), 'sr': sr, 'n': int(x.size),
            'rms_all': round(rms, 5), 'rms_window': round(rms_w, 5),
            'peak': round(peak, 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--sd-device', type=int, default=None,
                    help='sounddevice 输出索引（默认 = 系统默认输出）')
    ap.add_argument('--case', action='append', default=None,
                    metavar='LABEL[=WAV]',
                    help='跑一例：`440Hz`（内置测试音）或 `CUDA=x.wav`（真实 TTS 音频）；可重复')
    ap.add_argument('--json', default=OUT, help='结果写入路径（默认同目录同名 json）')
    ap.add_argument('--append', action='store_true',
                    help='保留 json 里已有的 cases，把本轮结果追加进去')
    args = ap.parse_args()

    import sounddevice as sd
    import soundcard as sc

    dev = args.sd_device if args.sd_device is not None else sd.default.device[1]
    spk, sd_name = pick_speaker(sc, sd, dev)
    rec = {'sd_device': dev, 'sd_name': sd_name,
           'soundcard_speaker': getattr(spk, 'name', None), 'cases': []}
    print('sounddevice 输出索引 %d → 「%s」' % (dev, sd_name))
    print('soundcard 扬声器   → 「%s」' % getattr(spk, 'name', None))
    if spk is None or not spk.name:
        print('🔴 找不到可用的扬声器端点 ⇒ 无法回环')
        rec['verdict'] = False
        json.dump(rec, open(args.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 2

    specs = args.case or ['440Hz']
    if args.append and os.path.exists(args.json):
        try:
            old = json.load(open(args.json, encoding='utf-8'))
            rec['cases'] = [c for c in old.get('cases', [])
                            if c.get('sd_device') == dev]
        except Exception:
            pass

    rc = 0
    for spec in specs:
        label, a, sr, wav = load_case(spec)
        print('\n=== 例「%s」%s ===' % (label, ('  用 wav：%s' % wav) if wav else '  内置 440 Hz'))
        case = {'label': label, 'wav': wav, 'sd_device': dev, 'sd_name': sd_name}
        try:
            case.update(run_case(a, sr, spk, sc, sd, dev))
        except Exception as e:
            case.update({'rms_window': None, 'verdict': False,
                         'error': '%s: %s' % (type(e).__name__, e)})
            print('🔴 本例失败：%s' % case['error'])
            rec['cases'].append(case)
            rc = 1
            continue
        ok = case['rms_window'] > 0.005
        case['verdict'] = bool(ok)
        print('回环 RMS（整段）= %.5f   峰值 = %.4f' % (case['rms_all'], case['peak']))
        print('回环 RMS（播放窗口内）= %.5f  ⇒ %s'
              % (case['rms_window'], 'PASS' if ok else 'FAIL'))
        rec['cases'].append(case)
        if not ok:
            rc = 1

    all_ok = bool(rec['cases']) and all(c.get('verdict') for c in rec['cases'])
    rec['verdict'] = all_ok
    rec['verdict_note'] = (
        '② 通过：所有例子都在系统混音器里录到了信号 ⇒ App 侧链路没问题，'
        '听不到要去查**终点设备 / 音量 / 静音 / 插孔**'
        if all_ok else
        '② 失败：混音器里几乎没有信号 ⇒ 播放写到了一个**没有真实端点**的设备'
        '（或系统在混音前就静音了）')
    print('\n===== 汇总（%d 例）=====' % len(rec['cases']))
    for c in rec['cases']:
        print('  %-14s rms_window=%-9s peak=%-8s %s'
              % (c.get('label'), c.get('rms_window'), c.get('peak'),
                 'PASS' if c.get('verdict') else 'FAIL'))
    print('\n结论：%s — %s' % ('PASS' if all_ok else 'FAIL', rec['verdict_note']))
    json.dump(rec, open(args.json, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('结果：', args.json)
    return rc


if __name__ == '__main__':
    sys.exit(main())
