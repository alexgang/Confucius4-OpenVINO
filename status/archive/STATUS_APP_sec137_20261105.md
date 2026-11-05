# STATUS_APP §137 正文（2026-11-05 13:37）

> 本件为 `status/app/STATUS_APP.md` §137 的**逐字正文**；STATUS 内只留速查表（APP-052 ④ 惯例）。
> 纠偏文件 `status/app/CORRECTIONS_APP.md` 本轮**只读、未修改、未提交**。

## 一、开工基线与收尾复核

| 项 | 开工（13:08 实测） | 收尾（13:37 实测） |
|---|---|---|
| `CORRECTIONS_APP.md` SHA256 | `3c06baa98d3f612a033742a277a0ece556648d60e850b0c398431520b2819f39` | 同左（逐字相同） |
| 字节数 | 206 686 B | 206 686 B |
| mtime | 2026-11-05 09:35:14 | 2026-11-05 09:35:14 |
| `## APP-xxx` 条数 | 70（APP-001 .. APP-070） | 70 |
| `STATUS_APP.md` 头部 `last_ack` | `APP-070` | `APP-070`（无新条目，不变） |

⇒ **不存在编号大于 `last_ack` 的新纠偏条目**；reviewer 本轮中途**未追加**条目（可如实写「SHA 零改动」）。
⇒ 按 APP-046「last_ack 追平后仍有未完成项就继续做、不空转」＋ 模块租约 TAKEOVER 规则「从断点继续、不从头重做」，本轮从 §136 的未完成清单续做。

## 二、租约／机器锁／断点

* `acquire app` ⇒ **TAKEOVER**（第 4 次）：上一租约 `0c4889a6` started 09:55:37、last_beat 11:11:03（117 min 前）、`live_pids=[]`、`alive=False`，其 note 记「rc3 设备级 3(a) PASS 9/0；app268 4/0；--check 崩溃 10/10 无崩；跑 GUI 相…」。本轮 token `ad14e111`。
* 断点产物已逐项核对：`app271_app069_rc3_cli_evidence.json` → `rc=0` / `wall_s=381.86` / `n_rows=76` / `content_criterion.verdict=PASS` / `C2_zero_runs_ge_0p3=0`；`app272_crash_out/progress.json` → `check` 10 条全 `rc=0` / `crashed=false`；`gui_00.log` 只有 1 行 ⇒ **GUI 臂未完成**。
* `MACHINE_LOCK` 开工时由 asr 模块持有（PID 46528，11:36:47，`asr118-param-ab-rows`）；独立 `ctypes OpenProcess` ⇒ **err=87（PID 不存在）** ⇒ 用项目 fail-closed 脚本 `_app239_reclaim_orphan_lock.py --reclaim` 回收。
* 第二次孤儿锁：本轮 GUI 臂工具调用被 SIGTERM 中断后，锁由 app PID 47088 持有；同样 `err=87` 确证死 ⇒ 同一脚本回收。
* 三次设备作业（MT 对比 ×1、GUI 探针 ×1、GUI 臂 ×2）均先 `wait_quiet_window_cpu(quiet_seconds=20)`（实测 `QUIET True` / `n_samples=4` / `waited_s=30.0`），再持 `MACHINE_LOCK`；作业结束 `release` 成功。未在 CPU 上跑推理／测速。

## 三、APP-069⑥ MT INT4 vs INT8（本条已完成）

* 首跑 **FAIL**：`_app273_mt_int4_vs_int8.py` 的 `load_segments()` 从 `minimvp.tts.jsonl` 按 `lang='en'` 取段；实测该文件 **76 行全是中文译文**（`lang='zh'`，首行 `text='大家早上好。'`）⇒ 过滤后 **0 段**，`APP273_EXIT=2`，无 tsv／无 evidence。
* 真实英文定稿来源：`results/app/app253_minimvp_out/minimvp.txt` = `shared/app_listen/minimvp_v1.0/minimvp_v1.0_final.txt`（**46 行，rc2/rc3 逐字节相同**），与 `app253_app066_minimvp_cli_evidence.json` → `summary.segs=46` 对齐；`minimvp.txt` 的 46 行与 TTS 侧 76 句中文是**不同粒度**。
* 修法：`_app274_fix_app273_loader.py` 做 bytes 级定点替换（只动 `load_segments()` 函数体＋`main()` 两处单行），唯一命中断言 ＋ `ast.parse` ＋ CRLF 保持 ＋ 写后逐字节复核；**旧正文未删**。反证证据 `app274_app069_loader_fix_evidence.json` **4 PASS / 0 FAIL**（F1 能取到段 / F2 全英文 / F3 旧口径 0 段 / F4 段数 = 46）。
* 持锁重跑（`app273_mt_compare_run.log`）结果，字段取自 `app273_mt_int4_vs_int8_evidence.json`：

| 字段 | 值 |
|---|---|
| `device` / `target` | `GPU.0` / `zh` |
| `int4_dir` | `Confucius4_LiveCaption_MiniMVP_v1.0-rc3/models/mt/mt2-int4sym-cw-q` |
| `int8_dir` | `hy_bench/ov/mt2-int8sym-cw-q` |
| `n_segments` | 46 |
| `n_exact_same` / `exact_same_pct` | 2 / **4.35 %** |
| `chrf_mean` / `chrf_median` | **74.029** / **76.697** |
| `n_different` / `sample_20_different` | 44 / 20 条已落盘 |
| `wall_int4_s` / `wall_int8_s` | 19.85 / 28.91 |
| `tsv_bytes` | 14 513 |

* 🔴 **口径差异，交 reviewer 裁定**：APP-069⑥ 原文写「76 个定稿英文段」，本机可查英文定稿只有 **46 段**（76 是 TTS 侧中文译文句数）⇒ 按 **46 段真实英文**跑，**未切句凑 76、未改参照、未调阈值**；`source.scope_note`／`source.reviewer_expected_n_segments=76` 已写进 evidence。`chrf_impl` 明确为 `difflib.SequenceMatcher.ratio()*100`（字符级近似，**非 sacrebleu chrF**），避免把近似值当标准 chrF。
* 质量判定仍由 reviewer 用 MiniMax 回转写／人工评判，本模块**未调用 MiniMax**。

## 四、APP-069② 启动崩溃（需等 reviewer 复核，未完成）

* §136 已落盘：`--check` 臂 **10/10 零崩溃**（`app272_crash_stats_evidence.json` 11:10 版 `n_runs=10` / `n_crash_0xC0000409=0`）。
* 本轮 GUI 臂首次续跑 `--phase gui --n 3`：第 0 次 `rc=1` / `wall_s=420.96` / `loaded=false` / `crashed=false` / 日志 1 行 ⇒ **420 s 等不到「模型加载完成」被 harness `terminate()`**，`rc=1` 不是产品崩溃码 `3221226505`。
* 单次探针（`app275_gui_probe.log`，`PYTHONUNBUFFERED=1`，等 90 s）：日志仍只有 1 行（160 B）、进程未退出 ⇒ **排除 stdout 块缓冲**。
* 定位：GUI 臂 cmd 只给 `--autostart`，**缺音频源** ⇒ 不进入模型加载流程；§135 `app259_app066_minimvp_gui_coldstart.py` L261 的真实口径含 `--source file --file <wav> --autostart --selftest …`。
* 修法：`_app276_fix_app272_gui_cmd.py`（bytes 级定点替换、唯一命中断言、`ast.parse`、写后复核）给 GUI 臂补 `--source file --file ~/shared/SPE_0000_0500.wav`，并给 check/gui 两处 env 补 `PYTHONUNBUFFERED=1`；把失效的 `progress.json.gui` 清掉（**先备份**为 `progress.json.superseded_20261105_1332`，`check` 10 条逐字保留）。`app276_app069_gui_harness_fix_evidence.json` **4 PASS / 0 FAIL**。
* 修后复跑 2 次（`--gui-timeout 90`）：仍 `loaded=false` / `rc=1` / `wall_s=90.56` 与 `90.54` / 日志 1 行 ⇒ **本自动化会话环境仍无法让 GUI 输出「模型加载完成」**。另 `event_log_crashes()` 的 PowerShell 读取线程报 `UnicodeDecodeError: 0xcb`（非 UTF-8 输出）⇒ 事件日志取证臂失败，`event_log=[]`。
* 现状证据 `app272_crash_out/app272_crash_stats_evidence.json`：`n_runs=12` / `n_crash_0xC0000409=0` / `crash_rate_pct=0.0` / `verdict=INCOMPLETE` / `by_phase.check.n=10` / `by_phase.gui.n=2`。
* 🔴 结论：**GUI 有效启动 0/10，APP-069② 的「20 次启动 0 崩溃」验收未完成**；2 次 `rc=1` 是 harness 超时（不是产品缺陷）⇒ **不做「已通过」也不做「产品 FAIL」判定**（三态：无法判定）。需交互会话／reviewer 复核后再推进。崩溃根因 DLL 未定位，`faulthandler`／Windows 事件日志取证未完成。

## 五、仍待办（§136 未清项，本轮按纪律不越界）

1. ⛔ **APP-070① 删除 NPU 不加载的 TTS IR**：§136 明示候选 **975.9 MB** vs reviewer 估「约 567 MB」的**出入待 reviewer 裁定**；reviewer 明文顺序 ① 清单 → ② 删 → ③ e2e 证明 ⇒ 清单 `app270_tts_ir_inventory_evidence.json`（4/0）已在，**一个文件都没删**。
2. ⛔ **APP-070② A+C 设备级指标**（第一句可用时间／全编完时间／峰值内存／CPU，冷启 ≈ 20 min）与 **APP-069④ (i)–(iv)** 未跑。
3. ⛔ **APP-069⑦ rc3 zip** 未打：依赖 ② 完成；用户级纪律「未经用户明确通知不主动打包」仍有效；未通知用户、未放快捷方式、未发出去。
4. ⛔ **APP-069① 验收**：`reviewer` 回转写 MER ≤ 8 % 未做（本模块不自行调 MiniMax）；rc3 新 wav 已落盘 `shared/app_listen/minimvp_v1.0/minimvp_v1.0_rc3_tts.wav`（15 252 044 B / 76 行 tsv），**未交给用户抽听**。
5. ⛔ **v2.3 继续暂缓**（APP-067 顺序 1→2→3、4→5）；**未通知用户／未改桌面快捷方式／未动 v2.1、v2.2、rc1、rc2 任何一字节**（rc3 目录为 §136 构建，本轮未改）。

## 六、本轮产物清单（14 个文件，均落盘；SHA256 列写前 16 位，全值可复算）

| 文件（`results/app/` 下，除注明外） | 字节数 | mtime | SHA256（前 16 位） |
|---|---|---|---|
| `_app274_fix_app273_loader.py` | 4 285 | 13:16:28 | `b88e6bd24e5b235b…` |
| `app274_app069_loader_fix_evidence.json` | 1 863 | 13:16:46 | `c77408cd5bb3096e…` |
| `_app273_mt_int4_vs_int8.py`（修后） | 8 172 | 13:16:46 | `05694efe143a1b9d…` |
| `app273_mt_int4_vs_int8_evidence.json` | 9 482 | 13:18:34 | `29eb9d07731ec9c3…` |
| `app273_mt_int4_vs_int8.tsv` | 14 513 | 13:18:34 | `deb231f224c6226d…` |
| `app273_mt_compare_run.log` | 1 615 | 13:18:34 | `6896984fe8f6b462…` |
| `app275_gui_probe.log` | 160 | 13:30:18 | `2fc2d6eca60f5268…` |
| `_app276_fix_app272_gui_cmd.py` | 2 238 | 13:32:54 | `169fe2aca1e67a1d…` |
| `app276_app069_gui_harness_fix_evidence.json` | 1 705 | 13:33:05 | `ff1a177e6e4c9ee2…` |
| `_app272_rc3_crash_stats.py`（修后） | 12 338 | 13:33:05 | `cd75f7e88e27fd5b…` |
| `app272_gui_phase_run.log` | 519 | 13:19:37 | `41701177be61419a…` |
| `app272_gui_phase_run2.log` | 1 490 | 13:36:37 | `d4ef5b8c932978b5…` |
| `app272_crash_out/progress.json` | 1 838 | 13:36:37 | `6c184f80e4991404…` |
| `app272_crash_out/app272_crash_stats_evidence.json` | 2 307 | 13:36:37 | `0f3efa1cc8db387a…` |

> 说明：SHA256 列写前 16 位便于核对；全值可用 `hashlib.sha256(open(p,'rb').read()).hexdigest()` 复算。
> 另生成备份 `app272_crash_out/progress.json.superseded_20261105_1332`（不计入 14 个交付产物）。
