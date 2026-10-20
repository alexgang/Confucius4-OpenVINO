# Reviewer 上线汇总：Confucius4-R2T2 → Intel OpenVINO 流式 ASR

- **日期**：2026-10-15
- **代码**：`origin/c038-v2-ir` @ `7d42aad`（已同步远端）
- **当前状态**：**WAITING_REVIEW** — 交付配置已就绪，等待你确认报告口径与下一步
- **一句话结论**：上一轮待决的核心问题「INT8 量化导致 18.21% WER 是否可接受」**已被推翻**——
  瓶颈不在量化，而在流式生成长度机制。修复后 61-min 全量集 **WER 7.88%**，验收线 ≤11% 已满足。

---

## 0. 请 reviewer 先看这里：上轮结论已被推翻

你上次（10-13 凌晨）设的待决状态是：

> 「c039 (plain INT8) 18.21% WER 已是当前最佳…精度差距来自量化误差 + 流式 unfixed 丢词 +
> VAD 切段边界，**不在单一根因**」→ 请你在 (a) 接受 18.21% / (b) 手工 INT8 per-group /
> (c) 等 NNCF 升级 之间决策。

**这个判断需要修正。** C-047 用受控实验证明差距来自**一个被错译的参数**：

| | CUDA 官方（`third_party/Confucius4-R2T2/example.py`） | OV 移植版 |
|---|---|---|
| `max_new_tokens` | **自适应 1–4 token，带输出增长负反馈** | **固定 32** ← 错误引入点 |

只改这一个参数、其余全同（5 段探针集，ref=298 词）：

| 配置 | WER | 插入 I | 三连重复 |
|---|---|---|---|
| 640ms / k=5 / 固定 32（原生产） | 40.27% | 92 | 106 |
| **640ms / k=5 / 自适应**（仅改预算） | **4.36%** | **0** | 7 |

**其他 CUDA 差异项单独改全部无效**，都排除掉了：

- chunk 640→160ms：39.26%（墙钟 ×3.2，零收益）
- `unfixed_token_num` 5→1：37.92%
- first-chunk lookahead：40.27%（与基线**逐项完全相同**，OV 全库根本没实现这个机制）

**机制解释**（为什么上限 4 比上限 32 好）：自适应控制器在文本增长时收紧到 1 token、
停滞时放宽。价值不在预算小，而在**上限 4** —— 单次自回归失控最多写入 4 个 token 就被截断；
而 32 会让一次复读直接污染整个已冻结的前缀。E 变体逐 chunk 词数是 `0,2,4,4,5,8,…,60`
单调增长无跳变，基线则直接冲到 113 词。

**含义**：C-041（跨段 state 排查）、C-043/C-044（INT8 per-group / INT4 / NNCF 升级）
这一整条量化优化路线，**其必要性已被证伪**。当前 7.88% 是在 plain INT8 上取得的。

---

## 1. 交付成果（61-min 全量集 / 226 段 / 12297 词，同一验收口径）

| 指标 | 修复前（固定 32） | **修复后（自适应）** | 变化 |
|---|---|---|---|
| **WER** | 17.87% | **7.88%** | **−9.99pp** |
| 替换 S | 901 | 455 | −49.5% |
| 删除 D | 52 | 54 | 持平 |
| **插入 I** | 1025 | 363 | **−64.6%** |
| n3 三连重复 | 1983 | 981 | −50.5% |
| n4 四连重复 | 1207 | 262 | **−78.3%** |
| **RTF** | 0.687 | **0.639** | **更快** |
| 段 RTF P95 | 0.755 | 0.675 | −10.6% |
| 段 RTF max | 1.133 | 0.727 | −35.8% |

baseline 数字与 C-045 记录的生产值**逐项一致**，确认复刻链路与 WER 口径无误。

**横向对照**：

| 方案 | WER | RTF | 段尾延迟 | 说明 |
|---|---|---|---|---|
| CUDA 官方流式（reviewer 实测） | 7.69% | — | — | 上界参考 |
| 生产现状（固定 32 单遍） | 17.87% | 0.687 | 无 | 修复前 |
| C-045 int8 两遍式 | 7.84% | 0.72 | **3 秒** | 已废弃 |
| **C-047 自适应单遍** | **7.88%** | **0.639** | **无** | **推荐交付** |
| C-046 共识提交单遍 | 11.41%(5段) | 持平 | 无 | 备选 |

**7.88% 与 CUDA 官方的 7.69% 相差 0.19pp**，且已追平 C-045 两遍式（7.84%）——
所以**两遍式可以取消**，省掉 3 秒段尾延迟和一次全量解码。

---

## 2. 已落地的代码（默认即最优，不需额外参数）

```powershell
.venv/Scripts/python.exe transcribe_stream.py path\to.wav
```

| 文件 | 改动 |
|---|---|
| `streaming_asr.py` | 新增 `_adaptive_budget_init` / `_adaptive_budget_update` / `_is_last_token_chinese`；`streaming_transcribe(..., adaptive_budget=True)` |
| `seg_stream.py` | `SegmentedStreamer(..., adaptive_budget=True)` 透传 |
| `transcribe_stream.py` | `DEFAULT_ADAPTIVE_BUDGET = True`，开关反转为 `--no-adaptive-budget` |

**安全护栏**：`adaptive_budget=True` 但 `unfixed_token_num != 5` 时打印 WARN。
这是必要的——H 变体实测该组合（k=1 + 自适应）会退化到 **29.19%**，而命令行改 k 的人
不会知道这个耦合关系。

640ms chunk 下标定值：`base=8` / `floor=16`（官方公式随 chunk 线性缩放，≈每 80ms 音频 1 token）。

---

## 3. 两个必须知道的约束（实测得出，勿照搬 CUDA）

1. **必须配 `unfixed_token_num=5`** —— k=1 + 自适应会退化到 29.19%
2. **不要照搬 CUDA 的 finish 预算**（1–2 token）—— OV 生成质量低于 vLLM，流式未必收敛，
   finish 仍需 `max(64, ...)` 兜底。实测 1–2 token 收尾会截断尾巴（D≈293，输出全空）

另外 chunk **不要**改回 160ms：墙钟 ×3.2，WER 只从 40.27% 动到 39.26%。

---

## 4. 需要你决策的事项

### 4.1 【主要】验收口径与报告定稿

请确认按哪个口径写 PROJECT_REPORT.md：

- **A（建议）**：以 **7.88% / RTF 0.639 / 单遍 / 无延迟** 为最终交付数字。
  报告会明确修正此前「18.21% 是最佳、差距源于量化」的结论，并给出 C-047 受控实验证据链。
- **B**：先补测再定稿 —— 例如 CUDA 全长对照（`C-020`，历史上因 CUDA 撞
  240–300s `max_source_positions` 上限被 demote），或其他你指定的验证。

**待你确认：报告以 A 口径定稿，还是需要补 B 项验证？**

### 4.2 量化路线是否关闭

C-043/C-044 的量化优化路线（手工 INT8 per-group、INT4、AWQ、等待 NNCF 升级）
在当前结果下**已无必要**（7.88% 是在 plain INT8 上达成的，验收线已过）。

**请确认：这条路线关闭 / 保留待命 / 仍要求继续做？**
（手工 INT8 per-group 仍可实现，`c043_export_pergroup.py` 就在仓库里，预估 4–8h，
但预期收益已从「决定性」降为「边际」。）

### 4.3 C-045 两遍式脚本的处置

`c045_two_pass.py` 已降级为历史对照（7.84% vs 单遍 7.88%，但多 3 秒延迟 + 更高 RTF）。
**保留作对照 / 删除？**

### 4.4 中文场景未验证

本次验证集是 61-min **英文**音频。`_is_last_token_chinese` 分支（中文时预算放宽 ×2）
代码已实现且单元级验证正确，但**未在真实中文流式上跑过全量**。
若交付场景含中文，建议补一次中文验证（脚本就绪，半天内可出）。

---

## 5. 关键文件索引

| 内容 | 路径 |
|---|---|
| **C-047 完整分析报告** | `reports/C047_CUDA_PARITY.md` |
| C-046 根因报告 | `reports/C046_STREAM_GAP_ROOTCAUSE.md` |
| C-045 结果 | `reports/C045_RESULTS.md` |
| WER 误差分解 | `reports/WER_ANALYSIS_2026-10-13.md` |
| 全量集产物（baseline/adaptive 双份） | `reports/c048_61min_adaptive/` |
| 受控实验原始数据（逐 chunk 预算日志） | `reports/c047_cuda_parity/cuda_parity.json` |
| 全程状态日志 | `status/STATUS.md` |
| 全量集复现 | `c048_61min.py` → `c045_wer.py` |

---

## 6. 复现命令

```powershell
# 全量集双配置验证（约 45 分钟：baseline + adaptive 各跑一遍）
.venv/Scripts/python.exe c048_61min.py --variants baseline,adaptive

# 计算 WER
.venv/Scripts/python.exe c045_wer.py `
  reports/c048_61min_adaptive/transcript_adaptive.txt `
  reports/c048_61min_adaptive/transcript_baseline.txt

# 受控实验（8 变体，复现 40.27% → 4.36%）
.venv/Scripts/python.exe c047_cuda_parity.py --n-extra 2

# 部署入口
.venv/Scripts/python.exe transcribe_stream.py path\to.wav
```

---

## 7. 状态与 TODO

**state: WAITING_REVIEW**

- [x] 定位 OV 与 CUDA 流式的差距根因（C-047 受控实验锁定单参数）
- [x] 实现修复并设为默认（自适应生成长度）
- [x] 61-min 全量集验证（226 段）：WER 17.87% → 7.88%，RTF 0.639
- [x] 代码同步远端（`origin/c038-v2-ir` @ `7d42aad`）
- [ ] **reviewer 确认报告口径**（§4.1）
- [ ] **reviewer 决定量化路线是否关闭**（§4.2）
- [ ] PROJECT_REPORT.md 按确认口径定稿（旧版仍是 C-038 时代数字，需重写）
- [ ] （建议）中文场景验证
- [ ] 主工作区 `C:/Users/Trekker-PTL/confucius4-openvino` 落后远端 1 个合并提交，
      如需在那里开发请先 `git pull`

---

## 8. 需要 reviewer 回答的三个问题（压缩版）

1. **报告按 7.88% 定稿，还是要先补 CUDA 全长对照/其他验证？**
2. **量化优化路线（C-043/C-044）关闭吗？** 现有证据表明其必要性已被证伪。
3. **交付场景含中文吗？** 含的话建议补一次中文全量验证（自适应预算的中文分支未实测过）。