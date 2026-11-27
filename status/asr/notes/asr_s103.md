# ASR §103 明细（2026-11-26 18:01–18:30）

> 承接上一会话（TAKEOVER，note「最终复核：10 臂 ASR 字段汇总完毕，准备写 §103」）。
> 上一会话 token `4b4f50a4`，start 11-26 16:02:49，last_beat 16:23:17（98 min 前），`live_pids` 空 ⇒ 已死。
> 本轮 token `9fce2ba3`，acquire 时打印 TAKEOVER（陈旧租约）⇒ 按 ASR-039 从断点继续，未从头重做。

## §103.0 两条通道（纠偏 / 邮件）均无新 ASR 条目 ⇒ `last_ack` 保持 **ASR-068**

### 纠偏通道

- `status/asr/CORRECTIONS_ASR.md`：**109 822 B** / md5 **`3d25680748cf7934fe172f3bb372ec1a`** / mtime **2026-11-23 16:55:15** ⇒ 与 §96–§102 逐字相同（**未变**）。
- `^## ASR-` 标题最大编号 = **ASR-068**；搜 `ASR-069`/`ASR-07[0-9]` = **0 命中**。
- 根 `status/CORRECTIONS.md`（262 907 B / mtime 2026-11-25 22:04:31）内 ASR 编号条目 = **0**。
- ⇒ **无新纠偏条目** ⇒ `last_ack` 保持 **ASR-068**。

### 邮件通道（QQ 邮箱 `1985197690@qq.com`）

- 收件箱 after 2026-11-24T00:00:00Z 共 **12 封**，**全部非 ASR 编号**：APP-140（11-25 10:29:30Z）／H-030（11-25 10:29:26Z）／T-008（11-25 00:56:56Z）／H-028（11-24 10:11:12Z）／NPU 报告（11-24 07:46:40Z）／QQ 授权通知（11-24 07:13:42Z）／APP-133／APP-132／APP-131／APP-130／APP-129。
- 主题含 `[CORRECTION][ASR]` 的邮件最大编号仍 = **ASR-068**（`msg_tHwjDsvTKlufBDo6pyhm4IB3rG6j2nvzS3L_58wMzPidDQ`，11-23 08:55:15Z）。
- ⇒ **无 reviewer 新 ASR 邮件** ⇒ 不进本模块 `last_ack`。

## §103.1 🟢🟢 关键进展：EXT **v0.4.23 已修好 §102 报出的 06B 错配**（`c955411`，17:24:52）

- `C:\Users\Trekker-PTL\live_dub_ext` HEAD = **`c955411`**，提交时间 **2026-11-26 17:24:52 +0800**，标题「EXT v0.4.23: ASR works with Qwen3-ASR 0.6B packages (MiniMVP/SpecialMVP) — pick the model family the package actually ships」。前一提交 `e901cad`（v0.4.22）。
- 🔴 **§102.1 的根因已被 EXT 正面修掉**（只读复核 `ext/engine_runtime.py` L87–118）：
  - 新增 `ASR06B_ENCODER_DIR`=`models/asr06b-encoder-fp16`、`ASR06B_DECODER_DIR`=`models/asr06b-decoder-int8`、`ASR06B_TOKENIZER_DIR`=`models/asr06b-tokenizer`、`ASR06B_EMBED_NPY`=`models/embed_tokens_06b_f16.npy`。
  - 新增 `_asr_family()`：**按包内实际存在的模型族自动选**（两族都在 ⇒ 默认 R2T2；只有 06B ⇒ 06B）；`EXT_ASR_FAMILY=06b|r2t2` 可强制指定。
  - `_asr_label()`：`06b` ⇒ 「Qwen3-ASR 0.6B INT8」。
  - 加载分支 L492–520：06B 走 `import asr06b_stateful_backend`（照抄 App `OVEngine` 的 `kind=='asr06b'` 构造方式），失败抛 `EngineNeedsChange("Qwen3-ASR 0.6B", ...)`。
  - 源码注释**直书**：「以前 EXT 在这两种包里 ASR 100% 加载失败（ASR §102：123/123 段全错）」⇒ **reviewer 已读本模块 §102 并据此修**。
- 🟢 **MiniMVP v1.2 候选包已同步 v0.4.23**：包内 `ext/bridge/engine_runtime.py` mtime **11-26 17:33**（含 `06b` **17 处**）；`release.json` 原文 `ext.version` = **"0.4.23"**、`ext.note` = 「与完整版一致（EXT v0.4.23）：…ASR 自动适配包内模型族（R2T2 / Qwen3-ASR 0.6B）」。
- 🟢 **包内 06B 资产齐备**（实测目录）：`models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.{xml,bin}`、`models/asr06b-decoder-int8/openvino_model.{xml,bin}`、`models/asr06b-tokenizer/`、`models/embed_tokens_06b_f16.npy`、`app/asr06b_stateful_backend.py`、`app/asr_spk/`。
- 🟢 **App 侧 06B 引擎表只有两档**（`app/live_caption_app.py` L914–923 `ENGINES_ASR06B`）：`gpu_int8`（GPU.0）／`npu_int8`（NPU），两者**共用同一份 IR**（`ov-encoder-06b-fp16-static` + `ov-dec-06b-stateful-int8sym`），`kind='asr06b'`。
- 🔴 **但没有 v0.4.23 之后的验证臂**：§103.2 的 11 臂**全部早于** 17:24:52（最后一臂 17:09:45）⇒ **v0.4.23 修完后 ASR 能否真的跑通，本模块尚无实测**。

## §103.2 🔴 11 臂只读复算：ASR **11/11 臂 100% 段失败**（全部为 v0.4.22 及更早的产物）

> 上一会话 note 提到的「10 臂汇总」未落盘；本轮把 `shared/bgkeep/e2e_app146/` 下**全部 11 臂**统一复算（脚本 `status/asr/_asr103_agg.py`，输出 `status/asr/_asr103_agg.json`）。

| 臂 | `bgkeep_e2e.json` mtime | md5 | 时长 | 段数 | `asr_segments` | `n_submitted` | `n_error` | `spk_reason_hist` | `clone_reasons` |
|---|---|---|---|---|---|---|---|---|---|
| smoke | 14:02:05 | `812b5a4c…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| smoke2 | 14:06:46 | `c2898ef0…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| smoke3 | 15:06:10 | `446357a9…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| turbo_check | 15:58:58 | `acd63fda…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| turbo_check2 | 16:05:30 | `a8ddd4e1…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| probe1 | 16:07:15 | `42e98f85…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| probe2 | 16:16:52 | `b191b871…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| npu_check | 16:31:09 | `c7ded12a…` | 60 s | 13 | **0** | 13 | **13** | {none:13} | {} |
| three_arms/bgkeep_off | 16:48:51 | `8181379c…` | 600 s | 123 | **0** | 123 | **123** | {none:123} | {} |
| three_arms/bgkeep_on | 16:59:17 | `c18a3e52…` | 600 s | 123 | **0** | 123 | **123** | {none:123} | {} |
| three_arms/bgkeep_on_clone | 17:09:45 | `4ba63dac…` | 600 s | 170 | **0** | 170 | **170** | {none:124, **label:46**} | **10 键**（见下） |

- **11/11 臂**：`asr_segments`=**0**、`pipeline.n_error`=**n_submitted**（每段都错）、`spk_reason_hist` 几乎全是 `{none:N}`。
- **失败原文**（11 臂逐字相同，取 `npu_check` 为例，`bridge.log` L7/L18）：`ASR（R2T2 INT8） 加载失败 ⇒ EngineNeedsChange: [R2T2] SegmentEncoderOVBackend 构造失败（device=GPU.0）: … Could not open the file: "C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate\models\encoder-int8\openvino_encoder_model.xml"`。
- **计数核对**：`bridge.log` 中 `SegmentEncoderOVBackend`/`构造失败`/`Could not open the file` 各 **15 次**（60 s 臂）/ **125 次**（600 s 非克隆臂）/ **172 次**（克隆臂）⇒ 与「1 次加载失败 + 逐段重试」一致。
- 🟡 **`npu_check` 臂不能证明 NPU 档可用**：该臂日志原文 `ASR(R2T2 INT8@GPU.0)` ⇒ **ASR 仍在 GPU.0**，NPU 只是 TTS 档（`TTS(Qwen3-TTS@NPU)`）。
- 🔴 **本模块对这 11 臂的 ASR 侧数字一律无效**（`asr_segments`=0 ⇒ 无转写、无 WER/CER、无 RTF、无 §101.3 归因口径）。

### §103.2.1 🟡 新信息：`three_arms/bgkeep_on_clone` 臂的 `clone_reasons` **不是空**

> §102 只看了 4 臂（其中 3 个 smoke + 部分），记录 `clone_reasons`={}。本轮补上克隆臂 ⇒ **10 键**：

| 键 | 值 |
|---|---|
| `provisional` | **164** |
| `guard_keep` | **103** |
| `guard_short` | **64** |
| `label` | **61** |
| `self_ref_unvoiced` | **30** |
| `timeout` | **6** |
| `self_ref` | **2** |
| `guard_no_emb` | **2** |
| `fallback` | **2** |
| `gender_keep` | **2** |

- 该臂 `n_gender_splits`=**4**（非克隆两臂均 **0**）、`spk_reason_hist`={none:124, **label**:46}（非克隆臂全 {none:123}）⇒ **克隆臂才产出说话人标签与性别切分**。
- 🔴 **但该臂 `asr_segments`=0、`n_error`=170** ⇒ **标签/性别切分在 ASR 全失败的条件下照样产出** ⇒ 这些计数**只反映 EXT 克隆/旁路链路**，**不代表转写质量**；且 `spk_reason_hist` 合计 170 = `n_submitted` ⇒ 本臂**没有 §101.1 的段级表缺口**（该缺口是旁路**失败**原因进不了表；本臂旁路未开，`spk_bypass.enabled`=false，`spk_bypass` 只有 `enabled`/`note`/`spk_queue_drop`/`spk_worker_busy_ms` 4 键）。
- 🟡 **APP-131 要的三个字段在本臂仍缺**：`tts_nearest_voice`/`gender_switch`/`gender_selfref` **键不存在**（§101 已记，本臂仍如此）。

## §103.3 🔴 §102.2「README『四种 ASR 后端』表与包内不符」**仍未改**（复核确认）

- 包内 `README_zh.md`（mtime **11-26 17:33**，**晚于 EXT 同步**）**仍保留**：
  - L140 标题「## 四种 ASR 后端」；
  - L153–156 RTF 表：**GPU·INT8 0.70／GPU·INT4 0.73／NPU·INT8 0.86／NPU·INT4 0.75**；
  - L158「在 61 分钟英文会议录音的完整测试中，Intel NPU · INT8 的整体 RTF 为 0.77」；
  - L313 `--engine` 可选值仍写 **`gpu_int8`、`gpu_int4`、`npu_int8`、`npu_int4`**。
- 🔴 **与包内实际不符**：06B 只有 `gpu_int8`/`npu_int8` **两档**（`ENGINES_ASR06B` L914–923）；`app/asr06b_stateful_backend.py` 内 `int4` **0 命中**；`models/` 下无任何 `*int4*`。
- 🔴 **RTF 口径问题照旧**：那四个 RTF 与「61 分钟整体 0.77」是 **R2T2 口径**，与本模块 §83／ASR-060～061 **不是同一计分器**；且 §103.2 已证 **11 臂 ASR 全部失败 ⇒ 包内 06B 档至今没有任何本模块可引用的 RTF** ⇒ **本模块不给 06B 档对外数字**。
- 🟡 **README §「已知问题」是否已更新需 App 确认**：§102 记录两版 README 都已明写「插件侧 ASR 不可用」；EXT v0.4.23 已修 ⇒ 若 README 仍写「插件侧 ASR 不可用」⇒ **现在变成过时表述**，需同步改。

## §103.4 🟡 其它开口项无变化（只读复核）

- **§101.3 归因缺口仍在**：v0.4.23 的 `ext/speaker_bypass.py`（失败分支只 `n_no_label += 1`、**不写行**）与 `_spk_reason_hist()` **逐字未改**（v0.4.23 只动 `engine_runtime.py` 的模型族选择）⇒ 旁路失败原因仍结构上进不了段级表。
- **修前 v0.4.18／`5121d99` 对照臂仍缺**：`shared/bgkeep/` 下**无** `v0418*` 目录 ⇒ §96 ① 未闭。
- **分离人声 16 kHz wav 仍 0 产出**：全盘搜 `*vocal*` **0 命中**；`shared/bgkeep/vocals/` **仍不存在** ⇒「原声 vs 分离人声」WER 对比仍做不了。
- **对外 NPU 报告「RTF 0.067 / WER 0 / CER 0」口径仍待 reviewer 说明**（§101.5 挂项，未闭）。
- **配音迟到的有效数字仍以 §101 的 r2 臂为准**（max **182.62 s**）；§103.2 各臂 `dub_late_max` 均为**负值**（-8.1 ～ -15.9 s，ASR 全失败导致无真实配音时序）⇒ **不能用来替代**。

## §103.5 纪律

- **租约**：`acquire asr` ⇒ **TAKEOVER**（陈旧租约 token `4b4f50a4`，note「最终复核：10 臂 ASR 字段汇总完毕，准备写 §103」，`live_pids` 空 ⇒ 已死）⇒ 本轮 token **`9fce2ba3`**；beat 18:03:02／18:06:28 均 OK；末步 release。
- **共享机器锁**：`shared/MACHINE_LOCK` 存在，内容 `lfm 26840 2026-11-26 17:35:21` ⇒ 由 **lfm 模块**持有（非 ASR、非 App）⇒ 本模块**不取锁、不回收**（ASR 不越界回收他模块锁）。
- **全程只读复算**：未跑推理／未跑计时／未跑 WER／未跑分离器、未取 MACHINE_LOCK。
- 未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未改客户包；未打包；未调 MiniMax；未连 B 机；未自行开新实验（ASR-038）。
- **本轮无新纠偏** ⇒ `last_ack` 保持 **ASR-068**；但**有实质变化**（EXT v0.4.23 到位 ＋ 11 臂全失败确证 ＋ 克隆臂 `clone_reasons` 10 键 ＋ README 表仍未改）⇒ **写 §103 ＋ 发 STATUS 邮件**。
