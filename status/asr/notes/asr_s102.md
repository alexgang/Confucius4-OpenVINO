# ASR §102 — 巡检（无新 ASR 纠偏，`last_ack` 仍 **ASR-068**）＋ 🔴 **新发现：MiniMVP v1.2 候选包的 EXT 侧 ASR 引擎 100% 加载失败（123/123 段）** ＋ 🔴 **README「四种 ASR 后端」表与包内实际引擎集不符**（2026-11-26 14:40–14:55）

## 0. 本轮性质

- 🔴 **纠偏通道（文件 ＋ 邮件双复核）**：`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime **2026-11-23 16:55:15**
  ⇒ 与 §96–§101 **逐字相同**；`^## ASR-` 标题共 **37** 条、最大编号 **ASR-068**；搜 `ASR-069` ⇒ **0 命中**
  ⇒ **`last_ack` 保持 `ASR-068`**。
- 🟡 **根 `status/CORRECTIONS.md`**（262 907 B / mtime **2026-11-25 22:04:31**）内含 ASR 编号条目 **0**
  （唯一 `ASR-` 命中在 L216，是 C-019 正文里的 `Qwen3-ASR-1.7B` 产品名，**不是纠偏编号**）。
- 🔴 **邮件通道**：QQ 收件箱 after **2026-11-24T12:00:00Z** 共 **3 封，全部非 ASR 编号** ⇒ 不进本模块 `last_ack`：
  | 时间(Z) | 邮件 | 归属 |
  |---|---|---|
  | 11-25 00:56:56 | **T-008** `[FQ][B][CORRECTION][GEN]` | FQ（通用） |
  | 11-25 10:29:26 | **H-030** `[C4][A][CORRECTION][MT]` | MT |
  | 11-25 10:29:30 | **APP-140** `[C4][A][CORRECTION][APP]` | App |

  主题含 `[CORRECTION][ASR]` 的最大编号仍 **ASR-068**（11-23 08:55:15Z）；spam **0** 封；trash **1** 封（rc9 性能报告，非纠偏）。
- 🔴 **本轮不是纯巡检 ⇒ 有实质状态变化（2 条新发现）⇒ 写 §102 章节 ＋ 发 STATUS 邮件**。

## 1. 🔴🔴 新发现 1：MiniMVP v1.2 候选包**插件侧（EXT）ASR 引擎 100% 加载失败** ⇒ 三轮 e2e 的 ASR 数字全是空跑

### 1.1 事实（全部来自 App 产出的产物，本模块只读复算）

- 产物根：`shared/bgkeep/e2e_app146/`（App 模块 APP-146 三轮，**本机时间 14:01–14:49**）。
  - `smoke/bgkeep_on_1/bridge.log`（14:01）⇒ **ASR 失败 13 次**
  - `smoke2/bgkeep_on_1/bridge.log`（14:05）⇒ **ASR 失败 13 次**
  - `three_arms/bgkeep_off/bgkeep_off_1/bridge.log`（14:28–14:39，600 s 整段）⇒ **ASR 失败 123 次**（＝全部段）
  - `three_arms/bgkeep_on/bgkeep_on_1/bridge.log`（14:39–14:49）⇒ **ASR 失败 120 次**（跑到 583 s 时仍在失败）
- 失败原文（`three_arms/bgkeep_off/.../bridge.log` L6–L13）：
  ```
  [bridge 14:28:50] (1/3) 正在加载 ASR（R2T2 INT8） @ GPU.0 ……
  [bridge 14:28:54] (1/3) ASR（R2T2 INT8） 加载失败 ⇒ EngineNeedsChange: [R2T2] SegmentEncoderOVBackend 构造失败（device=GPU.0）:
      ir: Could not open the file: "C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate\models\encoder-int8\openvino_encoder_model.xml"
  [bridge 14:29:11] 引擎预热完成：成功 2/3，总耗时 20.9 秒
  [bridge 14:29:11] ❌ 部分引擎加载失败：{'asr': 'EngineNeedsChange: [R2T2] SegmentEncoderOVBackend 构造失败 …'}
  ```
  ⇒ **MT（Hy-MT3）与 TTS 正常加载**，**只有 ASR 起不来**；桥接**不中止**（`--real` 分支只对「引擎接线失败」return 4，
  预热失败只告警）⇒ **每段都走 ASR 异常分支**。
- 段级证据：`bridge.log` 每段都是 `ASR='—' | MT='—' | TTS=0.00s | 耗时 asr=0.00 mt=0.00 tts=0.00`。
- `stats_full` 原始字段（`three_arms/bgkeep_off/bgkeep_off_1/bgkeep_e2e.json`，**44 846 B** / mtime 11-26 14:39）：
  ```
  asr_segments = 0     mt_segments = 0     tts_segments = 0
  pipeline = {"n_submitted":123,"n_emitted":123,"n_error":123,"n_pending":0,
              "stage_wall_sec":{"asr":8.168,"mt":0.001,"tts":0.003},"emit_sec":0.008}
  spk_bypass = {"enabled":False,…}
  spk_reason_hist = {"none":123}
  clone_reasons = {}    n_gender_splits = 0
  speaker = {"n_speakers":0,"n_pending_unassigned":123,"n_final_without_spk":26,…}
  ```
  ⇒ 🔴 **`n_error` = 123 = `n_submitted`** ⇒ **整条链路的 123 段全是错误**，只有收口/计时统计还在跑。

### 1.2 根因（机理，读代码确认）

- EXT 的 ASR 引擎目录是**写死**的（`ext/bridge/engine_runtime.py` L85–86，v0.4.22 与 v0.4.21 逐字相同）：
  ```python
  ASR_ENCODER_DIR = os.path.join(MODELS_DIR, "encoder-int8")
  ASR_DECODER_DIR = os.path.join(MODELS_DIR, "decoder-gpu-int8")
  ```
  ⇒ EXT 只支持 **R2T2 1.7B**（`encoder-int8` ＋ `decoder-gpu-int8`）。
- 🟡 **但 MiniMVP 包只带 Qwen3-ASR-0.6B**（`app/live_caption_app.py` L774/L895–L922 的 `asr06b` 族：
  `ov-encoder-06b-fp16-static` ＋ `ov-dec-06b-stateful-int8sym`）⇒ **EXT 侧没有任何 06B 接线代码**
  （全仓 `ext/` 内搜 `06b` / `stateful` ⇒ **0 命中**）。
- 🔴 **包内模型目录实测**（`Confucius4_LiveCaption_MiniMVP_v1.2.candidate/models/`）：
  `asr06b-decoder-int8` / `asr06b-encoder-fp16` / `asr06b-tokenizer` / `bgsep` / `mt` / `qwen3tts` / `spk`
  ⇒ **`encoder-int8` 与 `decoder-gpu-int8` 都不存在** ⇒ 加载必然失败。
- 🟢 **对照：EXT 在完整版 v2.6 上一直正常** ⇒ 该臂 `e2e_app134b` / `e2e_app134c` 的 `pkg` 都是
  `Confucius4_LiveCaption_v2.6`（有 `encoder-int8` ＋ `decoder-gpu-int8`）⇒ **不是 EXT 新回归，是「EXT 只支持 R2T2」与
  「MiniMVP 只带 06B」的固有错配**。

### 1.3 影响面（🔴 必读：包括**已发客户**的 v1.1.1）

| 包 | EXT ASR | 是否已写明 | 备注 |
|---|---|---|---|
| `MiniMVP_v1.2.candidate`（本轮 App-146 重做） | ❌ 不可用 | ✅ **已写明**（`README_zh.md` L387–390「插件（EXT）侧的语音识别在本包不可用」） | 本轮新加的说明（`README_zh.md.bak_app146_readme` 与 `bak_app146_docs` 里都**没有** ⇒ 是 **11-26 14:04 本轮重写时新增**） |
| `MiniMVP_v1.1.1.zip`（🔴 **发客户的就是它**，5 212 403 155 B / 2026-11-23 10:31:48） | ❌ 不可用 | ✅ **已写明**（zip 内 `README_zh.md`「已知问题 4. ⚠️ EXT 的 ASR 在本版不可用」＋「配音桥接（EXT）」节整段说明） | 实测 zip 内 `models/encoder-int8/openvino_encoder_model.xml` **ABSENT**、`models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.xml` **PRESENT**、`ext/bridge/` **24** 个文件 ⇒ 错配确实在包里 |
| `MiniMVP_v1.1` | ❌ 不可用 | 🟡 未核（未查其 README） | `Start_Bridge.bat` 亦为 `EXT v0.4.18` |
| `MiniMVP_v1.0-rc11` / `SpecialMVP_v1.0-sp5` | ❌ 应同样不可用 | 🟡 未核 | 同为 06B 包布局 |
| `LiveCaption_v2.6`（完整版） | ✅ 正常 | — | 有 `encoder-int8` ＋ `decoder-gpu-int8` |

⇒ 🟢 **两个 MiniMVP README 都已把这条限制写在明面上 ⇒ 不是「悄悄坏了」**；🔴 **但 App-146 第 4 步的三轮 e2e
是在这个前提下跑的**，⇒ **三轮的 ASR 侧数字（段数、dub 数、clone_reasons、spk_reason_hist、dub_late）全部无效**
⇒ **APP-147 的自查条件 1「没有模块起不来」按字面已不满足** ⇒ **建议 App 线程在打 zip 前补一轮「ASR 引擎可用」的臂**
（或明确接受「插件侧 ASR 不可用」并据此写进自查条件）。

### 1.4 与本模块既有结论的关系

- 🟢 **不涉及 ASR 模型本身的精度/性能**（06B 后端在 App 侧 `live_caption_app.py` 的 `asr06b` 族是通的；本轮 ASR 交付文件未动）。
- 🔴 **但它使本模块 §96–§101 的「旁路/说话人链路」结论在新候选包上无法复算** ⇒ 本轮所有 App146 臂的
  `spk_reason_hist`/`clone_reasons`/`n_gender_splits` **不能**作为 §101.3 归因缺口的证据（旁路压根没跑）。
- 🟡 **§101.3 的归因缺口本身不受影响**：机理在 EXT 代码里（`ext/speaker_bypass.py` 失败分支只 `n_no_label += 1`、
  不写行；v0.4.22 HEAD `e901cad` 里 `ext/speaker_bypass.py` 与 `ext/bridge.py` 的 `_spk_reason_hist()` **逐字未改**
  ⇒ 只读复核确认**缺口仍在**）。

## 2. 🔴 新发现 2：README「四种 ASR 后端」表与 MiniMVP 包内实际引擎集不符（ASR 域内容，需 App/reviewer 拍板）

- 🔴 `README_zh.md`（11-26 14:04 重写版）L140–L158 仍保留完整版 v2.x 的「**四种 ASR 后端**」表：
  | 后端 | 模型 | README 给的 RTF |
  |---|---|---|
  | Intel GPU · INT8 | 编码器 INT8 ＋ 解码器 INT8 | 0.70 |
  | Intel GPU · INT4 | 编码器 INT4 ＋ 解码器 INT4 | 0.73 |
  | Intel NPU · INT8 | 编码器 FP16 ＋ 解码器 INT8 | 0.86 |
  | Intel NPU · INT4（实验） | 编码器 FP16 ＋ 解码器 INT4 | 0.75 |

  并写「61 分钟英文会议录音的完整测试中，Intel NPU · INT8 的整体 RTF 为 0.77」。
- 🔴 **但 MiniMVP 包内实际只有 06B 的两个后端**（`app/live_caption_app.py` L914–L922 `ENGINES_ASR06B`）：
  `gpu_int8`（label「Intel GPU · INT8 (stateful)」）与 `npu_int8`（「Intel NPU · INT8 (stateful)」）
  ⇒ 🔴 **没有 INT4 档**（`asr06b_gpu_int4` / `asr06b_npu_int4` 全仓 **0 命中**）
  ⇒ 🔴 **包内也没有任何 INT4 模型目录**（`models/` 下无 `*int4*`）。
- 🔴 **那四个 RTF 数字的口径也与本包不符**：
  - 本表写的是 **R2T2（完整版）** 的编码器/解码器组合（`encoder-int8` ＋ `ov-int8-past` 等），
    而本包跑的是 **06B stateful**；
  - 本模块 §83 / ASR-060～061 实测的 NPU 档是 **流式 RTF 0.3094 / 0.2912 / 0.3165**、离线 **0.0496 / 0.0448 / 0.0665**
    ⇒ **README 的 0.86 / 0.77 与本模块任何一档都不是同一计分器**（与 §101.5 已挂的「对外 NPU 报告 RTF 0.067 口径」
    **属同一类问题**，但**来源不同**：那封是 reviewer 自发报告，这份是**客户包 README**）。
- 🟢 **v1.1.1（已发客户）没有这个问题**：其 `README_zh.md` **不含**「四种 ASR 后端」/「0.70」/「61 分钟」，
  且明确写 `--engine` 只有 `gpu_int8` / `npu_int8` ⇒ **该表是 11-26 本轮重写时从完整版 README 带入的**。
- 🔴 **需 App/reviewer 决定**：① 删除该表，改为按 06B 两档（stateful GPU/NPU）重写；② 或保留但**逐行标注**
  「此表为完整版 R2T2 的数据，本包（MiniMVP 06B）不适用」；③ 并给出 06B 档的**同口径** RTF/延迟数字
  （🔴 **本模块不给数字**：06B 档的对外 RTF 需 reviewer 用同一计分器测，且与本模块 §83 不可混用）。

## 3. 🟡 其余只读复核（无变化 / 有变化但不影响本模块结论）

- 🟢 **EXT 已推进到 v0.4.22**：HEAD = **`e901cad`**（`EXT v0.4.22 补完：MT 模型名按实际加载的目录推导`），
  前一提交 `d548285`（`EXT v0.4.22: MT3 优先 + NPU turbo 统一判定 + 过期断言改现行契约`）。
  改动范围：`ext/engine_runtime.py`、`ext/version.py`、`extension/manifest.json`、
  `tests/test_ext009_adaptive_speed.py`、`tests/test_ext0422_mt3_turbo.py`、`.gitattributes`。
  ⇒ §101 记录的「HEAD 仍 `b2a4978`」**已过时**（按纪律在 §102 撤回该句，不改旧章节正文）。
- 🟡 **§101.3 归因缺口仍在**（只读确认）：v0.4.22 的 `ext/speaker_bypass.py` 与 `ext/bridge.py` 的
  `_spk_reason_hist()` **逐字未改** ⇒ 旁路失败原因仍进不了段级表。
- 🟡 **修前 v0.4.18 对照臂仍缺**：`shared/bgkeep/` 下无 `v0418*` 目录（只读全盘搜，0 命中）⇒ §96 ① 未闭。
- 🟡 **分离人声 16 kHz wav 仍 0 产出**：`shared/bgkeep/vocals/` 不存在；全盘搜 `*vocal*` **0 命中**
  ⇒ 「原声 vs 分离人声」WER 对比仍做不了。
- 🟡 **对外 NPU 报告 RTF 0.067 口径仍待 reviewer 说明**（§101.5 挂项，未闭）。
- 🔴 **配音迟到**：App146 `bgkeep_off` 臂 `dub_late_max` = **−11.883 s**（负值＝不迟到，因为 ASR 全失败没有内容）
  ⇒ **该数字无效**；`bgkeep_on` 臂同类。⇒ 配音迟到的有效数字仍以 §101 的 r2 臂为准（max **182.62 s**）。

## 4. 纪律

- **本轮全程只读复算**：未跑推理 / 未跑计时 / 未跑 WER / 未跑分离器 ⇒ **不取 `shared/MACHINE_LOCK`**
  （复核时锁由 **App 模块**持有：`app e2e drain 2026-11-26T14:39:25 pid=28448`，14:39:25 取锁；
  本模块**始终未取锁、未干扰**）。
- 未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未打包；
  未改客户包；未调 MiniMax；未连 B 机。
- 本模块**未自行开新实验**（ASR-038）；只做状态维护 ＋ 报告新发现。
- **未提交**（见 §102 章节「纪律」行）。
- **产物清单**：本文件 `status/asr/notes/asr_s102.md`（LF）＋ `status/asr/STATUS_ASR.md` §102（**39 927 B / 152 行**）＋ `status/archive/STATUS_ASR_sec102_upto_20261126.md`（§101 全文逐字归档，**9 762 B**）。
