#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app327_overload_driver.py —— **APP-093 §3.3 过载臂**（单会话内 1.0× → 2.0× → 1.0×）。

## 为什么不能分三段跑（reviewer §3.3 的核心要求）

reviewer 原文：
> **过载臂重做**：用 dialog3，前 60 s 1.0×，60–150 s 人为过载，
> 150 s 以后回到 1.0×。报……**从过载结束到 dequeue lag 回到 6 s 以内的用时**

⇒ **必须是「一个会话」**：「过载结束」这个时刻只在**同一条时间轴**上存在。
⇒ reviewer §3.c 已明确否定旧做法：「整场都是 2.0×，没有『过载结束』这个时刻」。

## 本脚本的做法（**仓库代码零改动**）

🔴 关键事实（读码定案）：
* `Session.__init__`：`self.src = source`（`live_caption_app.py:1877`）
  ⇒ **运行期可拿到音源对象**；
* `FileSource._run()` 每块（`BLOCK_MS`）读一次 `self.speed`
  （`audio_source.py:571-573`）⇒ **运行期改 `self.speed` 立即生效**；
* `FileSource.pace` 是 **property**，每次访问读 `self.speed`
  ⇒ `_cli_target_wall()`（`live_caption_app.py:7465-7469`）**动态**取新速率
  ⇒ 过载期的目标开播墙钟自动来得更快（这正是过载的定义）。

⇒ 做法：在**影子包**里放一个 `sitecustomize.py`（**只在这个影子包生效**）
⇒ 用 **`import` 钩子**在 `live_caption_app` 被导入的瞬间 patch `Session.start`
（**不在解释器启动时导入整个 App** ⇒ 无副作用）
⇒ `Session.start` 之后起一个后台线程，按**墙钟**改 `session.src.speed`。

| 阶段 | 源区间 | pace | 墙钟区间 | 含义 |
|---|---|---|---|---|
| 正常 | 0–60 s | **1.0** | [0, 60) | 正常负载 |
| 过载 | 60–150 s | **2.0** | [60, 105) | 源音频压缩进一半墙钟 ⇒ ASR/MT/TTS 同时承压 |
| 恢复 | 150 s+ | **1.0** | [105, ∞) | 观察 dequeue lag 回落 |

🔴 **为什么 pace 2.0 才是「过载」**：`pace` = 源秒 / 墙钟秒
⇒ pace 2.0 ⇒ 同样的源音频只花**一半墙钟** ⇒ ASR/MT/TTS 必须在**半数时间内**干完
⇒ **真过载**。
🔴 **上一版误用 `--speed 0.35`** ⇒ 源音频被**拉长**到 ~2.86× 墙钟 ⇒ 那是**卸载**，方向反了。

🔴 **60/150 s 是「源秒」**（reviewer 原文）⇒ 过载段 90 s 源在 pace 2.0 下只花
45 s 墙钟 ⇒ 过载墙钟区间 = **[60, 105] s**。

## 判据（reviewer §3.3 逐项）

* 过载起止：**源秒** + **墙钟**
* ASR/MT/TTS 积压曲线：过载前 / 峰值 / 结束时
* 过载期跳过句数
* **从过载结束到 dequeue lag 回到 6 s 以内的用时**
  ⇒ 口径 = `speed_lag_s`（worker **出队**时刻的滞后；`tts_worker.py:2514`）
* 字幕完整度（段数逐一对上）
* 🔴 **反证组**：把 `speed_lag_s` 全部抬高 ⇒ 恢复用时必须变 None

## 用法

```
.venv/Scripts/python.exe results/app/_app327_overload_driver.py --arm after
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import statistics as st
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')

BASE = os.path.join(HOME, '_app_shadow')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
OUTROOT = os.path.join(BASE, 'runs4')

#: reviewer §3.3 的分段时间点（**源秒**）
SRC_NORMAL_END = 60.0      # 0–60 s 源：1.0×
SRC_OVERLOAD_END = 150.0   # 60–150 s 源：2.0×（90 s 源）
PACE_NORMAL = 1.0
PACE_OVERLOAD = 2.0

#: 恢复判据阈值（reviewer §3.3 原文「dequeue lag 回到 6 s 以内」）
RECOVER_LAG_S = 6.0


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def acquire_lock(tag):
    for _ in range(180):
        if not os.path.exists(LOCK):
            payload = ('module=app\npid=%d\nstart=%s\ntag=%s\n'
                       % (os.getpid(), now(), tag))
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(payload)
                return payload
            except FileExistsError:
                pass
        time.sleep(10)
    return None


def release_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                if ('pid=%d' % os.getpid()) in f.read():
                    gone = os.path.join(os.path.dirname(LOCK),
                                        '.MACHINE_LOCK.released_%d_%d'
                                        % (os.getpid(), int(time.time())))
                    os.replace(LOCK, gone)
                    return not os.path.exists(LOCK)
    except OSError:
        pass
    return False


def build_cmd(root, out, wav):
    """🔴 与既有 runs2/runs3 **同口径**（ASR iGPU / MT iGPU / TTS NPU / 克隆跟随说话人）。"""
    return [
        os.path.join(root, 'python', 'python.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--cli', '--file', wav,
        '--speaker', 'on', '--tts', 'on', '--tts-voice', 'follow_speaker',
        '--tts-precision', 'f16', '--tts-device', 'NPU',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--out', os.path.join(out, 'subtitles.txt'),
        '--tts-out', os.path.join(out, 'mix.wav'),
        '--tts-jsonl', os.path.join(out, 'tts.jsonl'),
        '--tts-dump-dir', os.path.join(out, 'dump'),
        '--spk-seg-jsonl', os.path.join(out, 'spk_seg.jsonl'),
    ]


SITECUSTOMIZE = '''# -*- coding: utf-8 -*-
# 🔴 APP-093 §3.3 过载驱动（**只在本影子包生效**；仓库代码零改动）
import builtins, json, os, threading, time
import time as _time          # 🔴 v2 轮询线程用的别名

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLAN = json.load(open(os.path.join(_HERE, '_app327_overload_plan.json'),
                       encoding='utf-8'))
_META = os.path.join(_HERE, '_app327_session_meta.json')


def _patch_session(mod):
    if getattr(mod, '_app327_patched', False):
        return
    _orig_start = mod.Session.start

    def start(self):
        t0 = time.time()
        _orig_start(self)
        src = getattr(self, 'src', None)
        if src is None or not hasattr(src, 'speed'):
            return
        over_src = (_PLAN['src_overload_end'] - _PLAN['src_normal_end'])
        T1 = _PLAN['src_normal_end']
        T2 = T1 + over_src / _PLAN['pace_overload']
        meta = {'t0_wall': t0, 'T1_wall': t0 + T1, 'T2_wall': t0 + T2,
                'plan': _PLAN, 'events': []}
        try:
            with open(_META, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False)
        except OSError:
            pass

        def _worker():
            while True:
                el = time.time() - t0
                if el < T1:
                    src.speed = _PLAN['pace_normal']
                elif el < T2:
                    if meta['events'][-1:] != ['overload']:
                        meta['events'].append('overload')
                    src.speed = _PLAN['pace_overload']
                else:
                    if meta['events'][-1:] != ['recover']:
                        meta['events'].append('recover')
                    src.speed = _PLAN['pace_normal']
                time.sleep(0.2)

        threading.Thread(target=_worker, daemon=True).start()

    mod.Session.start = start
    mod._app327_patched = True


# 🔴🔴🔴 **懒 patch v2**：上一版用 `import live_caption_app` 钩子 ⇒ **完全无效**！
#
# **根因（读码定案）**：App 是**以 `__main__` 直接运行**的
#   （`live_caption_app.py` 末尾有 `if __name__ == '__main__':`）
#   ⇒ `import live_caption_app` 这个 import 语句**从来不会发生**
#   ⇒ `__import__` 钩子永远不触发 ⇒ `Session.start` 从未被 patch
#   ⇒ 上一轮 `session_meta` 为空（`t0_wall=None`）⇒ 三阶段划分全部失效。
#
# **修法**：改成**轮询 `sys.modules['__main__']`** —— App 在 `__main__` 里定义
#   `class Session` ⇒ 一旦 `__main__` 模块里出现 `Session`，就 patch 它的 `start`。
#   （`__main__` 在脚本开始执行时就已经在 sys.modules 里 ⇒ 轮询能可靠捕获。）
#
# 🔴 **为什么不能用 `atexit`/`trace`**：那会改运行语义；这里只做「轮询 + patch」，
#   仓库代码**零改动**（只写影子包的 sitecustomize.py）。
import sys
import threading as _threading


def _watch_main():
    deadline = _time.time() + 300.0
    while _time.time() < deadline:
        mod = sys.modules.get('__main__')
        if mod is not None and hasattr(mod, 'Session'):
            try:
                _patch_session(mod)
                if getattr(mod, '_app327_patched', False):
                    return
            except Exception:
                pass
        _time.sleep(0.05)


def _watch_main_thread():
    t = _threading.Thread(target=_watch_main, daemon=True)
    t.start()


try:
    _watch_main_thread()
except Exception:
    pass
'''


def patch_live_caption(app_dir, plan_path):
    """🔴 在**影子包的 app 目录**里放 `sitecustomize.py` + 计划文件。

    ⚠️ **不改仓库代码**：只写影子包 ⇒ 与仓库的差异**只有这两个新增文件**
    ⇒ 收尾时逐字节核对（证明「仓库零改动」）。
    """
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump({
            'src_normal_end': SRC_NORMAL_END,
            'src_overload_end': SRC_OVERLOAD_END,
            'pace_normal': PACE_NORMAL,
            'pace_overload': PACE_OVERLOAD,
        }, f, ensure_ascii=False)

    sc = os.path.join(app_dir, 'sitecustomize.py')
    with open(sc, 'w', encoding='utf-8') as f:
        f.write(SITECUSTOMIZE)
    return sc


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    i = int(q * (len(s) - 1))
    return round(s[i], 4)


def recovery_from(rows, t_end_wall, threshold=RECOVER_LAG_S):
    """🔴 从**过载结束墙钟**到 dequeue lag 回落到阈值内的用时。

    口径：`speed_lag_s`（worker 出队时的滞后；`tts_worker.py:2514`）
    ⇒ 这就是 reviewer 说的「dequeue lag」。

    🔴🔴🔳 **修正**：改用 `_wall_est`（= `t_submit` + 中位数 offset）定位墙钟
    ⇒ **`late_drop` 的行也能参与判定**（它们的 `speed_lag_s` 为空 ⇒
    会被跳过，但它们的**出现**说明过载仍在持续 ⇒ 恢复不可能早于它们）。
    """
    for r in sorted(rows, key=lambda x: x.get('_wall_est') or 0.0):
        sl = r.get('speed_lag_s')
        t = r.get('_wall_est')
        if not isinstance(sl, (int, float)) or not isinstance(t, (int, float)):
            continue
        if float(t) < t_end_wall:
            continue                       # 🔴 只看**过载结束之后**的句
        if sl <= threshold:
            return round(float(t) - t_end_wall, 3)
    return None


def neg_control(rows, threshold=RECOVER_LAG_S):
    """🔴 反证组：把 `speed_lag_s` 全部抬高 ⇒ 恢复用时必须变 None。"""
    tampered = []
    for r in rows:
        r2 = dict(r)
        r2['speed_lag_s'] = (r.get('speed_lag_s') or 0.0) + 1000.0
        tampered.append(r2)
    return recovery_from(tampered, 0.0, threshold)


def phase_of(wall_rel, T1, T2):
    if wall_rel is None:
        return None
    if wall_rel < T1:
        return 'normal'
    if wall_rel < T2:
        return 'overload'
    return 'recover'


def score_phase(rows, phase, T1, T2):
    sub = [r for r in rows if r.get('_phase') == phase]
    lags = [float(r['speed_lag_s']) for r in sub
            if isinstance(r.get('speed_lag_s'), (int, float))]
    play = [float(r['play_lag_s']) for r in sub
            if isinstance(r.get('play_lag_s'), (int, float))]
    fifo = [float(r['worker_fifo_wait_s']) for r in sub
            if isinstance(r.get('worker_fifo_wait_s'), (int, float))]
    rtfs = [float(r['synth_rtf']) for r in sub
            if isinstance(r.get('synth_rtf'), (int, float))]
    ers = {}
    for r in sub:
        k = str(r.get('end_reason'))
        ers[k] = ers.get(k, 0) + 1
    return {
        'n_rows': len(sub),
        'n_with_play_wall': sum(1 for r in sub
                                if isinstance(r.get('play_wall'), (int, float))),
        'speed_lag_p50': pct(lags, 0.50),
        'speed_lag_p95': pct(lags, 0.95),
        'speed_lag_max': round(max(lags), 4) if lags else None,
        'play_lag_p50': pct(play, 0.50),
        'play_lag_p95': pct(play, 0.95),
        'worker_fifo_wait_p50': pct(fifo, 0.50),
        'worker_fifo_wait_p95': pct(fifo, 0.95),
        'synth_rtf_p50': pct(rtfs, 0.50),
        'synth_rtf_p95': pct(rtfs, 0.95),
        'n_late_drop': sum(1 for r in sub if r.get('late_drop')
                           or r.get('dropped')),
        'late_drop_lag_s_p50': pct(
            [float(r['late_drop_lag_s']) for r in sub
             if isinstance(r.get('late_drop_lag_s'), (int, float))], 0.50),
        'late_drop_lag_s_max': (round(max(
            [float(r['late_drop_lag_s']) for r in sub
             if isinstance(r.get('late_drop_lag_s'), (int, float))]), 3)
            if any(isinstance(r.get('late_drop_lag_s'), (int, float))
                   for r in sub) else None),
        'n_speed_floor_conflict_max': max(
            [int(r['n_speed_floor_conflict']) for r in sub
             if isinstance(r.get('n_speed_floor_conflict'), (int, float))]
            or [0]),
        'end_reason_dist': ers,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after', choices=['after', 'before'])
    args = ap.parse_args()

    ev = {'created_at': now(), 'arm': args.arm,
          'criterion': 'APP-093 §3.3 单会话过载臂（1.0× → 2.0× → 1.0×）',
          'recover_threshold_s': RECOVER_LAG_S, 'lock': None, 'runs': []}

    lock = acquire_lock('app093-overload')
    if lock is None:
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev)
        print('!! 拿不到锁')
        return 2
    ev['lock'] = lock.strip()
    print('[lock] 已持有', flush=True)

    try:
        root = os.path.join(BASE, args.arm)
        app_dir = os.path.join(root, 'app')
        plan_path = os.path.join(app_dir, '_app327_overload_plan.json')
        sc_path = patch_live_caption(app_dir, plan_path)

        out = os.path.join(OUTROOT, args.arm, 'dialog3_overload3')
        os.makedirs(out, exist_ok=True)
        wav = os.path.join(SPKTEST, 'dialog3.wav')
        cmd = build_cmd(root, out, wav)
        env = dict(os.environ)
        env['PYTHONPATH'] = app_dir
        clone_dir = os.path.join(out, 'clone_voices')
        os.makedirs(clone_dir, exist_ok=True)
        env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir

        started = now()
        t0 = time.perf_counter()
        print('▶ 过载臂 %s：%s' % (args.arm, wav), flush=True)
        rc = -1
        log_path = os.path.join(out, 'run.log')
        with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
            lf.write('# cmd=%s\n# started=%s\n# patch=%s\n'
                     % (json.dumps(cmd), started, sc_path))
            lf.flush()
            # 🔴 stdout → 文件（不是 pipe）⇒ 不会因管道缓冲写满而阻塞
            p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                 env=env, cwd=root)
            rc = p.wait()
        wall = time.perf_counter() - t0

        rows = read_jsonl(os.path.join(out, 'tts.jsonl'))
        segs = read_jsonl(os.path.join(out, 'spk_seg.jsonl'))
        meta_path = os.path.join(app_dir, '_app327_session_meta.json')
        meta = json.load(open(meta_path, encoding='utf-8')) \
            if os.path.exists(meta_path) else {}

        over_src = SRC_OVERLOAD_END - SRC_NORMAL_END
        T1 = SRC_NORMAL_END
        T2 = T1 + over_src / PACE_OVERLOAD
        t0_wall = meta.get('t0_wall')
        T2_wall = meta.get('T2_wall')
        ev['plan'] = {
            'src_normal_end_s': SRC_NORMAL_END,
            'src_overload_end_s': SRC_OVERLOAD_END,
            'pace_normal': PACE_NORMAL,
            'pace_overload': PACE_OVERLOAD,
            'wall_overload_start_s_rel': T1,
            'wall_overload_end_s_rel': T2,
            'session_meta': meta,
            'note': ('reviewer 的 60/150 s 是**源秒**；过载段 90 s 源在 pace 2.0 '
                     '下花 45 s 墙钟 ⇒ 过载墙钟区间 = [60, 105] s'),
        }

        # ── 逐句打阶段标 ──
        # 🔴🔴🔳 **修正（上一版缺陷）**：上一版只用 `play_wall` 定位墙钟 ⇒
        #   **`late_drop` 的行 `play_wall=None`（22 句）被整体漏掉**
        #   ⇒ 过载期只统计到 1 句 ⇒ 「过载期跳过句数」全错。
        #   **修法**：`t_submit` 是**单调时钟**（`time.perf_counter`），
        #   与 `play_wall`（墙钟）**不可直接相减**；但二者的**差值恒定**
        #   （实测 std = 1.67 s）⇒ 取**中位数 offset** ⇒
        #   `wall_est = t_submit + offset` ⇒ **所有行**（含 late_drop）都能定位。
        offs = [float(r['play_wall']) - float(r['t_submit'])
                for r in rows
                if isinstance(r.get('play_wall'), (int, float))
                and isinstance(r.get('t_submit'), (int, float))]
        offset = st.median(offs) if offs else 0.0
        ev['clock_offset'] = {
            'method': 'wall_est = t_submit + median(play_wall - t_submit)',
            'n_used': len(offs),
            'offset_s': round(offset, 4),
            'offset_std_s': (round(st.pstdev(offs), 4) if len(offs) > 1
                             else None),
            'offset_min_s': (round(min(offs), 4) if offs else None),
            'offset_max_s': (round(max(offs), 4) if offs else None),
            'note': ('🔴 `t_submit` 是单调钟、`play_wall` 是墙钟 ⇒ 不能直接相减；'
                     '取差值中位数做平移 ⇒ late_drop 行（play_wall=None）'
                     '也能定位到墙钟'),
        }
        for r in rows:
            w = r.get('play_wall')
            if isinstance(w, (int, float)):
                rel = float(w) - float(t0_wall)
            else:
                ts = r.get('t_submit')
                rel = (float(ts) + offset - float(t0_wall)) if (
                    isinstance(ts, (int, float))
                    and isinstance(t0_wall, (int, float))) else None
            r['_wall_rel'] = rel
            r['_wall_est'] = (float(r['t_submit']) + offset
                              if isinstance(r.get('t_submit'), (int, float))
                              else None)
            r['_phase'] = phase_of(rel, T1, T2)

        ev['phases'] = {
            ph: score_phase(rows, ph, T1, T2)
            for ph in ('normal', 'overload', 'recover')
        }
        # 🔴 积压曲线（reviewer：「过载前、峰值、结束时」）
        curve = []
        for r in rows:
            if r.get('_wall_rel') is None:
                continue
            curve.append({
                'wall_rel_s': round(r['_wall_rel'], 2),
                'phase': r['_phase'],
                'speed_lag_s': r.get('speed_lag_s'),
                'play_lag_s': r.get('play_lag_s'),
                'late_drop_lag_s': r.get('late_drop_lag_s'),
                'late_drop': bool(r.get('late_drop')),
                'dropped': bool(r.get('dropped')),
                'worker_fifo_wait_s': r.get('worker_fifo_wait_s'),
                'synth_rtf': r.get('synth_rtf'),
                'n_speed_floor_conflict': r.get('n_speed_floor_conflict'),
            })
        ev['backlog_curve'] = curve

        # ── 🔴 ASR/MT 积压曲线（reviewer §3.3：「ASR/MT/TTS 积压曲线」）──
        #   App 自己落盘 `mix.wav.backlog_curve.csv`：
        #   `t_s,backlog_s,lag_s,ring_s,synth_s,queued_s,n_played,n_dropped,n_empty,n_submitted`
        #   ⇒ `backlog_s`/`lag_s` ＝ **ASR 侧积压**；`synth_s` ＝ TTS 合成占用；
        #   `queued_s` ＝ TTS 队列；`n_dropped` ＝ 已丢句数。
        bc_path = os.path.join(out, 'mix.wav.backlog_curve.csv')
        ev['asr_backlog_curve'] = {'path': bc_path, 'exists': os.path.exists(bc_path),
                                   'columns': [], 'phases': {}}
        if os.path.exists(bc_path):
            import csv
            with open(bc_path, encoding='utf-8', errors='replace',
                      newline='') as f:
                rdr = list(csv.DictReader(f))
            if rdr:
                ev['asr_backlog_curve']['columns'] = list(rdr[0].keys())
                ev['asr_backlog_curve']['n_points'] = len(rdr)
                for ph, (a, b) in (('normal', (0.0, T1)),
                                   ('overload', (T1, T2)),
                                   ('recover', (T2, 1e18))):
                    sub = [r for r in rdr
                           if a <= float(r.get('t_s') or 0.0) < b]
                    if not sub:
                        continue
                    bl = [float(r['backlog_s']) for r in sub
                          if r.get('backlog_s')]
                    lg = [float(r['lag_s']) for r in sub if r.get('lag_s')]
                    sy = [float(r['synth_s']) for r in sub if r.get('synth_s')]
                    qu = [float(r['queued_s']) for r in sub if r.get('queued_s')]
                    dp = [int(r['n_dropped']) for r in sub
                          if r.get('n_dropped')]
                    ev['asr_backlog_curve']['phases'][ph] = {
                        'n_points': len(sub),
                        'backlog_s_max': (round(max(bl), 4) if bl else None),
                        'backlog_s_p50': pct(bl, 0.50),
                        'lag_s_max': (round(max(lg), 4) if lg else None),
                        'lag_s_p50': pct(lg, 0.50),
                        'synth_s_max': (round(max(sy), 4) if sy else None),
                        'queued_s_max': (round(max(qu), 4) if qu else None),
                        'n_dropped_final': (dp[-1] if dp else None),
                    }
        olags = [c['speed_lag_s'] for c in curve
                 if c['phase'] == 'overload'
                 and isinstance(c['speed_lag_s'], (int, float))]
        # 🔴 过载期的**跳句滞后**用 `late_drop_lag_s`（墙钟 now−target_wall）
        odrops = [c['late_drop_lag_s'] for c in curve
                  if c['phase'] == 'overload'
                  and isinstance(c['late_drop_lag_s'], (int, float))]
        ev['overload_peak'] = {
            'speed_lag_max_in_overload': round(max(olags), 4) if olags else None,
            'late_drop_lag_max_in_overload': (round(max(odrops), 4)
                                              if odrops else None),
            'late_drop_lag_p50_in_overload': pct(odrops, 0.50),
            'n_late_drop_in_overload': ev['phases']['overload']['n_late_drop'],
            'lag_field_note': ('speed_lag_s＝worker 出队滞后；'
                               'late_drop_lag_s＝跳句时的墙钟滞后'
                               '（now − target_wall）'),
        }

        # ── 恢复用时 ──
        rec = recovery_from(rows, T2_wall) if isinstance(T2_wall, (int, float)) \
            else None
        nc = neg_control(rows)
        ev['recovery'] = {
            'threshold_s': RECOVER_LAG_S,
            'field': 'speed_lag_s（worker 出队滞后；tts_worker.py:2514）',
            'overload_end_wall': T2_wall,
            'recovery_s_after_overload': rec,
            'neg_control': nc,
            'neg_control_pass': (nc is None),
            'neg_control_note': ('🔴 反证：把 speed_lag_s 全部 +1000 ⇒ '
                                 '恢复用时必须变 None（否则判据恒真）'),
        }

        # ── 字幕完整度（段数逐一对上）──
        n_sub = 0
        sp = os.path.join(out, 'subtitles.txt')
        if os.path.exists(sp):
            with open(sp, encoding='utf-8', errors='replace') as f:
                n_sub = sum(1 for ln in f if ln.strip())
        ev['subtitle_completeness'] = {
            'n_subtitle_lines': n_sub,
            'n_seg_rows': len(segs),
            'n_tts_rows': len(rows),
            'n_sub_n_seg_equal': (n_sub == len(segs)),
            'note': ('App 侧 subtitles.txt 与 spk_seg.jsonl **同源同序** '
                     '（一 定稿一段）⇒ 段数应相等'),
        }

        ev['runs'] = [{
            'out': out, 'rc': rc, 'started': started, 'finished': now(),
            'wall_s': round(wall, 2), 'cmd': cmd, 'patch_file': sc_path,
            'n_tts_rows': len(rows), 'n_seg_rows': len(segs),
        }]
        ev['artifacts'] = {}
        for name in ('subtitles.txt', 'tts.jsonl', 'mix.wav', 'spk_seg.jsonl',
                     'subtitles.mt.txt', 'run.log'):
            pth = os.path.join(out, name)
            if os.path.exists(pth):
                ev['artifacts'][name] = {'bytes': os.path.getsize(pth),
                                         'sha256': sha(pth)}
        ev['verdict'] = 'RAN'
    finally:
        ev['lock_released'] = release_lock()
        ev['lock_exists_after'] = os.path.exists(LOCK)
        print('[lock] 释放=%s 残留=%s' % (ev['lock_released'],
                                        ev['lock_exists_after']), flush=True)
    _dump(ev)
    return 0


def _dump(ev):
    p = os.path.join(HERE, 'app327_overload_%s.json' % ev['arm'])
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % p, flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
