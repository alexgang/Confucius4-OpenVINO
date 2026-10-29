## §92 🔴🔴 **APP-034/035/036/037/038 五条新纠偏全部执行完毕 ⇒ 遥测口径 4 处已改（APP-036 C1–C4）＋ 句首标点已规范化（APP-037 C）＋ APP-036 D 已给出离线模拟数字 ＋ APP-035「FTP 已关闭」口径已纠正**（2026-10-29 12:58）｜**本条已完成**｜**本条需等 reviewer 复核**

### §92.0 本轮巡检

- `status/app/CORRECTIONS_APP.md` 全文扫描 ⇒ 共 **38 条**（`APP-001` ~ `APP-038`）；
- 开工时 `STATUS_APP.md` 头部 `last_ack: APP-033` ⇒ **新条目 = APP-034 ~ APP-038 共 5 条**；
- 该文件**只读、零改动**：指纹 **100 067 B / mtime 2026-10-29 11:00:14 / SHA256 `838b317124458a2baecb7de53afea827…`**（本轮全程未改、未暂存、未提交）。

### §92.1 APP-035 [BLOCKING] —— FTP 已由用户永久关闭 ⇒ **口径纠正，不重发**

reviewer 裁定（不是待定项）：用户 2026-10-25 已决定**关闭 FTP**（当时 FTP 暴露了整个用户目录）⇒
**不得**运行 `publish_ftp.py`、**不得**启动 ftp_share / 任何 FTP/HTTP 文件服务、**不得**为分发新开共享。

**本轮实测（PowerShell，只读）**：

| 项 | 实测结果 |
|---|---|
| FTP/HTTP/python 进程 | **无**（`Get-Process` / `Get-CimInstance Win32_Process` 过滤 `ftp|http|pyftpd|python` ⇒ 空） |
| 监听端口 21 / 2121 / 8080 / 80 / 8000 | **无**（`Get-NetTCPConnection -State Listen` ⇒ 空） |
| `FTP_Share/` 内容 | **仅 `Confucius4_LiveCaption_v1.4.zip`（11 216 051 100 B / 2026-10-25 07:47:29）+ `Confucius4_LiveCaption_v1.5.zip`（11 216 287 107 B / 2026-10-27 10:34:05）** ⇒ **v1.4 / v1.5 旧副本不删不动**（删不删由用户决定） |
| `publish_ftp.py` | 仓库内存在（`C:\Users\Trekker-PTL\confucius4-openvino\publish_ftp.py` / 8 828 B / 2026-10-25 20:59:20）⇒ **本轮未运行**（另有多份历史副本在 `git_app_push` / `git_rewrite*` / `git_verify_*` 下，均未运行） |

**⇒ 撤回 §90.6 / §91.8 的旧口径**：原写「v1.6 未发布到 FTP ⇒ 客户从 FTP 拿到的仍是旧的 ⇒ **是否重发待 reviewer 裁定**」
—— 该表述**作废**。FTP 已不是分发渠道 ⇒ 改为「**FTP 已关闭（用户 10-25 决定），不适用**」。
**分发方式**（reviewer 第 3 条）：v1.6 zip 留在目标机原位，写明绝对路径 + 字节数 + SHA256，**由 reviewer 用 SSH/SFTP 拉取**；
如需其他渠道由用户另行指定 ⇒ **App 不自行选渠道**。

### §92.2 APP-036 C1 —— worker 侧排队口径（旧的 `t_submit` 恒为 0 是假的）

reviewer 原话：「`t_submit` 是在 `_synth_babelvox` 开头取的 ⇒ `t_dequeue==t_submit`、`queue_lag_s` 恒为 0；
⇒ soak 报告的 `seg_queue_p50=0.0`、id≥4 的『排队 0.000 s』**都是假的**，worker 里实际排队 7–55 s。」

**改法**（`live_caption/tts_worker.py`）：

- 主循环 `for _raw in _stdin:` 顶部记 **`t_recv`**（读到 stdin 命令的时刻）；
- 入队处记 **`t_enqueue`**（放进合成 FIFO 的时刻）；
- 队列元组扩成 6 元组 `(jid, text, spk, spk_conf, lang, t_recv)`，合成线程解包**向后兼容**
  （`t_recv = item[5] if len(item) > 5 else None`）；
- jsonl 新增 4 个字段：`t_recv` / `t_enqueue` / `worker_fifo_wait_s`（= `t_enqueue − t_recv`）/
  **`worker_fifo_wait_total_s`**（= `t_dequeue − t_recv`，**这才是真排队**）；
- 新增常量 `_APP036_JSONL_KEYS`，`_record_jsonl()` 逐句落盘。

**实测**（`app134` C1 组，system 3.12 / numpy 2.5.4，零推理）：手工模拟「读到命令 → 等 1.2 s → 入队 → 再等 0.3 s → 出队」：

- `worker_fifo_wait_s` = **1.2002**（期望 ≈1.2）✔
- `worker_fifo_wait_total_s` = **1.5008**（期望 ≈1.5）✔
- **对照**：老口径 `t_submit − t_dequeue` = **0.0708 s**（≈0）⇒ 证明「老口径量不到排队」确实成立 ✔

### §92.3 APP-036 C2 —— 积压曲线（老实现只有 1 行，不是曲线）

**改法**（`live_caption/tts_service.py` + `live_caption/live_caption_app.py`）：

- service 内部起**采样线程**（`start_curve_sampler`，默认 **1.5 s**）⇒ **与 CLI 日志 grep 完全解耦**
  ⇒ **播放模式 / 落盘模式都有曲线**（reviewer 明文「在落盘模式下也要采」）；
- 采样点含 `t_s / backlog_s / lag_s / ring_s / synth_s / queued_s / n_played / n_dropped / n_empty / n_submitted`；
- `write_curve_csv(path)` 落 csv（**1 s 粒度**，reviewer 可按 `source_t` 对齐）；
- CLI 收尾写 `<tts_out>.backlog_curve.csv`（或 `tts_backlog_curve.csv`）并打印采样点数。

**实测**（`app134` C2 组，`out_wav` 非空 ⇒ 落盘模式）：采样点 **162**（老实现 1 行）✔；
csv **163 行**（表头 + 162 点）✔；表头含 `backlog_s/lag_s/ring_s/synth_s/queued_s` ✔；`t_s` 非递减 ✔。
⚠️ **采样间隔被产品代码钳到 0.2 s 下限**（`max(0.2, interval_s)`）⇒ 凑够 100 点需 ≥20 s ⇒ 本轮该组**持锁跑了 21 s**。

### §92.4 APP-036 C3 —— `end_lag_s` 的真实定义

reviewer 原话：「`end_lag_s=0.0` 是 drain 之后取的值，**没有意义**。
新增 `end_lag_s = 最后一句播完（或写完）的时刻 − 源音频结束时刻`，播放模式和落盘模式各自给出。」

**改法**：

- `TTSService.set_source_end(t)`（主进程时钟打点）＋ `_recompute_end_lag()`；
- `played` 分支 ⇒ 记 `_last_out_t`；`written` 分支且 `out_wav` 时 ⇒ 同样记（落盘模式没有 `played`）；
- `Session._loop` 的 `finally` ⇒ `self.source_end_t = time.perf_counter()`；
- CLI 收尾 ⇒ `tts.set_source_end(getattr(s, 'source_end_t', None))`；GUI 退出路径同样打点；
- 🔴 **跨进程时钟不可相减** ⇒ **worker 侧不做任何 `end_lag_s` 减法**（worker 的 `perf_counter()` 基准与主进程不同）。

**实测**（`app134` C3 组）：

| 判据 | 实测 |
|---|---|
| 未打点时 `end_lag_s` | **None**（老口径是 `0.0` ⇒ 没意义）✔ |
| 源结束先、播完后 | **+0.05 s**（>0）✔ |
| **源结束晚于播完** | **−1.0 s**（<0）⇒ 证明是**相减**不是取绝对值 ✔ |
| worker 源码含 `end_lag_s` 减法 | **False** ✔ |
| `played` 后 `end_lag_s` 有值 | ✔ |

### §92.5 APP-036 C4 —— `close()` 作废计数 ＋ close 后最终统计 ＋ drain 超时

reviewer 原话：「CLI 收尾的统计行在 `close()` **之前**打印 ⇒ §82 那次『丢弃 0』**实际作废 51 句**。
改成 close() 之后再打印一次最终统计，或者把 drain 超时设为 `max(120, 1.5×当前积压)`，并在报告里列出 `n_discard_on_close`。」

**改法**：

- `TTSService` 新增 `n_discard_on_close`（**close 主动作废的句子，单独计数**，不混 `n_dropped`）
  ⇒ `close()` 里 `n_dropped += len(orphan)` **且** `n_discard_on_close += len(orphan)`；
- `stats()` 新增 `end_lag_s` / `n_discard_on_close` / `n_empty`；
- CLI：drain 超时改 `max(120.0, 1.5 × 当前积压)`；`close()` **之后**再打印一次
  **「[TTS] 最终统计（close 后）」**（含提交/播完/丢弃/关闭作废/空句/失败/结尾滞后/积压最大）；
- 🔴 APP-037 C 引入 `n_empty` ⇒ 账本不变式扩成**三段式**：
  **`n_played + n_dropped + n_empty == n_submitted`**。

**实测**（`app134` C4 组）：3 句在途 ⇒ `close()` 后 `n_discard_on_close = 3`、`n_dropped = 3`、
不变式 `0 + 3 + 0 == 3` 成立 ✔；`stats()` 含 3 个新字段 ✔；
源码层：**「最终统计（close 后）」位置 172 848 > `tts.close()` 位置 119 568** ✔；
drain 超时含 `max(120.0, 1.5 * _bl)` ✔。

### §92.6 APP-037 C —— 句首标点统一规范化（reviewer 裁定）

reviewer 原话：「在 **tts_worker 合成前统一规范化**：去掉句首的标点和空白（全角/半角），
去掉后为空就**不合成**，记 `end_reason=empty`，**不计丢句**。三道失控守卫保持不变。
加单测：句首"，"、"、"、"。"、"…"和纯标点各 1 条。」

**改法**（`live_caption/tts_worker.py` + `live_caption/tts_service.py`）：

- 新增 `_LEAD_PUNCT_CHARS`（全角 + 半角）与 `_strip_lead_punct(text)`
  ⇒ 返回 `(处理后文本, 被剥标点)`；**只剥句首**（不改句中、不改句尾）
  ⇒ **不误伤**数字/字母/汉字（`2026年の売上` 原样保留）；
- `synth()` 里剥完若为空 ⇒ **独立早退路径**：
  `end_reason='empty'` ＋ 写 jsonl（`n_samples=0 / n_parts=0 / peak=0 / rms=0`）
  ＋ 发**专用事件 `kind='empty'`** ⇒ **既不发 `played`（会误记已播）也不发句子级 `error`（会误记丢句）**；
  ⚠️ **三道失控守卫（cap / runaway / 看门狗）代码路径未被触碰**；
- `TTSService._handle_event` 新增 `elif kind == 'empty':` ⇒ `n_empty += 1`（**不计 `n_dropped`**）
  ＋ 从 `pending` 摘除（否则 `drain()` 必超时）＋ 从 `_inflight` 摘除。

**单测**（`results/app/app133_app037c_lead_punct.py`，system 3.12 / numpy 2.5.4，**零推理 / 零 GPU / 零 NPU / 零声卡**）：

| 组 | 内容 | 结果 |
|---|---|---|
| **A** | 16 个 `_strip_lead_punct` 用例（含 reviewer 点名的「，」「、」「。」「…」各 1 条 ＋ **纯标点** 1 条 ＋ 半角 ＋ 空白 ＋ 不误伤数字/字母/句中/句尾标点）＋ 10 个剥离集合成员检查 | **26 PASS / 0 FAIL** |
| **B** | worker 空句早退路径（不发 `played` / 不发句子级 `error` / 发 `kind='empty'` / `end_reason='empty'` / jsonl 字段） | **11 PASS / 0 FAIL** |
| **C** | service `empty` 事件处理（`n_empty += 1` / **不计丢句** / 摘 `pending` / 摘 `_inflight` / 三段式不变式 ＋ **对照组**：普通句子级 error 仍计丢句） | **6 PASS / 0 FAIL** |
| **D** | 正常句语义零影响 | **4 PASS / 0 FAIL** |
| **X（反证）** | ① 剥标点逻辑失效 ⇒ A 组必 FAIL；② 空句改发 `played` ⇒ B 组必 FAIL；③ 空句改计丢句 ⇒ C 组必 FAIL | **3 PASS / 0 FAIL**（注入后对应判据**确实 FAIL** ⇒ 判据不恒真） |

**合计 50 PASS / 0 FAIL**（仓库版）；**客户包内那份代码重跑同样 50 PASS / 0 FAIL**。

### §92.7 APP-036 D —— 离线模拟播放速度对滞后曲线的影响（**只给数字，不改产品**）

reviewer D 明文：「可以先做的零风险准备：用现有 soak 的 jsonl **离线模拟**『播放 1.1×/1.2×/1.3× 时的滞后曲线』，
**只给数字，不改产品**。」

**本轮严格照办**：只读 `C:\Users\Trekker-PTL\app028_soak\app028_soak.wav.tts.jsonl`（76 句），
**零推理 / 零 GPU / 零 NPU**，**不设阈值、不改播放速度、不改 MT、不恢复任何丢句做法**。

**模型**（写清楚供复核）：内容轴 = `t_submit` 线性重映射到 `[0, 300 s]`（reviewer 的原声口径）；
产出时刻 = 内容时刻 + 合成耗时；`lag(t) = 已产出音频 − 已播音频`（= APP-028 的 `lag_s` 口径）；
播放速率 = `v`，**受「已产出」限制** ⇒ 欠载会停顿。

**关键数字**：

- 中文音频总时长 **338.8 s** vs 原声 **300 s** ⇒ **R = 1.1293（中文比原声长 12.9%）**；
- 合成侧产出速率 **1.0200 音频秒/墙钟秒** ⇒ **播放速度需 > 1.0200 才能收敛**；
- 🔴 **交叉校验**：reviewer 的速率模型 `lag(t) ≈ (R − v)·t` ⇒ `v=1.0` 时 `lag(300s) ≈ 38.8 s`
  （reviewer 原文「5 分钟下来至少 35–40 s」）⇒ **与本脚本逐句模型算出的 38.98 s 差 0.18 s ⇒ 同量级 ✓**。

| 播放速度 | lag@60s | lag@120s | lag@180s | lag@240s | **lag@300s** | max_lag_s | 欠载步数 |
|---|---|---|---|---|---|---|---|
| **1.0×** | 7.9 | 9.1 | 13.0 | 18.1 | **38.98** | 40.48 | 12 |
| **1.1×** | 6.5 | 3.9 | 3.8 | 6.2 | **22.84** | 24.49 | 43 |
| **1.2×** | 6.0 | 2.6 | 3.2 | 5.8 | **18.24** | 20.04 | 88 |
| **1.3×** | 5.6 | 2.0 | 2.6 | 5.7 | **13.64** | 15.59 | 124 |

（单位：秒。曲线 csv：`results/app/app135_app036d_lag_curves.csv`，4 条速度曲线叠在一起，采样步长 0.5 s。）

⚠️ **这张表只是数字**，**不含任何策略建议** —— 追赶策略（何时提速、提到几倍、TTS 语速、MT 简洁模式）
**等用户决定**，reviewer 已上报；本轮**未改任何产品行为**、**未恢复任何丢句/跳句做法**。

### §92.8 APP-034 / APP-038 —— FYI 两条的核查结论

**APP-034（用户决定方案 A：TTS 不等 spk）**：

- `TTSService.spk_update(jid, spk, spk_conf)` ⇒ 只 `{'cmd':'spk_update', ...}` **下发命令**，**不改任何合成行为**；
- `tts_worker.py` 的 `elif cmd == 'spk_update':` ⇒ **只 `log()` 一行**，不碰 `_synth_q`、不碰音色条件；
- `submit()` **不因 spk 阻塞**（`spk`/`spk_conf` 仅在有值时随命令附带）；
- `live_caption_app.py` / `offline_reader.py` ⇒ **App 侧根本没有调用 `spk_update`**（全仓仅 1 处注释提及）；
- ⇒ **结论：App 侧没有让 TTS 队列等 spk** ✔（符合 reviewer「只作通知，不新增要求」）。

**APP-038（NPU 驱动升级到 32.0.201.14005）**：

- reviewer 明文「**不需要专门去测**」；
- 本轮**未跑 NPU 推理**（守纪律）⇒ **未观测到编译缓存失效/数值异常/变慢**；
- 📌 **风险记录**：App 下次用 NPU 跑 TTS 时，**编译缓存可能失效、冷启动会变长**（属正常现象）；
  若出现 NPU 编译失败 / 数值异常 / 明显变慢，在 STATUS 记下来由主会话决定是否回退驱动
  （旧驱动 `32.0.100.4778` ⇒ 新 `32.0.201.14005`）。

### §92.9 本轮验收汇总（**代码侧**已过，**实测**未做）

| 脚本 | 内容 | 仓库版 | 客户包内那份 |
|---|---|---|---|
| `app133_app037c_lead_punct.py` | APP-037 C 单测 + 3 条反证 | **50 PASS / 0 FAIL** | **50 PASS / 0 FAIL** |
| `app134_app036c_telemetry.py` | APP-036 C1–C4 + 4 条反证 | **50 PASS / 0 FAIL** | **50 PASS / 0 FAIL** |
| `app135_app036d_speed_simulation.py` | APP-036 D 离线模拟 | 出数字 + csv | 不适用（只读 soak jsonl） |

**证据文件**（全部已落盘）：

| 文件 | 字节 | mtime | SHA256（前 32） |
|---|---|---|---|
| `results/app/app133_app037c_lead_punct.py` | 17 534 | 2026-10-29 12:50:40 | `535df61fe843ebe03034f4492b05461c` |
| `results/app/app133_app037c_lead_punct_evidence.json` | 8 644 | 2026-10-29 12:50:43 | `45214e201e1b99da5ece81ab96600ca4` |
| `results/app/app133_app037c_lead_punct_pkg_evidence.json` | 8 640 | 2026-10-29 12:58:13 | `c3f09db726a1c995d12c4dc257508962` |
| `results/app/app134_app036c_telemetry.py` | 26 357 | 2026-10-29 12:52:22 | `522fd3b93c989915ec76144e0df92080` |
| `results/app/app134_app036c_telemetry_evidence.json` | 9 849 | 2026-10-29 12:53:50 | `b9844bba07324b7f13064a366b91d90b` |
| `results/app/app134_app036c_telemetry_pkg_evidence.json` | 9 846 | 2026-10-29 12:58:40 | `7edd54dd57bc86ffde6e39cbe8cc16c3` |
| `results/app/app135_app036d_speed_simulation.py` | 9 345 | 2026-10-29 12:56:35 | `3ad42364dc56907c13de5656446d9ed2` |
| `results/app/app135_app036d_speed_simulation_evidence.json` | 2 022 | 2026-10-29 12:56:39 | `109d26c136391d847f345c82fe565f99` |
| `results/app/app135_app036d_lag_curves.csv` | 22 509 | 2026-10-29 12:56:39 | `b49e34eefd69e6a6fb72134ed45bb548` |
| `live_caption/sync_c155_to_pkg.py` | 11 272 | 2026-10-29 12:57:51 | `c3899f011e6dc5abb2fc39a155323137` |

### §92.10 客户包 v1.6 定点同步（**已完成**）

`live_caption/sync_c155_to_pkg.py`（**定点替换范式**：基线 = `HEAD`（`6ff8bf6`）→ `difflib` 派生变更块
⇒ **不手抄任何代码**；包内**唯一命中**断言；幂等；**包外备份**；归一化换行后**逐字一致**才写盘）：

| 文件 | 变更块 | 同步前字节 / SHA256（前 16） | 同步后字节 / SHA256（前 16） | 状态 |
|---|---|---|---|---|
| `app/tts_worker.py` | **14** | 177 319 / `71e8fcc861d2ee29` | 188 451 / `90835802f79a47e1` | SYNCED |
| `app/tts_service.py` | **11** | 104 066 / `b4800b5042c1207f` | 115 173 / `ec2ef04a5c6f9276` | SYNCED |
| `app/live_caption_app.py` | **7** | 243 363 / `7c062bb013c54575` | 248 484 / `5aa3269aa9b0b740` | SYNCED |

- 包外备份：`C:\Users\Trekker-PTL\pkg_backup_app_c155\`（`*.bak_20261029_125756`）
  ⇒ 🔴 **在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- **幂等复跑**：`--check` ⇒ **3/3 ALREADY** ✔；
- **仓库 ⇄ 包目录 逐字复核**（归一化 LF 后 SHA256）：**3/3 MATCH**
  （`tts_worker.py` `90835802f79a47e1` / `tts_service.py` `ec2ef04a5c6f9276` /
  `live_caption_app.py` `5aa3269aa9b0b740`）
  ⚠️ `live_caption_app.py` 字节数差 4 711 B ＝ **CRLF↔LF 行尾差异** ⇒ 归一化后逐字一致（**不是**内容差异）。

### §92.11 🔴 本轮「半交付」自检（开工第一件事）⇒ 抓出并修掉两个真实缺陷

按「开工先查上一轮是不是半交付」纪律，本轮开工时发现**孤儿锁**残留：

- `C:\Users\Trekker-PTL\shared\MACHINE_LOCK` 内容 = `EXT-throughput-all 38028 2026-10-29 12:14:12`
  （**别的模块**的测速作业，mtime 12:14:12）；
- ⚠️ **`Get-Process` / `Get-CimInstance` 都说不存在 PID 38028**，但**不能据此回收**
  ⇒ 按纪律用 ctypes 判定。

**🔴🔴 抓出的真实缺陷①：`ctypes.get_last_error()` 的口径陷阱**

- 我第一个探针用 `ctypes.windll.kernel32` + `ctypes.get_last_error()` ⇒ 读到 **陈旧的 0** ⇒ 误判「存活」；
- 改用 `ctypes.WinDLL('kernel32', use_last_error=True)` ⇒ `OpenProcess` 失败、`err = 87`
  （`ERROR_INVALID_PARAMETER`）⇒ **该 PID 确定不存在**；
- ⇒ **根因**：`ctypes.windll.kernel32`（**不带** `use_last_error`）**不会**把 Win32 的 last-error
  同步进 ctypes 的线程局部槽 ⇒ `get_last_error()` 读到的是**上一次别的调用留下的值**；
- ⇒ ✅ **产品代码 `machine_lock_app._pid_alive` 是对的**（它直接调 Win32 的 `GetLastError()`）
  ⇒ `lock_state()` 返回 **`stale_pid`** 与修正后的探针**一致**；
- 📌 **已把这条写进本轮探针脚本的注释**，避免下次再踩。

**三路一致判据（全部满足才回收）**：

| 判据 | 实测 |
|---|---|
| ① ctypes `OpenProcess` ⇒ `err == 87` | **err = 87** ✔（PID 确定不存在） |
| ② `machine_lock_app.lock_state()` ⇒ `stale_pid` | **stale_pid** ✔ |
| ③ 进程表无该 PID / 无 python 进程 | `EnumProcesses`（1 236 个 PID）**不含 38028**；无 python 进程 ✔ |

⇒ 三路一致 ⇒ **回收孤儿锁** ✔（删的是**已死** PID 的锁，未碰任何活锁）。
⚠️ **回收前再次复核**（`Get-Process` 与 ctypes 结论矛盾时**必须**查清根因，不能凭单一路径下结论）。

**🔴 抓出的真实缺陷②（本轮验收脚本自身）：`release()` 漏传 payload ⇒ 锁删不掉**

- `machine_lock_app.acquire()` 返回的是 **(ok, payload)**，
  而 `release(payload)` **必须**带 payload（只删「内容与自己那份完全一致」的文件）
  ⇒ 第一次运行器漏传 payload ⇒ **锁没删掉 ⇒ 残留成孤儿锁**；
- ⇒ 第二次用 ctypes 确认 PID 39072 已死（`err = 87`）后回收，并**修好运行器**（补上 payload）
  ⇒ 复跑后 `release` 打印「**[lock] 已释放**」✔。

### §92.12 本轮未做 / 仍等 reviewer（**不写「已交付」**）

- ⛔ **APP-036 的真实验收未做**：reviewer 验收要求「用 SPE 前 5 分钟 **NPU 默认配置**、**播放模式**
  重跑一次 ⇒ 报告给出滞后曲线（≥100 采样点）、worker_fifo_wait P50/P95/max、`end_lag_s`、
  `n_discard_on_close=0`，以及 B 段『中文时长/原声时长』比值」
  ⇒ 本轮**只做了口径修正 + 零推理验收** ⇒ **真机 5 分钟 NPU 播放模式重跑未做**
  （须持锁 ＋ 不在 CPU 上跑推理）⇒ **待 reviewer 复核**；
- ⛔ **APP-037 B1/B2/B3 未做**：「lang 显式下传」的流水线级证据（CLI `--translate ja` 76± 句
  逐句 `lang=ja` / `lang_src=explicit`）、NPU 组用修好语料重跑、日文 GUI 5 分钟
  ⇒ 本轮**未跑**（须持锁）⇒ **待 reviewer 复核**；
- ⛔ **追赶策略未做**（APP-036 D 明文等用户决定）⇒ 本轮**只给数字**；
- ⛔ **客户包 v1.6 zip 未重打** ⇒ 本轮改动**只进了包目录**，**zip 里仍是旧代码**
  ⇒ 按 §66 口径**不写「已交付」**（须持锁重打 ＋ 三方只读复核）；
- ⛔ **未跑 `verify_pkg_zip.py`、未跑 `publish_ftp.py`、未开 FTP**（APP-035）；
- ⛔ **未修改 `CORRECTIONS_APP.md`**（只读、零改动，指纹见 §92.0）；
- ⛔ **未用 `git add -A`**（逐文件 add，不吞 ASR/MT/TTS 他模块的未提交改动）；
- ⛔ **未调 MiniMax**（质量判定归 reviewer）。
