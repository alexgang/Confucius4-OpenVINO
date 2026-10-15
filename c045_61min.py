"""c045_61min.py — C-045: 61-min 全长验证（可指定 decoder）

与 c039_61min.py 相同的验收配置 (segment encoder + VAD 12-20s + no reset),
只把 decoder 换成参数, transcript/summary 按 decoder 名字区分。

用法:
  .venv python c045_61min.py --decoder models/ov-mix4-past
  .venv python c045_61min.py --decoder models/ov-int8-past --tag baseline
"""
import os, sys, time, json, re, argparse
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
from collections import Counter

from segment_encoder_backend import SegmentEncoderOVBackend
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
            counts[tuple(ws[i:i + n])] += 1
        out[f'n{n}_repeat'] = sum(c - 1 for c in counts.values() if c > 1)
        out[f'n{n}_max'] = max(counts.values()) if counts else 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--decoder', default='models/ov-int8-past')
    ap.add_argument('--encoder', default='models/ov-encoder-segment-reviewer')
    ap.add_argument('--tag', default=None, help='输出文件名 tag (默认取 decoder 目录名)')
    ap.add_argument('--audio', default='test_audio/260902_SPE_audio.wav')
    ap.add_argument('--no-warmup', action='store_true')
    args = ap.parse_args()

    tag = args.tag or os.path.basename(args.decoder.rstrip('/'))
    print(f'[c045-61] === 61-min 全长 (decoder={args.decoder}) ===', flush=True)
    print(f'[c045-61] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    audio, sr = sf.read(args.audio, dtype='float32')
    assert sr == 16000
    if audio.ndim > 1:
        audio = audio[:, 0]
    audio_dur = len(audio) / sr
    print(f'[c045-61] audio: {audio_dur:.1f}s ({audio_dur/60:.2f} min)', flush=True)

    print('[c045-61] loading SegmentEncoderOVBackend ...', flush=True)
    backend = SegmentEncoderOVBackend(
        encoder_dir=args.encoder, decoder_dir=args.decoder,
        device='GPU.0', precision='f16',
    )

    if not args.no_warmup:
        print('[c045-61] warmup (5s)...', flush=True)
        wstreamer = SegmentedStreamer(
            backend, strategy='off', chunk_size_sec=0.64,
            unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
            enable_hallucination_reset=False,
        )
        wstreamer.run(audio[:16000 * 5])
        print('[c045-61] warmup done', flush=True)

    print('[c045-61] main run (VAD 12-20s, no reset) ...', flush=True)
    streamer = SegmentedStreamer(
        backend, strategy='vad',
        min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64,
        unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
        enable_hallucination_reset=False,
    )
    t0 = time.perf_counter()
    full_text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0
    print(f'[c045-61] done, wall={wall:.1f}s ({wall/audio_dur:.3f} RTF)', flush=True)

    stats = ngram_stats(full_text)
    n_segs = len(segs)
    n_with_resets = sum(1 for s in segs if s.get('n_resets', 0) > 0)
    seg_rtfs = sorted(s['rtf'] for s in segs if s.get('rtf', 0) > 0)
    p50 = seg_rtfs[len(seg_rtfs) // 2] if seg_rtfs else 0
    p95 = seg_rtfs[min(int(len(seg_rtfs) * 0.95), len(seg_rtfs) - 1)] if seg_rtfs else 0

    print()
    print('=== 61-min 全长结果 ===')
    print(f'decoder:        {args.decoder}')
    print(f'wall_s:         {wall:.1f}')
    print(f'overall RTF:    {wall/audio_dur:.3f}')
    print(f'n_segs:         {n_segs}')
    print(f'总词数:         {stats["words"]}')
    print(f'n3_repeat:      {stats["n3_repeat"]}')
    print(f'n4_repeat:      {stats["n4_repeat"]}')
    print(f'seg RTF P50:    {p50:.3f}')
    print(f'seg RTF P95:    {p95:.3f}')

    out_dir = 'reports'
    transcript_path = os.path.join(out_dir, f'spe_61min_transcript_{tag}.txt')
    with open(transcript_path, 'w', encoding='utf-8') as f:
        for s in segs:
            f.write(f'[{s["start_s"]:7.1f}-{s["end_s"]:7.1f}] {s["text"]}\n')
    print(f'[c045-61] → {transcript_path}')

    segs_path = os.path.join(out_dir, f'spe_61min_segments_{tag}.json')
    with open(segs_path, 'w', encoding='utf-8') as f:
        json.dump(segs, f, ensure_ascii=False, indent=2)

    summary = {
        'mode': f'c045_61min_{tag}',
        'backend': 'SegmentEncoderOVBackend',
        'encoder_dir': args.encoder,
        'decoder_dir': args.decoder,
        'wall_s': wall, 'audio_dur_s': audio_dur, 'overall_rtf': wall / audio_dur,
        'n_segs': n_segs, 'n_chunks_total': sum(s['n_chunks'] for s in segs),
        'total_words': stats['words'], 'n3_repeat': stats['n3_repeat'], 'n4_repeat': stats['n4_repeat'],
        'n_segs_with_resets': n_with_resets, 'total_resets': sum(s.get('n_resets', 0) for s in segs),
        'seg_rtf_p50': p50, 'seg_rtf_p95': p95,
        'seg_rtf_max': seg_rtfs[-1] if seg_rtfs else 0,
    }
    summary_path = f'reports/c045_61min_{tag}/summary.json'
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'[c045-61] → {summary_path}')


if __name__ == '__main__':
    main()
