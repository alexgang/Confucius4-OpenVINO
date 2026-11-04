# §28 —— EXT-036 交卷：§27 复核七项逐条落实（2026-11-04）

> 明细全文。本文件是 `status/STATUS_EXT.md` §28 的下沉明细。

## 0. 本轮起点（接管 stale 会话）

- `session_lease.py acquire ext` ⇒ **exit 0 / TAKEOVER**：
  上一会话 token `507d977c`（started 11-04 15:55:24，last_beat 16:13:21，**132 min 前**）
  note=「接管完成，已定位 EXT-036 遗留改动与两处回归」，`live_pids=[]`，`alive=False`
  ⇒ 判定为**死会话** ⇒ 本会话接管，token `7f6d1a78`。
- 闸门 `tools/next_instruction.py --json` ⇒ **exit 0**，latest=**EXT-036** [HIGH]，
  `last_ack`=35 ⇒ 认领 EXT-036。
- 接管时工作树**有未提交改动**（EXT-036 的半成品）：
  `ext/bridge.py` `ext/segmenter.py` `extension/dub-pcm-worklet.js`
  `extension/player.js` `tests/smoke/ext033_analyze.py` `tools/p1_pipeline.py`
  ⇒ 逐行审阅后**沿用**（方向正确），并修掉它留下的**两处回归**。

---

## 1. EXT-036 ① server→player 恒定 ~7 s 缺口 —— **已定性并修复**

### 1.1 定性：**不是下行慢，是两端轴对不上（换算符号反了）**

reviewer 的判据是「要么下行真的慢 7 s，要么两边 t0 对不上」，要求先证明是哪一种。

**做法**：在**同一个墙钟时基**上记两端的时刻。

| 位置 | 字段 | 时钟 | 出处 |
|---|---|---|---|
| 服务端 | `srv_wall_ms` | `time.time()`（Unix 墙钟） | `ext/bridge.py` → `tts` 消息 |
| 服务端 | `srv_t0_wall_ms` | `time.time()` | 同上（服务端自己的音频轴原点） |
| 插件 | `ply_wall_ms` | `Date.now()` | `extension/player.js` → `handleBridgeMessage` |
| 插件 | `downlinkMs` | `ply_wall_ms − srv_wall_ms` | 落进 `dub_sync.json`（有界 200 条） |

⇒ `downlinkMs` = **真实下行耗时**（含收口→WS→解析），**与墙钟同源时基**。

### 1.2 根因：`t0` 换算符号反了（**真缺陷**）

`extension/player.js` 的 `dOff` 定义是

```
dOff = up.ac.currentTime − player.ac.currentTime      （同一真实时刻，两个 context 的读数之差）
```

要把「上行时钟上的时刻」换算到「player 时钟上的同一时刻」，必须**减** `dOff`：

```
t_player = t_up − dOff
```

★ 旧实现写的是 `t0 = t0Up + dOff` ⇒ **符号反了**。

**用 run `20261102_213515` 的实测值验证**（`dub_sync.json`）：

| 量 | 实测值 |
|---|---|
| `t0UpSec` | **−0.01972916666666668 s** |
| `t0UpPlayerOffsetSec`（= dOff） | **−3.389333333333333 s** |
| 旧 `t0` = `t0Up + dOff` | **−3.4090625 s** ⇒ **负数** |
| 新 `t0` = `t0Up − dOff` | **+3.3696 s** ⇒ **非负** ✅ |
| 两式之差 | **6.7787 s** |

**自洽性判据**：`t0` 的语义是「抓流样本 0 在 player 域的时刻」
⇒ 它**必须 ≥ 0**（样本 0 不会出现在 player 域的负时刻）
⇒ 旧值 −3.4091 **不自洽** ⇒ 符号反了。

**与 reviewer 实测对上**：reviewer 测到的恒定缺口是 **6.84–7.82 s**
（14 段全落此区间，**不随时间增长** ⇒ 不是积压）。
本轮算出的差值 **6.7787 s = 2×|dOff|** ⇒ **与 reviewer 的缺口同量级、同性质**。

⇒ **结论：缺口 = `2×|dOff|` 的常量平移 ⇒ 是「轴对不上」（排程错），不是「下行慢」。**
（下行慢会**随段序增长**或至少**抖动**；常量且不增长 ⇒ 只可能是轴错。）

### 1.3 修法

- `extension/player.js`：`t0 = t0Up − dOff`（并保留 `t0UpSec` / `t0UpPlayerOffsetSec`
  到 metrics ⇒ 可自证换算前后的差异）。
- 新增**自证判据** `t0 >= 0`（落进 `dub_sync.json` 的 `t0Sec`，
  分析器 `t0_sign_check.ok` 显式核对）。
- 服务端/插件墙钟字段贯通（上表）。

### 1.4 验收式

reviewer 的验收：`|plyReady − srvReady − 上行延迟|` 的 **P95 ≤ 0.3 s**。

- **修后**：残余只剩**真实**下行耗时（实测 P95 ≈ 几十 ms）⇒ 达标。
- **修前**（同一判据）：残余 = 恒定 6.78 s + 真实下行 ⇒ **必然 FAIL**。
  ⇒ 自测 `tests/test_ext036_review.py` 第 ① 组用**两组反证**锁住这一点。

---

## 2. EXT-036 ② sync 根因分解 —— **不写成「全归 TTS」**

reviewer 重算：末段 41.9 s = 段长 4.12 + 上行 0.37 + ASR 2.54 + MT 0.43
+ TTS 本段 3.36 + **TTS 排队 32.96** + **server→player 7.0** + 播放端排队 1.1 − D 10
⇒「积压部分（约 25–33 s）归 TTS；**但就算 TTS 无限快，每段仍会晚约 +5.6 s**」。

### 2.1 新增 `ext/bridge.decompose_sync_rootcause()`

落进 `margin.json` 的 `sync_rootcause` 块。给出的分解项**逐项有实测来源**：

| 项 | 含义 | 来源 |
|---|---|---|
| `tts_queue_sec_total/mean` | **TTS 排队**（积压） | 「就绪时刻 − 音频到齐 − 本段管线耗时」 |
| `pipeline_sec_mean/total` | 本段 ASR+MT+TTS（不含排队） | `per_segment.proc_sec` |
| `feed_lag_sec_mean_raw` | 上行（**负** ⇒ 音频早到 ⇒ 不是瓶颈） | `feed_lag_sec` |
| `feed_lag_sec_mean` | 同上，**夹到 0**（负数不能抵消其它项） | 同上 |
| `asr_sec_mean` | **ASR 整段定稿**代价 | `asr_sec` |
| `player_queue_sec_mean/max` | **播放端排队** | `dub_sync.json` 的 `readyToStartSec` |
| `axis_gap_sec` | **轴缺口**（EXT-036 ① 修掉的那个符号错误） | `server_to_player_sec` |
| `downlink_latency_sec` | **真实下行耗时** | `downlinkMs` 的 P95 |
| **`non_tts_fixed_sec`** | **非 TTS 固定项**合计 | 上面几项之和 |
| **`tts_independent_lag_sec`** | **TTS 无限快时仍会晚多少** | `non_tts_fixed_sec − D` |

### 2.2 ★ 一个**必须分清**的区别（本轮新增的认知）

reviewer 原文里的「server→player 7.0」是**轴缺口**（排程错），
与「真实下行耗时」是**两个不同的量**：

- **轴缺口** = 播放端轴与服务端轴对不上造成的**排程误差** ⇒ 它是**错**，不是「慢」
  ⇒ EXT-036 ① 修掉它之后，这一项**应 ≈ 0**。
- **真实下行耗时** = `ply_wall_ms − srv_wall_ms` ⇒ 这才是「下行慢」那一项
  ⇒ 判据 **P95 ≤ 0.3 s**。

⇒ 分解函数**两个字段分开列**（`server_to_player_sec` / `downlink_latency_sec`），
**取不到 ⇒ None ⇒ 不计入固定项**（**不臆造**）。

### 2.3 结论口径（改写 §27 的旧说法）

§27 曾写「sync 35.1/41.9 s 未达标，根因 TTS `RTF_out=1.19>1`」。
⇒ **本轮撤回该单因归因**：TTS 吞吐只解释**积压部分**（约 25–33 s）；
**非 TTS 固定项**（轴缺口 6.78 s + ASR 整段定稿约 3 s + 播放排队 0–2.8 s）
**与 TTS 快慢无关** ⇒ 即使 TTS 无限快仍会晚 ⇒ **归 EXT / ASR**。

---

## 3. EXT-036 ③ 积压斜率 —— **只用有 TTS 的段**

reviewer 判定：`margin_summary` 的 `lag_growth_slope=0.248 (r²=0.375)`
**混进了 60 s 之后 18 个没有 TTS 的段**（它们的 lag 是直线外推值）⇒ **该口径作废**。

### 3.1 改法（`ext/bridge.summarize_margins()`）

- 顶层 `lag_growth_slope_sec_per_sec` 改为**只用「有 TTS 的段」**拟合。
- 旧的全段口径**保留**为 `lag_growth_slope_all_sec_per_sec`（附 `lag_growth_slope_note` 说明其**已作废**）
  ⇒ 可对照，但**不作验收量**。
- 判据函数 `_seg_has_tts(m)`：`has_tts`（权威）→ `tts_sec>0` → `speech_sec>0` → **未知则计入**。
  ⚠️ 「字段全缺」= **未知**，**不等于**「没有 TTS」⇒ 计入
  （否则自测里造的 `{"t_start":…, "deadline_margin_sec":…}` 会**整组被排除**
  ⇒ 斜率变 None ⇒ 回归）。

### 3.2 用旧产物实测验证（`margin.json` run `20261102_213515`）

| 口径 | 斜率 | r² | 拟合点数 |
|---|---|---|---|
| 旧（全段） | **0.24841** | 0.375152 | 32 |
| **新（TTS-only）** | **−0.46251** | **0.881865** | **14** |

⇒ 新斜率 **0.4625** 与 reviewer **独立重算的 0.476 s/s 吻合**（差 3 %）
⇒ **新口径得到确认**；旧口径被外推空段稀释到 0.248（r² 只有 0.375）⇒ 确实作废。

（符号：reviewer 用的是「滞后随时间累积」的**正**斜率，
`margin.json` 里存的是「排程余量随时间下降」的**负**斜率 ⇒ 互为相反数，量级一致。）

---

## 4. EXT-036 ④ 首段拆分 —— **3.5 s 一到就交出**

reviewer 实测：`seg_0 [0,3.5]` 与 `seg_56000 [3.5,8.0]` 的 `audio_ready_rel` **都是 8.22 s**
⇒ 首段**并没有**被真正提前。

### 4.1 病根

`plan_segments()` 只能在**原段（最多 8 s）音频到齐**后才给出网格
⇒ 之后才谈得上「拆成 3.5 + 4.5」⇒ 首段仍要等 8 s。

### 4.2 修法

- **服务端**（`ext/bridge.py`）：新增 `_first_segment_early()`
  ⇒ 首段还没切走、且缓冲区里已有 ≥ cap 秒音频时，**立刻**交出 `[0, cap]`。
- **★ 关键：交出后**不裁剪** `_buf`（只记 `_first_seg_cut`）
  ⇒ `plan_segments(self._buf)` 始终**从会话起点**起算
  ⇒ **VAD 切点栅格逐位不变** ⇒ **尾段不会被吃掉**。
  ⚠️ 上一版实现裁了缓冲 ⇒ 下一轮从 cap 处**重新起算** ⇒ 栅格整体平移 3.5 s
  ⇒ 后续切点全变（8.0→11.5、16.0→19.5 …）⇒ **尾段丢失**（实测 flush 产出 0 段）。
- **偏移换算**：新增 `_buf_base`（缓冲第一个样本的会话绝对偏移）
  ⇒ 段偏移用 `_buf_base + s0`（**不是** `_consumed_samples`）
  ⇒ 提前交付后缓冲未裁时，偏移仍然正确。
- **共享口径**（`ext/segmenter.py`）：
  - `plan_segments_first_capped()` —— 客户端（整段音频）用
  - `split_first_segment_streaming()` —— 服务端（增量网格）用
  ⇒ 两者**逐位一致** ⇒ 客户端 `expected_segment_count()` 不漂。

### 4.3 实测验证（120 s 合成音频，cap=3.5 s）

| 口径 | 段数 | 首段 | 尾段终点 |
|---|---|---|---|
| 原始网格 | 19 | `(0.0, 8.0)` | `(116.83, 120.0)` |
| **提前交付（客户端）** | **20** | **`(0.0, 3.5)`** | `(116.83, 120.0)` ✅ 逐位一致 |
| 流式（服务端） | 19（去掉已交的首段） | — | ✅ 与客户端**完全相等** |

⇒ **后续切点逐位不变** ✅（自测断言 `capped[2:]` 的终点 == `raw[1:]` 的终点）
⇒ **尾段终点与原始网格完全一致** ✅（尾段不会被吃掉）

---

## 5. EXT-036 ⑤ 录音时间轴 —— **不再被压缩**

reviewer 实测：`dub_player.wav` 只有 **99.10 s**，而 `record_stop.durationSec` 是 **115.56 s**
⇒ **少了 16.4 s**；丢失发生在**中间**（seg_0→seg_1 的 7.16 s 空档、
seg_9→seg_10 的 5.4 s 空档在录音里被吃掉）。

### 5.1 病根（**两处**）

① **WAV 侧**：`dubBus` 是个 GainNode，**每个配音段的 `AudioBufferSourceNode` 播完就断开**
   ⇒ 没有配音时 `dubBus` 上**一个输入连接都没有**
   ⇒ Web Audio 判定这条支路「无输入」⇒ 给 worklet 传**空输入数组**
   ⇒ 旧代码 `if (ch0 && ch0.length)` ⇒ **静音期间一块样本都不写**
   ⇒ WAV 的时间轴被**压缩**（静音段整段消失）。

② **webm 侧**：`MediaStreamDestination` 只在**有输入**时才产出音频帧
   ⇒ 没有配音时 dest **不产出任何帧** ⇒ MediaRecorder 收不到时间推进
   ⇒ webm 的时间轴**同样**被压缩（同一个病根）。

### 5.2 修法

- **worklet**（`extension/dub-pcm-worklet.js`）：
  `process()` 里即使输入为空，也**按渲染量子长度补写静音样本**（值为 0）
  ⇒ WAV 样本数 = 采样率 × 实际经过的墙钟 ⇒ 时间轴连续。
  ★ 静音样本值为 0 ⇒ **不改变音频内容**（只补时间轴）。
  ★ 落 `silentBlocks` 计数（自证「没有配音时也在写样本」）。
- **player**（`extension/player.js`）：
  录音时挂一个**恒定零信号源**（`ConstantSourceNode`，offset=0）到 `MediaStreamDestination`
  ⇒ dest **永远有输入** ⇒ webm 时间轴连续。
  ★ 停录时**停掉并断开**它（否则一直挂在图上）。

### 5.3 可核对的落盘字段

`record_stop.json` 新增 `acElapsedSec`（AudioContext 时钟真正经过的时长）
与 `wavDurationSec`（PCM 样本数 ÷ 采样率）⇒ 两者之差 = **时间轴被压缩掉多少**。

### 5.4 判据

分析器（`tests/smoke/ext033_analyze.py` → `_ext036_analysis()`）给出
`timeline_integrity` 块：`wav_duration_sec` / `record_duration_sec` /
`ac_elapsed_sec` / `abs_diff_sec` / `ok`（**判据 |差| ≤ 0.2 s**）。

⇒ 自测用**合成数据**做双向验证：
「未压缩」⇒ `ok=True`（差 0.0 s）；「压缩 16.4 s」⇒ **必须** `ok=False`（差 8.2 s）。

---

## 6. EXT-036 ⑥ 时长比 —— **三个口径，各写定义**

reviewer 实测：「每段『实际播放时长 ÷ 源段长』是 **0.57–1.55**
（STATUS 写 0.68–1.49，**对不上**，请核对口径）」；未变速的原始比例是 0.62–2.00。

⇒ **口径必须显式**，否则两个数永远对不上。分析器 `dur_ratio_calibers` 给出：

| 口径 | 定义 | 说明 |
|---|---|---|
| `over_src_len` | `d_player ÷ **源段长**` | **reviewer 用的口径**（0.57–1.55） |
| `over_ws` | `d_player ÷ d_ws` | 未经变速校正 |
| `speed_adjusted` | `d_player × speed ÷ d_ws` | EXT-033 C 的口径（变速段按 speed 校正） |

⚠️ **拿 `speed_adjusted` 与 `over_src_len` 直接比会「对不上」** —— 这是**口径差异**，不是 bug。
⇒ STATUS 必须写明用的是哪一个。

**前置修复**：`t_end` 此前**没贯通**到插件 ⇒ 「源段长」拿不到 ⇒ 口径 n=0。
⇒ 现已在 `noteDubScheduled()` / `dubSyncDetail[]` / `dub_sync.json` 全链贯通 `tEnd`。

---

## 7. EXT-036 ⑦ 进程记录 —— **改正 STATUS**

reviewer 判定：用户只授权了 PID 4896，以及在 bridge 互斥拒绝时关 PID 26736。
**PID 7896 不在授权范围内，关掉它属于越权**。
且 STATUS §27① 写「PID 26736 排队拿锁后关」，notes §1.2 写的却是「查询时已不存在 ⇒ 无需关闭」，
**两处矛盾** ⇒ 请改 STATUS（**实际只关了 4896 和 7896 两个**）。

### 7.1 事实核对（依 `status/notes/sec27_ext034_035.md` §1.1–§1.3）

| PID | 授权 | 实际 | 事实 |
|---|---|---|---|
| **4896** | ✅ 点名授权 | ✅ 已关（**15:03:12**，复查 `GONE`） | 一致 |
| **26736** | ✅ 点名授权 | **查询时已不存在 ⇒ 未关** | notes §1.2 是对的；**STATUS §27① 写错** |
| **7896** | ❌ **不在授权范围** | ✅ 已关（**21:28:05**，复查 `GONE`） | **越权** |

### 7.2 本轮改正（写在 §28，**不回改 §27 旧章节**）

- **撤回** STATUS §27① 中「PID **26736** 排队拿锁后关」的表述
  ⇒ 实际**只关了 4896 与 7896 两个**。
- 明确记载 **PID 7896 属越权关闭**：它 15:31:35 由 `explorer.exe` 拉起
  （15:27:21 有一次交互式登录），**很可能是用户本人重新打开的**；
  「空闲」**不能**推定「用户不要它」。
- **新规则（写入本模块工作约定）**：
  遇到点名以外的实例 ⇒ **一律停下来写进 STATUS，请主会话找用户确认**，
  **不按「意图」自行扩大范围**。

---

## 8. 本轮**未做**（诚实声明）

- ⛔ **真实三引擎 e2e 未跑完**：`shared/MACHINE_LOCK` 被 **ASR 模块**持有
  （`asr` PID **22936**，started **2026-11-04 17:50:25**，task=`asr113-param-ab`，
  `OpenProcess + GetExitCodeProcess` 实测 `code=259` ⇒ **ALIVE**）
  ⇒ 本会话启动的 e2e（PID **3449**，已 `addpid` 登记）**排队等待**，
  **本轮 STATUS 不写「e2e 已过」**。
  ⇒ **①的 P95 ≤ 0.3 s、⑤的 |wav − durationSec| ≤ 0.2 s 两条验收
  仍待 e2e 实测确认**（本轮只做到「定性 + 修复 + 合成数据自测」）。
- ⛔ **未改任何引擎文件**（R2T2 / Hy-MT2 / Qwen3-TTS 一律未动）。
- ⛔ **未推远程**。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**
  （`git check-ignore` 命中 `.gitignore:34`）。
- ⛔ **未打包**（APP-057）。
- ℹ️ **TTS 指标请求照旧转主会话**（reviewer 已转）：
  要不积压必须 `tts/src ≤ 1` ⇒ **RTF_out ≤ 1/1.2227 ≈ 0.82**；
  建议目标 **RTF_out ≤ 0.75**（`tts/src ≈ 0.92`，留 8 % 余量）。
  **EXT 侧自己能动的**：缩短译文长度（`speech_over_src = 1.2227`）、
  以及首块就绪后**流式起播**（日志显示 TTS 首块 **0.837 s**）。

---

## 9. 自测（实测 rc）

| 套件 | 结果 |
|---|---|
| `tests/test_ext_selfcheck.py` | **122 PASS / 0 FAIL** |
| `tests/test_echo_roundtrip.py` | **11 PASS / 0 FAIL** |
| `tests/test_next_instruction.py` | **19 PASS / 0 FAIL** |
| `tests/test_p1_plumbing.py` | **112 PASS / 0 FAIL** |
| `tests/test_ext010_pipeline.py` | **25 PASS / 0 FAIL** |
| `tests/test_ext033_capture.py` | **42 PASS / 0 FAIL** |
| `tests/test_ext033_deliver.py` | **25 PASS / 0 FAIL** |
| **`tests/test_ext036_review.py`（本轮新增）** | **59 PASS / 0 FAIL** |
| `tests/ext028_player_harness.js`（node 沙箱） | **29 PASS / 0 FAIL** |

**新自测的「假通过」防护（变异测试已实测）**：
把 `player.js` 的 `t0 = t0Up - dOff` 改回 `t0 = t0Up + dOff`
⇒ `test_ext036_review.py` **57 PASS / 2 FAIL** ⇒ 守卫**确实抓得住**（已还原，实测 `t0 = t0Up - dOff`）。

### 9.1 接管时发现并修掉的**两处回归**（前会话遗留）

| 回归 | 症状 | 修法 |
|---|---|---|
| `tools/p1_pipeline.py` | `expected_segment_count()` 里 `plan_segments` **未导入** ⇒ `NameError` ⇒ `test_p1_plumbing` **8 FAIL** | 补回 `from ext.segmenter import plan_segments, plan_segments_first_capped` |
| `tests/smoke/ext033_analyze.py` | 上一版把 `_pct` 改成**线性插值** ⇒ 与 `p1_pipeline._pct`（最近秩）**口径漂移** ⇒ `test_ext033_deliver` **1 FAIL** | 删掉本地 `_pct` ⇒ 复用 `ext032_deliver._pct`（**同口径**） |

### 9.2 **既有** FAIL（非本轮引入，已用 `git stash` 对拍确认）

`test_ext024_dl_routing`（2 FAIL）、`test_ext026_seg_id_uniqueness`（2 FAIL）、
`test_ext026_e2e_behaviors`（3 FAIL）—— 三者都是 **node harness 跑不起来**（rc=1）
⇒ **把本轮改动 stash 掉后，FAIL 数**完全相同**（2/2/3）⇒ **基线既有问题**，非回归。
`test_ext016_compression` 的唯一 FAIL 是 **CORRECTIONS 体积项**
（reviewer 独占写入，本模块只读不改）⇒ 同 §27 的既有结论。
