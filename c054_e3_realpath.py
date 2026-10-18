"""c054_e3_realpath.py — C-054 E3: 用仓库真实 backend 逐调用打点

c052/c053 的汇总显示 INT4 的 prefill 比 INT8 慢 51%，但 standalone decoder IR
扫描显示 INT4 反而快 10-20%。差异必然来自真实调用路径的某个参数。
本脚本复刻 c052 的跑法，但对每次 dec_infer 记录：
  - 调用类型（prefill / decode）
  - Tt = len(full_ids)、Ta = N_audio（形状）
  - 耗时
从而定位「慢」到底慢在哪一次调用、哪一个形状。
"""
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import streaming_transcribe, finish_streaming_transcribe

ENC = 'models/ov-encoder-segment-reviewer'
DECS = {
    'INT8': 'models/ov-int8-past',
    'INT4': 'models/ov-int4-lmfp16-past',
}
WAV = r'C:\Users\Trekker-PTL\confucius4-r2t2\test.wav'
CHUNK_MS = 640.0


def run(tag, dec_dir, audio):
    backend = SegmentEncoderOVBackend(
        encoder_dir=ENC, decoder_dir=dec_dir, device='GPU.0',
        precision='f16', strict_intel=True)

    # 逐调用打点：包住 dec_infer，通过输入形状判断 prefill / decode
    orig_infer = backend.dec_infer.infer
    calls = []

    def spy(inputs, **kw):
        t0 = time.perf_counter()
        out = orig_infer(inputs, **kw)
        dt = (time.perf_counter() - t0) * 1000
        ids = inputs.get('input_ids')
        ehs = inputs.get('encoder_hidden_states')
        tt = int(ids.shape[1]) if ids is not None else -1
        ta = int(ehs.shape[1]) if ehs is not None else -1
        calls.append({'kind': 'prefill' if tt > 4 else 'decode',
                      'tt': tt, 'ta': ta, 'ms': round(dt, 1)})
        return out

    backend.dec_infer.infer = spy

    chunk_samples = int(round(CHUNK_MS * 16000 / 1000))
    ws = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_MS / 1000.0)
    streaming_transcribe(backend, audio[:chunk_samples * 2], ws,
                         max_new_tokens=32, adaptive_budget=True)
    finish_streaming_transcribe(backend, ws, max_new_tokens=32)

    calls.clear()
    state = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_MS / 1000.0)
    for s in range(0, len(audio), chunk_samples):
        streaming_transcribe(backend, audio[s:s + chunk_samples], state,
                             max_new_tokens=32, adaptive_budget=True)
    finish_streaming_transcribe(backend, state, max_new_tokens=32)
    return calls


def main():
    audio, sr = sf.read(WAV, dtype='float32')
    assert sr == 16000
    if audio.ndim > 1:
        audio = audio[:, 0]
    print(f'audio {len(audio)/sr:.2f}s  chunk={CHUNK_MS}ms')

    allc = {}
    for tag, dec in DECS.items():
        allc[tag] = run(tag, dec, audio)
        pre = [c for c in allc[tag] if c['kind'] == 'prefill']
        dec_ = [c for c in allc[tag] if c['kind'] == 'decode']
        print(f'\n[{tag}] prefill 调用 {len(pre)} 次：'
              f'均值 {np.mean([c["ms"] for c in pre]):.1f} ms  '
              f'Tt {min(c["tt"] for c in pre)}~{max(c["tt"] for c in pre)}  '
              f'Ta {min(c["ta"] for c in pre)}~{max(c["ta"] for c in pre)}')
        print(f'[{tag}] decode  调用 {len(dec_)} 次：'
              f'均值 {np.mean([c["ms"] for c in dec_]):.1f} ms')

    print('\n=== 逐 prefill 调用对比（ms / Tt / Ta）===')
    print(f'{"#":>3} {"INT8 ms":>9} {"Tt":>5} {"Ta":>5} | {"INT4 ms":>9} {"Tt":>5} {"Ta":>5}')
    p8 = [c for c in allc['INT8'] if c['kind'] == 'prefill']
    p4 = [c for c in allc['INT4'] if c['kind'] == 'prefill']
    for i in range(max(len(p8), len(p4))):
        a = p8[i] if i < len(p8) else None
        b = p4[i] if i < len(p4) else None
        print(f'{i:>3} {a["ms"]:>9.1f} {a["tt"]:>5} {a["ta"]:>5} | '
              f'{b["ms"]:>9.1f} {b["tt"]:>5} {b["ta"]:>5}')


if __name__ == '__main__':
    main()
