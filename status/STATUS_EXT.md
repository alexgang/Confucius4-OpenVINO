# STATUS_EXT
last_ack: EXT-033
更新时间: 2026-11-02 14:10
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§26 EXT-033 交卷** —— ★ 又一次租约 **TAKEOVER**（第 3 个会话接手）⇒ 从断点续做 ⇒ ✅ **修掉 3 个真缺陷**：**① `t0` 跨时钟域**（上行域算、player 域消费 ⇒ `schedClamped=13`、有符号误差恒为正 ⇒ 量不出早播）现已换算到 player 域（60 帧中位数，保留换算前后原值可自证）+ **浏览器实测 9 PASS**；**② 设备互斥从来没生效过**（bridge 跑在 App 自带 python ⇒ **无 psutil** ⇒ 恒 False；且只匹配 `live_caption` 带下划线 ⇒ 双重漏检）现已三级降级取进程列表 + 按 App 真实入口匹配 + 探测失败保守 ⇒ **实测检出字幕 App PID 4896**；**③ 交付分析器 `rms` 局部变量遮蔽**（`test_ext033_deliver` 实测崩）已修 ⇒ ✅ **六套自测全 0 FAIL**（106/11/19/42/25/9） ⇒ ⛔ **但实测仍未达标**：开口静音 26.58 s（判据 ≤15 s）、sync 有符号 P50/P95 = **28.7/29.5 s**（判据 ≤300 ms）、时长比 0.68~1.49 ⇒ ⛔ **根因是 TTS RTF 1.231 > 1 + 设备被字幕 App 占用**（`feed_lag` 全为负 ⇒ 非上行问题）⇒ **TTS 提速需主会话转达 TTS 模块**（本模块不碰引擎）⇒ ⛔ 未打包（APP-057）/ ⛔ 克隆音色不可用

阻塞 / 待决定:
① ⛔ **EXT-033 未达标：sync / 开口静音 / 时长比** —— 真实三引擎实测（run `20261102_121431`）：sync 有符号 P50/P95 = **28.7/29.5 s**（判据 ≤300 ms）、开口静音 **26.58 s**（判据 ≤15 s）、时长比 **0.68~1.49**（判据 1.00±0.02）。**根因已定位**：TTS **RTF 1.231 > 1**（ASR 0.773 / MT 0.193）+ 设备被实时字幕 App 占用；`feed_lag` **全为负** ⇒ **不是上行/反压问题**。⇒ **TTS 提速请主会话转达 TTS 模块**（目标 RTF ≤ 0.85）
② ⛔ **需主会话协调设备**：跑真实 e2e 时**实时字幕 App 在跑**（PID 4896，占 GPU.0+NPU）⇒ 按互斥铁律桥接 rc=3 拒绝启动 ⇒ 本轮**未跑出修复后的真实 e2e**
③ ⛔ **EXT-028 待用户抽听 ⇒ V2.0 插件部分暂不放行**（旧结论已在 §25 撤回）—— 交付物已落 `shared/ext_listen/ext032_20261102_010022/` 与 `shared/ext_listen/ext033_20261102_121928/`
④ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P3（打包）未开始**
⑤ ℹ️ **tabCapture 生产路径仍只能用户手势**（探针 12 次全败）—— 但 **EXT-033 已改走页面元素抓取**（`createMediaElementSource`）⇒ 该手势需求**本轮已绕开**（不再需要整机声交卷）
⑥ ℹ️ **EXT-009 服务端 lag 估计存在跨时钟常量偏差，尚未定量标定**（§17 已写清）；ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准）；✅ **EXT-023 已收口**（§18 实测 `on_npu=17 / on_cpu=[]`）

## 当前有效结论

| 项 | 值 | 来源文件 |
|---|---|---|
| 交付配置 | ASR=R2T2 INT8@GPU.0 / MT=Hy-MT2 INT8@GPU.0 / TTS=Qwen3-TTS@NPU | §10.4 启动日志 |
| 端到端稳态 RTF / TTS 稳态 RTF（去首段 18 段/286.32 s） | **2.0507**（ASR 0.6563 / MT 0.1507） / **1.0022**（无余量，>1.0） | `.tmp/ext008_bench/steady.json` → `steady_state_excl_first_segment` |
| 流水线末句滞后 | **71.2074 s（↓68.8 %）**，斜率 −0.106051（↓81.3 %）；串行（EXT-009 前）227.9863 s / 斜率 −0.565947 | `.tmp/p1_pipe/p1_report.json`（串行 `.tmp/p1_ext009/`） |
| 扩展 ID | `kekgmfkijphpfndbbpakjaokamkeooib`（由 manifest `key` 现场算，与 9 份探针一致） | `ext/extension_id.py` |
| `/pair` Origin 收紧 | 本插件 **200** / 别的扩展 **403** / 普通网页 **403** / 无 Origin **403** | §10.3 实测 |
| 启动器 `start()` 反馈延迟 | **0.032 s**（修前 4.244 s）⇒ 满足 EXT-017②「2 秒内」 | §12 实测 |
| **重复启动失败耗时** | **400 ms 退出码 6**（修前：预热 24 s 后整屏 traceback） | §14 实测 |
| 桥接冷启动（回声模式，不含引擎） | **5.0–5.7 s**（10/10 实测，min 4.948 / max 5.581 / 均值 5.324） | §12 实测 |
| 面板目标语言**实际生效** | `applied_target_lang`（= MT `tgt` / TTS `language` 真正用的码）可与 `client_target_lang` 比对 | §16 实测 |
| 抓流方式（capture_mode） | 由**客户端实际上报**（hello / capture_info）；未上报 = `null`（绝不臆造） | `ext/bridge.py` → `stats()` / `margin.json` |
| **下行路由（EXT-024 根因）** | 服务端按 **token 广播** `tts`/`echo`（产生它的连接 + 同 token 的 player 连接）；插件两条 WS **都**挂 `onmessage`；按 `id` 去重 | `ext/bridge.py` → `ConnectionRegistry.downlink_targets` + `extension/player.js` → `handleBridgeMessage` |
| **已下发到 player 段数** | `metrics.link.dubDelivered`（= player 端**实际收到**的 tts 消息数）⇒ **只有它 > 0 才说明下行通了** | `extension/player.js` → `diagnoseLink()` |
| **链路卡住原因（15 s 阈值）** | WS 未连 / 回声模式 / 引擎未就绪 / 没有音频轨 / 没出段 / **下行路由断了** —— 红字**如实**写明 | `extension/player.js` → `diagnoseLink()`（纯函数，可 node 沙箱验证） |
| **连接模式（真实/回声）** | `hello_ack.mode` = `'real'`/`'echo'`（**只增不改**旧字段）；`engines_ready` **诚实**（绝不因 real 就报 True） | `ext/bridge.py` → `_engines_ready()` / `hello_ack` |
| **t_start 时间轴口径** | **上行采样时间轴**（`s0/16000`，采样点 0 = 上行首帧）；插件按 `t0_player + t_start + D` 排程 ⇒ 与原声**同轴**；落盘 `t_start_axis` | §17 实测（`t_start_axis='uplink_sample_index'`） |
| **语言全称映射（EXT-024 G）** | 服务端独立认全称：`Chinese`→`zh` / `English`→`en` / `Japanese`→`ja` / `Korean`→`ko`；未知值 ⇒ None（绝不臆造） | `ext/config.py` → `normalize_lang_code()` |
| **EXT-023 真实值（已收口）** | **`on_npu=17` / `on_cpu=[]` / `on_unknown=[]`**；`cp_decode`=NPU；`talker`/`cp_prefill`/`decoder` 全 NPU ⇒ 无任何组件落在 CPU | `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`（4 260 B，mtime 20:54:13） |
| **段 id 跨会话唯一（EXT-026 ⑤）** | `seg_{8位数字会话前缀}_{数字}`（实测 `seg_55035942_194400` / `seg_77393782_194400`）⇒ 修掉 `seenDubIds` 撞号 | `ext/bridge.py` → `public_seg_id()` |
| **生产路径 flush（EXT-026 补齐）** | `offscreen.flushUplink()` → `sw.case 'flush'` → `popup`「停止并收尾」按钮（先 flush，12 s 后自动 stop）⇒ 尾段不再丢 | `extension/offscreen.js` / `sw.js` / `popup.js` |
| **设置持久化（T-6）** | popup 的 8 个设置控件**改了就立刻落盘**（`change` + 文本框 `input` 400 ms 防抖）；落盘前**归一**（语言全称⇒引擎码）；两条写盘路径共用 `readCfg()` ⇒ 口径一致 | `extension/popup.js` → `bindPersistListeners()` / `persistCfgNow()` |
| **内存不持续增长（T-5）** | 服务端逐帧到达延迟保留最近 **2000** 条、段级时刻表保留最近 **50** 段、插件 `gapDetail` 两侧各保留最近 **200** 条；**统计口径一字不变**（`n_frames_measured`/`late_ratio`/`mean`/`max` 由累计量承担 ⇒ 与旧实现逐位等价） | `ext/config.py` → `FRAME_DELAY_HISTORY` / `SEG_TIMING_HISTORY`；`ext/bridge.py` → `_trim_seg_timing_history()` |
| **说话人旁路（EXT-029，已收口）** | **独立线程 + 有界队列(64) + `put_nowait`**（满则**丢最旧块**并计数 `spk_queue_drop` 0–57）；标签**异步回填**（`n_label` 2–8，未到走**方案 A** 不等待）；**ASR 等 GPU 锁 A max 0.0007 s / B max 0.0008 s**（≤0.004 %）⇒ **不反压 ASR**；旁路占 GPU 锁**上界** 4.5–24.0 % | `ext/speaker_bypass.py` / `ext/spk_engine.py`；`agg_summary.json` |
| **发行包（EXT-031，已交清单）** | `release/V20_HANDOFF.md` 已写（插件 **15 文件 / 219 021 B**）；**实测模拟发行包启动 6 PASS / 0 FAIL**（零开发机依赖）；发行版调试已剔（`getDisplayMedia`/`audio_dump`/`margin` 全禁）；★ **App 包内缺 `websockets` + `psutil` ⇒ 打包必补装** | §23；`.tmp/ext031/fake_pkg_probe.json` |
| **pyannote 旁路（已接）** | 分段@**NPU**、嵌入@**GPU.0**（实测 NPU/GPU.1 不可用），经 `asr052_spk_runtime` 调用 ⇒ **旁路本身已通**；检出 **S1/S2(/S3)** | `ext/spk_engine.py`（§21） |
| **克隆音色（仍未接线）** | `voice_source` 实测**全 `'preset'`**、`clone_wired=false` ⇒ 引擎层 `voice` 参数**未**接进 `tts_engine.stream()` ⇒ **不宣称克隆音色可用** | `ext/bridge.py` → `_resolve_spk()` |
| 自测套件 | **28 套**（`test_ext029` **70 PASS / 0 FAIL**、`test_ext031` **24 PASS / 0 FAIL**、★ `test_ext032_deliver` **29 PASS / 0 FAIL**）；node harness **8 套 rc=0**；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改） | §21/§23/§25 实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-031** | 插件整合进发行包 V2.0，EXT 交一份可打包的交付清单 | ✅ **已认领并执行**（§23）：`release/V20_HANDOFF.md` 已写（六项齐全）；**模拟发行包启动实测 6 PASS / 0 FAIL**；★ **打包由 App 线程执行（APP-057）**；⚠️ **App 包内缺 `websockets`+`psutil` ⇒ 打包必补装**；⚠️ `liveDub.release` 需置 `true`（**打包必改只有 3 处**） |
| **EXT-030** | 巡检会话互相重叠 ⇒ 每会话开工前先拿「模块租约」 | ✅ **已认领并执行**（§22）：自动化指令已插入**四段**（`acquire`/`beat`/`addpid`/`release`），原文见 notes §22.1；★ 本轮**实测**触发 BUSY → 等 30 min → TAKEOVER ⇒ 租约机制**真实生效**；⛔ **未改 `session_lease.py`**（只读使用） |
| **EXT-029** | 说话人旁路必须独立线程、不得反压 ASR | ✅ **已认领并执行**（§21）：独立线程 + 有界队列 + `put_nowait` + 满丢旧块计数 + **异步回填不等待**；**ASR 等 GPU 锁 A max 0.0007 s / B max 0.0008 s**（≤0.004 %）⇒ **不反压 ASR**；5 轮真实三引擎 A/B 实测 + 4 个真缺陷已修；⚠️ 原文③「墙钟差异 ≤5%」经实测判为**噪声主导不可用** ⇒ 改用**机制直接度量** |
| **EXT-027** | 输入音频抓错 / 持锁铁律 / 克隆接线 / 同步误差 / 按序播放 | 🟡 **部分落地**：① 抓流（tabCapture **API 已修正**，但生产路径**未实测**——自动化拿不到，需用户点扩展图标）✅代码 / ② 持锁铁律 ✅ / ③ 克隆接线 ⛔（`voice_source` 全 `'preset'`）④ 同步误差 ⛔（未动引擎）⑤ 按序播放 ✅（`dubPlaybackEnd` 不叠播） |
| **EXT-032** | EXT-028 只修了代码没有交实录；「不构成打包阻塞」不成立 | ✅ **已认领并执行**（§25）：**撤回**旧结论 ⇒ EXT-028 改为**「待用户抽听」**；已交**逐段三份音频对比**（变速校正时长比 6/6 = 1.000–1.019、互相关峰 1.0000、SNR 中位 120 dB）+ **静音成因分解**（22.05 + 10 = 32.05 s，残差 −2.75 s）+ `sync_err p50/p95 = 0/0 ms` + 交付目录 `shared/ext_listen/ext032_20261102_010022/`（5 文件）；⛔ **① tabCapture 生产路径自动化拿不到**（探针 12 次全败）⇒ 须用户手势（`shared/ext_listen/v21/HOWTO.txt`） |
| **EXT-028** | 配音录音听不清 | 🟡 **代码侧已修 + 本轮已交实测，但用户抽听未做** ⇒ **「待用户抽听」**（★ **旧结论「不构成打包阻塞」已在 §25 撤回**）：根因是服务端不传 `sample_rate` 时插件按 16 kHz 重建 24 kHz 波形 ⇒ 1.5× 语速 + 升调 ⇒ 新增 `resolvePcmSampleRate()`；自测 `test_ext028_dub_audio_chain.py` **42 PASS / 0 FAIL**；★ 本轮实测 `pcmRateLast=24000 / pcmRateAssumed=0` ⇒ 修复**已生效**；⛔ player 录音逐段对齐只 **3/6** ⇒ 不宣称播放端完全对齐 |
| **EXT-026** | 真实三引擎端到端自动化冒烟 + 落盘配音/截图/段级日志 + 修 `seenDubIds` 撞号 | ✅ **已认领并执行**（`last_ack` = EXT-026）；两轮各 60 s 真实跑通、证据齐全、录音实测非静音（明细见 §18）；⛔ **Edge 默认 profile 真实手势验收仍需用户本人做** |
| **EXT-024** | 下行接通 / 会话生命周期 / 启动器 / 段级日志 / 状态条 / 模式显示 / 语言映射 | ✅ **代码侧 A–G 全部落地**（§17）；✅ **真实三引擎上已验证下行通**（§18：`dubDelivered=9`、下发到 player 9/9）；⛔ **Edge 真实手势 1 分钟验收未做**（用户本人） |
| **EXT-025** | RESUME：额度已重置，从 last_ack 继续 | ✅ **已认领并执行**（`last_ack` = EXT-025） |
| **EXT-023** | TTS 启动日志打印各组件 EXECUTION_DEVICES | ✅ **已收口**（§18）：真实跑批实测 `on_npu=17 / on_cpu=[]`，`cp_decode`=NPU，**无任何组件落在 CPU**（源 `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`） |
| **EXT-022** | 编号规则 / 待命规则 / 流水线默认开 / 冒烟脚本入库 | ✅ **全部落地**（编号改 T-1…T-4；`--pipeline` 默认 True；`tests/smoke/` 已入库，4 脚本实测 rc=0） |
| EXT-017 ④余项 | 浏览器端人工验收（tabCapture 需真实用户手势） | 需**用户本人**操作（EXT-022 已定②）；本机只有 Edge |
| EXT-005 ① | tabCapture 生产路径实测 | ⏳ **代码侧已就绪**（`capture_mode` 进 stats / margin.json）；⚠️ **自动化下拿不到 tabCapture**（需真实手势，实测错误原文见 §18）⇒ **仍需用户点一次扩展图标**（§13） |
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ✅ **ducking + 字幕已修好**（§15）；✅ **目标语言已真正生效**（§16）；✅ **设置持久化已修好**（§19：改了就落盘，8 个控件 change/input 即时落盘 + 归一 + 幂等）；✅ **内存不持续增长已修好**（§19：3 类无界增长真缺陷全部有界化，统计口径一字不变）；⛔ **克隆音色仍不可用**（旁路未接线，**依赖 ASR-013 交付**）；⛔ **「30 分钟不崩」未做**（需真实引擎 + 独占设备长跑）；⛔ **暂停拖动未做**（需真实浏览器 + 用户手势） |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；§9 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`（224 833 B）；§13~§16 见 `notes/sec13…sec16_*.md`。
>
> | 章节 | 明细全文 | 结论摘要 |
> |---|---|---|
> | §21 | `notes/sec21_ext029_spk_bypass_thread.md` | **EXT-029 说话人旁路**：独立线程 + 有界队列 + 异步回填（不反压 ASR）；修掉 **4 个真缺陷**；A/B 多轮实测 |
> | §22 / §23 | `notes/sec22_23_ext030_lease_ext031_handoff.md` | **EXT-030** 模块租约已接入自动化指令（实测 BUSY→TAKEOVER）；**EXT-031** V2.0 交付清单 + 不依赖开发目录实测 |
> | §24 | `notes/sec24_takeover_closeout.md` | **EXT-030/031 落库收口**：上一会话「做完就死」⇒ 闸门 exit 1 只判认领 ⇒ 本轮补记 EXEC_LOG + 提交；**复核 6 套全 0 FAIL**；★ 报出「闸门不校验收口」与「TTL 30 min」两个制度性缺口 |
> | §25 | `notes/sec25_ext032_deliver.md` | **EXT-032 交卷**：三份音频逐段对比（时长比 6/6、互相关 1.0000、SNR 120 dB）+ 静音成因分解（22.05+10=32.05 s，残差 −2.75 s）+ `sync_err p50/p95=0/0 ms` + 交付目录 `shared/ext_listen/ext032_20261102_010022/`；★ **撤回「EXT-028 不构成打包阻塞」** |
> | §26 | `notes/sec26_ext033.md` | **EXT-033 交卷**：修 3 个真缺陷（**t0 跨时钟域** / **设备互斥恒失效** / **分析器 `rms` 遮蔽**）；真实三引擎 e2e 产物已落 `shared/ext_listen/ext033_20261102_121928/`；⛔ sync 28.7/29.5 s、开口静音 26.58 s、时长比 0.68~1.49 **未达标**（根因 TTS RTF 1.231 + 设备占用） |

## §26 —— EXT-033 交卷：真实三引擎 e2e + 三个真缺陷修复（2026-11-02 14:10）

★ **全量明细见 `status/notes/sec26_ext033.md`**；§25 原文已下沉 `notes/sec25_ext032_deliver.md`。

⇒ **① ★★ 本轮修了三个真缺陷**（都有实测证据，不是推测）：
　**(1) `t0` 跨时钟域**（EXT-033 D 的根因）—— `t0` 曾在**上行 AudioContext** 域算出，却在**player** 域消费（`planned`/`when`/`at`）⇒ 两个 context 原点独立 ⇒ 系统性错位。
　　实测证据（前会话那一轮 `20261102_121431`）：`t0Sec=-0.0197`、`schedClamped=13`（**13 段全被钳成「立即播」**）⇒ 有符号误差**恒为正**（19.9~29.5 s）⇒ **量不出「早播」**。
　　**修法**：在 player 域测 `Δ = up.ac.currentTime − audioCtx.currentTime`（60 帧中位数）⇒ `t0 = t0_up + Δ`；**保留** `t0UpSec` / `t0UpPlayerOffsetSec` / `t0UpPlayerOffsetSpreadSec` ⇒ 换算前后**可自证**。`requested = t0 + t_start + D` 的算式**一字未改**。
　　**浏览器实测验证**（`tests/smoke/ext033_t0_verify.py`，CDP 直连不依赖 playwright，**9 PASS / 0 FAIL**）：两个 AudioContext 原点差 **Δ ≈ 0.37~1.05 s**（真实场景更大）⇒ **跨域问题真实存在**；换算自洽性（`t0_player−t0_up ≡ Δ`、同事件两域差 ≡ Δ）**逐条 PASS**；**反证**：不换算就引入 |Δ| 误差。
　　★ 实测发现（写进实现）：**`currentTime` 只在各自渲染量子推进时更新** ⇒ 单次相减带 ~80 ms 噪声 ⇒ **必须多次采样取中位数**（已做）。
　**(2) 设备互斥从来没生效过** —— `_caption_app_running()` 依赖 `psutil`，而 bridge 实际跑在 **App 自带 python** 里（**没有 psutil**）⇒ `except: return False` ⇒ **恒 False**；且旧实现只匹配 `"live_caption"`（带下划线），本机跑的是 **`LiveCaption`（无下划线）** ⇒ **双重漏检**。
　　**修法**：`wmic` → `Get-CimInstance Win32_Process` → `tasklist` 三级降级（**不依赖 psutil**）；按 **App 真实入口**（`bridge_launcher.py` / `live_caption_app.py`）匹配（不因"命令行提到该路径"误报）；**拿不到进程列表 ⇒ 保守按「可能在跑」处理**。
　　**实测**：0.56 s 内检出字幕 App（PID 4896）⇒ `caption_app_running = True`（修前恒 False）；3 个「命令行含该路径」的非 App 进程**均未误报** ✅。⇒ 本轮真实 e2e 重跑时被**正确拦下**（rc=3「检测到实时字幕 App 在运行，拒绝启动」）—— 这正是修复生效的**直接证明**。
　**(3) 交付分析器自带 bug** —— `ext033_analyze.py` 的 `voiced_span()` 里 `rms = _np.sqrt(...)` 让 `rms` 变成**局部变量** ⇒ 遮蔽全局 `rms(...)` ⇒ fallback 分支必 `UnboundLocalError`（`test_ext033_deliver.py` 实测崩）⇒ 局部改名 `_rms_blocks`。

⇒ **② ★ 前会话已完成的真实三引擎 e2e**（run `20261102_121431`，本轮接手其产物）：
　输入 = **页面元素**（`createMediaElementSource`）⇒ **不是整机声**（`uplink.captureMode="element"`、`gaps=0`、`maxAbsSkewAudioMs=1.08`）；素材 = 英文 SPE 0–60 s；**13 段 TTS**；录音 webm 856 053 B / WAV 10 012 716 B（48 kHz / 5 006 336 样本 / **104.299 s**、**不截断**）。
　❌ **但实测未达标**：开口静音 **26.58 s**（判据 ≤15 s）；sync 有符号 **P50/P95/max = 28650.0 / 29537.8 / 29537.8 ms**（判据 |P95| ≤ 300 ms）；时长比 **0.6825~1.4851**（判据 1.00±0.02）；1 段互相关峰 0.5005 < 0.6 标「**未对齐**」。

⇒ **③ ★ 剩余滞后的归因（**超出本模块职责**）**：`margin.json` 实测 —— `feed_lag` **全为负**（mean −5.85 s ⇒ **音频准时到，不是上行/反压**）；`intrinsic_lag` mean +2.27 s；滞后以 **0.3146 s/s 累积** ⇒ **管线吞吐 < 1**；**TTS RTF = 1.231 > 1**（ASR 0.773 / MT 0.193）⇒ **TTS 提速是 EXT 改不动的**（引擎属其它模块）⇒ **写进 STATUS 交主会话转达**，本轮**不碰任何引擎文件**。

⇒ **④ ★ 本轮自测（实测 rc）**：`test_ext_selfcheck` **106 PASS / 0 FAIL** (rc=0) ｜ `test_echo_roundtrip` **11 PASS / 0 FAIL** (rc=0) ｜ `test_next_instruction` **19 PASS / 0 FAIL** (rc=0) ｜ `test_ext033_capture` **42 PASS / 0 FAIL** (rc=0) ｜ `test_ext033_deliver` **25 PASS / 0 FAIL** (rc=0) ｜ `tests/smoke/ext033_t0_verify.py`（浏览器实测）**9 PASS / 0 FAIL** (rc=0)。
　★ 附带修：`test_ext_selfcheck` 原用 psutil 找「存活 PID 对照」⇒ **在真实运行环境（App python 无 psutil）里恒假失败** ⇒ 改用被测代码自己的 `_pid_alive`（ctypes 兜底）⇒ 106 PASS。

⇒ **⑤ ⛔ 明确未做 / 不宣称**：⛔ **本轮没跑出「修复后」的真实 e2e** —— 设备被**实时字幕 App（PID 4896）**占用 ⇒ 按铁律**不抢设备、不打断用户的 App** ⇒ 桥接 rc=3 拒绝启动 ⇒ **sync 修复效果只由浏览器实测探针证明，未由真实三引擎轮证明**；⛔ **开口静音 26.58 s 未解决**（TTS 未就绪 ⇒ 首段配音晚到）；⛔ **时长比 0.68~1.49 未解决**（需 TTS 提速后重测）；⛔ **未打包**（APP-057）/ **未改任何引擎文件** / **未推远程** / `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`git check-ignore` 命中 `.gitignore:34`）。

