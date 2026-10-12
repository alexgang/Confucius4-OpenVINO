"""c023v2_validate.py — C-038#2: 验证 v2 IR (有 padded mask) 在 4/8/.../60s 的 cos

对比 c023 v1 (models/ov-encoder-window) vs c023 v2 (models/ov-encoder-window-v2)
- v1 partial case 12s min cos 0.93 (c025 报告)
- v2 partial case 12s min cos 应该 0.99+

输出 reports/c023v2_validate.json
"""
import os, sys, time, json, argparse
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import torch
import torch.nn.functional as F
import numpy as np
import openvino as ov

sys.path.insert(0, '.')
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel

OUT_JSON = 'reports/c023v2_validate.json'


def aftercnn_len(n_mel: int) -> int:
    x = n_mel
    for _ in range(3):
        x = (x + 1) // 2
    return x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--encoder-dir', type=str, required=True,
                        help='OV encoder IR 目录')
    parser.add_argument('--tag', type=str, required=True,
                        help='标签 (v1 或 v2) — 用于报告标识')
    args = parser.parse_args()

    print(f'[c023v2] loading torch audio_tower ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()

    print(f'[c023v2] loading OV encoder from {args.encoder_dir} ...', flush=True)
    core = ov.Core()
    ov_model = core.read_model(
        model=os.path.join(args.encoder_dir, 'openvino_encoder_model.xml'),
        weights=os.path.join(args.encoder_dir, 'openvino_encoder_model.bin'),
    )
    inputs_dict = {}
    for inp in ov_model.inputs:
        name = inp.any_name
        if 'feature' in name.lower() or 'input' in name.lower():
            inputs_dict[name] = [1, 128, 800]
        else:
            inputs_dict[name] = [2]
    ov_model.reshape(inputs_dict)
    compiled = core.compile_model(ov_model, device_name='CPU')
    print(f'[c023v2] compiled on CPU', flush=True)

    durations = [4, 8, 10, 12, 16, 20, 30, 60]
    rows = []
    for dur in durations:
        n_mel = dur * 80
        n_windows = (n_mel + 799) // 800
        torch.manual_seed(dur)
        mel = torch.randn(128, n_mel)

        with torch.no_grad():
            torch_out = audio_tower(
                input_features=mel,
                feature_lens=torch.tensor([n_mel], dtype=torch.long),
            ).last_hidden_state
        torch_n = torch_out.shape[0]

        n_100_blocks = (n_mel + 99) // 100
        if n_100_blocks * 100 > n_mel:
            mel_padded = torch.nn.functional.pad(mel, (0, n_100_blocks*100 - n_mel))
        else:
            mel_padded = mel
        n_windows_v2 = (n_100_blocks + 7) // 8
        ov_chunks = []
        for w in range(n_windows_v2):
            blk_start = w * 800
            valid_mel_in_window = min(800, n_mel - blk_start)
            if valid_mel_in_window <= 0:
                break
            win = mel[:, blk_start:blk_start + valid_mel_in_window]
            win_n_100 = (valid_mel_in_window + 99) // 100
            if valid_mel_in_window % 100 == 0:
                valid_aftercnn = win_n_100 * 13
            else:
                valid_aftercnn = (win_n_100 - 1) * 13 + aftercnn_len(
                    valid_mel_in_window - (win_n_100 - 1) * 100
                )
            if win.shape[1] < 800:
                win = torch.nn.functional.pad(win, (0, 800 - win.shape[1]))
            win_in = win.unsqueeze(0).numpy().astype(np.float32)
            cu_in = np.array([0, valid_aftercnn], dtype=np.int32)
            result = compiled([win_in, cu_in])
            out = torch.from_numpy(result[0]).squeeze(0)
            out = out[:valid_aftercnn]
            ov_chunks.append(out)
        ov_out = torch.cat(ov_chunks, dim=0)

        cos = F.cosine_similarity(torch_out, ov_out, dim=-1)
        cos_mean = cos.mean().item()
        cos_min = cos.min().item()
        rows.append({
            'dur_s': dur,
            'n_mel': n_mel,
            'n_windows': n_windows,
            'torch_n': torch_n,
            'ov_n': ov_out.shape[0],
            'n_match': torch_n == ov_out.shape[0],
            'cos_mean': cos_mean,
            'cos_min': cos_min,
        })
        print(f'[c023v2] dur={dur}s n_mel={n_mel} n_windows={n_windows} '
              f'torch_n={torch_n} ov_n={ov_out.shape[0]} '
              f'cos_mean={cos_mean:.6f} cos_min={cos_min:.6f}', flush=True)

    report = {'tag': args.tag, 'encoder_dir': args.encoder_dir, 'rows': rows}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'[c023v2] → {OUT_JSON}', flush=True)

    all_pass = all(r['n_match'] and r['cos_mean'] > 0.99 and r['cos_min'] > 0.95
                   for r in rows)
    print(f'[c023v2] {args.tag} ALL PASS = {all_pass}', flush=True)


if __name__ == '__main__':
    main()
