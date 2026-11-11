#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app461_launch.py — **完全脱离本会话**地启动设备长跑作业（Windows）。

## 为什么不用 `Start-Process` / `nohup …&`
* 🔴 `Start-Process`（PowerShell 5.1）在本机会抛
  `已添加项。字典中的关键字:"Path"所添加的关键字:"PATH"`
  ⇒ 本机环境里**同时存在 `Path` 与 `PATH` 两个键** ⇒ Start-Process 重建环境字典时冲突。
* 🔴 `nohup …&`（Git Bash）**随 shell 退出被杀** ⇒ 上一轮（§176）就是这么丢的：
  第一次后台作业 PID 32816 被杀 ⇒ **留孤儿锁**。

## 本做法
`subprocess.Popen` + `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
⇒ 子进程**不依附**当前会话 ⇒ 会话死亡**不会**带走它；
且**不重建环境字典**（不传 `env=`）⇒ 绕开 `Path`/`PATH` 冲突。

⇒ 启动后**立刻** `session_lease.py addpid app <token> <pid>`
⇒ 下一会话拿到 **BUSY**，不会重复启动同一个作业。

用法：
    python results/app/_app461_launch.py <argv...>
"""
from __future__ import annotations

import os
import subprocess
import sys

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))


def main():
    argv = sys.argv[1:]
    if not argv:
        print('usage: _app461_launch.py <argv...>')
        return 2
    log = os.path.join(REPO, 'results', 'app', '_app461_run.log')
    errlog = os.path.join(REPO, 'results', 'app', '_app461_run.err.log')
    out = open(log, 'wb')
    err = open(errlog, 'wb')
    p = subprocess.Popen(
        argv, cwd=REPO, stdout=out, stderr=err,
        stdin=subprocess.DEVNULL,
        creationflags=(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP),
        close_fds=True)
    print('LAUNCHED PID=%d' % p.pid)
    print('LOG=%s' % log)
    print('ERRLOG=%s' % errlog)
    return 0


if __name__ == '__main__':
    sys.exit(main())
