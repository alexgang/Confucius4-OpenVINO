# -*- coding: utf-8 -*-
"""🔴 静态判据：开发期 `assert_*.py` 闸门**绝不能**进客户包（`assert_pkg_clean.py` 除外）。

## 背景（§173 ⑥ 留下的「下一轮必读」项）

> 「**v2.5 建包时别把 `assert_*.py` 带进 `app/`**（`pkg_exclude` 只排 `_` 前缀；
>   但 `assert_pkg_clean.py` 是**必须随包**的例外）」

⇒ 修之前的 `pkg_exclude.is_app_dev_only()` **只**认「`_` 前缀」⇒
   开发期闸门 `assert_sec_per_char_calibrated.py` / `assert_status_citations.py` /
   `assert_window_same_source.py` **不在排除范围** ⇒
   **只要建包脚本把它们拷进 `app/`，它们就会进 zip** ⇒ **开发机路径泄漏**
   （例：`results/app/app326_app097_lang_out/tts.json`、`status/app/STATUS_APP.md`）。

## 本脚本做三件事

1. **A 组（行为级真跑）**：真调 `pkg_exclude.is_app_dev_only()` / `is_excluded()`
   ⇒ 三个开发闸门**必须**判 True（排除）；`assert_pkg_clean.py` **必须**判 False（随包）。
2. **B 组（真实包反查）**：扫**已存在的每个客户包**的 `app/` 目录 ⇒
   除 `assert_pkg_clean.py` 外**不得**出现任何 `assert_*.py`。
3. **C 组（反证组）**：把例外名单**故意做掉**（把 `assert_pkg_clean.py` 加进排除）
   ⇒ A 组**必须** FAIL ⇒ 证明判据有鉴别力。

⚠️ **不 import 被测包内代码** ⇒ 只读目录 + 调 `pkg_exclude`（仓库侧单一数据源）。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import pkg_exclude as pe  # noqa: E402

#: 开发期闸门（**必须**排除）—— 名字取自 dev 树 `live_caption/` 实有文件
DEV_GATES = [
    'assert_sec_per_char_calibrated.py',
    'assert_status_citations.py',
    'assert_window_same_source.py',
]
#: 必须随包（**不得**排除）
MUST_SHIP = 'assert_pkg_clean.py'

#: 已存在的客户包根目录（扫描 `app/` 下的 `assert_*`）
PKG_ROOTS = [
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.3',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc5',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc6',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc7',
]


def check_a():
    """A 组：真调判据。"""
    checks = []

    def add(cid, name, ok, got, want):
        checks.append({'id': cid, 'group': 'A', 'name': name,
                       'ok': bool(ok), 'got': got, 'want': want})

    for i, f in enumerate(DEV_GATES, 1):
        rel = 'app/' + f
        got = pe.is_app_dev_only(rel)
        add('A%d' % i, 'is_app_dev_only(%s) == True（开发闸门须排除）' % rel,
            got is True, got, True)
    # `is_excluded()` 也必须判 True（zip 清单走的是它 ⇒ 两条路都要堵）
    got_x = pe.is_excluded('app/' + DEV_GATES[0])
    add('A4', 'is_excluded(app/%s) == True' % DEV_GATES[0],
        got_x is True, got_x, True)
    # 必须随包的那个**不得**被排除
    got_k = pe.is_app_dev_only('app/' + MUST_SHIP)
    add('A5', 'is_app_dev_only(app/%s) == False（必须随包）' % MUST_SHIP,
        got_k is False, got_k, False)
    # 随包的那个也**不得**被 `is_excluded` 排除
    got_kx = pe.is_excluded('app/' + MUST_SHIP)
    add('A6', 'is_excluded(app/%s) == False（必须随包）' % MUST_SHIP,
        got_kx is False, got_kx, False)
    return checks


def check_b():
    """B 组：扫已存在的客户包 `app/` 目录。"""
    checks = []
    for i, root in enumerate(PKG_ROOTS, 1):
        app = os.path.join(root, 'app')
        if not os.path.isdir(app):
            checks.append({'id': 'B%d' % i, 'group': 'B',
                           'name': '客户包 %s 存在' % os.path.basename(root),
                           'ok': True, 'got': 'absent', 'want': 'absent'})
            continue
        found = sorted(f for f in os.listdir(app)
                       if f.lower().startswith('assert')
                       and f.lower().endswith('.py'))
        bad = [f for f in found if f != MUST_SHIP]
        checks.append({'id': 'B%d' % i, 'group': 'B',
                       'name': ('客户包 %s/app 下无开发闸门（只允许 %s）'
                                % (os.path.basename(root), MUST_SHIP)),
                       'ok': not bad, 'got': found, 'want': [MUST_SHIP]})
    return checks


def check_c():
    """C 组：反证 —— 把例外名单做掉 ⇒ A5/A6 必须 FAIL。"""
    checks = []
    keep = pe.APP_DEV_ONLY_ASSERT_KEEP
    try:
        # 反证：把 `assert_pkg_clean.py` 也排除掉（= 错误做法）
        pe.APP_DEV_ONLY_ASSERT_KEEP = frozenset()
        got = pe.is_app_dev_only('app/' + MUST_SHIP)
        checks.append({'id': 'C1', 'group': 'C',
                       'name': '反证：例外名单被做掉 ⇒ assert_pkg_clean 必须 FAIL',
                       'ok': got is True, 'got': got, 'want': True})
        # 反证：把例外名单**放大**（误排除 assert_pkg_clean）
        pe.APP_DEV_ONLY_ASSERT_KEEP = frozenset()
        got2 = pe.is_excluded('app/' + MUST_SHIP)
        checks.append({'id': 'C2', 'group': 'C',
                       'name': '反证：例外名单被做掉 ⇒ is_excluded 必须 True',
                       'ok': got2 is True, 'got': got2, 'want': True})
    finally:
        pe.APP_DEV_ONLY_ASSERT_KEEP = keep
    return checks


def main():
    checks = check_a() + check_b() + check_c()
    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'task': 'App 侧打包卫生：开发期 assert_*.py 闸门不得进客户包（assert_pkg_clean 除外）',
        'repo': REPO,
        'criterion': 'behavior-level (真调 pkg_exclude.is_app_dev_only / is_excluded + 扫真实包目录)',
        'dev_gates': DEV_GATES,
        'must_ship': MUST_SHIP,
        'pass_count': n_pass, 'fail_count': n_fail, 'total': len(checks),
        'checks': checks,
    }
    dst = os.path.join(REPO, 'results', 'app',
                       'app433_pkg_dev_only_assert_gate.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('[app433] pkg dev-only assert gate: %d PASS / %d FAIL -> %s'
          % (n_pass, n_fail, dst))
    for c in checks:
        print('  [%s] %-4s %s  got=%r' % ('OK ' if c['ok'] else 'FAIL',
                                          c['id'], c['name'][:66], c['got']))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
