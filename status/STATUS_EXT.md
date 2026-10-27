# STATUS_EXT
last_ack: EXT-002
更新时间: 2026-10-27 16:48
当前任务: **§1 EXT-002 落地（pyannote 只做说话人识别、不再断句；分段一律用 R2T2 原有断句）** ⇒ ✅ 已建 `ext/` 核心库 + `tests/` 自测 ⇒ ✅ 自测 **34/34 PASS**（单元）＋ **10/10 PASS**（P0 ③ 回声端到端）⇒ ✅ **修掉 2 个真实缺陷**（① `speaker.py` 音色不会从预设 A 升级 + 上一句音色未记录；② `speaker.py` 用墙钟时间与音频相对时间比量纲，错配；③ `bridge.py` websockets 17.x 新 API 无 `request_headers`，握手必崩）⇒ ⛔ **ASR/MT/TTS 引擎未接线**（调用入口待主会话通知，见 §3）⇒ ⛔ **未跑推理 / 未占 GPU·NPU / 未抢共享锁** ⇒ ⛔ **插件（Manifest V3）尚未开工**

阻塞 / 待决定:
① 🔴 **ASR/MT/TTS 引擎调用入口未知** —— EXT-001 总原则要求「复用现有交付版本，不改其他模块的文件」，但三个引擎的**具体调用入口**需主会话转达（本轮已留好 `ext/engines.py` 的 `EngineAdapter` 接口 + 静态探测，不猜 API）；② 🔴 **插件侧（Manifest V3）本轮未开工** —— EXT-002 只影响服务端分段策略，插件侧无对应改动，先做服务端以免偏离架构；③ ⛔ **共享机器锁被占**（`app-pack` PID 9900，16:23:26 起）⇒ 本轮**未抢锁、未删锁**；④ ⛔ **pyannote 旁路未接线** —— ASR-013 交付后由主会话通知，本模块已备好 `SpeakerTracker.update_from_diarization()` 接线点；⑤ ⛔ **P0 ① ② 未做**（tabCapture+offscreen+AudioWorklet 上行、WebCodecs 延迟画面）—— 属插件侧，未开工；⑥ ⛔ **P0 ③ 只验证了服务端侧**（回声 PCM 逐样本一致 + 安全校验），**排程误差 ≤ 20 ms 需插件侧配合才能测**；⑦ ⛔ **P1/P2/P3 未开始**。

## 最近更新
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
