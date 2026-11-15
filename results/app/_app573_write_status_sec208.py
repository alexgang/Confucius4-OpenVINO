#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app573 —— §208 写 `status/app/STATUS_APP.md`（**fail-closed，原子写，逐字节复核**）。

🔴 **为什么用脚本写（而不是 Edit 工具手改）**
  §204 真踩过：`open(path,'w')` **先截断再写** ⇒ 写失败 ⇒ **文件变 0 B**
  ⇒ 本脚本一律「**临时文件 → `os.replace`**」，且**写前跑完自检**、写后逐字节复核。

🔴 **本脚本做的四件事（只这四件，其余一律不碰）**
  ① 把 **§207 整块逐字归档** ⇒ `status/archive/STATUS_APP_sec207_20261115.md`
     （活文档保留 §207 **标题行** ＋ 换 1 行指针；**正文一字未删**）
  ② 追加 **§208**（标题行 ＋ 摘要 ＋ 指针行）
  ③ 头部 `更新时间` 换成 `Get-Date` 实测值（`last_ack` **不动**：无新纠偏）
  ④ 「最近更新」加 1 条本轮条目

🔴 **自检（写盘前全过才写；任一不过 ⇒ 零写入）**
  · 新文件 ≤ **40 000 B**（APP-052④）
  · **纯 LF**、无 BOM
  · 章节数 = 开工数 ＋ 1（§208）
  · §207 归档件正文块 **逐字命中**（SHA256）
  · 除「授权改动」外，活文档其余部分**逐字未变**
  · **还原式复核**：把 §207 指针行换回原文 ＋ 退回授权改动 ⇒ 与开工备份**逐字节相同**
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec207_20261115.md')
COMPANION = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec208_detail_20261115.md')
LIMIT = 40000
TS = '2026-11-15 10:18:04'

SEC207_PTR = (
    '> \U0001f534 **本节正文已整块逐字归档** ⇒ '
    '`status/archive/STATUS_APP_sec207_20261115.md`'
    '（正文块 SHA256 `{sha}`／{n} B）⇒ 活文档保留 §207 标题行 ＋ 1 行指针。\n')

RECENT_LINE = (
    '> \U0001f534 2026-11-15 10:18:04 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：'
    '6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 逐字未变、agent-mail 工具层仍 `not_bound`'
    '（第 11 轮）、conversation_search 0、`NOTICE` 11-05、git 0/0、ASR-058 无 App 条目）｜'
    '\U0001f534 **修掉完整版（`pack_v13.py`）出包闸门真缺陷：全程零验收绑定**｜'
    '**鉴别力矩阵 15/15 PASS**｜**未打包／零客户包写入／未改产品代码**\n')

SEC208_TITLE = (
    '## §208 巡检（无新 reviewer 纠偏，last_ack 仍 **APP-109**）｜'
    '\U0001f534 **修掉完整版（`pack_v13.py`）出包闸门真缺陷：全程零验收绑定**｜'
    '**鉴别力矩阵 15/15 PASS**｜**未打包／零客户包写入／未改产品代码**｜'
    '**本条需等 reviewer 复核**\n')

SEC208_BODY = None  # 活文档速查**从 companion 读**（唯一事实来源）


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fail(msg):
    print('!! FAIL-CLOSED：%s ⇒ **零写入**' % msg)
    sys.exit(1)


def main():
    with open(STATUS, 'rb') as f:
        orig = f.read()
    orig_text = orig.decode('utf-8')
    print('[pre] STATUS = %d B' % len(orig))

    # ── 开工备份（供还原式复核用）──
    bak = os.path.join(tempfile.gettempdir(), 'wb_status_sec208_pre.bak')
    with open(bak, 'wb') as f:
        f.write(orig)

    # ── ① 定位 §207 整块（标题行 ＋ 正文，**到文件末尾**）──
    i207 = orig_text.find('\n## §207 ')
    if i207 < 0:
        fail('找不到 §207 标题行')
    sec207 = orig_text[i207 + 1:]              # 含标题行
    if not sec207.startswith('## §207 '):
        fail('§207 块起点异常')
    sec207_bytes = sec207.encode('utf-8')
    print('[pre] §207 块 = %d B（sha %s）' % (len(sec207_bytes), sha(sec207_bytes)[:16]))

    # ── ② companion：算正文块 SHA，回填占位符 ──
    with open(COMPANION, 'rb') as f:
        comp = f.read()
    comp_text = comp.decode('utf-8')
    LIVE_MARK = ('---- 活文档速查（以下 6 行＝**唯一事实来源**；'
                 'writer 按此**原样**追加到活文档）----')
    FULL_MARK = ('---- 完整正文（以下逐字；**正文块 SHA256 ＝ '
                 '本分隔线之后的全部内容**）----')
    if LIVE_MARK not in comp_text or FULL_MARK not in comp_text:
        fail('companion 缺「速查 / 完整正文」分隔标记')
    head, rest = comp_text.split(LIVE_MARK, 1)
    live_txt, body = rest.split(FULL_MARK, 1)
    live_txt = live_txt.strip('\n')
    body = body.strip('\n') + '\n'
    if '<FILLED_BY_WRITER>' not in head:
        fail('companion 占位符缺失')
    body_sha = sha(body.encode('utf-8'))
    body_bytes = len(body.encode('utf-8'))
    head = head.replace('<FILLED_BY_WRITER>', '%s（%d B）'
                      % (body_sha, body_bytes))
    comp_new = (head + LIVE_MARK + '\n' + live_txt + '\n' + FULL_MARK
                + '\n' + body).encode('utf-8')
    # 速查行：把 {cbytes} / {csha} 占位符**就地**填上（不用 .format
    # ⇒ 正文里的花括号不会炸）
    SEC208_BODY = (live_txt.replace('{cbytes}', str(body_bytes))
                   .replace('{csha}', body_sha) + '\n')
    print('[pre] 速查 %d B｜完整正文 %d B'
          % (len(SEC208_BODY.encode('utf-8')), body_bytes))

    # ── ③ 组装新活文档 ──
    text = orig_text

    # ③a 头部：只换 `更新时间`（last_ack 不动）
    new_text, n = re.subn(r'(?m)^更新时间: .*$', '更新时间: %s' % TS, text, count=1)
    if n != 1:
        fail('`更新时间` 行定位失败（命中 %d 次）' % n)
    text = new_text

    # ③b 「最近更新」加 1 条（插在该节第一条 `> ` 之前）
    k = text.find('\n## 最近更新\n')
    if k < 0:
        fail('找不到「## 最近更新」')
    j = text.find('\n> ', k)
    if j < 0:
        fail('「最近更新」节内找不到首条 `> `')
    text = text[:j + 1] + RECENT_LINE + text[j + 1:]

    # ③c §207 正文 ⇒ 指针行（**标题行保留**）
    ptr = SEC207_PTR.format(sha=sha(sec207_bytes), n=len(sec207_bytes))
    text = text.replace(sec207, sec207.split('\n', 1)[0] + '\n' + ptr, 1)
    if sec207 in text:
        fail('§207 原正文仍在活文档')

    # ③d 追加 §208（末尾）
    if not text.endswith('\n'):
        text += '\n'
    text += '\n' + SEC208_TITLE + SEC208_BODY
    new_bytes = text.encode('utf-8')

    # ── ④ 自检（全部通过才写盘）──
    if len(new_bytes) > LIMIT:
        fail('新文件 %d B > 限额 %d B' % (len(new_bytes), LIMIT))
    if b'\r\n' in new_bytes:
        fail('新文件含 CRLF（须纯 LF）')
    if new_bytes.startswith(b'\xef\xbb\xbf'):
        fail('新文件含 BOM')
    n_sec_old = len(re.findall(r'(?m)^## §\d+ ', orig_text))
    n_sec_new = len(re.findall(r'(?m)^## §\d+ ', text))
    if n_sec_new != n_sec_old + 1:
        fail('章节数 %d ⇒ %d（应 +1）' % (n_sec_old, n_sec_new))
    if '## §208 ' not in text:
        fail('§208 未写入')
    if 'last_ack: APP-109' not in text:
        fail('last_ack 被改动')
    if orig_text.count('## §207 ') != text.count('## §207 '):
        fail('§207 标题行数量变了')

    # 还原式复核：把 §207 指针行换回原文 ＋ 退回授权改动 ⇒ 应与开工备份逐字节相同
    restored = text.replace(sec207.split('\n', 1)[0] + '\n' + ptr, sec207, 1)
    restored = re.sub(r'(?m)^更新时间: .*$', '更新时间: 2026-11-15 08:47:45',
                      restored, count=1)
    restored = restored.replace(RECENT_LINE, '', 1)
    restored = restored.replace('\n' + SEC208_TITLE + SEC208_BODY, '', 1)
    if restored.encode('utf-8') != orig:
        fail('还原式复核不通过（退回授权改动后 ≠ 开工备份）')

    # ── ⑤ 写归档件（write-once）──
    arch_head = (
        '# STATUS_APP §207 整块逐字归档（2026-11-15）\n\n'
        '归档时间：%s\n'
        '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §208 出空间。\n'
        '正文一字未删（标题行仍留在活文档）。\n\n'
        '§207 正文块 SHA256（含标题行）：%s（%d B）\n\n'
        '---- 以下为 §207 原文，逐字 ----\n' % (TS, sha(sec207_bytes),
                                             len(sec207_bytes)))
    arch_bytes = (arch_head + sec207).encode('utf-8')
    if os.path.exists(ARCHIVE):
        with open(ARCHIVE, 'rb') as f:
            _old = f.read()
        if _old == arch_bytes:
            print('[write] 归档件已存在且**逐字节一致** ⇒ 幂等跳过')
        else:
            fail('归档件已存在但内容不同（write-once）：%s' % ARCHIVE)

    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)

    # ── ⑥ 原子写：临时文件 → os.replace ──
    def atomic_write(path, data):
        d = os.path.dirname(path)
        fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
        os.close(fd)
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    if not (os.path.exists(ARCHIVE) and open(ARCHIVE, 'rb').read() == arch_bytes):
        atomic_write(ARCHIVE, arch_bytes)
    atomic_write(COMPANION, comp_new)
    atomic_write(STATUS, new_bytes)

    # ── ⑦ 写后逐字节复核 ──
    with open(STATUS, 'rb') as f:
        got = f.read()
    if got != new_bytes:
        fail('写后逐字节复核不一致')
    with open(ARCHIVE, 'rb') as f:
        got_arch = f.read()
    if sec207_bytes not in got_arch:
        fail('归档件未逐字包含 §207 原文')
    if got_arch.count(sec207.encode('utf-8')) != 1:
        fail('归档件里 §207 原文出现次数 != 1')
    print('[post] STATUS = %d B（限额 %d）' % (len(got), LIMIT))
    print('[post] 归档件 = %d B｜companion = %d B'
          % (len(got_arch), len(comp_new)))
    print('[post] §207 正文块 sha = %s（%d B）'
          % (sha(sec207_bytes), len(sec207_bytes)))
    print('[post] §208 companion 正文块 sha = %s（%d B）'
          % (body_sha, body_bytes))
    print('[post] 还原式复核：PASS（写前已验）｜备份 = %s' % bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
