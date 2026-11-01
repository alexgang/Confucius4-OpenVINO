# STATUS_EXT
last_ack: EXT-032
更新时间: 2026-11-02 01:04
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§25 EXT-032 交卷** —— ★ 上一会话「证据落盘+提交收尾」时**死掉** ⇒ 租约 **TAKEOVER** ⇒ 从断点继续 ⇒ ✅ 已交**逐段三份音频对比**（变速校正时长比 6/6 = 1.000–1.019；互相关峰 1.0000；SNR 中位 120 dB）+ **静音成因分解**（可解释 32.05 s = 首语音 22.05 s + 缓冲 D 10 s，残差 −2.75 s）+ **sync_err p50/p95 = 0/0 ms** + 交付目录 `shared/ext_listen/ext032_20261102_010022/`（5 文件）⇒ ⛔ **撤回「EXT-028 不构成打包阻塞」**（改为**待用户抽听**）⇒ ⛔ tabCapture 生产路径**自动化拿不到**（探针 12 次全败）⇒ 须用户手势；⛔ 未打包（APP-057）/ ⛔ 克隆音色不可用 / ⛔ 端到端仍不实时（TTS RTF 1.0022）

阻塞 / 待决定:
① ⛔ **EXT-032① tabCapture 生产路径 = 只能用户手势** —— 探针 12 次尝试全败（`getMediaStreamId` 空 id / `capture` null stream / `capture({targetTabId})` 属性非法），原文见 `.tmp/probe_tabcapture/result.json`；⇒ 请按 `shared/ext_listen/v21/HOWTO.txt`（App 模块 APP-059 已写 6 步）转用户亲手跑一次 60 s
② ⛔ **EXT-028 待用户抽听 ⇒ V2.0 插件部分暂不放行**（旧结论已在本节撤回）—— 交付物已落 `shared/ext_listen/ext032_20261102_010022/`（player 录音 + README + 对比表），reviewer 可拉回做电平/静音测量与 MiniMax 回转写
③ ⛔ **端到端仍不实时，TTS 提速是上线的唯一前置** —— 稳态端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**，源 `.tmp/ext008_bench/steady.json`）⇒ 建议目标 ≤ 0.85，**由主会话转达 TTS 模块**
④ ⛔ **同步误差**：EXT-032 那一轮（真实浏览器+真实引擎）`sync_err p50/p95 = 0/0 ms`、`n_over_12000ms`=0；但**流水线轮**仍 `sync_err_ms.p50=67289.3` / `last_segment_lag_sec=71.2074`（源 `.tmp/p1_pipe/p1_report.json`）⇒ 两个口径不同，**实时未达成**的结论不变
⑤ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P3（打包）未开始**
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

## §21 ~ §24 —— 已下沉（EXT-016 规则：内联只留最近 3 节；**原文逐字存档在 notes，零丢失**）

| 节 | 明细全文（notes） | 结论摘要 |
|---|---|---|
| §21 | `notes/sec21_ext029_spk_bypass_thread.md` | **EXT-029**：独立线程 + 有界队列 + 异步回填 ⇒ **不反压 ASR**（等 GPU 锁 A max 0.0007 s / B max 0.0008 s，≤0.004 %）；修 4 个真缺陷；`test_ext029` 70 PASS / 0 FAIL |
| §22 | `notes/sec22_23_ext030_lease_ext031_handoff.md` §22.1 | **EXT-030**：模块租约已接入自动化指令（`acquire`/`beat`/`addpid`/`release`）；★ 实测 **BUSY → 等满 TTL → TAKEOVER** ⇒ 租约机制真实生效 |
| §23 | `notes/sec22_23_ext030_lease_ext031_handoff.md` | **EXT-031**：V2.0 交付清单已写（`release/V20_HANDOFF.md`）+ 模拟发行包启动实测 6 PASS / 0 FAIL。⚠️ §23 原结论含「EXT-028 ✅ 已修 ⇒ **不构成打包阻塞**」—— **该结论已由 §25① 撤回**（原文逐字保留在 `notes/sec21_24_inline_archive.md` 以存史） |
| §24 | `notes/sec24_takeover_closeout.md` | **EXT-030/031 落库收口**：上一会话「做完就死」⇒ 闸门 exit 1 只判认领 ⇒ 补记 EXEC_LOG + 提交；复核 6 套全 0 FAIL；报出「闸门不校验收口」「TTL 30 min」两个制度性缺口 |

## §25 —— EXT-032 交卷：三份音频逐段对比 + 静音成因分解 + 交付物落盘（2026-11-02 01:04）

★ **全量明细见 `status/notes/sec25_ext032_deliver.md`**（9 节）；本节只留结论、数字、指针。

⇒ **① ★★ 撤回旧结论**：§23 与「未完成纠偏清单」里那句 **「EXT-028 不构成打包阻塞」不成立** ⇒ 本节**撤回**它，改为 **「EXT-028 待用户抽听」** ⇒ **V2.0 插件部分暂不放行**（reviewer 20:30 的判断正确：EXT-028 当时确实一项验收都没交）。
⇒ **② ★ 指令②「逐段三份音频对比」已交**（6 段，源轮次 `.tmp/ext028_029_e2e/20261101_155037_13840/A_off`）：**变速校正时长比 6/6 合格（1.0000–1.0190）**、**互相关峰 1.0000**、**SNR 中位 120.0 dB**；唯一原始比不合格段（0.8564）= **speed=1.1899 的 WSOLA 变速段**（0.8564 ≈ 1/1.1899）⇒ **与采样率无关**。★ 采样率修复生效的直接证据：`metrics.json` → **`pcmRateLast=24000` / `pcmRateAssumed=0`**（不再按 16 kHz 重建 24 kHz ⇒ 「1.5× 语速 + 升调」根因已消除）。
⇒ **③ ★ 指令③「静音成因」已交**（**加法式分解**，残差可核）：**可解释开口静音 = 首语音位置 22.050 s + 播放缓冲 D 10.000 s = 32.050 s**；**实测开口静音 29.300 s**、**最长静音 29.250 s**、**总静音 30.000 s**（录音总长 **33.840 s**）；**残差 −2.750 s**（≈ player 时钟与桥接 t0 偏移）。**首段配音到达 = t_start 22.050 s**（段 `seg_90879187_352800`，`and you know`→`你知道的`）。**sync_err p50 / p95 = 0.0 / 0.0 ms**（max 0.0，`n_over_12000ms`=0；口径同 `tools/p1_pipeline.py`，**只统计有 TTS 的 3 段**）。
⇒ **④ ★ 为什么 22.05 s 之前没有配音**（三条排除）：(a) **不是素材问题** —— 实测素材 `test_en_60s.wav` **20/20 个 3.15 s 窗都有语音**（RMS −26.65…−36.02 dBFS，首语音窗 t=0.0）；(b) **不是 ASR 问题** —— 同轮 3 窗**正常英译中**（`and you know`/`because I don't decline`/`So just got to maintain the`）；(c) ⇒ **是抓流侧没把标签页音频送上来**（见 ⑤）。
⇒ **⑤ ★★ 指令①「tabCapture 生产路径」** —— **自动化拿不到，必须用户手势**：探针 **12 次尝试全失败**（`getMediaStreamId` 回空 id、`capture` 回 null stream、`capture({targetTabId})` 报 **"Unexpected property: 'targetTabId'"**；player 原文 **"Extension has not been invoked for the current page (see activeTab permission)."**）；该轮 `metrics.json` → **`captureMode = getDisplayMedia`**；**player 截图 `player_60s.png` 里画的是整个桌面**（终端/资源管理器/GPU 面板）⇒ 坐实**抓的是整机 + 系统声音混音**；**末尾 3 段是中文且 t_start 66.52/69.85/73.01 s 已超出素材 60 s** ⇒ 只能来自实时字幕 App 的混音 ⇒ **该轮「只抓页面元素音频 + 英文 SPE」两项均未达成**（EXT-027① 成立且已量化）。⇒ **请按 `shared/ext_listen/v21/HOWTO.txt`（App 模块 APP-059 已写 6 步）转用户亲手跑一次 60 s**；跑完后 `tests/smoke/ext032_deliver.py <该轮目录>` 一条命令即出同规格交付物。
⇒ **⑥ ★ 交付物已落盘**：`C:\Users\Trekker-PTL\shared\ext_listen\ext032_20261102_010022\`（**5 文件**：`dub_player.webm` 86 970 B / `README.md` 4 102 B / `ext032_compare.md` 1 985 B / `ext032_compare.json` 6 266 B / `ext032_deliver.json` 10 772 B）⇒ reviewer 可拉回做电平/静音测量与 MiniMax 回转写，再交用户抽听。
⇒ **⑦ ★ 本轮新增代码**：`tests/smoke/ext032_deliver.py`（成因分解 + 交付打包，**纯离线，不跑推理、不占 GPU/NPU、不创建锁**）、`tests/test_ext032_deliver.py`（**29 PASS / 0 FAIL**，含 4 组反证）；并接手上一会话已写的 `tests/smoke/ext032_audio_compare.py`（24 228 B，算法未改）。**三套明文自测 106 / 11 / 19 全 0 FAIL（rc=0）**。
⇒ **⑧ ⛔ 未做 / 不宣称**：⛔ 本轮**没跑新的真实三引擎 e2e**（00:40–00:48 机器锁被 **asr** 持有；00:48 锁释放后**实时字幕 App 在跑** ⇒ `ext.bridge` 按互斥铁律拒绝启动 ⇒ **不抢设备、不打断用户的 App**）；⛔ **player 录音逐段对齐只 3/6** ⇒ 不宣称播放端完全对齐；⛔ **未打包**（APP-057）/ **未改引擎** / **未推远程** / `CORRECTIONS_EXT.md` **只读未入库**。

> **§16 ~ §10 —— 已下沉**（明细全文在 `status/notes/`；§10 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`）：
> * **§13 ~ §16** 见 `notes/sec13…sec16_*.md`；**§12 / §11** 启动器 `start()` **4.244 s → 0.032 s**（EXT-017②）、STATUS 拆分归档（`notes/sec11_12_ext016_closeout.md`）
> * **§10** 控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`（用户方式实测通过，6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。

