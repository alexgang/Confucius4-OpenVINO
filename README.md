# Confucius4-R2T2 流式 ASR → Intel OpenVINO（Panther Lake Xe3 集显）

把官方 `netease-youdao/Confucius4-R2T2`（Qwen3-ASR-1.7B 流式微调，架构 `Qwen3ASRForConditionalGeneration`）
用 **OpenVINO 2026.4** 在 **Intel Core Ultra 7 356H（Panther Lake）Xe3 集显** 上跑通，
**INT8 权重压缩 + with-past stateful** 实现短音频 RTF ≈ 0.45（640 ms chunk），
**VAD 切句分段** 让任意长度音频 RTF 稳定 < 0.8。

## 验收结果（C-013 + C-014/C-016/C-018 最终方案）

| 指标 | 值 | 备注 |
|--|--|--|
| 设备 | Intel Xe3 iGPU (Panther Lake) | `GPU.0`，`FULL_DEVICE_NAME` 启动断言 Intel |
| 精度 | **INT8**（NNCF 权重量化）| 2.0 GB；57 ReadValue/Assign，stateful |
| chunk | **640 ms** | `unfixed_chunk_num=0, unfixed_token_num=5, adaptive_budget=True` |
| **RTF (6.74s 测试音频)** | **0.444** | 11 chunks, wall=2.99s |
| **RTF (28.5s 长音频)** | **0.730** | 45 chunks, wall=20.76s |
| **RTF (61.19 min 英文)** | **0.639** | 226 段 (VAD 切), wall=2348s |
| **WER (61.19 min, MiniMax 参考)** | **7.88%** | C-047 自适应生成长度（原 17.87%） |
| decode ms/token | **33 ms** | vs FP16 64 ms（1.9× speedup）|
| 与 torch golden 文本对比（去标点 CER）| **0%** | 内容字完全一致；INT8 自然输出 `。` |
| 末段文本（短音频）| `之前有顾客自己带酒水也没加收钱或者不让喝。` | 与 CUDA baseline（Q8_0）一致 |

> 详细报告见 `status/STATUS.md`，原始日志在 `reports/`。
> **最终报告：`reports/PROJECT_REPORT.md`**（精度基线为 MiniMax 云端 asr-1.0，非 CUDA）
> WER 与根因分析见 `reports/C047_CUDA_PARITY.md`（C-047）。

## 三个根因与修复顺序（详见 `reports/PROJECT_REPORT.md` §3）

| # | 根因 | 怎么发现的 | 修复 | 61-min WER |
|---|---|---|---|---|
| ① | optimum-intel 导出的 audio encoder **丢失了原模型的全局注意力**（参考实现的 `_prepare_attention_mask` 定义了但从未被调用） | torch 逐层对比：4 s 时逐 token cosine 只有 0.64，60 s 0.29 | 用 reviewer 的整段 encoder（`ov-encoder-segment-reviewer`，固定 `[1,128,2400]` + `n_valid`，全局注意力） | 23.5% → 17.9%<br>（与 ② 合计） |
| ② | 窗口编码器把**不满窗当成满窗**：`n_full_windows` 按块数向上取整而非按帧数向下取整，补的零帧被当有效音频编码且被永久缓存 | 逐 chunk 增长日志里 N_audio 与公式值不符（7.68 s：应是 100，实为 104） | `n_full_windows = mel_len // 800` | 同上（11 个最差段重复 4-gram 183 → 1） |
| ③ | **`max_new_tokens` 固定成 32，错译了官方的自适应生成预算**（1–4 token 负反馈） | 与 CUDA 官方 `example.py:118-155` 逐项对齐的 8 变体受控实验：只改这一项，5 段 40.27% → 4.36%；改 chunk/k/lookahead 全部无效 | `_adaptive_budget_init/update` + 中文分支，默认开启 | **17.87% → 7.88%** |

必须知道的两个耦合约束：

- **自适应必须配 `unfixed_token_num=5`** —— k=1 + 自适应在 640 ms 下退化到 29.19%（比固定 32 更差）。
  `transcribe_stream.py` 在检测到该组合时会打印告警。
- **不要照搬 CUDA 的 160 ms chunk** —— 实测换来 3.2 倍墙钟、WER 几乎无变化。
- **段尾 flush 预算保持 `max(64, ...)`** —— 官方段尾用 `first_max_new_tokens`（640 ms 时为 8），
  但 61-min 受控实验证明改过去会**截断段尾**：D 从 54 涨到 153，WER 7.88% → 8.41%（更差）。
  原因是 OV 的流式过程未必在最后一个 chunk 收敛。实验开关保留为
  `SegmentedStreamer(finish_budget='first')`，不作默认。


## 长音频 / OOM（C-014 关键修复）

### 复现结论（不分段时）

- **不是 OOM，是 encoder 位置编码上限**：`audio_config.max_source_positions=1500`（即 1500 × 80 ms = **120 s**）
- 崩溃点：音频累积约 **120.3 s** 时 encoder 内部 `Add_774378: Argument shapes are inconsistent`（n_audio ≈ 1556）
- 实时性：
  - 30 s 后 chunk wall 0.7 s（**瞬时 RTF ≈ 1.1**，已失守）
  - 80 s+ chunk wall 1.7-2.2 s（**瞬时 RTF ≈ 2.6-3.4**）
- 内存：RSS 平稳 4-4.8 GB（不是内存瓶颈，是计算量 + 位置编码上限）
- 曲线外推：30 min 时 n_audio ≈ 22500，crash 早在 120 s 就会发生

### 修复：VAD 切句分段（C-018 修正版）

- **不按固定时长盲切**（会把单词/句子从中间切断）
- 累积到 `min_segment_sec`（默认 **12 s**）后，在 `[12 s, max_segment_sec]`（默认 **20 s**）内找静音点切
- 切点必须走 `finish_streaming_transcribe` flush 尾巴（修了 C-015 #3 丢字）
- 新段 `unfixed_chunk_num=0`（per 官方 ws_server）
- 简单能量 VAD（100 ms 帧，最低 RMS 段中点）；无静音则硬切到 `max_segment_sec`

### CUDA（audio.cpp）不分段也有同样的上限

这不是 OV 独有的问题，是**同一份 HF 模型架构的固有上限**：

| 输入长度（不分段流式，Q8_0 + RTX 5050） | 结果 |
|---|---|
| 3 min / 4 min | ✅ 文本正确（RTF 1.37 / 1.64） |
| **5 min / 10 min** | ❌ `audio encoder token count exceeds max_source_positions` |

- CUDA 不分段触发阈值 **240–300 s**；OV 旧 IR 是 **120 s**（`max_source_positions=1500`）
- 结论：**CUDA 与 OV 都需要调用方自己做 VAD 切句**，audio.cpp 本身不支持长音频
- 按同一套 VAD 切段（226 段）跑完整 61 min，CUDA 流式是干净的：**WER 7.62%**（本机口径）/
  7.69%（reviewer 口径）。它是同一算法的 dGPU 参照，**不是本项目的验收基线**
  —— 验收基线是 MiniMax 云端 asr-1.0

### 验证（61.19 min 英文录音）

- 音频：`test_audio/260902_SPE_audio.wav`（16 kHz mono，Intel 业务会议英文）
- 计划 **226 段**（VAD 切），实测段长 min 0.6s / mean 16.2s / max 20s
- 全文 RTF ≈ 0.6，段 RTF P50 ≈ 0.58 / P95 ≈ 0.7 / max ≈ 0.99
- 全程 RSS 4.0-4.8 GB，**不随时长增长**（与分段前 30 s 后失守形成对比）
- 交付：
  - `reports/spe_61min_transcript.txt`（每段一行 `[起始秒-结束秒] 文本`）
  - `reports/spe_61min_segments.json`（每段 start/end/text/chunks/wall/rtf）

### `transcribe_stream.py` 默认行为（C-047 起为交付配置）

| 场景 | 行为 |
|--|--|
| 默认 | `SegmentEncoderOVBackend`（`ov-encoder-segment-reviewer` 整段全局注意力 encoder + `ov-int8-past` weight-only INT8 stateful decoder）|
| 短音频（≤ 20 s）| VAD 切成 1-2 段，行为与单段流式几乎一致 |
| 长音频（> 20 s）| VAD 在 12-20 s 内找静音切，226 段 ≈ 60 min |
| 生成长度 | **C-047 自适应**（默认开启）：每 chunk 按官方负反馈动态决定，base=8 / floor=16，取代固定 `max_new_tokens=32` |
| `--no-adaptive-budget` | 退回固定 `max_new_tokens=32`（仅复现历史行为；WER 17.87%）|
| `--no-seg` | 关闭分段，恢复单段（短音频 < 24 s 用；更长会撞 segment encoder 2400 帧硬上限） |
| `--strategy rolling` | 按 `max_segment_sec` 等分硬切（fallback） |
| `--strategy vad_roll` | VAD 优先，超过 max 强制切 |
| `--decoder-dir` | 切换 decoder IR。**C-043/C-044 的混合精度变体已证伪**，默认 `ov-int8-past` 即为达成 7.88% 的配置 |
| `--backend window` | 旧窗口 encoder 路径（仅复现历史行为用，非交付配置）|

> **C-045 变更说明**：旧默认是 `OVBackend` + optimum encoder IR（`models/ov-int8-past` 的 encoder 部分）
> + rolling 30 s。C-021 已实测该 encoder IR 全长度都错（4 s cos 0.64），已废弃。
> 现默认与 C-039 61-min 验收配置的 encoder/decoder 完全一致。

> **C-047 变更说明（重要）**：`max_new_tokens` 从固定 32 改为**自适应生成长度**。
> 这是 C-033 移植 R2T2 官方流式时漏掉的机制（见
> `third_party/Confucius4-R2T2/example.py:118-155`）。固定 32 会让单次自回归失控
> 直接写满冻结前缀，造成重复复读（61-min 实测 n3 重复 1983 次、插入错误 1025 词）。
> 61-min 全量集：**WER 17.87% → 7.88%，RTF 0.687 → 0.639**。
> 7.88% 已持平 C-045 的离线/两遍式 7.84%，**故两遍式方案不再需要**
> （省 3 秒段尾延迟 + 二次计算）。详见 `reports/C047_CUDA_PARITY.md`。

## 项目结构

```
confucius4-openvino/
├── transcribe_stream.py         # 部署入口（segment encoder + INT8 / 640ms / GPU.0 / VAD 12-20s / 自适应预算）
├── seg_stream.py                # C-014 分段驱动（VAD 找静音 + max 硬切）
├── backends.py                  # OVBackend + TorchBackend + ASRBackend 接口
├── segment_encoder_backend.py   # C-039 整段全局注意力 encoder backend（交付路径）
├── window_encoder_backend.py    # C-023 窗口 encoder backend（历史/对照）
├── streaming_asr.py             # backend-agnostic LSP 主循环 + C-047 自适应生成长度
├── c045_export_variants.py      # C-045 decoder 量化候选导出（mix4/mix8/INT4+AWQ）
├── c045_teacher_force.py        # C-045 候选确定性评估（top-1 / EOS / RTF）
├── c045_61min.py                # C-045 61-min 全长验证（可指定 decoder）
├── c045_two_pass.py             # C-045 两遍式第二遍（C-047 后已非必需，保留作对照）
├── c046_diag_stream.py          # C-046 流式 WER 差距根因取证（5 变体扫描）
├── c046_stream_fix.py           # C-046 LocalAgreement 共识提交修复（备选方案）
├── c046_loop_guard.py           # C-046 严格循环守卫（替代误报的 _detect_any_loop）
├── c047_cuda_parity.py          # C-047 CUDA/OV 流式逐项对齐对比（定位错误引入点）
├── c048_61min.py                # C-047/C-049 61-min 全量验证（baseline/adaptive/finish_first）
├── c045_wer.py                  # WER + S/D/I 分解（本机口径，与 c026 MiniMax baseline 对齐）
├── wer_check.py / wer_breakdown.py  # 真实 WER / S-D-I 误差分解（验收口径）
├── benchmark_int8_step.py       # C-013 分项 benchmark
├── diff_int8.py                 # INT8 vs torch 逐 chunk 对比 + CER
├── test_fe.py / test_decode_no_ehs.py  # 30s padding / tiny ehs 验证
├── test_audio/260902_SPE_audio.wav     # 61.19 min 英文真实录音（C-016 验收样本）
├── models/
│   ├── hf/                      # 原始 HF checkpoint
│   ├── ov-encoder-segment-reviewer/  # C-039 整段全局注意力 encoder IR（交付用）
│   ├── ov-fp16-past/            # FP16 stateful decoder IR（参考用，3.9 GB）
│   ├── ov-int8-past/            # INT8 stateful decoder IR（交付用，2.0 GB）
│   └── ov-mix4-past/ ...        # [已证伪，非交付路径] C-043/C-044 混合精度 decoder 变体
│                                #   lm_head-FP16 / per-group / per-layer 敏感度
│                                #   → C-047 证明 WER 瓶颈不在量化，这些产物仅存档
├── reports/                     # benchmark CSV/log + 流式输出 + transcript
│   └── PROJECT_REPORT.md        # 最终交付报告（精度基线 = MiniMax 云端 asr-1.0）
├── status/                      # 与 reviewer 通信：STATUS + history + CORRECTIONS
└── third_party/Confucius4-R2T2/ # 官方 r2t2 源码参考
```

## 部署运行

```powershell
# 1. 装环境（首次）
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2. 跑流式（默认 segment encoder + INT8 / 640ms / GPU.0 / VAD 12-20s / 自适应生成长度）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav

# 自定义参数
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --chunk-ms 320 --max-new-tokens 32

# 退回固定 max_new_tokens=32（C-047 前的历史行为，WER 17.87%）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --no-adaptive-budget

# 关闭分段（短音频 < 24 s 用）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --no-seg

# 换 decoder IR（注意：C-043/C-044 的混合精度变体已证伪，
# 7.88% 就是在默认 ov-int8-past 上达成的，混合精度不再更优）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --decoder-dir models/ov-int8-past

# 强制等分硬切（fallback，不推荐；会切到词中间）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --strategy rolling --max-segment-sec 20

# 流式输出示例
# [seg   0] start=   0.00s end=  13.68s chunks=22 wall= 7.16s RTF=0.523 text='Good morning everyone. Morning, let\'s ge'
# [seg   1] start=  13.68s end=  29.69s chunks=24 wall= 9.13s RTF=0.572 text='...'
# [transcribe] strategy=vad max_segment_sec=20.0 segments=226 chunks=...
```

## 关键技术修复（cumulative 12 步）

| 步骤 | 修复 | 效果 |
|--|--|--|
| 1. 导出 with-past | `optimum-cli export --task automatic-speech-recognition-with-past` | decoder stateful（57 ReadValue/Assign）|
| 2. backend 拆分 | TorchBackend（golden）+ OVBackend（生产）| 同接口、同循环 |
| 3. INT8 导出 | `--weight-format int8` | 2 GB（FP16 → INT8），NNCF 量化 |
| 4. **30s padding 修复** | `WhisperFeatureExtractor` `padding="do_not_pad"` | N_audio 85（不是 375），80% 静音被消除 |
| 5. **decode 步 tiny ehs** | `np.zeros((1,1,2048))` 占位 | stateful cross-attn 已缓存，5% 加速 |
| 6. 预热 pass | 先跑一遍不计时 | 避开 GPU 首次 kernel 编译 |
| 7. attention_mask 显式传 | TorchBackend generate | 消除 `attention mask is not set` 告警 |
| 8. decode 重置 state | 每 chunk `dec_infer.reset_state()` | KV 不串味 |
| 9. **VAD 切句** | 12-20 s 内找静音点切 | encoder 位置编码 ≤ 1500 永远满足；长音频 RTF 稳定 |
| 10. **新段 unfixed_chunk_num=0** | per 官方 ws_server | 段首不留 ghost prefix |
| 11. **切点 finish flush** | 段尾必走 `finish_streaming_transcribe` | 修 C-015 #3 丢字 bug |
| 12. **分段** | 简单能量 VAD | backend-agnostic，TorchBackend/OVBackend 共享 |

## 性能对比（6.74s 测试音频，warmup 后）

| 配置 | RTF | decode ms/tok | chunks | 与 torch 内容字差异 |
|--|--:|--:|--:|--|
| FP16 with-past, 320ms chunk | 1.368 | 64 | 22 | 0 |
| FP16 with-past, 640ms chunk | 1.166 | 64 | 11 | 0 |
| FP16 with-past, 1000ms chunk | 0.465 | 64 | 7 | 0 |
| **INT8 with-past, 640ms chunk** | **0.444** | **33** | 11 | **0** |
| CUDA baseline (Q8_0), 320ms | 0.544 | — | 22 | — |

## 句尾 `。` 问题（C-013 #6 结论）

- **torch FP32 golden**：句尾无 `。`
- **INT8**：句尾**有** `。`（chunk 7 / chunk 10）
- **CUDA Q8_0 baseline**：句尾有 `。`
- r2t2 官方 `finish_streaming_transcribe`（third_party/.../r2t2_asr.py:492-578）逻辑：和我们的 `streaming_asr.py:finish_streaming_transcribe` 一致
- **结论**：r2t2 官方逻辑本身 + FP32 torch 模型都不出 `。`，是模型精度问题。INT8 量化反而使 `。` 出现（与 CUDA Q8_0 一致）。**无需为 `。` 改算法**。

## Encoder 根因 & 修复（C-021~C-024）

### 根因

`optimum-intel` 导出的 encoder IR 在长音频上**逐 token 与 torch 不一致**（cosine 0.29-0.64，token 数也错）。
定位：`optimum-intel.Qwen3ASRModelPatcher._patch_audio_encoder` 用一份**简化版 forward** 替换了
`Qwen3ASRAudioEncoder.forward`，简化版对整段 mel 做：

1. **1D stride-8 conv**（把 100 帧一块的 chunk 折叠成 stride-8 的等长 token），丢掉 per-chunk 边界
2. **全局位置编码**（不是 per-chunk 循环 0-12），撞 `max_source_positions=1500` 上限
3. **标准 attention**（`is_causal=False` + 单一 mask），忽略 `cu_seqlens` 的 per-window 切分

证据（6.7 s 中文样本 parity，但 12-20 s 全坏）：
- 6.7 s < 800 帧：单 window，per-chunk 位置编码退化为全局，刚好巧合一致
- ≥ 12 s ≥ 1.2 个 window：分块/窗口逻辑被替换，cosine 暴跌
- 不分段 120 s 时 `Argument shapes are inconsistent`（n_audio=1556 > 1500）— 整段累积是另一表现

### 修复（方案 a，chosen）

不走 optimum 的 encoder IR，**自己用 `torch.jit.trace + ov.convert_model` 重新导出单窗 IR**：

- 输入固定 `(1, 128, 800)` + `cu_seqlens (2,) int32`（窗口内 valid token 数）
- 内部按 `qwen_asr.modeling_qwen3_asr.Qwen3ASRAudioEncoder.forward` 原逻辑：
  - 8 块 100-frame × 128-mel → 3 stride-2 conv → per-chunk 位置编码 (0-12，每窗内循环 8 次)
  - 24 层 attention，**显式构造 4D mask (1, 1, 104, 104)** 屏蔽 `cu_seqlens[1]` 之后的位置
    （为什么不用 cu_seqlens：SDPA / FA2 的 varlen 路径与原 eager 实现数值略差，且 trace 时 cu_seqlens 是输入张量；
    显式 4D mask 让 OV 用与原 Qwen3ASRAudioAttention 一致的 attention_interface）
- stride 保持：`mel.T.view(8, 100, 128).transpose(1, 2)`（与原 audio_tower 非 contiguous stride 一致，
  `mel.view(8, 128, 100)` 的 contiguous stride 会让 conv 输出有 0.04 数值差）

```python
# c023_export_window_encoder.py
class SingleWindowEncoder(nn.Module):
    def forward(self, input_features, cu_seqlens):
        x = input_features.squeeze(0)  # (128, 800)
        x = x.T.view(8, 100, 128).transpose(1, 2)  # (8, 128, 100) non-contig
        # 3 stride-2 convs + per-chunk pos emb (0..12) + 24 layers with 4D mask
        # output: (1, 104, 2048), Python side裁到 cu_seqlens[1]
```

导出：`ov.convert_model(traced, example_input=(randn(1,128,800), tensor([0,104], int32))` →
`models/ov-encoder-window/openvino_encoder_model.xml`（FP16 + FP32 两份）

### 验证（`c023_validate_window_encoder.py`）

| dur | n_mel | torch_n | ov_n | cos_mean | cos_min | pass |
|--:|--:|--:|--:|--:|--:|--|
| 4s | 400 | 52 | 52 | 1.0000 | 1.0000 | ✅ |
| 8s | 800 | 104 | 104 | 1.0000 | 1.0000 | ✅ |
| 10s | 800 | 104 | 104 | 1.0000 | 1.0000 | ✅ |
| 12s | 1200 | 156 | 156 | 0.9994 | 0.9984 | ✅ |
| 16s | 1600 | 208 | 208 | 0.9998 | 0.9986 | ✅ |
| 20s | 2000 | 260 | 260 | 0.9996 | 0.9966 | ✅ |
| 30s | 3000 | 390 | 390 | 0.9994 | 0.9916 | ✅ |
| 60s | 6000 | 780 | 780 | 0.9994 | 0.9780 | ✅ |

> 表中 n_mel 已用真实 100 frames/sec（hop=160, 16kHz）修正；之前 c023 验证脚本用
> `dur*80` 的错误标注不影响数值对比（用同一 n_mel 给 torch + OV），仅标签错。

### 流式 window cache（C-024 #3）

Qwen3-ASR encoder 的窗口之间**互相独立**（cu_seqlens per-window），所以流式时：

- 已填满的 800-mel 窗口（每 8 s 音频）的 encoder hidden states 可以**缓存**
- 每 chunk 只重新编码**最后一个未满窗口**（≤ 8 s 音频）
- encoder 每 chunk 成本有上界 ≈ 1 个 window（~30 ms GPU.0）

实现：`window_encoder_backend.py::WindowEncoderOVBackend`：
```python
for w in range(n_full_windows):
    if w < len(self._window_cache_ehs):  # 命中
        out_chunks.append(self._window_cache_ehs[w])
    else:  # 未命中
        ehs = self._encode_window(mel[:, w*800:(w+1)*800], 800)
        self._window_cache_ehs.append(ehs)
# partial 最后一窗永远重算
if last_chunk_count > 0:
    out_chunks.append(self._encode_window(mel[:, n_full_mel:], valid_in_partial))
```

## 性能瓶颈 & 后续优化

- **decode 仍占 60%**（33ms/token × 5-9 token/chunk）。如需进一步降低：
  - **C-006 step4 cached prefix**（prompt 头部 9 token 的 KV 复用）— 未实现，预期省 5-10%
  - **Window attention 复用**（n_window_infer=800）— **C-024 已实现**：encoder 每 chunk 只算最后未满窗（≤8 s 音频），满窗 ehs 缓存
  - **INT4**（`--weight-format int4 --ratio 1.0 --sym`）— 理论再省 30-40%，但精度风险大。**未做**（C-013 明确不做）
- **分段位置编码 hard cap**：encoder `max_source_positions=1500`（120 s）→ 必须 ≤ 20 s 段长。
  - 提升路径：换 encoder IR 重新 trace，把 dynamic shape 上限拉到 4096（成本是 IR 重导 + benchmark）

## 弃用的旧实现

- `ov_r2t2.py`（旧手写 OVR2T2ASR）— 已被 `backends.py::OVBackend` 取代
- `models/ov-fp16/`、`models/ov-int8/`（no-past 版本）— 已被 `models/ov-{fp16,int8}-past/` 取代
- `verify.py`（旧 CER 对比）— 已被 `diff_chunks.py` / `diff_int8.py` 取代
- `monitored_stream.py`（C-014 #1 OOM 监控）— 一次性脚本，验证完保留供复现用

## 协议

执行/监控协议、纠偏通道（CORRECTIONS.md）、检查点报告：见 `status/STATUS.md` 与 `status/CORRECTIONS.MD`。
