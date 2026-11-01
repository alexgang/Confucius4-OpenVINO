#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app129 —— 在 STATUS_APP.md 的「最近更新」与「最近章节」索引里补 §129 条目。

🔴 只**追加**条目，不改旧条目（一个字节都不改）。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

NEW_LINE = (
    '- 2026-11-02 04:47 **§129** ⇒ 无新纠偏（61 条 = APP-061）⇒ **自查 4 个真缺陷并修好**：'
    '① `app224` 用**移动 `git HEAD`** 当基线 ⇒ 修复一提交就在**正确代码上永久 FAIL**（0/5）'
    '⇒ 改钉 `fae75d9` ＋ **判据自检**（坏文件必被抓住）⇒ **5/0** '
    '② 锁闸门第 11 组 AST 反证谓词**恒真**（只认 `os.exists`、抓不到 `os.path.exists`）'
    '⇒ **只定位留证、待 reviewer 裁定** '
    '③ `app223` **3 个缺陷**（`--dry-run` 跑不出来 / 自检冲掉真机证据 / 反证臂从不判定）全修 '
    '④ **APP-061② 附带问题** `Fatal Python error: _enter_buffered_busy`（边车退出崩溃）'
    '⇒ 改裸 fd `os.read` ⇒ **A/B 实测 orig 崩 3221225477 / fixed rc=0（两组都收到数据）** '
    '＋ 回归 `app215` 29/0、`app220` 39/0、`app219` 13/0 '
    '⇒ ⛔ **设备级实测仍未开跑**（用户会话 PID 14712 实测仍在烧 CPU 0.656 s/5 s）'
    '＋ 🔴 v2.2 包内仍是改前版 ⇒ 下一版打 v2.3\n')

INDEX_ROW = (
    '| §129 | **巡检无新纠偏 ⇒ 自查 4 个真缺陷并修掉**（`app224` 移动-HEAD 基线 ⇒ 永久假 FAIL；'
    '锁闸门反证谓词恒真；`app223` 3 个缺陷；边车 `_enter_buffered_busy` 崩溃）'
    '＋ 回归 29/0・39/0・13/0 | **本轮新增（见下）** |\n')


def main() -> int:
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        text = f.read()

    # 1) 「最近更新」：在 `## 最近更新` 之后插入新条目（**不删旧条目**）
    if '§129' in text and NEW_LINE[:40] in text:
        print('最近更新：已存在 §129 条目 ⇒ 跳过')
    else:
        marker = '## 最近更新\n'
        i = text.index(marker) + len(marker)
        text = text[:i] + NEW_LINE + text[i:]
        print('最近更新：已插入 §129 条目（旧条目未动）')

    # 2) 「最近章节」索引表：在表末追加 §129 行
    if INDEX_ROW[:30] not in text:
        # 表末 = `| §128 | ... |\n` 那一行之后（用行首定位，避免中间空格差异）
        anchor = '| §128 | 巡检无新纠偏 ⇒ APP-061②'
        j = text.index(anchor)
        eol = text.index('\n', j) + 1
        text = text[:eol] + INDEX_ROW + text[eol:]
        print('最近章节索引：已追加 §129 行（旧行未动）')

    # 3) 原子替换
    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(tmp, STATUS)
    print('已写盘：%d B / %d 行'
          % (len(text.encode('utf-8')), text.count('\n') + 1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
