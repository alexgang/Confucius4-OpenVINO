#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-050 真机取证：**TTS 启动日志里的 EXECUTION_DEVICES 一行**。

## APP-050 原文要求

> 在你的 TTS 启动日志里打印 talker、cp_prefill、cp_decode、decoder 各自实际的
> EXECUTION_DEVICES，确认全部是 NPU。如果你是直接调 build()，要显式传
> cp_decode_device="NPU"（或者调用重编译）。**把一行日志证据写进 STATUS**。
> **不用另外做测速。**

## 本脚本做什么（**不推理、不测速**）

- 用**客户包自带的 python** + **客户包内的 `app/tts_engine.py`**（= 同步后的最新版）
- 调 `tts_engine.make_engine(device='NPU', ...)` ⇒ 这就是 **TTS 启动时走的同一条路**
  （`tts_worker.py::_try_load_babelvox()` L1305 调的就是它）
- 把 `on_log` 的**全部输出行**落盘（⇒ 就是「启动日志」）
- 断言那行 `EXECUTION_DEVICES …` 存在，且四个组件齐全
- 落盘 JSON 证据（文件数 / mtime / 字节数 / SHA256 由调用方补）

🔴 **不跑推理** ⇒ 不产生音频 ⇒ 不触「不在 CPU 上跑推理」的纪律。
🔴 但**加载模型要编译 NPU IR** ⇒ 会吃 CPU ⇒ **必须持机器锁**
   （用 `results/app/app174_run_with_lock.py` 这个壳来跑）。

## 关键前置：必须用**包内**的 tts_engine

- 只有包内 python 有 `openvino`（系统 python 无）。
- 仓库侧**没有** `models/qwen3tts/` ⇒ `tts_engine.model_root()` 会回落成不存在的路径。
⇒ `sys.path` 必须让 `import tts_engine` 解析到 **`<pkg>/app/tts_engine.py`**。

## 用法

    <pkg>/python/python.exe results/app/app174_run_with_lock.py \
        --script results/app/app174c_startup_log_evidence.py \
        --out results/app/app174c_startup_log_evidence.json
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

PKG_ROOT = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13'
PKG_APP = os.path.join(PKG_ROOT, 'app')


def main() -> int:
    out = {'pkg_root': PKG_ROOT, 'pkg_app': PKG_APP}

    # 🔴🔴🔴 **必须让 `import tts_engine` 解析到包内**
    #   （仓库的 live_caption/ 里那份**没有** models/qwen3tts/ ⇒ 加载必失败）
    if PKG_APP not in sys.path:
        sys.path.insert(0, PKG_APP)

    import tts_engine as TE
    out['tts_engine_file'] = os.path.abspath(TE.__file__)
    out['tts_engine_in_pkg'] = os.path.abspath(TE.__file__).lower().startswith(
        os.path.abspath(PKG_APP).lower())
    out['has_norm_helper'] = hasattr(TE, '_norm_exec_devices')

    logs = []

    def on_log(m):
        logs.append(str(m))
        print('  ' + str(m), flush=True)

    print('[engine] 开始加载（device=NPU）…', flush=True)
    t0 = time.perf_counter()
    try:
        eng = TE.make_engine(device='NPU', on_log=on_log,
                             cache_dir=os.path.join(
                                 os.environ.get('LOCALAPPDATA')
                                 or os.path.expanduser('~'),
                                 'Confucius4LiveCaption', 'tts_npu_cache'))
    except Exception as e:
        import traceback
        out['load_error'] = '%s: %s' % (type(e).__name__, e)
        out['traceback'] = traceback.format_exc()[-2000:]
        out['logs'] = logs
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1
    load_wall = round(time.perf_counter() - t0, 2)

    ex = getattr(eng, 'exec_devices', None) or {}
    out['load_wall_s'] = load_wall
    out['logs'] = logs
    out['exec_devices'] = ex
    out['actual'] = ex.get('actual')
    out['on_npu'] = ex.get('on_npu')
    out['on_cpu'] = ex.get('on_cpu')
    out['on_unknown'] = ex.get('on_unknown')
    out['unknown'] = ex.get('unknown')
    out['absent'] = ex.get('absent')
    out['key4_line'] = ex.get('key4_line')
    out['devices_raw'] = ex.get('devices_raw')

    # ── 判据 ─────────────────────────────────────────────────────
    checks = []
    kl = ex.get('key4_line') or ''
    checks.append(('key4_line存在', bool(kl), kl))
    for comp in ('talker=', 'cp_prefill=', 'cp_decode=', 'decoder='):
        checks.append(('key4含%s' % comp, comp in kl, kl))
    checks.append(('talker非?', 'talker=?' not in kl, kl))
    checks.append(('cp_prefill非?', 'cp_prefill=?' not in kl, kl))
    checks.append(('cp_decode非?', 'cp_decode=?' not in kl, kl))
    checks.append(('decoder非?', 'decoder=?' not in kl, kl))
    # 🔴 **四格都必须是 NPU**（APP-050 的核心判据）
    for comp in ('talker', 'cp_prefill', 'cp_decode'):
        v = (ex.get('actual') or {}).get(comp)
        if v is None:
            # talker 在有桶时是桶集合 ⇒ 取所有桶
            vs = [v2 for k2, v2 in (ex.get('actual') or {}).items()
                  if k2.startswith('talker_bucket@')]
            v = '/'.join(sorted(set(vs))) if vs else None
        checks.append(('%s落NPU' % comp, v == 'NPU', repr(v)))
    dv = [v2 for k2, v2 in (ex.get('actual') or {}).items()
          if k2 == 'tok_decoder' or k2.startswith('decoder_bucket@')]
    checks.append(('decoder全落NPU',
                   bool(dv) and all(v2 == 'NPU' for v2 in dv), repr(dv)))
    checks.append(('on_cpu为空', not (ex.get('on_cpu') or []),
                   repr(ex.get('on_cpu'))))
    checks.append(('on_unknown为空', not (ex.get('on_unknown') or []),
                   repr(ex.get('on_unknown'))))

    n_pass = sum(1 for _n, ok, _d in checks if ok)
    n_fail = len(checks) - n_pass
    out['checks'] = [dict(name=n, ok=bool(ok), detail=d) for n, ok, d in checks]
    out['n_pass'] = n_pass
    out['n_fail'] = n_fail
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    # 🔴 启动日志里那一行（写进 STATUS 用）
    out['log_line_key4'] = next(
        (m for m in logs if 'EXECUTION_DEVICES' in m), '')

    # 🔴 证据 JSON **自己落盘**（不让 runner 包一层）⇒ 下游可直接 json.load
    _ev = sys.argv[1] if len(sys.argv) > 1 else None
    if _ev:
        os.makedirs(os.path.dirname(os.path.abspath(_ev)), exist_ok=True)
        with open(_ev, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('[evidence] %s' % os.path.abspath(_ev))

    print(json.dumps({k: v for k, v in out.items() if k != 'logs'},
                     ensure_ascii=False, indent=2))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
