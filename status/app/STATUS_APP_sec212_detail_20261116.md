> 本节是 **APP-113** 的执行记录。**每个数字都从结果文件里取**；
> 产物附「字节数 ｜ mtime ｜ SHA256」。

### ① 纠偏文件只读复核（开工 vs 收尾）

| 项 | 开工（本轮实测） | 上一会话快照（16:21） |
|---|---|---|
| SHA256 | `3abed2a1f9da336a7515aa01e98cb6f9aa020ab9c6dad0eed29794d686cc29ae` | `3abed2a1f9da336a7515aa01e98cb6f9aa020ab9c6dad0eed29794d686cc29ae` |
| 字节数 | 376710 | 376710 |
| mtime | 2026-11-16 14:52:40 | 2026-11-16 14:52:40 |
| `## APP-xxx` 条数 | 113 | 113 |
| 最大编号 | APP-113 | APP-113 |

⇒ **本轮开工实测与上一会话 16:21 快照逐字一致** ⇒ 纠偏文件**未被任何会话改动**；
　`last_ack` **APP-112 → APP-113**。该文件**只读，本轮未修改**。

### ② §1 TTS 就绪前**排队等待**（方案 B）

**实现**（`live_caption/live_caption_app.py`）：

- 新增 `TtsReadyQueue`（GUI / CLI **共用一份**）：`push()` 入队 → `take_ready()` FIFO 补发 → `enforce_overflow()` 按最旧优先丢弃 → `poll()` 记就绪/清空时刻。
- 提交动作 `self._tts_submit_fn(ev)` / `_cli_make_submit(...)` 在**入队时冻结**参数（目标语言 / 按句音色 / 目标开播墙钟）⇒ 补发与「当场就绪提交」**逐字一致**。
- **队列上限保护**：队首等待超过 **120 s** 仍未就绪 ⇒ 按最旧优先丢弃并计 `n_drop_not_ready_overflow`（GUI 语音区状态条明示）。
- **服务层 `_drop_pending_on_ready`（APP-069④/070② A）未改** ⇒ App 层只在 ready 后 才 `submit()` ⇒ 服务层待发队列恒为空 ⇒ 老路径逐字不变。
- 旧的「未就绪即跳过」路径**已删除**（CLI 侧 `_skip_nr` 计数器一并删除，GUI 侧 `_tts_skip_not_ready` 保留但恒为 0）。

**行为级自测**（`results/app/app586_tts_ready_queue_selftest.json`，**不 import 被测模块**：AST 抽类 + `exec` 真跑）：**PASS**，8 个用例全 PASS，含 **4 个反证组**（阈值放大 / 滞后 50 s / `lag_s=0 但 play_lag_s=48` / 口径正例）。

  - [PASS] 正常等待后补发：一句不丢 + FIFO 顺序不变
  - [PASS] 溢出保护：超过阈值仍未就绪 ⇒ 按最旧优先丢弃 + 计数
  - [PASS] 反证组：阈值放大 ⇒ 溢出丢弃必须 = 0（证明用例 2 不是恒真）
  - [PASS] 反证组：滞后 50 s ⇒ 不得记「积压清空」
  - [PASS] 口径反证：lag_s=0 但 play_lag_s=48 ⇒ 不得记「积压清空」（证明判据用的是 play_lag_s，不是未播音频时长）
  - [PASS] 两道闸反证：play_lag_s=0.1 但**一句都还没播** ⇒ 不得记清空
  - [PASS] 两道闸正例：play_lag_s=0.1 且已播 2 句(=已补发) ⇒ 记「积压清空」
  - [PASS] 口径反证：无 play_lag_s ⇒ **不回落** lag_s ⇒ 不得记「积压清空」

### ③ §2 ASR 与 TTS **并行加载**

**实现**：

- **CLI**：`run_cli()` 在 `make_engine()`（ASR 加载）**之前**用后台线程起 `TTSService` ⇒ `Popen` 立即返回、模型在 **worker 进程内**加载 ⇒ 真并行。
- **GUI**：`App.start()` 在 `self.load_engine()` 之前走**同一入口** `_on_tts_toggled()`（APP-041「同一入口，不要另写一套」）。
- 🔴 **只并行 CUDA 这一路**：TTS 档位是 **GPU.0 / NPU** ⇒ **保持串行**（沿用「auto=False 防 GPU 编译死锁」的历史经验）。
- 🔴 **新增对照开关** `LIVECAP_TTS_PARALLEL=0` ⇒ 强制串行（供本节「并行 vs 串行」的同机同代码 A/B）。

**各组件就绪时刻（相对进程启动，秒）**：

| 臂 | ASR 就绪 | MT 就绪 | **TTS 就绪** | 收尾时进程已运行 | 整轮耗时 |
|---|---|---|---|---|---|
| sp4 中文目标（**并行**） | 4.5 | 10.1 | 37.6 | 608.2 | 613.1 |
| sp4 中文目标（**强制串行**，对照臂） | 5 | 10.3 | 43.6 | 608.2 | 613.1 |
| sp4 英文目标（**并行**） | 4.9 | 10.4 | 37 | 609 | 614.3 |

> 口径：`ASR就绪` = `eng.load_s`；`TTS就绪` = 队列 `ready_at_rel_s`（队列基准 = CLI 进程启动）；**两个数都写在 run log 的 `[APP-113]` 行**。

**并行 vs 串行（同机、同代码、同素材、同一次持锁会话）**：

| 指标 | 并行臂 | 串行臂 | 差 |
|---|---|---|---|
| ASR 就绪 (s) | 4.5 | 5 | -0.5 |
| TTS 就绪 (s) | 37.6 | 43.6 | -6.0 |
| 整轮耗时 (s) | 613.1 | 613.1 | +0.0 |

- 并行臂 CUDA 边车：`[TTS] [TTS] [tts_cuda] 就绪：NVIDIA GeForce RTX 5050 Laptop GPU / torch 2.11.0+cu128 / 加载 28.6s / 预热 2.5s`
- 串行臂 CUDA 边车：`[TTS] [TTS] [tts_cuda] 就绪：NVIDIA GeForce RTX 5050 Laptop GPU / torch 2.11.0+cu128 / 加载 29.3s / 预热 2.6s`

**与 sp3（串行旧包）的对比**（`results/app/app582_specialmvp_sp3_acceptance.v2.json`）：

| 项 | sp3（串行） | sp4（并行） |
|---|---|---|
| worker 模型加载完成 | **87.7 s** | 见上表 |
| CUDA 边车加载 | **78.9 s**（预热 2.7 s） | 见上表 |
| ASR 加载 | **15.8 s** | 见上表 |
| `timing_valid` | 🔴 **false**（窗口内有外部 4.56 GB + 0.59 GB 写入） | 见上表 |

⇒ 🔴 **sp3 基线的计时不可直接引用**（`timing_valid=false`）⇒ 「并行前后」的**干净对照**只能靠本节的同机 A/B 臂。

### ④ §3 非中文目标语速上限 **1.30× → 2.0×**

- `time_stretch.SPEED_MAX` **1.30 → 2.00**（所有目标语言）；`ZH_SPEED_MAX` 仍是 2.00 ⇒ **两种目标的上限现已一致**。
- 🔴 **增益曲线不动**：`LAG_DEADZONE_S=3.0` / `SPEED_PER_LAG_S=0.025` / `LAG_HYSTERESIS_S=2.0` / `MAX_STEP_CHANGE=0.1` 全部照旧。
- `speed_bounds_for_lang()`：中文 (1.10, 2.00)／其他 (1.00, **2.00**)。
- `tts_worker.py` 的两处兜底 (`1.0, 1.30)` → `(1.0, 2.00)`) 同步改。
- 「总倍率上限」：代码里**没有独立的总倍率上限**（只有相邻句 `MAX_STEP_CHANGE=0.1`）⇒ 无需改动；GUI/日志显示的是**当前句倍率**（`cur_speed`），**不含 1.30 字面量**。
- 🔴 **中英下限不同**：中文下限 **1.10**、非中文下限 **1.00**（10-29 口径不变）。

**三种形态默认值**（`results/app/app589_three_forms_defaults.json`）：

| 形态 | ASR | MT | TTS |
|---|---|---|---|
| FULL | GPU.0 | GPU.0 | GPU.0 |
| MINIMVP | GPU.0 | GPU.0 | NPU |
| SPECIALMVP | GPU.0 | NPU | CUDA |

⇒ 🔴 **MiniMVP（rc11）的 TTS = NPU ⇒ 走不到 CUDA 并行这一路**；**完整版 v2.1/v2.4 的 TTS = GPU.0 ⇒ 同样保持串行**⇒ **§2 的并行只对 SpecialMVP（CUDA）生效**，另两种形态**行为不变**。

### ⑤ §4 **sp4 已出**（sp3 逐字节未动）＋ 验收

**包**：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp4`

| 项 | 值 |
|---|---|
| 版本 | `1.0-sp4` |
| 基于 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp3`（**sp3 逐字节未动**） |
| 文件数 | 41374 |
| 目录字节 | 14232064511 |
| `.pyc` | 0 |
| 黑名单命中 | 0 |
| 包内 app 文件与 dev 不一致 | **无** |
| `pyvenv.cfg` 含 sp3 路径 | False |
| 构建判定 | **PASS** |

构建证据：`results/app/app587_specialmvp_sp4_build.json` ｜ 3577 B ｜ mtime 2026-11-16 20:28:49 ｜ SHA256 `aa8dc6bd22cac797`

🔴 **未打 zip**（APP-113 §4 明文「zip 等验收通过后再打，现在不打 sp4 zip」）⇒ `shared/specialmvp/` 下**仍只有 sp1 的 zip**。

**验收结果**（每臂：固定 10 分钟片段 SPE 0–600 s；持 `shared/MACHINE_LOCK`；结果 json 内含**锁证据**与 `timing_valid`）：

| 项 | sp4 中文目标（并行） | sp4 英文目标（并行） | sp4 中文目标（串行对照） |
|---|---|---|---|
| 目标语言 | zh | en | zh |
| 判定 | **PASS** | **PASS** | **PASS** |
| 退出码 | 0 | 0 | 0 |
| 译文句数 | 164 | 164 | 164 |
| **就绪前排队** | 10 | 10 | 12 |
| **已补发** | 10 | 10 | 12 |
| **进 TTS 句数** | 164 | 164 | 164 |
| **丢句（任何原因）** | 0 | 0 | 0 |
| TTS 就绪 (s) | 37.6 | 37 | 43.6 |
| 积压清空 (s) | 75 | 75.8 | 69.4 |
| 积压清空口径 | play_lag_s | play_lag_s | play_lag_s |
| 倍率 P50 | 1.1 | 1 | 1.1029 |
| 倍率 P95 | 1.5332 | 1.3705 | 1.6737 |
| 倍率 max | 1.5332 | 1.3705 | 1.6737 |
| 倍率 ≥1.8× 句数 | 0 | 0 | 0 |
| 最大播放滞后 (s) | 33 | 31.6 | 38.5 |
| 末句播放滞后 (s) | 3.5 | 4 | 2.9 |
| `timing_valid` | True | True | True |
| 外部大 IO | 0 | 0 | 0 |
| 整轮耗时 (s) | 613.1 | 614.3 | 613.1 |

**逐条判定**：

- **zh-parallel**（`app588_sp4_acceptance_sp4_zh.json`） verdict=**PASS**（0 项 FAIL）：
  - [PASS] 丢句数（任何原因）= 0 ｜ worker丢弃=0 + 溢出丢弃=0
  - [PASS] 译文句数 == 进 TTS 句数 + 丢弃总数（无其它丢失路径） ｜ 164（译文）== 164（进 TTS）+ 0（丢弃）
  - [PASS] 就绪前排队的句子**全部补发**（一句不丢） ｜ 10（就绪前排队）== 10（已补发）
  - [PASS] 倍率 max ≤ 2.0 ｜ max=1.5332 p50=1.1 p95=1.5332
  - [PASS] 退出码 0 ｜ rc=0
  - [PASS] 产出齐备（wav + 逐句 jsonl + 积压曲线） ｜ _app588_sp4_zh_tts_out.wav,_app588_sp4_zh_tts_out.wav.tts.jsonl,_app588_sp4_zh_tts_out.wav.backlog_curve.csv
  - [PASS] 逐句 jsonl **无重复 id**（未混入上一轮的行） ｜ 重复 id 数=0（[]）
  - [PASS] TTS 就绪时刻已记录 ｜ TTS就绪=37.6 s（相对进程启动；收尾时进程已运行 608.2 s）
  - [PASS] 积压清空时刻已记录（口径=play_lag_s） ｜ 积压清空=75.0 s（口径 play_lag_s；末句播放滞后 3.53 s）
  - [PASS] ASR/TTS 并行生效（并行=on） ｜ parallel=True（请求=on）
- **en-parallel**（`app588_sp4_acceptance_sp4_en.json`） verdict=**PASS**（0 项 FAIL）：
  - [PASS] 丢句数（任何原因）= 0 ｜ worker丢弃=0 + 溢出丢弃=0
  - [PASS] 译文句数 == 进 TTS 句数 + 丢弃总数（无其它丢失路径） ｜ 164（译文）== 164（进 TTS）+ 0（丢弃）
  - [PASS] 就绪前排队的句子**全部补发**（一句不丢） ｜ 10（就绪前排队）== 10（已补发）
  - [PASS] 倍率 max ≤ 2.0 ｜ max=1.3705 p50=1.0 p95=1.3705
  - [PASS] 退出码 0 ｜ rc=0
  - [PASS] 产出齐备（wav + 逐句 jsonl + 积压曲线） ｜ _app588_sp4_en_tts_out.wav,_app588_sp4_en_tts_out.wav.tts.jsonl,_app588_sp4_en_tts_out.wav.backlog_curve.csv
  - [PASS] 逐句 jsonl **无重复 id**（未混入上一轮的行） ｜ 重复 id 数=0（[]）
  - [PASS] TTS 就绪时刻已记录 ｜ TTS就绪=37.0 s（相对进程启动；收尾时进程已运行 609.0 s）
  - [PASS] 积压清空时刻已记录（口径=play_lag_s） ｜ 积压清空=75.8 s（口径 play_lag_s；末句播放滞后 3.999 s）
  - [PASS] ASR/TTS 并行生效（并行=on） ｜ parallel=True（请求=on）
- **zh-serial**（`app588_sp4_acceptance_sp4_zh_serial.json`） verdict=**PASS**（0 项 FAIL）：
  - [PASS] 丢句数（任何原因）= 0 ｜ worker丢弃=0 + 溢出丢弃=0
  - [PASS] 译文句数 == 进 TTS 句数 + 丢弃总数（无其它丢失路径） ｜ 164（译文）== 164（进 TTS）+ 0（丢弃）
  - [PASS] 就绪前排队的句子**全部补发**（一句不丢） ｜ 12（就绪前排队）== 12（已补发）
  - [PASS] 倍率 max ≤ 2.0 ｜ max=1.6737 p50=1.1029 p95=1.6737
  - [PASS] 退出码 0 ｜ rc=0
  - [PASS] 产出齐备（wav + 逐句 jsonl + 积压曲线） ｜ _app588_sp4_zh_serial_tts_out.wav,_app588_sp4_zh_serial_tts_out.wav.tts.jsonl,_app588_sp4_zh_serial_tts_out.wav.backlog_curve.csv
  - [PASS] 逐句 jsonl **无重复 id**（未混入上一轮的行） ｜ 重复 id 数=0（[]）
  - [PASS] TTS 就绪时刻已记录 ｜ TTS就绪=43.6 s（相对进程启动；收尾时进程已运行 608.2 s）
  - [PASS] 积压清空时刻已记录（口径=play_lag_s） ｜ 积压清空=69.4 s（口径 play_lag_s；末句播放滞后 2.906 s）
  - [PASS] ASR/TTS 强制串行生效（并行=off，对照臂） ｜ parallel=False（请求=off）

- **zh-parallel** 证据 json：`app588_sp4_acceptance_sp4_zh.json` ｜ 16235 B ｜ mtime 2026-11-16 20:39:10 ｜ SHA256 `4dd1070f7a7913f1`
- **en-parallel** 证据 json：`app588_sp4_acceptance_sp4_en.json` ｜ 15892 B ｜ mtime 2026-11-16 20:49:32 ｜ SHA256 `0722fd7d4def2b35`
- **zh-serial** 证据 json：`app588_sp4_acceptance_sp4_zh_serial.json` ｜ 15848 B ｜ mtime 2026-11-16 20:59:53 ｜ SHA256 `a7a1c7c66abe42c0`

**≥1.8× 配音样本**（供用户抽听 2.0× 听感）：

- **zh-parallel**：候选 164 句（≥1.8×），抽出 3 段
  - `sp4_zh_fast_id11_speed1_53.wav` ｜ speed **1.5332×** ｜ 59084 B ｜ 与软件团队一起。 ｜ SHA `d27642f20e9e0f0f`
  - `sp4_zh_fast_id12_speed1_53.wav` ｜ speed **1.5332×** ｜ 145484 B ｜ [会议句 idx 439]。 ｜ SHA `bcead2f8dbb87c55`
  - `sp4_zh_fast_id13_speed1_53.wav` ｜ speed **1.5332×** ｜ 103724 B ｜ 去推动我们前方的发展，这是我所期望的。 ｜ SHA `601d6a3a0354564f`
- **en-parallel**：候选 164 句（≥1.8×），抽出 3 段
  - `sp4_en_fast_id11_speed1_37.wav` ｜ speed **1.3705×** ｜ 67724 B ｜ [会议句 idx 194]. ｜ SHA `d98efa7c0b981c83`
  - `sp4_en_fast_id12_speed1_37.wav` ｜ speed **1.3705×** ｜ 106604 B ｜ I think it’s probably one of the biggest ｜ SHA `70782a266d681fef`
  - `sp4_en_fast_id13_speed1_37.wav` ｜ speed **1.3705×** ｜ 138284 B ｜ To enable the growth ahead of us, which  ｜ SHA `6b223a61892dd2fd`
- **zh-serial**：候选 164 句（≥1.8×），抽出 3 段
  - `sp4_zh_serial_fast_id13_speed1_67.wav` ｜ speed **1.6737×** ｜ 110924 B ｜ 去推动我们前方的发展，这是我所期望的。 ｜ SHA `254b972e467d71c3`
  - `sp4_zh_serial_fast_id14_speed1_67.wav` ｜ speed **1.6737×** ｜ 220364 B ｜ 最后，我们会有足够的时间进行问答环节，既可以在现场进行，也可以在线进行。 ｜ SHA `fddce0aad718ec91`
  - `sp4_zh_serial_fast_id15_speed1_67.wav` ｜ speed **1.6737×** ｜ 28844 B ｜ 好的。 ｜ SHA `cbbc968e0b52aa71`

### ⑥ 🔴 **判据/日志自身的 3 处修正**（本轮实测暴露 ⇒ 先怀疑判据）

1. **对账公式重复计数**（验收脚本）：旧式「译文 == 就绪前排队 + 进 TTS」把**排队句数了两遍**（排队句本来就在「进 TTS」里）⇒ 上一轮报出**假 FAIL**。改为 **「译文 == 进 TTS + 丢弃」**，并另加独立不变式 **「排队句全部补发」（n_flushed == n_queued）**。
2. **「积压清空」口径错**（产品代码）：原来用 service 的 `lag_s`（＝**未播音频时长**）⇒ worker 刚开始合成时它恒为 0 ⇒ 会把「刚就绪、队列还没开始合成」误判成「已清空」⇒ 上一轮实测得到 **0.2 s**（而同期**最大滞后 87.97 s**）＝**假口径**。现在**只认 worker 回报的 `play_lag_s`**（＝实际开播 − 目标开播，service `stats()` 的顶层字段），**不回落 `lag_s`**；并**再加第二道闸**：就绪后必须**真的播出了 ≥ max(1, 已补发句数) 句**（`n_played` 增量）⇒ 才允许记「积压已清空」。口径记在 `stats()` 的 `backlog_cleared_lag_kind` / `backlog_cleared_played_delta`（可核对）。
3. **日志字段误标**（产品代码）：`[APP-113]` 行的 `TTS就绪(相对进程启动)`实际打的是**打印时刻的进程已运行秒数**（不是就绪时刻）⇒ 已更名为 `进程已运行`，**真正的就绪时刻**放在 `TTS就绪=`。

⇒ 🔴 **产品代码因此改过 ⇒ sp4 重新同步 ⇒ 两臂 + 对照臂全部在最终代码上重跑**（不是沿用上一轮的结果）。

**验收脚本自身也加了 2 道自检**（防「判据自己骗人」）：

- **跑前把上一轮的产物改名挪开**（不删）⇒ 上一轮的 jsonl 行不会混进本轮（worker 的 jsonl 是**追加**写、收尾才整体重写 ⇒ 若中途崩溃会留下旧行）。
- **逐句 jsonl 重复 id 自检** ⇒ 有重复就判 FAIL。

### ⑥b 🔴 **冷启动参考臂**（口径修正前的那一轮，**保留作对照**）

⚠️ **不是交付臂**：它跑在「积压清空口径修正**前**」的代码上（差别**只有**判据口径 / 日志字段名 / 死计数器删除 / 并行开关，**均不改变运行时行为**：队列、丢句、倍率、滞后全部同逻辑）。保留它的唯一原因是：**那一轮是「真冷启动」**（CUDA 边车与模型文件都没缓存），⇒ 是唯一能产生 **≥1.8×** 样本的一轮。

| 项 | 值 |
|---|---|
| 译文句数 | 164 |
| 就绪前排队 / 已补发 | 25 / 25 |
| 进 TTS 句数 | 164 |
| 丢句（任何原因） | 0 |
| TTS 就绪 | **120.1 s**（边车加载 102.1 s） |
| 倍率 P50 / P95 / max | 1.1643 / 1.8024 / **1.8204** |
| ≥1.8× 句数 | **11** |
| 最大播放滞后 | **87.969 s** |
| 末句播放滞后 | 3.081 s |

> **数字出处（诚实声明）**：倍率/滞后/RTF 一栏取自该轮 **run stdout 日志**（下表下方给出文件 + SHA）；**「就绪前排队 25 / 已补发 25 / TTS 就绪 120.1 s / 边车加载 102.1 s / ASR 就绪 32.3 s」**取自**该轮的结果 json**——🔴 **该 json 已被下一轮同名产物覆盖**（验收脚本同名覆盖），这 5 个字段是本会话**当时读到的原文**；该轮的 `timing_valid` 当时实测为 **True**。

**冷启动 vs 热缓存**：CUDA 边车加载 **102.1 s**（冷）→ **28.4 s**（热）；ASR 就绪 **32.3 s**（冷）→ **5.0 s**（热）；⇒ **TTS 就绪时刻相差 ~3 倍** ⇒ **就绪前排队句数 25 → 10** ⇒ **积压规模差 2.5 倍** ⇒ **倍率上限能不能摸到，取决于机器冷热**。

⇒ 🔴 **结论：2.0× 只有在「冷启动 + 大积压」下才够得着**（中文下限 1.10× ⇒ 需 lag ≥ 39 s；非中文下限 1.00× ⇒ 需 lag ≥ 43 s）；热缓存下积压只有 ~32 s ⇒ 实测倍率上限 ~1.49×。

冷启动参考臂原始输出：`results/app/_app588_zh_run1_cold_runner.log` ｜ 1784 B ｜ mtime 2026-11-16 20:27:39 ｜ SHA256 `3b324a9aaaae19e7`
> ⚠️ **该 `.log` 被 `.gitignore` 的 `*.log` 排除 ⇒ 不进仓库**⇒ 为免「引用的证据不在仓库里」，**原文逐字内联**在下面。

```text
[app588] 起：C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp4\python\python.exe C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp4\app\live_caption_app.py --cli --file C:\Users\Trekker-PTL\confucius4-openvino\test_audio\clip_10min_0_600.wav --asr-device GPU.0 --mt-device NPU --tts-device CUDA --translate zh --tts on --tts-out C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app588_sp4_zh_tts_out.wav
rc=0  {"n_rows": 164, "n_dropped_worker": 0, "n_drop_not_ready_overflow": 0, "n_drop_total_any_reason": 0, "n_played": 164, "dropped_ids": [], "dropped_reasons": [], "speed_p50": 1.1643, "speed_p95": 1.8024, "speed_max": 1.8204, "speed_min": 1.1, "speed_mean": 1.3472, "speed_gain_mean": 1.3381, "n_speed_ge_1_8": 11, "n_speed_ge_2_0": 0, "n_speed_at_floor_1_10": 56, "rtf_ewma_min": 0.5304, "rtf_ewma_max": 3.7847, "rtf_ewma_mean": 0.618, "play_lag_max": 87.969, "play_lag_p95": 81.2415, "play_lag_end": 3.081, "n_speed_floor_conflict": 8}
  [PASS] 丢句数（任何原因）= 0 | worker丢弃=0 + 溢出丢弃=0
  [FAIL] 译文句数 == 就绪前排队 + 进 TTS 句数（无其它丢失路径） | 164（译文）− 25（就绪前排队）= 164（进 TTS）
  [PASS] 倍率 max ≤ 2.0 | max=1.8204 p50=1.1643 p95=1.8024
  [PASS] 退出码 0 | rc=0
  [PASS] 产出齐备（wav + 逐句 jsonl + 积压曲线） | _app588_sp4_zh_tts_out.wav,_app588_sp4_zh_tts_out.wav.tts.jsonl,_app588_sp4_zh_tts_out.wav.backlog_curve.csv
  [PASS] TTS 就绪时刻已记录 | TTS就绪=120.1 s（相对进程启动 635.8 s）
  [PASS] 积压清空时刻已记录 | 积压清空=0.2 s
  [PASS] ASR/TTS 并行生效（并行=on） | parallel=True
VERDICT=FAIL -> C:\Users\Trekker-PTL\confucius4-openvino\results\app\app588_sp4_acceptance_sp4_zh.json
```

**≥1.8× 抽听样本（来自冷启动参考臂）**：

- `sp4_zh_fast_id41_speed1_82.wav` ｜ 188684 B ｜ SHA256 `bd2ac64160a33608`
- `sp4_zh_fast_id42_speed1_82.wav` ｜ 216044 B ｜ SHA256 `ac26592730a2cd46`
- `sp4_zh_fast_id43_speed1_82.wav` ｜ 197324 B ｜ SHA256 `01ca6a566445fa66`

### ⑦ 本轮纪律与未结项

- **零产品代码之外的越权**：只改 App 侧 `live_caption/` 5 个文件（`live_caption_app.py` / `time_stretch.py` / `tts_worker.py` / `tts_service.py` / `device_config.py`）。
- **未改** `status/app/CORRECTIONS_APP.md`（**只读**）。
- **未打 sp4 zip**（§4 明文）。**未动 sp3 / sp2 / sp1 任何目录或 zip**。
- **持锁**：每臂都先取 `shared/MACHINE_LOCK`（内容 = 模块名 PID 开始时间 说明），**排队等待不抢锁**；回收前用 ctypes `OpenProcess`+`GetExitCodeProcess` 判活。
- **未在 CPU 上跑推理**；**未调用 MiniMax**（回转写质量判定属 reviewer）。
- 🔴 **未结项**：**① 非中文目标上限虽已放开到 2.0×，但实测倍率 max ≈ 1.82×**⇒ **2.0× 的听感本轮未真正验证**（抽听样本是 1.8× 档）；**② 中文目标下限仍是 1.10×**，非中文是 1.00×（10-29 口径未动）；**③ 并行 vs 串行的取舍见 §③**（待 reviewer / 用户裁定）。

