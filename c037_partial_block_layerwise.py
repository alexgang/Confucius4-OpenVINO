"""c037_partial_block_layerwise.py — C-032 描述的逐层对比 (本机主动跑)

按 C-032: "用 960 帧 (9 个满块 + 1 个 60 帧的不满块) 作为输入, 对 torch 和你的 wrapper
在以下位置挂 hook, 逐个比较: ① 三层 conv 之后 ② 加位置编码之后
③ 第 1 层、第 12 层、最后一层 attention 之后 ④ 最终投影之后。
第一个出现偏差的位置就是 bug。"

不重新导出 IR (per C-036 不动 models/ov-encoder-window/).
不修改 c023_export_window_encoder.py (per C-036).
仅 import SingleWindowEncoder 类, 跑 12s 真实音频逐层对比.
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import torch
import torch.nn.functional as F
import soundfile as sf

sys.path.insert(0, '.')

# SingleWindowEncoder 来自 c023 — 仅 import, 不改 c023 本体
from c023_export_window_encoder import SingleWindowEncoder
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
from backends import extract_audio_features, _qwen3_get_feat_extract_output_lengths

WAV = 'reports/c025/audio_A_600_660.wav'  # 60s 真实音频, 截前 12s 用
OUT_JSON = 'reports/c037_partial_block_layerwise.json'
N_FRAMES = 960  # 9 满块 + 1 60 帧不满块 (per C-032)


def aftercnn_len(n_mel):
    x = n_mel
    for _ in range(3):
        x = (x + 1) // 2
    return x


def main():
    print(f'[c037] loading torch audio_tower ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()
    print(f'[c037] n_window={audio_tower.n_window}, n_window_infer={audio_tower.n_window_infer}',
          flush=True)

    # 加载 12s 真实音频
    wav, sr = sf.read(WAV, dtype='float32', frames=12 * 16000)
    assert sr == 16000
    print(f'[c037] audio loaded: {len(wav)/sr:.2f}s', flush=True)

    feats_real, _, n_real, _ = extract_audio_features(
        wrapper.processor.feature_extractor, wav, return_torch=False,
    )
    full_mel = torch.from_numpy(feats_real[0])  # (128, 1200) — 12s 真实 mel
    print(f'[c037] full mel: {full_mel.shape}', flush=True)

    # === 构造输入: 12s 真实音频的 1 full window (800) + 1 partial window (160, 9 满 + 1 60 不满) ===
    # 但 12s = 1200 帧 = 800 (full) + 400 (partial 4 满 100 帧) — 不是 160
    # 改: 9.6s = 960 帧 = 800 (full) + 160 (1 满 100 + 1 不满 60)
    # 12s 实际可用: 前 9.6s 切出来
    # 但更直接: 用 9.6s 真实音频 (153600 samples)
    # 9.6s 真实音频重新跑 feature extraction
    wav_96, _ = sf.read(WAV, dtype='float32', frames=int(9.6 * 16000))
    feats_96, _, n_96, _ = extract_audio_features(
        wrapper.processor.feature_extractor, wav_96, return_torch=False,
    )
    mel_96 = torch.from_numpy(feats_96[0])  # (128, 960)
    print(f'[c037] 9.6s mel: {mel_96.shape} (n_mel={n_96})', flush=True)
    # 确认 n_mel = 960
    assert n_96 == N_FRAMES, f'expected {N_FRAMES} mel, got {n_96}'

    # === 路径 A: torch audio_tower (单次 960 帧) ===
    print(f'[c037] === Path A: torch audio_tower (single 960-frame) ===', flush=True)
    hooks_a = {}
    def make_hook(name):
        def h(_mod, _inp, out):
            if isinstance(out, tuple):
                t = out[0]
            else:
                t = out
            hooks_a[name] = t.detach().clone()
        return h

    # 关键 hook 点
    audio_tower.conv2d1.register_forward_hook(make_hook('after_conv2d1'))
    audio_tower.conv2d2.register_forward_hook(make_hook('after_conv2d2'))
    audio_tower.conv2d3.register_forward_hook(make_hook('after_conv2d3'))
    audio_tower.conv_out.register_forward_hook(make_hook('after_conv_out'))
    # positional_embedding: audio_tower.forward() 里 add, 不直接 hook
    # 24 transformer layers
    for i in [0, 11, 23]:
        audio_tower.layers[i].register_forward_hook(make_hook(f'after_layer{i}'))
    audio_tower.ln_post.register_forward_hook(make_hook('after_ln_post'))
    audio_tower.proj1.register_forward_hook(make_hook('after_proj1'))
    audio_tower.proj2.register_forward_hook(make_hook('after_proj2'))

    with torch.no_grad():
        torch_out = audio_tower(
            input_features=mel_96,
            feature_lens=torch.tensor([N_FRAMES], dtype=torch.long),
        ).last_hidden_state
    print(f'[c037] torch output: {torch_out.shape}', flush=True)

    # === 路径 B: SingleWindowEncoder (分窗) ===
    print(f'[c037] === Path B: SingleWindowEncoder (2 windows: 800 + 160) ===', flush=True)
    enc = SingleWindowEncoder(audio_tower)
    enc.eval()

    hooks_b = {}
    def make_hook_b(name):
        def h(_mod, _inp, out):
            if isinstance(out, tuple):
                t = out[0]
            else:
                t = out
            hooks_b[name] = t.detach().clone()
        return h

    enc.conv2d1.register_forward_hook(make_hook_b('after_conv2d1'))
    enc.conv2d2.register_forward_hook(make_hook_b('after_conv2d2'))
    enc.conv2d3.register_forward_hook(make_hook_b('after_conv2d3'))
    enc.conv_out.register_forward_hook(make_hook_b('after_conv_out'))
    for i in [0, 11, 23]:
        enc.layers[i].register_forward_hook(make_hook_b(f'after_layer{i}'))
    enc.ln_post.register_forward_hook(make_hook_b('after_ln_post'))
    enc.proj1.register_forward_hook(make_hook_b('after_proj1'))
    enc.proj2.register_forward_hook(make_hook_b('after_proj2'))

    # Window 1: 800 frames (full)
    win1_mel = mel_96[:, 0:800]  # already 800
    valid_aftercnn_1 = 8 * 13  # = 104
    print(f'[c037] window 1: 800 mel, valid_aftercnn={valid_aftercnn_1}', flush=True)
    with torch.no_grad():
        out_w1 = enc(
            input_features=win1_mel.unsqueeze(0),
            cu_seqlens=torch.tensor([0, valid_aftercnn_1], dtype=torch.int32),
        ).squeeze(0)[:valid_aftercnn_1]
    print(f'[c037] window 1 output: {out_w1.shape}', flush=True)
    # window 1 的 hook 是这次 enc() 的 — 但 window 2 会覆盖
    # 重新跑 (复制 hook 数据再跑 window 2)
    hooks_b_w1 = {k: v.clone() for k, v in hooks_b.items()}

    # 清除 hooks_b, 重新装 (避免污染)
    for h in list(hooks_b.keys()):
        del hooks_b[h]

    # Window 2: 160 mel (1 full 100 + 1 partial 60) → 13 + 8 = 21 tokens
    win2_mel_raw = mel_96[:, 800:960]  # 160 frames
    win2_mel = F.pad(win2_mel_raw, (0, 800 - 160))  # pad to 800
    valid_aftercnn_2 = 13 + aftercnn_len(60)  # 13 + 8 = 21
    print(f'[c037] window 2: 160 mel, valid_aftercnn={valid_aftercnn_2}', flush=True)
    with torch.no_grad():
        out_w2 = enc(
            input_features=win2_mel.unsqueeze(0),
            cu_seqlens=torch.tensor([0, valid_aftercnn_2], dtype=torch.int32),
        ).squeeze(0)[:valid_aftercnn_2]
    print(f'[c037] window 2 output: {out_w2.shape}', flush=True)
    hooks_b_w2 = {k: v.clone() for k, v in hooks_b.items()}

    # 拼成完整输出
    wrap_out = torch.cat([out_w1, out_w2], dim=0)
    print(f'[c037] wrapper full output: {wrap_out.shape} (torch={torch_out.shape[0]})', flush=True)
    assert wrap_out.shape == torch_out.shape, f'shape mismatch {wrap_out.shape} vs {torch_out.shape}'

    # === 整体 cos ===
    cos_full = F.cosine_similarity(torch_out, wrap_out, dim=-1)
    print(f'[c037] === Final overall: cos_mean={cos_full.mean().item():.6f} cos_min={cos_full.min().item():.6f} ===',
          flush=True)
    print(f'[c037] min token idx: {int(cos_full.argmin().item())} '
          f'(window 1: 0-103, window 2: 104-124)', flush=True)
    print(f'[c037] per-token cos (first 30): {[f"{c:.3f}" for c in cos_full[:30].tolist()]}', flush=True)
    print(f'[c037] per-token cos (last 30):  {[f"{c:.3f}" for c in cos_full[-30:].tolist()]}', flush=True)

    # === 逐层对比 (前 104 token = window 1 full, 应全 1.0; 后 21 token = window 2 partial) ===
    # 但 hook 是单次 forward 的中间输出, 路径 A 是一次 forward 出全部, 路径 B 是两次 forward
    # 路径 B 的 window 1 hooks_b_w1 对应 token 0-103, window 2 hooks_b_w2 对应 token 104-124
    # window 1 应该是全 1.0 (full window 已知)
    # window 2 partial 是要查的

    def compare_layer(name, t_a, t_b):
        # 处理 4D conv outputs / 3D transformer outputs
        if t_a.shape != t_b.shape:
            return {'shape_a': list(t_a.shape), 'shape_b': list(t_b.shape),
                    'note': 'shape mismatch — not directly comparable'}
        # 降维到 (..., D) 然后做 mean
        t_a_flat = t_a.reshape(-1, t_a.shape[-1])
        t_b_flat = t_b.reshape(-1, t_b.shape[-1])
        if t_a_flat.shape[0] > 0:
            cos = F.cosine_similarity(t_a_flat, t_b_flat, dim=-1)
            diff = (t_a_flat - t_b_flat).abs()
            return {
                'shape_a': list(t_a.shape), 'shape_b': list(t_b.shape),
                'cos_mean': cos.mean().item(),
                'cos_min': cos.min().item(),
                'abs_diff_max': diff.max().item(),
                'abs_diff_mean': diff.mean().item(),
            }
        return None

    # === 报告每个 hook 点的差异 (window 1 full + window 2 partial) ===
    report = {
        'audio': 'reports/c025/audio_A_600_660.wav (前 9.6s)',
        'n_mel': N_FRAMES,
        'final_cos': {
            'mean': cos_full.mean().item(),
            'min': cos_full.min().item(),
            'min_token_idx': int(cos_full.argmin().item()),
            'min_in_window': 'window_2' if int(cos_full.argmin().item()) >= 104 else 'window_1',
            'per_token_first30': [round(c, 4) for c in cos_full[:30].tolist()],
            'per_token_last30':  [round(c, 4) for c in cos_full[-30:].tolist()],
        },
        'window1_full': {},
        'window2_partial': {},
    }

    # Window 1 full — 应全 1.0
    print(f'\n[c037] === Window 1 (full 800 mel, 104 tokens) ===', flush=True)
    for k in hooks_a.keys():
        if k in hooks_b_w1:
            r = compare_layer(k, hooks_a[k], hooks_b_w1[k])
            if r:
                report['window1_full'][k] = r
                marker = ' [WARN]' if r.get('cos_min', 1.0) < 0.99 else ''
                print(f'  {k:20s} cos_mean={r.get("cos_mean", 0):.6f} '
                      f'cos_min={r.get("cos_min", 0):.6f}{marker}', flush=True)

    # Window 2 partial — 这是要查的
    print(f'\n[c037] === Window 2 (partial 160 mel: 100 + 60 不满, 21 tokens) ===', flush=True)
    for k in hooks_a.keys():
        if k in hooks_b_w2:
            r = compare_layer(k, hooks_a[k], hooks_b_w2[k])
            if r:
                report['window2_partial'][k] = r
                marker = ' [FIRST DIVERGENCE]' if r.get('cos_min', 1.0) < 0.99 else ''
                print(f'  {k:20s} cos_mean={r.get("cos_mean", 0):.6f} '
                      f'cos_min={r.get("cos_min", 0):.6f}{marker}', flush=True)

    # === 第一个偏差位置 ===
    first_div_w1 = None
    for k, r in report['window1_full'].items():
        if r.get('cos_min', 1.0) < 0.99:
            first_div_w1 = k
            break
    first_div_w2 = None
    for k, r in report['window2_partial'].items():
        if r.get('cos_min', 1.0) < 0.99:
            first_div_w2 = k
            break

    print(f'\n[c037] === 结论 ===', flush=True)
    print(f'  Window 1 (full)  第一个 cos<0.99 的层: {first_div_w1}', flush=True)
    print(f'  Window 2 (partial) 第一个 cos<0.99 的层: {first_div_w2}', flush=True)

    if first_div_w2 == 'after_conv2d1':
        print(f'  → Bug 在 conv2d1 (或之前: 输入 mel 切分/补齐)', flush=True)
    elif first_div_w2 == 'after_conv2d2':
        print(f'  → Bug 在 conv2d2', flush=True)
    elif first_div_w2 == 'after_conv2d3':
        print(f'  → Bug 在 conv2d3', flush=True)
    elif first_div_w2 == 'after_conv_out':
        print(f'  → Bug 在 conv_out', flush=True)
    elif first_div_w2 and first_div_w2.startswith('after_layer'):
        print(f'  → Bug 在 conv (前面), 但 layer 0 才放大', flush=True)
    elif first_div_w2 in ('after_ln_post', 'after_proj1', 'after_proj2'):
        print(f'  → Bug 早期, 但到 projection 才放大', flush=True)

    report['first_div_w1'] = first_div_w1
    report['first_div_w2'] = first_div_w2

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'[c037] → {OUT_JSON}', flush=True)


if __name__ == '__main__':
    main()
