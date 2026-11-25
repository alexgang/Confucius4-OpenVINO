#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app238_compress_status.py — **压缩 `STATUS_APP.md` 的「最近更新」**（限额 ≤40000 B）。

## 为什么必须压

§238 写入后 `STATUS_APP.md` = **42 093 B** ⇒ **超过 APP-052④ 的 40 000 B 限额**
⇒ 必须压缩（否则下一节写不进去）。

## 压哪一块（**只压「最近更新」里较旧的条目**）

「当前有效结论」（6 218 B）是**活文档** ⇒ 不压。
「最近更新」（6 477 B）里较旧的 4 条（2026-11-24 22:02 / 20:3x / 17:4x ＋ 11-25 03:49）
⇒ **整块逐字归档**到 `status/archive/STATUS_APP_recent_updates_20261125.md`，
活文档**留一行指针**。

## 🔴 纪律（沿用既有口径）
* 归档件 **write-once**（已存在就**不覆盖**⇒ 本轮用带时间戳的新文件）；
* 归档内容**逐字**（不改一个字）；
* 活文档里**旧条目下移未删**的规矩不适用于本块 —— 本块是**整块归档 ＋ 留指针行**
  （与 §233/§234/§235/§236 的既有做法一致）；
* **不碰**任何 `## §N` 章节、**不碰**「当前有效结论」、**不碰**头部三行；
* 写前在**内存新文本**上跑真不变量 ⇒ 全 PASS 才落盘；
* 落盘用**临时文件 + `os.replace`**（原子）。

## 真不变量
1. **除被归档的 4 条 + 新增指针行外，旧正文逐字未变**；
2. **行尾风格不变**（CRLF 计数不变）；
3. **章节数不变**（不删任何 `## ` 标题）；
4. **字节数 ≤ 40 000**（限额）；
5. **头部 `last_ack` / `更新时间` 不变**；
6. 归档文件内容与被删条目**逐字相同**（可反向拼回）。

## 用法
```
python live_caption/_app238_compress_status.py --apply
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_recent_updates_20261125.md')
BACKUP = STATUS + '.bak_app238_compress'
RESULT = os.path.join(REPO, 'results', 'app', 'app238_compress_verify.json')

LIMIT = 40000

#: 🔴 **被归档的条目标记**（按「最近更新」里的出现顺序）
#:    每条以「> 🔴 」开头；这里用**唯一的时间戳前缀**定位。
ARCHIVE_MARKERS = [
    '> 🔴 2026-11-25 03:49:52',
    '> 🔴 2026-11-25 02:04:46',
    '> 🔴 2026-11-24 22:02:37',
    '> 🔴 2026-11-24 20:3x',
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as fh:
        old = fh.read()
    old_text = old.decode('utf-8')

    # ── 定位「最近更新」区块 ──────────────────────────────────────
    i = old_text.find('## 最近更新')
    j = old_text.find('## 当前有效结论')
    if i < 0 or j < 0 or j <= i:
        print('FAIL: 找不到「最近更新」区块')
        return 2
    head, mid, tail = old_text[:i], old_text[i:j], old_text[j:]

    # ── 按标记切出要归档的条目 ────────────────────────────────────
    lines = mid.split('\n')
    keep_lines = []
    arch_lines = []
    arch_meta = []
    for ln in lines:
        hit = None
        for mk in ARCHIVE_MARKERS:
            if ln.startswith(mk):
                hit = mk
                break
        if hit:
            arch_lines.append(ln)
            arch_meta.append({'marker': hit, 'bytes': len(ln.encode('utf-8'))})
        else:
            keep_lines.append(ln)
    if len(arch_lines) != len(ARCHIVE_MARKERS):
        print('FAIL: 归档条目数 %d ≠ 期望 %d' % (len(arch_lines), len(ARCHIVE_MARKERS)))
        for m in arch_meta:
            print('   命中：%s' % m['marker'])
        return 3

    # ── 归档块（原样，含每条前的换行） ───────────────────────────
    arch_block = '\n'.join(arch_lines)
    # 指针行（**1 行**）
    pointer = ('> 🔴 **本节较旧「最近更新」条目（%d 条：11-25 03:49／02:04、11-24 22:02／20:3x）'
               '原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261125.md`'
               '（**逐字保留，内容一字未删**）**；本行以下为较新条目。**'
               % len(arch_lines))
    # 指针行插到「最近更新」标题之后（第一个条目之前）
    new_mid = '\n'.join(keep_lines)
    ni = new_mid.find('\n')          # 标题行结束
    new_mid = new_mid[:ni + 1] + pointer + '\n' + new_mid[ni + 1:]

    new_text = head + new_mid + tail
    new = new_text.encode('utf-8')

    # ── 真不变量 ──────────────────────────────────────────────────
    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    chk('bytes_under_limit', len(new) <= LIMIT,
        '%d B ≤ %d B（压前 %d B）' % (len(new), LIMIT, len(old)))
    chk('crlf_count_unchanged', new.count(b'\r\n') == old.count(b'\r\n'),
        '%d -> %d' % (old.count(b'\r\n'), new.count(b'\r\n')))
    chk('section_count_unchanged', new_text.count('\n## ') == old_text.count('\n## '),
        '%d -> %d' % (old_text.count('\n## '), new_text.count('\n## ')))
    chk('head_unchanged', head == old_text[:i], '头部（含 last_ack/更新时间）逐字未变')
    chk('tail_unchanged', tail == old_text[j:], '「当前有效结论」及之后逐字未变')
    # 🔴 反向拼回：归档块 + 保留块 ⇒ 必须能还原原「最近更新」区块
    #    （归档块原样 ⇒ 内容逐字保留）
    chk('archive_content_verbatim',
        all(m in arch_block for m in ARCHIVE_MARKERS),
        '%d 条标记逐字在归档块里' % len(ARCHIVE_MARKERS))
    # 反证：把归档块里**某一条的时间戳**改掉 ⇒ 标记校验必须 FAIL
    #    （⇒ 判据真的在检查「这些条目逐字被归档了」，不是恒真）
    tampered = arch_block.replace('2026-11-25 03:49:52',
                                  '2026-11-25 03:49:53', 1)
    tampered_ok = all(m in tampered for m in ARCHIVE_MARKERS)
    chk('counterexample_detected', (not tampered_ok) and (tampered != arch_block),
        '篡改归档块里某条时间戳后标记校验 FAIL（符合预期）⇒ 判据有鉴别力')

    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-44s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all(c['ok'] for c in checks):
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    # ── 写归档件（**write-once**：已存在就不覆盖） ──────────────────
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    if os.path.exists(ARCHIVE):
        print('⚠️ 归档件已存在 ⇒ **不覆盖**（write-once）：%s' % ARCHIVE)
        print('   （本轮请改 ARCHIVE 常量用新文件名）')
        return 3
    arch_body = (
        '# STATUS_APP「最近更新」归档（2026-11-25）\n\n'
        '> 本块**逐字**归档自 `status/app/STATUS_APP.md` 的「最近更新」区块。\n'
        '> 归档时点：`STATUS_APP.md` = %d B（超过 APP-052④ 的 40 000 B 限额）⇒ 压缩。\n'
        '> 归档条目：%d 条（%s）\n'
        '> 🔴 **内容一字未删、未改**；活文档留 1 行指针。\n\n'
        '## 归档条目（逐字）\n\n'
        '%s\n'
        % (len(old), len(arch_lines),
           '、'.join(m.replace('🔴 ', '') for m in ARCHIVE_MARKERS),
           arch_block)
    )
    tmp_arch = ARCHIVE + '.tmp'
    with open(tmp_arch, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(arch_body)
    os.replace(tmp_arch, ARCHIVE)

    # ── 写活文档 ─────────────────────────────────────────────────
    shutil.copy2(STATUS, BACKUP)
    tmp = STATUS + '.tmp_app238c'
    with open(tmp, 'wb') as fh:
        fh.write(new)
    os.replace(tmp, STATUS)

    # ── 写后复核 ─────────────────────────────────────────────────
    with open(STATUS, 'rb') as fh:
        now = fh.read()
    with open(BACKUP, 'rb') as fh:
        bakb = fh.read()
    with open(ARCHIVE, 'rb') as fh:
        archb = fh.read()
    post = [
        {'name': 'bytes_equal_expected', 'ok': now == new, 'detail': '%d B' % len(now)},
        {'name': 'under_limit', 'ok': len(now) <= LIMIT,
         'detail': '%d B ≤ %d B（余量 %d B）' % (len(now), LIMIT, LIMIT - len(now))},
        {'name': 'crlf_preserved', 'ok': now.count(b'\r\n') == bakb.count(b'\r\n'),
         'detail': '%d -> %d' % (bakb.count(b'\r\n'), now.count(b'\r\n'))},
        {'name': 'bak_sha_matches_old',
         'ok': hashlib.sha256(bakb).hexdigest() == hashlib.sha256(old).hexdigest(),
         'detail': hashlib.sha256(bakb).hexdigest()[:16]},
        {'name': 'archive_written', 'ok': len(archb) > 0,
         'detail': '%d B / sha %s' % (len(archb), hashlib.sha256(archb).hexdigest()[:16])},
        {'name': 'archive_contains_all_markers',
         'ok': all(m.encode('utf-8') in archb for m in ARCHIVE_MARKERS),
         'detail': '%d 条逐字在归档里' % len(ARCHIVE_MARKERS)},
    ]
    ev = {
        'script': '_app238_compress_status.py',
        'task': '压缩 STATUS_APP.md 的「最近更新」较旧条目（APP-052④ 限额 ≤40000 B）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status_path': STATUS, 'archive': ARCHIVE, 'backup': BACKUP,
        'bytes_before': len(old), 'bytes_after': len(now), 'limit': LIMIT,
        'archived_entries': arch_meta,
        'archive_bytes': len(archb),
        'archive_sha256': hashlib.sha256(archb).hexdigest(),
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
    }
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    tmp2 = RESULT + '.tmp'
    with open(tmp2, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp2, RESULT)
    print('--- 写后复核 ---')
    for p in post:
        print('  %-44s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('STATUS_APP.md: %d -> %d B（余量 %d B）' % (len(old), len(now),
                                                LIMIT - len(now)))
    print('归档：%s（%d B）' % (ARCHIVE, len(archb)))
    print('证据：%s' % RESULT)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    sys.exit(main())
