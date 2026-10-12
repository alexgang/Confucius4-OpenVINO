"""verify_seg.py — C-014 #3：分段流式验证

跑 30 min 音频（reports/test_long_30min.wav），用 rolling 30s 分段（`seg_stream.py`），
对每段：
  - 起新 ASRStreamingState
  - 跑 streaming_transcribe → finish_streaming_transcribe
  - 记录 n_chunks、wall、rtf、text

全程监控：
  - RSS peak / avail min
  - 总 RTF
  - 段间 fixed_text 拼起来 = 全文
  - 段间是否有 cut boundaries 丢字（每段尾是 LSP 锁定点，拼起来应与不分段基本一致）
"""
import os, sys, time, csv, json, argparse
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
    ap.add_argument('--wav', default='reports/test_long_30min.wav')
    ap.add_argument('--model-dir', default='models/ov-int8-past')
    ap.add_argument('--device', default='GPU.0')
    ap.add_argument('--chunk-ms', type=float, default=640)
    ap.add_argument('--strategy', default='rolling',
                    choices=['rolling', 'vad', 'vad_roll', 'off'])
    ap.add_argument('--max-segment-sec', type=float, default=30.0)
    ap.add_argument('--max-new-tokens', type=int, default=32)
    ap.add_argument('--out-log', default='reports/seg_verify.log')
    ap.add_argument('--out-csv', default='reports/seg_verify.csv')
    ap.add_argument('--no-warmup', action='store_true')
    args = ap.parse_args()

    print(f'[seg] audio: {args.wav}', flush=True)
    audio, sr = sf.read(args.wav)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE
    audio_dur = len(audio) / sr
    print(f'[seg] audio_dur={audio_dur:.2f}s samples={len(audio)}', flush=True)

    print(f'[seg] loading OVBackend ({args.model_dir} on {args.device}) ...', flush=True)
    t0 = time.perf_counter()
    b = OVBackend(model_dir=args.model_dir, device=args.device)
    print(f'[seg] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    # 预热
    if not args.no_warmup:
        print('[seg] WARMUP pass on first 10s ...', flush=True)
        streamer = SegmentedStreamer(
            b, strategy='off', max_segment_sec=args.max_segment_sec,
            chunk_size_sec=args.chunk_ms/1000,
            max_new_tokens=args.max_new_tokens,
        )
        warmup_audio = audio[:int(10*sr)]
        streamer.run(warmup_audio)
        print('[seg] warmup done', flush=True)

    rss0, avail0 = get_mem()
    print(f'[seg] pre-run: RSS={rss0:.2f}GB avail={avail0:.2f}GB', flush=True)

    streamer = SegmentedStreamer(
        b, strategy=args.strategy, max_segment_sec=args.max_segment_sec,
        chunk_size_sec=args.chunk_ms/1000,
        max_new_tokens=args.max_new_tokens,
    )

    wall_start = time.perf_counter()
    # 改写为带进度版：自己跑段循环
    segs = streamer._plan_segments(audio)
    print(f'[seg] planned {len(segs)} segments (strategy={args.strategy}, '
          f'max_segment_sec={args.max_segment_sec})', flush=True)
    seg_results = []
    full_text = ""
    peak_rss = rss0
    for idx, (s, e, kind) in enumerate(segs):
        seg_audio = audio[s:e]
        if seg_audio.shape[0] == 0:
            continue
        from seg_stream import _make_segment_state
        from streaming_asr import streaming_transcribe, finish_streaming_transcribe
        state = _make_segment_state(
            b,
            unfixed_chunk_num=2,
            unfixed_token_num=5,
            chunk_size_sec=args.chunk_ms/1000,
        )
        t0 = time.perf_counter()
        feed_chunk = int(SAMPLE_RATE * 0.04)
        feed_pos = 0
        while feed_pos < seg_audio.shape[0]:
            end = min(feed_pos + feed_chunk, seg_audio.shape[0])
            streaming_transcribe(
                b, seg_audio[feed_pos:end], state,
                max_new_tokens=args.max_new_tokens,
                rollback_punctuation=False,
            )
            feed_pos = end
        final_text = finish_streaming_transcribe(b, state, max_new_tokens=max(64, args.max_new_tokens))
        wall_seg = time.perf_counter() - t0
        rss, _ = get_mem()
        peak_rss = max(peak_rss, rss)
        seg_dur = (e - s) / SAMPLE_RATE
        seg_results.append({
            'seg_idx': idx,
            'start_s': s / SAMPLE_RATE,
            'end_s': e / SAMPLE_RATE,
            'duration_s': seg_dur,
            'n_chunks': state.chunk_id,
            'wall_s': wall_seg,
            'rtf': wall_seg / seg_dur if seg_dur > 0 else 0.0,
            'text': final_text,
        })
        full_text += final_text
        if idx % 5 == 0 or idx == len(segs) - 1:
            elapsed = time.perf_counter() - wall_start
            print(f'[seg] seg {idx:3d}/{len(segs)} start={s/SAMPLE_RATE:7.2f}s '
                  f'dur={seg_dur:6.2f}s chunks={state.chunk_id:3d} '
                  f'wall={wall_seg:6.2f}s RTF={wall_seg/seg_dur:.3f} '
                  f'RSS={rss:5.2f}GB elapsed={elapsed:6.1f}s', flush=True)
    wall = time.perf_counter() - wall_start
    rss1, avail1 = get_mem()
    rss1 = peak_rss  # 用 peak

    rtf = wall / audio_dur
    n_segs = len(seg_results)
    n_chunks = sum(s['n_chunks'] for s in seg_results)
    avg_rtf = sum(s['rtf'] for s in seg_results) / max(1, n_segs)

    print(f'\n[seg] === RESULT ===', flush=True)
    print(f'[seg] segments: {n_segs}, total chunks: {n_chunks}', flush=True)
    print(f'[seg] wall={wall:.2f}s audio={audio_dur:.2f}s RTF={rtf:.3f}', flush=True)
    print(f'[seg] avg seg RTF={avg_rtf:.3f}', flush=True)
    print(f'[seg] RSS: {rss0:.2f}GB → peak {rss1:.2f}GB (avail {avail1:.2f}GB)', flush=True)
    print(f'[seg] full_text chars: {len(full_text)}', flush=True)

    # 写日志
    os.makedirs(os.path.dirname(args.out_log), exist_ok=True)
    with open(args.out_log, 'w', encoding='utf-8') as f:
        f.write(f"# seg_stream verify — {args.model_dir} on {args.device}\n")
        f.write(f"# chunk_ms={args.chunk_ms} strategy={args.strategy} "
                f"max_segment_sec={args.max_segment_sec}\n")
        f.write(f"# audio_dur={audio_dur:.2f}s wall={wall:.2f}s RTF={rtf:.3f} "
                f"peak_RSS={rss1:.2f}GB avail={avail1:.2f}GB\n")
        f.write(f"# n_segs={n_segs} n_chunks={n_chunks} avg_seg_RTF={avg_rtf:.3f}\n\n")
        for s in seg_results:
            f.write(f"seg {s['seg_idx']:3d} start={s['start_s']:7.2f}s end={s['end_s']:7.2f}s "
                    f"dur={s['duration_s']:6.2f}s chunks={s['n_chunks']:3d} "
                    f"wall={s['wall_s']:6.2f}s RTF={s['rtf']:.3f} text={s['text']!r}\n")
        f.write(f"\nFULL_TEXT: {full_text!r}\n")
    print(f'[seg] log → {args.out_log}', flush=True)

    with open(args.out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['seg_idx', 'start_s', 'end_s', 'duration_s',
                                          'n_chunks', 'wall_s', 'rtf', 'text'])
        w.writeheader()
        for s in seg_results:
            w.writerow(s)
    print(f'[seg] csv → {args.out_csv}', flush=True)


if __name__ == '__main__':
    main()
