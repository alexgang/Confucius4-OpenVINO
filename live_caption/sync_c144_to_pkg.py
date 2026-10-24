#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c144_to_pkg.py — 把「§29 TTS 撤账修复」同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- **替换后必须与仓库版逐字一致（归一化换行）才写盘**。

## 要同步的变更（全部在 `app/tts_service.py`）

### ① `_send()` 必须**返回成败**（缺陷③）

旧实现：

```python
def _send(self, obj: dict):
    ...
    if p is None or p.stdin is None:
        return
    try:
        p.stdin.write(...)
        p.stdin.flush()
    except Exception as e:
        self.on_log(f'[TTS] 发送失败：{e}')
```

⇒ 只记日志、**不返回成败** ⇒ 调用方以为命令已下发 ⇒ 登记了 `_inflight`
⇒ 但 worker 永远收不到 ⇒ `pending[jid]` 永久悬挂 ⇒ **`drain()` 必超时**
（GUI 白等 30 s / CLI 白等 120 s）。

修法：返回 `bool`；`p is None` / `stdin is None` / 写异常 ⇒ 返回 False。

### ② `submit()` 送不出去 ⇒ **撤账 + 计丢句**（缺陷③）

`submit()` 登记了 `_inflight` 后调 `_send()` ⇒ 失败时必须
**清 `pending` + 注销 `_inflight` + 计丢句**（诚实记账）。

### ③ `_flush_queue()` 送不出去 ⇒ **撤账 + 计丢句**（缺陷③）

同上。

### ④ `cancel()` 必须**注销 `_inflight`**（缺陷②）

旧实现只 `pending.pop(jid, None)` ⇒ jid 永远留在 `_inflight` 里
⇒ ① 集合无界增长；② worker 崩溃时**再算一次**丢句（`n_dropped` 双记）。

### ⑤ `_update_backlog()` 丢句必须**注销 `_inflight`**（缺陷①）

旧实现只 `pending.pop(jid, None)` ⇒ 同 ④ 的两个后果。
**实测反证**：真实丢 8 句 ⇒ `n_dropped` 被统计成 **9**（双记）。

## 实测证据（见 `results/app/`）

- `test_tts_drop_crash.py` ⇒ 修复前 **3 项反证全部命中**
  （A5 幽灵 jid=[0] / D2 取消后仍在 / E1+E2 `pending` 悬挂 + `drain` 超时 6.0 s）、
  **不变式被破坏**（`n_played + n_dropped = 9 > n_submitted = 8`）；
  修复后 **REAL 全部 PASS + BUG 全部落空 ⇒ PASS**；
- §20/§21/§22 的 6 个既有套件 **全部未回归**
  （`test_tts_error_isolation` / `test_tts_stderr` 9/9 / `test_tts_close_leak` /
  `test_tts_close_orphan` / `test_tts_restart_nop` / `test_tts_restart_regression`）。

## 用法
    python live_caption/sync_c144_to_pkg.py            # 执行
    python live_caption/sync_c144_to_pkg.py --check    # 只校验不写
    python live_caption/sync_c144_to_pkg.py --report <报告输出路径>
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
BACKUP_DIR = r'C:\Users\Trekker-PTL\pkg_backup_app015'

# ── 要同步的文件 ──────────────────────────────────────────────────────
FILES = ['tts_service.py']

# ── 定点替换清单：(标签, 文件, OLD, NEW) ─────────────────────────────
PATCHES = [
    # ── ① `_send()` 返回成败（缺陷③ 的根）────────────────────────────
    (
        'P1-service-send-returns-bool',
        'tts_service.py',
        """    def _send(self, obj: dict):
        with self.lock:
            p = self.proc
        if p is None or p.stdin is None:
            return
        try:
            p.stdin.write(json.dumps(obj, ensure_ascii=False) + '\\n')
            p.stdin.flush()
        except Exception as e:
            self.on_log(f'[TTS] 发送失败：{e}')
""",
        """    def _send(self, obj: dict) -> bool:
        \"\"\"把一条命令写给 worker。

        🔴 2026-10-25 §29 修：**必须返回成败**。
        旧实现只记日志、不返回 ⇒ 调用方无法知道命令有没有真的送出去
        ⇒ 「已下发」的记账（`_inflight`）与事实脱节 ⇒ 句子永久悬挂
        ⇒ `drain()` 必超时。返回 False 的调用方必须**撤账**。
        \"\"\"
        with self.lock:
            p = self.proc
        if p is None or p.stdin is None:
            return False
        try:
            p.stdin.write(json.dumps(obj, ensure_ascii=False) + '\\n')
            p.stdin.flush()
            return True
        except Exception as e:
            self.on_log(f'[TTS] 发送失败：{e}')
            return False
""",
    ),

    # ── ② `submit()` 撤账（缺陷③）───────────────────────────────────
    (
        'P2-service-submit-accounting',
        'tts_service.py',
        """        if ready:
            with self.lock:
                self._inflight.add(jid)
            self._send(cmd)
        elif dead:
""",
        """        if ready:
            with self.lock:
                self._inflight.add(jid)
            # 🔴🔴 2026-10-25 §29 修：**命令送不出去时必须撤账**。
            #   `_send()` 旧实现只记日志、不返回成败 ⇒ 调用方以为已下发
            #   ⇒ `_inflight` 里留下这个 jid ⇒ 但 worker 永远收不到
            #   ⇒ `pending[jid]` 永久悬挂 ⇒ `drain()` 必超时
            #   （GUI 白等 30 s / CLI 白等 120 s）。
            #   现在：`_send()` 返回成败 ⇒ 失败即撤账（清 pending + 注销
            #   `_inflight`）+ **计丢句**（诚实记账，不让这句凭空消失）。
            if not self._send(cmd):
                with self.lock:
                    self.pending.pop(jid, None)
                    self._inflight.discard(jid)
                self.n_dropped += 1
        elif dead:
""",
    ),

    # ── ③ `_flush_queue()` 撤账（缺陷③）──────────────────────────────
    (
        'P3-service-flush-accounting',
        'tts_service.py',
        """        for cmd in q:
            jid = cmd.get('id')
            if jid is not None:
                with self.lock:
                    self._inflight.add(jid)
            self._send(cmd)
        if q:
""",
        """        n_failed = 0
        for cmd in q:
            jid = cmd.get('id')
            if jid is not None:
                with self.lock:
                    self._inflight.add(jid)
            # 🔴 2026-10-25 §29 修：同上 —— 送不出去必须撤账 + 计丢句
            if not self._send(cmd):
                n_failed += 1
                if jid is not None:
                    with self.lock:
                        self.pending.pop(jid, None)
                        self._inflight.discard(jid)
        if n_failed:
            self.n_dropped += n_failed
            self.on_log(f'[TTS] 补发时 {n_failed} 句未能下发（已计丢句）')
        if q:
""",
    ),

    # ── ④ `cancel()` 注销 `_inflight`（缺陷②）────────────────────────
    (
        'P4-service-cancel-discard-inflight',
        'tts_service.py',
        """        self._send({'cmd': 'cancel', 'id': jid})
        with self.lock:
            self.pending.pop(jid, None)
        self.n_dropped += 1
""",
        """        self._send({'cmd': 'cancel', 'id': jid})
        with self.lock:
            self.pending.pop(jid, None)
            # 🔴 2026-10-25 §29 修：**必须同时注销 `_inflight`**。
            #   旧实现只清 `pending` ⇒ 这个 jid 永远留在 `_inflight` 里
            #   ⇒ ① 集合无界增长；② worker 崩溃时 `_on_worker_exit()`
            #   会把它**再算一次**丢句（`n_dropped` 双记）。
            self._inflight.discard(jid)
        self.n_dropped += 1
""",
    ),

    # ── ⑤ `_update_backlog()` 注销 `_inflight`（缺陷①）───────────────
    (
        'P5-service-backlog-discard-inflight',
        'tts_service.py',
        """                for jid in drop_ids:
                    self.pending.pop(jid, None)
            # 通知 worker 别播这些句子（否则丢弃白做了）
""",
        """                for jid in drop_ids:
                    self.pending.pop(jid, None)
                    # 🔴🔴 2026-10-25 §29 修：**必须同时注销 `_inflight`**。
                    #   旧实现只清 `pending` ⇒ 这些 jid 永远留在 `_inflight` 里
                    #   ⇒ ① `_inflight` 集合无界增长（长会议内存单调上升）；
                    #   ② 🔴 worker 崩溃时 `_on_worker_exit()` 会
                    #      `lost = sorted(self._inflight)` ⇒ 把**早已丢弃**的
                    #      句子**再算一次**丢句 ⇒ `n_dropped` 双记、统计虚高
                    #      （实测：真实丢 8 句 ⇒ 统计成 9）。
                    self._inflight.discard(jid)
            # 通知 worker 别播这些句子（否则丢弃白做了）
""",
    ),
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def norm(txt: str) -> str:
    """归一化换行（仓库 ⇄ 包的 .py 常有 CRLF/LF 差异）。"""
    return txt.replace('\r\n', '\n')


def find_pkg_dir() -> str:
    """自动发现最大版本的客户包目录。

    ⚠️ 目录名里可能带后缀（`v1.0.bak_20261020`）⇒ 版本号必须用**正则**
    只取 `v<数字>` 部分，否则 `int()` 抛异常 ⇒ 整个目录列表被跳过。
    """
    import re
    base = r'C:\Users\Trekker-PTL'
    cands = []
    for name in os.listdir(base):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        if not os.path.isdir(os.path.join(base, name, 'app')):
            continue
        m = re.search(r'_v(\d+)(?:\D|$)', name)
        if not m:
            continue
        cands.append((int(m.group(1)), os.path.join(base, name)))
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只校验不写')
    ap.add_argument('--report', default=None, help='报告输出路径')
    args = ap.parse_args()

    pkg = args.pkg or find_pkg_dir()
    pkg_app = os.path.join(pkg, 'app')

    report = {
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': pkg,
        'check_only': bool(args.check),
        'files': {},
        'patches': [],
    }

    # 备份目录（包外）
    if not args.check:
        os.makedirs(BACKUP_DIR, exist_ok=True)

    for fn in FILES:
        src = os.path.join(SRC, fn)
        dst = os.path.join(pkg_app, fn)
        if not os.path.exists(dst):
            print(f'  [SKIP] 包内没有 {fn}')
            continue

        with open(dst, 'r', encoding='utf-8', newline='') as f:
            pkg_txt = f.read()
        with open(src, 'r', encoding='utf-8', newline='') as f:
            src_txt = f.read()

        orig_sha = hashlib.sha256(pkg_txt.encode('utf-8')).hexdigest()
        orig_bytes = len(pkg_txt.encode('utf-8'))
        cur = pkg_txt
        applied, skipped = [], []

        for tag, target, old, new in PATCHES:
            if target != fn:
                continue
            n_old = cur.count(old)
            n_new = cur.count(new)
            if n_new == 1 and n_old == 0:
                skipped.append(tag)          # 已同步（幂等）
                continue
            if n_old != 1:
                raise SystemExit(
                    f'✗ {tag}: OLD 在 {fn} 命中 {n_old} 次（要求恰好 1 次）'
                    f' / NEW 命中 {n_new} 次 ⇒ 拒绝写入')
            cur = cur.replace(old, new, 1)
            applied.append(tag)

        # 归一化换行后必须与仓库版**逐字一致**
        if norm(cur) != norm(src_txt):
            # 允许仓库版有其它未同步差异时给出明确差异量
            import difflib
            d = list(difflib.unified_diff(norm(pkg_txt).splitlines(),
                                          norm(cur).splitlines(), lineterm='', n=0))
            raise SystemExit('✗ 替换后与仓库版不一致，拒绝写盘：\n' +
                             '\n'.join(d[:40]))

        if not args.check:
            bak = os.path.join(BACKUP_DIR, fn + '.bak_' +
                               time.strftime('%Y%m%d_%H%M%S'))
            shutil.copy2(dst, bak)
            with open(dst, 'w', encoding='utf-8', newline='') as f:
                f.write(cur)

        new_bytes = len(cur.encode('utf-8'))
        new_sha = hashlib.sha256(cur.encode('utf-8')).hexdigest()
        report['files'][fn] = {
            'path': dst,
            'orig_sha256': orig_sha,
            'orig_bytes': orig_bytes,
            'new_sha256': new_sha,
            'new_bytes': new_bytes,
            'applied': applied,
            'already_synced': skipped,
            'repo_sha256': hashlib.sha256(src_txt.encode('utf-8')).hexdigest(),
            'repo_bytes': len(src_txt.encode('utf-8')),
        }
        report['patches'].extend(applied)
        print(f'  [OK] {fn}: {applied or "（已是最新）"}')
        if skipped:
            print(f'        幂等跳过：{skipped}')

    # 落盘后复核
    if not args.check:
        for fn in FILES:
            dst = os.path.join(pkg_app, fn)
            src = os.path.join(SRC, fn)
            with open(dst, 'r', encoding='utf-8', newline='') as f:
                a = norm(f.read())
            with open(src, 'r', encoding='utf-8', newline='') as f:
                b = norm(f.read())
            same = (a == b)
            st = os.stat(dst)
            report['files'][fn]['verify_equal_to_repo'] = same
            report['files'][fn]['mtime'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))
            report['files'][fn]['actual_sha256'] = sha256_file(dst)
            report['files'][fn]['actual_bytes'] = st.st_size
            print(f'  [复核] {fn}: 与仓库一致={same} '
                  f'实际 {st.st_size} B sha256={sha256_file(dst)[:16]}…')

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'  报告：{args.report}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
