"""c045_two_pass.py — C-045: 两遍式第二遍（离线逐段重解）

动机 (本项目实测数据):
  - OV INT8 流式 61-min WER = 17.87% (I=1025 插入为主)
  - OV INT8 离线逐段 WER = 8.65% (reports/spe_hybrid_offline.txt)
  - CUDA 流式 7.62%
  → 同一 decoder, 离线比流式好~9pp: 流式增量解码把INT8 的 ~6% token 翻转
    放大成重复循环。离线一次成型没有这个放大效应。

本脚本 = 第二遍: 读第一遍(c045_61min.py)输出的分段 JSON, 用同一 encoder/decoder
对每段音频做单次离线 greedy 重解, 覆盖流式文本。不重跑第一遍(省~40min)。

用法:
  .venv python c045_two_pass.py --segments reports/spe_61min_segments_mix4.json --decoder models/ov-mix4-past
"""
import os, sys, time, json, argparse
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
from streaming_asr import parse_asr_output

EOS_IDS = {151643, 151645}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--segments', required=True, help='第一遍输出的 segments JSON')
    ap.add_argument('--decoder', default='models/ov-int8-past')
    ap.add_argument('--encoder', default='models/ov-encoder-segment-reviewer')
    ap.add_argument('--audio', default='test_audio/260902_SPE_audio.wav')
    ap.add_argument('--max-new-tokens', type=int, default=128)
    ap.add_argument('--tag', default=None)
    ap.add_argument('--limit', type=int, default=0, help='>0 时只跑前 N 段 (快速验证)')
    args = ap.parse_args()

    tag = args.tag or os.path.basename(args.decoder.rstrip('/'))
    print(f'[c045-2p] === 两遍式第二遍: 离线逐段重解 (decoder={args.decoder}) ===', flush=True)
    print(f'[c045-2p] segments: {args.segments}', flush=True)

    audio, sr = sf.read(args.audio, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == 16000

    with open(args.segments, 'r', encoding='utf-8') as f:
        segs = json.load(f)
    if isinstance(segs, dict):
        segs = segs.get('segments', segs.get('segs', []))
    if args.limit:
        segs = segs[:args.limit]
    print(f'[c045-2p] {len(segs)} segments', flush=True)

    backend = SegmentEncoderOVBackend(
        encoder_dir=args.encoder, decoder_dir=args.decoder,
        device='GPU.0', precision='f16',
    )

    # 预热
    print('[c045-2p] warmup (5s) ...', flush=True)
    SegmentEncoderOVBackend  # noqa
    ehs, _, _ = backend.encode_audio(audio[:16000 * 5])
    backend.greedy_decode_with_prefix(ehs, [], max_new_tokens=16)

    out = []
    t_start = time.perf_counter()
    total_audio = 0.0
    for i, s in enumerate(segs):
        st = float(s['start_s'])
        en = float(s['end_s'])
        seg_audio = audio[int(st * sr):int(en * sr)]
        if len(seg_audio) < sr * 0.2:
            continue
        t0 = time.perf_counter()
        ehs, _, N_audio = backend.encode_audio(seg_audio)
        ids = backend.greedy_decode_with_prefix(ehs, [], max_new_tokens=args.max_new_tokens)
        # 去掉尾部 EOS
        clean = [t for t in ids if t not in EOS_IDS]
        raw_text = backend.tokenizer.decode(clean, skip_special_tokens=True)
        # 离线解码时模型会输出 "language None<asr_text>" 前缀, 必须按官方语义剥离
        # (与流式路径 parse_asr_output 一致, 否则每段多 3-4 个垃圾词)
        _lang, text = parse_asr_output(raw_text)
        wall = time.perf_counter() - t0
        total_audio += len(seg_audio) / sr
        out.append({'start_s': st, 'end_s': en, 'text': text,
                    'n_tokens': len(clean), 'wall_s': round(wall, 2),
                    'rtf': round(wall / (len(seg_audio) / sr), 3),
                    'stream_text': s.get('text', '')})
        if (i + 1) % 20 == 0 or i == len(segs) - 1:
            el = time.perf_counter() - t_start
            print(f'  [{i+1}/{len(segs)}] wall={el:.0f}s offline_rtf={el/max(total_audio,1e-9):.3f} '
                  f'last="{text[:60]}"', flush=True)

    wall = time.perf_counter() - t_start
    txt_path = f'reports/spe_61min_offline_{tag}.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        for r in out:
            f.write(f'[{r["start_s"]:7.1f}-{r["end_s"]:7.1f}] {r["text"]}\n')
    json_path = f'reports/spe_61min_offline_{tag}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    summary = {
        'mode': f'c045_two_pass_offline_{tag}',
        'decoder_dir': args.decoder,
        'segments_json': args.segments,
        'n_segs': len(out),
        'audio_dur_s': total_audio,
        'wall_s': wall,
        'offline_rtf': wall / max(total_audio, 1e-9),
        'transcript': txt_path,
    }
    sum_path = f'reports/c045_2pass_{tag}/summary.json'
    os.makedirs(os.path.dirname(sum_path), exist_ok=True)
    with open(sum_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print('=== 两遍式第二遍结果 ===')
    print(f'decoder:     {args.decoder}')
    print(f'n_segs:      {len(out)}')
    print(f'audio_dur:   {total_audio:.1f}s')
    print(f'wall:        {wall:.1f}s')
    print(f'offline RTF: {wall/max(total_audio,1e-9):.3f}')
    print(f'→ {txt_path}')
    print(f'→ {sum_path}')


if __name__ == '__main__':
    main()