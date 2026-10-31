#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-050 前置探针：**OV 的 `get_property('EXECUTION_DEVICES')` 到底返回什么类型**。

## 为什么必须先探这个

`live_caption/tts_engine.py::execution_devices()` 里写的是：

```python
devs = obj.get_property('EXECUTION_DEVICES')
...
out['devices'][label] = list(devs)
```

⇒ **`list(devs)`**。

🔴 如果 `devs` 是**字符串** `"NPU"` ⇒ `list("NPU") == ['N','P','U']`
   ⇒ 旧代码把这个「逐字符拆开」的产物**当成 NPU 插件的 fallback 链**
   ⇒ 文档里那段「缩写 fallback 链 [N,P,U]」的解读**是错的**
   ⇒ 且 **CPU 档会算成 `actual='C'`** ⇒ 落进 `on_unknown` ⇒
      **「CPU 回落」永远不会被 `on_cpu` 抓到**（静默漏报）。

🔴 如果 `devs` 是**列表** `['NPU','CPU','UNKNOWN']` ⇒ 旧解读成立。

⇒ **两种假设在旧证据里产出完全相同的 `['N','P','U']` ⇒ 旧证据不可分辨**
⇒ 必须实测。

## 本脚本做什么（**不做推理**）

用 OV 现场造一个**极小**的模型（一个 MatMul），分别在
`CPU` 与 `NPU` 上编译，然后打印 `get_property('EXECUTION_DEVICES')` 的
**原始值 / 类型 / repr**。

🔴 只编译、不推理 ⇒ 不产生任何语音/音频 ⇒ 不触「不在 CPU 上跑推理」的纪律。
🔴 极小模型 ⇒ 编译耗时在秒级。

## 用法

    "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.13/python/python.exe" \
        results/app/app174a_probe_exec_devices_type.py
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        import openvino as ov
        from openvino import opset13 as ops
    except Exception as e:
        print('[FATAL] import openvino 失败：%r' % (e,))
        return 2

    out = {'openvino_version': ov.__version__,
           'available_devices': [], 'probes': {}}
    try:
        core = ov.Core()
        out['available_devices'] = list(core.available_devices)
    except Exception as e:
        print('[FATAL] ov.Core() 失败：%r' % (e,))
        return 2

    # 🔴 极小模型：2×2 矩阵乘（1 个 MatMul 节点）⇒ 编译秒级
    param = ops.parameter([2, 2], ov.Type.f32, name='p')
    matmul = ops.matmul(param, param, False, False, name='mm')
    model = ov.Model([matmul], [param], 'probe')

    for dev in ('CPU', 'NPU'):
        rec = {}
        try:
            t0 = __import__('time').perf_counter()
            cm = core.compile_model(model, dev)
            rec['compile_s'] = round(__import__('time').perf_counter() - t0, 3)
            try:
                raw = cm.get_property('EXECUTION_DEVICES')
            except Exception as e:
                rec['get_property_error'] = '%s: %s' % (type(e).__name__, e)
                raw = None
            rec['raw_repr'] = repr(raw)
            rec['raw_type'] = type(raw).__name__
            rec['is_str'] = isinstance(raw, str)
            rec['is_list'] = isinstance(raw, list)
            rec['list_of_raw'] = list(raw) if raw is not None else None
            rec['list_of_raw_len'] = len(list(raw)) if raw is not None else None
            if isinstance(raw, str):
                rec['split_by_comma'] = [s for s in raw.split(',') if s]
            # 🔴 旧代码的解读路径
            _norm = {'N': 'NPU', 'P': 'CPU', 'U': 'UNKNOWN'}
            try:
                devs = list(raw) if raw is not None else None
                norm = [_norm.get(str(d).upper(), str(d)) for d in devs] if devs else []
                rec['old_code_actual'] = norm[0] if norm else None
            except Exception as e:
                rec['old_code_error'] = '%s: %s' % (type(e).__name__, e)
        except Exception as e:
            rec['compile_error'] = '%s: %s' % (type(e).__name__, e)
        out['probes'][dev] = rec

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
