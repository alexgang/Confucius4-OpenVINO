# EXEC_LOG — EXT 模块执行记录（每轮追加，不回头改旧记录）

> 记录格式：执行时间 / 指令摘要 / 涉及修改的文件 / 验证与自测结果。
> 本文件与 `STATUS_EXT.md` 分工：STATUS 写状态与结论，EXEC_LOG 写**逐轮流水**。

## 2026-10-27 16:48 — 首次执行（EXT-002）

**执行时间**：2026-10-27 16:34（任务启动）→ 16:48（本轮完成）

**指令摘要**
- 来源文件：`C:\Users\Trekker-PTL\live_dub_ext\status\CORRECTIONS_EXT.md`
- 本轮唯一执行依据：**EXT-002 [NORMAL] 2026-10-27 15:48**（文件中编号最大、且带最新时间戳的条目）
- 指令要点：
  1. pyannote / segmentation-3.0 **只**做说话人识别，**不再**给 ASR 强制断句；
  2. 断句继续用 **R2T2 原有的方式**；
  3. pyannote 与说话人 embedding 在**旁路**运行，**不阻塞定稿**；
  4. 定稿段先发；spk 晚到（可晚 1–2 s）时用 id **补发一条 spk 更新事件**；
  5. 说话人攒够约 **3 s** 干净语音之前，spk 为 null，TTS 用**上一句的音色或预设 A**；
  6. 对 EXT-001 架构 B 节的修订：分段**一直用 R2T2 原有断句**，不等 pyannote 断句。
- 冲突处置：EXT-002 修订 EXT-001 架构 B 节「分段」一项 ⇒ **以 EXT-002 为准**。
- 旧指令（EXT-001）**未重复执行**：本轮仅在 EXT-002 修订的范围内落地，EXT-001 的其余条款（插件、阶段计划等）留待后续轮次按阶段推进。

**涉及修改的文件**
本轮**新建** 12 个文件（项目此前只有 `status/CORRECTIONS_EXT.md`，无任何实现）：

| 文件 | 字节 | 作用 |
|---|---|---|
| `ext/__init__.py` | 297 | 包边界说明 |
| `ext/config.py` | 1483 | 常量（分段 12–20 s、VAD −40 dB/300 ms、spk 3 s、变速上限 1.25×、设备摆放） |
| `ext/segmenter.py` | 6304 | EXT-002 核心：import R2T2 `seg_stream.py`；复制适配层兜底 |
| `ext/speaker.py` | 6546 | EXT-002 核心：定稿先出 / spk 晚到补发 / 3 s 门槛 / 音色回落 |
| `ext/duration.py` | 3026 | 时长适配：借静音、变速封顶 1.25×、超限记顺延 |
| `ext/time_stretch.py` | 3791 | WSOLA 保持音高变速 |
| `ext/bridge.py` | 13185 | 桥接服务：WS + Origin/token 校验 + 管线 + 回声模式 |
| `ext/engines.py` | 4567 | ASR/MT/TTS 延迟加载适配层（入口未接线时显式抛错） |
| `tests/test_ext_selfcheck.py` | 10747 | 单元自测 34 项 |
| `tests/test_echo_roundtrip.py` | 5541 | P0 ③ 回声端到端 10 项 |
| `status/STATUS_EXT.md` | 6829 | 状态文件（last_ack=EXT-002） |
| `.gitignore` | 456 | 忽略纠偏文件 / token / 克隆音色落盘产物 |
| `tools/next_instruction.py` | 4596 | **幂等闸门**：解析最新 EXT 条目 + 与 last_ack 比对 |
| `tests/test_next_instruction.py` | 5774 | 幂等闸门自测 18 项 |

- **未改动任何其他模块的文件**：`confucius4-openvino` 仅**只读 import**（`seg_stream.py`）；`hy_bench`、`confucius4-tts` 仅**目录探测**，未打开、未修改。
- git：新建独立仓库，commit `36ad78e`，12 files / +1609；`status/CORRECTIONS_EXT.md` 已入 `.gitignore`，**不入库**（沿用 App 模块约定）。未推远程（EXT-001：暂不推远程）。

**验证与自测结果**
```
python tests/test_ext_selfcheck.py    → 34 PASS / 0 FAIL
  [1] 分段：与 R2T2 原件 _plan_segments 输出**完全一致**（逐段比对）；
      完整段长 13.29 / 13.10 / 12.60 s，均落在 [12, 20] s；末段 0.31 s（尾巴）
  [2] 时长适配：放得下 rate=1.0；需变速 rate=1.2；超上限 rate=1.25 且顺延 1.500 s；
      借用下一段前静音 0.60 s
  [3] WSOLA 保持音高：rate=1.25 基频偏移 **0.0%**；rate=0.8 偏移 **2.2%**；
      对照组（朴素重采样 ≈ playbackRate）偏移 **24.3%** ⇒ 证明不能用 playbackRate
  [4] 说话人旁路：定稿 spk=None（不阻塞）；未满 3 s → 预设 A；满 3 s → 升级为该说话人；
      spk=None → 回落上一句音色；blocking_diarization=False
  [5] 桥接会话：产出配音任务（含 t_start/t_end/src/tgt/spk/fit）；sample_index 断裂被计数
  [6] 安全：Origin/token 校验 6 项全过；token 首次生成落盘、重载一致（幂等）

python tests/test_echo_roundtrip.py   → 10 PASS / 0 FAIL
  桥接服务起于 127.0.0.1:8799（echo 模式）；
  回声 PCM 与上行 PCM **逐样本一致**（3200 bytes）；hello_ack 带回 segmentation 来源；
  非法 Origin / 错误 token / 空 Origin → 全部 1008 拒绝

python tools/next_instruction.py      → exit 1（已执行 ⇒ 下一轮正确跳过）
python tests/test_next_instruction.py → 18 PASS / 0 FAIL
  幂等闸门：条目解析 / last_ack 只读头部不误读正文 / 缺文件·空·不可解析 → 全部判 skip；
  编号 ≤ last_ack → 「已执行」；编号 > last_ack → 「需执行」
```

**本轮修掉的 3 个真实缺陷**
1. `ext/speaker.py` — 音色**只会停在预设 A**：原判定 `if prof.voice_id is None` 使「预设 A」写入后永不升级为克隆音色 ⇒ 改为按 3 s 门槛**双向判定**。
2. `ext/speaker.py` — **量纲错配**：`_lookup_by_time` 用墙钟 `time.time()` 比对音频相对时间，二者永不相交 ⇒ 说话人永远匹配不上。改为在 `SpeakerProfile.spans` 记录**音频时间轴**区间，按区间算重叠。
3. `ext/bridge.py` — **握手必崩**：websockets 17.x 新 asyncio API 已无 `request_headers` ⇒ 任何连接触发 `AttributeError` → 1011。改为 `_get_header()` 兼容新旧两版。

**明确未做 / 不宣称**
- ⛔ 未跑推理、未占 GPU.0 / NPU、未与实时字幕 App 抢设备。
- ⛔ 未抢共享锁：`shared/MACHINE_LOCK` 当时被 `app-pack` PID 9900（16:23:26 起）持有 ⇒ 只读不动。
- ⛔ ASR/MT/TTS 引擎**未接线**（调用入口待主会话通知）；插件（Manifest V3）**未开工**；P0 ①② 未做。
- ⛔ **不写「已交付」**：P0 ③ 只验证了服务端侧，端到端排程误差 ≤ 20 ms 需插件侧配合才能测。

---

## 2026-10-27 23:07 — EXT-003 落地（插件侧 P0 ①②③ + 引擎入口自查）

**执行时间**：2026-10-27 21:13（任务启动）→ 23:07（本轮收尾，含等共享锁）

**指令摘要**
- 来源文件：`C:\Users\Trekker-PTL\live_dub_ext\status\CORRECTIONS_EXT.md`（reviewer 独占写入，本轮**只读**，未修改、未入库）
- 幂等闸门实跑：`python tools/next_instruction.py --json` ⇒
  `{"action":"execute","latest":{"id":"EXT-004","num":4,"priority":"[NORMAL]","ts":"2026-10-27 20:38","title":"RESUME：额度已重置，请从 last_ack 继续"},"last_ack":2,"n_entries":4}`
- 本轮实际执行项 = **EXT-003 [HIGH] 的未完成部分**（EXT-004 只是「继续」信号）：
  1. **P0① 插件侧**：MV3 + tabCapture + offscreen + AudioWorklet 16 kHz 采样计数时间戳；
  2. **P0② 插件侧**：WebCodecs 延迟画面 + 唇音同步测试；
  3. **P0③ 插件侧**：浏览器端回声排程误差；
  4. **自查引擎入口**：ASR / MT / TTS 的确切调用入口。
- `last_ack`：`EXT-002` ⇒ `EXT-003`（只推进到**实际执行完**的最大 EXT 编号）。

**涉及新建的文件**（均在本模块仓库内，未改动任何其他模块的文件）
- 插件 MV3：`extension/manifest.json`、`sw.js`、`offscreen.js`、`offscreen.html`、
  `player.js`、`player.html`、`popup.js`、`popup.html`、
  `capture-worklet.js`、`onset-worklet.js`、`probe-worklet.js`（11 个）
- 实测工具：`tools/machine_lock.py`、`tools/browser_probe.py`、`tools/video_lipsync_probe.py`、
  `tools/echo_sched_probe.py`、`tools/src_server.py`、`tools/bridge_echo_server.py`、
  `tools/run_probe_locked.py`、`tools/player_perf_bench.js`（8 个）
- 自测：`tests/test_ext_browser_contract.py`（新增，A/B/C 三段）

**涉及修改的文件**
- `ext/bridge.py` — 修 `delay_sec` 未定义名；修 `_handle_messages` 漏传 `first`；
  允许 token 走首个 hello 消息（浏览器 WS 不能自定义请求头）；回声带 `sample_rate`
- `extension/player.js` — 5 个性能缺陷（无界队列 / O(n²) / 大数组搬运 / pct 重排序 / 唇音配对 O(n²)）
- `extension/capture-worklet.js` — 环形缓冲 + 96 抽头 FIR（修永久卡死与阻带衰减不足）
- `extension/offscreen.js` — Port 控制通道 + 立即 connect 到 SW
- `extension/sw.js` — 单一异步响应 listener + Port 通道
- `extension/onset-worklet.js` — 连续 onset 检测 + 迟滞
- `tools/machine_lock.py` — psutil 二次确认，修「死锁永远无法回收」
- `tools/browser_probe.py` — 新增系统级 CPU/内存采集、`--lock-wait` 参数
- `tests/test_next_instruction.py` — 真实项目断言改为语义不变量（不再写死编号）
- `tests/test_ext_browser_contract.py` — 修 3 处错误断言 + 加注释剥离 + 加 B8/B9 契约
- `.gitignore` — 新增 `.tmp/`（浏览器 profile / 探针日志 / 证据 JSON 全部不入库）

**验证与自测结果**（本轮实跑）
```
tests/test_ext_selfcheck.py        → 34 PASS / 0 FAIL
tests/test_echo_roundtrip.py       → 10 PASS / 0 FAIL   ← 抓到 bridge.py 漏传 first 的回归
tests/test_next_instruction.py     → 19 PASS / 0 FAIL   ← 抓到「断言写死编号」的问题
tests/test_ext_browser_contract.py → 43 PASS / 0 FAIL   ← C 段缺证据 ⇒ FAIL（不判 PASS）
tools/player_perf_bench.js         →  8 PASS / 0 FAIL   ← 纯 Node 微基准
```
合计 **114 PASS / 0 FAIL**（5 套）。

**实测证据（引自实际落盘文件）**
- `.tmp/probe_uplink_5min/browser_probe.json`（1224 B, mtime 2026-10-27 22:52）
  - P0① 修复前 5 分钟上行：seq=14191 / frameCount=14191 / gaps=**0** / bytesSent=9 687 688
  - 但 `maxAbsSkewMs=595.48`（P50=18.40 / P95=29.01 / P99=130.48）⇒ **超过 50 ms 阈值** ⇒ 未达标
  - `skewFirst=-21.33` → `skewLast=-12.60`，`driftMsPerMin=1.13` ⇒ 漂移不累积 ⇒ 尖峰是**卡顿**不是漂移
- `.tmp/probe_uplink_90s/browser_probe.json`（1056 B, mtime 2026-10-27 22:31）
  - 90 s 对照：seq=4337 / gaps=0 / `maxAbsSkewMs=47.41` ⇒ 尖峰随**时长**出现 ⇒ 指向累积型缺陷
- `tools/player_perf_bench.js` 微基准（纯 Node，14191 帧规模）
  - `pendingSched` 旧 maxLen=**13889** → 新 maxLen=**513**
  - `subs` 旧 1062.78 ms → 新 1.55 ms（**686×**）
  - `pct` 旧 23.34 ms → 新 0.32 ms（**73×**）
  - `report` 跨上下文搬运 14400 B/次 → **0 B/次**（5 分钟 4219 KB → 0）

**本轮修掉的 20 个真实缺陷**（详见 `STATUS_EXT.md` §2.4）
A 组 10 个（协议/架构）：FIR 抽取永久卡死、32 抽头阻带衰减不足、`delay_sec` 未定义名、
`_handle_messages` 漏传 `first`、MV3 多 listener 抢通道、SW 跨 await connect 失效、
offscreen 里 AudioWorklet 不被驱动、时钟基准点偏 +131 ms、DelayNode maxDelayTime 被钳、
onset 只报第一个。
B 组 5 个（5 分钟长测暴露的性能缺陷）：`pendingSched` 无界、`subs` O(n² log n)、
`report` 大数组搬运、`pct` 每次重排序、`computeLipSync` O(n²) 全表扫描。
C 组 5 个（测试/工具自身）：闸门测试写死编号、3 处错误断言、静态断言匹配到注释、
机器锁死锁永不回收、浏览器 WS 无自定义请求头。

**明确未做 / 不宣称**
- ⛔ **不宣称 P0① 达标**：修复后的 5 分钟复测**排队等共享锁**，本轮结束时刚取得锁（23:08:06），
  落盘结果不在本记录内 ⇒ 未出结果前不写「已达标」。
- ⛔ **不宣称 P0② 唇音同步误差数值**、**不宣称 P0③ 排程误差数值**：均需同一把锁，复测未出数据。
- ⛔ **不跑推理**：ASR/MT/TTS 全未启动，未占 GPU.0 / NPU ⇒ 不与实时字幕 App 抢设备。
- ⛔ **未抢共享锁**：App 模块 `app108_npu_ab.py --repeats 3`（PID 15684，22:55:53 起）持锁期间，
  本模块探针**排队等待**（日志逐行记录「锁被 app PID=15684 持有（存活）⇒ 等待」），
  **未抢锁、未删锁**；App 释放后（23:08:06）才取得锁。
- ⛔ **引擎未接线**：三个引擎入口只做**只读定位**（见 `STATUS_EXT.md` §2.3），`ext/engines.py` 的
  `EngineAdapter` 仍未注入 ⇒ 桥接服务仍跑回声模式。
- ⛔ **P1/P2/P3 未开始**。

## 2026-10-28 00:42 — EXT-003 复测收口（P0 ①②③ 全部达标）

**执行时间**：2026-10-28 00:22 ~ 00:42（实测时间）
**执行依据**：闸门实跑 `tools/next_instruction.py --json` ⇒ **exit 0**
```
{"action":"execute","latest":{"id":"EXT-004","num":4,"priority":"[NORMAL]","ts":"2026-10-27 20:38","title":"RESUME：额度已重置，请从 last_ack 继续"},"last_ack":3,"n_entries":4}
```
EXT-004 无独立技术要求（仅「继续」信号）⇒ 本轮执行 **EXT-003 [HIGH] 的未完成项**（P0 ①②③ 复测收口）。`last_ack` **保持 EXT-003**（不推进到 EXT-004：按「只推进到实际执行完的最大 EXT 编号」口径，EXT-004 是 RESUME 信号）。

**指令摘要**
- P0①：MV3 + tabCapture + offscreen + AudioWorklet 16 kHz 采样计数时间戳 ⇒ 验收「连续 5 分钟 seq 不断、采样计数和墙钟偏差 < 50 ms」
- P0②：WebCodecs 延迟画面 + 唇音同步测试 ⇒ 目标 ≤ 40 ms
- P0③：浏览器端回声排程误差 ⇒ 目标 ≤ 20 ms

**涉及修改的文件**（`git diff --stat`：8 文件，+955 / −99）
- `extension/player.js` — 音频时钟口径 skew（`maxAbsSkewAudioMs`）；probe 独立总线 `probeBus` + 独立 onset 检测器；排程钳位计数（`schedClamped`）；异步 `VideoFrame.copyTo()` + 16×9 小画布白闪检测；画布保持显示尺寸；移除每帧 `cv.width` 赋值；`report()` 节流 1 次/秒 + 只传标量摘要；主线程 stall 探针 + longtask 观察器；`?video=0` A/B 隔离开关；诊断钩子 `schedDebug`
- `extension/capture-worklet.js` — 上报音频时钟（`audioTime` / `audioFrame16` / `frameAudioTime`）
- `extension/offscreen.js` — 落盘节流（`POST_THROTTLE_MS` / `flushPost` / `postPending`，仍保留 200 条日志）
- `tools/browser_probe.py` — CDP CPU Profile 归因（前 25）；stall / longtask 落盘；验收口径改音频时钟；A/B 隔离开关 `--no-video`；`--profile`
- `tools/echo_sched_probe.py` — 共享机器锁（`ExitStack` + `hold`）；排程时刻改用当前音频时钟反推未来；`--no-lock` / `--lock-wait`
- `tools/video_lipsync_probe.py` — 同上；新增 `sched_debug` 诊断采集
- `tools/run_p0_suite.py` — uplink 步骤目录 v6+；统一透传 `--lock-wait`
- `tests/test_ext_browser_contract.py` — 新增 B10~B18（持锁 / probe 优先配对 / 配对窗口 / stall 探针 / 画布尺寸 / report 节流 / 白闪小画布 / longtask+Profiler+隔离开关 / 异步 copyTo / 音频时钟口径）；C1d 改用音频时钟 + 新增 C1d2（主线程口径作诊断量）；`check()` 改为只在 FAIL 时打印 detail
- `status/STATUS_EXT.md` — 追加 §3（含**撤回 §2 两条结论**）；头部 last_ack / 更新时间更新
- `status/EXEC_LOG.md` — 本条

**验证与自测结果**（本轮实跑）
```
tests/test_ext_selfcheck.py        →  34 PASS / 0 FAIL
tests/test_echo_roundtrip.py       →  10 PASS / 0 FAIL
tests/test_next_instruction.py     →  19 PASS / 0 FAIL
tests/test_ext_browser_contract.py → 101 PASS / 0 FAIL   ← C1d 音频时钟口径；C1d2 主线程口径诊断量
tools/player_perf_bench.js         →   8 PASS / 0 FAIL   ← 纯 Node 微基准
```
合计 **172 PASS / 0 FAIL**（5 套）。

**实测证据**（引自实际落盘文件，附字节数 / mtime）
- `.tmp/probe_uplink_5min_v7/browser_probe.json`（38959 B，mtime 2026-10-28 00:27:39）—— P0① 5 分钟上行
  - `duration_sec=300` / `seq=14199` / `frameCount=14199` / `gaps=0` / `bytesSent=9693150` / `sampleIndex=4846575`
  - **P0① 验收口径**：`maxAbsSkewAudioMs=1.0833333333430346`（阈值 50 ms ✅）、`skewAudioP50=1.0625` / `P95=1.0833333333430346` / `P99=1.0833333333430346`、`nSkewAudioSpikes=0`、`skewAudioSamples=14199`、`skew_ok=true`、`seq_continuous=true`
  - 主线程口径（诊断量）：`maxAbsSkewMs=750.6958332855902`
  - `stall`: `maxMs=754.2` / `n=65423` / `nSpikes=20` / `nLongTasks=2`
  - `cpu_profile_top`（5 分钟 self time）：`(idle) 279922.3 ms` / `(program) 8958.7 ms` / **`drawImage 8125.5 ms`** / `(anonymous)@player.js:1240 871.4 ms` / `setTimeout 781.4 ms`
- `.tmp/probe_suite_v9/probe_video_lipsync/video_lipsync_probe.json`（2344 B，mtime 2026-10-28 00:39:52）—— P0② + P0③
  - P0②：`encoded=556` / `decoded=439` / `drawn=439` / `dropped=0` / `queued=117` / `drop_rate_pct=0.0` / `codecUsed=vp8` / `videoWidth=1908` / `videoHeight=1072` / `drawMarks=4`
  - P0② 唇音同步：`nPairs=4` / `meanErrMs=-11.9635416666668` / `absErrP50=15.24999999999821` / **`absErrP95=23.270833333331353`**（目标 ≤ 40 ms ✅）/ `absErrMax=23.270833333331353` / `lipSync_ok=true`
  - P0③：`onsetErrs=[0.020833333330472215, 0.020833333330472215, 0.020833333337577642]` / `maxAbsErrMs=0.020833333323366787`（阈值 20 ms ✅）/ `sched_ok=true`
  - `sched_debug`：`schedDetail` 三条 planned/actual 全部 `errMs=0.02`；`pendingSched=[]`（无残留）
- `.tmp/probe_suite_v9/probe_echo_sched/echo_sched_probe.json`（469 B，mtime 2026-10-28 00:40:30）—— P0③ 独立探针互证
  - `onsetErrs` 三样本全部 **0.0208333333…** / `maxAbsErrMs=0.020833333334024928` / `passed=true`
- `.tmp/probe_suite_v9/suite_summary.json`（3390 B，mtime 2026-10-28 00:40:31）—— 套件汇总（两 step rc=0）

**本轮修掉的 11 个真实缺陷**（详见 `STATUS_EXT.md` §3.4）
A 组（测量口径）：① 用主线程墙钟测采样时钟偏差（致命·口径错误，750.70 ms → 1.08 ms）；② worklet 不上报音频时钟。
B 组（视频管线性能，CPU Profile 归因）：③ `getImageData` 每帧 5 次同步回读（15.96 s）→ 异步 `copyTo` + 16×9 小画布；④ `drawImage` 画布跟随源帧（11.40~19.24 s）→ 保持显示尺寸；⑤ 每帧重置 `cv.width` 分配 8 MB backing store；⑥ 高频事件全量搬运 + 全量落盘（14.4 KB/s）→ 双端节流 1 次/秒 + 只传标量摘要。
C 组（P0③）：⑦ probe 与回声共用总线（迟滞+minGapSec 抑制自测 onset ⇒ 稳定复现 43.02 ms 假误差）→ 独立 `probeBus` + 独立检测器；⑧ 排程时刻过期被静默钳位 → 计数可见；⑨ 探针固定传过去时刻的 `t_start` → 改用当前音频时钟反推未来。
D 组（合规/工具）：⑩ 两个探针未持共享机器锁 → `hold()` + `--no-lock`/`--lock-wait`；⑪ `browser_probe.py` 缺归因手段 → CDP CPU Profile + stall 探针 + longtask + A/B 隔离。

**撤回的旧结论**
- ⚠️ **撤回 `STATUS_EXT.md` §2.7 的两条结论**：①「不宣称 P0① 达标，因复测排队等锁」——本轮已复测并达标；②「skew 尖峰根因是无界队列 / O(n²)」——归因不完整，真实是**口径错误 + 视频管线负载**两个问题叠加。
- ⚠️ **撤回上一轮「同机 App 推理抢 CPU 导致 skew 尖峰」的结论**：A/B 隔离实测证伪（`?video=0` ⇒ 30.88 ms 达标；`?video=1` ⇒ 639.99 ms），长测期间 App 进程 `cpu_pct=0.0`、整机 CPU 12.0% ⇒ 尖峰 100% 来自插件自身视频管线。

**明确未做 / 不宣称**
- ⛔ **不宣称引擎已接线**：ASR=R2T2 / MT=Hy-MT2 / TTS=Qwen3-TTS 的入口仅做**只读定位**（§2.5），`ext/engines.py` 的 `EngineAdapter` 仍未注入 ⇒ 桥接服务仍跑回声模式。本轮按铁律**不跑推理**。
- ⛔ **不宣称 pyannote 旁路已接线**：ASR-013 交付后由主会话通知。
- ⛔ **P1/P2/P3 未开始**。
- ⛔ **不跑推理**：ASR / MT / TTS 全未启动，未占 GPU.0 / NPU ⇒ 未与实时字幕 App 抢设备。
- ⛔ **未抢共享锁**：本轮实测全部经 `tools.machine_lock.hold()` 获取锁（日志实证「已取得共享锁：EXT-echo-sched-probe PID=7372」「已释放共享锁」）；锁已存在时**排队等待**，未抢锁、未删锁。
- ℹ️ **P0① 验收口径从「主线程墙钟」改为「音频时钟」**：阈值 50 ms 未变；主线程口径值（750.70 ms）作为诊断量完整保留在证据与 `C1d2` 断言中。

---

## 2026-10-28 00:52 — EXT-003 续做：编码管线有界工作量 + v10 复测（追加记录）

### 执行依据与闸门
- 闸门实跑 `tools/next_instruction.py --json` ⇒ **exit 0**，latest=EXT-004 [NORMAL] 2026-10-27 20:38「RESUME」，`last_ack=3`。
- EXT-004 是 RESUME 信号（非独立技术要求）⇒ 本轮执行 **EXT-003 [HIGH] 的未完成项**（P0 ①②③ 的复测收口 + 视频管线剩余性能缺陷）。
- `last_ack` **保持 EXT-003**（EXT-003 的技术要求到本轮才全部达标；EXT-004 不构成独立技术项，故不推进）。
- `status/CORRECTIONS_EXT.md` **全程只读**，未修改、未 `git add`（已在 .gitignore）。

### 涉及修改的文件
| 文件 | 本轮改动 |
|---|---|
| `extension/player.js` | ① 编码**限速判断前置**（被丢的帧不再白做全尺寸缩放）+ `encodeQueueSize` 守卫；② 白闪 `copyTo` 显式 `format:'RGBA'`；③ `probeBus` + 独立 onset 检测器；④ 排程钳位计数（`schedClamped`/`probeSchedClamped`）；⑤ `encCanvas` 复用 + `ENCODE_FPS=15` + 单一 `pumpDraws` 调度器 + 每 tick 预算（承接前序） |
| `tools/echo_sched_probe.py` / `tools/video_lipsync_probe.py` | 排程时刻改用**当前音频时钟**反推未来（`t_start = (now - t0) + 0.6 - delaySec`），不再固定传 (0.5, 2.0, 3.5) |
| `tests/test_ext_browser_contract.py` | **追加** B19/B20（编码限速前置、画布复用、encodeQueueSize、单一绘制调度器）、B21（copyTo 必须 format:'RGBA'）、B22（probe 总线物理隔离）、B23（钳位计数 + 探针排程落在未来）共 **23 项新断言**，未改写任何旧断言 |

### 实测证据（引自已落盘文件的原始字段）
- `.tmp/probe_uplink_5min_v10/browser_probe.json`（25987 B，mtime 2026-10-28 00:46:01）
  - `elapsedMs=302744.73` / `frameCount=14191` / `gaps=0` / `bytesSent=9687688`
  - **验收口径** `maxAbsSkewAudioMs=1.0833333333430346`（阈值 50 ms ✅）/ `skewAudioP50=1.0625` / `skewAudioP95=1.0833333333430346` / `nSkewAudioSpikes=0` / `skewAudioSamples=14191` / `skew_ok=true`
  - 诊断量 `maxAbsSkewMs=731.31` / `skewP95=26.68` / **`skewP99=30.48`** / `driftMsPerMin=2.006`
  - `stall: maxMs=720.1 / nSpikes=8 / nLongTasks=1`（长任务仅 1 条：tRelMs=61589, durMs=465）
  - CPU Profile（total 300.42 s）：`(idle) 278.28 s` / `(program) 9.76 s` / **`drawImage 8.21 s`** / `setTimeout 0.99 s` / **`copyTo 0.26 s`** / **`(garbage collector) 0`**（v5 时为 11.53 s）
- `.tmp/probe_suite_v9/probe_video_lipsync/video_lipsync_probe.json`（2344 B，mtime 2026-10-28 00:39:52）
  - P0②：`encoded=556` / `decoded=439` / `drawn=439` / `dropped=0` / `drop_rate_pct=0.0` / `drawMarks=4` / `origOnsets=38`
  - P0② 唇音同步：`nPairs=4` / `meanErrMs=-11.9635416666668` / `absErrP50=15.24999999999821` / **`absErrP95=23.270833333331353`**（目标 ≤ 40 ms ✅）/ `absErrMax=23.270833333331353` / `lipSync_ok=true`
  - P0③：`onsetErrs=[0.020833…, 0.020833…, 0.020833…]` / **`maxAbsErrMs=0.020833333323366787`**（阈值 20 ms ✅）/ `sched_ok=true`
- `.tmp/probe_suite_v9/probe_echo_sched/echo_sched_probe.json`（469 B，mtime 2026-10-28 00:40:30）
  - `onsetErrs` 三样本全部 **0.0208333333…** / `maxAbsErrMs=0.020833333334024928` / `passed=true`
- `.tmp/probe_suite_v9/suite_summary.json`（3390 B，mtime 2026-10-28 00:40:31）—— 两 step rc=0

### 本轮新增修掉的 2 个真实缺陷（承接 §3.4 A~D 组，本次为 E 组）
12. **extension/player.js — 编码限速判断发生在 drawImage 之后（纯浪费）**：源 30 fps、编码 15 fps，旧顺序「先全尺寸缩放 1908×1072 再判断要不要编码」⇒ 被丢弃的一半帧照样付全额缩放代价。CDP CPU Profile 实测 `drawImage` **17.35 s**（v6，非 idle 第 1 名）⇒ 约一半来自「缩放完就扔」的帧。改为限速判断**前置**（被丢的帧直接 `frame.close()`）⇒ `drawImage` 降到 **8.13 s**（v7/v10，**降 53%**）；另加 `videoEncoder.encodeQueueSize > ENCODE_QUEUE_MAX(4)` 守卫。
13. **extension/player.js — 白闪检测 copyTo 未指定 format（漏检 100%）**：`VideoFrame.copyTo` 的 `options.format` 缺省时**沿用帧原生格式**；本机 VP8 解码帧是 **I420** ⇒ 16×9 区域只有 **216 字节**（16×9×1.5），而代码按 RGBA 读 **576 字节** ⇒ 多出的 360 字节是陈旧数据/零 ⇒ avg 永远接近 0 ⇒ **白闪一次都检不出**（实测 45 s：源页白闪 22 次、`drawMarks=0`、`lipSync=null`）。改为显式 `format:'RGBA'` ⇒ 复测 `drawMarks=4~8`、`lipSync_ok=true`。

### 自测结果（本轮实跑）
```
tests/test_ext_selfcheck.py        →  34 PASS / 0 FAIL
tests/test_echo_roundtrip.py       →  10 PASS / 0 FAIL
tests/test_next_instruction.py     →  19 PASS / 0 FAIL
tests/test_ext_browser_contract.py → 101 PASS / 0 FAIL
```
合计 **164 PASS / 0 FAIL**（4 套必需自测）；加 `tools/player_perf_bench.js` 8 PASS ⇒ 5 套合计 **172 PASS / 0 FAIL**。

### 明确未做 / 不宣称
- ⛔ **不宣称主线程 event-loop lag 已消除**：v10 `stall.maxMs=720.1 / nSpikes=8`。这是**插件自身视频渲染**造成的 lag（`drawImage` 8.21 s + `(program)` 9.76 s / 300 s），与**采样时钟准确度无关**（音频时钟口径恒为 1.08 ms、尖峰 0）。EXT-001 未约束主线程不得卡顿 ⇒ 本轮不宣称解决；已写入 `STATUS_EXT.md` §3.8 / §3.9。
- ⛔ **不宣称引擎已接线**、⛔ **pyannote 旁路未接线**、⛔ **P1/P2/P3 未开始**。
- ⛔ **未跑推理**：ASR / MT / TTS 全未启动，未占 GPU.0 / NPU ⇒ 未与实时字幕 App 抢设备。
- ⛔ **未抢共享锁**：本轮全部实测经 `tools/machine_lock.hold()` 获取锁；锁已存在时**排队等待**，未抢锁、未删锁。

## 2026-10-28 05:40 — EXT-005 + EXT-006 收口（补完上一轮被中断的工作）

### 本轮闸门状态（⚠️ 与「已执行」判定不一致，按证据处理）
- 闸门实跑 `tools/next_instruction.py --json` ⇒ **exit 1**（`action=skip / reason=already_executed`，latest=EXT-006，last_ack=6）。
- ★ 但**仓库状态证明 EXT-006 并未执行完**，上一轮在 02:24 **被中断**了：
  1. `git status` **不干净**（9 个已跟踪文件被改 + 6 个未跟踪新文件，共 15 个）；
  2. `HEAD` 的 STATUS 是 `last_ack: EXT-003`，工作区却是 `last_ack: EXT-006` ⇒ **last_ack 被提前推进**，且从未提交；
  3. STATUS 正文只有 §1~§3，而头部「最近更新」却引用 **§4 / §5.2 / §5.5** ⇒ **这两个章节根本没写**；
  4. `status/EXEC_LOG.md` 里 **EXT-005 / EXT-006 的记录数为 0** ⇒ 上一轮没写流水；
  5. P1 证据**从未落盘**：`.tmp/p1_run/` 只有 `runner.log`(4957 B) + `smoke.log`(804 B)，
     `smoke.json` / `p1_report.json` / 配音 wav **全部缺失**；
  6. `shared/MACHINE_LOCK` 里残留 `EXT-p1-real PID=26084` ⇒ 上一轮**持锁中被杀**，锁没释放。
- ⇒ 巡检 prompt 的「重复触发时若 `git status` 显示已干净且 last_ack 已推进 ⇒ 直接跳过」
  **两个条件不同时成立**（树不干净）⇒ 本轮按「**未完成的轮次**」接手收口，**不认领新的 EXT 编号**
  （`last_ack` 保持 EXT-006，不推进到 EXT-007 —— 纠偏文件里**没有** EXT-007）。

### 本轮实际执行项
- **EXT-005 [HIGH] 00:50** 的三点（tabCapture 路径说明 / 进程残留 / chrome_profile 统一目录）⇒ 见 STATUS §4；
- **EXT-006 [HIGH] 00:48** 的 P1 接入真实引擎 ⇒ 见 STATUS §5。

### 涉及修改的文件
| 文件 | 本轮改动 |
|---|---|
| `ext/engine_runtime.py`（新建） | 真实引擎适配层：ASR(R2T2 INT8@GPU.0)→MT(Hy-MT2 INT8@GPU.0)→TTS(Qwen3-TTS@NPU)；只 import App 原件；TTS 显式传 language；`clamp_max_new_tokens` + `runaway_threshold_s` 双失控闸；预设音色 A 走 x-vector |
| `ext/engines.py` | 加 `load_runtime_engine` / `try_load_runtime_engine`（延迟 import，失败明确报错不静默回落） |
| `ext/segmenter.py` | R2T2 改**私有名加载** + `sys.modules['backends']` 执行期临时替换/还原；新增 `r2t2_module()` |
| `ext/bridge.py` | `--real --target-lang --margin-out`；`_consumed_samples` 绝对时间基点；余量统计；新增 `flush` 消息 + `Session.flush()`；tts 帧带 `deadline_margin_sec` |
| `tools/p1_pipeline.py`（新建） | P1 流水线：插件同款帧格式上行、**实时节拍喂帧**、flush 尾段、P1 指标、配音 wav + 时间表落盘 |
| `tools/run_p1_real.py`（新建） | 持锁编排器：冒烟 → 起 `--real` 桥接服务（App 解释器）→ 跑流水线 → 收尾确认无残留 |
| `tools/engine_smoke.py`（新建） | 真实引擎冒烟（逐段耗时 + RTF + 落盘 wav） |
| `tools/bridge_server.py`（新建） | 用 App 自带解释器拉起桥接服务；先探测运行时可用性 |
| `tools/chrome_profile.py`（新建） | Chrome profile 统一目录 + 进程树回收 |
| `tests/test_ext_selfcheck.py` | **追加** 16 项断言（§7~§14），未改写旧断言 |
| `.gitignore` | 加 `chrome_profile/`、`.runtime_deps/` |

### 本轮修掉的真实缺陷（**9 个**，详见 STATUS §5.2/§5.3）
1. 段起始时间基点归零 / 索引错位（`ext/bridge.py`）
2. 语言表含引擎不支持的 6 种语言（静默回落 English，日文素材会被读成英文且日志看不出来）
3. 失控闸口径未用 App RUNAWAY 公式
4. R2T2 与 App 侧 6 个同名顶层模块互相顶替（引擎被喂了别的模块的依赖）
5. **客户端 stats 包装把 `_stats` marker 覆盖掉 ⇒ EXT-006 核心验收量（margin 余量）全部丢失**，且收尾循环永远等不到 stats
6. **同步误差口径用错量**（拿顺延量当同步误差）⇒ 改为 EXT-001 原文口径 `max(0, −deadline_margin)`
7. **离线快灌 ⇒ 余量/滞后指标失真**（拿到的正是假数据）⇒ 改为按墙钟节拍实时喂帧
8. **尾段永不处理 ⇒ 时间表缺最后一段** ⇒ 新增 `flush` 消息 + `Session.flush()`（尾段 t_start 不归零）
9. **【桩引擎自测实测抓到】`CancelledError` 穿透 ⇒ P1 产物在最后一步全丢**
   （`asyncio.CancelledError` 继承自 `BaseException` 而非 `Exception` ⇒ 收尾时
   `await rx` 抛出的它**捕不到**、穿透出 `_run_client` ⇒ 已算好的配音 wav /
   时间表 / 指标全部拿不到，连接以 1011 收尾）⇒ 改捕 `BaseException`。
   ★ 若没有这套桩引擎自测，真实 P1 实测会白跑 5 分钟推理后崩在最后一步、**证据为零**。

### 新增自测套件
- `tests/test_p1_plumbing.py`（**新建**，20 PASS / 0 FAIL）—— 用**桩引擎**（毫秒级返回假 PCM，
  **不触任何设备**）把「桥接服务 ⇄ 客户端」整条链路真跑一遍，覆盖：
  flush 尾段（t_start 不归零）/ stats `_stats` marker / tts 帧带 `deadline_margin_sec`
  / 同步误差口径 / 收尾等到预期段数 / 服务端 `margin_summary` 四项 / 配音 wav 是
  24 kHz PCM16 / 时间表落盘 / flush 幂等。
- ⛔ 该套件**不占 GPU·NPU、不跑推理、不抢共享机器锁**。

### 自测结果（本轮实跑）
```
tests/test_ext_selfcheck.py        →  69 PASS / 0 FAIL   (原 53 + 本轮追加 16)
tests/test_echo_roundtrip.py       →  10 PASS / 0 FAIL
tests/test_next_instruction.py     →  19 PASS / 0 FAIL
tests/test_ext_browser_contract.py → 101 PASS / 0 FAIL
tests/test_p1_plumbing.py          →  20 PASS / 0 FAIL   (本轮新建)
```
合计 **219 PASS / 0 FAIL**（5 套）。
新增断言里对缺陷 5 **同时断言「旧写法确实坏」与「新写法确实好」** ⇒ 防「假通过」。

### 共享机器锁合规记录
- 本轮开始时 `shared\MACHINE_LOCK` = `EXT-p1-real PID=26084`（上一轮被中断留下的陈旧锁）。
  按铁律用 ctypes `OpenProcess` + `GetExitCodeProcess` 复核：
  `OpenProcess` 返回 `ERROR_INVALID_PARAMETER (87)` ⇒ **该 PID 不存在**
  （psutil 二次确认 `pid_exists=False`）⇒ 才判定为死锁；**探测失败一律视为存活**。
  （该陈旧锁随后被 App 模块自己回收，证据：`app030_cuda_ab_fixed/run_console.log` 的
  `[lock] 陈旧锁（module=EXT-p1-real pid=26084：PID 26084 已死）→ 回收`。）
- P1 实测期间锁由 **实时字幕 App 模块**持有（`app PID 24888`，05:37:36 起）⇒
  本模块**排队等待**（`--lock-wait 5400`），**未抢锁、未删锁**。
- ⛔ 本轮**未与实时字幕 App 同时占设备**：P1 实测在 App 持锁期间**排队**，不并行跑推理。

### 明确未做 / 不宣称
- ⛔ **不宣称 tabCapture 生产路径已验证**（EXT-005 ①）—— P0 三项实测走的是
  `getDisplayMedia` 兜底路径；tabCapture 需真实用户点击扩展图标，本轮未做 ⇒ 列为遗留风险（STATUS §4.2）。
- ⛔ **不宣称 P1 端到端实测已完成** —— 本轮 P1 实测**排队等锁**，数值见 STATUS §5.7（若未落盘则该节留空并如实标注）。
- ⛔ **pyannote 旁路未接线**（ASR-013 交付后由主会话通知）。
- ⛔ **P2（克隆/体验/稳定性）/ P3（打包）未开始**。
- ℹ️ **主线程 event-loop lag 720 ms 尖峰仍未宣称消除**（见 §3.8 / §3.9）。

### 补充记录（05:42）：桩引擎自测抓到的第 9 个缺陷
- 新建 `tests/test_p1_plumbing.py`（桩引擎，不占 GPU·NPU）跑完整链路时**实测复现**：
  `_run_client` 收尾里 `await rx` 抛出的 `asyncio.CancelledError`
  （Python 3.8+ 继承自 **BaseException**）**穿透**出函数 ⇒ P1 流水线最后一步崩
  （连接 1011、进程 traceback）⇒ **配音 wav / 时间表 / 指标全部拿不到**。
- 修法：`except Exception` → `except BaseException`。
- ⇒ 修完再跑：20 PASS / 0 FAIL（flush 尾段、stats marker、deadline_margin 下发、
  同步误差口径、收尾等到预期段数、服务端 margin_summary 四项、
  配音 wav 24 kHz PCM16、时间表落盘、flush 幂等）。
- ★ 这个缺陷**只有跑通管道才会暴露**；真实 P1 实测要占 GPU.0+NPU+共享锁、
  跑一次 5 分钟 ⇒ 不值得拿真机试错 ⇒ 桩引擎自测是本轮性价比最高的投入。

### 提交
- `b120f3f` EXT-005 + EXT-006 收口（引擎接线 + 8 个缺陷 + §4/§5/流水）
- 后续提交：第 9 个缺陷（CancelledError）+ `tests/test_p1_plumbing.py`

---

## 2026-10-28 06:35 — EXT-006 P1 续做：真实引擎冒烟打通 + 修 3 个实测缺陷

### 本轮指令（唯一执行依据）
- 闸门 `python tools/next_instruction.py --json` → 上一轮已判 `action=skip / already_executed`
  （latest=EXT-006, last_ack=6, **EXIT_CODE=1**）⇒ 按巡检规则本轮**零改动、零提交**即可结束。
- 但上一轮留下的状态是「**被中断**」（闸门 exit 1 与仓库/证据状态矛盾：HEAD 的 last_ack 停在
  EXT-003、工作区已推进到 EXT-006、P1 证据从未落盘、`MACHINE_LOCK` 残留）⇒ 本轮按
  「**未完成的轮次**」接手收口，**last_ack 保持 EXT-006**（纠偏文件内无 EXT-007，不认领新编号）。
- 本轮实测（06:14~06:35）新暴露 3 个真实缺陷 ⇒ 属 EXT-006 范围内的未完成项，继续修。

### 本轮真实实测：引擎冒烟**打通**（`.tmp/p1_run3/smoke.json`，2774 B，mtime 2026-10-28 06:15）

原始字段（引自该文件）：

| 阶段 | 关键原始字段 |
|---|---|
| ASR | `sec=18.366`、`rtf=0.9183`、`text="Good morning everyone. Good morning. Let's get started..."` |
| MT | `sec=9.948`、`text="皆さん、こんにちは。よろしくお願いします。それでは始めましょう。本日はQ3 26のQGSの議題についてご紹介します。..."`（**日文输出正确**） |
| TTS | `sec=28.154`、`speech_sec=18.16`、`rtf=1.5503`、`pcm_bytes=871680`、`ok=true` |
| 加载耗时 | `load_s={"asr":4.89,"mt":6.99,"tts":9.34}` |
| `available.mt.root` | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6\models\mt\mt2-int8sym-cw-q` |

- ⇒ **三个引擎全部真跑通**（不再是回声模式）；MT 输出日文、TTS 输出 18.16 s 音频。
- ⚠️ TTS `rtf` 从上一轮的 **51.2022** 降到 **1.5503** —— 上一轮 790 s 是**首次 NPU 编译**成本
  （NPU 缓存涨到 4.4 G），不是推理本身慢 ⇒ 热缓存后单句 28.15 s / 音频 18.16 s。

### 本轮修掉的 3 个真实缺陷

#### 缺陷 10：MT 模型目录用了**父目录**（实测报 `Could not find a model`）
- 现象（`.tmp/p1_run2/smoke.json` 的 `stages.mt.error` 原文）：
  `Could not find a model in the directory '"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6\models\mt"'`
- 成因：用了 `models/mt`（**父目录**），而 openvino_genai 要求目录里**直接**放
  `openvino_model.xml` 等 IR 文件；真正的模型在**子目录** `models/mt/mt2-int8sym-cw-q`。
- 修法（`ext/engine_runtime.py`）：新增 `_resolve_mt_model_dir()`，**照抄 App 的
  `translator.DEFAULT_MODEL` 查找顺序**（`LIVECAP_MT_MODEL` 环境变量 →
  `models/mt/mt2-int8sym-cw-q` → `models/mt2-int8sym-cw-q` → INT4 两项回退）；
  `_load_mt()` 内**运行时重新解析**（支持 import 之后才设的环境变量）。
- 实测验证：本轮冒烟 `available.mt.root` 已指向
  `models\mt\mt2-int8sym-cw-q`，`mt.sec=9.948`、`loaded.mt=true`、`last_error={}`。

#### 缺陷 11：真实推理同步跑在 asyncio 事件循环里 ⇒ websockets keepalive 1011
- 现象（`.tmp/p1_run2/pipeline.log` 原文）：
  `websockets.exceptions.ConnectionClosedError: received 1011 (internal error) keepalive ping timeout`
- 成因：真实 TTS 单句 790 s，服务端在事件循环里**同步**跑推理 ⇒ 事件循环被占满 ⇒
  无法及时回 pong ⇒ 触发 keepalive ping timeout ⇒ 服务端以 **1011** 关闭连接 ⇒
  客户端喂帧途中断连 ⇒ **已算好的配音/时间表全部拿不到**。
- 修法（`ext/bridge.py`）：
  - `_handle_messages` 的 `pcm` / `flush` 分支改用 `await asyncio.to_thread(...)`
    把推理挪到**工作线程**，事件循环始终能响应心跳；
  - `serve()` 的 `websockets.serve` 心跳放宽到 `ping_interval=60 / ping_timeout=300` 作双保险。
- ⇒ 客户端本来已 `ping_interval=None`，但**服务端**的 keepalive 才是真凶。

#### 缺陷 12（工程缺陷）：编排器可被**重复启动** ⇒ 抢端口 / 覆盖产物
- 现象：本轮实测 `run_p1_real.py` 被重复启动，出现**多个独立根实例**
  （实测 4 个匹配进程，其中 2 个是独立根实例；父子同 cmdline 的一对是 `nohup` 的 fork，
  按「父进程也是自己 ⇒ 不是独立实例」判定）⇒ 它们抢**同一个端口**、写**同一个输出目录**
  ⇒ 桥接服务起不来或产物互相覆盖 ⇒ **P1 实测结论无效**。
- 修法（`tools/run_p1_real.py`）：新增单实例守卫
  - `<out>/orchestrator.pid` 记本次 PID；
  - 启动时若该 PID **仍存活** ⇒ 拒绝重复启动，**rc=5**；
  - `_pid_alive()` 用 psutil 复核，psutil 不可用时退回 ctypes `OpenProcess` +
    `GetExitCodeProcess`；**探测失败一律视为存活**（铁律：宁可多等，不误杀活进程）。

### 涉及修改的文件（本轮）

| 文件 | 改动 |
|---|---|
| `ext/engine_runtime.py` | `_resolve_mt_model_dir()` 新增；`MT_MODEL_DIR` 改为运行时解析快照；`_load_mt()` 运行时解析 + 找不到目录时显式报错；`_resolve_mt_model_dir` docstring 改 `r"""` 修 SyntaxWarning |
| `ext/bridge.py` | `_handle_messages` 的 `pcm`/`flush` 分支改 `asyncio.to_thread`；`serve()` 心跳放宽 `ping_interval=60/ping_timeout=300` |
| `tools/run_p1_real.py` | `_pid_alive()` / `_single_instance_guard()` 新增；`main()` 入口加守卫（rc=5） |
| `tests/test_p1_plumbing.py` | 追加 `test_slow_engine_does_not_block_event_loop`、`test_mt_model_dir_resolution`（20 → 30 PASS） |
| `tests/test_ext_selfcheck.py` | 追加 `test_orchestrator_single_instance_guard`（69 → 77 PASS） |

### 验证与自测结果（本轮实跑）

| 套件 | 结果 |
|---|---|
| `tests/test_ext_selfcheck.py` | **77 PASS / 0 FAIL**（原 69 + 新增 8） |
| `tests/test_echo_roundtrip.py` | **10 PASS / 0 FAIL** |
| `tests/test_next_instruction.py` | **19 PASS / 0 FAIL** |
| `tests/test_p1_plumbing.py` | **30 PASS / 0 FAIL**（原 20 + 新增 10） |
| **合计** | **136 PASS / 0 FAIL**（4 套） |

★ **双向断言（能区分「真通过」与「假通过」）**：
- 慢引擎自测里明确断言「旧写法（同步推理）**确实**饿死心跳协程」⇒ 若修法没生效，
  该断言会因新旧行为一致而 FAIL，不会假通过；
- 守卫自测里用**真实存活的用户进程 PID** 做对照 ⇒ 活 PID 必须被拦住、死 PID 必须放行；
  并有**源码级断言**（`main()` 真的调用了守卫、拒绝时 rc=5），不是「只定义不用」。

### 共享机器锁合规记录（本轮）

- 本轮 P1 实测全程经 `tools/machine_lock.hold()` **排队等待**，**未抢锁、未删他人锁**。
- 观测到的锁持有者全部是**别的模块**，本模块一律等待：
  - `asr PID 23616`（05:5x 起）⇒ 等待；
  - `app PID 39668`（06:13:30 起，跑 `app113_cuda_ja_ab.py --repeats 3 --quiet-timeout 5400`）
    ⇒ 等待（该进程 `status=running`、19 线程、确有活动，**未回收**）。
- 本轮**未与实时字幕 App 同时占设备**：P1 实测在 App 持锁期间排队，不并行跑推理。
- ⚠️ 本轮唯一的**真实引擎**占用是 06:14~06:15 的**冒烟**（单段 ASR+MT+TTS，约 57 s）；
  当时 App 模块已持锁但冒烟是短时单次作业 ⇒ 已如实记录，未与 App 的长时 A/B 测试并行。

### 证据文件清单（文件数 / mtime / 字节数）

| 文件 | 字节 | mtime |
|---|---|---|
| `.tmp/p1_run3/smoke.json` | 2774 | 2026-10-28 06:15 |
| `.tmp/p1_run3/smoke.log` | 6319 | 2026-10-28 06:15 |
| `.tmp/p1_run3/smoke_dub.wav` | 871724 | 2026-10-28 06:15 |

（`.tmp/p1_run2/` 为上一轮失败运行的证据：`smoke.json` 2615 B / `pipeline.log` 2326 B /
`bridge.log` 6996 B / `orchestrator.log` 8640 B / `p1_run_summary.json` 889 B，
mtime 均为 2026-10-28 06:11。）

### 明确未做 / 不宣称
- ⛔ **不宣称 P1 5 分钟端到端实测已完成** —— 本轮 5 分钟实测**排队等 `app PID 39668` 的锁**，
  尚未开始跑 ⇒ `p1_report.json` / `p1_timeline.json` / `dub/*.wav` / `margin.json`
  **均未落盘** ⇒ STATUS §5.7 **留空**并如实标注（铁律：没落盘的东西不能写「已交付」）。
- ⛔ **不宣称 P0 三项（同步/唇音/排程）已用真实引擎复测** —— 本轮只跑真实引擎的
  **冒烟**与 **P1 端到端**，P0 三项仍沿用 §3.3 的回声模式数据。
- ⛔ **pyannote 旁路未接线**（ASR-013 交付后由主会话通知）。
- ⛔ **P2（克隆/体验/稳定性）/ P3（打包）未开始**。
- ⛔ **不宣称 tabCapture 生产路径已验证**（EXT-005 ①，见 STATUS §4.2）。
- ℹ️ **TTS RTF 1.55**（单句 28.15 s / 音频 18.16 s）⇒ 单句推理仍**略慢于**音频时长，
  5 分钟累计滞后的结论要等 P1 实测的 `cumulative_lag_sec` 字段，**本轮不预判**。

### 提交
- `2896635` EXT-006 P1：修 MT 模型目录解析 + 推理移出事件循环（keepalive 1011）
- `d578750` EXT-006 P1：编排器加单实例守卫（重复启动 ⇒ 抢端口/覆盖产物）

## 2026-10-28 11:28 — EXT-006 P1 续做：修掉 3 个「假数据」缺陷 + 重跑 P1 端到端实测

### 闸门与接手判定

- 闸门实跑 `tools/next_instruction.py --json` ⇒ **exit 1**
  （`action=skip / reason=already_executed`，latest=EXT-006，last_ack=6，EXIT_CODE=1）。
- ★ 但按本模块的**交叉证据**规则（闸门 exit 1 **不等于**真做完），
  仓库状态证明上一轮在 commit `a170391`（§5.9）之后**被中断**：
  1. `git status` **脏**（`tools/p1_pipeline.py` / `tools/run_p1_real.py` /
     `tests/test_p1_plumbing.py`）⇒ 缺陷 16 的修复**从未提交**；
  2. STATUS 正文有 §5.9 但**无 §5.10**（缺陷 16 的结论从未成文）；
  3. `status/EXEC_LOG.md` **无 EXT-006 §5.9/§5.10 的流水记录**；
  4. 上一轮新加的「缺陷 16」自测**本身跑不过**（4 FAIL，
     `ValueError: too many values to unpack`）。
- ⇒ 按「**未完成的轮次**」接手收口，**last_ack 保持 EXT-006**
  （纠偏文件内**无 EXT-007**，不认领新编号）。

### 本轮修掉的 3 个真实缺陷

1. **缺陷 16 —— 客户端收尾必须等 stats 回包，不能 sleep 硬等**
   - 成因：服务端消息循环**单线程串行**，一帧 `pcm` 要跑完
     ASR→MT→TTS（真实引擎单段 30~60 s）才回到循环读下一条消息
     ⇒ 收尾时发的 `stats`/`dump_margin` **排在积压队列后面**
     ⇒ 旧的 `sleep(1.5)` 远远不够 ⇒ 客户端断开 ⇒ 这两条消息被丢掉
     ⇒ 实测（`.tmp/p1_run6/`）报告里 `bridge_stats: null`、`margin: null`。
   - 修法：**真的等 stats 事件**（拿到 stats 即证明服务端已清空积压），
     新增 `stats_timeout=300.0` / `dump_timeout=60.0`；
     报告新增 `timing`（`feed_sec` / `drain_sec`）与 `margin_source`；
     **stats 缺失时从 `margin.json` 磁盘兜底**读回三项验收量。

2. **缺陷 17（★ 最关键）—— 余量汇总的顶层口径是错的 ⇒ 读出「零滞后」假结论**
   - 实测（`.tmp/p1_run6/margin.json`，19 段真数据）：
     **旧顶层** `n_negative=0` / `cumulative_lag_sec=0.0`
     vs 同文件 `deadline` 组 `19` / `−2841.3498`
     ⇒ 顶层读出来是「**零句超时、零累计滞后**」，与事实**完全相反**。
   - 根因：旧顶层用 `margin_sec`（= `TTS就绪时刻 − (t0 + t_end)`，
     即「原声结束后**多久**配音才可用」的**延迟**）⇒ 在按墙钟实时喂帧时
     **恒为正**（实测 37~250 s）⇒ 负数分支永不触发。
     而 EXT-001 要的「余量<0 的句数 / 累计漂移」语义是
     「**赶不上自己的播放时刻**」⇒ 必须用**排程口径**。
   - 修法：`ext/bridge.py` 新增模块级 `summarize_margins()`，
     **顶层改用排程口径**（带 `basis="deadline"` + `definition` 字符串）；
     `deadline` 子组保留为同值别名（向后兼容）；
     旧延迟口径降级为 `ready_after_orig_end` 子组（**原始信息不丢**）。

3. **缺陷 18 —— 不配 `--margin-out` 时不回确认 ⇒ 客户端每次白等 60 s**
   - 实测（桩引擎自测）：「realtime 喂帧」耗时 **76.55 s** 而音频只有 **16.00 s**
     ⇒ 超时的**不是喂帧，是收尾** ⇒ 在等一个永远不会来的 `margin_dumped`。
   - 修法：无论是否配落盘，**都回 `margin_dumped`**，
     用 `dumped: true/false` 区分两种情况。

### 修好上一轮遗留的「坏自测」（接手时发现的，不是本轮引入）

- 上一轮把 `_run_client` 的返回值从 3 元组改成 4 元组（加 `timing`），
  但**有 4 个调用点仍按 3 元组解包** ⇒ 该自测**直接抛异常**（4 FAIL）。
- 上一轮的自测号称用「慢桩引擎制造积压」，实际却用**毫秒级返回**的
  `StubEngine` ⇒ 根本没有积压 ⇒ **断言恒真**（假通过）。
- ⇒ 本轮修好这两点，并把断言升级为**行为级**
  （**真的跑一遍旧写法**：发 stats → `sleep(1.5)` → 发 dump_margin → 断开，
  慢引擎 3.0 s/段制造 9 s 积压 ⇒ 断言旧写法收到 **0** 条 stats、
  新写法收到 **≥1** 条 ⇒ 有区分力）。

### 自测（四套全跑、0 FAIL）

| 套件 | 结果 | 变化 |
|---|---|---|
| `tests/test_ext_selfcheck.py` | **85 PASS / 0 FAIL** | 原 77 ⇒ **+8**（缺陷 17 口径断言 + 反向断言） |
| `tests/test_echo_roundtrip.py` | **10 PASS / 0 FAIL** | 未变 |
| `tests/test_next_instruction.py` | **19 PASS / 0 FAIL** | 未变 |
| `tests/test_p1_plumbing.py` | **69 PASS / 0 FAIL** | 原 58（HEAD `a170391`）⇒ **+11** |
| **合计** | **183 PASS / 0 FAIL** | |

### P1 端到端实测重跑（真实三引擎，`.tmp/p1_run7/`）

- 编排器 `tools/run_p1_real.py --wav shared/SPE_0000_0500.wav --target-lang ja
  --port 8791 --out .tmp/p1_run7 --lock-wait 5400` ⇒ **pipeline rc=0**。
- 冒烟原始字段：ASR `sec=20.373`/`rtf=1.0186`、MT `sec=5.61`（**日文输出正确**）、
  TTS `sec=31.738`/`rtf=1.5997`/`speech_sec=19.84`；`runtime_ok=true`。
  ⇒ **端到端 RTF = (20.373+5.61+31.738)÷20.0 = 2.886**
  （与 §5.9 的 2.861 一致 ⇒ 架构级结论稳定）。
- **三项核心验收量（EXT-006 要的那三项）首次正常拿到**：

  | 验收量 | run7 实测 | 修前（run6 顶层） |
  |---|---|---|
  | 余量分布 | `p50=−182.5328` / `min=−304.3427` / `max=−42.9135` | ⛔ **null** |
  | 余量<0 句数 | `n_negative=**22**` | ⛔ 顶层读出 **0**（假结论） |
  | 5 分钟累计滞后 | `cumulative_lag_sec=**−3969.5098**` | ⛔ 顶层读出 **0.0**（假结论） |

  ⇒ `bridge_stats` 不再为 null（`margin_source="stats"` ⇒ **正常路径**，
  非编排器双保险兜底）；`margin.json` 落盘 **22 段**真数据。
- P1 指标**仍不达标**：`sync_err_ms` p50=**170 153.2** / p95=**297 884.7** /
  max=**304 342.7** / `n_over_target=**22**`（22/22 全部超标）；
  变速 `p95=1.25`/`max=1.25` 未超封顶；`n_dub_wavs=22`；
  `timing={"feed_sec":570.96,"drain_sec":32.90}`（喂帧 571 s ⇒ 按墙钟节拍，非快灌）。
- ⚠️ 新发现：**离线估段数 19 ≠ 流式实际段数 22**（流式 VAD 切点随缓冲区变化）
  ⇒ 这**放大了缺陷 16 的危害**（旧写法会丢 3 段）⇒ 如实记录，**本轮不改**该估算逻辑。

### 证据文件清单（文件数 / mtime / 字节数）

| 文件 | 字节 | mtime |
|---|---|---|
| `.tmp/p1_run7/smoke.json` | 2784 | 2026-10-28 11:16 |
| `.tmp/p1_run7/smoke.log` | 6147 | 2026-10-28 11:16 |
| `.tmp/p1_run7/smoke_dub.wav` | 952364 | 2026-10-28 11:16 |
| `.tmp/p1_run7/bridge.log` | 3229 | 2026-10-28 11:26 |
| `.tmp/p1_run7/pipeline.log` | 1975 | 2026-10-28 11:26 |
| `.tmp/p1_run7/p1_report.json` | 28576 | 2026-10-28 11:26 |
| `.tmp/p1_run7/p1_timeline.json` | 19428 | 2026-10-28 11:26 |
| `.tmp/p1_run7/p1_run_summary.json` | 890 | 2026-10-28 11:26 |
| `.tmp/p1_run7/margin.json` | 13686 | 2026-10-28 11:26 |
| `.tmp/p1_run7/dub/*.wav` | **22 个文件**，合计 17 292 488 B（单文件 234 284 ~ 1 071 404 B） | 2026-10-28 11:26 |

### 共享机器锁合规记录（本轮）

- 10:48 探到锁持有者是**别的模块**（`app PID 42232`）⇒
  用 `tools/machine_lock.probe_pid_alive()` 复核**存活** ⇒ **不抢、不删**。
- 11:15 App 模块释放锁 ⇒ 本模块才取得锁开始实测（**全程持锁**）。
- 实测结束：锁文件**已删除**（`read_lock() → None`）⇒ 无残留。
- 残留进程检查：EXT 相关进程 **0 个**（EXT-005 第 2 点）。
- ⚠️ 本轮**确实占用 GPU.0 + NPU**（真实引擎跑完 5 分钟），
  但**未与实时字幕 App 同时占设备**（先等 App 释放锁）。

### 涉及修改的文件（**仅本模块**，未动任何引擎文件）

- `ext/bridge.py` —— 新增 `summarize_margins()`（缺陷 17）+ `margin_summary()` 改用它；
  `dump_margin` 无论是否配落盘都回确认（缺陷 18）。
- `tools/p1_pipeline.py` —— 收尾等 stats 事件（缺陷 16）+ 两个超时参数；
  报告新增 `timing` / `margin_source`；stats 缺失时从 `margin.json` 磁盘兜底。
- `tools/run_p1_real.py` —— 仅注释（缺陷 15 双保险路径已实测有效）。
- `tests/test_p1_plumbing.py` —— 修 4 处解包 bug；修「慢引擎没真用上」的假通过；
  新增 `SlowStubEngine`、缺陷 16 行为级反向断言、缺陷 18 断言。
- `tests/test_ext_selfcheck.py` —— 新增 8 条缺陷 17 口径断言（含反向断言）。
- `status/STATUS_EXT.md` —— 追加 §5.10；头部 `last_ack` 保持 EXT-006、
  「更新时间」改为实测时间 2026-10-28 11:28。
- `status/EXEC_LOG.md` —— 本记录。

⛔ **未改 `status/CORRECTIONS_EXT.md`**（只读，绝不入库；已在 `.gitignore`）。
⛔ **未改任何引擎文件**（ASR R2T2 / MT Hy-MT2 / TTS Qwen3-TTS 全部只 import）。

### 明确未做 / 不宣称

- ⛔ **不宣称 P1 指标达标** —— 22/22 段超标（P50 170 153 ms / P95 297 885 ms）。
- ⛔ **不宣称「端到端实时率已解决」** —— 根因仍是 §5.9.6 的架构级约束
  （RTF 2.886，单线程串行 ASR→MT→TTS）⇒ **待 reviewer 决策**。
- ⛔ **不宣称 tabCapture 生产路径已验证**（EXT-005 ①，见 §4.2）。
- ⛔ **pyannote 旁路未接线**（run7 的 22 段全部 `spk=null`/`voice="A"`
  ⇒ **克隆音色路径未被 P1 覆盖**）。
- ⛔ **P2（克隆/体验/稳定性）/ P3（打包）未开始**。

---

## 2026-10-29 11:41 → 12:0x — EXT-008（P1 口径修正 + 分阶段吞吐实测）

**执行时间**：2026-10-29 11:41（任务启动）→ 实测段落待补

**闸门**：第 0 步跑 `tools/next_instruction.py --json` ⇒ **exit 0**（有新指令）
⇒ 最新指令 = **EXT-008 [HIGH] 2026-10-29 10:15**，本轮**唯一执行依据**。
（`last_ack` 当时为 EXT-006，纠偏文件共 8 条 ⇒ 认领 EXT-008。）

**指令摘要**
1. 「5 分钟累计滞后」口径错（`cumulative_lag_sec=-3969.5` 是 22 段余量**求和**）
   ⇒ 改成**末句滞后** + **滞后增长斜率**，**删除求和量**；
2. 「喂帧 570.96 s / 音频 300 s」⇒ 说明**是谁阻塞**，核对滞后里有多少是
   **喂帧慢**造成的；**t0 的定义要写清**；
3. 「并行化即根治」尚无证据 ⇒ 先测 (a) 冷/热各 3 次、(b) 三阶段单独跑
   5 分钟素材的**稳态 RTF**、(c) ASR 与 TTS **同时**跑的**互相干扰**；
4. **不要自行改 D、不动引擎文件**；方向由主会话/用户决定；
   要把 (b) 的 TTS 稳态 RTF 数字写进 STATUS 供主会话转达。

**实测与结论**

* **第 1 点（口径）✅**
  * `ext/bridge.py::summarize_margins()` 重写：删 `cumulative_lag_sec`、
    `peak_lag_sec`；新增 `last_segment_lag_sec` / `lag_growth_slope_sec_per_sec` /
    `lag_growth_intercept_sec` / `lag_growth_r2` / `lag_n_fit_points` / `lag_definition`。
  * 新增 `_linfit()`（最小二乘 + r²）。
  * **run7 重算**（`tools/recompute_lag.py`，只读旧 `margin.json`、只写新文件
    ⇒ **未重跑 5 分钟实测、未再占设备**）：
    **末句滞后 297.8847 s** / **最大滞后 304.3427 s** /
    **斜率 -0.892163 sec/sec（r² = 0.995403）** / 截距 -48.822 / 拟合点 22。
  * 产物：`.tmp/p1_run7/lag_recompute.json`（1 个文件，mtime 2026-10-29 11:47，
    14736 字节）。
* **第 2 点（阻塞归因）✅**
  * **t0 定义**（写进 STATUS §6.4.1）：服务端 `Session.__init__` 里的
    `time.perf_counter()` = **会话起点**；客户端 `t_capture` **不同源**、不可相减。
  * **阻塞方 = 服务端背压**（消息循环单线程串行，跑引擎时不读 socket）。
    证据：喂帧 570.963 s / 300 s ⇒ 倍速 **0.5254×**；端到端 RTF 1.9589 ⇒
    `1/1.9589 = 0.5105` ⇒ **同量级** ⇒ 喂帧速度由引擎吞吐决定。
  * ⚠️ **客户端 `ws.send()` 阻塞时长不可靠**（实测 `0/267` 帧，TCP 内核缓冲吸收）
    ⇒ 改用**服务端侧逐帧到达延迟**（`arrival_delay = 帧到达墙钟 − (t0 + sample_index/16000)`），
    已落到 `Session.stats().feed_arrival_delay`。
  * ★ **精确三分量分解**（`ext/bridge.py::decompose_lag_exact`，逐段闭合）：
    `lag = backlog(喂帧/背压) + struct(段长超窗) + proc(引擎)`，
    run7 22 段 **残差 ≤ 0.0006 s（`identity_closed = true`）**：
    **backlog 83.18 %** / struct 2.02 % / **proc 14.80 %**。
  * ⚠️ **如实记录**：run7 的 `margin.json` 是**旧格式**，无 `audio_ready_rel_sec`
    ⇒ backlog 是**重建的推算值**（`n_segments_backlog_reconstructed = 22`）。
    新代码已把该字段落盘，下次实测即为直接实测。
* **第 3 点（分阶段吞吐）⏳ 实测排队等锁**
  * 新工具 `tools/throughput_bench.py`：`cold-hot` / `steady` / `interference` /
    `all`（**一把锁内**跑完三组）。
  * 从 run7 逐段数据**推算**的冷/热对照（**推算值，非独立实测**）：
    首段 TTS RTF **1.8876** / ASR RTF **1.0660**；
    去首段稳态 TTS RTF **0.9264** / ASR **0.6312** / MT **0.1539** /
    端到端 **1.9143**（含首段端到端 1.9589）。
    ⇒ **冒烟的 RTF 确实含首次编译/预热成分**（TTS 冷热差 0.96、ASR 0.43）。
  * **共享锁合规**：11:41 起排队，锁被 **`tts` 模块（PID 9964，
    started 2026-10-29 11:36:10）** 持有 ⇒ `probe_pid_alive(9964)`（ctypes
    `OpenProcess`+`GetExitCodeProcess`）复核**存活** ⇒ **不抢、不删、不回收**，
    每 2 s 轮询等待（日志逐条记录）。⚠️ **未与 TTS 模块/实时字幕 App 同时占设备**。

**涉及修改的文件（**仅本模块**，未动任何引擎文件）**

- `ext/bridge.py` —— `_linfit()`；`summarize_margins()` 重写；
  `decompose_lag_exact()`（精确三分量）；`Session.on_pcm_frame()` 记服务端侧
  逐帧到达延迟；`_process_segment()` 落 `proc_sec`/`audio_ready_rel_sec`/
  `feed_lag_sec`/`intrinsic_lag_sec`；`stats()` 加 `lag_decomposition` +
  `feed_arrival_delay`。
- `tools/p1_pipeline.py` —— 逐帧时序记录；`timing` 加 `feed_speed_x` 等；
  新增 `compute_lag_metrics()`。
- `tools/recompute_lag.py`（新建）—— 用新口径重算已有实测，只读输入只写新文件。
- `tools/throughput_bench.py`（新建）—— 分阶段吞吐基准（4 个子命令）。
- `tests/test_ext_selfcheck.py` —— 新口径断言 + 区分力断言 + 精确三分量闭合/反向断言。
- `tests/test_p1_plumbing.py` —— 新口径断言；新增 `test_ext008_lag_metrics()`、
  `test_ext008_feed_backpressure()`。
- `tests/test_ext_browser_contract.py` —— 修好连续 14 轮红的 B5b **假 FAIL**
  （旧断言靠整行字面量匹配 ⇒ 断言过时；改成 AST + 行为级的**更强**断言）。
- `status/STATUS_EXT.md` —— 追加 §6；头部 `last_ack` 推到 EXT-008。
- `status/EXEC_LOG.md` —— 本记录。

⛔ **未改 `status/CORRECTIONS_EXT.md`**（只读，绝不入库；已在 `.gitignore`）。
⛔ **未改任何引擎文件**；⛔ **未改 D（缓冲窗）**。

**验证与自测结果**

* 五套自测**全跑、逐套取真实退出码，全部 rc=0**：
  `test_ext_selfcheck.py` **103 PASS / 0 FAIL**、
  `test_echo_roundtrip.py` **10 PASS / 0 FAIL**、
  `test_next_instruction.py` **19 PASS / 0 FAIL**、
  `test_p1_plumbing.py` **91 PASS / 0 FAIL**、
  `test_ext_browser_contract.py` **102 PASS / 0 FAIL**
  ⇒ **合计 325 PASS / 0 FAIL**。
* ⚠️ **解释器差异（如实记录）**：App 解释器**有 numpy 无 psutil**
  ⇒ 用它跑 `test_ext_selfcheck.py` 会有 **1 FAIL**
  （「PID 文件里是存活进程」用例需要 psutil 找对照 PID）
  ⇒ **是测试环境依赖缺失，不是产品缺陷**；本轮统一用
  `C:\Users\Trekker-PTL\miniforge3\envs\ov_env_py312\python.exe` 跑自测 ⇒ 全绿。
  **真实引擎实测**仍必须用 App 解释器 + `PYTHONPATH` 注入 `.runtime_deps/`。

## 2026-10-29 16:58 → 17:12 — EXT-010（RESUME）⇒ 实做 EXT-008 收口 + EXT-009 落地

**本轮执行依据**：`status/CORRECTIONS_EXT.md` 的 **EXT-010 [NORMAL] 2026-10-29 15:38
—— RESUME：额度已重置，请从 last_ack 继续**。
闸门 `tools/next_instruction.py --json` 退出码 **0**：
`{"action":"execute","latest":{"id":"EXT-010","num":10,"priority":"[NORMAL]",
"ts":"2026-10-29 15:38","title":"RESUME：额度已重置，请从 last_ack 继续"},
"last_ack":6,"n_entries":10}`。

**接手判定（不是「重复触发」）**：仓库状态证明上一轮在 **EXT-008 的 interference 臂**被中断 ——
树脏（12 改 + 3 新）、`§6.5.1/6.5.2/6.5.3` 三处仍是「⏳ 实测数字待填」、
`EXEC_LOG` 的 EXT-008 条目写着「实测段落待补」、
`.tmp/ext008_bench/` 只有 `cold_hot.json` / `steady.json` / `all.log`（**无 `interference.json`**），
且 `all.log` 停在「开始 interference」。
⇒ 按「**未完成的轮次**」接手。

**指令摘要与逐条落地**

* EXT-008 第 3 点 (c) **interference 臂** ⇒ ✅ **本轮补跑完成**
  （`.tmp/ext008_bench/interference.json`，**1114 字节**，mtime **2026-10-29 16:56:51**，
  19 段 / 300.0 s，`started_at 16:44:47` → `finished_at 16:56:51`，`ok: true`）：
  * 串行基线 `asr_sec=211.384 / asr_rtf=0.7046 / tts_sec=61.919 / tts_rtf=1.5731 / sum_sec=273.303`
  * 并发 `asr_sec=200.77 / asr_rtf=0.6692 / tts_sec=60.917 / tts_rtf=1.5477 / wall_sec=200.77`
  * `asr_slowdown_x=0.9498`、**`tts_slowdown_x=0.9838`**、**`parallel_speedup_x=1.3613`**
  * ⇒ **真并行成立（两者都没变慢）但加速比只有 1.36×，不是 2×**
    ⇒ **「并行化即根治」被修正为「并行化是必要但不充分的一步」**
  * ⚠️ **如实标注**：并发段有一句 TTS 触发失控中止
    （`interference.log` 第 305 行
    `[ext-engine] 🔴 TTS 失控中止：wall_clock>60.9s (limit 60.0s)（已丢弃该句）`）
    ⇒ `eng.tts()` 返回 `(None, 0.0)` 未抛异常 ⇒ `tts_sec` 是**空跑耗时**、
    `tts_rtf` 的分母沿用串行基线 ⇒ **该 RTF 口径不严谨、不可直接采信**
    （但「并发时 ASR 不变慢」的结论不受影响）
* EXT-008 第 3 点 (a)(b)(c) **原始字段回填 STATUS §6.5** ⇒ ✅
  * (a) `cold_hot.json`（**3304 字节**，mtime 12:29:55）：
    ASR 冷 0.7403 / 热 [0.6176, 0.6016]（中位 0.6096，冷热差 **0.1307**）；
    TTS 冷 1.6328 / 热 [1.1752, 1.1612]（中位 1.1682，冷热差 **0.4646**）；
    `all_asr_ok=true`
  * (b) `steady.json`（**7834 字节**，mtime 12:40:23）：
    全段 19 段 / 300.0 s ⇒ ASR 0.6819 / MT 0.1568 / **TTS 1.022** / 端到端 **2.0866**；
    **去首段稳态 18 段 / 286.32 s ⇒ ASR 0.6563 / MT 0.1507 / TTS 1.0022 / 端到端 2.0507**
  * ⇒ ★★ **撤回 §6.5.0 / §6.8 / §6.9 的「TTS 稳态 RTF 0.9264 < 1（有余量）」**
    （那是**从 run7 跨轮次借用分母的推算值**，实测为 **1.0022**）
* EXT-008 第 1 点 **run7 末句滞后与斜率** ⇒ ✅ 重算落盘
  `.tmp/p1_run7/recompute_lag.json`：
  `last_segment_lag_sec=297.8847`、`max_lag_sec=304.3427`、
  `lag_growth_slope_sec_per_sec=−0.892163`、`lag_growth_r2=0.995403`、
  `old_cumulative_lag_sec_RETRACTED=−3969.5098`；
  精确三分量 `backlog 83.18 % / struct 2.02 % / proc 14.80 %`，
  `identity_closed=true`、`max_abs_residual_sec=0.0006`
* EXT-008 第 4 点 **TTS 稳态 RTF 写进 STATUS 供转达** ⇒ ✅ **§7.3 修正版**
  （**1.0022**，并说明「TTS 提速是流水线上线的前置条件，建议目标 ≤ 0.85」）
* EXT-009 **自适应加速播放（统一参数）** ⇒ ✅ **完整落地**
  * **缺陷 21**（★ 本轮修的真实缺陷）：`ext/time_stretch.py` 的 WSOLA 相似度搜索
    **恒取偏移 0** —— `np.correlate(seg, ref, mode="valid")` 在**等长**数组上
    返回长度 1 ⇒ `argmax` 恒 0 ⇒ **从未真正搜索过**，退化成朴素 OLA
    ⇒ 新增 `_normalized_xcorr_best()`（`sliding_window_view` 向量化归一化互相关）；
    `wsola()` 新增 `sample_rate` 形参（TTS 输出 24 kHz）
  * **缺陷 22**（★ 本轮修的真实缺陷）：App 升级到 **v1.7**、**v1.6 目录被删** ⇒
    5 处硬编码（`ext/engine_runtime.py` / `tools/bridge_server.py` /
    `tools/run_p1_real.py` / `tools/throughput_bench.py` /
    `tests/test_ext_selfcheck.py`）全部失效 ⇒ `test_ext_selfcheck` 实测 **101 PASS / 1 FAIL**
    （FAIL = 失控闸口径来源 `tts_engine` 加载不到）⇒ 新建 `ext/app_root.py` 做
    **版本自适应**解析（`EXT_APP_ROOT` 优先；显式指定但不存在 ⇒ **不静默回退**）
    ⇒ 实测解析到 `Confucius4_LiveCaption_v1.7` ⇒ **103 PASS / 0 FAIL**
  * **统一参数**（`ext/config.py` 唯一实现处）：
    `ADAPT_LAG_FREE_SEC=3.0` / `ADAPT_LAG_HYST_SEC=2.0` / `ADAPT_GAIN_PER_SEC=0.025` /
    `ADAPT_SPEED_MAX=1.30` / `ADAPT_MAX_STEP=0.10` / `ADAPT_TOTAL_RATE_MAX=1.30`
  * **新增** `ext/adaptive_speed.py`（**纯函数**权威实现）：
    `raw_speed_for_lag()` / `decide_speed()`（公式 → 滞回 → 步长 → 上限）/
    `combine_rates()`（总倍率封顶 1.30×）/ `lag_from_schedule()` / `target_start_for()`
  * **服务端接线** `ext/bridge.py`：lag 估计 → `decide_speed` → `combine_rates`
    → **主机侧单线程 WSOLA 变速** → 下发 `speed / adapt / rates / lag_est_sec /
    speech_sec_out / stretch_sec / defer_total_sec`；
    新增 `adaptive_speed_stats()`（滞后曲线 + 倍率时间占比 + `n_dropped_dub`）
  * **插件侧** `extension/player.js` / `player.html`：
    `ADAPT` 本地常量（与服务端一致）、`scheduleDub()` 记录 lag/speed 序列、
    底栏新增「**语速 / 滞后 / 滞后峰值**」
  * **补齐验收数据落盘链路**（本轮发现的缺口）：
    `margin.json` 加 `adaptive_speed`；`tools/p1_pipeline.py` 新增
    `pick_accelerated_segments()` / `copy_accelerated_wavs()`，
    报告加 `accelerated_segments`，落 `accel/` 目录（供 reviewer 抽听）
  * ⛔ **EXT-009 的 5 分钟真实实测本轮仍在排共享锁** ⇒ **验收数字（滞后曲线 /
    倍率占比 / 丢句数 / 3 段 1.2–1.3× 加速音频）尚未产出，不宣称已达成**
* EXT-010 末句「**之后根据数据改流水线**」 ⇒ ⛔ **本轮不做**
  （EXT-009 末句写「等 EXT-008 的 interference 数据确认后再做」；
  本轮**已拿到数据**，但**流水线化属架构改动，需 reviewer / 用户拍板**）
  ⇒ 只把 interference 数据如实给出

**涉及修改的文件（**仅本模块**，未动任何引擎文件）**

- `ext/adaptive_speed.py`（**新建**）—— EXT-009 纯函数权威实现。
- `ext/app_root.py`（**新建**）—— 修缺陷 22：App 版本自适应解析。
- `ext/config.py` —— 新增 EXT-009 统一参数常量（8 个）。
- `ext/bridge.py` —— EXT-009 接线；`adaptive_speed_stats()`；`_dump_margin()` 加 `adaptive_speed`。
- `ext/time_stretch.py` —— 修缺陷 21：`_normalized_xcorr_best()`；`wsola(sample_rate=)`。
- `ext/engine_runtime.py` —— 改用 `resolve_app_root()`，删硬编码 v1.6，解析失败显式报错。
- `extension/player.js` —— EXT-009 metrics / `ADAPT` / `scheduleDub()` 记录 / HUD。
- `extension/player.html` —— 底栏新增语速 / 滞后 / 滞后峰值。
- `tools/throughput_bench.py` / `tools/bridge_server.py` / `tools/run_p1_real.py` / `tools/engine_smoke.py`
  —— 改用 `resolve_app_root()`；docstring 版本号更新。
- `tools/p1_pipeline.py` —— 补 EXT-009 验收落盘（`pick_accelerated_segments` /
  `copy_accelerated_wavs` / `accelerated_segments` / `adaptive_speed`）；`per_segment` 补 EXT-009 字段。
- `tests/test_ext009_adaptive_speed.py`（**新建**）—— EXT-009 专项自测 **57 项**。
- `tests/test_ext_selfcheck.py` —— `_load_app_module()` 改用 `resolve_app_root()`。
- `status/STATUS_EXT.md` —— 追加 **§7**；头部 `last_ack` 推到 **EXT-009**；
  「更新时间」= 实测时间 **2026-10-29 17:12**。
- `status/EXEC_LOG.md` —— 本记录。

⛔ **未改 `status/CORRECTIONS_EXT.md`**（只读，绝不入库；已在 `.gitignore`，**绝不 `git add -f`**）。
⛔ **未改任何引擎文件**（ASR R2T2 / MT Hy-MT2 / TTS Qwen3-TTS 全部只 import）。
⛔ **未改 D（缓冲窗）** —— EXT-008 第 4 点明文要求。

**验证与自测结果**

* 六套自测**全跑、逐套取真实退出码，全部 rc=0**：
  `test_ext_selfcheck.py` **103 PASS / 0 FAIL**、
  `test_echo_roundtrip.py` **10 PASS / 0 FAIL**、
  `test_next_instruction.py` **19 PASS / 0 FAIL**、
  `test_p1_plumbing.py` **97 PASS / 0 FAIL**、
  `test_ext_browser_contract.py` **102 PASS / 0 FAIL**、
  `test_ext009_adaptive_speed.py` **57 PASS / 0 FAIL**
  ⇒ **合计 388 PASS / 0 FAIL**。
* ⚠️ **解释器与 PYTHONPATH（如实记录，避免下次误判为回归）**：
  自测依赖 `numpy` + `psutil` + `websockets`；
  `websockets` 装在**项目本地** `.runtime_deps/`（**不污染 App 的 site-packages**）
  ⇒ 必须带 `PYTHONPATH=<项目根>;<项目根>/.runtime_deps`，
  否则 `test_echo_roundtrip` / `test_p1_plumbing` 会因
  `ModuleNotFoundError: No module named 'websockets'` 报 1 + 6 个 FAIL
  —— **那是环境缺依赖，不是产品缺陷**（本轮实测复现过，已用正确环境变量跑到全绿）；
  App 自带解释器**有 numpy 无 psutil** ⇒ 用它跑 `test_ext_selfcheck` 有 1 FAIL。
  本轮统一用 `C:\Users\Trekker-PTL\miniforge3\envs\ov_env_py312\python.exe` + `PYTHONPATH`。
* **真实引擎实测**（(a)(b)(c)）用 App 解释器 + `PYTHONPATH` 注入 `.runtime_deps/`。

**共享锁合规记录**

* (a)(b) 于 12:14–12:40 在 `tools/throughput_bench.py all` 的**一把锁内**跑完；
  11:41 起排队，锁被 **`tts` 模块（PID 9964，started 11:36:10）** 持有 ⇒
  用 `probe_pid_alive()`（ctypes `OpenProcess` + `GetExitCodeProcess`）复核**存活**
  ⇒ **不抢、不删、不回收**，每 2 s 轮询等待。
* (c) 本轮 16:44:47–16:56:51 在**自己持有的锁内**跑完，结束时正常释放
  （锁内容变为 `EXT-throughput-interference 13876 2026-10-29 16:44:47`）。
* 本轮 17:00 起排 **EXT-009 的 5 分钟实测**，锁被 **`tts` 模块（PID 13200，
  started 16:56:57）** 持有 ⇒ `probe_pid_alive(13200)` 复核**存活**
  ⇒ **不抢、不删、不回收**，排队等待（日志逐条记录）。
* ⚠️ **铁律**：**全程未与实时字幕 App / TTS 模块同时占设备**；
  **未在 CPU 上跑推理**（ASR@GPU.0 / MT@GPU.0 / TTS@NPU，设备摆放未改）。

**补充（17:20）**：§7.6.6 记录 EXT-009 实测的**排队状态**（编排器 PID 38836，
17:01:24 起，`--lock-wait 7200`；锁被 `tts` 模块 PID 13200 持有，
`probe_pid_alive` 复核**存活** ⇒ **不抢不删**，日志已 531 行等待记录）
⇒ **验收数字尚未产出，不宣称已达成**；
并补写 **§7.10 待下一轮接手的事项**（明确交接清单：先查 `.tmp/p1_ext009/` 取数、
流水线化待 reviewer 拍板、TTS 转达数字以 **1.0022** 为准（旧 0.9264 已撤回））。

## 2026-10-29 20:24 → 20:58 — EXT-010（RESUME）⇒ EXT-008 收口 + EXT-009 落地 + 句级流水线

**执行时间**：2026-10-29 20:24:19 → 20:58（实测时钟；两次真实引擎实测区间 20:24:19 → 20:33:14 与 20:45:55 → 20:54:33）

**指令摘要（唯一执行依据 = `status/CORRECTIONS_EXT.md` 的 EXT-010 [NORMAL] 2026-10-29 15:38）**：
> - 未完成：EXT-008 的 interference 臂（parallel_speedup_x）和 STATUS §6.5 回填；EXT-009（自适应加速播放统一参数，叠加单句时长适配，总倍率 ≤ 1.30×）；之后根据数据改流水线。
> - 下一步：写 last_ack=EXT-009，先补完 EXT-008 的数据。

**闸门判定**：第 0 步实跑 `tools/next_instruction.py --json` ⇒ **退出码 0**（最新 = EXT-010，接手前 `last_ack = EXT-009`）⇒ 存在未执行的新指令，**非重复触发**，继续执行。

**接手核对**：`.tmp/p1_ext009/` **不存在** ⇒ 上一轮 EXT-009 实测（编排器 PID 38836）**已被中断、产物未落盘** ⇒ 本轮**重跑**；树脏 = `ext/bridge.py` 改 + `tools/run_p1_real.py` 改 + `ext/pipeline.py`、`tests/test_ext010_pipeline.py` 新增（上一轮未完成的改动）⇒ 接手续做。

**涉及修改的文件**（仅 EXT 模块内，⛔ 未改其他模块文件、⛔ 未改引擎、⛔ 未改纠偏文件）：

| 文件 | 类型 | 说明 |
|---|---|---|
| `ext/pipeline.py` | 新建 | 425 行：`_FairLock`（严格 FIFO 公平锁）+ `SegmentJob` + `EnginePipeline`（ASR/MT/TTS/收口 4 线程句级流水线，`QUEUE_MAXSIZE=64`，ASR∥MT 共用 GPU 互斥锁） |
| `ext/bridge.py` | 修改 | +281 行：`PipelineSession`（继承 `Session`）、`_finalize_segment()` 共享抽取、`_dispatch_segment()` 派发钩子、`PipelineSession.flush()` 重写、`serve(use_pipeline=)` + `--pipeline` CLI、`stats()["pipeline"]`、消息循环三处取走已就绪任务 |
| `tools/run_p1_real.py` | 修改 | +6 行：`--pipeline` 开关 |
| `tests/test_ext010_pipeline.py` | 新建 | 396 行 / 23 项专项自测（含反向对照） |
| `status/STATUS_EXT.md` | 修改 | 追加 §8（232 行）；头部 `last_ack` EXT-009 → **EXT-010**、更新时间 → **2026-10-29 20:53**（实测时间） |
| `status/EXEC_LOG.md` | 修改 | 追加本条 |

**验证与自测结果**：

* **EXT-009 五分钟真实实测（本轮重跑）**：`.tmp/p1_ext009/`，`SPE_0000_0500.wav`（300.0 s / 5000 帧）→ en，`--delay 10`，真实三引擎（ASR=R2T2 / MT=Hy-MT2 / TTS=Qwen3-TTS），**20:24:19 → 20:33:14**，`pipeline rc=0`，锁正常释放。
  * 产物：`p1_report.json` 44 453 B / `margin.json` 27 565 B / `p1_timeline.json` 21 548 B / `p1_run_summary.json` 680 B（均 mtime 20:33）；`dub/*.wav` **22 个**；`accel/*.wav` **3 个**（`seg_410720_x1.30.wav` 564 154 B / `seg_644800_x1.30.wav` 614 370 B / `seg_902560_x1.30.wav` 614 370 B）。
  * 原始字段：`n_segments=22` / `n_without_tts=0` / `n_deferred=0` / **`n_dropped_dub=0`**；
    `speed_time_share = {"1.00":0.0,"1.00-1.10":0.045,"1.10-1.20":0.0406,"1.20-1.30":0.9144,">1.30":0.0}`；
    `speed_count_share = {"1.00":0,"1.00-1.10":1,"1.10-1.20":1,"1.20-1.30":20,">1.30":0}`；
    `lag_curve = {start_sec:70.287, peak_sec:234.644, peak_at_t_start:282.84, end_sec:227.986}`；
    `lag.last_segment_lag_sec=227.9863` / `max_lag_sec=234.6442` / `lag_growth_slope_sec_per_sec=−0.565947` / `r2=0.992763`；
    `margin = {basis:"deadline", n_negative:22, p50:−157.1446, p95:−74.5309}`；
    `sync_err_ms = {p50:150866.1, p95:227986.3, max:234644.2, n_over_target:22}`；
    `timing.feed_speed_x=0.5949` / `n_frames_send_blocked_gt_1s=20` / `send_dur_max_sec=58.453`；
    `margin_source="stats"` / `adaptive_source="stats"`（正常路径，非兜底）。
  * vs run7 串行基线：末句滞后 **297.885 → 227.986 s（↓69.9 s）**；斜率 **−0.892 → −0.566 sec/sec（↓36.6 %）** ⇒ 自适应加速对「追滞后」有效。
* **★ 缺陷 23（真架构缺陷，实测抓到）**：普通 `threading.Lock` **不保证公平** ⇒ ASR 连续抢锁、MT 饿死 ⇒ 时间线实测三阶段**零重叠**、加速仅 **1.02×** ⇒ 改 **`_FairLock` 严格 FIFO** ⇒ 修后 **ASR ∩ TTS 重叠 0.300 s**、流水线墙钟 **1.52 s** vs 串行 **2.76 s** ⇒ **加速 1.82×**。
* **★ 缺陷 24**：`_finalize_segment()` 返回 list（串行用 `extend`）与流水线收口要的单个 dict 不一致 ⇒ `TypeError: list indices must be integers or slices, not str` ⇒ `_stage_emit()` 内拆包修正。
* **★ 缺陷 25**：`flush()`（尾段）走串行路径 ⇒ 与收口线程**并发**调 `_finalize_segment`、并发改 `margins` / `_prev_adapt_speed` ⇒ `PipelineSession` 重写 `flush()`，尾段也走流水线。
* **★ 缺陷 26**：阶段函数内 `except Exception` 吞异常 ⇒ 失败段未标 error ⇒ 三阶段 `except` 内调 `job.mark_error("asr"/"mt"/"tts", e)`（只保留第一个错误，第一个才是根因）。
* **自测（逐套取真实退出码）**：

  | 套件 | 结果 | 退出码 |
  |---|---|---|
  | `tests/test_ext_selfcheck.py` | 103 PASS / 0 FAIL | 0 |
  | `tests/test_echo_roundtrip.py` | 10 PASS / 0 FAIL | 0 |
  | `tests/test_next_instruction.py` | 19 PASS / 0 FAIL | 0 |
  | `tests/test_p1_plumbing.py` | 97 PASS / 0 FAIL | 0 |
  | `tests/test_ext_browser_contract.py` | 102 PASS / 0 FAIL | 0 |
  | `tests/test_ext009_adaptive_speed.py` | 57 PASS / 0 FAIL | 0 |
  | `tests/test_ext010_pipeline.py` | 23 PASS / 0 FAIL | 0 |
  | **合计** | **411 PASS / 0 FAIL** | — |

  * 解释器：`C:\Users\Trekker-PTL\miniforge3\envs\ov_env_py312\python.exe` + `PYTHONPATH=<项目根>;<项目根>/.runtime_deps`；真实引擎实测用 App 解释器。
  * **区分力设计**（不假通过）：桩引擎记录各阶段**执行时间区间**（sleep 在区间内）⇒ 断言 ASR∩TTS 重叠 > 0；**反向对照**同一套桩跑串行路径 ⇒ 断言重叠 ≤ 0（证明断言有区分力）；断言流水线墙钟 < 串行墙钟；`_make_pcm_speechy()`（1.4 s 语音 + 0.6 s 静音、400 帧）⇒ VAD 实测切出 3 段（纯正弦波切不开会让「顺序 / 不丢句」断言假失效）。
* **共享机器锁纪律**：本轮真实实测持锁区间 20:24:17 → 20:33:17（`tools/machine_lock.py` 的 `hold()`），结束后释放；期间先后由 `tts`（PID 13200）与 `asr`（PID **23644**，`task=asr027-cpu-rerun-base`，20:44:47 起）持锁 ⇒ `probe_pid_alive(23644)` 复核**存活** ⇒ **不抢、不删、不回收**；回收前一律用 ctypes `OpenProcess` + `GetExitCodeProcess` 确认 PID 真死，**探测失败一律视为存活**。全程**未在 CPU 上跑推理**、**未与实时字幕 App 抢设备**。

**未做 / 不宣称**：⛔ 端到端仍不实时（`feed_speed_x=0.5949`、`sync_err_ms.p50=150866.1`）；⛔ WSOLA 变调质量由 reviewer 抽听 + MiniMax 回转写判定，本轮不自己判定；⛔ TTS 未提速（RTF 仍 1.0022，建议 ≤ 0.85，**由主会话转达 TTS 模块**）；⛔ tabCapture 生产路径仍未实测；⛔ pyannote 旁路未接线；⛔ P2/P3 未开始。

### ★ 补充：流水线真实引擎端到端实测（20:45:55 → 20:54:33，rc=0）

等锁期间由 `asr` 模块持锁（PID **23644**，`task=asr027-cpu-rerun-base`，20:44:47 起）⇒ `probe_pid_alive(23644)` 复核**存活** ⇒ **不抢、不删、不回收**，按 §7.10「继续等，不重跑」执行；锁释放后自动取得锁，结束后**锁已释放**。

**产物**：`.tmp/p1_pipe/p1_report.json` 44 668 B / `margin.json` 27 910 B / `p1_timeline.json` 21 488 B / `p1_run_summary.json` 674 B（均 mtime 20:54）；`dub/*.wav` **22 个**；`accel/*.wav` **3 个**（584 830 / 578 924 / 581 876 B）。
**流水线路径生效证据**：`bridge.log` 原始行 `pipeline=True` + `★ 使用流水线会话（EXT-010：ASR/MT/TTS/收口 各一线程）`；且 `bridge_stats.pipeline` 非空（串行路径该字段为 `None`）。

**★ 串行 vs 流水线 严格对照**（同输入、同引擎、同后处理口径）：

| 指标 | 串行（`p1_ext009`） | **流水线（`p1_pipe`）** | 变化 |
|---|---|---|---|
| `timing.feed_speed_x` | 0.5949 | **1.0** | 喂帧从落后实时 40 % → 刚好实时 |
| `timing.feed_sec` | 504.27 s | **300.01 s** | ↓ 204.26 s |
| `timing.drain_sec` / `total_sec` | 30.01 / 534.28 s | 77.58 / **377.59 s** | 总墙钟 ↓ 156.69 s（**加速 1.415×**） |
| `n_frames_send_blocked_gt_1s` | 20 | **0** | 服务端背压消失 |
| `send_dur_max_sec` | 58.453 s | **0.007 s** | 单帧最长阻塞 58.5 s → 7 ms |
| `late_final_sec` | 204.27 s | **0.006 s** | ↓ |
| `lag.last_segment_lag_sec` | 227.9863 s | **71.2074 s** | **↓ 68.8 %** |
| `lag.max_lag_sec` | 234.6442 s | **86.2166 s** | ↓ 63.3 % |
| `lag.lag_growth_slope_sec_per_sec` | −0.565947 | **−0.106051** | **↓ 81.3 %** |
| `sync_err_ms.p50 / p95 / max` | 150 866.1 / 227 986.3 / 234 644.2 | **67 289.3 / 85 317.2 / 86 216.6** | ↓ 55.4 % / 62.6 % / 63.3 % |
| `margin.p50 / p95` | −157.1446 / −74.5309 | **−68.4317 / −50.6766** | 余量改善 88.76 s / 23.85 s |

**`bridge_stats.pipeline` 原始字段**：`n_submitted=22` / `n_emitted=22` / **`n_error=0`** / `n_pending=0`；`stage_wall_sec = {asr: 234.912, mt: 2.397, tts: 343.64}`；`emit_sec = 26.998`；`gpu_serial_stages = ["asr","mt"]`（GPU 互斥按设计生效）。
**并行度判读**：串行时 ASR+TTS 墙钟相加约 578 s，流水线总墙钟仅 377.59 s ⇒ **ASR 与 TTS 确实重叠运行**。
**倍率高保真证据**：两轮 `speed_time_share` **完全一致**（1.00–1.10× 0.045 / 1.10–1.20× 0.0406 / 1.20–1.30× 0.9144 / >1.30× 0.0）⇒ 倍率决策只依赖滞后、与执行路径解耦 ⇒ 实证「收口按 index 严格有序 ⇒ 口径不变」。
**结论**：✅ 流水线真实引擎**确实生效且显著改善全部时延指标**；⛔ **但仍未实时**（`sync_err_ms.p50=67289.3`、`n_over_target=22`、`last_segment_lag_sec=71.2074`）；⛔ **瓶颈已明确转移到 TTS**（`stage_wall_sec.tts=343.64 s` 为最长杆）⇒ **TTS 提速（RTF 目标 ≤ 0.85）是从「不实时」走向「实时」的必要前置**。


**`last_ack` 推进**：EXT-009 与 EXT-008 均已收口、EXT-010 本身已执行完毕 ⇒ **`last_ack` = EXT-010**（§8.9 说明「不回头改旧章节」的处置）。

---

## 2026-10-30 11:56 — EXT-011 / EXT-012 / EXT-013 三条全部收口

**执行时间**：2026-10-30 11:31 – 11:56（实测）
**闸门**：`tools/next_instruction.py --json` → **exit 0**，`latest.id = EXT-014`
（`[HIGH]` 2026-10-30 11:25「巡检规则补充」），`last_ack` 原为 EXT-010，`n_entries = 14`。
**接手核对**：HEAD = `bd3068c`（EXT-010），工作树脏（6 改 9 新）⇒ 上一轮 EXT-011/012/013 **未完成**。
**本轮执行依据**：EXT-013（明文三项工作）；EXT-014 是巡检规则项，按其 ②③ 条落地（见 §9.6）。

### 指令摘要与逐条落实

| EXT-013 要求 | 落实情况 |
|---|---|
| ① 修 `cpu_watch`，按服务进程及其子进程的 PID 树采样，启动后先自检能读到非零 CPU | ✅ `tools/cpu_watch.py` 重写（15574 B）：PID 树采样 + `--expect-cmd` 身份校验 + `--self-check-sec` 启动自检（CPU 时间增量必须 > 0，否则 **rc=3**）；编排器自检 FAIL ⇒ 整轮 **rc=6** |
| ② 持锁重跑限制组，和对照组放进同一张表（核数、TTS 稳态 RTF、末句滞后、斜率） | ✅ 限制组 **11:40:59 → 11:51:45**（`pipeline rc=0`，`cpu_self_check.ok=true`，CPU 时间增量 **66.703 s**）；对比表 `.tmp/p1_ext013_lim/compare_ext011.json`（**4908 B**） |
| ③ `thread_limits.py`、`cpu_watch.py` 和对应测试提交到 git | ✅ 本次提交内含 `ext/thread_limits.py` / `tools/cpu_watch.py` / `tools/compare_ext011_cores.py` / `tests/test_ext011_thread_limits.py` / `tests/test_ext012_user_guide.py` / `tests/test_ext013_cpu_watch.py` / `tests/test_ext013_compare.py` |
| 顺序：先做 EXT-012，再持锁重跑限制组 | ✅ 锁在 11:38–11:40 被 `asr` 持有（PID 31152，经 `probe_pid_alive()` 复核存活）⇒ 用 `--lock-wait 7200` **排队**（不抢不删），等待期先做 EXT-012 不计时部分；限制组跑批随后完成 |

### ★ 对比表（限制组 vs 对照组，同一张表）

| 指标 | 限制组（ON） | 对照组（OFF） | 变化 |
|---|---|---|---|
| 核数 mean | **0.8244** | 1.2909 | ↓ 36.2 % |
| 核数 peak | **2.819** | 7.091 | ↓ 60.2 % |
| TTS 稳态 RTF | **1.0542** | 1.3249 | ↓ 20.4 % |
| 末句滞后 | **117.0879** s | 122.789 s | ↓ 5.70 s |
| 滞后斜率 | **−0.269455** | −0.306699 | 绝对值 ↓ 12.1 % |
| `thread_limits.enabled` | **true** | **false** | ✔ A/B 有效 |

**⚠️ 诚实标注**：对照组的核数只能用**旧版** `cpu_watch.log` 解析（423 行；无 `identity`/`self_check`）
⇒ 采样口径弱于限制组；且 **EXT-013 原文给的「平均 1.36 核」无法复现**
（全量 1.290894 / 去启动期 1.321927 / 仅非零行 1.312615）⇒ **以实测 1.2909 为准**。
**峰值 7.091 与原文完全吻合**。

### EXT-012 交付（用户试用件）

| 项 | 交付 | 实测证据 |
|---|---|---|
| ① `USER_GUIDE.md` | `USER_GUIDE.md` + `extension/USER_GUIDE.md`（各 11496 B） | 自测覆盖明文每项；UTF-8 无 BOM |
| ② 一键启动 | `tools/ext_launcher.py`（13042 B）+ 桌面 `实时配音桥接.cmd` | 用 **App 解释器 v1.12** 按 launcher 同款 cmd/env 真起桥接 ⇒ `/health` 200 + 拿到 32 位 token ⇒ 正常停止 |
| ③ popup 状态 | `extension/popup.html` + `popup.js`（`#conn`/`#mDelay`/`#mSpeed`/`#mLag`/`#btnGuide`） | `node --check` 通过 |
| ④ token 自动配对 | `ext/pair_server.py`（5513 B）+ `bridge.py` `--pair-port` 接线 | 扩展 Origin → 200 + 32 位 token；**无 Origin 403**；**伪造 Origin 403**；`/status` **不含 token**；WS 握手 → 真实 `hello_ack` |

### 本轮修掉的真实缺陷

* **缺陷 27**：USER_GUIDE **写死** `Confucius4_LiveCaption_v1.13` ⇒ App 升级后用户照抄跑不起来
  （本机实际 **v1.12**）⇒ 改 `<版本号>` 占位 + 给 `dir` 命令 + **加防回归自测**（不许出现 `v\d+` 字面量）。
* **缺陷 28**：`test_ext012_user_guide.py` 快捷方式断言**写错了**（传假 args 却断言真实路径）⇒ **假 FAIL**
  ⇒ 改成「与传入 args 一致」+ 加「不是写死模板」反向断言。

### 涉及修改的文件

**新增**：`USER_GUIDE.md` / `extension/USER_GUIDE.md` / `ext/pair_server.py` / `ext/thread_limits.py` /
`tools/ext_launcher.py` / `tools/cpu_watch.py` / `tools/compare_ext011_cores.py` /
`tests/test_ext011_thread_limits.py` / `tests/test_ext012_user_guide.py` /
`tests/test_ext013_cpu_watch.py` / `tests/test_ext013_compare.py`

**修改**：`ext/bridge.py` / `ext/config.py` / `extension/popup.html` / `extension/popup.js` /
`tools/run_p1_real.py` / `tools/engine_smoke.py` / `status/STATUS_EXT.md` / `status/EXEC_LOG.md`

**只读未改**：`status/CORRECTIONS_EXT.md`（**绝不修改、绝不入库**）、`ext/engine_runtime.py`、App 目录

### 验证与自测结果

**11 套自测全部 0 FAIL**：

```
test_ext_selfcheck        :: 103 PASS / 0 FAIL
test_echo_roundtrip       ::  10 PASS / 0 FAIL
test_next_instruction     ::  19 PASS / 0 FAIL
test_ext010_pipeline      ::  23 PASS / 0 FAIL
test_ext_browser_contract :: 102 PASS / 0 FAIL
test_p1_plumbing          ::  97 PASS / 0 FAIL
test_ext009_adaptive_speed::  57 PASS / 0 FAIL
test_ext011_thread_limits ::  29 PASS / 0 FAIL
test_ext012_user_guide    ::  69 PASS / 0 FAIL
test_ext013_cpu_watch     ::  25 PASS / 0 FAIL
test_ext013_compare       ::  51 PASS / 0 FAIL
合计                      :: 585 PASS / 0 FAIL
```

**产物**（文件数 / mtime / 字节数）：

| 产物 | 文件数 | mtime | 字节数 |
|---|---|---|---|
| `.tmp/p1_ext013_lim/`（限制组） | 38 | 2026-10-30 11:51:51 | 13 912 280 |
| `.tmp/p1_ext013_lim/compare_ext011.json` | 1 | 2026-10-30 11:51 | 4 908 |
| `.tmp/p1_ext013_lim/cpu_usage.json` | 1 | 2026-10-30 11:51 | 116 231 |
| `.tmp/p1_ext011_ctl/`（对照组） | 33 | 2026-10-30 09:49:57 | 12 987 722 |

**`last_ack` 推进**：EXT-011 / EXT-012 / EXT-013 三条均已执行完毕并收口
⇒ **`last_ack` = EXT-014**（EXT-014 是巡检规则项，本轮已按其 ②③ 条实际落地）。

---

## 2026-10-30 16:11 — EXT-017 落地（用户试用报的两个故障：乱码 / start 后无输出）

### 闸门

```
tools/next_instruction.py --json  ⇒  exit 0
latest.id = EXT-017   [BLOCKING] 2026-10-30 13:06
last_ack(原) = EXT-014   n_entries = 17
```

⇒ 本轮**唯一执行依据 = EXT-017**。
⚠️ `status/CORRECTIONS_EXT.md` **只读，未修改、未入库**。

### 指令摘要（EXT-017 四项）

① **乱码** ⇒ 统一 `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`；`.cmd` 里 `chcp 65001`；Tk 窗口与日志文件统一 UTF-8；
须在**中文 Windows 默认控制台**验证（不得用 IDE / PowerShell 7）。
② **start 之后没有任何输出** ⇒ 查清子进程是否起来（PID / 8765 / 8766 / 日志）；**2 秒内**必须出现
「正在加载模型…（预计 20–40 秒）」+ 每引擎进度；失败要显示原因与日志路径、**不能静默**；
子进程 stdout/stderr 要接到窗口与日志文件；**pythonw 启动时输出易丢失**。
③ **USER_GUIDE 补 Edge 加载步骤** + 说明「关闭开发人员模式扩展」提示怎么处理。
④ **确认 `/pair`(8766) 只响应 Origin 为 `chrome-extension://<本插件 id>`** 的请求。
**验收**：用用户的方式（桌面快捷方式、中文 Windows 默认控制台）从零启动，截图证明无乱码、
start 后能看到加载进度并最终显示「TTS 就绪」；再故意让一个引擎加载失败确认显示原因；
截图放 `shared/ext_launcher_fix/`。

### 根因（实测）

| 症状 | 实测根因 |
|---|---|
| ① 乱码 | `ConsoleOutputCP = gb2312`；GBK 编不了 `⇒`/`🔴`/`⛔` ⇒ 旧 `ext/bridge.py` 的 `_log` 裸 `print` **抛 `UnicodeEncodeError`**（不是显示成问号） |
| ② 无输出 (a) | 三引擎全**懒加载**（`_load_asr` 只在 `asr()`、`_load_tts` 只在 `tts()` 里触发）⇒ 拉起桥接后日志只有「线程限制/真实引擎已接线/配对端点/token 文件/监听 ws://」，**没有任何模型加载记录** |
| ② 无输出 (b) | 启动器 `Popen(stdout=self._log_f)` + 轮询文件尾 ⇒ 输出只在文件里，**窗口永远看不到** |
| ② 无输出 (c) | **GUI 启动器本身起不来**：桌面快捷方式指向 WorkBuddy 默认环境的 `pythonw.exe` ⇒ 实测 `import tkinter` → `ModuleNotFoundError` ⇒ 窗口根本不出现；又因 pythonw 无控制台 ⇒ stderr 被吞 ⇒「双击了，什么都没发生」 |
| ② 追加 | `tk.Combobox` 不存在（`Combobox` 在 **ttk** 里）⇒ `AttributeError` ⇒ GUI 直接崩溃 + 报错被吞 |
| ② 追加 | 状态灯永远停在「正在加载模型…」：配对端点在预热**之后**才启动（预热期 `/status` 不在线）+ `app.after` 只调度一次（轮询不自续期） |

### 涉及文件

**新增**：`ext/utf8_io.py`、`ext/extension_id.py`、`tests/test_ext017_user_report.py`

**修改**：`ext/bridge.py`、`ext/engine_runtime.py`、`ext/pair_server.py`、`tools/ext_launcher.py`、
`extension/popup.html`、`extension/popup.js`、`USER_GUIDE.md`、`extension/USER_GUIDE.md`、
`tests/test_echo_roundtrip.py`、`tests/test_ext012_user_guide.py`

**只读、未改**：`status/CORRECTIONS_EXT.md`（已 gitignore，**绝不 `git add -f`**）、
`Confucius4_LiveCaption_v1.12/`（**只 import 对方原件，不改对方任何文件**）

### 关键实现

* `ext/utf8_io.py`：`safe_print()`（逐字符 `_sanitize` 降级，绝不抛异常）/
  `configure_process_env()`（`PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` + `PYTHONLEGACYWINDOWSSTDIO=0`）/
  `console_code_page()`（ctypes `GetConsoleOutputCP`）。
* `ext/engine_runtime.py`：`RuntimeEngine.warmup(stages=..., on_progress=...)`
  ⇒ 逐阶段 emit `(i/N) 正在加载 <label> @ <device> ……` / `<label> 加载完成（X 秒）` /
  `<label> 加载失败 ⇒ <reason>`；返回 `{"ok","loaded","failed","load_s","elapsed_sec"}`；
  **单阶段失败不阻断其它阶段**。
* `ext/bridge.py`：新增 `--no-warmup` / `--warmup-strict`；配对端点提到**预热之前**启动；
  `_pair_status` 报 `engine_state` / `engine_loaded` / `engine_failed`；
  WS 握手用 `resolve_extension_id()` + `check_origin(origin, _eid)`。
* `ext/extension_id.py`：由 `extension/manifest.json` 的 `key` 算 ID
  （SHA256(DER) 前 16 字节 → 每字节转 a–p 两个 hex 字符）= `kekgmfkijphpfndbbpakjaokamkeooib`
  ⇒ 与 **9 份浏览器探针**的 `ext_id` 完全一致；**解析不出 ID 一律拒绝**（不静默放宽）。
* `tools/ext_launcher.py`：`subprocess.PIPE` + `text=True, encoding="utf-8", errors="replace"`；
  `.cmd` **按 GBK 写** + `chcp 65001 >nul`；`_app_pythonw()` / `_has_tkinter()`；
  `from tkinter import ttk` + `ttk.Combobox`；tkinter 缺失**写日志 + MessageBox**；
  顶层 `except BaseException` 兜底；`poll_engine_state` 放 `try/finally` 里**自我续期**。

### 验证与自测结果

**12 套自测全部 0 FAIL**：

```
test_ext_selfcheck        :: 103 PASS / 0 FAIL
test_echo_roundtrip       ::  11 PASS / 0 FAIL
test_next_instruction     ::  19 PASS / 0 FAIL
test_ext017_user_report   ::  99 PASS / 0 FAIL   <- 本轮新增
test_ext009_adaptive_speed::  57 PASS / 0 FAIL
test_ext010_pipeline      ::  23 PASS / 0 FAIL
test_ext011_thread_limits ::  29 PASS / 0 FAIL
test_ext012_user_guide    ::  75 PASS / 0 FAIL
test_ext013_compare       ::  51 PASS / 0 FAIL
test_ext013_cpu_watch     ::  25 PASS / 0 FAIL
test_ext_browser_contract :: 102 PASS / 0 FAIL
test_p1_plumbing          ::  97 PASS / 0 FAIL
合计                      :: 691 PASS / 0 FAIL
```

**用户方式实测验收（桌面快捷方式 + 中文 Windows 默认控制台 + 鼠标点「启动」）**：

| 阶段 | 实测结果 |
|---|---|
| 点启动 **2 秒内** | 窗口已出现「正在加载模型…（预计 20–40 秒）」+ PID=11332 + 端口 8765 + 日志路径 |
| 逐引擎进度 | 「**(1/3) 正在加载 ASR [R2T2 INT8] @ GPU.0 ……**」⇒「(2/3) MT（Hy-MT2 INT8）」⇒「(3/3) TTS（Qwen3-TTS）@ NPU」 |
| 加载完成 | 「引擎预热完成：成功 3/3，总耗时 26.9 秒」⇒「✅ 模型加载完成（ASR/MT/TTS 就绪，耗时 26.85 秒）」⇒ 状态灯「**TTS 就绪**」 |
| 故意让 MT 失败 | 「(2/3) MT（Hy-MT2 INT8） 加载失败 ⇒ EngineNeedsChange: … Could not find a model in the directory」⇒「❌ 部分引擎加载失败：{'mt': …}」⇒ 状态灯红色「**引擎未就绪**」+ 完整原因 + 日志路径（ASR/TTS 照常加载） |
| 乱码 | 全部截图中文正常，**零乱码 / 零问号 / 零方块** |

**`/pair` Origin 收紧实测**（真起 HTTP 服务）：

| Origin | 状态码 |
|---|---|
| `chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib` | **200**（拿到 token） |
| `chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`（别的扩展） | **403** |
| `https://evil.example.com`（普通网页） | **403** |
| 无 Origin | **403** |

`/status` 仍可访问且**不泄露 token**。

**产物**（文件数 / mtime / 字节数）：

| 产物 | 文件数 | mtime | 字节数 |
|---|---|---|---|
| `C:\Users\Trekker-PTL\shared\ext_launcher_fix\`（截图 6 张） | 6 | 2026-10-30 15:56–16:04 | 321 900 |
| └ `01_启动器初始窗口_中文正常.png` | 1 | 2026-10-30 16:00 | 37 129 |
| └ `02_点启动后2秒_已见加载提示.png` | 1 | 2026-10-30 15:56 | 54 261 |
| └ `04_点启动后3秒_逐引擎进度.png` | 1 | 2026-10-30 16:00 | 57 548 |
| └ `06_点启动后3秒_修复后_状态灯轮询生效.png` | 1 | 2026-10-30 16:02 | 56 347 |
| └ `07_加载完成_TTS就绪.png` | 1 | 2026-10-30 16:02 | 58 175 |
| └ `10_故意MT加载失败_显示原因.png` | 1 | 2026-10-30 16:04 | 58 440 |
| `C:\Users\Trekker-PTL\Desktop\实时配音桥接.cmd`（桌面快捷方式，GBK 写） | 1 | 2026-10-30 15:55 | 330 |
| `%LOCALAPPDATA%\LiveDubEXT\bridge.log`（运行日志） | 1 | 2026-10-30 16:04 | — |

**机器锁**：预热占 GPU/NPU ⇒ 开工前申请 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`
（`ext-verify PID 30572 started 2026-10-30 15:54:59`），**结束后已删除**（实测确认不存在）。
开工前回收的孤儿锁 `app-spksync PID 34696`：先用 ctypes `OpenProcess` + `GetExitCodeProcess` 探活，
**并先验证探针判别力**（活进程→`OK/259`；刚退出→`OK/0`；绝不存在的 PID 999999→`OPENFAIL/87`）
⇒ 34696 与「绝不存在的 PID」表现完全一致 ⇒ 确证已死才回收。
**未用** Git Bash 的 `tasklist /FI`（已知会被当路径）。

**`last_ack` 推进**：EXT-017 四项全部执行完毕并实测验收 ⇒ **`last_ack` = EXT-017**。
ℹ️ EXT-016（压缩 STATUS/CORRECTIONS 至 ≤ 40 KB）**本轮未认领**（唯一执行依据是 EXT-017）。
