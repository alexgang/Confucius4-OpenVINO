# STATUS_EXT
last_ack: EXT-025
更新时间: 2026-10-31 15:57
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B）；逐条明细见 `status/notes/`
当前任务: **§17 EXT-024 收口**（EXT-025 RESUME 指向的主任务）⇒ ✅ **A–G 七项全部落地**（下行按 token 广播 + 插件两条 WS 都挂 onmessage + 按 id 去重；会话生命周期；启动器不加载模型即拒；段级日志含「下发到」；状态条 6 计数 + 红字写明原因；popup 回声红底 + 未就绪禁用「开始」；`Chinese`→`zh`）⇒ ✅ **时间轴口径明文落盘**（`t_start_axis="uplink_sample_index"`）⇒ ✅ **EXT-023** 执行设备如实上报 + 落盘 ⇒ ✅ **EXT-022** 编号改 T-1…T-4 + 流水线默认开 + 冒烟脚本入库 ⇒ ✅ **19 套 / 990 PASS / 0 FAIL** ⇒ ⚠️ 认领 EXT-024 + EXT-025 ⇒ `last_ack` = **EXT-025** ⇒ ⛔ **Edge 真实手势 1 分钟验收未做**（EXT-022 已定② ⇒ 由用户本人做）⇒ ⛔ **未在真实三引擎上验证**（未占 GPU/NPU，锁属 TTS 模块）⇒ ⛔ **不宣称**「用户已听到配音」「cp_decode 已确认全在 NPU」

阻塞 / 待决定:
① ⛔ **Edge 真实手势 1 分钟验收（EXT-024 验收 1–4 条）** —— 需**用户本人**在 Edge 默认 profile 手动：双击桌面「实时配音桥接.cmd」→ 等就绪 → 打开英文网页视频 → 点扩展「开始」→ player 点「开始捕获」→ 连播 1 分钟；截图（30 s / 60 s 各一张）+ 确认 bridge.log 本次段级日志 ≥5 段且「下发到 player」段数 = TTS 段数、无「不顶替」无 10048
② ⛔ **端到端仍不实时，TTS 提速是上线的唯一前置** —— 稳态端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**，源 `.tmp/ext008_bench/steady.json`）⇒ 建议目标 ≤ 0.85，**由主会话转达 TTS 模块**
③ ⛔ **同步误差仍全部超标** —— 流水线轮 `sync_err_ms.p50=67289.3` / `n_over_target=22` / `last_segment_lag_sec=71.2074`（源 `.tmp/p1_pipe/p1_report.json`）⇒ 实时未达成
④ ⛔ **EXT-023 待真实值** —— 上报与落盘机制已就绪，但**真实 cp_decode 落点要等下次真实启动**后从 `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json` 读（⇒ 不臆造「已确认全在 NPU」）
⑤ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P2（克隆/体验/稳定性）/ P3（打包）未开始**
⑥ ℹ️ **tabCapture 生产路径仍未实测**（EXT-005 ①，需真实用户手势）；⛔ **浏览器端人工验收未做**（EXT-022 已定② ⇒ 由用户本人做）
⑦ ℹ️ **EXT-009 服务端 lag 估计存在跨时钟常量偏差，尚未定量标定**（§17 已写清 t_start 时间轴口径与该偏差的关系；决策在服务端，不影响变速稳定性）；ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准，旧章节不回头改）

## 当前有效结论

| 项 | 值 | 来源文件 |
|---|---|---|
| 交付配置 | ASR=R2T2 INT8@GPU.0 / MT=Hy-MT2 INT8@GPU.0 / TTS=Qwen3-TTS@NPU | §10.4 启动日志 |
| 端到端稳态 RTF | **2.0507**（ASR 0.6563 / MT 0.1507 / TTS 1.0022） | `.tmp/ext008_bench/steady.json` → `steady_state_excl_first_segment` |
| TTS 稳态 RTF（独立实测，去首段 18 段/286.32 s） | **1.0022**（无余量，>1.0） | `.tmp/ext008_bench/steady.json` |
| 并行化收益上限 | `parallel_speedup_x=1.3613`（asr_slowdown 0.9498 / tts_slowdown 0.9838） | `.tmp/ext008_bench/interference.json` |
| 串行（EXT-009 前）末句滞后 | 227.9863 s，斜率 −0.565947 | `.tmp/p1_ext009/p1_report.json` |
| 流水线末句滞后 | **71.2074 s（↓68.8 %）**，斜率 −0.106051（↓81.3 %） | `.tmp/p1_pipe/p1_report.json` |
| 流水线喂帧 | `feed_speed_x` 0.5949 → **1.0**；`send_dur_max_sec` 58.453 → **0.007** | `.tmp/p1_pipe/p1_report.json` → `timing` |
| 流水线健康度 | `n_submitted=22 / n_emitted=22 / n_error=0 / n_pending=0` | `.tmp/p1_pipe/p1_report.json` → `bridge_stats.pipeline` |
| 流水线瓶颈 | `stage_wall_sec` = asr 234.912 / mt 2.397 / **tts 343.64** | `.tmp/p1_pipe/p1_report.json` |
| 自适应加速封顶 | `speed_time_share` >1.30× 占 **0.0**；1.20–1.30× 占 0.9144；`n_dropped_dub=0` | `.tmp/p1_pipe/p1_report.json` → `bridge_stats.adaptive_speed` |
| 线程限制 A/B | 核数 mean 0.8244 vs 1.2909（↓36.2 %）/ peak 2.819 vs 7.091（↓60.2 %）；TTS RTF 1.0542 vs 1.3249（↓20.4 %） | `.tmp/p1_ext013_lim/compare_ext011.json` |
| 余量口径 | 顶层 `basis="deadline"`（排程口径）；`n_negative=22`；`cumulative_lag_sec` 已被 EXT-008 有意删除 | `.tmp/p1_pipe/p1_report.json` → `metrics.margin` |
| 扩展 ID | `kekgmfkijphpfndbbpakjaokamkeooib`（由 manifest `key` 现场算，与 9 份探针一致） | `ext/extension_id.py` |
| `/pair` Origin 收紧 | 本插件 **200** / 别的扩展 **403** / 普通网页 **403** / 无 Origin **403** | §10.3 实测 |
| 控制台代码页 | 本机 `ConsoleOutputCP=gb2312` ⇒ GBK 编不了 `⇒`/`🔴`/`⛔` ⇒ 旧 `_log` 抛 `UnicodeEncodeError` | §10.1.1 实测 |
| 引擎加载耗时 | 17.9–26.9 s（预热阶段逐引擎 emit 进度） | §10.4 启动日志 |
| 用户方式验收 | 6 张截图 / 321 900 B 落 `C:\Users\Trekker-PTL\shared\ext_launcher_fix\` | §10.4 |
| 启动器 `start()` 反馈延迟 | **0.032 s**（修前 4.244 s）⇒ 满足 EXT-017②「2 秒内」 | §12 实测 |
| **重复启动失败耗时** | **400 ms 退出码 6**（修前：预热 24 s 后整屏 traceback） | §14 实测 |
| 桥接冷启动（回声模式，不含引擎） | **5.0–5.7 s**（10/10 实测，min 4.948 / max 5.581 / 均值 5.324） | §12 实测 |
| 自测套件 | **19 套 / 990 PASS / 0 FAIL**（全 rc=0；含反证：破坏归档 ⇒ 2 条断言红 rc=1） | §17 本轮实测 |
| 面板目标语言**实际生效** | `applied_target_lang`（= MT `tgt` / TTS `language` 真正用的码）可与 `client_target_lang`（面板选的）比对 | §16 实测 |
| 抓流方式（capture_mode） | 由**客户端实际上报**（hello / capture_info）；未上报 = `null`（**绝不臆造**） | `ext/bridge.py` → `stats()` / `margin.json` |
| 扩展图标 | 16/32/48/128 四个真实 PNG（116/152/180/443 B）；**manifest.key 未动 ⇒ 扩展 ID 不变** | `extension/icons/` + `tools/make_icons.py` |
| **下行路由（EXT-024 根因）** | 服务端按 **token 广播** `tts`/`echo`（产生它的连接 + 同 token 的 player 连接）；插件两条 WS **都**挂 `onmessage`；按 `id` 去重 | `ext/bridge.py` → `ConnectionRegistry.downlink_targets` + `extension/player.js` → `handleBridgeMessage` |
| **已下发到 player 段数** | `metrics.link.dubDelivered`（= player 端**实际收到**的 tts 消息数）⇒ **只有它 > 0 才说明下行通了** | `extension/player.js` → `diagnoseLink()` |
| **链路卡住原因（15 s 阈值）** | WS 未连 / 回声模式 / 引擎未就绪 / 没有音频轨 / 没出段 / **下行路由断了** —— 红字**如实**写明 | `extension/player.js` → `diagnoseLink()`（纯函数，可 node 沙箱验证） |
| **连接模式（真实/回声）** | `hello_ack.mode` = `'real'`/`'echo'`（**只增不改**旧字段）；`engines_ready` **诚实**（绝不因 real 就报 True） | `ext/bridge.py` → `_engines_ready()` / `hello_ack` |
| **t_start 时间轴口径** | **上行采样时间轴**（`s0/16000`，采样点 0 = 上行首帧）；插件按 `t0_player + t_start + D` 排程 ⇒ 与原声**同轴**；随 tts 消息 + `margin.json` 落盘 `t_start_axis` | §17 实测（`t_start_axis='uplink_sample_index'`） |
| **语言全称映射（EXT-024 G）** | 服务端独立认全称：`Chinese`→`zh` / `English`→`en` / `Japanese`→`ja` / `Korean`→`ko`；**未知值 ⇒ None（绝不臆造）** | `ext/config.py` → `normalize_lang_code()` |
| **TTS 组件执行设备（EXT-023）** | 四组件 EXECUTION_DEVICES **如实上报 + 落盘**（`devices`/`actual`/`on_npu`/`on_cpu`/`unknown`）；**未加载 = None**；真实值待下次真实启动 | `ext/engine_runtime.py` → `_report_tts_exec_devices()` → `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json` |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-024** | 下行接通 / 会话生命周期 / 启动器 / 段级日志 / 状态条 / 模式显示 / 语言映射 | ✅ **代码侧 A–G 全部落地**（见 §17）；⛔ **Edge 真实手势 1 分钟验收未做**（EXT-022 已定② ⇒ **由用户本人做**） |
| **EXT-025** | RESUME：额度已重置，从 last_ack 继续 | ✅ **已认领并执行**（`last_ack` = EXT-025） |
| **EXT-023** | TTS 启动日志打印各组件 EXECUTION_DEVICES | ✅ **上报 + 落盘机制已就绪**（`tts_exec_devices.json`）；⛔ **真实 cp_decode 落点待下次真实启动**后读文件（不臆造「全在 NPU」） |
| **EXT-022** | 编号规则 / 待命规则 / 流水线默认开 / 冒烟脚本入库 | ✅ **全部落地**（编号改 T-1…T-4；`--pipeline` 默认 True；`tests/smoke/` 已入库，4 脚本实测 rc=0） |
| EXT-016 | 压缩 STATUS 与 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB） | ✅ **已收口**（见 §11/§12）；★ 本轮再次压缩（§17） |
| EXT-017 ④余项 | 浏览器端人工验收（tabCapture 需真实用户手势） | 需**用户本人**操作（EXT-022 已定②）；本机只有 Edge |
| EXT-017 ② | start 后 2 秒内可见输出 | ✅ **已修好并补行为级验收**（0.032 s，见 §12） |
| EXT-015 | 机器锁让给 TTS-033：本轮不要再拿锁 | 已过该窗口；TTS-033 已由 TTS 模块处理 |
| EXT-005 ① | tabCapture 生产路径实测 | ⏳ **代码侧已就绪**（`capture_mode` 会进 stats / margin.json ⇒ 可从数据核对）；**仍需用户点一次扩展图标**（见 §13） |
| EXT-014 ② | 巡检规则：last_ack 追平后仍要继续下一项 | ✅ 已落地为常设规则 |
| EXT-011/012/013 | 线程限制重测 / 用户试用件 / 对照表 | ✅ 已收口（**§9 全文见 archive/STATUS_EXT_upto_20261030.md**） |
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ✅ **ducking + 字幕已修好**（§15）；✅ **目标语言已真正生效**（§16，`applied_target_lang` 可核对）；⛔ **克隆音色仍不可用**（pyannote 旁路未接线）；⛔ 设置持久化 / 暂停拖动 / 30 分钟不崩未开始（需真实浏览器 + 真实引擎） |
| T-4 余项 | 真实三引擎上端到端验证语言切换 | ⛔ 未做（未占 GPU/NPU，锁属 TTS 模块）⇒ 待主会话在锁空闲时安排 |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；
> §9 及更早的章节全文在 **`status/archive/STATUS_EXT_upto_20261030.md`**（224 833 B）。
>
> | 章节 | 明细全文 | 结论摘要 |
> |---|---|---|
> | §13 | `status/notes/sec13_t1_capture_mode_and_icons.md` | `captureMode` 进 stats/margin.json（未上报=`null`）；扩展图标 16/32/48/128（manifest.key 未动 ⇒ 扩展 ID 不变） |
> | §14 | `status/notes/sec14_t2_port_guard.md` | 重复启动：预热 24 s + 整屏 traceback ⇒ **400 ms 退出码 6 + 人话提示**；端口探测**前置到 warmup 之前**（不加载模型） |
> | §15 | `status/notes/sec15_t3_dead_controls.md` | 面板 4 个死控件已修（原声 dB / 字幕开关 / 目标语言 / 音色）⇒ `client_target_lang`/`client_voice` 进 stats；`dbToGain` 走真实 `setupOriginalAudio` 建图 |
> | §16 | `status/notes/sec16_t4_target_lang_effect.md` | 目标语言「只传不生效」已修（`mt()/tts()` 支持按调用覆盖 + 会话统一口径）⇒ `applied_target_lang` 可核对；老引擎回落旧行为并**如实**记 None |
> | §17 | `status/notes/sec17_ext024_closeout.md` | EXT-024 A–G + EXT-023 + EXT-022 全量明细（含根因、实测、反证、产物表） |

### §17 EXT-024 收口 —— 下行接通 / 生命周期 / 启动器 / 段级日志 / 状态条 / 模式 / 语言 + EXT-023（2026-10-31 15:57）

**依据**：闸门 → **exit 0**（`action=execute`，latest=**EXT-025** / last_ack=17 / n_entries=9）⇒ **有未执行的新指令**。
⚠️ **认领 EXT-024 + EXT-025 两个编号** ⇒ `last_ack` 推进到 **EXT-025**。
★ **明细全文见 `status/notes/sec17_ext024_closeout.md`**（12 节：根因 / 逐项修法 / 时间轴口径 / 实测 / 反证 / 冒烟 / 未做项 / 产物表）——本节**只留结论**。

⇒ **① 根因**：`player.js` 开了**两条** WS —— `connectBridge(...,'player')` **有** onmessage 但**不上行**（会话永不产段）、
`startUplink()` 的 `upState.ws` **只发 pcm 没有** onmessage ⇒ 服务端把 tts 发到上行连接 ⇒ **被浏览器丢弃**
⇒ **配音与字幕全丢**、只剩 DelayNode 延迟的原声 ⇒ 与用户 10-31 实测描述**完全一致**。

⇒ **② A 修下行**：**服务端按 token 广播**（reviewer 给的两个选项之一）—— 新增 `ConnectionRegistry` +
`classify_role()`（⚠️ 未报角色的连接**不当** player）+ `downlink_targets()` + `_broadcast_task()`；
插件两条 WS **都**挂 onmessage（共用 `handleBridgeMessage`）+ **按 `id` 去重**（`seenDubIds`，容量 500）；
offscreen 经 SW 转发给 player（旧实现只计数不转发 ⇒ offscreen 路径下 player **永远收不到** tts）。

⇒ **③ 时间轴口径**（reviewer 明文「要写清楚 t_start 用的是哪个时间轴」）：`t_start` = **上行采样时间轴**
（`s0/16000`，采样点 0 = 上行收到的第一帧音频；与墙钟、与服务端 t0 都无关）；插件按 **`t0_player + t_start + D`** 排程
⇒ 与原声**同轴**（两者来自同一路抓流，天然对齐）。⚠️ 已知偏差：插件 `t0_player` 与服务端 `t0` **不同源**（§6.4.1）
⇒ 该**常量偏差**会平移服务端的 `lag_est_sec`；但**排程本身**用同一个 `t0_player` ⇒ 偏差两边抵消，**不影响配音与原声的相对关系**。
⇒ **落盘**：tts 消息 + `margin.json` 都带 `t_start_axis="uplink_sample_index"`（实测值已验证）。

⇒ **④ B 会话生命周期**：连接关闭 ⇒ **清 holder** + 归档 `holder['last_session']` + 停掉流水线线程
（旧实现**从不清** holder ⇒ 用户日志里每条新连接都打「不顶替」⇒ stats 读到的全是旧会话）；
新 uplink **接管**旧 uplink（按 role 区分，player/探针**不顶替**）；
`_producer_session()` 让 stats/`margin.json` 读**真正产出段**的会话（否则段数恒为 0）；
`_propagate_client_settings()` 让面板设置在同 token 的会话间**双向同步**（否则 uplink 的语言是 None ⇒ 面板不生效）。

⇒ **⑤ C 启动器**：**无条件**先查 PID 文件里的活实例（ctypes，探测失败视为存活）⇒ 直接拒并提示
**「已有桥接服务在运行（PID x，端口 y）」**，**不加载模型、不动日志**；PID 无活实例但端口被占 ⇒ 判定为
**别的程序**占用 ⇒ **在起子进程之前**退出（用户不再白等 20–40 s）；日志每行加 `[#实例号 pid=]` 前缀防交错。

⇒ **⑥ D 段级日志**：每段一行 `段 <id> | t_start | t_end | ASR | MT | TTS秒 | 下发到=<角色>`
（⚠️ 字段缺失写 `—`，绝不编）—— ★ **「下发到」就是 EXT-024 的关键证据**。

⇒ **⑦ E 状态条**：常驻 6 计数 + 滞后；**任一环 15 s 为 0 ⇒ 红字写明具体原因**（WS 未连 / 回声 / 引擎未就绪 /
没有音频轨 / 没出段 / **下行路由断了**）；判定是**纯函数** `diagnoseLink()` ⇒ 可 node 沙箱验证。
★ `已下发到 player 段数`（`dubDelivered`）是**下行通了**的唯一硬证据。

⇒ **⑧ F popup**：`hello_ack` 新增 `mode`/`engines_ready`/`pipeline`（**只增不改**旧字段 ⇒ 向后兼容）；
回声**醒目红底**；`startGate()` 在**桥接没起来/回声/引擎未就绪**时**禁用「开始」并写明原因**；
⚠️ `engines_ready` **诚实**（绝不因 `mode=='real'` 就报 True ⇒ 查引擎 `stats()['loaded']` 三项）。

⇒ **⑨ G 语言映射**：服务端**独立**认全称（`ext/config.py` → `normalize_lang_code()`）⇒ 存量
`targetLang="Chinese"` ⇒ **`zh`**（旧实现落到 None ⇒ 按启动参数默认 en 翻译 ⇒ **用户看到「没翻译成中文」**）；
⚠️ 未知字符串 ⇒ **None**（**绝不臆造**）。

⇒ **⑩ EXT-023（TTS 执行设备）**：本模块走 App 的 `tts_engine.make_engine()`（**不是裸 build()**）
⇒ App 侧已调 `_move_cp_decode_to_npu()` 并挂好 `eng.exec_devices` ⇒ 本模块**只读不重复探测**（重复探测会再抢 NPU）；
打印 `key4_line` + 逐组件落点 + **落盘** `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`
（`devices`/`actual`/`on_npu`/`on_cpu`/`unknown`）⇒ ⚠️ **未加载 = None**、探测不到 = `ok=False`（**照样落盘**，让 reviewer 看到「没测到」）。

⇒ **⑪ EXT-022**：编号规则（自发工作改 **T-1…T-4**，代码注释 + notes 文件名 + 本 STATUS 同步）；
流水线 `--pipeline` **默认开启**（另给 `--no-pipeline` 逃生口，`bridge_server.py`/`run_p1_real.py` 显式传参）；
浏览器端人工验收**由用户亲自做**（本模块不再用 Playwright 替代）⇒ 冒烟脚本 `pw_accept1-4` 迁入 **`tests/smoke/`**
（路径全由 `__file__` 推导 ⇒ 可复现）并**入库** ⇒ 本轮实测 **4 个脚本全 rc=0**。

⇒ **⑫ 自测**：新增 `tests/test_ext023_tts_exec_devices.py`（**23 项**，五组，含**反证**：cp_decode 在 CPU ⇒ 如实报警；
引擎无 `exec_devices` ⇒ `ok=False`；未加载 ⇒ None）；`tests/test_ext024_dl_routing.py` 增至 **55 项**（+4，含真起回声桥接的两条 WS 断言）；
`tests/test_p1_plumbing.py` 增至 **99 项**（+2）；`tests/test_t3_dead_controls.py` **53 项**；
`tests/test_t4_target_lang_effect.py` **52 项**（+1）。
⇒ **19 套 / 990 PASS / 0 FAIL**（全 rc=0，逐套实测真实退出码）；三套明文要求的自测单独确认 rc=0；
闸门仍能解析（`entries=9` / latest=EXT-025 / last_ack=17 / exit=0）⇒ 没弄坏闸门。

★ **反证（证明断言不是恒真）**：把 `ext/bridge.py` 的 `session_holder["last_session"] = session` 改成 `pass`
（模拟 EXT-024 B 被改坏）⇒ **2 条断言全红 rc=1** ⇒ 恢复后 97 PASS / 0 FAIL。

⇒ **⑬ 修掉的 3 处自测回归**（都是 EXT-024 **故意**改变行为导致，按「以指令内容为准」更新断言，**不削弱**「不臆造」语义）：
`t3`「`'Chinese'` ⇒ None」⇒ 改为「⇒ `'zh'`」；`t4`「非法码 `'Chinese'`」⇒ 改用真·未知 `'xx'`（**另加**「`'Chinese'` ⇒ 真的按 `'zh'` 传给 MT」）；
`p1`「`holder['session']` 必须有」⇒ 改为 `session or last_session`（EXT-024 B 会话关闭清 holder + 归档）。

⇒ **⑭ 本轮产物清单（文件数 / mtime / 字节数，均为实测）**：

| 产物组 | 文件数 | mtime（最早~最晚） | 字节数 |
|---|---|---|---|
| 代码（ext/ extension/ tools/ USER_GUIDE） | 15 | 2026-10-31 09:05 ~ 15:40 | 435 080 |
| 新增自测（test_ext023 / test_ext024 / harness） | 3 | 2026-10-31 11:02 ~ 15:43 | 50 997 |
| 冒烟脚本（`tests/smoke/`，含 README） | 7 | 2026-10-31 09:05 | 16 056 |
| notes 明细（sec11_12 / sec13 / sec14 / sec15 / sec16 / sec17） | 6 | 2026-10-31 00:39 ~ 15:52 | 70 079 |

⇒ ⛔ **未做 / 不宣称**：**Edge 真实手势 1 分钟验收没做**（EXT-024 验收 1–4 条 ⇒ EXT-022 已定② **由用户本人做**）
⇒ **不宣称**「用户已听到配音」「字幕已显示」；**没在真实三引擎上跑过**（未占 GPU/NPU，锁属 TTS 模块）
⇒ **不宣称**「cp_decode 已确认全在 NPU」；⛔ 端到端仍不实时（TTS 稳态 RTF 1.0022）；⛔ 克隆音色仍不生效；
⛔ 本轮**未跑真实推理、未占 GPU/NPU**；`shared/MACHINE_LOCK` 属 **tts 模块**（PID 20684，探得 ALIVE）
⇒ **未创建、未动、未回收**；⛔ **未 kill 用户自己的桥接进程**（开工时 `psutil`/`netstat` 均查不到 `ext.bridge`）；
⛔ **未改任何引擎文件**（ASR/MT/TTS 一行未动；只读 App 的 `exec_devices`）；
⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在；未执行 `git add -f`）。

> **§14 / §13 / §12 / §11 / §10 —— 已下沉**（结论与关键数字保留在上方「当前有效结论」表与「未完成纠偏清单」里）：
> * **§14**（重复启动 ⇒ 端口占用 ⇒ 整屏 traceback）⇒ 明细 **`status/notes/sec14_t2_port_guard.md`**
>   ⇒ 结论：启动器 `_port_in_use`/`_find_port_owner`/`_pid_alive` 三道防线 + 桥接 `_probe_port_free` **前置到 warmup 之前**
>   （命中 10048 ⇒ `return 6`，**不加载模型**）⇒ 重复启动 **24 s + traceback ⇒ 400 ms + 人话提示**。
> * **§13**（P2 收口：`captureMode` 上报 + 扩展图标）⇒ 明细 **`status/notes/sec13_t1_capture_mode_and_icons.md`**
>   ⇒ 结论：`capture_mode` 进 `stats`/`margin.json`（没上报 = `null`，绝不臆造）；扩展图标 16/32/48/128（`manifest.key` 未动 ⇒ 扩展 ID 不变）。
> * **§12 / §11**（EXT-016 收口 + EXT-017② 行为级验收）⇒ 明细 **`status/notes/sec11_12_ext016_closeout.md`**
>   ⇒ 结论：抓到 2 个真缺陷（`_caption_app_running()` 阻塞 start 4.208 s；`test_ext017_user_report.py` 假 FAIL）
>   ⇒ 启动器 `start()` **4.244 s → 0.032 s**（满足 EXT-017②「2 秒内可见输出」）；STATUS 拆分（归档 224 833 B）。
> * **§10**（EXT-017 落地：乱码 / start 无输出）⇒ **原文一字未删**见归档
>   **`status/archive/STATUS_EXT_upto_20261030.md` 的 `## §10`**
>   ⇒ 结论：控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；
>   ★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`；
>   用户方式实测通过（6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。
