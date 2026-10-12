"""c038_multiwindow_debug.py — Reproduce c023v2_validate 12s case step by step

The 12s validation does:
- audio_tower(960) → 125 tokens
- c023(800) + c023(160) → 104 + 21 = 125 tokens (concatenated)

But c038_perchunk shows single 800/160 windows match audio_tower at cos=1.0.
So 0.93 must come from concatenation or comparison issue.
"""
import os, sys
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import torch
import torch.nn.functional as F
import numpy as np
import openvino as ov

sys.path.insert(0, '.')
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel


def aftercnn_len(n):
    x = n
    for _ in range(3):
        x = (x + 1) // 2
    return x


def main():
    print(f'[c038-multi] loading ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()

    core = ov.Core()
    ov_v2 = core.read_model(
        'models/ov-encoder-window-v2/openvino_encoder_model.xml',
        'models/ov-encoder-window-v2/openvino_encoder_model.bin',
    )
    for inp in ov_v2.inputs:
        n = inp.any_name
        ov_v2.reshape({n: [1, 128, 800] if 'feature' in n.lower() or 'input' in n.lower() else [2]})
    compiled_v2 = core.compile_model(ov_v2, device_name='CPU')

    n_mel = 960
    torch.manual_seed(12)
    mel = torch.randn(128, n_mel)

    # Path A: audio_tower(960) → 125 tokens
    with torch.no_grad():
        torch_out = audio_tower(
            input_features=mel, feature_lens=torch.tensor([n_mel], dtype=torch.long),
        ).last_hidden_state
    print(f'[c038-multi] audio_tower(960) output: {torch_out.shape}', flush=True)

    # Path B: c023(800) + c023(160) = 104 + 21
    win1 = mel[:, 0:800]
    win2 = mel[:, 800:960]  # 160 frames
    cu1 = np.array([0, 104], dtype=np.int32)
    cu2 = np.array([0, 21], dtype=np.int32)
    win1_in = win1.unsqueeze(0).numpy().astype(np.float32)
    win2_padded = F.pad(win2, (0, 800 - 160)) if win2.shape[1] < 800 else win2
    win2_in = win2_padded.unsqueeze(0).numpy().astype(np.float32)

    out_b1 = torch.from_numpy(compiled_v2([win1_in, cu1])[0]).squeeze(0)[:104]
    out_b2 = torch.from_numpy(compiled_v2([win2_in, cu2])[0]).squeeze(0)[:21]
    print(f'[c038-multi] c023 window 1 output: {out_b1.shape}', flush=True)
    print(f'[c038-multi] c023 window 2 output: {out_b2.shape}', flush=True)

    # Per-window cos
    cos_w1 = F.cosine_similarity(torch_out[:104], out_b1, dim=-1)
    cos_w2 = F.cosine_similarity(torch_out[104:125], out_b2, dim=-1)
    print(f'[c038-multi] window 1 (800 mel): cos_min={cos_w1.min().item():.6f} cos_mean={cos_w1.mean().item():.6f}', flush=True)
    print(f'[c038-multi] window 2 (160 mel): cos_min={cos_w2.min().item():.6f} cos_mean={cos_w2.mean().item():.6f}', flush=True)

    # Combined
    out_b = torch.cat([out_b1, out_b2], dim=0)
    cos_all = F.cosine_similarity(torch_out, out_b, dim=-1)
    print(f'[c038-multi] combined: cos_min={cos_all.min().item():.6f} cos_mean={cos_all.mean().item():.6f}', flush=True)
    print(f'[c038-multi] argmin={int(cos_all.argmin().item())}, per-token cos last 30:', flush=True)
    for i, c in enumerate(cos_all[-30:].tolist()):
        print(f'  token {104+i} (window 2): cos={c:.4f}', flush=True)

    # Also test what audio_tower(800) and audio_tower(160) give for comparison
    with torch.no_grad():
        torch_out_800 = audio_tower(
            input_features=mel[:, :800], feature_lens=torch.tensor([800], dtype=torch.long),
        ).last_hidden_state
        torch_out_160 = audio_tower(
            input_features=mel[:, 800:960], feature_lens=torch.tensor([160], dtype=torch.long),
        ).last_hidden_state
    cos_w1_at = F.cosine_similarity(torch_out_800, out_b1, dim=-1)
    cos_w2_at = F.cosine_similarity(torch_out_160, out_b2, dim=-1)
    print(f'[c038-multi] c023(800) vs audio_tower(800): cos_min={cos_w1_at.min().item():.6f}', flush=True)
    print(f'[c038-multi] c023(160) vs audio_tower(160): cos_min={cos_w2_at.min().item():.6f}', flush=True)

    cos_w1_at_960 = F.cosine_similarity(torch_out[:104], torch_out_800, dim=-1)
    print(f'[c038-multi] audio_tower(960)[:104] vs audio_tower(800): cos_min={cos_w1_at_960.min().item():.6f}', flush=True)


if __name__ == '__main__':
    main()
