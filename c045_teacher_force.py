"""c045_teacher_force.py — C-045: 候选 decoder 的确定性 teacher-forcing 评估

两阶段:
  Phase A (全部候选, 只编译 decoder): top-1 一致率 + EOS 一致率 vs FP16 目标序列
  Phase B (领先候选 + int8 基线, 完整 backend): 3 段 RTF 实测

序列收集 (FP16 backend, 3 段 seg118/161/163, chunk 0.64s, unfixed 0/5, max_new 32)
与 c044_teacher_force.py 完全一致, 保证可比 (int8 基线应复现 94.12%/63.41%)。

候选: models/ov-{name}-past (c045_export_variants.py 产物), 跳过导出失败的。
"""
import os, sys, time, json, glob, traceback
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer

ENC_DIR = 'models/ov-encoder-segment-reviewer'
FP16_DIR = 'models/ov-fp16-past'
INT8_DIR = 'models/ov-int8-past'

TF_SEGMENTS = [
    (1925.4, 1939.5, 'seg118_1925_1940'),
    (2622.2, 2640.4, 'seg161_2622_2640'),
    (2656.8, 2675.9, 'seg163_2657_2676'),
]
CHUNK_SIZE_SEC = 0.64
UNFIXED_TOKEN_NUM = 5
UNFIXED_CHUNK_NUM = 0
MAX_NEW_TOKENS = 32
EOS_IDS = {151643, 151645}

# Phase A 全部候选; Phase B (RTF) 只测 int8 + top-1 >= 该阈值的候选 + 全场最佳
RTF_TOP1_THRESHOLD = 0.96

CANDIDATES = ['int8', 'mixf2', 'mixl2', 'mix4', 'mixf4', 'mixl4',
              'mix8', 'mixf8', 'mixl8', 'mix12', 'mix16', 'int4lmfp16']

OUT_DIR = 'reports/c045_tf'


def log(msg):
    print(msg, flush=True)


DIR_MAP = {
    'int8': INT8_DIR,
    'int4lmfp16': 'models/ov-int4-lmfp16-past',
}


def decoder_dir_of(name):
    return DIR_MAP.get(name, f'models/ov-{name}-past')


def build_prompt_raw(tokenizer):
    msgs = [{'role': 'system', 'content': ''},
            {'role': 'user', 'content': [{'type': 'audio', 'audio': ''}]}]
    return tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)


def collect_sequences(backend, label, start, end, audio_full, sr):
    """FP16 流式跑一段, 收集每 chunk 的 (full_input_ids, ehs, fp16_target_tokens)."""
    seg = audio_full[int(start * sr):int(end * sr)]
    chunk_samples = int(CHUNK_SIZE_SEC * sr)
    n_chunks = (len(seg) + chunk_samples - 1) // chunk_samples
    log(f'  [FP16] {label}: {n_chunks} chunks ({len(seg)/sr:.2f}s)')

    tokenizer = backend.tokenizer
    ids_left, ids_right = backend._prompt_template_ids
    audio_pad_id = backend._audio_pad_id
    prompt_text = build_prompt_raw(tokenizer)
    prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)

    sequences = []
    fixed_text = ''
    for ci in range(n_chunks):
        e = min((ci + 1) * chunk_samples, len(seg))
        audio_accum = seg[:e]
        ehs, n_real, N_audio = backend.encode_audio(audio_accum)
        full_text = prompt_text + fixed_text
        full_ids = tokenizer.encode(full_text, add_special_tokens=False)
        prefix_ids = full_ids[len(prompt_ids):] if len(full_ids) > len(prompt_ids) else []
        full_input_ids = list(ids_left) + [audio_pad_id] * N_audio + list(ids_right) + list(prefix_ids)
        target_tokens = greedy_decode(backend.dec_infer, full_input_ids, ehs, max_new=MAX_NEW_TOKENS)
        sequences.append({
            'label': label, 'chunk': ci, 'N_audio': N_audio,
            'full_input_ids': full_input_ids, 'ehs': ehs,
            'fp16_target_tokens': target_tokens,
        })
        if target_tokens:
            n_fixed = max(0, len(target_tokens) - UNFIXED_TOKEN_NUM)
            if n_fixed > 0:
                fixed_text += tokenizer.decode(target_tokens[:n_fixed], skip_special_tokens=True)
        if (ci + 1) % 5 == 0 or ci == n_chunks - 1:
            log(f'    chunk {ci+1}/{n_chunks} done, fixed_text_len={len(fixed_text)}')
    return sequences


def greedy_decode(dec_infer, full_input_ids, ehs, max_new=32):
    ehs_dummy = ehs[:, :1, :]
    dec_infer.reset_state()
    out = dec_infer.infer({
        "input_ids": np.array([full_input_ids], dtype=np.int64),
        "encoder_hidden_states": ehs,
        "beam_idx": np.array([0], dtype=np.int32),
    }, share_inputs=True)
    logits = out["logits"] if isinstance(out, dict) else out[0]
    next_id = int(np.argmax(logits[0, -1, :]))
    generated = [next_id]
    for _ in range(max_new - 1):
        if next_id in EOS_IDS:
            break
        out = dec_infer.infer({
            "input_ids": np.array([[next_id]], dtype=np.int64),
            "encoder_hidden_states": ehs_dummy,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        next_id = int(np.argmax(logits[0, -1, :]))
        generated.append(next_id)
    return generated


def teacher_force(dec_infer, sequences, eos_ids=EOS_IDS):
    all_top1 = []
    n_eos_steps = 0
    n_eos_match = 0
    n_total = 0
    for seq in sequences:
        ehs = seq['ehs']
        full_ids = seq['full_input_ids']
        target_tokens = seq['fp16_target_tokens']
        N = len(full_ids)
        T = len(target_tokens)
        if T == 0:
            continue
        all_input_ids = list(full_ids) + list(target_tokens)
        dec_infer.reset_state()
        out = dec_infer.infer({
            "input_ids": np.array([all_input_ids], dtype=np.int64),
            "encoder_hidden_states": ehs,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        all_logits = out["logits"] if isinstance(out, dict) else out[0]
        for i in range(T):
            pos = N + i - 1
            if pos >= all_logits.shape[1] or pos < 0:
                continue
            target_token = target_tokens[i]
            logit = all_logits[0, pos, :].astype(np.float32)
            top1 = int(np.argmax(logit))
            all_top1.append(1 if top1 == target_token else 0)
            n_total += 1
            if target_token in eos_ids:
                n_eos_steps += 1
                if top1 in eos_ids:
                    n_eos_match += 1
    return {
        'top1_rate': float(np.mean(all_top1)) if all_top1 else 0.0,
        'n_steps': n_total,
        'n_eos_steps': n_eos_steps,
        'eos_rate': (n_eos_match / n_eos_steps) if n_eos_steps > 0 else 1.0,
    }


def compile_decoder_only(decoder_dir):
    """只编译 decoder (不含 encoder), 返回 (dec_infer, ir_mb)."""
    import openvino as ov
    core = ov.Core()
    core.set_property({'CACHE_DIR': './ov_cache'})
    model = core.read_model(
        model=os.path.join(decoder_dir, 'openvino_decoder_model.xml'),
        weights=os.path.join(decoder_dir, 'openvino_decoder_model.bin'),
    )
    compiled = core.compile_model(model, 'GPU.0',
                                  {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f16'})
    ir_mb = os.path.getsize(os.path.join(decoder_dir, 'openvino_decoder_model.bin')) / 1024 / 1024
    return compiled.create_infer_request(), ir_mb


def measure_rtf(decoder_dir, audio_full, sr):
    """完整 backend 跑 3 段 (strategy off), 返回平均 RTF."""
    backend = SegmentEncoderOVBackend(
        encoder_dir=ENC_DIR, decoder_dir=decoder_dir,
        device='GPU.0', precision='f16',
    )
    times = []
    for start, end, label in TF_SEGMENTS:
        seg = audio_full[int(start * sr):int(end * sr)]
        streamer = SegmentedStreamer(
            backend, strategy='off',
            chunk_size_sec=CHUNK_SIZE_SEC,
            unfixed_chunk_num=UNFIXED_CHUNK_NUM, unfixed_token_num=UNFIXED_TOKEN_NUM,
            max_new_tokens=MAX_NEW_TOKENS,
            enable_hallucination_reset=False,
        )
        t0 = time.perf_counter()
        streamer.run(seg)
        times.append((time.perf_counter() - t0) / (len(seg) / sr))
    del backend
    return float(np.mean(times)), [round(t, 3) for t in times]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    log(f'[c045-tf] updated: {time.strftime("%Y-%m-%d %H:%M")}')

    audio_path = 'test_audio/<redacted>.wav'
    audio_full, sr = sf.read(audio_path, dtype='float32')
    if audio_full.ndim > 1:
        audio_full = audio_full[:, 0]
    assert sr == 16000

    # Step 1: FP16 收集序列
    log('[c045-tf] Step 1: FP16 streaming → reference sequences ...')
    fp16_backend = SegmentEncoderOVBackend(
        encoder_dir=ENC_DIR, decoder_dir=FP16_DIR, device='GPU.0', precision='f16')
    all_sequences = []
    for start, end, label in TF_SEGMENTS:
        all_sequences.extend(collect_sequences(fp16_backend, label, start, end, audio_full, sr))
    total_target = sum(len(s['fp16_target_tokens']) for s in all_sequences)
    n_eos_total = sum(1 for s in all_sequences for t in s['fp16_target_tokens'] if t in EOS_IDS)
    log(f'[c045-tf] {len(all_sequences)} sequences, {total_target} target tokens, {n_eos_total} EOS steps')

    with open(os.path.join(OUT_DIR, 'sequences_meta.json'), 'w', encoding='utf-8') as f:
        json.dump({'n_sequences': len(all_sequences), 'n_target_tokens': total_target,
                   'n_eos_steps': n_eos_total}, f)
    del fp16_backend

    # Step 2: Phase A — 全部候选 teacher forcing (只编译 decoder)
    log('')
    log('[c045-tf] Step 2: Phase A — teacher forcing all candidates ...')
    results = {}
    for name in CANDIDATES:
        d = decoder_dir_of(name)
        if not os.path.exists(os.path.join(d, 'openvino_decoder_model.xml')):
            log(f'  {name:10s}: SKIP (IR 不存在: {d})')
            continue
        try:
            t0 = time.perf_counter()
            infer_req, ir_mb = compile_decoder_only(d)
            t_load = time.perf_counter() - t0
            t1 = time.perf_counter()
            r = teacher_force(infer_req, all_sequences)
            r['ir_mb'] = round(ir_mb, 1)
            r['eval_s'] = round(time.perf_counter() - t1, 1)
            results[name] = r
            log(f"  {name:10s}: TOP-1={r['top1_rate']:.4f}  EOS={r['eos_rate']:.4f}  "
                f"IR={r['ir_mb']:7.1f}MB  (load {t_load:.0f}s, eval {r['eval_s']:.0f}s)")
            del infer_req
            import gc
            gc.collect()
        except Exception as e:
            log(f'  {name:10s}: FAILED {type(e).__name__}: {e}')
            log(traceback.format_exc())

    # Step 3: Phase B — RTF for int8 + top-1>=阈值 + 最佳
    log('')
    log('[c045-tf] Step 3: Phase B — RTF (完整 backend, 3 段) ...')
    ranked = sorted(results.items(), key=lambda kv: kv[1]['top1_rate'], reverse=True)
    rtf_names = set(['int8'])
    for name, r in ranked:
        if r['top1_rate'] >= RTF_TOP1_THRESHOLD:
            rtf_names.add(name)
    if ranked:
        rtf_names.add(ranked[0][0])
    rtf_results = {}
    for name in sorted(rtf_names):
        d = decoder_dir_of(name)
        try:
            t0 = time.perf_counter()
            rtf, per = measure_rtf(d, audio_full, sr)
            rtf_results[name] = rtf
            if name in results:
                results[name]['rtf'] = round(rtf, 3)
                results[name]['rtf_per_seg'] = per
            log(f'  {name:10s}: RTF={rtf:.3f}  per-seg={per}  ({time.perf_counter()-t0:.0f}s)')
        except Exception as e:
            log(f'  {name:10s}: RTF FAILED {type(e).__name__}: {e}')

    # 汇总
    log('')
    log('=== C-045 候选对比 (FP16 参考: top-1=1.0, RTF≈1.166) ===')
    log(f"{'decoder':10s} {'TOP-1':>8s} {'EOS':>8s} {'RTF':>6s} {'IR(MB)':>8s}")
    for name in ['fp16'] + [n for n, _ in ranked]:
        if name == 'fp16':
            log(f"{'fp16':10s} {1.0:8.4f} {1.0:8.4f} {'~1.166':>6s} {3281.7:8.1f}")
            continue
        r = results[name]
        rtf = f"{r.get('rtf', float('nan')):.3f}" if 'rtf' in r else '  -  '
        log(f"{name:10s} {r['top1_rate']:8.4f} {r['eos_rate']:8.4f} {rtf:>6s} {r['ir_mb']:8.1f}")

    out = os.path.join(OUT_DIR, 'tf_results.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'sequences': {'n': len(all_sequences), 'target_tokens': total_target,
                                 'eos_steps': n_eos_total},
                   'results': results, 'rtf': rtf_results}, f, ensure_ascii=False, indent=2)
    log(f'[c045-tf] → {out}')
    log('[c045-tf] DONE')


if __name__ == '__main__':
    main()
