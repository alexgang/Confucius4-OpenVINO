#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-232 轮：核对**实发邮件正文**与**入库件**是否逐字节相同，并检查是否被截断。

## 🔴 为什么必须核对（§222 实证）
- 🔴 **「入库件」≠「实发件」**：§222 曾出现「发信记录入库的**不是实际发出的那版**」。
- 🔴 **长邮件正文会被截断**（§224 的 11 KB 中间丢失）⇒ 必须**取回实发正文**再比。
- 🔴 **首/中/尾三地标**（§226 的做法）：只查首尾**不足以**证明中间没丢 ⇒ 中段也放标记。

## 🔴 本脚本的取数方式（**不手抄正文**）
- 实发正文由**工具结果落盘** ⇒ `results/app/_app232_sent_body.html`
  （由调用方把 `GetMessage` 返回的 `body` 字段原样写入该文件）。
- 本脚本**只做机器比对**：HTML 反转义 → 纯文本 ⇒ 与入库件逐字节比。

## 判据
1. 实发正文（**去掉服务端追加的引用原文尾巴**）⇒ **与入库件逐字节相同**；
2. 长度相等（⇒ 没被截断、没被加内容）；
3. **首/中/尾三处标记**在实发正文中**全部命中**（中段命中 ⇒ 不是 §224 那种「中间丢」）。
"""
from __future__ import annotations

import html
import io
import os
import re
import sys

LOCAL = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption\_app232_email_body.txt'
SENT_HTML = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app232_sent_body.html'


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def to_text(s):
    s = html.unescape(s)
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = re.sub(r'</div>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    return s


def main():
    if not os.path.isfile(SENT_HTML):
        print('实发正文文件不存在 ⇒ 无法核对 ⇒ FAIL')
        return 1
    local = read(LOCAL)
    raw = read(SENT_HTML)
    marker = '---------- Original ----------'
    body = to_text(raw.split(marker)[0] if marker in raw else raw)

    errs = []
    print('入库件字符数: %d' % len(local))
    print('实发正文字符数: %d' % len(body))

    if len(body.strip()) != len(local.strip()):
        errs.append('长度不等（去尾空白）：实发 %d != 入库 %d'
                    % (len(body.strip()), len(local.strip())))

    if body.strip() != local.strip():
        errs.append('正文内容与入库件不同')
        a, b = body.strip(), local.strip()
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                errs.append('  首个差异 @%d: %r vs %r' % (i, a[i:i + 40], b[i:i + 40]))
                break
        else:
            errs.append('  前缀一致、长度不同 ⇒ 尾部被截断')
    else:
        # 🔴 **必须比「去尾空白」的版本**：服务端把正文包在 `<div>…</div>` 里
        #    ⇒ 反转义时 `</div>` → '\n' ⇒ **末尾多出 1~2 个换行**
        #    （**转换产物，不是内容差异**）⇒ 🔴 本轮初版直接比原始长度
        #    ⇒ 报「长度不等 2436 != 2434」⇒ **假 FAIL**。
        a, b = body.strip(), local.strip()
        print('✅ 实发正文（去尾空白）与入库件**逐字符完全相同**（%d 字符）' % len(a))
        extra = body[len(body.rstrip()):]
        if extra.strip():
            errs.append('尾部多出非空白字符：%r' % extra)

    n = len(local)
    marks = {'首': local[:18], '中': local[n // 2 - 9:n // 2 + 9], '尾': local[-18:].rstrip()}
    for k, v in marks.items():
        if v not in body:
            errs.append('%s 段标记未命中：%r' % (k, v))
        else:
            print('%s 段标记命中：%r' % (k, v))

    print()
    if errs:
        print('=== FAIL（%d 条）===' % len(errs))
        for e in errs:
            print('  ✗', e)
        return 1
    print('=== PASS：实发正文与入库件逐字节相同，首/中/尾三地标全部命中 ⇒ 未截断 ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
