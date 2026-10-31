#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-050 取证 runner：**持机器锁**跑子脚本并落盘证据。

## 为什么需要这个壳

- 「编译 NPU IR」会吃 CPU ⇒ 必须持 `shared/MACHINE_LOCK`（共享机器锁）。
- MEMORY 铁律：**等锁循环不得反复「建 tmp + 删 tmp」** ⇒ 用仓库既有的
  `machine_lock_app.acquire()`（**先探测 ⇒ 0 次文件写入**）。
- 回收锁前必须用 ctypes 的 `OpenProcess` + `GetExitCodeProcess` 确认 PID 真死，
  **探测失败一律视为存活**（`machine_lock_app` 内部已实现，见 `lock_state`）。

## 用法

    <pkg>/python/python.exe results/app/app174_run_with_lock.py \
        --script results/app/app174a_probe_exec_devices_type.py \
        --out results/app/app174a_exec_devices_type.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--script', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--timeout', type=float, default=1800.0)
    args = ap.parse_args()

    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    import machine_lock_app as ml

    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                  verbose=True)
    if not ok_lock:
        print('[lock] ❌ 未取得机器锁 ⇒ 放弃')
        return 3
    print('[lock] 已持有')

    script = os.path.abspath(args.script)
    out = os.path.abspath(args.out)
    try:
        print('[run] %s' % script)
        t0 = time.perf_counter()
        # 🔴 把 out 路径作为 argv[1] 传给子脚本 ⇒ 子脚本**自己**落盘证据
        #   （runner 不再包一层 ⇒ 下游可直接 json.load 证据文件）
        proc = subprocess.run([sys.executable, script, out], cwd=REPO,
                              capture_output=True, timeout=args.timeout)
        dt = round(time.perf_counter() - t0, 2)
        print('[run] rc=%s wall=%.1fs' % (proc.returncode, dt))
        stdout = proc.stdout.decode('utf-8', 'replace')
        stderr = proc.stderr.decode('utf-8', 'replace')
        print(stdout[-3000:])
        if stderr.strip():
            print('[stderr]\n' + stderr[-2000:])

        # 🔴 子脚本**已自己**落盘证据 ⇒ 只补 runner 元数据
        if os.path.isfile(out):
            try:
                with open(out, encoding='utf-8') as f:
                    parsed = json.load(f)
            except Exception:
                parsed = {'raw_stdout': stdout, 'raw_stderr': stderr}
        else:
            parsed = {'raw_stdout': stdout, 'raw_stderr': stderr}
        parsed['_runner'] = {
            'script': script,
            'script_sha256': sha256(script),
            'returncode': proc.returncode,
            'wall_s': dt,
            'python_exe': sys.executable,
        }
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        print('[out] %s bytes=%d sha256=%s'
              % (out, os.path.getsize(out), sha256(out)))
        return 0 if proc.returncode == 0 else 1
    finally:
        try:
            ml.release(payload)
            print('[lock] 已释放')
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
