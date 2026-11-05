# ASR 巡检 §74 —— ASR-046 / ASR-047 落地（2026-11-05 09:20–）

> 🔴 **本轮结论**：新纠偏 **ASR-046**（HIGH）+ **ASR-047**（NORMAL，用户决定）⇒
> `last_ack` **ASR-045 → ASR-047**。
> 🔴 **ASR-047 用户决定（2026-11-05 08:20）**：ASR 默认保持 **0.64 s** 步长、
> **VAD 门控默认关闭**；ASR-042 第 3 步（ASR+MT+TTS 同跑的 TTS RTF）**暂停**；
> 环境变量开关**可以保留但默认必须关闭**。
> 明细产物：`qwen3asr_06b/results/pyannote_seg/{asr079,asr119,asr120}_*.json`
> ＋ `qwen3asr_06b/models/pyannote_seg/ov-fp16-w5/pyannote_seg_3_0_w5.xml`。

---

## 1. 新纠偏判定（ASR-039 第 1 步）

| 项 | 值 |
|---|---|
| 纠偏文件 | `status/asr/CORRECTIONS_ASR.md`（32484 B @ Nov 5 08:22，md5 `dd0a9e139baa41797a754e39f21060c1`） |
| 全文最大编号 | **ASR-047** |
| 写入前 `last_ack` | **ASR-045** |
| 新条目 | **ASR-046**（第 222 行起，7 项「要做的」）＋ **ASR-047**（第 242 行起，用户决定） |

---

## 2. ASR-046 ① 5 s IR 的 `rt_info` 绝对路径清理（**BLOCKING，已完成**）

### 2.1 做了什么

`qwen3asr_06b/models/pyannote_seg/ov-fp16-w5/pyannote_seg_3_0_w5.xml` 第 2597 行
`rt_info/conversion_parameters/output_model` 的值原本是**本机绝对路径**
⇒ 改为**相对路径**，与包内 10 s IR 那一行同款写法：

```xml
<output_model value="models/pyannote_seg/ov-fp16-w5\pyannote_seg_3_0_w5.xml" />
```

🔴 **只改那一行** ⇒ 权重未动、行数未变、CRLF 行尾保持、
`openvino.read_model` 读回输入形状仍是 `[1,1,80000]`。
执行脚本：`qwen3asr_06b/scripts/asr117_clean_seg_ir_paths.py`（8 项落盘前自检 ＋
落盘后复核 `xml_parses` / `input_shape_still_80000`）。

### 2.2 新 md5（**App 同步时用这个**）

| 文件 | 清理前 md5 | **清理后 md5** | 大小 |
|---|---|---|---|
| `pyannote_seg_3_0_w5.xml` | `5295ec9c7fdf14d75b5d955884ac9e8e` | 🔴 **`14b224bced3289237799bc9a7eb746ff`** | 73206 B → **73172 B** |
| `pyannote_seg_3_0_w5.bin` | `32d5bc9ac2e32f9b8bb62bdfa4285328` | **`32d5bc9ac2e32f9b8bb62bdfa4285328`**（未变） | 2978960 B（未变） |

### 2.3 🔴 xml 的 mtime「11-04 22:17」是谁改的（ASR-046 ① 明写要求说明）

**结论：是 App 侧脚本 `results/app/app237_app067_d1_window_pkg_gate.py` 改的，
不是 ASR 侧，权重也没被改。**

* **机制**：`app237` 的 **CP-H4 反证**会把 **ASR 源 xml** 临时改成
  「第三维 = 160000」的假形状，跑完判据后再**写回原文**
  （`app237_app067_d1_window_pkg_gate.py` 第 430–446 行，
  `with open(x, 'w', ...)` **两次**）。
* **为什么「内容没变但 mtime 变了」**：还原时是**按字符串写回**的
  ⇒ 内容逐字相同（md5 仍是 `5295ec9c…`）但 **mtime 被刷新**。
* **时间线吻合**：`app237` 的重跑产物
  `results/app/app249_rerun_app237_app067_d1_window_pkg_evidence.json`
  mtime = **11-04 22:17** ⇒ 与源 xml 的 mtime **22:17:31** 同一分钟。
* **旁证**：影子包里的那份副本（`shared/app067_shadow/models/spk/pyannote_seg_3_0/fp16-w5/`）
  md5 同为 `5295ec9c…`、mtime **11-04 17:07**
  ⇒ **绝对路径在 17:07 就已存在**
  ⇒ 22:17 那次**不是「引入绝对路径」的那次**，只是**反证还原时刷新了时间戳**。
* 🔴 **根因**：绝对路径是 **11-02 09:33 导出 IR 时**（`export_meta.json` 的
  `generated_at` 与 bin/xml 的原始 mtime 都是 11-02 09:33）就写进去的
  ⇒ 是**导出脚本把 `output_model` 记成绝对路径**，不是谁后来改坏的。
* ⚠️ **给 App 的提醒**：`app237` 的反证**会临时改 ASR 仓库里的源文件**（跨模块写操作）
  ⇒ 建议改为「在临时副本上做反证」，避免再刷新 ASR 源文件的时间戳。

### 2.4 NOTICE 已更新

`shared/NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md` 第 4 节新增：
**§4.0**（清理内容 ＋ 新 md5 ＋ `export_meta.json` 不能进包）、
**§4.0.1**（mtime 归因）。

---

## 3. ASR-046 ② asr113 两处异常的根因

### 3.1 ① thr 三档（0.30 / 0.35 / 0.40）结果完全相同

**结论：参数确实传进了内核；是「测试集里没有落在这三档之间的相似度样本」。**

* `asr111` 的 5 s 臂三 clip 共 **124** 个 `spk_conf` 样本
  （clip00 = 40、clip01 = 42、clip02 = 42），
  **落在 [0.30, 0.40] 的样本数 = 0**（6 个臂逐臂核对，全为 0）。
* 最大间隙（**派生值**：0.4217 − 0.188）位于 **clip01** 的 0.188 与 0.4217 之间
  （0.188 与 0.4217 取 `asr111_evalset_metrics.json` 里 `spk_conf` 的**逐字原值**
  ⇒ 间隙是由这两个原值相减得到的**派生量**，产物里没有该字段）
  ⇒ 实际余弦相似度要么 **< 0.30**（低于阈值 ⇒ 新建簇）
  要么 **> 0.40**（高于阈值 ⇒ 命中）
  ⇒ 三档 thr 落在**空档** ⇒ 结果必然相同。
* ⚠️ **与 ASR-040「thr 0.40 召回有变化」不矛盾**：两套数据不同
  （ASR-040 用 App 48 段集，`plateau_thresholds = [0.38, 0.4, 0.42, 0.44, 0.46, 0.48, 0.5, 0.55, 0.6]`；
  asr113 用 900 s 评测集）。

### 3.2 ② min_dur_s = 3.0 时 136 段全部 `async_pending`

**结论：不是「段太短」，是「判定顺序倒置」＋「`_drain_pending` 永不回填」两个缺陷叠加。**

* **「段太短」被实测否掉**：`asr111` 参照段时长分布
  clip00 min **2.560**（45/46 ≥ 3.0）、clip01 min **6.400**（44/44 ≥ 3.0）、
  clip02 min **2.560**（45/46 ≥ 3.0）⇒ 绝大多数段**够长**。
* 🔴 **真缺陷 ①（顺序倒置）**：`scripts/asr052_speaker_tracker_api.py` 的 `on_final`
  **先**判 `min_dur_s`（第 329–338 行）**后**判 `seg is None`（第 339–343 行）
  ⇒ 音频还没缓冲够时**先**被误判成 `audio_not_buffered`。
* 🔴 **真缺陷 ②（永不回填）**：`live_caption/speaker_tracker.py` 的
  `_drain_pending` 第 758–760 行 `if not spk: continue`
  ⇒ `seg_pending` 拿到的段**永远不会回填标签**
  ⇒ 永久停在 `async_pending`。
* 🔴 **5 s 窗口放大效应**：分段按 5 s 跳 ⇒ 段边界与 5 s 网格错位更多
  ⇒ 触发「未缓冲够」的次数更多。

### 3.3 逐段数据已落盘

`qwen3asr_06b/eval/asr118_param_ab_rows.py`（**同一测试台** `asr111.run_clip`，
但**逐段 rows 落盘** ＋ 诊断 `thr_sensitivity` / `dur_diagnosis` ＋
每臂 `per_segment_diff_vs_A`）⇒ 产物
`results/pyannote_seg/asr118_param_ab_rows.json`。

---

## 4. ASR-046 ③ min_clean_ratio 0.6 候选

**asr113 实测**（900 s 评测集）：`min_clean_ratio 0.8`（基线）⇒ 召回 19/26、
误报 3、无标签段 12；`min_clean_ratio 0.6` ⇒ 召回 **22/26**、误报 **3**、无标签段 **5**；
`min_clean_ratio 0.4` ⇒ 召回 24/26、误报 4、无标签段 3。

🔴 **只给数据、不改默认值**（ASR-044 ③）⇒ **默认是否改由用户决定**。

### 4.1 逐 clip 分段数据（来源 `results/pyannote_seg/asr113_param_ab.json`）

臂 `B_min_clean_ratio_0.6`（其余三个参数与基线完全相同 ⇒ 可归因）：

| clip | 基线 recall（0.8） | 候选 recall（0.6） | 基线误报 | 候选误报 | 基线无标签 | 候选无标签 | 段数 |
|---|---|---|---|---|---|---|---|
| clip00 | 0.75 | **0.8333333333333334** | 0 | 0 | 6 | 2 | 46 |
| clip01 | 0.8571428571428571 | 0.8571428571428571 | 3 | 3 | 2 | 1 | 44 |
| clip02 | 0.5714285714285714 | **0.8571428571428571** | 0 | 0 | 4 | 2 | 46 |
| **合计** | **0.7308**（19/26） | **0.8462**（22/26） | **3** | **3** | **12** | **5** | — |

* 🔴 **召回 ↑（+3 个换人点）而误报不变（仍 3 次）** ⇒ 这是 `min_clean_ratio` 候选里
  **「召回↑且误报不变」的最优点**（对照 `0.4`：召回 0.9231 更高，**但误报升到 4**）。
* 产物自带 `self_check_pass=true`、`lock_probe_checks=1602`、`timing_valid=true`。
* 🔴 **本模块不改默认值**（ASR-044 ③）⇒ **默认值是否 0.8 → 0.6 由用户决定**。
* ⚠️ **ASR-046 ② 要求的「逐段 rows」（每个换人点一行）仍在 `asr118` 跑** ⇒ 本节给的是
  **逐 clip 聚合**（asr113 已有）；**逐点 rows 落盘后由 §75 补**。

---

## 5. ASR-046 ④ 960 ms 显著变差的机制（asr120 实测）

**结论：不是「步长越大越差」，而是「切点量子化 ＋ 0.96 s 与这份音频的静音结构
发生特定共振」⇒ 0.96 的切点系统性地落进语音里。**

### 5.1 机制

* `Segmenter.due(state.audio_accum)` **只在 chunk 边界被检查**
  ⇒ **候选切点被量化到 chunk 步长**；
  而 `find_silence_in_range`（`live_caption/seg_stream.py`）返回**静音段中点**
  ⇒ 实际切点 = 离静音中点最近的候选网格点。
* ⇒ 步长越粗 ⇒ 切点越可能**落进语音里** ⇒ 内容被拆到相邻段 ⇒ 段级文本错位 ⇒ WER 变差。

### 5.2 实测（用 App 的**真实 `Segmenter`** 重放切段，纯音频几何，**不跑推理**）

| 臂 | 真实切点数 | 切点落在**语音**里的比例 | asr115 段数 | 段级低相似段数（ratio < 0.6） |
|---|---|---|---|---|
| 0.64 s（基线） | 46 | **0.913043** | 46 | 0（与自身比） |
| **0.96 s** | 45 | 🔴 **0.933333**（最高） | 45 | 🔴 **14 / 45** |
| 1.28 s | 46 | **0.869565**（最低） | 46 | 6 / 46 |

* 🔴 **真实切点数与 asr115 的段数逐臂完全一致**（46/45/46）⇒ 重放口径正确。
* 🔴 **非单调**：1.28 s 的入语音率**低于** 0.64 s
  ⇒ **「步长越大越差」被否定** ⇒ 0.96 的劣势是**特定共振**，不是单调效应。
* 🔴 **机制与观测同向**：0.96 的入语音率最高 ⇒ 低相似段数也最多。
* 旁证（文本层）：0.96 臂有 3 处**纯丢失**（共 596 字符，其中一段 316 字符、
  一段 213 字符被整段删掉）；1.28 臂**纯丢失 0 处**。

### 5.3 反证（3 条全抓住）

* `cpA_reverse_criterion`：把指标反向（1 − 入语音率）⇒ 「0.96 最差」**翻转**
  ⇒ 判据有鉴别力。
* `cpB_fixed_step`：三臂共用**同一组**真实切点 ⇒ 指标**相同**
  ⇒ 差异确实来自步长。
* `cpC_relative_threshold_is_load_bearing`：相对化门限（p90 − 18 dB）
  与绝对 −40 dB 的判定结果**不同** ⇒ 判据确实依赖相对化口径。

### 5.4 第一版踩的坑（保留避免重犯）

第一版量的是「**所有** chunk 边界」而不是「**真实候选切点**」
（`due()` 要求段长 ≥ `MIN_SEG_SEC` = 6 s 才有资格切）
⇒ 稀释了信号；且自写静音判据与 App 的 `_silence_threshold` 口径不一致
⇒ **本版改用 App 的真实 `Segmenter.due()` 重放**。

产物：`results/pyannote_seg/asr120_chunk_cut_quantum.json`
（`self_check_pass=true`、反证 3/3、`runs_inference=false`、`needs_machine_lock=false`）。

---

## 6. ASR-046 ⑤ ASR-042 省时口径更正（reviewer 的复算结论已核对）

### 6.1 「只有 5 dB / 10 dB 可信」——**已在 asr106 原始字段里核对**

| 臂 | `infer_wall_s` | 省时（vs 基线 159.6355） | `infer_fin_wall_s` |
|---|---|---|---|
| 0（基线） | 159.6355 | 0 | 13.1769 |
| 5 dB | 112.1868 | **47.4487（≈30 %）** | **29.621**（reviewer 的 13.2 → 29.6 **完全吻合**） |
| 10 dB | 132.6345 | **27.001（≈17 %）** | 18.1164 |
| 15 dB | 159.9728 | **−0.3373（噪声内）** | 16.3269 |
| 20 dB | 148.9546 | 10.6809 | 13.47 |
| 25 dB | 142.571 | 17.0645 | 12.4655 |
| 30 dB | 139.4189 | 20.2166 | 11.8187 |

⇒ 同工作量的臂（0/20/25/30 dB 文本相同）单次调用耗时在 **0.277–0.333 s**
之间波动（**±10 % 噪声**）⇒ **15–30 dB 报的「节省 0–12.7 %」都在噪声内**
⇒ **只有 5 dB（约 30 %）和 10 dB（约 17 %）可信**。
🔴 5 dB 时**定稿耗时从 13.2 s 涨到 29.6 s** ⇒ 每段定稿慢约 **0.37 s**。

### 6.2 `first_text_wall_s` **不是实时首字延迟**

它是在**加速重放**里测的（300 s 音频墙钟只有 91–161 s）
⇒ **不是实时首字延迟**；**实时字幕刷新间隔 = chunk 步长**（0.64 → 1.28 s）。

### 6.3 🔴 STATUS §72 的表述矛盾已改正

§72 写的「**首字延迟随门限升高而变差**」与 asr106 的表格**矛盾**
（实测 5 dB 的 `first_text_wall_s` = **2.1276 s**，**比**基线 4.0523 s **更快**）
⇒ **该结论撤回**，改写为「`first_text_wall_s` 是**加速重放**的墙钟，
**不是实时首字延迟**，**不能**用来比较门限之间的高低」。

---

## 7. ASR-046 ⑥ + ASR-047 环境变量开关（**默认关闭**）

### 7.1 交付物

🔴 **新增 ASR 交付文件第 5 个**：`qwen3asr_06b/scripts/asr_runtime_switches.py`

| 项 | ASR 侧 | App 侧 |
|---|---|---|
| chunk 步长 | `ASR_CHUNK_SEC`（默认 **0.64**） | `LIVECAP_CHUNK_SEC` |
| VAD 门限（dB） | `ASR_VAD_GATE_DB`（默认 **0.0 = 关闭**） | `LIVECAP_VAD_GATE_DB` |

* 🔴 **默认值来自 ASR 侧这一个文件** ⇒ 两边不各写一份 ⇒ 不可能漂移
  （与 `asr_spk_window` 的 `ASR_SPK_WINDOW_S` / `LIVECAP_SPK_WINDOW_S` 同款）。
* 🔴 **非法值一律退回默认**（非数字 / ≤ 0）⇒ **不静默改语义**；
  越界夹到 `[CHUNK_SEC_MIN 0.08, CHUNK_SEC_MAX 2.0]` /
  `[0.0, VAD_GATE_DB_MAX 30.0]`。
* 🔴 **不设任何变量 ⇒ chunk 0.64 s ＋ VAD 关闭**
  ⇒ **行为与 ASR-045 之前交付版逐字一致**（ASR-047 用户决定）。
* 🔴 **不改生产代码**：`live_caption/` 属 App 属地 ⇒ ASR 侧**只提供配置读取与判据**
  ⇒ App 侧 import 它并使用返回值即可。

### 7.2 VAD 门控判据的**唯一实现**（方向铁律）

```python
def gate_decision(gate_ratio_db, p90_db, win_db):
    if gate_ratio_db <= 0.0 or win_db is None:
        return False
    return (float(p90_db) - float(win_db)) > float(gate_ratio_db)
```

⇒ **门限越大 ⇒ 能被判静音的窗越少 ⇒ 跳过占比单调递减**。

### 7.3 验证产物 `asr119_switch_default_off.json`（自检 **8/8 PASS**）

| 判据 | 结果 |
|---|---|
| 默认关闭（无 env ⇒ 0.64 / 0.0 / `vad_gate_enabled=False`） | ✅ |
| 显式设置生效（1.28 / 10.0 / `True`） | ✅ |
| 非法值退回默认 | ✅ |
| 越界夹取 | ✅ |
| 🔴 「import 后改 env 也生效」（`vad_gate_enabled()` 读**实时 env**） | ✅ |
| VAD 方向铁律 ＋ 单调递减 ＋ 反证 | ✅ |
| 交付闸门（5 文件 / 关键字 0 / 链越界 0 / 隔离自洽 / 反证 4/4） | ✅ |
| 代码位置已实测 | ✅ |

🔴 **本轮抓到的真缺陷**：`vad_gate_enabled()` 初版读的是 **import 时求值的模块级
`VAD_GATE_DB`** ⇒ 设置 env 后仍返回 `False` ⇒ **开关看起来没生效**
⇒ 已改为读实时 env。

### 7.4 交付闸门重跑（`asr079_delivery_set_gate.json`）

| 项 | 值 |
|---|---|
| 交付文件数 | **5**（4 → 5） |
| 内部关键字命中 | **0** |
| 运行时 import 链越界 | **0** |
| 隔离 import 自洽 | **True** |
| 反证 | **4/4 抓住** |

⚠️ 🔴 **闸门脚本的隔离探针必须用 ASR 侧的 venv python**
（WorkBuddy 自带 python 无 numpy ⇒ `self_contained=False`）。

⚠️ 🔴 **闸门抓到本轮自己的缺陷**：`asr_runtime_switches.py` 的 docstring 里
写了「内部关键字清单」本身 ⇒ 命中 4 ⇒ **已删除该清单的逐字内容**
⇒ **交付文件连「关键字清单」都不能写出来**。

### 7.5 🔴 代码位置（实测行号，供 STATUS 引用）

| 文件 | 位置 | 内容 |
|---|---|---|
| `qwen3asr_06b/scripts/asr_runtime_switches.py` | `CHUNK_SEC_DEFAULT` | **0.64** |
| 同上 | `VAD_GATE_DB_DEFAULT` | **0.0**（= 关闭） |
| 同上 | `CHUNK_SEC_ENV` / `VAD_GATE_DB_ENV` | `ASR_CHUNK_SEC` / `ASR_VAD_GATE_DB` |
| 同上 | `def gate_decision(` | VAD 判据唯一实现 |
| 同上 | `def vad_gate_enabled(` | 读**实时 env** |
| `live_caption/live_caption_app.py` | `CHUNK_SEC =` | **0.64**（生产默认，App 属地） |

### 7.1 ASR-047 验收「无环境变量时 5 分钟切片 WER 与交付基线一致」的等价性证据

ASR-047 原文：「**无环境变量时 5 分钟切片 WER 与交付基线一致**」。
WER 由 reviewer 用 MiniMax 判定（**本模块不产出 WER**）⇒ 本模块给的是**更强的前置证据**：

1. `asr119`（`results/pyannote_seg/asr119_switch_default_off.json`）实测
   **不设任何 env ⇒ `chunk_sec = 0.64`、`vad_gate_enabled = False`** ⇒ 默认配置。
2. 默认配置下的 5 分钟切片转写，与**交付基线逐字完全相同**：

| 来源 | 口径 | 门控 | chunk | `final_text` md5 | 长度 | 段数 |
|---|---|---|---|---|---|---|
| `asr106_vad_gate_windows.json` 臂 0 | 0 dB（门控关闭） | `skip_ratio=0.0`、`n_skip=0` | 0.64 | `32c556292a052cabe1fcfabfd62597c7` | 4651 | 46 |
| `asr115_chunk_size_eval.json` 臂 0.64 | 生产默认 chunk | — | `production_chunk_sec=0.64` | `32c556292a052cabe1fcfabfd62597c7` | 4651 | 46 |

   ⇒ 两条**独立**路径（VAD 门控参数化 / chunk 参数化）给出的默认文本**逐字一致**，
   且 **46/46 段逐段文字相同** ⇒ **同一计分器下 WER 必然一致**。
   （表里的 `final_text` md5 是**实测派生值**：产物里存的是 `final_text` 原文，
   md5 由它算出 ⇒ 可用 `hashlib.md5(final_text.encode('utf-8')).hexdigest()` 复算。）
3. 音频口径：两份产物都是 `shared/SPE_0000_0500.wav`（16 kHz、300.0 s）＝ 5 分钟切片。

🔴 **结论**：ASR-047 的验收项**等价性已闭合**；**具体 WER 数值仍交 reviewer**。

---

## 8. ASR-046 ⑦ status_verify 类脚本已删除

`qwen3asr_06b/eval/asr116_verify_s72.py`（11489 B @ Nov 4 21:33，
md5 `6c2a147da1955e2b96dd6897df1fa92a`）
⇒ 标题即「**独立复核 §72 写入**」⇒ 属 **status_verify 类**
⇒ 按 **ASR-038 ＋ ASR-046 ⑦ 删除**，且**不引用**。
🔴 该文件**不在 git 内**（`git ls-files` 无命中）⇒ 删除不影响仓库历史。
🔴 **同时不得新建替代复核脚本**（ASR-038）。

---

## 9. 本轮**未做**的（明确边界）

* 🔴 **未动 `live_caption/` 下的任何文件**（用户明令 + C-111 已移交 App）。
* 🔴 **未跑 TTS**（ASR-046 ⑥ 明写「本模块不要自己跑 TTS」）。
* 🔴 **ASR-042 第 3 步暂停**（ASR-047 用户决定：TTS 侧速度要求已取消）。
* 🔴 **未改任何默认值**（`min_clean_ratio`、`CHUNK_SEC`、VAD 门控默认都未改）。
* 🔴 **未打包**（用户级记忆：不通知 ⇒ 不主动打包）。
* 🔴 **未改 `CORRECTIONS_ASR.md`**（reviewer 维护且不提交）。
* 🔴 **WER 未算**（铁律）⇒ 交 reviewer。

---

## 10. 遗留（等用户指派）

1. 🟡 **待 App 侧落地**：5 个 ASR 文件（含新增 `asr_runtime_switches.py`）
   打进包 ＋ `sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 追加 2 个
   （`asr_spk_window.py` ＋ `asr_runtime_switches.py`）
   ＋ 5 s 静态 seg IR 放进 `models/spk/pyannote_seg_3_0/fp16-w5/`
   （**用新 md5 `14b224bced3289237799bc9a7eb746ff`**）。
2. 🟡 **待 App 侧实现**：chunk 步长 / VAD 门控的**读取**（import
   `asr_runtime_switches` ＋ 在 `live_caption_app.py` 的 `CHUNK_SEC` 与
   OVEngine backend 包装处使用）⇒ **ASR 侧不改 `live_caption/`**。
3. 🟡 **待 reviewer 补齐**：`CORRECTIONS_ASR.md` 索引表补 ASR-037…047 共 11 行。
4. 🟡 **待用户决定**：`min_clean_ratio` 默认值是否从 0.8 改到 0.6。
5. ⚠️ **非纠偏项遗留 3 条**（等用户指派才做）：
   ① OV f16 偏差高于 torch FP16 固有下界；
   ② `qwen3asr_06b` 不在 git 内 ⇒ 交付需另行打包；
   ③ 8 个 `pya_*` 历史产物无 `lock_probe` 块 ⇒ 只被归档引用。
