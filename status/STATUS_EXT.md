# STATUS_EXT
last_ack: EXT-017
更新时间: 2026-10-30 22:27
已压缩: 原文见 archive/STATUS_EXT_upto_20261030.md（224 833 B）；本精简版 ≤ 40 KB / ≤ 300 行
当前任务: **§13 P2 待办收口（`captureMode` 上报进 stats + 扩展图标）** ⇒ ✅ 插件把**实际抓流方式**上报桥接（hello/capture_info）⇒ ✅ 服务端 `stats()` 与 `margin.json` 都带 `capture_mode`/`client_source`/`source_rate` ⇒ ✅ manifest 加 `icons`（4 个真实 PNG，**key 未动 ⇒ 扩展 ID 不变**）⇒ ✅ 新增 `tests/test_ext018_capture_mode_stats.py`（38 项，**含反证：回退实现 ⇒ 4 FAIL rc=1**）⇒ ✅ **14 套自测 777 PASS / 0 FAIL**（全 rc=0）⇒ ⚠️ **本轮未认领新 EXT 编号**（reviewer 未下发 EXT-018）⇒ **`last_ack` 保持 EXT-017**（依据 EXT-014 ② 做 STATUS 里明列的未完成项）⇒ ⛔ tabCapture 生产路径**仍未人工实测**（需真实用户手势），但**从今以后可从数据核对**；⛔ 端到端仍不实时（TTS 稳态 RTF 1.0022）

阻塞 / 待决定:
① ⛔ **端到端仍不实时，TTS 提速是上线的唯一前置** —— 稳态端到端 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**，源 `.tmp/ext008_bench/steady.json`）⇒ 建议目标 ≤ 0.85，**由主会话转达 TTS 模块**
② ⛔ **流水线 `--pipeline` 默认关闭，待 reviewer 拍板** —— 已落地且真实引擎实测有效（末句滞后 ↓68.8 %、喂帧不落后实时、零丢句零错误）
③ ⛔ **同步误差仍全部超标** —— 流水线轮 `sync_err_ms.p50=67289.3` / `n_over_target=22` / `last_segment_lag_sec=71.2074`（源 `.tmp/p1_pipe/p1_report.json`）⇒ 实时未达成
④ ⛔ **pyannote 旁路未接线** —— ASR-013 交付后由主会话通知；⛔ **P2（克隆/体验/稳定性）/ P3（打包）未开始**
⑤ ⛔ **tabCapture 生产路径仍未实测**（EXT-005 ①，需真实用户手势）；⛔ **浏览器端人工验收未做** —— 本机无 Chrome 只有 Edge 126 ⇒ 不宣称 Chrome 路径已验证
⑥ ℹ️ **EXT-009 服务端 lag 估计存在跨时钟常量偏差，尚未定量标定** —— 决策在服务端，不影响变速稳定性
⑦ ℹ️ §6.5.0/§6.8/§6.9 的 0.9264 **已撤回**（以 §7 为准，旧章节不回头改）；ℹ️ EXT-014 已落地为常设巡检规则；ℹ️ **EXT-016 已收口**（压缩 STATUS + CORRECTIONS，见 §11/§12）；ℹ️ **EXT-017②「start 后 2 秒内可见输出」已补行为级验收并修好**（`start()` 4.244 s → **0.032 s**，见 §12）

## 当前有效结论

| 项 | 值 | 来源文件 |
|---|---|---|
| 交付配置 | ASR=R2T2 INT8@GPU.0 / MT=Hy-MT2 INT8@GPU.0 / TTS=Qwen3-TTS@NPU | §10.4 启动日志 |
| 端到端稳态 RTF | **2.0507**（ASR 0.6563 / MT 0.1507 / TTS 1.0022） | `.tmp/ext008_bench/steady.json` → `steady_state_excl_first_segment` |
| TTS 稳态 RTF（独立实测，去首段 18 段/286.32 s） | **1.0022**（无余量，>1.0） | `.tmp/ext008_bench/steady.json` |
| 并行化收益上限 | `parallel_speedup_x=1.3613`（asr_slowdown 0.9498 / tts_slowdown 0.9838） | `.tmp/ext008_bench/interference.json` |
| 串行（EXT-009 前）末句滞后 | 227.9863 s，斜率 −0.565947 | `.tmp/p1_ext009/p1_report.json` |
| 流水线末句滞后 | **71.2074 s（↓68.8 %）**，斜率 −0.106051（↓81.3 %） | `.tmp/p1_pipe/p1_report.json` |
| 流水线喂帧 | `feed_speed_x` 0.5949 → **1.0**；`send_dur_max_sec` 58.453 → **0.007** | `.tmp/p1_pipe/p1_report.json` → `timing` |
| 流水线健康度 | `n_submitted=22 / n_emitted=22 / n_error=0 / n_pending=0` | `.tmp/p1_pipe/p1_report.json` → `bridge_stats.pipeline` |
| 流水线瓶颈 | `stage_wall_sec` = asr 234.912 / mt 2.397 / **tts 343.64** | `.tmp/p1_pipe/p1_report.json` |
| 自适应加速封顶 | `speed_time_share` >1.30× 占 **0.0**；1.20–1.30× 占 0.9144；`n_dropped_dub=0` | `.tmp/p1_pipe/p1_report.json` → `bridge_stats.adaptive_speed` |
| 线程限制 A/B | 核数 mean 0.8244 vs 1.2909（↓36.2 %）/ peak 2.819 vs 7.091（↓60.2 %）；TTS RTF 1.0542 vs 1.3249（↓20.4 %） | `.tmp/p1_ext013_lim/compare_ext011.json` |
| 余量口径 | 顶层 `basis="deadline"`（排程口径）；`n_negative=22`；`cumulative_lag_sec` 已被 EXT-008 有意删除 | `.tmp/p1_pipe/p1_report.json` → `metrics.margin` |
| 扩展 ID | `kekgmfkijphpfndbbpakjaokamkeooib`（由 manifest `key` 现场算，与 9 份探针一致） | `ext/extension_id.py` |
| `/pair` Origin 收紧 | 本插件 **200** / 别的扩展 **403** / 普通网页 **403** / 无 Origin **403** | §10.3 实测 |
| 控制台代码页 | 本机 `ConsoleOutputCP=gb2312` ⇒ GBK 编不了 `⇒`/`🔴`/`⛔` ⇒ 旧 `_log` 抛 `UnicodeEncodeError` | §10.1.1 实测 |
| 引擎加载耗时 | 17.9–26.9 s（预热阶段逐引擎 emit 进度） | §10.4 启动日志 |
| 用户方式验收 | 6 张截图 / 321 900 B 落 `C:\Users\Trekker-PTL\shared\ext_launcher_fix\` | §10.4 |
| 启动器 `start()` 反馈延迟 | **0.032 s**（修前 4.244 s）⇒ 满足 EXT-017②「2 秒内」 | §12 实测 |
| 桥接冷启动（回声模式，不含引擎） | **5.0–5.7 s**（10/10 实测，min 4.948 / max 5.581 / 均值 5.324） | §12 实测 |
| 自测套件 | **14 套 / 777 PASS / 0 FAIL**（全 rc=0） | 本轮实测 |
| 抓流方式（capture_mode） | 由**客户端实际上报**（hello / capture_info）；未上报 = `null`（**绝不臆造**） | `ext/bridge.py` → `stats()` / `margin.json` |
| 扩展图标 | 16/32/48/128 四个真实 PNG（116/152/180/443 B）；**manifest.key 未动 ⇒ 扩展 ID 不变** | `extension/icons/` + `tools/make_icons.py` |

## 未完成纠偏清单

| 编号 | 一句话 | 下一步 |
|---|---|---|
| EXT-016 | 压缩 STATUS 与 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB） | ✅ **已收口**（见 §11/§12） |
| EXT-017 ④余项 | 浏览器端人工验收（tabCapture 需真实用户手势） | 需用户本人操作；本机只有 Edge |
| EXT-017 ② | start 后 2 秒内可见输出 | ✅ **已修好并补行为级验收**（0.032 s，见 §12） |
| EXT-015 | 机器锁让给 TTS-033：本轮不要再拿锁 | 已过该窗口；TTS-033 已由 TTS 模块处理 |
| EXT-005 ① | tabCapture 生产路径实测 | ⏳ **代码侧已就绪**（`capture_mode` 会进 stats / margin.json ⇒ 可从数据核对）；**仍需用户点一次扩展图标**（见 §13） |
| EXT-014 ② | 巡检规则：last_ack 追平后仍要继续下一项 | ✅ 已落地为常设规则 |
| EXT-011/012/013 | 线程限制重测 / 用户试用件 / 对照表 | ✅ 已收口（**§9 全文见 archive/STATUS_EXT_upto_20261030.md**） |
| P2 其余 | 克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 | ⛔ 未开始（多数需真实浏览器 + 真实引擎） |

## 最近章节

> §9 及更早的章节全文在 **`status/archive/STATUS_EXT_upto_20261030.md`**（224 833 B）；
> §13 的逐条明细在 **`status/notes/sec13_ext018_p2_capture_mode_and_icons.md`**（EXT-016 写作规则）。

### §13 P2 待办收口 —— `captureMode` 上报进 stats + 扩展图标（2026-10-30 22:27）

**依据**：闸门 → **exit 1**（latest=EXT-017 / last_ack=17），六项交叉证据一致 ⇒ **无新纠偏指令**；
但按 **EXT-014 ②**（常设规则「`last_ack` 追平后仍要继续下一项」）做 STATUS 里明列、不需 reviewer 决策的 P2 待办。
⚠️ **未认领新 EXT 编号**（reviewer 未下发 EXT-018）⇒ `last_ack` **保持 EXT-017**。
★ **明细全文见 `status/notes/sec13_ext018_p2_capture_mode_and_icons.md`**（EXT-016 写作规则）。

⇒ **① `captureMode` 上报进 stats**：插件早就知道走的哪条抓流路（`state.captureMode` / `upState.captureMode`），
却只显示在插件内部 ⇒ 服务端 `stats()` 与 `margin.json` **没这个字段** ⇒ reviewer 无法从 P1 产物判断
「这轮跑的是生产路径(tabCapture)还是兜底路径(getDisplayMedia)」⇒ 只能人工翻日志（正是 EXT-005 ① 要避免的）。
改法：`player.js` 的 hello 带 `capture_mode`（抓流在 WS 之前完成 ⇒ 已知实际值）；
`offscreen.js` 抓流成功后补发 `capture_info`（hello 早于抓流 ⇒ 那时还是 null）；
`bridge.py` 的 `Session.note_client()` 记录 ⇒ `stats()` 与 `margin.json` 输出，`hello_ack` 回显（向后兼容）。
★ **白名单**：只接受 `tabCapture`/`getDisplayMedia`；**没上报就是 `null`，绝不臆造**；报的是**实际值**不是 `sw.js` 的**计划值**。

⇒ **② 扩展图标**：manifest 此前**没有 `icons` 字段**（工具栏显示默认灰块）。
新增 `tools/make_icons.py`（纯标准库写 PNG，**无依赖、可复现**）生成 16/32/48/128 四个图标并挂进 manifest。
⚠️ **`manifest.key` 未动** ⇒ 扩展 ID 实测仍是 `kekgmfkijphpfndbbpakjaokamkeooib`（EXT-017④ 的 Origin 校验依赖它）。

⇒ **③ 自测**：新增 `tests/test_ext018_capture_mode_stats.py`（38 项，行为级：真起服务 + 真 WebSocket）。
★ 含**对照组**（不带 capture_mode ⇒ stats 为 `None` ⇒ 证明服务端不编造）与**反证**
（回退实现 ⇒ **34 PASS / 4 FAIL、rc=1** ⇒ 断言不是恒真）。
★ **14 套 / 777 PASS / 0 FAIL**（全 rc=0）；`node --check` 四个 JS 文件全通过。

⇒ **④ ★ 附带**：**用户 22:31:29 双击了桌面快捷方式**（`pythonw ext_launcher.py` ⇒ 子进程 `ext.bridge --real --pipeline --port 8765`）
⇒ **不是自测拉起的** ⇒ 按铁律**未 kill**（它正做真实推理）。**意外收获**：在**真实运行的三引擎桥接**上验证了新字段
（不带 ⇒ `None`；带 `'tabCapture'` ⇒ `hello_ack` 与 `stats` **都是 `'tabCapture'`** ✅）。
**顺带确认 EXT-017② 在用户真实一次启动里成立**：`bridge.log` 显示 **引擎预热成功 3/3、总耗时 25.1 s**、
`✅ 模型加载完成（ASR/MT/TTS 就绪）` @ 22:32:06（日志证据，非桩）。

⇒ ⛔ **tabCapture 生产路径仍未人工实测**（需真实用户手势；本机只有 Edge 126）⇒ **只把可核对性准备好了，不宣称已验证**；
⛔ 端到端仍不实时（TTS 稳态 RTF 1.0022）⇒ TTS 提速仍是唯一前置；
⛔ 本轮**未跑真实推理、未占 GPU/NPU**；⛔ 未改任何引擎文件。

### §12 EXT-016 收口（接手被中断的一轮）+ EXT-017②「2 秒内可见输出」补行为级验收（2026-10-30 21:06）

**依据**：闸门 `tools/next_instruction.py --json` → **exit 1**（`already_executed`，latest=EXT-017 / last_ack=17）⇒ 按闸门应跳过；
但**交叉证据表明上一轮（EXT-016 压缩）被中断** ⇒ 按「接手未完成的轮次」处理，**不认领新编号**（last_ack 保持 EXT-017）：

| 证据 | 正常做完 | 本轮实测（被中断） |
|---|---|---|
| `git status --porcelain` | 干净 | **脏**：staged rename + 3 个未跟踪文件 |
| 归档与精简版 | 都已提交 | `status/archive/STATUS_EXT_upto_20261030.md`（224 833 B）与 `status/STATUS_EXT.md`（11 043 B）**都没入库** |
| 新增自测 | 已入库 | `tests/test_ext016_compression.py` **未入库** |
| EXEC_LOG | 有该轮记录 | **无 EXT-016 记录**（最新仍是 2026-10-30 16:11 EXT-017） |
| 闸门解析 | — | 压缩后仍正常（exit 1 / latest=EXT-017）⇒ 压缩本身没坏闸门 |

⇒ **① EXT-016 收口**：归档原文与精简版**逐字节校验与 HEAD 一致**（`cmp` 通过）⇒ 只补提交，不重做。
`status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在）；已关闭条目归档 `status/archive/CORRECTIONS_EXT_closed_upto_20261030.md`（23 067 B / EXT-001~EXT-014 全文）**入库**（与 app/hy/tts 模块的同名归档做法一致）。

⇒ **② ★ 本轮抓到 2 个真缺陷**（都是上一轮 691 PASS 掩盖掉的）：

* **缺陷 29（★ 产品缺陷）`_caption_app_running()` 阻塞 start 4.208 秒**
  —— 旧写法 `psutil.process_iter(["pid","name","cmdline"])` 对**全部 369 个进程**取 `cmdline`
  ⇒ **实测 4.208 s** ⇒ `start()` 在这 4.2 秒里**什么都不显示**
  ⇒ **直接违反 EXT-017②「start 之后 2 秒内必须出现『正在加载模型…』」**。
  修法：① 先只取 `name`（实测 **0.005 s**）② 只对**候选**进程再取 `cmdline`（**0.003 s**）
  ⇒ **4.208 s → 0.0015–0.022 s**；⚠️ 候选名单必须含 python/pythonw ——
  App 是用自己的 `pythonw.exe` 跑的（`Start_LiveCaption.bat`）⇒ `live_caption` 只在**命令行**里。
  **检出正确性已验证**：有 live_caption 进程 ⇒ True（0.021 s）；杀掉 ⇒ False（0.006 s）。
* **缺陷 30（测试缺陷）`test_ext017_user_report.py` 假 FAIL**
  —— 固定端口 **18811/18812** + 固定 **8 s** 超时，而桥接冷启动**实测就要 5.0–5.7 s**
  ⇒ 只剩 ~2.3 s 余量 ⇒ 机器一忙就超时 ⇒ `terminate()` 把子进程**杀在启动途中**
  ⇒ 后面 3 条断言因拿不到日志而**一起**失败（4 条同时红）。
  **本轮首次批量跑就复现**（95 PASS / 4 FAIL），**HEAD worktree 复跑却是 99 PASS / 0 FAIL**
  ⇒ 判定为**冷启动抖动**（非回归），并据此定阈值。
  修法：端口改**动态分配**（`_free_port()`）；超时 8 s → **45 s**（是上限不是性能指标）；
  并**单独**加一条「冷启动耗时 ≤ 30 s」的性能口径（实测 5.28 s）。

⇒ **③ ★ 补上 EXT-017② 的行为级验收**（此前只有源码字符串检查 ⇒ 不能证明「用户真能 2 秒内看到」）：
新增 `test_launcher_feedback_within_2s()` —— 真跑 `BridgeRunner.start()`（用**桩命令**当子进程，
**不加载真模型、不占 GPU / NPU**）⇒ 实测 `start()` **4.244 s → 0.032 s**（连跑 8 次 0.033–0.048 s，8/8 绿）✅ 满足 2 秒口径；
并断言「提示带 PID/端口/日志路径」「状态灯同步切到加载中」「子进程输出既转发到窗口**又**落进日志文件」。
配套改动：`tools/ext_launcher.py` 的 `BridgeRunner` 新增 **自测注入点**
（`cmd=` / `log_path=` / `pid_path=`）⇒ 默认 `None` ⇒ **生产路径完全不变**。

⇒ **④ 自测**：**13 套 / 739 PASS / 0 FAIL**（全 rc=0）：
echo_roundtrip 11 / ext009 57 / ext010 23 / ext011 29 / ext012 75 / ext013_compare 51 /
ext013_cpu_watch 25 / **ext016_compression 39** / **ext017_user_report 108** / browser_contract 102 /
selfcheck 103 / next_instruction 19 / p1_plumbing 97。

⇒ ⛔ 端到端仍不实时（TTS 稳态 RTF **1.0022**）⇒ **TTS 提速仍是上线的唯一前置**；
⛔ 浏览器端人工验收仍未做（tabCapture 需真实用户手势）⇒ **不宣称浏览器链路已验证**；
⛔ 本机无 Chrome（只有 Edge 126）；⛔ 未跑任何真实推理（本轮全程 CPU 侧，**未占 GPU / NPU**）。

### §11 EXT-016 落地（2026-10-30 19:05）

**依据**：闸门 `tools/next_instruction.py --json` → **exit 1**（`already_executed`，latest=EXT-017 / last_ack=17）⇒ 无新纠偏；
但 **EXT-016（压缩 STATUS/CORRECTIONS）从未被认领**（§10 头部自注「EXT-016 压缩 STATUS 未认领」），
且 STATUS 仍 224 833 B ≫ reviewer 要求的 40 KB ⇒ 命中 **EXT-014 ②**（STATUS 仍有未完成项且本模块无进程在跑 ⇒ 直接继续下一项，不空转）。

**① STATUS 拆分**：`status/STATUS_EXT.md` → `status/archive/STATUS_EXT_upto_20261030.md`（**224 833 B**，原样保留，不删内容）；
新建精简版 `status/STATUS_EXT.md`（头部 ≤ 15 行 + 当前有效结论表 + 未完成纠偏清单 + 最近 3 节，每节 ≤ 60 行）。

**② CORRECTIONS 压缩**：已完成的 EXT-001~EXT-014 全文 → `status/archive/CORRECTIONS_EXT_closed_upto_20261030.md`；
`status/CORRECTIONS_EXT.md` 只留顶部索引表（编号/一句话/状态）+ 进行中全文 + 最近 5 条全文（EXT-013~EXT-017）。

**③ 闸门压缩后仍正常**：`next_instruction.py` → exit 1 / latest=EXT-017（编号与标题格式未变，reviewer 推送工具仍可追加）。

**④ 自测**：新增 `tests/test_ext016_compression.py`（结构 / 大小上限 / 归档存在 / 闸门可解析 / 索引覆盖 / 标题格式）。

### §10 EXT-017 落地 —— 用户报的两个故障（乱码 / start 后无输出）（2026-10-30 16:12）

* **① 乱码根因**：本机 `ConsoleOutputCP=gb2312`；GBK 编不了 `⇒`/`🔴`/`⛔` ⇒ 旧 `_log` 裸 `print` 抛 `UnicodeEncodeError` ⇒ 崩溃/日志中断。
  修法三层：`ext/utf8_io.py`（`safe_print` 逐字符降级 + `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`）+ `.cmd` 里 `chcp 65001` + `.cmd` 本身改**按 GBK 写**。
* **② start 无输出：三个独立成因全修**：三引擎全懒加载 ⇒ 新增 `RuntimeEngine.warmup()` 逐阶段预热并 emit 进度；
  子进程 stdout 被重定向到文件 ⇒ 改 `subprocess.PIPE` + `errors="replace"` 逐行喂窗口与日志；
  **★ GUI 启动器本身起不来** —— 桌面快捷方式指向**没有 tkinter** 的 `pythonw` ⇒ 窗口根本不出现且报错被 pythonw 吞掉 ⇒ 改指 App 自带 `pythonw` + `_has_tkinter()` 实测探测 + tkinter 缺失弹 MessageBox + 顶层异常兜底。
* **★ 验收中又抓到两个真缺陷**：`tk.Combobox` 不存在（应为 `ttk.Combobox`）；**状态灯永远停在「正在加载模型…」**（配对端点在预热之后才启动 + `app.after` 只调度一次）⇒ 配对端点提前启动 + 轮询放 `finally` 里自我续期。
* **★ 用户方式实测验收通过**（桌面快捷方式 → 中文 Windows 默认控制台 → 鼠标点启动）：**2 秒内**见「正在加载模型…（预计 20–40 秒）」+ PID/端口/日志路径 + 逐引擎进度「(1/3) 正在加载 ASR [R2T2 INT8] @ GPU.0」⇒ 加载总耗时 **17.9–26.9 s** ⇒ 最终「**TTS 就绪**」；
  **故意让 MT 加载失败 ⇒ 红色「引擎未就绪」+ 完整失败原因 + 日志路径**，ASR/TTS 照常加载 ⇒ 截图 **6 张 / 321 900 B** 落 `shared/ext_launcher_fix/`。
* **③ USER_GUIDE 补 Edge**（`edge://extensions` + 开发人员模式在**左下角** + 「加载解压缩的扩展」+ 「关掉开发人员模式会让插件被停用」）；两份文档各 14166 B。
* **④ `/pair` 收紧到本插件 ID**（`ext/extension_id.py` 由 manifest `key` 现场算 ID = `kekgmfkijphpfndbbpakjaokamkeooib`，与 **9 份浏览器探针**的 `ext_id` 完全一致）⇒ 实测本插件 Origin **200** / 别的扩展 **403** / 普通网页 **403** / 无 Origin **403**。
* **12 套自测 691 PASS / 0 FAIL**（新增 `tests/test_ext017_user_report.py` 99 项，含 4 处「假通过」断言改精确）。
* ⛔ 端到端仍不实时（TTS RTF 1.0542 > 1.0）⇒ **TTS 提速仍是唯一前置**；⛔ 浏览器端人工验收未做（tabCapture 需真实用户手势）⇒ **不宣称端到端浏览器链路已验证**；⛔ 本机无 Chrome（只有 Edge 126）。
