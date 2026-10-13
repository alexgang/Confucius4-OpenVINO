"""Export the Qwen3-ASR / Confucius4-R2T2 audio encoder as a fixed-shape OpenVINO IR that
matches the reference torch audio_tower exactly.

Why not windowed: the reference Qwen3ASRAudioEncoder.forward never passes an attention mask,
so under eager/sdpa attention is global over every audio token of the input (cu_seqlens is only
honoured by flash-attention-2). Restricting attention to 104-token windows diverges from the
reference as soon as the input exceeds 800 mel frames.

IR contract (one call encodes one whole VAD segment, up to MAX_CHUNKS * 100 mel frames):
  inputs : input_features [1, 128, MAX_FRAMES] float32  -- mel, zero-padded on the right
           n_valid        [1]                  int32    -- valid encoder tokens = aftercnn_len(frames)
  output : hidden         [1, MAX_TOKENS, 2048]          -- first n_valid rows are meaningful
Valid tokens are packed contiguously (every full chunk yields 13 tokens, only the last chunk
can be partial), so a key/query mask of `index < n_valid` reproduces the reference exactly.

Usage: export_segment_encoder.py <model_dir> <out_dir> [wav_for_validation]
"""
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

from qwen_asr.core.transformers_backend import Qwen3ASRForConditionalGeneration

CHUNK = 100
TOK = 13
MAX_CHUNKS = 24                  # 24 s; VAD segments are capped at 20 s, plus headroom for flush
MAX_FRAMES = MAX_CHUNKS * CHUNK
MAX_TOKENS = MAX_CHUNKS * TOK


def aftercnn_len(n):
    leave = n % CHUNK
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // CHUNK) * TOK


class SegmentEncoder(torch.nn.Module):
    def __init__(self, tower):
        super().__init__()
        self.tower = tower

    def forward(self, input_features, n_valid):
        t = self.tower
        x = input_features[0].T.reshape(MAX_CHUNKS, CHUNK, 128).transpose(1, 2).unsqueeze(1)
        x = F.gelu(t.conv2d1(x))
        x = F.gelu(t.conv2d2(x))
        x = F.gelu(t.conv2d3(x))
        b, c, f, n = x.size()
        x = t.conv_out(x.permute(0, 3, 1, 2).contiguous().view(b, n, c * f))
        x = x + t.positional_embedding.positional_embedding[:n, :].unsqueeze(0).to(x.dtype)
        h = x.reshape(MAX_CHUNKS * n, -1)

        idx = torch.arange(MAX_TOKENS, device=h.device)
        valid = idx < n_valid.to(idx.dtype).reshape(1)
        # Mask padded keys for every query; padded query rows are discarded by the caller.
        mask = torch.where(valid.view(1, 1, 1, MAX_TOKENS),
                           torch.zeros((), dtype=h.dtype),
                           torch.full((), torch.finfo(h.dtype).min, dtype=h.dtype))
        mask = mask.expand(1, 1, MAX_TOKENS, MAX_TOKENS)
        cu = torch.stack([torch.zeros_like(n_valid.reshape(())), n_valid.reshape(())]).to(torch.int32)
        for layer in t.layers:
            h = layer(h, cu, attention_mask=mask)[0]
        h = t.proj2(t.act(t.proj1(t.ln_post(h))))
        return h.unsqueeze(0)


def pad_mel(mel):
    """mel: (128, frames) numpy -> ([1,128,MAX_FRAMES] float32, n_valid int32[1])."""
    frames = mel.shape[1]
    assert frames <= MAX_FRAMES, f'segment too long: {frames} > {MAX_FRAMES} frames'
    out = np.zeros((1, 128, MAX_FRAMES), dtype=np.float32)
    out[0, :, :frames] = mel
    return out, np.array([aftercnn_len(frames)], dtype=np.int32)


def main():
    model_dir, out_dir = sys.argv[1], sys.argv[2]
    wav = sys.argv[3] if len(sys.argv) > 3 else None
    tower = Qwen3ASRForConditionalGeneration.from_pretrained(
        model_dir, dtype=torch.float32, attn_implementation='eager').thinker.audio_tower.eval()
    enc = SegmentEncoder(tower).eval()

    import openvino as ov
    ex = (torch.zeros(1, 128, MAX_FRAMES), torch.tensor([MAX_TOKENS], dtype=torch.int32))
    with torch.no_grad():
        ov_model = ov.convert_model(enc, example_input=ex)
    os.makedirs(out_dir, exist_ok=True)
    ov.save_model(ov_model, os.path.join(out_dir, 'openvino_encoder_model.xml'))  # fp16-compressed weights
    print('saved', out_dir, [i.get_partial_shape() for i in ov_model.inputs])

    if wav is None:
        return
    import soundfile as sf
    from transformers import WhisperFeatureExtractor
    fe = WhisperFeatureExtractor.from_pretrained(model_dir)
    audio, sr = sf.read(wav, dtype='float32')
    compiled = ov.Core().compile_model(os.path.join(out_dir, 'openvino_encoder_model.xml'), 'CPU',
                                       {'INFERENCE_PRECISION_HINT': 'f32'})
    start = 2812 * sr
    print(f'{"sec":>5} {"frames":>6} {"N":>4}   ov-vs-torch mean / min')
    for sec in (0.64, 4, 7.68, 8, 9.6, 12.8, 16, 20, 23.9):
        clip = audio[start:start + int(sec * sr)]
        mel = fe(clip, sampling_rate=sr, padding='do_not_pad', return_tensors='np').input_features[0]
        with torch.no_grad():
            ref = tower(input_features=torch.from_numpy(mel),
                        feature_lens=torch.tensor([mel.shape[1]])).last_hidden_state
        feats, n_valid = pad_mel(mel)
        out = compiled([feats, n_valid])[0][0, :n_valid[0]]
        cos = F.cosine_similarity(ref, torch.from_numpy(out), dim=-1)
        print(f'{sec:5.2f} {mel.shape[1]:6d} {ref.shape[0]:4d}   {cos.mean():.6f} / {cos.min():.6f}')


if __name__ == '__main__':
    main()
