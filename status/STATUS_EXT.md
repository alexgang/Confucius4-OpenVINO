# STATUS_EXT
last_ack: EXT-031
更新时间: 2026-11-01 21:25
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§24 EXT-030/031 落库收口** —— ★ 上一会话「实现做完即死」，闸门 **exit 1 只判「认领」不判「收口」** ⇒ 本轮**未重做实现**，只**补记 EXEC_LOG + 提交** ⇒ ✅ 复核 106/11/19 + 24 + 6 + 42 + 70 全 **0 FAIL** ⇒ ⚠️ ⛔ 打包未做（App 线程 APP-057）/ ⛔ 音色克隆仍不可用 / ⛔ tabCapture 生产路径未实测 / ⛔ 端到端仍不实时（TTS RTF 1.0022）/ ⛔ 同步误差仍超标

阻塞 / 待决定:
① ⛔ **Edge 真实手势 1 分钟验收（EXT-024 验收 1–4 条）** —— 需**用户本人**在 Edge 默认 profile 手动：双击桌面「实时配音桥接.cmd」→ 等就绪 → 打开英文网页视频 → 点扩展「开始」→ player 点「开始捕获」→ 连播 1 分钟；截图 30 s / 60 s 各一张；bridge.log 本次段级日志 ≥5 段且「下发到 player」段数 = TTS 段数、无「不顶替」无 10048
② ⛔ **端到端仍不实时，TTS 提速是上线的唯一前置** —— 稳态端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**，源 `.tmp/ext008_bench/steady.json`）⇒ 建议目标 ≤ 0.85，**由主会话转达 TTS 模块**
③ ⛔ **同步误差仍全部超标** —— 流水线轮 `sync_err_ms.p50=67289.3` / `n_over_target=22` / `last_segment_lag_sec=71.2074`（源 `.tmp/p1_pipe/p1_report.json`）⇒ 实时未达成
④ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P3（打包）未开始**
⑤ ℹ️ **tabCapture 生产路径仍未实测**（EXT-005 ①）+ **浏览器端人工验收未做**（EXT-017 ④余项）⇒ 均需真实用户手势，由用户本人做
⑥ ℹ️ **EXT-009 服务端 lag 估计存在跨时钟常量偏差，尚未定量标定**（§17 已写清与 t_start 时间轴口径的关系；决策在服务端，不影响变速稳定性）；ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准）；✅ **EXT-023 已收口**（§18 实测 `on_npu=17 / on_cpu=[]`，cp_decode=NPU）

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
| 自测套件 | **27 套**（`test_ext029` **70 PASS / 0 FAIL**、`test_ext031` **24 PASS / 0 FAIL**）；node harness **8 套 rc=0**；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改） | §21/§23 实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-031** | 插件整合进发行包 V2.0，EXT 交一份可打包的交付清单 | ✅ **已认领并执行**（§23）：`release/V20_HANDOFF.md` 已写（六项齐全）；**模拟发行包启动实测 6 PASS / 0 FAIL**；★ **打包由 App 线程执行（APP-057）**；⚠️ **App 包内缺 `websockets`+`psutil` ⇒ 打包必补装**；⚠️ `liveDub.release` 需置 `true`（**打包必改只有 3 处**） |
| **EXT-030** | 巡检会话互相重叠 ⇒ 每会话开工前先拿「模块租约」 | ✅ **已认领并执行**（§22）：自动化指令已插入**四段**（`acquire`/`beat`/`addpid`/`release`），原文见 notes §22.1；★ 本轮**实测**触发 BUSY → 等 30 min → TAKEOVER ⇒ 租约机制**真实生效**；⛔ **未改 `session_lease.py`**（只读使用） |
| **EXT-029** | 说话人旁路必须独立线程、不得反压 ASR | ✅ **已认领并执行**（§21）：独立线程 + 有界队列 + `put_nowait` + 满丢旧块计数 + **异步回填不等待**；**ASR 等 GPU 锁 A max 0.0007 s / B max 0.0008 s**（≤0.004 %）⇒ **不反压 ASR**；5 轮真实三引擎 A/B 实测 + 4 个真缺陷已修；⚠️ 原文③「墙钟差异 ≤5%」经实测判为**噪声主导不可用** ⇒ 改用**机制直接度量** |
| **EXT-027** | 输入音频抓错 / 持锁铁律 / 克隆接线 / 同步误差 / 按序播放 | 🟡 **部分落地**：① 抓流（tabCapture **API 已修正**，但生产路径**未实测**——自动化拿不到，需用户点扩展图标）✅代码 / ② 持锁铁律 ✅ / ③ 克隆接线 ⛔（`voice_source` 全 `'preset'`）④ 同步误差 ⛔（未动引擎）⑤ 按序播放 ✅（`dubPlaybackEnd` 不叠播） |
| **EXT-028** | 配音录音听不清 | ✅ **代码侧已修**：根因是服务端不传 `sample_rate` 时插件按 16 kHz 重建 24 kHz 波形 ⇒ 1.5× 语速 + 升调 ⇒ 新增 `resolvePcmSampleRate()`；自测 `test_ext028_dub_audio_chain.py` **42 PASS / 0 FAIL**、node harness rc=0 ⇒ **不构成打包阻塞** |
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
> | §22 / §23 | `notes/sec22_23_ext030_lease_ext031_handoff.md` | **EXT-030** 模块租约已接入自动化指令（实测 BUSY→TAKEOVER）；**EXT-031** V2.0 交付清单 + 不依赖开发目录实测 |

## §21 EXT-029 —— 说话人旁路：**独立线程 + 有界队列 + 异步回填**（不反压 ASR）（2026-11-01 16:14）

★ **原内联正文逐字存档见 `notes/sec21_24_inline_archive.md`**；全量明细（7 节）见 `notes/sec21_ext029_spk_bypass_thread.md`。

⇒ **结论**：4 个真缺陷已修（**D1** 流水线不登记定稿段 `n_final_req=0`→补 `_request_spk_label()`→复测 `n_final_req=19`；**D2** `tabCapture.capture({targetTabId})` **API 用错**（属 `getMediaStreamId()`）→改 `getMediaStreamId({targetTabId})`+`chromeMediaSource:'tab'`；**D3** `margin.json` 缺真实 ASR 墙钟→增落 `pipeline.stage_wall_sec.asr`；**D4** safe-delete 钩子腰斩录音分析→唯一 profile 名+`reuse_profile=True`）；★ 判据改用「ASR 等 GPU 锁时间」度量（原文「墙钟差异 ≤5%」被环境噪声主导：A 臂 ASR 自身 **21.9020–67.8250 s**、**3.1×** 波动）⇒ **A max 0.0007 s / B max 0.0008 s（≤0.004 %）⇒ 不反压 ASR** ✅；旁路指标 `spk_queue_drop` **0–57** / `spk_worker_busy_ms` **276.6–777.5** / `spk_gpu_lock_held_ms` **1726.1–6793.3**（占 ASR 墙钟 **4.5–24.0 %**）/ `n_label` **2–8** / 检出 **S1/S2(/S3)**；自测三套明文 **106/11/19** + `test_ext029` **70 PASS / 0 FAIL**（+12）；机器锁**等、不抢**（`ctypes` `OpenProcess`+`GetExitCodeProcess`，code=259 ⇒ 存活）；⛔ 音色克隆未接线、Edge 手势验收未做、tabCapture 生产路径未实测、端到端仍不实时（TTS RTF 1.0022）。

## §22 EXT-030 —— 巡检会话互相重叠：**模块租约**已接入自动化指令（2026-11-01 16:27）

★ **原正文逐字存档见 `notes/sec21_24_inline_archive.md`**；全量明细（含自动化指令新增四段原文）见 `notes/sec22_23_ext030_lease_ext031_handoff.md` §22.1。

⇒ **① 实测触发 EXT-030 描述的正是它自己的故障**：开工时租约被**另一 EXT 会话**（`c3389eb3`，15:42 起）持有 ⇒ `acquire ext` **exit 10 (BUSY)** ⇒ 按铁律**没抢**（后台轮询）⇒ 对方心跳停在 15:44（**21.7 min**）⇒ 满 30 min TTL ⇒ **exit 0 + `TAKEOVER`** ⇒ ★ **租约机制真实生效**（重叠被挡 → 超时自动接管 → 从断点继续）。
⇒ **② 自动化指令已改好**（id=`9ec49c32-…`，`FREQ=HOURLY`）新增**四段**：`acquire`（插在「第 0 步」之前）/ `beat` 心跳 / `addpid` / 结束 `release`；铁律区补「租约与 MACHINE_LOCK **互不替代**」。
⇒ **③ 证据**：`shared\leases\ext.json`（389 B，mtime 16:15）；`.workbuddy\logs\automation.log`（1 015 237 B，mtime 16:17）。
⇒ **④ 本轮未碰 MACHINE_LOCK**；⛔ 未改 `session_lease.py`（只读使用）/ 未改其他四模块自动化 / 未推远程。

## §23 EXT-031 —— 插件整合进发行包 V2.0：**交付清单已写 + 不依赖开发目录已实测**（2026-11-01 16:27）

★ **原内联正文逐字存档见 `notes/sec21_24_inline_archive.md`**；全量明细见 `notes/sec22_23_ext030_lease_ext031_handoff.md`。

⇒ **结论**：交付清单 `release/V20_HANDOFF.md`（新建）六项齐全（插件 unpacked **15 文件 / 219 021 B** / 桥接入口命令 / Python 依赖及 **App 包内缺的 `websockets`+`psutil` ⇒ 打包必须补装** / 模型与 IR 映射**不另带一份** / 端口 8765·8766 + token + 日志位置 / 首次启动步骤）；★★「不依赖开发目录」**实测** `tests/smoke/ext031_fake_pkg_launch.py` 造**模拟发行包根**（目录名故意不叫 `live_dub_ext`）⇒ **6 PASS / 0 FAIL**：引擎根+模型目录+说话人 IR **全在包内**（越界**无**）/ 解析结果**不含**开发机目录名 / `package_root()`=模拟包 / `EXT_RELEASE=1` ⇒ 白名单只留 `tabCapture`；证据 `.tmp/ext031/fake_pkg_probe.json`（**2 836 B**）；发行版调试剔除实测**真生效**（`allowedCaptureModes` **真拦截** `getDisplayMedia`／`--audio-dump-out`·`--margin-out` **忽略**／另剔 `probe-worklet.js` **391 B** 零引用）；EXT-028 ✅ 已修（**42 PASS / 0 FAIL**）⇒ **不构成打包阻塞** ⇒ ★ **插件部分 = 可打包**（**打包必改只有 3 处**）；⛔ 打包由 App 线程执行（APP-057）、音色克隆不可用、端到端仍不实时（RTF **2.0507** / TTS **1.0022**）、同步误差仍超标（`sync_err_ms.p50=67289.3`）。

## §24 —— EXT-030/031 **落库收口**：上一会话「做完就死」⇒ 接管补记 EXEC_LOG + 提交（2026-11-01 20:59）

★ **全量明细见 `status/notes/sec24_takeover_closeout.md`**（7 节）；原内联正文逐字存档见 `status/notes/sec21_24_inline_archive.md`。

⇒ **① ★★ 闸门 exit 1 只判「认领」，不判「收口」** —— 上一会话（token=`16a4f381`，末次心跳 **16:28:10**）把 EXT-030/031 **实现做完了**却**死在收口之前**：`EXEC_LOG.md` 里 EXT-030/031 记录数 = **0**、`git log` 仍停在 **`daaa00d`**（§21）⇒ 闸门复测 **exit 1 / `action=skip`** ⇒ 若直接跳过，**成果将永久搁浅** ⇒ 本轮**未重做实现**，只**补齐收口**（EXEC_LOG + 本节 + 提交）。
⇒ **② ★ 独立复核（实测重跑，非照抄）**：三套明文 **106 / 11 / 19 PASS、0 FAIL**（rc=0）；`test_ext031` **24 / 0**；`ext031_fake_pkg_launch` **6 / 0**；`test_ext028` **42 / 0**（EXT-031④ 打包门禁 ✅）；`test_ext029` **70 / 0**；`test_ext016_compression` 38 PASS / **1 FAIL**（既有基线红：CORRECTIONS **38 693 B** > 阈值 20 480 B ⇒ **reviewer 独占文件，只读不改**）。
⇒ **③ ★ 抽查「不是只写不生效」**：`extension/offscreen.js` 的 `allowedCaptureModes` **真拦截** `getDisplayMedia`（**明确失败**，绝不静默抓整机声音）；`ext/bridge.py:3099`/`:3145` 的 `--audio-dump-out`/`--margin-out` **真被 `RELEASE_MODE` 挡住**；`RELEASE_MODE` **显式覆盖优先** ✅。⚠️ `ext/config.py` 的 `CAPTURE_MODES` 在 `ext/` 内**无消费点** ⇒ 真正生效的是**插件侧** `offscreen.js`（**同名不同源**，勿混）。
⇒ **④ ★ 时间戳口径修正 + 一处旧章节数字不一致（禁止推算；不改旧文件，只如实标出）**：§22/§23 原写 **`16:45`**，但落盘 mtime = **16:27:19**、末次心跳 = **16:28:10** ⇒ **16:45 从未发生**（预写值）⇒ 本轮落库前改为**实测 16:27**、头部「更新时间」改为本轮实测；**§22/§23 结论与数字一字未改**。另：`notes/sec21_*.md` §21.6 记 `test_ext029` **56 PASS**（中途快照），§21 正文与 EXEC_LOG 记 **70 PASS**，本轮实测亦为 **70 / 0** ⇒ **70 为准**。
⇒ **⑤ ★ 报给 reviewer 的两个制度性缺口**：① 闸门 exit 1 **不校验「EXEC_LOG 有记录 + 已入库」** ⇒ 一个会话「做完就死」时下一轮直接跳过、**成果永久搁浅**（本轮即遇此情形）⇒ 建议**额外校验**「`last_ack` 对应编号是否在 `EXEC_LOG.md` 有记录且已入库」；② `session_lease.py` 的 **TTL = 30 min** ⇒ 上一会话「30 min 内活跃但已卡死」时新会话要**干等 30 min**（reviewer 可把 `TTL_MIN` 调至 **10–15**；★ 本模块**不改**该脚本）。
⇒ **⑥ ⛔ 未做 / 不宣称**：⛔ **打包未做**（App 线程 APP-057 执行 ⇒ **未产出 zip**）；⛔ 未改引擎 / 未推远程 / `CORRECTIONS_EXT.md` 只读未入库（其余阻塞项见 §23 ⑥ 与「未完成纠偏清单」表）。


> **§16 ~ §10 —— 已下沉**（明细全文在 `status/notes/`；§10 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`）：
> * **§13 ~ §16** 见 `notes/sec13…sec16_*.md`；**§12 / §11** 启动器 `start()` **4.244 s → 0.032 s**（EXT-017②）、STATUS 拆分归档（`notes/sec11_12_ext016_closeout.md`）
> * **§10** 控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`（用户方式实测通过，6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。

