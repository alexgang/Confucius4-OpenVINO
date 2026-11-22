## §87 ASR-066：§86 复核的 5 处补齐（2026-11-20 16:28–17:15）

### §87 ASR-066：§86 复核的 5 处补齐（2026-11-20 16:28–17:15）

> 🔴 **reviewer 核实 §86 核心结论全部成立** ⇒ **本轮不重跑任何计时**、**未取 MACHINE_LOCK**
> （16:26–16:57 该锁由 App 模块持有）、**交付文件 `live_caption/` 未动**。
> 明细 `status/asr/notes/asr_s87.md`（含逐条数字与 json 字段）。

- ✅ **① CI 口径改写（结论不变）**：主数字改**逐轮范围** —— SPE **−13.67 / −13.76 %**、英 **−23.26 / −21.41 %**、中 **−18.34 / −17.55 %**（均值 −13.72 / −22.34 / −17.94 %）；**CI 标「轮内段级配对 bootstrap（n_blocks=5，B=5000）⇒ 不含轮间方差、区间偏窄」**、**点估计与 CI 同源**（−13.9306 [−14.5006,−13.369] / −22.7257 [−23.4847,−22.0957] / −18.3901 [−18.8428,−17.9328]）⇒ 🔴 **EN 第 2 轮 −21.41 % 落在 CI 外 ≠ 结论被推翻**（轮级 vs 段级**不可混用**）。**pml 显著降 RTF 成立。**
- 🔴 **② 分档回退已实现（旧实现是假回退）**：`build_tiers_with_fallback()`（任一档失败 ⇒ `tier_cms={}` ＋ `fallback_reason`）＋ **`Asr065Runner` 侧强制 `use_tier=False`**（🔴 旧实现**只 `break`、仍以 `use_tier=True` 建 runner** ⇒ 缺档时 `encode()` 抛 `tier N 未编译` ⇒ **根本不回退**）。**负向用例 10/10 PASS**（`results/asr166_tier_fallback/asr066_tier_fallback.json`，5911 B，mtime 17:01）：正例 patched=60 ⇒ 3/3 档成功、`use_tier=True`；**负例 patched=59** ⇒ **0/3**、`use_tier=False`、`tier_cms={}`、`encode()` **不抛错** ⇒ **回退后转写 md5 = `ed3f52aaf1415ca01d785da4e3a78cb4`**、与 §85 参照**逐字节相同**（`md5sum` 独立复核）、`prefix_truncations=0`。
- ✅ **③ handoff 补前提（`dev/asr065_handoff.md`）**：**3(a)** KV 容量 = **320 + 64 = 384**（原 576 ⇒ 少 192 ⇒ 即降 RTF 机理之一）⇒ **每次 `max_new ≤ 64`**（`FLUSH_MAX_NEW=64` ⇒ 现状满足；⚠️ App 改 `max_new` 规则时必须一起查）；**3(b)** 截断**只砍前缀** ⇒ 临界 **2324 mel 帧 ≈ 23.24 s** 时「18+音频 token」就超 320 ⇒ **砍光也救不了** ⇒ **前提：段长 ≤ `MAX_SEG_SEC` 20.0 s**（实测 20.48 s ⇒ base_len **284** ⇒ 余量 **36**）⇒ **已加自检**（`base_len > pml` ⇒ **显式抛错**）＋ **待决③注明「放宽段长 ⇒ pml 必须重算」**；实测 15 臂 T 最大 **163 / 185 / 285**。
- ✅ **④ handoff §二 延迟改用 §86 pml-only**（🔴 旧版误引 §85 的 **both** 数字 144.3→93.3 ms 却写成「降 pml」）：**英 156.4276→116.5739 ms（−25.46 %）**、**SPE 147.9330→121.8224（−17.65 %）**、**中 144.8717→114.7359（−20.81 %）**（first p50，2 轮均值；口径 = 每次 `generate` 计算耗时，**不含** 640 ms 分块等待）。
- ✅ **⑤ 原始 json 标注修正 8/8 PASS（数值一律未改）**：🔴 根因 = **`REF_MD5[lang]` 键冲突**（**SPE 的 lang 也是 `'en'`**）⇒ 假阴性。**`bench.json`**：5 个 SPE run `transcript_identical` **false→true**、每 run 补 `env`（`ov_version=2026.4.1-22982-e213a147257`）＋ `enc_tiers_fallback_reason=null`、`tier exec_devices` **`['N','P','U']`→`['NPU']`**（🔴 `list("NPU")` 把字符串拆成字符）；**`analysis.json`（重生成）**：`prefix_truncations.per_run` 键改 **(arm, round, 素材标签 spe/en/zh)** ⇒ **10→15 键**（⚠️ 裸 `material` 仍会撞：FLEURS-EN 与 FLEURS-ZH 同为 `fleurs`）、`md5_note` 改**按 `md5_vs_sec85` 动态生成**（旧版写死 2.5.0 结论、与同文件全 true **自相矛盾**）、**新增 `ci_caliber_note`**；**`trunc_test.json`**：SPE `identical` false→true ⇒ `check_2.pass` / `verdict` **false→true**（截断用例①与 md5 未动）；**`session.json`** 补 `env`。备份 `.bak_asr066/`。
- 🔴 **⑥ 本轮修掉 2 个真缺陷**：**①** 分档**假回退** ⇒ 已实现并实测；**②** `EXECUTION_DEVICES` **字符串被拆成字符** ⇒ 改用 kit 同口径 `_read_exec_devices()`。另：`build_embeds` 补**段长超限自检**。
- 🔴 **⑦ 纪律**：**未重跑任何计时**（§86 的 RTF / 延迟 / 内存数字**全是原值**）、**未取 MACHINE_LOCK**、**未改交付文件**、**未打包**、**未改 `CORRECTIONS_ASR.md`**、`results/` **未入库**。

- 🟢 **⑧ 邮件已发（T-MAIL-003「STATUS 必须发邮件」）**：**2 封**（收件人 alexchen7694@agent.qq.com，均用 Reply 保持线程）—— **①** `Re: [C4][A][TASK][GEN] T-MAIL-003 …` ⇒ 正文首行 `[C4][A][STATUS][ASR] T-MAIL-003 ACK`（7 条遵守承诺）；**②** `Re: [C4][A][CORRECTION][ASR] ASR-066 …` ⇒ 正文首行 `[C4][A][STATUS][ASR] ASR-066 STATUS`（结论/逐条/缺陷/数字/环境+提交号/纪律/遗留 **自含**），附件 2 个（gzip：`asr066_json_fix_report.json.gz` 804 B sha1 `5be68a4e…`、`asr066_tier_fallback.json.gz` 1615 B sha1 `e1953905…`；解压后 = 原 json，sha1 与产物一致）。⇒ **STATUS 与邮件两边内容一致**。🔴 **§87 主体提交 `e2376be`；本行补记见紧随其后的 2 个提交（仅含本行文字，不改任何数字）**。
> ⇒ **本轮完成 ⇒ 停下等 reviewer 复核。**
