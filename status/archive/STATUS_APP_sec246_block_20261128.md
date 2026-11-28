# STATUS_APP §246 正文归档（write-once）

> 本文件是 `status/app/STATUS_APP.md` 中 **§246 一节的正文 4 行**的**逐字归档**（**原文一字未删、未改**；标题行仍留在活文档）。
> 归档时间：2026-11-28（§251 轮，STATUS 触顶处置：≤40 000 B 限额）。

---

## §246 **LOCK-001**（机器锁死锁修复）APP 侧安装完成｜`last_ack` **APP-151**（＋LOCK-001，不占模块编号）
> 🟢 **安装**：附件（**8 831 B**）经直连 API 由脚本落盘（无人工转写）⇒ `C:\Users\Trekker-PTL\shared\tools\machine_lock.py`（sha256 `c8eb39be7438043d99fed086b49d2e70ef07af8945680a72969f99ca2b500571`，`ast.parse` 通过）；`shared\README_LOCK.md` 顶部加 LOCK-001 段、旧机制保留备查（339→1 341 B，CRLF 0）。
> 🟢 **行为验证 5/5**（**包内 python** 跑，证据由脚本产出 ⇒ `results/app/app245_lock001_install.json`）：① `status`=**FREE** ② 单作业 `[machine_lock] acquired` + `released (rc=0)` ③ 持锁期 `status`=**HELD (live job)** ④ 第二作业 `waiting; holder…` 后 `acquired`（等 **15.6 s**）⑤ **整树被杀 ⇒ 系统锁自动放**，`status` 判 **STALE text lock (no live job)**（不再永久死锁）⇒ `reclaim` 归档 ⇒ **FREE**。
> 🔴 **未做（如实登记）**：既有取锁代码（`machine_lock_app.py` 的 `write_lock_atomic`、三轮编排脚本的 CreateNew/finally 删锁）**尚未改成套 `machine_lock.py run`** ⇒ 下一次计时作业起法改为 `run --module app --note … -- <命令>`，并在日志核对 `acquired`／`released (rc=…)` 两行（LOCK-001 验收第 2 条）。
> 🟢 **STATUS 邮件（T-MAIL-003 必须发）已发并已发箱回读核对**：① 状态报告 **4 918 B**（无附件）`msg_0WHS7mI7rDcDNMzVoh300SxFEVirHhdK5bNJe-mx14dbZw` ② 抽听样片 **1 406 B**＋**3 个 OGG 附件**（117 114/120 347/122 633 B，sha1 由发送脚本从磁盘现算）`msg_v6USGFcIM_QnAict57C6mUoGqbNRX3hJvwEfthNPDAWjoQ`；两封**首/中/尾三地标全部命中、无截断**，附件 3/3 与源字节一致。
