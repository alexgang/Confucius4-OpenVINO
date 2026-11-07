#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app328 — APP-081 第 3 点：assert_pkg_clean 改为 PKG_EXCLUDE_PATTERNS 驱动后的
6 类夹具回归（含反证）。

被测对象 = live_caption/assert_pkg_clean.py 的 scan()。
判据：
  * 6/6 违规路径全部检出（§148 覆盖矩阵里原先 3 类零检出的必须翻正）
  * 3 条干净路径 0 误伤
  * 规则来源 == PKG_EXCLUDE_PATTERNS（单一事实来源）
  * 反证 3 组（把被测对象换回旧 2 类闸门 / 清空规则 / 删后 3 条规则）
    必须被识破，否则说明判据恒真
  * 真实 v2.2 目录只读扫描 ⇒ 只读、不写、不删
纯 CPU 静态，不加载模型、不占设备。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import shutil
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV = os.path.join(ROOT, 'live_caption')
GATE = os.path.join(DEV, 'assert_pkg_clean.py')
OUT = os.path.join(ROOT, 'results', 'app', '_app328_app081_gate_fix_regression.json')
# 🔴 不写死客户包目录名（§48 包路径写死闸门）：用 pkg_paths 的前缀常量拼出
#   「历史对照包 v2.2」，代码行里不出现完整的 `..._v2.2` 字面量。
sys.path.insert(0, ROOT)
import pkg_paths  # noqa: E402
V22 = os.path.join(pkg_paths.PKG_ROOT_DEFAULT,
                   pkg_paths.PKG_NAME_PREFIX + '2.2')

# §148 facts.coverage_matrix 的 6 类夹具（逐字沿用，保证回归可比）
VIOLATIONS = [
    ('APP-077 固定 token', 'ext/bridge_token.txt'),
    ('APP-078 示例音色', 'python/Lib/site-packages/babelvox/data/speakers/cindy.json'),
    ('APP-078 示例音色', 'python/Lib/site-packages/babelvox/data/speakers/steve.npy'),
    ('APP-080 ④ 克隆音色', 'app/voices/spk_clone_s1.wav'),
    ('APP-080 ④ 克隆产物目录', 'app/v23_clone_r2/male_01_seg5.wav'),
    ('APP-080 ④ 测试 wav', 'app/audio/foo_test.wav'),
]
CLEAN = [
    'app/voices/preset_A.wav',
    'python/Lib/site-packages/babelvox/speakers.py',
    'models/tokenizer_config.json',
]


def load_gate():
    sys.path.insert(0, DEV)
    spec = importlib.util.spec_from_file_location('_app328_gate', GATE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_fixture(root, rels):
    for rel in rels:
        p = os.path.join(root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(b'FIXTURE')
    return root


def sha256_file(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    checks = []
    counter = []

    def chk(cond, name, detail=''):
        checks.append({'name': name, 'pass': bool(cond), 'detail': detail})

    gate = load_gate()
    rules = gate.load_exclude_rules()
    labels = [lab for _re, lab in rules]

    # ① 规则来源：必须来自 v23_preset_only.PKG_EXCLUDE_PATTERNS
    chk(all(lab.startswith('PKG_EXCLUDE_PATTERNS: ') for lab in labels),
        'rules_from_PKG_EXCLUDE_PATTERNS',
        'src labels=%r' % [l.split(':')[0] for l in labels])
    try:
        from v23_preset_only import PKG_EXCLUDE_PATTERNS
        chk(len(rules) == len(PKG_EXCLUDE_PATTERNS),
            'rule_count_matches_source', 'n=%d/%d' % (len(rules), len(PKG_EXCLUDE_PATTERNS)))
        n_pats = len(PKG_EXCLUDE_PATTERNS)
    except Exception as e:
        chk(False, 'rule_count_matches_source', 'import failed: %r' % (e,))
        n_pats = -1

    tmp = tempfile.mkdtemp(prefix='_app328_fixture_')
    try:
        make_fixture(tmp, [r for _c, r in VIOLATIONS] + CLEAN)
        bad = gate.scan(tmp)
        bad_rel = [b[0].replace(os.sep, '/') for b in bad]

        # ② 6/6 检出
        for cat, rel in VIOLATIONS:
            hit = [b for b in bad if b[0].replace(os.sep, '/') == rel]
            chk(len(hit) >= 1, 'detect_' + rel.replace('/', '_'),
                'category=%s hits=%d reason=%s' % (cat, len(hit),
                                                    hit[0][1] if hit else ''))
        # ③ 干净路径 0 误伤
        for rel in CLEAN:
            chk(not any(b[0].replace(os.sep, '/') == rel for b in bad),
                'clean_not_flagged_' + rel.replace('/', '_'))
        chk(len(bad) == len(VIOLATIONS), 'no_extra_violations',
            'n_bad=%d expect=%d' % (len(bad), len(VIOLATIONS)))

        # ④ 反证：反证必须破坏「被测的那个对象」（EXCLUDE_RULES）
        #    E1 换回旧 2 类闸门（等价 TOKEN_RE + VOICE_RE 的两条规则）
        old_rules = [
            (re.compile(r'(?i)(^|/)bridge_token\.txt$'), 'OLD: token'),
            (re.compile(r'(?i)python/Lib/site-packages/babelvox/data/speakers/'
                        r'(cindy|lou|phil|steve)\.(json|npy)$'), 'OLD: babelvox'),
        ]
        orig = gate.EXCLUDE_RULES
        gate.EXCLUDE_RULES = old_rules
        bad_old = gate.scan(tmp)
        gate.EXCLUDE_RULES = orig
        old_hit = len([b for b in bad_old if 'clone' in b[0].replace(os.sep, '/')
                       or '_test' in b[0]])
        counter.append({'id': 'E1_old_two_class_gate',
                        'n_detected': len(bad_old), 'n_of_6': len(bad_old),
                        'clone_or_test_detected': old_hit,
                        'identified': len(bad_old) < len(VIOLATIONS)})
        chk(len(bad_old) < len(VIOLATIONS), 'counterproof_E1_old_gate_identified',
            'old gate detects %d/6 (must be <6)' % len(bad_old))

        #    E2 清空规则 ⇒ 0 检出
        gate.EXCLUDE_RULES = []
        bad_empty = gate.scan(tmp)
        gate.EXCLUDE_RULES = orig
        counter.append({'id': 'E2_empty_rules', 'n_detected': len(bad_empty),
                        'identified': len(bad_empty) == 0})
        chk(len(bad_empty) == 0 and len(VIOLATIONS) > 0,
            'counterproof_E2_empty_rules_identified',
            'empty rules detects %d' % len(bad_empty))

        #    E3 删掉后 3 条（克隆音色 / 产物目录 / 测试 wav）⇒ 恰好漏 3 类
        gate.EXCLUDE_RULES = rules[:-3]
        bad_trim = gate.scan(tmp)
        gate.EXCLUDE_RULES = orig
        missed = [rel for _c, rel in VIOLATIONS
                  if not any(b[0].replace(os.sep, '/') == rel for b in bad_trim)]
        counter.append({'id': 'E3_drop_last3_rules', 'n_detected': len(bad_trim),
                        'missed': missed,
                        'identified': len(missed) == 3})
        chk(len(missed) == 3, 'counterproof_E3_dropped_rules_identified',
            'missed=%r' % missed)

        # ⑤ assert_clean 返回码（干净目录 0 / 违规目录 1）
        clean_dir = tempfile.mkdtemp(prefix='_app328_clean_')
        try:
            make_fixture(clean_dir, CLEAN)
            rc_clean = gate.assert_clean(clean_dir)
            rc_bad = gate.assert_clean(tmp)
            chk(rc_clean == 0 and rc_bad == 1, 'assert_clean_return_codes',
                'clean=%d bad=%d' % (rc_clean, rc_bad))
        finally:
            shutil.rmtree(clean_dir, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ⑥ 真实 v2.2 目录只读扫描（APP-081：旧包不动，只如实报告历史违规）
    v22 = {'present': os.path.isdir(V22)}
    if v22['present']:
        before = sha256_file(os.path.join(V22, 'ext', 'bridge_token.txt'))
        v22_bad = gate.scan(V22)
        after = sha256_file(os.path.join(V22, 'ext', 'bridge_token.txt'))
        v22['n_violations'] = len(v22_bad)
        v22['reasons'] = sorted(set(b[1].split(':')[0] for b in v22_bad))
        v22['bridge_token_sha_unchanged'] = (before == after)
        v22['sample'] = [b[0].replace(os.sep, '/') for b in v22_bad[:10]]
        chk(len(v22_bad) >= 9, 'v22_readonly_historical_violations_detected',
            'n=%d' % len(v22_bad))
        chk(v22['bridge_token_sha_unchanged'], 'v22_not_modified')
    else:
        v22['n_violations'] = None

    n_pass = sum(1 for c in checks if c['pass'])
    n_fail = len(checks) - n_pass
    n_cp = sum(1 for c in counter if c['identified'])
    ev = {
        'tool': '_app328', 'app': 'APP-081 第 3 点',
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'verdict': 'PASS' if (n_fail == 0 and n_cp == len(counter)) else 'FAIL',
        'n_pass': n_pass, 'n_fail': n_fail,
        'counterproof_identified': '%d/%d' % (n_cp, len(counter)),
        'gate': {'path': GATE, 'bytes': os.path.getsize(GATE),
                 'sha256': sha256_file(GATE)},
        'n_exclude_patterns_source': n_pats,
        'n_exclude_rules_loaded': len(rules),
        'fixture_violations': VIOLATIONS, 'fixture_clean': CLEAN,
        'checks': checks, 'counterproof': counter, 'v22_readonly': v22,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[%s] %d PASS / %d FAIL / 反证 %d/%d ⇒ %s'
          % (ev['verdict'], n_pass, n_fail, n_cp, len(counter), OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
