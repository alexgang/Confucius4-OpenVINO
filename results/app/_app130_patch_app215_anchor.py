#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130：更新 `app215` 的**反证变异锚点**（代码被 §130 重构 ⇒ 锚点要跟着走）。

🔴 **语义必须完全不变**：
  M2「恢复旧回落」= 把 CUDA 路线的回落从
      「`speaker_embed=None` + `speaker_name=_preset_name or 'A'`」
    改回
      「`speaker_embed=_preset_embed` + `speaker_name=_preset_name`」
  （⇒ 旧状态下 `_preset_name` 是 None ⇒ `speaker_name` 为空 ⇒ 旧闸门命中）

  §130 把这段代码搬进了新方法 `_fallback_to_preset_ref_cuda()`
  ⇒ 锚点的**缩进**从 12 空格变成 8 空格 ⇒ **只改缩进，语义一字不变**。
"""
import ast
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
TARGET = os.path.join(REPO, 'results', 'app', 'app215_app061_voice_clone_fix.py')

OLD = '''MUT_W_1B_OLD = """            self.speaker_embed = None
            self.speaker_name = self._preset_name or 'A'
            ref = self._preset_ref_path
"""
MUT_W_1B_NEW = """            self.speaker_embed = self._preset_embed
            self.speaker_name = self._preset_name
            ref = self._preset_ref_path
"""
'''

NEW = '''# 🔴🔴🔴 §130：这段代码被搬进了新方法 `_fallback_to_preset_ref_cuda()`
#   ⇒ **只改缩进**（12 → 8 空格），**语义一字不变**
#   ⇒ 反证仍然在测同一件事：「回落把 speaker_name 恢复成 _preset_name」
MUT_W_1B_OLD = """        self.speaker_embed = None
        self.speaker_name = self._preset_name or 'A'
        ref = self._preset_ref_path
"""
MUT_W_1B_NEW = """        self.speaker_embed = self._preset_embed
        self.speaker_name = self._preset_name
        ref = self._preset_ref_path
"""
'''


def main():
    with open(TARGET, 'rb') as f:
        raw = f.read()
    before = hashlib.sha256(raw).hexdigest()
    crlf = raw.count(b'\r\n')
    use_crlf = bool(crlf) and crlf == raw.count(b'\n')
    text = raw.decode('utf-8')
    if use_crlf:
        text = text.replace('\r\n', '\n')

    n = text.count(OLD)
    if n != 1:
        print('[FAIL] 锚点命中 %d 次（须恰好 1 次）' % n)
        return 2
    text = text.replace(OLD, NEW, 1)
    try:
        ast.parse(text)
    except SyntaxError as e:
        print('[FAIL] ast.parse 失败：%s' % e)
        return 3
    if use_crlf:
        text = text.replace('\n', '\r\n')
    out = text.encode('utf-8')
    with open(TARGET, 'wb') as f:
        f.write(out)
    with open(TARGET, 'rb') as f:
        check = f.read()
    assert check == out
    assert check.count(b'\r\n') == check.count(b'\n'), '出现裸 LF'
    print('[OK] app215 反证锚点已跟随重构更新（语义不变）')
    print('  bytes  %d → %d' % (len(raw), len(check)))
    print('  sha256 %s → %s' % (before, hashlib.sha256(check).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
