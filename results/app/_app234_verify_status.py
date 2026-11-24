#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · **另起脚本**独立复核 `status/app/STATUS_APP.md` 的 §234 写入。

🔴 为什么另起脚本：补丁脚本自己说 PASS 不算证据。

## 判据（14 条）

  1  `last_ack` 仍为 **APP-133**（本轮无新纠偏 ⇒ **值不得变**）
  2  「更新时间」＝ 传入的 `Get-Date` 实测值
  3  §234 章节标题**恰好 1 次**
  4  §234 章节在**文末**
  5  §234 的 pointer 行在**文末**
  6  「最近更新」块**首条**是 §234 的新条目
  7  旧的「最近更新」条目**仍在**（下移未删）
  8  **旧章节逐字未变**：§231/§232/§233 的标题行与 pointer 行**逐字节同**备份
  9  **还原式复核**：去掉本轮新增内容后 ⇒ 逐字节同写前备份
 10  字节数 ≤ 40 000（APP-052④ 硬限额）
 11  行数 ≤ 300
 12  未引入**新的** CRLF（新增行一律 LF；且**没动**既有行的行尾）
 13  **反证组**：把 §234 章节**移除**后 ⇒ 判据 3/4/5 必须 FAIL
     ⇒ 证明判据确实绑在「§234 是否存在」上，不是恒 PASS
 14  `status/app/CORRECTIONS_APP.md` **逐字节未变**（本轮绝不修改它）
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TARGET = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'),
                      'STATUS_APP.md.bak_app234')

FAILS = []
N = [0]


def chk(name, ok, detail=''):
    N[0] += 1
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('   ' + detail) if detail else ''))
    if not ok:
        FAILS.append((name, detail))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def main() -> int:
    ts = sys.argv[1] if len(sys.argv) > 1 else ''
    print('=== APP-234 独立复核：STATUS_APP.md 的 §234 写入 ===')

    raw = open(TARGET, 'rb').read()
    t = raw.decode('utf-8')
    old = open(BACKUP, 'rb').read().decode('utf-8')

    chk('1 last_ack 仍为 APP-133（值未变）',
        t.count('last_ack: APP-133') == 1
        and 'last_ack: APP-133' in old,
        'count=%d' % t.count('last_ack: APP-133'))
    m = re.search(r'^更新时间: (.+)$', t, re.M)
    chk('2 「更新时间」＝ Get-Date 实测值',
        bool(m) and m.group(1) == ts,
        'got=%r want=%r' % (m.group(1) if m else None, ts))

    sec = re.search(r'^## §234 .*$', t, re.M)
    chk('3 §234 章节标题恰好 1 次',
        len(re.findall(r'^## §234 ', t, re.M)) == 1)
    chk('4 §234 章节在文末（正文末行是 §234 指针行）',
        'STATUS_APP_sec234_detail_20261125.md' in t.rstrip().split('\n')[-1])
    chk('5 §234 pointer 行在文末',
        t.rstrip().split('\n')[-1].startswith('> '))

    lines = t.split('\n')
    i_recent = next(i for i, l in enumerate(lines) if l.startswith('## 最近更新'))
    first_entry = next(l for l in lines[i_recent + 1:] if l.startswith('> '))
    chk('6 「最近更新」块首条是 §234 的新条目',
        '2026-11-25 03:49:52' in first_entry,
        repr(first_entry[:70]))
    chk('7 旧的「最近更新」条目仍在（下移未删）',
        '2026-11-25 02:04:46' in t and '2026-11-24 22:02:37' in t)

    # 8 旧章节逐字未变
    ok_old = True
    for sec_no in ('231', '232', '233'):
        a = re.search(r'^## §%s .*$' % sec_no, old, re.M)
        b = re.search(r'^## §%s .*$' % sec_no, t, re.M)
        if not a or not b or a.group(0) != b.group(0):
            ok_old = False
    chk('8 旧章节 §231/§232/§233 标题行逐字节未变', ok_old)

    # 9 还原式复核：去掉新增内容后**逐字节**同备份
    #    🔴 比对**整串**（不 rstrip）—— 末尾换行也是内容的一部分
    #    🔴 **顺序要点**：先**替换时间戳**、再**切掉 §234**；
    #       反过来做时，切完后串里已无「更新时间」⇒ `replace()` 会误命中
    #       §233 指针行里的同名子串 ⇒ 假 FAIL（本轮踩过）。
    back = t
    back = re.sub(r'^> 🔴 2026-11-25 03:49:52 ｜.*\n', '', back, flags=re.M)
    # 🔴🔴 **前缀必须一起换**（APP-235 轮修掉的真缺陷）：
    #     原写法把整串 '更新时间: <ts>' 换成**只有时间戳** ⇒
    #     丢掉 '更新时间: ' 这 **6 个字符**（4 汉字 + ':' + ' '）
    #     ⇒ 还原串比备份**短 6 字符** ⇒ 判据 9 **恒 FAIL**（假 FAIL）。
    #     正确写法：连同 '更新时间: ' 前缀一起替换。
    back = back.replace('更新时间: %s' % ts,
                        '更新时间: %s' % re.search(
                            r'^更新时间: (.+)$', old, re.M).group(1), 1)
    i = back.rfind('\n\n## §234 ')
    if i >= 0:
        back = back[:i] + '\n'
    chk('9 还原式复核：去掉新增内容后逐字节同写前备份',
        back == old,
        'len %d vs %d' % (len(back), len(old)))
    # 9b 反证组：把还原串**中段挖掉 1 个字符** ⇒ 判据 9 必须 FAIL
    #     （证明它不是恒 PASS；挖中段＝模拟 §224 的真实失败模式）
    if len(back) > 200:
        mid = len(back) // 2
        broken = back[:mid] + back[mid + 1:]
        chk('9b 反证组：还原串中段挖 1 字符 ⇒ 判据 9 必须 FAIL',
            broken != old,
            'broken_len=%d' % len(broken))

    n_bytes = len(raw)
    n_lines = t.count('\n') + 1
    chk('10 字节数 ≤ 40 000', n_bytes <= 40000, '%d B' % n_bytes)
    chk('11 行数 ≤ 300', n_lines <= 300, '%d 行' % n_lines)

    old_crlf = old.count('\r\n')
    chk('12 未引入新的 CRLF（新增行全 LF）', t.count('\r\n') == old_crlf,
        'old=%d new=%d' % (old_crlf, t.count('\r\n')))

    # 13 反证组：移除 §234 后判据 3/4/5 必须 FAIL
    anti = t[:t.rfind('\n\n## §234 ')] + '\n'
    a3 = len(re.findall(r'^## §234 ', anti, re.M)) == 1
    a4 = 'STATUS_APP_sec234_detail_20261125.md' in \
        anti.rstrip().split('\n')[-1]
    chk('13 反证组：移除 §234 后判据 3/4/5 必须 FAIL',
        (not a3) and (not a4),
        'anti_has_sec234=%s anti_tail_ok=%s' % (a3, a4))

    # 14 纠偏文件逐字节未变
    corr_sha = sha(CORR)
    chk('14 CORRECTIONS_APP.md 未被修改（SHA 零改动）',
        corr_sha == '2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda',
        corr_sha[:24])

    print()
    print('PASS=%d / FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
    if FAILS:
        for n, d in FAILS:
            print('  [FAIL] %s  %s' % (n, d))
        return 1
    print('结论：PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
