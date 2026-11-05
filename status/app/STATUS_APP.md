# STATUS_APP

last_ack: APP-072
更新时间: 2026-11-05 15:28
当前任务: **§138 APP-072（MiniMVP rc3 性能测试 zip）本条已完成** —— **三道闸门全过**：①黑名单扫描 **6/0**（对**解压副本**扫；反证：同脚本扫源目录 ⇒ 判据④ FAIL 抓到 8 个 babelvox 示例音色 ⇒ 判据非恒真）②NOTICE 署名 **PASS**（Qwen3-ASR/Qwen3-TTS/Hy-MT2/OpenVINO 齐；补丁前后 9 643→10 339 B；三块定点替换各命中 1 次）③`--check` **5/0**（rc=0／「环境正常」／GPU.0+NPU 均探测到／ASR 可用后端 3 个）＋ **GUI 冒烟 5/0**（TTS 加载 8.5 s／NPU／抓到完整主窗口 1439×1093 非黑图／**字幕区 163 行墨迹**证明 ASR 出字+MT 翻译+渲染都通／**负对照 0 墨迹**／无 0xC0000409）｜**zip 已出**：`shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip`（**5 591 630 138 B**／**10 474 条目**／SHA `dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1`）｜**README_perftest.txt 已进包**（9 155 B／SHA `da3cd8ca1dabb1e28fdafb9ba243111f03daf513177782c6f7b545f32daa62b9`）｜**打包一致性对账**：rc3 目录相对打包前快照 **只新增 README、只改 NOTICE 一个文件，其余 10 502 个文件逐条未变**
阻塞 / 待用户决定: 🔴 **APP-071 仍未完成（BLOCKING）**（克隆音色串音：男声 3 段听上去是女声）—— 本轮**只完成根因分析第一部分**（S2 首次登记段确为 `seg1`／`spk_conf=0.1292`／与 reviewer 怀疑吻合；**当前代码完全没有 `spk_conf` 门槛**）⇒ **(a) 诊断落盘／(b) 余弦矩阵／(c) 登记逻辑修复（代码一行未改）／(d) `v23_clone_r2/` 均未做**｜⛔ **v2.3 不打包**（APP-071 (e) 明文）｜🔴 **本轮需 reviewer 复核**：APP-072 的 zip／三闸门／README（等 reviewer 转告用户去取包）｜⛔ **APP-069/070 剩余项仍未做**（§137 未清项，见 §136/§137 归档件）｜🔴 **未通知用户／未改桌面快捷方式／未动 v2.1、v2.2、rc1、rc2 一字节／未通过任何外部服务分发**
已压缩: **§135–§137 的正文均已原样归档**到 `status/archive/STATUS_APP_sec135_upto_20261105.md`（18 133 B）／`STATUS_APP_sec136_upto_20261105.md`（12 364 B）／`STATUS_APP_sec137_20261105.md`（9 705 B）／`STATUS_APP_sec135_137_infofast_20261105.md`（8 585 B）＋ **§138 正文归档**到 `status/archive/STATUS_APP_sec138_20261105.md`（28 336 B）⇒ 本文件内只留**速查行**；限额 ≤ 40000 B / ≤ 300 行（APP-052 ④）｜写后实测 **39145 B / 168 行**


## 最近更新
- 2026-11-05 15:28 **§138 已写** ⇒ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成**｜**zip 已出**：`shared/minimvp/…_v1.0-rc3_perftest.zip`（**5 591 630 138 B**／**10 474 条目**／SHA `dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1`）｜**三道闸门全过**：①黑名单 **6/0**（扫解压副本；反证：同脚本扫源目录 ⇒ 判据④ FAIL）②NOTICE 署名 **PASS**（Qwen3-ASR/Qwen3-TTS/Hy-MT2/OpenVINO 齐）③`--check` **5/0**（rc=0／「环境正常」／ASR 可用后端 3 个）＋ **GUI 冒烟 5/0**（TTS 加载 8.5 s／NPU／主窗口 1439×1093 非黑／**字幕区 163 行墨迹**＋**负对照 0**／无 0xC0000409）｜**README_perftest.txt 已进包**（9 155 B）｜**一致性对账**：rc3 只新增 README、只改 NOTICE，其余 10 502 文件逐条未变｜⛔ **APP-071 仍未完成（BLOCKING）**：只做了根因分析第一部分（S2 首登记段 `spk_conf=0.1292` 与 reviewer 怀疑吻合；**代码无 `spk_conf` 门槛**），**(a)(b)(c)(d) 全未做** ⇒ **v2.3 不打包**

- 2026-11-05 13:37 **§137 已写** ⇒ 无新纠偏（70 条 = APP-070）⇒ 从 §136 断点续做：**APP-069⑥ MT INT4/INT8 对比已完成**（46 段／4.35 % 相同／chrF 74.029；夹具 0 段缺陷已修＋反证 4/0）｜**APP-069② GUI 臂未完成**（有效启动 0/10，2 次 harness 超时、非产品崩溃）｜回收 2 个孤儿锁｜`CORRECTIONS_APP.md` 收尾 SHA 与开工逐字相同
- 2026-11-05 11:20 **§136 已写** ⇒ **APP-068 + APP-069 + APP-070 三条新纠偏的代码侧全部落地 ＋ MiniMVP rc3 已出（设备级 3(a) PASS 9/0）**｜🔴 **APP-069① 根因已判定**：rc2 的 **24 段全零是「落盘算法」假象**（`app267` 6/0：模型预测 24 段 vs 实测 24 段**精确对应**（54.18 s vs 54.24 s）＋ **反证** 5 个模型族全复现不出 ＋ 合成侧 peak/rms **76/76 健康** ⇒ **不是产品静音**）｜**dump 已修**（`_flush_timeline` 改**顺序拼接** ＋ 回填逐句 `wav_t0`/`wav_t1`/`peak`/`rms_db`）｜**内容判据 `app268` 4/0**（rc2 旧 wav **FAIL/受损 24 句**＝reviewer 口径；rc3 新 wav **PASS/零段 0**）｜**APP-068 `app266` 7/0**｜**APP-069⑤ 5 项清理全落地**（回归 215 29/0・227 34/0・229 反证 PASS・237 9/0）｜**APP-069③＋APP-070① 口径统一** ＋ **TTS IR 删前清单 `app270` 4/0**（候选 8 个 **975.9 MB**，**一个文件都没删**）｜**APP-069④＋APP-070② A+C 代码侧已落**｜**rc3 已出**（6 843.8 MB / 10 503 文件）＋ **设备级 3(a) PASS 9/0**｜**APP-069② `--check` 臂 10/10 零崩溃**｜⛔ GUI 臂等锁（TTS 模块在跑 e2e）｜⛔ ⑥MT 对比 / ⑦zip / ⑩删 IR / ⑪A+C 设备指标 **未跑**
- 2026-11-05 08:38 **§135 已写** ⇒ **APP-067 ②④ 设备级补齐**（② 交付物：`shared/app_listen/v23_clone/`；④ ABBA **10/0** ＋ GUI 臂 **5/0**）｜**APP-066 3(a) CLI **8/0**；3(b) GUI 冷启动：**首次 NPU 编译 1209.3 s**（真冷臂 `app263`）／**第二次启动 9.5 s**（热臂 `app264`）+ 100%/150% 主窗口截图**｜🔴 **MiniMVP rc1 P0 已修 ⇒ rc2**（9 闸门全绿）＋**修好 rc2 的 `ACCEPTED.pkg_dir` 与 R2 白名单**（app191 9/6 → **18/0**）｜⛔ 3(c) zip 未打｜🔴 **本轮接管死租约（第 2 次）**：上一会话起草了 §135 但**未写 STATUS**；本轮逐条与磁盘证据对照 ⇒ **更正其「3(b) 已通过」的不实陈述**（落盘证据实为 FAIL）⇒ **重跑 3(b)**｜🔴 `CORRECTIONS_APP.md` 零改动（67 条 / SHA `cf71e427…`）
- 2026-11-04 21:12 **§133 + §134 已写** ⇒ **APP-067 ①③⑤ 已完成（设备级，`app243` 9/0 + 4 反证）**｜**APP-066 v1.0 的 6 处硬缺陷（含 P0 无法启动）已修** ⇒ **`MiniMVP_v1.0-rc1`**（7 闸门全绿 / 52.41 % 体积）｜⛔ ②④ 与 (a)(b)(c) 未做（等锁）｜🔴 `CORRECTIONS_APP.md` 零改动（67 条 / SHA `cf71e427…`）
- 2026-11-04 20:41 **§133/§134 开工** ⇒ **两条新纠偏（APP-066 MiniMVP 最小包 / APP-067 克隆 0 % 根因 + D4 + ABBA + D1）**；`last_ack` **APP-065 → APP-067**；**接管上一会话（TAKEOVER，117 min 前失联）**：其 3 个提交（`42b62e7`/`e804108`/`e88e3f1`）已入库但 **STATUS 未写** ⇒ 本轮从断点续做
- 2026-11-02 10:58 **§131 APP-062（D1–D4）已执行** ⇒ **D1** 旁路窗长改**配置项**（`LIVECAP_SPK_WINDOW_S`）＋**与 ASR 侧同源**（读 `asr_spk_window.WIN_S`）｜**D2** 选「跟随说话人」⇒ **自动开旁路**（三处同步）＋ 状态栏「说话人分离：开（克隆需要）」｜**D3** **客户包去掉 TTS=CUDA**（界面不显示 ＋ CLI 拒绝 exit 2）＋ `pkg_exclude` 排除 3 个文件 ⇒ **包内 grep `_fq3tts_env` 命中 0 处**｜**D4** **禁止** MT+TTS 同 NPU ⇒ MT 自动改 GPU.0 ＋ 告知 ＋ 写日志 ＋ 启动时同样处理 ⇒ `app227` **34/0**、`app228` **8/0** ⇒ 回归 `app215` **29/0**、`app220` **39/0**、`app219` **13/0**、`app224` **5/0**（均与 §129 一致）⛔ D2/D4 截图与设备级实测仍未做（TTS 模块持 `MACHINE_LOCK`）🔴 **更正 §130**：reviewer 于 **09:17:51 追加了 APP-062** ⇒ §130「SHA 零改动」结论作废
- 2026-11-02 09:56 **§130** ⇒ 无新纠偏（61 条 = APP-061）⇒ **自查 3 个真缺陷并修好**：① `app224` 的「字符串常量逐字不变」**按下标比** ⇒ 合法增删一个常量就整体错位 ⇒ `app223` 炸出 **483 条**假「值变了」⇒ **闸门在正确代码上永久 FAIL**（实测 **3 PASS / 2 FAIL**）⇒ 改按**多重集**比 ＋ 拆出 docstring（散文会合法演进）＋ 加 ⑦⑧ 两组判据自检 ⇒ 改后 **5 PASS / 0 FAIL** ＋ 真实产物负向测试 **5/5** ② CUDA 路线「回落预设」**不换参考音频** ⇒ 边车里仍是上一人的克隆音频 ⇒ **串音** ⇒ 4 个回落出口**收敛到共用出口** ⇒ `app226` **10/0** （含反证：改回旧行为必 FAIL）③ `app215` 的 2 处判据被重构波及（反证锚点缩进 ＋ ①b 作用域：`ast.walk(If)` 会遍历 `else` 分支）⇒ **语义不变地**跟着走 ⇒ 回归 `app215` **29/0**、`app220` **39/0**、`app219` **13/0**（与 §129 逐字一致）＋ ⛔ **设备级实测仍未跑**（本轮定位到干扰源 = **ASR 持锁跑 D1**；用户 v2.1 会话实测 **0.000 s/10 s** ⇒ 不干扰）
- 2026-11-02 04:47 **§129** ⇒ 无新纠偏（61 条 = APP-061）⇒ **自查 4 个真缺陷并修好**：① `app224` 用**移动 `git HEAD`** 当基线 ⇒ 修复一提交就在**正确代码上永久 FAIL**（0/5）⇒ 改钉 `fae75d9` ＋ **判据自检**（坏文件必被抓住）⇒ **5/0** ② 锁闸门第 11 组 AST 反证谓词**恒真**（只认 `os.exists`、抓不到 `os.path.exists`）⇒ **只定位留证、待 reviewer 裁定** ③ `app223` **3 个缺陷**（`--dry-run` 跑不出来 / 自检冲掉真机证据 / 反证臂从不判定）全修 ④ **APP-061② 附带问题** `Fatal Python error: _enter_buffered_busy`（边车退出崩溃）⇒ 改裸 fd `os.read` ⇒ **A/B 实测 orig 崩 3221225477 / fixed rc=0（两组都收到数据）** ＋ 回归 `app215` 29/0、`app220` 39/0、`app219` 13/0 ⇒ ⛔ **设备级实测仍未开跑**（用户会话 PID 14712 实测仍在烧 CPU 0.656 s/5 s）＋ 🔴 v2.2 包内仍是改前版 ⇒ 下一版打 v2.3
- 2026-11-02 03:16 **§128** ⇒ 无新纠偏（61 条 = APP-061）⇒ APP-061② `SyntaxWarning` 已修（5 文件，告警全归零，字符串值未变）＋ 共享锁闸门夹具写死日期导致的 **8 条假 FAIL 已修（32/40 → 42/42）**＋ **CUDA 置灰 4/4 落点核验通过** ＋ 真机验收 harness `app223` 已备好（判据自检 5/5 ⇒ 非恒真）⇒ ⛔ **设备级实测未开跑**（用户 v2.1 会话在跑）＋ 🔴 新增待裁定：`stale_boot` 优先于 PID 存活 ⇒ 时钟异常会抢活锁
- 2026-11-02 02:00 **§127 APP-061 已执行** ⇒ ①⑤③⑥ 代码层全部修复（`app215` 29 PASS / 0 FAIL；`app220` 39 PASS / 0 FAIL；`app219` 13 PASS / 0 FAIL，v2.1 同口径 **FAIL** ⇒ 判据非恒真）⇒ **v2.2 新目录 + 新 zip**（v2.1 未改一字节；桌面快捷方式未改）⇒ ⛔ 设备级实测与 D1–D4 仍待办
- 2026-11-01 22:23 **§127 APP-061 开工**（`last_ack` APP-060 → **APP-061**）⇒ **BLOCKING**：用户实测 v2.1 的 6 个问题（CUDA 无声／离线无参考音色／卡顿／克隆每 10 s 一次／男声被女声播出／界面不紧凑）⇒ reviewer 已定位根因 ⇒ 在开发版 `live_caption/` 修 ⇒ **打新版本 v2.2**（v2.1 目录与 zip 一个字节都不许改）
- 2026-11-01 21:13 **§126 APP-060 已执行** ⇒ ① **交付版 = v2.1**（zip 20:38 SHA `835803a7…`）⇒ **v2.0 标 superseded**（`DELIVERY_2.0.json` / `DELIVERY_2.1.json`，只追加字段）② 桌面 **v2.0.lnk 已由 reviewer 21:10 删除** ⇒ `app212` 加 **SUPERSEDED 硬闸门**（被取代 ⇒ exit 2、不写 .lnk；已反证）③ **未通知安装 / 未打包**；今后改动只打 v2.2+ ④ **CORRECTIONS_APP.md 本轮中途被追加 APP-060**（⇒ §125 ⑧ 的「零修改」作废）
- 2026-11-01 21:10 **§125 APP-059 已执行** ⇒ ① **口径 A 作废、口径 B 为唯一口径**（7/12 = 58.33 %、误报 0 ⇒ 仍 FAIL、差 1 个点；**未换口径、未调阈值、未改参照**）② **README_zh/en 写明说话人标签局限**（v2.1 包内 L92-94 / L111-115）③ **更正 §124 两处**（许可证写反 / 「只差 speaker_assets 注释」不成立：实测 5 个 py 不同）④ **补齐 `app/MANIFEST.json` SHA 三元组** ＋ 写明 **v1.13.zip 与目录不一致 ⇒ 不要再从它安装**⑤ **EXT-028 未通过** ＋ **HOWTO 已写**（`shared\ext_listen21\HOWTO.txt`）⑥ **未通知安装、未打包**
## 当前有效结论

> 🔴 **每个数字都注明来源产物**；**被推翻的旧结论不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| 客户包目录 | 🔴 **两个并存**：`Confucius4_LiveCaption_v2.2` = **候选交付版**（APP-061，**待用户抽听 + reviewer 复核**；桌面快捷方式**仍指向 v2.1**）｜ `Confucius4_LiveCaption_v2.1` = **当前交付版**（v2.0 / v1.13 目录仍在，未删除） | `Confucius4_LiveCaption_v2.2/app/MANIFEST.json` → `version=2.2`（`DELIVERY_2.2.json` → `manifest_version`）；v2.1 见 `DELIVERY_2.1.json` |
| 客户包 zip | 🔴 **候选 = v2.2**（**2026-11-02 01:54:03** / **11 233 149 299 B** / **14 317 文件** / SHA256 **`ea5c5c850f8836a7edab982611cdd59d0ba0e83f8d5ff880cc797b7c67c23b75`**）⇒ 含 APP-061 全部代码（①④⑤＋③⑥）＋ EXT 插件 + 桥接服务 ＋ **重签的 `ACCEPTED.json`**（`code_fingerprint=fddb2dc6b06d…` / 28 个生产模块 / `binding_gate=app191`）＋ v2.2 改动说明（zh/en）⇒ **未改桌面快捷方式、未通知用户**（待抽听）｜ **当前交付版仍是 v2.1**（**2026-11-01 20:38:13** / **11 233 135 359 B** / SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`）⇒ **v2.0 首包（17:49 / SHA `8198924f…`）保留不删** | `results/app/DELIVERY_2.2.json` → `sha256` / `bytes` / `mtime`；打包日志 `_pack_v22_run.log` → 「比对 14 317 个文件 / 全部逐字节一致」＋ `testzip()` OK ＋ 「--no-shortcut 跳过桌面快捷方式更新」；v2.1 见 `DELIVERY_2.1.json` |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | TTS 走 NPU（F16 / INT8 视配置） | `app048_layout_1920x1080.png`（语音区实测「语音区 · Intel NPU · F16」） |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出） | `app185_app048_gui_layout_pkg_evidence.json` → `verdict=PASS` / `n_pass=64` / `n_fail=0`（**在客户包内代码上跑**） |
| 桌面快捷方式 | **v2.1 两个**（`Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`，均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证 ⇒ 非坏链）；⚠️ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（**未删**，待用户/reviewer 决定） | `results/app/app212_app057_v21_shortcuts_evidence.json` → `checks`（**9 PASS / 0 FAIL**，含 3 条反证） |
| 说话人识别旁路 | **默认关闭**（`--speaker off` 是默认；GUI 有「说话人识别」勾选框）⇒ v1.13 的阻断级回归已止血 | `results/app/app199_app054_ab_evidence.json` → `checks`（4 PASS / 0 FAIL）；`app197` → T7 |

### 关键数字

| 指标 | 值 | 来源产物 / 字段 |
|---|---|---|
| **说话人标签覆盖率（修复后）** | **93.48 %**（**43 / 46** 句带标签）⇒ 修复前 **7.23 %**（**×12.9**） | `results/app/app202_app053_coverage_evidence.json` → `after.measured_coverage_pct` / `before.coverage_pct` |
| 覆盖率 vs pyannote 自身（1c 口径） | App 原规则 **89.13 %** ⇒ 差 **4.35 pp**；ASR 参考真值 **95.65 %** ⇒ 差 **2.17 pp**（均 ≤ 5 pp） | `app202…` → `pyannote_offline_1c` / `checks`；1c 来源 `app193_app053_spk_frame_audit.json` |
| **旁路开时墙钟（修复后）** | **300.6 s / 300 s 音频** ⇒ reviewer's 缺陷态 **838.5 s**（**×2.79 提速**） | `app199_app054_ab_evidence.json` → `arms[on].wall_s` |
| **旁路开时最大积压** | **1.2 s** ⇒ reviewer's 缺陷态 **195.1 s**（**×163**） | `app199…` → `arms[on].max_backlog_s` |
| **出字延迟中位（旁路开 vs 关）** | **316 ms vs 331 ms** ⇒ Δ = **−15 ms**（≤ +200 ms ⇒ **不增加延迟**） | `app199…` → `arms[].first_char_latency_ms` |
| 旁路开时 RTF | **0.616**（旁路关 **0.632**）⇒ 旁路**不再拖慢** ASR | `app199…` → `arms[].rtf` |
| 旁路线程化闸门（含 4 条反证） | **11 PASS / 0 FAIL**（T8 用 v1.13 包内**旧产物**跑 ⇒ 正确 FAIL ⇒ 判据非恒真） | `results/app/app197_app054_bypass_nonblocking_evidence.json` → `n_pass` / `n_fail` |
| 段自身区间时间对齐闸门（含 2 条反证） | **7 PASS / 0 FAIL** | `results/app/app196_app053_batching_fix_evidence.json` → `n_pass` / `n_fail` |
| 客户包同步「骨架等价」闸门（含 4 条反证） | **10 PASS / 0 FAIL** | `results/app/app201_pkg_skeleton_evidence.json` → `n_pass` / `n_fail` |
| 快捷方式冷启动闸门（COM 读回 + 3 条反证 + 冷启动 ×2 + 截图） | **13 PASS / 0 FAIL** | `results/app/app192_lnk_coldstart_evidence.json` → `n_pass` / `n_fail` |
| `app195` M8 判据缺陷订正 | 原判据**恒假**（簇号 vs 人工编号无语义对应 ⇒ 0 %）⇒ 改为**最优编号置换** ⇒ **82.61 %**（≥ 60 %）⇒ **不是产品缺陷** | `results/app/app200_app053_m8_criterion_evidence.json` → `criterion_defect` / `checks`（3 PASS / 0 FAIL） |
| GUI 三分区布局验收 | **64 PASS / 0 FAIL** | `results/app/app165_app048_gui_layout_evidence.json` → `n_pass` / `n_fail` |
| 失败态 vs 正常态截图像素差 | **9 492 px**（证明不是同一张图） | `app165_app048_gui_layout_evidence.json` → `diff_pixels_normal_vs_failed` |
| 失败态截图 error 红色像素 | **767 px**（整行变色确实生效） | `app165_app048_gui_layout_evidence.json` → `error_red_pixels_in_failed` |
| 说话人资产同步验收 | **30 PASS / 0 FAIL** | `results/app/app164_app047_spk_resync_evidence.json` → `pass_` / `fail` |
| 克隆纯内存等价性 | **10 PASS / 0 FAIL**；mel `max|Δ|=0.000e+00`；入参逐位相同 | `results/app/app161_app045_clone_inmemory_equivalence.json` → `n_pass` / `n_fail` |
| 克隆 vs 旧落盘路径差 | `max|Δ|=4.101e-05` ⇒ **PCM_16 量化误差，非回归**（内存路径更精确） | `results/app/app161_app045_clone_inmemory_equivalence.json` → 判据②b |
| 内置音色不落用户目录 | **5 PASS / 0 FAIL**；用户目录 8 文件已**移出**（备份可回滚） | `results/app/app162_app045_speakerlib_no_copy.json` → `n_pass` / `n_fail` |
| 版本标识一致闸门 | **18 PASS / 0 FAIL**；BUG 组（修复前副本）**D1~D5 全部命中 FAIL** ⇒ 判据非恒真 | `results/app/app170_version_identity_gate_evidence.json` → `pass` / `fail` / `verdict` |
| 打包流水线 dry-run | §48 闸门 **0 处违规 / PASS** ｜ 内部素材 **0 命中** ｜ **结论 PASS** | `pack_v13.py --dry-run --same-version` 本轮实测输出 |
| MiniMax 回转写 CER（预设 A / 克隆） | **3.0243 %** / **3.0901 %**（ed 46 / 47 · ref 1521 字符） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `cer.cuda_preset/cuda_clone.total_cer_pct` |
| 克隆 − 预设A 的 Δ | **+0.0657 pp**，95% CI **[−0.7961, +0.9302]**（**含 0** ⇒ 未构成明显劣化） | 同上 → `pair_cuda_preset_vs_clone.bootstrap.delta_pp` / `ci_lo_pp` / `ci_hi_pp` |
| 判据非恒真（反证组） | 预设臂整体错位 ⇒ Δ = **−125.2465 pp**，CI **[−140.8994, −112.9758]** ⇒ 必判 FAIL | 同上 → `counterproof.swap_arms_bootstrap` |
| APP-050 启动日志 `EXECUTION_DEVICES` 一行 | `talker=NPU`，`cp_prefill=NPU`，`cp_decode=NPU`，`decoder=NPU`×9 | `results/app/app174d_worker_startup_e2e.json` → `key4_line`（真 worker stdout） |
| 各组件落点（直接调引擎） | **17 个组件全 NPU**；`on_cpu=[]`；`on_unknown=[]` | `results/app/app174c_startup_log_evidence.json` → `actual` / `on_npu` / `on_cpu` / `on_unknown` |
| `EXECUTION_DEVICES` 返回类型（实测） | NPU 档 = **字符串 `'NPU'`**；CPU 档 = **列表 `['CPU']`** ⇒ 旧代码 `list(devs)` 把字符串**逐字符拆开** | `results/app/app174a_exec_devices_type.json` → `probes.NPU.raw_type` / `probes.CPU.raw_type` |
| APP-050 离线单测（含 5 条反证） | **34 PASS / 0 FAIL**；反证组**全部命中** ⇒ 判据非恒真 | `results/app/app174b_exec_devices_unit.py` → `n_pass` / `n_fail` / `counterproof` |

### 已撤回的旧结论（**不作为结论**，仅备查）

> 本块已原样归档 ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。

## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| APP-043 | ASR 说话人接口已交付，APP-039/040 克隆资产可取（真机验收全套） | ✅ 链路与结构已通过（`app186` 总闸门）；🔴 **仍需用户实听 3 段 1.2–1.3× 素材**（`shared/app_accel_listen/`）＋ **reviewer 判定音质 / 不变调 / 可懂** |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | ✅ **已闭合**（§123）：`.lnk` 改为 COM 生成（**2 099 B**），COM 读回 `TargetPath` 指向 v1.13 包内 `Start_LiveCaption.bat`；从 `.lnk` 冷启动 **2 次**均成功 |
| APP-048 | GUI 状态信息按 ASR / 翻译 / 语音输出分区 | ✅ 布局代码在 v1.13 包内（`app185` **64/0**）＋ §123 已清理 markdown 星号与研发术语；🔴 **仍缺一张「运行中」截图** |
| APP-049 | 压缩 STATUS / CORRECTIONS | ✅ 本轮（§123 ④）压缩到 ≤ 40 KB / ≤ 300 行；🔴 需 reviewer 确认归档内容与索引表无误 |
| APP-051 | 重打 v1.13 ＋ APP-043 真机验收 ＋ `ACCEPTED.json` ＋ 桌面快捷方式 | ✅ 三条子项全做完；🔴 **待 reviewer 复核 3 项**（见 §117 ⑤） |
| **APP-052 ①** | 桌面 `.lnk` 是**坏链**（手工拼字节 ⇒ 字段错位 4 字节） | ✅ **本轮已完成**：改用 `WScript.Shell.CreateShortcut` 生成；判据改为 **COM 读回**（`TargetPath` 非空 / 所指文件存在 / 在 v1.13 包内 / `LinkFlags` 含目标定位位）＋ **3 条反证**（手工坏链 / 目标不存在 / 指向包外 **必须判 FAIL**）⇒ `app192` **13 PASS / 0 FAIL**；🔴 待 reviewer 复核 |
| **APP-052 ②** | `ACCEPTED.json` 未绑定重打的 zip；子项口径有缺口 | ✅ **本轮已完成**：`code_fingerprint`（app191 口径）＋ `binding_gate=app191` ＋ **6 个编号子项 ＋ `1b_lnk_shortcut`** ＋ 新 `accepted_at`；zip 的 SHA 记在 `DELIVERY_1.13.json`（**不循环**）；**旧 SHA `6576dabd…` / `3ca36ce3…` 已作废**；🔴 **待 reviewer 复核**（3 个口径缺口：`app175` 旧口径 / `app179` B4 **空真** / APP-048 截图只拍到空闲态） |
| **APP-052 ③** | 包内残留 `results/mt2_acc_outputs/*.json` ＋ notes 仍是「v1.6 修订」＋ docstring 写死开发机用户名 | ✅ **本轮已完成**：`pkg_exclude` 增 `results/mt2_acc_outputs/`（**22 个文件**整目录排除，**不误伤** `results/mt2_accuracy.json/.md`）；`pack_v13.py` 增 **v1.13 修订说明** ＋ 历史段落脱敏；3 个 docstring 改为 `<HOME>` 占位；🔴 **打包闸门实测又抓到 2 类真缺陷**（见 §123 ③⑤） |
| **APP-053** | 说话人切换时字幕显示不同说话人（v1.13 覆盖率 7 % 不达标） | ✅ **本轮已完成（修复 + 验收）**：查因 = **段自身区间口径** + **攒整窗喂音**；修复后 **93.48 %**（43/46）⇒ 与 pyannote 自身差 **2.17–4.35 pp**；`app202` **9 PASS / 0 FAIL**；🔴 **待 reviewer 复核**（① `app195` **M8 恒假判据**已订正为最优编号置换 ⇒ 82.61 %；② **GUI 转写区正式行的 `[Sx]` 前缀仍未取到图** ⇒ 记为未达成） |
| **APP-054** | 说话人旁路**同步阻塞 ASR 主循环**（墙钟 838.5 s / 300 s 音频，最大积压 195.1 s） | ✅ **本轮已完成（止血 + 治本定位 + 验收）**：旁路**默认关闭** ＋ **线程化** ＋ **攒整窗** ＋ **降级不反压**；A/B 实测旁路开 **300.6 s / 积压 1.2 s / 延迟 316 ms** ⇒ 三条判据全 PASS（`app199` **4 PASS / 0 FAIL**）；🔴 **根因在 ASR 侧**（`run_seg_side` 每次调用重编译模型）⇒ 已写 NOTICE **待主会话转达**；🔴 待 reviewer 复核（旁路默认关闭是否认可） |

| **说话人标签覆盖率（同段口径 · 修复后）** | **93.75 %**（45/48 句带标签，**分子分母同一段** Q&A 切片 3291.6–3591.6 s）⇒ 与 app193 参照 95.65 % 相差 **1.90 pp**（≤ 5 pp） | `results/app/app208_app058_spk_retest_evidence.json` → `measured.coverage_pct` / `checks` ② |
| **换人点召回率（APP-058 判据④）** | 口径 A **33.33 %**（4/12 命中、误报 3）／口径 B **58.33 %**（7/12、误报 0）⇒ **均 < 60 % ⇒ 未达标**（参照标注自身与人工标注差 1 处 ⇒ 上限 91.7 %） | `app208…` → `measured.switch_analysis`；`app210_app058_recall_diagnosis_evidence.json` → `method_A_index` / `method_B_text_aligned` |
| **v2.1 内容闸门 / 绑定闸门 / 快捷方式 / 依赖隔离** | `app213` **15/0**（8/8 反证）｜`app191` **18/0**｜`app212` **9/0**｜`app214` **4/0**（reviewer 点名的 5 个开发目录 **0** 命中；扫 6 729 个文件） | `results/app/app213_app057_v21_gates_evidence.json` / `app191_v21_binding_evidence.json` / `app212_app057_v21_shortcuts_evidence.json` / `app214_app057_v21_clean_test_evidence.json` |

## 最近章节

> 按 APP-052 ④：**每节最多 3 行的索引**；**§109–§124 正文已原样归档**到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（内含 §124 正文 ＋ 旧「最近更新」条目）与 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`（**逐字保留，内容一字未删**）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。

| 章节 | 一句话 | 状态 |
|---|---|---|
| §109 | APP-047 说话人 IR 精度定案 FP16 ⇒ `asr_spk/` 收敛为 3 文件 | 已归档 |
| §110 | APP-048 GUI 三分区状态条：代码 + 定点同步 + 64 PASS / 0 FAIL | 已归档 |
| §111 | APP-049 压缩：STATUS 1 437 968 B → ≤ 40 KB，原文原样归档 | 已归档 |
| §112 | 客户包「运行时可加载性」21 PASS / 0 FAIL ｜ 修掉「宿主 PYTHONPATH 污染」 | 已归档 |
| §113 | 修掉「版本标识在打包时复发」：新增打包前闸门 + 通用同步脚本 | 已归档 |
| §114 | APP-027 V3(a) MiniMax 回转写 CER 对比：14/0，Δ 的 95% CI 含 0 | 已归档 |
| §115 | APP-050 启动日志打印 `EXECUTION_DEVICES` ⇒ 实测全部 NPU | 已归档 |
| §116 | APP-050 git 收尾（commit / push）｜ 更正 §115 的一处事实错误 | 已归档 |
| §117 | APP-051 三条子项全完成：重打 v1.13 ＋ 真机验收 ＋ `ACCEPTED.json` | 已归档 |
| §118 | 抓到 3 个真缺陷（产物未入库 / clone 打包必失败 / 写死仓库根） | 已归档 |
| §119 | 补上「包 ⇄ 仓库 生产模块集合一致性」（新增 `app188` 闸门） | 已归档 |
| §120 | 闭环「包内代码写死开发机家目录」＋ 修掉两个过期断言 | 已归档 |
| §121 | 抓到 2 个「判据自身缺陷」｜ 连带修掉 `app187` 的 MISSING | 已归档 |
| §122 | 新增「验收证据 ↔ 被验收代码」绑定闸门 `app191` | 已归档 |
| §123 | **APP-052 / APP-053 / APP-054**：`.lnk` 坏链修复 ＋ ACCEPTED 重签 ＋ 标签覆盖率 7 % → 93.48 % ＋ 旁路线程化 ＋ STATUS 压缩 | **本轮新增（见下）** |
| §124 | **APP-055/056/057/058**：v1.13 还原 ＋ 模块租约 ＋ V2.1 交付包 ＋ 同段覆盖率复测 | 已归档 |
| §125 | **APP-059**：口径 B 定为唯一口径 ＋ README 局限说明 ＋ 两处更正 ＋ MANIFEST 三元组 ＋ HOWTO | **本轮新增（见下）** |
| §126 | **APP-060**：交付版 = v2.1 ＋ v2.0 标 superseded ＋ 桌面 v2.0.lnk 已删（脚本加硬闸门） | **本轮新增（见下）** |
| §127 | **APP-061**：用户实测 6 问（CUDA 无声 / 离线无参考音色 / 卡顿 / 克隆 10 s 一次 / 男声被女声播出 / 界面不紧凑）⇒ 代码层全修 ＋ v2.2 包 | **本轮新增（见下）** |
| §128 | 巡检无新纠偏 ⇒ APP-061② `SyntaxWarning` 已修 ＋ 共享锁闸门夹具假 FAIL 已修（42/42）＋ CUDA 置灰核验 ＋ 真机验收 harness 备好（设备级实测因用户会话在跑而未开跑） | **本轮新增（见下）** |
| §129 | **巡检无新纠偏 ⇒ 自查 4 个真缺陷并修掉**（`app224` 移动-HEAD 基线 ⇒ 永久假 FAIL；锁闸门反证谓词恒真；`app223` 3 个缺陷；边车 `_enter_buffered_busy` 崩溃）＋ 回归 29/0・39/0・13/0 | **本轮新增（见下）** |
| §131 | **APP-062（D1–D4：用户对 APP-061 的四项决定）** —— 代码层全完成（D1 窗口同源配置项 / D2 自动开旁路 / D3 客户包去 CUDA / D4 禁 MT+TTS 同 NPU） ｜ **本条需等 reviewer 复核** | 已归档 |
| §132 | **APP-063/064/065**：D4 bug ＋ D2 四入口 ＋ D1 窗口（ASR 未同源⇒跨模块错位）＋ 锁纪律 ＋ **界面重排 5 组**（截图/清单已交）＋ 改名 | **本轮新增（见下）** |
| §133 | **APP-067**：①克隆 0 % 根因（加载期排队 + seg→spk 绑定）＋ ③D4 界面 ＋ ④按钮/高级组截图 ＋ ⑤D1 5 s 窗口 ⇒ **①③⑤ 设备级已完成**；②④ 设备级未做（等锁） | **本轮新增（见下）** |
| §134 | **APP-066**：MiniMVP 最小包 v1.0 的 **6 处硬缺陷（含 P0 无法启动）**已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 构建闸门全绿 / 52.41 % 体积）；(a)(b)(c) 设备级未做 | **本轮新增（见下）** |

### §135 ✅ **APP-067 ②④ 设备级补齐（ABBA + GUI 臂 + ② 交付物）＋ APP-066 3(a)(b) ＋ 🔴 修 MiniMVP P0（rc2）** ｜ **本条已完成（设备级）**（2026-11-05 08:38）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec135_upto_20261105.md`（18 133 B，逐字保留）＋ 本轮追加的 §135–§137 三节原文另见 `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：④ ABBA **10/0** ＋ GUI 臂 **5/0**；② 交付物 **12/0**（`shared/app_listen/v23_clone/`）；3(a) CLI **8/0**；**MiniMVP P0 已修（rc2）**。

### §136 ✅ **APP-068 + APP-069 + APP-070 三条新纠偏的代码侧全部落地 ＋ MiniMVP rc3 已出（设备级 3(a) PASS 9/0）** ｜ **本条已完成（代码 + 部分设备级）**（2026-11-05 11:20）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec136_upto_20261105.md`（12 364 B，逐字保留，含 9 项速查表）＋ `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：APP-069① 根因＝**rc2 的 24 段全零是「落盘算法」假象**（`app267` 6/0）；dump 已修（顺序拼接＋回填 `wav_t0`/`wav_t1`/`peak`/`rms_db`）；内容判据 `app268` **4/0**；APP-068 `app266` **7/0**；APP-069⑤ 5 项清理全落地（含 torch 拆 `backends_torch.py`）；APP-070① **删 IR 清单已出（8 个 / 975.9 MB，一个都没删）**；rc3 **6 843.8 MB / 10 503 文件**；设备级 3(a) **PASS 9/0**（wall 381.86 s / 76 句全成）；APP-069② `--check` 臂 **10/10 零崩溃**。

### §137 ✅ **无新纠偏（70 条 = last_ack APP-070）⇒ 按 APP-046 从 §136 断点续做** ｜ **APP-069⑥ 已完成｜①③④ 需等 reviewer 复核**（2026-11-05 13:37）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec137_20261105.md`（9 705 B，逐字保留，含 14 个产物的字节数／mtime／SHA256 清单）＋ `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：APP-069⑥ MT INT4 vs INT8 **本条已完成**（46 段／`exact_same_pct=4.35`）；🔴 夹具缺陷**已修**（首跑 `APP273_EXIT=2` ＝ 0 段）；口径差异已说明（reviewer 写 76 段，本机英文定稿 **46**）；APP-069② GUI 臂 **需等 reviewer 复核**（`--check` 10/10 零崩溃 ✅，GUI 有效启动 0/10）；本轮回收 2 个孤儿机器锁（`OpenProcess err=87` 确证死）。

### §138 ✅ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成** ｜ **APP-071 仍未完成（BLOCKING）** ｜ **本条需等 reviewer 复核**（2026-11-05 15:28）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec138_20261105.md`（**28 336 B**，逐字保留，含 README 全文、全部产物元数据、闸门原始字段）。
> 🔴 开工/收尾 `CORRECTIONS_APP.md`：**SHA `f6001a0a…`／212 229 B／mtime 2026-11-05T14:33:28.815547／72 条**（APP-001..APP-072）⇒ **逐字相同**（reviewer 本轮未追加；本模块**只读、未改、未提交**）。**last_ack：APP-070 → APP-072**（APP-072 原文要求；**APP-071 编号更小但仍未完成** ⇒ 见 ⑨）。

| # | 事项 | 结论 | 证据 |
|---|---|---|---|
| ① | **zip 已出（§1）** | `shared/minimvp/…_v1.0-rc3_perftest.zip`：**5 591 630 138 B**／**10 474 条目**／SHA `dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1`／7-Zip **BELOW_NORMAL** 后台／`wall_s=157.49`／`rc=0`／`n_mismatch=0` | `app279_rc3_perftest_zip_evidence.json`（1 259 B） |
| ② | **闸门① 黑名单** | **6/0**（扫**解压副本**非源目录）：会议录音／克隆 npz／`tts_speakers`／babelvox 示例音色／开发目录绝对路径／torch·CUDA dll·pyd·cu·cuh **各 0**；🔴 **反证**：同脚本扫源目录 ⇒ 判据④ **FAIL**（抓到 8 个 babelvox 示例音色）⇒ 非恒真 | `app281_rc3_blacklist_scan_evidence.json`；反证 `_app281_counterexample_srcdir.json` |
| ③ | **闸门② NOTICE** | **PASS**：9 643 B／SHA `b4505621…` ⇒ **10 339 B**／SHA `e9c9cfc3…`；三块定点替换各 **hits=1**；`crlf_preserved=true`；必含 `Qwen3-ASR-0.6B`／`Qwen3-TTS`／`Hy-MT2-1.8B`／`OpenVINO 2026.4.1`／`BabelVox`／`babelvox-openvino-int8` 全 true；⚠️ **未**声称随包附模型许可证全文 | `app278_rc3_notice_patch_evidence.json`（`verdict=PASS`） |
| ④ | **闸门③ `--check`** | **5/0**：`rc=0`／`wall_s=11.86`／含「环境正常」／`n_gpu0_hits=3`／`n_npu_hits=8`／`n_asr_backends=3`；原始结论行「**环境正常。ASR 可用后端 3 个，Intel 集显可用。**」；⚠️ CUDA Q8_0/Q4_K 显示「模型齐全」是**开发机 `~/confucius4-r2t2` 残留**（`_cuda_root()` L428-441）⇒ **包内无 CUDA**（`cuda/` 不存在、`*.cu/*.cuh/*.ptx` 0 个、`*torch*.dll/*.pyd` 0 个） | `app282_rc3_check_evidence.json` ＋ `app282_rc3_check_output.txt`（2 694 B／SHA `05de9cdedcf9a674…`） |
| ⑤ | **闸门③ GUI 冒烟** | **5/0**：`tts_load_s=8.5`／`model_loaded_at_s=27.9`／`wall_s=28.46`／`tts_device=NPU`；主窗口 `client=[1439,1093]`／`bytes=43745`／`all_black=false`／`is_main_window=true`；**字幕区 `rows_with_ink=163`／`max_row_ink=373`**；**负对照 `control_rows_with_ink=0`**；`crash_marker_found=false`；截图核验：标题「实时字幕 MiniMVP v1.0」＋五组齐全＋ASR「就绪 RTF 0.56」＋MT「就绪 延迟 387 ms」＋字幕已渲染中英双语 | `app280_rc3_gui_smoke_evidence.json`（10 076 B）＋ `app280_rc3_gui/gui_rc3.png`（65 925 B／SHA `61a99040b518e46d…`） |
| ⑥ | 🔴 **判据缺陷已修并复跑** | 首跑 3 PASS／**1 FAIL**：第③项抓 CLI 串 `[gpu_int8] 加载 x s`，而 **GUI 模式下 ASR 就绪只写状态栏**（`var_status.set`，`app/live_caption_app.py` L3367）⇒ **不落盘** ⇒ 恒 `None` ⇒ **假 FAIL**（截图证明 GUI 当时正常）⇒ 改**字幕区像素判据**＋**负对照** ⇒ 复跑 5/0；另**独立反证**：真图字幕区涂白 ⇒ `rows_with_ink=0` ⇒ 必 FAIL | `_counterexample_blank_caption.png` |
| ⑦ | **打包一致性对账** | rc3 目录相对打包前快照（10 503 条）：**新增 1**（`README_perftest.txt`）／**删除 0**／**大小变化 1**（`NOTICE` 9 643→10 339 B）／**其余 10 502 个文件 size+mtime 逐条未变** ⇒ ✅ **除 NOTICE 补丁＋新增 README 外一个字节都没动** | `shared/_rc3_snapshot_before_pack.json` |
| ⑧ | **README_perftest.txt** | **9 155 B**／SHA `da3cd8ca1dabb1e28fdafb9ba243111f03daf513177782c6f7b545f32daa62b9`／LF／无 U+FFFD／**已进 zip**；覆盖 reviewer 全部小节（定位／系统要求＋**实测驱动号** NPU `32.0.201.14005`·集显 `32.0.101.8508`／内存 **≥16 GB** 且**明确 APP-070 的 8 GB 是磁盘不是内存**／磁盘 ~6.7 GB＋缓存 ~8 GB＋`%LOCALAPPDATA%\Confucius4LiveCaption\`／已知问题 5 条／CLI 测法＋`Get-Counter` 采 CPU 的原因「包内无 psutil」／带回清单／日志关键行／**Panther Lake 基准对照**，数字全取自已落盘 `app271`·`app263`·`app264`） | 全文见归档件 §3 |
| ⑨ | ⛔ **APP-071 未完成（BLOCKING）** | 本轮**只完成根因分析第一部分**：S2 首次登记段**确为** `seg_id=1`／`t0=9.6`／`t1=19.2`／`span=9.6 s`／**`spk_conf=0.1292`**／`spk_source=retry`／`switch S1→S2` ⇒ **与 reviewer 怀疑吻合**；🔴 **当前代码完全没有 `spk_conf` 门槛**（`speaker_voice.py` 的 `note_final()`/`ready_to_embed()` 只看 `dur_s` vs `MIN_S=1.5`/`REFINE_S=3.0`）⇒ 低置信度首检会被直接登记；`_pending_spk_voice` 只有「模型未就绪排队」语义，**无「低置信度 pending」**。⇒ **(a)(b)(c)(d) 全未做**：诊断未落盘／余弦矩阵未算／**产品代码一行未改**／`v23_clone_r2/` 未生成 ⇒ **v2.3 不打包** | `shared/app_listen/v23_clone/seg_voice_table_by_seg.csv`；`live_caption/speaker_voice.py`、`live_caption/live_caption_app.py`（只读） |
| ⑩ | **纪律自检** | ✅ 未改 `CORRECTIONS_APP.md`／✅ 未覆盖·未删任何旧目录旧 zip／✅ 不用 `--same-version`／✅ `live_caption/` **一行未改**／✅ 设备作业全持 `MACHINE_LOCK`（PID 43172·6828）＋ session_lease `addpid`／✅ 安静窗口 45 s 通过／✅ **未通过 FTP 或任何外部服务分发**／✅ **未通知用户**（等 reviewer 转告）／⛔ **未打 v2.3** | 逐条明细见归档件 §6 |

🔴 **本轮产物 15 个**（仓库内）＋ 3 个包外产物 ⇒ **全量字节数／mtime／SHA256 见归档件 §5**。
🔴 **本轮 git**：main 分支普通 push（未 force）；只 `git add` App 模块自己的文件；🔴 **绝不提交 `CORRECTIONS_APP.md`**、**不吞** ASR／MT／TTS 其它模块的未提交改动。
