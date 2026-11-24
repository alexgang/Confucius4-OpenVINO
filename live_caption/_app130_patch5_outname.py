#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130 补丁⑤：`_out_name` 用 `ConstOutput.get_names()` 取**输出名**。

## 为什么还要补这一刀（补丁④ 的残留）

补丁④把 `OVDict` 归一成了 `{名字: ndarray}`，但**名字取错了**：

```
CPU 的键 repr： <ConstOutput: names[hidden_states] shape[1,?,1024] type: f32>
NPU 的键 repr： <ConstOutput: names[hidden_states] shape[1,2,1024] type: f32>
```

⇒ CPU（**动态维** IR）与 NPU（**reshape 成静态形状**）的键**字符串不同**
⇒ 归一化后两边**键对不上** ⇒ 「键缺失」⇒ 余弦还是算不出来。

🔴 正确取法（本机 OV 2026.4.1 实测）：
- `ConstOutput.get_names()` ⇒ **`{'hidden_states'}`（set）** ✅ 两边一致；
- `ConstOutput.node.get_names()` ⇒ **在动态形状上抛 RuntimeError**
  （`to_shape was called on a dynamic shape`）⇒ 不能用；
- `ConstOutput.names` ⇒ 同 `get_names()`（set）。

⇒ 判据：**先试 `get_names()`（set ⇒ 取 sorted 第一个），
   再退 `node.get_names()`（列表 ⇒ 取第一个），最后才退 `str(k)`。**
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'tts_engine.py')


def crlf(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


OLD = '''
def _out_name(k) -> str:
    """把 OV 的输出键（`ConstOutput`）还原成输出名（如 `hidden_states`）。"""
    try:
        names = k.node.get_names()
        if names:
            return str(names[0])
    except Exception:
        pass
    return str(k)
'''

NEW = '''
def _out_name(k) -> str:
    """把 OV 的输出键（`ConstOutput`）还原成输出名（如 `hidden_states`）。

    🔴 **必须只取名字、不能带形状**（本机 OV 2026.4.1 实测）：
       CPU（动态维 IR）的键 repr 是 `names[hidden_states] shape[1,?,1024]`，
       NPU（reshape 成静态形状）的是 `names[hidden_states] shape[1,2,1024]`
       ⇒ 若用 `str(k)` 当键 ⇒ **两边键对不上** ⇒ 比不了。

    🔴 `ConstOutput.get_names()` ⇒ **set**（`{'hidden_states'}`）✅ 两边一致；
       `ConstOutput.node.get_names()` 在**动态形状**上会抛 RuntimeError
       （`to_shape was called on a dynamic shape`）⇒ 不能当首选。
    """
    try:
        names = k.get_names()
        if names:
            return sorted(str(n) for n in names)[0]
    except Exception:
        pass
    try:
        names = k.node.get_names()
        if names:
            return str(list(names)[0])
    except Exception:
        pass
    return str(k)
'''

PATCHES = [('_out_name', OLD, NEW)]


def main() -> int:
    raw = open(TARGET, 'rb').read()
    orig = raw.decode('utf-8')
    if '\r\n' not in orig:
        print('FAIL: 目标不是 CRLF ⇒ 停手')
        return 2
    backup = os.path.join(tempfile.gettempdir(), 'tts_engine.py.app130e.bak')
    shutil.copy2(TARGET, backup)
    print('备份: %s (%d B)' % (backup, len(raw)))

    text = orig
    for name, old, new in PATCHES:
        o, n = crlf(old), crlf(new)
        cnt = text.count(o)
        if cnt != 1:
            print('FAIL: 补丁 %r 命中 %d 次（要求 1 次）⇒ 零改动' % (name, cnt))
            return 3
        text = text.replace(o, n, 1)

    errs = []
    back = text
    for name, old, new in reversed(PATCHES):
        o, n = crlf(old), crlf(new)
        if back.count(n) != 1:
            errs.append('还原式复核失败：%r 反向命中 %d 次' % (name, back.count(n)))
            break
        back = back.replace(n, o, 1)
    else:
        if back != orig:
            errs.append('还原式复核失败：反向替换后与原文不逐字节相同')
    if text.count('\n') != text.count('\r\n'):
        errs.append('行尾风格被改')
    if 'k.get_names()' not in text:
        errs.append('缺 get_names() 调用')
    try:
        compile(text, TARGET, 'exec')
    except SyntaxError as e:
        errs.append('语法错误：%s' % e)
    if errs:
        print('自检 FAIL ⇒ 零改动：')
        for e in errs:
            print('  - %s' % e)
        return 4

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TARGET), suffix='.app130e.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(text.encode('utf-8'))
        os.replace(tmp, TARGET)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print('已打补丁：_out_name（get_names 优先）')
    print('字节：%d → %d（%+d）／行数：%d → %d（%+d）'
          % (len(raw), len(text.encode('utf-8')),
             len(text.encode('utf-8')) - len(raw),
             orig.count('\n'), text.count('\n'),
             text.count('\n') - orig.count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
