"""c031_growing_audio_cosine.py — C-031 第 2 步: 逐 chunk 增长一致性测试

Per C-031 怀疑: window cache 在逐 chunk 增长音频下, 因 WhisperFeatureExtractor
全局归一化 (log_spec.max() 对整段求) 而导致 ehs 与全量重算不一致。

测试:
- 取 seg172 [2812-2828] 真实音频 (15.4s)
- 模拟 640ms 一步增长
- 每步: cache-mode encode_audio vs full-recompute ehs 逐 token cosine
- 报告: 每步 min cos / 第一次 <0.99 在哪步 / 哪个窗口
"""
import os, sys, time
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf
import openvino as ov

from window_encoder_backend import WindowEncoderOVBackend
from backends import extract_audio_features


def aftercnn_len(n: int) -> int:
    x = n
    for _ in range(3):
        x = (x + 1) // 2
    return x


def compute_ehs_full_recompute(backend, mel):
    """全量重算: 不读 cache, 每个窗调 _encode_window.
    C-033#1: 同样按 mel 帧数向下取整, 不要 n_100//8.
    """
    n_mel = mel.shape[1]
    n_full_windows = n_mel // 800
    n_full_mel = n_full_windows * 800
    out_chunks = []
    for w in range(n_full_windows):
        win_mel = mel[:, w*800:(w+1)*800]
        ehs = backend._encode_window(win_mel, 800)
        out_chunks.append(ehs)
    partial_mel_len = n_mel - n_full_mel
    if partial_mel_len > 0:
        partial_mel = mel[:, n_full_mel:]
        valid_in_partial = partial_mel_len
        ehs = backend._encode_window(partial_mel, valid_in_partial)
        out_chunks.append(ehs)
    if not out_chunks:
        return np.zeros((1, 0, 2048), dtype=np.float32)
    return np.concatenate(out_chunks, axis=1)


def main():
    print('[c031-cos] === 逐 chunk 增长 cache vs full-recompute cosine ===', flush=True)
    print(f'[c031-cos] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print('[c031-cos] loading backend ...', flush=True)
    backend = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )

    audio_path = 'reports/c028_snippets/seg172_2812_2828.wav'
    audio, sr = sf.read(audio_path, dtype='float32')
    print(f'[c031-cos] seg172 audio: {len(audio)} samples = {len(audio)/sr:.2f}s', flush=True)

    chunk_sec = 0.64
    chunk_samples = int(chunk_sec * sr)
    n_steps = (len(audio) + chunk_samples - 1) // chunk_samples
    print(f'[c031-cos] {n_steps} steps of {chunk_sec}s', flush=True)

    # Reset cache
    backend._window_cache_ehs = []
    backend._window_cache_mel_cum = 0

    rows = []
    first_low_step = None
    for step in range(1, n_steps + 1):
        end = min(step * chunk_samples, len(audio))
        audio_so_far = audio[:end]

        # 1) cache-mode encode_audio (会读写 backend._window_cache_ehs)
        ehs_cache, n_real_cache, N_audio_cache = backend.encode_audio(audio_so_far)

        # 2) full-recompute (不读 cache, 但需要重新提特征, 提特征本身会受 log-mel 全局归一化影响)
        #    为了隔离 cache 与 full 的差异, full 也要用同样的 audio_so_far 提特征再算 ehs
        feats_full, _, n_real_full, N_audio_full = extract_audio_features(
            backend.feature_extractor, audio_so_far, return_torch=False,
        )
        mel_full = feats_full[0]
        ehs_full = compute_ehs_full_recompute(backend, mel_full)

        # 3) cosine
        n_compare = min(ehs_cache.shape[1], ehs_full.shape[1])
        if n_compare == 0:
            print(f'  step {step:2d}  audio={end/sr:.2f}s  empty ehs, skip', flush=True)
            continue
        a = ehs_cache[0, :n_compare, :].astype(np.float32)
        b = ehs_full[0, :n_compare, :].astype(np.float32)
        cos_per_tok = (a * b).sum(axis=-1) / (
            np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1) + 1e-9
        )
        cos_mean = float(cos_per_tok.mean())
        cos_min = float(cos_per_tok.min())
        n_low = int((cos_per_tok < 0.99).sum())
        first_low_tok = None
        if n_low > 0:
            idx = np.where(cos_per_tok < 0.99)[0]
            first_low_tok = int(idx[0])
        print(f'  step {step:2d}  audio={end/sr:5.2f}s  N_audio={n_compare:4d}  '
              f'cos_mean={cos_mean:.6f}  cos_min={cos_min:.6f}  '
              f'n<0.99={n_low:3d}  first_low_tok={first_low_tok}', flush=True)
        rows.append({
            'step': step, 'audio_s': end/sr, 'N_audio': n_compare,
            'cos_mean': cos_mean, 'cos_min': cos_min, 'n_low_99': n_low,
            'first_low_tok': first_low_tok,
        })
        if first_low_step is None and n_low > 0:
            first_low_step = step

    out_dir = 'reports/c031_epath'
    os.makedirs(out_dir, exist_ok=True)
    import json
    with open(os.path.join(out_dir, 'growing_audio_cosine.json'), 'w', encoding='utf-8') as f:
        json.dump({'rows': rows, 'first_low_step': first_low_step}, f, ensure_ascii=False, indent=2)
    print(f'\n[c031-cos] first step with any tok < 0.99: {first_low_step}', flush=True)
    print(f'[c031-cos] → {out_dir}/growing_audio_cosine.json', flush=True)


if __name__ == '__main__':
    main()
