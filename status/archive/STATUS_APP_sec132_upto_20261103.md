### §132 🔄 **APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 ＋ APP-065 A 界面重排 ＋ B 改名** ｜ **本条已完成（代码层）** ｜ **本条需等 reviewer 复核**（2026-11-02 20:52）

> 🔴 **本节更正 §131 的一条结论**：§131 写「D1 是否切 5 s 等 reviewer 裁定（ASR 自己没切 ⇒ App 保持 10 s）」——
> **已不成立**：reviewer 在 APP-063 ③ 裁定「D1 改为 5 s」，且 **ASR 侧 `asr_spk_window.WIN_S` 已于 2026-11-02 16:20 改成 5.0**
> ⇒ App 侧**同源自动跟随**（实测 `_WIN_S = 5.0`，来源「同源 asr_spk_window.WIN_S=5.0」）
> ⇒ **但 ASR 运行时内核未同源**（见 ③）⇒ **旁路目前处于「喂 5 s / 切 10 s」的错位状态**。

#### ① 📌 **开工基线（只读 `CORRECTIONS_APP.md`，全程未写入）**

**开工基线**：`CORRECTIONS_APP.md` SHA `0b9cf622…a033` / 182 008 B / mtime 2026-11-02 14:55:36 / **65 条**（APP-001…APP-065）⇒ **本轮新条目 = APP-063 / APP-064 / APP-065**（`last_ack` APP-062 → **APP-065**）；**收尾实测值见 ⑫**。

#### ② ✅ **APP-063 ①（D4 bug）＋ ②（D2 四入口）—— 代码层已修，`app229` 38 PASS / 0 FAIL**

| 子项 | reviewer 要求 | 本轮实现 | 证据 |
|---|---|---|---|
| **D4 bug** | `_on_mt_combo_changed` 在 enforce 之后又 `set_engine/set_device(opt)` ⇒ **把 MT 覆盖回 NPU**（配置写 GPU.0、实际跑 NPU、还弹框说「已改到 GPU.0」） | ①enforce 命中 ⇒ **重读 `opt`**（`_forced`）②enforce 内补 **set_engine(GPU.0 那一项) → set_device('GPU.0')**（原只调 set_device ⇒ engine 与设备不一致）③**CLI** 补 `--mt-device NPU --tts-device NPU` ⇒ 改 GPU.0 ＋ 日志 | `app229` 探针：`mt.device='GPU.0'`、`engine_key='gpu_int8cw'`、落盘 `mt='GPU.0'`；反证（删重读分支⇒失效）**PASS** |
| **D2(a)** | GUI 启动 `--tts-voice follow_speaker` / `_on_tts_toggled` ⇒ 自动开旁路（原来只打日志「将使用预设 A」） | 启动路径 + `_on_tts_toggled` 克隆分支 ⇒ 都调 `_enable_speaker_for_clone`（幂等） | `d2a_*` 2 条 **PASS** |
| **D2(b)** | CLI `--tts-voice follow_speaker` ⇒ `_spk_enabled=True`（原来只看 `--speaker`） | `_want_clone` **提前**算 ⇒ 强制 True（**显式 `--speaker off` 也不覆盖**） | `d2b_*` 4 条 **PASS** ＋ 反证 **PASS** |
| **D2(c)** | 取消「说话人识别」勾选 ⇒ 音色切回 A 并提示（或禁止取消）；原来 `cb_speaker` **没绑事件** | 新增 `_on_speaker_toggled`：取消 ⇒ 切「预设 A」＋重启 worker ＋状态栏/日志提示；勾选 ⇒ 同步 bridge.enabled | 探针：取消后 `var_tts_voice='预设 A'`、`bridge.enabled=False` **PASS** ＋ 反证 **PASS** |
| **D2(d)** | 会话进行中 ⇒ **真正拉起线程**（原来状态栏说「开」但要重启会话才生效） | 新增 `SpeakerBridge.ensure_started()`（主动 `_ensure_worker()`）＋ 判定 `session.running` ⇒ 即时拉起，状态栏「**已即时生效，无需重启会话**」；失败才如实写「需重启会话后生效」 | `ensure_started` 调用 1 次 ＋ 状态栏含「已即时生效」**PASS** |

🔴 **连带修掉的既有缺陷**：`self.tts` 从未在 `__init__` 初始化 ⇒ 首次 `_on_tts_toggled` 抛 `AttributeError`（APP-065 A 截图脚本在「配音开启」分支实测到）⇒ 已补 `self.tts = None`。

#### ③ ⛔ **APP-063 ③（D1 窗口 5 s）—— App 侧已同源，但 **ASR 内核未同源 ⇒ 跨模块错位**（已交 ASR + reviewer）**

🔴 **实测事实**（`app230` 7 PASS / 5 FAIL，判据就是这条不变量）：

| 项 | 值 | 结论 |
|---|---|---|
| ASR 唯一事实来源 `asr_spk_window.WIN_S` | **5.0**（2026-11-02 16:20 改） | ✅ |
| App 解析 `_WIN_S` / 来源 | **5.0** ／「同源 `asr_spk_window.WIN_S=5.0`」 | ✅ **没写第二份默认值**（reviewer 要求） |
| App 喂窗样本数 | **80 000**（5.0×16 k） | — |
| 内核 `asr052_spk_runtime.WIN_N` / `N_FRAMES` / `FPS` | **160 000**（仍 10 s）/ **589**（5 s 应 293）/ **58.9**（应 58.6） | 🔴 **三处错位** |
| 客户包 `app/asr_spk/` 含 `asr_spk_window.py`？ | **否**（v2.2 只有 `asr052_speaker_tracker_api.py`/`asr052_spk_runtime.py`/`asr_thread_defaults.py`） | 🔴 客户机仍退回 10 s |

⇒ **后果**：`run_seg_side` 的 `while win_start + WIN_N <= len(audio)`（内核 L464）在 App 只喂 80 000 样本时**恒不成立** ⇒ 旁路**拿不到帧**（不是精度下降，是**零标签**）。
⇒ **已发通知**：`shared/NOTICE_app_to_asr_spk_window_5s_alignment.md`（含「内核改成从 `asr_spk_window` 取值」的**首选方案** ＋ 扩交付集合为 4 个文件的**备选方案** ＋ 需 ASR 回答的 3 个问题，含「seg IR 是否已导成 5 s 静态形状」）。
⇒ ⛔ **App 侧无法单方面完成**（`asr052_spk_runtime.py` 属 ASR 模块）⇒ **v2.3 建议暂缓发布**。

#### ④ ✅ **APP-065 A（界面重排）—— 5 组竖排 + 统一网格；截图与清单已备，交 reviewer 复核**

reviewer 要求：「按处理链分组，从上到下：①音频输入 ②语音识别 ③翻译 ④语音输出（开关、输出设备、音色）⑤高级。每组一个 GroupBox，组内用统一网格：标签列右对齐、等宽，控件列左对齐、同宽；**所有组的标签列宽度一致，行高一致**。」

| 要求 | 实现 | 实测（`app231`） |
|---|---|---|
| 5 组竖排 | `self._groups` 内 ①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级（默认收起） | 截图 ＋ `app165` C4（**分区数 = 5**，口径按 APP-065 A 更新）**PASS** |
| 标签列右对齐等宽 | `columnconfigure(0, uniform='lbl', minsize=_GRID_LABEL_PX)` ＋ `anchor='e'`；**不用 `ttk.Label(width=N)`**（N 是字符数 ⇒ 像素宽随缩放变 ⇒ 不可比） | **100 %：4 组右边缘全 56 px**；**150 %：全 76 px**（组间恒等） |
| 控件列左对齐同宽 | 全部 Combobox/Entry 用 `width=_GRID_CTRL_CHARS` | **全 233 px**；左边缘 64 px(100 %)/84 px(150 %)，4 组一致 |
| 行高一致 | 统一 `pady=0` ＋ 同类控件 | 100 % = 18/20 px；150 % = 28/30 px（组间一致） |
| 高级只放不常用项，每项一句话提示 | 设备选择（识别/翻译/语音后端）、草稿译文、重试翻译、显示说话人、**区分说话人（用于克隆）**、离线朗读、测试声音、耳机提示 —— 每项旁**同行**说明 | 控件→组清单 13 项 ＋ `app065a_control_group_map.txt` |
| 常用项不得进高级 | 输入源→①；识别语种→②；目标语言→③；开关/音色/输出设备→④ | 同上清单 |
| 100 %/150 % 各 2 张截图 | `tk scaling` 模拟（**150 % 保持逻辑尺寸不变** ⇒ 物理 = 逻辑×scaling） | **4 张 PNG 全成功**（31.8–43.9 KB），`results/app/app065a_shots/` |

🔴 **本轮顺带修掉的 3 个真缺陷**：①`_adv_frame` **从未 pack** ⇒ 展开「⑤ 高级」是**空的**（实测 h=1）②`lbl_source_note` 的 `reqwidth` **撑宽 column 2** ⇒ 150 % 下右侧被**裁**（且 `before=` 跨父容器 ⇒ **每次启动 TclError**）③顶栏「有模块待处理」按钮 `width=12` 在 150 % 下**文字被裁**。
🔴 **口径冲突（提请 reviewer 裁定）**：APP-061⑥ 的「字幕区 ≥ 窗口高度 **70 %**」与 APP-065 A 的「5 组竖排」在 **800 px 高**下**不可兼得** —— 实测 `app219` G2 = **66.88 %**（其余 11 条全 PASS：状态条 1 行、高级默认收起、1024 宽不越界）。已做的压缩：状态条与控件**同行**（每组省 21 px）、① 组设备控件**并入同一行**（省 25 px）、各组 `padding=(6,0)` ＋ `pady=0`、全局状态行**并入顶栏**。**若必须 ≥70 %**：需允许 ④ 组出现**第二个标签列**（把「开关」与「音色」并到一行）⇒ 可再省 ~25 px ⇒ 约 70 %。

#### ⑤ ✅ **APP-065 B（改名）** ｜ GUI「说话人识别」→ **「区分说话人（用于克隆）」**，**移入「⑤ 高级」**，带提示「检测谁在说话，换人时重新克隆音色；只在音色=跟随说话人时生效」；**变量名 `var_speaker` 保持不变**（`app227`/`app204` 依赖）。

#### ⑥ ✅ **APP-064（锁纪律）** ｜ 设备级作业**先拿 `MACHINE_LOCK` 再跑** ＋ **先探安静窗口**（`wait_quiet_window_cpu`）；`app223 --run` 指向**本轮影子包**（`shared/app065_shadow`）⇒ **测的是本轮代码**，不是 v2.2 旧码。细节见 ⑩。

#### ⑦ 🔄 **回归（本轮全部复跑，输出另存，不覆盖仓库原证据）**

| 脚本 | 结果 | 说明 |
|---|---|---|
| `app229`（新：D4＋D2 四入口，含 3 组反证） | **38/0** | ✅ |
| `app230`（新：D1 跨模块一致性） | **7 PASS/5 FAIL** | ✅ 5 条 FAIL 是**真实跨模块错位**（见 ③），非判据缺陷 |
| `app227`（APP-062 D1–D4） | **34/0** | ✅ 口径已更新：D1 改为「等于 ASR 唯一事实来源」；D2 反证改为破坏**全部** 3 处调用点（旧版删一行留空 `if` 块 ⇒ SyntaxError ⇒ 无法判定） |
| `app165`（APP-048 三分区布局） | **PASS** | ✅ C4 口径更新为 5（依据 APP-065 A）；**C3/C5/C6 未动** ⇒ 状态条仍在自己的分组内、顶部 meter 不在任何分区内 ⇒ **APP-048 核心不变量保住** |
| `app219`（APP-061⑥ 紧凑） | **11 PASS/2 FAIL** | ⚠️ 2 条 FAIL 都是 G2（66.88 % < 70 %）⇒ 见 ④ 口径冲突 |
| `app220`/`app226`/`app228` | **39/10/8 全 PASS** | ✅ 零回归 |
| `app215` | **27 PASS/2 FAIL** | ⚠️ 与本轮无关（`1c_voice_error_when_ref_missing`/`M3_1abc_mutant_is_caught`）—— **HEAD 版同脚本跑出完全相同的 2 条** ⇒ **既有缺陷** |

#### ⑧ 🔴 **本轮新增待 reviewer 裁定 / 待 ASR 回答**
1. 🔴 **D1 跨模块错位**（③）⇒ **ASR 侧必须同源**（`asr052_spk_runtime` 读 `asr_spk_window`）；**v2.3 建议暂缓发布**。
2. 🔴 **70 % 字幕区 vs 5 组竖排**（④）⇒ 请 reviewer 在「接受 66.88 %」与「允许 ④ 组第二个标签列」间选。
3. 🔴 **seg IR 是否已导成 5 s 静态形状**（③ NOTICE 问题 2）⇒ 若仍是 10 s 形状 ⇒ 切 5 s 会**直接报形状不匹配**。
4. 🔴 **app215 的 2 条既有 FAIL**（⑦）⇒ 是否顺手修（属 APP-061①「音色错误提示」）。
5. 🔴 **判据①的假 PASS 已修**（⑪-1）⇒ 请 reviewer 确认「三条故障串」的口径。

#### ⑨ 🔴 **未做 / 未交付**
- ⛔ **未打包 v2.3**（APP-065 A 明文「**截图先交 reviewer，通过后才打包**」⇒ **本轮停在 reviewer 复核点**；且 ③ 的 ASR 错位未解决前也不该打包）。
- ⛔ **未通知用户 / 未改桌面快捷方式**（APP-063 交付要求「先报 reviewer」）。
- ⛔ **v2.1、v2.2 的目录与 zip 一个字节都没动**；本轮只建了**影子包** `shared/app065_shadow`（硬链接自 v2.2）**用于设备级实测**，不是交付物。
- ⛔ **未提交任何 `CORRECTIONS_*.md`**（`status/app/CORRECTIONS_APP.md` 本模块**全程只读**）。
