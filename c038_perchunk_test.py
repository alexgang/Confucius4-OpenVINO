"""c038_perchunk_test.py — Test per-chunk vs full attention for partial windows
Test 160/320/400/500/600/700/800 mel single partial windows
- audio_tower (per-chunk attention)
- v1 IR (full attention within window)
- v2 IR (with my padded mask + full attention)
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


def valid_aftercnn_for_mel(mel_len):
    """Compute valid_aftercnn for a given mel length (single window partial)."""
    n_100 = mel_len // 100
    rem = mel_len - n_100 * 100
    if rem == 0:
        return n_100 * 13
    return n_100 * 13 + aftercnn_len(rem)


def main():
    print(f'[c038-pc] loading model ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()

    core = ov.Core()
    ov_v1 = core.read_model(
        'models/ov-encoder-window/openvino_encoder_model.xml',
        'models/ov-encoder-window/openvino_encoder_model.bin',
    )
    for inp in ov_v1.inputs:
        n = inp.any_name
        ov_v1.reshape({n: [1, 128, 800] if 'feature' in n.lower() or 'input' in n.lower() else [2]})
    compiled_v1 = core.compile_model(ov_v1, device_name='CPU')

    ov_v2 = core.read_model(
        'models/ov-encoder-window-v2/openvino_encoder_model.xml',
        'models/ov-encoder-window-v2/openvino_encoder_model.bin',
    )
    for inp in ov_v2.inputs:
        n = inp.any_name
        ov_v2.reshape({n: [1, 128, 800] if 'feature' in n.lower() or 'input' in n.lower() else [2]})
    compiled_v2 = core.compile_model(ov_v2, device_name='CPU')

    sizes = [100, 200, 320, 400, 500, 600, 700, 800]
    print(f'\n=== Single partial window test ===', flush=True)
    print(f'{"n_mel":>5} {"v_aftercnn":>10} {"v1_cos_min":>12} {"v2_cos_min":>12} {"diff":>8}', flush=True)
    for n_mel in sizes:
        torch.manual_seed(n_mel)
        mel = torch.randn(128, n_mel)
        va = valid_aftercnn_for_mel(n_mel)

        # audio_tower
        with torch.no_grad():
            out_a = audio_tower(
                input_features=mel, feature_lens=torch.tensor([n_mel], dtype=torch.long),
            ).last_hidden_state

        # v1 IR
        win = F.pad(mel, (0, 800 - n_mel)) if n_mel < 800 else mel[:, :800]
        win_in = win.unsqueeze(0).numpy().astype(np.float32)
        cu = np.array([0, va], dtype=np.int32)
        out_v1 = torch.from_numpy(compiled_v1([win_in, cu])[0]).squeeze(0)[:va]
        out_v2 = torch.from_numpy(compiled_v2([win_in, cu])[0]).squeeze(0)[:va]
        cos_v1 = F.cosine_similarity(out_a, out_v1, dim=-1).min().item()
        cos_v2 = F.cosine_similarity(out_a, out_v2, dim=-1).min().item()
        print(f'{n_mel:>5} {va:>10} {cos_v1:>12.6f} {cos_v2:>12.6f} {cos_v2 - cos_v1:>+8.4f}', flush=True)


if __name__ == '__main__':
    main()
