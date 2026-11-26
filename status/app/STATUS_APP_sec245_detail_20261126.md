# STATUS_APP §245 — 接续上一会话（TAKEOVER）｜闭合 §244 断点：排空判据缺陷 → 三轮全部 PASS → 抽听样片 ＋ 交付面清洗

> 本轮 `last_ack` **不变（仍 APP-151）**——`CORRECTIONS_APP.md` 无新编号（27 323 B／SHA256 `1f92a2d3…`／mtime 2026-11-26 16:14:36，与 §244 收尾一致）。

## §0 本轮性质与断点

| 项 | 值 |
|---|---|
| 租约 | `acquire app` ⇒ **TAKEOVER stale lease** `87a7f1ef`（心跳停在 18:28:05，登记 PID 15196/15336 **全部 err=87 已死**）⇒ 新 TOKEN `13160ba5` |
| 上一会话留下的断点 | 租约 note 原文：**「EXT 同步核对 0 真差异；冒烟重新排队等锁」**；§244 companion 的 §7 第 2 条「三轮重跑」未做 |
| 读到的现场 | `results/app/app149_three_arms.json`（**19:14:24** 落盘）＝上一会话其实已跑三轮，但 `gate_all_pass=false`、三臂 `drained_to_zero` 全 False、`arm_done rc=2` |
| 六通道复核 | 纠偏文件无新编号；`CORRECTIONS_APP.md` 收尾四项指纹不变 ⇒ **本轮不执行新纠偏，只闭合断点** |

### §0.1 🔴 上一轮三轮为什么全 FAIL（根因，不是产品缺陷）

三臂的 `drain` 原始字段完全一致：

| 字段 | 值 |
|---|---|
| `drain_elapsed_sec` | **10.02 / 10.02 / 10.04**（`drain_cap` = 300） |
| `disconnected` | `TimeoutError('stats 未在 10.0 s 内返回（桥接可能卡住）')` |
| `drain_hard_cap_hit` | False（硬上限 312 s **根本没到**） |
| `n_pending_after_drain` | **8 / 26 / 47** |
| `n_pending_series` | **空列表**（一次都没成功记到采样点） |

而 **`bridge.log` 证明桥接没卡死**：`bgkeep_off` 在 `18:51:23` **一次性补出剩余 10 段**，
`dubs` 最终 **123 = `n_submitted` 123**；`stats_full.pipeline.n_pending` 末值 **0**。

⇒ 根因：`_app137_e2e_drain.drain_until_zero()` 把**一次 stats 接收超时**当成断连并 `break`，
而片尾 NPU TTS 清 backlog 时 WS 应答被压在 10 s 之外 ⇒ **排空整段放弃** ⇒
`drained_to_zero` 恒 False ⇒ APP-150 §2 门禁**永远过不了**，v1.2 打不出来。
（APP-143 b ③ 原文是「超时/断连 ⇒ 如实记录后退出」，本意是防 65 分钟挂死；但 ② 的**墙钟硬上限**已经在兜底，③ 不该再一刀切。）

## §1 修法（`live_caption/_app137_e2e_drain.py`）

| 改动 | 内容 |
|---|---|
| 单次 stats 超时 | **继续排空**（`continue`），不再 `break` |
| 记录 | 新增 `drain_timeout_events`（每次超时的 `rel_sec` / `elapsed_in_drain_sec` / `msg`），`stats_timeout_count` 照旧；`run_drain` 的 `drain{}` 透传该字段 |
| 兜底 | 超时分支里**也**检查墙钟 `hard_cap`（`drain_cap + stats_timeout + 2`）⇒ 到点 `drain_hard_cap_hit=True` 退出 ⇒ **APP-143 b ② 不破** |
| 真断连 | 非 `TimeoutError` ⇒ 立即退出（原行为） |
| `disconnected` | 排空成功时保持 `None`（不把「中途超时」误报成断连）；只有硬上限退出时填最后一次超时 |

改动方式：`app245_patch_drain_timeout.py`（备份 → 内存里跑 8 条真不变量 → 临时文件 → `os.replace`）。
写前 8/8 不变量：纯 LF、无 TAB、行数 +22、旧锚点消失、新锚点各 1 次、文件头未动、`ast.parse` OK、**反证组**（还原成 break ⇒ 文本必须不同）。
写后：23 035 → 24 536 B／477 → 499 行／`sha256 587fe119…`。

### §1.1 行为级验证（`_app245_verify_drain_timeout.py`，5/5 PASS，**含反证**）

| 判据 | 结果 |
|---|---|
| `tolerate_one_timeout_then_drain` | **PASS** `drained=True`、`n_timeouts=1`、`disconnected=None`、`elapsed=1.21 s`（hard_cap 33 s） |
| `old_code_fails_same_scenario`（**反证**） | **PASS** 还原成 `break` 的旧逻辑同场景 `drained=False`、`n_pending=2`、`elapsed=1.01 s` ⇒ 判据**有鉴别力** |
| `hard_cap_still_enforced` | **PASS** 永远不回 ⇒ `drain_hard_cap_hit=True`、4.07 s ≤ 3.5+1.5 s |
| `real_disconnect_exits_fast` | **PASS** `ConnectionResetError` ⇒ 0.00 s 退出、`n_timeouts=0` |
| `field_passthrough_drain_timeout_events` | **PASS** `drain{}` 含该字段 |

证据：`results/app/app245_drain_timeout_verify.json`。
**APP-143 b 回归**（`_app143b_timeout_counterexample.py` 原样重跑）4/4 PASS：新逻辑 **43.1 s** 退出 ≤ 上限 50 s（cap 30 + timeout 10 + 10），`stats_timeout_count=4`，旧版仍挂死 ⇒ **APP-143 b 的保证没被破坏**。

## §2 三轮重跑（`_app245_run_three_arms.py`，新目录 `three_arms_r245/`，旧证据不覆盖）

配置同上一轮：候选 `MiniMVP v1.2.candidate` ＋ EXT v0.4.23、10 分钟片段、`drain-cap 300`、`tail-wait 30`、
`EXT_TTS_DEVICE=NPU｜EXT_MT_DEVICE=GPU.0`、**候选目录自带 python 起桥接**、**每次实测都自己拿 MACHINE_LOCK**。

| 臂 | rc | 用时 s | dubs | 丢句 | 排空 | 积压段(媒体末) | 排空用时 s | 容忍超时次数 |
|---|---|---|---|---|---|---|---|---|
| 背景音关 | **0** | 715.3 | **123** | 0 | **True** | 18 | **84.3** | 7 |
| 背景音开 | **0** | 747.5 | **123** | 0 | **True** | 26 | **116.6** | 9 |
| 背景音开＋克隆 | **0** | 809.1 | **170** | 0 | **True** | 47 | **177.8** | 14 |

三臂 `lock_lost=0`、`waited_s=0`、`arm_done rc=0`。门禁首轮：**3/3 PASS**（`app245_three_arms.json` 的 `gate_all_pass=true`）。

### §2.1 APP-150 §2 逐项（`_app245_gate_metrics.py` ⇒ `results/app/app245_gate_metrics.json`）

| 门禁项 | 关 | 开 | 开＋克隆 |
|---|---|---|---|
| `n_error` = 0 | **0** | **0** | **0** |
| asr / mt / tts 段数 | 123/123/123 | 123/123/123 | 168/168/**167** |
| 丢句（mt 段 − dubs） | 0 | 0 | 0 |
| `tts_runaway`（APP-130 早停） | 0 | 0 | 0 |
| 撞 39 s 帧上限句数 | **0** | **0** | **0**（逐句 `tts_sec` 最大 **15.26 s**） |
| NaN / Inf 句数 | 0 | 0 | 0（`NaN 守卫已装 2 个` 是**安装行**，已排除） |
| 削波（混音 \|x\|≥0.999 采样点） | 0 | 0 | **0 / 28 800 000** |
| 最大语速倍率 | **1.7** | **1.7** | **1.7**（贴上限句数 99/115/167） |
| `synth_rtf` | 0.9834 | 1.0408 | 1.0547 |
| 进程内存 MB | 7 949 | 8 062 | 8 504 |
| `npu_pct`（末次采样） | 0.0 | 69.1 | 47.5 |

**逐句滞后**（`dub_late_final_summary`）：p50 **29.2 / 51.2 / 95.0 s**、p90 **100.6 / 166.9 / 274.2 s**、
最大 **160.8 / 224.8 / 337.9 s**。

**cp 自检与落点**（原文，三臂一致）：
`cp_prefill: NPU 自检通过（耗时 0.079–0.085 s，用例 [(0.02, 0.998595), (0.1, 0.99931), (1.0, 0.999953)]）`、
`cp_decode: NPU 自检通过（0.048–0.064 s，[(0.02, 0.999438), (0.1, 0.999718), (1.0, 0.999952)]）`、
`各组件落点：cp_decode=NPU，cp_prefill=NPU，decoder_bucket@38=NPU，speaker_enc=NPU，talker_bucket@64/128/256/384/512=NPU，tok_decoder=NPU(lazy)`、
`落点统计：NPU 上 9 个组件；CPU 上 0 个组件 []`；`NPU_TURBO=True` 9 行、`turbo 已生效：YES` 7 行。
MT 就绪原文：`MT 就绪（Hy-MT3 INT8 @ GPU.0，2.1s／2.1s／2.6s）`；ASR 就绪：`ASR 就绪（Qwen3-ASR 0.6B INT8 @ GPU.0，…）`。

## §3 APP-148 §1c 抽听样片（`_app245_extract_samples.py`）

| # | 起点 | 时长 | OGG 字节 | 编码 |
|---|---|---|---|---|
| 1 | 93.3 s | 40.0 s | **117 114** | Ogg/**Opus** 16 kHz |
| 2 | 280.0 s | 40.0 s | **120 347** | 同上 |
| 3 | 466.7 s | 40.0 s | **122 633** | 同上 |

源＝clone 臂 `player_mix.wav`（**播放端真正听到的混音**，48 kHz/2ch/600 s）。
附带统计（`margin.json` 的 `per_segment`，170 段）：撞 39 s 上限 **0**、NaN/Inf **0**、语速最大 **1.7**；
混音削波 **0 / 28 800 000** 采样点。证据：`results/app/app245_listen/app245_listen.json`。

### §3.1 🔴 本轮抓到的两个真缺陷（都影响这条任务）

1. **`_app148_extract_samples.py` 读 10 分钟混音会静默崩溃**：它用 `array` + Python float 列表读
   2 880 万帧 ⇒ 实测 **rc=127、无 traceback**。改用 numpy（≈230 MB）后正常 ⇒ 新写 `_app245_extract_samples.py`。
2. **本机 libsndfile 1.2.2 的 VORBIS 编码器爆栈**（`Windows fatal exception: stack overflow`，
   rc=`-1073741571`）：**按样本数**有阈值 —— 48 kHz 10 s 可以、**20 s 崩**；16 kHz 30 s 可以、**40 s 崩**；
   而 **OPUS 16 kHz 40 s 正常**。证据 `results/app/app245_ogg_threshold.json`。
   ⇒ 本轮样片改用 **Ogg/Opus**（仍是 `.ogg`，40 s ≈ 120 KB ≪ 1 MB）。
   🔴 这条也解释了 §230 登记的「OGG 编码器不可用」——不是没装，是**大块写会爆栈**。

## §4 交付面清洗（§244 白名单漏项）

### §4.1 🔴 白名单原来只有 18 条 ⇒ **漏查备份文件**，实测包里躺着 **32 个 `*.bak_*`**

含 `app/translator.py.bak_app151`（改之前的**旧版 translator**）、`ext/bridge/engine_runtime.py.bak_app149_v0423` 等，
会**随 zip 发给客户**。

处理：`app245_move_pkg_baks.py` **只移不删** ⇒ `C:\Users\Trekker-PTL\shared\pkg_baks_20261126\`（32 个，
逐个比 size + sha256，`verified=true` 32/32，包内残留 0）。证据 `results/app/app245_pkg_baks_move.json`。

### §4.2 白名单补第 ⑨ 条并重跑 ⇒ **19/19 PASS**

`_app150_zip_whitelist.py`：新增「无备份/临时文件（`*.bak*` / `*.overwritten*` / `*.tmp`）」＋
输出路径可用 `APP150_OUT` 覆盖（**重跑不覆盖 §244 的 18/18 证据**）。
重跑结果：**19 PASS / 0 FAIL**（`results/app/app245_zip_whitelist.json`）。

## §5 README 按实测改写（APP-150 §2 末条）

上一版写「10 分钟连续讲话实测，最大滞后约 **45 s～2 min**」——本轮实测**最坏 161 / 225 / 338 s**，
**明显超过** ⇒ 按 reviewer 要求改写（`app245_readme_lag.py`，先备份、纯 LF 保持、写后逐字节复核）：

* `README_zh.md` 31 264 → **31 554 B**：滞后中位数 **29 / 51 / 95 s**，最坏 **161 / 225 / 338 s**，
  媒体结束后 **1.4～3.0 分钟**才播完积压；并给出「关背景音／不用克隆」两个可操作的缓解项。
* `README_en.md` 33 975 → **34 476 B**：Known limitations 段新增同口径英文条目。
* 备份移到包外（见 §4.1）。

## §6 结论（可交付口径）

* APP-147 自查条件 **1（三轮 rc=0 / lock_lost=0 / 排空为 0）✅**、**2（MT3 就绪 ＋ turbo 实际值）✅**、
  **3（包内 mt3-only／克隆空／无音视频／无 CUDA DLL／模型身份）✅**；
  APP-148 §1a ✅（§244 已有 6 组 hex）、§1c ✅（本轮）、§1b **待打 zip**；
  APP-150 §1 ✅（19/19）、§2 ✅（上表）、§3 ✅（§244）、§4 ✅（APP-143 a/b ＋ EXT 全量单测，§243/§244）；
  APP-151 ✅（§244）。
* 🔴 **仍未打 zip、未签 ACCEPTED**：APP-147 第 5 步要求「三轮通过后直接打 zip」，
  但用户级纪律是**未经用户明确要求不主动打包** ⇒ 本轮**停下问用户**，不自行吃版本号。

## §7 未完成 / 待裁定

1. 🔴 **等用户一句话**：是否现在就打 `Confucius4_LiveCaption_MiniMVP_v1.2.zip`
   （APP-147 已授权「三轮过了就打」；用户级纪律要求先问）。打之前只剩 APP-148 §1b（zip↔目录比对）
   ＋ 解压到临时目录跑 `--check` 两项，打完即可闭环。
2. 🔴 **滞后必须让用户知道**：默认 TTS=NPU 档在本机连续讲话时**中位 29 s、最坏 5.6 min**，
   与 v1.1.1 说明书的 1–2 min 差一个量级（TTS 不能放 GPU.0 —— §240 的结论仍然有效）。
   README 已如实改写，是否在发客户说明里再加一段由用户定。
3. 🔴 **B 机复验仍未做**（APP-147 已明确不挡发版）。
4. 🔴 **clone 臂 tts 段数 167 / mt 168**：差 1 段（`n_emitted=170`、丢句 0）⇒ 属分段口径，
   已在门禁里按「丢句 = mt−dubs」判；若要逐句追平需要 EXT 侧加段级对账（未做）。

## §8 纪律自查

| 纪律 | 结果 |
|---|---|
| 租约 | 🟢 TAKEOVER → 每步 `beat`（**带 token**）→ 收尾 `release` |
| 机器锁 | 🟢 三轮各自由驱动器 `acquire/release`（`waited=0`、`lock_lost=0`）；**不在锁外跑计时** |
| 只追加 `## §N` | 🟢 只加 §245 指针行；旧章节一字未改（`§241/§243/§244` 原样） |
| `CORRECTIONS_APP.md` | 🟢 只读未改（27 323 B／`1f92a2d3…`／mtime 16:14:36） |
| 证据 | 🟢 每个数字都给结果文件＋原始字段 |
| 不打包 | 🟢 未打任何 zip、未签 ACCEPTED、未改旧客户包 |
| 客户包改动 | 🟢 仅 `.candidate`（README ＋ 移出 32 个 .bak），旧包未动 |
| 未连 B 机／未调 MiniMax | 🟢 |

## §9 本轮踩到的两个坑（给下一轮）

1. 🔴 **`session_lease.py beat` 的参数顺序是 `<module> <token> [note]`**：把 note 当 token 传 ⇒
   脚本打印 **`LOST lease`**（假丢锁）。判定前先看租约文件里的 `token` 是否仍是自己。
2. 🔴 **管道下崩溃会吞掉全部 stdout**：脚本前几行 `print` 都看不到 ≠ 没执行到；要用 `-u`
   ＋ `-X faulthandler` 才拿到 `Windows fatal exception: stack overflow` 的真位置。
