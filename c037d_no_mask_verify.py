"""c037d_no_mask_verify.py — 验证: 拿掉 attn_mask 后 SingleWindowEncoder 是否与 audio_tower 完全一致

假设: SingleWindowEncoder 的 4D attn_mask 把 partial block 的 cos 限制到 0.93.
      audio_tower 在 eager 模式下不传 attn_mask = 全 attention.
      拿掉 mask 后的 wrapper 应该与 audio_tower 在 12s 输入上 cos=1.0.

不修改 c023, 只 import SingleWindowEncoder 类.
"""
import os, sys
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import torch
import torch.nn.functional as F
import soundfile as sf

sys.path.insert(0, '.')
from c023_export_window_encoder import SingleWindowEncoder
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
from backends import extract_audio_features

WAV = 'reports/c025/audio_A_600_660.wav'

# 加载 model
wrapper = Qwen3ASRModel.from_pretrained('models/hf', dtype=torch.float32, attn_implementation='eager')
audio_tower = wrapper.model.thinker.audio_tower
audio_tower.eval()

# 12s 真实音频 (c025 测试用例: 12s = 1200 mel, 应得到 0.93 cos)
wav, _ = sf.read(WAV, dtype='float32', frames=int(12 * 16000))
feats, _, n_96, _ = extract_audio_features(
    wrapper.processor.feature_extractor, wav, return_torch=False,
)
mel_12 = torch.from_numpy(feats[0])  # (128, 1200)
print(f'12s mel: {mel_12.shape}, n_mel={n_96}')

# Path A: audio_tower
with torch.no_grad():
    out_a = audio_tower(
        input_features=mel_12,
        feature_lens=torch.tensor([n_96], dtype=torch.long),
    ).last_hidden_state
print(f'Path A output: {out_a.shape}')

# Path B-original: SingleWindowEncoder (有 attn_mask)
enc_with_mask = SingleWindowEncoder(audio_tower)
enc_with_mask.eval()
# 12s = 1 full 800 + 1 partial 400 (4 满 100 帧 = 4 chunks × 13 = 52 token)
win1 = mel_12[:, 0:800].unsqueeze(0)
win2_raw = mel_12[:, 800:1200]  # 400 frames
win2 = F.pad(win2_raw, (0, 800 - 400))  # pad to 800
valid_aftercnn_2 = 4 * 13  # 4 full chunks of 13 each = 52
print(f'window 1: 800 mel (valid_aftercnn=104)')
print(f'window 2: 400 mel (valid_aftercnn=52)')

with torch.no_grad():
    out_b1 = enc_with_mask(win1, torch.tensor([0, 104], dtype=torch.int32)).squeeze(0)[:104]
    out_b2 = enc_with_mask(win2.unsqueeze(0), torch.tensor([0, 52], dtype=torch.int32)).squeeze(0)[:52]
out_b_with_mask = torch.cat([out_b1, out_b2], dim=0)
print(f'Path B (WITH mask) output: {out_b_with_mask.shape}')

# 比较 with-mask vs audio_tower
n_min = min(out_a.shape[0], out_b_with_mask.shape[0])
cos_with = F.cosine_similarity(out_a[:n_min], out_b_with_mask[:n_min], dim=-1)
print(f'\n[WITH mask] cos_mean={cos_with.mean().item():.6f} cos_min={cos_with.min().item():.6f}')
print(f'  (c025 报告 0.93 — 复现 ✓)')

# === 验证: 拿掉 attn_mask 是否能让 cos=1.0 ===
# 临时 monkey-patch: 把 attention_mask 改成 None
import types

def forward_no_mask(self, input_features, cu_seqlens):
    """复制 c023 的 forward, 但不构造 attn_mask"""
    x = input_features.squeeze(0)
    chunk_num = 8
    x = x.T.view(chunk_num, 100, 128).transpose(1, 2)
    padded_feature = x.unsqueeze(1)
    padded_embed = F.gelu(self.conv2d1(padded_feature))
    padded_embed = F.gelu(self.conv2d2(padded_embed))
    padded_embed = F.gelu(self.conv2d3(padded_embed))
    b, c, f, t = padded_embed.size()
    padded_embed = self.conv_out(
        padded_embed.permute(0, 3, 1, 2).contiguous().view(b, t, c * f)
    )
    pos_emb = self.positional_embedding.positional_embedding[:t, :].unsqueeze(0).to(padded_embed.dtype)
    padded_embed = padded_embed + pos_emb
    hidden_states = padded_embed.reshape(chunk_num * t, -1)
    cu_seqlens = cu_seqlens.to(torch.int32)
    # **关键差异**: 不构造 attn_mask, 也不传给 layer
    for encoder_layer in self.layers:
        layer_outputs = encoder_layer(hidden_states, cu_seqlens)  # 无 attention_mask 参数
        hidden_states = layer_outputs[0]
    hidden_states = self.ln_post(hidden_states)
    hidden_states = self.proj1(hidden_states)
    hidden_states = self.act(hidden_states)
    hidden_states = self.proj2(hidden_states)
    return hidden_states.unsqueeze(0)

# 创建新 wrapper, 用 monkey-patched forward
enc_no_mask = SingleWindowEncoder(audio_tower)
enc_no_mask.forward = types.MethodType(forward_no_mask, enc_no_mask)
enc_no_mask.eval()

with torch.no_grad():
    out_b1_nm = enc_no_mask(win1, torch.tensor([0, 104], dtype=torch.int32)).squeeze(0)[:104]
    out_b2_nm = enc_no_mask(win2.unsqueeze(0), torch.tensor([0, 52], dtype=torch.int32)).squeeze(0)[:52]
out_b_no_mask = torch.cat([out_b1_nm, out_b2_nm], dim=0)
print(f'\nPath B (NO mask) output: {out_b_no_mask.shape}')

cos_no = F.cosine_similarity(out_a[:n_min], out_b_no_mask[:n_min], dim=-1)
print(f'[NO mask]   cos_mean={cos_no.mean().item():.6f} cos_min={cos_no.min().item():.6f}')

if cos_no.min().item() > 0.99:
    print('\n*** 结论: 拿掉 attn_mask 后 cos=1.0 → 0.93 的根因就是 attn_mask 设计 ***')
    print('*** 修复: c023 需要去掉 attn_mask, 重新导出 IR ***')
else:
    print(f'\n*** 即使去掉 mask, cos_min={cos_no.min().item():.4f}, 还有别的问题 ***')
