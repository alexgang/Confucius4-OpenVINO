"""c030b_export_window_encoder_perchunk.py — C-030 step 2 (B) 重导 single-window encoder

修复 C-025#1 遗留的 partial chunk min cos 0.93 问题：
- 原版 (c023_export_window_encoder.py) 把 cu_seqlens 当成 [0, valid_aftercnn] 单段
  → 4D mask 让所有 valid token 互相 attend
  → 800 mel full window: per-chunk 注意力等价于全连接 → cos=1.0
  → 600 mel partial: per-chunk 注意力 vs 全连接**不同** → cos=0.93
- 修复：cu_seqlens 改 per-chunk 累积，例 [0, 13, 26, 39, 52, 65, 78]
  → 4D mask 块内 attention（每 chunk 13 token 只 attend 自己）
  → 与 r2t2 源码 modeling_qwen3_asr.py 695-732 完全一致

新 IR 路径：models/ov-encoder-window-v2/
"""
import os, sys, time
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
# 不强制 USE_TORCH=0：导出需要 torch

sys.path.insert(0, '.')
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import openvino as ov


def _get_feat_extract_output_lengths(input_lengths):
    """复刻 qwen_asr.modeling_qwen3_asr._get_feat_extract_output_lengths"""
    input_lengths_leave = input_lengths % 100
    feat_lengths = (input_lengths_leave - 1) // 2 + 1
    output_lengths = ((feat_lengths - 1) // 2 + 1 - 1) // 2 + 1 + (input_lengths // 100) * 13
    return output_lengths


def compute_per_chunk_cu_seqlens(valid_mel_in_window):
    """Compute per-chunk cumulative seqlens for a window with valid_mel_in_window frames.

    For 800 mel (8 full 100-mel chunks): [0, 13, 26, 39, 52, 65, 78, 91, 104]
    For 600 mel (5 full + 1 full=100 chunk): [0, 13, 26, 39, 52, 65, 78]
    For 50 mel: [0, 7]
    """
    n_full = valid_mel_in_window // 100
    rem = valid_mel_in_window - n_full * 100
    cu = [0]
    for i in range(n_full):
        cu.append(cu[-1] + 13)
    if rem > 0:
        cu.append(cu[-1] + int(_get_feat_extract_output_lengths(torch.tensor([rem])).item()))
    return cu


OUT_DIR = 'models/ov-encoder-window-v2'
os.makedirs(OUT_DIR, exist_ok=True)


class SingleWindowEncoderV2(nn.Module):
    """单窗口 audio encoder (V2: per-chunk cu_seqlens).

    输入：
      input_features: (1, 128, 800) — 0-padded to 800
      cu_seqlens: (N+1,) int32 — per-chunk cumulative, N ∈ [1, 8]
                  例 full window: [0, 13, 26, 39, 52, 65, 78, 91, 104]
                  例 partial 600:  [0, 13, 26, 39, 52, 65, 78]
    输出：hidden_states (1, 104, 2048) — padded with zeros for invalid positions
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
        self._attn_impl = audio_tower.layers[0].self_attn.config._attn_implementation

    def forward(self, input_features: torch.Tensor, cu_seqlens: torch.Tensor):
        """
        input_features: (1, 128, 800)
        cu_seqlens: (N+1,) int32, per-chunk cumulative
        """
        x = input_features.squeeze(0)  # (128, 800)
        chunk_num = 8
        x = x.T.view(chunk_num, 100, 128).transpose(1, 2)  # (8, 128, 100) non-contig
        padded_feature = x.unsqueeze(1)  # (8, 1, 128, 100)
        padded_embed = F.gelu(self.conv2d1(padded_feature))
        padded_embed = F.gelu(self.conv2d2(padded_embed))
        padded_embed = F.gelu(self.conv2d3(padded_embed))
        b, c, f, t = padded_embed.size()
        padded_embed = self.conv_out(
            padded_embed.permute(0, 3, 1, 2).contiguous().view(b, t, c * f)
        )
        pos_emb = self.positional_embedding.positional_embedding[:t, :].unsqueeze(0).to(padded_embed.dtype)
        padded_embed = padded_embed + pos_emb
        hidden_states = padded_embed.reshape(chunk_num * t, -1)  # (104, 1024)

        cu_seqlens = cu_seqlens.to(torch.int32)
        total_valid = cu_seqlens[-1]  # tensor scalar, dynamic

        # Match torch: line 718 of qwen_asr `hidden_states = padded_embed[padded_mask_after_cnn]`
        # torch REMOVES invalid positions before attention. OV needs fixed 104-shape for trace,
        # so we zero out invalid positions AFTER pos_emb. The invalid positions get:
        #   CNN(0) + pos_emb = pos_emb, then * 0 = 0
        # So they contribute 0 to Q/K/V → softmax weight ~0 → output matches torch.
        idx = torch.arange(104, device=hidden_states.device).view(104, 1)
        valid_mask_flat = (idx < total_valid).to(hidden_states.dtype)  # (104, 1)
        hidden_states = hidden_states * valid_mask_flat  # broadcast over hidden dim

        # NO 4D mask — match torch SDPA/eager behavior (no mask, full attention over valid positions)
        for encoder_layer in self.layers:
            layer_outputs = encoder_layer(hidden_states, cu_seqlens)
            hidden_states = layer_outputs[0]

        hidden_states = self.ln_post(hidden_states)
        hidden_states = self.proj1(hidden_states)
        hidden_states = self.act(hidden_states)
        hidden_states = self.proj2(hidden_states)
        return hidden_states.unsqueeze(0)  # (1, 104, 2048)


def main():
    print(f'[c030b] loading Qwen3ASRModel ...', flush=True)
    from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio_tower = wrapper.model.thinker.audio_tower
    audio_tower.eval()
    print(f'[c030b] audio_tower loaded, n_window={audio_tower.n_window}, '
          f'n_window_infer={audio_tower.n_window_infer}', flush=True)

    enc = SingleWindowEncoderV2(audio_tower)
    enc.eval()

    # Smoke tests
    print(f'[c030b] === smoke test ===', flush=True)
    for valid in [800, 700, 600, 500, 400, 300, 200, 100, 50, 1]:
        torch.manual_seed(42)
        mel = torch.randn(128, 800)
        if valid < 800:
            mask = torch.zeros(128, 800)
            mask[:, :valid] = 1
            # Just feed the valid portion + pad
        win_mel = mel[:, :valid] if valid < 800 else mel
        # tower takes 2D
        with torch.no_grad():
            out_tower = audio_tower(input_features=win_mel,
                                     feature_lens=torch.tensor([valid], dtype=torch.long)).last_hidden_state
            cu = compute_per_chunk_cu_seqlens(valid)
            cu_t = torch.tensor(cu, dtype=torch.int32)
            win_padded = F.pad(win_mel, (0, 800 - valid)) if valid < 800 else win_mel
            out_v2 = enc(
                input_features=win_padded.unsqueeze(0),
                cu_seqlens=cu_t,
            ).squeeze(0)[:int(cu[-1])]
        cos = F.cosine_similarity(out_tower, out_v2, dim=-1)
        n_low = int((cos < 0.99).sum())
        print(f'[c030b] valid={valid:3d}  cu={cu}  '
              f'cos_mean={cos.mean().item():.6f} cos_min={cos.min().item():.6f} '
              f'n(<0.99)={n_low}', flush=True)

    # torch.jit.trace + ov.convert_model
    print(f'[c030b] torch.jit.trace (with example cu_seqlens for 600 mel) ...', flush=True)
    example_input = torch.randn(1, 128, 800)
    example_cu = torch.tensor(compute_per_chunk_cu_seqlens(600), dtype=torch.int32)  # [0, 13, 26, 39, 52, 65, 78]
    print(f'[c030b]   example cu_seqlens: {example_cu.tolist()}', flush=True)
    with torch.no_grad():
        traced = torch.jit.trace(enc, (example_input, example_cu))
    print(f'[c030b] traced ok', flush=True)

    print(f'[c030b] ov.convert_model ...', flush=True)
    with torch.no_grad():
        ov_model = ov.convert_model(traced, example_input=(example_input, example_cu))
    print(f'[c030b] converted ok, inputs:', flush=True)
    for inp in ov_model.inputs:
        print(f'  {inp.any_name}: {inp.partial_shape}', flush=True)
    print(f'[c030b] outputs:', flush=True)
    for i, out in enumerate(ov_model.outputs):
        names = list(out.get_names()) if out.get_names() else []
        name = names[0] if names else f'out_{i}'
        print(f'  {name}: {out.partial_shape}', flush=True)

    # Reshape cu_seqlens to dynamic [1, 9] upper bound (max 8 chunks + 1 = 9)
    print(f'[c030b] reshape cu_seqlens to dynamic [-1, 9]...', flush=True)
    for inp in ov_model.inputs:
        name = inp.any_name
        if 'cu' in name.lower() or 'seqlen' in name.lower():
            try:
                inp.get_node().set_partial_shape([-1])
            except Exception as e:
                print(f'  warn reshape {name}: {e}', flush=True)

    out_xml = os.path.join(OUT_DIR, 'openvino_encoder_model.xml')
    out_bin = os.path.join(OUT_DIR, 'openvino_encoder_model.bin')
    ov.save_model(ov_model, out_xml)
    print(f'[c030b] → {out_xml}', flush=True)
    print(f'[c030b] → {out_bin}', flush=True)

    out_xml32 = os.path.join(OUT_DIR, 'openvino_encoder_model_fp32.xml')
    out_bin32 = os.path.join(OUT_DIR, 'openvino_encoder_model_fp32.bin')
    ov.save_model(ov_model, out_xml32, compress_to_fp16=False)
    print(f'[c030b] → {out_xml32}', flush=True)


if __name__ == '__main__':
    main()
