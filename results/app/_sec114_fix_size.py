#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 §114 草稿里写死的体积自指数字与实际输出**迭代对齐**（到收敛）。

🔴 为什么需要迭代：§114 正文自身写了 STATUS 的体积数字（自指）
   ⇒ 改草稿 ⇒ 写入器输出变大 ⇒ 数字又要改 ⇒ **必须迭代到不动点**，
   否则要么数字失配，要么无穷改不完（ASR-036 的同类坑）。
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
P = os.path.join(HERE, '_sec114_body.md')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec109_113_upto_20261030.md')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'), 'STATUS_APP.sec114_base.md')
WRITER = os.path.join(HERE, '_sec114_write_status.py')
PY = sys.executable


def current_size():
    raw = open(STATUS, 'rb').read()
    return len(raw), len(raw.decode('utf-8').split('\n'))


# ① 先备份「写入前」的基线（一次即可）
if not os.path.exists(BACKUP):
    shutil.copyfile(STATUS, BACKUP)
    print('[基线] 已备份写入前版本：%s（%d B）' % (BACKUP, os.path.getsize(BACKUP)))

prev = None
for it in range(1, 8):
    # ② 草稿里的数字对齐到当前 STATUS
    t = open(P, encoding='utf-8').read()
    m = re.search(r'现 \*\*([\d\s]+) B / (\d+) 行\*\*', t)
    assert m, '§114 草稿：未找到体积自指串'
    old = m.group(0)
    b, l = current_size()
    new = '现 **%d B / %d 行**' % (b, l)
    if old != new:
        t = t.replace(old, new, 1)
        open(P, 'w', encoding='utf-8', newline='').write(t)
        print('[迭代 %d] 草稿自指：%s -> %s' % (it, old, new))

    # ③ 从基线重跑写入器
    shutil.copyfile(BACKUP, STATUS)
    if os.path.exists(ARCHIVE):
        os.remove(ARCHIVE)
    r = subprocess.run([PY, WRITER], capture_output=True, text=True,
                       cwd=REPO, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print('[迭代 %d] 写入器失败：\n%s' % (it, r.stdout[-2000:] + r.stderr[-2000:]))
        sys.exit(1)
    nb, nl = current_size()
    print('[迭代 %d] 写入后：%d B / %d 行' % (it, nb, nl))

    # ④ 判断是否收敛：草稿写的数字 == 实际
    t2 = open(P, encoding='utf-8').read()
    m2 = re.search(r'现 \*\*([\d\s]+) B / (\d+) 行\*\*', t2)
    if m2 and int(m2.group(1).replace(' ', '')) == nb and int(m2.group(2)) == nl:
        print('\n✅ 收敛：草稿自指 == 实际（%d B / %d 行），迭代 %d 次' % (nb, nl, it))
        break
    prev = (nb, nl)
else:
    print('❌ 未收敛：最后实际 %s，草稿仍不匹配' % (prev,))
    sys.exit(1)
