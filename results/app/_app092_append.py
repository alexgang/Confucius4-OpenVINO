# -*- coding: utf-8 -*-
"""app092 —— 把 §92 章节追加到 STATUS_APP.md（**只追加**，不改旧章节）。

🔴 纪律：
- **只追加**（不回头改旧章节）⇒ 旧结论错了就在新章节里写「撤回 §x」；
- STATUS 是 **LF** 换行 ⇒ 写盘必须 `newline=''`；
- 写后必须验「**原有章节一个不少**」（§53 本来就缺 ⇒ 不能写「§1..§N 全在」）
  ＋「**旧正文逐字未变**」。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SECTION = os.path.join(REPO, 'results', 'app', '_app092_section.md')


def main():
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        old = f.read()
    with open(SECTION, 'r', encoding='utf-8', newline='') as f:
        body = f.read()

    old_sections = re.findall(r'^## §\d+', old, re.M)
    old_sha = hashlib.sha256(old.encode('utf-8')).hexdigest()

    if '\n## §92 ' in old:
        print('❌ §92 已存在 ⇒ 不重复追加')
        return 2

    new = old + body
    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)

    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        after = f.read()
    b = after.encode('utf-8')

    new_sections = re.findall(r'^## §\d+', after, re.M)
    kept = [s for s in old_sections if s in new_sections]
    print('旧章节数 = %d ／ 追加后章节数 = %d' % (len(old_sections),
                                               len(new_sections)))
    print('**原有章节一个不少** = %s' % (len(kept) == len(old_sections)))
    print('新章节 = %s' % new_sections[-1][:20])
    print('**旧正文逐字未变** = %s'
          % after.startswith(old))
    print('CRLF = %d ／ LF-only = %d'
          % (b.count(b'\r\n'), b.count(b'\n') - b.count(b'\r\n')))
    print('字节：%d → %d（+%d）' % (len(old.encode('utf-8')),
                                   len(b), len(b) - len(old.encode('utf-8'))))
    print('旧内容 SHA256（追加前）= %s' % old_sha[:32])
    ok = (len(kept) == len(old_sections) and after.startswith(old)
          and b.count(b'\r\n') == 0 and '## §92 ' in after)
    print()
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
