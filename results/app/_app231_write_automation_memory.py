#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-231：把本轮结论**追加**到本自动化的记忆文件。

## 🔴 纪律
- `.workbuddy/memory/automations/*/memory.md` **只许追加、禁覆盖**。
- 🔴 **本脚本用 Write 落盘再执行**（不用 bash heredoc）—— 本轮实测：heredoc 里
  的反引号被 **shell 当成命令替换** ⇒ `` `session_lease.py acquire app` `` 被执行
  ⇒ 正文**缺字**（"**租约**： ⇒ exit 0"）⇒ **必须**走「文件 ⇒ 执行」路径。
- 🔴 幂等守卫：标题已存在 ⇒ **零改动**。
"""
from __future__ import annotations

import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
P = os.path.join(REPO, '.workbuddy', 'memory', 'automations',
                 'c773e368-530e-4404-9b0d-66da2193cbf6', 'memory.md')
TITLE = '## 2026-11-24 19:5x–20:3x · App 巡检轮（接续上一会话 TAKEOVER）'

ENTRY = r"""
## 2026-11-24 19:5x–20:3x · App 巡检轮（接续上一会话 TAKEOVER）—— 六通道复核无新 App 纠偏（last_ack 仍 APP-133）；🟢 闭合上一会话遗留的「记忆写入未落盘」；🟢 补上 APP-132 的**生产路径补漏**

- **租约**：`session_lease.py acquire app` ⇒ exit 0 / **TAKEOVER**（上一会话 token `47796b43`，17:06:53 起、last_beat 18:34:37＝**78 min 前** ⇒ 死会话；note＝「已提交 19d9369 并推送（origin/main 0/0）；邮件 2 封已发（含 3 个 OGG）；**写记忆文件**」；live_pids=[] alive=False）⇒ 本轮 token **`377715be`**，beats ×N ⇒ 收尾 `release`。
- **纠偏（六通道全空 ⇒ 无新 App 纠偏）**：局域网 `status/app/CORRECTIONS_APP.md` **130 条／max APP-133**／SHA `2db65bf1…`／**440 181 B**／mtime **2026-11-24 13:56:42**；QQ 收件箱最新 App 封仍 = **APP-133**（`msg_HbiVRXlg…`，05:56:40Z）；spam **0**；trash **1**（无关旧件）；根 `status/CORRECTIONS.md` max **C-135**（已冻结）；`shared/NOTICE*` 仍 ≤11-05；agent-mail `not_bound`。收件箱整体最新 = **H-028 [MT]**（10:11:12Z）＝ MT 模块，正文明确「App 接入等本条验收后另发 APP 纠偏」⇒ **不据此动 App 代码**。⇒ **`last_ack` 仍 APP-133**（本地 max ＝ QQ max ＝ last_ack）。
- **🟢 本轮主发现：APP-132 的修法只落在侧写 harness，成包路径原封不动**：上一轮 §230 的修法在 `results/app/_app132_lock.py`（专供 v2.6 整链三臂跑）⇒ **那一轮的验收目标确实达成**（整链一次持锁到底，`lock_lost` 0 条）；但**真正成包的路径** `live_caption/_app116_build_v25.py`（⇒ `_app129_build_v26.py` 第 216 行 `B.acquire_lock`）**仍是旧代码**：① `os.replace(tmp, LOCK)` **非原子**（两进程可同时拿到＋会覆盖别人的锁）；② 看门狗 `own is None or own.get('pid') == os.getpid()` ⇒ **被抢即放弃写回**且写回又用 `os.replace` ⇒ **链继续跑但不再持锁且无人知晓**＋静默覆盖别人的锁。
  ⇒ **通用判据：「修了 harness」≠「修了产品」**（交付路径与验收路径是**两条路** ⇒ 修锁/修闸门前必须问「**生产上真正跑的是哪个文件**」）。
- **🟢 已修**（**只改这一个文件**：10 820 B → 15 749 B，`ast.parse` OK，纯 LF）：新增 `_create_lock_exclusive()`（**tmp 写全 + `os.link`** ⇒ 原子 + 独占 + 不露半成品锁，同仓库根 `machine_lock_app._write_lock_atomically` 的正解）；`acquire_lock()` 把「探测⇒创建」**合并进同一 while 循环**（消除 TOCTOU 窗口）；看门狗改为**只自检不盲写**（锁被删⇒原子+独占地补建；被抢⇒记 `lock_lost`）；新增 `results/app/app231_pack_lock_events.jsonl`。
- **🟢 独立行为级复核 9/9 PASS**（`results/app/_app231_verify_lock.py`；**纯 CPU 逻辑测试**，不跑推理·不测速，**用临时目录做锁 ⇒ 不碰真 `shared\MACHINE_LOCK`**）：判据①**确定性**（6 进程经**文件栅栏**同瞬间并发建锁 ⇒ **恰好 1 个**成功）；🔴**反证组**（同测试跑在旧 `os.replace` 实现上 ⇒ **2 个**成功 ⇒ 缺陷可复现 ⇒ **判据能识破有缺陷的旧代码**，非假 PASS）；判据②**端到端重叠**（两进程走完 `acquire_lock`，持锁期间轮询锁内容 ⇒ **无两把锁并存**）；＋别人先建锁⇒创建失败且不覆盖；＋看门狗⇒记 `lock_lost` 且不覆盖；＋放锁只删自己的。
- **🟢 上一会话遗留项已闭合**：它的 `results/app/_app133_write_memory.py` **从未运行** ⇒ 当日日志无「第 126 轮」、`MEMORY.md` 无机器锁指针且 §十二 仍写**过期的 `last_ack=APP-128`**、`MEMORY_MODULES.md` 无本轮细节；且那个脚本**还漏了 `MEMORY.md` 的 9 700 字符上限断言**。⇒ 本轮补写并**补上该断言**（`MEMORY.md` **9 700 → 9 655 字符**，仍 ≤ 上限；压缩 §十二 三条**已过期**状态行以腾字数，差异行**都在 §十二 内**且判据关键词未丢）⇒ 独立复核 **19/19 PASS**。
- **🔴 本轮新学的三个判据坑**（已下沉 `MEMORY_MODULES.md` 五十）：① **「两个进程都拿到锁」≠「两把锁并存」** —— A 可能**先放锁再轮到 B** ⇒ 那是**合法串行** ⇒ 判据必须测「**持锁期间锁内容被别人改写**」这个**重叠**现象，**不能数进程数**（本轮初版判据就错在这儿）。② **判据写文本计数 ⇒ 必假 FAIL**（`os.replace(tmp, LOCK)` 这个串在**新 docstring 里本来就要出现**）⇒ **改用 AST 判定**「代码里不得有 `os.replace` 调用」⇒ **判据要绑语义、不绑字面**。③ **锚点是行前缀时 ⇒ 取行尾必须「向后扫到第一个换行」**（直接看锚点后面紧跟什么 ⇒ 拿到的是**行内字符** ⇒ 返回空串 ⇒ **两行被拼成一行**）＋ **`Get-Date` 只能取一次**（写后复核再取一次 ⇒ 跨秒 ⇒ 还原式复核**必然假 FAIL**）。
- **🟢 STATUS §231**（正文全文 ⇒ `status/app/STATUS_APP_sec231_detail_20261124.md`）：**38 082 B／114 行**（限额 40 000 B／300 行）｜头 `更新时间` 换成 **`Get-Date` 实测值**（`2026-11-24 20:27:19`）｜**`last_ack` 仍 APP-133**（值不变）｜**最近更新**块首插入新条目（旧条目**下移未删**）｜§231 **只追加在文末**（§227 及更早**逐行逐字节未变**）｜🔴 **本文件是「混合行尾」**（头部与 §228–§230 用 LF、更早各节用 CRLF；写前实测 13 处孤立 LF ⇒ **不可断言「全文无孤立 LF」**）⇒ 新增行**按所在区域既有行尾**写入 ⇒ 独立复核 **15/15 PASS**。
- **邮件（T-MAIL-003 必须发）**：`msg_bzP_8MzmDWNRG03ehaUmNteSKPKcpjkLtgM6Lpm83WVaVg`（2026-11-24T12:29:01Z，回复 APP-133 原邮件），正文 **5 258 B**／控制字符 0／附件 0；两步 token（`ctk_b1c94449…` ⇒ 原样带 token 重发 ⇒ `queued:true`）⇒ **明文 token 已覆写并删除**；**首/中/尾三地标在已发箱全部命中 ⇒ 未截断**；正文由脚本生成 ⇒ **入库件与实发逐字节相同**（`live_caption/_app231_email_body.txt` 已入库）。
- **提交**：`eb82d17`（12 个文件，**只 App 侧**）＋ `48cd061`（邮件正文入库）⇒ **推送 `origin/main` 成功（0/0）**。
- **纪律**：🟢 **未打包 zip**（用户级纪律「不通知 ⇒ 不打包」）｜🟢 **未覆盖/未删除任何旧版本目录与 zip**｜🟢 **未通知用户**｜🟢 **未连 B 机**｜🟢 **未调 MiniMax**｜🟢 **未跑推理·未测速**（纯逻辑测试，不占机器锁）｜🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ SHA 零改动）｜🟢 **未进 MiniMVP 包**｜🟢 **未吞他模块改动**（全仓脏 945 是别的模块的）。
- **下一轮**：last_ack 仍 **APP-133**；⏭ 等 reviewer 复核 **§230**（APP-131/132/133）与**§231**（本轮补漏）；🔴 **待裁定**：仓库根 `.gitattributes` 根治（跨模块）／默认分离设备／`n_speakers=0` 口径／**v2.6 交接与是否出 zip**／**v2.5 重签 ACCEPTED**。
"""


def main():
    with open(P, 'r', encoding='utf-8', newline='') as f:
        old = f.read()
    # 🔴 **幂等守卫要认「本段正文完整性」，不只认标题**（本轮实测：标题在、但正文被
    #   shell 破坏（反引号被当命令替换 ⇒ 缺字）⇒ 只判标题会**误报「已存在」**
    #   ⇒ 坏段永远修不掉）。⇒ 判据 = **只看本段**（标题 → 文件尾）里的关键片段。
    i = old.find(TITLE)
    seg = old[i:] if i >= 0 else ''
    intact = bool(seg) and ('session_lease.py acquire app' in seg
                           and '待裁定' in seg
                           and '反证组' in seg)
    if intact:
        print('ALREADY PRESENT（且**本段**正文完整）=> 零改动')
        return 0
    if i > 0:
        old = old[:i].rstrip('\n') + '\n'
        print('已截掉损坏/旧的同名段（offset %d）' % i)
    new = old.rstrip('\n') + '\n' + ENTRY
    tmp = P + '.tmp_app231'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, P)
    print('OK  %s' % P)
    print('  %d → %d 字符' % (len(old), len(new)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
