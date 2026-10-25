#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-040：TTS **只验合成**（不碰播放）—— 把「合成」与「播放设备」解耦。

🔴🔴 **为什么必须单独一个脚本**（本轮实测踩到的坑）：
   `app039_tts_e2e_smoke.py` 让 worker 走完整链路（合成 + 写播放环形缓冲），
   但在**后台非交互会话**里音频回调线程不消费（`已有 0`）
   ⇒ 环形缓冲只有 **3 s**（`RingBuffer(capacity=sr*3)` = 72 000 帧）
   ⇒ 只要句子音频 > 3 s 就必然「写入超时」⇒ 判定 FAIL
   ⇒ **这个 FAIL 与 TTS 能不能合成无关**，是播放环境的伪结果。

⇒ 本脚本**绕开 sounddevice**，直接调 `tts_engine.make_engine` + `tts_engine.stream`，
   只看三件事：
     1. 引擎能否加载（7 个 IR 全编过）；
     2. 合成出的**音频时长**是否合理（≈ 字数 × 0.25~0.35 s）；
     3. 是否**跑满 `max_decoder_frames=512`**（= 1920×512 = 983 040 样本
        = 40.96 s ⇒ talker 没发出 EOS = **失控**，是缺陷不是「话长」）。
   并把音频落成 wav 供人工抽听。

🔴 必须用**客户包**的 python：
   `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.5\\python\\python.exe`
用法：
   `app040_tts_synth_only.py --device NPU --precision f16`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5"
APP_DIR = os.path.join(PKG, "app")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "app040_tts_synth_only.json")

# 合成句（**不用真实语料**，守「写举例一律用合成句」铁律）
SENTENCE = "这是一次语音输出的自测，用来确认朗读功能可以正常工作。"

FRAME_SAMPLES = 1920        # 每帧 1920 样本（80 ms @ 24 kHz）
MAX_FRAMES = 512            # = tts_engine.MAX_DECODER_FRAMES
SR = 24000


def run_one(device, precision, out_wav):
    import numpy as np
    import tts_engine

    logs = []

    def log(m):
        logs.append(str(m))
        print('   [log]', m)

    rec = {'device': device, 'precision': precision, 'logs': logs,
           'ready': False, 'samples': 0, 'seconds': 0.0,
           'frames': 0.0, 'hit_max_frames': False,
           'err': None, 'wav': out_wav}

    t0 = time.perf_counter()
    try:
        eng = tts_engine.make_engine(device=device, precision=precision,
                                     on_log=log)
    except Exception as e:
        rec['err'] = '%s: %s' % (type(e).__name__, e)
        rec['load_s'] = round(time.perf_counter() - t0, 2)
        print('   !! 引擎加载失败：%s' % rec['err'])
        return rec
    rec['ready'] = True
    rec['load_s'] = round(time.perf_counter() - t0, 2)
    print('   引擎加载 %.1f s' % rec['load_s'])

    try:
        ref = tts_engine.preset_voice_path()
        spk = tts_engine.speaker_embedding(eng, ref, on_log=log)
        text = tts_engine.normalize_zh_numbers(SENTENCE)
        parts = tts_engine.split_long_text(text)
        print('   切分：%d 段' % len(parts))
        chunks = []
        t1 = time.perf_counter()
        for p in parts:
            for wav_chunk, sr in tts_engine.stream(
                    eng, p, language='Chinese', speaker_embed=spk,
                    cancel_event=threading.Event()):
                chunks.append(np.asarray(wav_chunk, dtype=np.float32).reshape(-1))
        rec['synth_s'] = round(time.perf_counter() - t1, 2)
        wav = np.concatenate(chunks) if len(chunks) > 1 else (
            chunks[0] if chunks else np.zeros(0, dtype=np.float32))
        n = int(wav.size)
        rec['samples'] = n
        rec['seconds'] = round(n / float(SR), 3)
        rec['frames'] = round(n / float(FRAME_SAMPLES), 2)
        rec['hit_max_frames'] = (n >= FRAME_SAMPLES * MAX_FRAMES - 16)
        rec['rms'] = round(float(np.sqrt(np.mean(wav ** 2))) if n else 0.0, 6)
        rec['peak'] = round(float(np.max(np.abs(wav))) if n else 0.0, 6)
        print('   合成 %.1f s ⇒ 音频 %.2f s（%.1f 帧）RMS=%.4f peak=%.3f'
              % (rec['synth_s'], rec['seconds'], rec['frames'],
                 rec['rms'], rec['peak']))
        if rec['hit_max_frames']:
            print('   🔴 跑满 MAX_DECODER_FRAMES=%d ⇒ talker 未发 EOS（失控）'
                  % MAX_FRAMES)
        # 落 wav 供人工抽听
        if n:
            import wave
            with wave.open(out_wav, 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                pcm = (np.clip(wav, -1.0, 1.0) * 32767).astype('<i2')
                w.writeframes(pcm.tobytes())
            print('   wav 已落盘：%s' % out_wav)
    except Exception as e:
        import traceback
        rec['err'] = '%s: %s' % (type(e).__name__, e)
        print('   !! 合成失败：%s' % rec['err'])
        print(traceback.format_exc())
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--no-lock', action='store_true')
    args = ap.parse_args()

    sys.path.insert(0, APP_DIR)

    def _go():
        print('被测 App 目录:', APP_DIR)
        print('设备=%s 精度=%s' % (args.device, args.precision))
        print('合成句:', SENTENCE)
        print()
        tag = '%s_%s' % (args.device.replace('.', ''), args.precision)
        wav_path = os.path.join(HERE, 'app040_synth_%s.wav' % tag)
        rec = run_one(args.device, args.precision, wav_path)
        res = {'sentence': SENTENCE, 'result': rec}
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print()
        print('=' * 60)
        ok = rec['ready'] and rec['samples'] > 0 and not rec['hit_max_frames']
        print('合成判定：', 'PASS' if ok else 'FAIL')
        print('=' * 60)
        print('证据已落盘:', OUT)
        return 0 if ok else 1

    if args.no_lock:
        return _go()
    sys.path.insert(0, r"C:\Users\Trekker-PTL\confucius4-openvino")
    from machine_lock_app import LockHeld
    with LockHeld(module='app', timeout=1800, poll=20.0, verbose=True) as lk:
        print('[lock] 已持锁：%r' % (lk.payload,), flush=True)
        return _go()


if __name__ == '__main__':
    sys.exit(main())
