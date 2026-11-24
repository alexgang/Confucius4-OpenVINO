#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：把 **§228 companion 的 §4 整链表**标注为「已被 §230 取代」。

## 为什么

§228 companion 的 §4（10 分钟整链）那张表**整列是 `None`** ——
那是**上一会话**在链刚跑完、还没抽数时写下的骨架 ⇒ 留着一张全 `None` 的表
会让 reviewer 以为「v2.6 整链没出数字」。

⇒ 本轮 **§230 companion** 里有**完整的三臂数字**（含 reviewer §3.2 要的
synth_rtf / 语速 max / 积压峰值 / 收尾积压，全部采到了）⇒
⇒ 在 §228 的 §4 表**上方**加一行明确的**取代声明**（**表本身逐字保留**，
只加指针），让 reviewer 一眼知道去哪看真数字。

## 纪律

- **只加 1 行指针**（表本身与正文一字不改）；
- 定点替换 ＋ 唯一命中断言 ＋ 写前真不变量 ＋ **还原式复核**
  ⇒ 临时文件 → `os.replace` ⇒ **写后逐字节复核**。
"""
from __future__ import annotations

import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'status/app/STATUS_APP_sec228_detail_20261124.md'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    p = os.path.join(REPO, TARGET)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    crlf = '\r\n' in src

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133h'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    old = ("## §4 10 分钟固定片段整链（§3.2）—— 保留背景音 **开 / 关各一轮，每轮单独起桥接**\n"
           "\n"
           "（证据：`results/app/app129_chain_v26_evidence.json` ＋ `shared/bgkeep/e2e_v26/*/`）")
    new = ("## §4 10 分钟固定片段整链（§3.2）—— 保留背景音 **开 / 关各一轮，每轮单独起桥接**\n"
           "\n"
           "> 🔴🔴 **本节的整链数字已被 §230 取代（不要看这里）**\n"
           ">\n"
           "> 本节这张表是**上一会话**在链刚跑完、**还没抽数**时写下的骨架\n"
           "> ⇒ **整列是 `None`** ⇒ **不是**「v2.6 没出数字」。\n"
           "> ⇒ **真数字（三臂对照 ＋ synth_rtf ＋ 语速 max ＋ 积压峰值/收尾积压\n"
           "> ＋ clone 臂克隆计数）全部在** `status/app/STATUS_APP_sec230_detail_20261124.md`\n"
           "> ⇒ **证据**：`results/app/app133_chain_v26_evidence.json` ＋\n"
           "> `shared/bgkeep/e2e_v26_r2/*/`。\n"
           "> ⇒ 本表**逐字保留**（历史痕迹，不静默抹掉）。\n"
           "\n"
           "（原始证据：`results/app/app129_chain_v26_evidence.json` ＋ `shared/bgkeep/e2e_v26/*/`）")

    o, nw = norm(old), norm(new)
    c = src.count(o)
    if c != 1:
        raise SystemExit('FAIL：命中 %d 次（要求 1）' % c)
    out = src.replace(o, nw)

    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = nw.count('\n') - o.count('\n')
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d'
                         % (delta_got, delta_expect))
    red = out.replace(nw, o)
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133h'
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
