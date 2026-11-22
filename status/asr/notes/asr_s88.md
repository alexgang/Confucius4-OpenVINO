# §88 明细：APP-120 §0 —— ASR-065/066 优化接入复核（ASR 线程）

> 🔴 **本轮性质**：reviewer 的 **APP-120**（App 模块纠偏，2026-11-22 13:26）
> **§0 要求 ASR 线程在 STATUS 里逐项回答 ASR-065/066 是否已接入**，并给代码位置。
> 🔴 **纠偏文件通道**：本轮 **`CORRECTIONS_ASR.md` 无新条目**
> （105 868 B / md5 `b6fd2e14…` / mtime 2026-11-20 15:33 ⇒ 与前 20+ 轮逐字相同；
> 35 个 `## ASR-` 标题、最大 **ASR-066**、搜 ASR-067+ **0 命中**）
> ⇒ **`last_ack` 保持 `ASR-066`**。
> 🔴 **本轮是只读复核 ＋ 文档**：**未跑任何计时**、**未取 MACHINE_LOCK**
> （全程锁不存在）、**未改交付文件**（`live_caption/` 由 App 在 `1af497d` 提交）、
> **未打包**、**未改 `CORRECTIONS_ASR.md`**。
> 明细：本文件。

---

## 〇、结论（一行）

🟢 **ASR-065/066 的全部 4 项优化，已确认接入客户包
`Confucius4_LiveCaption_MiniMVP_v1.1`**（App 侧提交 `1af497d`）；
**NPU 臂三素材转写与 §86 参照逐字节相同**。
🔴 **但复核中发现 1 个此前未记录的 ASR 口径问题（§四）**：
**§86/§87 的参照 md5 是「NPU 专属」的**，而**出厂默认 ASR 档是 GPU.0**
⇒ **GPU.0 与参照 md5 不同（已证明是跨加速器数值差异，非回归）**。

---

## 一、§0 逐项回答（代码位置 = 客户包 `Confucius4_LiveCaption_MiniMVP_v1.1/app/`）

### ✅ ① `NPUW MAX_PROMPT_LEN=320` ＋ 超长前缀按 token 左截断（**默认开**）

| 项 | 代码位置（包内 `app/asr06b_stateful_backend.py`） | 状态 |
|---|---|---|
| `NPUW_LLM_MAX_PROMPT_LEN: '320'` | **:75** | ✅ |
| `NPUW_LLM_MIN_RESPONSE_LEN: '64'`（不变） | **:76** | ✅ |
| 实际生效上界按设备定（NPU⇒320 / GPU⇒512） | **:325-327** `self._max_prompt_tok` | ✅ |
| 前缀**从左**截断（保留右端＝最新内容） | **:561** `prefix_ids = prefix_ids[drop:]` | ✅ |
| 截断**单独计数** `prefix_truncations` | **:564**（+ :91 常量定义） | ✅ |
| **不抛错、不回退 512**（用户 11-20 定） | **:547** 注释明示；实现在 :561-569 | ✅ |

> ⚠️ **口径提醒**：`MAX_PROMPT_LEN=320` 是 **NPUW（NPU 档）** 的属性；
> **GPU.0 档不走 NPUW** ⇒ 仍可用 IR 硬上界 **512**（:545-546 明示）。

### ✅ ② `asr_enc_tiers` **默认 off** ＋ 分档失败自动退回 2400 单档

| 项 | 代码位置 | 状态 |
|---|---|---|
| 开关读取（`ASR_ENC_TIERS` ∈ {1,on,true,yes}） | **:99-112** `_env_tiers_enabled()` | ✅ **默认 off** |
| 档位 `{400,800,1600,2400}` | **:85** `ASR_ENC_TIERS` | ✅ |
| **回退实现（构建处）**：任一档失败 ⇒ `tier_cms={}` ＋ 记 `fallback_reason` | **:216-255** `build_tiers_with_fallback()` | ✅ |
| **回退实现（调用处）**：`fallback_reason` 非空 ⇒ **强制 `use_tier=False`** | **:361-365**（`self.asr_enc_tiers = False`） | ✅ |
| probe 字段 `enc_tiers_fallback_reason` | **:96** 常量 ＋ **:416** 写入 probe | ✅ |
| CLI 开关 `--asr-enc-tiers on\|off`（默认 None ⇒ 仍 off） | `app/live_caption_app.py` **:9472**、:9483 | ✅ |

> 🔴 **App 本轮修掉的真缺陷**：旧实现**只 `break`、仍以 `use_tier=True` 建 runner**
> ⇒ 缺档时 `encode()` 抛「tier N 未编译」⇒ **根本没回退**。
> 本轮按 ASR-066 §2（handoff §5.1）**补齐两处**（`1af497d` diff 已复核）。

### ✅ ③ 前提条件（`max_new ≤ 64` / 段长 ≤ 20 s / `base_len > pml` 显式报错）

| 项 | 位置 | 状态 |
|---|---|---|
| `max_new ≤ 64`（KV = 320+64 = **384**） | 交接单 `dev/asr065_handoff.md` §四；`bk_run` 的 `FLUSH_MAX_NEW=64` | ✅ 现状满足 |
| 段长 ≤ `MAX_SEG_SEC = 20.0` s | `app/live_caption_app.py` **:566** `MAX_SEG_SEC = 20.0`；:1816 硬切 | ✅ |
| 段长上限在分段器侧 | `app/seg_stream.py` :181 `max_segment_sec: float = 20.0` | ✅ |
| encoder 静态上限 2400 mel 帧（= 24.0 s） | `app/asr06b_stateful_backend.py` **:48** `ENC_MAX_FRAMES = 2400` | ✅ |
| **`base_len > pml` 显式报错** | `app/asr06b_stateful_backend.py` **:554-558**（`allowed_prefix < 0` ⇒ `raise ValueError('prompt 骨架 %d + 预留 %d > stateful 上界 %d（音频过长）'）`） | ✅ |

> ⚠️ **精确表述**：交付代码里的报错文案是「**prompt 骨架 + 预留 > stateful 上界**」，
> 与 handoff §四 的 `base_len > pml` 是**同一判据**（`base_len`＝18+音频 token＝骨架）
> 的两种写法 ⇒ **语义等价，不是缺项**。

### ✅ ④ 包内 python 跑 §86 三素材（SPE/EN/ZH）：转写 md5 ＋ NPU/GPU.0 两档 RTF

**产物**：`confucius4-openvino/results/app/app120_asr_3mat_NPU.json`（4146 B，mtime 11-22 14:20）、
`app120_asr_3mat_GPU0.json`（4152 B，14:25）、`app120_asr_3mat_GPU0_pml512.json`（4167 B，14:31）
＋ `app120_asr_gpu0_vs_asrmodule_baseline.json`（1406 B，16:38）。
**环境**：包内 python 3.12.10、**OV `2026.4.1-22982-e213a147257`**（🔴 **与 §86 参照同版本**，口径纪律成立）、
transformers 4.57.6、`timing_valid=true`、`lock_probe_stolen=0`（4 次自检）。

**NPU 臂（`pml=320`、`use_tier=false`）—— 与 §86 参照**逐字节相同**（`all_md5_match=true`）**：

| 素材 | 转写 md5 | 参照 md5（§86） | 一致 | RTF | `prefix_truncations` | `enc_tiers_fallback_reason` |
|---|---|---|---|---|---|---|
| SPE | `cd67417e64ae6009c0b703453f7c5316` | `cd67417e…` | ✅ `bytes_identical=true`（11 850 B） | **0.2754** | 0 | `null` |
| EN | `ed3f52aaf1415ca01d785da4e3a78cb4` | `ed3f52aa…` | ✅ `bytes_identical=true`（6 658 B） | **0.2483** | 0 | `null` |
| ZH | `d93062a686fc1e647b34f4a813bad01d` | `d93062a6…` | ✅ `bytes_identical=true`（6 211 B） | **0.2416** | 0 | `null` |

**GPU.0 臂**：

| 素材 | 转写 md5 | 与参照 | RTF（pml=320） | RTF（pml=512 对照） |
|---|---|---|---|---|
| SPE | `e9f783ab391bec1190e13e5602454bd8` | ❌ 不同（11 861 B vs 11 850 B） | **0.2126** | 0.2039 |
| EN | `f8384c408fe9eea0e783689320bb9fe0` | ❌ 不同（6 659 B vs 6 658 B） | **0.1829** | 0.1791 |
| ZH | `812873dfd2e5edad4aeb7fd2d2ac2e1a` | ❌ 不同（6 211 B，词级 1 处差异） | **0.1722** | 0.1685 |

> 🔴 **GPU.0 的 md5 差异 ≠ App 接入引入的回归**：
> **GPU.0 pml=320 与 pml=512 两臂 md5 完全相同** ⇒ 差异**与 pml 无关**；
> 且 App 的 GPU.0 三素材转写与 **ASR 模块自己 11-19 的 GPU.0 基准**
> （`qwen3asr_06b/results/asr162/_smoke_gpu/`）**逐字节相同**
> （`e9f783ab…` / `f8384c40…` / `812873df…`，`md5sum` 独立复核）
> ⇒ **零回归**；差异全部来自 **NPU(NPUW/INT8) vs GPU.0(OV GPU/FP32) 跨加速器数值差异**。

---

## 二、🔴 §0 复核中发现的、此前 STATUS 未记录的 ASR 口径问题（**本轮唯一的新结论**）

### 2.1 问题：§86/§87 的参照 md5 是「**NPU 专属**」的

- §86/§87 的参照 md5（SPE `cd67417e` / EN `ed3f52aa` / ZH `d93062a6`）
  来自 `results/asr165_ov241/`，其 `session.json` / `bench.json` 明确记 **`"device": "NPU"`**。
- 而 **APP-119 定的出厂默认是 `ASR = GPU.0`**（`app/device_config.py` `_DEFAULT_DEVICES_FULL['asr'] = 'GPU.0'`；
  MiniMVP 的 `_DEFAULT_DEVICES_MINIMVP` 同形）⇒ **客户机默认跑的是 GPU.0 档**。
- ⇒ **在 GPU.0 上拿 §86 的参照 md5 做「逐字节相同」判定，必然失败**。
  这**不是**回归，但会让人误判。

### 2.2 量化（本轮用包内 transcript 与 §86 参照做的词级比对，`difflib` 词序列）

| 素材 | GPU.0 词数 | 参照词数 | 相同词 | 差异词 | **词级差异率** |
|---|---|---|---|---|---|
| SPE | 1 773 | 1 769 | 1 748 | 26 | **1.4664 %** |
| EN | 877 | 878 | 875 | 3 | **0.3417 %** |
| ZH | 214 | 214 | 213 | 1 | **0.4673 %** |

⇒ **量级 0.34–1.47 %**，是**跨加速器浮点噪声**的典型规模，**不是**系统性错误。
（抽查差异内容：如 `…and go through…` vs `…, go through…`（标点/连读）、
`I'll expect to` vs `Alex spoke to`（近音混淆）、`physicality` vs `physical`。）

### 2.3 结论写法（**建议口径**，供 reviewer 决定是否要改写 §86/§87 的表述）

🔴 **§86/§87 的「转写 md5 与参照逐字节相同」这句话，隐含前提是「同一设备（NPU）＋ 同一 OV 版本（2026.4.1）」。**
在**非 NPU 设备**上，**同一份代码**就会得到不同 md5 ⇒
**「md5 逐字节相同」应当被明确标注为 NPU 档 + OV 2026.4.1 口径下的判据**。

⚠️ **本轮未改写 §86/§87**（纪律：**不回头改旧章节**）⇒ 记在此处 ＋ 正文 §88。

### 2.4 另一处配套事实：`pml=320` 的 RTF 收益**只对 NPU 档成立**

- §86 的 pml 降幅（−13.72 / −22.34 / −17.94 %）测的是 **NPU 档**。
- GPU.0 档**不走 NPUW** ⇒ `NPUW_LLM_MAX_PROMPT_LEN=320` 对 GPU.0 **无作用**
  （`app/asr06b_stateful_backend.py` :325-327：GPU 档 `_max_prompt_tok = MAX_STATEFUL_TOK = 512`）。
- 本轮 GPU.0 的 pml=320 / pml=512 对照臂 RTF 分别为 0.2126/0.2039、0.1829/0.1791、0.1722/0.1685
  ⇒ 差 **≈ −4 %**（**不是** §86 的 −14 % ~ −22 %）⇒ **与「pml 在 GPU.0 无效」一致**
  （差值来自 harness 侧 `max_prompt_len` 参数，不是 NPUW 属性）。

---

## 三、§0 之外：App 侧待落地 3 项的**当前状态**（ASR 线程只读核对，不代做）

| 项 | 状态 | 证据 |
|---|---|---|
| ASR 文件进 v2.3 / MiniMVP ＋ `ASR_FILES` 4→6 | ✅ **已进 MiniMVP v1.1**：`app/asr_spk/` 含 **6** 个文件（`asr052_speaker_tracker_api.py`、`asr052_spk_runtime.py`、`asr_runtime_switches.py`、`asr_spk_cluster_v2.py`、`asr_spk_window.py`、`asr_thread_defaults.py`） | 包内 `app/asr_spk/` 实测 |
| 5 s **静态** seg IR 进 `models/spk/pyannote_seg_3_0/fp16-w5/` | 🟡 **v2.5 有、MiniMVP v1.1 没有**：`Confucius4_LiveCaption_v2.5/models/spk/pyannote_seg_3_0/fp16-w5/`（2 文件：`pyannote_seg_3_0_w5.bin/.xml`）在；**MiniMVP v1.1 `models/` 下无 `spk/` 目录**（只有 asr06b-decoder-int8 / asr06b-encoder-fp16 / asr06b-tokenizer / embed_tokens_06b_f16.npy / mt / qwen3tts）⇒ 🔴 **说话人识别（`--speaker on`）在 MiniMVP v1.1 上无 seg IR 可用** ⇒ 与 APP-120 §1「MiniMVP 不带说话人模型」一致（出厂默认 `--speaker off`） | 包目录实测 ＋ v2.5 目录实测 |
| App 侧 import `asr_runtime_switches` ＋ 实现 `LIVECAP_SPK_MIN_CLEAN_RATIO` | ✅ **已实现**：`app/speaker_tracker.py` :206 `_MIN_CLEAN_RATIO_ENV = 'LIVECAP_SPK_MIN_CLEAN_RATIO'`、:209 兜底 0.6、:213-268 **从 ASR 侧源码读 `DEFAULT_MIN_CLEAN_RATIO`（同源）**；`app/asr_spk/asr_runtime_switches.py` 随包在（:80 `import asr_runtime_switches as SW`） | 包内 grep |

---

## 四、纪律（本轮）

- 🔴 **未跑任何计时**（App 的 RTF 数字**全是原值**，本轮只做只读复核与词级比对）。
- 🔴 **未取 MACHINE_LOCK**（`shared/MACHINE_LOCK` 全程**不存在**；本轮未做计时/测速 ⇒ 无需持锁、不需回收）。
- 🔴 **未改交付文件**（`live_caption/asr06b_stateful_backend.py` 的改动由 **App** 在 `1af497d` 提交 ⇒ **ASR 线程未动 `live_caption/`**）。
- 🔴 **未打包**（MiniMVP v1.1 的 zip 由 App 打出：**5 212 356 737 B / 10 881 文件**，
  `results/app/_app120_zip_v11.log`；ASR 线程**不重复打包**）。
- 🔴 **未改 `CORRECTIONS_ASR.md`**（本轮**无新 ASR 纠偏条目**）。
- 🔴 **未改旧章节**（§86/§87 的原文**一字未动**；§87 已逐字归档）。
- 🔴 **`last_ack` 保持 `ASR-066`**（本轮无新 ASR 纠偏条目；触发源是 reviewer 的 **APP-120** 邮件）。
- 🟡 **质量判定未做**：GPU.0 vs NPU 的 0.34–1.47 % 词级差异**未做 WER/CER 判定**
  ⇒ 按纪律**交 reviewer 用 MiniMax 回转写判定**，目标机不自己调 MiniMax。
