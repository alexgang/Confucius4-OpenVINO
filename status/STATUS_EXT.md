# STATUS_EXT
last_ack: EXT-035
更新时间: 2026-11-02 21:40
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§27 EXT-035 交卷（与 EXT-034 一并 ack）** —— ✅ **EXT-034 四项缺陷全部修完并由真实三引擎 e2e 证实**：**① 同步测量覆盖 7/13 → 14/14**（主口径改用 **`start(when)` 采样精确的排程起点**，onset 口径单列不污染）｜**② RTF 三口径分列**（`RTF_out=1.1937` / `speech_over_src=1.2227` / `tts_over_src=1.4595`）｜**③ 首段会话级拆两段**（≤3.5 s ⇒ startup **25.547 → 9.731 s**，后续切点逐位不变）｜**④ `D_required=19.939 s`** ⇒ ✅ **EXT-035 验收 5 项全过**：`t0UpPlayerOffsetSec=-3.389 s` / **首段就绪→起播 0.005 s** / **开口静音 14.620 s** / **detail 14/14** / **三口径分列** ⇒ ✅ **八套自测全 0 FAIL**（122/11/19/112/42/25/25/29）⇒ ⛔ **仍不达标**：sync **P50/P95 = 35.1/41.9 s** ⇒ 根因 **TTS 自身 RTF_out=1.19>1**（引擎属其它模块）⇒ ⛔ 未打包（APP-057）/ ⛔ 克隆音色不可用（★ 明细见 §27 与 `notes/sec27_ext034_035.md`）

阻塞 / 待决定:
① ⛔ **EXT-035 验收项里的 sync 本身仍未达标**：P50/P95 = **35.1/41.9 s**（判据 ≤300 ms）。**根因是 TTS 自身吞吐**：`RTF_out=1.1937 > 1`（译文变长只占 `speech_over_src=1.2227`，已单列不混入）⇒ **TTS 提速请主会话转达 TTS 模块**（目标 `RTF_out ≤ 0.85`）；EXT 侧已把 D_required 算清（**19.939 s**）交用户定 D
② ⛔ **时长比 0.68~1.49 未解决**（EXT-034 未列入验收，但仍是未达标项）—— 需 TTS 提速后重测
③ ⛔ **EXT-028 待用户抽听 ⇒ V2.0 插件部分暂不放行**（旧结论已在 §25 撤回）—— 交付物已落 `shared/ext_listen/ext032_20261102_010022/` 与 `shared/ext_listen/ext033_20261102_121928/`
④ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P3（打包）未开始**
⑤ ℹ️ **tabCapture 生产路径仍只能用户手势**（探针 12 次全败）—— 但 **EXT-033 已改走页面元素抓取**（`createMediaElementSource`）⇒ 该手势需求**已绕开**
⑥ ℹ️ **本轮关闭了两个 v2.1 空闲 pythonw**：PID **4896**（EXT-035 授权点名，**15:03:12** 关闭）+ PID **7896**（15:31:35 由 explorer 拉起的新实例，**21:28:05** 关闭）—— 两者均**先核对 `ExecutablePath` 仍在 v2.1 包目录**且命令行含 `bridge_launcher.py`（**未打印完整命令行**）⇒ 关闭后**设备互斥解除**（`_caption_app_running()=False`）⇒ 真实 e2e 才能跑起来；⚠️ **字幕 App 本体（`live_caption_app.py`）未碰**（不在 EXT-035 授权内），是它退出后 e2e 才拿到锁
⑦ ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准）；✅ **EXT-023 已收口**（§18 实测 `on_npu=17 / on_cpu=[]`）

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
| 自测套件 | **28 套**（`test_ext_selfcheck` **122 PASS / 0 FAIL**、★ `test_p1_plumbing` **112 PASS / 0 FAIL**、`test_ext029` **70 PASS / 0 FAIL**、★ `test_ext032_deliver` **29 PASS / 0 FAIL**）；node harness **29 PASS / 0 FAIL**；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改） | §21/§23/§25/§27 实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-035 / EXT-034** | 关 v2.1 空闲 pythonw 后重跑 e2e；EXT-034 四项（同步覆盖 / RTF 口径 / 首段过长 / 所需 D） | ✅ **已认领并执行**（§27）：EXT-035 验收 **5 项全过**（`t0UpPlayerOffsetSec=-3.389 s` / 首段就绪→起播 **0.005 s** / 开口静音 **14.620 s** / detail **14/14** / 三口径 1.1937·1.2227·1.4595）；⛔ **sync 35.1/41.9 s 未达标**（根因 TTS `RTF_out=1.19>1`，引擎属其它模块 ⇒ **请主会话转达 TTS 模块**） |
| **EXT-031** | 插件整合进发行包 V2.0，EXT 交交付清单 | ✅ **已执行**（§23）：`release/V20_HANDOFF.md` 已写；模拟发行包启动 **6 PASS**；★ **打包由 App 线程执行（APP-057）**；⚠️ **App 包内缺 `websockets`+`psutil` ⇒ 打包必补装**；⚠️ `liveDub.release` 需置 `true`（**打包必改 3 处**） |
| **EXT-030** | 巡检会话重叠 ⇒ 开工先拿「模块租约」 | ✅ **已执行**（§22）：自动化插入**四段**（`acquire`/`beat`/`addpid`/`release`）；★ 实测触发 BUSY → 等 30 min → TAKEOVER ⇒ 机制**真实生效**；⛔ **未改 `session_lease.py`** |
| **EXT-029** | 说话人旁路独立线程、不得反压 ASR | ✅ **已执行**（§21）：独立线程 + 有界队列 + 异步回填不等待；**ASR 等 GPU 锁 ≤0.004 %** ⇒ 不反压；5 轮真实 A/B + 4 个真缺陷已修；⚠️ 原文③「墙钟差异 ≤5%」实测**噪声主导不可用** ⇒ 改用机制直接度量 |
| **EXT-032 / EXT-028** | EXT-028 只修代码没交实录；「不构成打包阻塞」不成立 | ✅ **已执行**（§25）：**撤回**旧结论 ⇒ EXT-028 改「**待用户抽听**」；已交逐段三份音频对比（时长比 6/6 = 1.000–1.019、互相关 1.0000、SNR 120 dB）+ 静音分解 + 交付目录 `shared/ext_listen/ext032_20261102_010022/`；⛔ **tabCapture 生产路径自动化拿不到**（探针 12 次全败）⇒ 须用户手势 |
| **EXT-027** | 抓错音频 / 持锁 / 克隆接线 / 同步误差 / 按序播放 | 🟡 **部分落地**：① 抓流（API 已修，生产路径**未实测**）✅ / ② 持锁 ✅ / ③ 克隆 ⛔（`voice_source` 全 `'preset'`）④ 同步误差 ⛔（未动引擎）⑤ 按序播放 ✅（`dubPlaybackEnd` 不叠播） |
| **EXT-026 / EXT-024 / EXT-025 / EXT-023 / EXT-022** | e2e 冒烟 / 下行接通 / RESUME / 设备上报 / 编号与流水线默认 | ✅ **全部已执行**（§17–§23）：EXT-023 **已收口**（`on_npu=17 / on_cpu=[]`，无组件落 CPU）；EXT-026 两轮 60 s 真实跑通；EXT-024 **真实三引擎已验证下行通**（`dubDelivered=9`，下发 9/9）；⛔ **Edge 真实手势验收仍需用户本人做** |
| EXT-017 ④余项 / EXT-005 ① | 浏览器端人工验收（tabCapture 需真实用户手势） | 需**用户本人**操作（EXT-022 已定②）；本机只有 Edge ⇒ **自动化拿不到 tabCapture** |
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ✅ ducking + 字幕（§15）/ **目标语言已真正生效**（§16）/ **设置持久化已修好**（§19：8 控件 change/input 即时落盘 + 归一 + 幂等）/ **内存不持续增长已修好**（§19：3 类无界增长全部有界化，统计口径一字不变）；⛔ **克隆音色仍不可用**（旁路未接线，**依赖 ASR-013 交付**）；⛔ **「30 分钟不崩」未做**（需真实引擎 + 独占设备长跑）；⛔ **暂停拖动未做**（需真实浏览器 + 用户手势） |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；§9 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`（224 833 B）；§13~§16 见 `notes/sec13…sec16_*.md`。
>
> | 章节 | 明细全文 | 结论摘要 |
> |---|---|---|
> | §25 | `notes/sec25_ext032_deliver.md` | **EXT-032 交卷**：三份音频逐段对比（时长比 6/6、互相关 1.0000、SNR 120 dB）+ 静音成因分解 + `sync_err p50/p95=0/0 ms` + 交付目录 `shared/ext_listen/ext032_20261102_010022/`；★ **撤回「EXT-028 不构成打包阻塞」** |
> | §26 | `notes/sec26_ext033.md` | **EXT-033 交卷**：修 3 个真缺陷（**t0 跨时钟域** / **设备互斥恒失效** / **分析器 `rms` 遮蔽**）；真实三引擎 e2e 产物已落 `shared/ext_listen/ext033_20261102_121928/`；⛔ sync 28.7/29.5 s、开口静音 26.58 s、时长比 0.68~1.49 **未达标**（根因 TTS RTF 1.231 + 设备占用） |
> | §27 | `notes/sec27_ext034_035.md` | **EXT-034/035 交卷**：① 同步测量覆盖 **7/13 → 14/14**（`start(when)` 采样精确排程起点，onset 口径单列）② RTF **三口径分列**（1.1937 / 1.2227 / 1.4595）③ 首段**会话级拆两段**（startup 25.5→9.7 s，切点逐位不变）④ `D_required=19.939 s`；✅ **EXT-035 验收 5 项全过**（`t0UpPlayerOffsetSec=-3.389 s` / 首段就绪→起播 **0.005 s** / 开口静音 **14.620 s** / detail **14/14** / 三口径分列）；⛔ sync **35.1/41.9 s** 未达标（根因 TTS `RTF_out=1.19>1`） |

## §26 —— EXT-033 交卷：三个真缺陷修复 + 真实三引擎 e2e（2026-11-02 14:10）

★ **全量明细见 `status/notes/sec26_ext033.md`**（逐条证据、实测值、反证组）。

⇒ **三个真缺陷**（均有实测证据）：**① `t0` 跨时钟域**（上行域算、player 域消费 ⇒ 两 context 原点独立 ⇒ `schedClamped=13`、误差恒为正 19.9~29.5 s）⇒ 改在 player 域测 `Δ`（**60 帧中位数**；`currentTime` 只在渲染量子推进时更新 ⇒ 单次相减带 ~80 ms 噪声）⇒ `t0 = t0_up + Δ`，保留 `t0Up*` 三字段可自证，`requested` 算式一字未改（浏览器实测 Δ≈0.37~1.05 s，9 PASS）。**② 设备互斥从未生效**（依赖 `psutil`，App 自带 python 没有 ⇒ 恒 False；且只匹配 `live_caption`，本机是 `LiveCaption` ⇒ 双重漏检）⇒ 改 `wmic`→`Get-CimInstance`→`tasklist` 三级降级 + 按 App 真实入口匹配 + 拿不到列表保守判「可能在跑」；实测 0.56 s 检出、3 个非 App 进程不误报 ✅；**修复的直接证明 = 本轮 e2e 被正确拦下（rc=3）**。**③ 分析器自带 bug**（`voiced_span()` 里 `rms` 遮蔽全局 `rms()` ⇒ fallback 必 `UnboundLocalError`）⇒ 改名 `_rms_blocks`。

⇒ **真实三引擎 e2e**（run `20261102_121431`）：输入 = **页面元素**（`createMediaElementSource`，非整机声；`gaps=0`、`maxAbsSkewAudioMs=1.08`）；**13 段 TTS**；录音 WAV 10 012 716 B / 48 kHz / **104.299 s 不截断**。❌ 未达标：开口静音 **26.58 s**（≤15 s）；sync P50/P95 = **28650.0 / 29537.8 ms**（≤300 ms）；时长比 **0.6825~1.4851**。

⇒ **滞后归因（**超出本模块职责**）**：`feed_lag` **全为负**（mean −5.85 s ⇒ 音频准时到，**不是上行/反压**）；滞后以 **0.3146 s/s 累积** ⇒ 管线吞吐 < 1；**TTS RTF=1.231 > 1**（ASR 0.773 / MT 0.193）⇒ **TTS 提速 EXT 改不动**（引擎属其它模块）⇒ 写进 STATUS 交主会话，本轮**不碰任何引擎文件**。

⇒ **自测（实测 rc）**：`test_ext_selfcheck` **106** ｜ `test_echo_roundtrip` **11** ｜ `test_next_instruction` **19** ｜ `test_ext033_capture` **42** ｜ `test_ext033_deliver` **25** ｜ `ext033_t0_verify` **9** —— 全 **0 FAIL**。

⇒ **⛔ 明确未做**：⛔ **没跑出「修复后」的真实 e2e**（设备被字幕 App 占用 ⇒ 不抢设备 ⇒ rc=3）｜⛔ 开口静音 / 时长比 **未解决**｜⛔ **未打包**（APP-057）/ **未改引擎文件** / **未推远程** / `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`git check-ignore` 命中 `.gitignore:34`）。

## §27 —— EXT-034 / EXT-035 交卷：四项缺陷修复 + EXT-035 验收 5 项全过（2026-11-02 21:40）

★ **全量明细见 `status/notes/sec27_ext034_035.md`**（指令原文、逐项根因、逐段数据、命令与实测值）。

⇒ **① EXT-035① 关进程（授权范围内全执行）**：PID **4896**（点名 v2.1）**15:03:12** 关；PID **26736**（v2.2）**排队拿锁后关**；PID **7896**（新出现的同类 v2.1）**21:28:05** 关。三者均**先核对 `ExecutablePath` 在对应包目录 + 命令行含 `bridge_launcher.py`（未打印完整命令行）**、**普通 `Stop-Process`**、记录时间与核对结果 ⇒ **其他实例一律未碰**；⛔ **字幕 App 本体不在授权内 ⇒ 从未关闭**（它自己退出、锁才释放）。

⇒ **② EXT-034① 同步覆盖 7/13 → 14/14（双重根因）**：① **onset 配对被「最近的下一段排程」抢走**（`PAIR_WINDOW_SEC=0.25`，实测 `dubOnsets` 有 50 ms 间隔连续 onset）；② **TTS 中文开头常是辅音/静音 ⇒ onset 未必触发** ⇒ 13 段只进 7 段。修法 = **主口径改用 `start(when)` 采样精确排程起点**（比 `onended` 反推可靠，不把回调延迟 10–40 ms 当同步误差），onset 口径**单列**；★ 顺带**修掉污染 bug**：`noteDubEnded()` 原把**排程口径**的 `signedErrMs` 推进 `dubSyncErrsOnset` ⇒ 两口径混在同一数组（已删，C4f/C4g 反证组守护）。

⇒ **③ EXT-034② RTF 三口径分列**（落盘 `margin.json`）：`RTF_out=1.1937`（Σtts/Σspeech）｜`speech_over_src=1.2227`（Σspeech/Σsrc）｜`tts_over_src=1.4595`（Σtts/Σsrc）。★ 旧结论「TTS RTF=1.231」实为 **`tts_over_src`**（混入译文变长）⇒ 三者含义各自明确，可交叉核对 `tts_over_src == RTF_out × speech_over_src`。

⇒ **④ EXT-034③④ 首段会话级拆分 + 所需 D**：ASR **整段到齐才定稿** ⇒ 起步耗时 ≈ 首段长+ASR+MT+TTS ⇒ **会话级拆首段**（`FIRST_SEGMENT_MAX_SEC=3.5`，**拆两段而非截短** ⇒ 后续切点**逐位不变**、尾段行为不变）⇒ startup **25.547 → 9.731 s**；`D_required = 19.939 s`（vs 当前 D=10 s ⇒ **光调 D 不够**，须先提 TTS 吞吐）⇒ **交用户定 D**。★ 关键设计：`split_first_segment()` 抽到 **`ext/segmenter.py` 共享**，**服务端与客户端同一份代码** ⇒ 口径永不漂移。

⇒ **⑤ EXT-035② 修复后真实三引擎 e2e（≥75 s，两轮跑完 EXIT=0）—— 验收 5 项全过**：`t0UpPlayerOffsetSec=**−3.389333 s**`（非空，spread 16 ms）✅｜**首段就绪→起播 0.005 s**（<0.5 s）✅｜**开口静音 14.620 s**（≤15 s；旧轮 26.59 s）✅｜**`dubSyncDetail` 14/14**（旧轮 7/13）✅｜**三口径分列** ✅｜附带录音 **99.099 s** ✅。
　★ 新增「**就绪→起播**」口径（原先**根本无法测量**）：`dubReadyAt`（段 id → 就绪时刻，AudioContext 时钟，**排程之前**取）+ `readyAtAc`/`readyToStartSec`（= `actual − readyAtAc`，**不含 D、不含服务端起步**）⇒ 14 段全有值；首段 0.005 s，其余 6 段 >0.5 s 是**按序播放排队**（前一段未播完）⇒ **不是缺陷，是设计**。

⇒ **⑥ EXT-034① 分析侧收尾**：`_sync_coverage()` 拿 `margin.json` 的「有 TTS 的段」做全集，与 detail 按**采样点后缀**对齐（⚠️ 两者 id 前缀有无不同 ⇒ 直接求差会把全部段算成缺失）⇒ 输出覆盖率 + 缺失归因（附**可核对证据字段**）⇒ 旧产物实测 `coverage=0.5385 / missing=6`，缺失段与 EXT-034 原文**逐位一致**。

⇒ **⑦ 自测（实测 rc）**：`test_ext_selfcheck` **122** ｜ `test_echo_roundtrip` **11** ｜ `test_next_instruction` **19** ｜ `test_p1_plumbing` **112** ｜ `test_ext033_capture` **42** ｜ `test_ext033_deliver` **25** ｜ `test_ext010_pipeline` **25** ｜ `ext028_player_harness.js`（node 沙箱）**29** —— **八套全 0 FAIL**。
　★ 透明说明：`test_p1_plumbing` 的 `test_expected_segment_count_strict` **参照基准**从「未拆分的 raw」换成「**服务端口径**」—— ⚠️ **不是回归**：已用**真桥接服务对拍**（45 s 音频 ⇒ 服务端实际 **7** 段 = `raw 6`+1，客户端 `expected=7` ⇒ 三者一致）；断言强度与意图**一字未减**，另**追加** EXT-034④ 专属自测组（12 条）。

⇒ **⑧ ⛔ 明确未做**：⛔ **sync 有符号误差本身仍未达标**（P50/P95 = **35.1 / 41.9 s**，判据 ≤300 ms）—— 根因是 **TTS 自身吞吐**（`RTF_out=1.1937 > 1`）⇒ **TTS 提速请主会话转达 TTS 模块**（目标 `RTF_out ≤ 0.85`）；⛔ **时长比 0.68~1.49 未解决**（需提速后重测）；⛔ **未打包**（APP-057）/ ⛔ **未改任何引擎文件**（R2T2 / Hy-MT2 / Qwen3-TTS 一律未动）/ ⛔ **未改 `session_lease.py`** / ⛔ **未推远程** / ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`git check-ignore` 命中 `.gitignore:34`）。
