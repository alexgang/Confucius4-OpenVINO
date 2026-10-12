"""verify.py — 阶段 4：三方对齐（OV vs qwen_asr golden vs CUDA baseline）

比较：
- OV 流式最终文本 vs qwen_asr 离线 golden
- OV 流式最终文本 vs audio.cpp CUDA 基准
- 计算 CER（character error rate）
"""
import os, sys, json, csv
os.environ['PYTHONIOENCODING'] = 'utf-8'

import numpy as np
import soundfile as sf
from ov_r2t2 import OVR2T2ASR, OVConfig, SAMPLE_RATE

CUDA_BASELINE = '之前有顾客自己带酒水也没加收钱或者不让喝。'
PYTORCH_GOLDEN = '之前有顾客自己带酒水，也没加收钱或者不让喝。'
WAV = 'C:/Users/Trekker-PTL/confucius4-r2t2/test.wav'


def cer(ref: str, hyp: str) -> float:
    """字符错误率：edit distance / len(ref)"""
    ref = list(ref); spec = list(hyp)
    if not ref:
        return 0.0 if not spec else 1.0
    dp = [[0] * (len(spec) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        dp[i][0] = i
    for j in range(len(spec) + 1):
        dp[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(spec) + 1):
            if ref[i-1] == spec[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1])
    return dp[-1][-1] / len(ref)


def strip_lang_prefix(text: str) -> str:
    """剥离 'language XXX<asr_text>' 前缀"""
    idx = text.find('<asr_text>')
    if idx >= 0:
        return text[idx + len('<asr_text>'):]
    return text


def run_ov_streaming(model_dir='models/ov-fp16', device='GPU.0',
                     chunk_ms=320, unfixed_chunk_num=2, unfixed_token_num=5,
                     max_new_tokens=32):
    cfg = OVConfig(model_dir=model_dir, device=device)
    asr = OVR2T2ASR(cfg)
    audio, sr = sf.read(WAV)
    audio = audio.astype(np.float32)
    asr.encode_audio(audio[:16000])  # warmup
    state = asr.init_streaming_state(chunk_size_sec=chunk_ms/1000,
                                     unfixed_chunk_num=unfixed_chunk_num,
                                     unfixed_token_num=unfixed_token_num)
    chunk_samples = int(SAMPLE_RATE * 0.04)
    for i in range(0, len(audio), chunk_samples):
        asr.streaming_transcribe(audio[i:i+chunk_samples], state, max_new_tokens=max_new_tokens)
    asr.finish_streaming_transcribe(state, max_new_tokens=64)
    return strip_lang_prefix(state.text)


def main():
    import time
    results = {}

    # 1. OV FP16 流式
    print('[verify] OV FP16 streaming (320ms)...')
    t0 = time.perf_counter()
    ov_text = run_ov_streaming(model_dir='models/ov-fp16', device='GPU.0',
                                chunk_ms=320)
    results['ov_fp16_stream_320'] = ov_text
    print(f'[verify] OV FP16 text: {ov_text!r}')

    # 2. OV INT8 流式
    print('[verify] OV INT8 streaming (320ms)...')
    t0 = time.perf_counter()
    ov_text_int8 = run_ov_streaming(model_dir='models/ov-int8', device='GPU.0',
                                     chunk_ms=320)
    results['ov_int8_stream_320'] = ov_text_int8
    print(f'[verify] OV INT8 text: {ov_text_int8!r}')

    # 3. PyTorch golden
    results['pytorch_golden'] = PYTORCH_GOLDEN
    results['cuda_baseline'] = CUDA_BASELINE

    # 4. CER
    cer_ov_pt = cer(PYTORCH_GOLDEN, ov_text)
    cer_ov_cuda = cer(CUDA_BASELINE, ov_text)
    cer_int8_pt = cer(PYTORCH_GOLDEN, ov_text_int8)
    cer_int8_cuda = cer(CUDA_BASELINE, ov_text_int8)
    cer_pt_cuda = cer(PYTORCH_GOLDEN, CUDA_BASELINE)

    print()
    print('=' * 60)
    print('CER comparison (lower is better):')
    print(f'  PyTorch golden ↔ CUDA baseline: {cer_pt_cuda*100:.2f}%')
    print(f'  OV FP16 ↔ PyTorch golden     : {cer_ov_pt*100:.2f}%')
    print(f'  OV FP16 ↔ CUDA baseline      : {cer_ov_cuda*100:.2f}%')
    print(f'  OV INT8 ↔ PyTorch golden     : {cer_int8_pt*100:.2f}%')
    print(f'  OV INT8 ↔ CUDA baseline      : {cer_int8_cuda*100:.2f}%')
    print('=' * 60)
    print('Texts:')
    for k, v in results.items():
        print(f'  {k:25s}: {v!r}')

    # save
    os.makedirs('reports', exist_ok=True)
    with open('reports/verify.json', 'w', encoding='utf-8') as f:
        json.dump({
            'texts': results,
            'cer': {
                'pytorch_vs_cuda': cer_pt_cuda,
                'ov_fp16_vs_pytorch': cer_ov_pt,
                'ov_fp16_vs_cuda': cer_ov_cuda,
                'ov_int8_vs_pytorch': cer_int8_pt,
                'ov_int8_vs_cuda': cer_int8_cuda,
            },
        }, f, indent=2, ensure_ascii=False)
    print('[verify] → reports/verify.json')


if __name__ == '__main__':
    main()