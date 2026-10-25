#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""声卡自检：确认「程序到底有没有把声音送出去」以及「送去了哪个设备」。

用户反馈「语音输出听不到声音」时，先跑这个 —— 它把问题**切成两半**：

- 如果**这个工具**在某台设备上能响，但 App 不响 ⇒ 问题在 App 用的设备/链路；
- 如果**这个工具**在所有设备上都不响 ⇒ 问题在系统（音量/静音/输出端点/耳机插孔）。

用法（用**客户包**的 python）：
    python app\\audio_check.py                # 列设备 + 依次在每台设备上响两声
    python app\\audio_check.py --device 3     # 只在指定 index 上响
    python app\\audio_check.py --play-wav out.wav --device 3   # 用真实 TTS 音频试
"""
from __future__ import annotations

import argparse
import sys
import time
import wave


def _tone(sr, seconds=1.2, freq=440.0):
    import math
    n = int(sr * seconds)
    # 加淡入淡出，避免爆音；中间留 0.25 s 静音，听成「两声」
    out = []
    half = n // 2
    for i in range(n):
        if i < half // 2 or i >= n - half // 2:
            env = 0.0
        else:
            env = min(1.0, (i % 2400) / 240.0)
        out.append(0.25 * env * math.sin(2 * math.pi * freq * i / sr))
    return out


def list_out(sd):
    rows = []
    for i, d in enumerate(sd.query_devices()):
        if d['max_output_channels'] > 0:
            rows.append((i, d['name'], sd.query_hostapis(d['hostapi'])['name'],
                         int(d['default_samplerate'])))
    return rows


def play(sd, samples, sr, device):
    import numpy as np
    a = np.asarray(samples, dtype='float32')
    sd.play(a, sr, device=device)
    sd.wait()
    time.sleep(0.15)


def read_wav(path):
    import numpy as np
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype='<i2').astype('float32') / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch)[:, 0]
    return a, sr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', type=int, default=None)
    ap.add_argument('--play-wav', default=None, help='用这个 wav 代替测试音')
    ap.add_argument('--sr', type=int, default=48000)
    ap.add_argument('--gap', type=float, default=1.2)
    args = ap.parse_args()

    import sounddevice as sd

    print('默认输出设备索引：', sd.default.device[1])
    try:
        print('默认输出设备名  ：', sd.query_devices(kind='output')['name'])
    except Exception as e:
        print('默认输出设备名  ： 查询失败', e)
    print('\n=== 可用的输出设备 ===')
    rows = list_out(sd)
    for i, name, host, dsr in rows:
        mark = '  <= 默认' if i == sd.default.device[1] else ''
        print('%2d  [%s] sr=%d  %s%s' % (i, host, dsr, name, mark))

    targets = [args.device] if args.device is not None else [r[0] for r in rows]
    if args.play_wav:
        samples, sr = read_wav(args.play_wav)
        print('\n用 wav：%s（%.2f s @ %d Hz）' % (args.play_wav,
                                               len(samples) / sr, sr))
    else:
        sr = args.sr
        samples = _tone(sr)
        print('\n用测试音：440 Hz / %.1f s @ %d Hz' % (len(samples) / sr, sr))

    heard = []
    for dev in targets:
        name = next((r[1] for r in rows if r[0] == dev), '?')
        print('\n▶ 正在设备 %d「%s」播放…' % (dev, name), flush=True)
        try:
            play(sd, samples, sr, dev)
            print('  ✅ 播放 API 没报错（是否真的听到要看你的耳朵）')
            heard.append(dev)
        except Exception as e:
            print('  🔴 播放失败：%s: %s' % (type(e).__name__, e))
        time.sleep(args.gap)

    print('\n=== 结论怎么读 ===')
    print('  ① 某台设备响了 ⇒ 把 App「语音输出 → 输出设备」也选成**同一台**；')
    print('  ② 全都不响 ⇒ 查 Windows 音量/静音、输出端点是否被切到 HDMI、耳机插孔；')
    print('  ③ 全部播放都报错 ⇒ 系统音频服务异常（重启 Windows Audio 服务）。')
    print('  能播的 index：', heard)
    return 0


if __name__ == '__main__':
    sys.exit(main())
