r"""c089d_score_wer.py — C-089 步骤 4：给某个配方的转写算 WER + 配对 bootstrap CI

判据完全沿用 c087d 已验证的口径（Reviewer 要求「精度判据只用真实音频 prompt 的
端到端 WER + 配对 bootstrap CI」）：

* baseline 词表 = `c026_minimax_raw.json`，按 500 s 大块线性插值定位词时间，
  取 12–27 min；
* 归因 = **method_b**（全局 SequenceMatcher 对齐 + 按 owner 归因）。
  **method A（时间桶）已被 C-059#4 证伪**：绝对 WER 虚高到 81%，勿用；
* CI = 配对 bootstrap 5000 次（seed 固定 1234），Δ = WER(候选) − WER(INT8 参照)；
* **参照自校验**：先报参照自身的 WER，必须落在期望值 ±0.35 内。

## C-092 / C-095：三道断言（任一不满足 → 报错退出，不出结论）

C-092 原文：
> 「`c089d` 加三道断言，任一不满足就报错退出，不出结论：
>   - 候选段数 == 参照段数（55），并且逐段时间戳一致；
>   - bootstrap 的 CI 宽度 > 0；
>   - 参照自身 WER 复现 6.643%。」

C-095 原文：
> 「修 `c089d`：**全长模式也必须做那三道断言**——段数一致、CI 宽度 > 0、参照复现。」

⚠️ 本脚本**绝不**在退化情形下输出 `ci95: [0, 0]`。C-092/C-095 抓到的正是这个：
段数不匹配时 bootstrap 退化，旧代码跳过计算却用 0 占位，于是
`ci_contains_zero: true` —— R0 那种 `yay`、土耳其语乱码会被**判成「通过」**。

## 时间戳口径

参照与候选的时间戳基准不同，必须先对齐再比：
* **切片参照**（c085）用**切片内相对秒**（0–900）；
* **切片候选**（c089c 落盘）加回了 `SLICE_LO=720`，是**绝对秒**（720–1620）。
  → 逐段比较前统���减 `SLICE_LO`。
* **全长参照**（c048）与**全长候选**都用绝对秒，直接比。

用法：
    python c089d_score_wer.py transcript_R0_npu_1227.txt --recipe R0
    python c089d_score_wer.py transcript_R4_npu_full.txt --recipe R4 --full
"""
import argparse
import json
import os
import re
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

START, END = 720.0, 1620.0          # 12–27 分钟（切片口径）
FULL_START, FULL_END = 0.0, 3671.1893125   # 61 min 全长
SLICE_LO = 720.0                     # 候选转写已加回的偏移
# 切片参照 = INT8 全 NPU（c085，md5 8682554d…）；全长参照 = c048 adaptive
REF = 'reports/c085_e2e/transcript_all_npu.txt'
REF_MD5_PREFIX = '8682554d'
REF_EXPECT_WER = 6.643
REF_FULL = 'reports/c048_61min_adaptive/transcript_adaptive.txt'
REF_FULL_EXPECT_WER = 7.798
# 逐段时间戳容差（秒）。参照的边界来自同一套 VAD，抖动在一帧（0.64 s）内。
TS_TOL_S = 0.70
OUT_DIR = 'reports/c089_int4'


def segs(path):
    """解析 `[t0-t1] text` 行。**丢弃空文本段**。

    ⚠️ 必须丢弃，不能只是计数。c048 的全长参照末行是
    `[3670.6-3671.2] `（尾音，无词）；而 c089c 的 `write_transcript`
    本来就跳过空段。若把参照的空尾段算进去，候选恒定少一段，
    断言会以「段数不一致」误报 —— 这正是 C-095 抓到的那个假象的另一半。
    空段对 WER 贡献 0 词，归因时也无内容，归一化后无影响。
    """
    out = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line)
        if m:
            if not m.group(3).strip():      # 空文本段（尾音）→ 丢弃
                continue
            out.append((float(m.group(1)), float(m.group(2)), m.group(3)))
        else:
            out.append((None, None, line))
    return out


def md5(path):
    import hashlib
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def _norm_bounds(ss, shift):
    """把一段转写的时间戳归一到「切片内相对秒」基准。"""
    return [(None if a is None else a - shift,
             None if b is None else b - shift) for a, b, _ in ss]


def check_alignment(ref_ss, cand_ss, cand_shift, tag):
    """C-092#2 第一道断言：段数一致 + 逐段时间戳一致。返回 (ok, 详情)。"""
    problems = []
    if len(ref_ss) != len(cand_ss):
        problems.append(f'段数不一致：参照 {len(ref_ss)} 段 / 候选 '
                        f'{len(cand_ss)} 段（差 {len(cand_ss)-len(ref_ss):+d}）')
    cb = _norm_bounds(cand_ss, cand_shift)
    n_cmp = min(len(ref_ss), len(cb))
    bad = []
    for i in range(n_cmp):
        ra, rb, _ = ref_ss[i]
        ca, cbnd = cb[i]
        if None in (ra, rb, ca, cbnd):
            continue                      # 无时间戳行（C-092#1 抓的正是这种）
        if abs(ra - ca) > TS_TOL_S or abs(rb - cbnd) > TS_TOL_S:
            bad.append((i, (ra, rb), (ca, cbnd)))
    if bad:
        problems.append(f'逐段时间戳不一致：{len(bad)}/{n_cmp} 段超出 '
                        f'{TS_TOL_S} s 容差，前 3 例 '
                        + '; '.join(f'#{i} 参照({a:.2f},{b:.2f}) vs '
                                    f'候选({c:.2f},{d:.2f})'
                                    for i, (a, b), (c, d) in bad[:3]))
    if any(a is None for a, _, _ in cand_ss):
        problems.append('候选转写里有的行没有 [t0-t1] 时间戳 —— 先查 c089c 的 '
                        'write_transcript 格式，不要直接评分')
    return (not problems), problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('transcript')
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--iters', type=int, default=5000)
    ap.add_argument('--full', action='store_true',
                    help='61 min 全长口径（参照换成 c048 adaptive）')
    ap.add_argument('--no-bootstrap', action='store_true',
                    help='只报绝对 WER（仅调试用，报告里必须标注）')
    a = ap.parse_args()

    from c058m_bootstrap_crosscheck import (baseline_words, method_b, boot,
                                            norm)

    base_all = baseline_words()
    # ⚠️ 必须按**时间顺序**取词，不能 sorted()！c087d 的写法是
    # `ws = sorted([(t,x) for ...]); base = [x for _,x in ws]`，
    # 排序键是**时间**，取出后仍保持时间序。我若再对词本身 sorted()，
    # 词会被按字母重排，SequenceMatcher 完全对不上 —— 实测参照自身 WER
    # 会虚高到 191.7%（真值 6.643%）。这是 method_b 的硬前提。
    lo, hi = (FULL_START, FULL_END) if a.full else (START, END)
    ref_path = REF_FULL if a.full else REF
    ref_md5_expect = REF_MD5_PREFIX if not a.full else None
    ref_expect_wer = REF_FULL_EXPECT_WER if a.full else REF_EXPECT_WER
    ref_n_expect = None if a.full else 55
    cand_shift = 0.0 if a.full else SLICE_LO
    timed = sorted([(t, w) for t, w in base_all if lo <= t <= hi])
    base = [w for _, w in timed]
    print('[c089d] baseline %s 词数 %d' % ('全长' if a.full else '12–27min',
                                            len(base)), flush=True)

    ref_segs = segs(ref_path)
    per_r, tot_r, n_r = method_b(base, ref_segs)
    ref_wer = 100.0 * tot_r / n_r
    ref_md5 = md5(ref_path)
    print('[c089d] 参照 %s WER = %.3f%%（n_ref=%d, segs=%d, md5=%s）'
          % (os.path.basename(ref_path), ref_wer, n_r, len(ref_segs),
             ref_md5[:8]), flush=True)

    # ── 三道断言（C-092#2 / C-095#1）────────────────────────────────
    asserts = []
    # ① 参照自身 WER 复现
    d_ref = abs(ref_wer - ref_expect_wer)
    asserts.append(('参照 WER 复现', d_ref < 0.35,
                    f'{ref_wer:.3f}% vs 期望 {ref_expect_wer}%（|Δ|={d_ref:.3f}）'
                    + (f'，md5 前缀 {ref_md5[:8]} 期望 {ref_md5_expect}'
                       if ref_md5_expect else '')))
    if ref_n_expect is not None:
        asserts.append(('参照段数', len(ref_segs) == ref_n_expect,
                        f'{len(ref_segs)} 段，期望 {ref_n_expect}'))

    ok_ref = all(v for _, v, _ in asserts)
    print('[c089d] 参照自校验：%s' % ('通过' if ok_ref else '不通过'),
          flush=True)

    cand = segs(a.transcript)
    cand_md5 = md5(a.transcript)
    print('[c089d] 候选 %s: %d 段, md5=%s' % (a.recipe, len(cand),
                                              cand_md5[:8]), flush=True)

    # ② 候选与参照的段结构对齐（切片模式下候选已加回 SLICE_LO）
    align_ok, align_problems = check_alignment(ref_segs, cand, cand_shift,
                                               'full' if a.full else '1227')
    asserts.append(('段结构对齐', align_ok,
                    '；'.join(align_problems) if align_problems else
                    f'{len(cand)} 段逐段时间戳全部在 {TS_TOL_S} s 内'))

    all_ok = ok_ref and align_ok
    for name, val, detail in asserts:
        print('  [%s] %-10s %s' % ('OK ' if val else 'FAIL', name, detail),
              flush=True)

    if not all_ok:
        print('\n✗ 断言未通过 —— 按 C-092 要求**不出结论**。'
              '\n  段数/时间戳不匹配时 bootstrap 会退化，'
              '\n  旧脚本此时输出 ci95 [0,0] + ci_contains_zero=true，'
              '\n  正是 C-092/C-095 抓到的「把乱码判成通过」。',
              file=sys.stderr, flush=True)
        json.dump({'recipe': a.recipe, 'device': a.device,
                   'transcript': a.transcript, 'transcript_md5': cand_md5,
                   'mode': 'full61' if a.full else 'slice_12_27',
                   'slice_sec': [lo, hi],
                   'wer_pct': None, 'ci95': None, 'delta_pp': None,
                   'aborted': True,
                   'abort_reason': 'assertions_failed',
                   'assertions': [{'name': n, 'ok': bool(v), 'detail': d}
                                  for n, v, d in asserts],
                   'n_cand_segs': len(cand),
                   'n_ref_segs': len(ref_segs),
                   'reference': {'path': ref_path, 'md5': ref_md5,
                                 'expected_wer': ref_expect_wer,
                                 'wer_pct': round(ref_wer, 3)}},
                  open(os.path.join(OUT_DIR,
                       f'{a.recipe}_{a.device.lower()}'
                       f'{"_full" if a.full else "_1227"}_wer.json'),
                       'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        return 3

    per_c, tot_c, n_c = method_b(base, cand)
    wer = 100.0 * tot_c / n_c
    delta = wer - ref_wer

    boot_res = None
    if a.no_bootstrap:
        ci = None
        significant = None
        print('[c089d] ⚠️ --no-bootstrap：不出 CI', file=sys.stderr)
    else:
        boot_res = boot(per_r, per_c, iters=a.iters)
        ci = boot_res['ci95']
        significant = boot_res['significant']
        # ③ CI 宽度 > 0（C-092#2）
        width = ci[1] - ci[0]
        if width <= 0:
            print('\n✗ CI 宽度 = 0 —— bootstrap 已退化（段数/词数不匹配或全同）。'
                  '\n  按 C-092 要求**不出结论**。', file=sys.stderr, flush=True)
            return 4
        asserts.append(('CI 宽度 > 0', True, f'{width:.4f} pp'))

    print('\n' + '=' * 72)
    if ci:
        print('%-8s %8s %9s %22s  %s'
              % ('配方', 'WER%', 'Δ pp', 'CI95', '判定'))
        print('%-8s %8.3f %+9.3f  [%+.3f, %+.3f]  —'
              % ('INT8参照', ref_wer, 0.0, 0.0, 0.0))
        print('%-8s %8.3f %+9.3f  [%+.3f, %+.3f]  %s'
              % (a.recipe, wer, delta, ci[0], ci[1],
                 '**显著变差**' if significant else '与 INT8 无显著差异'))
    else:
        print('%-8s %8.3f %+9.3f  %22s  %s'
              % ('配方', 'WER%', 'Δ pp', 'CI95', '判定'))
        print('%-8s %8.3f %+9.3f  %22s  —' % ('INT8参照', ref_wer, 0.0, ''))
        print('%-8s %8.3f %+9.3f  %22s  %s'
              % (a.recipe, wer, delta, 'n/a', '无 CI（--no-bootstrap）'))
    print('=' * 72, flush=True)

    rep = {
        'recipe': a.recipe,
        'device': a.device,
        'transcript': a.transcript,
        'transcript_md5': cand_md5,
        'wer_pct': round(wer, 3),
        'ref_wer_pct': round(ref_wer, 3),
        'delta_pp': round(delta, 3),
        'ci95': [round(x, 3) for x in ci] if ci else None,
        'boot_full': boot_res,
        'ci_contains_zero': (not significant) if ci else None,
        'significantly_worse': significant,
        'n_ref_words': n_r,
        'n_cand_words': n_c,
        'n_cand_segs': len(cand),
        'n_ref_segs': len(ref_segs),
        'bootstrap_iters': a.iters,
        'assertions': [{'name': n, 'ok': bool(v), 'detail': d}
                       for n, v, d in asserts],
        'reference': {'path': ref_path, 'md5': ref_md5,
                      'expected_md5_prefix': ref_md5_expect,
                      'expected_wer': ref_expect_wer,
                      'wer_pct': round(ref_wer, 3),
                      'selfcheck_ok': bool(ok_ref)},
        'baseline_words': len(base),
        'slice_sec': [lo, hi],
        'candidate_ts_shift': cand_shift,
        'mode': 'full61' if a.full else 'slice_12_27',
    }
    suffix = 'full' if a.full else '1227'
    out = os.path.join(OUT_DIR, f'{a.recipe}_{a.device.lower()}_{suffix}_wer.json')
    json.dump(rep, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('saved ->', out)

    # C-094 判据：CI 含 0（不显著）且 RTF < 0.778 才算通过。
    # 统计功效提示：12–27 分钟只有 55 段，1–2 pp 的差会被 CI 吞掉（C-095）。
    verdict = '显著变差' if significant else 'CI 含 0（需再确认统计功效）'
    print(f'\n[c089d] 判定：{verdict}')
    if not a.full and not significant:
        print('[c089d] ⚠️ C-095：12–27 分钟只有 55 段，统计功效不足，'
              'CI 含 0 **不能**当作通过；候选配方必须再跑 61 min 全长复核。',
              file=sys.stderr, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
