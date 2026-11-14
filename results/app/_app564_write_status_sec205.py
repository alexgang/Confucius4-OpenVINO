#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app564_write_status_sec205.py —— 写 STATUS §205（append-only）＋ 归档 §204。

纪律（全部 fail-closed：**任何自检不过 ⇒ 零写入**）：
  · 只**追加** `## §N` 章节，不回头改旧章节；旧结论错了在新章节里写「撤回 §x」；
  · `last_ack` 无新纠偏 ⇒ **保持 APP-109**（不写自己的编号）；
  · 「更新时间」用 **Get-Date 实测值**（由调用方传入）；
  · 压缩：把 §204 正文**整块逐字归档**，活文档保留 §204 **标题行** ＋ 1 行指针；
  · **还原式复核**：把本轮**所有**增量（新增章节 ＋ 新插入行 ＋ 指针行 ＋ 头部
    时间戳行）**逐一逆向还原** ⇒ 必须与开工备份**逐字节相同**；
  · 上限 **40 000 B／300 行**（APP-052④）、纯 LF、无 BOM；
  · 落盘一律「写临时文件 → `os.replace`」＋ 写后逐字节复核（§204 真踩过 0 B）。
"""
import hashlib
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec204_20261114.md')
BODY_FILE = os.path.join(REPO, 'results', 'app', '_app565_sec205_body.txt')
SUMMARY_FILE = os.path.join(REPO, 'results', 'app', '_app566_sec205_summary.txt')
TS = sys.argv[1] if len(sys.argv) > 1 else '2026-11-14 20:52:02'
MAXB, MAXL = 40000, 300

base = open(STATUS, 'rb').read()
assert b'\r' not in base, '开工文件含 CR（行尾不是纯 LF）'
assert base[:3] != b'\xef\xbb\xbf', '开工文件有 BOM'
base_txt = base.decode('utf-8')

# ── 定位 §204（应是最后一节）──
i204 = base_txt.index('## §204 ')
sec204 = base_txt[i204:]                      # 标题行 ＋ 正文，到 EOF
title204 = sec204.split('\n')[0]
assert base_txt.count(title204) == 1, '§204 标题行不唯一'
last_line = [l for l in sec204.rstrip('\n').split('\n') if l.strip()][-1]
assert last_line.startswith('> **⑫'), '§204 不是最后一节：%r' % last_line[:40]

# ── 归档件正文块（含标题行）──
block204 = sec204.rstrip('\n')
sha204 = hashlib.sha256(block204.encode('utf-8')).hexdigest()
arch = (
    '# STATUS_APP §204 整块逐字归档（2026-11-14）\n'
    '\n'
    '归档时间：%s\n'
    '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §205 出空间。\n'
    '正文一字未删（标题行仍留在活文档）。\n'
    '\n'
    '§204 正文块 SHA256（含标题行）：%s（%d B）\n'
    '\n'
    '---- 以下为 §204 原文，逐字 ----\n'
    % (TS, sha204, len(block204.encode('utf-8')))
) + block204 + '\n'

# ── §205 正文：完整正文进 companion（APP-052④ 限额），活文档只留摘要 ──
FULL_BODY = open(BODY_FILE, encoding='utf-8').read().rstrip('\n')
assert FULL_BODY.startswith('## §205 '), '§205 完整正文开头不对'
assert FULL_BODY.count('\n> ') >= 11, '§205 完整正文形状不对（条目数不足）'
DETAIL = os.path.join(REPO, 'status', 'app',
                      'STATUS_APP_sec205_detail_20261114.md')
detail_txt = (
    '# STATUS_APP §205 完整正文（companion，2026-11-14）\n'
    '\n'
    '归档原因：活文档逼近 **40 000 B** 上限（APP-052④）⇒ §205 完整正文放 companion，\n'
    '活文档只留摘要（§205 标题行 ＋ 摘要条目 ＋ 指针行）。\n'
    '生成时间：%s\n'
    '\n'
    '§205 完整正文 SHA256：%s（%d B）\n'
    '\n'
    '---- 以下为 §205 完整正文，逐字 ----\n'
    % (TS, hashlib.sha256(FULL_BODY.encode('utf-8')).hexdigest(),
       len(FULL_BODY.encode('utf-8')))
) + FULL_BODY + '\n'
detail_sha = hashlib.sha256(FULL_BODY.encode('utf-8')).hexdigest()
detail_len = len(FULL_BODY.encode('utf-8'))

SUMMARY = open(SUMMARY_FILE, encoding='utf-8').read().rstrip('\n')
assert SUMMARY.startswith('## §205 '), '§205 摘要开头不对'
assert '"""' not in SUMMARY, '§205 摘要里含三引号'
SEC205 = SUMMARY.replace(
    '（**7 789 B**／SHA256 见本节末）',
    '（**%d B**／SHA256 `%s`）' % (detail_len, detail_sha))
assert ('**%d B**／SHA256 `%s`' % (detail_len, detail_sha)) in SEC205, \
    '摘要里没把 companion 的字节/SHA 填进去'

POINTER204 = ('> 🔴 **本节正文已整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_sec204_20261114.md`'
              '（块 SHA256 `%s`）；活文档保留 §204 标题行 ＋ 1 行指针。'
              % sha204)

RECENT = ('> 🔴 %s ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：'
          '6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 逐字未变、'
          'agent-mail 仍 `not_bound`、`conversation_search` 0 命中、'
          '`NOTICE` 最新 11-05、git 0/0、`MACHINE_LOCK` 无）｜'
          '🔴 **修掉 Special MVP 两个真缺陷：sp2 的 MANIFEST 指向 sp1'
          '（重定向是死代码）＋ 出包闸门对包内容 0 字节验证（验收后改包照样能出包）**｜'
          '**鉴别力矩阵 12/12 PASS**｜**客户包写入仅 sp2 的 MANIFEST 一个字段**｜'
          '**未打包／未改产品代码**\n' % TS)

# ── 组装新内容 ──
new = base_txt
old_ts_line = [l for l in new.split('\n') if l.startswith('更新时间: ')]
assert len(old_ts_line) == 1, '头部「更新时间」行不唯一'
new = new.replace(old_ts_line[0], '更新时间: ' + TS)
ru = '## 最近更新\n'
assert new.count(ru) == 1, '「## 最近更新」标题不唯一'
new = new.replace(ru, ru + RECENT)
assert new.count(sec204) == 1, '§204 块定位失败'
new = new.replace(sec204, title204 + '\n\n' + POINTER204 + '\n')
new = new.rstrip('\n') + '\n\n' + SEC205

nb = new.encode('utf-8')
nl = nb.count(b'\n')
checks = [
    ('字节上限', len(nb) <= MAXB, '%d B（上限 %d）' % (len(nb), MAXB)),
    ('行数上限', nl <= MAXL, '%d 行（上限 %d）' % (nl, MAXL)),
    ('纯 LF', b'\r' not in nb, 'CR=%d' % nb.count(b'\r')),
    ('无 BOM', nb[:3] != b'\xef\xbb\xbf', ''),
    ('§204 标题行仍在且唯一', new.count(title204) == 1, ''),
    ('§205 为最后一节',
     new.rstrip('\n').rfind('## §205 ') > new.rstrip('\n').rfind('## §204 '), ''),
    ('最近更新条目在标题后',
     new.split(ru)[1].split('\n')[0].startswith('> 🔴 %s' % TS), ''),
    ('归档块与开工逐字节一致',
     block204.encode('utf-8') in arch.encode('utf-8'), ''),
    ('last_ack 仍 APP-109', 'last_ack: APP-109' in new, ''),
]

# ── 还原式复核：逐一逆向还原本轮**所有**增量 ──
rest = new
cut = rest.rindex('\n\n## §205 ')
rest = rest[:cut] + '\n'
rest = rest.replace(title204 + '\n\n' + POINTER204 + '\n', sec204)
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
if os.path.isfile(ARCHIVE):
    old_arch = open(ARCHIVE, encoding='utf-8').read()
    assert block204 in old_arch, '已存在的归档件与开工 §204 块不一致 ⇒ 中止'
    arch_action = '已存在（write-once，只校验未重写）'
else:
    atomic_write(ARCHIVE, arch)
    arch_action = '新写入'
if os.path.isfile(DETAIL):
    old_det = open(DETAIL, encoding='utf-8').read()
    assert FULL_BODY in old_det, '已存在的 companion 与本轮 §205 完整正文不一致 ⇒ 中止'
    det_action = '已存在（write-once，只校验未重写）'
else:
    atomic_write(DETAIL, detail_txt)
    det_action = '新写入'
atomic_write(STATUS, nb.decode('utf-8'))
assert open(STATUS, 'rb').read() == nb, '落盘后校验失败（文件与内存不一致）'
assert FULL_BODY in open(DETAIL, encoding='utf-8').read(), 'companion 写盘后校验失败'
print('\n✅ 已写入：')
print('  STATUS_APP.md          %d B / %d 行（开工 %d B）' % (len(nb), nl, len(base)))
print('  §204 归档块 SHA256     %s（%d B）' % (sha204, len(block204.encode('utf-8'))))
print('  归档件 %s  %d B（%s）' % (os.path.relpath(ARCHIVE, REPO),
                                   len(arch.encode('utf-8')), arch_action))
print('  companion %s  %d B（%s）｜正文块 SHA256 %s'
      % (os.path.relpath(DETAIL, REPO), len(detail_txt.encode('utf-8')),
         det_action, detail_sha))
print('  last_ack 保持          APP-109（无新纠偏）')
print('  更新时间               %s' % TS)
