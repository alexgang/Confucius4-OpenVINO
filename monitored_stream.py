"""monitored_stream.py — C-014 #1：带监控的流式（每 chunk 记录 RSS/耗时/prefill）

用法：
  .venv/Scripts/python.exe monitored_stream.py --wav reports/test_long_30min.wav --max-seconds 600

设熔断：单 chunk > 20s，进程 RSS > 14GB，可用内存 < 4GB 自动停。
"""
import os, sys, time, csv, json, gc, argparse
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf
import psutil

sys.path.insert(0, '.')
from backends import OVBackend, SAMPLE_RATE
from streaming_asr import streaming_transcribe, finish_streaming_transcribe

# 熔断
MAX_CHUNK_SEC = 20.0
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
    ap.add_argument('--max-new-tokens', type=int, default=32)
    ap.add_argument('--max-seconds', type=float, default=600.0,
                    help='最多跑多少秒音频（避免一次性跑 30min）')
    ap.add_argument('--feed-chunk-ms', type=float, default=40)
    ap.add_argument('--out-csv', default='reports/oom_repro.csv')
    ap.add_argument('--out-log', default='reports/oom_repro.log')
    ap.add_argument('--no-warmup', action='store_true')
    args = ap.parse_args()

    audio, sr = sf.read(args.wav)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE
    audio_dur = len(audio) / sr
    max_samples = int(args.max_seconds * sr)
    audio = audio[:max_samples]
    print(f'[mon] audio: {len(audio)/sr:.2f}s (max {args.max_seconds}s)', flush=True)

    print(f'[mon] loading OVBackend ({args.model_dir} on {args.device}) ...', flush=True)
    t0 = time.perf_counter()
    b = OVBackend(model_dir=args.model_dir, device=args.device)
    print(f'[mon] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    if not args.no_warmup:
        # 用前 10s 做 warmup
        wstate = b.init_streaming_state(
            unfixed_chunk_num=2, unfixed_token_num=5, chunk_size_sec=args.chunk_ms/1000,
        )
        feed_chunk = int(SAMPLE_RATE * 0.04)
        warmup_audio = audio[:int(10*sr)]
        feed_pos = 0
        while feed_pos < len(warmup_audio):
            end = min(feed_pos + feed_chunk, len(warmup_audio))
            streaming_transcribe(b, warmup_audio[feed_pos:end], wstate,
                                 max_new_tokens=args.max_new_tokens, rollback_punctuation=False)
            feed_pos = end
        finish_streaming_transcribe(b, wstate, max_new_tokens=64)
        print(f'[mon] warmup done', flush=True)

    state = b.init_streaming_state(
        unfixed_chunk_num=2, unfixed_token_num=5, chunk_size_sec=args.chunk_ms/1000,
    )
    feed_chunk = int(SAMPLE_RATE * args.feed_chunk_ms / 1000)
    feed_pos = 0
    wall_start = time.perf_counter()
    rows = []
    stop_reason = None
    error_msg = None

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    try:
        while feed_pos < len(audio):
            end = min(feed_pos + feed_chunk, len(audio))
            chunk_audio = audio[feed_pos:end]
            feed_pos = end

            t_chunk_start = time.perf_counter()
            text, fixed = streaming_transcribe(
                b, chunk_audio, state,
                max_new_tokens=args.max_new_tokens, rollback_punctuation=False,
            )
            chunk_wall = time.perf_counter() - t_chunk_start

            if state.chunk_id > len(rows):
                rss, avail = get_mem()
                row = {
                    'chunk_id': state.chunk_id,
                    'audio_so_far_s': len(state.audio_accum)/SAMPLE_RATE,
                    'n_audio_tokens': int(state.audio_accum.shape[0] / 160 * 12.5) // 13 * 13 + 13,
                    'chunk_wall_s': chunk_wall,
                    'rss_gb': rss,
                    'avail_gb': avail,
                    'text': text,
                }
                # 真实 N_audio 用 ehs.shape[1]，但 streaming_transcribe 不返回这个。粗估：
                # audio_tower 公式：n_real_mel = 1 + audio_accum_samples/160
                # 每次 640ms 步进，新增 100 mel 帧，对应 13 audio token
                n_real = 1 + len(state.audio_accum) // 160
                # 模拟 _get_feat_extract_output_lengths
                a, b_rem = n_real % 100, n_real // 100
                f = (a - 1) // 2 + 1 if a > 0 else 0
                f2 = ((f - 1) // 2 + 1 - 1) // 2 + 1 if f > 0 else 0
                row['n_audio_est'] = f2 + b_rem * 13
                row['prefill_est'] = 17 + row['n_audio_est']  # ids_left + audio_pad*N + ids_right 约 17+N
                rows.append(row)
                print(f'[mon] chunk {row["chunk_id"]:4d} audio={row["audio_so_far_s"]:7.1f}s '
                      f'n_audio≈{row["n_audio_est"]:5d} chunk_wall={chunk_wall:5.2f}s '
                      f'RSS={rss:5.2f}GB avail={avail:5.2f}GB text={text[:30]!r}', flush=True)

                # 熔断
                if chunk_wall > MAX_CHUNK_SEC:
                    stop_reason = f'chunk_wall>{MAX_CHUNK_SEC}s at chunk {row["chunk_id"]}'
                    break
                if rss > MAX_RSS_GB:
                    stop_reason = f'RSS>{MAX_RSS_GB}GB at chunk {row["chunk_id"]}'
                    break
                if avail < MIN_AVAIL_GB:
                    stop_reason = f'avail_mem<{MIN_AVAIL_GB}GB at chunk {row["chunk_id"]}'
                    break
    except Exception as e:
        import traceback
        error_msg = f'{type(e).__name__}: {e}'
        rss, avail = get_mem()
        # 用已知的 state 信息记录出错位置
        try:
            audio_at_err = len(state.audio_accum) / SAMPLE_RATE
            chunk_at_err = state.chunk_id
        except Exception:
            audio_at_err = 0.0
            chunk_at_err = 0
        print(f'\n[mon] CRASH at chunk≈{chunk_at_err} audio≈{audio_at_err:.1f}s '
              f'RSS={rss:.2f}GB avail={avail:.2f}GB', flush=True)
        print(f'[mon] ERROR: {error_msg}', flush=True)
        stop_reason = f'EXCEPTION: {error_msg}'

    final = ""
    try:
        final = finish_streaming_transcribe(b, state, max_new_tokens=64)
    except Exception as e:
        print(f'[mon] finish_streaming_transcribe also failed: {e}', flush=True)
    wall = time.perf_counter() - wall_start
    print(f'\n[mon] FINAL = {final[:50]!r}...', flush=True)
    print(f'[mon] wall={wall:.2f}s audio={len(audio)/sr:.2f}s RTF={wall/(len(audio)/sr):.3f}', flush=True)
    if stop_reason:
        print(f'[mon] STOPPED: {stop_reason}', flush=True)

    # 写日志
    with open(args.out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['chunk_id', 'audio_so_far_s', 'n_audio_est',
                                          'prefill_est', 'chunk_wall_s', 'rss_gb', 'avail_gb', 'text'],
                            extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(args.out_log, 'w', encoding='utf-8') as f:
        f.write(f"# OOM repro (no segmentation) — {args.model_dir} on {args.device}\n")
        f.write(f"# chunk_ms={args.chunk_ms} audio_dur={len(audio)/sr:.2f}s "
                f"wall={wall:.2f}s RTF={wall/(len(audio)/sr):.3f}\n")
        f.write(f"# stop_reason: {stop_reason or 'completed'}\n")
        f.write(f"# circuit_breaker: chunk_wall>{MAX_CHUNK_SEC}s OR RSS>{MAX_RSS_GB}GB OR avail<{MIN_AVAIL_GB}GB\n\n")
        for r in rows:
            f.write(f"chunk {r['chunk_id']:4d} audio={r['audio_so_far_s']:7.1f}s "
                    f"n_audio≈{r['n_audio_est']:5d} prefill≈{r['prefill_est']:5d} "
                    f"wall={r['chunk_wall_s']:5.2f}s RSS={r['rss_gb']:5.2f}GB "
                    f"avail={r['avail_gb']:5.2f}GB text={r['text']!r}\n")
        f.write(f"\nFINAL: {final!r}\n")
    print(f'[mon] log → {args.out_log}', flush=True)


if __name__ == '__main__':
    main()
