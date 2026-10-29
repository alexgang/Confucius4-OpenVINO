## §95 🔴 APP-041 + APP-042 两条新纠偏已实施（代码侧全部完成）＋ 客户包 **v1.8 已重打 ⇒「已交付」成立** ⇒ ⛔ APP-042 的 SPE 5 分钟真机实测仍未做（ASR 持锁）｜**本条已完成**｜**本条需等 reviewer 复核**（2026-10-29 20:49）

> ⚠️ 本节是**并发会话**（17:0x–17:3x 实现 + 17:37 打包）与本轮（20:4x 独立复核 + 补写 STATUS）的**合并记录**。
> 凡结论一律指向**结果文件与其中的原始字段**；未落盘的东西**不写「已交付」**。

### 95.1 巡检（纠偏文件**只读、零改动**）

| 项 | 值 |
|---|---|
| `status/app/CORRECTIONS_APP.md` | 108 783 B / mtime `2026-10-29 15:30:53` / SHA256 `c50dcdd1ad02b45f…` |
| `## APP-xxx` 条数 | **42**（APP-001 … APP-042） |
| 开工时 `last_ack` | `APP-040` ⇒ 新条目 **APP-041 [HIGH]**（14:58）、**APP-042 [HIGH]**（15:30） |

本文件对本轮结论**只追加**；旧章节逐字未改（写后按 §95.8 校验）。

### 95.2 APP-041 —— reviewer 的推测**成立（第一种）**，且**已在产品代码里修掉**

| # | reviewer 推测 | 代码证据 | 结论 |
|---|---|---|---|
| ① | 「GUI 只把开关变量初值设成 True，初始化只挂在 `command=` 回调上，启动时没调用」 | 修前 `var_tts_on = tk.BooleanVar(value=True)`，而 `_on_tts_toggled()` **只挂在 Checkbutton 的 `command=`**（`live_caption_app.py` L2269）；修前全文件调用点只有「换设备重启 / 切换项重起 / 离线朗读兜底」，**无一处属启动流程** | ✅ **成立** |
| ② | 「调了但早于输出设备列表加载」 | 启动流程里**根本没调** ⇒ 不成立 | ❌ **不成立** |

**修法（APP-041①~④ 逐条）**：
- ① **同一入口**：新增 `_arm_startup_tts()`（登记待办）+ `_maybe_startup_tts()`（真正初始化）⇒ **调用的是同一个 `_on_tts_toggled()`**（不另写一套）⇒ 手动勾选与启动自动**行为逐字一致**；顺序 = **ASR 就绪（`_engine_ready`）→ MT 不再 `loading`**（沿用既有「依次加载、`auto=False` 防 GPU 编译死锁」顺序）⇒ 在 `_poll()` 里触发。
- ② **失败自动回关**：`_on_tts_toggled()` 的异常分支与「无任何可用设备」分支都 `var_tts_on.set(False)` + 状态栏写明原因并指向日志 ⇒ **绝不显示「开启」却不工作**（代码：`live_caption_app.py` L2862「🔴 语音输出启动失败：…（已自动关闭…）」、L3326「🔴 启动失败：{e}（已自动关闭，详见日志）」）。
- ③ **输出设备/音色选项启动即生效**：`_on_tts_toggled()` 本来就读 GUI 的实时选择（`var_tts_out` / `var_tts_voice`）⇒ 走同一入口即自动满足。
- ④ **其它默认开启项自查**：`var_show_spk`（§94 改的默认 True）是**纯显示开关、无 `command=` 副作用** ⇒ 无同类问题；`var_overlay`（`live_caption_app.py` L2081，默认 True）在启动流程里**已显式调用**同名回调（L3801/L3807）⇒ 无同类问题。**唯一同类缺陷就是 TTS 这一个。**

### 95.3 APP-042 —— 自适应加速播放：**主链已接通**（主进程 → service → worker → 流式播放）

| 环节 | 实现 | 文件 |
|---|---|---|
| 统一参数 | `speed_for_lag(lag, prev)`：`clamp(1.0+(lag−3)×0.025, 1.0, 1.30)`（`SPEED_PER_LAG_S=0.025` / `SPEED_MIN=1.0` / `SPEED_MAX=1.30`）；**滞回**（降速需 `lag<2 s`）；**相邻句变化 ≤ 0.1×**（`MAX_STEP_CHANGE=0.1`） | `live_caption/time_stretch.py`（**新增**，19 765 B） |
| 保音高变速 | **WSOLA**（归一化互相关搜索 + Hann 窗 OLA）⇒ **不用改采样率 / playbackRate**（改采样率的对照组实测 **f0 200→250 Hz = 变调 25%**，判据有分辨力） | 同上（`time_stretch()` + `StreamWSOLA` 流式版） |
| 依赖纪律 | **只用 numpy**（`imports=['__future__','math','numpy','wave']`，`extra=[]`）⇒ **客户包零新增依赖** | 同上 |
| 目标开播时刻 | `_seg_target_wall[seg] = _target_play_wall()`（`t0 + 已消费源音频秒数`）⇒ **无会话时返回 `None` ⇒ 不下发加速参数 ⇒ 旧行为逐字不变** | `live_caption_app.py` L3669/L3672 |
| 倍率计算 | `submit(..., target_play_at=)` ⇒ `lag` ⇒ `speed_for_lag` ⇒ 写进命令体 `cmd['speed']` / `cmd['target_wall']` / `cmd['lag_s']` | `tts_service.py` |
| 下发 | worker 主循环 `msg.get("speed")` ⇒ clamp `[1.0, 1.30]` ⇒ 传 `self.synth(..., speed, target_wall)` | `tts_worker.py` |
| 变速播放 | **流式** `StreamWSOLA.process(w)` + `flush()` 收尾块 ⇒ **首块即可出声**（不等整句合成完，否则首包 +4~8 s，与「追赶滞后」背道而驰） | `tts_worker.py` L1714 |
| 遥测回报 | `speed` / `in_dur_s` / `out_dur_s` / `speed_gain` / `target_wall` / `play_lag_s` | `tts_worker.py` |
| 闭环 | 主进程 `played` 事件回收倍率与实际播放滞后 ⇒ `cur_speed` / `play_lag_s` / `peak_play_lag_s` / `n_speed_adjusted` / `speed_time_s` | `tts_service.py` |
| GUI 底栏 | 显示「**语速 1.15×**」「**播放滞后 12.3 s**」 | `live_caption_app.py` L3534-3535 |

🔴 **跨进程时钟口径**：lag 的「目标」在主进程（「实际开播 − 目标开播」的墙钟口径，APP-042 明文）、「实际开播」在 worker ⇒ `time.perf_counter()` **基准不同不可比** ⇒ 统一改用**墙钟 `time.time()`**（同一台机器系统时钟 ⇒ 跨进程可比）。

### 95.4 验收（**零推理 / 零 GPU / 零 NPU / 未调 MiniMax / 未开 FTP / 未发 FTP**）

| 套件 | 覆盖 | 结果 | 证据（bytes / SHA256 前 16 / mtime） |
|---|---|---|---|
| `app139_app041_startup_tts.py` | APP-041 静态结构 + 行为 9 项 + **基线反证** + **反证（判据不恒真）** | **21/21 PASS** | 3 544 B / `ec1911a17fb7c9c9` / 17:17:30 |
| `app140_app042_wsola.py` | WSOLA 保音高 + `speed=1.0` 恒等 + 统一参数公式 + 依赖纪律 + **变调反证** | **22/22 PASS** | 3 531 B / `c0d376af890a54ff` / 17:19:40 |
| `app141_app042_end_to_end.py` | **APP-042 主链集成**（补 app140 只测模块的缺口）：静态链路 12 项 + 行为 + **反证** | **24/24 PASS** | 4 336 B / `c599608b0a3108a5` / 17:19:14 |
| `app141_app042_integration.py` | 8 组：静态结构 / B1 速度公式 / B2 流式 WSOLA / B3-B4 命令体 / B5 worker 变速 / B6-B9 遥测显示 / **反证（注入）** / **反证（基线 commit）** | **62 PASS / 0 FAIL** | 9 218 B / `3080dc0902d0a56a` / 17:19:41 |
| `app142_app042_pkg_check.py` | **客户包内**复跑：包内 4 文件与仓库逐字一致 + 包内 WSOLA 音高 + APP-041/042 静态链路 + 反证 | **22/22 PASS** | 4 215 B / `0f574f13e8cfc872` / 17:19:41 |

- 🔴 **本轮自查抓出「判据自身的 3 处缺陷」（产品没暴露缺陷）**：
  ① **判据环境缺 `time_stretch` 可 import 模块** ⇒ 真实代码 `import time_stretch as _ts` 失败 ⇒ 走进 `except` ⇒ **静默不加速** ⇒ 表现为「speed 永远算不出来」⇒ **看起来像产品缺陷** ⇒ 修法：把 `exec` 出来的模块塞进 `sys.modules`。
  ② **B4 期望值写错**：原期望「lag=60 s ⇒ speed=1.30」⇒ 但 APP-042 的**两条**约束同时生效（`clamp` 上限 **且** 相邻句变化 ≤ 0.1×）⇒ **第一句**从 `prev=1.0` 出发最多到 **1.10** ⇒ **判据错、产品对** ⇒ 改成「连续 6 句 ⇒ 逐句 +0.1 收敛到 1.30 且不超」（实测 `speeds=[1.1, 1.2, 1.3, 1.3, 1.3, 1.3]`）。
  ③ **反证删代码只删了半行** ⇒ `PATTERN NOT FOUND` ⇒ 反证无效 ⇒ 改用**带上下文的整块正则**替换。
- 🔴 **反证基线用固定 commit `f724769`**（不是 `HEAD`）⇒ 同一套场景对**修前源码**复现缺陷（修前 188 939 字符，**确实没有**启动初始化机制）。
- 🔴 **`app142` 证据里的 `pkg` 字段仍写 `…_v1.7`**（脚本写死的版本名）⇒ 实际包目录在打包时**同卷改名为 v1.8** ⇒ 本轮已用**独立三方复核**替代（见 §95.5）⇒ ✅ **该字段不作为交付依据**。

### 95.5 🔴🔴 交付侧**独立复核**（本轮亲自跑，未依赖他人结论）

| 判据 | 结果 |
|---|---|
| 客户包目录 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.8`（`Confucius4_LiveCaption_v1.7` 目录已不存在 ⇒ 打包时同卷改名，符合 §94 的「版本号自动递增」） |
| zip | `Confucius4_LiveCaption_v1.8.zip` / **11 218 155 024 B** / mtime `2026-10-29 17:37:13` / SHA256 `0e3b4d263c0cbb967705c8e8c91b7bfa078309e2f6da3f6238296b459188757c` |
| zip 结构 | **14 201** 条目 / **14 201** 文件（无目录项）/ **EOCD 签名在**（尾 64 KB 内 `PK\x05\x06` 偏移 65 514） |
| MANIFEST | `version='1.8'` / `files=14200` |
| **zip ⇄ 包目录** | 全量 `.py` **6 590** 个文件**逐字节 SHA256 一致，0 差异**（含 `app/` 下 24 个） |
| **仓库 ⇄ 包目录**（`app/*.py`） | 交付相关的 **4 个改动文件逐字一致**：`live_caption_app.py` `c123cdfbf70b2685…` / `tts_service.py` `b55bf25a6fe6f2c0…` / `tts_worker.py` `83d500c6a94fdae2…` / `time_stretch.py` `f1f7f5e1c18c3e1e…`（**归一化换行后**；与仓库同名文件逐字节相同） |
| 定点同步 | `live_caption/sync_c157_to_pkg.py`（13 749 B / `df1f4133ba205483` / 17:14:35）⇒ **未做整目录覆盖** |

🔴 **「仓库里那 166 个 `diag_*` / `sync_*` 未进包」不是缺陷** —— 它们是仓库里的**开发期诊断与同步脚本**，**从来就不属于客户包** ⇒ 本轮比对时按「仓库 ⇄ 包目录」单向核对时它们显示 `PKG MISS`，**已确认属预期**（`pkg_exclude.py` 的排除清单），**不是**「包里少了东西」。

### 95.6 ⛔ **本条未做完的部分（明确不写「已交付」）**

- 🔴 **APP-042 的真机验收未做**：reviewer 明文「**SPE 前 5 分钟，默认设备摆放，持锁。报告滞后随时间的曲线（起点、峰值、结尾）和各倍率的时间占比，丢句 = 0；挑 3 段 1.2–1.3× 的配音落盘，供用户抽听，确认不变调、可懂**」⇒ **本轮未跑**。
  - **原因（事实）**：20:44 起 `shared/MACHINE_LOCK` 被 **ASR** 持有（`asr PID 23644 started 2026-10-29 20:44:47 task=asr027-cpu-rerun-base`）⇒ **守纪律不抢锁**（`fail-closed`，别人活只能等不能杀）。
  - ⇒ 该项**仍是 ⛔ 未完成**，**下一轮持锁时优先补做**。
- 🔴 **APP-041 的真机验收未做**：reviewer 明文「**验收必须走用户的启动方式：桌面快捷方式 → `pythonw.exe`，冷启动后什么都不点，直接播放测试音和朗读一句，能出声；状态栏显示 TTS 就绪；日志里能看到启动时调用了初始化函数，而且只调用一次**」⇒ 本轮**未跑**（属真实用户会话 + 持锁）。
- 🔴 **APP-041 的「所选输出设备不存在 ⇒ 开关自动回关闭并提示原因」** ⇒ 只在**零推理单元级**验证（`app139` B4/B6：开关回 `False` + 状态栏写明原因），**未做真机复现**。

### 95.7 本轮产物指纹表

| 文件 | 字节 | SHA256（前 16） | mtime |
|---|---|---|---|
| `live_caption/time_stretch.py` | 19 765 | `f1f7f5e1c18c3e1e` | 16:56:00 |
| `live_caption/sync_c157_to_pkg.py` | 13 749 | `df1f4133ba205483` | 17:14:35 |
| `live_caption/live_caption_app.py` | 268 629 | `b1759e6a532dab3f` | 17:13:36 |
| `live_caption/tts_service.py` | 123 345 | `dc9c9bd79172b1a5` | 17:13:36 |
| `live_caption/tts_worker.py` | 200 007 | `ba6a2b0ad0bc3d1a` | 17:13:36 |
| `results/app/app139_app041_startup_tts.py` | 27 812 | `b6e239859a2bbd73` | 17:12:44 |
| `results/app/app139_app041_startup_tts_evidence.json` | 3 544 | `ec1911a17fb7c9c9` | 17:17:30 |
| `results/app/app140_app042_wsola.py` | 11 629 | `60b31de50f61cc62` | 16:39:22 |
| `results/app/app140_app042_wsola_evidence.json` | 3 531 | `c0d376af890a54ff` | 17:19:40 |
| `results/app/app141_app042_end_to_end.py` | 23 231 | `28dab19ce861d5c0` | 17:16:28 |
| `results/app/app141_app042_end_to_end_evidence.json` | 4 336 | `c599608b0a3108a5` | 17:19:14 |
| `results/app/app141_app042_integration.py` | 31 810 | `f90710e28d007fe2` | 17:03:45 |
| `results/app/app141_app042_integration_evidence.json` | 9 218 | `3080dc0902d0a56a` | 17:19:41 |
| `results/app/app142_app042_pkg_check.py` | 10 608 | `6ae8ca95e060dd36` | 17:15:06 |
| `results/app/app142_app042_pkg_evidence.json` | 4 215 | `0f574f13e8cfc872` | 17:19:41 |
| `Confucius4_LiveCaption_v1.8.zip`（交付物） | 11 218 155 024 | `0e3b4d263c0cbb96…` | 17:37:13 |

### 95.8 git 状态（**普通快进，未 force**）

- 并发会话已提交并 push：`37d278a`（APP-041 + APP-042 实现，**15 个 App 职责内文件**）→ `897da53`（复跑 `app141` 并刷新 evidence，**1 文件**）。
- `HEAD == origin/main == 897da534b61694a8d2392dd7d49ddce689ce64aa`；仓库**只有 `main` 分支**。
- `git show --name-only --format="" HEAD | grep -c CORRECTIONS` = **0** ⇒ `status/app/CORRECTIONS_APP.md`（reviewer 独占）**未入库**。
- 他模块改动（`status/CORRECTIONS.md` / ASR `c0*.py` / `diag_c111_*` / `live_caption_app.py` 方案 C 在制品等）**全部保留在工作区，未吞**。
- 本轮（并发会话之外）**新增提交 = 0** ⇒ 本轮只补写 STATUS。

### 95.9 写后校验

- 章节数 94 → **95**（写后 `grep -c "^## §"`；原有章节**一个不少**）。
- 旧正文（自 `## §1 ` 起的全部内容）**逐字未变**。
- 头部只改 4 字段行：`last_ack` / `更新时间` / `当前任务` / `阻塞 / 待用户决定`；「最近更新」区块 **≤15 行**（插入新行 + 裁掉最旧行）。
