# STATUS_APP §231 详情（2026-11-24 19:5x–20:3x）

> 🔴 本文件是 `status/app/STATUS_APP.md` **§231** 的正文全文（活文档只留标题＋指针行）。
> 🔴 **只追加，不回头改旧节**；本文件 **write-once**。

## §1 六通道复核 ⇒ **无新 App 纠偏**（`last_ack` 保持 **APP-133**）

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| ① | 局域网 `status/app/CORRECTIONS_APP.md` | **130 条／max APP-133**／SHA256 `2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda`／**440 181 B**／mtime **2026-11-24 13:56:42** | 无 > APP-133 |
| ② | QQ 收件箱（reviewer `alexchen7694@agent.qq.com`） | 最新 **App** 封 = **APP-133**（`msg_HbiVRXlgp8eXsg7kDK4uUcgmLi_ao2pMbVJcZzbdbNhmGw`，2026-11-24T05:56:40Z） | 无 > APP-133 |
| ③ | QQ 垃圾箱 | **0 封** | 空 |
| ④ | QQ 已删除 | **1 封**＝MiniMVP rc9 性能报告（11-13，**与 App 纠偏无关**） | 无关 |
| ⑤ | 根 `status/CORRECTIONS.md` | max **C-135**（**该文件已于 10-23 冻结**） | 不属 App 模块 |
| ⑥ | `shared/NOTICE*` | 最新 **2026-11-05** | 无新 |
| ⑦ | agent-mail | `not_bound` | 未开通 |

- 🟢 **收件箱整体最新 = H-028 [MT]**（`msg_23BciIYN3hFfEMcWmHS-T030k5PJXqk-WVhqGsWNCtbPBA`，10:11:12Z）
  ＝ **MT 模块**（Hy-MT2→Hy-MT3 升级）⇒ 其正文明确「**App 接入等本条验收后另发 APP 纠偏**」
  ⇒ **本轮不据此动 App 代码**。
- 🔴 **结论**：本地 max ＝ QQ max ＝ `last_ack` ＝ **APP-133** ⇒ **无新条目**
  ⇒ 按 MEMORY §三「**无新纠偏时 `last_ack` 不变**」⇒ **`last_ack` 保持 APP-133**。

## §2 上一会话遗留项（TAKEOVER ⇒ 从断点继续，**不从头重做**）

- 🔴 **租约**：`acquire app` ⇒ exit 0 / **TAKEOVER**（上一会话 token `47796b43`，17:06:53 起、
  last_beat 18:34:37 ＝ **78 min 前** ⇒ 死会话；note＝「已提交 `19d9369` 并推送（origin/main 0/0）；
  邮件 2 封已发（含 3 个 OGG）；**写记忆文件**」；`live_pids=[]` `alive=False`）
  ⇒ 本轮 token **`377715be`**，beats ×N，收尾 `release`。
- 🟢 **上一会话已完成的部分（复核确认，无需重做）**：
  | 项 | 实测 |
  |---|---|
  | 提交 | **`19d9369`**（52 个文件，**只 App 侧**；**未 add** `CORRECTIONS_APP.md`） |
  | 推送 | `origin/main` ＝ `19d9369`，**ahead/behind 0/0**（`git rev-list --left-right --count origin/main...HEAD`） |
  | 邮件 | **3 封已发**（`msg_IUZ_i57L…` 交付／`msg_cG7Lu6ZZ…` 三臂数字＋**3 个 OGG 附件**／`msg_lkjLer4m…`） |
  | STATUS | **§228 / §229 / §230** 已追加并提交（+ companion 三件） |
  | 整链三臂 | 已跑完（17:45:04→18:25:10，**一次持锁到底**，`lock_lost` **0** 条） |
- 🔴 **上一会话未完成的部分（＝本轮闭合的遗留项）**：
  它的 `results/app/_app133_write_memory.py` **存在但从未运行**
  ⇒ ① `.workbuddy/memory/2026-11-24.md` **无「第 126 轮」**（实测轮次只有 123/124/125）；
  ② `.workbuddy/memory/MEMORY.md` **无机器锁指针**，且 §十二 首行仍写
  **`last_ack=APP-128`（已过期**，实际 APP-133）；③ `MEMORY_MODULES.md` **无本轮细节**；
  ④ 该脚本**还漏了 `MEMORY.md` 的 9 700 字符上限断言** ⇒ 本轮补上。
- 🟢 **本轮闭合方式**：`results/app/_app231_write_memory.py`（写入）＋
  `results/app/_app231_verify_memory.py`（**另起脚本独立复核 19/19 PASS**）：
  | 文件 | 结果 |
  |---|---|
  | `2026-11-24.md` | **append-only**（轮次 3 → 4；旧段是写前备份的**前缀** ⇒ 逐字未变） |
  | `MEMORY.md` | **9 700 → 9 655 字符**（上限 9 700，余 45）｜**行数 +1**｜**纯 LF**｜新指针落在「二、机器锁」小节内｜**除被压缩的 3 行外逐行逐字未变**（且差异行**都在 §十二 内**）｜**`last_ack` 已更新为 APP-133**｜压缩的三行**判据关键词未丢**（`854`／`n_speakers=0`／`b2a4978`／`msg_52Ta35`／`b7507cb`／`reviewer 复算底本`） |
  | `MEMORY_MODULES.md` | **追加「五十」小节**（+5 969 B）｜旧正文是写前备份的**前缀** ⇒ 逐字未变｜**围栏仍配对**（22 个） |
- 🔴 **`CORRECTIONS_APP.md` 零改动**（收尾四项指纹逐字一致）：SHA256 `2db65bf1…`／
  **440 181 B**／`## APP-xxx` **130 条**。

## §3 APP-132 的**生产路径补漏**（本轮主发现）

### 3.1 事实：上一轮（§230）的修法只落在**侧写 harness**

- 🔴 §230 写的是「APP-132 机器锁修掉两处真缺陷」，其实现落在
  **`results/app/_app132_lock.py`** ＝ **专供 v2.6 整链三臂跑的侧写 harness**。
- 🔴 **真正成包的路径没被修**：
  `live_caption/_app116_build_v25.py`（v2.5/v2.6 成包都走它）
  ⇒ `live_caption/_app129_build_v26.py` 第 216 行 `B.acquire_lock('app build v2.6 copy')`。
- 🔴 该文件里**两处原缺陷原封不动**：

| # | 位置 | 缺陷 | 后果 |
|---|---|---|---|
| ① | `acquire_lock()` 末行 `os.replace(tmp, LOCK)` | **不是原子创建** | 两个进程可同时「拿到」锁；且**会覆盖别人刚建的锁**（TOCTOU） |
| ② | `start_lock_watchdog()` | 条件 `own is None or own.get('pid') == os.getpid()` ⇒ 被抢即放弃写回；写回又用 `os.replace` | 链**继续跑但不再持锁**且**无人知晓**；写回还**静默覆盖别人的锁** |

### 3.2 🔴 通用判据：**「修了 harness」≠「修了产品」**

交付路径与验收路径是**两条路** ⇒ 修锁/修闸门/修格式时**必须问：「生产上真正跑的是哪个文件？」**
（本例：`import _app116_build_v25 as B` ⇒ 生产走 **B**，不是 harness）。
⇒ 与 MEMORY §四「**PASS ≠ 正确**」同族：**验收通过的那条路 ≠ 生产实际跑的那条路**。

### 3.3 修法：机器锁必须「tmp 写全 + `os.link`」（原子 + 独占 + 不露半成品）

仓库根 `machine_lock_app.py` 第 405~420 行有**逐字论证 + 实测事故**：

| 写法 | 原子？ | 独占？ | 别的模块会看到半成品锁？ |
|---|---|---|---|
| `os.replace(tmp, LOCK)` | 🔴 **否** | 🔴 **否**（覆盖别人） | 否 |
| `os.open(O_CREAT\|O_EXCL)` **再写内容** | ✅ | ✅ | 🔴 **会**（先建空文件、之后才写内容 ⇒ 窗口内别人读锁**解析不出 pid** ⇒ 判成「陈旧锁」⇒ `os.remove` **删掉我们的活锁** ⇒ 两模块同时跑） |
| ✅ **tmp 写全 + `os.link(tmp, LOCK)`** | ✅ **是** | ✅ **是**（目标已存在 ⇒ `FileExistsError`） | ✅ **不会**（内容要么完整、要么文件不存在） |

⇒ 依据 `shared/NOTICE_tts_lock_atomic_20261026.md`；与仓库根
`machine_lock_app._write_lock_atomically` **同源同法**（该模块的公开入口注释写明
「**App 侧所有计时脚本统一走这里 ⇒ 不再各写一份（逻辑漂移的根源）**」——本轮教训正是**逻辑漂移**）。

### 3.4 实际改动（**只改一个文件**）

- `live_caption/_app116_build_v25.py`：**10 820 B / SHA256 `49c879e1817ab9c9ae08b0b8a148688e554f883fa1400194252c3364d98d4119`**
  ⇒ **15 749 B / SHA256 `8d1c9b5e6226b5d65c30e83104e8708ba3a4bc2a9b820a0a171824ecbc58dddb`**
  （`ast.parse` OK，**纯 LF**）：
  ① 新增 `_create_lock_exclusive()`（tmp 写全 + `os.link`，**独占**）；
  ② `acquire_lock()` 把「探测 ⇒ 创建」**合并进同一个 while 循环**（**消除 TOCTOU 窗口**），
  别人抢先 ⇒ **不覆盖**、继续等；
  ③ `start_lock_watchdog()` 改为**只自检、不盲写**：锁被删 ⇒ **原子+独占地补建**
  （补不上 ⇒ 已被别人抢 ⇒ 记 `lock_lost`）；锁被别人抢走 ⇒ **记 `lock_lost` 事件**、**不写回**；
  锁仍是自己的 ⇒ 内容静态 ⇒ **不动文件**；
  ④ 新增 `release_lock()` 事件登记（released／release_skipped_not_owner／release_no_lock）；
  ⑤ 新增 `results/app/app231_pack_lock_events.jsonl`（JSONL，一行一条）。
- **未碰**客户包、**未碰**其它模块文件、**未碰** `status/app/CORRECTIONS_APP.md`。
- 🔴 **补丁脚本幂等**：`_app231_patch_lock.py` 带守卫「已打过补丁 ⇒ 拒」。

## §4 独立行为级复核 **9/9 PASS**（`results/app/_app231_verify_lock.py`）

- 🔴 **纯 CPU 逻辑测试**：**不跑推理·不测速**、**用临时目录做锁** ⇒ **不碰真
  `shared\MACHINE_LOCK`**（按纪律「纯静态检查／不载模型的 CPU 单测不锁」）⇒ 与其它模块零干扰。
- 判据①**确定性**（6 进程经**文件栅栏**同瞬间并发建锁 ⇒ **恰好 1 个**成功：n_created=1）；
- 🔴 **反证组**（同测试跑在旧 `os.replace` 实现上 ⇒ **2 个**成功 ⇒ **缺陷可复现**
  ⇒ **判据能识破有缺陷的旧代码** ⇒ 不是「判据恒 PASS」的假 PASS）：new=1 / old=2；
- 判据②**端到端重叠**（两进程走完 `acquire_lock`，持锁期间每 100 ms 读锁内容
  ⇒ **无「两把锁并存」**：n_overlap=0）；
- ＋别人先建锁 ⇒ 我方独占创建**失败**且锁内容**未被覆盖**；
- ＋看门狗：锁被抢 ⇒ **记 `lock_lost` 事件** 且 **不覆盖**别人的锁；
- ＋放锁：内容不是自己的 ⇒ **不删**别人的锁。
- 证据：`results/app/app231_lock_verify.json`（**9/9 PASS**）＋
  产生它的脚本**一并入库**（§222：**证据 json 入库 ⇒ 其产生脚本也要入库**）。

## §5 🔴 本轮新学的两个判据坑（已下沉 `MEMORY_MODULES.md` 五十）

1. 🔴 **「两个进程都拿到锁」≠「两把锁并存」** —— 进程 A 可能**先放锁再轮到 B**
   ⇒ 那是**合法串行**，不是违规（**本轮实测**：初版判据数「拿到锁的进程数」⇒ 报 FAIL，
   实际是**判据错**，不是代码错）⇒ ✅ 判据必须测「**持锁期间锁内容被别人改写**」这个
   **重叠**现象，**不能数进程数**。
2. 🔴 **判据写文本计数 ⇒ 必假 FAIL** —— `os.replace(tmp, LOCK)` 这个串在**新 docstring 里
   本来就要出现**（解释旧缺陷）⇒ 文本计数命中 ⇒ 误报「旧的非原子写仍在」
   ⇒ ✅ **改用 AST 判定**「代码里不得存在对 `os.replace` 的调用」
   （`ast.walk` 找 `Call(func=Attribute(attr='replace', value=Name('os')))`）
   ⇒ **语义精确、注释/docstring 不误伤**。
   ⇒ 与 MEMORY §四「**判据里写死的常量 = 假 FAIL 源**」同族：**判据要绑语义，不绑字面**。
3. 🔴（附带）**Python `spawn` 不能 pickle 局部函数** ⇒ 并发测试的子进程目标函数必须在**模块级**；
   且竞态测试要用**文件栅栏**才**确定性**（否则「两边都拿到」可能根本没发生 ⇒ 判据不可靠）。

## §6 纪律

- 🟢 **未打包 zip**（用户级纪律「**不通知 ⇒ 不打包**」；完整版 v2.x 历来无 zip ⇒ 只出目录＋签 ACCEPTED）
- 🟢 **未覆盖／未删除任何旧版本目录与 zip**｜🟢 **未通知用户**｜🟢 **未连 B 机**
- 🟢 **未调 MiniMax**｜🟢 **未跑推理·未测速**（纯逻辑测试，不占机器锁）
- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（只读；收尾四项指纹逐字一致 ⇒ SHA 零改动）
- 🟢 **未进 MiniMVP 包**｜🟢 **未吞其它模块的未提交改动**（全仓脏文件是别的模块的）
- 🔴 **本条需等 reviewer 复核**。
