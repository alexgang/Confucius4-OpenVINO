"""transcribe_stream.py — C-013 #7 + C-014 部署入口

Confucius4-R2T2 流式 ASR 推理（OpenVINO INT8 with-past, Intel GPU.0）。

默认配置（按 C-013 + C-014 决定）：
  - 模型:     models/ov-int8-past
  - 设备:     GPU.0（Intel iGPU；启动时断言 FULL_DEVICE_NAME 含 "Intel"）
  - chunk:    640 ms
  - 量化:     INT8（57 ReadValue/Assign, stateful）
  - cache:    ./ov_cache（避免每次启动重新编译）
  - 分段:     rolling 30s（默认开；按 C-014 解决长音频 encoder shape / RTF 漂移）

用法：
  .venv/Scripts/python.exe transcribe_stream.py [path/to.wav]
  .venv/Scripts/python.exe transcribe_stream.py --chunk-ms 320 --max-new-tokens 32 path/to.wav
  .venv/Scripts/python.exe transcribe_stream.py --no-seg path/to.wav  # 单段（短音频）
"""
import os, sys, time, argparse
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import openvino as ov
import soundfile as sf

# 让 backends 走相对导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backends import OVBackend, SAMPLE_RATE
from seg_stream import SegmentedStreamer
from streaming_asr import streaming_transcribe, finish_streaming_transcribe


DEFAULT_MODEL = "models/ov-int8-past"
DEFAULT_DEVICE = "GPU.0"
DEFAULT_CHUNK_MS = 640
DEFAULT_UNFIXED_CHUNK_NUM = 2
DEFAULT_UNFIXED_TOKEN_NUM = 5
DEFAULT_MAX_NEW_TOKENS = 32
# C-014：默认开 rolling 分段，避免长音频 encoder shape 限制（≈120s）+ RTF 漂移
DEFAULT_SEG_STRATEGY = "rolling"
DEFAULT_MAX_SEGMENT_SEC = 30.0


def assert_intel_device(device: str):
    """C-002：启动时断言 FULL_DEVICE_NAME 含 'Intel'。"""
    full = ov.Core().get_property(device, "FULL_DEVICE_NAME")
    assert "Intel" in full, (
        f"device {device} 不是 Intel：FULL_DEVICE_NAME={full!r}。"
        "按 C-002 必须用 Intel iGPU（GPU.0），不要用 NVIDIA。"
    )
    return full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('wav', nargs='?', default='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
    ap.add_argument('--model-dir', default=DEFAULT_MODEL)
    ap.add_argument('--device', default=DEFAULT_DEVICE)
    ap.add_argument('--chunk-ms', type=float, default=DEFAULT_CHUNK_MS)
    ap.add_argument('--unfixed-chunk-num', type=int, default=DEFAULT_UNFIXED_CHUNK_NUM)
    ap.add_argument('--unfixed-token-num', type=int, default=DEFAULT_UNFIXED_TOKEN_NUM)
    ap.add_argument('--max-new-tokens', type=int, default=DEFAULT_MAX_NEW_TOKENS)
    ap.add_argument('--cache-dir', default='./ov_cache')
    ap.add_argument('--no-warmup', action='store_true',
                    help='跳过预热 pass（默认会先跑一遍不计时以避开 kernel 编译）')
    ap.add_argument('--strategy', default=DEFAULT_SEG_STRATEGY,
                    choices=['rolling', 'vad', 'vad_roll', 'off'],
                    help=f'C-014 分段策略（默认 {DEFAULT_SEG_STRATEGY}）')
    ap.add_argument('--max-segment-sec', type=float, default=DEFAULT_MAX_SEGMENT_SEC,
                    help=f'C-014 每段最长秒数（默认 {DEFAULT_MAX_SEGMENT_SEC}）')
    ap.add_argument('--no-seg', action='store_true',
                    help='关闭分段（短音频 < 30s 可用；长音频会撞 C-014 报告的 encoder shape 限制）')
    ap.add_argument('--out-log', default='reports/transcribe_stream.log')
    args = ap.parse_args()

    strategy = 'off' if args.no_seg else args.strategy

    print(f'[transcribe] device check: {args.device}', flush=True)
    full = assert_intel_device(args.device)
    print(f'[transcribe] FULL_DEVICE_NAME = {full!r} (Intel ✅)', flush=True)

    print(f'[transcribe] loading OVBackend ({args.model_dir} on {args.device}) ...', flush=True)
    t0 = time.perf_counter()
    backend = OVBackend(
        model_dir=args.model_dir, device=args.device, cache_dir=args.cache_dir,
    )
    print(f'[transcribe] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    audio, sr = sf.read(args.wav)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE, f"sample rate {sr} != {SAMPLE_RATE}"
    audio_dur = len(audio) / sr
    print(f'[transcribe] audio: {len(audio)} samples, {audio_dur:.2f}s', flush=True)
    print(f'[transcribe] strategy: {strategy}, max_segment_sec: {args.max_segment_sec}', flush=True)

    chunk_size_sec = args.chunk_ms / 1000

    # 预热：先完整跑一遍不计时（用前 10s 短样本）
    if not args.no_warmup:
        print('[transcribe] WARMUP pass on first 10s ...', flush=True)
        warmup_audio = audio[:min(int(10 * sr), len(audio))]
        warm_streamer = SegmentedStreamer(
            backend, strategy='off',
            unfixed_chunk_num=args.unfixed_chunk_num,
            unfixed_token_num=args.unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
            max_new_tokens=args.max_new_tokens,
        )
        warm_streamer.run(warmup_audio)
        print(f'[transcribe] warmup done', flush=True)

    # 正式（C-014：默认分段）
    wall_start = time.perf_counter()
    if strategy == 'off':
        # 旧路径：单段不分（短音频 < 30s）
        state = backend.init_streaming_state(
            unfixed_chunk_num=args.unfixed_chunk_num,
            unfixed_token_num=args.unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
        )
        feed_chunk = int(SAMPLE_RATE * 0.04)
        feed_pos = 0
        chunk_idx = 0
        rows = []
        while feed_pos < len(audio):
            end = min(feed_pos + feed_chunk, len(audio))
            chunk_audio = audio[feed_pos:end]
            feed_pos = end
            text, fixed = streaming_transcribe(
                backend, chunk_audio, state,
                max_new_tokens=args.max_new_tokens, rollback_punctuation=False,
            )
            if state.chunk_id > chunk_idx:
                chunk_idx = state.chunk_id
                t_now = time.perf_counter() - wall_start
                audio_so_far = len(state.audio_accum) / SAMPLE_RATE
                print(f'[chunk {chunk_idx:2d}] t={t_now:6.2f}s audio={audio_so_far:.2f}s '
                      f'text={text!r}', flush=True)
                rows.append((chunk_idx, t_now, audio_so_far, text, fixed))
        final = finish_streaming_transcribe(backend, state, max_new_tokens=max(64, args.max_new_tokens))
        n_chunks = chunk_idx
        seg_results = []
    else:
        # C-014：新路径，分段
        streamer = SegmentedStreamer(
            backend, strategy=strategy,
            max_segment_sec=args.max_segment_sec,
            unfixed_chunk_num=args.unfixed_chunk_num,
            unfixed_token_num=args.unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
            max_new_tokens=args.max_new_tokens,
        )
        full_text, seg_results = streamer.run(audio)
        n_chunks = sum(s['n_chunks'] for s in seg_results)
        # 行级打印（每段打摘要）
        for s in seg_results:
            print(f'[seg {s["seg_idx"]:3d}] start={s["start_s"]:7.2f}s end={s["end_s"]:7.2f}s '
                  f'chunks={s["n_chunks"]:3d} wall={s["wall_s"]:6.2f}s RTF={s["rtf"]:.3f} '
                  f'text={s["text"]!r}', flush=True)
        final = full_text
        rows = []

    wall = time.perf_counter() - wall_start
    rtf = wall / audio_dur

    print()
    print(f'[transcribe] FINAL = {final!r}', flush=True)
    if strategy == 'off':
        print(f'[transcribe] {n_chunks} chunks + final_flush, wall={wall:.2f}s, '
              f'audio={audio_dur:.2f}s, RTF={rtf:.3f}', flush=True)
    else:
        print(f'[transcribe] strategy={strategy} max_segment_sec={args.max_segment_sec} '
              f'segments={len(seg_results)} chunks={n_chunks}, wall={wall:.2f}s, '
              f'audio={audio_dur:.2f}s, RTF={rtf:.3f}', flush=True)

    # 写日志
    os.makedirs(os.path.dirname(args.out_log), exist_ok=True)
    with open(args.out_log, 'w', encoding='utf-8') as f:
        f.write(f"# transcribe_stream.py INT8 ({args.model_dir} on {args.device})\n")
        f.write(f"# chunk_ms={args.chunk_ms} unfixed_chunk_num={args.unfixed_chunk_num} "
                f"unfixed_token_num={args.unfixed_token_num} max_new_tokens={args.max_new_tokens}\n")
        f.write(f"# strategy={strategy} max_segment_sec={args.max_segment_sec}\n")
        f.write(f"# audio_dur={audio_dur:.2f}s wall={wall:.2f}s RTF={rtf:.3f}\n\n")
        if strategy == 'off':
            for cid, t, aud, text, fixed in rows:
                f.write(f"chunk {cid:2d}  t={t:6.2f}s  audio={aud:.2f}s  text={text!r}\n")
        else:
            for s in seg_results:
                f.write(f"seg {s['seg_idx']:3d} start={s['start_s']:7.2f}s end={s['end_s']:7.2f}s "
                        f"chunks={s['n_chunks']:3d} wall={s['wall_s']:6.2f}s RTF={s['rtf']:.3f} "
                        f"text={s['text']!r}\n")
        f.write(f"\nFINAL: {final!r}\n")
    print(f'[transcribe] log → {args.out_log}', flush=True)


if __name__ == '__main__':
    main()
