#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-235 轮 · 往 `status/app/STATUS_APP.md` **追加** `## §235` 章节。

## 定点写入三件套（按项目纪律）

1. 备份 `%TEMP%/STATUS_APP.md.bak_app235`；
2. 写前在**内存新文本**上跑真不变量（唯一命中断言 + 旧正文**逐字未变**
   ＋ **还原式复核** + 字节/行数上限断言）；
3. 临时文件 → `os.replace` ⇒ 写后**另起脚本**独立复核 + `git diff --numstat`。

## 🔴 只追加，绝不回头改旧章节

- 旧章节（§231…§234 等）**逐字不动**；
- 头部 `last_ack` **不改**（本轮无新纠偏 ⇒ 仍 APP-133）；
- 头部「更新时间」改为 **`Get-Date` 实测值**（实参传入，不推算）；
- 「最近更新」块**首部插入** 1 条（新条目在上、旧条目下移**不删**）。

## 🔴 还原式复核的正确写法（APP-235 轮修掉的判据坑）

还原时**必须连同定长前缀一起还原**：
`'更新时间: ' + TS` → `'更新时间: ' + old_ts`
（上一版只还原了时间戳 ⇒ 丢掉 6 字符 ⇒ 判据恒 FAIL ⇒ 假 FAIL）。
"""
from __future__ import annotations

import os
import re
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TARGET = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'),
                      'STATUS_APP.md.bak_app235')
TS = sys.argv[1] if len(sys.argv) > 1 else ''
if not TS:
    raise SystemExit('[FAIL] 必须传入 Get-Date 实测时间戳')

SEC_TITLE = (
    '## §235 接续上一会话（**TAKEOVER**）｜**六通道复核 ⇒ 仍无新 App 纠偏**'
    '（`last_ack` 仍 **APP-133**）｜🟢 **闭合上一会话遗留**'
    '（§234 已写 STATUS，但**未提交/未推送/未发信/未写日志**）'
    '｜🟢 **独立复现** §234 的 3 处修法（**11/11 ＋ 17/17 ＋ 16/16 全 PASS**）'
    '｜🟢 **修掉 2 处新真缺陷**：'
    '① 判据自身缺陷（还原式复核丢掉 `更新时间: ` 前缀 ⇒ **恒 FAIL 假 FAIL**）'
    '② 🔴 **生产路径缺陷**（`sync_pkg_identity.py` 会用**影子包**结果'
    '**覆盖**交付包的 app170 闸门证据 ⇒ **审计链断**）'
    '｜🟢 独立行为级复核 **25/25 PASS**（含**反证组**与**非空洞**检查）'
    '｜🟢 **未改任何客户包**（真包 48 792 文件 0 变化）'
    '｜🟢 **未打包 zip**／未跑推理·计时（**未取 MACHINE_LOCK**）／未调 MiniMax／未连 B 机'
    '｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）'
    '｜🔴 **如实登记 8 处未修/待裁定项**'
    '｜**本条需等 reviewer 复核**')
SEC_POINTER = (
    '> 🔴 **本节正文全文 ⇒ '
    '`status/app/STATUS_APP_sec235_detail_20261125.md`**'
    '（含 §0 租约 TAKEOVER、§1 六通道逐通道证据、§2 独立复核 §234 的 3 处修法、'
    '§3 本轮修掉的 2 处新真缺陷（含根因/修法/25/25 判据表）、'
    '§4 交付面只读复核、§5 未修项如实登记、§6 纪律自查、§7 下一轮）')

RECENT = (
    '> 🔴 __TS__ ｜ **接续上一会话（TAKEOVER）＋ 六通道复核 ⇒ 仍无新 App 纠偏**'
    '（本地 max APP-133 ＝ QQ max APP-133 ＝ `last_ack` ⇒ **值不变**）'
    '｜🟢 **闭合上一会话遗留 4 件事**（§234 的 STATUS 已写，但上一会话**未提交/未推送/'
    '未发信/未写当日日志与 automation memory**）'
    '｜🟢 **独立复现** §234 的 3 处修法（**11/11 ＋ 17/17 ＋ 16/16 全 PASS**，各含反证组）'
    '｜🟢 **修掉 2 处新真缺陷**：'
    '① 🟡 **判据自身缺陷** ⇒ `results/app/_app234_verify_status.py` 判据 9 '
    '把 `更新时间: <ts>` 换成**只有时间戳** ⇒ 丢掉 `更新时间: ` 这 **6 个字符** '
    '⇒ **恒 FAIL（假 FAIL）**（修正前实测 13/14 FAIL 1）⇒ 修判据 ＋ **新增反证组 9b** '
    '⇒ **15/15 PASS**；且修正后还原串与写前备份**逐字节相等** ⇒ '
    '**STATUS 正文本身无缺陷**；'
    '② 🔴 **生产路径缺陷** ⇒ `live_caption/sync_pkg_identity.py` **无条件**把 app170 '
    '闸门证据写到**规范路径** ⇒ 在任何影子包上跑一次就**覆盖**「交付包的闸门记录」'
    '（实测 `pkg` 变成 `%TEMP%\\app234_id_klh3m45v\\...v2.10`＝**跑完即删不可复算**、'
    '`pass` 19→20、真实包两条**真实 advisory** 整条消失 ⇒ **审计链断**）'
    '⇒ 改**生产路径**：**交付候选包**才写规范文件；**非交付包**写**临时文件**并用后删除 '
    '⇒ ①绝不覆盖 ②**零仓库污染**；规范证据已用**真实交付包 v2.6** 重刷'
    '（rc=0／`pass=19`／`fail=0`／两条 advisory 回到位／**与 HEAD 逐字节相同**）'
    '｜🟢 独立行为级复核 **25/25 PASS**（A 5 ＋ B 6 ＋ **C 反证组 3** ＋ '
    '**D 非空洞检查 4** ＋ E 5）'
    '｜🟢 **未改任何客户包**（真包 48 792 文件跑前跑后 **0 变化**；4 个身份文件 SHA256 一致）'
    '｜🟢 **未打包 zip**／未跑推理·计时（**未取 MACHINE_LOCK**）／未调 MiniMax／未连 B 机'
    '｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）'
    '｜🔴 **如实登记 8 处未修/待裁定项**'
    '｜**本条需等 reviewer 复核**').replace('__TS__', TS)


def main() -> int:
    raw0 = open(TARGET, 'rb').read()
    text0 = raw0.decode('utf-8')
    print('写前：%d B；CRLF %d；LF %d' % (
        len(raw0), text0.count('\r\n'), text0.count('\n')))

    shutil.copy2(TARGET, BACKUP)
    print('备份：%s' % BACKUP)

    # ── 锚点唯一性断言 ────────────────────────────────────────────
    a_ts = '更新时间: '
    assert text0.count(a_ts) == 1, '「更新时间」锚点不唯一'
    m_ts = re.search(r'^更新时间: (.+)$', text0, re.M)
    old_ts = m_ts.group(1)
    a_ack = 'last_ack: '
    assert text0.count(a_ack) == 1, '「last_ack」锚点不唯一'
    # 🔴 实测：该标题是**混合行尾**里的一处 **CRLF**（`## 最近更新\r\n`）
    a_recent = '## 最近更新\r\n'
    assert text0.count(a_recent) == 1, '「最近更新」锚点不唯一'
    assert text0.rstrip().endswith('）'), '文末形态与预期不符'

    # ── 在内存新文本上做替换（**只追加/只改头部两行**）──────────────
    text1 = text0.replace(a_ts + old_ts, a_ts + TS, 1)
    text1 = text1.replace(a_recent, a_recent + RECENT + '\n', 1)
    text1 = text1.rstrip('\n') + '\n\n' + SEC_TITLE + '\n' + SEC_POINTER + '\n'

    # ══ 真不变量 ═════════════════════════════════════════════════
    checks = []
    checks.append(('「更新时间」已改为实测值',
                   ('更新时间: ' + TS) in text1))
    checks.append(('「last_ack」**未变**（仍 APP-133）',
                   text1.count('last_ack: APP-133') == 1))
    checks.append(('「最近更新」新条目已插入',
                   RECENT[:60] in text1))
    checks.append(('§235 章节已追加在文末',
                   text1.rstrip().endswith(SEC_POINTER)))
    checks.append(('§235 章节只出现 1 次',
                   text1.count(SEC_TITLE) == 1))
    # 🔴 还原式复核：**连同定长前缀一起还原**（APP-235 修掉的判据坑）
    back = text1.replace(a_recent + RECENT + '\n', a_recent, 1)
    back = back.replace(a_ts + TS, a_ts + old_ts, 1)
    back = back.rstrip('\n')
    back = back[:back.rfind('\n\n## §235')] + '\n' if '\n\n## §235' in back \
        else back
    checks.append(('还原式复核：去掉新增内容后逐字节同原文',
                   back.rstrip('\n') == text0.rstrip('\n')))
    for keep in ('## §231 ', '## §232 ', '## §233 ', '## §234 '):
        checks.append(('旧章节保留：%s' % keep.strip(),
                       text1.count(keep) == 1))
    n_bytes = len(text1.encode('utf-8'))
    checks.append(('字节数 ≤ 40 000（%d）' % n_bytes, n_bytes <= 40000))
    n_lines = text1.count('\n') + 1
    checks.append(('行数 ≤ 300（%d）' % n_lines, n_lines <= 300))
    checks.append(('未引入新的 CRLF（新增行全 LF）',
                   text1.count('\r\n') == text0.count('\r\n')))

    for name, ok in checks:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
    if not all(ok for _, ok in checks):
        print('\n[FAIL] 真不变量未全过 ⇒ **零改动**（不写盘）')
        return 1

    tmp = TARGET + '.tmp_app235'
    with open(tmp, 'wb') as f:
        f.write(text1.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)
    print('\n写入完成：%d B → %d B（delta %+d）；行数 %d'
          % (len(raw0), n_bytes, n_bytes - len(raw0), n_lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
