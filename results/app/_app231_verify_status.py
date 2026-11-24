#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-231：**独立复核** `status/app/STATUS_APP.md` 的 §231 写入（另起脚本）。

## 复核项
1. **旧正文逐字未变**：除「头部 `更新时间` 一行」＋「最近更新**插入**的一行」
   ＋「文末新增的 §231 两行」外，**其余每一行逐字节相同**（含行尾）。
2. **行尾风格不变**：**旧行的行尾一个都没改**（逐行核对）⇒ 新增行的行尾
   与其所在区域的既有行尾一致（头部=LF／最近更新=LF／文末=LF）。
3. `last_ack` **仍是 APP-133** 且**唯一**（本轮无新纠偏 ⇒ 值不变）。
4. `更新时间` 已换成**实测值**（不是旧值 `18:29:37`）。
5. §231 **只出现一次**，且在**文末**；companion 文件**存在**。
6. 限额：≤ 40 000 B / ≤ 300 行（APP-052④）。
7. `CORRECTIONS_APP.md` **零改动**（SHA/字节/条数）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
DETAIL = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec231_detail_20261124.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
TMP = os.environ.get('TEMP', '/tmp')
BACKUP = os.path.join(TMP, 'STATUS_APP.md.bak_app231')

CORR_BEFORE = {
    'sha256': '2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda',
    'bytes': 440181,
    'n_app': 130,
}

checks = []


def chk(name, ok, detail=''):
    checks.append({'check': name, 'pass': bool(ok), 'detail': str(detail)})
    print('%-4s %s %s' % ('PASS' if ok else 'FAIL', name, detail))


def split_keep(text):
    """拆成 [(行内容, 行尾)]，保留行尾信息。"""
    parts = re.split(r'(\r\n|\n)', text)
    out = []
    cur = ''
    for i in range(0, len(parts), 2):
        cur += parts[i]
        e = parts[i + 1] if i + 1 < len(parts) else ''
        out.append((cur, e))
        cur = ''
    if cur:
        out.append((cur, ''))
    return out


def main():
    new = open(STATUS, 'r', encoding='utf-8', newline='').read()
    old = open(BACKUP, 'r', encoding='utf-8', newline='').read()
    nl = split_keep(new)
    ol = split_keep(old)

    # ── ① 旧行逐字节未变（除 3 处允许变更）───────────────────
    # 允许变更：① 头部「更新时间」行 ② 最近更新**新增**行 ③ 文末 §231 两行
    new_idx = [i for i, (l, _) in enumerate(nl) if '机器锁' in l and '未通知用户' in l]
    sec231_idx = [i for i, (l, _) in enumerate(nl) if l.startswith('## §231 ')]
    chk('§231 标题在**文末**（且只出现一次）',
        len(sec231_idx) == 1 and sec231_idx[0] >= len(ol) - 3,
        'idx=%r（写前行数 %d）' % (sec231_idx, len(ol)))

    # 最近更新：新条目应紧邻旧条目之前
    # 🔴 **两侧索引必须各自在自己的列表里找**（本轮初版 bug：`recent_old`
    #   却在 `nl`（新文件）里找 ⇒ 却拿去索引 `ol`（旧文件）⇒ 错位 ⇒ 假 FAIL）
    recent_new = [i for i, (l, _) in enumerate(nl)
                  if l.startswith('> 🔴 2026-11-24 20:3x')]
    recent_17_new = [i for i, (l, _) in enumerate(nl)
                     if l.startswith('> 🔴 2026-11-24 17:4x')]
    recent_17_old = [i for i, (l, _) in enumerate(ol)
                     if l.startswith('> 🔴 2026-11-24 17:4x')]
    chk('「最近更新」：新条目**插在块首**、旧条目仍在',
        len(recent_new) == 1 and len(recent_17_new) == 1
        and len(recent_17_old) == 1 and recent_new[0] < recent_17_new[0],
        'new@%r 旧条目 new@%r old@%r' % (recent_new, recent_17_new, recent_17_old))

    # 头部更新时间行
    upd_new = [i for i, (l, _) in enumerate(nl) if l.startswith('更新时间: ')]
    upd_old = [i for i, (l, _) in enumerate(ol) if l.startswith('更新时间: ')]
    chk('头部「更新时间」只有 1 行', len(upd_new) == 1 and len(upd_old) == 1)
    chk('头部「更新时间」已换成**实测值**（旧值 18:29:37 已消失）',
        '18:29:37' not in new and upd_new[0] == upd_old[0],
        'new=%r' % nl[upd_new[0]][0][:60])

    # 逐行比对：把 3 处允许变更扣掉后，其余行必须逐字节相同（含行尾）
    # 🔴 **两侧要扣的是同一批行**：旧文件里「更新时间」行**也要扣掉**
    #   （本轮初版只从 new 侧扣 ⇒ 两边错位 ⇒ 报「旧正文变了」＝**假 FAIL**）
    allowed_new = set(recent_new) | set(sec231_idx) | set(upd_new)
    # §231 段共 2 行（标题 + 指针行）
    for i in sec231_idx:
        allowed_new.add(i + 1)
    # 🔴 **旧侧只扣「更新时间」那一行**：17:4x 条目在新文件里只是**下移了一行**
    #   ⇒ 它**仍然要被逐字节比对**（它证明旧正文没被动过）
    allowed_old = set(upd_old)
    kept_new = [(l, e) for i, (l, e) in enumerate(nl) if i not in allowed_new]
    kept_old = [(l, e) for i, (l, e) in enumerate(ol) if i not in allowed_old]
    same = kept_new == kept_old
    detail = ''
    if not same:
        d = []
        for i, (a, b) in enumerate(zip(kept_old, kept_new)):
            if a != b:
                d.append((i, b[0][:40], b[1]))
        detail = 'diff=%r（old %d 行 vs new %d 行）' % (d[:5], len(kept_old), len(kept_new))
    chk('旧正文**逐行逐字节未变**（含行尾；仅 3 处允许变更已扣除）',
        same, detail)

    # ── ② 行尾风格不变 ─────────────────────────────────────
    old_e = [e for i, (_, e) in enumerate(ol) if i not in allowed_old]
    new_kept_e = [e for i, (_, e) in enumerate(nl) if i not in allowed_new]
    chk('**旧行的行尾一个都没改**', old_e == new_kept_e,
        'old_lf=%d new_lf=%d' % (old_e.count('\n'), new_kept_e.count('\n')))
    # 新增行的行尾 == 其所在区域既有行尾
    chk('新增「最近更新」行行尾 == 该区域既有行尾（LF）',
        nl[recent_new[0]][1] == '\n', repr(nl[recent_new[0]][1]))
    chk('新增 §231 两行行尾 == 文末既有行尾（LF）',
        all(nl[i][1] == '\n' for i in sec231_idx), '')

    # ── ③ last_ack ─────────────────────────────────────────
    chk('`last_ack` **仍是 APP-133**（本轮无新纠偏 ⇒ 值不变）',
        new.count('last_ack: APP-133') == 1
        and 'last_ack: APP-128' not in new)

    # ── ④ companion + 限额 ──────────────────────────────────
    chk('companion 正文文件存在', os.path.isfile(DETAIL),
        '%d B' % (os.path.getsize(DETAIL) if os.path.isfile(DETAIL) else 0))
    b = os.path.getsize(STATUS)
    lines = new.count('\n') + 1
    chk('限额：≤ 40 000 B', b <= 40000, '%d B' % b)
    chk('限额：≤ 300 行', lines <= 300, '%d 行' % lines)

    # ── ⑤ 纠偏文件零改动 ────────────────────────────────────
    cb = open(CORR, 'rb').read()
    csha = hashlib.sha256(cb).hexdigest()
    n_app = len(re.findall(r'^##\s*APP-(\d+)', cb.decode('utf-8', 'replace'), re.M))
    chk('CORRECTIONS_APP.md：**SHA 零改动**', csha == CORR_BEFORE['sha256'],
        csha[:24])
    chk('CORRECTIONS_APP.md：字节数一致', len(cb) == CORR_BEFORE['bytes'],
        '%d' % len(cb))
    chk('CORRECTIONS_APP.md：`## APP-xxx` 条数一致', n_app == CORR_BEFORE['n_app'],
        '%d' % n_app)

    n_pass = sum(1 for c in checks if c['pass'])
    out = os.path.join(REPO, 'results', 'app', 'app231_status_verify.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'checks': checks, 'n_pass': n_pass,
                   'n_fail': len(checks) - n_pass,
                   'status_bytes': b, 'status_lines': lines,
                   'status_sha256': hashlib.sha256(
                       open(STATUS, 'rb').read()).hexdigest()},
                  f, ensure_ascii=False, indent=2)
    print('\n%d/%d PASS  ⇒ %s' % (n_pass, len(checks), out))
    return 0 if n_pass == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
