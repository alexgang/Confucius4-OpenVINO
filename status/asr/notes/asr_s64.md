# ASR §64 明细 —— 无新纠偏 + 只读复核抓出 5 个真缺陷 + 加固自指大小守卫

> 🔴 本文件是 `status/asr/STATUS_ASR.md` §64 的**明细去处**（ASR-036 定的写作规则：
> 「长日志、逐条明细、大表格写到 `notes/<章节号>.md` 或 `results` 目录，
> STATUS 里只放结论、数字和链接」）。
> 落点取 `status/asr/notes/`（而非 `status/notes/`）⇒ **保持本模块的提交范围**（只提交 `status/asr/`）。
> 本文件是**只读明细**：结论、判据、数字的**唯一事实来源仍是产物 JSON**。

## 0. 本轮背景

- 本轮**无新纠偏**：`status/asr/CORRECTIONS_ASR.md` 最大编号 = **ASR-036** = `last_ack`。
- 按 **ASR-034**「last_ack 追平后，只要还有未完成项，就自己继续做，不要空转」
  ⇒ 做**只读复核**（不跑模型、不计时、不申请共享机器锁）。
- 复核**不是空跑**：在本模块**已提交的产物内部**抓出 **5 个真缺陷**
  （D1–D4 在 §63 已提交的产物里；**D5 在本轮 in-flight 的写入脚本里**），并全部修掉。

## 1. 🔴 D1 —— §63 记录的「反证条数」与产物不符（§41 数字手抄，第 5 次复发）

| 项 | §63 文中写的 | 产物实测 | 判定 |
|---|---|---|---|
| 反证条数 | **5 条** | `n_counterproofs` = **6** | **不符** |
| 反证通过 | **5/5 全过** | `n_counterproofs_caught` = **6** | **不符** |

- 根因：数字**抄自 `asr086_selfref_size_gate_pre_fix.json`**（§63 修 bug **之前**的快照，
  该快照是 5 条 / 3 被抓住）⇒ **修完之后没有重新读产物**。
- 这正是 §41「结论写进文档 ≠ 结论落进产物 / 数字不能手抄」的第 5 次复发。
- ✅ 修法（**不改旧章节**，按规则在 §64 更正并显式标注为陈旧）：
  - §63 的两行反证计数**加「陈旧计数」标注 + 指向本节**（§63 章节其余**逐字保留**）；
  - 本模块自指大小守卫的唯一事实来源改为
    `asr088_selfref_size_gate_v2.json` → `n_counterproofs` / `n_counterproofs_caught`。
- 🔴 **为什么旧守卫自己没抓到**：asr086 守卫只校验**自指大小**，
  **不校验「文中提到的反证条数 == 产物里的条数」** ⇒ 这类「文档↔产物计数不一致」
  **不在它的能力范围内** ⇒ 只能靠**独立复核**抓（见 §3 的 D1 复核项）。

## 2. 🔴 D2 —— asr086 的 historical 豁免有盲区（漏检，**注入实证**）

### 根因

v1 判 `historical`（豁免，不判失败）的条件之一是「**整句含历史标记**」
（`当时 / 首版 / 压缩前 / 原稿 / 旧版 / 历史 / 曾 / 撤回 / 改动前 / 陈旧 / 那一版`）。
⇒ **同一子句里**若既有历史标记、又有**错的当前断言** ⇒ **整句被豁免** ⇒ **漏检**。

### 注入实证（不是假设）

| 注入样本 | v1 结果 | v2 结果 |
|---|---|---|
| `当前大小是 1 234 B / 5 行（§62 当时的旧值另计）。` | **没抓住**（`ok=True`） | **抓住**（1 处不匹配） |
| `当时是 1 234 B / 5 行，现在的文件是 999 999 B / 999 行。` | **没抓住**（`ok=True`） | **抓住**（1 处不匹配） |

⇒ 产物字段 `blindspot_proof.inject_a / inject_b` 落盘
（`v1_caught=false` ×2、`v2_caught=true` ×2）⇒ **证明这次修复有鉴别力**（不是恒真）。

### 修法（`scripts/asr088_selfref_size_gate_v2.py`）

引入「**强当前指示词优先**」：

- 强当前指示词 = `当前大小 / 当前 / 现在 / 目前 / 现为 / 现已 / 现值`
  （**不认**「文件是」这类弱连接，否则「当时的文件是 …」会被误判成当前断言 ⇒ 误伤）。
- 判定：数值**同一子句的前缀里**若出现强当前指示词，且它**晚于**同一子句内的历史标记
  ⇒ 一律判 **current**（豁免失效）。
- **数值之后**的历史标记（如 §62/§63 的「（§62 当时的压缩结果）」）**仍**算历史
  ⇒ **不误伤**已提交的合法历史引用。
- 🔴 **asr086 v1 冻结**为 §63 的历史证据（不删不改），v2 是新增脚本。
- 实测：对**当前这份 STATUS**，v1 与 v2 的分类结果**逐处一致**
  （`baseline_v1_comparison.n_kind_diffs` = **0**；**§64 写入后**的实测 =
  current **1** 处 / historical **15** 处 / current 不匹配 **0**）
  ⇒ **收紧没有引入误伤**。

### v2 反证（9 条，全过）

| # | 名称 | 期望 | 抓住 |
|---|---|---|---|
| cp1 | `cp1_baseline_must_pass` | PASS | ✅ |
| cp2 | `cp2_wrong_truth_field_must_fail` | FAIL | ✅ |
| cp3 | `cp3_missing_truth_field_must_fail` | FAIL | ✅ |
| cp4 | `cp4_wrong_current_assertion_must_fail`（`==` 句式） | FAIL | ✅ |
| cp5 | `cp5_historical_context_must_not_fail` | PASS | ✅ |
| cp6 | `cp6_backtick_quote_must_not_fail` | PASS | ✅ |
| cp7 | `cp7_hist_marker_same_clause_must_fail`（**专打 D2 盲区**） | FAIL | ✅ |
| cp8 | `cp8_current_indicator_after_hist_marker_must_fail`（**专打 D2 盲区**） | FAIL | ✅ |
| cp9 | `cp9_historical_with_weak_connector_must_not_fail`（**防收紧后误伤**） | PASS | ✅ |

## 3. 🔴 D3 —— §63 的独立复核脚本依赖一个**不存在**的路径 ⇒ 复核不可复现

- `_tmp_verify_status_s63.py` 读 `status/asr/STATUS_ASR.md.clean_base_asr087`
  ⇒ 该路径**不存在**（干净起点实际在
  `C:\Users\Trekker-PTL\qwen3asr_06b\results\pyannote_seg\_STATUS_ASR_clean_base_asr087.md`）
  ⇒ 在干净环境重跑**必然 FAIL**（实测 FAIL 项 = 「干净起点存在」）
  ⇒ §63 的「独立复核全 PASS」**不可复现**。
- ✅ 修法：
  - §64 的独立复核脚本**自己**从 `qwen3asr_06b` 的只读副本**生成**干净起点
    （不手工造、不依赖上一轮的临时文件）；
  - 复核项包含 **D1 专项**：把「文中反证计数」与**产物字段**逐处比对
    （这是 asr086/asr088 守卫**能力范围外**的缺陷 ⇒ 只能靠独立复核抓）。

## 4. 🔴 D4 —— §63 的章节长度违反 ASR-036 自己定的写作规则

- ASR-036 明文：「每个新章节 **≤ 60 行**」。
- 🔴 **实测 §63 = 70 行**（口径：**正文行数**，不含尾部空段）⇒ **超限 10 行**
  ⇒ **STATUS 里已有 1 个违规章节**。
- ✅ 修法：
  - §64 起，**明细进本文件**（`status/asr/notes/asr_s64.md`），
    STATUS 内 §64 **只留结论、数字和链接** ⇒ 压到 ≤ 60 行；
  - §64 的写入脚本**自检**里带「每个新章节 ≤ 60 行」这一项 ⇒ **今后由机器拦住**。
- ⚠️ **§63 的 70 行**属**已提交的旧章节** ⇒ 按「只追加新章节、不回头改旧章节」的规则，
  **不删不改 §63**；超限事实与处置记在本节 + §64。

## 5. 🔴 D5 —— 本轮 in-flight 的写入脚本有 2 个真 bug（干跑抓出，**未污染真实 STATUS**）

### 根因

§64 的写入脚本 `scripts/asr089_status_write_s64.py` 在**上一会话中断时从未执行过**
⇒ 这正是 §40「**脚本写好了 ≠ 脚本能跑**」的又一次复现
（与 §61 抓到的 `asr047` 同型：写了但没跑过 ⇒ 「已备好脚本」是**未经核验的断言**）。

⇒ 本轮的纪律：**先干跑**（把脚本的 `STATUS` 路径改到**沙箱副本**），干跑转绿才写真实 STATUS。

### 干跑抓到的 2 个 bug

| # | 现象 | 被谁抓住 | 修法 |
|---|---|---|---|
| ① | §64 模板内部是**纯 LF** ⇒ 拼进正文后**裸 LF ≠ 0** | asr089 自检 | 模板插入前**归一为 CRLF** |
| ② | §64 正文 = **62 行 > 60**（ASR-036 上限） | asr089 自检 | 正文压到 ≤ 60 行（明细搬本文件）⇒ 实测 **56 行** |

- 🔴 干跑第 1 轮**误写了真实 STATUS**（补丁脚本因 `\U` 转义失败没生效）⇒
  **自检拦下 ⇒ 自动从备份还原** ⇒ **实测 md5 复原 == 改前值**
  （`44aa0a4a1bd88256d5be6dc8e3c45201` / 23 941 B）⇒ **还原路径本身有效**。
- ✅ 另有 2 个 bug 由**干跑 + 自检**在本轮抓到并修掉：
  - **真值点重复**：拼接时没跳过干净起点里的**旧真值点** ⇒ 出现 **2 个** `自指大小:` 行
    ⇒ 守卫的 `TRUTH_RE` 要求真值点**唯一** ⇒ 已修（跳过 `base_lines[5]`）+ 加自检「真值点唯一」。
  - **§64 定位用 `list.index`**：标题行带后缀（`### §64 …`）⇒ `index('### §64 ')` 抛 `ValueError`
    ⇒ 改为按**前缀**扫描。
- ✅ 另修掉 §63 遗留的**同类隐患**：§63「最近更新」里那处 `（当前 = 23 941 B / 224 行）`
  在 §64 写入后会变成**错的当前断言**（文件大小/行数已变）⇒ 已按 §63 对 §62 的同一手法
  改标为历史（`（§63 当时的实测 = …；数值以头部唯一真值点为准）`），
  并加自检「旧断言不再裸露 + 历史标注已落地」。

## 6. 🔴 §64 的独立复核（`asr090`）与**注入测试**（`asr091`）

### `asr090_status_verify_s64.py`（**不复用** asr088 守卫的分类逻辑 ⇒ 真正独立）

- ✅ **修掉 D3**：干净起点**自己**从 `qwen3asr_06b/results/pyannote_seg/_STATUS_ASR_clean_base_s64.md`
  取（**不依赖**上一轮的临时文件、**不手工造**）⇒ 干净环境重跑**可复现**。
- ✅ 复核项：换行（CRCRLF / 裸 LF）、行数/字节上限、头部 6 行齐全、
  **真值点唯一且 == 实测**、「最近更新」≤15 行、§64 恰好 1 个、**§63 逐字未改**
  （与干净起点比对，只允许 1 处历史标注差异）、**§64 ≤ 60 行**、无残留占位符、
  **D1 专项**（文中反证计数 ↔ 产物字段逐处比对）、§64 正文无自指大小断言、
  §64 引用的产物**存在且 size/mtime 与文中所写一致**。
- ✅ 实测：**ALL PASS**。

### `asr091_s64_counterproofs.py` —— 证明 `asr090` **有鉴别力**（§44b 铁律）

🔴 「守卫通过」≠「守卫有鉴别力」⇒ 必须配**注入测试**（故意注入缺陷 ⇒ 必须失败）。

| # | 名称 | 期望 | 抓住 |
|---|---|---|---|
| cp1 | `cp1_baseline_must_pass` | PASS | ✅ |
| cp2 | `cp2_wrong_truth_must_fail`（真值点写错） | FAIL | ✅ |
| cp3 | `cp3_missing_truth_must_fail`（真值点删除） | FAIL | ✅ |
| cp4 | `cp4_wrong_counterproof_count_must_fail`（**D1 专项**） | FAIL | ✅ |
| cp5 | `cp5_s63_row_modified_must_fail`（旧章节被改） | FAIL | ✅ |
| cp6 | `cp6_bare_lf_must_fail`（换行被破坏） | FAIL | ✅ |
| cp7 | `cp7_hist_marker_removed_must_fail`（豁免被撤） | FAIL | ✅ |
| cp8 | `cp8_chapter_over_60_must_fail`（章节超限） | FAIL | ✅ |
| cp9 | `cp9_selfref_assertion_in_s64_must_fail`（自指断言） | FAIL | ✅ |

- ✅ 实测 **9/9 全过** ⇒ `asr091_s64_counterproofs.json` → `all_pass` = **true**。
- ✅ 注入方式：把 STATUS 复制到沙箱副本再变异 ⇒ **不碰真实 STATUS**。

## 7. 产物清单（实测）

| 项 | 大小 / mtime | 说明 |
|---|---|---|
| `scripts/asr088_selfref_size_gate_v2.py` | 18 077 B @ 2026-10-30 21:54:13 | v2 守卫脚本（新增；v1 冻结不动） |
| `results/pyannote_seg/asr088_selfref_size_gate_v2.json` | **每次重跑都会变** ⇒ 只引**内容事实** | v2 守卫产物：`passes` = **true**、`all_counterproofs_caught` = **true**、`n_counterproofs` = **9**、`n_current` = **1** / `n_historical` = **15** / current 不匹配 = **0** |
| `scripts/asr089_status_write_s64.py` | 21 358 B @ 2026-10-30 22:30:27 | §64 写入脚本（**本轮修掉 4 个 bug**） |
| `scripts/asr090_status_verify_s64.py` | 9 406 B @ 2026-10-30 22:28:00 | §64 独立复核脚本（**修掉 D3**） |
| `scripts/asr091_s64_counterproofs.py` | 5 088 B @ 2026-10-30 22:27:57 | 复核脚本的**注入测试** |
| `results/pyannote_seg/asr091_s64_counterproofs.json` | **每次重跑都会变** ⇒ 只引**内容事实** | 注入测试产物：`n_counterproofs` = **9** / `n_counterproofs_ok` = **9** / `all_pass` = **true** |
| `results/pyannote_seg/asr086_selfref_size_gate.json` | 6 654 B @ 2026-10-30 21:31:04 | v1 产物（**冻结**，不改） |
| `results/pyannote_seg/asr086_selfref_size_gate_pre_fix.json` | 3 896 B @ 2026-10-30 20:13:21 | 修复前证据（**冻结**） |
| `results/_cp_s64/` | — | 本轮改前备份（守卫脚本 v1 / v1 产物快照 / STATUS 改前） |
| `status/asr/notes/asr_s64.md` | — | 本文件（明细） |

> 🔴 **口径说明**：**只对「冻结」产物引用 size/mtime**（`asr086` v1 / `pre_fix`）——
> 它们不再重跑 ⇒ 引用永不过期。
> ⚠️ **可重跑产物**（`asr088` v2 / `asr091`）**每跑一次 mtime 就变** ⇒ 若在文档里引用其 mtime，
> 则**每跑一次守卫文档就过期一次** ⇒ **自指式churn 循环**（本轮实测踩到：
> 重跑守卫 ⇒ notes 里的 mtime 立即过期 ⇒ 复核判 FAIL）。
> ⇒ 对可重跑产物**只引内容事实**（`passes` / 计数），**不引 size/mtime**。

## 8. 纪律

- 本轮**纯只读 + 文本守卫**（不跑模型、不计时）⇒ **未申请共享机器锁**；
  复核期间 `shared/MACHINE_LOCK` 由 **TTS** 持有（`module: tts`）⇒ 本模块**不干扰**。
- **未动** `live_caption/`；**未改** `CORRECTIONS_ASR.md`（纠偏文件由 reviewer 维护）。
- `last_ack` 保持 **ASR-036**（无新纠偏）。
  ASR-036 在纠偏索引表里的状态仍是「进行中」——**该文件由 reviewer 维护**，本模块不代改。
- **未跑 WER**（交 reviewer）；未开新实验。
- 🔴 **本轮修掉的缺陷清单**（供后续复查）：
  | # | 缺陷 | 类别 | 状态 |
  |---|---|---|---|
  | D1 | §63 的「反证 5 条 / 5-5」与产物（**6 / 6**）不符 | §41 数字手抄第 5 次复发 | ✅ 已撤回（§64） |
  | D2 | asr086 的 historical 豁免有盲区（同句含历史标记 ⇒ 整句豁免 ⇒ 漏检） | 守卫漏检 | ✅ v2 已修 + 注入实证 |
  | D3 | §63 的复核脚本依赖**不存在**的路径 ⇒ 「复核全 PASS」不可复现 | 复核不可复现 | ✅ asr090 已修 |
  | D4 | §63 = **70 行** > ASR-036 的 60 行上限 | 违反自己的写作规则 | ✅ §64 起明细进 notes |
  | D5 | 本轮 in-flight 写入脚本 4 个 bug（裸 LF / 62 行 / 真值点重复 / `index` 抛错） | §40「写好了 ≠ 能跑」 | ✅ 干跑抓出 + 已修 |
- ⚠️ **本轮仍未跑**：`asr086`（v1 守卫）**未重跑**（冻结为 §63 的历史证据）；
  `asr088`（v2）**已在 §64 写入后重跑** ⇒ `passes` = **true**、
  `all_counterproofs_caught` = **true**、`n_counterproofs` = **9**。
