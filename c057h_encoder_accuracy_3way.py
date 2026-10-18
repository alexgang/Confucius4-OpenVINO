"""c057h_encoder_accuracy_3way.py — C-057h: encoder FP16/INT8/INT4 三方精度对比

背景：
  C-057 确认 encoder 现状是纯 FP16（605.6 MiB）。
  C-057e 测出 INT4_SYM g128（162.5 MiB）的 teacher-forcing top-1 掉 1.80 pp。
  C-057g 导出 INT8_ASYM/SYM（均约 303.8 MiB）—— 假设它是「省内存」诉求下的甜点。

本脚本把精度实验参数化为 encoder 集合，一次跑完：
  Step 1  encoder hidden states 数值误差（rel_L2 / cosine），对 FP16 基线
  Step 2  teacher forcing（C-044 同 3 段 / 82 seq / 721 步，decoder 固定 INT8）
          —— 每个候选喂「自己 encoder 产出的 ehs」，差异纯粹来自 encoder
  Step 3  端到端流式 3 段 + token 级 diff vs FP16

用法：.venv python c057h_encoder_accuracy_3way.py
输出：reports/c057_encoder_acc_3way.json
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
    TF_SEGMENTS, CHUNK_SIZE_SEC, UNFIXED_TOKEN_NUM,
    UNFIXED_CHUNK_NUM, MAX_NEW_TOKENS,
    get_fp16_streaming_sequences, teacher_force,
)

OUT = 'reports/c057_encoder_acc_3way.json'
AUDIO = 'test_audio/<redacted>.wav'
DEC_INT8 = 'models/ov-int8-past'

# (key, 目录, 展示名)
ENCODERS = [
    ('enc_fp16', 'models/ov-encoder-segment-reviewer', 'FP16 (现状)'),
    ('enc_int8asym', 'models/ov-encoder-segment-reviewer-int8asym',
     'INT8_ASYM per-ch'),
    ('enc_int8sym', 'models/ov-encoder-segment-reviewer-int8sym',
     'INT8_SYM per-ch'),
    ('enc_int4', 'models/ov-encoder-segment-reviewer-int4',
     'INT4_SYM g128'),
]
BASE = 'enc_fp16'


def stream_text(backend, seg):
    streamer = SegmentedStreamer(
        backend, strategy='off', chunk_size_sec=CHUNK_SIZE_SEC,
        unfixed_chunk_num=UNFIXED_CHUNK_NUM,
        unfixed_token_num=UNFIXED_TOKEN_NUM,
        max_new_tokens=MAX_NEW_TOKENS)
    return streamer.run(seg)[0]


def main():
    print('[c057h] === encoder FP16 / INT8 / INT4 三方精度对比 ===', flush=True)
    print(f'[c057h] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    audio_full, sr = sf.read(AUDIO, dtype='float32')
    if audio_full.ndim > 1:
        audio_full = audio_full[:, 0]
    print(f'[c057h] 测试段: {[s[2] for s in TF_SEGMENTS]}（C-044 同段同参数）',
          flush=True)

    sizes = {k: os.path.getsize(f'{d}/openvino_encoder_model.bin') / 1024 ** 2
             for k, d, _ in ENCODERS}
    print('[c057h] encoder IR 体积：' +
          '  '.join(f'{k}={v:.1f}MiB' for k, v in sizes.items()), flush=True)

    backends = {}
    for k, d, _ in ENCODERS:
        print(f'[c057h] 加载 {k} ...', flush=True)
        backends[k] = SegmentEncoderOVBackend(
            encoder_dir=d, decoder_dir=DEC_INT8,
            device='GPU.0', precision='f16')

    # ── Step 1: hidden states 数值误差（对 FP16 基线）──────
    print('\n[c057h] Step 1: encoder hidden states 数值误差...', flush=True)
    hd = {k: [] for k, _, _ in ENCODERS}
    for start, end, label in TF_SEGMENTS:
        seg = audio_full[int(start * sr):int(end * sr)]
        cs = int(round(CHUNK_SIZE_SEC * sr))
        n_chunks = (len(seg) + cs - 1) // cs
        for ci in (0, min(1, n_chunks - 1)):
            acc = seg[:min((ci + 1) * cs, len(seg))]
            _, _, N = backends[BASE].encode_audio(acc)
            if N == 0:
                continue
            a = backends[BASE].encode_audio(acc)[0][0, :N, :].astype(np.float64)
            for k, _, _ in ENCODERS:
                if k == BASE:
                    hd[k].append({'label': label, 'chunk': ci,
                                  'n_audio_tokens': int(N),
                                  'rel_l2_pct': 0.0, 'cosine': 1.0})
                    continue
                b = backends[k].encode_audio(acc)[0][0, :N, :].astype(np.float64)
                rel = float(np.linalg.norm(a - b) / max(np.linalg.norm(a), 1e-9))
                cos = float(np.sum(a * b) /
                            (np.linalg.norm(a) * np.linalg.norm(b)))
                hd[k].append({'label': label, 'chunk': ci,
                              'n_audio_tokens': int(N),
                              'rel_l2_pct': round(100 * rel, 4),
                              'cosine': round(cos, 6)})
    for k, name in [(k, n) for k, _, n in ENCODERS]:
        rs = [h['rel_l2_pct'] for h in hd[k]]
        cs_ = [h['cosine'] for h in hd[k]]
        print(f'  {name:<18} rel_L2={np.mean(rs):6.3f}%  '
              f'cos={np.mean(cs_):.6f}', flush=True)

    # ── Step 2: teacher forcing ───────────────────────────
    print('\n[c057h] Step 2a: 生成参考序列（FP16 enc + INT8 dec）...', flush=True)
    ref_seqs = []
    for start, end, label in TF_SEGMENTS:
        ref_seqs.extend(get_fp16_streaming_sequences(
            backends[BASE], label, start, end, audio_full, sr))
    print(f'  {len(ref_seqs)} sequences / '
          f'{sum(len(s["fp16_target_tokens"]) for s in ref_seqs)} target tokens',
          flush=True)

    # 每个候选：用自己 encoder 重算每段的 ehs，其余字段不动
    tf = {}
    for k, d, name in ENCODERS:
        if k == BASE:
            seqs = ref_seqs
        else:
            seqs = []
            for start, end, label in TF_SEGMENTS:
                seg = audio_full[int(start * sr):int(end * sr)]
                cs = int(round(CHUNK_SIZE_SEC * sr))
                n_chunks = (len(seg) + cs - 1) // cs
                for ci in range(n_chunks):
                    acc = seg[:min((ci + 1) * cs, len(seg))]
                    ehs, _, N = backends[k].encode_audio(acc)
                    seqs.append({'ehs': ehs})
            assert len(seqs) == len(ref_seqs), f'{len(seqs)} vs {len(ref_seqs)}'
            merged = []
            for r, c in zip(ref_seqs, seqs):
                m = dict(r)
                m['ehs'] = c['ehs']
                merged.append(m)
            seqs = merged
        t0 = time.perf_counter()
        r = teacher_force(backends[k].dec_infer, seqs)
        tf[k] = r
        print(f'  {name:<18} TOP-1={r["top1_rate"]:.4f}  '
              f'EOS={r["eos_rate"]:.4f}  n={r["n_steps"]}  '
              f'({time.perf_counter()-t0:.1f}s)', flush=True)

    # ── Step 3: 端到端 ────────────────────────────────────
    print('\n[c057h] Step 3: 端到端流式 3 段...', flush=True)
    e2e = {}
    for k, d, name in ENCODERS:
        texts = []
        for start, end, label in TF_SEGMENTS:
            seg = audio_full[int(start * sr):int(end * sr)]
            texts.append({'label': label, 'text': stream_text(backends[k], seg)})
        e2e[k] = texts
        print(f'  {name:<18} ' +
              ' || '.join(t['text'][:28] for t in texts), flush=True)

    tok = backends[BASE].tokenizer
    diffs = {}
    for k, _, name in ENCODERS:
        if k == BASE:
            continue
        n_ref = n_ed = 0
        for a, b in zip(e2e[BASE], e2e[k]):
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
        diffs[k] = {'edits': n_ed, 'ref_tokens': n_ref,
                    'rate_pct': round(100.0 * n_ed / max(n_ref, 1), 2)}
        print(f'  {name:<18} token 编辑 {n_ed}/{n_ref} = '
              f'{diffs[k]["rate_pct"]}%', flush=True)

    base_top1 = tf[BASE]['top1_rate']
    summary = {k: {
        'name': n,
        'ir_mib': round(sizes[k], 1),
        'ir_pct_of_fp16': round(100 * sizes[k] / sizes[BASE], 1),
        'rel_l2_pct': round(float(np.mean([h['rel_l2_pct'] for h in hd[k]])), 3),
        'cosine': round(float(np.mean([h['cosine'] for h in hd[k]])), 6),
        'top1': round(tf[k]['top1_rate'], 4),
        'top1_delta_pp': round(100 * (tf[k]['top1_rate'] - base_top1), 2),
        'eos': round(tf[k]['eos_rate'], 4),
        'token_edit_pct': diffs.get(k, {}).get('rate_pct', 0.0),
    } for k, _, n in ENCODERS}

    out = {
        'generated': time.strftime('%Y-%m-%d %H:%M'),
        'segments': [s[2] for s in TF_SEGMENTS],
        'chunk_ms': CHUNK_SIZE_SEC * 1000,
        'decoder': DEC_INT8,
        'n_sequences': len(ref_seqs),
        'n_target_tokens': sum(len(s['fp16_target_tokens'])
                               for s in ref_seqs),
        'summary': summary,
        'hidden_diff': hd,
        'teacher_forcing': tf,
        'e2e_texts': e2e,
        'token_diffs': diffs,
    }
    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}', flush=True)

    print(f'\n{"配置":<18}{"IR MiB":>9}{"占比":>8}{"rel_L2":>9}'
          f'{"cos":>10}{"top-1":>9}{"Δpp":>8}{"tok编辑":>9}')
    for k, _, n in ENCODERS:
        s = summary[k]
        print(f'{n:<18}{s["ir_mib"]:>9.1f}{s["ir_pct_of_fp16"]:>7.0f}%'
              f'{s["rel_l2_pct"]:>8.2f}%{s["cosine"]:>10.5f}'
              f'{s["top1"]:>9.4f}{s["top1_delta_pp"]:>+8.2f}'
              f'{s["token_edit_pct"]:>8.2f}%')


if __name__ == '__main__':
    main()
