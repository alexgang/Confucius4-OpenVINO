# STATUS_APP §230 · 执行 **APP-131 / APP-132 / APP-133**（v2.6 最终交付：EXT **v0.4.21 / b2a4978** ＋ **一次持锁到底**重跑整链）

- 日期：2026-11-24（本轮实跑）
- `last_ack`：APP-130 → **APP-133**
- 纠偏来源：**局域网** `status/app/CORRECTIONS_APP.md`（APP-131/132/133 三条同在）＋ **QQ 邮箱** `alexchen7694@agent.qq.com`（`msg_ikwZH3hFJQ84g3LmdIwtlowZhpr-vcalHHNyyG-DtX1QAA`＝APP-131；`msg_WCFDSHflL8ZKI41A6vd5NXSixhH-AAdKoCmtSjLtkZlU5g`＝APP-132；`msg_HbiVRXlgp8eXsg7kDK4uUcgmLi_ao2pMbVJcZzbdbNhmGw`＝APP-133）⇒ **同一编号两个通道都到 ⇒ 只执行一次**。

## §1 APP-133：v2.6 的 EXT = **b2a4978（v0.4.21）**

reviewer APP-133 原文：
> **v2.6 的 EXT 改用 b2a4978**（替代 APP-131 的 4740b06）；验收第 1 项 `tests/test_ext0420_clone_gender.py` 应 **16/16**；clone 臂请报 `stats_full.clone_reasons` 与 `n_gender_splits`。……注意 APP-132：整条链一次持锁到底；你 13:08 起的那一臂未完成，重跑时直接用 b2a4978。

⇒ **版本链**：APP-129 `3573b2d`（v0.4.19）→ APP-131 `4740b06`（v0.4.20）→ **APP-133 `b2a4978`（v0.4.21）＝ 本轮交付口径**。

**包内 EXT 与 commit b2a4978 的独立复核**（证据：`results/app/app133_pkg_ext_verify.json`）

| 项 | 值 |
|---|---|
| 核对文件数 | **44**（`ext/bridge/*.py` ＋ `ext/extension/*` ＋ `tools/ext_launcher.py` ＋ manifest） |
| 逐字节一致 | 全部通过（行尾归一化后与 commit blob 相同） |
| `ext/bridge/version.py` | `0.4.21` |
| `ext/extension/manifest.json` version | `0.4.21` |
| manifest `liveDub.release` | `True`（成包脚本故意置 true，APP-129 §2） |
| **反证组** | 故意改坏一个文件 ⇒ 判据报错 ⇒ **True**（判据承重） |

- 🔴 **判据纪律**：`manifest.json` 的 `liveDub.release` 是**白名单例外**（成包脚本故意 `false → true`）⇒ 单独逐字段核对，**只允许这一个字段不同**，其余字段必须与 commit 逐字节一致。

**成包证据**（`results/app/app129_build_v26_evidence.json`）：`ext_commit=b2a4978`、包内污染扫描 **0 项**、EXT 版本一致性 `True`。

- Demucs 模型（`models/bgsep/`，**对源 `shared/bgkeep/htdemucs_core.*` 逐字节一致**）：
  - `models/bgsep/htdemucs_core.xml`：**1341298 B**，sha256 `eb62037b77c34fb8`（源 sha256 `eb62037b77c34fb8`，一致 `True`）
  - `models/bgsep/htdemucs_core.bin`：**106628066 B**，sha256 `62ad36576041af56`（源 sha256 `62ad36576041af56`，一致 `True`）

## §2 离线一致性（APP-129 §3.1 ＋ APP-131 ＋ APP-133）—— **包内 python / 包内 EXT**

| 测试 | 口径 | reviewer 口径 | 结果 |
|---|---|---|---|
| `tests/test_ext0419_bgkeep.py` | **包内 python** ＋ **包内 EXT** | 14/14 | **14/14 PASS**（rc=0） |
| `tests/ext0419_bg_harness.js` | **node v22.22.2** ＋ **包内 `ext/extension/player.js`** | 18/18 | **18/18 PASS**（rc=0） |
| `tests/test_ext0420_clone_gender.py` | **包内 python** ＋ **包内 EXT（b2a4978）** | APP-131 12/12 → **APP-133 16/16** | **16/16 PASS**（rc=0） |

- **16/16 的分母说明**：b2a4978 的测试文件多了「4. split at gender changes」一节（4 条新断言）⇒ 运行时断言 **12 → 16**；源码 `check()` 调用点 12 处（分母取**运行时 PASS+FAIL**，不取调用点数）。
- 🔴 **本轮实测踩到的「判据过期」**：上一轮 runner 的分母还写死 APP-131 的 **12** ⇒ 实测 16/16 PASS 却被判成 FAIL ⇒ **判据过期，不是产品缺陷**（⇒「FAIL 先怀疑判据/环境」又中一例）⇒ 已按 APP-133 改为 16。

## §3 APP-132：机器锁 —— **一次持锁到底** ＋ 丢锁可检测

reviewer APP-132 原文：
> reviewer 的排队脚本（只用 CreateNew 原子创建，绝不抢锁）在 **12:44:18** 成功创建了锁 ⇒ 说明当时锁文件不存在，即你的链在某个时刻删了锁、之后又继续起臂。……请对照 reviewer 桥接日志时间 `shared\bgkeep\gender_ab2\v0420\bridge.log` 判断重叠区间，重叠的臂一并重跑。……要求：整条链（所有臂、默认值检查、抽听样片）**一次持锁到底**，中途不删；锁内容写明起止。结束后再删（只删自己的）。

### §3.1 上一轮（12:33–13:16）的两处真缺陷

| # | 缺陷 | 后果 |
|---|---|---|
| ① | `_app116_build_v25.acquire_lock()` 用 `os.replace(tmp, LOCK)` 写锁 ⇒ **不是原子创建** | reviewer 的 CreateNew 在 12:44:18 成功 ⇒ 我方**实际没在持锁** |
| ② | 看门狗只在「锁是我的或锁没了」时才写回 ⇒ **一旦别人抢走就彻底放弃** | 锁被抢后链**继续跑但不再持锁** ⇒ 计时作废且**无人知晓** |

### §3.2 修法（`results/app/_app132_lock.py`）

- **原子创建**：`os.open(LOCK, O_CREAT|O_EXCL|O_WRONLY)` ⇒ 只有真正空闲才拿得到⇒ **绝不与别人的 CreateNew 竞争**；
- **看门狗每 10 s 复核**：锁**不再是我的**（被抢 / 被删）⇒ **立刻记一条事件**⇒ 整链计时据此作废；
- **锁内容写明起止**：`module pid <start> <end> note`；
- **只删自己的锁**（释放前再核一次 pid）。

**自测（`results/app/app132_lock_events.jsonl` 可查）**：竞争者用 CreateNew ⇒ **BLOCKED**（拿不到）；外部删锁 ⇒ **12 s 内**记 `lock_lost` ⇒ `lk.lost=True` ⇒ 判据**承重**。

### §3.3 reviewer 桥接日志的重叠区间核对（reviewer 要求的）

| reviewer 臂 | 桥接日志 | 起止 |
|---|---|---|
| v0.4.20 | `shared/bgkeep/gender_ab2/v0420/bridge.log` | **13:28:21 → 13:37:03** |
| v0.4.21 | `shared/bgkeep/gender_ab2/v0421/bridge.log` | **13:37:09 → 13:45:36** |

⇒ 与我方上一轮的三臂（**12:33:38–12:44:56 / 12:44:56–12:56:14 / 12:56:14–13:07:39**）**时间上不重叠**；但 reviewer **明确要求重跑**（锁被抢过 ⇒ 计时不可信）⇒ 本轮**全部重跑**。

### §3.4 本轮持锁证据

| 项 | 值 |
|---|---|
| 锁内容 | `app bgkeep v2.6 chain (APP-132 一次持锁到底)` |
| 持锁起 | **2026-11-24 17:45:04** |
| 持锁止 | **2026-11-24 18:25:10** |
| **中途丢锁** | **False**（`lock_lost` 事件 **0** 条） |
| 三臂后复核持锁 | [True, True, True] |
| 默认值检查后复核 | True |
| 抽听样片后复核 | True |

- 事件日志：`results/app/app132_lock_events.jsonl`（**每条都可审计**）。

## §4 10 分钟固定片段整链（APP-129 §3.2 ＋ APP-131 clone 臂 ＋ APP-133 clone 计数）

（证据：`results/app/app133_chain_v26_evidence.json` ＋ `shared/bgkeep/e2e_v26_r2/*/`）

| 指标 | bgkeep **关** | bgkeep **开** | bgkeep 开 ＋ **voice=clone** |
|---|---|---|---|
| 跑到的媒体时长 s | 600.0 | 600.0 | 600.0 |
| **dubs（配音条数）** | 95 | 90 | 114 |
| **丢句**（须 0） | 0 | 0 | 0 |
| 语速 max | 1.7 | 1.7 | 1.7 |
| dub_late max | 115.42 | 139.22 | 182.62 |
| dub_late p90 | 105.56 | 122.58 | 161.25 |
| dub_late n_late | 90 | 87 | 110 |
| **bg_blocks** | 0 | 600 | 600 |
| **bg_late_blocks** | 0 | 0 | 0 |
| **fallback_to_orig_s** | 600.0 | 0.0 | 0.0 |
| **synth_rtf** | 1.0511 | 1.1081 | 1.1273 |
| 积压峰值（max_lag_sec） | 123.4921 | 143.774 | 200.5375 |
| 收尾积压（lag_curve end_sec） | 0.0 | 0.0 | 0.0 |
| 分离设备 | None | GPU.0 | GPU.0 |
| 桥接峰值工作集 MB | 9468.8 | 11470.2 | 11894.5 |

- **桥接进程峰值内存开关差值**（reviewer 实测约 +1.9 GB，作对照）：bgkeep_off 9468.8 MB、bgkeep_on 11470.2 MB、bgkeep_clone 11894.5 MB。
- **设备口径**：ASR(R2T2 INT8)@GPU.0 ／ MT(Hy-MT2 INT8)@GPU.0 ／ TTS(Qwen3-TTS)@NPU；分离 `EXT_BG_DEVICE` 未设 ⇒ **EXT 默认 GPU.0**（reviewer §1 定的默认值）。

### §4.1 APP-133 要的**克隆计数**（clone 臂）

| 字段 | 值 |
|---|---|
| `stats_full.clone_reasons` | `{"self_ref_unvoiced": 2, "self_ref": 1, "guard_no_emb": 2, "timeout": 6, "label": 61, "provisional": 159, "tts_nearest_voice": 1, "guard_keep": 66, "fallback": 2, "tts_nearest": 1, "guard_short": 45, "gender_keep": 2}` |
| `stats_full.spk_reason_hist` | `{"none": 3, "label": 156}` |
| `stats_full.n_gender_splits` | 4 |
| `stats_full.tts_nearest_voice` | null |
| `stats_full.gender_switch` | null |
| `stats_full.gender_selfref` | null |

- `clone_reasons` 的**逐项计数**（APP-133 要的 `stats_full.clone_reasons`）：

| 原因 | 次数 |
|---|---|
| `provisional` | 159 |
| `guard_keep` | 66 |
| `label` | 61 |
| `guard_short` | 45 |
| `timeout` | 6 |
| `self_ref_unvoiced` | 2 |
| `guard_no_emb` | 2 |
| `fallback` | 2 |
| `gender_keep` | 2 |
| `self_ref` | 1 |
| `tts_nearest_voice` | 1 |
| `tts_nearest` | 1 |

- 🔴 **`tts_nearest_voice` / `gender_switch` / `gender_selfref` 在 `stats_full` 顶层是 `null`** ⇒ 它们的计数在 `clone_reasons` **里面**（如 `tts_nearest_voice` = 1）⇒ 如实按实际位置报，**不谎称在顶层**。

## §5 默认值检查（§3.3）＋ 不可用降级（§3.4）＋ 抽听样片（§3.5）

### §5.1 默认值检查（§3.3）

| 场景 | 期望 | 实测 | popup 显示 | 结果 |
|---|---|---|---|---|
| fresh_install | True | True | `正常（GPU.0）` | ✅ |
| upgrade_from_v0418 | True | True | `正常（GPU.0）` | ✅ |
| manual_off_restart | False | False | `已关闭（原声压低）` | ✅ |
| manual_on_restart | True | True | `正常（GPU.0）` | ✅ |

- 🔴 **口径如实说明**：本机**无可控的 Chrome 自动化环境** ⇒ 本检查是在 node 里**执行包内 `ext/extension/popup.js` 的真实表达式**（覆盖「存储初态 ⇒ 默认值/文案」这一层）；**浏览器端 UI 交互本身由 reviewer 复核**。
- popup.js sha256 `a764af38655a1f8a`（32511 B）。

### §5.2 不可用降级（§3.4）

| 项 | 值 |
|---|---|
| 场景 | `degradation_models_bgsep_missing` |
| 改名（模型目录 → 不存在） | `True` |
| 桥接就绪 | `True`（20.0 s） |
| `hello_ack.bg.state` | `unavailable` |
| `hello_ack.bg.reason` | `背景分离模型缺失（models/bgsep/htdemucs_core.xml）` |
| 恢复（改回原名） | `True` |

### §5.3 抽听样片（§3.5）—— **≤1 MB 的 OGG**

| 样片 | player_mix B | OGG | ≤1 MB | codec | 解码帧数 |
|---|---|---|---|---|---|
| `s2` | 5902744 | `app129_listen_s2.ogg` | ✅ | `libopus` | 1538 |
| `cs2` | 14128180 | `app129_listen_cs2.ogg` | ✅ | `libopus` | 3680 |
| `tuffy` | 8666848 | `app129_listen_tuffy.ogg` | ✅ | `libopus` | 2258 |

- 🔴 **本轮实测修的真缺陷**：包内 python 的 **PyAV 19.0.1** 上 `add_stream("vorbis", …)` **直接抛** `ExperimentalError(…, 'avcodec_open2("vorbis", {})')` ⇒ 上一轮**四个样片的 OGG 一个都没生成**（`ogg_ok=false`）⇒ 一条附件都发不出去。
- 修法：**按优先级逐个真开一次**（`vorbis` → `libopus` → `opus`）⇒ 第一个「能开 ＋ 产出文件 ＋ **能被回读解码**」的胜出（**成功判据不能只看没抛异常**）⇒ 实际 codec 与字节数**写进证据**。
- 本机 `av.codecs_available` 里**列得出** `vorbis`/`speex`，但**真开必抛** ⇒ **「列表里有」≠「能开」** ⇒ 不能用编码器列表当判据。

## §6 签 ACCEPTED（v2.6）

| 项 | 值 |
|---|---|
| 版本 | `2.6` |
| 模块数 | 33 |
| EXT | `0.4.21`（commit `None`） |
| 模型清单条目 | 2 |

## §7 纪律

- 🟢 **未通知用户**（reviewer APP-129 §4 明文「不要通知用户」）；🟢 **未连 B 机**；🟢 **未调 MiniMax**；🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）；
- 🟢 **未打包 zip**（用户级纪律「不通知 ⇒ 不打包」；APP-129 §3.6 说「按惯例出包」，但**完整版 v2.x 历来无 zip**（只有 MiniMVP 线打 zip）⇒ 本轮**只出目录 ＋ 签 ACCEPTED**）；
- 🟢 **未覆盖/未删除任何旧版本目录与 zip**（v2.5 及更早原封不动）；
- 🔴 **计时类结论的前提**：本轮**一次持锁到底**（`lock_lost` 事件 **0** 条）⇒ 计时有效；但 reviewer 的 **v0.4.21 对比臂**（端口 8785/8786）若与本轮重叠仍需 reviewer 自行核对。

### §7.1 STATUS 邮件（T-MAIL-003 必须发）

| # | 主题 | 正文 | 附件 | message_id |
|---|---|---|---|---|
| ① | `[C4][A][STATUS][APP] APP-133 v2.6 交付 —— EXT 升到 v0.4.21(b2a4978)；…` | **4 769 B** | 0 | `msg_IUZ_i57L-QSU-4X21TzQc1A1xybSAzOWCrCQhGemKQzpUA` |
| ② | `[C4][A][STATUS][APP] APP-133 v2.6 整链三臂数字 ＋ 抽听样片 OGG 附件…` | **3 999 B** | **3**（s2 / cs2 / tuffy 的 OGG） | `msg_cG7Lu6ZZSV85Tiz4Z4OdnCjoasES2jOXtt5qc8t8VswKXw` |

- 两封正文均**远低于** §224 的 11 KB 截断线（4.8 KB / 4.0 KB）⇒ 已发箱**逐行回读**核对首/中/尾三处地标**全部命中 ⇒ 未截断**；附件 **3 个 OGG**（328 411 / 852 817 / 580 867 B，均 ≤1 MB，**sha1 由发送脚本从磁盘现算** ⇒ 无人工转写）。
- 🔴 **如实登记 1 处发信事故**：第一版「整链数字」邮件（`msg_lkjLer4m2Jv4oy6_e8mnFBUVMN2Mczq-Oar0ID1JCFFajA`）的**积压峰值一行打印成「（未取到）」** ⇒ 根因＝邮件生成器取的字段名 `peak_lag_sec` 与 `margin.json` 里实际的 `max_lag_sec` 不一致（**与 §4 表格同源**，在同一轮被发现）⇒ **已改正并重发**（上表②＝重发后的那封）；「交付」那封（①）**不含该行** ⇒ 无需重发。
