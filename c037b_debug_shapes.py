"""c037b_debug_shapes.py — 看 audio_tower 内部 conv2d1 实际 input 形状 vs SingleWindowEncoder"""
import os, sys
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import torch
import torch.nn.functional as F
import soundfile as sf

sys.path.insert(0, '.')
from c023_export_window_encoder import SingleWindowEncoder
from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
from backends import extract_audio_features

# Load
wrapper = Qwen3ASRModel.from_pretrained('models/hf', dtype=torch.float32, attn_implementation='eager')
audio_tower = wrapper.model.thinker.audio_tower
audio_tower.eval()

# 9.6s 真实音频
wav, _ = sf.read('reports/c025/audio_A_600_660.wav', dtype='float32', frames=int(9.6 * 16000))
feats, _, n_96, _ = extract_audio_features(wrapper.processor.feature_extractor, wav, return_torch=False)
mel_96 = torch.from_numpy(feats[0])  # (128, 960)
print(f'mel_96.shape: {mel_96.shape}, n_96={n_96}')

# 看 audio_tower 内部如何切分
print(f'\n[audio_tower config]')
print(f'  n_window={audio_tower.n_window}, n_window_infer={audio_tower.n_window_infer}')
print(f'  conv_chunksize={audio_tower.conv_chunksize}')

# 在 audio_tower.conv2d1 上挂 hook, 打印 input shape
captured = []
def hook(_mod, inp, out):
    captured.append({
        'input_shape': list(inp[0].shape),
        'input_dtype': inp[0].dtype,
        'input_first_chunk': inp[0][0, 0, 0, :5].tolist(),  # first 5 of chunk 0, mel 0
        'input_last_chunk': inp[0][-1, 0, 0, :5].tolist(),  # first 5 of last chunk
        'output_shape': list(out.shape),
    })

audio_tower.conv2d1.register_forward_hook(hook)
print(f'\n[Path A: audio_tower(input_features=mel_96[None], feature_lens=[960])]')
with torch.no_grad():
    out_a = audio_tower(
        input_features=mel_96,
        feature_lens=torch.tensor([960], dtype=torch.long),
    ).last_hidden_state
print(f'  Path A conv2d1 hook captured: {captured[-1]}')
print(f'  Path A output: {out_a.shape}')

# Path B: SingleWindowEncoder on window 1 (800 frames)
enc = SingleWindowEncoder(audio_tower)
enc.eval()
captured_b = []
def hook_b(_mod, inp, out):
    captured_b.append({
        'input_shape': list(inp[0].shape),
        'input_first_chunk': inp[0][0, 0, 0, :5].tolist(),
    })
enc.conv2d1.register_forward_hook(hook_b)
print(f'\n[Path B: SingleWindowEncoder on window 1 (800 mel)]')
with torch.no_grad():
    out_b1 = enc(
        input_features=mel_96[:, 0:800].unsqueeze(0),
        cu_seqlens=torch.tensor([0, 104], dtype=torch.int32),
    ).squeeze(0)[:104]
print(f'  Path B conv2d1 hook captured: {captured_b[-1]}')
print(f'  Path B output: {out_b1.shape}')

# 比较两个 path 的前 8 个 chunk 的 conv2d1 输出
# Path A hook output: (10, ...) 取前 8 个
# Path B hook output: (8, ...) 全 8 个
capt_a = captured[-1]
capt_b = captured_b[-1]
print(f'\n[Compare]')
print(f'  Path A conv2d1 input: shape={capt_a["input_shape"]}, first chunk first 5: {capt_a["input_first_chunk"]}')
print(f'  Path B conv2d1 input: shape={capt_b["input_shape"]}, first chunk first 5: {capt_b["input_first_chunk"]}')
print(f'  Match first chunk? {capt_a["input_first_chunk"] == capt_b["input_first_chunk"]}')

# 直接比较 conv2d1 output (从 hook 拿)
def run_conv2d1_only(input_to_conv, conv2d1):
    """input shape: (chunk_num, 1, 128, 100)"""
    return F.gelu(conv2d1(input_to_conv))

# Path A input
with torch.no_grad():
    in_a = torch.tensor(capt_a['input_first_chunk'] + [0]*95, dtype=torch.float32).reshape(1, 128, 100).unsqueeze(0)
    # 实际上 hook 给的 input 是 inp[0], 我们没存
    # 让我们自己手动跑 conv2d1 with the right inputs

# 重新跑, 把 input 存进 hook
captured_input_a = None
captured_output_a = None
def hook_a_full(_mod, inp, out):
    global captured_input_a, captured_output_a
    captured_input_a = inp[0].detach().clone()
    captured_output_a = out.detach().clone()

audio_tower.conv2d1.register_forward_hook(hook_a_full)
audio_tower.conv2d1._forward_hooks.clear()  # 清掉之前的 hook? 实际 PyTorch 会累积
# 重新加载避免 hook 冲突
del enc, audio_tower
wrapper = Qwen3ASRModel.from_pretrained('models/hf', dtype=torch.float32, attn_implementation='eager')
audio_tower = wrapper.model.thinker.audio_tower
audio_tower.eval()

in_a, out_a_hook = None, None
def hook_full(_mod, inp, out):
    global in_a, out_a_hook
    in_a = inp[0].detach().clone()
    out_a_hook = out.detach().clone()

audio_tower.conv2d1.register_forward_hook(hook_full)
with torch.no_grad():
    _ = audio_tower(input_features=mel_96, feature_lens=torch.tensor([960], dtype=torch.long))
print(f'\n[Path A re-run]')
print(f'  conv2d1 input: shape={list(in_a.shape)}, dtype={in_a.dtype}')
print(f'  conv2d1 output: shape={list(out_a_hook.shape)}')

# Path B: 自己构造 (8, 1, 128, 100) input
in_b = in_a[:8].clone()  # 取前 8 个 chunk
print(f'  Path B 截前 8 chunk: shape={list(in_b.shape)}')
print(f'  in_a[0,0,0,:5]={in_a[0,0,0,:5].tolist()}')
print(f'  in_b[0,0,0,:5]={in_b[0,0,0,:5].tolist()}')

# 跑 conv2d1 on in_b
with torch.no_grad():
    out_b_hook = F.gelu(audio_tower.conv2d1(in_b))
print(f'  conv2d1 on in_b (8 chunks): output shape={list(out_b_hook.shape)}')

# 比较 path A 前 8 个 chunk 输出 vs path B 输出
out_a_first8 = out_a_hook[:8]
cos = F.cosine_similarity(out_a_first8.reshape(-1, out_a_first8.shape[-1]),
                          out_b_hook.reshape(-1, out_b_hook.shape[-1]), dim=-1)
print(f'\n[Compare] path A first 8 chunks conv2d1 output vs path B conv2d1 output:')
print(f'  cos_mean={cos.mean().item():.6f}, cos_min={cos.min().item():.6f}')

# 直接 input 比一下
print(f'\n[Input identical?] in_a[:8] vs in_b: {torch.equal(in_a[:8], in_b)}')
print(f'  in_a[:8].shape={list(in_a[:8].shape)}, in_b.shape={list(in_b.shape)}')

# Path A: 用我自己的 chunking 看 input
chunk_num_a = 10
chunk_lens = [100]*9 + [60]
# 重新构造 padded_feature 路径
input_features = mel_96  # (128, 960)
input_features_b = input_features.unsqueeze(0)  # (1, 128, 960)
chunk_list = input_features_b.transpose(0, 1).reshape(960, 128, 1).split(chunk_lens, dim=0)
# chunk_list: list of (chunk_len, 128, 1)
print(f'\n[Reconstruct audio_tower padded_feature]')
print(f'  chunk_list len: {len(chunk_list)}, shapes: {[c.shape for c in chunk_list]}')
padded_feature = nn.utils.rnn.pad_sequence(chunk_list, batch_first=True).transpose(1, 2)
print(f'  padded_feature after pad_sequence+transpose: {padded_feature.shape}')

# 看 path A 真实 input vs 我自己的
import torch.nn as nn
print(f'\n[Compare audio_tower input vs my reconstruction]')
print(f'  audio_tower in_a.shape: {list(in_a.shape)}')
print(f'  reconstructed padded_feature.shape: {padded_feature.shape}')
# 但 padded_feature 是 (chunk_num, 128, 1, 100), audio_tower 期望 (chunk_num, 1, 128, 100)?
# 实际看 audio_tower 的代码, .unsqueeze(1) 加在 128 之后, 1 之前
# 所以 padded_feature 应该是 (chunk_num, 128, 1, 100), unsqueeze(1) → (chunk_num, 128, 1, 100) 不变 (dim 1 已经是 1)
# 但实际 in_a 是 (chunk_num, 1, 128, 100) — 所以 padded_feature 是 (chunk_num, 1, 128, 100)?
# 看 .transpose(1, 2): (10, 100, 128, 1) → (10, 128, 1, 100) 之后 .unsqueeze(1) → (10, 128, 1, 1, 100) 5D
# 这不对, 实际 conv2d1 接收 4D

# 让我直接看 audio_tower 的实际 in_a
print(f'  in_a.shape={list(in_a.shape)}')

# 重新构造 (按 audio_tower forward 严格)
B, n_mels, T = 1, 128, 960
input_features = mel_96.unsqueeze(0)  # (1, 128, 960)
chunk_lengths = torch.tensor([100]*9 + [60], dtype=torch.long)
chunk_list2 = input_features.T.split(chunk_lengths.tolist(), dim=0)
# input_features.T: (960, 128, 1)
# split along dim 0 with chunk_lengths → list of (chunk_len, 128, 1)
print(f'  chunk_list2 shapes: {[c.shape for c in chunk_list2]}')
padded_feature2 = nn.utils.rnn.pad_sequence(chunk_list2, batch_first=True)
# 应该是 (10, 100, 128, 1) padded
print(f'  padded_feature2 (before transpose): {padded_feature2.shape}')
padded_feature2 = padded_feature2.transpose(1, 2)
# 应该是 (10, 128, 1, 100)
print(f'  padded_feature2 (after transpose(1,2)): {padded_feature2.shape}')
padded_feature2 = padded_feature2.unsqueeze(1)
# 应该是 (10, 1, 128, 100)  — 如果原本 dim 1 是 1 那 unsqueeze 变 5D
print(f'  padded_feature2 (after unsqueeze(1)): {padded_feature2.shape}')
