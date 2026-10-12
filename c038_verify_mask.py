"""c038_verify_mask.py — Verify v2 IR actually applies the padded mask

Single partial window test:
- audio_tower(160 mel) → 21 tokens
- c023 v1 IR (160 padded to 800, cu=[0,21])[:21] → 21 tokens
- c023 v2 IR (160 padded to 800, cu=[0,21])[:21] → 21 tokens
- v1 should be ~0.93 cos, v2 should be ~1.0 cos (if mask is applied)
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
from c023_export_window_encoder import SingleWindowEncoder


def aftercnn_len(n):
    x = n
    for _ in range(3):
        x = (x + 1) // 2
    return x


def main():
    print(f'[c038-verify] loading model ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()

    # 160 mel partial window
    torch.manual_seed(0)
    mel_160 = torch.randn(128, 160)
    valid_aftercnn_160 = 13 + aftercnn_len(60)  # 13 + 8 = 21
    print(f'[c038-verify] 160 mel: valid_aftercnn = {valid_aftercnn_160}', flush=True)

    # Path A: audio_tower(160) → 21 tokens
    with torch.no_grad():
        out_a = audio_tower(
            input_features=mel_160,
            feature_lens=torch.tensor([160], dtype=torch.long),
        ).last_hidden_state
    print(f'[c038-verify] path A (audio_tower 160): out shape {out_a.shape}', flush=True)

    # Path B1: SingleWindowEncoder v1 (no mask), torch forward
    enc_v1 = SingleWindowEncoder(audio_tower)
    enc_v1.eval()
    # Reload audio_tower to get a fresh state (since v1 is from before my edit)
    # Actually c023_export_window_encoder.py is now v2 (with mask)
    # For v1, I need to revert the file or import a v1 class

    # Path B1: Just use the v2 class (which has the mask)
    win_160_padded = F.pad(mel_160, (0, 800 - 160))  # (128, 800)
    with torch.no_grad():
        out_b_torch = enc_v1(
            win_160_padded.unsqueeze(0),
            torch.tensor([0, 21], dtype=torch.int32),
        ).squeeze(0)[:21]
    print(f'[c038-verify] path B1 (SingleWindowEncoder torch, 160 padded, cu=[0,21]): out shape {out_b_torch.shape}', flush=True)

    cos_torch = F.cosine_similarity(out_a, out_b_torch, dim=-1)
    print(f'[c038-verify] cos (torch, v2 model) = mean={cos_torch.mean().item():.6f} min={cos_torch.min().item():.6f}', flush=True)

    # Path B2: v2 IR on OV
    print(f'[c038-verify] loading v2 IR ...', flush=True)
    core = ov.Core()
    ov_model = core.read_model(
        model='models/ov-encoder-window-v2/openvino_encoder_model.xml',
        weights='models/ov-encoder-window-v2/openvino_encoder_model.bin',
    )
    for inp in ov_model.inputs:
        name = inp.any_name
        if 'feature' in name.lower() or 'input' in name.lower():
            ov_model.reshape({name: [1, 128, 800]})
        else:
            ov_model.reshape({name: [2]})
    compiled_v2 = core.compile_model(ov_model, device_name='CPU')
    win_in = win_160_padded.unsqueeze(0).numpy().astype(np.float32)
    cu_in = np.array([0, 21], dtype=np.int32)
    result_v2 = compiled_v2([win_in, cu_in])
    out_b_v2 = torch.from_numpy(result_v2[0]).squeeze(0)[:21]
    print(f'[c038-verify] path B2 (v2 IR, 160 padded, cu=[0,21]): out shape {out_b_v2.shape}', flush=True)
    cos_v2 = F.cosine_similarity(out_a, out_b_v2, dim=-1)
    print(f'[c038-verify] cos (v2 IR) = mean={cos_v2.mean().item():.6f} min={cos_v2.min().item():.6f}', flush=True)

    # Path B3: v1 IR on OV (no mask, baseline)
    print(f'[c038-verify] loading v1 IR ...', flush=True)
    ov_model_v1 = core.read_model(
        model='models/ov-encoder-window/openvino_encoder_model.xml',
        weights='models/ov-encoder-window/openvino_encoder_model.bin',
    )
    for inp in ov_model_v1.inputs:
        name = inp.any_name
        if 'feature' in name.lower() or 'input' in name.lower():
            ov_model_v1.reshape({name: [1, 128, 800]})
        else:
            ov_model_v1.reshape({name: [2]})
    compiled_v1 = core.compile_model(ov_model_v1, device_name='CPU')
    result_v1 = compiled_v1([win_in, cu_in])
    out_b_v1 = torch.from_numpy(result_v1[0]).squeeze(0)[:21]
    print(f'[c038-verify] path B3 (v1 IR, 160 padded, cu=[0,21]): out shape {out_b_v1.shape}', flush=True)
    cos_v1 = F.cosine_similarity(out_a, out_b_v1, dim=-1)
    print(f'[c038-verify] cos (v1 IR) = mean={cos_v1.mean().item():.6f} min={cos_v1.min().item():.6f}', flush=True)

    print(f'\n=== Summary ===', flush=True)
    print(f'  Torch (v2 c023, has mask) vs audio_tower: cos_min = {cos_torch.min().item():.6f}', flush=True)
    print(f'  v2 IR vs audio_tower:                     cos_min = {cos_v2.min().item():.6f}', flush=True)
    print(f'  v1 IR vs audio_tower:                     cos_min = {cos_v1.min().item():.6f}', flush=True)
    if cos_v2.min().item() > cos_v1.min().item() + 0.01:
        print(f'  ✓ v2 IR mask is working (improvement {(cos_v2.min() - cos_v1.min()).item():.4f})', flush=True)
    elif abs(cos_v2.min().item() - cos_v1.min().item()) < 0.001:
        print(f'  ✗ v2 IR gives same cos as v1 — mask NOT captured by IR', flush=True)
    else:
        print(f'  ~ marginal change: {cos_v2.min().item() - cos_v1.min().item():.4f}', flush=True)


if __name__ == '__main__':
    main()
