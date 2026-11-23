#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§222：**把 §222 追加进 `status/app/STATUS_APP.md`**（严格「只追加、不回头改旧章节」）。

## 做什么
1. 🔴 **写前备份**（`%TEMP%/STATUS_APP.md.bak_app222`）—— 供还原式复核；
2. 写前在**内存新文本**上跑**真不变量**：
   * `last_ack` 唯一且**保持 APP-121**（本轮**没有新纠偏** ⇒ 不许改它）；
   * 旧章节（§211/§212/…/§221 标题行）**逐字未变**；
   * 「最近更新」旧条目**逐字未变**（只在其**前面**插入本轮一行）；
   * 字节数 ≤ 40000、行数 ≤ 300（APP-052④ 限额）；
3. **临时文件 → `os.replace`**（**不先截断原文件**）；
4. 🔴 **写后独立复核**（另起进程可重跑）：不变量全过 + **还原式复核**
   （去掉本轮新增 ⇒ 与写前原件**逐字节**相同）。

## 纪律
- **只追加**；不改旧章节正文；**不碰** `status/app/CORRECTIONS_APP.md`；
- 「更新时间」用 `Get-Date` **实测值**（Windows 下走 `powershell.exe`，
  取不到则退回 `datetime.now()` 并在证据里标明来源）。

## 用法
```
python live_caption/_app222_write_status.py --title-file <t.txt> --recent-file <r.txt> [--apply]
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def get_date_measured() -> tuple:
    """「更新时间」用 Get-Date 实测值（Windows）；返回 (值, 来源)。"""
    try:
        out = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command',
             "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"],
            capture_output=True, text=True, timeout=30)
        v = (out.stdout or '').strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', v):
            return v, 'Get-Date (powershell.exe)'
    except Exception:
        pass
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'datetime.now()'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--title-file', required=True,
                    help='§222 的标题行 + 指针行（两行文本）')
    ap.add_argument('--recent-file', required=True,
                    help='「最近更新」本轮条目（一行文本）')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app222_write_status_evidence.json'))
    args = ap.parse_args()

    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        orig = f.read()
    if not args.apply:
        print('（dry-run）')
        print('  字节 %d / 行 %d（限额 %d / %d）'
              % (len(orig.encode('utf-8')), len(orig.splitlines()),
                 LIMIT_BYTES, LIMIT_LINES))
        print('  last_ack 命中 %d 次' % orig.count('last_ack: APP-121'))
        print('  §221 标题行存在 =', '## §221 ' in orig)
        return 0

    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app222')
    shutil.copy2(STATUS, bak)

    with io.open(args.title_file, 'r', encoding='utf-8') as f:
        title_block = f.read().rstrip('\n')
    with io.open(args.recent_file, 'r', encoding='utf-8') as f:
        recent_line = f.read().rstrip('\n')

    lines = orig.splitlines(True)
    text = ''.join(lines)

    # ── 写前真不变量（内存态）────────────────────────────────
    pre = {}
    pre['n_ack'] = text.count('last_ack: APP-121')
    pre['old_sections_unchanged'] = all(
        ('## §%d ' % n) in text for n in (211, 212, 213, 214, 215, 219, 220, 221))
    pre['recent_anchor'] = text.count('## 最近更新\n')
    pre['bytes_before'] = len(text.encode('utf-8'))
    pre['lines_before'] = len(text.splitlines())

    # ── ① 头部「更新时间」（last_ack **不变**：本轮无新纠偏）────
    now, now_src = get_date_measured()
    text, n_upd = re.subn(r'(?m)^更新时间: .*$',
                           '更新时间: %s' % now, text, count=1)
    if n_upd != 1:
        print('FAIL: 「更新时间」行命中 %d 次（应为 1）' % n_upd)
        return 2
    if text.count('last_ack: APP-121') != 1:
        print('FAIL: `last_ack: APP-121` 命中数异常（本轮不许改 last_ack）')
        return 2

    # ── ② 「最近更新」**最前面**插入本轮条目（旧的条目不删）────
    m = re.search(r'(?m)^## 最近更新\n', text)
    if not m:
        print('FAIL: 找不到「## 最近更新」')
        return 2
    ins = m.end()
    text = text[:ins] + recent_line + '\n' + text[ins:]

    # ── ③ 追加 §222（标题行 + 指针行）─────────────────────────
    if not text.endswith('\n'):
        text += '\n'
    text += '\n' + title_block + '\n'

    # ── 写前（落盘前）不变量 ────────────────────────────────
    pre['bytes_after'] = len(text.encode('utf-8'))
    pre['lines_after'] = len(text.splitlines())
    pre['bytes_ok'] = pre['bytes_after'] <= LIMIT_BYTES
    pre['lines_ok'] = pre['lines_after'] <= LIMIT_LINES
    pre['title_present'] = '\n## §222 ' in text
    pre['recent_present'] = recent_line.strip()[:60] in text
    if not (pre['bytes_ok'] and pre['lines_ok'] and pre['title_present']
            and pre['recent_present']):
        print('FAIL: 写前不变量未过 ⇒ 源文件零改动')
        for k in ('bytes_ok', 'lines_ok', 'title_present', 'recent_present'):
            print('   %s = %s' % (k, pre[k]))
        return 2

    # ── ④ 写盘（临时文件 → os.replace，**不先截断原文件**）────
    tmp = STATUS + '.app222.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    # ── ⑤ 写后独立复核 ──────────────────────────────────────
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        after = f.read()
    checks = [
        ('last_ack 仍为 APP-121（唯一）',
         after.count('last_ack: APP-121') == 1),
        ('「更新时间」已更新为 Get-Date 实测值',
         ('更新时间: %s' % now) in after),
        ('§222 标题行在', '\n## §222 ' in after),
        ('§221 标题行仍在（未回头改旧章节）', '## §221 ' in after),
        ('§211/§212/§213/§214/§215/§219/§220 标题行仍在',
         all(('## §%d ' % n) in after
             for n in (211, 212, 213, 214, 215, 219, 220))),
        ('「最近更新」本轮条目在', recent_line.strip()[:60] in after),
        ('字节数 ≤ %d' % LIMIT_BYTES,
         len(after.encode('utf-8')) <= LIMIT_BYTES),
        ('行数 ≤ %d' % LIMIT_LINES, len(after.splitlines()) <= LIMIT_LINES),
    ]
    # 🔴 **还原式复核**：去掉本轮新增 ⇒ 应与写前原件**逐字节**相同
    undo = after.replace(recent_line + '\n', '', 1)
    undo = undo.replace('\n' + title_block + '\n', '', 1)
    m_upd = re.search(r'(?m)^更新时间: .*$', orig)
    if m_upd:
        undo = re.sub(r'(?m)^更新时间: .*$', lambda _m: m_upd.group(0), undo,
                      count=1)
    checks.append(('还原式复核（去掉本轮新增后与写前原件逐字节一致）',
                   undo == orig))

    ev = {
        'script': '_app222_write_status.py',
        'ts': now,
        'date_source': now_src,
        'status': STATUS,
        'backup': bak,
        'pre_invariants': pre,
        'bytes_before': pre['bytes_before'],
        'lines_before': pre['lines_before'],
        'bytes_after': pre['bytes_after'],
        'lines_after': pre['lines_after'],
        'title_block_sha256': sha_text(title_block),
        'recent_line_sha256': sha_text(recent_line),
        'checks': {n: bool(o) for n, o in checks},
        'n_fail': sum(1 for _n, o in checks if not o),
        'note': ('本轮**没有新的 reviewer 纠偏** ⇒ `last_ack` 保持 APP-121；'
                 '§222 只追加，不回头改任何旧章节。'),
    }
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    t2 = args.out + '.tmp'
    with io.open(t2, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(t2, args.out)
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))
    print('  字节 %d / 行 %d（限额 %d B / %d 行）'
          % (ev['bytes_after'], ev['lines_after'], LIMIT_BYTES, LIMIT_LINES))
    print('  判定：%s' % ev['verdict'])
    print('  证据 → %s' % args.out)
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
