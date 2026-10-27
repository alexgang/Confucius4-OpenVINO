# EXEC_LOG — EXT 模块执行记录（每轮追加，不回头改旧记录）

> 记录格式：执行时间 / 指令摘要 / 涉及修改的文件 / 验证与自测结果。
> 本文件与 `STATUS_EXT.md` 分工：STATUS 写状态与结论，EXEC_LOG 写**逐轮流水**。

## 2026-10-27 16:48 — 首次执行（EXT-002）

**执行时间**：2026-10-27 16:34（任务启动）→ 16:48（本轮完成）

**指令摘要**
- 来源文件：`C:\Users\Trekker-PTL\live_dub_ext\status\CORRECTIONS_EXT.md`
- 本轮唯一执行依据：**EXT-002 [NORMAL] 2026-10-27 15:48**（文件中编号最大、且带最新时间戳的条目）
- 指令要点：
  1. pyannote / segmentation-3.0 **只**做说话人识别，**不再**给 ASR 强制断句；
  2. 断句继续用 **R2T2 原有的方式**；
  3. pyannote 与说话人 embedding 在**旁路**运行，**不阻塞定稿**；
  4. 定稿段先发；spk 晚到（可晚 1–2 s）时用 id **补发一条 spk 更新事件**；
  5. 说话人攒够约 **3 s** 干净语音之前，spk 为 null，TTS 用**上一句的音色或预设 A**；
  6. 对 EXT-001 架构 B 节的修订：分段**一直用 R2T2 原有断句**，不等 pyannote 断句。
- 冲突处置：EXT-002 修订 EXT-001 架构 B 节「分段」一项 ⇒ **以 EXT-002 为准**。
- 旧指令（EXT-001）**未重复执行**：本轮仅在 EXT-002 修订的范围内落地，EXT-001 的其余条款（插件、阶段计划等）留待后续轮次按阶段推进。

**涉及修改的文件**
本轮**新建** 12 个文件（项目此前只有 `status/CORRECTIONS_EXT.md`，无任何实现）：

| 文件 | 字节 | 作用 |
|---|---|---|
| `ext/__init__.py` | 297 | 包边界说明 |
| `ext/config.py` | 1483 | 常量（分段 12–20 s、VAD −40 dB/300 ms、spk 3 s、变速上限 1.25×、设备摆放） |
| `ext/segmenter.py` | 6304 | EXT-002 核心：import R2T2 `seg_stream.py`；复制适配层兜底 |
| `ext/speaker.py` | 6546 | EXT-002 核心：定稿先出 / spk 晚到补发 / 3 s 门槛 / 音色回落 |
| `ext/duration.py` | 3026 | 时长适配：借静音、变速封顶 1.25×、超限记顺延 |
| `ext/time_stretch.py` | 3791 | WSOLA 保持音高变速 |
| `ext/bridge.py` | 13185 | 桥接服务：WS + Origin/token 校验 + 管线 + 回声模式 |
| `ext/engines.py` | 4567 | ASR/MT/TTS 延迟加载适配层（入口未接线时显式抛错） |
| `tests/test_ext_selfcheck.py` | 10747 | 单元自测 34 项 |
| `tests/test_echo_roundtrip.py` | 5541 | P0 ③ 回声端到端 10 项 |
| `status/STATUS_EXT.md` | 6829 | 状态文件（last_ack=EXT-002） |
| `.gitignore` | 456 | 忽略纠偏文件 / token / 克隆音色落盘产物 |
| `tools/next_instruction.py` | 4596 | **幂等闸门**：解析最新 EXT 条目 + 与 last_ack 比对 |
| `tests/test_next_instruction.py` | 5774 | 幂等闸门自测 18 项 |

- **未改动任何其他模块的文件**：`confucius4-openvino` 仅**只读 import**（`seg_stream.py`）；`hy_bench`、`confucius4-tts` 仅**目录探测**，未打开、未修改。
- git：新建独立仓库，commit `36ad78e`，12 files / +1609；`status/CORRECTIONS_EXT.md` 已入 `.gitignore`，**不入库**（沿用 App 模块约定）。未推远程（EXT-001：暂不推远程）。

**验证与自测结果**
```
python tests/test_ext_selfcheck.py    → 34 PASS / 0 FAIL
  [1] 分段：与 R2T2 原件 _plan_segments 输出**完全一致**（逐段比对）；
      完整段长 13.29 / 13.10 / 12.60 s，均落在 [12, 20] s；末段 0.31 s（尾巴）
  [2] 时长适配：放得下 rate=1.0；需变速 rate=1.2；超上限 rate=1.25 且顺延 1.500 s；
      借用下一段前静音 0.60 s
  [3] WSOLA 保持音高：rate=1.25 基频偏移 **0.0%**；rate=0.8 偏移 **2.2%**；
      对照组（朴素重采样 ≈ playbackRate）偏移 **24.3%** ⇒ 证明不能用 playbackRate
  [4] 说话人旁路：定稿 spk=None（不阻塞）；未满 3 s → 预设 A；满 3 s → 升级为该说话人；
      spk=None → 回落上一句音色；blocking_diarization=False
  [5] 桥接会话：产出配音任务（含 t_start/t_end/src/tgt/spk/fit）；sample_index 断裂被计数
  [6] 安全：Origin/token 校验 6 项全过；token 首次生成落盘、重载一致（幂等）

python tests/test_echo_roundtrip.py   → 10 PASS / 0 FAIL
  桥接服务起于 127.0.0.1:8799（echo 模式）；
  回声 PCM 与上行 PCM **逐样本一致**（3200 bytes）；hello_ack 带回 segmentation 来源；
  非法 Origin / 错误 token / 空 Origin → 全部 1008 拒绝

python tools/next_instruction.py      → exit 1（已执行 ⇒ 下一轮正确跳过）
python tests/test_next_instruction.py → 18 PASS / 0 FAIL
  幂等闸门：条目解析 / last_ack 只读头部不误读正文 / 缺文件·空·不可解析 → 全部判 skip；
  编号 ≤ last_ack → 「已执行」；编号 > last_ack → 「需执行」
```

**本轮修掉的 3 个真实缺陷**
1. `ext/speaker.py` — 音色**只会停在预设 A**：原判定 `if prof.voice_id is None` 使「预设 A」写入后永不升级为克隆音色 ⇒ 改为按 3 s 门槛**双向判定**。
2. `ext/speaker.py` — **量纲错配**：`_lookup_by_time` 用墙钟 `time.time()` 比对音频相对时间，二者永不相交 ⇒ 说话人永远匹配不上。改为在 `SpeakerProfile.spans` 记录**音频时间轴**区间，按区间算重叠。
3. `ext/bridge.py` — **握手必崩**：websockets 17.x 新 asyncio API 已无 `request_headers` ⇒ 任何连接触发 `AttributeError` → 1011。改为 `_get_header()` 兼容新旧两版。

**明确未做 / 不宣称**
- ⛔ 未跑推理、未占 GPU.0 / NPU、未与实时字幕 App 抢设备。
- ⛔ 未抢共享锁：`shared/MACHINE_LOCK` 当时被 `app-pack` PID 9900（16:23:26 起）持有 ⇒ 只读不动。
- ⛔ ASR/MT/TTS 引擎**未接线**（调用入口待主会话通知）；插件（Manifest V3）**未开工**；P0 ①② 未做。
- ⛔ **不写「已交付」**：P0 ③ 只验证了服务端侧，端到端排程误差 ≤ 20 ms 需插件侧配合才能测。

---
