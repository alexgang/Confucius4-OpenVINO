#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-050 端到端取证：**真的起一个 TTS worker**，抓它 stdout 里的那一行。

## 为什么还要这一层（§174c 只测了 `make_engine` 直接调用）

§174c 证明的是 `tts_engine.make_engine()` 会打出那一行。
但 APP-050 要求的是「**TTS 启动日志**」⇒ 真实路径是：

    GUI → TTSService → Popen(tts_worker.py) → worker stdout → on_log → 会话日志

⇒ **必须证明那一行真的从 worker 进程流到主进程**，否则
「代码里有这行」≠「用户看得到这行」。

## 本脚本做什么（**不推理**）

- 用**客户包自带 python** 起 `app/tts_worker.py --device NPU`
- 只读它 stdout 前若干行 ⇒ 找到 `EXECUTION_DEVICES` 那行
- 然后**优雅关闭**（发 `{"cmd":"quit"}`）⇒ 不合成任何句子
- 落盘证据 JSON

🔴 worker 启动会**加载模型**（编译 NPU IR）⇒ 吃 CPU ⇒ **必须持机器锁**
   （用 `results/app/app174_run_with_lock.py` 这个壳跑）。

## 用法

    <pkg>/python/python.exe results/app/app174_run_with_lock.py \
        --script results/app/app174d_worker_startup_e2e.py \
        --out results/app/app174d_worker_startup_e2e.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

PKG_ROOT = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13'
PKG_APP = os.path.join(PKG_ROOT, 'app')
PY = os.path.join(PKG_ROOT, 'python', 'python.exe')
WORKER = os.path.join(PKG_APP, 'tts_worker.py')


def main() -> int:
    out = {'pkg_root': PKG_ROOT, 'worker': WORKER, 'python': PY}
    out['worker_exists'] = os.path.isfile(WORKER)
    out['python_exists'] = os.path.isfile(PY)
    if not (out['worker_exists'] and out['python_exists']):
        print('[FATAL] 包内 worker / python 不存在')
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    # 🔴 离线优先（不让它联网查 HF）
    env['HF_HUB_OFFLINE'] = '1'

    cmd = [PY, WORKER, '--device', 'NPU', '--precision', 'f16']
    out['cmd'] = cmd
    print('[spawn] %s' % ' '.join(cmd), flush=True)
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=PKG_APP, env=env,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    lines = []
    key4 = ''
    ready = False
    deadline = time.time() + 900.0
    try:
        # 🔴 只读到「ready」或超时 ⇒ **不合成任何句子**
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            s = line.decode('utf-8', 'replace').rstrip('\r\n')
            if not s:
                continue
            lines.append(s)
            if 'EXECUTION_DEVICES' in s and not key4:
                key4 = s
                print('[key4] %s' % s, flush=True)
            if '"kind": "ready"' in s or '"kind":"ready"' in s:
                ready = True
                break
            if '"kind": "error"' in s or '"kind":"error"' in s:
                print('[worker error] %s' % s, flush=True)
                break
    finally:
        try:
            proc.stdin.write(b'{"cmd":"quit"}\n')
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()

    out['wall_s'] = round(time.perf_counter() - t0, 2)
    out['n_lines'] = len(lines)
    out['key4_line'] = key4
    out['ready_seen'] = ready
    out['stdout_head'] = lines[:40]
    try:
        out['stderr_tail'] = proc.stderr.read().decode('utf-8', 'replace')[-1500:]
    except Exception:
        out['stderr_tail'] = ''

    checks = [
        ('worker启动成功', ready, str(ready)),
        ('捕获到EXECUTION_DEVICES行', bool(key4), key4),
        ('该行含talker=', 'talker=' in key4, key4),
        ('该行含cp_prefill=', 'cp_prefill=' in key4, key4),
        ('该行含cp_decode=', 'cp_decode=' in key4, key4),
        ('该行含decoder=', 'decoder=' in key4, key4),
        ('talker=NPU', 'talker=NPU' in key4, key4),
        ('cp_prefill=NPU', 'cp_prefill=NPU' in key4, key4),
        ('cp_decode=NPU', 'cp_decode=NPU' in key4, key4),
        ('decoder无?占位', 'decoder=?' not in key4, key4),
    ]
    out['checks'] = [dict(name=n, ok=bool(ok), detail=d) for n, ok, d in checks]
    out['n_pass'] = sum(1 for _n, ok, _d in checks if ok)
    out['n_fail'] = len(checks) - out['n_pass']
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'

    _ev = sys.argv[1] if len(sys.argv) > 1 else None
    if _ev:
        os.makedirs(os.path.dirname(os.path.abspath(_ev)), exist_ok=True)
        with open(_ev, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('[evidence] %s' % os.path.abspath(_ev))

    print(json.dumps({k: v for k, v in out.items()
                      if k not in ('stdout_head', 'stderr_tail')},
                     ensure_ascii=False, indent=2))
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
