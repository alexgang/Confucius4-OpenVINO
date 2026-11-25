#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_e2e_driver.py — **APP-134 a / APP-137 §3** 的 e2e 驱动器（Python 版）。

## 为什么重写成 Python（而不是沿用 `_app137_e2e_driver.ps1`）

🔴 **PowerShell 5.1 的 `Start-Process` 在本机会抛**
`ArgumentException: 已添加项。字典中的关键字:"Path"所添加的关键字:"PATH"`
—— 本机环境里**同时存在 `Path` / `PATH` / `path` 三个键**（Windows 环境块
允许同名不同大小写的重复项）⇒ .NET 的 `Process.Start` 组装环境字典时撞键。
⇒ 改用 Python 的 `subprocess`（`os.environ` 在 nt 上是**大小写不敏感**的
单字典 ⇒ 天然去重）⇒ **同一个坑从根上绕开**。

## 口径（reviewer APP-134 a 原文）
* 媒体结束后**继续等**，直到 `stats_full.pipeline.n_pending == 0`（或等满
  `--drain-cap` 秒，默认 300）；
* 报告**排空时刻**、各句最终的 `dub_late`、**排空前的 n_pending**；
* 至少两轮：`bgkeep_on`（TTS=NPU）与 `bgkeep_on`（**AUTO** ＝ Start_Bridge
  实际走的配置）。

## 🔴 纪律
* **一次持锁到底**：整个 job 一把 `shared\MACHINE_LOCK`，**原子创建**
  （`O_CREAT|O_EXCL`）⇒ 别人必失败 ⇒ **抢不到就排队等，绝不抢**；
* 每个臂**起一个全新桥接**（不背上一臂的积压）；
* 桥接**跑在客户包自己的 `ext/`**（cwd = 包根）⇒ AUTO 臂走的就是用户
  双击 `Start_Bridge.bat` 时的那份 `ext/bridge/config.py`；
* e2e 客户端用**包内 python**（APP-120 血泪：判「包能否用」用客户解释器）；
* token 文件**放臂目录** ⇒ 客户包一个字节都不动；
* 只停**自己起的**桥接进程；释放锁前确认本 job 进程已死。

## 用法
```
python live_caption/_app137_e2e_driver.py \
    --app "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.6" \
    --root "C:/Users/Trekker-PTL/shared/bgkeep/e2e_app134a" \
    --arms "bgkeep_on_npu:EXT_TTS_DEVICE=NPU|EXT_MT_DEVICE=GPU.0,bgkeep_on_auto:"
```
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

DEFAULT_MEDIA = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
DEFAULT_SHORT = os.path.join(REPO, 'test_audio', 'app119_clip_0_60.wav')


# ──────────────────────────────────────────────────────────────────────
# 机器锁（原子创建；抢不到就排队等，绝不抢）
# ──────────────────────────────────────────────────────────────────────
def acquire_lock(lock_path: str, tag: str, max_wait_s: int = 7200):
    """原子创建锁文件。返回 (True, waited_s) 或 (False, waited_s)。"""
    waited = 0
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(tag)
            return True, waited
        except FileExistsError:
            if waited >= max_wait_s:
                return False, waited
            time.sleep(20)
            waited += 20


def release_lock(lock_path: str, tag: str):
    """只有锁内容还是**本 job 的 tag** 才释放 ⇒ 不误删别人的锁。"""
    try:
        with open(lock_path, encoding='utf-8') as fh:
            cur = fh.read().strip()
    except OSError:
        return False
    if cur.split(' pid=')[0] != tag.split(' pid=')[0]:
        return False
    try:
        os.remove(lock_path)
        return True
    except OSError:
        return False


def append_event(events_path: str, obj: dict):
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    with open(events_path, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + '\n')


# ──────────────────────────────────────────────────────────────────────
# 端口
# ──────────────────────────────────────────────────────────────────────
def ports_free(ports, timeout_s: int = 180) -> bool:
    """端口是否空闲（Windows：用 socket 试探 bind）。"""
    import socket
    deadline = time.time() + timeout_s
    while True:
        busy = []
        for p in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                s.bind(('127.0.0.1', p))
            except OSError:
                busy.append(p)
            finally:
                s.close()
        if not busy:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(2)


# ──────────────────────────────────────────────────────────────────────
# 桥接
# ──────────────────────────────────────────────────────────────────────
def start_bridge(app: str, out_dir: str, env_extra: dict, ready_timeout_s: int = 300):
    """起一个全新桥接（跑包内 ext/）。返回 (proc, log_path, err_path, ready)。"""
    py = os.path.join(app, 'python', 'python.exe')
    log = os.path.join(out_dir, 'bridge.log')
    err = os.path.join(out_dir, 'bridge.err')
    token = os.path.join(out_dir, 'bridge_token.txt')

    env = dict(os.environ)
    # 🔴 Windows 上 `os.environ` 已把同名不同大小写的键合并 ⇒ 不会撞键
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['EXT_APP_ROOT'] = app
    env['EXT_APP_SEARCH_ROOT'] = app
    env['PYTHONPATH'] = os.pathsep.join(
        [app, os.path.join(app, 'ext', '.runtime_deps')])
    env['EXT_BG_CACHE_DIR'] = os.path.join(os.path.dirname(out_dir), '_bg_ov_cache')
    # 每个臂先清掉上一臂的设备环境变量
    for k in ('EXT_TTS_DEVICE', 'EXT_MT_DEVICE', 'EXT_ASR_DEVICE', 'EXT_BG_DEVICE'):
        env.pop(k, None)
    for k, v in (env_extra or {}).items():
        env[k] = v

    fh_log = open(log, 'wb')
    fh_err = open(err, 'wb')
    cmd = [py, '-X', 'utf8', '-m', 'ext.bridge', '--real', '--pipeline',
           '--port', '8765', '--delay', '20', '--target-lang', 'zh',
           '--token-file', token,
           # 🔴 逐段余量表落盘（**臂目录**里 ⇒ 客户包一个字节都不动）
           #    ⇒ 客户端发 `dump_margin` 时才有地方写 ⇒ 才有 tts_sec/speech_sec
           #    ⇒ 才能算 synth_rtf。
           '--margin-out', os.path.join(out_dir, 'margin.json')]
    proc = subprocess.Popen(cmd, cwd=app, env=env,
                            stdout=fh_log, stderr=fh_err,
                            creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    ready = False
    deadline = time.time() + ready_timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            with open(log, 'r', encoding='utf-8', errors='replace') as fh:
                if 'ws://127.0.0.1:8765' in fh.read():
                    ready = True
                    break
        except OSError:
            pass
        time.sleep(3)
    return proc, log, err, token, ready


def stop_bridge(proc, fh_log=None, fh_err=None):
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    for fh in (fh_log, fh_err):
        try:
            if fh:
                fh.close()
        except Exception:
            pass


def parse_devices(err_path: str) -> dict:
    """从 bridge.err 解析**实际设备**（reviewer 要求「解析出来的实际设备」）。"""
    dev = {}
    try:
        with open(err_path, 'r', encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
    except OSError:
        return dev
    pats = [
        ('asr', r'ASR 就绪（([^）]*)）'),
        ('mt', r'加载翻译模型（([^）]*)）'),
        ('tts_exec_devices', r'实测执行设备：([^\r\n]*)'),
        ('tts_load_device', r'加载模型：device=(\S*)'),
        ('cp_decode_selfcheck', r'cp_decode: NPU 自检通过（耗时 ([^）]*)'),
        ('cp_prefill_selfcheck', r'cp_prefill: NPU 自检通过（耗时 ([^）]*)'),
        ('vocoder_window', r'APP-123 声码器窗口：([^\r\n]*)'),
        ('decoder', r'使用 (MultiDecoderBabelVox[^（]*)'),
        ('speaker_library', r'SpeakerLibrary 就绪：([^\r\n]*)'),
        ('na_guard', r'NaN 守卫已装 (\d+) 个'),
    ]
    import re
    for key, pat in pats:
        m = re.search(pat, txt)
        if m:
            dev[key] = m.group(1).strip()
    return dev


def run_arm(app, root, name, env_extra, media, drain_cap, tail_wait, max_sec,
            voice, extra_args, bridge_root, tool, events_path):
    out = os.path.join(root, name)
    os.makedirs(out, exist_ok=True)
    if not ports_free((8765, 8766)):
        return {'arm': name, 'error': 'ports_busy'}
    t0 = time.time()
    proc, log, err, token, ready = start_bridge(app, out, env_extra)
    if not ready:
        rc = proc.poll()
        stop_bridge(proc)
        append_event(events_path, {'ev': 'arm_not_ready', 'arm': name, 'bridge_rc': rc})
        return {'arm': name, 'error': 'bridge_not_ready', 'bridge_rc': rc}
    try:
        cmd = [os.path.join(app, 'python', 'python.exe'), '-X', 'utf8', tool,
               '--media', media, '--port', '8765', '--delay', '20',
               '--target-lang', 'zh', '--token-file', token, '--out', out,
               '--voice', voice, '--bridge-root', bridge_root,
               '--drain-cap', str(drain_cap)] + list(extra_args)
        if max_sec:
            cmd += ['--max-sec', str(max_sec)]
        with open(os.path.join(out, 'e2e_stdout.txt'), 'wb') as so:
            cp = subprocess.run(cmd, cwd=bridge_root,
                                stdout=so, stderr=subprocess.STDOUT)
        rc = cp.returncode
    finally:
        try:
            peak_ws_mb = round(proc.memory_info().rss / (1 << 20))
        except Exception:
            peak_ws_mb = None
        stop_bridge(proc)
    elapsed = int(time.time() - t0)

    res = {'arm': name, 'rc': rc, 'elapsed_s': elapsed, 'peak_ws_mb': peak_ws_mb,
           'env': env_extra}
    jf = os.path.join(out, 'bgkeep_e2e.json')
    if os.path.isfile(jf):
        with open(jf, 'r', encoding='utf-8') as fh:
            j = json.load(fh)
        d = j.get('drain') or {}
        pl = (j.get('stats_full') or {}).get('pipeline') or {}
        dl = j.get('dub_late_final_summary') or {}
        mg = (j.get('stats_full') or {}).get('margin') or {}
        res.update({
            'dubs': j.get('dubs'),
            'n_submitted': pl.get('n_submitted'),
            'n_emitted': pl.get('n_emitted'),
            'n_pending': pl.get('n_pending'),
            'n_pending_at_media_end': d.get('n_pending_at_media_end'),
            'n_emitted_at_media_end': d.get('n_emitted_at_media_end'),
            'n_submitted_at_media_end': d.get('n_submitted_at_media_end'),
            'n_pending_after_drain': d.get('n_pending_after_drain'),
            'drained_to_zero': d.get('drained_to_zero'),
            'drain_elapsed_s': d.get('drain_elapsed_sec'),
            'dub_late_max': dl.get('max'),
            'dub_late_p90': dl.get('p90'),
            'dub_late_p50': dl.get('p50'),
            'dub_late_n': dl.get('n'),
            'last_segment_lag': mg.get('last_segment_lag_sec'),
            'lag_slope': mg.get('lag_growth_slope_sec_per_sec'),
            'lag_r2': mg.get('lag_growth_r2'),
            'bg_late_blocks': j.get('bg_late_blocks'),
            'synth_rtf': (j.get('synth_rtf') or {}).get('synth_rtf'),
            'synth_rtf_n': (j.get('synth_rtf') or {}).get('n_segments_with_tts'),
            'synth_rtf_cross_check_ok': (j.get('synth_rtf') or {}).get('cross_check_ok'),
            'speech_over_src': (j.get('synth_rtf') or {}).get('ext_speech_over_src'),
            'tts_over_src': (j.get('synth_rtf') or {}).get('ext_tts_over_src'),
            'proc_mem_mb': (j.get('stats_full') or {}).get('proc_mem_mb'),
            'clone_reasons': (j.get('stats_full') or {}).get('clone_reasons'),
            'n_gender_splits': (j.get('stats_full') or {}).get('n_gender_splits'),
            'devices': parse_devices(err),
            'json': jf,
        })
    else:
        res['error'] = 'no_bgkeep_e2e_json'
    append_event(events_path, {'ev': 'arm_done', 'arm': name, 'rc': rc,
                               'elapsed_s': elapsed, 'lock_lost': 0})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', required=True, help='客户包目录（不修改它）')
    ap.add_argument('--root', required=True, help='输出根目录')
    ap.add_argument('--arms', required=True,
                    help='"name:ENV=VAL|ENV=VAL,name2:"（空规格 = AUTO）')
    ap.add_argument('--bridge-root', default='', help='默认 = --app')
    ap.add_argument('--media', default=DEFAULT_MEDIA)
    ap.add_argument('--drain-cap', type=float, default=300.0)
    ap.add_argument('--tail-wait', type=float, default=30.0)
    ap.add_argument('--max-sec', type=float, default=None)
    ap.add_argument('--voice', default='A')
    ap.add_argument('--bg-off', action='store_true')
    ap.add_argument('--lock', default=os.path.join(HOME, 'shared', 'MACHINE_LOCK'))
    ap.add_argument('--lock-wait-s', type=int, default=7200)
    args = ap.parse_args()

    app = os.path.abspath(args.app)
    root = os.path.abspath(args.root)
    bridge_root = os.path.abspath(args.bridge_root or app)
    tool = os.path.join(HERE, '_app137_e2e_drain.py')
    os.makedirs(root, exist_ok=True)
    events_path = os.path.join(root, '_lock_events.jsonl')

    tag_base = 'app e2e drain'
    tag = '%s %s pid=%d' % (tag_base, time.strftime('%Y-%m-%dT%H:%M:%S'), os.getpid())
    ok, waited = acquire_lock(args.lock, tag, args.lock_wait_s)
    if not ok:
        print('LOCK BUSY >%ds :: %s' % (args.lock_wait_s, waited), flush=True)
        return 3
    append_event(events_path, {'ev': 'lock_acquired', 'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
                               'tag': tag, 'waited_s': waited})
    print('lock taken after %ds :: %s' % (waited, tag), flush=True)

    summary = []
    try:
        for spec in args.arms.split(','):
            spec = spec.strip()
            if not spec:
                continue
            name, _, envspec = spec.partition(':')
            env_extra = {}
            if envspec:
                for kv in envspec.split('|'):
                    if not kv:
                        continue
                    k, _, v = kv.partition('=')
                    env_extra[k] = v
            extra = ['--bg-off'] if args.bg_off else []
            print('== arm %s env=%s' % (name, env_extra), flush=True)
            r = run_arm(app, root, name, env_extra, args.media, args.drain_cap,
                        args.tail_wait, args.max_sec, args.voice, extra,
                        bridge_root, tool, events_path)
            summary.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1), flush=True)
    finally:
        sp = os.path.join(root, '_summary.json')
        with open(sp, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=1)
        if release_lock(args.lock, tag):
            append_event(events_path, {'ev': 'lock_released',
                                       'ts': time.strftime('%Y-%m-%dT%H:%M:%S')})
            print('lock released', flush=True)
        else:
            print('LOCK NOT RELEASED (tag mismatch) -- 保留给下一个 job', flush=True)
    print('driver done', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
