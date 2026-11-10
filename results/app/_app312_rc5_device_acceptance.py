#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app312_rc5_device_acceptance.py —— **MiniMVP v1.0-rc5 设备级验收**（APP-096 §3a）。

## 依据

* **APP-096 §3a**：用 rc4 §161 的同一份 5 分钟英文切片
  （`shared/SPE_0000_0500.wav`），**0.6B iGPU 和 0.6B NPU 各跑一次**，
  把 **transcript 落盘**交给 reviewer 复算 WER，
  并和 rc4 的 R2T2 数字并排列出（rc4 5 分钟：**NPU 15.53 % / iGPU 14.55 %**）；
  另报 **RTF、首词延迟 P50、最大积压、峰值内存**；
  给出 **EXECUTION_DEVICES** 证据（NPU 臂必须 encoder=NPU、decoder=NPU）。
* **APP-096 §4**：计时臂必须**正确持有** `shared/MACHINE_LOCK`，做完释放。

## 🔴🔴🔴 与 rc4 完全同口径（否则数字不可比）

* **命令**照抄 `_app294_rc4_npu_acceptance.py::build_cmd`：
  `--cli --file WAV --engine <e> --asr-device <d> --translate zh
  --mt-device GPU.0 --mt-engine gpu_int4cw --tts off --speaker off
  --max-seconds 300 --out transcript.txt`
* 🔴 **`--tts off` 是隔离口径**：rc4 实测「NPU 全家桶 RTF 1.284 / 出字延迟 57.8 s」
  那是 **TTS 与 ASR 抢 NPU 的争用**，不是 ASR 本身慢 ⇒ 计时臂必须关 TTS。
* **summary 正则**照抄 `_RE_SUMMARY`（同一口径 ⇒ 数字可与 rc4 直接并排）。

## 🔴 锁泄漏防护（**本轮实测踩到**）

第一版脚本被 `timeout` 的 SIGTERM 杀掉时，`finally` **没有执行**
⇒ 锁留在 `shared/MACHINE_LOCK` 里变成孤儿锁。
⇒ 本版：
  ① 注册 `SIGTERM`/`SIGINT` 处理器 ⇒ **优雅释放锁**；
  ② 释放前**校验锁里的 pid 是自己**（不是自己就不删）；
  ③ 收尾**再确认一次**锁已消失（落进证据）。

## 用法

```
.venv/Scripts/python.exe results/app/_app312_rc5_device_acceptance.py --arm gpu
.venv/Scripts/python.exe results/app/_app312_rc5_device_acceptance.py --arm npu
```
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
WAV = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_ROOT = os.path.join(HERE, 'app312_rc5_out')

#: rc4 §161 的 R2T2 参照数字（reviewer 要的「并排列出」）
RC4_REF = {
    'npu': {'wer_pct': 15.5266, 'rtf': 0.803, 'latency_ms': 540,
            'peak_mem_mb': 5212.6},
    'gpu': {'wer_pct': 14.5494, 'rtf': 0.696, 'latency_ms': 376,
            'peak_mem_mb': 4819.5},
}

ARMS = {
    'npu': dict(engine='npu_int8', asr_device='NPU'),
    'gpu': dict(engine='gpu_int8', asr_device='GPU.0'),
}

#: 🔴 与 rc4 **逐字同一口径**的 summary 正则
_RE_SUMMARY = re.compile(
    r'\[(?P<engine>\w+)\]\s*音频\s+(?P<audio>[\d.]+)s\s+'
    r'墙钟\s+(?P<wall>[\d.]+)s\s+RTF\(计算\)\s+(?P<rtf>[\d.]+)\s+'
    r'出字延迟中位\s+(?P<lat>\d+)\s*ms\s+'
    r'最大积压\s+(?P<backlog>[\d.]+)s\s+段\s+(?P<segs>\d+)')


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════
# 机器锁（🔴 fail-closed）
# ══════════════════════════════════════════════════════════════════════
def _lock_owned_by_me() -> bool:
    if not os.path.exists(LOCK):
        return False
    try:
        with open(LOCK, encoding='utf-8', errors='replace') as f:
            return ('pid=%d' % os.getpid()) in f.read()
    except OSError:
        return False


def acquire_lock(module: str) -> dict:
    waited = []
    for _ in range(180):          # 最多等 30 分钟
        if not os.path.exists(LOCK):
            payload = ('module=%s\npid=%d\nstarted=%s\n'
                       % (module, os.getpid(),
                          datetime.datetime.now().isoformat()))
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, payload.encode('utf-8'))
                os.close(fd)
                return {'acquired': True, 'waited_s': len(waited) * 10,
                        'payload': payload.strip()}
            except FileExistsError:
                pass
        try:
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                waited.append(f.read().strip())
        except OSError:
            pass
        time.sleep(10)
    return {'acquired': False, 'waited_s': len(waited) * 10,
            'waited_last': waited[-1] if waited else None}


def release_lock() -> bool:
    """🔴 只删**自己**持有的锁（不是自己的 ⇒ 不动）。"""
    if not os.path.exists(LOCK):
        return False
    if not _lock_owned_by_me():
        return False
    try:
        os.remove(LOCK)
        return True
    except OSError:
        return False


def _install_signal_handlers():
    def _handler(signum, _frame):
        print('\n[signal] 收到 %d ⇒ 释放锁并退出' % signum, flush=True)
        release_lock()
        sys.exit(128 + signum)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            pass


# ══════════════════════════════════════════════════════════════════════
# 峰值内存采样（🔴 不遮蔽 Thread._stop）
# ══════════════════════════════════════════════════════════════════════
class MemSampler:
    def __init__(self, pid: int, interval: float = 0.5):
        import threading
        self.pid = pid
        self.interval = interval
        self.peak_mb = 0.0
        self._stopev = threading.Event()
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()

    def _rss_mb(self) -> float:
        try:
            import psutil
            return psutil.Process(self.pid).memory_info().rss / (1 << 20)
        except Exception:
            return 0.0

    def _loop(self):
        while not self._stopev.is_set():
            m = self._rss_mb()
            if m > self.peak_mb:
                self.peak_mb = m
            self._stopev.wait(self.interval)

    def stop(self) -> float:
        self._stopev.set()
        self._th.join(timeout=5)
        return round(self.peak_mb, 1)


def build_cmd(arm: str, out: str, seconds: float) -> list:
    """🔴 与 rc4 **同口径**（含 `--tts off` 隔离）。"""
    cfg = ARMS[arm]
    return [
        PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
        '--cli', '--file', WAV,
        '--engine', cfg['engine'],
        '--asr-device', cfg['asr_device'],
        '--translate', 'zh',
        '--mt-device', 'GPU.0', '--mt-engine', 'gpu_int4cw',
        '--tts', 'off',
        '--speaker', 'off',
        '--max-seconds', str(int(seconds)),
        '--out', os.path.join(out, 'transcript.txt'),
    ]


def parse_summary(log_path: str) -> dict:
    out = {}
    try:
        txt = open(log_path, encoding='utf-8', errors='replace').read()
    except OSError:
        return out
    m = None
    for m in _RE_SUMMARY.finditer(txt):
        pass
    if m:
        d = m.groupdict()
        for k in ('audio', 'wall', 'rtf', 'backlog'):
            try:
                d[k] = float(d[k])
            except (TypeError, ValueError):
                d[k] = None
        try:
            d['lat_ms'] = int(d['lat'])
        except (TypeError, ValueError):
            d['lat_ms'] = None
        try:
            d['segs'] = int(d['segs'])
        except (TypeError, ValueError):
            pass
        out['summary'] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['gpu', 'npu'], required=True)
    ap.add_argument('--seconds', type=float, default=300.0)
    args = ap.parse_args()

    _install_signal_handlers()

    out_dir = os.path.join(OUT_ROOT, args.arm)
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    ev = {
        'arm': args.arm,
        'started_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'pkg': PKG,
        'wav': WAV,
        'wav_sha256': sha256_file(WAV) if os.path.exists(WAV) else None,
        'seconds': args.seconds,
        'rc4_ref': RC4_REF.get(args.arm),
        'cmd': build_cmd(args.arm, out_dir, args.seconds),
    }

    print('[lock] 申请 MACHINE_LOCK …', flush=True)
    lk = acquire_lock('app-rc5-acceptance-%s' % args.arm)
    ev['lock'] = lk
    if not lk['acquired']:
        print('!! 拿不到锁 ⇒ 放弃')
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev, out_dir)
        return 2
    print('[lock] 已持有：%s' % lk['payload'].replace('\n', ' '), flush=True)

    try:
        # ── 缓存写独立临时目录（不复用 Panther Lake 产物冒充证据）────
        cache_dir = tempfile.mkdtemp(prefix='rc5_cache_%s_' % args.arm)
        env = dict(os.environ)
        env['LOCALAPPDATA'] = cache_dir
        env['PYTHONIOENCODING'] = 'utf-8'
        env['LIVECAP_MODELS_DIR'] = os.path.join(PKG, 'models')
        ev['cache_dir'] = cache_dir

        cmd = ev['cmd']
        print('[run] %s' % ' '.join(cmd), flush=True)
        t0 = time.time()
        proc = subprocess.Popen(cmd, env=env, cwd=PKG,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        ev['pid'] = proc.pid
        sampler = MemSampler(proc.pid)
        out_log = os.path.join(out_dir, 'run.log')
        with open(out_log, 'wb') as lf:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                lf.write(line)
                lf.flush()
        rc = proc.wait()
        wall = time.time() - t0
        peak = sampler.stop()
        ev['rc'] = rc
        ev['wall_s'] = round(wall, 2)
        ev['peak_rss_mb'] = peak
        ev['log_bytes'] = os.path.getsize(out_log)

        ev.update(parse_summary(out_log))

        for name in ('transcript.txt', 'transcript.mt.txt'):
            p = os.path.join(out_dir, name)
            if os.path.exists(p):
                ev.setdefault('artifacts', {})[name] = {
                    'bytes': os.path.getsize(p),
                    'sha256': sha256_file(p),
                    'mtime': datetime.datetime.fromtimestamp(
                        os.path.getmtime(p)).isoformat(timespec='seconds')}
        tp = os.path.join(out_dir, 'transcript.txt')
        if os.path.exists(tp):
            txt = open(tp, encoding='utf-8', errors='replace').read()
            ev['transcript_chars'] = len(txt)
            ev['transcript_head'] = txt[:800]

        ev['finished_at'] = datetime.datetime.now().isoformat(timespec='seconds')
        ev['verdict'] = 'RAN' if rc == 0 else 'RC_%d' % rc
    finally:
        ev['lock_released'] = release_lock()
        ev['lock_exists_after'] = os.path.exists(LOCK)
        print('[lock] 已释放：%s（残留=%s）'
              % (ev['lock_released'], ev['lock_exists_after']), flush=True)
        _dump(ev, out_dir)

    return 0


def _dump(ev, out_dir):
    p = os.path.join(out_dir, 'acceptance.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % p, flush=True)


if __name__ == '__main__':
    sys.exit(main())
