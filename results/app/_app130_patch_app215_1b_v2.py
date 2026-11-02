#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130（v2）：修 `app215` ①b 判据的**作用域**错误。

🔴 **原判据的真问题**：`ast.walk(cuda_branch)` 遍历的是**整个 `If` 节点**
⇒ **把 `else` 分支（= BabelVox 路线）也遍历进去了**
⇒ 收集到的 `speaker_name` 赋值混进了 else 分支的
⇒ §130 把 CUDA 分支的赋值搬进共用出口后，
   `assigns` **非空**（全是 else 分支的）⇒ 我的「委派」判定**永远进不去**
⇒ 判据 FAIL。

🔴 **修法**：**只看 CUDA 分支的 body**（`cuda_branch.body`），
   再按需**跟随委派**进 `_fallback_to_preset_ref_cuda()`。
   ⇒ **鉴别力必须不变**：
      - CUDA 分支 body 里有 BoolOp 赋值（改前形态）⇒ PASS
      - CUDA 分支 body **委派**给共用出口（§130 新形态）⇒ 看去那个方法 ⇒ PASS
      - 两处都没有（v2.1 形态）⇒ **FAIL**
"""
import ast
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
TARGET = os.path.join(REPO, 'results', 'app', 'app215_app061_voice_clone_fix.py')

OLD = """        else:
            # 🔴🔴🔴 §130：§130 把 CUDA 路线的回落**收敛**到共用出口
            #   `_fallback_to_preset_ref_cuda()` ⇒ 赋值搬进了那个方法。
            #   ⇒ 判据**跟着委派关系**找 ⇒ 但**鉴别力必须不变**：
            #   两处都没有 BoolOp 赋值 ⇒ 仍判 FAIL（v2.1 形态必须被抓出来）。
            assigns = []
            for n in ast.walk(cuda_branch):
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        if isinstance(t, ast.Attribute) and t.attr == 'speaker_name':
                            assigns.append(_src_of(w_src, n.value))
            scope = cuda_branch
            helper = _fn(tree, '_fallback_to_preset_ref_cuda')
            delegated = False
            if not assigns and helper is not None:
                seg = _src_of(w_src, cuda_branch)
                if '_fallback_to_preset_ref_cuda' in seg:
                    delegated = True
                    scope = helper
                    for n in ast.walk(helper):
                        if isinstance(n, ast.Assign):
                            for t in n.targets:
                                if (isinstance(t, ast.Attribute)
                                        and t.attr == 'speaker_name'):
                                    assigns.append(_src_of(w_src, n.value))
            ok = bool(assigns) and any(
                isinstance(n.value, ast.BoolOp) for n in ast.walk(scope)
                if isinstance(n, ast.Assign))
            out['1b_cuda_fallback_keeps_name'] = (
                bool(ok),
                'CUDA 分支内 speaker_name 赋值=%r（委派共用出口=%r）'
                % (assigns, delegated))
"""

NEW = """        else:
            # 🔴🔴🔴 §130：**只看 CUDA 分支的 body**（`ast.walk(If)` 会把
            #   **else 分支**（BabelVox 路线）也遍历进去 ⇒ 语义被污染）
            #   ⇒ 再按需**跟随委派**进 `_fallback_to_preset_ref_cuda()`
            #   ⇒ **鉴别力必须不变**（v2.1 形态：两处都没有 ⇒ FAIL）。
            def _collect(body):
                got = []
                for stmt in body:
                    for n in ast.walk(stmt):
                        if isinstance(n, ast.Assign):
                            for t in n.targets:
                                if (isinstance(t, ast.Attribute)
                                        and t.attr == 'speaker_name'):
                                    got.append((n, _src_of(w_src, n.value)))
                return got

            body_assigns = _collect(cuda_branch.body)
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
            assigns = [s for _n, s in scope_assigns]
            ok = bool(assigns) and has_boolop
            out['1b_cuda_fallback_keeps_name'] = (
                bool(ok),
                'CUDA 分支内 speaker_name 赋值=%r（委派共用出口=%r）'
                % (assigns, delegated))
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
    print('[OK] app215 ①b 判据作用域已修正（只看 CUDA 分支 body）')
    print('  bytes  %d → %d' % (len(raw), len(check)))
    print('  sha256 %s → %s' % (before, hashlib.sha256(check).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
