# §13 明细 —— P2 待办收口：`captureMode` 上报进 stats + 扩展图标

> **来源**：EXT-016 要求「长日志、逐条明细、大表格写到 `status/notes/<章节号>.md`，
> STATUS 里只放结论、数字和链接」。
> 本文件是 **STATUS §13** 的明细附件（2026-10-30 22:13 → 22:27）。
> ⚠️ **reviewer 未下发 EXT-018** ⇒ 本轮**未认领新编号**，`last_ack` 保持 EXT-017。

---

## 0. 闸门与交叉证据

`tools/next_instruction.py --json` → **exit 1**（`already_executed`，latest=EXT-017 / last_ack=17）⇒ **无新纠偏指令**。

| 证据 | 实测 |
|---|---|
| `git status --porcelain` | **空**（树干净） |
| HEAD | `f8c7510`（2026-10-30 21:11:14，标题含 EXT-016/EXT-017）的 `last_ack: EXT-017` == 工作区 |
| STATUS 正文 | 含 §1~§12 ⇒ 一致 |
| EXEC_LOG | 上一轮记录在（`## 2026-10-30 20:33 → 21:06 — EXT-016 收口…`） |
| 产物 | `.tmp/p1_ext009/`（dub 22 wav / accel 3 wav / margin.json 27 565 B / p1_report.json 44 453 B）+ `.tmp/p1_pipe/`（dub 22 wav / margin.json 27 910 B / p1_report.json 44 668 B）+ `.tmp/ext008_bench/interference.json` 1 114 B —— 均齐全 |
| 纠偏文件 | mtime 2026-10-30 19:02、9 689 B、`^## EXT-` 条目 **5 条**（EXT-013~017）⇒ **无 EXT-018** |

⇒ **闸门 exit 1 是「真跳过」**（无新指令，上一轮确实做完）。
但 **EXT-014 ②**（常设巡检规则）：「`last_ack` 追平后，只要还有未完成项，就自己继续做，不要空转」
⇒ 本轮做 STATUS 里**明列且不需要 reviewer 决策**的 P2 待办两项。

---

## 1. `captureMode` 上报进 stats（EXT-005 ① 的前置）

### 1.1 问题

插件侧**早就知道**自己走的哪条抓流路：

| 位置 | 变量 | 取值 |
|---|---|---|
| `extension/offscreen.js` | `state.captureMode` | `'tabCapture'` / `'getDisplayMedia'` |
| `extension/player.js` | `upState.captureMode` | 同上 |

但此前**只在插件内部 / 弹窗里显示**（`popup.js` 的「抓流方式：…」）
⇒ 服务端 `stats()` 与落盘的 `margin.json` **根本没有这个字段**
⇒ reviewer 拿到 P1 产物时**无法判断**「这轮跑的是生产路径(tabCapture)还是兜底路径(getDisplayMedia 兜底)」
⇒ 只能人工翻日志 —— 正是 EXT-005 ① 想避免的「宣称已验证但没法证明」。

### 1.2 改动（4 个文件）

| 文件 | 行数 | 改了什么 |
|---|---|---|
| `extension/player.js` | +7 | `hello` 消息带 `capture_mode: upState.captureMode`。player 的抓流在 WS 连接**之前**完成 ⇒ 那一刻已知**实际值**。 |
| `extension/offscreen.js` | +35 | 新增 `reportCaptureMode()`，抓流成功后**补发** `capture_info`。offscreen 的 `hello` 在 `connectWs` 里发、**抓流在其之后** ⇒ hello 时 `state.captureMode` 仍是 null ⇒ 只能补报。 |
| `ext/bridge.py` | +77 | `Session.note_client()` 记 `capture_mode` / `client_source` / `source_rate`；`stats()` 输出三字段；`_dump_margin()` 落盘 `margin.json` 也输出三字段；新增 `capture_info` 消息分支；`hello_ack` **回显**服务端记到的 `capture_mode`（**向后兼容**：旧客户端不受影响）。 |

### 1.3 关键设计约束

- **取值白名单**：只接受 `'tabCapture'` / `'getDisplayMedia'`，**其它一律记 `None`**
  （不静默接受未知字符串，避免报告里出现含义不明的字段值）。
- **没上报就是 `null`，绝不臆造 `'tabCapture'`** ⇒ 这条是「证据规则」的直接落地。
- **报的是实际值、不是计划值**：`sw.js` 里的 `captureMode` 是**计划值**
  （拿不到 stream id 时会被降级成 `getDisplayMedia`）⇒ 插件上报的一律取
  `state.captureMode` / `upState.captureMode`（**拿到流的那一刻**才赋的值）。

---

## 2. 扩展图标

`extension/manifest.json` 此前**没有 `icons` 字段** ⇒ 工具栏显示的是默认灰块。

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/make_icons.py`（新增）—— 纯标准库 `zlib` + `struct` 写 PNG，**无第三方依赖、可复现**（本机 venv 无 PIL） |
| 图案 | 深色圆角方块（#161b22）+ 三条浅蓝声波竖条（#58a6ff，中间最高）⇒ 一眼能认出是「音频/配音」类插件，16px 仍可辨认 |
| 产物 | `extension/icons/icon16.png`（116 B）/ `icon32.png`（152 B）/ `icon48.png`（180 B）/ `icon128.png`（443 B） |
| manifest | 挂 `icons` + `action.default_icon`（16/32/48/128） |

⚠️ **`manifest.key` 绝不能动**（扩展 ID 由 key 决定）⇒ 实测
`resolve_extension_id()` = **`kekgmfkijphpfndbbpakjaokamkeooib`**
（与 EXT-017④ 的 Origin 校验一致，**未变**）。

---

## 3. 自测：`tests/test_ext018_capture_mode_stats.py`（38 项）

**行为级**（真起桥接服务 + 真 WebSocket，**回声模式、不跑推理、不占 GPU/NPU**）：

| 组 | 断言 |
|---|---|
| ★ 对照组 | 不带 `capture_mode` 的 hello ⇒ stats 里必须是 `None` ⇒ **证明服务端不会自己编一个 `'tabCapture'`**（防假通过的关键） |
| ★ 实验组 | hello 带 `capture_mode` ⇒ stats 回包 `'tabCapture'`；`hello_ack` 回显一致；`source_rate` 一并记下 |
| ★ 第三条路径 | hello 后补发 `capture_info` ⇒ stats 拿到 `'getDisplayMedia'`（offscreen 的真实时序） |
| ★ 白名单 | 未知取值被丢弃 ⇒ stats 里仍是 `None` |
| B 落盘 | `_dump_margin` 写出的 `margin.json` 带 `capture_mode='tabCapture'` + `client_source` |
| C 插件契约 | hello 带 `capture_mode`；补发 `capture_info`；报的是**实际值**而非 `sw.js` 的**计划值**（降级陷阱防护）；服务端认 `capture_info`；`stats()` 与落盘都输出 |
| D 图标 | `icons` 字段存在；四个文件**真实存在且是合法 PNG**（尺寸对、非 0 字节）；`manifest.key` 未变（扩展 ID 不变）；生成脚本在库 |

★ **反证（区分力验证）**：把 `note_client` 改成「不记 capture_mode」⇒ 该套自测
**34 PASS / 4 FAIL、rc=1** ⇒ 断言**不是恒真**，能真正抓到回归（随后已还原，
`git diff --stat ext/bridge.py` = 77 insertions）。

★ **JS 语法**：`node --check` 对 player.js / offscreen.js / popup.js / sw.js **全部通过**。

---

## 4. 全套自测

**14 套 / 777 PASS / 0 FAIL**（全 rc=0，逐套取**真实退出码**、不用 pipe）：

```
test_echo_roundtrip             ::  11 PASS / 0 FAIL
test_ext009_adaptive_speed      ::  57 PASS / 0 FAIL
test_ext010_pipeline            ::  23 PASS / 0 FAIL
test_ext011_thread_limits       ::  29 PASS / 0 FAIL
test_ext012_user_guide          ::  75 PASS / 0 FAIL
test_ext013_compare             ::  51 PASS / 0 FAIL
test_ext013_cpu_watch           ::  25 PASS / 0 FAIL
test_ext016_compression         ::  39 PASS / 0 FAIL
test_ext017_user_report         :: 108 PASS / 0 FAIL
test_ext018_capture_mode_stats  ::  38 PASS / 0 FAIL   <- 本轮新增
test_ext_browser_contract       :: 102 PASS / 0 FAIL
test_ext_selfcheck              :: 103 PASS / 0 FAIL
test_next_instruction           ::  19 PASS / 0 FAIL
test_p1_plumbing                ::  97 PASS / 0 FAIL
合计                            :: 777 PASS / 0 FAIL
```

---

## 5. ★ 附带：用户在 22:31:29 双击了桌面快捷方式

进程链：`pythonw.exe tools/ext_launcher.py`（PID 30872，父 PID 24740 **已退出**）
⇒ 子进程 `python.exe -m ext.bridge --host 127.0.0.1 --port 8765 --delay 10.0 --real --target-lang zh --pipeline`（PID 5464）。

⇒ **这不是自测拉起的**（自测只用 `--echo` 与桩命令）⇒ 是**用户本人在试用**。
按铁律 **未 kill、未回收**（它正持有 GPU/NPU 做真实推理，不能打断用户操作）。

### 5.1 意外收获：在真实运行的真实三引擎桥接上验证了本轮新字段

连的是**用户正在跑**的 8765 真实桥接：

| 探测 | 实测回包 |
|---|---|
| hello 不带 capture_mode | `hello_ack.capture_mode = None`；`stats.capture_mode = None`；`stats.client_source = 'probe'` |
| hello 带 `capture_mode='tabCapture'` | `hello_ack.capture_mode = 'tabCapture'`；`stats.capture_mode = 'tabCapture'` |

⇒ **新字段在真实部署里确实生效**（不只是自测里生效）。

### 5.2 顺带确认 EXT-017② 在用户真实一次启动里成立

`%LOCALAPPDATA%\LiveDubEXT\bridge.log`（23 584 B / 2026-10-30 22:32）实测：

- `引擎预热完成：成功 3/3，总耗时 25.1 秒`（MT 2.5 s / TTS 14.3 s / ASR 先完成）
- `✅ 模型加载完成（ASR/MT/TTS 就绪，耗时 25.09 秒）` @ 22:32:06
- `监听 ws://127.0.0.1:8765（echo=False, D=10.0s，pipeline=True）`

⇒ ★ **「start 后能看到加载进度并最终显示 TTS 就绪」在用户真实一次启动里成立**（日志证据，非桩）。

---

## 6. ⛔ 明确未做 / 未宣称

- ⛔ **tabCapture 生产路径仍未人工实测**（需真实用户点一次扩展图标；本机只有 Edge 126、无 Chrome）
  ⇒ 本轮只把「**可核对性**」准备好了，**不宣称已验证**。
- ⛔ 端到端仍不实时（TTS 稳态 RTF **1.0022**）⇒ **TTS 提速仍是唯一前置**。
- ⛔ **本轮未跑任何真实推理、未占 GPU / NPU**（全程 CPU 侧 + 回声模式）。
- ⛔ **未改任何引擎文件**（ASR / MT / TTS 均未动）。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未改、未入库**（`.gitignore:34`；`git log --all` 查无此文件 ⇒ 从未入库）。

### 机器锁

本轮**未创建锁、未跑任何推理、未占 GPU / NPU**。
巡检期间 `shared/MACHINE_LOCK` 存在（78 B / 2026-10-30 21:16:56），内容 = **`tts` 模块** PID 15900
⇒ `probe_pid_alive(15900)` = **False**（该 PID 已死 ⇒ 陈旧锁）⇒ 但属**他人模块**所有，
且实时字幕 App 模块会自行回收 ⇒ **本轮未创建 / 未删除 / 未回收**。

### `last_ack`

**保持 EXT-017 不变** —— 本轮**未认领任何新的 EXT 编号**（reviewer 未下发 EXT-018）⇒
不自行占用 reviewer 的编号命名空间。
