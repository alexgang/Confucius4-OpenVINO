# §29 —— EXT-036 补测：真实三引擎 e2e（①⑤ 两条验收实测确认）+ 客户端实测数据上报闭环

> 执行时间：2026-11-04 19:43 ~ 20:03（实测时间，非推算）
> 租约：EXT-030 模块租约 `token=7f986f16`（本轮新拿；接管前会话 token `7f6d1a78` 已死，TAKEOVER）
> 闸门：`tools/next_instruction.py --json` ⇒ **exit 1**（`already_executed`，latest=EXT-036，last_ack=36）
> ⇒ 本轮**不认领新编号**；`last_ack` **保持 EXT-036 不变**。
> ⇒ 但按 EXT-030 的 TAKEOVER 条款，从死会话的断点**继续**：
> 死会话遗留 e2e（PID 3449）已死、产物目录 `20261104_183902` **为空**（0 文件）、
> `shared/MACHINE_LOCK` 被 ASR 模块持有（PID 2188，`asr106-vad-gate-windows`）。

---

## 0. 接管时的事实认定（全部实测，非推断）

| 项 | 探测方式 | 结果 |
|---|---|---|
| ASR 锁持有者 PID 2188 | `OpenProcess(0x1000)` + `GetLastError` | **err=87**（`ERROR_INVALID_PARAMETER` ⇒ PID 不存在）⇒ **确认已死** |
| 同上（二次确认） | `psutil.pid_exists(2188)` | `False` |
| 同上（三次确认） | 本仓 `tools/machine_lock.py` | `模块=asr PID=2188 存活=False` |
| 死会话 e2e PID 3449 / 48136 | `OpenProcess` err=87 + `psutil` | **均不存在** ⇒ 确认已死 |
| 死会话遗留产物 | `ls .tmp/ext033_e2e/20261104_183902/` | **空目录（0 文件）** ⇒ 那轮 e2e **什么都没产出** |
| 当前有无引擎作业 | `psutil` 全进程扫 `r2t2/hy-mt/qwen/tts/asr/bridge/ext033` | **无**（唯一命中是系统 `BridgeCommunication.exe`，与本项目无关） |

⇒ 依铁律「探测失败一律视为存活」：本轮探测**成功**（err=87 = PID 确不存在，非权限不足）
⇒ 判定**确认已死** ⇒ 允许回收锁。
★ 回收动作由本仓 `tools/machine_lock.py` 的 `hold()` **自动**完成（实测日志
`[lock] 持有者 PID=2188 已确认死亡 ⇒ 回收锁并接管`），**未手工删** `shared/MACHINE_LOCK`。

---

## 1. ★ ①⑤ 两条验收 —— 实测确认（§28 时因锁被占用而未跑完）

### 轮次 A：`20261104_194608`（首轮补测）

* 真实三引擎（ASR=R2T2 / MT=Hy-MT2 / TTS=Qwen3-TTS），**engine_state=ready**
* 素材：英文 SPE 60 s（`confucius4-openvino/live_caption/test_en_60s.wav`）
* 抓流：**页面元素 WebAudio**（`createMediaElementSource` ⇒ 不碰系统声音）
* 录音：webm（560 392 B）+ WAV（7 867 436 B / 48 kHz / 3 933 696 样本 / 81.952 s）
* 收尾：已录 **77.9 s**（≥75 s ✅），静默 12.2 s，TTS 段 **8**
* 产物目录 `.tmp/ext033_e2e/20261104_194608/`：**11 个文件**

| 验收 | 判据 | 实测 | 结论 |
|---|---|---|---|
| **① 下行耗时 P95** | **≤ 0.3 s** | `downlinkMs` = [16,39,34,121,48,27,29,25,4,11] ms ⇒ **P50=27 / P95=121 / max=121 ms** | ✅ **0.121 s ≤ 0.3 s** |
| **⑤ 录音时间轴** | **\|wav − durationSec\| ≤ 0.2 s** | wav **81.952 s** vs `durationSec` 81.999 / `acElapsedSec` 81.941 ⇒ **差 0.011 s** | ✅ **0.011 s ≤ 0.2 s** |

⇒ **★ ① 的判据被实测回答**：`downlinkMs` 是 `Date.now() − srv_wall_ms`
（同一 Unix 墙钟时基）⇒ **真实下行耗时** P95 仅 **121 ms**（≪1 s）
⇒ 证实 §28 的结论：**7 s 缺口不是下行慢**，是**两端音频轴对不上**（排程错）。

### 轮次 B：`20261104_195911`（改完上报闭环后的**验证轮**，独立复现）

| 验收 | 判据 | 实测 | 结论 |
|---|---|---|---|
| ① 下行耗时 P95 | ≤ 0.3 s | **P50=22 / P95=35 / max=35 ms**（n=10） | ✅ |
| ⑤ 录音时间轴 | ≤ 0.2 s | wav **81.861 s** vs `acElapsedSec` 81.851 ⇒ **差 0.011 s** | ✅ |
| ① 自证 `t0 ≥ 0` | 必须 ≥0 | `t0Sec = 3.1696` | ✅ |
| 同步测量覆盖 | 全覆盖 | `n_detail 8 / n_tts_segments 8` ⇒ **coverage 1.0** | ✅ |

⇒ **两轮独立复现，①⑤ 均达标** ⇒ §28 的「⛔ 真实 e2e 未跑完」**解除**。

### ①⑤ 之外，本轮同时实测到的其余项（诚实记录，含未达标项）

| 项 | 轮次 A | 轮次 B | 判据 | 结论 |
|---|---|---|---|---|
| sync 有符号误差 P50/P95 | 5071 / **9087** ms | 4459 / **8727** ms | ≤300 ms | ❌ **未达标** |
| 开头静音 | 10.46 s | 10.19 s | ≤15 s | ✅ |
| 录音时长 | 81.952 s | 81.861 s | ≥75 s | ✅ |
| 段对齐（互相关） | 8/8 | 8/8 | 全对齐 | ✅ |
| ⑥ 时长比 `over_src_len`（**reviewer 口径**） | 0.4617–1.0586 | 0.4600–1.0774 | — | **与 reviewer 0.57–1.55 同量级但仍偏低** |
| ⑥ 时长比 `speed_adjusted` | 0.6939–1.3599 | 0.8180–1.3135 | — | 另一口径，**不可混比** |
| `RTF_out` | — | **0.8182** | ≤0.82 | ✅ **刚好达标**（reviewer 建议 ≤0.75） |

---

## 2. ★★ 补测**暴露**的真缺陷（本轮修掉）：客户端实测数据**从不上报服务端**

### 2.1 缺陷陈述

客户端**一直测得到**这三项，且都已落进 `dub_sync.json`：

* `ply_wall_ms − srv_wall_ms` = **真实下行耗时**
* `readyToStartSec` = **就绪→起播**（播放端排队）
* `t0UpPlayerOffsetSec` = **轴偏移**

⇒ 但它们**只留在插件本地** ⇒ **从不上报服务端**
⇒ `margin.json` 的 `sync_rootcause` 里：

```
server_to_player_sec   = null
downlink_latency_sec   = null
player_queue_sec_mean  = null
```

⇒ 「**非 TTS 固定项**」只加得上一部分 ⇒ **归因不完整**
（reviewer EXT-036 ② 要求的是**逐项分解**）。

### 2.2 更糟的一点：**假 0.0**

`non_tts_fixed_detail` 原实现把 `None` **强转成 `0.0`**：

```python
"axis_gap_sec": axis_gap or 0.0,        # axis_gap 可能是 None
"downlink_latency_sec": dlat or 0.0,    # dlat 可能是 None
```

⇒ 落盘后读起来像「**实测为零**」⇒ **假数据**（违反「没落盘的东西不能写成已交付」与
「不臆造」两条铁律）。

### 2.3 修法（**最小、范围可控**，不偏离现有架构）

| 侧 | 改动 | 文件 |
|---|---|---|
| 客户端 | 新增 `reportClientMetrics()`：把 `dubDownlinkMs`（逐段下行耗时）、`metrics.dubSyncDetail`（就绪→起播）、`metrics.t0UpPlayerOffsetSec`（轴偏移）打包成 `client_metrics` 消息发给服务端；**在 `requestMarginDump()` 落盘之前**发送 | `extension/player.js` |
| 服务端 | 新增 `Session.note_client_metrics()`（只收数值、负值视为无效、列表**有界 ≤200**）与 `Session.client_metrics_summary()`（**最近秩**分位，与既有 `_pct` 口径一致） | `ext/bridge.py` |
| 服务端 | 新增消息分支 `mtype == "client_metrics"` ⇒ 记到**生产者会话**（`_producer_session`，与 `per_segment` 同源） | `ext/bridge.py` |
| 服务端 | 新增 `_client_rootcause_kwargs()`：把客户端实测值喂进 `decompose_sync_rootcause`（下行耗时按 **P95/1000**；轴缺口取**绝对值**，因实测是有符号的 −3.19） | `ext/bridge.py` |
| 服务端 | ★ `non_tts_fixed_detail` 的 null **不再强转 0.0**；null 项**不计入**合计 ⇒ 合计是**下界**，并用 `non_tts_fixed_is_lower_bound` 标明；新增 `unmeasured` 列出哪些项没测到 | `ext/bridge.py` |
| 服务端 | `margin.json` 新增 `client_metrics` 键（独立落盘 ⇒ reviewer 可直接核对原始分位） | `ext/bridge.py` |

### 2.4 修后实测（轮次 B `20261104_195911` 的 `margin.json`）

```json
"client_metrics": {
  "n_downlink_samples": 11, "downlink_p50_ms": 22.0, "downlink_p95_ms": 35.0,
  "downlink_max_ms": 35.0,
  "n_player_queue_samples": 8, "player_queue_p50_sec": 0.005,
  "player_queue_p95_sec": 4.167, "player_queue_max_sec": 4.167,
  "t0_up_player_offset_sec": -3.1893333333333334
}
"sync_rootcause": {
  "server_to_player_sec": 3.189,      "downlink_latency_sec": 0.035,
  "player_queue_sec_mean": 1.038,     "player_queue_sec_max": 4.167,
  "non_tts_fixed_sec": 7.184,  "non_tts_fixed_is_lower_bound": false,
  "tts_independent_lag_sec": -2.816,  "rtf_out": 0.8182
}
"non_tts_fixed_detail": {
  "feed_lag_sec": 0.0, "asr_sec": 2.922, "player_queue_sec": 1.038,
  "axis_gap_sec": 3.189, "downlink_latency_sec": 0.035,
  "server_to_player_sec": 3.189, "unmeasured": []
}
```

⇒ **三项全部不再是 null**，`unmeasured: []`（全测到了）⇒
**「非 TTS 固定项」现在是完整分解**（不再是少算三项的下界）。

### 2.5 ★ 关键推论（归因变化）

`non_tts_fixed_sec = 7.184 s`（轮次 B）⇒ **TTS 无限快时每段仍会晚 7.184 − D(10) = −2.816 s**
⇒ 本轮 D=10 s **已足以吸收**非 TTS 固定项 ⇒
**残余滞后主要仍归 TTS 吞吐**（`RTF_out = 0.8182`）。

★ 与 §28 的差异**不是结论变了，是口径变了**：
§28 时 `player_queue_sec` / `axis_gap` / `downlink_latency` **三项恒 null**
⇒ §28 写下的 `non_tts_fixed_sec = 2.892`（**只含 ASR**）是**残缺**的，
本轮补测后**改为 7.184 s**（含播放排队 1.038 + 轴缺口 3.189 + 下行 0.035）。
⇒ **§28 ② 的「非 TTS 固定项」数值应更新为 7.184 s**（本节即为其修正依据）。

---

## 3. 自测（实测 rc）

**十套全 0 FAIL**：

| 套 | PASS/FAIL | 套 | PASS/FAIL |
|---|---|---|---|
| `test_ext_selfcheck` | 122 / 0 | `test_ext033_capture` | 42 / 0 |
| `test_echo_roundtrip` | 11 / 0 | `test_ext033_deliver` | 25 / 0 |
| `test_next_instruction` | 19 / 0 | `test_ext036_review` | 59 / 0 |
| `test_p1_plumbing` | 112 / 0 | **`test_ext036b_client_metrics`（新建）** | **39 / 0** |
| `test_ext010_pipeline` | 25 / 0 | `ext028_player_harness.js`（node） | 29 / 0 |

★ **新增自测** `tests/test_ext036b_client_metrics.py`（**39 项**）覆盖：
① 客户端确实上报（消息类型/字段/有界/取自实测变量/先报后 dump/未测到报 null）；
② 服务端确实收（消息分支/两个方法/落盘键/记到生产者会话/负值过滤/有界）；
③ 落盘不再是 null（**P95=121 ms 最近秩**/轴偏移**保留符号**/没报⇒None）；
④ ★ **核心守卫**：未实测项**不许**被写成 0（null 仍是 None + `unmeasured` 列出 +
合计只含已实测项 + 部分上报时标明是下界）；
⑤ 接线（下行按 P95/1000 传、轴缺口取绝对值、没报则**一个参数都不传**）。

### ★ 变异测试实测（证明守卫**抓得住**，不是假通过）

把 `non_tts_fixed_detail` 的 null 强转改回旧写法
（`"axis_gap_sec": axis_gap or 0.0` 等四处）⇒
**新自测 35 PASS / 4 FAIL** ⇒ **4 项如实 FAIL**
（④ A 的轴缺口/下行耗时/播放端排队三项 + ④ C 的未报两项）
⇒ **守卫确实有效** ⇒ **已还原**（实测 `grep '"axis_gap_sec": axis_gap,'` 命中，
自测回到 **39 PASS / 0 FAIL**）。

★ 另一次变异（把合计里的 `if _v is not None` 改成 `float(_v or 0.0)`）
⇒ 自测 **39 PASS / 0 FAIL** ⇒ **说明**该变异**数值上等价**（加 0 不改变和）
⇒ 真守卫在**明细字典**（null 的呈现）而不在合计公式 ⇒ 已据此把变异对准明细。

---

## 4. 产物清单（附文件数 / mtime / 字节数）

### 轮次 A `.tmp/ext033_e2e/20261104_194608/`（11 文件，mtime 2026-11-04 19:48–19:50）

| 文件 | 字节 | mtime |
|---|---|---|
| `dub_player.wav` | 7 867 436 | 11-04 19:48 |
| `dub_player.webm` | 560 392 | 11-04 19:48 |
| `margin.json` | 29 927 | 11-04 19:48 |
| `metrics.json` | 41 900 | 11-04 19:48 |
| `dub_sync.json` | 5 868 | 11-04 19:48 |
| `bridge.log` | 8 922 | 11-04 19:48 |
| `player.png` | 23 949 | 11-04 19:48 |
| `record_stop.json` | 273 | 11-04 19:48 |
| `ext033_compare.json` | 12 266 | 11-04 19:50 |
| `ext033_compare.md` | 3 259 | 11-04 19:50 |
| `audio_dump/`（目录） | — | 11-04 19:47 |

### 轮次 B `.tmp/ext033_e2e/20261104_195911/`（11 文件，mtime 2026-11-04 20:00–20:01）

| 文件 | 字节 | mtime |
|---|---|---|
| `dub_player.wav` | 7 858 732 | 11-04 20:01 |
| `dub_player.webm` | 546 720 | 11-04 20:01 |
| `margin.json` | 30 700 | 11-04 20:01 |
| `metrics.json` | 41 578 | 11-04 20:01 |
| `dub_sync.json` | 5 918 | 11-04 20:01 |
| `bridge.log` | 8 911 | 11-04 20:01 |
| `player.png` | 23 103 | 11-04 20:01 |
| `record_stop.json` | 286 | 11-04 20:01 |
| `ext033_compare.json` | 12 284 | 11-04 20:01 |
| `ext033_compare.md` | 3 250 | 11-04 20:01 |
| `audio_dump/`（目录） | — | 11-04 20:00 |

★ 两轮的**轮次摘要**：`summary_20261104_194608.json` / `summary_20261104_195911.json`
（各含 `rc`/`metrics_key`/`dub_sync`/`record_stop` 等原始字段）。

---

## 5. ⛔ 明确未做 / 不宣称

- ⛔ **未认领新 EXT 编号**（闸门 exit 1，`last_ack` 保持 **EXT-036**）。
- ⛔ **sync 有符号误差仍未达标**（P95 9087 / 8727 ms，判据 ≤300 ms）⇒
  **不写「同步已解决」**；本轮只把 ①⑤ 两条验收确认通过。
- ⛔ **时长比未解决**（`over_src_len` 0.46–1.08，reviewer 实测 0.57–1.55）
  ⇒ 口径已分列（`over_src_len`/`over_ws`/`speed_adjusted`），**数值差仍未追平**。
- ⛔ **`RTF_out = 0.8182`** 刚好 ≤0.82（reviewer 建议 ≤0.75）⇒
  **仍建议 TTS 模块继续提速**（转主会话）。
- ⛔ **未改任何引擎文件**（R2T2 / Hy-MT2 / Qwen3-TTS 一律未动）。
- ⛔ **未改其它模块文件**（改动全部落在 `live_dub_ext` 内）。
- ⛔ **未打包**（APP-057）/ ⛔ **未推远程**（本仓不推）。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**
  （`git check-ignore` 命中 `.gitignore`）。
- ℹ️ **EXT-028 仍待用户抽听**（V2.0 插件暂不放行）；**pyannote 旁路未接线**。

---

## 6. 对主会话的请求

1. **TTS 指标照旧转达 TTS 模块**：`RTF_out` 本轮实测 **0.8182**
   ⇒ 已**刚好**满足 ≤0.82（要不积压的门槛），但**未达** reviewer 建议的 ≤0.75
   ⇒ 建议目标仍为 **≤0.75**（留 8 % 余量）。
2. **ASR 侧**：`asr_sec_mean = 2.922 s`（整段定稿）⇒ 若要再压非 TTS 固定项，
   这是**第二大**的固定项（第一是轴缺口 3.189 s）。
3. ⛔ **进程规则提醒**（§28⑦ 新规仍有效）：遇到**点名以外**的实例，
   一律停下写 STATUS 请主会话找用户确认。本轮**未**关闭任何进程
   （只回收了**已确认死亡**的 ASR 锁 PID 2188 的锁文件，且由本仓
   `machine_lock.hold()` 自动完成）。
