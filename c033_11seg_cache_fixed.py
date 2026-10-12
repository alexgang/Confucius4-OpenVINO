"""c033_11seg_cache_fixed.py — C-033#3: 11 个最差段 a 路（修好 cache）复测 n4

Per C-033: 用修好的 cache-mode backend 跑 11 个最差段, 对比 183 baseline.
无 reset (per C-033#1: 修 bug → 11 段复测 → 再叠加 reset)。
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
    print('[c033-11a] === 11 段 a 路 (cache 修好, 无 reset) ===', flush=True)
    print(f'[c033-11a] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    backend = WindowEncoderOVBackend(
        encoder_dir=os.environ.get('C038_ENCODER_DIR', 'models/ov-encoder-window'),
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )

    snip_dir = 'reports/c028_snippets'
    results = []
    for seg_idx, start, end, label in SEGMENTS:
        snip_path = os.path.join(snip_dir, f'{label}.wav')
        if not os.path.exists(snip_path):
            print(f'  [c033-11a] skip {label}', flush=True)
            continue
        audio, sr = sf.read(snip_path, dtype='float32')
        assert sr == 16000
        # 重置 cache (新段)
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
            results.append({
                'label': label, 'idx': seg_idx,
                'text': text, 'wall_s': wall,
                **stats,
            })
            print(f'  [c033-11a] [a-fixed] {label:24s} {stats["words"]:3d}w n3={stats["n3_repeat"]:2d} n4={stats["n4_repeat"]:2d} n4max={stats["n4_max"]:2d} wall={wall:.1f}s', flush=True)
        except Exception as e:
            print(f'  [c033-11a] [a-fixed] {label:24s} ERROR: {e}', flush=True)
            import traceback; traceback.print_exc()
            results.append({'label': label, 'err': str(e)})

    out_dir = 'reports/c033_cache_fixed'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results_11seg.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 对比 183 baseline (a-path 旧)
    a_old_data = {}
    a_old_path = 'reports/c028_4path/results.json'
    if os.path.exists(a_old_path):
        for r in json.load(open(a_old_path, encoding='utf-8')).get('a', []):
            a_old_data[r['label']] = r

    print()
    print('=== Summary (a-old cache broken vs a-fixed cache) ===')
    print(f'{"label":24s} {"a_old_n4":>9s} {"a_fix_n4":>9s}  {"diff":>5s}')
    tot_old = tot_new = 0
    for i, (_, _, _, label) in enumerate(SEGMENTS):
        old4 = a_old_data.get(label, {}).get('n4_repeat', '-')
        new_rec = results[i] if i < len(results) else {}
        new4 = new_rec.get('n4_repeat', '-')
        if isinstance(old4, int): tot_old += old4
        if isinstance(new4, int): tot_new += new4
        diff = (new4 - old4) if isinstance(old4, int) and isinstance(new4, int) else '-'
        print(f'{label:24s} {str(old4):>9s} {str(new4):>9s}  {str(diff):>5s}')
    print(f'{"TOTAL":24s} {tot_old:>9d} {tot_new:>9d}  {tot_new - tot_old:>5d}')

    with open(os.path.join(out_dir, 'summary_11seg.txt'), 'w', encoding='utf-8') as f:
        f.write(f'c033 11-segment a-path (cache fixed, no reset) vs a-old baseline\n')
        f.write(f'a-old (broken cache) TOTAL n4_repeat: {tot_old}\n')
        f.write(f'a-fix (cache fixed)   TOTAL n4_repeat: {tot_new}\n')
        f.write(f'diff: {tot_new - tot_old}\n\n')
        f.write(f'{"label":24s} {"a_old_n4":>9s} {"a_fix_n4":>9s} {"diff":>5s}\n')
        for i, (_, _, _, label) in enumerate(SEGMENTS):
            old4 = a_old_data.get(label, {}).get('n4_repeat', '-')
            new_rec = results[i] if i < len(results) else {}
            new4 = new_rec.get('n4_repeat', '-')
            f.write(f'{label:24s} {str(old4):>9s} {str(new4):>9s} {str(new4 - old4 if isinstance(old4, int) and isinstance(new4, int) else "-"):>5s}\n')
    print(f'[c033-11a] → {out_dir}/summary_11seg.txt')


if __name__ == '__main__':
    main()
