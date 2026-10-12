"""c030_chunk_trace.py — C-030 step 1 (E) 逐 chunk 追踪

对 seg172 [2812-2828] 和 seg38 [607-624] 跑 OV path a (现状)。
每 chunk 记录：prefix/gen_text/raw_decoded/fixed_text/state.text。
与 c029_audiocpp_seg172.log (CUDA Q8_0) 逐 chunk 对比，
找第一次"gen_text 重复 prefix 已有内容"的 chunk。
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf

from streaming_asr import (
    _ASR_TEXT_TAG, _normalize_punct_by_context, parse_language_output,
    parse_asr_output, streaming_transcribe, finish_streaming_transcribe,
)
from window_encoder_backend import WindowEncoderOVBackend


SNIPS = [
    ('reports/c028_snippets/seg172_2812_2828.wav', 'seg172_2812_2828'),
    ('reports/c028_snippets/seg38_607_624.wav',    'seg38_607_624'),
]
OUT_DIR = 'reports/c030_chunk_trace'


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return [w for w in s.split() if w]


import re


def find_repeat(prefix_words, gen_words, n_min=3):
    """Return the largest n such that gen_words[:n] is a subsequence of prefix_words
       (i.e. model is repeating content already in prefix).
    """
    if not prefix_words or not gen_words:
        return 0
    pset = set(prefix_words)
    n = 0
    for w in gen_words:
        if w in pset:
            n += 1
        else:
            break
    return n


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print('[c030] loading OV path a backend...', flush=True)
    b = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )
    print(f'[c030] loaded (tokenizer ok)', flush=True)

    all_results = {}
    for wav_path, label in SNIPS:
        if not os.path.exists(wav_path):
            print(f'[c030] missing {wav_path}, skip', flush=True)
            continue
        print(f'\n[c030] === {label} ===', flush=True)
        audio, sr = sf.read(wav_path, dtype='float32')
        assert sr == 16000

        state = b.init_streaming_state(
            unfixed_chunk_num=0,
            unfixed_token_num=5,
            chunk_size_sec=0.64,
        )

        rows = []
        first_repeat_chunk = None
        feed_chunk = int(16000 * 0.04)  # 40ms
        p = 0
        t_start = time.perf_counter()
        while p < len(audio):
            e = min(p + feed_chunk, len(audio))
            # Snapshot state before this feed
            chunk_id_before = state.chunk_id
            raw_decoded_before = state._raw_decoded
            text_before = state.text
            # Run one feed (may produce ≥1 chunks)
            text_after, fixed_text_after = streaming_transcribe(b, audio[p:e], state, max_new_tokens=32)
            # If new chunks were processed, snapshot
            if state.chunk_id > chunk_id_before:
                # prefix is computed inside streaming_transcribe; reconstruct from
                # raw_decoded_before (with rollback k=5)
                cur_ids = b.tokenizer.encode(raw_decoded_before.split("|")[0])
                end_idx = max(0, len(cur_ids) - 5)
                prefix = b.tokenizer.decode(cur_ids[:end_idx]) if end_idx > 0 else ''
                # gen_text = new state._raw_decoded minus prefix
                gen_text = state._raw_decoded[len(prefix):] if prefix else state._raw_decoded
                # detect repeat
                pw = words(prefix)
                gw = words(gen_text)
                r = find_repeat(pw, gw, n_min=3)
                rows.append({
                    'chunk_id': state.chunk_id,
                    'wall_s': time.perf_counter() - t_start,
                    'audio_so_far_s': state.audio_accum.shape[0] / 16000,
                    'prefix': prefix,
                    'gen_text': gen_text,
                    'raw_decoded': state._raw_decoded,
                    'fixed_text': fixed_text_after,
                    'state_text': state.text,
                    'prefix_n_words': len(pw),
                    'gen_n_words': len(gw),
                    'repeat_n': r,
                })
                if r >= 3 and first_repeat_chunk is None:
                    first_repeat_chunk = state.chunk_id
                    print(f'[c030]   ** FIRST REPEAT at chunk {state.chunk_id}: {r}-gram repeat', flush=True)
                    print(f'[c030]      prefix ({len(pw)}w): {prefix[-200:]!r}', flush=True)
                    print(f'[c030]      gen   ({len(gw)}w): {gen_text[:300]!r}', flush=True)
            p = e

        # Finish
        final = finish_streaming_transcribe(b, state, max_new_tokens=64)
        rows.append({
            'chunk_id': state.chunk_id + 0.5,  # marker
            'kind': 'FINAL_FLUSH',
            'final_text': final,
            'state_text': state.text,
            'raw_decoded': state._raw_decoded,
        })

        out_path = os.path.join(OUT_DIR, f'{label}_chunks.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'label': label,
                'wav': wav_path,
                'n_chunks': len([r for r in rows if 'kind' not in r]),
                'first_repeat_chunk': first_repeat_chunk,
                'final_text': final,
                'rows': rows,
            }, f, ensure_ascii=False, indent=2)
        all_results[label] = {
            'n_chunks': len([r for r in rows if 'kind' not in r]),
            'first_repeat_chunk': first_repeat_chunk,
            'final_text': final[:500],
            'out_path': out_path,
        }
        print(f'[c030] {label}: {len([r for r in rows if "kind" not in r])} chunks, first_repeat={first_repeat_chunk}', flush=True)
        print(f'[c030]   final (first 500): {final[:500]!r}', flush=True)
        print(f'[c030]   → {out_path}', flush=True)

    # Summary
    with open(os.path.join(OUT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f'\n[c030] === summary ===', flush=True)
    for k, v in all_results.items():
        print(f'  {k}: first_repeat_chunk={v["first_repeat_chunk"]}, n_chunks={v["n_chunks"]}', flush=True)
    print(f'[c030] → {OUT_DIR}/summary.json', flush=True)


if __name__ == '__main__':
    main()
