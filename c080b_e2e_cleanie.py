"""c080b_e2e_cleanie.py — C-080#3：INT4/INT8 cleanie NPU 解码器端到端。

按 `status/CORRECTIONS.md` C-080 执行：

  1. `models/qwen3-lm-{int4,int8}sym-cleanie-ov` 接进 `seg_stream`（prompt 拼接
     在 Python 里做，见 `npu_embeds_backend.py`）；
  2. 每个 chunk 照生产逻辑 `reset_state()` + 全量 prefill，自适应
     max_new_tokens 与 EOS 规则与生产一致（直接复用 `seg_stream` /
     `streaming_asr`，没有另写一套）；
  3. 12–27 分钟切片、全新进程、GPU encoder + NPU decoder、
     计时子进程 `USE_TORCH=0`；
  4. 报 WER + 配对 CI（对 ABBA 配置 A 的同一切片转写，paired_bootstrap 5000）、
     P50 / 整体 RTF、每块耗时中 prefill 与 decode 分项、GPU compute 占用。

## 与 c062r 的关键差别

生产配置 A 的 decoder 有 cross-attention（音频走 `encoder_hidden_states` 端口），
cleanie 没有（音频铺进 embedding）。所以两者的 encoder 调用次数、prefill 次数、
prompt 长度都不同，**RTF 必须实测**，不能用 C-079 的倍数法外推 —— 那个倍数法是
给「同图不同设备」用的，这里换了 decoder 形态。

## GPU 占用

`--guard` 会把本作业的 PID 交给 `c058l_gpu_guard.py`（独立进程）。guard 只在正常
退出时写 JSON，中途被 kill 报告就丢了，所以它必须比作业活得久。

用法：
  .venv python c080b_e2e_cleanie.py --guard          # INT4 + INT8 + 配对 CI 汇总
  .venv python c080b_e2e_cleanie.py --guard-seconds 3600
  .venv python c080b_e2e_cleanie.py --child int4    # 内部
"""
import json
import os
import subprocess
import sys
import time

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

AUDIO = 'test_audio/<redacted>.wav'
SR = 16000
SLICE_START_SEC = 12 * 60      # 与 C-062 ABBA 完全同一切片（配对 WER 需要）
SLICE_END_SEC = 27 * 60
CHUNK_SEC = 0.64
WARMUP_SWEEP_SEC = [5, 12, 18]  # 与 c062r 一致，覆盖到接近 VAD 段上限
ENC_DIR = 'models/ov-encoder-segment-reviewer'

CFG = {
    'int4': 'models/qwen3-lm-int4sym-cleanie-ov',
    'int8': 'models/qwen3-lm-int8sym-cleanie-ov',
}
NAMES = {
    'int4': 'INT4_SYM cleanie @NPU + FP16 enc @GPU',
    'int8': 'INT8_SYM cleanie @NPU + FP16 enc @GPU',
}
OUT_DIR = 'reports/c080_e2e'
REF_A = 'reports/c062_abba/transcripts/transcript_A_rep0.txt'
# C-060 定规：参考词表必须是外部参考（MiniMax），不是参照系统 A。
# 时间戳是整段坐标，需要 +SLICE_START_SEC 平移到切片坐标。
MINIMAX = 'reports/c026_minimax_transcript.txt'


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
    import soundfile as sf
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR, sr
    a = audio[SR * SLICE_START_SEC:SR * SLICE_END_SEC]
    dur = len(a) / SR
    assert abs(dur - (SLICE_END_SEC - SLICE_START_SEC)) < 1.0, dur
    return a, dur


def run_child(cfg):
    import numpy as np
    from npu_embeds_backend import NPUEmbedsDecoderBackend
    from seg_stream import SegmentedStreamer
    from c058q_wordcount import count_words, save_transcript

    audio, dur = load_slice()
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f'[c080b:{cfg}] 切片 {dur:.1f}s', flush=True)

    be = NPUEmbedsDecoderBackend(encoder_dir=ENC_DIR, decoder_dir=CFG[cfg])
    print(f'[c080b:{cfg}] NPU 编译 {be.npu_compile_s}s', flush=True)

    for s in WARMUP_SWEEP_SEC:
        SegmentedStreamer(
            be, strategy='off', chunk_size_sec=CHUNK_SEC,
            unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
            adaptive_budget=True,
            enable_hallucination_reset=False).run(audio[:SR * s])
    print(f'[c080b:{cfg}] warmup done', flush=True)

    streamer = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)

    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0

    tp = save_transcript(segs, f'{OUT_DIR}/transcript_{cfg}_npu.txt')

    # ── 分项耗时（会话内口径，不新建请求计数） ────────────────────
    pr = be.probe

    def agg(v):
        if not v:
            return {}
        return {'median': round(float(np.median(v)), 1),
                'mean': round(float(np.mean(v)), 2),
                'p95': round(pct(v, 0.95), 1), 'n': len(v),
                'sum': round(float(np.sum(v)), 1)}

    rtfs = [x['rtf'] for x in segs if x.get('rtf', 0) > 0]
    res = {
        'cfg': cfg, 'cfg_name': NAMES[cfg], 'decoder_dir': CFG[cfg],
        'encoder_dir': ENC_DIR,
        'npu_compile_s': be.npu_compile_s,
        'slice': [SLICE_START_SEC, SLICE_END_SEC],
        'audio_sec': round(dur, 1),
        'wall_s': round(wall, 1),
        'overall_rtf': round(wall / dur, 4),
        'seg_rtf_p50': round(pct(rtfs, 0.50), 4),
        'seg_rtf_p95': round(pct(rtfs, 0.95), 4),
        'seg_rtf_max': round(max(rtfs), 4) if rtfs else 0.0,
        'n_segs': len(segs),
        'total_words': count_words(segs),
        'transcript': tp,
        'breakdown': {
            'enc_ms': agg(pr['enc_ms']), 'prefill_ms': agg(pr['prefill_ms']),
            'decode_ms_total_per_call': agg(pr['decode_ms']),
            'n_decode_steps_per_call': agg(pr['n_decode']),
            'out_tokens_per_call': agg(pr['out_tokens']),
            'prompt_len': agg(pr['prompt_len']),
            'n_audio_tokens': agg(pr['n_audio']),
            'budget': agg(pr['budget']),
        },
        'n_generate_calls': len(pr['prefill_ms']),
        'pid': os.getpid(),
        'guard_report': f'reports/c058_gpu_guard_c080_{cfg}.json',
    }
    # 每块耗时里的 prefill / decode 分项
    b = res['breakdown']
    tot = (b['enc_ms'].get('sum', 0) + b['prefill_ms'].get('sum', 0)
           + b['decode_ms_total_per_call'].get('sum', 0))
    res['share_of_accounted_ms'] = {
        'enc': round(b['enc_ms'].get('sum', 0) / tot, 4) if tot else None,
        'prefill': round(b['prefill_ms'].get('sum', 0) / tot, 4) if tot else None,
        'decode': round(b['decode_ms_total_per_call'].get('sum', 0) / tot, 4) if tot else None,
        'accounted_s': round(tot / 1000, 1),
        'wall_s': round(wall, 1),
        'accounted_share_of_wall': round(tot / (wall * 1000), 4),
    }
    res['text_head'] = text[:400]
    del be
    return res


def _shift(segs, offset):
    """把转写里的时间戳整体平移（切片是从 12 min 开始的）。"""
    return [(None if s is None else s + offset,
             None if e is None else e + offset, w) for s, e, w in segs]


def score(ref_path, cand_path, iters=5000, base_path=MINIMAX):
    """配对 bootstrap，口径按 C-060 定规。

    C-060 要求：**baseline 词表必须用外部参考（MiniMax），不是参照系统 A**。
    参考词表决定分母；用 A 自己的词表当分母会把「A 本身的错误」从分子里抹掉。

    配对单元：cleanie 的 VAD 段（候选自己的段边界）。MiniMax 是 ~0.1 s 碎片，
    必须用 `align_to_segments` 聚合到 cleanie 的段网格上。
    统计量 = WER(A) − WER(cleanie)，**正值 = cleanie 更差**（与 reviewer 口径一致）。

    ⚠️ 三份转写的时间戳基准不同：A_rep0 已经是切片坐标；cleanie 也是切片坐标；
    只有 MiniMax 是整段坐标，所以要先加 12 min 偏移。
    """
    from c058b_paired_bootstrap import (parse, align_to_segments,
                                        paired_delta, edit_counts)
    cand = parse(cand_path)                      # 切片坐标
    ref = parse(ref_path)                        # 切片坐标
    minimax = _shift(parse(base_path), SLICE_START_SEC)   # 整段 → 切片坐标

    # 用 cleanie 的段网格配对（候选是本次的主角）
    grid = [(st, en, ws) for st, en, ws in cand]
    base = align_to_segments(minimax, grid)      # 每段的参考词表
    d = paired_delta(cand, ref, base, iters=iters)
    d.update({
        'n_cand_segs': len(cand), 'n_ref_A_segs': len(ref),
        'n_baseline_segs': len(minimax),
        'baseline': base_path,
        'baseline_shift_sec': SLICE_START_SEC,
        'paired_on': 'cleanie 的 VAD 段网格，参考词表来自 MiniMax',
        'ref_words': sum(len(w) for _, _, w in base),
    })
    return d


def absolute_wer(ref_path, cand_path, base_path=MINIMAX):
    """相对 MiniMax 参考的绝对 WER（cleanie 与 A 各算一次）。只作补充。"""
    from c058b_paired_bootstrap import parse, align_to_segments, edit_counts
    c = parse(cand_path)
    grid = [(st, en, ws) for st, en, ws in c]
    base = align_to_segments(_shift(parse(base_path), SLICE_START_SEC), grid)
    refw = [w for _, _, s in base for w in s]
    out = {}
    for name, path in (('cleanie', cand_path), ('A', ref_path)):
        h = [w for _, _, s in parse(path) for w in s]
        if not refw or not h:
            continue
        S, D, I = edit_counts(refw, h)
        out[name] = {'words': len(h), 'S': S, 'D': D, 'I': I,
                     'wer_pct': round(100.0 * (S + D + I) / len(refw), 3)}
    out['ref_words_minimax'] = len(refw)
    return out


def main():
    argv = sys.argv[1:]
    if '--child' in argv:
        cfg = argv[argv.index('--child') + 1]
        r = run_child(cfg)
        print('\n__RESULT__' + json.dumps(r, ensure_ascii=False), flush=True)
        return 0

    guard_s = 3600
    if '--guard-seconds' in argv:
        guard_s = int(argv[argv.index('--guard-seconds') + 1])

    os.makedirs(OUT_DIR, exist_ok=True)
    # C-080 指定「INT4_SYM 先跑，INT8_SYM 后跑」。但 c080f 的重复测量显示
    # INT4 cleanie 在 NPU 上**确定性地**输出人造物（3/3 次都是 "yay"，
    # CPU 上 4/4 次都是正常人话）。这是 INT4 × NPUW 的组合失败，比 C-080#4
    # 的止损线（RTF>0.9 / CI 下界>0）严重得多，且是确定性的、不可复现为正常。
    # 按止损线在 IR 层面排除 INT4，只对 INT8 跑 15 分钟端到端 ——
    # 否则 15 分钟只会得到一份 100% WER 的废数据。
    # `--force-int4` 可覆盖这个判断（留痕：需要 reviewer 明确推翻 c080f）。
    order = ['int4', 'int8'] if '--force-int4' in argv else ['int8']
    if order == ['int8']:
        print('[c080b] INT4_SYM 已被 c080f 在 IR 层面排除'
              '（NPU 上确定性人造物，CPU 上正常）→ 本轮只跑 INT8。',
              flush=True)
    guard_pids, guard_procs = [], []
    if '--guard' in argv:
        for cfg in order:
            tag = f'c080_{cfg}'
            env = dict(os.environ)
            env.update({'USE_TORCH': '0', 'USE_TF': '0', 'USE_FLAX': '0',
                        'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
            gp = subprocess.Popen(
                [sys.executable, 'c058l_gpu_guard.py', '0', tag,
                 str(guard_s), 'c080b_e2e_cleanie.py'],
                env=env, stdout=open(f'{OUT_DIR}/guard_{tag}.log', 'w'),
                stderr=subprocess.STDOUT)
            guard_procs.append((tag, gp))
            print(f'[c080b] guard 启动 {tag} pid={gp.pid} {guard_s}s',
                  flush=True)
            time.sleep(2)

    results = {}
    for cfg in order:
        print(f'\n[c080b] === {cfg}: {NAMES[cfg]} ===', flush=True)
        env = dict(os.environ)
        env.update({'USE_TORCH': '0', 'USE_TF': '0', 'USE_FLAX': '0',
                    'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
        p = subprocess.run([sys.executable, __file__, '--child', cfg],
                           capture_output=True, env=env)
        out = p.stdout.decode('utf-8', errors='replace')
        err = p.stderr.decode('utf-8', errors='replace')
        line = [l for l in out.splitlines() if l.startswith('__RESULT__')]
        if not line:
            print(f'[c080b] {cfg} 子进程失败\n{out[-2000:]}\n{err[-2500:]}')
            results[cfg] = {'error': 'child failed',
                            'stdout_tail': out[-2000:],
                            'stderr_tail': err[-2500:]}
            continue
        r = json.loads(line[0][len('__RESULT__'):])
        results[cfg] = r
        print(f'[c080b] {cfg}: P50={r["seg_rtf_p50"]} overall={r["overall_rtf"]} '
              f'words={r["total_words"]} wall={r["wall_s"]}s', flush=True)

    # ── 配对 CI（对 ABBA 配置 A 的同一切片） ──────────────────────
    for cfg in order:
        r = results.get(cfg)
        if not r or r.get('error') or not os.path.exists(REF_A):
            continue
        r['paired_vs_A'] = score(REF_A, f'{OUT_DIR}/transcript_{cfg}_npu.txt')
        r['absolute_vs_A'] = absolute_wer(
            REF_A, f'{OUT_DIR}/transcript_{cfg}_npu.txt')

    # guard 收尾：让 guard 正常退出才会写 JSON
    for tag, gp in guard_procs:
        try:
            gp.wait(timeout=max(5, guard_s - 20))
        except Exception:
            gp.terminate()

    rep = {
        'note': 'C-080#3：cleanie IR 的 NPU 解码器端到端。'
                'GPU encoder（生产 models/ov-encoder-segment-reviewer）+ '
                'NPU decoder，12–27 min 切片，fresh 进程，USE_TORCH=0。'
                '判据：WER 配对 CI（对 ABBA 配置 A 同一切片，5000 次）+ '
                '实测 RTF。止损线 RTF>0.9 或 CI 下界>0。',
        'int4_gated_out': {
            'reason': 'c080f 重复测量：INT4 cleanie 在 NPU 上 3/3 次输出'
                      '人造物（"yay"），CPU 上 4/4 次输出人话；'
                      '确定性失败，定位在 INT4 × NPUW 组合。'
                      '按 C-080#4 止损，不跑 15 分钟端到端。',
            'evidence': 'reports/c080f_int4_stability.json',
            'override_flag': '--force-int4',
        } if order == ['int8'] else None,
        'reference_for_wer': REF_A + '（ABBA 配置 A = 交付基线）',
        'slice_sec': [SLICE_START_SEC, SLICE_END_SEC],
        'chunk_sec': CHUNK_SEC,
        'warmup_sweep_sec': WARMUP_SWEEP_SEC,
        'npu_max_prompt_len': 512,
        'stop_loss': {'rtf_gt': 0.9, 'ci_lower_gt': 0.0},
        'by_cfg': results,
    }
    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('\nsaved ->', f'{OUT_DIR}/summary.json')
    for cfg in order:
        r = results.get(cfg) or {}
        pv = r.get('paired_vs_A') or {}
        print(f"  {cfg:5s} RTF={r.get('overall_rtf')} P50={r.get('seg_rtf_p50')} "
              f"WER(cand)={pv.get('wer_cand')} WER(A)={pv.get('wer_ref')} "
              f"Δ={pv.get('delta_pp')} CI=[{pv.get('ci95_lo')},"
              f"{pv.get('ci95_hi')}]")
    return 0


if __name__ == '__main__':
    sys.exit(main())
