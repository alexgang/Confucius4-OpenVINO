# ASR §92 明细（2026-11-23 12:30–12:40）

> 本轮 = **纯巡检 ＋ 完成 §91 遗留的本模块文档职责**（handoff 前提表述改写）。
> 🔴 未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 `live_caption/`、未改纠偏文件、未改旧章节。

## 一、纠偏通道 ＋ 邮箱（本轮只读）

| 通道 | 结果 |
|---|---|
| `CORRECTIONS_ASR.md` | **105 868 B** / md5 **`b6fd2e14…`** / mtime **2026-11-20 15:33** ⇒ 最大编号 **ASR-066**、**无 ASR-067+** ⇒ `last_ack` **保持 ASR-066** |
| QQ 收件箱 | **无新 ASR 邮件**。最新 = reviewer 的 **APP-121**（11-23 09:03，已于 §89 回复）；同批另有 **TTS-077**（11-23 10:34）、**TTS-076**（11-23 10:15）、**MT H-027**（11-20）、**APP-120/119**（11-20/11-22）⇒ **均非本模块**（ASR/MT/TTS/App 各写自己的 STATUS） |
| 垃圾箱 | 空 |

## 二、本轮唯一实质动作：改本模块自己的 handoff

**文件**：`qwen3asr_06b/dev/asr065_handoff.md`
**规模**：**18 295 B / LF 348 行** → **23 091 B / LF 409 行**（**LF 保持不变**，末尾 LF）
**备份**：`qwen3asr_06b/dev/asr065_handoff.md.bak_asr092`（18 295 B）

### 2.1 改了什么（6 处）

| # | 位置 | 原文（要点） | 改后 |
|---|---|---|---|
| ① | **§三之二** | 「段长 ≤ `MAX_SEG_SEC` = 20.0 s（实测最长 20.48 s）⇒ `base_len ≤ 284 ≤ 320` ⇒ **余量 36 token** ⇒ **永不触发**」 | 「**这句只对骨架成立，对整条 prompt 不成立**」⇒ **两条同时成立**：（a）段长上限 `base_len ≤ pml`；（b）**段内累积前缀 ≤ `pml − 18 − 音频 token`**」＋「**余量 36 只够骨架、不够带前缀**」＋ **新增 NPU 档段长→预算对照表** ＋ 澄清 §七「T 最大 285」是总长口径、勿与 `skeleton` 混用 |
| ② | **§四** | 「⚠️ **正常素材不会触发**（实测 3 素材各 1 轮 ⇒ 计数 0、transcript 逐字节不变）」 | **三口径对照表**：ASR 参照 15 臂 = **0** / **App 生产路径 NPU 档 ZH = 3** / App GPU.0 档 = **0** ⇒ 「**计数 0 是参照口径＋该素材的性质，不是契约保证**」＋ 质量限定「**机制成立、未见可见损失**」＋「最长前缀 43 vs 预算 36 已贴边」 |
| ③ | **§三**（新增段） | — | 「🔴🔴 **从左截断 ＝ 会丢句首 ⇒ 越界不是『无害』**」＋ 写明**不要**写成「已证实丢句首」 |
| ④ | **§七 验收表**（2 行） | 「正常素材触发降级次数 = **0**（15 臂全程 total=0）」；「真实流水线 T_max = **313**」 | 触发次数改三口径；`T_max` 注明 **29 是参照口径前缀** ＋ 补「**App 口径 18+266+43 = 327 > 320 ⇒ 越界 7 token**」 |
| ⑤ | **§七 前提第 2 条** | 「段长 ≤ `MAX_SEG_SEC` = 20.0 s ⇒ 加 §三之二 的自检」 | ＋ 前缀约束 ＋ **按 0.64 s 分块粒度算的 `MAX_SEG_SEC` 建议值**（19.0 → 实际 19.20 s ⇒ 预算 52；19.5 → 实际 19.84 s ⇒ 预算 44） |
| ⑥ | **§八 口径提醒** | 「段长前提：pml=320 成立的前提是段长 ≤ 20.0 s（⇒ 余量 36 token）」 | ＋「🔴🔴 **余量 36 token 只够骨架，不够带前缀** ⇒ 真正的约束是『**段长上限 ＋ 段内累积前缀 ≤ pml − 18**』」 |

### 2.2 新增的对照表（本轮用 `bk_mel.total_aftercnn_len` 同公式复算，纯算术、**无推理**）

`frames = 秒 × 100`；`音频 token = total_aftercnn_len(frames)`；`skeleton = 18 + 音频 token`；`allowed_prefix = 320 − skeleton`（NPU 档 pml=320）：

| 段长上限（s） | mel 帧 | 音频 token | skeleton | **allowed_prefix** |
|---|---|---|---|---|
| 18.56 | 1856 | 241 | 259 | **61** |
| 19.20 | 1920 | 250 | 268 | **52** |
| 19.84 | 1984 | 258 | 276 | **44** |
| **20.48（现状 `MAX_SEG_SEC = 20.0`）** | 2048 | 266 | 284 | **36** |
| 21.00 | 2100 | 273 | 291 | 29 |
| 22.00 | 2200 | 286 | 304 | 16 |
| 23.24 | 2324 | 302 | 320 | 0（骨架临界，截断救不了） |

### 2.3 🟡 本轮新算的 2 个事实（订正 §91 的估算）

- 🟢 **（a）App 实际最长段 20.48 s 是分块粒度造成的**，不是切段器偶然：
  - `live_caption_app.py` L566 `MAX_SEG_SEC = 20.0`；L525 `CHUNK_SEC = 0.64`；L1816 `if dur >= MAX_SEG_SEC: return True`
  - ⇒ 第一个 ≥20.0 s 的块倍数 = **32 × 0.64 = 20.48 s**
  - ⇒ L626 注释「**实测 20.48s 一段**」自证
  - 🔴 **含义**：**段长不是连续可调的**，只能落在 `k × 0.64` 上 ⇒ 调 `MAX_SEG_SEC` 的效果是**阶梯式**的。
- 🔴 **（b）「`MAX_SEG_SEC` 调到 19.0 s」实际拿到的是 19.20 s**（30 × 0.64）⇒ `skeleton = 18+250 = 268` ⇒ `allowed_prefix = **52**`
  - ⇒ 🔴 **订正 §91 的估算**（§91 写「`skeleton ≤ 275` ⇒ `allowed_prefix ≥ 45`」）⇒ **实际是 52** ⇒ **建议值从「≈19 s」明确为 19.0 s**（余量 9 token，覆盖实测最长前缀 43）。

### 2.4 原始字段复核（本轮独立读 json）

`results/app/app121_asr_app_3mat_NPU.json`（56 845 B / 11-23 09:45）：
- `materials[0].prefix_truncations = 0`、`materials[1].prefix_truncations = 0`、**`materials[2].prefix_truncations = 3`**（`materials[2]` = ZH）
- `backend_class` = `…MiniMVP_v1.1.1\app\live_caption_app.py.asr06b_stateful_backend.ASR06BStatefulBackend`
- `env.ov_version` = `2026.4.1-22982-e213a147257-releases/2026/4`

`results/app/app121_asr_app_3mat_GPU0.json`（56 815 B / 11-23 09:54）：三素材 `prefix_truncations` **全 0**、`ov_version` 同。

⇒ 🟢 **§91 的「NPU=3 / GPU.0=0（同素材、同切段）」经本轮独立复核成立。**

## 三、本轮做了什么 / 没做什么

- 🟢 **做了**：租约 acquire/beat/release；读 `CORRECTIONS_ASR.md`（md5/size/mtime/编号）；列 QQ 收件箱与垃圾箱；改 `qwen3asr_06b/dev/asr065_handoff.md`（6 处，含 1 张新对照表）；用 `bk_mel.total_aftercnn_len` 同公式复算段长→前缀预算（含 0.64 s 分块粒度的阶梯）；读 `live_caption_app.py` L525/L566/L626/L1816 自证分块粒度；读 `app121_asr_app_3mat_{NPU,GPU0}.json` 复核原始字段。
- 🔴 **没做**：未跑任何推理/计时（**未取 MACHINE_LOCK**）；未改交付包、**未打包**；未改 `live_caption/`；未改纠偏文件；未改旧章节（§91 已逐字归档）；未代做 App 线程作业（`MAX_SEG_SEC` 的改动属 App 树，本模块**只提方案**）。
- **产物**：本文件 `status/asr/notes/asr_s92.md`（**LF**）＋ `status/asr/STATUS_ASR.md` §92 ＋ `qwen3asr_06b/dev/asr065_handoff.md`（**改后 23 091 B / LF 409 行**，备份 `.bak_asr092`）。
