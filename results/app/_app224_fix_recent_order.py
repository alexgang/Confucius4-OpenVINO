# -*- coding: utf-8 -*-
r"""_app224_fix_recent_order.py —— 把「最近更新」里 §128 那行**移到列表最前**。

🔴 约定：**最新的在最前** ⇒ §128（03:16）必须排在 §127（02:00）之前。
🔴 bytes 级定点替换 ⇒ 行尾（纯 LF）不受影响；写后复核。
"""
from __future__ import annotations

import os
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'


def main():
    with open(STATUS, 'rb') as f:
        data = f.read()
    lines = data.split(b'\n')
    idx = [i for i, l in enumerate(lines)
           if l.startswith(b'- 2026-11-02 03:16 **\xc2\xa7128**')]
    if not idx:
        print('ℹ §128 行不在「最近更新」列表里（可能已被移到别处）⇒ 无需调整')
        return 0
    i = idx[0]
    row = lines.pop(i)
    # 找到「最近更新」标题行
    hdr = [j for j, l in enumerate(lines) if l == b'## \xe6\x9c\x80\xe8\xbf\x91\xe6\x9b\xb4\xe6\x96\xb0']
    if not hdr:
        print('❌ 找不到「## 最近更新」标题')
        return 1
    j = hdr[0] + 1
    lines.insert(j, row)
    new = b'\n'.join(lines)
    tmp = STATUS + '.tmp_app224b'
    with open(tmp, 'wb') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)
    with open(STATUS, 'rb') as f:
        after = f.read()
    print('字节 %d → %d ｜ CRLF %d ｜ 行数 %d'
          % (len(data), len(after), after.count(b'\r\n'),
             len(after.splitlines())))
    k = after.index(b'## \xe6\x9c\x80\xe8\xbf\x91\xe6\x9b\xb4\xe6\x96\xb0')
    print(after[k:k + 300].decode('utf-8'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
