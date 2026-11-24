#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130 补丁④：**修「OV 输出不是 dict」导致的假 FAIL**（判据自身的 bug）。

## 现象（A 机 11-24 10:36 实测）

```
[tts_engine] cp_decode:  NPU 自检失败（用例 amp=0.02 与 CPU 余弦 0.0000 < 0.99）⇒ 留在 CPU
[tts_engine] cp_prefill: NPU 自检失败（用例 amp=0.02 与 CPU 余弦 0.0000 < 0.99）⇒ 留在 CPU
```

⇒ A 机（Panther Lake，NPU 正常机型）**本应通过**自检、cp 仍留在 NPU，
   却被打回 CPU ⇒ **判据错了，不是模型坏了**。

## 根因（本机实测确认）

`openvino 2026.4.1` 的 `CompiledModel.__call__` 返回的是
**`openvino.utils.data_helpers.wrappers.OVDict`**：

| 断言 | 实测 |
|---|---|
| `isinstance(out, dict)` | **False**（它是 `collections.abc.Mapping`） |
| `list(out.keys())` | 元素是 **ConstOutput 对象**（不是字符串名） |
| `np.asarray(out)` | shape **(3,) object** ← **把三个输出包成对象数组** |
| `out['hidden_states']` | ✅ 可用（babelvox 就是这么取的） |

⇒ 补丁①里的判据：
  - `_cp_compare_outputs`：`isinstance(cpu_out, dict) and isinstance(npu_out, dict)`
    ⇒ **False** ⇒ 走「整体当数组比」分支 ⇒ `np.asarray(OVDict)` 得到
    **object 数组** ⇒ 两边 size 不等 ⇒ `_cosine` 返回 **0.0**
    ⇒ **恒判失败**（余弦恰好 0.0000 就是这个特征）。
  - `_find_nonfinite`：`isinstance(out, dict)` ⇒ False ⇒ `np.asarray(out)`
    得到 object 数组 ⇒ `dtype.kind == 'O'` ⇒ **直接返回 None**
    ⇒ 🔴 **运行时 NaN 守卫等于没装**（永远不触发）。

⇒ 同一个根因同时打坏了「自检」与「运行时保险」两处。

## 修法

新增三个归一化 helper：

- `_as_array(v)`：OV 的输出值是 `ConstOutput` ⇒ 取 `.data` 再转 numpy；
- `_out_name(k)`：把 ConstOutput 还原成输出名（`hidden_states` 等）；
- `_ov_out_to_dict(out)`：把 **OVDict / dict / ndarray** 统一归一成
  `{名字: np.ndarray}`。

然后 `_find_nonfinite` 与 `_cp_compare_outputs` **一律先归一化**。

## 纪律（定点写入三件套）

备份 → 写前真不变量 ＋ **还原式复核** → 临时文件 → `os.replace`
⇒ **写后另起脚本复核** ＋ `git diff --numstat`。
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


OLD_FIND = '''
def _find_nonfinite(out):
    """在 OV 输出（dict / ndarray）里找 NaN / Inf。返回描述串或 None。"""
    try:
        import numpy as np
    except Exception:
        return None

    def _one(arr):
        try:
            a = np.asarray(arr)
        except Exception:
            return None
        if a.dtype.kind not in 'fc':
            return None
        if not bool(np.all(np.isfinite(a))):
            return 'NaN' if bool(np.isnan(a).any()) else 'Inf'
        return None

    if isinstance(out, dict):
        for k in sorted(out.keys(), key=str):
            r = _one(out[k])
            if r:
                return '%s 含 %s' % (k, r)
        return None
    r = _one(out)
    return ('含 %s' % r) if r else None
'''

NEW_FIND = '''
def _as_array(v):
    """把 OV 的输出值转成 numpy 数组。

    🔴 **OV 2026.4.1 的 `CompiledModel.__call__` 返回 `OVDict`**，
       它的**值是 `ConstOutput` 对象** ⇒ 必须取 `.data` 才是真数组。
       （`np.asarray(ConstOutput)` 恰好也能work，但 `np.asarray(OVDict)`
       会得到 **object 数组** ⇒ 必须先归一化再比。）
    """
    try:
        import numpy as np
    except Exception:
        return None
    d = getattr(v, 'data', None)
    if d is not None:
        try:
            return np.asarray(d)
        except Exception:
            pass
    try:
        return np.asarray(v)
    except Exception:
        return None


def _out_name(k) -> str:
    """把 OV 的输出键（`ConstOutput`）还原成输出名（如 `hidden_states`）。"""
    try:
        names = k.node.get_names()
        if names:
            return str(names[0])
    except Exception:
        pass
    return str(k)


def _ov_out_to_dict(out):
    """把 OV 的输出**统一归一**成 `{输出名: np.ndarray}`。

    🔴 为什么要这一步（APP-130 补丁④ 的根因）：
       `OVDict` **不是 `dict`**（是 `collections.abc.Mapping`），
       `isinstance(out, dict)` 为 **False**；
       而 `np.asarray(OVDict)` 得到 shape `(N,) object` 的**对象数组**
       ⇒ 直接拿去比大小/比余弦 ⇒ **恒不相等** ⇒ 自检恒判失败（假 FAIL），
       NaN 守卫也**永远不触发**。
    """
    if out is None:
        return None
    d = _ov_items(out)
    if d:
        return d
    a = _as_array(out)
    return {'__out__': a} if a is not None else None


def _ov_items(out):
    """OV 输出（`OVDict` / `dict`）⇒ `{输出名: ndarray}`；不是映射 ⇒ 空 dict。"""
    if out is None or not hasattr(out, 'items'):
        return {}
    d = {}
    try:
        for k, v in out.items():
            a = _as_array(v)
            if a is not None:
                d[_out_name(k)] = a
    except Exception:
        return {}
    return d


def _find_nonfinite(out):
    """在 OV 输出里找 NaN / Inf。返回描述串或 None。

    🔴 **先归一化**（OVDict / ConstOutput / ndarray 都要处理）⇒ 见 `_ov_out_to_dict`。
    """
    try:
        import numpy as np
    except Exception:
        return None

    d = _ov_out_to_dict(out)
    if not d:
        return None

    def _one(arr):
        try:
            a = np.asarray(arr)
        except Exception:
            return None
        if a.dtype.kind not in 'fc':
            return None
        if not bool(np.all(np.isfinite(a))):
            return 'NaN' if bool(np.isnan(a).any()) else 'Inf'
        return None

    for k in sorted(d.keys()):
        r = _one(d[k])
        if r:
            return '%s 含 %s' % (k, r)
    return None
'''

OLD_CMP = '''
def _cp_compare_outputs(cpu_out, npu_out):
    """逐键比较 CPU / NPU 输出。返回 `(min_cos, bad_desc)`。"""
    if isinstance(cpu_out, dict) and isinstance(npu_out, dict):
        keys = [k for k in cpu_out.keys() if k in npu_out]
        if not keys:
            return 0.0, '输出键不匹配（CPU %s / NPU %s）' % (
                sorted(map(str, cpu_out.keys())),
                sorted(map(str, npu_out.keys())))
        min_cos = 1.0
        desc = ''
        for k in sorted(keys, key=str):
            c = _cosine(cpu_out[k], npu_out[k])
            if c < min_cos:
                min_cos = c
            if c < CP_SELFCHECK_COS_MIN and not desc:
                desc = '%s 与 CPU 余弦 %.4f < %.2f' % (
                    k, c, CP_SELFCHECK_COS_MIN)
        return min_cos, desc
    c = _cosine(cpu_out, npu_out)
    if c < CP_SELFCHECK_COS_MIN:
        return c, '与 CPU 余弦 %.4f < %.2f' % (c, CP_SELFCHECK_COS_MIN)
    return c, ''
'''

NEW_CMP = '''
def _cp_compare_outputs(cpu_out, npu_out):
    """逐键比较 CPU / NPU 输出。返回 `(min_cos, bad_desc)`。

    🔴 **两侧都先归一化**（OV 的 `OVDict` 不是 `dict`）⇒ 见 `_ov_out_to_dict`。
    """
    c = _ov_out_to_dict(cpu_out)
    n = _ov_out_to_dict(npu_out)
    if c is None or n is None:
        return 0.0, '输出无法归一化（CPU %r / NPU %r）' % (type(cpu_out),
                                                         type(npu_out))
    keys = [k for k in c.keys() if k in n.keys()]
    if not keys:
        return 0.0, '输出键不匹配（CPU %s / NPU %s）' % (
            sorted(map(str, c.keys())), sorted(map(str, n.keys())))
    min_cos = 1.0
    desc = ''
    for k in sorted(keys):
        v = _cosine(c[k], n[k])
        if v < min_cos:
            min_cos = v
        if v < CP_SELFCHECK_COS_MIN and not desc:
            desc = '%s 与 CPU 余弦 %.4f < %.2f' % (k, v, CP_SELFCHECK_COS_MIN)
    return min_cos, desc
'''

PATCHES = [
    ('_find_nonfinite + 归一化 helper', OLD_FIND, NEW_FIND),
    ('_cp_compare_outputs 归一化', OLD_CMP, NEW_CMP),
]


def main() -> int:
    raw = open(TARGET, 'rb').read()
    orig = raw.decode('utf-8')
    if '\r\n' not in orig:
        print('FAIL: 目标不是 CRLF ⇒ 停手')
        return 2
    backup = os.path.join(tempfile.gettempdir(), 'tts_engine.py.app130d.bak')
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
    for sym in ('_ov_out_to_dict', '_as_array', '_out_name'):
        if sym not in text:
            errs.append('缺关键符号：%s' % sym)
    try:
        compile(text, TARGET, 'exec')
    except SyntaxError as e:
        errs.append('语法错误：%s' % e)
    if errs:
        print('自检 FAIL ⇒ 零改动：')
        for e in errs:
            print('  - %s' % e)
        return 4

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TARGET), suffix='.app130d.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(text.encode('utf-8'))
        os.replace(tmp, TARGET)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print('已打补丁：%s' % '、'.join(n for n, _o, _x in PATCHES))
    print('字节：%d → %d（%+d）／行数：%d → %d（%+d）'
          % (len(raw), len(text.encode('utf-8')),
             len(text.encode('utf-8')) - len(raw),
             orig.count('\n'), text.count('\n'),
             text.count('\n') - orig.count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
