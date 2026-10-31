# STATUS_EXT
last_ack: EXT-026
更新时间: 2026-11-01 00:55
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§20 §19 收口**（闸门 **exit 1**，**未认领新编号** ⇒ `last_ack` 仍 = **EXT-026**）⇒ ✅ **T-5 内存不持续增长**：修掉 **3 类无界增长**（服务端 `_frame_arrival_delays` 每帧追加永不裁剪 / `_seg_orig_end`+`_seg_ready` 只写不读 / 插件 `gapDetail` 只追加永不裁剪）⇒ **统计口径一字不变**（均值累加 round 后的值 ⇒ 逐位等价）⇒ ✅ **T-6 设置持久化**：8 个控件 change/input 即时落盘（400 ms 防抖）+ 归一 + 幂等 ⇒ ✅ 新增自测 2 个（node 16 / Python 40）⇒ ✅ **24 套 / 1 104 PASS / 1 FAIL**（唯一 FAIL = 既有 `test_ext016_compression`；**② 已在本轮修**，见 §20）⇒ node harness **7 套全 rc=0** ⇒ ⚠️ `last_ack` = **EXT-026**（不变）⇒ ⛔ **Edge 真实手势验收仍需用户本人做**；⛔ 「30 分钟不崩」未做（需真实引擎）/ 克隆音色未接线（依赖 ASR-013）/ 暂停拖动未做（需 reviewer 口径）/ 端到端仍不实时（TTS RTF 1.0022）/ 同步误差仍超标（既有阻塞项，未动引擎）

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
| 自测套件 | **24 套 / 1 104 PASS / 1 FAIL**（唯一 FAIL = 既有 `test_ext016_compression`：① CORRECTIONS 21 943 B（reviewer 独占，只读不改）② 精简版 STATUS 超 EXT-016 限额 —— **② 本轮已修**，见 §20）+ node harness **7 套全 rc=0** | §19/§20 本轮实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
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
> | §20 | 本文件内联（§19 收口） | 补 EXEC_LOG + 提交 + **STATUS 压缩回 EXT-016 限额内** |### §18 EXT-026 收口 —— 真实三引擎端到端自动化冒烟 + 证据落盘 + `seenDubIds` 撞号修复（2026-10-31 21:23）

**依据**：闸门 **exit 0**（latest=**EXT-026** / last_ack=25）⇒ **认领 EXT-026** ⇒ `last_ack` = **EXT-026**。
★ **明细全文见 `status/notes/sec18_ext026_real_e2e.md`**（7 节，12 520 B）——本节按 EXT-016 常设规则**只留结论**（★ 数字**一字未改**）。

⇒ **① 两轮各 60 s**：A 轮 `.tmp/ext026_e2e/`（兜底路径）+ B 轮 `.tmp/ext026_prodpath/`（**生产路径**）。
自动化下**必然拿不到 tabCapture**（实测原文 `Extension has not been invoked for the current page
(see activeTab permission). Chrome pages cannot be captured.`）⇒ 降级 `getDisplayMedia`，两轮**如实上报、未谎报**。

⇒ **② 实测**（原始字段，详见 notes）：段级日志 **9 / 9**、有 TTS 段 **7**（A）/ **5**（B）、10048 **0**、
「不顶替」 **2**、TTS 语音 **43.84 s**（A）/ **27.84 s**（B）、
`hello_ack` = `mode=real / engines_ready=true / pipeline=true`、`dubDelivered/echoRecv/dubDup` = **9/9/9**、
`lagSec` **12.7046 / 16.4806**、段 id `seg_55035942_194400` / `seg_77393782_194400`。
⇒ **③ 录音实测非静音**（新工具 `tests/smoke/analyze_dub_audio.py`，headless Edge WebAudio **纯解码**，不跑推理）：
A 轮 **585 326 B / 76.2 s / RMS 0.063978（−23.88 dBFS）/ 32 burst / 语音 26.74 s（35.09 %）**；
B 轮 **409 669 B / 115.02 s / RMS 0.048422（−26.30 dBFS）/ 28 burst / 语音 18.08 s（15.72 %）**
⇒ 两轮 `non_silent=true`（分析落盘 488 B / 497 B）。

⇒ **④ EXT-023 收口**：落盘 `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`（4 260 B，20:54:13）
⇒ **`on_npu=17` / `on_cpu=[]` / `on_unknown=[]`**，`cp_decode`=NPU，`talker`/`cp_prefill`/`decoder` 全 NPU
⇒ **无任何组件落在 CPU**。

⇒ **⑤ `seenDubIds` 跨会话撞号已修**（EXT-026 第 5 条）：原 `seg_{s0}` 每会话从 0 开始 ⇒ 与页面级常驻的
`seenDubIds` 撞号 ⇒ 新会话的段被**静默丢弃**。修法：`ext/bridge.py` 加 `public_seg_id()`
⇒ 段 id = `seg_{8位纯数字会话前缀}_{数字}`（★ 前缀必须**纯数字**，否则
`tools/compare_ext011_cores.py` 的 `int(id.split("_")[-1])` 会 ValueError）；内部键仍用裸 `seg_id`；
`hello_ack` 新增向后兼容字段 `session_id`。

⇒ **⑥ 修掉的 5 个真缺陷**（**只有生产路径才会暴露**）：**P1** `pollStats()` 只认 `upState.ws`
⇒ **状态条段数恒为 0** ⇒ 回落用 player 自己那条 WS；**P2** `sw.js`/`offscreen.js` **都没 flush**
⇒ **点「停止」时最后一句永远丢** ⇒ `offscreen.flushUplink()` + `sw.case 'flush'` + popup「停止并收尾」
（**先 flush，12 s 后自动 stop**）；**P3** popup 配置**只写 storage 不够** ⇒ 须**同时**写 storage 与 DOM；
**P4** `pairUrl()` 从 ws 端口 **+1** 推配对端口 ⇒ 改用 `_free_port_pair()` 取**连续两个**空闲端口；
**P5** `pollStats` 有**两处** `send` ⇒ 旧反证只改坏一处失效 ⇒ C4 反证改为**同时**改坏两处。
★ 逐条根因/修法/反证全文见 notes §4。

⇒ **⑦ 产物**（**实测**）：A 轮证据 **8 个 / 665 745 B**；B 轮证据 **7 个 / 469 835 B**；
产品代码改动 **9 个 / 344 468 B**（+543 −143 行）；新增自测 + 冒烟脚本 **10 个 / 150 109 B**；
notes 明细 **1 个 / 12 520 B**。

⇒ **⑧ 未做 / 不宣称**：⛔ **Edge 默认 profile 真实手势验收未做**（EXT-022 已定② ⇒ **由用户本人做**）
⇒ **可以请用户在 Edge 默认 profile 手势验收**；⛔ **不宣称「用户已听到配音」**（录音非静音已实测，真人听感仍待用户验收）；
⛔ **不宣称「tabCapture 生产抓流已在真机验证」**；⛔ 端到端仍不实时（TTS 稳态 RTF **1.0022** > 1.0）、同步误差仍超标、
克隆音色仍未接线 ⇒ **既有阻塞项，未动引擎**；⛔ **未改任何引擎文件**；⛔ `CORRECTIONS_EXT.md` **只读、未修改、未入库**。

### §19 T-5 / T-6 —— 内存不持续增长（无界列表有界化） + 设置持久化（2026-10-31 23:21）

**依据**：闸门 **exit 1**（latest=**EXT-026** / last_ack=26 / `already_executed`）⇒ **没有更新的纠偏条目**
⇒ **未认领新编号** ⇒ **`last_ack` 保持 EXT-026**。★ 按 **EXT-014 ②**（「`last_ack` 追平后，只要还有未完成项，
就自己继续做，不要空转」）⇒ 继续「未完成纠偏清单」里的 **P2 待办**（`设置持久化 / 30 分钟不崩·内存不持续增长`）；
克隆音色（依赖 ASR-013 交付）、暂停拖动（需真实手势 + reviewer 口径）本轮**不做**。
★ **明细全文见 `status/notes/sec19_t5_t6_bounds_persist.md`**（6 节，13 267 B）——本节按 EXT-016 常设规则**只留结论**。

⇒ **① 3 类真缺陷（无界增长）**（★ 逐条根因/修法见 notes §19.2）：
**T5-a** 服务端 `_frame_arrival_delays` 每帧追加永不裁剪（≈47 帧/秒 ⇒ **30 分钟 ≈ 8.5 万条/会话**）
⇒ 保留最近 **`C.FRAME_DELAY_HISTORY = 2000`** 条；**统计口径不变**（`n_frames_measured`/`late_ratio`/`mean`/`max`
改由**累计量**承担，⚠️ 均值累加 `round(delay,4)` ⇒ 与旧实现**逐位等价**），新增 `history_window`/`history_kept`。
**T5-b** `_seg_orig_end`/`_seg_ready` **只写不读**（全仓 grep 零读取点）⇒ 保留最近 **`C.SEG_TIMING_HISTORY = 50`** 段
（无读取点 ⇒ **不影响任何统计口径**；加 `threading.Lock` 防并发改 dict）。
**T5-c** 插件 `player.js`+`offscreen.js` 的 `gapDetail` 只追加永不裁剪 ⇒ 两侧各加 **`GAP_DETAIL_CAP = 200`**，
超出丢最旧的并**如实计数**（`gapDetailDropped`），上报口径 `slice(-20)` **不变**。
⚠️ **刻意没改** `margins`/`engine_calls`（reviewer 的**验收记录本体** ⇒ 裁剪会让验收数字失真）。

⇒ **② T-6 设置持久化**：`saveCfg()` **只在点「开始」时被调用** ⇒ 用户改了设置后**直接关掉弹窗** ⇒ 改动**全丢**
⇒ 新增 `readCfg()`/`persistCfgNow()`/`schedulePersistCfg()`（400 ms 防抖）/`bindPersistListeners()`
（**8 个控件**全挂 `change`，文本框与数字框额外挂 `input`）；`saveCfg()` **改为复用 `readCfg()`** ⇒ 两条写盘路径
口径**必然一致**；落盘前**归一**；绑定**幂等**；调用点在 `loadCfg()` **之后**。

⇒ **③ 自测**：新增 `t5_t6_bounds_persist_harness.js`（**16**）+ `test_t5_t6_bounds_persist.py`（**40**）
⇒ **24 套 / 1 104 PASS / 1 FAIL**（§18 为 23 套 / 1 064 / 1 ⇒ **+1 套 / +40 PASS，零回归**）；
node harness **7 套全 rc=0**；三套明文自测单独确认 rc=0（**103**/**11**/**19**）。

⇒ **④ ★反证**（区分真通过/假通过，详见 notes §19.4）：短路 `player.js` 裁剪 / 改坏 `popup.js` 绑定
⇒ harness **rc=1**；删掉 `bridge.py` 裁剪两行 ⇒ Python **rc=1（3 条断言红）**；短路
`_trim_seg_timing_history` ⇒ **rc=1**。★ 另修**两个测试自身的坑**：①「口径对照」首跑红 2 条
⇒ 根因**墙钟噪声**（两个 session 的 `t0` 不同）⇒ 改为**显式对齐 `t0` + 同一组 `recv_at`**
⇒ 并借此发现并修正一个**真口径差异**（round 前 vs round 后求和）；② `popup.js` 是 **CRLF**
⇒ 反证正则写死 `\n` 匹配不到 ⇒ 全改 `\r?\n`。

⇒ **⑤ FAIL 归因**：`test_ext016_compression` ⇒ **基线复核**（`git stash` 后重跑）⇒ **同样 37 PASS / 2 FAIL**
⇒ **既有状态、非本轮引入**；其中「CORRECTIONS 明显变小」⇒ reviewer 独占文件 ⇒ **只读、不 `git add -f`**；
「精简版 STATUS 不含历史全文」⇒ **本轮已修**（见 §20）。

⇒ **⑥ 产物**：产品代码改动 **5 个**（+215 −12 行）；新增自测 **2 个**；notes 明细 **1 个**。

⇒ ⛔ **未做 / 不宣称**：⛔ **未认领新 EXT 编号**；⛔ **克隆音色仍不可用**（依赖 ASR-013 交付）；
⛔ **「30 分钟不崩」未做**（需真实引擎 + 独占设备）⇒ **不宣称「30 分钟不崩已验证」**；
⛔ **「暂停拖动」未做**（需真实手势 + reviewer 口径）；⛔ 端到端仍不实时（TTS RTF 1.0022）/ 同步误差仍超标；
⛔ **未改任何引擎文件**；⛔ **未跑真实推理、未占 GPU/NPU、未创建/未回收机器锁**（开工时锁不存在）；
⛔ `CORRECTIONS_EXT.md` **只读、未修改、未入库**。

### §20 §19 收口 —— 补 EXEC_LOG + 提交 + **STATUS 压缩回限额内**（2026-11-01 00:5x）

**依据**：闸门 **exit 1**（latest=**EXT-026** / last_ack=26）⇒ **无新编号** ⇒ 继续 §19 的**收口**（上一轮被中断：
代码与 notes 已写好，但 **EXEC_LOG 未追加、未提交**）。

⇒ **① 补完 §19 的收口动作**：追加 `status/EXEC_LOG.md` 本轮记录 + 在本仓库提交
（只加本模块文件；`status/CORRECTIONS_EXT.md` 在 `.gitignore` ⇒ **未 `git add -f`**）。

⇒ **② ★发现并修掉一个本轮引入的回归**：§19 的正文写入把精简版 STATUS 从 **22 559 B** 推到 **29 652 B**
⇒ 撞破 EXT-016 的硬约束「< 归档/10 = 22 483 B」⇒ `test_ext016_compression` 的
「精简版 STATUS 不含历史全文」断言**由 PASS 转 FAIL**（⇒ **不能只报「既有 FAIL」就放过**）。
★ 修法（**按 EXT-016 规则裁剪，不是删内容**）：§17 / §18 / §19 的内联明细**下沉到 `status/notes/`**
（三份 notes 已在库、已含全部实测数字与反证）⇒ STATUS 只留「依据 + 关键数字 + 结论 + 指针」。
⚠️ **不回头改旧章节的结论**；§17/§18/§19 的**数字一字未改**（只是搬到 notes）。

⇒ **③ 自测**：三套明文自测 **rc=0**（**103**/**11**/**19**）；全量 **24 套**；
node harness **7 套全 rc=0**；`test_t5_t6_bounds_persist.py` **40 PASS / 0 FAIL**。

> **§16 ~ §10 —— 已下沉**（明细全文在 `status/notes/`；§10 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`）：
> * **§13 ~ §16** 明细全文见 `status/notes/sec13…sec16_*.md`（§16 摘要见上方指针表）。
> * **§12 / §11** 启动器 `start()` **4.244 s → 0.032 s**（EXT-017②）；STATUS 拆分归档（`notes/sec11_12_ext016_closeout.md`）
> * **§10** 控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；
★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`，用户方式实测通过
（6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。
