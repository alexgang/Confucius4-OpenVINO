# §214 执行 **APP-115**（last_ack=APP-115，2026-11-17 14:2x）｜🔴 **§1 两条中文热臂的计时判为无效（`timing_valid=false`，v2 文件）**｜🔴 **撤回 §213⑨-3 的归因**｜🟢 **§2 持锁重跑一条干净中文热臂：PASS（丢句 0 / max 1.6972 / synth_rtf P90 0.6215 / 锁全程未被抢）**｜🟢 **§3 ≥1.6× 共 46 句（作废臂的 26 句不作数）**｜**未改产品代码／未重打包／未打 zip**

> 本文件是 `status/app/STATUS_APP.md` **§214 的 companion 正文**（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
> 纠偏来源：`status/app/CORRECTIONS_APP.md` **§APP-115（2026-11-17 12:59）**（reviewer 独占写入，本模块**只读**）。

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| APP-115 §3.3-1（两臂计时作废） | ✅ **已完成** —— 094715 / 100823 另写 `_v2.json`，`timing_valid=false` ＋ 原因；**原 json 逐字节未动** |
| APP-115 §3.3-2（持锁重跑一条干净中文臂） | ✅ **已完成** —— run `20261117-140853`，`timing_valid=true`，判定项全 PASS（n_fail=0） |
| APP-115 §3.3-3（报 lag + ≥1.6× 并与 APP-113 zh 对比） | ✅ **已完成** —— 见 §4 对比表 |
| APP-115 §3.3-4（不改代码／不重打包／不打 zip） | ✅ **已完成** —— 本节**零产品代码改动**、零客户包写入、**零 zip**；冷启动臂挪开的 `ov_cache` 副本**原样保留** |
| 撤回项 | 🔴 **撤回 §213⑨-3 的归因**（lag 103.6 s / 22.8 s 属**作废臂**的数字 ⇒ 不是 1.70× 上限造成的，也不是「用户听感判断」） |

---

## 1. APP-115 原文要求 ↔ 本轮落地对照

| reviewer 要求（§3.3） | 本轮落地 | 证据 |
|---|---|---|
| ① 094715 / 100823 两份验收 json 补写 `timing_valid=false`，原因「锁在运行中丢失 + synth_rtf P90 >1.1」（旧文件保留，另写 v2 也可以） | ✅ 另写 v2（原件零改动） | §2 |
| ② STATUS §213 的中文臂 lag **103.6 / 22.8 标成无效** | ✅ 在活文档 §213 指针行下加勘误行；本节 §3 写明「撤回 §213⑨-3 的归因」 | §3 |
| ③ 持锁重跑一条**中文目标热臂**（sp5、10 分钟、并行加载开启、run 号不覆盖） | ✅ run `20261117-140853`，sp5 包，600 s 素材，`--parallel on`，产物名带 run 号 | §4 |
| ④ 验收 json 加**两项报告项**（不是新闸门）：放锁时锁内容是否还是本作业；synth_rtf 中位和 P90 | ✅ 两项都进 `checks`（`report_only=true` ⇒ **不进 n_fail**）＋ `required_report` ＋ `reports` | §4.3 |
| ⑤ 判定：丢句 0、max ≤1.70、RTF P90 ≤0.75 时 `timing_valid=true`；锁又丢了或 RTF 又异常就查是谁动了锁，把结果写进 STATUS，不要猜 | ✅ 本臂三条全满足 ⇒ `timing_valid=true`；**锁全程未被抢、RTF 正常** ⇒ 「查是谁动了锁」分支未触发（但仍对**历史两次丢失**做了取证，见 §5） | §4.2／§4.3／§5 |
| ⑥ 报这一臂的 lag P50/P95/max/end 和 ≥1.6× 句数，和 APP-113 zh 对比 | ✅ 见 §4 对比表（参照臂 = `app588_sp4_acceptance_sp4_zh.json`，同一算子复算） | §4.4 |
| ⑦ 不改代码、不重打包、不打 zip（zip 等 reviewer 接受后再打） | ✅ 零产品代码改动、零客户包写入、零 zip | §6 |
| ⑧ 冷启动臂挪开的 ov_cache 副本先保留 | ✅ `ov_cache.app591_coldarm_20261117`（14.2 GB）**未删、未动** | §6 |

---

## 2. §3.3-1 落地：两条中文热臂的计时判为无效（v2 文件）

### 2.1 复核方法（与 reviewer 同一批 jsonl、同一算子 ⇒ 数值可直接对表）

逐句遥测 `*.tts_out.wav.tts.jsonl` → 取 `synth_rtf`（非 `rtf_ewma`）→ **线性插值分位数**。本轮用同一批 jsonl 复算，与 reviewer 的表**逐项一致**：

| 臂 | reviewer：中位 / P90 / RTF>1 | 本轮复算 | 一致？ |
|---|---|---|---|
| sp4 zh（APP-113 参照） | 0.544 / 0.610 / 1 | **0.5444 / 0.6088 / 1** | ✔ |
| sp5 cold_zh 093348 | 0.645 / 0.682 / 1 | **0.6448 / 0.6824 / 1** | ✔ |
| sp5 zh 094715 | 0.665 / **1.165** / 37 | **0.6650 / 1.1653 / 37** | ✔ |
| sp5 zh 100823 | 0.664 / **1.282** / 48 | **0.6644 / 1.2818 / 48** | ✔ |
| sp5 en 101859 | 0.571 / 0.645 / 0 | **0.5706 / 0.6455 / 1** | ✔（RTF>1 差 1：reviewer 按 >1 严判，本轮同口径复算为 1，见 §5 注） |

### 2.2 v2 文件（**原 json 逐字节保留**）

| 原 json（**未改**） | 字节 | SHA256（前 16） | v2 文件 | 字节 | SHA256（前 16） | `timing_valid` |
|---|---|---|---|---|---|---|
| `app591_acceptance_sp5_zh_run20261117-094715.json` | 20 664 | `ecf214f413e03b44` | `app591_acceptance_sp5_zh_run20261117-094715_v2.json` | 22 397 | `9b3b3c201ef26112` | **false** |
| `app591_acceptance_sp5_zh_run20261117-100823.json` | 22 411 | `ad284921a7711a22` | `app591_acceptance_sp5_zh_run20261117-100823_v2.json` | 24 831 | `295942b83fcd8727` | **false** |

v2 内新增/改写的字段（复用验收 harness 自己的 `finalize_app115()` / `pct()` ⇒ 与新臂同一套口径）：

- `timing_valid` = **false**
- `timing_invalid_reason` = 「锁在运行中丢失（放锁时锁内容=None，**不是本作业 PID**）；synth_rtf P90=1.165 > 0.75（合成 RTF 异常 ⇒ 机器被占） ⇒ **计时类结论不成立**（计数类结论不受影响）」
- `telemetry.synth_rtf_n / _p50 / _p90 / _max / _min / _n_gt_1 / _n_ge_0_75`
- `checks`/`reports` 新增**两项报告项**（`report_only=true`）：放锁时锁内容是否还是本作业 / synth_rtf 中位+P90
- `required_report`：`lock_content_at_release`、`lock_at_release_is_own_job`、`synth_rtf_*`、`lock_watch_events`
- `app115`（新增）：写明 correction 编号、原件 SHA256、原因串、reviewer 对表引用

对账索引：`results/app/app591_app115_invalid_arms_v2.json`（1 415 B／SHA256 `093e42547a83f8ad…`）。

**处置口径**：两臂的**计数类**结论（丢句 0、164==164+0、排队==补发、max≤1.70）**仍成立**（reviewer 亦持此口径：「计数类结论不受影响」）；**计时类**结论（lag、RTF、就绪时刻推导出的听感）**作废**。

---

## 3. 🔴 **撤回 §213⑨-3 的归因**（APP-115 §3.3-2②）

**§213 原文（companion `STATUS_APP_sec213_detail_20261117.md` L184）**：

> 3. 🔴 **中文臂积压未回落到 <2 s**（lag 末值 22.756 s）⇒ 「积压清空时刻」本臂**未产生**（已按 reviewer「lag 只报告」处理）⇒ 追赶速度是否够，属**用户听感判断**，本模块不自行下结论。

**撤回点（三条）**：

1. 🔴 **数字归属撤回**：lag **103.622 s** / 末值 **22.756 s** 取自 `app591_acceptance_sp5_zh_run20261117-100823.json`，该臂**计时无效**（锁在运行中丢失 ＋ synth_rtf P90=1.282）⇒ 这两个数字**不能当产品结论**（现已由 `_v2.json` 标 `timing_valid=false`）。
2. 🔴 **归因撤回**：把它们归为「**用户听感判断**」**不成立** —— reviewer 已算明：lag 从 33 s 涨到 103.6 s 是**机器被占**造成的（同一段代码、同一中文目标，冷启动臂 RTF 正常 0.682，两条热臂 P90 1.165/1.282）；**既不是 1.70× 上限造成的，也不是听感问题**。
3. 🟢 **替代口径（以 §4 的干净臂为准）**：积压**深**与**就绪慢**同步（TTS 就绪 **98.0 s**，就绪前排队 **23** 句 ⇒ 起步积压更深）；机器**干净**（synth_rtf P90 0.6215、锁全程未被抢）⇒ 属**启动时序（就绪慢）**问题，**不是语速上限的问题**。

> ⚠️ **§213 companion 正文逐字不动**（归档件 write-once）⇒ 只在活文档 §213 指针行下加勘误行 ＋ 本节撤回声明。

---

## 4. §3.3-2 落地：持锁重跑一条**干净中文热臂**

### 4.1 跑法（与 APP-114 臂同构，只加锁与报告项）

| 项 | 值 |
|---|---|
| 被测包 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5`（**sp5，零改动**） |
| 命令 | `<pkg>\python\python.exe <pkg>\app\live_caption_app.py --cli --file …\test_audio\clip_10min_0_600.wav --asr-device GPU.0 --mt-device NPU --tts-device CUDA --translate zh --tts on --tts-out …\_app591_spsp5_zh_run20261117-140853_tts_out.wav` |
| cwd / 并行 | cwd = 包目录；`--parallel on`（`LIVECAP_TTS_PARALLEL` 未设 ⇒ on） |
| 素材 | `clip_10min_0_600.wav`（19 200 044 B / 600 s，与前四臂同一素材） |
| run 号 | `20261117-140853`（**产物名带 run 号 ⇒ 不覆盖**；前缀因包名派生规则落在 `spsp5`，见下注） |
| 用时 / rc | elapsed **635.1 s**（≈10.6 min）｜rc **0**｜verdict **PASS**（n_fail=0） |
| 锁 | 内容 `app 12080 2026-11-17 14:08:53 app115-zh`；取得 **14:08:53**（等待 0.0 s）→ 放锁 **14:19:34**，**放锁时锁内容仍是本作业** |

> 注：本臂产物前缀为 `_app591_spsp5_zh_run20261117-140853`（harness 的 tag 派生把包名 `…_v1.0-sp5` 里的 `sp` 前缀替换后又拼上 `sp5` ⇒ `spsp5`）。**唯一性不受影响**（与前五臂 `_app591_sp5_zh_*` 不撞名），但命名不整齐，如实记录。

### 4.2 锁看门狗（**本轮新增的取证手段**，只读采样）

- 实现：验收 harness 内 `LockWatch`（daemon 线程，每 **10 s** 只读锁文件原文），只落**内容变动事件**（含时刻 + 当时原文）。
- 本臂结果：**采样 63 次／内容变动 1 次（＝初始内容）／**非本作业的内容变动 0 次**` ⇒ 🔴 **锁全程没人动过**（`lock_content_at_release` 也仍是本作业原文 ⇒ 互证）。
- 价值：若再发生「锁丢了」，看门狗会直接给出**谁动的**（锁原文里带模块名 + PID + 说明）。

### 4.3 判定结果（**判定项 11 条全 PASS** ＋ **报告项 3 条**）

| 判定项 | 结果 | detail |
|---|---|---|
| 丢句数（任何原因）= 0 | ✅ | worker丢弃=0 ＋ 溢出丢弃=0 ＋ worker失败丢弃=0 |
| 译文句数 == 进 TTS ＋ 丢弃 | ✅ | 164 == 164 + 0 |
| 就绪前排队全部补发 | ✅ | 23（排队）== 23（补发） |
| 倍率 max ≤ 1.70 | ✅ | **max=1.6972** p50=1.1549 p95=1.6659 |
| 退出码 0 | ✅ | rc=0 |
| 产出齐备 | ✅ | wav ＋ jsonl ＋ backlog csv |
| 逐句 jsonl 无重复 id | ✅ | 0 |
| TTS 就绪时刻已记录 | ✅ | **98.0 s**（CUDA 加载 80.0 s／预热 1.7 s；模型加载完成 94.0 s；ASR 22.5 s／MT 27.8 s） |
| ASR/TTS 并行生效 | ✅ | parallel=True（请求=on） |
| preflight（1.70× / 队列不按时间丢句） | ✅ | `SPEED_MAX=1.7`/`ZH_SPEED_MAX=1.7`/`ZH_SPEED_MIN=1.1`；`_TTS_QUEUE_OVERFLOW_S=None` |
| 队列行为探针 | ✅ | 300 s 过期仍保留 5 句、丢弃 0；worker 失败清空 5 句、计数 5 |
| **报告项①** 放锁时锁内容是否还是本作业 | 📋 | `app 12080 2026-11-17 14:08:53 app115-zh` ⇒ **仍是本作业=True**；看门狗 0 次外来变动 |
| **报告项②** synth_rtf 中位 / P90 | 📋 | **中位 0.5784／P90 0.6215**（max 3.6738；**RTF>1 仅 1 句**／共 164 句） |
| **报告项** 积压清空时刻 | 📋 | **174.2 s**（口径 `play_lag_s`）；末句播放滞后 3.665 s；lag max 75.529 s |

**`timing_valid` = true**（三条全满足）：① 运行窗口内 >100 MB 外部文件改写 **0** 个；② 锁**未丢**（放锁时仍是本作业）；③ synth_rtf **P90 0.6215 ≤ 0.75**。

> ⚠️ **报告项 ≠ 新闸门**：两项报告项 `report_only=true`，**不进 `n_fail`**（APP-085 §2／§209 的「§1 起不自建闸门」纪律不变）。`timing_valid` 是**报告字段**不是判定项。

### 4.4 §3.3-3：与 **APP-113 zh** 对比（参照臂 = sp4 臂，同一算子复算）

| 指标 | **APP-113 sp4 zh**（参照，`timing_valid=true`，放锁时锁内容仍是本作业） | **APP-115 sp5 zh 140853**（干净臂，`timing_valid=true`） | 读法 |
|---|---|---|---|
| lag p50 | 5.606 s | **6.6955 s** | 同档 |
| lag p95 | 26.6134 s | **69.3475 s** | 本臂更深 |
| lag max | 32.995 s | **75.529 s** | 本臂更深 |
| lag end | 3.53 s | **3.665 s** | 同档（**都没回落到 <2 s**） |
| 积压清空时刻 | 75.0 s | **174.2 s** | 本臂起步积压更深 |
| **≥1.6× 句数** | **0** | **46** | 🔴 关键差异 |
| speed max | 1.5332 | **1.6972**（未触 1.70 顶） | 本臂更高 |
| speed p50 | 1.1 | **1.1549** | |
| synth_rtf 中位 / P90 | 0.5444 / 0.6088（RTF>1: 1） | **0.5784 / 0.6215（RTF>1: 1）** | 🟢 **同档 ⇒ 机器干净** |
| TTS 就绪 | 37.6 s（CUDA 加载 23.3 s） | **98.0 s（CUDA 加载 80.0 s）** | 🔴 本臂就绪慢 |
| 就绪前排队 → 补发 | 10 → 10 | **23 → 23** | 本臂积压更深 |
| 丢句 | 0 | **0** | 一致 |

**读法（三条，均只依据上表字段）**：

1. 🟢 **机器是干净的**：两臂 synth_rtf 中位/P90 同档（0.544/0.609 vs 0.578/0.622）、RTF>1 都只有 1 句（首句含预热）⇒ 与作废两臂（P90 1.165 / 1.282、RTF>1 37/48 句）形成对照 ⇒ **上一轮的中文臂数字是被外部作业污染的，本臂才是产品基线**。
2. 🔴 **lag 更深的同步因素是「就绪慢」**：就绪 98.0 s（vs 37.6 s）⇒ 就绪前排队 23 句（vs 10）⇒ 起步积压更深 ⇒ lag 峰值 75.5 s（vs 33.0 s）、积压清空 174.2 s（vs 75.0 s）；**倍率上限 1.70 不产生排队**，故**不是** 1.70× 上限造成的。（这是**相关性**证据，未做对照实验 ⇒ 不写成因果结论。）
3. 🟢 **中文目标确实能进 1.6–1.7× 档**：本臂 **46 句 ≥1.6×**（max **1.6972**，未触 1.70 顶，n≥1.7=0），抽听样本 3 段真实倍率 **1.6972 / 1.676 / 1.6713**（`fell_back_to_top_speed=false` ⇒ 真命中目标档，不是回落取最高速）⇒ **§213 用作废臂得出的「中文臂 26 句 ≥1.6×」不再作为结论**，以本臂 **46 句**为准。

> 🔴 **待办（未结）**：本臂 TTS 就绪 **98.0 s**（CUDA 加载 80.0 s）明显高于前几臂（34.3 s / 37.6 s / 61.2 s）⇒ 是否为**一次性冷文件缓存**（跑前做过大目录扫描）**未证实** ⇒ 需要 reviewer 裁定是否复跑一条对照臂（**本轮不自行复跑**：APP-115 §3.3-2 只要求重跑**一条**）。

---

## 5. 「锁在运行中丢失」的取证（reviewer §3.3-2 的「查是谁动了锁」分支）

本臂**未复发**（锁全程未被抢、RTF 正常）⇒ 该分支未触发；但仍对**历史两次丢失**做了取证，结论如实记录（**不猜**）。

### 5.1 事实链

| 时刻 | 事件 | 证据 |
|---|---|---|
| 09:33:48–09:44:35 | 冷启动臂：放锁时锁内容**仍是本作业** | `app591_acceptance_sp5_cold_zh_run20261117-093348.json` → `lock_content_at_release='app 17044 … app114-zh'` |
| **09:47:15–09:57:32** | **zh 094715 臂**：放锁时锁内容 **None**（锁文件已不在） | 同上 json → `lock_content_at_release=None`；且 `synth_rtf` P90 **1.1653**、RTF>1 **37 句** |
| 09:57:32 | 下一臂（en 095732）取得锁，等待 **0.0 s** | `acquired_at=09:57:32`、`waited_s=0.0` ⇒ 锁当时**已空**，不是被排队等到的 |
| 09:57:32–10:07:47 | en 095732 臂：放锁时锁内容**仍是本作业**，RTF P90 0.6048 ⇒ 正常 | ✔ |
| **10:08:23–10:18:59** | **zh 100823 臂**：放锁时锁内容 **None**；synth_rtf P90 **1.2818**、RTF>1 **48 句** | 同上 json |
| **10:07:54–10:14:07** | 🔴 **EXT replay 作业在同机跑 CUDA TTS** | `live_dub_ext/.tmp/replay2_lad/` 内文件 mtime：10:07:54（`Intel Corporation/stats`）、10:08:50–10:09:53（`LiveDubEXT/clone_voices/*.wav`）、**10:14:07**（`Confucius4LiveCaption/tts_cuda_trace.log`） |
| **10:11:08–10:14:07** | 同上作业的 **CUDA 合成请求在跑**（REQ/DONE 逐条） | `…/replay2_lad/Confucius4LiveCaption/tts_cuda_trace.log`：`10:11:08 REQ rid=1` … `10:14:07 DONE rid=67`＋`10:14:07 REQ rid=68`（**无 DONE ⇒ 10:14:07 被中断**） |
| 10:18:59 | 下一臂（en 101859）取得锁，等待 **0.0 s**；该臂 RTF P90 0.6455 ⇒ 正常 | ✔ |

⇒ **100823 臂的争用源已被实物证据锁定**：EXT replay 作业的**自产 CUDA trace + 克隆音频落盘**时间**全部落在本臂窗口内**（10:08:23–10:18:59），且它在 10:14:07 被中断 ⇒ 与 reviewer 观察到的「RTF 从第 0 句就慢、持续到约 250 s」「开跑前有外部 PID 21744」**一致**。

### 5.2 锁文件是怎么没的（**已排除项 / 未证实项**）

- ✅ **不是 App 侧回收路径**：App 的 `acquire_lock` 只在「持有者 PID **确认已死**」时把锁改名为 `MACHINE_LOCK.stale.<ts>` ⇒ `shared/` 下**没有任何 `MACHINE_LOCK.stale.*`**（只有 11-10～11-16 的 `.MACHINE_LOCK.released_*` 旧记录）⇒ 锁是被**直接删除或被覆盖**，不是改名回收。
- ✅ **不是 EXT 模块的规范锁实现**：`live_dub_ext/tools/machine_lock.py` 的 `probe_pid_alive()` **判活正确**（`code.value == STILL_ACTIVE`＝259 ⇒ 活；另加 psutil 二次确认）⇒ 它**不会**误判我们的活 PID 而抢锁；且它的释放路径只删**自己创建**的锁。
- ⚠️ **未证实**：实际动锁者是 **reviewer 侧自带的临时锁写入器**——hy_bench 模块在 11:20 记录到的锁内容格式是 `ext 0418ab 2026-11-17T11:19:00 A/B v0.4.17 vs v0.4.18 replay max_spk=2 (~13 min)`，与 `tools/machine_lock.py` 的 `模块 PID YYYY-MM-DD HH:MM:SS` **格式不同** ⇒ **另一套实现**；其代码不在本模块可读范围内 ⇒ **本轮不下结论**（不猜）。
- ⚠️ **094715 臂（09:47–09:57）的争用源未定位到写入证据**：已扫 `live_dub_ext/`（maxdepth 3）、`hy_bench/`（maxdepth 4）、`qwen3tts_eval/`、`%LOCALAPPDATA%\Confucius4LiveCaption`（maxdepth 2）在 09:40–10:00 窗口内**均无文件写入** ⇒ 只确认「机器被占 + 锁文件消失」两个事实，**未确认动锁者**。

> ⇒ **给 reviewer 的可执行结论**：① 本轮干净臂证明**在无外部作业时锁机制可用**（看门狗 0 次外来变动）；② **EXT/reviewer 的 replay 类作业与 App 计时臂会争 GPU**，且其锁写法与 App 不同 ⇒ 建议二选一：reviewer 侧 replay 作业**不要与 App 计时臂同时跑**，或统一走 `shared/MACHINE_LOCK`（App 侧已加看门狗取证，可直接看到谁动的）。

---

## 6. 纪律与本轮未结项

**本轮已守**：

- 🔴 **零产品代码改动**（`live_caption/` tracked 改动数 = 0）；改动只在**验收 harness**（`results/app/_app588_sp4_acceptance.py`）与**一次性脚本**（`results/app/_app115_mark_invalid_arms.py`）⇒ 属 App 侧验收工具，不是产品逻辑。
- 🔴 **零客户包写入**（sp5 包内文件一字未动）；**未重打包**、**未打 zip**（sp4 / sp5 仍**均无 zip**；`shared/specialmvp/` 下仍只有 sp1 的 zip 14 244 490 059 B）。
- 🔴 **未改** `status/app/CORRECTIONS_APP.md`（reviewer 独占文件，只读；本轮开工＝收尾 SHA 一致 ⇒ 见 §6.2）。
- 🔴 **冷启动臂挪开的 `ov_cache` 副本保留**（`%LOCALAPPDATA%\Confucius4LiveCaption\ov_cache.app591_coldarm_20261117`，14.2 GB，**未删可回滚**）。
- 🔴 **未调 MiniMax**（质量判定仍归 reviewer）；**未跑**「≥1.7× / 听感」自评结论。
- 🔴 **未吞他模块改动**：本轮只 `git add` App 侧文件（验收脚本 ＋ 结果 json/jsonl/csv/log ＋ `status/app/STATUS_APP.md` ＋ 本 companion）；**绝不提交** `status/app/CORRECTIONS_APP.md`（它有 reviewer 自己的未提交追加）。

### 6.1 本轮未结项（**单列，不并入 PASS**）

1. 🔴 **TTS 就绪 98.0 s**（CUDA 加载 80.0 s）vs 前几臂 34.3/37.6/61.2 s ⇒ 是否一次性（冷文件缓存）**未证实** ⇒ 待 reviewer 裁定是否复跑一条对照臂。
2. 🔴 **英文臂仍未摸到 1.6–1.7×**（沿用 §213⑨-1：en 101859 max 1.2866×、≥1.6× **0** 句）⇒ 本轮未处理。
3. 🔴 **lag 末值 3.665 s 未回落到 <2 s**（两臂同档）⇒ 属**启动时序**问题（就绪慢⇒起步积压深），非语速上限问题；**未做对照实验**。
4. 🔴 **094715 臂的争用源/动锁者未定位**（见 §5.2）。
5. 🔴 **10 个带 APP-086·2a 缺陷包**（作废还是标注）、**完整版 v2.5 何时打**、**EXT 换嵌通知**、**目标机 SHA256 对账（.206，需开机＋凭据）**、**CUDA TTS 音质待回转写**、**冷启动臂挪开的 ov_cache 是否可清理** —— 均沿用未结（不在 APP-115 范围）。

### 6.2 本轮产物清单（文件数／字节／SHA256）

| 产物 | 字节 | SHA256 |
|---|---|---|
| `results/app/app591_acceptance_spsp5_zh_run20261117-140853.json` | 25 555 | `d27635a808d31be99819a8510e070cc02262cf51681e79188cd38439e2646e4a` |
| `results/app/_app591_spsp5_zh_run20261117-140853_tts_out.wav.tts.jsonl` | 256 726 | `cef54e4aa5e6bba80d9a48adbddc8c8c56d3b78b39d3101f47cc28efa9841c5d` |
| `results/app/_app591_spsp5_zh_run20261117-140853.log` | 285 482 | `aedf1a8a9520995f37a87ac0fbaea9d8c8587437f87438359a487bcd8e26e94b` |
| `results/app/_app591_spsp5_zh_run20261117-140853_tts_out.wav` | 27 934 604 | （见 json `artifacts`） |
| `results/app/_app591_spsp5_zh_run20261117-140853_tts_out.wav.backlog_curve.csv` | 17 910 | （见 json `artifacts`） |
| `results/app/app591_acceptance_sp5_zh_run20261117-094715_v2.json` | 22 397 | `9b3b3c201ef2611207a66883845cb421c64feadeaa96f0d9a4a7671e80b2f3b7` |
| `results/app/app591_acceptance_sp5_zh_run20261117-100823_v2.json` | 24 831 | `295942b83fcd87270ea3cdb286bf94c33364d2cb8175d9ca1e91c59911be26f8` |
| `results/app/app591_app115_invalid_arms_v2.json` | 1 415 | `093e42547a83f8add53d7745f6e7a95273e47e32bceea6761838038b15f9cc42` |
| `results/app/_app591_fast_samples/_app591_spsp5_zh_run20261117-140853_fast_id{15,14,28}_speed{1_70,1_68,1_67}.wav` | 23 084 / 200 204 / 51 884 | `421c1ac3852f85b5…` / `9b5c4711e019b10e…` / `2409f9714c2b65f1…` |

**抽听样本真实倍率**：id15 = **1.6972×**、id14 = **1.676×**、id28 = **1.6713×**（文件名与 `speed` 字段一致）。

### 6.3 本轮改动清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `results/app/_app588_sp4_acceptance.py` | **改** | 加两项报告项（放锁时锁内容 / synth_rtf 中位+P90）＋ `timing_valid` 判定（锁未丢 ＋ RTF P90≤0.75）＋ `LockWatch` 锁看门狗 ＋ `--lock-note` 参数（**验收工具，非产品代码**） |
| `results/app/_app115_mark_invalid_arms.py` | **新增** | 生成两臂 v2（复用 harness 的 `finalize_app115()`/`pct()`） |
| `status/app/STATUS_APP_sec214_detail_20261117.md` | **新增** | 本 companion |
| `status/app/STATUS_APP.md` | **改** | 头部 `last_ack` → APP-115 ＋ 更新时间；§213 指针行下加勘误行；追加 §214 标题行 ＋ 指针行 |
| `results/app/app591_acceptance_*_v2.json` ＋ 新臂 json/jsonl/csv/log ＋ 抽听样本 | **新增** | 证据 |
| `status/app/CORRECTIONS_APP.md` | 🚫 **未改** | reviewer 独占文件（只读） |
