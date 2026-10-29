# -*- coding: utf-8 -*-
"""app093 —— 修「最近更新」里的重复行（头部字段块，允许重写；§N 正文一律不动）。

🔴 为什么需要：本轮头部脚本**先失败一次后成功一次** ⇒ 失败那次已写入「13:28 §93」行
   ⇒ 第二次又插入一条 ⇒ **重复**。⇒ 只在「最近更新」块内做**相邻去重**，
   **绝不触碰** `## §N` 正文。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'


def main():
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        s = f.read()

    m = re.search(r'(## 最近更新\n)(.*?)(\n\n## §1 )', s, re.S)
    assert m, '未找到「最近更新」块'
    lines = [l for l in m.group(2).split('\n') if l.strip()]

    before = len(lines)
    dedup = []
    for l in lines:
        if dedup and dedup[-1] == l:
            print('删除重复行：%s' % l[:60])
            continue
        dedup.append(l)

    assert len(dedup) <= 15, '最近更新超过 15 行'

    new_block = '\n'.join(dedup)
    new = s[:m.start(2)] + new_block + s[m.end(2):]

    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)

    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        after = f.read()
    b = after.encode('utf-8')

    m2 = re.search(r'## 最近更新\n(.*?)\n\n## §1 ', after, re.S)
    lines2 = [l for l in m2.group(1).split('\n') if l.strip()]

    # 正文（§1 之后）必须逐字未变
    bak = r'C:\Users\Trekker-PTL\status_app_backup_before_s93_header.md'
    with open(bak, 'r', encoding='utf-8', newline='') as f:
        prev = f.read()
    anchor = '\n## §1 '
    body_same = (after[after.index(anchor):] == prev[prev.index(anchor):])

    print('最近更新行数 = %d（改前 %d）' % (len(lines2), before))
    print('重复行数 = %d' % (before - len(lines2)))
    print('第 1 行 = %s' % lines2[0][:60])
    print('第 2 行 = %s' % lines2[1][:60])
    print('旧正文逐字未变 = %s' % body_same)
    print('CRLF = %d' % b.count(b'\r\n'))
    print('字节 = %d' % len(b))
    print('SHA256 = %s' % hashlib.sha256(b).hexdigest())

    ok = (body_same and b.count(b'\r\n') == 0 and len(lines2) <= 15
          and lines2[0] != lines2[1])
    print()
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
