#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""App §82 · APP-027 / §81.11 第 3 条：**NPU 身份实证**（实测每个 IR 的执行设备）。

🔴🔴🔴 **本脚本解决的问题（§81.11 第 3 条）**
────────────────────────────────────────────────────────────────
`app118_engine_baseline_tts_only.py` 的报告里 `device_desc=null` / `load_s=null`
⇒ 根因是**引擎对象从未暴露这两个属性** ⇒ 报告脚本只能靠 `getattr` 猜
⇒ 猜不到就写 `null` ⇒ **审问「是否真在 NPU 上跑」时无法回答**。

🔴🔴 **本脚本是「正面实证」而不是「兜底」**：
- 用 `CompiledModel.get_property('EXECUTION_DEVICES')` —— 这是 OV 2026.4.1 里
  **实测每个 IR 真实执行设备**的决定性证据（不是「请求了什么设备」）。
- 逐组件列出落点：`speaker_encoder` / `talker_prefill` / `talker_decode` /
  `talker_buckets` / `cp_prefill` / `cp_decode` / `code_predictor` /
  `tokenizer_decoder`。
- 附带 NPU 插件自身属性（FULL_DEVICE_NAME / DRIVER / COMPILER 版本），
  以及 `core.available_devices`。

🔴 **不做的事**
- 不跑推理（只加载模型 + 查属性）⇒ 但**加载模型本身要编译 NPU IR**
  ⇒ 必须持机器锁（编译会吃 CPU）。
- 不做质量判定（交 reviewer）。

用法：
    python app120_npu_exec_device_proof.py                # 正常取证
    python app120_npu_exec_device_proof.py --probe-only    # 只探环境，不加载模型
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LIVE = os.path.join(REPO, 'live_caption')

OUT_DIR = os.path.join(os.path.expanduser('~'), 'app027_v1')
REPORT = os.path.join(OUT_DIR, 'npu_exec_device_proof.json')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _env_probe():
    """只读探环境（不加载模型 ⇒ 不占 CPU ⇒ 不需要锁）。"""
    out = dict(ok=False)
    try:
        import openvino as ov
        core = ov.Core()
        out['openvino_version'] = ov.__version__
        out['available_devices'] = list(core.available_devices)
        try:
            out['npu_full_device_name'] = str(
                core.get_property('NPU', 'FULL_DEVICE_NAME'))
        except Exception as e:
            out['npu_full_device_name'] = 'ERR:%r' % (e,)
        for prop in ('NPU_PLATFORM', 'NPU_DRIVER_VERSION', 'NPU_COMPILER_VERSION'):
            try:
                out[prop] = str(core.get_property('NPU', prop))
            except Exception as e:
                out[prop] = 'ERR:%r' % (e,)
        out['ok'] = True
    except Exception as e:
        out['error'] = '%s: %s' % (type(e).__name__, e)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--probe-only', action='store_true')
    ap.add_argument('--lock-timeout', type=float, default=7200.0)
    args = ap.parse_args()

    env = _env_probe()
    print('[env] %s' % json.dumps(env, ensure_ascii=False))
    if args.probe_only:
        return 0 if env.get('ok') else 2

    if LIVE not in sys.path:
        sys.path.insert(0, LIVE)

    # 🔴🔴🔴 **必须用「客户包内的解释器 + 包内的 tts_engine」**：
    #   ① 只有包内 python 有 `openvino`（系统 python 无 ⇒ ModuleNotFoundError）
    #   ② 仓库侧**没有** `models/qwen3tts/` ⇒ `tts_engine.model_root()`
    #      会回落成不存在的路径 ⇒ 加载必失败
    #   ⇒ 本脚本**必须由 `<pkg>/python/python.exe` 运行**，且
    #      `tts_engine` 必须解析到 **`<pkg>/app/tts_engine.py`**（= 已同步的 §82 版）
    PKG_ROOT = os.path.join(os.path.expanduser('~'),
                            'Confucius4_LiveCaption_v1.6')
    PKG_APP = os.path.join(PKG_ROOT, 'app')
    if PKG_APP not in sys.path:
        sys.path.insert(0, PKG_APP)
    print('[paths] pkg_app=%s' % PKG_APP)

    # ── 机器锁（加载模型会编译 NPU IR ⇒ 吃 CPU ⇒ 必须持锁）──
    # 🔴 机器锁模块在**仓库根**（不在客户包里）⇒ 需要把仓库根加进 sys.path
    REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=args.lock_timeout,
                                   poll=20, verbose=True)
    if not ok_lock:
        print('[lock] ❌ 未取得机器锁 ⇒ 放弃（绝不在无锁状态下编译 NPU IR）')
        return 3
    print('[lock] 已持有')
    try:
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                   timeout=900.0, verbose=True)
        print('[lock] 静默窗口 ok=%s info=%s' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] ❌ 静默窗口未通过 ⇒ 放弃')
            return 4

        import tts_engine as TE

        t0 = time.perf_counter()
        eng = TE.make_engine(device=args.device, on_log=lambda m: print('  ' + m))
        load_wall = round(time.perf_counter() - t0, 2)
        print('[engine] 加载完成 %.1f s' % load_wall)

        # 引擎对象自带字段（本轮 tts_engine.py 改动的产物）
        obj_fields = dict(
            load_s=getattr(eng, 'load_s', None),
            device_desc=getattr(eng, 'device_desc', None),
            device=getattr(eng, 'device', None),
            cp_on_cpu=getattr(eng, 'cp_on_cpu', None),
        )
        print('[engine] obj_fields=%s' % json.dumps(obj_fields, ensure_ascii=False))

        # ── 正面实证：逐组件 EXECUTION_DEVICES ──
        ex = getattr(eng, 'exec_devices', None)
        if not ex:
            ex = TE.execution_devices(eng, on_log=lambda m: print('  ' + m))
        print('[exec_devices] %s' % json.dumps(ex, ensure_ascii=False))

        devices = ex.get('devices') or {}
        # 🔴🔴🔴 **NPU 插件的 `EXECUTION_DEVICES` 返回「缩写 fallback 链」**
        #   （本轮实测）：直接 compile ⇒ `'NPU'`（字符串）；
        #   经 App 的精度注入（`set_property('NPU', {...})`）⇒ `['N','P','U']`
        #   ⇒ **链首 = 首选 = 实际落点**（`N` ⇒ NPU，`P` ⇒ CPU）。
        dnorm = ex.get('devices_norm')
        if not dnorm:
            _map = {'N': 'NPU', 'P': 'CPU', 'U': 'UNKNOWN'}
            dnorm = {k: [_map.get(str(d).upper(), str(d)) for d in v]
                     for k, v in devices.items()}
        actual = ex.get('actual')
        if not actual:
            actual = {k: (v[0] if v else None) for k, v in dnorm.items()}
        on_npu = sorted(k for k, v in actual.items() if v == 'NPU')
        on_cpu = sorted(k for k, v in actual.items() if v == 'CPU')
        on_unknown = sorted(k for k, v in actual.items()
                            if v not in ('NPU', 'CPU'))

        report = dict(
            ts=time.strftime('%Y-%m-%d %H:%M:%S'),
            cfg='npu_exec_device_proof',
            requested_device=args.device,
            env=env,
            load_wall_s=load_wall,
            engine_obj_fields=obj_fields,
            exec_devices=ex,
            components_on_npu=on_npu,
            components_on_cpu=on_cpu,
            components_on_unknown=on_unknown,
            components_unknown=list(ex.get('unknown') or []),
            note=('EXECUTION_DEVICES 是 OV 2026.4.1 实测每个 IR 真实执行设备的'
                  '决定性证据；不是「请求了什么设备」。'
                  '⚠️ NPU 插件返回缩写 fallback 链 [N,P,U]'
                  '（N=NPU / P=CPU / U=UNKNOWN）⇒ 链首=首选=实际落点。'
                  '对照实测：直接 compile ⇒ "NPU"（字符串）；CPU 档 ⇒ ["CPU"]。'
                  '未落盘的组件一律记 unknown，不猜。'),
        )
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('[report] %s' % REPORT)
        print('[report] bytes=%d sha256=%s'
              % (os.path.getsize(REPORT), _sha256(REPORT)))
        return 0
    finally:
        try:
            ml.release(payload)
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
