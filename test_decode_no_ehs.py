"""test_decode_no_ehs.py — C-009 #2：测试 decode 步能否省掉 encoder_hidden_states"""
import os, sys, time
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf
from backends import OVBackend, AUDIO_PAD, EOS_IDS

b = OVBackend()
audio, sr = sf.read('C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
audio = audio.astype(np.float32)
print(f'audio: {len(audio)/sr:.2f}s')

# encode
ehs, n_real, N_formula = b.encode_audio(audio)
N_audio = int(ehs.shape[1])
print(f'encoder: n_real={n_real}, N_audio={N_audio}, ehs={ehs.shape}')

ids_left, ids_right = b._prompt_template_ids
full_ids = list(ids_left) + [AUDIO_PAD] * N_audio + list(ids_right)
print(f'prefill len: {len(full_ids)}')

# Approach 1: pass ehs every step (current)
b.dec_infer.reset_state()
t0 = time.perf_counter()
b.dec_infer.infer({
    'encoder_hidden_states': ehs,
    'input_ids': np.array([full_ids], dtype=np.int64),
    'beam_idx': np.array([0], dtype=np.int32),
})
logits = b.dec_infer.get_output_tensor(0).data
next_id = int(np.argmax(logits[0, -1]))
t_prefill = time.perf_counter() - t0
print(f'prefill: {t_prefill*1000:.0f}ms, first token={next_id}')

# decode with ehs
t0 = time.perf_counter()
n_steps = 0
tokens_a = [next_id]
cur = next_id
for _ in range(31):
    b.dec_infer.infer({
        'encoder_hidden_states': ehs,
        'input_ids': np.array([[cur]], dtype=np.int64),
        'beam_idx': np.array([0], dtype=np.int32),
    })
    cur = int(np.argmax(b.dec_infer.get_output_tensor(0).data[0, -1]))
    n_steps += 1
    if cur in EOS_IDS: break
    tokens_a.append(cur)
t_decode_with = time.perf_counter() - t0
print(f'decode WITH ehs: {n_steps} steps, {t_decode_with*1000:.0f}ms total, {t_decode_with*1000/n_steps:.1f}ms/step')
print(f'  decoded={b.tokenizer.decode(tokens_a, skip_special_tokens=True)!r}')

# Approach 2: zero ehs on decode
b.dec_infer.reset_state()
t0 = time.perf_counter()
b.dec_infer.infer({
    'encoder_hidden_states': ehs,
    'input_ids': np.array([full_ids], dtype=np.int64),
    'beam_idx': np.array([0], dtype=np.int32),
})
logits = b.dec_infer.get_output_tensor(0).data
next_id = int(np.argmax(logits[0, -1]))
t_prefill2 = time.perf_counter() - t0
print(f'\nprefill2: {t_prefill2*1000:.0f}ms')

# decode with zero ehs
t0 = time.perf_counter()
n_steps = 0
tokens_b = [next_id]
cur = next_id
ehs_zero = np.zeros_like(ehs)
for _ in range(31):
    b.dec_infer.infer({
        'encoder_hidden_states': ehs_zero,
        'input_ids': np.array([[cur]], dtype=np.int64),
        'beam_idx': np.array([0], dtype=np.int32),
    })
    cur = int(np.argmax(b.dec_infer.get_output_tensor(0).data[0, -1]))
    n_steps += 1
    if cur in EOS_IDS: break
    tokens_b.append(cur)
t_decode_zero = time.perf_counter() - t0
print(f'decode ZERO ehs: {n_steps} steps, {t_decode_zero*1000:.0f}ms total, {t_decode_zero*1000/n_steps:.1f}ms/step')
print(f'  decoded={b.tokenizer.decode(tokens_b, skip_special_tokens=True)!r}')

# Approach 3: dummy tiny ehs (just [1,1,2048] to test if shape matters)
b.dec_infer.reset_state()
b.dec_infer.infer({
    'encoder_hidden_states': ehs,
    'input_ids': np.array([full_ids], dtype=np.int64),
    'beam_idx': np.array([0], dtype=np.int32),
})
next_id = int(np.argmax(b.dec_infer.get_output_tensor(0).data[0, -1]))
ehs_tiny = np.zeros((1, 1, 2048), dtype=np.float32)
t0 = time.perf_counter()
n_steps = 0
tokens_c = [next_id]
cur = next_id
for _ in range(31):
    b.dec_infer.infer({
        'encoder_hidden_states': ehs_tiny,
        'input_ids': np.array([[cur]], dtype=np.int64),
        'beam_idx': np.array([0], dtype=np.int32),
    })
    cur = int(np.argmax(b.dec_infer.get_output_tensor(0).data[0, -1]))
    n_steps += 1
    if cur in EOS_IDS: break
    tokens_c.append(cur)
t_decode_tiny = time.perf_counter() - t0
print(f'\ndecode TINY ehs (1,1,2048): {n_steps} steps, {t_decode_tiny*1000:.0f}ms total, {t_decode_tiny*1000/n_steps:.1f}ms/step')
print(f'  decoded={b.tokenizer.decode(tokens_c, skip_special_tokens=True)!r}')

# Compare
print(f'\nSpeedup vs WITH ehs: zero={t_decode_with/t_decode_zero:.2f}x, tiny={t_decode_with/t_decode_tiny:.2f}x')
print(f'Identical tokens? with==zero: {tokens_a == tokens_b}, with==tiny: {tokens_a == tokens_c}')
