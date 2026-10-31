# §15 T-3 —— 插件面板「死控件」修复（逐条明细）

> 本文件是 `status/STATUS_EXT.md` §15 的**明细全文**（EXT-016 写作规则：
> 长日志 / 逐条明细写到 notes，STATUS 里只留结论、数字和链接）。

## §15.0 依据与触发方式

* 闸门 `tools/next_instruction.py --json` → **exit 1**
  （`reason=already_executed`，`latest=EXT-017`，`last_ack=17`）
  ⇒ **没有新的 EXT 纠偏指令**（我另外把闸门的解析逻辑对着
  `CORRECTIONS_EXT.md` 的**原始文件**核过一遍：条目只有 EXT-013~EXT-017，
  **不存在比 EXT-017 更新的编号** ⇒ 闸门的 exit 1 是**真的**，不是解析漏掉）。
* 按 **EXT-014 ②**（常设规则：「`last_ack` 追平后，只要还有未完成项，
  就自己继续做，不要空转」）⇒ 继续 STATUS「未完成纠偏清单」里的
  **P2 待办**（`克隆音色 / ducking / 字幕 / 设置持久化 / …`）。
* ⚠️ **未认领新 EXT 编号**（reviewer 未下发新纠偏）
  ⇒ **`last_ack` 保持 EXT-017**，不自行占用 reviewer 的编号命名空间。
* 本轮**未跑任何真实推理、未占 GPU/NPU、未创建/未回收机器锁**
  （全程 CPU 侧 + 回声模式 + node 沙箱）。

## §15.1 找到的缺陷：4 个面板控件是「死控件」

审 P2 待办时逐个核对面板控件与真实实现，发现 **4 个控件在面板上怎么调都不起作用**，
而 `USER_GUIDE.md` **明确承诺**它们可调：

| # | 控件 | 面板承诺 | 真实行为 | 根因（读代码得到） |
|---|---|---|---|---|
| **D1** | **原声压低量（dB）** | 「把原声压低多少 dB」 | **永远是 1.0（不压低）** | `player.js` 的 `setupOriginalAudio` 硬编码 `origGain.gain.value = 1.0`；`duckDb` 只在 `popup.js` 存进 `chrome.storage.local`，**`player.js` 从来没读过** |
| **D2** | **字幕开关** | 「是否显示译文字幕」 | **关掉也照样显示** | `player.js` 的 `pumpSubs` **无条件**写 `div.innerHTML`；`subsOn` 同样只存不读 |
| **D3** | **目标语言** | 「配音要译成的语言」 | **选了不生效** | ① `popup.html` 存的是语言**全称**（`Chinese`/`English`/`Japanese`），而引擎的 `LANG_TO_MT`/`LANG_TO_TTS` **只认 `zh/en/ja/ko`**；② 更根本：`targetLang` **从没进过 `start` 消息** ⇒ 服务端**根本收不到** |
| **D4** | **音色** | 「预设 A / 克隆说话人」 | **选了不生效** | ① `voice` **从没进过 `start` 消息**；② 服务端 `tracker.voice_for(spk)` **完全忽略用户选择** —— 只要某个说话人攒够 3 s 干净语音，就**自动**切到克隆音色 ⇒ 用户选「预设 A」也不管用 |

### 交叉验证（不是「看代码觉得像」）

* 全扩展目录搜 `duckDb` / `subsOn` ⇒ **命中点只有 `popup.js` 与 `sw.js` 的默认值**，
  `player.js` / `offscreen.js` **零命中**（`grep -rn "duckDb\|subsOn" extension/`）。
* `popup.js` 的 `start` 消息字段实测只有
  `{target, cmd, tabId, wsUrl, token, delaySec}` ⇒ **不含** `targetLang` / `voice`。
* `sw.js` → `offscreen.js` 的 `start` 载荷同样只有
  `{streamId, display, wsUrl, token, delaySec}`。
* `offscreen.js` 的 hello 消息只有
  `{type, token, sample_rate, source, role}` ⇒ **不带** `target_lang`。
* 服务端 `Session.note_client()` 只认 `capture_mode` / `source`/`role` / `source_rate`
  ⇒ **没有** `target_lang` / `voice` 的入口。

## §15.2 修复（最小、范围可控）

### ① 原声压低量（`player.js`）

* 新增 `dbToGain(db)`：dB → 线性增益 `10^(dB/20)`，
  **越界夹到 [-60, 0]**（防止正 dB 把增益放大到削波），非法输入回落 1.0。
* 新增 `applyDuckDb()`：把增益真正写到 `origGain.gain` 上，
  并把**用户设的值**（`metrics.duckDb`）、**换算出的增益**（`metrics.duckGain`）、
  **已实际套用的 dB**（`metrics.duckDbApplied`）**分开记** ⇒
  抓流前（`origGain` 还不存在）`duckDbApplied` 保持 `null`，**不假装已生效**。
* `setupOriginalAudio` 里把硬编码的 `origGain.gain.value = 1.0` 换成 `applyDuckDb()`。
* `boot()` 读 `cfg.duckDb`（默认 −15）；并监听 `chrome.storage.onChanged`
  ⇒ **运行中改设置立刻生效**，不用重开窗口。

### ② 字幕开关（`player.js`）

* `pumpSubs()`：`subsOn === false` ⇒ **一次都不写 DOM**，
  并把**已显示的旧字幕清空**（不留残影）、把队列里的旧字幕丢弃（并计数，不静默丢）。
* `scheduleSub()`：字幕关 ⇒ **不入队**（省掉无用的文本处理）。
* `metrics.subsOn` 如实回报当前开关状态。

### ③ 目标语言（`popup.html` / `popup.js` / `sw.js` / `offscreen.js` / `ext/bridge.py`）

* `popup.html`：下拉框 `value` 改成**引擎码** `zh/en/ja/ko`（显示文字不变）。
* `popup.js`：新增 `normalizeLang()` —— 老配置里存的**全称**
  （`Chinese`/`English`/`Japanese`/`Korean`）**自动迁移**成引擎码
  ⇒ 用户不会遇到「下拉框选不中任何一项」。
* `popup.js` → `sw.js` → `offscreen.js`：`start` 消息**带上** `targetLang` / `voice`，
  offscreen 把它放进 **hello** 消息（`target_lang` / `voice`）。
* `ext/bridge.py`：`Session.note_client()` 记 `client_target_lang` / `client_voice`。
  ⚠️ 语言**只接受白名单**（`C.LANG_CODES` = `zh/en/ja/ko`）——
  传全称或其它值一律记 `None`（**不静默接受**），否则 reviewer 会看到
  「目标语言：Chinese」这种引擎其实不认的值，误以为这轮真按它译了。
* `ext/config.py`：新增 `LANG_CODES`（与 `engine_runtime` 的两张表**键集合一致**）。
* `stats()` 与落盘的 `margin.json` 都带上 `client_target_lang` / `client_voice`
  ⇒ reviewer **可以直接从产物核对**本轮面板上选了什么。
  ⚠️ 与 `margin.json` 里原有的 `target_lang`（**服务端启动参数**）**区分开**。

### ④ 音色（`ext/bridge.py`）

* 新增 `Session._pick_voice(spk)`：
  * 面板选 `A` ⇒ **一律用预设 A**（**不再看 tracker 说什么** ⇒ 修掉 D4 的自动切换）；
  * 面板选 `clone` ⇒ 沿用 tracker 的判断（攒够 3 s 才克隆，否则回落预设 A）。
* ⚠️ **诚实性**：选 `clone` 但**没有 spk** 时**回落到预设 A**
  （因为 pyannote 旁路**尚未接线**）⇒ 由 `client_voice` 如实记录，**不假装克隆已生效**。

## §15.3 验证

### ① 插件侧行为级（node 沙箱跑 `player.js` 的**真实函数**）

本机**没有 playwright**（实测 `ModuleNotFoundError: No module named 'playwright'`）
⇒ 不能在真浏览器里点面板。
⇒ 做法：`tests/t3_settings_harness.js` 从**真实的 `player.js` 源文件**里
**原样抽出** `dbToGain` / `applyDuckDb` / `scheduleSub` / `pumpSubs` /
`setupOriginalAudio`（按花括号配对抽取，不是正则截半），
放进带桩的沙箱（`vm`）里执行 ⇒ **验的是真代码，不是复刻品**。

⇒ **26 PASS / 0 FAIL**（harness 自报）。

关键几条：

```
[PASS] dB=-15 ⇒ 增益 ≈ 0.1778（= 10^(-15/20)）
[PASS] ★★★ 走真实 setupOriginalAudio ⇒ 新建的原声增益节点 = 0.1778
[PASS] ★★★ 对照组：dB=0 ⇒ 原声增益 = 1.0（没被误静音）
[PASS] ★★★ 对照组：dB=-40 ⇒ 原声增益 ≈ 0.01
[PASS] ★ 抓流前（origGain 不存在）⇒ duckDbApplied 保持 null（不假装生效）
[PASS] ★★ 字幕关 ⇒ DOM **一次都没被写**
[PASS] ★★ 字幕关 ⇒ 队列里的旧字幕被清空（不留残影）
[PASS] ★★ 字幕关 ⇒ 新字幕不入队
[PASS] ★★ 字幕关 ⇒ 已显示的旧字幕被清空（不留残影）
```

### ② ★ 反证（harness 必须有区分力）

★ **第一次反证暴露了 harness 自己的漏洞**：只测 `applyDuckDb()` 的直接调用时，
把 `setupOriginalAudio` 改成硬编码 1.0 **没被抓到**（因为测试绕过了建图路径）。
⇒ 于是把断言改成**走真实的 `setupOriginalAudio`**（建出真正的增益节点再读它的值），
并补了 `dB=0` / `dB=-40` 两个对照组。

改坏后的实测（`player_broken.js`：ducking 退回硬编码 1.0 + 字幕开关失效）：

```
harness 结果：20 PASS / 6 FAIL / 共 26
FAIL 明细：
 - ★★★ 走真实 setupOriginalAudio ⇒ 新建的原声增益节点 = 0.1778 — 实测 1
 - ★★★ setupOriginalAudio 之后 duckDbApplied = -15 — 实测 null
 - ★★★ 对照组：dB=-40 ⇒ 原声增益 ≈ 0.01 — 实测 1
 - ★★ 字幕关 ⇒ DOM **一次都没被写** — writes=["<span>不该出现</span>"]
 - ★ 字幕关 ⇒ metrics.subsOn 如实为 false — 实测 true
 - ★★ 字幕关 ⇒ 已显示的旧字幕被清空（不留残影） — 实测 "<span>旧字幕</span>"
```

⇒ **6 个缺陷全部被抓到，rc=1** ⇒ harness **有区分力**（不是恒真断言）。

### ③ 服务端行为级（真起桥接 + 真 WebSocket，回声模式）

* 真起 `bridge.serve()`（动态端口，**不撞**用户正在跑的 8765 实例），
  用真 WebSocket 发 hello（`Origin` 用本插件 id）⇒
  `stats` 里 `client_target_lang='ja'` / `client_voice='clone'`。
* ★ **对照组**：连一个**不带** `target_lang` 的客户端 ⇒ `client_target_lang` 是 `None`
  ⇒ 证明**服务端不会自己编**。
* ★ `hello_ack` 的结构**没变**（向后兼容，不破坏旧客户端）。

### ④ 自测套件

`tests/test_t3_dead_controls.py` ⇒ **53 PASS / 0 FAIL**（rc=0），
含 A 插件行为级（含反证）/ B 语言码接线 / C 音色偏好 / D 服务端产物 /
E 真起桥接 / F 文档口径 六组。

### ⑤ 完整回归

**16 套 / 858 PASS / 0 FAIL**（全 rc=0，逐套实测真实退出码）：

```
echo_roundtrip 11 / ext009 57 / ext010 23 / ext011 29 / ext012 75 /
ext013_compare 51 / ext013_cpu_watch 25 / ext016_compression 39 /
ext017_user_report 108 / t1_capture_mode 38 / t2_port_guard 28 /
★ t3_dead_controls 53 / browser_contract 102 / selfcheck 103 /
next_instruction 19 / p1_plumbing 97
```

★ 三套**明文要求**的自测单独确认退出码：
`test_ext_selfcheck.py` rc=0 / `test_echo_roundtrip.py` rc=0 / `test_next_instruction.py` rc=0。

★ 闸门仍正常：`next_instruction.py --json` → exit 1 / `latest=EXT-017` / `last_ack=17`
⇒ **压缩与本轮改动都没弄坏闸门**。

## §15.4 产物（文件数 / mtime / 字节数）

| 产物 | 文件数 | mtime | 字节数 |
|---|---|---|---|
| `tests/test_t3_dead_controls.py` | 1 | 2026-10-31 00:30 | 19 372 |
| `tests/t3_settings_harness.js` | 1 | 2026-10-31 00:28 | 9 878 |
| `status/notes/sec15_t3_dead_controls.md` | 1 | 2026-10-31 00:40 | 本文件 |

（`extension/*.js` 与 `ext/*.py` 的字节数见 §15.5 表。）

## §15.5 涉及修改的文件

| 文件 | 改动 |
|---|---|
| `extension/player.js` | 原声压低量（`dbToGain`/`applyDuckDb`）+ 字幕开关（`pumpSubs`/`scheduleSub`）+ `boot()` 读设置与 `storage.onChanged` 监听 + `metrics`/`__ext.settings()` 暴露生效值 |
| `extension/popup.html` | 目标语言 `option value` 改成引擎码 `zh/en/ja/ko`（+ 补 `ko`） |
| `extension/popup.js` | `normalizeLang()` 归一 + `start` 消息带 `targetLang`/`voice` + 启动状态回显四个设置 |
| `extension/sw.js` | `start` 载荷透传 `targetLang`/`voice`；`onInstalled` 默认 `targetLang='zh'` |
| `extension/offscreen.js` | `connectWs` 收 `opts`，hello 带 `target_lang`/`voice` |
| `ext/bridge.py` | `note_client` 记 `client_target_lang`/`client_voice`（语言走白名单）；新增 `_pick_voice`；`stats()` 与 `_dump_margin` 带新字段 |
| `ext/config.py` | 新增 `LANG_CODES` |
| `USER_GUIDE.md` / `extension/USER_GUIDE.md` | 参数表补 `ko` + T-3 修正说明（含「克隆仍不生效」的诚实说明）；两份保持**逐字节一致** |

## §15.6 ⛔ 明确未做 / 未宣称

- ⛔ **未认领新 EXT 编号** ⇒ `last_ack` **保持 EXT-017**。
- ⛔ **`克隆说话人` 仍不生效** —— 依赖 pyannote 旁路，而旁路**尚未接线**
  ⇒ 选克隆时回落到预设 A。**已在 USER_GUIDE 与本文件如实写明**，不宣称已实现。
- ⛔ **浏览器端人工验收仍未做**（本机**无 playwright、无 Chrome** ⇒ 只有 Edge 126）
  ⇒ 插件侧改动**只做到 node 沙箱级的行为验证**，
  **不宣称**「已在真浏览器里点过面板」。
- ⛔ **端到端仍不实时**（TTS 稳态 RTF **1.0022**）⇒ **TTS 提速仍是上线的唯一前置**。
- ⛔ **tabCapture 生产路径仍未人工实测**（需真实用户手势）。
- ⛔ 本轮**未跑任何真实推理、未占 GPU/NPU、未创建/未回收机器锁**
  （`shared/MACHINE_LOCK` 属 `tts` 模块 ⇒ 未动）。
- ⛔ **未 kill 用户自己的桥接进程**（PID 5464，`ext.bridge --real --pipeline --port 8765`）。
- ⛔ **未改任何引擎文件**（ASR/MT/TTS 均未动）；`ext/engine_runtime.py` **未改**
  （只新增了轻量的 `ext/config.py::LANG_CODES`，与它的两张表键集合一致）。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在）。
