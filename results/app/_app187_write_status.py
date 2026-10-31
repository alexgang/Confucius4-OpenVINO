#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app187 —— 把 §118 章节**追加**进 `status/app/STATUS_APP.md`（只追加，不改旧章节）。

🔴🔴🔴 **为什么用脚本而不是 Edit 工具**
------------------------------------
1. **旧正文一字未删**是硬要求 ⇒ 用「首个章节锚点切片」保住 `lines[i_s1:]` 整块；
2. **头部字段替换**要避免「value 自带 key 前缀 ⇒ 写两遍」（§29/§112 两次踩坑）；
3. **换行风格**必须先探测（STATUS 有 LF / CRLF 两种历史状态）⇒ 不能假设；
4. 写完要**逐项自检**：章节数 +1、旧正文整块仍在、头部字段各只出现一次。

🔴 **纪律**：本脚本**只写** `status/app/STATUS_APP.md`；**绝不碰** `CORRECTIONS_APP.md`。
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY = os.path.join(HERE, '_sec118_body.md')

NEW_LAST_ACK = 'APP-051'          # 本轮无新纠偏条目 ⇒ 不变
NEW_UPDATED = '2026-11-01 02:26'  # Get-Date 实测值


def read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    nl = '\r\n' if b'\r\n' in raw else '\n'
    return raw.decode('utf-8'), nl


def set_field(head, key, value):
    """在头部区替换 `key: value`（value **不得**自带 key 前缀）。"""
    assert not value.startswith(key + ':'), 'value 自带 key 前缀 ⇒ 会写两遍'
    pat = re.compile(r'^(%s:\s*)(.*)$' % re.escape(key), re.M)
    hits = pat.findall(head)
    assert len(hits) == 1, '头部字段 %r 出现 %d 次（应为 1）' % (key, len(hits))
    return pat.sub(lambda m: m.group(1) + value, head, count=1)


def main():
    text, nl = read_text(STATUS)

    # ── 1. 备份（先备份，再改；追加后也要能对照）──
    bak = os.path.join(tempfile.gettempdir(),
                       'STATUS_APP_before_sec118_%d.md' % os.getpid())
    shutil.copy2(STATUS, bak)
    print('[bak] %s' % bak)

    # ── 2. 切分：头部 = 第一个 `### §` 之前；正文 = 全部章节 ──
    m = re.search(r'(?m)^### §', text)
    assert m, '找不到章节锚点 `### §`'
    i_anchor = m.start()
    head, body = text[:i_anchor], text[i_anchor:]

    n_before = len(re.findall(r'(?m)^### §', body))
    print('[slice] 章节数 %d；头部 %d B；正文 %d B' % (n_before, len(head), len(body)))

    # ── 3. 追加新章节（**只追加在文件末尾**）──
    with open(BODY, 'r', encoding='utf-8') as f:
        new_body = f.read().rstrip('\n')
    # 🔴 追加块前保留一个空行分隔；且**不动**旧正文任何一个字节
    out_body = body.rstrip('\n') + '\n\n' + new_body + '\n'

    # ── 4. 改头部（只动头部区）──
    head = set_field(head, 'last_ack', NEW_LAST_ACK)
    head = set_field(head, '更新时间', NEW_UPDATED)

    # ── 5. 「最近更新」区块：追加一条 + 裁掉最旧的（硬约束 ≤ 15 行）──
    m2 = re.search(r'(?ms)^## 最近更新\n(.*?)(?=^## |\Z)', head)
    assert m2, '找不到「最近更新」区块'
    block = m2.group(1)
    lines = [l for l in block.split('\n')]
    # 去掉尾部空行
    while lines and not lines[-1].strip():
        lines.pop()
    new_entry = ('- 2026-11-01 02:26 **§118 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 按 APP-046 继续做，'
                 '抓到 **3 个真缺陷**：① **§117 验收链产物一个都没入库**（§104 同类错误复发）'
                 '② **HEAD 上 fresh clone 打包必失败**（`pack_v13` 传 `--expect-version`，'
                 '而 HEAD 的 `app170` 不认 ⇒ `rc=1` 拒绝打包）'
                 '③ **验收链脚本写死仓库根** ⇒ fresh clone 验收是假象（实测踩到）；'
                 '✅ 全部修掉（fresh clone 内 `app186` = **PASS 25/0**、`check_version_identity` **rc=0**）'
                 '＋ **新增 `app187` 入库完整性闸门**（AST 判定「写死仓库根」，鉴别力实测 **9/9**）')
    merged = [new_entry] + lines
    assert len(merged) <= 15, '「最近更新」超 15 行（%d）' % len(merged)
    while len(merged) > 15:
        merged.pop()
    new_block = '\n'.join(merged) + '\n\n'
    head = head[:m2.start()] + '## 最近更新\n' + new_block + head[m2.end():]

    # ── 6. 写回（保持原换行风格）──
    out = head + out_body
    with open(STATUS, 'wb') as f:
        f.write(out.replace('\n', nl).encode('utf-8'))

    # ── 7. 自检 ──
    check, cnl = read_text(STATUS)
    n_after = len(re.findall(r'(?m)^### §', check))
    assert n_after == n_before + 1, '章节数 %d ⇒ %d（应 +1）' % (n_before, n_after)
    # 旧正文整块仍在（**逐字**）
    old_body_core = body.rstrip('\n')
    assert old_body_core in check, '旧正文整块不在新文件里（被改动！）'
    # 头部字段各只出现一次
    for k in ('last_ack', '更新时间'):
        c = len(re.findall(r'(?m)^%s:' % re.escape(k), check))
        assert c == 1, '头部字段 %r 出现 %d 次' % (k, c)
    assert re.search(r'(?m)^last_ack: APP-051$', check), 'last_ack 取值不对'
    assert re.search(r'(?m)^更新时间: 2026-11-01 02:26$', check), '更新时间取值不对'
    # 新章节在末尾
    assert check.rstrip().endswith('需用户确认）。'), '新章节不在末尾'
    print('[ok] 章节 %d ⇒ %d；旧正文整块保留；头部字段各 1 次；字节 %d'
          % (n_before, n_after, len(check.encode('utf-8'))))


if __name__ == '__main__':
    sys.exit(main())
