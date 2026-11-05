# §76 ASR-048 落地：给 App 的「新说话人登记用干净段」接口说明（a–d）＋ `overlap_ratio_max` 惰性参数的定性

> 本节 = `status/asr/notes/asr_s76.md`（**已提交**）。
> 产物：`C:\Users\Trekker-PTL\qwen3asr_06b\results\pyannote_seg\asr121_overlap_clean_diag.json`
> （23314 B，`self_check_pass=true`；**纯静态分析 + 数值复刻** ⇒ 不跑推理、不占设备、不需机器锁）。
> 脚本：`C:\Users\Trekker-PTL\qwen3asr_06b\eval\asr121_overlap_clean_diag.py`（**不在 git 内**，`qwen3asr_06b` 未纳入版本管理）。

---

## 0. 本轮范围（严格按 ASR-048，不扩大）

ASR-048 要求：**不改默认值、不新开长实验、不需要锁、不需要新作业**，只做两件事：

1. **第 1 点**：核实 `overlap_ratio_max` 在当前路径下是否根本没被求值 ⇒ 给出结论。
2. **第 3 点 (a–d)**：给 App 写一份 ≤1 页的接口说明 ⇒ 落在本文件 §2 与 STATUS §76。

**本轮未做**：未改任何默认值（`thr=0.35` / `min_clean_ratio=0.8` / `overlap_ratio_max=0.02` / `min_dur_s=2.0` **全部原样**）；
未跑推理/测速；未申请 `MACHINE_LOCK`；**未动 `live_caption/` 任何文件**；未新增 `status_verify` 类脚本
（本脚本是**产品级诊断**，输出的是「参数是否惰性」这一**产品结论**，不是 STATUS 自审守卫）。

---

## 1. 第 1 点结论：`overlap_ratio_max` 是**惰性参数（never fires）** 🔴

### 1.1 结论一句话

> 🔴 **`overlap_ratio_max` 在当前路径下**根本没有被求值** ⇒ 它是一个**永不触发的惰性参数**。
> ⇒ **不能**把「`B_overlap_ratio_max_0.05` 与基线 136/136 逐段相同」当作「已验证无影响」
> —— 它**恒等于基线，与阈值取值无关**（把阈值改成 0.05、0.02、0.001 都一样）。

### 1.2 证据链（三层，逐层可复核）

**① 源码级（真实字节，产物 `code_locations.overlap_expr` / `code_locations.p_dom_source`）**

求值点（`qwen3asr_06b/scripts/asr052_speaker_tracker_api.py`，`:351`）：

```python
                overlap_ratio = float(
                    (p_dom[:, 1:].sum(axis=1) > 1.05).mean())
```

判定点（同文件 `:361`）：`if overlap_ratio > self.overlap_ratio_max:`

`p_dom` 的**唯一来源**（`qwen3asr_06b/scripts/asr052_spk_runtime.py`，`:487` `FrameAggregator.finalize()`）：

```python
        p_speech = 1.0 - p[:, 0]
        p_dom = p[:, list(SINGLE_CLASSES)]
```

而 `SINGLE_CLASSES = (1, 2, 3)`（`:431`）、`NUM_CLASSES = 7`（`:430`）。

🔴 **关键**：segmentation-3.0 是 **powerset 7 类**（0=空 / 1-3=单说话人 / **4-6=两两重叠**），
但 `finalize()` **只取 `p[:, [1,2,3]]`** ⇒ **重叠类 4/5/6 在进入判定前就被丢弃**
⇒ `p_dom` 的每一行是「三个单人类概率」⇒ **行和 ≤ 1.0**
⇒ `(p_dom[:, 1:].sum(axis=1) > 1.05)` **恒为 False** ⇒ `overlap_ratio` **恒 0.0**
⇒ `0.0 > 0.02` **永远不成立** ⇒ 该分支**永不执行**。

**② 数值复刻（产物 `numeric_replication`）**：20000 次随机 powerset 采样，
逐字复刻同一表达式 ⇒ `overlap_ratio` = **0.0**（`is_zero=true`），行和 max **1.0000000000000002**。
**反证**（同产物 `counterexample_with_overlap_classes`）：把重叠类（4/5/6）并进 `p_dom` 后
`overlap_ratio` = **0.61835** ⇒ 证明「恒 0」的根因是 **`p_dom` 的构造**，**不是**阈值取值。

**③ 产物级（产物 `rows_audit.arms`）**：8 个臂 × 136 段，`overlap_ratio` 全为 `None`（桥接层过滤，见 §1.3），
而 `B_overlap_ratio_max_0.05` 与基线**逐段 136/136 相同**（`id_swap_vs_baseline` 里 diff=0）⇒ 与「该分支永不触发」一致。

### 1.3 顺带定位第 1 点的第二半：`clean_ratio` 为什么是 `None`

🔴 **`clean_ratio` 不是「没求值」，而是「**求值了但字段在桥接层被丢弃**」**：

* 内核**确实**算出了它：`asr052_speaker_tracker_api.py:347`
  `clean_ratio = float(clean_f.mean()) if clean_f.size else 0.0` ⇒ `:356` `base['clean_ratio'] = round(clean_ratio, 4)`；
* 但 `live_caption/speaker_tracker.py` 的 `_drain_pending`（`:763`）只按**白名单**转发 **6 个字段**：
  `spk` / `spk_conf` / `clean_ranges` / `pending` / `reason` / `is_new_spk`
  ⇒ **`clean_ratio` 与 `overlap_ratio` 都不在白名单里**
  ⇒ 评测脚本（`asr111_evalset_metrics.py:177`/`:216` 读 `res.get('clean_ratio')`）拿到的必然是 `None`；
* **对照证据**：`n_clean_ranges` 在**同一处**由 `len(res.get('clean_ranges') or [])` 算出 ⇒ **有值**
  （`asr118` 基线：标段 = {1 区间: 120 段, 2 区间: 4 段}）
  ⇒ **恰好证明「字段是被过滤掉的，不是没算」**。

🔴 **重要含义**：`min_clean_ratio` **是生效的**（它在**内核**里判，`:358`），
只是它的**比值**没被桥接层转发出来。**不要**把「`clean_ratio` 是 None」读成「`min_clean_ratio` 没生效」。

---

## 2. 给 App 的接口说明（ASR-048 第 3 点 a–d）— APP-071 线索

> **给谁看**：App 线程（`APP-071` 报告「克隆把男声 S2 克隆成女声，怀疑 S2 首次检测用了错误片段登记」）。
> **ASR 侧只提供口径，不改 App 代码**；下列字段与取舍**由 App 线程决定是否采用**。

### (a) `spk_conf` 的确切含义 —— 它是「与已登记说话人的最大余弦相似度」，**低 = 新人**，不是「标签可信度」

* **定义**：`spk_conf` = 该段嵌入向量与**已有簇心**的**最大余弦相似度**
  （`qwen3asr_06b/scripts/asr052_spk_runtime.py` 的 `OnlineSpeakerCluster.assign()`：
  `sims = [dot(u, c) for c in centroids]`；`j = argmax(sims)`；`conf = sims[j]`）。
* **三种情形**：
  | 情形 | `spk_conf` | 含义 |
  |---|---|---|
  | 该 spk 是**第一个**簇 | **1.0** | `assign()` 直接返回 `('S1', 1.0, 'init')`，**不是相似度** |
  | 命中已有簇 | `sims[j]`（通常 0.4–0.9） | 与该簇心的相似度 |
  | **新说话人**（相似度 < `thr`=0.35） | `sims[j]`（**低**，如 0.0833 / 0.1212 / 0.101 / 0.0153） | **「与所有已登记人都不像」⇒ 判为新人** |
* 🔴 **因此：`spk_conf` 低 ≠ 标签不可信，而是「这一段与所有已登记说话人都不同 ⇒ 疑似新人」**。
  典型新说话人事件（`asr118` 基线臂，`is_new_spk=true` 且 `spk_conf` 低）：
  `clip00 seg1 conf=0.0833`、`clip00 seg4 conf=0.1212`、`clip00 seg18 conf=0.0153`、
  `clip02 seg4 conf=0.101`、`clip01 seg3 conf=-0.0446`（**负值**也是合法的余弦相似度）。
* 🔴 **对 APP-071 的直接含义**：**不能**用 `spk_conf` 低来怀疑「标签错」；
  真正该查的是 **「这第一次登记用的音频段是不是选对了」**（见 (b)）。

### (b) 新说话人登记时用的是**哪段音频**

* **登记用的音频 = 该段的 `clean_ranges`**（**不是**整个段）：
  App 侧 `live_caption_app.py` 的 `_spk_pcm_for()` → `SpeakerBridge.pcm_for_ranges(rngs, ...)`
  ⇒ **只切 `clean_ranges` 覆盖的子区间** ⇒ **结构性保证「不混入别人」**。
* **`clean_ranges` 的定义**（`asr052_speaker_tracker_api.py` 的 `_clean_ranges()`，`:520`）：
  段内 `p_speech >= 0.5` 的**连续区间**，且**长度 ≥ 0.3 s** 才算可用；坐标 = **全局时间轴秒**。
* 🔴 **换人边界所在段是否可能混入上一说话人？** —— **可能，而且这正是 APP-071 的怀疑点**：
  * 段边界来自 App 的切段规则（规则1/规则2，最短 6 s），**不是**按说话人换人点切的 ⇒
    **换人点常常落在某个段内部** ⇒ 该段**前半是上一说话人、后半是新人**；
  * 此时 `clean_ranges` 会把该段切成**多个连续区间**（`asr118` 基线：4 段有 **2** 个区间，120 段有 **1** 个），
    但 **`clean_ranges` 只按 `p_speech ≥ 0.5` 切（语音 vs 非语音）**，
    **不区分「是谁在说话」** ⇒ 🔴 **一个区间里完全可能同时包含两个人的语音**
    （只要都不是静音）；
  * ⇒ **这不能靠 ASR 侧再补判据解决**：ASR 侧只有「语音/非语音」和「整段的簇归属」，
    **没有帧级的说话人身份**。
    ⇒ **App 侧可行的处置（由 App 线程决定）**：
    ① 首次登记**只取该段 clean 区间里**与 `is_new_spk` 判定**时间上最近**的一段
    （或只取 `t_start` 之后的部分）；
    ② 或者**等新人拿到第二段再登记**（用第二段单独算 ⇒ 更干净），代价是首句延迟；
    ③ 或者 ASR 侧**新增**「段内按帧级主导说话人切分」的能力 —— 但这需要 `p_dom` 的**完整 7 类**
    （当前被截成 3 类，见 §1.2）⇒ **属新开发量，不在本轮范围**。
* ⚠️ **`is_new_spk` 的确切语义**（`asr052_speaker_tracker_api.py:380`）：
  `is_new = (self._prev_spk is None) or (spk != self._prev_spk)`
  ⇒ **「与上一段标签不同」**，**不是**「这个 spk 从未出现过」。
  ⇒ 同一说话人被**拆成两个 ID** 时，第二个人也会触发 `is_new_spk=True`
  ⇒ App 侧「`is_new_spk` ⇒ 换人 ⇒ 取样一次」的前提**在拆分场景下会误触发**
  （`asr118` 基线里 `is_new_spk=true` 的段共 **29** 个，而真实换人点只有 **26** 个 ⇒ **3 个是拆分/回切误触发**）。

### (c) `clean_ranges` / `clean_ratio` / `overlap_ratio` 的定义、单位、App 怎么拿

| 字段 | 定义 | 单位 | 内核是否真的算 | 现有 API 是否返回给 App |
|---|---|---|---|---|
| `clean_ranges` | 段内 `p_speech ≥ 0.5` 的**连续区间**，长度 ≥ **0.3 s** 才保留 | **秒**（全局时间轴，`(start_s, end_s)` 元组列表） | ✅ 算 | ✅ **已经在返回**（桥接层白名单内，`:763`）⇒ **App 无需新字段** |
| `clean_ratio` | 段内 `p_speech ≥ 0.5` 的**帧占比** | **无量纲 ∈ [0,1]** | ✅ 算（`:347`） | ❌ **被桥接层丢弃** ⇒ 读到的必然是 `None` |
| `overlap_ratio` | `(p_dom[:, 1:].sum(axis=1) > 1.05).mean()` —— 意在量「重叠帧占比」 | 无量纲 ∈ [0,1] | ⚠️ **恒 0.0**（§1.2） | ❌ 被桥接层丢弃 ⇒ `None` |

* 🔴 **`clean_ranges` 已经通过现有 API 返回**（App 侧 `note_final()` / `_spk_pcm_for()` **已经在用**）
  ⇒ **ASR-048 (c) 的答案：App 不需要内核新增字段就能拿到每段的 clean 区间**；
* **若 App 还想要 `clean_ratio` 本身**（例如想自己按比值筛选段）⇒ **可以由 `clean_ranges` 直接算出**
  （`clean_ratio ≈ Σ(b-a) / 段时长`）⇒ **不必改内核**；
  ⇒ 若确实想让内核直接给，**需要改桥接层白名单**（`live_caption/speaker_tracker.py`）⇒ **属 App 属地，ASR 侧不越权改**；
* 🔴 **`overlap_ratio` 即使转发出来也是 0.0** ⇒ **不要**基于它做决策（§1）。

### (d) 「≥1.5 s 取样、攒到 3 s 重算」这条用户规则，**能否改用 clean 区间累计时长**

* **先说事实：App 侧现在用的**已经是** clean 区间累计时长**，不是段时长**：
  * `live_caption/speaker_voice.py` 的 `_merge_clean_spans()` 把该 spk 的 `clean_ranges` **取并集**，
    再 `row['clean_dur_s'] = sum(b - a for a, b in out)` ⇒ **并集累计时长**；
  * `ready_to_embed()` 判 `row['dur_s'] >= need`（`dur_s = clean_dur_s`）⇒ **判据用的就是 clean 累计**；
  * `MIN_S = 1.5` / `REFINE_S = 3.0`（`speaker_voice.py:81`/`:82`）；
  * 而 `live_caption_app.py` 里还有一道**独立的**硬判据：
    `pcm.size < int(speaker_voice.MIN_S * SR)` ⇒ **按实际切出的 PCM 样本数**判 ⇒ **同样是 clean 区间时长**。
  ⇒ 🔴 **结论 (d)：这条规则**已经**在用 clean 区间累计时长**，ASR 侧**无需再改**，也**不需要**提新需求。
* 🔴 **但有一个 ASR 侧的**真实约束**要提醒 App**：
  **`clean_ranges` 的最短可用区间是 0.3 s，且每段至少要有 1 个区间**（否则 `n_clean_ranges=0`）
  ⇒ **单段的 clean 总时长可能 < 1.5 s** ⇒ App 的「等下一段」逻辑（`continue`）是对的，
  **不要**改成「用段时长凑够 1.5 s」（那会把静音/别人的声音切进来）。
* ⚠️ **一个口径提醒**：`clean_ranges` 的区间是**按段**给的（每段一次 `note_final`），
  而 `_merge_clean_spans` 会**取并集** ⇒ **同一 spk 在相邻段的区间不重叠** ⇒ 并集 ≈ 累计（无重复计数）✅。

---

## 3. 第 2 点：`spk` ID 的口径 —— **到达序编号，跨臂不可直接比**

🔴 **reviewer 的观察成立**：`asr118` 的 `B_min_clean_ratio_0.6` 臂与基线臂的**说话人 ID 整体互换**。
* **机制**：`OnlineSpeakerCluster.assign()` 是**先到先得**的在线聚类
  ⇒ **第一个被登记的段拿到 `S1`**，第二个新说话人拿到 `S2`……
  ⇒ 只要**哪一个段先被登记**变了，后续编号**全部平移/互换**。
* **实测（产物 `rows_audit.id_swap_vs_baseline`）**：
  | 臂 | clip00 | clip01 | clip02 |
  |---|---|---|---|
  | `B_min_clean_ratio_0.6` | 逐段 diff **0** | 逐段 diff **0** | 逐段 diff **32 / 46** |
  | `B_min_clean_ratio_0.4` | 逐段 diff **0** | 逐段 diff **0** | 逐段 diff **32 / 46** |
  | `B_thr_0.4` / `B_thr_0.3` / `B_min_dur_s_1.5` / `B_overlap_ratio_max_0.05` | 0 | 0 | **0** |
  * `B_min_dur_s_3.0` 全无标签 ⇒ 无 ID 可比。
  * ⇒ **只有 `min_clean_ratio` 两臂出现互换**，因为**只有它们让 clip02 的 seg0 从「无标签」变成「有标签」**
    ⇒ **第一个被登记的段从 seg1 变成 seg0** ⇒ **后续编号整体平移**。
    （实测：基线 clip02 首个有标签段 = **seg 1**；0.6/0.4 臂 = **seg 0**。）
  * 🔴 **`is_new_spk` 计数**（各臂实测）：基线 / thr 0.4 / thr 0.3 / min_dur 1.5 / overlap 0.05 = **29**；
    0.6 臂 = **30**、0.4 臂 = **31**、min_dur 3.0 臂 = **0**（全无标签）
    ⇒ **换人点只有 26 个，但 `is_new_spk` 触发 29 次** ⇒ **3 次是拆分/回切误触发**
    ⇒ **与 (b) 里「`is_new_spk` ≠ 「新说话人」」的口径一致**。
* 🔴 **对 App 的口径提醒（务必写进 STATUS）**：
  **`spk`（`S1`/`S2`/…）是「到达序编号」，不是「人的身份」**
  ⇒ **跨臂 / 跨会话 / 跨运行不可直接比较**；
  ⇒ 需要稳定身份时**必须**借助外部映射（例如 `ref_spk` 参照、或 App 侧自己的音色登记表）。
* ✅ **不受影响的部分**：**命中数按换人事件计**（`n_hit` / `recall` / `n_false_positive`）
  ⇒ 用的是**参照段 ↔ 实测段的一对一映射**（`asr105.hit_analysis`），**不依赖 ID 的绝对值**
  ⇒ 0.6 臂的召回 22/26 与基线 19/26 **可比**。

---

## 4. 本轮修掉的 1 处真缺陷（自检抓出）

🔴 `asr121_overlap_clean_diag.py` 的 `locate_bridge_payload()` 初版用「**首个含 `)` 的行就停**」
截取 `out = dict(...)` 代码块 ⇒ 而 `spk_conf=(res or {}).get('spk_conf'),` 这一行**本身含 `)`**
⇒ **只取到 2 行** ⇒ 漏掉了后面的 `clean_ranges` ⇒ 自检 `bridge_forwards_clean_ranges` **FAIL**。
⇒ **修法**：改成**括号配平扫描**（累计 `depth`，`depth ≤ 0` 才停）⇒ 自检 **7/7 PASS**。
🔴 **教训（可复用）**：**代码块提取不能用「首个 `)`」** ⇒ 必须**配平扫描**；
否则会**静默漏字段**，而自检恰好能抓住（这正是配反证的价值）。

---

## 5. 本轮对既有结论的影响（**不撤回任何已验收结论**，只加口径）

| 项 | 影响 | 处置 |
|---|---|---|
| §75「`B_overlap_ratio_max_0.05` 与基线逐段 136/136 相同」 | 🔴 **该表述须按 §1 口径读**：它**恒等于基线**，**不是**「已验证 `overlap_ratio_max` 无影响」 | ✅ **在 §76 与 STATUS「最近更新」加口径**（**不删旧行、不改旧章节**） |
| §74 / §75「`min_clean_ratio` 候选 0.6」 | **不受影响**（`min_clean_ratio` 在内核里**确实生效**，只是比值没被转发） | ✅ 结论保留 |
| §75「thr 三档相同」 | **不受影响**（`spk_conf` 的空隙解释与本轮无关） | ✅ 结论保留 |
| §75「min_dur_s=3.0 全 `async_pending`」 | **不受影响** | ✅ 结论保留 |
| `min_clean_ratio` 默认值 0.8 → 0.6 | **仍是候选**，默认值**未动** | 🟡 **等用户决定**（ASR-044 ③） |

---

## 6. 自检（产物 `asr121_overlap_clean_diag.json` → `self_check`）

| 判据 | 结果 |
|---|---|
| `overlap_ratio_replicated_is_zero` | **true** |
| `p_dom_only_single_classes`（`SINGLE_CLASSES == [1,2,3]`） | **true** |
| `bridge_does_not_forward_clean_ratio` | **true** |
| `bridge_does_not_forward_overlap_ratio` | **true** |
| `bridge_forwards_clean_ranges` | **true** |
| `rows_all_clean_ratio_none`（8 臂 × 136 段全 None） | **true** |
| `source_files_exist` | **true** |
| **`self_check_pass`** | **true**（7/7） |

🔴 **口径**：本产物是**产品级诊断**（回答「参数是否惰性」），**不是** `status_verify` 类自审守卫
（ASR-038 禁的是「给 STATUS 自身写守卫」）；本产物**不引用 STATUS 的任何字段** ⇒ 无自指。
🔴 `timing_valid=null` / `lock_probe=null` / `lock_probe_checks=null`
（**本轮未跑推理、未占设备、未申请机器锁** ⇒ 这三个字段**按纪律写 null**，不是漏填）。
