"""c057f_encoder_61min.py — C-057f: encoder INT4 的 61-min 端到端验收

C-057d/e 已证明：encoder FP16→INT4 体积 -73%、encoder 快 21%、内存省 10.6%，
但 teacher-forcing top-1 掉了 1.80 pp。本脚本用与交付验收完全相同的口径
（segment encoder + VAD 12–20 s + no reset + adaptive budget）跑 61-min 全量集，
decoder 固定 INT8，只换 encoder，得到：
  - 整体 RTF（含段级 P50/P95）
  - 输出文本的词数 / 3-gram / 4-gram 重复（幻觉与复读的廉价代理指标）
  - 两种 encoder 的 transcript 文本 diff（词级编辑率）

用法：.venv python c057f_encoder_61min.py
输出：reports/c057_61min_encoder/{summary.json,transcript_*.txt}
"""
import os
import sys
import re
import json
import time
from collections import Counter
from difflib import SequenceMatcher

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

OUT_DIR = 'reports/c057_61min_encoder'
ENC_FP16 = 'models/ov-encoder-segment-reviewer'
ENC_INT4 = 'models/ov-encoder-segment-reviewer-int4'
DEC = 'models/ov-int8-past'
AUDIO = 'test_audio/<redacted>.wav'
VARIANTS = [('enc_fp16', ENC_FP16), ('enc_int4', ENC_INT4)]


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    return [w for w in re.sub(r'\s+', ' ', s).strip().split() if w]


def ngram_stats(text, n_list=(3, 4)):
    ws = words(text)
    out = {'words': len(ws)}
    for n in n_list:
        c = Counter()
        for i in range(len(ws) - n + 1):
            c[tuple(ws[i:i + n])] += 1
        out[f'n{n}_repeat'] = sum(v - 1 for v in c.values() if v > 1)
        out[f'n{n}_max'] = max(c.values()) if c else 0
    return out


def run(backend, audio, dur, tag):
    print(f'\n[c057f] === {tag} ===', flush=True)
    streamer = SegmentedStreamer(
        backend, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0

    st = ngram_stats(text)
    rtfs = sorted(s['rtf'] for s in segs if s.get('rtf', 0) > 0)
    r = {
        'tag': tag,
        'wall_s': round(wall, 1), 'overall_rtf': round(wall / dur, 3),
        'n_segs': len(segs),
        'total_words': st['words'],
        'n3_repeat': st['n3_repeat'], 'n4_repeat': st['n4_repeat'],
        'n3_max': st['n3_max'], 'n4_max': st['n4_max'],
        'seg_rtf_p50': round(rtfs[len(rtfs) // 2], 3) if rtfs else 0,
        'seg_rtf_p95': round(rtfs[min(int(len(rtfs) * .95), len(rtfs) - 1)], 3)
                      if rtfs else 0,
        'seg_rtf_max': round(rtfs[-1], 3) if rtfs else 0,
        'text': text,
    }
    with open(f'{OUT_DIR}/transcript_{tag}.txt', 'w', encoding='utf-8') as f:
        for s in segs:
            f.write(f'[{s["start_s"]:7.1f}-{s["end_s"]:7.1f}] {s["text"]}\n')
    print(f'[c057f] {tag}: RTF={r["overall_rtf"]:.3f} wall={wall:.0f}s '
          f'segs={len(segs)} words={st["words"]} n3={st["n3_repeat"]} '
          f'n4={st["n4_repeat"]} P50={r["seg_rtf_p50"]} '
          f'P95={r["seg_rtf_p95"]}', flush=True)
    return r


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    dur = len(audio) / sr
    print(f'[c057f] audio {dur:.1f}s ({dur/60:.2f} min)  decoder=INT8 固定',
          flush=True)

    results = []
    for tag, enc in VARIANTS:
        backend = SegmentEncoderOVBackend(encoder_dir=enc, decoder_dir=DEC,
                                          device='GPU.0', precision='f16')
        print(f'[c057f] warmup [{tag}] ...', flush=True)
        SegmentedStreamer(
            backend, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            enable_hallucination_reset=False).run(audio[:16000 * 5])
        results.append(run(backend, audio, dur, tag))
        del backend

    # 词级 diff
    a, b = results[0], results[1]
    wa, wb = words(a['text']), words(b['text'])
    n_ed = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=wa, b=wb,
                                                autojunk=False).get_opcodes():
        if tag == 'replace':
            n_ed += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            n_ed += i2 - i1
        elif tag == 'insert':
            n_ed += j2 - j1
    a['word_diff'] = {'edits': n_ed, 'ref_words': len(wa),
                      'rate_pct': round(100.0 * n_ed / max(len(wa), 1), 2)}
    print(f'\n[c057f] 61-min 词级 diff：{n_ed}/{len(wa)} = '
          f'{a["word_diff"]["rate_pct"]}%', flush=True)
    print(f'[c057f] RTF {a["overall_rtf"]:.3f} → {b["overall_rtf"]:.3f} '
          f'({100*(b["overall_rtf"]/a["overall_rtf"]-1):+.1f}%)', flush=True)

    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT_DIR}/summary.json', flush=True)


if __name__ == '__main__':
    main()
