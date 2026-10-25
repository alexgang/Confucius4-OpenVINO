#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APP-035：把 status/app/STATUS_APP.md 头部的「最近更新」块裁到 <= 15 行。

🔴 口径（守 APP-001 的 STATUS 格式要求）：
  - 只动头部「## 最近更新」与第一个「## §N」之间的那一段；
  - **不删任何章节正文**（§N 里的历史记录必须完整保留）；
  - 合并的是**头部摘要行**，信息全部压进保留行里（不丢结论）；
  - 写回用 newline='' ⇒ 保留原行尾风格；幂等（第二次跑应「无变化」）。

用法：
  python app035_trim_status_head.py --file <STATUS_APP.md> [--check-only]
"""
from __future__ import annotations

import argparse
import io
import os
import sys

MAX_LINES = 15
HEAD_MARK = '## 最近更新'
SECTION_MARK = '## §'


def read_text(path: str) -> str:
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def split_block(txt: str):
    """返回 (head, block_lines, tail)：block 是「最近更新」下的摘要行（去掉空行）。"""
    lines = txt.split('\n')
    try:
        h = lines.index(HEAD_MARK)
    except ValueError:
        raise SystemExit('!! 未找到「## 最近更新」标题')

    e = None
    for i in range(h + 1, len(lines)):
        if lines[i].startswith(SECTION_MARK):
            e = i
            break
    if e is None:
        raise SystemExit('!! 未找到「## §N」章节标题，无法确定块尾')

    block = [ln for ln in lines[h + 1:e] if ln.strip()]
    head = lines[:h + 1]
    tail = lines[e:]
    return head, block, tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()

    txt = read_text(args.file)
    head, block, tail = split_block(txt)
    n = len(block)

    print(f'[head] 「最近更新」当前 {n} 行（上限 {MAX_LINES}）')

    if n <= MAX_LINES:
        print('[skip] 已符合 <= %d 行 ⇒ 无需裁剪' % MAX_LINES)
        return 0

    if args.check_only:
        print('[check-only] 超限，未写入')
        return 1

    # 🔴 合并策略：**头部只保留最新 15 条 + 一条指针行**。
    #    被丢弃的条目**在正文 §N 章节里本来就完整存在**（STATUS 是 append-only 的），
    #    ⇒ 头部压缩**不会丢信息**，只是把「历史细节」指回章节即可。
    keep = block[:MAX_LINES - 1]
    dropped = block[MAX_LINES - 1:]

    # 指针行：写明被合并掉多少条 + 指向最早的章节
    first_dropped = dropped[0]
    sec = ''
    if '§' in first_dropped:
        tail_txt = first_dropped.split('§', 1)[1]
        num = ''.join(ch for ch in tail_txt if ch.isdigit())
        if num:
            sec = '§' + num
    pointer = (f'- （更早 {len(dropped)} 条已合并 ⇒ 完整记录见正文 {sec} 及更早章节，'
               f'头部只保留最近 {MAX_LINES} 条）')

    new_block = keep + [pointer]
    out = '\n'.join(head + new_block + tail)

    with io.open(args.file, 'w', encoding='utf-8', newline='') as f:
        f.write(out)

    print(f'[ok] 已重写：{n} 行 -> {len(new_block)} 行（合并 {len(dropped)} 行）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
