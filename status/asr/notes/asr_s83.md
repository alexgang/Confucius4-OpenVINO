# §83 ASR-060 落地明细：Qwen3-ASR-0.6B INT8 NPU「整段离线转写」RTF ＋ 流式对照

> 🔴 **ASR-036 明细归 notes**（STATUS 只留结论与数字）。
> 🟢 **本节只做测速**：**未改交付默认**、**未编译 OpenVINO / GenAI 源码**、**未装 PR 分支**、
> **未打包**、**未动 `live_caption/`**、**未做新的导出或量化**。

---

## 一、ASR-060 要求与本轮交付对照

| ASR-060 要求 | 本轮交付 | 产物 |
|---|---|---|
| ① 模型用交付那套：encoder `ov-encoder-06b-fp16-static` ＋ decoder `ov-dec-06b-stateful-int8sym`（bin SHA256 0059531a…，**开头核对一次**） | ✅ **两臂 SHA256 都核对过并写进 json** | 各臂 json 的 `sha256_check` |
| ② 素材：rc9 同一份 FLEURS dev 中英各 45 句 ＋ 固定 10 分钟片段（SPE 0–600 s）按 ≤30 s 无重叠切块 | ⚠️ **切块上限改为 24.0 s**（见 §五 限制①） | `offline_*_*.json` 的 `blocks[]` |
| ③ 离线口径：特征 → encoder 一次 → decoder 贪心解码到 EOS；分别计时特征/encoder/prefill/每 token/合计；RTF = Σ合计 / Σ音频；报含/不含首编译 RTF、每块中位与 p95、token/s、加载/编译时间 | ✅ 全部落盘 | `summary`（`stage_pct` / `block_rtf_p50` / `block_rtf_p95` / `token_per_s`）＋ `compile_cache.json` |
| ④ 对照：同一会话同素材跑流式路径 ＋ GPU.0 离线，三行一张表 | ✅ **3 行 × 3 素材 = 9 臂** | `runs.json` / `runs_stream_rerun.json` / `runs_spe_rerun.json` |
| ⑤ 准确率：离线/流式各报 WER/CER（同一 normalizer） | ✅ **9 臂全有 WER + CER** | `wer_cer.json` |
| ⑥ 结果写 STATUS 新一节 ＋ json（逐句：id、时长、各段耗时、文本） | ✅ §83 ＋ 9 个 json ＋ 逐句 rows | `status/asr/STATUS_ASR.md` §83 ＋ `results/asr/asr160/` |
| 验收：全程持锁、跑完释放、无残留进程 | ✅ **3 轮持锁**，锁自检 **18 次全 True**、**0 次被抢** | `runs*.json` 的 `lock_probe` |

---

## 二、🔴 核心结论：**差距是测法，不是补丁**

### 2.1 三行 × 三素材 RTF 表（含 WER/CER）

| 素材（时长） | ① **NPU 离线** | ② **NPU 流式** | ③ **GPU.0 离线** | 离线/流式 倍数 |
|---|---|---|---|---|
| FLEURS **EN** 448.34 s | **RTF 0.0496**<br>WER 5.2332% / CER 2.7439% | RTF 0.3094<br>WER 7.6223% / CER 4.2917% | **RTF 0.0383**<br>WER 5.9158% / CER 3.0019% | **6.24×** |
| FLEURS **ZH** 467.40 s | **RTF 0.0448**<br>WER 4.3603% / CER 6.4050% | RTF 0.2912<br>WER 5.5754% / CER 7.7135% | **RTF 0.0323**<br>WER 4.2888% / CER 6.3361% | **6.50×** |
| **SPE 10 min** 600.00 s | **RTF 0.0665**<br>WER 6.3028% / CER 2.5641% | RTF 0.3165<br>WER 9.7355% / CER 4.2005% | **RTF 0.0526**<br>WER 6.4716% / CER 2.6801% | **4.76×** |

**逐句 rows**：`wer_cer.json` → `arms.<臂>.per_sentence[]`（EN/ZH 各 45 句：id、`ref_text`、
`n_ref_words`、`n_errors`、`wer_pct`）⇒ **可重算**（`asr160_score_wer.py` 直接 import
reviewer 的 `compare_wer.norm`，**未改一个字**）。

### 2.2 结论三条

1. 🔴 **现有 IR（未打 PR）在整段离线口径下已经到 RTF 0.045–0.067**
   ⇒ **与 openvino PR #39312（NPUW）+ genai PR #4760 宣称的 RTF≈0.05 同量级**
   ⇒ **「RTF 0.05」那个说法本身是对的，但前提是「整段离线」测法**。
2. 🔴 **我们此前报的 0.547 / 0.544 是流式口径**（每 640 ms 一块、最长 24 s 上下文
   **反复重编码重解码**）⇒ 与 0.05 **不可直接比** ⇒ **差距 6× 里绝大部分是测法**。
   ⇒ 🔴 **不能据此断言「合入 PR 后还能再快 6×」** —— 本轮**没有**测未打 PR 的 IR。
3. 🔴 **离线还更准**（不是更快但更差）：
   EN WER **5.23% vs 7.62%**、ZH **4.36% vs 5.58%**、SPE **6.30% vs 9.74%**
   ⇒ 离线**没有掉字**，反而因为「不反复重解码」少了流式的改写噪声。

### 2.3 🔴 **但流式那个 0.547 也不能直接说「虚高」** —— 口径确实不同，但含义也不同

* rc9 的 **0.547** 是 **MiniMVP 整链 CLI 的墙钟 / 音频时长**（`bench/out/asr_NPU_en.log`
  末行：`音频 448.4s  墙钟 449.0s  RTF(计算) 0.547`）
  ⇒ 它**含整链开销**（CLI 启动、模型加载、MT/TTS 关闭但仍有进程开销）。
* 本轮**流式臂 0.3094** 是 **`bk_run.run_stream` 的纯 ASR 墙钟**（**已排除**加载/编译）。
* ⇒ 两个数**不是同一计分器** ⇒ 🔴 **按 ASR-002 纪律，不可直接相减**
  ⇒ 本轮**只报各自的原始值 ＋ 各自的出处**，**不给「流式快了 1.77×」这种跨口径差值**。

---

## 三、各阶段占比（离线臂）

| 臂 | mel | encoder | embeds | decoder prefill | **每 token 解码** | 块 RTF p50 / p95 |
|---|---|---|---|---|---|---|
| NPU EN | 2.45% | 2.87% | 0.14% | 9.60% | **84.94%** | 0.0480 / 0.0618 |
| NPU ZH | 3.11% | 3.04% | 0.15% | 10.35% | **83.35%** | 0.0454 / 0.0538 |
| NPU SPE | 1.89% | 1.89% | 0.09% | 6.32% | **89.81%** | 0.0668 / 0.0752 |
| GPU EN | 3.94% | 7.63% | 0.17% | 7.16% | **81.09%** | 0.0357 / 0.0521 |
| GPU ZH | 3.49% | 5.00% | 0.19% | 7.64% | **83.68%** | 0.0317 / 0.0416 |
| GPU SPE | 2.36% | 2.79% | 0.11% | 3.78% | **90.96%** | 0.0531 / 0.0612 |

⇒ 🔴 **「encoder 只跑一次」的效果非常明显**：离线臂的 **encoder 占比只有 1.9–7.6%**
⇒ **瓶颈全在「每 token 解码」（81–91%）** ⇒ 🔴 **再优化 encoder 收益 ≤ 8%**；
⇒ 🔴 **要再降 RTF ⇒ 只有两条路**：① **每 token 解码更快**（NPUW / int8 / 更大的 batch）；
② **少解 token**（解码更短、或用非自回归）。

### 3.1 token/s ���每块中位 / p95（离线）

| 臂 | token/s（模型侧） | token/音频秒 |
|---|---|---|
| NPU EN | 47.22 | 2.342 |
| NPU ZH | 46.18 | 2.068 |
| NPU SPE | 51.47 | 3.560 |
| GPU EN | 61.02 | 2.340 |
| GPU ZH | 63.89 | 2.067 |
| GPU SPE | 70.18 | 3.560 |

### 3.2 模型加载 / 编译时间（ASR-060 §3 第 3 条：「有缓存、无缓存各一次」）

| 设备 | 冷编译（无缓存）enc / dec / 合计 | 热编译（有缓存）enc / dec / 合计 | 加速 |
|---|---|---|---|
| **NPU** | 20.19 / 9.52 / **29.71 s** | 20.61 / 9.06 / **29.67 s** | **≈1.00×（无缓存收益）** |
| **GPU.0** | 3.98 / 2.61 / **6.59 s** | 2.31 / 2.24 / **4.55 s** | **1.45×** |

🔴 **NPU 侧 OV/NPUW 的编译缓存目录本机不存在**（`%LOCALAPPDATA%\Intel\OpenVINO\CompiledModelCache`
与 `~\.cache\openvino\compiled_model_cache` **实测都没有**）⇒ **「无缓存」这一档清不掉任何东西**
⇒ **NPU 的 29.71 s 与 29.67 s 是同一个「无缓存」状态跑了两遍** ⇒
**不能声称 NPU 有缓存加速**（≈1.00× 也说明没命中）。
⇒ GPU.0 的 1.45× 是 **OV 的 GPU 编译缓存真实命中**。

---

## 四、🔴 本轮修掉的 **2 个真缺陷**（都是测速脚本自身，但都会让结论失真）

### 缺陷①：流式臂的**中文用了 English 语种 prompt**

* **根因**：`bk_run.BkRunner.__init__` 把 `self.prompt_raw` 固定成
  `assets/prompt.json` 的 **English** 版（`language English<asr_text>`）
  ⇒ 直接拿它跑**中文**素材 ⇒ 模型被迫夹带英文。
* **实测证据**：修正前中文流式臂 = **1231 汉字 + 589 拉丁字母**；
  rc9 的中文臂 = **1405 汉字 + 18 拉丁字母** ⇒ 修正后**逐字对齐 rc9**。
* **影响**：修正前中文流式臂 **WER 16.08%** ⇒ 修正后 **5.58%** ⇒
  🔴 **差 10.5 pp** ⇒ **不修正则中英两行不可比**。
* **修法**：`asr160_stream_arm.py` 按素材语种改写 `runner.prompt_raw`
  （写法照抄 App 侧 `live_caption/asr06b_stateful_backend.py` 的
  `language Chinese<asr_text>` / `language English<asr_text>`）。
* ⚠️ **只改了测速脚本，**没改 `b_kit_stateful/scripts/bk_run.py`**（那是交付套件，
  改了 SHA 就变 ⇒ **ASR-059 冻结的 B 套件不动**）。

### 缺陷②：SPE 10 分钟片段被误判为**中文**

* **根因**：`clip_10min_0_600.wav` 实测是**英文**（`reports/c026_minimax_transcript.txt`
  原文 = "All right, good morning everyone…"）⇒ 第一轮误用 zh prompt。
* **实测证据**：修正前 SPE 流式臂 = **84 汉字 + 7463 拉丁字母**；
  修正后 = **0 汉字 + 7704 拉丁字母**。
* **影响**：修正前 SPE 流式臂中文混排 ⇒ 不可比 ⇒ 重跑。

### ⇒ 因此共 **3 轮持锁**：`runs.json`（9 臂）→ `runs_stream_rerun.json`（3 流式臂）→
`runs_spe_rerun.json`（3 SPE 臂）⇒ **中英两素材的离线臂未重跑**（语种本来就对）。

---

## 五、🔴 限制与口径说明（**必须与 reviewer 一起看**）

### 限制①：**「≤30 s 无重叠切块」在现有交付 IR 上做不到 ⇒ 实测按 24.0 s 切**

* `ov-encoder-06b-fp16-static` 的 `input_features` 是**静态** `[1,128,2400]`
  ⇒ 最多 **2400 mel 帧**（mel 100 fps）⇒ **24.0 s 音频**
  ⇒ 30 s ⇒ 3001 帧 ⇒ **塞不进 2400 的静态输入**（实测抛
  `ValueError: could not broadcast input array from shape (128,2445) into shape (128,2400)`）。
* ⇒ 本脚本按 **383 840 样本 = 23.99 s** 切块（每块留 1 帧给 `n_valid` 边界）。
* 🔴 **这本身是一条结论**：对照 openvino #39312 / genai #4760 宣称的 **30 s 上下文**，
  **我们现有交付 IR 的上限是 24 s** ⇒ **那套补丁里必然也改了 encoder 的静态形状**。

### 限制②：**FLEURS 逐句边界不在本机** ⇒ 逐句归属用「词数等分」口径

* FLEURS **原始逐句 wav 不在本机**（`bench_data.json` 只有 `id` + 文本，**无 duration**）
  ⇒ 逐句 WER 的归属靠**把 45 句按词数等分到整条音频时间轴**，
  再按**块的时间覆盖**把参照词分配给块（与 reviewer `spread()` 的思路一致）
  ⇒ **可重算**，但**不是**真实的句边界。
* ⇒ 🔴 **逐句 WER 供 reviewer 复核用；总 WER 才是结论**。
* **SPE 臂**：参照 = **reviewer 的 MiniMax baseline**（`reports/c026_minimax_segjson_10min`，
  **1777 词 / 0–600 s**）⇒ **与历史 ASR 结果同一计分器** ⇒ SPE 臂**只有全局 WER/CER**
  （MiniMax baseline 无逐句）。

### 限制③：**SPE 臂的流式/离线切分边界不同** ⇒ 不做边界敏感的比较

* 离线臂 = 26 块（≤24 s）；流式臂 = 93 段（`bk_run` 的段级切分）⇒ 边界完全不同
  ⇒ 🔴 **SPE 只报全局 WER/CER + 词数**（离线 2136 词 vs 流式 1768 词），
  **不报逐句**。

### 限制④：**没有测「打了 PR 的 IR」** ⇒ 不能声称「合入后还能再快」

* ASR-060 明示「**不要编译 OpenVINO / GenAI 源码，不装 PR 分支**」⇒ 本轮**严格遵守**
  ⇒ 本轮所有数字都是**现有交付 IR** 的表现。

---

## 六、产物清单（`results/asr/asr160/`，**35 个文件**）

| 文件 | 内容 |
|---|---|
| `offline_{NPU,GPU0}_{en,zh,spe}.json` (6) | **离线臂逐块明细**：块号、起止秒、时长、mel/enc/embeds/prefill/decode/合计耗时、token 数、prompt token 数、文本；＋ `summary`（RTF / p50 / p95 / 各阶段占比 / token/s）；＋ `sha256_check`；＋ `exec_devices` |
| `stream_NPU_{en,zh,spe}/summary.json` (3) | 流式臂 summary（`bk_run.run_stream` 的原版字段 ＋ `rtf` / `n_segs` / `total_words`） |
| `stream_NPU_{en,zh,spe}/segments.json` + `.jsonl` + `transcript.txt` (9) | 流式臂**逐段**文本与时间戳（**逐句 json 可重算**的原料） |
| `wer_cer.json` | **9 臂**的 WER/CER ＋ 逐句 rows（EN/ZH 各 45 句） |
| `compile_cache.json` | 冷/热编译时间（NPU + GPU.0） |
| `runs.json` / `runs_stream_rerun.json` / `runs_spe_rerun.json` | **3 轮持锁**的作业清单 ＋ **锁自检**（18 次 / 0 被抢） |
| `*.log` (12) | 每个作业的原始 stdout（**可复核**） |

**脚本**（在 `C:\Users\Trekker-PTL\qwen3asr_06b\scripts\`，**不在 git 仓库内**）：
`asr160_offline_bench.py`（离线臂）、`asr160_stream_arm.py`（流式臂）、
`asr160_run_all.py` / `asr160_rerun_stream.py` / `asr160_rerun_spe.py`（持锁编排）、
`asr160_score_wer.py`（WER/CER）、`asr160_compile_cache.py`（编译缓存）。

---

## 七、🔴 给用户/reviewer 的 3 个判断点

1. **要不要把「离线」加成一条交付路径？**
   本轮实测离线 RTF **0.045–0.067** ＋ WER **更好**（EN 5.23% vs 流式 7.62%）
   ⇒ 但**离线没有流式的增量出字**（不能做实时字幕）⇒ 适合「整段转写 / 会议纪要 / 字幕成片」。
   ⇒ **是否加、怎么加，是用户决定**（本轮**未改交付默认**）。
2. **「RTF≈0.05」的说法怎么对外写？**
   建议写成「**整段离线口径**下现有 INT8 IR 在 NPU 上 RTF **0.045–0.067**（与宣称同量级）；
   **流式口径**下是 **0.29–0.32**（不含加载）」⇒ **别把两者混着报**。
3. **encoder 静态上限 24 s** 是不是要改？
   对照那两套 PR 宣称 30 s ⇒ 若要上 30 s 上下文，**得改 encoder 的静态形状**（＝重导出）
   ⇒ **超出本轮范围**（ASR-060 只测速），**等用户指派**。

## 八、reviewer 独立复核（ASR-061，2026-11-19 09:10）

> 🔴 **本节是 reviewer 的复核记录**（ASR-061，**[FYI]** ⇒ **不需要重跑**）。
> reviewer 拉回 `results/asr/asr160/` **全部 35 个文件**（mtime 2026-11-17 17:08:47），
> 在 reviewer 本机**独立重算** ⇒ **结论：接受** ⇒ **ASR-060 关闭，回到待命**。

### 8.1 复核结果（reviewer 独立重算）

| 复核项 | reviewer 结果 | 与本模块 §83 对照 |
|---|---|---|
| RTF（Σ`blocks.total_s` / Σ`duration_s`）NPU 离线 EN / ZH / SPE | 0.0496 / 0.0448 / 0.0665 | ✅ **逐位一致** |
| RTF GPU.0 离线 EN / ZH / SPE | 0.0383 / 0.0323 / 0.0526 | ✅ **逐位一致** |
| RTF **去掉第 1 块**（编译不计入）NPU | 0.0487 / 0.0445 / 0.0666 | ⇒ 首次推理影响 **≤0.002** |
| RTF **去掉第 1 块** GPU.0 | 0.0365 / 0.0318 / 0.0524 | 同上 |
| `total_s` = 各阶段之和 | **最大差 0** | ✅ 一致 |
| 块 RTF p50/p95、阶段占比 | 已核对 | ✅ 一致 |
| 流式 Σdec_wall / Σ音频 | 0.3056 / 0.2860 / 0.3138（加 wall 后 **0.309 / 0.291 / 0.317**） | ✅ 与 §83 的 0.3094 / 0.2912 / 0.3165 一致 |
| WER/CER EN / ZH 三臂（`compare_wer.norm` ＋ `jiwer`，流式取 `segments.jsonl` 文本） | 逐位一致 | ✅ 一致 |
| WER SPE（reviewer 用 `spe_baseline` 中 **<600 s 的 1765 词**） | NPU 离线 **5.55%** / GPU 离线 **5.89%** / 流式 **9.46%** | ⚠️ §83 用 **1777 词**得 6.30 / 6.47 / 9.74 ⇒ **差别来自参照截取**，**排序相同** |
| 删除数（EN） | 离线 **8** vs 流式 **14** | ⇒ 离线**没掉字** |
| 模型身份 | dec bin `0059531a…`、enc `0b7463d6…`（`b_kit_stateful` 与 `models` **两份相同**） | ✅ 一致 |
| encoder 输入 | **静态** `[1,128,2400]` ⇒ 按 **24 s** 切块是对的 | ✅ 与 §83⑦ 一致 |
| 锁与干扰 | 三轮持锁（PID **27088 / 30040 / 18920**），**18 次自检，0 次被抢**；16:15–17:10 期间 A 上其他模块目录**无写入**（`qwen3tts_genai_rc2` 最后写入 15:58）；现无锁、无 python 残留 | ⇒ `timing_valid` **成立** |

### 8.2 reviewer 由 probe 算出的**流式阶段分解**（新增信息，§83 未有）

- **FLEURS EN**：766 次 generate × prefill **96 ms** ≈ **74 s（54%）**；
  1118 token × **19.8 ms** ≈ **22 s（16%）**；
  其余 ≈ **41 s（30%）** 是 701 步里**重复的 mel ＋ encoder**。
- **离线每 token**：NPU **17–18 ms**、GPU **13 ms**。
- ⇒ **流式慢 5–6 倍的主因 = 每 640 ms 一次固定约 95 ms 的 NPU prefill ＋ encoder 重复计算**
  （不是 decoder 本身慢）⇒ 与 §83④「离线口径下每 token 解码占 81–91%」**不矛盾**（口径不同）。

### 8.3 🔴 3 个「只记录、不用重跑」的小问题（reviewer 记录，本轮**不改脚本**）

1. **日志里的 `EXECUTION_DEVICES` 只读了 decoder** ⇒ 以后的脚本要把 **encoder 也打出来**
   （本次 encoder 用的是**显式 "NPU"**，可以接受）。
2. **FLEURS 是用拼接 wav 按 24 s 切块跑的**，不是 45 个单句 ⇒ **单句口径**下 prefill 占比
   会更高、**RTF 会略高**（⇒ §83 的 0.045–0.067 是**拼接 wav 口径**，对外写时要注意）。
3. **`compile_cache` 的冷 / 热没有真正清缓存**（`cache_dirs_cleared=[]`）⇒ §83⑤ 已说明
   （本机 OV/NPUW 编译缓存目录实测不存在），**这一点接受**。

### 8.4 结论（reviewer 原话要点）

- **离线 RTF 和 PR 宣称的 0.05 是同一量级，差距来自测法** ⇒ §83③ **成立**。
- **流式慢 5–6 倍**，主因是每 640 ms 一次固定约 95 ms 的 NPU prefill ＋ encoder 重复计算。
- **ASR-060 关闭，回到待命**。

> ⇒ **本模块本轮无新章节**（ASR-061 为 FYI；照 ASR-058 / ASR-059 的 FYI 先例：只写头部 4 行
> ＋ 一行「最近更新」＋ 未完成纠偏表加一行）⇒ `last_ack` = **ASR-061**。
