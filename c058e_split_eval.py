"""c058e_split_eval.py — C-058⑤: 按 12 分钟切分校准集 / 评测集

🔴 **本脚本的 WER / CI 已于 C-060 正式退役，只保留「12 分钟切分」这一个用途。**

retirement 原因（2026-10-16，C-059#4 + C-060#2 确认）：
  本脚本用 `align_base_to()` 把 MiniMax 碎片**按时间戳分桶**到 OV 的 VAD 段，
  再逐段算 WER。实测该路径在本项目**根本不成立**：
    - OV 的 VAD 段边界与 MiniMax 句子边界系统性错位，226 段里 180 段（80%）
      的段首词错位 >5 词 → 段内对齐崩塌；
    - 绝对 WER 虚高到 **81%**（真值 ~7.8%）；
    - 对同一对比，方法 A 给「显著变差」，方法 B（全局对齐）给「不显著」，
      **显著性结论相反**。
  → 正式判据一律用 `c058m_bootstrap_crosscheck.py` 里的**方法 B**
    （整段一次全局对齐，错误按假设词位置归段，断言 Σ段错误 == 全局 S+D+I）。
  → 本脚本仅保留 `split_eval()`，供「校准 0–12 分钟 / 评测 ≥12 分钟」的切分使用；
    其 WER / CI 输出**不得引用**。

reviewer 硬性要求（CORRECTIONS.md ⑤）：
  「校准集不得包含评测音频：英文素材只有这一条 61 分钟录音，请用其
    **0–12 分钟的 VAD 段**做校准，所有系统（含 INT8 基线）的 WER
    只在 **≥12 分钟**的部分比较」

所以已跑完的 61 分钟 transcript 必须按段的时间戳重新切：
  - 起点 < 720 s 的段 → 校准区（不可用于评测）
  - 起点 ≥ 720 s 的段 → 评测区（唯一可用于 WER 判据的部分）

本脚本对任意 transcript 做切分，并输出评测区子集；baseline 同样切。
注意：OV 的 VAD 段可能跨过 720 s 边界，这类段应**整体归入评测区**
（含少量 ≤12 min 的音频），因为段的输出无法按段内时间再拆分。

用法：
  .venv python c058e_split_eval.py <transcript.txt> [更多...]
  .venv python c058e_split_eval.py --pair <baseline> <cand1> <cand2> ...
"""
import os
import sys
import re
import json
from difflib import SequenceMatcher

SPLIT_SEC = 12 * 60      # 12 分钟
REF = 'reports/c026_minimax_transcript.txt'


def norm(w):
    return re.sub(r"[^\w']", '', w.lower()).replace("'", '')


def parse(path):
    segs = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line)
        if m:
            ws = [n for w in m.group(3).split() if (n := norm(w))]
            segs.append((float(m.group(1)), float(m.group(2)), ws, line))
    return segs


def split_eval(segs, split=SPLIT_SEC):
    """返回 (校准区段, 评测区段)。跨边界的段整体归入评测区。"""
    calib = [s for s in segs if s[1] <= split]
    ev = [s for s in segs if s[1] > split]
    return calib, ev


def align_base_to(base_segs, target):
    """把 baseline 碎片按时间戳聚合到 target 的段边界。"""
    buckets = [[] for _ in target]
    for st, en, ws, _ in base_segs:
        mid = (st + en) / 2
        for i, (ts, te, _, _) in enumerate(target):
            if ts <= mid <= te:
                buckets[i].extend(ws)
                break
    return buckets


def edit_counts(ref, hyp):
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
    return S, D, I


def wer_on(base_buckets, cand_segs):
    S = D = I = N = 0
    for rw, cs in zip(base_buckets, cand_segs):
        hyp = cs[2]
        N += len(rw)
        s, d, i = edit_counts(rw, hyp)
        S += s
        D += d
        I += i
    return {'N_ref': N, 'S': S, 'D': D, 'I': I,
            'wer': round(100.0 * (S + D + I) / N, 3) if N else 0.0}


def bootstrap_ci(per_a, per_b, iters=5000, seed=1234):
    """per_* = [(N, err)]，统计量 = WER(参照) − WER(候选)。

    与 c058b_paired_bootstrap.py 保持同一约定：
      Δ > 0 → 候选 WER 低于参照（候选更好）
      Δ < 0 → 候选 WER 高于参照（候选更差）
    """
    import random
    rng = random.Random(seed)
    n = len(per_a)

    def w(per, idx):
        N = sum(per[i][0] for i in idx)
        E = sum(sum(per[i][1]) for i in idx)
        return 100.0 * E / N if N else 0.0

    allidx = list(range(n))
    wa, wb = w(per_a, allidx), w(per_b, allidx)
    d = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        d.append(w(per_b, idx) - w(per_a, idx))
    d.sort()
    lo = d[min(int(len(d) * 0.025), len(d) - 1)]
    hi = d[min(int(len(d) * 0.975), len(d) - 1)]
    return {'wer_cand': round(wa, 3), 'wer_ref': round(wb, 3),
            'delta_pp': round(wb - wa, 3),
            'ci95': [round(lo, 3), round(hi, 3)],
            'significant': not (lo <= 0 <= hi)}


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    iters = 5000
    if '--iters' in args:
        i = args.index('--iters')
        iters = int(args[i + 1])
        del args[i:i + 2]
    pair_mode = '--pair' in args
    if pair_mode:
        args.remove('--pair')

    base_raw = parse(REF)
    out = {'split_sec': SPLIT_SEC, 'iters': iters, 'candidates': []}

    if pair_mode and len(args) >= 2:
        # args[0] = 参照（INT8 基线），args[1:] = 候选
        ref_segs = parse(args[0])
        ref_cal, ref_ev = split_eval(ref_segs)
        base_ev = align_base_to(base_raw, ref_ev)
        print(f'参照: {os.path.basename(args[0])}')
        print(f'  全量 {len(ref_segs)} 段 → 校准区 {len(ref_cal)} 段 / '
              f'评测区 {len(ref_ev)} 段（> {SPLIT_SEC}s）')
        rref = wer_on(base_ev, ref_ev)
        print(f'  评测区 WER = {rref["wer"]}%  (N_ref={rref["N_ref"]}, '
              f'S={rref["S"]} D={rref["D"]} I={rref["I"]})')
        per_ref = [(len(base_ev[i]), edit_counts(base_ev[i], ref_ev[i][2]))
                   for i in range(len(ref_ev))]
        out['ref'] = {'file': args[0], **rref}
        out['paired_vs_ref'] = []
        for p in args[1:]:
            ev = split_eval(parse(p))[1]
            bb = align_base_to(base_raw, ev)
            r = wer_on(bb, ev)
            per_c = [(len(bb[i]), edit_counts(bb[i], ev[i][2]))
                     for i in range(len(ev))]
            ci = bootstrap_ci(per_c, per_ref, iters)
            print(f'\n{os.path.basename(p)}')
            print(f'  评测区 {len(ev)} 段  WER={r["wer"]}%  '
                  f'(S={r["S"]} D={r["D"]} I={r["I"]})')
            print(f'  ΔWER = {ci["delta_pp"]:+.2f} pp  '
                  f'95% CI [{ci["ci95"][0]:+.2f}, {ci["ci95"][1]:+.2f}]  '
                  f'{"显著" if ci["significant"] else "不显著"}')
            out['candidates'].append({'file': p, **r, **ci})
            out['paired_vs_ref'].append({'cand': p, **ci})
    else:
        print(f'单文件评测区 WER（>{SPLIT_SEC}s）')
        for p in args:
            segs = parse(p)
            cal, ev = split_eval(segs)
            bb = align_base_to(base_raw, ev)
            r = wer_on(bb, ev)
            print(f'\n{os.path.basename(p)}')
            print(f'  {len(segs)} 段 → 校准区 {len(cal)} / 评测区 {len(ev)}')
            print(f'  评测区 WER={r["wer"]}%  N_ref={r["N_ref"]}  '
                  f'S={r["S"]} D={r["D"]} I={r["I"]}')
            out['candidates'].append({'file': p, 'n_segs_total': len(segs),
                                      'n_segs_calib': len(cal), **r})

    op = 'reports/c058_eval_ge12min.json'
    os.makedirs('reports', exist_ok=True)
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {op}')


if __name__ == '__main__':
    main()
