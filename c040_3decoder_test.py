"""c040_3decoder_test.py — C-040#1: 15 段 × 3 decoder 对比

3 decoders (用同一份 VAD-off 流式 + 同样的 segment encoder IR):
  (i)   OV INT8-past  (models/ov-int8-past,  现状)
  (ii)  OV FP16-past  (models/ov-fp16-past)
  (iii) torch FP32    (用 hybrid-style torch 路径 + 同样的 segment ehs)

每个 segment 用 SegmentedStreamer 跑一次 (VAD off, 单段流式), 然后换 backend 重跑.
"""
import os, sys, time, json, re
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '1')  # 需要 torch for (iii)
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf
import torch
from collections import Counter

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer


# 15 个最差段 (按 c039 61-min n4 排序)
TOP15 = [
    (1925.4, 1939.5, 'seg118_1925_1940'),
    (2656.8, 2675.9, 'seg163_2657_2676'),
    (1086.3, 1102.4, 'seg67_1086_1102'),
    (2622.2, 2640.4, 'seg161_2622_2640'),
    ( 863.7,  881.1, 'seg55_864_881'),
    (2195.0, 2214.2, 'seg133_2195_2214'),
    (3439.4, 3458.2, 'seg212_3439_3458'),
    (3458.2, 3477.7, 'seg213_3458_3477'),
    (1034.1, 1051.5, 'seg65_1034_1051'),
    ( 372.7,  386.7, 'seg23_373_386'),
    (1647.2, 1664.1, 'seg99_1647_1664'),
    (1449.7, 1467.4, 'seg87_1450_1467'),
    (1530.7, 1550.1, 'seg92_1531_1550'),
    (2092.4, 2107.8, 'seg126_2092_2108'),
    ( 292.8,  309.3, 'seg18_293_309'),
]


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return [w for w in s.split() if w]


def ngram_stats(text):
    ws = words(text)
    out = {'words': len(ws)}
    for n in (3, 4):
        counts = Counter()
        for i in range(len(ws) - n + 1):
            counts[tuple(ws[i:i+n])] += 1
        out[f'n{n}_repeat'] = sum(c-1 for c in counts.values() if c > 1)
        out[f'n{n}_max'] = max(counts.values()) if counts else 0
    return out


def main():
    print('[c040-3dec] === 15 段 × 3 decoder 对比 (VAD off, single segment streaming) ===', flush=True)
    print(f'[c040-3dec] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    # 3 backends
    print('[c040-3dec] 加载 3 个 backend (共用同一份 segment encoder IR)...', flush=True)
    backends = {
        'int8': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past',
            device='GPU.0', precision='f16',  # f16 perf hint
        ),
        'fp16': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-fp16-past',
            device='GPU.0', precision='f16',
        ),
        'torch': SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past',  # 占位
            device='GPU.0', precision='f16',
        ),
    }

    # 加载 torch thinker (替换 torch backend 的 decoder)
    print('[c040-3dec] 加载 torch thinker (FP32 CPU)...', flush=True)
    from qwen_asr.core.transformers_backend import Qwen3ASRForConditionalGeneration
    thinker = Qwen3ASRForConditionalGeneration.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager'
    ).thinker
    thinker.eval()
    # Monkey-patch torch backend's decode methods to use torch thinker
    backends['torch']._torch_thinker = thinker

    # Monkey-patch torch backend's greedy_decode_with_prefix to use torch
    orig_greedy = SegmentEncoderOVBackend.greedy_decode_with_prefix
    def torch_greedy(self, encoder_hidden_states, prefix_ids, max_new_tokens):
        """替换为 torch FP32 decoder。"""
        ehs_np = encoder_hidden_states
        N = ehs_np.shape[1]
        ids_left, ids_right = self._prompt_template_ids
        full_ids = list(ids_left) + [self._audio_pad_id] * N + list(ids_right) + list(prefix_ids)
        full_ids_t = torch.tensor([full_ids], dtype=torch.long)

        thinker = self._torch_thinker
        embed = thinker.get_input_embeddings()
        inputs_embeds = embed(full_ids_t)

        ehs_t = torch.from_numpy(ehs_np).to(inputs_embeds.dtype)
        audio_mask = (full_ids_t == self._audio_pad_id).unsqueeze(-1)
        inputs_embeds = inputs_embeds.masked_scatter(audio_mask, ehs_t)

        eos_ids = {151643, 151645, self.tokenizer.eos_token_id}
        with torch.no_grad():
            out = thinker(inputs_embeds=inputs_embeds, use_cache=True)
            past = out.past_key_values
            next_id = int(out.logits[0, -1, :].argmax().item())
            generated = [next_id]
            for _ in range(max_new_tokens - 1):
                if next_id in eos_ids:
                    break
                new_embed = embed(torch.tensor([[next_id]], dtype=torch.long))
                out = thinker(inputs_embeds=new_embed, past_key_values=past, use_cache=True)
                past = out.past_key_values
                next_id = int(out.logits[0, -1, :].argmax().item())
                generated.append(next_id)
        return generated

    backends['torch'].greedy_decode_with_prefix = torch_greedy.__get__(backends['torch'], SegmentEncoderOVBackend)

    # 跑 15 段 × 3 decoders
    results_all = []
    for start, end, label in TOP15:
        # 切音频
        snip_path = f'reports/c028_snippets/{label}.wav'
        if not os.path.exists(snip_path):
            audio_full, sr = sf.read('test_audio/260902_SPE_audio.wav', dtype='float32')
            if audio_full.ndim > 1:
                audio_full = audio_full[:, 0]
            audio = audio_full[int(start*sr):int(end*sr)]
        else:
            audio, sr = sf.read(snip_path, dtype='float32')
            if audio.ndim > 1:
                audio = audio[:, 0]
        assert sr == 16000
        print(f'\n[c040-3dec] === {label} ({len(audio)/sr:.1f}s) ===', flush=True)

        seg_results = {'label': label, 'start': start, 'end': end, 'dur': end-start}

        for name, backend in backends.items():
            # 预热 encoder (3 个 backend 共享同一份 IR; 只需第一次)
            _ = backend.encode_audio(audio[:16000])

            streamer = SegmentedStreamer(
                backend, strategy='off',  # 不分 VAD, 整段
                chunk_size_sec=0.64,
                unfixed_chunk_num=0, unfixed_token_num=5,
                max_new_tokens=32,
            )
            t0 = time.perf_counter()
            text, _segs = streamer.run(audio)
            wall = time.perf_counter() - t0
            stats = ngram_stats(text)
            seg_results[f'{name}_text'] = text
            seg_results[f'{name}_words'] = stats['words']
            seg_results[f'{name}_n3'] = stats['n3_repeat']
            seg_results[f'{name}_n4'] = stats['n4_repeat']
            seg_results[f'{name}_n4max'] = stats['n4_max']
            seg_results[f'{name}_wall'] = wall
            print(f'  [{name:6s}] {stats["words"]:3d}w n3={stats["n3_repeat"]:3d} n4={stats["n4_repeat"]:3d} n4max={stats["n4_max"]:2d} wall={wall:.1f}s', flush=True)
            print(f'    text: {text[:120]}...', flush=True)
        results_all.append(seg_results)

    out_dir = 'reports/c040_3dec'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results_15seg.json'), 'w', encoding='utf-8') as f:
        json.dump(results_all, f, ensure_ascii=False, indent=2)

    # Summary
    print('\n=== Summary (3-decoder comparison) ===')
    print(f'{"label":24s} {"i_n4":>6s} {"ii_n4":>7s} {"iii_n4":>7s}')
    tot_i = tot_ii = tot_iii = 0
    for r in results_all:
        i = r.get('int8_n4', 0)
        ii = r.get('fp16_n4', 0)
        iii = r.get('torch_n4', 0)
        tot_i += i
        tot_ii += ii
        tot_iii += iii
        print(f'{r["label"]:24s} {i:6d} {ii:7d} {iii:7d}')
    print(f'{"TOTAL":24s} {tot_i:6d} {tot_ii:7d} {tot_iii:7d}')

    with open(os.path.join(out_dir, 'summary_15seg.txt'), 'w', encoding='utf-8') as f:
        f.write('c040 15-segment × 3-decoder comparison\n')
        f.write('(i) OV INT8-past  (ii) OV FP16-past  (iii) torch FP32\n\n')
        f.write(f'{"label":24s} {"i_n4":>6s} {"ii_n4":>7s} {"iii_n4":>7s}\n')
        for r in results_all:
            f.write(f'{r["label"]:24s} {r.get("int8_n4",0):6d} {r.get("fp16_n4",0):7d} {r.get("torch_n4",0):7d}\n')
        f.write(f'{"TOTAL":24s} {tot_i:6d} {tot_ii:7d} {tot_iii:7d}\n')
    print(f'[c040-3dec] → {out_dir}/summary_15seg.txt')


if __name__ == '__main__':
    main()
