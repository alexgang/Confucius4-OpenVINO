#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-047：在 **NVIDIA CUDA（PyTorch）** 上跑 faster-qwen3-tts，量真实 TTFA / RTF。

背景（用户 2026-10-25 追问）：
  我上一轮说的「CUDA 不可用」**只针对 OpenVINO 的 CUDA plugin**（OV IR 跑 NVIDIA），
  并不是说 CUDA 本身不可用。`nvidia-smi` 一直是好的（RTX 5050 Laptop / 592.82 / sm_120）。
  ⇒ 本项目可以走**另一条完全独立的路径**：PyTorch + CUDA（faster-qwen3-tts，CUDA Graph）。
  本脚本就是拿同一句、同一个音色素材，在这条路径上量数字，用来决定「要不要把它做成
  语音输出的第三个选项」。

口径（与 App 侧 §39/§40 对齐，便于横比）：
  - 句子：与 `app040_tts_synth_only.py` 完全相同（26 字中文）；
  - 音色：`models/qwen3tts/voices/preset_A.wav`（x-vector 模式，和 App 现用的 embedding 同源）；
  - TTFA = 流式第一次拿到 chunk 的时刻（不含模型加载、不含 warmup）；
  - RTF  = 合成总耗时 / 音频时长（<1 才算「比实时快」）；
  - 合成完把 wav 落到仓库外，**不把音频写进仓库**。

用法：
  python app047_cuda_tts_probe.py --repeats 3
  python app047_cuda_tts_probe.py --model C:\\...\\snapshots\\<hash>   # 指定本地快照
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import wave

# ── 复用 App 侧同一个测试句与音色 ───────────────────────────────────────────
SENTENCE = "这是一次语音输出的自测，用来确认朗读功能可以正常工作。"
LANGUAGE = "Chinese"

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5"
DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
DEFAULT_REF = os.path.join(PKG, "models", "qwen3tts", "voices", "preset_A.wav")
OUT_DIR = r"C:\Users\Trekker-PTL\_fq3tts_out"
JSON_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'app047_cuda_tts_probe.json')


def pcm_stats(audio, sr):
    """RMS / peak / 时长。audio 是 list 或 1-D ndarray。"""
    try:
        import numpy as np
        a = np.asarray(audio, dtype='float32').reshape(-1)
        rms = float(np.sqrt((a * a).mean())) if a.size else 0.0
        peak = float(np.abs(a).max()) if a.size else 0.0
    except Exception:
        rms = peak = 0.0
    return {'n': int(len(audio)), 'sr': int(sr),
            'dur_s': round(len(audio) / float(sr), 3),
            'rms': round(rms, 4), 'peak': round(peak, 4)}


LOCK_PATH = r"C:\Users\Trekker-PTL\shared\MACHINE_LOCK"


def _lock_owner():
    """读共享机器锁的首行（不判死，只记录「跑的时候有没有别人在跑」）。"""
    try:
        with open(LOCK_PATH, 'r', encoding='utf-8', errors='replace') as f:
            head = f.readline().strip()
        return head or '(空文件)'
    except FileNotFoundError:
        return None
    except Exception as e:
        return '(读失败: %s)' % e


def save_wav(path, audio, sr):
    try:
        import numpy as np
        a = np.asarray(audio, dtype='float32').reshape(-1)
        a = np.clip(a, -1.0, 1.0)
        with wave.open(path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(sr))
            w.writeframes((a * 32767.0).astype('<i2').tobytes())
        return True
    except Exception as e:
        print('  [warn] 写 wav 失败:', e)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--ref-audio', default=DEFAULT_REF)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--chunk-size', type=int, default=8)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--dtype', default='bfloat16')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    rec = {'sentence': SENTENCE, 'language': LANGUAGE, 'text_len': len(SENTENCE),
           'model': args.model, 'ref_audio': args.ref_audio,
           'device': args.device, 'dtype': args.dtype,
           'chunk_size': args.chunk_size}

    # ── 0. 环境自检（先证 CUDA 真的能用，别把「装错了」当「方案不行」）──
    import torch
    rec['torch'] = torch.__version__
    rec['cuda_version'] = torch.version.cuda
    rec['cuda_available'] = bool(torch.cuda.is_available())

    # 🔴 计时口径：跑的时候机器上有没有别人持锁 —— 有 ⇒ timing_valid=False
    #    （铁律：计时必须持锁 + 安静窗口；无锁数据只能当「量级参考」，不能对外报）
    rec['lock_owner_at_start'] = _lock_owner()
    rec['timing_valid'] = rec['lock_owner_at_start'] is None
    if not rec['timing_valid']:
        print('[warn] 跑时机器锁被占用：%r ⇒ timing_valid=False（只作量级参考）'
              % (rec['lock_owner_at_start'],))
    if not rec['cuda_available']:
        print('!! torch.cuda.is_available() = False ⇒ 先修环境，不要下结论')
        rec['verdict'] = False
        with open(JSON_OUT, 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        return 2
    rec['gpu'] = torch.cuda.get_device_name(0)
    rec['capability'] = list(torch.cuda.get_device_capability(0))
    print('torch %s / CUDA %s / %s (sm_%d%d)'
          % (rec['torch'], rec['cuda_version'], rec['gpu'],
             rec['capability'][0], rec['capability'][1]))

    from faster_qwen3_tts import FasterQwen3TTS

    # ── 1. 加载 + CUDA Graph 预热（首次一定慢，必须与稳态分开报）──
    t0 = time.monotonic()
    model = FasterQwen3TTS.from_pretrained(
        args.model, device=args.device, dtype=args.dtype, local_files_only=True)
    rec['load_s'] = round(time.monotonic() - t0, 2)
    print('模型加载 %.2f s' % rec['load_s'])

    t0 = time.monotonic()
    model.warmup(prefill_len=100)
    rec['warmup_s'] = round(time.monotonic() - t0, 2)
    print('CUDA Graph 预热 %.2f s' % rec['warmup_s'])

    # ── 2. 稳态非流式（量 RTF）──
    runs = []
    for i in range(args.repeats):
        torch.cuda.synchronize()
        t0 = time.monotonic()
        audio_list, sr = model.generate_voice_clone(
            text=SENTENCE, language=LANGUAGE,
            ref_audio=args.ref_audio, xvec_only=True,
        )
        torch.cuda.synchronize()
        sec = time.monotonic() - t0
        audio = audio_list[0] if isinstance(audio_list, (list, tuple)) else audio_list
        st = pcm_stats(audio, sr)
        st['synth_s'] = round(sec, 3)
        st['rtf'] = round(sec / st['dur_s'], 3) if st['dur_s'] else None
        runs.append(st)
        print('  [non-stream #%d] %.3f s / 音频 %.3f s ⇒ RTF %.3f（RMS %.4f peak %.4f）'
              % (i + 1, sec, st['dur_s'], st['rtf'], st['rms'], st['peak']))
        if i == 0:
            save_wav(os.path.join(OUT_DIR, 'cuda_nostream.wav'), audio, sr)
    rec['nonstream'] = runs
    if runs:
        rec['rtf_median'] = round(statistics.median(
            [r['rtf'] for r in runs if r['rtf']]), 3)
        rec['synth_median_s'] = round(statistics.median(
            [r['synth_s'] for r in runs]), 3)
        rec['audio_dur_s'] = runs[0]['dur_s']

    # ── 3. 稳态流式（量 TTFA —— 这才是「实时朗读」的判据）──
    torch.cuda.synchronize()
    t0 = time.monotonic()
    ttfa = None
    first = None
    last = None
    n_chunk = 0
    for audio_chunk, sr, timing in model.generate_voice_clone_streaming(
            text=SENTENCE, language=LANGUAGE,
            ref_audio=args.ref_audio, xvec_only=True,
            chunk_size=args.chunk_size):
        if ttfa is None:
            ttfa = round(time.monotonic() - t0, 3)
            first = audio_chunk
        last = audio_chunk
        n_chunk += 1
    total = time.monotonic() - t0
    rec['stream'] = {'ttfa_s': ttfa, 'chunks': n_chunk,
                     'total_s': round(total, 3)}
    if first is not None:
        st1 = pcm_stats(first, sr)
        rec['stream']['first_chunk_s'] = round(st1['n'] / float(sr), 3)
        rec['stream']['sr'] = st1['sr']
        print('  [stream] TTFA %.3f s / 首块 %.3f s / 共 %d 块 / 总 %.3f s'
              % (ttfa, rec['stream']['first_chunk_s'], n_chunk, total))
        try:
            import numpy as np
            save_wav(os.path.join(OUT_DIR, 'cuda_stream.wav'),
                     np.concatenate([np.asarray(first, dtype='float32').reshape(-1),
                                     np.asarray(last, dtype='float32').reshape(-1)]),
                     sr)
        except Exception:
            pass

    # ── 4. 与 App 现网（OV/NPU）横比 ──
    rec['compare_ov_npu'] = {'first_packet_s': 6.964, 'note': 'App §39 实测（NPU·F16）'}
    ok = (runs and rec.get('rtf_median') is not None
          and rec['rtf_median'] < 1.0 and ttfa is not None)
    rec['verdict'] = bool(ok)
    rec['verdict_note'] = ('RTF %.3f < 1 且 TTFA %.3f s ⇒ 实时朗读可行'
                           % (rec['rtf_median'], ttfa or -1)) if ok else \
                          '未达到「比实时快」或流式失败 ⇒ 需再调'
    print('\n结论：%s' % ('PASS' if ok else 'FAIL'), '—', rec['verdict_note'])

    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print('结果：', JSON_OUT)
    print('音频：', OUT_DIR)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
