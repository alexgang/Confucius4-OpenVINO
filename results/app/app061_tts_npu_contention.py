#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-061：量化「NPU 争用」对 TTS 合成速度的影响（reviewer APP-018 第 1 条第 2 项）。

## reviewer 的问题

> 和 ASR、MT 同时运行时，**NPU 是否被争用**（ASR 是否也在 NPU 上）；
> TTS worker 是否用了生产配置……**编译缓存是否命中**（每次重新编译要 950 s）。

## 本探针要量的三件事（**不假设，只测**）

| # | 问题 | 指标 |
|---|---|---|
| Q1 | **TTS 单句合成速度**（引擎层，无干扰） | 单句 RTF、首包 |
| Q2 | **NPU 独占 vs 与 MT 共存** | 同上（MT 跑 NPU 时 TTS 的 RTF 变化） |
| Q3 | **同一进程内多句并发** vs **逐句串行** | 合成总速率（**注意：这是人为构造，不是 App 真实路径**，见下） |

## 🔴🔴🔴 **本脚本的 Q3 结论已被撤回（2026-10-26 §49）**

**原结论**（已作废）：「ABBA 实测里 7 句是同时提交的 ⇒ worker 里每个
`synth()` 各起一个线程 ⇒ 同一个 NPU 上并发跑 7 路推理 ⇒ 单句 RTF 从 0.8
飙到 2.6~3.0 ⇒ 这才是『丢句 57%』的真正机制」。

**错在哪**：
1. **`threads` 臂直接调引擎层，绕过了 worker 的 `_synth_lock`** ⇒
   它测的是**人为构造的并发**，**不是 App 真实行为**。
2. **App 真实路径是串行的**：`tts_worker.py` 的 `synth()` 把整段合成包在
   `with self._synth_lock:` 内 ⇒ worker 层**不存在并发推理**。
3. **ABBA 数据自己就否证了「并发」**：7 句的 `t_submit` 跨度仅 **0.0126 s**
   （确实同时提交），但**首包是递增的**（组 B：2.02 → 9.98 → 17.74 → 26.63
   → 28.71 → 35.59 → 46.27 s）⇒ 这是**串行队列**的特征，不是并发。

**真实机制（§49 更正后的口径）**：
**串行 + 单句 RTF > 1 ⇒ 第 N 句的首包 = 前 N−1 句耗时之和 ⇒ 排队累积
⇒ P95 首包 46–57 s ⇒ service 层积压超限 ⇒ 丢句。**

⇒ 治本方向**不是**「消除并发」（本来就没有并发），而是**把单句 RTF 压到 < 1**
（见 §49：cp_decode 放 NPU ⇒ RTF 中位 1.912 → 1.218）。

⚠️ **本脚本的 `threads` 臂仍然保留**（作为「人为并发下会退化多少」的对照数据），
但**不得再把它当成 App 真实机制的证据**。

## 纪律

- 🔴 **持共享机器锁**（计时作业）。
- 🔴 **不 import 被测模块**（`tts_worker` 顶部连带 numpy/openvino）
  ⇒ 这里只调**引擎层** `tts_engine`（真实路径，且它是纯 python 入口）。
- 🔴 **同一时刻只跑本脚本自己**（计时窗口内不启动任何别的 python.exe）。
- 🔴 产物写**仓库外**。

用法（客户包 python）：
    python results/app/app061_tts_npu_contention.py --mode solo
    python results/app/app061_tts_npu_contention.py --mode threads
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
OUT_DIR = r'C:\Users\Trekker-PTL\abba_out'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# 真实会议素材（自造的 TTS 语音，与 abba_input_16k.wav 同源）
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


def acquire_lock(module='app', timeout_s=3600.0):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    t0 = time.time()
    while True:
        if not os.path.exists(LOCK):
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, ('%s PID=%d started %s\n'
                              % (module, os.getpid(),
                                 time.strftime('%Y-%m-%d %H:%M:%S'))).encode('utf-8'))
                os.close(fd)
                print('[lock] 已取得 %s' % LOCK)
                return True
            except FileExistsError:
                pass
        try:
            raw = io.open(LOCK, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            raw = ''
        pid = None
        for ln in raw.split('\n'):
            if 'PID=' in ln.upper():
                try:
                    pid = int(ln.upper().split('PID=')[1].split()[0].strip())
                except Exception:
                    pid = None
                break
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='solo', choices=['solo', 'threads'],
                    help='solo=逐句串行；threads=模拟 App 的多句并发')
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--no-lock', action='store_true')
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(PKG, 'app'))
    sys.path.insert(0, os.path.join(PKG, 'python', 'Lib', 'site-packages'))
    os.chdir(PKG)

    if not args.no_lock and not acquire_lock('app-061'):
        return 2

    rec = {'mode': args.mode, 'device': args.device,
           'precision': args.precision,
           'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
    try:
        import numpy as np
        import tts_engine

        print('\n=== 加载引擎（生产配置）===')
        t0 = time.perf_counter()
        eng = tts_engine.make_engine(device=args.device,
                                     precision=args.precision,
                                     on_log=lambda m: print('  ' + m))
        rec['load_s'] = round(time.perf_counter() - t0, 2)
        print('  加载 %.1f s' % rec['load_s'])

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
            """合成一句，返回 (首块耗时, 整句耗时, 音频秒数)。"""
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

        if args.mode == 'solo':
            print('\n=== 逐句串行（每句都从头跑）===')
            rows = []
            for i, txt in enumerate(TEXTS):
                t_first, t_all, audio = synth_one(txt)
                rows.append({'id': i, 't_first': round(t_first, 3),
                             't_all': round(t_all, 3),
                             'audio_s': round(audio, 2),
                             'rtf': round(t_all / audio, 3) if audio else None})
                print('  句%d 首块 %.3f s  整句 %.3f s  音频 %.2f s  RTF %.3f'
                      % (i, t_first, t_all, audio, t_all / max(audio, 1e-9)))
            rec['rows'] = rows
            rtfs = [r['rtf'] for r in rows if r['rtf']]
            rec['rtf_median'] = round(statistics.median(rtfs), 3) if rtfs else None
            rec['first_block_median'] = round(
                statistics.median([r['t_first'] for r in rows]), 3)
            rec['wall_s'] = round(sum(r['t_all'] for r in rows), 2)
            rec['audio_total_s'] = round(sum(r['audio_s'] for r in rows), 2)
            rec['aggregate_rtf'] = round(
                rec['wall_s'] / max(rec['audio_total_s'], 1e-9), 3)
        else:
            print('\n=== 多句并发（模拟 App：N 句同时提交）===')
            results = {}
            lock = threading.Lock()

            def worker(i):
                tf, ta, au = synth_one(TEXTS[i])
                with lock:
                    results[i] = {'id': i, 't_first': round(tf, 3),
                                  't_all': round(ta, 3),
                                  'audio_s': round(au, 2),
                                  'rtf': round(ta / au, 3) if au else None}

            t_wall = time.perf_counter()
            ths = [threading.Thread(target=worker, args=(i,))
                   for i in range(len(TEXTS))]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
            total_wall = time.perf_counter() - t_wall
            rows = [results[i] for i in sorted(results)]
            for r in rows:
                print('  句%d 首块 %.3f s  整句 %.3f s  音频 %.2f s  RTF %.3f'
                      % (r['id'], r['t_first'], r['t_all'], r['audio_s'],
                         r['rtf']))
            rec['rows'] = rows
            rec['wall_s'] = round(total_wall, 2)
            rec['audio_total_s'] = round(sum(r['audio_s'] for r in rows), 2)
            rec['aggregate_rtf'] = round(
                total_wall / max(rec['audio_total_s'], 1e-9), 3)
            rtfs = [r['rtf'] for r in rows if r['rtf']]
            rec['rtf_median'] = round(statistics.median(rtfs), 3) if rtfs else None
            rec['first_block_median'] = round(
                statistics.median([r['t_first'] for r in rows]), 3)

        print('\n  串行/并发 汇总：墙钟 %.2f s  音频 %.2f s  聚合 RTF %.3f  单句 RTF 中位 %.3f'
              % (rec['wall_s'], rec['audio_total_s'], rec['aggregate_rtf'],
                 rec['rtf_median'] or 0))
        rec['verdict'] = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        rec['error'] = '%s: %s' % (type(e).__name__, e)
        rec['verdict'] = False
    finally:
        if not args.no_lock:
            release_lock()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'app061_tts_npu_contention_%s.json' % args.mode)
    io.open(out, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结果：%s' % out)
    return 0 if rec.get('verdict') else 1


if __name__ == '__main__':
    sys.exit(main())
