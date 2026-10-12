"""c021_encoder_compare.py — C-021#1 验证：4/8/10/12/16/20/30/60s 片段

对比 torch `model.thinker.audio_tower` (FP32) vs OV encoder IR (FP16 + INT8)。
打印：n_real_mel, N_audio, encoder 输出 shape，逐 token cosine (mean/min)。

预期：≤ 8 s 时 cosine > 0.99；> 8 s 时明显下降（OV IR 把 chunking/cu_seqlens
trace 时固化了）。
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf
import openvino as ov
import torch

sys.path.insert(0, '.')
from backends import extract_audio_features, SAMPLE_RATE, _qwen3_get_feat_extract_output_lengths

WAV_IN = 'test_audio/<redacted>.wav'
MODEL_HF = 'models/hf'
OV_FP16 = 'models/ov-int8-past'  # shape-wise same encoder; reuse for cosine
DURATIONS = [4, 8, 10, 12, 16, 20, 30, 60]


def load_torch_encoder():
    print('[torch] loading ...', flush=True)
    from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
    wrapper = Qwen3ASRModel.from_pretrained(
        MODEL_HF, dtype=torch.float32, attn_implementation='eager',
    )
    enc = wrapper.model.thinker.audio_tower
    enc.eval()
    return enc


def load_ov_encoder(model_dir):
    print(f'[ov] loading {model_dir} ...', flush=True)
    core = ov.Core()
    m = core.compile_model(os.path.join(model_dir, 'openvino_encoder_model.xml'), 'GPU.0')
    ir = m.create_infer_request()
    return ir


def torch_encode(enc, mel_real, n_real):
    """mel_real: numpy (1, 128, T_real)  ->  ehs numpy (1, T_audio, 2048)

    audio_tower.forward expects 2D (n_mels, n_frames) — see qwen_asr's
    get_audio_features which slices per-sample and feeds the encoder unbatched.
    OV encoder IR accepts 3D (1, n_mels, n_frames) — the IR was traced with
    the chunking/cu_seqlens logic folded in.
    """
    with torch.no_grad():
        x = torch.from_numpy(mel_real).float().squeeze(0)  # (128, T_real) 2D
        feat_len = torch.tensor([n_real], dtype=torch.long)
        out = enc(input_features=x, feature_lens=feat_len)
    return out.last_hidden_state.cpu().numpy()


def ov_encode(enc_ir, mel_real):
    """mel_real: numpy (1, 128, T_real)  ->  ehs numpy (1, T_audio, 2048)"""
    enc_ir.infer({'input_features': mel_real})
    return enc_ir.get_output_tensor(0).data


def cosine_stats(a, b):
    """a, b: (T, D)"""
    a = a.reshape(-1, a.shape[-1])
    b = b.reshape(-1, b.shape[-1])
    n = min(a.shape[0], b.shape[0])
    if n == 0:
        return float('nan'), float('nan'), 0
    a, b = a[:n], b[:n]
    an = a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-8)
    bn = b / (np.linalg.norm(b, axis=-1, keepdims=True) + 1e-8)
    cos = (an * bn).sum(-1)  # (n,)
    return float(cos.mean()), float(cos.min()), n


def main():
    audio, sr = sf.read(WAV_IN)
    assert sr == SAMPLE_RATE
    audio = audio.astype(np.float32)

    # 公共：feature extractor
    from transformers import WhisperFeatureExtractor
    fe = WhisperFeatureExtractor.from_pretrained(MODEL_HF)
    print(f'[fe] {fe.feature_size}-mel, n_fft={fe.n_fft}, hop={fe.hop_length}', flush=True)

    torch_enc = load_torch_encoder()
    ov_int8 = load_ov_encoder(OV_FP16)

    rows = []
    for dur in DURATIONS:
        clip = audio[:dur * SAMPLE_RATE]
        feats_real, mask_real, n_real, N_audio_pred = extract_audio_features(fe, clip)
        print(f'\n[dur={dur}s] n_real_mel={n_real} N_audio_pred={N_audio_pred} '
              f'mel_shape={feats_real.shape}', flush=True)

        # 1) torch encoder
        t0 = time.perf_counter()
        torch_ehs = torch_encode(torch_enc, feats_real, n_real)
        torch_t = time.perf_counter() - t0
        print(f'  torch  ehs.shape={torch_ehs.shape} wall={torch_t*1000:.1f}ms', flush=True)

        # 2) OV encoder (warm-up 1st)
        ov_ehs = ov_encode(ov_int8, feats_real)
        t0 = time.perf_counter()
        ov_ehs = ov_encode(ov_int8, feats_real)
        ov_t = time.perf_counter() - t0
        print(f'  ov     ehs.shape={ov_ehs.shape}  wall={ov_t*1000:.1f}ms', flush=True)

        # 3) cosine
        cos_mean, cos_min, n = cosine_stats(torch_ehs, ov_ehs)
        print(f'  cosine (n={n}) mean={cos_mean:.4f} min={cos_min:.4f}', flush=True)

        rows.append({
            'dur_s': dur, 'n_real_mel': n_real, 'N_audio_pred': N_audio_pred,
            'torch_shape': list(torch_ehs.shape), 'ov_shape': list(ov_ehs.shape),
            'torch_wall_ms': round(torch_t*1000, 1), 'ov_wall_ms': round(ov_t*1000, 1),
            'cos_mean': round(cos_mean, 4), 'cos_min': round(cos_min, 4), 'cos_n': n,
        })

    out_path = 'reports/c021_encoder_compare.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'rows': rows, 'model_ov': OV_FP16}, f, ensure_ascii=False, indent=2)
    print(f'\n[done] → {out_path}', flush=True)

    # 打印表格
    print('\n' + '=' * 100)
    print(f'{"dur(s)":>6} {"mel":>5} {"N_pred":>6} {"torch T":>8} {"torch D":>5} '
          f'{"ov T":>5} {"ov D":>5} {"cos_mean":>9} {"cos_min":>9}')
    print('-' * 100)
    for r in rows:
        print(f'{r["dur_s"]:>6} {r["n_real_mel"]:>5} {r["N_audio_pred"]:>6} '
              f'{r["torch_wall_ms"]:>8.1f} {r["torch_shape"][1]:>5} '
              f'{r["ov_shape"][1]:>5} {r["ov_shape"][1]:>5} '
              f'{r["cos_mean"]:>9.4f} {r["cos_min"]:>9.4f}')


if __name__ == '__main__':
    main()
