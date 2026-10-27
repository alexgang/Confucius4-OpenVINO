#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""§65 —— 更新 STATUS_APP.md 的头部字段 + 追加 §65 章节。

🔴🔴 纪律（沿用 §64 修好的两处）：
  - **章节计数用正则** `^## §\d+`（只数标题行）⇒ 正文引用不算章节；
  - **「最近更新」按行切片**（不能用 `re.search(r'.*?$)` ⇒ `$` 在 MULTILINE
    下只吃 1 行 ⇒ 旧的 29 行会整体丢掉）；
  - 头部切片用「首个章节锚点 `## §1 `」⇒ `lines[i_s1:]` 原样保留；
  - 新章节**追加在文件末尾** ⇒ 不回头改旧章节；
  - 字段唯一性断言用「**行首精确匹配**的行计数」（子串会误命中正文引用）；
  - STATUS 是 **LF** 换行 ⇒ 用 `newline=''` 读写；
  - 写盘前 `shutil.copy2` 备份 + 多项前置断言。
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'status', 'app', 'STATUS_APP.md')
NEW_SECTIONS = [os.path.join(HERE, '_app065_status_section.md'),
                 os.path.join(HERE, '_app066_status_section.md')]
BACKUP = os.path.join(HERE, '_app065_status_backup.md')

NOW = '2026-10-27 11:05'   # 🔴 Get-Date 实测值，禁止推算
LAST_ACK = 'APP-023'       # 🔴 APP-024 只做了 ①，②③④ 未做 ⇒ 不进 last_ack

RECENT = [
    r'11:05 §66 🔴🔴🔴 **【用户明文新口径】以后不做一致性校验、不开 FTP 服务** ⇒ **覆盖 §61 的交付四步**：第 ③ 步 `verify_pkg_zip.py` 独立复核 **取消**、第 ④ 步 `publish_ftp.py` 重发 FTP **取消** ⇒ 新流程 = **定点同步 → 先提交 → 持锁重打 zip**（+ 一道**只读本地**的「zip ⇄ 包目录 diff = 0」）',
    r'11:05 §66 🔴 **「已交付」口径改写**：**不再**以「三方闭环（源 zip = FTP 副本 = 包目录）」为准 ⇒ 改为 **「包目录 + zip 已含最新代码，且该代码已入库（`HEAD`）」** ⇒ §61/§64 的 FTP 结论**只作历史记录**，不得再作对外报数依据',
    r'11:05 §66 ⚠️ **别把新口径读成「不用打包了」** —— 取消的是**校验与 FTP**，**不是打包** ⇒ APP-024① 代码（10:38）**在**上次打包（10:17–10:31）**之后** ⇒ 当前 zip 仍旧版 ⇒ **仍必须持锁重打 zip**',
    r'11:05 §65 ✅ **§64 真正落盘**（前两次被脚本自身断言拦下 ⇒ STATUS 未被误改）：修 2 处「脚本缺陷」——① 章节计数用子串 `count(\'## §\')` ⇒ 改正则 `^## §\d+`（63→64）② 「最近更新」用 `re.search(.*?$)` ⇒ `$` 在 MULTILINE 下只吃 **1 行** ⇒ 旧的 **29 行会整体丢** ⇒ 改**按行切片**（保留 15 行）',
    '11:05 §65 🔴🔴 **发现并修掉 2 处 U+FFFD 损坏字符**（「保留在**工**作区」）⇒ 字节层修复 ⇒ 两文件 U+FFFD 计数 **0**（备份里本就是 0 ⇒ 未污染旧 STATUS）',
    '11:05 §65 ✅ **已提交 `2d19402`**（10 files / +1073 / −29）⇒ 逐文件 `git add`、**未提交** `CORRECTIONS_APP.md`、**未吞**他模块（提交前实测 **479** 项全留）',
    '11:05 §65 ✅ **已定点同步客户包**：新建 `sync_app024_to_pkg.py`（`git show 0d1be9d` + `get_grouped_opcodes(n=3)` **自动派生**，禁整目录覆盖）⇒ `tts_service.py` 4 块 + `tts_worker.py` 4 块**全部唯一命中** ⇒ 归一化后与仓库**逐字节相同**',
    '11:05 §65 🔴🔴 **踩到「换行差异让 diff 退化」**：仓库 `tts_service.py` 是 **CRLF 1550 处**、包侧 LF ⇒ 裸 diff 把整文件当一块（`-1503/+1550`）⇒ 修法 = **派生前归一化为 LF** ⇒ 块粒度回到 `-6/+N`',
    '11:05 §65 🔴🔴 **新交付代差（自查发现）**：APP-024① 改代码（10:38）**在打包（10:17–10:31）之后** ⇒ zip 仍是 10:28 旧版 ⇒ **必须重打包**',
    r'11:05 §65 🔴 **自曝一处自造事故**：备份目录 `_pkg_backup_app_s64` 放**在包目录内** ⇒ 复核误报「237 个缺失」⇒ 已移至**包外** `C:\Users\Trekker-PTL\pkg_backup_app_s64`（合历史惯例）⇒ 教训：**包目录内不许放任何备份/临时文件**',
    '11:05 §65 🔴 **停在「等锁重打包」**：ASR 活锁 `PID 34724`（`pya_app_baseline_base61`，exit=259）⇒ **不抢不删**；TTS runner 也在等空闲 ⇒ **App 打包是解锁链的一环** ⇒ 拿到锁就尽快打包并释放',
]

TASK = ('**§66 🔴🔴🔴 【用户新口径】以后不做一致性校验、不开 FTP 服务** ⇒ 交付流程改写为 '
        '**定点同步 → 先提交 → 持锁重打 zip**（+ 只读本地「zip ⇄ 包目录 diff = 0」）⇒ '
        '**「已交付」口径改为「包目录 + zip 已含最新代码且已入库」**'
        ' + ✅ **§65 §64 真正落盘**（修 2 处应用脚本缺陷 + 2 处 U+FFFD）'
        ' + ✅ **已提交 `2d19402`**（APP-024① 首包拆两段 + app093/app096 去硬编码 + app097 验收）'
        ' + ✅ **已定点同步客户包**（8 块全部唯一命中；🔴 换行差异让 diff 退化 ⇒ 归一化后才派生出精确块）'
        ' + 🔴 **新交付代差**：APP-024① 改在打包之后 ⇒ zip 仍旧版 ⇒ **仍须重打包**'
        ' + 🔴 **自曝一处自造事故**：备份目录放包内 ⇒ 复核误报 237 缺失 ⇒ 已移至包外'
        ' ⇒ 🔴 **停在等 ASR 活锁（PID 34724）释放** ⇒ 拿到锁即重打包（**不再**跑全量复核、**不再**跑 FTP）'
        ' ⇒ 🔴 **APP-024②③④ 未做** ⇒ **`last_ack` 保持 APP-023**'
        ' ⇒ ⛔ **同时仍停在 §63 的 L4 等用户实测**（桌面快捷方式 ⇒ 测试声音 → CUDA → NPU）')

BLOCK = ('① 🔴 **§66 用户新口径生效**：**不再做一致性校验（`verify_pkg_zip.py`）、不再开 FTP 服务** ⇒ '
         '交付流程 = **定点同步 → 先提交 → 持锁重打 zip**（+ 只读本地「zip ⇄ 包目录 diff = 0」）⇒ '
         '**FTP 服务保持关闭**；🔴 **「已交付」不再以「三方闭环」为准** ⇒ 改为「包目录 + zip 已含最新代码且已入库」；'
         '② 🔴 **§65.5 等 ASR 活锁释放**（`PID 34724` / `pya_app_baseline_base61` / exit=259 ⇒ 活锁）⇒ **不抢不删** ⇒ 释放后**只重打 zip**（**不再**跑全量复核、**不再**跑 FTP）；'
         '🔴 **当前 zip 不含 APP-024① ⇒ 仍不写「已交付」**；'
         '③ ⛔ **§63 的 L4 等用户实测**（需人）：桌面快捷方式 →「🔊 测试声音」→ CUDA 朗读一句 → NPU 朗读一句 ⇒ 反馈听到/听不到 + `%LOCALAPPDATA%\\Confucius4LiveCaption\\session_*.log` 路径 ⇒ **用户亲口确认前不得写「能出声」**；'
         '④ 🔴 **APP-024②③④ 未做**（加载期句子单独列 / 按 BRIEF 素材持锁重跑 ABBA / 「加载期攒句是否按 8 s 丢」—— reviewer 明文「**不要自己改**」）⇒ **`last_ack` 保持 APP-023**；'
         '⑤ ✅ **§65.2 已提交 `2d19402`**（逐文件 add、**未提交** `CORRECTIONS_APP.md`、**未吞**他模块 **479** 项）⇒ 🔴 **尚未 push**；'
         '⑥ 🔴 **§66.2 别误读**：取消的是**校验与 FTP**，**不是打包** ⇒ APP-024① 改代码（10:38）**在**打包（10:17–10:31）**之后** ⇒ **仍必须重打 zip**；'
         '⑦ 🔴 **§65.4 自造事故已修**：备份目录从**包内**移到**包外** `pkg_backup_app_s64` ⇒ 教训：**包目录内不许放备份/临时文件**（会被 `pkg_exclude`/MANIFEST 统计到）；'
         '⑧ 🔴 **APP-022 集成需等 ASR-013 + TTS-019 交付**（§55 只做接口预留，**未集成**）；'
         '⑨ 🔴 **术语表 / `packaging` 默认值待用户决定**（MT 通知 14 建议已被用户 09:01 **作废** ⇒ App 不改术语表）；'
         '⑩ 🔴 **§50.5 需 TTS 模块配合**（App 不代跑尺子）；'
         '⑪ 🔴 **§45.6①–⑤ / §44 `MAX_SEG_SPAN=2` / §46.5 / §42.3 / MT 通知 13 回复** ⇒ 等 reviewer 裁定；'
         '⑫ 🔴 **§56.9**：TTS-019 `single` 臂 / TTS-017① `A_CPU` 臂是否重跑由 TTS 自行决定；'
         '⑬ 🔴 **§56.2**：ASR/TTS 侧锁写法的**独占性**待其自评；'
         '⑭ 🔴 **§57**：历史遗留未跟踪文件（`sync_c148b_to_pkg.py` / `sync_c150_to_pkg.py` / `app073*` / `app074*` 等）**归属未判定** ⇒ 本轮**未提交**；'
         '⑮ 🔴 **§64.6**：`test_tts_cmp_orig.py` 因 `_orig_mod/` **从未入 git** 而无法运行 ⇒ **环境缺失非回归**')


def set_field(lines, key, value):
    """替换 `key: value` 行。value **不得**含 key 前缀。"""
    prefix = key + ': '
    assert not str(value).startswith(prefix), \
        'value 已含 key 前缀 ⇒ 会写两遍: %r' % value
    hit = 0
    for i, ln in enumerate(lines):
        if ln.startswith(prefix):
            lines[i] = prefix + value
            hit += 1
    assert hit == 1, '字段 %r 命中 %d 次（应为 1）' % (key, hit)
    return lines


def main():
    shutil.copy2(STATUS, BACKUP)
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    lines = text.split('\n')

    # ── 找首个章节锚点 ────────────────────────────────────────────────
    i_s1 = None
    for i, ln in enumerate(lines):
        if ln.startswith('## §1 '):
            i_s1 = i
            break
    assert i_s1 is not None, '找不到 "## §1 " 锚点'
    head = lines[:i_s1]
    body = lines[i_s1:]
    print('头部行数 =', len(head), ' 正文行数 =', len(body))

    # ── 头部字段 ──────────────────────────────────────────────────────
    set_field(head, 'last_ack', LAST_ACK)
    set_field(head, '更新时间', NOW)
    set_field(head, '当前任务', TASK)
    set_field(head, '阻塞 / 待用户决定', BLOCK)

    # ── 「最近更新」区块（按行切片，**不用** `re.search(.*?$)`）────────
    i_rec = None
    for i, ln in enumerate(head):
        if ln.strip() == '## 最近更新':
            i_rec = i
            break
    assert i_rec is not None, '找不到「## 最近更新」'
    end_rec = i_rec + 1
    while end_rec < len(head) and not head[end_rec].startswith('## §'):
        end_rec += 1
    old_rec = [x for x in head[i_rec + 1:end_rec] if x.strip()]
    assert len(old_rec) >= 5, '「最近更新」只抓到 %d 行 ⇒ 切片有误' % len(old_rec)
    merged = (RECENT + old_rec)[:15]
    assert len(merged) <= 15, '最近更新 %d 行 > 15' % len(merged)
    print('最近更新：旧 %d 行 + 新 %d 行 ⇒ 保留 %d 行' %
          (len(old_rec), len(RECENT), len(merged)))

    keep = head[end_rec:]
    new_head = head[:i_rec + 1] + merged + [''] + keep

    # ── 新章节（可多章，依次追加在文件末尾）────────────────────────────
    new_parts = []
    for sec_path in NEW_SECTIONS:
        with io.open(sec_path, 'r', encoding='utf-8', newline='') as f:
            sec = f.read()
        sec = sec.replace('\r\n', '\n').rstrip('\n')
        assert '�' not in sec, '新章节 %s 含 U+FFFD 损坏字符 ⇒ 不写盘' % sec_path
        new_parts.append(sec)

    out = new_head + body + ['']
    for sec in new_parts:
        out = out + sec.split('\n') + ['']
    out_text = '\n'.join(out)

    # ── 写盘前断言 ────────────────────────────────────────────────────
    n_old = len(re.findall(r'^## §\d+', text, re.M))
    n_new = len(re.findall(r'^## §\d+', out_text, re.M))
    assert n_new == n_old + len(NEW_SECTIONS), \
        '章节数不对: %d → %d（应 +%d）' % (n_old, n_new, len(NEW_SECTIONS))
    print('章节数（标题行）: %d → %d' % (n_old, n_new))
    for old_sec in ('## §62 ', '## §63 ', '## §64 ', '## §65 ', '## §66 '):
        assert old_sec in out_text, '章节 %s 缺失' % old_sec
    assert 'last_ack: APP-023' in out_text
    for key in ('last_ack: ', '更新时间: ', '当前任务: ', '阻塞 / 待用户决定: '):
        n = sum(1 for ln in out_text.split('\n') if ln.startswith(key))
        assert n == 1, '%s 出现 %d 次（应为 1）' % (key, n)
    assert sum(1 for ln in new_head if ln.startswith('- ')) <= 15
    assert '�' not in out_text, '输出含 U+FFFD ⇒ 不写盘'

    with io.open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(out_text)
    print('已写盘:', STATUS, os.path.getsize(STATUS), 'B')


if __name__ == '__main__':
    main()
