#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-062：**cp_decode 设备**的决定性 A/B（reviewer APP-018 第 1 条第 1 项）。

## 假设（来自代码事实，非猜测）

reviewer 的生产配置明写「**cp_decode 放 NPU**」，但 App 侧从来没实现过：

| 位置 | 代码 | cp_decode 设备 |
|---|---|---|
| `babelvox/pipeline.py` L347-350（原生 `BabelVox._load_npu_models`） | `core.compile_model(cp_decode.xml, "CPU")` | **CPU** |
| `live_caption/tts_engine_patch.py` L379-382（App vendored patch，md5 与 TTS 模块 `qwen3tts_patch.py` **完全一致**） | 同上 | **CPU** |
| `qwen3tts_eval/eval_cp_on_npu.py::_recompile_cp_on_npu()`（TTS 模块的「尺子」） | `m.reshape(CP_SHAPE)` 后 `compile_model(m, "NPU")` | **NPU** |

⇒ TTS 模块测出 RTF 0.8568 / 首包 0.5862 s 时，**cp_decode 在 NPU**；
   App 测出 RTF ~2.05 / 首块 1.07-1.29 s 时，**cp_decode 在 CPU**。
⇒ 差 ≈ **2.4×**，与观测到的 RTF 差距量级一致。

## 本脚本要做的

**同一个进程、同一个引擎实例、同一批句子**，只切 `cp_decode` 的编译设备：

- **A 臂（基线）**：`cp_decode` 留在 **CPU**（= 现在的 App 行为）
- **B 臂**：把 `cp_decode` 用**同样的 CP_SHAPE reshape** 后**重新编译到 NPU**

⇒ 只改一个变量 ⇒ 直接读出这个变量的效应。

⚠️ **必须 reshape**：动态维 IR 直接编到 NPU 会 **Segfault**（进程直接崩，
   try/except 接不住）—— 详见 `eval_cp_on_npu.py` 的 docstring。

## 纪律

- 🔴 **持共享机器锁**（计时作业）。
- 🔴 **不 import 被测模块**（`tts_worker` 顶部连带 numpy/openvino ⇒ import 阶段就 abort）。
  ⇒ 这里只调**引擎层** `tts_engine`（纯 python 入口，走客户包真实路径）。
- 🔴 **计时窗口内除本进程外不启动任何 `python.exe`**（连读 JSON 都不行）。
- 🔴 产物写**仓库外**。

用法（客户包 python）：
    python results/app/app062_cp_decode_device_ab.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# 🔴 取锁统一走仓库根的 `machine_lock_app`（**原子写** + 独占 + fail-closed）。
#   旧的「各自复制一份取锁代码」是逻辑漂移的根源 ⇒ 已全部收敛到这里。
#   旧写法 `os.open(O_CREAT|O_EXCL)` **先建空文件、之后才写内容**
#   ⇒ 存在「文件已存在、内容还是空的」窗口 ⇒ 别的模块读到空锁
#   ⇒ 解析不出 pid ⇒ 判成「陈旧锁」⇒ **删掉别人的活锁** ⇒ 两个模块同时跑
#   ⇒ 实测作废 TTS 两轮数据（16/30、24/30 行 timing_valid=false）。
#   依据：shared/NOTICE_tts_lock_atomic_20261026.md §一 / §三 3.1。
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import machine_lock_app


def _lock_probe_fields():
    """🔴 逐条锁自检字段（TTS 通知 §四）。

    🔴 「锁被抢 / 被删 / 被换写」在数据里**完全看不出来**
    ⇒ 逐条查 ⇒ 锁一断就 `timing_valid=false` ⇒ 污染不会伪装成正常结果。
    """
    p = machine_lock_app.lock_probe()
    return {'timing_valid': p['lock_ok'], 'lock_note': p['lock_note'],
            'lock_pid': p['lock_pid']}

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
OUT_DIR = r'C:\Users\Trekker-PTL\abba_out'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# 🔴 cp_decode 的静态形状（取自 babelvox pipeline.py 的 CP_* 常量，
#    与 `qwen3tts_eval/eval_cp_on_npu.py` **完全一致** ⇒ 同一把尺子）
CP_SHAPE = {
    "inputs_embeds": [1, 1, 1024],
    "cache_position": [1],
    "attention_mask": [1, 1, 1, 20],
    "past_keys": [5, 1, 8, 20, 128],
    "past_values": [5, 1, 8, 20, 128],
}

# 与 `app061` 同一批句子（同源素材）⇒ 可与 app061 solo 直接对照
TEXTS = [
    '大家早上好，欢迎参加季度工程评审会。',
    '今天，我想与团队一起探讨三个主要主题。',
    '首先，我们将看看上次测量的推理延迟数据。',
    '其次，包装流程得到了大幅简化。',
    '第三，我们希望简化流程，讨论下一次发布的路线图。',
    '如果还有任何问题，请随时告诉我，我们继续吧。',
]


def _pid_alive(pid: int) -> bool:
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if k.GetExitCodeProcess(h, ctypes.byref(code)):
            return code.value == 259
        return False
    finally:
        k.CloseHandle(h)


def _read_lock_pid(raw: str):
    """🔴 锁格式兼容：README 单行（`asr PID=…`）+ key-value 两种都要认。"""
    for ln in raw.split('\n'):
        up = ln.upper()
        if 'PID=' in up:
            try:
                return int(up.split('PID=')[1].split()[0].strip())
            except Exception:
                return None
        if up.strip().startswith('PID:'):
            try:
                return int(up.split('PID:')[1].split()[0].strip())
            except Exception:
                return None
    return None


def acquire_lock(module='app', timeout_s=3600.0):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    t0 = time.time()
    while True:
        if not os.path.exists(LOCK):
                _pay = ('module: %s\npid: %d\nstarted: %s\n'
                        'host: %s\n'
                        % (module, os.getpid(),
                           time.strftime('%Y-%m-%d %H:%M:%S'),
                           os.environ.get('COMPUTERNAME', '?')))
                if machine_lock_app.write_lock_atomic(LOCK, _pay):
                    print('[lock] 已取得 %s' % LOCK)
                    return True
        try:
            raw = io.open(LOCK, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            raw = ''
        pid = _read_lock_pid(raw)
        if pid and not _pid_alive(pid):
            print('[lock] 陈旧锁（pid=%d 已死）→ 回收' % pid)
            try:
                os.remove(LOCK)
            except OSError:
                pass
            continue
        if time.time() - t0 > timeout_s:
            print('[lock] 等锁超时 ⇒ 放弃')
            return False
        print('[lock] 等待中…（已等 %.0fs）' % (time.time() - t0), flush=True)
        time.sleep(10.0)


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except OSError:
        pass


def _cp_decode_ir_path(eng, model_root):
    """定位 cp_decode 的 IR。

    🔴 `MultiDecoderBabelVox`（App 用的类）**没有** `_ir_path`
    （那是 `QuantEvalBabelVox` 才有的）⇒ 走原生路径：
    `model_dir = export_dir / precision` ⇒ `.../int8/cp_decode.xml`。
    """
    fn = getattr(eng, '_ir_path', None)
    if callable(fn):
        return fn('cp_decode')
    root = getattr(eng, '_model_dir', None)
    if not root:
        root = os.path.join(model_root, 'int8')
    return os.path.join(root, 'cp_decode.xml')


def _recompile_cp_decode_npu(eng, core, model_root):
    """把 cp_decode 用**固定形状**重编译到 NPU（与 TTS 模块同一把尺子）。

    🔴🔴 **必须 reshape**：动态维 IR 直接编到 NPU 会 **Segfault**
    （进程直接崩，try/except 接不住）—— 见 `eval_cp_on_npu.py` 的 docstring。
    """
    t0 = time.perf_counter()
    ir = _cp_decode_ir_path(eng, model_root)
    m = core.read_model(ir)
    m.reshape(CP_SHAPE)
    cm = core.compile_model(m, 'NPU')
    dt = time.perf_counter() - t0
    eng.cp_decode = cm
    eng.cp_on_cpu = False
    return dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--no-lock', action='store_true')
    ap.add_argument('--skip-quiet', action='store_true',
                    help='跳过安静窗口闸门（必须在日志里写明理由）')
    ap.add_argument('--quiet-max-wait', type=float, default=1800.0)
    args = ap.parse_args()

    # 🔴 顺序铁律：**客户包优先** ⇒ 仓库 live_caption 只能 append，
    #    否则 tts_engine 会被解析成仓库版（模型不在仓库里 ⇒ 找不到）。
    sys.path.insert(0, os.path.join(PKG, 'app'))
    sys.path.append(os.path.join(HERE, '..', '..', 'live_caption'))
    sys.path.insert(0, os.path.join(PKG, 'python', 'Lib', 'site-packages'))
    os.chdir(PKG)

    if not args.no_lock and not acquire_lock('app-062'):
        return 2

    # 🔴🔴 **安静窗口闸门**：计时前必须确认「没有别的推理作业在跑」。
    #   实测教训：ASR 的 `p3_ov_app.py --device NPU` 并发跑（且**不持锁**）
    #   ⇒ 同一脚本两跑 RTF 中位 2.284 → 3.256（差 1.43×）。
    # 🔴 按**文件路径**加载 proc_guard（不依赖 sys.path 顺序）
    import importlib.util as _ilu
    _pg_path = os.path.join(HERE, 'proc_guard.py')
    _spec = _ilu.spec_from_file_location('proc_guard', _pg_path)
    _pg = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_pg)
    QuietGate = _pg.QuietGate
    gate = QuietGate()
    # 🔴🔴 闸门必须**先自检**：读不到命令行 ⇒ 不能声称「无污染」
    gate_ok = gate.self_test()
    quiet_ok = gate.wait_quiet(max_wait_s=args.quiet_max_wait,
                               require_two_rounds=not args.skip_quiet,
                               skip=args.skip_quiet)
    print('[quiet] 闸门自检=%s  安静窗口=%s' % (gate_ok, quiet_ok))

    rec = {'experiment': 'APP-062 cp_decode 设备 A/B（CPU vs NPU）',
           'precision': args.precision,
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           # 🔴🔴 这两个字段**必须落真实值**（曾经写成 None ⇒ 报告无法自证
           #    「数据是不是在安静窗口里测的」⇒ 不可追溯）。
           'quiet_ok': quiet_ok,
           'gate_self_test': gate_ok,
           'skip_quiet': bool(args.skip_quiet),
           'texts': TEXTS}
    try:
        import numpy as np
        import openvino as ov
        import tts_engine

        print('\n=== 加载引擎（生产配置：NPU/int8/ctx25/chunk8/spkonly）===')
        t0 = time.perf_counter()
        eng = tts_engine.make_engine(device=args.device,
                                     precision=args.precision,
                                     on_log=lambda m: print('  ' + m))
        rec['load_s'] = round(time.perf_counter() - t0, 2)
        print('  加载 %.1f s' % rec['load_s'])

        # 记录 cp_decode 当前设备（基线应为 CPU）
        # 🔴 判据用 `eng.cp_on_cpu`（原生 pipeline.py L181/L356 设的标志位）：
        #    CompiledModel **没有** `get_property('DEVICE')` ⇒ 不能靠它。
        cp_dev = 'CPU' if getattr(eng, 'cp_on_cpu', False) else 'NPU(?)'
        rec['arm_A_cp_decode_device'] = cp_dev
        rec['arm_A_cp_on_cpu_flag'] = bool(getattr(eng, 'cp_on_cpu', False))
        print('  基线 cp_decode 设备 = %s（cp_on_cpu=%s）'
              % (cp_dev, rec['arm_A_cp_on_cpu_flag']))

        ref = tts_engine.preset_voice_path()
        spk = tts_engine.speaker_embedding(eng, ref,
                                           on_log=lambda m: print('  ' + m))
        rec['spk_ok'] = spk is not None

        # 预热（排除首次编译/首帧）
        t0 = time.perf_counter()
        _ = list(tts_engine.stream(eng, '预热。', language='Chinese',
                                   speaker_embed=spk))
        rec['warmup_s'] = round(time.perf_counter() - t0, 2)
        print('  预热 %.1f s' % rec['warmup_s'])

        def synth_one(text):
            t = time.perf_counter()
            t_first = None
            total = 0
            for w, sr in tts_engine.stream(eng, text, language='Chinese',
                                           speaker_embed=spk):
                if t_first is None:
                    t_first = time.perf_counter() - t
                total += len(w)
            t_all = time.perf_counter() - t
            return (t_first, t_all, total / 24000.0)

        def run_arm(name):
            print('\n=== 臂 %s ===' % name)
            rows = []
            for i, txt in enumerate(TEXTS):
                tf, ta, au = synth_one(txt)
                rtf = (ta / au) if au else None
                rows.append({'id': i, 't_first': round(tf, 3),
                             't_all': round(ta, 3),
                             'audio_s': round(au, 2),
                             'rtf': round(rtf, 3) if rtf else None,
                             **_lock_probe_fields()})
                print('  句%d 首块 %.3f s  整句 %.3f s  音频 %.2f s  RTF %.3f'
                      % (i, tf, ta, au, rtf or 0))
            rtfs = [r['rtf'] for r in rows if r['rtf']]
            wall = sum(r['t_all'] for r in rows)
            audio = sum(r['audio_s'] for r in rows)
            out = {
                'rows': rows,
                'rtf_median': round(statistics.median(rtfs), 3) if rtfs else None,
                'first_block_median': round(
                    statistics.median([r['t_first'] for r in rows]), 3),
                'wall_s': round(wall, 2),
                'audio_total_s': round(audio, 2),
                'aggregate_rtf': round(wall / max(audio, 1e-9), 3),
            }
            print('  ⇒ 单句 RTF 中位 %.3f  首块中位 %.3f s  聚合 RTF %.3f'
                  % (out['rtf_median'], out['first_block_median'],
                     out['aggregate_rtf']))
            return out

        # ── A 臂：cp_decode 留在 CPU（= 现在的 App 行为）──
        rec['arm_A'] = run_arm('A：cp_decode=CPU（App 现状）')

        # ── 切设备（只改这一个变量）──
        print('\n=== 把 cp_decode 重编译到 NPU（reshape 定形状）===')
        core = ov.Core()
        try:
            cdir = tts_engine._cache_dir()
            core.set_property({'CACHE_DIR': cdir})
        except Exception:
            pass
        try:
            dt = _recompile_cp_decode_npu(eng, core, tts_engine.model_root())
            rec['arm_B_recompile_s'] = round(dt, 2)
            print('  ✅ cp_decode → NPU，编译 %.2f s' % dt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            rec['arm_B_error'] = '%s: %s' % (type(e).__name__, e)
            rec['verdict'] = False
            raise
        try:
            cp_dev_b = 'CPU' if getattr(eng, 'cp_on_cpu', False) else 'NPU'
        except Exception:
            cp_dev_b = 'unknown'
        rec['arm_B_cp_decode_device'] = cp_dev_b
        rec['arm_B_cp_on_cpu_flag'] = bool(getattr(eng, 'cp_on_cpu', False))
        print('  B 臂 cp_decode 设备 = %s（cp_on_cpu=%s）'
              % (cp_dev_b, rec['arm_B_cp_on_cpu_flag']))

        # ── B 臂：cp_decode 在 NPU ──
        rec['arm_B'] = run_arm('B：cp_decode=NPU')

        # ── 汇总 ──
        a, b = rec['arm_A'], rec['arm_B']
        rec['delta_rtf_median'] = round(b['rtf_median'] - a['rtf_median'], 3)
        rec['delta_first_block_median'] = round(
            b['first_block_median'] - a['first_block_median'], 3)
        rec['speedup_rtf_median'] = round(
            a['rtf_median'] / b['rtf_median'], 3) if b['rtf_median'] else None
        rec['speedup_first_block'] = round(
            a['first_block_median'] / b['first_block_median'], 3) \
            if b['first_block_median'] else None
        print('\n===== 结论 =====')
        print('  单句 RTF 中位：CPU %.3f → NPU %.3f  （提速 %.2f×）'
              % (a['rtf_median'], b['rtf_median'],
                 rec['speedup_rtf_median'] or 0))
        print('  首块中位：     CPU %.3f s → NPU %.3f s  （提速 %.2f×）'
              % (a['first_block_median'], b['first_block_median'],
                 rec['speedup_first_block'] or 0))
        print('  聚合 RTF：     CPU %.3f → NPU %.3f'
              % (a['aggregate_rtf'], b['aggregate_rtf']))
        rec['verdict'] = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        rec.setdefault('error', '%s: %s' % (type(e).__name__, e))
        rec.setdefault('verdict', False)
    finally:
        if not args.no_lock:
            release_lock()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'app062_cp_decode_device_ab.json')
    io.open(out, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结果：%s' % out)
    return 0 if rec.get('verdict') else 1


if __name__ == '__main__':
    sys.exit(main())
