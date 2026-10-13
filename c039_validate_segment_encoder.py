"""c039_validate_segment_encoder.py — C-039#2

GPU.0 FP16 验证 9 长度 OV 整段 encoder vs torch 参考实现。
- 加载 models/ov-encoder-segment-reviewer (FP16-compressed IR)
- 9 长度: 0.64, 4, 7.68, 8, 9.6, 12.8, 16, 20, 23.9 秒
- 音频: test_audio/260902_SPE_audio.wav, 从 2812 s 开始
- 对比: torch audio_tower (CPU FP32) vs OV FP16 GPU.0
- 报告: cos mean/min, 帧数, N_audio, 编码耗时 (含首调用编译)
- 双 GPU.0 / CPU 都跑以确认精度（per C-007）
"""
import os
import sys
import time
import json
import numpy as np
import torch
import torch.nn.functional as F
import soundfile as sf
import openvino as ov
from transformers import WhisperFeatureExtractor

from qwen_asr.core.transformers_backend import Qwen3ASRForConditionalGeneration

CHUNK = 100
TOK = 13
MAX_CHUNKS = 24
MAX_FRAMES = MAX_CHUNKS * CHUNK
MAX_TOKENS = MAX_CHUNKS * TOK


def aftercnn_len(n):
    leave = n % CHUNK
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // CHUNK) * TOK


def total_aftercnn_len(frames):
    if frames <= 0:
        return 0
    n_full = frames // CHUNK
    leave = frames - n_full * CHUNK
    if leave == 0:
        return n_full * TOK
    return n_full * TOK + aftercnn_len(leave)


def pad_mel(mel):
    """mel: (128, frames) -> ([1,128,2400] float32, n_valid[1] int32)"""
    frames = mel.shape[1]
    assert frames <= MAX_FRAMES, f'segment too long: {frames} > {MAX_FRAMES}'
    out = np.zeros((1, 128, MAX_FRAMES), dtype=np.float32)
    out[0, :, :frames] = mel
    return out, np.array([total_aftercnn_len(frames)], dtype=np.int32)


def main():
    model_dir = 'models/hf'
    enc_dir = 'models/ov-encoder-segment-reviewer'
    wav = 'test_audio/260902_SPE_audio.wav'
    start_sec = 2812  # seg172

    print("=== c039_validate_segment_encoder (C-039#2) ===")
    print(f"model={model_dir}  enc_ir={enc_dir}  audio={wav}  start={start_sec}s")

    # 1. 加载 torch 参考
    print("\n[1/4] Loading torch reference (CPU FP32)...")
    t0 = time.time()
    model = Qwen3ASRForConditionalGeneration.from_pretrained(
        model_dir, dtype=torch.float32, attn_implementation='eager')
    tower = model.thinker.audio_tower.eval()
    fe = WhisperFeatureExtractor.from_pretrained(model_dir)
    print(f"  torch load: {time.time()-t0:.1f}s")

    # 2. 加载 OV IR (CPU + GPU.0 各一份)
    print("\n[2/4] Compiling OV IR (CPU FP32 + GPU.0 FP16)...")
    core = ov.Core()
    xml = os.path.join(enc_dir, 'openvino_encoder_model.xml')
    bin_ = os.path.join(enc_dir, 'openvino_encoder_model.bin')

    enc_cpu = core.compile_model(core.read_model(model=xml, weights=bin_), 'CPU',
                                 {'INFERENCE_PRECISION_HINT': 'f32'})
    full_name = core.get_property('GPU.0', 'FULL_DEVICE_NAME')
    print(f"  GPU.0 = {full_name}")
    assert 'Intel' in full_name, f"GPU.0 not Intel: {full_name}"
    enc_gpu = core.compile_model(core.read_model(model=xml, weights=bin_), 'GPU.0',
                                 {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f16'})

    # 3. 加载音频
    print("\n[3/4] Loading audio...")
    audio, sr = sf.read(wav, dtype='float32')
    print(f"  audio: sr={sr}, samples={audio.shape[0]} ({audio.shape[0]/sr:.1f}s)")
    start = start_sec * sr

    # 4. 9 长度验证
    print("\n[4/4] Validating 9 lengths...")
    lengths = (0.64, 4, 7.68, 8, 9.6, 12.8, 16, 20, 23.9)
    print(f"\n{'sec':>6} {'frames':>7} {'N_tok':>5}  "
          f"{'OV-CPU-FP32 mean/min':>22}  {'OV-GPU0-FP16 mean/min':>22}  "
          f"{'cpu_ms':>8} {'gpu_ms':>8}")
    print("-" * 100)
    results = []
    with torch.no_grad():
        for sec in lengths:
            clip = audio[start:start + int(sec * sr)]
            mel = fe(clip, sampling_rate=sr, padding='do_not_pad', return_tensors='np').input_features[0]
            frames = mel.shape[1]
            # torch reference
            ref = tower(input_features=torch.from_numpy(mel),
                        feature_lens=torch.tensor([frames])).last_hidden_state
            # pad
            feats, n_valid = pad_mel(mel)
            # OV CPU
            t0 = time.time()
            out_cpu = enc_cpu([feats, n_valid])[0][0, :n_valid[0]]
            cpu_ms = (time.time() - t0) * 1000
            # OV GPU
            t0 = time.time()
            out_gpu = enc_gpu([feats, n_valid])[0][0, :n_valid[0]]
            gpu_ms = (time.time() - t0) * 1000
            # cosine vs torch
            c_cpu = F.cosine_similarity(ref, torch.from_numpy(out_cpu), dim=-1)
            c_gpu = F.cosine_similarity(ref, torch.from_numpy(out_gpu), dim=-1)
            n_tok = ref.shape[0]
            print(f"{sec:6.2f} {frames:7d} {n_tok:5d}  "
                  f"{c_cpu.mean():12.6f} / {c_cpu.min():9.6f}  "
                  f"{c_gpu.mean():12.6f} / {c_gpu.min():9.6f}  "
                  f"{cpu_ms:8.2f} {gpu_ms:8.2f}")
            results.append({
                'sec': sec, 'frames': frames, 'n_tok': n_tok,
                'cos_cpu_mean': float(c_cpu.mean()), 'cos_cpu_min': float(c_cpu.min()),
                'cos_gpu_mean': float(c_gpu.mean()), 'cos_gpu_min': float(c_gpu.min()),
                'cpu_ms': cpu_ms, 'gpu_ms': gpu_ms,
            })

    # 5. 预热后再测一次（kernel 编译已稳定后）
    print("\n=== Warm-up pass (after kernel cache) ===")
    print(f"{'sec':>6} {'frames':>7} {'N_tok':>5}  {'gpu_ms':>8}")
    print("-" * 50)
    warm = []
    for sec in lengths:
        clip = audio[start:start + int(sec * sr)]
        mel = fe(clip, sampling_rate=sr, padding='do_not_pad', return_tensors='np').input_features[0]
        frames = mel.shape[1]
        feats, n_valid = pad_mel(mel)
        # 跑 3 次取中位
        ts = []
        for _ in range(3):
            t0 = time.time()
            out_gpu = enc_gpu([feats, n_valid])[0][0, :n_valid[0]]
            ts.append((time.time() - t0) * 1000)
        gpu_ms = sorted(ts)[1]
        n_tok = total_aftercnn_len(frames)
        print(f"{sec:6.2f} {frames:7d} {n_tok:5d}  {gpu_ms:8.2f}")
        warm.append({'sec': sec, 'frames': frames, 'n_tok': n_tok, 'gpu_ms': gpu_ms})

    # 写 JSON
    out = {
        'model_dir': model_dir,
        'enc_dir': enc_dir,
        'audio': wav,
        'start_sec': start_sec,
        'device': 'GPU.0 ' + full_name,
        'cold_results': results,
        'warm_results': warm,
    }
    out_path = 'reports/c039_segment_encoder_validation.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n=> saved {out_path}")

    # 总结
    print("\n=== Summary ===")
    g = [r for r in results]
    print(f"GPU.0 FP16 cos mean:  min={min(r['cos_gpu_mean'] for r in g):.6f}  "
          f"max={max(r['cos_gpu_mean'] for r in g):.6f}")
    print(f"GPU.0 FP16 cos min:   min={min(r['cos_gpu_min'] for r in g):.6f}  "
          f"max={max(r['cos_gpu_min'] for r in g):.6f}")
    w = [r for r in warm]
    print(f"Warm encoder time:    min={min(r['gpu_ms'] for r in w):.1f}ms  "
          f"max={max(r['gpu_ms'] for r in w):.1f}ms")


if __name__ == '__main__':
    main()
