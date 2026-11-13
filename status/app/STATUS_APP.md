# STATUS_APP

last_ack: APP-107
更新时间: 2026-11-13 10:26:18
当前任务: **执行 APP-107**（MiniMVP **翻译模型改 INT8-CW** ⇒ 出 **rc11**，rc10 不改）｜**rc11 已打好并验收 PASS**（包目录 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc11`；zip `C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc11_perftest.zip`）｜`models/mt/` **只带** `mt2-int8sym-cw-q`（12 文件 / 1 812 121 487 B，逐文件 SHA256 与拷贝源一致）｜**行为级**默认/`auto` ＝ **INT8-CW**（`MT_ENGINES` 无 INT4）｜MANIFEST 记录拷贝源路径 + hidden_size 2048 / num_hidden_layers 32 + INT8_SYM 按通道｜**整链**：ASR RTF **0.735**、翻译中位 **763.5 ms** / P95 **1354.0 ms** / TTFT **228.1 ms** / **23.9 tok/s**、TTS **提交 155 / 播完 99 / 丢弃 56**、`CL_OUT_OF_RESOURCES` **0**｜README 三份的「A 机实测」**每个数字注明设备组合** + 补本包整链数字（数字从验收 json 生成）｜**未改 rc10**（只读）、**未改客户包**、**A 的真实 device_config 前后 SHA 一致**、**未调 MiniMax**、**未通知用户**
阻塞 / 待用户决定: 🔴 **APP-107 §1–§2 已闭合**（rc11 打好 + 包上验收 PASS）｜🔴 **待 reviewer 复核**：**rc11 的整链数字**（**ASR RTF 0.735** vs rc10 的 0.538；MT 中位 **763.5 ms**（rc10 383.5 ms）；TTS 播完 **99/155**（rc10 126/158））——INT8 使 **ASR+MT 同占 GPU.0** 更重，**性能是否可接受**由 reviewer 裁定｜🔴 **待用户决定**：**10 个带 APP-086·2a 缺陷的包**（完整版 v2.2／v2.3／v2.3_aborted／v2.4 ＋ MiniMVP v1.0／rc1–rc5）作废还是标注（**目录不要删**）｜**完整版 v2.5 必须带收窄才可交付**（闸门④ 已 fail-closed；未打包）｜**当前交付版仍是 v2.1**｜🔴 **待 B 机 rc11 实测**｜**EXT 换嵌**待 reviewer 通知｜**GUI 布局修复仍未同步客户包**
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）｜**§167 压缩**：§167 正文整块归档 ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12 277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）｜**§168 压缩**：§168 正文整块归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8 599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）｜**§178–§180 压缩**（APP-101 §1.d「每节不超过 3 行速查」）：三节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec178_180_20261112.md`（块 SHA256 `d91b34ffed16ff1b22f0dd369c66bd9477351a8e782f327ff1740f0b44113705`）；活文档三节各留 1 行速查｜**§141–§160 压缩**：20 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜**§171–§180 压缩**：10 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜**§170 + §183 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（块 SHA256 见 §185）｜**§186 + §187 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）｜**「最近更新」5 条较旧条目（APP-104／APP-102／接单 APP-101／APP-099×2）整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_20261113.md`（块 SHA256 见 §188）｜**§188 压缩**（2026-11-13）：§188 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec188_20261113.md`（块 SHA256 见 §189 末）｜**§189 压缩**（2026-11-13）：§189 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec189_20261113.md`（块 SHA256 见 §190 末）｜**§190 压缩**（2026-11-13）：§190 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec190_20261113.md`（块 SHA256 `184a60612732eeffd7d6893cce15b7599d875a6df8227a0d7aace2eb4f09fbbc`）｜**§135–§140 标题块压缩**：标题行＋指针行整块逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_headers_20261113.md`（块 SHA256 `7a3e4ba75f5c030e339ae131ca06d2b7027a91086fda9113ed060dad6f29be75`）｜**「最近更新」较旧 1 条（2026-11-12 16:51:46「APP-105 执行完（rc10）」）整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261112.md`（块 SHA256 `1d58e96d85cc862067351ba99bfb5bed3d9c0e3b9854c78a08d77e25aa58558b`）


## 最近更新
> 🔴 2026-11-13 10:26:18 ｜ **执行 APP-107**：**MiniMVP rc11 已打**（翻译模型 **INT8-CW**，`models/mt/` 只带 `mt2-int8sym-cw-q`，12 文件 / 1 812 121 487 B，逐文件 SHA256 与拷贝源一致；**rc10 原样未改**）｜**包上验收 PASS**：静态 7 项 + `--check` exit 0（**INT8-CW（默认）**）＋ **10 分钟整链** exit 0（ASR RTF **0.735**、MT 中位 **763.5 ms** / P95 **1354.0 ms** / TTFT **228.1 ms** / **23.9 tok/s**、TTS **155/99/56**、`CL_OUT_OF_RESOURCES` **0**）＋ **10 语种 MT 30/30 + TTS 30/30** ＋ GUI verdict PASS｜README 三份的实测数字**每个注明设备组合**（数字从验收 json 生成，**打包缺它就拒绝**）｜**A 的真实 device_config 前后 SHA 一致**（探针用隔离 LOCALAPPDATA：缓存 junction，配置独立）｜未调 MiniMax、未通知用户
> 🔴 2026-11-13 09:33:57 ｜ **执行 APP-106**（纠偏文件 **106 条**／最大 **APP-106**／SHA `aab1d83a…`／**352 203 B**／mtime 11-13 09:07:45）｜**§1 落地**：A 的真实 `device_config.json` 用 app493 备份**还原回 59 B**（前 SHA `0971eb73…`／108 B → 后 SHA `9d484c1c…`／59 B，**与备份逐字节一致**）｜**§4 落地**：交付配置表把 **v2.2 改为「带 APP-086·2a 缺陷，不能交付」**（交付版仍是 v2.1）＋ **本轮零新建 `app5xx` 判据脚本**｜**§2 顺延**下一个包（rc11／换 EXT）改 README 数字，**rc10 不重打**｜**§3 记录**：空 `__pycache__` 目录不进 zip｜**§0**：reviewer 独立复核 rc10 通过 ⇒ 直接交 B 机｜**未打包／未改产品代码／未改客户包／未调 MiniMax／未通知用户**
> 🔴 2026-11-13 08:21:30 ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜**修掉 2 个 App 侧真缺陷**：① **打包闸门④ 看不见「终端 else 回落预设 A」兜底**（AST 里 `else` 体挂在最内层 If 的 `orelse` 上 ⇒ 不属于任何 If 的 `body`）⇒ 实测：兜底被废掉／删除时闸门④ 仍 **rc=0 放行**而行为判据 **B3 FAIL**（真串音）⇒ **fail-open**（已修：新增 `_terminal_else`／`_fallback_calls` ＋ 终端 else 兜底检查）② **MUST 清单缺 TTS 生产模块** ⇒ 改前闸门④ 对「包内无 `app/tts_worker.py`」**SKIP 放行** ⇒ 可交付**没有 TTS 的包**（已修：MUST 增 3 条 ＋ 缺文件改判 FAIL）｜新证据 `app522`（合成 **9/9**、真包 **17/18**、e2e 闸门链 ④ 在建 zip 之前）＋ `app523`（**VERDICT PASS**，18/18 真包齐全 ⇒ 不误伤）｜**真包判定未变**（10 个带缺陷包仍 FAIL／8 个通过包仍 PASS）｜复跑既有闸门 3/3 复现 §185／§188／§189 结论｜未打包、未改客户包、未改产品代码、未通知用户
> 🔴 2026-11-13 06:49:24 ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜**修掉 2 个 App 侧真缺陷**：① **打包闸门④的检测范围有洞** ⇒ 只看分支条件里的 `_has_clone_voice()` ⇒ **分支①**（`if self.clone_mode and not _bound:`）看不见 ⇒ 实测「分支①去守卫」⇒ 闸门④ 仍 PASS 而行为判据 **B3 FAIL**（真串音）⇒ 改为「分支体里自己执行 keep-logger 调用」也算（**不下钻进嵌套 If**）＋ **守卫必须指向真实存在的绑定**（`not self._bound` 整个模块不存在）② **app512 漏扫 10 个 MiniMVP 包** ⇒ 实测 **MiniMVP v1.0/rc1–rc5 也缺 APP-086·2a 收窄**｜新证据 `app521`：**静态闸门④ × 行为判据 app157 B3 交叉验证**（合成 12/13、真包 17/18、e2e fail-closed PASS）｜复跑既有闸门 3/3 复现 §185／§188 结论｜未打包、未改客户包、未改产品代码、未通知用户
> 🔴 2026-11-13 04:46:11 ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门④判据本身 fail-open** ⇒ 旧判据「test 树里出现过 `not _bound`」会放行 ①`not _bound` 挂在 OR 上 ②悬空调用（两者改前都 PASS）⇒ 改为「分支条件**逻辑蕴含** `not _bound`」＋悬空调用登记｜合成矩阵 **12/12**、真包矩阵 **9/9 判定未变**（v2.2／v2.3／v2.4 FAIL；v2.1／v2.0／v1.13／rc10／dev PASS）、e2e fail-closed **PASS**｜复跑既有闸门 3/3 复现 §185 结论｜未打包、未改客户包、未改产品代码、未通知用户
> 🔴 本节 5 条较旧「最近更新」条目（APP-104／APP-102／接单 APP-101／APP-099×2）原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261113.md`（块 SHA256 见 §188）；活文档本节仅留本指针行。｜**另 2 条**已归档 ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261112.md`（2026-11-12 16:51:46「APP-105 执行完（rc10）」）＋ `status/archive/STATUS_APP_recent_updates_upto_20261113b.md`（2026-11-13 03:32:16「巡检：无新纠偏 ＋ 新增打包闸门④」）；活文档保留最近 **5** 条。
> 🔴 本节 7 条较旧「最近更新」原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261111.md`（块 SHA256 `35882165a9e7ba88a39e134ea72a81cee4a4f3d41961c751cb6a359097eed9fe`／5198 B）；速查：APP-098 rc6 修整／§169 两真缺陷／§168 ABBA／APP-093 §3+APP-097 §2 补齐／APP-094-096 rc5／APP-093 ack／rc4 zip。
> 🔴 本节 6 条较旧「最近更新」原文（rc4 已建／APP-086②／§139-140 索引／2026-11-05 及更早索引／APP-085／APP-086-088 ack）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261110.md`（块 SHA256 `84ffe113eeb4d580a1e8e3f3919f37409b9798f515da21dbf2e24109bcf2a236`）；本节只留 rc4 zip 与 APP-093。
## 当前有效结论

> 🔴 **每个数字都注明来源产物**；**被推翻的旧结论不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| 客户包目录 | 🔴 **两个并存**：`Confucius4_LiveCaption_v2.2` = 🔴 **带 APP-086·2a 缺陷，不能交付**（APP-106 §4 裁定：reviewer 11-13 grep 复核 `Confucius4_LiveCaption_v2.4\app\tts_worker.py:1741` = `elif self._has_clone_voice():`，**缺 `and not _bound`** ⇒ 按句绑定 + 标签晚到会**沿用上一句克隆音色（串音）**；**v2.2 不得再当候选交付版**；**目录保留不删**，作废还是标注**等用户决定**）｜ `Confucius4_LiveCaption_v2.1` = **当前交付版**（v2.0 / v1.13 目录仍在，未删除；桌面快捷方式**仍指向 v2.1**）｜ 🔴 **带缺陷的包共 10 个**：完整版 **v2.2／v2.3／v2.3_aborted／v2.4** ＋ MiniMVP **v1.0／rc1／rc2／rc3／rc4／rc5**（**目录一律保留不删**） | `Confucius4_LiveCaption_v2.2/app/MANIFEST.json` → `version=2.2`（`DELIVERY_2.2.json` → `manifest_version`）；v2.1 见 `DELIVERY_2.1.json`；缺陷判定见本文件 §191 ⑤（`results/app/app522_gate4_fallback_scope_evidence.json`、`app523_pack_must_ttsworker_evidence.json`） |
| 客户包 zip | 🔴 **v2.2 zip 不得再当候选交付**（**11 233 149 299 B**／SHA `ea5c5c85…`／2026-11-02 01:54:03／14 317 文件 ⇒ **带 APP-086·2a 缺陷**，见上行「客户包目录」）｜ **当前交付版仍是 v2.1**（**2026-11-01 20:38:13** / **11 233 135 359 B** / SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`）⇒ **v2.0 首包（17:49 / SHA `8198924f…`）保留不删**；**v2.5 未打包**（必须带 APP-086·2a 收窄，闸门④ 已 fail-closed）｜ MiniMVP **rc10** zip `shared\minimvp\…rc10_perftest.zip` **5 926 048 165 B**（11-12 16:49:06）（reviewer 11-13 09:00–09:05 已独立复核通过 ⇒ 直接交 B 机） | `results/app/DELIVERY_2.1.json` → `sha256` / `bytes` / `mtime`；rc10 zip 磁盘实测（11-13 09:29:32）；本文件 §191 ⑧ |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | 🔴 **APP-101 §0.3 / APP-102 §0（用户 11-12 决定）**：完整版 TTS 与克隆（说话人编码器／x-vector）→ **GPU.0**；MiniMVP **rc10** TTS → **NPU**（克隆置灰）｜**MiniMVP rc10 已进包**（出厂默认实测 `GPU.0/GPU.0/NPU`）；**完整版 v2.5 未打包** | `live_caption/device_config.py:69-74`；`app486_app102_rc8_smoke.json` → `factory_default_probe.default_devices`；本文件 §191 ⑧ |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出） | `app185_app048_gui_layout_pkg_evidence.json` → `verdict=PASS` / `n_pass=64` / `n_fail=0`（**在客户包内代码上跑**） |
| 桌面快捷方式 | **v2.1 两个**（`Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`，均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证 ⇒ 非坏链）；⚠️ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（**未删**，待用户/reviewer 决定） | `results/app/app212_app057_v21_shortcuts_evidence.json` → `checks`（**9 PASS / 0 FAIL**，含 3 条反证） |
| 说话人识别旁路 | **默认关闭**（`--speaker off` 是默认；GUI 有「说话人识别」勾选框）⇒ v1.13 的阻断级回归已止血 | `results/app/app199_app054_ab_evidence.json` → `checks`（4 PASS / 0 FAIL）；`app197` → T7 |
| MiniMVP 默认设备（rc10 代次） | 🔴 **rc10 出厂默认 = ASR **GPU.0** / MT **GPU.0** / TTS **NPU**（第 2 代，`CONFIG_DEFAULTS_VERSION=9`）（**取代** rc8 的「ASR NPU / MT GPU.0 / TTS GPU.0」）；`device_config.DEFAULT_DEVICES` 为唯一事实来源，GUI `_dev_selected` 与 CLI `get_devices()` 同源（无第二份字面量）｜ **dev 树与 rc10 包内 `app/device_config.py` 逐字节同 SHA**（`ea470419…`／35 189 B） | `live_caption/device_config.py` → `_DEFAULT_DEVICES_MINIMVP`（注释：APP-105 §7「用户 2026-11-12 14:30 决定」）；包内 `Confucius4_LiveCaption_MiniMVP_v1.0-rc10/app/device_config.py`（磁盘实测 11-13 09:29） |
| 磁盘最新完整版包 | `Confucius4_LiveCaption_v2.4/` 与 `Confucius4_LiveCaption_v2.4.zip`（**11 235 954 241 B** / 2026-11-07 23:04）在位；**v2.5 未打包**；v1.5 / v1.13 / v2.0–v2.3 / `v2.3_aborted_20261107_1517` 均保留未删 | 磁盘实测 `ls -d` / `ls -la`（2026-11-12 09:47） |
| 磁盘最新 MiniMVP 包 | 🔴 **rc11 已打**（APP-107）：`Confucius4_LiveCaption_MiniMVP_v1.0-rc11/`（**10 629 文件**／**6.28 GiB**；`models/mt/` 只带 **INT8-CW** `mt2-int8sym-cw-q`）＋ `~/shared/minimvp/…rc11_perftest.zip`（**6,697,683,352 B**）｜**包上验收 PASS**（静态 7 项 + `--check` + 10 分钟整链 + 10 语种 MT/TTS 30/30 + GUI）｜**rc10 及更早目录/zip 全部保留未删**（rc6 已按 APP-099 移入回收站，可逆） | `results/app/app524_minimvp_rc11_build_evidence.json`；`results/app/app526_app107_rc11_acceptance.json` → `verdict`；`results/app/app528_app107_rc11_10lang_smoke.json`；本文件 §192 |

### 关键数字

> 🔴 本表已**整表逐字归档** ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（块 SHA256 `0b1e0843e6192300fe8d72fbeb1965d2464d1df93e15ab1e3b2c4cca15131d0a`）。
> 🔴 表内每行均注明「来源产物 / 字段」⇒ 可按文件名完整追回；**本轮（APP-093 §3 / APP-097 §2）的关键数字见 §167**。

### 已撤回的旧结论（**不作为结论**，仅备查）

> 本块已原样归档 ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。

## 未完成纠偏

> 🔴 本表（APP-043..APP-054 与 3 行关键指标）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_unfinished_corrections_upto_20261106.md`；正文一字未删。
> 🔴 **速查**：APP-045/047/048/049/050 已闭合；APP-043/051/052/053/054 均「已完成、待 reviewer 复核」；🔴 APP-048 仍缺「运行中」截图、APP-053 仍缺转写区 `[Sx]` 前缀截图、APP-043 仍需用户实听 3 段素材。
## 最近章节

> 按 APP-052 ④：**每节最多 3 行的索引**；**§109–§124 正文已原样归档**到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（内含 §124 正文 ＋ 旧「最近更新」条目）与 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`（**逐字保留，内容一字未删**）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。

> 🔴 **§109–§139 的「最近章节」索引表已整表逐字归档** ⇒ `status/archive/STATUS_APP_sec109_139_index_20261113.md`（块 SHA256 `5937553dc219a9d689d3ca4b85442a81d22b83fb592f0c4d424c044cd0168463`）；活文档本处留此指针行。
## §135–§140（本批 6 节｜**标题行＋指针行已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec135_140_headers_20261113.md`（块 SHA256 `7a3e4ba75f5c030e339ae131ca06d2b7027a91086fda9113ed060dad6f29be75`）｜活文档留此指针行

## §141–§160（本批 20 节｜注意**无 §161**）｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜活文档留此指针行

## §162 执行 APP-089/090/091/092（last_ack=APP-092）｜移植完成＋NPU 验收已跑 ⇒ **停在等 reviewer 复核**（2026-11-10 06:29:03）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec162_20261110.md`（5052 B／块 SHA256 `3098e4dd75a6444fbb7424ba67e38d49bdad838cf162649d9022b9b7827131c6`）；**§164 已撤回本节 ③④⑤ 的错误结论**（`app394.verdict=FAIL`／`app391…json` 幻影产物／「RTF≈0.90」笼统口径）。原文未删一字，按「只追加、不回改旧结论」纪律以索引替代。

## §163 MiniMVP rc4 打 zip 完成（用户 2026-11-10 指示「打包 rc4 吧」）
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec163_20261110.md`（3299 B／块 SHA256 `3cf5cc22541fdd65da07bc58211757c056c83d8f37eccef551020957ad9ed3ef`）。
## §164 执行 APP-093（last_ack=APP-093）｜§162 复核：验收 **FAIL** 如实入册、静态诊断＋STATUS 更正已完成 ⇒ 设备作业未跑，**本条需等 reviewer 复核**（2026-11-10 08:49）
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec164_20261110.md`（7496 B／块 SHA256 `d1b7efee44eb62e30d82e286916d327fdf0da8bf4f8f33aa419819ad70747f3a`）。

## §165 执行 APP-094 / APP-095 / APP-096（last_ack=APP-096）｜MiniMVP **rc5**（ASR→Qwen3-ASR-0.6B）已出包＋设备验收；**APP-093 设备作业部分完成**，停等 reviewer 复核
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec165_20261110.md`（7828 B／块 SHA256 `49b14a8f57e3817a569a202979ac4efd33b5783f4a6b253b32c7a9b05017b7e6`）。

## §166 执行 APP-097（last_ack=APP-097）｜目标语言扩到 10 种（静态部分完成）｜**逐语种设备验收未跑 ⇒ 需等 reviewer 复核**

> 🔴 本节正文已整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 `ddc46f321b1833cf7c04be048847a55f57677eaac4004fdc9fd405f93eb85f3f`）

## §167 续做 APP-093 §3 + APP-097 §2 设备验收（last_ack=APP-097，2026-11-10 15:59）｜**§3.7 截图 PASS（含一个阻断级真缺陷的根因修复）**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）。

## §168 巡检（last_ack=APP-097，2026-11-10 16:53:01）｜**无新纠偏**；补做 APP-093 §3.6「切段开/关的 ASR RTF」对照（设备跑，持锁，ABBA）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）。

## §169 巡检（last_ack=APP-097，2026-11-10 18:51:52）｜**无新纠偏**；查出并修掉 2 个 App 侧真缺陷（§167 归档件引用了不存在的产物路径／旁路窗长注释与 ASR 现状不符）＋ 新增 3 道静态闸门｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec169_20261110.md`（6978 B／块 SHA256 `f0f1735aaeb0b256cd8ffe565fed085ebe7f1879cd2d453d3942e7099d19c898`）。

## §170 与 §183｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（4713 B／块 SHA256 `ded2cae481bf6ca175f7a1a71255ad508e12318edc862bf413737f180cd345a8`）｜活文档留此指针行
## §171–§180（本批 10 节）｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜活文档留此指针行

## §181 接单 APP-101 / APP-102（2026-11-12 09:46:41）｜静态前置完成；设备作业与 rc8 未做
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec181_182_body_20261113.md`（块 SHA256 `4e101ee84c2ca7e3361a1b431ae2cc26acc74b8df81e9472bb6d2092aaf52db4`）；活文档保留标题行 + 1 行指针。
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec181_182_body_20261113.md`（块 SHA256 `4e101ee84c2ca7e3361a1b431ae2cc26acc74b8df81e9472bb6d2092aaf52db4`）；活文档保留标题行 + 1 行指针。

## §182 执行 APP-102 / APP-103（2026-11-12 10:44:44）｜rc8 已打并验收 6/6 PASS；撤回 §181 的「未做／等裁定」结论
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec181_182_body_20261113.md`（块 SHA256 `4e101ee84c2ca7e3361a1b431ae2cc26acc74b8df81e9472bb6d2092aaf52db4`）；活文档保留标题行 + 1 行指针。
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec181_182_body_20261113.md`（块 SHA256 `4e101ee84c2ca7e3361a1b431ae2cc26acc74b8df81e9472bb6d2092aaf52db4`）；活文档保留标题行 + 1 行指针。

## §170 与 §183｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（4713 B／块 SHA256 `ded2cae481bf6ca175f7a1a71255ad508e12318edc862bf413737f180cd345a8`）｜活文档留此指针行

## §184 执行 APP-105（last_ack=APP-105，2026-11-12 16:51:46）｜MiniMVP rc10 已打并验收 13/13 PASS｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec184_20261113.md`（6953 B／块 SHA256 `b746af218d24a41132c6e13a081495c2e9a9044357869f66c35441787ca94cfb`）。
## §185 巡检（last_ack=APP-105，2026-11-13 00:43:00）｜**无新 reviewer 纠偏**；接上个会话断点修好 **app157 判据**（**判据层，产品代码零改动**）｜🔴 **查明完整版 v2.2/v2.3/v2.4 仍带 APP-086·2a 串音缺陷**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec185_20261113.md`（块 SHA256 见 §187 末）；活文档保留本标题行 + 1 行指针。
## §186 巡检（last_ack=APP-105，2026-11-13 02:03:00）｜**无新 reviewer 纠偏**（6 通道全查空）｜复跑既有闸门 3/3 **复现 §185 结论**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）；活文档保留 §186 标题行 + 1 行指针。
## §187 巡检（last_ack=APP-105，2026-11-13 03:32:16）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门放行 APP-086·2a 缺陷**（新增打包前闸门④）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）；活文档保留 §187 标题行 + 1 行指针。


## §188 巡检（last_ack=APP-105，2026-11-13 04:46:11）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门④的判据本身是 fail-open**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec188_20261113.md`（块 SHA256 `d7ffc944c78957d906d55838b9bc6d93fb6df3cfe5fba9c57dcb66473db30b0c`）；活文档保留 §188 标题行 + 1 行指针。

## §189 巡检（last_ack=APP-105，2026-11-13 06:49:24）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 2 个 App 侧真缺陷：打包闸门④的检测范围有洞（分支① 看不见）＋ 守卫可指向不存在的属性；app512 漏扫全部 MiniMVP 包**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec189_20261113.md`（7151 B／块 SHA256 `854c5f07dc196c4e969701ce9b9bb2e0b624f16bd87735d621146fdc3f0d1b21`）；活文档保留 §189 标题行 + 1 行指针。

## §190 巡检（last_ack=APP-105，2026-11-13 08:21:30）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 2 个 App 侧真缺陷：① 打包闸门④ 看不见「终端 else 回落预设 A」兜底（串音可放行）② MUST 清单缺 TTS 生产模块 ⇒ 可交付「没有 TTS 的包」**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec190_20261113.md`（块 SHA256 `184a60612732eeffd7d6893cce15b7599d875a6df8227a0d7aace2eb4f09fbbc`）；活文档保留 §190 标题行 + 1 行指针。

## §191 执行 APP-106（last_ack=APP-106，2026-11-13 09:33:57）｜**§1 已完成**（还原 A 的真实 device_config）＋ **§4 已完成**（交付配置表改判 v2.2 不可交付）｜ **§2 顺延下一个包**｜ **§3 已记录**｜ **本条需等 reviewer 复核**
> **① 纠偏文件复核（只读、未改、未提交）**：开工＝收尾 **106 条**／最大 **APP-106**／SHA `aab1d83a99e0bfaac19791f62f6060ae30eb0628504f93997d7d6ca456f4d62b`／**352 203 B**／mtime **2026-11-13 09:07:45** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` 升 **APP-106**（reviewer 的编号，本轮已执行）。
> **② 其它通道全空（⇒ 无遗漏指令）**：`shared/NOTICE*` 最新仍 **11-05**｜agent-mail 回 **`not_bound`**（面板显示 connected，实际未开通）｜git `main...HEAD` ahead=0/behind=0（HEAD `cae2c53`）｜`MACHINE_LOCK` **NOT_PRESENT**（本轮零推理、零计时）｜`CORRECTIONS_APP.md` 未入库（reviewer 独占写）。
> **③ §1【已完成】还原 A 的真实 device_config**：**前置态**（实测 `%LOCALAPPDATA%\Confucius4LiveCaption\device_config.json`）＝ SHA `0971eb73d485aa16c84384c041cab503a7287a1eed656b72e78d6507a5b054a6`／**108 B**／mtime **2026-11-12 16:43:10**／内容 `{asr=GPU.0, mt=GPU.0, tts=NPU, profile=minimvp, defaults_version=9}` ⇒ 与 APP-106 §1 描述**完全一致**（`app505` GUI 探针 16:43 那次写回）。**还原**：用 `results/app/app493_app104_rc9_acceptance/device_config.backup.json` 的**原始字节**写回（先断言前置态 108 B 且 SHA 精确命中，不符即中止）⇒ **还原后 SHA `9d484c1c9402d7a9911f2af6a53f6e056a18039715b8bda9ec15ddecf6b473a2`／59 B／mtime 2026-11-13 09:28:41**／内容 `{asr=GPU.0, mt=GPU.0, tts=GPU.0}`（**无 profile、无 defaults_version**）⇒ **与 app493 备份逐字节一致**（`post == backup` 断言通过，JSON 可解析）⇒ **APP-106 §5 验收点达成**；还原前／后 SHA 均已登记。
> **④ §1 后续纪律（reviewer 明确要求）**：以后做 GUI 或 `--check` 探针，**必须把 `LOCALAPPDATA` 指到临时目录**（reviewer 11-13 09:03 就是这么做：4 种旧配置场景全 exit 0 且 A 的真实配置 SHA 前后不变）⇒ **不得再碰 A 的真实配置**。另记（reviewer FYI，**本次不改**）：GUI 开→关就会把当前出厂默认带 `defaults_version` 写进文件 ⇒ 以后被当成「用户自己选的」；**下次默认值变动时把代次再升一级**即可。
> **⑤ §4【已完成】交付配置表改判**：「客户包目录 / 客户包 zip」两行已把 **v2.2 由「候选交付版」改为「带 APP-086·2a 缺陷，不能交付」**；**当前交付版仍是 v2.1**（桌面快捷方式仍指向 v2.1）。**reviewer 独立核过**：`Confucius4_LiveCaption_v2.4\app\tts_worker.py:1741` = `elif self._has_clone_voice():`（**无 `and not _bound`**）⇒ 完整版 **v2.2 / v2.3 / v2.3_aborted / v2.4** ＋ MiniMVP **v1.0 / rc1–rc5** 共 **10 个包**带串音缺陷 ⇒ **目录一律保留不删**（作废还是标注**等用户决定**）。
> **⑥ §4【已完成】停止新增闸门与判据脚本**：`pack_v13.py` 的**闸门④**（`check_app086_2a_narrowing`，含 `_terminal_else`/`_fallback_calls`，`pack_v13.py:1144/1301/1329`）与 **MUST 增 3 条**（`app/tts_worker.py`/`tts_service.py`/`tts_engine.py`，`pack_v13.py:130-132`）**原样保留、未再扩展**（`pack_v13.py` 本轮**零改动**，已入库 `cae2c53`；缺 `app/tts_worker.py` 改判 FAIL：`pack_v13.py:1196`）⇒ **本轮零新建 `app5xx` 判据脚本**（APP-106 §5 验收点达成）｜§189／§190 的脚本与 json **留在 `results/app`**（`app510`–`app523` 已入库，本轮**未新增、未改动、未提交新文件**）。
> **⑦ §2【顺延下一个包】README「A 机实测」数字仍是 rc8 旧默认时的**：**实测定位** `Confucius4_LiveCaption_MiniMVP_v1.0-rc10/README_zh.md:38-39` 与 `README_en.md:41-42` 写着「集显 **0.397** / NPU **0.538** / 包目录整链 **0.544**」——整链 **0.544 是 rc8 在 ASR=NPU 时测的**，而 rc10 出厂默认 ASR 在 **GPU.0** ⇒ **B 机的人会误以为 0.544 是新默认下的整链数字**。**下一个包（rc11 或换嵌 EXT）要改**：每个数字标上**设备组合**，补上 **rc10 新默认下的整链 ASR RTF 与 TTS 提交/播完/丢弃**，且**都从验收 json 生成**。**rc10 不为这个重打**（本轮未打包、未改包内 README）。
> **⑧ §2 备查 rc10 新默认下的真数字**（来源：reviewer 11-13 §0 引的 10 分钟整链 `chain10min.log`）：ASR `EXECUTION_DEVICES`＝**encoder=GPU.0，decoder=GPU.0**，RTF **0.538**，最大积压 0.9 s｜MT **GPU.0**，中位 **383.5 ms**、P95 **765.8 ms**｜TTS **12 个组件全在 NPU**，**提交 158 / 播完 126 / 丢弃 32**，首包 0.41 s，最大积压 105.07 s，结尾滞后 7.46 s，失败 0｜⚠️ **同一数值 0.538 在旧 README 指「NPU 的 ASR RTF」、在这组新数据指「GPU.0 的 ASR RTF」** ⇒ 下一轮**必须逐个数字标设备组合**。
> **⑨ §3【已记录】`--check` 留下的空 `__pycache__` 目录**：reviewer 实测即使加 `-B` ＋ `PYTHONDONTWRITEBYTECODE=1`，仍会建 `python\Lib\site-packages\librosa\__pycache__` 与 `librosa\core\__pycache__` 两个**空目录**。**本仓库口径已核实**：`pkg_exclude.py:121` `KEEP_PYCACHE_UNDER={"python"}` ⇒ `python/**/__pycache__` **按设计保留**（省客户机首次启动 1~5 s）；`pack_v13.py:1555` 的 zip **只收** `pkg_exclude.iter_package_files(PKG)` 的**文件项** ⇒ **空目录根本不会进 zip**；§184 纪律亦为「包内**禁** `.pyc`（仍建**空** `__pycache__` 目录）」⇒ **无需额外清理**。包目录实测 10 629 文件／1 185 目录／`.pyc` **0**／`__pycache__` 目录 **0**。另记：reviewer 提醒**包里的代码改动尽量放在最后一次设备验收之前**（本次「旧 旧」文案是整链跑完后才改的，只是一个字符串，可接受）。
> **⑩ §0 我方独立复核（只读，与 reviewer 结论一致）**：rc10 包目录 **10 629 文件**｜zip `shared\minimvp\…rc10_perftest.zip` **5 926 048 165 B**／mtime **2026-11-12 16:49:06**｜**dev 树与 rc10 包内 `app/device_config.py` 同 SHA `ea470419…`／35 189 B**，`CONFIG_DEFAULTS_VERSION=9`、`_DEFAULT_DEVICES_MINIMVP`＝**ASR GPU.0 / MT GPU.0 / TTS NPU**｜包内 `.pyc` 0、`__pycache__` 目录 0。
> **⑪ 纪律**：**未打包**（v2.5 未打／rc10 未重打／无新 zip）｜**未改任何客户包**（全部只读；本轮唯一写入＝`%LOCALAPPDATA%` 下 App 自身配置文件，属 §1 明确要求的还原）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 `CORRECTIONS_APP.md`**（只读、未入库、未提交）｜**未跑推理／未计时 ⇒ 未取 `MACHINE_LOCK`**｜**未调 MiniMax**｜**未通知用户**｜**未提交** ASR／MT／TTS 其它模块的未提交改动。
> **⑫ 本条需等 reviewer 复核**：① §1 还原（SHA `9d484c1c9402d7a9911f2af6a53f6e056a18039715b8bda9ec15ddecf6b473a2`／59 B）；② §4 交付配置表改判（v2.2 不可交付）；③ **10 个带缺陷包**作废还是标注（**目录一律不删**）；④ **完整版 v2.5** 何时打（必须带收窄，闸门④ 已 fail-closed）；⑤ §2 的 README 数字是否按 ⑧ 的口径在下一个包统一改；⑥ **B 机 rc10 实测**；⑦ **EXT 换嵌**通知。

## §192 执行 APP-107（last_ack=APP-107，2026-11-13 10:26:18）｜**MiniMVP rc11 已打（翻译模型 INT8-CW）**｜包上验收 **PASS**｜**本条需等 reviewer 复核**
> **① 纠偏文件复核（只读、未改、未提交）**：开工＝**106 条**／最大 **APP-106**／SHA `aab1d83a…`／352 203 B／mtime 11-13 09:07:45；**收尾＝107 条**／最大 **APP-107**／SHA `006d1ab7…`／**355 098 B**／mtime **11-13 09:28:40** ⇒ 🔴 **reviewer 在本轮中途追加了 APP-107** ⇒ **撤回 §191 ①「开工＝收尾逐字一致 ⇒ SHA 零改动」**（以本节为准）；**本文件全程未被修改**。
> **② §1.1 落地**：`models/mt/` 下**只带** `mt2-int8sym-cw-q`（**12 文件 / 1 812 121 487 B**；拷贝源 `hy_bench\ov\mt2-int8sym-cw-q`；**逐文件 SHA256 与源目录一致**）⇒ **INT4 不再随包**（rc10 的 INT4 是 1 040 491 337 B，**+0.77 GB**）⇒ 包内 `models/mt/` 只有 1 个目录。
> **③ §1.2 落地（行为级，不是查字面）**：包内实测 `DEFAULT_MODEL` = `…/models/mt/mt2-int8sym-cw-q`；`default_quant` = **int8**；`auto` label = 「**自动 · INT8-CW 模型（默认）**」；`MT_ENGINES` = **[auto, gpu_int8cw, npu_int8cw]**（**没有 INT4 项**）⇒ `--check` 输出：「[ OK ] Intel GPU · INT8-CW（默认） GPU.0」「[ — ] Intel GPU · INT4-CW …（**本包不附带该量化版本**）」「[ OK ] 自动 · INT8-CW 模型（默认）」。
> **④ §1.3 落地（模型身份）**：MANIFEST 新增 `mt/mt2-int8sym-cw-q` 条目 —— **拷贝源路径** `C:\Users\Trekker-PTL\hy_bench\ov\mt2-int8sym-cw-q` ＋ **12 个文件逐个 SHA256**（与源目录**一致**）＋ config **hidden_size 2048 / num_hidden_layers 32** ＋ **INT8_SYM 对称按通道** ⇒ `all_match=true`／`n_mismatches=0`；int4 条目标 `optional`（MiniMVP 不带 ⇒ **不算不一致**；**带了就照常对拍**）。
> **⑤ §2 包上验收 PASS**（在 **rc11 包目录**上跑、包内 python、**隔离 LOCALAPPDATA**）：静态 7 项全 PASS（INT8-only／MANIFEST／默认行为／出厂默认／卫生／README／app 内 int4 只剩注释与回退链）｜`--check` exit **0**｜**10 分钟整链** exit **0**：ASR RTF **0.735**（encoder+decoder 均 GPU.0）、翻译中位 **763.5 ms** / P95 **1354.0 ms** / TTFT **228.1 ms** / **23.9 tok/s**、TTS **提交 155 / 播完 99 / 丢弃 56**（落点 **NPU**）、**`CL_OUT_OF_RESOURCES` 0**、无 Traceback｜**10 语种冒烟 MT 30/30 ＋ TTS 30/30**｜GUI 截图 verdict **PASS**（翻译下拉只有 INT8-CW）。
> **⑥ §1.4 / APP-106 §2 落地（README 口径）**：三份 README 的「A 机实测」**每个数字都注明设备组合**（ASR 单项：集显 0.397／NPU 0.538），并补上**本包出厂默认（ASR=GPU.0 / MT=GPU.0（INT8-CW）/ TTS=NPU）下的整链 ASR RTF 与 TTS 提交/播完/丢弃** ⇒ **数字全部从验收 json 生成**（`results/app/app526_rc11_chain_measurements.json`）⇒ **打包时缺这个文件就拒绝出包**（fail-closed）。
> **⑦ 交付物**：目录 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc11`（**10 629 文件 / 6.28 GiB**）＋ zip `C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc11_perftest.zip`（**6,697,683,352 B**）；`release.json` 版本 `1.0-rc11`（`corrections` 含 APP-106／APP-107；`rc11_changes` 四条）。
> **⑧ 纪律**：**rc10 原样未改**（只读；旧目录/zip **不覆盖不删**）｜**未改任何其它客户包**｜**A 上真实的 `device_config.json` 前后 SHA 一致**（`9d484c1c…`／59 B）——探针一律用**隔离 LOCALAPPDATA**（**编译缓存用 junction 指向真目录**，129 GiB 缓存不重编译；`device_config.json` 独立 ⇒ **A 的旧配置现场仍在**）｜**未跑推理于 CPU**（设备作业持 `MACHINE_LOCK`）｜**未调 MiniMax**｜**未通知用户**｜**未改 `CORRECTIONS_APP.md`**（只读、未入库、未提交）｜**未提交** ASR／MT／TTS 其它模块的未提交改动。
> **⑨ 本条需等 reviewer 复核**：① **rc11 的整链数字**（**ASR RTF 0.735** vs rc10 的 0.538；MT 中位 **763.5 ms** vs rc10 383.5 ms；TTS 播完 **99/155** vs rc10 126/158）——INT8 使 **ASR+MT 同占 GPU.0** 更重，**性能是否可接受**请裁定；② **10 个带缺陷包**作废还是标注（**目录一律不删**）；③ **完整版 v2.5** 何时打（必须带 APP-086·2a 收窄）；④ README 数字口径是否按本节改法；⑤ **B 机 rc11 实测**；⑥ **EXT 换嵌**通知。
