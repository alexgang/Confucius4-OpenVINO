#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_pack_gates_guard_pkg.py —— §251 补齐：守卫**真的把 --pkg 闸门跑起来**。

🔴 **为什么必须补（死会话留下的真实缺口）**
   死会话（16:21–17:36）的 note 是「**验证 --pkg 闸门对 v2.6**」，
   但它写出来的守卫 `_app251_pack_gates_guard.py` 把 **3 个需要 `--pkg` 的闸门
   全部 SKIP**（理由写的是「需指定客户包，本轮不代选」）
   ⇒ **它证明的只是「闸门清单能抽出来」，并没有证明「闸门是绿的」**
   ⇒ 而 `check_internal_material --pkg <包>` **恰好是红的**
      （`ext/extension/player.js` 的 3×U+FFFD ⇒ 阻断出包）⇒ **假绿**。

🔴 **本脚本补什么**
   ① `--pkg` 参数：**显式指定**要验收的客户包目录（**不猜、不代选**）。
   ② 逐个跑需要 `--pkg` 的闸门：
      - `check_internal_material.py`            —— **只读**
      - `results/app/app170_version_identity_gate.py` —— **只读**（自建影子包，不碰真包）
      - `live_caption/sync_c172_version_identity_to_pkg.py` —— **会写包**！
        ⇒ **一律加 `--dry-run`**（脚本自带该开关 ⇒ 真跑一遍校验逻辑，但不写盘）
   ③ **区分「只读闸门」与「会写盘的闸门」**：后者**必须**带 `--dry-run`，
      否则就是对客户包动手 —— 本脚本**拒绝**不带 `--dry-run` 地调用它。
   ④ 记录每个闸门的 **rc + 输出要点** ⇒ 落盘成证据。

🔴 **安全约束**
   * 默认**不跑**任何 `--pkg` 闸门（不给 `--pkg` 就只跑离线闸门）⇒ 不误触客户包。
   * `--pkg` 指向的目录**只被读取**（除 `sync_c172` 的 `--dry-run` 外，不写）。
   * 零推理、零 GPU、零 NPU、不调 MiniMax、不打包、不改客户包。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **会写盘的脚本** ⇒ 必须带 `--dry-run` 才允许跑
MUTATING = {
    'live_caption/sync_c172_version_identity_to_pkg.py': ['--dry-run'],
}

#: **只读**脚本（可安全直接跑）
READONLY = {
    'check_internal_material.py',
    'results/app/app170_version_identity_gate.py',
    'results/app/app049_pkg_path_hardcode_gate.py',
}


def run_script(rel, argv, timeout=1800):
    path = os.path.join(REPO, rel.replace('/', os.sep))
    if not os.path.isfile(path):
        return None, '脚本不存在'
    cmd = [sys.executable, path] + argv
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout,
                           cwd=REPO)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return None, '超时（>%d s）' % timeout
    except (OSError, subprocess.SubprocessError) as e:
        return None, '执行失败：%r' % e


def tail(out, n=400):
    out = (out or '').strip()
    return out[-n:] if len(out) > n else out


def main():
    ap = argparse.ArgumentParser(
        description='§251 补齐：把需要 --pkg 的打包路径闸门真跑一遍')
    ap.add_argument('--pkg', default=None,
                    help='要验收的客户包目录（只读）。不给 ⇒ 只跑离线闸门')
    ap.add_argument('--json', default=None, help='证据落盘路径')
    args = ap.parse_args()

    results = []
    overall_ok = True

    print('=' * 72)
    print('§251 补齐：--pkg 闸门实跑（只读；不猜客户包 ⇒ 需显式 --pkg）')
    print('=' * 72)
    if args.pkg:
        pkg = os.path.abspath(args.pkg)
        if not os.path.isdir(pkg):
            print('!! --pkg 目录不存在：%s' % pkg)
            return 2
        print('验收包目录：%s' % pkg)
    else:
        print('未给 --pkg ⇒ **不跑**任何需要客户包的闸门（不代选、不误触）')
    print()

    # ── 离线闸门（不需要 --pkg）──────────────────────────────────────
    for rel in sorted(READONLY):
        if rel == 'check_internal_material.py' or rel.startswith('results/app/app170'):
            continue          # 需要 --pkg 的，稍后跑
        rc, out = run_script(rel, [])
        ok = (rc == 0)
        overall_ok = overall_ok and ok
        results.append(dict(script=rel, argv=[], rc=rc, pass_=ok,
                            tail=tail(out)))
        print('  [%s] %s — rc=%r' % ('PASS' if ok else 'FAIL', rel, rc))
        if not ok:
            print('        %s' % tail(out, 600).replace('\n', '\n        '))

    # ── 需要 --pkg 的闸门 ────────────────────────────────────────────
    if args.pkg:
        for rel in sorted(READONLY):
            if not (rel == 'check_internal_material.py'
                    or rel.startswith('results/app/app170')):
                continue
            rc, out = run_script(rel, ['--pkg', args.pkg])
            ok = (rc == 0)
            overall_ok = overall_ok and ok
            results.append(dict(script=rel, argv=['--pkg', args.pkg], rc=rc,
                                pass_=ok, tail=tail(out)))
            print('  [%s] %s --pkg — rc=%r' % ('PASS' if ok else 'FAIL', rel, rc))
            print('        %s' % tail(out, 600).replace('\n', '\n        '))

        # ── 会写盘的闸门：**必须** --dry-run ──────────────────────────
        for rel, extra in sorted(MUTATING.items()):
            argv = ['--pkg', args.pkg] + list(extra)
            assert '--dry-run' in argv, '会写盘的闸门必须带 --dry-run'
            rc, out = run_script(rel, argv)
            # dry-run 的 rc=0 表示「校验通过、无需改动」；有改动时会以其它码报告
            ok = (rc == 0)
            overall_ok = overall_ok and ok
            results.append(dict(script=rel, argv=argv, rc=rc, pass_=ok,
                                dry_run=True, tail=tail(out)))
            print('  [%s] %s %s — rc=%r（**dry-run，未写包**）'
                  % ('PASS' if ok else 'FAIL', rel, ' '.join(extra), rc))
            print('        %s' % tail(out, 600).replace('\n', '\n        '))
    else:
        for rel in sorted(READONLY):
            if (rel == 'check_internal_material.py'
                    or rel.startswith('results/app/app170')):
                results.append(dict(script=rel, argv=['--pkg', '<未指定>'],
                                    rc=None, pass_=None, skipped=True,
                                    tail='需 --pkg，未指定 ⇒ 未跑'))
                print('  [SKIP] %s --pkg（需显式指定客户包）' % rel)

    print()
    n_pass = len([r for r in results if r.get('pass_') is True])
    n_fail = len([r for r in results if r.get('pass_') is False])
    n_skip = len([r for r in results if r.get('pass_') is None])
    print('PASS %d / FAIL %d / SKIP %d' % (n_pass, n_fail, n_skip))
    verdict = 'PASS' if overall_ok else 'FAIL'
    print('总判定：%s' % verdict)
    print('=' * 72)

    ev = args.json or os.path.join(HERE, 'app251_pack_gates_guard_pkg.json')
    with io.open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(pkg=args.pkg, n_pass=n_pass, n_fail=n_fail,
                       n_skip=n_skip, verdict=verdict, results=results),
                  f, ensure_ascii=False, indent=1)
    print('证据已落盘：%s' % ev)
    return 0 if overall_ok else 1


if __name__ == '__main__':
    sys.exit(main())
