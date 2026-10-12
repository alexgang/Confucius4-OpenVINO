"""ov_offline_full.py — C-020: OV INT8-past 离线整段 greedy，每段一次

按 reports/spe_61min_segments.json 切段，每段用 OVBackend 离线 greedy 跑一次。
输出 reports/spe_ov_offline.txt (格式 [start-end] text)。
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf

sys.path.insert(0, '.')
from backends import OVBackend, SAMPLE_RATE

WAV_IN = 'test_audio/260902_SPE_audio.wav'
SEG_JSON = 'reports/spe_61min_segments.json'
MODEL_DIR = 'models/ov-int8-past'
OUT_TXT = 'reports/spe_ov_offline.txt'
OUT_JSON = 'reports/spe_ov_offline_segments.json'
OUT_DIR = 'reports/spe_ov_offline_logs'
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    print(f'[ov-offline] loading {MODEL_DIR} ...', flush=True)
    t0 = time.perf_counter()
    b = OVBackend(model_dir=MODEL_DIR, device='GPU.0')
    print(f'[ov-offline] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    audio, sr = sf.read(WAV_IN)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE

    with open(SEG_JSON, 'r', encoding='utf-8') as f:
        segs = json.load(f)['segments']
    print(f'[ov-offline] {len(segs)} segments', flush=True)

    results = []
    full_text_lines = []
    wall_start = time.perf_counter()
    for s in segs:
        idx = s['seg_idx']
        start = int(s['start_s'] * SAMPLE_RATE)
        end = int(s['end_s'] * SAMPLE_RATE)
        seg_audio = audio[start:end]
        if seg_audio.shape[0] == 0:
            continue
        # 离线 greedy
        seg_t0 = time.perf_counter()
        ehs, n_real, N_audio = b.encode_audio(seg_audio)
        out_ids = b.greedy_decode_with_prefix(ehs, prefix_ids=[], max_new_tokens=512)
        seg_wall = time.perf_counter() - seg_t0
        text = b.tokenizer.decode(out_ids, skip_special_tokens=True)
        # 切 language 前缀
        from streaming_asr import parse_asr_output
        lang, txt = parse_asr_output(text, user_language=None)
        if not txt:
            txt = text
        print(f'[ov-offline] seg {idx:3d} start={s["start_s"]:.1f}s end={s["end_s"]:.1f}s '
              f'wall={seg_wall:.2f}s n_real={n_real} N_audio={N_audio} '
              f'out_ids={len(out_ids)} text[:60]={txt[:60]!r}', flush=True)
        results.append({
            'seg_idx': idx, 'start_s': s['start_s'], 'end_s': s['end_s'],
            'wall_s': seg_wall, 'n_real': n_real, 'N_audio': N_audio,
            'out_ids_count': len(out_ids), 'text': txt,
        })
        full_text_lines.append(f"[{s['start_s']:.1f}-{s['end_s']:.1f}] {txt}")
    wall_total = time.perf_counter() - wall_start
    print(f'[ov-offline] done {len(results)} segs, wall={wall_total:.2f}s', flush=True)

    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(full_text_lines) + '\n')
    print(f'[ov-offline] → {OUT_TXT}', flush=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'wall_s': wall_total, 'segments': results}, f, ensure_ascii=False, indent=2)
    print(f'[ov-offline] → {OUT_JSON}', flush=True)


if __name__ == '__main__':
    main()
