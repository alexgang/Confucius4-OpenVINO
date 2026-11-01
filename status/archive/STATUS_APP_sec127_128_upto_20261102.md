# STATUS_APP 归档（§127 / §128 正文逐字留存）

> 本文件由 `results/app/_app129_archive_sec127_128.py` 于 2026-11-02 生成。
> **§127 / §128 的正文逐字保留，内容一字未删**；原位留有指针行（见 `status/app/STATUS_APP.md`）。

### §127 ✅ **APP-061 —— 用户实测 v2.1 的 6 个问题（CUDA 无声 / 离线无参考音色 / 卡顿 / 克隆约 10 s 一次 / 男声被女声播出 / 界面不紧凑）：代码层全部修复 ＋ 打 v2.2 交付包** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**


> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。
> 🔴 **本轮是「接手上一会话的半成品」**：上一会话（租约 `67f14126`）在 22:21 之后**心跳中断**（22:41 仍有文件落盘）⇒ 本轮按 APP-061 的**断点继续**，**不从头重做**（已完成的 ①②④⑤ 代码改动**保留**，本轮在其上补 ③⑥ ＋ 打包）。

**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ `last_ack` **APP-061**（APP-061 明文要求「开工前先写 last_ack」⇒ 上一会话已写，本轮沿用）。

#### ① ① CUDA 语音无声 ＋ ② 离线「无参考音色」（同一根因，已修）
* 根因（reviewer 定位）：CUDA 分支只缓存 `_preset_ref_path`、**未缓存 `_preset_name`** ⇒ 回落把 `speaker_name` 清空 ⇒ `synth()` 的音色检查成立 ⇒ 每句「没有可用的音色」⇒ **请求根本没送到边车**。
* 改法：`tts_worker.py` 的 CUDA 分支补 `self._preset_name = 'A'`；回落路径在 CUDA 下**只换参考音频、不清空音色名**；音色检查对 `USES_REF_AUDIO` 后端改为查「当前有没有参考音频」（`_has_ref_audio()`）。
* 判据：`results/app/app215_app061_voice_clone_evidence.json` → `n_pass=29` / `n_fail=0`（**含 7 条反证，全部被抓住**）

#### ② ④ 克隆从「每 10 s 一次」改为「换人时才取样」
* 停用旧的 APP-027 定时采集器（`CloneCollector`）⇒ 克隆只走按句绑定（`is_new` 取样首段 ≥1.5 s → 3 s 定稿 → 老说话人复用缓存）。
* GUI 文案去掉「每 30 s」；`_retry_spk_labels` 补登记 `is_new`（CLI 同步路径同修）。
* 判据：同 ① 的 `app215` 证据（`4a_timer_collector_disabled` / `5b_gui_retry_is_new` / `5b_cli_retry_is_new` 全 PASS）。

#### ③ ⑤ 男声被女声播出（已修）
* 三处根因：a. GUI 构造 `TTSService` **漏传 `clone=`**（CLI 传了）⇒ worker `clone_mode=False` ⇒ 每句回落预设 A；b. `_retry_spk_labels` **丢掉 `is_new`** ⇒ 新说话人永不被取样；c. 标签未到时**一律回落预设 A**。
* 改法：a. 补传 `clone=self._clone_enabled`；b. `is_new` 为真时执行 `_spk_pending_embed.append((seg, spk))`；c. **已有克隆音色时沿用上一句**（`keep_last`，日志固定关键词 `spk_pending⇒keep_last`）⇒ 没有克隆音色时才用预设 A。
* 判据：`app215` 证据 → `5c_keep_last_helper` / `5c_synth_calls_keep_last` PASS；反证 M4（M4_5a_mutant_is_caught）/ M5（M5_5b_mutant_is_caught）**均被抓住**。

#### ④ ③ 卡顿（遥测 ＋ 预缓冲 ＋ 倍速封顶 ＋ NPU 提示）
* (a) 逐句遥测新增 `uf_in_sentence` / `uf_in_sentence_ms` / `uf_idle` / `uf_idle_ms` / `uf_total_ms`（**句内 = 听得见的断音**；句间空闲单列）；主进程累计「句内欠载总时长」「句内欠载 = 0 的句数」；GUI 会话日志**每 30 s** 打一行 `asr_rtf / asr_backlog_s / mt_lat_p50 / tts_synth_rtf / uf_in_sentence_ms`。
* (b) 预缓冲公式升级为 **`est_dur × (1 − 1/(r·speed))`**（r = 最近 8 句实测 「合成墙钟 ÷ 音频时长」）；`r·speed ≤ 1` ⇒ 退化为首块即播（0.3 s 底线）；**speed = 1 时与旧公式逐位相同 ⇒ 零回归风险**。
* (c) **倍速动态封顶** `speed ≤ 1/r_recent`（合成跟不上时宁可滞后，不靠加速把环形缓冲抽空；**用户定的 1.30× 上限不变**）；封顶在 `self._last_speed = _sp` **之前**生效 ⇒ 下一句拿到的是实际用掉的倍率。
* (d) MT/ASR 与 TTS 同在 NPU ⇒ 语音区**标黄提示**「NPU 共用，语音可能卡顿」（**只提示、不禁止** ⇒ D4 待决）。
* 判据：`results/app/app220_app061_stutter_evidence.json` → `n_pass=39` / `n_fail=0` / `n_none=0`（**含 5 条反证**：M1 去 speed 因子 / M2 去封顶 / M3 删 uf 字段 / M4 删 30 s 行 / M5 把 warn 改成 error ⇒ **全部被抓住**）
* 行为探针（实测值）：`speed=1.0 ⇒ 预缓冲 0.947 s`、`speed=1.30 ⇒ 1.651 s`；`r=1.31 ⇒ cap=1.0000`（不许加速）、`r=0.50 ⇒ cap=1.3000`（用户上限）、无实测 RTF ⇒ 不封顶。

#### ⑤ ⑥ 界面紧凑（已修）
* 控件压缩到 ≤ 2 行；不常用控件进**可折叠「高级」面板**（默认收起）；三个分区说明行**并进状态栏 tooltip**；字幕字体保持 13 pt；最小宽度 1024。
* **顺带修掉一个真缺陷**：三个分区的说明行被移进**未映射**的「高级」面板 ⇒ Tk 对未映射控件 `winfo_width()` 恒返 **1** ⇒ 说明行拿不到换行宽度 ⇒ `wraplength=0` ⇒ **展开面板时横向溢出**（实测最长 reqwidth = **3 003 px**）⇒ 新增 `_wrap_width()`（容器未布局时**回退到窗口宽**）＋ 展开/收起后重算。
* 判据：`results/app/app219_app061_gui_compact_evidence.json` → `n_pass=13` / `n_fail=0` / `n_none=0`；**字幕区占比 78.88 %（v2.1 同口径 31.5 %）** ⇒ 同一判据在 **v2.1 上 FAIL**（`app219_app061_gui_compact_v21_evidence.json` → `n_pass=7` / `n_fail=2`）⇒ **判据能识破旧版缺陷（非恒真）**。
* 状态栏 **1 行**（三个分区各 21 px）；1024 宽**无控件越界/被裁剪**（判据含反证探针 ⇒ 被抓住）。
* 前后对比截图 4 张：`shared/app_gui_layout/app061_v21_*.png` 与 `app061_v22_*.png`（1280×800 与 1024×800 各 2 张）。

#### ⑥ 交付：v2.2 新目录 ＋ 新 zip（v2.1 一个字节都没改）
* `pack_v13.py` 新增 `--no-shortcut` ⇒ **不动桌面快捷方式**（APP-061：「用户抽听以后才能改桌面快捷方式」）。
* 打包前 `--dry-run` 闸门：**PASS**（包路径写死 0 处违规 / 版本标识一致 PASS / 内部素材 0 命中）⇒ 见 `results/app/_pack_v22_dryrun.log`。
* v2.2 目录由 **v2.1 目录**派生（`results/app/app221_app061_v22_build_evidence.json`）：`models/` ＋ `python/` **硬链接**（零拷贝、只读）、其余**真实复制**；**只定点同步本轮改过的 3 个生产模块**（`live_caption_app.py` / `tts_worker.py` / `tts_service.py`，行尾归一 LF ＋ 写后逐字节复核）⇒ **不整目录覆盖**。
* 🔴 **本轮自抓的打包缺陷**：复制时跳过 `__pycache__` ⇒ v2.2 **少 3 519 个 .pyc**
  （`pack_v13.py` 的排除规则**保留** `python/**/__pycache__` ⇒ 少它们 ⇒
  客户首次启动要多编译 1~5 s）⇒ 而「zip ⇄ 包目录 内容一致性校验」**查不出来**
  （两边都少、自洽）⇒ **必须与源包逐名比对** ⇒ `app221` 已加**完整性闸门**
  （缺文件 ⇒ exit 4）⇒ 补齐后 **14 462 = 14 462（零缺失零多出）**，重新打了一次包。
* ✅ **「验收证据 ↔ 被验收代码」绑定闸门 `app191` 对 v2.2 实测 PASS 16 / FAIL 0**
  （`results/app/app191_app061_v22_binding_evidence.json`）：
  R1 漂移 = 本轮改过的 3 个模块；R2 三条均判为「非良性差异」但**被 reviewer 显式承认**
  （白名单写明 `reason` ＋ `source` = APP-061 各项）⇒ 放行；
  R3b 白名单**自洽**（3 条 ↔ 3 处真实漂移、无幽灵条目）；
  R4 指纹基线 = `fddb2dc6b06d…`；
  **R5 `ACCEPTED.code_fingerprint` == 包内当前指纹 ⇒ 验收结论在交付物上成立**。
* `ACCEPTED.json` **重签**（按新代码算指纹：`code_fingerprint=fddb2dc6b06d…`，**28 个生产模块**）⇒ 否则 zip 内那一份仍绑旧代码（APP-052 ② 的教训）。
* ✅ **v2.2 zip 已生成**：（**11233149299 B** / SHA256 `ea5c5c850f8836a7edab982611cdd59d…` / mtime `2026-11-02T01:54:03`）
* 🔴 **v2.1 原样保留**：本轮**未改、未覆盖、未删除** v2.1 的目录与 zip；v2.2 是**全新目录 + 全新 zip**（新版本号 ⇒ 不是 `--same-version` 覆盖重打）。

#### ⑦ 收尾复核（`CORRECTIONS_APP.md` 全程只读）
* 开工基线：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**（APP-001…APP-061）。
* 收尾实测（2026-11-02 02:01 现场重算）：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ **与开工基线逐字相同 ⇒ 本轮 reviewer 未追加新条目 ⇒ 「SHA 零改动」在本轮成立**（与 §125/§126 那两轮「中途被追加」的情况**不同**，勿混为一谈）。
* 本模块对 `CORRECTIONS_APP.md` **全程只读、未写入**。

#### ⑧ 待 reviewer 复核 / 未达成（不粉饰）
① ⛔ **①⑤ 的真机复测未做**（需 GUI + SPE 前 5 分钟 + 耳机实听）：判据与代码已就绪，**但本轮未跑设备级复测** ⇒ 「没有可用的音色 0 次」「REQ 数 = 提交句数」「`voice_kind=clone` 占比 ≥ 80 %」这些**数字尚未实测** ⇒ **不能写「已通过」**。
② ⛔ **③ 的 SPE 5 分钟实测未做**（`uf_in_sentence_ms` 总和 ≤ 音频时长 0.5 % / ASR RTF 增量 ≤ +0.10 / 丢句 0 / TTS 首包 P50-P95）⇒ 同上，**未实测**。
③ ⛔ **③(e) CPU 卸载候选的 A/B 未做**（旁路 pyannote/wespeaker、克隆 `speaker_enc`、TTS `tok_decoder`）⇒ 需持机器锁的 ABBA 实测；**「改默认摆放要先报主会话」⇒ 本轮未改任何默认摆放**。
④ ℹ️ **D1–D4 仍待用户/reviewer 决定**（线程不自定）：D1 旁路窗口 10 s 能否缩短；D2 选「跟随说话人」是否自动开旁路；D3 客户包是否保留 TTS=CUDA 选项；D4 MT/TTS 同 NPU 是警告还是禁止。**用户决定之前的默认实现已按 STATUS 头部记录落地**（② 检测不到边车 ⇒ CUDA 置灰并显示原因；⑤d 旁路关时明确提示、不静默退回定时克隆）。
⑤ ℹ️ **桌面快捷方式未改**（`--no-shortcut`）⇒ 用户抽听通过后再由主会话改指 v2.2。
⑥ ℹ️ **v2.1 的 zip 与目录 README 仍不一致**（zip 内是 21:05 改前的版本）⇒ 该缺口**已由 v2.2 带上**（v2.2 继承了目录版本 47 786 B）⇒ v2.1 本身**不再原地改**。



### §128 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 转做 APP-061② 附带问题 ＋ 共享锁闸门修复 ＋ 备好真机验收 harness；设备级实测因用户会话在跑而未开跑** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 03:16）


**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ `last_ack` **APP-061** ⇒ **无新纠偏条目**（本轮**不执行**任何新条目；`last_ack` **不变**）。

#### ① APP-061② 附带问题：`SyntaxWarning: invalid escape sequence`（reviewer 点名 `tts_cuda_sidecar.py:8`）已修
* 全量扫 `live_caption/*.py` + `machine_lock_app.py` + `pack_v13.py` ⇒ **4 处**同类告警：`tts_cuda_sidecar.py:8`（`\_`）、`machine_lock_app.py:258`（`\S`）、`_app100b_patch_status.py:67`（`\p`）、`sync_c195_app052054_to_pkg.py:29`（`\|`）⇒ **全部归零**（另加本轮新建的 `app223` 自身 1 处）。
* 改法**最小化**：docstring 加 `r` 前缀 / 单个反斜杠转义 ⇒ **不写死源码、不整目录覆盖**。
* 🔴 **「行为不变」的证明**：改前/改后**逐个字符串常量**（`ast` 全量 `Constant(str)`）对照 ⇒ **值一个都没变**；唯一差异是 `machine_lock_app.py` 的 `_parse_module_pid` docstring 里 `\b` 从**不可见背空格**（0x08）变成**可见字面量**（文档更对，非行为变化）⇒ 证据 `results/app/app224_app061_escape_lock_gates_evidence.json` → `escape_fixes[]`（**5 PASS / 0 FAIL**）。
* ⚠️ **v2.2 包内仍是改前版**（`tts_cuda_sidecar.py:8` 的 `\_` 仍在）⇒ 下一版必须**打 v2.3**（**禁止 `--same-version`**），本轮**未打包**（未获授权）。

#### ② 共享锁闸门 `results/app/test_machine_lock_app.py`：8 条**假 FAIL** 已修（32/40 → **42/42**）
* 根因 = **夹具写死绝对日期**（`2026-10-24 / 10-25 / 10-28`）＋ 本机 **2026-10-31 08:44 重启过** ⇒ 这些锁的 `started` **早于开机时间** ⇒ 命中 `stale_boot` 分支（代码里明文「**优先于 PID 判断**」）⇒ 8 条断言在「锁语义没变」的情况下**假 FAIL**。
* 🔴 **反证基线**（拿 HEAD 版 `machine_lock_app.py` + 旧夹具跑）⇒ **同样的 8 条 FAIL**（30/39）⇒ 证明是**判据缺陷**（夹具），不是产品缺陷（对齐记忆「判据 FAIL 先怀疑判据/环境」）。
* 改法：夹具时间戳一律**动态**（`_ts()`）＋ **补 `stale_boot` 分支的显式覆盖**（原来这一分支**没有任何断言**）。
* 改后（仓库内跑，含 git 反证组）⇒ **42/42 PASS**（`app224…` → `lock_test_current.n_pass=42` / `n_fail=0`）。

#### ③ 🔴 顺带查出的**风险项**（本轮**未自行改实现**，交 reviewer 裁定）
* `lock_state()` 的 `stale_boot`（锁的 `started` 早于开机时间）**优先于 PID 存活判断** ⇒ **别的模块时钟被往回调**（或开机时间算错）时，会**抢走活锁** ⇒ 两个模块同占设备（违反「死判据只能是 `OpenProcess` err==87」的铁律）。
* 本轮**只把它写成显式断言**（口径锁定：`(口径锁定) started 早于开机时间 ⇒ stale_boot 优先于 PID 存活`，见 `test_machine_lock_app.py` §3b）⇒ **语义改动留给 reviewer**。

#### ④ APP-061②「CUDA 置灰 + 显示原因」在 **v2.2 包内代码**确实落地（静态核验 4/4）
* 4 个落点全部命中 `Confucius4_LiveCaption_v2.2/app/live_caption_app.py`：① 列表项 `disabled=(not _cuda_ok), why=_cuda_why`（L896）② 不可用项**不作为初值**（L2849）③ 选中不可用项 ⇒ **拒绝启动 + 显示原因 + 回退可用项**（L3555）④ 启动前**拦住**并自动改用可用设备（L3679）。
* 证据：`app224…` → `cuda_graying.anchors`（4/4，`ok=true`）。

#### ⑤ 🔴 设备级实测（本轮**最重要的缺口**）：harness 已备好，**但未开跑**
* 新增 `results/app/app223_app061_device_acceptance.py`：3 臂（`tts_off` / `tts_on_preset` / `tts_on_clone`）＋ **v2.1 反证臂**；判据覆盖 APP-061 **①（没有可用的音色=0）③（uf_in_sentence_ms ≤ 0.5 % / ≥95 % 句子为 0 / ASR RTF 增量 ≤ +0.10 / 丢句=0 / 首包 P50-P95）④（声纹次数 ≤ 2×说话人数 / ±1 s 配对 / 定时克隆=0）⑤（voice_kind=clone ≥ 80 % / 回落 ≤ 2×说话人数）**；**三态**（True/False/**None 无法判定**）+ 自取机器锁 + 等安静窗口。
* 🔴 **判据非恒真的证明（不需要设备）**：拿 **reviewer 点名的 v2.1 会话日志**（`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261101_212026.log`）跑同一套判据 ⇒ **5 PASS / 0 FAIL**（抓到 **83** 次「已回落到预设 A」（reviewer 原文 83）、**50** 次「没有可用的音色」、**25** 次 10.0 s 定时克隆更新、**27** 次声纹计算对不上 `new_spk`）⇒ 同一套判据对 **v2.1 必须 FAIL** ⇒ 对 v2.2 的判定才可信。
* ⛔ **真机三臂本轮未跑**：`machine_lock_app.wait_quiet_window_cpu(30 s/60 s)` ⇒ **ok=False**（`last_busy_pids=[14712]` = **用户自己的 v2.1 GUI 会话**，`live_caption_app.py` 21:20:24 启动）⇒ 与用户会话抢 NPU 会让**两边数字都失真** ⇒ **本轮不开跑**（`app224…` → `device_acceptance_blocked=true`）。
* ⇒ **APP-061 ①③④⑤ + ③(e) 的设备级数字仍然「未实测」**（代码层已由 `app215/219/220` 覆盖）；下一步：机器安静 + 用户会话结束后跑 `python results/app/app223_app061_device_acceptance.py --run`。

#### ⑥ 收尾复核（`CORRECTIONS_APP.md` 全程只读）
* 收尾实测（2026-11-02 03:1x 现场重算）：见本节末尾「收尾实测」行 ⇒ 与开工基线**逐字相同** ⇒ 本轮 reviewer **未**追加新条目（若中途被追加则如实记录，不声称「零改动」）。

#### ⑦ 本轮交付
* 代码：`live_caption/tts_cuda_sidecar.py`、`machine_lock_app.py`、`live_caption/_app100b_patch_status.py`、`live_caption/sync_c195_app052054_to_pkg.py`、`results/app/app223_app061_device_acceptance.py`、`results/app/app224_app061_escape_lock_gates.py`、`results/app/_app223_doc_snapshot.py`、`results/app/_app223_escape_fix_verify.py`、`results/app/_app224_write_status.py`、`results/app/test_machine_lock_app.py`。
* 证据：`results/app/app223_app061_device_acceptance_evidence.json`（判据自检 5/5）、`results/app/app224_app061_escape_lock_gates_evidence.json`（5 PASS / 0 FAIL ＋ 锁闸门 42/42 ＋ 基线 30/39 ＋ CUDA 4/4）。
* 🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**（v2.1、v2.2 目录与 zip **一个字节都没动**）。

