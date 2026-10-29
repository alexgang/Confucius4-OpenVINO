#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§99：扫描 4 个改动文件里的「bytes 转义污染」行。

只读扫描，不修改任何文件。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
FILES = [
    os.path.join(ROOT, 'live_caption', 'live_caption_app.py'),
    os.path.join(ROOT, 'live_caption', 'tts_service.py'),
    os.path.join(ROOT, 'live_caption', 'speaker_tracker.py'),
    os.path.join(ROOT, 'live_caption', 'speaker_voice.py'),
]

ESC = chr(92) + 'u'   # 反斜杠 + u
FFFD = chr(0xFFFD)

for f in FILES:
    raw = open(f, 'rb').read()
    txt = raw.decode('utf-8', errors='replace')
    eol = 'CRLF' if b'\r\n' in raw else 'LF'
    lines = txt.replace('\r\n', '\n').split('\n')
    hits = []
    for i, l in enumerate(lines, 1):
        bad = []
        if ESC in l:
            bad.append('literal-escape')
        if FFFD in l:
            bad.append('U+FFFD')
        if bad:
            hits.append((i, bad, l))
    print('== %s  [%s]  %d lines' % (os.path.basename(f), eol, len(lines)))
    if not hits:
        print('   (clean)')
    for i, bad, l in hits:
        print('   L%-5d %-24s %s' % (i, ','.join(bad), l.strip()[:120]))
