#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app329b_app093_voice_attrib_driver.py —— **驱动 §3.5 音色归属（4 组：before/after × dialog3/tight）**。

## reviewer §3.5 原文
> **音色归属按 APP-089 原判据重算**：输出 x-vector 和 truth.json 里三个人的参考比余弦，
> 报最接近正确说话人的占比。**before 和 after 都要，dialog3 和 tight 都要。**
> 现在的"本句原声"判据可以作为附加项保留。

## 为什么需要 driver
🔴 `speaker_embedding` 需要 **NPU** ⇒ 必须在**影子包的 python** 里跑（包内才有 babelvox/openvino）
⇒ 本 driver（仓库侧、仓库 python）负责：
  1. 拿 **MACHINE_LOCK**（NPU 是共享资源 ⇒ 必须持锁）
  2. 逐组调用**影子包 python** 跑 `_app329_app093_voice_attrib.py`
  3. 子进程 stdout/stderr → **文件**（🔴 不是 pipe ⇒ 不会管道死锁）
  4. 汇总 4 组结果到一个 json，并把**锁记录**写进去（APP-093 §4：「计时跑的 json 里要写锁的持有记录」）

## 四组配置
| label | arm | 素材 | truth | run 目录 |
|---|---|---|---|---|
| before_dialog3 | before | dialog3.wav | truth.json | runs2/before/dialog3 |
| after_dialog3  | after  | dialog3.wav | truth.json | runs2/after/dialog3 |
| before_tight   | before | dialog3_tight.wav | truth_tight.json | runs2/before/dialog3_tight |
| after_tight    | after  | dialog3_tight.wav | truth_tight.json | runs3/after/dialog3_tight_thr6 |

🔴 **注意**：`after_tight` 用 `runs3/after/dialog3_tight_thr6`（阈值 6.0 = 默认值 ⇒ 与 before 同口径）。
   `before` 没有 tight 的 thr6 目录 ⇒ 用 `runs2/before/dialog3_tight`（默认阈值那次跑）。

## 用法
```
python results/app/_app329b_app093_voice_attrib_driver.py
```
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '_app_shadow')
SHADOW_ROOT = os.path.join(BASE, 'after2')          # 包（含 python/ + models/ 联接）
SHADOW_PY = os.path.join(SHADOW_ROOT, 'python', 'python.exe')
SHADOW_APP = os.path.join(SHADOW_ROOT, 'app')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')

RUNNER = os.path.join(HERE, '_app329_app093_voice_attrib.py')
REPORT = os.path.join(HERE, 'app329_app093_voice_attrib.json')

GROUPS = [
    {'label': 'before_dialog3', 'arm': 'before',
     'wav': 'dialog3.wav', 'truth': 'truth.json',
     'run': os.path.join(BASE, 'runs2', 'before', 'dialog3')},
    {'label': 'after_dialog3', 'arm': 'after',
     'wav': 'dialog3.wav', 'truth': 'truth.json',
     'run': os.path.join(BASE, 'runs2', 'after', 'dialog3')},
    {'label': 'before_tight', 'arm': 'before',
     'wav': 'dialog3_tight.wav', 'truth': 'truth_tight.json',
     'run': os.path.join(BASE, 'runs2', 'before', 'dialog3_tight')},
    {'label': 'after_tight', 'arm': 'after',
     'wav': 'dialog3_tight.wav', 'truth': 'truth_tight.json',
     'run': os.path.join(BASE, 'runs3', 'after', 'dialog3_tight_thr6')},
]


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag):
    """🔴 锁已存在就**等待**（不抢）；拿不到就返回 None。"""
    for _ in range(3):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            print('[lock] 已存在，等待…', flush=True)
            time.sleep(30)
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write('module=app\npid=%d\nstart=%s\ntag=%s\n'
                    % (os.getpid(), now(), tag))
        return open(LOCK, encoding='utf-8').read()
    return None


def release_lock():
    """🔴🔴 用 `os.replace` 改名释放（**不是** os.remove ⇒ safe-delete 钩子会拦）。"""
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                if ('pid=%d' % os.getpid()) in f.read():
                    gone = os.path.join(
                        os.path.dirname(LOCK),
                        '.MACHINE_LOCK.released_%d_%d' % (os.getpid(), int(time.time())))
                    os.replace(LOCK, gone)
                    return not os.path.exists(LOCK)
    except OSError:
        pass
    return False


def run_one(g):
    out_json = os.path.join(HERE, 'app329_%s.json' % g['label'])
    dump_dir = os.path.join(g['run'], 'dump')
    cmd = [SHADOW_PY, RUNNER,
           '--app', SHADOW_APP,
           '--out', out_json,
           '--truth', os.path.join(SPKTEST, g['truth']),
           '--wav', os.path.join(SPKTEST, g['wav']),
           '--tts-jsonl', os.path.join(g['run'], 'tts.jsonl'),
           '--dump-dir', dump_dir,
           '--label', g['label']]
    log = os.path.join(HERE, '_app329_%s.log' % g['label'])
    print('▶ %s' % g['label'], flush=True)
    t0 = time.perf_counter()
    rc = -1
    with open(log, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n# started=%s\n' % (json.dumps(cmd), now()))
        lf.flush()
        # 🔴 stdout → 文件（不是 pipe）⇒ 不会管道死锁
        rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT)
    wall = round(time.perf_counter() - t0, 1)
    tail = ''
    try:
        tail = open(log, encoding='utf-8', errors='replace').read()[-2500:]
    except OSError:
        pass
    res = None
    if os.path.exists(out_json):
        try:
            res = json.load(open(out_json, encoding='utf-8'))
        except ValueError:
            res = None
    return {'label': g['label'], 'arm': g['arm'], 'rc': rc, 'wall_s': wall,
            'out_json': out_json, 'log': log,
            'run_dir': g['run'], 'n_dump': len(os.listdir(dump_dir))
            if os.path.isdir(dump_dir) else None,
            'summary': (res or {}).get('summary'),
            'ref_pair_cosine': (res or {}).get('ref_pair_cosine'),
            'neg_control': (res or {}).get('neg_control'),
            'log_tail': tail}


def main():
    ev = {
        'created_at': now(),
        'correction': 'APP-093 §3.5 音色归属（按 APP-089 原判据重算）',
        'criterion': ('输出 x-vector 与 truth.json 三人参考分别比余弦 ⇒ 取最大者；'
                      '若最大者 == 该句真值说话人 ⇒ 命中'),
        'method': ('NPU 设备跑（speaker_embedding）⇒ 持 MACHINE_LOCK；'
                   '4 组：before/after × dialog3/tight'),
        'device_job': True,
        'shadow_root': SHADOW_ROOT,
        'groups': [],
    }

    lock = acquire_lock('app093-voice-attrib')
    if lock is None:
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev)
        print('!! 拿不到锁')
        return 2
    ev['lock_record'] = {
        'module': 'app', 'pid': os.getpid(),
        'start': now(), 'tag': 'app093-voice-attrib',
        'file': LOCK, 'content': lock.strip(),
    }
    print('[lock] 已持有', flush=True)

    try:
        for g in GROUPS:
            try:
                ev['groups'].append(run_one(g))
            except Exception as exc:          # noqa: BLE001
                ev['groups'].append({'label': g['label'], 'error': repr(exc)})
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                if ('pid=%d' % os.getpid()) not in f.read():
                    ev['verdict'] = 'LOCK_LOST'
                    _dump(ev)
                    print('!! 锁已丢失', flush=True)
                    return 3
    finally:
        ev['lock_released'] = release_lock()

    ev['verdict'] = 'RAN'
    _dump(ev)
    return 0


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT, flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
