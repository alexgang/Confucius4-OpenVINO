# Confucius4-R2T2 → Intel OpenVINO 移植报告

> 日期: 2026-10-15
> 工作目录: `C:\Users\Trekker-PTL\confucius4-openvino`
> GitHub: <https://github.com/alexgang/Confucius4-OpenVINO> (branch `c038-v2-ir`)
> 状态: **交付达成** —— 61-min 英文长音频 WER **7.88%**（reviewer 独立复核 8.17%），RTF **0.639**
> 精度基准: **MiniMax 云端 asr-1.0**（`reports/c026_minimax_transcript.txt`，11066 词）

---

## 1. 项目目标

把官方 `netease-youdao/Confucius4-R2T2`（`Qwen3ASRForConditionalGeneration` / Qwen3-ASR-1.7B，
R2T2 用 LSP 前缀做流式微调）的**流式 ASR** 移植到 **Intel OpenVINO 2026.4**，
目标硬件为 **Intel Core Ultra 7 356H (Panther Lake) Xe3 集显（GPU.0）**。

交付形态必须**完全不依赖 torch**：目标机开启 Windows 智能应用控制（Smart App Control），
未签名的 `torch_python.dll` 会被拦截（C-029/C-034/C-036）。全部运行时只有 OpenVINO + numpy。

---

## 2. 最终成果

### 2.1 精度（61.19 min 英文 SPE 录音，226 段，参考 = MiniMax asr-1.0，11066 词）

| 配置 | 词数 | S | D | **I** | **WER** |
|---|---:|---:|---:|---:|---:|
| MiniMax asr-1.0（基准本身） | 11066 | — | — | — | — |
| **OV 流式（本次交付）** | 11266 | 455 | 54 | **363** | **7.88%** |
| └ reviewer 独立复核同一份产物 | 11266 | 282 | 151 | 463 | **8.17%** |
| OV 段级离线 FP16（两遍式第二遍，上限参照） | 11217 | 428 | 73 | 334 | 7.55% |
| OV 段级离线 INT8（两遍式第二遍） | 11254 | 433 | 73 | 362 | 7.84% |
| Hybrid 离线（torch encoder + 同一 OV INT8 decoder） | 11341 | 436 | 73 | 448 | 8.65% |
| **修复前** OV 流式（`max_new_tokens` 固定 32） | 12313 | 901 | 52 | **1025** | **17.87%** |
| *参照* CUDA 流式 audio.cpp Q8_0（RTX 5050 dGPU，非基线） | 11169 | 473 | 75 | 295 | 7.62% |

**读表**：

- 交付版本 **7.88%**，优于当时作为目标的 Hybrid 离线（8.65%）和"可接受"线 11%。
- 流式与"段级离线"的差距只有 0.04pp（7.88% vs 7.84%）——**两遍式不再必要**，
  省掉了段尾额外一次全量解码与相应延迟。
- 误差结构与 CUDA 参照同形；CUDA 的 7.62% 是同算法的 dGPU 实现，不是本项目的验收基线。
- S/D/I 的口径差异：本机口径（小写 + 去标点）与 reviewer 口径（小写 + 去标点 + 数字保留原样）
  相差 0.29pp，主要落在 S/D 的切分上。以 reviewer 复核口径为准。

### 2.2 性能（同上 61.19 min 输入）

| 指标 | 修复前（固定 32） | **交付（自适应）** | 变化 |
|---|---:|---:|---|
| 整体 RTF | 0.687 | **0.639** | −7.0% |
| 段 RTF P50 | 0.677 | 0.636 | −6.1% |
| 段 RTF P95 | 0.755 | **0.675** | −10.6% |
| 段 RTF max | 1.133 | **0.727** | −35.8% |
| 墙钟 | 2521 s | 2348 s | −173 s |
| 重复 3-gram | 1983 | 981 | −50.5% |
| 重复 4-gram | 1207 | 262 | −78.3% |

自适应预算**反而更快**：每 chunk 生成 token 数变少，解码步数下降，而瓶颈在 encoder 侧不动。
验收线 RTF < 1 / P95 ≤ 0.8 已满足，P95 余量 0.125。

### 2.3 部署体积

| 产物 | 大小 | 说明 |
|---|---:|---|
| `models/ov-encoder-segment-reviewer/` | 607 MB | 整段全局注意力 encoder（FP16 权重压缩） |
| `models/ov-int8-past/` | 2.0 GB | **生产** INT8 权重压缩 stateful decoder（57 ReadValue/Assign） |
| 合计 | **≈ 2.6 GB** | 运行只需 OpenVINO runtime |

---

## 3. 三个根因与修复顺序

整条链路从"23% WER 不可交付"到"7.88% 达标"，中间有三个**互相独立**的根因。
必须按此顺序修，因为后者要在前者的基础上才能被观测到。

### 根因 ①：optimum-intel 导出的 audio encoder 丢失了全局注意力

**症状**：所有长度的输出都不对。4 s 音频逐 token cosine 只有 **0.64**，60 s 降到 **0.29**；
token 数也不等于公式值（4 s 时 OV 50 vs torch 52）。这导致 61-min WER 被锁死在 23%+，
且在此之前任何 decoder / 流式层面的结论都不可信。

**定位**（C-021 → C-023 → C-039）：
- `modeling_qwen3_asr.py` 的 `Qwen3ASRAudioEncoder.forward`（第 727-733 行）调用每一层时是
  `encoder_layer(hidden_states, cu_seqlens)`，**没有传 attention_mask**；构造窗口 mask 的
  `_prepare_attention_mask`（第 649 行）**定义了但从未被调用**。在 eager/sdpa 下 `cu_seqlens`
  被忽略 → **参考实现对输入里的所有音频 token 做全局注意力**。只有 flash-attention-2 路径才按
  104-token 窗口切。
- optimum-intel 的 `Qwen3ASRModelPatcher._patch_audio_encoder` 用一个简化 forward 替换了真
  forward（全局 1D conv + 全局位置编码 + 标准 attention），分块/窗口语义被丢掉。
- 中途自导的"窗口 IR"（104-token 注意力）同样是错的：>800 帧时 min cos 降到 0.005-0.09 ——
  这是我方当年对源码的误读，已由 C-039 更正并作废。

**修复**：改用 reviewer 交付的整段 encoder
（`reviewer/export_segment_encoder.py` → `models/ov-encoder-segment-reviewer/`）：
固定输入 `input_features [1,128,2400]` + `n_valid [1] int32`，输出 `[1,312,2048]`，
注意力为**全局**、只屏蔽补齐的 key。
**数值验收**：0.64–23.9 s 全部长度 cos mean **1.000000** / min **≥ 0.999996**（对比 torch）。

### 根因 ②：窗口编码器把不满窗当成满窗（计数 bug）

**症状**：每约 8 s 就有约 1 s 的音频被注入 4 个"幻影"音频 token，令 model 反复重述 prefix
里已有的内容。在 11 个最差段上重复 4-gram 总数 183。

**定位**（C-033）：`window_encoder_backend.py:170-172` 用
`n_100_blocks = ceil(mel/100)`、`n_full_windows = n_100_blocks // 8`。当 mel 落在 (700,800)
区间时，块数向上取整后等于 8 的倍数 → 把**不满的窗口当成满窗**，补的零帧当作有效音频编码。
实例：7.68 s = 768 帧，正确 N_audio = 91+9 = **100**，日志里是 **104**。
缓存模式下这个被污染的窗口被**永久缓存**，后续每个 chunk 都错。

**修复**：`n_full_windows = mel_len // 800`（按帧数向下取整，不按块数）。
修完 11 个最差段重复 4-gram **183 → 1**。
（该后端最终被 ① 的全局 encoder 取代；但"缓存必须在输入严格不变时才复用"这条结论
被吸收进了最终设计——全局注意力下无法跨 chunk 复用 ehs，索性不做任何缓存。）

**效果**（本机同脚本口径）：窗口 IR 23.51% → cache 修复后 17.87%（**−5.64pp**）。

### 根因 ③（主因）：`max_new_tokens` 被固定成 32，错译了官方的自适应生成预算

**症状**：替换错误早已正常，但**插入错误始终居高不下**（修复前 I=1025，占 WER 的绝大部分）。
Hybrid 离线（同一个 OV INT8 decoder，整段一次解码）干净 → 与量化、与 encoder 都无关；
CUDA 流式干净 → 与流式算法本身无关;

**定位**（C-047）：与 CUDA 官方 `example.py:118-155` 逐项对齐，做 8 变体受控实验。

| 参数 | CUDA 官方 | 移植时的取值 |
|---|---|---|
| `chunk_size_ms` | 160 | 640 |
| `unfixed_token_num` | 1 | 5 |
| **`max_new_tokens`** | **自适应 1–4（负反馈）** | **固定 32** ← 主因 |
| first-chunk lookahead | 160 ms | 无实现 |
| finish 预算 | `first_max_new_tokens` | `max(64, 32)=64` |

CUDA 的负反馈控制器是一个**上限约束**：
```python
max_new_tokens      = max(1, int((step + lookhead) / 1280))   # 文本在增长 → 收紧
max_new_tokens_floor= min(32, max(4, 2 * int(step / 1280)))   # 文本停滞 → +1（中文 ×2）
first_max_new_tokens= max_new_tokens                          # 段尾 flush 用这个值
```
它的价值不在"预算小"，而在**上限**：单次自回归失控最多写 4 个 token 就被截断。
固定 32 时，每个 640 ms chunk 只有约 8 个 token 的新内容可支撑，模型被迫重述 prefix 填满预算，
而**已经写出去的部分会被永久冻结进下一个 chunk 的 prefix**——错误就这样被固化。

**受控实验结论**（只改这一个参数，其余全同，5 段 ref=298 词）：

| 配置 | WER | 插入 | 重复 |
|---|---:|---:|---:|
| 640 ms / k=5 / **固定 32** | 40.27% | 92 | 106 |
| 640 ms / k=5 / **自适应** | **4.36%** | **0** | 7 |

而其它 CUDA 差异项**单独改全部无效**（C 改 160 ms → 39.26%；B 改 k=1 → 37.92%；
D 加 first lookahead → 40.27%，与基线逐项相同）。

**效果**（61-min 全量）：WER **17.87% → 7.88%**（**−9.99pp**），I 1025 → 363（**−64.6%**），
n4 重复 1207 → 262，同时 RTF 0.687 → 0.639。

### 必须知道的两个耦合约束

1. **自适应必须配 `unfixed_token_num=5`**：k=1 + 自适应在 640 ms 下退化到 **29.19%**
   （比固定 32 还差）。已把这个耦合做进 `transcribe_stream.py` 的启动告警。
2. **不要照搬 CUDA 的 160 ms chunk**：改 160 ms 只换来 3.2 倍墙钟、**零收益**。

---

## 4. 架构

```
   16 kHz mono wav
        │
        ▼
┌──────────────────────┐
│ WhisperFeatureExtract│  mel (1,128,T)，do_not_pad
└──────────────────────┘
        │  补零至 2400 帧 + n_valid
        ▼
┌────────────────────────────────┐
│ SegmentEncoderOVBackend        │  整段全局注意力（回答根因 ①）
│ models/ov-encoder-segment-     │  固定静态 shape，不做任何缓存
│ reviewer/ (FP16, 607 MB)       │  上限 2400 帧 ≈ 23.9 s
└────────────────────────────────┘
        │  ehs (1, N_audio, 2048)
        ▼
┌────────────────────────────────┐
│ OV decoder INT8 stateful       │  每次 prefill 前 reset_state()
│ models/ov-int8-past/ (2.0 GB)  │  greedy, temperature=0,
│ 57 ReadValue/Assign            │  eos=[151643,151645]
└────────────────────────────────┘
        │  max_new_tokens ← 自适应负反馈（回答根因 ③）
        ▼
┌────────────────────────────────┐
│ streaming_asr.py               │  LSP 主循环，抄自 r2t2_asr.py:302-578
│ unfixed_chunk_num=0            │  prefix 回滚 / 去标点 / 中文去空格
│ unfixed_token_num=5            │  hallucination reset 默认不启用（C-036）
└────────────────────────────────┘
        │
        ▼
┌────────────────────────────────┐
│ seg_stream.py                  │  VAD 在 [12,20] s 找静音切段，段尾 flush
│ transcribe_stream.py           │  部署入口（默认上述配置）
└────────────────────────────────┘
```

### 关键设计决策

1. **不用 optimum 导出的 encoder IR**（根因 ①）。自己导出 + torch 逐长度 cosine 验收，
   要求 mean 1.000000 / min ≥ 0.999996 才算通过。
2. **全局注意力 ⇒ 不做任何窗口缓存**。参考实现在非 FA2 路径下就是全局注意力，
   旧的"cache 缓存已满窗口"优化（C-024 提出、C-031 排查、C-033 修 bug）在语义上不成立，
   已整体作废。取而代之是靠静态 shape + FP16 把单次 encode 压进 GPU 预算。
3. **VAD 切句而非盲切**：encoder 有 2400 帧（≈23.9 s）硬上限。累积到 12 s 后在
   [12,20] s 内找静音点切；新段 `unfixed_chunk_num=0`（per 官方 ws_server），
   段尾必走 `finish_streaming_transcribe` flush 尾巴。
4. **不依赖 torch**：全链路 `USE_TORCH=0`，feature extractor 与 tokenizer 走纯 numpy 路径。
   这不是洁癖——目标机的 Smart App Control 会拦未签名 DLL（C-029）。
5. **不用 reset 掩盖 repetition**。hallucination reset 一度作为安全网加上（C-033#2），
   用户明确要求"从根因上解决"（C-036），已撤销为诊断选项。
   最终交付产物全部在 `enable_hallucination_reset=False` 下产出。

---

## 5. CUDA 长音频上限验证（回答用户最初的反馈）

用户最初的反馈是"CUDA 也要处理长音频"。实测（audio.cpp + GGUF Q8_0，RTX 5050，**不分段**流式）：

| 输入长度 | 结果 | RTF |
|---|---|---:|
| 3 min | ✅ 文本正确 | 1.374 |
| 4 min | ✅ 文本正确 | 1.637 |
| 5 min | ❌ CRASH | — |
| 10 min | ❌ CRASH | — |

报错：`audio encoder token count exceeds max_source_positions`。

**结论**：这是**同一份 HF 模型架构的固有上限**，不是 CUDA 或 OV 某一侧的实现缺陷。
- CUDA 不分段触发阈值 **240–300 s**；OV 旧 IR 是 **120 s**（`max_source_positions=1500`）。
- **CUDA 与 OV 都需要做 VAD 切句**。按同一套 VAD 切段（226 段）跑完整 61 min，
  CUDA 流式是干净的，WER 7.62%（本机口径）/ 7.69%（reviewer 口径）。
- 这条结论直接回应了用户反馈：audio.cpp 本身不支持长音频，除非调用方自己切句。

---

## 6. 已探索并证伪的路径

以下路径在本项目中投入过实打实的工作量，**结论为"不必要"，保留供检索**：

| 编号 | 假设 | 证据 | 结论 |
|---|---|---|---|
| C-043 | INT8 decoder 的 lm_head 量化误差是第二大根因（logits 整体放大 11%、top-3 排序翻转） | logits 证据属实，但修复该项后 61-min WER 仍停在 17%+ | **证伪**：它是真实存在的数值偏差，但不是 WER 瓶颈 |
| C-044 | 用 teacher-forcing 确定性指标（top-1 一致率 / EOS 一致率 / KL P99）挑选量化方案 | 五个候选（per-channel / per-group 128 / per-group 64 / +lm_head FP16 / 按层敏感度）全部在 99% 以下徘徊 | **证伪**：提升无法转化为 WER 改善且 RTF 不达标 |
| C-045 | 两遍式（流式出实时字幕，段尾再对整段离线重解一次） | 第二遍达 7.84%，但单遍自适应修好后已达 7.88% | **不再必要**，保留脚本作历史对照（`c045_two_pass.py`） |
| C-046 | LocalAgreement 共识提交，只冻结连续多轮一致的文本 | 5 段 40.27% → 11.41% | **降为备选**：不如限制生成侧（4.36%） |
| — | 窗口 IR + 窗口缓存作为 encoder 的性能优化 | 根因 ① 证明语义不等价 | **作废**（`ov-encoder-window*` 不再使用） |
| C-049 | 段尾 flush 预算改为官方 `first_max_new_tokens`（8）可追平 CUDA 的残差 | 61-min 受控实验：WER **8.41% vs 7.88%**，D 54 → 153（段尾被截断） | **已验证无改善**，保持 `max(64,...)` |

**量化继续扣分体现在哪里**：7.88% 就是在 **plain INT8**（`ov-int8-past`，NNCF per-channel）
上拿到的。以下 decoder 变体均为探索产物，**已从默认路径移除、仅存档**
（`models/` 下仍在，部署入口不再引用）：
`ov-int8-lmfp16-past`、`ov-int4-lmfp16-past`、`ov-mix4/8/12/16-past`、
`ov-mixf2/4/8-past`、`ov-mixl2/4/8-past`。

---

## 7. 已知限制

1. **基线自身的缺口**：最差的两个窗口（36 分、46 分，各约 60% 局部 WER）几乎纯插入、
   S/D 接近零，与 Hybrid 离线在同一窗口的数字完全一致 —— 是 MiniMax baseline 在 Q&A 段漏转
   （约 269 词），不是本方错误。扣除后**等效 WER ≈ 5.7%**。
2. **中文未在真实长音频上全量验证**：自适应预算的中文分支（`is_last_token_chinese` + 预算翻倍）
   代码与官方一致、单元级验证通过，但 61-min 验证集是英文。中文场景待 C-050 补测。
3. **段尾 flush 预算与官方不一致 —— 已做受控实验，结论为"不要改"**：
   官方段尾用 `first_max_new_tokens`（640 ms 时为 8），本项目用 `max(64, 32)=64`。
   C-049 受控实验（只改这一个量，61-min 全长）：

   | 段尾预算 | WER | S | **D** | I | RTF |
   |---|--:|--:|--:|--:|--:|
   | `max(64,32)` = 64（交付） | **7.88%** | 455 | **54** | 363 | 0.639 |
   | `first_max_new_tokens` = 8 | 8.41% | 459 | **153** | 319 | 0.620 |

   插入确实降了 44 个，但**删除涨了近 3 倍**（54 → 153），整体 WER 反而差 0.53pp。
   原因是 OV 的流式过程未必在最后一个 chunk 收敛，预算 8 会把段尾压着的内容截断。
   该实验开关保留在代码中（`SegmentedStreamer(finish_budget='first')`），**不作默认**。
4. **远场 / 高噪场景未测**：验证集是单路近场会议录音，不含噪声鲁棒性结论。

---

## 8. 文件索引

### 8.1 关键代码

| 文件 | 用途 |
|---|---|
| `transcribe_stream.py` | 部署入口（默认 segment encoder + INT8 + 自适应预算 + VAD 12-20 s）|
| `streaming_asr.py` | backend-agnostic LSP 主循环 + 自适应预算 + 中文分支 |
| `seg_stream.py` | VAD 切段驱动；`finish_max_new_tokens()` 控制段尾预算口径 |
| `segment_encoder_backend.py` | 整段全局注意力 encoder backend（生产路径）|
| `reviewer/export_segment_encoder.py` | reviewer 的整段 encoder 导出与验证脚本 |
| `c047_cuda_parity.py` | 8 变体受控实验，定位根因 ③ |
| `c048_61min.py` | 61-min 全量验证（baseline / adaptive / finish_first）|
| `c045_wer.py` | WER 与 S/D/I 分解（本机口径）|

### 8.2 关键报告

| 报告 | 内容 |
|---|---|
| `reports/C047_CUDA_PARITY.md` | 根因 ③ 的完整论证与全量集验证 |
| `reports/C046_STREAM_GAP_ROOTCAUSE.md` | 插入错误的根因分析（共识提交方案）|
| `reports/C045_RESULTS.md` | 量化候选与两遍式的评估数据 |
| `reports/WER_ANALYSIS_2026-10-13.md` | 第三方视角的独立复核（含审查链上的误判）|
| `reports/REVIEWER_BRIEF_2026-10-15.md` | reviewer 交接汇总 |
| `status/STATUS.md` | 当前状态与执行进度 |
| `status/CORRECTIONS.md` | reviewer 指令（执行 agent 只读）|

### 8.3 主要产物

| 路径 | 说明 |
|---|---|
| `reports/c048_61min_adaptive/transcript_adaptive.txt` | **交付 transcribe**（7.88%）|
| `reports/c048_61min_adaptive/transcript_baseline.txt` | 修复前对照（17.87%）|
| `reports/c048_61min_adaptive/summary.json` | RTF / n-gram 完整统计 |
| `reports/c026_minimax_transcript.txt` | 精度基线（MiniMax asr-1.0）|
| `reports/spe_61min_transcript_v3_segenc_int8.txt` | 根因 ① 修完、③ 未修的中间态 |
| `reports/spe_61min_transcript_noreset.txt` | 根因 ② 修完的中间态 |

---

## 9. 复现

```bash
# 交付配置（默认值即最优）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav

# 复现 61-min 全量对照
.venv/Scripts/python.exe c048_61min.py --variants baseline,adaptive
.venv/Scripts/python.exe c045_wer.py \
    reports/c048_61min_adaptive/transcript_adaptive.txt \
    reports/c048_61min_adaptive/transcript_baseline.txt

# 复现根因 ③ 的 8 变体受控实验
.venv/Scripts/python.exe c047_cuda_parity.py --n-extra 2
```

环境：全程 `USE_TORCH=0`、设备 `GPU.0`（f16 精度的 segment encoder + INT8 权重 decoder）、
仅依赖 OpenVINO runtime 与 numpy。
首次调用含图编译，第一路必须预热丢弃（编译后首次推理会直接吐 EOS）。

---

## 10. 协作协议

- 角色：本机执行 agent；远程 reviewer 通过 `status/CORRECTIONS.md` 下指令
- 状态通道：执行 agent 写 `status/STATUS.md`；指令履历在 `status/CORRECTIONS.md`（agent 只读）
- 每步执行前重读 CORRECTIONS.md，处理完在 STATUS 回执
- GitHub 同步：SSH 推送到 `origin/c038-v2-ir`（per C-037）

---

> 本报告取代 2026-10-12 版的 PROJECT_REPORT（那一版记录 23% WER 与已作废的窗口 encoder）。
> 精度对比口径：MiniMax 云端 asr-1.0，非 CUDA。
