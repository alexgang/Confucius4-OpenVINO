# §87 明细：ASR-066（§86 复核 —— 5 处要补）

> 🔴 **本轮性质**：reviewer 复核 **§86 核心结论全部成立**（不需重跑计时）
> ⇒ ASR-066 只要求**改文档 / 改代码 / 改 json 标注**。
> 🔴 **本轮未跑任何计时** ⇒ **未取 MACHINE_LOCK**（16:26–16:57 期间该锁由
> App 模块持有：pid 9584 → 26972，`app118-v25-full-zh` / `app118-v25-zh-cuda`）。
> 🔴 **交付默认未改**：`live_caption/` **未动**（改 MiniMVP 仍由 App 线程执行）。

---

## 〇、reviewer 已核实成立的部分（**本轮不重跑、不改写**）

- **OV 版本根因**：`results/asr165/probe/probe.json` 同一代码两解释器 ⇒
  `_ov265rc_env`（2026.5.0-23816）→ `d4f01c24…`；
  `_ov241_kitenv`（2026.4.1-22982）→ `cd67417e…`
  ⇒ **OV 版本、非 NPU 非确定性**。
- **15 臂转写**：base/pml/pmltiers × SPE/EN/ZH 全部 =
  `cd67417e` / `ed3f52aa` / `d93062a6`，与 §85 逐字节同 ⇒ WER/CER 与 §85 一致。
- **pml-only 交错**：编译在循环外（startup 188.37 s 单列）；锁自检 30/0。
- **截断**：T=321/330/350 不抛错、计数 3；15 臂 `prefix_truncations` 全 0。
- **分档**：默认 `use_tier=False`；3 档均 `n_patched=60`；不落盘成立。
- **内存**：5 场景 fresh 进程 json 全在，+1127.61 MB RSS / −0.37 MB 与原始字段一致。

---

## 一、第 1 项：CI 口径（🔴 **改口径，结论不变**）

### 🔴 reviewer 的问题
`analysis.segment_paired_bootstrap` 只是**同一进程内按段**的 bootstrap
（`n_blocks=5`，均值 −13.93 / −22.73 / −18.39），
STATUS 却把它和逐轮均值 −13.72 / −22.34 / −17.94 **写在一起**。
**EN 第 2 轮 −21.41% 落在 CI [−23.48,−22.10] 外** ⇒ 该 CI **没有包含轮间方差**。

### ✅ 改法（`asr165_analyze.py` 新增 `ci_caliber_note` 块）
1. **主数字 = 逐轮范围**（不是均值，更不是 CI）：
   | 素材 | 2 轮逐轮 ΔRTF | 均值 |
   |---|---|---|
   | SPE | **−13.67 / −13.76 %** | −13.72% |
   | 英 | **−23.26 / −21.41 %** | −22.34% |
   | 中 | **−18.34 / −17.55 %** | −17.94% |
2. **CI 标注**：`轮内段级配对 bootstrap（n_blocks=5，B=5000，seed=20261120）`
   ⇒ **只含轮内段级方差，不含轮间方差** ⇒ 区间偏窄
   ⇒ **不能**用它判定「某个逐轮值是否落在区间内」。
3. **点估计与 CI 用同一统计量**（都是轮内段级均值）：
   SPE −13.9306（CI [−14.5006,−13.369]）/
   英 −22.7257（CI [−23.4847,−22.0957]）/
   中 −18.3901（CI [−18.8428,−17.9328]）。
4. **结论不变**：pml=320 **显著**降低 NPU 流式 RTF（2 轮逐轮**全为负**）。

### 🔴 为什么 EN 第 2 轮落在 CI 外**不是**矛盾
两个口径的**方差来源不同**：
* 逐轮值 = **轮级** RTF 比（整轮 448.34 s 音频）⇒ 含**轮间**系统波动；
* CI = **轮内段级**配对 bootstrap ⇒ 只含**段级**波动、**不含**轮间波动。
⇒ 两者**不可混用、不可互相证伪**。

---

## 二、第 2 项：encoder 分档**回退没有实现**（🔴 真缺陷，已修）

### 🔴 reviewer 的问题（成立）
`asr065_handoff.md` §五要求「patched≠60 ⇒ 打日志、退回 2400 单档」，
但参考实现（`asr165_bench.py` L323–326）**只是 `break`**，
随后**仍以 `use_tier=True` 建 runner**
⇒ 缺档时 `encode()` 抛 `tier N 未编译`（`asr065_backend.py` 的
`_get_tier_cm`）⇒ **根本不会回退**。

### ✅ 修法（`scripts/_asr065/asr065_backend.py`）
1. **新增 `build_tiers_with_fallback(device, tiers, expected_patched)`**
   ⇒ 逐档构建；**任一档失败 ⇒ `tier_cms = {}` ＋ 返回
   `fallback_reason`**（含每档失败原因）。
2. **`build_tier_runtime(N, device, expected_patched=None)`**
   ⇒ 断言期望值**可注入**（负向用例要把 60 改成 59）。
3. **`Asr065Runner.__init__(..., tier_fallback_reason=None)`**
   ⇒ **若 `tier_fallback_reason` 非空 ⇒ 强制 `self._use_tier = False`**
   ＋ 记 `self.enc_tiers_fallback_reason`（**交付日志字段名**）
   ＋ 打 `[asr065:backend] 🔴 encoder 分档回退到 2400 单档：…`。
   ⇒ **这正是旧实现缺的那一环**（只 build 侧判失败、但 runner 侧不知情）。
4. **`asr165_bench.py`** ⇒ 改用 `build_tiers_with_fallback()`；
   `startup['pmltiers']` 记 `use_tier` ＋ `enc_tiers_fallback_reason`。

### ✅ 负向用例（`scripts/_asr065/asr066_tier_fallback_test.py`）
**不计时、不取 MACHINE_LOCK**（reviewer 明确要求）⇒ json 里的 `rtf`
**不作为结论**，只报**回退行为**与 **md5**。
用 **kit 的 OV 2026.4.1**（`_ov241_kitenv`）⇒ md5 与 §85 / §86 同口径。

| 用例 | 期望 patched | 结果 |
|---|---|---|
| `positive_60` | 60（真实值） | **3/3 档构建成功**、`use_tier=True`、`fallback_reason=None`、`encode()` 不抛错 |
| `negative_59` | **59（故意不符）** | **0/3 档成功**、`use_tier=**False**`、`tier_cms={}`、`fallback_reason` 非空、`encode()` **不抛错** |

### ✅ **回退后转写 md5 不变**（reviewer 的验收点）
`negative_59` 跑 FLEURS-EN（448.34 s）⇒
**md5 = `ed3f52aaf1415ca01d785da4e3a78cb4`**，
与 §85 参照 `ed3f52aa…` **逐字节相同**（`md5sum` **独立复核**通过）、
`prefix_truncations = 0`。
⇒ **回退到 2400 单档不改变文本**。

**断言 10/10 全 PASS** ⇒ 产物
`results/asr166_tier_fallback/asr066_tier_fallback.json`（5911 B，mtime 17:01）
＋ 同目录 `run_negative_59/fleurs_en/{transcript.txt,segments.json,segments.jsonl}`（**4 文件**）。

---

## 三、第 3 项：handoff 前提条件没写全（✅ 已补）

### 3(a) KV 容量 = pml + MIN_RESPONSE_LEN = **384**
* pml **320** ＋ `MIN_RESPONSE_LEN` **64** ⇒ KV 容量 **384**
  （原 512+64 = 576 ⇒ **少 192** ⇒ 这正是 pml 降 RTF 的机理之一）。
* 🔴 **硬性要求：每次 `max_new ≤ 64`**
  ⇒ `bk_run` 的 `FLUSH_MAX_NEW = 64`、`AdaptiveBudget` 上限也是 64 ⇒ **现状满足**。
  ⇒ ⚠️ **App 改 `max_new_tokens` 规则时必须一起检查**
  （超出 ⇒ 要么抬 `MIN_RESPONSE_LEN`、要么抬 KV 容量 ⇒ **RTF 数字要重测**）。

### 3(b) 截断**只能砍前缀** ⇒ 段长前提
* `T = 18（模板）+ 音频 token + 前缀`。
* 若「18 + 音频 token」本身就 > 320 ⇒ `keep = pml - base_len < 0`
  ⇒ **砍光前缀也救不了** ⇒ 仍会抛错。
* 🔴 **临界**：**2324 mel 帧 ≈ 23.24 s** 时音频 token = 302 ⇒ `18+302 = 320`。
* ✅ **前提：段长 ≤ `MAX_SEG_SEC` = 20.0 s**（实测最长 **20.48 s**）
  ⇒ 音频 token **266** ⇒ `base_len = 284` ⇒ **前缀余量 36 token**。
* ✅ **代码已加自检**（`asr065_backend.build_embeds`）：
  `base_len > pml` ⇒ **显式抛错**（不静默）＋ 计 `seg_too_long_events`。
* 实测 15 臂 T 最大值：SPE **163** / 英 **185** / 中 **285** ⇒ 离 320 尚有余量。
* ⚠️ **待用户决定③（30 s 上下文）里已注明：一旦放宽段长，pml=320 必须重算。**

### ✅ 已在 `dev/asr065_handoff.md` 落地
* §一 表格第 5 行（新增「回退」行）＋ 第 2 行补「段长超限自检」；
* **§三之二**（新增）：段长超限自检代码；
* **§四**（重写）：4.1 KV 容量前提、4.2 日志字段 ＋ `enc_tiers_fallback_reason`
  ＋ 「质量影响未测、线上计数 >0 需告警」；
* **§五**（扩写）：5.1 回退代码（两处都要有：构建处 ＋ runner 处）；
* §二：延迟数字换成 **§86 pml-only**；
* §七：验收数字表改逐轮范围；
* §八：口径提醒 ＋ CI 口径 ＋ 段长前提。

---

## 四、第 4 项：handoff §二 延迟数字张冠李戴（✅ 已改）

🔴 **旧**：引 §85 的 **both** 数字（144.3 → 93.3 ms）却写成「降 pml 降出字延迟」。
**新**（**§86 pml-only**，单位 ms = 每次 `generate` 的计算耗时，**不含** 640 ms 分块等待）：

| 素材 | base(512) first p50 | pml(320) first p50 | 变化 |
|---|---|---|---|
| 英 | **156.4276** | **116.5739** | **−25.46%** |
| SPE | **147.9330** | **121.8224** | **−17.65%** |
| 中 | **144.8717** | **114.7359** | **−20.81%** |

（出处：`results/asr165_ov241/analysis.json` → `latency_summary.{base,pml}.first.<mat>.p50_mean`，n_rounds=2）

---

## 五、第 5 项：原始 json 标注（✅ 已修，**数值未改**）

🔴 **根因**：`REF_MD5[lang]` **键冲突** —— **SPE 的 `lang` 也是 `'en'`**
⇒ SPE 拿到 FLEURS-EN 的参照 ⇒ `identical` **假阴性**。

### 5.1 `bench.json`（2214490 B，mtime 16:52）
| 修什么 | 修前 | 修后 |
|---|---|---|
| 5 个 SPE run 的 `transcript_identical` | `false` | **`true`**（参照 `cd67417e…`，不是 `ed3f52aa…`） |
| 每个 run 补 `env` | 缺 | **`{python, python_version, ov_version}`**（`ov_version = 2026.4.1-22982-e213a147257-releases/2026/4`） |
| 每个 run 补 `enc_tiers_fallback_reason` | 缺 | **`null`**（本轮未回退） |
| `startup.tier_runtime_build[].exec_devices` | **`["N","P","U"]`** | **`["NPU"]`** |

🔴 **`exec_devices` 的 bug**：`list(cm.get_property('EXECUTION_DEVICES'))`
⇒ OV 在该版本返回**字符串 `"NPU"`** ⇒ `list("NPU")` = `['N','P','U']`。
⇒ **已修** `asr065_backend.py`（新增 `_read_exec_devices()`，按逗号切分，
**与 kit 的 `bk_run._read_exec_devices` 同一口径**）。

### 5.2 `analysis.json`（**重新生成**，33913 B，mtime 16:52）
* 🔴 `prefix_truncations.per_run` 的键：旧版用 `r['lang']` ⇒ **SPE 与 FLEURS-EN
  撞车** ⇒ **SPE 键缺失**（旧 10 键）。
  ⇒ **改为 `(arm, round, 素材标签 spe/en/zh)`** ⇒ **15 键**（15 臂全在）。
  （⚠️ 用裸 `material` **仍会撞**：FLEURS-EN 与 FLEURS-ZH 同为 `fleurs`
  ⇒ 必须用**素材标签**。）
* 🔴 `md5_note` **写死**成「与 §85 不同」（那是 **2.5.0 那轮**的结论）
  ⇒ 与同文件的 `md5_vs_sec85`（**全 true**）**自相矛盾**
  ⇒ **改为按 `md5_vs_sec85` 动态生成**。
* ✅ **新增 `ci_caliber_note`**（见 §一）。

### 5.3 `trunc_test.json`（4321 B，mtime 16:52）
* `normal_materials[].ref_md5` / `identical` **按 (material, lang) 组合键重算**
  ⇒ SPE 的 `identical` **false → true**
  ⇒ `check_2.pass` **false → true**、`verdict` **false → true**。
* 🔴 **截断用例①（T=321/330/350）与转写 md5 全部未改。**

### 5.4 `session.json`（996 B，mtime 16:52）
* 补 `env`（`python` / `python_version` / `ov_version`）
  ⇒ 旧 json 缺 `ov_version` ⇒ 只能靠 md5 间接确认是 2.4.1。

### ✅ 独立复核（`asr066_fix_json.py` 自带，**8/8 PASS**）
`bench: SPE 全部 identical=true (5/5)` / `bench: 所有 run 都有 env.ov_version` /
`bench: tier exec_devices == ["NPU"]` / `analysis: per_run 有 15 个键（含 SPE）` /
`analysis: md5_vs_sec85 全 true` / `analysis: 有 ci_caliber_note` /
`trunc: check_2.pass=true 且 verdict=true` / `session: 有 env.ov_version`
⇒ 报告 `results/asr165_ov241/asr066_json_fix_report.json`（1826 B）。
🔴 **改前备份** `results/asr165_ov241/.bak_asr066/`（4 个 json）。

---

## 六、🔴 本轮**没有**做的事（明确说明）

* ❌ **未重跑任何计时** ⇒ §86 的 RTF / 延迟 / 内存数字**全部是原值**
  （json 只改了**标注**，**数值未动**）。
* ❌ **未取 MACHINE_LOCK**（16:26–16:57 该锁由 App 模块持有）
  ⇒ 负向用例是**短时 NPU 推理**（不含计时结论）。
* ❌ **未改交付文件**（`live_caption/` **未动**）⇒ 改 MiniMVP 仍由 App 线程执行。
* ❌ **未打包**（用户 11-20 规则：不主动打包）。
* ❌ **未改 `CORRECTIONS_ASR.md`**（reviewer 维护、本模块不提交）。
* ❌ **未入 git 产物**（`results/` 按纪律不入库）。

---

## 七、产物清单

| 产物 | 文件数 | mtime | 说明 |
|---|---|---|---|
| `results/asr166_tier_fallback/` | **4** | 17:01 | 回退负向用例：`asr066_tier_fallback.json`（5911 B）＋ `run_negative_59/fleurs_en/`（transcript.txt 6658 B + segments.json 17025 B + segments.jsonl 14380 B） |
| `results/asr165_ov241/`（json 标注修正后） | **98** | 16:52 | `analysis.json` 33913 B ＋ `bench.json` 2214490 B ＋ `trunc_test.json` 4321 B ＋ `session.json` 996 B ＋ `asr066_json_fix_report.json` 1826 B；备份在 `.bak_asr066/` |
| `scripts/_asr065/asr065_backend.py` | 1 | 17:0x | **新增** `build_tiers_with_fallback()` ＋ `tier_fallback_reason` 分支 ＋ `_read_exec_devices()` ＋ 段长超限自检 |
| `scripts/_asr065/asr165_bench.py` | 1 | 17:0x | 改用回退接口 ＋ 补 `env` ＋ 补 `enc_tiers_fallback_reason` |
| `scripts/_asr065/asr165_analyze.py` | 1 | 17:0x | 新增 `ci_caliber_note` ＋ 修 `per_run` 键 ＋ `md5_note` 动态化 |
| `scripts/_asr065/asr066_fix_json.py` | 1 | 16:52 | json 标注修正 ＋ **8 项独立复核** |
| `scripts/_asr065/asr066_tier_fallback_test.py` | 1 | 16:58 | 回退负向用例（**10 项断言**） |
| `dev/asr065_handoff.md` | 1 | 17:0x | 补 §三之二 / §4.1 / §5.1 ＋ 改 §二 延迟 ＋ §七 验收 ＋ §八 口径 |
| `status/asr/notes/asr_s87.md` | 1 | 17:1x | 本文件 |

---

## 八、遗留（不变）

* 🟡 **待用户决定 3 项**（数字以 §86 为准）：① 整段离线转写要不要加成交付路径；
  ② 「RTF≈0.05」对外怎么写；③ 🔴 encoder 静态上限 = 2400 mel 帧 = 24.0 s
  ⇒ 要上 30 s 上下文**得重导出 encoder**。
  ⇒ 🔴 **③ 已补注**：一旦放宽段长，**pml=320 必须重算**（见 §三 3(b)）。
* 🟡 **待 App 侧落地 3 项**（未变）：ASR 文件进 v2.3 / MiniMVP ＋ `ASR_FILES` 4→6；
  5 s 静态 seg IR 进 `models/spk/pyannote_seg_3_0/fp16-w5/`；
  App 侧 import `asr_runtime_switches` ＋ 实现 `LIVECAP_SPK_MIN_CLEAN_RATIO`。
* 🟡 **待 App 线程决定**：新说话人首次登记用哪段音频（推荐方案 B）。
* 🟡 **ASR-028 换人点抽听**：用户侧待办。
* ⚠️ **ASR-042 第 3 步仍暂停**（ASR-047）⇒ 本模块不跑 TTS。
* 🔴 **B 机实测已关闭**（11-15 用户决定，ASR-059）⇒ B 套件冻结。
* 🔴 **口径纪律**：凡与 §85/§86 参照比较的数字**必须用 OpenVINO 2026.4.1**。


## 十、「最近章节」摘要行移出索引（ASR-038 行数门禁）

（正文的 `### §NN` 全文节**未动**；只把较早的 § 摘要行移出「最近章节」列表 ⇒ 全文仍在 `status/archive/`）

- 已移出 § 摘要行（第 114 行）
- 已移出 § 摘要行（第 115 行）
- 已移出 § 摘要行（第 116 行）
- 已移出 § 摘要行（第 118 行）
- 已移出 § 摘要行（第 119 行）
- 已移出 § 摘要行（第 123 行）
