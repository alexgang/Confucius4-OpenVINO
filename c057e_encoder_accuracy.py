"""c057e_encoder_accuracy.py — C-057e: encoder INT4 的精度代价实测

问题：encoder 现在是 FP16（605.6 MiB）。压到 INT4（162.5 MiB，-73%）会掉多少精度？

方法（全部复用 C-044 的现成函数，保证口径完全一致）：
  Step 1  encoder hidden states 直接数值误差（rel_L2 / 余弦）—— 区分「数值扰动」
          和「真的影响识别」
  Step 2  用 FP16-decoder 流式收集的 (full_input_ids, ehs, fp16_target_tokens) 做
          teacher forcing。关键：给候选 backend 喂**它自己 encoder 产出的 ehs**，
          这样 top-1 差异 = encoder INT4 的净代价（decoder 固定 INT8，被控制住）
  Step 3  端到端流式 3 段，对比文本与 token 级 diff

用法：.venv python c057e_encoder_accuracy.py
输出：reports/c057_encoder_acc.json
"""
import os
import sys
import time
import json

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf
from difflib import SequenceMatcher

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer

from c044_teacher_force import (
    TF_SEGMENTS, EOS_IDS, CHUNK_SIZE_SEC, UNFIXED_TOKEN_NUM,
    UNFIXED_CHUNK_NUM, MAX_NEW_TOKENS, build_prompt_raw,
    get_fp16_streaming_sequences, teacher_force,
)

OUT = 'reports/c057_encoder_acc.json'
AUDIO = 'test_audio/<redacted>.wav'
ENC_FP16 = 'models/ov-encoder-segment-reviewer'
ENC_INT4 = 'models/ov-encoder-segment-reviewer-int4'
DEC_INT8 = 'models/ov-int8-past'


def stream_text(backend, seg):
    streamer = SegmentedStreamer(
        backend, strategy='off', chunk_size_sec=CHUNK_SIZE_SEC,
        unfixed_chunk_num=UNFIXED_CHUNK_NUM,
        unfixed_token_num=UNFIXED_TOKEN_NUM,
        max_new_tokens=MAX_NEW_TOKENS)
    return streamer.run(seg)[0]


def main():
    print('[c057e] === encoder INT4 精度代价实测 ===', flush=True)
    print(f'[c057e] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)
    print(f'[c057e] 测试段: {[s[2] for s in TF_SEGMENTS]}（C-044 同段同参数）',
          flush=True)

    audio_full, sr = sf.read(AUDIO, dtype='float32')
    if audio_full.ndim > 1:
        audio_full = audio_full[:, 0]

    print('[c057e] 加载 backends（decoder 固定 INT8，只换 encoder）...', flush=True)
    bf = SegmentEncoderOVBackend(encoder_dir=ENC_FP16, decoder_dir=DEC_INT8,
                                 device='GPU.0', precision='f16')
    bi = SegmentEncoderOVBackend(encoder_dir=ENC_INT4, decoder_dir=DEC_INT8,
                                 device='GPU.0', precision='f16')

    # ── Step 1: encoder 输出数值误差 ────────────────────
    print('\n[c057e] Step 1: encoder hidden states 数值误差...', flush=True)
    hd = []
    for start, end, label in TF_SEGMENTS:
        seg = audio_full[int(start * sr):int(end * sr)]
        cs = int(round(CHUNK_SIZE_SEC * sr))
        for ci, frac in [(0, 1.0), (1, 2.0)]:
            acc = seg[:int(len(seg) / frac)] if frac > 1 else seg
            e1, _, N = bf.encode_audio(acc)
            e2, _, _ = bi.encode_audio(acc)
            if N == 0:
                continue
            a = e1[0, :N, :].astype(np.float64)
            b = e2[0, :N, :].astype(np.float64)
            rel = float(np.linalg.norm(a - b) / max(np.linalg.norm(a), 1e-9))
            cos = float(np.sum(a * b) / (np.linalg.norm(a) * np.linalg.norm(b)))
            hd.append({'label': label, 'chunk': ci, 'n_audio_tokens': int(N),
                       'rel_l2_pct': round(100 * rel, 4),
                       'cosine': round(cos, 6)})
            print(f'  {label} chunk{ci}: N={N:3d}  '
                  f'rel_L2={100*rel:6.3f}%  cos={cos:.6f}', flush=True)
        del cs

    # ── Step 2: teacher forcing ─────────────────────────
    # 参考序列用 FP16 decoder + FP16 encoder 生成（与 C-044 同源）
    print('\n[c057e] Step 2a: 生成参考序列（FP16 enc + INT8 dec）...', flush=True)
    ref_seqs = []
    for start, end, label in TF_SEGMENTS:
        ref_seqs.extend(get_fp16_streaming_sequences(bf, label, start, end,
                                                     audio_full, sr))
    n_tok = sum(len(s['fp16_target_tokens']) for s in ref_seqs)
    print(f'  {len(ref_seqs)} sequences / {n_tok} target tokens', flush=True)

    # 候选序列：把 ref 里的 ehs 换成「候选自己 encoder 产出」的，其余
    # （full_input_ids / fp16_target_tokens）保持不变 —— 差异纯粹来自 encoder
    print('\n[c057e] Step 2b: 用 INT4 encoder 重算每段的 ehs...', flush=True)
    cand_seqs = []
    for start, end, label in TF_SEGMENTS:
        seg = audio_full[int(start * sr):int(end * sr)]
        cs = int(round(CHUNK_SIZE_SEC * sr))
        n_chunks = (len(seg) + cs - 1) // cs
        for ci in range(n_chunks):
            acc = seg[:min((ci + 1) * cs, len(seg))]
            ehs_i4, _, N_i4 = bi.encode_audio(acc)
            cand_seqs.append({'label': label, 'chunk': ci,
                              'N_audio': int(N_i4), 'ehs': ehs_i4})
    # 与 ref_seqs 一一对应（同 label 同 chunk 顺序）
    assert len(cand_seqs) == len(ref_seqs), \
        f'{len(cand_seqs)} vs {len(ref_seqs)}'
    merged = []
    for r, c in zip(ref_seqs, cand_seqs):
        assert r['label'] == c['label']
        m = dict(r)
        m['ehs'] = c['ehs']
        merged.append(m)

    tf = {}
    for name, b, seqs in [('enc_fp16', bf, ref_seqs), ('enc_int4', bi, merged)]:
        t0 = time.perf_counter()
        r = teacher_force(b.dec_infer, seqs)
        tf[name] = r
        print(f'  {name:10s}: TOP-1={r["top1_rate"]:.4f}  '
              f'EOS={r["eos_rate"]:.4f}  n_steps={r["n_steps"]}  '
              f'({time.perf_counter()-t0:.1f}s)', flush=True)

    # ── Step 3: 端到端 ─────────────────────────────────
    print('\n[c057e] Step 3: 端到端流式 3 段...', flush=True)
    e2e = {}
    for name, b in [('enc_fp16', bf), ('enc_int4', bi)]:
        texts = []
        for start, end, label in TF_SEGMENTS:
            seg = audio_full[int(start * sr):int(end * sr)]
            texts.append({'label': label, 'text': stream_text(b, seg)})
        e2e[name] = texts
        print(f'  {name:10s}: ' + ' || '.join(t['text'][:34] for t in texts),
              flush=True)

    tok = bf.tokenizer
    n_ref = n_ed = 0
    for a, b in zip(e2e['enc_fp16'], e2e['enc_int4']):
        wa = tok.encode(a['text'], add_special_tokens=False)
        wb = tok.encode(b['text'], add_special_tokens=False)
        for tag, i1, i2, j1, j2 in SequenceMatcher(
                a=wa, b=wb, autojunk=False).get_opcodes():
            if tag == 'replace':
                n_ed += max(i2 - i1, j2 - j1)
            elif tag == 'delete':
                n_ed += i2 - i1
            elif tag == 'insert':
                n_ed += j2 - j1
        n_ref += len(wa)
    diff = {'edits': n_ed, 'ref_tokens': n_ref,
            'rate_pct': round(100.0 * n_ed / max(n_ref, 1), 2)}
    print(f'  token 级编辑 {n_ed}/{n_ref} = {diff["rate_pct"]}%', flush=True)

    out = {
        'generated': time.strftime('%Y-%m-%d %H:%M'),
        'segments': [s[2] for s in TF_SEGMENTS],
        'chunk_ms': CHUNK_SIZE_SEC * 1000,
        'hidden_diff': hd,
        'n_sequences': len(ref_seqs),
        'teacher_forcing': tf,
        'e2e_texts': e2e,
        'token_diff': diff,
        'ir_mib': {
            'enc_fp16': os.path.getsize(f'{ENC_FP16}/openvino_encoder_model.bin')
                        / 1024 ** 2,
            'enc_int4': os.path.getsize(f'{ENC_INT4}/openvino_encoder_model.bin')
                        / 1024 ** 2,
        },
    }
    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}', flush=True)
    d = 100 * (tf['enc_int4']['top1_rate'] - tf['enc_fp16']['top1_rate'])
    print(f'\n=== 小结 ===')
    print(f'encoder INT4 净代价: top-1 {d:+.2f} pp（{tf["enc_fp16"]["n_steps"]} 步）')
    print(f'hidden rel_L2 均值: '
          f'{np.mean([h["rel_l2_pct"] for h in hd]):.3f}%  '
          f'cos 均值 {np.mean([h["cosine"] for h in hd]):.6f}')


if __name__ == '__main__':
    main()
