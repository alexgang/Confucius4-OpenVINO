#!/usr/bin/env python
r"""APP-024：**决定性**验证 —— TTS 的真实 INT8 IR 能否在 **NVIDIA 独显（CUDA）** 上编译。

🔴 为什么必须单独验证真实 IR：
   - 合成小模型在 GPU.1 上编译成功 ⇒ **只能证明 CUDA plugin 存在**；
   - 但 TTS 用的是 **INT8 权重**（`models/qwen3tts/int8/*.xml/.bin`）
     ⇒ NVIDIA 后端对 INT8 的 kernel 覆盖与 Intel GPU 不同
     （实测已在 ``convert:Constant_496`` 处报「Could not find a suitable kernel」）
   ⇒ 结论必须来自**逐个编译 TTS 的真实 IR**。

输出：每个 IR 在 GPU.0 / GPU.1 上的编译结果 + 失败原因摘录。
"""
from __future__ import annotations

import glob
import os
import sys
import time

import openvino as ov

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4"
IR_DIR = os.path.join(PKG, "models", "qwen3tts", "int8")

DEVICES = ("GPU.0", "GPU.1")


def main() -> None:
    if not os.path.isdir(IR_DIR):
        print("!! 找不到 IR 目录:", IR_DIR)
        sys.exit(2)
    xmls = sorted(glob.glob(os.path.join(IR_DIR, "*.xml")))
    print("TTS IR 数量:", len(xmls))
    for x in xmls:
        print("   -", os.path.basename(x))
    print()

    core = ov.Core()
    print("本机设备:", core.available_devices)
    for d in DEVICES:
        if d in core.available_devices:
            print("   %s = %s" % (d, core.get_property(d, "FULL_DEVICE_NAME")))
    print()

    # 只取**主干** IR（talker / talker_decode / talker_prefill / cp_decode / cp_prefill /
    # speaker_encoder / code_predictor / tokenizer_*）—— 全量都编太慢。
    key_words = ("talker", "cp_decode", "cp_prefill", "speaker", "code_predictor")
    targets = [x for x in xmls
               if any(k in os.path.basename(x) for k in key_words)]
    if not targets:
        targets = xmls

    results = {}
    for dev in DEVICES:
        if dev not in core.available_devices:
            print("== %s 本机无此设备，跳过" % dev)
            continue
        print("=" * 72)
        print("== %s (%s)" % (dev, core.get_property(dev, "FULL_DEVICE_NAME")))
        print("=" * 72)
        for xml in targets:
            name = os.path.basename(xml)
            t0 = time.perf_counter()
            try:
                model = core.read_model(xml)
                core.compile_model(model, dev)
                dt = time.perf_counter() - t0
                print("   ✅ %-26s 编译成功 %.1f s" % (name, dt))
                results.setdefault(dev, {})[name] = "OK %.1fs" % dt
            except Exception as e:
                msg = str(e).replace("\n", " ")
                print("   ❌ %-26s 失败" % name)
                # 摘录关键原因
                for key in ("Could not find a suitable kernel",
                            "Failed to select implementation",
                            "ProgramBuilder build failed",
                            "not supported",
                            "Unsupported"):
                    if key in msg:
                        i = msg.find(key)
                        print("      →", msg[max(0, i - 90):i + 190].strip()[:300])
                        break
                else:
                    print("      →", msg[:220].strip())
                results.setdefault(dev, {})[name] = "FAIL"
        print()

    print("=" * 72)
    print("汇总：")
    for dev, r in results.items():
        ok = sum(1 for v in r.values() if v.startswith("OK"))
        print("   %-6s 成功 %d / %d" % (dev, ok, len(r)))
    print("=" * 72)


if __name__ == "__main__":
    main()
