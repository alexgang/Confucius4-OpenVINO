"""c056_lmhead_accuracy.py — C-056: lm_head 量化到 INT4 的精度代价实测

问题（承接 C-055）：交付的 ov-int4-lmfp16-past 刻意把 lm_head 留在 FP16
（c043_export_int4.py 的 ignored_scope + clone），代价是词表矩阵被复制成两份
（148 MiB i4 embed + 594 MiB f16 lm_head）。如果把 lm_head 也量化到 INT4
（tie 保留，decoder IR 846 MiB vs INT8 1723 MB，-51%），精度会掉多少？

方法（与 C-044 完全同口径，可复现对比）：
  Step 1  用 FP16 decoder 流式跑 C-044 的 3 个代表段（seg118/161/163，
          即当年找到的 INT8 翻转段），收集 (full_input_ids, ehs, fp16_target_tokens)
  Step 2  对 int4lmfp16（现状）与 int4lmhead（what-if）做 teacher forcing，
          统计 top-1 一致率 / EOS 一致率 → 两者的差就是 lm_head INT4 的净代价
  Step 3  端到端流式（strategy='off'，同 C-044）跑 3 段，对比两个变体的
          输出文本与 token 级 diff → 估计 WER 变化

用法：.venv python c056_lmhead_accuracy.py
输出：reports/c056_lmhead_acc.json
"""
import os
import sys
import time
import json

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer

# 复用 C-044 的确定性机制（同段、同参数、同 prompt）
from c044_teacher_force import (
    TF_SEGMENTS, EOS_IDS, CHUNK_SIZE_SEC, UNFIXED_TOKEN_NUM,
    UNFIXED_CHUNK_NUM, MAX_NEW_TOKENS,
    get_fp16_streaming_sequences, teacher_force,
)

OUT = 'reports/c056_lmhead_acc.json'
AUDIO = 'test_audio/<redacted>.wav'


def stream_text(backend, seg):
    """端到端流式跑一段，返回 (text, tokens)。参数同 C-044 Step 3。"""
    streamer = SegmentedStreamer(
        backend, strategy='off',
        chunk_size_sec=CHUNK_SIZE_SEC,
        unfixed_chunk_num=UNFIXED_CHUNK_NUM, unfixed_token_num=UNFIXED_TOKEN_NUM,
        max_new_tokens=MAX_NEW_TOKENS,
    )
    text, _segs = streamer.run(seg)
    return text


def main():
    print('[c056] === lm_head INT4 精度代价实测 ===', flush=True)
    print(f'[c056] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)
    print(f'[c056] 测试段: {[s[2] for s in TF_SEGMENTS]}（C-044 同段）', flush=True)

    audio_full, sr = sf.read(AUDIO, dtype='float32')
    if audio_full.ndim > 1:
        audio_full = audio_full[:, 0]
    assert sr == 16000

    print('[c056] 加载 backends...', flush=True)
    backends = {
        'fp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-fp16-past',
            device='GPU.0', precision='f16'),
        'int4lmfp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int4-lmfp16-past',
            device='GPU.0', precision='f16'),
        'int4lmhead': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int4-lmhead-past',
            device='GPU.0', precision='f16'),
    }

    # ── Step 1: FP16 参考序列 ────────────────────────────
    print('\n[c056] Step 1: FP16 streaming 收集参考序列...', flush=True)
    all_sequences = []
    for start, end, label in TF_SEGMENTS:
        seqs = get_fp16_streaming_sequences(backends['fp16'], label, start,
                                            end, audio_full, sr)
        all_sequences.extend(seqs)
    total_target_tokens = sum(len(s['fp16_target_tokens'])
                              for s in all_sequences)
    print(f'[c056] {len(all_sequences)} 个 sequences，'
          f'{total_target_tokens} 个 target tokens', flush=True)

    # ── Step 2: teacher forcing ──────────────────────────
    print('\n[c056] Step 2: teacher forcing...', flush=True)
    tf = {}
    for name in ['int4lmfp16', 'int4lmhead']:
        t0 = time.perf_counter()
        r = teacher_force(backends[name].dec_infer, all_sequences)
        tf[name] = r
        print(f'  {name:12s}: TOP-1={r["top1_rate"]:.4f}  '
              f'EOS={r["eos_rate"]:.4f}  n_steps={r["n_steps"]}  '
              f'({time.perf_counter()-t0:.1f}s)', flush=True)

    # ── Step 3: 端到端流式文本对比 ───────────────────────
    print('\n[c056] Step 3: 端到端流式（3 段，strategy=off）...', flush=True)
    e2e = {}
    for name in ['fp16', 'int4lmfp16', 'int4lmhead']:
        texts = []
        for start, end, label in TF_SEGMENTS:
            seg = audio_full[int(start * sr):int(end * sr)]
            t = stream_text(backends[name], seg)
            texts.append({'label': label, 'text': t})
        e2e[name] = texts
        print(f'  {name:12s}: ' + ' || '.join(
            t['text'][:38] for t in texts), flush=True)

    # token 级 diff：int4lmfp16 vs int4lmhead（相对 FP16 各自多少替换）
    tok = backends['fp16'].tokenizer
    diffs = {}
    for name in ['int4lmfp16', 'int4lmhead']:
        n_ref = n_sub = 0
        for a, b in zip(e2e['fp16'], e2e[name]):
            wa = tok.encode(a['text'], add_special_tokens=False)
            wb = tok.encode(b['text'], add_special_tokens=False)
            from difflib import SequenceMatcher
            sm = SequenceMatcher(a=wa, b=wb, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'replace':
                    n_sub += max(i2 - i1, j2 - j1)
                elif tag == 'delete':
                    n_sub += i2 - i1
                elif tag == 'insert':
                    n_sub += j2 - j1
            n_ref += len(wa)
        diffs[name] = {'sub_tokens': n_sub, 'ref_tokens': n_ref,
                       'sub_rate_pct': round(100.0 * n_sub / max(n_ref, 1), 2)}
        print(f'  {name:12s}: token 级替换 {n_sub}/{n_ref} '
              f'= {diffs[name]["sub_rate_pct"]}%', flush=True)

    out = {
        'generated': time.strftime('%Y-%m-%d %H:%M'),
        'segments': [s[2] for s in TF_SEGMENTS],
        'n_sequences': len(all_sequences),
        'n_target_tokens': total_target_tokens,
        'teacher_forcing': tf,
        'e2e_texts': e2e,
        'token_diffs_vs_fp16': diffs,
        'ir_mib': {
            'int8': os.path.getsize('models/ov-int8-past/'
                                    'openvino_decoder_model.bin') / 1024 ** 2,
            'int4lmfp16': os.path.getsize('models/ov-int4-lmfp16-past/'
                                          'openvino_decoder_model.bin') / 1024 ** 2,
            'int4lmhead': os.path.getsize('models/ov-int4-lmhead-past/'
                                          'openvino_decoder_model.bin') / 1024 ** 2,
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[c056] saved -> {OUT}', flush=True)

    # 小结
    a = tf['int4lmfp16']['top1_rate']
    b = tf['int4lmhead']['top1_rate']
    print('\n=== 小结 ===')
    print(f'int4lmfp16（现状）  top-1 = {a:.4f}')
    print(f'int4lmhead（what-if）top-1 = {b:.4f}  （lm_head 也 INT4）')
    print(f'lm_head INT4 的净代价: top-1 {100 * (b - a):+.2f} pp'
          f'（{total_target_tokens} 步）')
    print(f'端到端 token 替换率: int4lmfp16 {diffs["int4lmfp16"]["sub_rate_pct"]}% '
          f'→ int4lmhead {diffs["int4lmhead"]["sub_rate_pct"]}%')


if __name__ == '__main__':
    main()
