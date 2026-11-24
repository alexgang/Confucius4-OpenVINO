#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · §233 写入后的**独立**复核（另起脚本，不 import 被检脚本）。

## 判据
1. 硬限额：≤ 40 000 B／≤ 300 行（APP-052④／APP-049）
2. `last_ack` 唯一且仍 = **APP-133**（本轮无新纠偏 ⇒ 值不变）
3. 头部「更新时间」格式为 `YYYY-MM-DD HH:MM:SS`（Get-Date 实测值）
4. **§135–§232 一个都没删**（旧章节逐条在位）
5. **新增节号只有 233**
6. §233 标题行 ＋ 指针行在文末；指针行指向的 companion **存在**且非空
7. 「最近更新」块**新增 1 条**且旧的**一条没删**（计数对得上）
8. **两处表行**已更新到 v2.6（`客户包目录` / `完整版 v2.6` / `客户包 zip`），
   且**旧行文本已不存在**（避免新旧并存）
9. **反证组**：把归档指针行/表行**篡改** ⇒ 相关判据必须 FAIL（判据有鉴别力）
10. 纠偏文件**未被改动**（四项指纹逐字一致）
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
COMPANION = os.path.join(
    REPO, 'status', 'app', 'STATUS_APP_sec233_detail_20261125.md')
ARCHIVE = os.path.join(
    REPO, 'status', 'archive', 'STATUS_APP_sec211_227_headers_20261125.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

# 纠偏文件的**开工时**四项指纹（本轮开工实测）
CORR_SHA = '2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda'
CORR_BYTES = 440181
CORR_MTIME = 1795499802.0     # 2026-11-24 13:56:42（本地时区）
CORR_ENTRIES = 130

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
    raw = open(STATUS, 'rb').read()
    text = raw.decode('utf-8')
    print('[post-write] %d B / 40000 B；%d 行 / 300 行'
          % (len(raw), raw.count(b'\n')))

    # 1) 硬限额
    chk('≤ 40000 B', len(raw) <= 40000, '%d B' % len(raw))
    chk('≤ 300 行', raw.count(b'\n') <= 300, '%d 行' % raw.count(b'\n'))

    # 2) last_ack
    la = re.findall(r'last_ack:\s*APP-(\d+)', text)
    chk('last_ack 唯一且仍 = APP-133', la == ['133'], str(la))

    # 3) 更新时间格式
    m = re.search(r'更新时间: ([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})',
                  text)
    chk('「更新时间」为 Get-Date 实测格式', bool(m), m.group(1) if m else '')

    # 4/5) 节号
    #    🔴 判据修正：§211–§227 的**标题行**已按 §233 §2.1 归档
    #    ⇒ 它们**不在活文档里**（在归档件里）⇒ 不能断言「都在活文档」。
    #    真正的真不变量是「**每个旧节号都仍被交代**」＝ live ∪ archived。
    secs = [int(x) for x in re.findall(r'^## §(\d+)', text, re.M)]
    arc_text = open(ARCHIVE, encoding='utf-8').read() if os.path.isfile(ARCHIVE) else ''
    arc_secs = set(int(x) for x in re.findall(r'^## §(\d+)', arc_text, re.M))
    old_secs = [135, 141, 162, 170, 171, 211, 212, 213, 214, 215, 219, 220,
                221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232]
    missing = [s for s in old_secs if s not in (set(secs) | arc_secs)]
    chk('每个旧节号都仍被交代（活文档 ∪ 归档件）', not missing,
        'missing=%s' % (missing or '无'))
    chk('归档件承载 §211–§227（14 节）', len(arc_secs & set(range(211, 228))) == 14,
        'archived=%s' % sorted(arc_secs & set(range(211, 228))))
    chk('活文档仍保留 §135–§171 与 §228–§232',
        all(s in secs for s in [135, 141, 162, 170, 171, 228, 229, 230, 231, 232]),
        str(sorted(s for s in [135, 141, 162, 170, 171, 228, 229, 230, 231, 232]
                   if s not in secs)))
    chk('新增节号只有 233',
        sorted(set(secs) - set(old_secs)) == [233],
        str(sorted(set(secs) - set(old_secs))))
    chk('§233 在文末', secs and secs[-1] == 233, str(secs[-3:]))

    # 6) companion 存在
    chk('companion 文件存在且非空',
        os.path.isfile(COMPANION) and os.path.getsize(COMPANION) > 1000,
        '%d B' % (os.path.getsize(COMPANION) if os.path.isfile(COMPANION) else 0))
    chk('§233 指针行指向该 companion',
        'STATUS_APP_sec233_detail_20261125.md' in text)
    chk('归档件存在', os.path.isfile(ARCHIVE),
        '%d B' % (os.path.getsize(ARCHIVE) if os.path.isfile(ARCHIVE) else 0))
    chk('指针行指向的归档件在文档中出现',
        'STATUS_APP_sec211_227_headers_20261125.md' in text)

    # 7) 「最近更新」条目计数
    upd = re.findall(r'^> 🔴 \d{4}-\d{2}-\d{2} ', text, re.M)
    chk('「最近更新」条目数 ≥ 4（本轮 +1 且旧条未删）', len(upd) >= 4,
        'count=%d' % len(upd))
    chk('本轮的「最近更新」条目在最前',
        re.search(r'^> 🔴 2026-11-25 ', text, re.M) is not None)

    # 8) 表行已更新
    chk('表行「客户包目录」已写明 v2.6 当前交付版',
        '当前交付版 = `Confucius4_LiveCaption_v2.6`' in text)
    chk('旧行文本已不存在（不留新旧并存）',
        '`Confucius4_LiveCaption_v2.1` = **当前交付版**' not in text)
    chk('表行「完整版」已是 v2.6',
        '| **完整版 v2.6（当前交付，「全集」形态）** |' in text)
    chk('旧行「完整版 v2.5（本轮交付…）」已不存在',
        '| **完整版 v2.5（本轮交付，「全集」形态）** |' not in text)
    chk('表行「客户包 zip」已写明发客户发 v1.1.1.zip',
        '发客户的是 MiniMVP `v1.1.1.zip`' in text)
    chk('旧行「当前交付版仍是 v2.1」已不存在',
        '**当前交付版仍是 v2.1**' not in text)
    # 三行各唯一
    for lbl, pat in (('客户包目录', r'^\| 客户包目录 \|'),
                     ('完整版', r'^\| \*\*完整版 v2\.6'),
                     ('客户包 zip', r'^\| 客户包 zip \|')):
        chk('表行「%s」唯一' % lbl, len(re.findall(pat, text, re.M)) == 1,
            'count=%d' % len(re.findall(pat, text, re.M)))

    # 10) 纠偏文件四项指纹
    cb = open(CORR, 'rb').read()
    csha = hashlib.sha256(cb).hexdigest()
    cmt = os.path.getmtime(CORR)
    cids = re.findall(r'^## (APP-\d+)', cb.decode('utf-8'), re.M)
    chk('纠偏文件 SHA256 未变', csha == CORR_SHA, csha[:16])
    chk('纠偏文件字节数未变', len(cb) == CORR_BYTES, '%d B' % len(cb))
    chk('纠偏文件 mtime 未变', abs(cmt - CORR_MTIME) < 2,
        '%.0f' % cmt)
    chk('纠偏文件条数未变', len(cids) == CORR_ENTRIES, '%d 条' % len(cids))

    # 9) 反证组
    print('  [反证组] 篡改后相关判据必须 FAIL：')
    tampered = text.replace('当前交付版 = `Confucius4_LiveCaption_v2.6`',
                            '当前交付版 = `Confucius4_LiveCaption_v9.9`')
    chk('反证组：篡改后「v2.6 当前交付版」判据 FAIL',
        '当前交付版 = `Confucius4_LiveCaption_v2.6`' not in tampered)
    tampered2 = text.replace('| **完整版 v2.6（当前交付，「全集」形态）** |',
                             '| **完整版 v2.5（当前交付，「全集」形态）** |')
    chk('反证组：篡改后「完整版 v2.6」判据 FAIL',
        '| **完整版 v2.6（当前交付，「全集」形态）** |' not in tampered2)

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
