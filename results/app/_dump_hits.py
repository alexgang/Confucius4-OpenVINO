#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时：把全量扫描的 9 处命中**逐条原文**打出来（含上下文行），用于定点改。"""
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r'C:\v20_cleantest_v2\Confucius4_LiveCaption_v2.0'
ABS = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\s"\'<>|]*)')
DEV_DIRS = ('confucius4-openvino', 'live_dub_ext', 'qwen3tts_eval', 'hy_bench',
            'Worktrees')
DEV_USER = 'Trekker-PTL'
SCAN_EXT = ('.py', '.json', '.lnk', '.cmd')

for dp, dn, fns in os.walk(ROOT):
    rel_dp = os.path.relpath(dp, ROOT)
    parts = rel_dp.split(os.sep)
    if (parts and parts[0] == 'python') or rel_dp.startswith(
            os.path.join('ext', '.runtime_deps')):
        dn[:] = []
        continue
    for fn in sorted(fns):
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
        lines = t.splitlines()
        for i, line in enumerate(lines, 1):
            for m in ABS.findall(line):
                low = m.lower()
                mk = None
                for d in DEV_DIRS:
                    if d.lower() in low:
                        mk = d
                        break
                if mk is None and DEV_USER.lower() in low:
                    mk = 'dev-user'
                if mk:
                    print('=' * 78)
                    print('HIT %s:%d  marker=%s' % (rel, i, mk))
                    print('  abs: %s' % m)
                    for j in range(max(0, i - 4), min(len(lines), i + 3)):
                        print('  %s%5d| %s' % ('>>' if j + 1 == i else '  ',
                                               j + 1, lines[j][:200]))
