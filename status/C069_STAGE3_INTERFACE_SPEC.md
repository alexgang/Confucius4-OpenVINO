# C-066 阶段 3 · 方案 B：`inputs_embeds` 解码器导出规格

> 状态：**等待导出**。本机 torch 被 WDAC 企业策略拦截（见 STATUS「torch 拦截根因」），
> 按 C-069 铁律不绕过。此文件给出完整接口规格，**在任意有 torch 的机器上照此导出即可**。

---

## 为什么需要方案 B

现有 stateful 解码器 IR（`models/ov-int8-past` 等）**不能上 NPU**，三重障碍：

1. **动态形状** —— 输入签名含 `[?]`，NPU 插件直接拒绝
2. **状态变量** —— 57 个 `ReadValue` + 57 个 `Assign`（KV 缓存），NPU 不支持图内状态
3. **图内形状计算** —— `ShapeOf` 35、`Range` 4、`CumSum` 1、`GatherElements` 1、`ScatterNDUpdate` 3

Encoder 侧我们用 `Model.reshape()` 解决了动态形状，但**状态变量与图内形状计算无法用 reshape 解决**，
必须改模型结构 → 只能重新导出。

GenAI 的 NPU 流水线（`NPUW_LLM`）要求：静态形状 + 预填充分块 + 静态 KV 缓存 +
**不支持 beam search**。这正是「标准 LM + `inputs_embeds`」的形态。

---

## 需要导出的模型

### 1. 主体：标准 Qwen3 LM（`inputs_embeds` 为输入）

| 项 | 值 | 说明 |
|---|---|---|
| 输入名 | `inputs_embeds` | **不要** `input_ids`，音频嵌入在 Python 里拼好再送入 |
| 输入形状 | `[1, MAX_PROMPT_LEN, 2048]` | **静态**；`hidden_size=2048`（取自 `models/hf/config.json` 的 `text_config.hidden_size`，并经 `c069g` 实测 IR 确认；早期版本本文件误写 4096，已更正） |
| `MAX_PROMPT_LEN` | **512** | 见下方预算推导 |
| KV 缓存长度 | `max_length = 1024` | NPUW 默认提示上限 1024 |
| `beam_idx` | **不保留** | NPUW **不支持 beam search**；greedy 解码无需它 |
| 权重精度 | `INT4_SYM`，**按通道** `--sym --ratio 1.0 --group-size -1` | NPU 友好；见下方精度警告 |
| 附加属性 | 若插件认识则设 `NPUW_QWEN3_ASR_MAX_ENCODER_LEN = 312` | 主线 2026.4.1 **不认识**，可省 |

**`MAX_PROMPT_LEN = 512` 的预算推导**（C-066 给的上界）：
```
模板 system + user 前缀          ≈ 13 tokens
音频 token（≤ 24 s 音频）        ≤ 312 tokens
language 提示 + 回复引导前缀      ≤ 100 tokens
生成余量                          预留
────────────────────────────────────
合计                             ≤ 425  →  取 512（向上对齐 64 的倍数）
```
C-068 的 PR 公式是 `align_up(max_encoder_len + 128, 64)` = `align_up(312+128,64)` = **512**，
与此一致。

### 2. 量化精度警告（重要，不要沿用现有结论）

现有全量 INT4 解码器用的是 **`INT4_SYM` + `g128`**，实测 WER **+0.352 pp 不显著**。
但 **NPU 友好的按通道（`group-size -1`）不等于 g128**，C-067 已明确提醒：

> 「上 NPU 的解码器需要重新量化成按通道，精度可能比 g128 更差」

**所以阶段 3 必须单独重测 WER，不能沿用 g128 的 +0.352 pp。**

---

## Python 侧推理契约（导出后如何调用）

`encoder_hidden_states` 形状为 `[1, N_audio, 2048]`（2048 = 模型的隐藏维）。
需要在 Python 里完成三步拼装，再送进 LM：

```
1. 文本前缀      : tokenizer 编码 ids_left            → [L,]
2. 音频占位      : ids_left + [AUDIO_PAD]*N_audio + ids_right + prefix_ids
                    ↑ AUDIO_PAD = 151676（AUDIO_START=151669, AUDIO_END=151670）
3. 词嵌入 + 替换 : emb(ids) → 把 N_audio 个 AUDIO_PAD 位置的向量
                   替换成 encoder_hidden_states.squeeze(0)
4. 送入 LM       : inputs_embeds = [1, 512, 2048]，右侧用 padding token 填充
5. 生成          : greedy，取 lm_head 输出 argmax，直到 EOS
                   EOS_IDS = [151643, 151645]
```

关键常量（已在 `backends.py` 中确认，可直接复用）：
```python
SAMPLE_RATE   = 16000
AUDIO_START   = 151669   # <|audio_start|>
AUDIO_END     = 151670   # <|audio_end|>
AUDIO_PAD     = 151676   # <|audio_pad|>
EOS_IDS       = [151643, 151645]
```
音频 token 数公式（`backends.py` 的 `_qwen3_get_feat_extract_output_lengths`）：
```
N_audio = 13 * (frames // 100) + aftercnn_tail(frames % 100)     # frames = mel 帧数
```

---

## 交付物清单（导出方需回传）

- [ ] `openvino_decoder_model.xml` + `.bin`（INT4_SYM 按通道）
- [ ] **导出脚本**（要能复现，写进 STATUS）
- [ ] 上面表格里的接口字段实测值（输入名、各维长度、是否有 `beam_idx`、KV 轴位置）
- [ ] 若用 `NPUW_LLM_BATCH_DIM` / `SEQ_LEN_DIM`，给出**对应的 KV 轴位置**

---

## 阶段 3 验收判据（C-066）

- 与 GPU INT8 基线做 **12–27 分钟**同一批语音段对比
- **WER + 配对 bootstrap 95% CI**（方法 B），不用 teacher-forcing 下结论
- 速度：**P50 与整体 RTF**（全新进程、ABBA 顺序），P95/max 只列出
- 每块处理耗时、收尾耗时、GPU compute 占用下降比、NPU/CPU 占用、内存

---

## 备选：方案 A（现有 IR 直接 NPUW）

按 C-067 照常试一次、记录报错全文。已知必失败（动态形状 + 状态变量 + 图内形状计算），
**不作为主路线**。若要试，属性：
```
NPU_USE_NPUW = YES
NPUW_LLM = YES
NPUW_LLM_MAX_PROMPT_LEN = 512
NPUW_LLM_MIN_RESPONSE_LEN = 1
```
现有 IR 的自定义输入 `encoder_hidden_states` 很可能不被识别 —— 失败即记录。
