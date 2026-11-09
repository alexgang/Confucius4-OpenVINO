# -*- coding: utf-8 -*-
"""app352_app086_merge_tests.py — APP-086(1) 合并 claude-clone 后的回归套件。

纯 CPU 静态：不加载模型、不占设备、不推理、不测速、不建 MACHINE_LOCK。
  1. 对合并提交的 8 个 .py 文件做 ast.parse（语法未被合并破坏）；
  2. 跑 6 个仓库既有纯静态闸门/自检（用仓库 .venv python）；
  3. 跑前/跑后快照 live_caption/ 与 results/app/ 下所有已跟踪文件的 SHA256
     ⇒ 任何被测试脚本改写的既有证据都如实列出（不静默吞掉）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PY = os.path.join(REPO, '.venv', 'Scripts', 'python.exe')
RA = os.path.join(REPO, 'results', 'app')
EVID = os.path.join(RA, 'app352_app086_merge_test_evidence.json')

MERGED_PY = [
    r'live_caption\asr_spk_v24\asr052_speaker_tracker_api.py',
    r'live_caption\asr_spk_v24\asr_spk_cluster_v2.py',
    r'live_caption\live_caption_app.py',
    r'live_caption\speaker_voice.py',
    r'live_caption\tts_engine.py',
    r'live_caption\tts_engine_patch.py',
    r'pack_v13.py',
    r'results\app\app_v24_build.py',
]
TESTS = [
    'app007_gate_selftest.py',
    'app049_gate_selftest.py',
    '_app294_gate_selftest.py',
    '_app307_assert_pkg_clean_selftest.py',
    '_app315_app080_preset_only_selftest.py',
    'app236_app067_clone_fix_gate.py',
]


def sha256_file(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def snapshot():
    out = subprocess.run(['git', 'ls-files', 'live_caption', 'results/app'],
                         cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace')
    d = {}
    for rel in (out.stdout or '').splitlines():
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if os.path.isfile(p):
            try:
                d[rel] = sha256_file(p)
            except OSError:
                pass
    return d


def main():
    assert os.path.isfile(PY), 'missing .venv python: ' + PY
    before = snapshot()
    checks = []

    def ck(name, ok, detail=''):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail)[:300]))

    # 1. ast.parse 合并进来的 py 文件
    ast_rows = []
    for rel in MERGED_PY:
        p = os.path.join(REPO, rel)
        try:
            src = open(p, 'rb').read().decode('utf-8')
            ast.parse(src, filename=rel)
            ast_rows.append(dict(file=rel, bytes=len(src.encode('utf-8')),
                                 sha256=hashlib.sha256(src.encode('utf-8')).hexdigest(),
                                 ast='PASS'))
        except Exception as e:
            ast_rows.append(dict(file=rel, ast='FAIL', error=repr(e)))
    ck('ast_all_merged_py', all(r['ast'] == 'PASS' for r in ast_rows),
       '%d/%d' % (sum(r['ast'] == 'PASS' for r in ast_rows), len(ast_rows)))

    # 2. 既有闸门
    test_rows = []
    for name in TESTS:
        p = os.path.join(RA, name)
        if not os.path.isfile(p):
            test_rows.append(dict(script=name, rc=None, verdict='MISSING'))
            continue
        t0 = time.time()
        try:
            r = subprocess.run([PY, p], cwd=REPO, capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=180)
            rc, so, se = r.returncode, r.stdout or '', r.stderr or ''
        except subprocess.TimeoutExpired as e:
            rc, so, se = -99, str(e), ''
        except Exception as e:
            rc, so, se = -98, '', repr(e)
        test_rows.append(dict(script=name, rc=rc, wall_s=round(time.time() - t0, 2),
                              stdout_tail=so[-420:], stderr_tail=se[-420:],
                              verdict='PASS' if rc == 0 else 'FAIL'))
    for r in test_rows:
        ck('test_' + r['script'], r['verdict'] == 'PASS',
           'rc=%s wall=%s' % (r['rc'], r.get('wall_s')))

    after = snapshot()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    ck('tracked_files_unchanged_by_tests', len(changed) == 0,
       'changed=%d %s' % (len(changed), changed[:8]))

    ev = dict(
        tool='app352_app086_merge_tests',
        python=PY,
        merge_commit=subprocess.run(['git', 'log', '-1', '--format=%h %s'], cwd=REPO,
                                    capture_output=True, text=True).stdout.strip(),
        merged_py=ast_rows,
        tests=test_rows,
        n_tests=len(test_rows),
        n_test_pass=sum(1 for r in test_rows if r['verdict'] == 'PASS'),
        snapshot_before_n=len(before), snapshot_after_n=len(after),
        tracked_files_changed=changed,
        checks=checks,
        n_pass=sum(1 for c in checks if c['ok']),
        n_fail=sum(1 for c in checks if not c['ok']),
        verdict='PASS' if all(c['ok'] for c in checks) else 'FAIL',
    )
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(verdict=ev['verdict'], n_pass=ev['n_pass'], n_fail=ev['n_fail'],
                          tests=[(r['script'], r['verdict'], r.get('rc')) for r in test_rows],
                          ast_n=len(ast_rows), changed=len(changed)), ensure_ascii=False))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
