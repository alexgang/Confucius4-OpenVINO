"""c031_smart_cache.py — C-031#4: smart cache backend

Per C-031 fix proposal:
- 每个 chunk 照常对整段音频提 mel（mel 很便宜）
- 只缓存窗口的 encoder 输出
- 缓存命中条件: 该窗口的 mel 与缓存时相比 max abs diff < 1e-4
- 否则重算
- 最近一个已满窗口**不缓存**（避开 STFT 边界）

对比:
- a = 原版 cache（每个 full 窗永久缓存）
- e = 无 cache（每 chunk 全量编码）
- f = smart cache（mel 变化时 invalidate）
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
from backends import extract_audio_features


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


class SmartCacheWindowEncoderOVBackend(WindowEncoderOVBackend):
    """f 路: smart cache，mel 变化时自动 invalidate

    缓存结构:
    - _cache_ehs[i] = window i 的 encoder 输出 (1, 104, 2048)
    - _cache_mel[i] = window i 对应的 mel slice (128, 800)
    - _cache_n_mel_total = 缓存时 audio_so_far 的总 mel 数
    """

    def __init__(self, *args, mel_tol: float = 1e-4, **kwargs):
        super().__init__(*args, **kwargs)
        self._mel_tol = mel_tol
        # 替换内部 cache 结构
        self._cache_ehs = []  # list of (1, 104, 2048)
        self._cache_mel = []  # list of (128, 800)
        # WindowEncoderOVBackend 原版的 _window_cache_ehs 也保留兼容

    def encode_audio(self, wav: np.ndarray):
        """
        smart cache:
        1) 重新提特征
        2) 对每个 full 800-mel 窗: 比较 _cache_mel[i] vs mel[:, i*800:(i+1)*800]
           - 一致 (max abs diff < tol): 复用 _cache_ehs[i]
           - 不一致: 重算 + 更新 _cache_mel[i] 和 _cache_ehs[i]
        3) 最后一个 partial 窗: 永远重算, 不缓存 (C-031 边界规则)
        """
        feats_real, _, n_real, N_audio = extract_audio_features(
            self.feature_extractor, wav, return_torch=False,
        )
        mel = feats_real[0]  # (128, T_mel_real)
        n_mel = mel.shape[1]
        if n_mel == 0:
            return np.zeros((1, 0, 2048), dtype=np.float32), 0, 0

        n_100_blocks = (n_mel + 99) // 100
        n_full_windows = n_100_blocks // 8
        n_full_mel = n_full_windows * 800
        last_chunk_count = n_100_blocks - n_full_windows * 8

        out_chunks = []

        # 对每个完整窗: smart cache
        for w in range(n_full_windows):
            cur_mel = mel[:, w*800:(w+1)*800]
            if w < len(self._cache_ehs) and self._cache_mel[w].shape == cur_mel.shape:
                cached_mel = self._cache_mel[w]
                max_diff = float(np.max(np.abs(cached_mel - cur_mel)))
                if max_diff < self._mel_tol:
                    # cache hit
                    out_chunks.append(self._cache_ehs[w])
                    continue
            # cache miss or stale: 重算
            ehs = self._encode_window(cur_mel, 800)
            # 更新 cache
            if w < len(self._cache_ehs):
                self._cache_ehs[w] = ehs
                self._cache_mel[w] = cur_mel.copy()
            else:
                # 超出原 cache 长度, append (但保留最后 1 个不缓存)
                if w < n_full_windows - 1:
                    self._cache_ehs.append(ehs)
                    self._cache_mel.append(cur_mel.copy())
                else:
                    # 最后一个已满窗: 不缓存 (C-031 边界规则)
                    pass
            out_chunks.append(ehs)

        # 截断 cache 到当前 full 窗数（如果音频变短了）
        if len(self._cache_ehs) > n_full_windows:
            self._cache_ehs = self._cache_ehs[:n_full_windows]
            self._cache_mel = self._cache_mel[:n_full_windows]

        # 最后一个 partial 窗: 永远重算, 不缓存
        if last_chunk_count > 0:
            partial_mel = mel[:, n_full_mel:]
            valid_in_partial = partial_mel.shape[1]
            ehs = self._encode_window(partial_mel, valid_in_partial)
            out_chunks.append(ehs)

        if not out_chunks:
            return np.zeros((1, 0, 2048), dtype=np.float32), 0, 0

        ehs_all = np.concatenate(out_chunks, axis=1)
        return ehs_all, n_real, ehs_all.shape[1]


def run_streaming_f(backend, snip, label):
    from streaming_asr import streaming_transcribe, finish_streaming_transcribe
    audio, sr = sf.read(snip['path'], dtype='float32')
    state = backend.init_streaming_state(
        unfixed_chunk_num=0,
        unfixed_token_num=5,
        chunk_size_sec=0.64,
    )
    t0 = time.perf_counter()
    feed_chunk = int(16000 * 0.04)  # 40ms
    p = 0
    n_chunks = 0
    while p < len(audio):
        e = min(p + feed_chunk, len(audio))
        streaming_transcribe(backend, audio[p:e], state, max_new_tokens=32)
        p = e
        n_chunks += 1
    final = finish_streaming_transcribe(backend, state, max_new_tokens=64)
    wall = time.perf_counter() - t0
    audio_dur = len(audio) / 16000.0
    stats = ngram_stats(final)
    stats['n_chunks'] = n_chunks
    stats['audio_dur_s'] = audio_dur
    stats['seg_rtf'] = wall / audio_dur if audio_dur else 0
    return {
        'label': label, 'idx': snip['idx'],
        'start_s': snip['start_s'], 'end_s': snip['end_s'],
        'text': final, 'wall_s': wall,
        **stats,
    }


def main():
    print('[c031f] === f 路 (smart cache) 11 段 ===', flush=True)
    print(f'[c031f] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    b_f = SmartCacheWindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
        mel_tol=1e-4,
    )

    snip_dir = 'reports/c028_snippets'
    results = {'f': []}
    for seg_idx, start, end, label in SEGMENTS:
        snip_path = os.path.join(snip_dir, f'{label}.wav')
        if not os.path.exists(snip_path):
            print(f'  [c031f] skip {label}', flush=True)
            continue
        snip = {'idx': seg_idx, 'start_s': start, 'end_s': end, 'label': label, 'path': snip_path}
        try:
            t_start = time.perf_counter()
            r = run_streaming_f(b_f, snip, label)
            wall = time.perf_counter() - t_start
            results['f'].append(r)
            print(f'  [c031f] [f] {label:24s} {r["words"]:3d}w n3={r["n3_repeat"]:2d} n4={r["n4_repeat"]:2d} n4max={r["n4_max"]:2d} wall={wall:.1f}s', flush=True)
        except Exception as e:
            print(f'  [c031f] [f] {label:24s} ERROR: {e}', flush=True)
            import traceback; traceback.print_exc()
            results['f'].append({'label': label, 'err': str(e)})

    out_dir = 'reports/c031_epath'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results_f_smart_cache.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    a_path = 'reports/c028_4path/results.json'
    e_path_data = os.path.join(out_dir, 'results.json')
    a_data = {}
    if os.path.exists(a_path):
        for r in json.load(open(a_path, encoding='utf-8')).get('a', []):
            a_data[r['label']] = r
    e_data = {}
    if os.path.exists(e_path_data):
        for r in json.load(open(e_path_data, encoding='utf-8')).get('e', []):
            e_data[r['label']] = r

    print()
    print('=== Summary (a 原版 cache vs e 无 cache vs f smart cache) ===')
    print(f'{"label":24s} {"a_n4":>5s} {"e_n4":>5s} {"f_n4":>5s}  {"f_words":>7s}')
    tot_a = tot_e = tot_f = 0
    for i, (_, _, _, label) in enumerate(SEGMENTS):
        a4 = a_data.get(label, {}).get('n4_repeat', '-')
        e4 = e_data.get(label, {}).get('n4_repeat', '-')
        f_rec = results['f'][i] if i < len(results['f']) else {}
        f4 = f_rec.get('n4_repeat', '-')
        fw = f_rec.get('words', '-')
        if isinstance(a4, int): tot_a += a4
        if isinstance(e4, int): tot_e += e4
        if isinstance(f4, int): tot_f += f4
        print(f'{label:24s} {str(a4):>5s} {str(e4):>5s} {str(f4):>5s}  {str(fw):>7s}')
    print(f'{"TOTAL":24s} {tot_a:>5d} {tot_e:>5d} {tot_f:>5d}')

    with open(os.path.join(out_dir, 'summary_f.txt'), 'w', encoding='utf-8') as f:
        f.write(f'c031 f-path (smart cache)\n')
        f.write(f'a TOTAL n4_repeat: {tot_a}\n')
        f.write(f'e TOTAL n4_repeat: {tot_e}\n')
        f.write(f'f TOTAL n4_repeat: {tot_f}\n\n')
        f.write(f'{"label":24s} {"a_n4":>5s} {"e_n4":>5s} {"f_n4":>5s}\n')
        for i, (_, _, _, label) in enumerate(SEGMENTS):
            a4 = a_data.get(label, {}).get('n4_repeat', '-')
            e4 = e_data.get(label, {}).get('n4_repeat', '-')
            f_rec = results['f'][i] if i < len(results['f']) else {}
            f4 = f_rec.get('n4_repeat', '-')
            f.write(f'{label:24s} {str(a4):>5s} {str(e4):>5s} {str(f4):>5s}\n')
    print(f'[c031f] → {out_dir}/summary_f.txt')


if __name__ == '__main__':
    main()
