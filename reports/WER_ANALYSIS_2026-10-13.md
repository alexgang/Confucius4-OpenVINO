# Confucius4-R2T2 → OpenVINO 移植：WER 问题独立分析报告

- 日期：2026-10-13
- 分析人：WorkBuddy（独立复算，不复读 STATUS 结论）
- 输入：README.md、status/STATUS.md、status/CORRECTIONS.md（C-000~C-037）、全部 c0xx 脚本、reports/ 下全部 transcript 与 JSON
- 方法：用 reports/ 里已有的 4 份 61-min transcript + MiniMax baseline（c026_minimax_transcript.txt）**重新计算 WER 与 S/D/I 分解**（脚本 `wer_check.py` / `wer_breakdown.py` / `loop_onset.py`，本目录根部）。计算口径与 reviewer 互相验证：对 reviewer 已算过的配置，本文数字与 reviewer 数字相差 <0.15pp（v1 23.20% vs 23.13%；CUDA 7.62% vs 7.51-7.69%；hybrid 8.65% vs 8.66-9.07%），说明口径可信。

---

## 0. 结论（TL;DR）

1. **当前方案确实有问题，而且是三层问题叠加**：① 部署入口 `transcribe_stream.py` 用的还是 C-021 时代已证伪的坏 encoder IR（跑 README 命令得到的是 ~58% WER 的行为）；② 真正验收过的版本（`spe_61min_transcript_noreset.txt`，cache 修复后）实测 **WER 17.87%**，仍高于 ≤11-12% 的验收线；③ 项目诊断链上有两个结论是被污染/误判的实验支撑的，导致后续修复（v2 IR、reset）打在了空处，而**最关键的对照实验反而一直没做**。
2. **剩余 17.87% 的误差构成（本次实测）**：插入 I=1140（10.3pp，重复循环）+ 替换 S=789（7.1pp，半数是专有名词，CUDA 也有）+ 删除 D=49（0.4pp）。**"unfixed 回滚丢词"理论可以被正式判死**（D 只有 49 个，比 Hybrid 离线的 73 个还少）；问题 100% 是"模型重复转写 prefix 已有内容"的插入错误。
3. **一个被埋没的真实进展**：C-033#1 的 cache 计数 bug 修复把 WER 从 23.20% 降到了 **17.87%（-5.4pp）**，但 STATUS 用 n3/n4 代理指标（1141→1184，略升）误判为"没有改善甚至略差"，于是把这个版本当成"仍 ~23%"对待。n-gram 计数是错的 WER 代理，它给团队的指引反了两次。
4. **最该先做的一件事**：跑一次"干净的 no-cache（每 chunk 全量重算）61-min"。历史上判定"cache 不是根因"的 e-path 实验（230 vs 183）是在**窗口计数 bug 未修**的代码上跑的（`c031_e_path_nocache.py:85-88`、`c031_smart_cache.py:101-104` 仍是 `n_100_blocks // 8`），不满窗区间每 8s 就有约 1s 会往序列里注入 4 个幻影 token——那个"更差"的结论不成立。干净的对照实验从未做过，而它恰好是 C-031（reviewer）正确指出的、OV 与官方实现之间仅剩的确定性语义差异。

---

## 1. 现状实测：四份 transcript 的同口径对比

全部 vs MiniMax baseline（11066 词），同归一化（小写、去标点）：

| 配置 | 词数 | S | D | **I** | WER |
|---|---:|---:|---:|---:|---:|
| CUDA 流式（audio.cpp GGUF Q8_0，dGPU，同流式参数） | 11169 | 473 | 75 | **295** | **7.62%** |
| Hybrid 离线（torch encoder + **同一个** OV INT8 decoder，段级单次 decode） | 11341 | 436 | 73 | **448** | **8.65%** |
| OV 流式 v1（窗口 IR + 坏 cache，= `spe_61min_transcript.txt`） | 12131 | — | — | — | **23.20%** |
| **OV 流式 noreset（窗口 IR + cache 修复，= 当前交付）** | 12295 | 789 | 49 | **1140** | **17.87%** |

参考（旧坏 encoder，仅作历史坐标）：OV 流式旧 encoder 58.23%；OV 离线旧 encoder 74.84%（与 C-019/C-024 reviewer 数字一致）。

**读表**：
- OV 流式比 CUDA 流式多出 ~845 个插入词（≈7.6pp 纯插入）——这就是"WER 非常高"的全部实质。
- Hybrid 离线用**同一个 OV INT8 decoder** 做到 8.65% → **decoder 单独不是根因**（C-028 已论证，本次数据再次确认）。
- CUDA 流式用同一个流式算法做到 7.62% → **流式算法/我们的 streaming_asr.py 移植不是根因**（C-030 E 步逐行对照过，数据确认）。
- 差值只可能来自：**OV encoder 的流式路径（窗口 IR + cache）** 与 **INT8 decoder 在流式 prefix 条件下的数值敏感性**（C-028 path d：FP16 decoder 使 11 个最差段 n4 -54%）。

---

## 2. 问题清单（按严重度排序）

### P0 — 部署入口与验收对象不是同一个东西（工程债，5 分钟可修）

`transcribe_stream.py`（README 声明的部署入口）：
- 用 `OVBackend(model_dir="models/ov-int8-past")` → 编码器是 optimum 导出的 IR，C-021 已实测**全长度都错**（4s cos 0.64、60s 0.29，token 数也不对），这正是 58%/75% WER 的源头；
- 分段默认 `rolling 30s` + `unfixed_chunk_num=2`，也不是 C-018 修订后的 VAD 12-20s + `unfixed_chunk_num=0`；
- 真正修好的窗口 encoder 路径（`WindowEncoderOVBackend`）只存在于 `c033_61min_noreset.py` 等**验证脚本**里，没有任何入口默认用它。

后果：按 README 命令部署，拿到的是 58% WER 的行为；按验收脚本跑，才是 17.9%。**交付物和验收对象脱节**。

### P0 — "cache 无害"结论建立在被污染的实验上（诊断链缺陷）

- C-031#1 e-path（关缓存，11 段：230 vs 183，"cache 不是根因"）与 C-031#4 smart cache（≈no cache）两个实验，跑的都是**还带着窗口计数 bug 的 no-cache 代码路径**（`c031_e_path_nocache.py:85-88`、`c031_smart_cache.py:101-104` 仍为 `n_100_blocks // 8`）。C-033#1 只修了生产文件 `window_encoder_backend.py` 和 `c031_growing_audio_cosine.py`。
- 该 bug 的后果（C-033 自述）：mel 落在 (700,800) 等区间时，不满窗被当满窗，**往序列里注入 4 个幻影 token**；不缓存时"每 8 秒里有 1 秒"都会发生。也就是说 e-path 的每一次"更差"里都混着这个确定性 bug 的贡献。
- **干净的 no-cache 对照实验（cache 修复后的代码）从未做过。** 而它对应的恰好是 C-031 指出的、OV 与官方之间仅剩的确定性语义差异：**window cache 的陈旧化**——官方/vLLM/audio.cpp 每个 chunk 都用当前整段 mel 全量重算（`WhisperFeatureExtractor` 的 `max(log_spec, log_spec.max()-8)` 全局钳制会随新音频改变旧帧特征值），而 OV 把满窗 ehs 在首次填满时永久冻结。本次复算 `reports/c031_epath/growing_audio_cosine.json` 证实该差异在修复后依然存在（step 20 第 2 个满窗填入后，1 个 token cos 掉到 0.952，且不再恢复）——幅度不大，但 greedy 流式解码对扰动极端敏感（C-030 自己的结论）。

### P1 — "partial block 0.93 bug"是误判，v2 IR 是 no-op（诊断链缺陷）

- C-037c 的 layer 11 分歧（cos_min 0.92）是比较方法学问题：`audio_tower(960)` vs `c023(800)` 的 mel 全局归一化不同 + 序列长度不同（125 vs 104 token）。C-038#2 自己给出了铁证：`audio_tower(800) vs audio_tower(960)[:104]` 也只有 0.998——**audio_tower 自身多窗拼接就不严格相等**，0.93 不是 c023 的 bug。
- 基于该误诊断加的 v2 mask（padded token 置零）在数学上与 v1 等价（valid token 不 attend padded token，attention 是唯一跨 token 操作），C-038#2 实测 v2 ≡ v1（6 位小数相同）。生产至今用 v1，无损——但"根因已修"的叙事是假的，团队为此绕了弯路。
- 副产品：`c037d_no_mask_verify.py` 证明 attn_mask 不是根因，也是对一个不存在的问题的验证。

### P1 — 评估指标用错：n3/n4 重复计数当 WER 代理（方法论缺陷）

- cache 修复后，proxy 指标 n4 从 1141→1184（略升），团队据此认为"61-min 没有改善"（STATUS 12:09："结果反直觉…总体微升"）。**本次实测 WER：23.20% → 17.87%（-5.4pp），是真实的显著改善。**
- 原因：cache 修复消除了灾难段（n4_max 54→19）但把循环"摊平"成更多段的中度重复（C-030 的 fragility 观察），n-gram 计数对这种结构变化不敏感。**必须用真实 WER（vs MiniMax）做验收判据**，proxy 只能用于定性。

### P2 — 剩余 17.87% 的归因（数据驱动）

误差分解（本次实测）：**I=1140（10.3pp）/ S=789（7.1pp）/ D=49（0.4pp）**。

- 插入是绝对主因，且形态是"整句重说"（例 [2025-0-2042.2]：`...until we get to be very far in front of us until we get that traction through the next year at least and then on physical ai...` 重复 3 遍；[2552.3-2571.2] 单短语重复 30+ 次）。
- loop onset 分析（`loop_onset.py`）：56/226 段有 ≥2 的 n4 重复，循环起点中位数在段内 37% 处，**不集中在 8s 窗口边界**——不是单一"边界 bug"，是系统性的数值脆弱：多个各自很小的偏差（满窗 ehs 陈旧化 cos≈0.95-0.999；INT8 logits 噪声）在流式 prefix 条件下累积，把 greedy 解码推入重复。CUDA（ggml 全量重算 + Q8_0）没有这些偏差的叠加，所以干净。
- 替换里约一半是专有名词（hammerlake→hammerlick、18a/18ap、wifi、q3）——CUDA 流式也有（S=473 vs OV 789），属于 1.7B 流式模型的固有水平 + MiniMax baseline 自身噪声，**不是 OV 特有问题，不要为它改算法**。
- 删除 49 个：`unfixed_token_num 5→2` 之类的"丢词修复"（STATUS 选项 A2/C）可以正式放弃。

口径说明：S/D/I 的拆分依赖对齐算法（本文用 difflib，总量与 Levenshtein DP 相差 ~0.1pp）；但"I 远大于 D"的结论与对齐方式无关（23:1），且 reviewer 自己在 C-027 用另一套口径也得到同样结构（OV I=1499 vs Hybrid I=562，OV 多出约 940 个插入）。v1（坏 cache）的 difflib 分解为 S=1815/D=163/I=624（总 2602，WER 23.51%；Levenshtein 总量 2567 → 23.20%）——注意 v1 的"插入少"是对齐假象：灾难性长循环在对齐器眼里被算成大量替换，总量才是可比数字。

---

## 3. 改进路线图（按预期收益/成本排序）

### 第 0 步（立即，~5 分钟）：对齐部署入口

`transcribe_stream.py` 默认改为与 `c033_61min_noreset.py` 相同的生产配置：`WindowEncoderOVBackend(encoder_dir="models/ov-encoder-window", decoder_dir="models/ov-int8-past")`、`strategy=vad, min_segment_sec=12, max_segment_sec=20`、`unfixed_chunk_num=0`、`enable_hallucination_reset=False`。否则后面所有验收继续脱节。

### 第 1 步（判决性实验，~40 分钟机时，一行级代码改动）：干净的 no-cache 61-min

- 改动：`WindowEncoderOVBackend.__init__` 加 `use_window_cache: bool = True`；`encode_audio` 里 cache 命中分支改为 `if False and w < len(...)`（或等价开关）。**必须基于已修复的 `mel_len // 800` 逻辑**（直接复用现有生产代码主体，天然满足）。
- 判定标准（用真实 WER，不是 n4）：
  - WER ≤ 12% → cache 陈旧化是主因，交付 no-cache 版。成本：每 chunk encoder 从 1 窗变 2-3 窗（16s 段 ≈ +60-90ms），预计 RTF 0.535 → ~0.63，仍 < 1，达标。
  - WER 仍 > 12% → encoder 路径被进一步排除，坐实 INT8 decoder 流式敏感性，进第 3 步。
- 这个实验同时覆盖 C-031 reviewer 的核心论点，无论结果如何都消除因果链上最大的不确定性。

### 第 2 步（与第 1 步并行，~20 分钟机时）：OV 窗口 encoder 离线 per-segment 61-min（从未做过）

- 实现：`SegmentedStreamer` 加 `offline_final=True`：每段只 `init_streaming_state` → 喂完整段音频 → 一次 `generate_with_prefix(prefix="")` → 取文本。不做 chunk 循环、无 prefix 回滚。
- 预期 ≈ 8.7%（与 Hybrid 离线同水位，因为 encoder 单窗 cos=1.0 + 同一个 INT8 decoder 离线已验证 8.65%）。
- 价值：① 证明窗口 encoder IR 在生产路径上正确；② 为第 5 步两遍式方案提供质量背书；③ 填补"OV 窗口 encoder 离线 WER 从未测量"的空白（现有 spe_ov_offline.txt 75% 是旧坏 encoder 的数字，不能代表现状）。

### 第 3 步（若第 1 步不够）：降低 decoder 数值偏差

- 先跑全 FP16 decoder（`models/ov-fp16-past` 已存在）在 11 个最差段 + 10 分钟切片上的 WER/RTF。C-028 path d 的证据（11 段 n4 -54%）指向这里。
- 实时性账：decode 33ms/token → ~64ms/token，每 chunk 5-9 token，chunk wall 342ms → ~600ms，RTF ~0.9、段 RTF P95 会超 0.8 目标线。**全 FP16 有实时性风险，优先做混合精度**（lm_head + 最后 2-3 层 FP16，其余 INT8；NNCF/optimum 导出时对指定层关闭量化），预期拿到大部分质量收益、RTF 涨幅减半。
- 若混合精度后 WER 达标且 RTF < 0.8，作为主交付；否则进第 5 步。

### 第 4 步（诊断，本机 torch 已验证可用，STATUS 5.20）：hybrid 流式 11 段

- torch encoder per chunk + OV INT8 decoder + 同一个流式循环（`HybridBackend` 已存在，直接接 `streaming_transcribe`）。
- 干净（≈9%）而 no-cache OV 仍循环 → 问题在窗口 IR 流式细节，回第 1 步深挖；仍循环 → INT8 decoder 流式模式坐实，第 3 步成为必选项。这是最后一块归因拼图，成本低（11 段 × ~10s/段，CPU encoder 慢但可接受）。

### 第 5 步（产品级兜底，需用户拍板）：两遍式

流式出实时字幕（保持实时性），段尾对整段离线重解一次作为最终文本（第 2 步已验证 ≈8.7% 质量）。C-027 已明确这改变产品形态、需用户决定。若第 1-4 步都无法把流式本身压到 ≤11%，这是保底方案。

### 附带决定

- **hallucination reset 维持 C-036 决定：不作交付**，保留为可选安全网（对极端段），开启时单独报告 WER/D 变化。
- **放弃** unfixed_token_num 5→2 选项（D=49，无利可图）。
- 评估流程：所有"改善/恶化"判定用 `wer_check.py`（对 MiniMax 的真实 WER）而不是 n3/n4。

---

## 4. 证据索引（可复算）

| 结论 | 证据 |
|---|---|
| 当前交付 WER 17.87% | `wer_check.py` 对 `reports/spe_61min_transcript_noreset.txt`；口径经 reviewer 已算配置验证 |
| 误差 85% 是插入 | `wer_breakdown.py`：S=789/D=49/I=1140 |
| 循环起点不集中窗口边界 | `loop_onset.py`：56 段，onset 中位数 37% |
| e-path/smart-cache 实验被污染 | `c031_e_path_nocache.py:85-88`、`c031_smart_cache.py:101-104`（旧 `n_100_blocks // 8`） |
| cache 陈旧化在修复后仍存在 | `reports/c031_epath/growing_audio_cosine.json`：step 20 起 1 token cos 0.952 |
| v2 IR ≡ v1 | `reports/c023v2_validate.json` + STATUS C-038#2 |
| 部署入口用坏 encoder | `transcribe_stream.py:28,84`（OVBackend + models/ov-int8-past） |
| FP16 decoder 能减循环 | `reports/c028_4path/results.json`：a=183, d=85 |
| 流式算法/decoder 单独无罪 | CUDA 7.62%（I=295）；Hybrid 8.65%（I=448）——本次复算 |
