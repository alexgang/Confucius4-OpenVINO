import os
import re

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SRC = os.path.join(REPO, 'results', 'app', '_sec202_body.txt')

t = open(STATUS, encoding='utf-8').read()
pat = re.compile(r'（last_ack=APP-109，2026-11-14 (\d{4}-\d{2}-\d{2} '
                 r'\d{2}:\d{2}:\d{2})）')
m = pat.search(t)
if not m:
    raise RuntimeError('§202 标题里没找到重复日期')
ts = m.group(1)
new_title = '（last_ack=APP-109，%s）' % ts
t2 = t[:m.start()] + new_title + t[m.end():]
if t2.count(new_title) != 1:
    raise RuntimeError('替换后命中 %d 次' % t2.count(new_title))
with open(STATUS, 'w', encoding='utf-8', newline='\n') as f:
    f.write(t2)
b = open(STATUS, 'rb').read()
print('§202 标题已修：%s' % new_title)
print('bytes=%d lines=%d CRLF=%d' % (len(b), b.count(b'\n'),
                                     b.count(b'\r\n')))

# 源文件也修一下（保持与落盘一致）
s = open(SRC, encoding='utf-8').read()
s2 = s.replace('2026-11-14 {{TS}}', '{{TS}}')
if s2 != s:
    with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
        f.write(s2)
    print('源文件 _sec202_body.txt 已同步')
