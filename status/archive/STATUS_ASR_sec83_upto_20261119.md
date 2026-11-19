## §83 ASR-060 落地：Qwen3-ASR-0.6B INT8「整段离线转写」RTF ＋ 流式对照（2026-11-17 15:52–17:20）

### §83 ASR-060 落地：Qwen3-ASR-0.6B INT8「整段离线转写」RTF ＋ 流式对照（2026-11-17 15:52–17:20）

> 🔴 **明细全文** `status/asr/notes/asr_s83.md`（**已提交**）；本节只留结论与数字（ASR-036 明细归 notes）。
> 🔴 **只做测速**：**未改交付默认**、**未编译 OpenVINO / GenAI 源码**、**未装 PR 分支**、**未打包**、**未动 `live_caption/`**、**未做新的导出或量化**、**未动 B 套件**（ASR-059 冻结）。

- ✅ **① 9 臂全部持锁跑完**（{**NPU 离线**, **NPU 流式**, **GPU.0 离线**} × {FLEURS **EN** 448.34 s, **ZH** 467.40 s, **SPE 10 min** 600.0 s}）：**锁自检 18 次全 True / 0 被抢**，**跑完释放锁**、**无残留进程**；产物 `results/asr/asr160/`（**35 个文件**）。

- ✅ **② RTF 三行表（含 WER/CER，同一 normalizer = reviewer `compare_wer.norm`）**：

| 素材 | ① NPU 离线 | ② NPU 流式 | ③ GPU.0 离线 | 离线/流式 |
|---|---|---|---|---|
| FLEURS EN 448.34 s | **0.0496** / WER **5.2332%** / CER 2.7439% | 0.3094 / WER 7.6223% / CER 4.2917% | **0.0383** / WER 5.9158% / CER 3.0019% | **6.24×** |
| FLEURS ZH 467.40 s | **0.0448** / WER **4.3603%** / CER 6.4050% | 0.2912 / WER 5.5754% / CER 7.7135% | **0.0323** / WER 4.2888% / CER 6.3361% | **6.50×** |
| SPE 10 min 600.0 s | **0.0665** / WER **6.3028%** / CER 2.5641% | 0.3165 / WER 9.7355% / CER 4.2005% | **0.0526** / WER 6.4716% / CER 2.6801% | **4.76×** |

- 🔴 **③ 核心结论：差距是测法，不是补丁** —— 现有 IR（**未打 PR**）在**整段离线**口径下 **RTF 0.045–0.067** ⇒ **与 openvino #39312（NPUW）/ genai #4760 宣称的 RTF≈0.05 同量级**；此前报的 **0.547/0.544 是流式口径**（每 640 ms 一块、最长 24 s 上下文**反复重编码重解码**）⇒ 🔴 **两者不可直接比** ⇒ **不能断言「合入 PR 后还能再快 6×」**（**本轮没测打了 PR 的 IR**）。⇒ 🔴 **离线还更准**（EN 5.23% vs 流式 7.62%）⇒ **离线没掉字**。⇒ ⚠️ rc9 的 0.547 含 MiniMVP 整链启动/加载，本轮流式 0.3094 是 `bk_run.run_stream` 的**纯 ASR 墙钟** ⇒ **跨口径 ⇒ 按 ASR-002 不给差值**。

- ✅ **④ 各阶段占比（离线臂）**：**encoder 只跑一次 ⇒ 仅 1.89–7.63%**；**每 token 解码 81.09–90.96%** ＝ **瓶颈全在解码**（再优化 encoder 收益 ≤ 8%）；mel 1.89–3.94%、embeds 0.09–0.19%、decoder prefill 3.78–10.35%。**块 RTF p50/p95**：NPU EN 0.0480/0.0618、ZH 0.0454/0.0538、SPE 0.0668/0.0752；GPU EN 0.0357/0.0521、ZH 0.0317/0.0416、SPE 0.0531/0.0612。**token/s（模型侧）**：NPU 46.18–51.47、GPU 61.02–70.18。

- ✅ **⑤ 加载/编译（冷/热各一次）**：**NPU 冷 29.71 s（enc 20.19 ＋ dec 9.52）/ 热 29.67 s（enc 20.61 ＋ dec 9.06）⇒ ≈1.00×**（🔴 本机 OV/NPUW 编译缓存目录**实测不存在** ⇒ 不能声称 NPU 有缓存加速）；**GPU.0 冷 6.59 s（enc 3.98 ＋ dec 2.61）/ 热 4.55 s（enc 2.31 ＋ dec 2.24）⇒ 1.45×（真实命中）**。

- 🔴 **⑥ 本轮修掉 2 个真缺陷**（都在测速脚本自身，**各重跑一次**，共 **3 轮持锁**；**未改 `b_kit_stateful/scripts/bk_run.py`**，交付套件 ASR-059 冻结）：**①** 流式臂**中文误用 English 语种 prompt** ⇒ 修正前中文臂 **1231 汉字 ＋ 589 拉丁字母**，修正后 **1405 汉字 ＋ 18 拉丁字母（逐字对齐 rc9）**，中文流式 **WER 16.0829% → 5.5754%（差 10.5 pp）**；**②** SPE 10 分钟片段**误判为中文**（实测 `reports/c026_minimax_transcript.txt` 是英文）⇒ 修正前 **84 汉字 ＋ 7463 拉丁字母** ⇒ 修正后 **0 汉字 ＋ 7704 拉丁字母**。

- 🔴 **⑦ 两处口径限制（必须与 reviewer 一起看）**：**①** 「≤30 s 无重叠切块」在现有交付 IR 上**物理做不到** —— `ov-encoder-06b-fp16-static` 的 `input_features` 是**静态** `[1,128,2400]` ⇒ 上限 **2400 mel 帧 = 24.0 s**（30 s ⇒ 实测抛 `could not broadcast input array from shape (128,2445) into shape (128,2400)`）⇒ 实测按 **383 840 样本 = 23.99 s** 切块 ⇒ 🔴 **要上 30 s ＝ 重导出 encoder**（超本轮范围）；**②** FLEURS **逐句 wav 不在本机**（`bench_data.json` 只有 `id` ＋ 文本、**无 duration**）⇒ 逐句 WER 归属按**词数等分**到音频时间轴再按块覆盖分配（**可重算**，**非真实句边界**）⇒ 🔴 **总 WER 才是结论**；SPE 臂参照 = **reviewer 的 MiniMax baseline**（`reports/c026_minimax_segjson_10min`，**1777 词 / 0–600 s**，同一计分器）⇒ **只有全局 WER/CER**。

- ✅ **⑧ 逐句 json 可重算**：`results/asr/asr160/wer_cer.json` → `arms.<臂>.per_sentence[]`（EN/ZH 各 **45** 句：id、`ref_text`、`n_ref_words`、`n_errors`、`wer_pct`）；离线臂逐块 = `offline_{NPU,GPU0}_{en,zh,spe}.json` 的 `blocks[]`（起止秒、时长、mel/enc/embeds/prefill/decode/合计、token 数、prompt token 数、文本）；流式臂逐段 = `stream_NPU_*/segments.json` ＋ `transcript.txt`；评分器 `asr160_score_wer.py`（**直接 import reviewer 的 `compare_wer.norm`，未改一个字**；WER = `jiwer.process_words`、CER = `jiwer.process_characters`）。

> ⇒ **本轮全部完成 ⇒ 停下等 reviewer 复核。**
