# §33 —— EXT-040 ② 全量明细

> 执行时间：**2026-11-06 08:15 ~ 08:35**（实测时间，非推算）
> 指令：`status/CORRECTIONS_EXT.md` 的 **EXT-040 [NORMAL] 2026-11-06 08:10**
> 闸门：`tools/next_instruction.py --json` ⇒ **exit 0**（`action=execute`，latest=**EXT-040**，`last_ack=39`）
> ⇒ **认领 EXT-040** ⇒ `last_ack` = **EXT-040**
> 租约：`session_lease.py acquire ext` ⇒ exit 0，`TOKEN=6acc9767`（**无 TAKEOVER**）

---

## 0. reviewer 的三条「留意点」与本轮处理

| reviewer 条目 | 本轮处理 |
|---|---|
| ① 斜率 +0.135（180 s 轮）vs +0.342（60 s 轮）差 2.5 倍，**只有两个 run** ⇒ **勿写成定值** | ✅ 写入 §33④，**明确标注「勿写成定值」**；本轮**不做新的 e2e**（指令要求）⇒ 不增加第三个数据点 |
| ② **「20 s 缓冲耗尽」的物理含义没写清** ⇒ 请在 STATUS 用**一句话**写明 | ✅ **本轮唯一交付物** —— 见 §1 |
| ③ 根因仍是 `tts_over_src=1.0936>1` ⇒ **EXT 不再做同步性能调参**，直到用户决定「P95≤0.3 s 是否放宽 / 变速上限是否提高」 | ✅ 写入 §33⑥「明确未做」；**本轮零性能调参** |

reviewer 的**复算结论**（EXT-039 执行属实、数字全部可复现）⇒ 本轮**不重跑 e2e、不复算已复核过的数字**。

---

## 1. ★ 那一句话（EXT-040 ② 的答案）

> **「20 s 缓冲耗尽」的物理含义 = 画面照旧按固定 D 播放（不会暂停、不会再缓冲），而配音落后画面；耗尽后不丢句、不静音，只是按「不丢句」排队（实测顺延 23 次 / 37.129 s）。**

reviewer 要回答的是**二选一**：

| 选项 | 本实现 | 证据 |
|---|---|---|
| 画面继续按 D 播放 + 配音落后 | ✅ **就是这个** | 画面目标时刻恒为 `(t0 + 帧时刻) + D`；配音**只**钳位/顺延、**无等待画面的机制** |
| 画面被暂停 / 再缓冲（等配音） | ❌ **不是** | 全仓 `extension/` + `ext/` **无 `.pause()`、无 rebuffer/stall 逻辑** |

⇒ 换言之，`signed_err = actual − (t0 + tStart + D) > 0` 表示
**配音相对「已延迟 D 的画面」晚了多少**，>0 即 **配音落后画面**（口型/语义不同步）；
**画面时间轴始终固定在 D** ⇒ 差距只会**单向累积**，不会自愈。

---

## 2. 那句话依赖的**代码级不变量**（逐条可查）

> 判据：**这不是"读一遍代码觉得对"** —— 每条都有可机械核对的源码事实，
> 并被 `tests/test_ext040_buffer_exhaust_meaning.py` 守住。

| 断言 | 源码事实 | 位置 |
|---|---|---|
| **D 是常量**，运行期不会自动变大 | `delaySec` 无 `+=` / `-=` / `*=` / `/=` 改写；`setDelay()` **无任何调用者**（`extension/` 内 0 处调用）⇒ D 恒为 20 s | `extension/player.js:365`、`:2909` |
| **画面时间轴固定在 D** | `const target = (t0 + frame.timestamp / 1e6) + delaySec;` | `extension/player.js:535` |
| **画面不会被暂停/再缓冲** | `extension/` + `ext/` 全仓**无** `.pause(`、**无** rebuffer/stall 代码 ⇒ 画面没有"等配音"的机制 | 全仓扫描 |
| **原声也固定在 D** | `origDelay.delayTime.value = delaySec;` | `extension/player.js:2293` |
| **不丢句** | `scheduleDub()` 只有两条路径：**钳位**（`metrics.schedClamped`，实测 33）与**顺延**（`metrics.dubRescheduled`，实测 23 / 37.129 s），**无丢弃分支** | `extension/player.js:1327–1401` |
| **不静音** | 耗尽区逐段空档全 ≤ 0.003 s（§31⑥） | `notes/sec31_ext039.md` §7.6 |

⚠️ **`setDelay()` 的存在本身是陷阱**：它是一个**未被调用**的 API。
若将来有人调用它改 D，§33 的那句话就需要重新审视 ⇒
自测里专门断言「`setDelay()` 在 `extension/` 内无调用者」。

---

## 3. 数据侧佐证（run `20261105_174558`，180 s 素材，D=20）

从落盘产物 `metrics.json` / `ext039_sync_curve.json` 读取：

| 字段 | 值 | 来源 |
|---|---|---|
| `delaySec` | **20** | `metrics.json` |
| `schedClamped` | **33** | `metrics.json` |
| `dubRescheduled` / `dubRescheduleDelaySec` | **23** / **37.129** | `metrics.json` |
| `dubPcmDropped` / `dubDup` / `dropped` | **0** / **0** / **0** | `metrics.json` |
| `adaptTotalSpeed` | **1.30**（已封顶） | `metrics.json` |
| signed_err >20 s 的区间 | **128–157 s**，max **22.725 s** | reviewer EXT-040 ② |
| `signed_err_reaches_delay_at_src_sec`（t_exhaust） | **156.517** | `ext039_sync_curve.json:buffer_exhaust` |
| `d_needed_sec` | **40.440**（> D=20 ⇒ 缓冲不足） | `ext039_sync_curve.json:buffer_exhaust` |
| `n_dropped_dub` / `n_silent_fill_segments` | **0** / **19** | `ext039_sync_curve.json:behavior_after_exhaustion` |

⇒ **signed_err 峰值 > D=20 ⇒ 本轮素材确实碰过上限**（不是外推出来的假设）。

⚠️ **回落到 16.7 s 不是"被系统拉回"**：素材语音在 179.85 s 结束，
之后**没有新段** ⇒ 峰值后的回落是**源端没内容**造成的，
**不是**同步在自愈 ⇒ 「差距单向累积」的结论成立。

---

## 4. ★ 口径澄清（reviewer ①）

| run | 素材 | 口径 A `signed_err` 斜率 |
|---|---|---|
| `20261105_112057` | 60 s | **+0.342402 s/s** |
| `20261105_174558` | 180 s | **+0.134808 s/s** |

⇒ 差 **2.5 倍** ⇒ **斜率随素材长度与 TTS 负载变化**，
且**只有两个 run** ⇒ **⚠️ 不得写成定值**。
另：口径 A（`signed_err`，player 实测，自变量 `t_start`）与
口径 B（`lag_est`，服务端估算）**各自定义、不可混用**（§31②）。

---

## 5. 本轮改动文件

| 文件 | 改动 |
|---|---|
| `status/STATUS_EXT.md` | ★ 新增 **§33**；头部 `last_ack` → **EXT-040**、更新时间 → 实测；★ 按 EXT-016 压缩（§30/§31 正文移出，**结论数字一字未改**） |
| `status/notes/sec33_ext040.md` | ★ 本文件 |
| `status/notes/sec30_ext037_038.md` | ★ 追加「§30 的 STATUS 内联全文」（压缩时移出，**原文保留**） |
| `status/notes/sec31_ext039.md` | ★ 追加「§31 的 STATUS 内联全文」（同上） |
| `status/EXEC_LOG.md` | ★ 追加本轮记录 |
| `tests/test_ext040_buffer_exhaust_meaning.py` | ★ **新增**（含**变异测试**） |
| **生产代码** | ★ **零改动**（`ext/bridge.py` / `extension/*` 本轮未动） |

### 新增自测 `tests/test_ext040_buffer_exhaust_meaning.py`

| 组 | 内容 |
|---|---|
| ① STATUS 那句话 | 头部 `last_ack=EXT-040`、有 `## §33`、**7 项必需措辞**齐全、引用 run 目录；且**不得**出现与代码矛盾的「画面会被暂停/再缓冲」表述（**否定式「不会暂停」是要求的内容**，用否定 tempered pattern 区分） |
| ② 代码不变量 | `delaySec` 无自增自减｜`setDelay()` 无调用者｜画面 `target` 含 `+ delaySec`｜`origDelay.delayTime.value = delaySec`｜全仓无 `.pause()`/rebuffer｜`scheduleDub` 有钳位+顺延、**无丢弃分支**（**排除 `pendingSched`/`adaptSpeedHistory` 的记账表裁剪** —— 那是事后量误差用的表，**不丢音频**）｜`src.start(when)` 用的是**顺延后**的时刻 |
| ③ 产物对齐 | `metrics.json` 的 `delaySec`/`dubPcmDropped`/`dubDup`/`dubRescheduled`/`dubRescheduleDelaySec` 与期望值**逐位相等**（产物缺失 ⇒ 明确 **SKIP**，**不判 PASS**） |
| ④ ★ **区分力** | 逐个篡改 7 项必需措辞（**全部**出现，不是第一个）+ 篡改 run 目录 + 篡改 `last_ack` ⇒ **9 种都必须判 FAIL** |

⚠️ **区分力是这一条的关键**：若只断言「STATUS 里有相关文字」，
那么把那句话改得面目全非也能过 ⇒ 就是**假守卫**。
★ **本轮实测中，这个守卫真的抓出了 3 个我自己写错的判据**：
① 否定式「不会暂停」被矛盾检测误判 ⇒ 改用否定 tempered pattern；
② `pendingSched` 裁剪被误判成「丢弃音频」⇒ 改为只认**真正的丢音频信号**
   并**反向断言** `src.start(when)`；
③ 变异只替换了**第一个**出现 ⇒ 判定仍是 PASS（**假通过**）⇒ 改为**全部替换**。

### ★ 源码级变异测试（M1/M2/M3，验证守卫不是摆设）

| # | 变异 | 期望 | 实测 |
|---|---|---|---|
| **M1** | 在 `let delaySec = 20;` 后加 `delaySec += 1`（模拟 D 被动态调大） | 被捕获 | ✅ **FAIL**：「delaySec 没有运行期自增/自减」 |
| **M2** | 给 `setDelay()` 加一个调用者（模拟 D 被人为调大） | 被捕获 | ✅ **FAIL**：「`setDelay()` 在 extension/ 内无调用者（1 处调用）」 |
| **M3** | 给 `drawFrame()` 加 `.pause()`（模拟画面会被暂停等配音） | 被捕获 | ✅ **FAIL**：「无 .pause() / rebuffer 代码」 |

⇒ **3/3 全部 DETECTED**；每次变异后**立即还原**，
还原后 `git diff extension/player.js` = **空** ⇒ **生产代码本轮零改动**已验证。

---

## 6. 明确未做 / 不宣称

- ⛔ **未做新 e2e**（按 EXT-040 指令「不需要新 e2e」）
- ⛔ **未做同步性能调参**（reviewer ③：根因是 `tts_over_src=1.0936>1` ⇒ 归 TTS；
  等用户决定「P95≤0.3 s 是否放宽 / 变速上限是否提高」）
- ⛔ **未自行放宽目标**（判据仍 ≤300 ms；**不写「同步已解决」**）
- ⛔ **未打包**（★ 按用户规则**不主动打包**）
- ⛔ **未改引擎**（R2T2 / Hy-MT2 / Qwen3-TTS 未动）｜⛔ 未改其它模块文件｜⛔ **未推远程**
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**
- ⛔ **未做 MiniMax 回转写**（本轮无新音频；质量判定由 reviewer 负责）
- ⛔ **未关闭任何进程**｜⛔ `.tmp/` 不入库｜⛔ 未抢活锁（本轮**不需要** `MACHINE_LOCK`：无计时/测速作业）
- ⛔ EXT-028 待用户抽听、V2.0 插件部分**暂不放行**；⛔ pyannote 旁路未接线（待 ASR-013）
- ⛔ **斜率仍只基于两个 run** ⇒ 未补第三个数据点（指令未要求，且需计时作业）
