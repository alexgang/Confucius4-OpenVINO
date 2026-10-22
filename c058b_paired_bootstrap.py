"""c058b_paired_bootstrap.py — C-058⑥: 配对 bootstrap 95% CI

reviewer 要求（CORRECTIONS.md ⑥）：所有精度结论附运行次数和配对 bootstrap 95% CI。
口径与 reviewer 的 `~/asr_baseline/scripts/paired_bootstrap.py` 对齐：
  - 按 VAD 段配对重采样（段是流水线的自然决策单元）
  - 每次重采样把同一组段索引同时应用到 baseline 与候选，保持配对
  - 统计量 = 两个系统 WER 之差（pp），报告 2.5/97.5 分位

同时输出 S/D/I 分解与 n-gram 重复，便于判断差异是「多说词」还是「识别错」。

用法：
  .venv python c058b_paired_bootstrap.py <baseline_dir> <cand_dir> [more...]
  .venv python c058b_paired_bootstrap.py --iters 5000 reports/A reports/B
其中 <dir> 内需含 transcript_*.txt（形如 [start-end] text），或直接给 txt 文件。
"""
import os
import re
import sys
import json
import random
from difflib import SequenceMatcher

REF = 'reports/c026_minimax_transcript.txt'


def norm(w):
    return re.sub(r"[^\w']", '', w.lower()).replace("'", '')


def parse(path):
    """读 transcript，返回 [(start, end, [words...])]，按时间戳标注的段组织。

    ⚠️ baseline（MiniMax）与 OV 的分段粒度不同：MiniMax 是 ~0.1 s 碎片，
    OV 是 12–20 s 的 VAD 段。配对前必须用 `align_to_segments` 把碎片
    按时间戳聚合到 OV 的段边界上，否则段数对不上、CI 无意义。
    """
    segs = []
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line)
        if m:
            ws = [n for w in m.group(3).split() if (n := norm(w))]
            if ws:
                segs.append((float(m.group(1)), float(m.group(2)), ws))
        else:
            ws = [n for w in line.split() if (n := norm(w))]
            if ws:
                segs.append((None, None, ws))
    return segs


def align_to_segments(frag_segs, target_segs):
    """把 baseline 的细碎片按时间戳聚合到 target（OV VAD 段）的边界上。

    返回与 target_segs 等长、同顺序的段列表。未被覆盖的 target 段给空词表。
    计数时用 target 段的词数作分母，保证各系统 WER 可比。
    """
    buckets = [[] for _ in target_segs]
    for st, en, ws in frag_segs:
        if st is None:
            continue
        mid = (st + en) / 2
        # 找到覆盖该中点的 target 段
        for i, (ts, te, _) in enumerate(target_segs):
            if ts is None:
                continue
            if ts <= mid <= te:
                buckets[i].extend(ws)
                break
    return [(ts, te, b) for (ts, te, _), b in zip(target_segs, buckets)]


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


def ngram_repeat(ws, n=4):
    from collections import Counter
    c = Counter()
    for i in range(len(ws) - n + 1):
        c[tuple(ws[i:i + n])] += 1
    return sum(v - 1 for v in c.values() if v > 1)


def bootstrap(base, cand, iters=5000, seed=1234):
    """base/cand = [(start,end,words)]。按段索引配对重采样，返回 ΔWER 的分布。"""
    rng = random.Random(seed)
    n = min(len(base), len(cand))
    assert n > 10, f'段数太少: {n}'

    # 预计算每段的 (N_ref, err)
    per_base, per_cand = [], []
    for i in range(n):
        rw = base[i][2]
        per_base.append((len(rw), edit_counts(rw, cand[i][2])))
        per_cand.append((len(rw), edit_counts(rw, base[i][2])))

    def wer_of(per, idx):
        N = sum(per[i][0] for i in idx)
        E = sum(sum(per[i][1]) for i in idx)
        return 100.0 * E / N if N else 0.0

    allidx = list(range(n))
    wb = wer_of(per_base, allidx)
    wc = wer_of(per_cand, allidx)

    deltas = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(wer_of(per_base, idx) - wer_of(per_cand, idx))
    deltas.sort()

    def pct(p):
        return deltas[min(int(len(deltas) * p), len(deltas) - 1)]

    return {
        'wer_baseline': round(wb, 3),
        'wer_candidate': round(wc, 3),
        'delta_pp': round(wb - wc, 3),
        'ci95_lo': round(pct(0.025), 3),
        'ci95_hi': round(pct(0.975), 3),
        'n_segments': n,
        'iters': iters,
        'significant': not (pct(0.025) <= 0 <= pct(0.975)),
    }


def paired_delta(cand, ref, base, iters=5000, seed=1234):
    """候选系统相对参照系统的配对 ΔWER 与 95% CI（reviewer 的核心口径）。

    统计量 = WER(参照) − WER(候选)，**正值表示候选更差**（与 reviewer 口径一致：
    「decoder INT4 比 INT8 差 +1.05 pp」）。
    ⚠️ 参考词表必须是 **baseline**（MiniMax），不是参照系统。
    `base` 已按同一段网格对齐，每段给出该段 baseline 的词表。
    """
    rng = random.Random(seed)
    n = min(len(cand), len(ref), len(base))
    assert n > 10, f'段数太少: {n}'

    per_c, per_r = [], []
    for i in range(n):
        rw = base[i][2]
        per_c.append((len(rw), edit_counts(rw, cand[i][2])))
        per_r.append((len(rw), edit_counts(rw, ref[i][2])))

    def wer_of(per, idx):
        N = sum(per[i][0] for i in idx)
        E = sum(sum(per[i][1]) for i in idx)
        return 100.0 * E / N if N else 0.0

    allidx = list(range(n))
    wc, wr = wer_of(per_c, allidx), wer_of(per_r, allidx)
    deltas = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        # 参照 − 候选：正值 = 候选更差
        deltas.append(wer_of(per_r, idx) - wer_of(per_c, idx))
    deltas.sort()
    lo = deltas[min(int(len(deltas) * 0.025), len(deltas) - 1)]
    hi = deltas[min(int(len(deltas) * 0.975), len(deltas) - 1)]
    return {
        'wer_cand': round(wc, 3), 'wer_ref': round(wr, 3),
        'delta_pp': round(wr - wc, 3),   # 正 = 候选更差
        'ci95_lo': round(lo, 3), 'ci95_hi': round(hi, 3),
        'significant': not (lo <= 0 <= hi),
        'n_segments': n, 'iters': iters,
    }


def full_report(path_str, cand_segs, base_segs):
    ws = [w for _, _, s in cand_segs for w in s]
    ref = [w for _, _, s in base_segs for w in s]
    S, D, I = edit_counts(ref, ws)
    return {
        'file': os.path.basename(path_str),
        'words': len(ws), 'S': S, 'D': D, 'I': I,
        'wer': round(100.0 * (S + D + I) / len(ref), 3),
        'n4_repeat': ngram_repeat(ws, 4),
    }


def main():
    iters = 5000
    args = sys.argv[1:]
    if '--iters' in args:
        i = args.index('--iters')
        iters = int(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        return

    base_path, cand_paths = args[0], args[1:]
    base_raw = parse(base_path)
    print(f'baseline: {base_path}')
    print(f'  {len(base_raw)} 段 / {sum(len(s[2]) for s in base_raw)} 词')

    # 若 baseline 的段粒度远细于候选（MiniMax ~0.1s vs OV 12–20s VAD 段），
    # 用第一个候选的段边界把 baseline 碎片聚合过去，保证配对单位一致。
    grid = None
    if base_raw and base_raw[0][0] is not None:
        avg_base = (base_raw[-1][1] - base_raw[0][0]) / max(len(base_raw), 1)
        first_cand = parse(cand_paths[0])
        if first_cand and first_cand[0][0] is not None:
            avg_cand = ((first_cand[-1][1] - first_cand[0][0])
                        / len(first_cand))
            if avg_base < avg_cand / 4:
                grid = [(s[0], s[1]) for s in first_cand]
                print(f'  ⚠️ baseline 段均长 {avg_base:.2f}s ≪ 候选 {avg_cand:.2f}s'
                      f' → 按候选的 {len(grid)} 个段边界聚合 baseline')
        base_segs = align_to_segments(base_raw,
                                      [(a, b, None) for a, b in grid]) \
            if grid else base_raw
    else:
        base_segs = base_raw

    base_ws = [w for _, _, s in base_segs for w in s]
    print(f'  对齐后 {len(base_segs)} 段 / {len(base_ws)} 词（配对单位）')

    out = {'baseline': base_path, 'iters': iters, 'candidates': []}
    print(f'\n{"candidate":<40}{"WER":>8}{"S":>6}{"D":>6}{"I":>6}{"n4rep":>7}')
    print('-' * 76)
    loaded = {}
    for p in cand_paths:
        cand_segs = parse(p)
        # 候选若有段时间戳，也对齐到同一网格，保证逐段可配对
        if grid and cand_segs and cand_segs[0][0] is not None:
            cand_segs = align_to_segments(
                cand_segs, [(a, b, None) for a, b in grid])
        loaded[p] = cand_segs
        rep = full_report(p, cand_segs, base_segs)
        print(f'{os.path.basename(p)[:39]:<40}{rep["wer"]:>7.2f}%'
              f'{rep["S"]:>6}{rep["D"]:>6}{rep["I"]:>6}{rep["n4_repeat"]:>7}')
        out['candidates'].append({'file': p, **rep,
                                  'abs_wer_ci': bootstrap(base_segs, cand_segs,
                                                          iters)})

    # ── 系统两两配对 ΔWER（reviewer 的核心口径）────────────
    if len(loaded) >= 2:
        keys = list(loaded)
        ref_key = keys[0]
        print(f'\n=== 配对 ΔWER（相对 {os.path.basename(ref_key)}）===')
        print(f'{"candidate":<40}{"ΔWER":>9}{"95% CI":>20}{"显著?":>7}')
        print('-' * 78)
        out['paired_vs_ref'] = []
        for k in keys[1:]:
            d = paired_delta(loaded[k], loaded[ref_key], base_segs, iters)
            ci = f'[{d["ci95_lo"]:+.2f}, {d["ci95_hi"]:+.2f}]'
            print(f'{os.path.basename(k)[:39]:<40}{d["delta_pp"]:>+9.2f}'
                  f'{ci:>20}{"是" if d["significant"] else "否":>7}')
            out['paired_vs_ref'].append({'cand': k, 'ref': ref_key, **d})

        # 全矩阵两两比较
        print(f'\n=== 全矩阵两两配对 ΔWER ===')
        print(f'{"A":<34}{"B":<34}{"Δpp":>8}{"95% CI":>20}{"显著?":>7}')
        print('-' * 104)
        out['paired_matrix'] = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                d = paired_delta(loaded[keys[i]], loaded[keys[j]], base_segs, iters)
                ci = f'[{d["ci95_lo"]:+.2f}, {d["ci95_hi"]:+.2f}]'
                print(f'{os.path.basename(keys[i])[:33]:<34}'
                      f'{os.path.basename(keys[j])[:33]:<34}'
                      f'{d["delta_pp"]:>+8.2f}{ci:>20}'
                      f'{"是" if d["significant"] else "否":>7}')
                out['paired_matrix'].append({'a': keys[i], 'b': keys[j], **d})

    os.makedirs('reports', exist_ok=True)
    op = 'reports/c058_paired_bootstrap.json'
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {op}')


if __name__ == '__main__':
    main()
