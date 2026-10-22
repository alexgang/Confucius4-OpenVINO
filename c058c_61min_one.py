"""c058c_61min_one.py — C-058④⑤: 单配置 61 分钟验收（子进程）

reviewer 要求（CORRECTIONS.md ④）：
  「请**独占 GPU**（不得与其它任务并发，C-053 那次的 RTF 作废就是并发造成的）
    跑 61 分钟」

本脚本是 worker：一次只跑一个 (encoder, decoder) 组合，走完就退出，
由 c058c_61min_batch.py 串行调度，保证任意时刻只有一个 OV 任务占 GPU。

用法：python c058c_61min_one.py <encoder_dir> <decoder_dir> <tag> [out_dir]
"""
import os
import sys
import re
import json
import time
from collections import Counter

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer
from c058q_wordcount import count_words, save_transcript

AUDIO = 'test_audio/<redacted>.wav'

# C-061#3：warmup 覆盖多种输入长度，避免起始段吃到冷启动。
# ⚠️ 不能超过 MAX_FRAMES=2400 mel 帧（≈24 s），否则 `encode_audio` 会 assert。
# 所以取 5 / 12 / 18 s —— 覆盖从短段到接近 VAD 段上限（20 s）的各种 chunk 数与 KV 长度。
WARMUP_SWEEP_SEC = [5, 12, 18]


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    return [w for w in re.sub(r'\s+', ' ', s).strip().split() if w]


def ngram_repeat(ws, n=4):
    c = Counter()
    for i in range(len(ws) - n + 1):
        c[tuple(ws[i:i + n])] += 1
    return sum(v - 1 for v in c.values() if v > 1)


def main():
    enc_dir, dec_dir, tag = sys.argv[1], sys.argv[2], sys.argv[3]
    out_dir = sys.argv[4] if len(sys.argv) > 4 else 'reports/c058_61min'
    os.makedirs(out_dir, exist_ok=True)

    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    dur = len(audio) / sr
    print(f'[{tag}] audio {dur:.1f}s ({dur/60:.2f} min)', flush=True)
    print(f'[{tag}] enc={enc_dir}\n[{tag}] dec={dec_dir}', flush=True)

    backend = SegmentEncoderOVBackend(encoder_dir=enc_dir, decoder_dir=dec_dir,
                                      device='GPU.0', precision='f16')
    # C-061#3：warmup 只跑 5 s 只覆盖一种 shape，起始段容易吃到冷启动。
    # 改为按多个长度扫描，覆盖从短段到接近段上限的 chunk 数与 KV 长度。
    print(f'[{tag}] warmup sweep {WARMUP_SWEEP_SEC}s ...', flush=True)
    for _s in WARMUP_SWEEP_SEC:
        SegmentedStreamer(
            backend, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            enable_hallucination_reset=False).run(audio[:16000 * _s])

    print(f'[{tag}] 61-min 全量开始 ...', flush=True)
    streamer = SegmentedStreamer(
        backend, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0

    # C-061#5：必须**按段**计词。`words(text)` 对拼接后的整体文本分词，
    # 段间无分隔符时会粘连（这正是 c058k 少算 206 词的原因）。
    ws = words(text)
    n_words_segwise = count_words(segs)
    rtfs = sorted(s['rtf'] for s in segs if s.get('rtf', 0) > 0)

    def pct(p):
        return rtfs[min(int(len(rtfs) * p), len(rtfs) - 1)] if rtfs else 0

    # 逐段 RTF 分布（用于判断尾延迟是离群还是系统性）
    seg_rtfs = [{'label': i, 'start': round(s['start_s'], 1),
                 'end': round(s['end_s'], 1), 'rtf': round(s.get('rtf', 0), 3),
                 'n_chunks': s.get('n_chunks', 0)}
                for i, s in enumerate(segs)]

    tp = os.path.join(out_dir, f'transcript_{tag}.txt')
    save_transcript(segs, tp)      # C-061#5：统一格式的转写落盘

    result = {
        'tag': tag, 'encoder_dir': enc_dir, 'decoder_dir': dec_dir,
        'audio_sec': round(dur, 1),
        'wall_s': round(wall, 1), 'overall_rtf': round(wall / dur, 3),
        # C-061#5：total_words 用**按段**计词（正式口径）；
        # 拼接整体分词的结果留作对照，便于发现段间粘连。
        'n_segs': len(segs), 'total_words': n_words_segwise,
        'total_words_joined': len(ws),
        'n3_repeat': ngram_repeat(ws, 3), 'n4_repeat': ngram_repeat(ws, 4),
        'seg_rtf_p50': round(pct(0.50), 3),
        'seg_rtf_p95': round(pct(0.95), 3),
        'seg_rtf_p99': round(pct(0.99), 3),
        'seg_rtf_max': round(rtfs[-1], 3) if rtfs else 0,
        'enc_ir_mib': round(os.path.getsize(
            os.path.join(enc_dir, 'openvino_encoder_model.bin')) / 1024 ** 2, 1),
        'dec_ir_mib': round(os.path.getsize(
            os.path.join(dec_dir, 'openvino_decoder_model.bin')) / 1024 ** 2, 1),
        'transcript': tp, 'seg_rtfs': seg_rtfs,
    }
    result['ir_total_mib'] = round(result['enc_ir_mib'] + result['dec_ir_mib'], 1)
    # 尾延迟：> P95 的段数占比，用于判断是系统性还是单点离群
    p95 = result['seg_rtf_p95']
    tail = [s for s in seg_rtfs if s['rtf'] > p95]
    result['n_above_p95'] = len(tail)
    result['above_p95_segs'] = [{'start': s['start'], 'rtf': s['rtf']}
                                for s in tail[:10]]

    with open(os.path.join(out_dir, f'summary_{tag}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\n[{tag}] DONE  RTF={result["overall_rtf"]} wall={result["wall_s"]}s '
          f'segs={result["n_segs"]} words={result["total_words"]} '
          f'n4={result["n4_repeat"]} P50={result["seg_rtf_p50"]} '
          f'P95={result["seg_rtf_p95"]} max={result["seg_rtf_max"]} '
          f'>P95段数={result["n_above_p95"]}', flush=True)
    print(f'[{tag}] saved -> {out_dir}/summary_{tag}.json', flush=True)


if __name__ == '__main__':
    main()
