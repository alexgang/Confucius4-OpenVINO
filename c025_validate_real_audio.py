"""c025_validate_real_audio.py — C-025#3 关键诊断: 真实音频上 OV vs torch encoder

问题: 验证脚本用 torch.randn 合成 mel，cos=1.0，但生产 61-min WER 18.40%
      (vs Hybrid 9.07%)。差异可能来自真实音频的 mel 分布 vs 高斯噪声。
      这一步用真实 600-660s 音频做一次逐窗对比，定位 OV encoder 是否仍坏。
"""
import os, sys, time
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import torch
import torch.nn.functional as F
import openvino as ov
import soundfile as sf

sys.path.insert(0, '.')
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
from backends import extract_audio_features, _qwen3_get_feat_extract_output_lengths

WAV = 'reports/c025/audio_A_600_660.wav'
OUT_DIR = 'models/ov-encoder-window'
OUT_JSON = 'reports/c025_real_audio_validate.json'


def aftercnn_len(n_mel):
    x = n_mel
    for _ in range(3):
        x = (x + 1) // 2
    return x


def torch_encode(window_mel):
    """window_mel: (128, 800) — 单窗 8 chunks 全满. 传给 audio_tower 用 2D shape."""
    with torch.no_grad():
        out = audio_tower(
            input_features=window_mel,  # (128, 800) 2D, qwen_asr 自己处理 batch
            feature_lens=torch.tensor([800], dtype=torch.long),
        ).last_hidden_state
    return out  # (104, 2048)


def ov_encode(window_mel, valid_aftercnn=104):
    win = window_mel if window_mel.shape[1] == 800 else F.pad(window_mel, (0, 800 - window_mel.shape[1]))
    win_in = win.unsqueeze(0).numpy().astype(np.float32)
    cu_in = np.array([0, valid_aftercnn], dtype=np.int32)
    result = compiled([win_in, cu_in])
    return torch.from_numpy(result[0]).squeeze(0)  # (104, 2048)


def main():
    print(f'[c025] loading torch audio_tower ...', flush=True)
    global audio_tower
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()

    print(f'[c025] loading OV window encoder ...', flush=True)
    core = ov.Core()
    ov_model = core.read_model(
        model=os.path.join(OUT_DIR, 'openvino_encoder_model.xml'),
        weights=os.path.join(OUT_DIR, 'openvino_encoder_model.bin'),
    )
    inputs_dict = {}
    for inp in ov_model.inputs:
        name = inp.any_name
        if 'feature' in name.lower() or 'input' in name.lower():
            inputs_dict[name] = [1, 128, 800]
        else:
            inputs_dict[name] = [2]
    ov_model.reshape(inputs_dict)
    global compiled
    compiled = core.compile_model(ov_model, device_name='CPU')
    print(f'[c025] compiled on CPU', flush=True)

    print(f'[c025] loading real audio {WAV} ...', flush=True)
    wav, sr = sf.read(WAV, dtype='float32')
    assert sr == 16000
    feats_real, _, n_real, N_audio = extract_audio_features(
        wrapper.processor.feature_extractor, wav, return_torch=False,
    )
    mel = torch.from_numpy(feats_real[0])  # (128, T_mel)
    print(f'[c025] audio: {n_real} mel frames, N_audio={N_audio}', flush=True)

    n_100_blocks = (n_real + 99) // 100
    n_windows = n_100_blocks // 8
    print(f'[c025] n_100_blocks={n_100_blocks}, n_full_800_windows={n_windows}', flush=True)

    rows = []
    for w in range(n_windows):
        win_mel = mel[:, w*800:(w+1)*800]
        t = torch_encode(win_mel)
        o = ov_encode(win_mel, 104)
        cos = F.cosine_similarity(t, o, dim=-1)
        rows.append({
            'window': w,
            'start_mel': w*800,
            'end_mel': (w+1)*800,
            'cos_mean': cos.mean().item(),
            'cos_min': cos.min().item(),
            'n_low_99': int((cos < 0.99).sum()),
        })
        print(f'[c025] window {w:2d} mel=[{w*800}-{(w+1)*800}] '
              f'cos_mean={cos.mean().item():.6f} cos_min={cos.min().item():.6f} '
              f'n(<0.99)={int((cos<0.99).sum())}', flush=True)

    import json
    summary = {
        'audio': WAV,
        'n_real_mel': n_real,
        'N_audio': N_audio,
        'n_windows': n_windows,
        'cos_mean_avg': sum(r['cos_mean'] for r in rows) / len(rows),
        'cos_min_overall': min(r['cos_min'] for r in rows),
        'n_windows_with_below_99': sum(1 for r in rows if r['cos_min'] < 0.99),
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'summary': summary, 'rows': rows}, f, ensure_ascii=False, indent=2)
    print(f'[c025] summary: {summary}', flush=True)
    print(f'[c025] → {OUT_JSON}', flush=True)


if __name__ == '__main__':
    main()
