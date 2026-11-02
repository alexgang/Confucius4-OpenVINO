# §26 —— EXT-033 交卷：真实三引擎 e2e + 三个真缺陷修复（2026-11-02）

> 本节是 EXT-033（[BLOCKING] 2026-11-02 09:22）的全量明细。
> 指令原文见 `status/CORRECTIONS_EXT.md`（**reviewer 独占、只读、全程未修改、未入库**）。

---

## 0. 本轮是怎么开始的（租约接管链）

| 会话 | token | 起止 | 结局 |
|---|---|---|---|
| 第 1 次 | `c09ec63e` | 09:32 起 | **中途死亡**（心跳停 43 min） |
| 第 2 次 | `9ea5f801` | 10:21 起 | **中途死亡**（心跳停 67 min，note「e2e 完成(WAV 完整 104.3s)，跑 analyze 生成对比与交付」） |
| 第 3 次（本轮） | `4ffeaecb` | 13:26 起 | **进行中** |

⇒ 每一次都是 `session_lease.py acquire ext` 返回 **TAKEOVER** ⇒ 按指令读前会话 note + `STATUS_EXT.md` + `EXEC_LOG.md` + 磁盘产物 ⇒ **从断点续做**，不重启。
⇒ **本轮接手的磁盘产物**（前会话已写、未提交）：
`extension/player.js`（改）、`extension/manifest.json`（改）、`extension/dub-pcm-worklet.js`（新）、
`tests/smoke/browser_harness.py`（改）、`tests/smoke/ext033_e2e.py`（新）、
`tests/smoke/ext033_analyze.py`（新）、`tests/smoke/probe_ext033_{action,capture,tabconsume}.py`（新）、
`tests/test_ext033_capture.py`（新）、`tests/test_ext033_deliver.py`（新）。

---

## 1. 前会话已完成的真实三引擎 e2e（run `20261102_121431`）

★ **这是本轮最重要的输入**（本轮没有重跑这一轮；见 §3 重跑原因）。

| 项 | 实测值 | 源 |
|---|---|---|
| 引擎 | ASR=R2T2 INT8@GPU.0 → MT=Hy-MT2 INT8@GPU.0 → TTS=Qwen3-TTS@NPU | `bridge.log` |
| 模型加载 | ASR 25.0 s / MT 2.2 s / TTS 14.9 s | `bridge.log` |
| 输入方式 | **页面元素**（`createMediaElementSource` + `MediaStreamDestination`）⇒ **不是整机声** | `metrics.json` → `uplink.captureMode = "element"` |
| 素材 | 英文 SPE `test_en_60s.wav`（0–60 s） | `summary_*.json` |
| 上行健康 | `frameCount=4985`、`gaps=0`、`maxAbsSkewAudioMs=1.08`（音频时钟口径） | `metrics.json` → `uplink` |
| TTS 段数 | **13 段**（`link.ttsSegments=13`，`asrSegments=13`，`mtSegments=13`） | `metrics.json` → `link` |
| player 录音 | webm **856 053 B** / WAV **10 012 716 B**（48 kHz / 5 006 336 样本 / **104.299 s**） | `dub_player.webm` / `dub_player.wav` |
| 录音完整性 | `stopDubRecordingAsync()` 等 `onstop` + PCM dump ⇒ **不截断** | `record_stop.json` |

### ❌ 但**实测未达标**（这是 EXT-032 之后第一次真跑，数字如下）

| 项 | 实测 | 判据 | 结果 |
|---|---|---|---|
| 录音时长 | **104.299 s** | ≥ 75 s | ✅ |
| 开头静音 | **26.58 s** | ≤ 15 s | ❌ |
| sync_err（有符号）P50 / P95 / max | **28650.0 / 29537.8 / 29537.8 ms** | \|P95\| ≤ 300 ms | ❌ |
| 段数 / 已对齐 / 未对齐 | 7 / 6 / 1 | 对齐峰 ≥ 0.6 | 1 段未对齐 |
| 时长比（player÷(b)，变速校正） | **0.6825 ~ 1.4851** | 1.00 ± 0.02 | ❌ |
| 源语言全为英文 | True | EXT-033 E | ✅ |
| `metrics.schedClamped` | **13** | — | ⚠️ **13 段全被钳成「立即播」** |

---

## 2. ★ 本轮定位并修复的**三个真缺陷**（不是推测，全部有实测证据）

### ★★★ 缺陷 1（EXT-033 D 的根因）：`t0` **跨时钟域** —— 上行域算、player 域消费

**证据**：
- `metrics.t0Sec = -0.0197`（`t0Axis="audio_clock"`）
- `dub_sync.json` → 首段 `requested = 9.980 s`（= t0 + t_start 0 + D 10），**实测 actual = 29.927 s** ⇒ `signedErrMs = +19947`
- `metrics.schedClamped = 13` ⇒ **13 段全部** `planned < audioCtx.currentTime + 0.005` ⇒ 被钳成「立即播」
- ⇒ 有符号误差**恒为正**（19.9 ~ 29.5 s），**量不出「早播」** ⇒ 正是 EXT-032 批评的「口径不是同步误差」

**根因**：
`d.audioFrame16` 来自 **上行 AudioContext**（`upState.ac`，`extension/player.js:1364` 创建），
而 `planned` / `src.start(when)` / onset 的 `at` 全在 **player AudioContext**（`audioCtx`，`extension/player.js:2582` 创建）的时间轴上。
**两个 AudioContext 的原点互相独立**（各自从 0 开始计时）⇒ 直接把上行域的 t0 当 player 域的时刻 ⇒ **系统性偏差**。

**修法**（`extension/player.js`）：
1. 在 **player 域**内测 uplink↔player 原点差 `Δ = upState.ac.currentTime − audioCtx.currentTime`（两个 context 都 running 时采样，取前 60 帧中位数）；
2. `t0 = t0_up + Δ`（`t0_up = off16 / 16000` 不变）；
3. **保留** `t0UpSec` / `t0UpPlayerOffsetSec` 到 `metrics` ⇒ **换算前后可自证**；
4. `requested = t0 + t_start + D` 的口径**一字未改** ⇒ 审阅者要求的算式不变。

**自测**：`tests/test_ext033_capture.py` 新增 2 条断言（换算存在 / 换算前原值保留）。

### ★★★ 缺陷 2（设备互斥**从来没生效过**）：`_caption_app_running()` **恒返回 False**

**证据**：
- 旧实现 `import psutil` → **App 自带的 python 里没有 psutil**（EXT-017② 注释里早已记过此事）
  ⇒ `except Exception: return False` ⇒ **恒 False** ⇒ 互斥形同虚设
- 旧实现还只匹配字面量 `"live_caption"`（**带下划线**），而本机跑的是 `Confucius4_LiveCaption_v2.1`（**无下划线**）⇒ **双重漏检**
- 实测：本轮 e2e 跑的同时，**实时字幕 App（PID 4896，8765/8766 监听中）正在跑** ⇒ 两个进程**同时抢 GPU.0 + NPU**

**修法**（`ext/bridge.py`）：
1. **不依赖 psutil** ⇒ 用 Windows 自带 `wmic` → `Get-CimInstance Win32_Process` → `tasklist` 三级降级；
2. 匹配 **App 的真实入口**（`bridge_launcher.py` / `live_caption_app.py`）⇒ 不因「命令行里提到该路径」而误报；
3. **拿不到进程列表 ⇒ 保守按「可能在跑」处理**（探测失败 ≠ 没在跑）。

**实测验证**（App 自带 python）：
```
n=346 耗时 0.56 s
4896 HIT= True  | "C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1\python\pythonw.exe" ...\ext\bridge\bridge_launcher.py
⇒ caption_app_running = True      （修前恒 False）
```
误报检查：同批进程里 3 个「命令行含 LiveCaption 路径」的非 App 进程（timeout.exe / python -c）**均未命中** ✅

**自测**：`tests/test_ext033_capture.py` 新增 3 条断言（不依赖 psutil〔**用 AST 检查，避开注释干扰**〕/ 按真实入口匹配 / 探测失败保守处理）。

### ★★★ 缺陷 3（交付分析器自带 bug）：`ext033_analyze.py` 的 `rms` **局部变量遮蔽**

**证据**：`tests/test_ext033_deliver.py` 直接崩：
```
UnboundLocalError: cannot access local variable 'rms' where it is not associated with a value
  ext033_analyze.py:166: if dbfs(rms(x[i:i + step])) > thr_db:
```
**根因**：`voiced_span()` 的 numpy 分支里 `rms = _np.sqrt(...)` ⇒ Python 把整个函数里的 `rms` 判成**局部变量**
⇒ fallback 分支（无 numpy 时）调用**全局** `rms(...)` 必然 `UnboundLocalError`。

**修法**：numpy 分支局部变量改名 `_rms_blocks`。

### ★ 附带修的两处（同样是真问题）
- `tests/test_ext_selfcheck.py`：用 psutil 找「存活 PID 对照」⇒ **在真实运行环境（App python）里恒 FAIL（假失败）**
  ⇒ 改用被测代码自己的 `R._pid_alive`（有 ctypes 兜底）⇒ **106 PASS / 0 FAIL**
- `ext/bridge.py` docstring 里的 `\p` 转义 ⇒ `SyntaxWarning`（本轮顺手清掉）

---

## 3. 本轮的重跑（验证缺陷 1 的修复）

- 前会话那一轮（`20261102_121431`）**没有修 t0** ⇒ 数字是**修前**的 ⇒ 必须重跑才能证明修复有效。
- 本轮重跑：`tests/smoke/ext033_e2e.py --real`，**持共享机器锁**（`ext 5100 2026-11-02 13:59:36`），
  PID **15540** 已按 EXT-030 ③ 用 `session_lease.py addpid ext 4ffeaecb 15540` 注册。
- ⚠️ **重跑时实时字幕 App（PID 4896）仍在跑** ⇒ 设备仍是**争抢**状态 ⇒ 这正好是**最坏情形**；
  若修复后 sync 仍不达标，则**瓶颈在引擎吞吐**，不在 t0 口径 ⇒ 结论要写进 STATUS 交主会话。

---

## 4. 剩余滞后（超出 EXT 模块职责范围的部分）

`margin.json`（run `20261102_121431`）实测分解：

| 量 | 值 | 含义 |
|---|---|---|
| `margin_summary.p50`（排程余量） | **−14.387 s** | 这句**赶不上**自己的播放时刻 |
| `margin_summary.max_lag_sec` | **25.72 s** | 最大滞后 |
| `lag_growth_slope_sec_per_sec` | **0.3146** | 滞后**随时间累积** ⇒ 管线吞吐 < 1 |
| `feed_lag`（音频到达服务端） | **全为负**（mean −5.85 s） | 音频**准时**到 ⇒ **不是上行/反压问题** |
| `intrinsic_lag`（引擎慢） | mean **+2.27 s**，10 段为正 | **引擎侧**赶不上 |
| ASR RTF | **0.773** | OK |
| MT RTF | **0.193** | OK |
| **TTS RTF** | **1.231** | ❌ **> 1 ⇒ 结构上不可能实时** |

⇒ **GPU 侧（ASR+MT）合计 75.3 s / 60 s 音频；TTS 侧 73.8 s / 60 s 音频** ⇒ 两侧都 > 60 s。
⇒ ★ **TTS 提速是 EXT 模块改不动的**（引擎文件属其它模块，铁律禁止本模块改动）
⇒ 按指令要求：**把「需要改引擎」写进 `STATUS_EXT.md` 交主会话转达**，本模块**不碰引擎**。

---

## 5. 本轮改动的文件（**仅本模块**）

| 文件 | 动作 | 说明 |
|---|---|---|
| `extension/player.js` | 改 | ★ 缺陷 1：`t0` 换算到 player 域（`t0UpSec` / `t0UpPlayerOffsetSec` 上报） |
| `ext/bridge.py` | 改 | ★ 缺陷 2：设备互斥去 psutil 化 + 按 App 真实入口匹配 + 探测失败保守 |
| `tests/smoke/ext033_analyze.py` | 改 | ★ 缺陷 3：`rms` 局部变量遮蔽 |
| `tests/test_ext033_capture.py` | 改 | 新增 5 条断言（t0 换算 ×2 / 互斥 ×3） |
| `tests/test_ext_selfcheck.py` | 改 | 自测不再依赖 psutil（真实运行环境可用） |
| `status/notes/sec26_ext033.md` | 新建 | 本文件 |
| `status/STATUS_EXT.md` | 改 | `last_ack` → EXT-033 + 新增 §26 |
| `status/EXEC_LOG.md` | 改 | 追加本轮记录 |

**未改 / 未碰**：`status/CORRECTIONS_EXT.md`（只读）、任何引擎文件、任何其它模块的文件、`session_lease.py`。
