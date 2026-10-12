"""benchmark.py — 阶段 4：跨 chunk size × FP16/INT8 的延迟 / RTF 测量

跑矩阵：
- chunk_ms ∈ {160, 640, 1000}
- 精度 ∈ {FP16, INT8}

输出：每组 (chunk, prec) 的 wall / RTF / 文本
"""
import os, sys, time, json
os.environ['PYTHONIOENCODING'] = 'utf-8'

import numpy as np
import soundfile as sf
from ov_r2t2 import OVR2T2ASR, OVConfig, SAMPLE_RATE

WAV = 'C:/Users/Trekker-PTL/confucius4-r2t2/test.wav'


def strip_lang(text: str) -> str:
    idx = text.find('<asr_text>')
    return text[idx + len('<asr_text>'):] if idx >= 0 else text


def run_one(model_dir, device, chunk_ms, unfixed_chunk_num, unfixed_token_num, max_new_tokens):
    cfg = OVConfig(model_dir=model_dir, device=device)
    asr = OVR2T2ASR(cfg)
    audio, sr = sf.read(WAV)
    audio = audio.astype(np.float32)
    # warmup (compile)
    asr.encode_audio(audio[:16000])
    # streaming
    state = asr.init_streaming_state(chunk_size_sec=chunk_ms/1000,
                                     unfixed_chunk_num=unfixed_chunk_num,
                                     unfixed_token_num=unfixed_token_num)
    chunk_samples = int(SAMPLE_RATE * 0.04)
    n_chunks = 0
    wall_start = time.perf_counter()
    for i in range(0, len(audio), chunk_samples):
        asr.streaming_transcribe(audio[i:i+chunk_samples], state, max_new_tokens=max_new_tokens)
        if state.chunk_id > n_chunks:
            n_chunks = state.chunk_id
    asr.finish_streaming_transcribe(state, max_new_tokens=64)
    wall = time.perf_counter() - wall_start
    audio_dur = len(audio) / SAMPLE_RATE
    return {
        'text': strip_lang(state.text),
        'wall_s': wall, 'audio_dur': audio_dur, 'rtf': wall / audio_dur,
        'n_chunks': n_chunks, 'n_tokens': len(asr.tokenizer.encode(state.text, add_special_tokens=False)),
    }


def main():
    out = []
    cases = [
        # (label, model_dir, device, chunk_ms, unfixed_chunk_num, unfixed_token_num, max_new_tokens)
        ('FP16/320ms', 'models/ov-fp16', 'GPU.0', 320, 2, 5, 32),
        ('FP16/640ms', 'models/ov-fp16', 'GPU.0', 640, 2, 5, 32),
        ('FP16/1000ms', 'models/ov-fp16', 'GPU.0', 1000, 2, 5, 32),
        ('INT8/320ms', 'models/ov-int8', 'GPU.0', 320, 2, 5, 32),
        ('INT8/640ms', 'models/ov-int8', 'GPU.0', 640, 2, 5, 32),
        ('FP16/160ms', 'models/ov-fp16', 'GPU.0', 160, 2, 5, 32),
    ]
    for label, md, dev, cms, ucn, unq, mnt in cases:
        print(f'[bench] {label} ({md} on {dev}) ...')
        try:
            r = run_one(md, dev, cms, ucn, unq, mnt)
            r['label'] = label
            out.append(r)
            print(f'  text={r["text"]!r}')
            print(f'  wall={r["wall_s"]:.2f}s, audio={r["audio_dur"]:.2f}s, '
                  f'RTF={r["rtf"]:.3f}, chunks={r["n_chunks"]}, tokens={r["n_tokens"]}')
        except Exception as e:
            print(f'  FAILED: {e}')
            out.append({'label': label, 'error': str(e)})

    # save
    os.makedirs('reports', exist_ok=True)
    with open('reports/benchmark.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print('[bench] → reports/benchmark.json')

    # pretty print table
    print()
    print('=' * 90)
    print(f'{"label":20s} {"chunks":>6s} {"tokens":>6s} {"wall_s":>8s} {"audio_s":>8s} {"RTF":>6s}')
    print('-' * 90)
    for r in out:
        if 'error' in r:
            print(f'{r["label"]:20s}  ERROR: {r["error"]}')
        else:
            print(f'{r["label"]:20s} {r["n_chunks"]:>6d} {r["n_tokens"]:>6d} '
                  f'{r["wall_s"]:>8.2f} {r["audio_dur"]:>8.2f} {r["rtf"]:>6.3f}')


if __name__ == '__main__':
    main()