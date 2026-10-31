# §17 明细 —— EXT-024 收口（下行路由 / 会话生命周期 / 启动器 / 段级日志 / 状态条 / 模式 / 语言）+ EXT-023

> **来源**：EXT-024 [BLOCKING] 2026-10-31 09:05 + EXT-025 [NORMAL] 2026-10-31 10:37（RESUME）
> 本文件是 **STATUS §17** 的明细附件（2026-10-31 15:20 → 15:55）。
> **认领 EXT-024 与 EXT-025 两个编号** ⇒ `last_ack` 推进到 **EXT-025**。

---

## 0. 闸门与本轮范围

`tools/next_instruction.py --json` → **exit 0**（`action=execute`，latest=**EXT-025** / last_ack=17 / n_entries=9）
⇒ **有未执行的新指令** ⇒ 本轮执行。

⚠️ **开工时工作区已有一批未提交的 EXT-024 改动**（上一轮被中断留下的）：
`git status` 显示 26 个文件被改 + `tests/test_ext024_dl_routing.py`、`tests/ext024_link_harness.js`、
`tests/smoke/` 为未跟踪。
⇒ 本轮**接手这批改动**，逐项核对 A–G 是否真的落地，补齐缺口，并修掉它带来的 3 处自测回归。

★ **EXT-024 与 EXT-025 的分工**：
* **EXT-024 [BLOCKING]** = 主任务（A–G 七项 + 验收）；
* **EXT-025 [NORMAL]** = RESUME（额度重置，从 last_ack 继续）⇒ 本轮一并认领。

---

## 1. A 项 —— 修下行（**EXT-024 的根因**）

### 1.1 根因（reviewer 已定位，本轮复核确认）

`extension/player.js` 开了**两条** WS：

| 连接 | 旧行为 | 后果 |
|---|---|---|
| `connectBridge(..., 'player')` | 有 `onmessage`（收 tts/echo） | 但**这条连接不上行**，服务端它的会话**永远不产段** |
| `startUplink()` 的 `upState.ws` | **只发 pcm，没有 onmessage** | 服务端把这条会话产出的 `tts` **全发到这里** ⇒ 被浏览器丢弃 |

⇒ **配音与字幕全都丢了**；用户只听到 DelayNode 延迟的原声（duck 仅 −15 dB）
⇒ 与用户 10-31 实测描述（「仅仅是原来的声音延迟重放，也没有字幕和翻译文本」）**完全一致**。

### 1.2 修法：**服务端按 token 广播**（reviewer 给的两个选项之一）+ 插件两条连接都挂 onmessage

* `ext/bridge.py`：
  * 新增 `ConnectionRegistry`（连接登记表：conn_id → websocket/token/role/session）；
  * 新增 `classify_role(msg)` —— 识别 `'player'` / `'uplink'`，
    ⚠️ **未报角色的连接一律不当 player**（否则等于退回旧错误行为）；
  * 新增 `downlink_targets(token, origin_conn_id=)` —— 目标 = 「产生它的连接」+「同 token 的 player 连接」；
  * `_broadcast_task(task)` —— 把 `tts`/`echo` 发给这些目标；
  * ⚠️ **没有 registry 时退回旧行为**（只发本连接）⇒ 单连接探针/自测不受影响。
* `extension/player.js`：
  * `upState.ws` **加上 `onmessage`** ⇒ 复用同一个 `handleBridgeMessage(m)`（不重复实现）；
  * 按 `id` 去重（`seenDubIds`，容量 500）—— 服务端可能把同一条广播给两条连接；
    ★ **去重只影响「排程一次」，计数也只加一次**（`dubDelivered` 不重复计）。
* `extension/offscreen.js` + `extension/sw.js`：
  * 旧实现 offscreen 只**计数不转发** ⇒ 走 offscreen 抓流时 player 页**永远收不到 tts**；
  * 现在 offscreen 把下行 `forwardToPlayer(m)` ⇒ 经 SW 的 `runtime` 广播 / Port 通道送到 player.html。

### 1.3 ★ 时间轴口径（reviewer 明文：「要写清楚 t_start 用的是哪个时间轴」）

**t_start 的时间轴 = 上行链路的采样时间轴**：
* `t_start = s0 / 16000`，`s0` = 该段第一帧在**上行 PCM 里的累计采样数**
  ⇒ **采样点 0 = 上行链路收到的第一帧音频**；
* 这个轴**与墙钟无关**（EXT-001 A 节）、**与服务端 t0 无关**；
* 插件按 **`t0_player + t_start + D`** 排程 ⇒ 与原声**同轴**
  （上行采样点 0 与原声起点来自同一路抓流 ⇒ 二者天然对齐，配音与原声按同一口径错开 D 秒）。

⚠️ **诚实的已知偏差**：插件 `t0_player`（AudioContext 基准，由首帧 `inSamples` 反推）与
服务端 `t0`（会话建立时刻）**不同源**（§6.4.1 已记录）⇒ 该**常量偏差**会平移服务端的
`lag_est_sec` 估计；但**排程本身**用的是插件自己的同一个 `t0_player`
⇒ 偏差在两边同时抵消，**不影响配音与原声的相对关系**；滞后的主导项是管线 backlog（83.18 %，§6.4.3）
⇒ 该偏差是二阶效应。**不宣称「精确对齐」。**

★ **落盘**（铁律「没落盘的东西不能写『已交付』」）：
* `tts` 消息新增字段 `t_start_axis = "uplink_sample_index"`（随消息下发到客户端）；
* `margin.json` 新增 `t_start_axis` + `t_start_axis_note`（reviewer 可直接 `json.load` 核对）。

---

## 2. B 项 —— 会话生命周期（EXT-024 B）

* **连接关闭 ⇒ 清 holder**（`_release_session`）：
  * 旧实现：`_register_session` 只在 holder 为空时登记，而 `finally` 里**从不清 holder**
    ⇒ 用户日志里 22:34:22–22:37:14 每条新连接都打「已有活跃会话 ⇒ 本连接不顶替」
    ⇒ stats/HUD/popup 读到的**都是旧会话的数据**；
  * 现在：连接关闭 ⇒ 若 holder 里的 session 就是本会话 ⇒ 置空，
    并归档到 `holder["last_session"]`（保留统计供事后核对），且**停掉流水线线程**。
* **只允许一个 uplink 会话，新 uplink 接管时停掉旧的流水线**：
  * 靠 `role` 区分：`role == 'uplink'` 且旧会话**也是 uplink** ⇒ **接管**（关旧会话的流水线）；
  * 其它情况（player 连接 / 探针）⇒ **不顶替**（保留缺陷 15 的语义：避免落盘空统计）。
* **产出会话与 player 会话分离**：`_producer_session(holder, registry, token)`
  ⇒ stats / margin.json 优先读**真正产出段的那条**（uplink 会话）
  ⇒ 否则 player 的空会话会让**段数恒为 0**（正是用户 10-31 实测时 popup 段数全 0 的原因）。
* **面板设置双向同步**（`_propagate_client_settings`）：
  * 上报 hello 的可能是 player 连接，而产出段的是 uplink 会话
    ⇒ 若不传播，uplink 的 `client_target_lang` 是 None ⇒ 翻译按服务端启动参数走
    ⇒ **用户在面板上选的中文不生效**；
  * 现在同 token 的所有会话**双向同步「非 None」的语言/音色**（不覆盖对方已报的值）。

---

## 3. C 项 —— 启动器：端口被占时**不加载模型**、日志不交错

* `tools/ext_launcher.py`：
  * **无条件**先查 PID 文件里的活实例（`_alive_instance` → ctypes `OpenProcess`+`GetExitCodeProcess`，
    探测失败**视为存活**）⇒ 命中 ⇒ 直接拒，提示
    **「已有桥接服务在运行（PID x，端口 y）」**，**不启动子进程、不加载模型、不动日志**；
  * PID 文件无活实例但**端口被占** ⇒ 判定为**别的程序占用** ⇒ 同样**在起子进程之前**退出
    ⇒ 用户**不会白等 20–40 秒**（旧行为：预热 24 s 后才 bind 失败、整屏 traceback）；
  * **日志交错**：每行加 `[#<实例号> pid=<PID>]` 前缀（实例号 = 启动时刻到秒）
    ⇒ 用户 10-31 的现场证据里**三个 bridge 实例交错写同一个 bridge.log** ⇒ 现在可分辨。

---

## 4. D 项 —— 段级日志（`_log_segment`）

旧实现整个会话**没有一行段级日志** ⇒ reviewer 无法判断「有没有出过段」「下发给了谁」。

现在每段一行：
`段 <id> | t_start=<x> t_end=<y> | ASR='前 30 字' | MT='前 30 字' | TTS=<秒>s | 下发到=<角色,...>`

⚠️ 字段缺失写 `—`，**绝不编**。

★ 实测（回声/桩引擎，真实跑通）：
```
[bridge 15:30:06] 段 seg_0 | t_start=0.000 t_end=15.170 | ASR='テスト原稿' | MT='translated' | TTS=0.50s | 下发到=本连接
[bridge 15:30:07] 段 seg_242720 | t_start=15.170 t_end=20.000 | ASR='テスト原稿' | MT='translated' | TTS=0.50s | 下发到=本连接
```

---

## 5. E 项 —— player 常驻链路状态条

* `extension/player.html` 加 `#linkBar`（常驻）+ `#linkReason`（原因行）；
* `extension/player.js` 的 `metrics.link` 记：已收音频秒数 / ASR 段 / MT 段 / TTS 段 /
  **已下发到 player 段数** / 当前滞后 / 各环最后活动时刻；
* `diagnoseLink(link, nowMs)` 是**纯函数**（不碰 DOM）⇒ 可被 node 沙箱直接验证；
* **15 秒阈值**（reviewer 明文 `LINK_STALL_SEC = 15`），任何一环为 0 超过 15 s ⇒ **红字写明原因**：
  * WS 未连 ⇒ 桥接服务没启动 / 端口不通；
  * 回声模式 ⇒ 醒目提示（**不是**真实翻译配音）；
  * 引擎未就绪 ⇒ 正在加载模型，等 20–40 秒；
  * 没有音频轨 ⇒ tabCapture 没抓到声音；
  * 收到音频但没出段 ⇒ 查 bridge.log 的段级日志；
  * 有 TTS 段但下发 0 ⇒ **下行路由断了**。

★ `已下发到 player 段数` 是 EXT-024 的**关键证据**：只有它 > 0 才说明下行真的通了。

---

## 6. F 项 —— popup 显示真实/回声模式 + 未就绪禁用「开始」

* `hello_ack` 新增 `mode`（`'real'` / `'echo'`）、`engines_ready`、`pipeline`（**只增不改**旧字段 ⇒ 向后兼容）；
* `/status` 输出 `mode` / `engine_state`（`'loading'`/`'ready'`/`'partial`）/`engine_loaded`/`engine_failed`；
* `popup.js` 的 `startGate(st)` 返回 `{ok, reason}`：
  * 桥接没起来 ⇒ 不能开始（写明原因）；
  * **回声模式 ⇒ 不能开始**（★ 回声不是真实翻译配音，用户会误以为「翻译没出声音」⇒ 宁可拦住并说清楚）；
  * 真实引擎但未就绪（`loading`/`partial`）⇒ 不能开始（写明哪个引擎失败）；
  * 真实引擎 + 就绪 ⇒ 可以开始；
* ⚠️ `engines_ready` **诚实性**：绝不因为 `mode == 'real'` 就报 True
  ⇒ 真实模式但模型没加载完 ⇒ 报 False（`_engines_ready()` 查引擎 `stats()['loaded']` 三项）；
* `popup.html` 加 `#modeCard`（回声=红底、真实=绿底）；**点「开始」前再查一次门禁**（轮询有 2 s 间隔）。

---

## 7. G 项 —— `targetLang` 存成 `"Chinese"` 时正确映射成 `zh`

现场证据：用户 Edge 默认 profile 的 `chrome.storage` 里 `targetLang` 存的就是 **`"Chinese"`**
（插件侧后来改用引擎码，但**存量配置不会自动迁移**）
⇒ 服务端只认 `zh/en/ja/ko` 时 `"Chinese"` 落到 None ⇒ 服务端按启动参数（默认 en）翻译
⇒ **用户看到「没翻译成中文」**。

修法：`ext/config.py` 新增 `LANG_ALIASES` + `normalize_lang_code(value)`
（`chinese/中文` → `zh`，`english` → `en`，`japanese` → `ja`，`korean` → `ko`，…）
⇒ **服务端独立实现**（插件没升级也能正确翻译）；
⚠️ **白名单**：未知字符串 ⇒ **None**（**绝不臆造**；不是默认 `'zh'`）。

★ **连带影响（本轮修掉的 3 处自测回归）**：这条改动**故意**改变了三条旧断言的行为
⇒ 旧断言写的是「全称 ⇒ None」，与 EXT-024 G **直接冲突**
⇒ 按指令「以指令内容为准」**更新断言**（并保留「未知值 ⇒ None」这组**不臆造**的对照）：

| 旧断言 | 新断言 | 依据 |
|---|---|---|
| `t3`：`'Chinese'` ⇒ 记成 None | `'Chinese'` ⇒ 记成 `'zh'` | EXT-024 G 明文 |
| `t4`：非法码 `'Chinese'` ⇒ 不传给引擎 | 非法码改用真·未知 `'xx'` ⇒ 不传给引擎；**另加** `'Chinese'` ⇒ 真的按 `'zh'` 传给 MT | EXT-024 G |
| `p1`：`holder['session']` 必须有 | `holder['session'] or holder['last_session']` | EXT-024 B（连接关闭清 holder + 归档） |

⚠️ 三处都**没有削弱**「不臆造」的语义：`t3` 里 `'xx'` 与「不带」两组仍必须记 None。

---

## 8. EXT-023 —— TTS 各组件 EXECUTION_DEVICES

要求：打印 talker / cp_prefill / cp_decode / decoder 各自**实际**的 EXECUTION_DEVICES，确认全部是 NPU。

* 本模块走的是 App 的 `tts_engine.make_engine()`（**不是裸 `build()`**）
  ⇒ App 侧 `make_engine()` 的最后一步已调 `_move_cp_decode_to_npu(eng)`
  **且**挂好 `eng.exec_devices = execution_devices(eng)`
  （见 `Confucius4_LiveCaption_v1.13/app/tts_engine.py` 的 make_engine 末段）
  ⇒ **不需要重复探测**（重复探测会再抢一次 NPU、很慢）；
* `ext/engine_runtime.py` 的 `_report_tts_exec_devices()`：
  * 打印一行 `key4_line`（`EXECUTION_DEVICES talker=…，cp_prefill=…，cp_decode=…，decoder=…`）；
  * 逐组件打印实际落点；
  * **落盘** `%LOCALAPPDATA%\LiveDubEXT\tts_exec_devices.json`
    （与 `bridge.log` 同目录；reviewer 可直接 `json.load` 出 `devices`/`actual`/`on_npu`/`on_cpu`/`unknown`）；
  * ⚠️ **绝不臆造**：引擎没有 `exec_devices` ⇒ `ok=False` + 原因，**照样落盘**（让 reviewer 看到「没测到」）；
  * ⚠️ 落盘失败**不抛**（诊断增强不能搞挂引擎）。

⛔ **本轮未在真实三引擎上验证 cp_decode 真的在 NPU**（机器锁属 TTS 模块，本轮未占 GPU/NPU）
⇒ 只落地了「**如实上报 + 落盘**」的机制 ⇒ **真实值要等下一次真实启动后从
`%LOCALAPPDATA%\LiveDubEXT\tts_exec_devices.json` 读**，**不宣称「已确认全在 NPU」**。

---

## 9. EXT-022 —— 编号规则 + 待命规则 + 两个已定事项

* **编号规则**：EXT-xxx 只用于主会话/reviewer 推送；自发工作改成 **T-1…T-4**
  ⇒ 本轮把工作区里自称的 `EXT-018`/`EXT-019`/`EXT-020`/`EXT-021`
  统一改成 **T-1**/`T-2`/`T-3`/`T-4`（代码注释 + notes 文件名 + STATUS 链接）。
* **流水线默认开启**（EXT-022 已定①）：`ext/bridge.py` 的 `--pipeline` 默认 **True**（另给 `--no-pipeline` 逃生口）；
  `tools/bridge_server.py` 与 `tools/run_p1_real.py` 同步为显式传 `--pipeline` / `--no-pipeline`
  ⇒ 消除「服务端默认值变了 ⇒ 脚本行为跟着变」的隐式耦合。
* **浏览器端人工验收由用户亲自做**（EXT-022 已定②）：本模块**不再**用 Playwright 替代；
  `pw_accept1-4` 与 `ext022_browser_harness` 作为**冒烟测试**保留 ⇒
  ★ **本轮已把它们从 `.tmp/` 迁到 `tests/smoke/`**（路径全部由 `__file__` 推导 ⇒ 可复现）
  并**入库**（EXT-022 已定②：「要么提交 git，要么删除，不要留在工作区」）。
  ⇒ 本轮实测 4 个脚本**全部 rc=0**（`pw_accept4` 动态分配端口，不与用户开着的桥接撞端口）。

---

## 10. 自测（本轮实测）

### 10.1 三处回归的修法与**反证**（证明断言不是恒真）

★ **反证**（把 `ext/bridge.py` 的 `session_holder["last_session"] = session` 改成 `pass` 模拟 EXT-024 B 被改坏）：

```
[FAIL] 服务端 session 可取到 — holder 里既没有 session 也没有 last_session
[FAIL] ★ EXT-008：能取到服务端 session（查逐帧到达延迟） — holder 里既没有 session 也没有 last_session
结果：88 PASS / 2 FAIL / 共 90     rc=1
```

⇒ 断言**有区分力**（改坏就红）⇒ 恢复后 `97 PASS / 0 FAIL` rc=0。

### 10.2 全量结果

| 套件 | rc | 结果 |
|---|---|---|
| `tests/test_echo_roundtrip.py` | 0 | 11 PASS / 0 FAIL |
| `tests/test_ext009_adaptive_speed.py` | 0 | 57 PASS / 0 FAIL |
| `tests/test_ext010_pipeline.py` | 0 | 23 PASS / 0 FAIL |
| `tests/test_ext011_thread_limits.py` | 0 | 29 PASS / 0 FAIL |
| `tests/test_ext012_user_guide.py` | 0 | 75 PASS / 0 FAIL |
| `tests/test_ext013_compare.py` | 0 | 51 PASS / 0 FAIL |
| `tests/test_ext013_cpu_watch.py` | 0 | 25 PASS / 0 FAIL |
| `tests/test_ext016_compression.py` | 0 | 39 PASS / 0 FAIL |
| `tests/test_ext017_user_report.py` | 0 | 108 PASS / 0 FAIL |
| **`tests/test_ext023_tts_exec_devices.py`（本轮新增）** | **0** | **23 PASS / 0 FAIL** |
| `tests/test_ext024_dl_routing.py` | 0 | 55 PASS / 0 FAIL（新增 4 项：t_start_axis 口径） |
| `tests/test_ext_browser_contract.py` | 0 | 102 PASS / 0 FAIL |
| `tests/test_ext_selfcheck.py` | 0 | 103 PASS / 0 FAIL |
| `tests/test_next_instruction.py` | 0 | 19 PASS / 0 FAIL |
| `tests/test_p1_plumbing.py` | 0 | 99 PASS / 0 FAIL（新增 2 项：t_start_axis） |
| `tests/test_t1_capture_mode_stats.py` | 0 | 38 PASS / 0 FAIL |
| `tests/test_t2_port_guard.py` | 0 | 28 PASS / 0 FAIL |
| `tests/test_t3_dead_controls.py` | 0 | 53 PASS / 0 FAIL |
| `tests/test_t4_target_lang_effect.py` | 0 | 52 PASS / 0 FAIL（新增 1 项：'Chinese'⇒zh 传给 MT） |

⇒ **19 套 / 990 PASS / 0 FAIL**（全 rc=0，逐套实测真实退出码）。
三套明文要求的自测单独确认：`test_ext_selfcheck.py` rc=0 / `test_echo_roundtrip.py` rc=0 /
`test_next_instruction.py` rc=0。
★ `test_next_instruction.py` 确认闸门仍能解析（`entries=9`、latest=EXT-025、last_ack=17、exit=0）⇒ 没弄坏闸门。

### 10.3 冒烟测试（EXT-022 已定②，**不是**人工验收）

| 脚本 | rc | 实测输出要点 |
|---|---|---|
| `tests/smoke/pw_accept1.py` | 0 | popup 正常渲染；storage 读到 `targetLang:'zh'` |
| `tests/smoke/pw_accept2.py` | 0 | 设置写入与回填一致（zh/A/−15/10/True） |
| `tests/smoke/pw_accept3.py` | 0 | player 页加载正常；读得到设置 |
| `tests/smoke/pw_accept4.py` | 0 | 插件 ↔ 桥接（回声）hello 到达服务端；`/status` 返回 `mode:"echo"` |

⚠️ `pw_accept1/3` 里的 `ERR_CONNECTION_REFUSED` 是**预期的**（那两轮没有桥接在跑）。

---

## 11. ⛔ 明确未做 / 未宣称

- ⛔ **Edge 真实手势 1 分钟验收没做**（EXT-024 验收 1–4 条）⇒ **必须由用户本人做**
  （EXT-022 已定②：浏览器端人工验收**由用户亲自做**，本模块不再用 Playwright 替代）
  ⇒ 因此**不宣称**「用户已听到中文配音」「字幕已显示」；
- ⛔ **没在真实三引擎上端到端跑过**（本轮未占 GPU/NPU；机器锁属 TTS 模块）⇒
  **不宣称**「cp_decode 已确认全在 NPU」（只落地了如实上报 + 落盘机制）；
- ⛔ **没在真实浏览器里验证过 tabCapture 生产路径**（需真实用户手势）；
- ⛔ **端到端仍不实时**（TTS 稳态 RTF **1.0022**）⇒ TTS 提速仍是上线的唯一前置；
- ⛔ **克隆音色仍不生效**（pyannote 旁路未接线 ⇒ 回落预设 A）；
- ⛔ **流水线 `--pipeline` 默认已开**（EXT-022 已定①），但**同步误差仍全部超标**
  ⇒ 实时未达成；
- ⛔ 本轮**未跑真实推理、未占 GPU/NPU**；`shared/MACHINE_LOCK` 属 **tts 模块**
  （PID 20684，探得 ALIVE）⇒ **未创建、未动、未回收**；
- ⛔ **未 kill 用户自己的桥接进程**（本轮开工时 `psutil`/`netstat` 均查不到 `ext.bridge`，8765/8766 无监听）；
- ⛔ **未改任何引擎文件**（ASR/MT/TTS 对方模块一行未动；只读 App 的 `exec_devices`）；
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在；未执行 `git add -f`）。

---

## 12. 产物清单（文件数 / mtime / 字节数）

见 STATUS §17 的产物表（逐项实测 `ls -la`）。
