#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compress_c195_app052_status.py —— 【APP-052 ④】压缩 STATUS_APP.md 到 ≤40 KB / ≤300 行。

## 做什么

1. **归档（只追加，bytes 级零风险）**
   把 `status/app/STATUS_APP.md` 里 **§109–§122 的正文**原样**追加**到
   `status/archive/STATUS_APP_sec109_122_upto_20261101.md`
   ⇒ **一个字都不删**（审计链完整）。
2. **精简版 = 模板生成**
   `status/app/_status_slim_template.md` ＋ 占位符替换
   （头部 5 字段 / 最近更新 / zip 信息 / §123 正文）
   ⇒ 🔴 **不用正则改现有文件** ⇒ 不会误伤行尾 / 不会丢章节。
3. **自指大小一致**：模板里写「本文件 N B / M 行」⇒ **占位符 + 不动点迭代**
   （替换后长度会变 ⇒ 必须迭代到稳定）。

## 🔴 关键纪律

- **只重写精简版**，**归档是追加** ⇒ 旧正文永远可取回；
- **行尾实测**：本文件实测是 **LF** ⇒ 写回用 `newline=''` 保持一致；
- **归档件写完立即算 SHA256** ⇒ 写进头部「已压缩」行；
- **写盘前**校验：≤ 40 000 B 且 ≤ 300 行 ⇒ 否则**拒绝写盘**（保留原文件）。

## 用法

    python live_caption/compress_c195_app052_status.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
TEMPLATE = os.path.join(REPO, 'status', 'app', '_status_slim_template.md')
SEC123 = os.path.join(REPO, 'status', 'app', '_sec123_body.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_sec109_122_upto_20261101.md')

#: 归档哪些章节的正文（标题行也进归档；精简版用索引表代替）
ARCHIVE_SECTIONS = list(range(109, 123))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: str):
    with open(path, 'rb') as f:
        raw = f.read()
    nl = '\r\n' if b'\r\n' in raw else '\n'
    return raw.decode('utf-8'), nl


def split_sections(text: str, nl: str):
    """按 `### §N` 切段 ⇒ [(编号 or None, [行...]), ...]。"""
    lines = text.split(nl)
    trailing = bool(lines and lines[-1] == '')
    if trailing:
        lines = lines[:-1]
    out = []
    cur_num, cur = None, []
    for ln in lines:
        if ln.startswith('### §'):
            # `### §109 ✅ ...` ⇒ 取 `§` 后的数字（不要用 `ln[4:]`，
            # 那个位置正好是 `§`）
            num = int(ln[4:].split()[0].lstrip('§'))
            out.append((cur_num, cur))
            cur_num, cur = num, [ln]
        else:
            cur.append(ln)
    out.append((cur_num, cur))
    return out, trailing


def build_archive(text: str, nl: str) -> str:
    secs, _ = split_sections(text, nl)
    blocks = []
    for num, ls in secs:
        if num is None:
            continue
        if num in ARCHIVE_SECTIONS:
            blocks.append(nl.join(ls))
    head = [
        '# STATUS_APP 归档（§109–§122 正文，bytes 级原样保留）',
        '',
        '> 生成时间：%s ｜ 来源：`status/app/STATUS_APP.md`（压缩前）'
        % time.strftime('%Y-%m-%d %H:%M:%S'),
        '> 用途：APP-052 ④ 要求把正文移入 `status/archive/`（**只追加**）。',
        '> 🔴 **本文件为只读归档** —— 结论以精简版 `status/app/STATUS_APP.md` 为准。',
        '> 🔴 §117 追加过「§109–§122」的章节编号与本归档一致 ⇒ 逐字可对照。',
        '',
        '',
    ]
    return nl.join(head + blocks) + nl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    text, nl = read_text(STATUS)
    tmpl, tnl = read_text(TEMPLATE)
    if tnl != nl:
        # 🔴 行尾不一致 ⇒ 统一到 STATUS 的行尾（模板是纯文本，无所谓）
        tmpl = tmpl.replace('\r\n', '\n')
    sec123 = ''
    if os.path.isfile(SEC123):
        sec123, _ = read_text(SEC123)

    arc_text = build_archive(text, nl)
    arc_sha = sha256_bytes(arc_text.encode('utf-8'))

    # ── 取值来源：`status/app/_status_fill.json`（由调用方按实测填写）──
    fill_json = os.path.join(REPO, 'status', 'app', '_status_fill.json')
    vals = {}
    if os.path.isfile(fill_json):
        import json
        with open(fill_json, 'r', encoding='utf-8') as f:
            vals = json.load(f)
    else:
        raise RuntimeError('缺 %s（必须先按实测填写 zip SHA / 字节数 / mtime 等）'
                           % fill_json)

    def fill(t: str, mapping: dict) -> str:
        for k, v in mapping.items():
            t = t.replace(k, v)
        return t

    def render(mapping: dict) -> str:
        body = fill(tmpl, dict(mapping))
        body = body.replace('__SEC123__', sec123.rstrip())
        if nl != '\n':
            body = body.replace('\n', nl)
        return body

    # ── 不动点迭代（自指大小一致）──
    base = {
        '__LAST_ACK__': vals.get('last_ack', 'APP-054'),
        '__UPDATED__': vals.get('updated', time.strftime('%Y-%m-%d %H:%M')),
        '__CURRENT__': vals.get('current', ''),
        '__BLOCKERS__': vals.get('blockers', ''),
        '__ZIP_MTIME__': vals.get('zip_mtime', ''),
        '__ZIP_BYTES__': vals.get('zip_bytes', ''),
        '__ZIP_FILES__': vals.get('zip_files', ''),
        '__ZIP_SHA__': vals.get('zip_sha', ''),
        '__RECENT__': vals.get('recent', ''),
    }
    out = render(base)
    for _ in range(40):
        compressed = ('本文件 __B__ B / __L__ 行（APP-052 ④ 限额 ≤ 40 000 B / ≤ 300 行）'
                      '；**§109–§122 正文已原样归档**到 '
                      '`status/archive/STATUS_APP_sec109_122_upto_20261101.md`'
                      '（%d B，SHA256 `%s`）；更早的章节见 '
                      '`status/archive/STATUS_APP_upto_20261030.md`'
                      % (len(arc_text.encode('utf-8')), arc_sha))
        m = dict(base)
        m['__COMPRESSED__'] = compressed
        cand = render(m)
        nb = len(cand.encode('utf-8'))
        nl_ = cand.count(nl) + (0 if cand.endswith(nl) else 1)
        c2 = compressed.replace('__B__', str(nb)).replace('__L__', str(nl_))
        m['__COMPRESSED__'] = c2
        cand2 = render(m)
        nb2 = len(cand2.encode('utf-8'))
        if nb2 == nb:
            out = cand2
            break
        out = cand2
    else:
        out = render(m)

    n_bytes = len(out.encode('utf-8'))
    n_lines = out.count(nl) + (0 if out.endswith(nl) else 1)
    print('精简版：%d B / %d 行（限额 40 000 B / 300 行）⇒ %s'
          % (n_bytes, n_lines,
             'PASS' if (n_bytes <= 40000 and n_lines <= 300) else 'FAIL'))
    print('归档：%d B（SHA256 %s）' % (len(arc_text.encode('utf-8')), arc_sha[:16]))
    if n_bytes > 40000 or n_lines > 300:
        print('  ⚠️ 超限 ⇒ 不写盘（保留原文件）')
        return 1
    if args.dry_run:
        print('[dry-run] 不写盘')
        return 0

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    mode = 'ab' if os.path.exists(ARCHIVE) else 'wb'
    with open(ARCHIVE, mode) as f:
        f.write(arc_text.encode('utf-8'))
    print('归档已写入：%s（%d B，SHA256 %s）'
          % (os.path.relpath(ARCHIVE, REPO), os.path.getsize(ARCHIVE),
             sha256_file(ARCHIVE)))

    with open(STATUS, 'wb') as f:
        f.write(out.encode('utf-8'))
    print('精简版已写入：%s（%d B / %d 行，SHA256 %s）'
          % (os.path.relpath(STATUS, REPO), os.path.getsize(STATUS),
             n_lines, sha256_file(STATUS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
