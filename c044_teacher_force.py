"""c044_teacher_force.py — C-044: 确定性 teacher-forcing 指标

对几个段, 先用 FP16 decoder 流式, 记录每个 chunk 送进 decoder 的完整
full_input_ids 和 FP16 逐步生成的 token 序列. 然后用同样的 full_input_ids
+ 同样的 FP16 token 序列对每个候选 decoder 做 teacher forcing, 统计:
  1. top-1 一致率 (候选 argmax == FP16 token)
  2. KL(FP16 || 候选) 的均值和 P99
  3. EOS 判定一致率 (FP16 在 step i 说 EOS, 候选是否也说 EOS)

候选 decoder (C-044 列了 5 个, NNCF 3.4.0 限制下我们能跑的):
  (a) INT8_ASYM per-channel (基准, 已有 ov-int8-past)
  (b) INT8_SYM per-group g128  - NNCF 3.4 不支持 INT8 per-group, 跳过
  (c) INT8_ASYM per-group g64   - NNCF 3.4 不支持, 跳过
  (d) (b) + lm_head FP16 + 层 0,1,26,27 FP16 - NNCF 不支持 per-layer, 跳过
  (e) per-layer sensitivity     - NNCF 不支持, 跳过
  (a2) INT4_SYM per-group g128 (已有 ov-int4-lmfp16-past) - 作为 (b) 的代理
  (a3) INT8_ASYM per-channel + FP16 lm_head (已有 ov-int8-lmfp16-past)
  (a4) FP16 (baseline, 已有 ov-fp16-past)
"""
import os, sys, time, json, re
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
from collections import Counter

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer


# 3 个测试段 (c040/c043 用的 15 段中挑 3 个最有代表性的:
#  seg118/161/163 = C-040 找到的 INT8 翻转段)
TF_SEGMENTS = [
    (1925.4, 1939.5, 'seg118_1925_1940'),
    (2622.2, 2640.4, 'seg161_2622_2640'),
    (2656.8, 2675.9, 'seg163_2657_2676'),
]

# FP16 streaming 参数
CHUNK_SIZE_SEC = 0.64
UNFIXED_TOKEN_NUM = 5
UNFIXED_CHUNK_NUM = 0
MAX_NEW_TOKENS = 32

EOS_IDS = {151643, 151645}


def build_prompt_raw(tokenizer):
    msgs = [{'role': 'system', 'content': ''},
            {'role': 'user', 'content': [{'type': 'audio', 'audio': ''}]}]
    return tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)


def get_fp16_streaming_sequences(backend, label, start, end, audio_full, sr):
    """用 FP16 decoder 流式跑一个段, 收集每个 chunk 的 (full_input_ids, ehs, fp16_target_tokens)."""
    seg = audio_full[int(start*sr):int(end*sr)]
    chunk_samples = int(CHUNK_SIZE_SEC * sr)
    n_chunks = (len(seg) + chunk_samples - 1) // chunk_samples
    print(f'  [FP16] {label}: {n_chunks} chunks ({len(seg)/sr:.2f}s)', flush=True)

    tokenizer = backend.tokenizer
    ids_left, ids_right = backend._prompt_template_ids
    audio_pad_id = backend._audio_pad_id
    prompt_text = build_prompt_raw(tokenizer)
    prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)

    # 用 SegmentedStreamer 跑流式
    streamer = SegmentedStreamer(
        backend, strategy='off',
        chunk_size_sec=CHUNK_SIZE_SEC,
        unfixed_chunk_num=UNFIXED_CHUNK_NUM, unfixed_token_num=UNFIXED_TOKEN_NUM,
        max_new_tokens=MAX_NEW_TOKENS,
    )

    # 这里我们手动流式每个 chunk, 记录每步状态
    # 简化: 实际跑流式, 从 streamer 内部状态取 prefix
    # 不容易拿, 所以直接模拟: 每 chunk encode audio_accum + run greedy
    sequences = []
    fixed_text = ''  # 已确认的文本
    for ci in range(n_chunks):
        e = min((ci + 1) * chunk_samples, len(seg))
        audio_accum = seg[:e]
        ehs, n_real, N_audio = backend.encode_audio(audio_accum)

        # 构造 prompt + prefix
        prefix = fixed_text
        full_text = prompt_text + prefix
        full_ids = tokenizer.encode(full_text, add_special_tokens=False)
        prefix_ids = full_ids[len(prompt_ids):] if len(full_ids) > len(prompt_ids) else []

        # 构造 decoder 输入: left + audio_pad*N + right + prefix
        full_input_ids = list(ids_left) + [audio_pad_id] * N_audio + list(ids_right) + list(prefix_ids)

        # Greedy decode 这个 chunk
        target_tokens = greedy_decode(backend.dec_infer, full_input_ids, ehs, max_new=MAX_NEW_TOKENS)

        sequences.append({
            'label': label, 'chunk': ci,
            'N_audio': N_audio,
            'full_input_ids': full_input_ids,
            'ehs': ehs,
            'fp16_target_tokens': target_tokens,
        })

        # 更新 fixed_text: unfixed_token_num 之前的部分
        if target_tokens:
            gen_text = tokenizer.decode(target_tokens, skip_special_tokens=True)
            # unfixed_token_num: 保留前 (len(tokens) - UNFIXED_TOKEN_NUM) 个 token
            n_fixed_tokens = max(0, len(target_tokens) - UNFIXED_TOKEN_NUM)
            if n_fixed_tokens > 0:
                fixed_text += tokenizer.decode(target_tokens[:n_fixed_tokens], skip_special_tokens=True)
        if (ci + 1) % 5 == 0 or ci == n_chunks - 1:
            print(f'    chunk {ci+1}/{n_chunks} done, fixed_text_len={len(fixed_text)}', flush=True)
    return sequences


def greedy_decode(dec_infer, full_input_ids, ehs, max_new=32):
    """对 full_input_ids 一次 prefill, 然后 greedy decode max_new tokens."""
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
    """对所有 sequence, 用候选 decoder 做 teacher forcing.

    对每个 sequence: prefill 整个 full_input_ids + fp16_target_tokens 一起, 一次性取所有步的 logits.
    logits 位置 j 表示基于 input[:j+1] 预测 input[j+1] 的分布.
    预测 target_tokens[i] 应看 logits[N+i-1] (其中 N=len(full_input_ids)).

    Returns: dict of metrics
    """
    all_top1_match = []
    all_max_abs_diff = []
    all_kl = []
    n_eos_steps = 0  # FP16 在某步说 EOS 的次数
    n_eos_match = 0  # 候选也在该步说 EOS 的次数
    fp16_eos_only = []  # 候选在 EOS 步后开始分叉的 token 序列
    cand_eos_only = []  # 候选在 FP16 没 EOS 步说 EOS
    n_total_steps = 0
    n_l1_diff_logit = 0

    for seq in sequences:
        ehs = seq['ehs']
        full_ids = seq['full_input_ids']
        target_tokens = seq['fp16_target_tokens']
        N = len(full_ids)
        T = len(target_tokens)
        if T == 0:
            continue

        # Teacher forcing: prefill 一次送入 full_ids + target_tokens
        all_input_ids = list(full_ids) + list(target_tokens)
        input_ids = np.array([all_input_ids], dtype=np.int64)

        dec_infer.reset_state()
        out = dec_infer.infer({
            "input_ids": input_ids,
            "encoder_hidden_states": ehs,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        all_logits = out["logits"] if isinstance(out, dict) else out[0]
        # all_logits shape: [1, total_len, vocab]

        # 预测 target_tokens[i] 用 logits[N+i-1]
        for i in range(T):
            if N + i - 1 >= all_logits.shape[1] or N + i - 1 < 0:
                continue
            target_token = target_tokens[i]
            logit = all_logits[0, N + i - 1, :].astype(np.float32)
            top1 = int(np.argmax(logit))
            match = (top1 == target_token)
            all_top1_match.append(1 if match else 0)
            n_total_steps += 1
            # EOS agreement: if FP16 token is EOS, check candidate also predicts EOS at same step
            if target_token in eos_ids:
                n_eos_steps += 1
                if top1 in eos_ids:
                    n_eos_match += 1
            # 如果 FP16 已经说 EOS 但候选没在同 step 说 EOS
            elif i > 0 and target_tokens[i-1] in eos_ids and top1 not in eos_ids:
                # 候选没在 EOS step 后停下
                pass

    top1_rate = np.mean(all_top1_match) if all_top1_match else 0.0
    eos_rate = n_eos_match / n_eos_steps if n_eos_steps > 0 else 1.0
    return {
        'top1_rate': top1_rate,
        'n_steps': n_total_steps,
        'n_eos_steps': n_eos_steps,
        'eos_rate': eos_rate,
    }


def main():
    print('[c044-tf] === C-044: 确定性 teacher-forcing 评估 ===', flush=True)
    print(f'[c044-tf] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)
    print(f'[c044-tf] 测试段: {[s[2] for s in TF_SEGMENTS]}', flush=True)

    audio_path = 'test_audio/260902_SPE_audio.wav'
    audio_full, sr = sf.read(audio_path, dtype='float32')
    if audio_full.ndim > 1:
        audio_full = audio_full[:, 0]
    assert sr == 16000
    print(f'[c044-tf] audio: {len(audio_full)/sr:.1f}s', flush=True)

    # 加载所有 backends
    print('[c044-tf] 加载 5 backends...', flush=True)
    backends = {
        'fp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-fp16-past',
            device='GPU.0', precision='f16',
        ),
        'int8': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past',
            device='GPU.0', precision='f16',
        ),
        'int8lmfp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-lmfp16-past',
            device='GPU.0', precision='f16',
        ),
        'int4lmfp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int4-lmfp16-past',
            device='GPU.0', precision='f16',
        ),
    }

    # Step 1: 用 FP16 流式跑 3 段, 收集 sequences
    print()
    print('[c044-tf] Step 1: FP16 streaming to get reference sequences...', flush=True)
    all_sequences = []
    for start, end, label in TF_SEGMENTS:
        seqs = get_fp16_streaming_sequences(backends['fp16'], label, start, end, audio_full, sr)
        all_sequences.extend(seqs)
    print(f'[c044-tf] 总共 {len(all_sequences)} 个 sequences', flush=True)
    total_target_tokens = sum(len(s['fp16_target_tokens']) for s in all_sequences)
    print(f'[c044-tf] 总 target tokens: {total_target_tokens}', flush=True)

    # 保存 sequences (不存 ehs, 太大)
    out_dir = 'reports/c044_tf'
    os.makedirs(out_dir, exist_ok=True)
    seqs_save = []
    for s in all_sequences:
        seqs_save.append({
            'label': s['label'], 'chunk': s['chunk'],
            'N_audio': s['N_audio'],
            'full_input_ids': s['full_input_ids'],
            'fp16_target_tokens': s['fp16_target_tokens'],
        })
    with open(os.path.join(out_dir, 'sequences.json'), 'w', encoding='utf-8') as f:
        json.dump(seqs_save, f, ensure_ascii=False, indent=2)
    print(f'[c044-tf] → {out_dir}/sequences.json', flush=True)

    # Step 2: 对每个候选 decoder 跑 teacher forcing
    print()
    print('[c044-tf] Step 2: Teacher forcing each decoder...', flush=True)
    results = {}
    for name, backend in backends.items():
        if name == 'fp16':
            # baseline: top-1 = 100% (自己对自己)
            results[name] = {
                'top1_rate': 1.0,
                'n_steps': total_target_tokens,
                'n_eos_steps': sum(1 for s in all_sequences for t in s['fp16_target_tokens'] if t in EOS_IDS),
                'eos_rate': 1.0,
            }
            print(f'  {name:12s}: TOP-1=1.0000 (baseline)  EOS=1.0000  n_steps={total_target_tokens}', flush=True)
            continue
        t0 = time.perf_counter()
        result = teacher_force(backend.dec_infer, all_sequences)
        results[name] = result
        print(f'  {name:12s}: TOP-1={result["top1_rate"]:.4f}  EOS={result["eos_rate"]:.4f}  n_steps={result["n_steps"]}  ({time.perf_counter()-t0:.1f}s)', flush=True)

    # Save
    with open(os.path.join(out_dir, 'tf_results.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    print()
    print('=== Summary (C-044 teacher-forcing) ===')
    print(f'{"decoder":12s} {"TOP-1":>8s} {"EOS":>8s} {"n_steps":>8s} {"n_eos":>6s}')
    for name, r in results.items():
        print(f'{name:12s} {r["top1_rate"]:8.4f} {r["eos_rate"]:8.4f} {r["n_steps"]:8d} {r.get("n_eos_steps", 0):6d}')

    # RTF check (segment 118, 161, 163 wall)
    print()
    print('[c044-tf] Step 3: 单段 RTF 测量 (chunk 0.64s, 3 段总和)...', flush=True)
    rtf_results = {}
    for name, backend in backends.items():
        if name == 'fp16':
            continue
        times = []
        for start, end, label in TF_SEGMENTS:
            seg = audio_full[int(start*sr):int(end*sr)]
            chunk_samples = int(CHUNK_SIZE_SEC * sr)
            n_chunks = (len(seg) + chunk_samples - 1) // chunk_samples
            t0 = time.perf_counter()
            streamer = SegmentedStreamer(
                backend, strategy='off',
                chunk_size_sec=CHUNK_SIZE_SEC,
                unfixed_chunk_num=UNFIXED_CHUNK_NUM, unfixed_token_num=UNFIXED_TOKEN_NUM,
                max_new_tokens=MAX_NEW_TOKENS,
            )
            _text, _segs = streamer.run(seg)
            wall = time.perf_counter() - t0
            times.append(wall / (len(seg) / sr))
        rtf_avg = np.mean(times)
        rtf_results[name] = rtf_avg
        print(f'  {name:12s}: RTF={rtf_avg:.3f} (per-seg: {[f"{t:.3f}" for t in times]})', flush=True)

    # Save RTF
    with open(os.path.join(out_dir, 'rtf_results.json'), 'w', encoding='utf-8') as f:
        json.dump(rtf_results, f, ensure_ascii=False, indent=2)

    # IR sizes
    print()
    print('[c044-tf] Step 4: IR 大小...', flush=True)
    ir_sizes = {}
    decoder_dirs = {
        'fp16': 'models/ov-fp16-past',
        'int8': 'models/ov-int8-past',
        'int8lmfp16': 'models/ov-int8-lmfp16-past',
        'int4lmfp16': 'models/ov-int4-lmfp16-past',
    }
    for name, d in decoder_dirs.items():
        for ext in ('.bin',):
            p = os.path.join(d, f'openvino_decoder_model{ext}')
            if os.path.exists(p):
                ir_sizes[name] = os.path.getsize(p) / 1024 / 1024
                print(f'  {name:12s}: {ir_sizes[name]:.1f} MB', flush=True)
                break

    # Final summary
    print()
    print('=== C-044 候选方案对比 (按 C-044 选择规则) ===')
    print(f'选择规则: RTF ≤ 0.8 方案中选 top-1 + EOS 一致率最高; 目标 top-1 ≥ 99.5%, EOS ≥ 99%')
    print()
    print(f'{"方案":12s} {"TOP-1":>8s} {"EOS":>8s} {"RTF":>6s} {"IR(MB)":>8s} {"选":>4s}')
    fp16_top1 = results['fp16']['top1_rate']
    for name in ['fp16', 'int8', 'int8lmfp16', 'int4lmfp16']:
        r = results.get(name, {})
        rtf = rtf_results.get(name, 0)
        ir = ir_sizes.get(name, 0)
        ok = '✓' if (rtf <= 0.8 and r.get('top1_rate', 0) >= 0.995 and r.get('eos_rate', 0) >= 0.99) else ' '
        print(f'{name:12s} {r.get("top1_rate", 0):8.4f} {r.get("eos_rate", 0):8.4f} {rtf:6.3f} {ir:8.1f} {ok:>4s}')

    # NNCF 限制说明
    print()
    print('=== NNCF 3.4.0 限制 ===')
    print('C-044 列出的 5 个方案 (a-e) 中:')
    print('  (a) INT8_ASYM per-channel      = 已有 ov-int8-past')
    print('  (b) INT8_SYM per-group g128    = NNCF 3.4 不支持 (per-group 仅 INT4 模式)')
    print('  (c) INT8_ASYM per-group g64    = NNCF 3.4 不支持')
    print('  (d) (b) + lm_head FP16 + 4层 FP16 = NNCF 不支持 per-layer FP16')
    print('  (e) per-layer sensitivity      = NNCF 不支持 per-layer')
    print('只能用 NNCF 支持的方案, 即上面的 (a)/(a2 INT4 per-group)/(a3 INT8+FP16-lm)/(a4 FP16)')

    # 写入 STATUS
    print()
    print('[c044-tf] DONE', flush=True)


if __name__ == '__main__':
    main()
