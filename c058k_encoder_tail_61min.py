"""c058k_encoder_tail_61min.py — C-058 尾延迟专项：重跑并存**逐段** RTF

reviewer 追问（C-058 第五节）：
  「encoder INT4 这次的 seg_rtf_max = 0.805（FP16 是 0.676），P95 也从 0.638
    升到 0.689；请确认是**单点离群**还是**系统性**（看逐段 RTF 分布，
    必要时重跑该段）」

问题：`c057f` 只把 P50/P95/max **汇总分位数**存进 summary.json，**没存逐段序列**，
所以无法判断尾延迟是单点还是系统性 —— 必须重跑并存逐段 RTF。

本脚本对 FP16 / INT4 encoder 各跑一次 61 分钟（**串行、独占 GPU**），
保存逐段 (label, start, end, rtf, n_chunks)，供 `c058j_tail_latency.py` 配对分析。

⚠️ 与其它 GPU 任务必须串行（reviewer：C-053 的 RTF 就是并发作废的）。

C-061#3 的三处修正（reviewer 指出起始段偏慢可能是冷启动）：
  1. **warmup 覆盖更多输入长度**：原来只有 5 s，只覆盖一种 shape，FP16 先跑时
     吃满了 kernel / shape 编译。现在改为按长度扫描（见 `WARMUP_SWEEP`）。
  2. **ABBA 顺序**：原来固定 FP16 在前、INT4 在后，顺序与冷启动叠加。
     现在顺序为 FP16 → INT4 → INT4 → FP16（`--order abba`，默认），
     可用 `--order fp16_first` 退回旧顺序做对照。
  3. **各自 fresh 进程**：同一进程内先后加载两个 encoder 会互相污染
     （内存/缓存/编译状态）。`--order fresh` 时每个变体起一个独立子进程
     （`--child`），彻底隔离。**这是最干净的方案，默认用它。**

C-061#5 的修正：
  - 计词改用 `c058q_wordcount.count_words`（原来裸 `text.split()` 会因段间
    无分隔符粘连而少算约 206 个词，正是 reviewer 发现的 11042 vs 11248）。
  - **每次都保存转写**（原来没存，导致无法证明流水线确定性）。

用法：
  .venv python c058k_encoder_tail_61min.py                # fresh 进程（默认）
  .venv python c058k_encoder_tail_61min.py --order abba   # 同进程 ABBA
  .venv python c058k_encoder_tail_61min.py --child enc_fp16   # 内部用
输出：reports/c058_tail/summary_seg_rtf.json
"""
import os
import subprocess
import sys
import json
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer
from c058q_wordcount import count_words, save_transcript

AUDIO = 'test_audio/<redacted>.wav'
DEC = 'models/ov-int8-past'            # 固定 INT8 decoder，只变 encoder
VARIANTS = [
    ('enc_fp16', 'models/ov-encoder-segment-reviewer'),
    ('enc_int4', 'models/ov-encoder-segment-reviewer-int4'),
]
OUT_DIR = 'reports/c058_tail'

# C-061#3：warmup 要覆盖多种输入长度，不能只跑 5 s 一种 shape。
# ⚠️ 不能超过 MAX_FRAMES=2400 mel 帧（≈24 s），否则 `encode_audio` 会 assert。
# 取 5 / 12 / 18 s —— 覆盖从短段到接近 VAD 段上限（20 s）的各种 chunk 数与 KV 长度。
WARMUP_SWEEP_SEC = [5, 12, 18]


def pct(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(int(len(s) * q), len(s) - 1)]


def warmup(backend, audio, tag=''):
    """C-061#3：按多个输入长度扫描 warmup，覆盖 kernel / shape 编译。

    用**真实音频**而不是静音：静音可能被 VAD 直接跳过，拿不到 decoder 输出，
    编译也就不会发生。长度都 ≤18 s，不会撞 MAX_FRAMES=2400。
    """
    sr = 16000
    for secs in WARMUP_SWEEP_SEC:
        SegmentedStreamer(
            backend, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            enable_hallucination_reset=False).run(audio[:sr * secs])
        print(f'[c058k] warmup [{tag}] {secs}s done', flush=True)


def run(backend, audio, tag):
    streamer = SegmentedStreamer(
        backend, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0
    rtfs = [s['rtf'] for s in segs if s.get('rtf', 0) > 0]

    # C-061#5：统一计词 + 每次保存转写（原来两项都缺）
    tp = save_transcript(segs, f'{OUT_DIR}/transcript_{tag}.txt')
    n_words = count_words(segs)

    return {
        'tag': tag, 'wall_s': round(wall, 1),
        'overall_rtf': round(wall / (len(audio) / 16000), 3),
        'n_segs': len(segs),
        'total_words': n_words,               # 统一口径 c058q_wordcount
        'total_words_naive_split': len(text.split()),  # 保留旧口径供对照
        'transcript': tp,
        'seg_rtf_p50': round(pct(rtfs, .50), 3),
        'seg_rtf_p90': round(pct(rtfs, .90), 3),
        'seg_rtf_p95': round(pct(rtfs, .95), 3),
        'seg_rtf_p99': round(pct(rtfs, .99), 3),
        'seg_rtf_max': round(max(rtfs), 3),
        'n_gt_075': sum(1 for x in rtfs if x > 0.75),
        # 逐段序列 —— 这是回答「单点 vs 系统性」的关键
        'seg_rtfs': [{'label': s['seg_idx'], 'start': round(s['start_s'], 2),
                      'end': round(s['end_s'], 2), 'rtf': round(s['rtf'], 4),
                      'n_chunks': s.get('n_chunks', 0)} for s in segs],
    }


def run_one(tag, enc):
    """跑单个变体并返回结果 dict（供 fresh 模式与同进程模式共用）。"""
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    print(f'\n[c058k] === {tag}: {enc} ===', flush=True)
    backend = SegmentEncoderOVBackend(encoder_dir=enc, decoder_dir=DEC,
                                      device='GPU.0', precision='f16')
    print(f'[c058k] warmup sweep [{tag}] {WARMUP_SWEEP_SEC} ...', flush=True)
    warmup(backend, audio, tag)
    r = run(backend, audio, tag)
    del backend
    return r


def child(tag):
    """`--child <tag>` 模式：只跑一个变体，把结果打到 stdout 的标记行。"""
    enc = dict(VARIANTS)[tag]
    r = run_one(tag, enc)
    print('\n__RESULT__' + json.dumps(r, ensure_ascii=False), flush=True)
    return 0


def main():
    argv = sys.argv[1:]
    if '--child' in argv:
        return child(argv[argv.index('--child') + 1])

    order = 'fresh'
    if '--order' in argv:
        order = argv[argv.index('--order') + 1]

    os.makedirs(OUT_DIR, exist_ok=True)
    _, sr = sf.read(AUDIO, dtype='float32')
    print(f'[c058k] audio {AUDIO} decoder={DEC} 固定  order={order} '
          f'warmup_sweep={WARMUP_SWEEP_SEC}', flush=True)

    if order == 'fresh':
        # C-061#3 最干净的方案：每个变体独立子进程，无任何跨变体污染。
        # 顺序仍用 ABBA 以消除时间顺序的系统偏差。
        seq = ['enc_fp16', 'enc_int4', 'enc_int4', 'enc_fp16']
        results = []
        for i, tag in enumerate(seq):
            print(f'\n[c058k] fresh 轮 {i+1}/{len(seq)}: {tag}', flush=True)
            p = subprocess.run(
                [sys.executable, __file__, '--child', tag],
                capture_output=True)
            out = p.stdout.decode('utf-8', errors='replace')
            line = [l for l in out.splitlines() if l.startswith('__RESULT__')]
            if not line:
                print(f'[c058k] 子进程失败:\n{out[-2000:]}\n'
                      f'{p.stderr.decode("utf-8", errors="replace")[-2000:]}')
                return 1
            r = json.loads(line[0][len('__RESULT__'):])
            r['fresh_round'] = i + 1
            results.append(r)
            print(f'[c058k] round{i+1} {tag}: RTF={r["overall_rtf"]:.3f} '
                  f'P50={r["seg_rtf_p50"]:.3f} P95={r["seg_rtf_p95"]:.3f} '
                  f'max={r["seg_rtf_max"]:.3f} words={r["total_words"]}',
                  flush=True)
        # ABBA 的两个同配置轮次取**较差**的那个做汇总，保守
        merged = {}
        for tag, _ in VARIANTS:
            rs = [r for r in results if r['tag'] == tag]
            worst = max(rs, key=lambda x: x['seg_rtf_p95'])
            worst['abba_rounds'] = [x['seg_rtf_p95'] for x in rs]
            merged[tag] = worst
        results = [merged[t] for t, _ in VARIANTS]
    else:
        # 同进程模式，ABBA 顺序
        seq = ['enc_fp16', 'enc_int4', 'enc_int4', 'enc_fp16']
        results = []
        for i, tag in enumerate(seq):
            enc = dict(VARIANTS)[tag]
            r = run_one(tag, enc)
            r['fresh_round'] = i + 1
            results.append(r)
            print(f'[c058k] round{i+1} {tag}: RTF={r["overall_rtf"]:.3f} '
                  f'P95={r["seg_rtf_p95"]:.3f}', flush=True)
        merged = {}
        for tag, _ in VARIANTS:
            rs = [r for r in results if r['tag'] == tag]
            worst = max(rs, key=lambda x: x['seg_rtf_p95'])
            worst['abba_rounds'] = [x['seg_rtf_p95'] for x in rs]
            merged[tag] = worst
        results = [merged[t] for t, _ in VARIANTS]

    payload = {
        'order': order,
        'warmup_sweep_sec': WARMUP_SWEEP_SEC,
        'word_count_fn': 'c058q_wordcount.count_words',
        'results': results,
    }
    out = f'{OUT_DIR}/summary_seg_rtf.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {out}', flush=True)
    for r in results:
        print(f'  {r["tag"]}: P50={r["seg_rtf_p50"]:.3f} '
              f'P95={r["seg_rtf_p95"]:.3f} max={r["seg_rtf_max"]:.3f} '
              f'ABBA 各轮 P95={r["abba_rounds"]} '
              f'words={r["total_words"]} (naive={r["total_words_naive_split"]})',
              flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
