# STATUS_EXT
last_ack: EXT-029
更新时间: 2026-11-01 16:14
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§21 EXT-029 收口**（闸门 **exit 0** / latest=EXT-029 ⇒ **认领 EXT-029** ⇒ `last_ack` = **EXT-029**）⇒ ✅ **说话人旁路已接成独立线程 + 有界队列 + 异步回填**（`ext/speaker_bypass.py` / `ext/spk_engine.py`：分段@**NPU**、嵌入@**GPU.0** 与 ASR 共用公平锁）⇒ ✅ **5 轮真实三引擎 A/B 实测**：**ASR 等 GPU 锁时间 A max 0.0007 s / B max 0.0008 s**（≤0.004 %）⇒ **旁路没有反压 ASR** ⇒ ✅ **`spk_queue_drop` 0–57 / `spk_worker_busy_ms` 276–778 ms**（60 s 音频只忙 ≈0.5 %）⇒ ✅ **检出 S1/S2(/S3)**（多说话人真被区分）⇒ ★ **实测抓到并修掉 4 个真缺陷**（流水线从不登记标签 / tabCapture API 用错 / margin 缺真实墙钟 / 录音分析被腰斩致 summary 没落盘）⇒ ★ **EXT-029③ 判据口径修正**（墙钟相对差异被环境噪声主导：A 臂自身 21.90–67.83 s 波动 3.1×、有符号差异符号不一致 ⇒ 改用「ASR 等锁时间」）⇒ ✅ 自测 **26 套**，`test_ext029_spk_bypass.py` **70 PASS / 0 FAIL**（+12），node harness **8 套 rc=0** ⇒ ✅ **STATUS 已按 EXT-016 规则压回 19 424 B / 142 行**（§19/§20 内联正文下沉到 `status/notes/sec19_20_closeout.md`，数字一字未改）⇒ ⚠️ ⛔ **音色克隆仍未接线**（`voice_source` 全 `'preset'`）/ ⛔ **Edge 真实手势验收仍需用户本人做** / ⛔ **tabCapture 生产路径未实测**（Chrome 要求用户激活）/ ⛔ **英译中仍未真正测到**（抓流仍是整机声音）/ ⛔ 「30 分钟不崩」未做 / 暂停拖动未做 / 端到端仍不实时（TTS RTF 1.0022）/ 同步误差仍超标（既有阻塞项，未动引擎）

阻塞 / 待决定:
① ⛔ **Edge 真实手势 1 分钟验收（EXT-024 验收 1–4 条）** —— 需**用户本人**在 Edge 默认 profile 手动：双击桌面「实时配音桥接.cmd」→ 等就绪 → 打开英文网页视频 → 点扩展「开始」→ player 点「开始捕获」→ 连播 1 分钟；截图 30 s / 60 s 各一张；bridge.log 本次段级日志 ≥5 段且「下发到 player」段数 = TTS 段数、无「不顶替」无 10048
② ⛔ **端到端仍不实时，TTS 提速是上线的唯一前置** —— 稳态端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**，源 `.tmp/ext008_bench/steady.json`）⇒ 建议目标 ≤ 0.85，**由主会话转达 TTS 模块**
③ ⛔ **同步误差仍全部超标** —— 流水线轮 `sync_err_ms.p50=67289.3` / `n_over_target=22` / `last_segment_lag_sec=71.2074`（源 `.tmp/p1_pipe/p1_report.json`）⇒ 实时未达成
④ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P3（打包）未开始**
⑤ ℹ️ **tabCapture 生产路径仍未实测**（EXT-005 ①）+ **浏览器端人工验收未做**（EXT-017 ④余项）⇒ 均需真实用户手势，由用户本人做
⑥ ℹ️ **EXT-009 服务端 lag 估计存在跨时钟常量偏差，尚未定量标定**（§17 已写清与 t_start 时间轴口径的关系；决策在服务端，不影响变速稳定性）；ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准）；✅ **EXT-023 已收口**（§18 实测 `on_npu=17 / on_cpu=[] / on_unknown=[]`，cp_decode=NPU）

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
| **说话人旁路（EXT-029，已收口）** | **独立线程 + 有界队列(64) + `put_nowait` 入口**（满则**丢最旧块**并计数 `spk_queue_drop` 0–57）；标签**异步回填**（`n_label` 2–8，未到走**方案 A** 不等待）；**ASR 等 GPU 锁 A max 0.0007 s / B max 0.0008 s**（≤0.004 %）⇒ **不反压 ASR**；旁路占 GPU 锁**上界** 4.5–24.0 % | `ext/speaker_bypass.py` / `ext/spk_engine.py`；`.tmp/ext028_029_e2e/agg_summary.json` |
| **pyannote 旁路（EXT-029 已接）** | 分段推理跑在 **NPU**、wespeaker 嵌入跑在 **GPU.0**（实测 NPU/GPU.1 不可用），经 `asr052_spk_runtime` 交付集合调用 ⇒ **pyannote 旁路本身已通**；检出 **S1/S2(/S3)** | `ext/spk_engine.py`（§21 notes） |
| **克隆音色（仍未接线）** | `voice_source` 实测**全 `'preset'`**、`clone_wired=false` ⇒ 引擎层 `tts()` 的 `voice` 参数**未**接进 `tts_engine.stream()` ⇒ **不宣称克隆音色可用** | `ext/bridge.py` → `_resolve_spk()` |
| 自测套件 | **26 套**（`test_ext029_spk_bypass.py` **70 PASS / 0 FAIL**，本轮 +12）；node harness **8 套全 rc=0**；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改） | §21 本轮实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-029** | 说话人旁路必须独立线程、不得反压 ASR | ✅ **已认领并执行**（`last_ack` = **EXT-029**，§21）：独立线程 + 有界队列 + `put_nowait` + 满丢旧块计数 + **异步回填不等待**；**ASR 等 GPU 锁 A max 0.0007 s / B max 0.0008 s**（≤0.004 %）⇒ **不反压 ASR**；5 轮真实三引擎 A/B 实测 + 4 个真缺陷已修；⚠️ 原文③「墙钟差异 ≤5%」经 5 轮实测判为**噪声主导不可用** ⇒ 改用**机制直接度量**并在 §21 写清 |
| **EXT-027** | 输入音频抓错 / 持锁铁律 / 克隆接线 / 同步误差 / 按序播放 | 🟡 **部分落地**：① 抓流（tabCapture **API 已修正**，但生产路径**未实测**——自动化拿不到，需用户点扩展图标）✅代码 / ② 持锁铁律 ✅ / ③ 克隆接线 ⛔（`voice_source` 全 `'preset'`）④ 同步误差 ⛔（未动引擎）⑤ 按序播放 ✅（`dubPlaybackEnd` 不叠播） |
| **EXT-028** | 配音录音听不清 | ✅ **代码侧已修**：根因是服务端不传 `sample_rate` 时插件按 16 kHz 重建 24 kHz 波形 ⇒ 1.5× 语速 + 升调 ⇒ 新增 `resolvePcmSampleRate()`；自测 `test_ext028_dub_audio_chain.py` **42 PASS / 0 FAIL**、node harness `ext028_player_harness.js` rc=0 |
| **EXT-026** | 真实三引擎端到端自动化冒烟 + 落盘配音/截图/段级日志 + 修 `seenDubIds` 撞号 | ✅ **已认领并执行**（`last_ack` = EXT-026）；两轮各 60 s 真实跑通、证据齐全、录音实测非静音（明细见 §18）；⛔ **Edge 默认 profile 真实手势验收仍需用户本人做** |
| **EXT-024** | 下行接通 / 会话生命周期 / 启动器 / 段级日志 / 状态条 / 模式显示 / 语言映射 | ✅ **代码侧 A–G 全部落地**（§17）；✅ **真实三引擎上已验证下行通**（§18：`dubDelivered=9`、`下发到=player,uplink` 9/9）；⛔ **Edge 真实手势 1 分钟验收未做**（由用户本人做） |
| **EXT-025** | RESUME：额度已重置，从 last_ack 继续 | ✅ **已认领并执行**（`last_ack` = EXT-025） |
| **EXT-023** | TTS 启动日志打印各组件 EXECUTION_DEVICES | ✅ **已收口**（§18）：真实跑批实测 `on_npu=17 / on_cpu=[]`，`cp_decode`=NPU，**无任何组件落在 CPU**（源 `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`） |
| **EXT-022** | 编号规则 / 待命规则 / 流水线默认开 / 冒烟脚本入库 | ✅ **全部落地**（编号改 T-1…T-4；`--pipeline` 默认 True；`tests/smoke/` 已入库，4 脚本实测 rc=0） |
| EXT-017 ④余项 | 浏览器端人工验收（tabCapture 需真实用户手势） | 需**用户本人**操作（EXT-022 已定②）；本机只有 Edge |
| EXT-005 ① | tabCapture 生产路径实测 | ⏳ **代码侧已就绪**（`capture_mode` 进 stats / margin.json）；⚠️ **自动化下拿不到 tabCapture**（需真实手势，实测错误原文见 §18）⇒ **仍需用户点一次扩展图标**（§13） |
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ✅ **ducking + 字幕已修好**（§15）；✅ **目标语言已真正生效**（§16，`applied_target_lang` 可核对）；✅ **设置持久化已修好**（§19：改了就落盘，8 个控件 change/input 即时落盘 + 归一 + 幂等）；✅ **内存不持续增长已修好**（§19：3 类无界增长真缺陷全部有界化，统计口径一字不变）；⛔ **克隆音色仍不可用**（pyannote 旁路未接线，**依赖 ASR-013 交付**）；⛔ **「30 分钟不崩」未做**（需真实引擎 + 独占设备长跑，本轮只做了「内存不持续增长」这一半）；⛔ **暂停拖动未做**（需真实浏览器 + 用户手势，且属新增交互 ⇒ 待 reviewer 明确口径） |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；
> §9 及更早的章节全文在 **`status/archive/STATUS_EXT_upto_20261030.md`**（224 833 B）。
> （★ §13~§16 的明细全文仍在 `status/notes/sec13…sec16_*.md`，只是不再在指针表里逐行列出。）
>
> | 章节 | 明细全文 | 结论摘要 |
> |---|---|---|
> | §17 | `status/notes/sec17_ext024_closeout.md` | EXT-024 A–G + EXT-023 + EXT-022 全量明细（含根因、实测、反证、产物表） |
> | §18 | `status/notes/sec18_ext026_real_e2e.md` | EXT-026 真实三引擎端到端冒烟全量明细（两条路径各 60 s、证据清单、录音非静音实测、EXT-023 收口、5 个真缺陷） |
> | §19 | `status/notes/sec19_t5_t6_bounds_persist.md` | T-5 内存不持续增长（3 类无界增长真缺陷 + 统计口径不变）+ T-6 设置持久化（改了就丢的真缺陷）全量明细（含 6 条反证与 2 个测试自身的坑） |
> | §20 | 本文件内联（§19 收口） | 补 EXEC_LOG + 提交 + **STATUS 压缩回 EXT-016 限额内** |
> | §21 | `status/notes/sec21_ext029_spk_bypass_thread.md` | **EXT-029 说话人旁路**：独立线程 + 有界队列 + 异步回填（不反压 ASR）；实测抓到并修掉 **4 个真缺陷**；A/B 多轮实测 |

### §19 T-5 / T-6 —— 内存不持续增长（无界列表有界化） + 设置持久化（2026-10-31 23:21）

★ **明细全文见 `status/notes/sec19_t5_t6_bounds_persist.md`**（6 节，13 267 B）
★ **本节原内联正文（含 §19 / §20 两节全文）已下沉到 `status/notes/sec19_20_closeout.md`**（按 EXT-016 规则裁剪，数字一字未改）

⇒ **结论**：3 类无界增长真缺陷全部有界化（统计口径一字不变） + 设置持久化修好（改了就落盘）
⇒ 自测 **24 套 / 1 104 PASS / 1 FAIL**（唯一 FAIL = 既有 `test_ext016_compression` 的 CORRECTIONS 体积项，属 reviewer 独占文件 ⇒ 只读不改）；node harness **7 套 rc=0**。

### §20 §19 收口 —— 补 EXEC_LOG + 提交 + **STATUS 压缩回限额内**（2026-11-01 00:57）

★ **明细全文见 `status/notes/sec19_20_closeout.md`**

⇒ **结论**：补完 §19 的 EXEC_LOG + 提交；并发现并修掉一个本轮引入的回归（STATUS 被写到 29 652 B → 破过 EXT-016 硬约束 「< 归档/10 = 22 483 B」）→ 按规则把 §17/§18/§19 内联明细下沉到 notes，STATUS 回到限额内；三套明文自测 **rc=0**（103/11/19）。

## §21 EXT-029 —— 说话人旁路：**独立线程 + 有界队列 + 异步回填**（不反压 ASR）（2026-11-01 16:14）

**依据**：闸门 **exit 0**（latest=**EXT-029** / last_ack=26 / `n_entries=13`）⇒ **认领 EXT-029** ⇒ `last_ack` = **EXT-029**。
★ **明细全文见 `status/notes/sec21_ext029_spk_bypass_thread.md`**（7 节）——本节按 EXT-016 规则**只留结论**。

⇒ **① 开工状态**：工作区有 **9 个已改 + 9 个新文件**的**未提交在制品**（EXT-027/028/029，一轮被中断）
⇒ 本轮**不推倒重做**，而是逐条核对 + 实测找缺陷 + 补证据 + 收口。

⇒ **② ★实测抓到并修掉 4 个真缺陷**：
**D1** ★★★ `PipelineSession` 覆盖 `_dispatch_segment()` 且**不调基类**
⇒ 流水线（= 生产路径）**从不**向旁路登记定稿段 ⇒ 实测 `n_final_req=0`/`n_label=0`（段级表 `spk` 全 null）
⇒ 修：补 `self._request_spk_label(abs0, abs1)` ⇒ 复测 `n_final_req=19`（= 段数）、`n_label` 2–8。
**D2** ★★★ `chrome.tabCapture.capture({audio,video,targetTabId})` **API 用错**
（查官方文档：`capture()` 的 options 是 `CaptureOptions`，**无** `targetTabId`；`targetTabId` 属于 `getMediaStreamId()`）
⇒ 实测报错 `No matching signature.` ⇒ **每轮都降级** `getDisplayMedia`（整机声音）⇒ 英译中没测到
⇒ 修：改 `getMediaStreamId({targetTabId})` + `chromeMediaSource:'tab'` 消费
⇒ 修后报错原文**已变**为 `Extension has not been invoked…(see activeTab permission)` ⇒ **API 已被接受**（余下是 Chrome 要求用户激活 ⇒ **环境限制**）。
**D3** ★★ `margin.json` 缺**真实 ASR 墙钟**（`asr_sec` 是纯引擎耗时，**不含**等 GPU 锁 ⇒ 会**低估**旁路影响）
⇒ 修：增落 `pipeline.stage_wall_sec.asr`。
**D4** ★★ 录音分析被 safe-delete 钩子腰斩 ⇒ **`summary.json` 根本没落盘**（两轮白跑）
⇒ 修：profile 名改唯一 + `reuse_profile=True`；`analyze_recordings` 加 try/except ⇒ **保证 summary 一定落盘**。

⇒ **③ ★★ EXT-029 ③ 的判据口径修正（5 轮实测）**：原文「ASR 墙钟与 feed_lag 差异 ≤5%」**被环境噪声主导**
⇒ A 臂 ASR 墙钟**自身**在 **21.9020 ~ 67.8250 s**（**同样配置/同样素材**，**3.1×** 波动），
asr_wall 有符号差异 **[−33.85, −54.74, −10.30, +26.40, +29.48] %**（**符号不一致**）
⇒ **改用机制直接度量**：**ASR 等 GPU 锁的时间**（`stage_wall_sec.asr` − Σ`asr_sec`）。
★ **5 轮实测**：A 臂 max **0.0007 s** / B 臂 max **0.0008 s**（占 ASR 墙钟 **≤0.004 %**）⇒ **旁路没有反压 ASR** ✅。
⇒ feed_lag 改用**每段均值**（总和口径与段数 13–20 的抖动强相关 ⇒ 不可比）。

⇒ **④ 旁路指标（5 轮 B 臂实测）**：`spk_queue_drop` **0–57**（满了丢旧块并计数）、
`spk_worker_busy_ms` **276.6–777.5 ms**（60 s 音频里只忙 ≈0.5 %）、
`spk_gpu_lock_held_ms` **1726.1–6793.3**（额外延迟**上界**，占 ASR 墙钟 **4.5–24.0 %**）、
`n_label` **2–8**、检出 **S1/S2(/S3)**（**多说话人真被区分**）、`enc_ready=true`、`seg_infer_count` 5–6。
⇒ **EXT-029 ④ 已满足**：共用 GPU.0（实测唯一可编译设备）⇒ **报测得的额外延迟**；实测 ASR **实际多等 ≤0.8 ms**（公平 FIFO 生效）。

⇒ **⑤ 机器锁（铁律）**：开工时锁被 **app-pack**（PID 8412）持有
⇒ 用 **ctypes `OpenProcess`+`GetExitCodeProcess`** 探测（**code=259 ⇒ 存活**）⇒ **等，不抢**；
本模块 5 轮**逐轮取放**（`ext <PID> <时刻>`），**未回收任何他人的锁**。

⇒ **⑥ 自测（实测）**：三套明文自测 **rc=0**（**106**/**11**/**19**）；
`test_ext029_spk_bypass.py` **70 PASS / 0 FAIL**（本轮 **+12**，**不改写旧断言**）；
node harness **8 套全 rc=0**；全量 **26 套**。
★ 新增断言覆盖 4 个缺陷：流水线登记标签（含反证）/ 标签回填后 `spk` 非 null / tabCapture API 口径 / margin 含真实墙钟。
★ **本轮自己引入的回归已修**：写 §21 正文把 STATUS 推到 24 143 B ⇒ **撞破 EXT-016 硬约束「< 归档/10 = 22 483 B」**
⇒ 按 EXT-016 规则把 §19/§20 内联正文下沉到 `status/notes/sec19_20_closeout.md`（**数字一字未改**）⇒ 回落到 **21 890 B / 148 行** ✅

⇒ **⑦ 三个红套件归因（`git stash` 基线复核）**：`test_ext016_compression` **基线同样红**（CORRECTIONS 现 34 075 B ⇒ **reviewer 独占，只读**）；
`test_ext017_user_report` / `test_ext026_audio_analysis` **单独跑全绿**（批处理里偶发红：实时字幕 App 在跑 ⇒ 互斥拒绝；safe-delete 钩子拦批量删）⇒ **环境性，非回归**。

⇒ **⑧ ⛔ 明确未做 / 不宣称**：⛔ **音色克隆未接线**（`voice_source` 实测全 `'preset'`、`clone_wired=false`
⇒ 引擎层 `tts()` 的 `voice` 参数没接进 `tts_engine.stream()` ⇒ **不宣称「克隆音色可用」**）；
⛔ **Edge 默认 profile 真实手势验收未做**（**由用户本人做**）；⛔ **tabCapture 生产路径未实测**（自动化拿不到，需用户点扩展图标）；
⛔ **英译中仍未真正测到**（抓流仍是整机声音 ⇒ B 轮 ASR 混进中文内容；A/B「同输入」对比**有效**，但「输入是纯英文」**未达成**）；
⛔ 端到端仍不实时（TTS RTF 1.0022）/ 同步误差仍超标 ⇒ **未动引擎**；
⛔ **未改任何引擎文件**；⛔ `CORRECTIONS_EXT.md` **只读、未修改、未入库**。

> **§16 ~ §10 —— 已下沉**（明细全文在 `status/notes/`；§10 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`）：
> * **§13 ~ §16** 明细全文见 `status/notes/sec13…sec16_*.md`（§16 摘要见上方指针表）。
> * **§12 / §11** 启动器 `start()` **4.244 s → 0.032 s**（EXT-017②）；STATUS 拆分归档（`notes/sec11_12_ext016_closeout.md`）
> * **§10** 控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；
★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`，用户方式实测通过
（6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。
