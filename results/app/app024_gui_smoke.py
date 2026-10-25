#!/usr/bin/env python
r"""APP-024：GUI 冒烟测试 —— 验证设备下拉的构造**没有破坏 GUI**。

🔴 必须验的五件事：
  1. **label 全局唯一**（GUI 靠 label 反查 engine/device，撞号会取错引擎）；
  2. 三个分区的 Combobox 都能建起来、值都能反查回原选项；
  3. **ASR 分区里同一块物理显卡不重复出现**（2026-10-25 用户反馈：
     「asr 里的设备既有 NVIDIA 独显又有 NVIDIA GPU (Cuda)，重复了，
     保留 Cuda 即可」）⇒ NVIDIA 独显那条**必须消失**，CUDA 那条**必须保留**；
  4. **TTS 分区里不再出现 NVIDIA 设备**（2026-10-25 用户反馈：
     「语音输出，提示本机 OV 未安装 Cuda plugin，语音输出无法工作」）
     ⇒ 必须能在下拉里选到**真能用**的设备，且**有明确说明**为什么没有 CUDA；
  5. 假设备（`Intel GPU 2`）不再出现。

🔴🔴 **本脚本的断言已随 2026-10-25 的修法一起改过**：
   旧版断言「TTS 里**能看到** CUDA 选项」（当时用户要求把 CUDA 加进 TTS），
   但现在已证明 **NVIDIA 上 TTS 必然加载失败**（7 个 IR 只编过 3 个，
   而 BabelVox 要求全过）⇒ 那条断言**必然 FAIL**，方向也反了。
   ⇒ 现改为断言「TTS **无** CUDA 选项 **且** note 里有说明」。

⚠️ **必须用客户包的 python 跑**（需要 numpy / openvino / tkinter）：
   `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\python\python.exe`
"""
from __future__ import annotations

import argparse
import io
import os
import sys

PKG_APP = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\app"
REPO_APP = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"


def check_unique(name, opts):
    labels = [o["label"] for o in opts]
    dup = {x for x in labels if labels.count(x) > 1}
    print("[%s] 选项 %d 个，label 唯一：%s"
          % (name, len(labels), "OK" if not dup else "FAIL %s" % dup))
    if dup:
        for d in dup:
            print("      重复 label:", d)
            for o in opts:
                if o["label"] == d:
                    print("        ->", o)
    return not dup


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-dir", default=PKG_APP,
                    help="要测的 App 目录（默认客户包，交付口径）")
    args = ap.parse_args()

    app_dir = args.app_dir
    if not os.path.isdir(app_dir):
        print("FAIL: App 目录不存在 %s" % app_dir)
        sys.exit(2)
    sys.path.insert(0, app_dir)
    print("被测目录:", app_dir)

    import tkinter as tk
    import tkinter.ttk as ttk
    import device_config
    import live_caption_app as app

    print("device_config 来自:", device_config.__file__)
    print("live_caption_app 来自:", app.__file__)
    print()

    devs = device_config.available_devices()
    print("本机设备:", devs)
    print("has_cuda_plugin:", device_config.has_cuda_plugin())
    print()

    asr = app.build_asr_options(devs)
    mt = app.build_mt_options(devs)
    tts = app.build_tts_options(devs)

    ok = True
    ok &= check_unique("ASR", asr)
    ok &= check_unique("MT", mt)
    ok &= check_unique("TTS", tts)

    # ── ① ASR：NVIDIA 独显那条必须消失、CUDA 那条必须保留 ──
    print()
    print("=== ASR 分区内容 ===")
    for o in asr:
        print("  %-46s dev=%-6s prec=%s"
              % (o["label"], o["device"], o["precision"]))
    nv_ov = [o for o in asr
             if o["device"] != "CUDA" and device_config.is_cuda_device(o["device"])]
    cuda_items = [o for o in asr if o["device"] == "CUDA"]
    print()
    print("ASR 里 OV 档重复列出的 NVIDIA 设备条数：%d => %s"
          % (len(nv_ov), "PASS（已去重）" if not nv_ov else "FAIL"))
    ok &= not nv_ov
    print("ASR 里 NVIDIA GPU（CUDA）条数：%d => %s"
          % (len(cuda_items), "PASS（保留）" if cuda_items else "FAIL（丢了）"))
    ok &= bool(cuda_items)
    # 每一块物理显卡在 ASR 里最多出现一次
    seen = {}
    for o in asr:
        if o["device"] in ("CUDA", "NPU"):
            continue
        seen[o["device"]] = seen.get(o["device"], 0) + 1
    print("ASR 每台 OV 设备的出现次数：%s" % seen)

    # ── ② TTS：不得出现 NVIDIA 设备，且必须有说明 ──
    print()
    print("=== TTS 分区内容（语音输出实际可选）===")
    for o in tts:
        print("  %-46s dev=%-6s prec=%s"
              % (o["label"], o["device"], o["precision"]))
    tts_cuda = [o for o in tts
                if "CUDA" in o["label"] or device_config.is_cuda_device(o["device"])]
    print()
    print("TTS 里的 NVIDIA/CUDA 选项条数：%d => %s"
          % (len(tts_cuda), "PASS（已移除）" if not tts_cuda else "FAIL（选了会失败）"))
    ok &= not tts_cuda
    notes = " ".join(o.get("note") or "" for o in tts)
    has_note = ("已从语音输出列表移除" in notes) and ("NVIDIA" in notes)
    print("TTS note 里有「已从语音输出列表移除」+ NVIDIA 原因说明：",
          "PASS" if has_note else "FAIL（用户会以为程序漏了硬件）")
    ok &= has_note
    gpu_f16 = [o for o in tts if o["device"].upper().startswith("GPU")
               and o["precision"] == "f16"]
    print("TTS 里集显 f16（实测合成失控）条数：%d => %s"
          % (len(gpu_f16), "PASS（已移除）" if not gpu_f16 else "FAIL"))
    ok &= not gpu_f16
    print("TTS 至少有一个可用选项：", "PASS" if tts else "FAIL")
    ok &= bool(tts)
    print("TTS 首选是否为 NPU：",
          "PASS" if (tts and tts[0]["device"].upper() == "NPU") else "FAIL")
    ok &= bool(tts and tts[0]["device"].upper() == "NPU")

    # ── ③ 假设备 ──
    print()
    print("=== 假设备检查 ===")
    fake = [o for o in (asr + mt + tts) if "Intel GPU 2" in o["label"]]
    print("含「Intel GPU 2」的选项：", len(fake),
          "=>", "OK（已消失）" if not fake else "FAIL")
    ok &= not fake

    # ── ④ 真起一个 Tk（无窗口，离屏）验证 Combobox 装配 ──
    print()
    print("=== Tk 装配冒烟 ===")
    try:
        root = tk.Tk()
        root.withdraw()
        for name, opts in (("ASR", asr), ("MT", mt), ("TTS", tts)):
            cb = ttk.Combobox(root, state="readonly",
                              values=[o["label"] for o in opts])
            cb.set(opts[0]["label"] if opts else "")
            got = cb.get()
            back = next((o for o in opts if o["label"] == got), None)
            print("  %-4s Combobox OK，反查 %s"
                  % (name, "OK" if back else "FAIL"))
            ok &= bool(back)
        root.destroy()
    except Exception as e:
        print("  Tk 冒烟失败：%s: %s" % (type(e).__name__, e))
        ok = False

    # ── ⑤ 静态自检：修法必须真的在文件里（防「同步漏了」） ──
    print()
    print("=== 静态自检（源码里必须有修法标记）===")
    app_src = io.open(os.path.join(app_dir, "live_caption_app.py"),
                      encoding="utf-8").read()
    dc_src = io.open(os.path.join(app_dir, "device_config.py"),
                     encoding="utf-8").read()
    te_src = io.open(os.path.join(app_dir, "tts_engine.py"),
                     encoding="utf-8").read()
    tw_src = io.open(os.path.join(app_dir, "tts_worker.py"),
                     encoding="utf-8").read()
    checks = (
        ("live_caption_app: _tts_device_problem", "def _tts_device_problem" in app_src),
        ("live_caption_app: _first_usable_tts_device",
         "def _first_usable_tts_device" in app_src),
        ("live_caption_app: _track_tts_state", "def _track_tts_state" in app_src),
        ("live_caption_app: 精度感知判定",
         "def _is_intel_gpu" in app_src),
        ("live_caption_app: ASR 跳过 CUDA 设备",
         "CUDA 设备由 kind=='cuda' 那条承担" in app_src),
        ("live_caption_app: TTS 移除说明",
         "已从语音输出列表移除" in app_src),
        ("device_config: cuda_backend_possible",
         "def cuda_backend_possible" in dc_src),
        ("tts_engine: precision 形参",
         "precision: Optional[str] = None" in te_src),
        ("tts_engine: _ov_precision 注入",
         "INFERENCE_PRECISION_HINT" in te_src),
        ("tts_worker: 传 precision", "precision=self.precision" in tw_src),
    )
    for label, hit in checks:
        print("  %-44s %s" % (label, "OK" if hit else "FAIL"))
        ok &= hit

    print()
    print("=" * 60)
    print("GUI 冒烟：", "全 PASS" if ok else "有 FAIL")
    print("=" * 60)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
