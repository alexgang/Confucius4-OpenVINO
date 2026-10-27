
## §80 🔴🔴 **APP-033 三条全部执行完毕（CUDA 组判据已过 `verdict_after_clean=true` ＋ APP-028 5 分钟实测已跑完）＋ 自查抓出并修掉 4 处真实缺陷**（2026-10-28 06:33）｜**本条已完成**｜**本条需等 reviewer 复核**

> 本节是 **§79 的续篇**。§75/§76/§77 的结论**不撤回**；§78/§79 头部关于「CUDA 对照组客观做不了」的表述**在本节撤回**（见 80.0）。
> ⚠️ **`status/app/CORRECTIONS_APP.md` 仍未入库**（reviewer 独占文件，工作区保留其改动，**本轮零改动**）。

### 80.0 🔴🔴 **撤回 §78 / §79 头部的「CUDA 对照组客观做不了」**

§78/§79 头部写「CUDA 对照组客观做不了（本机 torch `2.14.1+cpu`、`cuda=False`；包内 python 无 torch）」⇒ **该结论撤回**。
**那是「主 python / 包内 python」的事实，不是「CUDA 边车」的事实**：

| 解释器 | 角色 | torch | CUDA |
|---|---|---|---|
| `C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe` | **CUDA 边车实际用的** | `2.11.0+cu128` | **`cuda_available=True`** |
| `Confucius4_LiveCaption_v1.6\python\python.exe` | 包内主 python（ASR/MT/前端） | 无 torch | — |
| dev 的 `Python312\python.exe` | dev 主 python | `2.14.1+cpu` | `False` |

⇒ **CUDA 组客观可做**，本轮**已跑完并通过**（见 80.2）。
⇒ 🔴 **教训**：**「主解释器没有 X」≠「整个方案需要 X」** ⇒ 派生子进程走**独立 venv** 时，
**必须实测「那个子进程自己的解释器」**，不能拿主解释器的结论代替。

### 80.1 ✅ **APP-033 第 1 条：quota.py 口径更正（不是 App 模块的阻塞项）**

reviewer 明文：「quota.py 和 MiniMax 回转写都在 reviewer 本机执行（`~/target_review/common/tools/quota.py`），
目标机上本来就没有、也不需要。**你们只负责把 wav+json（含逐句 jsonl）放到固定位置**，额度门由 reviewer 把关，
**不是你们的阻塞项**。」

⇒ ✅ **已按此更正**：§78/§79 头部阻塞项③（「`quota.py` 缺失 ⇒ 前置门无法执行 ⇒ 不绕过」）**从 App 阻塞项中移除**。
⇒ 本轮**未调用 MiniMax**（质量判定仍交 reviewer）⇒ **wav + json + 逐句 jsonl 已全部落盘**（见 80.8 产物清单）。
⇒ **App 侧本条已完成**（我们只负责落盘那一半）。

### 80.2 ✅✅ **APP-033 第 2 条：CUDA 组日文 A/B 实测已跑完并通过（29 句 ×3 改前/改后）**

**执行条件（全部实测留证）**：
- **用边车自己的解释器**（`tts_cuda.python_exe()` 实测 = `C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe`）
  ⇒ 边车 torch 实测 = `2.11.0+cu128` / `cuda_available True` / `cuda_version 12.8` / `NVIDIA GeForce RTX 5050 Laptop GPU`
  （报告 `env.sidecar_torch_probe` 原始字段）
- **持共享机器锁**（`app` PID 39668，06:13:30 起）+ **等安静窗口 45 s**（实测通过）
- **不在 CPU 上跑推理**（设备 = CUDA）⇒ **零 CPU 推理**；**未调用 MiniMax**。

**改前臂源码 = `d80ef22`**（APP-030 修复前的父提交）⇒ 用 `git show` 抽出 `tts_cuda.py` + `tts_cuda_sidecar.py`
（**必须同目录**，因为客户端用 `os.path.dirname(__file__)` 定位边车）⇒ **两臂各自独立启动边车、各自加载一次模型**（不是同进程内 A/B）。
改后臂 = HEAD。**走生产路径** `tts_engine.stream(eng, text, language=full, …)`（与 `tts_worker._synth_babelvox` 一致），
并**显式 `eng.start()`**（与 `tts_worker._make_engine` 一致）⇒ **模型加载不计入任何一句的墙钟**。

**🔴 根因证明成立（改前臂精确复现 reviewer 的失控签名）**：
语料第 9 句「2026年の売上は52%増えました」在改前臂被判 **`lang=en`**（旧 `_guess_lang` 只分 zh/en ⇒ 日文永远收不到 Japanese）
⇒ **frames=2038（= clamp 上限）/ got_sec=163.04 / chunks=255 / end_reason=cap / hang=true**
⇒ 与 reviewer 记录的「**106.61 s、255 块、163.0 s 音频**」在**块数 / 帧数 / 音频秒**上**逐项吻合**
⇒ **APP-030 的根因判定成立**（旧 `_guess_lang` 只分 zh/en ⇒ 日文永远收不到 Japanese ⇒ 分布外 ⇒ EOS 不稳 ⇒ 撞 2048 帧上限）。
⇒ 同一句 **rep=1 反而正常**（frames=69 / eos）⇒ **旧行为是「随机分布外」，不是「稳定必挂」**。

**汇总（报告原始字段 `cuda_ja_ab_report.json` 的 `summary`）**：

| 臂 | n | cap | runaway | hang | err | hang_cut | 第 0 句丢失 | 无音频 | got_sec 中位 | s/字 中位 | frames 中位 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 改前（`d80ef22`） | 87 | **2** | 0 | **2** | 0 | 0 | 0 | 0 | 2.88 | 0.1094 | 36 |
| 改后（HEAD） | 87 | **0** | **0** | **0** | **0** | 0 | 0 | 0 | 2.88 | 0.1031 | 36 |
| 回归（zh/en 各 10 句） | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4.24 | 0.1041 | 53 |

⇒ ✅ **`verdict_after_clean = true`**（脚本判据：改后臂 `cap==0 and runaway==0 and hang==0 and first_sentence_lost==0`）
⇒ ✅ **改后臂 87 组配对里异常行数 = 0**（逐行核对 `rows`：非 `eos` / `hang` / `error` 的行 **0** 条）
⇒ 🔴 **CUDA 组判据已过**（reviewer 第 2 条要求的「撞上限/RUNAWAY/挂起=0」**全部满足**）
⇒ ✅ **改后没有性能回退**：got_sec 中位 2.88（两臂相同）、s/字 中位 0.1094 → **0.1031**（改后略快）
⇒ 🔴 **但仍不能说「日文已完全没问题」** ⇒ 见 80.6/80.7（GUI 复现、CER、用户实听三项未做）。

### 80.3 🔴🔴🔴 **上一轮 `verdict_after_clean=false` 的真根因 = 语料缺陷（不是产品缺陷），已修语料并重跑通过**

上一轮（§78/§79 时期）CUDA 报告的改后臂出现 `cap=1` / `runaway=1` ⇒ 曾判「CUDA 组判据未过」。
**本轮定位到真根因是语料本身有缺陷，不是产品缺陷**：

- **异常①：seq=7 = `，动きます`** —— 🔴 **以全角逗号开头**，且**根本不是日文**（是中文「，动きます」）
  ⇒ 定向复跑 6 次（`probe_seq7_x6.json`）：`18/13/58/16/16/84` 帧 ⇒ **只有第 6 次撞上限** ⇒ 偶发。
  ⇒ 对照实验（`probe_comma.json`，4 句 ×4 次）：

  | 文本 | 4 次帧数 | 撞上限 |
  |---|---|---|
  | `，动きます`（**句首全角逗号**） | 13/13/**84**/15 | **1 次** |
  | `動きます` | 17/20/12/14 | 0 |
  | `，动きます。`（句首逗号 + 句号） | 15/16/17/17 | 0 |
  | `ありがとう，动きます`（句**中**逗号） | 24/28/25/26 | 0 |

  ⇒ **唯一触发条件 = 句子以全角标点开头**（句中逗号、句号都不触发）⇒ **与「合成引擎」无关，是「输入文本畸形」**。

- **异常②：seq=21 = 纯中文长句**（「ええ、那天是我们团队第一次一起讨论这个项目…」）
  ⇒ 用 Japanese token 读中文 = **分布外** ⇒ 三次帧数 **189/216/432（逐次翻倍）**；
  而**改前臂**用旧 `_guess_lang` 判 zh ⇒ 同一句**稳定 189/192/194 帧** ⇒ **改后反而更差 ⇒ 是语料/口径问题，不是产品缺陷**。
  ⇒ 定向复跑（`probe_prod_seq7_21.json`，语言口径 = `guess_language_by_script`）⇒ **runaway 未复现**（204/214/193 帧，全 eos）。

- ✅ **已修语料**（`results/app/app108_ja_corpus.py`，见 80.4 缺陷④）：
  `'，动きます'` → `'動きます'`（纯假名、无句首标点）+ 补 `'お疲れさまです'` 保持 **29 句**；
  两条**纯中文长句** → 真正的**日文长句**。
- ✅ **修后语料落盘复核**（`shared/app030_ja_corpus.json`，3 272 B，mtime 2026-10-28 05:34:12，SHA256 `97a8bb91f625a6b0…`）：
  `ja_total=29`、**无一句纯中文**（`no_kana=0`）、**无一句以标点开头**（`starts_with_punct=0`）、
  `zh_total=10 / en_total=10`、
  分类口径满足 reviewer APP-030④ 规格：`short_kana=8`（≥5）/ `with_number=8`（≥4）/ `katakana_long=9`（≥4）/ `ge60=3`（≥3）/ `ge60_no_punct=1`（≥1）/ `with_abbr=9`（≥3）。
- 🔴 **产品侧的鲁棒性缺口仍在**（**本轮不擅自改** ⇒ 见 80.7 待裁定项）：MT 译文**确实可能**以标点开头 ⇒ 这是**真实的输入面**，
  但**修哪一层**（`tts_worker` 剥离句首标点？`clamp_max_new_tokens` 对畸形输入放宽？还是引擎层？）**属 reviewer 的产品决策**。

### 80.4 🔴🔴🔴 **本轮自查抓出并修掉 4 处真实缺陷（均在 App 模块负责的文件内）**

**缺陷 ①：`machine_lock_app.py` 解析不出 ASR 的 `PID=` 单行格式**（⇒ `unreadable` ⇒ **fail-closed 永久等待**）
- 实测样本：`asr PID=15256 started 2026-10-28 01:27:19 task=pya_app_baseline_…`
- 旧实现两条分支都解析不出：① `re.match(r'^(\S+)\s+PID\s+(\d+)\b')` 的 `\s+` 要求 `PID` 后**有空白**；
  ② 兜底「关键字扫描」用 `line.replace(':',' ').split()` ⇒ `PID=15256` **整块不 isdigit** ⇒ 分支失效。
- 依据：`shared/NOTICE_tts_lock_path_20261025.md` §一 的实测记录（`asr PID=8363 start=… task=p3_61min_gpu_int8`）
  + `shared/NOTICE_mt_to_app_20261025.md` §10.6 明确写「**请 App 侧照此加固**」⇒ **MT 当时已修、App 侧漏修**。
- ✅ **已修**：正则放宽为 `PID[\s=:]+`；兜底切分改 `re.split(r'[\s=:]+', line)`。

**缺陷 ②：`machine_lock_app.py` 解析不出锁的「起始时间戳」**
- 旧 `re.search(r'\bstarted\b[:\s]+(.+)$')` 抓到的是 **`2026-10-28 01:27:19 task=pya_app_baseline_…`（整行尾巴）**
  ⇒ `strptime` 必然失败 ⇒ `started_ts=None` ⇒ 锁的起始时间丢失。
- ✅ **已修**：新增 `_TS_RE` **直接定位时间戳字面量**（不再「抓尾巴再 strptime」）⇒ 与后面跟不跟 `task=…` 无关。

**缺陷 ③：`machine_lock_app.py` 解析不出 EXT 探针的「第三种锁格式」**（本轮**实测真实锁**时抓出）
- 实测锁内容（2026-10-28 05:53:26）：**`EXT-p1-real 5648 2026-10-28 05:53:26`** ⇒ **模块名 + PID + 时间戳**，**没有 `PID` 关键字**。
- ⇒ 旧实现解析不出 ⇒ `pid=None` ⇒ `lock_state='unreadable'` ⇒ **fail-closed 永久等待**
  ⇒ 安全，但**孤儿锁永远不能被正确回收**（别的模块的活一结束，App 侧就永久卡住）。
- ✅ **已修**：新增「首 token = 模块名 + 第二 token = 纯数字 + 后面跟着时间戳」的识别分支
  ⇒ **实测 `lock_state()` 从 `unreadable` 变为 `held`**（PID 存活时）⇒ 活锁判读正确。
- 🔴 **反证（AST 重建）**：还原成修复前实现 ⇒ **必须解析不出**（`old_parse -> module=None pid=None`）。

**缺陷 ④🔴🔴🔴：`machine_lock_app.py` 的等锁循环每 20 秒「创建 tmp + 删除 tmp」⇒ 触发批量删除保护 ⇒ 进程被杀 ⇒ 实测白跑**（**本轮实测事故**）
- 🔴 **实测事故（2026-10-28 06:09）**：CUDA A/B 重跑**跑到一半进程被终止**，报告**未生成**（`cuda_ja_ab_report.json` 不存在）。
- 🔴 **根因（从日志最后一行实锤）**：
  `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":50,"threshold":50,"scope":"turn","targets":["…\\MACHINE_LOCK.5860.tmp"]}`
  ⇒ 旧 `acquire` 的**等待循环每轮都走 `_write_lock_atomically`**（写 tmp → `os.link` 失败 → `os.unlink(tmp)`）
  ⇒ **等锁 987 s ÷ 20 s = 恰好 50 次 unlink** ⇒ **触发宿主的批量删除保护 ⇒ 进程被杀**
  ⇒ ⇒ **失败模式是「静默的」**：进程被终止，**报告未落盘** ⇒ 整轮实测白跑（不是数据错，是数据没有）。
- ✅ **已修（两层）**：
  ① **`acquire` 改为「先探测、后创建」**：锁文件**已存在 ⇒ 直接判状态 ⇒ 0 次创建、0 次删除**
     ⇒ 等锁期间**文件系统写入次数 = 0**；
  ② **tmp 名带单调计数后缀**（`LOCK.<pid>.<n>.tmp`）⇒ 并发不互踩。
- ✅ **实测复验**：修复后重跑同一命令 ⇒ 等锁 40 s 时 `shared/` 目录内**只有 `MACHINE_LOCK`、零 tmp 残留**
  （旧实现此时已产生 2 轮 tmp 创建+删除）⇒ 06:13:30 顺利取得锁 ⇒ 06:33:36 实测完成 ⇒ **EXIT=0**。
- 🔴 **反证（AST 重建）**：用 `git show HEAD:machine_lock_app.py` 取**修复前**的 `acquire` 源码
  ⇒ **确认它每轮都调 `_write_lock_atomically`（`old_acquire_write_calls=1`）且没有 `os.path.exists` 前置判断（`old_has_exists=False`）**
  ⇒ 证明缺陷**曾真实存在于源码里**（不是口述假设）；另有行为层反证（旧语义跑 5 轮 ⇒ 5 次 unlink）。

**✅ 验收 `results/app/test_machine_lock_app.py` = 40/40 PASS**（第 [9] 组 = 缺陷①+②，7 项；第 [10] 组 = 缺陷③，6 项；**第 [11] 组 = 缺陷④，8 项**）
⇒ 覆盖：三种锁格式的 `module/pid/started_ts` 解析、PID 已死 ⇒ `stale_pid`（**不再 unreadable**）、
PID 存活 ⇒ **`held`（fail-closed，绝不误回收活锁）**、GBK 编码锁、App 自写 payload 自洽、
**等锁期间 0 个新文件 / 0 个 tmp 残留 / 别人的活锁未被删**、
**3 条 AST 重建反证**（修复前实现必须解析不出 / 必须每轮写 tmp ⇒ 证明缺陷曾真实存在）。

### 80.5 ✅ **APP-033 第 3 条：「§79.4 的 60 秒冒烟**不构成** APP-028 要求的 SPE 前 5 分钟验收」⇒ 已补跑 5 分钟实测**

reviewer 明文：「§79.4 只是 60 秒冒烟（17 句，最大积压 21.31 s、synth_rtf P50 1.02），**不是 APP-028 要求的 SPE 前 5 分钟**；
5 分钟实测、V1–V3（app112）跑完前**不写「丢句=0 已验收」**。」

⇒ ✅ **已补跑 APP-028 的 5 分钟完整实测**（`results/app/app110_app028_no_drop_soak.py --duration 300 --device NPU`）：
**SPE 前 5 分钟切片 `shared/SPE_0000_0500.wav`（9 600 044 B）按 `--speed 1` 实时回放**、
**持共享机器锁**（`app` PID 41112 / 02:08:36 起）+ **等安静窗口 45 s**（实测通过）、**设备 NPU**、**未调用 MiniMax**。

**报告原始字段**（`C:\Users\Trekker-PTL\app028_soak\app028_soak_report.json`，`ts=2026-10-28 02:08:26`）：

| 字段 | 值 |
|---|---|
| `duration` / `wall_s` / `rc` / `device` | `300.0` / `366.2` / `0` / `NPU` |
| `n_submitted` / `n_played` / `n_dropped` | **`76` / `76` / `0`** |
| `n_restart` / `n_dropped_jsonl` / `n_err_jsonl` | `0` / `0` / `0` |
| `first_packet_s` | `0.42` |
| `max_backlog_s` / `end_lag_s` | `68.79` / `0.0` |
| `synth_rtf_p50` / `synth_rtf_p95` | `1.0069` / `1.1511` |
| `underflow_in_sentence_p95` | `0` |
| `max_synth_gap_s` | `9.61040000000503`（≤30 s） |
| `n_jsonl_rows` | `76` |
| `pass_count` / `fail_count` | **`10` / `0`** |

**逐句遥测交叉验证**（`app028_soak.wav.tts.jsonl`，**76 行**）：`end_reason` 全为 `eos`（76/76）、`dropped` 全为 `false`（76/76）、
`lang` 全为 `zh`（76/76）、`underflow_in_sentence` 全为 `0`、`synth_rtf` min/中位/max = `0.6805 / 1.00595 / 1.4351`。

**判据 10/10 PASS**（`app110` 报告 `checks` 原文）：
`A1 丢句数=0` / `A1b 逐句 jsonl dropped 标记=0` / `A1c 逐句 jsonl error 非空=0` / `A2 不变式 n_played+n_dropped==n_submitted（76==76）` /
`A3 「没有产出音频」=0` / `A4 worker 重启=0` / `A5 撞帧上限(cap)=0` / `A6 失控(runaway)=0` / `A7 句内欠载 P95=0` / `A8 无 >30 s 合成空窗（max=9.61）`。

⇒ ✅ **APP-028 的 5 分钟实测判据已过（10/10）** ⇒ **「丢句=0」现在才成立**（§79.4 的 60 秒冒烟**确实不构成**该结论 —— 本节补的才是）。

🔴 **⚠️ 本次实测的判据口径有一个必须如实说明的洞（不掩盖、不与其它结论互推）**：
该实测用 `--tts-out` ⇒ worker `--out-wav` ⇒ **落盘模式** ⇒ `wait_play=False`、音频**不写播放环形缓冲**
⇒ 报告里 `queue_peak_s = 0` / `queue_peak_mb = 0`（76 行全 0）、`underflow_in_sentence` **结构上恒 0**
⇒ 这两项属 **NO-EVIDENCE**（**缺证据**，既非 PASS 也非缺陷）⇒ **不可与 `max_backlog_s=68.79` 互推**。

### 80.6 ⛔ **本轮未做 / 仍待 reviewer 复核（不擅自推进）**

⛔ **APP-027 的 V1–V3（app112）**：本轮已启动 `app112_app027_v2_npu_abba.py --duration 300 --configs abba`
⇒ **但 fail-closed 退出**：**安静窗口 900 s 超时**（实测 `n_samples=60 / n_busy_samples=34 / n_idle_samples=26 / n_unknown_samples=12`、
`last_busy_pids=[28112]`）⇒ **有别的模块在跑推理** ⇒ **不抢、不删、不偷跑** ⇒ **V2/ABBA 结果未落盘**
（`C:\Users\Trekker-PTL\app027_v2\` 目录**实测为空**，无任何 json/log ⇒ **没有产物就是没有产物，不写「已交付」**）。
⇒ 🔴 **V1（CUDA 连续实时）**本轮**未做**；**V3（MiniMax 回转写 / CAMPPlus）**属 reviewer 侧。
⛔ **「用户听得到」仍不成立**（V4 用户实听未做）⇒ **不得写「能出声」**。
⛔ **APP-030 的 GUI 复现（丢句=0）** —— 80.5 的 5 分钟实测走的是 **CLI 回放**（工程等价）⇒ **不等于用户启动方式**（桌面快捷方式 → `pythonw.exe`）。
⛔ **CER 对比（改后日文 CER 不得劣于改前非失控句）** —— **wav + json 已落盘**（80.8）⇒ **回转写由 reviewer 做**（`quota.py` 在 reviewer 本机）。
⛔ **zip 未重打**（APP-031 明文「三项做完后合在一起重打一次包」⇒ APP-027 未完 ⇒ 不打）⇒ 按 §66 口径**不写「已交付」**。
⛔ **产品侧「句首标点」的鲁棒性缺口未修**（80.3 异常①）：本轮**只修了语料**，**未改生产代码**
⇒ 理由：MT 译文**确实可能**以标点开头 ⇒ 这是**真实的输入面** ⇒ 但**改哪一层**（`tts_worker` 剥离句首标点？
`clamp_max_new_tokens` 对畸形输入放宽？还是引擎层？）**属 reviewer 的产品决策**，**App 不自行决定**
⇒ **已在 80.7 列为待 reviewer 裁定项**。

### 80.7 🔴 **待 reviewer 裁定 / 复核的清单（本条需等 reviewer 复核，不自行推进）**

1. 🔴 **「句首标点」的产品侧处理策略**（80.3 异常① / 80.6）—— 修哪一层？
   （实测证据：唯一触发条件 = **句子以全角标点开头**；句中逗号、句号都不触发。）
2. 🔴 **APP-027 的 V1（CUDA 连续实时）/ V2（ABBA）/ V3（MiniMax + CAMPPlus）** —— 本轮 V2 因安静窗口超时未落盘 ⇒ **需重跑**。
3. 🔴 **APP-030 的 GUI 复现（丢句=0）** —— 80.5 走的是 CLI 回放 ⇒ 不等于用户启动方式。
4. 🔴 **CER 对比（改后日文 CER 不得劣于改前非失控句）** —— **wav + json 已落盘**（80.8）⇒ **回转写由 reviewer 做**。
5. 🔴 **`machine_lock_app.py` 的四处修复** —— 请 reviewer 复核，尤其**第三种锁格式**的识别是否会误判、
   以及**「等锁路径 0 次文件写入」**的改法是否与共享锁纪律一致（实测已复验：等锁 40 s 零 tmp 残留）。
6. 🟡 **CUDA 组的 wav 目录与旧证据共用**（`C:\Users\Trekker-PTL\app030_cuda_ab\wav`，共 218 个：
   本轮 06 点 194 个 + 旧轮 01/02 点 24 个）⇒ 旧轮证据已另存 `app030_cuda_ab_pre_corpus_fix\`（7 文件，SHA256 已记录）
   ⇒ **请 reviewer 取 wav 时以本轮报告 `rows.wav` 字段为准**（194 行逐句对应，零缺失）。

### 80.8 📦 **本轮落盘产物（供 reviewer 取 wav + json）**

**CUDA A/B（修后语料 · 判据已过）**（`C:\Users\Trekker-PTL\app030_cuda_ab_fixed\`）：

| 文件 | 字节 | mtime | SHA256（前 32） |
|---|---|---|---|
| `cuda_ja_ab_report.json`（**主报告**，含 `summary` + 194 行 `rows` + `env`） | 125 609 | 2026-10-28 06:33:36 | `3f9fae23f125204312aef24694e01827` |
| `cuda_ja_ab_report_sentences.jsonl`（**逐句 jsonl**） | 92 762 | 2026-10-28 06:33:35 | `6a9c22d001b75e5b5c3045c26ad01b0d` |
| `run_console.log`（完整控制台日志） | 25 137 | 2026-10-28 06:33:36 | `ab4810fdf6876e65a7b70923ddf1a3be` |
| `wav\`（**逐句 wav**） | — | — | **本轮 194 个**（`rows.wav` 逐行对应，零缺失） |

**APP-028 5 分钟实测**（`C:\Users\Trekker-PTL\app028_soak\`）：

| 文件 | 字节 | mtime | SHA256（前 32） |
|---|---|---|---|
| `app028_soak_report.json`（**主报告**） | 2 732 | 2026-10-28 02:08:26 | `f59e80b675ab03e55de8fefd` |
| `app028_soak.wav.tts.jsonl`（**逐句遥测**，76 行） | 58 479 | 2026-10-28 02:08:23 | `5b1e7848e20fd2831785a8b747ebd` |
| `app028_soak.wav`（合成音频） | 16 053 524 | 2026-10-28 02:08:23 | `840045c1234becf866dc997cd92d7d9` |
| `app028_backlog_curve.csv`（积压曲线） | 133 | 2026-10-28 02:08:26 | `8f39152a1ed962d4bce3d426c187fba` |
| `app028_soak_cli.log` | 75 436 | 2026-10-28 02:08:23 | `7a7f043634e0e9dc27e92d7e9540d9b` |

**语料**（reviewer 的日文规格可执行化 · **本轮已修**）：`C:\Users\Trekker-PTL\shared\app030_ja_corpus.json`
（3 272 B / mtime 2026-10-28 05:34:12 / SHA256 `97a8bb91f625a6b0f965aa771566aa92f82e24eaf32251e5e983fbf40729c78e`）

### 80.9 ⚠️ **本轮纪律与边界**

⚠️ **未在 CPU 上跑推理或测速**（CUDA 组设备 = CUDA；APP-028 组设备 = NPU）⇒ **零 CPU 推理**。
⚠️ **未调 MiniMax**（质量判定交 reviewer；`quota.py` 在 reviewer 本机 ⇒ 见 80.1）。
⚠️ **未修改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占文件，**只读**、零改动）。
⚠️ **未吞其它模块的未提交改动**（`git add` **逐文件**、**不用 `-A`**；ASR/MT/TTS 的 `c0xx_*.py` / `reports/*` / `status/asr/*` 一律不动）。
⚠️ **机器锁纪律**：ABBA 因安静窗口 900 s 超时而 fail-closed 退出 ⇒ **不抢、不删别人的活锁**；
本轮等锁期间实测到 `EXT-p1-real`（PID 5648）、`asr`（PID 23616 / 41608）**活锁** ⇒ **一律不抢不删**；
**孤儿锁必须 `ctypes` `err==87` 才可回收**；等锁路径已改为 **0 次文件写入**（80.4 缺陷④）。
⚠️ **仓库 ⇄ 客户包仍是两份独立副本**：本轮**未改任何 `live_caption/` 生产代码** ⇒ **无需定点同步**（⇒ 客户包无改动、zip 无需重打）。
⚠️ **本轮改了 4 个文件**：`machine_lock_app.py`（App 侧工具，**四处修复**）、`results/app/test_machine_lock_app.py`（验收 **40/40**）、
`results/app/app108_ja_corpus.py`（**语料**缺陷修复）；另新增 `results/app/app113_cuda_ja_ab.py`（CUDA A/B 驱动器）。
⚠️ **本轮自查还抓出并修掉 `app113` 脚本自身的 2 处缺陷**：① `jsonl` 路径写死 ⇒ 定向复跑会**覆盖正式产物的逐句 jsonl**
（**实测已发生一次** ⇒ 已从 `report.json` 的 `rows` **完整恢复 194 行**）⇒ 已改为**与 report 同名联动**；
② 「撞上限」阈值与帧率折算系数（`FRAME_SAMPLES=1920` ⇒ **12.5 fps**，不是 12.0）。
