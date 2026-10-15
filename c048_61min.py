"""c048_61min.py — C-047/C-048: 61-min 全量集验证自适应生成长度

对比以下配置（同验收口径：segment encoder + VAD 12-20s + no reset）：
  baseline     : max_new_tokens=32 固定（当前生产）
  adaptive     : 自适应 1..floor（复刻 R2T2 官方 example.py:118-155），
                 段尾 flush 预算 max(64, 32)=64（C-047 现状）
  finish_first : 同上，但段尾 flush 用官方 first_max_new_tokens
                 = max(1, int(chunk_samples/1280))，640 ms → 8
                 （C-049 遗留项受控实验，只改这一个量）

用法:
  .venv python c048_61min.py --variants baseline,adaptive
  .venv python c048_61min.py --variants finish_first      # C-049 受控实验
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

ENC = 'models/ov-encoder-segment-reviewer'
DEC = 'models/ov-int8-past'
OUT_DIR = 'reports/c048_61min_adaptive'


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


def run_variant(backend, audio, adaptive, audio_dur, finish_budget='max64',
                name=None):
    """跑一个变体。C-049 起支持 finish_budget 口径（max64 现状 / first 官方）。"""
    if name is None:
        name = 'adaptive' if adaptive else 'baseline'
    print(f'\n[c048] === {name} (finish_budget={finish_budget}) ===', flush=True)
    streamer = SegmentedStreamer(
        backend, strategy='vad',
        min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64,
        unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
        adaptive_budget=adaptive,
        finish_budget=finish_budget,
        enable_hallucination_reset=False,
    )
    t0 = time.perf_counter()
    full_text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0

    stats = ngram_stats(full_text)
    seg_rtfs = sorted(s['rtf'] for s in segs if s.get('rtf', 0) > 0)
    p50 = seg_rtfs[len(seg_rtfs) // 2] if seg_rtfs else 0
    p95 = seg_rtfs[min(int(len(seg_rtfs) * 0.95), len(seg_rtfs) - 1)] if seg_rtfs else 0

    print(f'[c048] {name}: wall={wall:.1f}s RTF={wall/audio_dur:.3f} '
          f'segs={len(segs)} words={stats["words"]} '
          f'n3={stats["n3_repeat"]} n4={stats["n4_repeat"]} '
          f'P50={p50:.3f} P95={p95:.3f}', flush=True)

    tp = os.path.join(OUT_DIR, f'transcript_{name}.txt')
    with open(tp, 'w', encoding='utf-8') as f:
        for s in segs:
            f.write(f'[{s["start_s"]:7.1f}-{s["end_s"]:7.1f}] {s["text"]}\n')
    with open(os.path.join(OUT_DIR, f'segments_{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(segs, f, ensure_ascii=False, indent=2)

    return {
        'name': name, 'adaptive': adaptive, 'finish_budget': finish_budget,
        'wall_s': round(wall, 1), 'overall_rtf': round(wall / audio_dur, 3),
        'n_segs': len(segs),
        'n_chunks_total': sum(s['n_chunks'] for s in segs),
        'total_words': stats['words'],
        'n3_repeat': stats['n3_repeat'], 'n4_repeat': stats['n4_repeat'],
        'n3_max': stats['n3_max'], 'n4_max': stats['n4_max'],
        'seg_rtf_p50': round(p50, 3), 'seg_rtf_p95': round(p95, 3),
        'seg_rtf_max': round(seg_rtfs[-1], 3) if seg_rtfs else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variants', default='baseline,adaptive')
    ap.add_argument('--audio', default='test_audio/260902_SPE_audio.wav')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    audio, sr = sf.read(args.audio, dtype='float32')
    assert sr == 16000
    if audio.ndim > 1:
        audio = audio[:, 0]
    audio_dur = len(audio) / sr
    print(f'[c048] audio {audio_dur:.1f}s ({audio_dur/60:.2f} min)', flush=True)

    backend = SegmentEncoderOVBackend(encoder_dir=ENC, decoder_dir=DEC,
                                      device='GPU.0', precision='f16')

    # 预热（编译后第一次推理会直接吐 EOS，必须废弃一次）
    print('[c048] warmup (5s) ...', flush=True)
    ws = SegmentedStreamer(backend, strategy='off', chunk_size_sec=0.64,
                           unfixed_chunk_num=0, unfixed_token_num=5,
                           max_new_tokens=32, adaptive_budget=True,
                           enable_hallucination_reset=False)
    ws.run(audio[:16000 * 5])
    print('[c048] warmup done', flush=True)

    results = []
    for v in args.variants.split(','):
        v = v.strip()
        if v == 'baseline':
            kw = dict(adaptive=False, finish_budget='max64', name='baseline')
        elif v == 'adaptive':
            kw = dict(adaptive=True, finish_budget='max64', name='adaptive')
        elif v == 'finish_first':
            # C-049 受控实验：只改段尾 flush 预算为官方 first_max_new_tokens
            kw = dict(adaptive=True, finish_budget='first', name='finish_first')
        else:
            raise SystemExit(f'unknown variant: {v}')
        results.append(run_variant(backend, audio, audio_dur=audio_dur, **kw))

    sp = os.path.join(OUT_DIR, 'summary.json')
    with open(sp, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n[c048] saved -> {sp}', flush=True)

    print('\n=== 汇总 ===')
    for r in results:
        print(f'{r["name"]:9s} RTF={r["overall_rtf"]:.3f} wall={r["wall_s"]:6.1f}s '
              f'words={r["total_words"]:5d} n3={r["n3_repeat"]:4d} n4={r["n4_repeat"]:4d} '
              f'P95={r["seg_rtf_p95"]:.3f}', flush=True)


if __name__ == '__main__':
    main()