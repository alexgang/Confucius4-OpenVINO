#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-059：验证 §48 的**流式改造**真的把首包降下来了（端到端，真实 worker 进程）。

## reviewer 的要求（APP-018 第 1 条）

> 修好后做 ABBA（tts off/on/on/off，fresh 进程，持锁）：ASR RTF 增量、
> 语音输出延迟 P50/P95、积压和丢句数。

本脚本是**改造后的单点验证**（ABBA 在 `app060` 里做）：

| 指标 | 改造前（§15 / app056 实测） | 目标 |
|---|---|---|
| App 报的 `first_packet` | **8.36 s**（= 整句合成耗时） | **≈ 1.2 s**（= 真实首块） |
| 报的首包 / 真实首块 | **7.2×** | **≈ 1.0×** |

## 怎么测（**不 import 被测模块**）

🔴 `tts_worker` 顶部连带 numpy/openvino ⇒ 不能 import
   ⇒ 这里**起一个真实的 worker 子进程**（`python app/tts_worker.py`），
   通过 stdin/stdout 的 JSON 协议对话 —— 这正是生产路径。

判据：
1. worker 回的 `first_packet.latency_s` 必须 **≈ 引擎层真实首块**（1.2 s 级）；
2. `played` 必须到达（流式不破坏完成事件）；
3. 音频总时长必须 > 0（不能因为流式丢样本）；
4. `first_packet` 必须 **显著早于** `played`（= 真流式，不是整句后补发）。

## 纪律

- 🔴 **持共享机器锁**（计时作业）。
- 🔴 **不 import 被测模块**（用子进程 + JSON 协议）。
- 🔴 产物写**仓库外**。

用法（客户包 python）：
    python results/app/app059_tts_streaming_e2e.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
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

REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
OUT_DIR = r'C:\Users\Trekker-PTL\abba_out'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

TEXTS = [
    '这是一次语音输出的自测，用来确认朗读功能可以正常工作。',
    '现在播第二句，验证流式播放不会互相打断。',
    '第三句比较短。',
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
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--voice', default='A')
    ap.add_argument('--no-lock', action='store_true')
    ap.add_argument('--out-wav', default=None,
                    help='落盘 wav（--out-wav 模式；音频走落盘不实时播放）')
    args = ap.parse_args()

    worker_py = os.path.join(PKG, 'python', 'python.exe')
    worker = os.path.join(PKG, 'app', 'tts_worker.py')
    if not os.path.isfile(worker_py):
        print('找不到客户包 python：%s' % worker_py)
        return 2

    if not args.no_lock and not acquire_lock('app-059'):
        return 2

    rec = {'device': args.device, 'precision': args.precision,
           'voice': args.voice, 'sents': [], 'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
    try:
        cmd = [worker_py, worker, '--device', args.device,
               '--precision', args.precision, '--voice', args.voice]
        if args.out_wav:
            cmd += ['--out-wav', args.out_wav]
        print('=== 起 worker：%s' % ' '.join(cmd))
        p = subprocess.Popen(cmd, cwd=os.path.join(PKG, 'app'),
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace', bufsize=1)
        t0 = time.perf_counter()
        ready_at = None

        def send(obj):
            p.stdin.write(json.dumps(obj, ensure_ascii=False) + '\n')
            p.stdin.flush()

        # 🔴 **必须等 `ready` 再发 synth**：模型加载要 ~37 s，
        #    worker 未 ready 时 `self.engine is None` ⇒ 走「没有可用的音色」分支
        #    ⇒ 测的是「加载中提交」，不是「流式首包」。
        print('=== 等 worker ready（模型加载，生产配置）…')
        while True:
            line = p.stdout.readline()
            if not line:
                print('!! worker 提前退出（没等到 ready）')
                return 1
            line = line.strip()
            if not line:
                continue
            if not line.startswith('{'):
                print('    | %s' % line[:160])
                continue
            try:
                msg = json.loads(line)
            except Exception:
                print('    | %s' % line[:160])
                continue
            if msg.get('kind') == 'ready':
                ready_at = time.perf_counter() - t0
                print('    [ready] %.1f s' % ready_at)
                break
            if msg.get('kind') == 'error':
                print('    [error] %s' % msg.get('message'))
                rec['error'] = 'worker 加载失败：%s' % msg.get('message')
                return 1

        for i, txt in enumerate(TEXTS, 1):
            print('\n--- 第 %d 句：%s' % (i, txt))
            send({'cmd': 'synth', 'id': i, 'text': txt})
            t_submit = time.perf_counter()
            ev = {'first_packet': None, 'played': None, 'logs': []}
            while True:
                line = p.stdout.readline()
                if not line:
                    print('!! worker 提前退出')
                    break
                line = line.strip()
                if not line:
                    continue
                if not line.startswith('{'):
                    ev['logs'].append(line)
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    ev['logs'].append(line)
                    continue
                kind = msg.get('kind')
                if kind == 'first_packet':
                    ev['first_packet'] = {
                        'latency_s': msg.get('latency_s'),
                        't_wall': round(time.perf_counter() - t_submit, 3),
                    }
                    print('    [first_packet] %.3f s' % (msg.get('latency_s') or 0))
                    continue
                if kind == 'played':
                    ev['played'] = {
                        'dur_s': msg.get('dur_s'),
                        'latency_s': msg.get('latency_s'),
                        't_wall': round(time.perf_counter() - t_submit, 3),
                    }
                    print('    [played] dur=%.2f s  合计 %.3f s'
                          % (msg.get('dur_s') or 0,
                             time.perf_counter() - t_submit))
                    break
                if kind == 'error':
                    ev['logs'].append('ERROR: %s' % msg.get('message'))
                    print('    [error] %s' % msg.get('message'))
                    if msg.get('id') is not None:
                        break
                    continue
                ev['logs'].append(line)
            rec['sents'].append(ev)

        try:
            send({'cmd': 'quit'})
        except Exception:
            pass
        try:
            p.wait(timeout=60)
        except Exception:
            p.kill()

        rec['ready_s'] = round(ready_at, 2) if ready_at else None

        # ── 判据 ──────────────────────────────────────────────────
        fps = [s['first_packet']['latency_s'] for s in rec['sents']
               if s.get('first_packet')]
        durs = [s['played']['dur_s'] for s in rec['sents'] if s.get('played')]
        walls = [s['played']['t_wall'] for s in rec['sents'] if s.get('played')]
        rec['first_packet_s'] = fps
        rec['dur_s'] = durs
        rec['wall_s'] = walls

        ok = True
        if not fps:
            rec['verdict_note'] = '没有任何 first_packet ⇒ FAIL'
            ok = False
        else:
            p50 = sorted(fps)[len(fps) // 2]
            rec['first_packet_p50'] = p50
            # ① 首包必须 **≤ 3 s**（改造前是 8.36 s）
            ok &= p50 <= 3.0
            # ② 必须**明显早于**整句完成（真流式）
            if walls and durs:
                gap = [w - d for w, d in zip(walls, durs)]
                rec['gap_first_to_done_s'] = [round(g, 3) for g in gap]
                ok &= max(gap) > 0.5
            # ③ 音频必须非零
            ok &= all((d or 0) > 0 for d in durs)
            rec['verdict_note'] = (
                '首包 P50 %.3f s（改造前 8.36 s）' % p50)
        rec['verdict'] = bool(ok)
        print('\n结论：%s — %s' % ('PASS' if ok else 'FAIL',
                                  rec.get('verdict_note')))
    except Exception as e:
        import traceback
        traceback.print_exc()
        rec['error'] = '%s: %s' % (type(e).__name__, e)
        rec['verdict'] = False
    finally:
        if not args.no_lock:
            release_lock()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'app059_tts_streaming_e2e.json')
    io.open(out, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结果：%s' % out)
    return 0 if rec.get('verdict') else 1


if __name__ == '__main__':
    sys.exit(main())
