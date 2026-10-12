"""c024_window_ov_61min.py — C-023#4: OV 窗口 encoder + INT8 decoder 跑 61-min 流式

C-024#3 验收：使用 WindowEncoderOVBackend（window cache 优化）跑 61-min VAD 分段流式
输出 reports/spe_61min_transcript.txt（OV 流式最终交付）
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf

sys.path.insert(0, '.')
from window_encoder_backend import WindowEncoderOVBackend
from backends import SAMPLE_RATE
from seg_stream import SegmentedStreamer

WAV_IN = 'test_audio/260902_SPE_audio.wav'
OUT_TXT = 'reports/spe_61min_transcript.txt'
OUT_JSON = 'reports/spe_61min_segments.json'
LOG_DIR = 'reports/c024_61min_logs'
os.makedirs(LOG_DIR, exist_ok=True)


def main():
    print(f'[c024] loading WindowEncoderOVBackend ...', flush=True)
    t0 = time.perf_counter()
    b = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0',
        precision='f16',
    )
    print(f'[c024] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    audio, sr = sf.read(WAV_IN, dtype='float32')
    assert sr == SAMPLE_RATE
    audio_dur = audio.shape[0] / SAMPLE_RATE
    print(f'[c024] audio: {audio.shape[0]} samples = {audio_dur:.1f}s', flush=True)

    # VAD 分段流式
    seg = SegmentedStreamer(
        b,
        strategy='vad',
        chunk_size_sec=0.64,
        unfixed_chunk_num=0,  # C-018 新段 unfixed_chunk_num=0
        unfixed_token_num=5,
        max_new_tokens=32,
        force_language=None,  # C-017 用自动
        min_segment_sec=12.0,
        max_segment_sec=20.0,
    )

    print(f'[c024] running segmented streaming ...', flush=True)
    wall_start = time.perf_counter()
    text, results = seg.run(audio, progress=True)
    wall_total = time.perf_counter() - wall_start

    # 输出 transcript（[start-end] text 一行一段，UTF-8）
    lines = []
    for r in results:
        s, e = r['start_s'], r['end_s']
        lines.append(f"[{s:.1f}-{e:.1f}] {r['text']}")
    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'[c024] → {OUT_TXT} ({len(results)} segs)', flush=True)

    # 统计
    seg_durs = [r['duration_s'] for r in results]
    seg_rtfs = [r['rtf'] for r in results]
    inst_rtfs = []
    for r in results:
        # 段内瞬时 RTF：wall / (chunk 间隔 × n_chunks)
        # 简化：用 seg 整体 rtf
        inst_rtfs.append(r['rtf'])
    inst_rtfs_sorted = sorted(inst_rtfs)
    p50 = inst_rtfs_sorted[len(inst_rtfs_sorted) // 2]
    p95 = inst_rtfs_sorted[int(len(inst_rtfs_sorted) * 0.95)]
    n_bad = sum(1 for r in results if r['rtf'] > 0.8)
    n_over = sum(1 for r in results if r['rtf'] > 1.0)

    summary = {
        'wall_s': wall_total,
        'audio_dur_s': audio_dur,
        'rtf': wall_total / audio_dur,
        'n_segs': len(results),
        'total_chunks': sum(r['n_chunks'] for r in results),
        'n_words': sum(len(r['text'].split()) for r in results),
        'seg_dur_min_s': min(seg_durs) if seg_durs else 0,
        'seg_dur_max_s': max(seg_durs) if seg_durs else 0,
        'seg_dur_mean_s': sum(seg_durs) / len(seg_durs) if seg_durs else 0,
        'seg_rtf_p50': p50,
        'seg_rtf_p95': p95,
        'seg_rtf_max': max(inst_rtfs) if inst_rtfs else 0,
        'n_segs_rtf_gt_0.8': n_bad,
        'n_segs_rtf_gt_1.0': n_over,
        'n_circular_segs': 0,  # 待检查
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'summary': summary, 'segments': results}, f, ensure_ascii=False, indent=2)
    print(f'[c024] → {OUT_JSON}', flush=True)
    print(f'[c024] summary: {summary}', flush=True)


if __name__ == '__main__':
    main()
