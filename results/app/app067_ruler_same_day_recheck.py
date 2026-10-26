#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-067：**同日同机复测「尺子」**，判定 App 与尺子的差距是否真的存在。

## 为什么要做这件事

reviewer APP-018 的核心假设是：
> 「App 首包 5.5 s、丢句 57%」 vs 「TTS 模块单测 RTF 0.79–0.86、首包约 0.5 s」
> ⇒ **问题出在 App 的集成层**。

App 侧修完两处（首包计时起点 + `cp_decode` 放 NPU）后，**同进程 A/B** 已经把
RTF 从 1.912 压到 1.218–1.33（`app062` / `app065`）。
但尺子的 **0.8568** 仍然够不到 ⇒ 要么「App 集成层还有残余」，要么……

🔴🔴 **要么这个 0.8568 本身是「跨天」的数**：
尺子 manifest 的时间戳是 **2026-10-25 15:14**，而 App 的复测在 **2026-10-26 11:16**
⇒ 两天的机器状态（NPU 热/后台作业/驱动）不同 ⇒ **两个数不可直接对话**
（这正是本仓库吃过多次亏的「不同一把尺子」问题）。

**已经逐个排除的候选原因**（都是逐字节/逐版本核对的，不是猜）：

| 候选 | 结论 |
|---|---|
| `babelvox/pipeline.py` | 逐字节一致（md5 `ae57530c…`） |
| patch 文件（App vs 尺子） | md5 完全一致 |
| OpenVINO / numpy 版本 | 完全相同 |
| 调用路径（`generate_stream` + chunk 8 + ctx 25） | 相同 |
| `cp_decode` 设备 | **App 曾是 CPU** ⇒ §49.2 已修（1.57×），现两边都 NPU |
| `cp_prefill` 设备 | 两边都 **CPU**（App patch 的 NPU 路径 L379-382 显式编 CPU） |
| `INFERENCE_PRECISION_HINT` | App 注入 f16、尺子不注入 ⇒ **`app065` 实测效应 −0.018 ≤ 漂移 0.061 ⇒ 不成立** |
| `zh-num` 归一 | App 也有（`ZH_NUM_RULES_VERSION='zh-num-v1.0'`） |
| 句长 | 尺子「短句组」RTF 0.8263 **比整体还快** ⇒ 不是句长效应 |

⇒ 只剩「**机器状态跨天漂移**」这一条最可疑 ⇒ **必须今天再跑一次尺子**。

## 做法

1. 持共享机器锁（尺子自己要计时）；
2. 用**尺子自己的 python**（`qwen3tts_eval/.venv-qwen3tts`）
   跑 `eval_final_config_timing.py --voice A`；
3. 🔴 **`--out` 指到仓库外**（`C:\\Users\\Trekker-PTL\\abba_out\\app067_ruler_today`）
   ⇒ **绝不写进 TTS 模块的 results/**（守模块边界）；
4. 读回 `manifest.json`，与 App 的 `app065` 结果并排打印。

## 纪律

- 🔴 持共享机器锁；只跑一次，不重试刷数（尺子自己有 `--retry-invalid`）。
- 🔴 **不改 TTS 模块任何文件**（只执行它的脚本 + 把产物指到别处）。
- 🔴 产物写仓库外。

用法：
    python results/app/app067_ruler_same_day_recheck.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'

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

OUT = os.path.join(HOME, 'abba_out', 'app067_ruler_today')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
RULER_PY = os.path.join(HOME, 'qwen3tts_eval', '.venv-qwen3tts', 'Scripts', 'python.exe')
RULER_CWD = os.path.join(HOME, 'qwen3tts_eval')
RULER_SCRIPT = 'eval_final_config_timing.py'
OLD_MANIFEST = os.path.join(HOME, 'qwen3tts_eval', 'results', 'voice_ac',
                            'final_config', 'manifest.json')
APP_JSON = os.path.join(HOME, 'abba_out', 'app065_precision_hint_ab.json')


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
            return code.value == 259
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


def acquire_lock(module='app-067', timeout_s=3600.0):
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
                    print('[lock] 已取得')
                    return True
        try:
            raw = open(LOCK, encoding='utf-8', errors='replace').read()
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
            return False
        time.sleep(5)


def release_lock():
    try:
        raw = open(LOCK, encoding='utf-8', errors='replace').read()
        if _read_lock_pid(raw) == os.getpid():
            os.remove(LOCK)
            print('[lock] 已释放')
    except Exception:
        pass


def load_manifest(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception as e:
        print('!! 读不了 %s: %s' % (p, e))
        return None


def main() -> int:
    for p in (RULER_PY, os.path.join(RULER_CWD, RULER_SCRIPT)):
        if not os.path.isfile(p):
            print('!! 找不到 %s' % p)
            return 1
    os.makedirs(OUT, exist_ok=True)

    old = load_manifest(OLD_MANIFEST)
    old_a = (old or {}).get('A') or {}

    if not acquire_lock():
        return 2
    rc = 0
    try:
        cmd = [RULER_PY, RULER_SCRIPT,
               '--voice', 'A',
               '--out', OUT,
               '--tag', 'recheck_s49',
               '--retry-invalid',
               '--max-rounds', '6']
        print('[ruler] %s' % ' '.join(cmd))
        t0 = time.time()
        # 🔴 不捕获输出到内存（可能很长）⇒ 直接透传
        rc = subprocess.call(cmd, cwd=RULER_CWD)
        print('[ruler] 退出码 %d，用时 %.0f s' % (rc, time.time() - t0))
    finally:
        release_lock()

    # 🔴 尺子写的是 `manifest_<voice>.json`（不是 `manifest.json`）
    new = load_manifest(os.path.join(OUT, 'manifest_A.json'))
    # 该文件本身就是 single-voice 结构 ⇒ 顶层的 "A" 键可能有也可能没有
    new_a = (new or {}).get('A') or (new or {})
    sna = new_a.get('summary') or {}
    soa = old_a.get('summary') or {}
    app = {}
    try:
        app = json.load(open(APP_JSON, encoding='utf-8'))
    except Exception:
        pass
    app_rtf = (app.get('baseline_rtf_median')
               or (app.get('arm_A2') or {}).get('rtf_median'))

    print('\n' + '=' * 68)
    print('  尺子 RTF 中位：10-25 = %s   今天 = %s'
          % (soa.get('rtf_median_all'), sna.get('rtf_median_all')))
    print('  尺子首包中位  ：10-25 = %s   今天 = %s'
          % (soa.get('first_packet_median_all'),
             sna.get('first_packet_median_all')))
    print('  App 同配置    ：app065 基线 = %s' % app_rtf)
    print('  App/尺子(今天) = %s'
          % (round(app_rtf / sna['rtf_median_all'], 3)
             if app_rtf and sna.get('rtf_median_all') else 'n/a'))
    print('  尺子今天 invalid  = %s / %s'
          % (sna.get('n_timing_invalid'), sna.get('n')))
    print('=' * 68)

    rec = {
        'experiment': 'APP-067 尺子同日同机复测（判定跨天漂移）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'ruler_rc': rc,
        'ruler_old': {'created': old_a.get('created'),
                      'rtf_median': soa.get('rtf_median_all'),
                      'first_packet_median': soa.get('first_packet_median_all')},
        'ruler_today': {'created': new_a.get('created'),
                        'rtf_median': sna.get('rtf_median_all'),
                        'first_packet_median': sna.get('first_packet_median_all'),
                        'n': sna.get('n'),
                        'n_timing_invalid': sna.get('n_timing_invalid')},
        'app_baseline_rtf': app_rtf,
    }
    try:
        open(os.path.join(HOME, 'abba_out', 'app067_ruler_recheck.json'),
             'w', encoding='utf-8', newline='').write(
                 json.dumps(rec, ensure_ascii=False, indent=1))
        print('产物：%s' % os.path.join(HOME, 'abba_out', 'app067_ruler_recheck.json'))
    except Exception:
        pass
    return 0 if rc == 0 else rc


if __name__ == '__main__':
    sys.exit(main())
