#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app562_verify_status_sec204.py —— **独立复核** §204 的落盘结果。

刻意**不复用**写者脚本的任何逻辑：基线取自 `git cat-file blob HEAD:status/app/
STATUS_APP.md`（提交前的版本），逐项比对：
  ① §203 正文块：归档件里与 HEAD 里的**逐字节相同**；
  ② 归档件声明的块 SHA256 与实测一致；
  ③ 活文档里 §203 ＝ **标题行 ＋ 1 行指针**（正文已不在）；
  ④ §204 是最后一节；
  ⑤ 头部「更新时间」已更新、`last_ack` **仍是 APP-109**；
  ⑥ 「最近更新」新条目在标题之后第一行；
  ⑦ 除**授权改动**（头部时间戳行 ＋ 新插入行 ＋ §203 正文→指针 ＋ 新增 §204）外，
     **旧正文零丢失**（按「逐行做还原式比对」判定，不按行号）。
"""
import hashlib
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec203_20261114.md')

head = subprocess.run(['git', '-C', REPO, 'cat-file', 'blob',
                       'HEAD:status/app/STATUS_APP.md'],
                      capture_output=True).stdout.decode('utf-8')
now = open(STATUS, encoding='utf-8').read()
arch = open(ARCHIVE, encoding='utf-8').read()

checks = []


def chk(name, cond, extra=''):
    checks.append((name, bool(cond), extra))


# ① §203 正文块逐字节相同
i203 = head.index('## §203 ')
sec203_head = head[i203:].rstrip('\n')
chk('① §203 正文块：归档件 == HEAD 原文（逐字节）',
    sec203_head in arch, 'HEAD 块 %d B' % len(sec203_head.encode('utf-8')))
chk('①b 归档件里 §203 正文块只出现 1 次',
    arch.count(sec203_head) == 1, '出现 %d 次' % arch.count(sec203_head))

# ② 归档件声明的 SHA 与实测一致
m = re.search(r'§203 正文块 SHA256（含标题行）：([0-9a-f]{64})（(\d+) B）', arch)
chk('② 归档件声明了块 SHA256', m is not None)
if m:
    actual = hashlib.sha256(sec203_head.encode('utf-8')).hexdigest()
    chk('②b 声明的块 SHA256 == 实测', m.group(1) == actual,
        '声明 %s… / 实测 %s…' % (m.group(1)[:12], actual[:12]))
    chk('②c 声明的块字节数 == 实测', int(m.group(2)) == len(sec203_head.encode('utf-8')),
        '声明 %s / 实测 %d' % (m.group(2), len(sec203_head.encode('utf-8'))))

# ③ 活文档里 §203 = 标题 + 1 行指针
i_now = now.index('## §203 ')
sec203_now = now[i_now:now.index('## §204 ')]
lines203 = [l for l in sec203_now.split('\n') if l.strip()]
chk('③ 活文档 §203 只剩标题行 ＋ 1 行指针', len(lines203) == 2,
    '实到 %d 行' % len(lines203))
chk('③b 指针行指向归档件',
    len(lines203) == 2 and 'STATUS_APP_sec203_20261114.md' in lines203[1])

# ④ §204 是最后一节
tail = now.rstrip('\n')
chk('④ §204 是最后一节', tail.rindex('## §204 ') > tail.rindex('## §203 '))
chk('④b §204 标题行唯一', now.count('## §204 ') == 1)

# ⑤ 头部
head_ts = [l for l in head.split('\n') if l.startswith('更新时间: ')][0]
now_ts = [l for l in now.split('\n') if l.startswith('更新时间: ')]
chk('⑤ 头部「更新时间」行唯一且已更新',
    len(now_ts) == 1 and now_ts[0] != head_ts,
    '%r ⇒ %r' % (head_ts, now_ts[0] if now_ts else None))
chk('⑤b last_ack 仍 APP-109（无新纠偏 ⇒ 不改）',
    [l for l in now.split('\n') if l.startswith('last_ack:')] == ['last_ack: APP-109'])

# ⑥ 最近更新新条目在标题之后第一行
ru = '## 最近更新\n'
after = now.split(ru)[1].split('\n')
chk('⑥ 「最近更新」标题唯一', now.count(ru) == 1)
chk('⑥b 新条目在标题之后第一行',
    after[0].startswith('> 🔴 2026-11-14 19:38:17'), after[0][:60])
chk('⑥c 新条目在本节最后一条之前',
    after[0].startswith('> 🔴') and after[1].startswith('> 🔴'),
    '第 2 行 %r' % after[1][:50])

# ⑦ 旧正文零丢失：把本轮增量逆向还原后与 HEAD 逐字节比对
# ⚠️ 切点必须是「\n\n## §204 」（连分隔符一起切）—— 只切到 '## §204 ' 会多留
#    一个换行 ⇒ 还原后比 HEAD 多 1 B ⇒ 假 FAIL（本复核脚本首版就踩了这个）。
cut = now.rindex('\n\n## §204 ')
rest = now[:cut] + '\n'
rest = rest.replace(lines203[0] + '\n\n' + lines203[1] + '\n',
                    sec203_head + '\n')
rest = rest.replace(after[0] + '\n', '', 1)
rest = rest.replace(now_ts[0], head_ts)
chk('⑦ 逆向还原后与 HEAD 逐字节相同（旧正文零丢失）',
    rest == head, '还原 %d B vs HEAD %d B'
    % (len(rest.encode('utf-8')), len(head.encode('utf-8'))))

# ⑧ 结构上限
nb = open(STATUS, 'rb').read()
chk('⑧ 字节上限 40 000 B', len(nb) <= 40000, '%d B' % len(nb))
chk('⑧b 行数上限 300 行', nb.count(b'\n') <= 300, '%d 行' % nb.count(b'\n'))
chk('⑧c 纯 LF、无 BOM', b'\r' not in nb and nb[:3] != b'\xef\xbb\xbf')

ok = all(c[1] for c in checks)
for n, g, e in checks:
    print(('  [OK] ' if g else '  [FAIL] ') + n + (('  ' + e) if e else ''))
print('\n独立复核 verdict =', 'PASS' if ok else 'FAIL')
print('STATUS bytes %d / lines %d / sha %s'
      % (len(nb), nb.count(b'\n'), hashlib.sha256(nb).hexdigest()))
raise SystemExit(0 if ok else 1)
