# C-045 执行报告：per-layer 混合精度 decoder + 两遍式

- 日期：2026-10-13 下午
- 执行者：WorkBuddy（按 `reports/WER_ANALYSIS_2026-10-13.md` 的改进路线执行）
- 环境：本worktree（代码/报告）+ 主仓库 `C:/Users/Trekker-PTL/confucius4-openvino`（.venv / models / test_audio，已建 junction）
- 设备：OpenVINO **GPU.0 = Intel Graphics iGPU**（脚本 assert 要求；GPU.1 是 NVIDIA 独显，未使用）

---

## 0. 一句话结论

**WER 从 17.87% 降到 7.68%（追平 CUDA 流式 7.62%），总 RTF 仍只有 0.76。**
做法是两件事叠加：

1. **per-layer 混合精度 decoder**（C-044 判定"做不到"，实测可行）：
   `nncf.compress_weights` 的 `IgnoredScope(patterns=...)` 让指定层保持 FP16。
   28 层里挑 12 层（mix12）把 EOS 一致率从 **63.41% → 87.80%**、top-1 从 94.12% → 97.77%，
   61-min 流式 WER 17.87% → **12.04%**（RTF 0.585 → 0.809）。
2. **两遍式解码**：流式给即时字幕 + 段尾离线重解给最终文本。第二遍 RTF仅 **0.176**
   （每段约 2.9 s），把 WER 再拉到 **7.68%**。
   最优架构是 **pass 1 用 int8（RTF 0.585）+ pass 2 用 mix12（RTF 0.176）**，
   即"用int8 的速度拿 mix12 的精度"，且已验证两版分段边界 226/226 一致。

附带发现：**量化敏感度强烈集中在网络前部**——同体积下"前 4 层 FP16"的 EOS 比
"后 4 层 FP16"高 **13.4 pp**（76.83% vs 63.41%）；以及一个**模板残留坑**：
离线解码会输出 `language None<asr_text>` 前缀，不剥离会让 WER 虚增约 3.7 pp。

---

## 1. 第0 步：部署入口对齐（已完成）

`transcribe_stream.py` 原默认是 `OVBackend` + optimum encoder IR（`models/ov-int8-past` 的
encoder 部分）+ rolling 30 s。C-021 已实测该 encoder IR 全长度都错（4 s cos 0.64），
与验收配置完全脱节。已重写为：

| 项 | 旧默认 | 新默认（= C-039 验收配置） |
|---|---|---|
| backend | `OVBackend` | `SegmentEncoderOVBackend` |
| encoder | optimum IR（C-021 证伪） | `models/ov-encoder-segment-reviewer` |
| decoder | `models/ov-int8-past` | `models/ov-int8-past`（可用 `--decoder-dir` 切换） |
| 分段 | rolling 30 s | VAD 12–20 s |
| unfixed_chunk_num | 2 | 0 |
| hallucination reset | 默认开 | 关（C-036 决定） |

新增参数：`--backend {segment,window}`、`--encoder-dir`、`--decoder-dir`、`--min/max-segment-sec`。
旧窗口路径保留在 `--backend window` 下仅供复现。README 已同步。

---

## 2. 关键事实修正：C-044 的三个前提有两处需要更正

**(1) `ov-int8-past` 本身就是 weight-only INT8。** IR 里 **0 个 FakeQuantize**，
只有权重侧的 `Convert/Subtract/Multiply` 反量化链；激活与 KV cache 全程 FP16。
所以"weight-only 量化"不是新方向，INT8 剩余的 5.9 pp top-1 差距**纯粹来自权重量化**，
与激活/KV 无关。

**(2) "NNCF 不支持 per-layer FP16 / per-layer 敏感度"只对 `nncf.quantize` 成立。**
`nncf.compress_weights` 支持：

- `ignored_scope=IgnoredScope(patterns=[...])`：正则屏蔽任意 op，保持 FP16
  （语义是 `re.match`，**锚定字符串开头**；层命名 `__module.model.thinker.model.layers.{i}.*`，
  本项目 28 层 × 7 MatMul/层）
- `ratio` + `sensitivity_metric`：自动 per-layer 敏感度混合

**(3) 但 INT8 模式的量化参数被硬锁死**（实测报错，比 C-044 描述更具体）：

| 想做的 | NNCF 3.4.0 结果 |
|---|---|
| INT8 + `all_layers` | ✗ `INT8 modes do not support all_layers option(s)` |
| INT8 + AWQ（带校准集） | ✗ `INT8 modes do not support dataset, awq option(s)` |
| INT8 + GPTQ | ✗ 同上，`gptq` |
| INT8 + `ratio`（敏感度混合） | ✗ `INT8 modes require per-channel quantization of all layers in 8 bit` |
| INT8 + `group_size`（per-group） | ✗ 同上 |
| INT4 + `group_size` / `all_layers` / AWQ | ✓ 支持（但 AWQ 导出进程在本机被硬杀，见 §6） |

即：**INT8 唯一可用的手段就是 per-channel 压缩 + `ignored_scope` 挑层保 FP16**——
这恰好就是本报告采用的方案。

---

## 3. 敏感度画像（本次最有价值的发现）

teacher-forcing 口径与 C-044 完全一致（3 段 / 82 chunks / 629 target tokens / 82 EOS steps），
int8 基线**精确复现** C-044 的 94.12% / 63.41%，因此可直接横向比较。

| 变体 | 保持 FP16 的层 | IR (MB) | top-1 | EOS |
|---|---|---:|---:|---:|
| int8（C-044 基线 = 当前交付） | 无 | 1643.3 | 0.9412 | 0.6341 |
| mixl2 | 后 2（26-27） | 1738.9 | 0.9428 | 0.6220 |
| mixf2 | 前 2（0-1） | 1738.9 | 0.9491 | 0.6707 |
| mixl4 | 后 4（24-27） | 1834.8 | 0.9459 | 0.6341 |
| mix4 | 前2+后2 | 1834.8 | 0.9507 | 0.6829 |
| **mixf4** | **前 4（0-3）** | 1834.8 | **0.9618** | **0.7683** |
| mixl8 | 后 8（20-27） | 2026.6 | 0.9475 | 0.6829 |
| mixf8 | 前 8（0-7） | 2026.6 | 0.9698 | 0.8171 |
| mix8 | 前4+后4 | 2026.6 | 0.9714 | 0.8171 |
| **mix12** | **前6+后6** | 2218.4 | **0.9777** | **0.8780** |
| mix16 | 前8+后8 | 2410.1 | 0.9777 | 0.8659 |
| int4lmfp16（C-043 已有） | INT4 + lm_head FP16 | 1439.7 | 0.8426 | 0.4146 |

结论：

1. **敏感度集中在网络前部**。同样把 4 层换成 FP16：前 4 层 EOS 76.83%，后 4 层 63.41%
   （= int8 基线，等于白换）。mix8里那 4 个后部层只贡献 +0.16 pp top-1。
2. **EOS 比 top-1 更能解释 WER**。EOS 一致率是"能不能停下来"的开关，插入（重复循环）
   正是 EOS 判错的后果。int8 的 EOS 只有 63.41% → 约 1/3 的 chunk 不该停却继续生成，
   与61-min 实测 I=1025（9.3 pp 插入）方向一致。mix12 把 EOS 拉到 87.80%。
3. **收益递减**：mix12 → mix16 体积 +192 MB 但 top-1 不再涨（0.9777 → 0.9777），EOS 反而
   略降。**mix12 是性价比拐点，mix16 被支配。**
4. lm_head FP16 / INT4 路线（C-043）被再次确认无效（EOS 41.46%，比 int8 还差）。

---

## 4. 61-min 全长验证（mix12）——已完成

配置与 C-039 完全一致：segment encoder + VAD 12-20 s + unfixed 0/5 + no reset。
产物：`reports/spe_61min_transcript_ov-mix12-past.txt`、`reports/c045_61min_ov-mix12-past/summary.json`

| 指标 | int8（C-039，当前交付） | **mix12** | 变化 |
|---|---:|---:|---|
| **WER（vs MiniMax 11066 词）** | 17.87% | **12.04%** | **-5.83 pp** |
| 替换 S | 789 | 542 | -247 |
| 删除 D | 49 | 47 | -2 |
| 插入 I | 1140 | **743** | **-397** |
| 总词数 | 12295 | 11717 | -578（少了很多幻觉） |
| n3_repeat（代理指标） | 1983 | 1403 | -29% |
| n4_repeat（代理指标） | 1207 | 642 | **-47%** |
| overall RTF | 0.585 | **0.809** | +38% |
| seg RTF P50 / P95 / max | 0.576/ 0.646 / 0.956 | 0.799 / **0.884** / 1.016 | — |

两个要点：

1. **WER 首次降到 12%量级**（目标 ≤11% 已近在咫尺），且插入词 −397 印证了 §3 的
   "EOS 一致率是主开关"结论——teacher-forcing 预测的 EOS +24.4pp 确实转化成了 WER。
2. **n3/n4 代理指标这次与真实 WER 同向**（n4 −47%）。此前 C-033 那次 cache 修复就是被
   这个代理指标误判成"无改善"，建议今后以 `c045_wer.py` 为准。
3. **RTF 代价**：overall 0.809仍 <1（可实时），但 P95 0.884 超过项目 0.8 验收线，
   seg max 1.016 意味着个别段会拖慢。若P95 是硬指标，应选 mixf4（§6）。

### 4.1 为什么没有再跑"干净 no-cache 61-min"（原改进路线第 1 步）

原第 1 步是"在窗口 encoder 路径上做一次干净的 no-cache 对照"，用来判决 encoder 侧的
陈旧化（ehs 满窗后不再更新）到底贡献多少。这条实验现在**结构上不再成立**：

- C-039 起交付路径已换成 **segment encoder（整段全局注意力）**，每个 chunk 都对
  "当前整段音频"重新编码一次，**不存在任何跨 chunk 的 encoder 缓存**，
  encoder 侧陈旧化在架构上已被消除；
- decoder侧同样是每 chunk `reset_state()` + 全量 prefill，也没有 KV 复用。

也就是说报告 §1 里"满窗 ehs 陈旧化"这条差异在当前交付配置中已经不存在，
再跑 no-cache 对照不会产生新的判决信息。原第 2 步（窗口 encoder 离线 per-segment）
同样被 segment encoder 取代，且离线基线已有（`reports/spe_hybrid_offline.txt`，8.65%）。

剩下的误差被拆成两块，本轮分别处理：
**权重量化**（§3 per-layer 混合精度）与**流式解码放大**（§5 两遍式）。

---

## 5. 两遍式（流式 +离线逐段重解）

数据动机：同一INT8 decoder，**离线逐段 WER 8.65% vs 流式 17.87%**
（`reports/spe_hybrid_offline.txt`），而 CUDA 流式是 7.62%。
说明流式增量解码把INT8 的 ~6% token 翻转放大成重复循环，**解码策略的影响比量化本身更大**。
第二遍脚本：`c045_two_pass.py`（直接复用第一遍的 segments JSON，不必重跑第一遍）。

（结果见下节 — `reports/c045_2pass_ov-mix12-past/summary.json`）

## 5. 两遍式（流式 + 离线逐段重解）——已完成，**这是本轮最有价值的交付**

数据动机：同一 INT8 decoder，**离线逐段 WER 8.65% vs 流式 17.87%**
（`reports/spe_hybrid_offline.txt`），而 CUDA 流式是 7.62%。
说明流式增量解码把 INT8 的 ~6% token 翻转放大成重复循环，**解码策略的影响比量化本身更大**。
第二遍脚本：`c045_two_pass.py`（直接复用第一遍的 segments JSON，不必重跑第一遍）。

实测（复用 226 段流式分段，第二遍 decoder = mix12）：

| 指标 | mix12 流式 | **mix12 两遍式** |
|---|---:|---:|
| **WER** | 12.04% | **7.68%** |
| 替换 S | 542 | 446 |
| 删除 D | 47 | 69 |
| 插入 I | 743 | **335** |
| 第二遍耗时 | — | **646 s / 3671 s 音频 = RTF 0.176** |

**两处关键修正/发现：**

1. **模板残留坑（重要）**：离线解码时模型会输出 `language None<asr_text>` 前缀
   （流式路径由 `parse_asr_output` 剥离，我第一版离线脚本漏了），226 段**全部**带此前缀，
   每段多3–4 个垃圾词 → 虚增 S≈870，WER 被高估到 11.40%。
   修正后（`c045_clean_offline.py`，无需重跑模型）**WER 7.68%**。
   凡新增解码路径，都必须走 `parse_asr_output`。
2. **第二遍极便宜**：每段约 16 s 音频只需约 2.9 s 重解（RTF 0.176），
   完全塞得进实时预算；代价只是最终文本比流式文本晚约 3 秒（段结束后立刻可用）。
   插入词 743 → 335 再次印证流式放大确实存在。

### 5.1 最优架构：pass 1 用便宜的 int8，pass 2 用 mix12

已验证 **mix12 流式跑出的 226 个分段边界与 int8（C-039）流式跑出的边界 226/226 完全一致**，
因此上表结果等价于下面这个组合，无需额外跑一遍：

| 遍 | 用途 | decoder | RTF | 质量 |
|---|---|---|---:|---|
| pass 1（流式，即时字幕） | 用户正在看的临时字幕 | **int8**（保持 C-039 配置） | 0.585 | 17.87%（会被pass 2 覆盖） |
| pass 2（段尾离线重解） | 最终字幕文本 | **mix12** | 0.176 | **7.68%** |
| 合计 | | | **≈0.76** | **7.68%** |

即：**用int8 的速度拿到 mix12 的精度**，总 RTF 仍远低于 1，
且彻底绕开了"mix12 流式 P95 0.884 超线"的问题（因为高精度 decoder 只在离线第二遍用）。

**7.68% vs CUDA 流式 7.62%——Intel iGPU 上的 OpenVINO 方案已基本追平 CUDA 基线**，
远低于项目验收线 WER ≤ 11%。

### 5.2 离线路径的 decoder 消融（int8 / mix12 / fp16）—— 归因结论

同一份 226 段分段、同一脚本、同一 encoder，只换第二遍 decoder：

| 第二遍 decoder | WER | S | D | I | 离线 RTF | IR (MB) |
|---|---:|---:|---:|---:|---:|---:|
| **FP16**（架构天花板） | **7.55%** | 428 | 73 | 334 | 0.246 | 3281.7 |
| mix12 | 7.68% | 446 | 69 | 335 | 0.176 | 2218.4 |
| int8 | 7.84% | 433 | 73 | 362 | 0.136 | 1643.3 |
| 参考：torch encoder + int8 离线（旧 hybrid） | 8.65% | 436 | 73 | 448 | — | — |
| 参考：CUDA 流式 | 7.62% | 473 | 75 | 295 | — | — |

### 5.3 归因结论（与 C-043 / C-044 的判断不同）

把四个数字放在一起看，结论非常干净：

| | int8 | mix12 | FP16 |
|---|---:|---:|---:|
| **流式 WER** | 17.87% | 12.04% | （RTF 1.166，不可用） |
| **离线 WER** | 7.84% | 7.68% | 7.55% |
| 差值 | **10.03 pp** | 4.36 pp | — |

1. **那10 pp 差距的主因是"流式增量解码的误差放大"，不是权重量化。**
   量化本身只值 **0.29 pp**（int8 离线 7.84% vs FP16 离线 7.55%）。
   同样int8，流式 17.87% → 离线 7.84%，**一次架构改动消掉 10 pp**。
2. **C-043 / C-044 走的量化路线（lm_head FP16 / INT4 / AWQ），是在解一个值0.29 pp 的问题。**
   真正的解法是架构性的——两遍式，也就是 STATUS 选项表里列了预估 9-11% 但**从未跑过**的 A3。
3. **per-layer 混合精度（mix12）的价值集中在流式那一遍**（17.87% → 12.04%，-5.8 pp），
   放进第二遍只赚 0.16 pp。所以它**不是**当前交付的必需品（见 §5.4）。
4. 顺带说明：**OV 整段 segment encoder 这条路本身没问题**——离线 7.55-7.84% 已经优于
   旧 torch encoder hybrid 的 8.65%。

### 5.4 交付建议

| 方案 | WER | 总 RTF | 需要新 IR? | 评价 |
|---|---:|---:|---|---|
| A. int8 流式（C-039 现状） | 17.87% | 0.585 | 否 | 达不到验收线 |
| B. mix12 流式 | 12.04% | 0.809（P95 0.884 超线） | 是（+575MB） | 超线且仍比两遍式差 4.4 pp |
| **C. int8 两遍式** | **7.84%** | **0.72** | **否** | ✅ **推荐**：改动最小、不需新 IR |
| D. mix12 两遍式 | 7.68% | 0.76 | 是 | +575MB IR 换 0.16 pp，不划算 |
| E. fp16 两遍式 | 7.55% | 0.83 | 3.3GB IR | +1.6GB 换 0.13 pp，不划算 |

**推荐 C**：WER 7.84%（验收线 ≤11%），总 RTF 0.72，离 CUDA 流式（7.62%）仅差 0.22 pp，
**且完全不需要新导出的 IR**（复用现有 `models/ov-int8-past`），部署改动只是加一个段尾重解步骤。

若部署方要求"最终文本与即时字幕完全一致"（即不能接受 pass 2 覆盖 pass 1），
则退而选 **B（mix12 流式12.04%）**，并接受 P95 0.884。

---

## 6. 未完成 / 受阻项

- **INT4 + AWQ 导出被硬杀**（无 Python 异常，疑似内存耗尽：AWQ 需同时持有 3.9 GB FP16
  模型 + 编译副本）。脚本 bug 已修（校准样本里的 `label` 字符串键被当成 OV 输入端口）。
  **但按 §5.3 的归因，这条路线现已无必要**——INT4 在离线路径上最多也就再赚 0.2 pp，
  而 INT8 离线已达 7.84%、FP16 天花板仅 7.55%。
- **两遍式的工程化**：目前 `c045_two_pass.py` 是离线批处理脚本（读segments JSON）。
  接进 `transcribe_stream.py` 作为在线"段尾重解"钩子还需约 0.5 h：
  在 `SegmentedStreamer` 每段结束时对该段音频再解一次并覆盖文本。
- **P95 RTF 口径**：mix12 流式 P95 0.884 超项目 0.8 验收线；若 P95 是硬指标，
  用 mixf4（1835 MB，top-1 0.9618 / EOS 0.7683）可把 P95 压回 0.8 以内。
- **单遍 vs 两遍的产品决策**：两遍式意味着最终字幕比即时字幕晚约 3 秒（段尾修正），
  需要产品侧确认可接受。
- **manual INT8 per-group**：已知 NNCF 层面走不通，只能手改 IR 权重与 scale；
  按 §5.3 归因（量化只值 0.29 pp）优先级已降至最低。

---

## 7. 产出文件

| 文件 | 说明 |
|---|---|
| `c045_export_variants.py` | 12 个 decoder 变体导出（patterns屏蔽层 + INT4/AWQ 尝试） |
| `c045_teacher_force.py` | 两阶段评估：Phase A top-1/EOS（只编译 decoder）+ Phase B RTF |
| `c045_61min.py` | 参数化 61-min 全长验证（`--decoder`） |
| `c045_two_pass.py` | 两遍式第二遍：离线逐段重解（复用第一遍分段） |
| `c045_wer.py` | 统一 WER + S/D/I 口径（与 WER_ANALYSIS 一致） |
| `c045_clean_offline.py` | 从离线结果 JSON 剥离 `language None<asr_text>` 前缀并重生成 txt |
| `reports/c045_export/results.json` | 导出结果（含失败原因原文） |
| `reports/c045_tf/tf_results.json` | teacher-forcing 全量指标 |
| `reports/spe_61min_transcript_ov-mix12-past.txt` | mix12 流式 61-min transcript（WER 12.04%） |
| `reports/spe_61min_offline_ov-{int8,mix12,fp16}-past.txt` | 两遍式第二遍 transcript（WER 7.84% / 7.68% / 7.55%） |
| `reports/c045_61min_*/summary.json`、`reports/c045_2pass_*/summary.json` | RTF / 分段统计 |
| `models/ov-{mixf2,mixl2,mixf4,mixl4,mixf8,mixl8,mix4,mix8,mix12,mix16}-past/` | 新导出的 decoder IR（10 个） |
| `status/logs/c045_*.log` | 全部运行日志 |
| `reports/spe_61min_segments_ov-mix12-past.json` | 226 段分段（与 C-039 int8 分段边界 226/226 一致） |

## 8. 复现命令

```powershell
# 1. 导出候选
.venv\Scripts\python.exe c045_export_variants.py

# 2. 确定性评估（top-1 / EOS / RTF）
.venv\Scripts\python.exe c045_teacher_force.py

# 3. 61-min 全长
.venv\Scripts\python.exe c045_61min.py --decoder models/ov-mix12-past

# 4. 两遍式第二遍（复用第 3 步的分段）
.venv\Scripts\python.exe c045_two_pass.py --segments reports/spe_61min_segments_ov-mix12-past.json --decoder models/ov-int8-past

# 5. 清理模板残留 + WER
.venv\Scripts\python.exe c045_clean_offline.py reports/spe_61min_offline_ov-int8-past.json
.venv\Scripts\python.exe c045_wer.py reports/spe_61min_offline_ov-int8-past.txt
```