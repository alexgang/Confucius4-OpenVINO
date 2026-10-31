# §16 T-4 —— 目标语言**真正生效**（逐条明细）

> 本文件是 `status/STATUS_EXT.md` §16 的**明细全文**（EXT-016 写作规则：
> 长日志 / 逐条明细写到 notes，STATUS 里只留结论、数字和链接）。

## §16.0 依据与触发方式

* 闸门 `tools/next_instruction.py --json` → **exit 1**
  （`reason=already_executed`，`latest=EXT-017`，`last_ack=17`）
  ⇒ **没有新的 EXT 纠偏指令**（另把闸门解析对着 `CORRECTIONS_EXT.md`
  **原始文件**核过一遍：条目只有 EXT-013~EXT-017，**不存在比 EXT-017 更新的编号**
  ⇒ exit 1 是真的，不是解析漏掉）。
* 按 **EXT-014 ②**（常设规则：「`last_ack` 追平后，只要还有未完成项，
  就自己继续做，不要空转」）⇒ 继续 STATUS「未完成纠偏清单」里的 **P2 待办**。
* ⚠️ **未认领新 EXT 编号**（reviewer 未下发新纠偏）
  ⇒ **`last_ack` 保持 EXT-017**，不自行占用 reviewer 的编号命名空间。
* 本轮**未跑任何真实推理、未占 GPU/NPU、未创建/未回收机器锁**
  （全程 CPU 侧 + 桩引擎 + node 沙箱）。

## §16.1 发现的缺陷：T-3 只修了一半 —— 「目标语言」仍是死控件

T-3（§15）把插件面板的 4 个「死控件」接上线了。但复查 §15 的结论时发现
**「目标语言」这一项只修了一半**：

| 环节 | T-3 之后 | 本轮之前（缺陷） |
|---|---|---|
| popup 存语言码（zh/en/ja/ko） | ✅ 已修 | — |
| 语言进 `start` 消息 → offscreen → hello | ✅ 已修（**offscreen 这条链路**） | — |
| 服务端**记录** `client_target_lang` | ✅ 已修 | — |
| ★ **服务端用这个语言去翻译/合成** | ❌ | **没做** |

⇒ **面板上选日语，出来的还是服务端的语言** ⇒ 「目标语言」**依然是死控件**。

### 根因（读代码得到，不是「看代码觉得像」）

1. `ext/engine_runtime.py` 的 `RuntimeEngine.target_lang` 是**构造时定死**的
   （`load_runtime_engine(target_lang=args.target_lang)`，即服务端 `--target-lang`）；
2. `RuntimeEngine.mt()` / `.tts()` **不接受**按调用的语言参数
   ⇒ 调用方**没法**覆盖 ⇒ 只能改 `self.target_lang`（全局、且有竞态）；
3. `ext/bridge.py` 的 `Session._process_segment()`（串行）与
   `PipelineSession._stage_mt()/_stage_tts()`（**生产默认走这条**）
   调的都是 `self._engine.mt(text)` / `.tts(text, voice=...)`
   ⇒ **从不传语言** ⇒ 面板的选择到不了引擎。

### ★ 顺带发现的第二个缺口：`player.js` 的 hello 没带语言/音色

* `extension/offscreen.js` 的 hello 带 `target_lang` / `voice`（T-3 加的）；
* 但 `extension/player.js` 的上行 hello **没有**这两个字段
  ⇒ **player 这条上行链路**（getDisplayMedia 兜底路径）上，
  服务端**根本收不到**面板上的选择 ⇒ 该路径上语言/音色**完全丢失**。

### ★ 为什么引擎侧本来可以支持（查过对方接口，没改对方文件）

* Hy-MT2：`translator.py` 的 `translate(self, text, tgt, ...)` ⇒ **按调用传 tgt** ✅
* Qwen3-TTS：`tts_engine.py` 的 `stream(..., language=...)` ⇒ **按调用传 language** ✅
⇒ **只需在本模块的适配层加一个可选参数**（不改任何引擎文件，符合 EXT-001 铁律）。

## §16.2 修复（最小、范围可控）

### ① 适配层支持**按调用覆盖**目标语言（`ext/engine_runtime.py`）

* `RuntimeEngine.mt(text, *, target_lang=None)` / `.tts(text, *, voice, target_lang=None)`；
* `mt_target(target_lang=None)` / `tts_language(target_lang=None)`
  —— 传了就用（**覆盖**），不给则沿用构造时的默认（**向后兼容**）；
* ⚠️ 非法码**照旧抛 `EngineNeedsChange`**（绝不静默回落）——
  与 EXT-006 的既有守卫一致（`test_ext_selfcheck.py` 的断言仍绿）。
* 新增 `applied_target_lang`：**最后一次真正用于翻译/合成**的语言码。

### ② 服务端真的把面板语言用起来（`ext/bridge.py`）

* `Session._effective_target_lang()`：客户端报了**白名单内**的码 ⇒ 用它；
  没报 / 非法码 ⇒ `None`（沿用引擎默认，**不臆造**）。
* `Session._mt_with_lang()` / `._tts_with_lang()`：**按句**把语言传给引擎。
  ⚠️ **向后兼容**：引擎的 `mt`/`tts` 若**不接** `target_lang` 关键字
  （老适配层 / 自测桩）⇒ 捕获 `TypeError` ⇒ **回落旧调用**，并
  **如实**记 `applied_target_lang=None`（**不假装生效**）+ 打日志。
* **串行路径** `_process_segment()` 与**流水线路径**（生产默认）
  `_stage_mt()` / `_stage_tts()` **同一口径**。
* `stats()` 与落盘的 `margin.json` 新增 `applied_target_lang`
  ⇒ reviewer 可直接比对「面板选的」与「实际生效的」。

### ③ 插件侧把语言/音色真正报上去（`extension/player.js` / `popup.js`）

* `player.js` 新增 `targetLang` / `voicePref` 两个模块级状态；
  `boot()` 从 `chrome.storage.local` 读出来并**归一**；
  `storage.onChanged` 监听 ⇒ 运行中改也跟上；
* `player.js` 的上行 hello **带上** `target_lang` / `voice`
  ⇒ **补上 player 这条链路上的丢失**；
* `player.js` / `popup.js` 各自新增 `normalizeVoice()`，
  `normalizeLang()` 两边**口径必须一致**（自测会比对别名表）；
* `popup.js` 的音色也走 `normalizeVoice()` ⇒ 不把非法值发给服务端。

## §16.3 验证

### ① 引擎侧（真起 `RuntimeEngine`，**不加载权重**）

* `mt_target('ja')` ⇒ `'ja'`、`tts_language('ja')` ⇒ `'Japanese'`（覆盖生效）；
* 对照组：不传 ⇒ 沿用构造时的 `'en'` / `'English'`；
* 对照组：非法码 `xx`/`Chinese`/`''`/`jp` ⇒ **抛异常**（不静默回落）。

### ② 服务端行为级（桩引擎，**不触任何设备**）

* 实验组：客户端报 `'ja'` ⇒ **MT 收到 `'ja'`**、**TTS 收到 `'ja'`**
  （不是服务端默认的 `'en'`）⇒ `applied_target_lang='ja'`；
* 对照组：不报语言 ⇒ 引擎**不带** `target_lang`（沿用默认），
  `applied_target_lang` 保持 `None`（**不臆造**）；
* 对照组：报非法码 ⇒ **不传给引擎**（否则会把引擎打挂）；
* 对照组：**老引擎**（不接 `target_lang` 关键字）⇒ **不崩**，
  回落旧行为，且 `applied_target_lang` 记 `None`（不假装生效）；
* 流水线路径（生产默认）同样验证通过。

### ③ 真起桥接服务（回声模式 + 真 WebSocket）

* `stats` 里有 `client_target_lang='ja'`、`applied_target_lang` 字段存在；
* 回声模式没跑引擎 ⇒ `applied_target_lang` 为 `None`（**不臆造**）；
* `hello_ack` **结构不变**（向后兼容，不破坏旧客户端）。

### ④ 插件侧（node 沙箱跑 `player.js` 的**真实函数**）

`tests/t4_lang_harness.js` 从**真实的 `player.js` 源文件**里
**原样抽出** `normalizeLang` / `normalizeVoice` / `LANG_ALIASES`
（按花括号配对抽取，不是正则截半），放进带桩的沙箱（`vm`）里执行
⇒ **验的是真代码，不是复刻品**。

⇒ **28 PASS / 0 FAIL**（harness 自报，rc=0）。

### ⑤ ★ 反证（harness 必须有区分力）

★ **反证①（服务端侧）**：把 `bridge.py` 里的接线拆掉
（`_mt_with_lang` → `self._engine.mt(text)`，`_tts_with_lang` → `self._engine.tts(...)`）
⇒ 拷到临时目录跑整套自测：

```
结果：46 PASS / 4 FAIL / 共 50   rc=1
FAIL 明细：
 - ★★★ MT 真的收到了 'ja'（不是服务端的默认 'en'） — 实测 mt_calls=[('测试原稿', None)]
 - ★★★ TTS 真的收到了 'ja' — 实测 tts_calls=[('translated-to-en', 'A', None)]
 - ★★★ applied_target_lang 如实记成 'ja' — 实测 None
 - ★★ stats 里的 applied_target_lang = 'ja' — 实测 None
```

★ **反证②（插件侧）**：从 `player.js` 的 hello 载荷里去掉
`target_lang` / `voice` ⇒ 传给 harness 一份**改坏的副本**：

```
harness 结果：24 PASS / 4 FAIL / 共 28   rc=1
FAIL 明细：
 - ★★★ player.js 的 hello 载荷里含 target_lang
 - ★★★ player.js 的 hello 载荷里含 voice
 - ★★ player.js 的 hello 用的是归一后的 targetLang
 - ★★ player.js 的 hello 用的是归一后的 voicePref
```

⇒ **两组反证都让断言全红 rc=1** ⇒ 断言**不是恒真**（有区分力）。

### ⑥ 完整回归

**17 套 / 908 PASS / 0 FAIL**（全 rc=0，逐套实测真实退出码）：

```
echo_roundtrip 11 / ext009 57 / ext010 23 / ext011 29 / ext012 75 /
ext013_compare 51 / ext013_cpu_watch 25 / ext016_compression 39 /
ext017_user_report 108 / t1_capture_mode 38 / t2_port_guard 28 /
t3_dead_controls 53 / ★ t4_target_lang_effect 50 /
browser_contract 102 / selfcheck 103 / next_instruction 19 / p1_plumbing 97
```

★ 三套**明文要求**的自测单独确认退出码：
`test_ext_selfcheck.py` rc=0 / `test_echo_roundtrip.py` rc=0 /
`test_next_instruction.py` rc=0。

★ 闸门仍正常：`next_instruction.py --json` → exit 1 / `latest=EXT-017`
⇒ **没弄坏闸门**。

## §16.4 产物（文件数 / mtime / 字节数）

| 产物 | 文件数 | mtime | 字节数 |
|---|---|---|---|
| `tests/test_t4_target_lang_effect.py` | 1 | 2026-10-31 07:29 | 22 719 |
| `tests/t4_lang_harness.js` | 1 | 2026-10-31 07:29 | 12 883 |
| `status/notes/sec16_t4_target_lang_effect.md` | 1 | 2026-10-31 07:40 | 13 069 |
| `USER_GUIDE.md` / `extension/USER_GUIDE.md` | 各 1 | 2026-10-31 07:30 | 各 16 793（逐字节一致 ✅ `cmp` 通过） |

## §16.5 涉及修改的文件

| 文件 | 改动 |
|---|---|
| `ext/engine_runtime.py` | `mt()`/`tts()` 支持 `target_lang` 覆盖；`mt_target()`/`tts_language()` 支持覆盖；新增 `applied_target_lang` |
| `ext/bridge.py` | `Session._effective_target_lang()` / `_mt_with_lang()` / `_tts_with_lang()`；串行 + 流水线路径都真正用上面板语言；`stats()`/`margin.json` 新增 `applied_target_lang` |
| `extension/player.js` | 新增 `targetLang`/`voicePref` 状态 + `normalizeLang`/`normalizeVoice`；`boot()` 读设置；`storage.onChanged` 跟随；上行 hello 带 `target_lang`/`voice` |
| `extension/popup.js` | 新增 `normalizeVoice()`；音色存/读/显示都走归一 |
| `USER_GUIDE.md` / `extension/USER_GUIDE.md` | 补 T-4 修正说明（含「实际生效」字段与「会话中途改需重新开始」的诚实提示）；两份保持**逐字节一致** |
| `tests/test_t4_target_lang_effect.py` | **新增**（50 项，五组） |
| `tests/t4_lang_harness.js` | **新增**（28 项，四组） |

## §16.6 ⛔ 明确未做 / 未宣称

- ⛔ **未认领新 EXT 编号** ⇒ `last_ack` **保持 EXT-017**。
- ⛔ **未跑真实推理** ⇒ 「选日语 ⇒ 真的译成日语」这条**没有**在真实
  ASR/MT/TTS 上端到端跑过（那要占 GPU/NPU + 机器锁，且 TTS 模块正在用锁）。
  ⇒ 本轮验证到的是「**语言确实被传到了引擎的调用点，且引擎按它映射**
  （MT `tgt` / TTS `language`）」+「**面板的语言确实到达了服务端**」，
  **不宣称**「真机听感已验证」。
- ⛔ **浏览器端人工验收仍未做**（本机**无 playwright、无 Chrome**，只有 Edge 126）
  ⇒ 插件侧只做到 node 沙箱级行为验证，**不宣称**真浏览器链路已验证。
- ⛔ **`克隆说话人` 仍不生效**（依赖 pyannote 旁路 ⇒ 未接线 ⇒ 回落预设 A）。
- ⛔ **会话中途改语言/音色不会即时生效**（已建立的 WS 连接不会重发 hello）
  ⇒ 已**如实写进 USER_GUIDE**，提示用户重新点「开始」。
- ⛔ 端到端仍不实时（TTS 稳态 RTF **1.0022**）⇒ TTS 提速仍是上线的唯一前置。
- ⛔ tabCapture 生产路径仍未人工实测（需真实用户手势）。
- ⛔ 本轮**未创建/未回收机器锁**：
  - 开工时 `shared/MACHINE_LOCK` 内容为 `module: tts / pid: 15788`
    ⇒ ctypes `OpenProcess`+`GetExitCodeProcess` 探得 PID 15788 **ALIVE**
    ⇒ **未创建、未动、未回收**（锁属他人模块，不能碰）。
  - 收尾复核（2026-10-31 07:40）：`shared/MACHINE_LOCK` **已不存在**
    （`ls shared/` 实测只有 6 个 `NOTICE_*.md`）⇒ 属**他人自行释放**，
    **不是本轮回收的**。
- ⛔ **未 kill 任何进程**：
  - 开工时用户自己的桥接 PID 5464（`ext.bridge --real --pipeline --port 8765`）
    探得 **ALIVE** ⇒ 未打断（它正做真实推理）。
  - 收尾复核（07:40）：`psutil` 扫不到 `ext.bridge` 进程、`netstat` 查
    8765/8766 **无监听** ⇒ 该桥接**已自行退出**，
    **不是本轮 kill 的**（本轮全程未执行任何 kill）。
- ⛔ **未改任何引擎文件**（ASR/MT/TTS 的对方模块一行未动；
  只在本模块的**适配层** `ext/engine_runtime.py` 加了可选参数）。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在）。
