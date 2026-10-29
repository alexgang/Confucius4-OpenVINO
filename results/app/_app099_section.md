## §99 🔴🔴🔴 **APP-039/040「音色按句绑定」链路自查出 5 处断链（A/B/C/E/F）⇒ 已全部修复 ＋ 修掉 3 个验收脚本自身的判据缺陷 ＋ 客户包 v1.10 已定点同步并持锁重打 zip** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 04:02）

### 99.0 本轮起点（巡检结论）

- 🔴 **纠偏巡检**：`status/app/CORRECTIONS_APP.md` 最大编号 = **APP-042**；
  `STATUS_APP.md` 头部 `last_ack: APP-042` ⇒ **无编号大于 last_ack 的新条目**
  ⇒ 本轮**不执行任何新纠偏**，改为补做 App 职责内的遗留事项。
  （第 26 次同一口径复核；reviewer 独占写入文件**零改动**）
- 🔴 **本轮未修改** `CORRECTIONS_APP.md`（**只读，reviewer 独占写入**）。
- ⚠️ 承接 §98 的阻塞：§98 判定「APP-039/040 核心已实施」⇒ 本轮按 §98 的口径
  **重新逐条走查该链路的代码路径**，结果**自查出 5 处断链** ⇒ §97/§98 的
  「核心已实施」口径**不成立**，见 §99.7 的撤回声明。

### 99.1 🔴🔴🔴 **自查出 5 处断链（A/B/C/E/F）——「测试全绿但用户全挂」的 5 个镜像**

> 🔴 **发现方式**：本轮不是跑既有回归（那必然全绿），而是**逐条按 APP-039/040 的
> 语义要求反查代码路径**，发现 5 处「判据测不到、但真机上必然失效」的断点。
> ⚠️ **这 5 处全部落在「离线验收覆盖不到」的边界上** ⇒ 既有 `app150`/`app152` 全绿
> **不能证明**链路闭合。

#### 断链 A：ASR 段太短 ⇒ 说话人段根本没建起来

- **现象**：`SpeakerTracker.on_final` 里 ASR 的硬门槛 `min_dur_s` 默认 **2.0 s**
  ⇒ 段短于 2 s 时 ASR 直接返 `reason='too_short'` ⇒ App 侧拿不到 `clean_ranges`
  ⇒ **说话人音色样本取不到** ⇒ 整条「音色按句绑定」无从谈起。
- **根因**：App 侧**没有**在调用 ASR 之前为短段**往前借**音频窗口
  ⇒ `speaker_tracker.span_for_final(t_end)` 的 `min_s` 语义写成了「**只往后借**」，
  而真实需求是「**往前借**」（`t_end` 不变，向前取够 `min_s`）。
- **修复**（`live_caption/speaker_tracker.py`）：
  - 新增模块常量 `SPAN_MIN_S = 2.5`（> ASR 的 2.0 s 硬门槛，留 0.5 s 余量）；
  - 新增 `span_for_final(t_end: float, min_s: float = SPAN_MIN_S)`：
    `t0 = te - need` ⇒ **往前借**，`t_end` **保持不变**；
  - GUI 侧 `_on_final` 改用 `speaker_tracker.span_for_final(float(self._seg_audio_end))`；
  - CLI 侧 `on_final` 改用 `speaker_tracker.span_for_final(float(_spk_audio_end[0]))`。
- ⚠️ **判据纠偏**：`app154` 的 A3 原按 `span_for_final(t_start, t_end)` 调用 ⇒
  **真实签名只有 1 个位置参数** ⇒ 第二实参被当成 `min_s` ⇒ 判据**假 FAIL**。
  已改为按真实签名调用（`fn(10.4)` / `fn(20.0)` / `fn(1.0)`）。

#### 断链 B：`dur_s` 恒 0 ⇒ 「攒够 N 秒」门槛永远不满足

- **现象**：`speaker_voice.py` 的建表处 `dur_s=0.0`，而**只有** `add_clean_ranges`
  之外的路径会累加 ⇒ `dur_s` 实际**恒为 0** ⇒ `ready_to_embed` 永远 False
  ⇒ **新说话人永远攒不够样本**。
- **根因**：`add_clean_ranges` 用**求和**累加 ⇒ 区间**重叠**时**重复计数**
  （同一段音频被 ASR 多次标为干净 ⇒ 时长虚高）。
- **修复**（`live_caption/speaker_voice.py`）：
  - 新增 `_merge_clean_spans()`：区间**并集**合并（相邻/重叠合并为一段）；
  - `add_clean_ranges()` 改为累计**并集**并同时维护 `clean_dur_s` / `clean_spans`，
    `dur_s` 改为**等于** `clean_dur_s`（消除双口径不一致）；
  - 两处建表处补齐 `clean_dur_s=0.0` / `clean_spans=[]`；
  - `stats()` 对外暴露 `clean_dur_s`。
- ⚠️ **判据纠偏（假通过）**：`app150` 的 A6 原判据是「S1 从未 `refined=True`
  却断言 `ready_to_embed` 恒 False」⇒ 在 HEAD 上「恰好 PASS」**只是因为断链 B
  让 `dur_s` 恒 0 掩盖了** ⇒ 典型的**假通过**。已改为先
  `mark_embedded('S1', refined=True)` 再查，并新增 A6b「未细化但攒够 `REFINE_S`
  ⇒ **可**细化」的正向门槛。

#### 断链 C：GUI/CLI 侧 `mark_embedded` **不等 worker 回执** ⇒ 失败也当成功

- **现象**：App 侧在**发出** `spk_voice` 命令后**立刻** `mark_embedded(...)`
  ⇒ worker 侧其实**可能失败**（PCM 提取失败 / 音频太短 / 命令超时）
  ⇒ App 侧**照样**把它记成「已登记音色」⇒ 后续所有句子都用一个**无效**音色。
- **根因**：App 侧**没有**接 worker 的 `spk_voice` 事件回执
  （`{'kind':'spk_voice','spk':…,'ok':…,'dur_s':…}`）—— `tts_service.py` 里
  **根本没有** `spk_voice` 事件分支 ⇒ 回执**被丢弃**。
- **修复**：
  - `live_caption/tts_service.py`：`__init__` 新增 `self._spk_voice_status = {}`；
    `_handle_event` 新增 `elif kind == 'spk_voice':` 分支（存 `ok`/`dur_s`/`message`）；
    新增 `spk_voice_status(spk)`（**取出即消费**，避免重复消费同一回执）。
  - `live_caption/live_caption_app.py`（GUI）：`__init__` 新增 `self._spk_voice_sent = set()`
    （元素为 `(spk, refined)`）；`_pump_spk_voices` 开头先查 worker 回执：
    - 回执 `ok=True` ⇒ **此时**才 `mark_embedded(...)`；
    - 回执 `ok=False` ⇒ `mark_fallback(...)`（回落预设 A，**不**用别人冒充）；
    - 回执**未到** ⇒ **继续等**（**不阻塞** pump）。
  - `live_caption/live_caption_app.py`（CLI）：闭包新增 `_spk_voice_sent = set()` +
    `nonlocal _spk_pending_embed, _spk_voice_sent`，同样逻辑。
  - `clear()` 两侧都清理 `_spk_voice_sent`。
- ⚠️ **判据纠偏（假通过）**：`app154` 的反证 C 原为**函数级** token 匹配
  ⇒ 注入的无条件 `mark_embedded` 加在函数开头，而函数里**本就有**
  `spk_voice_status` ⇒ token 命中 ⇒ **假通过**。
  已新增 `mark_embedded_sites()`：**调用点级** AST 判据（沿父链找最近的 `If`，
  要求其条件含 `ok` 且所在函数含 `spk_voice_status(...)`）
  ⇒ 反证 C 现报 `unconfirmed=['_pump_spk_voices@3763']` ⇒ **FAIL** ✅。

#### 断链 E：ASR 的**全局时间轴**被当成**环形缓冲下标** ⇒ 取到的 PCM 全错

- **现象**：`pcm_for_ranges(ranges, keep=…)` 里
  `i = int(round(a * _SR))` ⇒ 把 ASR 给的**全局时间轴秒**直接当**缓冲下标**。
  环形缓冲下标 0 对应的是**缓冲起点**的时刻，**不是** t=0
  ⇒ 只要缓冲里已经滚过一段时间，取出来的 PCM 就**完全错位**。
- **修复**（`live_caption/speaker_tracker.py`）：
  - `pcm_for_ranges()` 新增 `keep_t0` 参数（缓冲起点对应的全局时刻）；
  - 换算改为 `i = max(0, int(round((float(a) - base) * _SR)))`，
    其中 `base = 0.0 if keep_t0 is None else float(keep_t0)`。
  - `live_caption_app.py`：GUI 新增 `self._spk_pcm_t0`（float）、CLI 新增
    `self._spk_pcm_t0`（`[0.0]`），在 `_on_audio_span` / `_cli_on_audio_span` 维护
    `self._spk_pcm_t0 = (float(t_end) - self._spk_pcm_buf.size / float(SR))`；
    三处 `pcm_for_ranges` 调用**全部**加上 `keep_t0=`。
- ⚠️ **判据纠偏**：反证 E 的注入锚点已随实现更新
  （`i = max(0, int(round((float(a) - base) * _SR)))`）。

#### 断链 F 🔴：**初次登记即移出 pending ⇒ APP-040②「攒够 3 s 重算一次」从不发生**

- **现象**：`_pump_spk_voices` 在**初次登记成功**后就把该 spk 从 `_spk_pending_embed`
  移除 ⇒ `else:` 分支（「够 `REFINE_S` 就**用自己的段**重算一次」）**永远进不去**
  ⇒ APP-040② 的「攒到 ≥3 s 用自己的段重算一次」**从不发生**。
- **根因**：pending 集合被**同时**当成「待首次登记」与「待细化」两种语义，
  首次登记成功就把两种语义**一起**清掉了。
- **修复**（GUI + CLI 两侧）：
  - 初次登记回执 `ok=True` 时 **不**把 spk 移出 pending；
  - **只有细化完成**（`_refined=True` 的回执）才移出 pending；
  - 已在等回执的 spk 本轮**跳过**（`if any(s == spk for s, _r in self._spk_voice_sent): continue`）
    ⇒ **不会**重复下发命令。
  - 可行性：`ready_to_embed()` 在 `voice=='clone' and refined` 时返回 False
    ⇒ 不会重复细化。
- ⚠️ **判据**：`app154` 新增 `behavior_F`（用 `_FakeTts` / `_FakeVoiceTable` /
  `_FakeArr` / `_FakeSV` 真跑 GUI pump 的核心逻辑，`ast.unparse` 脱壳 + `self.` 剥离），
  模拟三轮：轮1 发命令（无回执）⇒ 轮2 回执 `ok=True` 后**仍**在 pending
  ⇒ 轮3 应发出**细化**命令（第 2 次 register）；反证注入「初次登记即移出 pending」
  ⇒ `spk_still_pending=False refine_dead=[]` ⇒ 判据 **FAIL** ✅。

### 99.2 🔴 **上轮 bytes 转义写坏中文注释 ⇒ 客户包一启动就崩**（本轮修好）

- **现象**：上轮用 bytes 级替换写中文注释时，把 `\uff08` 写成了**字面反斜杠转义**，
  且产生了**非法 UTF-8 字节** ⇒ `compile()` 直接 `SyntaxError: 'utf-8' codec can't
  decode byte 0x9f` ⇒ **客户包一启动就崩**。
- **定位**：新增 `results/app/_app099_scan_corrupt.py` 扫描 4 个改动文件，
  检出字面 `\uXXXX` 与 U+FFFD ⇒ 命中
  `live_caption_app.py` L3822/L4615、`tts_service.py` L306-308/L1754-1756/L1763/L1765/L1865-1869。
- **修复**：`_app099_fix_svc_pollution.py`（行级定位 + 固定块长）、
  `_app099_fix_gui_c3.py`（按缩进 12/20 区分两处）、`_app099_fix_cli_c.py`
  ⇒ 全部整行重写为正常中文；**写盘前强制** `raw.decode('utf-8')` + `compile()` 校验。
- **当前状态**：4 个文件**全部** UTF-8 OK + COMPILE OK。

### 99.3 ✅ **3 个验收脚本的「判据自身缺陷」已修**（都是「测试全绿但用户全挂」的镜像）

| 脚本 | 缺陷 | 修法 | 结果 |
|---|---|---|---|
| `app150` | A6 在 HEAD 上**假通过**（断链 B 掩盖） | 先 `mark_embedded(refined=True)` 再查 + 新增 A6b 正向门槛 | **17/17 PASS** |
| `app152` | 静态判据「读在绑之前」与真实源码「先读后赋」不符；`drop_nonlocal` 改的是**另一个 tree** ⇒ 反证静默失效 | 判据改为「**重绑外层变量 + 同名有读取**」+ `ast.walk` 排除嵌套函数 + 限定 `SHARED_STATE_VARS` 名单；`drop_nonlocal` 改同一 tree + 删空声明；探针改为**闭包嵌在外层函数内**（保留 `nonlocal` 原义，不改写成 `global`） | **7/7 PASS** |
| `app154` | A3 按错误签名调用；反证 A/E 锚点过时；反证 C 为**函数级** token ⇒ 假通过 | A3 按真实签名调用；锚点更新；新增 `mark_embedded_sites()` **调用点级** AST 判据 | **20/20 PASS** |

### 99.4 ✅ **回归结果**（system Python 3.12，`C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312\python.exe`）

| 脚本 | 结果 | 证据文件 |
|---|---|---|
| `app154_app039_wiring_gap_test.py` | **PASS=20 / FAIL=0**（反证 E/A/B/C/F **5 条全部命中**） | `results/app/app154_app039_wiring_gap_evidence.json` |
| `app150_app039_spk_bound_voice.py` | **PASS=17 / FAIL=0**（反证 A/B/C/D **4 条全部命中**） | `results/app/app150_app039_spk_bound_voice_evidence.json` |
| `app152_app151_cli_closure_scope.py` | **PASS=7 / FAIL=0**（反证①②/② **全部命中**） | `results/app/app152_app151_cli_closure_scope_evidence.json` |
| `app139_app041_startup_tts.py` | **VERDICT PASS**（4 组全 PASS） | `results/app/app139_app041_startup_tts_evidence.json` |
| `app140_app042_wsola.py` | **VERDICT PASS**（4 组全 PASS） | `results/app/app140_app042_wsola_evidence.json` |
| `app141_app042_end_to_end.py` | **24/24 PASS** | `results/app/app141_app042_end_to_end_evidence.json` |
| `app141_app042_integration.py` | **62 PASS / 0 FAIL** | `results/app/app141_app042_integration_evidence.json` |
| `app142_app042_pkg_check.py` | **22 PASS / 0 FAIL**（P2 包内⇄仓库一致 **PASS**） | `results/app/app142_app042_pkg_evidence.json` |
| `app145_app042_cli_target_wall.py` | **VERDICT PASS** | `results/app/app145_app042_cli_target_wall_evidence.json` |
| `app144_app042_jsonl_keys.py` | **REAL 组全 PASS**（4 个 FAIL 全在**反证组** ⇒ 期望结果） | `results/app/app144_app042_jsonl_keys_evidence.json` |

- 🔴 **反证全部命中** ⇒ 判据**不恒真**（不是「写个断言就绿」）。
- 🔴 **未在 CPU 上跑推理/测速**；**未自行调用 MiniMax**。

### 99.5 ✅ **客户包定点同步（禁止整目录覆盖 ⇒ 定点方式）**

- **同步前基线确认**：包内 4 个目标文件**精确等于 HEAD**（归一化 LF 后 SHA 相同）
  ⇒ 包与仓库同源、只差本轮改动 ⇒ 差分同步安全：
  - `speaker_tracker.py` pkg=`b609d5950dc78e4d` HEAD=`b609d5950dc78e4d` ✔
  - `speaker_voice.py` pkg=`27b2b6e31ead94f8` HEAD=`27b2b6e31ead94f8` ✔
  - `live_caption_app.py` pkg=`66d27b9d3a73577e` HEAD=`66d27b9d3a73577e` ✔
  - `tts_service.py` pkg=`46d73950f2cb6558` HEAD=`46d73950f2cb6558` ✔
- **备份**（同步前）：包内 `_backup_app_20261030_pre_sync99/app/`
  （4 文件，SHA 与上表 `pkg` 列一致）。
- **同步方式**（新增 `live_caption/sync_c161_to_pkg.py`）：
  `difflib.SequenceMatcher` **派生替换块**（**OLD 取自「包内实际内容」**）
  → 两端**归一化 LF** → 未变动区间照抄包内 / 变动区间取仓库 → **流式构建**
  ⇒ **不错位** → 写盘前 `compile()` 校验 → 写盘后**逐字节**断言与仓库一致。
- 🔴 **同步脚本自身踩到的 2 个坑（已修）**：
  ① 「纯插入块用原始下标 `i1` 原地插入」⇒ 前序块已改变行数 ⇒ **错位**
     （首次运行即报 `同步结果与仓库不一致（15259 vs 15259 字节）`）⇒ 改为**流式构建**；
  ② 「替换块在包内唯一命中」断言对**合法多处同改**（`speaker_voice.py` 两处建表代码
     **完全相同** ⇒ 命中 2 次）会误报 ⇒ 改为**审计计数**（记录命中次数供复核）
     + **逐字节一致**断言作为真正的安全网。
- **同步结果**（归一化 LF 后与仓库**逐字节一致**）：

| 文件 | 包内 SHA256 | 字节数 | UTF-8 | compile |
|---|---|---|---|---|
| `speaker_tracker.py` | `c7c53000dc2e83ee…` | 15 259 | OK | OK |
| `speaker_voice.py` | `42a7aaeedc944916…` | 20 582 | OK | OK |
| `live_caption_app.py` | `6d930e429b9d9b99…` | 293 051 | OK | OK |
| `tts_service.py` | `4b34e8015d6ad538…` | 125 332 | OK | OK |

- ⚠️ **原始字节 SHA 与归一化 SHA 不同是正常现象**（仓库 CRLF / 包 LF）
  ⇒ **假报警**，必须**归一化后再比**。
- 🔴 `app142` 的 **P2** 判据已由 FAIL（包内 v1.7 vs 仓库）转 **PASS**（22/22）。
- ✅ **包内副本的独立验收**（不依赖「包=仓库」这个推论）：
  `app154` 新增环境变量覆盖 `APP154_LIVE_DIR`（默认仍跑仓库那份 ⇒ 行为不变），
  对**客户包内那份**源码跑同一套验收 ⇒ **PASS=20 / FAIL=0**，反证 E/A/B/C/F **5 条全部命中**。
  证据：`results/app/_app099_app154_pkg_evidence.json`
  （`live_dir` 字段自证来源 = `C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.10/app`）。

### 99.6 ✅ **git 入库**

- **commit `b5bd143`**（12 文件）：`live_caption/{speaker_tracker,speaker_voice,live_caption_app,tts_service}.py`
  ＋ `live_caption/sync_c161_to_pkg.py`
  ＋ `results/app/{app142_pkg_evidence.json, app150*.py+evidence.json,
  app152*.py+evidence.json, app154*_test.py+evidence.json}`。
- 🔴 **未提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占写入）。
- 🔴 **未吞** ASR/MT/TTS 其它模块的未提交改动（逐文件 `git add`，**不用 `-A`**）。

### 99.7 🔴 **撤回声明（更正旧章节口径）**

- 🔴 **撤回 §97.1 的「APP-039 / APP-040 核心：音色按句绑定 spk（已实施）」** ——
  §97 的「已实施」口径**不成立**：当时链路存在**断链 A/B/C/E/F 共 5 处**，
  其中断链 C（不等 worker 回执）、断链 F（细化分支不可达）**在真机上必然失效**。
  ⇒ 以 **§99** 为准。
- 🔴 **撤回 §97.7 结论 ① 的「APP-039/040 核心已实施（GUI + CLI 双路径）」** ——
  同上；本轮已修复 5 处断链，但**仍只做了离线验收**。
- 🔴 **撤回 §98 中「§97 的代码与验收产物未入库 ⇒ 半交付之一已闭环」之外的
  「APP-039/040 核心已实施」隐含口径**（§98 只解决了「入库」，**未解决「是否真闭合」**）。
- ⚠️ **不撤回 §95/§96/§97/§98 的其它结论**（版本自动递增、定点同步机制、三道闸门、
  APP-042 定速口径、闭环机制等仍有效）。

### 99.8 结论

- ✅ **本条已完成**：
  ① **5 处断链（A/B/C/E/F）全部修复**，GUI + CLI **双路径**接线；
  ② **3 个验收脚本的判据自身缺陷**已修（`app150` 17/17、`app152` 7/7、`app154` 20/20，
     反证全部命中 ⇒ 判据不恒真）；
  ③ **上轮非法 UTF-8 污染**已修（4 文件 UTF-8 OK + COMPILE OK ⇒ 客户包不再启动即崩）；
  ④ 客户包已**定点同步**（4 文件归一化后与仓库逐字节一致）+ **同步前备份**；
  ⑤ 回归 **10 个脚本全绿**（含 `app142` 22/22、`app141_integration` 62/62）；
  ⑥ **commit `b5bd143`** 已入库（12 文件，未含 `CORRECTIONS_APP.md`）。
- 🔴 **本条需等 reviewer 复核**：
  ① 🔴 **reviewer 的 MiniMax 回转写错误率对比**（本模块**不得自做**）；
  ② 🔴 **用户实听 3 段 1.2–1.3× 配音**（不变调、可懂）——
     3 段 wav **已落盘并已呈现**，但 `.gitignore` 忽略 `*.wav` ⇒ **不入库**；
  ③ 🔴 **APP-039/040 的音色按句绑定仍只做了离线验收** ——
     **真机 NPU 实测（两个说话人 ⇒ 音色按句切换）未做**；
  ④ 🔴 **APP-041 桌面快捷方式 → `pythonw.exe` 冷启动真机验收未做**；
  ⑤ 🔴 **GUI 路径**的 APP-042 加速未做真机实测（历轮走的是 CLI 回放路径）；
  ⑥ 🔴 **ASR 通知 §8 的交付形态待裁定**（FP16 保真不过门槛 / FP32 过门槛 / INT8 未测）
     ＋ **是否把 `wespeaker-resnet34-fp16`（13 MB）与 `pyannote_seg/ov-fp16`（3.0 MB）
     随包分发**（合计 16 MB）⇒ **会改包内容 ⇒ 需裁定后重打 zip**；
  ⑦ 🔴 **客户机说话人旁路当前必然降级**（实测包内无 wespeaker / pyannote_seg
     ⇒ `SpeakerBridge().available=False`）⇒ 字幕无说话人标签、音色按句绑定在客户机上不生效。
