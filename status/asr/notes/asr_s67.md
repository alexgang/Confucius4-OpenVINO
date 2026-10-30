# ASR §67 明细 —— 无新纠偏 + 只读复核抓出 3 类新真缺陷 + 加装 `asr099` v4 守卫

> 🔴 **本轮无新纠偏**（`CORRECTIONS_ASR.md` **12 493 B @ 2026-10-30 15:44:31**、
> md5 `ae967731dd2e2dbf49fb7690239b30bb`，与 §63/§64/§65/§66 **四轮逐字节一致**；
> 文件内最大编号 = **ASR-036** = `last_ack`；全仓扫 `ASR-0(3[7-9]|[4-9][0-9])` 命中 **0**）。
> ⇒ 按 **ASR-034**「last_ack 追平后只要还有未完成项就继续做，不要空转」⇒ 做**只读复核**。
>
> 🔴 本轮**纯只读 + 文本守卫**（不跑任何模型推理、不计时）⇒ **未申请共享机器锁**。

---

## 1. 复核范围与方法

只读脚本（临时，均在 git 仓库外，跑完已清理）：

| 脚本 | 作用 |
|---|---|
| `_tmp_check_fieldpaths.py` | 逐条核对「关键数字」表标注的字段路径是否存在、取值是否一致 |
| `_tmp_scan_paths.py` | 扫 STATUS **全文**所有 `产物 → 字段路径` 引用 |
| `_tmp_full_scan.py` | 全文引用清单 + 各产物顶层字段清单 |
| `_tmp_strict_recon.py` | 表格每个数字 ↔ 产物字段的严格对账 |

⇒ 复核**不是空跑**：在本模块**已提交的产物内部**抓出 **3 类**新真缺陷（D1–D3）。

---

## 2. 🔴 D1 —— 「关键数字」表的字段路径**不可解析**

### 2.1 实测

`asr099` v4 守卫（修好后）实测：STATUS 全文 `产物 → 字段路径` 引用 **27 条**，
其中**缺陷描述豁免 1 条**，**缺陷 0 条**；修复前实测**缺陷 11 条**：

| # | 位置 | 原文路径 | 问题 | 修后路径 |
|---|---|---|---|---|
| 1 | 「关键数字」表 · 换人点 F1 | `switch_points_vs_pseudo_truth.tol_0p5s.f1` / `tol_3p2s.f1` | **路径不存在**（漏了 `per_arm_vs_pseudo_truth.A_fp16.` 前缀） | `per_arm_vs_pseudo_truth.A_fp16.switch_points_vs_pseudo_truth.tol_0p5s.f1` / `...tol_3p2s.f1` |
| 2 | 「关键数字」表 · 嵌入墙钟 | `embed_wall_s` | **路径不存在**（实际在 `arms.<arm>.` 下） | `arms.embed_dynamic.embed_wall_s` / `arms.embed_range_2048.embed_wall_s` |
| 3 | 「关键数字」表 · 向量一致性 | `consistency_vs_dynamic.embed_range_2048` | **指向对象**而非数值 | `consistency_vs_dynamic.embed_range_2048.n` / `.cos_min` / `per_segment[].rel_max_abs_diff` |
| 4 | 「关键数字」表 · 生产段帧数 | `offline_segment_length` | **指向对象** | `offline_segment_length.prod_frame_upper_bound` / `.app_MAX_SEG_SEC` / `.landed_EMBED_RANGE_HI` |
| 5 | 「关键数字」表 · FP16 保真 | `experiments.ov_fp16_vs_torch_fp32` | **指向对象** | `experiments.ov_fp16_vs_torch_fp32.cos` / `.rel_max_abs_diff` |
| 6 | §64/§65 表格 · 盲区实证 | `blindspot_proof` | **指向对象** | `blindspot_proof.inject_a.v1_caught` / `.inject_a.v2_caught` / `.inject_b.v1_caught` / `.inject_b.v2_caught` |
| 7 | 头部第 4 行 | `asr096_legacy_consistency_gate.json` → `legacy_no_lock_probe` | **指向对象** | 同文件 → `legacy_no_lock_probe.count` |
| 8 | §65 表格 · v3 反证 | `asr093_status_gate_v3.json` → `n_counterproofs` | **路径不存在**（见 D2） | 同文件 → `counterproof_evidence.n_counterproofs` / `.n_counterproofs_caught` |
| 9 | §66 表格 · 扫描产物 | 同上 → `checks` | **跨产物误指**（`checks` 在基线产物，`n_checks` 才是计数） | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（见 D3） |
| 10 | §66 表格 · ②类历史遗留 | 同上 → `legacy_no_lock_probe.count` | **跨产物误指**（「同上」指到了 inject 产物） | 显式指 `asr096_legacy_consistency_gate.json` → `legacy_no_lock_probe.count` |
| 11 | §66 表格 · V17 新增判据 | 同上 → `checks` | **跨产物误指**（同上） | 显式指 `asr098_status_verify_s66.json` → `checks` |

### 2.2 根因

§62 压缩 STATUS 时，把「来源产物 / 字段」列**手工简化**过（省掉中间层级）。
⇒ **数值本身是对的**（实测全部一致），但**路径指不到那个值**。

🔴 **这是 §41「数字手抄」的第 7 次复发，但性质变了**：前 6 次是**数值抄错**，
这次是**路径写错**（数值对、指针错）⇒ **更隐蔽**：只看数字完全看不出问题。

### 2.3 为什么 §66 的独立复核没抓到

`asr098_status_verify_s66.py` 的 **V13** 只查「STATUS 里每个**长小数**能否在产物/notes 里
**逐字找到**」⇒ **路径错但数值对** ⇒ 天然漏检 ⇒ **判据无鉴别力**。

---

## 3. 🔴 D2 —— `asr093` 基线与 `--inject` 写**同一个**产物文件

### 3.1 实测

`asr093_status_gate_v3.json`（修复前）顶层字段实测 =
`['probe','status','passes','n_checks','defects_found','checks','generated_at']`
⇒ **没有** `n_counterproofs` / `n_counterproofs_caught`
⇒ §65 表格声称的「反证 **8/8** 全过」**在产物里查无实据**。

### 3.2 根因

`asr093_status_gate_v3.py` 的 `--inject` 分支与基线分支**都写**
`asr093_status_gate_v3.json` ⇒ 跑完注入后基线产物被**覆盖**。

🔴 **这正是 §66 已在 `asr096` 上修过的同一类 bug**（§66 把 `asr096` 拆成
`asr096_legacy_consistency_gate.json` + `asr096_legacy_consistency_gate_inject.json`）
⇒ **在 `asr093` 上复发** ⇒ 说明「修一个实例」≠「修掉这一类」。

### 3.3 修法

- 拆成**两个产物**：`asr093_status_gate_v3.json`（基线）/
  `asr093_status_gate_v3_inject.json`（注入）。
- 基线产物**显式携带** `counterproof_evidence`（注入产物名 + 实测条数 + 一致性标志）
  ⇒ 读者按「基线产物 → 反证条数」查**不再落空**。
- 实测（修后）：基线 `counterproof_evidence.n_counterproofs` = **8**、
  `n_counterproofs_caught` = **8**、`all_counterproofs_caught` = `true`；
  基线顶层**不含** `results`（= 没被注入产物覆盖）；注入产物实测 `n_counterproofs` = **8**。

---

## 4. 🔴 D3 —— `asr096` 的扫描数**只 print 不落盘**

### 4.1 实测

`asr096_legacy_consistency_gate.json`（修复前）**无** `n_json_scanned` / `n_scanned` 字段
（脚本 `scan_timing_valid()` 返回 `n_scanned` 但只 `print`）
⇒ §66 表格「扫描产物 **123** 个 JSON」**无字段可溯源**。

### 4.2 修法

显式落 `n_json_scanned` 字段；STATUS 路径改为该字段。
实测（修后）：`n_json_scanned` = **127**
（**注**：不再是 §66 写的 123 —— 因为本轮新增了产物 ⇒ 扫描对象变多 ⇒ **数值随实测变**，
这正说明「只 print 不落盘」的危害：文档里的数字会**悄悄过期**）。

---

## 5. 加装 `asr099` v4 守卫（实测）

| 项 | 值 | 来源 |
|---|---|---|
| v4 守卫脚本 | `scripts/asr099_status_gate_v4.py`（**新增**） | — |
| v4 基线守卫 | **ALL PASS**（**18** 项判据） | `asr099_status_gate_v4.json` → `status` / `n_checks` |
| v4 注入反证 | **8/8** 全过 | `asr099_status_gate_v4_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| §67 独立复核 | **ALL PASS**（**23** 项判据） | `asr100_status_verify_s67.json` → `status` / `n_checks` |
| §67 复核注入反证 | **9/9** 全过 | `asr100_status_verify_s67_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |

### 5.1 v4 守卫的判据（G1–G10）

| 判据 | 内容 | 补的哪个盲区 |
|---|---|---|
| G1 | STATUS **全文** `产物 → 字段路径` 引用**逐条可解析**（路径存在，且**不是对象**） | **D1** |
| G2 | `asr093` 基线/注入**两个产物都存在**，且基线**不含**注入专有字段 `results` | **D2** |
| G3 | `asr093` 基线**显式携带** `counterproof_evidence` 且条数 > 0、与注入产物一致 | **D2** |
| G4 | `asr096` **显式落盘**扫描数（`n_json_scanned`） | **D3** |
| G5 | 头部唯一真值点 `自指大小: N B / M 行` == 实测 | （沿用） |
| G6 | CRCRLF == 0 且 裸 LF == 0 | （沿用） |
| G7 | 无残留 `@@…@@` 令牌 | （沿用） |
| G8 | 「最近更新」条目数 ≤ 15 | （沿用） |
| G9 | 「最近章节」节数 == 3（ASR-036 明文） | （沿用） |
| G10 | **每一个**章节（正文口径，去尾部空段）≤ 60 行 | （沿用） |

### 5.2 v4 守卫自身踩的坑（记录，避免复发）

1. 🔴 **「同上」跨表格沿用** ⇒ 把别的产物的路径算到本行头上 ⇒ **15 条假阳性**
   ⇒ 修法：「同上」记忆**限定在表格作用域**，出表即重置。
2. 🔴 **同格内多个产物名** ⇒ 候选文件取了**全部** ⇒ 「基线 → 路径（反证本体在 `inject.json`）」
   被误判 ⇒ 修法：候选只取「**紧跟 `→` 之前最近的那个**」产物名。
3. 🔴 **相对简写 `.field`** ⇒ `→ `a.b` / `.c`` 的第二段被当成完整路径 ⇒ 修法：支持
   **相对简写**（父级 = 上一路径去掉最后一段）。
4. 🔴 **缺陷描述豁免** ⇒ 正文在**描述一个已修缺陷**时会引出「当时那条不存在的路径」
   ⇒ 修法：窄豁免（必须**逐字**命中「该路径不存在 / 路径不存在 / 查无实据 / 字段不存在 /
   顶层字段 =」）⇒ **豁免规则比判错规则更危险，必须窄且配反证**（§44b/§45）。

---

## 6. §67 写入脚本自检抓出的自身 bug（§40/§64 纪律的又一次验证）

`asr101_status_write_s67.py` **干跑**抓出 **6 个**自身 bug（**真实 STATUS 直到转绿才被写**）：

| # | bug | 抓法 |
|---|---|---|
| 1 | 替换串未命中却**静默通过** | 加「每条替换**必须命中或已是修好的样子**」否则报错 |
| 2 | 「同上 → `blindspot_proof`」等替换串**永不命中**（该行在**被移走的 §64 段**里） | 拆成 `repl`（rest 作用域）与 `ARCHIVE_FIX`（**移走前**修） |
| 3 | 头部定位**硬编码** `lines[4]` / `lines[6]` ⇒ 上一轮 commit 后头部已 6 行 ⇒ **「已压缩」行重复 + 真值点 2 个** | 改用**前缀扫描**（§52 铁律） |
| 4 | 重跑会**再追加一个 §67** ⇒ 章节数变 4 | 加幂等：已有 §67 ⇒ **删旧段**再追加 |
| 5 | 「最近更新」重跑会**重复出现两条 §67 条目** | 加幂等：先剔除旧 §67 条目 |
| 6 | 数字随实测变（123 → 127）⇒ 字面替换**不幂等** | 改**行级正则**只改路径部分 |

🔴 另：**自指 bootstrap** —— STATUS 引用了本轮才生成的 `asr099_status_gate_v4_inject.json` /
`asr100_status_verify_s67.json` ⇒ 首次运行时它们**尚不存在** ⇒ 守卫报 FAIL。
⇒ 解法：**先生成再复核**（跑两遍），这是 §55「自校验必须在依赖链下游」的自然结果，
**不是**判据放宽。

---

## 7. 产物清单（实测）

| 文件 | size / mtime | 说明 |
|---|---|---|
| `scripts/asr099_status_gate_v4.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实** | v4 守卫脚本（新增）：判据 **12** 条（G1–G12）+ 反证 **10** 条 |
| `scripts/asr100_status_verify_s67.py` | 🔴 **不引 size/mtime**（§56②：复核脚本**自身**被改 ⇒ 引用即过期 ⇒ 自指 churn）⇒ 只引**内容事实** | §67 **独立复核**脚本（§43 新写，不复用写入脚本自检）：判据 **14** 条（V1–V14）、反证 **9** 条 |
| `scripts/asr101_status_write_s67.py` | 🔴 **不引 size/mtime**（§68 D6）⇒ 只引**内容事实** | §67 STATUS 写入脚本（干跑→转绿→才写真实） |
| `scripts/asr093_status_gate_v3.py` | 改动（拆基线/注入产物 + 基线携带证据指针） | v3 守卫（**D2 修法**） |
| `scripts/asr096_legacy_consistency_gate.py` | 改动（显式落 `n_json_scanned`） | 遗留一致性守卫（**D3 修法**） |
| `results/pyannote_seg/asr099_status_gate_v4.json` | 每次重跑都会变 ⇒ **只引内容事实** | v4 守卫基线：`status` = `PASS` / `n_checks` = **18** |
| `results/pyannote_seg/asr099_status_gate_v4_inject.json` | 每次重跑都会变 ⇒ **只引内容事实** | v4 注入反证：`n_counterproofs` = **8** / caught = **8** |
| `results/pyannote_seg/asr100_status_verify_s67.json` | 每次重跑都会变 ⇒ **只引内容事实** | 独立复核基线：`status` = `PASS` / `n_checks` = **23** |
| `results/pyannote_seg/asr100_status_verify_s67_inject.json` | 每次重跑都会变 ⇒ **只引内容事实** | 独立复核注入：`n_counterproofs` = **9** / caught = **9** |
| `results/pyannote_seg/asr093_status_gate_v3.json` | 每次重跑都会变 ⇒ **只引内容事实** | v3 基线（**修后**）：`counterproof_evidence.n_counterproofs` = **8** |
| `results/pyannote_seg/asr093_status_gate_v3_inject.json` | 每次重跑都会变 ⇒ **只引内容事实** | v3 注入（**新增**，修后）：`n_counterproofs` = **8** |
| `results/pyannote_seg/asr096_legacy_consistency_gate.json` | 每次重跑都会变 ⇒ **只引内容事实** | `n_json_scanned` = **127**（**修后新增字段**） |
| `results/pyannote_seg/_cp_s67/` | 沙箱 | 干跑产物 + 改前备份 |

---

## 8. 纪律

- 本轮**纯只读 + 文本守卫**（不跑任何模型推理、不计时）⇒ **未申请共享机器锁**
  （检查时 `shared/MACHINE_LOCK` 不存在、`shared/*.tmp` 残留 **0**、`GIT_FREEZE` 不存在）。
- 🔴 **未动 `live_caption/`**；🔴 **未改 `CORRECTIONS_ASR.md`**（reviewer 维护）；
  `last_ack` 保持 **ASR-036**。
- 🔴 **未覆盖已交付产物**（`asr055` 清单 v1/v2、79 个音频 md5 锚定未动）。
- ⚠️ **WER 未跑**（交 reviewer）；**未开新实验**；**未打包**。
- 遗留（非纠偏项，等用户指派）：① OV f16 偏差高于 torch FP16 固有下界 ⇒ 精度优化空间未做；
  ② `qwen3asr_06b` 不在 git 仓库内 ⇒ 交付需另行打包；
  ③ **8 个 `pya_*` 历史产物 `timing_valid=true` 但无 `lock_probe` 块** ⇒ 同样未经核验，
  但**只被归档章节引用** ⇒ **追溯改 = 改旧结论**，等用户指派再动。
