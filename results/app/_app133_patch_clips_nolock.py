#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-132：给 `_app129_clips_v26.py` 加 `--no-lock` 开关（供整链**一次持锁到底**用）。

## 为什么

reviewer APP-132 明文：
> 要求：整条链（所有臂、默认值检查、抽听样片）**一次持锁到底**，中途不删；
> 锁内容写明起止。结束后再删（只删自己的）。

上一轮 `_app129_clips_v26.py` 自己 `B.acquire_lock(...)` ⇒ 若整链脚本已经持着锁，
这里会**再取一次** ⇒ 要么排队等自己（**死等**），要么两个锁实现并存
（一个原子、一个 `os.replace` ⇒ 又回到「不原子」的老缺陷）。

⇒ 改法：加 `--no-lock` ⇒ 由整链脚本**统一**持锁 ⇒ 抽听样片与降级检查
   与三臂**在同一次持锁窗口内**完成（真正满足「一次持锁到底」）。

## 纪律

- **只加一个开关 ＋ 一处条件**；**其余逻辑一行不改**；
- 定点替换 ＋ 唯一命中断言 ＋ 写前不变量 ＋ **还原式复核** ＋ 写后逐字节复核。
"""
from __future__ import annotations

import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'results/app/_app129_clips_v26.py'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    p = os.path.join(REPO, TARGET)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    crlf = '\r\n' in src

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    subs = [
        # ① 加开关
        ("    ap.add_argument('--skip-degrade', action='store_true')",
         "    ap.add_argument('--skip-degrade', action='store_true')\n"
         "    # 🔴 APP-132：整链脚本已持锁时用 --no-lock ⇒ 本脚本**不再自己取锁**\n"
         "    #   （否则会与整链的锁并存 ⇒ 两个锁实现 ⇒ 又回到「不原子」的老缺陷）\n"
         "    ap.add_argument('--no-lock', action='store_true')"),
        # ② 取锁条件化
        ("    lock = B.acquire_lock('app bgkeep v2.6 clips+degrade')\n"
         "    try:",
         "    lock = None if args.no_lock else \\\n"
         "        B.acquire_lock('app bgkeep v2.6 clips+degrade')\n"
         "    try:"),
        # ③ 放锁条件化
        ("    finally:\n"
         "        B.release_lock(lock)\n"
         "    log('证据：results/app/app129_clips_v26_evidence.json')",
         "    finally:\n"
         "        if lock is not None:\n"
         "            B.release_lock(lock)\n"
         "    log('证据：results/app/app129_clips_v26_evidence.json')"),
    ]

    out = src
    for old, new in subs:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != 1:
            raise SystemExit('FAIL：命中 %d 次（要求 1）：%r' % (c, old[:90]))
        out = out.replace(o, nw)

    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = sum(norm(b).count('\n') - norm(a).count('\n')
                        for a, b in subs)
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d' % (delta_got, delta_expect))
    red = out
    for old, new in subs:
        red = red.replace(norm(new), norm(old))
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133c'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL：写后逐字节复核失败')
    import ast
    ast.parse(after.decode('utf-8'))
    print('OK %s  %d B -> %d B  sha %s -> %s  (AST OK)'
          % (TARGET, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))


if __name__ == '__main__':
    main()
