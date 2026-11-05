# STATUS_EXT
last_ack: EXT-038
更新时间: 2026-11-05 11:29
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行 / < 归档/10（22 483 B 上限）；逐条明细见 `status/notes/`
当前任务: **§30 EXT-037 + EXT-038 交卷** —— ✅ **丢 3.5 s 已修**（覆盖率 100%）✅ **口径重写**（fixed/result 分列 + `seg_len`）✅ **compare 口径**（`over_ws`=1.00）✅ **默认 D=20 s**（两侧一致）✅ **真实 e2e `20261105_112057`**（静音 20.11 s、\|wav−dur\| 0.149 s、覆盖 14/14）｜⛔ **sync 有符号 P95 = 16130.6 ms ≫ 300 ms 未达标**（`D_needed` **33.652 s** ⇒ `RTF_out` **1.0562** 饱和 ⇒ **光调 D 无解** ⇒ **请转达 TTS：目标 `RTF_out ≤ 0.75`**）｜✅ 自测 0 FAIL ｜⛔ 未打包 / ⛔ 未改引擎 / ⛔ 未推远程（★ 明细见 §30 与 `notes/sec30_ext037_038.md`）

阻塞 / 待决定:
① ✅ **EXT-036 ①⑤ 已由真实 e2e 确认**（§29）：**下行耗时 P95 = 121 ms**（轮次 B 复现 **35 ms**）≤ 0.3 s ✅；**\|wav − durationSec\| = 0.011 s** ≤ 0.2 s ✅ ⇒ §28「⛔ e2e 未跑完」**解除**
② ⛔ **sync 仍未达标（EXT-038 验收）**：D=20 实测 **有符号 P50/P95 = 5978.7 / 16130.6 ms**（判据 ≤300 ms）⇒ **不写「同步已解决」**、**不自行放宽目标**；★ `D_needed` **33.652 s ≫ D=20** ⇒ **根因是吞吐饱和**（`RTF_out` **1.0562 > 1**、`speech_over_src` **1.244** ⇒ `tts_over_src` **1.3139**）⇒ **任何固定 D 都追不上** ⇒ **请主会话转达 TTS：`RTF_out` 实测 1.0562**（§29 的 0.8182 是丢段后的假值，**已作废**）⇒ **目标 `RTF_out ≤ 0.75`**；`speech_over_src` 1.244 需压到 ≈1.0（归 MT/EXT）；`seg_len` 4.263 + ASR 整段定稿 3.388 归 EXT/ASR
③ ✅ **时长比口径已追平（撤回旧结论）**：旧「0.46–1.08 未追平」是**分析器口径错误**（`d_ws` 已是 WSOLA 后时长又乘一次 speed ⇒ 重复校正）⇒ **作废 `speed_adjusted`**、`d_player` 改 `endedAt−actual` ⇒ **本轮 `over_ws` = 0.9991~1.0008（1.00±0.02 全合格）** ⇒ **不是播放器的问题**；reviewer 的 0.57–1.55 是 `over_src_len` 口径，与 `over_ws` **不可直接互比**
④ ⛔ **EXT-028 待用户抽听 ⇒ V2.0 插件部分暂不放行**；⛔ **pyannote 旁路未接线**（克隆音色依赖 ASR-013 交付）；⛔ **P3（打包）未开始**
⑤ ⛔ **进程越权规则（§28⑦）**：**PID 7896 不在 EXT-035 授权范围** ⇒ 关闭属越权；**新规则**：遇到点名以外的实例**一律停下来写进 STATUS 请主会话找用户确认**；★ **§29/§30 两轮均未关闭任何进程**
⑥ ℹ️ **tabCapture 生产路径仍只能用户手势**（探针 12 次全败）—— 但 **EXT-033 已改走页面元素抓取** ⇒ 该手势需求**已绕开**；✅ **EXT-023 已收口**（`on_npu=17 / on_cpu=[]`）


## 当前有效结论

| 项 | 值 | 来源文件 |
|---|---|---|
| 交付配置 | ASR=R2T2 INT8@GPU.0 / MT=Hy-MT2 INT8@GPU.0 / TTS=Qwen3-TTS@NPU | §10.4 启动日志 |
| 稳态 RTF（去首段 18 段/286.32 s） | 端到端 **2.0507**（ASR 0.6563 / MT 0.1507） / TTS **1.0022**（>1.0） | `.tmp/ext008_bench/steady.json` |
| 流水线末句滞后 | **71.2074 s（↓68.8 %）**，斜率 −0.106051 | `.tmp/p1_pipe/p1_report.json` |
| 扩展 ID / `/pair` Origin | `kekgmfkijphpfndbbpakjaokamkeooib`（manifest `key` 现场算，9 份探针一致）；本插件 **200** / 别的扩展 **403** / 普通网页 **403** / 无 Origin **403** | `ext/extension_id.py`；§10.3 实测 |
| 启动器 / 重复启动 / 桥接冷启动 | `start()` 延迟 **0.032 s**（修前 4.244 s）⇒ 满足 EXT-017②；重复启动 **400 ms 退出码 6**；桥接冷启动 **5.0–5.7 s**（均值 5.324） | §12 / §14 实测 |
| 面板目标语言**实际生效** | `applied_target_lang`（= MT `tgt` / TTS `language` 真正用的码）可与 `client_target_lang` 比对 | §16 实测 |
| 抓流方式（capture_mode） | 由**客户端实际上报**；未上报 = `null`（绝不臆造） | `ext/bridge.py` → `stats()` |
| **下行路由（EXT-024 根因）** | 服务端按 **token 广播** `tts`/`echo`；插件两条 WS **都**挂 `onmessage`；按 `id` 去重 | `ext/bridge.py` → `ConnectionRegistry.downlink_targets` |
| **已下发到 player 段数** | `metrics.link.dubDelivered`（player 端**实际收到**的 tts 数）⇒ **只有它 > 0 才说明下行通了** | `extension/player.js` → `diagnoseLink()` |
| **链路卡住原因（15 s 阈值）** | WS 未连 / 回声模式 / 引擎未就绪 / 没音频轨 / 没出段 / **下行路由断了** —— 红字**如实**写明 | `extension/player.js` → `diagnoseLink()` |
| **连接模式（真实/回声）** | `hello_ack.mode` = `'real'`/`'echo'`（**只增不改**）；`engines_ready` **诚实** | `ext/bridge.py` → `_engines_ready()` |
| **t_start 时间轴口径** | **上行采样时间轴**（`s0/16000`）；插件按 `t0_player + t_start + D` 排程 ⇒ 与原声**同轴** | §17 实测 |
| **语言全称映射（EXT-024 G）** | `Chinese`→`zh` / `English`→`en` / `Japanese`→`ja` / `Korean`→`ko`；未知值 ⇒ None（绝不臆造） | `ext/config.py` → `normalize_lang_code()` |
| **EXT-023 真实值（已收口）** | **`on_npu=17` / `on_cpu=[]` / `on_unknown=[]`**；`cp_decode`/`talker`/`cp_prefill`/`decoder` 全 NPU ⇒ 无组件落 CPU | `%LOCALAPPDATA%/LiveDubEXT/tts_exec_devices.json` |
| **段 id 跨会话唯一（EXT-026 ⑤）** | `seg_{8位会话前缀}_{数字}`（实测 `seg_55035942_194400`）⇒ 修掉 `seenDubIds` 撞号 | `ext/bridge.py` → `public_seg_id()` |
| **生产路径 flush（EXT-026 补齐）** | `offscreen.flushUplink()` → `sw.case 'flush'` → popup「停止并收尾」（先 flush，12 s 后 stop）⇒ 尾段不再丢 | `extension/offscreen.js` / `sw.js` / `popup.js` |
| **设置持久化（T-6）** | popup 8 个设置控件**改了就立刻落盘**（`change` + 文本框 `input` 400 ms 防抖）；落盘前**归一** | `extension/popup.js` → `bindPersistListeners()` |
| **内存不持续增长（T-5）** | 逐帧延迟保留最近 **2000** 条、段级时刻表最近 **50** 段、插件 `gapDetail` 两侧各 **200** 条；**统计口径一字不变** | `ext/config.py` / `ext/bridge.py` → `_trim_seg_timing_history()` |
| **说话人旁路（EXT-029，已收口）** | **独立线程 + 有界队列(64) + `put_nowait`**（满则**丢最旧块**，计数 `spk_queue_drop` 0–57）；标签**异步回填**；**ASR 等 GPU 锁 ≤0.004 %** ⇒ **不反压 ASR** | `ext/speaker_bypass.py` / `ext/spk_engine.py`；`agg_summary.json` |
| **发行包（EXT-031，已交清单）** | `release/V20_HANDOFF.md` 已写（插件 **15 文件 / 219 021 B**）；**模拟发行包启动 6 PASS / 0 FAIL**；★ **App 包内缺 `websockets` + `psutil` ⇒ 打包必补装** | §23；`.tmp/ext031/fake_pkg_probe.json` |
| **pyannote 旁路（已接）** | 分段@**NPU**、嵌入@**GPU.0**（NPU/GPU.1 不可用）⇒ **旁路本身已通**；检出 **S1/S2(/S3)** | `ext/spk_engine.py`（§21） |
| **克隆音色（仍未接线）** | `voice_source` 实测**全 `'preset'`**、`clone_wired=false` ⇒ 引擎层 `voice` 参数**未**接进 `tts_engine.stream()` ⇒ **不宣称克隆音色可用** | `ext/bridge.py` → `_resolve_spk()` |
| **EXT-037 ② 段覆盖率（已修）** | **29 段 / 相邻缺口全 0 / 总覆盖 0→105.791 s（100%）**；**14 个 TTS 段**与参照轮 `20261102_213515` 一致；守卫 = `_buf_base == 0`（只切一次）+ `flush()` 跳已交付前缀 | §30 ①；`notes/sec30_ext037_038.md` |
| **EXT-037 ③ 口径（fixed/result 分列）** | 固定项 = 上行(0) + ASR **3.388** + **`seg_len` 4.263** + 真实下行 **0.039** ⇒ `non_tts_fixed_sec` **7.690**（`unmeasured:[]`）；结果项 = `player_queue` 2.962 / `axis_gap` 4.200 **单列** | §30 ②；`margin.json` → `non_tts_fixed_detail` / `result_items_detail` |
| **EXT-037 ④ compare 口径** | `speed_adjusted` **作废**；主口径 `over_ws`（d_player ÷ d_ws）；`d_player` 主口径 = `endedAt − actual` ⇒ 实测 **0.9991~1.0008** | §30 ③；`ext033_compare.json` |
| **EXT-038 默认 D** | **20 s**（插件 popup/sw/player + bridge `--delay` + 9 个 runner，**两侧一致**）；e2e 三处**全部参数化** + 插件侧写后读回校验 + `reload()` | §30 ④；`tests/test_ext037_seg_coverage.py` |
| **EXT-038 实测 e2e（run `20261105_112057`）** | 静音 **20.11 s**｜\|wav−durationSec\| **0.149 s ≤ 0.2 s** ✅｜覆盖 **14/14** ✅｜⛔ sync **P50/P95 = 5978.7 / 16130.6 ms**（max 16198.3）❌｜`RTF_out` **1.0562**｜`tts_over_src`/`speech_over_src` **1.3139 / 1.2440**｜lag 斜率 **−0.4106**（r²=0.866, n=14）｜`over_ws` **0.9991~1.0008** ✅｜`D_needed` **33.652 s** | §30 ④⑥；`.tmp/ext033_e2e/20261105_112057/` |
| 自测套件 | **本轮全部 0 FAIL**（selfcheck **122** / echo **11** / next_instruction **19** / p1 **112** / ext010 **25** / ext033_capture **42** / ext033_deliver **25** / ext036 **64** / ext036b **41** / ★ **ext037_seg_coverage 53（新建）**）；node 沙箱 **29 / 33 / 16**；★ **变异测试 M1/M2/M3b/M4 全 DETECTED**（M3 数值等价属预期）；唯一既有 FAIL = `test_ext016_compression` 的 CORRECTIONS 体积项（reviewer 独占，只读不改） | §21–§30 实测 |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| **EXT-038** | 默认 D=20 s，同步目标保持有符号 P95 ≤0.3 s | ✅ **已认领并执行**（§30）：**默认 D 改 20 s**（插件 3 处 + bridge `--delay` + 9 个 runner，**两侧一致**）＋ **e2e 的 D 三处全部参数化** + **插件侧写入后读回校验 + reload**｜★ **真实 e2e `20261105_112057`**：静音 **20.11 s**、\|wav−dur\| **0.149 s ≤ 0.2 s**、覆盖 **14/14**、时长比 ✅ ｜⛔ **sync P50/P95 = 5978.7 / 16130.6 ms ≫ 300 ms 未达标**（**不自行放宽目标**）｜★ `D_needed` **33.652 s ≫ D=20** ⇒ **RTF_out 1.0562 饱和** ⇒ **光调 D 无解** ⇒ **请转达 TTS：目标 `RTF_out ≤ 0.75`** |
| **EXT-037** | §29 复核【BLOCKING】：EXT-036④ 引入每段丢 3.5 s；7.184 s 分解口径有误；≤300 ms 需 D≈20 s | ✅ **已认领并执行**（§30）：**② 丢 3.5 s 已修**（守卫 `_buf_base == 0` 只切一次 + `flush()` 跳已交付未裁前缀）⇒ **实测覆盖率 100%**（29 段 / 缺口全 0 / 总覆盖 0→105.791 s，**14 个 TTS 段与参照轮一致**，§29 丢失译文全部恢复）｜**③ 口径重写**（`axis_gap`/`player_queue` 移出固定项、新增 `seg_len`）⇒ `non_tts_fixed_sec` **7.690 s**（`unmeasured:[]`）｜**④ compare 口径**（作废 `speed_adjusted`、`d_player` 改 `endedAt−actual`）⇒ **`over_ws` 0.9991~1.0008 命中 1.00** ｜ ★ **撤回 §29「D=10 已足够吸收 / 7.184 s / 时长比 0.46–1.08」** |
| **EXT-036** | §27 复核七项：7 s 缺口定性/根因分解/斜率口径/首段提前/录音时间轴/时长比口径/PID 改正 | ✅ **已认领并执行**（§28）＋**§29 补测完成真实三引擎 e2e**：①⑤ 两条验收**实测确认**（**下行 P95 = 121 ms ≤ 300 ms**；**\|wav − durationSec\| = 0.011 s ≤ 0.2 s**，轮次 B 复现 35 ms / 0.011 s）｜★ **补测暴露真缺陷并已修**：客户端实测数据**从不上报服务端** ⇒ `sync_rootcause` 三项恒 null 且被**强转成假 0.0** ⇒ 已改（上报 + 接收 + null 不冒充 0 + 新增 `client_metrics`）｜✅ **十套自测 0 FAIL**（**变异测试 4 FAIL** 证明守卫有效）⇒ ⛔ **sync P95 9087/8727 ms 仍未达标**｜⛔ 时长比旧口径 0.46–1.08 **已由 §30④ 撤回** |
| **EXT-035 / EXT-034** | 关 v2.1 空闲 pythonw 后重跑 e2e；EXT-034 四项（同步覆盖 / RTF 口径 / 首段过长 / 所需 D） | ✅ **已认领并执行**（§27）：EXT-035 验收 **5 项全过**（`t0UpPlayerOffsetSec=-3.389 s` / 首段就绪→起播 **0.005 s** / 开口静音 **14.620 s** / detail **14/14** / 三口径 1.1937·1.2227·1.4595）；⛔ **sync 35.1/41.9 s 未达标**（⇒ §28② 已**撤回「全归 TTS」**） |
| **EXT-031** | 插件整合进发行包 V2.0，EXT 交交付清单 | ✅ **已执行**（§23）：`release/V20_HANDOFF.md` 已写；模拟发行包启动 **6 PASS**；★ **打包由 App 线程执行（APP-057）**；⚠️ **App 包内缺 `websockets`+`psutil` ⇒ 打包必补装**；⚠️ `liveDub.release` 需置 `true`（**打包必改 3 处**） |
| **EXT-030** | 巡检会话重叠 ⇒ 开工先拿「模块租约」 | ✅ **已执行**（§22）：自动化插入**四段**（`acquire`/`beat`/`addpid`/`release`）；★ 实测触发 BUSY → 等 30 min → TAKEOVER ⇒ 机制**真实生效**；⛔ **未改 `session_lease.py`** |
| **EXT-029** | 说话人旁路独立线程、不得反压 ASR | ✅ **已执行**（§21）：独立线程 + 有界队列 + 异步回填不等待；**ASR 等 GPU 锁 ≤0.004 %** ⇒ 不反压；5 轮真实 A/B + 4 个真缺陷已修；⚠️ 原文③「墙钟差异 ≤5%」实测**噪声主导不可用** ⇒ 改用机制直接度量 |
| **EXT-032 / EXT-028** | EXT-028 只修代码没交实录；「不构成打包阻塞」不成立 | ✅ **已执行**（§25）：**撤回**旧结论 ⇒ EXT-028 改「**待用户抽听**」；已交逐段三份音频对比（时长比 6/6 = 1.000–1.019、互相关 1.0000、SNR 120 dB）+ 交付目录 `shared/ext_listen/ext032_20261102_010022/`；⛔ **tabCapture 生产路径自动化拿不到** ⇒ 须用户手势 |
| **EXT-027** | 抓错音频 / 持锁 / 克隆接线 / 同步误差 / 按序播放 | 🟡 **部分落地**：① 抓流（API 已修，生产路径**未实测**）✅ / ② 持锁 ✅ / ③ 克隆 ⛔（`voice_source` 全 `'preset'`）④ 同步误差 ⛔（未动引擎）⑤ 按序播放 ✅（`dubPlaybackEnd` 不叠播） |
| **EXT-026 / EXT-024 / EXT-025 / EXT-023 / EXT-022** | e2e 冒烟 / 下行接通 / RESUME / 设备上报 / 编号与流水线默认 | ✅ **全部已执行**（§17–§23）：EXT-023 **已收口**（`on_npu=17 / on_cpu=[]`）；EXT-026 两轮 60 s 真实跑通；EXT-024 **真实三引擎已验证下行通**（`dubDelivered=9`）；⛔ **Edge 真实手势验收仍需用户本人做** |
| EXT-017 ④余项 / EXT-005 ① | 浏览器端人工验收（tabCapture 需真实用户手势） | 需**用户本人**操作（EXT-022 已定②）；本机只有 Edge ⇒ **自动化拿不到 tabCapture** |
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ✅ ducking + 字幕（§15）/ **目标语言已真正生效**（§16）/ **设置持久化已修好**（§19：8 控件 change/input 即时落盘 + 归一 + 幂等）/ **内存不持续增长已修好**（§19：3 类无界增长全部有界化，统计口径一字不变）；⛔ **克隆音色仍不可用**（依赖 ASR-013）；⛔ **「30 分钟不崩」未做**；⛔ **暂停拖动未做**（需真实浏览器 + 用户手势） |

## 最近章节

> ★ 按 **EXT-016 写作规则**：「最近章节只保留最近 3 节」，逐条明细**下沉到 `status/notes/`**；§9 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`（224 833 B）；§13~§27 见 `notes/sec13…sec27_*.md`。
>
> | 章节 | 明细全文 | 结论摘要 |
> |---|---|---|
> | **§28** | **`notes/sec28_ext036.md`** | **EXT-036 交卷**：① 7 s 缺口已定性并修复（**不是下行慢，是轴对不上**：`t0 = t0Up − dOff`；差 **6.7787 s = 2×\|dOff\|** ≈ reviewer 6.84~7.82 s）② 根因分解（轴缺口与真实下行**分列**）③ 斜率只用有 TTS 的段（**−0.46251 / r²=0.8819 / n=14**）④ 首段 3.5 s 即交出 ⑤ 录音时间轴不再压缩 ⑥ 时长比三口径分列（★ 已由 §30④ 修订）⑦ PID 记录改正 ⇒ ✅ **九套自测 0 FAIL**；⛔ 当时 e2e 未跑完 ⇒ **★ §29 已补测确认** |
> | **§29** | **`notes/sec29_ext036_e2e.md`** | **EXT-036 补测（真实三引擎 e2e 跑完）**：✅ **① 下行耗时 P95 = 121 ms ≤ 300 ms**（轮次 B 复现 **35 ms**）✅ **⑤ \|wav − durationSec\| = 0.011 s ≤ 0.2 s**｜★ **补测暴露真缺陷**：客户端实测数据**从不上报服务端** ⇒ `sync_rootcause` 三项恒 null 且被**强转成假 0.0** ⇒ **已修**（上报 + 接收 + null 不冒充 0 + 新增 `client_metrics`）｜✅ **十套自测 0 FAIL**（新增 `test_ext036b_client_metrics`）⇒ ⛔ **sync P95 9087/8727 ms 仍未达标**（★ §30 实测 5978.7/16130.6 ms，仍未达标） |
> | **§30** | **`notes/sec30_ext037_038.md`** | **EXT-037 + EXT-038 交卷**：① **丢 3.5 s 已修**（`_buf_base == 0` 只切一次 + `flush()` 跳已交付前缀）⇒ **覆盖率 100%**（29 段 / 缺口全 0 / 总覆盖 0→105.791 s）② **口径重写**（`axis_gap`/`player_queue` 移出固定项、新增 `seg_len`）⇒ `non_tts_fixed_sec` **7.690 s** ③ **compare 口径**（作废 `speed_adjusted`、`d_player` 改 `endedAt−actual`）⇒ **`over_ws` 0.9991~1.0008** ④ **默认 D=20 s**（两侧一致）+ 真实 e2e `20261105_112057`｜⛔ **sync P95 16130.6 ms 未达标**、`D_needed` **33.652 s**、`RTF_out` **1.0562** 饱和 ⇒ **请转达 TTS：目标 RTF_out ≤ 0.75** |

## §28 —— EXT-036 交卷：§27 复核七项逐条落实（2026-11-04 18:40）

★ **全量明细见 `status/notes/sec28_ext036.md`**（逐条证据、实测值、反证组、变异测试）

⇒ **① 7 s 缺口已定性并修复**：**不是下行慢，是两端轴对不上**（`t0 = t0Up − dOff`；旧式 `+ dOff` ⇒ t0=**−3.4091** 不自洽；两式差 **6.7787 s = 2×|dOff|** ≈ reviewer 实测 6.84~7.82 s）⇒ **恒定 ⇒ 排程错，非下行慢**；新增自证判据 `t0 ≥ 0`；`srv_wall_ms` ↔ `ply_wall_ms` ⇒ `downlinkMs` = **真实下行耗时**。
⇒ **② 根因分解**：新增 `decompose_sync_rootcause()` ⇒ **轴缺口与真实下行耗时分列** ⇒ **撤回 §27「全归 TTS」的单因归因**；★ **该数值已由 §29 修正为 7.184 s**（本节的 2.892 s **残缺**——当时三项恒 null）。
⇒ **③ 斜率只用有 TTS 的段**：新 **−0.46251 / r²=0.8819 / n=14** ≈ reviewer 重算 0.476（旧 0.248/0.375 **作废**）。
⇒ **④ 首段 3.5 s 一到就交出**（不裁缓冲 ⇒ 栅格不变 ⇒ 尾段不丢；两端口径**逐位相等**）。
⇒ **⑤ 录音时间轴不再压缩**（worklet 补静音样本 + `ConstantSourceNode`）；★ **该判据已由 §29 真实 e2e 实测确认（差 0.011 s）**。
⇒ **⑥ 时长比三口径分列**（`over_src_len`/`over_ws`/`speed_adjusted`）。
⇒ **⑦ PID 记录改正**（撤回 §27①「26736 已关」；**7896 属越权** ⇒ 新规则：点名以外一律停下请用户确认）。
⇒ **⑧ 自测九套全 0 FAIL**（含新 `test_ext036_review`）；★ 变异测试 `+ dOff` ⇒ **57 PASS/2 FAIL** ⇒ 守卫有效。
⇒ **⑨ ⛔ 当时未做**：真实三引擎 e2e 未跑完 ⇒ ①⑤ 待实测；★ **已由 §29 补测解除**。

## §29 —— EXT-036 补测：真实三引擎 e2e（①⑤ 确认）+ 客户端实测数据上报闭环（2026-11-04 20:03）

★ **全量明细见 `status/notes/sec29_ext036_e2e.md`**（逐条证据、探测原始值、产物清单、变异测试）

★ **闸门** `next_instruction.py --json` ⇒ **exit 1**（`already_executed`，latest=EXT-036，`last_ack=36`）
⇒ **不认领新编号**，`last_ack` **保持 EXT-036**；按 EXT-030 **TAKEOVER** 条款从死会话断点继续
（死会话 e2e PID 3449/48136 **已死**、遗留目录 `20261104_183902` **空**、ASR 锁 PID 2188 **已死**）

⇒ **① 下行耗时 P95 = 121 ms ≤ 300 ms ✅**（轮次 A `20261104_194608`；`downlinkMs`=[16,39,34,121,48,27,29,25,4,11] ms）
⇒ **轮次 B `20261104_195911` 独立复现**：**P95 = 35 ms**、**⑤ 差 0.011 s** ⇒ **两轮均达标** ⇒ §28 的「⛔ e2e 未跑完」**解除**
⇒ **⑤ |wav(81.952) − durationSec(81.999)| = 0.011 s ≤ 0.2 s ✅**（轮次 B：81.861 vs 81.910 ⇒ 同 0.011 s）
⇒ **★ 补测暴露的真缺陷（已修）**：客户端**测得到** `ply_wall_ms − srv_wall_ms`、`readyToStartSec`、`t0UpPlayerOffsetSec`，
但**只留在插件本地、从不上报服务端** ⇒ `margin.json` 的 `sync_rootcause` 里
`server_to_player_sec`/`downlink_latency_sec`/`player_queue_sec_mean` **三项恒 null**，
且 `non_tts_fixed_detail` 把 null **强转成 `0.0`**（**假数据**）
⇒ **修法（最小改动）**：客户端 `reportClientMetrics()`（在 `requestMarginDump` **之前**发 `client_metrics`）
＋ 服务端 `note_client_metrics()` / `client_metrics_summary()` / `_client_rootcause_kwargs()`
＋ **null 不再强转 0、不计入合计**（合计标 `non_tts_fixed_is_lower_bound`，明细列 `unmeasured`）
＋ `margin.json` 新增 `client_metrics` 键 ⇒ 修后实测 `unmeasured: []`。
⇒ **★ 非 TTS 固定项修正为 7.184 s**（§28② 的 **2.892 s 是残缺的**——当时三项恒 null）：
ASR **2.922** + 播放排队 **1.038** + **轴缺口 3.189** + 下行 **0.035** ⇒ 本轮 D=10 s **已足够吸收**
⇒ 残余滞后主要仍归 TTS 吞吐（`RTF_out` 实测 **0.8182**，刚好 ≤0.82，未达建议 0.75）。
⇒ **自测十套全 0 FAIL**：122/11/19/112/25/42/25/59/**39**（新 `test_ext036b_client_metrics`）/29（node 沙箱）
⇒ ★ **变异测试**：null 强转改回旧写法 ⇒ 新自测 **35 PASS / 4 FAIL** ⇒ 守卫有效（已还原）。
⇒ ⛔ **sync 有符号误差仍未达标**（P95 **9087 / 8727** ms，判据 ≤300 ms）⇒ **不写「同步已解决」**
⇒ ⛔ **时长比仍未追平**（`over_src_len` 0.46–1.08 vs reviewer 0.57–1.55，**同口径**）
⇒ ⛔ 未改引擎/其它模块文件／⛔ 未打包／⛔ 未推远程／⛔ `CORRECTIONS_EXT.md` 只读未改未入库
⇒ ⛔ **本轮未关闭任何进程**（只由 `machine_lock.hold()` 自动回收**已确认死亡**的 ASR 锁 PID 2188）

## §30 —— EXT-037 + EXT-038 交卷：丢 3.5 s 真缺陷已修（覆盖率 100%）+ 默认 D=20 s 实测（2026-11-05 11:29）

★ **全量明细见 `status/notes/sec30_ext037_038.md`**（逐条证据、原始字段、变异测试、产物清单）

★ **闸门** `next_instruction.py --json` ⇒ **exit 0**（`action=execute`，latest=**EXT-038**，`last_ack=36`）
⇒ 本轮**认领 EXT-038**（与 EXT-037 一起 ack）⇒ `last_ack` 推进到 **EXT-038**
（★ 开工时 `acquire ext` 返回 **TAKEOVER**（死会话 token=b1c6d479，last_beat 83 min 前）⇒ 按 EXT-030 条款
**从断点继续**，不从头重做：上一会话已把 EXT-037 ②③④、EXT-038 ② **写完但未提交** ⇒ 本轮接手**核对 + 补齐 + 提交**。）

### ① EXT-037 ②【BLOCKING】每段丢 3.5 s —— ✅ 已修，覆盖率 100%

⇒ **病根**：`ext/bridge.py` 每次调用 `split_first_segment_streaming(...)` 都把缓冲开头的 `[0, 3.5 s)`
当「已交付首段」切掉 ⇒ 旧实现**每段之后都丢 3.5 s**（60 s 素材丢约 24 s / 40%）。
⇒ **修法（最小改动）**：守卫 = **`_buf_base == 0`**（缓冲起点仍是会话起点 ⇒ 缓冲里**还留着**已交付的首段
需要对齐）＋ 处理完网格、**裁掉缓冲之后**才把 `_first_seg_cut` 清零
（⚠️ 提前清零 ⇒ 缓冲没被裁时 `_buf_base` 仍为 0 ⇒ 下一轮不再对齐 ⇒ 原始网格首段被**重复派发**）。
⇒ **配套**：`flush()` / `PipelineSession.flush()` 必须**跳过「已交付但仍在缓冲里」的前缀**
（新增 `_buf_delivered_prefix`）⇒ 否则尾段与首段**重叠**。
⇒ **★ 实测确认（run `20261105_112057`，D=20）**：**29 段 / 相邻段缺口全为 0.0 / 无重叠 / 总覆盖 0 → 105.791 s**
⇒ **段覆盖率 100% ✅**（对比：§29 旧轮次 8 段、每档 3.5 s 缺口；本轮 **14 个 TTS 段**，
与参照轮 `20261102_213515` 的 **14 段一致** ⇒ **丢段问题确实修好了**）
⇒ **翻译内容也已恢复**（§29 丢失的 6 处译文**全部在本轮逐段明细里出现** ⇒ 内容层面亦验证通过）。

### ② EXT-037 ③ —— sync_rootcause 口径重写 ✅

⇒ **固定项** = 上行(夹0) + ASR整段定稿 + **seg_len（等整段说完）** + 真实下行耗时
⇒ **结果项** = `player_queue`（排队）、`axis_gap`（**两端时钟的换算常数，不是延迟**）⇒ 单列到 `result_items_detail`
⇒ **★ 本轮实测值**：`non_tts_fixed_sec` = **7.690 s**
= 上行 **0.000** + ASR **3.388** + **seg_len 4.263** + 真实下行 **0.039**（`unmeasured: []` ⇒ **不是下界，是全量**）
⇒ `player_queue` 均值 **2.962** / max **12.170**、`axis_gap` **4.200** ⇒ **均在结果项，不进固定项**。
⇒ **★ D_needed 实测 = 33.652 s**（= P95(ready − t_start) **33.352** + 0.3）
⇒ **⚠️ 与 §29 的 2.892 s / 7.184 s 口径不同 ⇒ 旧值作废**（见 ⑤ 撤回条）。

### ③ EXT-037 ④ —— compare 时长比口径 ✅

⇒ **作废** `speed_adjusted`（`d_player × speed ÷ d_ws`）—— **`d_ws` 已是 WSOLA 变速后时长 ⇒ 再乘一次 speed 是重复校正**
⇒ **主口径 = `over_ws`**（d_player ÷ d_ws，**未经**变速校正）；reviewer 口径 `over_src_len` 保留
⇒ **`d_player` 主口径改为 `endedAt − actual`**（包络起止 ⇒ 不截尾部静音；旧能量检测口径保留为 fallback 并标 `d_player_caliber`）
⇒ **★ 本轮实测：`over_ws` = 0.9991 ~ 1.0008**（判据 1.00±0.02 ⇒ **✅ 全部合格**）
⇒ ⇒ **⚠️ 撤回 §28⑥/§29「时长比 0.46–1.08 未追平」** —— **那是分析器口径错误**，**不是播放器的问题**。

### ④ EXT-038 —— 默认 D=20 s + 真实 e2e 实测

⇒ **默认 D 改 20 s（插件与桥接两侧一致）**：`extension/popup.js`（`delaySec` 默认 + `readCfg()` 回落）、
`extension/popup.html`（`value="20"`）、`extension/sw.js`（`onInstalled` 默认）、
`extension/player.js`（`let delaySec = 20` + `boot()` 回落 `|| 20`）、`ext/bridge.py`（`--delay` 默认 `20.0`）、
`tools/*`（9 个 runner 的 `--delay` 默认）、`USER_GUIDE.md`（两处文案）
⇒ ★ **★ 关键修正：e2e 跑批里 D 出现在三处，服务端 `--delay`、插件 `chrome.storage.local.delaySec`、e2e 自身默认值
⇒ 只要漏改一处，**测出来的 sync 就是假的** ⇒ 已把三处**全部参数化** ＋ **插件侧写入后读回校验**（不符即报错）＋ **写完 reload**
（`boot()` 只在加载时读 storage）⇒ 新增自测 `test_06_e2e_delay_plumbing`（**12 项**）。

⇒ **★ 真实 e2e（run `20261105_112057`，60 s 素材，录音 104.469 s）**：

| 项 | 实测 | 判据 | 结论 |
|---|---|---|---|
| **段覆盖率** | **100%**（29 段 / 缺口全 0 / 总覆盖 0→105.791 s） | 100% | ✅ |
| 开头静音（ffmpeg 口径） | **20.11 s** | ≈D=20 | ✅（D 生效） |
| \|wav − durationSec\| | \|104.469 − 104.618\| = **0.149 s** | ≤ 0.2 s | ✅ |
| **有符号 sync P50 / P95** | **5978.7 / 16130.6 ms**（max 16198.3） | P95 ≤ 300 ms | ❌ **未达标** |
| 同步测量覆盖率 | **14/14（100%）** | 段数相等 | ✅ |
| `RTF_out` | **1.0562** | 只报告 | ⚠️ **>1**（饱和） |
| `tts_over_src` / `speech_over_src` | **1.3139 / 1.2440** | 只报告 | ⚠️ |
| lag 斜率（TTS-only 拟合） | **−0.4106**（r²=0.866，n=14） | 只报告 | ⚠️ **仍有积压** |
| 时长比 `over_ws` | **0.9991 ~ 1.0008** | 1.00±0.02 | ✅ |

⇒ **⛔ 未达标项按 EXT-038「不要自行改目标」处理**：sync P95 **16130.6 ms ≫ 300 ms** ⇒ **不写「同步已解决」**。

### ⑤ 撤回 §29 的两条结论（EXT-037 ③/④ 明确要求）

⇒ **撤回 §29「D=10 已足够吸收 / 非 TTS 固定项 7.184 s / tts_independent_lag −2.8 s」**：
旧口径把 `axis_gap`（换算常数）算进固定项 ⇒ 数值不可比；新口径下 `non_tts_fixed_sec` = **7.690 s**、
**结果项**（排队 2.962 / 轴缺口 4.200）单列 ⇒ 且 **`D_needed` 实测 33.652 s ≫ D=20 s** ⇒ **「D=20 足够」不成立**。
⇒ **撤回 §28⑥/§29「时长比 0.46–1.08 未追平」**（分析器口径错误 ⇒ 新口径 0.9991~1.0008 精确命中 1.00）。

### ⑥ 为什么 D=20 仍达不到 300 ms（实测归因，不臆造）

⇒ **`D_needed` = P95(ready − t_start) + 0.3 = 33.652 s**（本轮实测 `ready − t_start` 逐段
7.97/14.70/17.62/16.60/22.53/24.84/25.12/32.30/29.83/28.65/33.73/32.67/33.35/32.62）
⇒ **拆解**：逐段「就绪时刻 − 该段开始播放」**随段号单调增长**（7.97 → 33.73）
⇒ 这正是 EXT-037 ③ 说的**「等整段说完 + 管线耗时」**叠加
⇒ **根因 = 吞吐饱和**：`RTF_out` **1.0562 > 1**、且 `speech_over_src` **1.244**
⇒ `tts_over_src = RTF_out × speech_over_src = 1.3139 > 1`
⇒ **每 1 s 源音频要花 1.31 s 合成 ⇒ 队列必然越排越长 ⇒ 任何固定 D 都追不上**
⇒ **D_needed 会随素材长度继续增长**（P95 由**后段**决定）。
⇒ **归属**：**TTS 整句非流式 + `RTF_out > 1`** ⇒ **TTS 模块**（EXT-037 ③ 已如此归属）；
**译文变长**（`speech_over_src` 1.244）⇒ **MT/EXT 的译文长度控制**；
**段长与 ASR 整段定稿** ⇒ EXT/ASR（`seg_len` 4.263 s + ASR 3.388 s）。
⇒ ⇒ **★ 要达到 P95 ≤ 300 ms，需要 TTS 侧把 `RTF_out` 降到 ≲ 0.75（reviewer 建议目标）**
（且 `speech_over_src` 1.244 也要压到 ≈1.0），否则**光调 D 无解**。
⇒ ⇒ **请主会话转达 TTS 模块**：`RTF_out` 实测 **1.0562**（§29 的 0.8182 —— **那是丢段后只合成 39 s/60 s 的假值**，
**已作废**）⇒ **TTS 侧的真实目标是 `RTF_out ≤ 0.75`**（不是 ≤0.82）。

### ⑦ 自测（实测 rc）

`test_ext_selfcheck` **122**｜`test_echo_roundtrip` **11**｜`test_next_instruction` **19**｜
`test_p1_plumbing` **112**｜`test_ext010_pipeline` **25**｜`test_ext033_capture` **42**｜
`test_ext033_deliver` **25**｜`test_ext036_review` **64**｜`test_ext036b_client_metrics` **41**｜
★ **`test_ext037_seg_coverage` 53（新建）**｜node 沙箱：`ext028_player_harness` **29**、
`ext024_link_harness` **33**、`t5_t6_bounds_persist` **16** ⇒ **全部 0 FAIL**。

⇒ ★ **本轮修了两个「legacy 套件契约冲突」**（上一会话改了口径，但**没同步改旧断言** ⇒ 套件变红）：
① `test_ext036_review`：7 FAIL ⇒ 旧断言写死「固定项含 axis_gap/player_queue」+「三个时长比口径」
⇒ 已迁到**新契约**并**加强**（新增「明细里**不含** axis_gap/player_queue」「新增 seg_len 项」
→「结果项单列」「旧口径 speed_adjusted **不得**再出现」等守卫）。
② `test_ext036b_client_metrics`：4 FAIL ⇒ 同因 ⇒ 已迁到新契约并**加强**
（新增「axis_gap/player_queue 不在固定项」「结果项单列」「测不到的 seg_len 仍是 None」）。
⇒ ★ **注意：这是「改旧断言迁到新契约」，不是「放宽断言掩盖回归」** —— 原守卫（null 不冒充 0、
非 TTS 固定项 > D ⇒ 不能写成「全归 TTS」）**全部保留并加强**（合成数据改成段长 15 s > D=10
⇒ 保证「固定项 > D」这条守卫不会被新口径稀释掉）。

⇒ ★ **变异测试（`.tmp/_mutation_test.py`，4 个变异 + 1 个等价变异）**：
M1 把 axis_gap/player_queue 放回固定项 ⇒ **DETECTED**（3 套件共 4 FAIL）｜
M2 把 seg_len 从固定项删掉 ⇒ **DETECTED**（共 5 FAIL）｜
M3b 把**明细字典**里的 null 强转成 0.0 ⇒ **DETECTED**（1 FAIL）｜
M4 去掉「只切一次」守卫 ⇒ **DETECTED**（1 FAIL）｜
M3 把**合计公式**里的 null 强转成 0.0 ⇒ **MISSED（数值等价，属预期）**
⇒ 真守卫在**明细字典**（null 的呈现）而非合计公式 ⇒ **已如实记录，不虚报**。
⇒ **还原后三套件全 0 FAIL**（41/64/41）。

⇒ ★ **另修一个既有基线红**：`tests/ext024_link_harness.js` 在 **HEAD 版本就报**
`ReferenceError: dubDownlinkMs is not defined`（已用 `git show HEAD:` 复现确认 ⇒ **非本轮引入**）
⇒ 已给沙箱补桩（`dubDownlinkMs` / `dubReadyAt` / `audioCtx` / `noteDubScheduled` / `currentSessionId`）
⇒ **33 PASS / 0 FAIL**。

### ⑧ 产物清单（文件数 / mtime / 字节数）

- `.tmp/ext033_e2e/20261105_112057/` ⇒ **12 项**（11 文件 + 1 目录）：
  `dub_player.wav` **10 029 100 B**、`dub_player.webm` **927 795 B**、`margin.json` **60 056 B**、
  `metrics.json` **46 425 B**、`dub_sync.json` **10 738 B**、`bridge.log` **12 024 B**、
  `player.png` **24 404 B**、`record_stop.json` **291 B**、`ext033_compare.json` **20 335 B**、
  `ext033_compare.md` **4 793 B**、`audio_dump/`（目录）—— mtime 2026-11-05 11:26~11:28。
- 轮次摘要 `.tmp/ext033_e2e/summary_20261105_112057.json`（`delay_sec=20` / `plugin_delay_sec=20` / `rc=0`）。
- e2e 日志 `.tmp/ext033_e2e/run_d20.log`。
- 新增文档 `status/notes/sec30_ext037_038.md`（本节全量明细）。

### ⑨ 交 reviewer 的清单（EXT-038 ④）

⇒ **player 录音 wav**：`.tmp/ext033_e2e/20261105_112057/dub_player.wav`（**10 029 100 B**，104.469 s）
⇒ **每段译文（含 json）**：`.tmp/ext033_e2e/20261105_112057/ext033_compare.json`
（`segments[]` 含 `seg_id` / 源 / 译 / `signed_err_ms` / 时长比）
＋ 逐段明细表 `.tmp/ext033_e2e/20261105_112057/ext033_compare.md`
⇒ ⛔ **质量判定由 reviewer 用 MiniMax 回转写，本模块不自行调用**（铁律）。

### ⑩ 明确未做 / 不宣称

⇒ ⛔ **sync P95 16130.6 ms 未达标**（判据 ≤300 ms）⇒ **不写「同步已解决」**、**不自行放宽目标**。
⇒ ⛔ **未打包**（EXT-031/APP-057；★ 按用户规则**不主动打包**）。
⇒ ⛔ **未改引擎文件 / 未改其它模块文件 / 未推远程**。
⇒ ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`git check-ignore` 命中 `.gitignore`）。
⇒ ⛔ **本轮未关闭任何进程**；MACHINE_LOCK 由 `machine_lock.hold()` 正常排队获取与释放
（等 TTS 模块 PID 7592 释放后才起跑 ⇒ **未抢他人活锁**）。
⇒ ⛔ **EXT-028 待用户抽听、V2.0 暂不放行**（旧结论仍在 §25）；⛔ **克隆音色仍不可用**（依赖 ASR-013）。

### `last_ack`

**EXT-038** —— 本轮**认领并执行**（闸门 exit 0）⇒ `last_ack` 由 EXT-036 推进到 **EXT-038**。
