last_ack: ASR-066
更新时间: 2026-11-23 11:15
当前任务: 🟢 **ASR-066 已落地（§87）；本轮（§91）＝ 纯巡检 ＋ App §221 交付面只读复核**：**无新 ASR 纠偏条目**（`CORRECTIONS_ASR.md` 105 868 B / md5 `b6fd2e14…` / mtime 2026-11-20 15:33 ⇒ 最大 **ASR-066**、无 ASR-067+）⇒ **`last_ack` 保持 ASR-066**；**QQ 邮箱无新 ASR 邮件**（最新仍是 APP-121，已于 §89 回复）。🔴 **本轮只读，未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 live_caption/**。🟢 **App 在 §90 之后落了 `88b9ea8`（APP-121 §221）⇒ 交付面实质变化 ⇒ 本轮逐条只读复核**：**①** 🟢 **§89 的 HIGH 缺陷已闭环**（独立复现）：旧包 `v1.1`（后端 md5 `a92c02f2…`）长段 **rc=1 / ValueError「骨架 281+64>320」/ 字幕 0 行**；新包 `v1.1.1`（md5 `4b43dcbc…`）同素材 **rc=0 / 字幕 2 行 / 514 字符**；实现与 §89 补正的 handoff 契约一致（L583-591 NPU 档 `allowed_prefix = limit − skeleton`；**GPU 档一字未动**）；单测 **11/11 PASS**（含反证组）＋ 截断口径一致性 **3/3**。**②** 🟢 **§90 的「zip 必须自证」对新 zip 成立（本轮自己算的）**：用 `pack_v13._acc_module_fingerprints` 同口径从 `v1.1.1.zip` 内重算 ⇒ **ok=31 / missing=[] / changed=[] / extra=[]**；`ACCEPTED.json` `version=1.1.1` 与目录逐条一致；`tts_cuda*` 已挪出包外 ⇒ **31 个 .py == ACCEPTED 31 条**。**③** 🟢 **item 2 的 App 后端三素材 md5 已产出**（§88④/⑤ 撤回后一直缺的替代证据，OV 2026.4.1）⇒ **GPU 档新旧包三素材 md5 逐字节相同**（零回归成立）；**App 侧 NPU md5 ≠ §86 参照** ⇒ **§88④ 撤得对**。**④** 🔴 **本轮新发现（ASR 契约层面）**：**App 侧 NPU 在 ZH 上 `prefix_truncations=3`、GPU.0 = 0** ⇒ **handoff §四「正常素材不会触发（计数 0）」在 App 生产路径上不成立** ⇒ **§三之二 的余量前提写漏「段内累积前缀」**（实测 20.48 s ZH 段前缀 **39/43/32/21 token** vs NPU 档预算 **36**＝320−284）⇒ **§四/§三之二 需改写（本模块职责，下一轮）**；🟡 **但质量影响本轮未观测到**：**4 个长段 NPU/GPU 转写逐字节相同（4/4）**、ZH 的 4 处差异**全在短段** ⇒ **当前差异不能归因于截断**（浮点分叉）⇒ 属「机制成立、未见可见损失」的边界情形。**⑤** 🟡 **订正 App §221 的一条归因**：其「① 切段器不同 ⇒ 段边界/段数本就不一致」**不成立**（段数完全一致 93/65/66）⇒ **处置结论对、归因 ① 错**。**产物** `status/asr/notes/asr_s91.md`
阻塞 / 待用户决定: 🟢 **无阻塞**（ASR-066 已完成；**无新 ASR 纠偏条目** ⇒ `last_ack` 仍 **ASR-066**）。🔴 **本轮新增 1 项待处理（本模块自己的文档，下一轮做）**：改 `qwen3asr_06b/dev/asr065_handoff.md` **§三之二 / §四 前提表述** —— 「正常素材不会触发（计数 0）」在 **App 生产路径**上不成立（NPU 档 ZH 实测 3 次）；余量约束须补「**段长上限 ＋ 段内累积前缀 ≤ pml − 18**」。🟡 **待 App 线程决定 1 项（新）**：NPU 档前缀截断处置 —— 建议 **① `MAX_SEG_SEC` 降到 ≈19 s**（不动 pml、不动 §86 的 RTF 数字、不动 GPU 档）；备选 ② 超预算丢段尾前缀而非左截断；🔴 ③ 上调 pml **会改变 §86 全部 RTF 数字 ⇒ 必须重测**。🟡 **待用户/reviewer 决定 4 项（沿用）**：**①** 「md5 逐字节相同」口径改写为「**NPU 档 + OV 2026.4.1**」⇒ **仍未获批**（🔴 本轮补充：App 侧 NPU md5 与参照**确实不同**，但那是**切段/解码入口/语种注入**口径不同、**不是**回归）；**②** 整段离线转写是否加成交付路径；**③** 「RTF≈0.05」对外口径；**④** 🔴 encoder 静态上限 2400 mel 帧 = 24.0 s ⇒ 30 s 上下文**得重导出 encoder**（**放宽段长 ⇒ pml=320 必须重算**）。🟡 **待用户/reviewer 决定 1 项（新）**：README 是否加「**NPU 档在 20 s 长段会触发前缀截断（实测 3 次；本轮两侧转写一致、未见丢字，但机制上会丢句首）**」（App §221 §4 重写后的 README **目前没有**）。⚠️ **待 App 侧落地 1 项（已收窄）**：§90 的「① 重签 ② zip 自证 ③ item 2 补测」**三项本轮确认已闭环** ⇒ **只剩 ④ README 的 `--asr-device NPU` 示例能否给客户**（🔴 **旧 `v1.1.zip` 仍在磁盘且不自证** ⇒ **发客户前必须确认发的是 `v1.1.1.zip`**）。🟡 **待 App 线程决定 1 项（沿用）**：新说话人首次登记用哪段音频（推荐**方案 B**）。⚠️ 沿用不变：ASR-028 换人点抽听（用户侧）；**ASR-042 第 3 步仍暂停**（ASR-047）⇒ 本模块不跑 TTS；**B 机实测已关闭**（ASR-059）；`results/asr162`/`asr163`/`asr121_item1_check`/`asr090_zipcheck` 按纪律**未入库**；**OV 2026.4.1 口径纪律**。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。 §80 全文归档见 `status/archive/STATUS_ASR_sec80_upto_20261115.md`。
自指大小: 39420 B / 134 行

## 最近更新
- 2026-11-23 11:15 **§91（纯巡检 ＋ App §221 交付面只读复核）：无新 ASR 纠偏、无新 ASR 邮件、`last_ack` 仍 ASR-066；App 的 `88b9ea8`（APP-121 §221）把 §90 的 3 条待办全部闭环（本轮独立复核通过）；但首次发现 1 条 ASR 契约新问题（未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 live_caption/）** —— **①** 🟢 **§89 的 HIGH 缺陷已闭环**：旧包 `v1.1` 长段 **rc=1 / ValueError「骨架 281+64>320」/ 字幕 0 行**；新包 `v1.1.1` 同素材 **rc=0 / 字幕 2 行 / 514 字符**；单测 **11/11 PASS**（含反证组）＋ 截断口径一致性 **3/3**。**②** 🟢 **zip 自证本轮自己算的**：`pack_v13._acc_module_fingerprints` 同口径从 `v1.1.1.zip` 内重算 ⇒ **ok=31 / missing=[] / changed=[] / extra=[]**；`ACCEPTED.json` `version=1.1.1` 与目录逐条一致 ⇒ **31 个 .py == ACCEPTED 31 条**。**③** 🟢 **item 2 已产出**（§88④/⑤ 撤回后一直缺的替代证据，OV 2026.4.1）：App 后端三素材 md5 ⇒ **GPU 档新旧包逐字节相同**（零回归成立）、**App 侧 NPU ≠ §86 参照**（§88④ 撤得对）。**④** 🔴 **本轮新发现：App 侧 NPU 在 ZH 上 `prefix_truncations=3`、GPU.0 = 0** ⇒ **handoff §四「正常素材不会触发（计数 0）」在 App 生产路径上不成立**；**§三之二 的余量前提写漏「段内累积前缀」**（实测 20.48 s ZH 段前缀 **39/43/32/21** vs 预算 **36**）⇒ **§四/§三之二 需改写（本模块职责，下一轮）**；🟡 **但质量影响本轮未观测到**：**4 个长段 NPU/GPU 转写逐字节相同（4/4）**、ZH 的 4 处差异**全在短段** ⇒ **当前差异不能归因于截断**（浮点分叉）⇒ 属「机制成立、未见可见损失」的边界情形。**⑤** 🟡 **订正 App §221 的一条归因**：其「① 切段器不同 ⇒ 段边界/段数本就不一致」**不成立**（段数完全一致 93/65/66）⇒ **处置结论对、归因 ① 错**。**产物** `status/asr/notes/asr_s91.md`
- 2026-11-23 09:41 **§90（纯巡检 ＋ 只读交付面自检）：无新 ASR 纠偏、无新邮件、`last_ack` 仍 ASR-066；做出 reviewer item 3「zip 解压自检」的**第一手实测 ＋ 3 条只读结论**（未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 live_caption/）** —— **①** 🔴 **现有 zip（v1.1，11-22 16:51，5 212 356 737 B）解压后过不了自己的验收绑定闸门** ⇒ `pack_v13.check_acceptance_binding` 对 zip 内 `app/` + `ACCEPTED.json` 判 **`CONTENT_MISMATCH`**（`n_registered=33`/`n_current=31`/`n_changed=0`/**`n_missing=2`**：`tts_cuda.py`、`tts_cuda_sidecar.py`）⇒ **声明在 ACCEPTED 里的两个模块 zip 里没有**；zip 内后端 md5 = `a92c02f2…`（＝**缺陷版**）⇒ **客户若拿到此 zip，ASR=NPU 长段仍会停字幕**。**②** 🔴 **App 已把修法版同步进 `MiniMVP_v1.1.1` 目录**（包内后端 md5 `4b43dcbc…`）**但 `ACCEPTED.json` 未重签**（`version` 仍 `1.1`、`pkg_dir` 仍指 `…_v1.1`、指纹仍旧）⇒ 权威闸门判 **`VERSION_MISMATCH`** ⇒ **「改了代码但未重签」中间态** ⇒ **重打 zip 前必须先重签**。**③** 🟡 **item 2 的 App 后端三素材 md5 补测仍未产出**。⇒ **三条均属 App 线程交付面 ⇒ ASR 侧只读上报、不代做**。**产物** `status/asr/notes/asr_s90.md`
- 2026-11-23 09:30 **§89（APP-121 §1/§2 复核）：reviewer 的 [HIGH] 缺陷断言成立；§88 两句结论撤回；handoff 契约已补正（纯只读，未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 live_caption/）** —— **① 缺陷复现（不做推理）**：App `allowed_prefix = limit - skeleton - reserve` 把**生成预算**算进 **prompt 上界** ⇒ **NPU 档（320）段长 ≈18.33–18.57 s 即抛 ValueError** ⇒ 冒到 `Session._loop` ⇒ **字幕整条停掉**；交付版（git HEAD ＝ 包内那份，`a92c02f2…`）实测 NPU+reserve=64 在 audio_tok 260/266 **RAISE**、**GPU.0（512）全 OK**、`skeleton=321` 正确报错。**② 第二个后果**：A 版**前缀多砍 32–64 token** ⇒ **App 口径 ≠ ASR 参照口径** ⇒ 「App 侧 NPU 逐字节复现参照」「对 GPU.0 零回归」两句**撤回**。**③ 归因**：`git log -S` ⇒ **`dfb225e`（APP-118 接入 pml=320）** 引入 ⇒ **ASR-065 参考实现本身无错**。**④ App 修法（B 版 `4b43dcbc…`，未提交）已只读验证通过**：NPU 长段**全不抛错**、`skeleton=321` 仍报错、**GPU 档一字未动**、**前缀口径 32/64 一致（320 == 320）**。**⑤ 本模块动作**：**补正 handoff 契约**（新增 §三点三 + §八口径：`allowed_prefix = limit - skeleton`（**不减 reserve**）＋ 总量检查 `prompt + reserve ≤ limit + 64`）⇒ 根因＝**契约表述有歧义**。**⑥ item 2 的 App 后端三素材补测属 App 线程**（不代跑）。**产物** `status/asr/notes/asr_s89.md` ＋ `qwen3asr_06b/results/asr121_item1_check/`（**2 文件**，仓库外未入库）。
- 2026-11-20 17:08 **ASR-066 已落地（§87）：§86 复核的 5 处全部补齐（纯文档/代码/json 标注，**未重跑计时**、未取 MACHINE_LOCK、交付文件未动）** —— **① CI 口径已改**：主数字改**逐轮范围**（SPE −13.67/−13.76、英 −23.26/−21.41、中 −18.34/−17.55 %），CI 标「**轮内段级、不含轮间方差**」、点估计与 CI **同源**（−13.9306/−22.7257/−18.3901）⇒ **结论不变**（EN 第 2 轮落 CI 外**不是**被推翻）。**② 分档回退已实现**（`build_tiers_with_fallback()` ＋ runner 侧强制 `use_tier=False` ＋ `enc_tiers_fallback_reason`；🔴 旧实现**只 break 不回退**是真缺陷）⇒ **负向用例 10/10 PASS**：期望 patched 改 **59** ⇒ 3 档全败 ⇒ `use_tier=False`、`tier_cms={}`、`encode()` **不抛** ⇒ **转写 md5 = `ed3f52aa…` 与 §85 参照逐字节同**（`md5sum` 独立复核）。**③ handoff 补前提**：KV 容量 = **320+64 = 384** ⇒ **每次 `max_new ≤ 64`**（App 改 `max_new` 规则时必须一起查）；段长 **≤ MAX_SEG_SEC 20 s**（实测 20.48 s ⇒ base_len 284 ⇒ 余量 36；临界 **23.24 s**）＋ **自检代码**（`base_len > pml` ⇒ 显式抛错）＋ 待决③注明「放宽段长 ⇒ pml 必须重算」。**④ 延迟数字改用 §86 pml-only**（英 first p50 156.4→116.6 / SPE 147.9→121.8 / 中 144.9→114.7 ms）（🔴 旧版误引 §85 的 both 数字 144.3→93.3）。**⑤ json 标注 8/8 PASS**：SPE `identical` 假阴性纠正（false→true）、`per_run` 补到 **15 键**、`ov_version`/`env` 补进 bench+session、`exec_devices` `['N','P','U']`→`['NPU']`（字符串被拆成字符）、`md5_note` 改动态生成、`trunc_test` 的 `check_2.pass`/`verdict` 纠正为 **true** ⇒ **数值一律未改**。**产物** `results/asr166_tier_fallback/`（**4 文件**）＋ `results/asr165_ov241/`（98 文件，json 已标注修正）＋ `status/asr/notes/asr_s87.md`。
- 2026-11-15 12:05 **ASR-059 已读（`last_ack` → **ASR-059**）⇒ B 机实测待办**已关闭**，ASR 线程**待命**（纯文档，未跑实验/未取锁）**：用户 **11-15 决定 B 机（192.168.2.206）不跑 ASR 套件** ⇒ 头部「B 机实测由 reviewer / 主会话安排」改为「**11-15 用户决定不做（ASR-059）**」；**ASR-028 换人点抽听**仍为**用户侧待办**（本线程**无动作**）。🔴 **本轮只改文档**：未跑计时/WER、未取 MACHINE_LOCK、未改套件文件、未打包、未动 `live_caption/`；🔴 **为腾出 ASR-036（≤40 KB / ≤160 行）余量**，**§80 全文归档** ⇒ `status/archive/STATUS_ASR_sec80_upto_20261115.md`（**逐字保留**）＋ 正文留一行摘要（结论/数字仍在「关键数字」表 ＋「已撤回的旧结论」清单，**未丢结论**）。
- 2026-11-14 16:25 **ASR-058 已读（`last_ack` → **ASR-058**）⇒ ASR-057 关闭，ASR 线程**待命**（按 §3 **不写新章节**）**：reviewer 验收**全通过** —— `run_bk.cmd` **3764 B / CRLF 134 / 裸 LF 0 / 纯 ASCII / SHA256 `3c9b387a…b3c1`**（与 SHA256SUMS 一致），三种用法 **12/1/1 组 rc=0**，假桩失败 ⇒ 打印 **failed 12/1/1 且 rc=1**，两参 ⇒ 用法 **rc=2**；套件 **65 文件 == `n_files` 65**（去 `MANIFEST.json`+`SHA256SUMS.txt` ⇒ **2 348 478 744 B** == §82），无 `.bak*`/`results_A_local`/`.pyc`；`ref_A/` **8 文件 = 最终版 4 组**；`sources` **14 条**（4 条派生 `identical=null`+`derived=true`）；10min 口径 SPE **0–600 s** 一致；本轮**只读复核**：`_asr057_verify_status.py` **32 PASS**、`_asr057_verify_kit.py` **26 PASS**（哈希 0 处不符）⇒ **未打包、未动 `live_caption/`、未上 B 机**。
- 2026-11-13 10:10 **ASR-057 已落地（`last_ack` ASR-056 → **ASR-057**）⇒ 停下等 reviewer 复核**：**①** 🔴 `run_bk.cmd` **CRLF + 纯 ASCII** ＋ **`all`(12 组) / `selftest` 分支** ＋ **失败非 0 退出** ⇒ **假桩实测 12 / 1 / 1**（`bk_check_cmd.py` **8 PASS / 0 FAIL**）；**②** `.bak_asr056/` ＋ `results_A_local/` **移出套件** ＋ `SKIP_DIRS` 收窄 ⇒ **文件数 65 == MANIFEST `n_files` 65**；**③** `ref_A/` 补**最终版 18 s 三组** ＋ 删旧脚本 3 组 ⇒ **最终版 4 组**；**④** `sources` 拆 **copy/derived** ⇒ **14 条**（copy 10 / derived 4）＋ **tokenizer + `prompt.json`** 补齐；**⑤** 遗留项「待用户决定 `overlap_ratio_max`」**已删**（用户 11-07 已决定不修）；**附带修掉 2 处真缺陷**（`n_files` 语义 ＋ **MANIFEST.json 在 PS 5.1 解析失败**）；**验收 26 PASS / 0 FAIL**、`--check` **0 处不符** ⇒ 详见 **§82**。
- 2026-11-11 15:40 **ASR-056 已落地（`last_ack` ASR-055 → **ASR-056**）⇒ 停下等 reviewer 复核**：**①** §79 正文 **4 处标撤回** ＋ 已撤回清单补 **3 条**；**②** 旧计时 json（**10 个**）标 `unverified` ＋ `bk_run.py` 无锁改 `"no_lock"`；**③** 跨脚本比较块清理（4 个 bench json → `cross_script_ref_1025` ＋ `"comparable": false`，**并修掉标签颠倒**）＋ `asr138*` 加 `superseded_by`；**④** 关键数字表**补 300 s / 18 s 并排行**（带出处）＋ GPU 提速写 **RTF 区间 1.6–2.1×**；**⑤** 套件**最终版脚本持锁补跑 4 组** ⇒ **31/31 PASS**；**⑥** 套件小修 a–f 全做 ⇒ **61 文件 / 2348476971 B**；**未打包、未动 App 树 / 客户包 / `live_caption/`** ⇒ 详见 **§81**。

## 当前有效结论

> 🔴 **每个数字都注明来源产物**；被推翻的旧结论**不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| ASR 主模型 | R2T2（Qwen3-ASR-Flash-Realtime 路线），**默认 GPU.0** | ASR-018 用户决定 |
| 语音输出模型 | TTS 走 NPU（**不属本模块**） | ASR-018 |
| 线程 | **限线程是交付默认**：`OMP/MKL/OPENBLAS/NUMEXPR/VECLIB_MAXIMUM_THREADS=1`，**必须在 import numpy/torch 之前** | `asr073_thread_limit_delivery_default.json`（AST 级守卫 + 6/6 反证）；单一事实来源 `scripts/asr_thread_defaults.py` |
| 说话人编码器 | **wespeaker resnet34 OV IR，FP16 交付**（ASR-025 已关闭） | `asr067_fp16_vs_fp32_cluster.json` |
| 说话人聚类阈值 | `thr = 0.35` | ASR-013 ③ |
| 切段 | 规则1（段长 ≥MIN_SEG 且近 3 s 内有 ≥300 ms 静音）+ 规则2（静音超时 0.8 s 优先）+ 空段守卫 | C-108 / C-109（MIN_SEG = 6 s） |
| 强制断句 | **已停用**（pyannote 只做说话人识别，不产生断点） | ASR-021 用户决定 |
| TTS 音色策略 | 方案 A：**TTS 不等说话人标签** | ASR-024 用户决定 |

### 关键数字

| 指标 | 值 | 来源产物 / 字段 |
|---|---|---|
| CPU 占用（不限线程 / 限线程） | 7.8074 核 / **0.9981 核** | `asr049_cpu_attribution_rerun_{base,ovthreads}.json` → `avg_cores` |
| RTF（不限线程 / 限线程） | 0.6444 / **0.5302** | 同上 → `rtf`（🔴 单次测量 ⇒ 只能写「**不变或略好**」，不得写提速 18%） |
| 定稿段数（两臂） | 45 / 45 | 同上 → `n_segs` |
| 锁自检次数（两臂） | 88 / 73 | 同上 → `lock_probe.lock_probe_checks`（stolen 均 0） |
| 说话人聚类：FP16 vs FP32 不一致段数 | **0 / 196**（diff_rate 0.0） | `asr067_fp16_vs_fp32_cluster.json` → `arm_consistency.n_diff_segments` |
| 说话人：段级纯度 vs 伪真值 | 0.9147（n=183 段） | 同上 → `per_arm_vs_pseudo_truth.A_fp16.purity_and_fragmentation.segment_purity_vs_pseudo_truth` |
| 说话人：换人点 F1（±0.5 s / ±3.2 s） | 0.2025 / 0.6582 | 同上 → `per_arm_vs_pseudo_truth.A_fp16.switch_points_vs_pseudo_truth.tol_0p5s.f1` / `per_arm_vs_pseudo_truth.A_fp16.switch_points_vs_pseudo_truth.tol_3p2s.f1` |
| 说话人：识别人数 | 5（伪真值 6 人） | `asr055_spk_qa_reference_eval.json` → `asr_side_report.n_speakers` / `ref_meta.n_speakers` |
| 嵌入 RTF 增量（改法① 落地前 / 后） | 0.0494 / **0.0315** | `asr081_range_hi_coverage.json` → `arms.embed_dynamic.rtf_increment_vs_asr_only` / `arms.embed_range_2048.rtf_increment_vs_asr_only` |
| 嵌入墙钟（落地前 / 后） | 5.921 s / **0.551 s** | 同上 → `arms.embed_dynamic.embed_wall_s` / `arms.embed_range_2048.embed_wall_s` |
| 嵌入向量一致性（落地后 vs 动态） | 43 段逐段，cos 最小 1.0、rel 最大 0.0 | 同上 → `consistency_vs_dynamic.embed_range_2048.n` / `.cos_min` / `per_segment[].rel_max_abs_diff` |
| 生产段帧数上界 | 1998 帧（= MAX_SEG_SEC 20.0 s）；落地取 EMBED_RANGE_HI **2048** | 同上 → `offline_segment_length.prod_frame_upper_bound` / `.app_MAX_SEG_SEC` / `.landed_EMBED_RANGE_HI` |
| FP16 嵌入保真（余弦 / rel） | 0.999998775537715 / 0.001432037985732332（**不过** 1e-3 门槛） | `asr060_wespeaker_precision_attrib.json` → `experiments.ov_fp16_vs_torch_fp32.cos` / `.rel_max_abs_diff` |
| FP32 对照 rel | 1.1163879303042469e-06（**过**门槛）⇒ 归因 = FP16 格式固有精度，非 IR 缺陷 | 同上 → `experiments.ov_fp32_vs_torch_fp32.rel_max_abs_diff` |
| `SpeakerTracker` 接口自检 | 19/19 全过 | `asr054_speaker_tracker_selftest.json` → `n_pass`/`n_checks` |
| 交付集合闸门（3 文件） | 关键字 0、运行时链越界 0、隔离自洽 True、反证 4/4 | `asr079_delivery_set_gate.json` |
| NOTICE 关键字闸门 | 命中 0、反证 4/4 | `asr085_notice_keyword_gate.json` |
| 说话人旁路窗口 10 s vs 5 s：召回（10 s / 5 s） | 10/12 / **10/12** | `asr105_spk_window_5s_vs_10s.json` → `arms[].evaluation.analysis_raw.n_hit`（`n_ref_switches` = 12） |
| 说话人旁路窗口 10 s vs 5 s：误报（10 s / 5 s） | **0 / 0** | 同上 → `arms[].evaluation.analysis_raw.n_false_positive` |
| 标签到达延迟 P50（10 s / 5 s） | 10.0003 s / **5.0002 s** | 同上 → `arms[].evaluation.label_lag.all_pending.p50_s` |
| 标签到达延迟 P95（10 s / 5 s） | 10.0013 s / **5.0008 s** | 同上 → `arms[].evaluation.label_lag.all_pending.p95_s` |
| 每窗口耗时：旁路分段 P50（10 s / 5 s，GPU.0） | 0.04159 s / **0.021128 s** | `asr105_window_bench.json` → `seg_bench[].infer_p50_s` |
| 每窗口耗时：旁路分段 P50（10 s / 5 s，CPU 对照） | 0.054432 s / **0.027677 s** | 同上 |
| 旁路分段 RTF（10 s / 5 s，GPU.0） | 0.004159 / **0.004226** | `asr105_window_bench.json` → `summary[].rtf_seg`（窗口数翻倍 ⇒ RTF 略升）|
| 旁路+嵌入 RTF（10 s / 5 s，GPU.0） | 0.004807 / **0.005521** | 同上 → `summary[].rtf_total` |
| 300 s 总成本（10 s / 5 s，GPU.0） | 1.248 s / **1.268 s** | 同上 → `summary[].projected_300s_cost_s`（基本持平）|
| stateful vs mask2（**同脚本同口径**，10 分钟）RTF：GPU.0 / NPU | **0.2479 / 0.3998**（1.6×）与 **0.384 / 0.5696**（1.5×） | `asr138_10min_{stateful,stateless}_{GPU0,NPU}/summary.json` → `rtf`（🔴 **不再用 10-25 旧 runner 的 0.6827/1.0684** ⇒ §79④ 已撤回）|
| stateful vs mask2 每 token 解码 p50：GPU.0 / NPU | **14.5565 / 56.7728 ms**（3.9×）与 **18.7421 / 91.6198 ms**（4.9×） | 同上 → `probe.decode_ms_p50` |
| stateful vs mask2 出字延迟 p50：GPU.0 / NPU | **0.0928 / 0.0949 s**（持平）与 **0.1518 / 0.1296 s**（NPU 反而慢 17%） | 同上 → `first_tok_latency_p50` |
| mask2 18 s 端到端（GPU.0 / NPU） | **3.7929 s / rtf 0.2107** 与 **4.6038 s / rtf 0.2558** | `asr147_bench_mask2_{GPU0,NPU}.json` → `B3_e2e_18s.wall_s` / `.rtf`（**带 `lock_record`**、`timing_valid=true`）|
| mask2 300 s 流式（GPU.0 / NPU） | **rtf 0.5397 / 46 段 / 829 词** 与 **rtf 0.5259 / 46 段 / 831 词** | 同上 → `B4_stream_300s.rtf` / `.n_segs` / `.total_words` |
| stateful vs mask2 **同 runner 300 s / 18 s 并排**（GPU.0 / NPU） | **300 s RTF** GPU **0.2627 / 0.5397**（**0.49×**）、NPU **0.3496 / 0.5259**（**0.66×**）；**18 s wall** GPU **1.4541 / 3.7929 s**（**0.38×**）、NPU **1.706 / 4.6038 s**（**0.37×**）；**每 token p50** GPU **16.4051 / 81.0881 ms**（**0.2×**）、NPU **17.7664 / 89.6434 ms**（**0.2×**）；**300 s 出字 p50** GPU **0.0951 / 0.1317 s**、NPU **0.1451 / 0.1264 s**（**NPU stateful 慢 15%**）🔴 **GPU 提速只能写区间：RTF 口径约 1.6–2.1×**（10 分钟跑 **1.6×**、300 s 跑 **2.1×**）—— mask2 GPU 每 token p50 在 10 分钟跑是 **56.7728 ms**、300 s 跑是 **81.0881 ms**，**相差 43%**，两次各只跑 1 遍 ⇒ **不报单点、不要求补跑**；🔴 **NPU 首字归因（stateful vs mask2 同在 NPU）**：mask2 首 token 是**一次 512 静态前向**、B1 p50 **89.6434 ms**，stateful prefill p50 **94.7818 ms** ⇒ **量级相同** ⇒ 持平或略慢**预期内** | `asr135_bench_{GPU0,NPU}.json` → `B1_per_token.decode_ms_p50` / `B3_e2e_18s.wall_s` / `B4_stream_300s.rtf` / `B4_stream_300s.first_tok_latency_p50` ＋ `asr147_bench_mask2_{GPU0,NPU}.json`（**同字段**）＋ `asr138_10min_stateless_GPU0/summary.json` → `rtf` / `probe.decode_ms_p50` |
| NPU prefill p50（stateful） | **94.7818 ms**（GPU.0 60.2073 ms ⇒ 慢 **34.5745 ms**（差值，由两字段相减）） | `asr135_bench_{NPU,GPU0}.json` → `B2_prefill.prefill_ms_p50`（⇒ NPU 出字延迟变差的主因）|
| **按段配对 WER**（stateful NPU vs mask2 GPU0） | **Δ +0.2251 pp，CI [-0.2906, 0.776]，`significant_worse=false`** | `asr146_wer_seg_paired.json` → `comparisons[2].delta_pp` / `.ci95` / `.significant_worse`（`mode`=`segment_paired`，`n_blocks`=93，`scorer`=`reviewer_minimax_global`）|
| 按段配对 WER：stateful GPU0 vs mask2 GPU0 | **Δ -0.0563 pp，CI [-0.5775, 0.4638]，不显著** | 同上 → `comparisons[0]` |
| B 机套件 `b_kit_stateful` | **65 文件（磁盘实际）/ 63 进哈希 / 2348478744 B**（assets 356067863/11、models 1884374957/6、ref_A 15391/8、scripts 121679/12、wheels 107868519/23）⇒ **文件数 == MANIFEST `n_files`**；`--check` **0 处不符** | `b_kit_stateful/MANIFEST.json` → `n_files` / `n_hashed_files` / `total_bytes` / `dir_sizes`；`SHA256SUMS.txt` 同源；`bk_sha256.py --check` |
| B 机套件 A 机自测（`--mel torch`） | **46/46 段文本逐位同、词数 831=831、词级差 0、RTF 差 6.43% ⇒ 7/7 PASS** | `b_kit_stateful/results/bk_cmp_selftest_torchmel.json` → `txt_same` / `total_words_new` / `word_diff_count` / `rtf_rel_diff` / `verdict` |
| B 机套件 A 机自测（`--mel fft`，免 torch） | **43/46 段同、词数 831=831、词级差 6 词（0.72%）、RTF 差 8.22%** | `b_kit_stateful/results/bk_cmp_selftest_numpymel.json` |
| mel 数值差归因 | 填充/窗/帧化**逐位同**；谱差 **1.3487e-06**（相对 8.04e-08）⇒ 差异**双来源**：FFT 实现（**不可消除**）＋ dtype/log10（**可消除**）；`--mel torch` 与 transformers **逐位同（maxdiff 0.0）** | `b_kit_stateful/results/bk_mel_bench.json` → `cases[].pad_bitwise_same` / `.window_bitwise_same` / `.frames_bitwise_same` / `.spec_diff_numpy_vs_torch` / `.torch_mode_all_bitwise_same` |
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |

### 已撤回的旧结论（**不作为结论**，仅备查）

- 🔴 **§88④/⑤ 的「App 侧接入在 NPU 上逐字节复现参照」「对 GPU.0 零回归」已撤回** ⇒ **APP-121 §2 复核成立**：`_app120_asr_3mat.py` 用的是 **ASR 模块**的 `bk_run.run_stream` ＋ `asr065_backend.Asr065Runner`，**没经过 App 的 `ASR06BStatefulBackend`** ⇒ 只能证明「包里的模型文件与 ASR 模块用同一份」。🔴 **补充**：即便改用 App 代码，**交付版**（`dfb225e` 引入的「`allowed_prefix` 减 `reserve`」）在 NPU 档会把前缀**多砍 32–64 token**⇒ 口径本就与 ASR 参照不同 ⇒ **大概率仍不会逐字节相同**。🟡 **§88「GPU.0 与 ASR 模块 11-19 基准逐字节相同」本身仍成立**（ASR 模块**内部**前后自比）；**撤回**的是把它当作「**App 接入**零回归」的证据。详见 §89。
- 🔴 **§85⑦ 的「4 档全带 ≈ +1.9 GB RSS / +1.19 GB 私有」已撤回** ⇒ §86 fresh 进程实测：**分档相对 base = +1127.61 MB RSS / +1121.70 MB Private**（reviewer 指出：那是 4 个**单档**相加、含 base 里本来就有的 2400 档 ⇒ 真实增量只算 400+800+1600 三档）
- 🔴 **§85 反推的「① 单独（仅降 pml）= −19.76%」已撤回** ⇒ §86 **直接实测**：**−13.72% / −22.34% / −17.94%**（SPE/英/中，配对 bootstrap）⇒ 反推值偏高约 6 pp（分档收益被算进残差）
- §84④ 的「①+② 组合降幅 **−31.6% / −53.2% / −42.2%**」⇒ **已撤回**（base 臂受干扰 ＋ 四臂**按臂顺序**跑、未交错）⇒ **§85 交错重测 18 臂**：both vs base = -20.41% / -27.00% / -26.00%（SPE/英/中）。
- §84④ 的「② 分档单独降幅 **−2.0% / −41.7% / −2.8%**」⇒ **已撤回**（`tier_spe`/`tier_zh` 的 wall **含懒编译**）⇒ **§85（计时前全编译好）**：-5.62% / -9.04% / -6.66%（SPE/英/中）。
- §84⑨ 的「① 与 ② 有正交互（组合优于线性叠加 3.1–6.7%）」⇒ **已撤回**（tier 懒编译伪影把 ② 高估）⇒ **§85 正确口径下二者收益可叠加、无正交互**。
- §84⑥ 的「prefill 耗时与真实长度无关 ⇒ **不是**补齐到 `MAX_PROMPT_LEN`」⇒ **已撤回**（该反驳推理不成立：真实长度 26–285 **不能**否定静态补齐）⇒ **§85 实测按 T//32 分桶的 prefill p50 是平的** ⇒ **NPUW 确实按 `MAX_PROMPT_LEN` 静态补齐后计算**（reviewer 原推断正确）。
- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。
- §79② 的「旧 `ov-dec-06b-past-int8` 在 NPUW 下即编过 ⇒ **判断成立**」⇒ **ASR-055 已撤回**（`asr130…json` → `verdict.reviewer_hypothesis_npuw_only` = **`"REFUTED"`**；真条件 = `inputs_embeds`-only 端口形态 ＋ `NPUW_LLM` 缺一不可）。
- §79④ 的「**RTF 降到 mask2 的 0.38×（≈2.6× 加速）、出字延迟降到 0.39×**」⇒ **ASR-055 已撤回**（mask2 基线取自 10-25 旧 runner ⇒ **跨脚本**；同脚本同口径见关键数字表，**NPU 出字延迟反而慢 15%**）。
- §79⑥ 的「stateful NPU 对 mask2 GPU **显著变差 True**」⇒ **ASR-055 已撤回**（配对 bootstrap 只分 5 块 ⇒ 假象；改**按段配对** null 块后 6 组**全部不显著**，`asr146_wer_seg_paired.json`）。

## 未完成纠偏
| 编号 | 一句话 | 状态 |
|---|---|---|
| ASR-042 | VAD 门控 / 降频 / ASR+MT+TTS 并发 TTS RTF | ✅ **① VAD 门控已落盘**（§72.⑧-1；只给数据、不改默认值）；✅ **② 降频/合并窗口已落盘**（§72.⑧-2）；🟡 **③ 第 3 步（ASR+MT+TTS 同跑对比 TTS RTF）**⇒ **需与 TTS 线程协调 + 共用 TTS-044 负载脚本** ⇒ **本模块单方无法完成** |
| ASR-036 | 压缩 STATUS 与 CORRECTIONS（索引表每个编号一行 + ≤40 KB） | 🟡 **压缩本体已完成**（STATUS ≤160 行；CORRECTIONS 25.7 KB ≤ 40 KB）；🔴 **索引表已由 reviewer 补到 ASR-046 ⇒ 只缺 ASR-047/048 共 2 行** ⇒ CORRECTIONS 由 reviewer 维护且不提交 ⇒ **待 reviewer 补齐**（本模块不改不提交） |

> 🟡 **本模块已把可独立完成的部分做完**；ASR-042 第 3 步是**跨模块协作项**，等待 TTS 线程配合。

## 最近章节

> 只保留最近 3 节；更早的章节见 `status/archive/STATUS_ASR_upto_20261030.md`。
> 🔴 **§66–§68 的全文已归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文只留摘要；明细在 `status/asr/notes/asr_s6*.md`（**已提交**）。
> 🔴 **§70 / §71 / §72 已移入归档**（ASR-036「只保留最近 3 节」门禁）⇒ 明细见 `status/asr/notes/asr_s40.md` / `asr_s41.md` / `asr_s72.md`。

- ✅ **§88（APP-120 §0：ASR-065/066 优化接入复核（2026-11-23 03:27–03:40））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec88_upto_20261123.md`

- ✅ **§89（APP-121 §1/§2 复核：NPU 档长段抛错（缺陷成立）＋ 撤回 §88 两句结论 ＋ handoff 契约补正（2026-11-23 09:10–09:30））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec89_upto_20261123.md`

- ✅ **§90（纯巡检 ＋ 只读交付面自检：zip 解压自检实测 `CONTENT_MISMATCH` ＋ v1.1.1 未重签 `VERSION_MISMATCH` ＋ item 2 未产出（2026-11-23 09:33–09:45））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec90_upto_20261123.md`
- ✅ **§91（__TS__）**：纯巡检 ＋ App §221 交付面只读复核 —— §90 的 3 条待办全部闭环（缺陷已修 / 新 zip 31/31 自证 / item 2 三素材已产出）＋ **新发现：App 侧 NPU 前缀截断计数 3 ⇒ handoff 前提待改写**

### §91 纯巡检 ＋ App §221 交付面只读复核：§90 的 3 条待办全部闭环 ＋ 新发现「App 侧 NPU 前缀截断计数 3 ⇒ handoff 前提需改写」（2026-11-23 10:57–11:15）

> 🔴 **纯巡检 ＋ 只读复核**。纠偏通道 **无新 ASR 条目**（`CORRECTIONS_ASR.md` **105 868 B** / md5 `b6fd2e14…` / mtime **2026-11-20 15:33** ⇒ 最大 **ASR-066**、无 ASR-067+）⇒ **`last_ack` 保持 `ASR-066`**；**QQ 邮箱无新 ASR 邮件**（最新 = reviewer 的 **APP-121**，11-23 09:03，已于 §89 回复）。🔴 **只读**：未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 `live_caption/`、未改纠偏文件、未改旧章节。明细 `status/asr/notes/asr_s91.md`。
> 🟢 **触发点**：App 在 §90 之后落了 **`88b9ea8`（APP-121 §221，48 文件）** ⇒ 交付面实质变化 ⇒ 本轮逐条只读复核。

- 🟢 **① §89 的 HIGH 缺陷已闭环（本轮独立复现）**：旧包 `v1.1`（后端 md5 **`a92c02f2…`** ＝ 缺陷版）⇒ `app121_asr_npu_longseg_old_v11.json`：**`rc=1`**、`has_valueerror=true`、**字幕 `n_final_lines=0`**、`ValueError: prompt 骨架 281 + 预留 64 > stateful 上界 320`；新包 `v1.1.1`（md5 **`4b43dcbc…`**）⇒ **`rc=0`**、**字幕 `n_final_lines=2` / `n_chars=514`**。🟢 **实现与契约一致**：`asr06b_stateful_backend.py` L583-591 NPU 档 = `allowed_prefix = limit − skeleton`（**不减 reserve**）＋ 只在 `skeleton > limit` 抛错；**GPU 档（L593-598）一字未动**。🟢 **单测** `app121_asr_npu_prefix_unit.json` ⇒ **11/11 PASS**、**含反证组**（旧文件 sha256 `07fff396…`，旧版错抛 2 个「本该通过」用例）；**截断口径一致性 3/3 PASS**。
- 🟢 **② §90 的「zip 必须自证」对新 zip 成立 —— 本轮自己算的**：用 **`pack_v13._acc_module_fingerprints` 同口径**（§90 教训：不手写指纹算法）从 `v1.1.1.zip`（**5 212 403 155 B**）内 `app/` 逐个重算 ⇒ **ok=31 / missing=[] / changed=[] / extra=[]**，zip 内 `app/` 根目录**恰好 31 个 .py**；zip 内 `ACCEPTED.json` `version=1.1.1` 与目录**逐条一致**；权威闸门 `check_acceptance_binding` 对 `v1.1.1` 目录 ⇒ **`ok=True`**（`n_registered=31`/`n_current=31`/`n_changed=0`/`n_missing=0`）。🟢 **`tts_cuda*` 已挪出包外（未删）** ⇒ **ACCEPTED 31 条 == zip 内 31 个 .py**。🟢 **README 的 zip 口径数字是对的**（非缺陷）：「**10 881 文件 / 6 701 780 843 B**」＝**解压后**口径（实测 entries=10881）。🟡 **App 已撤回「机器被占」这个无证据归因**，改记 `synth_rtf P90=1.1126 > 0.75` ⇒ **计时类不作数、计数类成立** ⇒ **ASR 侧不引用 App 的计时数字**。
- 🟢 **③ item 2 的 App 后端三素材 md5 已产出**（§88④/⑤ 撤回后一直缺的替代证据）：`results/app/app121_asr_app_3mat_{NPU,GPU0,GPU0_OLD_v11}.json`，`backend_class` ＝ 包内 `ASR06BStatefulBackend`（**真走 App 代码**），`env.ov_version` ＝ **2026.4.1-22982** ⇒ **OV 口径与 §86/§87 参照一致** ✅。**GPU 档新旧包三素材 md5 逐字节相同**（`d68715df…`/`fbe91f2a…`/`57ce6bc1…`）⇒ **「GPU 档零回归」成立**。**App 侧 NPU md5 ≠ §86 参照** ⇒ **§88④ 撤得对**。
- 🔴 **④ 本轮新发现（ASR 契约层面，此前无人提过）**：**App 侧 NPU 在 ZH 上 `prefix_truncations=3`、GPU.0 同素材 = 0** ⇒ **是设备档差异，不是素材差异**；而 §86/§87 参照（正是 NPU 档、pml=320、OV 2026.4.1）15 臂计数**全为 0** ⇒ ⇒ 🔴 **handoff §四「正常素材不会触发（计数 0）」在 App 生产路径上不成立**；**「计数 0」是 ASR 参照口径（流式前缀几乎为空）的性质，不是 App 路径的性质**。
  - **机理（只读定位，未跑推理）**：**不是** App 的 `allowed_prefix` 口径问题，而是**前缀内容口径不同** —— ASR 参照 `bk_run._prefix_for_chunk` 取**流式解码的 `raw`**（`probe_detail.prefix_len_tokens` 实测 **max=1**、p95=1.0、`n_nonzero=66/797` ⇒ **前缀几乎恒为空**）；App 的 `_finalize()` 传**整段累积文本** ⇒ 前缀**随段内累积文本增长**。🔴 **算术**（`bk_mel.total_aftercnn_len` 同公式）：20.48 s ⇒ 2048 帧 ⇒ 音频 token **266** ⇒ `skeleton=284` ⇒ NPU 档 `allowed_prefix = 320−284 = **36**`；App 的 4 个 20.48 s ZH 段前缀（包内 tokenizer **只 tokenize、无推理**）= **39/43/32/21 token** ⇒ **39、43 > 36 ⇒ 必然触发**；**GPU 档 `allowed_prefix = 512−284−64 = 164`** ⇒ 同样的前缀远不到 ⇒ **0 次** ⇒ **解释「NPU=3 / GPU=0」**。🟡 json 只给总数、未给逐次明细 ⇒ **第 3 次的确切来源未逐次定位**。
  - 🟡 **质量影响本轮未观测到（不能下「丢字」的结论）**：**4 个 20.48 s 长段的 NPU 与 GPU.0 转写逐字节相同（4/4）**；ZH 的 4 处差异（`difflib` 相似度 **0.9975**）**全在 6–11 s 短段**，形态是**同音/近形词分歧** ⇒ ⇒ **当前 NPU↔GPU 差异不能归因于截断**（是浮点分叉）⇒ 属「**机制成立、本轮未见可见损失**」的边界情形；但**风险真实存在**（最长前缀 43 vs 预算 36 ⇒ **已贴边**）。
  - 🔴 **⇒ handoff §三之二 的前提写漏一项**：它写「`base_len ≤ 284 ≤ 320` ⇒ **余量 36 token** ⇒ **永不触发**」⇒ 🔴 **这 36 token 只够骨架、不够带前缀** ⇒ 真正约束应是「**段长上限 ＋ 段内累积前缀 ≤ pml − 18**」⇒ **不是 App 的 bug，是 handoff 前提不完整**。
  - 🟡 **建议（只提方案，不代改 `live_caption/`）**：**①（推荐）`MAX_SEG_SEC` 20 s → ≈19 s**（⇒ `skeleton ≤ 275` ⇒ `allowed_prefix ≥ 45` ⇒ 覆盖实测最长前缀 43）—— **不动 pml、不动 §86 的 RTF 数字、不动 GPU 档**；**②** NPU 档超预算时「丢段尾前缀」而非左截断；**③** 上调 pml —— 🔴 **会改变 §86 全部 RTF 数字 ⇒ 必须重测**。
- 🟡 **⑤ 顺带订正 App §221 §2 的一条归因**：其「**① 切段器不同 ⇒ 段边界与段数本就不一致**」**不成立** —— 实测**段数完全一致**（93/93、65/65、66/66），**逐段边界只差最后一段的起点**；**②「解码入口不同」✅ 属实**、**③「语种注入路径不同」✅ 属实** ⇒ **处置结论（不要求硬凑一致）对，但归因 ① 错**；真正来源是 ③（token 序列不同 ⇒ 贪心解码分叉）＋ ②。
- 🔴 **⑥ 交付纪律（§90 遗留，本轮收窄）**：§90 的「① 重签 ② zip 自证 ③ item 2 补测」**三项本轮确认已闭环** ⇒ **只剩 ④ README 的 `--asr-device NPU` 示例能否给客户**；🔴 **旧 `v1.1.zip`（5 212 356 737 B / 11-22 16:51）仍在磁盘且仍不自证**（本轮复现：zip 内 `ACCEPTED.json` `n_fp=33`，但 zip 内 `app/` **没有** `tts_cuda.py`/`tts_cuda_sidecar.py`）⇒ ⇒ 🔴 **发客户前必须确认发的是 `v1.1.1.zip`，不是 `v1.1.zip`**（v1.1 zip 内后端 md5 = `a92c02f2…` ＝ 缺陷版）。
- 🔴 **动作边界**：未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未改 `live_caption/`、未改纠偏文件、未改旧章节、未代做 App 线程作业。🟡 **留到下一轮（本模块自己的文档）**：改 handoff **§三之二 / §四** 的前提表述（§④）。**产物** `status/asr/notes/asr_s91.md`。
