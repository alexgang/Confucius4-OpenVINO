"""c037c_layerwise_correct.py — 修正 c037 的 hook 覆盖 bug

c037 的问题: audio_tower 和 SingleWindowEncoder 共享 conv2d1 module,
path A 的 hook 会被 path B 覆盖. 修正: 用两份独立的 audio_tower state.

方法: 对每个 hook 点分别跑 path A 和 path B, 每次跑前清除 hooks.
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import copy
import numpy as np
import torch
import torch.nn.functional as F
import soundfile as sf

sys.path.insert(0, '.')
from c023_export_window_encoder import SingleWindowEncoder
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
from backends import extract_audio_features

WAV = 'reports/c025/audio_A_600_660.wav'
OUT_JSON = 'reports/c037c_layerwise_correct.json'


def aftercnn_len(n_mel):
    x = n_mel
    for _ in range(3):
        x = (x + 1) // 2
    return x


def load_tower():
    """每次 load 一份独立的 audio_tower (避免共享 module + hook 覆盖)"""
    wrapper = Qwen3ASRModel.from_pretrained('models/hf', dtype=torch.float32, attn_implementation='eager')
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()
    return audio_tower


def capture_layer_outputs(audio_tower, input_forward, hooks_to_register, return_final=True):
    """Run forward with hooks, return {name: tensor} for each hook + optionally final output"""
    captured = {}
    handles = []
    for name, mod in hooks_to_register:
        def make_h(n):
            def h(_m, _i, o):
                if isinstance(o, tuple):
                    captured[n] = o[0].detach().clone()
                else:
                    captured[n] = o.detach().clone()
            return h
        h = mod.register_forward_hook(make_h(name))
        handles.append(h)
    final = input_forward()
    for h in handles:
        h.remove()
    if return_final:
        return captured, final
    return captured


def main():
    print(f'[c037c] loading model', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained('models/hf', dtype=torch.float32, attn_implementation='eager')
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()
    print(f'  n_window={audio_tower.n_window}, n_window_infer={audio_tower.n_window_infer}', flush=True)

    # 9.6s 真实音频
    wav, _ = sf.read(WAV, dtype='float32', frames=int(9.6 * 16000))
    feats, _, n_96, _ = extract_audio_features(
        wrapper.processor.feature_extractor, wav, return_torch=False,
    )
    mel_96 = torch.from_numpy(feats[0])  # (128, 960)
    print(f'  mel_96: {mel_96.shape}', flush=True)
    assert n_96 == 960

    # SingleWindowEncoder on first 800 frames
    enc = SingleWindowEncoder(audio_tower)
    enc.eval()

    # 各个 hook 点 (name, audio_tower_mod, enc_mod)
    layer_specs = [
        ('after_conv2d1', audio_tower.conv2d1, enc.conv2d1),
        ('after_conv2d2', audio_tower.conv2d2, enc.conv2d2),
        ('after_conv2d3', audio_tower.conv2d3, enc.conv2d3),
        ('after_conv_out', audio_tower.conv_out, enc.conv_out),
        ('after_layer0',  audio_tower.layers[0],  enc.layers[0]),
        ('after_layer11', audio_tower.layers[11], enc.layers[11]),
        ('after_layer23', audio_tower.layers[23], enc.layers[23]),
        ('after_ln_post', audio_tower.ln_post, enc.ln_post),
        ('after_proj1',   audio_tower.proj1,   enc.proj1),
        ('after_proj2',   audio_tower.proj2,   enc.proj2),
    ]

    report = {'n_mel': 960, 'window_a': 800}

    # 对每个 hook 点分别跑 path A 和 path B
    final_a = final_b = None
    for name, mod_a, mod_b in layer_specs:
        # === Path A: audio_tower on full 960 frames, hook at this layer ===
        def make_path_a_fwd():
            def fwd():
                with torch.no_grad():
                    return audio_tower(
                        input_features=mel_96,
                        feature_lens=torch.tensor([960], dtype=torch.long),
                    ).last_hidden_state
            return fwd
        cap_a, final_a = capture_layer_outputs(
            audio_tower, make_path_a_fwd(), [(name, mod_a)]
        )

        # === Path B: SingleWindowEncoder on first 800 frames, hook at this layer ===
        def make_path_b_fwd():
            def fwd():
                with torch.no_grad():
                    return enc(
                        input_features=mel_96[:, 0:800].unsqueeze(0),
                        cu_seqlens=torch.tensor([0, 104], dtype=torch.int32),
                    ).squeeze(0)[:104]
            return fwd
        cap_b, final_b = capture_layer_outputs(
            audio_tower, make_path_b_fwd(), [(name, mod_b)]
        )

        # 比较: path A 的 hook 输出 (前 104 tokens / 前 8 chunks 视情况) vs path B 的 hook 输出
        out_a = cap_a.get(name)
        out_b = cap_b.get(name)
        if out_a is None or out_b is None:
            print(f'  {name:20s} SKIP (no capture)', flush=True)
            continue

        # 比较策略: flatten 成 (-1, last_dim), 然后做逐"行" cos
        flat_a = out_a.reshape(-1, out_a.shape[-1])
        flat_b = out_b.reshape(-1, out_b.shape[-1])
        n_a = flat_a.shape[0]
        n_b = flat_b.shape[0]

        # 取前 min(n_a, n_b) 行, 并标记出"等价部分"大小
        n_min = min(n_a, n_b)
        if n_min > 0:
            cos = F.cosine_similarity(flat_a[:n_min], flat_b[:n_min], dim=-1)
            cos_mean = cos.mean().item()
            cos_min = cos.min().item()
            abs_diff = (flat_a[:n_min] - flat_b[:n_min]).abs()
            abs_diff_max = abs_diff.max().item()
        else:
            cos_mean = cos_min = abs_diff_max = 0.0

        report[name] = {
            'shape_a': list(out_a.shape),
            'shape_b': list(out_b.shape),
            'n_rows_a': n_a,
            'n_rows_b': n_b,
            'n_compared': n_min,
            'cos_mean': cos_mean,
            'cos_min': cos_min,
            'abs_diff_max': abs_diff_max,
        }
        marker = ' [DIVERGE]' if cos_min < 0.99 else ''
        print(f'  {name:20s} A:{list(out_a.shape)} B:{list(out_b.shape)} '
              f'cos_mean={cos_mean:.6f} cos_min={cos_min:.6f}{marker}', flush=True)

    # === Final output 比较 ===
    final_cos = F.cosine_similarity(final_a[:104], final_b, dim=-1)
    report['final_cos'] = {
        'shape_a': list(final_a.shape),
        'shape_b': list(final_b.shape),
        'cos_mean': final_cos.mean().item(),
        'cos_min': final_cos.min().item(),
        'cos_argmin': int(final_cos.argmin().item()),
    }
    print(f'\n  final output: cos_mean={final_cos.mean().item():.6f} '
          f'cos_min={final_cos.min().item():.6f} argmin={int(final_cos.argmin().item())}', flush=True)

    # 找第一个 divergence
    first_div = None
    for n, r in report.items():
        if isinstance(r, dict) and r.get('cos_min', 1.0) < 0.99:
            if first_div is None:
                first_div = n
    report['first_divergence_layer'] = first_div
    print(f'\n  First divergence (cos<0.99): {first_div}', flush=True)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'[c037c] → {OUT_JSON}', flush=True)


if __name__ == '__main__':
    main()
