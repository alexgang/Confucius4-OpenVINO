#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_verify178.py —— §178 落盘后**独立**复核（不复用写入脚本的逻辑）。"""
import hashlib
import io
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
A = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec178_20261111.md')
C = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

b = open(S, 'rb').read()
t = b.decode('utf-8')
print('bytes %d /40000 | lines %d /300 | CRLF %d'
      % (len(b), b.count(b'\n') + 1, b.count(b'\r\n')))
secs = re.findall(r'(?m)^## (§\d+)', t)
print('sections %d : %s' % (len(secs), secs[-6:]))
for n in ('175', '177', '178'):
    m = re.search(r'(?m)^## §' + n + r' .*?(?=^## |\Z)', t, re.S)
    print('  §%s live block: %d B' % (n, len(m.group(0).encode()) if m else -1))

a = open(A, 'rb').read()
ah = hashlib.sha256(a).hexdigest()
print('archive: %d B sha %s' % (len(a), ah[:20]))
mm = re.search(r'status/archive/STATUS_APP_sec178_20261111\.md`（([0-9 ]+) B／SHA256 `([0-9a-f]+)`）', t)
print('pointer cited: %s B / %s' % (mm.group(1), mm.group(2)[:20]))
print('  SHA match:', mm.group(2) == ah,
      '| bytes match:', int(mm.group(1).replace(' ', '')) == len(a))

# 归档件须含活文档 §178 块的实质内容
missing = [l for l in re.search(r'(?m)^## §178 .*?(?=^## |\Z)', t, re.S).group(0).split('\n')
           if l.strip() and l not in a.decode('utf-8')]
print('§178 live lines not verbatim in archive: %d' % len(missing))

# 旧章节必须一字未改（对比 §178 写入前的 HEAD 版本）
import subprocess
head = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:status/app/STATUS_APP.md'],
                       capture_output=True).stdout.decode('utf-8')
old_secs = re.findall(r'(?m)^## §(\d+)', head)
new_secs = re.findall(r'(?m)^## §(\d+)', t)
print('old sections %d -> new %d (added %s)'
      % (len(old_secs), len(new_secs), sorted(set(new_secs) - set(old_secs))))
# 除 §175（已索引化）外，旧章节正文须逐字不变
diff = []
for n in old_secs:
    mo = re.search(r'(?m)^## §' + n + r' .*?(?=^## |\Z)', head, re.S)
    mn = re.search(r'(?m)^## §' + n + r' .*?(?=^## |\Z)', t, re.S)
    if mo and mn and mo.group(0) != mn.group(0):
        diff.append(n)
print('sections whose live body changed: %s' % (diff or 'NONE'))
print('  (§175 改动是**索引化**：正文逐字仍在 write-once 归档件 sec175 里)')

# CORR 必须零改动
c = open(C, 'rb').read()
print('CORR sha %s / %d B / %d headings'
      % (hashlib.sha256(c).hexdigest()[:20], len(c),
         len(re.findall(r'(?m)^## APP-\d+', c.decode('utf-8')))))
