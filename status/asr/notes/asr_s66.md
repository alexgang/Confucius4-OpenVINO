# ASR §66 明细 —— 修掉两个遗留真缺陷 + 加装守卫

> 🔴 本文件是 `status/asr/STATUS_ASR.md` §66 章节的**明细**（ASR-036：长日志 / 逐条明细写
> `status/asr/notes/`，STATUS 里只留结论、数字和链接）。
> 🔴 **本轮无新纠偏**（`CORRECTIONS_ASR.md` **12 493 B @ 2026-10-30 15:44:31**、
> md5 `ae967731dd2e2dbf49fb7690239b30bb` ⇒ 与 §63/§64/§65 三轮**逐字节一致**；
> `grep '^## ASR-'` 全文最大编号 = **ASR-036** = `last_ack`）⇒ 按 **ASR-034**
> 「last_ack 追平后只要还有未完成项就继续做，不要空转」⇒ 本轮做**遗留项修复**。

---

## 0. 纠偏检查（本轮）

| 项 | 实测 |
|---|---|
| `status/asr/CORRECTIONS_ASR.md` | **12 493 B @ 2026-10-30 15:44:31**，md5 `ae967731dd2e2dbf49fb7690239b30bb` |
| 与上轮（§65）比 | **逐字节一致**（md5 相同）⇒ **未被追加** |
| 全文最大编号 | **ASR-036**（`grep '^## ASR-'`） |
| `STATUS_ASR.md` 的 `last_ack` | **ASR-036**（= 最大编号） |
| 全仓扫 `ASR-0(3[7-9]|[4-9][0-9])`（`status/` + `qwen3asr_06b`） | **命中 0** |
| ⇒ 结论 | 🔴 **无新纠偏**，按 ASR-034 继续做遗留项 |

---

## 1. 🔴 缺陷 A —— `timing_valid = true` 但 `lock_probe_checks = 0`

### 1.1 症状（STATUS 头部「阻塞/待用户决定」③ 早已点名）

> 旧产物 `asr050`（`timing_valid=true` 但 `lock_probe_checks=0`）… **复用前需修**

### 1.2 为什么这是**真缺陷**（§31 铁律）

- §31：**计时脚本必须真调 `probe.check()`** ⇒ 每 2 s 调一次并让
  **`lock_probe_checks > 0` 成为产物断言**。
- 这 3 个产物的 `lock_probe.lock_probe_checks = 0` ⇒ **`probe.check()` 从未被调用**
  ⇒ 产物里 `lock_probe_note` 写的「本次**未**发现锁被抢」是**一句未经核验的断言**
  （**没查 ≠ 没被抢**）⇒ `timing_valid = true` 不成立。
- 归档 §62 的处方原文：「`asr050` 的 `lock_probe_checks = 0` 却写了
  `timing_valid = True`（离线作业）⇒ **应写 `timing_valid = null`**」。

### 1.3 🔴 实测：STATUS 只点了 1 个，**实际有 3 个**

| 产物 | `timing_valid` 所在位置 | 原值 | `lock_probe_checks` | 本轮处置 |
|---|---|---|---|---|
| `asr050_spk_qa_speaker_test.json` | 🔴 **`timing` 子块**（不是顶层！） | `true` | **0** | → `null` |
| `asr055_spk_qa_reference_eval.json` | 顶层 | `true` | **0** | → `null` |
| `_smoke_asr040_base.json` | 顶层 | `true` | **0** | → `null` |

- 🔴 **口径坑**：`asr050` 把 `timing_valid` / `lock_probe` 放在 **`timing` 子块**里
  ⇒ 只查顶层会**漏掉 asr050**（守卫首版就漏了 ⇒ 由**自检**抓出，见 §4.1）。
- ⚠️ `_smoke_asr040_base.json` 是**冒烟产物**（`_` 前缀）⇒ 未被 STATUS 点名，
  但它同样写着 `timing_valid=true` + `checks=0` ⇒ **同一类缺陷，一并修**。

### 1.4 本轮怎么改（🔴 只改标记，**不改任何实测数值**）

每个产物：

- `timing_valid`: `true` → **`null`**（语义 = 「本产物**不产**性能结论」，
  **不是**「测得无效」）；
- 原值挪 **`timing_valid_observed`**（不删历史）；
- 加 `timing_valid_reasons`（4 条，逐条含证据）+ `timing_valid_evidence`
  （含 `lock_probe_checks` / `lock_probe_stolen` / 原值 / 字段位置）；
- 🔴 **改正锁探针的假断言**：原文挪 `lock_probe_note_original`，
  新 `lock_probe_note` 写明「**本次未做锁核验**（`checks == 0`）⇒ 原文那句
  『未发现锁被抢』**不成立**」。

**实测数值一个没动**：`asr050` 的 `main_wall_s = 814.046`、`seg_wall_s = 41.997`、
`seg_rtf = 0.03019` **逐字未改**（只是不再被标成「有效计时」）。

---

## 2. 🔴 缺陷 B —— `clips_manifest` 的 `n_both = 0` 却 `tp = 8`

### 2.1 症状

STATUS 头部与归档 §62 都点过：

> ⑤ ⚠️ **`clips_manifest` 的 `n_both = 0` 却 `tp = 8`**（8 个命中点被导出两次，
> 来源标签不对）⇒ 复用前修

### 2.2 🔴 根因（实测定位，不是猜）

`eval/asr055_spk_qa_reference_eval.py` 构造清单的代码：

```python
clip_points = sorted(set(pred_switch + substantial_qa))
```

- 去重用 **`set()`（精确相等）** ⇒ 只有**时间戳完全相同**的点才合并；
- 而匹配容差是 **`tol_s = 0.5`** ⇒ **8 对命中点两侧时间差只有 0.024 – 0.388 s**
  ⇒ **不被判为同一事件** ⇒ 同一事件被导出**两次**、来源标签一个 `pred_only`
  一个 `truth_only` ⇒ **`n_both = 0`**（与 `tp = 8` 自相矛盾）。

**实测 8 对命中点两侧时间戳与 v1 的 idx**（`tol_s = 0.5`）：

| # | `pred_t` | v1 idx | `truth_t` | v1 idx | `dt` |
|---|---|---|---|---|---|
| 1 | 2305.6 | 1 | 2305.73 | 2 | 0.13 |
| 2 | 2744.0 | 21 | 2744.024 | 22 | 0.024 |
| 3 | 3007.04 | 34 | 3007.308 | 35 | 0.268 |
| 4 | 3028.16 | 36 | 3028.52 | 37 | 0.36 |
| 5 | 3185.6 | 42 | 3185.643 | 43 | 0.043 |
| 6 | 3198.4 | 44 | 3198.788 | 45 | 0.388 |
| 7 | 3481.28 | 59 | 3481.327 | 60 | 0.047 |
| 8 | 3551.04 | 65 | 3551.324 | 66 | 0.284 |

⇒ **全部落在容差内，却全部被拆成两条** ⇒ 根因坐实。

### 2.3 修法（v2 清单）

- 🔴 **按 `tol_s = 0.5` 把命中对聚成「事件」** ⇒ 命中 ⇒ 1 条，
  `in_pred = true` / `in_truth_substantial = true` / `source = 'both'`；
- 每个事件都带 **`pred_t` / `truth_t` / `dt`** ⇒ §22「口径钉死」：
  `n_pred` / `n_truth` / `n_both(=tp)` **可从清单自身复算**；
- **v1 清单与 79 个音频一个字节未动**（md5 锚定 `2c578a27c123b80050011441a6ac735a`）
  ⇒ v2 写到**新目录** `_asr055_clips_v2/`；
- 额外落 **v1 ↔ v2 索引映射**（79 条全覆盖）⇒ 旧的按 idx / 按 t 的引用仍可追溯；
- `asr055` 的 `clips` 字段改指 v2，v1 挪到 `clips_legacy_v1`（**不删历史**）。

### 2.4 实测结果（v1 → v2）

| 项 | v1 | **v2** |
|---|---|---|
| 清单条数 | 79 | **71** |
| `n_pred` | 29 | **29** |
| `n_truth` | 50 | **50** |
| `n_both` | 🔴 **0** | ✅ **8** |
| 从清单复算的 `tp` | —— | **8** |
| `n_both == tp` | 🔴 否（0 ≠ 8） | ✅ **是** |
| 与 `asr055` 的 `tp`（可比口径）一致 | —— | ✅ **8 == 8** |

- **71 = 29 预测 + 50 真值 − 8 合并** ⇒ 数学自洽。
- 🔴 **ASR-032 的 3 个抽听引用仍可解析**：`t=2514.2 → v2 idx 9`、
  `t=2527.0 → v2 idx 10`、`t=3570.2 → v2 idx 61`（三者 `source` 仍是 `pred_only`
  ⇒ **用户抽听结论不受影响**）。
- v1→v2 映射的来源标签变化（实测 79 条全覆盖）：
  `truth_only→truth_only` 42 条 / `pred_only→pred_only` 21 条 /
  **`pred_only→both` 8 条** / **`truth_only→both` 8 条** ⇒ 正好是那 8 对命中点。

---

## 3. 加装守卫 `asr096_legacy_consistency_gate.py`

🔴 两个缺陷属**同一类**：「产物里有一个**断言**，但产物自己手里的**证据**不支持它」
⇒ 变成**机读门禁**，且**每条判据配反证**（§44b：守卫通过 ≠ 守卫有鉴别力）。

| 判据 | 内容 |
|---|---|
| G1 | 凡 `timing_valid == true` ⇒ 必须 `lock_probe.lock_probe_checks > 0`（**递归**查顶层与 `timing` 子块） |
| G2 | 凡 `timing_valid == null` ⇒ 必须有 `timing_valid_reasons` **或** `timing_valid_reason` |
| G3 | v2 清单 `n_both` == 从清单**自身复算**的 `tp` |
| G4 | v2 的 `n_pred`/`n_truth`/`tp` 与 `asr055` 可比口径一致 |
| **G4b** | v2 的**真值点集**与**独立重算**逐字一致（不只比个数） |
| **G4c** | v2 的**预测点集**与 `asr050` 的 `switch_points` 逐字一致 |
| G5 | v1 清单 md5 == 冻结锚点（证明「修 v2 没偷偷改 v1」） |
| G6 | v2 输出目录 wav 数 == 清单条数 |

- 🔴 **两类必须分开**（否则要么误伤、要么漏检）：
  - **① 硬缺陷**：产物**自带 `lock_probe` 块**且 `checks == 0` ⇒ 判 FAIL；
  - **② 历史遗留**：产物**没有 `lock_probe` 块** ⇒ 那是**锁探针机制引入之前**
    （`asr_lock_common.py` @ **2026-10-27 09:34**）的产物（这批是 **10-26/10-27**）
    ⇒ 当时**没有**「探针检查」这回事 ⇒ 同样未经核验，但**只被归档章节引用**
    ⇒ 本轮**只记录，不追溯改历史结论**（改标 = 改旧结论）。

### 3.1 实测结果

| 项 | 值 | 来源 |
|---|---|---|
| 基线守卫 | **ALL PASS**（9 项判据） | `asr096_legacy_consistency_gate.json` → `status` = `PASS` / `n_checks` = 9 |
| 注入反证 | **10/10 全过** | `asr096_legacy_consistency_gate_inject.json` → `n_counterproofs` = 10 / `n_counterproofs_caught` = 10 |
| 扫描产物数 | **123** 个 JSON | 同上 → `checks` |
| ②类历史遗留 | **8** 个（`pya_*` 家族） | 同上 → `legacy_no_lock_probe.count` |

**8 个 ②类历史遗留**（**只记录，等用户指派**）：
`pya_bench_fp16_GPU0` / `pya_bench_fp16_NPU` / `pya_bypass_spk_asr021ami` /
`pya_bypass_spk_wes_ami` / `pya_bypass_spk_wes_ami1280` /
`pya_bypass_spk_wes_spe5m` / `pya_stream_full61_NPU` / `pya_stream_smoke_GPU0`
⇒ ⚠️ 这 8 个**只被归档章节引用**（当前精简版 STATUS **引用 0** 次），
且 `pya_stream_full61_NPU.json` 的 `rtf_seg_model` = **0.01068** 曾进过交付对比
⇒ 🔴 **追溯改它们 = 改旧结论** ⇒ **等用户指派再动**。

---

## 4. 🔴 本轮**自检抓出的自身 bug**（§40/§64 纪律的又一次验证）

### 4.1 写入脚本 `asr095` 的 2 个 bug（**干跑时**抓出，未污染真实产物）

| # | bug | 症状 | 修法 |
|---|---|---|---|
| 1 | 只查**顶层** `timing_valid` | `asr050` 把字段放在 **`timing` 子块** ⇒ 改标数 **2/3** | 递归定位承载块（顶层 or `timing` 子块） |
| 2 | `greedy_match` 返回的 `used` 装的是**真值点下标**，代码却拿它和**时间戳**比 | 命中过的真值点被当成「只真值有」重复导出 ⇒ `n_truth` 虚高 **58 vs 正确 50** | 把下标**还原成时间戳**再比对 |

🔴 另有 1 个：**输出目录未清空** ⇒ 第 1 轮（79 事件）与第 2 轮（71 事件）的 wav
**同目录共存 = 146 个** ⇒ 目录里的片段数与清单**对不上** ⇒ 抽听时会把过期片段当新的
⇒ 修法：**先清空输出目录** + 落盘后自检「wav 数 == 清单条数」。

⇒ **干跑 3 轮才转绿**；真实产物在转绿后才写。

### 4.2 守卫脚本 `asr096` 的 3 个 bug（**注入测试**抓出）

| # | bug | 症状 | 修法 |
|---|---|---|---|
| 1 | `check_clips_v2()` 把 `P` / `CLIP_V2` **硬编码** | 注入测试在**沙箱副本**上跑，它检查的仍是**真实产物** ⇒ 注入的缺陷**根本没被看到** ⇒ 反证 cp8「鉴别力不足」 | 所有路径**从 `root` 派生**；`clips.dir` 只比**末段目录名** |
| 2 | G2 只认 `timing_valid_reasons`（复数） | `asr082` 用的是 `timing_valid_reason`（单数）⇒ **误伤** | 两种字段名都认 ⇒ 并加反证 cp10「**不得**误伤」 |
| 3 | G4 只比**计数** | 把某个真值时间戳改成别的值，**计数不变** ⇒ 计数判据**看不见** ⇒ 反证 cp5「鉴别力不足」 | 加 **G4b / G4c**：**点集逐字比对**（真值点集 vs 独立重算、预测点集 vs `asr050`） |

🔴 另：**`--inject` 会覆盖基线产物** ⇒ 「基线 ALL PASS」与「反证 10/10」两个事实
只剩一个 ⇒ 拆成**两个产物文件**（`asr096_legacy_consistency_gate.json` /
`asr096_legacy_consistency_gate_inject.json`）。

### 4.3 🔴 复核脚本 `asr098` 的 3 个 bug（**复跑 + 注入测试**抓出）

| # | bug | 症状 | 修法 |
|---|---|---|---|
| 1 | notes 里**只列了** `asr095` / `asr096` 两个脚本的 size/mtime，**从未列** `asr097` | 独立复核 V14 判 `asr097` 引用 == 实测 ⇒ **FAIL**（`21 925 B @ 2026-10-31 01:33:28` 缺失） | 把 `asr097` 的实测 size/mtime 补进 §6 产物清单 |
| 2 | 🔴 **复跑 `asr096` 后立刻复发 §60 铁律**：守卫产物 JSON 的 mtime 从 `01:31:44` 变成 `01:36`（**重跑即改写**），而 §6 **引了它的 size/mtime** ⇒ **立刻脱节** | 这是 §64/§65 修过 D6 的**同一类缺陷复发**（§60：可重跑产物**只引内容事实**、**不引 mtime**） | §6 里所有**可重跑** JSON 产物改引**内容事实**（`status` / `n_checks` / 计数），**只对冻结脚本**引 size/mtime |
| 3 | 🔴 若把**复核脚本自身** `asr098` 的 size/mtime 也写进 notes | 改脚本 → 引用过期 → 再改脚本 ⇒ **自指 churn** ⇒ 基线必 FAIL（§55 循环依赖铁律） | **不引用复核脚本自身**的 size/mtime，只引其**内容事实**（ALL PASS 判据数 + 反证条数） |

🔴 由此新增守卫判据 **V17**（**§60 铁律的机器化守卫**）：notes 里若出现
「可重跑产物文件名 + `<size> B @ <时间>`」⇒ **FAIL**；
配套**注入反证 cp9**（往沙箱 notes 塞一行这种引用 ⇒ 必须被抓）。

⇒ asr098 独立复核：**基线 ALL PASS（42 项判据）** + **注入反证 9/9**。

---

## 5. 纪律

- 本轮**不跑任何模型推理**（只做文件读写 + 音频切片 + 数值重算）⇒ **未申请共享机器锁**
  （检查时 `shared/MACHINE_LOCK` **不存在**、`shared/*.tmp` 残留 **0**、`GIT_FREEZE` 不存在）。
- 🔴 **未动 `live_caption/`**；🔴 **未改** `CORRECTIONS_ASR.md`（reviewer 维护）；
  `last_ack` 保持 **ASR-036**。
- 🔴 **未覆盖已交付产物**：v1 清单与 79 个音频**一个字节未动**（md5 锚定）。
- ⚠️ **WER 未跑**（交 reviewer）；**未开新实验**（只做遗留项修复）。
- 🔴 **未打包**（按用户级记忆：不主动打包）。

---

## 6. 产物清单（**均在 git 仓库外** —— `qwen3asr_06b` 不在 repo 内 ⇒ 交付需另行打包）

| 路径 | size / mtime | 说明 |
|---|---|---|
| `qwen3asr_06b/scripts/asr095_fix_legacy_timing_and_clips_v2.py` | **27 955 B @ 2026-10-31 01:28:01** | 修复脚本（干跑→转绿→才写真实） |
| `qwen3asr_06b/scripts/asr096_legacy_consistency_gate.py` | **22 452 B @ 2026-10-31 01:31:31** | 守卫脚本（判据 G1–G6 + 反证） |
| `qwen3asr_06b/scripts/asr097_status_write_s66.py` | **21 925 B @ 2026-10-31 01:33:28** | §66 STATUS 写入脚本（干跑→转绿→才写真实） |
| `qwen3asr_06b/scripts/asr098_status_verify_s66.py` | 内容事实：基线 **ALL PASS**（**42** 项判据）+ 注入反证 **9/9** | §66 **独立复核**脚本（§43：不复用写入脚本自检）。🔴 **不引 size/mtime**（§55 循环依赖：复核脚本与 notes 互引 ⇒ 自指 churn） |
| `qwen3asr_06b/results/pyannote_seg/asr095_fix_legacy_timing_and_clips_v2.json` | 内容事实：`passes` = **true**；改标 **3/3**、v2 **71** 事件 | 修复产物（**可重跑** ⇒ 只引内容事实，**不引 size/mtime**，见 §60 铁律） |
| `qwen3asr_06b/results/pyannote_seg/asr096_legacy_consistency_gate.json` | 内容事实：`status` = **PASS**、`n_checks` = **9**、扫描 **123** 个 JSON | 基线守卫产物（**可重跑** ⇒ 不引 size/mtime） |
| `qwen3asr_06b/results/pyannote_seg/asr096_legacy_consistency_gate_inject.json` | 内容事实：反证 **10/10** | 注入产物（**可重跑** ⇒ 不引 size/mtime） |
| `qwen3asr_06b/results/pyannote_seg/asr098_status_verify_s66.json` | 内容事实：`status` = **PASS**、`n_checks` = **42** | 独立复核基线产物（**可重跑** ⇒ 不引 size/mtime） |
| `qwen3asr_06b/results/pyannote_seg/asr098_status_verify_s66_inject.json` | 内容事实：反证 **9/9** | 独立复核注入产物（**可重跑** ⇒ 不引 size/mtime） |
| `qwen3asr_06b/results/pyannote_seg/_asr055_clips_v2/clips_manifest.json` | 内容事实：**71** 事件（含 `v1_to_v2_index_map` 79 条全覆盖） | **v2 清单**（**可重跑** ⇒ 不引 size/mtime） |
| `qwen3asr_06b/results/pyannote_seg/_asr055_clips_v2/clip_*.wav` | **71 个** | **v2 片段**（与清单条数一致） |
| `qwen3asr_06b/results/pyannote_seg/asr050_spk_qa_speaker_test.json` | 改标 | `timing.timing_valid` → `null`（实测数值未改） |
| `qwen3asr_06b/results/pyannote_seg/asr055_spk_qa_reference_eval.json` | 改标 + 改指 v2 | `timing_valid` → `null`；`clips` → v2（v1 留 `clips_legacy_v1`） |
| `qwen3asr_06b/results/pyannote_seg/_smoke_asr040_base.json` | 改标 | `timing_valid` → `null` |
| `confucius4-openvino/status/asr/notes/asr_s66.md` | — | **本文件（进 git）** |
