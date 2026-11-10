#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app334_fix_gui_init_indent.py —— 修 APP-093 §3.7 的**阻断级根因**：
GUI 布局代码被误吞进 `App._clone_nearest` 方法体。

## 根因（读码 + ast 定案）

`commit 874924a`（APP-086(2) 接入 clone 策略层）把
`def _clone_nearest(self, seg, spk, sim):` **插进了 `App.__init__` 的中间**：

```
class App:
    def __init__(self, root, args):        # ← 本应到这里结束于 2292 行
        ...
        self._clone_pol = clone_voice.CloneVoices(..., on_nearest=self._clone_nearest)
                                        # ← 874924a 在这里插了 def
    def _capture_self_ref_pcm(...)         # 三个方法（2294-2387）
    def _reset_clone_session(...)
    def _clone_nearest(self, seg, spk, sim):   # 2389
        <docstring>
        try: ...spk_update_seg...          # 2397-2406（**本方法真正的全部**）
        except Exception as e: ...
        # ↓↓↓ 2407-3157：**原本属于 __init__ 的 GUI 布局代码**
        #        （root.title / root.geometry / 控件构建 / prewarm / load_engine）
        #        ⇒ 被吞进本方法体 ⇒ **运行时永不执行**
```

⇒ `App.__init__` 的 ast 范围只有 **2205-2292（88 行）**，
   而 `root.title()`（2468 行）落在 `_clone_nearest`（2389-3157）体内。

⇒ **后果（实测）**：GUI 只剩一个空的 `tk` 200×200 窗口
   - 无标题（`root.title()` 没执行）
   - 无控件（`_build_ui` 等整段没执行）
   - 引擎从不加载（`self.load_engine()` 没执行）⇒ **字幕永不出现**
   ⇒ APP-093 §3.7「截一张有三行字幕的图」**在结构上不可能成功**。

## 修法（**只搬移，不改写**）

把 **2407-3157 整块**（原本属于 `__init__` 的部分）**搬回 `__init__` 末尾**，
`_clone_nearest` 只保留它本来的 `try/except`（2397-2406）。

```
class App:
    def __init__(self, root, args):
        <2206-2292 原样>
        <2407-3157 原样搬回>          # ← 本次搬移
    def _capture_self_ref_pcm(...)
    def _maybe_send_self_ref(...)
    def _reset_clone_session(...)
    def _clone_nearest(self, seg, spk, sim):   # 只剩 try/except
```

⚠️ **只搬移整块 ⇒ 每一行内容逐字未变** ⇒ 无语义改动风险。
   搬移后 `__init__` 里 `args` 参数重新可见（2407+ 段用到 `args.tts_voice`，
   在 `_clone_nearest` 里其实是 **NameError**（未定义的局部名））。

## 校验（全部必须通过）

1. `ast.parse` 成功
2. `App.__init__` 的 ast 范围覆盖到 `root.title(...)` 那一行
3. `root.title(...)` / `root.geometry(...)` 的**最内层归属函数** == `__init__`
4. `_clone_nearest` 的 ast 范围 == 仅 try/except（≤ 30 行）
5. **常量多重集不变**（证明没有丢/改任何字面量）
6. **语句多重集不变**（去位置后比对，证明只有搬移没有改写）
7. 行数不变（只搬移 ⇒ 行数守恒）
8. 行尾风格不变（LF）

## 用法
```
.venv/Scripts/python.exe results/app/_app334_fix_gui_init_indent.py --file <path> [--apply]
```
默认只做**试算 + 校验**（不写文件）；加 `--apply` 才落盘。
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
OUT = os.path.join(REPO, 'results', 'app',
                   'app334_app093_gui_init_indent_fix.json')


def find_app_methods(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'App':
            out = {}
            for m in node.body:
                if isinstance(m, ast.FunctionDef):
                    out[m.name] = m
            return out
    return {}


def owner_of_line(tree, lineno):
    """返回**最内层**包含该行的函数名。"""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.lineno <= lineno <= node.end_lineno:
                if best is None or node.lineno > best.lineno:
                    best = node
    return best.name if best else None


def const_multiset(tree):
    c = collections.Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            c[(type(node.value).__name__, repr(node.value))] += 1
    return c


def stmt_multiset(tree):
    """语句多重集。

    🔴 **必须排除** FunctionDef / AsyncFunctionDef / ClassDef / Module
       —— 它们的 `ast.dump` **内嵌整个函数体**
       ⇒ 搬移后必然变化 ⇒ 会把「纯搬移」误判成「改写」。
    ⇒ 只统计**不含嵌套函数体**的语句。
    """
    skip = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
    c = collections.Counter()
    for node in ast.walk(tree):
        if isinstance(node, skip):
            continue
        if isinstance(node, ast.stmt):
            c[ast.dump(node, annotate_fields=False)] += 1
    return c


def call_sites(tree):
    """返回 [(func_attr, arg_repr, lineno)]，只看 title/geometry。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ('title', 'geometry'):
            try:
                arg = ast.unparse(node.args[0]) if node.args else ''
            except Exception:
                arg = '?'
            out.append((node.func.attr, arg, node.lineno))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    path = args.file
    raw = open(path, 'rb').read()
    text = raw.decode('utf-8')
    eol = '\r\n' if b'\r\n' in raw else '\n'
    lines = text.split('\n')
    trailing_nl = lines[-1] == ''
    if trailing_nl:
        lines = lines[:-1]

    tree = ast.parse(text)
    meth = find_app_methods(tree)
    init = meth.get('__init__')
    cn = meth.get('_clone_nearest')
    rep = {'file': path, 'bytes_before': len(raw), 'eol': 'CRLF' if eol == '\r\n' else 'LF',
           'lines_before': len(lines)}

    if init is None or cn is None:
        rep['verdict'] = 'FAIL_NO_METHOD'
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 2

    rep['init_range_before'] = [init.lineno, init.end_lineno]
    rep['clone_nearest_range_before'] = [cn.lineno, cn.end_lineno]
    rep['init_len_before'] = init.end_lineno - init.lineno + 1

    # ── 定位 `_clone_nearest` 里**真正的**方法体末尾
    #    ⚠️ 不能用「遍历所有 ExceptHandler 取 max」——**被吞进本方法的
    #       `__init__` 尾部代码里也有 except handler** ⇒ max 会跑到 3155。
    #    ⇒ 正确口径：`_clone_nearest` 的**直接**子语句序列 =
    #       [docstring(Expr), Try(2397-2406), <被吞的 __init__ 语句…>]
    #       ⇒ **第 2 条直接语句（Try）的 end_lineno** 才是本方法真正的末尾。
    if len(cn.body) < 2 or not isinstance(cn.body[1], ast.Try):
        rep['verdict'] = 'FAIL_UNEXPECTED_SHAPE'
        rep['cn_body_types'] = [type(s).__name__ for s in cn.body[:6]]
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 2
    last_stmt_end = cn.body[1].end_lineno
    rep['clone_real_body_end'] = last_stmt_end
    rep['cn_direct_stmt_count'] = len(cn.body)

    init_end = init.end_lineno            # 2292
    cn_start = cn.lineno                 # 2389
    cn_real_end = last_stmt_end           # 2406
    block_a = (cn_real_end + 1, cn.end_lineno)   # 2407..3157（搬回 __init__）

    rep['block_a_moved'] = list(block_a)
    rep['block_a_first_line'] = lines[block_a[0] - 1][:90]
    rep['block_a_last_line'] = lines[block_a[1] - 1][:90]

    # ── 搬移（只搬移，行内容逐字不变）
    new_lines = (lines[:init_end]
                 + lines[block_a[0] - 1: block_a[1]]
                 + lines[init_end: block_a[0] - 1]
                 + lines[block_a[1]:])
    rep['lines_after'] = len(new_lines)
    rep['lines_ conserved'] = (len(new_lines) == len(lines))

    new_text = '\n'.join(new_lines) + ('\n' if trailing_nl else '')
    new_raw = new_text.encode('utf-8')

    # ── 校验
    checks = {}
    try:
        new_tree = ast.parse(new_text)
        checks['ast_parse'] = True
    except SyntaxError as exc:
        rep['verdict'] = 'FAIL_AST'
        rep['error'] = repr(exc)
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 3

    nm = find_app_methods(new_tree)
    ninit, ncn = nm.get('__init__'), nm.get('_clone_nearest')
    rep['init_range_after'] = [ninit.lineno, ninit.end_lineno]
    rep['clone_nearest_range_after'] = [ncn.lineno, ncn.end_lineno]

    # 🔴 搬移后行号会变 ⇒ **不能**再硬编码 2468
    #    ⇒ 改为：找到 title/geometry 的调用点，验证其**最内层归属函数**是 __init__
    title_owners = []
    for a, b, c in call_sites(new_tree):
        if a == 'title':
            title_owners.append((c, owner_of_line(new_tree, c)))
    rep['title_call_owners_after'] = title_owners
    checks['title_owned_by_init'] = bool(title_owners) and all(
        o == '__init__' for _, o in title_owners)
    checks['init_covers_title_line'] = bool(title_owners) and all(
        ninit.lineno <= ln <= ninit.end_lineno for ln, _ in title_owners)
    checks['clone_nearest_small'] = (ncn.end_lineno - ncn.lineno + 1) <= 30
    checks['const_multiset_same'] = (const_multiset(tree) == const_multiset(new_tree))
    checks['stmt_multiset_same'] = (stmt_multiset(tree) == stmt_multiset(new_tree))
    checks['line_count_same'] = (len(new_lines) == len(lines))
    checks['eol_preserved'] = (b'\r\n' not in new_raw) == (b'\r\n' not in raw)

    # 调用点表（title/geometry 的归属函数）
    rep['call_sites_after'] = [
        {'call': a, 'arg': b, 'line': c,
         'owner': owner_of_line(new_tree, c)}
        for a, b, c in call_sites(new_tree)]

    rep['checks'] = checks
    rep['all_checks_pass'] = all(checks.values())
    rep['verdict'] = 'PASS' if rep['all_checks_pass'] else 'FAIL_CHECKS'

    if args.apply and rep['all_checks_pass']:
        with open(path, 'wb') as f:
            f.write(new_raw)
        rep['applied'] = True
        rep['bytes_after'] = len(new_raw)
    else:
        rep['applied'] = False

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    print('[out] %s' % OUT)
    return 0 if rep['all_checks_pass'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
