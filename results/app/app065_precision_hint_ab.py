#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-065：`INFERENCE_PRECISION_HINT` 是不是 App 比「尺子」慢 1.42× 的原因？

## 问题的来源（APP-018 第 1 条）

修完 `cp_decode → NPU` 之后（§49.2），App 的单句 RTF 中位是 **1.218**，
但 TTS 模块的「尺子」（`qwen3tts_eval/results/voice_ac/final_config/manifest.json`）
在**同设备、同精度、同 chunk、同 ctx、同 spkonly** 下是 **0.8568**。

⇒ 还差 **1.42×**。已经排除的因素（都是**逐字节/逐版本核对**过的，不是猜的）：

| 候选原因 | 核对结果 |
|---|---|
| `babelvox/pipeline.py` 版本 | **逐字节一致**（1239 行，md5 `ae57530c…` 两边相同） |
| `tts_engine_patch.py`（App）vs `qwen3tts_patch.py`（尺子） | md5 **完全一致** |
| OpenVINO 版本 | 两边都是 `2026.4.1-22982-e213a147257` |
| numpy 版本 | 两边都是 `2.4.6` |
| 调用方式 | 两边都是 `generate_stream` + `chunk_frames=8` + `ctx_frames=25` |
| 句子长度量级 | 尺子 `dur_median=3.68 s`；本脚本同批句子 3.4–5.1 s ⇒ **同量级** |
| 挂表方式 | 两边都是 `rtf = 整句合成秒 / 音频秒`、`first_packet = 首块秒` |

**唯一剩下的差异**：App 的 `make_engine()` 会通过 `_ov_precision()`
**给 NPU 注入 `INFERENCE_PRECISION_HINT=f16`**（`tts_engine.py` L460），
而尺子**从不注入任何 hint**（`eval_final_config_timing.py` 里没有 `set_property`）。

🔴 **假设 H4**：NPU 上的 INT8 IR 本来就该走它的默认精度，
   而强制 `f16` 反而让 OP 之间插入 f16↔int8 的 reorder/convert ⇒ **变慢**。

## 本脚本要回答的

| 臂 | hint | 期望 |
|---|---|---|
| A | `f16`（**App 现状**） | 复现 1.218 |
| B | **不注入**（= 尺子的做法） | 若显著更快 ⇒ H4 成立 |
| A2 | `f16`（**再测一次**） | 排除「越跑越热/缓存变好」的单向漂移 |

⇒ **A/B/A** 结构（不是 A/B）⇒ 能把「次序效应」与「hint 效应」分开。

## 纪律

- 🔴 **持共享机器锁**（计时作业）。
- 🔴 **安静窗口闸门**（`proc_guard.py`）⇒ 别的模块**不持锁**的作业照样会污染。
- 🔴 客户包 python（`Confucius4_LiveCaption_v1.5/python/python.exe`）。
- 🔴 产物写**仓库外**（`C:\\Users\\Trekker-PTL\\abba_out\\`）。
- ⚠️ 本脚本**只测不改产品代码**：抑制 hint 靠**进程内**临时替换
  `tts_engine._ov_precision`（跑完即结束，不落盘）。

用法：
    python results/app/app065_precision_hint_ab.py
    python results/app/app065_precision_hint_ab.py --skip-quiet   # 并写明理由
"""
from __future__ import annotations

import argparse
import contextlib
import gc
import importlib.util as ilu
import io
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

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

HOME = r'C:\Users\Trekker-PTL'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v1.5')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
OUT = os.path.join(HOME, 'abba_out', 'app065_precision_hint_ab.json')

# 与 `app061` / `app062` **同一批句子** ⇒ 三份结果可直接对照
TEXTS = [
    '大家早上好，欢迎参加季度工程评审会。',
    '今天，我想与团队一起探讨三个主要主题。',
    '首先，我们将看看上次测量的推理延迟数据。',
    '其次，包装流程得到了大幅简化。',
    '第三，我们希望简化流程，讨论下一次发布的路线图。',
    '如果还有任何问题，请随时告诉我，我们继续吧。',
]


# ---------------------------------------------------------------------------
# 机器锁（与 app062 同一套：fail-closed + 陈旧锁可回收 + 两种格式都认）
# ---------------------------------------------------------------------------
def _pid_alive(pid: int) -> bool:
    import ctypes
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code)):
            return code.value == 259      # STILL_ACTIVE
        return False
    finally:
        k.CloseHandle(ctypes.c_void_p(h))


def _read_lock_pid(raw: str):
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


def acquire_lock(module='app-065', timeout_s=3600.0):
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
        time.sleep(5)


def release_lock():
    try:
        raw = io.open(LOCK, 'r', encoding='utf-8', errors='replace').read()
        if _read_lock_pid(raw) == os.getpid():
            os.remove(LOCK)
            print('[lock] 已释放')
    except Exception:
        pass


def load_proc_guard():
    """🔴 按**文件路径**加载 ⇒ 不依赖 sys.path 顺序（仓库 live_caption 只能 append）。"""
    p = os.path.join(HERE, 'proc_guard.py')
    spec = ilu.spec_from_file_location('proc_guard', p)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--no-lock', action='store_true')
    ap.add_argument('--skip-quiet', action='store_true',
                    help='跳过安静窗口闸门（必须在日志里写明理由）')
    ap.add_argument('--quiet-max-wait', type=float, default=1800.0)
    args = ap.parse_args()

    # 🔴 客户包优先：仓库 live_caption 只能 append
    sys.path.insert(0, os.path.join(PKG, 'app'))
    sys.path.append(os.path.join(REPO, 'live_caption'))
    sys.path.insert(0, os.path.join(PKG, 'python', 'Lib', 'site-packages'))
    os.chdir(PKG)

    if not args.no_lock and not acquire_lock():
        return 2

    gate_ok = quiet_ok = None
    try:
        pg = load_proc_guard()
        gate = pg.QuietGate()
        gate_ok = gate.self_test()
        quiet_ok = gate.wait_quiet(max_wait_s=args.quiet_max_wait,
                                   require_two_rounds=not args.skip_quiet,
                                   skip=args.skip_quiet)
        print('[quiet] 自检=%s  安静窗口=%s' % (gate_ok, quiet_ok))
    except Exception as e:
        print('[quiet] ⚠️ 闸门不可用（%s: %s）⇒ 结果需标注可疑' % (type(e).__name__, e))

    rec = {
        'experiment': 'APP-065 INFERENCE_PRECISION_HINT A/B/A（f16 vs 不注入）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'device': args.device,
        'precision': args.precision,
        'gate_self_test': gate_ok,
        'quiet_ok': quiet_ok,
        'skip_quiet': bool(args.skip_quiet),
        'texts': TEXTS,
        'hypothesis': 'App 注入 f16 反而比不注入慢（NPU 上的 INT8 IR 有默认精度）',
    }

    try:
        import tts_engine

        orig_ov_precision = tts_engine._ov_precision

        @contextlib.contextmanager
        def _no_hint(*a, **kw):
            """**不注入任何 hint**（= 尺子的做法）。"""
            yield

        def synth_one(eng, spk, text):
            t = time.perf_counter()
            t_first = None
            total = 0
            for w, sr in tts_engine.stream(eng, text, language='Chinese',
                                           speaker_embed=spk):
                if t_first is None:
                    t_first = time.perf_counter() - t
                total += len(w)
            t_all = time.perf_counter() - t
            return t_first, t_all, total / 24000.0

        def run_arm(name, use_hint):
            """建一个新引擎（hint 在**编译期**生效 ⇒ 必须重建引擎）。"""
            print('\n=== 臂 %s（hint=%s）===' % (name, 'f16' if use_hint else '不注入'))
            tts_engine._ov_precision = (orig_ov_precision if use_hint
                                        else _no_hint)
            t0 = time.perf_counter()
            eng = tts_engine.make_engine(device=args.device,
                                         precision=args.precision,
                                         on_log=lambda m: print('  ' + m))
            load_s = time.perf_counter() - t0
            ref = tts_engine.preset_voice_path()
            spk = tts_engine.speaker_embedding(eng, ref,
                                               on_log=lambda m: print('  ' + m))
            # 预热（排除首帧）
            list(tts_engine.stream(eng, '预热。', language='Chinese',
                                   speaker_embed=spk))
            rows = []
            for i, txt in enumerate(TEXTS):
                tf, ta, au = synth_one(eng, spk, txt)
                rtf = (ta / au) if au else None
                rows.append({'id': i, 't_first': round(tf, 3),
                             't_all': round(ta, 3),
                             'audio_s': round(au, 2),
                             'rtf': round(rtf, 3) if rtf else None})
                print('  句%d 首块 %.3f s  整句 %.3f s  音频 %.2f s  RTF %.3f'
                      % (i, tf, ta, au, rtf or 0))
            rtfs = [r['rtf'] for r in rows if r['rtf']]
            out = {
                'hint': 'f16' if use_hint else 'none',
                'load_s': round(load_s, 2),
                'rows': rows,
                'rtf_median': round(statistics.median(rtfs), 3) if rtfs else None,
                'first_block_median': round(
                    statistics.median([r['t_first'] for r in rows]), 3),
                'audio_total_s': round(sum(r['audio_s'] for r in rows), 2),
                'wall_s': round(sum(r['t_all'] for r in rows), 2),
            }
            out['aggregate_rtf'] = round(
                out['wall_s'] / max(out['audio_total_s'], 1e-9), 3)
            print('  ⇒ RTF 中位 %.3f  首块中位 %.3f s  聚合 RTF %.3f'
                  % (out['rtf_median'], out['first_block_median'],
                     out['aggregate_rtf']))
            # 释放引擎（NPU 显存/内存有限 ⇒ 必须回收再建下一个）
            del eng, spk
            gc.collect()
            tts_engine._ov_precision = orig_ov_precision
            return out

        rec['arm_A'] = run_arm('A：hint=f16（App 现状）', True)
        rec['arm_B'] = run_arm('B：不注入 hint（尺子做法）', False)
        rec['arm_A2'] = run_arm('A2：hint=f16（复测，排除漂移）', True)

        a, b, a2 = rec['arm_A'], rec['arm_B'], rec['arm_A2']
        # 漂移 = A 与 A2 的差；hint 效应 = A/A2 均值 与 B 的差
        drift = abs(a2['rtf_median'] - a['rtf_median'])
        base = (a['rtf_median'] + a2['rtf_median']) / 2.0
        rec['A_A2_drift_rtf'] = round(drift, 3)
        rec['baseline_rtf_median'] = round(base, 3)
        rec['delta_rtf_median'] = round(b['rtf_median'] - base, 3)
        rec['speedup_rtf_median'] = round(base / b['rtf_median'], 3) \
            if b['rtf_median'] else None
        rec['delta_first_block_median'] = round(
            b['first_block_median']
            - (a['first_block_median'] + a2['first_block_median']) / 2.0, 3)
        # 判定：hint 效应必须**大于**漂移，才算真效应
        rec['effect_beyond_drift'] = bool(
            abs(b['rtf_median'] - base) > max(drift, 0.02))
        rec['verdict'] = rec['effect_beyond_drift']
        print('\n===== 汇总 =====')
        print('  A  %.3f | B  %.3f | A2 %.3f'
              % (a['rtf_median'], b['rtf_median'], a2['rtf_median']))
        print('  A↔A2 漂移 %.3f s；hint 效应 %+.3f（提速 %.2f×）'
              % (drift, rec['delta_rtf_median'],
                 rec['speedup_rtf_median'] or 0))
        print('  结论：%s'
              % ('hint 效应显著 ⇒ H4 成立' if rec['verdict']
                 else 'hint 效应 ≤ 漂移 ⇒ H4 不成立，差距在别处'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        rec['error'] = '%s: %s' % (type(e).__name__, e)
        rec['verdict'] = False
    finally:
        try:
            io.open(OUT, 'w', encoding='utf-8', newline='').write(
                json.dumps(rec, ensure_ascii=False, indent=1))
            print('\n产物：%s' % OUT)
        except Exception:
            pass
        if not args.no_lock:
            release_lock()
    return 0


if __name__ == '__main__':
    sys.exit(main())
