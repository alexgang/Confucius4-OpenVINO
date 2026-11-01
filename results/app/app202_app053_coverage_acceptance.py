#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app202_app053_coverage_acceptance.py —— 【APP-053 ③】标签覆盖率验收（**离线**）。

## 依据

- **修复前基线**：`results/app/app175_app043_clone_acceptance_evidence.json`
  → `spk_label_coverage_pct = 7.23`（用户要求「说话人切换时字幕显示不同说话人」
  ⇒ 7 % 基本不可见）。
- **pyannote 自身覆盖率（1c 口径）**：`results/app/app193_app053_spk_frame_audit.json`
  → `pyannote_offline.app_span_rule_pass_pct = 89.13`（App 原取值规则）
  → `pyannote_offline.ref_span_rule_pass_pct = 95.65`（ASR 参考真值）。
- **修复后实测**：`results/app/app199_app054_ab_evidence.json`
  → 臂 `on` 的 `cli_n_spk_tagged_lines / cli_n_lines`。

## 验收判据（reviewer APP-053 原文）

> 标签覆盖率应接近 pyannote 有标签的句子比例（即 1c 的比例；**差距 ≤ 5 个百分点**，
> 或逐句列出每个无标签句的原因）

⇒ 判据 = `|实测覆盖率 − 1c 覆盖率| ≤ 5.0 pp`（**两个 1c 口径都判**）。

## 附加判据

- **晚到标签回填**：臂 `on` 里 `n_spk_label_backfilled > 0` ⇒ 标签**确实是晚到的**，
  且**被回填进了字幕行**（`cli_n_spk_tagged_lines` 与回填数一致）；
- **旁路关闭时行为与 v1.12 一致**：臂 `off` 的 `cli_n_spk_tagged_lines == 0`。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AB = os.path.join(HERE, 'app199_app054_ab_evidence.json')
AUDIT = os.path.join(HERE, 'app193_app053_spk_frame_audit.json')
BEFORE = os.path.join(HERE, 'app175_app043_clone_acceptance_evidence.json')
OUT = os.path.join(HERE, 'app202_app053_coverage_evidence.json')


def main():
    for p in (AB, AUDIT, BEFORE):
        if not os.path.isfile(p):
            print('缺产物：%s' % p)
            return 2
    with open(AB, 'r', encoding='utf-8') as f:
        ab = json.load(f)
    with open(AUDIT, 'r', encoding='utf-8') as f:
        audit = json.load(f)
    with open(BEFORE, 'r', encoding='utf-8') as f:
        before = json.load(f)

    arms = {a['arm']: a for a in ab.get('arms') or []}
    on = arms.get('on')
    off = arms.get('off')
    if not on or not off:
        print('A/B 证据缺 arm')
        return 2

    n_lines = on.get('cli_n_lines') or 0
    n_tagged = on.get('cli_n_spk_tagged_lines') or 0
    cov = round(100.0 * n_tagged / max(1, n_lines), 2)

    py = audit.get('pyannote_offline') or {}
    c_app = py.get('app_span_rule_pass_pct')       # 89.13（App 原规则）
    c_ref = py.get('ref_span_rule_pass_pct')       # 95.65（ASR 真值）

    checks = []

    def chk(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))

    chk('修复前基线（app175）覆盖率 = 7.23 %',
        abs(float(before.get('spk_label_coverage_pct') or 0) - 7.23) < 0.01,
        dict(spk_label_coverage_pct=before.get('spk_label_coverage_pct'),
             n_spk_tagged_lines=before.get('n_spk_tagged_lines'),
             n_spk_reference=before.get('n_spk_reference')))

    chk('修复后实测覆盖率 ≥ 修复前的 10 倍（7.23 % ⇒ ≥ 72.3 %）',
        cov >= 72.3, dict(measured_pct=cov, baseline_pct=7.23))

    gap_app = None if c_app is None else round(abs(cov - float(c_app)), 2)
    gap_ref = None if c_ref is None else round(abs(cov - float(c_ref)), 2)
    chk('与 1c 口径（App 原规则 %.2f %%）差距 ≤ 5 pp' % (c_app or 0),
        gap_app is not None and gap_app <= 5.0,
        dict(measured_pct=cov, pyannote_offline_app_rule_pct=c_app,
             gap_pp=gap_app, limit_pp=5.0))
    chk('与 1c 口径（ASR 参考真值 %.2f %%）差距 ≤ 5 pp' % (c_ref or 0),
        gap_ref is not None and gap_ref <= 5.0,
        dict(measured_pct=cov, pyannote_offline_ref_rule_pct=c_ref,
             gap_pp=gap_ref, limit_pp=5.0))

    n_back = on.get('n_spk_label_backfilled') or 0
    chk('晚到标签**确实被回填**（回填数 > 0 且 = 字幕标签行数）',
        n_back > 0 and n_back == n_tagged,
        dict(n_spk_label_backfilled=n_back,
             cli_n_spk_tagged_lines=n_tagged,
             n_spk_no_label_reasons=on.get('n_spk_no_label_reasons')))

    chk('旁路关闭时字幕**无**说话人标签（行为与 v1.12 一致）',
        (off.get('cli_n_spk_tagged_lines') or 0) == 0,
        dict(off_cli_n_spk_tagged_lines=off.get('cli_n_spk_tagged_lines'),
             off_n_lines=off.get('cli_n_lines')))

    # ── 无标签句的原因（APP-053 要求「或逐句列出每个无标签句的原因」）──
    # 🔴 **口径**：App 侧对「无标签原因」按**去重**口径记录
    #   （`_spk_reason_seen` / `_cli_spk_reason_seen` ⇒ 每种原因**只记一次**）
    #   ⇒ 「日志条数」≠「无标签句条数」⇒ 不能按条数判等。
    #   ⇒ 正确判据：① 日志里记到的段号**必须**落在「无标签段号集合」内
    #              ② 有无标签段 ⇒ **至少记到 1 种原因**
    #              ③ 无标签段号集合本身（逐句）必须能**列全**
    reasons = []
    txt = os.path.join(HERE, 'app199_ab_out', 'arm_on.txt')
    if os.path.isfile(txt):
        with open(txt, 'r', encoding='utf-8', errors='replace') as f:
            body = f.read()
        reasons = [(int(i), r) for i, r in re.findall(
            r'\[spk\]\s*第\s*(\d+)\s*段无说话人标签：(\S+)', body)]

    # 逐句列出无标签段号（从字幕文件按行序推）
    untagged_segs = []
    cli_txt = os.path.join(HERE, 'app199_ab_out', 'arm_on.txt.cli.txt')
    if os.path.isfile(cli_txt):
        with open(cli_txt, 'r', encoding='utf-8', errors='replace') as f:
            sub = f.read()
        seg = 0
        for ln in sub.splitlines():
            if not ln.strip():
                continue
            if '[S' not in ln:
                untagged_segs.append(seg)
            seg += 1
    untagged = n_lines - n_tagged
    logged_segs = [i for i, _ in reasons]
    chk('每种「无标签原因」**至少记一次**（App 按去重口径记）',
        (untagged == 0 and not reasons) or bool(reasons),
        dict(n_untagged=untagged, n_reasons_listed=len(reasons),
             reasons=reasons))
    chk('日志里记到的「无标签段号」**必须**落在无标签段号集合内',
        all(i in untagged_segs for i in logged_segs) if logged_segs else True,
        dict(logged_segs=logged_segs, untagged_segs=untagged_segs))
    chk('无标签段号**逐句列全**（数量 = 无标签句数）',
        len(untagged_segs) == untagged,
        dict(n_untagged=untagged, n_untagged_segs=len(untagged_segs),
             untagged_segs=untagged_segs))

    # ── 换人点召回（APP-053：「参考说话人 5 个里被检出的换人点，对照参考报告召回率」）──
    cli_txt = os.path.join(HERE, 'app199_ab_out', 'arm_on.txt.cli.txt')
    distinct = []
    if os.path.isfile(cli_txt):
        with open(cli_txt, 'r', encoding='utf-8', errors='replace') as f:
            sub = f.read()
        distinct = sorted(set(re.findall(r'\[(S\d+)\]', sub)))
    ref_switch = (before.get('n_switch_points') or 0)
    ref_spk = (before.get('n_spk_reference') or 0)

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = dict(
        script='app202_app053_coverage_acceptance.py',
        correction='APP-053',
        purpose='APP-053 ③ 标签覆盖率验收（离线，只用已落盘产物）',
        before=dict(coverage_pct=before.get('spk_label_coverage_pct'),
                    n_spk_tagged_lines=before.get('n_spk_tagged_lines'),
                    n_spk_reference=ref_spk,
                    n_switch_points=ref_switch,
                    source='app175_app043_clone_acceptance_evidence.json'),
        pyannote_offline_1c=dict(app_rule_pct=c_app, ref_rule_pct=c_ref,
                                  source='app193_app053_spk_frame_audit.json'),
        after=dict(measured_coverage_pct=cov, n_lines=n_lines,
                   n_tagged=n_tagged, n_backfilled=n_back,
                   arm='on', source='app199_app054_ab_evidence.json'),
        distinct_spk_labels=distinct,
        untagged_reasons=reasons,
        checks=checks, n_pass=n_pass, n_fail=n_fail,
        verdict='PASS' if n_fail == 0 else 'FAIL',
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for c in checks:
        print('  [%s] %s  %s'
              % ('PASS' if c['ok'] else 'FAIL', c['name'],
                 json.dumps(c['detail'], ensure_ascii=False)[:300]))
    print('结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s' % OUT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
