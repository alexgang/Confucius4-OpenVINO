"""c062r_abba_speed.py — C-062#2：用交替运行确认「全量 INT4 真的更快」

reviewer 的要求（`status/CORRECTIONS.md` C-062 第二节）：
  「P95 是不稳定的指标，不要用它来证明"变快"。**判据请用 P50 与 overall RTF，
    并用交替运行确认。**」

  交替运行规格：
    - 音频取 **12–27 分钟这 15 分钟**（与评测区重合，不碰校准区）
    - **ABBA 顺序**，每个配置 **≥3 次**
    - 每次 **fresh 进程**（否则后一个配置会沾前一个的缓存/编译状态）
    - 开 **guard**，存**逐段 RTF** 和**转写**
    - 报告 **P50 / overall RTF 的中位数和范围**，以及相对 A 的百分比
    - **P95 / max 只列出，不做显著性结论**

三个配置：
    A = FP16 enc + INT8 dec          （当前交付）
    B = FP16 enc + INT4 全量 dec     （C-060 重跑的那个）
    C = INT4 enc + INT4 全量 dec     （推荐候选）

为什么必须 fresh 进程 + ABBA
---------------------------
C-061#3 已证实：同进程内先跑的配置会吃冷启动（kernel / shape 编译），
后跑的沾光，方向固定。ABBA 让「顺序」这个混淆因子在两组上对称抵消；
fresh 进程则消除残留的内存与编译状态。

用法：
  .venv python c062r_abba_speed.py                # 完整 ABBA，3 次/配置
  .venv python c062r_abba_speed.py --reps 4       # 每配置 4 次
  .venv python c062r_abba_speed.py --child <cfg> <rep>   # 内部用
输出：
  reports/c062_abba/child_<cfg>_<rep>.json      每轮的 summary + 转写路径
  reports/c062_abba/summary.json               汇总（P50 / overall RTF 中位数与范围）
"""
import json
import os
import subprocess
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
# ⚠️ 这三个必须设：否则 `transformers` 会 import torch，而本机的应用控制策略
# （WinError 4551）会拦掉 torch_python.dll。`c058c` 等脚本都设了，这里也要。
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
from c058q_wordcount import count_words, save_transcript

AUDIO = 'test_audio/<redacted>.wav'
SR = 16000

# reviewer 指定：12–27 分钟这 15 分钟，与评测区重合（不碰 0–12 分钟校准区）
SLICE_START_SEC = 12 * 60
SLICE_END_SEC = 27 * 60

CFG = {
    'A': ('models/ov-encoder-segment-reviewer',     'models/ov-int8-past'),
    'B': ('models/ov-encoder-segment-reviewer',     'models/ov-int4-lmhead-past'),
    'C': ('models/ov-encoder-segment-reviewer-int4', 'models/ov-int4-lmhead-past'),
}
NAMES = {
    'A': 'FP16 enc + INT8 dec（交付）',
    'B': 'FP16 enc + INT4全量 dec',
    'C': 'INT4 enc + INT4全量 dec（推荐）',
}

# C-061#3：warmup 扫多种长度，覆盖到接近 VAD 段上限；都 ≤18 s 不撞 MAX_FRAMES
WARMUP_SWEEP_SEC = [5, 12, 18]
OUT_DIR = 'reports/c062_abba'


def pct(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(int(len(s) * q), len(s) - 1)]


def med(v):
    if not v:
        return 0.0
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def load_slice():
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR, sr
    a = audio[SR * SLICE_START_SEC:SR * SLICE_END_SEC]
    dur = len(a) / SR
    assert abs(dur - (SLICE_END_SEC - SLICE_START_SEC)) < 1.0, dur
    return a, dur


def run_child(cfg, rep):
    enc_dir, dec_dir = CFG[cfg]
    audio, dur = load_slice()

    os.makedirs(f'{OUT_DIR}/transcripts', exist_ok=True)
    backend = SegmentEncoderOVBackend(encoder_dir=enc_dir, decoder_dir=dec_dir,
                                      device='GPU.0', precision='f16')
    for s in WARMUP_SWEEP_SEC:
        SegmentedStreamer(
            backend, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            enable_hallucination_reset=False).run(audio[:SR * s])

    streamer = SegmentedStreamer(
        backend, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0

    rtfs = [x['rtf'] for x in segs if x.get('rtf', 0) > 0]
    tp = save_transcript(
        segs, f'{OUT_DIR}/transcripts/transcript_{cfg}_rep{rep}.txt')

    res = {
        'cfg': cfg, 'cfg_name': NAMES[cfg], 'rep': rep,
        'enc_dir': enc_dir, 'dec_dir': dec_dir,
        'slice': [SLICE_START_SEC, SLICE_END_SEC], 'audio_sec': round(dur, 1),
        'wall_s': round(wall, 1),
        'overall_rtf': round(wall / dur, 4),
        # 判据指标
        'seg_rtf_p50': round(pct(rtfs, 0.50), 4),
        # 只列出，不做显著性结论
        'seg_rtf_p95': round(pct(rtfs, 0.95), 4),
        'seg_rtf_max': round(max(rtfs), 4) if rtfs else 0.0,
        'n_segs': len(segs), 'total_words': count_words(segs),
        'transcript': tp,
        'seg_rtfs': [{'label': i, 'start': round(x['start_s'], 1),
                      'end': round(x['end_s'], 1),
                      'rtf': round(x.get('rtf', 0), 4),
                      'n_chunks': x.get('n_chunks', 0)}
                     for i, x in enumerate(segs)],
        'pid': os.getpid(),
    }
    del backend
    return res


def abba_sequence(reps):
    """构造 ABBA 序列：A B B A | A B B A | ...

    reviewer 要求「ABBA 顺序，每个配置 ≥3 次」。
    每个 rep 贡献 A×2 / B×2 / C×2，即每配置 2×reps 次 ≥3（reps≥2）。
    """
    seq = []
    for _ in range(reps):
        seq += ['A', 'B', 'C', 'C', 'B', 'A']
    return seq


def main():
    argv = sys.argv[1:]
    if '--child' in argv:
        i = argv.index('--child')
        cfg, rep = argv[i + 1], int(argv[i + 2])
        r = run_child(cfg, rep)
        print('\n__RESULT__' + json.dumps(r, ensure_ascii=False), flush=True)
        return 0

    reps = 2
    if '--reps' in argv:
        reps = int(argv[argv.index('--reps') + 1])
    assert reps >= 2, '每配置需 ≥3 次 → reps ≥2（每 rep 贡献每配置 2 次）'

    os.makedirs(OUT_DIR, exist_ok=True)
    seq = abba_sequence(reps)
    print(f'[c062r] 音频切片 {SLICE_START_SEC/60:.0f}–'
          f'{SLICE_END_SEC/60:.0f} min（{(SLICE_END_SEC-SLICE_START_SEC)/60:.0f} min）')
    print(f'[c062r] ABBA 序列 {len(seq)} 轮: {seq}')
    print(f'[c062r] 每配置 {2*reps} 次 fresh 进程，warmup={WARMUP_SWEEP_SEC}')
    print('[c062r] ⚠️ 计时期间必须另开 c058l_gpu_guard.py', flush=True)

    results = []
    for i, cfg in enumerate(seq):
        print(f'\n[c062r] {i+1}/{len(seq)}: {cfg} {NAMES[cfg]}', flush=True)
        # 显式传环境：子进程必须拿到 USE_TORCH=0，否则 transformers 会 import
        # torch 并被本机应用控制策略拦掉（WinError 4551）。
        child_env = dict(os.environ)
        child_env.update({'USE_TORCH': '0', 'USE_TF': '0', 'USE_FLAX': '0',
                          'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
        p = subprocess.run(
            [sys.executable, __file__, '--child', cfg, str(i)],
            capture_output=True, env=child_env)
        out = p.stdout.decode('utf-8', errors='replace')
        line = [l for l in out.splitlines() if l.startswith('__RESULT__')]
        if not line:
            print(f'[c062r] 子进程失败:\n{out[-1500:]}\n'
                  f'{p.stderr.decode("utf-8", errors="replace")[-1500:]}')
            return 1
        r = json.loads(line[0][len('__RESULT__'):])
        r['seq_pos'] = i
        results.append(r)
        print(f'[c062r]   P50={r["seg_rtf_p50"]:.4f} '
              f'overall={r["overall_rtf"]:.4f} '
              f'(P95={r["seg_rtf_p95"]:.4f} 仅列出) pid={r["pid"]}', flush=True)

    summary = build_summary(results, seq)
    out = f'{OUT_DIR}/summary.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {out}')

    print('\n=== C-062#2 判据表：P50 与 overall RTF ===')
    print(f'{"配置":<30}{"n":>3}{"P50 中位":>11}{"P50 范围":>18}'
          f'{"RTF 中位":>11}{"RTF 范围":>18}{"vs A":>9}')
    a_p50 = summary['by_cfg']['A']['p50_median']
    a_rtf = summary['by_cfg']['A']['overall_rtf_median']
    for c in 'ABC':
        d = summary['by_cfg'][c]
        dp = (d['p50_median'] / a_p50 - 1) * 100
        dr = (d['overall_rtf_median'] / a_rtf - 1) * 100
        print(f'{d["name"]:<30}{d["n"]:>3}{d["p50_median"]:>11.4f}'
              f'{("[%.4f, %.4f]" % (d["p50_min"], d["p50_max"])):>18}'
              f'{d["overall_rtf_median"]:>11.4f}'
              f'{("[%.4f, %.4f]" % (d["overall_rtf_min"], d["overall_rtf_max"])):>18}'
              f'{("%+.1f%% / %+.1f%%" % (dp, dr)):>9}')
    print('\nP95 / max 只列出，不做显著性结论：')
    for c in 'ABC':
        d = summary['by_cfg'][c]
        print(f'  {d["name"]:<30} P95 {d["p95_list"]}  max {d["max_list"]}')
    return 0


def build_summary(results, seq):
    by = {}
    for c in 'ABC':
        rs = [r for r in results if r['cfg'] == c]
        p50 = [r['seg_rtf_p50'] for r in rs]
        rtf = [r['overall_rtf'] for r in rs]
        by[c] = {
            'name': NAMES[c], 'n': len(rs),
            'p50_median': round(med(p50), 4),
            'p50_min': min(p50), 'p50_max': max(p50),
            'p50_list': p50,
            'overall_rtf_median': round(med(rtf), 4),
            'overall_rtf_min': min(rtf), 'overall_rtf_max': max(rtf),
            'overall_rtf_list': rtf,
            'p95_list': [r['seg_rtf_p95'] for r in rs],
            'max_list': [r['seg_rtf_max'] for r in rs],
            'words_list': [r['total_words'] for r in rs],
            'pids': [r['pid'] for r in rs],
        }
    a = by['A']
    for c in 'BC':
        by[c]['p50_vs_A_pct'] = round(
            (by[c]['p50_median'] / a['p50_median'] - 1) * 100, 1)
        by[c]['rtf_vs_A_pct'] = round(
            (by[c]['overall_rtf_median'] / a['overall_rtf_median'] - 1) * 100, 1)
    return {
        'note': 'C-062#2：判据是 **P50 与 overall RTF**（中位数 + 范围）。'
                'ABBA 顺序、每配置 fresh 进程、warmup 扫多种长度。'
                'P95 / max 只列出，不做显著性结论（逐段强相关 + 运行间波动大）。',
        'slice_sec': [SLICE_START_SEC, SLICE_END_SEC],
        'slice_reason': 'reviewer 指定 12–27 分钟，与评测区重合，不碰 0–12 分钟校准区',
        'seq': seq,
        'reps_per_cfg': by['A']['n'],
        'warmup_sweep_sec': WARMUP_SWEEP_SEC,
        'by_cfg': by,
        'results': results,
    }


if __name__ == '__main__':
    sys.exit(main())
