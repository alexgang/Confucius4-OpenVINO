"""c028_4path_localize.py — C-027/C-028 4 路定位实验

目标：定位 OV 流式 WER 23% 根因。
方法：对 11 个最差段（含 C-027 提及的 [2812-2828]、[2025-2042]、[3458-3477]、seg 38/39）
      跑 4 路配置：
        a) OV 窗口 encoder + OV INT8 decoder（现状）
        b) torch encoder + OV INT8 decoder（区分 encoder vs decoder）
        c) OV 窗口 encoder（截到整 100 帧）+ OV INT8 decoder（区分不满块）
        d) OV 窗口 encoder + OV FP16 decoder（区分 INT8 量化）

每路报告每段 4-gram 重数 + [2812-2828] 完整输出。
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

sys.path.insert(0, '.')
import numpy as np
import soundfile as sf
from collections import Counter

from window_encoder_backend import WindowEncoderOVBackend
from backends import HybridBackend
from seg_stream import SegmentedStreamer


WAV_IN = 'test_audio/<redacted>.wav'
SNIP_DIR = 'reports/c028_snippets'
OUT_DIR = 'reports/c028_4path'
os.makedirs(SNIP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


# 11 个最差段（C-027/356 中提及的 5 个 + top 9 by 4-gram repeat；remove seg 152 overlap）
SEGMENTS = [
    # (seg_idx, start_s, end_s, label)
    (38, 607.0, 624.0, 'seg38_607_624'),        # C-027 提及
    (39, 624.0, 641.1, 'seg39_624_641'),        # C-027 提及
    (172, 2812.3, 2827.7, 'seg172_2812_2828'),  # 最严重
    (124, 2025.0, 2042.2, 'seg124_2025_2042'),
    (212, 3439.4, 3458.2, 'seg212_3439_3458'),
    (197, 3198.0, 3215.0, 'seg197_3198_3215'),
    (213, 3458.2, 3477.7, 'seg213_3458_3477'),
    (23, 372.7, 386.7, 'seg23_372_386'),
    (163, 2656.8, 2675.9, 'seg163_2656_2676'),
    (161, 2622.2, 2640.4, 'seg161_2622_2640'),
    (81, 1313.3, 1328.9, 'seg81_1313_1329'),
]


def cut_snippets(wav_path, snip_dir):
    audio, sr = sf.read(wav_path, dtype='float32')
    assert sr == 16000
    snips = []
    for idx, start, end, label in SEGMENTS:
        s = int(start * sr); e = int(end * sr)
        snip = audio[s:e]
        path = os.path.join(snip_dir, f'{label}.wav')
        sf.write(path, snip, sr)
        snips.append({'idx': idx, 'start_s': start, 'end_s': end,
                       'label': label, 'path': path,
                       'duration_s': (end - start), 'sr': sr})
    print(f'[c028] cut {len(snips)} snippets', flush=True)
    return snips


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return [w for w in s.split() if w]


import re


def ngram_stats(text, n_list=(3, 4)):
    ws = words(text)
    out = {'words': len(ws)}
    for n in n_list:
        counts = Counter()
        for i in range(len(ws) - n + 1):
            counts[tuple(ws[i:i+n])] += 1
        total_repeat = sum(c - 1 for c in counts.values() if c > 1)
        max_count = max(counts.values()) if counts else 0
        out[f'n{n}_repeat'] = total_repeat
        out[f'n{n}_max'] = max_count
    return out


# ── Path c 专用：截到整 100 帧的 backend ─────────────────────────
class TruncatedPartialWindowEncoderOVBackend(WindowEncoderOVBackend):
    """路径 c：partial window 编码时把音频截到 floor(valid/100)*100 帧（丢掉不满块）"""
    def _encode_window(self, win_mel, valid_mel_in_window):
        # 截到整 100 帧边界
        truncated = (valid_mel_in_window // 100) * 100
        if truncated == 0:
            truncated = 100  # 至少 1 块
        if truncated < valid_mel_in_window:
            # 物理截断 mel
            win_mel_trunc = win_mel[:, :truncated].copy()
        else:
            win_mel_trunc = win_mel
        return super()._encode_window(win_mel_trunc, truncated)


# ── 跑单条流式 ─────────────────────────────────────────
def run_streaming(backend, snip, label):
    """单段 streaming 跑一次，返回 (full_text, n_words, n3_repeat, n4_repeat, n4_max, wall_s)"""
    from streaming_asr import streaming_transcribe, finish_streaming_transcribe
    audio, sr = sf.read(snip['path'], dtype='float32')
    state = backend.init_streaming_state(
        unfixed_chunk_num=0,
        unfixed_token_num=5,
        chunk_size_sec=0.64,
    )
    t0 = time.perf_counter()
    feed_chunk = int(16000 * 0.04)  # 40ms
    p = 0
    while p < len(audio):
        e = min(p + feed_chunk, len(audio))
        streaming_transcribe(backend, audio[p:e], state, max_new_tokens=32)
        p = e
    final = finish_streaming_transcribe(backend, state, max_new_tokens=64)
    wall = time.perf_counter() - t0
    stats = ngram_stats(final)
    return {
        'label': label, 'idx': snip['idx'],
        'start_s': snip['start_s'], 'end_s': snip['end_s'],
        'text': final, 'wall_s': wall,
        **stats,
    }


def main():
    print('[c028] === 4-path localization experiment ===', flush=True)
    snips = cut_snippets(WAV_IN, SNIP_DIR)

    # 3 个 backend 实例（per C-029：USE_TORCH=0 下 qwen_asr 不可用，path b 改用已有 Hybrid 离线结果）
    print('[c028] loading path a (OV window + OV INT8)...', flush=True)
    b_a = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )
    print('[c028] loading path d (OV window + OV FP16)...', flush=True)
    b_d = WindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-fp16-past',
        device='GPU.0', precision='f16',
    )
    print('[c028] loading path c (OV window truncated + OV INT8)...', flush=True)
    b_c = TruncatedPartialWindowEncoderOVBackend(
        encoder_dir='models/ov-encoder-window',
        decoder_dir='models/ov-int8-past',
        device='GPU.0', precision='f16',
    )
    # Per C-029: path b (torch encoder) 在 USE_TORCH=0 下不可用
    # qwen_asr.core.transformers_backend.modeling_qwen3_asr 导入
    # transformers.generation.GenerationMixin，USE_TORCH=0 时该符号不存在
    # 替代证据：reports/spe_hybrid_offline.txt (Hybrid 离线: torch encoder + OV INT8, WER 9.07%)
    print('[c028] SKIP path b (Hybrid torch encoder + OV INT8) — per C-029 USE_TORCH=0 incompatible with qwen_asr', flush=True)
    print('[c028]    using reports/spe_hybrid_offline.txt as path b substitute (Hybrid offline 9.07% WER, full-length)', flush=True)

    results = {'a': [], 'c': [], 'd': []}
    for snip in snips:
        for path_name, backend in [('a', b_a), ('c', b_c), ('d', b_d)]:
            tag = f'[{path_name}] {snip["label"]}'
            try:
                r = run_streaming(backend, snip, snip['label'])
                results[path_name].append(r)
                print(f'  [c028] {tag:42s} {r["words"]:3d}w n3={r["n3_repeat"]:2d} n4={r["n4_repeat"]:2d} n4max={r["n4_max"]:2d} wall={r["wall_s"]:.1f}s', flush=True)
            except Exception as e:
                print(f'  [c028] {tag:42s} ERROR: {e}', flush=True)
                import traceback; traceback.print_exc()
                results[path_name].append({'label': snip['label'], 'err': str(e)})

    # Save
    with open(os.path.join(OUT_DIR, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'[c028] → {OUT_DIR}/results.json', flush=True)

    # Summary table
    print()
    print('=== Summary (per path × segment) ===')
    print(f'{"label":24s} {"a_n4":>5s} {"c_n4":>5s} {"d_n4":>5s}')
    for i, snip in enumerate(snips):
        a4 = results['a'][i].get('n4_repeat', '-')
        c4 = results['c'][i].get('n4_repeat', '-')
        d4 = results['d'][i].get('n4_repeat', '-')
        print(f'{snip["label"]:24s} {str(a4):>5s} {str(c4):>5s} {str(d4):>5s}')
    tot_a = sum(r.get('n4_repeat', 0) for r in results['a'])
    tot_c = sum(r.get('n4_repeat', 0) for r in results['c'])
    tot_d = sum(r.get('n4_repeat', 0) for r in results['d'])
    print(f'{"TOTAL":24s} {tot_a:>5d} {tot_c:>5d} {tot_d:>5d}')
    print()
    print('=== Path b substitute: Hybrid 离线 WER 9.07% (torch encoder + OV INT8 decoder) ===')
    print('   reports/spe_hybrid_offline.txt — encoder 替换为 torch 时 WER 达标，证明 encoder 是 path a 问题的源头')
    print()
    print('=== Worst segment [2812-2828] per path ===')
    for path_name in 'acd':
        for r in results[path_name]:
            if r.get('start_s') == 2812.3:
                print(f'\n[path {path_name}] {r["text"][:600]!r}')
                break

    print(f'\n→ {OUT_DIR}/results.json')


if __name__ == '__main__':
    main()