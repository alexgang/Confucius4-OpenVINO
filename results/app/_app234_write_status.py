#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · 往 `status/app/STATUS_APP.md` **追加** `## §234` 章节。

## 定点写入三件套（按项目纪律）

1. 备份 `%TEMP%/STATUS_APP.md.bak_app234`；
2. 写前在**内存新文本**上跑真不变量（唯一命中断言 + 旧正文**逐字未变**
   ＋ **还原式复核** + 字节/行数上限断言）；
3. 临时文件 → `os.replace` ⇒ 写后**另起脚本**独立复核 + `git diff --numstat`。

## 🔴 只追加，绝不回头改旧章节

- 旧章节（§231/§232/§233 等）**逐字不动**；
- 头部 `last_ack` **不改**（本轮无新纠偏 ⇒ 仍 APP-133）；
- 头部「更新时间」改为 **`Get-Date` 实测值**（实参传入，不推算）；
- 「最近更新」块**首部插入** 1 条（新条目在上、旧条目下移**不删**）。

## 行尾

活文档是**混合行尾**（头部与新章节用 LF、更早各节用 CRLF；
实测 57 CRLF / 25 孤立 LF）⇒ **不可断言「全文无孤立 LF」**。
本轮**新增的行一律用 LF**（与 §232/§233 同款），且**不触碰**任何既有行的行尾。
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TARGET = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'),
                      'STATUS_APP.md.bak_app234')
TS = sys.argv[1] if len(sys.argv) > 1 else ''
if not TS:
    raise SystemExit('[FAIL] 必须传入 Get-Date 实测时间戳')

SEC_TITLE = (
    '## §234 待命轮（**六通道复核 ⇒ 无新 App 纠偏**，`last_ack` 仍 '
    '**APP-133**）｜🟢 **修掉 3 处真缺陷**：'
    '① v2.6 改动说明正文**未入库**（干净 clone 跑不了已入库的复核脚本）'
    '｜🔴 **完整版成包路径从不执行版本标识同步**（§233 的修法没接进生产路径）'
    '｜🔴 **插入锚点唯一性判据与选取口径不一致**（**阻断下一版 v2.7 成包**）'
    '｜🟢 独立复核 **11/11 ＋ 17/17 ＋ 16/16 全 PASS**（各含反证组）'
    '｜🔴 **如实登记 7 处未修/待裁定项**｜**本条需等 reviewer 复核**')
SEC_POINTER = (
    '> 🔴 **本节正文全文 ⇒ '
    '`status/app/STATUS_APP_sec234_detail_20261125.md`**'
    '（含 §0 六通道逐通道证据、§1 三处真缺陷逐条根因与修法、'
    '§2 独立复核与反证组（含本轮自己踩的 5 个坑）、'
    '§3 交付面只读复核、§4 未修项如实登记、§5 纪律自查、§6 下一轮）')

RECENT = (
    '> 🔴 %s ｜ **待命轮：六通道复核 ⇒ 仍无新 App 纠偏**'
    '（本地 max APP-133 ＝ QQ max APP-133 ＝ `last_ack` ⇒ **值不变**）'
    '｜🟢 **修掉 3 处真缺陷**：'
    '① `live_caption/_app129_changelog_2.6_{zh,en}.md` **未入库** ⇒ '
    '已入库的 `_app233_verify_sync_c172_e2e.py` **依赖**它们 ⇒ '
    '**干净 clone 跑不了**（§222 入库完整性）⇒ **已入库**；'
    '② 🔴 **完整版成包路径从不执行版本标识同步**'
    '（`_app129_build_v26.py` 的 `stage=sync` **不碰** README/NOTICE/MANIFEST；'
    '唯一会调 `sync_c172` 的 `pack_v13` 挂在**从不执行**的 `stage=pack` 上'
    '⇒ 实测构建日志全文**无一行 `stage=pack`**）⇒ 新增通用 '
    '`live_caption/sync_pkg_identity.py`（sync_c172 ＋ app170 闸门 ＋ **硬断言**）'
    '并接成成包脚本的第 5 个 stage `identity`；'
    '③ 🔴 **插入锚点唯一性判据与选取口径不一致** ⇒ v2.7（robocopy v2.6 ⇒ v2.7）'
    '插入时锚点 `## v2.6 改动说明` 命中 **2 次** ⇒ **整个身份同步失败**'
    '⇒ 新增 `unique_anchor()`（**只扩展锚点、不改既有章节标题**）'
    '｜🟢 独立复核 **11/11 ＋ 17/17 ＋ 16/16 全 PASS**（各含**反证组**）'
    '｜🟢 **未改任何客户包**（真包 4 个身份文件 SHA256 跑前跑后一致）'
    '｜🟢 **未打包 zip**／未跑推理·计时（**未取 MACHINE_LOCK**）／未调 MiniMax／未连 B 机'
    '｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）'
    '｜🔴 **如实登记 7 处未修/待裁定项**'
    '｜**本条需等 reviewer 复核**' % TS)


def main() -> int:
    raw0 = open(TARGET, 'rb').read()
    text0 = raw0.decode('utf-8')
    print('写前：%d B；CRLF %d；LF %d' % (
        len(raw0), text0.count('\r\n'), text0.count('\n')))

    shutil.copy2(TARGET, BACKUP)
    print('备份：%s' % BACKUP)

    # ── 锚点唯一性断言 ────────────────────────────────────────────
    a_ts = '更新时间: '
    assert text0.count(a_ts) == 1, '「更新时间」锚点不唯一'
    m_ts = re.search(r'^更新时间: (.+)$', text0, re.M)
    old_ts = m_ts.group(1)
    a_ack = 'last_ack: '
    assert text0.count(a_ack) == 1, '「last_ack」锚点不唯一'
    # 🔴 实测：该标题是**混合行尾**里的一处 **CRLF**（`## 最近更新\r\n`），
    #    而文件其余新章节用 LF ⇒ 锚点必须按**确切字节**取，
    #    且**新插入的行用 LF**（不改动该标题自身的行尾）。
    a_recent = '## 最近更新\r\n'
    assert text0.count(a_recent) == 1, '「最近更新」锚点不唯一'
    assert text0.rstrip().endswith('）'), '文末形态与预期不符'

    # ── 在内存新文本上做替换（**只追加/只改头部两行**）──────────────
    text1 = text0.replace(a_ts + old_ts, a_ts + TS, 1)
    # 「最近更新」块首部插入 1 条（旧条目下移、不删）
    text1 = text1.replace(a_recent, a_recent + RECENT + '\n', 1)
    # §234 章节**追加在文末**
    text1 = text1.rstrip('\n') + '\n\n' + SEC_TITLE + '\n' + SEC_POINTER + '\n'

    # ══ 真不变量 ═════════════════════════════════════════════════
    checks = []
    checks.append(('「更新时间」已改为实测值',
                   ('更新时间: ' + TS) in text1))
    checks.append(('「last_ack」**未变**（仍 APP-133）',
                   text1.count('last_ack: APP-133') == 1))
    checks.append(('「最近更新」新条目已插入',
                   RECENT[:60] in text1))
    checks.append(('§234 章节已追加在文末',
                   text1.rstrip().endswith(SEC_POINTER)))
    checks.append(('§234 章节只出现 1 次',
                   text1.count(SEC_TITLE) == 1))
    # 🔴 旧正文逐字未变：把**新增/改动**的三处还原后应逐字节等于原文
    back = text1.replace(a_recent + RECENT + '\n', a_recent, 1)
    back = back.replace(a_ts + TS, a_ts + old_ts, 1)
    back = back.rstrip('\n')
    back = back[:back.rfind('\n\n## §234')] + '\n' if '\n\n## §234' in back \
        else back
    checks.append(('还原式复核：去掉新增内容后逐字节同原文',
                   back.rstrip('\n') == text0.rstrip('\n')))
    # 旧章节标题仍在
    for keep in ('## §231 ', '## §232 ', '## §233 '):
        checks.append(('旧章节保留：%s' % keep.strip(),
                       text1.count(keep) == 1))
    # 硬限额（APP-052④）
    n_bytes = len(text1.encode('utf-8'))
    checks.append(('字节数 ≤ 40 000（%d）' % n_bytes, n_bytes <= 40000))
    n_lines = text1.count('\n') + 1
    checks.append(('行数 ≤ 300（%d）' % n_lines, n_lines <= 300))
    # 新增行一律 LF（不引入 CRLF）
    checks.append(('未引入新的 CRLF（新增行全 LF）',
                   text1.count('\r\n') == text0.count('\r\n')))

    for name, ok in checks:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
    if not all(ok for _, ok in checks):
        print('\n[FAIL] 真不变量未全过 ⇒ **零改动**（不写盘）')
        return 1

    tmp = TARGET + '.tmp_app234'
    with open(tmp, 'wb') as f:
        f.write(text1.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)
    print('\n写入完成：%d B → %d B（delta %+d）；行数 %d'
          % (len(raw0), n_bytes, n_bytes - len(raw0), n_lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
