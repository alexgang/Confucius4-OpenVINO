"""c031_hallucination_reset_test.py — user 10:26 fallback option B

按 user 10:26 指令: "如果 30 分钟（到 10-12 11:00）已过仍未收到,
仍按 C-027 STATUS 推荐 option B 执行: 在 streaming_asr.py 加 hallucination reset
(3-gram ≥3 连续重复 → 截断 + finish 当前段), 36-min 复测 + 61-min 复跑 + WER 复算"

deadline 11:00 已过 (当前 11:10+), reviewer 响应 (C-030/031/032) 未给出可行路径:
- C-031 e-path: cache 不是根因
- C-032: per-chunk cu_seqlens 方向错
- C-030 B 修 partial chunk mask: 需 torch, SAC 阻塞

按 user 兜底,实施 option B。

测试:
- 11 个最差段 (C-028 同一组)
- 用 WindowEncoderOVBackend (原版 cache) + seg_stream 单段 + hallucination reset
- 对比 a-path (cache, no reset) 的 n4-repeats
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
    print('[c031g] === g 路 (cache + hallucination reset) 11 段 ===', flush=True)
    print(f'[c031g] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

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
            print(f'  [c031g] skip {label}', flush=True)
            continue
        audio, sr = sf.read(snip_path, dtype='float32')
        assert sr == 16000
        # 用 SegmentedStreamer 单段 (strategy=off) + 1 段 = 整段
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
            print(f'  [c031g] [g] {label:24s} {stats["words"]:3d}w n3={stats["n3_repeat"]:2d} n4={stats["n4_repeat"]:2d} n4max={stats["n4_max"]:2d} resets={n_resets} wall={wall:.1f}s', flush=True)
        except Exception as e:
            print(f'  [c031g] [g] {label:24s} ERROR: {e}', flush=True)
            import traceback; traceback.print_exc()
            results.append({'label': label, 'err': str(e)})

    out_dir = 'reports/c031_epath'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results_g_hallucination_reset.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    a_data = {}
    a_path = 'reports/c028_4path/results.json'
    if os.path.exists(a_path):
        for r in json.load(open(a_path, encoding='utf-8')).get('a', []):
            a_data[r['label']] = r
    e_data = {}
    e_path_data = os.path.join(out_dir, 'results.json')
    if os.path.exists(e_path_data):
        for r in json.load(open(e_path_data, encoding='utf-8')).get('e', []):
            e_data[r['label']] = r

    print()
    print('=== Summary (a cache vs e no-cache vs g cache+reset) ===')
    print(f'{"label":24s} {"a_n4":>5s} {"e_n4":>5s} {"g_n4":>5s}  {"resets":>7s}')
    tot_a = tot_e = tot_g = tot_resets = 0
    for i, (_, _, _, label) in enumerate(SEGMENTS):
        a4 = a_data.get(label, {}).get('n4_repeat', '-')
        e4 = e_data.get(label, {}).get('n4_repeat', '-')
        g_rec = results[i] if i < len(results) else {}
        g4 = g_rec.get('n4_repeat', '-')
        nr = g_rec.get('n_resets', 0)
        if isinstance(a4, int): tot_a += a4
        if isinstance(e4, int): tot_e += e4
        if isinstance(g4, int): tot_g += g4
        if isinstance(nr, int): tot_resets += nr
        print(f'{label:24s} {str(a4):>5s} {str(e4):>5s} {str(g4):>5s}  {str(nr):>7s}')
    print(f'{"TOTAL":24s} {tot_a:>5d} {tot_e:>5d} {tot_g:>5d}  {tot_resets:>7d}')

    with open(os.path.join(out_dir, 'summary_g.txt'), 'w', encoding='utf-8') as f:
        f.write(f'c031 g-path (cache + hallucination reset, user 10:26 fallback)\n')
        f.write(f'a TOTAL n4_repeat: {tot_a}\n')
        f.write(f'e TOTAL n4_repeat: {tot_e}\n')
        f.write(f'g TOTAL n4_repeat: {tot_g}\n')
        f.write(f'g TOTAL resets triggered: {tot_resets}\n\n')
        f.write(f'{"label":24s} {"a_n4":>5s} {"e_n4":>5s} {"g_n4":>5s} {"resets":>7s}\n')
        for i, (_, _, _, label) in enumerate(SEGMENTS):
            a4 = a_data.get(label, {}).get('n4_repeat', '-')
            e4 = e_data.get(label, {}).get('n4_repeat', '-')
            g_rec = results[i] if i < len(results) else {}
            g4 = g_rec.get('n4_repeat', '-')
            nr = g_rec.get('n_resets', 0)
            f.write(f'{label:24s} {str(a4):>5s} {str(e4):>5s} {str(g4):>5s} {str(nr):>7s}\n')
    print(f'[c031g] → {out_dir}/summary_g.txt')


if __name__ == '__main__':
    main()
