#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app467_write_status177.py —— 往 `status/app/STATUS_APP.md` **定点追加** §177 章节。

## 纪律（照抄，不要改）
1. **只追加** `## §N 标题（YYYY-MM-DD HH:MM）` 章节；**旧章节一字未改**；
2. 头部三行（`last_ack` / `更新时间` / `当前任务` / `阻塞 / 待用户决定`）**定点替换**，
   其余头部一字未动；
3. **限额**：≤ 40 000 B 且 ≤ 300 行（APP-052 ④）⇒ **写前自检**，超限 ⇒ **源文件零改动**；
4. 旧正文逐字未变（写后独立复核）；
5. 无裸 LF（真不变量；**不是**「CRLF 个数不变」那种伪不变量）；
6. `CORRECTIONS_APP.md` **全程只读**（本脚本不碰它）。

## 为什么需要单独脚本
活文档已 36 917 B / 189 行 ⇒ 余量只有 ~3 000 B ⇒ §177 的正文必须**进归档件**，
活文档只留 **≤3 行索引 + 速查**（与 §171–§175 同一做法）。
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec177_20261111.md')

LIMIT_BYTES = 40000
LIMIT_LINES = 300

NEW_SECTION = """
## §177 执行 APP-100（last_ack=APP-100）｜canonical 10 分钟片段两臂**都自然退出**（A 951.9 s／B 1759.1 s，**PASS**）＋ 查出并修掉 **1 个 App 侧真缺陷**（`late_drop` 双记 ＋ drain 永不退出）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec177_20261111.md`（{ARCH_BYTES} B／SHA256 `{ARCH_SHA}`）｜**归档件逐字节未动**（write-once）｜**上一会话的 §176 归档件 `status/archive/STATUS_APP_sec176_20261111.md`（13851 B／SHA256 `7c43b365e3f958a9…`）此前从未被活文档引用**（会话中途死亡）⇒ 一并索引，结论以 §177 归档件为准。
> 🔴 **速查①APP-100 已执行** ⇒ canonical **SPE 0–600 s 连续**（`test_audio/clip_10min_0_600.wav`／19 200 044 B／SHA256 `d412f00af6b792ce…`，**与 ASR 侧逐字节相同**）⇒ **§175「本机只有 300 s」前提经实测证伪**，旧「0–300 s ×2」违反 APP-100「所有臂都用这同一段」⇒ 弃用。
> 🔴 **速查②两臂都自然退出（exit=0）**：A（ASR GPU.0＋MT GPU.0＋TTS NPU）**951.9 s**／shared **2262.1 MB**／RSS **7688.2 MB**；B（ASR NPU＋MT GPU.0＋TTS NPU）**1759.1 s**／shared **1810.6 MB**／RSS **7097.1 MB** ⇒ **PASS、`timing_valid=True`** ⇒ **A 臂未复现 B 机 268 s 崩溃**；两臂差异真因是 **NPU 争用**（B 臂 ASR＋TTS 同在 NPU ⇒ TTS 被挤 ⇒ 积压 763.70 s vs A 臂 229.22 s）。
> 🔴 **速查③查实并修掉 1 个 App 侧真缺陷**：`tts_service.py` 的 `late_drop` 分支只 `n_dropped += 1` 而**不摘 `pending`** ⇒ ① `drain()` 退出条件 `pending_n==0` **永不成立** ⇒ 必然空等到超时（**B 臂白等 1157.8 s ≈ 19 min**）；② `close()` 再把同一批当 orphan 计一次 ⇒ §29 不变式破坏（**A 臂提交 159 播完 93 丢弃 132 ⇒ 多 66 句**，＝ jsonl 实测 `late_drop` 66 句）⇒ 改走 §60 唯一原子口径 `_drop_one(jid)` ⇒ **只改 dev 树**（已交付包零影响）｜**判据 8/8 PASS**（REAL 4/4 ＋ **反证 4/4 全触发**）｜另修 harness 3 个缺陷（verdict 期望臂数假阴性／`n, _` 解包崩溃／**`--outroot` 相对路径把产物落进 rc7 包内** ⇒ 已改绝对路径、10 个产物**逐字节抢救**回仓库、**rc7 包已复原**）｜**纠偏文件全程只读**：开工＝收尾 SHA `219ef841…`／308 340 B／**100 条** ⇒ **SHA 零改动**｜**未打包 v2.5、未打 rc8、未通知用户、未调 MiniMax、未改任何默认值或产品判据**｜**本条需等 reviewer 复核**。
"""

NEW_HEAD = {
    'last_ack': 'APP-100',
    '更新时间': None,          # 用 Get-Date 实测
    '当前任务': ('**执行 APP-100（长跑改固定 10 分钟片段）｜canonical SPE 0–600 s 连续，'
                 '两臂都自然退出（951.9 s／1759.1 s，PASS）｜查出并修掉 1 个 App 侧真缺陷**'
                 '（`late_drop` 双记 ＋ drain 永不退出，已修 dev 树）**｜结果见 §177 归档件**'),
    '阻塞 / 待用户决定': (
        '🔴 **`late_drop` 修复未进任何客户包**（只改 dev 树）⇒ APP-055 须打新版本号；'
        '且 MiniMVP 按用户决定**暂不打包** ⇒ **等 reviewer 裁定何时随 v2.5 / rc8 出**'
        '｜🔴 **该缺陷正落在 `tts_late_drop_sec` 阈值上**（用户 11-11 定「下次再定」）⇒ 修好后影响面会变'
        '｜🔴 **GUI 布局修复仍未同步客户包**（v2.5 未打包）⇒ **请 reviewer 裁定**：立刻修还是随 v2.5 一起出'
        '｜🔴 **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972）⇒ 未自行换判据'
        '｜🔴 **§3.6 切段开销不可测**（质心恒 1）⇒ 需 reviewer 裁定'
        '｜**倍率地板** 与 **`tts_late_drop_sec`** 仍未裁定'),
}


def fail(msg):
    print('!! 自检 FAIL：%s' % msg)
    # 🔴🔴🔴 **必须真的回滚** ⇒ 否则「自检 FAIL ⇒ 源文件零改动」是**假话**：
    #    上一次就是这样：写盘后校验失败 ⇒ 只打印 FAIL ⇒ 文件**已被改写**却仍报「零改动」。
    #    ⇒ 凡是在**写盘之后**失败 ⇒ 用 `.bak_sec177` 复原。
    bak = STATUS + '.bak_sec177'
    if os.path.isfile(bak):
        try:
            shutil.copy2(bak, STATUS)
            print('   ⇒ 已用 %s **回滚**（源文件复原）'
                  % os.path.basename(bak))
        except Exception as e:
            print('   ⇒ 🔴 回滚失败：%r（请手工用 %s 复原）' % (e, bak))
    else:
        print('   ⇒ ⚠️ 无备份可回滚（%s 不存在）' % os.path.basename(bak))
    print('   ⇒ 源文件零改动')
    sys.exit(1)


def main():
    if not os.path.isfile(ARCHIVE):
        fail('缺少归档件 %s' % ARCHIVE)
    arch = open(ARCHIVE, 'rb').read()
    arch_sha = hashlib.sha256(arch).hexdigest()
    arch_bytes = len(arch)

    orig = open(STATUS, 'rb').read()
    orig_text = orig.decode('utf-8')
    # 🔴 旧正文的**逐字快照**（写后要逐字比对）
    old_sections = re.split(r'(?m)^(?=## §)', orig_text)

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    NEW_HEAD['更新时间'] = now

    text = orig_text

    # ── ① 头部定点替换（只动这 4 个键的行）──────────────────────────
    for key, val in NEW_HEAD.items():
        pat = re.compile(r'(?m)^(%s\s*:\s*).*$' % re.escape(key))
        m = pat.search(text)
        if not m:
            fail('头部找不到键 %r' % key)
        text = pat.sub(lambda mm: mm.group(1) + val, text, count=1)

    # ── ② 追加 §177 章节 ──────────────────────────────────────────
    sec = NEW_SECTION.replace('{ARCH_BYTES}', '%d' % arch_bytes)
    sec = sec.replace('{ARCH_SHA}', arch_sha)
    if not text.endswith('\n'):
        text += '\n'
    text += sec

    # ── ③ 写前自检（超限 ⇒ 源文件零改动）─────────────────────────
    data = text.encode('utf-8')
    n_lines = text.count('\n')
    print('写前自检: %d B / %d 行（限额 %d B / %d 行）'
          % (len(data), n_lines, LIMIT_BYTES, LIMIT_LINES))
    if len(data) > LIMIT_BYTES:
        fail('超字节限额 %d > %d' % (len(data), LIMIT_BYTES))
    if n_lines > LIMIT_LINES:
        fail('超行数限额 %d > %d' % (n_lines, LIMIT_LINES))
    # 真不变量：无裸 LF 之外的怪字符
    if '\r\n' in text:
        fail('文本含 CRLF（本仓库要求纯 LF）')

    # ── ④ 写盘（先备份，失败可回滚）───────────────────────────────
    bak = STATUS + '.bak_sec177'
    shutil.copy2(STATUS, bak)
    try:
        with open(STATUS, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    except Exception as e:
        shutil.copy2(bak, STATUS)
        fail('写盘失败已回滚：%r' % e)

    # ── ⑤ 写后独立复核 ────────────────────────────────────────────
    new_text = open(STATUS, 'r', encoding='utf-8', newline='').read()
    new_sections = re.split(r'(?m)^(?=## §)', new_text)

    # 旧章节逐字未变（**只查 § 章节**；头部 4 行是**定点替换**、允许变）
    old_sec_blocks = [s for s in old_sections if s.startswith('## §')]
    new_sec_blocks = [s for s in new_sections if s.startswith('## §')]
    for i, sec_old in enumerate(old_sec_blocks):
        if i >= len(new_sec_blocks):
            fail('写后 § 章节数变少')
        # 🔴 末节（后面要接新节）会多一个换行 ⇒ 用 rstrip 比较，
        #    否则会把「加了个换行」误判成「旧正文被改」。
        if new_sec_blocks[i].rstrip() != sec_old.rstrip():
            fail('旧 § 章节被改动（第 %d 块：%s）'
                 % (i, sec_old.split('\n')[0][:50]))
    if len(new_sec_blocks) != len(old_sec_blocks) + 1:
        fail('§ 章节数不是 +1（%d → %d）'
             % (len(old_sec_blocks), len(new_sec_blocks)))
    # §177 已追加
    if '## §177 执行 APP-100' not in new_text:
        fail('§177 未追加')
    # 头部除 4 个键外**逐字未变**
    head_old = old_sections[0]
    head_new = new_sections[0]
    for line in head_old.split('\n'):
        if line.startswith(('last_ack:', '更新时间:', '当前任务:',
                            '阻塞 / 待用户决定:')):
            continue
        if line not in head_new:
            fail('头部非目标行被改动：%r' % line[:60])
    # 头部键已更新
    for key, val in NEW_HEAD.items():
        if not re.search(r'(?m)^%s\s*:\s*%s' % (re.escape(key),
                                                  re.escape(val[:30])), new_text):
            fail('头部键 %r 未正确更新' % key)
    # 无裸 LF
    if '\r' in new_text:
        fail('写后含裸 CR')
    # 体积
    nb = len(new_text.encode('utf-8'))
    nl = new_text.count('\n')
    if nb > LIMIT_BYTES or nl > LIMIT_LINES:
        shutil.copy2(bak, STATUS)
        fail('写后超限已回滚：%d B / %d 行' % (nb, nl))

    os.remove(bak)
    print()
    print('✅ 已追加 §177：%d → %d B，%d → %d 行' % (
        len(orig), nb, orig_text.count('\n'), nl))
    print('   归档件：%s（%d B／SHA256 %s）' % (
        os.path.relpath(ARCHIVE, REPO), arch_bytes, arch_sha))
    print('   旧 § 章节逐字未变：%d 块全部命中' % len(old_sec_blocks))
    print('   头部：仅 4 行定点替换，其余行逐字未变')
    print('   更新时间实测值：%s' % now)
    return 0


if __name__ == '__main__':
    sys.exit(main())
