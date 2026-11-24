#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：把签 ACCEPTED 脚本的 **EXT_VERSION 闸门**从 0.4.20 改成 **0.4.21**。

## 为什么

本轮把包内 EXT 升到 **b2a4978（v0.4.21）**（`EXT_COMMIT` 已改），
但闸门里的 `EXT_VERSION` 仍是 **`'0.4.20'`** ⇒ 签 ACCEPTED 时
`('EXT 版本 = %s（APP-131）' % EXT_VERSION, ext_ver == EXT_VERSION)`
这一项 **FAIL**（实测：`[FAIL] EXT 版本 = 0.4.20（APP-131）`）。

🔴 **这是「判据过期」而不是产品缺陷** —— 包内 `ext/bridge/version.py` 里
就是 `EXT_VERSION = "0.4.21"`（已由 `_app133_verify_pkg.py` 独立复核
**44 文件逐字节一致**）⇒ 闸门的期望值过期了。

⇒ 修法：`EXT_VERSION` ⇒ `'0.4.21'` ＋ 注释说明版本链 ＋ 闸门标签改为 APP-133。

## 纪律

- **只改版本常量与闸门标签**；验收逻辑一行不改；
- 定点替换 ＋ 唯一命中断言 ＋ 写前真不变量 ＋ **还原式复核**
  ⇒ 临时文件 → `os.replace` ⇒ **写后逐字节复核**。
"""
from __future__ import annotations

import ast
import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'live_caption/_app129_sign_accepted_v26.py'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    p = os.path.join(REPO, TARGET)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    crlf = '\r\n' in src

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133i'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    subs = [
        ("#: 🔴🔴 **APP-131**：EXT 由 **3573b2d（v0.4.19）改为 4740b06（v0.4.20）**\n"
         "#:   （reviewer：「APP-129 第 2 节的「EXT：3573b2d」改为「4740b06」」）\n"
         "EXT_COMMIT = 'b2a4978'\n"
         "EXT_VERSION = '0.4.20'",
         "#: 🔴🔴 **EXT 版本链**（reviewer 逐条覆盖）：\n"
         "#:   APP-129 `3573b2d`（v0.4.19）→ APP-131 `4740b06`（v0.4.20）\n"
         "#:   → **APP-133 `b2a4978`（v0.4.21）＝ 本轮交付口径**\n"
         "#:   （reviewer：「v2.6 的 EXT 改用 b2a4978（替代 APP-131 的 4740b06）」）\n"
         "EXT_COMMIT = 'b2a4978'\n"
         "EXT_VERSION = '0.4.21'"),
        ("        ('EXT 版本 = %s（APP-131）' % EXT_VERSION, ext_ver == EXT_VERSION),",
         "        ('EXT 版本 = %s（APP-133）' % EXT_VERSION, ext_ver == EXT_VERSION),"),
    ]

    out = src
    for old, new in subs:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != 1:
            raise SystemExit('FAIL：命中 %d 次（要求 1）：%r' % (c, old[:80]))
        out = out.replace(o, nw)

    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = sum(norm(b).count('\n') - norm(a).count('\n')
                        for a, b in subs)
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d'
                         % (delta_got, delta_expect))
    red = out
    for old, new in subs:
        red = red.replace(norm(new), norm(old))
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133i'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL：写后逐字节复核失败')
    ast.parse(after.decode('utf-8'))
    print('OK %s  %d B -> %d B  sha %s -> %s  (AST OK)'
          % (TARGET, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))


if __name__ == '__main__':
    main()
