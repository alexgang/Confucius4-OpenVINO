r"""machine_lock_app.py —— App 模块的**共享机器锁**（stdlib only，fail-closed）。

## 为什么需要

4 个模块线程（ASR / MT / TTS / App）共用一台机器。**计时/测速作业**开始前必须持
`C:\Users\Trekker-PTL\shared\MACHINE_LOCK`，结束后删除。

App 侧典型需要持锁的作业（本文件加锁的对象）：

- `pack_v13.py` —— 刷新 MANIFEST + 压缩 13.7 GB + 逐文件 SHA256 复核 11.2 GB zip
  ⇒ 长时间占满 CPU 与磁盘 I/O
- `verify_ftp.py` —— 把 11.2 GB zip 从 FTP 全量 RETR 下来做 md5 比对

🔴 **实测事故（2026-10-23 22:25~22:29）**：App 的 `pack_v13.py` 在 22:25 启动，
TTS 模块 22:29 开始测每帧耗时 —— TTS 的 `timing_guard.py` v1 只做「基线进程快照差分」，
`pack_v13.py` 因为**在基线采样之前就已存在**而被当成「自己人」
⇒ 报出 `timing_valid = True`（**假阳性**）⇒ 绝对值被抬高（82.9 ms/帧 vs 干净值 63.98 ms/帧）。

⇒ 证据：`shared/NOTICE_tts_to_app_20261024.md`「通知 2」；
`qwen3tts_eval/status/STATUS_TTS.md` §22 / §24.5。

## 纪律（照抄，不要改）

1. 锁文件 = `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`
2. 内容：模块名 + PID + 开始时间（每行 `key: value`，便于各模块互读）
3. **锁已存在 ⇒ 等待**。可回收的条件只有两个：
   - 能**确定**持锁 PID 已经死了（`ctypes` 的 `OpenProcess` + `GetExitCodeProcess`）
   - 锁的 `started` **早于本机开机时间**（机器重启后的残留锁）
4. 🔴 **探测失败一律视为「存活」**（fail-closed）⇒ 宁可等，不可误删别人的活锁。

🔴🔴 **绝不用 `tasklist /FI` 判存活**：Git Bash 下 MSYS 路径转换会把 `/FI` 当成路径
⇒ 抛异常 ⇒ 旧代码 `except: return False` ⇒ 误判「死了」⇒ **误删他人的活锁**
（2026-10-23 11:23 真实事故：误回收 App 活锁 PID 29864）。
本文件只用 `ctypes` 调 Win32 API，不经过 shell。

## 用法

```python
from machine_lock_app import LockHeld

with LockHeld(module='app-pack', timeout=3600) as lk:
    ...  # 重活
# 退出 with 自动释放（只删内容与自己那份完全一致的文件）
```

命令行脚本里也可以：

```python
lk = LockHeld(module='app-pack')
lk.acquire()
try:
    ...
finally:
    lk.release()
```
"""
from __future__ import annotations

import ctypes
import datetime
import os
import re
import time

# 共享锁路径（4 个模块共用）
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# started 时间戳解析容差（秒）：锁内容里的 started 与文件 mtime 最多允许差这么多
_CLOCK_SKEW = 120

# Windows 常量
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87


# ── 底层判活（ctypes Win32，**不经过 shell**）────────────────────────────
def _pid_alive(pid: int) -> bool:
    """判断 PID 是否还活着。

    用 `OpenProcess` + `GetExitCodeProcess`：
    - 打开成功且退出码 == STILL_ACTIVE(259) ⇒ **活着**
    - 打开成功且退出码 != 259 ⇒ **已死**
    - 打开失败且 `GetLastError() == ERROR_INVALID_PARAMETER(87)`
      ⇒ **该 PID 确定不存在** ⇒ **已死**（这是唯一可以据以回收的失败情形）
    - **其它任何失败 / 异常 ⇒ 视为活着**（fail-closed）

    ⚠️ 不按进程名过滤（PID 可能被复用；进程名判据历史上误回收过活锁）。
    """
    try:
        k32 = ctypes.windll.kernel32
        k32.GetLastError.restype = ctypes.c_ulong
        h = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            err = k32.GetLastError()
            # 87 = ERROR_INVALID_PARAMETER ⇒ 该 PID 确定不存在 ⇒ 已死。
            # ⚠️ 其余错误码（权限不足 / 其它异常）⇒ 不确定 ⇒ 视为存活。
            return err != _ERROR_INVALID_PARAMETER
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return True          # 探测失败 ⇒ 视为存活
            return code.value == _STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    except Exception:
        return True                  # 探测失败 ⇒ 视为存活


def _boot_time() -> float:
    """本机开机时间（本地时区 epoch 秒）。取不到返回 0.0。

    用 `GetTickCount64()`（开机至今毫秒数）⇒ 开机时刻 = now − uptime。
    不用 PowerShell / wmic / net statistics（都不可用或被安全策略拦）。
    """
    try:
        ms = ctypes.windll.kernel32.GetTickCount64()
        return time.time() - ms / 1000.0
    except Exception:
        return 0.0


# ── 锁文件读写 ─────────────────────────────────────────────────────────
def _decode_lock_bytes(path: str):
    """读锁文件原始字节并解码。

    🔴 **多编码回退**：别的模块可能用 Windows 默认 ANSI（GBK）写锁
    （TTS 侧 `machine_lock.py` 明确记录了这一点）⇒ 只用 utf-8 + errors='replace'
    会把模块名等字段变成乱码。⇒ 依次尝试 utf-8 → gbk → cp936 → latin-1。
    """
    try:
        with open(path, 'rb') as f:
            blob = f.read()
    except FileNotFoundError:
        return None
    except Exception:
        # 读不出来 = 不确定 ⇒ 调用方按 fail-closed 处理
        return dict(raw='', parse_error=True)
    for enc in ('utf-8', 'gbk', 'cp936', 'latin-1'):
        try:
            return blob.decode(enc)
        except Exception:
            continue
    return blob.decode('latin-1', errors='replace')


def _read_lock(lock_path: str = LOCK):
    """读锁文件。返回 dict(module/pid/started/started_ts/raw) 或 None（不存在）。

    🔴 **兼容两种格式**（4 个模块可能各写各的）：
    ① key-value（本模块历史上写的）：
         module: app-pack
         pid: 12345
         started: 2026-10-25 03:00:00
    ② **README_LOCK.md 规定的格式**（ASR / MT 等模块在用）：
         asr PID 14644 started 2026-10-24 15:13:06
    """
    raw = _decode_lock_bytes(lock_path)
    if raw is None:
        return None
    if isinstance(raw, dict):          # parse_error
        return raw

    info = dict(raw=raw, module='?', pid=None, started=None, parse_error=False)
    for line in raw.splitlines():
        line = line.strip()
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        k = k.strip().lower()
        v = v.strip()
        if k == 'module':
            info['module'] = v
        elif k == 'pid':
            try:
                info['pid'] = int(v)
            except Exception:
                info['pid'] = None
        elif k == 'started':
            info['started'] = v

    # ② README 格式兜底：key-value 解析不出 pid/module 时启用。
    if info['pid'] is None or info['module'] == '?':
        mod2, pid2 = _parse_module_pid(raw)
        if mod2 is not None:
            info['module'] = mod2
        if pid2 is not None:
            info['pid'] = pid2
    if info['started'] is None:
        m = re.search(r'\bstarted\b[:\s]+(.+)$', raw, re.I | re.M)
        if m:
            info['started'] = m.group(1).strip()
    info['started_ts'] = _parse_started(raw)
    return info


def _parse_module_pid(text: str):
    """解析 README 格式的「模块名 PID <pid> started <时间>」⇒ (module, pid)。

    解析不出来返回 (None, None)。

    ⚠️ **模块名不限于 ASCII**（别的模块可能写中文模块名，且锁可能是 GBK 编码）
    ⇒ 模块名取「PID 关键字之前的那一串非空白字符」。
    """
    for line in (text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(\S+)\s+PID\s+(\d+)\b', line, re.I)
        if m:
            return m.group(1), int(m.group(2))
    # 兜底：关键字扫描（与 TTS 侧 `machine_lock.py` 同策略）
    #   —— 找含 'pid' 的行，取其中第一个纯数字 token。
    for line in (text or '').splitlines():
        line = line.strip()
        if 'pid' not in line.lower():
            continue
        for tok in line.replace(':', ' ').split():
            if tok.isdigit():
                pid = int(tok)
                # 模块名 = 该行 PID 之前的第一段非空白
                head = line[:line.lower().index(tok)].strip()
                mod = head.split()[0] if head.split() else '?'
                return mod, pid
    return None, None


def _parse_started(text: str):
    """从锁内容里解析 started 时间戳（epoch 秒）。解析不了返回 None。

    支持两种格式：
    ① key-value：`started: 2026-10-25 03:00:00`
    ② README 格式：`asr PID 14644 started 2026-10-24 15:13:06`
    """
    fmts = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y/%m/%d %H:%M:%S')

    def _try(raw):
        raw = raw.strip()
        for fmt in fmts:
            try:
                return datetime.datetime.strptime(raw, fmt).timestamp()
            except Exception:
                continue
        return None

    for line in (text or '').splitlines():
        line = line.strip()
        low = line.lower()
        if low.startswith('started'):
            raw = line.split(':', 1)[1].strip() if ':' in line else ''
            ts = _try(raw)
            if ts is not None:
                return ts
        # ② README 格式：`<module> PID <pid> started <time>`
        m = re.search(r'\bstarted\b[:\s]+(.+)$', line, re.I)
        if m:
            ts = _try(m.group(1))
            if ts is not None:
                return ts
    return None


def lock_state(lock_path: str = LOCK):
    """判断锁状态。返回 (state, info)。

      'free'        —— 锁不存在，可以拿
      'held'        —— 持锁 PID 存活（或状态不确定）⇒ **必须等待**
      'stale_pid'   —— 能确定 PID 已死 ⇒ 可回收
      'stale_boot'  —— 锁的 started 早于开机时间 ⇒ 可回收
      'unreadable'  —— 锁存在但读不出 ⇒ **必须等待**（fail-closed）

    ⚠️ 只有 'stale_pid' / 'stale_boot' 允许回收，其余一律等待。
    """
    info = _read_lock(lock_path)
    if info is None:
        return 'free', dict(module=None, pid=None)
    if info.get('parse_error'):
        return 'unreadable', info

    pid = info.get('pid')
    boot = _boot_time()

    # (1) 锁的 started 早于开机时间 ⇒ 上次开机前的残留 ⇒ 可回收（优先于 PID 判断）
    st = info.get('started_ts')
    if st is not None and boot > 0 and st < boot - _CLOCK_SKEW:
        return 'stale_boot', info
    if st is None and boot > 0:
        try:
            mt = os.path.getmtime(lock_path)
            if mt < boot - _CLOCK_SKEW:
                return 'stale_boot', info
        except Exception:
            pass    # mtime 也读不到 ⇒ 不确定 ⇒ fail-closed

    # (2) PID 判断（**不按进程名过滤**）
    if pid is None:
        return 'unreadable', info
    if _pid_alive(pid):
        return 'held', info
    return 'stale_pid', info


# ── 取锁 / 放锁 ────────────────────────────────────────────────────────
def acquire(lock_path: str = LOCK, module: str = 'app', timeout: float = 3600,
            poll: float = 20.0, verbose: bool = True):
    """取得机器锁。返回 (ok, payload)。

    * `os.open(O_CREAT|O_EXCL)` 原子创建 ⇒ 物理上不可能两个模块同时拿到锁。
    * 锁已存在：`held` / `unreadable` ⇒ **等待**（fail-closed）；
      `stale_pid` / `stale_boot` ⇒ 回收后重试。
    """
    t0 = time.time()
    attempt = 0
    while True:
        if time.time() - t0 > timeout:
            if verbose:
                print('[lock] 超时，未能取得机器锁 %s' % lock_path, flush=True)
            return False, None
        attempt += 1
        # 🔴 **写成两种格式**（README_LOCK.md 单行格式 + key-value）
        #    ⇒ 四个模块的读锁实现都能解析（MT 读两种、TTS 关键字扫描、
        #      ASR 人工读 key-value、App 自己也读两种）。
        #    ⚠️ 历史上 App 只写 key-value ⇒ 别的模块按 README 格式的解析器
        #      读不出 PID（MT 通知 2 记录过 14 分钟空等事故）。
        _started = time.strftime('%Y-%m-%d %H:%M:%S')
        payload = ('%s PID %d started %s\n'
                   'module: %s\npid: %d\nstarted: %s\nhost: %s\n'
                   % (module, os.getpid(), _started,
                      module, os.getpid(), _started,
                      os.environ.get('COMPUTERNAME', '?')))
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, payload.encode('utf-8'))
            finally:
                os.close(fd)
            if verbose:
                print('[lock] 已取得机器锁（第 %d 次尝试）\n%s' % (attempt, payload),
                      flush=True)
            return True, payload
        except FileExistsError:
            state, info = lock_state(lock_path)
            mod = info.get('module', '?')
            pid = info.get('pid')
            if state in ('stale_pid', 'stale_boot'):
                reason = ('PID %s 已死' % pid if state == 'stale_pid'
                          else '锁的 started 早于开机时间')
                if verbose:
                    print('[lock] 陈旧锁（module=%s pid=%s：%s）→ 回收'
                          % (mod, pid, reason), flush=True)
                try:
                    os.remove(lock_path)
                except Exception:
                    pass
                time.sleep(1.0)
                continue
            # held / unreadable ⇒ 等待（fail-closed）
            if verbose:
                print('[lock] 等待中…（module=%s pid=%s state=%s，已等 %ds）'
                      % (mod, pid, state, int(time.time() - t0)), flush=True)
            time.sleep(poll)
        except Exception as e:
            if verbose:
                print('[lock] 创建锁异常（%s），按 fail-closed 等待后重试' % e, flush=True)
            time.sleep(poll)


def release(payload, lock_path: str = LOCK, verbose: bool = True) -> bool:
    """释放锁：只删内容与自己那份完全一致的文件（避免误删别人的锁）。"""
    if payload is None:
        return False
    try:
        with open(lock_path, encoding='utf-8', errors='replace') as f:
            cur = f.read()
    except FileNotFoundError:
        return False
    except Exception:
        return False
    if cur != payload:
        if verbose:
            print('[lock] 内容已被他人改动，不删除（避免误删别人的锁）', flush=True)
        return False
    try:
        os.remove(lock_path)
        if verbose:
            print('[lock] 已释放', flush=True)
        return True
    except Exception as e:
        if verbose:
            print('[lock] 释放异常:', e, flush=True)
        return False


class LockHeld:
    """上下文管理器：进入时取锁，退出时释放。"""

    def __init__(self, lock_path: str = LOCK, module: str = 'app',
                 timeout: float = 3600, poll: float = 20.0, verbose: bool = True):
        self.lock_path = lock_path
        self.module = module
        self.timeout = timeout
        self.poll = poll
        self.verbose = verbose
        self.payload = None
        self.ok = False

    def acquire(self) -> bool:
        self.ok, self.payload = acquire(self.lock_path, self.module,
                                        self.timeout, self.poll, self.verbose)
        return self.ok

    def release(self) -> bool:
        return release(self.payload, self.lock_path, self.verbose)

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError('未能取得共享机器锁 %s' % self.lock_path)
        return self

    def __exit__(self, *exc):
        self.release()
        return False


if __name__ == '__main__':
    st, inf = lock_state()
    print('state =', st)
    for k, v in inf.items():
        if k != 'raw':
            print('  %s = %r' % (k, v))
    print('--- raw ---')
    print(inf.get('raw', ''))
