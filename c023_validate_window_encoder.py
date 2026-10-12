"""c023_validate_window_encoder.py — C-023#3: 验证 OV 窗口 encoder vs torch audio_tower
对 4/8/10/12/16/20/30/60 s 片段，torch audio_tower vs OV 单窗口 IR：
- token 数对比
- 逐 token cosine (mean/min)
要求：token 数一致，cos mean > 0.99，min > 0.95
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import torch
import torch.nn.functional as F
import numpy as np
import openvino as ov

sys.path.insert(0, '.')
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel

OUT_DIR = 'models/ov-encoder-window'
OUT_JSON = 'reports/c023_encoder_validate.json'


def aftercnn_len(n_mel: int) -> int:
    """qwen3_get_feat_extract_output_lengths: 3 stride-2 convs"""
    # 1 conv: ceil(n/2) = (n+1)//2 ; 2 conv: ceil(((n+1)//2 + 1)//2) = ...
    # actually _get_feat_extract_output_lengths((n+1)//2 //2 //2)
    # Let's just replicate: x = n; x = (x+1)//2; x = (x+1)//2; x = (x+1)//2
    x = n_mel
    for _ in range(3):
        x = (x + 1) // 2
    return x


def main():
    print('[c023v] loading torch audio_tower ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()

    print('[c023v] loading OV window encoder ...', flush=True)
    core = ov.Core()
    use_fp32 = os.environ.get('OV_FP32', '0') == '1'
    xml_name = 'openvino_encoder_model_fp32.xml' if use_fp32 else 'openvino_encoder_model.xml'
    bin_name = 'openvino_encoder_model_fp32.bin' if use_fp32 else 'openvino_encoder_model.bin'
    ov_model = core.read_model(
        model=os.path.join(OUT_DIR, xml_name),
        weights=os.path.join(OUT_DIR, bin_name),
    )
    # 静态 shape
    inputs_dict = {}
    for inp in ov_model.inputs:
        name = inp.any_name
        if 'feature' in name.lower() or 'input' in name.lower():
            inputs_dict[name] = [1, 128, 800]
        else:
            inputs_dict[name] = [2]  # cu_seqlens 长度固定为 2
    ov_model.reshape(inputs_dict)
    compiled = core.compile_model(ov_model, device_name='CPU')  # CPU first for reproducibility
    print(f'[c023v] compiled on CPU (FP32={use_fp32})', flush=True)

    durations = [4, 8, 10, 12, 16, 20, 30, 60]
    rows = []
    for dur in durations:
        n_mel = dur * 80  # 16kHz / hop 160 = 80 frames/sec → n_mel = dur*80
        n_windows = (n_mel + 799) // 800
        torch.manual_seed(dur)
        mel = torch.randn(128, n_mel)  # 不 pad，torch audio_tower 自己处理

        # torch audio_tower on raw mel
        with torch.no_grad():
            torch_out = audio_tower(
                input_features=mel,
                feature_lens=torch.tensor([n_mel], dtype=torch.long),
            ).last_hidden_state
        torch_n = torch_out.shape[0]

        # OV encoder: pad mel to multiple of 100, then pack 8 chunks (=800 frames) per IR call
        # Each 100-mel chunk = 13 aftercnn tokens, last chunk of last window may have <13 valid
        n_100_blocks = (n_mel + 99) // 100
        # pad mel to n_100_blocks * 100
        if n_100_blocks * 100 > n_mel:
            mel_padded = torch.nn.functional.pad(mel, (0, n_100_blocks*100 - n_mel))
        else:
            mel_padded = mel
        # Group every 8 chunks into one window
        n_windows_v2 = (n_100_blocks + 7) // 8
        ov_chunks = []
        for w in range(n_windows_v2):
            blk_start = w * 800
            valid_mel_in_window = min(800, n_mel - blk_start)  # 真实 mel 长度（不含 padding）
            if valid_mel_in_window <= 0:
                break
            # 用 mel（不是 mel_padded）取真实 mel 切片，再补零到 800
            win = mel[:, blk_start:blk_start + valid_mel_in_window]
            # valid_aftercnn for this window: for each 100-mel chunk in window, 13 tokens; last chunk may have <13
            win_n_100 = (valid_mel_in_window + 99) // 100
            if valid_mel_in_window % 100 == 0:
                valid_aftercnn = win_n_100 * 13
            else:
                valid_aftercnn = (win_n_100 - 1) * 13 + aftercnn_len(valid_mel_in_window - (win_n_100 - 1) * 100)
            # Pad win to 800
            if win.shape[1] < 800:
                win = torch.nn.functional.pad(win, (0, 800 - win.shape[1]))
            win_in = win.unsqueeze(0).numpy().astype(np.float32)
            cu_in = np.array([0, valid_aftercnn], dtype=np.int32)
            result = compiled([win_in, cu_in])
            out = torch.from_numpy(result[0]).squeeze(0)  # (104, 2048)
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
        print(f'[c023v] dur={dur}s n_mel={n_mel} n_windows={n_windows} '
              f'torch_n={torch_n} ov_n={ov_out.shape[0]} '
              f'cos_mean={cos_mean:.6f} cos_min={cos_min:.6f}', flush=True)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'rows': rows}, f, ensure_ascii=False, indent=2)
    print(f'[c023v] → {OUT_JSON}', flush=True)
    # Summary
    all_pass = all(r['n_match'] and r['cos_mean'] > 0.99 and r['cos_min'] > 0.95 for r in rows)
    print(f'[c023v] ALL PASS (n_match + cos>0.99 mean + cos>0.95 min) = {all_pass}', flush=True)


if __name__ == '__main__':
    main()
