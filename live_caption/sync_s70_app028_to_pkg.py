#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s70_app028_to_pkg.py —— 把 APP-028（无界队列 / 取消丢句 / 语音滞后）
同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换块**从 git 自动派生**（不手抄任何代码）⇒ 抄错的风险归零；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- 写盘时**保留包内原有的换行风格**（本包是 CRLF ⇒ 写回 CRLF）。

## 本轮要同步的变更（APP-028）

`app/tts_worker.py`：
① `RingBuffer`（有界 3 s + 写满反压阻塞）⇒ **`AudioQueue`**（无界、保序）；
② **合成线程不再等播放** ⇒ 「等播完 + 发 `played`」挪到**独立的看门狗线程**
   （`_played_loop` / `_finish_played`）；
③ `synth_state` 上报 **`lag_s`**（语音滞后）且**不再**把队列水位截断到 3 s；
④ `cancel` 语义改为**整句摘除**（`drop_jid`）⇒ 删除「中止已写入句子」的路径；
⑤ 新增 **`clear_queue`** 指令（用户手动停止 / 切换会话时清空队列）；
⑥ stdout 写锁（`_OUT_WLOCK`）—— 多线程写会**交错** ⇒ 主进程 JSON 解析失败；
⑦ jsonl 新增 `queue_lag_s` / `queue_peak_s` / `queue_peak_mb`（验收要报队列峰值）。

`app/tts_service.py`：
⑧ `_update_backlog()` 的**丢句分支整段删除**（只统计积压，不丢句）；
⑨ 新增 `lag_s` 字段 + `stats()` 暴露 + 滞后告警（边沿触发 + 冷却）；
⑩ 新增 `clear_audio_queue()`（用户手动停止 / 切换会话）。

`app/live_caption_app.py`：
⑪ 底栏实时显示「**语音滞后 X 秒**」（`_tts_meter()` 接入 `_poll()`）；
⑫ 用户手动停止时清空音频队列（`_clear_tts_queue()`）。

`app/offline_reader.py`：
⑬ 节流口径说明更新（不再「防丢句」，改「防内存涨 + 保首段快出」）。

## 基线 commit

🔴 **不能用 `HEAD`** —— 本轮提交后 HEAD 就是新版本 ⇒ 无法派生替换块。
⇒ 用**同步前的固定 commit** `5e2aef7`（= §69 的客户包同步提交，
   `tts_worker.py` / `tts_service.py` / `live_caption_app.py` /
   `offline_reader.py` / `device_config.py` 在包内与之**逐字一致**
   —— 已用 SHA256 逐文件核对过）。

## 用法

    python live_caption/sync_s70_app028_to_pkg.py --check   # 只查差异
    python live_caption/sync_s70_app028_to_pkg.py            # 同步
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s70')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
TARGETS = [
    ('live_caption/tts_worker.py', 'app/tts_worker.py'),
    ('live_caption/tts_service.py', 'app/tts_service.py'),
    ('live_caption/live_caption_app.py', 'app/live_caption_app.py'),
    ('live_caption/offline_reader.py', 'app/offline_reader.py'),
]

# 🔴 **同步前的固定 commit**（不是 HEAD！见模块 docstring）
BASE_COMMIT = '5e2aef7'


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(b: bytes) -> bytes:
    """归一化换行（CRLF/CR → LF）⇒ 比对与派生都用它。"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _detect_eol(b: bytes) -> bytes:
    """探测原文件的换行风格（\r\n 还是 \n）。"""
    return b'\r\n' if b'\r\n' in b else b'\n'


def _git_show(commit: str, rel: str) -> bytes:
    r = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git show %s:%s 失败: %s'
                           % (commit, rel, r.stderr.decode('utf-8', 'replace')))
    return r.stdout


def _pkg_dirs():
    """自动发现最大版本客户包目录（🔴 目录名可能有 `_bak_日期` 后缀
    ⇒ 必须用正则取版本号，不能用 `rsplit('_v',1)[1]`）。"""
    out = []
    for name in os.listdir(HOME):
        p = os.path.join(HOME, name)
        if not os.path.isdir(p):
            continue
        m = re.match(r'^Confucius4_LiveCaption_v(\d+)(?:\.\d+)*$', name)
        if m:
            out.append((int(m.group(1)), name, p))
    out.sort()
    return out


def _derive_blocks(old: bytes, new: bytes):
    """用 difflib 从「同步前 → 同步后」派生替换块（含上下文 ⇒ 唯一命中）。

    🔴🔴 **必须用 `get_grouped_opcodes(n=3)`**（带上下文），
    不能用裸 `get_opcodes()`：
      裸 opcodes 里「纯新增块」的 old 部分是**空串** ⇒
      `text.count('')` = len(text)+1 ⇒ 报「命中 161148 次」⇒ 误导性失败。
    ⇒ 带上下文后，每块都含**前后各若干行公共上下文** ⇒ 可唯一定位。
    """
    old_lines = _norm(old).decode('utf-8').splitlines(keepends=True)
    new_lines = _norm(new).decode('utf-8').splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for group in sm.get_grouped_opcodes(n=3):
        i1 = group[0][1]
        i2 = group[-1][2]
        j1 = group[0][3]
        j2 = group[-1][4]
        old_b = ''.join(old_lines[i1:i2])
        new_b = ''.join(new_lines[j1:j2])
        if old_b == new_b:
            continue
        blocks.append((old_b, new_b))
    return blocks


def _apply(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise AssertionError('期望恰好命中 1 次，实际 %d 次 ⇒ 块无法唯一定位' % n)
    return text.replace(old, new)


def sync_one(repo_rel: str, pkg_rel: str, pkg_root: str, check_only: bool):
    src = os.path.join(REPO, repo_rel.replace('/', os.sep))
    dst = os.path.join(pkg_root, pkg_rel.replace('/', os.sep))
    if not os.path.isfile(src):
        return ('SKIP', repo_rel, '仓库文件不存在')
    if not os.path.isfile(dst):
        return ('SKIP', repo_rel, '包内文件不存在: %s' % dst)

    with open(src, 'rb') as f:
        cur = f.read()
    with open(dst, 'rb') as f:
        disk = f.read()

    if _norm(disk) == _norm(cur):
        return ('ALREADY', repo_rel, '已与仓库一致，无需同步')

    base = _git_show(BASE_COMMIT, repo_rel)
    # 🔴 基线必须是**包内当前内容的来源**（否则派生块对不上）。
    if _norm(base) != _norm(disk):
        return ('FAIL', repo_rel,
                '基线 %s 与包内当前内容不一致 ⇒ 拒绝派生（包可能被手工改过）'
                % BASE_COMMIT)

    blocks = _derive_blocks(base, cur)
    if not blocks:
        return ('FAIL', repo_rel, '无法从 %s 派生替换块' % BASE_COMMIT)

    eol = _detect_eol(disk)
    text = _norm(disk).decode('utf-8')
    applied = 0
    for old_b, new_b in blocks:
        try:
            text = _apply(text, old_b, new_b)
            applied += 1
        except AssertionError as e:
            return ('FAIL', repo_rel, '块 %d 未唯一命中: %s' % (applied, e))
    out = text.replace('\n', eol.decode('utf-8')).encode('utf-8')

    # 🔴 写盘前必须与仓库版逐字一致（归一化换行）
    if _norm(out) != _norm(cur):
        return ('FAIL', repo_rel, '替换后与仓库版不一致 ⇒ 中止写盘')

    if check_only:
        return ('DIFF', repo_rel, '%d 块待同步（未写盘，--check）' % applied)

    # 备份（包外）
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(dst, os.path.join(BACKUP_DIR, os.path.basename(dst)))

    tmp = dst + '.s70tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)
    return ('SYNCED', repo_rel,
            '%d 块；sha %s → %s（%d → %d B）'
            % (applied, _sha(disk)[:16], _sha(out)[:16], len(disk), len(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    dirs = _pkg_dirs()
    if not dirs:
        print('!! 找不到客户包目录')
        return 1
    ver, name, root = dirs[-1]
    print('客户包目录: %s（v%d）' % (root, ver))
    print('基线 commit: %s' % BASE_COMMIT)
    print('备份目录（包外）: %s' % BACKUP_DIR)
    print('-' * 70)

    rc = 0
    for repo_rel, pkg_rel in TARGETS:
        st, rel, msg = sync_one(repo_rel, pkg_rel, root, args.check)
        print('[%s] %s — %s' % (st, rel, msg))
        if st == 'FAIL':
            rc = 1
    print('-' * 70)
    print('结论：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
