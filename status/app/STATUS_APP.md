# STATUS_APP

last_ack: APP-107
更新时间: 2026-11-14 10:37:18
**Special MVP 已出包（§195）**，**目标机拷贝已实际完成（§197）**：用户 22:31 补的凭据 → **SSH 认证通过** → 大文件弃用 SFTP（实测 0.3 MB/s）改走 **HTTP(range)+curl（73.0 MB/s / 3 min 06 s）** → zip **14 244 490 059 B** 已落到目标机 `C:\Users\63446\Desktop\`（**大小与源逐字节相等**）⇒ 🔴 **两端 SHA256 对账被目标机 AV 独占锁挡住（ERROR_SHARING_VIOLATION）⇒ 只报「大小一致」，不报「SHA 一致」**（后台重试中）
🔴 **待用户：⓿ 目标机 `192.168.2.194` 已整体离线**（ping 4/4 丢包／无 ARP／22/445 超时）⇒ **先开机 ＋ 给一条认证**（密码或装公钥）｜① 是否授权删目标机上的 zip**（目标机 C: 仅 **1.55 GiB** 可用 ⇒ zip 13.27 GiB ＋ 解压 13.25 GiB ⇒ **删 zip 才能解压运行**；删除属破坏性 ⇒ 本轮**未删**）｜② **待目标机实机 `--check`**（RTX 4050 Laptop **sm_89 / 6 GB** vs 包内验收基线 **sm_120** ⇒ 不可外推）｜③ **OPEN-1** 长跑退出码 3221226505 待定位｜沿用未变：**CUDA TTS 音质/音色**待回转写、**TTS 首启 58.7 s** 是否可接受、10 个带 APP-086·2a 缺陷包作废还是标注、完整版 v2.5 何时打、EXT 换嵌通知
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）｜**§167 压缩**：§167 正文整块归档 ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12 277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）｜**§168 压缩**：§168 正文整块归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8 599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）｜**§178–§180 压缩**（APP-101 §1.d「每节不超过 3 行速查」）：三节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec178_180_20261112.md`（块 SHA256 `d91b34ffed16ff1b22f0dd369c66bd9477351a8e782f327ff1740f0b44113705`）；活文档三节各留 1 行速查｜**§141–§160 压缩**：20 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜**§171–§180 压缩**：10 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜**§170 + §183 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（块 SHA256 见 §185）｜**§186 + §187 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）｜**「最近更新」5 条较旧条目（APP-104／APP-102／接单 APP-101／APP-099×2）整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_20261113.md`（块 SHA256 见 §188）｜**§188 压缩**（2026-11-13）：§188 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec188_20261113.md`（块 SHA256 见 §189 末）｜**§189 压缩**（2026-11-13）：§189 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec189_20261113.md`（块 SHA256 见 §190 末）｜**§190 压缩**（2026-11-13）：§190 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec190_20261113.md`（块 SHA256 `184a60612732eeffd7d6893cce15b7599d875a6df8227a0d7aace2eb4f09fbbc`）｜**§135–§140 标题块压缩**：标题行＋指针行整块逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_headers_20261113.md`（块 SHA256 `7a3e4ba75f5c030e339ae131ca06d2b7027a91086fda9113ed060dad6f29be75`）｜**「最近更新」较旧 1 条（2026-11-12 16:51:46「APP-105 执行完（rc10）」）整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261112.md`（块 SHA256 `1d58e96d85cc862067351ba99bfb5bed3d9c0e3b9854c78a08d77e25aa58558b`）｜**§191 压缩**（2026-11-13）：§191 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec191_20261113.md`（7823 B／正文块 SHA256 `7d9337297a92c7a99be00aaf2e4db862486eb31dc0d8172fe20f78189ea40161`）；活文档保留 §191 标题行 ＋ 1 行指针｜**§192 + §193 压缩**（2026-11-13）：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec192_193_20261113.md`（**13729 B**／块 SHA256 `09efa039662f7c27a7812ab514d72895e634018458067c6b463ebbcad1b7b864`）；活文档保留 §192／§193 标题行 ＋ 1 行指针｜**§194 压缩**（2026-11-13）：正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec194_20261113.md`（**9087 B**／块 SHA256 `ed87dafbfaae247f94a69f535b5d297f3d62b1df99d06b380a239f98dcf811c7`）；活文档保留 §194 标题行 ＋ 1 行指针｜**§195 压缩**（2026-11-13）：正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec195_20261113.md`（正文块 7650 B／SHA256 `66d0b44c805585ba65ec73450d21e473b5472e41b39c70be7161edb6929396b1`）｜**§197+§198 压缩**（2026-11-13）：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec197_198_20261113.md`（8717 B／块 SHA256 `ce563357566997e4482dcdf3daf6764c0a2fc30ea805962dd6367bc7f3d47f97`）；活文档保留 §197／§198 标题行 ＋ 1 行指针


## 最近更新
> 🔴 2026-11-13 23:59:06 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）**：6 通道全查空（`CORRECTIONS_APP.md` 107 条/APP-107 未变、NOTICE 最新 11-05、agent-mail 仍 `not_bound` 查不了、conversation_search 0 命中、git 0/0、`MACHINE_LOCK` 无）｜🔴 **本轮唯一实质发现（交付通道层）：目标机的无人值守进入通道已失效** —— 口令当时只放在临时环境变量 `WB_SSH_PASS`（**未落盘未入库**）⇒ 本轮及后续会话都登不上；公钥路实测也未通（**已排除探法错误**：显式 `-i github_backup_ed25519 -o IdentitiesOnly=yes` 仍 Permission denied）⇒ §197⑤/§198② 的**两端 SHA256 对账任何无人值守轮次都无法闭环**，需用户给一次密码或装公钥｜未打包/未改客户包/未改产品代码/未跑推理/未调 MiniMax
> 🔴 2026-11-13 22:48:21 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）＋ 目标机拷贝已实际完成**：用户补的凭据 → SSH 认证通过；🔴 **大文件弃用 SFTP（0.3 MB/s）改走 HTTP+curl（73.0 MB/s / 3 min 06 s）**；zip **14 244 490 059 B** 落到目标机 `C:\Users\63446\Desktop\`（**大小逐字节相等**）；🔴 **两端 SHA256 对账被目标机 AV 独占锁挡住**（ERROR_SHARING_VIOLATION）⇒ 只报大小一致；🔴 **目标机 C: 仅 1.55 GiB 可用 ⇒ 删 zip 才能解压运行**（未删，等授权）；🔴 **目标机 RTX 4050 sm_89 vs 包基线 sm_120** ⇒ 须实机 `--check`；未打包/未改客户包/未改产品代码/未调 MiniMax
> 🔴 2026-11-13 22:21:35 ｜ **Special MVP 目标机拷贝被凭据挡住**（§196）：目标 `192.168.2.194`(`laptop-vqsjm79a`) 可达（9 ms）但**只开 22/445**，`test/Intel123` 在 SSH(password/interactive/publickey) 与 SMB(1326) 上**全被拒** ⇒ **已停止重试**（防 Windows 账号锁死，≥8 次失败认证）｜**传输工具已备好**（断点续传 + 两端 SHA256 对账 + 目标机 nvidia-smi/--check 预检）＋**公钥已给出** ＋ **桌面拷贝说明**＋ 包旁 `_DELIVERY_SPECIALMVP.txt`｜zip SHA256 `72d2727a…`｜未改目标机任何东西
> 🔴 2026-11-13 21:27:28 ｜ **Special MVP 出包**（用户 2026-11-13 决定）：**TTS 仅用 CUDA**（NV5050 环境**随包**）／**ASR 用 iGPU**／**MT 用 NPU**｜包 `Confucius4_LiveCaption_SpecialMVP_v1.0-sp1`（**41,374 文件 / 13.25 GiB**）｜包上验收 **PASS（13/13）**｜整链实测：ASR RTF **0.522**（集显）／翻译落点 **NPU**（中位 898.8 ms）／TTS 由 **?** 合成（加载 ? s、预热 ? s）｜**新包形态** `profile=specialmvp`（MiniMVP/完整版行为**一字不变**，已回归）｜未改旧包、未调 MiniMax、未通知用户
> 🔴 本节 4 条较旧「最近更新」条目（2026-11-13 09:33:57／10:26:18／12:42:21／16:03:02）原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261113_2254.md`（块 SHA256 `99240bb5131586caa8d9fcf2b9fb63c152d4f74c9baf517bedbaeb2d56694861`）
> 🔴 本节 3 条较旧「最近更新」条目（2026-11-13 04:46:11／06:49:24／08:21:30 三轮巡检）原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261113c.md`（3241 B／块 SHA256 `d5eba71ed0a9e2df0e9263fbc6ba4c6d95e7b4f97256ceb436cb5cd1566a421e`）；本节只留最近 3 条。
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

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec191_20261113.md`（7823 B／正文块 SHA256 `7d9337297a92c7a99be00aaf2e4db862486eb31dc0d8172fe20f78189ea40161`）；活文档保留 §191 标题行 ＋ 1 行指针。
## §192 执行 APP-107（last_ack=APP-107，2026-11-13 10:26:18）｜**MiniMVP rc11 已打（翻译模型 INT8-CW）**｜包上验收 **PASS**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec192_193_20261113.md`（§192 正文块 4548 B／SHA256 `825e0302c70d89a98cc007257d8202698bc924384568b1a1ea4e29e4fee6052a`；§193 正文块 8610 B／SHA256 `338eb2a00a067ca16032e0281b95309bc4e0ed01e45bccbbe947e8f6fcc2f626`）；活文档保留 §192 标题行 ＋ 1 行指针。
## §193 巡检（last_ack=APP-107，2026-11-13 12:42:21）｜**无新 reviewer 纠偏**（6 通道全查空）｜**rc11 半交付复核 PASS（zip ⇄ 包目录逐字节一致）**｜**`app523` 的 FAIL ＝ 判据过期（假 FAIL），非产品回归**｜**未打包／未改客户包／未改产品代码**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec192_193_20261113.md`（§193 正文块 8610 B／SHA256 `338eb2a00a067ca16032e0281b95309bc4e0ed01e45bccbbe947e8f6fcc2f626`；§192 正文块 4548 B／SHA256 `825e0302c70d89a98cc007257d8202698bc924384568b1a1ea4e29e4fee6052a`）；活文档保留 §193 标题行 ＋ 1 行指针。

## §194 巡检（last_ack=APP-107，2026-11-13 16:03:02）｜**无新 reviewer 纠偏**（6 通道全查空）｜**既有闸门复跑判定未变**（`app510` PASS／`app512` 19 包）｜🔴 **新发现：`app512` 的 `tag` 对 v1.5 误标**（`branch2_exists=false` 却标「收窄在包里」）｜**rc11 无漂移**｜**未打包／未改客户包／未改产品代码**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec194_20261113.md`（正文块 8688 B／SHA256 `e66567ef73b823252960a92a2de99d1146bb3ce37142147aa886d8d12397e6ee`）；活文档保留 §194 标题行 ＋ 1 行指针。

## §195 **Special MVP 出包**（用户 2026-11-13 决定：TTS 仅用 CUDA／ASR 用 iGPU／MT 用 NPU）｜`Confucius4_LiveCaption_SpecialMVP_v1.0-sp1`｜包上验收 **PASS（13/13）**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec195_20261113.md`（正文块 7650 B／SHA256 `66d0b44c805585ba65ec73450d21e473b5472e41b39c70be7161edb6929396b1`）；活文档保留 §195 标题行 ＋ 1 行指针。

## §196 Special MVP **目标机拷贝：被凭据挡住**（目标 `192.168.2.194` = `laptop-vqsjm79a`）｜**包已就绪，待一条可用认证**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec196_20261113.md`（正文块 3790 B／SHA256 `ead1629fca3f6d3fd484fca3e1728df8b132d3f1c0181719ddc180bbd899841a`）；活文档保留 §196 标题行 ＋ 1 行指针。

## §197 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-107**）＋ **执行用户补给的认证 ⇒ Special MVP 已实际拷到目标机**
> **§197+§198 压缩**（2026-11-13）：**两节正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec197_198_20261113.md`（8717 B／块 SHA256 `ce563357566997e4482dcdf3daf6764c0a2fc30ea805962dd6367bc7f3d47f97`）；本行同时覆盖 §197 与 §198 两节正文；两节**标题行仍逐字保留在活文档**。

## §198 §197 收尾复核（2026-11-13 22:54）｜🔴 **目标机磁盘比传输后更紧张** ｜两端 SHA256 仍未闭环

## §199 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-107**）｜🔴 **目标机进入通道已结构性失效** ⇒ §197 ⑤／§198 ② 的 SHA256 对账**任何无人值守轮次都无法闭环**

> **§199 压缩**（2026-11-14）：**正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec199_20261114.md`（5554 B／块 SHA256 `ae2eb18fb51b14b3d995fe261bcb42d2008fe6893ebac0041763644c03d9d817`）；活文档保留 §199 标题行 ＋ 1 行指针。

## §200 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-107**）｜🔴 **修掉 App 侧真缺陷：两个自检脚本会覆盖用户真实的 `device_config`**（APP-106 §1 的「旧用户配置」现场被毁，**已还原**）｜🔴 **目标机 `192.168.2.194` 已整体离线**

> **① 巡检（6 通道全查空，附开工实测值）**：`status/app/CORRECTIONS_APP.md` 开工＝**107 条／最大 APP-107**（SHA `006d1ab7386ddfdf5f988330c74632f19f21b63b20d55aba8c5ca2febaf07ea5`／**355 098 B**／mtime **11-13 09:28:40**）⇒ **无编号 > last_ack 的新条目** ⇒ `last_ack` **保持 APP-107**（无新纠偏 ⇒ 不写自己的编号）。其余通道：`shared/NOTICE*` 最新仍 **11-05 09:35**｜agent-mail 工具返 **`not_bound`**（**该通道本轮查不了**，如实记录，不声称查过）｜`conversation_search`（11-13～11-14）**0 命中**｜git `origin/main...main`＝**0/0**（HEAD `d029ab4`）｜`claude-clone --not main`＝**0**｜`MACHINE_LOCK` **NOT_PRESENT**｜根 `status/CORRECTIONS.md` 最大 **C-135**（10-24 17:01）｜ASR 侧最大 **ASR-057**（11-13 09:06，无 App 条目）｜`clone_dev` 等旧克隆仍是 **10 929 B／最大 APP-004** 的陈旧快照。
> **② 🔴 本轮实质发现（App 侧真缺陷，已修）**：**两个自检脚本会写用户的真实配置**。① `live_caption/diag_device_select.py` §4 的小节标题就叫「**配置持久化（真实路径）**」⇒ 跑一次自检就把 `%LOCALAPPDATA%\Confucius4LiveCaption\device_config.json` 覆盖成 `{asr:GPU.0, mt:GPU.0, tts:NPU}`；② `live_caption/diag_device_gui.py` 构造**真 App** ⇒ `_init_combo_values` → `device_config.save_config(...)` ＋ 3 次 combo 切换 ⇒ **至少 4 次**写真实配置（且带 `profile`＋`defaults_version`）⇒ **APP-106 §1 要保住的「旧用户配置」现场当场被毁**（2026-11-12 16:43:10 那次 108 B 覆盖就是这条路径）。
> **③ 实测确证（非推理、非猜测）**：改前在**隔离 LOCALAPPDATA** 下跑 `diag_device_select.py` ⇒ 实测它把 `{asr:GPU.0, mt:GPU.0, tts:NPU}` 写进了 `CONFIG_PATH`（实测路径＝隔离目录 ⇒ 正常运行时就是**真实**路径）⇒ 机制成立。A 上真实文件在 **11-13 15:10:34** 被改成 **57 B／SHA `4bdaff2b…`**（＝旧包的 `save_config` 走 `json.dump(devices)` 写出的 3 键形态，**逐字节**与 `diag_device_select.py` 的硬编码三元组一致）⇒ **§191 的还原被推翻且无人发现**（§194～§199 五轮都只查了包，没查这个文件）。
> **④ 修法（产品代码，只改 dev 树；不改客户包、不打包）**：`diag_device_select.py` §4 改走**隔离路径**并新增「真实配置 SHA256 前后一致」断言；`diag_device_gui.py` 在 import **之前**把 `LOCALAPPDATA` 指到**临时目录** ⇒ 连模块级 `CONFIG_DIR` 都在临时目录 ⇒ 物理上够不到真实配置，并同样加 SHA 断言。两个脚本**都不进客户包**（19 个包目录里均无 `diag_device_*.py`）⇒ **不需要打新版本号**。
> **⑤ 顺带修掉一个假 FAIL**：`diag_device_select.py` §3「回落到推荐默认」改前**恒 FAIL**（脚本改前输出 `ALL FAIL (1)`）⇒ 根因：`save_config({})` 在 APP-090②c／APP-104 的**合并写**语义下**清不掉**已有设备键 ⇒ 断言拿到旧值当「默认」。修法是**断言前真的删掉配置文件**（不是放宽断言）⇒ 现在 `ALL PASS`。
> **⑥ 验收（真实环境、端到端、零推理）**：还原后真实配置＝**59 B／SHA `9d484c1c…`／mtime 11-14 10:35:53**（＝ app493 备份**逐字节**一致）⇒ 跑 `diag_device_select.py` → **ALL PASS**（PYRC=0）、真实配置 SHA **前后一致**；跑 `diag_device_gui.py` → **ALL PASS**（PYRC=0，耗时 16 s）、真实配置 SHA **前后一致且 mtime 未变**；GUI 自检的落盘文件在 `%TEMP%\diag_gui_devcfg_*\Confucius4LiveCaption\device_config.json`，内容 `{'asr':'GPU.0','mt':'GPU.0','tts':'NPU','profile':'full','defaults_version':9}` ⇒ **污染形态一模一样，只是目标路径被换掉** ⇒ 机制对照成立。
> **⑦ 🔴 目标机已整体离线（比 §199 的「结构性失效」更硬）**：本机仍在 **192.168.2.189/24**（网关 192.168.2.1）⇒ **不是本机换网**；目标 **192.168.2.194** ping **4/4 丢包**、**无 ARP 表项**、TCP **22/445 均超时**（SSH 直接 `Connection timed out`，连 `Permission denied` 都到不了）⇒ **目标机已关机／脱网**。⇒ §197 ⑤／§198 ② 的两端 SHA256 对账、目标机磁盘（82.3 MB 可用）、实机 `--check`（RTX 4050 sm_89 vs 包基线 sm_120）、删 zip 授权 —— **全部**只能等用户把机器开回来**并**给一条认证。
> **⑧ 零漂移复核（只读）**：客户包目录 **19 个**、本轮**一个都没改**；`shared/minimvp/` 8 个 zip 未动（rc10 5 926 048 165 B／rc11 6 697 683 352 B／mtime 11-13 10:23:53）｜Special MVP 源 zip **14 244 490 059 B／mtime 11-13 21:24:59** 未漂移｜`live_caption/` 本轮**只改 2 个自检脚本**，产品逻辑零改动｜**完整版 v2.5 仍未打包**（现存最大完整版 v2.4 ⇒ 下一次完整版打包即 v2.5；闸门④ 已 fail-closed）。
> **⑨ 纪律**：本节**只追加**，§199 正文已整块逐字归档 ⇒ `status/archive/STATUS_APP_sec199_20261114.md`，旧正文一字未删｜**未打包**｜**未改任何客户包**｜**未跑推理**（本轮只有设备枚举＋GUI 构造，无模型、无推理）⇒ 未取 `MACHINE_LOCK`｜**未调 MiniMax**｜**未改 `CORRECTIONS_APP.md`**（收尾仍 **107 条／APP-107／SHA `006d1ab7…`／355 098 B／mtime 11-13 09:28:40** ＝ 开工值 ⇒ 本轮可写「SHA 零改动」）｜**未提交其它模块**的未提交改动｜`results/app/app512_pkg_follow_speaker_matrix.json`（+18/-0）与 `results/app/app523_pack_must_ttsworker_evidence.json`（+16/-7）**仍保持未提交**（等 reviewer 对 app523 裁定，**不预判**）｜**本轮零新增判据/审计脚本**（APP-106 §4）。
> **⑩ 等用户/reviewer（沿用未变）**：① **目标机开机 ＋ 一条认证**（给一次 `test` 密码，或把 `C:\Users\Trekker-PTL\.ssh\github_backup_ed25519.pub` 追加到目标机 `C:\Users\63446\.ssh\authorized_keys`）⇒ 才能闭环 SHA256／磁盘／实机 `--check`；② **是否授权删目标机上的 zip**（目标机 C: 仅 82.3 MB 可用 ⇒ zip 13.27 GiB ＋ 解压 13.25 GiB ⇒ 删 zip 才能解压运行）；③ **10 个带 APP-086·2a 缺陷包**作废还是标注（目录一律保留不删）；④ **完整版 v2.5** 何时打（**必须带收窄；用户不通知不打包**）；⑤ **EXT 换嵌**通知；⑥ `app523` 假 FAIL 是否退役；⑦ rc11 **B 机**运行；⑧ **OPEN-1** 退出码 3221226505 定位；⑨ **CUDA TTS 音质/音色**待 reviewer 回转写、**TTS 首启 58.7 s** 是否可接受。

## §201 勘误（2026-11-14 10:50）｜**撤回** §200 ④／⑧ 的「客户包目录 **19 个**」⇒ 实测 **20 个目录** ＋ 1 个 zip 文件
> **① 撤回**：§200 ④「**19 个**包目录里均无 `diag_device_*.py`」与 ⑧「客户包目录 **19 个**」两处计数**写错了** ⇒ **更正为 20 个目录**。实测 20 个目录里 `app/diag_device_*.py` **命中 0** ⇒ **结论不变，只是计数错**。
> **② 实测清单（20 个目录）**：MiniMVP **11**（v1.0／rc1／rc2／rc3／rc4／rc5／rc7／rc8／rc9／rc10／rc11）｜完整版 **8**（v1.13／v1.5／v2.0／v2.1／v2.2／v2.3／v2.3_aborted_20261107_1517／v2.4）｜SpecialMVP **1**（v1.0-sp1）＝ **20**；另有 `Confucius4_LiveCaption_v2.4.zip`（**11 235 954 241 B／mtime 11-07 23:04**）是**文件**、**不计入目录数**。
> **③ 其余结论不变**：本轮**一个客户包都没改**（全部只读）｜两个自检脚本**不在任何包内** ⇒「**不需要打新版本号**」的判断**不受影响**｜§200 的 ①–③⑤–⑩、归档件 `STATUS_APP_sec199_20261114.md`、git `756d064` **均不变**。
