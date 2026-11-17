# STATUS_APP §213 正文（companion · APP-052④）

> 本文件是 `status/app/STATUS_APP.md` **§213 的正文**（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
> 本轮：**执行 APP-114**（`last_ack` APP-113 → **APP-114**）。

## §213 执行 **APP-114**（last_ack=APP-114，2026-11-17 10:33）｜🔴 **§1 语速上限 2.00× → 1.70×（所有目标语言）**｜🔴 **§2.1 就绪前队列不再「按时间丢弃」**｜🔴 **§3 出 sp5（sp4 逐字节不动）＋ 内嵌 EXT 升 v0.4.16**｜🟢 **§4 三臂 10 分钟验收全部 PASS**｜**未打 zip**｜**本条需等 reviewer 复核**

### ① 纠偏文件只读复核（**SHA 零改动**，全程只读、未入库、未提交）

| 项 | 开工（09:08） | 收尾（10:33） | 结论 |
|---|---|---|---|
| SHA256 | `f1a1f7eebbd3a91fef806feb5dcf31512e014f8380083e3820889f2ba5783a8a` | `f1a1f7eebbd3a91fef806feb5dcf31512e014f8380083e3820889f2ba5783a8a` | **逐字节一致** |
| 字节数 | **381 637 B** | **381 637 B** | 一致 |
| mtime | 2026-11-17 08:12:47 | 2026-11-17 08:12:47 | 一致（**本轮中途无追加**） |
| `## APP-xxx` 条数 | **114 条**（最大 **APP-114**，无缺号无重号） | **114 条**（最大 **APP-114**） | 一致 |

⇒ 本轮**可如实写「SHA 零改动」**（不是「中途被追加」那种情况）⇒ `last_ack` 由 **APP-113 → APP-114**。

### ② §1 要改的内容（**只改这些**）—— 已完成

reviewer 原话：「`time_stretch.SPEED_MAX` 和 `ZH_SPEED_MAX`：**2.00 → 1.70**；`speed_bounds_for_lang()` 改成中文 (1.10, 1.70)、其他语言 (1.00, 1.70)。`tts_worker.py` 里两处兜底 `(1.0, 2.00)` 改成 `(1.0, 1.70)`；`tts_service.py`、`device_config.py`、GUI 提示文字、README 里出现的 2.0×/1.30× 上限说明一起改。」

| # | 文件 | 改动 | 复核 |
|---|---|---|---|
| 1 | `live_caption/time_stretch.py` | `SPEED_MAX` **2.00 → 1.70**、`ZH_SPEED_MAX` **2.00 → 1.70**；`speed_bounds_for_lang()` 随常量 ⇒ 中文 **(1.10, 1.70)**／其他 **(1.00, 1.70)**；docstring 同步 | AST 实测：`(1.1, 1.7)` / `(1.0, 1.7)` |
| 2 | `live_caption/tts_worker.py` | **三处**兜底上限 ⇒ `(1.0, 1.70)`（`_speed_bounds` 异常分支 L3512、`_speed_cap_by_rtf` 异常分支 L3566、命令回填异常分支 L3870） | AST 实测三处均为 1.70 |
| 3 | `live_caption/tts_service.py` | 仅注释同步（行为经 `time_stretch` 统一） | 无行为改动 |
| 4 | `live_caption/device_config.py` | `'tts_speed_max_zh': 2.00 → 1.70` ＋ 键名说明注释 | 实测 1.70 |
| 5 | `live_caption/live_caption_app.py` | §2.1 队列语义（见 ④） | 见 ④ |
| 6 | GUI 提示文字 | 🔴 **无「上限 2.0×」静态文案可改**：GUI 的「语速」只显示**当前倍率值**（`st.set('speed', '语速', '%.2f×' % cur_speed)`，`live_caption_app.py:6860/6891`）⇒ **无需改**；GUI 里的 `2.0×` 出现在**文件回放速度**下拉（`:3107`）⇒ 那是**输入文件节奏**，不是 TTS 语音倍率 ⇒ 按 reviewer「视频播放速度不改」**保留** | `app591_app114_speed_cap_audit.json` → `gui_readme_wording` |
| 7 | README | 🔴 **三个 README（`README_zh.md` / `README_en.md` / `README_perftest.txt`）都没有语速上限说明文本** ⇒ **无需改**（已全文 grep 留证） | 同上 |

🔴 **明文不改的四项**（复核：全部原样）：

| 项 | 值 | 复核 |
|---|---|---|
| 丢句阈值 `tts_late_drop_sec` | **0.0**（不变） | `device_config.py:800` |
| 增益曲线 DEADZONE / 每秒 / 滞回 / 步长 | **3.0 / 0.025 / 2.0 / 0.1**（不变） | AST 实测（`app591_app114_speed_cap_audit.json` → `scopes.A…pkg_speed_constants`） |
| 中文下限 | **1.10**（不变） | 同上 |
| 视频 / 文件回放速度 | 不变 | 见上表第 6 项 |

### ③ §1 的落盘证据：**全文 grep 表 + 总倍率论证**

🔴 reviewer 原话：「**总倍率上限也要是 1.7** …… 请把证据落盘：对 dev 树和 sp4 包内 app 目录全文 grep `2\.0|2\.00|1\.3|1\.30|SPEED_MAX|speed_max|rate`，把命中行列成表，逐行写清是否和播放倍率相关。如果 TTS 合成有语速参数（例如 speaking rate），而且它和 WSOLA 倍率相乘，那么**乘积必须 ≤1.70**。」

**证据文件**：`results/app/app591_app114_speed_cap_audit.json` ｜ **362 856 B** ｜ mtime 2026-11-17 09:35 ｜ SHA256 `94cad9217945a5cd…`（生成脚本 `results/app/_app591_speed_cap_audit.py`）

**四个范围（逐行分类，命中行**全部**列在 json 里）**：

| 范围 | 目录 | 文件数 | 命中行 | 分类统计 |
|---|---|---|---|---|
| **A** | **sp5 的 `app/`（交付包）** | 28 | **251** | speed_cap **37**（含全部是 1.70 常量与沿革注释）／speed_history 6／synth_cfg 5／speed_measure 2／other_numeric 201 |
| **B** | dev 树里**随包的那批**生产模块 | 28 | **251** | 与 A **逐行相同**（dev ⇄ 包 两份副本同源） |
| **C** | dev 树里**不随包**的历史一次性脚本 | 200+ | 397 | other_numeric 366／speed_measure 28／speed_cap 1／speed_history 2 ⇒ ⚪ **不是交付物**（`sync_*` / `diag_*` / `_*_write_status` 等工具与记录），其中「1.00× ~ 1.30×」是**旧 README 补丁脚本的文案** |
| **D** | **sp4 的 `app/`（已冻结）** | 28 | 264 | speed_cap 41 ⇒ ⚪ **sp4 逐字节未动 ⇒ 仍是 APP-113 的 2.00× 口径（预期如此，交付包是 sp5）** |

🔴 **「是否和播放倍率相关」的判定结论**（A 范围逐行核对）：

- **与播放倍率直接相关 ⇒ 全部已是 1.70**：唯一来源是 `time_stretch.SPEED_MAX = 1.70` / `ZH_SPEED_MAX = 1.70`，`device_config.tts_speed_max_zh = 1.70`，worker 三处兜底 `(1.0, 1.70)`；
- **保留不动的 2.00 / 1.30 文字**：全部是**决策沿革注释**（`1.30 → 1.50 → 2.00 → 1.70` 的历史记录，例：`time_stretch.py:9-13/75-79/92/101/106-113`）⇒ 不是活的限速值；
- **与播放倍率无关**：`_TTS_BACKLOG_CLEAR_S = 2.0`（积压清空阈值）、`LAG_HYSTERESIS_S = 2.0`（滞回，reviewer 明文不改）、`cfg_rate / inference_cfg_rate = 0.7`（**扩散采样 CFG 引导率**，不是语速）、采样率 / 超时 / 帧数 / RTF 等普通数字、`live_caption_app.py:3107` 的**文件回放速度**下拉。
- 🔴 **另做了一次「非注释活代码」专项扫描**：交付包 `app/` 里命中 `2.0/1.3/1.30` 的**活代码行只有 30 行**，逐行核对**没有一行是语速上限**（唯一与语速有关的 `device_config.py:795` 值已是 1.70）。

🟢 **总倍率论证（乘积 ≤ 1.70）**（同文件 → `total_multiplier`）：

| 环节 | 证据（文件 + 行） | 结论 |
|---|---|---|
| 变速发生点 | `tts_worker.py`：`StreamWSOLA(speed=_sp)` → `_stretcher.process(w)` | 语音倍率 = `_sp`（自适应值，**上界 1.70**） |
| 合成侧语速参数 | `tts_cuda.py`：`generate_stream(self, text, language, speaker_embed, speaker, split_on_silence, cancel_event, chunk_frames, max_new_tokens, est_sec, **_kw)`；`tts_engine.py`：`generate_stream(**kwargs)` | 🔴 **没有 speed / rate / speaking_rate 参数** ⇒ 合成侧速率恒为 **1.0×** |
| `cfg_rate` 是什么 | `tts_worker.py` `inference_cfg_rate=0.7` / `tts_engine.py` | ⚪ **扩散采样 CFG 引导率** ⇒ **不与 WSOLA 相乘** |

⇒ 🟢 **总倍率 = 合成侧速率 × WSOLA 倍率 = 1.0 × ≤1.70 = ≤1.70** ⇒ 满足 reviewer 的「乘积必须 ≤1.70」。

### ④ §2.1「120 s 溢出丢弃」与「一句不丢」的冲突 —— 已修

reviewer 原话：「改成：**只有 TTS worker 明确失败或退出时才清空队列，并计数、在 GUI 上显示**；正常加载慢的时候**不按时间丢句**。」

| 改动点 | 内容 |
|---|---|
| `live_caption_app.py` `_TTS_QUEUE_OVERFLOW_S` | **120.0 → `None`**（= **不设时间上限**）⇒ 旧阈值**删除** |
| `TtsReadyQueue.enforce_overflow()` | `overflow_s is None` ⇒ **直接返回、不丢弃**（方法保留，调用点不变） |
| `TtsReadyQueue.clear_on_worker_failure(reason)`（**新增**） | **唯一**允许丢弃排队句的路径：清空队列 ＋ 计数 `n_drop_worker_failed` ＋ 日志 |
| GUI 状态条 | `'%d（就绪前排队 %d / worker失败丢弃 %d）'`（原「溢出丢弃」改为「worker失败丢弃」） |
| CLI 主循环 | 每拍检查 `tts.state == 'error'` ⇒ 调 `clear_on_worker_failure()` |
| CLI 结算行 | `[APP-113] … ｜ worker失败丢弃=N ｜ …`（**新字段**，验收脚本已解析） |

🔴 **为什么删掉时间阈值而不是调大**（reviewer 给的第二个选项是「保留但 ≥600 s」）：§212 实测**冷启动臂 TTS 就绪用了 120.1 s** ⇒ 旧阈值 120 s **正好压在线上**；而 B 机/更冷机器只会更慢 ⇒ 任何固定阈值都是「赌机器够快」。改成「**只有 worker 失败/退出才清空**」⇒ **「一句不丢」成为结构性保证**，与机器冷热无关。

🟢 **行为级判据（真跑被测包的代码，不是 grep）**：验收脚本的 preflight 里有一个**队列探针**（`AST 直读包内 `live_caption_app.py` → 取 `TtsReadyQueue` / `_TTS_QUEUE_OVERFLOW_S` / `_TTS_BACKLOG_CLEAR_S` → `exec` 后真跑）：

| 步骤 | 期望 | 实测（三臂全部一致） |
|---|---|---|
| 入队 5 句 ⇒ 把入队时刻改到 **300 s 前**（> 旧阈值 120 s） | **仍保留 5 句、丢弃 0** | **保留 5 / 丢弃 0** ✔ |
| `clear_on_worker_failure()` | 清空 5 句 ＋ 计数 5 | **清空 5 / 计数 5** ✔ |

### ⑤ §2.2 / §2.3 / §2.4 验收侧的判据修正（**复用同一个脚本，未新建闸门/矩阵/判据脚本**）

| reviewer 要求 | 处置 | 落点 |
|---|---|---|
| §2.2「每臂的产物文件名都要带时间戳或 run 编号，**禁止覆盖**」 | 产物名改为 `_app591_<tag>_run<YYYYMMDD-HHMMSS>_*`；**启动前断言产物不存在**（存在即 FAIL，不覆盖） | `results/app/_app588_sp4_acceptance.py` |
| §2.3「抽听样本改成按**实际倍率的真实标注**」 | 抽样只取 **1.60–1.70× 目标档**；**没有命中时回落为「倍率最高的 N 句」并明确标注「不得当作 1.6–1.7× 样本解读」**；每个样本写 `speed` / `speed_label`（真实倍率） | 同上（`extract_fast_wavs`） |
| §2.4「附上每句倍率的**直方图**（或排序后的前 15 个值），说明为什么相等」 | 结果 json 增 `speed_histogram`：**分箱直方图 ＋ 排序前 15 ＋ `n_at_max` ＋ `p95_equals_max` ＋ 自动生成的「为什么 P95= max」说明** | 同上（`speed_histogram`） |
| §4「lag max / lag end / 积压清空时刻 …… **lag 数字只报告，不设判定门槛**」 | 🔴 **修掉继承自 APP-113 的判据错误**：原脚本把「积压清空时刻已记录」当 **FAIL 项** ⇒ 改为 **报告项**（`report_only=True`，不进 `n_fail`），并在 `required_report` 汇总 reviewer 明确要求「报」的指标 | 同上（`checks` / `reports` / `required_report`） |

🔴 **一次假 FAIL 的发现与处置（诚实记录）**：第一轮 zh/en 臂（run `…094715` / `…095732`）用的是**判据修正前**的脚本 ⇒ zh 臂因此 **FAIL 1 项**（唯一 FAIL 项 = 「积压清空时刻已记录」；**该臂的 run log 里 `积压清空=—`** ⇒ 本臂积压**在 600 s 内没有回落到 <2 s**（lag 末值 5.073 s）⇒ 是**判据把「lag 数字」当门槛**，不是产品缺陷）。处置：**改判据 ⇒ zh/en 两臂**在最终代码上**整体重跑**（run `…100823` / `…101859`）⇒ **不是**沿用上一轮结果、也**不是**改结论。**旧的两轮产物全部保留在盘上**（run 号不同 ⇒ 天然不覆盖），可对照。冷启动臂（run `…093348`）跑在判据修正前，但**它通过了更严的全部 12 项** ⇒ 在新判据下同样成立。

### ⑥ §3 出包：**选 sp5**（**sp4 逐字节不动**）＋ 内嵌 EXT 升 **v0.4.16**

reviewer 给了两个分支：「并入 sp4：在 sp4 目录里重新同步 app 文件。**如果你那边已经把 sp4 冻结，就出 sp5，sp4 逐字节不动**。在 STATUS 里写明选了哪一个。」

🟢 **本轮选 sp5**，理由三条：

1. 🔴 **sp4 的包内容已被两处证据绑定**：`app587_specialmvp_sp4_build.json` → `app_sync.synced`（`live_caption_app.py` sha256 `ef367412…`）＋ §212 的三份验收 json（都跑在 sp4 上）⇒ **原地改 sp4 会让这些证据不再描述磁盘上的 sp4**（APP-206/207/208 的「证据必须同时绑『包身份』+『包内容』」）；
2. APP-055：**旧版本目录不覆盖不删**、**不原地改包**、只打新版本号；
3. reviewer 明文允许这一分支。

🔴 **sp4 逐字节未动的实证**（收尾实测）：

| 项 | app587 记录（11-16 20:28） | 本轮实测（11-17 10:33） | 结论 |
|---|---|---|---|
| 文件数 / 总字节 | 41 374 / **14 232 064 511 B** | 41 374 / **14 232 064 511 B** | **一致** |
| `app/live_caption_app.py` sha256 | `ef367412632ad774…` | `ef367412632ad774…` | **一致** |
| `app/time_stretch.py` | 含 2.00（APP-113 口径） | 含 2.00 | **未动**（预期） |

**构建证据**：`results/app/app591_specialmvp_sp5_build.json` ｜ **12 904 B** ｜ mtime 2026-11-17 09:29 ｜ SHA256 `f1ab389d61070862…`（脚本 `results/app/_app591_build_specialmvp_sp5.py`）｜ verdict **PASS**（43.1 s）

| 构建动作 | 结果 |
|---|---|
| 拷贝 sp4 → sp5 | robocopy rc=1 ⇒ **41 374 文件 / 14 232 064 511 B**（与 sp4 相同） |
| 路径重定位 | `cuda_env/pyvenv.cfg`（×4）、`app/MANIFEST.json`（×1）⇒ **无残留 sp4 路径** |
| **EXT v0.4.8 → v0.4.16** | `git archive 7a92f12`（`live_dub_ext`）⇒ **43 个文件**写入 `ext/bridge/` ＋ `ext/extension/` ＋ `ext/USER_GUIDE.md`；`ext/release.json` 记 version **0.4.16** / commit **`7a92f12a7d83dd8e9c196d4181617d509b7d1113`** / 逐文件 sha256；App 侧垫片（`ext/version.py` / `app_root.py` / `utf8_io.py` / `bridge/__main__.py`）**保留**；`ext/bridge/tts_cuda_sidecar_ext.py` 沿用 v0.4.8 的嵌入清单（**不新增**，包内无对应文件且仅被注释引用） |
| app 代码定点同步 | **5 个文件**（`live_caption_app.py` / `time_stretch.py` / `tts_worker.py` / `tts_service.py` / `device_config.py`）逐文件 sha256（dev = 包内）；**其余 23 个 .py 与 dev 逐字相同** |
| 包级 `release.json` | version `1.0-sp5`；`corrections` += **APP-114**；`ext` = 0.4.16 / commit；新增 `sp5_changes`（4 条） |
| README 包体积行 | 按实测值改写（41 374 文件 / 14 232 088 734 B / 13.255 GiB；zip 仍「待打包」） |
| 闸门 | `.pyc` **0**；黑名单（`bridge_token*` / `*.pid` / `*.log`）**0**；app 与 dev 不一致 **0**；`pyvenv.cfg` 含 sp5 路径且**不含** sp4 路径；`MANIFEST.json` 同；`profile=specialmvp`、`allow_cuda=true`；**包内 `SPEED_MAX=1.70` / `ZH_SPEED_MAX=1.70`**；**增益曲线四项原样**；**`_TTS_QUEUE_OVERFLOW_S = None`** ⇒ **verdict PASS** |

🔴 **未打 zip**（APP-114 §3「验收通过前不打 zip」＋ 用户级纪律）⇒ `shared/specialmvp/` 下**仍只有 sp1 的 zip**（14 244 490 059 B，11-13 21:24）⇒ **sp4 / sp5 都没有 zip**。

### ⑦ §4 三臂 10 分钟验收（SPE 0–600 s，持 MACHINE_LOCK，锁证据进 json）

🔴 **三臂全部 PASS**（判定项：丢句=0 / 译文==进TTS / 排队==补发 / max≤1.70 / rc=0 / 产出齐备 / 无重复 id / 就绪时刻已记录 / 并行生效 / preflight / 队列探针；**lag 类只报告**）：

| 臂 | 证据 json（run 号 ⇒ 产物不覆盖） | verdict | 丢句 | 译文==进TTS | 排队==补发 | **speed max** | p50 / p95 | ≥1.6× | TTS 就绪 | ASR 就绪 | 边车加载 | lag max / end | 积压清空 | `timing_valid` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **冷启动（zh）**（`ov_cache` 已挪开 14.2 GB） | `app591_acceptance_sp5_cold_zh_run20261117-093348.json` ｜ 21 616 B ｜ sha `991f84dcd3aa6ee0…` | **PASS**（12/12） | **0** | 164 == 164 + 0 | 12 == 12 | **1.5804** | 1.145 / 1.5798 | 0 | **61.2 s** | 27.9 s | 44.1 s | 32.837 / 4.491 | 74.6 s | **True** |
| **中文目标（zh）** | `app591_acceptance_sp5_zh_run20261117-100823.json` ｜ 22 411 B ｜ sha `ad284921a7711a22…` | **PASS**（11 判定项 + 1 报告项） | **0** | 164 == 164 + 0 | 10 == 10 | **1.70** | 1.4811 / 1.6672 | **26** | 34.3 s | 4.9 s | 23.3 s | 103.622 / 22.756 | **未清空**（末值 22.756 s） | **True** |
| **英文目标（en）** | `app591_acceptance_sp5_en_run20261117-101859.json` ｜ 22 638 B ｜ sha `d20a438657143295…` | **PASS**（11 判定项 + 1 报告项） | **0** | 164 == 164 + 0 | 10 == 10 | **1.2866** | 1.0069 / 1.2793 | 0 | 31.3 s | 4.4 s | 23.1 s | 25.027 / 4.592 | 81.2 s | **True** |

🔴 **锁证据**（reviewer 要求「结果 json 里写锁内容和取锁、放锁时刻」）：三臂的 `lock_evidence` 均有 `lock_content`（`app <pid> <时间> app114-<lang>`）＋ `acquired_at` ＋ `released_at` ＋ `lock_content_at_release`；冷启动臂 `waited_s=0`（本轮自持）。

🔴 **§2.4 的「P95 为什么等于 max」—— 本轮三臂的回答**（`speed_histogram`）：

- 冷启动臂：164 句 / **9 个分箱**；max 1.5804（**4 句**在 max 档）⇒ P95 1.5798 < max ⇒ **未相等**；排序前 15 = `1.5804 ×4, 1.5798 ×8, 1.5592 ×2, 1.4937`；
- 中文臂：164 句 / **10 个分箱**；max **1.70**（**5 句**在 1.70 档）⇒ P95 1.6672 < max；排序前 15 = `1.70 ×5, 1.6672 …`；
- 英文臂：164 句 / **6 个分箱**；max 1.2866（**9 句**在 max 档）⇒ P95 1.2793 < max。
⇒ §212 那个「P95 == max」的现象**不是统计口径错**，而是**多句停在同一个最高倍率** ⇒ 本轮把「停在最高档的句数」`n_at_max` 也一并落盘，可直接核对。

🔴 **三臂的原始产物原样留在 `results/app/`（run 号 ⇒ 不覆盖）**：

| 臂 | tts.jsonl | backlog_curve.csv | run log |
|---|---|---|---|
| 冷启动 | `_app591_sp5_cold_zh_run20261117-093348_tts_out.wav.tts.jsonl` ｜ 256 804 B ｜ sha `c43098f7598af5a1…` | `…backlog_curve.csv` ｜ 18 054 B ｜ sha `fc7fe55f2e8bb372…` | `…093348.log` ｜ 281 300 B ｜ sha `c892660fb09d7fa8…` |
| 中文 | `_app591_sp5_zh_run20261117-100823_tts_out.wav.tts.jsonl` ｜ 257 867 B ｜ sha `918ef6b423c7619b…` | `…backlog_curve.csv` ｜ 19 663 B ｜ sha `7a1777a6aab0bbd2…` | `…100823.log` ｜ 303 324 B ｜ sha `0597b13d4da8ec25…` |
| 英文 | `_app591_sp5_en_run20261117-101859_tts_out.wav.tts.jsonl` ｜ 255 808 B ｜ sha `ca56027a3d6ed005…` | `…backlog_curve.csv` ｜ 17 031 B ｜ sha `8835e475bc823e76…` | `…101859.log` ｜ 280 054 B ｜ sha `980ac1def1b2d351…` |

（判据修正前的两轮 zh/en 产物同样保留：`…094715` / `…095732`。）

### ⑧ 抽听样本（**真实倍率标注**）

🟢 **中文臂命中目标档**：1.60–1.70× 共 **26 句** ⇒ 抽出 3 段**真实倍率 1.7000×**（`results/app/_app591_fast_samples/`）：

| 文件 | 倍率 | 文本 | 字节 |
|---|---|---|---|
| `_app591_sp5_zh_run20261117-100823_fast_id138_speed1_70.wav` | **1.7000×** | 但为了继续前进，一些我们目前没有的能力也是必要的。 | 141 164 |
| `_app591_sp5_zh_run20261117-100823_fast_id139_speed1_70.wav` | **1.7000×** | 我们不得不继续调整我们的策略。 | 79 244 |
| `_app591_sp5_zh_run20261117-100823_fast_id140_speed1_70.wav` | **1.7000×** | 组织旨在了解我们如何为未来的发展提供动力。 | 138 284 |

⚠️ **冷启动臂 / 英文臂没有 1.60–1.70× 的句子**（冷启动臂 max 1.5804×、英文臂 max 1.2866×）⇒ 按 §2.3 **如实标注**：抽的是「倍率最高的前 3 句」，真实倍率分别是 **1.5804×**（冷启动臂）与 **1.2866×**（英文臂），**不得**当作 1.6–1.7× 样本解读。

### ⑨ 未结项（**单列，不并入 PASS**）

1. 🔴 **英文目标臂没能摸到 1.6–1.7×**（max 1.2866×、≥1.6× **0 句**）：英文目标下限 1.00×、本臂 lag max 仅 25.0 s ⇒ 自适应倍率上不去 ⇒ **英文侧的「1.7× 听感」本轮未验证**。
2. 🔴 **冷启动臂的 TTS 就绪是 61.2 s，**不是 reviewer 假设的「约 120 s」⇒ 「TTS 就绪 120 s 时丢句仍为 0」这一**具体数值场景未复现**；但 §2.1 的保证是**结构性**的（**无时间阈值**）＋ 队列探针证明「300 s 过期仍不丢句」⇒ 该风险的**机制**已被消除。
3. 🔴 **中文臂积压未回落到 <2 s**（lag 末值 22.756 s）⇒ 「积压清空时刻」本臂**未产生**（已按 reviewer「lag 只报告」处理）⇒ 追赶速度是否够，属**用户听感判断**，本模块不自行下结论。

### ⑩ 本轮纪律

🔴 **未打包**（sp4 / sp5 均无 zip；`shared/specialmvp/` 仍只有 sp1 的 zip）｜🔴 **未改 `CORRECTIONS_APP.md`**（只读；SHA 零改动；**未入库、未提交**）｜🔴 **未改 sp4**（逐字节未动，已实测）｜🔴 **未新建闸门/矩阵/判据脚本**（APP-110 §1）：验收**复用** APP-113 的 `results/app/_app588_sp4_acceptance.py`（只改判据本身）；新增的两个脚本是 **构建脚本**（`_app591_build_specialmvp_sp5.py`）与**只读审计脚本**（`_app591_speed_cap_audit.py`）｜🔴 **未调 MiniMax**（质量判定留给 reviewer 回转写）｜🔴 **未吞其它模块的改动**（只提交 App 侧文件；`status/app/CORRECTIONS_APP.md`、`results/app/app157_*` / `app468_*` / `app523_*` 等历史脏条目**一律未提交**）｜🔴 设备作业全程持 `MACHINE_LOCK`（三臂各持一次，取锁/放锁时刻已落盘）｜🔴 本机安全删除 shim ⇒ **全程只改名挪开、不删文件**（冷启动臂把 `ov_cache` 改名挪开 14.2 GB，**旧副本仍在** `%LOCALAPPDATA%\Confucius4LiveCaption\ov_cache.app591_coldarm_20261117`，可回滚；**未删**，等 reviewer 同意后再清理）。
