"""transcribe_stream.py — 部署入口（C-045 起对齐验收配置）

Confucius4-r2T2 流式 ASR 推理（OpenVINO，Intel GPU.0）。

默认配置（对齐 C-039 61-min 验收配置，RTF≈0.63）：
  - encoder:  models/ov-encoder-segment-reviewer（整段全局注意力，无 window cache）
  - decoder:  models/ov-int8-past（weight-only INT8 stateful）
  - 设备:     GPU.0（Intel iGPU；启动时断言 FULL_DEVICE_NAME 含 "Intel"）
  - chunk:    640 ms
  - unfixed:  chunk_num=0 / token_num=5（C-033#1 修复后）
  - 分段:     VAD 12–20s（C-039 定版；短音频自动退化为单段）
  - cache:    ./ov_cache（避免每次启动重新编译）

历史注意（C-045）：
  - 旧默认 OVBackend + models/ov-int8-past(optimum encoder) + rolling 30s 是
    C-021 已实测全长度错误的坏 encoder IR 路径，已废弃；如确需复现旧行为用
    --backend window（WindowEncoderOVBackend + models/ov-encoder-window）。
  - decoder 可用 --decoder-dir 切换到 C-045 导出的量化变体
    （models/ov-int8-mix4-past 等，见 c045_export_variants.py）。

用法：
  .venv/Scripts/python.exe transcribe_stream.py path/to.wav
  .venv/Scripts/python.exe transcribe_stream.py path/to.wav --chunk-ms 320
  .venv/Scripts/python.exe transcribe_stream.py path/to.wav --no-seg   # 短音频单段
  .venv/Scripts/python.exe transcribe_stream.py path/to.wav --decoder-dir models/ov-int8-mix4-past
"""
import os, sys, time, argparse
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

import numpy as np
import openvino as ov
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seg_stream import SegmentedStreamer

DEFAULT_ENCODER_DIR = "models/ov-encoder-segment-reviewer"
DEFAULT_DECODER_DIR = "models/ov-int8-past"
DEFAULT_DEVICE = "GPU.0"
DEFAULT_CHUNK_MS = 640
DEFAULT_UNFIXED_CHUNK_NUM = 0
DEFAULT_UNFIXED_TOKEN_NUM = 5
DEFAULT_MAX_NEW_TOKENS = 32
# C-047: 自适应生成长度（复刻 R2T2 官方负反馈）。61-min 全量集验证
# WER 17.87% → 7.88%，RTF 0.687 → 0.639。需配合 unfixed_token_num=5。
DEFAULT_ADAPTIVE_BUDGET = True
# C-039 定版：VAD 切段 12–20s（segment encoder 上限 ≈23.9s）
DEFAULT_SEG_STRATEGY = "vad"
DEFAULT_MIN_SEGMENT_SEC = 12.0
DEFAULT_MAX_SEGMENT_SEC = 20.0


def assert_intel_device(device: str):
    """C-002：启动时断言 FULL_DEVICE_NAME 含 'Intel'。"""
    full = ov.Core().get_property(device, "FULL_DEVICE_NAME")
    assert "Intel" in full, (
        f"device {device} 不是 Intel：FULL_DEVICE_NAME={full!r}。"
        "按 C-002 必须用 Intel iGPU（GPU.0），不要用 NVIDIA。"
    )
    return full


def build_backend(args):
    if args.backend == "window":
        from window_encoder_backend import WindowEncoderOVBackend
        return WindowEncoderOVBackend(
            encoder_dir=args.encoder_dir,
            decoder_dir=args.decoder_dir,
            device=args.device,
        )
    from segment_encoder_backend import SegmentEncoderOVBackend
    return SegmentEncoderOVBackend(
        encoder_dir=args.encoder_dir,
        decoder_dir=args.decoder_dir,
        device=args.device,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('wav', nargs='?', default='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
    ap.add_argument('--backend', default='segment', choices=['segment', 'window'],
                    help='segment=整段全局注意力 encoder（默认，验收配置）；'
                         'window=旧窗口 encoder（仅复现用）')
    ap.add_argument('--encoder-dir', default=DEFAULT_ENCODER_DIR)
    ap.add_argument('--decoder-dir', default=DEFAULT_DECODER_DIR,
                    help='decoder IR 目录（可切 C-045 量化变体，如 models/ov-int8-mix4-past）')
    ap.add_argument('--device', default=DEFAULT_DEVICE)
    ap.add_argument('--chunk-ms', type=float, default=DEFAULT_CHUNK_MS)
    ap.add_argument('--unfixed-chunk-num', type=int, default=DEFAULT_UNFIXED_CHUNK_NUM)
    ap.add_argument('--unfixed-token-num', type=int, default=DEFAULT_UNFIXED_TOKEN_NUM)
    ap.add_argument('--max-new-tokens', type=int, default=DEFAULT_MAX_NEW_TOKENS)
    ap.add_argument('--no-adaptive-budget', dest='adaptive_budget',
                    action='store_false', default=DEFAULT_ADAPTIVE_BUDGET,
                    help='关闭 C-047 自适应生成长度，退回固定 max_new_tokens=32'
                         '（61-min 实测 WER 17.87%%，仅复现历史行为用）')
    ap.add_argument('--cache-dir', default='./ov_cache')
    ap.add_argument('--no-warmup', action='store_true',
                    help='跳过预热 pass（默认会先跑一遍不计时以避开 kernel 编译）')
    ap.add_argument('--strategy', default=DEFAULT_SEG_STRATEGY,
                    choices=['rolling', 'vad', 'vad_roll', 'off'],
                    help=f'分段策略（默认 {DEFAULT_SEG_STRATEGY}）')
    ap.add_argument('--min-segment-sec', type=float, default=DEFAULT_MIN_SEGMENT_SEC)
    ap.add_argument('--max-segment-sec', type=float, default=DEFAULT_MAX_SEGMENT_SEC,
                    help='每段最长秒数（默认 20；segment encoder 硬上限 ≈23.9s）')
    ap.add_argument('--no-seg', action='store_true',
                    help='关闭分段（短音频 < 24s 可用；长音频会撞 segment encoder 2400 帧上限）')
    ap.add_argument('--out-log', default='reports/transcribe_stream.log')
    args = ap.parse_args()

    strategy = 'off' if args.no_seg else args.strategy

    # C-047: 自适应预算必须配合 unfixed_token_num=5。
    # H 变体实测 k=1 + 自适应会退化到 WER 29.19%（5 段集），提前告警。
    if args.adaptive_budget and args.unfixed_token_num != 5:
        print(f'[transcribe] WARN: adaptive_budget 建议配合 unfixed_token_num=5，'
              f'当前为 {args.unfixed_token_num}，质量可能显著退化', flush=True)

    print(f'[transcribe] device check: {args.device}', flush=True)
    full = assert_intel_device(args.device)
    print(f'[transcribe] FULL_DEVICE_NAME = {full!r} (Intel ✅)', flush=True)

    print(f'[transcribe] loading {args.backend} backend '
          f'(enc={args.encoder_dir}, dec={args.decoder_dir} on {args.device}) ...', flush=True)
    t0 = time.perf_counter()
    backend = build_backend(args)
    print(f'[transcribe] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    audio, sr = sf.read(args.wav)
    audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == 16000, f"sample rate {sr} != 16000"
    audio_dur = len(audio) / sr
    print(f'[transcribe] audio: {len(audio)} samples, {audio_dur:.2f}s', flush=True)
    print(f'[transcribe] strategy: {strategy}, '
          f'segment: [{args.min_segment_sec}, {args.max_segment_sec}]s, '
          f'unfixed: chunk={args.unfixed_chunk_num} token={args.unfixed_token_num}', flush=True)

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
            adaptive_budget=args.adaptive_budget,
            enable_hallucination_reset=False,
        )
        warm_streamer.run(warmup_audio)
        print('[transcribe] warmup done', flush=True)

    # 正式跑
    wall_start = time.perf_counter()
    streamer = SegmentedStreamer(
        backend, strategy=strategy,
        min_segment_sec=args.min_segment_sec,
        max_segment_sec=args.max_segment_sec,
        unfixed_chunk_num=args.unfixed_chunk_num,
        unfixed_token_num=args.unfixed_token_num,
        chunk_size_sec=chunk_size_sec,
        max_new_tokens=args.max_new_tokens,
        adaptive_budget=args.adaptive_budget,
        enable_hallucination_reset=False,
    )
    full_text, seg_results = streamer.run(audio)
    wall = time.perf_counter() - wall_start
    rtf = wall / audio_dur
    n_chunks = sum(s['n_chunks'] for s in seg_results)

    for s in seg_results:
        print(f'[seg {s["seg_idx"]:3d}] start={s["start_s"]:7.2f}s end={s["end_s"]:7.2f}s '
              f'chunks={s["n_chunks"]:3d} wall={s["wall_s"]:6.2f}s RTF={s["rtf"]:.3f} '
              f'text={s["text"]!r}', flush=True)

    print()
    print(f'[transcribe] FINAL = {full_text!r}', flush=True)
    print(f'[transcribe] strategy={strategy} segments={len(seg_results)} '
          f'chunks={n_chunks}, wall={wall:.2f}s, audio={audio_dur:.2f}s, RTF={rtf:.3f}', flush=True)

    os.makedirs(os.path.dirname(args.out_log) or '.', exist_ok=True)
    with open(args.out_log, 'w', encoding='utf-8') as f:
        f.write(f"# transcribe_stream.py ({args.backend}: {args.encoder_dir} + {args.decoder_dir} on {args.device})\n")
        f.write(f"# chunk_ms={args.chunk_ms} unfixed_chunk_num={args.unfixed_chunk_num} "
                f"unfixed_token_num={args.unfixed_token_num} max_new_tokens={args.max_new_tokens} "
                f"adaptive_budget={args.adaptive_budget}\n")
        f.write(f"# strategy={strategy} segment=[{args.min_segment_sec}, {args.max_segment_sec}]s\n")
        f.write(f"# audio_dur={audio_dur:.2f}s wall={wall:.2f}s RTF={rtf:.3f}\n\n")
        for s in seg_results:
            f.write(f"seg {s['seg_idx']:3d} start={s['start_s']:7.2f}s end={s['end_s']:7.2f}s "
                    f"chunks={s['n_chunks']:3d} wall={s['wall_s']:6.2f}s RTF={s['rtf']:.3f} "
                    f"text={s['text']!r}\n")
        f.write(f"\nFINAL: {full_text!r}\n")
    print(f'[transcribe] log → {args.out_log}', flush=True)


if __name__ == '__main__':
    main()
