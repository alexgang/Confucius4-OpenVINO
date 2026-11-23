#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_write_status.py —— §227 轮：把 §227 写进 `status/app/STATUS_APP.md`。

## 纪律（照搬项目既有约定）

- **只追加** `## §N` 章节，**不回头改旧章节**（旧结论错了就在新章节里写「撤回 §x」）。
- 头部 `last_ack` **本轮不变**（仍 APP-128：无新编号 ⇒ 不改）。
- 头部「更新时间」用 **实测值**，**禁止推算**。
- 正文放 companion（APP-052④）⇒ 活文档只留**标题行 ＋ 指针行**。
- 限额 **≤40 000 B / ≤300 行**（APP-052④）⇒ 写前先算，超限就**归档最老的一条真条目（逐字）**。
- 「最近更新」条目：**新的一条写在最上面**；本节已有 3 条**真条目**（日期戳开头）＋ 若干**归档指针行**（以「本节 N 条较旧…」开头）
  ⇒ 本轮**新增 1 条真条目**并把**最老的一条真条目**整块逐字归档（§226 轮那条 2026-11-24 00:41 不动，它是最新的一条）。
  归档件 = `status/archive/STATUS_APP_recent_updates_20261124b.md`（**新文件名**，不覆盖 §226 那份）⇒ **write-once**。
- **定点写入三件套**：① 备份 ② 写前在**内存新文本**上跑真不变量 ③ 临时文件 → `os.replace`
  ⇒ **写后另起脚本独立复核**。

## 真不变量（关键：活文档里**只追加不删改**，所以旧行必须**逐行仍可数到**）

  ① 字节数 ≤ 40 000 ② 行数 ≤ 300
  ③ **旧文件每一行（非空）仍出现在新文件里，且出现次数不少于原来**（⇒ 只追加 ⇒ 不删不改）
  ④ `last_ack: APP-128` 仍在（未变）
  ⑤ `## §227` 出现 1 次；指针行指向 companion；归档指针指向归档件
  ⑥ 无 CR 引入；结尾有换行 ⑦ 旧 `§nnn` 编号全部存活
"""
from __future__ import annotations

import collections
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_recent_updates_20261124b.md')
COMPANION = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec227_detail_20261124.md')

LIMIT_BYTES = 40000
LIMIT_LINES = 300

UPDATED = '2026-11-24 05:5x'   # 实测（Get-Date），非推算

SECTION_TITLE = (
    '## §227 巡检（**无新 reviewer 纠偏**，`last_ack` 仍 **APP-128**）｜🔴 **接续上一会话（TAKEOVER）并闭合其遗留的 3 处半交付**｜'
    '🟢 **已修：MEMORY.md 超限 710 字符**｜🟢 **已补：上一会话从未写的 automation memory ＋ 当日日志**｜**本条需等 reviewer 复核**'
)

SECTION_POINTER = (
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec227_detail_20261124.md`**'
    '（§0 六通道复核／§1 TAKEOVER 交接／§2 MEMORY.md 超限的修法与写后独立复核／'
    '§3 两处记忆文件补写／§4 §226 状态块去重／§5 纪律／§6 纠偏文件 SHA 零改动／§7 待复核裁定／§8 新学到的可复用知识）'
)

RECENT_NEW = (
    '> 🔴 2026-11-24 05:5x ｜ **巡检（无新 reviewer 纠偏，`last_ack` 仍 **APP-128**）＋ 接续上一会话（TAKEOVER）闭合其遗留的 3 处半交付**：'
    '🟢 **§0 六通道全空**（局域网 **125 条／max APP-127**／SHA `fafecf08…`／**429 255 B**／mtime 11-23 16:55:40；'
    'QQ 最新 App 封仍是 APP-128 补充＝§225 已执行；`APP-129` 全库命中 **0**；spam **0**；根 `CORRECTIONS.md` max C-135；'
    '`shared/NOTICE*` 仍 11-05；agent-mail `not_bound`）｜'
    '🔴 **§1 TAKEOVER**：上一会话（租约 `4dc753a6`，00:20:07 起、**00:45:18 后失联**）**死在 step11 之后** ⇒ '
    '代码/STATUS/邮件已落盘推送（`58439ba`，origin/main **0/0**），但**留下 3 处半交付**｜'
    '🟢 **§2 遗留①**：`MEMORY.md` 实测 **10 410 字符 > 自声明 9 700** ⇒ **超限 710 字符、注入被截断**；'
    '修法＝压缩前全文逐字下沉 `MEMORY_MODULES.md` **附录·四十九**（write-once）＋逐条不删只压从句＋临时文件 `os.replace`；'
    '**写后独立复核 ALL PASS**（**9 699 字符**／行数章节数不变／**每行 🔴🟢 标记数不减少**／编号全存活／'
    '附录逐字含原文 10 410 字符／只出现 1 次／被压掉标识符仅 **1** 个且在 MODULES 有逐字原文）｜'
    '🟢 **§3 遗留②**：上一会话**从未写** automation memory（`grep §226`＝**0**）＋当日日志（只有 2 条 TTS、无 App 条目）⇒ 本轮**追加**补齐'
    '（**171 301→173 253**／**2 282→3 588** 字符，**append-only**、断言原文逐字仍在）｜'
    '🟢 **§4 遗留③**：MEMORY.md 里 §226 的**方法细节**与 §八「§226 修法」重复 ⇒ 压掉重复（**全文仍在 MODULES 附录·四十九**）｜'
    '🔴 **§6 收尾**：`CORRECTIONS_APP.md` 四项指纹**逐字一致 ⇒ SHA 零改动**｜'
    '🔴 **未打包／未改客户包／未跑推理·计时（未取 MACHINE_LOCK）／未调 MiniMax／未连 B 机／未改纠偏文件／未进 v2.6**｜'
    '🔴 **待 reviewer 复核**：§227 压缩是否可接受｜**§226 复核仍挂**（3 份底本 clone 口径 3/3）｜'
    '**仓库根 `.gitattributes` 根治**（跨模块，851 个历史文件 blob）｜默认分离设备（建议 GPU.0）｜`n_speakers=0` 口径｜v2.6 交接｜'
    '**本条需等 reviewer 复核**'
)


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_atomic(p, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), prefix='.app227_', suffix='.tmp')
    with io.open(fd, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def main():
    if not os.path.exists(COMPANION):
        print('[FAIL] companion 不存在：%s' % COMPANION)
        return 2
    orig = read(STATUS)
    print('[pre] STATUS_APP.md %d B / %d 行'
          % (len(orig.encode('utf-8')), orig.count('\n')))
    if '## §227' in orig:
        print('[FAIL] §227 已存在 ⇒ 幂等拒绝')
        return 2
    if os.path.exists(ARCH):
        print('[FAIL] 归档件已存在 ⇒ write-once 拒绝：%s' % ARCH)
        return 3

    lines = orig.split('\n')
    ri = next(i for i, l in enumerate(lines) if l.startswith('## 最近更新'))
    j = ri + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    entry_start = j
    while j < len(lines) and lines[j].startswith('> '):
        j += 1
    block = lines[entry_start:j]

    # **真条目**＝以日期戳开头（`> 🔴 YYYY-MM-DD`）；**归档指针行**＝以「本节 N 条较旧」开头
    real_idx = [k for k, l in enumerate(block)
                if re.match(r'^> 🔴 \d{4}-\d{2}-\d{2}', l)]
    if len(real_idx) < 2:
        print('[FAIL] 「最近更新」真条目不足（%d）' % len(real_idx))
        return 3
    oldest_k = real_idx[-1]
    oldest = block[oldest_k]
    print('[info] 归档最老的真条目（%d 字符）：%s' % (len(oldest), oldest[:70]))

    # ── 归档件（write-once）──
    arch_body = (
        '# STATUS_APP「最近更新」归档（§227 轮 · 2026-11-24）\n\n'
        '> 🔴 本文件是 `status/app/STATUS_APP.md` 里「最近更新」一节**最老的一条真条目**'
        '（🔴 2026-11-23 20:2x「执行 APP-128」＝**§224**）的**整块逐字归档**（write-once）。\n'
        '> 活文档对应位置只留**一行指针**；**原文一字未删、未改**。\n\n'
        + oldest + '\n'
    )
    write_atomic(ARCH, arch_body)
    arch_sha = hashlib.sha256(arch_body.encode('utf-8')).hexdigest()
    print('[ok] 归档件已写：%s（%d B／SHA256 %s）'
          % (ARCH, len(arch_body.encode('utf-8')), arch_sha))

    # ── 组装新活文档 ──
    new_block = [RECENT_NEW] + [l for k, l in enumerate(block) if k != oldest_k]
    new_lines = lines[:entry_start] + new_block + lines[j:]

    # 归档指针行：紧跟在新条目区之后（归档指针行区）
    ri2 = next(i for i, l in enumerate(new_lines) if l.startswith('## 最近更新'))
    k = ri2 + 1
    while k < len(new_lines) and not new_lines[k].strip():
        k += 1
    while k < len(new_lines) and new_lines[k].startswith('> '):
        k += 1
    arch_ptr = (
        '> 🔴 本节 1 条较旧「最近更新」条目（🔴 2026-11-23 20:2x「执行 APP-128」＝§224）原文已**整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_recent_updates_20261124b.md`（%d B／块 SHA256 `%s`）；**原文一字未删、未改**。'
        % (len(arch_body.encode('utf-8')), arch_sha)
    )
    new_lines = new_lines[:k] + [arch_ptr] + new_lines[k:]

    # 头部「更新时间」（last_ack 不变）
    for i, l in enumerate(new_lines[:12]):
        if l.startswith('更新时间:'):
            new_lines[i] = '更新时间: ' + UPDATED
            break
    else:
        print('[FAIL] 未找到「更新时间」行')
        return 3

    # 末尾追加 §227
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()
    new_lines += ['', SECTION_TITLE, SECTION_POINTER, '']
    new = '\n'.join(new_lines)

    # ── 真不变量 ──
    fails = []

    def chk(name, cond, detail=''):
        print('  %-46s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
        if not cond:
            fails.append(name)

    print('[info] 新 STATUS_APP.md %d B / %d 行'
          % (len(new.encode('utf-8')), new.count('\n')))
    chk('字节数 ≤ 40 000', len(new.encode('utf-8')) <= LIMIT_BYTES,
        '(%d)' % len(new.encode('utf-8')))
    chk('行数 ≤ 300', new.count('\n') <= LIMIT_LINES, '(%d)' % new.count('\n'))

    # ③ 旧每一行（非空）仍可数到，且次数不少于原来
    #    （**两处允许的例外**，白名单在此显式列出，不藏着）：
    #      a) 被归档的那一条「最近更新」真条目（−1）
    #      b) 头部「更新时间」行（**纪律明确要求**用实测值覆盖）—— 旧值必须被新值取代
    ALLOWED = {oldest, next(l for l in lines if l.startswith('更新时间:'))}
    o_cnt = collections.Counter(l for l in lines if l.strip())
    n_cnt = collections.Counter(l for l in new_lines if l.strip())
    short = {l[:60]: (o_cnt[l], n_cnt[l]) for l in o_cnt
             if n_cnt[l] < o_cnt[l] - (1 if l in ALLOWED else 0)}
    chk('旧每一行仍可数到（只追加不删改；例外白名单 2 条）', not short, str(short)[:300])
    chk('头部「更新时间」已换成实测值',
        ('更新时间: ' + UPDATED) in new and UPDATED != next(
            l for l in lines if l.startswith('更新时间:')).split(': ', 1)[1])

    chk('last_ack 未变（仍 APP-128）', 'last_ack: APP-128' in new)
    chk('§227 章节已追加', '## §227' in new)
    chk('§227 标题行只出现一次', new.count('## §227') == 1)
    chk('§227 指针行指向 companion', os.path.basename(COMPANION) in new)
    chk('归档指针含归档件路径', 'STATUS_APP_recent_updates_20261124b.md' in new)
    chk('无 CR 引入', '\r' not in new)
    chk('结尾有换行', new.endswith('\n'))
    o_secs = set(re.findall(r'§\d+', orig))
    n_secs = set(re.findall(r'§\d+', new))
    chk('旧 § 编号全部存活', not (o_secs - n_secs), str(sorted(o_secs - n_secs))[:200])

    if fails:
        print('[FAIL] 不变量未过：%s ⇒ 源文件零改动' % fails)
        return 4

    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app227')
    shutil.copy2(STATUS, bak)
    print('[info] 备份 %s' % bak)
    write_atomic(STATUS, new)
    print('[ok] 已写盘：%s（%d B / %d 行）'
          % (STATUS, len(new.encode('utf-8')), new.count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
