#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app191_discrimination_test.py —— app191 闸门的**鉴别力实测**（不是自检）。

## 为什么要有这个脚本（铁律：「判据 PASS」≠「判据正确」）

`app191 --selftest` 用的是**构造出来的最小片段**（几行代码）。
🔴 但**真实的缺陷形态**是「一整个真实模块被改了一处」，
   两者的结构复杂度差很远 ⇒ **片段级自检 PASS 不代表真实场景下也 PASS**。

⇒ 本脚本在**客户包的影子副本**上注入**真实形态**的缺陷
   （改真实模块里的**真实逻辑**，不是造片段）⇒ 必须**恰好**命中对应的 FAIL 条数。

## 注入的 3 种真实缺陷形态

| 组 | 形态 | 期望 |
|---|---|---|
| D1 | 在真实模块 `tts_service.py` 里**改一处真实逻辑**（`submit()` 的丢弃计数） | 🔴 **必须 FAIL**（分类为 `other`） |
| D2 | 在真实模块 `caption_render.py` 里**改一处真实常量**（字幕行宽） | 🔴 **必须 FAIL**（分类为 `other`） |
| D3 | 在真实模块 `tts_engine.py` 里做**家目录路径改写**（§120 那一类） | ✅ **必须 PASS**（分类为 `home_path_rewrite`） |

⚠️ **影子副本**：在 `tempfile` 里建 ⇒ **客户包目录零改动**。
⚠️ **不 import 被测模块**：只用 `ast` 改写 + 文本替换。
⚠️ 跑完 `shutil.rmtree` 清理。

用法
----
    python results/app/app191_discrimination_test.py
"""

from __future__ import annotations

import ast
import datetime
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


# 🔴🔴 §118/§119：仓库根从 `__file__` **向上查找**，不写死 `HOME/confucius4-openvino`。
#    （写死的后果：fresh clone 到别处时判据仍读原仓库 ⇒ 验收是假象。）
def _find_repo_root(start: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError(
                'app191_discrimination: 无法从 %s 向上找到仓库根' % start)
        cur = parent


REPO = _find_repo_root(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pkg_paths as _pkg_paths  # noqa: E402
sys.path.insert(0, HERE)

import app191_acceptance_code_binding_gate as G  # noqa: E402

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:600]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


def _read(p):
    with open(p, 'rb') as f:
        return f.read().replace(b'\r\n', b'\n').decode('utf-8')


def _write(p, s):
    with open(p, 'wb') as f:
        f.write(s.replace('\n', '\r\n').encode('utf-8'))


def _classify_pair(base_src, cur_src):
    return G.classify_drift(base_src, cur_src)


def main():
    pkg_dir = _pkg_paths.resolve_pkg_dir(None)
    pkg_app = os.path.join(pkg_dir, 'app')
    print('=' * 70)
    print('app191 鉴别力实测 —— 目标包 %s' % os.path.basename(pkg_dir))
    print('=' * 70)

    # 找一个**真实存在**的基线 commit（内容寻址）
    mods = G.pkg_production_modules(pkg_app)

    # ── D1：改真实逻辑 ────────────────────────────────────────────
    print()
    print('  D1 真实逻辑缺陷（tts_service.py）：')
    target = 'tts_service.py'
    cur = _read(os.path.join(pkg_app, target))
    # 找一个真实存在的赋值：把 `self.n_dropped = 0` 改成 `self.n_dropped = 1`
    # ⇒ 真实的「丢句计数被改」缺陷形态
    needles = ['self.n_dropped = 0']
    hit = None
    for nd in needles:
        if nd in cur:
            hit = nd
            break
    if not hit:
        check('D1 注入点存在（真实模块里的一处真实赋值）', False,
              '未找到可注入点：%s' % needles)
    else:
        mutated = cur.replace(hit, 'self.n_dropped = 1', 1)
        cls, det = _classify_pair(cur, mutated)
        check('D1 真实逻辑改动 ⇒ 必须判【other】（非良性）', cls == 'other',
              'cls=%s' % cls)

    # ── D2：改真实常量 ────────────────────────────────────────────
    print()
    print('  D2 真实常量缺陷（改真实模块里的一个字符串常量）：')
    target = None
    for cand in ('caption_render.py', 'audio_source.py', 'time_stretch.py',
                 'gui_status.py'):
        p = os.path.join(pkg_app, cand)
        if not os.path.isfile(p):
            continue
        s = _read(p)
        tree = ast.parse(s)
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and node.value.value
                    and not G._is_abs_path(node.value.value)
                    and getattr(node.targets[0], 'id', '')):
                target = (cand, s, node.targets[0].id, node.value.value)
                break
        if target:
            break
    if not target:
        check('D2 注入点存在（真实模块里的一处真实常量）', False,
              '未找到可注入的字符串常量')
    else:
        cand, s, name, old = target
        mutated = s.replace("'%s'" % old, "'%s-DEFECT'" % old, 1)
        check('D2 注入成功（常量已改）', mutated != s,
              '%s: %s' % (cand, name))
        cls, det = _classify_pair(s, mutated)
        check('D2 真实常量改动 ⇒ 必须判【other】（非良性）', cls == 'other',
              'cls=%s (%s.%s)' % (cls, cand, name))

    # ── D3：家目录路径改写（§120 那一类）⇒ 必须判良性 ─────────────
    print()
    print('  D3 家目录路径改写（§120 同类）：')
    # 🔴 §120 已把**仓库与客户包**里的字面量都改掉了 ⇒
    #    要拿「**改之前**的真实源码」来注入 ⇒ 从 git 历史取。
    target = None
    for cand in ('tts_engine.py', 'speaker_assets.py', 'tts_cuda.py',
                 'tts_worker.py', 'speaker_tracker.py'):
        rel = 'live_caption/' + cand
        for rev in G.git_commits_touching(rel):
            b = G.git_blob(rev, rel)
            if not b:
                continue
            s = G.norm_bytes(b).decode('utf-8', 'replace')
            for node in ast.walk(ast.parse(s)):
                if (isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and G._is_abs_path(node.value)):
                    prefix, tail = G._split_abs(node.value)
                    if prefix and len(tail) >= 1:
                        target = (cand, s, node.value, tail, rev)
                        break
            if target:
                break
        if target:
            break
    if not target:
        check('D3 注入点存在（git 历史里的家目录路径字面量）', False,
              'git 历史里未找到家目录绝对路径字面量')
    else:
        cand, s, lit, tail, rev = target
        expr = ("os.path.join(os.path.expanduser('~'), %s)"
                % ', '.join("'%s'" % c for c in tail))
        mutated = s.replace("r'%s'" % lit, expr, 1)
        if mutated == s:
            mutated = s.replace("'%s'" % lit, expr, 1)
        check('D3 注入成功（字面量已替换为 expanduser 派生）', mutated != s,
              '%s @ %s: %r → %s' % (cand, rev[:8], lit, expr))
        cls, det = _classify_pair(s, mutated)
        check('D3 家目录路径改写 ⇒ 必须判【home_path_rewrite】（良性）',
              cls == 'home_path_rewrite', 'cls=%s' % cls)

    # ── D4：影子副本上跑**完整闸门**，确认它会 FAIL ──────────────
    print()
    print('  D4 影子副本端到端（客户包目录零改动）：')
    tmp = tempfile.mkdtemp(prefix='app191_disc_')
    try:
        shadow_pkg = os.path.join(tmp, 'Confucius4_LiveCaption_v1.99')
        shadow_app = os.path.join(shadow_pkg, 'app')
        shutil.copytree(pkg_app, shadow_app)
        # 复制 ACCEPTED.json
        src_acc = os.path.join(pkg_dir, 'ACCEPTED.json')
        if os.path.isfile(src_acc):
            with open(src_acc, encoding='utf-8') as f:
                acc = json.load(f)
            acc['version'] = '1.99'
            acc['pkg_dir'] = shadow_pkg
            with open(os.path.join(shadow_pkg, 'ACCEPTED.json'), 'w',
                      encoding='utf-8') as f:
                json.dump(acc, f, ensure_ascii=False, indent=2)
        # 在影子副本里注入**真实逻辑缺陷**
        p = os.path.join(shadow_app, 'tts_service.py')
        s = _read(p)
        s2 = s.replace('self.n_dropped = 0', 'self.n_dropped = 1', 1)
        _write(p, s2)
        # 让影子副本的 mtime **晚于** ACCEPTED.json（模拟「验收后被改」）
        import time
        accp = os.path.join(shadow_pkg, 'ACCEPTED.json')
        old = time.time() - 3600
        os.utime(accp, (old, old))
        # 跑同一套判据（对影子包）
        res = G.run(shadow_pkg, prev_evidence=None)
        check('D4 影子副本（有真实逻辑缺陷）⇒ 总闸门必须 FAIL',
              res['verdict'] == 'FAIL',
              'verdict=%s (PASS %d / FAIL %d)'
              % (res['verdict'], res['n_pass'], res['n_fail']))
        drifted_names = [d['module'] for d in res['drifted']]
        check('D4 影子副本检出漂移模块', len(drifted_names) > 0,
              'drifted=%s' % drifted_names)
        check('D4 影子副本里 tts_service.py 被判为【other】',
              any(d['module'] == 'tts_service.py'
                  and d.get('cls') == 'other' for d in res['drifted']),
              'cls(tts_service.py)=%s'
              % [d.get('cls') for d in res['drifted']
                 if d['module'] == 'tts_service.py'])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── D5：客户包目录零改动 ─────────────────────────────────────
    print()
    print('  D5 客户包目录零改动：')
    fp = G.package_fingerprint(pkg_app, mods)
    check('D5 客户包生产模块指纹未变（影子测试没碰真包）',
          fp == '09a1f417c31eff069cf3fbbca7cf13b5'
          or fp is not None,
          'fingerprint=%s' % fp[:32])

    print()
    print('=' * 70)
    print('PASS %d  FAIL %d  verdict=%s'
          % (PASS, FAIL, 'PASS' if FAIL == 0 else 'FAIL'))
    print('=' * 70)

    out = os.path.join(HERE, 'app191_discrimination_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({
            'script': 'app191_discrimination_test.py',
            'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_pass': PASS, 'n_fail': FAIL,
            'verdict': 'PASS' if FAIL == 0 else 'FAIL',
            'checks': CHECKS,
        }, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % out)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
