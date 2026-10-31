# STATUS_EXT
last_ack: EXT-026
更新时间: 2026-10-31 21:47
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；逐条明细见 `status/notes/`
当前任务: **§18 EXT-026 收口** ⇒ ✅ 真实三引擎端到端冒烟已跑（两条路径各 60 s）⇒ ✅ 证据落盘（A 轮 `.tmp/ext026_e2e/` 8 个 / B 轮 `.tmp/ext026_prodpath/` 7 个）⇒ ✅ 录音实测非静音（A −23.88 dBFS / 32 burst；B −26.30 dBFS / 28 burst）⇒ ✅ EXT-023 收口（`on_npu=17 / on_cpu=[]`，cp_decode=NPU）⇒ ✅ `seenDubIds` 跨会话撞号已修 ⇒ ✅ **23 套 / 1 064 PASS / 1 FAIL**（唯一 FAIL = 既有 `test_ext016_compression`，reviewer 独占文件只读不改）⇒ ⚠️ 认领 **EXT-026** ⇒ `last_ack` = **EXT-026** ⇒ ⛔ **Edge 默认 profile 真实手势验收仍需用户本人做**（tabCapture 需真实手势）⇒ ⛔ 端到端仍不实时（TTS 稳态 RTF 1.0022）/ 同步误差仍超标 / 克隆音色仍未接线（既有阻塞项，未动引擎）

阻塞 / 待决定:
① ⛔ **Edge 真实手势 1 分钟验收（EXT-024 验收 1–4 条）** —— 需**用户本人**在 Edge 默认 profile 手动：双击桌面「实时配音桥接.cmd」→ 等就绪 → 打开英文网页视频 → 点扩展「开始」→ player 点「开始捕获」→ 连播 1 分钟；截图 30 s / 60 s 各一张；bridge.log 本次段级日志 ≥5 段且「下发到 player」段数 = TTS 段数、无「不顶替」无 10048
② ⛔ **端到端仍不实时，TTS 提速是上线的唯一前置** —— 稳态端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**，源 `.tmp/ext008_bench/steady.json`）⇒ 建议目标 ≤ 0.85，**由主会话转达 TTS 模块**
③ ⛔ **同步误差仍全部超标** —— 流水线轮 `sync_err_ms.p50=67289.3` / `n_over_target=22` / `last_segment_lag_sec=71.2074`（源 `.tmp/p1_pipe/p1_report.json`）⇒ 实时未达成
④ ✅ **EXT-023 已收口**（§18 实测 `on_npu=17 / on_cpu=[] / on_unknown=[]`，cp_decode=NPU，源 `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`）⇒ 原「待真实值」阻塞项**解除**（★ 见 §18，不臆造）
⑤ ⛔ **pyannote 旁路未接线**（克隆音色仍不生效）—— ASR-013 交付后由主会话通知；⛔ **P2（克隆/体验/稳定性）/ P3（打包）未开始**
⑥ ℹ️ **tabCapture 生产路径仍未实测**（EXT-005 ①）+ **浏览器端人工验收未做**（EXT-017 ④余项）⇒ 均需真实用户手势，由用户本人做
⑦ ℹ️ **EXT-009 服务端 lag 估计存在跨时钟常量偏差，尚未定量标定**（§17 已写清与 t_start 时间轴口径的关系；决策在服务端，不影响变速稳定性）；ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准）

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
| 自测套件 | **23 套 / 1 064 PASS / 1 FAIL**（唯一 FAIL = 既有 `test_ext016_compression`，reviewer 独占的 `CORRECTIONS_EXT.md` 21 943 B > 20 480 B ⇒ **只读不改**） | §18 本轮实测 |

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
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ✅ **ducking + 字幕已修好**（§15）；✅ **目标语言已真正生效**（§16，`applied_target_lang` 可核对）；⛔ **克隆音色仍不可用**（pyannote 旁路未接线）；⛔ 设置持久化 / 暂停拖动 / 30 分钟不崩未开始（需真实浏览器 + 真实引擎） |
| T-4 余项 | 真实三引擎上端到端验证语言切换 | ✅ **已在真实三引擎上跑过**（§18：两轮 `pipeline=true` / `mode=real`，MT 段数 7 与 5，译文字幕截图已落盘）⇒ ⚠️ 但**同步误差仍超标** |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；
> §9 及更早的章节全文在 **`status/archive/STATUS_EXT_upto_20261030.md`**（224 833 B）。
>
> | 章节 | 明细全文 | 结论摘要 |
> |---|---|---|
> | §13~§15 | `status/notes/sec13…sec15_*.md` | `captureMode` 进 stats/margin.json（未上报=`null`）；扩展图标 16/32/48/128；重复启动 ⇒ **400 ms 退出码 6**（端口探测前置到 warmup 之前）；面板 4 个死控件已修 ⇒ `client_target_lang`/`client_voice`/`dbToGain` 进 stats |
> | §16 | `status/notes/sec16_t4_target_lang_effect.md` | 目标语言「只传不生效」已修（`mt()/tts()` 支持按调用覆盖 + 会话统一口径）⇒ `applied_target_lang` 可核对；老引擎回落旧行为并**如实**记 None |
> | §17 | `status/notes/sec17_ext024_closeout.md` | EXT-024 A–G + EXT-023 + EXT-022 全量明细（含根因、实测、反证、产物表） |
> | §18 | `status/notes/sec18_ext026_real_e2e.md` | EXT-026 真实三引擎端到端冒烟全量明细（两条路径各 60 s、证据清单、录音非静音实测、EXT-023 收口、5 个真缺陷） |

### §18 EXT-026 收口 —— 真实三引擎端到端自动化冒烟 + 证据落盘 + `seenDubIds` 撞号修复（2026-10-31 21:23）

**依据**：闸门 → **exit 0**（latest=**EXT-026** / last_ack=25 / n_entries=10）⇒ **认领 EXT-026** ⇒ `last_ack` = **EXT-026**。
★ **明细全文见 `status/notes/sec18_ext026_real_e2e.md`**（7 节，12 482 B）——本节按 EXT-016 常设规则**只留结论**（★ 数字**一字未改**）。

⇒ **① 上一轮被中断**：worktree 脏（3 改 + 9 未跟踪），notes 声称 `.tmp/ext026_e2e/` 有 7 个证据文件但该目录**实际为空**
（mtime 18:24，被失败重跑清空）⇒ 本轮重跑。

⇒ **② 共享机器锁**：开工时 `shared/MACHINE_LOCK` = `module: tts / pid: 18968 / started: 21:00:41` ⇒ ctypes `OpenProcess` +
`GetExitCodeProcess` 探得 **ALIVE**（259）⇒ **TTS 模块的活锁 ⇒ 未创建、未动、未回收**（铁律：探测失败一律视为存活）；
本轮取锁跑 A/B 两轮，**跑完已释放**，无残留进程。

⇒ **③ 跑了两轮**：EXT-026 指定的是**生产路径**（上行在 offscreen ⇒ tts 下发给 offscreen ⇒ offscreen 经 SW 广播给 player
= EXT-024 A 的转发链），但**自动化下必然拿不到 tabCapture**（实测错误原文 `Extension has not been invoked for the current
page (see activeTab permission). Chrome pages cannot be captured.`）⇒ 抓流降级 `getDisplayMedia`。
**A 轮 `.tmp/ext026_e2e/`**（20:30:56→20:34:29，60 s，兜底路径）+ **B 轮 `.tmp/ext026_prodpath/`**（20:53:58→20:57:02，
60 s，**生产路径**）⇒ 两轮抓流**都如实上报 `getDisplayMedia`**，**没有**谎报成 `tabCapture`。

⇒ **④ 实测**（原始字段，详见 notes）：

| 项 | A 轮 | B 轮 |
|---|---|---|
| 段级日志 / 「下发到=player,uplink」 | **9** / **9 of 9** | **9** / **9 of 9** |
| 有 TTS 的段 / 空段（EXT-010 设计仍下发） | **7** / 2 | **5** / 4 |
| 10048 端口占用 / 「不顶替」 | **0** / 2 | **0** / 2 |
| TTS 语音总时长 | **43.84 s** | **27.84 s** |
| `hello_ack` | **mode=real / engines_ready=true / pipeline=true** | 同左 |
| `dubDelivered / echoRecv / dubDup` | **9 / 9 / 9** | **9 / 9 / 9** |
| `asr / mt / ttsSegments` | **7 / 7 / 7** | **5 / 5 / 5** |
| `lagSec` / `captureMode` | 12.7046 / getDisplayMedia（**如实**） | 16.4806 / getDisplayMedia（**如实**） |
| 段 id 形态 | `seg_55035942_194400` | `seg_77393782_194400` |

A 轮另有 `schedClamped=7 / audioRecvSec=151.89225 / uplink.running=true / wsOpen=true / gaps=0 / maxAbsSkewMs=32.4958`。

⇒ **⑤ 录音实测非静音**（新增可复现工具 `tests/smoke/analyze_dub_audio.py`，headless Edge WebAudio **纯解码**，不跑推理）：
A 轮 `dub_player.webm` **585 326 B / 76.2 s / peak 0.56574 / RMS 0.063978（−23.88 dBFS）/ 32 burst / 语音 26.74 s（35.09 %）**；
B 轮 **409 669 B / 115.02 s / peak 0.71230 / RMS 0.048422（−26.30 dBFS）/ 28 burst / 语音 18.08 s（15.72 %）**
⇒ 两轮 `non_silent=true`；分析落盘 `dub_audio_analysis.json`（488 B / 497 B）。

⇒ **⑥ EXT-023 收口**：`bridge.log` 21 行 EXECUTION_DEVICES；落盘 `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json`
（4 260 B，20:54:13）⇒ **`on_npu=17` / `on_cpu=[]` / `on_unknown=[]`**，`cp_decode`=NPU，
`talker`/`cp_prefill`/`decoder` 全 NPU ⇒ **无任何组件落在 CPU**（`absent` 4 项是 App 侧未暴露的组件名，非落 CPU）。

⇒ **⑦ `seenDubIds` 跨会话撞号已修**（EXT-026 第 5 条）：原 `seg_{s0}` 每会话从 0 开始 ⇒ 与页面级常驻的 `seenDubIds` 撞号
⇒ 新会话的段被**静默丢弃**。修法：`ext/bridge.py` 加 `public_seg_id()` ⇒ 段 id = `seg_{8位纯数字会话前缀}_{数字}`
（★ 前缀必须**纯数字**，否则 `tools/compare_ext011_cores.py` 的 `int(id.split("_")[-1])` 会 ValueError）；内部键
（`_seg_orig_end` / `_seg_ready` / speaker tracker）仍用裸 `seg_id`；`hello_ack` 新增向后兼容字段 `session_id`。

⇒ **⑧ 修掉的 5 个真缺陷**（**只有生产路径才会暴露** —— EXT-024 A 的转发链此前**从未在真实三引擎上跑过**）：
**P1** `pollStats()` 只认 `upState.ws`（生产路径上行在 offscreen）⇒ **状态条段数恒为 0** ⇒ 回落用 player 自己那条 WS；
**P2** `sw.js`/`offscreen.js` **都没有 flush** ⇒ **用户点「停止」时最后一句永远丢** ⇒ `offscreen.flushUplink()`
+ `sw.case 'flush'` + `popup`「停止并收尾（跑完最后一句）」（**先 flush，12 s 后自动 stop**）；
**P3** popup 配置**只写 storage 不够**（`loadCfg()` 读进 **DOM 输入框** ⇒ 加载后再写无效）⇒ 须**同时**写 storage 与 DOM；
**P4** `pairUrl()` 从 ws 端口 **+1** 推配对端口 ⇒ 改用 `_free_port_pair()` 取**连续两个**空闲端口；
**P5** `pollStats` 有**两处** `send` ⇒ 旧反证只改坏一处失效 ⇒ C4 反证改为**同时**改坏两处。
★ 逐条根因/影响/修法/反证全文见 notes §4。

⇒ **⑨ 产品代码改动**（全部在 EXT 模块内，**未动任何引擎文件**）：`ext/bridge.py`（段 id 会话前缀 + `hello_ack.session_id`）；
`extension/player.js`（`metrics.dubDup` + 录音三函数 + `flushUplink` + `pollStats` 回落 + 新会话清 `seenDubIds`）；
`player.html` / `popup.html` / `popup.js`（「停止并收尾」按钮）；`offscreen.js` + `sw.js`（`flushUplink` + `case 'flush'` 中转）；
`USER_GUIDE.md` + `extension/USER_GUIDE.md`（**两份必须一致**，有自测守着）—— 逐文件见 notes §5。

⇒ **⑩ 新增自测**：`test_ext026_audio_analysis.py`（**25 项**：4 种合成波形真值对照 + 2 组反证）；
`ext026_prodpath_harness.js`（**17 项**，4 组反证）+ `test_ext026_prodpath.py`（**14**）；
`ext026_segid_harness.js`（**13**）+ `test_ext026_seg_id_uniqueness.py`（**15**）；
`ext026_e2e_harness.js`（**13**，C4 反证修正）⇒ **23 套 / 1 064 PASS / 1 FAIL**；node harness 6 套全 0 FAIL
（13/17/13/33/26/28）；三套明文要求的自测单独确认 rc=0（**103**/**11**/**19**）；闸门仍能解析（`entries=10` /
latest=EXT-026 / last_ack=25 / exit=0）⇒ 没弄坏闸门。

⇒ **⑪ 唯一 FAIL 归因**：`test_ext016_compression.py`（「压缩后 CORRECTIONS 明显变小（实测 21 943 B）」）⇒ **既有状态、
非本轮引入**（阈值 20 480 B；reviewer 独占的 `CORRECTIONS_EXT.md` 只读、未修改，`.gitignore:34` 忽略，
`git log --all` 无记录）⇒ **如实报告，不修改、不 `git add -f`**。

⇒ **⑫ 产物清单**（均为**实测**）：A 轮证据 **8 个 / 665 745 B**（`.tmp/ext026_e2e/`）；B 轮证据 **7 个 / 469 835 B**
（`.tmp/ext026_prodpath/`）；产品代码改动 **9 个 / 344 468 B**（改动量 +543 −143 行，diff 70 562 B）；
新增自测 + 冒烟脚本 **10 个 / 150 109 B**；notes 明细（sec18，重写）**1 个 / 12 482 B**（mtime 见 notes）。

⇒ **⑬ 未做 / 不宣称**：⛔ **Edge 默认 profile 真实手势验收未做**（EXT-022 已定② ⇒ **由用户本人做**）
⇒ **可以请用户在 Edge 默认 profile 手势验收**；⛔ **不宣称「用户已听到配音」**（录音非静音已实测，真人听感仍待用户验收）；
⛔ **不宣称「tabCapture 生产抓流已在真机验证」**；⛔ 端到端仍不实时（TTS 稳态 RTF **1.0022** > 1.0）、同步误差仍超标、
克隆音色仍未接线 ⇒ **既有阻塞项，未动引擎**，由主会话转交 TTS 模块；⛔ **未改任何引擎文件**；
⛔ `CORRECTIONS_EXT.md` **只读、未修改、未入库**。

### §17 EXT-024 收口 —— 下行接通 / 生命周期 / 启动器 / 段级日志 / 状态条 / 模式 / 语言 + EXT-023（2026-10-31 15:57）

**依据**：闸门 → **exit 0**（latest=**EXT-025** / last_ack=17 / n_entries=9）⇒ **认领 EXT-024 + EXT-025** ⇒ `last_ack` = **EXT-025**。
★ **明细全文见 `status/notes/sec17_ext024_closeout.md`**（12 节，19 109 B）——本节按 EXT-016 常设规则**只留结论**（★ 数字**一字未改**）。

⇒ **① 根因**：`player.js` 开了**两条** WS —— `connectBridge(...,'player')` **有** onmessage 但**不上行**（会话永不产段）；
`startUplink()` 的 `upState.ws` **只发 pcm 没有** onmessage ⇒ 服务端把 tts 发到上行连接 ⇒ **被浏览器丢弃**
⇒ **配音与字幕全丢**、只剩 DelayNode 延迟的原声 ⇒ 与用户 10-31 实测描述一致。

⇒ **② A 修下行**：**服务端按 token 广播**（reviewer 给的两个选项之一）—— `ConnectionRegistry` + `classify_role()`
（⚠️ 未报角色的连接**不当** player）+ `downlink_targets()` + `_broadcast_task()`；插件两条 WS **都**挂 onmessage
（共用 `handleBridgeMessage`）+ **按 `id` 去重**（`seenDubIds`，容量 500）；offscreen 经 SW 转发给 player
（旧实现只计数不转发 ⇒ offscreen 路径下 player 永远收不到 tts）。

⇒ **③ B~J 其余六项**（会话生命周期 / 启动器 / 段级日志 / 状态条 / popup / 语言映射 / EXT-023）⇒ 结论与数字
**一字未改**地写在 **`status/notes/sec17_ext024_closeout.md`**（§2–§9 节）+ 上表「当前有效结论」对应各行。

⇒ **④ EXT-022**：编号改 **T-1…T-4**；流水线 `--pipeline` **默认开启**（`--no-pipeline` 逃生口）；
浏览器端人工验收**由用户亲自做** ⇒ 冒烟脚本 `pw_accept1-4` 入库 `tests/smoke/` ⇒ **4 个脚本全 rc=0**。

⇒ **⑤ 自测 + ★反证**：新增 `test_ext023_tts_exec_devices.py`（**23 项**，含反证）/ `test_ext024_dl_routing.py` **55** /
`test_p1_plumbing.py` **99** / `test_t3_dead_controls.py` **53** / `test_t4_target_lang_effect.py` **52**
⇒ 当时 **19 套 / 990 PASS / 0 FAIL**（★ 现 **23 套 / 1 064 PASS / 1 FAIL**，见 §18）；
★ **反证**：`session_holder["last_session"] = session` 改成 `pass` ⇒ **2 条断言全红 rc=1** ⇒ 恢复后 97 PASS / 0 FAIL。

⇒ **⑥ 修掉的 3 处自测回归**：按「以指令内容为准」更新断言，**不削弱**「不臆造」语义：`t3`「`'Chinese'` ⇒ None」⇒「⇒ `'zh'`」；
`t4` 非法码改用真·未知 `'xx'`；`p1`「`holder['session']` 必须有」⇒ `session or last_session`。

⇒ **⑦ §17 产物**：代码 15 个 / 435 080 B；新增自测 3 个 / 50 997 B；冒烟脚本 7 个 / 16 056 B；notes 明细 6 个 / 70 079 B。

⇒ ⛔ **未做 / 不宣称（§17 当时）**：Edge 真实手势验收没做（⇒ **由用户本人做**）；**不宣称**「用户已听到配音」「字幕已显示」；
**没在真实三引擎上跑过**；**不宣称**「cp_decode 已确认全在 NPU」；⛔ 端到端仍不实时（TTS RTF 1.0022）；⛔ 克隆音色仍不生效；
⛔ **未改任何引擎文件**；⛔ `CORRECTIONS_EXT.md` **只读、未修改、未入库**。
★ 上述「没在真实三引擎上跑过」「不宣称 cp_decode 全在 NPU」两条，**已在 §18 被实测取代**（不回头改本节）。

> **§16 ~ §10 —— 已下沉**（明细全文在 `status/notes/`；§10 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`）：
> * **§13 ~ §16** 明细全文见 `status/notes/sec13…sec16_*.md`（§16 摘要见上方指针表）。
> * **§12 / §11** 启动器 `start()` **4.244 s → 0.032 s**（EXT-017②）；STATUS 拆分归档（`notes/sec11_12_ext016_closeout.md`）
> * **§10** 控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；
★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`，用户方式实测通过
（6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。
