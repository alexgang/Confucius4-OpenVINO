#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_write_status179.py —— 写 STATUS §179（勘误：§178 引用的判据行数是「自指快照」）。

🔴 起因：§178 归档件里写的判据结果是「**177 行**／OK 173／FAIL 0」，
   那是**写 §178 那一刻**的行数；等 §178 自身（归档件 + 判据脚本 + 判据产物）也入库后，
   判据多看到 7 行 ⇒ **稳态是 184 行**（OK 179／FAIL 0）。
   ⇒ §178 的「177 行」是**自指快照**（MEMORY 老坑：「自指大小必须与磁盘实测一致」）。
   ⇒ 归档件 write-once 不可回改 ⇒ 在**新章节** §179 写明勘误 + 稳态真值。

纪律：只追加 §179；旧章节正文一字不改；CORR 只读。
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec179_20261111.md')
NOW = '2026-11-11 18:55:00'

ARCHIVE_BODY = """# STATUS_APP §179（归档件 · write-once）

> 🔴 **归档件 = write-once**：本文件落盘后**逐字节不再改**；活文档 `status/app/STATUS_APP.md`
> 只保留 ≤3 行索引（APP-052 ④）。任何更正都写进**新章节**，不改本文件。

## §179 勘误（2026-11-11 18:55:00）｜**撤回 §178 归档件里的「判据 177 行」这一数字** ⇒ **稳态真值 = 184 行**（OK 179／FAIL 0／反证 3/3）｜§178 的**结论与修复本身全部成立、不变**

---

### 一、勘误内容（**只改数字，不改结论**）

§178 归档件第四节末写：

> **判据结果**：`results/app/app468_status_git_halfdelivery.json`
> ⇒ **177 行／OK 173／FAIL 0／MISSING 0／OK_GITIGNORED 3／KNOWN_ERRATA 1／无 SHA 声明 143／反证 3/3 全触发 ⇒ PASS**。

🔴 **「177 行」是「写 §178 那一刻」的快照，不是稳态**：
判据会审计**活文档 + 它引用的归档件里引用到的每个产物**
⇒ 等 §178 自身也落盘并入库后（归档件 `sec178` ＋ 判据脚本 ＋ 判据产物 ＋
`sec160_20261109.md` 孤儿重复件 ＋ 脚本/产物在活文档与归档件里**各被引用一次**），
**多出 7 行** ⇒ **稳态 = 184 行**。

| 项 | §178 归档件写的 | **稳态真值（本轮实测 2 次一致）** |
|---|---|---|
| 审计行数 | 177 | **184** |
| OK | 173 | **179** |
| **FAIL** | **0** | **0**（**不变**） |
| MISSING | 0 | **0**（不变） |
| OK_GITIGNORED | 3 | **3**（不变） |
| OK_DUPLICATE | （该分类是 §178 落盘后补的） | **1**（`sec160_20261109.md` 孤儿重复件） |
| KNOWN_ERRATA | 1 | **1**（不变） |
| 无 SHA 声明 | 143 | **150** |
| **反证** | 3/3 全触发 | **3/3 全触发**（不变） |

🔴 **不撤回的部分**：**FAIL = 0**、**反证 3/3**、**6 处 git 半交付已修复**、
**CRLF 形态这个新发现**、**根因分析**（§173 判据查不出 git 半交付）⇒ **全部成立**。
**只撤回「177 行」这一个数字** ⇒ 改为 **184 行**。

### 二、🔴 教训（**已并入判据设计**）

> 🔴 **自指数字必须以磁盘实测的稳态为准**（MEMORY 老坑：「自指大小必须与磁盘实测一致（差 2 B 也要改）」）。
> 🔴 本例的具体形态：**审计对象包含审计结论自身所在的文档** ⇒ 行数会随「写完自己」而增长
> ⇒ 任何「N 行」的自指数字都必然有 1 轮的偏差。
> ⇒ 处置：① 归档件 write-once ⇒ **不回改**，在**新章节**写勘误（本文）；
> ② 判据的**结论口径不依赖行数**（`FAIL=0`／反证 3/3 才是不变量）⇒ 结论不受自指影响；
> ③ **行数只作参考**，不作判据阈值。

### 三、本轮其余状态（未变）

- `CORRECTIONS_APP.md` **全程只读**：SHA `219ef841…`／308 340 B／**100 条**／最大 APP-100 ⇒ **SHA 零改动**；
- `last_ack` 仍是 **APP-100**（**无编号更大的新条目 ⇒ 无新纠偏需执行**）；
- **未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未改任何默认值或产品判据／未占设备／未持锁**；
- 节点仍是 **等 reviewer 复核 §174／§175／§177／§178**。
"""

LIVE_SECTION = """
## §179 勘误（2026-11-11 18:55:00）｜**撤回 §178 归档件里的「判据 177 行」这一数字** ⇒ **稳态真值 = 184 行**（OK 179／FAIL 0／反证 3/3）｜§178 的**结论与修复本身全部成立、不变**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec179_20261111.md`（__ARCH_B__ B／SHA256 `__ARCH_SHA__`）｜**归档件逐字节未动**（write-once）。
> 🔴 **勘误**：§178 归档件写的「177 行／OK 173」是**写 §178 那一刻的自指快照**（判据要审计活文档与归档件里引用到的每个产物 ⇒ §178 自身入库后**多 7 行**）⇒ **稳态 = 184 行／OK 179**（本轮实测 **2 次一致**）；**只撤回这一个数字** ⇒ **FAIL = 0／MISSING = 0／反证 3/3／6 处半交付已修复／CRLF 形态这个新发现** —— **全部成立、不变**。
> 🔴 **教训**：**自指数字必须以磁盘实测稳态为准**；且判据的**结论口径不依赖行数**（`FAIL=0`＋反证 3/3 才是不变量）⇒ **结论不受自指影响**，行数只作参考、**不作阈值**。
"""


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    corr_before = open(CORR, 'rb').read()
    orig = open(STATUS, 'rb').read()
    text = orig.decode('utf-8')

    if os.path.exists(ARCH):
        print('ABORT: 归档件已存在（write-once）')
        return 1
    arch_bytes = ARCHIVE_BODY.encode('utf-8')
    arch_sha = sha(arch_bytes)
    live = (LIVE_SECTION
            .replace('__ARCH_B__', '{:,}'.format(len(arch_bytes)).replace(',', ' '))
            .replace('__ARCH_SHA__', arch_sha))

    new_text = text.rstrip('\n') + '\n' + live
    nb = new_text.encode('utf-8')
    nl = nb.count(b'\n') + 1

    checks = [
        ('bytes<=40000', len(nb) <= 40000, str(len(nb))),
        ('lines<=300', nl <= 300, str(nl)),
        ('no CRLF', nb.count(b'\r\n') == 0, str(nb.count(b'\r\n'))),
        ('§178 present', '## §178 ' in new_text, ''),
        ('§179 present', '## §179 ' in new_text, ''),
        ('CORR untouched', sha(open(CORR, 'rb').read()) == sha(corr_before), ''),
        ('last_ack=APP-100', 'last_ack: APP-100' in new_text, ''),
        ('old sections kept', len(re.findall(r'(?m)^## §', new_text)) == 24,
         str(len(re.findall(r'(?m)^## §', new_text)))),
    ]
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print('  %-22s %s %s' % (name, 'OK' if ok else 'FAIL', detail))
    if bad:
        print('ABORT: 写前自检未过 ⇒ 源文件零改动')
        return 1

    with io.open(ARCH, 'wb') as f:
        f.write(arch_bytes)
    with io.open(STATUS, 'wb') as f:
        f.write(nb)
    print('WROTE archive: %s (%d B sha %s)' % (ARCH, len(arch_bytes), arch_sha))
    print('WROTE status : %s (%d B %d lines)' % (STATUS, len(nb), nl))
    return 0


if __name__ == '__main__':
    sys.exit(main())
