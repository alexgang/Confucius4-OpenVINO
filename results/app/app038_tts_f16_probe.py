#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-037：TTS 在 **NVIDIA 独显（GPU.1）** 上，**f16 推理精度**能否编译通过。

🔴 背景（用户反馈 2026-10-25 16:40）：
   「语音输出，提示本机 OV 未安装 Cuda plugin，语音输出无法工作」
   ⇒ §32 的实测结论是 GPU.1 上 TTS 真实 INT8 IR **3/7 编译失败**，
   失败点全部在 **FP16↔FP32 reorder 节点**（「Could not find a suitable kernel」）。

🔴 **本脚本要回答的问题**：
   那个失败是「**权重本身**（INT8）在 NVIDIA 后端无 kernel」，
   还是「**推理精度选 f16 才触发的 reorder**」？
   ⇒ 若 f16 精度能编过 ⇒ 就有解：TTS 在 NVIDIA 上用 f16 即可工作
      （代价：显存/速度，不是正确性问题）。

判据：逐个编译**客户包内真实的 TTS IR**（不改权重），
      分别在 GPU.0 / GPU.1 上，且分别用 **f32 / f16** 两种 INFERENCE_PRECISION。

🔴 纪律：
  - **持共享机器锁**（会占 GPU，污染其它模块的计时）；
  - 只编译，**不推理**（不产生音频、不占显存做长时推理）；
  - 结果落盘 `results/app/app038_tts_f16_probe.json`。
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

import openvino as ov

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5"
IR_DIR = os.path.join(PKG, "models", "qwen3tts", "int8")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "app038_tts_f16_probe.json")

# 主干 IR：§32 的实测就是在这 7 个上做的
TARGETS = ("talker", "talker_decode", "talker_prefill", "cp_decode",
           "cp_prefill", "speaker_encoder", "code_predictor")

ERROR_KEYS = ("Could not find a suitable kernel",
              "Failed to select implementation",
              "ProgramBuilder build failed",
              "not supported",
              "Unsupported",
              "UnsupportedPrecision")


def compile_one(core, xml, dev, prec):
    """在 (dev, prec) 下编译一个 IR ⇒ (ok, seconds, error_excerpt)。"""
    name = os.path.basename(xml)
    t0 = time.perf_counter()
    try:
        model = core.read_model(xml)
        core.set_property(dev, {"INFERENCE_PRECISION_HINT": prec})
        core.compile_model(model, dev)
        return True, round(time.perf_counter() - t0, 2), ''
    except Exception as e:
        msg = str(e).replace('\n', ' ')
        excerpt = ''
        for key in ERROR_KEYS:
            if key in msg:
                i = msg.find(key)
                excerpt = msg[max(0, i - 100):i + 220].strip()[:320]
                break
        if not excerpt:
            excerpt = msg[:240].strip()
        return False, round(time.perf_counter() - t0, 2), excerpt


def main() -> int:
    if not os.path.isdir(IR_DIR):
        print('!! 找不到 IR 目录:', IR_DIR)
        return 2

    xmls = [x for x in sorted(glob.glob(os.path.join(IR_DIR, '*.xml')))
            if any(t in os.path.basename(x) for t in TARGETS)]
    if not xmls:
        xmls = sorted(glob.glob(os.path.join(IR_DIR, '*.xml')))
    print('目标 IR 数量:', len(xmls))
    for x in xmls:
        print('   -', os.path.basename(x))
    print()

    core = ov.Core()
    devs = list(core.available_devices)
    print('本机设备:', devs)
    for d in devs:
        try:
            print('   %s = %s' % (d, core.get_property(d, 'FULL_DEVICE_NAME')))
        except Exception:
            pass
    print()

    result = {'ir_dir': IR_DIR, 'devices': devs, 'runs': {}}
    # 只测**有 GPU 的**设备 + 两种精度
    gpu_devs = [d for d in devs if str(d).upper().startswith('GPU')]

    for dev in gpu_devs:
        for prec in ('f32', 'f16'):
            key = '%s@%s' % (dev, prec)
            print('=' * 72)
            print('== %s  精度=%s' % (dev, prec))
            print('=' * 72)
            per = {}
            ok_n = 0
            for xml in xmls:
                name = os.path.basename(xml)
                ok, dt, err = compile_one(core, xml, dev, prec)
                per[name] = {'ok': ok, 'sec': dt, 'err': err}
                if ok:
                    ok_n += 1
                    print('   [OK]   %-24s %.1f s' % (name, dt))
                else:
                    print('   [FAIL] %-24s %.1f s' % (name, dt))
                    if err:
                        print('          ->', err[:200])
            result['runs'][key] = {'ok': ok_n, 'total': len(xmls), 'per_ir': per}
            print('   => 成功 %d / %d' % (ok_n, len(xmls)))
            print()

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('证据已落盘:', OUT)

    print('=' * 72)
    print('汇总：')
    for k, v in result['runs'].items():
        print('   %-14s %d / %d' % (k, v['ok'], v['total']))
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
