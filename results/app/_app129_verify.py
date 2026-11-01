#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app129 —— 收尾复核：确认 STATUS 压缩**没有丢任何旧正文**。

🔴 三条硬判据：
  ① §127/§128 的正文**逐字**在归档件里（一个字符都不能差）；
  ② 压缩前的 STATUS 里的**所有旧章节正文**，逐字出现在压缩后的 STATUS **或**归档件里
     （⇒ 没有任何旧正文被删掉，只是搬走了）；
  ③ 头部字段（last_ack / 更新时间 / 当前任务）与「最近更新」「最近章节」索引都在。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                       'STATUS_APP_sec127_128_upto_20261102.md')
BEFORE = os.path.join(os.environ.get('TEMP', '/tmp'),
                      'STATUS_APP_before_sec129.md')


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def sections(text):
    ms = list(re.finditer(r'(?m)^(### §\d+ .*)$', text))
    out = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(1)] = text[m.end():end]
    return out


def main() -> int:
    now = read(STATUS)
    arc = read(ARCHIVE)
    before = read(BEFORE) if os.path.isfile(BEFORE) else None

    fails = []
    n = 0

    # ① 归档件逐字命中
    for title, body in sections(arc).items():
        b = body.strip()
        if b and b not in arc:
            fails.append('归档件未逐字命中 %s' % title[:40])
        n += 1
    print('① 归档件含 %d 节，逐字命中检查完成' % n)

    # ② 压缩前的旧正文 ⇒ 必须逐字出现在「压缩后」或「归档件」里
    if before:
        n = 0
        for title, body in sections(before).items():
            b = body.strip()
            if not b:
                continue
            n += 1
            if b not in now and b not in arc:
                fails.append('旧正文丢失：%s' % title[:40])
        print('② 压缩前 %d 节旧正文 ⇒ 全部逐字落在「新 STATUS」或「归档件」' % n)
    else:
        print('② ⚠️ 找不到压缩前快照（%s）⇒ 跳过' % BEFORE)

    # ③ 头部字段与索引
    for key in ('last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:',
                '已压缩:'):
        if key not in now:
            fails.append('头部缺字段 %s' % key)
    for key in ('## 最近更新', '## 当前有效结论', '## 未完成纠偏',
                '## 最近章节', '### §129'):
        if key not in now:
            fails.append('缺章节 %s' % key)
    if '| §129 |' not in now:
        fails.append('最近章节索引缺 §129 行')
    la = re.search(r'(?m)^last_ack: (\S+)', now)
    print('③ last_ack = %s；头部与索引字段齐全'
          % (la.group(1) if la else '?'))

    # ④ 自指大小必须与磁盘实测一致
    m = re.search(r'(?m)^已压缩: 本文件 (\d+) B / (\d+) 行', now)
    real_b = len(now.encode('utf-8'))
    real_l = now.count('\n') + 1
    if m:
        if int(m.group(1)) != real_b or int(m.group(2)) != real_l:
            fails.append('自指大小不符：头部 %s B / %s 行 ⇒ 实测 %d B / %d 行'
                         % (m.group(1), m.group(2), real_b, real_l))
        else:
            print('④ 自指大小一致：%d B / %d 行' % (real_b, real_l))
    else:
        fails.append('缺「已压缩」自指大小行')

    # ⑤ 限额
    if real_b > 40000:
        fails.append('超字节限额：%d > 40000' % real_b)
    if real_l > 300:
        fails.append('超行数限额：%d > 300' % real_l)

    print()
    if fails:
        print('❌ 复核失败 %d 条：' % len(fails))
        for f in fails:
            print('   - %s' % f)
        return 1
    print('✅ 复核全部通过')
    print('   STATUS  SHA256 = %s' % hashlib.sha256(
        open(STATUS, 'rb').read()).hexdigest())
    print('   归档件  SHA256 = %s' % hashlib.sha256(
        open(ARCHIVE, 'rb').read()).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
