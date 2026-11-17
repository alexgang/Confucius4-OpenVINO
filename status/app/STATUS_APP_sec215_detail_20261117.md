# §215 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-115**）｜🔴 **接续上一会话（TAKEOVER）并闭合 §214 的未结项「094715 臂的争用源未定位」**｜🟢 **两臂的争用源＝reviewer 侧 EXT replay 作业（实物证据）**｜🔴 **锁丢失根因＝reviewer 脚本 `finally` 无条件 `Remove-Item $lock`**｜🟢 **验收 harness 的锁获取改 fail-closed（原实现 fail-open ⇒ 静默覆盖他人锁）**｜**未打包／零客户包写入／零产品代码改动**

> 本文件是 `status/app/STATUS_APP.md` **§215 的 companion 正文**（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
> 纠偏来源：**无新条目**（`CORRECTIONS_APP.md` 115 条／最大 **APP-115** ＝ `last_ack`）⇒ 本节为**接续上一会话的取证收尾**，不认领新编号。
> 上一会话（token `09df68e8`）于 11-17 18:41 后失联 ⇒ 本轮 **TAKEOVER** 接手，**从断点继续**：其 note 停在「已定位 094715/100823 两臂的 EXT 争用源；正在核对锁释放路径」。

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| 是否有新 reviewer 纠偏 | ❌ **无** —— 纠偏文件 **115 条／最大 APP-115**，SHA 与上轮逐字一致；`last_ack` **不写新编号**（仍 APP-115） |
| §214 未结项「094715 臂的争用源未定位」 | 🟢 **已闭合** —— 争用源＝**reviewer 侧 EXT replay 作业**（`replay2_lad`），与 100823 臂**同一个作业、同一机制** |
| 「锁在运行中丢失」的根因 | 🔴 **已定位** —— reviewer 脚本 `finally { Remove-Item $lock }` **无条件删锁**（不看内容、不看持有者）⇒ 放锁时锁已被删 ⇒ `lock_content_at_release=None` |
| 两臂计时有效性 | 🔴 **维持作废**（`timing_valid=false`）—— 结论与 §214 一致，**不翻案**；本节只补「为什么」 |
| 本轮改动 | 🟢 **仅验收工具**：`results/app/_app588_sp4_acceptance.py` 的锁获取改 **fail-closed**（原 fail-open ⇒ 静默覆盖他人锁）＋ 证据 JSON 落盘 |
| 产品代码／客户包／zip | 🚫 **零产品代码改动／零客户包写入／未打 zip**（用户未通知 ⇒ 不打包） |

---

## 1. 无新纠偏的核对（开工＝收尾逐字一致）

`status/app/CORRECTIONS_APP.md`（reviewer 独占写入，本模块**只读**）：

| 项 | 值 |
|---|---|
| SHA256 | `fac6e56d335d296028f963ada5ff6bd829d514276786d000fe2f8caef2c56752` |
| 字节数 | **385 724 B** |
| mtime | **2026-11-17 13:00:15** |
| `## APP-xxx` 条目数 | **115**（APP-001 … APP-115，**无 ≥116**） |
| `STATUS_APP.md` 头部 `last_ack` | **APP-115** ⇒ **无编号大于 last_ack 的新条目** ⇒ **本轮不执行任何新纠偏**，**不写自己的编号** |

其余通道全空（与上轮一致）：agent-mail 工具层仍 **`not_bound`**（**连续第 27 轮**；面板显示 connected 但工具明确「当前请勿重试」⇒ **未重试**）；`shared/NOTICE*` 最新仍 **11-05 09:35**；根 `status/CORRECTIONS.md`（10-24）与 ASR `CORRECTIONS_ASR.md`（11-17 14:54）**无 App 条目**；git 分支 `main`。

---

## 2. 墙钟锚点校准（🔴 先解决「和死会话数字对不上」再谈结论）

死会话的 `results/app/app591_app115_ext_contention_forensics.json`（19:15 落盘，未提交）给出 094715 臂窗口 `09:47:52..09:57:26`；本轮独立复算得 `09:47:15..09:57:32`（取 harness 的 `started`）⇒ **两者差 37 s**。

**根因＝锚点口径不同，不是数据打架。** 本轮用**结束锚定**复核（`jsonl` 的 mtime 减去「最后一句 `t_done` − 首句 `t_submit`」），逐臂与死会话窗口对照：

| 臂 | 本轮结束锚定 | 死会话窗口 | 差 |
|---|---|---|---|
| `093348` cold_zh | 09:34:58..09:44:29 | 09:35:00..09:44:29 | 2 s |
| `094715` zh | 09:47:50..09:57:26 | 09:47:52..09:57:26 | 2 s |
| `095732` en | 09:58:06..10:07:42 | 09:58:06..10:07:41 | 0 s |
| `100823` zh | 10:09:00..10:18:53 | 10:09:03..10:18:52 | 3 s |
| `101859` en | 10:19:32..10:29:10 | 10:19:33..10:29:10 | 1 s |

⇒ **五臂全部吻合（±1–3 s）** ⇒ 死会话的锚点**成立**；本节沿用该口径，**结论以双方一致的数值为准**。（死会话的 JSON 仍未提交，本轮另立 `app591_app215_ext_contention_forensics.json` 落盘本模块自有证据。）

---

## 3. 争用源：EXT replay 作业（🔴 §214 记为「未定位」的那一项）

### 3.1 实物证据链

| 环节 | 证据 | 文件 |
|---|---|---|
| ① EXT 作业在跑 | CUDA trace 11-17 两段：**行 4038–4195**（`09:48:59..09:54:10`，**62 REQ**）／**行 4197–4371**（`10:08:50..10:14:07`，**68 REQ**） | `C:\Users\Trekker-PTL\live_dub_ext\.tmp\replay2_lad\Confucius4LiveCaption\tts_cuda_trace.log`（296 649 B／mtime **2026-11-17 10:14:07**） |
| ② 它属 11-17（不是别的日期） | 该两段的**落盘产物 mtime** 落在同区间：`out_intro_busy/*.wav` **09:49:11–09:54:09**／`out_intro/*.wav` **10:08:57–10:14:07**；trace 的日期回退点只有 3 个（行 568／2370／4037）⇒ **行 4038 起即 11-17** | `_reviewer_tmp/spktest/out_intro_busy/`、`out_intro/` |
| ③ 它就是 reviewer 的 replay 作业 | `replay2.py` 第 2 行 `os.environ['LOCALAPPDATA'] = r'C:\Users\Trekker-PTL\live_dub_ext\.tmp\replay2_lad'` ⇒ **trace 路径由该脚本指定** | `_reviewer_tmp/replay2.py` |
| ④ 与两臂窗口重叠 | 094715 臂 `09:47:52..09:57:26` ⊃ `09:48:59..09:54:10`；100823 臂 `10:09:03..10:18:52` ⊃ `10:08:50..10:14:07` | §214 companion §5.2 |
| ⑤ 产物计数互证 | `out_intro_busy` **62** 个 wav ↔ trace 该段 **62 REQ**；`out_intro` **68** 个 wav ↔ **68 REQ** | 同上 |

### 3.2 🔴 **App 自己的 sidecar 记录**（独立佐证，不依赖 EXT 侧任何自述）

判据只用 **App 日志自带字段** `[sidecar] DONE rid=N … elapsed=Xs`（App 的 tts_cuda 客户端打印，164 句逐句可对齐）：

| 臂 | reviewer 作业窗口**内**的 sidecar elapsed | 窗口**外** | 判读 |
|---|---|---|---|
| `094715` zh | n=91　p50 **1.080**　p90 1.348　max 1.45　**n>1s=27** | n=73　p50 **0.500**　p90 0.826　n>1s=8 | **内 p50 是外的 2.16 倍** |
| `100823` zh | n=154　p50 **1.210**　p90 1.468　max 3.25　**n>1s=35** | n=10　p50 **0.530**　p90 0.670　n>1s=10 | **内 p50 是外的 2.28 倍** |
| `093348` cold_zh（对照） | **n=0**（窗口内无 reviewer 作业） | n=164　p50 **0.390**　n>1s=**1** | 干净臂 |
| `095732` en（对照） | **n=0** | n=164　p50 **0.440**　n>1s=**1** | 干净臂 |
| `101859` en（对照） | **n=0** | n=164　p50 **0.440**　n>1s=**1** | 干净臂 |
| `140853` zh（对照，§214 的干净臂） | **n=0** | n=164　p50 **0.410**　n>1s=**1** | 干净臂 |

### 3.3 🔴 **自然实验：慢句 100 % 落在 reviewer 作业窗口内**

以 **`synth_rtf > 1.0`** 判「慢句」，以**作业窗口**（§3.4 的实物证据）判归属：

| 臂 | 窗口**内**句数 / 其中慢句 | 窗口**外**句数 / 其中慢句 | 慢句是否全在窗口内 |
|---|---|---|---|
| `094715` zh | 91 / **37** | 73 / **0** | 🟢 **是（37/37）** |
| `100823` zh | 154 / **48** | 10 / **0** | 🟢 **是（48/48）** |
| `093348` cold_zh（对照） | 0 / 0 | 164 / 1 | ❌ 否（**1** 句在窗口外） |
| `095732` en（对照） | 0 / 0 | 164 / 1 | ❌ 否（同上） |
| `101859` en（对照） | 0 / 0 | 164 / 1 | ❌ 否（同上） |
| `140853` zh（对照） | 0 / 0 | 164 / 1 | ❌ 否（同上） |

⇒ **两条受害臂的慢句 37/37 与 48/48 **全部**落在 reviewer 作业窗口内，而 4 条对照臂与 reviewer 作业**零重叠**（各只有第 0 句的冷启动一次性慢句）** ⇒ **争用 ⇒ 合成变慢**这条因果链由 **App 侧自有记录**独立成立，**不依赖 reviewer 的任何自述或解释**。

### 3.4 争用窗口的口径（🔴 **不用 trace 时钟单独推日期**）

🔴 **口径修正（对死会话取证 JSON 的复核意见）**：死会话的 `app591_app115_ext_contention_forensics.json` 列出**三段** 11-17 reviewer 会话，其中「`10:11:08..10:15:52`、82 REQ、行 569–791」一段的**日期依据不成立**：trace 的**日期回退点**只有 3 个（行 568 / 2370 / 4037）⇒ 行 569–791 属于**更早的一天**（它排在 11-17 段之前）；且其声称的 `out_intro/*.wav` mtime 依据只覆盖 67 个文件中的 39 个，**而那 39 个文件其实属于 `10:08:50..10:14:07` 那一段**（`out_intro` 全量 mtime 实测 **10:08:57..10:14:07**）⇒ **该段不应算作 11-17 的会话**。

🔴 本轮改用**作业窗口**（三重实物证据，确定性高于 trace 时钟）：

| 作业 | 窗口 | 实物依据 |
|---|---|---|
| `job1`＝`run417.ps1` | **09:46:49..09:54:10** | 脚本 mtime **09:46:49** ＋ `out_intro_busy/*.wav` mtime **09:49:11–09:54:09**（**62** 个文件 ↔ trace 该段 **62** REQ） |
| `job2`＝`q417.ps1` | **10:07:53..10:18:28** | `q417.out` 逐行记录：`queued 10:05:23` / **`FREE 10:07:53`** / `DONE 10:18:28` / `lock released` ＋ `out_intro/*.wav` mtime **10:08:57–10:14:07**（**68** 个文件 ↔ trace 该段 **68** REQ） |

🔴 **`job2` 的窗口覆盖了 100823 臂的整个窗口**（臂 10:08:23–10:18:59 ⊃ 作业 10:07:53–10:18:28）⇒ 该臂 `lock_content_at_release=None` 有直接解释（见 §4）。

### 3.5 落盘证据

`results/app/app591_app215_ext_contention_forensics.json`（**5 441 B**，本轮落盘）：`reviewer_jobs_on_20261117`（两作业的 window/date_basis）＋ `reviewer_trace_segments_on_20261117`（两段 clock/n_req/trace_lines）＋ `replay2_lad_trace`（bytes/sha256/mtime）＋ `arms`（六臂 inside/outside 的 n/p50/p90/max/n>1s ＋ `slow_rtf_gt_1` ＋ `all_slow_inside_reviewer_job`）。

---

## 4. 🔴 锁丢失的根因（死会话 note 里「正在核对锁释放路径」那一问）

### 4.1 现象

| 臂 | 取锁时刻 | 放锁时锁内容 | `waited_s` |
|---|---|---|---|
| `093348` cold | 09:33:48 | `app 17044 …`（**还是本作业**） | 0.0 |
| **`094715` zh** | 09:47:15 | **`None`**（锁文件已不在） | 0.0 |
| `095732` en | 09:57:32 | `app 24508 …` | 0.0 |
| **`100823` zh** | 10:08:23 | **`None`** | 0.0 |
| `101859` en | 10:18:59 | `app 24124 …` | 0.0 |
| `140853` zh（§214 干净臂） | 14:08:53 | `app 12080 …` | 0.0 |

⇒ **恰好两条受害臂的锁被删**，其余四臂放锁时锁**仍是本作业** ⇒ **不是 App 自己的放锁路径**（App 的 `release_lock` 只删自己 pid 匹配的锁）。

### 4.2 根因（reviewer 侧脚本）

reviewer 的 4 个 ps1 与 2 个 py **全部**在收尾无条件删锁：

```powershell
# _reviewer_tmp/run417.ps1（mtime 11-17 09:46:49）
} finally { Remove-Item $lock -ErrorAction SilentlyContinue; "lock released" }
```
（`ab417.ps1` / `ab418.ps1` / `ab418b.ps1` / `q417.ps1` 同款；`stab_arms.py` / `acc_run.py` 用 `os.remove(LOCK)`）

且 `q417.ps1` 的排队日志**直接记下了抢锁时刻**：

```
queued 10:05:23
FREE 10:07:53          ← 轮到它拿锁
...
lock released
DONE 10:18:28          ← 收尾删锁
```

🔴 **关键**：`q417.ps1` 在 `10:05:23` 排队、`10:07:53` 拿到锁、**`10:18:28` 才删锁** ⇒ 这把锁**覆盖了 100823 臂的整个窗口（10:08:23–10:18:59）**，并且在 **App 放锁之后**才被删 ⇒ **App 放锁时锁已被 reviewer 删掉** ⇒ `lock_content_at_release=None`。094715 臂同理：`run417.ps1`（mtime **09:46:49**）在 094715 臂开跑前 26 s 就已写锁，其 `finally` 在臂窗口内删锁。

⇒ 🔴 **「锁丢了」不是 App 的 bug，是 reviewer 脚本删了别人的锁**；而 **App 侧确实有一个真缺陷**：见 §5。

---

## 5. 🔴 本轮修掉的真缺陷：验收 harness 的锁获取是 **fail-open**（⇒ 静默覆盖他人锁）

### 5.1 缺陷（**行为级复现**，非读码猜测）

reviewer 侧锁内容格式**两种**，`int(parts[1])` 都解析不出 pid：

- `run417.ps1`：`reviewer ext0417acc 2026-11-17T09:47:15 replay dialog3_intro (~7 min)` ⇒ `parts[1]='ext0417acc'` → `int()` 抛异常
- `stab_arms.py`：`module: ext\npid: %d\nstarted: …\nhost: …`（**多行**）⇒ `parts[1]='ext'` → `int()` 抛异常

**旧实现**（`HEAD` 版本）把「锁文件存在但 pid 解析不出」当作「**没有锁**」⇒ `acquire_lock` 直接 `open(LOCK,'w')` **静默覆盖 reviewer 的锁**。实测（反证组，`ast` 取函数后 `exec` 到临时目录）：

```
OLD lock_owner() -> None
OLD acquire_lock OVERWROTE foreign lock: True
 before: 'reviewer ext0417acc 2026-11-17T09:47:15 some desc'
 after : 'app 8968 2026-11-17 20:39:15 t\n'
```

🔴 **这正是两条受害臂的机制**：App 以为拿到了锁（`waited_s=0.0`、无排队记录），实际与 reviewer 的 CUDA 作业**同机并发**⇒ 合成变慢；同时 reviewer 的 `finally` 又把 App 的锁删掉 ⇒ 计时作废。**「变慢」与「锁丢」是同一个根因的两个表现**。

### 5.2 修法（**验收工具，非产品代码**）

`results/app/_app588_sp4_acceptance.py`（**唯一改动文件**）：

| 位置 | 改法 |
|---|---|
| `lock_owner()` | 锁文件**存在**但 pid 不可解析 ⇒ 返回 `{'pid': None, 'unparsed': True, …}`（**不再返回 None**）⇒ 区分「没有锁」与「锁不可解析」 |
| `acquire_lock()` | ① `unparsed` ⇒ **保守等待**（fail-closed，**绝不覆盖**）；② 取锁改 **`os.open(O_CREAT|O_EXCL)` 原子创建**，消除「读时无锁→写时他人锁已现」的 TOCTOU 覆盖窗口 |
| `release_lock()` | **只删自己 pid 的锁**（原已如此）；放锁时读到他人锁 ⇒ **原样记进 `lock_content_at_release`**（⇒ 下次能直接指认是谁的锁） |

### 5.3 修后行为验证（**正例 + 反例**全过）

| # | 用例 | 结果 |
|---|---|---|
| 1 | reviewer 格式锁在场 ⇒ `acquire_lock` 必须**超时抛错**且**锁内容一字未改** | ✅ 抛「等锁超时 1 s（锁内容不可解析…）」，锁内容逐字节未变 |
| 2 | 无锁 ⇒ 自取自放 | ✅ `acquired=True`，放锁后锁文件消失 |
| 3 | 他人锁在场 ⇒ `release_lock` **不得删**、且**记下他人锁原文** | ✅ 锁仍在且内容逐字节完好；`lock_content_at_release='reviewer ext0417acc … replay dialog3_intro (~7 min)'` |
| 4 | 自有锁 ⇒ 放锁删掉 | ✅ 锁文件消失 |
| 5 | 锁**已被人删** ⇒ 放锁时读到 `None` | ✅ `lock_content_at_release=None`（**如实记「锁已被别人删掉」**） |

> 全部为**纯 CPU 静态/逻辑验证**（`ast` 取函数 + `exec` 到临时目录）⇒ **未加载模型、未占 GPU/NPU、未碰 MACHINE_LOCK**（本轮全程 `MACHINE_LOCK` **不存在**）。

---

## 6. 本轮落盘 / 改动清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `results/app/_app588_sp4_acceptance.py` | **改** | 锁获取 fail-closed ＋ 原子创建 ＋ 放锁记他人锁原文（**验收工具**；**零产品代码改动**） |
| `results/app/app591_app215_ext_contention_forensics.json` | **新增** | 本模块自有取证证据（5 441 B） |
| `status/app/STATUS_APP_sec215_detail_20261117.md` | **新增** | 本 companion |
| `status/app/STATUS_APP.md` | **改** | 头部「更新时间」一行（`last_ack` **不变**，仍 APP-115）＋ 追加 §215 标题行 ＋ 指针行 |
| `results/app/app591_app115_ext_contention_forensics.json` | **不提交** | 死会话产物：其**锚点口径**已在本轮 §2 复核并沿用（±1–3 s），但其「三段会话」中**第三段的日期依据不成立**（见 §3.4）⇒ **不代提交**，避免把未复核的日期口径带进仓库；本模块自有证据另立 `app591_app215_*.json` |
| `status/app/CORRECTIONS_APP.md` | 🚫 **未改** | reviewer 独占文件（只读）；开工＝收尾 SHA 逐字一致 |

---

## 7. 结论与后续（**本条需等 reviewer 复核**）

🟢 **可结**：§214 的「094715 臂的争用源未定位」**已闭合**（EXT replay 作业 ＋ App 侧 sidecar 独立佐证）；「锁丢失」根因**已定位**（reviewer 脚本无条件删锁）；验收 harness 的 **fail-open 静默覆盖**缺陷**已修**并过反证组。

🔴 **仍未结（沿用，不新增）**：
1. **reviewer 侧无条件删锁**（`Remove-Item $lock`）**不在本模块可写范围** ⇒ **未改**（只取证、不越界）⇒ 建议 reviewer 把 4 个 ps1 的 `finally` 改成「只删内容匹配自己 id 的锁」。
2. **跨模块时序纪律**：reviewer 的作业与本模块的计时臂**同机并发** ⇒ 本模块后续计时臂**必须持锁且独占机器**（锁只防「同时写锁」，**防不住 reviewer 那种「先写锁后删锁」**）。
3. §214 未结项其余 3 条不变：就绪 98.0 s 待复核／英文臂仍未摸到 1.6–1.7×／lag 末值 3.665 s 未回落 <2 s。
4. 沿用未变：10 个带 APP-086·2a 缺陷包作废还是标注／完整版 v2.5 何时打／EXT 换嵌通知／目标机 SHA256 对账（**192.168.2.206**）／冷启动臂 `ov_cache` 是否可清理／**sp5 zip 待用户通知**。

🚫 **本轮纪律**：未打包／零客户包写入／零产品代码改动／未改纠偏文件／未跑推理／未占设备／未调 MiniMax／未通知用户／未动目标机·B 机／未吞他模块改动。
