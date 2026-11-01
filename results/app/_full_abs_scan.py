#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时：对已解压副本做**全量**绝对路径扫描（含第三方运行时 python/ 与 ext/.runtime_deps/），
用来判断「只扫自有代码」这个口径到底漏了什么。"""
import json
import os
import re
import sys
from collections import Counter

ROOT = sys.argv[1] if len(sys.argv) > 1 else r'C:\v20_cleantest_v2\Confucius4_LiveCaption_v2.0'
ABS = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\s"\'<>|]*)')
DEV_DIRS = ('confucius4-openvino', 'live_dub_ext', 'qwen3tts_eval', 'hy_bench',
            'Worktrees')
DEV_USER = 'Trekker-PTL'
SCAN_EXT = ('.py', '.json', '.lnk', '.cmd')

n = 0
hits_dev = []
hits_user = []
by_group = Counter()
scanned_by_group = Counter()
for dp, dn, fns in os.walk(ROOT):
    rel_dp = os.path.relpath(dp, ROOT)
    parts = rel_dp.split(os.sep)
    group = 'thirdparty' if (parts and parts[0] == 'python') or \
        rel_dp.startswith(os.path.join('ext', '.runtime_deps')) else 'own'
    for fn in fns:
        if not fn.lower().endswith(SCAN_EXT):
            continue
        p = os.path.join(dp, fn)
        rel = os.path.relpath(p, ROOT)
        try:
            b = open(p, 'rb').read()
        except Exception:
            continue
        if b'\x00' in b[:4096]:
            continue
        t = b.decode('utf-8', 'replace')
        n += 1
        scanned_by_group[group] += 1
        for i, line in enumerate(t.splitlines(), 1):
            for m in ABS.findall(line):
                low = m.lower()
                mk = None
                for d in DEV_DIRS:
                    if d.lower() in low:
                        mk = d
                        break
                if mk:
                    hits_dev.append((group, rel, i, mk, m[:160]))
                elif DEV_USER.lower() in low:
                    hits_user.append((group, rel, i, 'dev-user', m[:160]))

print('scanned %d files: %s' % (n, dict(scanned_by_group)))
print('== 指向 reviewer 点名开发目录的绝对路径：%d 处 ==' % len(hits_dev))
for h in hits_dev[:40]:
    print('   ', h)
print('== 绝对路径里含构建机用户名（reviewer ③ 未点名）：%d 处 ==' % len(hits_user))
cnt = Counter((h[0], h[1]) for h in hits_user)
for (g, rel), c in cnt.most_common(30):
    print('    [%s] %s  x%d' % (g, rel, c))
