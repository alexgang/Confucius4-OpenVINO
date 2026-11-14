#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app558_write_status_sec203.py —— 写 STATUS_APP §203（巡检轮：无新纠偏）。

🔴 **口径（§185／APP-052④／§193 ⑦／§194 ⑦）**：
  · 只**追加** §203 一节，**不回头改旧章节**；
  · 活文档逼近 **40 000 B** 上限 ⇒ 先把 **§202 正文整块逐字归档**
    ⇒ `status/archive/STATUS_APP_sec202_20261114.md`（**write-once**）
    ⇒ 活文档保留 §202 **标题行** ＋ 1 行指针（**分隔符原样保留**）；
  · 头部 `last_ack` **不变**（无新纠偏 ⇒ 不写自己的编号），只更新「更新时间」；
  · 写后自检：≤40 000 B ／ ≤300 行 ／ 章节数不少 ／ 旧正文逐字未变
    （**还原式复核**）／归档件 SHA 与指针声明一致；
  · 状态写入脚本**一次性** ⇒ **不入库、不提交**（§193 ⑦／§194 ⑦ 口径）。
"""
import hashlib
import os
import re
import shutil
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
ARCH_202 = os.path.join(ARCH_DIR, 'STATUS_APP_sec202_20261114.md')
ARCH_RU = os.path.join(ARCH_DIR, 'STATUS_APP_recent_updates_20261114b.md')
BACKUP = os.path.join(REPO, 'results', 'app', '_backup_STATUS_APP_before_203.md')
NOW = '2026-11-14 18:28:17'
OLD_TS = '2026-11-14 17:17:05'

SEC203 = r"""
## §203 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉包矩阵闸门 `app512` 的覆盖漏洞：SpecialMVP 两个客户包从未进过闸门**｜**「10 个带缺陷包」经全盘 AST 复核数字不变**｜**未打包／未改客户包／未改产品代码**｜**本条需等 reviewer 复核**

> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾 **109 条**／最大 **APP-109**／SHA256 `30a55189…`（全 64 位同 §202 ①）／**360 842 B**／mtime **2026-11-14 15:38:28** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` **仍 APP-109**（无新纠偏 ⇒ **不写自己的编号**）⇒ **本轮无新条目可执行**。⚠️ `git status` 的 ` M` 属**常态**（HEAD blob 仅 **10 854 B** ／ 工作区 **360 842 B** ／ `+2 451 / −0` ⇒ reviewer 自 10 月起持续追加、**我方从不提交该文件**；**非** autocrlf 假阳性 —— CRLF **0**、全 LF）。
> **② 其它 5 通道全空**：agent-mail **`not_bound`**（面板 connected 但实际未开通）｜`conversation_search`（11-14）**0 命中**｜仓库内 `NOTICE*` **0 个**、`shared/NOTICE*` 最新仍 **11-02 16:26**｜git `origin/main...main` = **0/0**（HEAD `e778f44`，已 push）｜`MACHINE_LOCK` **NOT_PRESENT**（零推理／零计时 ⇒ **未取锁**）｜根 `status/CORRECTIONS.md` 仍 **10-24 17:01**（268 334 B）；ASR 侧 **27 条／最大 ASR-058**／mtime **11-14 15:29**（**无 App 侧条目**）。
> **③【🔴 实质发现 ①（闸门层真缺陷）：包矩阵闸门 `app512` 漏扫 SpecialMVP 整个形态 ⇒ §195／§202 刚出的两个客户候选包从未进过任何闸门】**：原 `pkg_dirs()` 只认两个前缀（完整版 `…_v*` ＋ MiniMVP `…_MiniMVP_v*`）⇒ 实测**只扫 19 个包**（§194 引用的「19 包」即此数），而磁盘上客户包目录实为 **21 个**（§201 修正为「20 目录＋1 zip」；本轮因 sp2 出包 ⇒ **21 目录＋1 zip**）⇒ **差的正是 sp1＋sp2**。**这是 §190 老教训在包级的复现**：「缺文件 ≠ 不适用」⇒ 包级同样成立「**没扫 ≠ 没缺陷**」。**修法（只改覆盖范围，不改任何 verdict 口径）**：枚举放宽到 `Confucius4_LiveCaption_` ⇒ 复跑 **21/21 全扫**（evidence 新增 `coverage`：候选 **21**／已扫 **21**／跳过 **0**／`coverage_ok=true`）⇒ **sp1＝PASS 11/0、sp2＝PASS 11/0**（两者**均已带** APP-086·2a 收窄 ⇒ **无产品缺陷**，只是**从未被闸门验过**）。
> **④【🔴 实质发现 ②（闸门层潜在口子）：`app512` 会静默丢弃没有 `app/tts_worker.py` 的包目录】**：原实现 `if os.path.isfile(...): out.append(...)` ⇒ 无该文件的目录**直接被丢掉** ⇒ 矩阵报的「N 个包」会**静默少于**磁盘实际包数，**且从 evidence 看不出来**（§201 修正过的「目录数」与矩阵「包数」从此对不上）。**修法**：候选目录**都进矩阵**，无该文件的单列为 **`SKIP_NO_TTS_WORKER`** 行（`branch2_exists=null`／`tag` 明写「判据**不适用**，**不得当作通过**」）**不计入通过数**；evidence 另写 **`coverage`**（候选／已扫／跳过三数）⇒ **矩阵不可能再少报**。**本轮实测跳过＝0**（21 个目录全有该文件）⇒ **未实际发生**，属**预防性修复**。
> **⑤【独立复核：「10 个带缺陷包」数字不变】**：本轮**另做一次全盘 AST 复核**（不依赖 `app512` 字符串判定，直接对 21 个包的 `synth()` 里 `if spk:` 分支做 AST 判定）⇒ **恰 10 个包**存在**分支② 存在且无 `_bound` 守卫**（＝真缺陷）：完整版 **v2.2／v2.3／v2.3_aborted／v2.4** ＋ MiniMVP **v1.0／rc1／rc2／rc3／rc4／rc5**；**另 3 个包（v1.13／v2.0／v2.1）分支② 根本不存在**（`b2cnt=0`）⇒ **缺陷不适用、非缺陷**（⇒ **v2.1＝当前交付版本身不带该缺陷**）；**v1.5** 连 `if spk:` 分支都没有 ⇒ **判据不适用**。⇒ **「带缺陷的包共 10 个」的口径经复核仍成立**。
> **⑥【§194 ④ 的 `tag` 三分支改法：本轮仍未改，等 reviewer 裁定】**：§194 ④ 已把「① `branch2_exists=false`⇒判据不适用／② 有守卫⇒收窄在／③ 无守卫⇒缺收窄」**挂起等裁定**（APP-106 §4 ＋ §193 ⑤）⇒ **本轮遵守**：只改覆盖、**不改 `tag` 语义** ⇒ 复跑后 `v1.5` 的 `tag` 仍显示「收窄在包里」而 `verdict=FAIL 2/8`（**自相矛盾仍存在，等裁定**；§194 已入册）。
> **⑦【目标机与用户真配置】**：目标机 `192.168.2.194` **仍整体离线**（ping **无 ARP 条目**、ICMP 由网关回「无法访问目标主机」⇒ 同 §199）⇒ §197／§198 的**两端 SHA256 对账仍无法闭环**（需用户开机＋给凭据）｜**用户真 `device_config.json` 完好**：`C:/Users/Trekker-PTL/AppData/Local/Confucius4LiveCaption/device_config.json` = **59 B**／SHA256 `9d484c1c9402d7a9911f2af6a53f6e056a18039715b8bda9ec15ddecf6b473a2`（同 §202 记录 ⇒ 本轮**未动**）。
> **⑧【纪律】**：**未打包**（未打任何 zip；**sp2 仍无 zip**，等用户通知）｜**未改客户包**（21 个包目录**全部只读**）｜**未改产品代码**（`live_caption/` 与 `pack_v13.py` **零改动**；唯一改动＝**闸门脚本** `results/app/app512_pkg_follow_speaker_matrix.py` ＋其 evidence）｜**未改 `CORRECTIONS_APP.md`**｜**未跑推理／未计时 ⇒ 未取锁**｜**未调 MiniMax**｜**未动 B 机任何文件**（APP-109 ④）｜**未提交**其它模块的未提交改动（**逐文件** `git add`，**未提交** `CORRECTIONS_APP.md`）。
> **⑨【证据（字节／mtime／SHA256）】**：`results/app/app512_pkg_follow_speaker_matrix.json` = **14 427 B**／mtime **2026-11-14 18:28**／SHA256 `0460b897f240fb59ee76b2d314a424d303139826503b9f4ec5e3159c7797a4bf`（**复跑后原地覆写**；旧版可 `git show HEAD:…` 取回）｜`app512_pkg_follow_speaker_matrix.py` = **10 999 B**（改动＝枚举放宽 ＋ SKIP 行 ＋ `coverage` 字段）｜状态写入脚本 `_app558_write_status_sec203.py`（一次性，**按 §193 ⑦／§194 ⑦ 不入库、不提交**）｜改前逐字节备份 `results/app/_backup_STATUS_APP_before_203.md`。
> **⑩【压缩（APP-052④ 上限 40 000 B／300 行）】**：**§202 正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec202_20261114.md`（块 SHA256 见该文件末）⇒ 活文档保留 §202 标题行 ＋ 1 行指针（§202 完整正文另存 `status/app/STATUS_APP_sec202_detail_20261114.md`，**未动**）；**「最近更新」2 条较旧整条逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261114b.md`（块 SHA256 见该文件末）⇒ 活文档换 1 行指针。
> **⑪ 本条需等 reviewer 复核**：① §203 ③ 覆盖修法是否认可；② §203 ④ SKIP 行＋`coverage` 是否认可；③ **§194 ④ 的 `tag` 三分支改法**是否采纳（**本轮仍未改**）；④ **sp2 的 zip**（须**用户通知**）；⑤ **TTS 是否改为默认不丢句**（6.0 → 0）；⑥ **OPEN-1（0xC0000409）** 是否继续定位（§202 ④ 三臂 rc=0）；⑦ **10 个带缺陷包**作废还是标注（**目录一律不删**）；⑧ **完整版 v2.5** 何时打（**必须带收窄**）；⑨ **目标机**开机＋凭据；⑩ **gradio 示例音频**是否下一版排除（APP-108 §5 FYI）。
> **⑫【与 APP-085 §2「待命期不新增 § 章节／不归档／不 commit」的偏离 —— 如实申报】**：本轮**确实无新纠偏**，但产出**两项此前未记录、可复算的闸门层结论**（③ 覆盖漏洞 ＋ ④ 静默丢弃口子）与**一项独立复核**（⑤）⇒ 按任务口径写入本节并按 40 000 B 限额归档 §202 ⇒ **本轮新增 § 章节 1 节（§203）／归档件 1 份／闸门脚本改动 1 个文件／提交 1 次**（普通 push、无 force、逐文件 `git add`、**未提交** `CORRECTIONS_APP.md`）⇒ 若 reviewer 认为本轮应当零写入：**单步回退即可**（`git revert <本轮 commit>`；归档件与改前逐字节备份都在磁盘上）⇒ **回退不丢任何原始交付物**（21 个客户包目录、zip 均未被本轮触碰）。
"""

RECENT = ("> \U0001f534 2026-11-14 18:28:17 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**："
          "6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 未变、agent-mail 仍 `not_bound`、"
          "`conversation_search` 0 命中、`NOTICE` 最新 11-02、git 0/0、`MACHINE_LOCK` 无）｜"
          "🔴 **修掉包矩阵闸门 `app512` 的覆盖漏洞**（`SpecialMVP` sp1/sp2 **从未进过闸门** ⇒ "
          "枚举放宽 ⇒ 复跑 **21/21**，sp1/sp2 均 **PASS 11/0**）＋ **静默丢弃无 `tts_worker.py` 的包**"
          "的口子（改 `SKIP` 行＋`coverage` 字段）｜**「10 个带缺陷包」经全盘 AST 复核数字不变**"
          "（v1.5 判据不适用、v1.13/v2.0/v2.1 无分支②）｜**未打包／未改客户包／未改产品代码**\n")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    raw = open(STATUS, 'rb').read()
    s = raw.decode('utf-8')
    # ── 备份（改前逐字节） ──
    shutil.copyfile(STATUS, BACKUP)

    # ── ① 归档 §202（write-once：已存在则**校验块 SHA**，一致才复用） ──
    m = re.search(r'(?m)^## §202 .*$', s)
    if not m:
        print('ABORT: 找不到 §202 标题行')
        return 2
    title = m.group(0)
    sec202 = s[m.start():]                      # 标题行 + 正文（§202 是最后一节 ⇒ 到 EOF）
    blk = sec202.rstrip('\n')
    blk_sha = sha256_bytes(blk.encode('utf-8'))
    if os.path.isfile(ARCH_202):
        old = open(ARCH_202, encoding='utf-8').read()
        if blk_sha not in old:
            print('ABORT: 归档件已存在但块 SHA 不一致（write-once）: %s' % ARCH_202)
            return 2
        print('归档件已存在且块 SHA 一致 ⇒ 复用（write-once 保持）')
    else:
        arch = (
            '# STATUS_APP §202 整块逐字归档（2026-11-14）\n\n'
            '归档时间：2026-11-14 18:28:17\n'
            '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §203 出空间。\n'
            '正文一字未删（标题行仍留在活文档）。\n\n'
            '§202 正文块 SHA256（含标题行）：%s（%d B）\n\n'
            '---- 以下为 §202 原文，逐字 ----\n%s\n'
            % (blk_sha, len(blk.encode('utf-8')), blk)
        )
        with open(ARCH_202, 'w', encoding='utf-8', newline='\n') as f:
            f.write(arch)
    arch_sha = sha256_bytes(open(ARCH_202, 'rb').read())

    # ── ② 活文档：§202 正文 → 1 行指针（标题行逐字保留） ──
    pointer = ('> \U0001f534 **本节正文已整块逐字归档** ⇒ '
               '`status/archive/STATUS_APP_sec202_20261114.md`（块 SHA256 `%s`）；'
               '活文档保留 §202 标题行 ＋ 1 行指针。\n' % blk_sha)
    s2 = s[:m.start()] + title + '\n' + pointer + '\n'
    assert s2.startswith(s[:m.start()]), '前置内容被改动'
    assert title in s2, '标题行丢失'

    # ── ③ 头部：更新时间（last_ack 不变） ──
    assert s2.count('更新时间: ' + OLD_TS) == 1, '更新时间行定位失败'
    s2 = s2.replace('更新时间: ' + OLD_TS, '更新时间: ' + NOW, 1)
    assert 'last_ack: APP-109' in s2, 'last_ack 被改动'

    # ── ④ 最近更新：把**两条较旧整条**逐字归档（write-once）⇒ 换 1 行指针 ──
    ru_marks = ['> \U0001f534 2026-11-14 17:17:05',
                '> \U0001f534 2026-11-13 23:59:06']
    ru_lines = []
    for mk in ru_marks:
        hit = [ln for ln in s2.split('\n') if ln.startswith(mk)]
        if len(hit) != 1:
            print('ABORT: 「最近更新」条目定位失败 %s (命中 %d)' % (mk, len(hit)))
            return 2
        ru_lines.append(hit[0])
    ru_block = '\n'.join(ru_lines)
    ru_sha = sha256_bytes(ru_block.encode('utf-8'))
    if os.path.isfile(ARCH_RU):
        if ru_sha not in open(ARCH_RU, encoding='utf-8').read():
            print('ABORT: 最近更新归档件已存在但块 SHA 不一致（write-once）')
            return 2
        print('最近更新归档件已存在且块 SHA 一致 ⇒ 复用（write-once 保持）')
    else:
        arch_ru = (
            '# STATUS_APP 「最近更新」2 条较旧条目整块逐字归档（2026-11-14）\n\n'
            '归档时间：2026-11-14 18:28:17\n'
            '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §203 出空间。\n'
            '正文一字未删。\n\n'
            '块 SHA256：%s（%d B）\n\n'
            '---- 以下为原文，逐字 ----\n%s\n'
            % (ru_sha, len(ru_block.encode('utf-8')), ru_block)
        )
        with open(ARCH_RU, 'w', encoding='utf-8', newline='\n') as f:
            f.write(arch_ru)
    ru_pointer = ('> \U0001f534 本节 2 条较旧「最近更新」条目（2026-11-14 17:17:05'
                  '「执行 APP-108／APP-109」／2026-11-13 23:59:06「巡检：无新纠偏」）'
                  '原文已**整块逐字归档** ⇒ '
                  '`status/archive/STATUS_APP_recent_updates_20261114b.md`'
                  '（%d B／块 SHA256 `%s`）。\n'
                  % (len(ru_block.encode('utf-8')), ru_sha))
    for ln in ru_lines:
        assert s2.count(ln + '\n') == 1, '最近更新条目定位不唯一'
        s2 = s2.replace(ln + '\n', '', 1)
    anchor = '## 最近更新\n'
    i = s2.index(anchor) + len(anchor)
    s2 = s2[:i] + ru_pointer + s2[i:]

    # ── ④b 最近更新：把本轮条目插到最前 ──
    i = s2.index(anchor) + len(anchor)
    s2 = s2[:i] + RECENT + s2[i:]

    # ── ⑤ 追加 §203 ──
    if not s2.endswith('\n'):
        s2 += '\n'
    s2 = s2.rstrip('\n') + '\n' + SEC203
    if not s2.endswith('\n'):
        s2 += '\n'

    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(s2)

    # ── ⑥ 写后自检 ──
    out = open(STATUS, 'rb').read()
    o = out.decode('utf-8')
    n_sec_new = len(re.findall(r'(?m)^## §\d+', o))
    n_sec_old = len(re.findall(r'(?m)^## §\d+', s))
    checks = {
        'bytes<=40000': len(out) <= 40000,
        'lines<=300': out.count(b'\n') + 1 <= 300,
        'sections_not_fewer': n_sec_new >= n_sec_old + 1,
        'sec203_present': '## §203 ' in o,
        'last_ack_unchanged': 'last_ack: APP-109' in o,
        'title_sec202_kept': title in o,
        'old_body_preserved_in_archive': blk in open(ARCH_202, encoding='utf-8').read(),
        'no_bare_lf': (out.count(b'\n') - out.count(b'\r\n')) >= 0,
    }
    # 还原式复核：把指针行换回原文 + 去掉新增的 §203 ⇒ 应与改前逐字节一致
    restored = o
    if restored.endswith(SEC203):
        restored = restored[:-len(SEC203)]
    restored = restored.replace(title + '\n' + pointer, sec202)
    restored = restored.replace('更新时间: ' + NOW, '更新时间: ' + OLD_TS)
    restored = restored.replace(RECENT, '')
    restored = restored.replace(ru_pointer, '\n'.join(ru_lines) + '\n')
    checks['restore_roundtrip_ok'] = (restored.rstrip('\n') == s.rstrip('\n'))
    checks['ru_archived_verbatim'] = (ru_block in open(ARCH_RU, encoding='utf-8').read())

    print('STATUS bytes=%d lines=%d sections=%d(旧 %d)'
          % (len(out), out.count(b'\n') + 1, n_sec_new, n_sec_old))
    print('ARCHIVE %s bytes=%d sha=%s' % (ARCH_202, os.path.getsize(ARCH_202), arch_sha))
    print('BLOCK SHA (含标题行) = %s' % blk_sha)
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print('  %-32s %s' % (k, 'PASS' if v else 'FAIL'))
    if bad:
        print('SELF-CHECK FAIL => %s' % bad)
        shutil.copyfile(BACKUP, STATUS)      # 回滚到改前
        print('已回滚到改前版本')
        return 1
    print('SELF-CHECK ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
