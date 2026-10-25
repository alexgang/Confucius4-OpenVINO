#!/usr/bin/env python
r"""APP-024：实测 TTS 引擎在 **NVIDIA 独显（OV 的 GPU.1 / CUDA plugin）** 上能否加载并合成。

🔴 为什么要实测（不能只看「available_devices 里有 GPU.1」就下结论）：
   - OpenVINO 的 CUDA plugin 与 **Intel GPU plugin 是两套完全不同的后端**；
   - TTS 用的是 **INT8 权重**（`models/qwen3tts/int8/*.bin`）
     ⇒ NVIDIA 后端对 INT8 的支持路径与 Intel 不同（可能需 FP16 重编译）；
   - 结论必须来自**真实加载 + 真实合成**，不是「设备在列表里」。

用法：
    python app024_tts_cuda_probe.py [--device GPU.1]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
# 🔴 **必须优先用「脚本所在目录」的模块**（客户包 app/ 或仓库 live_caption/），
#    否则 sys.path.insert(REPO/live_caption) 会抢先导入**仓库那份** tts_engine
#    ⇒ PKG_ROOT 指向仓库 ⇒ 找不到客户包里的模型 ⇒ 误报「找不到 TTS 模型」。
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="GPU.1")
    ap.add_argument("--text", default="这是一段中文测试。")
    args = ap.parse_args()

    print("=" * 70)
    print("TTS 设备实测：device =", args.device)
    print("=" * 70)

    # ① 设备信息
    import openvino as ov
    core = ov.Core()
    if args.device not in core.available_devices:
        print("!! 本机没有该设备，退出")
        sys.exit(2)
    print("[1] FULL_DEVICE_NAME =", core.get_property(args.device, "FULL_DEVICE_NAME"))

    # ② 加载引擎
    import tts_engine
    t0 = time.perf_counter()
    try:
        eng = tts_engine.make_engine(device=args.device, on_log=lambda m: print("   ", m))
    except Exception as e:
        print("[2] ❌ 引擎加载失败：%s: %s" % (type(e).__name__, e))
        sys.exit(1)
    print("[2] ✅ 引擎加载完成 %.1f s" % (time.perf_counter() - t0))

    # ③ 合成一句
    t0 = time.perf_counter()
    try:
        audio = eng.generate(args.text)
    except TypeError:
        audio = eng.generate_stream(args.text)
    except Exception as e:
        print("[3] ❌ 合成失败：%s: %s" % (type(e).__name__, e))
        sys.exit(1)
    dt = time.perf_counter() - t0

    n = len(audio) if audio is not None else 0
    print("[3] ✅ 合成完成 %.2f s，音频 %d 采样" % (dt, n))
    if n:
        try:
            import numpy as np
            a = np.asarray(audio, dtype="float32")
            print("    RMS=%.4f  peak=%.4f  有效=%s" % (
                float(np.sqrt((a ** 2).mean())), float(np.abs(a).max()),
                "有信号" if np.abs(a).max() > 1e-4 else "🔴 全静音"))
        except Exception:
            pass
    print("=" * 70)
    print("结论：", args.device, "可用" if n else "未产出音频")
    sys.exit(0 if n else 1)


if __name__ == "__main__":
    main()
