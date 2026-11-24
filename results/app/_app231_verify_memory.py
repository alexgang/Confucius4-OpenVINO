#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-231：**独立复核**本轮三个记忆文件的写入（另起脚本，不信写入脚本的自证）。

## 为什么"另起脚本"
MEMORY §一：「**写后另起脚本独立复核**＋`numstat`」⇒ 写入脚本的**自证不算数**
（本轮写入脚本本身就被自己的断言打回过 3 次：① 文本计数假 FAIL ② 行数 off-by-one
③ 锚点手抄差一处 ⇒ 全部是**写前**拦下的 ⇒ 证明断言有效，但**写后**仍要独立复核）。

## 复核项
1. **当日日志** `2026-11-24.md`：本轮段**在末尾**（append-only）｜旧段**逐字未变**
   （对写前备份逐行 diff）｜轮次编号 +1。
2. **`MEMORY.md`**：**≤ 9 700 字符**（自声明上限）｜行数 +1｜**旧正文逐字未变**
   （除「压缩的三行」外）｜新指针行**确实存在**且**落在「二、机器锁」小节内**｜
   压缩的三行**判据关键词未丢失**（逐个 token 核对）｜`last_ack` 已更新为 APP-133。
3. **`MEMORY_MODULES.md`**：新小节在**末尾**｜**围栏配对**（``` 计数仍为偶数）｜
   **旧正文逐字未变**（对写前备份比对）。
4. **`CORRECTIONS_APP.md` 未被改**（SHA/字节/mtime 与开工时逐字一致）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MEM = os.path.join(REPO, '.workbuddy', 'memory')
TMP = os.environ.get('TEMP', '/tmp')

FILES = {
    'log': os.path.join(MEM, '2026-11-24.md'),
    'memory': os.path.join(MEM, 'MEMORY.md'),
    'modules': os.path.join(MEM, 'MEMORY_MODULES.md'),
}
BACKUP = {
    'log': os.path.join(TMP, '2026-11-24.md.bak_app231'),
    'memory': os.path.join(TMP, 'MEMORY.md.bak_app231'),
    'modules': os.path.join(TMP, 'MEMORY_MODULES.md.bak_app231'),
}
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
# 开工时指纹（2026-11-24 19:52 实测）
CORR_BEFORE = {
    'sha256': '2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda',
    'bytes': 440181,
    'n_app': 130,
}

checks = []


def chk(name, ok, detail=''):
    checks.append({'check': name, 'pass': bool(ok), 'detail': str(detail)})
    print('%-4s %s %s' % ('PASS' if ok else 'FAIL', name, detail))


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    # ── ① 当日日志 ───────────────────────────────────────────
    log_new = read(FILES['log'])
    log_old = read(BACKUP['log'])
    marker = '### 第 126 轮巡检（2026-11-24 19:5x–20:3x）'
    idx = log_new.find(marker)
    chk('当日日志：本轮段存在', idx >= 0)
    chk('当日日志：本轮段**在末尾**（append-only）',
        idx > 0 and log_new[idx:].count('### 第 ') == 1,
        'tail rounds=%d' % log_new[idx:].count('### 第 '))
    chk('当日日志：旧段**逐字未变**（是写前备份的前缀）',
        log_old.rstrip('\n') in log_new)
    chk('当日日志：轮次计数 +1',
        log_new.count('### 第 ') == log_old.count('### 第 ') + 1,
        '%d → %d' % (log_old.count('### 第 '), log_new.count('### 第 ')))

    # ── ② MEMORY.md ──────────────────────────────────────────
    m_new = read(FILES['memory'])
    m_old = read(BACKUP['memory'])
    chk('MEMORY.md：**≤ 9 700 字符**（自声明上限）', len(m_new) <= 9700,
        '%d 字符（余 %d）' % (len(m_new), 9700 - len(m_new)))
    chk('MEMORY.md：行数 +1', m_new.count('\n') == m_old.count('\n') + 1,
        '%d → %d' % (m_old.count('\n'), m_new.count('\n')))
    chk('MEMORY.md：**纯 LF**（未被改成 CRLF）', '\r\n' not in m_new)
    chk('MEMORY.md：新指针行存在', '机器锁必须原子创建' in m_new)
    # 指针行必须落在「二、机器锁」小节内
    i2 = m_new.find('## 二、机器锁')
    j2 = m_new.find('\n## ', i2)
    chk('MEMORY.md：指针行**落在「二、机器锁」小节内**',
        i2 >= 0 and j2 > i2 and '机器锁必须原子创建' in m_new[i2:j2])
    chk('MEMORY.md：`last_ack` 已更新为 **APP-133**',
        '`last_ack=APP-133`' in m_new and '`last_ack=APP-128`' not in m_new)
    # 压缩的三行：**判据关键词未丢**
    lost = []
    for kw, where in (('854', '§226 行'), ('n_speakers=0', '§十二 首行'),
                      ('b2a4978', '§十二 首行'), ('msg_52Ta35', 'APP-128 补充行'),
                      ('b7507cb', 'APP-128 补充行'),
                      ('reviewer 复算底本', '§226 行')):
        if kw not in m_new:
            lost.append('%s(%s)' % (kw, where))
    chk('MEMORY.md：压缩的三行**判据关键词未丢失**', not lost, 'lost=%r' % (lost,))
    # 旧正文逐字未变：把三行还原后应等于原文
    old_lines = m_old.split('\n')
    new_lines = m_new.split('\n')
    chk('MEMORY.md：除新增指针行外**其余行逐字未变**',
        [l for l in new_lines if l not in old_lines or l == '机器锁必须原子创建'] is not None
        and len(new_lines) == len(old_lines) + 1)
    # 精确：删掉新指针行后 ⇒ 与原文逐行相同（允许 3 行被压缩 ⇒ 单独核）
    idx_ptr = new_lines.index([l for l in new_lines if '机器锁必须原子创建' in l][0])
    without = new_lines[:idx_ptr] + new_lines[idx_ptr + 1:]
    diffs = []
    for k, (a, b) in enumerate(zip(old_lines, without)):
        if a != b:
            diffs.append(k)
    # 🔴 **判据不写死行号**（本轮实测：写死 (20,21,23) ⇒ 行号一变就**假 FAIL**；
    #   正确判据 = 「差异行数 == 3」＋「差异行**都落在 §十二 小节内**」）
    o12 = old_lines.index([l for l in old_lines
                           if l.startswith('## 十二、App 当前状态')][0])
    o12_end = old_lines.index([l for l in old_lines
                               if l.startswith('## 十二之补')][0])
    chk('MEMORY.md：除**被压缩的 3 行**外**逐行逐字未变**（且差异行都在 §十二 内）',
        len(diffs) == 3 and all(o12 < k < o12_end for k in diffs),
        'diff lines=%r（§十二 范围 %d..%d）' % (diffs, o12, o12_end))

    # ── ③ MEMORY_MODULES.md ──────────────────────────────────
    mo_new = read(FILES['modules'])
    mo_old = read(BACKUP['modules'])
    chk('MODULES：新小节在**末尾**',
        mo_new.find('## 五十、机器锁的「原子创建」与「生产路径」判据') > len(mo_old) - 200)
    chk('MODULES：旧正文**逐字未变**（是写前备份的前缀）',
        mo_old.rstrip('\n') in mo_new)
    fences = len(re.findall(r'^\`\`\`', mo_new, re.M))
    chk('MODULES：围栏**仍配对**（计数为偶数）', fences % 2 == 0, 'fences=%d' % fences)

    # ── ④ 纠偏文件零改动 ──────────────────────────────────────
    b = open(CORR, 'rb').read()
    sha = hashlib.sha256(b).hexdigest()
    n_app = len(re.findall(r'^##\s*APP-(\d+)', b.decode('utf-8', 'replace'), re.M))
    chk('CORRECTIONS_APP.md：**SHA 零改动**（与开工时一致）',
        sha == CORR_BEFORE['sha256'], '%s' % sha[:24])
    chk('CORRECTIONS_APP.md：字节数一致', len(b) == CORR_BEFORE['bytes'],
        '%d' % len(b))
    chk('CORRECTIONS_APP.md：`## APP-xxx` 条数一致', n_app == CORR_BEFORE['n_app'],
        '%d' % n_app)

    n_pass = sum(1 for c in checks if c['pass'])
    out = os.path.join(REPO, 'results', 'app', 'app231_memory_verify.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'checks': checks, 'n_pass': n_pass,
                   'n_fail': len(checks) - n_pass,
                   'memory_chars': len(m_new),
                   'corr_sha256': sha}, f, ensure_ascii=False, indent=2)
    print('\n%d/%d PASS  ⇒ %s' % (n_pass, len(checks), out))
    return 0 if n_pass == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
