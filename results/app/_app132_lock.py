#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-132：**一次持锁到底**的机器锁（原子创建 ＋ 连续自检 ＋ 可审计事件日志）。

## 为什么要另写一个（🔴 本轮实测抓到的真缺陷）

reviewer APP-132 原文：

> 事实：`shared\\MACHINE_LOCK` 在 12:58 前后读到的是你的 `app 29444 … app bgkeep
> v2.6 chain`，但 reviewer 的排队脚本（只用 CreateNew 原子创建，绝不抢锁）在
> **12:44:18** 成功创建了锁 ⇒ 说明当时锁文件不存在，即你的链在某个时刻删了锁、
> 之后又继续起臂。……请在锁内重跑。……要求：整条链（所有臂、默认值检查、抽听
> 样片）**一次持锁到底**，中途不删；锁内容写明起止。结束后再删（只删自己的）。

**上一轮（`_app116_build_v25.py` 的 `acquire_lock`）的两处真缺陷**：

| # | 缺陷 | 后果 |
|---|---|---|
| **①** | 用 `os.replace(tmp, LOCK)` 写锁 ⇒ **不是原子创建** ⇒ 两个进程可同时"拿到"锁 | reviewer 的 CreateNew 在 12:44:18 成功 ⇒ 我的链**实际上没在持锁** |
| **②** | 看门狗只在 `own is None or own.get('pid') == os.getpid()` 时写回 ⇒ **一旦别人抢了锁就彻底放弃写回** | 锁被抢后，我的链**继续跑但不再持锁** ⇒ 计时全部作废且**无人知晓** |

⇒ 本模块的修法：

1. **原子创建**：`os.open(LOCK, O_CREAT | O_EXCL | O_WRONLY)` ⇒ 只有真正空闲时
   才拿得到 ⇒ **绝不与别人的 CreateNew 竞争**；
2. **看门狗每 10 s 复核**：若锁文件**不再是我的**（被别人抢走 / 被删）⇒
   **立刻把「持锁丢失」记成一条事件**（含时间戳）⇒ 整链的计时结论据此作废；
3. **锁内容写明起止**：`module pid <start> <end> note` ⇒ reviewer 能从锁文件
   直接看出「这一条链的起止时刻」；
4. **只删自己的锁**：释放前再核一次 pid。

## 事件日志

所有「锁状态变化」都追加到 `results/app/app132_lock_events.jsonl`（JSONL，
一行一条）⇒ **可审计**：reviewer 能独立复核「锁在哪一刻被抢过」。

## 用法

```python
from _app132_lock import MachineLock
lk = MachineLock('app bgkeep v2.6 chain')
lk.acquire()                     # 排队等待（不抢别人的）
try:
    ...                            # 整条链都在这里
finally:
    lk.release()                  # 只删自己的
```
"""
from __future__ import annotations

import ctypes
import datetime
import json
import os
import threading
import time

HOME = r'C:\Users\Trekker-PTL'
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
REPO = os.path.join(HOME, 'confucius4-openvino')
EVENTS = os.path.join(REPO, 'results', 'app', 'app132_lock_events.jsonl')


def _now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def pid_alive(pid):
    """🔴 存活判据：**259 = STILL_ACTIVE = 活**；**探测失败 ⇒ 视为存活**。

    （与 `_app116_build_v25.pid_alive` 同一条纪律：Git Bash 下 `tasklist /FI`
    会被当路径，曾误回收他人活锁。）
    """
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return k.GetLastError() != 87
        code = ctypes.c_ulong(0)
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            k.CloseHandle(h)
            return True
        k.CloseHandle(h)
        return code.value == 259
    except Exception:
        return True


def lock_owner():
    """读当前锁的内容。返回 None（不存在）或 dict。"""
    try:
        with open(LOCK, encoding='utf-8') as f:
            raw = f.read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return {'raw': None, 'pid': None, 'unparsed': True}
    parts = raw.split()
    pid = None
    for p in parts:
        if p.isdigit():
            pid = int(p)
            break
    return {'raw': raw, 'pid': pid,
            'module': parts[0] if parts else '?'}


def _event(kind, **kw):
    """追加一条锁事件（JSONL，可审计）。"""
    rec = {'ts': _now(), 'event': kind}
    rec.update(kw)
    line = json.dumps(rec, ensure_ascii=False)
    try:
        os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
        with open(EVENTS, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass
    print('[LOCK] ' + line, flush=True)


class MachineLock(object):
    """一次持锁到底的机器锁（原子创建 ＋ 连续自检）。"""

    def __init__(self, note, module='app', poll_s=5.0):
        self.note = note
        self.module = module
        self.poll_s = poll_s
        self.pid = os.getpid()
        self.content = None
        self.started = None
        self.ended = None
        self._stop = False
        self._thread = None
        #: 持锁期间是否**丢过锁**（True ⇒ 计时结论作废）
        self.lost = False
        self.events = []

    # ── 内部：锁文件内容 ────────────────────────────────────────
    def _compose(self, ended=None):
        return '%s %d %s %s %s' % (
            self.module, self.pid,
            self.started or _now(),
            ended or 'RUNNING',
            self.note)

    def _write_content(self, ended=None):
        """把锁内容写回自己（**不改变持有权语义**，只是刷新起止信息）。"""
        try:
            with open(LOCK, 'r+', encoding='utf-8') as f:
                f.seek(0)
                f.truncate()
                f.write(self._compose(ended))
            return True
        except Exception:
            return False

    # ── 取锁 ────────────────────────────────────────────────────
    def acquire(self, timeout_s=None):
        """排队等待并**原子创建**锁文件。

        🔴 **绝不抢锁**：只用 `O_CREAT|O_EXCL` ⇒ 别人先拿到就必然失败 ⇒
        我方排队等。
        """
        t0 = time.time()
        while True:
            if self._try_create():
                return True
            own = lock_owner()
            if own is None:
                continue                      # 锁刚被别人释放 ⇒ 立刻重试
            pid = own.get('pid')
            if pid == self.pid:
                self.content = own.get('raw')
                self.started = self.started or _now()
                return True
            if pid and not pid_alive(pid):
                # 持有者已死 ⇒ **确认真死**（fail-closed 反向）才回收
                _event('reclaim_dead_owner', owner_pid=pid,
                       owner_raw=own.get('raw'))
                try:
                    os.remove(LOCK)
                except Exception:
                    pass
                continue
            if timeout_s is not None and (time.time() - t0) > timeout_s:
                _event('acquire_timeout', owner_pid=pid,
                       owner_raw=own.get('raw'))
                return False
            time.sleep(self.poll_s)

    def _try_create(self):
        """**原子**创建锁文件（O_EXCL）。成功 ⇒ 持锁。"""
        self.started = _now()
        content = self._compose()
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            self.started = None
            return False
        except Exception as e:
            self.started = None
            _event('create_error', error=repr(e))
            return False
        try:
            os.write(fd, content.encode('utf-8'))
        finally:
            os.close(fd)
        self.content = content
        _event('acquired', pid=self.pid, content=content)
        self._start_watchdog()
        return True

    # ── 看门狗：连续自检 ────────────────────────────────────────
    def _start_watchdog(self):
        def _watch():
            while not self._stop:
                time.sleep(10)
                if self._stop:
                    break
                own = lock_owner()
                if own is None:
                    # 🔴 锁文件**没了**（被人删）⇒ 持锁丢失
                    self.lost = True
                    _event('lock_lost', why='file_missing', pid=self.pid)
                    continue
                if own.get('pid') != self.pid:
                    # 🔴 锁被别人抢走 ⇒ 持锁丢失（**这是 12:44 的那一次**）
                    self.lost = True
                    _event('lock_lost', why='taken_by_other',
                           owner_pid=own.get('pid'), owner_raw=own.get('raw'))
                    continue
                # 锁仍是自己的 ⇒ 刷新内容里的「结束时刻」占位
                self._write_content()

        t = threading.Thread(target=_watch, daemon=True)
        t.start()
        self._thread = t

    def check(self):
        """**当场**复核一次持锁状态。返回 True/False。"""
        own = lock_owner()
        ok = own is not None and own.get('pid') == self.pid
        if not ok:
            self.lost = True
            _event('lock_check_failed', owner_raw=(own or {}).get('raw'))
        return ok

    # ── 放锁 ────────────────────────────────────────────────────
    def release(self):
        """只删**自己的**锁；并把「结束时刻」写进事件日志。"""
        self._stop = True
        self.ended = _now()
        own = lock_owner()
        if own is not None and own.get('pid') != self.pid:
            _event('release_skipped_not_owner', owner_raw=own.get('raw'))
            return False
        try:
            # 先把结束时刻写进锁内容（评审要能看出起止）
            self._write_content(ended=self.ended)
            os.remove(LOCK)
            _event('released', pid=self.pid, started=self.started,
                   ended=self.ended, lost=self.lost)
            return True
        except Exception as e:
            _event('release_error', error=repr(e))
            return False


if __name__ == '__main__':
    import sys
    lk = MachineLock('probe')
    ok = lk.acquire(timeout_s=5)
    print('acquired:', ok, '| lost:', lk.lost)
    if ok:
        print('content:', open(LOCK, encoding='utf-8').read())
        lk.release()
    sys.exit(0 if ok else 1)
