"""c080g_score.py — C-080#3 的 WER 判据（method B：全局对齐归因）。

## 为什么不能用时间桶对齐（这是本项目已证伪的坑）

第一版我用了 `c058b_paired_bootstrap.align_to_segments`（按时间戳把 MiniMax
碎片聚合到候选段），结果 **WER(cleanie)=614%、WER(A)=612%** —— 配置 A 自己的
WER 也是 612%，而它的真值是 **7.798%**。这种量级的数字说明对齐整体崩塌，
不是模型差。

`c058m_bootstrap_crosscheck.method_a` 的文档已经把原因写清楚了（2026-10-16
C-059#4 交叉验证）：

    OV 的 VAD 段边界与 MiniMax 的句子边界系统性错位 —— 226 段里 180 段（80%）
    的段首词在 baseline 中错位 >5 词。例：OV seg0[0.0-13.7] 的 hyp 实际对应
    baseline 第 3–22 词，但时间桶给它的是第 1–40 词 → 段内对齐崩塌。
    结果：绝对 WER 虚高到 81%（真值 ~7.8%），Δ 也被放大。

**结论：正式判据一律用 `method_b`（全局对齐 + 按 owner 归因）。**
本脚本直接复用 `c058m_bootstrap_crosscheck` 的实现，不重写，避免再次踩坑。

## 口径

1. 参考词表 = MiniMax（`c026_minimax_raw.json`，带时间戳的原始分块）
2. 参照系统 = ABBA 配置 A（交付基线）
3. 候选 = cleanie @NPU
4. 统计量 = WER(A) − WER(cleanie)，**正值 = cleanie 更差**
5. 配对 bootstrap 5000 次，按「段」重采样（method_b 的 per_seg 归因）

用法：`.venv python c080g_score.py [--iters 5000]`
"""
import json
import os
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

OUT_DIR = 'reports/c080_e2e'
REF_A = 'reports/c062_abba/transcripts/transcript_A_rep0.txt'
BASE_JSON = 'reports/c026_minimax_raw.json'
OUT = 'reports/c080g_wer.json'

# ABBA 配置 A 的交付基线真值（C-060/C-062 已复核，用于交叉校验本脚本算得对不对）
A_KNOWN_WER = 7.798


def log(*a):
    print(*a, flush=True)


def segs_from_transcript(path):
    """转写 → [(start, end, text)]，按 c058b 的口径解析（词表交给 method_b）。"""
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

    from c058m_bootstrap_crosscheck import (baseline_words, method_b, boot,
                                           norm)
    from difflib import SequenceMatcher

    # ── 切片坐标（12–27 min）对应的 baseline 词 ──────────────────
    # baseline 是整段坐标；c026_minimax_raw.json 的 chunk 带 start_s/end_s。
    START, END = 12 * 60, 27 * 60
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
    log('[c080g] baseline 切片内词数 %d（12–27 min）' % len(base_words))

    a_segs = segs_from_transcript(REF_A)
    rep = {'note': 'C-080 WER 判据（method B 全局对齐归因；'
                   'method A 时间桶对齐是本项目已证伪的坑，见 c058m）。',
           'baseline': BASE_JSON, 'reference_system': REF_A,
           'slice_sec': [START, END],
           'A_known_wer_for_crosscheck': A_KNOWN_WER,
           'iters': iters, 'by_cfg': {}}

    per_a = None
    for cfg in ('int8', 'int4'):
        p = f'{OUT_DIR}/transcript_{cfg}_npu.txt'
        if not os.path.exists(p):
            rep['by_cfg'][cfg] = {'status': 'no transcript'}
            continue
        c_segs = segs_from_transcript(p)
        # method_b 期望 (start, end, text) 三元组
        c_trip = [(s, e, t) for s, e, t in c_segs]
        per_c, tot_c, n_c = method_b(base_words, c_trip)
        if per_a is None:
            per_a, tot_a, n_a = method_b(base_words, a_segs)
            rep['A'] = {'wer_pct': round(100.0 * tot_a / n_a, 3),
                        'ref_words': n_a, 'n_segs': len(a_segs),
                        'S+D+I': tot_a}
            log('[c080g] 配置 A WER = %.3f%%（已知交付真值 %.3f%%）'
                % (100.0 * tot_a / n_a, A_KNOWN_WER))
        if len(per_c) != len(per_a):
            log('[c080g] !! 段数不同 cleanie=%d A=%d，按最小段数配对'
                % (len(per_c), len(per_a)))
        k = min(len(per_c), len(per_a))
        b = boot(per_a[:k], per_c[:k], iters=iters)
        wer_c = 100.0 * tot_c / n_c
        d = {'wer_pct': round(wer_c, 3),
             'wer_A_pct': rep['A']['wer_pct'],
             'delta_pp': round(wer_c - rep['A']['wer_pct'], 3),
             'ci95': b['ci95'],
             'significant_vs_A': b['significant'],
             'ref_words': n_c, 'n_segs': len(c_segs),
             'paired_n_segs': k}
        # 4-gram 重复：幻觉/撞墙的粗信号
        hyp = [w for _, _, t in c_segs for w in norm(t)]
        from collections import Counter
        c4 = Counter(tuple(hyp[i:i + 4]) for i in range(len(hyp) - 3))
        d['n4_repeat'] = sum(v - 1 for v in c4.values() if v > 1)
        d['words'] = len(hyp)
        d['stop_loss_ci_lower_gt_0'] = bool(b['ci95'][0] > 0)
        d['stop_loss_rtf_gt_09'] = None      # 由 c080b 的实测 RTF 填
        rep['by_cfg'][cfg] = d
        log('[c080g] %s: WER=%.3f%%  A=%.3f%%  Δ=%+.3f pp  CI=[%.3f, %.3f]  '
            'seg=%d words=%d n4repeat=%d'
            % (cfg, wer_c, rep['A']['wer_pct'], d['delta_pp'],
               b['ci95'][0], b['ci95'][1], len(c_segs), len(hyp),
               d['n4_repeat']))
        log('[c080g]   CI 是否显著（下界>0 = cleanie 显著更差）: %s'
            % d['stop_loss_ci_lower_gt_0'])

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
