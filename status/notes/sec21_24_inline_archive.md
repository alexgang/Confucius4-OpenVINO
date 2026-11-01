# §19·§20 / §21 / §22 / §23 —— **原内联正文下沉存档**（**数字一字未改**）

> ★ 本文件是 `status/STATUS_EXT.md` 中 **§19 / §20 / §21 / §22 / §23** 五节**原内联正文的逐字存档**。
> ★ 依据 **EXT-016 写作规则**（STATUS ≤ 300 行 / ≤ 40 KB / < 归档/10 = 22 483 B；「最近章节只保留最近 3 节」）；
> ★ 沿用本模块 **§20 收口**（commit `5088005`）的既有做法：内联正文逐字下沉、STATUS 只留结论。
> ⚠️ **下方正文一律逐字照抄，数字一个未改**——只搬位置，不改内容。

---

## §21 —— 原内联正文（逐字）

## §21 EXT-029 —— 说话人旁路：**独立线程 + 有界队列 + 异步回填**（不反压 ASR）（2026-11-01 16:14）
**依据**：闸门 **exit 0**（latest=**EXT-029** / last_ack=26）⇒ **认领 EXT-029**。
★ **明细全文见 `status/notes/sec21_ext029_spk_bypass_thread.md`**（7 节）——本节按 EXT-016 规则**只留结论**。
⇒ **① 4 个真缺陷已修**（根因/修法/证据见 notes §21.2）：**D1** `PipelineSession` 覆盖 `_dispatch_segment()` 不调基类 ⇒ 流水线从不登记定稿段（`n_final_req=0`/`n_label=0`）⇒ 补 `_request_spk_label()` ⇒ 复测 `n_final_req=19`/`n_label` 2–8；**D2** `tabCapture.capture({targetTabId})` **API 用错**（属 `getMediaStreamId()`）⇒ 每轮降级整机声音 ⇒ 改 `getMediaStreamId({targetTabId})`+`chromeMediaSource:'tab'`；**D3** `margin.json` 缺真实 ASR 墙钟 ⇒ 增落 `pipeline.stage_wall_sec.asr`；**D4** safe-delete 钩子腰斩录音分析 ⇒ `summary.json` 未落盘 ⇒ 唯一 profile 名 + `reuse_profile=True` + try/except。
⇒ **② ★ 判据口径修正（5 轮实测）**：原文「ASR 墙钟差异 ≤5%」**被环境噪声主导**（A 臂 ASR 自身 **21.9020–67.8250 s**、**3.1×** 波动，有符号差异**符号不一致**）⇒ **改用机制直接度量**：ASR 等 GPU 锁时间 = `stage_wall_sec.asr` − Σ`asr_sec` ⇒ ★ **A max 0.0007 s / B max 0.0008 s（≤0.004 %）⇒ 不反压 ASR** ✅；feed_lag 改用每段均值。
⇒ **③ 旁路指标（5 轮 B 臂）**：`spk_queue_drop` **0–57**（满丢旧块并计数）/ `spk_worker_busy_ms` **276.6–777.5**（≈0.5 %）/ `spk_gpu_lock_held_ms` **1726.1–6793.3**（额外延迟**上界**，占 ASR 墙钟 **4.5–24.0 %**）/ `n_label` **2–8** / 检出 **S1/S2(/S3)** ⇒ EXT-029 ④ 已满足（已**报测得的额外延迟**）。
⇒ **④ 机器锁（铁律）**：开工锁被 **app-pack**（PID 8412）持有 ⇒ 用 **ctypes `OpenProcess`+`GetExitCodeProcess`** 探测（**code=259 ⇒ 存活**）⇒ **等，不抢**；5 轮逐轮取放，**未回收他人锁**。
⇒ **⑤ 自测（实测）**：三套明文 **rc=0**（**106**/**11**/**19**）；`test_ext029_spk_bypass.py` **70 PASS / 0 FAIL**（+12，**不改写旧断言**）；node harness **8 套 rc=0**；全量 **26 套 / 1 221 PASS / 1 FAIL**（唯一 FAIL = 既有 CORRECTIONS 体积项 ⇒ 只读不改）。★ 新增断言覆盖 4 个缺陷（含反证）。
⇒ **⑥ 红套件归因（`git stash` 基线复核）**：`test_ext016_compression` **基线同样红**；`test_ext017_user_report`/`test_ext026_audio_analysis` **单独跑全绿**（批处理偶发红 = 实时字幕 App 在跑 / safe-delete 钩子）⇒ **环境性，非回归**。
⇒ **⑦ ⛔ 未做 / 不宣称**：⛔ **音色克隆未接线**（`voice_source` 全 `'preset'`、`clone_wired=false`）⇒ **不宣称克隆音色可用**；⛔ **Edge 真实手势验收未做**（用户本人）；⛔ **tabCapture 生产路径未实测**；⛔ **英译中仍未真正测到**（抓流仍是整机声音）；⛔ 端到端仍不实时（TTS RTF 1.0022）/ 同步误差仍超标 ⇒ **未动引擎**；⛔ `CORRECTIONS_EXT.md` 只读未入库。

## §22 —— 原内联正文（逐字）

## §22 EXT-030 —— 巡检会话互相重叠：**模块租约**已接入自动化指令（2026-11-01 16:45）
★ **全量明细（含自动化指令新增四段原文）见 `status/notes/sec22_23_ext030_lease_ext031_handoff.md` §22.1**。
⇒ **① ★★ 本轮实测触发 EXT-030 描述的正是它自己的故障**：开工时租约已被**另一 EXT 会话**（token=`c3389eb3`，15:42 起）持有 ⇒ `acquire ext` **exit 10 (BUSY)** ⇒ 按铁律**没抢**（后台轮询）⇒ 该会话心跳停在 15:44（**21.7 min**）⇒ 满 30 min TTL ⇒ **exit 0 + `TAKEOVER`** ⇒ 本会话拿 `TOKEN=16a4f381` ⇒ ★ **租约机制真实生效**（重叠被挡 → 超时自动接管 → 从断点继续）。
⇒ **② 自动化指令已改好**（id=`9ec49c32-…`，`FREQ=HOURLY`）新增**四段**：开工前 `acquire`（插在「第 0 步」之前）/ `beat` 心跳 / `addpid`（长作业后台启动后登记 PID）/ 结束 `release`（无论是否跳过都做）；铁律区补「租约与 MACHINE_LOCK **互不替代**」。
⇒ **③ 证据**：`shared\leases\ext.json`（389 B，mtime 16:15）；`.workbuddy\logs\automation.log`（1 015 237 B，mtime 16:17）。
⇒ **④ 本轮未碰 MACHINE_LOCK**；⛔ 未改 `session_lease.py`（只读使用）/ 未改其他四模块自动化 / 未推远程。

## §23 —— 原内联正文（逐字）

## §23 EXT-031 —— 插件整合进发行包 V2.0：**交付清单已写 + 不依赖开发目录已实测**（2026-11-01 16:45）
★ **全量明细见 `status/notes/sec22_23_ext030_lease_ext031_handoff.md`**。
⇒ **① 交付清单** `release/V20_HANDOFF.md`（新建）六项齐全：插件 unpacked（**15 文件 / 219 021 B**）/ 桥接入口命令（参数表）/ Python 依赖（包名+版本）及 **App 包内缺的**（★ **`websockets` 与 `psutil` 包内没有 ⇒ 打包必须补装**）/ 模型与 IR 映射（**不另带一份**，全映射到 App 包内 `models/`）/ 端口 8765·8766 + `bridge_token.txt` + `%LOCALAPPDATA%\LiveDubEXT\bridge.log` / 首次启动步骤。
⇒ **② ★★「不依赖开发目录」实测**（不是看代码）：新脚本 `tests/smoke/ext031_fake_pkg_launch.py` 造**模拟发行包根**（目录名故意不叫 `live_dub_ext`）⇒ ★ **6 PASS / 0 FAIL**：引擎根+模型目录+说话人 IR **全在包内**（越界**无**）/ 解析结果**不含**开发机目录名 / `package_root()`=模拟包 / `EXT_RELEASE=1` ⇒ 白名单只留 `tabCapture`。证据 `.tmp/ext031/fake_pkg_probe.json`（2 836 B）。
⇒ **③ ★ 发行版调试剔除**：`RELEASE_MODE`（`EXT_RELEASE` 或包根 `release.json` ⇒ **显式覆盖优先**）⇒ ① 白名单**只留 `tabCapture`**（整机 `getDisplayMedia` 回退禁用）② `--audio-dump-out` **忽略** ③ `--margin-out` **忽略**；另剔 `extension/probe-worklet.js`（391 B，**零引用**）；Playwright 驱动**只在 `tools/`**（不进包）。
⇒ **④ EXT-027/028/029**：**EXT-028 ✅ 已修**（`resolvePcmSampleRate()`；**42 PASS / 0 FAIL**）⇒ **不构成打包阻塞**；EXT-027 🟡 代码侧已修但**生产路径未实测**；EXT-029 ✅（§21）。
⇒ **⑤ 结论**：★ **插件部分 = 可打包**；★ **但**发行包**必须补装 `websockets`+`psutil`**，且 `manifest.json` 的 `liveDub.release` 需置 `true`（**打包必改只有 3 处**，清单 §9）。
⇒ **⑥ ⛔ 未做**：⛔ **打包由 App 线程执行（APP-057）**；⛔ **音色克隆不可用**（全 `'preset'`）⇒ 按预设音色发布；⛔ 端到端仍不实时（RTF **2.0507** / TTS **1.0022**）⇒ **由主会话转达 TTS 模块**；⛔ 同步误差仍超标（`sync_err_ms.p50=67289.3`）；⛔ Edge 真实手势验收未做（用户本人）；⛔ 未改引擎 / 未推远程 / `CORRECTIONS_EXT.md` 只读。
> **§16 ~ §10 —— 已下沉**（明细全文在 `status/notes/`；§10 及更早见归档 `status/archive/STATUS_EXT_upto_20261030.md`）：
> * **§13 ~ §16** 见 `notes/sec13…sec16_*.md`；**§12 / §11** 启动器 `start()` **4.244 s → 0.032 s**（EXT-017②）、STATUS 拆分归档（`notes/sec11_12_ext016_closeout.md`）
> * **§10** 控制台 `ConsoleOutputCP=gb2312` ⇒ 乱码根因；三层修复（`ext/utf8_io.py` + `chcp 65001` + 日志 UTF-8）；★ GUI 启动器指向**没有 tkinter** 的 `pythonw`（窗口根本不出现）⇒ 改指 App 自带 `pythonw`（用户方式实测通过，6 张截图 / 321 900 B 落 `shared/ext_launcher_fix/`）；`/pair` 收紧到本插件 ID（本插件 **200** / 别家 **403** / 无 Origin **403**）。

## §19 / §20 —— 原内联小节（逐字）

### §19 / §20 —— T-5 内存有界化 + T-6 设置持久化 + §19 收口（2026-10-31 23:21 / 2026-11-01 00:57）
★ **明细全文见 `status/notes/sec19_t5_t6_bounds_persist.md`**（13 267 B）**与 `status/notes/sec19_20_closeout.md`**（§19/§20 原内联正文，**数字一字未改**）
⇒ **结论**：3 类无界增长真缺陷全部有界化（统计口径一字不变）+ 设置持久化修好（改了就落盘）；自测 **24 套 / 1 104 PASS / 1 FAIL**（唯一 FAIL = 既有 CORRECTIONS 体积项，reviewer 独占只读）、node harness **7 套 rc=0**；三套明文自测 **rc=0**（103/11/19）。

---

> ★ §19/§20 因「最近章节只保留最近 3 节」而**移出**最近章节窗口（结论仍在「当前有效结论」表的 T-5 / T-6 两行；
> 明细见 `notes/sec19_20_closeout.md` 与 `notes/sec19_t5_t6_bounds_persist.md`，两者均已入库）。
> ★ 本轮新增的 §24 正文**不在**本存档里（它是新增内容，见 `notes/sec24_takeover_closeout.md`）。
