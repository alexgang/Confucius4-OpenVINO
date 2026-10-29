# -*- coding: utf-8 -*-
"""🔴 验收：**打包版本号自动递增**（2026-10-29 用户决定）。

用户原话：「每次打新包的时候自动升级版本好，不要一直沿用旧版本号」。

## 为什么必须自动

旧做法 `PKG_VERSION = '1.6'` 写死 ⇒ 一连十几轮都叫 v1.6：
  ① 分不清用户手里那份是哪次打的；
  ② 新包**原地覆盖**旧 v1.6 zip ⇒ 想回滚时旧包已经没了；
  ③ STATUS 里「已交付」写同一个版本号 ⇒ 事后对不上时间线。

## 实现（`pack_v13.py`）

- `discover_max_version()`：扫 `Confucius4_LiveCaption_vX.Y`（**目录与 zip 都算**）⇒ 取最大；
- `bump_version()`：**minor + 1**（用**元组**比较 ⇒ `1.9 ⇒ 1.10` 不会踩字符串排序的坑）；
- `VERSION_FLOOR`：推算结果不低于历史基线；
- CLI：`--version X.Y` 显式指定 / `--same-version` 覆盖重打（失败重试不该白吃版本号）；
- `--rename-pkg-dir`（默认开）：版本号变了 ⇒ 源目录**同卷改名**
  ⇒ 保证「目录版本 == zip 版本 == MANIFEST version」三者一致。

🔴 **不 `import` 被测模块**（避免顶层副作用）⇒ `ast` 抽函数 + `exec`。
"""
from __future__ import annotations

import ast
import io
import json
import os
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, 'pack_v13.py')

N_OK = N_FAIL = 0
ROWS = []


def check(group, name, ok, detail=''):
    global N_OK, N_FAIL
    ok = bool(ok)
    N_OK, N_FAIL = (N_OK + 1, N_FAIL) if ok else (N_OK, N_FAIL + 1)
    ROWS.append({'group': group, 'name': name, 'ok': ok, 'detail': str(detail)[:300]})
    print('  [%s] %s %s  <- %s' % (group, 'PASS' if ok else 'FAIL', name,
                                   str(detail)[:160]))


def load_version_api(src):
    tree = ast.parse(src)
    ns = {'os': os, 're': __import__('re'), 'VERSION_FLOOR': None,
          'HOME_DIR': ''}
    want = {'_ver_key', 'discover_max_version', 'bump_version', '_names_for'}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in want:
            exec(compile(ast.Module(body=[n], type_ignores=[]), 'pack_v13', 'exec'), ns)
    return ns


def make_root(entries):
    """造一个临时「HOME」，里面放若干**（空）目录 / 空 zip 文件**。"""
    d = tempfile.mkdtemp(prefix='app138_home_')
    for name in entries:
        p = os.path.join(d, name)
        if name.endswith('.zip'):
            open(p, 'wb').close()
        else:
            os.makedirs(p, exist_ok=True)
    return d


def main():
    src = io.open(SRC, encoding='utf-8').read()
    ns = load_version_api(src)
    discover, bump = ns['discover_max_version'], ns['bump_version']
    names_for = ns['_names_for']

    print('=' * 74)
    print('打包版本号自动递增 —— 验收')
    print('=' * 74)

    # ── REAL ────────────────────────────────────────────────────────
    check('REAL', 'R1 三个函数都抽到了',
          callable(discover) and callable(bump) and callable(names_for),
          'ok')

    r1 = make_root(['Confucius4_LiveCaption_v1.6',
                    'Confucius4_LiveCaption_v1.6.zip'])
    check('REAL', 'R2 现存 v1.6 ⇒ 自动升到 1.7',
          discover(r1, '1.0') == '1.6' and bump(r1, '1.0') == '1.7',
          'max=%s bump=%s' % (discover(r1, '1.0'), bump(r1, '1.0')))

    r2 = make_root(['Confucius4_LiveCaption_v1.6',
                    'Confucius4_LiveCaption_v1.7',
                    'Confucius4_LiveCaption_v1.7.zip'])
    check('REAL', 'R3 现存 v1.7 ⇒ 再翻倍 rounds ⇒ 1.8（不重复已用过的号）',
          bump(r2, '1.0') == '1.8', 'bump=%s' % bump(r2, '1.0'))

    r3 = make_root(['Confucius4_LiveCaption_v1.9.zip'])
    check('REAL', 'R4 1.9 ⇒ 1.10（元组比较，不是字符串排序）',
          bump(r3, '1.0') == '1.10', 'bump=%s' % bump(r3, '1.0'))

    r4 = make_root([])
    check('REAL', 'R5 空目录 ⇒ 落到 VERSION_FLOOR 的下一个版本',
          bump(r4, '1.6') == '1.7', 'bump=%s' % bump(r4, '1.6'))

    r5 = make_root(['Confucius4_LiveCaption_v1.0.bak_20261020',
                    'Confucius4_LiveCaption_v1.6'])
    check('REAL', 'R6 带后缀的备份目录也按版本识别（不 > 1.6）',
          discover(r5, '1.0') == '1.6', 'max=%s' % discover(r5, '1.0'))

    d, z, pre = names_for('1.7')
    check('REAL', 'R7 目录 / zip / 前缀三者同版本',
          d.endswith('Confucius4_LiveCaption_v1.7.zip'.replace('.zip', ''))
          and z.endswith('Confucius4_LiveCaption_v1.7.zip')
          and pre == 'Confucius4_LiveCaption_v1.7',
          'dir=%s zip=%s prefix=%s' % (os.path.basename(d), os.path.basename(z), pre))

    # 真实源码：MANIFEST 的 version 必须来自同一全局变量
    tree = ast.parse(src)
    # ⚠️ 目标可能是 **Subscript**（`data['version'] = ...`），不是 Attribute/Name
    #   ⇒ 只按命名查会漏（本轮首跑就漏了 ⇒ 属**判据缺陷**，不是产品缺陷）
    wrote = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            is_ver_key = ((getattr(t, 'attr', '') == 'version')
                          or (getattr(t, 'id', '') == 'version')
                          or (isinstance(t, ast.Subscript)
                              and isinstance(t.slice, ast.Constant)
                              and t.slice.value == 'version'))
            if is_ver_key:
                wrote.append(n)
    srcs = [ast.get_source_segment(src, n) for n in wrote]
    check('REAL', 'R8 MANIFEST 的 version 由 PKG_VERSION 写入（不是手填常量）',
          any('PKG_VERSION' in (s or '') for s in srcs),
          'assigns=%r' % (srcs,))

    check('REAL', 'R9 PKG_VERSION 不再是写死的字符串常量',
          "PKG_VERSION = '" not in src and 'PKG_VERSION = bump_version' in src,
          'ok')

    # ── BUG（缺陷仍在 ⇒ 命中即 FAIL）────────────────────────────────
    check('BUG', 'B1 版本号写死（旧行为）', 'PKG_VERSION = bump_version' in src,
          'ok')
    check('BUG', 'B2 bump 用字符串比较（1.9 ⇒ 1.10 会错）',
          bump(r3, '1.0') == '1.10', 'bump=%s' % bump(r3, '1.0'))
    check('BUG', 'B3 只看目录、看不到 zip ⇒ 已发布的版本号会被重用',
          os.path.exists(os.path.join(r2, 'Confucius4_LiveCaption_v1.7.zip'))
          and bump(r2, '1.0') == '1.8', 'ok')

    verdict = 'PASS' if N_FAIL == 0 else 'FAIL'
    print('\n结果：%d PASS / %d FAIL ｜ verdict=%s' % (N_OK, N_FAIL, verdict))
    out = os.path.join(HERE, 'app138_pack_version_autobump_evidence.json')
    io.open(out, 'w', encoding='utf-8').write(json.dumps(
        {'script': os.path.basename(__file__), 'n_pass': N_OK, 'n_fail': N_FAIL,
         'verdict': verdict, 'rows': ROWS,
         'time': time.strftime('%Y-%m-%d %H:%M:%S')},
        ensure_ascii=False, indent=1))
    print('证据落盘：%s' % out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
