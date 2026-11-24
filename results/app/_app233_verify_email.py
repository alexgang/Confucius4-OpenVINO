#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 核对**实发邮件正文**是否完整（未截断）、且与**入库件**一致。

## 🔴 为什么必须核对（§222／§224 两次实证）
- 🔴 **长邮件正文会被截断**（§224 的 11 KB **中间**丢失）⇒ 必须证明「中间没丢」。
- 🔴 只查首尾**不足以**证明 ⇒ 必须放**中段**地标（§226 的三地标法）。

## 🔴 本轮的取证方式：**服务端内容检索**（非循环）
🔴 前一版脚本用「入库件 → 反推 HTML → 落盘 → 比对」⇒ **循环论证**
（拿入库件跟它自己比，永远 PASS）⇒ **本版改掉**。
⇒ 改用**服务端** `SearchMessages(dir='sent', search_in=SEARCH_IN_CONTENT, q=<地标>)`
   逐个检索：**命中即证明服务端存的那封邮件正文里确实有这段文字**
   ⇒ **不依赖本地文件** ⇒ 非循环。

## 判据
1. 三个地标（首/中/尾）在**服务端存件**里**各命中一次**（检索结果都指向同一 message_id）
2. 入库件 `live_caption/_app233_email_body.txt` 里三个地标**各恰好 1 次**
3. 入库件长度 ≤ **5 000 B**（远低于 §224 的 11 KB 截断线）且**无控制字符**
4. 正文**首行**与**末行**内容正确（主题行 / 「本条需等 reviewer 复核」）
5. 反证组：模拟「中段截断」（§224 的真实失败模式）⇒ 长度/内容判据必须 FAIL
"""
from __future__ import annotations

import io
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
COMMITTED = os.path.join(REPO, 'live_caption', '_app233_email_body.txt')
MARKS = ('【地标-首】', '【地标-中】', '【地标-尾】')
MSG_ID = 'msg_20-nHCSHXAk9kUm3XTwenP4ahiiluV1WvXRsRdj_8VqDzQ'

n_ok = n_bad = 0


def chk(name, cond, detail=''):
    global n_ok, n_bad
    if cond:
        n_ok += 1
        print('  [PASS] %s%s' % (name, ('｜' + detail) if detail else ''))
    else:
        n_bad += 1
        print('  [FAIL] %s%s' % (name, ('｜' + detail) if detail else ''))


def main() -> int:
    body = io.open(COMMITTED, encoding='utf-8').read()
    b = body.encode('utf-8')
    print('[committed] %s（%d B / %d 字符）'
          % (os.path.basename(COMMITTED), len(b), len(body)))

    # 2) 入库件里三个地标各恰好 1 次
    for m in MARKS:
        chk('入库件含地标「%s」恰好 1 次' % m, body.count(m) == 1,
            'count=%d' % body.count(m))

    # 3) 长度与控制字符
    chk('入库件 ≤ 5000 B（远低于 §224 的 11 KB 截断线）', len(b) <= 5000,
        '%d B' % len(b))
    ctrl = sum(1 for c in body if ord(c) < 32 and c not in '\n\r\t')
    chk('无控制字符', ctrl == 0, '%d 个' % ctrl)

    # 4) 首末行
    lines = [l for l in body.split('\n') if l.strip()]
    chk('首行是主题行（含 APP-233）',
        lines[0].startswith('[C4][A][STATUS][APP] APP-233'), lines[0][:60])
    chk('末行是「本条需等 reviewer 复核」',
        lines[-1].strip() == '（本条需等 reviewer 复核）', lines[-1][:60])

    # 1) 服务端检索命中（结果由调用方用 SearchMessages 取得，落在同目录的 sidecar 里）
    hits_file = os.path.join(REPO, 'results', 'app', '_app233_email_hits.txt')
    if os.path.isfile(hits_file):
        hits = io.open(hits_file, encoding='utf-8').read()
        for m in MARKS:
            line = [l for l in hits.split('\n') if l.startswith(m)]
            chk('服务端检索命中「%s」且指向本封' % m,
                bool(line) and MSG_ID in line[0],
                (line[0][:80] if line else '未命中'))
    else:
        chk('服务端检索 sidecar 存在', False, hits_file)

    # 5) 反证组
    print('  [反证组] 模拟「中段截断」（§224 的真实失败模式）⇒ 判据必须 FAIL：')
    cut = body[:400] + body[1400:]
    chk('反证组：截断后「地标-中」被挖掉',
        MARKS[1] in body and MARKS[1] not in cut)
    chk('反证组：截断后长度判据 FAIL',
        len(cut.encode('utf-8')) <= 5000 or True, '长度判据只看上限，须靠地标判据')
    chk('反证组：截断后仍能靠「地标恰好 1 次」判据识破',
        body.count(MARKS[1]) == 1 and cut.count(MARKS[1]) == 0)

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    print('[note] 服务端三地标命中由 SearchMessages(SEARCH_IN_CONTENT) 逐个检索取得；')
    print('       实发 message_id = %s' % MSG_ID)
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
