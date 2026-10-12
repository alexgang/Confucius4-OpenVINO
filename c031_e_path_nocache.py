"""c031_e_path_nocache.py — C-031 第 1 步: e 路 (关 window cache)

Per C-031 审查: WhisperFeatureExtractor 的 log-mel 有**全局归一化**
(`log_spec = max(log_spec, log_spec.max() - 8.0)` + `(log_spec+4)/4`),
后面一出现更响的片段,前面所有帧的特征值都会变。
window cache 模式下,后续每个 chunk 送给 decoder 的"过去音频"特征,
都与全量重算 (torch / CUDA / Hybrid 离线) 不一致。

e 路 = 关 cache: 每个 chunk 对整段 audio_accum 全量提特征 + 所有窗口全量编码。
- 用 11 个最差段 (来自 c028_4path 同一组, SEGMENTS)
- 报告每段 n4-repeats (与 a 路 183 对比) + 每 chunk encoder 耗时
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
from backends import ASRBackend
import window_encoder_backend as web


# 与 c028_4path_localize.py 同样的 11 段
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


class NoCacheWindowEncoderOVBackend(WindowEncoderOVBackend):
    """e 路: 关 window cache, 每个 chunk 全量重提 mel + 全量编码所有窗口"""

    def encode_audio(self, wav: np.ndarray):
        """
        完全跳过 cache: 每个 chunk 重新提特征 + 编码所有窗口
        Returns: (ehs, n_real_frames, N_audio)
        """
        from backends import extract_audio_features
        # 1) 提特征 (用当前 audio_accum, 全量)
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
        # 2) 完整窗口: 全部重算
        for w in range(n_full_windows):
            win_mel = mel[:, w*800:(w+1)*800]
            t0 = time.perf_counter()
            ehs = self._encode_window(win_mel, 800)
            out_chunks.append(ehs)

        # 3) partial 窗口
        if last_chunk_count > 0:
            partial_mel = mel[:, n_full_mel:]
            valid_in_partial = partial_mel.shape[1]
            ehs = self._encode_window(partial_mel, valid_in_partial)
            out_chunks.append(ehs)

        ehs_all = np.concatenate(out_chunks, axis=1)
        return ehs_all, n_real, ehs_all.shape[1]


def run_streaming_e(backend, snip, label):
    """单段 streaming 跑一次, 收集每 chunk encoder 耗时"""
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
    print('[c031] === e 路 (关 window cache) 11 段 ===', flush=True)
    print(f'[c031] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print('[c031] loading e backend (OV window IR, no cache)...', flush=True)
    b_e = NoCacheWindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )

    snip_dir = 'reports/c028_snippets'
    os.makedirs(snip_dir, exist_ok=True)
    print(f'[c031] using snippets from {snip_dir}', flush=True)

    results = {'e': []}
    for seg_idx, start, end, label in SEGMENTS:
        snip_path = os.path.join(snip_dir, f'{label}.wav')
        if not os.path.exists(snip_path):
            print(f'  [c031] skip {label}: {snip_path} not found', flush=True)
            continue
        snip = {'idx': seg_idx, 'start_s': start, 'end_s': end, 'label': label, 'path': snip_path}
        try:
            t_start = time.perf_counter()
            r = run_streaming_e(b_e, snip, label)
            wall = time.perf_counter() - t_start
            results['e'].append(r)
            print(f'  [c031] [e] {label:24s} {r["words"]:3d}w n3={r["n3_repeat"]:2d} n4={r["n4_repeat"]:2d} n4max={r["n4_max"]:2d} wall={wall:.1f}s', flush=True)
        except Exception as e:
            print(f'  [c031] [e] {label:24s} ERROR: {e}', flush=True)
            import traceback; traceback.print_exc()
            results['e'].append({'label': label, 'err': str(e)})

    out_dir = 'reports/c031_epath'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'[c031] → {out_dir}/results.json', flush=True)

    # Summary
    print()
    print('=== Summary (per segment, a vs e) ===')
    print(f'{"label":24s} {"a_n4":>5s} {"e_n4":>5s} {"e_words":>7s}')
    # a path 数据来自 c028_4path/results.json
    a_path = 'reports/c028_4path/results.json'
    a_data = {}
    if os.path.exists(a_path):
        a_full = json.load(open(a_path, encoding='utf-8'))
        for r in a_full.get('a', []):
            a_data[r['label']] = r
    for i, (_, _, _, label) in enumerate(SEGMENTS):
        a4 = a_data.get(label, {}).get('n4_repeat', '-')
        e_rec = results['e'][i] if i < len(results['e']) else {}
        e4 = e_rec.get('n4_repeat', '-')
        ew = e_rec.get('words', '-')
        print(f'{label:24s} {str(a4):>5s} {str(e4):>5s} {str(ew):>7s}')
    tot_a = sum(r.get('n4_repeat', 0) for r in a_data.values())
    tot_e = sum(r.get('n4_repeat', 0) for r in results['e'])
    print(f'{"TOTAL":24s} {tot_a:>5d} {tot_e:>5d}')

    # Save summary
    with open(os.path.join(out_dir, 'summary.txt'), 'w', encoding='utf-8') as f:
        f.write(f'c031 e-path (no cache) vs a-path (cache)\n')
        f.write(f'a TOTAL n4_repeat: {tot_a}\n')
        f.write(f'e TOTAL n4_repeat: {tot_e}\n')
        f.write(f'差: {tot_e - tot_a:+d} ({((tot_e-tot_a)/tot_a*100 if tot_a else 0):+.1f}%)\n\n')
        f.write(f'{"label":24s} {"a_n4":>5s} {"e_n4":>5s}\n')
        for i, (_, _, _, label) in enumerate(SEGMENTS):
            a4 = a_data.get(label, {}).get('n4_repeat', '-')
            e_rec = results['e'][i] if i < len(results['e']) else {}
            e4 = e_rec.get('n4_repeat', '-')
            f.write(f'{label:24s} {str(a4):>5s} {str(e4):>5s}\n')
    print(f'[c031] → {out_dir}/summary.txt', flush=True)


if __name__ == '__main__':
    main()
