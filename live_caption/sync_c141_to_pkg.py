#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c141_to_pkg.py — 把「TTS worker 生命周期修复」同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包，C-133 教训）。

## 要同步的变更（唯一一处）

`app/tts_service.py` —— **两个真实 bug**（2026-10-24 §21 实测）：

### ① 孤儿 worker 进程泄漏（`close()`）
旧 `close()` 把 `self.state = 'idle'` 放在 `p.wait()` **之后**，
而 `p.wait()` 一返回 stdout 就关闭 ⇒ `_read_loop` 线程醒来时 `self.state`
仍是 'ready' ⇒ 走 `_on_worker_exit()` ⇒ **自动重启一次**
⇒ `close()` 返回后 `self.proc` 指向**新进程**，它永远收不到 quit
⇒ **孤儿 worker 进程泄漏**（占 GPU/NPU + 音频输出流）。
GUI 有 **4 条**路径会调 `close()`（quit / 停 TTS / 换设备 / 换音色）⇒ 每走一次漏一个。

### ② C-101「崩溃自动重启一次」**从未真正生效**
`_on_worker_exit()` 调 `self.start()`，但 `start()` 开头有
`if self.proc is not None and self.proc.poll() is None: return`
—— Windows 上进程刚死时 `poll()` **仍返回 None**
⇒ **直接 return ⇒ 重启被静默跳过**。
后果更糟：`state` 停在 'ready' ⇒ App 以为 TTS 正常
⇒ 之后每句 `submit()` 都写进**死进程的 stdin** ⇒ **语音输出静默消失**，
不报错、不掉状态（与 §15/§20 的现象高度吻合）。

实测证据（见 `results/app/`）：
- `test_tts_close_orphan.py` ⇒ 修复前 close() 后多起 1 个 worker 且**仍存活**；修复后 0 孤儿；
- `test_tts_restart_nop.py` ⇒ 修复前 worker 实例启动次数 = **1**（重启被跳过）；
  修复后 = **2**，`state` 正确变 'error'；
- `test_tts_restart_regression.py` ⇒ 崩溃重启语义 A/B/C **9/9 PASS**；
- `test_tts_stderr.py` ⇒ §20 的 stderr 修复 **9/9 PASS**（未受影响）。

## 用法
    python live_caption/sync_c141_to_pkg.py            # 执行
    python live_caption/sync_c141_to_pkg.py --check    # 只校验不写
    python live_caption/sync_c141_to_pkg.py --report <报告输出路径>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'live_caption')

# 包外备份目录（绝不能放包内）
BACKUP_DIR = r'C:\Users\Trekker-PTL\pkg_backup_app014'

REL = 'tts_service.py'

# ── 定点替换清单：(标签, OLD, NEW) ────────────────────────────────────
# 每条 OLD 都必须在包内**唯一命中**（assert count == 1）才允许替换。

PATCHES = [
    (
        'P1-init-closing-gate',
        """        self.n_restart = 0             # worker 崩溃重启次数（C-101：最多 1 次）
        self._restarted = False
""",
        """        self.n_restart = 0             # worker 崩溃重启次数（C-101：最多 1 次）
        self._restarted = False
        # 🔴 2026-10-24 §21 修：`_closing` 闸门 —— `close()` 期间**禁止重启 worker**。
        #   起因：旧 `close()` 把 `self.state = 'idle'` 放在 `p.wait()` **之后**，
        #   而 `p.wait()` 一返回，stdout 就已关闭 ⇒ `_read_loop` 线程醒来时
        #   `self.state` 仍是 'ready' ⇒ 走 `_on_worker_exit()` ⇒ **自动重启一次**
        #   ⇒ `close()` 返回后 `self.proc` 指向**新进程**，它永远收不到 quit
        #   ⇒ **孤儿 worker 进程泄漏**（占着 GPU/NPU + 音频输出流）。
        #   实测（`results/app/test_tts_close_orphan.py`）：close() 后多起 1 个
        #   worker 且**仍存活**。GUI 的 quit / 停 TTS / 换设备 / 换音色 4 条路径
        #   都会调 `close()` ⇒ 每次都漏一个孤儿。
        self._closing = False
        self._reader_threads: List = []
""",
    ),
    (
        'P2-start-guard',
        """        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return
            self.state = 'loading'
""",
        """        with self.lock:
            # 🔴 §21：`close()` 期间（`_closing=True`）**不允许起 worker**。
            #   否则 close() 与退出竞态时会把刚起的 worker 立刻丢掉 ⇒ 又一个孤儿。
            if self._closing:
                self.on_log('[TTS] 正在关闭，跳过 worker 启动')
                return
            if self.proc is not None and self.proc.poll() is None:
                return
            # 🔴 §21：旧 proc 已死（poll 有退出码）⇒ 必须先回收它的管道，
            #   否则它的 reader 线程还挂着（daemon 线程会一直占着 fd）。
            if self.proc is not None:
                try:
                    self.proc.kill()
                except Exception:
                    pass
                self.proc = None
            self.state = 'loading'
""",
    ),
    (
        'P3-reader-threads',
        """        t2 = threading.Thread(target=self._read_stderr_loop, args=(proc,), daemon=True)
        t2.start()
""",
        """        t2 = threading.Thread(target=self._read_stderr_loop, args=(proc,), daemon=True)
        t2.start()
        self._reader_threads = [t, t2]
""",
    ),
    (
        'P4-read-loop-wait-rc',
        """        # stdout 关闭 = worker 退出
        rc = proc.poll()
        if self.state != 'idle':
            self._on_worker_exit(rc)

    def _on_worker_exit(self, rc):
        \"\"\"worker 崩溃：C-101 要求自动重启一次；再崩就报错（不影响字幕翻译）。\"\"\"
        if self._restarted:
            self.state = 'error'
            self.err = RuntimeError(f'TTS worker 退出（rc={rc}），已重启过一次仍失败')
            self.on_log(f'[TTS] worker 再次退出（rc={rc}），不再重启；语音输出已停用')
            return
        self._restarted = True
""",
        """        # stdout 关闭 = worker 退出
        # 🔴 §21：`poll()` 在进程刚死时可能仍返回 None（Windows 上退出码还没回填）
        #   ⇒ 旧代码把 `rc=None` 记进日志，且**判断不到「真的死了」**。
        #   这里显式 `wait()` 拿到真实退出码。
        try:
            rc = proc.wait(timeout=2)
        except Exception:
            rc = proc.poll()
        # 🔴 §21：只有「**不是**主动 close 导致的退出」才走重启路径。
        #   主动 close 时 `_closing=True` ⇒ 不重启（否则就是孤儿泄漏）。
        if self.state != 'idle' and not self._closing:
            self._on_worker_exit(rc, proc)

    def _on_worker_exit(self, rc, dead_proc=None):
        \"\"\"worker 崩溃：C-101 要求自动重启一次；再崩就报错（不影响字幕翻译）。\"\"\"
        if self._restarted:
            self.state = 'error'
            self.err = RuntimeError(f'TTS worker 退出（rc={rc}），已重启过一次仍失败')
            self.on_log(f'[TTS] worker 再次退出（rc={rc}），不再重启；语音输出已停用')
            return
        # 🔴🔴 §21：**必须先把死掉的 proc 从 `self.proc` 上摘掉**，否则
        #   `start()` 开头那句
        #       if self.proc is not None and self.proc.poll() is None: return
        #   会看到「旧 proc 还活着」（Windows 上 poll 还没更新）⇒ **直接 return**
        #   ⇒ C-101 要求的「崩溃自动重启一次」**从未真正生效**（实测：
        #   `results/app/test_tts_restart_nop.py` ⇒ worker 实例启动次数 = 1）。
        #   后果更糟：`state` 停在 'ready' ⇒ App 以为 TTS 正常
        #   ⇒ 之后每句 `submit()` 都写进**死进程的 stdin** ⇒ **语音输出静默消失**，
        #   不报错、不掉状态（与 §15/§20 的现象高度吻合）。
        with self.lock:
            if dead_proc is not None and self.proc is dead_proc:
                self.proc = None
        self._restarted = True
""",
    ),
    (
        'P5-close-order',
        """    def close(self):
        with self.lock:
            p = self.proc
            self.proc = None
        if p is not None:
            try:
                p.stdin.write(json.dumps({'cmd': 'quit'}) + '\\n')
                p.stdin.flush()
            except Exception:
                pass
            try:
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self.state = 'idle'
""",
        """    def close(self):
        \"\"\"关闭 TTS worker（**必须真正关掉，不留孤儿进程**）。

        🔴 2026-10-24 §21 修（**孤儿 worker 进程泄漏**）：
        旧实现的顺序错了 —— `self.state = 'idle'` 放在 `p.wait()` **之后**，
        而 `p.wait()` 一返回，stdout 已关闭 ⇒ `_read_loop` 线程醒来时
        `self.state` 仍是 'ready' ⇒ 判定为「worker 崩溃」⇒ `_on_worker_exit()`
        ⇒ **自动重启一次** ⇒ `close()` 返回后 `self.proc` 指向**新进程**，
        它永远收不到 quit ⇒ **孤儿进程**（占 GPU/NPU + 音频输出流）。
        实测：`results/app/test_tts_close_orphan.py` ⇒ close() 后多起 1 个
        worker 且**仍存活**。GUI 有 4 条路径会调 `close()`（quit / 停 TTS /
        换设备 / 换音色）⇒ 每走一次漏一个孤儿。

        新顺序：
          ① `_closing = True`（闸门：禁止 `start()` 重启）；
          ② `state = 'idle'`（让 `_read_loop` 的 `state != 'idle'` 判断为假）；
          ③ 发 quit → 等 → kill；
          ④ **再等 reader 线程收尾**（避免它们还持有旧 proc 的管道）。
        \"\"\"
        with self.lock:
            self._closing = True
            p = self.proc
            self.proc = None
            self.state = 'idle'
        try:
            if p is not None:
                try:
                    p.stdin.write(json.dumps({'cmd': 'quit'}) + '\\n')
                    p.stdin.flush()
                except Exception:
                    pass
                try:
                    p.wait(timeout=3)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
                    try:
                        p.wait(timeout=2)
                    except Exception:
                        pass
            # 等 reader 线程收尾（它们读的是旧 proc 的管道）
            for th in list(self._reader_threads):
                try:
                    th.join(timeout=1.0)
                except Exception:
                    pass
            self._reader_threads = []
        finally:
            with self.lock:
                self._closing = False
""",
    ),
]


def discover_pkg_app(home: str = r'C:\Users\Trekker-PTL') -> str:
    """按 `Confucius4_LiveCaption_vX.Y` 自动发现**版本号最大**的包。

    🔴 必须排除 `.bak` / `backup` / `_pre_` 目录（长期记忆铁律：
       验证脚本不得写死版本号/包路径）。
    """
    best = None
    best_key = None
    for name in os.listdir(home):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        low = name.lower()
        if '.bak' in low or 'backup' in low or '_pre_' in low:
            continue
        app = os.path.join(home, name, 'app')
        if not os.path.isdir(app):
            continue
        ver = name.rsplit('_v', 1)[-1]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best = app
    if best is None:
        raise SystemExit('[客户包] 未找到 Confucius4_LiveCaption_vX.Y/app')
    return best


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包 app 目录（默认自动发现）')
    ap.add_argument('--check', action='store_true', help='只校验不写')
    ap.add_argument('--report', default=None, help='报告输出路径')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg_app()
    target = os.path.join(pkg, REL)
    src = os.path.join(SRC, REL)

    print(f'客户包 app : {pkg}')
    print(f'目标文件   : {target}')
    print(f'仓库源文件 : {src}')
    print()

    if not os.path.isfile(target):
        raise SystemExit(f'!! 包内找不到 {REL}')
    if not os.path.isfile(src):
        raise SystemExit(f'!! 仓库找不到 {REL}')

    with open(target, 'r', encoding='utf-8', newline='') as f:
        pkg_text = f.read()
    with open(src, 'r', encoding='utf-8', newline='') as f:
        repo_text = f.read()

    sha_pkg_before = sha256(target)
    mtime_before = os.path.getmtime(target)

    # ── 逐块判定状态 ────────────────────────────────────────────────────
    # ⚠️ **不能**用「全部 OLD 都不在包里」判幂等：某些 OLD 是 NEW 的**子串**
    #    （例如 P1/P3 是「原样 + 追加」型）⇒ 替换后 OLD 仍然在包里。
    # ⇒ 必须**逐块**判定，且 **NEW 优先**（NEW 在 ⇒ 已应用）。
    states = []   # (tag, 'already' | 'pending')
    for tag, old, new in PATCHES:
        if new in pkg_text:
            states.append((tag, 'already'))
        elif old in pkg_text:
            states.append((tag, 'pending'))
        else:
            raise SystemExit(
                f'!! [{tag}] 旧代码块与新代码块**都不在**包内 ⇒ 中止（不猜）')

    n_already = sum(1 for _, s in states if s == 'already')
    n_pending = sum(1 for _, s in states if s == 'pending')
    for tag, s in states:
        print(f'[state] {tag}: {s}')

    if n_pending == 0:
        print('[skip] 包内已是新代码（幂等，无需改动）')
        status = 'already_synced'
    else:
        # ── 校验每个待替换的 OLD 唯一命中 ───────────────────────────────
        for tag, old, _new in PATCHES:
            if any(t == tag and s == 'pending' for t, s in states):
                n = pkg_text.count(old)
                if n != 1:
                    raise SystemExit(
                        f'!! [{tag}] 旧代码块命中 {n} 次（必须恰好 1 次）⇒ 中止')
        print(f'[ok] {n_pending} 个待替换块唯一命中（count == 1）；'
              f'已应用 {n_already} 个')

        if args.check:
            print('[check] --check 模式，不写盘')
            status = 'would_sync'
        else:
            new_text = pkg_text
            for tag, old, new in PATCHES:
                state = dict(states)[tag]
                if state == 'already':
                    continue          # 已应用 ⇒ 不重复替换
                new_text = new_text.replace(old, new, 1)
                assert new_text.count(new) == 1, f'[{tag}] 替换后新代码块命中数 != 1'
            # ── 备份（包外）────────────────────────────────────────────
            os.makedirs(BACKUP_DIR, exist_ok=True)
            bk = os.path.join(
                BACKUP_DIR,
                f'{os.path.basename(os.path.dirname(pkg))}_{REL}.{time.strftime("%Y%m%d_%H%M%S")}.bak')
            shutil.copy2(target, bk)
            print(f'[ok] 已备份到包外: {bk}')
            with open(target, 'w', encoding='utf-8', newline='') as f:
                f.write(new_text)
            print('[ok] 已写入定点替换')
            status = 'synced'

    sha_pkg_after = sha256(target)
    mtime_after = os.path.getmtime(target)
    sz_after = os.path.getsize(target)
    sz_repo = os.path.getsize(src)
    sha_repo = sha256(src)

    # 归一化换行符后与仓库比对
    with open(target, 'r', encoding='utf-8', newline='') as f:
        t_norm = f.read().replace('\r\n', '\n')
    with open(src, 'r', encoding='utf-8', newline='') as f:
        r_norm = f.read().replace('\r\n', '\n')
    identical = (t_norm == r_norm)

    print()
    print(f'状态         : {status}')
    print(f'包内 SHA256  : {sha_pkg_before[:16]}… -> {sha_pkg_after[:16]}…')
    print(f'包内 mtime   : {mtime_before:.0f} -> {mtime_after:.0f}')
    print(f'包内字节     : {sz_after}')
    print(f'仓库字节     : {sz_repo}   SHA256 {sha_repo[:16]}…')
    print(f'与仓库逐字相同(归一化换行): {identical}')

    report = dict(
        status=status,
        pkg=pkg,
        file=REL,
        n_patches=len(PATCHES),
        sha_pkg_before=sha_pkg_before,
        sha_pkg_after=sha_pkg_after,
        bytes=sz_after,
        mtime=mtime_after,
        repo_sha256=sha_repo,
        identical_to_repo=identical,
    )
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f'报告已写: {args.report}')

    return 0 if status in ('synced', 'already_synced', 'would_sync') else 1


if __name__ == '__main__':
    sys.exit(main())
