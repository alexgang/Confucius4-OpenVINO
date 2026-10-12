"""benchmark_ov_step.py — C-006 step5：分项 benchmark

每个 chunk 拆出三个阶段的耗时：
  - encode_ms   : encoder IR 一次（audio_accum 整段重编码）
  - prefill_ms  : decoder IR 一次 prefill（整条 prompt）
  - decode_ms   : decoder IR 增量 1 token/step 直到 EOS / max_new_tokens
  - decode_total_ms = sum of decode steps
  - decode_per_token_ms = decode_total_ms / n_decoded_tokens
  - chunk_wall_ms = encode + prefill + decode_total

输出 reports/benchmark_ov_step.csv + 报告。
"""
import os, sys, time, csv, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np
import soundfile as sf

sys.path.insert(0, '.')
from backends import (
    OVBackend, ASRStreamingState, SAMPLE_RATE, AUDIO_PAD, EOS_IDS,
)
from streaming_asr import finish_streaming_transcribe


def instrument_decode(backend: OVBackend, ehs: np.ndarray, prefix_ids: list,
                      max_new_tokens: int):
    """拆开 encode/prefill/decode 三段计时，返回 (tokens, timings)"""
    import time as _t
    # 1) prefill
    ids_l, ids_r = backend._prompt_template_ids
    N = int(ehs.shape[1])
    full = list(ids_l) + [AUDIO_PAD] * N + list(ids_r) + list(prefix_ids)
    backend.dec_infer.reset_state()
    t0 = _t.perf_counter()
    backend.dec_infer.infer({
        "encoder_hidden_states": ehs,
        "input_ids": np.array([full], dtype=np.int64),
        "beam_idx": np.array([0], dtype=np.int32),
    })
    prefill_ms = (_t.perf_counter() - t0) * 1000
    logits = backend.dec_infer.get_output_tensor(0).data
    nxt = int(np.argmax(logits[0, -1]))
    out = [nxt]
    if nxt in EOS_IDS:
        return out, dict(prefill_ms=prefill_ms, decode_total_ms=0.0, n_decoded=1)
    # 2) incremental decode
    t0 = _t.perf_counter()
    n_steps = 0
    for _ in range(max_new_tokens - 1):
        backend.dec_infer.infer({
            "encoder_hidden_states": ehs,
            "input_ids": np.array([[nxt]], dtype=np.int64),
            "beam_idx": np.array([0], dtype=np.int32),
        })
        logits = backend.dec_infer.get_output_tensor(0).data
        nxt = int(np.argmax(logits[0, -1]))
        n_steps += 1
        if nxt in EOS_IDS: break
        out.append(nxt)
    decode_total_ms = (_t.perf_counter() - t0) * 1000
    return out, dict(prefill_ms=prefill_ms, decode_total_ms=decode_total_ms, n_decoded=len(out))


def main(wav_path='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav',
         chunk_ms=320, unfixed_chunk_num=2, unfixed_token_num=5,
         max_new_tokens=32,
         model_dir='models/ov-fp16-past', device='GPU.0',
         out_csv='reports/benchmark_ov_step.csv',
         out_log='reports/benchmark_ov_step.log'):

    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE
    audio_dur = len(audio) / sr
    print(f'[bench] audio: {len(audio)} samples, {audio_dur:.2f}s')

    print(f'[bench] loading OVBackend ({model_dir} on {device}) ...')
    t0 = time.perf_counter()
    b = OVBackend(model_dir=model_dir, device=device)
    print(f'[bench] loaded in {time.perf_counter()-t0:.1f}s')

    # warmup
    print('[bench] warmup ... ', end='', flush=True)
    t0 = time.perf_counter()
    b.encode_audio(audio[:16000])
    print(f'{time.perf_counter()-t0:.2f}s')

    state = b.init_streaming_state(
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=chunk_ms / 1000,
    )
    feed_chunk = int(SAMPLE_RATE * 0.04)
    feed_pos = 0
    wall_start = time.perf_counter()
    rows = []
    last_chunk_id = 0

    while feed_pos < len(audio):
        end = min(feed_pos + feed_chunk, len(audio))
        chunk_audio = audio[feed_pos:end]
        feed_pos = end
        # 把音频加入 buffer（streaming_transcribe 等价步骤）
        if chunk_audio.shape[0] > 0:
            state.buffer = np.concatenate([state.buffer, chunk_audio.astype(np.float32, copy=False)], axis=0)
        # process complete chunks
        while state.buffer.shape[0] >= state.chunk_size_samples:
            # build prefix as streaming_transcribe does
            if state.chunk_id < state.unfixed_chunk_num:
                prefix = ""
            else:
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
            # 把一个完整 chunk 拉出来
            chunk = state.buffer[:state.chunk_size_samples]
            state.buffer = state.buffer[state.chunk_size_samples:]
            if state.audio_accum.shape[0] == 0:
                state.audio_accum = chunk
            else:
                state.audio_accum = np.concatenate([state.audio_accum, chunk], axis=0)

            # encode
            t_e0 = time.perf_counter()
            ehs = b.encode_audio(state.audio_accum)
            encode_ms = (time.perf_counter() - t_e0) * 1000
            # decode (instrumented)
            out_ids, timings = instrument_decode(b, ehs, prefix_ids, max_new_tokens)
            # commit
            gen_text = b.tokenizer.decode(out_ids, skip_special_tokens=True)
            new_raw = (prefix + gen_text) if prefix else gen_text
            state._raw_decoded = new_raw.split("|")[0]
            # simple: just bump chunk_id and record
            state.chunk_id += 1
            n_audio = ehs.shape[1]
            wall_now = time.perf_counter() - wall_start
            chunk_wall = encode_ms + timings['prefill_ms'] + timings['decode_total_ms']
            rows.append({
                'chunk_id': state.chunk_id,
                'audio_so_far_s': len(state.audio_accum) / SAMPLE_RATE,
                'n_audio_tokens': n_audio,
                'encode_ms': encode_ms,
                'prefill_ms': timings['prefill_ms'],
                'decode_total_ms': timings['decode_total_ms'],
                'n_decoded_tokens': timings['n_decoded'],
                'decode_per_token_ms': timings['decode_total_ms'] / max(1, timings['n_decoded'] - 1),  # exclude prefill
                'chunk_wall_ms': chunk_wall,
                'wall_s': wall_now,
                'text': b.tokenizer.decode(out_ids, skip_special_tokens=False),
            })
            print(f'[bench] chunk {state.chunk_id:2d} audio={rows[-1]["audio_so_far_s"]:.2f}s '
                  f'encode={encode_ms:.0f}ms prefill={timings["prefill_ms"]:.0f}ms '
                  f'decode={timings["decode_total_ms"]:.0f}ms/{timings["n_decoded"]-1}tok '
                  f'wall={chunk_wall:.0f}ms text={rows[-1]["text"]!r}')

    # finish
    finish_text = finish_streaming_transcribe(b, state, max_new_tokens=64)
    wall_total = time.perf_counter() - wall_start
    print()
    print(f'[bench] FINAL text = {finish_text!r}')
    print(f'[bench] {len(rows)} chunks, wall={wall_total:.2f}s, audio={audio_dur:.2f}s, '
          f'RTF={wall_total/audio_dur:.3f}')

    # 写 CSV
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=[
            'chunk_id', 'audio_so_far_s', 'n_audio_tokens',
            'encode_ms', 'prefill_ms', 'decode_total_ms', 'n_decoded_tokens',
            'decode_per_token_ms', 'chunk_wall_ms', 'wall_s', 'text',
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # 写 log
    with open(out_log, 'w', encoding='utf-8') as f:
        f.write(f"# Per-step benchmark OV ({model_dir} on {device})\n")
        f.write(f"# chunk_ms={chunk_ms} unfixed_chunk_num={unfixed_chunk_num} "
                f"unfixed_token_num={unfixed_token_num} max_new_tokens={max_new_tokens}\n")
        f.write(f"# audio_dur={audio_dur:.2f}s wall={wall_total:.2f}s RTF={wall_total/audio_dur:.3f}\n\n")
        for r in rows:
            f.write(f"chunk {r['chunk_id']:2d} audio={r['audio_so_far_s']:.2f}s "
                    f"n_audio={r['n_audio_tokens']:3d} "
                    f"encode={r['encode_ms']:6.1f}ms prefill={r['prefill_ms']:6.1f}ms "
                    f"decode={r['decode_total_ms']:6.1f}ms/{r['n_decoded_tokens']:2d}tok "
                    f"wall={r['chunk_wall_ms']:6.1f}ms text={r['text']!r}\n")
        f.write(f"\nFINAL text: {finish_text!r}\n")
    print(f'[bench] csv → {out_csv}')
    print(f'[bench] log → {out_log}')

    # summary
    if rows:
        avg = {k: float(np.mean([r[k] for r in rows])) for k in
               ('encode_ms', 'prefill_ms', 'decode_total_ms', 'chunk_wall_ms')}
        print()
        print(f'[bench] === Average per-chunk (excl. warmup) ===')
        print(f'  encode: {avg["encode_ms"]:7.1f} ms')
        print(f'  prefill: {avg["prefill_ms"]:7.1f} ms')
        print(f'  decode:  {avg["decode_total_ms"]:7.1f} ms')
        print(f'  total:   {avg["chunk_wall_ms"]:7.1f} ms')
        print(f'[bench] Target RTF < 1 → need chunk_wall < {chunk_ms} ms. Current avg: {avg["chunk_wall_ms"]:.0f} ms.')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--chunk-ms', type=float, default=320)
    p.add_argument('--unfixed-chunk-num', type=int, default=2)
    p.add_argument('--unfixed-token-num', type=int, default=5)
    p.add_argument('--max-new-tokens', type=int, default=32)
    p.add_argument('--wav', default='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
    p.add_argument('--model-dir', default='models/ov-fp16-past')
    p.add_argument('--device', default='GPU.0')
    p.add_argument('--out-csv', default='reports/benchmark_ov_step.csv')
    p.add_argument('--out-log', default='reports/benchmark_ov_step.log')
    args = p.parse_args()
    main(wav_path=args.wav, chunk_ms=args.chunk_ms,
         unfixed_chunk_num=args.unfixed_chunk_num,
         unfixed_token_num=args.unfixed_token_num,
         max_new_tokens=args.max_new_tokens,
         model_dir=args.model_dir, device=args.device,
         out_csv=args.out_csv, out_log=args.out_log)
