# §25 EXT-032 —— 「EXT-028 只修了代码，没有交实录」的逐条交卷

> 全量明细（本文件）。STATUS 精简版只留结论 + 指针。
> 写作规则见 EXT-016：明细下沉 notes，STATUS 只放结论/数字/链接。

## §25.0 本轮身份与依据

- **指令**：EXT-032 [BLOCKING] 2026-11-01 20:30 ——「EXT-028 只修了代码，没有交实录；
  "不构成打包阻塞"的说法不成立」。闸门 `tools/next_instruction.py --json` **exit 0**
  （`action=execute` / latest=EXT-032 / `last_ack`=31）。
- **本轮起点**：上一会话（token=`81d2924a`，末次心跳 **11-01 22:27:46**）在
  「EXT-032 证据落盘 + STATUS 撤回 + 提交收尾」时**死掉** ⇒ 租约 **TAKEOVER**
  （stale，135 min 无心跳）。**从断点继续**，未重做。
- **断点已落盘的成果**（上一会话写的，本轮接手）：
  - `tests/smoke/ext032_audio_compare.py`（**24 228 B**，mtime **11-01 21:56**）——
    三份音频逐段对比工具（纯信号处理 + 浏览器 WebAudio 解码，零第三方依赖）。
  - `.tmp/ext028_029_e2e/20261101_155037_13840/A_off/ext032_compare.{json,md}`
    ——它已经对**既有轮次**跑过一次对比。
- **本轮新增**：`tests/smoke/ext032_deliver.py`（成因分解 + 交付物打包）、
  `tests/test_ext032_deliver.py`（29 项自测）、交付目录
  `C:\Users\Trekker-PTL\shared\ext_listen\ext032_20261102_010022\`。

## §25.1 指令 5 条逐条交卷

| EXT-032 要求 | 本轮状态 | 证据 |
|---|---|---|
| ① 走 **tabCapture 生产路径**、Edge 播英文 SPE 60 s、只抓页面元素音频、录 player 端 | ⛔ **自动化拿不到 tabCapture ⇒ 只能由用户手势做** | `tests/smoke/probe_tabcapture.py` 实测 **12 次尝试全失败**（`.tmp/probe_tabcapture/result.json`）：`getMediaStreamId` 回空 id、`capture` 回 null stream、`capture({targetTabId})` 直接报 **"Unexpected property: 'targetTabId'"**（该属性只属于 `getMediaStreamId`）。player 侧原文：**"Extension has not been invoked for the current page (see activeTab permission)."** ⇒ 需真实用户点扩展图标（EXT-022 已定②） |
| ② 每段三份音频逐段对比（时长比 / 互相关峰与偏移 / SNR），时长比 **1.00±0.02** | ✅ **已交**（6 段逐段表） | `ext032_compare.md`；**变速校正比 6/6 合格（1.000–1.019）**；原始比 5/6（唯一不合格段是 speed=1.1899 的 WSOLA 变速段，原始比 0.8564 = 1/1.1899，**与采样率无关**） |
| ③ 讲清静音成因 + 给修复后数据（开口静音 / 最长静音 / 首段配音到达 / sync_err p50·p95） | ✅ **已交**（加法式分解，逐条带证据） | 见 §25.2 |
| ④ 新建 `shared/ext_listen/ext032_<时间>/`，放 player 录音 + README（每段起止+译文）+ 对比表 | ✅ **已落盘** | `C:\Users\Trekker-PTL\shared\ext_listen\ext032_20261102_010022\`（**5 文件**） |
| ⑤ STATUS 撤回「EXT-028 不构成打包阻塞」，改成「EXT-028 待用户抽听」 | ✅ **已撤回** | STATUS §25 + 「未完成纠偏清单」EXT-028 行 |

## §25.2 指令③：开口静音的成因分解（**不是**一句推测，是可核对的加法）

> 数据源：轮次 `.tmp/ext028_029_e2e/20261101_155037_13840/A_off/`
> （`dub_player.webm` / `bridge.log` / `margin.json` / `metrics.json` / `audio_dump/`）

| 项 | 实测 | 来源 |
|---|---|---|
| 录音总长 | **33.840 s** @ 16 000 Hz | `ext032_compare.json` → `player_duration_sec` |
| **录音开头静音**（到首段配音） | **29.300 s** | 同上 `player_leading_silence_sec` |
| **最长静音段** | **29.250 s** | 同上 `player_longest_silence_sec` |
| 总静音 | 30.000 s | 同上 `player_total_silence_sec` |
| **首段配音到达**（上行时间轴） | **t_start = 22.050 s**（段 `seg_90879187_352800`，原文 `and you know` → 译文 `你知道的`） | `bridge.log` 段级日志 |
| **sync_err p50 / p95** | **0.0 / 0.0 ms**（max 0.0，`n_over_12000ms`=0） | `margin.json` → `per_segment[].deadline_margin_sec`，口径同 `tools/p1_pipeline.py` 的 `sync_err_ms` |
| 计划缓冲 D | **10.0 s** | `metrics.json` → `delaySec`（EXT-009 约定） |

**分解（残差可核）**：

```
可解释开口静音 = 首语音位置 + D = 22.050 + 10.000 = 32.050 s
实测开口静音                              = 29.300 s
残差 = 实测 − 可解释                      = −2.750 s   （≈ player 端时钟与桥接 t0 的偏移）
```

**为什么「首语音位置」是 22.05 s 而不是 0**（这一条最关键）：

- 上行按 **3.15 s** 切窗；**首语音之前有 7 窗 ASR 为空**（`ASR='—'`）⇒ 那些窗没有配音可播。
- ★ **不是素材的问题**：实测素材 `test_en_60s.wav`（16 kHz 单声道 60.0 s）**每 3.15 s 窗都有语音**
  —— RMS **−26.65 / −27.07 / −27.04 / −31.81 / −30.01 / −27.82 / −32.06 dBFS …**，
  **20/20 窗全部有语音，首个语音窗在 t=0.0 s**（落盘于 `ext032_deliver.json`
  → `silence.source_windows_rms_dbfs` / `source_windows_with_speech=20`）。
- ★ **也不是 ASR 的问题**：同一轮里 ASR 在 22.05 / 25.20 / 40.95 s 三窗**正常识别出英文**并翻译
  （`and you know`→`你知道的`、`because I don't decline`→`因为我不拒绝`、
  `So just got to maintain the`→`所以只需要保持现状即可`）⇒ **英译中链路本身是通的**。
- ⇒ **只能是抓流侧没把标签页音频送上来**（见 §25.3）。

## §25.3 ★ 为什么抓的是整机而不是标签页（EXT-032① 的直接证据）

| 证据 | 内容 |
|---|---|
| `metrics.json` → `captureMode` | **`getDisplayMedia`**（≠ `tabCapture`） |
| `metrics.json` → `tabCaptureError` | **"Extension has not been invoked for the current page (see activeTab permission). Chrome pages cannot be captured."** |
| `metrics.json` → `captureModeDetail` | `getDisplayMedia` |
| **player 截图** `player_60s.png`（114 761 B） | 画的是**整个桌面**：可见终端窗口、资源管理器、GPU 监控面板、任务栏 ⇒ 抓的是**整机屏幕**（系统声音混音），不是标签页 |
| **末尾 3 段是中文**（`你每天吃吃吃吃睡，` / `增加太多的情绪，得想办法释放出来。` / `你每天吃吃吃吃睡`） | 出现在 **t_start = 66.520 / 69.850 / 73.010 s** ⇒ **已超出英文 SPE 的 60.0 s 长度** ⇒ 只可能来自**实时字幕 App 的系统声音混音**（那台机器当时 App 在跑），不是素材 |
| `probe_tabcapture.py`（12 次尝试） | 自动化**拿不到** tabCapture ⇒ 只能退到整机兜底 |

⇒ **EXT-028 的验收项（"只抓页面元素的音频" + "英文 SPE"）在自动化下**不可能**满足**；
EXT-027① 的结论（「必须 tabCapture 生产路径」）**成立且已被量化**。

## §25.4 ★ 采样率修复是否真的生效（EXT-032② 的核心判据）

| 指标 | 实测 | 判定 |
|---|---|---|
| 原始时长比（桥接下发 ÷ TTS 原始）min/mean/max | **0.8564 / 0.9761 / 1.0000** | 5/6 合格（区间 1.00±0.02） |
| **变速校正时长比**（原始比 × speed，抵消 WSOLA 变速）min/max | **1.0000 / 1.0190** | **6/6 合格** |
| 互相关峰（TTS 原始 vs 桥接下发 PCM） | **1.0000**（5 段）／0.1410（唯一变速段） | 5/6 合格 |
| SNR | 中位 **120.0 dB**（5 段）／−2.01 dB（唯一变速段） | 5/6 合格 |
| player 录音按内容对齐落点 | 3/6 对齐成功 | 见下 |

- **唯一不合格的那一段**（`seg_90879187_1117600`）是 **speed=1.1899** 的自适应变速段：
  原始比 **0.8564 ≈ 1/1.1899** ⇒ 这是 **WSOLA 变速**（EXT-009）造成的，
  **不是采样率问题**；变速校正后 **1.0190** 落在 1.00±0.02 内 ✅。
- ★ **采样率修复的直接证据**：`metrics.json` → `pcmRateLast = 24000`、
  **`pcmRateAssumed = 0`** ⇒ player 用的是**服务端声明的 24000 Hz**
  （`resolvePcmSampleRate()`），**没有**再按 16000 Hz 重建 24 kHz 波形
  ⇒ 「1.5× 语速 + 升调」这个根因**已消除**。
- ⚠️ **诚实标注**：player 录音对齐只成功 3/6 ⇒ 播放端与桥接端的**时间轴对齐**
  还有 3 段没对上（互相关峰 0.04–0.33）⇒ **不能宣称「player 端逐段完全对齐」**。

## §25.5 本轮新增的代码（最小、范围可控）

| 文件 | 大小 | 说明 |
|---|---|---|
| `tests/smoke/ext032_audio_compare.py` | 24 228 B | ★ **上一会话写的**（本轮接手，未改其算法），三份音频逐段对比 |
| `tests/smoke/ext032_deliver.py` | 本轮新建 | 成因分解（`analyze_silence_cause`）+ sync_err 统计 + 交付物打包（`build_delivery`） |
| `tests/test_ext032_deliver.py` | 本轮新建 | **29 PASS / 0 FAIL**，含 4 组反证 |

- ★ **没有改任何引擎文件**（`ext/` 一行未动）、**没有改 `extension/`**（采样率修复上一轮已在）。
- ★ **没有改 `shared/tools/session_lease.py`**（reviewer 部署，只读使用）。
- ★ **没有改 `status/CORRECTIONS_EXT.md`**（reviewer 独占、只读、未入库）。

## §25.6 自测（实测 rc）

| 套件 | 结果 | rc |
|---|---|---|
| `tests/test_ext_selfcheck.py`（EXT-032 明文要求） | **106 PASS / 0 FAIL** | 0 |
| `tests/test_echo_roundtrip.py`（明文要求） | **11 PASS / 0 FAIL** | 0 |
| `tests/test_next_instruction.py`（明文要求） | **19 PASS / 0 FAIL** | 0 |
| `tests/test_ext032_deliver.py`（本轮新增） | **29 PASS / 0 FAIL** | 0 |

★ **反证**（自测要能区分真通过/假通过）：
① 把 sync_err 公式改成「恒 0」⇒ 迟到 30 s 的合成段**必须**不再被报出（已断言）；
② 把 D（播放缓冲）从公式里去掉 ⇒ 分解结果**必须**改变（已断言）；
③ 把译文清空 ⇒ README 里那一格**必须**变空（证明 README 是渲染出来的，不是模板硬编码）；
④ 段级日志的 `has_text` 恒置 True ⇒ 「无语音窗」判定**必须**翻转。

## §25.7 交付物清单（**实测**文件数 / mtime / 字节数）

`C:\Users\Trekker-PTL\shared\ext_listen\ext032_20261102_010022\`（**5 个文件**）

| 文件 | 字节数 | mtime | 内容 |
|---|---|---|---|
| `dub_player.webm` | **86 970** | 2026-11-02 01:01 | player 端录音**原样拷贝**（不转码 ⇒ 保留原始证据） |
| `README.md` | **4 102** | 2026-11-02 01:01 | 每段起止时间 + 原文 + 译文 + 三份音频指标 + 静音画像 + 5 条口径说明 |
| `ext032_compare.md` | **1 985** | 2026-11-02 01:01 | 逐段对比表（人看的） |
| `ext032_compare.json` | **6 266** | 2026-11-02 01:01 | 逐段对比表（机器读的） |
| `ext032_deliver.json` | **10 772** | 2026-11-02 01:01 | 全部数字（静音画像 / sync_err / 素材窗 RMS / 段级明细） |

## §25.8 ⛔ 明确未做 / 不宣称

- ⛔ **tabCapture 生产路径未实测**（自动化拿不到 ⇒ **必须用户按
  `C:\Users\Trekker-PTL\shared\ext_listen\v21\HOWTO.txt`（App 模块 APP-059 已写）
  亲手做一次**：关字幕 App → 起桥接 → Edge 加载扩展 → 播英文 SPE → 点扩展「开始」
  → player 点「开始捕获」→ 跑满 60 s → 回扩展点「停止并收尾」）。
- ⛔ **EXT-028 仍未通过**（用户抽听未做）⇒ **撤回**「不构成打包阻塞」，改为
  **「EXT-028 待用户抽听」** ⇒ **V2.0 插件部分暂不放行**。
- ⛔ 本轮**没有**跑新的真实三引擎 e2e：00:40–00:48 机器锁被 **asr** 模块
  （`asr040-spk-change-point-diag`, PID 6224）持有；**00:48 锁释放后**
  **实时字幕 App 在运行**（PID 14712 `live_caption_app.py` + PID 22400 `tts_worker --device NPU`）
  ⇒ 按互斥铁律 `ext.bridge` 会**拒绝启动**（`_caption_app_running()` → rc=3），
  ⇒ **不抢设备、不打断用户的 App** ⇒ 本轮**没有**起第二个桥接实例。
- ⛔ **player 录音逐段对齐只 3/6** ⇒ 不宣称播放端完全对齐。
- ⛔ **未打包**（EXT-031：打包由 App 线程 APP-057 执行）、**未推远程**、**未改引擎**。

## §25.9 ★ 给 reviewer 的 3 条明确请求

1. **EXT-028 的最后一环需要用户手势**：请把 `shared/ext_listen/v21/HOWTO.txt`
   转给用户照做一次（那是 App 模块写的 6 步流程）；用户跑完后，
   `tests/smoke/ext032_deliver.py <该轮目录>` 一条命令即可产出同规格交付物。
2. **V2.0 插件部分先别放行**：EXT-028 = 「待用户抽听」（本轮已撤回旧结论）。
3. **本轮没有新的真实引擎轮次**（设备互斥）⇒ §25 的数据来自 **11-01 15:52 那一轮**
   （**修复后**代码）。若 reviewer 要求「修复后 + tabCapture 生产路径」的**同一轮**证据，
   需要在**实时字幕 App 关闭**且**用户手势**的窗口里再跑一轮。

---

<!-- 以下为 STATUS_EXT.md 中 §25 的原文（2026-11-02 本轮下沉，逐字保留以存史） -->

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

