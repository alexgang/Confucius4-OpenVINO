"""debug_torch.py — 单 chunk torch backend 调试"""
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import sys
sys.path.insert(0, '.')
import math
import numpy as np
import soundfile as sf
import torch
from backends import TorchBackend, ASRStreamingState, SAMPLE_RATE, AUDIO_PAD, EOS_IDS

audio, sr = sf.read('C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
audio = audio.astype(np.float32)
print(f'audio: {len(audio)} samples, {sr}Hz, {len(audio)/SAMPLE_RATE:.2f}s')

# Load model
b = TorchBackend('models/hf')

# Encode first 1.28s of audio
chunk_audio = audio[:SAMPLE_RATE*4]  # 4s
print(f'chunk_audio: {len(chunk_audio)} samples')

# Use only prefix = '' (first chunk)
state = ASRStreamingState(
    unfixed_chunk_num=2, unfixed_token_num=5,
    chunk_size_sec=0.32, chunk_size_samples=SAMPLE_RATE*32//100,
    chunk_id=2,  # skip unfixed
    prompt_raw='',  # will set
    buffer=np.zeros(0, dtype=np.float32),
    audio_accum=chunk_audio,
)
state.prompt_raw = b._build_text_prompt(context='', force_language=None)
print(f'prompt_raw: {state.prompt_raw!r}')

# Just call generate
out = b.generate_with_prefix(state, chunk_audio, prefix_text='', max_new_tokens=32)
print(f'gen output: {out!r}')
