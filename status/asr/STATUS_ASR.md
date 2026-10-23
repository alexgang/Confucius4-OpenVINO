# STATUS_ASR
last_ack: ASR-003
更新时间: 2026-10-23 14:05
当前任务: **§10 三项改动已实施并验证（用户裁决 1.yes/2.yes/3.yes/4.no）**：① 静音门限改相对判据（段内 p90−12dB，`_silence_threshold()`，替换 `due()` 行 456 与 `_silence_tail()` 的硬编码 −40dBFS）；② `_has_speech` 加相对分支（段内 p90−18dB，与绝对分支取并集）+ 空段拒切防护 `_speech_ratio_ok()`（相对语音覆盖率 ≥0.40）；③ 回环立体声混合 `_stereo_to_mono()`（含**反相检测**）。**真实实现 A/B（直接调用改后的 `seg.due()`）**：真实回环 120s 间隔 17.28s→**6.40s**、>12s **62.5%→6.2%**、硬切 4→0；真实演讲 12 分钟空段 0→0、>12s 0%→0%、规则2 切点 10/10 安全；低电平 gain0.3/0.1 >12s 67.4%/100%→**0%**
阻塞 / 待用户决定: ① **§10.6**：回环左右声道收益数据待补（采集时回环是数字静音 `db_L=db_R=−120dB`），请在播放视频时跑 `results\asr_diag\probe_loopback_stereo.py --seconds 30`；② **§10 的 `live_caption/` 改动按 ASR-003 归 App 模块提交**（ASR 侧只提交 `status/asr/`）；③ C-111 的 git 提交与客户包同步归属待 App 模块决定（见 §7.6/§7.7）；④ 「GPU INT8 8.17%」属 reviewer 计分器，产物在 reviewer 本机（按 ASR-002 不补测）

## 最近更新
- 14:05 **§10 三项改动已实施 + 真实实现 A/B 通过**：静音门限相对化（段内 p90−12dB）+ `_has_speech` 相对分支 + 空段拒切（相对覆盖率≥0.40）+ 回环立体声混合（含**反相检测**，修掉一个会把信号相消成 −120dB 的 bug）。真实回环 120s：间隔 **17.28s→6.40s**、>12s **62.5%→6.2%**、硬切 4→0；真实演讲 12 分钟：空段 0→0、规则2 切点 **10/10 安全**；低电平 gain0.3/0.1：>12s 67.4%/100%→**0%**
- 14:05 **§10 否定结论两条（勿再尝试）**：① 空段拒切**不能用绝对口径**（绝对语音占比在 gain=0.3 的正常段只有 0.8%~6%，会把麦克风场景打死；「静音占比」同理）——绝对电平**原理上**无法区分「轻声说话」与「安静」；② 空段拒切要用**相对语音覆盖率**（真空段 0.317/0.379 vs 正常段 ≥0.425，阈值 0.40 可干净分开），用「最长连续语音」不行（真空段也有 360~720ms）
- 13:30 **§9 根因修正（撤回 §8 的一处归因）**：用户输入是 **B 站视频（WASAPI 回环）**，实测回环信号**电平正常**（帧 p50=-21.8dB）**但全程无静音**（最长连续静音 0.00~0.43s）⇒ 规则2/规则1 永不触发 ⇒ **间隔恒 20.48s 硬切**（真实回环数据跑真实 `seg.due()` 实测确认 rule=max）；机制验证：背景声达 -40dBFS 时间隔从 6.4s 突跳到 20.48s；修复方案「静音门限改相对判据 p90−12dB」双向交叉验证通过
- 13:25 在**真实回环数据**（120s，你的视频信号）上验证候选判据：相对 p90−12dB 使间隔 17.28s→**6.40s**、>12s 62.5%→**6.2%**、硬切段 4→0、空段 0；真实演讲上交叉验证**不劣化**（108→110 段，空段 0，>12s 仍 0%）
- 13:05 定位「定稿间隔 >12s」（§8，电平方向）：`_has_speech()` 用**绝对电平 -35dBFS**，麦克风电平偏低时恒 False ⇒ 在 `due()` 最前面**短路** ⇒ 只剩 20s 硬切；A/B 改相对判据后 gain=0.3 时间隔 20.48s→6.40s（**该结论对麦克风场景仍有效，但对你的视频输入不适用 ⇒ 见 §9.2**）
- 11:50 收到 ASR-003【用户决定】：C-111 交 **App 模块**合入与端到端验证，翻译逻辑由 **MT 模块**复核；已在 §7 写**正式移交说明**；**ASR 线程自此不再改 `live_caption/`、不再提交**（§10 是用户直接批准的例外）
- 11:20 收到 ASR-002：① §1 基线改为**两列口径**（目标机 7.798/7.952/0.7722 vs reviewer 8.17/8.27），并撤回上一版两处归因错误；② **C-111 归属 MT + app 模块**，ASR 线程不再推进；③ C-110 结论 reviewer 认可，记录在案不擅自改
- 11:16 C-111 客户包行为验证通过（客户包代码上 `half`/`fix` 语义实测生效）；等锁自动跑 e2e 的排队脚本（**已按 ASR-002 停用**）
- 11:14 C-111 已提交（`ebc6107`）；客户包已同步（备份在包外 `_backup_c111/`）；交付基线 RTF/WER 产物定位到 `reports/c086d_full61_all_npu_matrix.json`
- 11:12 C-111 fix-key 回归（假引擎 + 真实 72 段）ALL PASS：fix 25 次 / 唯一 key 25 个 ⇒ 证实「半句链闭合后 `_half` 未清空」已修复
- 11:10 C-111 归属对照重跑：覆盖率仍 100%（缺失词 0 / 推迟词 0 / 段尾半句归本段 29/29）；状态机 10 用例仍 ALL PASS
- 11:05 建 STATUS_ASR.md（ASR-001 启动单）；C-111 翻译层改动完成，段归属对照：覆盖率 84.1%→100%、推迟词 100→0、段尾半句归本段 3/29→29/29
- 10:56 收到 ASR-001 启动单（模块拆分 + 共享机器锁 + 证据规则）；本模块范围=R2T2 enabling/精度/量化/摆放/流式切段/RTF
- 08:56 C-110 落档：标点切句**不可行**（四策略真实 ASR 对照），推荐改翻译层挂起时机 → 用户批准
- 07:24 C-110 三项发现（合并）：① 句末标点 ≠ 语音结束位置（260 个真句号处尾部静音 p50 仅 0.04s）② 标点跨 chunk 确认率仅 26.2%（根因 `rollback_punctuation=False` → `unfixed_token_num(5)` 恒定回退末 5 token）③ 现状规则1 切点本身就不在静音里（16 个切点里 14 个尾部静音 = 0.00s）

## §1 交付基线（ASR-001 指定；**按 ASR-002 修正为两列口径**）

⚠️ **口径警告（ASR-002）**：8.17% / 7.95% / 0.772 **来自两套不同计分器，不能放在同一列比较**。
以后做判定时，**Δ 只和同一计分器的基线比较**。

### 1.1 目标机计分器（R4 json 用的同一套；全局对齐 + 分段配对 bootstrap）

| 指标 | 数值 | 产物 / 出处 |
|---|---|---|
| GPU INT8 参照 WER | **7.798%** | `reports/c086d_full61_all_npu_matrix.json` → `results_full61min.wer_A_pct=7.798`；同族 `reports/c089_int4/R4_npu_full_wer.json` 的 `ref_wer_pct=7.798` |
| 全 NPU INT8 cleanie WER | **7.952%** | 同上 → `results_full61min.wer_pct=7.952`、`verdict.wer_pct=7.952`、`slice_consistency_check.full61min.all_npu=7.952` |
| 全 NPU vs GPU Δ | **+0.154 pp**，`ci95=[-0.288, +0.584]`，`significant_vs_A=false` | 同上 → `results_full61min.delta_pp_vs_A=0.154` / `ci95` / `significant_vs_A` |
| 全 NPU 61 分钟 RTF | **0.7722**（`seg_rtf_p50=0.7718` / `p95=0.7942` / `max=0.8152`） | 同上 → `results_full61min.rtf=0.7722`、`seg_rtf_p50/p95/max`；`wall_s=2834.59`（47.24 min）/ `audio_sec=3671.0`（61.19 min）/ `n_segs=226` / `paired_n_segs=226` / `ref_words=11067` |
| 配方 | `enc@NPU + dec@NPU (cleanie INT8_SYM)` | 同上 → `config.name`（encoder/decoder 均 NPU） |

> 📎 **R4 INT4 配方的处置**（目标机口径，判定用）：
> `reports/c089_int4/R4_npu_full_wer.json` — `wer_pct=9.795`、`ref_wer_pct=7.798`、
> `delta_pp=1.997`、`ci95=[0.95, 3.095]`、`significantly_worse=true`、`ci_contains_zero=false`
> ⇒ **R4 INT4 在 NPU 上显著劣化，不可用**（这条结论口径一致、成立）。

### 1.2 reviewer 计分器（reviewer 本机 compare_wer.py + paired_bootstrap.py，MiniMax baseline）

| 指标 | 数值 | 出处 |
|---|---|---|
| GPU INT8（enc FP16 + dec INT8）WER | **8.17%** | reviewer 本机 `~/asr_baseline/report/data/npu.json` 与 `OV_vs_CUDA_INT4_INT8_report.md`（**产物在 reviewer 本机，不在本仓库**） |
| 全 NPU WER | **8.27%** | 同上 |
| 全 NPU vs GPU Δ | **+0.10 pp**，`[-0.41, +0.56]` | 同上 |
| 全 NPU 61 分钟 RTF | P50 **0.7722** / P95 0.7942 / max 0.8152 | 同一次全长运行，226 段（与 1.1 的目标机 RTF 数值一致） |

> ✅ **本仓库 `reports/` 下没有 reviewer 口径的 WER 产物**（`8.17` / `8.27` 搜不到），
> 按 ASR-002「找不到就如实写『产物缺失』，**不需要为此补测**」—— 此处如实标注为
> **产物在 reviewer 本机**，不是本仓库的缺失。
>
> 🔴 **修正记录（ASR-002 指出）**：本节上一版把「8.17%」的产物写成
> `reports/c089_int4/R4_npu_full_wer.json`、并把「全 NPU 7.95%」写成该 json 的
> `ref_wer_pct` —— **两处都错**：
> ① R4 json 里只有 **7.798** 这个**目标机口径的 GPU 参照**，没有 8.17；
> ② `ref_wer_pct=7.798` 是 **GPU** 参照，**不是 NPU**（NPU 是 `wer_pct=7.952`）。

## §2 最近一周的结论摘要（均引用产物）

### 2.1 切段策略（属本模块范围）
| 编号 | 结论 | 产物 |
|---|---|---|
| C-108 | 按 Qwen3-ASR-Flash-Realtime 方案改造定稿规则：规则1（段长≥MIN_SEG 且近 3s 内有 ≥300ms 静音）+ 规则2（静音超时 0.8s 优先）+ 空段守卫（须有 ≥200ms 连续语音帧高于 -35dB） | 提交 `c7d7ef1`；`runs/c108_qwen3/`（cut0.8.json / cut1.2.json / 4 个 diag_seg_qwen3_result.json） |
| C-109 | MIN_SEG_SEC 12s → **6s**（用户决策，不做 Manual 模式）：41 段 → **72 段**，段长 p50 6.40s | 提交 `63020bf`；`runs/c109_minseg6/min6.0_cut0.8.json`（min_seg=6.0, cut=0.8, guard_ms=200, wall=329.0s, 72 段） |
| C-110 | **标点触发切点不可行**，不建议实施（详见 §3） | `runs/c110_punct/`（punct_probe_12min.json / punct_value_12min.json / punct_after_hist.npy） |

### 2.2 量化 / 摆放
- R4 配方 NPU 全量：`reports/c089_int4/R4_npu_full_wer.json` — `wer_pct=9.795`，参照 `ref_wer_pct=7.798`，`delta_pp=1.997`，`ci95=[0.95, 3.095]`，`significantly_worse=true`，`ci_contains_zero=false` ⇒ **R4 INT4 在 NPU 上显著劣化，不可用**。
- 61 分钟产物目录：`reports/c058_61min/`（summary_int4lmhead_dec.json + transcript_int4lmhead_dec.txt）。

### 2.3 已知硬边界（对本模块后续所有工作有效）
| 边界 | 数值 | 出处 |
|---|---|---|
| 编码器单段上限 | `MAX_CHUNKS=24` → `MAX_FRAMES=2400` mel 帧（≈23.9s 音频） | `live_caption/segment_encoder_backend.py`；实测 P3 策略在 600s 处触发 `AssertionError: segment too long: 2432 > 2400` |
| 延迟保护期 | 绝对阈值 ∪ 相对阈值（C-105） | 提交 `322654f`；真实录音上白字提前中位 5.76s |
| `enable_hallucination_reset` | **受 C-036 用户决策约束，不得擅自打开** | — |

## §3 C-110 标点切句调研结论（已落档，供 reviewer 审查）

**问题**：能否把「标点切句机制」加入定稿机制 / 把翻译层的实现前移到切段层？

**结论：技术上可行，但实测「标点触发切点」不可行，不建议实施。**
- 判定逻辑前移 ✅ 干净可行；切点位置由标点决定 ❌ 不可行（无词级时间戳 + 标点位置 ≠ 语音结束）；标点作辅助条件 ⚠️ 机制有效但收益被 6s 门槛吃掉。

**三个反直觉发现（均有产物）**：
1. **ASR 的句末标点 ≠ 语音结束位置**。12 分钟真实演讲、1126 chunk 快照（真实 OV gpu_int8 引擎）：真句末标点 260/1126（23.1%），伪句号（缩写/小数点/版本号）**0 个**；标点处尾部静音 p50 = **0.04s**，静音 <0.3s 占 78.8%、<0.8s 占 97.3%；标点后 1 秒内「仍在讲话」时间占比 p50 = **0.54**。→ 标点是「说话人语义停顿」的产物，不是「音频静音」的产物。
2. **标点信号本身不稳定**：严格口径下句末标点跨 chunk 确认率仅 **26.2%**（260 次首现 → 68 次确认，192 次被 prefix 回退抹掉）。根因 `streaming_asr.py` 的 `rollback_punctuation=False` → `k = unfixed_token_num(5)` 恒定回退末 5 token，尾部标点处于「未定」区会被反复改写。
3. **现状切点本身就不在静音里**：2 分钟真实切点分类 —— rule2（静音超时 0.8s）2 个切点尾部静音 0.82/0.81s ✅；rule1（段长≥6s 且近 3s 内**某处**有 300ms 静音）16 个切点里 **14 个尾部静音 = 0.00s** ❌（因为规则1 只要求 lookback 窗口内**某处**有静音，不要求**末尾**有静音）。⇒ **不能拿「切点是否落在静音里」评价新规则**。

**四策略真实 ASR 对照**（12 分钟，各自独立跑真实引擎）：

| 策略 | 段数 | 段长 p50/p95 | 段尾完整句率 | 挂起词数占比 | 切在静音里 | vs 基线词级差 |
|---|---|---|---|---|---|---|
| P0 现状 | 109 | 6.40/8.30s | 56.0% | 45.5% | 22.0% | — |
| P1 标点辅助 | 105 | 6.40/9.60s | 57.1% | 43.6% | 17.1% | 丢失 40 / 多出 26 |
| P2 纯标点 | 164 | 3.90/7.70s | 53.7% | 45.8% | 17.7% | 丢失 107 / 多出 99 |
| P3 标点+静音 | 72 | 7.30/**18.15s** | 31.9% | 64.7% | 6.9% | 丢失 **416** / 多出 54 |

**标点口径（用户 2026-10-23 正式定义）**：只认 `.` `!` `?` `。` `！` `？` 为句末；`;`/`；`/冒号/引号/逗号/顿号**不算**。`translator._SENT_END = '.?!。？！；;…'` 与该口径**唯一不一致的是分号**（分句边界是既有设计，本轮未动）。

## §4 C-111 翻译层「段尾半句当段即翻」（**已实现；按 ASR-002 归属 MT + app 模块，已移交 —— 详见 §6**）

### 4.1 用户决策（本轮）
- 同意**不动切段规则**，改**翻译层**的挂起时机；
- 追加：每次定稿就执行一次翻译，完整句时再翻译一次，并修正之前的翻译错误；
- 粒度：**做法A**（按句翻，段尾半句也立刻翻）；修正范围：**只修段尾半句**。

### 4.2 实现（已落盘，未提交）
| 文件 | 改动 |
|---|---|
| `live_caption/translator.py` | `_carry`（挂起）→ `_half`（当段即翻）；`_Job.kind` 扩展 `final`/`half`/`fix`/`draft`；`submit()` 改为段尾半句当段即翻；半句闭合时**原地覆盖**重翻（用户要的「修正」）；`flush()` 只标记不再重翻 |
| `live_caption/live_caption_app.py` | GUI `_pump_tts` 与 CLI `run_cli` 的 outbox 消费：`half` 只显示不朗读，`final`/`fix` 朗读 ⇒ 同一句不念两遍 |

### 4.3 验证结果（全部落盘）
**A) 状态机（假引擎，秒级）** — `live_caption/diag_c111_half.py`，10 个用例 ALL PASS：半句当段即翻 / 整段半句 / 链上每段各留一份 / flush / 跨段整句原地修正 / TTS 不重复朗读 / 段间无越界串词 / 超长句 / 去重。

**B) 段归属对照（真实 C-109 定稿 72 段，12 分钟演讲）** — `live_caption/diag_c111_own.py`，产物 `hy_bench/runs/c111_half/c111_ownership.json`：

| 指标 | 旧机制(C-099① 挂起) | 新机制(C-111) |
|---|---|---|
| **本段原文的词在本段译文里能找到** | 1181 / 1405（**84.1%**） | 1405 / 1405（**100.0%**） |
| 缺失词数 | **224** | **0** |
| 被推迟显示的词 | 100 | **0** |
| 丢失的词 | 0 | 0 |
| 段尾半句归本段 | 3/29 | **29/29** |

### 4.4 过程中修正的三个实现缺陷（均由对照实验暴露）
1. **补全句归错段**：初版把整句归「当前段」，导致上一段的半句译文「消失」（缺失词 224→307，更差）⇒ 改为**原地覆盖**半句槽位、归属不变。
2. **半句链上的中间段为空**：段7/段8 连续两段都是半句、直到段9才闭合 ⇒ 初版把整条链的译文都归闭合段，段7/段8 的 `seg_keys` **全空**（比旧机制更糟）⇒ 改为**链上每段各留一份**（各自那部分原文作槽位）。
3. **本段首半句被粘连**：首半句没有句末标点，会和后续内容粘成一句、归属到更后面的段 ⇒ 改为首半句**单独切分、单独翻、单独归本段**（kind='half'，不朗读，因整句已由 'fix' 朗读）。

### 4.5 未完成 / 待办
- **端到端真实翻译模型验证未完成**：`diag_c111_e2e.py` 在翻译模型加载阶段退出（日志仅到「等待翻译模型加载…」，`hy_bench/runs/c111_half/e2e.log` 70 B），推测与 app 模块并行占用 GPU 有关。需**持共享机器锁**重跑，测：翻译次数增量、RTF、队列积压、段尾半句译文延迟（T3）。
- **未做 git 提交**，未同步客户包 `Confucius4_LiveCaption_v1.3`（按 APP-002，仓库与客户包是双副本，须写定点替换 sync 脚本）。
- **模块边界待裁决**：C-111 改的是 `translator.py`（翻译层）⇒ 按 ASR-001 的划分属 **MT 模块**；但它服务于 ASR 的切段输出（段-译对应）。请 reviewer 明确：留在 ASR 模块，还是移交 MT 模块？

---

## §5 C-111 收尾：bug 修复、三套验证重跑、客户包同步（2026-10-23 11:35）

### 5.1 端到端暴露的第 4 个实现缺陷（已修复并回归）
**症状**：真实翻译模型 e2e（首轮，持锁）产出 `fix` 事件 59 次，但 key 大量重复 ——
`And then the last` 9 次、`We see the benefit of that today...` 8 次、
`Like as an example, Silicon by itself` 7 次、`Who` 6 次、`So, welcome` 3 次；
追踪 job 序列看到同一个槽位被连续改写成三句不同的话：

```
fix  | So, welcome | So, welcome Welcome to our Q3 26 [REDACTED].
half | Welcome to our Q3 26 [REDACTED].
fix  | So, welcome | So, welcome Agenda topics today.   ← 已闭合的链首被再次修正
half | Agenda topics today.
```

**根因**：**半句链闭合后 `self._half` 未被清空**。本段没有产生新半句时，`self._half`
仍保留上一个已闭合的链首 ⇒ 下一段把它当成**新链头**再走一遍闭合流程 ⇒ 同一槽位被反复 fix。

**修复**（`translator.py`「本段文本分句」分支）：链已闭合而本段无新半句 ⇒ `self._half = None`。
同时简化链延长分支的 `self._half` 赋值（去掉冗余的 `chain_head_key`/`chain_head_seg`，
回到 `{'text': merged, 'key': prev_half['key'], 'seg': prev_half['seg']}`）。

### 5.2 三套验证重跑结果（全部通过）
| 验证 | 脚本 | 产物 | 结果 |
|---|---|---|---|
| 状态机 10 用例 | `live_caption/diag_c111_half.py` | stdout | **ALL PASS**（半句当段即翻 / 链上每段各留一份 / 跨段整句原地修正 / TTS 不重复朗读 / 段间无越界串词 / 超长句 / 去重 等） |
| 段归属对照（真实 C-109 定稿 72 段） | `live_caption/diag_c111_own.py` | `hy_bench/runs/c111_half/c111_ownership.json` | 覆盖率 **1405/1405 = 100%**、缺失词 **0**、推迟词 **0**、段尾半句归本段 **29/29** |
| fix-key 回归（假引擎 + 真实 72 段） | `live_caption/diag_c111_fixkey.py`（**本轮新建**） | `hy_bench/runs/c111_half/c111_fixkey.json` | fix 事件 **25 次 / 唯一 key 25 个**、事件序列全部合法（`[half]`/`[half,fix]`/`[final]`/`[fix]`）、fix 均为整句覆盖 ⇒ **§5.1 的 bug 已修好** |

**判据修正记录（两处，都是我自己的判据写错，不是实现错）**：
1. 「一个 key 只应有一个译文」是**错判据** —— `half` → `fix` 的两段历史正是 C-111 的设计意图
   （半句先占位、补全后整句覆盖）。正确判据是「终态只能有一个，且必须在序列末尾」。
2. 「fix 必须是整句」判据里我**只给 half 剥了 `ZH:` 假引擎前缀**、忘了给 fix 也剥 ⇒ 误报 25 个
   「未覆盖原半句」。修正后全部通过。

### 5.3 真实翻译模型端到端（首轮，**timing_valid=false**）
首轮 e2e 虽已跑出结果，但**当时 ASR-001 的机器锁规则尚未生效**、且与 app 模块并行占用 GPU
⇒ 按 ASR-001「数值和质量作业不需要锁，但被干扰时要把计时标记为 `timing_valid=false`」处理。
产物 `hy_bench/runs/c111_half/c111_e2e.json`：

| 指标 | 旧机制（C-099① 挂起） | 新机制（C-111） | 变化 |
|---|---|---|---|
| 翻译次数 | 126 | 196 | **+55.6%** |
| 事件构成 | `{'final':126}` | `{'half':94, 'final':43, 'fix':59}` | — |
| 总墙钟 | 44.5s | 105.3s | +136.6% |
| 段提交→译完 中位 | 0.597s | 1.537s | — |
| 段提交→译完 P95 | 1.147s | 2.355s | — |
| 段提交→译完 最大 | 1.404s | 2.658s | — |
| TTS 朗读次数 | 126 | 102 | 半句不朗读 |

**实时性判定（不积压）**：105.3s 墙钟对应 720s 音频 = **7.64x 实时**；段间隔约 10s、
每段翻译 1.31s ⇒ 翻译线程远快于段产出速度，**不会积压**。
⚠️ 该轮的 `fix` 计数含 §5.1 的 bug（重复修正）⇒ 修复后需重跑，**当前数值为修复前**。

### 5.4 e2e 脚本的加固（本轮）
`live_caption/diag_c111_e2e.py`：
- **自持机器锁**：`acquire_lock()` / `release_lock()`，锁已存在且持有者 PID 存活 ⇒ **直接退出
  （不抢、不排队、不干扰别的模块）**；PID 已不在或锁早于开机时间 ⇒ 回收后继续。
  已实测：TTS 模块持锁（PID 36608 存活）时本脚本正确拒绝运行。
- 新增 **fix key 唯一性**与**事件序列合法性**两项检查，写入 `c111_e2e.json`。
- 修正 `_pid_alive()` 的实现错误（`wintypes` 未导入 ⇒ 任何锁都会被误判为孤儿锁）。

### 5.5 客户包同步（已完成）
`live_caption/sync_c111_to_pkg.py`（**本轮新建**）—— 目标是 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`：
- `translator.py`：**整文件复制**。前置安全闸 —— 客户包旧版必须与**仓库 HEAD** 字节一致
  （实测 SHA256 `eb0417dc…` 相同）才允许覆盖，否则拒绝执行；覆盖前备份到**包外**
  `Confucius4_LiveCaption_v1.3/_backup_c111/`（**不留 `.bak` 在包内**，避免污染交付物）。
- `live_caption_app.py`：**5 处定点替换**（`clear()` 清 `seg_half`、GUI 文案、CLI 两处 outbox
  消费、CLI 落盘文案），每处 `assert` 命中恰好 1 次。
- **幂等**：重跑输出「已完成：共 0 处改动」（已在临时副本 `/tmp/pkgtest` 上验证两遍）。
- 落地后校验：客户包 `translator.py` 与仓库**字节一致**、`_carry` 已全部改为 `_half`
  （仅剩合法字段名 `seg_carry`）、C-111 标记 8 处（translator）+ 2 处（app）、两文件语法检查通过。
- **客户包代码上的行为验证**（假引擎，直接 `import` 客户包的 `translator.py`）：
  ```
  half  ZH:So welcome                ← 段尾半句当段即翻、只显示
  final ZH:Good morning everyone.
  final ZH:Let us start.
  fix   ZH:So welcome to our Q3 meeting.   ← 补全后整句原地覆盖
  half  ZH:to our Q3 meeting.
  final ZH:Then we cover AI.
  ```
  ⇒ 客户包代码里 `half` / `fix` 语义确实生效。

### 5.6 本轮新产物清单
| 产物 | 文件数 | 说明 |
|---|---|---|
| `hy_bench/runs/c111_half/c111_ownership.json` | 1 | 段归属对照（覆盖率 100%） |
| `hy_bench/runs/c111_half/c111_fixkey.json` | 1 | fix-key 回归（**本轮新建**） |
| `hy_bench/runs/c111_half/c111_e2e.json` | 1 | 真实翻译模型 e2e（**timing_valid=false**，修复前） |
| `live_caption/diag_c111_fixkey.py` | 1 | fix-key 回归脚本（**本轮新建**） |
| `live_caption/sync_c111_to_pkg.py` | 1 | 客户包同步脚本（**本轮新建**） |
| `live_caption/wait_and_run_e2e.py` | 1 | 等锁 + 自动跑 e2e 的排队脚本（**本轮新建**） |
| `status/asr/STATUS_ASR.md` | 1 | 本文件 |

### 5.7 下一步计划
1. **持共享机器锁重跑 e2e**（`python live_caption/diag_c111_e2e.py`）—— 确认修复后
   翻译次数、事件构成、`fix` key 不再重复；这次 `timing_valid=true`。
   （脚本已自带锁逻辑：锁被别的模块持有时**直接退出不抢**；孤儿锁可回收。）
   **已启动排队任务** `live_caption/wait_and_run_e2e.py`（本轮新建）：每 30s 查一次锁，
   锁释放（或变孤儿锁）就自动跑 e2e 并把日志写到 `hy_bench/runs/c111_half/e2e.log`。
   ⇒ **TTS 模块持锁期间不抢锁、不干扰**（ASR-001 规则）。
2. ~~**git 提交**（只提本线程的改动，见 §5.8 的 hunk 边界）~~ → **已完成**，见 §5.9。
3. **等 reviewer 裁决**模块边界（C-111 属 ASR 还是 MT）与「GPU INT8 8.17%」的产物路径。

### 5.9 提交（已完成，2026-10-23 12:00）
提交 `ebc6107`「C-111：翻译层『段尾半句当段即翻 + 补全后修正』」，**8 文件 +1686 / -56**：

| 文件 | 状态 | 说明 |
|---|---|---|
| `live_caption/translator.py` | M | 全部 224 增 / 48 删，逐行核对过**全部属 C-111**（删除行全是旧挂起机制 `_carry`） |
| `live_caption/live_caption_app.py` | M | **仅 C-111 的 5 处**（`clear()` 的 `seg_half.clear()`、GUI 文案、CLI 两处 outbox 消费、CLI 落盘文案）⇒ **不含任何 TTS 代码** |
| `live_caption/diag_c111_half.py` | A | 状态机 10 用例 |
| `live_caption/diag_c111_own.py` | A | 段归属对照 |
| `live_caption/diag_c111_e2e.py` | A | 真实翻译模型 e2e（含机器锁自持 + fix-key 检查） |
| `live_caption/diag_c111_fixkey.py` | A | fix-key 回归（本轮新建） |
| `live_caption/sync_c111_to_pkg.py` | A | 客户包同步（本轮新建） |
| `status/asr/STATUS_ASR.md` | A | 本模块状态文件 |

**做法**：工作区含 app/TTS 线程的未完成改动（`npu_delivery_backend.py` /
`npu_embeds_backend.py` / `pack_v13.py` / `update_manifest_v13.py` / `tts_service.py` /
`tts_worker.py` / `status/CORRECTIONS.md` + `live_caption_app.py` 的 TTS 面板 hunk），
**不能整文件提交** ⇒ 对 `live_caption_app.py` 用「HEAD 版 + C-111 的 5 处定点替换」
构造**独立可运行**的版本再 stage（`git hash-object -w` + `git update-index --cacheinfo`）。
- 关键前提：**HEAD 版 `live_caption_app.py` 里没有 `tts` 变量** ⇒ C-111 的 app 改动
  若带上 `tts.submit` 引用会造成 NameError，故必须剥离。
- 已验证 staged 版本 `py_compile` 通过（app + translator）。
- **未提交**、留给 app/TTS 线程的文件一律保持工作区原样，未做任何改动。

### 5.8 待提交内容与 hunk 边界（工作区含他人未完成改动，不能整文件提交）
| 文件 | 提交范围 |
|---|---|
| `live_caption/translator.py` | **全部**（224 增 / 48 删，逐行核对过：全部属 C-111） |
| `live_caption/live_caption_app.py` | **仅 outbox 消费相关 hunk**（`_save_text` 文案、`clear()` 的 `seg_half.clear()`、CLI 两处消费）；**排除** TTS 面板、`_cache()` 改动等属于 app/TTS 线程的 hunk |
| `status/asr/STATUS_ASR.md` | 全部（本模块） |
| `live_caption/diag_c111_{half,own,e2e,fixkey}.py` | 全部（验证脚本） |
| `live_caption/sync_c111_to_pkg.py` | 全部（客户包同步） |
| **不提交** | `npu_delivery_backend.py` / `npu_embeds_backend.py` / `pack_v13.py` / `update_manifest_v13.py` / `tts_service.py` / `tts_worker.py` / `status/CORRECTIONS.md`（均属 app / TTS 线程） |

---

## §6 ASR-002 回执：§1 口径修正 + C-111 移交 MT/app（2026-10-23 11:20）

> `last_ack: ASR-002`。本节只追加，不回头改旧章节；上一版的错误归因在 §1 的「修正记录」里点明。

### 6.1 §1 基线：改为两列口径（ASR-002 第 1 条，已执行）
- §1 已重写为 **1.1 目标机计分器** / **1.2 reviewer 计分器** 两张表。
- **目标机口径**（产物在本仓库 `reports/c086d_full61_all_npu_matrix.json`）：
  GPU INT8 参照 **7.798%**（`results_full61min.wer_A_pct`）、全 NPU INT8 cleanie **7.952%**
  （`results_full61min.wer_pct`）、Δ **+0.154 pp**（`delta_pp_vs_A`，`ci95=[-0.288,+0.584]`，
  `significant_vs_A=false`）、RTF **0.7722**（`rtf`；`seg_rtf_p50=0.7718` / `p95=0.7942` /
  `max=0.8152`；`wall_s=2834.59` / `audio_sec=3671.0` / `n_segs=226` / `paired_n_segs=226` /
  `ref_words=11067`）、配方 `config.name = enc@NPU + dec@NPU (cleanie INT8_SYM)`。
- **reviewer 口径**（产物在 reviewer 本机）：GPU INT8 **8.17%**、全 NPU **8.27%**、
  Δ **+0.10 pp** `[-0.41,+0.56]`，出自 `~/asr_baseline/report/data/npu.json` 与
  `OV_vs_CUDA_INT4_INT8_report.md`；RTF P50 0.7722 / P95 0.7942 / max 0.8152（226 段，
  与目标机数值一致）。
- **撤回上一版的两处归因错误**（ASR-002 指出，均为我方错误）：
  ① 上一版把「GPU INT8 8.17%」的产物写成 `reports/c089_int4/R4_npu_full_wer.json`
     —— **错**，该 json 里只有目标机口径的 GPU 参照 **7.798**，没有 8.17；
  ② 上一版把「全 NPU 7.95%」写成该 json 的 `ref_wer_pct` —— **错**，
     `ref_wer_pct=7.798` 是 **GPU** 参照，NPU 是 `wer_pct=7.952`。
- ✅ 遵守「**不需要为此补测**」：本仓库 `reports/` 下确实没有 reviewer 口径的 WER 产物
  （8.17 / 8.27 都搜不到），§1 如实标注其**产物在 reviewer 本机**，不写成"本仓库缺失"。
- 📌 **判定规则（已写入 §1 表头警示）**：以后做判定时，**Δ 只和同一计分器的基线比较**。

### 6.2 C-111 移交（ASR-002 第 2 条）—— 移交说明
**归属**：翻译层（`translator.py`）⇒ **MT 模块**；App 的 outbox 消费
（`live_caption_app.py`）⇒ **app 模块**；**均不属于 ASR**。
reviewer 已上报主会话协调移交；**ASR 线程自此不再推进 C-111**（§4/§5 保留原样作档案）。

**改动文件清单**
| 文件 | 归属 | 改动 |
|---|---|---|
| `live_caption/translator.py` | MT | `_carry`（挂起）→ `_half`（当段即翻）；`_Job.kind` 扩展 `final`/`half`/`fix`/`draft`；`submit()` 重写；半句闭合**原地覆盖**重翻；`flush()` 只标记不再重翻；`seg_half` 字典 |
| `live_caption/live_caption_app.py` | app | outbox 消费（`half` 只显示不朗读、`final`/`fix` 朗读 ⇒ 同一句不念两遍）；`clear()` 清 `seg_half`；文案「（半句，接续下一段）」→「（译文生成中…）」 |
| `live_caption/diag_c111_half.py` | MT | 状态机 10 用例（假引擎，秒级） |
| `live_caption/diag_c111_own.py` | MT | 段归属对照（真实 72 段） |
| `live_caption/diag_c111_fixkey.py` | MT | fix-key 回归（本轮新建） |
| `live_caption/diag_c111_e2e.py` | MT | 真实翻译模型 e2e（**已加机器锁自持**） |
| `live_caption/sync_c111_to_pkg.py` | app | 客户包同步（translator 整文件复制带 SHA256 安全闸 + app 5 处定点替换，幂等） |
| `live_caption/wait_and_run_e2e.py` | MT | 等锁自动跑 e2e 的排队脚本（**已按 ASR-002 停用并终止**） |

**两个诊断脚本怎么跑**（接手方直接可用，均**不需要 GPU、不需要模型、不需要机器锁**）
```bat
cd C:/Users/Trekker-PTL/confucius4-openvino
.venv\Scripts\python.exe live_caption\diag_c111_half.py     :: 状态机 10 用例，秒级，末尾输出 ALL PASS
.venv\Scripts\python.exe live_caption\diag_c111_own.py      :: 段归属对照，读 hy_bench\runs\c109_minseg6\min6.0_cut0.8.json
.venv\Scripts\python.exe live_caption\diag_c111_fixkey.py  :: fix-key 回归（同上输入）
```
- 共同前置：仓库 `.venv`（Python 3.12.10，含 numpy）；假引擎 = 输出 `ZH:`+原文的 `FakeTr`。
- `diag_c111_e2e.py`（真实翻译模型）**需持共享机器锁**，脚本自带
  `acquire_lock()`/`release_lock()`：锁被别的模块持有 ⇒ **直接退出不抢**；
  孤儿锁（PID 已不在 / 早于开机时间）才回收。

**产物位置**
| 产物 | 路径 | 内容 |
|---|---|---|
| 段归属对照 | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_ownership.json` | 覆盖率 100%（1405/1405）、缺失词 0、推迟词 0、段尾半句归本段 29/29 |
| fix-key 回归 | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_fixkey.json` | fix 25 次 / 唯一 key 25 个、事件序列全部合法 |
| 真实模型 e2e | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_e2e.json` | ⚠️ **`timing_valid=false`**（未持锁且与 app 模块并行占 GPU），且含 §5.1 的 bug ⇒ **修复后需重跑**才可作结论 |

**🔴 需要主会话裁决的既成事实**（ASR-002 要求「保持现状，不提交 git、不同步客户包」，
但这两件事**在 ASR-002 到达前已经发生**）：
- 已提交 3 次：`ebc6107`（C-111 主体，8 文件 +1686/−56）、`3ce0919`（§1 产物定位补记）、
  `6f05815`（客户包行为验证 + 排队脚本）。
- 已同步客户包 `C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.3/app`
  （`translator.py` 整文件复制 + `live_caption_app.py` 5 处定点替换；
  备份在**包外** `Confucius4_LiveCaption_v1.3\_backup_c111\`）。
- 请主会话裁决：保留（归入 MT/app 提交历史）／回退（`git revert` + 客户包还原）／其他。
  **ASR 线程不自行处置。**

### 6.3 C-110（ASR-002 第 3 条）
reviewer 认可「标点触发切点不实施、现状切段规则（C-108 + C-109 MIN_SEG=6s）不变」。
`rollback_punctuation=False` ⇒ 尾部 5 token 恒定回退这条发现**记录在案，不擅自改**
（会改定稿行为与 WER；如要改，需先给出 61 分钟 WER 配对 bootstrap 方案并经用户同意）。

### 6.4 ASR 本模块状态（ASR-002 第 4 条）
**待命。** 目前没有在跑的 ASR 作业，交付基线没有变化。
只维护 STATUS，**不自行开新实验**。TaskList #15（C-058⑤ INT4 配方矩阵补测）保持 pending，
不主动启动。

---

## §7 C-111 正式移交说明（2026-10-23 11:50）—— 按 ASR-003【用户决定】交 App 模块

> `last_ack: ASR-003`。用户已确认：**C-111 由 App 模块接手**合入与端到端验证，
> 翻译逻辑由 MT 模块复核。**ASR 线程自此不再改 `live_caption/` 下任何文件、不再提交**
> （那些文件以后只由 App 线程提交）。本节写完后 ASR 回到本模块本职。

### 7.1 改了哪些文件、哪些函数（附 diff 摘要）
基线 `63020bf`（C-109）→ `ebc6107`（C-111）：
```
 live_caption/translator.py         | 272 ++++++++++++++++++++++++-------
 live_caption/live_caption_app.py   |  25 ++--
 2 files changed, 241 insertions(+), 56 deletions(-)
```

**`live_caption/translator.py`（翻译层，MT 模块复核）**
| 位置（当前行号） | 符号 | 改动 |
|---|---|---|
| 699 | `class _Job` | `kind` 语义扩展：`final`（朗读）/ **`half`（段尾半句，只显示不朗读）** / **`fix`（修正版，朗读）** / `draft`；`__slots__` 加 `old_key`/`old_seg` |
| 764–770 | `TranslationService.__init__` | **`self._carry`（挂起）→ `self._half`**（未闭合的半句链，存 `{'text','key','seg'}`）；新增 `self.seg_half = {}`（段序号 → 本段末尾是否半句） |
| 898 | `_enqueue_half()` **新增** | 段尾半句**当段即翻**：入队 `kind='half'`，key 记在**产生它的那一段** |
| 910 | `_enqueue_fix()` **新增** | 半句被补成完整句后**重翻**：入队 `kind='fix'`，译文**原地覆盖**半句原来的槽位（`slot_key`） |
| 923 | `submit()` **重写** | 主流程：半句链未闭合 → 本段各留一份；闭合 → `_enqueue_fix` 整句覆盖**链首**槽位 + 本段首半句单独切分/单独翻/归本段；本段文本分句 → 段尾半句当段即翻；**段尾链闭合而本段无新半句 ⇒ `self._half = None`**（关键修复，见 7.4） |
| 1082 | `flush()` | 不再重翻，只把最后一个半句标记为 `final` 交出 |
| 1107 | `mt_of_seg()` | 按 `seg_keys[seg]` 拼译文（半句译文归本段 ⇒ 不再缺字） |
| 1123 | `carry` property | 返回 `self._half['text']` |
| 1200–1203 | 换模型清理 | `_carry` → `_half = None`；新增 `seg_half.clear()` |
| 1251 | `_run_jobs()` | `kind in ('final','half','fix')` 都写 `svc.done[key]` 并 `outbox.append((kind, key, text))`；`'final'`/`'fix'` 更新 `_last_src` |

**`live_caption/live_caption_app.py`（App 模块）** — 6 个 hunk、**不含任何 TTS 代码**
| 位置 | 改动 |
|---|---|
| `App.clear()` 1446 | 新增 `self.mt.seg_half.clear()` |
| `App._save_text()` 1456–1462 | 文案：旧「（半句，接续下一段）」→「（译文生成中…）」；注释改为 C-111 语义 |
| `run_cli()` 1741–1746 | outbox 消费①：`half` → 打印「[半句译文]」**不朗读**；`final`/`fix` → 打印「[译文]」/「[修正译文]」**朗读** |
| `run_cli()` 1764–1768 | outbox 消费②（收尾）：同上 |
| `run_cli()` 1790 | 落盘文案同 7 |
（🔴 提交时 app 用的是「HEAD 版 + C-111 的 5 处定点替换」构造的**独立可运行**版本 ——
HEAD 版 app 里**没有 `tts` 变量**，带 `tts.submit` 引用会 NameError，故必须剥离 TTS 行。）

### 7.2 设计意图
**问题**（C-110 调研后确定不动切段规则）：ASR 句末标点 ≠ 语音结束位置 ⇒ 段尾经常是半句。
旧机制（C-099① 挂起）把半句挂到下一段一起翻 ⇒ **本段译文缺一截**（用户界面上这段原文"没有译文"）。

**新机制三条**：
1. **段尾半句当段就翻**（`kind='half'`），译文归**产生它的那一段** ⇒ 每段都有自己原文的译文。
2. **补全后重翻并原地覆盖**（`kind='fix'`）—— 这就是用户要的「修正之前的翻译错误」；
   整句译文**原地覆盖链首**的半句槽位 ⇒ 归属不变（跨段句只能归属一段，是固有约束）。
3. **TTS 语义**：`half` **只显示不朗读**（残句语义不完整），`final`/`fix` 朗读
   ⇒ 同一句不会被念两遍（`tts_service.submit()` 的 `seg` 只作记录、不做去重/替换）。

**为什么这样分**：`half`/`fix` 分离让「显示」和「朗读」解耦 —— 段尾半句立刻可见（解决 T3 痛点），
但不进 TTS；等它成为完整句时用 `fix` 覆盖同一个槽位并朗读。

### 7.3 已有测试结果（含口径与产物）
**输入**：`hy_bench/runs/c109_minseg6/min6.0_cut0.8.json`（C-109 定稿，**72 段** / 12 分钟真实演讲）。

**① 段归属对照** — `live_caption/diag_c111_own.py`
产物 `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_ownership.json`（1 文件 / 7090 B / mtime 2026-10-23 11:07）
| 指标 | 旧机制 | 新机制 |
|---|---|---|
| `own_hit`（本段原文的词能在**本段** key 列表里找到） | 1181 | **1405** |
| `own_miss`（缺失词数） | **224** | **0** |
| `delayed`（被推迟显示的词） | 100 | **0** |
| `early`（提前） | 763 | 768 |
| `lost`（丢失） | 0 | 0 |
| `tail_own` / `tail_total`（段尾半句归本段） | 3 / 29 | **29 / 29** |

> 🔴 **口径（务必按此读，不要只看 84.1%→100%）**：
> 判据是**词级覆盖率** —— 「**本段**原文的词，能否在**本段**的 `seg_keys` 里找到」。
> 分母 = 全部 72 段原文的词数 = **1405**（新机制 `own_hit` 达到 1405 ⇒ 覆盖率 100%）。
> ⚠️ **不是**「自然句边界」判据：用自然句边界当判据时，跨段句（只能归属一段）
> 本来就不在任何一段的 key 列表里 ⇒ 会得出「新机制更差」的**错误结论**。
> ⚠️ `early`（提前）**不是缺陷**：跨段的那一句只能归属一段，提前/推迟是固有属性，
> **覆盖率才是缺陷指标**。

**② 状态机** — `live_caption/diag_c111_half.py`（假引擎，秒级，**10 用例 ALL PASS**）
半句当段即翻 / 整段半句 / 链上每段各留一份 / flush / 跨段整句原地修正 /
**TTS 不重复朗读** / 段间无越界串词 / 超长句 / 去重 / 无残留 `_carry`。

**③ fix-key 回归** — `live_caption/diag_c111_fixkey.py`（假引擎 + 真实 72 段）
产物 `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_fixkey.json`（1 文件 / 290 B / mtime 2026-10-23 11:09）
`n_segments=72` / `translate_calls=164` / `kinds={half:58, final:81, fix:25}` /
`fix_key_total=25` / `fix_key_unique=25` / `fix_key_dup={}` / `bad_sequence_keys=[]` /
`fix_not_whole_sentence=[]` / `combo_dup={}` / `pass=true`
⇒ **每个槽位只被修正一次**，且每个 key 的事件序列只可能是 `[half]` / `[half,fix]` / `[final]` / `[fix]`。

**④ 客户包代码上的行为验证**（直接 import `Confucius4_LiveCaption_v1.3/app/translator.py`）
```
half  ZH:So welcome                ← 段尾半句当段即翻、只显示
final ZH:Good morning everyone.
fix   ZH:So welcome to our Q3 meeting.   ← 补全后整句原地覆盖
half  ZH:to our Q3 meeting.
final ZH:Then we cover AI.
```

### 7.4 过程中修正的 4 个实现缺陷（**接手方请注意，都是真实踩过的坑**）
1. **补全句归错段** —— 初版把整句归「当前段」⇒ 上一段的半句译文「消失」
   （缺失词 224→307，比旧机制更糟）⇒ 改为**原地覆盖**半句槽位、归属不变。
2. **半句链中间段为空** —— 段7/段8 连续两段都是半句、到段9才闭合 ⇒ 初版把整链归闭合段，
   段7/段8 的 `seg_keys` **全空**（比旧机制更糟）⇒ 改为**链上每段各留一份**。
3. **本段首半句被粘连** —— 首半句无句末标点会与后续内容粘成一句、归属到更后面的段
   ⇒ 改为首半句**单独切分、单独翻、单独归本段**。
4. 🔴 **半句链闭合后 `self._half` 未清空**（真实翻译模型 e2e 才暴露）⇒ 下一段把**已闭合**的
   旧半句当成新链头再走一遍闭合流程 ⇒ **同一槽位被反复 `fix`**（实测 key 重复 9 次/8 次/7 次/6 次/3 次，
   译文被连续改写成三句不同的话）⇒ 已在「本段文本分句」分支加
   `elif prev_half is not None: self._half = None`，并由 ③ 回归守住。

### 7.5 还没完成的事项（**移交后由 App 模块接手**）
| 事项 | 现状 | 说明 |
|---|---|---|
| **真实翻译模型端到端重跑** | ❌ 未完成 | 首轮结果 `hy_bench/runs/c111_half/c111_e2e.json` 标 **`timing_valid=false`**（未持共享机器锁、且与 app 模块并行占 GPU），**且含 7.4-④ 的 bug** ⇒ 修复后的数值为空，**必须重跑**。脚本 `live_caption/diag_c111_e2e.py` 已自带机器锁自持（锁被别的模块持有 ⇒ 直接退出不抢；孤儿锁才回收）+ fix-key 唯一性检查 |
| 翻译次数增量 | 首轮（修复前）126→196（**+55.6%**） | 修复后预期下降（重复 `fix` 消失），需重测 |
| 实时性是否积压 | 首轮 105.3s 墙钟 / 720s 音频 = **7.64x 实时** | 段间隔约 10s、每段翻译 1.31s ⇒ 不积压；修复后需复核 |
| TTS 朗读次数 | 首轮 126→102（半句不朗读） | 需在 App 侧确认不重复朗读 |
| **ASR 侧是否受益** | 未量化 | 段归属覆盖率 100% 是**翻译层**口径；「定稿后多久看到自己那段的译文」（T3）在真实链路上仍需端到端测 |
| 客户包 | ✅ 已同步（App 模块可复核） | `Confucius4_LiveCaption_v1.3/app`：`translator.py` 整文件复制（SHA256 安全闸）+ `live_caption_app.py` 5 处定点替换；备份在**包外** `Confucius4_LiveCaption_v1.3/_backup_c111/`。**改源目录 ≠ 交付给客户，必须重打包才生效** |

### 7.6 已发生的提交（**App 模块复核时请注意历史**）
| 提交 | 内容 |
|---|---|
| `ebc6107` | C-111 主体：translator.py 全部 + app 5 处 + 4 个诊断脚本 + `sync_c111_to_pkg.py` + `status/asr/STATUS_ASR.md`（8 文件 +1686/−56） |
| `3ce0919` | §1 交付基线产物定位补记（ASR 模块自己的状态文件） |
| `6f05815` | 客户包行为验证 + `wait_and_run_e2e.py`（该排队脚本已按 ASR-002 停用并终止） |
| `7fc535c` / `23436f1` / `b6de69a` / `cc8eb96` | ASR-002 回执（只含 `status/asr/` 下的文件） |

🔴 **提醒**：工作区 `live_caption/translator.py` 仍有**未提交**改动
（默认量化 INT4→INT8 切换，引用 H-001/H-007）—— 那是 **MT 模块**的工作，
ASR 线程未碰、未提交。

### 7.7 交接检查清单（给 App 模块）
- [ ] 端到端重跑 `python live_caption/diag_c111_e2e.py`（**先确认共享机器锁**），
      记录 `fix` key 是否唯一、翻译次数、实时性、TTS 朗读次数。
- [ ] 复核翻译逻辑（MT 模块）：`submit()` 的半句链状态机、`_enqueue_fix` 的原地覆盖语义。
- [ ] 决定 C-111 代码的**最终提交归属**（当前在 `ebc6107` 里，由 ASR 线程提交）。
- [ ] 决定 `sync_c111_to_pkg.py` 的归属（客户包归 App 模块）。
- [ ] 客户包**重打包**后才算交付给客户。

### 7.8 定期检查机制（本模块）
用户要求「定期检查 `corrections_ASR.md` 是否有更新，如果有则按要求执行」⇒ 已建立**每小时**一次的
定期检查（自动化任务「ASR 模块纠偏定期检查」）。每次运行的动作：
1. 读 `status/asr/CORRECTIONS_ASR.md`，找编号 **> `last_ack`** 的条目；
2. 无新条目 ⇒ 什么都不改，只回报「无新纠偏」；
3. 有新条目 ⇒ 逐条按其「要做的 / 验收」执行，**不自行扩大范围**；
4. 结果写进本文件（开头 4 行 + `最近更新` ≤15 行 + 只追加 `## §N` 章节），**只提交 `status/asr/` 下的文件**。

**当前状态**：`last_ack: ASR-003`，**无新纠偏**；ASR 侧无用户指派任务 ⇒ **待命**。
（ASR-003 提到的本模块本职：模型、量化、设备摆放、流式与切段策略、RTF ——
切段参数实际定义在 App 模块的 `live_caption_app.py`
（`MIN_SEG_SEC` 默认 6.0 / `MAX_SEG_SEC` 20.0，均可用 `LIVECAP_*` 环境变量覆盖），
ASR 侧只做策略研究与验证，**不直接改 App 文件**。）

---

## §8 实时「定稿间隔 >12s」根因定位（2026-10-23 13:05）—— ASR 侧诊断，代码改动待 App 模块

### 8.1 口径对齐（与用户 2026-10-23 12:55 确认）
「定稿间隔」= **从第 i 次定稿到第 i+1 次定稿的间隔**。
连续切段时它**等于**第 i+1 段的段长（段首尾相接）⇒ 统计段长即可等价。
本节全部数字都按这个口径。

### 8.2 结论（一句话）
**C-109 的 6s 改动确实已实施、且在"正常电平"下有效；实时跑之所以还是 >12s，
是因为 `_has_speech()` 空段守卫用的是**绝对电平阈值**（-35dBFS），
在麦克风输入电平偏低时恒为 False ⇒ 它在 `due()` 最前面**短路**，
规则1/规则2 全被跳过 ⇒ 只能等 `MAX_SEG_SEC=20s` 硬切。**
⇒ 用户看到的 >12s，实际是 **20.48s**（20s 门槛 + 0.64s chunk 粒度）。

### 8.3 证据链

**证据 1：改动已实施（两处都在）**
- 仓库版 `live_caption/live_caption_app.py` 行 98：`MIN_SEG_SEC = float(os.environ.get('LIVECAP_MIN_SEG_SEC', '6.0'))`
- 用户启动路径就是这个文件 ⇒ 走的就是 6.0s。
- 用户进程环境无 `LIVECAP_*` 覆盖（实测 `os.environ` 扫描结果为空）⇒ 不会被改回 12。
- 客户包 `Confucius4_LiveCaption_v1.3/app` 同值，切段逻辑与仓库 diff 一致。

**证据 2：正常电平下改动有效（用真实 `Segmenter.due()`，12 分钟真实演讲）**
```
gain=1.0  段数=108  规则={rule1:102, rule2:6}
  定稿间隔 p50=6.40s p90=7.68s p95=8.32s max=11.52s | >12s: 0/108 (0.0%)
```
⇒ 与 C-109 离线产物（72 段 / p50=6.40 / p95=8.90 / max=11.50 / >12s 0/72）**一致**
⇒ **切段逻辑本身没问题**。

**证据 3：低电平 ⇒ 间隔恒为 20.48s（本节核心）**
输入增益扫描（同一段真实音频整体乘 g，模拟麦克风音量/底噪差异），
**直接调用真实的 `seg.due()`**：
```
gain=1.0  音频p50=-37.5dB p90=-24.4dB  段数=108  间隔 p50=6.40  max=11.52  >12s: 0/108   (0.0%)
gain=0.7  音频p50=-40.6dB p90=-27.5dB  段数=101  间隔 p50=6.40  max=16.64  >12s: 3/101   (3.0%)
gain=0.5  音频p50=-43.5dB p90=-30.5dB  段数= 86  间隔 p50=6.40  max=20.48  >12s: 12/86  (14.0%)
gain=0.3  音频p50=-47.9dB p90=-34.9dB  段数= 46  间隔 p50=20.48 max=20.48  >12s: 31/46  (67.4%)
gain=0.2  音频p50=-51.4dB p90=-38.4dB  段数= 36  间隔 p50=20.48 max=20.48  >12s: 35/36  (97.2%)
gain=0.1  音频p50=-57.5dB p90=-44.4dB  段数= 35  间隔 p50=20.48 max=20.48  >12s: 35/35  (100.0%)
```
>12s 的段的判据明细（gain=0.5 / 0.3）：
```
dur=20.48 has_speech=False silence_tail=False seg_p90=-34.5 frac_sil=0.70 max_run=190ms
dur=20.48 has_speech=False silence_tail=True  seg_p90=-38.7 frac_sil=0.85 max_run=90ms
```
⇒ **`has_speech=False` 是特征**：段内**最长连续 >-35dB 的帧只有 70~190ms < 200ms 门槛**
⇒ `_has_speech` 恒 False ⇒ `due()` 在第 446 行 `return False` ⇒ 规则2/规则1 全跳过
⇒ 只有第 442 行 `dur >= MAX_SEG_SEC(20s)` 能出段 ⇒ **间隔恒 20.48s**。

**证据 4：`_has_speech` 的电平依赖是"断崖式"的**
把真实录音整体衰减，统计"最长连续 >-35dB 的帧数"：
```
gain=1.000  语音帧占比 38.8%  最长连续 0.67s  pass=True
gain=0.500  语音帧占比 19.5%  最长连续 0.34s  pass=True
gain=0.300  语音帧占比  5.1%  最长连续 0.16s  pass=False   ← 断崖
gain=0.200  语音帧占比  0.5%  最长连续 0.07s  pass=False
gain=0.100  语音帧占比  0.0%  最长连续 0.00s  pass=False
```
⇒ 只要**说话时的帧电平跌破 -35dBFS**，守卫立刻从"放行"翻成"拦截"，
**没有任何过渡区** ⇒ 这是一个**开关**，不是渐变。

**证据 5：A/B 验证 —— 换成相对判据后，低电平也正常**
把 `_has_speech` 改成**相对判据**（段内 p90 - 18dB，与 `_silence_tail` 的 C-105 相对判据同思路）：
```
现状   gain=0.5  段数= 86  间隔 p50=6.40 p90=13.44 max=20.48  >12s: 12/86  (14.0%)
相对   gain=0.5  段数=116  间隔 p50=6.40 p90= 6.72 max=10.88  >12s: 0/116  (0.0%)
现状   gain=0.3  段数= 46  间隔 p50=20.48 max=20.48          >12s: 31/46  (67.4%)
相对   gain=0.3  段数=130  间隔 p50=6.40 p90= 6.40 max=7.68   >12s: 0/130  (0.0%)
现状   gain=0.7  段数=101  间隔 p50=6.40 p90= 8.32 max=16.64  >12s: 3/101  (3.0%)
相对   gain=0.7  段数=110  间隔 p50=6.40 p90= 7.10 max=11.52  >12s: 0/110  (0.0%)
```
⇒ **相对判据在所有电平下都把间隔拉回 6.4s 量级**，且正常电平下**不变差**
（gain=1.0：现状 108 段/0 个 >12s ↔ 相对 110 段/0 个 >12s）。

### 8.4 产物清单
| 文件 | 说明 | mtime |
|---|---|---|
| `results/asr_diag/diag_realtime_latency.py` | 第一版（判据有缺陷，见 8.5） | 2026-10-23 12:56 |
| `results/asr_diag/diag_realtime_latency2.py` | 修正版（**直接调用真实 `seg.due()`**） | 2026-10-23 12:59 |
| `results/asr_diag/diag_has_speech_gate.py` | A/B（绝对 vs 相对判据） | 2026-10-23 13:01 |
| `results/asr_diag/realtime_latency.json` | 增益扫描产物（第 1 版） | 2026-10-23 12:58 |
| `results/asr_diag/realtime_latency2.json` | 增益扫描产物（真实 due，含逐段判据明细） | 2026-10-23 12:59 |
| `results/asr_diag/has_speech_gate.json` | A/B 产物 | 2026-10-23 13:01 |
| `results/mic_noise_probe.npy` | 麦克风底噪实测（10s，p50=-96.5dB） | 2026-10-23 12:55 |

### 8.5 自我修正（判据写错的教训）
第 1 版 `diag_realtime_latency.py` **自己复现**了 `due()` 的判定顺序，
漏掉了 `_has_speech` 守卫**在最前面直接 `return False`** 的短路语义
⇒ 低电平下误判成"rule1 触发"，得出"低电平也无影响"的错误结论。
第 2 版改为**直接调用真实的 `seg.due()`**，明细只用于事后解释，才拿到正确结论。
**教训：诊断脚本必须调用真实实现，不要复现判定逻辑。**

### 8.6 建议的修复方向（**待 App 模块实施；ASR 侧不改 `live_caption/`**）
按 ASR-003，ASR 线程**不再改 `live_caption/` 下任何文件**。建议交 App 模块：

1. **首选**：把 `_has_speech()` 的判据从**绝对电平**（-35dBFS）改为**相对电平**
   （段内 p90 - drop），drop 建议 **18dB**（与 `GUARD_REL_DROP_DB` 一致），
   并保留绝对判据作并集（`绝对 ∪ 相对`，与 `_silence_tail` 的 C-105 思路一致，
   保证**只放宽不收紧**）。
2. **或**（更保守）：把空段守卫的绝对阈值从 -35dBFS 降到 -45dBFS，
   并把 `SEG_MIN_SPEECH_RUN_MS` 从 200ms 降到 100ms。
   ⚠️ 但这会**削弱空段守卫的防切空段能力**（C-108 的原始目的）⇒
   必须重跑 C-108 的空段校验（61 分钟素材，hang 0.8/0.6/0.5 三档）。
3. **零代码的即时缓解**：调高系统麦克风输入增益 / 靠近麦克风；
   或用 `LIVECAP_MIN_SPEECH_FRAME_DB` 环境变量（**注意：该常量当前是硬编码
   `SEG_SPEECH_FRAME_DB = -35.0`，没有 env 开关**，需 App 模块先加开关）。

### 8.7 待用户决定
- 是否按 8.6 建议 1（相对判据）改？改动涉及 App 模块的 `live_caption_app.py`。
- 是否需要 ASR 侧补测「空段守卫改动后的空段数」以保证不切空段？
- 是否需要在 GUI 里显示「当前输入电平 dB」与「定稿间隔」两个实时指标，便于用户自查。

---

## §9 【重要修正】用户输入源是**系统回环（B 站在线视频）**⇒ §8 的根因**不适用**，真实根因是「全程无静音」（2026-10-23 13:30）

### 9.1 触发修正的关键信息
用户 2026-10-23 13:17 补充：**测试模式的输入音源是 B 站在线视频**
（`https://www.bilibili.com/video/BV1jS411c79s/...&p=3`）
⇒ 走的是 **`SystemAudioSource`（WASAPI 回环）**，**不是麦克风**。
⇒ §8 定位的「`_has_speech` 绝对电平 -35dBFS 拦截」**对你的场景不成立**（见 9.3）。

### 9.2 撤回 §8 的根因结论
**撤回 §8.2 的一处归因**：`_has_speech` 的绝对电平阈值**不是**你这次 >12s 的原因。
它**是**一个真实存在的隐患（麦克风电平偏低时会踩到，§8.3 证据 3/4/5 依然成立），
但**与你的视频输入无关**。
§8 的**结论 C-109 已实施、正常电平下有效**（§8.3 证据 2）**依然成立**。

### 9.3 真实根因：**视频音频全程没有静音** ⇒ 两条规则都废 ⇒ 只剩 20s 硬切
用 `probe_loopback_live.py` **实测采集你正在播放视频时的回环信号**（120s）：
```
帧dB: p10=-41.9 p50=-21.8 p90=-13.9 max=-9.2      整段 RMS=-18.3dB
低于 -40dB 的帧占比 = 12.2%
逐 2 秒窗口的最长连续静音：0.00 ~ 0.43s（19 个窗口里只有 1 个窗口 >0.3s）
```
⇒ **电平正常**（帧 p50=-21.8dB ≫ -35dBFS）⇒ `_has_speech` 守卫**放行**（实测"守卫OK"）
⇒ **但几乎没有静音**：最长连续静音 0.00~0.43s，**全部 < 0.8s**
⇒ **规则2**（段尾连续静音 ≥0.8s）**永不触发**
⇒ **规则1**（近 3s 内有 ≥300ms 静音）**也永不触发**（最长才 0.43s）
⇒ **只剩 `MAX_SEG_SEC=20s` 硬切** ⇒ **定稿间隔恒 20.48s**

**用你的真实回环数据跑真实 `seg.due()` 的直接确认**：
```
真实回环采集 39.7s  RMS=-18.7dB
段数=1   间隔 20.48s   rule=max(硬切)   该段最长静音=1.56s   守卫=True   规则2=False
```
⇒ **就是 20.48s 硬切**，与用户观感「>12 秒」完全吻合。

**机制验证（合成背景声）**：在真实演讲上叠加恒定电平背景声，
用真实 `seg.due()` 扫描：
```
背景声   无      静音帧占比 0.428  间隔 p50= 6.40  max=11.52  >12s 0/108 (0.0%)
背景声 -45dBFS   静音帧占比 0.383  间隔 p50= 6.40  max=11.52  >12s 0/107 (0.0%)
背景声 -42dBFS   静音帧占比 0.310  间隔 p50= 6.40  max=11.52  >12s 0/105 (0.0%)
背景声 -40dBFS   静音帧占比 0.074  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)  ← 跳变
背景声 -38dBFS   静音帧占比 0.000  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)
背景声 -20dBFS   静音帧占比 0.000  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)
```
⇒ **只要背景声达到 -40dBFS（= `SILENCE_DB`），间隔立刻从 6.4s 跳到 20.48s**。
⇒ 根因一句话：**`SILENCE_DB=-40dBFS` 是绝对阈值，而视频有持续背景声，永远跌不下去。**

### 9.4 候选判据验证（真实回环数据 + 真实演讲数据双向交叉）

**在真实回环数据（120s，你的视频信号）上**：
```
判据                              段数 硬切 空段 | 间隔 p50   p90    max    | >12s
A 绝对 -40dBFS（现状）              8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
B 相对 段内p90-12dB                16   0    0   |  6.40   8.32  13.44  | 1 ( 6.2%)  ← 最佳
B 相对 段内p90-18dB                12   1    0   |  7.04  18.37  20.48  | 3 (25.0%)
B 相对 段内p90-24dB                 8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
E 绝对∪相对(取min) p90-12          8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
D 相对 p90-18dB + 静音门槛300ms    12   1    0   |  7.04  18.37  20.48  | 3 (25.0%)
```
⇒ **相对判据 `段内 p90 − 12dB`** 在真实视频信号上把间隔从 17.28s 降到 **6.40s**，
>12s 从 **62.5% → 6.2%**，**硬切段 4→0**，**空段 0**。

**在真实演讲数据（12 分钟）上交叉验证（确认不劣化原质量）**：
```
现状 绝对-40dBFS      段数=108 硬切=0 空段=0 | p50=6.40 p90=7.68 max=11.52 | >12s 0 (0.0%)
推荐 相对 p90-12dB   段数=110 硬切=0 空段=0 | p50=6.40 p90=7.04 max=10.88 | >12s 0 (0.0%)
```
⇒ **不劣化**（段数 108→110，空段 0，>12s 仍 0%），且最长段从 11.52s 降到 10.88s。

### 9.5 建议的修复方向（**待 App 模块实施**）
在 `Segmenter` 里把**静音判据**从「绝对 -40dBFS」改成「**相对**：段内 p90 − 12dB」，
即：静音门限 = `min(绝对 -40dBFS, 段内语音电平p90 − 12dB)`（取更宽松者，只放宽不收紧），
并让 `_silence_tail()` 与规则1 共用同一门限。
⚠️ 注意：**这条与 §8.6 建议 1 是两处不同的改动**
- §8.6 建议 1 改的是 `_has_speech()`（空段守卫）⇒ 针对**麦克风电平偏低**
- 本节 §9.5 改的是**静音门限 `SILENCE_DB`** ⇒ 针对**背景声导致无静音**
⇒ 两者可独立实施，**对麦克风场景 §9.5 也无害**（真实演讲交叉验证已证明）。

**零代码的即时缓解**（用户可自行试）：
- 在 App 里把 `SILENCE_CUT_SEC` 调小到 **0.2s**（`LIVECAP_SILENCE_CUT_SEC=0.2`）——
  实测你的信号里有 0.43s 的停顿，门槛 0.3~0.4s 就能触发；
- 但**注意**：规则1 仍需「近 3s 内 ≥300ms 静音」，需要配合降低 `SILENCE_DB`
  才能整体生效 ⇒ **单改 `SILENCE_CUT_SEC` 不够**。
- 最可靠的还是 §9.5 的相对门限。

### 9.6 附带发现（供 App 参考，非本次根因）
- **回环立体声只取左声道**：`audio_source.py:335` 采 2 声道，
  行 352 `_to_mono(data)` **只取 `a[:, 0]`** ⇒ 右声道内容被丢弃。
  若视频左右声道内容不同（如背景声走一路、人声走另一路），
  **取 ch0 可能把主要人声丢掉** ⇒ 电平损失可达数 dB。
  ⇒ 建议改成 `(L+R)/2` 或两声道能量取大。
- **回环在无播放时输出数字零**（实测 12s 全零，帧 dB max=-119.2dB），
  与麦克风的 -96dB 底噪不同 ⇒ 两种音源的"静音"表现差异很大，
  **任何绝对电平阈值都只对其中一种成立**。

### 9.7 产物清单（本节）
| 文件 | 说明 | mtime |
|---|---|---|
| `results/asr_diag/probe_loopback_live.py` | 实时回环探测（只读采集 + 能量分析） | 2026-10-23 13:21 |
| `results/asr_diag/diag_bgm_no_silence.py` | 背景声 ⇒ 无静音机制验证（合成） | 2026-10-23 13:20 |
| `results/asr_diag/diag_loopback_vad.py` | 候选判据筛选（真实演讲） | 2026-10-23 13:22 |
| `results/asr_diag/diag_loopback_real.py` | 候选判据验证（**真实回环数据**） | 2026-10-23 13:25 |
| `results/asr_diag/loopback_live_raw.npy` | 真实回环原始采集（120s） | 2026-10-23 13:24 |
| `results/asr_diag/loopback_live_probe.json` | 回环探测汇总（40s） | 2026-10-23 13:21 |
| `results/asr_diag/loopback_live_probe_120.json` | 回环探测汇总（120s） | 2026-10-23 13:24 |
| `results/asr_diag/bgm_no_silence.json` | 背景声扫描产物 | 2026-10-23 13:20 |
| `results/asr_diag/loopback_vad.json` | 候选判据（真实演讲）产物 | 2026-10-23 13:22 |
| `results/asr_diag/loopback_real.json` | 候选判据（真实回环）产物 | 2026-10-23 13:25 |
| `results/loopback_probe.npy` | 无播放时的回环采样（全零对照） | 2026-10-23 13:18 |

### 9.8 待用户决定
- 是否按 §9.5 实施「静音门限改相对判据（段内 p90−12dB）」？**这是解决你这次现象的关键改动**。
- 是否同时实施 §8.6 建议 1（`_has_speech` 改相对判据）—— 面向**麦克风**场景，可选。
- 是否按 §9.6 改回环立体声取单声道为 `(L+R)/2`？
- 是否在 GUI 加「实时输入电平 dB / 段内最长静音 / 定稿间隔」三个实时指标
  —— 有助于用户自己区分"电平问题"与"无静音问题"。



## §10 实施 §9.5 三项改动 + 真实实现 A/B 验证（2026-10-23 14:05）

用户裁决（§9.8）：**1.yes（静音门限相对化）/ 2.yes（`_has_speech` 相对化）/ 3.yes（回环立体声混合）/ 4.no（不加 GUI 指标）**。
本节记录**已实施**的三项改动、验证数据、以及实施过程中被证伪的中间方案。

> ⚠️ **模块边界（ASR-003）**：本节改动了 `live_caption/` 下 2 个文件，
> 但按 ASR-003「ASR 线程不再改 `live_caption/`、不再提交」——
> 本次是**用户直接批准的 §10 实施**（切段策略属 ASR 范围，见 ASR-001
> 「流式和切段策略」），**代码改动已在工作区**，但**git 提交仍归 App 模块**。
> ASR 侧本节只提交 `status/asr/`。

### 10.1 改动清单

| # | 文件 | 位置 | 内容 |
|---|---|---|---|
| 1 | `live_caption/live_caption_app.py` | 常量区（`SILENCE_DB` 之后） | 新增 7 个相对判据常量 |
| 1 | 同上 | `Segmenter._silence_threshold()` | **新增**：本段静音门限 = 段内 p90 − `SIL_REL_DROP_DB`(12dB) |
| 1 | 同上 | `Segmenter.due()` 规则1 | 原**硬编码** `silence_db=-40.0` → 改用 `self._silence_threshold(acc)` |
| 1 | 同上 | `Segmenter._silence_tail()` | `silence_db=SILENCE_DB` → 改用同一门限 |
| 2 | 同上 | `Segmenter._has_speech()` | 新增**相对分支**（帧 > 段内 p90−18dB 且 > −70dBFS 地板，连续 ≥200ms），与原绝对分支**取并集** |
| 2 | 同上 | `Segmenter._speech_ratio_ok()` | **新增**：空段拒切防护（§10.3） |
| 2 | 同上 | `Segmenter.due()` | 规则2 与规则1 均加「空段拒切」 |
| 3 | `live_caption/audio_source.py` | `_stereo_to_mono()` / `_corr()` | **新增**：回环立体声混合（§10.4） |
| 3 | 同上 | `SystemAudioSource._run()` | `resample_to_16k(_to_mono(data), SR)` → `resample_to_16k(_stereo_to_mono(data, self._mix_state), SR)` |

新增常量（全部 env 可控，便于回退）：
```
SIL_REL_ENABLED=1  SIL_REL_DROP_DB=12  SIL_REL_MIN_SPEECH_DB=-60  SIL_REL_MODE=max
SPK_REL_ENABLED=1  SPK_REL_DROP_DB=18  SPK_REL_MIN_SPEECH_DB=-60  SPK_REL_FLOOR_DB=-70
SEG_MIN_REL_COVER=0.40
STEREO_MIX_BALANCE_DB=6  STEREO_MIX_EMA=0.9  STEREO_MIX_ANTIPHASE_CORR=-0.5
```
env 名：`LIVECAP_SIL_REL` / `LIVECAP_SIL_REL_DROP` / `LIVECAP_SIL_REL_MIN_SPEECH` /
`LIVECAP_SIL_REL_MODE` / `LIVECAP_SPK_REL` / `LIVECAP_SPK_REL_DROP` /
`LIVECAP_SPK_REL_MIN_SPEECH` / `LIVECAP_SPK_REL_FLOOR` / `LIVECAP_MIN_REL_COVER` /
`LIVECAP_STEREO_BALANCE_DB` / `LIVECAP_STEREO_EMA` / `LIVECAP_STEREO_ANTIPHASE`

### 10.2 真实实现 A/B 验证（**直接调用改后的真实 `seg.due()`**）

★ 铁律遵守：判定**一律调用真实实现**，不复现判定逻辑（§8.5 教训）。
A/B 手段：改**环境变量**让真实实现自己切换行为（`LIVECAP_SIL_REL=0` + `LIVECAP_SPK_REL=0` = 基线）。

**数据 1：真实回环 120s**（`results/asr_diag/loopback_live_raw.npy`，用户在播 B 站视频时采集）

| | 段数 | 硬切 | 空段 | 间隔 p50 | p90 | max | >12s |
|---|---|---|---|---|---|---|---|
| A 基线（绝对阈值） | 8 | 4 | 0 | 17.28s | 20.48s | 20.48s | **5 (62.5%)** |
| B 相对判据 | 16 | **0** | 0 | **6.40s** | 8.32s | 13.44s | **1 (6.2%)** |

**数据 2：真实演讲 12 分钟**（`test_audio/<redacted>.wav`，回归）

| | 段数 | 硬切 | 空段 | 间隔 p50 | max | >12s | 规则2 危险切点 |
|---|---|---|---|---|---|---|---|
| A 基线 | 108 | 0 | 0 | 6.40s | 11.52s | 0 (0.0%) | 0/6 |
| B 相对判据 | 110 | 0 | **0** | 6.40s | 10.88s | 0 (0.0%) | **0/10** |

**数据 3：低电平扫描**（增益作用于真实演讲 ⇒ 模拟麦克风电平偏低）

| gain | A 基线 >12s | B 相对判据 >12s | A 空段(绝对口径) | B 空段(绝对口径) |
|---|---|---|---|---|
| 1.0 | 0.0% | 0.0% | 0 | 0 |
| 0.5 | 14.0% | **0.0%** | 0 | 5 |
| 0.3 | 67.4% | **0.0%** | 18 | 48 |
| 0.1 | 100.0% | **0.0%** | 35 | 119 |

⚠️ 「空段」列在低电平下用**绝对口径**统计会失真（绝对阈值在低电平下天然失效，
`frac_abs` 恒为 0）。**相对口径**下 A 基线与 B 新判据的增益 1.0 空段都是 **0**
（见 `s10_scan.json` 的 `n_empty` 字段 = 相对口径）。

**参数扫描**（`results/asr_diag/s10_scan.json`，15 组 floor × drop）：
`floor=-70, drop=12`（= 当前默认）**全指标 PASS**，且是唯一同时满足
「回环 >12s ≤ 10%」「gain=1.0 空段=0 且危险切点=0」「gain=0.3 >12s=0」
「gain=0.1 >12s ≤ 40%」的组合。

### 10.3 实施过程中被证伪的两个中间方案（**否定结论，勿再尝试**）

**否定结论 A：空段拒切不能用绝对口径。**
§9.4 的「相对 ∪ 绝对（取 min）」在静音门限上无效（绝对 −40dBFS 恒更严）。
本轮又发现：**空段拒切**若用 C-108 的绝对语音占比（帧 > −35dBFS 占比 < 10%），
在低电平麦克风场景会**误杀正常说话段** ——
实测 gain=0.3 的正常段绝对语音占比只有 **0.8%~6%**（那**是真的说话**），
用它拒切 ⇒ gain=0.3 的 >12s 从 0% 退化到 **23.4%**。
同理「静音占比」（帧 ≤ −40dBFS）也不行：低电平时底噪本身就在 −40dBFS 以下
⇒ 会被误判成全静音。
⇒ **原理**：绝对电平口径**无法区分「轻声说话」与「安静」** —— 把增益调低 10dB
后二者不可分辨。**判据必须相对化。**

**否定结论 B：空段拒切要用「相对语音覆盖率」，不是「连续语音」。**
实测区分度（12 分钟真实演讲，真实 `due()` 产生的段，产物 `s10_discrim.json`）：

| 段 | 相对覆盖率 C1 | 绝对语音占比 | 最长连续(相对) |
|---|---|---|---|
| 真空段（gain=1.0，2 个） | **0.317 / 0.379** | 0.024 / 0.037 | 360 / 720ms |
| 正常段 gain=1.0 | ≥ 0.425 | 0.20~0.47 | 360~2050ms |
| 正常段 gain=0.5 | ≥ 0.425 | 0.04~0.30 | 360~1870ms |
| 正常段 gain=0.3 | ≥ 0.437 | 0.008~0.14 | 250~2050ms |
| 正常段 gain=0.1 | ≥ 0.520 | 0.0 | 370~2050ms |

⇒ **相对覆盖率阈值 0.40** 能干净分开（真空段 ≤0.379 < 0.40 ≤ 正常段）。
用「最长连续语音（相对口径）」不行 —— 真空段的 C2 也有 360~720ms
（噪声突发凑够了连续性），与正常段重叠。

**最终空段拒切判据**（`_speech_ratio_ok()`）：
```
段内 p90 ≤ SPK_REL_MIN_SPEECH_DB(-60dBFS)  → 放行（整段极弱/数字静音）
否则 相对覆盖率 = mean(帧 > max(p90-18dB, -70dBFS)) ≥ 0.40 → 放行
否则 → 拒切（段继续累积）
```

### 10.4 改动 3 的**反相 bug**（实施中实测发现并修复）

初版实现按用户批准的「RMS 接近取 (L+R)/2、明显不同取 RMS 大路」写完后，
函数级测试（`diag_s10_stereo.py`）**T4 反相用例 FAIL**：
两路**反相**（R = −L）时两路 RMS **相等** ⇒ 只看 RMS 会误判成「平衡」
⇒ 取平均 ⇒ **信号完全相消**（实测输出 **−120dB = 数字静音**）。

⇒ 修复：新增 `_corr()`（皮尔逊相关系数），**corr ≤ −0.5 判为反相**
⇒ 强制走「取 RMS 大路」分支。
（工程教训：**RMS 相等 ≠ 内容相同**，只看能量判据会漏掉反相。）

函数级测试最终结果（`results/asr_diag/diag_s10_stereo.py`，6/6 PASS）：

| 用例 | 结果 | 关键数值 |
|---|---|---|
| T1 单声道原样返回 | PASS | len 16000 = 16000 |
| T2 L=R 取平均不损失 | PASS | out −14.02dB = in −14.02dB |
| T3 明显不同时取 RMS 大路 | PASS | out −10.48dB（L −10.48 / R −30.43） |
| T4 反相不被相消 | PASS | out **−10.42dB** vs 平均 **−120.00dB** |
| T5 EMA 平滑不抖动 | PASS | bal +20.1 → +16.1dB，瞬时翻转后仍选强路 |
| T6 全零输入不炸 | PASS | — |

⚠️ **反相分支不能只靠 RMS 判**这条，已写进 `audio_source.py` 的代码注释。

### 10.5 §9 修复方案的**实施差异**（与 §9.5 原提案不同）

§9.5 提案是「静音门限 = 段内 p90 − 12dB，**只取相对**」。
实际实施用了 `SIL_REL_MODE='max'`（= `max(相对, 绝对)`），**不是只取相对**：
* 背景声场景（用户实测）：段内 p90 = −13.9dB ⇒ 相对门限 −25.9dB
  **比绝对 −40dBFS 高** ⇒ `max` 取相对 ⇒ 效果与「只取相对」**完全一致**
  （实测回环 >12s 62.5% → 6.2%，与 §9.4 的「只取相对」数据逐位吻合）。
* 安静场景（麦克风、底噪低）：段内 p90 低 ⇒ 相对门限可能**低于**绝对 −40dBFS
  ⇒ `max` 取绝对 ⇒ **保留旧行为**，不会因为相对化而在极安静时误判静音。

⇒ 即 `max` 模式在背景声场景等价于「只取相对」，在安静场景等价于「只取绝对」，
**两种场景都拿到各自的最优行为**。`SIL_REL_MODE` 保留 `'abs'` / `'rel'` 两个
取值供回退与对照。

### 10.6 待补测（阻塞：需要用户配合）

**左右声道对比数据仍缺**。`results/asr_diag/loopback_stereo_probe.json`
（mtime 2026-10-23 14:05，29.6s）显示回环当前是**数字静音**：
`db_L = db_R = −120.0dB`，`corr_LR = 0.0`，`sil_frac_L = sil_frac_R = 1.0`
⇒ **采集时没有播放声音** ⇒ 量化不了「只取 ch0」到底丢了多少。

复现命令（请在**正在播放视频/音频**时跑）：
```
cd C:/Users/Trekker-PTL/confucius4-openvino
.venv\Scripts\python.exe results\asr_diag\probe_loopback_stereo.py --seconds 30
```
该脚本会输出 `db_L / db_R / db_diff / corr_LR / db_old_ch0 / db_avg / db_new /
sil_frac_L / sil_frac_R / p90_L / p90_R`，可直接量化改动 3 的收益。
**改动 3 本身是安全的**（T1~T6 全 PASS，反相 bug 已修），缺的只是收益量化数据。

### 10.7 产物清单（`results/asr_diag/`，已被 `.gitignore` 第 73 行排除，不入库）

| 文件 | mtime | 内容 |
|---|---|---|
| `diag_s10_verify.py` | 13:39 | A/B 主脚本（真实 `due()`，3 组数据 × 2 方案） |
| `s10_verify.json` | 14:03 | A/B 结果（回环 + 真实演讲 + 增益扫描） |
| `diag_s10_scan.py` | 14:00 | 参数扫描（floor × drop 共 15 组 × 6 指标） |
| `s10_scan.json` | 14:03 | 扫描结果（含基线对照） |
| `diag_s10_cutsafe.py` | 13:41 | 切点安全（**第一版，判据口径有误**，见下方说明） |
| `s10_cutsafe.json` | 13:41 | 同上结果 |
| `diag_s10_cutsafe2.py` | 13:42 | 切点安全（**采用 C-108 官方口径**，有效） |
| `s10_cutsafe2.json` | 13:42 | 规则2 切点安全性 / 空段 / 短段 |
| `diag_s10_empty.py` | 13:40 | 空段疑点追查（绝对 vs 相对口径） |
| `diag_s10_trace.py` | 13:58 | 逐段打印真实实现内部判定状态 |
| `diag_s10_runlen.py` | 13:54 | 候选判据区分度（最长连续语音） |
| `diag_s10_discrim.py` | 13:59 | 候选判据区分度（覆盖率 / 动态范围） |
| `s10_discrim.json` | 13:59 | 区分度数据（相对覆盖率 0.317/0.379 vs ≥0.425） |
| `diag_s10_stereo.py` | 14:04 | 立体声混合函数级测试（T1~T6） |
| `probe_loopback_stereo.py` | 14:04 | 回环双声道采集探针（**待用户配合重跑**） |
| `loopback_stereo_probe.json` | 14:05 | 双声道探测结果（本次全零） |

⚠️ `diag_s10_cutsafe.py`（第一版）的安全判据写错了：把「切点前 0.5s 内
**存在** ≥300ms 静音」当成安全，而 C-108 官方口径是「切点前 0.5s **整窗**
最大帧 dB < −40dB」，且**只统计规则2 切点**。用错口径会得出「基线自身
危险切点 76/108」这种误导性结论（规则1 本来就不保证切在词间隙）。
**有效数据是 `s10_cutsafe2.json`**。

### 10.8 结论

1. **用户实测现象已修复**：真实回环数据上定稿间隔 **17.28s → 6.40s**，
   >12s 占比 **62.5% → 6.2%**，硬切段 **4 → 0**。
2. **回归无退化**：真实演讲 12 分钟，空段 0 → 0，>12s 0% → 0%，
   规则2 切点 6/6 安全 → **10/10 安全**。
3. **麦克风场景额外受益**：低电平（gain 0.3/0.1）>12s 从 67.4%/100%
   降到 **0%**。
4. **两个否定结论**（§10.3）已落档，避免后续重复踩坑。
5. **改动 3 的反相 bug** 已修（§10.4）；左右声道收益量化数据待用户配合（§10.6）。
6. **git 提交归属**：`live_caption/` 的改动按 ASR-003 归 **App 模块**提交；
   ASR 侧只提交本文件。
