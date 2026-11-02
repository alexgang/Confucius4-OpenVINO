#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130（v3）：`app215` ①b 判据的**委派检测**改用 AST（不用源码片段）。

🔴 **为什么 v2 不行**：`ast.get_source_segment()` 需要节点**有位置信息**；
   我构造的合成 `ast.Module` **没有 lineno** ⇒ 片段恒为 '' ⇒ 委派检测恒 False。
⇒ 改为**直接在 AST 上找** `Call(func=Attribute(attr='_fallback_to_preset_ref_cuda'))`
   ⇒ **不依赖源码文本** ⇒ 更稳。
"""
import ast
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
TARGET = os.path.join(REPO, 'results', 'app', 'app215_app061_voice_clone_fix.py')

OLD = """            body_assigns = _collect(cuda_branch.body)
            has_boolop = any(isinstance(n.value, ast.BoolOp)
                             for n, _s in body_assigns)
            scope_assigns = body_assigns
            delegated = False
            if not has_boolop:
                # CUDA 分支 body 里没有 BoolOp 赋值 ⇒ 可能是 §130 的委派形态
                seg = _src_of(w_src, ast.Module(body=cuda_branch.body,
                                                type_ignores=[]))
                helper = _fn(tree, '_fallback_to_preset_ref_cuda')
                if helper is not None and '_fallback_to_preset_ref_cuda' in seg:
                    delegated = True
                    h_assigns = _collect(helper.body)
                    scope_assigns = h_assigns
                    has_boolop = any(isinstance(n.value, ast.BoolOp)
                                     for n, _s in h_assigns)
"""

NEW = """            body_assigns = _collect(cuda_branch.body)
            has_boolop = any(isinstance(n.value, ast.BoolOp)
                             for n, _s in body_assigns)
            scope_assigns = body_assigns
            delegated = False
            if not has_boolop:
                # CUDA 分支 body 里没有 BoolOp 赋值 ⇒ 可能是 §130 的委派形态
                # 🔴 **在 AST 上直接找调用**（不用源码片段：
                #   `ast.get_source_segment` 需要节点有位置信息 ⇒ 合成节点取不到）
                def _calls_helper(stmts):
                    for stmt in stmts:
                        for n in ast.walk(stmt):
                            if isinstance(n, ast.Call):
                                f = n.func
                                if isinstance(f, ast.Attribute) and \\
                                        f.attr == '_fallback_to_preset_ref_cuda':
                                    return True
                                if isinstance(f, ast.Name) and \\
                                        f.id == '_fallback_to_preset_ref_cuda':
                                    return True
                    return False

                helper = _fn(tree, '_fallback_to_preset_ref_cuda')
                if helper is not None and _calls_helper(cuda_branch.body):
                    delegated = True
                    h_assigns = _collect(helper.body)
                    scope_assigns = h_assigns
                    has_boolop = any(isinstance(n.value, ast.BoolOp)
                                     for n, _s in h_assigns)
"""


def main():
    with open(TARGET, 'rb') as f:
        raw = f.read()
    before = hashlib.sha256(raw).hexdigest()
    text = raw.decode('utf-8')
    n = text.count(OLD)
    if n != 1:
        print('[FAIL] ①b 判据块命中 %d 次（须恰好 1 次）' % n)
        return 2
    text = text.replace(OLD, NEW, 1)
    try:
        ast.parse(text)
    except SyntaxError as e:
        print('[FAIL] ast.parse 失败：%s' % e)
        return 3
    out = text.encode('utf-8')
    with open(TARGET, 'wb') as f:
        f.write(out)
    with open(TARGET, 'rb') as f:
        check = f.read()
    assert check == out
    print('[OK] app215 ①b 委派检测改用 AST（不依赖源码片段）')
    print('  bytes  %d → %d' % (len(raw), len(check)))
    print('  sha256 %s → %s' % (before, hashlib.sha256(check).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
