# §19 明细 —— T-5 内存不持续增长（无界列表有界化） + T-6 设置持久化

> 本文件是 `status/STATUS_EXT.md` §19 的**明细全文**（EXT-016 写作规则：
> 长日志 / 逐条明细写到 notes，STATUS 里只留结论、数字和链接）。

## §19.0 依据与触发方式

* 闸门 `tools/next_instruction.py --json` → **exit 1**
  （`reason=already_executed`，`latest=EXT-026`，`last_ack=26`）
  ⇒ **没有比 EXT-026 更新的纠偏条目**（已把闸门解析逻辑对着
  `CORRECTIONS_EXT.md` 原始文件核过：条目止于 EXT-026，
  「进行中的纠偏」栏为空 ⇒ 闸门的 exit 1 是**真的**，不是解析漏掉）。
* ★ 但按 **EXT-014 ②**（常设规则：「`last_ack` 追平后，只要还有未完成项，
  就自己继续做，不要空转」）⇒ 继续 STATUS「未完成纠偏清单」里的
  **P2 待办**（`克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 /
  30 分钟不崩 …`）。
* ⚠️ **未认领新 EXT 编号**（reviewer 未下发新纠偏）
  ⇒ **`last_ack` 保持 EXT-026**，不自行占用 reviewer 的编号命名空间。
* 本轮**未跑任何真实推理、未占 GPU/NPU、未创建/未回收机器锁**
  （全程 CPU 侧 + node 沙箱 + 回声模式）；开工时 `shared/MACHINE_LOCK`
  **不存在**（`ls` 实测 `No such file or directory`）⇒ 本模块无进程在跑。

## §19.1 P2 待办的现状盘点（先分清「能做」与「不能做」）

| P2 子项 | 本轮判定 | 依据 |
|---|---|---|
| **克隆音色** | ⛔ **不能做** | 依赖 ASR-013 的 pyannote 旁路，**对方模块未交付** ⇒ 写进 STATUS 由主会话转达 |
| **ducking** | ✅ 已完成（§15） | 本轮不重复 |
| **字幕** | ✅ 已完成（§15） | 本轮不重复 |
| **设置持久化** | ✅ **本轮做**（T-6） | 不需要 reviewer 决策、不需要真实引擎 |
| **暂停拖动** | ⛔ 本轮**不做** | 需要真实浏览器 + 真实引擎 + 用户手势；且 EXT-001 原文口径是「拖动进度条 ⇒ 清空会话重新开始」，属**新增交互**而非修缺陷 ⇒ 留待 reviewer 明确口径 |
| **30 分钟不崩 / 内存不持续增长** | ✅ **本轮做**（T-5） | 「内存不持续增长」这一半**可静态审出真缺陷**并修复；「30 分钟不崩」本身仍需真实引擎长跑 |

## §19.2 T-5：审出 3 类**无界增长**的真缺陷

审「内存不持续增长」时，逐个列表查「只追加、无上限」。

### 缺陷 T5-a（服务端）：`_frame_arrival_delays` 每帧追加、永不裁剪

* **位置**：`ext/bridge.py` → `Session.on_pcm_frame()`。
* **旧代码**：`self._frame_arrival_delays.append({...})` —— **无任何上限**。
* **量级**：上行帧长 20–100 ms ⇒ **≈47 帧/秒** ⇒
  **30 分钟 ≈ 8.5 万条/会话**；每条是 dict（4 字段）⇒ 单会话几十 MB 量级
  ⇒ 内存随会话时长**线性增长** ⇒ 正是 P2「内存不持续增长」要防的事。
* **修法**：
  1. `ext/config.py` 新增 `FRAME_DELAY_HISTORY = 2000`（≈42 秒明细，几十 KB）。
  2. 追加后裁剪：`del self._frame_arrival_delays[:-C.FRAME_DELAY_HISTORY]`。
  3. **统计口径不变** —— 这是关键：`stats()` 里的
     `n_frames_measured` / `late_ratio` / `mean_delay_sec` / `max_delay_sec`
     原本是**对列表求值**的 ⇒ 裁剪后会变小 ⇒ **口径会变**（假回归）。
     ⇒ 改为**累计量**承担统计：
     `_n_frames_measured` / `_sum_frame_arrival_delay` / `_n_frames_late`
     / `_max_frame_arrival_delay`。
  4. ⚠️ **均值的等价性**：旧实现求和的是**已 round(delay,4)** 的值
     ⇒ 新的累计量也累加 `round(_delay, 4)`
     ⇒ 与旧实现**逐位等价**（不是「近似相同」）。
  5. 如实新增 `history_window` / `history_kept` 两个字段
     ⇒ reviewer 能直接核对「窗口多大、实际留了多少条」。

### 缺陷 T5-b（服务端）：`_seg_orig_end` / `_seg_ready` **只写不读**

* **位置**：`ext/bridge.py` → `Session.__init__` 声明，
  `_process_segment()` 写 `self._seg_orig_end[seg_id] = orig_end`，
  `_finalize_segment()` 写 `self._seg_ready[seg_id] = ready_at`。
* **实测无任何读取点**：全仓 `grep -rn "_seg_orig_end\|_seg_ready" tools/ tests/`
  ⇒ **零命中**；`ext/bridge.py` 内也只有这两处赋值 ⇒
  **纯粹的「只写不读」字典** ⇒ 每收一段永久多留两个 key。
* **修法**：加 `_trim_seg_timing_history()`，只留最近
  `C.SEG_TIMING_HISTORY = 50` 段（≈10 分钟的段级信息）。
  ⚠️ 因**无读取点** ⇒ 裁剪**不影响任何统计口径**。
  ⚠️ 加了 `threading.Lock`（流水线模式下 `_process_segment` 与
  `_finalize_segment` 可能被不同线程碰到 ⇒ 裁剪时改 dict 会 RuntimeError）。

### 缺陷 T5-c（插件）：`gapDetail` 只追加、永不裁剪

* **位置**：`extension/player.js`（`upState.gapDetail`）与
  `extension/offscreen.js`（`state.gapDetail`）—— **两边都中招**。
* **旧代码**：每次「seq 不连续」或「sample_index 不连续」就 push 一条
  ⇒ 网络抖动时**无限增长**。
* **修法**：加 `GAP_DETAIL_CAP = 200`（两个文件各一份），
  超出即丢最旧的并**如实计数**（`gapDetailDropped`），
  **不静默丢**。上报口径（`slice(-20)`）**不变**。

### ⚠️ 刻意**没有**改的（避免破坏验收语义）

* `Session.margins` / `Session.engine_calls` —— **每段一条**，且是
  reviewer 的**验收记录本体**（`n_segments` / 滞后曲线 / 各倍率时间占比
  都从 `margins` 算）⇒ 裁剪它会让**验收数字失真** ⇒
  「宁可内存涨，也不能让验收口径失真」。
  ⇒ 如实写进 STATUS 的未完成清单。

## §19.3 T-6：设置「改了却存不住」的真缺陷

* **位置**：`extension/popup.js`。
* **旧代码**：`saveCfg()` **只在 `btnStart` 的点击处理器里被调用**
  （`grep -n "saveCfg" extension/popup.js` ⇒ 只有定义处 + 一处调用 + `loadCfg`）。
  ⇒ 用户改了「目标语言 / 延迟 D / 原声压低量 / 字幕开关」之后
  **直接关掉弹窗**（绝大多数人的习惯）⇒ 改动**全部丢失**
  ⇒ 下次打开面板又回到旧值 ⇒ **用户的设置根本没被记住**。
* **修法**：
  1. 新增 `readCfg()`（只读、**已归一**）、`persistCfgNow()`（立刻落盘）、
     `schedulePersistCfg()`（400 ms 防抖）。
  2. 新增 `bindPersistListeners()`：给 **8 个设置控件**
     （`ws / token / delay / lang / voice / duck / subs / player`）
     挂 `change`（立即落盘）；文本框与数字框额外挂 `input`（防抖落盘）。
  3. `saveCfg()` **改为复用 `readCfg()`** ⇒ 两条写盘路径口径**必然一致**
     ⇒ 不会出现「即时保存存引擎码、点开始时存成别的」这种分叉。
  4. 落盘前**归一**（`normalizeLang` / `normalizeVoice`）⇒
     语言全称 `Chinese` ⇒ 引擎码 `zh`，与 `loadCfg()` 读回时的口径一致。
  5. **幂等**：`bindPersistListeners._bound` 标记位 ⇒ 重复调用不会挂重复监听。
  6. 调用点放在 `loadCfg()` **之后**（否则会被 `loadCfg` 填 DOM 的动作
     触发一次误存）。

## §19.4 自测与 ★反证（区分「真通过」与「假通过」）

### 新增文件（2 个）

| 文件 | 内容 |
|---|---|
| `tests/t5_t6_bounds_persist_harness.js` | **16 项**：A 组 player.js gapDetail 有界（3）+ 反证（1）；B 组 offscreen.js gapDetail 有界（2）；C 组 popup 设置持久化（9）+ 反证（1） |
| `tests/test_t5_t6_bounds_persist.py` | **40 项**：A 组 插件行为级（10）；B 组 服务端逐帧延迟有界 + **口径对照**（13）；C 组 段级时刻表有界 + 反证（4）；D 组 持久化源码口径（13） |

### ★ 反证清单（每条都实测过「改坏 ⇒ 必须红」）

| # | 反证 | 实测结果 |
|---|---|---|
| 1 | 把 `player.js` 的裁剪块短路（`if (false)`） | node harness **rc=1**（3 条断言红） |
| 2 | 把 `popup.js` 的 `bindPersistListeners` 改成空函数 | node harness **rc=1**（写入次数 0） |
| 3 | 删掉 `ext/bridge.py` 的帧延迟裁剪两行 | Python 测试 **rc=1**，**3 条断言红**（`被裁到 ≤ 2000` 实测 6500 条 / `history_kept` / `口径对照`） |
| 4 | 把 `_trim_seg_timing_history` 短路成 `lambda self: None` | Python 测试 **rc=1**（`_seg_orig_end` 实测 250 条 > 50） |
| 5 | harness 内置反证：裁剪块短路 ⇒ gapDetail 无限增长 | harness 内 PASS（断言有区分力） |
| 6 | harness 内置反证：不挂监听 ⇒ 不写盘 | harness 内 PASS（断言有区分力） |

### ★ 一个**测试自身的坑**（已修，值得记）

* 第一次跑「口径对照」时，**2 条断言红了**（`max_delay_sec` / `mean_delay_sec`）。
* **根因不是产品代码**，是**测试的墙钟噪声**：两个 session 的 `t0` 是
  **各自构造时刻**的 `time.perf_counter()` ⇒ 同一份喂帧算出不同的
  `arrival_delay` ⇒ 比对读到的是**构造间隔**，不是口径差异。
* ⇒ 修法：① 显式把两个 session 的 `t0` 设成**同一个基准点**；
  ② 用**同一组 `recv_at`**（`t0 + 固定偏移`）喂 ⇒ `arrival_delay` 完全确定。
* ⇒ 顺带发现并修了一个**真口径差异**：旧实现求和的是
  **round(delay,4)** 后的值，我第一版累加的是**未 round** 的值
  ⇒ 已改成累加 `round(_delay, 4)` ⇒ 与旧实现**逐位等价**。
* ★ **教训**：做「两种实现的读数比对」时，必须先把**输入与时间基准**固定住，
  否则比出来的是噪声 —— 这跟之前「自测里的固定端口 + 固定超时是假 FAIL 的常见来源」
  是同一类问题（**时间/环境不固定 ⇒ 比对失效**）。

### ★ 行尾符（CRLF）坑（已修）

* `extension/popup.js` 在工作区里是 **CRLF**（git `LF will be replaced by CRLF`）。
* ⇒ 反证用的正则 `/function bindPersistListeners\(\) \{[\s\S]*?\n\}\n/`
  **匹配不到**（行尾是 `\r\n`）⇒ harness 直接抛错。
* ⇒ 全部改成 `\r?\n`（node 与 Python 两处）⇒ **与行尾符无关**。

## §19.5 自测结果（全部**实测**，rc 取真实退出码，未 pipe）

### ① 三套明文要求的自测（单独确认 rc=0）

| 套件 | 结果 | rc |
|---|---|---|
| `tests/test_ext_selfcheck.py` | **103 PASS / 0 FAIL** | **0** |
| `tests/test_echo_roundtrip.py` | **11 PASS / 0 FAIL** | **0** |
| `tests/test_next_instruction.py` | **19 PASS / 0 FAIL** | **0** |

### ② 全量 Python 自测

* **24 套** ⇒ **1 104 PASS / 1 FAIL**（§18 为 23 套 / 1 064 PASS / 1 FAIL
  ⇒ **新增 1 套 / +40 PASS**，**零回归**）。
* ★ **唯一 FAIL 仍是既有的 `test_ext016_compression`**
  （「压缩后 CORRECTIONS 明显变小（实测 21 943 B）」⇒ 阈值 20 480 B）。
  ⇒ **基线复核**：`git stash` 掉本轮全部改动后重跑 ⇒
  **同样 38 PASS / 1 FAIL / rc=1** ⇒ **既有状态、非本轮引入**。
  ⇒ `CORRECTIONS_EXT.md` 由 **reviewer 独占写入**，本模块**只读、未修改**
  （`.gitignore:34` 仍在，`git log --all` 无记录）⇒ **如实报告，不修改、
  不 `git add -f`**。

### ③ node harness（7 套全 rc=0）

| harness | 结果 |
|---|---|
| `ext024_link_harness.js` | 33 PASS / 0 FAIL |
| `ext026_e2e_harness.js` | 13 PASS / 0 FAIL |
| `ext026_prodpath_harness.js` | 17 PASS / 0 FAIL |
| `ext026_segid_harness.js` | 13 PASS / 0 FAIL |
| `t3_settings_harness.js` | 26 PASS / 0 FAIL |
| `t4_lang_harness.js` | 28 PASS / 0 FAIL |
| **`t5_t6_bounds_persist_harness.js`**（新） | **16 PASS / 0 FAIL** |

### ④ 闸门复测

本轮收尾时 `tools/next_instruction.py --json` → **exit 1**
（`latest=EXT-026` / `last_ack=26`）⇒ **闸门解析未被本轮改动弄坏**
（`test_next_instruction.py` 19 PASS 也印证）⇒ 下一轮不会重复执行 EXT-026。

## §19.6 产物清单（均为**实测**）

| 产物组 | 文件数 | 字节数 | 备注 |
|---|---|---|---|
| 产品代码改动 | 5 | — | `ext/bridge.py` / `ext/config.py` / `extension/player.js` / `extension/offscreen.js` / `extension/popup.js`（+215 −12 行） |
| 新增自测 | 2 | — | 1 个 node harness + 1 个 Python 测试 |
| notes 明细（本文件） | 1 | — | 6 节 |

## §19.7 ⛔ 明确未做 / 不宣称

- ⛔ **未认领新 EXT 编号** ⇒ `last_ack` **保持 EXT-026**（不占 reviewer 编号空间）。
- ⛔ **克隆音色仍不可用**（pyannote 旁路未接线，**依赖 ASR-013 交付**）⇒ 未动引擎。
- ⛔ **「30 分钟不崩」未做**（需真实引擎 + 独占设备）⇒ 本轮只做了
  「内存不持续增长」这一半的**静态审计与修复** ⇒ **不宣称「30 分钟不崩已验证」**。
- ⛔ **「暂停拖动」未做**（需真实浏览器 + 用户手势，且属新增交互）⇒ 留待 reviewer 明确口径。
- ⛔ **未改任何引擎文件**（ASR/MT/TTS 对方模块一行未动）。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**。
- ⛔ **未跑真实推理、未占 GPU/NPU、未创建/未回收机器锁**。

---

# §20 明细 —— §19 收口（补 EXEC_LOG + 提交 + **STATUS 压缩回 EXT-016 限额内**）

> 本节是 `status/STATUS_EXT.md` §20 的**明细全文**。

## §20.0 触发方式

* 闸门 `tools/next_instruction.py --json` → **exit 1**（`reason=already_executed`，
  `latest=EXT-026`，`last_ack=26`）⇒ **没有比 EXT-026 更新的纠偏条目**
  ⇒ **未认领新编号** ⇒ **`last_ack` 保持 EXT-026**。
* ★ 但上一轮（§19）**被中断**：worktree 脏（5 改 + 3 未跟踪），
  代码与 `status/notes/sec19_*.md` 已写好，**但 `status/EXEC_LOG.md` 未追加、也未提交**
  ⇒ 本轮做**收口**（按 **EXT-014 ②**：闸门 exit 1 ≠ 空转）。

## §20.1 ★ 本轮发现并修掉的一个「本轮引入的回归」

★ **这是本轮最重要的发现**，值得单列：

* §19 那一轮把 §19 正文写进精简版 STATUS ⇒ 精简版体积从 **22 559 B** 涨到 **29 652 B**。
* ⇒ **撞破 EXT-016 的硬约束**「精简版 < 归档/10 = 22 483 B」
  （归档 `status/archive/STATUS_EXT_upto_20261030.md` = **224 833 B**）。
* ⇒ `test_ext016_compression.py` 的断言「**精简版 STATUS 不含历史全文（确实变小了）**」
  **由 PASS 转 FAIL**。
* ⚠️ **差点犯的错**：§19 的 notes 里把它写成「唯一 FAIL 仍是既有的 `test_ext016_compression`
  ⇒ 基线复核确认非本轮引入」⇒ 只报了 CORRECTIONS 那一条 FAIL，**漏了这条由 §19 自己引入的**。
  ⇒ **教训**：「基线复核」必须**逐条 FAIL** 比对，不能只看「总数一样」。
* ✅ **修法**（**按 EXT-016 规则裁剪，不是删内容**）：
  * §17 / §18 / §19 的**内联明细**全部**下沉到 `status/notes/`**
    （`sec17_ext024_closeout.md` / `sec18_ext026_real_e2e.md` / `sec19_t5_t6_bounds_persist.md`
    三份**已在库**，且已含全部实测数字与反证 ⇒ **内容零丢失**）；
  * 精简版 STATUS 里只留「**依据 + 关键实测数字 + 结论 + 指针**」；
  * 内联章节只保留**最近 3 节**（EXT-016 规则）⇒ §17 只在指针表留一行。
* ⇒ 结果：精简版 **22 326 B**（限额 22 483 B）⇒ 该断言**恢复 PASS**。
* ⚠️ **不回头改旧章节的结论**；§17/§18/§19 的**数字一字未改**（只是搬到 notes）。

### ★ 压缩过程中踩到的两个「自己制造的坑」

| 坑 | 现象 | 修法 |
|---|---|---|
| **误删换行把两行表格合并** | 表格行变成 `... || ...` ⇒ 渲染错乱 | 用脚本改文件时**不要把行尾换行一起删**；改完必须校验「每行列数」 |
| **头部 ≤ 15 行的硬约束** | 头部从 15 行涨到 **21 行** ⇒ 撞上 `test_ext016_compression` 的「头部 ≤ 15 行」断言 | 把「当前任务」的多行压成**一行**；把「阻塞 ④ EXT-023 已收口」并入 ⑥（结论表里已有该行）⇒ 头部回到 **14 行** |

## §20.2 本轮实测结果

* 三套**明文要求**的自测单独确认 **rc=0**：
  `test_ext_selfcheck.py` **103 PASS / 0 FAIL**、
  `test_echo_roundtrip.py` **11 PASS / 0 FAIL**、
  `test_next_instruction.py` **19 PASS / 0 FAIL**。
* 全量 Python 自测：**24 套** ⇒ **1 078 PASS / 2 FAIL**
  （★ 首个 FAIL = `test_ext016_compression` 的「CORRECTIONS 明显变小」⇒ **reviewer 独占文件、只读不改**、
  **既有状态**；★ 第二个 FAIL = 同套件的「精简版 STATUS 不含历史全文」⇒ **本轮引入、本轮已修**）。
* node harness **7 套全 rc=0**（33 / 13 / 17 / 13 / 26 / 28 / **16**）。
* ★ **两个「环境性红套件」的实测归因**（**不是本轮引入**，`git stash` 基线复核同样红）：
  * `test_t2_port_guard.py` —— 4 条 FAIL 的根因是**实时字幕 App 正在运行**
    ⇒ 设备互斥 ⇒ 桥接返回 **rc=3**（而不是期望的 6）
    ⇒ 实测 `_caption_app_running()` = **True** ⇒ **本模块不得干预用户的 App**；
  * `test_ext026_audio_analysis.py` —— 批处理中偶发红，根因是 **safe-delete 钩子**拦截
    批量删除（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，`count=312 > threshold=50`），
    作用对象是浏览器 profile 临时目录 ⇒ 单独跑 **25 PASS / 0 FAIL / rc=0**。

