#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · 给完整版成包脚本接上「版本标识一致」stage（**生产路径**）。

## 为什么必须改（🔴 真缺陷，APP-234 轮实测）

`_app129_build_v26.py` 的 stage 有 4 个：`copy` / `sync` / `pack` / `cleanup`：

- `stage=sync` 只写 `app/tts_engine.py`、`app/tts_worker.py`、`ext/bridge/*`、
  `ext/extension/*`、`ext/extension/manifest.json`、`Start_Bridge.bat`、
  `models/bgsep/*` ⇒ **从不碰** `README_zh.md` / `README_en.md` /
  `NOTICE` / `app/MANIFEST.json`；
- 唯一会调 `sync_c172` 的是 `pack_v13.py` 的 `main()`；
- 而**完整版线（v2.x）从来不出 zip**（用户长期规则「不通知 ⇒ 不打包」）
  ⇒ `stage=pack` **不执行** ⇒ 版本标识**永不自动同步**。

**实测证据**：`results/app/app129_build_v26.log` 全文只有 `stage=copy`（×2）
与 `stage=sync`（×5），**没有一行 `stage=pack`**；
v2.6 的 `README_zh.md` mtime = **2026-11-24 13:14:55**
（与 `_app129_changelog_2.6_zh.md` 的 13:14 同批）⇒ 版本标识是
**人工带外**做的。

⇒ APP-233 把修法放进 `sync_c172`（对的），但**没接进完整版的成包路径**
⇒ 下一版（v2.7）照抄同一套 stage 又要人工做一遍。
本脚本把 `sync_pkg_identity`（sync_c172 + app170 闸门 + 硬断言）接成
**第 5 个 stage**，并纳入 `all`。

## 定点写入三件套（按项目纪律）

1. 备份（`%TEMP%/_app129_build_v26.py.bak_app234`）；
2. 写前在**内存新文本**上跑真不变量（唯一命中断言 + AST + 行尾风格不变
   + 旧正文逐字未变）+ **还原式复核**（改回须逐字节同）；
3. 临时文件 → `os.replace` ⇒ 写后**另起脚本**独立复核 + `numstat`。

## 行尾

目标文件是**纯 CRLF**（实测 477 CRLF / 0 孤立 LF）⇒ 本脚本**按 CRLF 写**。
"""
from __future__ import annotations

import ast
import io
import os
import shutil
import sys

def find_repo():
    """向上找含 `live_caption/` 的目录（不写死层级 ⇒ 本脚本挪位置也不坏）。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, 'live_caption')):
            return d
        d = os.path.dirname(d)
    raise SystemExit('[FAIL] 找不到仓库根（无 live_caption/）')


REPO = find_repo()
TARGET = os.path.join(REPO, 'live_caption', '_app129_build_v26.py')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'),
                      '_app129_build_v26.py.bak_app234')


def read_raw(path):
    with open(path, 'rb') as f:
        return f.read()


def to_text(data: bytes) -> str:
    return data.decode('utf-8')


def main() -> int:
    raw0 = read_raw(TARGET)
    text0 = to_text(raw0)
    if '\r\n' not in text0:
        print('[FAIL] 目标文件不是 CRLF ⇒ 需人工确认行尾策略')
        return 2
    n_crlf0 = text0.count('\r\n')
    n_lf0 = text0.count('\n')
    print('写前：%d B；CRLF %d；LF 合计 %d；孤立 LF %d'
          % (len(raw0), n_crlf0, n_lf0, n_lf0 - n_crlf0))

    # ── 备份 ──────────────────────────────────────────────────────
    shutil.copy2(TARGET, BACKUP)
    print('备份：%s' % BACKUP)

    # ── 唯一的命中断言 ────────────────────────────────────────────
    anchor_stage_def = (
        'def stage_cleanup():')
    assert text0.count(anchor_stage_def) == 1, 'stage_cleanup 锚点不唯一'
    anchor_choices = (
        "choices=['copy', 'sync', 'pack', 'cleanup', 'all'])")
    assert text0.count(anchor_choices) == 1, 'choices 锚点不唯一'
    anchor_sync_call = (
        "    if args.stage in ('sync', 'all'):\r\n"
        "        if not stage_sync():\r\n"
        "            return 3\r\n")
    assert text0.count(anchor_sync_call) == 1, 'sync 调用锚点不唯一'

    new_stage = (
        'def stage_identity():\r\n'
        '    """🔴 版本标识一致（**生产路径**）：README / NOTICE / MANIFEST。\r\n'
        '\r\n'
        '    ## 为什么必须有这一步（APP-234 轮实测的真缺陷）\r\n'
        '    `stage=sync` 只写 `app/*.py` 与 `ext/**` ⇒ **从不碰**\r\n'
        '    `README_zh.md` / `README_en.md` / `NOTICE` / `app/MANIFEST.json`；\r\n'
        '    而唯一会调 `sync_c172` 的是 `pack_v13.py` 的 `main()` ⇒\r\n'
        '    **完整版线（v2.x）从来不出 zip**（用户规则「不通知 ⇒ 不打包」）\r\n'
        '    ⇒ `stage=pack` **不执行** ⇒ 版本标识**永不自动同步**。\r\n'
        '\r\n'
        '    **实测证据**：`results/app/app129_build_v26.log` 全文只有\r\n'
        '    `stage=copy`（×2）与 `stage=sync`（×5），**没有一行 `stage=pack`**；\r\n'
        '    v2.6 的 `README_zh.md` mtime = 2026-11-24 13:14:55\r\n'
        '    ⇒ 版本标识是**人工带外**做的。\r\n'
        '\r\n'
        '    ⇒ 本 stage 把「sync_c172 + app170 闸门 + 硬断言」接进成包流程\r\n'
        '    ⇒ 下一版**不需要**再人工带外做这一步。\r\n'
        '    """\r\n'
        '    tool = os.path.join(HERE, \'sync_pkg_identity.py\')\r\n'
        '    if not os.path.isfile(tool):\r\n'
        '        log(\'🔴 找不到 sync_pkg_identity.py ⇒ 版本标识同步失败\')\r\n'
        '        return False\r\n'
        '    cmd = [sys.executable, tool, \'--pkg\', DST]\r\n'
        '    log(\'① 版本标识同步 + app170 闸门 + 硬断言\')\r\n'
        '    p = subprocess.run(cmd, capture_output=True, text=True,\r\n'
        '                       timeout=1800)\r\n'
        '    log(p.stdout[-6000:])\r\n'
        '    if p.stderr.strip():\r\n'
        '        log(\'stderr: %s\' % p.stderr[-2000:])\r\n'
        '    log(\'版本标识同步 rc=%d\' % p.returncode)\r\n'
        '    return p.returncode == 0\r\n'
        '\r\n'
        '\r\n')

    new_choices = (
        "choices=['copy', 'sync', 'identity', 'pack', 'cleanup', 'all'])")

    new_sync_call = (
        "    if args.stage in ('sync', 'all'):\r\n"
        "        if not stage_sync():\r\n"
        "            return 3\r\n"
        "    if args.stage in ('identity', 'all'):\r\n"
        "        if not stage_identity():\r\n"
        "            return 6\r\n")

    # ── 在内存新文本上做替换 ──────────────────────────────────────
    text1 = text0.replace(anchor_stage_def, new_stage + anchor_stage_def, 1)
    text1 = text1.replace(anchor_choices, new_choices, 1)
    text1 = text1.replace(anchor_sync_call, new_sync_call, 1)

    # ══ 真不变量（写前，在内存新文本上）═════════════════════════════
    checks = []

    # ① 唯一命中：三个锚点各被替换恰好一次
    checks.append(('stage_identity 定义已插入且唯一',
                   text1.count('def stage_identity():') == 1))
    checks.append(('identity stage 已接入 choices',
                   "choices=['copy', 'sync', 'identity', 'pack', 'cleanup', 'all'])"
                   in text1))
    checks.append(('identity stage 已在 main() 中被调用',
                   text1.count("if args.stage in ('identity', 'all'):") == 1))

    # ② AST 可解析
    try:
        ast.parse(text1)
        checks.append(('ast.parse 通过', True))
    except SyntaxError as e:
        checks.append(('ast.parse 通过（%r）' % (e,), False))

    # ③ 行尾风格不变（纯 CRLF ⇒ 无孤立 LF）
    n_crlf1 = text1.count('\r\n')
    n_lf1 = text1.count('\n')
    checks.append(('行尾风格不变（纯 CRLF，无孤立 LF）',
                   n_lf1 == n_crlf1))
    checks.append(('CRLF 数增加 == 新增行数',
                   (n_crlf1 - n_crlf0) ==
                   (text1.count('\n') - text0.count('\n'))))

    # ④ 旧正文逐字未变（把新增块去掉后应逐字节等于原文）
    text1_back = text1.replace(new_stage + anchor_stage_def,
                               anchor_stage_def, 1)
    text1_back = text1_back.replace(new_choices, anchor_choices, 1)
    text1_back = text1_back.replace(new_sync_call, anchor_sync_call, 1)
    checks.append(('还原式复核：改回后逐字节同原文',
                   text1_back == text0))

    # ⑤ 关键旧内容仍在（不被误删）
    for keep in ('def stage_copy():', 'def stage_sync():',
                 'def stage_pack():', 'def main():',
                 'import _app116_build_v25 as B'):
        checks.append(('旧内容保留：%s' % keep, keep in text1))

    # ⑥ 字节数增量 == 新增内容字节数（无隐藏改动）
    raw1 = text1.encode('utf-8')
    expect_delta = len(new_stage.encode('utf-8')) \
        + (len(new_choices) - len(anchor_choices)) \
        + (len(new_sync_call) - len(anchor_sync_call))
    checks.append(('字节增量 == 新增内容字节数（delta=%d）'
                   % (len(raw1) - len(raw0)), len(raw1) - len(raw0) == expect_delta))

    for name, ok in checks:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
    if not all(ok for _, ok in checks):
        print('\n[FAIL] 真不变量未全过 ⇒ **零改动**（不写盘）')
        return 1

    # ── 写盘：临时文件 → os.replace ───────────────────────────────
    tmp = TARGET + '.tmp_app234'
    with open(tmp, 'wb') as f:
        f.write(raw1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)
    print('\n写入完成：%d B → %d B（delta %+d）'
          % (len(raw0), len(raw1), len(raw1) - len(raw0)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
