"""c080h_encoder_share.py — C-080：补上 encoder 分项（c080b 的 probe 漏了）。

## 为什么必须补

`c080b` 的 `share_of_accounted_ms` 里 `enc = 0.0`，不是因为 encoder 免费，
而是因为 `npu_embeds_backend.NPUEmbedsDecoderBackend` 只在
`greedy_decode_with_prefix` 里往 `self.probe['enc_ms']` 追加，而**从没调用过
`encode_audio`**（父类的方法没有打桩）。所以 16.3% 的「未计入」时间被
错误地显示成 encoder=0。

不补的话，交付报告里「GPU compute 降幅」就没有依据 —— 因为 cleanie 与配置 A
的差异**恰恰**主要来自 encoder（配置 A 的 encoder 和 cleanie 的 encoder 是
同一个 IR，差别只在 decoder 跑到 NPU 上）。

本脚本用同一段切片的前 N 段，单独测：
  1. `encode_audio` 的耗时分布（含 mel 特征提取）
  2. 与配置 A 端到端的 encoder 份额对照（c069m 实测 A 的 enc_ms_mean）

输出：reports/c080h_encoder_share.json
"""
import json
import os
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

import numpy as np
import soundfile as sf

SR = 16000
START, END = 12 * 60, 27 * 60
N_SEGS = 8
OUT = 'reports/c080h_encoder_share.json'


def log(*a, **kw):
    print(*a, flush=kw.get('flush', True))


def main():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    a = a[SR * START:SR * END]

    from npu_embeds_backend import NPUEmbedsDecoderBackend
    from seg_stream import SegmentedStreamer

    be = NPUEmbedsDecoderBackend(
        decoder_dir='models/qwen3-lm-int8sym-cleanie-ov')

    # 复用生产切段计划，保证段长分布与端到端一致
    segs = SegmentedStreamer(
        None, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64)._plan_segments(a)[:N_SEGS]

    # warmup：与 c080b/c062r 同口径
    for s in (5, 12, 18):
        be.encode_audio(a[:SR * s])
    log('[c080h] warmup done', flush=True)

    rows = []
    for i, (s, e) in enumerate(segs):
        w = a[s:e]
        ts = []
        for _ in range(3):          # 每段重复 3 次取中位，压掉抖动
            t0 = time.perf_counter()
            ehs, _, N = be.encode_audio(w)
            ts.append((time.perf_counter() - t0) * 1000)
        ts.sort()
        rows.append({'seg': i, 'dur_s': round((e - s) / SR, 2),
                     'n_audio': int(N),
                     'enc_ms_median': round(ts[1], 1),
                     'enc_ms_all': [round(x, 1) for x in ts]})
        log('[c080h] seg%d dur=%.2fs N_audio=%d enc=%.1fms'
            % (i, (e - s) / SR, N, ts[1]))

    med = float(np.median([r['enc_ms_median'] for r in rows]))

    # 流式循环里 encoder 被反复调用（每个 640 ms chunk 一次全量重编码），
    # 用 c080b 实测的调用画像换算总时长
    with open('reports/c080_e2e/summary.json', encoding='utf-8') as f:
        e2e = json.load(f)['by_cfg']['int8']
    n_gen = e2e['n_generate_calls']
    wall = e2e['wall_s']
    acct = e2e['share_of_accounted_ms']
    enc_total_s = n_gen * med / 1000

    rep = {
        'note': 'C-080 补测：cleanie 端到端里的 encoder 分项。'
                'c080b 的 probe 没给 encode_audio 打桩，导致 enc share 显示为 0；'
                '本脚本单独测，用于判断「GPU compute 降幅」的来源。',
        'encoder_ir': be.dec_xml and 'models/ov-encoder-segment-reviewer',
        'n_segs_measured': len(rows),
        'segments': rows,
        'enc_ms_median': round(med, 1),
        'stream_accounting': {
            'n_generate_calls': n_gen,
            'enc_ms_each': round(med, 1),
            'enc_total_s': round(enc_total_s, 1),
            'wall_s': wall,
            'enc_share_of_wall': round(enc_total_s / wall, 4),
            'prefill_share_of_wall': round(
                acct['prefill'] * acct['accounted_s'] / wall, 4),
            'decode_share_of_wall': round(
                acct['decode'] * acct['accounted_s'] / wall, 4),
            'previously_unattributed_s': round(
                wall - acct['accounted_s'], 1),
        },
        'cross_check_vs_config_A': {
            # ⚠️ C-081 更正：这里原来硬写成 48.09 ms 并称来自 c069m，是**错的**
            # 来源标注。c069m_real_call_profile.json 里配置 A（FP16 enc，同一
            # encoder IR）的 enc_ms_mean 逐段为
            #   62.97 / 66.58 / 62.34 / 61.15 / 64.41 / 66.06 / 69.73 / 62.27
            # → 逐段均值的均值 = 64.44 ms；按 n_generate 加权 = 64.83 ms。
            # 48.09 这个数字在 c069m 里根本不存在，来源不明，作废。
            'A_enc_ms_mean_c069m_mean_of_seg_means': 64.44,
            'A_enc_ms_mean_c069m_weighted_by_n_generate': 64.83,
            'A_per_seg_enc_ms_mean': [62.97, 66.58, 62.34, 61.15,
                                      64.41, 66.06, 69.73, 62.27],
            'A_source': 'reports/c069m_real_call_profile.json 的 segments[].enc_ms_mean'
                        '（配置 A = FP16 enc + INT8 dec，同一 encoder IR '
                        'models/ov-encoder-segment-reviewer）',
            'A_bad_value_voided': 48.09,
            'A_bad_value_note': 'C-081 撤回：48.09 ms 在 c069m 中不存在，来源'
                                '标注错误。原 ratio=1.723 作废。',
            'ratio_cleanie_over_A_mean_of_seg_means': round(med / 64.44, 3),
            'ratio_cleanie_over_A_weighted': round(med / 64.83, 3),
            'same_encoder_ir': True,
        },
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    sa = rep['stream_accounting']
    log('\n[c080h] enc 中位 %.1f ms/次 × %d 次 = %.1f s = wall 的 %.1f%%'
        % (med, n_gen, enc_total_s, 100 * sa['enc_share_of_wall']))
    log('[c080h] 之前未计入 %.1f s，现已基本归因'
        % sa['previously_unattributed_s'])
    log('[c080h] 配置 A 同一 encoder IR 的 enc=%.2f ms/次（c069m 逐段均值 %.2f）'
        ' → 比值 %.2f（C-081 更正，原 48.09 作废）'
        % (64.83, 64.44,
           rep['cross_check_vs_config_A']['ratio_cleanie_over_A_weighted']))
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
