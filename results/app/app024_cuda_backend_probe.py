#!/usr/bin/env python
r"""APP-024：探针 —— 判定 OpenVINO 的 ``GPU.1`` 到底走**哪个 plugin**（CUDA vs Intel GPU）。

🔴 为什么要单独探针：
   - OV 2026.4 把 CUDA plugin 合并进主包 ⇒ ``available_devices`` 里出现
     ``GPU.1``（NVIDIA）**不代表**能用 CUDA 后端；
   - 报错路径里出现 ``src\plugins\intel_gpu\...`` 让人误以为走的是 Intel 后端
     ⇒ 必须用**实测**判定，不能靠猜。

判定手段：加载一个**含 INT8 权重**的模型，在 GPU.0 / GPU.1 上分别编译，
对比能否编译成功 + 编译日志里的 plugin 路径。
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import openvino as ov

# 🔴 OV 2026.4 已把 ``openvino.runtime`` 合并进主包（``openvino.runtime`` 不再存在）
#    ⇒ 统一用 ``ov.opset13``。
ovr = ov.opset13
_T = ov.Type


def make_model():
    """构造一个含 **reorder/convert** 节点的小模型（对齐 TTS 失败的那个节点类型）。"""
    p = ovr.parameter([1, 64], _T.f32, name="x")
    y = ovr.convert(ovr.multiply(p, ovr.constant(np.ones((1, 64), dtype=np.float32))),
                    _T.f16)
    z = ovr.convert(y, _T.f32)
    return ov.Model([z], [p], "probe")


def main() -> None:
    core = ov.Core()
    print("openvino:", ov.__version__)
    print("devices :", core.available_devices)
    print()

    model = make_model()
    for dev in ("GPU.0", "GPU.1"):
        if dev not in core.available_devices:
            print("== %s: 本机无此设备，跳过" % dev)
            continue
        print("=" * 66)
        print("== %s  (%s)" % (dev, core.get_property(dev, "FULL_DEVICE_NAME")))
        t0 = time.perf_counter()
        try:
            cm = core.compile_model(model, dev)
            dt = time.perf_counter() - t0
            out = cm(np.ones((1, 64), dtype=np.float32))
            print("   ✅ 编译+推理成功 %.2f s" % dt)
            # 🔴 OV 2026.4 的 infer 返回 **OVDict**（不是 ndarray）
            arr = out
            if hasattr(out, "values"):
                arr = list(out.values())[0]
            arr = np.asarray(arr)
            print("   输出 shape =", arr.shape, " 有限值 =", bool(np.isfinite(arr).all()))
            for p in cm.get_properties():
                if "PLUGIN" in p.upper() or "AFFINITY" in p.upper():
                    try:
                        print("   %s = %s" % (p, cm.get_property(p)))
                    except Exception:
                        pass
        except Exception as e:
            msg = str(e)
            print("   ❌ 失败：%s" % type(e).__name__)
            for line in msg.splitlines()[:6]:
                print("      ", line)
            # 关键：看 plugin 路径
            for line in msg.splitlines():
                if "plugins\\" in line or "plugins/" in line:
                    print("      [plugin 路径]", line.strip())
                    break
        print()


if __name__ == "__main__":
    main()
