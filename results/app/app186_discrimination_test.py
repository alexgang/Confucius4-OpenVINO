#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app186 判据的**鉴别力实测**（§四「判据 PASS ≠ 判据正确」纪律）。

🔴🔴 **为什么要这个脚本**
----------------------
APP-051② 要求「验收通过后写 ACCEPTED.json」⇒ 「通过」这个结论一旦判错，
就会把**没验收过的包**发给客户 ⇒ 代价极高。

⇒ 光跑出 `verdict=PASS` **不构成证据**：必须证明
   **「往证据里注入已知缺陷 ⇒ 同一个判据必定 FAIL」**
   ⇒ 即判据**非恒真**、且**确实覆盖**了被注入的那几处。

🔴 **做法**（不碰任何生产证据）：
  ① 把 6 个证据文件复制到**临时目录**；
  ② 在**副本**上注入 N 处**已知缺陷**（每处对应一条子判据）；
  ③ 用**同一个脚本**（只改 `--ev` 指向临时目录）跑；
  ④ 断言：注入 N 处 ⇒ 至少 N 条判据 FAIL 且 `verdict=FAIL`；
  ⑤ 断言：**原**证据目录跑 ⇒ `verdict=PASS`（对照）。

🔴 **纪律**：纯离线（只读/复制 JSON）⇒ 不占机器锁、不跑推理、不碰 GPU。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(HERE, 'app186_app051_acceptance_gate.py')
EV = HERE

#: 被复制的证据文件（覆盖总闸门读取的全部子项证据）
EVIDENCE_FILES = (
    'app181_pythonw_coldstart_v2_evidence.json',
    'app175_app043_clone_acceptance_evidence.json',
    'app179_app042_gui_accel_evidence.json',
    'app183_app042_formula_evidence.json',
    'app185_app048_gui_layout_pkg_evidence.json',
    'app184_app051_accel_listen_manifest.json',
)

#: 注入的已知缺陷：每条 = (证据文件, 描述, 改写函数)
MUTATIONS = (
    ('app181_pythonw_coldstart_v2_evidence.json',
     '① 把 pythonw 冷启动 verdict 改成 FAIL',
     lambda d: d.update({'verdict': 'FAIL'})),
    ('app175_app043_clone_acceptance_evidence.json',
     '② 把克隆验收 n_clone_rows 清零（无克隆音色）',
     lambda d: d.update({'n_clone_rows': 0})),
    ('app183_app042_formula_evidence.json',
     '③ 把加速公式一致性 verdict 改成 FAIL',
     lambda d: d.update({'verdict': 'FAIL'})),
    ('app185_app048_gui_layout_pkg_evidence.json',
     '④ 把 pkg_under_test 指向**仓库源码**（不是客户包）',
     lambda d: d.update({'pkg_under_test':
                         os.path.join(REPO, 'live_caption')})),
    ('app184_app051_accel_listen_manifest.json',
     '⑤ 把实听素材速度改成不含 1.2× / 1.3×',
     lambda d: d.update({'clips': [dict(c, speed=1.0) for c in d.get('clips', [])]})),
)


def run_gate(pkg_dir, ev_dir, out_path):
    r = subprocess.run(
        [sys.executable, SCRIPT, '--pkg', pkg_dir, '--ev', ev_dir, '--out', out_path],
        capture_output=True, text=True, cwd=REPO)
    out = r.stdout or ''
    if r.returncode != 0 and 'verdict=' not in out:
        raise RuntimeError('总闸门运行失败：%s\n%s' % (r.stderr[-2000:], out[-2000:]))
    with open(out_path, encoding='utf-8') as f:
        return json.load(f), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--out', default=os.path.join(
        EV, 'app186_app051_gate_discrimination_evidence.json'))
    args = ap.parse_args()

    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    import pkg_paths as _pkg_paths
    pkg_dir = _pkg_paths.resolve_pkg_dir(args.pkg)

    print('=' * 70)
    print('app186 判据鉴别力实测（注入已知缺陷 ⇒ 必须 FAIL）')
    print('=' * 70)
    print('包目录:', pkg_dir)

    tmp = tempfile.mkdtemp(prefix='app186_disc_')
    try:
        # ── 对照组：原证据目录 ⇒ 必须 PASS ────────────────────────────
        ctrl_out = os.path.join(tmp, 'ctrl.json')
        ctrl, ctrl_log = run_gate(pkg_dir, EV, ctrl_out)
        ctrl_pass = (ctrl.get('verdict') == 'PASS')
        print('\n[对照] 原证据目录 ⇒ verdict=%r（期望 PASS）'
              % ctrl.get('verdict'))

        # ── 实验组：副本注入缺陷 ⇒ 必须 FAIL ──────────────────────────
        os.makedirs(os.path.join(tmp, 'ev'), exist_ok=True)
        for name in EVIDENCE_FILES:
            shutil.copy(os.path.join(EV, name), os.path.join(tmp, 'ev', name))
        for fname, desc, fn in MUTATIONS:
            p = os.path.join(tmp, 'ev', fname)
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
            fn(d)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            print('  [注入] %s' % desc)

        exp_out = os.path.join(tmp, 'exp.json')
        exp, exp_log = run_gate(pkg_dir, os.path.join(tmp, 'ev'), exp_out)

        failed_checks = [c for c in exp.get('checks', []) if not c.get('ok')]
        exp_fail = (exp.get('verdict') == 'FAIL')
        enough = len(failed_checks) >= len(MUTATIONS)

        print('\n[实验] 注入 %d 处缺陷 ⇒ verdict=%r（期望 FAIL），'
              'FAIL 判据数 = %d（期望 ≥ %d）'
              % (len(MUTATIONS), exp.get('verdict'),
                 len(failed_checks), len(MUTATIONS)))
        for c in failed_checks:
            print('   - %s' % c.get('name'))

        ok = bool(ctrl_pass and exp_fail and enough)
        print('\n鉴别力判定：%s' % ('PASS（非恒真，判据能识破注入的缺陷）'
                                   if ok else 'FAIL'))

        result = {
            'script': os.path.basename(__file__),
            'purpose': '证明 app186 总闸门判据**非恒真**且覆盖被注入的缺陷',
            'pkg_dir': pkg_dir,
            'n_mutations': len(MUTATIONS),
            'mutations': [{'file': m[0], 'desc': m[1]} for m in MUTATIONS],
            'control': {
                'ev_dir': EV,
                'verdict': ctrl.get('verdict'),
                'n_pass': ctrl.get('n_pass'),
                'n_fail': ctrl.get('n_fail'),
                'expect': 'PASS',
                'ok': ctrl_pass,
            },
            'experiment': {
                'ev_dir': os.path.join(tmp, 'ev'),
                'verdict': exp.get('verdict'),
                'n_pass': exp.get('n_pass'),
                'n_fail': exp.get('n_fail'),
                'failed_check_names': [c.get('name') for c in failed_checks],
                'expect': 'FAIL',
                'ok': bool(exp_fail and enough),
            },
            'n_pass': 3 if ok else 0,
            'n_fail': 0 if ok else 1,
            'verdict': 'PASS' if ok else 'FAIL',
        }
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print('[evidence] %s' % args.out)
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main())
