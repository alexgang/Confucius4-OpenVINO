# -*- coding: utf-8 -*-
r"""_app497 — **EXT 启动器隔离验收**（APP-104 §3 的第 3 条，带锁）。

## 为什么要有这个单独一轮
reviewer 的验收要求「在包目录里用 bat 启动桥接，日志出现「真实引擎已接线」
和「TTS 就绪」，截一张启动器的图（不能有目标语言下拉框），然后停掉桥接」。

🔴 **实测发现：本机 8765 端口被「别人」的桥接占着** —— 那是
   **reviewer 自己**在跑的实例（`Confucius4_LiveCaption_v2.4\\python\\python.exe
   -m ext.bridge --port 8765`，PID 23448，12:13:46 起）⇒ 包内启动器
   按设计**拒绝**起第二个实例（「已有实例在运行」/「端口已被占用」）
   ⇒ 那不是包的问题，是**环境占用**。

⇒ 本轮做法（**不碰别人的进程、不改包内文件**）：
  * 持 MACHINE_LOCK（设备作业）；
  * **只在运行时覆盖**启动器的端口（8765 → 8785）与 PID 文件位置
    （`ext_launcher.DEFAULT_PORT` / `PID_PATH` 是模块属性，
    `BridgeRunner(port=…, pid_path=…)` 本来就支持）
    ⇒ **包内 `tools/ext_launcher.py` 与 817abcb 仍逐字节一致**；
  * 其余流程与包内文档一致：启动器 GUI → 点「启动」⇒ 桥接真实引擎
    ⇒ 日志「真实引擎已接线」＋ 窗口标题「TTS 就绪」→ 截图 → 停桥接。

跑法：
    python results/app/_app497_ext_launcher_isolated.py [port]
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc9')
OUTROOT = os.path.join(HERE, 'app493_app104_rc9_acceptance')
REPORT = os.path.join(HERE, 'app497_app104_ext_launcher_isolated.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
ISOLATE_DIR = os.path.join(HERE, 'app497_isolated')
DRIVER = os.path.join(HERE, '_app494_ext_launcher_drive.py')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def pid_alive(pid):
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    if not ok:
        return True
    return code.value == 259


def acquire_lock(tag):
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('utf-8'))
        os.close(fd)
        return payload
    except FileExistsError:
        pass
    info = open(LOCK, encoding='utf-8', errors='replace').read()
    m = re.match(r'\S+\s+(\d+)\s', info)
    if m and pid_alive(int(m.group(1))):
        return None
    return None


def release_own_lock(payload):
    try:
        if os.path.exists(LOCK):
            cur = open(LOCK, encoding='utf-8', errors='replace').read()
            if cur != payload:
                print('!! 锁内容已变，拒绝删除：%r' % cur[:120])
                return False
            os.remove(LOCK)
            return True
    except Exception as e:
        print('!! 释放锁异常：%r' % e)
    return False


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8785
    os.makedirs(OUTROOT, exist_ok=True)
    os.makedirs(ISOLATE_DIR, exist_ok=True)
    pidfile = os.path.join(ISOLATE_DIR, 'bridge.pid')
    shot = os.path.join(OUTROOT, 'ext_launcher.png')
    djson = os.path.join(OUTROOT, 'ext_launcher.json')

    payload = acquire_lock('app104_ext_isolated')
    if not payload:
        print('🔴 MACHINE_LOCK 被占（持锁进程存活）⇒ 本轮不跑')
        return 1
    print('[lock] %s' % payload, flush=True)
    ev = {'at': now(), 'pkg': PKG, 'port': port, 'pidfile': pidfile,
          'lock': {'module': 'app', 'pid': os.getpid(), 'started': now()},
          'reason_for_isolation': (
              '本机 8765 被 reviewer 自己的 v2.4 桥接实例占用 ⇒ 包内启动器'
              '按设计拒绝起第二个实例；本轮只在**运行时**把端口换成 %d，'
              '包内 tools/ext_launcher.py 与 817abcb 仍逐字节一致' % port)}
    try:
        cmd = [os.path.join(PKG, 'python', 'python.exe'), '-B', DRIVER,
               PKG, shot, djson, '600', str(port), pidfile]
        t0 = time.time()
        p = subprocess.run(cmd, cwd=PKG, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=900)
        ev['driver_exit_code'] = p.returncode
        ev['driver_stdout_tail'] = (p.stdout or '')[-1500:]
        ev['driver_stderr_tail'] = (p.stderr or '')[-800:]
        ev['wall_s'] = round(time.time() - t0, 1)
        if os.path.isfile(djson):
            ev['driver'] = json.load(open(djson, encoding='utf-8'))
        ev['verdict'] = 'PASS' if (ev.get('driver', {}).get('verdict') == 'PASS'
                                  and ev['driver_exit_code'] == 0) else 'FAIL'
    finally:
        ev['lock']['ended'] = now()
        release_own_lock(payload)
        ev['lock']['released'] = True
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    d = ev.get('driver', {})
    print('verdict=%s ready=%s engine_line=%s tts_ready=%s combo=%s shot=%s'
          % (ev['verdict'], d.get('ready'), d.get('has_real_engine_line'),
             d.get('has_tts_ready'), d.get('n_combobox'),
             d.get('shot_bytes')))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
