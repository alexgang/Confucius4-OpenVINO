#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130：更新 `app215` 的 ①b 判据（代码 §130 重构 ⇒ 判据要跟着走）。

🔴 **语义必须完全不变**：
  ①b 判的是「**CUDA 路线回落时，`speaker_name` 必须被赋成一个 BoolOp**
  （即 `self._preset_name or 'A'`）⇒ **不能**被清空」
  ⇒ 清空了 ⇒ `synth()` 报「没有可用的音色」⇒ APP-061① 回归。

§130 把这段赋值搬进了新方法 `_fallback_to_preset_ref_cuda()`
⇒ 判据必须**跟着委派关系**找到它 ⇒ 但**鉴别力必须不变**：
  - 直接赋值在 CUDA 分支里 ⇒ 通过（改前形态）
  - CUDA 分支**委派**给 `_fallback_to_preset_ref_cuda()` ⇒
    去看**那个方法里**有没有 BoolOp 赋值（§130 新形态）
  - 两处都没有 ⇒ **FAIL**（旧 v2.1 形态 ⇒ 必须被抓出来）
"""
import ast
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
TARGET = os.path.join(REPO, 'results', 'app', 'app215_app061_voice_clone_fix.py')

OLD = """        else:
            assigns = []
            for n in ast.walk(cuda_branch):
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        if isinstance(t, ast.Attribute) and t.attr == 'speaker_name':
                            assigns.append(_src_of(w_src, n.value))
            ok = bool(assigns) and any(
                isinstance(n.value, ast.BoolOp) for n in ast.walk(cuda_branch)
                if isinstance(n, ast.Assign))
            out['1b_cuda_fallback_keeps_name'] = (
                bool(ok), 'CUDA 分支内 speaker_name 赋值=%r' % (assigns,))
"""

NEW = """        else:
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
    print('[OK] app215 ①b 判据已跟随重构更新（鉴别力不变）')
    print('  bytes  %d → %d' % (len(raw), len(check)))
    print('  sha256 %s → %s' % (before, hashlib.sha256(check).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
