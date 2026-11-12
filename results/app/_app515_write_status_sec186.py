#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app515_write_status_sec186.py —— 写 STATUS §186（巡检无新纠偏）＋ 归档 §184。

## 纪律（全部先跑自检、自检不过 ⇒ 源文件零改动）

- **写前自检全绿才落盘**（APP-049/052④ 的 fail-closed）。
- 归档件 **write-once**：目标文件已存在 ⇒ 直接 ABORT（不覆盖）。
- 活文档只做三件事：① 改头部 3 行 ② §184 正文换指针行（正文整块逐字进归档件）③ 追加 §186。
- **旧正文一字不删**（除 §184 正文 ⇒ 逐字进归档件 + 留指针行）。
- 复核「旧正文未变」**不按行号比** ⇒ 用**还原式复核**（指针行换回原文 ⇒ 与旧文件逐行 diff，差异必须逐条落在允许集合内）。
- §186 内容里的产物证据全部来自本轮实测（app157 / app510 / app512 复跑结果）。

## 用法

    python _app515_write_status_sec186.py <YYYY-MM-DD HH:MM:SS>
"""

from __future__ import annotations

import difflib
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
ARCH = os.path.join(ARCH_DIR, 'STATUS_APP_sec184_20261113.md')

MAX_BYTES = 40000
MAX_LINES = 300


def fail(msg):
    print('ABORT: %s' % msg)
    sys.exit(2)


def main():
    if len(sys.argv) < 2:
        fail('need timestamp arg')
    stamp = sys.argv[1].strip()

    if not os.path.isdir(ARCH_DIR):
        fail('archive dir missing: %s' % ARCH_DIR)
    if os.path.exists(ARCH):
        fail('archive file already exists (write-once): %s' % ARCH)

    with open(STATUS, encoding='utf-8', newline='') as f:
        old = f.read()
    if '\r' in old:
        fail('source has CR (expect pure LF)')

    # --- 定位 §184 / §185 ---
    i = old.index('## §184 ')
    j = old.index('## §185 ')
    sec184 = old[i:j]                       # 整节（标题行 + 正文）
    hdr184, rest184 = sec184.split('\n', 1)  # 标题行 / 正文（正文以 \n 结尾）
    if not hdr184.startswith('## §184 '):
        fail('sec184 header not matched')

    arch_bytes = sec184.encode('utf-8')
    arch_sha = hashlib.sha256(arch_bytes).hexdigest()
    arch_size = len(arch_bytes)

    pointer = ('> \U0001f534 **本节正文已整块逐字归档** ⇒ '
               '`status/archive/STATUS_APP_sec184_20261113.md`'
               '（%d B／块 SHA256 `%s`）。\n' % (arch_size, arch_sha))

    # --- §186 正文 ---
    sec186 = (
        '## §186 巡检（last_ack=APP-105，%s）｜**无新 reviewer 纠偏**'
        '（6 通道全查空）｜复跑既有闸门 3/3 **复现 §185 结论**｜**本条需等 reviewer 复核**\n'
        '\n'
        '> **① 纠偏文件复核（只读、未改、未提交）**：开工＝收尾 **105 条**／最大 **APP-105**／'
        'SHA `321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1`／**344 419 B**／'
        'mtime **2026-11-12 14:25:47** ⇒ **逐字一致 ⇒ SHA 零改动**；'
        '`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）。\n'
        '> **② 其它通道全空（⇒ 无遗漏指令）**：`shared/NOTICE*` 最新仍 11-05｜'
        'agent-mail 工具回 **`not_bound`**（面板虽显示 connected，**实际未开通**）｜'
        '`conversation_search` 两次不同措辞均 **0 命中**｜git `origin/main..main=0` 且 `main..origin/main=0`｜'
        '`claude-clone` 相对 main **无新提交**｜`MACHINE_LOCK` NOT_PRESENT（未占设备）。\n'
        '> **③ 复跑既有闸门（纯静态、零推理、零 GPU、未新增任何判据脚本）**：'
        '`app157` dev 树 **11 PASS/0 FAIL**｜`app510` 产品级反证 **VERDICT PASS**'
        '（M1–M4 注入缺陷全被识破）｜`app512` 包矩阵 **复现 §185**：v1.13/v2.0/v2.1 **PASS 11/0**、'
        '**v2.2 9/2・v2.3 8/3・v2.3_aborted 8/3・v2.4 9/2 FAIL**（＝带 APP-086·2a 缺陷）、'
        'v1.5 **2/8 属判据不适用**；**rc10 另跑 `app157` = 11 PASS/0 FAIL**'
        '⇒ **dev/rc10 收窄在、客户包缺陷分布未变**（§185 的交付阻断项依然成立）。\n'
        '> **④ 产物零改动**：4 个 evidence json 复跑后与 HEAD **逐字节一致**'
        '（只有时间戳变 ⇒ 已用开工快照还原，`git status` 对这 4 个文件为空）⇒ **无 diff 噪声**；'
        '未打包、未改客户包、未改产品代码、未跑推理（⇒ 未取 MACHINE_LOCK）、未调 MiniMax、未通知用户。\n'
        '> **⑤ 归档（限额腾挪）**：**§184**（rc10 交付记录）正文整块逐字归档 ⇒ '
        '`status/archive/STATUS_APP_sec184_20261113.md`（%d B／块 SHA256 `%s`）⇒ '
        '活文档保留 §184 标题行 + 1 行指针；**§185 等既有归档件未动**。\n'
        '> **⑥ 本条需等 reviewer 复核（§185 ⑫ 仍未裁定）**：① 完整版 **v2.5 必须带 APP-086·2a 收窄**'
        '（否则重犯「男声被配成女声」）；② v2.2/v2.3/v2.4 是否作废/标注；'
        '③ §185 新增 5 个脚本是否保留（与 APP-101 §1.d「不再新增审计/判据脚本」有张力）；④ rc10 仍待 B 机实测。\n'
        % (stamp, arch_size, arch_sha)
    )

    # --- 组装新正文 ---
    new = old[:i] + hdr184 + '\n' + pointer + old[j:]

    # 头部 3 行
    lines = new.split('\n')
    assert lines[2].startswith('last_ack:'), lines[2][:40]
    lines[3] = '更新时间: %s' % stamp
    old_task = lines[4]
    lines[4] = (
        '当前任务: **无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 105 条／最大 **APP-105**／'
        'SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47 ⇒ 与上轮**逐字一致**；'
        '**6 通道全查空** ⇒ 无遗漏指令）｜`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）｜'
        '**复跑既有闸门 3/3 复现 §185 结论**（app157 dev 11/0、app510 反证 VERDICT PASS、'
        'app512 包矩阵缺陷分布未变、rc10 11/0）｜🔴 **§185 的交付阻断项仍未裁定**'
        '（完整版 v2.5 必须带 APP-086·2a 收窄）｜未打包、未调 MiniMax、未通知用户'
    )
    new = '\n'.join(lines)

    # 最近更新：加一条（放在列表最前）
    anchor = '## 最近更新\n'
    k = new.index(anchor) + len(anchor)
    upd = ('> \U0001f534 %s ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／'
           'SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜'
           '**复跑既有闸门 3/3 复现 §185 结论**（app157 dev 11/0、app510 反证 VERDICT PASS、'
           'app512 包矩阵：v1.13/v2.0/v2.1 PASS 11/0、v2.2 9-2／v2.3 8-3／v2.3_aborted 8-3／v2.4 9-2 FAIL、v1.5 判据不适用；'
           'rc10 11/0）｜🔴 **完整版 v2.5 必须带 APP-086·2a 收窄**（§185 交付阻断项待裁定）｜'
           '未打包、未改客户包、未改产品代码、未通知用户\n'
           % stamp)
    new = new[:k] + upd + new[k:]

    # 追加 §186
    if not new.endswith('\n'):
        new += '\n'
    new += '\n' + sec186

    # ---------------- 写前自检（fail-closed） ----------------
    nb = new.encode('utf-8')
    nl = new.count('\n') + (0 if new.endswith('\n') else 1)
    checks = []
    checks.append(('size<=40000', len(nb) <= MAX_BYTES, '%d B' % len(nb)))
    checks.append(('lines<=300', nl <= MAX_LINES, '%d lines' % nl))
    checks.append(('no CR', '\r' not in new, 'CR=%d' % new.count('\r')))
    checks.append(('archive target absent', not os.path.exists(ARCH), ARCH))
    checks.append(('last_ack unchanged', 'last_ack: APP-105' in new.split('\n')[2], ''))
    checks.append(('sec186 appended', '## §186 ' in new, ''))
    checks.append(('sec185 body intact', '⑫ 本条需等 reviewer 复核' in new, ''))
    checks.append(('archive holds full sec184', arch_bytes.decode('utf-8').startswith('## §184 '), ''))

    # 还原式复核：把指针行换回 §184 原正文 ⇒ 与旧文件的差异必须逐条落在允许集合
    restored = new.replace(hdr184 + '\n' + pointer, sec184)
    ol = old.split('\n')
    rl = restored.split('\n')
    sm = difflib.SequenceMatcher(None, ol, rl, autojunk=False)
    allowed = []
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        allowed.append((tag, a1, a2, b1, b2, ol[a1:a2], rl[b1:b2]))
    # 允许的差异：头部 3 行（索引 3/4/5）、最近更新插入 1 行、末尾追加 §186
    ok_diff = True
    detail = []
    for tag, a1, a2, b1, b2, oa, rb in allowed:
        o_txt = '\n'.join(oa)[:40]
        r_txt = '\n'.join(rb)[:40]
        r_all = '\n'.join(rb)
        if tag == 'replace' and a2 <= 8 and b2 <= 8 and a1 >= 3 and b1 >= 3:
            # 只允许头部区域（更新时间／当前任务／阻塞行）被替换
            kind = 'HEADER'
        elif (tag == 'insert' and (b2 - b1) == 1 and rb[0].startswith('> ')
              and '巡检无新 reviewer 纠偏' in rb[0] and '## §186' not in rb[0]):
            kind = 'RECENT_UPDATES(+1行)'
        elif tag == 'insert' and '## §186' in r_all and b2 >= len(rl) - 1:
            kind = 'APPEND_SEC186'
        else:
            kind = 'UNEXPECTED'
            ok_diff = False
        detail.append('%s @old[%d:%d]→new[%d:%d] :: %s' % (kind, a1, a2, b1, b2, r_txt))
    checks.append(('restored-diff only-allowed', ok_diff, ' | '.join(detail)[:400]))

    print('=== 写前自检 ===')
    for name, ok, info in checks:
        print('%-28s %s  %s' % (name, 'PASS' if ok else 'FAIL', info))
    if not all(ok for _, ok, _ in checks):
        fail('write-before self-check FAILED ⇒ 源文件零改动')

    # ---------------- 落盘 ----------------
    with open(ARCH, 'w', encoding='utf-8', newline='') as f:
        f.write(sec184)
    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)

    print('=== 已落盘 ===')
    print('archive: %s  %d B  sha %s' % (ARCH, os.path.getsize(ARCH),
          hashlib.sha256(open(ARCH, 'rb').read()).hexdigest()))
    print('status : %s  %d B  %d lines' % (STATUS, os.path.getsize(STATUS),
          open(STATUS, encoding='utf-8', newline='').read().count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
