## §64 🔴 巡检（**APP-023 / APP-024 / APP-025 = 3 条新条目**）+ ✅ **APP-024① 首包拆两段** + ✅ **修掉「打包自检被自己的新验收脚本拦下」** + ✅ **交付代差闭环**（zip 三方一致）+ 🔴 **§63 的 L4 仍等用户**（2026-10-27 10:48）

### §64.1 巡检：`CORRECTIONS_APP.md` 本轮有 **3 条新条目**
`status/app/CORRECTIONS_APP.md` 指纹 **SHA256 `32991dc9bd3a4f35f94d731d7bdfb504dda225b587300879f1a4763bf9513431` / 59 279 B / mtime 2026-10-27 09:06:18**（上轮 `682aced289a58d18b…` / 48 457 B / 16:18:08）⇒ `^## APP-\d+` 命中 **25** 条，最大 **APP-025**；本轮进入前头部 `last_ack: APP-022` ⇒ 编号差 **3** ⇒ 触发 **APP-023 / APP-024 / APP-025**。
`CORRECTIONS_APP.md` 全程 **只读零修改**（reviewer 独占文件，本轮未 `git add`、远端 blob 仍为 `7082400b…`）。

### §64.2 ✅ 独立核实并发 App 会话的 APP-023①③④ / APP-025 成果（**全部真实落盘**）
并发 App 会话已于 09:50（`6d7ef24`）与 10:16（`0d1be9d`）提交并推送 `§63`。本轮**独立逐条核实**（不采信 `§63` 的自述）：

| APP-023 要求 | 独立核实方式 | 结论 |
|---|---|---|
| ① 边车 std 句柄 | `git show 6d7ef24 -- live_caption/tts_cuda.py` | ✅ `stderr` 恒 `PIPE` + daemon 抽水线程 + `_NO_WINDOW_FLAG()`（`CREATE_NO_WINDOW=0x08000000`）⇒ **绝不**走 `GetStdHandle`/`DuplicateHandle` |
| ① worker 解释器 | 读 `tts_service.py::_worker_python()` | ✅ pythonw→同目录 python.exe；⚠️ **弃用 `sys._base_executable`**（实测丢 venv，`numpy 2.4.6→2.5.4`） |
| ③ 去掉旧引擎回落 | AST 读 `tts_worker.py::load()` / `_try_load_babelvox()` | ✅ `load()` 内 **`_try_load_ov` 调用 0 处**；`_try_load_babelvox` **不再 `return None`**（抛 `RuntimeError(_babelvox_failure_reason(...))`）⇒ 缺 babelvox 直接报「缺少 Qwen3-TTS 运行时」 |
| ④ 测试音不依赖 worker | 读 `play_test_tone_direct` + GUI 调用点 | ✅ 本进程直放 440 Hz（不建 `TTSService`） |
| APP-025 报错可理解 | 读 `describe_tts_failure` / `_TTS_FAILURE_HINTS` | ✅ rc/`WinError 50`/缺 babelvox/`LLVM ERROR` → 一句人话 + **落盘日志路径** |
| APP-025 按钮置灰 | 读 `offline_reader_gui.py::_sync_availability` | ✅ `_poll` 里持续调用 ⇒ worker 不可用即置灰「开始朗读」+ 写明原因 |

### §64.3 🔴🔴 本轮真实缺陷 —— **打包自检被「自己的新验收脚本」拦下**（§48 闸门真的拦住了）
`pack_v13.py --dry-run` 判 **FAIL**（不是打包失败，是**自检**失败）：
```
🔴 违规 2 处：
  [A] results/app/app093_sync_integrity_check.py         行[29]
      PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\app'
  [A] results/app/app096_pythonw_launch_gate.py          行[33]
      PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
⇒ 修法：用 `pkg_paths.discover_pkg_dir()` / `pkg_paths.pkg_app_dir()`（单一数据源），**不写死版本号**。
```
⇒ **根因 = 验收脚本自己写死了包路径**（§48 的「包路径写死」缺陷类别）⇒ 修法 = 改用 `pkg_paths` 单一数据源。
⇒ ✅ 修后 `app093` **19 PASS / 0 FAIL**、`app096` **13 PASS / 0 FAIL**、`pack_v13.py --dry-run` **PASS**（关键文件全 `[OK]`、内部素材闸门 **0** 命中、第三方素材 **0** 命中）。
⇒ 🔴 **这条同时说明「§48 闸门不是摆设」**：它拦下了**本轮自己产出的**违规文件。

### §64.4 ✅ APP-024① —— **首包拆成两段上报**（本轮实现；APP-024②③④ 未做）
**根因（§49.7 的实测）**：旧 `latency_s` = 「submit → 首块到达」一个总值，把**排队等待**与**合成首包**混在一起 ⇒ §49.7 的「首包 P50 17.29 s」量到的是**加载期攒下的队一次性倒出来**（7 句 `t_submit` 跨度仅 0.115 s）⇒ **根本分不开**。
🔴🔴 **跨进程时钟不可比**（本轮的核心约束）：Windows `time.perf_counter()` 走 **QPC**、起点是**进程启动时刻** ⇒ 主进程与 worker 的 `perf_counter()` **基准不同** ⇒ **不能直接相减**。⇒ 拆分方案：
| 段 | 谁算 | 公式 | 为什么 |
|---|---|---|---|
| **排队等待** `queued_s` | **主进程** | `t_sent − t_submit` | 同一进程 ⇒ `perf_counter()` 同源可比（`t_sent` = 命令真正写进 worker stdin 的时刻） |
| **合成首包** `synth_s` | **worker** | `t_first − t_dequeue` | 同一进程 ⇒ 同源可比（`t_dequeue` = worker 主循环从 stdin 取到该命令的瞬间） |
| `latency_s`（旧口径） | worker | `t_first − t_submit`（worker 内部） | **保留不删** ⇒ 旧消费方（ABBA 报告）不受影响 |

改动（4 处）：`tts_service.py` `_send()` 在 flush 后回填 `pending[jid]['t_sent']` ｜ `tts_service.py` `first_packet` 分支算 `queued_s` 并写 `first_packet_parts`（进 `stats()`）｜ `tts_worker.py` 主循环记 `self._dequeue_at[jid]` ｜ `tts_worker.py` `synth()` 消费 `_dequeue_at`（`None` 兜底）+ `first_packet` 事件带 `synth_s`。
⚠️ **worker 回传的 `t_dequeue` 只作诊断**，**不参与**主进程排队段计算（跨进程不可比）。
**验收 `app097`**（新增）：REAL **20 PASS / 0 FAIL** + BUG **3/3 命中**（基线固定 `0d1be9d`，**不是 HEAD** ⇒ 提交后仍成立）。
- R9 行为级实测：`queued_s = 0.300`（submit 100.000 → 写 stdin 100.300）、`synth_s = 0.420`（worker 5.000 → 5.420）⇒ **两段确实是不同的数**；
- **R9d 反证**：若误用 worker 的 `t_dequeue` 去算排队段 ⇒ `100.000 − 5.000 = 95.0 s` ⇒ 完全离谱 ⇒ 证明「跨进程相减」这条铁律**有实测支撑**。
🔴 **本轮验收脚本自身踩了两次「判据假通过」（§62 同源教训，已修）**：① `'synth_s' not in src` 命中了 **`synth_stream`** 的**子串** ⇒ 改 `has_ident()` 走 AST；② 找 `emit({'kind': 'first_packet'})` 时查的是**字典的 key 列表** ⇒ 而 `'first_packet'` 是 **`kind` 这个 key 的 value** ⇒ 改成解析 `key→value` 映射。⇒ **判据自身也会假通过，必须逐条自证**。

### §64.5 ✅ 交付代差闭环（**§61 四步**全做，zip 三方一致）
**发现**：§63 同步了包目录（09:52）但 **zip 是 06:43** ⇒ `verify_pkg_zip.py` 独立复核报 **FAIL**、**5 个文件内容不一致**（`live_caption_app.py` / `offline_reader_gui.py` / `tts_cuda.py` / `tts_service.py` / `tts_worker.py`）⇒ **客户拿到的 zip 不含 APP-023 的任何修复**。
✅ **四步全做**（§61 定案顺序）：
1. **定点同步**（`sync_app023_to_pkg.py`：`git show` + `difflib.get_grouped_opcodes(n=3)` 自动派生，**不手抄**、**禁整目录覆盖**）；
2. **先提交 → 再打包** ⇒ 持共享锁 `app-pack` / **PID 32772** / 10:17:13 起 ⇒ `pack_v13.py` **14 min 7 s** ⇒ **PASS**、md5 `fcee4434ece1d49d0390f2879c9248be`、MANIFEST `version=1.5 / files=13985 / bytes=13668477340`、zip **13986** 条目**逐字节一致**、**原子改名**、锁已释放；
3. **独立复核** `verify_pkg_zip.py` ⇒ **PASS**：[1] zip⇄包目录 **13986 全部逐字节一致** + [2] HEAD⇄包目录 **22/22**；
4. **重发 FTP** `publish_ftp.py` 持锁 `app-ftppub` ⇒ **10.0 s / 1071.0 MB/s**、源⇄副本 SHA256 **一致** ⇒ ✅ **三方闭环**（源 zip = FTP 副本 = 包目录）。
**交付物最终指纹**：**11 216 287 107 B** / SHA256 **`c7f60bcacda7e4d04d0cdd6776f34a91b928d30ad4fb6d5b1f64906da3a667e4`** / zip **13986** 条目 / mtime 10:28（FTP 副本 10:34）。
✅ **zip 内已含 APP-023 的 5 个修复**（SHA256 与包目录/仓库逐字相同：`tts_cuda.py` `b5be4ce571abcc67` / `tts_service.py` `77c20a52f5767391` / `tts_worker.py` `77f189f7b1e3164b` / `live_caption_app.py` `b9e21d398ea42bc3` / `offline_reader_gui.py` `a3df2d46f9512b73`）。
✅ **APP-018② 第三方素材在 zip 内真正清零**（**散包目录**仍有 8 + 22，但**交付 zip** 内实测 **0 + 0** ⇒ 规则生效）：`babelvox/data/speakers` **0**、`scipy/**/tests/*.wav` **0**、`voices/` 只剩 `preset_A.wav` **1** 个。
🔴 **FTP 服务仍关闭**（netstat 实测 21/2121 无监听，守 APP-009③）；v1.4 保留。

### §64.6 🔴 回归结果（全绿，1 项失败已定位为**环境缺失**而非回归）
- `app097`（新增）REAL **20/20** + BUG **3/3**；
- `app092` **24/24**、`app096` **13/13**、`app093` **19/19** ⇒ **全绿**；
- TTS 记账 5 套件 `app057`/`app086`/`app088`/`app089`/`app090` ⇒ **全部「REAL 全过」**；
- `test_tts_*` **19 个 PASS**；
- ⚠️ **1 个失败：`test_tts_cmp_orig.py`** ⇒ `FileNotFoundError: results/app/_orig_mod/tts_service_orig.py`。**已定位为环境缺失、不是本轮回归**：`git ls-files` / `git log` 对 `_orig_mod/` **均无记录** ⇒ 它是 §21 时期的**临时备份目录**（**从未被 git 跟踪**）⇒ 早被清理 ⇒ 该套件**长期**无法运行。⇒ 🔴 **再次印证 §62 的教训**：「反证基线不能用临时备份目录」⇒ 本轮 `app097` 的基线用的是**固定 commit SHA `0d1be9d`**（`git show`）⇒ **不会**随清理失效。

### §64.7 ⛔ **本轮停在 §63 的 L4**（等用户实测）—— 不自行推进
APP-023 的 **L4** 原文：「通知用户从桌面快捷方式按 L1→L2→L3 再测一遍，并说明听到/听不到（会话日志由 reviewer 核对）。**用户亲口确认之前，仍不得写「能出声」**」。
🔴 **本轮只做链路级与代码级闭环**（L1/L2/L3 自动化冒烟已在 `§63` 全绿 + 本轮交付 zip 已含修复），**未**宣称「用户听得见」。
**请用户现在双击桌面「Confucius4 实时字幕」图标**（已指向 v1.5 包 `Start_LiveCaption.bat`）：① 点「🔊 测试声音」→ ② 选 **CUDA** 朗读一句 → ③ 选 **NPU** 朗读一句 → ④ 反馈听到/听不到 + `%LOCALAPPDATA%\Confucius4LiveCaption\session_*.log` 路径。

### §64.8 🔴 **未推进**（等 reviewer 裁定 / 等用户）
- 🔴 **APP-024②**（加载期提交的句子单独列）—— 本轮只做了 ①，② 需与实测一起做（APP-024 明文「APP-023 验收通过后再做这条」）；
- 🔴 **APP-024③**（按 BRIEF 规定素材 SPE 12–27 分钟 + 中英混合音频、`--speed 1`、**持锁**重跑 ABBA）—— 等 L4 用户确认 + 机器锁；
- 🔴 **APP-024④**（「加载期攒下的句子在 ready 那一刻也按 8 s 规则丢掉」是否改）—— reviewer 明文「**不要自己改**，写进待用户决定」；
- 🔴 **APP-022** 集成（等 ASR-013 + TTS-019）；🔴 **§45.6①–⑤** / **§44 `MAX_SEG_SPAN=2`** / **§46.5** / **§42.3** / **MT 通知 13 回复** ⇒ 均等裁定。

### §64.9 ⚠️ 本轮纪律自检
✅ 未在 CPU 跑推理/测速（CUDA/NPU 是加速器）｜✅ 未调 MiniMax｜✅ 未改 `CORRECTIONS_APP.md`｜✅ 未吞其它模块改动（提交前 `git status` 实测 **474** 项，他模块全部保留在工作区）｜✅ 打包/发布**全程持共享机器锁**（`app-pack` PID 32772 / `app-ftppub`），锁**已释放**｜✅ 仓库⇄客户包只做**定点替换**（禁整目录覆盖）｜✅ 提交**逐文件 `git add`**（不用 `-A`），**不提交** `status/app/CORRECTIONS_APP.md`｜✅ **普通 push**，未 force。
⚠️ 本轮 `app095`/`app097` 的耗时数字**一律标 `timing_valid=false`** ⇒ **不对外报**。
