#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app573_write_status_sec207.py —— 写 STATUS §207（append-only）＋ 归档 §206 ＋ 归档 3 条旧「最近更新」。

纪律（全部 fail-closed：**任何自检不过 ⇒ 零写入**）：
  · 只**追加** `## §N` 章节，不回头改旧章节；
  · `last_ack` 无新纠偏 ⇒ **保持 APP-109**（不写自己的编号）；
  · 「更新时间」用 **Get-Date 实测值**（调用方传入）；
  · 压缩：把 §206 正文**整块逐字归档**，活文档保留 §206 **标题行** ＋ 1 行指针；
    另把「最近更新」里 3 条较旧条目**整块逐字归档** ＋ 1 行指针（沿用既有做法）；
  · **还原式复核**：把本轮**所有**增量（新增章节 ＋ 两条指针行 ＋ 最近更新行 ＋
    头部时间戳行）**逐一逆向还原** ⇒ 必须与开工备份**逐字节相同**；
  · 上限 **40 000 B／300 行**（APP-052④）、纯 LF、无 BOM；
  · 落盘一律「写临时文件 → `os.replace`」＋ 写后逐字节复核（§204 真踩过 0 B）。
"""
import hashlib
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec206_20261115.md')
RU_ARCHIVE = os.path.join(REPO, 'status', 'archive',
                           'STATUS_APP_recent_updates_20261115.md')
DETAIL = os.path.join(REPO, 'status', 'app',
                      'STATUS_APP_sec207_detail_20261115.md')
BODY_FILE = os.path.join(REPO, 'results', 'app', '_app571_sec207_body.txt')
SUMMARY_FILE = os.path.join(REPO, 'results', 'app',
                            '_app572_sec207_summary.txt')
TS = sys.argv[1] if len(sys.argv) > 1 else '2026-11-15 08:47:45'
MAXB, MAXL = 40000, 300

base = open(STATUS, 'rb').read()
assert b'\r' not in base, '开工文件含 CR（行尾不是纯 LF）'
assert base[:3] != b'\xef\xbb\xbf', '开工文件有 BOM'
base_txt = base.decode('utf-8')

# ── 定位 §206（应是最后一节）──
i206 = base_txt.index('## §206 ')
sec206 = base_txt[i206:]                      # 标题行 ＋ 正文，到 EOF
title206 = sec206.split('\n')[0]
assert base_txt.count(title206) == 1, '§206 标题行不唯一'
last_line = [l for l in sec206.rstrip('\n').split('\n') if l.strip()][-1]
assert last_line.startswith('> **⑩'), '§206 不是最后一节：%r' % last_line[:40]

# ── 归档件正文块（含标题行）──
block206 = sec206.rstrip('\n')
sha206 = hashlib.sha256(block206.encode('utf-8')).hexdigest()
arch = (
    '# STATUS_APP §206 整块逐字归档（2026-11-15）\n'
    '\n'
    '归档时间：%s\n'
    '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §207 出空间。\n'
    '正文一字未删（标题行仍留在活文档）。\n'
    '\n'
    '§206 正文块 SHA256（含标题行）：%s（%d B）\n'
    '\n'
    '---- 以下为 §206 原文，逐字 ----\n'
    % (TS, sha206, len(block206.encode('utf-8')))
) + block206 + '\n'

# ── 定位「最近更新」里 3 条较旧条目（到第一条指针行为止）──
ru = '## 最近更新\n'
assert base_txt.count(ru) == 1, '「## 最近更新」标题不唯一'
ru_body = base_txt.index(ru) + len(ru)
m = re.search(r'^> 🔴 本节 ', base_txt[ru_body:], flags=re.M)
assert m, '「最近更新」里找不到指针行 ⇒ 3 条旧条目定位失败'
ru_block = base_txt[ru_body:ru_body + m.start()]      # 3 条真实条目（含换行）
ru_lines = [l for l in ru_block.split('\n') if l.strip()]
assert len(ru_lines) == 3, '「最近更新」旧条目数不是 3：%d' % len(ru_lines)
sha_ru = hashlib.sha256(ru_block.encode('utf-8')).hexdigest()
ru_arch = (
    '# STATUS_APP 「最近更新」3 条较旧条目整块逐字归档（2026-11-15）\n'
    '\n'
    '归档时间：%s\n'
    '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §207 出空间。\n'
    '正文一字未删。\n'
    '\n'
    '块 SHA256：%s（%d B）\n'
    '\n'
    '---- 以下为原文，逐字 ----\n'
    % (TS, sha_ru, len(ru_block.encode('utf-8')))
) + ru_block
assert ru_arch.endswith('\n'), '归档件末尾缺换行'

# ── §207 正文：完整正文进 companion（APP-052④ 限额），活文档只留摘要 ──
FULL_BODY = open(BODY_FILE, encoding='utf-8').read().rstrip('\n')
assert FULL_BODY.startswith('## §207 '), '§207 完整正文开头不对'
assert FULL_BODY.count('\n> ') >= 11, '§207 完整正文形状不对（条目数不足）'
detail_sha = hashlib.sha256(FULL_BODY.encode('utf-8')).hexdigest()
detail_len = len(FULL_BODY.encode('utf-8'))
detail_txt = (
    '# STATUS_APP §207 完整正文（companion，2026-11-15）\n'
    '\n'
    '归档原因：活文档逼近 **40 000 B** 上限（APP-052④）⇒ §207 完整正文放 companion，\n'
    '活文档只留摘要（§207 标题行 ＋ 摘要条目 ＋ 指针行）。\n'
    '生成时间：%s\n'
    '\n'
    '§207 完整正文 SHA256：%s（%d B）\n'
    '\n'
    '---- 以下为 §207 完整正文，逐字 ----\n'
    % (TS, detail_sha, detail_len)
) + FULL_BODY + '\n'

SUMMARY = open(SUMMARY_FILE, encoding='utf-8').read().rstrip('\n')
assert SUMMARY.startswith('## §207 '), '§207 摘要开头不对'
assert '"""' not in SUMMARY, '§207 摘要里含三引号'
SEC207 = SUMMARY.replace('__DETAIL_LEN__', str(detail_len))
SEC207 = SEC207.replace('__DETAIL_SHA__', detail_sha)
assert ('**%d B**／SHA256 `%s`' % (detail_len, detail_sha)) in SEC207, \
    '摘要里没把 companion 的字节/SHA 填进去'
assert '__DETAIL' not in SEC207, '摘要里还有未填的占位符'

POINTER206 = ('> 🔴 **本节正文已整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_sec206_20261115.md`'
              '（正文块 SHA256 `%s`）；活文档保留 §206 标题行 ＋ 1 行指针。'
              % sha206)
POINTER_RU = ('> 🔴 本节 3 条较旧「最近更新」条目（2026-11-14 18:28:17／'
              '19:38:17／20:52:02 三轮巡检）原文已**整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_recent_updates_20261115.md`'
              '（块 SHA256 `%s`）；活文档本节仅留本指针行。' % sha_ru)

RECENT = ('> 🔴 %s ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：'
          '6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 逐字未变、'
          'agent-mail 仍 `not_bound`、`conversation_search` 0 命中、'
          '`NOTICE` 最新 11-05、git 0/0、ASR 最大 ASR-058 无 App 条目）｜'
          '🔴 **修掉 MiniMVP 出包闸门的真缺陷：验收证据不绑包身份、'
          '不绑包内容（验收后改包照样能出包）＋「PASS（有 1 项未结：…）」被误判 FAIL**｜'
          '**鉴别力矩阵 12/12 PASS（改前 5 臂 fail-open ＋ 1 臂假 FAIL）**｜'
          '**零客户包写入／未打包／未改产品代码**\n' % TS)

# ── 组装新内容 ──
new = base_txt
old_ts_line = [l for l in new.split('\n') if l.startswith('更新时间: ')]
assert len(old_ts_line) == 1, '头部「更新时间」行不唯一'
new = new.replace(old_ts_line[0], '更新时间: ' + TS)
# ① 归档「最近更新」3 条旧条目 ⇒ 换 1 行指针
assert new.count(ru_block) == 1, '「最近更新」旧条目块定位失败'
new = new.replace(ru_block, POINTER_RU + '\n')
# ② 插入本轮的「最近更新」条目
assert new.count(ru) == 1, '「## 最近更新」标题不唯一'
new = new.replace(ru, ru + RECENT)
# ③ 归档 §206 ⇒ 留标题行 ＋ 指针行
assert new.count(sec206) == 1, '§206 块定位失败'
new = new.replace(sec206, title206 + '\n' + POINTER206 + '\n')
# ④ 追加 §207 摘要
new = new.rstrip('\n') + '\n\n' + SEC207

nb = new.encode('utf-8')
nl = nb.count(b'\n')
checks = [
    ('字节上限', len(nb) <= MAXB, '%d B（上限 %d）' % (len(nb), MAXB)),
    ('行数上限', nl <= MAXL, '%d 行（上限 %d）' % (nl, MAXL)),
    ('纯 LF', b'\r' not in nb, 'CR=%d' % nb.count(b'\r')),
    ('无 BOM', nb[:3] != b'\xef\xbb\xbf', ''),
    ('§206 标题行仍在且唯一', new.count(title206) == 1, ''),
    ('§207 为最后一节',
     new.rstrip('\n').rfind('## §207 ') > new.rstrip('\n').rfind('## §206 '), ''),
    ('最近更新条目在标题后',
     new.split(ru)[1].split('\n')[0].startswith('> 🔴 %s' % TS), ''),
    ('§206 归档块与开工逐字节一致',
     block206.encode('utf-8') in arch.encode('utf-8'), ''),
    ('「最近更新」归档块与开工逐字节一致',
     ru_block.encode('utf-8') in ru_arch.encode('utf-8'), ''),
    ('last_ack 仍 APP-109', 'last_ack: APP-109' in new, ''),
    ('无未填占位符', '__DETAIL' not in new, ''),
]

# ── 还原式复核：逐一逆向还原本轮**所有**增量 ──
rest = new
cut = rest.rindex('\n\n## §207 ')
rest = rest[:cut] + '\n'
rest = rest.replace(title206 + '\n' + POINTER206 + '\n', sec206)
rest = rest.replace(POINTER_RU + '\n', ru_block)
rest = rest.replace(ru + RECENT, ru)
rest = rest.replace('更新时间: ' + TS, old_ts_line[0])
checks.append(('还原式复核（逐字节回到开工）', rest == base_txt,
               '还原后 %d B vs 开工 %d B' % (len(rest.encode('utf-8')), len(base))))

ok = all(c[1] for c in checks)
for name, good, extra in checks:
    print(('  [OK] ' if good else '  [FAIL] ') + name + ('  ' + extra if extra else ''))
if not ok:
    print('\n🔴 自检未全过 ⇒ **零写入**，中止。')
    raise SystemExit(1)


def atomic_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(data)
    os.replace(tmp, path)


os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
for path, data, probe, label in ((ARCHIVE, arch, block206, '§206 归档'),
                                  (RU_ARCHIVE, ru_arch, ru_block, '「最近更新」归档'),
                                  (DETAIL, detail_txt, FULL_BODY, 'companion')):
    if os.path.isfile(path):
        old = open(path, encoding='utf-8').read()
        assert probe in old, '已存在的 %s 与本轮内容不一致 ⇒ 中止' % label
        action = '已存在（write-once，只校验未重写）'
    else:
        atomic_write(path, data)
        action = '新写入'
    print('  %-16s %s  %d B' % (label, os.path.relpath(path, REPO),
                                len(data.encode('utf-8'))), '（%s）' % action)
atomic_write(STATUS, nb.decode('utf-8'))
assert open(STATUS, 'rb').read() == nb, '落盘后校验失败（文件与内存不一致）'
assert FULL_BODY in open(DETAIL, encoding='utf-8').read(), 'companion 写盘后校验失败'
print('\n✅ 已写入：')
print('  STATUS_APP.md          %d B / %d 行（开工 %d B）' % (len(nb), nl, len(base)))
print('  §206 正文块 SHA256     %s（%d B）' % (sha206, len(block206.encode('utf-8'))))
print('  「最近更新」块 SHA256  %s（%d B）' % (sha_ru, len(ru_block.encode('utf-8'))))
print('  companion 正文块 SHA   %s（%d B）' % (detail_sha, detail_len))
print('  last_ack 保持          APP-109（无新纠偏）')
print('  更新时间               %s' % TS)
