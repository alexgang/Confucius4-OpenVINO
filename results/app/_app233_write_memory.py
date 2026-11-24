#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 写记忆文件（MEMORY_MODULES 附录·五十二 ＋ MEMORY.md 指针 ＋ 当日日志 ＋ automation memory）。

## 🔴 纪律
- `MEMORY_MODULES.md`：**append-only／write-once**（只追加新节，不改旧节）。
- `MEMORY.md`：**≤9 700 字符**自声明上限 ⇒ **谁写完都要重跑上限断言**（跨模块共享文件）。
  本轮只做**指针更新**（轮次状态属 STATUS 的职责，**不**在 MEMORY.md 里再抄一遍 — §227 教训）。
- 当日日志 `.workbuddy/memory/2026-11-25.md`：**新建**（本轮跨日 01:37 起）。
- automation memory：**只许追加、禁覆盖**（gitignore ⇒ 无副本）⇒ 追加前先备份。

## 🔴 MEMORY.md 的腾挪（§232 先例：「逐条不删，只压从句」＋「删过期状态 ≠ 删判据」）
- 写前实测 **9 652／9 700**（余量仅 **48**）⇒ 本轮要加的内容**放不下**。
- ⇒ 腾挪来源：§十二 里 **§225／§226 两行「已完成」的轮次状态**
  （**已过期** ⇒ 按 §232 先例可删；其**逐字全文**在 `MEMORY_MODULES.md` 附录·四十七／五十二，
  **且** STATUS §225／§226 与 companion 仍在 ⇒ **不丢任何知识**）。
  **保留**：🔴「全仓 854 个 `i/lf+w/crlf` 须 reviewer 裁定」（**仍是待裁定项**）。
- ⇒ 判据：① **≤9 700** ② **所有判据关键词逐条存活**（含否定式表述的可 grep 串）
  ③ **所有 `APP-/TTS-/ASR-/MT-/C-/§` 编号存活** ④ **还原式复核**逐字节等于写前
  ⑤ **标记数减少仅允许发生在「删过期状态」那一行**（逐行比对，其余行**标记数不减少**）。
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
MODULES = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY_MODULES.md')
DAILY = os.path.join(REPO, '.workbuddy', 'memory', '2026-11-25.md')
AUTOM = os.path.join(REPO, '.workbuddy', 'memory', 'automations',
                     'c773e368-530e-4404-9b0d-66da2193cbf6', 'memory.md')

MEM_LIMIT = 9700

MODULES_APPEND = open(
    os.path.join(REPO, 'results', 'app', '_app233_modules_append.md'),
    encoding='utf-8').read()

# ── MEMORY.md 的编辑表（每条：旧文本 → 新文本）────────────────────
MEM_EDITS = [
    # E1：§十二 标题里的 companion 指针范围 ⇒ 补 §233
    ('## 十二、App 当前状态（**逐字⇒MODULES 三十七/四十三–四十九 ＋ STATUS §224–§231 companion**）',
     '## 十二、App 当前状态（**逐字⇒MODULES 三十七/四十三–五十二 ＋ STATUS §224–§233 companion**）'),
    # E2：头部指针 §214–226 ⇒ §214–233
    ('**§214–226⇒`status/app/STATUS_APP_sec2*_detail_*.md`**',
     '**§214–233⇒`status/app/STATUS_APP_sec2*_detail_*.md`**'),
    # E3：§十二 状态行 ⇒ 补「v2.6 两处包内缺陷已修开发树、真包未动 ⇒ 待出 v2.7」
    ('🔴**待裁定**：默认分离设备／v2.6 交接。',
     '🔴**待裁定**：默认分离设备／v2.6 交接／§233（v2.6 两处包内缺陷已修开发树、'
     '真包未动 ⇒ 待出 v2.7）。'),
    # E4：§十二 里 §225／§226 的「已完成轮次状态」⇒ 按 §232 先例删（逐字全文在 MODULES 附录）
    ('-🟢**APP-128 补充已执行（§225）**：补发 e2e7 三臂表 ⇒ `msg_52Ta35…`（462 B）｜'
     '`b7507cb`｜🟢**§226**：已修复算底本入库字节不一致（3/3＋反证组 3/3）｜'
     '🔴**全仓 854 个 `i/lf+w/crlf` 须 reviewer 裁定**。',
     '-🔴**全仓 854 个 `i/lf+w/crlf` 须 reviewer 裁定**（§225／§226 已执行，'
     '逐字全文见 MODULES 附录·四十七／五十二 ＋ STATUS §225／§226）。'),
]

# ── 判据关键词（**含否定式表述的可 grep 串**）─────────────────────
MEM_KEYWORDS = [
    '定点写入三件套', '还原式复核', '不 force push', 'last_ack=APP-133',
    '未经用户通知不打包', 'TAKEOVER', '上限断言', '不通知 ⇒ 不打包',
    '真不变量', '假 FAIL', '反证组', '写-once', 'write-once',
    '归档件 write-once', '不是新编号', '不代表', '禁覆盖',
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    failed = []

    def chk(name, cond, detail=''):
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                               ('｜' + detail) if detail else ''))
        if not cond:
            failed.append(name)

    # ══ ① MEMORY_MODULES.md：append-only ══════════════════════════
    print('[1] MEMORY_MODULES.md（append-only）')
    mb = open(MODULES, 'rb').read()
    mtext = mb.decode('utf-8')
    if '附录·五十二' in mtext:
        print('  [SKIP] 附录·五十二 已存在 ⇒ 不重复追加')
    else:
        new_m = (mtext.rstrip('\n') + '\n' + MODULES_APPEND).encode('utf-8')
        assert new_m[:len(mb)] == mb, 'append-only 前缀不成立'
        tmp = MODULES + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(new_m)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, MODULES)
        print('  [PASS] 追加 %d B（%d → %d B）；SHA256 %s'
              % (len(new_m) - len(mb), len(mb), len(new_m),
                 sha256_bytes(new_m)[:16]))

    # ══ ② MEMORY.md：腾挪 ＋ 指针更新 ＋ 上限断言 ══════════════════
    print('\n[2] MEMORY.md（腾挪 ＋ 指针更新 ＋ %d 上限断言）' % MEM_LIMIT)
    mem_raw = open(MEM, 'rb').read()
    mem = mem_raw.decode('utf-8')
    print('  写前 %d 字符（余量 %d）' % (len(mem), MEM_LIMIT - len(mem)))

    for o, n in MEM_EDITS:
        assert mem.count(o) == 1, '锚点不唯一：%r' % o[:50]
    new_mem = mem
    for o, n in MEM_EDITS:
        new_mem = new_mem.replace(o, n, 1)
    print('  写后 %d 字符（余量 %d）' % (len(new_mem), MEM_LIMIT - len(new_mem)))

    chk('≤ %d 字符' % MEM_LIMIT, len(new_mem) <= MEM_LIMIT, '%d' % len(new_mem))
    # 判据关键词逐条存活
    lost_kw = [k for k in MEM_KEYWORDS if k in mem and k not in new_mem]
    chk('判据关键词逐条存活（含否定式表述）', not lost_kw, 'lost=%s' % (lost_kw or '无'))
    # 编号存活
    nums_b = set(re.findall(r'(?:APP|TTS|ASR|MT|C)-\d+', mem))
    nums_a = set(re.findall(r'(?:APP|TTS|ASR|MT|C)-\d+', new_mem))
    lost_n = sorted(n for n in nums_b if n not in nums_a)
    chk('全部 APP-/TTS-/ASR-/MT-/C- 编号存活', not lost_n, 'lost=%s' % (lost_n or '无'))
    # 章节数不变（**不新增章节** ⇒ 只在既有节内加指针）
    chk('章节数不变（不新增节）',
        len(re.findall(r'^## ', new_mem, re.M))
        == len(re.findall(r'^## ', mem, re.M)))
    # 标记数：**逐行**比对，仅「删过期状态」那一行允许减少
    lb, la = mem.split('\n'), new_mem.split('\n')
    chk('行数不变', len(lb) == len(la), '%d → %d' % (len(lb), len(la)))
    diff_lines = [i for i in range(min(len(lb), len(la))) if lb[i] != la[i]]
    chk('仅 4 行被改（编辑表条数）', len(diff_lines) == len(MEM_EDITS),
        'diff=%s' % diff_lines)
    mark_drop = []
    for i in diff_lines:
        ob = lb[i].count('🔴') + lb[i].count('🟢')
        oa = la[i].count('🔴') + la[i].count('🟢')
        if oa < ob:
            mark_drop.append(i)
    chk('标记数减少只发生在「删过期状态」那一行（E4）',
        mark_drop == [diff_lines[-1]], 'drop_at=%s' % mark_drop)
    # 还原式复核
    restored = new_mem
    for o, n in reversed(MEM_EDITS):
        assert restored.count(n) == 1, '还原定位失败'
        restored = restored.replace(n, o, 1)
    chk('还原式复核＝逐字节等于写前', restored == mem)

    if failed:
        print('  [ABORT] 真不变量有 FAIL ⇒ 零改动：%s' % failed)
        return 1

    bak = os.path.join(tempfile.gettempdir(), 'MEMORY.md.bak_app233')
    shutil.copy2(MEM, bak)
    print('  [backup] %s' % bak)
    tmp = MEM + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_mem.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, MEM)
    print('  [write ] %d 字符；SHA256 %s'
          % (len(new_mem), sha256_bytes(new_mem.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
