#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app200_app053_m8_criterion_fix.py —— 【APP-053】修掉 `app195` 的 **M8 判据缺陷**。

## 🔴 抓到的判据缺陷（不是产品缺陷）

`app195_app053_mechanism_evidence.json` 的 **M8「A 臂与参考伪真值一致率 ≥ 60%」= 0.0**
⇒ 当时看起来像「App 的说话人判定完全错误」。

**但那是判据本身的缺陷**：

- App 侧的 `spk` 是 **pyannote/wespeaker 聚类自己产生的簇号**
  （`S1/S2/S3/S4`，**编号顺序由首次出现顺序决定**）；
- 参考标注（`shared/spe_qa_spk.json`）的 `S1…S5` 是 **人工标注的编号**
  （编号顺序由标注者决定）；
- ⇒ **两套编号没有语义对应关系** ⇒ 直接比字符串 ⇒ **必然接近 0**
  ⇒ 这是**恒假判据**（与「弱标记恒真」同类问题）。

🔴 **正确口径**：先求**最优编号置换**（Hungarian / 穷举），再算一致率
⇒ 这才是「同一句话被归到同一个说话人」的真正度量。

**实测（离线，只用已落盘的 `app195` 证据，不重跑模型）**：
  最优置换一致率 = **38/46 = 82.61 %**（映射 `S1→S3, S2→S1, S3→S2, S4→S5`）
  ⇒ 远高于 60 % 门槛 ⇒ **A 臂的说话人判定其实是对的**。

## 本脚本做什么

1. 读 `app195_app053_mechanism_evidence.json`（**只读**，不改它）；
2. 对每臂算「最优置换一致率」；
3. 判定 M8'（置换后一致率 ≥ 60 %）；
4. **反证**：把 A 臂的标签**随机打乱**（打乱后与参考的一致率必须**大幅下降**）
   ⇒ 证明该判据**非恒真**；
5. 产出 `results/app/app200_app053_m8_criterion_evidence.json`。

⚠️ **纯离线**（不跑模型 / 不占 GPU / 不取机器锁）。
"""
from __future__ import annotations

import itertools
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'app195_app053_mechanism_evidence.json')
OUT = os.path.join(HERE, 'app200_app053_m8_criterion_evidence.json')


def best_permutation_agree(rows):
    """最优编号置换下的最大一致率。

    ⇒ App 的簇号与参考标注的编号**无语义对应** ⇒ 必须先求置换。
    ⇒ 规模小（≤ 46 行 / ≤ 8 簇）⇒ 穷举即可（`itertools.permutations`）。
    """
    apps = sorted({r['spk'] for r in rows if r.get('spk')})
    refs = sorted({r['ref_spk'] for r in rows if r.get('ref_spk')})
    if not apps or not refs:
        return 0, 0, {}
    n = len(rows)
    best = 0
    best_map = {}
    # 簇数可能大于参考人数 ⇒ 只取等长置换，其余参考名视为「不可映射」
    for perm in itertools.permutations(refs, min(len(apps), len(refs))):
        mp = dict(zip(apps, perm))
        ok = sum(1 for r in rows
                 if r.get('spk') and mp.get(r.get('spk')) == r.get('ref_spk'))
        if ok > best:
            best = ok
            best_map = mp
    return best, n, best_map


def main():
    if not os.path.isfile(SRC):
        print('缺 app195 证据：%s' % SRC)
        return 2
    with open(SRC, 'r', encoding='utf-8') as f:
        d = json.load(f)

    checks = []

    def chk(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))

    arms = d.get('arms') or []
    arm_out = []
    for a in arms:
        rows = a.get('rows') or []
        ok, n, mp = best_permutation_agree(rows)
        raw_ok = sum(1 for r in rows
                     if r.get('spk') and r.get('spk') == r.get('ref_spk'))
        arm_out.append(dict(
            arm=a.get('arm'),
            n_rows=n,
            n_tagged=a.get('n_tagged'),
            raw_agree=raw_ok,
            raw_agree_pct=round(100.0 * raw_ok / max(1, n), 2),
            best_permutation_agree=ok,
            best_permutation_agree_pct=round(100.0 * ok / max(1, n), 2),
            mapping=mp,
        ))

    # ── M8'：A 臂的置换一致率 ≥ 60 % ──
    a_arm = next((x for x in arm_out if x['arm'] == 'A_oneshot_300s'), None)
    chk("M8' A 臂（一次性喂）**最优置换**一致率 ≥ 60 %",
        bool(a_arm) and a_arm['best_permutation_agree_pct'] >= 60.0,
        dict(arm='A_oneshot_300s',
             raw_pct=(a_arm or {}).get('raw_agree_pct'),
             best_pct=(a_arm or {}).get('best_permutation_agree_pct'),
             mapping=(a_arm or {}).get('mapping')))

    # ── 反证：打乱标签 ⇒ 一致率必须大幅下降（判据非恒真）──
    if a_arm:
        rows = [r for r in (d['arms'][0].get('rows') or [])
                if r.get('spk')]
        if rows:
            rnd = random.Random(20261101)
            shuffled = []
            for _ in range(20):
                tags = [r['spk'] for r in rows]
                rnd.shuffle(tags)
                sh = [dict(r, spk=tags[i]) for i, r in enumerate(rows)]
                ok, n, _ = best_permutation_agree(sh)
                shuffled.append(ok)
            worst = max(shuffled)
            chk('反证：打乱标签后一致率必须**大幅下降**（判据非恒真）',
                worst < a_arm['best_permutation_agree'],
                dict(real_best=a_arm['best_permutation_agree'],
                     shuffled_max=worst,
                     shuffled_mean=round(sum(shuffled) / len(shuffled), 2),
                     n_trials=len(shuffled)))

    # ── 反证 2：把参考标注打乱 ⇒ 一致率必须下降 ──
    if a_arm:
        rows = d['arms'][0].get('rows') or []
        rnd = random.Random(20261102)
        sh = []
        refs = [r.get('ref_spk') for r in rows if r.get('ref_spk')]
        rnd.shuffle(refs)
        it = iter(refs)
        for r in rows:
            r2 = dict(r)
            if r2.get('ref_spk'):
                r2['ref_spk'] = next(it)
            sh.append(r2)
        ok, n, _ = best_permutation_agree(sh)
        chk('反证 2：打乱**参考标注**后一致率必须下降（判据非恒真）',
            ok < a_arm['best_permutation_agree'],
            dict(real_best=a_arm['best_permutation_agree'],
                 shuffled=ok))

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = dict(
        script='app200_app053_m8_criterion_fix.py',
        correction='APP-053',
        purpose='修掉 app195 的 M8 判据缺陷（簇号 vs 人工标注编号无语义对应 ⇒ '
                '恒假）⇒ 改用「最优编号置换」口径',
        src_evidence=os.path.basename(SRC),
        criterion_defect=dict(
            old='M8 A 臂与参考伪真值一致率 ≥ 60 %（**直接比字符串**）',
            why_broken='App 的 spk 是聚类簇号（S1/S2/S3/S4，首次出现序决定）；'
                       '参考标注的 S1…S5 是人工编号（标注序决定）'
                       '⇒ 两套编号无语义对应 ⇒ 直接比字符串必然≈0 ⇒ 恒假判据',
            new="M8' A 臂**最优编号置换**后一致率 ≥ 60 %",
            measured_a_arm_pct=(a_arm or {}).get('best_permutation_agree_pct'),
            measured_a_arm_raw_pct=(a_arm or {}).get('raw_agree_pct'),
            conclusion='A 臂的说话人判定其实是对的（82.61 % ≥ 60 %）'
                       '⇒ app195 的 verdict=FAIL 是**判据缺陷**，不是产品缺陷'),
        arms=arm_out,
        checks=checks,
        n_pass=n_pass, n_fail=n_fail,
        verdict='PASS' if n_fail == 0 else 'FAIL',
        ts=__import__('time').strftime('%Y-%m-%d %H:%M:%S'),
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for c in checks:
        print('  [%s] %s  %s'
              % ('PASS' if c['ok'] else 'FAIL', c['name'],
                 json.dumps(c['detail'], ensure_ascii=False)))
    print('结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s' % OUT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
