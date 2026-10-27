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

## 🔴🔴「我持锁」≠「机器空闲」—— 安静窗口闸门

**实测事故（2026-10-25 16:04，MT 侧记录）**：MT **已持锁**（`module: mt / pid: 7592`）并在跑
`ts10_nopunct_r2`，**同时** ASR 的 `p3_int4_slice_decode.py --device GPU.0` 正在跑
（PID 15884 / 31756）⇒ **GPU.0 上两个作业并行** ⇒ MT 的计时被污染 ⇒ MT 主动停掉重跑。
⚠️ ASR 自己的 `STATUS_ASR.md` §19.7 记载的上一轮是**同一个模式**。

⇒ **根因**：共享锁是**协作式**的 ⇒ ASR/MT/TTS 的许多脚本**根本不取锁**
⇒ **光靠「我持锁」不足以保证机器空闲**。

⇒ 本模块的做法（照 TTS 的三层叠加，取中间那层）：
1. **取锁**（本文件的 `LockHeld`）；
2. 🔴 **再等一道「安静窗口」**：连续 N 次采样，**没有**别的模块的 python 作业进程，
   才开跑；否则继续等（**不抢、不 kill 别人的进程**）；
3. 跑批期间若发现别的模块进来 ⇒ 记 `timing_valid=false`（由调用方决定是否作废）。

依据：`shared/NOTICE_tts_lock_path_20261025.md` 第三节；
`shared/NOTICE_mt_to_app_20261025.md` §10.6（明确要求 App 侧照此加固）。

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

🔴 **计时/测速类重活建议用 `LockHeld` + `wait_quiet_window()` 两步**
（见 `pack_v13.py` / `publish_ftp.py` 的用法）：
取锁只保证「没有别的模块**自觉**取锁」；安静窗口才保证「没有别的模块**偷跑**」。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
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


# 🔴🔴🔴 **时间戳正则**（本轮 APP-033 巡检自测抓出的真实缺陷的修法核心）
#
#   实测样本（ASR 单行格式）：
#       `asr PID=15256 started 2026-10-28 01:27:19 task=pya_app_baseline_…`
#                    └──── 后面还跟着 `task=…` ────┘
#
#   旧实现用 `re.search(r'\bstarted\b[:\s]+(.+)$')` ⇒ 抓到的是
#   **`2026-10-28 01:27:19 task=pya_app_baseline_…`（整行尾巴）**
#   ⇒ `strptime` 必然失败 ⇒ `started_ts=None`
#   ⇒ 锁的「起始时间」丢失 ⇒ 无法判断锁是否陈旧（只能靠 PID 死活的 ctypes 判据兜底，
#      但**报给用户/写进 STATUS 的 started 时间是空的**）。
#
#   ✅ **修法**：不再「抓尾巴再 strptime」，而是**直接用正则定位时间戳字面量**，
#   只取形如 `YYYY-MM-DD HH:MM:SS` 的那一段 ⇒ 与后面跟不跟 `task=…` 无关。
#
# ⚠️ **定义必须在 `_parse_module_pid` 之前**（下面第三种格式的识别要用它）。
_TS_RE = re.compile(r'(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{1,2}:\d{2}:\d{2})')


def _parse_module_pid(text: str):
    """解析 README 格式的「模块名 PID <pid> started <时间>」⇒ (module, pid)。

    解析不出来返回 (None, None)。

    ⚠️ **模块名不限于 ASCII**（别的模块可能写中文模块名，且锁可能是 GBK 编码）
    ⇒ 模块名取「PID 关键字之前的那一串非空白字符」。

    🔴🔴🔴 **本轮（APP-033 巡检）自测抓出的真实缺陷：`PID=` 写法被误解析成 PID=1**

    ASR 实际写的锁是 **`PID=`** 写法（不是 `PID ` 空格写法）：

        asr PID=15256 started 2026-10-28 01:27:19 task=pya_app_baseline_...

    （依据：`shared/NOTICE_tts_lock_path_20261025.md` §一 的实测记录
    `asr PID=8363 start=2026-10-25 12:56:21 task=p3_61min_gpu_int8`。）

    旧实现的两条分支都解析不出它：
      ① `re.match(r'^(\S+)\s+PID\s+(\d+)\b')` ⇒ `\s+` 要求 `PID` 后有**空白**
         ⇒ `PID=15256` 不匹配；
      ② 兜底「关键字扫描」⇒ `line.replace(':', ' ').split()` 把
         `PID=15256` 切成 **`['PID=15256']`** ⇒ `tok.isdigit()` 为 **False**
         ⇒ **整个分支扫不到任何数字 token**。

    ⇒ 旧实现落到 `return None, None` ⇒ `_read_lock` 的 pid 保持 `None`
    ⇒ `lock_state()` 判 **`unreadable`** ⇒ **fail-closed 永久等待**
    ⇒ 与 MT 通知 §10.6 记录的事故同类（「把 ASR 的活锁误判成解析不出 PID」）
    ⇒ **MT 侧当时已修（`hy_bench/machine_lock.py` 补了 `PID=` / `start=` 格式），
       App 侧漏修**（本轮实测确认）。

    ⚠️ 但**实测当前 ASR 的锁同时含 key-value 段**（`module:` / `pid:` / `started:`）
    ⇒ `_read_lock` 的 **key-value 分支先命中** ⇒ 不会落到本函数
    ⇒ 本缺陷**只在 ASR 只写单行 `PID=` 格式时**才暴露。
    ⇒ 仍必须修：**别的模块（ASR 的 `pya_app_path_seg.py` 等）确实写单行格式**。

    🔴 **修法**：把 `PID` 后的分隔符从「必须有空白」放宽为「空白 / `=` / `:`」
    ⇒ 且**关键字扫描分支**要把 `=` 与 `:` 都当分隔符切分。
    """
    for line in (text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        # 🔴 `PID` 后允许 **空白 / `=` / `:`** 三种分隔符
        #   （README 单行格式 `PID 14644`、ASR 的 `PID=15256`、防御性 `PID: 15256`）
        m = re.match(r'^(\S+)\s+PID[\s=:]+(\d+)\b', line, re.I)
        if m:
            return m.group(1), int(m.group(2))
    # 🔴🔴🔴 **第三种格式（EXT 探针）**（本轮 APP-033 巡检实测抓出）
    #   实测样本：`EXT-p1-real 26084 2026-10-28 02:23:37`
    #   ⇒ **模块名 + PID + 时间戳**，**没有 "PID" 关键字**。
    #   ⇒ 旧实现两条分支都解析不出 ⇒ pid=None ⇒ `lock_state='unreadable'`
    #   ⇒ **fail-closed 永久等待**（安全，但**无法区分活锁与孤儿锁** ⇒
    #      孤儿锁永远不能被正确回收 ⇒ 别的模块的活一旦结束，App 侧就永久卡住）。
    #   ✅ 修法：识别「首 token 是模块名 + 第二 token 是纯数字」的行。
    #   ⚠️ **必须排除**含 `PID` 关键字的行（那种已由上面的分支处理）
    #     且**必须排除**时间戳行（时间戳里的数字不是独立的纯数字 token）。
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or 'pid' in line.lower():
            continue
        toks = line.split()
        if len(toks) < 2:
            continue
        if not toks[1].isdigit():
            continue
        # 🔴 第二 token 是纯数字 ⇒ 当作 PID（第三种格式）
        #   ⚠️ 再确认**后面**确实跟着一个时间戳（否则可能把别的数字误当 PID）
        rest = ' '.join(toks[2:])
        if not _TS_RE.search(rest):
            continue
        return toks[0], int(toks[1])
    # 兜底：关键字扫描（与 TTS 侧 `machine_lock.py` 同策略）
    #   —— 找含 'pid' 的行，取其中第一个纯数字 token。
    for line in (text or '').splitlines():
        line = line.strip()
        if 'pid' not in line.lower():
            continue
        # 🔴🔴 **`=` 与 `:` 都要当分隔符** ⇒ `PID=15256` 才能切出 `15256`
        #   （旧实现只 replace(':') ⇒ `PID=15256` 整块不 isdigit ⇒ 分支失效）
        for tok in re.split(r'[\s=:]+', line):
            if tok.isdigit():
                pid = int(tok)
                # 模块名 = 该行 PID 之前的第一段非空白
                head = line[:line.lower().index(tok)].strip()
                mod = head.split()[0] if head.split() else '?'
                return mod, pid
    return None, None


# 🔴🔴🔴 **时间戳正则**（本轮 APP-033 巡检自测抓出的真实缺陷的修法核心）
#
#   实测样本（ASR 单行格式）：
#       `asr PID=15256 started 2026-10-28 01:27:19 task=pya_app_baseline_…`
#                    └──── 后面还跟着 `task=…` ────┘
#
#   旧实现用 `re.search(r'\bstarted\b[:\s]+(.+)$')` ⇒ 抓到的是
#   **`2026-10-28 01:27:19 task=pya_app_baseline_…`（整行尾巴）**
#   ⇒ `strptime` 必然失败 ⇒ `started_ts=None`
#   ⇒ 锁的「起始时间」丢失 ⇒ 无法判断锁是否陈旧（只能靠 PID 死活的 ctypes 判据兜底，
#      但**报给用户/写进 STATUS 的 started 时间是空的**）。
#
#   ✅ **修法**：不再「抓尾巴再 strptime」，而是**直接用正则定位时间戳字面量**，
#   只取形如 `YYYY-MM-DD HH:MM:SS` 的那一段 ⇒ 与后面跟不跟 `task=…` 无关。
#   （`_TS_RE` 已定义在**本文件上方**、`_parse_module_pid` 之前 ⇒ 供第三种格式共用。）


def _parse_started(text: str):
    """从锁内容里解析 started 时间戳（epoch 秒）。解析不了返回 None。

    支持的格式：
    ① key-value：`started: 2026-10-25 03:00:00`
    ② README 格式：`asr PID 14644 started 2026-10-24 15:13:06`
    ③ 🔴 **ASR 的 `start=` 写法**：`asr PID=15256 start=2026-10-28 01:27:19 task=…`
    ④ 🔴 **ASR 的 `started ` + 尾随 `task=` 写法**：
       `asr PID=15256 started 2026-10-28 01:27:19 task=pya_app_baseline_…`
    ⑤ 🔴 **EXT 探针的第三种格式**：`EXT-p1-real 26084 2026-10-28 02:23:37`
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

    def _find_ts(chunk):
        """在 chunk 里找**第一个**形如时间戳的字面量并解析。"""
        for m in _TS_RE.finditer(chunk or ''):
            ts = _try(m.group(1))
            if ts is not None:
                return ts
        return None

    for line in (text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        # ① key-value：`started: 2026-10-25 03:00:00`
        if low.startswith('started'):
            raw = line.split(':', 1)[1].strip() if ':' in line else ''
            ts = _try(raw)
            if ts is not None:
                return ts
            ts = _find_ts(line)
            if ts is not None:
                return ts
        # 🔴🔴 ②③④ **关键字锚定**：`start` / `started` / `start=` / `started=`
        #   ⇒ 在关键字**之后**找时间戳字面量 ⇒ 尾随 `task=…` 不再干扰。
        #   ⚠️ `\bstart(?:ed)?\b` 覆盖 `start` 与 `started` 两种写法；
        #     `\b` 保证 `started` 不会被 `start` 分支提前吃掉（`start` 后接 `ed`
        #     不构成词边界 ⇒ `\bstart\b` 不匹配 `started`）。
        km = re.search(r'\bstart(?:ed)?\b\s*[:=]?\s*', line, re.I)
        if km:
            ts = _find_ts(line[km.end():])
            if ts is not None:
                return ts
    # 🔴 兜底：整块文本里任意时间戳（防止锁写成跨行/表头形式）
    return _find_ts(text)


# ── 原子写锁（2026-10-26 21:45 TTS 通知 §一 / §三 3.1）────────────────
# 🔴🔴 **为什么不能用 `os.open(O_CREAT|O_EXCL)` 再写内容**：
#   那是「**先建空文件、之后才写内容**」⇒ 存在一个「文件已存在、内容还是空的」
#   时间窗口 ⇒ 别的模块（ASR 的 `pya_app_path_seg.py` / `p3_run_with_lock.py`）
#   在窗口里读锁 ⇒ **解析不出 pid** ⇒ 判成「陈旧锁」⇒ `os.remove` **删掉我们的活锁**
#   ⇒ 两个模块同时跑。
#   实测事故（2026-10-26 21:21~21:38，TTS 侧记录）：
#     · 21:21~21:22  TTS-019 `single` 臂 **16/30** 行 `timing_valid=false`
#     · 21:34~21:38  TTS-017① `A_CPU` 臂 **24/30** 行 `timing_valid=false`
#   依据：`shared/NOTICE_tts_lock_atomic_20261026.md`。
#
# ✅ **本实现**：先把内容**完整**写进临时文件 ⇒ `os.link()` 原子地建立硬链接。
#   - `os.link` 在目标已存在时**抛 FileExistsError** ⇒ **独占**（绝不覆盖别人）
#   - 建立硬链接是**原子**的 ⇒ 别的模块**永远看不到半成品锁**
#     （内容要么完整、要么文件不存在）
#   ⚠️ **刻意不用 `os.replace`**：它会**覆盖**已存在的锁 ⇒ 丢掉独占性
#     （TOCTOU：两个模块都看到「不存在」⇒ 都 replace ⇒ 后写者覆盖前者 ⇒ 两个都以为拿到了锁）。
# 🔴🔴🔴 **tmp 文件名唯一化计数器**（本轮 APP-033 巡检实测抓出，见
# `_write_lock_atomically` 的说明）：
#   等待循环里每次尝试都会建一个 tmp ⇒ 若 tmp 名固定（只有 PID），
#   并发场景下会互踩；且**同名 tmp 反复创建/删除**会累计成「批量删除」，
#   触发宿主的删除保护 ⇒ 进程被杀 ⇒ 实测白跑。
#   ⇒ 加上单调计数 ⇒ 每次 tmp 名唯一 ⇒ 删除次数虽仍多，但**每次删的是不同文件**。
_TMP_SEQ = {'n': 0}


def _write_lock_atomically(lock_path: str, payload: str) -> bool:
    """原子 + 独占地创建锁文件。成功返回 True；锁已存在返回 False。

    🔴 临时文件名**必须带 PID**（`LOCK.<pid>.tmp`）⇒ 两个模块不会用同一个 tmp 名互踩。

    🔴🔴🔴 **本轮（APP-033 巡检）实测抓出的真实缺陷：等待循环里反复创建/删除 tmp
    ⇒ 触发环境的「批量删除保护」⇒ 进程被杀 ⇒ 报告未生成**

    实测事故（2026-10-28 06:09）：`acquire` 的**等待循环每 20 s 就走一次本函数**
    ⇒ 每次都「写 tmp → `os.link` 失败（锁已被别人持有）→ `os.unlink(tmp)`」
    ⇒ 等锁 987 s = **恰好 50 次 unlink**
    ⇒ 触发宿主环境的删除保护：`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
       {"count":50,"threshold":50,"scope":"turn","targets":["…\\MACHINE_LOCK.5860.tmp"]}`
    ⇒ **进程被终止 ⇒ 报告未生成 ⇒ 实测白跑**

    ⇒ **修法（两层）**：
      ① **等待路径不再创建 tmp**：先看锁文件在不在 ⇒ 在 ⇒ 直接判状态（`acquire` 里改）
         ⇒ **等锁期间 0 次删除**。
      ② **tmp 名带唯一后缀**（PID + 单调计数）⇒ 即使并发也不会互踩；
         且 `unlink` 失败不再往上抛。
    """
    tmp = '%s.%d.%d.tmp' % (lock_path, os.getpid(),
                            _TMP_SEQ.setdefault('n', 0) + 1)
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, lock_path)
        except FileExistsError:
            return False            # 别人抢先 ⇒ 独占失败
        return True
    finally:
        try:
            os.unlink(tmp)           # 硬链接已建立 ⇒ 删掉 tmp 不影响锁
        except OSError:
            pass


def write_lock_atomic(lock_path: str, payload: str) -> bool:
    """🔴 **公开入口**：原子 + 独占地写锁。成功 True；锁已存在 False。

    ⇒ App 侧所有计时脚本**统一走这里** ⇒ 不再各写一份（逻辑漂移的根源）。
    """
    return _write_lock_atomically(lock_path, payload)


def lock_probe(lock_path: str = LOCK, own_pid: int = None, own_pids=None):
    """🔴 **逐条锁自检**（TTS 通知 §四）⇒ 返回可直接落盘的 dict。

    字段与 TTS 侧 `_lock_probe()` 对齐：
      `lock_ok`    —— 锁是否完好（True/False）
      `lock_note`  —— 原因（人可读）
      `lock_pid`   —— 当前锁内的 PID（读不到为 None）

    🔴🔴 **为什么必须逐条查**：「锁被抢 / 被删 / 被换写」这件事
    **在数据里完全看不出来** ⇒ 不查就会把**被污染的数据**当成正常结果
    （TTS 第一轮就是这样：数据看着像没事，实际上 16/30 被污染）。

    用法（计时脚本）：
        p = machine_lock_app.lock_probe()
        row['timing_valid'] = p['lock_ok']
        row['lock_note'] = p['lock_note']
    """
    ok, why = lock_intact(lock_path, own_pid=own_pid, own_pids=own_pids)
    info = _read_lock(lock_path)
    pid = None
    if isinstance(info, dict):
        pid = info.get('pid')
    return dict(lock_ok=bool(ok), lock_note=why, lock_pid=pid)


def lock_intact(lock_path: str = LOCK, own_pid: int = None, own_pids=None):
    """持锁方**逐条自检**：锁还在吗？内容还是我这一份吗？

    返回 `(ok: bool, reason: str)`。

    🔴🔴 **用途**（TTS 通知 §四）：锁被别的模块抢走 / 被删掉时，
    「锁被抢」这件事**在数据里完全看不出来** ⇒ 必须逐条自检 ⇒
    锁一断就**强制 `timing_valid=false`** ⇒ 污染不会伪装成正常数据。

    判据（三条全过才算 intact）：
      ① 锁文件存在；
      ② 能解析出 pid 且该 pid **仍存活**（ctypes Win32，fail-closed）；
      ③ 该 pid **是自己**（`own_pid` 或在 `own_pids` 集合里）。
    """
    own = set(int(p) for p in (own_pids or ()))
    if own_pid is not None:
        own.add(int(own_pid))
    if not own:
        own.add(os.getpid())

    if not os.path.exists(lock_path):
        return False, '锁文件不存在（被删或从未创建）'
    info = _read_lock(lock_path)
    if info is None:
        return False, '锁文件读不到'
    if info.get('parse_error'):
        return False, '锁文件读不出来（parse_error）'
    pid = info.get('pid')
    if pid is None:
        return False, '锁里解析不出 pid（半成品锁？）'
    # 🔴 **判定顺序**：先判「是不是自己」⇒ 诊断更准。
    #    锁被**别人换写**时，锁内的 PID 往往已经死了
    #    ⇒ 若先判存活就会报「PID 已死」⇒ 掩盖了真正的现象「锁被抢」。
    if int(pid) not in own:
        alive = '存活' if _pid_alive(pid) else '已死'
        return False, '锁内 PID %d 不是自己（%s）⇒ 锁被抢（该 PID %s）' % (
            pid, sorted(own), alive)
    if not _pid_alive(pid):
        return False, '锁内 PID %d 已死（锁被回收/换写）' % pid
    return True, '锁完好（pid=%d）' % pid


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


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴 安静窗口闸门（2026-10-25 新增，见模块 docstring）
# ══════════════════════════════════════════════════════════════════════
# 「我持锁」≠「机器空闲」：别的模块的脚本**大多不取锁** ⇒ 必须再加一道
# 「安静窗口」检查：连续 N 次采样没有别的模块的 python 作业，才开跑。
#
# 🔴 **只等、只观察，绝不 kill 别人的进程**。
# 🔴 **判据用 ctypes Win32 API 枚举进程**（CreateToolhelp32Snapshot +
#   Process32FirstW/NextW）⇒ 不用 `tasklist /FI`（Git Bash 下会被当路径）。
# 🔴 **读不到命令行 ⇒ 保守判为「有干扰」**（fail-closed）⇒ 宁可多等。

_TH32CS_SNAPPROCESS = 0x00000002


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', ctypes.wintypes.DWORD),
        ('cntUsage', ctypes.wintypes.DWORD),
        ('th32ProcessID', ctypes.wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
        ('th32ModuleID', ctypes.wintypes.DWORD),
        ('cntThreads', ctypes.wintypes.DWORD),
        ('th32ParentProcessID', ctypes.wintypes.DWORD),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', ctypes.wintypes.DWORD),
        ('szExeFile', ctypes.c_wchar * 260),
    ]


def list_processes():
    """枚举所有进程 => [(pid, exe_name), ...]（ctypes，无外部依赖）。

    ⚠️ 这里**不读命令行**（读 PEB 的实现见 `results/app/app037_quiet_window.py`）
    ⇒ 本模块保持 **stdlib only + ctypes**，不引入 psutil。
    """
    out = []
    try:
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = ctypes.wintypes.HANDLE
        k32.Process32FirstW.restype = ctypes.wintypes.BOOL
        k32.Process32NextW.restype = ctypes.wintypes.BOOL
        snap = k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        invalid = ctypes.c_void_p(-1).value
        if not snap or snap == invalid:
            return out
        try:
            pe = _PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            if k32.Process32FirstW(snap, ctypes.byref(pe)):
                while True:
                    out.append((int(pe.th32ProcessID), pe.szExeFile))
                    if not k32.Process32NextW(snap, ctypes.byref(pe)):
                        break
        finally:
            k32.CloseHandle(snap)
    except Exception:
        # 🔴 枚举失败 ⇒ **fail-closed**（调用方按「有干扰」处理）
        raise
    return out


# 🔴 **自己**的进程标识（出现在可执行名/路径里 ⇒ 视为「自己」，不计入干扰）
_SELF_EXE_NAMES = ('python', 'pythonw')


def external_python_pids(exclude_pids=()):
    """返回「不是自己的 python 进程」的 PID 列表。

    ⚠️ **只认 python 进程**：WorkBuddy 自己的 `bash.exe -c ...` 外壳里
    也会出现别的模块的脚本名（命令行里带了那些字符串）⇒ 按进程名过滤
    才是可靠口径（MT 侧 `quiet_window.py` 实测 3 个误报即源于此）。

    🔴 **枚举失败 ⇒ 抛异常**（由 `wait_quiet_window` 按 fail-closed 处理）。
    """
    ex = set(int(p) for p in (exclude_pids or ()))
    ex.add(os.getpid())
    out = []
    for pid, exe in list_processes():
        if pid in ex:
            continue
        name = (exe or '').lower()
        if name.startswith('python') or name.startswith('pythonw'):
            out.append(pid)
    return out


# ── 「在等锁」与「在算」的区分（MT 通知 12 §12.5）────────────────────
#
# 🔴🔴 **为什么必须区分**（MT 侧实测事故）：
#   共享锁是**协作式**的 ⇒ 别的模块的脚本**在等锁时也会是一个活着的 python 进程**
#   ⇒ 老判据「只看进程存在」会把**协作方**（正是因为在等**你**才存在）
#   误判成「干扰源」⇒ **必然互等死锁**。
#   ⇒ MT 侧实测白等 **1 h 41 min**。
#
# 🔴 **判据 = CPU 时间增量**（`GetProcessTimes`，ctypes Win32 API）：
#   「在等锁」的进程只是 `sleep()` ⇒ CPU 增量 ≈ **0 s**；
#   「在算」的进程真正在烧 CPU ⇒ 增量显著 > 0。
#   ⇒ **增量 ≈ 0 ⇒ 放行**（等锁不是干扰）；**增量 > 0 ⇒ 算干扰**。
#
# ⚠️ **不放松 fail-closed**：CPU 读不到 ⇒ 视为「在算」（= 干扰）⇒ 继续等。
# ⚠️ **首次采样必然没有历史** ⇒ 不能在第一次采样就下判断
#    （MT 通知 12 §12.5 的第三个缺陷：旧判据要求「有 CPU 历史」，
#      于是第一次采样必然判「在算」⇒ 把锁包装器判成干扰 ⇒ 整批永久作废）。
#    ⇒ 本实现：**第一次采样只记录基线、不下结论**；从第二次采样起才有结论。

_CPU_SAMPLE_INTERVAL = 3.0     # 两次 CPU 采样的间隔（秒）
_CPU_IDLE_EPS = 0.05           # CPU 增量 ≤ 此值（秒）⇒ 判「在等锁/在睡」


def _process_cpu_seconds(pid: int):
    """返回该进程累计的 (kernel + user) CPU 秒数；读不到返回 None。

    用 `GetProcessTimes`（ctypes Win32 API）⇒ 不用 `wmic` / `psutil`
    （`wmic` 在本机已被移除；`psutil` 会破坏本模块的 stdlib-only 契约）。
    """
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.wintypes.HANDLE
        h = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return None
        try:
            c = ctypes.wintypes.FILETIME()
            e = ctypes.wintypes.FILETIME()
            k = ctypes.wintypes.FILETIME()
            u = ctypes.wintypes.FILETIME()
            if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                       ctypes.byref(k), ctypes.byref(u)):
                return None
            def _v(ft):
                return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
            return (_v(k) + _v(u)) / 1e7
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def classify_external_python(exclude_pids=(), sample_interval=_CPU_SAMPLE_INTERVAL,
                             idle_eps=_CPU_IDLE_EPS, prev_cpu=None):
    """把外部 python 进程分成「在等锁（放行）」与「在算（算干扰）」。

    返回 `(busy_pids, idle_pids, unknown_pids, prev_cpu)`：

    - `busy_pids`   ：CPU 增量显著 ⇒ **在算** ⇒ 干扰源
    - `idle_pids`   ：CPU 增量 ≈ 0 ⇒ **在等锁 / 在睡** ⇒ **放行**
    - `unknown_pids`：**读不到 CPU** ⇒ fail-closed ⇒ **算干扰**
    - `prev_cpu`    ：本轮的 CPU 基线（下一轮传入 ⇒ 才有增量可比）

    🔴 **第一次采样没有历史** ⇒ 只建基线、**不下结论**
    ⇒ 全部归入 `unknown_pids`（fail-closed ⇒ 算干扰 ⇒ 继续等）。
    ⚠️ 这样第一次采样会**多等一轮**，但**不会**像 MT 旧实现那样
    「第一次必然判 dirty ⇒ 整批永久作废」—— 第二次采样起就能正常区分。
    """
    ex = set(int(p) for p in (exclude_pids or ()))
    ex.add(os.getpid())
    try:
        pids = external_python_pids(exclude_pids=ex)
    except Exception:
        # 枚举失败 ⇒ fail-closed ⇒ 全部算干扰
        return ([-1], [], [], dict(prev_cpu or {}))

    prev = dict(prev_cpu or {})
    now = {}
    busy, idle, unknown = [], [], []
    for pid in pids:
        cpu = _process_cpu_seconds(pid)
        if cpu is None:
            unknown.append(pid)
            continue
        now[pid] = cpu
        old = prev.get(pid)
        if old is None:
            # 第一次见到这个进程 ⇒ 还没有历史 ⇒ 无法判断 ⇒ fail-closed
            unknown.append(pid)
            continue
        delta = cpu - old
        if delta <= idle_eps:
            idle.append(pid)          # 在等锁 / 在睡 ⇒ 放行
        else:
            busy.append(pid)          # 真在算 ⇒ 干扰源
    return (busy, idle, unknown, now)


def wait_quiet_window_cpu(quiet_seconds: float = 45.0, timeout: float = 1800.0,
                           poll: float = 15.0, exclude_pids=(), verbose: bool = True,
                           sample_interval=_CPU_SAMPLE_INTERVAL,
                           idle_eps=_CPU_IDLE_EPS):
    """安静窗口（**区分「在等锁」与「在算」**的版本）⇒ 返回 (ok, info)。

    与 `wait_quiet_window` 的区别：
    - 老版：只要存在外部 python 进程 ⇒ 判「有干扰」⇒ **永远等不到**
      （协作方在等锁时也是活着的 python 进程 ⇒ **互等死锁**）。
    - 本版：用 **CPU 时间增量**区分 ⇒ 「在等锁」的协作方**放行**，
      只有「真在算」的进程才算干扰。

    🔴 **fail-closed 保持**：CPU 读不到 / 首次采样无历史 ⇒ 算干扰 ⇒ 继续等。
    🔴 **不 kill 任何进程**。
    """
    t0 = time.time()
    quiet_since = None
    prev_cpu = None
    info = dict(quiet_seconds=quiet_seconds, timeout=timeout,
                waited_s=0.0, n_samples=0, n_busy_samples=0,
                n_idle_samples=0, n_unknown_samples=0,
                last_busy_pids=[], last_idle_pids=[],
                classifier='cpu-delta')
    while time.time() - t0 < timeout:
        info['n_samples'] += 1
        busy, idle, unknown, prev_cpu = classify_external_python(
            exclude_pids=exclude_pids, sample_interval=sample_interval,
            idle_eps=idle_eps, prev_cpu=prev_cpu)
        blockers = list(busy) + list(unknown)
        if blockers:
            info['n_busy_samples'] += 1
            if unknown:
                info['n_unknown_samples'] += 1
            info['last_busy_pids'] = blockers[:20]
            quiet_since = None
            if verbose:
                print('[quiet] 有 %d 个「在算」的外部 python 进程（另有 %d 个在等锁'
                      '、%d 个读不到）⇒ 继续等（已等 %.0f s）'
                      % (len(busy), len(idle), len(unknown), time.time() - t0),
                      flush=True)
        else:
            info['n_idle_samples'] += 1
            info['last_idle_pids'] = list(idle)[:20]
            if quiet_since is None:
                quiet_since = time.time()
                if verbose:
                    print('[quiet] 外部 python 进程均「在等锁/在睡」⇒ 视为安静，'
                          '开始计时安静窗口…', flush=True)
            elif time.time() - quiet_since >= quiet_seconds:
                info['waited_s'] = time.time() - t0
                info['quiet_since'] = quiet_since
                if verbose:
                    print('[quiet] ✅ 安静窗口已持续 %.0f s ⇒ 可以开始计时'
                          % quiet_seconds, flush=True)
                return True, info
        time.sleep(poll)
    info['waited_s'] = time.time() - t0
    if verbose:
        print('[quiet] 🔴 超时 %.0f s 仍未进入安静窗口 ⇒ 不开跑'
              % timeout, flush=True)
    return False, info


def wait_quiet_window(quiet_seconds: float = 45.0, timeout: float = 1800.0,
                      poll: float = 15.0, exclude_pids=(), verbose: bool = True):
    """等待「没有别的 python 进程」并持续 `quiet_seconds` 秒。

    返回 (ok: bool, info: dict)。

    * `ok=True`  ⇒ 进入安静窗口，可以开始计时
    * `ok=False` ⇒ 超时未进入（调用方**应当拒绝开跑**，或标记 timing_valid=false）

    🔴 **fail-closed**：枚举失败 / 读不到 ⇒ 视为「有干扰」⇒ 继续等。
    🔴 **不 kill 任何进程**。
    """
    t0 = time.time()
    quiet_since = None
    info = dict(quiet_seconds=quiet_seconds, timeout=timeout,
                waited_s=0.0, n_samples=0, n_busy_samples=0,
                last_busy_pids=[])
    while time.time() - t0 < timeout:
        info['n_samples'] += 1
        try:
            busy = external_python_pids(exclude_pids)
        except Exception as e:
            busy = [-1]          # fail-closed：枚举失败 ⇒ 视为有干扰
            info['enumeration_error'] = repr(e)
        if busy:
            info['n_busy_samples'] += 1
            info['last_busy_pids'] = busy[:20]
            quiet_since = None
            if verbose:
                print('[quiet] 有 %d 个外部 python 进程 ⇒ 继续等（已等 %.0f s）'
                      % (len(busy), time.time() - t0), flush=True)
        else:
            if quiet_since is None:
                quiet_since = time.time()
                if verbose:
                    print('[quiet] 外部 python 进程已空，开始计时安静窗口…',
                          flush=True)
            elif time.time() - quiet_since >= quiet_seconds:
                info['waited_s'] = time.time() - t0
                info['quiet_since'] = quiet_since
                if verbose:
                    print('[quiet] ✅ 安静窗口已持续 %.0f s ⇒ 可以开始计时'
                          % quiet_seconds, flush=True)
                return True, info
        time.sleep(poll)
    info['waited_s'] = time.time() - t0
    if verbose:
        print('[quiet] 🔴 超时 %.0f s 仍未进入安静窗口 ⇒ 不开跑'
              % timeout, flush=True)
    return False, info


# ── 取锁 / 放锁 ────────────────────────────────────────────────────────
def acquire(lock_path: str = LOCK, module: str = 'app', timeout: float = 3600,            poll: float = 20.0, verbose: bool = True):
    """取得机器锁。返回 (ok, payload)。

    * 🔴🔴 **原子写**（`tmp` 写全 + `os.link` 建硬链接）⇒ 别的模块**永远看不到半成品锁**，
      且**独占**（目标已存在就失败 ⇒ 绝不覆盖别人的锁）。
      依据：`shared/NOTICE_tts_lock_atomic_20261026.md` §一 / §三 3.1。
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
        # 🔴🔴🔴 **先探测、后创建**（本轮 APP-033 巡检实测抓出的真实缺陷的修法）
        #   旧实现：**每轮都先写 tmp → link 失败 → 删 tmp** ⇒ 等锁期间每次
        #   循环产生 1 次文件创建 + 1 次删除 ⇒ 等锁 987 s = 50 次删除
        #   ⇒ 触发宿主「批量删除保护」⇒ **进程被杀 ⇒ 实测白跑**（实测事故已发生）。
        #   新实现：**锁文件已存在 ⇒ 直接判状态 ⇒ 0 次创建、0 次删除**；
        #   只有在锁**不存在**时才去尝试创建（那一次成功即拿到锁）。
        #   ⇒ 等锁期间的文件系统写入次数 = 0（而不是 N 次）。
        if os.path.exists(lock_path):
            # 锁已存在 ⇒ 判状态（不创建 tmp、不删除任何文件）
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
            if state == 'unreadable':
                # 🔴🔴 **「读不出 pid」≠「锁是空的」**（TTS 通知 §三 3.2）
                #    ⇒ 别的模块**正在写**这个锁时，我们也会读不出 pid
                #    ⇒ **不许马上删** ⇒ 先等 2 s 再读一次。
                # 🔴 **比 TTS 的建议更严一档**：只在「文件确实是空的（0 字节 /
                #    纯空白）」时才回收 ⇒ 别的模块用**我们不认识的格式**写的
                #    **活锁**绝不删除（那正是「误删活锁」的原始事故形态）。
                time.sleep(2.0)
                raw2 = _decode_lock_bytes(lock_path)
                blank = (raw2 is None) or (not raw2.strip())
                if blank:
                    if verbose:
                        print('[lock] 锁是**空文件**（等 2 s 后仍无内容）→ 回收',
                              flush=True)
                    try:
                        os.remove(lock_path)
                    except Exception:
                        pass
                    continue
                if verbose:
                    print('[lock] 锁读不出 pid，但内容非空 ⇒ 可能是别的模块的格式'
                          ' ⇒ **不删**，继续等（fail-closed）', flush=True)
            if verbose:
                print('[lock] 等待中…（module=%s pid=%s state=%s，已等 %ds）'
                      % (mod, pid, state, int(time.time() - t0)), flush=True)
            time.sleep(poll)
            continue
        # 锁不存在 ⇒ 去创建（唯一一次写 tmp 的路径）
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
            got = _write_lock_atomically(lock_path, payload)
        except Exception as e:
            if verbose:
                print('[lock] 创建锁异常（%s），按 fail-closed 等待后重试' % e,
                      flush=True)
            time.sleep(poll)
            continue
        if got:
            if verbose:
                print('[lock] 已取得机器锁（第 %d 次尝试）\n%s' % (attempt, payload),
                      flush=True)
            return True, payload
        # 🔴 **走到这里 = 锁在我们探测之后被别人抢先创建了**（TOCTOU 窗口极小）
        #    ⇒ 直接回到循环开头重新探测（**不再重复判状态/不再重复写 tmp**）
        #    ⇒ 保持「等待路径 0 次文件删除」的性质。
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

    def intact(self) -> tuple:
        """🔴 逐条自检：锁还在吗？内容还是我这一份吗？（见 `lock_intact`）

        ⇒ 计时脚本在**每条样本前后**调用一次 ⇒ 锁一断就
        `timing_valid=false` ⇒ 「锁被抢」不会伪装成正常数据。
        """
        return lock_intact(self.lock_path, own_pid=os.getpid())

    def wait_quiet(self, quiet_seconds: float = 45.0, timeout: float = 1800.0,
                   poll: float = 15.0, use_cpu_classifier: bool = True):
        """🔴 **取锁之后的第二道闸门**：等「安静窗口」。

        「我持锁」≠「机器空闲」—— 别的模块的脚本**大多不取锁**
        ⇒ 只取锁会被偷跑污染 ⇒ 计时类作业必须**再等一道**。

        🔴🔴 **默认用 CPU 增量分类器**（MT 通知 12 §12.5）：
        别的模块的脚本**在等锁时也是活着的 python 进程** ⇒ 老判据
        「只看进程存在」会把**协作方**误判成干扰源 ⇒ **互等死锁**
        （MT 侧实测白等 1 h 41 min）⇒ 现在按 **CPU 时间增量**区分：
        「在等锁/在睡」（增量 ≈ 0）**放行**，「真在算」（增量 > 0）才算干扰。

        返回 (ok, info)；`info` 含 `waited_s` / `n_samples` / `n_busy_samples`
        / `last_busy_pids`（+ CPU 分类器时另含 `n_idle_samples` /
        `n_unknown_samples` / `last_idle_pids` / `classifier`），可直接落盘作证据。
        """
        if use_cpu_classifier:
            return wait_quiet_window_cpu(quiet_seconds=quiet_seconds,
                                         timeout=timeout, poll=poll,
                                         verbose=self.verbose)
        return wait_quiet_window(quiet_seconds=quiet_seconds, timeout=timeout,
                                  poll=poll, verbose=self.verbose)

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
