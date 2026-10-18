"""c086a_full61_all_npu.py — C-086#1：**全 NPU 在 61 min 全长真实音频上的端到端**。

## 为什么要再跑一次全长

C-085 已经在 12–27 min 切片上把「全 NPU（enc@NPU + dec@NPU）」跑通并定稿：
RTF 0.7782、WER 6.643%、GPU 占用 0。但那个切片只有 15 min，本项目历史上所有
**交付级真值**（RTF / WER）都是**全长 61 min** 口径，且 C-081 已证明两个口径差异
很大（同一配置 A：全长 7.798% vs 子切片 5.961%）。用户要求直接看全长的数，
所以这里把同一配置扩到全长，与历史真值直接可比。

## 口径（严格照抄 C-085 / c081t，避免第二次踩坑）

- 音频：`test_audio/<redacted>.wav`，3671.19 s（61.2 min），全量不做二次切片
- 参照系统（配置 A）：`reports/c048_61min_adaptive/transcript_adaptive.txt`
  —— 这就是 c081t 里精确复现 7.798% 的那份转写，226 段、n_ref 11067
- WER 判据：method_b 全局对齐归因 + 配对 bootstrap 5000 次
  （method A 时间桶对齐已被 C-059#4 证伪，绝对值虚高到 81%，禁用）
- RTF：会话内多步中位（每 chunk 新建 InferRequest、chunk 内复用，C-069 口径）
- 其余全部与 C-085 一致：同一 cleanie INT8 decoder IR、同一 `seg_stream`
  生产逻辑、同一 warmup sweep、同一 max_new_tokens / budget 配置

## 长跑踩坑防护（C-085 付了 2 小时学费）

1. **probe 中途落盘**：起后台守护线程每 150 s 把 `be.probe` dump 到
   `probe_checkpoint.json`。上次 `pr = be.probe` 写在使用点之后 → UnboundLocalError，
   跑了两小时才发现 probe 全丢；这次崩了/被杀了也还能看到已积累的分项数据。
2. **进度可见**：日志重定向到文件（不用 `| tail`，管道缓冲会吞掉全部输出），
   且 python -u 无缓冲。
3. **不误判卡死**：本脚本自己打印 `heartbeat`，同时把内存/CPU 变化写进日志。
4. **先导**：仍保留 `C086A_START/END` 环境变量做小切片先导（默认 0–3671 全长）。

输出：reports/c086_full61/{summary.json, transcript_all_npu_full.txt}
"""
import json
import os
import sys
import threading
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
SLICE_START_SEC = int(os.environ.get('C086A_START', 0))
SLICE_END_SEC = int(os.environ.get('C086A_END', 10 ** 9))   # 默认全长
CHUNK_SEC = 0.64
ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/qwen3-lm-int8sym-cleanie-ov'
OUT_DIR = 'reports/c086_full61'
WARMUP_SWEEP_SEC = [5, 12, 18]
CKPT_INTERVAL_S = 150.0
# 参照系统 = 配置 A 全长 61 min 真值（c081t 复现 7.798%）
REF_A_FULL = 'reports/c048_61min_adaptive/transcript_adaptive.txt'
A_KNOWN_FULL_61 = 7.798


def pct(v, q):
    return float(np.percentile(np.asarray(v, dtype=np.float64), q * 100))


def agg(v):
    if not v:
        return {}
    return {'median': round(float(np.median(v)), 1),
            'mean': round(float(np.mean(v)), 2),
            'p95': round(pct(v, 0.95), 1), 'n': len(v),
            'sum': round(float(np.sum(v)), 1)}


def start_checkpointer(be, stop_evt):
    """周期性把 probe 落盘——长跑崩了也不能把分项数据全丢掉。"""
    path = f'{OUT_DIR}/probe_checkpoint.json'

    def loop():
        while not stop_evt.wait(CKPT_INTERVAL_S):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({k: [round(float(x), 2) for x in v]
                               for k, v in be.probe.items()}, f)
                print(f'[ckpt] probe 快照 n_gen={len(be.probe["prefill_ms"])}',
                      flush=True)
            except Exception as e:       # checkpoint 绝不能弄崩主流程
                print('[ckpt] 失败（忽略）:', e, flush=True)

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th


def main():
    from c085a_smoke_all_npu import make_all_npu_backend
    from seg_stream import SegmentedStreamer
    from c058q_wordcount import save_transcript

    info = sf.info('test_audio/<redacted>.wav')
    total_sec = info.duration
    end_sec = min(SLICE_END_SEC, int(total_sec))
    audio, _ = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[SR * SLICE_START_SEC:SR * end_sec]
    audio_sec = len(a) / SR
    assert audio_sec > 60, audio_sec
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f'[c086a] 切片 {audio_sec:.1f}s '
          f'（{SLICE_START_SEC}–{end_sec} s / 全长 {total_sec:.1f}s）', flush=True)

    be = make_all_npu_backend(ENC_DIR, DEC_DIR)
    print(f'[c086a] 编译 enc {be.npu_enc_compile_s}s / dec {be.npu_compile_s}s',
          flush=True)

    for s in WARMUP_SWEEP_SEC:
        SegmentedStreamer(
            be, strategy='off', chunk_size_sec=CHUNK_SEC,
            unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
            adaptive_budget=True, enable_hallucination_reset=False
        ).run(a[:SR * s])
    print('[c086a] warmup done', flush=True)

    # ── 计时前先把 probe 引用取好（上次的 UnboundLocalError 就出在这）────
    pr = be.probe

    streamer = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)

    stop_evt = threading.Event()
    start_checkpointer(be, stop_evt)

    t0 = time.perf_counter()
    text, segs = streamer.run(a, progress=True)
    wall = time.perf_counter() - t0
    stop_evt.set()

    tp = save_transcript(segs, f'{OUT_DIR}/transcript_all_npu_full.txt')
    print(f'[c086a] wall {wall:.1f}s RTF {wall/audio_sec:.4f}', flush=True)

    with open(f'{OUT_DIR}/probe_raw.json', 'w', encoding='utf-8') as f:
        json.dump({k: [round(float(x), 2) for x in v]
                   for k, v in pr.items()}, f)

    rtfs = [x['rtf'] for x in segs if x.get('rtf', 0) > 0]
    res = {
        'cfg': 'all_npu',
        'cfg_name': 'enc@NPU + dec@NPU (cleanie INT8_SYM)',
        'devices': {'encoder': 'NPU', 'decoder': 'NPU'},
        'encoder_dir': ENC_DIR, 'decoder_dir': DEC_DIR,
        'npu_enc_compile_s': be.npu_enc_compile_s,
        'npu_dec_compile_s': be.npu_compile_s,
        'scope': 'full61min',
        'slice': [SLICE_START_SEC, end_sec],
        'full_audio_sec': round(total_sec, 2),
        'audio_sec': round(audio_sec, 2),
        'wall_s': round(wall, 2),
        'overall_rtf': round(wall / audio_sec, 4),
        'seg_rtf_p50': round(float(np.median(rtfs)), 4) if rtfs else None,
        'seg_rtf_p95': round(pct(rtfs, 0.95), 4) if rtfs else None,
        'seg_rtf_max': round(max(rtfs), 4) if rtfs else None,
        'n_segs': len(segs),
        'n_generate_calls': len(pr['prefill_ms']),
        'transcript_path': tp,
        'total_words': len(text.split()),
        'breakdown': {k: agg(pr[k]) for k in ('enc_ms', 'prefill_ms', 'decode_ms')},
        'n_decode': agg(pr['n_decode']),
        'out_tokens': agg(pr['out_tokens']),
        'prompt_len': agg(pr['prompt_len']),
        'reference_system_full61min': REF_A_FULL,
        'A_known_wer_full61min': A_KNOWN_FULL_61,
    }
    print(json.dumps({k: v for k, v in res.items()}, ensure_ascii=False,
                     indent=2), flush=True)

    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('saved ->', f'{OUT_DIR}/summary.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
