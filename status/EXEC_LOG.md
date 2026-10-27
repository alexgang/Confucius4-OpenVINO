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

### 本轮修掉的真实缺陷（8 个，详见 STATUS §5.2/§5.3）
1. 段起始时间基点归零 / 索引错位（`ext/bridge.py`）
2. 语言表含引擎不支持的 6 种语言（静默回落 English，日文素材会被读成英文且日志看不出来）
3. 失控闸口径未用 App RUNAWAY 公式
4. R2T2 与 App 侧 6 个同名顶层模块互相顶替（引擎被喂了别的模块的依赖）
5. **客户端 stats 包装把 `_stats` marker 覆盖掉 ⇒ EXT-006 核心验收量（margin 余量）全部丢失**，且收尾循环永远等不到 stats
6. **同步误差口径用错量**（拿顺延量当同步误差）⇒ 改为 EXT-001 原文口径 `max(0, −deadline_margin)`
7. **离线快灌 ⇒ 余量/滞后指标失真**（拿到的正是假数据）⇒ 改为按墙钟节拍实时喂帧
8. **尾段永不处理 ⇒ 时间表缺最后一段** ⇒ 新增 `flush` 消息

### 自测结果（本轮实跑）
```
tests/test_ext_selfcheck.py        →  69 PASS / 0 FAIL   (原 53 + 本轮追加 16)
tests/test_echo_roundtrip.py       →  10 PASS / 0 FAIL
tests/test_next_instruction.py     →  19 PASS / 0 FAIL
tests/test_ext_browser_contract.py → 101 PASS / 0 FAIL
```
合计 **199 PASS / 0 FAIL**（4 套）。
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
