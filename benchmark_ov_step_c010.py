"""benchmark_ov_step_c010.py — C-010 #5：预热后分项 benchmark

mel / encode / prefill / decode(+token) 四段计时，参数组 A（320ms chunk）。
先完整跑一遍预热，再正式计时。
"""
import os, sys, time, csv
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf

sys.path.insert(0, '.')
from backends import (
    OVBackend, ASRStreamingState, SAMPLE_RATE, AUDIO_PAD, EOS_IDS,
)
from streaming_asr import finish_streaming_transcribe


def instrument_one_chunk(b: OVBackend, audio_accum: np.ndarray, prefix_ids: list,
                         max_new_tokens: int):
    """拆 mel / encode / prefill / decode 四段计时。"""
    # 1) mel
    t0 = time.perf_counter()
    feats_real, _, n_real, N_formula = b.encode_audio(audio_accum)[:4] if False else (
        *[(None,)],  # placeholder
    )[0] if False else (None, None, None, None)
    # 真实代码：
    pass


def main(wav_path='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav',
         chunk_ms=320, unfixed_chunk_num=2, unfixed_token_num=5,
         max_new_tokens=32,
         model_dir='models/ov-fp16-past', device='GPU.0',
         out_csv='reports/benchmark_ov_step_c010.csv',
         out_log='reports/benchmark_ov_step_c010.log'):

    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE
    audio_dur = len(audio) / sr
    print(f'[bench] audio: {len(audio)} samples, {audio_dur:.2f}s', flush=True)

    print(f'[bench] loading OVBackend ({model_dir} on {device}) ...', flush=True)
    t0 = time.perf_counter()
    b = OVBackend(model_dir=model_dir, device=device)
    print(f'[bench] loaded in {time.perf_counter()-t0:.1f}s', flush=True)

    # 预热一遍（C-009 #1）：先完整跑一次不计时
    print('[bench] WARMUP run (no timing) ...', flush=True)
    state = b.init_streaming_state(
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=chunk_ms / 1000,
    )
    feed_chunk = int(SAMPLE_RATE * 0.04)
    feed_pos = 0
    while feed_pos < len(audio):
        end = min(feed_pos + feed_chunk, len(audio))
        chunk_audio = audio[feed_pos:end]
        feed_pos = end
        if chunk_audio.shape[0] > 0:
            state.buffer = np.concatenate(
                [state.buffer, chunk_audio.astype(np.float32, copy=False)], axis=0)
        while state.buffer.shape[0] >= state.chunk_size_samples:
            chunk = state.buffer[:state.chunk_size_samples]
            state.buffer = state.buffer[state.chunk_size_samples:]
            if state.audio_accum.shape[0] == 0:
                state.audio_accum = chunk
            else:
                state.audio_accum = np.concatenate([state.audio_accum, chunk], axis=0)
            # 简化：每 chunk 跑一次 generate
            prefix = ""
            if state.chunk_id >= state.unfixed_chunk_num:
                state._raw_decoded = state._raw_decoded.split("|")[0]
                cur_ids = b.tokenizer.encode(state._raw_decoded)
                k = int(state.unfixed_token_num)
                while True:
                    end_idx = max(0, len(cur_ids) - k)
                    prefix = b.tokenizer.decode(cur_ids[:end_idx]) if end_idx > 0 else ""
                    if '\ufffd' not in prefix: break
                    if end_idx == 0: prefix = ""; break
                    k += 1
            prefix_ids = b.tokenizer.encode(prefix, add_special_tokens=False) if prefix else []
            gen = b.generate_with_prefix(state, state.audio_accum, prefix, max_new_tokens)
            new_raw = (prefix + gen) if prefix else gen
            state._raw_decoded = new_raw.split("|")[0]
            state.chunk_id += 1
    finish_streaming_transcribe(b, state, max_new_tokens=64)
    print(f'[bench] warmup done. last text: {state.text!r}', flush=True)

    # 正式计时
    state = b.init_streaming_state(
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=chunk_ms / 1000,
    )
    feed_pos = 0
    wall_start = time.perf_counter()
    rows = []
    while feed_pos < len(audio):
        end = min(feed_pos + feed_chunk, len(audio))
        chunk_audio = audio[feed_pos:end]
        feed_pos = end
        if chunk_audio.shape[0] > 0:
            state.buffer = np.concatenate(
                [state.buffer, chunk_audio.astype(np.float32, copy=False)], axis=0)
        while state.buffer.shape[0] >= state.chunk_size_samples:
            chunk = state.buffer[:state.chunk_size_samples]
            state.buffer = state.buffer[state.chunk_size_samples:]
            if state.audio_accum.shape[0] == 0:
                state.audio_accum = chunk
            else:
                state.audio_accum = np.concatenate([state.audio_accum, chunk], axis=0)

            prefix = ""
            if state.chunk_id >= state.unfixed_chunk_num:
                state._raw_decoded = state._raw_decoded.split("|")[0]
                cur_ids = b.tokenizer.encode(state._raw_decoded)
                k = int(state.unfixed_token_num)
                while True:
                    end_idx = max(0, len(cur_ids) - k)
                    prefix = b.tokenizer.decode(cur_ids[:end_idx]) if end_idx > 0 else ""
                    if '\ufffd' not in prefix: break
                    if end_idx == 0: prefix = ""; break
                    k += 1
            prefix_ids = b.tokenizer.encode(prefix, add_special_tokens=False) if prefix else []

            # 计时：mel
            t0 = time.perf_counter()
            feats_real, _, n_real, N_formula = b.encode_audio(state.audio_accum)[:4] if False else (None, None, None, None)
            from backends import extract_audio_features
            feats_real, _, n_real, N_formula = extract_audio_features(
                b.feature_extractor, state.audio_accum, return_torch=False,
            )
            mel_ms = (time.perf_counter() - t0) * 1000

            # 计时：encode (audio_tower)
            t0 = time.perf_counter()
            ehs = b.enc({"input_features": feats_real})["last_hidden_state"]
            encode_ms = (time.perf_counter() - t0) * 1000
            N_audio = int(ehs.shape[1])

            # 计时：prefill + decode
            ids_left, ids_right = b._prompt_template_ids
            full_ids = list(ids_left) + [AUDIO_PAD] * N_audio + list(ids_right) + list(prefix_ids)
            b.dec_infer.reset_state()
            t0 = time.perf_counter()
            b.dec_infer.infer({
                "encoder_hidden_states": ehs,
                "input_ids": np.array([full_ids], dtype=np.int64),
                "beam_idx": np.array([0], dtype=np.int32),
            })
            logits = b.dec_infer.get_output_tensor(0).data
            next_id = int(np.argmax(logits[0, -1]))
            prefill_ms = (time.perf_counter() - t0) * 1000

            n_decoded = 1
            ehs_dummy = np.zeros((1, 1, 2048), dtype=np.float32)
            t0 = time.perf_counter()
            out_tokens = [next_id]
            if next_id not in EOS_IDS:
                for _ in range(max_new_tokens - 1):
                    b.dec_infer.infer({
                        "encoder_hidden_states": ehs_dummy,
                        "input_ids": np.array([[next_id]], dtype=np.int64),
                        "beam_idx": np.array([0], dtype=np.int32),
                    })
                    logits = b.dec_infer.get_output_tensor(0).data
                    next_id = int(np.argmax(logits[0, -1]))
                    n_decoded += 1
                    if next_id in EOS_IDS: break
                    out_tokens.append(next_id)
            decode_total_ms = (time.perf_counter() - t0) * 1000

            gen_text = b.tokenizer.decode(out_tokens, skip_special_tokens=True)
            new_raw = (prefix + gen_text) if prefix else gen_text
            state._raw_decoded = new_raw.split("|")[0]

            chunk_wall = mel_ms + encode_ms + prefill_ms + decode_total_ms
            rows.append({
                'chunk_id': state.chunk_id + 1,
                'audio_so_far_s': len(state.audio_accum) / SAMPLE_RATE,
                'n_mel_real': n_real,
                'n_audio_tokens': N_audio,
                'prefill_len': len(full_ids),
                'mel_ms': mel_ms,
                'encode_ms': encode_ms,
                'prefill_ms': prefill_ms,
                'decode_total_ms': decode_total_ms,
                'n_decoded': n_decoded,
                'decode_per_token_ms': decode_total_ms / max(1, n_decoded - 1),
                'chunk_wall_ms': chunk_wall,
                'text': b.tokenizer.decode(out_tokens, skip_special_tokens=False),
            })
            print(f'[bench] chunk {rows[-1]["chunk_id"]:2d} audio={rows[-1]["audio_so_far_s"]:.2f}s '
                  f'n_mel={n_real:3d} n_audio={N_audio:3d} prefill={len(full_ids):3d}tok '
                  f'mel={mel_ms:5.0f} encode={encode_ms:5.0f} prefill={prefill_ms:5.0f} '
                  f'decode={decode_total_ms:5.0f}/{n_decoded-1}tok '
                  f'wall={chunk_wall:5.0f}ms text={rows[-1]["text"]!r}', flush=True)
            state.chunk_id += 1

    final = finish_streaming_transcribe(b, state, max_new_tokens=64)
    wall_total = time.perf_counter() - wall_start
    print(f'\n[bench] FINAL = {final!r}', flush=True)
    print(f'[bench] {len(rows)} chunks, wall={wall_total:.2f}s, audio={audio_dur:.2f}s, '
          f'RTF={wall_total/audio_dur:.3f}', flush=True)

    # 写 CSV
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=[
            'chunk_id', 'audio_so_far_s', 'n_mel_real', 'n_audio_tokens', 'prefill_len',
            'mel_ms', 'encode_ms', 'prefill_ms', 'decode_total_ms', 'n_decoded',
            'decode_per_token_ms', 'chunk_wall_ms', 'text',
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    with open(out_log, 'w', encoding='utf-8') as f:
        f.write(f"# Per-step benchmark OV (C-010 fix: no 30s pad, C-009#2 tiny ehs on decode)\n")
        f.write(f"# {model_dir} on {device} FP16, chunk_ms={chunk_ms}\n")
        f.write(f"# audio_dur={audio_dur:.2f}s wall={wall_total:.2f}s RTF={wall_total/audio_dur:.3f}\n")
        f.write(f"# After 1 warmup pass\n\n")
        for r in rows:
            f.write(f"chunk {r['chunk_id']:2d} audio={r['audio_so_far_s']:.2f}s "
                    f"n_mel={r['n_mel_real']:3d} n_audio={r['n_audio_tokens']:3d} "
                    f"prefill={r['prefill_len']:3d}tok "
                    f"mel={r['mel_ms']:6.1f} encode={r['encode_ms']:6.1f} "
                    f"prefill={r['prefill_ms']:6.1f} decode={r['decode_total_ms']:6.1f}/{r['n_decoded']-1}tok "
                    f"wall={r['chunk_wall_ms']:6.1f}ms text={r['text']!r}\n")
        f.write(f"\nFINAL: {final!r}\n")

    if rows:
        avg = {k: float(np.mean([r[k] for r in rows])) for k in
               ('mel_ms', 'encode_ms', 'prefill_ms', 'decode_total_ms', 'chunk_wall_ms')}
        print(f'\n[bench] === Average per-chunk (post-warmup) ===')
        print(f'  mel:     {avg["mel_ms"]:7.1f} ms')
        print(f'  encode:  {avg["encode_ms"]:7.1f} ms')
        print(f'  prefill: {avg["prefill_ms"]:7.1f} ms')
        print(f'  decode:  {avg["decode_total_ms"]:7.1f} ms')
        print(f'  total:   {avg["chunk_wall_ms"]:7.1f} ms')
        print(f'[bench] Target chunk<{chunk_ms}ms for RTF<1. Current avg: {avg["chunk_wall_ms"]:.0f} ms.')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--chunk-ms', type=float, default=320)
    p.add_argument('--max-new-tokens', type=int, default=32)
    p.add_argument('--wav', default='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
    p.add_argument('--model-dir', default='models/ov-fp16-past')
    p.add_argument('--device', default='GPU.0')
    p.add_argument('--out-csv', default='reports/benchmark_ov_step_c010.csv')
    p.add_argument('--out-log', default='reports/benchmark_ov_step_c010.log')
    args = p.parse_args()
    main(wav_path=args.wav, chunk_ms=args.chunk_ms,
         max_new_tokens=args.max_new_tokens,
         model_dir=args.model_dir, device=args.device,
         out_csv=args.out_csv, out_log=args.out_log)
