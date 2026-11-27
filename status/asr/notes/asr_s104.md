# ASR §104 明细（2026-11-27 11:20–15:05，跨两会话）

> 本轮为 **TAKEOVER 断点续做**。上一会话 token `7c01780b`，start 11-27 11:20:50，
> last_beat 11:39:24（note「LOCK-001/002 锁代码改造完成，验收 29/29 PASS」、`live_pids` 空 ⇒ 已死）。
> 本会话 token `4012e303`，acquire 时打印 TAKEOVER ⇒ 按 ASR-039 先读上一会话的 note/STATUS/产物，
> **从断点继续，未从头重做**：上一会话已完成纠偏登记、锁代码改造、§102 归档（sec103），
> 但 §104 写入器（_asr104_write_status.py）有三个 bug（LF/CRLF 混用致 split 越界、old_ptr 空格不匹配、
> SEC104 126 行超 160 行门禁）⇒ 从未落盘 ⇒ 本会话用 _asr104_write_status_v2.py 补齐，并独立复核全部数字。

## §104.0 两条通道均无新 ASR 编号条目 ⇒ `last_ack` 保持 ASR-068

### 纠偏通道

- `status/asr/CORRECTIONS_ASR.md`：**119 150 B** / md5 **`cae93591a741d852a11c66259b69a778`** / mtime **2026-11-27 11:40:25**
  ⇒ 较 §102 时的 109 822 B 变大，**增量来自上一会话追加的跨模块编号 LOCK-001／LOCK-002**。
- `^## ASR-` 标题最大编号 = **ASR-068**（11-23）；搜 `ASR-069` **0 命中**。
- **LOCK-001／LOCK-002 不占 ASR 编号、不改 `last_ack`**（与 T-MAIL-002／003 同规则）⇒ `last_ack` 保持 **ASR-068**。

### 邮件通道（QQ 邮箱 `1985197690@qq.com`）

- 收件箱 after 2026-11-26T00:00:00Z 共 **4 封，全部非 ASR 编号**：
  - **LOCK-002** [HIGH]（11-26 14:48:03Z，`msg_JC9_njlVEGhbz0AnA5nfya7WYvcIcQA6hmmZuC4WqOepkA`）
  - **APP-152** [HIGH]（11-26 13:53:18Z，`msg_67grwLF4dA6D7xH5X5A5EcI_EGfsk-1iDBulbV8flviPDw`）
  - **R-029 / T-009**（B 机，11-26 12:08:33Z，`msg_AstUNYq2K6IJexeYe8V4LAfUuVAySVK0cnPRaRJvPIJMpg`）
  - **LOCK-001** [HIGH]（11-26 11:59:50Z，`msg_djwiubxX0MiOhxxIbtTN_j3QLwG7NZ4UQsnPA96DMypnuQ`）
- 主题含 `[CORRECTION][ASR]` 的最大编号仍 = **ASR-068**（11-23 08:55:15Z，`msg_tHwjDsv…`）。
- ⇒ **无 reviewer 新 ASR 邮件** ⇒ 不进本模块 `last_ack`。

## §104.1 🟢🟢 EXT v0.4.23 修掉 §102.1 根因 ⇒ `e2e_app149` 七臂 ASR 全部跑通

### EXT 版本

- 本会话复核 `C:\Users\Trekker-PTL\live_dub_ext` git log：
  - HEAD = **`e092343`**（**2026-11-27 12:09:48**，v0.4.24，APP-154 §1「runaway judged by generated audio length, not wall clock」）
  - 前一 = **`c955411`**（2026-11-26 17:24:52，v0.4.23，「ASR works with Qwen3-ASR 0.6B packages」）
  - 再前 = `e901cad`（v0.4.22）
- 🟢 §104 的核心结论基于 **v0.4.23**（修 06B 错配）；v0.4.24 只改 runaway 判定、**不改 ASR 加载** ⇒ 结论仍成立。
- `ext/bridge/engine_runtime.py` 新增 `_asr_family()`（按包内实际模型族自动选：两族都在 ⇒ R2T2；只有 06B ⇒ 06B；
  `EXT_ASR_FAMILY=06b|r2t2` 可强制）＋ 06B 的 encoder/decoder/tokenizer/embed 目录常量与加载分支。

### 七臂逐臂复算（`shared/bgkeep/e2e_app149/`，本会话独立复核）

| 臂 | json mtime | 时长 | `asr_segments` | `n_submitted` | **`n_error`** | `spk_reason_hist` | `n_gender_splits` | `bg_clone_from_vocals` |
|---|---|---|---|---|---|---|---|---|
| `smoke/smoke_1` | 18:35:35 | 60 s | **13** | 13 | **0** | {none:13} | 0 | 0 |
| `three_arms/bgkeep_off` | 18:51:27 | 600 s | **123** | 123 | **0** | {none:123} | 0 | 0 |
| `three_arms/bgkeep_on` | 19:03:08 | 600 s | **95** | 121 | **0** | {none:95} | 0 | 0 |
| `three_arms/bgkeep_on_clone` | 19:14:22 | 600 s | **120** | 168 | **0** | {none:4, label:117} | 4 | **167** |
| `three_arms_r245/bgkeep_off` | 19:53:11 | 600 s | **123** | 123 | **0** | {none:123} | 0 | 0 |
| `three_arms_r245/bgkeep_on` | 20:05:39 | 600 s | **123** | 123 | **0** | {none:123} | 0 | 0 |
| `three_arms_r245/bgkeep_on_clone` | 20:19:08 | 600 s | **168** | 170 | **0** | {none:5, label:165} | 4 | **169** |

- 🟢 **`bridge.log` 侧交叉验证**：七臂加载行逐字相同
  「`(1/3) 正在加载 ASR（Qwen3-ASR 0.6B INT8） @ GPU.0 ……`」；
  段行 `n_with_asr_text` == `n_seg_lines`（13/123/96/121/123/123/170）⇒ 每段都有转写；`fail_hits` 全空。
- 🔴 **撤回 §102.1「ASR 100% 加载失败（123/123 段全错）」与 §103.2「11/11 臂 100% 段失败」在 v0.4.23 上的适用性**：
  §102/§103 引用的臂全部早于 17:24:52（最后一臂 17:09:45）⇒ 是 v0.4.22 及更早的产物。
- 🟡 **ASR 侧 RTF（本模块只记录，不对外）**：`bridge.log` 累计 `耗时 asr=` ÷ 语音总时长 ⇒
  **0.5433（60 s 冒烟）/ 0.4377/0.6236/0.6425/0.4888/0.5865/0.6323**（六臂 600 s）。
  🔴 这是 **App 链路的端到端 ASR 段耗时**，与 §83/ASR-060~061
  （NPU 流式 0.3094/0.2912/0.3165、离线 0.0496/0.0448/0.0665）**非同一计分器** ⇒ 不给对外、不与 §83 混用。
- 🟢 **`clone_reasons` 已进 `stats_full`**（§99「只写日志、不进 stats_full」在 v0.4.23 已闭）：
  `three_clone` 11 键 = provisional 159/guard_keep 72/guard_short 48/label 61/timeout 6/guard_no_emb 1/
  tts_nearest 1/self_ref 1/self_ref_unvoiced 2/fallback 2/gender_keep 2；
  `r245_clone` 11 键（guard_keep 104/provisional 164/guard_short 64/label 61/其余同上）。
  🔴 APP-131 要的 `tts_nearest_voice`/`gender_switch`/`gender_selfref` 三字段仍缺两个 ⇒ §101 挂项未闭。
- 🔴 **§101.3 归因缺口仍在**：v0.4.24 的 `ext/speaker_bypass.py` L429（失败分支只 `n_no_label += 1`、不写行）
  与 `_spk_reason_hist()` 逐字未改七臂 `spk_bypass.enabled` 全 `false`（只有 enabled/note/spk_queue_drop/spk_worker_busy_ms 四键）
  ⇒ 对 §101.3 不构成新证据。
- 🔴 **配音迟到（只记录不归因）**：七臂 `dub_late_vs_play_s.max`=13.99/54.53/108.34/159.12/160.76/224.81/**337.90 s**
  （`n_late`=3/60/89/118/101/115/166）⇒ App/TTS 排队时延口径；
  🟡 本模块有效数字仍以 §101 的 r2 臂 max **182.62 s** 为准。

## §104.2 🔴 README「四种 ASR 后端」表已随最终 zip 发出

- 🔴 `Confucius4_LiveCaption_MiniMVP_v1.2/README_zh.md`（**31 676 B** / mtime 11-26 22:30）仍保留：
  - **L141** 标题「## 四种 ASR 后端」；
  - **L154–157** RTF 表：Intel GPU·INT8 **0.70**／GPU·INT4 **0.73**／NPU·INT8 **0.86**／NPU·INT4 **0.75**；
  - **L159**「61 分钟英文会议录音整体 RTF 0.77」；
  - **L314** `--engine` 可选值仍写 `gpu_int8`/`gpu_int4`/`npu_int8`/`npu_int4`。
- 🔴 **包内实际只有 06B 两档**（`app/live_caption_app.py` L914–923 `ENGINES_ASR06B`：只 `gpu_int8`/`npu_int8`）；
  `models/` 实测无 `*int4*`、无 `encoder-int8`。
- 🟢 **代码侧安全**：`active_asr_engines()`（L1044–1071）按 `_asr06b_models_present()`/`_r2t2_models_present()`
  实测判定 ⇒ MiniMVP 只带 06B ⇒ 返回 `ENGINES_ASR06B` ⇒ INT4 不会被选中 ⇒ **文档不符、非运行时错档**。
- 🔴 **已进最终交付物**：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.zip`
  **5 309 448 161 B** / mtime 2026-11-26 22:39:16 ⇒ zip 内 README 实测仍含该表
  ⇒ **不是候选阶段问题，是已交付物问题** ⇒ 建议 v1.2.1 改（LFM-009：正式发的是 `LiveCaption_MiniMVP_v1.2.1.zip`，由 App 做）。
- 🔴 那四个 RTF 与「61 分钟 0.77」是 **R2T2 口径**、与 §83/ASR-060~061 非同一计分器 ⇒ **本模块不给 06B 档对外数字**。
- 🟢 已发客户 `v1.1.1.zip` 另属一种情况：`release.json` 原文 `ext.version`=**0.4.18**、`ext/` 内 `06b` **0 命中**
  ⇒ 「EXT 的 ASR 在本版不可用」（README「已知问题 4」）在 v1.1.1 仍成立 ⇒ **两版口径须分别说明**。

## §104.3 🟢 跨模块纠偏 LOCK-001/002 已登记并落地（ASR 侧）

### 登记

- **LOCK-001**（11-26 19:59Z，`msg_djwiubxX0MiOhxxIbtTN_j3QLwG7NZ4UQsnPA96DMypnuQ`）：
  机器锁死锁修复——计时/测速作业一律用 `shared\tools\machine_lock.py run` 运行，不再手工建/删 MACHINE_LOCK。
- **LOCK-002**（11-26 22:48Z，`msg_JC9_njlVEGhbz0AnA5nfya7WYvcIcQA6hmmZuC4WqOepkA`）：
  machine_lock.py v2，双格式锁文本、原子写（采纳 MT §126；APP 替换已安装文件）。
- ⇒ 两条均已按原文要点追加进 `status/asr/CORRECTIONS_ASR.md`（索引表两行 + 全文两节，逐条引用、不改写）
  ⇒ 🔴 **不占 ASR 编号、`last_ack` 不变**。

### 工具已装（APP 线程责任）

- `C:\Users\Trekker-PTL\shared\tools\machine_lock.py` **9 397 B** / mtime **2026-11-27 11:32**
  ⇒ 实测含 `_atomic_write`（临时文件 + `os.replace`）与双格式锁文本（首行 + `module:`/`pid:`/`started:`/`host:`）
  ⇒ LOCK-002 的 v2 已生效。`shared\README_LOCK.md` 1 341 B / 11-26 21:43，顶部已有 LOCK-001 段。
- 🟢 本会话复核 `machine_lock.py status` = **HELD**（App APP-154 three arms bgkeep_on_clone，
  pid 9644，job_pid 9524，started 14:44:28，timeout_min 180）⇒ 本会话未取锁、未干扰。

### ASR 侧脚本改造（`qwen3asr_06b/scripts/asr_lock_common.py`，42 193 B / mtime 11-27 11:38:56）

① `parse_lock()` 新增第 ④ 分支 ⇒ 能解析 `machine_lock.py` 的 v1 单格式首行
   （`<module> <pid> <时间> machine_lock.py <说明>`，以前实测 `pid=None`）；
② 新增 `os_lock_live()`（只读探测 `shared\MACHINE_LOCK.os` 是否被活作业独占）；
③ `lock_is_stale()` 新增前置判据 ⇒ **背后有活 OS 锁 ⇒ 绝不判陈旧**（LOCK-002 点名的事故根因修正）；
④ 新增 `inside_machine_lock_run()` + `acquire()` 第 0 步 ⇒ 已在 `machine_lock.py run` 里的作业不再抢锁
   （否则作业会等自己 ⇒ 死锁，正是 LOCK-001 要根治的那一类）；
⑤ `release_lock_if_owner()` 新增护栏 ⇒ machine_lock.py 持有的锁本脚本绝不删；
⑥ `LockProbe.check()` 新增 `machine_lock.py` 分支 ⇒ 不再把「外层持锁」误判成「锁被抢」
   ⇒ 不会把有效计时误标成 `timing_valid=false`。

### 验收

- 🟢 `scripts/asr_lock_001_verify.py`（12 553 B / 11-27 11:39）⇒ **29/29 PASS**（上一会话，无锁环境）：
  含 v1/v2 两种 `job_pid` 写法、活 OS 锁下不删锁、run 内不死锁、LockProbe 不误判、工具静态检查。
- 🟢 原有回归 `scripts/asr_lock_verify.py`（13 086 B）⇒ **19/19 PASS（零回归）**。
- 🟡 **本会话复跑 `asr_lock_001_verify.py` ⇒ 28/29 PASS**，FAIL 项
  「无活 OS 锁 + pid 已死 ⇒ 判陈旧（可回收）」(`pid=999999`)。机理：
  - 情形 A 用例在临时目录造文本锁（pid 已死），但**未把 `CANON_LOCK` 指向临时目录**，
    `os_lock_live()` 探测的是真实 `shared\MACHINE_LOCK.os`；
  - 当时 App 正持活 OS 锁（APP-154）⇒ `os_lock_live()` 返回 True
    ⇒ `lock_is_stale()` 按 LOCK-002 加固「活 OS 锁绝不判陈旧」返回 False（不删）
    ⇒ 用例期望 True ⇒ FAIL。
  - ⇒ **这是 fail-closed 的正确行为，非代码回归**；待 App 释放锁后复跑可回 29/29。
  - 情形 B（真活 OS 锁 + 文本 pid 已死 ⇒ 不判陈旧）PASS，正是 LOCK-002 要的事故根因修正。
- 🔴 全程只在临时目录操作、未触碰真实 `shared\MACHINE_LOCK`（脚本末项自检通过）。
- ⚠️ 上一会话实测抓到的真缺陷（已修）：`job_pid` 正则初版要求行尾 ⇒ v1 写法（`job_pid N timeout_min M` 同一行）
  解析不出 ⇒ `inside_machine_lock_run()` 返 False ⇒ `acquire()` 会等自己 120 s ⇒ 已改为不要求行尾。
- 🟡 **LOCK-001 验收还差一项**：「下一次计时作业日志里有 `[machine_lock] acquired`/`released (rc=…)` 两行」
  ⇒ 本会话无计时作业（App 持锁）⇒ 留到下一轮真计时作业补（用 `machine_lock.py run --module asr` 起）。

## §104.4 其它开口项无变化（只读复核）

- 🔴 修前 v0.4.18/`5121d99` 对照臂仍缺：`shared/bgkeep/` 下无 `v0418*` 目录 ⇒ §96 ① 未闭。
- 🔴 分离人声 16 kHz wav 仍 0 产出：`shared/bgkeep/vocals/` 仍不存在、全盘搜 `*vocal*` 0 命中 ⇒ WER 对比做不了。
- 🟡 对外 NPU 报告「RTF 0.067/WER 0/CER 0」口径仍待 reviewer 说明（§101.5 挂项）。
- 🟡 §99 的「`clone_reasons` 不进 `stats_full`」已闭（v0.4.23 起 11 键），但 APP-131 三字段仍缺两个 ⇒ §101 挂项未闭。
- 🟡 `spk_reason_hist` 的 §100「零缺口」结论已撤回（§101）⇒ 本轮七臂旁路未开 ⇒ 不构成新证据。

## §104.5 纪律与产物

- **租约**：上一会话 acquire 得 `7c01780b`、11:39 后死；本会话 acquire ⇒ TAKEOVER、token `4012e303`，
  beat 14:56:45／14:58:04 OK；末步 release。
- **本会话全程只读复算 + 锁代码单测**：未跑推理/计时/WER/分离器 ⇒ 不取机器锁
  （`machine_lock.py status`=HELD，App APP-154 持锁）⇒ 未干扰任何在跑作业。
- 未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（只读）；未改客户包；未打包；
  未调 MiniMax；未连 B 机；未自行开新实验（ASR-038）。
- **产物**：`notes/asr_s104.md`（本文件，LF）+ `STATUS_ASR.md` §104（36 968 B / 154 行，CRLF）
  + `status/archive/STATUS_ASR_sec103_upto_20261127.md`（§102 全文逐字归档，9 696 B）。
