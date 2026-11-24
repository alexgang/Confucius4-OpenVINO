#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 写当日日志（`2026-11-25.md`）＋ automation memory（**只许追加**）。

## 🔴 纪律
- 当日日志 `.workbuddy/memory/2026-11-25.md`：**新建**（本轮跨日 01:37 起）。
- automation memory：**只许追加、禁覆盖**（gitignore ⇒ 无副本）⇒ 追加前先备份。
  ⇒ 真不变量：**写前内容逐字节是写后内容的前缀**。

## 🔴 日志只记「有持久价值的结论」，不抄 STATUS
本日志**追加**一条 §233 轮的摘要（判据坑与结论指针），
**不**把 STATUS 正文抄一遍（§227 教训：轮次状态属 STATUS 的职责）。
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DAILY = os.path.join(REPO, '.workbuddy', 'memory', '2026-11-25.md')
AUTOM = os.path.join(REPO, '.workbuddy', 'memory', 'automations',
                     'c773e368-530e-4404-9b0d-66da2193cbf6', 'memory.md')

DAILY_BODY = """# 2026-11-25 · App 巡检轮 · §233（待命轮 ＋ TAKEOVER 接续）

## 2026-11-25 01:37–02:2x · App 巡检轮 · **§233**（待命轮 ＋ TAKEOVER 接续上一会话）—— 六通道全空 ⇒ 无新 App 纠偏（`last_ack` 仍 **APP-133**）；🟢 闭合上一会话遗留的 **4 处真缺陷**；🟢 修掉「STATUS 只剩 196 B 余量」这个结构性阻塞

- **租约**：`session_lease.py acquire app` ⇒ exit 0 / **TAKEOVER**（上一 token `b1933ada`，started 11-24 23:07:24、last_beat **11-24 23:50:08**＝**108 min 前** ⇒ 死会话；note＝`verified 6 channels empty; found 4 real defects; verifying facts`；`live_pids=[]` `alive=False`）⇒ 本轮 token **`b13b16db`**，beats ×N ⇒ 收尾 `release`。
- 🔴 **上一会话未留下任何可交付物**：全仓 mtime 扫描（11-24 22:50 → 11-25 01:40）**0 个**文件；STATUS **无 §233**；automation memory **最后一条仍是 §232**；当日日志**无本轮条目** ⇒ ⇒ **必须从会话 JSONL 重建其分析链**（`bb563780-642b-4d0d-9260-b258a87aa629.jsonl`，430 条／162 次 `function_call`）⇒ 取回「4 处真缺陷」清单 ⇒ **逐条独立复核后才动手**（不直接采信上一会话结论）。
- **六通道全空 ⇒ 无新 App 纠偏**（`last_ack` **仍 APP-133**，**值不变**）：局域网 `status/app/CORRECTIONS_APP.md` **130 条／max APP-133**／SHA `2db65bf1…`／**440 181 B**／mtime **11-24 13:56:42**（与 §232 逐字一致）；QQ 收件箱最新 App 封仍 = **APP-133**（`msg_HbiVRXlg…`，05:56:40Z）＝已执行，其后仅 **H-028 [MT]**（10:11:12Z，正文明确「App 接入等本条验收后另发」⇒ **不据此动 App 代码**）；spam **0**；trash **1**（MiniMVP rc9 报告，无关）；全库 `APP-134+` 命中 **0**；根 `CORRECTIONS.md` max **C-135**；`shared/NOTICE*` 仍 ≤11-05；agent-mail **`not_bound`**。
- 🟢 **缺陷①（阻塞）**：`STATUS_APP.md` **39 804／40 000 B** ⇒ 只剩 **196 B**，下一轮写 §N（历史每轮 792–1 958 B）**必超限** ⇒ 修法＝§211–§227 **标题行＋指针行整块逐字归档**（write-once，沿用 §181–§210／§162–§169／§135–§140 成例）⇒ **24 998 B（余量 15 002 B）**；归档前逐条校验该区间 **14 个** `status/...` 指针目标**全部存在**；复核 **17/17 PASS**（含反证组）。
- 🟢 **缺陷②**：v2.6 的 `README_zh.md` 的 `## v2.6 改动说明` 出现 **2 次**（第 1 个是**空段**）、`README_en.md` 多出空的 `## What's new in v2.6` ＋ `## v2.6 changes` ⇒ 根因＝**`sync_c172` 插入时自己写一个标题**，而人撰写正文（`_app129_changelog_2.6_{zh,en}.md`）**首行就是同一个标题** ⇒ 两个标题叠加 ⇒ 修法＝开发树 `sync_c172` 插入前**剥离**正文自带的同版本标题（**窄口径**：只剥首行／恰好 `## `／含本版本号；`###` 小节绝不剥；**幂等**）⇒ 复核 **16/16** ＋ **影子包端到端 23/23**（真包 4 文件跑前跑后 SHA256 一致 ⇒ 隔离有效）。
- 🟢 **缺陷③**：v2.6 的 `app/MANIFEST.json` 写着 `version=2.5`，且与 v2.5 的**逐字节相同**（md5 `239ea82a…`）⇒ 根因＝该字段**只有** `pack_v13.refresh_manifest()` 会写（挂在**打包阶段**），而**完整版线（v2.x）从来不出 zip** ⇒ 打包阶段**永不执行** ⇒ 该字段永不被刷新；**附带**：`app170` 的 I1b 提醒原写「**zip 级断言兜底**」，但完整版线**没有 zip** ⇒ **那个兜底不存在** ⇒ 提醒措辞已改为真实修法 ⇒ 修法＝开发树 `sync_c172` 新增 `sync_manifest_version()`（**只改 `version` 一个字段**；`files`/`bytes` 仍归打包净载荷口径；写盘格式与 `refresh_manifest()` 一致 ⇒ **JSON 往返逐字节稳定**；**幂等**）⇒ 复核 **19/19**（含反证组）。
- 🟢 **缺陷④**：入库的 `app170` 证据与实包对不上（证据 README_zh `6f8b933e…`／55 968 B、实包 `0bb23e7c…`／**57 986 B**；`D4 count` 0 vs 实包 2）⇒ 重跑闸门刷新入库证据 ⇒ 与实包**逐字节一致**；两条提醒**如实保留，不掩盖**。
- 🔴 **如实登记（未修／不擅自修）**：① v2.6 包两处缺陷（②③）修法已落**开发树**，但按 **APP-055** **未原地改已签 ACCEPTED 的包** ⇒ **是否出 v2.7 待 reviewer/用户裁定**；② `results/app/app231_pack_lock_events.jsonl` **不存在且未入库**（被 4 处当审计指针）—— 它是修好后的**生产路径**在**运行时**产出的文件，v2.6 那次构建跑在修复提交（eb82d17，11-24 20:28）**之前** ⇒ 尚未产出 ⇒ 🔴 **不伪造空文件**（那是制造证据）；§231「lock_lost 0 条」结论**不受影响**（其证据 `app132_lock_events.jsonl` **已入库**）；③ `Confucius4_LiveCaption_v2.6.staging` 残留 **25 GB** ⇒ 删除属**破坏性**操作 ⇒ **未删**，待授权。
- 🟢 **STATUS §233**（正文全文 ⇒ `status/app/STATUS_APP_sec233_detail_20261125.md`，**18 723 B**）：**28 159 B／82 行**（限额 40 000 B／300 行）｜头 `last_ack` **未变**、「更新时间」用 **Get-Date 实测值**（`2026-11-25 02:04:46`）｜「最近更新」块首插入新条目（旧条目**下移未删**）｜**两处表行按既有成例（`1e3201c`）就地更新**为 v2.6（客户包目录／完整版 v2.6／客户包 zip），旧行文本**已不存在**（不留新旧并存）｜§233 **只追加在文末** ⇒ 独立复核 **30/30 PASS**（含反证组）。
- 🟢 **邮件（T-MAIL-003 必须发）**：`msg_20-nHCSHXAk9kUm3XTwenP4ahiiluV1WvXRsRdj_8VqDzQ`（**2026-11-24T18:06:48Z**＝11-25 02:06:48 GMT+8，回复 APP-133 原邮件），正文 **4 044 B／2 253 字符**；两步 token（`ctk_7e6b8005…` ⇒ **原样**带 token 重发 ⇒ `queued:true`）⇒ 正文由 `_app233_email_body.py` 生成 ⇒ 入库件与实发**同源**；**首/中/尾三地标**经**服务端** `SearchMessages(SEARCH_IN_CONTENT)` 逐个检索**全部命中同一 message_id** ⇒ **未截断**（§224 的 11 KB 中段丢失模式不成立）。
- 🔴 **本轮踩到并修掉的判据坑（已下沉 `MEMORY_MODULES.md` 附录·五十二）**：① **「章节号集合不变」是错判据**（归档标题行**本来就要**把那些 §N 移走 ⇒ **必假 FAIL**）⇒ 正确判据＝「**没有丢**」`old ⊆ (live ∪ archived)`；② **指针行行尾 off-by-one**（自带 `\n` 再补 `eol` ⇒ `\n\n` ⇒ **多 1 字节**＋孤立 LF）⇒ 由**还原式复核**如实抓出（39 805 vs 39 804 B）⇒ 修法＝按区域既有行尾**只写一个**终止符（且 `is_crlf_block` **不能**用 `crlf == lf_total` 判）；③ **测试脚本自己造假的 FAIL**（`str.find(正则串)` 是**字面**匹配 ⇒ −1 ⇒ **把文件截断**）⇒ 一律用 `re.search`；④ **核对「实发件 == 入库件」会循环论证**（拿入库件反推 HTML 再跟它自己比 ⇒ **永远 PASS**）⇒ 改用**服务端内容检索**取证；⑤ **反证组要模拟真实失败模式**（改 1 字节**不改变长度** ⇒ 拿「长度差」当反证目标是**恒 PASS 的错判据**）⇒ 应**挖中段**（§224 的真实失败模式）。
- **纪律**：🟢 **未打包 zip**（用户级纪律「**不通知 ⇒ 不打包**」）｜🟢 **未覆盖/未删除**任何旧版本目录与 zip｜🟢 **未改任何客户包**（v2.6 4 个文件跑前跑后 SHA256 一致）｜🟢 **未跑推理·计时**（**未取 MACHINE_LOCK**）｜🟢 **未调 MiniMax**｜🟢 **未连 B 机**｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ **SHA 零改动**）｜🟢 **只 add App 侧文件**｜🟢 **普通 push，无 force push**｜🟢 **未进 v2.6 包**（只读复核）。
- **提交**：`3670d1a`（代码修复）＋ `910e726`（§233）＋ `2d9e982`（邮件正文入库）**已推 `origin/main`**（`git rev-list --left-right --count origin/main...main` = **0 0**）。
- **下一轮**：`last_ack` 仍 **APP-133**；⏭ 等 reviewer 复核 **§233**；🔴 **待裁定**：**是否出 v2.7**（带 README 双标题 ＋ MANIFEST.version 两处修复）／**是否删** `.staging`（**25 GB**）／`app231_pack_lock_events.jsonl` 等下轮成包路径产出后**入库**／**v2.5 重签 ACCEPTED**／仓库根 `.gitattributes` 根治（854 个 `i/lf+w/crlf`）／默认分离设备／`n_speakers=0` 口径。
"""

AUTOM_BODY = """
## 2026-11-25 01:37–02:2x · App 巡检轮 · **§233**（待命轮 ＋ TAKEOVER 接续）—— 六通道全空 ⇒ 无新 App 纠偏（`last_ack` 仍 **APP-133**）；🟢 闭合上一会话遗留的 **4 处真缺陷**

- **租约**：`acquire app` ⇒ exit 0 / **TAKEOVER**（上一 token `b1933ada`，started 11-24 23:07:24、last_beat **11-24 23:50:08**＝**108 min 前** ⇒ 死会话；note＝`verified 6 channels empty; found 4 real defects; verifying facts`；`live_pids=[]` `alive=False`）⇒ 本轮 token **`b13b16db`**，beats ×N ⇒ 收尾 `release`。
- 🔴 **上一会话未留任何可交付物**（全仓 mtime 扫描 0 个文件／STATUS 无 §233／automation memory 末条仍 §232／当日日志无本轮条目）⇒ **从会话 JSONL**（`bb563780-…jsonl`，430 条／162 次 `function_call`）**重建其分析链**取回「4 处真缺陷」⇒ **逐条独立复核后才动手**（不直接采信）。
- **六通道全空**（`last_ack` **仍 APP-133**，**值不变**）：局域网 **130 条／max APP-133**／SHA `2db65bf1…`／**440 181 B**／mtime **11-24 13:56:42**（与 §232 逐字一致）；QQ 收件箱最新 App 封仍 = **APP-133**（已执行），其后仅 **H-028 [MT]**（明确「App 接入另发」⇒ **不据此动 App 代码**）；spam 0；trash 1（无关）；全库 `APP-134+` 命中 0；根 max **C-135**；NOTICE ≤11-05；agent-mail `not_bound`。
- 🟢 **4 处真缺陷（逐条独立复核后修）**：① **STATUS 只剩 196 B 余量**（39 804／40 000 B ⇒ 下轮写 §N 必超限）⇒ §211–§227 标题行＋指针行**整块逐字归档**（write-once，成例同 §181–§210）⇒ **24 998 B（余量 15 002 B）**，**17/17 PASS**；② **v2.6 README 双标题**（根因＝`sync_c172` 自写标题 ＋ 人撰写正文首行同名 ⇒ 标题叠加）⇒ 开发树 `sync_c172` 插入前剥离（窄口径／幂等），**16/16 ＋ 影子包 e2e 23/23 PASS**（真包逐字节未动）；③ **v2.6 `app/MANIFEST.json` `version=2.5`**（与 v2.5 逐字节相同 ⇒ robocopy 原件从未刷新；根因＝`pack_v13.refresh_manifest()` 只在**打包阶段**，而**完整版线从不出 zip** ⇒ 永不执行）⇒ 开发树 `sync_c172` 新增 `sync_manifest_version()`（只改 `version`；幂等）＋ app170 的 I1b 提醒措辞改为**真实修法**（原「zip 级断言兜底」在完整版线**不存在**），**19/19 PASS**；④ **入库 app170 证据与实包不符**（README sha/字节、`D4 count` 0 vs 2）⇒ 重跑闸门刷新 ⇒ 与实包逐字节一致。
- 🔴 **如实登记（未修／不擅自修）**：v2.6 包两处缺陷修法**已落开发树**但按 **APP-055 未原地改已签包** ⇒ **是否出 v2.7 待裁定**；`results/app/app231_pack_lock_events.jsonl` **不存在且未入库**（4 处当审计指针）⇒ 它是**运行时**产物（v2.6 构建跑在修复提交之前）⇒ **不伪造空文件**，§231 结论不受影响（其证据 `app132_lock_events.jsonl` 已入库）；`Confucius4_LiveCaption_v2.6.staging` 残留 **25 GB** ⇒ **未删**（破坏性⇒待授权）。
- 🟢 **STATUS §233**（⇒ `status/app/STATUS_APP_sec233_detail_20261125.md`，**18 723 B**）：**28 159 B／82 行**｜`last_ack` **未变**｜「更新时间」**Get-Date 实测值**（`2026-11-25 02:04:46`）｜「最近更新」**+1 条**（旧条**下移未删**）｜**两处表行按成例 `1e3201c` 就地更新为 v2.6**（旧行文本已不存在，不留新旧并存）｜§233 **只追加在文末** ⇒ 独立复核 **30/30 PASS**（含反证组）。
- 🟢 **邮件（T-MAIL-003 必须发）**：`msg_20-nHCSHXAk9kUm3XTwenP4ahiiluV1WvXRsRdj_8VqDzQ`（2026-11-24T18:06:48Z＝11-25 02:06:48 GMT+8，回复 APP-133 原邮件），正文 **4 044 B／2 253 字符**；两步 token（`ctk_7e6b8005…` ⇒ 原样重发 ⇒ `queued:true`）；正文**由脚本生成** ⇒ 入库件与实发**同源**；**首/中/尾三地标**经**服务端** `SearchMessages(SEARCH_IN_CONTENT)` **全部命中同一 message_id** ⇒ **未截断**。
- 🔴 **本轮新学的 5 个判据坑（已下沉 `MEMORY_MODULES.md` 附录·五十二）**：① **「章节号集合不变」是错判据**（归档标题行本就要移走 ⇒ **必假 FAIL**）⇒ 真不变量＝「**没有丢**」`old ⊆ (live ∪ archived)`；② **指针行行尾 off-by-one**（自带 `\n` 再补 ⇒ **多 1 字节**＋孤立 LF）⇒ 由**还原式复核**抓出 ⇒ **只写一个**终止符（`is_crlf_block` **不能**用 `crlf == lf_total` 判）；③ **测试脚本自己造假的 FAIL**（`str.find(正则串)` 是**字面**匹配 ⇒ 截断文件）⇒ 一律 `re.search`；④ **核对「实发件 == 入库件」会循环论证** ⇒ 改用**服务端内容检索**取证；⑤ **反证组要模拟真实失败模式**（改 1 字节不改变长度 ⇒ 长度判据**恒 PASS**）⇒ 应**挖中段**。
- **纪律**：🟢 **未打包 zip**（用户级「不通知 ⇒ 不打包」）｜🟢 未覆盖/未删除旧目录与 zip｜🟢 **未改任何客户包**｜🟢 未跑推理·计时（**未取 MACHINE_LOCK**）｜🟢 未调 MiniMax｜🟢 未连 B 机｜🟢 **未改 `CORRECTIONS_APP.md`**（四项指纹逐字一致 ⇒ **SHA 零改动**）｜🟢 只 add App 侧文件｜🟢 普通 push 未 force。
- **提交**：`3670d1a` ＋ `910e726` ＋ `2d9e982` **已推 `origin/main`**（**0 0**）。
- **下一轮**：`last_ack` 仍 **APP-133**；⏭ 等 reviewer 复核 **§233**；🔴 **待裁定**：**是否出 v2.7**／**是否删 `.staging`（25 GB）**／`app231_pack_lock_events.jsonl` 下轮入库／**v2.5 重签 ACCEPTED**／仓库根 `.gitattributes` 根治／默认分离设备／`n_speakers=0` 口径。
"""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    # ── ① 当日日志（新建）────────────────────────────────────────
    print('[1] 当日日志 2026-11-25.md（新建）')
    if os.path.exists(DAILY):
        print('  [SKIP] 已存在 ⇒ 不覆盖（只许追加）')
    else:
        tmp = DAILY + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(DAILY_BODY.encode('utf-8'))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DAILY)
        b = open(DAILY, 'rb').read()
        print('  [PASS] 写入 %d B；SHA256 %s'
              % (len(b), sha256_bytes(b)[:16]))

    # ── ② automation memory（只许追加）────────────────────────────
    print('\n[2] automation memory（只许追加、禁覆盖）')
    before = open(AUTOM, 'rb').read()
    btext = before.decode('utf-8')
    if '§233' in btext and '附录·五十二' in btext:
        print('  [SKIP] 本轮条目已存在 ⇒ 不重复追加')
    else:
        new = (btext.rstrip('\n') + '\n' + AUTOM_BODY).encode('utf-8')
        assert new[:len(before)] == before, 'append-only 前缀不成立'
        bak = os.path.join(tempfile.gettempdir(), 'autom_memory.bak_app233')
        shutil.copy2(AUTOM, bak)
        print('  [backup] %s' % bak)
        tmp = AUTOM + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, AUTOM)
        print('  [PASS] 追加 %d B（%d → %d B）'
              % (len(new) - len(before), len(before), len(new)))
        print('  SHA256 %s' % sha256_bytes(new)[:16])
    return 0


if __name__ == '__main__':
    sys.exit(main())
