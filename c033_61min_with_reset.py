"""c033_61min_with_reset.py — C-033#5: 61-min 全长 (cache 修好 + 新 reset 语义)

Per C-033#5 步骤 3: 'spe_61min_transcript.txt' (修 bug + reset)。
C-033#4 新 reset 语义: 3-gram ≥3 OR prefix overlap ≥6 → DISCARD gen_text + KEEP prev
fixed_text + CONTINUE; 3-in-a-row → force_finish + 重开段.
输出:
- reports/spe_61min_transcript.txt
- reports/spe_61min_segments.json
- reports/c033_cache_fixed/61min_with_reset_summary.json
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf
from collections import Counter
import re

from window_encoder_backend import WindowEncoderOVBackend
from seg_stream import SegmentedStreamer


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return [w for w in s.split() if w]


def ngram_stats(text, n_list=(3, 4)):
    ws = words(text)
    out = {'words': len(ws)}
    for n in n_list:
        counts = Counter()
        for i in range(len(ws) - n + 1):
            counts[tuple(ws[i:i+n])] += 1
        total_repeat = sum(c - 1 for c in counts.values() if c > 1)
        max_count = max(counts.values()) if counts else 0
        out[f'n{n}_repeat'] = total_repeat
        out[f'n{n}_max'] = max_count
    return out


def main():
    print('[c033-61r] === 61-min 全长 (cache 修好 + 新 reset 语义) ===', flush=True)
    print(f'[c033-61r] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    audio_path = 'test_audio/260902_SPE_audio.wav'
    audio, sr = sf.read(audio_path, dtype='float32')
    assert sr == 16000
    audio_dur = len(audio) / sr
    print(f'[c033-61r] audio: {audio_dur:.1f}s ({audio_dur/60:.2f} min)', flush=True)

    # 加载 backend
    print('[c033-61r] loading backend ...', flush=True)
    backend = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )

    # 预热
    print('[c033-61r] warmup (跑 5s 音频避免首次 kernel 编译)...', flush=True)
    warm_audio = audio[:16000 * 5]
    wstreamer = SegmentedStreamer(
        backend, strategy='off', chunk_size_sec=0.64,
        unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
        enable_hallucination_reset=True,
    )
    wstreamer.run(warm_audio)
    print('[c033-61r] warmup done', flush=True)

    # 主跑 (VAD 切段 12-20s, WITH reset)
    streamer = SegmentedStreamer(
        backend, strategy='vad',
        min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64,
        unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
        enable_hallucination_reset=True,
    )
    t0 = time.perf_counter()
    full_text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0
    print(f'[c033-61r] done, wall={wall:.1f}s ({wall/audio_dur:.3f} RTF)', flush=True)

    # Stats
    stats = ngram_stats(full_text)
    n_segs = len(segs)
    n_with_resets = sum(1 for s in segs if s.get('n_resets', 0) > 0)
    total_resets = sum(s.get('n_resets', 0) for s in segs)
    seg_rtfs = [s['rtf'] for s in segs if s.get('rtf', 0) > 0]
    seg_rtfs_sorted = sorted(seg_rtfs)
    p50 = seg_rtfs_sorted[len(seg_rtfs_sorted) // 2] if seg_rtfs_sorted else 0
    p95_idx = min(int(len(seg_rtfs_sorted) * 0.95), len(seg_rtfs_sorted) - 1)
    p95 = seg_rtfs_sorted[p95_idx] if seg_rtfs_sorted else 0
    rtf_max = seg_rtfs_sorted[-1] if seg_rtfs_sorted else 0

    print()
    print('=== 61-min 全长结果 (cache 修好 + 新 reset) ===')
    print(f'wall_s:         {wall:.1f}')
    print(f'audio_dur_s:    {audio_dur:.1f}')
    print(f'overall RTF:    {wall/audio_dur:.3f}')
    print(f'n_segs:         {n_segs}')
    print(f'n_chunks (总):  {sum(s["n_chunks"] for s in segs)}')
    print(f'总词数:         {stats["words"]}')
    print(f'n3_repeat:      {stats["n3_repeat"]}')
    print(f'n4_repeat:      {stats["n4_repeat"]}')
    print(f'n_segs_with_resets: {n_with_resets}/{n_segs} ({n_with_resets/n_segs*100:.1f}%)')
    print(f'total resets (3-in-a-row finishes):   {total_resets}')
    print(f'seg RTF P50:    {p50:.3f}')
    print(f'seg RTF P95:    {p95:.3f}')
    print(f'seg RTF max:    {rtf_max:.3f}')

    # 写 transcript
    out_dir = 'reports'
    transcript_path = os.path.join(out_dir, 'spe_61min_transcript.txt')
    with open(transcript_path, 'w', encoding='utf-8') as f:
        for s in segs:
            t_start = s['start_s']
            t_end = s['end_s']
            text = s['text']
            f.write(f'[{t_start:7.1f}-{t_end:7.1f}] {text}\n')
    print(f'[c033-61r] → {transcript_path}')

    # 写 segments.json
    segs_path = os.path.join(out_dir, 'spe_61min_segments.json')
    with open(segs_path, 'w', encoding='utf-8') as f:
        json.dump(segs, f, ensure_ascii=False, indent=2)
    print(f'[c033-61r] → {segs_path}')

    # 写 summary
    summary = {
        'mode': 'cache_fixed_with_reset',
        'wall_s': wall,
        'audio_dur_s': audio_dur,
        'overall_rtf': wall / audio_dur,
        'n_segs': n_segs,
        'n_chunks_total': sum(s['n_chunks'] for s in segs),
        'total_words': stats['words'],
        'n3_repeat': stats['n3_repeat'],
        'n4_repeat': stats['n4_repeat'],
        'n_segs_with_resets': n_with_resets,
        'total_resets': total_resets,
        'seg_rtf_p50': p50,
        'seg_rtf_p95': p95,
        'seg_rtf_max': rtf_max,
    }
    summary_path = 'reports/c033_cache_fixed/61min_with_reset_summary.json'
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'[c033-61r] → {summary_path}')


if __name__ == '__main__':
    main()
