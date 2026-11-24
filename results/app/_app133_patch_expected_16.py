#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：把包内测试 runner 的 **clone 性别守门分母**从 12 改成 16。

## 为什么

reviewer **APP-131**（2026-11-24 10:47）原文：
> 验收第 1 项再加 `python tests/test_ext0420_clone_gender.py`（应 **12/12**）。

reviewer **APP-133**（2026-11-24 13:56）原文（**后发 ⇒ 覆盖 APP-131**）：
> 验收第 1 项 `tests/test_ext0420_clone_gender.py` 应 **16/16**

APP-133 同时把 EXT 升到 **b2a4978（v0.4.21）** ⇒ 该 commit 的测试文件
**多了「4. split at gender changes」一节**（4 条新断言）⇒
**运行时断言数从 12 变成 16**（实测 **16/16 PASS**）。

⇒ 🔴 **本轮实测证据**：在**包内 python ＋ 包内 EXT（b2a4978）**上跑，
`RESULT: PASS (16/16)`、`PASS=16 FAIL=0 rc=0`
⇒ 上一轮报「总结：FAIL」是**判据过期**（分母还写着 12），**不是产品缺陷**
（这就是「FAIL 先怀疑判据」的又一例）。

## 纪律

- **只改分母常量与注释**；**测试逻辑一行不改**；
- 定点替换 ＋ 唯一命中断言 ＋ 写前不变量 ＋ **还原式复核** ＋ 写后逐字节复核。
"""
from __future__ import annotations

import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'results/app/_app129_run_pkg_tests.py'


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
        # ① 模块头注释
        ("- `tests/test_ext0420_clone_gender.py`（**APP-131** 追加，reviewer 口径：**12/12**）",
         "- `tests/test_ext0420_clone_gender.py`（**APP-131** 追加；reviewer 口径：\n"
         "  APP-131 = **12/12**、**APP-133（后发，覆盖）= 16/16** ⇒ 本轮按 **16**）"),
        # ② reviewer 原文引用
        ('#   `python tests/test_ext0420_clone_gender.py`（应 **12/12**）」',
         '#   `python tests/test_ext0420_clone_gender.py`（应 **12/12**）」\n'
         '        #   ⇒ 🔴 **APP-133（2026-11-24 13:56，后发 ⇒ 覆盖 APP-131）**：\n'
         '        #      「验收第 1 项 `tests/test_ext0420_clone_gender.py` 应 **16/16**」\n'
         '        #      （EXT 同时升到 b2a4978 ⇒ 该 commit 的测试文件多了\n'
         '        #        「4. split at gender changes」一节 ⇒ 运行时断言 12 → 16）'),
        # ③ 分母注释
        ("            # 🔴 0420 的 `check()` 有 **5 处在 for 循环里** ⇒ 源码 call site 8 个\n"
         "            #   ⇒ 运行时实际 **12** 个断言（reviewer 口径 12/12）\n"
         "            #   ⇒ 分母取**运行时 PASS+FAIL**，不取源码 call site 数。",
         "            # 🔴 0420 的 `check()` 有 **5 处在 for 循环里** ⇒ 源码 call site 12 个\n"
         "            #   ⇒ **运行时**断言数：APP-131 口径 = 12；**APP-133 口径 = 16**\n"
         "            #     （b2a4978 多了「4. split at gender changes」4 条 ⇒ 12 → 16）\n"
         "            #   ⇒ 分母取**运行时 PASS+FAIL**，不取源码 call site 数。\n"
         "            #   ⇒ 🔴 **期望值取 APP-133（后发 ⇒ 覆盖 APP-131）= 16**。"),
        # ④ 判定条件 + 期望字段
        ("                       and den3 == 12),",
         "                       and den3 == 16),"),
        ("                'required_by': 'APP-131',\n"
         "                'expected': '12/12',",
         "                'required_by': 'APP-133（覆盖 APP-131）',\n"
         "                'expected': '16/16',\n"
         "                'expected_by_app131': '12/12',"),
    ]

    out = src
    for old, new, cnt in [(a, b, 1) for a, b in subs]:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != cnt:
            raise SystemExit('FAIL：命中 %d 次（要求 %d）：%r' % (c, cnt, old[:90]))
        out = out.replace(o, nw)

    # 真不变量
    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = sum(norm(b).count('\n') - norm(a).count('\n') for a, b in subs)
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d' % (delta_got, delta_expect))
    red = out
    for old, new in subs:
        red = red.replace(norm(new), norm(old))
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133b'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL：写后逐字节复核失败')
    print('OK %s  %d B -> %d B  sha %s -> %s'
          % (TARGET, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))


if __name__ == '__main__':
    main()
