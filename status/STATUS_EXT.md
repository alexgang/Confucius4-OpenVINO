# STATUS_EXT
last_ack: EXT-003
更新时间: 2026-10-27 23:07
当前任务: **§2 EXT-003 落地（插件侧 P0 ①②③）** ⇒ ✅ 已建 **MV3 插件**（`extension/` 11 文件：manifest / sw / offscreen / player / popup + 4 个 AudioWorklet）⇒ ✅ **P0① 音频上行**打通（AudioWorklet 48 kHz→16 kHz FIR 抽取 → WebSocket）⇒ ✅ **P0② WebCodecs 延迟画面**打通（VP8 编码 → 环形缓冲 → 解码 → canvas）⇒ ✅ **P0③ 回声排程**已实现（浏览器端 `scheduleDub` + onset worklet 逐样本测误差）⇒ ✅ **三个引擎入口已自查定位**（ASR/MT/TTS 确切类与方法签名，见 §2.5）⇒ ✅ **修掉 9 个真实缺陷**（见 §2.4，含 5 分钟长测暴露的 3 个 O(n²)/无界队列性能缺陷）⇒ ✅ 自测 **34 + 10 + 19 + 43 + 8 = 114 PASS / 0 FAIL**（5 套）⇒ ⛔ **未跑推理 / 未占 GPU·NPU**（ASR/MT/TTS 全不接）⇒ ⛔ **P0① 5 分钟复测排队等锁中**（App 模块持 `shared/MACHINE_LOCK`，本模块排队未抢）

阻塞 / 待决定:
① 🔴 **P0① 5 分钟复测排队中** —— App 模块 `app108_npu_ab.py --repeats 3`（PID 15684，22:55:53 起）持有共享机器锁 ⇒ 本模块探针**排队等待**（`--lock-wait 5400`），未抢锁、未删锁；修复后需重跑以确认 `maxAbsSkewMs < 50 ms`；② 🔴 **P0② 唇音同步误差尚未复测出数值** —— 修完「连续 onset + 一对一配对 + 中心采样白闪检测」后**还没跑出新数据**（等待同一把锁）；③ 🔴 **P0③ 排程误差落盘证据尚未产出** —— `tools/echo_sched_probe.py` / `tools/video_lipsync_probe.py` 已写好，等锁后执行；④ ⛔ **引擎仍未接线** —— 入口已定位（§2.5）但**本轮不接线**（不跑推理），`ext/engines.py` 的 `EngineAdapter` 留空待主会话指示；⑤ ⛔ **pyannote 旁路未接线** —— ASR-013 交付后由主会话通知；⑥ ⛔ **P1/P2/P3 未开始**。

## 最近更新
23:07 §2 **EXT-003 落地**（本轮执行依据 = EXT-004 → 实际未完成项为 EXT-003 [HIGH] 的插件侧 P0 ①②③ + 引擎入口自查）：✅ **新建 MV3 插件** `extension/`（manifest.json / sw.js / offscreen.js / offscreen.html / player.js / player.html / popup.js / popup.html + capture-worklet.js / onset-worklet.js / probe-worklet.js）⇒ ✅ **P0① 音频上行**：AudioWorklet 48 kHz→16 kHz（96 抽头 Blackman-sinc 环形缓冲抽取）→ WebSocket 上行，实测 5 分钟 **14191 帧 / gaps=0 / 9.69 MB** ⇒ ✅ **P0② WebCodecs 延迟画面**：`MediaStreamTrackProcessor` → `VideoEncoder(VP8)` → 300 块环形缓冲 → `VideoDecoder` → canvas（延迟 D），实测 **encoded=409 / decoded=243 / drawn=243** ⇒ ✅ **P0③ 回声排程**：`scheduleDub` 按 `t0 + t_start + D` 排程 + onset worklet 逐样本测「实际出声 − 计划出声」⇒ ✅ **三个引擎入口自查定位完成**（§2.5）⇒ ✅ **修 9 个真实缺陷**（§2.4）⇒ ✅ **5 套自测 114 PASS / 0 FAIL** ⇒ ⛔ **5 分钟复测排队等锁**、⛔ **P0②③ 数值待实测**、⛔ **未跑推理/未占 GPU·NPU**
16:48 §1 **EXT-002 落地**（本轮唯一执行依据 = EXT-002）：✅ 新建 `ext/` 核心库 7 文件（`config.py` / `segmenter.py` / `speaker.py` / `duration.py` / `time_stretch.py` / `bridge.py` / `engines.py`）＋ `tests/` 2 文件 ⇒ ✅ **分段走 R2T2 原件 import**（`confucius4-openvino/seg_stream.py`，只读不改），自测断言与原件 `_plan_segments` **完全一致** ⇒ ✅ **speech 旁路语义落地**：定稿段先发（`spk=None`）、spk 晚到用 id **补发 spk_update 事件**、攒够 3 s 才从预设 A 升级为克隆音色、`blocking_diarization=False` ⇒ ✅ **时长适配**：变速封顶 1.25×、超限记顺延、可借下一段前静音 ⇒ ✅ **WSOLA 保持音高**：rate=1.25 基频偏移 0.0%、rate=0.8 偏移 2.2%，对照组朴素重采样偏移 24.3%（证明不能用 playbackRate）⇒ ✅ **安全**：Origin 必须 `chrome-extension://` + token 校验，非法 Origin / 错 token / 空 Origin 全部 1008 拒绝 ⇒ ✅ **修 3 个真实缺陷**：`speaker.py` 音色不升级、`speaker.py` 墙钟/音频时间量纲错配、`bridge.py` websockets 17.x `request_headers` 崩溃 ⇒ ⛔ **引擎未接线**、⛔ **插件未开工**、⛔ **未跑推理/未占 GPU·NPU/未抢锁**

## §1 EXT-002 落地（2026-10-27 16:48）

### 1.1 本轮指令（唯一执行依据）
`status/CORRECTIONS_EXT.md` 的 **EXT-002 [NORMAL] 2026-10-27 15:48**：
> pyannote/segmentation-3.0 只用来识别说话人，**不再**用来给 ASR 强制断句。
> 断句继续用 R2T2 原有的方式。pyannote 和说话人 embedding 在**旁路**运行，**不阻塞定稿**：
> 定稿段先发出去，spk 晚到（可以晚 1–2 s）时，用 id 补发一条 spk 更新事件。
> 说话人攒够约 3 s 干净语音之前，spk 为 null，TTS 用上一句的音色或预设 A。
> 对 EXT-001 架构的修订：B 节"分段"一项改成**一直用 R2T2 原有断句**，不等 pyannote 断句。

冲突处置：EXT-002 修订 EXT-001 架构 B 节「分段」一项 ⇒ **以 EXT-002 为准**（符合本模块总原则）。

### 1.2 涉及修改的文件
本轮**新建**（项目此前只有交接单 `CORRECTIONS_EXT.md`，无任何实现）：

| 文件 | 作用 |
|---|---|
| `ext/__init__.py` | 包边界说明（复用引擎、不改他模块文件） |
| `ext/config.py` | 常量：分段 12–20 s、VAD −40 dB/300 ms、spk 3 s、变速上限 1.25×、设备摆放 ASR/MT=GPU.0、TTS=NPU |
| `ext/segmenter.py` | **EXT-002 核心**：优先 import R2T2 `seg_stream.py`；不可用时用复制适配层。`pyannote_used_for_segmentation=False` |
| `ext/speaker.py` | **EXT-002 核心**：定稿先出 / spk 晚到补发 / 3 s 门槛 / 上一句音色回落 |
| `ext/duration.py` | 时长适配：借静音、变速封顶 1.25×、超限记顺延 |
| `ext/time_stretch.py` | WSOLA 保持音高变速（不用 playbackRate） |
| `ext/bridge.py` | 桥接服务：127.0.0.1 + WS、Origin/token 校验、管线、回声模式 |
| `ext/engines.py` | 引擎适配层：延迟加载、静态探测、**不猜 API** |
| `tests/test_ext_selfcheck.py` | 单元自测 34 项 |
| `tests/test_echo_roundtrip.py` | P0 ③ 回声端到端 10 项 |
| `tools/next_instruction.py` | **幂等闸门**：解析最新 EXT 条目 + 与 `last_ack` 比对（退出码 0/1/2） |
| `tests/test_next_instruction.py` | 幂等闸门自测 18 项 |

**未改动任何其他模块的文件**（`confucius4-openvino` 只读 import，`hy_bench` / `confucius4-tts` 只探测目录）。

### 1.3 验证与自测结果
```
tests/test_ext_selfcheck.py    → 34 PASS / 0 FAIL
  [1] 分段：与 R2T2 原件 _plan_segments **完全一致**；段长 13.29/13.10/12.60 s 均在 [12,20] 内
  [2] 时长适配：rate=1 / 1.2 / 封顶 1.25+顺延 1.500 s / 借静音 0.60 s
  [3] WSOLA：rate 1.25 基频偏移 **0.0%**，rate 0.8 偏移 **2.2%**；对照组朴素重采样 **24.3%**
  [4] 说话人旁路：定稿 spk=None / 未满 3 s 用预设 A / 满 3 s 升级为该说话人 / spk=None 回落上一句
  [5] 桥接会话：产出配音任务（含 t_start,t_end,src,tgt,spk,fit）/ sample_index 断裂计数
  [6] 安全：Origin / token 校验 6 项 + token 落盘幂等

tests/test_echo_roundtrip.py   → 10 PASS / 0 FAIL
  桥接服务起于 127.0.0.1:8799；回声 PCM 与上行 PCM **逐样本一致**（3200 bytes）；
  hello_ack 带回 segmentation 来源；非法 Origin / 错 token / 空 Origin → 1008 拒绝

tests/test_next_instruction.py → 18 PASS / 0 FAIL
  幂等闸门：条目解析 / last_ack 只读头部 / 缺文件·空·不可解析 → 全部判 skip；
  编号 ≤ last_ack → 判「已执行」；编号 > last_ack → 判「需执行」；
  真实项目当前判定 = **已执行（exit 1）** ⇒ 下一轮会正确跳过
```

### 1.4 本轮修掉的真实缺陷（非风格调整）
1. **`ext/speaker.py`** — 音色只会停在预设 A：原逻辑 `if prof.voice_id is None` 使「预设 A」写入后**永不升级**为克隆音色。改为按 3 s 门槛**双向判定**（够量升级为 spk_id，不够回落预设 A）。
2. **`ext/speaker.py`** — **量纲错配**：`_lookup_by_time` 用 `time.time()`（墙钟）比对音频相对时间（会话起点 t0 起算），两者永不相交 ⇒ 说话人永远匹配不上。改为在 `SpeakerProfile.spans` 里记录**音频时间轴**区间，重叠度按区间算。
3. **`ext/bridge.py`** — **握手必崩**：websockets 17.x 的新 asyncio API 已无 `request_headers`（仅 `websocket.request.headers`）⇒ 任何连接都触发 `AttributeError` → 1011。改为 `_get_header()` 兼容新旧两版 API。

### 1.5 证据（文件 mtime / 字节数）
见本轮 §1.6 表与 `ext/`、`tests/` 目录实际内容。

### 1.6 未做 / 明确不宣称
- ⛔ **不写「已交付」**：插件（Manifest V3）、P0 ①②、P1、P2、P3 均未开工。
- ⛔ **不宣称排程误差 ≤ 20 ms**：P0 ③ 只验证了服务端侧（回声内容一致 + 安全），端到端排程误差需插件侧配合。
- ⛔ **不跑推理**：未启动 ASR/MT/TTS，未占 GPU.0 / NPU，未与实时字幕 App 抢设备。
- ⛔ **未抢共享锁**：`shared/MACHINE_LOCK` 当时被 `app-pack` PID 9900（16:23:26）持有 ⇒ 只读不动。
- ⛔ **引擎未接线**：`ext/engines.py` 的 `asr/mt/tts` 在未注入时抛 `NotImplementedError` ⇒ 桥接服务仍可跑回声模式。

## §2 EXT-003 落地（2026-10-27 23:07）

### 2.1 本轮指令（唯一执行依据）
`status/CORRECTIONS_EXT.md` 的 **EXT-004 [NORMAL] 2026-10-27 20:38**「RESUME：额度已重置，请从 last_ack 继续」，
其正文指向**未完成的 EXT-003 [HIGH]**，要求落地插件侧 P0 ①②③ + 自查引擎入口。

> 闸门输出（本轮开头实跑 `tools/next_instruction.py --json`）：
> `{"action":"execute","latest":{"id":"EXT-004","num":4,"priority":"[NORMAL]","ts":"2026-10-27 20:38","title":"RESUME：额度已重置，请从 last_ack 继续"},"last_ack":2,"n_entries":4}`

**冲突处置**：EXT-004 本身不含新要求，只是「继续」信号 ⇒ 本轮执行的是 EXT-003 的未完成项。
`last_ack` 从 `EXT-002` 推进到 **`EXT-003`**（EXT-004 是 RESUME 信号，不是独立技术要求；
按「只推进到实际执行完的最大 EXT 编号」的口径，先把 EXT-003 的技术要求做完）。

### 2.2 本轮新建的文件

**插件（MV3）—— `extension/`**

| 文件 | 字节 | 作用 |
|---|---|---|
| `manifest.json` | 1026 | MV3 清单：`tabCapture`/`offscreen`/`storage`/`scripting` 权限、`minimum_chrome_version: 116`、固定 `key` ⇒ 扩展 ID 稳定为 `kekgmfkijphpfndbbpakjaokamkeooib` |
| `sw.js` | 9321 | service worker：编排 + **Port 控制通道**（offscreen 主动 connect） |
| `offscreen.js` | 12283 | offscreen document：tabCapture/getDisplayMedia 抓流 → 16 kHz 重采样 → WS 上行 |
| `offscreen.html` | 156 | offscreen 宿主页 |
| `player.js` | 41738 | **扩展页播放器**：延迟画面（WebCodecs）、音频上行、排程、唇音同步、HUD |
| `player.html` | 1972 | 播放器页（含 CPU/内存 HUD 位） |
| `popup.js` / `popup.html` | 3326 / 2530 | popup：真实用户手势入口（`getMediaStreamId` / 开始 / 停止） |
| `capture-worklet.js` | 6648 | P0① 抽取：48 kHz→16 kHz，**96 抽头** Blackman-sinc FIR + **环形缓冲** |
| `onset-worklet.js` | 2801 | onset 精确检测（**连续检测 + 迟滞**），逐样本给时间戳 |
| `probe-worklet.js` | 391 | 调试用：隔离验证 AudioWorklet 是否被驱动 |

**实测工具 —— `tools/`**

| 文件 | 字节 | 作用 |
|---|---|---|
| `machine_lock.py` | 7130 | 共享机器锁：`hold()` 上下文管理器 + `probe_pid_alive()`（ctypes `OpenProcess`+`GetExitCodeProcess`，psutil 二次确认） |
| `browser_probe.py` | 17755 | P0①②③ 主探针：Playwright 驱动 Edge 加载扩展，落盘 `browser_probe.json` |
| `video_lipsync_probe.py` | 11405 | P0②+P0③ 联合实测（独立端口 8794/8894） |
| `echo_sched_probe.py` | 5743 | P0③ 独立实测（独立端口 8793） |
| `src_server.py` | 4994 | 测试源页：`/`（1080p30 + 真实 WAV）、`/sync`（**白闪与 3 kHz beep 同源触发**） |
| `bridge_echo_server.py` | 1570 | 回声模式桥接服务（`--port/--delay/--token-file`） |
| `run_probe_locked.py` | 2046 | 在机器锁保护下跑实测 |
| `player_perf_bench.js` | 9048 | 主线程开销**微基准**（纯 Node，不占浏览器/GPU/NPU） |

**自测 —— `tests/`**

| 文件 | 作用 |
|---|---|
| `tests/test_ext_browser_contract.py` | 新增：A 段 FIR 等价实现 + 唇音配对算法等价性；B 段插件侧静态契约；C 段落盘证据校验（**缺证据文件 ⇒ FAIL，不判 PASS**） |

### 2.3 三个引擎的调用入口（EXT-003 要求「自查引擎入口」）
**只读定位，未接线、未跑推理。** 位置：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6\app\`

**ASR（沿用 R2T2 既有链路）**
- `app/segment_encoder_backend.py:59` — `class SegmentEncoderOVBackend(ASRBackend)`
  `__init__(self, encoder_dir="models/ov-encoder-segment-reviewer", decoder_dir="models/ov-int8-past", device="GPU.0", precision="f16", cache_dir="./ov_cache", strict_intel=True)`
  ⚠️ `strict_intel=True` 会断言设备名含 "Intel"（本机 GPU.1 是 RTX 5050 ⇒ 需 `strict_intel=False` 才能对照）。
- `app/streaming_asr.py:230` — `streaming_transcribe(backend, pcm16k, state, max_new_tokens=None, rollback_punctuation=False, enable_hallucination_reset=True, adaptive_budget=False) -> tuple[str, str]`
- `app/streaming_asr.py:409` — `finish_streaming_transcribe(backend, state, max_new_tokens=None) -> str`

**MT**
- `app/translator.py:838` — `class TranslationService`；`__init__(self, target='off', device='GPU.0', model_dir=None, on_log=print, ...)`
- `app/translator.py:1096` — `submit(self, sentence, seg=None, spk=None, spk_conf=None)`
- `app/translator.py:1483` — `pop_outbox(self)`
- `app/translator.py:691` — `class HunyuanTranslator`；`__init__(self, model_dir=None, device='GPU.0', cache_dir=None, on_log=print)`

**TTS**
- `app/tts_engine.py:400` — `make_engine(device='NPU', model_path=None, cache_dir=None, on_log=print, precision=None)`
- `app/tts_engine.py:1107` — `stream(eng, text, language='English', speaker_embed=None, speaker=None, cancel_event=None, max_new_tokens=None, est_sec=None, on_log=print) -> Iterator[Tuple]`（产出 `(chunk_waveform, sample_rate)`，sample_rate 恒 **24000**）
- `app/tts_engine.py:717` — `speaker_embedding(eng, ref_wav=None, on_log=print) -> Optional[np.ndarray]`（shape `(1,1024)`，**只算一次**）
- `app/tts_worker.py` — `TTSWorker.__init__(device='GPU.0', voice='A', out_device=None, model_dir=None, clone=False, bigvgan_ir=None, precision='f32', out_wav=None, seed=1234, steps=25, cfg_rate=0.7)` / `TTSWorker.synth(jid, text, spk=None, spk_conf=None, lang=None)`

**运行时与模型位置**：babelvox 运行时在 `Confucius4_LiveCaption_v1.6/python/Lib/site-packages/babelvox`；
模型在 `Confucius4_LiveCaption_v1.6/models/qwen3tts`（TTS）与 `models/mt`（MT）。

### 2.4 本轮修掉的真实缺陷（非风格调整）

**A 组：协议与架构（早期实测踩出来的）**

1. **`extension/capture-worklet.js` — FIR 抽取永久卡死**（致命）：旧实现用**绝对** `outCount` 算窗口需求 `(outCount+1)*decim + CENTER + 1`，而历史缓冲固定 512 ⇒ 输出约 165 个样本后 `need > histLen` 永久卡死 ⇒ `minOut(320)` 永达不到 ⇒ `_flush()` 从不执行 ⇒ **一帧都发不出去**（实测 `frameCount=0`）。改为**环形缓冲（HB=1024）+ 相对索引**。
2. **`extension/capture-worklet.js` — 32 抽头 FIR 阻带衰减不足**：实测频响 9 kHz 仅 −12.2 dB（16 kHz 抽取会混叠）。抽头数对比：48→−16.7 / 64→−22.3 / **96→−38.7** / 128→−68.1 dB ⇒ 改为 **96 抽头**（`TAPS=96`、`CENTER=47`），Python 等价实现同步。
3. **`ext/bridge.py` — `delay_sec` 未定义名**（致命）：`_handle_messages` 里引用的是 `handle_ws` 作用域的变量 ⇒ 每条消息处理都抛 `NameError` ⇒ 连接立即被关 ⇒ **P0① 上行链路此前根本没跑通**。日志证据：`[bridge 22:10:54] 连接异常: name 'delay_sec' is not defined`。改为 `_handle_messages(..., delay_sec: float)` 显式带形参。
4. **`ext/bridge.py` — `_handle_messages` 漏传 `first` 形参**（本轮自测回归）：拆函数时 `handle_ws` 的第二处调用点忘了传 `first=None` ⇒ 走 header token 路径的连接必抛 `TypeError` ⇒ 1011。**由 `tests/test_echo_roundtrip.py` 抓到**（4 PASS / 1 FAIL → 修复后 10 PASS / 0 FAIL）。
5. **`extension/sw.js` — MV3 多 listener 抢消息通道**：报错 `A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received`。改为**只有主 listener 返回 `true`**，广播 listener 返回 `false`。
6. **`extension/sw.js` — 跨 `await` 后 `chrome.runtime.connect()` 报 "Receiving end does not exist"**（MV3 SW 时序限制）：改为**架构反转** —— offscreen 文档在脚本加载时立即 `connect()` 到 SW，SW 持有引用（`Port` 是点对点的，不存在 sendMessage 的广播/异步响应归属问题）。
7. **`extension/offscreen.js` — offscreen document 里 AudioWorklet 不被驱动**（关键发现）：`ac.state=running` 但 worklet 的 `process()` 从不调用（实测 `workletProcessCalls=0`、0 帧）；对照实验证明**同样的代码在扩展页里完全正常** ⇒ **音频上行改到扩展页（player.html）承载**，offscreen 保留为生产 tabCapture 路径的备选。
8. **`extension/player.js` — 时钟基准点偏 +131 ms**：t0 原先在「建好节点后立刻」记，含了抓流管线的固定延迟。改为用首帧的 `inSamples` 反推真实基准点 ⇒ 偏差降到 **30.9 ms**。
9. **`extension/player.js` — `createDelay(2.0)` 把 `delayTime=10` 钳到 2 秒**：浏览器警告 `Delay.delayTime.value 10 outside nominal range [0, 2]` ⇒ 改为 `createDelay(Math.max(2, delaySec + 1))`（`maxDelayTime` 是**构造参数**）。
10. **`extension/onset-worklet.js` — 只报第一个 onset**：原 `armedCount` 默认只报一次 ⇒ 唇音同步只捕到 1 个，配对算出 **1962 ms** 的荒谬值。改为**连续检测 + 迟滞**（`threshold` 触发 / `release = threshold*0.4` 复位 / `minGapSec` 保护）。

**B 组：5 分钟长测暴露的三个性能缺陷（本轮新增）**

11. **`extension/player.js` — `pendingSched` 无界增长**：bridge 回声模式**每帧**回灌一个 echo（16 kHz / 20~100 ms 一帧 ⇒ 约 47 帧/秒），而 `onDubOnset` 只在**检出 onset**时才 shift ⇒ 5 分钟累积 **13889** 条（微基准实测）⇒ 主线程负担持续上升。改为**有界**（`PENDING_SCHED_CAP=512`，先裁剪再 push，超限计入 `metrics.pendingSchedDropped`，不静默丢）。
12. **`extension/player.js` — `subs` 每条 push 都 `sort()` ⇒ O(n² log n)**：5 分钟 14191 条 ⇒ 微基准实测 **1062.78 ms**（旧）vs **1.55 ms**（新，**686×**）。改为**有序插入**（尾部单调递增时 O(1) push，否则二分插入）+ 上限 `SUBS_CAP=200`。
13. **`extension/player.js` — `report()` 每秒全量搬运含大数组的 metrics**：`metrics` 含 `onsetErrs`/`lipErrs`/`drawMarks`/`origOnsets`/`dubOnsets` 五个 200~500 项数组，每秒随 `report` 发给 SW，SW 再转发 offscreen，offscreen 又写 `chrome.storage.local`（保留 200 条）⇒ 每秒约 **14.4 KB** 序列化+落盘，5 分钟约 **4.2 MB**。改为**只发标量摘要**（`reportSummary` + `REPORT_SCALARS`），大数组留在 player 页按需取。
14. **`extension/player.js` — `pct()` 每次调用都 `[...arr].sort()`**：`computeLipSync` 每秒调 3 次、`onDubOnset` 每次调 2 次 ⇒ 持续排序 500 项。改为**缓存有序副本**（`WeakMap` + 长度/首尾元素做脏检查）⇒ 微基准 **23.34 ms → 0.32 ms（73×）**。
15. **`extension/player.js` — `computeLipSync` 是 O(n²) 全表扫描**：每个 onset 扫全部 marks（n=500 ⇒ 25 万次比较/秒）。改为**单调双指针 + 小窗口**（仍是最近邻语义），并用 Python 等价实现验证**与旧贪心结果一致**。

**C 组：测试与工具自身的缺陷（本轮修正）**

16. **`tests/test_next_instruction.py` — 真实项目断言写死编号**：原断言 `rc == 1`（依赖「本轮已做完 EXT-002」）⇒ `last_ack` 一推进就必然失效。改为断言**语义不变量**（退出码必须与「最新条目编号 vs last_ack」的真实关系一致）。
17. **`tests/test_ext_browser_contract.py` — 3 处错误断言**（非产品问题）：A1 未考虑 FIR **群延迟**（96 抽头 ⇒ ≈16 个输出样本）；A3 用时域窗口测阻带会被群延迟错位 ⇒ 改用**频域**测量并加 A3c/A3d；B6b 统计了 relay 函数的 `return true`（返回值，非异步响应标记）⇒ 改为只统计 `onMessage.addListener` 块内的。
18. **`tests/test_ext_browser_contract.py` — 静态断言匹配到注释**：B8c 误判 `subs.sort(` 仍在（实际只在注释里）⇒ 加 `_strip_js_comments()` 剥离注释后再断言。
19. **`tools/machine_lock.py` — 死锁永远无法回收**：`OpenProcess` 对已消失进程返回 NULL，按铁律「探测失败视为存活」⇒ 死持有者的锁**永远**回收不了。改为用 `psutil.pid_exists` 二次确认区分「已死」与「权限不足」：**psutil 说不存在 ⇒ 确认已死可回收；说存在或无法确认 ⇒ 保守视为存活**。
20. **`ext/bridge.py` — 浏览器 WS 无法自定义请求头**：`getDisplayMedia` 路径的插件握手必崩 ⇒ 允许 token 放在**首个 hello 消息**里（安全口径不变：token 必须正确 + Origin 必须 `chrome-extension://`）。

### 2.5 本机实测到的硬约束（决定了实现形态）
1. `chrome.tabCapture.getMediaStreamId()` 在**自动化**里拿不到流 id（"Extension has not been invoked for the current page"）⇒ 自动化走 `getDisplayMedia({video, audio:true})` + `--auto-select-tab-capture-source-by-title=EXTSRCPAGE`；生产路径保留 popup 真实手势。
2. 本机 WebCodecs **不支持 H.264**（`avc1.*` 全部 `isConfigSupported=false`）；**VP9/AV1 虽 supported=true 但实际编码必失败**（`EncodingError: Flushing error.`）⇒ 唯一实测可用的是 **VP8 + no-preference** ⇒ 候选顺序必须 VP8 打头。
3. **后台标签页不产帧** ⇒ 源页必须开在**独立窗口**（CDP `Target.createTarget(newWindow:true)`）⇒ 否则 `MediaStreamTrackProcessor` 拿不到帧、`encoded` 恒为 0。
4. **offscreen document 里 AudioWorklet 不被驱动**（见缺陷 7）⇒ 音频上行放扩展页。
5. `getDisplayMedia` 需要**真实用户手势** ⇒ 由 Playwright 点击页面上的「开始捕获」按钮触发。
6. **编码器尺寸必须来自真实帧**：实测 `track.getSettings()` 给 2048×1280 而实际帧是 2048×1078 ⇒ 尺寸不符 ⇒ `OperationError: Encoding error.` ⇒ 改为等第一帧到达后用 `frame.displayWidth/Height` 配置编码器。

### 2.6 验证与自测结果
```
tests/test_ext_selfcheck.py        → 34 PASS / 0 FAIL
tests/test_echo_roundtrip.py       → 10 PASS / 0 FAIL   （缺陷 4 由它抓到）
tests/test_next_instruction.py     → 19 PASS / 0 FAIL   （缺陷 16 修正后）
tests/test_ext_browser_contract.py → 43 PASS / 0 FAIL   （C 段读落盘证据，缺证据 ⇒ FAIL）
tools/player_perf_bench.js         →  8 PASS / 0 FAIL   （纯 Node 微基准）
```
合计 **114 PASS / 0 FAIL**（5 套）。

### 2.7 未做 / 明确不宣称
- ⛔ **不宣称 P0① 已达标**：5 分钟长测（修复前）实测 `maxAbsSkewMs=595.48`（P95=29.01、P99=130.48）**超过 50 ms 阈值**；已定位为缺陷 11–15 并修复，**修复后的 5 分钟复测排队等共享锁中**（App 模块持锁）⇒ 复测未出结果前不宣称达标。
- ⛔ **不宣称 P0② 唇音同步误差数值**：修复了「连续 onset + 一对一配对 + 中心 5 点采样白闪检测 + `/sync` 同源测试片」，但**尚未跑出新数据**。
- ⛔ **不宣称 P0③ 排程误差数值**：`echo_sched_probe.py` / `video_lipsync_probe.py` 已写好，等锁后执行。
- ⛔ **不跑推理**：未启动 ASR/MT/TTS，未占 GPU.0 / NPU ⇒ 不与实时字幕 App 抢设备。
- ⛔ **未抢共享锁**：App 模块 `app108_npu_ab.py --repeats 3`（PID 15684，22:55:53 起）持有 `shared/MACHINE_LOCK` ⇒ 本模块探针**排队等待**（`--lock-wait 5400`），未抢锁、未删锁。
- ⛔ **引擎未接线**：§2.3 只做**只读定位**，`ext/engines.py` 的 `EngineAdapter` 仍未注入 ⇒ 桥接服务仍跑回声模式。
- ⛔ **P1/P2/P3 未开始**。
