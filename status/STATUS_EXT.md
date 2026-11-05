# STATUS_EXT
last_ack: EXT-038
更新时间: 2026-11-05 12:31
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）与 archive/STATUS_EXT_upto_20261105.md（34 816 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10；逐条明细见 `status/notes/`
当前任务: **§30 EXT-037 + EXT-038 交卷** —— ✅ 丢 3.5 s 已修（覆盖率 100%）✅ 口径重写（fixed/result 分列 + `seg_len`）✅ compare 口径（`over_ws`=1.00）✅ 默认 D=20 s（两侧一致）✅ 真实 e2e `20261105_112057` ｜⛔ sync 有符号 P95 = 16130.6 ms ≫ 300 ms 未达标（`D_needed` **33.652 s** ⇒ `RTF_out` **1.0562** 饱和 ⇒ **光调 D 无解** ⇒ **请转达 TTS：目标 `RTF_out ≤ 0.75`**）｜✅ 自测 0 FAIL ｜⛔ 未打包/未改引擎/未推远程（★ 明细见 §30 与 `notes/sec30_ext037_038.md`）
阻塞 / 待决定:
① ✅ **EXT-036 ①⑤ 已由真实 e2e 确认**（§29）：下行 P95 = 121 ms（轮次 B 复现 35 ms）≤ 0.3 s；`|wav − durationSec|` = 0.011 s ≤ 0.2 s ⇒ §28「⛔ e2e 未跑完」**解除**
② ⛔ **sync 仍未达标（EXT-038 验收）**：D=20 实测有符号 P50/P95 = 5978.7 / 16130.6 ms（判据 ≤300 ms）⇒ **不写「同步已解决」**、**不自行放宽目标**；★ `D_needed` **33.652 s ≫ D=20** ⇒ **根因是吞吐饱和**（`RTF_out` **1.0562 > 1**、`speech_over_src` **1.244** ⇒ `tts_over_src` **1.3139**）⇒ **任何固定 D 都追不上** ⇒ **请主会话转达 TTS：`RTF_out` 实测 1.0562**（§29 的 0.8182 是丢段后假值，**已作废**）⇒ **目标 `RTF_out ≤ 0.75`**；`speech_over_src` 1.244 需压到 ≈1.0（归 MT/EXT）；`seg_len` 4.263+ASR 3.388 归 EXT/ASR
③ ✅ **时长比口径已追平（撤回旧结论）**：旧「0.46–1.08 未追平」是**分析器口径错误**（`d_ws` 已是 WSOLA 后时长又乘一次 speed ⇒ 重复校正）⇒ **作废 `speed_adjusted`**、`d_player` 改 `endedAt−actual` ⇒ 本轮 **`over_ws` = 0.9991~1.0008**（1.00±0.02 全合格）⇒ **不是播放器的问题**；reviewer 的 0.57–1.55 是 `over_src_len` 口径，**不可直接互比**
④ ⛔ **EXT-028 待用户抽听 ⇒ V2.0 插件部分暂不放行**；⛔ **pyannote 旁路未接线**（克隆音色依赖 ASR-013）；⛔ **P3（打包）未开始**
⑤ ⛔ **进程越权规则（§28⑦）**：PID 7896 不在 EXT-035 授权范围 ⇒ 关闭属越权；**新规则**：点名以外的实例**一律停下写进 STATUS 请主会话找用户确认**；★ **§29/§30 两轮均未关闭任何进程**
⑥ ℹ️ **tabCapture 生产路径仍只能用户手势**（探针 12 次全败）—— 但 **EXT-033 已改走页面元素抓取** ⇒ 需求**已绕开**；✅ **EXT-023 已收口**（`on_npu=17 / on_cpu=[]`）

## 当前有效结论

| 项 | 值 | 来源文件 |
|---|---|---|
| **EXT-037 ②③④ 三项** | ② 丢 3.5 s **已修** ⇒ **29 段 / 缺口全 0 / 总覆盖 0→105.791 s（100%）**、14 个 TTS 段与参照轮 `20261102_213515` 一致｜③ 固定项 = 上行(0)+ASR **3.388**+**`seg_len` 4.263**+下行 **0.039** ⇒ `non_tts_fixed_sec` **7.690**；结果项 `player_queue` 2.962 / `axis_gap` 4.200 **单列**（`axis_gap` 是时钟换算常数不是延迟）｜④ `speed_adjusted` **作废**，主口径 `over_ws` ⇒ **0.9991~1.0008** | §30 ①–③；`notes/sec30_ext037_038.md` |
| **EXT-038 默认 D + 实测 e2e（run `20261105_112057`）** | **D=20 s**（插件 popup/sw/player + bridge `--delay` + 9 runner **两侧一致**；e2e 三处**全部参数化** + 插件写后读回 + `reload()`）｜静音 **20.11 s**｜\|wav−durationSec\| **0.149 s ≤ 0.2 s** ✅｜覆盖 **14/14** ✅｜⛔ sync **P50/P95 = 5978.7 / 16130.6 ms**（max 16198.3）❌｜`RTF_out` **1.0562**｜`tts_over_src`/`speech_over_src` **1.3139 / 1.2440**｜lag 斜率 **−0.4106**（r²=0.866, n=14）｜`over_ws` **0.9991~1.0008** ✅｜`D_needed` **33.652 s** | §30 ④⑥；`.tmp/ext033_e2e/20261105_112057/` || **EXT-036 ①⑤ 实测确认** | 下行 P95 = **121 ms**（轮次 B 复现 **35 ms**）≤ 300 ms ✅；`\|wav − durationSec\|` = **0.011 s** ≤ 0.2 s ✅ ⇒ §28「⛔ e2e 未跑完」解除 | §29；`notes/sec29_ext036_e2e.md` || 交付配置 / RTF | ASR=R2T2 INT8@GPU.0 / MT=Hy-MT2 INT8@GPU.0 / TTS=Qwen3-TTS@NPU；端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507）/ TTS **1.0022**（>1.0）；末句滞后 **71.2074 s（↓68.8 %）**、斜率 −0.106051 | §10.4 启动日志；`.tmp/ext008_bench/steady.json`；`.tmp/p1_pipe/p1_report.json` |
| 下行链路（EXT-024 根因） | 服务端按 **token 广播** `tts`/`echo`；插件两条 WS **都**挂 `onmessage`、按 `id` 去重；**只有 `metrics.link.dubDelivered > 0` 才说明下行通了**；`hello_ack.mode` 只增不改、`engines_ready` 诚实 | `ext/bridge.py` → `downlink_targets` / `_engines_ready()`；`extension/player.js` → `diagnoseLink()` |
| 设备收口 / 旁路 / 发行包 | EXT-023 **已收口**（`on_npu=17 / on_cpu=[]`）；旁路独立线程 + 有界队列(64) + `put_nowait`、标签异步回填、**ASR 等 GPU 锁 ≤0.004 %** ⇒ 不反压；`release/V20_HANDOFF.md` 已写（插件 15 文件 / 219 021 B，模拟发行包启动 6 PASS），★ **App 包内缺 `websockets`+`psutil` ⇒ 打包必补装**；⭐ **克隆音色未接线**（`voice_source` 全 `'preset'`）⇒ **不宣称可用** | `tts_exec_devices.json`；`ext/speaker_bypass.py`；§23；`.tmp/ext031/fake_pkg_probe.json` |
| 自测套件 | **本轮全部 0 FAIL**（selfcheck **122** / echo **11** / next_instruction **19** / p1 **112** / ext010 **25** / ext033_capture **42** / ext033_deliver **25** / ext036 **64** / ext036b **41** / ★ **ext037_seg_coverage 53（新建）**）；node 沙箱 **29 / 33 / 16**；★ **变异测试 M1/M2/M3b/M4 全 DETECTED**（M3 数值等价属预期）；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改） | §21–§30 实测 |
| §1~§27 历史结论 | 逐条明细见 `status/notes/sec11…sec27_*.md` 与 `status/archive/STATUS_EXT_upto_20261030.md`（224 833 B）：交付配置 / 扩展 ID / 启动器 / 语言映射 / t_start 时间轴 / 下行链路 / 段 id / 持久化与内存有界 / 设备收口 等 9 组结论均以 notes 为准 | §11–§27；`notes/` |
## 未完成纠偏清单

| 编号 | 状态 | 结论 / 下一步 |
|---|---|---|
| **EXT-038** | ✅ 已执行（§30） | 默认 D 改 **20 s**（插件 3 处 + bridge + 9 runner 两侧一致）＋ e2e 三处参数化 + 插件写后读回 + reload；真实 e2e `20261105_112057`：静音 20.11 s、\|wav−dur\| 0.149 s、覆盖 14/14、时长比 ✅ ｜⛔ **sync P50/P95 = 5978.7 / 16130.6 ms ≫ 300 ms 未达标**（**不自行放宽目标**）｜`D_needed` **33.652 s** ⇒ **RTF_out 1.0562 饱和** ⇒ **请转达 TTS：目标 `RTF_out ≤ 0.75`** |
| **EXT-037** | ✅ 已执行（§30 ①–③） | 丢 3.5 s 已修 ⇒ **覆盖率 100%**；口径重写 ⇒ `non_tts_fixed_sec` **7.690 s**；compare 改 `over_ws` ⇒ **0.9991~1.0008** ｜★ **撤回 §29「D=10 足够 / 7.184 s / 时长比 0.46–1.08」** |
| **EXT-036** | ✅ 已执行（§28/§29） | ①⑤ **实测确认**（下行 P95 121 ms；\|wav−dur\| 0.011 s）｜★ **暴露真缺陷并已修**（客户端实测从不上报 ⇒ null 被强转假 0.0）｜✅ 十套自测 0 FAIL ⇒ ⛔ sync P95 9087/8727 ms 未达标｜⛔ 旧时长比口径**已由 §30④ 撤回** |
| **EXT-035 / EXT-034** | ✅ 已执行（§27） | EXT-035 **5 项全过**（`t0UpPlayerOffsetSec=-3.389` / 起播 0.005 s / 静音 14.620 s / detail 14/14 / 三口径 1.1937·1.2227·1.4595）；⛔ sync 35.1/41.9 s 未达标 |
| **EXT-031 / EXT-030 / EXT-029** | ✅ 已执行（§21–§23） | `release/V20_HANDOFF.md` 已写（模拟发行包 6 PASS）｜★ **打包由 App 线程执行**，⚠️ **App 包内缺 `websockets`+`psutil` ⇒ 打包必补装**；⚠️ `liveDub.release` 需置 `true`（**打包必改 3 处**）｜租约四段自动化实测 BUSY → TAKEOVER ⇒ 机制生效；旁路独立线程 + 有界队列，**ASR 等 GPU 锁 ≤0.004 %** |
| **EXT-032 / EXT-028** | ✅ 已执行（§25） | **撤回**旧结论 ⇒ EXT-028 改「**待用户抽听**」；已交逐段三份音频对比（时长比 6/6 = 1.000–1.019、互相关 1.0000、SNR 120 dB）+ `shared/ext_listen/ext032_20261102_010022/`；⛔ tabCapture 自动化拿不到 ⇒ 须用户手势 |
| **EXT-027 / EXT-026 / EXT-024 / EXT-025 / EXT-023 / EXT-022 / EXT-017④ / EXT-005①** | ✅ 已执行 / 🟡 部分 | EXT-023 **已收口**；EXT-024 **真实三引擎下行通**（`dubDelivered=9`）；EXT-026 两轮 60 s 真实跑通；EXT-027：抓流 ✅ / 持锁 ✅ / 克隆 ⛔ / 同步误差 ⛔ / 按序播放 ✅；⛔ **Edge 真实手势验收仍需用户本人做**（本机只有 Edge ⇒ 自动化拿不到 tabCapture）｜逐条明细见 `notes/sec17…sec27_*.md` |
| P2 其余 | 🟡 部分落地 | ✅ ducking + 字幕（§15）/ 目标语言已生效（§16）/ 设置持久化已修好（§19）/ 内存不持续增长已修好（§19）；⛔ **克隆音色仍不可用**（依赖 ASR-013）｜⛔ **「30 分钟不崩」未做**｜⛔ **暂停拖动未做** |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；§9 及更早见 `status/archive/`（头部「已压缩」行已列两个归档文件）；§11~§27 见 `notes/sec11…sec27_*.md`。
>
> | 章节 | 明细全文 | 一句话结论 |
> |---|---|---|
> | **§28** | `notes/sec28_ext036.md` | EXT-036 交卷（复核七项）：7 s 缺口已定性并修复（**轴对不上**，差 6.7787 s = 2×\|dOff\|）；根因分列；斜率 −0.46251（n=14）；时长比三口径分列（★ 已由 §30③ 修订）；PID 记录改正 ⇒ 九套自测 0 FAIL |
> | **§29** | `notes/sec29_ext036_e2e.md` | EXT-036 补测：① 下行 P95 = 121 ms ≤ 300 ms ② \|wav − durationSec\| = 0.011 s ≤ 0.2 s；★ 暴露并修复真缺陷（客户端实测从不上报 ⇒ null 被强转假 0.0）；⛔ sync P95 9087/8727 ms 未达标 |
> | **§30** | `notes/sec30_ext037_038.md` | EXT-037 + EXT-038 交卷：① 丢 3.5 s 已修 ⇒ 覆盖率 100% ② 口径重写 ⇒ `non_tts_fixed_sec` 7.690 s ③ compare 改 `over_ws` ⇒ 0.9991~1.0008 ④ 默认 D=20 s + 真实 e2e `20261105_112057`；⛔ sync P95 16130.6 ms 未达标、`D_needed` 33.652 s、`RTF_out` 1.0562 饱和 ⇒ **请转达 TTS：目标 RTF_out ≤ 0.75** |

## §30 —— EXT-037 + EXT-038 交卷：丢 3.5 s 真缺陷已修（覆盖率 100%）+ 默认 D=20 s 实测

★ **全量明细见 `status/notes/sec30_ext037_038.md`**（逐条证据、原始字段、变异测试、产物清单、reviewer 交付清单）｜★ **闸门** exit 0（`action=execute`，latest=**EXT-038**）⇒ 本轮**认领 EXT-038**（与 EXT-037 一起 ack）⇒ `last_ack` 推进到 **EXT-038**；★ 开工时 `acquire ext` 返回 **TAKEOVER**（死会话 token=b1c6d479）⇒ 按 EXT-030 **从断点继续**。

⇒ **① EXT-037 ②【BLOCKING】每段丢 3.5 s —— ✅ 已修，覆盖率 100%**：**病根** = `ext/bridge.py` 每次调 `split_first_segment_streaming(...)` 都把缓冲开头 `[0, 3.5 s)` 当「已交付首段」切掉 ⇒ 旧实现**每段之后都丢 3.5 s**（60 s 素材丢约 24 s / 40%）｜**修法（最小改动）**：守卫 **`_buf_base == 0`**（缓冲起点仍是会话起点 ⇒ 已交付首段还在缓冲里）+ **裁掉缓冲之后**才清零 `_first_seg_cut`（⚠️ 提前清零 ⇒ 原始网格首段被**重复派发**）＋ 配套 `flush()` 跳过「已交付但仍在缓冲里」的前缀（新增 `_buf_delivered_prefix`）⇒ 否则尾段与首段**重叠**｜**★ 实测（run `20261105_112057`，D=20）**：**29 段 / 缺口全 0.0 / 无重叠 / 总覆盖 0→105.791 s ⇒ 覆盖率 100%**（§29 旧轮仅 8 段、每档 3.5 s 缺口；**14 个 TTS 段**与参照轮 `20261102_213515` 一致）⇒ **§29 丢失的 6 处译文全部恢复**。
⇒ **② EXT-037 ③ sync_rootcause 口径重写 ✅**：**固定项** = 上行(夹0) + ASR整段定稿 + **seg_len（等整段说完）** + 真实下行耗时；**结果项** = `player_queue`（排队）、`axis_gap`（**两端时钟的换算常数，不是延迟**）⇒ 单列 `result_items_detail`｜**★ 实测** `non_tts_fixed_sec` = **7.690 s** = 上行 0.000 + ASR **3.388** + **seg_len 4.263** + 下行 **0.039**（`unmeasured: []` ⇒ **不是下界，是全量**）；`player_queue` 均值 **2.962** / max 12.170、`axis_gap` **4.200** ⇒ **均在结果项，不进固定项**｜**★ D_needed = 33.652 s**（P95(ready − t_start) 33.352 + 0.3）。
⇒ **③ EXT-037 ④ compare 时长比口径 ✅**：**作废** `speed_adjusted`（`d_player × speed ÷ d_ws`）—— **`d_ws` 已是 WSOLA 变速后时长 ⇒ 再乘一次 speed 是重复校正**；**主口径 = `over_ws`**（d_player ÷ d_ws），reviewer 口径 `over_src_len` 保留；**`d_player` 主口径改 `endedAt − actual`**（包络起止 ⇒ 不截尾部静音；能量检测保留为 fallback）｜**★ 实测 `over_ws` = 0.9991 ~ 1.0008**（1.00±0.02 ⇒ **✅ 全合格**）⇒ **⚠️ 撤回 §28⑥/§29「时长比 0.46–1.08 未追平」**（分析器口径错误，**不是播放器的问题**）。
⇒ **④ EXT-038 默认 D=20 s + 真实 e2e ✅**：插件（`popup.js`/`popup.html`/`sw.js`/`player.js`）+ `ext/bridge.py --delay` + 9 个 runner + `USER_GUIDE.md` **两侧一致**｜★ **关键修正：e2e 跑批里 D 出现在三处**（服务端 `--delay`、插件 `chrome.storage.local.delaySec`、e2e 自身默认值）⇒ 漏改一处**测出的 sync 就是假的** ⇒ 三处**全部参数化** + **插件侧写入后读回校验**（不符即报错）+ **写完 reload**（`boot()` 只在加载时读 storage）⇒ 新增自测 `test_06_e2e_delay_plumbing`（12 项）｜**★ 真实 e2e（run `20261105_112057`，60 s 素材，录音 104.469 s）**：覆盖率 **100%** ✅｜开头静音 **20.11 s** ≈D=20 ✅｜\|wav − durationSec\| = **0.149 s** ≤ 0.2 s ✅｜覆盖 **14/14** ✅｜⛔ **有符号 sync P50/P95 = 5978.7 / 16130.6 ms**（max 16198.3）**≫ 300 ms 未达标**｜`RTF_out` **1.0562**｜`tts_over_src`/`speech_over_src` **1.3139 / 1.2440**｜lag 斜率 **−0.4106**（r²=0.866, n=14）｜`over_ws` **0.9991~1.0008** ✅ ⇒ **⛔ 按 EXT-038「不要自行改目标」⇒ 不写「同步已解决」**。
⇒ **⑤ 撤回 §29 的两条结论**：**撤回「D=10 已足够吸收 / 非 TTS 固定项 7.184 s / tts_independent_lag −2.8 s」**（旧口径把 `axis_gap` 算进固定项 ⇒ 数值不可比；新口径 `non_tts_fixed_sec` = 7.690 s、结果项单列 ⇒ 且 **`D_needed` 33.652 s ≫ D=20 ⇒ 「D=20 足够」不成立**）｜**撤回「时长比 0.46–1.08 未追平」**。
⇒ **⑥ 为什么 D=20 仍达不到 300 ms（实测归因，不臆造）**：`D_needed` = **33.652 s**（`ready − t_start` 逐段 7.97→33.73 随段号**单调增长**）⇒ 正是 ③ 的**「等整段说完 + 管线耗时」**叠加｜**根因 = 吞吐饱和**：`RTF_out` **1.0562 > 1**、`speech_over_src` **1.244** ⇒ `tts_over_src` = **1.3139 > 1** ⇒ **每 1 s 源音频要花 1.31 s 合成 ⇒ 队列必然越排越长 ⇒ 任何固定 D 都追不上**（P95 由后段决定）｜**归属**：**TTS 整句非流式 + `RTF_out > 1`** ⇒ **TTS 模块**；译文变长 ⇒ **MT/EXT**；段长与 ASR 整段定稿 ⇒ **EXT/ASR**（`seg_len` 4.263 + ASR 3.388）⇒ ⇒ **★ 要达到 P95 ≤ 300 ms，需 TTS 侧把 `RTF_out` 降到 ≲ 0.75**（且 `speech_over_src` 压到 ≈1.0），否则**光调 D 无解**｜⇒ **请主会话转达 TTS**：`RTF_out` 实测 **1.0562**（§29 的 0.8182 —— **丢段后只合成 39 s/60 s 的假值，已作废**）⇒ **TTS 侧真实目标 `RTF_out ≤ 0.75`**（不是 ≤0.82）。
⇒ **⑦ 自测（实测 rc）**：selfcheck **122**｜echo **11**｜next_instruction **19**｜p1 **112**｜ext010 **25**｜ext033_capture **42**｜ext033_deliver **25**｜ext036 **64**｜ext036b **41**｜★ **ext037_seg_coverage 53（新建）**｜node 沙箱 **29 / 33 / 16** ⇒ **全部 0 FAIL**｜★ **本轮修了两个「legacy 套件契约冲突」**（上一会话改了口径但没同步改旧断言 ⇒ 套件变红）：`test_ext036_review` 7 FAIL、`test_ext036b_client_metrics` 4 FAIL ⇒ 已迁到**新契约**并**加强**（新增「明细不含 axis_gap/player_queue」「新增 seg_len 项」「结果项单列」「旧口径 `speed_adjusted` 不得再出现」等守卫）⇒ ★ **是「改旧断言迁到新契约」，不是「放宽断言掩盖回归」** —— 原守卫（null 不冒充 0 等）**全部保留并加强**｜★ **变异测试 M1/M2/M3b/M4 全 DETECTED**；M3 合计公式 null 强转 0.0 ⇒ **MISSED（数值等价，属预期）** ⇒ **已如实记录，不虚报**｜★ **另修一个既有基线红**：`ext024_link_harness.js` 在 **HEAD 版本就报** `ReferenceError: dubDownlinkMs is not defined`（`git show HEAD:` 复现确认 ⇒ **非本轮引入**）⇒ 补沙箱桩 ⇒ **33 PASS / 0 FAIL**。
⇒ **⑧ 产物清单**（文件数 / mtime / 字节数）：`.tmp/ext033_e2e/20261105_112057/` ⇒ **12 项**（11 文件+1 目录）：`dub_player.wav` **10 029 100 B**、`dub_player.webm` **927 795 B**、`margin.json` **60 056 B**、`metrics.json` **46 425 B**、`dub_sync.json` **10 738 B**、`bridge.log` **12 024 B**、`player.png` **24 404 B**、`record_stop.json` **291 B**、`ext033_compare.json` **20 335 B**、`ext033_compare.md` **4 793 B**、`audio_dump/`（目录）—— mtime 2026-11-05 11:26~11:28；摘要 `summary_20261105_112057.json`（`delay_sec=20`/`plugin_delay_sec=20`/`rc=0`）。
⇒ **⑨ 交 reviewer（EXT-038 ④）**：**wav** `.tmp/ext033_e2e/20261105_112057/dub_player.wav`（**10 029 100 B**，104.469 s）；**每段译文** `ext033_compare.json`（`segments[]` 含 `seg_id`/源/译/`signed_err_ms`/时长比）＋ 明细表 `ext033_compare.md`；⛔ **质量判定由 reviewer 用 MiniMax 回转写，本模块不自行调用**。
⇒ **⑩ 明确未做 / 不宣称**：⛔ **sync P95 未达标** ⇒ **不写「同步已解决」**、**不自行放宽目标**；⛔ **未打包**（★ 按用户规则**不主动打包**）；⛔ **未改引擎/其它模块文件、未推远程**；⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**；⛔ **本轮未关闭任何进程**；MACHINE_LOCK 由 `machine_lock.hold()` 正常排队 ⇒ **未抢活锁**；⛔ **EXT-028 待用户抽听、V2.0 暂不放行**；⛔ **克隆音色仍不可用**（依赖 ASR-013）。

### `last_ack`
**EXT-038** —— 本轮**认领并执行**（闸门 exit 0）⇒ `last_ack` 由 EXT-036 推进到 **EXT-038**。

## §29 —— EXT-036 补测：真实三引擎 e2e（①⑤ 确认）+ 客户端实测数据上报闭环（2026-11-04 20:03）

★ **全量明细见 `status/notes/sec29_ext036_e2e.md`**（★ 闸门 exit 1 `already_executed` ⇒ 不认领新编号，按 EXT-030 TAKEOVER 从断点继续）

⇒ **① 下行耗时 P95 = 121 ms ≤ 300 ms ✅**（轮次 A `20261104_194608`；轮次 B `20261104_195911` 独立复现 **35 ms**）⇒ §28「⛔ e2e 未跑完」**解除**；**⑤ |wav − durationSec| = 0.011 s ≤ 0.2 s ✅**。
⇒ **★ 补测暴露的真缺陷（已修）**：客户端测得到 `ply_wall_ms − srv_wall_ms` / `readyToStartSec` / `t0UpPlayerOffsetSec`，但**只留本地、从不上报服务端** ⇒ `sync_rootcause` 三项恒 null，且 `non_tts_fixed_detail` 把 null **强转成 `0.0`**（**假数据**）⇒ **修法**：客户端 `reportClientMetrics()`（在 `requestMarginDump` **之前**发 `client_metrics`）＋ 服务端 `note_client_metrics()` / `client_metrics_summary()` ＋ **null 不再强转 0**（合计标 `non_tts_fixed_is_lower_bound`，明细列 `unmeasured`）⇒ 修后 `unmeasured: []`。
⇒ **★ 非 TTS 固定项 7.184 s**（§28② 的 2.892 s 残缺）⇒ 曾判「D=10 已足够」；★ **已由 §30⑤ 撤回**（旧口径把 `axis_gap` 算进固定项）。
⇒ **自测十套全 0 FAIL**（122/11/19/112/25/42/25/59/39/29）｜★ **变异测试**：null 强转改回旧写法 ⇒ **35 PASS/4 FAIL** ⇒ 守卫有效（已还原）。
⇒ ⛔ **sync 有符号误差仍未达标**（P95 **9087 / 8727** ms）⇒ **不写「同步已解决」**｜⛔ 时长比仍未追平（★ 已由 §30④ 撤回）｜⛔ 未改引擎/其它模块文件／未打包／未推远端／`CORRECTIONS_EXT.md` 只读未改未入库｜⛔ **本轮未关闭任何进程**（只由 `machine_lock.hold()` 自动回收**已确认死亡**的 ASR 锁 PID 2188）。

## §28 —— EXT-036 交卷：§27 复核七项逐条落实（2026-11-04 18:40）

★ **全量明细见 `status/notes/sec28_ext036.md`**（逐条证据、实测值、反证组、变异测试）

⇒ **① 7 s 缺口已定性（修复）**：**不是下行慢，是两端轴对不上**（`t0 = t0Up − dOff`；旧式 `+ dOff` ⇒ t0=−**3.4091** 不自洽；两式差 **6.7787 s = 2×|dOff|** ≈ reviewer 实测 6.84~7.82 s）⇒ **恒定 ⇒ 排程错，非下行慢**；新增自证判据 `t0 ≥ 0`；`srv_wall_ms` ↔ `ply_wall_ms` ⇒ `downlinkMs` = **真实下行耗时**（新自测 `t_ext036_review` 59）。
⇒ **② 根因分解**：新增 `decompose_sync_rootcause()` ⇒ 轴缺口与真实下行耗时**分列** ⇒ **撤回 §27「全归 TTS」**（该数值已由 §29 改为 7.184 s，★ 已由 §30⑤ 撤回）｜**③ 斜率只用有 TTS 的段**：新 **−0.46251 / r²=0.8819 / n=14**（旧 0.248/0.375 **作废**）。
⇒ **④⑤ 首段 3.5 s 一到就交出**（不裁缓冲 ⇒ 栅格不变 ⇒ 尾段不丢）；**录音时间轴不再压缩**（worklet 补静音样本 + `ConstantSourceNode`）—— 已由 §29 真实 e2e 实测确认（差 0.011 s）。
⇒ **⑥ 时长比三口径分列**（`over_src_len`/`over_ws`/`speed_adjusted`）★ **已由 §30④ 修订为 `over_ws` 主口径**｜**⑦ PID 记录改正**（撤回「26736 已关」；**7896 属越权** ⇒ 新规则：点名以外一律停下请用户确认）。
⇒ **⑧ 自测九套全 0 FAIL**；★ 变异测试 `+ dOff` ⇒ **57 PASS/2 FAIL** ⇒ 守卫有效｜**⑨ ① 当时 e2e 未跑完** ⇒ ★ 已由 §29 补测解除。

