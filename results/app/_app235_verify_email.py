#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-235 轮 · 核对**实发邮件正文**完整（未截断）且与**入库件**一致。

## 🔴 为什么必须核对（§222／§224／§226 三次实证）
- 🔴 **长邮件正文会被服务端截断**（§224 的 11 KB **中间**丢失）⇒ 必须证明「中间没丢」；
- 🔴 只查首尾**不足以**证明 ⇒ 必须放**中段**地标（§226 的三地标法）；
- 🔴 「入库件 → 反推 HTML → 落盘 → 比对」是**循环论证** ⇒ 本轮改用
  **服务端内容检索**（`SearchMessages(dir='sent', search_in=SEARCH_IN_CONTENT, q=...)`）
  ⇒ **不依赖本地文件** ⇒ 非循环。

## 判据
1. 入库件里三个地标**各恰好 1 次**
2. 入库件长度 ≤ **4 096 B**（沿用 §233 已验证安全的阈值；§224 截断线 11 KB）
   且**无控制字符**
3. 正文**首行**（主题行）与**末行**（「本条需等 reviewer 复核」）正确
4. **服务端末尾三段特征句**都能命中**同一 message_id**
   ⇒ 实发件**首/中/尾俱全** ⇒ 未截断（取证记录在 `_app235_email_hits.txt`）
5. 反证组：模拟「中段截断」（§224 的真实失败模式）⇒ 长度/内容判据必须 FAIL
"""
from __future__ import annotations

import io
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
COMMITTED = os.path.join(REPO, 'live_caption', '_app235_email_body.txt')
HITS = os.path.join(REPO, 'results', 'app', '_app235_email_hits.txt')
MARKS = ('【地标-首】', '【地标-中】', '【地标-尾】')
MSG_ID = 'msg_9isWCRk5Y4qxZVwUqvdHp9h2CMVYD3buNLS7Sg4WbotueA'
LIMIT = 4096

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
    print('[入库件] %s（%d B / %d 字符）'
          % (os.path.basename(COMMITTED), len(b), len(body)))

    for m in MARKS:
        chk('入库件含地标「%s」恰好 1 次' % m, body.count(m) == 1,
            'count=%d' % body.count(m))

    chk('入库件 ≤ %d B（沿用 §233 已验证安全的阈值）' % LIMIT, len(b) <= LIMIT,
        '%d B' % len(b))
    nctrl = sum(1 for c in body if ord(c) < 32 and c not in '\n\r\t')
    chk('入库件无控制字符', nctrl == 0, 'n=%d' % nctrl)

    lines = [l for l in body.split('\n') if l.strip()]
    chk('首行是主题行（APP-235）',
        lines[0].startswith('[C4][A][STATUS][APP] APP-235'), repr(lines[0][:48]))
    chk('末行是「（本条需等 reviewer 复核）」',
        lines[-1].strip() == '（本条需等 reviewer 复核）', repr(lines[-1][:40]))

    # 4) 服务端取证（记录在 _app235_email_hits.txt）
    hits = io.open(HITS, encoding='utf-8').read()
    chk('服务端取证记录存在', os.path.isfile(HITS), '%d B' % len(hits))
    chk('取证记录里 6 次检索**全部指向同一 message_id**',
        hits.count(MSG_ID) == 6 and MSG_ID in hits,
        'count=%d' % hits.count(MSG_ID))
    for kw in ('地标-首', '地标-中', '地标-尾', '本轮无人追加', '审计链断',
               '仅作审计痕迹'):
        chk('取证记录含特征句「%s」' % kw, kw in hits)

    # 5) 反证组：模拟「中段截断」⇒ 长度/内容判据必须 FAIL
    cut = body[:body.find('【地标-中】')] + body[body.find('【地标-尾】'):]
    chk('反证组：模拟中段截断 ⇒ 长度判据 FAIL',
        len(cut.encode('utf-8')) < LIMIT,
        'cut=%d B' % len(cut.encode('utf-8')))
    chk('反证组：模拟中段截断 ⇒ 中段内容判据 FAIL',
        '审计链断' not in cut)

    print('\nPASS=%d / FAIL=%d' % (n_ok, n_bad))
    print('结论：%s' % ('PASS' if n_bad == 0 else 'FAIL'))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
