"""c086b_wer_score_full.py — C-086#2：**全长 61 min** 全 NPU 转写的端到端 WER
+ 配对bootstrap CI。

## 参照系统（配置 A）为什么换成 c048 而不是 c062_abba

C-085（12–27 min切片）用的参照是 `reports/c062_abba/transcripts/transcript_A_rep0.txt`。
全长口径没有对应的 ABBA 转写，本项目的**全长 61 min 交付真值**来自 C-048 adaptive
（`reports/c048_61min_adaptive/transcript_adaptive.txt`），也就是 C-081t 里用同一份
method_b 代码**精确复现出 7.798%** 的那一份（n_ref=11067, 226 段）。本次沿用它，
好处是结果可以直接和历史交付值对话：

- 配置 A 全长 = **7.798%**（历史真值，c081t 已复现）
- 全 NPU 全长 = 本脚本产出

不要和12–27 min 切片的数混用（C-081 明确要求引用 WER 必带切片范围）：
12–27 min 口径是 A 5.961% / cleanie 6.679% / 全 NPU 6.643%。

## 判据口径（不变）

method_b 全局SequenceMatcher 对齐 + 按 owner 归因；配对 bootstrap 5000 次。
**method A（时间桶对齐）已被 C-059#4 证伪**，绝对 WER 虚高到 81%，禁用。

## 分段配对的坑

全长两侧段数不同（A=226 段，全 NPU 段数由VAD 决定）。`c058m.boot` 假设两侧
per-segment 错误数等长，所以沿用 C-085 的做法取 `k = min(len(per_c), len(per_a))`
做配对重采样。**绝对 WER 不受k 影响**（各自用自己的全量per 段），只有CI 宽度受影响；
k 的具体取值已在输出中记录。

输出：reports/c086_full61/wer_full.json
"""
import json
import os
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

BASE_JSON = 'reports/c026_minimax_raw.json'
REF_A = 'reports/c048_61min_adaptive/transcript_adaptive.txt'
CAND = 'reports/c086_full61/transcript_all_npu_full.txt'
OUT = 'reports/c086_full61/wer_full.json'
A_KNOWN_FULL_61 = 7.798
A_SLICE_12_27 = 5.961


def segs_from_transcript(path):
    import re
    segs = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line)
        if m:
            segs.append((float(m.group(1)), float(m.group(2)), m.group(3)))
        else:
            segs.append((None, None, line))
    return segs


def main():
    iters = 5000
    if '--iters' in sys.argv:
        iters = int(sys.argv[sys.argv.index('--iters') + 1])

    from c058m_bootstrap_crosscheck import baseline_words, method_b, boot, norm
    from collections import Counter

    # 全长 baseline 词表（不加时间过滤）
    raw = json.load(open(BASE_JSON, encoding='utf-8'))
    words = []
    for ch in raw:
        st = ch.get('start_s', 0.0)
        en = ch.get('end_s', st)
        ws = norm(ch.get('text', ''))
        if not ws:
            continue
        step = (en - st) / len(ws)
        words += [(st + (i + .5) * step, w) for i, w in enumerate(ws)]
    words = sorted(words)
    base_words = [w for _, w in words]
    print('[c086b] 全长 baseline 词数 %d' % len(base_words), flush=True)

    a_segs = segs_from_transcript(REF_A)
    per_a, tot_a, n_a = method_b(base_words, a_segs)
    A_WER = 100.0 * tot_a / n_a
    print('[c086b] 配置 A 全长 WER = %.3f%%（n_ref=%d, segs=%d）'
          % (A_WER, n_a, len(a_segs)), flush=True)
    reproduces = abs(A_WER - A_KNOWN_FULL_61) < 0.01
    print('[c086b] 是否精确复现历史真值 7.798%%：%s' % reproduces, flush=True)

    rep = {
        'note': 'C-086 全长 61 min（3671.19 s）全 NPU（enc@NPU + dec@NPU）'
                '端到端 WER + 配对 bootstrap CI。口径 = method_b 全局对齐归因。',
        'scope': 'full61min',
        'baseline': BASE_JSON,
        'reference_system': REF_A,
        'candidate': CAND,
        'iters': iters,
        'method': 'method_b (global SequenceMatcher alignment + per-owner attribution)',
        'A': {'wer_pct': round(A_WER, 3), 'ref_words': n_a,
              'n_segs': len(a_segs), 'S_plus_D_plus_I': tot_a,
              'known_historical_value': A_KNOWN_FULL_61,
              'reproduces_known': bool(reproduces)},
        'do_not_mix': '本报告为全长 61 min 口径（A=%.3f%%）。12–27 min 子切片口径为 '
                      'A %.3f%% / cleanie 6.679%% / 全 NPU 6.643%%，两者不可混用。'
                      % (A_WER, A_SLICE_12_27),
        'by_cfg': {},
    }

    if not os.path.exists(CAND):
        rep['by_cfg']['all_npu'] = {'status': 'no transcript', 'path': CAND}
        print('[c086b] 全 NPU 全长转写缺失：%s' % CAND, flush=True)
    else:
        c_segs = segs_from_transcript(CAND)
        per_c, tot_c, n_c = method_b(base_words, c_segs)
        k = min(len(per_c), len(per_a))
        b = boot(per_a[:k], per_c[:k], iters=iters)
        wer_c = 100.0 * tot_c / n_c
        hyp = [w for _, _, t in c_segs for w in norm(t)]
        c4 = Counter(tuple(hyp[i:i + 4]) for i in range(len(hyp) - 3))
        d = {'path': CAND,
             'wer_pct': round(wer_c, 3),
             'wer_A_pct': round(A_WER, 3),
             'delta_pp': round(wer_c - A_WER, 3),
             'ci95': b['ci95'],
             'significant_vs_A': b['significant'],
             'ref_words': n_c, 'n_segs': len(c_segs), 'paired_n_segs': k,
             'words': len(hyp),
             'n4_repeat': sum(v - 1 for v in c4.values() if v > 1),
             'significant_regression': bool(b['ci95'][0] > 0)}
        rep['by_cfg']['all_npu'] = d
        print('[c086b] all_npu 全长 WER=%.3f%%  Δ=%+.3f pp  CI=[%.3f, %.3f]  '
              'seg=%d words=%d n4repeat=%d'
              % (wer_c, d['delta_pp'], b['ci95'][0], b['ci95'][1],
                 len(c_segs), len(hyp), d['n4_repeat']), flush=True)
        print('[c086b]   显著退化（下界>0）：%s' % d['significant_regression'],
              flush=True)

    try:
        with open('reports/c086_full61/summary.json', encoding='utf-8') as f:
            s = json.load(f)
        rep['rtf'] = {'all_npu_full61': s['overall_rtf'],
                      'wall_s': s['wall_s'], 'audio_sec': s['audio_sec']}
        rep['rtf_scope'] = 'full61min（与 WER 同口径）'
        rep['breakdown_median_ms'] = s['breakdown']
    except FileNotFoundError:
        rep['rtf'] = {'status': 'summary.json 缺失'}

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
