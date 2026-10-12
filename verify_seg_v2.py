"""verify_seg_v2.py — C-014 #3 / C-016 验收：61 分钟英文录音 + VAD 切句

跑 `test_audio/<redacted>.wav`（61.19 min，16 kHz mono），用 VAD 切句
（min=12s, max=20s），交付：
  - reports/spe_61min_transcript.txt:  每段一行，格式 `[起始秒-结束秒] 文本`
  - reports/spe_61min_segments.json: 每段 start/end/text/chunks/wall/rtf

监控全程 RSS、瞬时 RTF P50/P95/最大。
"""
import os, sys, time, json, csv, argparse
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf
import psutil

sys.path.insert(0, '.')
from backends import OVBackend, SAMPLE_RATE
from seg_stream import SegmentedStreamer

MAX_RSS_GB = 14.0
MIN_AVAIL_GB = 4.0


def get_mem():
    p = psutil.Process()
    rss = p.memory_info().rss / 1024**3
    avail = psutil.virtual_memory().available / 1024**3
    return rss, avail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wav', default='test_audio/<redacted>.wav')
    ap.add_argument('--model-dir', default='models/ov-int8-past')
    ap.add_argument('--device', default='GPU.0')
    ap.add_argument('--chunk-ms', type=float, default=640)
    ap.add_argument('--strategy', default='vad')
    ap.add_argument('--min-segment-sec', type=float, default=12.0)
    ap.add_argument('--max-segment-sec', type=float, default=20.0)
    ap.add_argument('--max-new-tokens', type=int, default=32)
    ap.add_argument('--no-warmup', action='store_true')
    ap.add_argument('--out-prefix', default='reports/spe_61min')
    args = ap.parse_args()

    print(f'[v2] wav: {args.wav}', flush=True)
    audio, sr = sf.read(args.wav)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE, f"sample rate {sr} != {SAMPLE_RATE}"
    audio_dur = len(audio) / sr
    print(f'[v2] audio_dur={audio_dur:.2f}s samples={len(audio)}', flush=True)

    print(f'[v2] loading OVBackend ({args.model_dir} on {args.device}) ...', flush=True)
    t0 = time.perf_counter()
    b = OVBackend(model_dir=args.model_dir, device=args.device)
    print(f'[v2] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    # 预热：跑 15s 短样本
    if not args.no_warmup:
        print('[v2] WARMUP pass on first 15s ...', flush=True)
        streamer_w = SegmentedStreamer(
            b, strategy='off',
            chunk_size_sec=args.chunk_ms/1000,
            max_new_tokens=args.max_new_tokens,
        )
        streamer_w.run(audio[:int(15*sr)])
        print('[v2] warmup done', flush=True)

    rss0, avail0 = get_mem()
    print(f'[v2] pre-run: RSS={rss0:.2f}GB avail={avail0:.2f}GB', flush=True)

    # 计划段
    streamer = SegmentedStreamer(
        b, strategy=args.strategy,
        min_segment_sec=args.min_segment_sec,
        max_segment_sec=args.max_segment_sec,
        chunk_size_sec=args.chunk_ms/1000,
        max_new_tokens=args.max_new_tokens,
    )
    segs = streamer._plan_segments(audio)
    print(f'[v2] planned {len(segs)} segments (strategy={args.strategy}, '
          f'min={args.min_segment_sec}s, max={args.max_segment_sec}s)', flush=True)
    if segs:
        durs = [(e - s) / SAMPLE_RATE for s, e in segs]
        print(f'[v2] segment dur: min={min(durs):.2f}s max={max(durs):.2f}s '
              f'mean={sum(durs)/len(durs):.2f}s', flush=True)

    wall_start = time.perf_counter()
    full_text, seg_results = streamer.run(audio, progress=True)
    wall = time.perf_counter() - wall_start
    rss1, avail1 = get_mem()
    peak_rss = rss1

    rtf = wall / audio_dur
    n_segs = len(seg_results)
    n_chunks = sum(s['n_chunks'] for s in seg_results)
    seg_rtfs = [s['rtf'] for s in seg_results]
    p50 = float(np.percentile(seg_rtfs, 50)) if seg_rtfs else 0.0
    p95 = float(np.percentile(seg_rtfs, 95)) if seg_rtfs else 0.0
    rtf_max = max(seg_rtfs) if seg_rtfs else 0.0

    print(f'\n[v2] === RESULT ===', flush=True)
    print(f'[v2] audio_dur={audio_dur:.2f}s wall={wall:.2f}s RTF={rtf:.3f}', flush=True)
    print(f'[v2] segments={n_segs} chunks={n_chunks}', flush=True)
    print(f'[v2] seg RTF: P50={p50:.3f} P95={p95:.3f} max={rtf_max:.3f}', flush=True)
    print(f'[v2] RSS: {rss0:.2f}GB → {rss1:.2f}GB (peak {peak_rss:.2f}GB) avail={avail1:.2f}GB', flush=True)
    print(f'[v2] full_text chars: {len(full_text)}', flush=True)

    # 写 transcript
    os.makedirs(os.path.dirname(args.out_prefix), exist_ok=True)
    transcript_path = args.out_prefix + '_transcript.txt'
    with open(transcript_path, 'w', encoding='utf-8') as f:
        for s in seg_results:
            f.write(f"[{s['start_s']:.1f}-{s['end_s']:.1f}] {s['text']}\n")
    print(f'[v2] transcript → {transcript_path}', flush=True)

    # 写 segments.json
    segments_path = args.out_prefix + '_segments.json'
    with open(segments_path, 'w', encoding='utf-8') as f:
        json.dump({
            'audio_file': args.wav,
            'audio_dur_s': audio_dur,
            'wall_s': wall,
            'rtf': rtf,
            'peak_rss_gb': peak_rss,
            'n_segs': n_segs,
            'n_chunks': n_chunks,
            'rtf_p50': p50,
            'rtf_p95': p95,
            'rtf_max': rtf_max,
            'strategy': args.strategy,
            'min_segment_sec': args.min_segment_sec,
            'max_segment_sec': args.max_segment_sec,
            'segments': seg_results,
        }, f, ensure_ascii=False, indent=2)
    print(f'[v2] segments.json → {segments_path}', flush=True)


if __name__ == '__main__':
    main()
