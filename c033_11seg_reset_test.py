"""c033_11seg_reset_test.py — C-033#4: 11 个最差段 (cache 修好 + 新 reset 语义)

Per C-033#4: 新 reset 语义
- 3-gram ≥3 OR gen_text 前缀与 prefix 末尾 ≥6 词重合
- → DISCARD gen_text, KEEP prev fixed_text, CONTINUE
- 同一段内连续 3 次就 force_finish

对比 c033_11seg_cache_fixed.py (cache 修好无 reset) 和 c031_11seg_reset (旧 reset)
"""
import os, sys, time, json, re
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf
from collections import Counter

from window_encoder_backend import WindowEncoderOVBackend
from seg_stream import SegmentedStreamer


SEGMENTS = [
    (38, 607.0, 624.0, 'seg38_607_624'),
    (39, 624.0, 641.1, 'seg39_624_641'),
    (172, 2812.3, 2827.7, 'seg172_2812_2828'),
    (124, 2025.0, 2042.2, 'seg124_2025_2042'),
    (212, 3439.4, 3458.2, 'seg212_3439_3458'),
    (197, 3198.0, 3215.0, 'seg197_3198_3215'),
    (213, 3458.2, 3477.7, 'seg213_3458_3477'),
    (23, 372.7, 386.7, 'seg23_372_386'),
    (163, 2656.8, 2675.9, 'seg163_2656_2676'),
    (161, 2622.2, 2640.4, 'seg161_2622_2640'),
    (81, 1313.3, 1328.9, 'seg81_1313_1329'),
]


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
    print('[c033-11r] === 11 段 cache 修好 + 新 reset 语义 ===', flush=True)
    print(f'[c033-11r] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    backend = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )

    snip_dir = 'reports/c028_snippets'
    results = []
    for seg_idx, start, end, label in SEGMENTS:
        snip_path = os.path.join(snip_dir, f'{label}.wav')
        if not os.path.exists(snip_path):
            print(f'  [c033-11r] skip {label}', flush=True)
            continue
        audio, sr = sf.read(snip_path, dtype='float32')
        assert sr == 16000
        # 重置 cache + 新段
        backend._window_cache_ehs = []
        backend._window_cache_mel_cum = 0

        streamer = SegmentedStreamer(
            backend, strategy='off',
            chunk_size_sec=0.64,
            unfixed_chunk_num=0, unfixed_token_num=5,
            max_new_tokens=32,
        )
        try:
            t0 = time.perf_counter()
            text, segs = streamer.run(audio)
            wall = time.perf_counter() - t0
            stats = ngram_stats(text)
            n_resets = segs[0].get('n_resets', 0) if segs else 0
            results.append({
                'label': label, 'idx': seg_idx,
                'text': text, 'wall_s': wall,
                **stats,
                'n_resets': n_resets,
            })
            print(f'  [c033-11r] {label:24s} {stats["words"]:3d}w n3={stats["n3_repeat"]:2d} n4={stats["n4_repeat"]:2d} n4max={stats["n4_max"]:2d} resets={n_resets} wall={wall:.1f}s', flush=True)
        except Exception as e:
            print(f'  [c033-11r] {label:24s} ERROR: {e}', flush=True)
            import traceback; traceback.print_exc()
            results.append({'label': label, 'err': str(e)})

    out_dir = 'reports/c033_cache_fixed'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results_11seg_with_reset.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 对比
    a_old_data = {}
    a_old_path = 'reports/c028_4path/results.json'
    if os.path.exists(a_old_path):
        for r in json.load(open(a_old_path, encoding='utf-8')).get('a', []):
            a_old_data[r['label']] = r

    a_fix_data = {}
    a_fix_path = os.path.join(out_dir, 'results_11seg.json')
    if os.path.exists(a_fix_path):
        for r in json.load(open(a_fix_path, encoding='utf-8')):
            a_fix_data[r['label']] = r

    print()
    print('=== Summary (a-old vs a-fix vs a-fix+reset) ===')
    print(f'{"label":24s} {"a_old":>5s} {"a_fix":>5s} {"a_f+r":>5s}  {"resets":>7s}')
    tot_old = tot_fix = tot_reset = tot_resets = 0
    for i, (_, _, _, label) in enumerate(SEGMENTS):
        old4 = a_old_data.get(label, {}).get('n4_repeat', '-')
        fix4 = a_fix_data.get(label, {}).get('n4_repeat', '-')
        r_rec = results[i] if i < len(results) else {}
        r4 = r_rec.get('n4_repeat', '-')
        nr = r_rec.get('n_resets', 0)
        if isinstance(old4, int): tot_old += old4
        if isinstance(fix4, int): tot_fix += fix4
        if isinstance(r4, int): tot_reset += r4
        if isinstance(nr, int): tot_resets += nr
        print(f'{label:24s} {str(old4):>5s} {str(fix4):>5s} {str(r4):>5s}  {str(nr):>7s}')
    print(f'{"TOTAL":24s} {tot_old:>5d} {tot_fix:>5d} {tot_reset:>5d}  {tot_resets:>7d}')

    with open(os.path.join(out_dir, 'summary_11seg_with_reset.txt'), 'w', encoding='utf-8') as f:
        f.write(f'c033 11-segment: a-old (broken cache) vs a-fix (cache fixed) vs a-fix+reset (new reset)\n')
        f.write(f'a-old TOTAL n4: {tot_old}\n')
        f.write(f'a-fix TOTAL n4: {tot_fix}\n')
        f.write(f'a-fix+reset TOTAL n4: {tot_reset}\n')
        f.write(f'a-fix+reset force_finishes: {tot_resets}\n\n')
        f.write(f'{"label":24s} {"a_old":>5s} {"a_fix":>5s} {"a_f+r":>5s} {"resets":>7s}\n')
        for i, (_, _, _, label) in enumerate(SEGMENTS):
            old4 = a_old_data.get(label, {}).get('n4_repeat', '-')
            fix4 = a_fix_data.get(label, {}).get('n4_repeat', '-')
            r_rec = results[i] if i < len(results) else {}
            r4 = r_rec.get('n4_repeat', '-')
            nr = r_rec.get('n_resets', 0)
            f.write(f'{label:24s} {str(old4):>5s} {str(fix4):>5s} {str(r4):>5s} {str(nr):>7s}\n')
    print(f'[c033-11r] → {out_dir}/summary_11seg_with_reset.txt')


if __name__ == '__main__':
    main()
