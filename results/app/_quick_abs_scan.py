#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时：快速扫包目录里的「绝对路径 + 开发目录特征词」命中（不含 python/Lib）。"""
import os
import re
import sys
from collections import Counter

PKG = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.0'
ABS = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\s"\'<>|]*)')
DEV = ('confucius4-openvino', 'live_dub_ext', 'qwen3tts_eval', 'hy_bench',
       'Worktrees', 'Trekker-PTL')
EXT = ('.py', '.json', '.lnk', '.cmd', '.md', '.bat', '.txt')
SKIP_PREFIX = ('python/Lib', 'python/include')

n = 0
tops = Counter()
hits = []
for root, dirs, files in os.walk(PKG):
    for f in files:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, PKG).replace('\\', '/')
        if rel.startswith(SKIP_PREFIX):
            continue
        if not f.lower().endswith(EXT):
            continue
        try:
            b = open(p, 'rb').read()
        except Exception:
            continue
        if b'\x00' in b[:4096]:
            continue
        t = b.decode('utf-8', 'replace')
        n += 1
        tops[rel.split('/')[0]] += 1
        for i, line in enumerate(t.splitlines(), 1):
            for m in ABS.findall(line):
                if any(d in m for d in DEV):
                    hits.append((rel, i, m[:200]))

print('scanned %d files; per-top-dir: %s' % (n, dict(tops)))
print('ABS dev hits: %d' % len(hits))
byfile = {}
for rel, i, m in hits:
    byfile.setdefault(rel, []).append((i, m))
for rel, v in sorted(byfile.items()):
    print('--- %s (%d)' % (rel, len(v)))
    for i, m in v[:4]:
        print('    L%-5d %s' % (i, m))
