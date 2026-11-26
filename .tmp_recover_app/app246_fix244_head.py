"""修 §244：把被整行替换掉的原标题恢复成「## §244 …」标题行 + 指针行。

原 §244 是**标题与正文同一行**（3742 B），上一脚本整行换成了 blockquote 指针 ⇒
标题丢失。这里从归档文件取原标题（`｜` 之前的部分）补回。
不变量：归档文件里原文逐字仍在；只改这一处；CRLF 计数不变。
"""
import io
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARC = os.path.join(REPO, 'status', 'archive',
                   'STATUS_APP_sec244_headline_20261126.md')
MARK = '> 🔴 **本节原正文（一整行'.encode('utf-8')


def main():
    raw = open(P, 'rb').read()
    lines = raw.split(b'\n')
    hit = [i for i, l in enumerate(lines) if l.startswith(MARK)]
    print('pointer line hits =', hit)
    if len(hit) != 1:
        return 2
    i = hit[0]
    if i > 0 and lines[i - 1].startswith(b'## \xc2\xa7244'):
        print('SKIP: 标题已存在')
        return 0

    arc = open(ARC, 'rb').read().decode('utf-8')
    old = [l for l in arc.split('\n') if l.startswith('## §244')]
    if len(old) != 1:
        print('FAIL: 归档里没找到 §244 原标题行')
        return 3
    head = old[0].split('｜')[0].strip()
    assert head.startswith('## §244'), head[:30]

    eol = b'\r' if lines[i].endswith(b'\r') else b''
    crlf0 = raw.count(b'\r\n')
    new_head = head.encode('utf-8') + eol
    lines.insert(i, new_head)
    out = b'\n'.join(lines)

    checks = [
        ('标题行已插入', ('## §244 ').encode('utf-8') in out),
        ('CRLF 计数', out.count(b'\r\n') == crlf0 + (1 if eol else 0)),
        ('体积 ≤ 40000', len(out) <= 40000),
        ('归档原文仍在', old[0] in arc),
    ]
    for n, ok in checks:
        print('%-14s %s' % (n, 'OK' if ok else 'FAIL'))
    if not all(ok for _, ok in checks):
        return 4
    open(P, 'wb').write(out)
    print('WROTE bytes=%d lines=%d' % (len(out), out.decode('utf-8').count('\n') + 1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
