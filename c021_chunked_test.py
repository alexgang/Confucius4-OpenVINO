"""c021_chunked_test.py — 验证 option (d): Python 侧 100-mel chunking + OV encoder

Hypothesis: optimum-intel 的 _patch_audio_encoder 把 chunking/cu_seqlens 干掉了，
但**当输入是单个 100-mel chunk** 时（对应 1 个 100-frame chunk 单元），输出与 torch
audio_tower 的单 chunk 输出等价（3 stride-2 convs → 13 aftercnn；position 0-12；
single attention window — 等价于 torch 的 cu_seqlens=[0,13] 单窗口）。

如果验证通过，60s 音频切成 60 个 100-mel 块，60 次 OV encoder，拼接 → 等价于
torch 完整 encoder。
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf
import openvino as ov
import torch

sys.path.insert(0, '.')
from backends import extract_audio_features, SAMPLE_RATE

WAV_IN = 'test_audio/260902_SPE_audio.wav'
MODEL_HF = 'models/hf'
OV_DIR = 'models/ov-int8-past'
DURATIONS = [4, 8, 10, 12, 16, 20, 30, 60]


def load_torch_encoder():
    from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
    wrapper = Qwen3ASRModel.from_pretrained(MODEL_HF, dtype=torch.float32, attn_implementation='eager')
    enc = wrapper.model.thinker.audio_tower
    enc.eval()
    return enc


def load_ov_encoder():
    core = ov.Core()
    m = core.compile_model(os.path.join(OV_DIR, 'openvino_encoder_model.xml'), 'GPU.0')
    return m.create_infer_request()


def torch_encode_full(enc, mel_real, n_real):
    with torch.no_grad():
        x = torch.from_numpy(mel_real).float().squeeze(0)  # (128, T) 2D
        feat_len = torch.tensor([n_real], dtype=torch.long)
        out = enc(input_features=x, feature_lens=feat_len)
    return out.last_hidden_state.cpu().numpy()


def ov_encode_chunked(ov_ir, mel_real):
    """mel_real: (1, 128, T) — split into 100-mel chunks, encode each, concat."""
    _, T = mel_real.shape[1], mel_real.shape[2]
    n_chunks = T // 100
    chunks_out = []
    for i in range(n_chunks):
        chunk = mel_real[:, :, i*100:(i+1)*100].copy()  # (1, 128, 100)
        ov_ir.infer({'input_features': chunk})
        out = ov_ir.get_output_tensor(0).data  # (1, 13, 2048)
        chunks_out.append(out)
    return np.concatenate(chunks_out, axis=1)  # (1, n_chunks*13, 2048)


def cosine_stats(a, b):
    a = a.reshape(-1, a.shape[-1])
    b = b.reshape(-1, b.shape[-1])
    n = min(a.shape[0], b.shape[0])
    a, b = a[:n], b[:n]
    an = a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-8)
    bn = b / (np.linalg.norm(b, axis=-1, keepdims=True) + 1e-8)
    cos = (an * bn).sum(-1)
    return float(cos.mean()), float(cos.min()), n


def main():
    audio, sr = sf.read(WAV_IN)
    audio = audio.astype(np.float32)
    from transformers import WhisperFeatureExtractor
    fe = WhisperFeatureExtractor.from_pretrained(MODEL_HF)

    torch_enc = load_torch_encoder()
    ov_ir = load_ov_encoder()

    print(f"\n{'dur(s)':>6} {'mel':>5} {'torch_D':>8} {'ov_chunk_D':>11} {'cos_mean':>9} {'cos_min':>9} {'ov_ms':>7}")
    print('-' * 65)
    rows = []
    for dur in DURATIONS:
        clip = audio[:dur * SAMPLE_RATE]
        feats_real, _, n_real, N_audio_pred = extract_audio_features(fe, clip)
        # 确保是 100-mel 整数倍
        T_use = (n_real // 100) * 100
        feats_real = feats_real[:, :, :T_use]

        # torch (整段)
        t0 = time.perf_counter()
        torch_ehs = torch_encode_full(torch_enc, feats_real, T_use)
        torch_ms = (time.perf_counter() - t0) * 1000

        # OV chunked
        t0 = time.perf_counter()
        ov_ehs = ov_encode_chunked(ov_ir, feats_real)
        ov_ms = (time.perf_counter() - t0) * 1000

        cos_mean, cos_min, n = cosine_stats(torch_ehs, ov_ehs)
        print(f'{dur:>6} {T_use:>5} {torch_ehs.shape[0]:>8} {ov_ehs.shape[1]:>11} '
              f'{cos_mean:>9.4f} {cos_min:>9.4f} {ov_ms:>7.1f}  '
              f'(torch {torch_ms:.0f}ms)', flush=True)
        rows.append({
            'dur_s': dur, 'T_mel': T_use, 'N_audio_pred': N_audio_pred,
            'torch_D': int(torch_ehs.shape[0]), 'ov_chunk_D': int(ov_ehs.shape[1]),
            'cos_mean': round(cos_mean, 4), 'cos_min': round(cos_min, 4),
            'ov_chunked_ms': round(ov_ms, 1), 'torch_full_ms': round(torch_ms, 1),
        })

    with open('reports/c021_chunked_test.json', 'w', encoding='utf-8') as f:
        json.dump({'rows': rows}, f, ensure_ascii=False, indent=2)
    print('\n[done] → reports/c021_chunked_test.json')


if __name__ == '__main__':
    main()
