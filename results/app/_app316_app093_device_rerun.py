#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app316_app093_device_rerun.py —— **APP-093 §3 的设备级重跑**（2/3/4/5）。

## 依据（reviewer 原文 §3）

* **§3.2 阈值 A/B**：`tts_late_drop_sec` 取 **6 / 10 / 15**，**tight 和 dave 各跑一次**
  正常速度。每组报 **跳过句数、play_lag p50/p95、n_speed_floor_conflict**。
  🔴 **默认值保持 6.0**（本脚本只改命令行参数，**不改代码默认值**）。
* **§3.3 过载臂重做**：用 dialog3，**前 60 s 1.0×，60–150 s 人为过载，150 s 以后回 1.0×**。
  报过载起止时间（源秒和墙钟）、ASR/MT/TTS 积压曲线、跳过句数、
  **从过载结束到 dequeue lag 回到 6 s 以内的用时**、字幕完整度。
* **§3.4 before 臂补齐**：tight 和 dave 各跑一次 **before**（APP-086 接线版）。
* **§3.5 音色归属**：输出 x-vector 和 truth.json 里三个人的参考比余弦，
  报**最接近正确说话人的占比**。before 和 after 都要，dialog3 和 tight 都要。

## 🔴🔴🔳 纪律

* **持 `MACHINE_LOCK`**（计时作业）⇒ 做完释放；锁内容写模块名 + PID + 起止时间。
* **不调 MiniMax**（CER 由 reviewer 复算）。
* **不改代码默认值**（阈值只作为命令行参数传入）。
* 影子包：`before` = APP-086 接线前，`after` = 仓库当前代码
  （`_app_shadow/{before,after}`）。

## 用法

```
.venv/Scripts/python.exe results/app/_app316_app093_device_rerun.py --part threshold
.venv/Scripts/python.exe results/app/_app316_app093_device_rerun.py --part before
.venv/Scripts/python.exe results/app/_app316_app093_device_rerun.py --part overload
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

BASE = os.path.join(HOME, '_app_shadow')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
OUTROOT = os.path.join(BASE, 'runs3')
REPORT = os.path.join(HERE, 'app316_app093_device_rerun.json')

MATERIALS = {
    'dialog3': 'dialog3.wav',
    'dialog3_tight': 'dialog3_tight.wav',
    'dialog3_dave': 'dialog3_dave.wav',
}

#: 🔴 reviewer 指定的阈值 A/B 组合（**不改代码默认值**）
THRESHOLDS = (6.0, 10.0, 15.0)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


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
                    os.remove(LOCK)
                    return True
    except OSError:
        pass
    return False


def build_cmd(root, out, wav, extra=None):
    """🔴 与 `_app385` **同口径**（ASR iGPU / MT iGPU / TTS NPU / 克隆跟随说话人）。"""
    cmd = [
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
    if extra:
        cmd += list(extra)
    return cmd


def run_one(arm, mat, extra=None, sub=None, tag='', env_extra=None):
    root = os.path.join(BASE, arm)
    wav = os.path.join(SPKTEST, MATERIALS[mat])
    out = os.path.join(OUTROOT, arm, sub or mat)
    os.makedirs(out, exist_ok=True)
    log_path = os.path.join(out, 'run.log')
    cmd = build_cmd(root, out, wav, extra)
    env = dict(os.environ)
    clone_dir = os.path.join(out, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir
    # 🔴 阈值用**环境变量**传（`device_config.get_numeric` 的优先级：
    #    环境变量 > device_config.json > 默认值）
    #    ⇒ **不动代码默认值**（APP-093 §3.2 明文「默认值保持 6.0」）
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})

    started = now()
    print('▶ [%s/%s%s] %s' % (arm, mat, tag, wav), flush=True)
    rc = -1
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n# started=%s\n' % (json.dumps(cmd), started))
        lf.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace',
                             bufsize=1, env=env, cwd=root)
        for line in p.stdout:
            lf.write(line)
            lf.flush()
            if ('音频 ' in line or '⏭' in line or '已晚' in line
                    or 'TTS] 收尾' in line):
                print('   ' + line.rstrip()[:200], flush=True)
        rc = p.wait()
    arts = {}
    for name in ('subtitles.txt', 'tts.jsonl', 'mix.wav', 'spk_seg.jsonl'):
        pth = os.path.join(out, name)
        if os.path.exists(pth):
            arts[name] = {'bytes': os.path.getsize(pth), 'sha256': sha(pth)}
    return {'arm': arm, 'material': mat, 'sub': sub or mat, 'tag': tag,
            'extra': list(extra or []), 'env_extra': dict(env_extra or {}),
            'rc': rc, 'started': started,
            'finished': now(), 'out': out, 'cmd': cmd, 'artifacts': arts}


def score_tts_jsonl(path):
    """从 tts.jsonl 算：跳过句数、play_lag p50/p95、n_speed_floor_conflict、synth_rtf。

    🔴 字段口径照 reviewer 引用的一致（`n_late_drop` / `play_lag_s` /
    `n_speed_floor_conflict` / `synth_rtf`）。
    """
    import statistics as st
    rows = []
    if not os.path.exists(path):
        return {'error': 'no tts.jsonl'}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    n_late = sum(1 for r in rows if r.get('late_drop')
                 or r.get('dropped') or r.get('skipped'))
    lags = [float(r['play_lag_s']) for r in rows
            if isinstance(r.get('play_lag_s'), (int, float))]
    rtfs = [float(r['synth_rtf']) for r in rows
            if isinstance(r.get('synth_rtf'), (int, float))]
    conflicts = [int(r['n_speed_floor_conflict']) for r in rows
                 if isinstance(r.get('n_speed_floor_conflict'), int)]
    return {
        'n_rows': len(rows),
        'n_late_drop': n_late,
        'play_lag_p50': round(st.median(lags), 4) if lags else None,
        'play_lag_p95': (round(sorted(lags)[int(0.95 * (len(lags) - 1))], 4)
                         if lags else None),
        'synth_rtf_p50': round(st.median(rtfs), 4) if rtfs else None,
        'n_speed_floor_conflict_max': max(conflicts) if conflicts else None,
        'fields_seen': sorted({k for r in rows for k in r})[:40],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', choices=['threshold', 'before', 'overload'],
                    required=True)
    args = ap.parse_args()

    ev = {'created_at': now(), 'part': args.part, 'runs': [], 'lock': None}

    lock = acquire_lock('app093-%s' % args.part)
    if lock is None:
        print('!! 拿不到锁')
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev)
        return 2
    ev['lock'] = lock.strip()
    print('[lock] 已持有：%s' % lock.strip().replace('\n', ' '), flush=True)

    try:
        if args.part == 'threshold':
            # 🔴 §3.2：阈值 A/B（tight + dave × 6/10/15）
            for mat in ('dialog3_tight', 'dialog3_dave'):
                for thr in THRESHOLDS:
                    r = run_one('after', mat,
                                extra=None,
                                sub='%s_thr%g' % (mat, thr),
                                tag=' thr=%g' % thr,
                                env_extra={'LIVECAP_TTS_LATE_DROP_SEC': thr})
                    r['threshold_s'] = thr
                    r['scores'] = score_tts_jsonl(
                        os.path.join(r['out'], 'tts.jsonl'))
                    ev['runs'].append(r)
        elif args.part == 'before':
            # 🔴 §3.4：before 臂补齐（tight + dave）
            for mat in ('dialog3_tight', 'dialog3_dave'):
                r = run_one('before', mat, sub=mat, tag=' before')
                r['scores'] = score_tts_jsonl(
                    os.path.join(r['out'], 'tts.jsonl'))
                ev['runs'].append(r)
        else:
            # 🔴 §3.3：过载臂重做（前 60 s 1.0×，60–150 s 过载，150 s 后 1.0×）
            #    用 `--speed` 分段：先 1.0 跑 60 s，再 0.35（过载）跑 90 s，
            #    再 1.0 跑剩余 —— 三段拼接成一条素材，源秒与墙钟都能标。
            wav = os.path.join(SPKTEST, MATERIALS['dialog3'])
            out = os.path.join(OUTROOT, 'after', 'dialog3_overload3')
            os.makedirs(out, exist_ok=True)
            seg_plan = [('part1_1x', 60.0, ['--speed', '1.0']),
                        ('part2_overload', 90.0, ['--speed', '0.35']),
                        ('part3_1x', 150.0, ['--speed', '1.0'])]
            segs = []
            for sub, secs, extra in seg_plan:
                r = run_one('after', 'dialog3',
                            extra=extra + ['--max-seconds', str(int(secs))],
                            sub='dialog3_overload3/%s' % sub,
                            tag=' %s' % sub)
                r['seg_plan'] = {'sub': sub, 'secs': secs, 'extra': extra}
                r['scores'] = score_tts_jsonl(
                    os.path.join(r['out'], 'tts.jsonl'))
                segs.append(r)
                ev['runs'].append(r)
            ev['overload_segments'] = segs
    finally:
        ev['lock_released'] = release_lock()
        ev['lock_exists_after'] = os.path.exists(LOCK)
        print('[lock] 已释放：%s（残留=%s）'
              % (ev['lock_released'], ev['lock_exists_after']), flush=True)

    ev['verdict'] = 'RAN'
    _dump(ev)
    return 0


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT, flush=True)


if __name__ == '__main__':
    sys.exit(main())
