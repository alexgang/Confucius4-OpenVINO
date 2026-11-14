#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app554_write_status_sec202.py —— 写 `status/app/STATUS_APP.md` 的 §202。

🔴 **纪律（APP-052④ / §185 归档纪律 / 只追加）**：
  · 活文档逼近 **40 000 B** ⇒ **先归档老正文**（§200／§201 两节 ＋ 最近更新里
    最旧 3 条，逐字）⇒ 活文档换**指针行**（**标题行仍保留**）⇒ 再追加 §202；
  · **旧正文一字不删** ⇒ 自检用**还原式复核**（把指针行换回原文 ⇒ 必须
    与开工时的文档**逐字节相同**），**不按行号比**；
  · 头部只动 `last_ack` 与 `更新时间` 两行；`更新时间` 用 **Get-Date 实测值**；
  · 「最近更新」**只加一行**（新的在最前）；
  · **先跑完自检再落盘**（fail-closed ⇒ 自检不过则**零写入**）。
"""
import hashlib
import os
import re
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive')
RESULTS = os.path.join(REPO, 'results', 'app')

# ── 要归档的三样东西 ──
SEC_ARCHIVE = [
    ('§200', 'STATUS_APP_sec200_20261114.md'),
    ('§201', 'STATUS_APP_sec201_20261114.md'),
]
RECENT_ARCHIVE = ('STATUS_APP_recent_updates_20261114.md',
                  ['> 🔴 2026-11-13 22:48:21 ｜',
                   '> 🔴 2026-11-13 22:21:35 ｜',
                   '> 🔴 2026-11-13 21:27:28 ｜'])


def get_date():
    """`Get-Date` 实测值（**不推算**）。"""
    p = subprocess.run(['powershell', '-NoProfile', '-NonInteractive',
                        '-Command', 'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
                       capture_output=True, text=True, timeout=60)
    return (p.stdout or '').strip()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def find_section(t, key):
    """返回 (标题行, 起点, 终点, 正文)。"""
    idx = [(m.start(), m.group(0)) for m in re.finditer(r'^## .*$', t, re.M)]
    for i, (pos, title) in enumerate(idx):
        if not title.startswith('## ' + key + ' '):
            continue
        end = idx[i + 1][0] if i + 1 < len(idx) else len(t)
        nl = t.index('\n', pos)
        return t[pos:nl], pos, end, t[nl + 1:end].rstrip('\n')
    raise RuntimeError('找不到章节 %s' % key)


def find_recent_block(t, prefixes):
    """最近更新里**连续**的若干行（按前缀定位）⇒ 返回 (整块文本, 起点, 终点)。"""
    lines = t.split('\n')
    offs, pos = [], 0
    for l in lines:
        offs.append((pos, l))
        pos += len(l) + 1
    hit = [(o, l) for (o, l) in offs if any(l.startswith(p) for p in prefixes)]
    if len(hit) != len(prefixes):
        raise RuntimeError('最近更新：定位到 %d 行（应 %d 行）'
                           % (len(hit), len(prefixes)))
    hit.sort()
    start = hit[0][0]
    end = hit[-1][0] + len(hit[-1][1])
    if hit[-1][0] - hit[0][0] > 20000:
        raise RuntimeError('最近更新：目标行不连续')
    return t[start:end], start, end


def main():
    orig = open(STATUS, 'rb').read()
    if orig.count(b'\r\n'):
        raise RuntimeError('活文档含 CRLF，先归一化')
    t = orig.decode('utf-8')
    ts = get_date()

    jobs = []          # 每件：{'file','block','old','new','sha256','bytes','hdr'}

    # ── ① 两节老正文 ──
    for key, fname in SEC_ARCHIVE:
        title_line, pos, end, body = find_section(t, key)
        block = t[pos:end].rstrip('\n')
        bb = block.encode('utf-8')
        hdr = ('# STATUS_APP %s 整块逐字归档（2026-11-14）\n\n'
               '归档时间：%s\n'
               '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §202 出空。\n'
               '正文一字未删（标题行仍留在活文档）。\n\n'
               '%s 正文块 SHA256（含标题行）：%s（%d B）\n\n'
               '---- 以下为 %s 原文，逐字 ----\n'
               % (key, ts, key, sha256_bytes(bb), len(bb), key))
        ptr = ('> **%s 压缩**（2026-11-14）：**正文整块逐字归档** ⇒ '
               '`status/archive/%s`（正文块 %d B／SHA256 `%s`）；'
               '活文档保留 %s 标题行 ＋ 1 行指针。'
               % (key, fname, len(bb), sha256_bytes(bb), key))
        jobs.append({'file': fname, 'block': block, 'hdr': hdr,
                     'old': block,
                     'new': title_line + '\n\n' + ptr,
                     'sha256': sha256_bytes(bb), 'bytes': len(bb),
                     'kind': key})

    # ── ② 最近更新里最旧 3 条 ──
    fname, prefixes = RECENT_ARCHIVE
    blk, _s, _e = find_recent_block(t, prefixes)
    bb = blk.encode('utf-8')
    hdr = ('# STATUS_APP 「最近更新」较旧 3 条整块逐字归档（2026-11-14）\n\n'
           '归档时间：%s\n'
           '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §202 出空。\n'
           '正文一字未删（原文逐字保留在本文件）。\n\n'
           '正文块 SHA256：%s（%d B）\n\n'
           '---- 以下为「最近更新」较旧 3 条原文，逐字 ----\n'
           % (ts, sha256_bytes(bb), len(bb)))
    ptr = ('> 🔴 本节 3 条较旧「最近更新」条目（2026-11-13 21:27:28「Special MVP 出包」'
           '／22:21:35「目标机拷贝被凭据挡住」／22:48:21「目标机拷贝已完成」）'
           '原文已**整块逐字归档** ⇒ `status/archive/%s`（%d B／块 SHA256 `%s`）。'
           % (fname, len(bb), sha256_bytes(bb)))
    jobs.append({'file': fname, 'block': blk, 'hdr': hdr,
                 'old': blk, 'new': ptr,
                 'sha256': sha256_bytes(bb), 'bytes': len(bb),
                 'kind': '最近更新×3'})

    # ── ③ 活文档：正文 → 指针行 ──
    new = t
    for j in jobs:
        if new.count(j['old']) != 1:
            raise RuntimeError('%s 在活文档里命中 %d 次（应 1）'
                               % (j['kind'], new.count(j['old'])))
        new = new.replace(j['old'], j['new'], 1)

    # ── ④ 还原式复核：指针换回原文 ⇒ 必须与开工逐字节相同 ──
    back = new
    for j in jobs:
        if back.count(j['new']) != 1:
            raise RuntimeError('%s 指针行命中 %d 次（应 1）'
                               % (j['kind'], back.count(j['new'])))
        back = back.replace(j['new'], j['old'], 1)
    if back != t:
        raise RuntimeError('还原式复核失败：换回原文后与开工文档不一致')

    # ── ⑤ 头部两行 ──
    m = re.search(r'^last_ack: APP-(\d+)$', new, re.M)
    if not m:
        raise RuntimeError('头部没有 last_ack 行')
    if m.group(1) != '107':
        raise RuntimeError('开工 last_ack 不是 APP-107（实际 %s）' % m.group(1))
    new = new[:m.start()] + 'last_ack: APP-109' + new[m.end():]

    m2 = re.search(r'^更新时间: .*$', new, re.M)
    if not m2:
        raise RuntimeError('头部没有 更新时间 行')
    new = new[:m2.start()] + ('更新时间: %s' % ts) + new[m2.end():]

    # ── ⑥ 最近更新：加一行（最新在最前）──
    rec = ('> 🔴 %s ｜ **执行 APP-108／APP-109**（last_ack 107→**109**）：'
           '**修掉 Special MVP 真缺陷**（`current_profile()` 从不返回 '
           "'specialmvp' ⇒ 旧配置覆盖出厂默认 **MT=NPU→GPU.0**）⇒ **出 sp2**"
           '（包内复验 **PASS**：三配置全解析出 GPU.0/NPU/CUDA）；'
           '**OPEN-1（0xC0000409）三臂对照已跑**（10 分钟 × 3 臂 rc 全 0，'
           '**含原组合**）⇒ 验收结论改写为「PASS（有 1 项未结：退出码异常）」，'
           '不写 13/13；**10 句丢弃 = 全部 late_drop**（阈值 6.0 s，非 8 s）＋'
           '§195 ③ 的「?」字段已补齐（CUDA／加载 25.4 s／预热 2.0 s）｜'
           '**未打包 zip**（用户不通知不打包）／未改 sp1／未动 B 机\n'
           % ts)
    h = re.search(r'^## 最近更新\n', new, re.M)
    if not h:
        raise RuntimeError('找不到「## 最近更新」')
    new = new[:h.end()] + rec + new[h.end():]

    # ── ⑦ 追加 §202 摘要 ──
    sec = open(os.path.join(RESULTS, '_sec202_body.txt'),
               encoding='utf-8').read().rstrip('\n').replace('{{TS}}', ts)
    if not sec.startswith('## §202 ') or '{{TS}}' in sec:
        raise RuntimeError('§202 正文异常')
    new = new.rstrip('\n') + '\n\n' + sec + '\n'

    # ── ⑧ 自检（fail-closed）──
    nb = new.encode('utf-8')
    problems = []
    if len(nb) > 40000:
        problems.append('字节数 %d > 40000' % len(nb))
    if nb.count(b'\n') > 300:
        problems.append('行数 %d > 300' % nb.count(b'\n'))
    if b'\r\n' in nb:
        problems.append('含 CRLF')
    if nb[:3] == b'\xef\xbb\xbf':
        problems.append('含 BOM')
    if new.count('## §202 ') != 1:
        problems.append('§202 标题命中 %d 次' % new.count('## §202 '))
    if new.count('last_ack: APP-109') != 1:
        problems.append('last_ack 行数异常')
    if 'last_ack: APP-107' in new:
        problems.append('旧 last_ack 仍在')
    # 老章节标题：数量必须与**开工时一致**（不许丢、不许被我这边重复）。
    # 🔴 注意：开工文档里本来就有**重名**标题（§170 与 §183 的指针行出现 2 次）
    #    ⇒ 判据用「与开工一致」，**不是**「恰好 1 次」（否则是假 FAIL）。
    for title in re.findall(r'^## .*$', t, re.M):
        if title.startswith('## §') and new.count(title) != t.count(title):
            problems.append('老章节标题数量变了：%s（开工 %d → 现在 %d）'
                            % (title[:40], t.count(title), new.count(title)))
    for j in jobs:
        full = j['hdr'] + j['block'] + '\n'
        if j['block'] not in full:
            problems.append('归档件自检失败：%s' % j['kind'])
    if problems:
        raise RuntimeError('自检不过 ⇒ 零写入：\n  - ' + '\n  - '.join(problems))

    # ── ⑨ 落盘（先归档件，再活文档）──
    for j in jobs:
        p = os.path.join(ARCHIVE, j['file'])
        if os.path.exists(p):
            raise RuntimeError('归档件已存在（不覆盖）：%s' % p)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(j['hdr'] + j['block'] + '\n')
    with open(STATUS, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)

    rb = open(STATUS, 'rb').read()
    if rb != nb:
        raise RuntimeError('落盘后字节与自检时不一致')
    print('OK  bytes=%d (limit 40000)  lines=%d (limit 300)  ts=%s'
          % (len(rb), rb.count(b'\n'), ts))
    for j in jobs:
        print('    归档 %-12s -> %s  (%d B, sha %s)'
              % (j['kind'], j['file'], j['bytes'], j['sha256'][:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
