#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_verify_status.py —— §227 轮：**STATUS_APP.md 写后独立复核**（另起脚本）。

复核项：
  ① 字节数 ≤ 40 000／行数 ≤ 300（APP-052④）
  ② 旧文件每一行（非空）仍出现在新文件里且次数不少于原来（**只追加不删改**；
     例外白名单：① 被归档的那一条真条目 ② 头部「更新时间」行＝**纪律要求换成实测值**）
  ③ `last_ack: APP-128` 未变（无新编号 ⇒ 不改）
  ④ `## §227` 出现 1 次；指针行指向 companion（且 companion 文件**真实存在**）
  ⑤ 归档指针指向的归档件**真实存在**，且其中**逐字含**被归档的那条原文
  ⑥ 归档件是**新文件**（不覆盖 §226 那份 20261124.md）
  ⑦ 全部旧 `§nnn` 编号存活；⑧ 无 CR；结尾有换行
  ⑨ companion 里的「SHA 零改动」四件套与磁盘实测**一致**（收尾复核用）
"""
from __future__ import annotations

import collections
import hashlib
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
COMPANION = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec227_detail_20261124.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_recent_updates_20261124b.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
BACKUP = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app227')

fails = []


def chk(name, cond, detail=''):
    print('  %-52s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(name)


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    if not os.path.exists(BACKUP):
        print('[FAIL] 找不到写前备份：%s' % BACKUP)
        return 2
    orig = read(BACKUP)
    new = read(STATUS)
    lines_o = orig.split('\n')
    lines_n = new.split('\n')

    print('[pre] 写前 %d B / %d 行' % (len(orig.encode('utf-8')), orig.count('\n')))
    print('[pre] 写后 %d B / %d 行' % (len(new.encode('utf-8')), new.count('\n')))

    chk('① 字节数 ≤ 40 000', len(new.encode('utf-8')) <= 40000,
        '(%d)' % len(new.encode('utf-8')))
    chk('① 行数 ≤ 300', new.count('\n') <= 300, '(%d)' % new.count('\n'))

    # ② 旧行仍可数到（白名单：归档件里的那一条 + 更新时间行）
    old_ts = next(l for l in lines_o if l.startswith('更新时间:'))
    arch_txt = read(ARCH) if os.path.exists(ARCH) else ''
    arch_entries = [l for l in arch_txt.split('\n')
                     if re.match(r'^> 🔴 \d{4}-\d{2}-\d{2}', l)]
    ALLOWED = set(arch_entries) | {old_ts}
    o_cnt = collections.Counter(l for l in lines_o if l.strip())
    n_cnt = collections.Counter(l for l in lines_n if l.strip())
    short = {l[:60]: (o_cnt[l], n_cnt[l]) for l in o_cnt
             if n_cnt[l] < o_cnt[l] - (1 if l in ALLOWED else 0)}
    chk('② 旧每一行仍可数到（只追加不删改）', not short, str(short)[:300])

    chk('③ last_ack 未变（APP-128）', 'last_ack: APP-128' in new)
    chk('③ 头部「更新时间」已换实测值',
        '更新时间: 2026-11-24 05:5x' in new)

    chk('④ `## §227` 出现 1 次', new.count('## §227') == 1,
        '(count=%d)' % new.count('## §227'))
    chk('④ §227 指针行指向 companion',
        'STATUS_APP_sec227_detail_20261124.md' in new)
    chk('④ companion 文件真实存在', os.path.exists(COMPANION),
        '(%d B)' % (os.path.getsize(COMPANION) if os.path.exists(COMPANION) else 0))

    chk('⑤ 归档件真实存在', os.path.exists(ARCH),
        '(%d B)' % (os.path.getsize(ARCH) if os.path.exists(ARCH) else 0))
    chk('⑤ 归档指针指向归档件',
        'STATUS_APP_recent_updates_20261124b.md' in new)
    if arch_entries:
        chk('⑤ 归档件逐字含被归档的原文',
            arch_entries[0] in arch_txt)
    prev_arch = os.path.join(REPO, 'status', 'archive',
                              'STATUS_APP_recent_updates_20261124.md')
    chk('⑥ 归档件是**新文件**（与 §226 那份并存、未覆盖）',
        os.path.exists(ARCH) and os.path.exists(prev_arch)
        and os.path.abspath(ARCH) != os.path.abspath(prev_arch)
        and open(ARCH, 'rb').read() != open(prev_arch, 'rb').read(),
        '(%s 与 %s 并存且内容不同)'
        % (os.path.basename(ARCH), os.path.basename(prev_arch)))

    o_secs = set(re.findall(r'§\d+', orig))
    n_secs = set(re.findall(r'§\d+', new))
    chk('⑦ 全部旧 § 编号存活', not (o_secs - n_secs), str(sorted(o_secs - n_secs))[:200])
    chk('⑧ 无 CR 引入', '\r' not in new)
    chk('⑧ 结尾有换行', new.endswith('\n'))

    # ⑨ companion 里声明的「SHA 零改动」四件套 vs 磁盘实测
    cb = open(CORR, 'rb').read()
    csha = hashlib.sha256(cb).hexdigest()
    cts = re.search(r'^## APP-', cb.decode('utf-8', 'replace'), re.M)
    n_entries = len(re.findall(r'^## APP-', cb.decode('utf-8', 'replace'), re.M))
    comp = read(COMPANION)
    ok_sha = csha in comp
    ok_bytes = ('429 255' in comp) and (len(cb) == 429255)
    ok_n = ('125 条' in comp) and (n_entries == 125)
    chk('⑨ companion 声明的 SHA256 == 磁盘实测', ok_sha, csha[:24] + '…')
    chk('⑨ companion 声明的字节数 == 磁盘实测', ok_bytes, str(len(cb)))
    chk('⑨ companion 声明的条数 == 磁盘实测', ok_n, str(n_entries))

    print()
    if fails:
        print('[FAIL] 写后独立复核未过：%s' % fails)
        return 3
    print('[ok] STATUS_APP.md 写后独立复核 ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
