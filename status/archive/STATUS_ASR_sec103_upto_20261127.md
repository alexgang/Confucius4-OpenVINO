# STATUS_ASR §103 归档（§102 全文逐字）

> 归档时间 2026-11-27 15:05；来源 `status/asr/STATUS_ASR.md.bak_asr104`（§104 写入前的基线，39 986 B / 152 行）。
> 格式与 `status/archive/STATUS_ASR_sec102_upto_20261126.md` 一致（全文逐字，不改一字）。
> 本文件是 §102 的唯一归档副本；正文 `status/asr/STATUS_ASR.md` 只留一行摘要。

---

### §102 巡检（无新 ASR 纠偏，`last_ack` 仍 **ASR-068**）＋ 🔴🔴 **新发现 1：MiniMVP v1.2 候选包插件侧（EXT）ASR 引擎 100% 加载失败（123/123 段全错）** ＋ 🔴 **新发现 2：README「四种 ASR 后端」表与包内实际引擎集不符**（2026-11-26 14:40–14:55）

> 🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，与 §96–§101 逐字相同；`^## ASR-` 标题 **37** 条、最大编号 **ASR-068**；搜 `ASR-069` **0 命中**；根 `status/CORRECTIONS.md` 内 ASR 编号条目 **0**）。邮件 after 2026-11-24T12:00:00Z 共 **3 封全部非 ASR 编号**（T-008／H-030／APP-140）⇒ 不进本模块 `last_ack`；主题含 `[CORRECTION][ASR]` 的最大编号仍 **ASR-068**；spam **0**、trash **1**（rc9 报告，非纠偏）。
> 🔴 **本轮不是纯巡检 ⇒ 有实质变化（2 条新发现）⇒ 写 §102 ＋ 发 STATUS 邮件**。**全文明细 ⇒ `status/asr/notes/asr_s102.md`（12 470 B / LF）**。

#### §102.1 🔴🔴 新发现 1：MiniMVP v1.2 候选包**插件侧（EXT）ASR 引擎 100% 加载失败** ⇒ App-146 三轮的 ASR 侧数字全部无效

- 🔴 **事实（App 产物，本模块只读复算）**：`shared/bgkeep/e2e_app146/` 四臂 —— `smoke`（14:01）**ASR 失败 13 次**、`smoke2`（14:05）**13 次**、`three_arms/bgkeep_off`（14:28–14:39，600 s 整段）**123 次（＝全部段）**、`three_arms/bgkeep_on`（14:39–14:49）**120 次**。
- 🔴 **失败原文**（`three_arms/bgkeep_off/bgkeep_off_1/bridge.log` L6–L13）：`(1/3) ASR（R2T2 INT8） 加载失败 ⇒ EngineNeedsChange: [R2T2] SegmentEncoderOVBackend 构造失败（device=GPU.0）: … ir: Could not open the file: "…/Confucius4_LiveCaption_MiniMVP_v1.2.candidate/models/encoder-int8/openvino_encoder_model.xml"` ⇒ **MT（Hy-MT3）／TTS 正常加载，只有 ASR 起不来**；桥接**不中止**（预热失败只告警）⇒ **每段都走 ASR 异常分支**，段级日志全是 `ASR='—' | MT='—' | TTS=0.00s`。
- 🔴 **`stats_full` 原始字段**（`three_arms/bgkeep_off/bgkeep_off_1/bgkeep_e2e.json`，**44 846 B** / mtime 11-26 14:39）：`asr_segments`=**0**、`mt_segments`=**0**、`tts_segments`=**0**、`pipeline`={"n_submitted":123,"n_emitted":123,"n_error":**123**,"n_pending":0,"stage_wall_sec":{"asr":8.168,"mt":0.001,"tts":0.003}}、`spk_bypass.enabled`=**false**、`spk_reason_hist`={none:123}、`clone_reasons`={}、`n_gender_splits`=0、`speaker.n_speakers`=0 / `n_pending_unassigned`=123 ⇒ 🔴 **`n_error`＝`n_submitted`＝123 ⇒ 整条链路 123 段全是错误**。
- 🔴 **根因（读代码确认）**：EXT 的 ASR 目录**写死**（`ext/bridge/engine_runtime.py` L85–86，v0.4.22 与 v0.4.21 逐字相同）`ASR_ENCODER_DIR = …/encoder-int8`、`ASR_DECODER_DIR = …/decoder-gpu-int8` ⇒ **只支持 R2T2 1.7B**；🟡 而 MiniMVP 包只带 **Qwen3-ASR-0.6B**（`app/live_caption_app.py` L895–922 的 `asr06b` 族）⇒ **EXT 侧无任何 06B 接线代码**（全仓 `ext/` 搜 `06b`／`stateful` ⇒ **0 命中**）；🔴 包内 `models/` 实测**无 `encoder-int8`／`decoder-gpu-int8`** ⇒ 加载必然失败。
- 🟢 **不是 EXT 新回归，是「EXT 只支持 R2T2」与「MiniMVP 只带 06B」的固有错配**：对照完整版 v2.6 的 App134b／App134c 臂 `pkg` 都是 `Confucius4_LiveCaption_v2.6`（有 `encoder-int8`＋`decoder-gpu-int8`）⇒ ASR 正常。
- 🔴 **影响面（必读：含已发客户的包）**：🟢 `MiniMVP_v1.2.candidate` 的 `README_zh.md` L387–390 **已明写**「插件（EXT）侧的语音识别在本包不可用」（该段是 **11-26 14:04 本轮重写时新增**）；🟢 **已发客户的 `MiniMVP_v1.1.1.zip`（5 212 403 155 B／11-23 10:31:48）同样错配**（zip 内 `models/encoder-int8/openvino_encoder_model.xml` **ABSENT**、06B 编码器 **PRESENT**）**且 README 已明写**「已知问题 4. ⚠️ EXT 的 ASR 在本版不可用」⇒ **两版都不是「悄悄坏了」**。
- 🔴 **但对 App 发版流程有实质影响**：App-146 第 4 步的三轮 e2e 是在「ASR 引擎起不来」的前提下跑的 ⇒ **三轮的 ASR 侧数字（段数、dubs、`clone_reasons`、`spk_reason_hist`、`dub_late`）全部无效**（该臂 `dub_late_max`=**−11.883 s**，负值＝因为根本没有内容）⇒ **APP-147 自查条件 1「没有模块起不来」按字面已不满足** ⇒ **建议打 zip 前补一轮「ASR 引擎可用」的臂，或明确把「插件侧 ASR 不可用」写进自查条件**。
- 🟢 **不涉及 ASR 模型本身的精度/性能**（06B 后端在 App 侧 `live_caption_app.py` 的 `asr06b` 族是通的；本轮未改 4 个 ASR 交付文件）；🔴 但它使 §96–§101 的旁路/说话人链路结论**在新候选包上无法复算** ⇒ App146 臂的 `spk_reason_hist`／`clone_reasons`／`n_gender_splits` **不能**作为 §101.3 的证据。
- 🔴 **EXT 侧适配 0.6B（stateful）是 EXT/App 的事，本模块不代改 EXT 源码**（EXT 源码由 reviewer 写）。

#### §102.2 🔴 新发现 2：README「四种 ASR 后端」表与 MiniMVP 包内实际引擎集不符（需 App/reviewer 拍板）

- 🔴 v1.2 候选 `README_zh.md` L140–158 **仍保留完整版 v2.x 的「四种 ASR 后端」表**：Intel GPU·INT8（编码器 INT8＋解码器 INT8，RTF **0.70**）／GPU·INT4（**0.73**）／NPU·INT8（编码器 FP16＋解码器 INT8，**0.86**）／NPU·INT4（**0.75**），并写「61 分钟英文会议录音的完整测试中，Intel NPU · INT8 的整体 RTF 为 **0.77**」。
- 🔴 **但包内实际只有 06B 的两个后端**（`app/live_caption_app.py` L914–922 `ENGINES_ASR06B`：`gpu_int8` =「Intel GPU · INT8 (stateful)」、`npu_int8` =「Intel NPU · INT8 (stateful)」）⇒ **没有 INT4 档**（`asr06b_gpu_int4`／`asr06b_npu_int4` 全仓 **0 命中**）；🔴 **包内也没有任何 INT4 模型目录**（`models/` 下无 `*int4*`）。
- 🔴 **那四个 RTF 是 R2T2（完整版）口径**，而本包跑 **06B stateful**；🔴 **与本模块 §83／ASR-060～061 也不是同一计分器**（本模块 NPU 流式 RTF 0.3094／0.2912／0.3165、离线 0.0496／0.0448／0.0665）⇒ **与 §101.5 已挂的「对外 NPU 报告 RTF 0.067 口径」属同一类问题、但来源不同**（那封是 reviewer 自发报告，**这份是客户包 README**）。
- 🟢 **v1.1.1（已发客户）无此问题**：其 `README_zh.md` **不含**「四种 ASR 后端」／「0.70」／「61 分钟」，且明确 `--engine` 只有 `gpu_int8`／`npu_int8` ⇒ **该表是 11-26 本轮重写时从完整版 README 带入的**。
- 🔴 **需拍板**：① 删除该表、改为按 06B 两档重写；② 或逐行标注「此表为完整版 R2T2 数据，本包不适用」；③ 并给出 06B 档**同口径**的 RTF/延迟数字 ⇒ 🔴 **本模块不给该数字**（需 reviewer 用同一计分器测，且与 §83 不可混用）。

#### §102.3 🟢 EXT 已推进到 v0.4.22 ⇒ 撤回 §101「HEAD 仍 `b2a4978`」；🔴 §101.3 归因缺口仍在；🟡 旧开口项无变化

- 🟢 **EXT v0.4.22**：HEAD = **`e901cad`**（`EXT v0.4.22 补完：MT 模型名按实际加载的目录推导`），前一提交 **`d548285`**（`EXT v0.4.22: MT3 优先 + NPU turbo 统一判定 + 过期断言改现行契约`）⇒ §101 记录的「HEAD 仍 `b2a4978`」**已过时、撤回该句**（不改旧章节正文）。
- 🔴 **§101.3 归因缺口仍在**（只读确认）：v0.4.22 的 `ext/speaker_bypass.py`（失败分支只 `n_no_label += 1`、**不写行**）与 `ext/bridge.py` 的 `_spk_reason_hist()`（L2145–2153）**逐字未改** ⇒ **旁路失败原因仍结构上进不了段级表** ⇒ 需 reviewer 让**失败路径也写行**（或由 `spk_bypass.stats()` 导出否定 reason 计数）。
- 🟡 **修前 v0.4.18／`5121d99` 对照臂仍缺**（`shared/bgkeep/` 下**无** `v0418*` 目录）⇒ §96 ① 未闭。**分离人声 16 kHz wav 仍 0 产出**（全盘搜 `*vocal*` **0 命中**）⇒「原声 vs 分离人声」WER 对比仍做不了。**对外 NPU 报告 RTF 0.067 口径仍待 reviewer 说明**（§101.5 挂项，未闭）。
- 🔴 **配音迟到的有效数字仍以 §101 的 r2 臂为准**（max **182.62 s**）；App146 臂的 `dub_late_max` 因 ASR 全失败**无效**。

#### §102.4 纪律

- **本轮全程只读复算**：未跑推理／未跑计时／未跑 WER／未跑分离器 ⇒ **不取 `shared/MACHINE_LOCK`**（复核时锁由 **App 模块**持有：pid=28448）⇒ 本模块**始终未取锁、未干扰**。
- 未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未改客户包；未打包；未调 MiniMax；未连 B 机；未自行开新实验（ASR-038）。- **已发 STATUS 邮件**（T-MAIL-003）：`msg_cwHjmlBsyrItRVZfVc9LRu_RmDpZYbRvuOdcxy3dAMRJVQ`（**07:00:26Z**）；正文留档 `_asr102_email_body.txt`。
- 产物：`notes/asr_s102.md`（LF）＋ `STATUS_ASR.md` §102 ＋ `status/archive/STATUS_ASR_sec102_upto_20261126.md`（§101 全文逐字归档）。
