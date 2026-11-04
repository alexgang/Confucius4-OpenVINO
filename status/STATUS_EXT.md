# STATUS_EXT
last_ack: EXT-036
更新时间: 2026-11-04 18:40
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；明细见 `status/notes/`
当前任务: **§28 EXT-036 交卷（§27 复核七项逐条落实）** —— ✅ **① 7 s 缺口已定性并修复**：**不是下行慢，是两端轴对不上**（`t0` 换算符号反了：`t0 = t0Up − dOff`；旧式 `+ dOff` ⇒ t0=−3.409 <0 **不自洽**；差值 **6.7787 s = 2×|dOff|** ⇒ 与 reviewer 实测 6.84~7.82 s **同量级**）｜✅ **② sync 根因分解**（**非 TTS 固定项** 与 **TTS 无限快时的残余滞后**；轴缺口与真实下行耗时**分列**）｜✅ **③ 斜率只用有 TTS 的段**（新 **−0.46251 / r²=0.8819 / n=14** ≈ reviewer 独立重算 0.476）｜✅ **④ 首段 3.5 s 一到就交出**（不裁缓冲 ⇒ 栅格不变 ⇒ 尾段不丢）｜✅ **⑤ 录音时间轴不再压缩**｜✅ **⑥ 时长比三口径分列**｜✅ **⑦ PID 记录改正**（撤回 §27①「26736 已关」；**7896 属越权**）⇒ ✅ **九套自测全 0 FAIL**（122/11/19/112/25/42/25/**59**/29）⇒ ⛔ **真实 e2e 未跑完**（MACHINE_LOCK 被 ASR 模块持有，PID 3449 排队）⇒ ⛔ 未打包（APP-057）/ ⛔ 克隆音色不可用（★ 明细见 §28 与 `notes/sec28_ext036.md`）

阻塞 / 待决定:
① ⛔ **EXT-036 ①⑤ 两条验收待真实 e2e 确认**：已完成**定性 + 修复 + 合成数据自测**，但 `MACHINE_LOCK` 被 **ASR 模块**持有（`asr` PID **22936**，started **17:50:25**，task=`asr113-param-ab`，`OpenProcess+GetExitCodeProcess` 实测 `code=259` ⇒ **ALIVE**）⇒ e2e（PID **3449**，已 `addpid` 登记）**排队等待** ⇒ **未写「e2e 已过」**；待验证：`|plyReady−srvReady−上行延迟|` **P95 ≤ 0.3 s**、**wav 时长与 durationSec 差 ≤ 0.2 s**
② ⛔ **sync 归因已改写（撤回 §27 的「全归 TTS」）** ⇒ TTS 吞吐只解释**积压部分**（约 25–33 s）；**非 TTS 固定项**（轴缺口 **6.78 s** + ASR 整段定稿约 3 s + 播放排队 0–2.8 s）**与 TTS 快慢无关** ⇒ 即使 TTS 无限快仍会晚 ⇒ **归 EXT / ASR**；⇒ **TTS 提速指标请主会话转达 TTS 模块**：要不积压须 `tts/src ≤ 1` ⇒ **RTF_out ≤ 0.82**，建议目标 **≤ 0.75**（`tts/src ≈ 0.92`，留 8 % 余量）
③ ⛔ **时长比未解决，但口径已明确**（§28⑥）：reviewer 的 **0.57–1.55** 是 `over_src_len`（`d_player ÷ 源段长`）；STATUS 旧写的 **0.68–1.49** 是 `speed_adjusted` ⇒ **两者不是同一个数**（不是算错）⇒ 现三口径分列落盘 ⇒ 需 TTS 提速后重测
④ ⛔ **EXT-028 待用户抽听 ⇒ V2.0 插件部分暂不放行**（旧结论已在 §25 撤回）—— 交付物已落 `shared/ext_listen/ext032_20261102_010022/` 与 `shared/ext_listen/ext033_20261102_121928/`；⛔ **pyannote 旁路未接线**（克隆音色仍不生效，依赖 ASR-013 交付）；⛔ **P3（打包）未开始**
⑤ ⛔ **进程越权已记录（§28⑦）**：**PID 7896 不在 EXT-035 授权范围**（只授权 4896 与「bridge 互斥拒绝时关 26736」）⇒ 关闭它**属越权**；且 **26736 实际未关**（查询时已不存在）⇒ **实际只关了 4896 与 7896 两个** ⇒ **撤回 §27① 的「26736 排队拿锁后关」**；⇒ **新规则**：遇到点名以外的实例 **一律停下来写进 STATUS 请主会话找用户确认**，不按「意图」自行扩大范围
⑥ ℹ️ **tabCapture 生产路径仍只能用户手势**（探针 12 次全败）—— 但 **EXT-033 已改走页面元素抓取** ⇒ 该手势需求**已绕开**；ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准）；✅ **EXT-023 已收口**（§18 实测 `on_npu=17 / on_cpu=[]`）


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
| 自测套件 | **29 套**（`test_ext_selfcheck` **122 PASS / 0 FAIL**、★ `test_p1_plumbing` **112 PASS / 0 FAIL**、`test_ext029` **70 PASS / 0 FAIL**、★ `test_ext032_deliver` **29 PASS / 0 FAIL**、★ **`test_ext036_review` 59 PASS / 0 FAIL**）；node harness **29 PASS / 0 FAIL**；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改）；另 3 套 node-harness 类既有 FAIL（2/2/3，已 `git stash` 对拍确认**基线既有**，非回归） | §21/§23/§25/§27/**§28** 实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-036** | §27 复核七项：7 s 缺口定性/根因分解/斜率口径/首段提前/录音时间轴/时长比口径/PID 改正 | ✅ **已认领并执行**（§28）：**① 缺口已定性并修复**（**不是下行慢，是轴对不上**：`t0 = t0Up − dOff`，差 **6.7787 s = 2×|dOff|** ≈ reviewer 实测 6.84~7.82 s）｜**② 根因分解**（`sync_rootcause`：**非 TTS 固定项** + `tts_independent_lag_sec`；轴缺口与真实下行**分列**）｜**③ 斜率只用有 TTS 的段**（新 **−0.46251 / r²=0.8819 / n=14** ≈ reviewer 重算 0.476；旧 0.248/0.375 **作废**）｜**④ 首段 3.5 s 即交出**（不裁缓冲 ⇒ 栅格不变 ⇒ 尾段不丢；两端**逐位相等**）｜**⑤ 录音时间轴不再压缩**（worklet 补静音样本 + `ConstantSourceNode`）｜**⑥ 时长比三口径分列**｜**⑦ PID 记录改正**（撤回 §27①；**7896 属越权**）⇒ ✅ **九套自测 0 FAIL**；⛔ **真实 e2e 未跑完**（MACHINE_LOCK 被 ASR 模块持有，PID 3449 排队）⇒ ①⑤ 两条验收待实测确认 |
| **EXT-035 / EXT-034** | 关 v2.1 空闲 pythonw 后重跑 e2e；EXT-034 四项（同步覆盖 / RTF 口径 / 首段过长 / 所需 D） | ✅ **已认领并执行**（§27）：EXT-035 验收 **5 项全过**（`t0UpPlayerOffsetSec=-3.389 s` / 首段就绪→起播 **0.005 s** / 开口静音 **14.620 s** / detail **14/14** / 三口径 1.1937·1.2227·1.4595）；⛔ **sync 35.1/41.9 s 未达标**（⇒ §28② 已**撤回「全归 TTS」**的单因归因） |
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
> | §27 | `notes/sec27_ext034_035.md` | **EXT-034/035 交卷**：① 同步测量覆盖 **7/13 → 14/14**（`start(when)` 采样精确排程起点，onset 口径单列）② RTF **三口径分列**（1.1937 / 1.2227 / 1.4595）③ 首段**会话级拆两段**（startup 25.5→9.7 s，切点逐位不变）④ `D_required=19.939 s`；✅ **EXT-035 验收 5 项全过**；⛔ sync **35.1/41.9 s** 未达标（⇒ **§28② 撤回「全归 TTS」**） |
> | **§28** | **`notes/sec28_ext036.md`** | **EXT-036 交卷（§27 复核七项）**：**① 7 s 缺口已定性并修复**（**不是下行慢，是轴对不上**：`t0 = t0Up − dOff`；差 **6.7787 s = 2×|dOff|** ≈ reviewer 实测 6.84~7.82 s）｜**② 根因分解**（`sync_rootcause`：**非 TTS 固定项** + `tts_independent_lag_sec`；轴缺口与真实下行**分列**）｜**③ 斜率只用有 TTS 的段**（新 **−0.46251 / r²=0.8819 / n=14** ≈ reviewer 重算 0.476；旧 0.248/0.375 **作废**）｜**④ 首段 3.5 s 即交出**（不裁缓冲 ⇒ 栅格不变）｜**⑤ 录音时间轴不再压缩**｜**⑥ 时长比三口径分列**｜**⑦ PID 记录改正**（撤回 §27①；7896 属越权）⇒ ✅ **九套自测 0 FAIL**；⛔ **真实 e2e 未跑完**（MACHINE_LOCK 被 ASR 模块持有） |

## §28 —— EXT-036 交卷：§27 复核七项逐条落实（2026-11-04 18:40）

★ **全量明细见 `status/notes/sec28_ext036.md`**（逐条证据、实测值、反证组、变异测试）。

⇒ **① 7 s 缺口已定性并修复（真缺陷）**：**不是下行慢，是两端轴对不上** —— `dOff = up−player` ⇒ 换算须**减**：`t0 = t0Up − dOff`（旧式 `+ dOff` ⇒ 实测 t0=**−3.4091** **不自洽**，修后 **+3.3696 ≥ 0** ✅）；**两式差 6.7787 s = 2×|dOff|** ≈ reviewer 实测 **6.84–7.82 s** ⇒ **恒定 ⇒ 排程错，非下行慢**；新增自证判据 `t0 ≥ 0`；服务端 `srv_wall_ms` ↔ 插件 `ply_wall_ms` ⇒ `downlinkMs` = **真实下行耗时**。
⇒ **② 根因分解**：新增 `decompose_sync_rootcause()` ⇒ `margin.json` 的 `sync_rootcause`（**非 TTS 固定项** + `tts_independent_lag_sec`）；★ **轴缺口与真实下行耗时分列**（前者是排程错、修后 ≈0；后者才是「慢」、判据 P95 ≤ 0.3 s）⇒ **撤回 §27「全归 TTS」的单因归因**：TTS 只解释积压（约 25–33 s），**非 TTS 固定项**（轴缺口 6.78 s + ASR 整段定稿约 3 s + 播放排队 0–2.8 s）**与 TTS 快慢无关** ⇒ 归 EXT/ASR。
⇒ **③ 斜率只用有 TTS 的段**：顶层改 TTS-only，旧全段口径保留为 `lag_growth_slope_all_sec_per_sec`（**已作废**）；**旧产物对拍**（32 段/14 段有 TTS）：新 **−0.46251 / r²=0.8819 / n=14** vs 旧 **0.24841 / r²=0.3752 / n=32** ⇒ 新值 ≈ reviewer 独立重算 **0.476**（差 3 %）✅；判据 `_seg_has_tts()`：字段全缺 = **未知 ⇒ 计入**。
⇒ **④ 首段 3.5 s 一到就交出**：新增 `_first_segment_early()`；★ **交出后不裁 `_buf`**（只记 `_first_seg_cut`）⇒ **VAD 切点栅格逐位不变** ⇒ **尾段不被吃掉**（旧版裁缓冲 ⇒ 栅格平移 3.5 s ⇒ 尾段丢失）；偏移改用新增 `_buf_base`；**实测**（120 s 合成）：首段 `(0,3.5)` 精确、后续切点逐位不变、尾段终点与原网格一致、**两端口径完全相等** ✅。
⇒ **⑤ 录音时间轴不再压缩**：病根①`dubBus` 无配音时无输入 ⇒ worklet 空输入 ⇒ 旧代码静音期**一块不写**；②`MediaStreamDestination` 无输入 ⇒ **不产帧** ⇒ webm 同压。修法：worklet **按渲染量子补写静音样本**（值 0）+ 落 `silentBlocks`；录音挂 **`ConstantSourceNode`** 保 webm 连续（停录即停掉）；落盘 `acElapsedSec`/`wavDurationSec` ⇒ 判据 **|差| ≤ 0.2 s**。
⇒ **⑥ 时长比三口径**：reviewer **0.57–1.55** = `over_src_len`（`d_player ÷ 源段长`）；旧写 **0.68–1.49** = `speed_adjusted` ⇒ **不是同一个数**（非算错）；现 `over_src_len`/`over_ws`/`speed_adjusted` 三口径各带 `definition`；★ 前置修复 `tEnd` **全链贯通**（此前口径 n=0）。
⇒ **⑦ PID 记录改正**：**撤回 §27①「26736 排队拿锁后关」** ⇒ 实际**只关 4896 与 7896**；**7896 属越权**（不在授权范围，explorer 拉起、可能是用户本人重开，「空闲」不能推定用户不要）⇒ **新规则**：点名以外的实例 **一律停下写进 STATUS 请主会话找用户确认**。
⇒ **⑧ 自测九套全 0 FAIL**：122/11/19/112/25/42/25/**59**（新 `test_ext036_review`）/29（node 沙箱）；★ **变异测试实测**：`t0Up − dOff` 改回 `+ dOff` ⇒ 新自测 **57 PASS/2 FAIL** ⇒ 守卫确实抓得住（已还原）；★ 修掉接管时的**两处遗留回归**（`p1_pipeline` 漏导入 `plan_segments` 8 FAIL；`analyze._pct` 被改成线性插值致口径漂移 1 FAIL）。
⇒ **⑨ ⛔ 明确未做**：⛔ **真实三引擎 e2e 未跑完** —— `MACHINE_LOCK` 被 **ASR 模块**持有（`asr` PID **22936**，started **17:50:25**，task=`asr113-param-ab`，`OpenProcess+GetExitCodeProcess` 实测 `code=259` ⇒ **ALIVE**）⇒ e2e（PID **3449**，已 `addpid`）**排队** ⇒ **不写「e2e 已过」** ⇒ **①P95 ≤ 0.3 s 与 ⑤≤ 0.2 s 待实测确认**；⛔ 未改引擎文件／⛔ 未推远程／⛔ 未打包／⛔ `CORRECTIONS_EXT.md` **只读未改未入库**。

## §26 —— EXT-033 交卷（2026-11-02 14:10）

★ **全量明细见 `status/notes/sec26_ext033.md`** ⇒ **三个真缺陷**（`t0` 跨时钟域 / 设备互斥恒失效 / 分析器 `rms` 遮蔽）；真实三引擎 e2e（run `20261102_121431`，13 段 TTS，WAV 104.299 s 不截断）；❌ 开口静音 **26.58 s**、sync P50/P95 = **28.65/29.54 s**、时长比 **0.6825~1.4851**。

## §27 —— EXT-034 / EXT-035 交卷（2026-11-02 21:40）

★ **全量明细见 `status/notes/sec27_ext034_035.md`** ⇒ ① 同步测量覆盖 **7/13 → 14/14**（`start(when)` 采样精确排程起点，onset 口径单列）② RTF **三口径分列**（1.1937 / 1.2227 / 1.4595）③ 首段**会话级拆两段**（startup 25.547→9.731 s，切点逐位不变）④ `D_required=19.939 s`；✅ **EXT-035 验收 5 项全过**（`t0UpPlayerOffsetSec=-3.389 s` / 首段就绪→起播 **0.005 s** / 开口静音 **14.620 s** / detail **14/14** / 三口径分列）；八套自测全 0 FAIL；⛔ sync **35.1/41.9 s** 未达标（⇒ **§28② 已撤回「全归 TTS」的单因归因**）。
