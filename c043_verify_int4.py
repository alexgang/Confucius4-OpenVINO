"""c043_verify_int4.py — C-043#3 备选 2 验证: INT4 + FP16 lm_head

对比 4 个 decoder (15 段):
  (i)   OV INT8 (all int8) [c039 baseline]
  (ii)  OV INT8+FP16-lm_head [c043 备选 1, 失败]
  (iii) OV FP16 [baseline]
  (iv)  OV INT4+FP16-lm_head [c043 备选 2, NEW]
"""
import os, sys, time, json, re
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


TOP15 = [
    (1925.4, 1939.5, 'seg118_1925_1940'),
    (2656.8, 2675.9, 'seg163_2657_2676'),
    (1086.3, 1102.4, 'seg67_1086_1102'),
    (2622.2, 2640.4, 'seg161_2622_2640'),
    ( 863.7,  881.1, 'seg55_864_881'),
    (2195.0, 2214.2, 'seg133_2195_2214'),
    (3439.4, 3458.2, 'seg212_3439_3458'),
    (3458.2, 3477.7, 'seg213_3458_3477'),
    (1034.1, 1051.5, 'seg65_1034_1051'),
    ( 372.7,  386.7, 'seg23_373_386'),
    (1647.2, 1664.1, 'seg99_1647_1664'),
    (1449.7, 1467.4, 'seg87_1450_1467'),
    (1530.7, 1550.1, 'seg92_1531_1550'),
    (2092.4, 2107.8, 'seg126_2092_2108'),
    ( 292.8,  309.3, 'seg18_293_309'),
]


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return [w for w in s.split() if w]


def ngram_stats(text):
    ws = words(text)
    out = {'words': len(ws)}
    for n in (3, 4):
        counts = Counter()
        for i in range(len(ws) - n + 1):
            counts[tuple(ws[i:i+n])] += 1
        out[f'n{n}_repeat'] = sum(c-1 for c in counts.values() if c > 1)
        out[f'n{n}_max'] = max(counts.values()) if counts else 0
    return out


def compare_logits_segment118(backends):
    print()
    print('[c043-int4-verify] === Step-by-step logits on seg118 chunk 4 ===', flush=True)
    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    seg = audio[int(1925.4*sr):int(1939.5*sr)]
    assert sr == 16000
    chunk_samples = int(0.64 * sr)
    chunk_audio = seg[:4 * chunk_samples]
    ehs, n_real, N_audio = backends['int8'].encode_audio(chunk_audio)
    print(f'[c043-int4-verify] ehs shape: {ehs.shape}, N_audio: {N_audio}', flush=True)
    for name in backends:
        dec = backends[name].dec_infer
        ids_left, ids_right = backends[name]._prompt_template_ids
        audio_pad_id = backends[name]._audio_pad_id
        prefix_ids = []
        full_ids = list(ids_left) + [audio_pad_id] * N_audio + list(ids_right) + list(prefix_ids)
        input_ids = np.array([full_ids], dtype=np.int64)
        ehs_dummy = ehs[:, :1, :]
        dec.reset_state()
        out = dec.infer({
            "input_ids": input_ids,
            "encoder_hidden_states": ehs,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        top5_idx = np.argsort(logits[0, -1, :])[-5:][::-1].tolist()
        top5_vals = logits[0, -1, top5_idx].tolist()
        top1 = top5_idx[0]
        top2 = top5_idx[1] if len(top5_idx) > 1 else -1
        margin = top5_vals[0] - top5_vals[1]
        print(f'  {name:14s} top1={top1} val={top5_vals[0]:.4f}  top2={top2} val={top5_vals[1]:.4f}  margin={margin:.4f}  top5={top5_idx}', flush=True)


def main():
    print('[c043-int4-verify] === C-043#3 备选 2: INT4 + FP16-lm_head ===', flush=True)
    print(f'[c043-int4-verify] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print('[c043-int4-verify] 加载 4 backends...', flush=True)
    backends = {
        'int8': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past',
            device='GPU.0', precision='f16',
        ),
        'int8lmfp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-lmfp16-past',
            device='GPU.0', precision='f16',
        ),
        'fp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-fp16-past',
            device='GPU.0', precision='f16',
        ),
        'int4lmfp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int4-lmfp16-past',
            device='GPU.0', precision='f16',
        ),
    }

    compare_logits_segment118(backends)

    print()
    print('[c043-int4-verify] === 15 段 × 4 decoder ===', flush=True)
    results_all = []
    for start, end, label in TOP15:
        snip_path = f'reports/c028_snippets/{label}.wav'
        if not os.path.exists(snip_path):
            audio_full, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
            if audio_full.ndim > 1:
                audio_full = audio_full[:, 0]
            audio = audio_full[int(start*sr):int(end*sr)]
        else:
            audio, sr = sf.read(snip_path, dtype='float32')
            if audio.ndim > 1:
                audio = audio[:, 0]
        assert sr == 16000
        print(f'\n[c043-int4-verify] === {label} ({len(audio)/sr:.1f}s) ===', flush=True)

        seg_results = {'label': label, 'start': start, 'end': end, 'dur': end-start}

        for name, backend in backends.items():
            _ = backend.encode_audio(audio[:16000])
            streamer = SegmentedStreamer(
                backend, strategy='off',
                chunk_size_sec=0.64,
                unfixed_chunk_num=0, unfixed_token_num=5,
                max_new_tokens=32,
            )
            t0 = time.perf_counter()
            text, _segs = streamer.run(audio)
            wall = time.perf_counter() - t0
            stats = ngram_stats(text)
            seg_results[f'{name}_text'] = text
            seg_results[f'{name}_words'] = stats['words']
            seg_results[f'{name}_n3'] = stats['n3_repeat']
            seg_results[f'{name}_n4'] = stats['n4_repeat']
            seg_results[f'{name}_n4max'] = stats['n4_max']
            seg_results[f'{name}_wall'] = wall
            print(f'  [{name:11s}] {stats["words"]:3d}w n3={stats["n3_repeat"]:3d} n4={stats["n4_repeat"]:3d} n4max={stats["n4_max"]:2d} wall={wall:.1f}s', flush=True)
        results_all.append(seg_results)

    out_dir = 'reports/c043_int4_verify'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results_15seg.json'), 'w', encoding='utf-8') as f:
        json.dump(results_all, f, ensure_ascii=False, indent=2)

    print()
    print('=== Summary (c043-int4: 4-decoder comparison) ===')
    print(f'{"label":24s} {"i_n4":>6s} {"ii_n4":>8s} {"iv_n4":>8s} {"iii_n4":>7s}')
    tot_i = tot_ii = tot_iv = tot_iii = 0
    for r in results_all:
        i = r.get('int8_n4', 0)
        ii = r.get('int8lmfp16_n4', 0)
        iv = r.get('int4lmfp16_n4', 0)
        iii = r.get('fp16_n4', 0)
        tot_i += i
        tot_ii += ii
        tot_iv += iv
        tot_iii += iii
        print(f'{r["label"]:24s} {i:6d} {ii:8d} {iv:8d} {iii:7d}')
    print(f'{"TOTAL":24s} {tot_i:6d} {tot_ii:8d} {tot_iv:8d} {tot_iii:7d}')


if __name__ == '__main__':
    main()
