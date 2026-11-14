#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app556_verify_status_sec202.py —— **独立**复核 §202 的落盘结果。

🔴 **不复用写者的自检逻辑**（写者的判据自己也可能错）⇒ 本脚本
   只拿「开工备份」和「落盘结果」两个**外部事实**对账：
     ① 三个归档件的正文块与**开工备份里的对应原文**逐字节相同；
     ② **还原式复核**：把活文档里的 3 个指针换回原文 ⇒ 必须与开工备份
        **逐字节相同**（⇒ 旧正文一字未删、也没被改动）；
     ③ 活文档的限额（≤40 000 B／≤300 行）、纯 LF、无 BOM；
     ④ 头部 `last_ack`＝APP-109、只出现一次；
     ⑤ §202 标题恰好 1 次、位置在文末；
     ⑥ §202 摘要里的**证据文件**都真实存在于磁盘。
"""
import hashlib
import os
import re
import sys

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive')
BACKUP = os.path.join(HOME, 'AppData', 'Local', 'Temp',
                       'STATUS_APP.before_sec202.bak')
RESULTS = os.path.join(REPO, 'results', 'app')

JOBS = [
    ('§200', 'STATUS_APP_sec200_20261114.md'),
    ('§201', 'STATUS_APP_sec201_20261114.md'),
    ('最近更新×3', 'STATUS_APP_recent_updates_20261114.md'),
]
#: §202 摘要里引用的证据文件（必须在磁盘上存在）
EVIDENCE = ['app549_sp1_device_resolution.json',
            'app549_sp2_device_resolution.json',
            'app550_specialmvp_sp2_build.json',
            'app551_open1_two_arm.json', 'app551_open1_armC.json',
            'app552_special_profile_check_after_fix.json',
            'app552_specialmvp_dropped_sentences.json',
            'app553_specialmvp_sp2_acceptance.json',
            'app555_sync_ttsworker_sp2.json']

errs = []


def err(msg):
    errs.append(msg)


def block_of(path):
    """从归档件里取出「---- 以下为 … 原文，逐字 ----」之后的正文块
    （**去掉尾部换行**，与 §199 归档件的约定一致）。"""
    t = open(path, encoding='utf-8').read()
    m = re.search(r'^---- 以下为.*原文，逐字 ----$', t, re.M)
    if not m:
        err('归档件 %s 没有「原文」标记行' % os.path.basename(path))
        return None
    i = m.end()
    assert t[i] == '\n'
    blk = t[i + 1:].rstrip('\n')
    # 归档件头部里声明的块 SHA 必须与实际块一致
    dm = re.search(r'正文块 SHA256(?:（含标题行）)?：([0-9a-f]{64})（(\d+) B）',
                   t[:m.start()])
    if dm:
        h = hashlib.sha256(blk.encode('utf-8')).hexdigest()
        if h != dm.group(1):
            err('归档件 %s 声明的 SHA 与实际块不符（声明 %s / 实际 %s）'
                % (os.path.basename(path), dm.group(1)[:16], h[:16]))
        if int(dm.group(2)) != len(blk.encode('utf-8')):
            err('归档件 %s 声明的字节数与实际不符（声明 %s / 实际 %d）'
                % (os.path.basename(path), dm.group(2),
                   len(blk.encode('utf-8'))))
    return blk


if not os.path.isfile(BACKUP):
    err('缺开工备份：%s' % BACKUP)
    print('FAIL'); sys.exit(1)

old_b = open(BACKUP, 'rb').read()
new_b = open(STATUS, 'rb').read()
old = old_b.decode('utf-8')
new = new_b.decode('utf-8')

if b'\r\n' in new_b:
    err('活文档含 CRLF')
if new_b[:3] == b'\xef\xbb\xbf':
    err('活文档含 BOM')
if len(new_b) > 40000:
    err('字节数 %d > 40000' % len(new_b))
if new_b.count(b'\n') > 300:
    err('行数 %d > 300' % new_b.count(b'\n'))

# ① 归档件正文块 vs 开工备份里的原文
blocks = {}
for kind, fname in JOBS:
    p = os.path.join(ARCHIVE, fname)
    if not os.path.isfile(p):
        err('缺归档件 %s' % fname)
        continue
    blk = block_of(p)
    if blk is None:
        continue
    blocks[kind] = blk
    if blk not in old:
        err('归档件 %s 的正文块**不在开工备份里**（不是逐字原文）' % fname)
    print('  归档 %-12s %s  %d B  %s'
          % (kind, fname, len(blk.encode('utf-8')),
             hashlib.sha256(blk.encode('utf-8')).hexdigest()[:16]))

# ② 还原式复核：把活文档里的指针换回原文 ⇒ 必须与开工备份逐字节相同
back = new
for kind, fname in JOBS:
    blk = blocks.get(kind)
    if blk is None:
        continue
    # 指针行：含该归档件文件名的那一行
    lines = [l for l in back.split('\n')
             if ('status/archive/%s' % fname) in l and l.startswith('> ')]
    if len(lines) != 1:
        err('%s 的指针行命中 %d 次（应 1）' % (fname, len(lines)))
        continue
    ptr = lines[0]
    # 🔴 **还原映射要分两种**（这正是独立复核抓到写者之外的问题）：
    #    · 节归档（§200/§201）：活文档里**标题行仍在**，指针行取代的是
    #      **正文** ⇒ 还原＝「标题＋指针」→ 「标题＋原文正文」；
    #    · 「最近更新」归档：指针行取代的是**整块 3 行** ⇒ 还原＝
    #      「指针」→ 「整块原文」。
    if kind.startswith('§'):
        title = blk.split('\n')[0]
        body = blk[len(title):].lstrip('\n')
        # 开工时的分隔符（§200 是空行、§201 没有空行 ⇒ 必须分别处理）
        sep_orig = '\n\n' if blk.startswith(title + '\n\n') else '\n'
        # 活文档里现在的分隔符（指针行前）
        j = back.find(ptr)
        head = back[:j]
        sep_cur = '\n\n' if head.endswith(title + '\n\n') else '\n'
        ph = '\x00PLACEHOLDER_%s\x00' % kind
        if back.count(title + sep_cur + ptr) != 1:
            err('%s 指针定位失败（sep=%r）' % (kind, sep_cur))
        back = back.replace(title + sep_cur + ptr, ph, 1)
        back = back.replace(ph, title + sep_orig + body, 1)
    else:
        ph = '\x00PLACEHOLDER_%s\x00' % kind
        back = back.replace(ptr, ph, 1)
        back = back.replace(ph, blk, 1)

# ②b 把**授权的改动**也退回（头部两行 / 新「最近更新」一行 / §202 整节）
#     ⇒ 之后必须与开工备份**逐字节相同**（⇒ 旧正文一字未删、未被改动）。
old_ack = re.search(r'^last_ack: APP-(\d+)$', old, re.M).group(1)
old_ts = re.search(r'^更新时间: (.*)$', old, re.M).group(1)
back = re.sub(r'^last_ack: APP-\d+$', 'last_ack: APP-%s' % old_ack,
              back, count=1, flags=re.M)
back = re.sub(r'^更新时间: .*$', '更新时间: %s' % old_ts, back, count=1,
              flags=re.M)
# 去掉新「最近更新」一行（含本轮时间戳的那行）
lines = back.split('\n')
lines = [l for l in lines if not (l.startswith('> 🔴 2026-11-14 ')
                                  and '执行 APP-108' in l)]
back = '\n'.join(lines)
# 去掉 §202 整节（到文末）
# 🔴 `back[:i]` **已经**以 '\n' 结尾（i 指向 '\n## §202 ' 里的那个 '\n'，
#    而它前面还有一个 '\n' 留在切片里）⇒ **不要再补 '\n'**（补了就多一行）。
i = back.find('\n## §202 ')
if i >= 0:
    back = back[:i]
if not back.endswith('\n'):
    back += '\n'

if back != old:
    ol = old.split('\n')
    nl = back.split('\n')
    extra = [l for l in nl if l not in ol]
    missing = [l for l in ol if l not in nl]
    err('还原后与开工备份不一致：新增 %d 行 / 丢失 %d 行' % (len(extra),
                                                            len(missing)))
    for m in missing[:3]:
        err('    丢失行：%s' % m[:120])
    for m in extra[:3]:
        err('    多出行：%s' % m[:120])
else:
    print('  还原式复核：PASS（换回原文 + 退回授权改动后与开工备份逐字节相同）')

# ③④⑤
if new.count('last_ack: APP-109') != 1:
    err('last_ack 行数异常')
if 'last_ack: APP-107' in new:
    err('旧 last_ack 仍在')
if new.count('## §202 ') != 1:
    err('§202 标题命中 %d 次' % new.count('## §202 '))
else:
    i = new.index('## §202 ')
    j = new.index('\n## ', i + 5) if '\n## ' in new[i + 5:] else len(new)
    if j >= len(new) - 200:
        print('  §202 位于文末 ✔')
    else:
        err('§202 不在文末')
if not re.search(r'^更新时间: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', new, re.M):
    err('更新时间格式不对')

# ⑥ 证据文件都在磁盘上
for f in EVIDENCE:
    if not os.path.isfile(os.path.join(RESULTS, f)):
        err('缺证据文件 results/app/%s' % f)
print('  证据文件 %d 个全部存在' % len(EVIDENCE))

print()
if errs:
    print('FAIL：')
    for e in errs:
        print('  -', e)
    sys.exit(1)
print('PASS  bytes=%d lines=%d' % (len(new_b), new_b.count(b'\n')))
