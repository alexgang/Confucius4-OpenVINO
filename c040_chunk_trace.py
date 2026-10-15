"""c040_chunk_trace.py — C-040#2: per-chunk trace seg 67/118/161

对每个段, 跑 (i) OV INT8 vs (ii) OV FP16 vs (iii) torch, 逐 chunk 记录:
- prefix_ids (完整 token 列表)
- gen_ids (本 chunk 生成)
- raw_decoded
- fixed_text (已 commit 部分)

找第一个分叉 chunk: 对比 INT8 vs FP16 vs torch, 看 prefix 相同但 gen 不同 还是 prefix 就不同。
"""
import os, sys, time, json, re
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '1')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

# stdout 强制 UTF-8 (Windows GBK 兜底)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf
import torch
from transformers import AutoTokenizer

from segment_encoder_backend import SegmentEncoderOVBackend, total_aftercnn_len
from backends import extract_audio_features, SAMPLE_RATE


# C-040 指定的 2 段 + seg 161 (INT8 唯一出问题的)
TRACE_SEGMENTS = [
    (1086.3, 1102.4, 'seg67'),
    (1925.4, 1939.5, 'seg118'),
    (2622.2, 2640.4, 'seg161'),  # 额外: INT8 n4=26
]


def already_done(label, out_dir):
    return os.path.exists(os.path.join(out_dir, f'{label}_trace.json'))


def main():
    print('[c040-trace] === per-chunk trace seg 67/118/161 (i INT8 vs ii FP16 vs iii torch) ===', flush=True)
    print(f'[c040-trace] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    # 加载
    print('[c040-trace] 加载 3 backends + segment encoder + tokenizer...', flush=True)
    backends = {
        'int8': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past',
            device='GPU.0', precision='f16',
        ),
        'fp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-fp16-past',
            device='GPU.0', precision='f16',
        ),
    }
    tokenizer = backends['int8'].tokenizer
    ids_left, ids_right = backends['int8']._prompt_template_ids
    audio_pad_id = backends['int8']._audio_pad_id

    # torch
    from qwen_asr.core.transformers_backend import Qwen3ASRForConditionalGeneration
    thinker = Qwen3ASRForConditionalGeneration.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager'
    ).thinker
    thinker.eval()

    def ov_greedy_log(dec_infer, ehs, prefix_ids, max_new_tokens):
        """Returns (gen_ids, first_chunk_logits_top5_first_token_id)."""
        N = ehs.shape[1]
        full_ids = list(ids_left) + [audio_pad_id] * N + list(ids_right) + list(prefix_ids)
        input_ids = np.array([full_ids], dtype=np.int64)
        ehs_dummy = ehs[:, :1, :]

        dec_infer.reset_state()
        out = dec_infer.infer({
            "input_ids": input_ids,
            "encoder_hidden_states": ehs,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        # 保存 top-5 供对比
        top5 = np.argsort(logits[0, -1, :])[-5:][::-1].tolist()
        top5_logits = logits[0, -1, top5].tolist()
        next_id = int(top5[0])
        generated = [next_id]
        eos_ids = {151643, 151645, tokenizer.eos_token_id}
        for _ in range(max_new_tokens - 1):
            if next_id in eos_ids:
                break
            out = dec_infer.infer({
                "input_ids": np.array([[next_id]], dtype=np.int64),
                "encoder_hidden_states": ehs_dummy,
                "beam_idx": np.array([0], dtype=np.int32),
            }, share_inputs=True)
            logits = out["logits"] if isinstance(out, dict) else out[0]
            next_id = int(np.argmax(logits[0, -1, :]))
            generated.append(next_id)
        return generated, top5, top5_logits

    def torch_greedy_log(thinker, ehs_np, prefix_ids, max_new_tokens):
        N = ehs_np.shape[1]
        full_ids = list(ids_left) + [audio_pad_id] * N + list(ids_right) + list(prefix_ids)
        full_ids_t = torch.tensor([full_ids], dtype=torch.long)
        embed = thinker.get_input_embeddings()
        inputs_embeds = embed(full_ids_t)
        ehs_t = torch.from_numpy(ehs_np).to(inputs_embeds.dtype)
        audio_mask = (full_ids_t == audio_pad_id).unsqueeze(-1)
        inputs_embeds = inputs_embeds.masked_scatter(audio_mask, ehs_t)
        eos_ids = {151643, 151645, tokenizer.eos_token_id}
        with torch.no_grad():
            out = thinker(inputs_embeds=inputs_embeds, use_cache=True)
            past = out.past_key_values
            top5 = torch.topk(out.logits[0, -1, :], 5).indices.tolist()
            top5_logits = torch.topk(out.logits[0, -1, :], 5).values.tolist()
            next_id = top5[0]
            generated = [next_id]
            for _ in range(max_new_tokens - 1):
                if next_id in eos_ids:
                    break
                new_embed = embed(torch.tensor([[next_id]], dtype=torch.long))
                out = thinker(inputs_embeds=new_embed, past_key_values=past, use_cache=True)
                past = out.past_key_values
                next_id = int(out.logits[0, -1, :].argmax().item())
                generated.append(next_id)
        return generated, top5, top5_logits

    # 跑 trace
    out_dir = 'reports/c040_trace'
    os.makedirs(out_dir, exist_ok=True)
    for start, end, label in TRACE_SEGMENTS:
        if already_done(label, out_dir):
            print(f'\n[c040-trace] === {label} already done, skip ===', flush=True)
            continue
        audio_full, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
        if audio_full.ndim > 1:
            audio_full = audio_full[:, 0]
        audio = audio_full[int(start*sr):int(end*sr)]
        assert sr == 16000
        print(f'\n[c040-trace] === {label} ({len(audio)/sr:.1f}s, {int(start)}-{int(end)}) ===', flush=True)

        # 预热
        _ = backends['int8'].encode_audio(audio[:16000])

        # 流式 trace
        sr_ = SAMPLE_RATE
        chunk_samples = int(0.64 * sr_)
        n_chunks = (len(audio) + chunk_samples - 1) // chunk_samples

        # Per-decoder state
        per_dec_state = {name: {'gen_so_far': '', 'raw_decoded_so_far': ''} for name in ['int8', 'fp16', 'torch']}
        per_dec_state.update({name: {'gen_so_far': '', 'raw_decoded_so_far': ''} for name in backends})

        # 第一个 chunk 的 logits top5 对比 (用最简单 prompt 即可)
        # 注: chunk 0 的 prefix = ""
        all_chunks_log = []
        first_divergence = None

        for ci in range(n_chunks):
            s = ci * chunk_samples
            e = min((ci + 1) * chunk_samples, len(audio))
            audio_accum = audio[:e]

            # 共享 ehs
            ehs, n_real, N_audio = backends['int8'].encode_audio(audio_accum)

            # 计算 prefix_text (简化: chunk 0 = "", chunk 1+ = 上一 chunk gen_text)
            # 实际 streaming 是 raw_decoded 滚回 unfixed_token_num, 这里简化
            # 用 INT8 的 raw_decoded_so_far 作为所有 decoder 的 prefix (这会造成 INT8 循环传染给 FP16/torch, 不是我们要的)
            # 正确做法: 每个 decoder 用自己的 raw_decoded_so_far, 即每个独立流式
            for name in ['int8', 'fp16', 'torch']:
                if ci == 0:
                    prefix_text = ''
                else:
                    prefix_text = per_dec_state[name]['raw_decoded_so_far']
                # tokenize prefix
                if prefix_text:
                    full = build_prompt_raw(tokenizer) + prefix_text
                    raw_ids = tokenizer.encode(build_prompt_raw(tokenizer), add_special_tokens=False)
                    full_ids = tokenizer.encode(full, add_special_tokens=False)
                    prefix_ids = full_ids[len(raw_ids):] if len(full_ids) > len(raw_ids) else []
                else:
                    prefix_ids = []

                # run decoder
                if name == 'torch':
                    gen_ids, top5, top5l = torch_greedy_log(thinker, ehs, prefix_ids, 32)
                else:
                    gen_ids, top5, top5l = ov_greedy_log(backends[name].dec_infer, ehs, prefix_ids, 32)
                gen_text = tokenizer.decode(gen_ids, skip_special_tokens=True)

                chunk_log = {
                    'chunk': ci,
                    'prefix_len': len(prefix_ids),
                    'prefix_text_tail': prefix_text[-50:] if prefix_text else '',
                    'gen_ids': gen_ids,
                    'gen_text': gen_text,
                    'logits_top5': top5,
                    'logits_top5_vals': top5l,
                }
                per_dec_state[name].setdefault('chunks', []).append(chunk_log)

                # 更新 raw_decoded_so_far
                if ci == 0:
                    per_dec_state[name]['raw_decoded_so_far'] = gen_text
                else:
                    per_dec_state[name]['raw_decoded_so_far'] = (
                        per_dec_state[name]['raw_decoded_so_far'] + ' ' + gen_text
                        if per_dec_state[name]['raw_decoded_so_far'] else gen_text
                    )

            # 检查该 chunk 3 个 decoder 是否 prefix 一致 + gen 一致
            if ci > 0:
                i_pref = per_dec_state['int8']['chunks'][-1]['prefix_len']
                ii_pref = per_dec_state['fp16']['chunks'][-1]['prefix_len']
                iii_pref = per_dec_state['torch']['chunks'][-1]['prefix_len']
                i_gen = tuple(per_dec_state['int8']['chunks'][-1]['gen_ids'])
                ii_gen = tuple(per_dec_state['fp16']['chunks'][-1]['gen_ids'])
                iii_gen = tuple(per_dec_state['torch']['chunks'][-1]['gen_ids'])
                if first_divergence is None and (i_gen != ii_gen or ii_gen != iii_gen):
                    first_divergence = {
                        'chunk': ci,
                        'int8_gen': i_gen,
                        'fp16_gen': ii_gen,
                        'torch_gen': iii_gen,
                        'int8_prefix_len': i_pref,
                        'fp16_prefix_len': ii_pref,
                        'torch_prefix_len': iii_pref,
                        'int8_top5': per_dec_state['int8']['chunks'][-1]['logits_top5'],
                        'fp16_top5': per_dec_state['fp16']['chunks'][-1]['logits_top5'],
                        'torch_top5': per_dec_state['torch']['chunks'][-1]['logits_top5'],
                        'int8_top5_vals': per_dec_state['int8']['chunks'][-1]['logits_top5_vals'],
                        'fp16_top5_vals': per_dec_state['fp16']['chunks'][-1]['logits_top5_vals'],
                        'torch_top5_vals': per_dec_state['torch']['chunks'][-1]['logits_top5_vals'],
                    }

            if ci < 3 or first_divergence is not None:
                try:
                    print(f'  [chunk {ci:2d}] int8="{per_dec_state["int8"]["chunks"][-1]["gen_text"][:30]:30s}" '
                          f'fp16="{per_dec_state["fp16"]["chunks"][-1]["gen_text"][:30]:30s}" '
                          f'torch="{per_dec_state["torch"]["chunks"][-1]["gen_text"][:30]:30s}"', flush=True)
                except Exception:
                    pass

        # 保存
        seg_log = {
            'label': label,
            'start': start, 'end': end, 'dur': end - start,
            'n_chunks': n_chunks,
            'first_divergence': first_divergence,
            'int8': {
                'final_text': per_dec_state['int8']['raw_decoded_so_far'],
                'n_chunks': len(per_dec_state['int8']['chunks']),
            },
            'fp16': {
                'final_text': per_dec_state['fp16']['raw_decoded_so_far'],
                'n_chunks': len(per_dec_state['fp16']['chunks']),
            },
            'torch': {
                'final_text': per_dec_state['torch']['raw_decoded_so_far'],
                'n_chunks': len(per_dec_state['torch']['chunks']),
            },
            'chunks_int8': per_dec_state['int8']['chunks'],
            'chunks_fp16': per_dec_state['fp16']['chunks'],
            'chunks_torch': per_dec_state['torch']['chunks'],
        }
        log_path = os.path.join(out_dir, f'{label}_trace.json')
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(seg_log, f, ensure_ascii=False, indent=2)
        print(f'  → {log_path}')
        if first_divergence:
            print(f'  ** first divergence at chunk {first_divergence["chunk"]} **')
            print(f'     int8 gen_ids (first 5): {first_divergence["int8_gen"][:5]}')
            print(f'     fp16 gen_ids (first 5): {first_divergence["fp16_gen"][:5]}')
            print(f'     torch gen_ids (first 5): {first_divergence["torch_gen"][:5]}')
            print(f'     int8 top5: {first_divergence["int8_top5"]}')
            print(f'     fp16 top5: {first_divergence["fp16_top5"]}')
            print(f'     torch top5: {first_divergence["torch_top5"]}')
            print(f'     int8 top5 vals: {first_divergence["int8_top5_vals"]}')
            print(f'     fp16 top5 vals: {first_divergence["fp16_top5_vals"]}')
            print(f'     torch top5 vals: {first_divergence["torch_top5_vals"]}')
        else:
            print(f'  ** no divergence in {n_chunks} chunks **')
    print('\n[c040-trace] DONE')


def build_prompt_raw(tokenizer):
    msgs = [{'role': 'system', 'content': ''},
            {'role': 'user', 'content': [{'type': 'audio', 'audio': ''}]}]
    return tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)


if __name__ == '__main__':
    main()
