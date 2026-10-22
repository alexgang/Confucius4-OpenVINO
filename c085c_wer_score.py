"""c085c_wer_score.py — C-085#2：全 NPU 转写的端到端 WER + 配对 bootstrap CI。

**精度判据的唯一口径**（硬性约束）：真实音频 prompt 的端到端 WER + 配对 bootstrap CI。
短 dummy prompt 的贪心token 分叉**不作为**量化精度判据。

复用 `c080g_score.py` 的同一套实现（`c058m_bootstrap_crosscheck.method_b`全局
对齐 + 按 owner 归因 + `boot` 配对重采样），不重写，避免再次踩 method A 时间桶
对齐的坑（C-059#4 已证伪：绝对WER 虚高到 81%）。

参照系统 = ABBA 配置 A 的同一切片转写（`reports/c062_abba/transcripts/transcript_A_rep0.txt`），
candidate = 全 NPU（enc@NPU + dec@NPU，cleanie INT8）。

同时把 cleanie（enc@集显 + dec@NPU）的同一切片结果一并列出，
以便判断「encoder 换到 NPU 是否损精度」。

用法：`.venv python c085c_wer_score.py [--iters 5000]`
输出：reports/c085_wer.json
"""
import json
import os
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

START, END = 12 * 60, 27 * 60
BASE_JSON = 'reports/c026_minimax_raw.json'
REF_A = 'reports/c062_abba/transcripts/transcript_A_rep0.txt'
CANDIDATES = {
    # name: transcript 路径
    'all_npu': 'reports/c085_e2e/transcript_all_npu.txt',
    'cleanie_igpu_enc_npu_dec': 'reports/c080_e2e/transcript_int8_npu.txt',
}
OUT = 'reports/c085_wer.json'
A_KNOWN_FULL_61 = 7.798     # 全长 61 min 交付真值（交叉校验用）


def log(*a):
    print(*a, flush=True)


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

    # baseline 切片词表（与 c080g 完全相同的构造）
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
    words = sorted([(t, w) for t, w in words if START <= t <= END])
    base_words = [w for _, w in words]
    log('[c085c] baseline 切片内词数 %d（12–27 min）' % len(base_words))

    a_segs = segs_from_transcript(REF_A)
    per_a, tot_a, n_a = method_b(base_words, a_segs)
    A_WER = 100.0 * tot_a / n_a
    log('[c085c] 配置 A WER = %.3f%%（n_ref=%d, segs=%d）'
        % (A_WER, n_a, len(a_segs)))

    rep = {'note': 'C-085 全 NPU（enc@NPU + dec@NPU）端到端 WER + 配对 bootstrap CI。'
                   '口径 = method_b 全局对齐归因（method A 时间桶对齐已被 C-059#4 证伪）。'
                   '只此一项为精度判据，不用 dummy prompt 的 token 分叉。',
           'baseline': BASE_JSON, 'reference_system': REF_A,
           'slice_sec': [START, END], 'iters': iters,
           'method': 'method_b (global SequenceMatcher alignment + per-owner attribution)',
           'A': {'wer_pct': round(A_WER, 3), 'ref_words': n_a,
                 'n_segs': len(a_segs), 'S+D+I': tot_a},
           'A_known_wer_full61min': A_KNOWN_FULL_61,
           'do_not_mix': '本切片 A=%.3f%%；全长 61 min 口径为 %.3f%%。引用时必须带切片范围。'
                         % (A_WER, A_KNOWN_FULL_61),
           'by_cfg': {}}

    for name, path in CANDIDATES.items():
        if not os.path.exists(path):
            rep['by_cfg'][name] = {'status': 'no transcript', 'path': path}
            log('[c085c] %s: 无转写（%s）' % (name, path))
            continue
        c_segs = segs_from_transcript(path)
        c_trip = [(s, e, t) for s, e, t in c_segs]
        per_c, tot_c, n_c = method_b(base_words, c_trip)
        k = min(len(per_c), len(per_a))
        b = boot(per_a[:k], per_c[:k], iters=iters)
        wer_c = 100.0 * tot_c / n_c
        hyp = [w for _, _, t in c_segs for w in norm(t)]
        c4 = Counter(tuple(hyp[i:i + 4]) for i in range(len(hyp) - 3))
        d = {'path': path,
             'wer_pct': round(wer_c, 3),
             'wer_A_pct': round(A_WER, 3),
             'delta_pp': round(wer_c - A_WER, 3),
             'ci95': b['ci95'],
             'significant_vs_A': b['significant'],
             'ref_words': n_c, 'n_segs': len(c_segs), 'paired_n_segs': k,
             'words': len(hyp),
             'n4_repeat': sum(v - 1 for v in c4.values() if v > 1),
             'significant_regression': bool(b['ci95'][0] > 0)}
        rep['by_cfg'][name] = d
        log('[c085c] %-24s WER=%.3f%%  Δ=%+.3f pp  CI=[%.3f, %.3f]  '
            'seg=%d words=%d n4repeat=%d'
            % (name, wer_c, d['delta_pp'], b['ci95'][0], b['ci95'][1],
               len(c_segs), len(hyp), d['n4_repeat']))
        log('[c085c]   显著退化（下界>0）：%s' % d['significant_regression'])

    # RTF 从 summary.json 带过来
    try:
        with open('reports/c085_e2e/summary.json', encoding='utf-8') as f:
            s = json.load(f)
        rep['rtf'] = {'all_npu': s['overall_rtf'],
                      'cleanie_igpu_enc_npu_dec': 0.8525,
                      'config_A': 0.578}
        rep['rtf_slice_sec'] = [START, END]
        rep['rtf_note'] = 'RTF 与 WER 同为 12–27 min 切片（C-083 统一口径）。'
    except FileNotFoundError:
        rep['rtf'] = {'status': 'summary.json 缺失'}

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
