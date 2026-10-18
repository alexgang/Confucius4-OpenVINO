"""c058p_rerun_tail.py — C-060#1 重跑的尾延迟确认

背景
----
第一次 `int4lmhead_dec`（10:43–11:18）没开 GPU guard，报出
P50 0.532 / P95 0.778 / max 0.877。P50 比交付配置还低、尾部却明显更高，
形态像间歇性 GPU 争用，reviewer 要求串行带 guard 重跑，验收线 P95 ≤ 0.8。

重跑（`reports/c058_61min_rerun/`）报出
P50 0.495 / P95 0.595 / P99 0.621 / max 0.627 —— 尾部比第一次低得多。

本脚本做三件事：
  1. 重跑 vs 第一次：逐段配对，直接看差多少、是否稳定（争用应是零星尖峰，
     不是全段一致偏移）；
  2. 重跑 vs `c058k` 的 FP16 encoder 同条件运行：同块数配对 bootstrap 算 ΔP95
     与 CI，隔离「段长差异」这个混淆因素；
  3. 给出是否满足 C-060 的 **P95 ≤ 0.8** 验收线。

对照基线的选择
--------------
`reports/c048_61min_adaptive/summary.json`（INT8 交付）**没有逐段 RTF**
（只有 P50/P95/max 汇总），无法做逐段配对。可用的逐段基线是
`reports/c058_tail/summary_seg_rtf.json` 里的 `enc_fp16`——
它是 c058k 用**同一个 INT8 decoder + 同一份 FP16 encoder** 在同一天带 guard 跑的，
与本次重跑构成严格可比的对照（同 encoder、同 decoder 家族、同 guard 条件）。

用法：.venv python c058p_rerun_tail.py
输出：reports/c058_rerun_tail.json
"""
import json
import os
import random
from collections import defaultdict

RERUN = 'reports/c058_61min_rerun/summary_int4lmhead_dec_rerun.json'
FIRST = 'reports/c058_61min/summary_int4lmhead_dec.json'
FP16_SEG = 'reports/c058_tail/summary_seg_rtf.json'
OUT = 'reports/c058_rerun_tail.json'

ACCEPT_P95 = 0.8
BOXES = [20, 24, 28, 31]
N_BOOT = 5000
SEED = 1234


def pct(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    k = min(int(len(s) * q), len(s) - 1)
    return s[k]


def stats(rtfs):
    return {
        'p50': pct(rtfs, 0.50),
        'p90': pct(rtfs, 0.90),
        'p95': pct(rtfs, 0.95),
        'p99': pct(rtfs, 0.99),
        'max': max(rtfs) if rtfs else 0.0,
    }


def paired_bootstrap_p95(a, b, iters=N_BOOT, seed=SEED):
    """统计量 = P95(b) − P95(a)，正 = b 更慢。"""
    rng = random.Random(seed)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    allidx = list(range(n))
    obs = pct(b, 0.95) - pct(a, 0.95)
    d = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        d.append(pct([b[i] for i in idx], 0.95) - pct([a[i] for i in idx], 0.95))
    d.sort()
    lo, hi = d[int(len(d) * 0.025)], d[int(len(d) * 0.975)]
    return {
        'delta_p95': round(obs, 4),
        'ci95': [round(lo, 4), round(hi, 4)],
        'significant': not (lo <= 0 <= hi),
        'n': n,
    }


def by_chunks(pairs):
    """按 n_chunks 分箱，箱内配对，返回每箱 P50/P95 与 P95 差。"""
    box = defaultdict(lambda: {'a': [], 'b': []})
    for pa, pb in pairs:
        n = pa.get('n_chunks')
        box[n]['a'].append(pa['rtf'])
        box[n]['b'].append(pb['rtf'])
    out = {}
    for n in sorted(box):
        a, b = box[n]['a'], box[n]['b']
        out[n] = {
            'n_segs': len(a),
            'p50_a': round(pct(a, 0.5), 3),
            'p95_a': round(pct(a, 0.95), 3),
            'p50_b': round(pct(b, 0.5), 3),
            'p95_b': round(pct(b, 0.95), 3),
            'delta_p95': round(pct(b, 0.95) - pct(a, 0.95), 4),
        }
    return out


def load_results(path):
    """兼容两种 summary_seg_rtf.json 格式。

    旧格式（C-058k 原版）：顶层是 list，元素带 `tag`。
    新格式（C-061#3 起）：顶层是 dict，`{'order':..., 'results':[...]}`
    （因为要记录 order / warmup_sweep / ABBA 各轮等信息）。
    """
    d = json.load(open(path, encoding='utf-8'))
    if isinstance(d, list):
        return d
    return d.get('results', d.get('data', []))


def collect_all_runs():
    """C-061#3：汇总所有已有 61 分钟运行的 P50/P95/max，供报告引用。

    重点是**范围**而不是单次最好值 —— 同一交付配置在不同运行里 P95 相差可达 0.13，
    只报最好一次会给出「有余量」的错觉。
    """
    import os
    runs = []

    def add(tag, path, picker=None, note=''):
        if not os.path.exists(path):
            return
        try:
            d = json.load(open(path, encoding='utf-8'))
        except Exception:
            return
        item = picker(d) if picker else d
        segs = item.get('seg_rtfs')
        if segs:
            rtfs = [s['rtf'] for s in segs if s.get('rtf', 0) > 0]
            runs.append({
                'tag': tag, 'source': path, 'has_seg_rtfs': True,
                'p50': round(pct(rtfs, 0.5), 4),
                'p95': round(pct(rtfs, 0.95), 4),
                'max': round(max(rtfs), 4),
                'n_segs': len(rtfs), 'note': note,
            })
        else:
            # 只存了汇总分位数（如 c048），照抄其自带字段
            runs.append({
                'tag': tag, 'source': path, 'has_seg_rtfs': False,
                'p50': item.get('seg_rtf_p50'),
                'p95': item.get('seg_rtf_p95'),
                'max': item.get('seg_rtf_max'),
                'n_segs': item.get('n_segs'), 'note': note,
            })

    def pick(tag):
        def f(d):
            return next(x for x in d if x.get('tag') == tag)
        return f

    add('c048 FP16enc+INT8dec (INT8 交付)',
        'reports/c048_61min_adaptive/summary.json',
        lambda d: d[0], '仅汇总分位数，无逐段 RTF')
    add('c057f FP16enc+INT8dec',
        'reports/c057_61min_encoder/summary.json',
        lambda d: d[0] if isinstance(d, list) else d, '')
    add('c058k FP16enc+INT8dec (带 guard, fresh)',
        FP16_SEG, pick('enc_fp16'), 'C-058k 重跑，同 FP16 enc + INT8 dec')
    add('c058k INT4enc+INT8dec (带 guard)',
        FP16_SEG, pick('enc_int4'), '')
    add('c058④ FP16enc+INT4全量dec (无 guard)',
        FIRST, None, 'C-060#1 判定尾部不可信')
    add('c060 FP16enc+INT4全量dec (带 guard 重跑)',
        RERUN, None, '本次重跑')

    return runs


def main():
    rerun = json.load(open(RERUN, encoding='utf-8'))
    first = json.load(open(FIRST, encoding='utf-8'))
    fp16 = next(it for it in load_results(FP16_SEG)
                 if it.get('tag') == 'enc_fp16')

    r_seg = rerun['seg_rtfs']
    f_seg = first['seg_rtfs']
    p_seg = fp16['seg_rtfs']

    res = {
        'note': 'delta = P95(B) − P95(A)；正 = B 更慢。'
                '对照基线 = c058k 的 enc_fp16（同 FP16 encoder + 同 INT8 decoder 家族，'
                '同 guard 条件）。c048 INT8 交付基线无逐段 RTF，不能做逐段配对。',
        'accept_line': f'C-060 验收：P95 ≤ {ACCEPT_P95}',
        'rerun': {
            'tag': rerun['tag'],
            'wall_s': rerun['wall_s'],
            'overall_rtf': rerun['overall_rtf'],
            'total_words': rerun['total_words'],
            'stats': stats([s['rtf'] for s in r_seg]),
            'n_gt_accept': sum(1 for s in r_seg if s['rtf'] > ACCEPT_P95),
            'n_gt_075': sum(1 for s in r_seg if s['rtf'] > 0.75),
        },
        'first_run': {
            'tag': first['tag'],
            'wall_s': first['wall_s'],
            'overall_rtf': first['overall_rtf'],
            'total_words': first['total_words'],
            'stats': stats([s['rtf'] for s in f_seg]),
            'n_gt_accept': sum(1 for s in f_seg if s['rtf'] > ACCEPT_P95),
            'n_gt_075': sum(1 for s in f_seg if s['rtf'] > 0.75),
        },
    }

    # 1) 重跑 vs 第一次：逐段配对
    n = min(len(r_seg), len(f_seg))
    pairs = [(f_seg[i], r_seg[i]) for i in range(n)]
    res['rerun_vs_first'] = {
        'paired': paired_bootstrap_p95(
            [p[0]['rtf'] for p in pairs], [p[1]['rtf'] for p in pairs]),
        'by_chunks': by_chunks(pairs),
        'n_segments_first_slower': sum(
            1 for a, b in pairs if a['rtf'] > b['rtf']),
        'delta_all_segments': {
            'mean': round(sum(b['rtf'] - a['rtf'] for a, b in pairs) / n, 4),
            'min': round(min(b['rtf'] - a['rtf'] for a, b in pairs), 4),
            'max': round(max(b['rtf'] - a['rtf'] for a, b in pairs), 4),
        },
    }

    # 2) 重跑 vs FP16 encoder 同条件基线
    # ⚠️ C-062#2：这里的 paired CI **不可用于**声称「INT4 变快」。
    # 原因同 C-061#2：逐段 RTF 强相关（lag-1 0.77），iid 重采样出的窄 CI 是假的，
    # 且两次运行不在同一时间窗口。P95 本身也是不稳定指标。
    # 「变快」的判据是 P50 与 overall RTF（见 C-062#2 的交替运行实验）。
    n2 = min(len(r_seg), len(p_seg))
    pairs2 = [(p_seg[i], r_seg[i]) for i in range(n2)]
    res['rerun_vs_fp16_enc_samecond'] = {
        'WARNING': 'C-062#2：不可据此下显著性结论。逐段强相关 + 跨运行不可比；'
                    '判据请用 P50 与 overall RTF。',
        'paired': paired_bootstrap_p95(
            [p[0]['rtf'] for p in pairs2], [p[1]['rtf'] for p in pairs2]),
        'by_chunks': by_chunks(pairs2),
        'fp16_stats': stats([s['rtf'] for s in p_seg]),
        'rerun_stats': stats([s['rtf'] for s in r_seg]),
        # 稳健口径：P50 与 overall RTF
        'robust_p50_delta': round(
            pct([s['rtf'] for s in r_seg], 0.5)
            - pct([s['rtf'] for s in p_seg], 0.5), 4),
        'robust_overall_rtf': {
            'fp16_enc_int8_dec': p_seg and next(
                (x.get('overall_rtf') for x in load_results(FP16_SEG)
                 if x.get('tag') == 'enc_fp16'), None),
            'fp16_enc_int4_dec': rerun['overall_rtf'],
        },
    }

    # 3) 验收判定
    # C-062#1：`verdict.pass` 必须同时包含 guard 的 `rtf_valid`。
    # 只有 P95 达标而 GPU 被别人占用，这次 RTF 一样作废。
    p95_r = pct([s['rtf'] for s in r_seg], 0.95)

    guard_path = 'reports/c058_gpu_guard_int4lmhead_rerun.json'
    guard = None
    if os.path.exists(guard_path):
        guard = json.load(open(guard_path, encoding='utf-8'))
    rtf_valid = bool(guard and guard.get('rtf_valid'))

    res['guard'] = guard if guard else {
        'error': f'guard 输出缺失: {guard_path}'}
    res['verdict'] = {
        'p95_rerun': round(p95_r, 4),
        'threshold': ACCEPT_P95,
        'p95_pass': p95_r <= ACCEPT_P95,
        'guard_found': bool(guard),
        'guard_rtf_valid': rtf_valid,
        'guard_start': (guard or {}).get('start_time'),
        'guard_end': (guard or {}).get('end_time'),
        'guard_samples': (guard or {}).get('n_samples'),
        'guard_conflicts': (guard or {}).get('n_conflict_samples_util_gt_5'),
        # 最终有效 = P95 达标 AND guard 干净
        'pass': (p95_r <= ACCEPT_P95) and rtf_valid,
        'margin': round(ACCEPT_P95 - p95_r, 4),
        # C-061#3：单次运行通过验收线 ≠ 这个配置有余量。
        # 同一交付配置 FP16 enc + INT8 dec 在 c048/c057f/c058k 三次运行里
        # P95 分别是 0.657 / 0.638 / 0.771，max 达 0.990。
        'caveat': 'C-061#3：P95 ≤ 0.8 在本机**不是稳健余量**。同一交付配置历史 '
                  'P95 = 0.657 / 0.638 / 0.771、max 达 0.990，单段 RTF 会逼近 1；'
                  '且 VAD 段上限 20 s，RTF≈1 的事件会让该段最终文字延迟约等于段长。',
        # C-062#2：P95 不可用于证明「变快」。
        'speed_caveat': 'C-062#2：不要用 P95 证明「全量 INT4 更快」。P95 不稳定，'
                        '且逐段 RTF 强相关（lag-1 FP16 0.77），iid 重采样出的窄 CI '
                        '是假的。判据请用 **P50 与 overall RTF**，并用交替运行确认。',
    }
    res['all_runs_rtf'] = collect_all_runs()

    json.dump(res, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print(f'\nsaved -> {OUT}')


if __name__ == '__main__':
    main()
