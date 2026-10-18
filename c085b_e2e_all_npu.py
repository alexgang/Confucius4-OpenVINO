"""c085b_e2e_all_npu.py — C-085#1：**全 NPU** 端到端（enc@NPU + dec@NPU）。

## 为什么现在要跑这一格

C-082/C-083 的阶段 4 矩阵把「全 NPU」标为「不跑」，理由是「编码器在 NPU 上更慢，
没有理由跑」+「cleanie 后iGPU 只剩约 7% 可省」。**那两个理由都建立在「机器有集显」这个
前提上。** 用户的实际场景是**完全无 GPU 的台式机（无集显、不用独显），只有 CPU + NPU**，
此时「完全不占 GPU」本身就是收益，所以这一格必须重测。

## 与 cleanie 的唯一差别

c080b/c080e 跑的 cleanie 是 **enc@集显 + dec@NPU**；本脚本是 **enc@NPU + dec@NPU**，
其余完全一致：同一个cleanie INT8 decoder IR、同一切片（12–27 min）、同一套
`seg_stream` 生产逻辑、同一个 warmup、同一份 RTF 口径。这样 RTF 差值可直接归因到
「encoder 换设备」这一件事上。

## 精度判据

按硬性约束：**只用真实音频 prompt 的端到端 WER + 配对 bootstrap CI**（method B全局
对齐归因；method A 时间桶对齐已被 C-059#4 证伪）。参照系统是ABBA 配置 A 的同一切片转写。

输出：reports/c085_e2e/{summary.json,transcript_all_npu.txt}
"""
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
SLICE_START_SEC = int(os.environ.get('C085B_START', 12 * 60))
SLICE_END_SEC = int(os.environ.get('C085B_END', 27 * 60))
CHUNK_SEC = 0.64
ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/qwen3-lm-int8sym-cleanie-ov'
OUT_DIR = 'reports/c085_e2e'
WARMUP_SWEEP_SEC = [5, 12, 18]


def pct(v, q):
    return float(np.percentile(np.asarray(v, dtype=np.float64), q * 100))


def agg(v):
    if not v:
        return {}
    return {'median': round(float(np.median(v)), 1),
            'mean': round(float(np.mean(v)), 2),
            'p95': round(pct(v, 0.95), 1), 'n': len(v),
            'sum': round(float(np.sum(v)), 1)}


def main():
    from c085a_smoke_all_npu import make_all_npu_backend
    from seg_stream import SegmentedStreamer
    from c058q_wordcount import save_transcript

    audio, dur = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[SR * SLICE_START_SEC:SR * SLICE_END_SEC]
    assert abs(len(a) / SR - (SLICE_END_SEC - SLICE_START_SEC)) < 1.0
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f'[c085b] 切片 {len(a)/SR:.1f}s（{SLICE_START_SEC}–{SLICE_END_SEC} s）',
          flush=True)

    be = make_all_npu_backend(ENC_DIR, DEC_DIR)
    print(f'[c085b] 编译 enc {be.npu_enc_compile_s}s / dec {be.npu_compile_s}s',
          flush=True)

    for s in WARMUP_SWEEP_SEC:
        SegmentedStreamer(
            be, strategy='off', chunk_size_sec=CHUNK_SEC,
            unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
            adaptive_budget=True, enable_hallucination_reset=False
        ).run(a[:SR * s])
    print('[c085b] warmup done', flush=True)

    streamer = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)

    t0 = time.perf_counter()
    text, segs = streamer.run(a, progress=True)
    wall = time.perf_counter() - t0
    tp = save_transcript(segs, f'{OUT_DIR}/transcript_all_npu.txt')
    print(f'[c085b] wall {wall:.1f}s RTF {wall/(len(a)/SR):.4f}', flush=True)

    pr = be.probe
    # 失败时也要把 probe 落盘，否则等于白跑
    with open(f'{OUT_DIR}/probe_raw.json', 'w', encoding='utf-8') as f:
        json.dump({k: [round(float(x), 2) for x in v]
                   for k, v in pr.items()}, f)

    pr = be.probe
    rtfs = [x['rtf'] for x in segs if x.get('rtf', 0) > 0]
    res = {
        'cfg': 'all_npu',
        'cfg_name': 'enc@NPU + dec@NPU (cleanie INT8)',
        'devices': {'encoder': 'NPU', 'decoder': 'NPU'},
        'encoder_dir': ENC_DIR, 'decoder_dir': DEC_DIR,
        'npu_enc_compile_s': be.npu_enc_compile_s,
        'npu_dec_compile_s': be.npu_compile_s,
        'slice': [SLICE_START_SEC, SLICE_END_SEC],
        'audio_sec': round(len(a) / SR, 2), 'wall_s': round(wall, 2),
        'overall_rtf': round(wall / (len(a) / SR), 4),
        'seg_rtf_p50': round(float(np.median(rtfs)), 4) if rtfs else None,
        'seg_rtf_p95': round(pct(rtfs, 0.95), 4) if rtfs else None,
        'seg_rtf_max': round(max(rtfs), 4) if rtfs else None,
        'n_segs': len(segs),
        'n_generate_calls': len(pr['prefill_ms']),
        'transcript_path': tp,
        'total_words': len(text.split()),
        'breakdown': {k: agg(pr[k]) for k in ('enc_ms', 'prefill_ms', 'decode_ms')},
        'n_decode': agg(pr['n_decode']),
        'out_tokens': agg(pr['out_tokens']),
        'prompt_len': agg(pr['prompt_len']),
        'text_head': text[:400],
    }

    # ── 与 cleanie（enc@集显 + dec@NPU）的 encoder 分项对照 ────────
    with open('reports/c080_e2e/summary.json', encoding='utf-8') as f:
        ref = json.load(f)['by_cfg']['int8']
    res['vs_cleanie_gpu_enc'] = {
        'cleanie_rtf': ref['overall_rtf'],
        'all_npu_rtf': res['overall_rtf'],
        'rtf_ratio': round(res['overall_rtf'] / ref['overall_rtf'], 4),
        'cleanie_enc_median_ms': ref['breakdown'].get('enc_ms', {}).get('median'),
        'all_npu_enc_median_ms': res['breakdown']['enc_ms'].get('median'),
        'note': '同一cleanie INT8 decoder、同一 12–27 min 切片，唯一差别是 encoder 的设备。',
    }
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ('text_head',)}, ensure_ascii=False,
                     indent=2)[:2000], flush=True)

    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('saved ->', f'{OUT_DIR}/summary.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
