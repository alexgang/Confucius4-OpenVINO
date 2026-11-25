#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_profile_behavior_test.py — **APP-137 §1 的行为级复核**。

## 为什么必须是「行为级」而不是「读文本」

🔴 §四 的判据铁律：**PASS ≠ 正确** ⇒ 判据必须
① **能被有缺陷的旧产物识破**（反证组）；② **行为级真跑**（不是 grep 文本）。

⇒ 本脚本对 `package_profile.py` 做**真跑**：
   在**临时目录**里造出四种标记文件（full / 新 minimvp / 老 minimvp / 坏标记），
   各自**真跑一遍** `package_profile` 的四个读取口，断言它们的返回值。

## 四组用例（每组都断言「真跑出来的值」）

| 组 | 标记 | 期望 `allow_clone_voice` | 期望 `allow_bgkeep` | 期望 `allow_tts_c13` |
|---|---|---|---|---|
| A 完整版（v2.6 的 marker，**无新字段**） | `profile=full` | True | True | True |
| B 新 MiniMVP v1.2 | `profile=minimvp` + 三个新字段 | **True** | **True** | **False** |
| C 老 MiniMVP v1.1.1（**只有旧字段**） | `profile=minimvp` + `allow_clone_voice=false` | **False** | **False** | **False** |
| D 坏标记（不是 json） | 坏内容 | True（按 full） | True | True |

🔴 **C 组是本脚本的承重用例**：它证明「老 MiniMVP 包行为逐字不变」。

## 反证组（**必须有鉴别力**）

反证组把 `package_profile.py` 换成**有缺陷的版本**（把
`allow_clone_voice` 又改回「minimvp ⇒ False」硬编码）⇒ 判据**必须 FAIL**。
⇒ 若反证组也 PASS ⇒ 判据是恒真的假 PASS ⇒ **本脚本自己就是坏的**。

## 用法
```
python live_caption/_app137_profile_behavior_test.py
```
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app137_profile_behavior.json')

PROFILE_PY = os.path.join(HERE, 'package_profile.py')

#: 四组用例：(名称, marker 内容或 None=坏标记, 期望值 dict)
CASES = [
    ('A_full_v26_marker', {
        'profile': 'full', 'allow_cuda': True, 'allow_clone_voice': True,
        'target_langs': 10,
    }, {'allow_clone_voice': True, 'allow_bgkeep': True, 'allow_tts_c13': True,
        'is_minimvp': False}),
    ('B_new_minimvp_v12', {
        'profile': 'minimvp', 'allow_cuda': False, 'allow_clone_voice': True,
        'allow_bgkeep': True, 'tts_c13': False, 'mt_model': 'mt2-int8sym-cw-q',
        'target_langs': 10,
    }, {'allow_clone_voice': True, 'allow_bgkeep': True, 'allow_tts_c13': False,
        'is_minimvp': True}),
    ('C_old_minimvp_v111', {
        'profile': 'minimvp', 'allow_cuda': False, 'allow_clone_voice': False,
        'target_langs': 10,
    }, {'allow_clone_voice': False, 'allow_bgkeep': False, 'allow_tts_c13': False,
        'is_minimvp': True}),
    ('D_broken_marker', '@@not-json@@', {
        'allow_clone_voice': True, 'allow_bgkeep': True, 'allow_tts_c13': True,
        'is_minimvp': False}),
]


def make_sandbox(marker_obj, profile_src: str, tag: str):
    """造一个临时「包根」，把 profile.py 放成 `<包根>/app/package_profile.py`。"""
    root = tempfile.mkdtemp(prefix='app137_pf_%s_' % tag)
    appd = os.path.join(root, 'app')
    os.makedirs(appd, exist_ok=True)
    shutil.copy2(profile_src, os.path.join(appd, 'package_profile.py'))
    if isinstance(marker_obj, str):
        with open(os.path.join(root, 'package_profile.json'), 'w',
                  encoding='utf-8') as fh:
            fh.write(marker_obj)
    else:
        with open(os.path.join(root, 'package_profile.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(marker_obj, fh, ensure_ascii=False)
    return root


def run_case(profile_src: str, name: str, marker_obj, expect: dict):
    root = make_sandbox(marker_obj, profile_src, name)
    saved_path = list(sys.path)
    saved_mod = sys.modules.pop('package_profile', None)
    try:
        sys.path.insert(0, os.path.join(root, 'app'))
        mod = importlib.import_module('package_profile')
        got = {
            'allow_clone_voice': mod.allow_clone_voice(),
            'allow_bgkeep': mod.allow_bgkeep(),
            'allow_tts_c13': mod.allow_tts_c13(),
            'is_minimvp': mod.is_minimvp(),
        }
    finally:
        sys.path = saved_path
        sys.modules.pop('package_profile', None)
        if saved_mod is not None:
            sys.modules['package_profile'] = saved_mod
        shutil.rmtree(root, ignore_errors=True)
    checks = []
    for k, v in expect.items():
        checks.append({'name': '%s.%s' % (name, k), 'ok': got.get(k) == v,
                       'detail': '期望 %r / 实测 %r' % (v, got.get(k))})
    return {'case': name, 'got': got, 'expect': expect,
            'checks': checks, 'ok': all(c['ok'] for c in checks)}


def main():
    checks = []
    results = []

    # ── 正向：四组用例 ──────────────────────────────────────────────
    for name, marker_obj, expect in CASES:
        r = run_case(PROFILE_PY, name, marker_obj, expect)
        results.append(r)
        checks.extend(r['checks'])

    # ── 反证组：把 `allow_clone_voice` 改回「minimvp ⇒ False」硬编码 ──
    #    ⇒ B 组（期望 True）**必须 FAIL** ⇒ 判据有鉴别力。
    with open(PROFILE_PY, encoding='utf-8') as fh:
        good_src = fh.read()
    bad_src = good_src.replace(
        "    if is_minimvp():\n"
        "        # 🔴 MiniMVP：读标记；**缺字段 ⇒ False**（保守 ⇒ 不会静默放开克隆）。\n"
        "        return bool(_MARKER.get('allow_clone_voice', False))\n",
        "    if is_minimvp():\n"
        "        return False\n", 1)
    if bad_src == good_src:
        print('FAIL: 反证组改不动（源码形态与预期不符）⇒ 判据无法证明有鉴别力')
        return 3
    tmp_bad = os.path.join(tempfile.mkdtemp(prefix='app137_bad_'),
                           'package_profile.py')
    with open(tmp_bad, 'w', encoding='utf-8') as fh:
        fh.write(bad_src)
    r_bad = run_case(tmp_bad, 'X_counterexample_hardcoded_false',
                     CASES[1][1], CASES[1][2])
    results.append(r_bad)
    ce_ok = (not r_bad['ok']) and any(
        not c['ok'] for c in r_bad['checks'])
    checks.append({
        'name': 'counterexample_must_fail',
        'ok': ce_ok,
        'detail': ('反证组（minimvp 硬编码 False）实测 %s ⇒ 判据有鉴别力'
                   % ('FAIL（符合预期）' if not r_bad['ok'] else 'PASS（判据恒真！）'))})
    shutil.rmtree(os.path.dirname(tmp_bad), ignore_errors=True)

    # ── 反证组 2：把 `allow_tts_c13` 的 minimvp 默认改成 True ────────
    bad2_src = good_src.replace(
        "    if is_minimvp():\n"
        "        return bool(_MARKER.get('tts_c13', False))\n",
        "    if is_minimvp():\n"
        "        return bool(_MARKER.get('tts_c13', True))\n", 1)
    if bad2_src != good_src:
        tmp_bad2 = os.path.join(tempfile.mkdtemp(prefix='app137_bad2_'),
                                'package_profile.py')
        with open(tmp_bad2, 'w', encoding='utf-8') as fh:
            fh.write(bad2_src)
        r_bad2 = run_case(tmp_bad2, 'Y_counterexample_c13_default_true',
                          CASES[2][1], CASES[2][2])
        results.append(r_bad2)
        ce2_ok = not r_bad2['ok']
        checks.append({
            'name': 'counterexample2_must_fail',
            'ok': ce2_ok,
            'detail': ('反证组 2（minimvp 的 c13 默认改 True）实测 %s ⇒ 有鉴别力'
                       % ('FAIL（符合预期）' if not r_bad2['ok'] else 'PASS（判据恒真！）'))})
        shutil.rmtree(os.path.dirname(tmp_bad2), ignore_errors=True)
    else:
        checks.append({'name': 'counterexample2_must_fail', 'ok': False,
                       'detail': '改不动源码 ⇒ 判据无法证明有鉴别力'})

    ok = all(c['ok'] for c in checks)
    print('--- 行为级复核 ---')
    for c in checks:
        print('  %-52s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    ev = {
        'script': '_app137_profile_behavior_test.py',
        'task': 'APP-137 §1：package_profile 四个读取口的行为级复核（含反证组）',
        'cases': results,
        'checks': checks,
        'all_pass': ok,
        'note': ('🔴 **真跑**：每个用例都在临时「包根」里放一份 marker，'
                 '再 import 真的 `package_profile` ⇒ 断言的是**真跑出来的值**。'
                 'C 组（老 minimvp marker）承重：证明老包行为逐字不变。'),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('证据：%s' % EVIDENCE)
    print('ALL PASS' if ok else 'FAIL')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
