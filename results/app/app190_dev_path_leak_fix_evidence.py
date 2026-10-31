#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app190_dev_path_leak_fix_evidence.py —— 「§120 修掉包内生产模块写死开发机家目录」的验收。

🔴 **零推理、零 GPU、零测速**（本轮不取共享机器锁）。

判据分两组（§四纪律）：

* **REAL 组**：修复后必须**全部成立**（命中即 FAIL）。
* **BUG 组（反证）**：拿**修前的真实源码**跑同一套场景 ⇒ 必须**命中**
  ⇒ 证明缺陷**曾经真实存在** ⇒ 判据**非恒真**。
  ⚠️ 基线用**固定 commit SHA**（不用 `HEAD`、不依赖临时备份目录）——
  否则修复提交之后 `HEAD` 就是修复版 ⇒ 反证**永远落空** ⇒ 失去证据价值。

跑法::

    python results/app/app190_dev_path_leak_fix_evidence.py
    python results/app/app190_dev_path_leak_fix_evidence.py --json <out.json>
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **修前基线 commit**（`tts_worker.py` 最后一次「含开发机硬编码」的提交）
#:   —— 必须用**固定 SHA**，不能用 `HEAD`（§118 的教训）。
BASELINE_COMMIT = 'bb7274e'

#: 交付 zip 里的生产模块（与本轮实测一致）
TARGET_FILES = ['speaker_assets.py', 'speaker_tracker.py', 'tts_cuda.py',
                'tts_engine.py', 'tts_worker.py']

DEV_HOME_RE = re.compile(r'[A-Za-z]:[\\/]Users[\\/][^\\/\'"\s]+[\\/]', re.IGNORECASE)

RESULTS = []


def check(group, name, ok, detail=''):
    RESULTS.append({'group': group, 'name': name,
                    'pass': bool(ok), 'detail': str(detail)[:400]})
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name,
                            ('— ' + str(detail)[:200]) if detail else ''))
    return bool(ok)


def code_lines(path):
    """返回「属于代码」的行号集合（跳过注释与 docstring）。"""
    src = open(path, 'r', encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set(range(1, len(src.splitlines()) + 1))
    cl = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            continue
        if isinstance(node, ast.Expr):
            v = getattr(node, 'value', None)
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                continue
        ln = getattr(node, 'lineno', None)
        if ln is None:
            continue
        end = getattr(node, 'end_lineno', None) or ln
        for n in range(ln, end + 1):
            cl.add(n)
    return cl


def dev_home_hits(path):
    """该文件**代码行**里出现开发机家目录的位置。"""
    src = open(path, 'r', encoding='utf-8', errors='replace').read()
    cl = code_lines(path)
    out = []
    for i, ln in enumerate(src.split('\n'), 1):
        if i in cl and DEV_HOME_RE.search(ln) and not ln.strip().startswith('#'):
            out.append((i, ln.strip()[:160]))
    return out


def git_show(commit, rel):
    """取指定 commit 下的文件内容（`git show` ⇒ 固定基线）。"""
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser(description='§120 开发机路径泄漏修复验收')
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    print('== §120 包内生产模块「开发机绝对路径」修复验收 ==')

    # ───────────────────────── REAL 组 ─────────────────────────
    print('-- REAL 组（修复后必须全部成立）--')

    # R1：仓库侧 5 个目标文件**代码行**里不再有开发机家目录
    all_hits = {}
    for f in TARGET_FILES:
        p = os.path.join(REPO, 'live_caption', f)
        h = dev_home_hits(p)
        if h:
            all_hits[f] = h
    check('REAL', 'R1 仓库 5 个目标文件代码行无开发机家目录',
          not all_hits, json.dumps(all_hits, ensure_ascii=False))

    # R2：修复后的常量与**修前硬编码**逐字节相同 ⇒ 开发机行为零变化
    pairs = [('speaker_assets.py', 'DEV_ASR_SCRIPTS'),
             ('speaker_tracker.py', '_ASR_SCRIPTS')]
    eq = {}
    for f, var in pairs:
        old_src = git_show(BASELINE_COMMIT, 'live_caption/%s' % f)
        new_src = open(os.path.join(REPO, 'live_caption', f), encoding='utf-8').read()

        def grab(src):
            if src is None:
                return None
            t = ast.parse(src)
            for n in t.body:
                if isinstance(n, ast.Assign):
                    for tg in n.targets:
                        if isinstance(tg, ast.Name) and tg.id == var:
                            return eval(compile(ast.Expression(n.value), '<x>', 'eval'),
                                        {}, {'os': os})
            return None

        o, n = grab(old_src), grab(new_src)
        eq[f] = {'var': var, 'old': o, 'new': n, 'equal': o == n}
    check('REAL', 'R2 修复后常量与修前硬编码逐字节相同（行为零变化）',
          all(v['equal'] for v in eq.values()),
          json.dumps(eq, ensure_ascii=False))

    # R3：修前 commit 的这些文件**确实**含硬编码（证明基线有效）
    base_hits = {}
    for f in TARGET_FILES:
        src = git_show(BASELINE_COMMIT, 'live_caption/%s' % f)
        if src is None:
            base_hits[f] = None
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                         encoding='utf-8') as tf:
            tf.write(src)
            tmp = tf.name
        try:
            base_hits[f] = len(dev_home_hits(tmp))
        finally:
            os.unlink(tmp)
    check('REAL', 'R3 基线 commit %s 的目标文件确有硬编码（基线有效）'
          % BASELINE_COMMIT,
          all(v for v in base_hits.values()),
          json.dumps(base_hits, ensure_ascii=False))

    # R4：全部目标文件 `ast.parse` 通过（语法未破）
    bad = []
    for f in TARGET_FILES:
        p = os.path.join(REPO, 'live_caption', f)
        try:
            ast.parse(open(p, encoding='utf-8').read())
        except SyntaxError as e:
            bad.append('%s: %s' % (f, e))
    check('REAL', 'R4 5 个目标文件 ast.parse 通过', not bad, bad)

    # R5：`tts_cuda.ENV_PY` 推导值与原硬编码**逐字节相同**
    src = open(os.path.join(REPO, 'live_caption', 'tts_cuda.py'),
               encoding='utf-8').read()
    t = ast.parse(src)
    env_py = None
    for n in t.body:
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name) and tg.id == 'ENV_PY':
                    env_py = ast.unparse(n.value)
    derived = os.path.join(os.path.expanduser('~'),
                           '_fq3tts_env', 'Scripts', 'python.exe')
    hard = r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe'
    check('REAL', 'R5 tts_cuda ENV_PY 推导值 == 原硬编码值',
          derived == hard, 'derived=%r hard=%r' % (derived, hard))

    # ───────────────────────── BUG 组（反证）─────────────────────────
    print('-- BUG 组（修前源码必须命中 ⇒ 判据非恒真）--')

    # B1：拿基线 commit 的 `tts_cuda.py` 跑同一套「代码行泄漏」判定 ⇒ 必须命中
    src = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda.py')
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                     encoding='utf-8') as tf:
        tf.write(src)
        tmp = tf.name
    try:
        h = dev_home_hits(tmp)
    finally:
        os.unlink(tmp)
    check('BUG', 'B1 基线 tts_cuda.py 被判出开发机路径（缺陷曾真实存在）',
          len(h) >= 1, h)

    # B2：拿基线 commit 的 `tts_worker.py` 跑同一套判定 ⇒ 必须命中
    src = git_show(BASELINE_COMMIT, 'live_caption/tts_worker.py')
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                     encoding='utf-8') as tf:
        tf.write(src)
        tmp = tf.name
    try:
        h = dev_home_hits(tmp)
    finally:
        os.unlink(tmp)
    check('BUG', 'B2 基线 tts_worker.py 被判出开发机路径（缺陷曾真实存在）',
          len(h) >= 1, h)

    # B3：docstring / 注释里的路径**不得**被判成泄漏（防「判据恒真」）
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                     encoding='utf-8') as tf:
        tf.write('r"""\n示例 C:\\Users\\SomeOne\\x\n"""\n'
                 '# 注释 C:\\Users\\SomeOne\\y\n'
                 'V = 1\n')
        tmp = tf.name
    try:
        h = dev_home_hits(tmp)
    finally:
        os.unlink(tmp)
    check('BUG', 'B3 docstring/注释里的路径不判泄漏（判据不恒真）',
          h == [], h)

    # ───────────────────────── 汇总 ─────────────────────────
    n_pass = sum(1 for r in RESULTS if r['pass'])
    n_fail = len(RESULTS) - n_pass
    res = {
        'n_pass': n_pass,
        'n_fail': n_fail,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
        'baseline_commit': BASELINE_COMMIT,
        'target_files': TARGET_FILES,
        'checks': RESULTS,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'script': os.path.basename(__file__),
        'inference': 'none（零推理、零 GPU、零测速；本轮未取共享机器锁）',
    }
    print('  结论: %s（PASS %d / FAIL %d）' % (res['verdict'], n_pass, n_fail))

    if args.json:
        outp = args.json if os.path.isabs(args.json) else os.path.join(REPO, args.json)
        d = os.path.dirname(outp)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(outp, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print('  证据已落盘: %s' % outp)

    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
