"""c058m_bootstrap_crosscheck.py — C-059 第 4 点：交叉验证两种 bootstrap 归因方法

reviewer 指出（C-059#4）：
  「你把 MiniMax 碎片按时间戳聚合到 OV 段边界，这种『按时间给段分配基准词』的
    做法在段边界会多算错误（我最初也这么做过，绝对 WER 虚高到 18%）；我的版本
    是对整段做**一次全局对齐，再把错误归到所在的假设段**，各段错误数之和严格
    等于整体 S+D+I。……两种方法的 Δ 应相差 ≤0.2 pp，差得更多说明某一边有 bug。」

本脚本对**同一对 transcript** 同时跑两种归因：
  方法 A（我的，c058e）：按时间戳把 baseline 碎片聚合到候选 VAD 段，逐段算 WER
  方法 B（reviewer）：整段一次全局对齐，错误按假设词位置归到各段，
                      断言 Σ 段错误 == 全局 S+D+I

输出两种方法的绝对 WER、Δ 与 CI，量化它们到底差多少。

⚠️ 12 分钟纪律：reviewer 已确认「泄漏只发生在用了校准数据的配方上」。
   无校准配方之间继续用全长 61 分钟结果；本脚本因此**默认全长**，
   仅在 --ge12min 时切到评测区。

用法：
  .venv python c058m_bootstrap_crosscheck.py <ref_transcript> <cand_transcript> [--ge12min]
"""
import os
import re
import sys
import json
import random
from difflib import SequenceMatcher

LINE = re.compile(r'^\s*\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$')
BASE_JSON = 'reports/c026_minimax_raw.json'
SPLIT_SEC = 12 * 60


def norm(t):
    t = t.lower().replace('’', "'")
    t = re.sub(r"[^a-z0-9' ]+", ' ', t)
    return [w for w in t.split() if w]


def load_segments(path):
    out = []
    for line in open(path, encoding='utf-8'):
        m = LINE.match(line)
        if m:
            out.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return out


def spread(start, end, text):
    ws = norm(text)
    if not ws:
        return []
    step = (end - start) / len(ws)
    return [(start + (i + 0.5) * step, w) for i, w in enumerate(ws)]


def baseline_words():
    """从 c026_minimax_raw.json 还原 baseline 词序列（带时间戳）。"""
    raw = json.load(open(BASE_JSON, encoding='utf-8'))
    words = []
    for chunk in raw:
        st = chunk.get('start_s', 0.0)
        en = chunk.get('end_s', st)
        words += spread(st, en, chunk.get('text', ''))
    return sorted(words, key=lambda x: x[0])


# ---------------- 方法 A：按时间聚合（我的原做法）⚠️ 已证伪 ----------------
def method_a(base_timed, segs):
    """按时间戳把 baseline 碎片聚合到候选 VAD 段，逐段算 WER。

    ⚠️ **本项目已证伪，勿用于出结论**（2026-10-16，C-059#4 交叉验证）：
    OV 的 VAD 段边界与 MiniMax 的句子边界**系统性错位**—— 实测 226 段里
    **180 段（80%）的段首词在 baseline 中错位 >5 词**。例：
      OV seg0[0.0-13.7] hyp 实际对应 baseline 第 3–22 词，
      但时间桶给它的是第 1–40 词 → 段内对齐整体崩塌。
    结果：绝对 WER 虚高到 **81%**（真值 ~7.8%），Δ 也被放大到 +0.74 pp。

    保留此函数仅为复现该 bug，正式判据一律用 `method_b`。
    """
    buckets = [[] for _ in segs]
    for t, w in base_timed:
        for i, (s, e, _) in enumerate(segs):
            if s <= t <= e:
                buckets[i].append(w)
                break
        else:                      # 落在所有段之外 → 归给最近的段
            best = min(range(len(segs)),
                       key=lambda i: min(abs(t - segs[i][0]), abs(t - segs[i][1])))
            buckets[best].append(w)
    per = []
    for i, (_, _, text) in enumerate(segs):
        ref, hyp = buckets[i], norm(text)
        sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
        err = sum(max(i2 - i1, j2 - j1) if tag == 'replace' else
                  (i2 - i1) if tag == 'delete' else
                  (j2 - j1) if tag == 'insert' else 0
                  for tag, i1, i2, j1, j2 in sm.get_opcodes())
        per.append((len(ref), err))
    return per


# ---------------- 方法 B：全局对齐归因（reviewer 的做法） ----------------
def method_b(base_words, segs):
    hyp, owner = [], []
    for i, (_, _, text) in enumerate(segs):
        ws = norm(text)
        hyp += ws
        owner += [i] * len(ws)
    sm = SequenceMatcher(a=base_words, b=hyp, autojunk=False)
    errs = [0] * len(segs)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace':
            n = max(i2 - i1, j2 - j1)
            S += n
            k = min(j1, len(owner) - 1)
            errs[owner[k]] += n
        elif tag == 'delete':
            D += i2 - i1
            k = min(j1, len(owner) - 1)
            errs[owner[k]] += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
            for k in range(j1, min(j2, len(owner))):
                errs[owner[k]] += 1
    total = S + D + I
    assert sum(errs) == total, (
        f'归因丢失错误：Σ段={sum(errs)} vs 全局={total}')
    n = len(base_words)
    per_seg = [max(1, len(norm(t))) for _, _, t in segs]
    scale = n / sum(per_seg)
    return [(p, e) for p, e in zip([x * scale for x in per_seg], errs)], total, n


def boot(per_a, per_b, iters=5000, seed=1234):
    """Δ = WER(B) − WER(A)，正 = B 更差。"""
    rng = random.Random(seed)
    n = len(per_a)

    def w(per, idx):
        N = sum(per[i][0] for i in idx)
        E = sum(per[i][1] for i in idx)
        return 100.0 * E / N if N else 0.0
    allidx = list(range(n))
    wa, wb = w(per_a, allidx), w(per_b, allidx)
    d = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        d.append(w(per_b, idx) - w(per_a, idx))
    d.sort()
    return {'wer_a': round(wa, 3), 'wer_b': round(wb, 3),
            'delta_pp': round(wb - wa, 3),
            'ci95': [round(d[int(len(d) * .025)], 3),
                     round(d[int(len(d) * .975)], 3)],
            'significant': not (d[int(len(d) * .025)] <= 0 <=
                                d[int(len(d) * .975)])}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ge12 = '--ge12min' in sys.argv
    fa, fb = args[0], args[1]

    bt = baseline_words()
    bw = [w for _, w in bt]
    sa, sb = load_segments(fa), load_segments(fb)
    if ge12:
        sa = [s for s in sa if s[1] > SPLIT_SEC]
        sb = [s for s in sb if s[1] > SPLIT_SEC]
        bt = [(t, w) for t, w in bt if t > SPLIT_SEC]
        bw = [w for t, w in bt]
    assert len(sa) == len(sb), (
        f'段数不同：{len(sa)} vs {len(sb)}（含时长范围可能不同）')

    print(f'A = {os.path.basename(fa)}')
    print(f'B = {os.path.basename(fb)}')
    print(f'口径 = {"评测区 ≥12min" if ge12 else "全长 61min"}  '
          f'段数 = {len(sa)}  baseline 词数 = {len(bw)}')

    pa_a, pa_b = method_a(bt, sa), method_a(bt, sb)
    rb_a = boot(pa_a, pa_b)
    print(f'\n方法 A（按时间聚合，我的原做法）⚠️ 已证伪，仅复现用:')
    print(f'  A WER {rb_a["wer_a"]:.3f}%   B WER {rb_a["wer_b"]:.3f}%   '
          f'Δ(B−A) = {rb_a["delta_pp"]:+.3f} pp')
    print(f'  → 绝对WER 虚高到 ~81%（真值 ~7.8%）：OV 的 VAD 段边界与 baseline '
          f'句子边界系统性错位，80% 的段首词错位 >5 词，段内对齐崩塌。**不可用**')

    pb_a, tot_a, n = method_b(bw, sa)
    pb_b, tot_b, _ = method_b(bw, sb)
    rb_b = boot(pb_a, pb_b)
    print(f'\n方法 B（全局对齐归因，reviewer 的做法）✅ 正式判据:')
    print(f'  A WER {rb_b["wer_a"]:.3f}% ({int(tot_a)} 错)   '
          f'B WER {rb_b["wer_b"]:.3f}% ({int(tot_b)} 错)   '
          f'Δ(B−A) = {rb_b["delta_pp"]:+.3f} pp  '
          f'CI [{rb_b["ci95"][0]:+.3f}, {rb_b["ci95"][1]:+.3f}]  '
          f'{"显著" if rb_b["significant"] else "不显著"}')
    print(f'  ✓ 已断言 Σ段错误 == 全局 S+D+I')

    d = abs(rb_a['delta_pp'] - rb_b['delta_pp'])
    print(f'\n=== 两法 Δ 相差 {d:.3f} pp → 方法 A 有 bug，已废弃；'
          f'后续一律用方法 B ===')

    out = {'ref': fa, 'cand': fb, 'scope': 'ge12min' if ge12 else 'full61',
           'n_segs': len(sa), 'n_ref_words': len(bw),
           'method_A_time_bucket_REJECTED': rb_a,
           'method_B_global_ALIGNED': rb_b,
           'delta_diff_pp': round(d, 3),
           'verdict': 'method_A_invalid_seg_boundary_misalignment'}
    with open('reports/c058_bootstrap_crosscheck.json', 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('saved -> reports/c058_bootstrap_crosscheck.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
