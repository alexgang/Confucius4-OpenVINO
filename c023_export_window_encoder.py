"""c023_export_window_encoder.py — C-023 step 2: 重新导出 single-window encoder IR (cu_seqlens 动态)

按 C-023 方案 (a) 重导：
- 输入固定 [1, 128, 800] (一个 800 帧注意力窗口 = 8 块 100 帧)
- cu_seqlens 作为输入 (Python 侧根据实际 valid_aftercnn 算)
- 内部按 qwen_asr 原 Qwen3ASRAudioEncoder.forward 逻辑
- 不走 optimum-intel Qwen3ASRModelPatcher
- 用 torch.jit.trace + ov.convert_model 直接导出

C-038#1 (per user 13:30 13:35)：加 padded token 零屏蔽 mask，模拟 r2t2 原版
`padded_mask_after_cnn` 的过滤效果，修复 partial block 0.93 cos bug。

输出：models/ov-encoder-window-v2/ (保留 v1 不动 per 协议)
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import torch
import openvino as ov
import numpy as np

sys.path.insert(0, '.')

from qwen_asr.inference.qwen3_asr import Qwen3ASRModel

# C-038#1: 输出到 v2 目录 (v1 保留不动)
OUT_DIR = 'models/ov-encoder-window-v2'
os.makedirs(OUT_DIR, exist_ok=True)


class SingleWindowEncoder(torch.nn.Module):
    """单窗口 audio encoder，输入固定 (1, 128, 800) + cu_seqlens (2,)。
    C-038#1 fix：在 pos_emb 之后加 padded token 零屏蔽 mask，模拟 r2t2 原版
    `padded_mask_after_cnn` 的过滤效果（消除 padded 零帧经过 conv bias 后的非零向量
    对 transformer attention 的污染）。
    """
    def __init__(self, audio_tower):
        super().__init__()
        self.conv2d1 = audio_tower.conv2d1
        self.conv2d2 = audio_tower.conv2d2
        self.conv2d3 = audio_tower.conv2d3
        self.conv_out = audio_tower.conv_out
        self.positional_embedding = audio_tower.positional_embedding
        self.layers = audio_tower.layers
        self.ln_post = audio_tower.ln_post
        self.proj1 = audio_tower.proj1
        self.act = audio_tower.act
        self.proj2 = audio_tower.proj2
        self.n_window = audio_tower.n_window
        self.n_window_infer = audio_tower.n_window_infer
        # 保留 audio_tower 原本的 _attn_implementation（不要改 eager，会破坏与原 audio_tower 的数值一致）
        self._attn_impl = audio_tower.layers[0].self_attn.config._attn_implementation

    def forward(self, input_features: torch.Tensor, cu_seqlens: torch.Tensor):
        """input_features: (1, 128, 800) — 固定形状，Python 侧把 mel 切 8 块并补零
        cu_seqlens: (2,) int32 — [0, valid_aftercnn]
        Returns: (1, 104, 2048) — 104 固定；前 cu_seqlens[1] 个是有效 token
        """
        # 2D view 给 conv2d1（unsqueeze channel）
        x = input_features.squeeze(0)  # (128, 800)
        chunk_num = 8
        # 关键 stride：用 mel.T.view(8, 100, 128).transpose(1, 2) 跟原 audio_tower 一致
        x = x.T.view(chunk_num, 100, 128).transpose(1, 2)  # (8, 128, 100) 非 contiguous

        padded_feature = x.unsqueeze(1)  # (8, 1, 128, 100)
        # 3 stride-2 conv
        padded_embed = torch.nn.functional.gelu(self.conv2d1(padded_feature))
        padded_embed = torch.nn.functional.gelu(self.conv2d2(padded_embed))
        padded_embed = torch.nn.functional.gelu(self.conv2d3(padded_embed))
        b, c, f, t = padded_embed.size()
        # conv_out: (8, 13, 1024)
        padded_embed = self.conv_out(
            padded_embed.permute(0, 3, 1, 2).contiguous().view(b, t, c * f)
        )
        # per-chunk 位置编码 0-12
        pos_emb = self.positional_embedding.positional_embedding[:t, :].unsqueeze(0).to(padded_embed.dtype)
        padded_embed = padded_embed + pos_emb
        # (104, 1024)
        hidden_states = padded_embed.reshape(chunk_num * t, -1)

        # cu_seqlens 现在是输入 (2,) int32 = [0, valid_aftercnn]
        cu_seqlens = cu_seqlens.to(torch.int32)

        # === C-038#1 fix: 屏蔽 padded token (position >= n_valid) ===
        # r2t2 原版：`hidden_states = padded_embed[padded_mask_after_cnn]` 仅保留有效 token
        # c023 v1：不过滤，全部 104 token 进 transformer → padded 零帧经过 conv bias 变成
        #         非零向量污染 attention → partial window cos 0.93
        # 修复：保持 IR 输出形状固定 104 tokens，但 padded 位置强制置零
        positions = torch.arange(104, device=hidden_states.device, dtype=torch.int32)
        n_valid = cu_seqlens[1]  # int32 scalar, dynamic input
        pad_mask = (positions < n_valid).to(hidden_states.dtype).unsqueeze(-1)  # (104, 1)
        hidden_states = hidden_states * pad_mask

        # 构造 4D attention mask（1, 1, 104, 104）：valid 窗口内 = 0，外 = -inf
        # 不用 Python int，用 tensor broadcasting 让 trace 保留 valid 为输入
        idx_row = torch.arange(104, device=hidden_states.device).view(1, 1, 104, 1)
        idx_col = torch.arange(104, device=hidden_states.device).view(1, 1, 1, 104)
        valid_t = cu_seqlens[1].view(1, 1, 1, 1)
        valid_mask = (idx_row < valid_t) & (idx_col < valid_t)
        neg_inf = torch.finfo(hidden_states.dtype).min
        attn_mask = torch.where(
            valid_mask,
            torch.zeros((), device=hidden_states.device, dtype=hidden_states.dtype),
            torch.full((), neg_inf, device=hidden_states.device, dtype=hidden_states.dtype),
        ).view(1, 1, 104, 104)

        # 24 层 attention（用 attn_mask）
        for encoder_layer in self.layers:
            layer_outputs = encoder_layer(hidden_states, cu_seqlens, attention_mask=attn_mask)
            hidden_states = layer_outputs[0]

        hidden_states = self.ln_post(hidden_states)
        hidden_states = self.proj1(hidden_states)
        hidden_states = self.act(hidden_states)
        hidden_states = self.proj2(hidden_states)
        return hidden_states.unsqueeze(0)


def main():
    print(f'[c023] loading Qwen3ASRModel ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()
    print(f'[c023] audio_tower loaded, n_window={audio_tower.n_window}, '
          f'n_window_infer={audio_tower.n_window_infer}', flush=True)

    enc = SingleWindowEncoder(audio_tower)
    enc.eval()

    # Smoke test
    print(f'[c023] smoke test ...', flush=True)
    # Full window 800 mel
    test_mel = torch.randn(128, 800)
    with torch.no_grad():
        out_tower = audio_tower(input_features=test_mel, feature_lens=torch.tensor([800], dtype=torch.long)).last_hidden_state
        out_wrap = enc(
            input_features=test_mel.unsqueeze(0),
            cu_seqlens=torch.tensor([0, 104], dtype=torch.int32),
        ).squeeze(0)
    cos = torch.nn.functional.cosine_similarity(out_tower, out_wrap, dim=-1)
    print(f'[c023] full 800 mel: cos mean={cos.mean().item():.6f} min={cos.min().item():.6f}', flush=True)

    # Partial window 320 mel (4 chunks, aftercnn=42)
    test_mel_p = torch.randn(128, 320)
    with torch.no_grad():
        out_tower_p = audio_tower(input_features=test_mel_p, feature_lens=torch.tensor([320], dtype=torch.long)).last_hidden_state
        win_p = torch.nn.functional.pad(test_mel_p, (0, 480))
        out_wrap_p = enc(
            input_features=win_p.unsqueeze(0),
            cu_seqlens=torch.tensor([0, 42], dtype=torch.int32),
        ).squeeze(0)[:42]
    cos_p = torch.nn.functional.cosine_similarity(out_tower_p, out_wrap_p, dim=-1)
    print(f'[c023] partial 320 mel: cos mean={cos_p.mean().item():.6f} min={cos_p.min().item():.6f}', flush=True)

    # torch.jit.trace + ov.convert_model
    print(f'[c023] torch.jit.trace ...', flush=True)
    example_input = torch.randn(1, 128, 800)
    example_cu = torch.tensor([0, 104], dtype=torch.int32)
    with torch.no_grad():
        traced = torch.jit.trace(enc, (example_input, example_cu))
    print(f'[c023] traced ok', flush=True)

    print(f'[c023] ov.convert_model ...', flush=True)
    with torch.no_grad():
        ov_model = ov.convert_model(traced, example_input=(example_input, example_cu))
    print(f'[c023] converted ok, inputs:', flush=True)
    for inp in ov_model.inputs:
        print(f'  {inp.any_name}: {inp.partial_shape}', flush=True)
    print(f'[c023] outputs:', flush=True)
    for i, out in enumerate(ov_model.outputs):
        names = list(out.get_names()) if out.get_names() else []
        name = names[0] if names else f'out_{i}'
        print(f'  {name}: {out.partial_shape}', flush=True)

    out_xml = os.path.join(OUT_DIR, 'openvino_encoder_model.xml')
    out_bin = os.path.join(OUT_DIR, 'openvino_encoder_model.bin')
    ov.save_model(ov_model, out_xml)
    print(f'[c023] → {out_xml}', flush=True)
    print(f'[c023] → {out_bin}', flush=True)

    # 也导一份 FP32 用于精度验证
    out_xml32 = os.path.join(OUT_DIR, 'openvino_encoder_model_fp32.xml')
    out_bin32 = os.path.join(OUT_DIR, 'openvino_encoder_model_fp32.bin')
    ov.save_model(ov_model, out_xml32, compress_to_fp16=False)
    print(f'[c023] → {out_xml32}', flush=True)

    # 备份 smoke test 数字
    smoke = {
        'c038_v2': {
            'full_800_mel_cos_mean': cos.mean().item(),
            'full_800_mel_cos_min': cos.min().item(),
            'partial_320_mel_cos_mean': cos_p.mean().item(),
            'partial_320_mel_cos_min': cos_p.min().item(),
        }
    }
    with open('reports/c023_v2_smoke.json', 'w', encoding='utf-8') as f:
        json.dump(smoke, f, ensure_ascii=False, indent=2)
    print(f'[c023] smoke → reports/c023_v2_smoke.json', flush=True)


if __name__ == '__main__':
    main()
