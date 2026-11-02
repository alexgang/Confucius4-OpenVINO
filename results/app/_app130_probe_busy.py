#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130：安静窗口探测时**同步记录「在算」进程的命令行**。

🔴 **为什么要连命令行一起记录**（MEMORY 四/十二）：
  只记 PID ⇒ 换一轮就换了 PID ⇒ **判不出是谁**
  ⇒ 必须把**命令行**一起记下来 ⇒ 才能分清「用户会话」/「别的模块」/「自己的」。
"""
import sys
import time

sys.path.insert(0, r'C:\Users\Trekker-PTL\confucius4-openvino')
import machine_lock_app as M


def cmdline(pid):
    import subprocess
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine"
             % pid], capture_output=True, text=True, errors='replace',
            timeout=20)
        return (out.stdout or '').strip()
    except Exception as e:
        return '<fail %s>' % e


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    seen = {}
    prev_cpu = None
    for i in range(rounds):
        busy, idle, unknown, prev_cpu = M.classify_external_python(
            exclude_pids=(), sample_interval=M._CPU_SAMPLE_INTERVAL,
            idle_eps=M._CPU_IDLE_EPS, prev_cpu=prev_cpu)
        print('--- 采样 %d：busy=%r idle=%r unknown=%r'
              % (i + 1, list(busy), list(idle), list(unknown)))
        for pid in list(busy) + list(unknown):
            cl = cmdline(pid)
            key = cl[:200]
            seen.setdefault(pid, set()).add(key)
        time.sleep(15)
    print('\n===== 汇总（PID → 命令行）=====')
    for pid, cls in sorted(seen.items()):
        for c in cls:
            print('  pid=%-7d %s' % (pid, c))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
