#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app314_rc5_exec_device.py —— **rc5 的「实际执行设备」直证**（APP-096 §3a）。

## 为什么需要这个脚本（App 日志不够）

App 的日志只打「加载 Intel NPU · INT8」⇒ 那是 **App 自己声称的**，
不是 OpenVINO 层面的事实。

⇒ 本脚本**用包内自己的 python**，按 App 的**同一路径**造出后端
（`asr06b_backend.ASR06BBackend`），然后读**编译产物**的
`EXECUTION_DEVICES` 属性：

    be.enc → encoder 的实际落点
    be.dec → decoder 的实际落点

⚠️ **必须是「包内 python」**：包内带的是随包发版的 OV 2026.4.1，
开发机 .venv 的 OV 版本可能不同 ⇒ 验收要用**客户环境的那一份**。

## 🔴 纪律

* 缓存写**独立临时目录** ⇒ 不复用 Panther Lake 的产物冒充可移植性证据。
* 编译要占设备 ⇒ **持 MACHINE_LOCK**。
* **不写死 NPU 架构 5010**（APP-096 §3d：目标机是 Meteor Lake / arch 不同）。

## 用法

```
.venv/Scripts/python.exe results/app/_app314_rc5_exec_device.py --device NPU
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
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
REPORT = os.path.join(HERE, 'app314_rc5_exec_device_evidence.json')

#: 在**包内 python** 里跑的探针源码
#: ⚠️ 用 `@PKG@` 占位（**不是** `%s`）——探针内部有 `%s` 格式化（`"<err:%s>"`）
#:    ⇒ 用 `%` 做占位会把它们一起吃掉（第一版实测 `TypeError: not enough arguments`）。
PROBE = r'''
import json, os, sys, time
sys.path.insert(0, os.path.join(r"@PKG@", "app"))
from asr06b_backend import ASR06BBackend

PKG = r"@PKG@"
MODELS = os.path.join(PKG, "models")
dev = sys.argv[1]
cache = sys.argv[2]

def mp(name):
    return os.path.join(MODELS, name)

t0 = time.time()
be = ASR06BBackend(
    encoder_dir=mp("asr06b-encoder-fp16"),
    decoder_dir=mp("asr06b-decoder-int8"),
    tokenizer_dir=mp("asr06b-tokenizer"),
    embed_npy=mp("embed_tokens_06b_f16.npy"),
    device=dev, precision="f16", cache_dir=cache, strict_intel=False)
load_s = time.time() - t0

def exec_devices(cm):
    """🔴🔴🔳 **不要**盲目 `list()`！

    OV 的 `EXECUTION_DEVICES` **返回值类型随设备而异**：
      · NPU 档返回**字符串** `'NPU'`
      · 其他设备可能返回**列表**
    ⇒ `list('NPU')` ⇒ `['N','P','U']`（**字符拆开**）⇒ 会误判成「不在 NPU」。
    （这正是旧「fallback 链」误读的根源。）
    ⇒ 这里**保留原始类型**，并额外给一个归一化后的字符串列表。
    """
    try:
        raw = cm.get_property("EXECUTION_DEVICES")
    except Exception as e:
        return {"raw": None, "norm": [], "error": str(e)}
    if isinstance(raw, str):
        norm = [raw]
    else:
        norm = [str(x) for x in raw]
    return {"raw": raw if isinstance(raw, str) else list(raw),
            "norm": norm}

out = {
    "device_requested": dev,
    "enc_exec_devices": exec_devices(be.enc),
    "dec_exec_devices": exec_devices(be.dec),
    "load_s": round(load_s, 1),
    "cache_dir": cache,
}
try:
    out["enc_device_arch"] = be.enc.get_property("DEVICE_ARCHITECTURE")
except Exception:
    out["enc_device_arch"] = None
try:
    out["dec_device_arch"] = be.dec.get_property("DEVICE_ARCHITECTURE")
except Exception:
    out["dec_device_arch"] = None
print("__PROBE__" + json.dumps(out, ensure_ascii=False))
'''


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def on_target(devs, want):
    """判「实际落点是不是目标设备」（兼容 raw 是字符串或列表）。

    ⚠️ 这份**主进程**侧的判定与探针内的同名函数**同口径**
    （探针在**子进程**里跑 ⇒ 它内部的那份是独立的）。
    """
    norm = (devs or {}).get('norm') or []
    return any(want.upper() in str(d).upper() for d in norm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    args = ap.parse_args()

    ev = {
        'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'pkg': PKG,
        'device': args.device,
        'correction': 'APP-096 §3a (EXECUTION_DEVICES evidence) + §3d (no hardcoded 5010)',
    }

    # ── 机器锁 ────────────────────────────────────────────────────
    lock_payload = None
    for _ in range(180):
        if not os.path.exists(LOCK):
            payload = ('module=app-rc5-execdev\npid=%d\nstarted=%s\n'
                       % (os.getpid(), datetime.datetime.now().isoformat()))
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, payload.encode('utf-8'))
                os.close(fd)
                lock_payload = payload.strip()
                break
            except FileExistsError:
                pass
        time.sleep(10)
    if lock_payload is None:
        print('!! 拿不到锁')
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev)
        return 2
    ev['lock'] = lock_payload

    try:
        cache = tempfile.mkdtemp(prefix='rc5_execdev_')
        probe = PROBE.replace('@PKG@', PKG)
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['LOCALAPPDATA'] = cache
        py = os.path.join(PKG, 'python', 'python.exe')
        cmd = [py, '-c', probe, args.device, cache]
        print('[run] %s' % ' '.join(cmd))
        p = subprocess.run(cmd, env=env, cwd=PKG, capture_output=True,
                           text=True, timeout=1800)
        out = None
        for line in p.stdout.split('\n'):
            if line.startswith('__PROBE__'):
                out = json.loads(line[len('__PROBE__'):])
        if out is None:
            ev['verdict'] = 'PROBE_FAILED'
            ev['stdout_tail'] = p.stdout[-3000:]
            ev['stderr_tail'] = p.stderr[-3000:]
        else:
            ev.update(out)
            want = args.device
            enc_ok = on_target(out['enc_exec_devices'], want)
            dec_ok = on_target(out['dec_exec_devices'], want)
            ev['enc_on_target_device'] = enc_ok
            ev['dec_on_target_device'] = dec_ok
            ev['verdict'] = 'PASS' if (enc_ok and dec_ok) else 'FAIL'
        ev['stdout_tail'] = p.stdout[-1500:]
        ev['stderr_tail'] = p.stderr[-1500:]
    finally:
        # 🔴 **只删自己持有的锁**（不是自己的 ⇒ 不动）
        # ⚠️ 第一版用 `except OSError` 兜底，但 `os.remove` 在**别的进程**
        #    持有锁时会成功删掉别人的锁 ⇒ 必须先核对 pid。
        ev['lock_released'] = False
        try:
            if os.path.exists(LOCK):
                with open(LOCK, encoding='utf-8', errors='replace') as f:
                    mine = ('pid=%d' % os.getpid()) in f.read()
                if mine:
                    os.remove(LOCK)
                    ev['lock_released'] = True
        except OSError:
            ev['lock_released'] = False
        ev['lock_exists_after'] = os.path.exists(LOCK)

    _dump(ev)
    print(json.dumps({k: ev.get(k) for k in
                      ('verdict', 'enc_exec_devices', 'dec_exec_devices',
                       'enc_on_target_device', 'dec_on_target_device',
                       'npu_arch', 'lock_released')}, ensure_ascii=False, indent=1))
    return 0 if ev.get('verdict') == 'PASS' else 1


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)


if __name__ == '__main__':
    sys.exit(main())
