#!/usr/bin/env python
r"""APP-024：GUI 冒烟测试 —— 验证设备标签改动**没有破坏 GUI**。

🔴 必须验的三件事：
  1. **label 全局唯一**（GUI 靠 label 反查 engine/device，撞号会取错引擎）；
  2. 三个分区的 Combobox 都能建起来、值都能反查回原选项；
  3. TTS 分区**能看到 CUDA 选项**（用户明确要求）。
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
import tkinter.ttk as ttk

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
sys.path.insert(0, os.path.join(REPO, "live_caption"))

import device_config  # noqa: E402
import live_caption_app as app  # noqa: E402


def check_unique(name, opts):
    labels = [o["label"] for o in opts]
    dup = {x for x in labels if labels.count(x) > 1}
    print("[%s] 选项 %d 个，label 唯一：%s" % (name, len(labels), "OK" if not dup else "FAIL %s" % dup))
    if dup:
        for d in dup:
            print("      重复 label:", d)
            for o in opts:
                if o["label"] == d:
                    print("        ->", o)
    return not dup


def main() -> None:
    devs = device_config.available_devices()
    print("本机设备:", devs)
    print()

    asr = app.build_asr_options(devs)
    mt = app.build_mt_options(devs)
    tts = app.build_tts_options(devs)

    ok = True
    ok &= check_unique("ASR", asr)
    ok &= check_unique("MT", mt)
    ok &= check_unique("TTS", tts)

    print()
    print("=== TTS 分区内容（用户要在这里看到 CUDA）===")
    cuda_seen = False
    for o in tts:
        mark = ""
        if "CUDA" in o["label"]:
            mark = "  <= CUDA 选项"
            cuda_seen = True
        print("  %-46s%s" % (o["label"], mark))
    print()
    print("TTS 里能看到 CUDA 选项：", "OK" if cuda_seen else "FAIL")
    ok &= cuda_seen

    print()
    print("=== 假设备检查 ===")
    fake = [o for o in (asr + mt + tts) if "Intel GPU 2" in o["label"]]
    print("含「Intel GPU 2」的选项：", len(fake), "=>", "OK（已消失）" if not fake else "FAIL")
    ok &= not fake

    # ── 真起一个 Tk（无窗口，离屏）验证 Combobox 装配 ──
    print()
    print("=== Tk 装配冒烟 ===")
    try:
        root = tk.Tk()
        root.withdraw()
        for name, opts in (("ASR", asr), ("MT", mt), ("TTS", tts)):
            cb = ttk.Combobox(root, state="readonly", values=[o["label"] for o in opts])
            cb.set(opts[0]["label"] if opts else "")
            got = cb.get()
            back = next((o for o in opts if o["label"] == got), None)
            print("  %-4s Combobox OK，反查 %s" % (name, "OK" if back else "FAIL"))
            ok &= bool(back)
        root.destroy()
    except Exception as e:
        print("  Tk 冒烟失败：%s: %s" % (type(e).__name__, e))
        ok = False

    print()
    print("=" * 60)
    print("GUI 冒烟：", "全 PASS" if ok else "有 FAIL")
    print("=" * 60)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
