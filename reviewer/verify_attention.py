"""Verify the encoder-attention hypothesis against the reference torch audio_tower.

The reference forward never passes an attention mask, so under eager/sdpa its
attention is global over every audio token. Compare three implementations on
real mel features of growing length:
  windowed : the target's SingleWindowEncoder (attention restricted to 104-token windows)
  global   : the same code, but attention over all valid tokens of the input
Usage: verify_attention.py <model_dir> <wav>
"""
import sys

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from transformers import WhisperFeatureExtractor

from qwen_asr.core.transformers_backend import Qwen3ASRForConditionalGeneration

CHUNK = 100   # mel frames per conv chunk (n_window * 2)
TOK = 13      # tokens per full chunk after the 3 stride-2 convs


def aftercnn_len(n):
    leave = n % CHUNK
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // CHUNK) * TOK


def chunk_tokens(tower, mel):
    """Per-chunk conv + per-chunk positional embedding, exactly as the reference does it."""
    n = mel.shape[1]
    n_chunks = (n + CHUNK - 1) // CHUNK
    padded = F.pad(mel, (0, n_chunks * CHUNK - n))
    x = padded.T.reshape(n_chunks, CHUNK, 128).transpose(1, 2).unsqueeze(1)
    x = F.gelu(tower.conv2d1(x))
    x = F.gelu(tower.conv2d2(x))
    x = F.gelu(tower.conv2d3(x))
    b, c, f, t = x.size()
    x = tower.conv_out(x.permute(0, 3, 1, 2).contiguous().view(b, t, c * f))
    x = x + tower.positional_embedding.positional_embedding[:t, :].unsqueeze(0).to(x.dtype)
    valid = [TOK] * (n // CHUNK) + ([aftercnn_len(n % CHUNK)] if n % CHUNK else [])
    return torch.cat([x[i, :v] for i, v in enumerate(valid)], dim=0)


def run_layers(tower, h, mask):
    cu = torch.tensor([0, h.shape[0]], dtype=torch.int32)
    for layer in tower.layers:
        h = layer(h, cu, attention_mask=mask)[0]
    h = tower.proj2(tower.act(tower.proj1(tower.ln_post(h))))
    return h


def window_mask(n_tok, win=104):
    m = torch.full((1, 1, n_tok, n_tok), torch.finfo(torch.float32).min)
    for s in range(0, n_tok, win):
        e = min(s + win, n_tok)
        m[..., s:e, s:e] = 0
    return m


def main():
    model_dir, wav = sys.argv[1], sys.argv[2]
    tower = Qwen3ASRForConditionalGeneration.from_pretrained(
        model_dir, dtype=torch.float32, attn_implementation='eager').thinker.audio_tower.eval()
    fe = WhisperFeatureExtractor.from_pretrained(model_dir)
    audio, sr = sf.read(wav, dtype='float32')
    assert sr == 16000
    start = 2812 * sr  # seg172, where the streaming loop starts
    print(f'{"sec":>5} {"frames":>6} {"N":>4}  {"windowed mean/min":>20}  {"global mean/min":>20}')
    with torch.no_grad():
        for sec in (4, 7.68, 8, 9.6, 12, 12.8, 16, 20):
            clip = audio[start:start + int(sec * sr)]
            mel = torch.from_numpy(fe(clip, sampling_rate=sr, padding='do_not_pad',
                                      return_tensors='np').input_features[0])
            n = mel.shape[1]
            ref = tower(input_features=mel, feature_lens=torch.tensor([n])).last_hidden_state
            tok = chunk_tokens(tower, mel)
            assert tok.shape[0] == ref.shape[0] == aftercnn_len(n), (tok.shape, ref.shape)
            win = run_layers(tower, tok, window_mask(tok.shape[0]))
            glob = run_layers(tower, tok, None)
            cw = F.cosine_similarity(ref, win, dim=-1)
            cg = F.cosine_similarity(ref, glob, dim=-1)
            print(f'{sec:5.2f} {n:6d} {ref.shape[0]:4d}  {cw.mean():9.6f} / {cw.min():9.6f}  '
                  f'{cg.mean():9.6f} / {cg.min():9.6f}')


if __name__ == '__main__':
    main()
