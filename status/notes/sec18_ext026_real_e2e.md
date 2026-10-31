# §18 EXT-026 真实三引擎端到端冒烟（实测记录）

> ★ 本文件**据实重写**。上一版本（被中断那一轮）的数字（7 段 / 514 982 B /
> 18:10~18:12 等）**已作废**，以本文件的实测数字为准。
>
> 生成时间：2026-10-31（本轮实测）
> 数据来源：
> - `.tmp/ext026_e2e/`（player getDisplayMedia **兜底路径**）
> - `.tmp/ext026_prodpath/`（popup → tabCapture → offscreen → SW → player **生产路径**）
> - `%LOCALAPPDATA%\LiveDubEXT\tts_exec_devices.json`（EXT-023 执行设备落盘）

---

## 1. 为什么跑两轮

EXT-026 指令第 2 条指定的是「popup 点开始 → player 点开始捕获」的路径，
即 **生产路径**（上行在 offscreen 文档里，服务端把 tts 下发给 offscreen，
offscreen 再经 SW 广播给 player —— 即 EXT-024 A 新加的转发环节）。

但**生产路径在自动化下拿不到 tabCapture**：`chrome.tabCapture.getMediaStreamId()`
要求「Extension has not been invoked for the current page (see activeTab
permission)」⇒ 必须**用户点一下工具栏图标**（真实手势）。
自动化是直接 `open_ext_page("popup.html")`（把 popup 当普通页打开）
⇒ **不算**「对当前页面的 invoke」⇒ 必然降级到 `getDisplayMedia`。

实测错误原文（已落盘在 `summary.json` 的 `capture_error`）：

```
Extension has not been invoked for the current page (see activeTab permission).
Chrome pages cannot be captured.
```

⇒ 因此**两轮都跑**：
- **A 轮（`.tmp/ext026_e2e/`）**：player 页直接 `getDisplayMedia` 兜底路径，
  60 s 采集 ⇒ 验证「服务端产段 → tts 下发 → player 播放 → 录音非静音」这条主链；
- **B 轮（`.tmp/ext026_prodpath/`）**：**生产路径**（popup → SW → offscreen →
  SW relay → player），60 s 采集 ⇒ 验证 EXT-024 A 的转发链在真实三引擎上通。

★ 两轮的抓流方式**都如实上报为 `getDisplayMedia`**（metrics.captureMode），
  **没有**谎报成 `tabCapture`。

---

## 2. A 轮：兜底路径（`.tmp/ext026_e2e/`）

- 起止：**2026-10-31 20:30:56 → 20:34:29**（采集 60 s）
- 页面：`http://127.0.0.1:52539/index.html`
- 素材：`confucius4-openvino\live_caption\test_en_60s.wav`（英文 60 s，**只读引用**）

### 2.1 段级日志（源 `.tmp/ext026_e2e/bridge.log`）

| 指标 | 实测值 |
|---|---|
| 段级日志行数 | **9** |
| 「下发到」含 player 的段数 | **9 / 9**（全部 `下发到=player,uplink`） |
| 有 TTS 音频的段数 | **7** |
| 空段数（按 EXT-010 设计仍下发） | **2** |
| 10048 端口占用 | **0 次** |
| 「不顶替」日志行 | 2 次（EXT-024 设计：player 先连 ⇒ uplink 连上时打印；`producer_session` 仍指向真会话） |
| TTS 语音总时长 | **43.84 s**（各段 6.96 / 3.92 / 5.76 / 8.0 / 6.08 / 8.32 / 4.8） |

实测段 id 形态：`seg_55035942_0` / `seg_55035942_194400` / `seg_55035942_392000` …
⇒ **会话前缀已生效**（EXT-026 第 5 条的 `seenDubIds` 撞号缺陷已修）。

### 2.2 hello_ack（源 `.tmp/ext026_e2e/hello_ack.json`，479 B）

```json
{ "kind": "hello_ack", "delay_sec": 10, "sample_rate": 16000,
  "mode": "real", "engines_ready": true, "pipeline": true,
  "session_id": "55035942" }
```

⇒ **mode=real / engines_ready=true / pipeline=true** 三项均达标。

### 2.3 metrics（源 `.tmp/ext026_e2e/metrics.json`，1 423 B）

| 字段 | 实测值 |
|---|---|
| dubDelivered | 9 |
| echoRecv | 9 |
| dubDup | 9 |
| dubDupsCleared | 0 |
| asrSegments / mtSegments / ttsSegments | **7 / 7 / 7** |
| schedClamped | 7 |
| lagSec | 12.7046 |
| audioRecvSec | 151.89225 |
| captureMode | getDisplayMedia |
| uplink.running / wsOpen | true / true |
| uplink.maxAbsSkewMs / skewP95 | 32.4958 / 28.6833 |
| uplink.gaps | 0 |

> `schedErrMs / schedErrP50 / schedErrP95 = None`：真实模式下没有 probe 排程，
> `onsetErrs` 只统计 probe 口径 ⇒ **既有口径差异，不是缺陷**。

### 2.4 EXT-023 执行设备（收口）

`.tmp/ext026_e2e/bridge.log` 里 **21 行** EXECUTION_DEVICES 相关日志，其中关键行：

```
[ext-engine] [tts_engine] EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，decoder=NPU/NPU/NPU/NPU/NPU/NPU/NPU/NPU/NPU
[ext-engine] [TTS-EXEC] on_npu=17 on_cpu=0 unknown=0 absent=4
```

落盘 `%LOCALAPPDATA%\LiveDubEXT\tts_exec_devices.json`（4 260 B，mtime 20:54:13）：

- `on_npu`：**17 项**
- `on_cpu`：**[]**（空）
- `on_unknown`：`[]`
- `absent`：`["talker_prefill","talker_decode","talker","code_predictor"]`
- `requested_device`: `NPU`；`actual_devices`：全部 `NPU`

⇒ **EXT-023 收口**：talker / cp_prefill / **cp_decode** / decoder 全部落在 **NPU**，
  **无任何一项落在 CPU**。

### 2.5 配音录音非静音（源 `.tmp/ext026_e2e/dub_audio_analysis.json`）

用 `tests/smoke/analyze_dub_audio.py`（headless Edge WebAudio 解码，**纯解码不跑推理**）实测：

| 字段 | 实测值 |
|---|---|
| 文件 | `dub_player.webm` **585 326 B**（mtime 20:34:06） |
| 时长 | **76.2 s**（16 kHz mono，1 219 200 帧） |
| peak | **0.56574**（−4.95 dBFS） |
| RMS | **0.063978**（**−23.88 dBFS**） |
| 语音 burst 数 | **32** |
| 语音时长 | **26.74 s**（占比 35.09%） |
| 判定 | **non_silent = true** |

⇒ **非静音**达成；段数对得上（7 段有音频，录音里 32 个 burst 覆盖 26.74 s）。

### 2.6 截图

- `.tmp/ext026_e2e/player_30s.png`：**28 756 B**（mtime 20:32:34）
- `.tmp/ext026_e2e/player_60s.png`：**28 064 B**（mtime 20:33:04）

目视 60 s 截图：中文译文字幕「对我说了什么，劳儿啊，快起来起来，地上凉」+
状态条「音源 90.0s | ASR 4 | MT 4 | TTS 4 | 下发 6 | 滞后 22.1s」。

### 2.7 A 轮证据清单（文件数 8，合计 665 745 B）

| 文件 | 字节 | mtime |
|---|---|---|
| `bridge.log` | 9 024 | 20:34:06 |
| `dub_player.webm` | 585 326 | 20:34:06 |
| `dub_audio_analysis.json` | 488 | 21:14:32（本轮用真工具重测） |
| `hello_ack.json` | 479 | 20:34:06 |
| `metrics.json` | 1 423 | 20:34:06 |
| `player_30s.png` | 28 756 | 20:32:34 |
| `player_60s.png` | 28 064 | 20:33:04 |
| `summary.json` | 12 185 | 20:34:29 |

---

## 3. B 轮：生产路径（`.tmp/ext026_prodpath/`）

- 起止：**2026-10-31 20:53:58 → 20:57:02**（采集 60 s）
- 页面：`http://127.0.0.1:62485/index.html`

### 3.1 段级日志（源 `.tmp/ext026_prodpath/bridge.log`，8 703 B）

| 指标 | 实测值 |
|---|---|
| 段级日志行数 | **9** |
| 「下发到」含 player 的段数 | **9 / 9** |
| 有 TTS 音频的段数 | **5** |
| 空段数 | 4 |
| 10048 端口占用 | **0 次** |
| TTS 语音总时长 | **27.84 s**（7.6 / 2.72 / 6.56 / 4.0 / 6.96） |

段 id 形态：`seg_77393782_0` / `seg_77393782_194400` … ⇒ 会话前缀生效。

### 3.2 metrics（源 `.tmp/ext026_prodpath/metrics.json`，272 B）

| 字段 | 实测值 |
|---|---|
| dubDelivered | **9**（转发链通了） |
| echoRecv / dubDup | 9 / 9 |
| asrSegments / mtSegments / ttsSegments | **5 / 5 / 5** |
| captureMode | **getDisplayMedia**（如实） |
| lagSec | 16.4806 |
| mode / enginesReady / pipeline | real / true / true |

> ★ `asr/ttsSegments = 5` 是**本轮修掉的缺陷**：`pollStats()` 原本只认
> `upState.ws`，而生产路径的上行 WS 在 **offscreen** 里 ⇒ player 的
> `upState.ws` 是 null ⇒ stats 发不出去 ⇒ 状态条段数**恒为 0**。
> 修法：回落用 player 自己那条 WS（role=player，服务端按 token 取真会话）。

### 3.3 配音录音非静音（源 `.tmp/ext026_prodpath/dub_audio_analysis.json`）

| 字段 | 实测值 |
|---|---|
| 文件 | `dub_player.webm` **409 669 B**（mtime 20:56:38） |
| 时长 | **115.02 s**（1 840 320 帧） |
| peak | **0.71230**（−2.95 dBFS） |
| RMS | **0.048422**（**−26.30 dBFS**） |
| 语音 burst 数 | **28** |
| 语音时长 | **18.08 s**（占比 15.72%） |
| 判定 | **non_silent = true** |

### 3.4 截图

- `.tmp/ext026_prodpath/player_30s.png`：**19 857 B**
- `.tmp/ext026_prodpath/player_60s.png`：**19 924 B**

### 3.5 B 轮证据清单（文件数 7，合计 469 835 B）

| 文件 | 字节 | mtime |
|---|---|---|
| `bridge.log` | 8 703 | 20:56:39 |
| `dub_player.webm` | 409 669 | 20:56:38 |
| `dub_audio_analysis.json` | 497 | 21:14:34（本轮用真工具重测） |
| `metrics.json` | 272 | 20:56:38 |
| `player_30s.png` | 19 857 | 20:55:06 |
| `player_60s.png` | 19 924 | 20:55:37 |
| `summary.json` | 10 913 | 20:57:02 |

---

## 4. 本轮在生产路径上抓到的 3 个真缺陷（都已修 + 有反证）

| # | 缺陷 | 现象 | 修法 |
|---|---|---|---|
| P1 | `pollStats()` 只认 `upState.ws` | 生产路径下状态条段数**恒为 0** | 回落用 player 自己那条 WS |
| P2 | 生产路径**没有 flush** | 用户点「停止」时**最后一句永远丢** | `offscreen.js` 加 `flushUplink()`；`sw.js` 加 `case 'flush'` 中转；`popup.html/js` 加「停止并收尾」按钮（先 flush，12 s 后自动 stop） |
| P3 | popup 配置只写 storage 不够 | 自动化下点「开始」报「桥接服务未启动」 | `popup.js` 的 `loadCfg()` 在页面加载时把 storage 读进 **DOM 输入框** ⇒ 必须**同时**写 storage 和 DOM |

另有 2 个非生产路径特有的坑：

| # | 坑 | 修法 |
|---|---|---|
| P4 | popup 的 `pairUrl()` 从 ws 端口 **+1** 推出配对端口 | 冒烟脚本改用 `_free_port_pair()` 取**连续两个**空闲端口 |
| P5 | `pollStats` 现在有**两处** `send` ⇒ 旧反证只改坏一处就失效 | 旧 harness 的 C4 反证改为**同时**改坏 `up.send` 与 `w.send` 两处 |

---

## 5. 本轮改动的产品代码（全部在 EXT 模块内）

| 文件 | 改动 |
|---|---|
| `ext/bridge.py` | 段 id 加会话前缀：`seg_{8位数字会话前缀}_{数字}`（`public_seg_id()`）；`hello_ack` 新增 `session_id` |
| `extension/player.js` | `metrics.dubDup` 计数；录音三函数（`startDubRecording`/`stopDubRecording`/`dubRecordingBlob`，只接 `dubBus`）；`flushUplink()`；`pollStats()` 回落 player 自己那条 WS；新会话清 `seenDubIds` |
| `extension/player.html` | 新增「停止并收尾」按钮 |
| `extension/offscreen.js` | `flushUplink()` + `case 'flush'`；`state.flushSent` |
| `extension/sw.js` | `case 'flush'` 中转到 offscreen |
| `extension/popup.html` / `popup.js` | 「停止并收尾」按钮 + 先 flush 再 stop |
| `USER_GUIDE.md` / `extension/USER_GUIDE.md` | 同步「停止并收尾」说明（两份必须一致，有自测守着） |

---

## 6. 本轮新增的自测

| 文件 | 内容 | 结果 |
|---|---|---|
| `tests/smoke/analyze_dub_audio.py` | 录音非静音分析工具（WebAudio 解码 + 单一事实来源的判据 `is_non_silent()`） | 工具 |
| `tests/test_ext026_audio_analysis.py` | 4 种合成波形真值对照 + 2 组反证 | **25 PASS / 0 FAIL** |
| `tests/smoke/ext026_e2e.py` | A 轮冒烟 + 接入音频分析 + verdict 写盘顺序修正 | 脚本 |
| `tests/smoke/ext026_prodpath.py` | B 轮生产路径冒烟 + 接入音频分析 + verdict 写盘顺序修正 | 脚本 |
| `tests/ext026_prodpath_harness.js` | 生产路径新行为的 node 沙箱 harness（4 组反证） | **17 PASS / 0 FAIL** |
| `tests/test_ext026_prodpath.py` | 上述 harness 的 Python 载体 | **14 PASS / 0 FAIL** |
| `tests/ext026_e2e_harness.js` | 旧 harness（C4 反证修正为两处都改坏） | **13 PASS / 0 FAIL** |
| `tests/ext026_segid_harness.js` | 段 id 唯一性 harness | **13 PASS / 0 FAIL** |
| `tests/test_ext026_seg_id_uniqueness.py` | 段 id 跨会话唯一性 | **15 PASS / 0 FAIL** |
| `tests/test_ext026_e2e_behaviors.py` | 旧 e2e 行为自测 | **21 PASS / 0 FAIL** |

---

## 7. 未做 / 不宣称

- ⛔ **不宣称「用户已听到配音」**：自动化下 player 播的是真实 TTS 音频
  （录音非静音已实测），但**真人戴耳机听**的验收仍需用户在 Edge 默认 profile 手势做。
- ⛔ **不宣称「tabCapture 生产抓流已在真机验证」**：自动化拿不到 tabCapture
  （需真实手势），实测错误原文已如实记录 ⇒ 该项仍待用户手势验收。
- ⛔ **端到端仍不实时**（TTS 稳态 RTF 1.0022 > 1.0）、**同步误差仍超标**、
  **克隆音色仍未接线** ⇒ 属既有阻塞项，本轮未动引擎，已在 STATUS 转交。
- ⛔ **未改任何引擎文件**：ASR=R2T2 / MT=Hy-MT2 / TTS=Qwen3-TTS 均按现有交付版本复用。
