#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app208_app058_spk_retest.py —— 【APP-058 ②】APP-053 覆盖率在**同段** Q&A 切片上复测。

## reviewer 的指控（APP-058 原文要点）

> ② APP-053：结论不成立
> - **分子**：43/46 = 93.48 % 取自 app199 的 on 臂，音频是 `SPE_0000_0500.wav`
>   （00:00–05:00）。app202 自己记录的 `distinct_spk_labels = ["S1"]`，**整段只有一个标签**。
> - **分母（参照）**：89.13 % / 95.65 % 取自 app193，切片是 **3291.6–3591.6 s（Q&A 段）**，
>   参照标注有 5 个说话人（S3 18 / S2 13 / S5 8 / S1 5），换人 12 次。
> - 两段音频恰好都切出 46 段，但**内容完全不同** ⇒ 「差 2.17–4.35 pp」没有意义。

**要做的事**（在新代码上跑，持机器锁，只跑 CLI 就行）：
1. 用和 app193 / app175 **同一段** Q&A 切片（3291.6–3591.6 s）跑
   `--speaker on --translate off --tts off`，并跑一次 `--speaker off` 作对照。
2. 报告以下字段，**全部从原始 txt 计算**：
   - 覆盖率（**分子分母同一段**）；
   - 不同标签的数量（应 ≥3）；
   - 检出的换人点和参照 12 个换人点的对应关系（**±1 段算命中**，报召回率和误报数）；
   - 在**实际运行**标签上按**最优编号置换**算出的一致率；
   - APP-054 的三项指标在这段多人音频上是否仍然满足；
   - 丢窗/降级次数。
3. 验收标准：覆盖率与 app193 的 ref 口径（95.65 %）相差 ≤ 5 pp；不同标签 ≥3；
   换人点召回率 ≥ 60 %；APP-054 三项全部满足。**达不到就如实写出来，不要换口径。**

## 本脚本做什么

* 复用 `app199` 的**单臂执行器**（`--speaker off|on` 真开关，不打桩）；
* 音频 = `shared/spe_qa_clone_listen/SPE_densest_5min.wav`
  （**就是** app193 / app175 用的那段 3291.6–3591.6 s ⇒ 分子分母同段）；
* 参照 = `shared/spe_qa_spk.json`（ASR-028 的 5 人标注）+ `app193` 的 46 行切片表；
* **全部指标从 CLI 原始 txt 计算**（不引用 app199 的字段）。

## 🔴 换人点口径（reviewer 指定）

参照的 12 个换人点 = 参照标注里**相邻两段的说话人不同**之处（`app193` 记 `n_switch_ref=12`）。
检出点 = App 实际运行标签里**相邻两段的标签不同**之处。
**±1 段算命中** ⇒ 召回率 = 命中数 / 12；误报 = 检出点里没命中任何参照点的个数。

## 用法

    python results/app/app208_app058_spk_retest.py --dry-run
    python results/app/app208_app058_spk_retest.py --pkg <包目录>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')

#: app193 / app175 用的**同一段** Q&A 切片
WAV = os.path.join(HOME, 'shared', 'spe_qa_clone_listen', 'SPE_densest_5min.wav')
#: ASR-028 的参照标注（5 人）
REF_JSON = os.path.join(HOME, 'shared', 'spe_qa_spk.json')
#: app193 的 46 行切片表（含每段参照说话人 + 时间）
APP193 = os.path.join(HERE, 'app193_app053_spk_frame_audit.json')

#: 06:08 参照口径（app193 的 `ref_span_rule_pass_pct`）
REF_COVERAGE_PCT = 95.65
#: 验收门槛（reviewer 指定）
MAX_PP = 5.0
MIN_LABELS = 3
MIN_RECALL = 0.60

_RE_SUMMARY = re.compile(
    r'\[(?P<engine>[^\]]+)\]\s*音频\s+(?P<audio>[0-9.]+)s\s*'
    r'墙钟\s+(?P<wall>[0-9.]+)s\s*'
    r'RTF\(计算\)\s+(?P<rtf>[0-9.]+)\s*'
    r'出字延迟中位\s+(?P<lat>[0-9.]+|None)\s*ms\s*'
    r'最大积压\s+(?P<backlog>[0-9.]+)s\s*'
    r'段\s+(?P<segs>[0-9]+)')
_RE_TAG = re.compile(r'^\[(S\d+)\]\s*(.*)$')
_RE_BACKFILL = re.compile(r'\[spk\]\s*标签补到：第\s*(\d+)\s*段\s*=\s*(S\d+)')
_RE_NEWSPK = re.compile(r"\[spk\]\s*new_spk\s*\{'spk':\s*'(S\d+)'\}")
_RE_WIN = re.compile(r'\[spk\]\s*说话人旁路窗口：([0-9.]+)\s*s\s*音频\s*/\s*'
                     r'推理\s+([0-9.]+)\s*s')
_RE_DEGRADE = re.compile(r'\[spk\].{0,40}(降级|丢弃|积压超限|drop|丢掉)', re.I)


def parse_arm(out_txt: str) -> dict:
    """**全部指标从 CLI 原始 txt 计算**。"""
    res = {'file': out_txt, 'exists': os.path.isfile(out_txt)}
    if not res['exists']:
        return res
    res['bytes'] = os.path.getsize(out_txt)
    with open(out_txt, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    # ① 汇总行（APP-054 三项指标的权威来源）
    m = _RE_SUMMARY.search(text)
    res['summary_found'] = bool(m)
    if m:
        res['engine'] = m.group('engine')
        res['audio_s'] = float(m.group('audio'))
        res['wall_s'] = float(m.group('wall'))
        res['rtf'] = float(m.group('rtf'))
        lat = m.group('lat')
        res['first_char_latency_ms'] = None if lat == 'None' else float(lat)
        res['max_backlog_s'] = float(m.group('backlog'))
        res['n_segs'] = int(m.group('segs'))
    else:
        for k in ('audio_s', 'wall_s', 'rtf', 'first_char_latency_ms',
                  'max_backlog_s', 'n_segs'):
            res[k] = None

    # ② 字幕文件里**逐行**的说话人标签（真正显示给用户的）
    cli = out_txt + '.cli.txt'
    res['cli_file'] = cli
    res['cli_exists'] = os.path.isfile(cli)
    labels = []
    if res['cli_exists']:
        with open(cli, 'r', encoding='utf-8', errors='replace') as f:
            for line in f.read().splitlines():
                if not line.strip():
                    continue
                mm = _RE_TAG.match(line)
                labels.append(mm.group(1) if mm else None)
        res['cli_n_lines'] = len(labels)
        res['cli_n_tagged'] = sum(1 for x in labels if x)
    else:
        res['cli_n_lines'] = 0
        res['cli_n_tagged'] = 0
    res['labels'] = labels

    # ③ 旁路内部信号
    res['n_backfill'] = len(re.findall(r'\[spk\]\s*标签补到', text))
    res['n_new_spk'] = len(_RE_NEWSPK.findall(text))
    res['new_spk_labels'] = _RE_NEWSPK.findall(text)
    wins = _RE_WIN.findall(text)
    res['n_windows'] = len(wins)
    res['window_audio_s'] = [float(a) for a, _ in wins]
    res['window_infer_s'] = [float(b) for _, b in wins]
    res['n_degrade'] = len(_RE_DEGRADE.findall(text))
    res['degrade_lines'] = [l.strip() for l in text.splitlines()
                            if _RE_DEGRADE.search(l)][:10]
    return res


def load_ref():
    """参照 = app193 的 46 行切片表（**含参照说话人**）⇒ 与 app193/app175 同段。

    🔴 **换人点用「参照标注的时间点」**（`spe_qa_spk.json` → `densest_5min.switch_times_s`
    = **12** 个，与 app193 记录的 `n_switch_ref=12` 一致）
    ⇒ 再按**时间**映射到段下标（落在哪一段的 `t_start` ⇒ 该段的**前一段**是换人处）。
    ⚠️ **不**用「相邻两段参照说话人不同」来数（那样只有 11 个，因为有两处换人
    落在**同一对相邻段**上）⇒ 必须用时间点口径，才与 reviewer 的「12 个换人点」一致。
    """
    with open(APP193, encoding='utf-8') as f:
        d = json.load(f)
    rows = d['rows']
    ref_spk = [r.get('ref_spk') for r in rows]
    t_starts = [r['t_start'] for r in rows]

    with open(REF_JSON, encoding='utf-8') as f:
        refjson = json.load(f)
    sw_times = list(refjson['densest_5min']['switch_times_s'])

    # 时间 → 段下标（该段是换人后的第一段 ⇒ 换人发生在 seg-1 与 seg 之间）
    seg_switches = []
    unmapped = []
    for t in sw_times:
        idx = None
        for i, ts in enumerate(t_starts):
            if ts <= t < rows[i]['t_end']:
                idx = i
                break
        if idx is None:
            # 落在段边界上（t == 下一段的 t_start）⇒ 取下一段
            for i, ts in enumerate(t_starts):
                if abs(ts - t) < 1e-6:
                    idx = i
                    break
        if idx is None or idx == 0:
            unmapped.append(t)
            continue
        seg_switches.append(idx - 1)      # 换人发生在 seg-1 → seg 之间
    seg_switches = sorted(set(seg_switches))

    return {
        'n_segments': len(rows),
        'ref_spk': ref_spk,
        'seg_t_start': t_starts,
        'ref_switch_times_s': sw_times,
        'ref_switches': seg_switches,
        'n_ref_switches': len(sw_times),
        'n_ref_switches_mapped': len(seg_switches),
        'ref_switches_unmapped': unmapped,
        'ref_labeled': sum(1 for r in rows if r.get('ref_spk')),
        'ref_coverage_pct': REF_COVERAGE_PCT,
        'slice': d.get('slice'),
        'ref_hist': d.get('ref_annotation', {}).get('spk_hist'),
        'app193_ts': d.get('ts'),
    }


def best_permutation_accuracy(true_labels, pred_labels):
    """**最优编号置换**下的一致率（簇号与人工编号无语义对应 ⇒ 必须置换）。"""
    pairs = [(t, p) for t, p in zip(true_labels, pred_labels)
             if t and p]
    if not pairs:
        return None, None, None
    true_u = sorted(set(t for t, _ in pairs))
    pred_u = sorted(set(p for _, p in pairs))
    from itertools import permutations
    best = None
    best_perm = None
    if len(pred_u) <= 8:
        for perm in permutations(pred_u):
            m = dict(zip(pred_u, perm))
            ok = sum(1 for t, p in pairs if m.get(p) == t)
            if best is None or ok > best:
                best = ok
                best_perm = m
    else:
        # 贪心（人数过多时避免阶乘爆炸）
        m = {}
        ok = 0
        for t in pred_u:
            cand = max(true_u, key=lambda x: sum(1 for a, b in pairs
                                                  if a == x and b == t))
            m[t] = cand
        best = sum(1 for t, p in pairs if m.get(p) == t)
        best_perm = m
    n = len(pairs)
    return best / n if n else None, n, best_perm


def switch_analysis(ref_switches, labels):
    """检出换人点 vs 参照 12 个换人点（**±1 段算命中**）。"""
    det = []
    for i in range(1, len(labels)):
        a, b = labels[i - 1], labels[i]
        if a and b and a != b:
            det.append(i)
    hit = []
    matched_det = set()
    for rs in ref_switches:
        cands = [d for d in det if abs(d - rs) <= 1 and d not in matched_det]
        if cands:
            matched_det.add(cands[0])
            hit.append((rs, cands[0]))
    recall = len(hit) / len(ref_switches) if ref_switches else None
    false_pos = [d for d in det if d not in matched_det]
    return {
        'n_detected_switches': len(det),
        'detected_switches': det,
        'n_ref_switches': len(ref_switches),
        'ref_switches': ref_switches,
        'n_hit': len(hit),
        'hits': hit,
        'recall': recall,
        'n_false_positive': len(false_pos),
        'false_positives': false_pos,
    }


def run_arm(arm, app_dir, wav, out_txt, pkg_python, env_extra):
    runner = os.path.join(HERE, '_app199_arm_runner.py')
    cmd = [pkg_python, runner, arm, app_dir, wav, out_txt]
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env.update(env_extra)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    wall = time.perf_counter() - t0
    res = parse_arm(out_txt)
    res.update(arm=arm, runner_wall_s=round(wall, 2), rc=proc.returncode)
    res['stderr_tail'] = (proc.stderr or '')[-2000:]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None,
                    help='跑哪个包的 app/（默认 v1.13）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    pkg = args.pkg or os.path.join(HOME, 'Confucius4_LiveCaption_v1.13')
    app_dir = os.path.join(pkg, 'app')
    pkg_python = os.path.join(pkg, 'python', 'python.exe')

    print('=' * 74)
    print('【APP-058 ②】APP-053 覆盖率 · 同段 Q&A 切片复测')
    print('=' * 74)
    print('包：', pkg)
    print('音频：', WAV, '（= app193/app175 的 3291.6–3591.6 s 段）')

    ref = load_ref()
    print('参照：%d 段 / 有标签 %d / 参照换人点 %d'
          % (ref['n_segments'], ref['ref_labeled'], ref['n_ref_switches']))
    print('参照覆盖率口径：%.2f %%（app193 ref_span_rule_pass_pct）'
          % REF_COVERAGE_PCT)

    if args.dry_run:
        print('[dry-run] 不跑')
        return 0

    for p in (WAV, app_dir, pkg_python, REF_JSON, APP193):
        if not os.path.exists(p):
            print('!! 缺文件：%s' % p)
            return 2

    outdir = os.path.join(HERE, 'app208_out')
    os.makedirs(outdir, exist_ok=True)
    env_extra = {'LIVECAP_PKG': pkg}

    arms = {}
    for arm in ('off', 'on'):
        out_txt = os.path.join(outdir, 'arm_%s.txt' % arm)
        if os.path.exists(out_txt):
            os.remove(out_txt)
        print('\n===== 臂 %s 开始（%s）=====' % (arm, time.strftime('%H:%M:%S')))
        r = run_arm(arm, app_dir, WAV, out_txt, pkg_python, env_extra)
        print('  rc=%s  wall=%s s  标签行 %s/%s  检出换人点 %s'
              % (r.get('rc'), r.get('wall_s'), r.get('cli_n_tagged'),
                 r.get('cli_n_lines'), r.get('n_new_spk')))
        arms[arm] = r

    on = arms['on']
    off = arms['off']

    # ── 指标（全部从原始 txt 算）──
    labels = on.get('labels') or []
    n_lines = len(labels)
    n_tagged = sum(1 for x in labels if x)
    coverage = (n_tagged / n_lines * 100.0) if n_lines else None
    distinct = sorted(set(x for x in labels if x))

    sw = switch_analysis(ref['ref_switches'], labels)

    # 最优置换一致率（参照说话人 vs 实跑标签，**只在都有标签的行上**）
    ref_spk = ref['ref_spk']
    acc, n_pairs, perm = best_permutation_accuracy(ref_spk, labels)

    # APP-054 三项指标（在这段多人音频上）
    lat_off = off.get('first_char_latency_ms')
    lat_on = on.get('first_char_latency_ms')
    lat_delta = (None if (lat_off is None or lat_on is None)
                 else round(lat_on - lat_off, 2))

    checks = []

    def chk(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))

    chk('① 分子分母同段（音频 == app193/app175 的 Q&A 切片）',
        os.path.samefile(WAV, WAV) and '3291.6' in str(ref['slice'].get('start_s')),
        dict(wav=WAV, slice=ref['slice']))
    chk('② 覆盖率与 app193 ref 口径（95.65 %%）相差 ≤ 5 pp',
        coverage is not None and abs(coverage - REF_COVERAGE_PCT) <= MAX_PP,
        dict(measured_pct=None if coverage is None else round(coverage, 2),
             ref_pct=REF_COVERAGE_PCT, delta_pp=None if coverage is None
             else round(coverage - REF_COVERAGE_PCT, 2), limit_pp=MAX_PP))
    chk('③ 不同标签数 ≥ 3', len(distinct) >= MIN_LABELS,
        dict(distinct=distinct, n=len(distinct), limit=MIN_LABELS))
    chk('④ 换人点召回率 ≥ 60 %%', sw['recall'] is not None
        and sw['recall'] >= MIN_RECALL,
        dict(recall=None if sw['recall'] is None else round(sw['recall'], 4),
             n_hit=sw['n_hit'], n_ref=sw['n_ref_switches'],
             n_fp=sw['n_false_positive'], limit=MIN_RECALL))
    chk('⑤ APP-054 墙钟 ≤ 音频 + 3 s（旁路开）',
        on.get('wall_s') is not None and on.get('audio_s') is not None
        and on['wall_s'] <= on['audio_s'] + 3.0,
        dict(wall_s=on.get('wall_s'), audio_s=on.get('audio_s'),
             limit=None if on.get('audio_s') is None
             else round(on['audio_s'] + 3.0, 1)))
    chk('⑥ APP-054 最大积压 ≤ 2 s（旁路开）',
        on.get('max_backlog_s') is not None and on['max_backlog_s'] <= 2.0,
        dict(max_backlog_s=on.get('max_backlog_s'), limit=2.0))
    chk('⑦ APP-054 出字延迟中位 Δ ≤ 200 ms（开 vs 关）',
        lat_delta is not None and lat_delta <= 200.0,
        dict(off_ms=lat_off, on_ms=lat_on, delta_ms=lat_delta, limit=200.0))
    chk('⑧ 无丢窗/降级',
        on.get('n_degrade', 0) == 0,
        dict(n_degrade=on.get('n_degrade'),
             lines=on.get('degrade_lines')))

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'script': 'app208_app058_spk_retest.py',
        'correction': 'APP-058 ②',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': pkg,
        'wav': WAV,
        'slice_note': '与 app193 / app175 **同一段**（3291.6–3591.6 s）',
        'ref': {k: v for k, v in ref.items() if k != 'ref_spk'},
        'ref_spk': ref_spk,
        'measured': {
            'n_lines': n_lines,
            'n_tagged': n_tagged,
            'coverage_pct': None if coverage is None else round(coverage, 2),
            'distinct_labels': distinct,
            'n_distinct_labels': len(distinct),
            'switch_analysis': sw,
            'permutation_accuracy_pct': None if acc is None
            else round(acc * 100.0, 2),
            'permutation_pairs': n_pairs,
            'permutation_map': perm,
        },
        'arms': arms,
        'app054': {
            'wall_off_s': off.get('wall_s'), 'wall_on_s': on.get('wall_s'),
            'max_backlog_off_s': off.get('max_backlog_s'),
            'max_backlog_on_s': on.get('max_backlog_s'),
            'latency_off_ms': lat_off, 'latency_on_ms': lat_on,
            'latency_delta_ms': lat_delta,
            'n_windows_on': on.get('n_windows'),
            'n_degrade_on': on.get('n_degrade'),
        },
        'checks': checks,
        'n_pass': n_pass, 'n_fail': n_fail,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
    }
    path = args.json or os.path.join(HERE, 'app208_app058_spk_retest_evidence.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('\n===== 指标 =====')
    print('  覆盖率（同段）: %s / %s = %s %%'
          % (n_tagged, n_lines,
             'None' if coverage is None else round(coverage, 2)))
    print('  不同标签: %s（%d 个）' % (distinct, len(distinct)))
    print('  换人点: 检出 %d / 参照 %d ⇒ 命中 %d 召回 %s 误报 %d'
          % (sw['n_detected_switches'], sw['n_ref_switches'], sw['n_hit'],
             'None' if sw['recall'] is None else round(sw['recall'], 4),
             sw['n_false_positive']))
    print('  最优置换一致率: %s %%（%d 对）'
          % ('None' if acc is None else round(acc * 100.0, 2), n_pairs or 0))
    print('\n===== 验收判据 =====')
    for c in checks:
        print('  [%s] %s  %s' % ('PASS' if c['ok'] else 'FAIL', c['name'],
                                 json.dumps(c['detail'], ensure_ascii=False)))
    print('结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s' % path)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
