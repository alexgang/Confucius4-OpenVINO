"""ref_torch.py — 阶段 2 Golden 参考

用官方 qwen_asr.Qwen3ASRModel（transformers backend, CPU, FP32）跑 test.wav 的**离线**转写。
由于 qwen_asr.streaming_transcribe 强制 vLLM backend（Windows 上不装），
所以 offline-only golden 即可（最终文本与 OV 离线对，验证算法 + tokenizer + prompt 构造是对的）。

跑两组：
A) 默认参数 (force_language=None) → 期待输出含 language tag
B) force_language='Chinese' → 输出 text-only
"""
import os, sys, time
os.environ['PYTHONIOENCODING'] = 'utf-8'

import numpy as np
import soundfile as sf
import qwen_asr

WAV = 'C:/Users/Trekker-PTL/confucius4-r2t2/test.wav'


def main():
    print('[ref] loading Qwen3ASRModel (transformers, CPU, FP32) ...')
    t0 = time.perf_counter()
    model = qwen_asr.Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    model.model = model.model.to('cpu')
    print(f'[ref] loaded in {time.perf_counter()-t0:.1f}s')

    audio, sr = sf.read(WAV)
    print(f'[ref] audio: {len(audio)} samples, {sr} Hz, {len(audio)/sr:.2f}s')

    # Run A: default
    t0 = time.perf_counter()
    results_A = model.transcribe((audio, sr), return_time_stamps=False)
    elapsed_A = time.perf_counter() - t0
    print(f'[ref A] transcribe in {elapsed_A:.2f}s, RTF={elapsed_A/(len(audio)/sr):.3f}')
    print(f'[ref A] language={results_A[0].language!r}')
    print(f'[ref A] text    ={results_A[0].text!r}')

    # Run B: forced language
    t0 = time.perf_counter()
    results_B = model.transcribe((audio, sr), language='Chinese', return_time_stamps=False)
    elapsed_B = time.perf_counter() - t0
    print(f'[ref B] transcribe in {elapsed_B:.2f}s, RTF={elapsed_B/(len(audio)/sr):.3f}')
    print(f'[ref B] language={results_B[0].language!r}')
    print(f'[ref B] text    ={results_B[0].text!r}')


if __name__ == '__main__':
    import torch
    main()