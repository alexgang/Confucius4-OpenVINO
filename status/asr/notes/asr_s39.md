# §69 / ASR-039 —— 会话租约（module lease）落地明细

> 本文件是 `status/asr/STATUS_ASR.md` §69 的明细，**结论与数字以 STATUS 为准**。
> 写作时间：2026-11-01 16:23（会话 token = `055db860`）。
> 本轮**纯文档 + 自动化指令编辑**：未跑推理、未计时 ⇒ 未申请 `shared/MACHINE_LOCK`；未动 `live_caption/`；未改 `CORRECTIONS_ASR.md`；未开新实验；未打包。

## 0. 本轮读到的新纠偏

- `CORRECTIONS_ASR.md` mtime = **2026-11-01 15:36**，size = **17 462 B**（本轮只读，未修改）。
- 旧 `last_ack` = **ASR-038** ⇒ 新条目 = **ASR-039**（[HIGH] 2026-11-01 15:40 — 巡检会话互相重叠：每个会话开工前先拿「模块租约」）。
- 索引表里 ASR-037 / ASR-038 / ASR-039 **均未列入**（索引止于 ASR-036）⇒ 索引表由 reviewer 维护，本模块**不改**（同 ASR-036 处置）。

## 1. 第 0 步：拿租约（ASR-039 要求 ①）

### 1.1 脚本实测

| 项 | 实测值 |
|---|---|
| 路径 | `C:\Users\Trekker-PTL\shared\tools\session_lease.py` |
| size | **5 574 B** |
| mtime | **2026-11-01 15:34:48** |
| 行数 | **132** |
| 解释器 | `C:\Users\Trekker-PTL\.workbuddy\binaries\python\versions\3.13.12\python.exe`（3.13.14；`which python` 亦解析到同一路径） |

### 1.2 acquire

```
> python C:\Users\Trekker-PTL\shared\tools\session_lease.py acquire asr
TOKEN=055db860
EXIT=0
```
- 无 `TAKEOVER`（`shared\leases\asr.json` 此前不存在）⇒ **不是断点续跑**，从头执行。
- 租约文件：`C:\Users\Trekker-PTL\shared\leases\asr.json`（与 `ext.json` 同目录，ext 于 16:15 建立，**不冲突**、各模块独立文件）。

### 1.3 协议自测（反证：两条失败路径都按 ASR-039 写的退出码走）

| 场景 | 期望（ASR-039 原文） | 实测输出 | 退出码 |
|---|---|---|---|
| 第二次 `acquire asr`（同会话再抢） | **10** = BUSY，另一个会话/作业还活着 ⇒ 零改动立即结束 | `BUSY token=055db860 started=11-01 16:18:29 last_beat=11-01 16:20:32(1min前) ... alive=True` | **10** ✅ |
| `beat asr <错误token>` | **11** = LOST，租约已被接管 ⇒ 立即停止，不再写文件 | `LOST lease (已被接管或已释放)： token=055db860 ... → 立即停止，不要再改任何文件。` | **11** ✅ |

> 🔴 自测只读状态、**未破坏本会话自己的租约**（第二次 `acquire` 在 BUSY 分支 `return 10`，不覆盖 token；`beat` 在 token 不匹配分支 `return 11`，不写盘）⇒ 事后 `status asr` 仍显示 `token=055db860 ... alive=True`。

### 1.4 本轮实际用到的命令

```
acquire asr                              -> TOKEN=055db860            (exit 0)
beat asr 055db860 "<进度>"                -> OK beat ...               (exit 0)  ×N
acquire asr   [自测 BUSY]                 -> BUSY ...                  (exit 10)
beat asr deadbeef "self-test" [自测 LOST] -> LOST ...                  (exit 11)
status asr                               -> asr token=055db860 ... alive=True
release asr 055db860                     -> RELEASED                  (exit 0)
```

- `addpid` 本轮**未用**：无后台长作业（纯文档，不跑推理/不计时/不打包）⇒ 没有需要登记的 PID。

## 2. 自动化指令改造（ASR-039 要求 ① / ⑤）

### 2.1 工具能力实测

- 用 WorkBuddy 的 `automation_update`（`mode=update`）直接改本模块自动化 **成功** ⇒ **不需要用户在 UI 里手改**。
- 自动化 id = `0cc12c3b-6fc1-42ad-98f3-0a1d9661d5a6`，name = **「ASR 模块纠偏定期检查」**，`rrule = FREQ=HOURLY;INTERVAL=1`，`status = ACTIVE`。
- 改完**回读**（`mode=view`）确认新指令已生效（不是「写盘了就算」）。

### 2.2 改动 diff（唯一一处：在原「执行步骤」之前插入「第 0 步」+ 会话中间/收尾两段）

原文（改动前）开头是「检查 … 若有则按要求执行。/ 背景 / 执行步骤：1. 读 …」，
改动后**在「执行步骤」之前**插入：

```
第 0 步（模块租约，必须最先执行；依 ASR-039）：
python C:\Users\Trekker-PTL\shared\tools\session_lease.py acquire asr
- exit 10 (BUSY)：另一个会话或它的后台作业还活着。只输出一句「上一会话仍在进行，跳过本轮」，然后立即结束：不读其他文件，不改任何东西，不碰 MACHINE_LOCK。
- exit 0：拿到 TOKEN=xxxx，记下这个 token，后面的步骤都带上它。
- 若打印 TAKEOVER：上一会话已经死了 ⇒ 先读它留下的 note、STATUS 和产物，从断点继续，不要从头重做。
- 调用 session_lease.py 用 WorkBuddy 自带 python：C:\Users\Trekker-PTL\.workbuddy\binaries\python\versions\3.13.12\python.exe。

会话中间（每完成一步，以及每次耗时操作前后）：
python C:\Users\Trekker-PTL\shared\tools\session_lease.py beat asr <token> "<一句话进度>"
- exit 11 (LOST)：租约已被别的会话接管 ⇒ 立即停止，不再写任何文件。

长作业（打包、计时、e2e）：
- 一律用 schtasks 或 Start-Process 后台启动，拿到 PID 后马上执行：
  python C:\Users\Trekker-PTL\shared\tools\session_lease.py addpid asr <token> <pid>
- 不要在一个工具调用里同步等待超过 20 分钟，要分次轮询，轮询之间 beat。
- 只要登记的 PID 还活着，新会话就会拿到 BUSY，不会重复启动同一个作业。

本轮结束（包括「无新纠偏、跳过」的情况）的最后一步：
python C:\Users\Trekker-PTL\shared\tools\session_lease.py release asr <token>
- 如果还有后台作业活着，脚本会自动保留租约（输出 KEPT）。
```

另把原第 2 步末尾补了半句：「…然后结束（**结束前仍要 release 租约**）。」

### 2.3 逐条对照 ASR-039

| ASR-039 要求 | 落地情况 |
|---|---|
| ① 在现有「第 0 步」**之前**插入 acquire | ⚠️ **原文没有「第 0 步」**（原指令直接从「执行步骤：1.」开始）⇒ 本轮**把 acquire 放在最前**，作为新增的「第 0 步（必须最先执行）」；其余原文一字未删 |
| ① exit 10 ⇒ 只输出一句、立即结束、不碰锁 | ✅ 已写进指令（含「不碰 MACHINE_LOCK」） |
| ① exit 0 ⇒ 带 token；TAKEOVER ⇒ 从断点继续 | ✅ 已写进指令 |
| ② 会话中间 beat；exit 11 ⇒ 立即停止 | ✅ 已写进指令 |
| ③ 长作业后台启动 + `addpid` + 不超 20 min 同步等待 | ✅ 已写进指令（本轮无长作业 ⇒ 未实际调用 `addpid`） |
| ④ 收尾 `release`（含「无新纠偏、跳过」也要 release） | ✅ 已写进指令，且本轮**实际执行了** release |
| ⑤ 指令全文/改动 diff 贴进 STATUS 新章节 | ✅ 见 §2.2（STATUS §69 内附同样文本） |
| ⑤ 若工具不允许线程自改 ⇒ 写「需用户在 UI 里改」 | ➖ **不适用**：`automation_update` 可用且已改成功 |
| ⑥ MACHINE_LOCK 规则不变（排队等待、不抢锁）；租约 ≠ 机器锁 | ✅ 原「硬性纪律」段**整段保留未动**；本轮无计时作业 ⇒ 未申请机器锁 |

## 3. 与 MACHINE_LOCK 的关系（ASR-039 要求 ⑥）

- `shared/MACHINE_LOCK` 本轮巡检时**不存在**（`ls` 报 No such file）⇒ 无模块持锁。
- 本轮**纯文档**：无推理、无计时、无打包 ⇒ 按既有纪律**不需要**机器锁（数值/质量作业不需要锁；计时作业才需要）。
- 租约管「同一模块不能有两个会话」，机器锁管「不同模块不要同时占用设备」⇒ 两者**都要遵守**，指令里两者都在。

## 4. git 纪律

- `git fetch origin` 后 **HEAD == origin/main == `087c1cc`**（一致 ⇒ 可提交）。
- `git status --short status/asr/` ⇒ 仅 `M status/asr/CORRECTIONS_ASR.md`（**reviewer 推的**，按既有纪律**不提交**，只 `git add status/asr/STATUS_ASR.md` + `status/asr/notes/asr_s39.md`）。
- `live_caption/` 下的未跟踪文件**全部不碰**（ASR-003 起 C-111 已移交 App 模块）。
- 无 `GIT_FREEZE` ⇒ 允许 commit/push。
- 提交用 `git commit --only <file>`（4 线程共用 worktree，避免误带他人改动）。

## 5. 未做 / 待用户指派（不自行扩范围）

- 本轮**未**跑推理、**未**计时、**未**测速、**未**打包、**未**动 `live_caption/`、**未**改 `CORRECTIONS_ASR.md`、**未**覆盖任何已交付产物、**未**新增任何 `asr1xx` 守卫/复核脚本（ASR-038 ① 继续遵守）。
- 非纠偏遗留仍是 3 条（OV f16 偏差 / `qwen3asr_06b` 打包 / `pya_*` 历史产物），**等用户指派**。
- ASR-039 要求「reviewer 查看 `shared\leases\` 和 automation.log，确认之后不再出现同一模块两个会话同时 working」⇒ **属 reviewer 验收动作**，本模块只负责把租约机制装好并在本轮实际用过一轮。
