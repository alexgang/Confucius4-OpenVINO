#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_write_status180.py —— 写 STATUS §180（勘误 §179 的「184 行」仍是自指快照）。

🔴 起因：§179 写的「稳态真值 = 184 行」**仍然错**——写 §179 自身（归档件 + 脚本 + 产物）
   又让判据多看到 1 行 ⇒ 实际 **185 行**。
   ⇒ 🔴 **正确结论**：判据的审计行数**永远不是定值**（自指 ⇒ 每轮必涨）
   ⇒ 判据的**不变量是 `FAIL=0` ＋ 反证 3/3**，行数只是观察量。

处置（§180）：
  ① **撤回** §179 的「184 行 = 稳态真值」这一措辞 ⇒ 改为「行数是观察量、非定值」；
  ② 给出**实测的当前值**（185 行）并说明它**会随每轮落盘继续变**；
  ③ 把「行数」从判据的**结论口径**里彻底剔除（判据 pass 条件本就不含行数）⇒
     ⇒ 后续轮次**不再需要**为行数写勘误（根因消除，不是逐轮打补丁）；
  ④ 顺带把 §171 的活文档块索引化（腾体积；正文逐字仍在 write-once 归档件 sec171 里）。

纪律：只追加 §180；旧章节正文一字不改（§171 是**索引化**，其正文逐字在归档件里）；CORR 只读。
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
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec180_20261111.md')

ARCHIVE_BODY = """# STATUS_APP §180（归档件 · write-once）

> 🔴 **归档件 = write-once**：本文件落盘后**逐字节不再改**；活文档 `status/app/STATUS_APP.md`
> 只保留 ≤3 行索引（APP-052 ④）。任何更正都写进**新章节**，不改本文件。

## §180 勘误（2026-11-11 18:55:00）｜**撤回 §179 的「184 行 = 稳态真值」措辞** ⇒ **审计行数是观察量、不是定值**；判据的**不变量 = `FAIL=0` ＋ 反证 3/3**（本轮实测 **185 行／OK 180／FAIL 0**）｜§178／§179 的**结论与 6 处修复本身全部成立、不变**

---

### 一、🔴 勘误：为什么「184 行」也错，而且**以后每轮都会错**

§179 写：「**稳态真值 = 184 行**」⇒ 🔴 **这个措辞本身是错的**。

**根因**：判据审计的对象包含**活文档自身引用的产物**
⇒ §178 自身（归档件 ＋ 脚本 ＋ 产物）入库后涨 7 行（177 → 184），
§179 自身（归档件 ＋ 2 个脚本 ＋ 1 个产物 json）入库后又涨 1 行（184 → **185**）
⇒ 🔴 **行数会随每轮落盘持续增长 ⇒ 永远没有「稳态」**。

| 项 | §178 写 | §179 写 | **本轮实测（§180）** |
|---|---|---|---|
| 审计行数 | 177 | 184 | **185** |
| OK | 173 | 179 | **180** |
| **FAIL** | 0 | 0 | **0**（**唯一的不变量**） |
| MISSING | 0 | 0 | **0**（不变量） |
| OK_GITIGNORED | 3 | 3 | 3（观察量） |
| OK_DUPLICATE | （分类后加） | 1 | 1（观察量） |
| KNOWN_ERRATA | 1 | 1 | 1（观察量） |
| 无 SHA 声明 | 143 | 150 | 150（观察量） |
| **反证** | 3/3 | 3/3 | **3/3**（**不变量**） |

🔴 **真正的结论**：判据 `pass` 的判定条件**本来就不含行数**
（代码：`pass = (n_fail == 0 and n_missing == 0 and anti_all_discriminating)`）
⇒ **行数从一开始就不参与结论** ⇒ §179 把行数写进「稳态真值」表是**概念错误**。

### 二、🔴 根因消除（不是逐轮打补丁）

**处置**：把「行数」**彻底从结论口径里剔除** ⇒
① 本节起，STATUS 里**只引用不变量**（`FAIL=0`／`MISSING=0`／反证 3/3）；
② 判据 JSON 的 `n_rows` 字段保留（供调试），但**不作阈值、不作结论**；
③ ⇒ **后续轮次不再需要为行数写勘误**（§178／§179 的两轮勘误是**同一根因的两次症状**，
根因消除后不再复发）。
🔴 对照 MEMORY 老坑「**自指大小必须与磁盘实测一致**」——
本例的形态是「**审计对象包含审计结论自身**」⇒ 任何**绝对**数字都必然滞后一轮
⇒ 正确做法是**改口径（引用不变量），而不是把数字追平**。

### 三、本轮其余状态（未变）

- `CORRECTIONS_APP.md` **全程只读**：SHA `219ef841…`／308 340 B／**100 条**／最大 APP-100 ⇒ **SHA 零改动**；
- `last_ack` 仍是 **APP-100**（**无编号更大的新条目 ⇒ 无新纠偏需执行**）；
- **§178／§179 的结论与 6 处 git 半交付修复全部成立**；
- **未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未改任何默认值或产品判据／未占设备／未持锁**；
- 节点仍是 **等 reviewer 复核 §174／§175／§177／§178**。
"""

LIVE_SECTION = """
## §180 勘误（2026-11-11 18:55:00）｜**撤回 §179 的「184 行 = 稳态真值」措辞** ⇒ **审计行数是观察量、不是定值**；判据的**不变量 = `FAIL=0` ＋ 反证 3/3**（本轮实测 **185 行／OK 180／FAIL 0**）｜§178／§179 的**结论与 6 处修复本身全部成立、不变**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec180_20261111.md`（__ARCH_B__ B／SHA256 `__ARCH_SHA__`）｜**归档件逐字节未动**（write-once）。
> 🔴 **勘误**：判据审计的对象**包含活文档自身引用的产物** ⇒ §178 入库涨 7 行、§179 入库再涨 1 行 ⇒ 🔴 **行数永远没有「稳态」** ⇒ 撤回 §179 的「184 行 = 稳态真值」措辞（本轮实测 **185 行**）。
> 🔴 **根因消除（不是逐轮打补丁）**：判据 `pass` 条件**本来就不含行数**（`n_fail==0 and n_missing==0 and anti_all_discriminating`）⇒ **行数从一开始就不参与结论** ⇒ 自本节起 STATUS **只引用不变量**（`FAIL=0`／`MISSING=0`／反证 **3/3**），`n_rows` 仅留作调试、**不作阈值** ⇒ **后续轮次不再需要为行数写勘误**。
> 🔴 **对照 MEMORY 老坑**「自指大小必须与磁盘实测一致」：本例形态是「**审计对象包含审计结论自身**」⇒ 任何**绝对**数字必然滞后一轮 ⇒ 正确做法是**改口径**，不是把数字追平。
"""


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    corr_before = open(CORR, 'rb').read()
    text = open(STATUS, 'rb').read().decode('utf-8')

    if os.path.exists(ARCH):
        print('ABORT: 归档件已存在（write-once）')
        return 1
    arch_bytes = ARCHIVE_BODY.encode('utf-8')
    arch_sha = sha(arch_bytes)
    live = (LIVE_SECTION
            .replace('__ARCH_B__', '{:,}'.format(len(arch_bytes)).replace(',', ' '))
            .replace('__ARCH_SHA__', arch_sha))

    new_text = text

    # ── 腾体积：§171 活文档块索引化（正文逐字仍在 write-once 归档件 sec171 里）──
    m171 = re.search(r'(?m)^## §171 .*?(?=^## |\Z)', new_text, re.S)
    if not m171:
        print('ABORT: 找不到 §171 块')
        return 1
    old171 = m171.group(0)
    a171 = open(os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec171_20261111.md'),
                encoding='utf-8').read()
    need = ['D1', 'D2', 'rc5', 'rc6', 'rc7', 'asr06b', '零交付物', 'app425',
            'hist_scan3', 'hist_impact', '§167']
    missing = [k for k in need if k not in a171]
    if missing:
        print('ABORT: sec171 归档件缺事实，不索引化:', missing)
        return 1
    new171 = ('## §171 巡检（last_ack=APP-098，2026-11-11 01:02:00）｜**无新纠偏**；'
              '把 §170 ⑨ 两项「历史影响未评估」**定界完毕**（D1 零交付物受影响／'
              '**D2 影响已交付的 rc5**）｜**本条需等 reviewer 复核**\n\n'
              '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec171_20261111.md`'
              '（10 930 B／块 SHA256 `45348f1f5e639e7b91a39e2ff1288264cabe6b60d9be7de4bdfe3842ce7081ff`）'
              '｜**归档件逐字节未动**（write-once）｜**正文全文（D1/D2 定界、15 包 AST 扫描、'
              'asr06b 档位 label 撞车三连判据修正、rc5/rc6/rc7 逐包结论、dev 树 git 史）逐字见该归档件**，'
              '活文档只留指针。\n')
    new_text = new_text.replace(old171, new171, 1)
    if new_text == text:
        print('ABORT: §171 替换未生效')
        return 1

    new_text = new_text.rstrip('\n') + '\n' + live
    nb = new_text.encode('utf-8')
    nl = nb.count(b'\n') + 1

    checks = [
        ('bytes<=40000', len(nb) <= 40000, str(len(nb))),
        ('lines<=300', nl <= 300, str(nl)),
        ('no CRLF', nb.count(b'\r\n') == 0, str(nb.count(b'\r\n'))),
        ('CORR untouched', sha(open(CORR, 'rb').read()) == sha(corr_before), ''),
        ('§171..§180 kept',
         all(('## §%d ' % n) in new_text for n in (171, 172, 173, 174, 175, 177, 178, 179, 180)),
         ''),
        ('§180 present', '## §180 ' in new_text, ''),
        ('last_ack=APP-100', 'last_ack: APP-100' in new_text, ''),
        ('sec171 pointer kept', 'STATUS_APP_sec171_20261111.md' in new_text, ''),
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
