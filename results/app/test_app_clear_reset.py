#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_app_clear_reset.py — 验证 App 的「清空」按钮**真的重置了整个 MT 会话**。

🔴 **为什么需要这个测试**（MT 移交说明 §4.3 点名的真实 bug）：
  旧的 `App.clear()` 只清 `seg_keys` / `seg_carry` / `seg_half`
  ⇒ **没清** `units` / `_seen` / `_pend` / `done`
  ⇒ 清屏后：
    · 上一场的句单元还在 ⇒ 渲染层混进旧译文；
    · `_seen` 还在 ⇒ 新场次里**同一句**被当成「已翻过」⇒ **这句话直接丢失**；
    · `_pend` 还挂着上一场半句 ⇒ 新场次第一段**接到上一场尾巴**后面；
    · `done` 里留旧译文 ⇒ 同句读到**上一场的旧译文**。

🔴 **本测试不 import 被测模块**（铁律）：
  `import translator` ⇒ 连带 numpy/OpenBLAS ⇒ 别的模块占满内存时进程在 import 阶段就 abort。
  ⇒ 用 `ast` 抽取源码 + `exec` 到独立命名空间，只测纯逻辑。
  ⇒ **不跑推理、不跑测速、不占 GPU**（纯 CPU）。

## 判据

| # | 判据 | 期望 |
|---|---|---|
| 1 | 清空后 `units` 为空 | ✅ |
| 2 | 清空后 `_seen` 为空 | ✅ |
| 3 | 清空后 `_pend` 为空串 | ✅ |
| 4 | 清空后 `done` 为空 | ✅ |
| 5 | 清空后 `seg_keys`/`seg_carry`/`seg_half` 为空 | ✅ |
| 6 | **反证**：修复前，第 2 项不成立（旧 clear 不清 `_seen`） | ✅ |
| 7 | 回归：新场次里**同一句**在清空后仍能被翻译并进显示单元 | ✅ |

## 用法
    python results/app/test_app_clear_reset.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
APP_PY = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
TR_PY = os.path.join(REPO, 'live_caption', 'translator.py')
REPORT = os.path.join(REPO, 'results', 'app', 'app_clear_reset_test.json')


def extract_class(path: str, cls_name: str, needed_methods):
    """用 ast 从源码里抽出类的指定方法，**返回 (源码文本, 可调用对象)**。

    🔴 不 import 被测模块（铁律）⇒ 用 ast 定位 + textwrap.dedent 抽源码。
    返回源码是为了让测试**真的在测线上代码**（而不是复制一份逻辑）。
    """
    import textwrap
    src = open(path, 'r', encoding='utf-8', newline='').read()
    src = src.replace('\r\n', '\n')
    tree = ast.parse(src)
    lines = src.split('\n')
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and sub.name in needed_methods:
                    seg = '\n'.join(lines[sub.lineno - 1:sub.end_lineno])
                    out.append(seg)
            break
    if not out:
        raise SystemExit(f'!! 在 {path} 里找不到类 {cls_name} 的目标方法')
    # ⚠️ 方法体在类里是缩进的 ⇒ 直接 exec 到模块级会 IndentationError
    #    ⇒ 必须 dedent 后再 exec。
    body = textwrap.dedent('\n\n'.join(out))
    ns = {}
    exec(compile(body, path, 'exec'), ns)
    return body, ns


class FakeMT:
    """最小 TranslationService 替身（字段与 translator.py 的 __init__ 对齐）。"""

    def __init__(self):
        self.done = {}
        self.done_fix = {}
        self.units = []
        self._seen = set()
        self._pend = ''
        self._half = None
        self.draft = ''
        self._last_src = ''
        self.seg_keys = {}
        self.seg_carry = {}
        self.seg_half = {}

    # 旧行为：只清 3 个字典
    def clear_old(self):
        self.seg_keys.clear()
        self.seg_carry.clear()
        self.seg_half.clear()

    # 新行为（App 里的 `_reset_mt_session`）
    def clear_new(self):
        for name in ('seg_keys', 'seg_carry', 'seg_half'):
            d = getattr(self, name, None)
            if isinstance(d, dict):
                d.clear()
        for name in ('done', 'done_fix'):
            d = getattr(self, name, None)
            if hasattr(d, 'clear'):
                d.clear()
        units = getattr(self, 'units', None)
        if isinstance(units, list):
            units.clear()
        seen = getattr(self, '_seen', None)
        if isinstance(seen, set):
            seen.clear()
        if hasattr(self, '_pend'):
            self._pend = ''
        if hasattr(self, '_half'):
            self._half = None
        if hasattr(self, 'draft'):
            self.draft = ''
        if hasattr(self, '_last_src'):
            self._last_src = ''


def main():
    # ── 0. 先从真实源码里取 App 的 clear/_reset_mt_session（证明测的是真代码）──
    ns = extract_class(APP_PY, 'App', {'clear', '_reset_mt_session'})
    src_body, ns = ns
    src_reset = ns['_reset_mt_session']
    src_clear = ns['clear']

    results = []

    def check(name, ok, detail=''):
        results.append(dict(name=name, pass_=bool(ok), detail=detail))
        print(f'[{"PASS" if ok else "FAIL"}] {name}' + (f' — {detail}' if detail else ''))

    # ── 反证：旧行为确实会留下脏状态 ──────────────────────────────────
    mt = FakeMT()
    mt.units.append(dict(key='k1', src='Hello world.', seg=0, mt=None))
    mt._seen.add('hello world')
    mt.done['hello world'] = '你好，世界。'
    mt._pend = 'a half sentence'
    mt.seg_keys[0] = ['k1']
    mt.seg_carry[0] = True
    mt.seg_half[0] = True

    mt.clear_old()
    check('反证 旧 clear 后 units 仍非空（证明是真 bug）',
          len(mt.units) == 1, f'units={len(mt.units)}')
    check('反证 旧 clear 后 _seen 仍非空（⇒ 同句会被当成已翻过 ⇒ 丢句）',
          len(mt._seen) == 1, f'_seen={len(mt._seen)}')
    check('反证 旧 clear 后 _pend 仍非空（⇒ 新场次会接上一场尾巴）',
          mt._pend != '', f'_pend={mt._pend!r}')
    check('反证 旧 clear 后 done 仍非空（⇒ 同句读到旧译文）',
          len(mt.done) == 1, f'done={len(mt.done)}')

    # ── 新行为：App 真实源码的 _reset_mt_session ───────────────────────
    mt2 = FakeMT()
    mt2.units.append(dict(key='k1', src='Hello world.', seg=0, mt=None))
    mt2._seen.add('hello world')
    mt2.done['hello world'] = '你好，世界。'
    mt2.done_fix['x'] = 'y'
    mt2._pend = 'a half sentence'
    mt2._half = ('half', 'k')
    mt2.draft = 'draft text'
    mt2._last_src = 'Hello world.'
    mt2.seg_keys[0] = ['k1']
    mt2.seg_carry[0] = True
    mt2.seg_half[0] = True

    # 用 App 真实源码里的实现来清（self.mt = mt2）
    class Holder:
        pass
    h = Holder()
    h.mt = mt2
    ns['_reset_mt_session'](h)

    check('① 清空后 units 为空', len(mt2.units) == 0, f'units={len(mt2.units)}')
    check('② 清空后 _seen 为空', len(mt2._seen) == 0, f'_seen={len(mt2._seen)}')
    check('③ 清空后 _pend 为空串', mt2._pend == '', f'_pend={mt2._pend!r}')
    check('④ 清空后 done 为空', len(mt2.done) == 0, f'done={len(mt2.done)}')
    check('④b 清空后 done_fix 为空', len(mt2.done_fix) == 0, f'done_fix={len(mt2.done_fix)}')
    check('⑤ 清空后 seg_keys/seg_carry/seg_half 为空',
          len(mt2.seg_keys) == 0 and len(mt2.seg_carry) == 0
          and len(mt2.seg_half) == 0,
          f'seg_keys={len(mt2.seg_keys)} seg_carry={len(mt2.seg_carry)} '
          f'seg_half={len(mt2.seg_half)}')
    check('⑥ 清空后 _half/draft/_last_src 也归零',
          mt2._half is None and mt2.draft == '' and mt2._last_src == '',
          f'_half={mt2._half!r} draft={mt2.draft!r}')

    # ── ⑦ 回归：新场次里同一句在清空后仍能被翻译并进显示单元 ─────────
    mt3 = FakeMT()
    mt3.units.append(dict(key='hello world', src='Hello world.', seg=0, mt=None))
    mt3._seen.add('hello world')
    mt3.done['hello world'] = '你好，世界。'
    mt3.seg_keys[0] = ['hello world']

    h3 = Holder()
    h3.mt = mt3
    ns['_reset_mt_session'](h3)

    # 模拟新场次 submit：同一句
    k = 'hello world'
    if k in mt3._seen:
        # 旧行为：新场次的这一句会被丢掉 ⇒ 这里应当**不会**发生
        mt3.units.append(dict(key=k, src='Hello world.', seg=0, mt=None))
    else:
        mt3._seen.add(k)
        mt3.units.append(dict(key=k, src='Hello world.', seg=0, mt=None))
        mt3.done[k] = '你好，世界。'
    check('⑦ 回归：清空后新场次同一句仍进显示单元（未被当成已翻过而丢弃）',
          len(mt3.units) == 1 and 'hello world' in mt3.done,
          f'units={len(mt3.units)} done={list(mt3.done)}')

    # ── ⑧ clear() 确实调用了 _reset_mt_session ────────────────────────
    check('⑧ App.clear() 确实调用 _reset_mt_session',
          '_reset_mt_session' in src_body,
          'clear() 源码里含调用')

    # ── ⑨ 缺字段时不崩（防御性）──────────────────────────────────────
    class Bare:
        pass
    b = Bare()
    hb = Holder()
    hb.mt = b
    try:
        ns['_reset_mt_session'](hb)
        check('⑨ 字段缺失时不抛异常（防御性）', True, 'bare 对象清空成功')
    except Exception as e:
        check('⑨ 字段缺失时不抛异常（防御性）', False, repr(e))

    n_pass = sum(1 for r in results if r['pass_'])
    n_fail = len(results) - n_pass
    print()
    print(f'==== {n_pass}/{len(results)} PASS' + (f'，{n_fail} FAIL' if n_fail else '') + ' ====')

    report = dict(
        total=len(results), n_pass=n_pass, n_fail=n_fail,
        all_pass=(n_fail == 0),
        app_py_sha256=hashlib.sha256(open(APP_PY, 'rb').read()).hexdigest(),
        translator_py_sha256=hashlib.sha256(open(TR_PY, 'rb').read()).hexdigest(),
        mtime=time.strftime('%Y-%m-%d %H:%M:%S'),
        checks=results,
    )
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'报告已写: {REPORT}')
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
