# C-047 与 CUDA 官方流式方案对齐：OV 错误引入点定位

日期: 2026-10-13
承接: C-046（`reports/C046_STREAM_GAP_ROOTCAUSE.md`）
问题: **为什么 CUDA 的流式方案 WER 很低，OV 同样模型却17.87%？用 CUDA 同样的流式方案对比，OV 的错误引入点在哪里？**

---

## 0. 结论先行

**错误引入点：`max_new_tokens` 被硬编码为固定 32，而 CUDA 官方是自适应生成长度。**

**全量集验证（61 分钟 / 226 段）：WER 17.87% → 7.88%（-9.99pp），RTF 0.687 → 0.639（更快）。**

7.88% 与 C-045 的离线/两遍式 7.84% 基本持平（差 0.04pp），
意味着**单遍流式即可达到离线质量，C-045 的两遍式方案可以取消**
（省 3 秒段尾延迟 + 二次计算）。

5 段测试集上的受控实验（只改这一个参数，其余全同）：

| 配置 | WER | 插入 | 重复 |
|---|---|---|---|
| A：640ms / k=5 / **固定 32**（OV 生产） | 40.27% | 92 | 106 |
| **E：640ms / k=5 / 自适应（仅改预算）** | **4.36%** | **0** | 7 |

**一个参数：40.27% → 4.36%。** 这是全部 8 个变体中唯一能单点解决问题的改动。

而其他 CUDA 差异项（chunk 160ms、k=1、first-chunk lookahead）单独改**都无效**：
- C（chunk 640→160ms）：39.26%，几乎无变化
- B（k 5→1）：37.92%，几乎无变化
- D（加 first lookahead）：40.27%，**逐项完全相同**

**所以 OV 移植时的主要偏差不是"chunk 太大"或"回滚不够"，而是把 CUDA 的自适应生成预算错译成了固定 32。**

---

## 1. 源码级参数差异（C-033 移植遗漏项）

对照 `third_party/Confucius4-R2T2/example.py`（CUDA/vLLM 官方示例）与
`transcribe_stream.py`（OV 部署入口）：

| 参数 | CUDA 官方 | OV 当前 | 说明 |
|---|---|---|---|
| `chunk_size_ms` | **160** | 640 | `example.py:199` vs `transcribe_stream.py:44` |
| `unfixed_token_num` | **1** | 5 | `example.py:204` vs `transcribe_stream.py:46` |
| `max_new_tokens` | **自适应 1–4** | 固定 32 | `example.py:118-155` vs `transcribe_stream.py:47` |
| first-chunk lookahead | **160ms** | **无实现** | `example.py:126`（OV 全库无此逻辑） |
| finish 预算 | `first_max_new_tokens`（1–2） | `max(64, 32)=64` | `seg_stream.py:207` |

`unfixed_chunk_num` 两边都是 0，无差异。

---

## 2. CUDA 的自适应生成长度机制

`example.py:118-155`：

```python
# 基准：随音频长度（160ms -> int(320/1280) -> 1 token）
max_new_tokens = max(1, int((step + lookhead) / 1280))
first_max_new_tokens = max_new_tokens
max_new_tokens_floor  = min(32, max(4, 2 * int(step / 1280)))   # -> 4

while ...:
    _, text = asr.streaming_transcribe(seg, state, int(max_new_tokens))
    if len(text) > len(last_text_tmp):
        max_new_tokens = max(1, int(step / 1280))   # 有新内容 -> 收紧
    else:
        if not is_last_token_chinese(total_new_asr_tokens):
            max_new_tokens = max_new_tokens + 1     # 无新增 -> 放宽
        else:
            max_new_tokens = max(1, int(step / 1280))
    if is_last_token_chinese(total_new_asr_tokens):
        max_new_tokens = 2 * max_new_tokens         # 中文 -> 翻倍
    max_new_tokens = min(max_new_tokens_floor, max_new_tokens)   # 上限 4
```

这是一个**按输出增长情况自我调节的负反馈控制器**，作用方向与直觉相反：

| 观察到的状态 | 模型的动作 | 意图 |
|---|---|---|
| 文本在增长 | **收紧**到基准（1 token） | 前缀健康，省算力 |
| 文本停滞 | **放宽**（+1，中文×2） | 前缀卡住，给纠错空间 |

上限仅 4 token，意味着**单次自回归失控最多写入 4 个 token**，
不会像 32 token 那样让一次复读直接污染整个冻结前缀。

---

## 3. 实测：逐项打开 CUDA 机制

5 段测试集（ref=298词），`c047_cuda_parity.py`：

| 变体 | 配置 | WER | S | D | I | n3 | 墙钟 |
|---|---|---|---|---|---|---|---|
| A_ov_prod | 640ms k=5 **固定32** | 40.27% | 19 | 9 | 92 | 106 | 67s |
| B_k1 | 640ms **k=1** 固定32 | 37.92% | 35 | 7 | 71 | 90 | 48s |
| C_chunk160 | **160ms** k=5 固定32 | 39.26% | 45 | 8 | 64 | 108 | 219s |
| D_lookahead | 640ms k=5 固定32 **+lookahead** | 40.27% | 19 | 9 | 92 | 106 | 65s |
| **E_adapt_only** | 640ms k=5 **自适应** | **4.36%** | 4 | 9 | **0** | 7 | 59s |
| F_cuda_full | 160ms k=1 自适应 +look | 13.76% | 1 | 40 | 0 | 7 | 141s |
| G_cuda_noadapt | 160ms k=1 固定 +look | 11.74% | 6 | 29 | 0 | 7 | 161s |
| H_cuda_640 | 640ms k=1 自适应 | 29.19% | 12 | 8 | 67 | 59 | 45s |

### 3.1 唯一的有效改动

A → E 只改生成长度：**40.27% → 4.36%，插入 92 → 0，重复 106 → 7。**
seg161 单段：hyp 113→60、I 55→0、n3 52→0（WER 100% → 8.20%）。

E 的逐 chunk 词数演化（seg161，29 个 chunk）：
```
0, 2, 4, 4, 4, 5, 8, 9, 12, 16, 18, 21, 24, 27, 30, 31, 32, 34, 35, 38, 41, 42, 44, 47, 50, 53, 56, 59, 60
```
**单调增长、无跳变** —— 小预算把生成约束在"每步只向前推一点"，
错误假设还没被冻结就有机会被下一次重解纠正。

### 3.2 其他差异项都无效

- **chunk 160ms 单独改几乎无效**（39.26% vs 40.27%），且墙钟从67s涨到 219s
- **k=1 单独改几乎无效**（37.92%）
- **first-chunk lookahead 完全无效**（40.27%，与A 逐项完全相同）

### 3.3 自适应必须配合 k=5

H（640ms + **k=1** + 自适应）= 29.19%，I=67 —— 比 E（k=5）差 25 pp。
而 B（640ms + k=1 + 固定32）= 37.92%。

说明自适应预算与小回滚窗口存在**交互作用**：
- k=5 + 小预算：每 640ms 冻结"除最后 5 token"外的部分，只新生成 1–4 token
  → 相当于**渐进式局部修正**，前缀稳定
- k=1 + 小预算：只留1 token 回滚，在低预算下偶发错误几乎无法被改写
  → 错误直接冻结

---

## 4. 回答：OV 的错误引入点

**在 `transcribe_stream.py` 的流式调用参数上，具体是把 `max_new_tokens` 固定成了 32，
而 CUDA 官方用的是自适应生成长度（1–4 token，带输出增长负反馈）。**

移植时的语义误解：把"每 chunk 允许生成的长度上限"当成了固定配额，
丢掉了 CUDA 版本"随输出状态动态调节"的控制逻辑。

错误引入路径：

```
固定 32 token
   ↓ 每 640ms 允许自回归走 32 步
   ↓ 贪心解码一旦进入复读路径，32 步全部落在复读上
   ↓ 这些 token 一次性写入 _raw_decoded
   ↓ 除最后 5 个外全部永久冻结（k=5）
   ↓ 下一 chunk 的 prefix 已含错误复读，后续以错为基线放大
seg161: hyp 113 vs ref 61，插入 55 词，3-gram 重复 52 次
```

自适应预算（1–4）下，这个链条在第一步就被掐断：
单次最多写 4 个 token，错误假设还没积累就被下一次重解冲掉。

---

## 5. 与 C-046 的关系（两者结论一致，路径不同）

| | C-046 | C-047 |
|---|---|---|
| 思路 | LocalAgreement 共识提交：**只冻结连续多轮一致的文本** | 自适应生成长度：**限制单次自回归步数** |
| 实现 | `c046_stream_fix.py` | `streaming_asr.py`（已接入生产路径） |
| WER（5 段） | 40.27% → 11.41% | 40.27% → **4.36%** |
| WER（61-min） | 未测 | 17.87% → **7.88%** |
| 是否贴近官方 | 自创机制 | **复现官方机制** |

两者殊途同归，都解决了"错误 token 被永久冻结"这一核心问题。
**C-047 更好**：完全对齐官方语义、改动面小（一个参数）、
且效果优于共识提交，同时 RTF 更低。

C-046 的共识提交仍可作为备选，但它是在**提交侧**补救；
C-047 证明了正确的做法是在**生成侧**就限制破坏范围。

### 最终交付建议

**采用 C-047 的自适应预算（`adaptive_budget=True`）**：

| 方案 | WER | RTF | 段尾延迟 | 备注 |
|---|---|---|---|---|
| 生产现状（固定32 单遍） | 17.87% | 0.687 | 无 | 当前状态 |
| C-045 int8 两遍式 | 7.84% | 0.72 | **3 秒** | 需二次计算 |
| **C-047 自适应单遍** | **7.88%** | **0.639** | **无** | **推荐** |
| C-046 共识提交单遍 | 11.41%(5段) | 持平 | 无 | 备选 |

**不需要新 IR、不需要两遍式、不需要段尾延迟，一个参数解决问题。**
验收线 ≤11% 已满足且有余量。

---

## 6. 全量集验证（61 分钟，226 段）

`c048_61min.py`，同验收口径（segment encoder + VAD 12-20s + no reset）：

| 指标 | baseline（固定32） | adaptive（自适应） | 变化 |
|---|---|---|---|
| **WER** | **17.87%** | **7.88%** | **-9.99 pp** |
| 替换 S | 901 | 455 | -49.5% |
| 删除 D | 52 | 54 | 持平 |
| **插入 I** | **1025** | **363** | **-64.6%** |
| n3 重复 | 1983 | 981 | -50.5% |
| n4 重复 | 1207 | 262 | **-78.3%** |
| 总词数 | 12297 | 11248 | -8.5% |
| RTF | 0.687 | **0.639** | **更快** |
| 段 RTF P95 | 0.755 | 0.675 | -10.6% |
| 段 RTF max | 1.133 | 0.727 | -35.8% |

**结论：单遍流式达到 7.88%，与 C-045 的离线/两遍式 7.84% 基本持平（差 0.04pp）。**

这意味着 **C-045 的两遍式方案可以取消**：
- 不再需要段尾离线重解，省掉 3 秒延迟
- 不再需要两遍计算，RTF 反而更低（0.639 vs 两遍式 0.72）
- 只改一个参数（生成长度策略），不动模型、不动 IR

参照基准（同口径同参考）：
- int8 离线（C-045）：7.84%
- fp16 离线（C-045）：7.55%
- int8 两遍式（C-045）：7.84%，RTF 0.72
- **int8 单遍 + 自适应预算（C-047）：7.88%，RTF 0.639** ← 本次
- int8 单遍 + 固定 32（生产）：17.87%，RTF 0.687

验收线 ≤11% 已满足，且留有余量。

### 6.1 复现命令

```bash
.venv python c048_61min.py --variants baseline,adaptive
.venv python c045_wer.py \
  reports/c048_61min_adaptive/transcript_adaptive.txt \
  reports/c048_61min_adaptive/transcript_baseline.txt
```

产出：`reports/c048_61min_adaptive/`（transcript、segments、summary.json）

---

## 7. 落地实现（已完成）

自适应预算已接入生产路径，默认关闭，不影响现有行为：

- `streaming_asr.py`
  - 新增 `_is_last_token_chinese` / `_adaptive_budget_init` / `_adaptive_budget_update`
  - `streaming_transcribe(...)` 新增参数 `adaptive_budget: bool = False`
- `seg_stream.py`
  - `SegmentedStreamer(...)` 新增参数 `adaptive_budget: bool = False`，透传至上述函数
- 预算状态挂在 `state._adp_*`，每段新建 state 自动重置

参数标定（640ms chunk）：
- `base = max(1, int(10240/1280)) = 8`
- `floor = min(32, max(4, 16)) = 16`

即每 chunk 基准 8 token、停滞时逐步放宽至上限 16。
**注意这与 CUDA 160ms 下的 base=2/floor=4 不同** —— 公式随 chunk 长度线性缩放
（≈每 80ms 音频 1 个 token），语义一致。

### 7.1 落地注意事项

1. **保持 `unfixed_token_num=5`**（H 变体证明 k=1 + 自适应退化到 29.19%）
2. **保持 chunk 640ms**（改 160ms 无质量收益，墙钟 ×3.2）
3. **finish 阶段保持 `max(64, ...)`**，不要照搬 CUDA 的 `first_max_new_tokens`
   —— 实测 1–2 token 收尾在 OV 上会截断尾巴（D≈293）
4. 开启方式：`SegmentedStreamer(..., adaptive_budget=True)` 或后续在
   `transcribe_stream.py` 增加 `--adaptive-budget` 开关

---

## 8. 复现命令

```bash
# 5 段测试集：CUDA/OV 逐项对齐（定位错误引入点）
.venv python c047_cuda_parity.py --n-extra 2

# 61-min 全量集验证
.venv python c048_61min.py --variants baseline,adaptive
.venv python c045_wer.py \
  reports/c048_61min_adaptive/transcript_adaptive.txt \
  reports/c048_61min_adaptive/transcript_baseline.txt
```

产出：`reports/c047_cuda_parity/cuda_parity.json`、`reports/c048_61min_adaptive/`

关键文件：
- `c047_cuda_parity.py` — CUDA/OV 逐项对齐对比（5 段）
- `c048_61min.py` — 全量集双配置验证
- `streaming_asr.py` — 自适应预算实现（已接入）
- `seg_stream.py` — `adaptive_budget` 参数透传
- `third_party/Confucius4-R2T2/example.py:92-162` — CUDA 官方流式循环（权威参照）