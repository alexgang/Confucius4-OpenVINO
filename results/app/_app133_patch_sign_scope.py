#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：把签 ACCEPTED 脚本的 **交付口径**更新到 v0.4.21 / b2a4978。

## 为什么

`_app129_sign_accepted_v26.py` 的 `payload['delivery_scope']` 里仍写着
**「EXT v0.4.20（4740b06）」**（APP-131 的口径）⇒ **与本轮实际打进包的
b2a4978（v0.4.21）不一致** ⇒ **签名件与包内容对不上** ⇒ reviewer 一看就知道。

同时 `corrections` 列表缺 **APP-131 / APP-132 / APP-133**。

## 纪律

- **只改交付口径文字与 corrections 列表**；**验收逻辑一行不改**；
- 定点替换 ＋ 唯一命中断言 ＋ 写前不变量 ＋ **还原式复核** ＋ 写后逐字节复核。
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

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133f'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    subs = [
        # ① corrections 列表
        ("        'corrections': ['APP-129', 'APP-130', 'APP-123'],",
         "        'corrections': ['APP-129', 'APP-130', 'APP-131',\n"
         "                         'APP-132', 'APP-133', 'APP-123'],"),
        # ② 交付口径里的 EXT 版本
        ("            '(1) EXT **v0.4.20（4740b06）**——「保留背景音」默认**开**、'\n"
         "            '默认分离设备 **GPU.0(FP32)**（可用 EXT_BG_DEVICE=CPU 改）、'\n"
         "            '克隆音色跟随男女切换（v0.4.20，APP-131）；'",
         "            '(1) EXT **v0.4.21（b2a4978）**——「保留背景音」默认**开**、'\n"
         "            '默认分离设备 **GPU.0(FP32)**（可用 EXT_BG_DEVICE=CPU 改）、'\n"
         "            '克隆音色跟随男女切换（v0.4.20，APP-131）＋'\n"
         "            '按音高把男女混在一起的段切开（v0.4.21，APP-133）；'"),
    ]

    out = src
    for old, new in subs:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != 1:
            raise SystemExit('FAIL：命中 %d 次（要求 1）：%r' % (c, old[:80]))
        out = out.replace(o, nw)

    # 真不变量
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
    tmp = p + '.tmp_app133f'
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
