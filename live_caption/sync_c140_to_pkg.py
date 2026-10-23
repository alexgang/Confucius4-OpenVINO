#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c140_to_pkg.py — 把「TTS worker stderr 被读出」的修复同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包，C-133 教训）。

## 要同步的变更（唯一一处）

`app/tts_service.py`：
- `_start_reader()` —— **新增** stderr 独立读者线程；
- 新增 `_read_stderr_loop(proc)`；
- `_read_loop` / `_read_stderr_loop` 改为**显式接收 `proc`**（避免 worker 重启后
  读到新进程的 `self.proc`，把上一个进程的输出当成新的）。

### 为什么必须修（不是可选优化）

`tts_service.py` 的 `Popen(..., stderr=subprocess.PIPE)` **从不读 stderr** ⇒

1. **静默吞掉崩溃原因**：worker 的 `traceback`（`tts_worker.py` L321/L407/L529/L766/L923
   都用 `log(traceback.format_exc())`）走 stdout，但**库级告警 / 未捕获异常**
   走 stderr ⇒ 排查 worker 问题**完全看不到东西**；
2. 🔴🔴 **管道写满 ⇒ worker 假死**：stderr 管道缓冲区写满后，worker 会
   **阻塞在 `write(stderr)`** ⇒ 表现为「worker 永不 emit `ready`」，
   与 §15 的 import 死锁症状**完全一样** ⇒ 极难定位。

**实测证据**（见 `results/app/test_tts_stderr*.txt`）：
- 旧行为（stderr 无人读）⇒ worker 写 >512 KB 后**卡死 60 s 不发 ready**（反证脚本 PASS）；
- 修复后 ⇒ 同一场景 **9/9 PASS**，读满 3000 行 stderr 仍能正常 emit ready。

## 用法
    python live_caption/sync_c140_to_pkg.py            # 执行
    python live_caption/sync_c140_to_pkg.py --check    # 只校验不写
    python live_caption/sync_c140_to_pkg.py --report <报告输出路径>
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

# ── 旧代码块（包内现状，**必须逐字节匹配**）────────────────────────────
OLD = '''    def _start_reader(self):
        """后台线程读 worker 的 stdout（状态行）与 stderr（日志）。"""
        t = threading.Thread(target=self._read_loop, daemon=True)
        t.start()

    def _read_loop(self):
        proc = self.proc
        if proc is None:
            return
'''

# ── 新代码块（来自仓库 `live_caption/tts_service.py`）──────────────────
NEW = '''    def _start_reader(self):
        """后台线程读 worker 的 stdout（状态行）与 stderr（日志）。"""
        proc = self.proc
        if proc is None:
            return
        t = threading.Thread(target=self._read_loop, args=(proc,), daemon=True)
        t.start()
        # 🔴 stderr **必须**有独立读者（2026-10-24 §20 修）。
        #   原因：worker 的 traceback / 库的告警都走 stderr ⇒
        #   ① 不读 ⇒ **静默吞掉崩溃原因**（排查时完全看不到东西）；
        #   ② 不读 ⇒ 管道缓冲区（Windows 约 64 KB）写满后 worker 会
        #      **阻塞在 write(stderr)** ⇒ 表现为「worker 永不 ready」
        #      的假死（和 §15 的 import 死锁症状一样，极难定位）。
        #   ⚠️ 不能合并进 _read_loop —— 那个循环在 stdout 关闭才结束，
        #      而 stdout 的行是稀疏的 ⇒ stderr 会一直堵着没人读。
        t2 = threading.Thread(target=self._read_stderr_loop, args=(proc,), daemon=True)
        t2.start()

    def _read_stderr_loop(self, proc):
        """把 worker 的 stderr 逐行转给 `on_log`（不再静默丢弃）。"""
        if proc is None or proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                line = line.rstrip('\\r\\n')
                if not line:
                    continue
                self.on_log(f'[TTS][stderr] {line}')
        except Exception:
            # stderr 在进程退出时关闭 → readline 抛 ValueError/IOError 属正常
            pass

    def _read_loop(self, proc):
        if proc is None:
            return
'''


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

    # ── 幂等判定 ────────────────────────────────────────────────────────
    if NEW in pkg_text:
        print('[skip] 包内已是新代码（幂等，无需改动）')
        status = 'already_synced'
    elif OLD in pkg_text:
        n = pkg_text.count(OLD)
        assert n == 1, f'旧代码块命中 {n} 次（必须恰好 1 次）⇒ 中止'
        print('[ok] 旧代码块唯一命中（count == 1）')
        if args.check:
            print('[check] --check 模式，不写盘')
            status = 'would_sync'
        else:
            new_text = pkg_text.replace(OLD, NEW)
            assert new_text.count(NEW) == 1, '替换后新代码块命中数 != 1'
            # ── 备份（包外）────────────────────────────────────────────
            os.makedirs(BACKUP_DIR, exist_ok=True)
            bk = os.path.join(
                BACKUP_DIR,
                f'{os.path.basename(os.path.dirname(pkg))}_{REL}.{time.strftime("%Y%m%d_%H%M%S")}.bak')
            shutil.copy2(target, bk)
            print(f'[ok] 已备份到包外: {bk}')
            with open(target, 'w', encoding='utf-8', newline='') as f:
                f.write(new_text)
            print(f'[ok] 已写入定点替换')
            status = 'synced'
    else:
        print('!! 包内既不是旧代码块也不是新代码块 ⇒ 中止（不猜）')
        status = 'unknown'

    sha_pkg_after = sha256(target)
    mtime_after = os.path.getmtime(target)
    sz_after = os.path.getsize(target)
    sz_repo = os.path.getsize(src)
    sha_repo = sha256(src)

    # 归一化换行符后与仓库比对（仓库 LF / 包内 LF，理论上应完全一致）
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
