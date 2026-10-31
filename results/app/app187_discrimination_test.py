#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app187 判据的**鉴别力实测**（§四「判据 PASS ≠ 判据正确」纪律）。

🔴🔴🔴 **为什么要这个脚本**
--------------------------
`app187` 断言的是「STATUS 里引用的产物**都已入库**」。
⇒ 如果这条判据**恒真**（例如正则写坏、一个路径都没抓到），
   那它就是一道**假闸门** ⇒ 比没有闸门更危险（会让人以为「已闭环」）。

⇒ 必须证明：**造一份「引用了未入库文件」的 STATUS 副本 ⇒ 同一个判据必定 FAIL**，
  而**原** STATUS ⇒ PASS（对照）。
⇒ 而且要证明它**不是靠「抓到更多路径」取胜** ⇒ 注入组必须**精确命中**注入的那几处。

🔴 **做法**（纯离线，不碰生产文件）：
  ① 把 `status/app/STATUS_APP.md` 复制到**临时目录**；
  ② 在**副本**里注入 N 处**已知的「引用未入库产物」**；
  ③ 用**同一个脚本**（`--status` 指向临时副本）跑；
  ④ 断言：注入 N 处 ⇒ **恰好** N 条 MISSING 且 `verdict=FAIL`；
  ⑤ 断言：**原** STATUS ⇒ `verdict=PASS`（对照）。

🔴 **纪律**：纯离线（只读 + 复制文本）⇒ 不占机器锁、不跑推理、不碰 GPU。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(HERE, 'app187_repo_artifact_in_repo_gate.py')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

#: 注入的「引用未入库产物」：每条 = (说明, 引用文本, 该路径必须**确实未入库**)
#: ⚠️ 注入用的路径名带 `__app187_probe_` 前缀 ⇒ 保证**绝不可能**已在库
MUTATIONS = (
    ('① 引用一个从未入库的产物',
     '探针产物 `results/app/__app187_probe_1.json`（应判 MISSING）',
     'results/app/__app187_probe_1.json'),
    ('② 引用另一个从未入库的产物',
     '探针产物 `results/app/__app187_probe_2.json`（应判 MISSING）',
     'results/app/__app187_probe_2.json'),
    ('③ 引用一个从未入库的脚本',
     '探针脚本 `results/app/__app187_probe_3.py`（应判 MISSING）',
     'results/app/__app187_probe_3.py'),
)


def run_gate(status_path):
    """跑一次 app187 闸门，返回解析后的 JSON。"""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'ev.json')
        p = subprocess.run(
            [sys.executable, SCRIPT, '--status', status_path, '--out', out],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if not os.path.isfile(out):
            return {'_rc': p.returncode, '_stdout': p.stdout.decode('utf-8', 'replace'),
                    '_stderr': p.stderr.decode('utf-8', 'replace')}
        with open(out, 'r', encoding='utf-8') as f:
            d = json.load(f)
        d['_rc'] = p.returncode
        return d


def main():
    ap = argparse.ArgumentParser(description='app187 判据鉴别力实测')
    ap.add_argument('--out', default=os.path.join(HERE,
                                                  'app187_discrimination_evidence.json'))
    args = ap.parse_args()

    RESULTS = []

    def rec(name, ok, detail=''):
        RESULTS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})
        print('  %-6s %s%s' % ('PASS' if ok else 'FAIL', name,
                               ('  [%s]' % detail) if detail else ''))
        return bool(ok)

    print('== 对照组（干净基线：去掉引用未入库产物的行）==')
    # 🔴 对照组**不能**直接用仓库现状当基线 ——
    #   仓库现状本身可能正带着真实缺陷（这正是本轮 §118 抓到的），
    #   那样对照组就会 FAIL ⇒ 判据就**分不出「有缺陷」与「没缺陷」**。
    # ⇒ 做法：先跑一次闸门拿到 missing/dirty 清单 ⇒ **剔除**引用它们的行
    #   ⇒ 得到一份「已知干净」的基线 ⇒ 它必须 PASS。
    probe = run_gate(STATUS)
    bad_paths = set(probe.get('missing', [])) | set(probe.get('dirty', []))
    clean_path = os.path.join(tempfile.mkdtemp(prefix='app187_clean_'), 'STATUS_clean.md')
    with open(STATUS, 'r', encoding='utf-8', errors='replace') as f:
        raw_lines = f.readlines()
    kept = [ln for ln in raw_lines
            if not any(p in ln for p in bad_paths)]
    with open(clean_path, 'w', encoding='utf-8') as f:
        f.writelines(kept)

    base = run_gate(clean_path)
    rec('T0 干净基线跑闸门成功', '_rc' in base and 'verdict' in base,
        'rc=%r' % base.get('_rc'))
    rec('T1 干净基线判定为 PASS', base.get('verdict') == 'PASS',
        'verdict=%r（剔除 %d 处引用）' % (base.get('verdict'), len(bad_paths)))
    n_base_missing = base.get('n_missing', -1)
    n_base_dirty = base.get('n_dirty', -1)
    print('  干净基线：候选 %s / MISSING %s / DIRTY %s'
          % (base.get('n_candidates'), n_base_missing, n_base_dirty))
    rec('T1b 干净基线**零** MISSING / 零 DIRTY',
        n_base_missing == 0 and n_base_dirty == 0,
        'missing=%s dirty=%s' % (n_base_missing, n_base_dirty))

    print('\n== 注入组（在**干净基线**上注入 %d 处「引用未入库产物」）==' % len(MUTATIONS))
    tmpdir = tempfile.mkdtemp(prefix='app187_disc_')
    try:
        injected_path = os.path.join(tmpdir, 'STATUS_APP_injected.md')
        # 🔴 注入的底稿必须是**干净基线**，不是原 STATUS ——
        #   否则注入组里会**混入原 STATUS 自带的真实缺陷**
        #   ⇒ MISSING 数不再「恰好 +N」⇒ 判据的精确性无法度量。
        with open(clean_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()

        # 在**正文末尾**追加注入段（不改动任何既有内容）
        inject_lines = ['', '', '<!-- app187 鉴别力注入段（仅存在于本临时副本） -->', '']
        for _desc, snippet, _path in MUTATIONS:
            inject_lines.append('- %s' % snippet)
        with open(injected_path, 'w', encoding='utf-8') as f:
            f.write(text + '\n'.join(inject_lines) + '\n')

        inj = run_gate(injected_path)
        rec('T2 注入组跑闸门成功', 'verdict' in inj, 'rc=%r' % inj.get('_rc'))
        rec('T3 注入组判定为 FAIL', inj.get('verdict') == 'FAIL',
            'verdict=%r' % inj.get('verdict'))

        missing = inj.get('missing', [])
        rec('T4 注入的 %d 个路径**全部**被判 MISSING' % len(MUTATIONS),
            all(p in missing for _d, _s, p in MUTATIONS),
            'missing=%r' % missing)

        # 🔴 精确性：MISSING 数**恰好**比对照多 N（不是「多抓了几个」取胜）
        rec('T5 MISSING 数**恰好** +%d（精确命中，非多抓取胜）' % len(MUTATIONS),
            (inj.get('n_missing', -1) - n_base_missing) == len(MUTATIONS),
            'base=%s inj=%s' % (n_base_missing, inj.get('n_missing')))

        # 🔴 判据对「已入库路径」不能误伤：对照里的 ok 集合应仍在注入组里
        base_ok = set(base.get('ok', []))
        inj_ok = set(inj.get('ok', []))
        rec('T6 已入库路径未被误判为 MISSING（无假阳性）',
            base_ok.issubset(inj_ok),
            'base_ok=%d inj_ok=%d' % (len(base_ok), len(inj_ok)))

        # 🔴 注入组不得引入额外 MISSING（除注入的 N 个）
        extra = [p for p in missing if p not in [m[2] for m in MUTATIONS]
                 and p not in base.get('missing', [])]
        rec('T7 注入组**无额外** MISSING（只命中注入的那几处）',
            not extra, 'extra=%r' % extra)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    n_pass = sum(1 for r in RESULTS if r['ok'])
    n_fail = len(RESULTS) - n_pass
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    print('\n==========================================================================')
    print('PASS=%d / FAIL=%d / verdict=%s' % (n_pass, n_fail, verdict))
    print('==========================================================================')

    out = {
        'script': os.path.basename(__file__),
        'purpose': '证明 app187 判据**非恒真**（能识破「STATUS 引用了未入库产物」）',
        'n_pass': n_pass,
        'n_fail': n_fail,
        'verdict': verdict,
        'checks': RESULTS,
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据：%s' % args.out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
