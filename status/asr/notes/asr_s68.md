# §68 明细 —— 无新纠偏（last_ack 保持 ASR-036）+ 复核抓出 3 类新真缺陷

> 🔴 **本轮无新纠偏**（`status/asr/CORRECTIONS_ASR.md` **12 493 B @ 2026-10-30 15:44:31**、
> md5 `ae967731dd2e2dbf49fb7690239b30bb`，与 §63/§64/§65/§66/§67 **逐字节一致**；
> 全文最大编号 = **ASR-036** = `last_ack`；全仓扫 `ASR-0(3[7-9]|[4-9][0-9])` 命中 **0**）
> ⇒ 按 **ASR-034**「last_ack 追平后继续做未完成项」⇒ 继续做**只读复核**。
>
> 🔴 本轮**纯只读 + 文本守卫**：不跑任何模型推理、不计时 ⇒ **未申请共享机器锁**
> （检查时 `shared/MACHINE_LOCK` 不存在、`shared/*.tmp` 残留 **0**、`GIT_FREEZE` 不存在）。

---

## 1. 复核范围与方法

| 项 | 内容 |
|---|---|
| 复核对象 | §67 **已交付**的产物内部（`status/asr/STATUS_ASR.md`、`status/asr/notes/asr_s6*.md`、§67 的 3 个脚本 + 产物） |
| 复核手段 | ① 逐字节读 STATUS 头部；② 扫 notes 里的「脚本 + size/mtime」引用；③ 重跑守卫拿实测值与文档比对；④ 干跑 §68 写入脚本（**不写真实文件**） |
| 复核脚本 | `asr099_status_gate_v4.py`（v4 守卫，扩到 **22** 条判据）/ `asr100_status_verify_s67.py`（独立复核，扩到 **28** 条判据）/ `asr102_fix_notes_script_refs.py`（notes 引用修法）/ `asr103_status_write_s68.py`（§68 写入） |
| 独立复核 | §43 铁律：`asr100` **不复用** `asr103` 的自检，也**不复用** `asr099` 的实现 ⇒ 路径解析**独立重新实现**一遍 |

**复核不是空跑**：在 §67 已交付的产物内部抓出 **3 类**新真缺陷（D4–D6）。

---

## 2. D4 —— 头部「已压缩:」行**重复**（§67 写入脚本自身引入）

### 2.1 实测

- STATUS 头部**有 2 行**以 `已压缩:` 开头（第 **5** / **6** 行），内容**逐字相同**。
- 实测命令：`grep -n "^已压缩:" status/asr/STATUS_ASR.md` ⇒ 命中 **2** 行。

### 2.2 根因

§67 的写入脚本 `asr101_status_write_s67.py`：

- `HEADER` 模板**本身含**一行「已压缩: …」；
- 脚本随后又 `out.append(lines[i_comp])`（把原文那行**再追加一次**）。

⇒ 写了两遍。§67 的**自检只查真值点唯一性**（`自指大小:`），**没查头部其它关键行**
⇒ **漏检**（自检覆盖面不足，§30「判据必须有鉴别力」）。

### 2.3 修法

- `asr103_status_write_s68.py`：头部重建时**只保留一行**「已压缩:」，且内容取**原文逐字**
  （`comp_line = lines[i_comp]`）⇒ 模板与原文**不会漂移**。
- 新增守卫判据：
  - `asr099` **G11**：头部 `last_ack:` / `已压缩:` / `自指大小:` 各**恰好 1 行**；
  - `asr100` **V15**：同上（**独立实现**）。
- 写入脚本**自检**也加同一条（`asr103` 自检段）。

### 2.4 反证

- `asr099` **cp9_dup_header_line_must_fail**：把「已压缩:」行复制一份 ⇒ **必须 FAIL** ⇒ 实测 **FAIL**（抓住）。
- `asr100` **cp10_dup_header_line_must_fail**：同上 ⇒ 实测 **FAIL**（抓住）。

---

## 3. D5 —— 「扫描产物」是**动态量** ⇒ STATUS 写死 ⇒ 必然漂移

### 3.1 实测

- §67 表格写「扫描产物 **127** 个 JSON」（两处：§66 章节表 + §67 章节表）。
- 本轮重跑 `asr096_legacy_consistency_gate.py` ⇒ 实测 `n_json_scanned` = **131**。
- **连跑 2 次稳定为 131**（⇒ 不是抖动，是**真实漂移**）。

### 3.2 根因

`n_json_scanned` 统计 `results/pyannote_seg/*.json` 的**文件数**
⇒ **每新增一个产物就 +1** ⇒ 它是**动态量**。

⇒ 「§41 数字不得手抄」的第 2 层：**来源本身会变**。
只做「手抄检查」不够 —— 抄得对也会过期。

### 3.3 修法

- 新增守卫判据：
  - `asr099` **G12**：STATUS「扫描产物」数值 **必须 == `asr096.n_json_scanned`**；
  - `asr100` **V16**：同上（**独立实现**）。
- `asr103` 每次写入都**从产物读**该值（`@@NJSON@@` 令牌）⇒ 不再手抄。
- `asr103` **自检**也比对一次（写入时就拦住）。

### 3.4 反证

- `asr099` **cp10_stale_dynamic_number_must_fail**：把 STATUS 的值改成 `999` ⇒ **必须 FAIL** ⇒ 实测 **FAIL**。
- `asr100` **cp11_stale_dynamic_number_must_fail**：同上 ⇒ 实测 **FAIL**。

---

## 4. D6 —— notes 引「可改脚本」的 size/mtime ⇒ **无限自指 churn**（§60 铁律的**根治**）

### 4.1 实测

`status/asr/notes/asr_s6*.md` 中「脚本 + size/mtime」的引用共 **10** 处：

| notes | 脚本 |
|---|---|
| `asr_s64.md` | `asr088_selfref_size_gate_v2.py`、`asr089_status_write_s64.py` |
| `asr_s65.md` | `asr092_status_write_s65.py`、`asr093_status_gate_v3.py`、`asr094_status_verify_s65.py` |
| `asr_s66.md` | `asr095_fix_legacy_timing_and_clips_v2.py`、`asr096_legacy_consistency_gate.py`、`asr097_status_write_s66.py` |
| `asr_s67.md` | `asr099_status_gate_v4.py`、`asr101_status_write_s67.py` |

本轮改 `asr099` / `asr100` / `asr101` 后 ⇒ 这些引用**立刻全部过期**
⇒ 只能靠「再改一次 notes」同步 ⇒ 而改 notes 又要动 size/mtime ⇒ **无限循环**。

### 4.2 根因（§66 判据 V17 的盲区）

§66 落成的判据 **V17**（notes 不得引用**可重跑产物**的 size/mtime）**只堵了「产物」**，
**没堵「脚本」** ⇒ 判据**有盲区**（§44b「守卫通过 ≠ 守卫有鉴别力」）。

§60 铁律写的是「**只对「冻结」对象引 size/mtime**」，
但此前**只落实了「产物」侧**，**脚本侧**一直漏 ⇒ 这是 §60 的**第 3 次复发**（§65 D6、§66 V17、本轮 D6）。

### 4.3 修法（**根治**，不是又一次同步）

- **notes 里「脚本」一律只引**内容事实**（判据条数 / 反证条数 / 用途）；
  **size/mtime 只留给「冻结」对象**（已归档不再改的 json 产物、`CORRECTIONS_ASR.md`）。
- 脚本 `asr102_fix_notes_script_refs.py`：**干跑 → 转绿 → 才写真实 notes**（§40 纪律）。
  - 每条替换**必须命中或已是修好的样子**（§64 纪律）⇒ 不会静默漏改；
  - 干跑的自检在**改后文本**上做（🔴 第一次写时错在「读磁盘旧内容」⇒ 干跑必假 FAIL，已修）。
- 新增守卫判据 **V17'**（`asr100`）：notes **不得**引**可改脚本**的 size/mtime。
- ⚠️ **保留历史证据行**：notes 里含「**过期值 / 不符 / 原写 / D6 实证 / D6 修正**」的行是
  **缺陷证据**（记录「当时写错了」）⇒ **不改**（删掉就丢证据）⇒ 守卫给**窄豁免**。

### 4.4 反证

- `asr100` **cp12_notes_script_sizemtime_must_fail**：
  在**沙箱 notes 目录**塞一条违规引用 ⇒ gate 用 `notes_dir` 扫到 ⇒ **必须 FAIL** ⇒ 实测 **FAIL**。
  - 为此 `asr100.gate()` 加了 `notes_dir` 参数（注入测试**自带 notes 沙箱** ⇒ **不污染真实 notes**，§49）。

---

## 4.5 D6 的连带发现 —— **历史专属守卫**随章节轮换而**老化**（同一根因）

修 D6 时发现：**历史专属守卫**（§65 的 `asr093`、§66 的 `asr098`）在章节轮换后**必然 FAIL**
⇒ 实测 `asr093` FAIL **1** 条（`有 §65 章节`）、`asr098` FAIL **4** 条。

| 守卫 | 老化判据 | 根因 | 修法 |
|---|---|---|---|
| `asr093`（§65 专属） | G8「有 §65 章节」 | §65 已按 ASR-036 移回归档 ⇒ 正文**不再有** §65 | 改为 G8「**§68 在正文存在**」+ G8b「§65 **已在归档**里」；反证 cp8 改为「移除 **§68**」 |
| `asr098`（§66 专属） | V8「§64/§65 章节恰好 1 个」 | 同上 | 改为「**已移回归档且未改数值/结论**」（行数相同 + 差异行必须**都是字段路径修法行**，§67 的 D1 修法**按设计**改了归档里的路径）；反证 cp8 改为「篡改 **§68**」 |

⚠️ **同类问题的通用教训**：**判据绑定具体章节号 ⇒ 章节一滚动就必然失效**
⇒ **「历史专属守卫」必须随轮换更新**，否则它们会从「保护网」变成「永久假 FAIL 噪声」
⇒ 假 FAIL 的真正危害不是「FAIL」，而是**让人习惯性忽略 FAIL**（§44b 的反面）。

⚠️ **V8 判据的第二个坑**：归档里章节标题是 `## §65 `（**2** 个 `#`），备份里是 `### §65 `（**3** 个 `#`）
⇒ 逐字比对前**必须归一前缀**，否则**必然不等**（本次实测抓到）。

---

## 5. 守卫判据表（实测）

| 守卫 | 判据条数 | 注入反证 | 产物 |
|---|---|---|---|
| `asr099` v4 | **22**（G1–G12） | **10/10** 全过 | `asr099_status_gate_v4.json` → `n_checks` = 22；`asr099_status_gate_v4_inject.json` → `n_counterproofs` = 10 / `n_counterproofs_caught` = 10 |
| `asr100` 独立复核 | **28**（V1–V17） | **12/12** 全过 | `asr100_status_verify_s67.json` → `n_checks` = 28；`asr100_status_verify_s67_inject.json` → `n_counterproofs` = 12 / `n_counterproofs_caught` = 12 |
| `asr096` 遗留一致性 | **9** | — | `asr096_legacy_consistency_gate.json` → `status` = `PASS` / `n_json_scanned` = **131** |

### 新增反证一览

| 反证 | 守卫 | 注入的缺陷 | 实测 |
|---|---|---|---|
| cp9_dup_header_line | `asr099` | 头部「已压缩:」行重复 | **FAIL（抓住）** |
| cp10_stale_dynamic_number | `asr099` | 动态数值漂移 | **FAIL（抓住）** |
| cp10_dup_header_line | `asr100` | 头部「已压缩:」行重复 | **FAIL（抓住）** |
| cp11_stale_dynamic_number | `asr100` | 动态数值漂移 | **FAIL（抓住）** |
| cp12_notes_script_sizemtime | `asr100` | notes 引可改脚本的 size/mtime | **FAIL（抓住）** |

---

## 6. §68 写入脚本干跑抓到的自身 bug

`asr103_status_write_s68.py` **第一次干跑就 FAIL**，抓到 **2 个**自身 bug：

| # | bug | 根因 | 修法 |
|---|---|---|---|
| 1 | 真值点字节数对不上（**34 483** vs 实测 **34 746**） | 真值点在 **LF 模板**上迭代，之后才转 CRLF ⇒ 字节数被 CRLF 转换改变 | **先统一成 CRLF 模板**，再在 CRLF 形态上做不动点迭代 |
| 2 | 「最近章节」节数 = **4**（应 3） | 只把 §65 **写进归档**，却**没从正文删掉** §65 段 ⇒ 章节数变 4 | 移回归档时**同步**从正文删除（全文已在归档 ⇒ 不丢内容） |

⇒ **干跑 → 转绿 → 才写真实 STATUS**（§40 / §64 纪律）纪律再次生效。

---

## 7. 产物清单

| 文件 | 说明 |
|---|---|
| `scripts/asr099_status_gate_v4.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实**：v4 守卫（判据 **22** 条 + 反证 **10** 条） |
| `scripts/asr100_status_verify_s67.py` | 🔴 **不引 size/mtime**（§68 D6 + §56② 自指 churn）⇒ 只引**内容事实**：独立复核（判据 **28** 条 + 反证 **12** 条） |
| `scripts/asr102_fix_notes_script_refs.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实**：notes 脚本引用修法（D6 根治，干跑→转绿→才写真实） |
| `scripts/asr103_status_write_s68.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实**：§68 STATUS 写入脚本（干跑→转绿→才写真实） |
| `scripts/asr101_status_write_s67.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实**：§67 写入脚本（**本轮修掉 D4 根因**） |
| `scripts/asr093_status_gate_v3.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实**：v3 守卫（**本轮修掉 G8 老化** + G1 与 D6 同步） |
| `scripts/asr098_status_verify_s66.py` | 🔴 **不引 size/mtime**（§68 D6 + §55 自指 churn）⇒ 只引**内容事实**：§66 独立复核（**本轮修掉 V8 老化** + V11/V12/V14 与 D6 同步） |
| `results/pyannote_seg/asr099_status_gate_v4.json` | 每次重跑都会变 ⇒ **只引内容事实** | `status` = `PASS` / `n_checks` = **22** |
| `results/pyannote_seg/asr099_status_gate_v4_inject.json` | 每次重跑都会变 ⇒ **只引内容事实** | `n_counterproofs` = **10** / caught = **10** |
| `results/pyannote_seg/asr100_status_verify_s67.json` | 每次重跑都会变 ⇒ **只引内容事实** | `status` = `PASS` / `n_checks` = **28** |
| `results/pyannote_seg/asr100_status_verify_s67_inject.json` | 每次重跑都会变 ⇒ **只引内容事实** | `n_counterproofs` = **12** / caught = **12** |
| `results/pyannote_seg/asr096_legacy_consistency_gate.json` | 每次重跑都会变 ⇒ **只引内容事实** | `n_json_scanned` = **131** |
| `results/pyannote_seg/_bk_s68/` | 沙箱 | 改前备份 + 干跑副本 + 归档干跑副本 |

---

## 8. 纪律

- 本轮**纯只读 + 文本守卫**（不跑任何模型推理、不计时）⇒ **未申请共享机器锁**。
- 🔴 **未动 `live_caption/`**；🔴 **未改 `CORRECTIONS_ASR.md`**（reviewer 维护）；`last_ack` 保持 **ASR-036**。
- 🔴 **未覆盖已交付产物**；⚠️ **WER 未跑**（交 reviewer）；**未开新实验**；**未打包**。
- ✅ STATUS「最近章节」仍为 **3** 节（§66 / §67 / §68），§65 全文**移回归档**（只追加，§46）。
