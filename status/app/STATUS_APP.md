# STATUS_APP

last_ack: APP-115
更新时间: 2026-11-18 16:39:49
**Special MVP 已出包（§195）**，**目标机拷贝已实际完成（§197）**：用户 22:31 补的凭据 → **SSH 认证通过** → 大文件弃用 SFTP（实测 0.3 MB/s）改走 **HTTP(range)+curl（73.0 MB/s / 3 min 06 s）** → zip **14 244 490 059 B** 已落到目标机 `C:\Users\63446\Desktop\`（**大小与源逐字节相等**）⇒ 🔴 **两端 SHA256 对账被目标机 AV 独占锁挡住（ERROR_SHARING_VIOLATION）⇒ 只报「大小一致」，不报「SHA 一致」**（🔴 11-17 23:10 实测：后台重试循环**已停止**——`_app547_hash_retry.py` 上限 60 次×45 s（约 11-13 23:32 到期）且证据 json **无 `hash_retry_log`** ⇒ 未写回；当前**无 python/curl/ssh 进程、无计划任务** ⇒ **两端 SHA256 仍未对账**；且该脚本 HOST 仍写 **.194 旧地址** ⇒ 续跑须先改 **.206**）
🔴 **待用户：⓿ 目标机地址已变为 `192.168.2.206`**（用户 11-14 15:45 确认；`.194` 是旧记录）｜**APP-109 ④ 仍然有效**：**不连接 B 机、不拷贝、不做 SHA 对账**｜① 是否授权删目标机上的 zip**（目标机 C: 仅 **1.55 GiB** 可用 ⇒ zip 13.27 GiB ＋ 解压 13.25 GiB ⇒ **删 zip 才能解压运行**；删除属破坏性 ⇒ 本轮**未删**）｜② **待目标机实机 `--check`**（RTX 4050 Laptop **sm_89 / 6 GB** vs 包内验收基线 **sm_120** ⇒ 不可外推）｜③ **OPEN-1** 长跑退出码 3221226505 待定位｜沿用未变：**CUDA TTS 音质/音色**待回转写、**TTS 首启 58.7 s** 是否可接受、10 个带 APP-086·2a 缺陷包作废还是标注、完整版 v2.5 何时打、EXT 换嵌通知
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166／§135–§140 摘要／关键数字表／§167／§168／§178–§180／§141–§160／§171–§180／§170+§183／§186+§187／「最近更新」5 条／§188／§189／§190 压缩条目已整块逐字归档** ⇒ `status/archive/STATUS_APP_compress_index_upto_20261113.md`（块 SHA256 `819c951a0203811670403e34140fb239a59cd98d6bb262399af0ff4ef9485dbb`／2517 B）｜**§135–§140 标题块压缩**：标题行＋指针行整块逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_headers_20261113.md`（块 SHA256 `7a3e4ba75f5c030e339ae131ca06d2b7027a91086fda9113ed060dad6f29be75`）｜**「最近更新」较旧 1 条（2026-11-12 16:51:46「APP-105 执行完（rc10）」）整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261112.md`（块 SHA256 `1d58e96d85cc862067351ba99bfb5bed3d9c0e3b9854c78a08d77e25aa58558b`）｜**§191 压缩**（2026-11-13）：§191 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec191_20261113.md`（7823 B／正文块 SHA256 `7d9337297a92c7a99be00aaf2e4db862486eb31dc0d8172fe20f78189ea40161`）；活文档保留 §191 标题行 ＋ 1 行指针｜**§192 + §193 压缩**（2026-11-13）：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec192_193_20261113.md`（**13729 B**／块 SHA256 `09efa039662f7c27a7812ab514d72895e634018458067c6b463ebbcad1b7b864`）；活文档保留 §192／§193 标题行 ＋ 1 行指针｜**§194 压缩**（2026-11-13）：正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec194_20261113.md`（**9087 B**／块 SHA256 `ed87dafbfaae247f94a69f535b5d297f3d62b1df99d06b380a239f98dcf811c7`）；活文档保留 §194 标题行 ＋ 1 行指针｜**§195 压缩**（2026-11-13）：正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec195_20261113.md`（正文块 7650 B／SHA256 `66d0b44c805585ba65ec73450d21e473b5472e41b39c70be7161edb6929396b1`）｜**§197+§198 压缩**（2026-11-13）：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec197_198_20261113.md`（8717 B／块 SHA256 `ce563357566997e4482dcdf3daf6764c0a2fc30ea805962dd6367bc7f3d47f97`）；活文档保留 §197／§198 标题行 ＋ 1 行指针｜**§209+§210 压缩**（2026-11-16）：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec209_210_20261116.md`（块 SHA256 `6bcc0223a8cf0637b2450ebe84cc6811e3d872d93861e015b4110fe9f430da3e`／7163 B）


## 最近更新
> 🔴 2026-11-17 10:33 ｜ **执行 APP-114**（last_ack=APP-113 → **APP-114**）：**§1 语速上限 2.00× → 1.70×**（**所有目标语言**、含总倍率；中文下限 1.10 / 丢句阈值 0 / 增益曲线 / 视频速度**均不改**）｜**§2.1 就绪前队列的 120 s 溢出丢弃 ⇒ 改为「仅 TTS worker 明确失败/退出才清空」**（正常慢加载**不按时间丢句**；队列探针：300 s 过期仍保留 5 句、丢弃 0）｜**§3 选 sp5**（**sp4 逐字节未动**：文件数 41 374 / 14 232 064 511 B / `live_caption_app.py` sha `ef367412…` 三项与 app587 记录一致；EXT 升 **v0.4.16** / commit `7a92f12`）｜**§4 三臂 10 分钟验收全部 PASS**（zh / en / 冷启动：**丢句 = 0**、译文 164 == 进 TTS 164、排队 == 补发、**max ≤ 1.70**、rc=0、`timing_valid=true`）｜**未打 zip**（sp4 / sp5 都无 zip）｜**本条需等 reviewer 复核**（未结 3 项见 §213⑨）
> 🔴 2026-11-16 21:00:08 ｜ **执行 APP-113**（last_ack=APP-112 → **APP-113**）：**§1 TTS 就绪前不再跳过 ⇒ 进队列等待（不丢句）**（120 s 溢出保护）｜**§2 ASR 与 TTS 并行加载**（只并行 CUDA；新增 `LIVECAP_TTS_PARALLEL=0` 对照开关）｜**§3 非中文目标语速上限 1.30× → 2.0×**（增益曲线不动）｜**sp4 已出**（sp3 逐字节未动）｜**验收：丢句 = 0**（译文 164 = 进 TTS 164；就绪前排队 10 全部补发 10）｜**未打 zip**（§4 明文）｜**未结：2.0× 听感未真正验证**（热缓存臂实测 max 中文 1.5332／英文 1.3705；冷启动参考臂 1.8204×）
> 🔴 2026-11-16 14:48 ｜ **执行 APP-112**（last_ack=APP-111 → **APP-112**）：**撤回 §210 ④⑤ 的「139 句全播完」与「根因=冷启动慢」** ⇒ 实为 **就绪前静默跳过 25/164（15.24 %）**（app581：30/164 = 18.29 %）｜**冷启动计时 `timing_valid=false`**（窗口内有外部 4.56 GB + 0.59 GB 写入）｜**新增验收 v2 json ×2**（**原文件一字未动**）｜**零代码改动／零新包／零 zip／零推理**
> 🔴 2026-11-15 12:16 ｜ **执行 APP-110 / APP-111**（last_ack=APP-109 → **APP-111**）：**APP-110 §0②(a)(b) 补测 9/9 PASS**（隔离 LOCALAPPDATA，真实配置 SHA 未变）｜**§0③ sp1 原命令原样复跑 rc=0 ⇒ OPEN-1 记「未复现（0/4）」、停止定位**｜**§1 自建闸门：立即停止**（本轮零新增闸门/矩阵/判据脚本）｜**§2 B 机地址 .194 → .206 已更正**｜**APP-111 §1 只改两处参数**：`tts_late_drop_sec` **6.0 → 0.0**（一句都不丢）＋ `tts_speed_max_zh` / `ZH_SPEED_MAX` **1.50 → 2.00**（增益曲线未动）｜**Special MVP sp3 已出**（基于 sp2 复制，**sp2 逐字节未动**）｜**sp3 10 分钟验收：丢句 = 0**｜**未打 zip**（等验收通过 ＋ 用户未通知）｜**未改其它模块文件／未提交 CORRECTIONS_APP.md**
> 🔴 本节 10 条较旧「最近更新」条目（🔴 2026-11-15 10:18:／🔴 2026-11-15 08:47:／🔴 本节 3 条较旧「最近更新」条目（ …）原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261115b.md`（4076 B／块 SHA256 `783dabb83ef79b45c7af930fcffd79d862d4f1b3cab07d7103078783d7d88167`）；活文档本节只留本行 ＋ 最新 1 条。
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

> **§200 压缩**（2026-11-14）：**正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec200_20261114.md`（正文块 6919 B／SHA256 `f7128a37772f945f0501270d540be973d18512f92a84f401a8ec00b2bf239898`）；活文档保留 §200 标题行 ＋ 1 行指针。

## §201 勘误（2026-11-14 10:50）｜**撤回** §200 ④／⑧ 的「客户包目录 **19 个**」⇒ 实测 **20 个目录** ＋ 1 个 zip 文件
> **§201 压缩**（2026-11-14）：**正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec201_20261114.md`（正文块 1131 B／SHA256 `d851f6a38dfc4008c731ea054ae922e867bd66ff507c2ba319acff8ce12fb768`）；活文档保留 §201 标题行 ＋ 1 行指针。

## §202 执行 **APP-108 / APP-109**（last_ack=APP-109，2026-11-14 17:17:05）｜🔴 **修掉 Special MVP 真缺陷（出厂默认 MT=NPU 曾被旧配置覆盖成 GPU.0）并出 sp2**｜🔴 **OPEN-1（0xC0000409）仍未定位**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec202_20261114.md`（块 SHA256 `98e117978d02b50449e23804ce49dbe0294b8a5a669e12ab293ca45b0572a1c3`）；活文档保留 §202 标题行 ＋ 1 行指针。

## §203 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉包矩阵闸门 `app512` 的覆盖漏洞：SpecialMVP 两个客户包从未进过闸门**｜**「10 个带缺陷包」经全盘 AST 复核数字不变**｜**未打包／未改客户包／未改产品代码**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec203_20261114.md`（块 SHA256 `46afd0997e8cd667aa08655f6a9f1f9286cd73f2caf3516bd76e7e8b8f6f8245`）；活文档保留 §203 标题行 ＋ 1 行指针。

## §204 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉交付闸门真缺陷：Special MVP 打 zip 的闸门可被架空**（拿 sp1 的验收结论放行 sp2）｜**参数化＋闸门重写，鉴别力矩阵 6/6 PASS**｜**未打包／未改客户包／未改产品代码**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec204_20261114.md`（块 SHA256 `251e9682857502b7b9eb1850e2594af070b1b59790cc2f7dc5b65c4d23f5acdc`）；活文档保留 §204 标题行 ＋ 1 行指针。

## §205 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉 Special MVP 两个真缺陷：① sp2 包内 MANIFEST 的 `pkg_models_root` 一直指向 sp1（重定向是死代码）② 出包闸门对包内容 0 字节验证（验收后改包照样能出包）**｜**鉴别力矩阵 12/12 PASS**｜**未打包／未改产品代码**｜**本条需等 reviewer 复核**
> **正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec205_20261114.md`（块 SHA256 见该文件末）＋ 完整正文 companion `status/app/STATUS_APP_sec205_detail_20261114.md`。

## §206 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉出包闸门的真缺陷：7.86 GiB / 96 个模型文件不在内容绑定范围内 ⇒ 验收后换掉模型照样能出包**｜**鉴别力矩阵 12/12 PASS（改前 5 臂 fail-open）**｜**未打包／零客户包写入／未改产品代码**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec206_20261115.md`（正文块 SHA256 `1be58d5fc6a5c54e79fd397f009de694e4f181e80f88c84d9550e8af40cf1634`）；活文档保留 §206 标题行 ＋ 1 行指针。

## §207 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉 MiniMVP 出包闸门的真缺陷：验收证据不绑包身份、不绑包内容（验收后改包照样能出包）＋「PASS（有 1 项未结：…）」被误判 FAIL**｜**鉴别力矩阵 12/12 PASS（改前 5 臂 fail-open ＋ 1 臂假 FAIL）**｜**未打包／零客户包写入／未改产品代码**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec207_20261115.md`（正文块 SHA256 `eaebeef1ee52d8a15210f0dc7c1fee42e802b4183769127df913e6bdae3870cc`／5831 B）⇒ 活文档保留 §207 标题行 ＋ 1 行指针。

## §208 巡检（无新 reviewer 纠偏，last_ack 仍 **APP-109**）｜🔴 **修掉完整版（`pack_v13.py`）出包闸门真缺陷：全程零验收绑定**｜**鉴别力矩阵 15/15 PASS**｜**未打包／零客户包写入／未改产品代码**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec208_20261115.md`（正文块 4897 B／SHA256 `25d2cd8dc0b3e68905d391bca5952a048fdc7a642e1b6dad0c5bfca00fcd8fbf`）；活文档保留 §208 标题行 ＋ 1 行指针。


## §209 执行 **APP-110**（last_ack=APP-111，2026-11-15 12:16）｜🔴 **§0②(a)(b) 补测 9/9 PASS**｜🔴 **§0③ sp1 原命令原样复跑 rc=0 ⇒ OPEN-1 记「未复现」**｜🔴 **§1 起不再新增任何闸门/矩阵/判据脚本**｜**未打包／未改产品代码（本节零产品改动）**｜**本条需等 reviewer 复核**
> 🔴 **正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec209_210_20261116.md`（§209+§210 标题行＋正文逐字保留；块 SHA256 `6bcc0223a8cf0637b2450ebe84cc6811e3d872d93861e015b4110fe9f430da3e`／7163 B）｜活文档本节只留标题行 ＋ 此指针行。

## §210 执行 **APP-111**（last_ack=APP-111，2026-11-15 12:16）｜🔴 **TTS 跳句阈值 6.0 → 0（一句都不丢）**＋ **语速上限 1.5× → 2.0×**（只改这两处）｜🔴 **Special MVP sp3 已出包**（**sp2 逐字节未动**）｜🔴 **10 分钟验收：丢句 = 0**｜**未打 zip（等验收通过）**｜**本条需等 reviewer 复核**
> 🔴 **正文已整块逐字归档** ⇒ 同上文件（`status/archive/STATUS_APP_sec209_210_20261116.md`）；🔴 **④⑤ 已被 §211 撤回并更正**（`n_translations=164`／`n_skip_not_ready=25`／`n_submitted=139`；就绪前跳过 25/164 = 15.24 %；冷启动计时 `timing_valid=false`）⇒ **以 §211 为准**。

## §211 执行 **APP-112**（last_ack=APP-112，2026-11-16 14:48）｜🔴 **撤回 §210 ④⑤ 的「139 句全播完」与「根因=冷启动慢」**｜🔴 **就绪前跳过 25/164（15.24 %）**｜🔴 **冷启动计时 `timing_valid=false`**｜**零代码改动／零新包／零 zip**｜**需等 reviewer 复核 + 用户裁定 A/B**
> 🔴 **正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec211_20261117.md`（正文块 5388 B／SHA256 `ca4a80365521f85979d3e28e9049c85536830755b1b97e211d6f4ba80aff57ca`）；活文档保留 §211 标题行 ＋ 1 行指针。

## §212 执行 **APP-113**（last_ack=APP-113，2026-11-16 21:00:08）｜🔴 **§1 就绪前排队（不丢句）＋ §2 ASR/TTS 并行加载 ＋ §3 非中文语速上限 1.30×→2.0×**｜🔴 **sp4 已出（sp3 逐字节未动）**｜🔴 **验收：丢句 = 0**｜**未打 zip**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字落 companion** ⇒ `status/app/STATUS_APP_sec212_detail_20261116.md`（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。

## §213 执行 **APP-114**（last_ack=APP-114，2026-11-17 10:33）｜🔴 **§1 语速上限 2.00× → 1.70×（所有目标语言、含总倍率）**｜🔴 **§2.1 就绪前队列不再「按时间丢弃」（仅 worker 失败/退出才清空）**｜🔴 **§3 出 sp5（sp4 逐字节未动）＋ 内嵌 EXT 升 v0.4.16**｜🟢 **§4 三臂 10 分钟验收（zh / en / 冷启动）全部 PASS：丢句 = 0、max ≤ 1.70**｜**未打 zip**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字落 companion** ⇒ `status/app/STATUS_APP_sec213_detail_20261117.md`（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
> 🔴 **勘误（APP-115，2026-11-17 14:26）**：本节⑨-3 与中文臂（`…100823`）的 **lag 103.622 s / 末值 22.756 s** 属**计时无效臂**（锁在运行中丢失 ＋ synth_rtf P90=1.282）⇒ **该数字作废**；⑨-3 的「**用户听感判断**」归因**不成立**（是机器被占，非 1.70× 上限）⇒ 🔴 **撤回 §213⑨-3 的归因**，**以 §214 为准**（companion 正文逐字不动，归档件 write-once）。

## §214 执行 **APP-115**（last_ack=APP-115，2026-11-17 14:26）｜🔴 **§1 两条中文热臂计时判为无效（`timing_valid=false`，另写 v2，原 json 逐字节未动）**｜🔴 **撤回 §213⑨-3 的归因**｜🟢 **§2 持锁重跑一条干净中文热臂：PASS（丢句 0／max 1.6972／synth_rtf P90 0.6215／锁全程未被抢：看门狗 63 采样 0 次外来变动）**｜🟢 **§3 ≥1.6× 共 46 句（作废臂的 26 句不作数）**｜**零产品代码改动／零客户包写入／未打 zip**
> 🔴 **本节正文已整块逐字落 companion** ⇒ `status/app/STATUS_APP_sec214_detail_20261117.md`（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。


## §215 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-115**）｜🔴 **接续上一会话（TAKEOVER）并闭合 §214 的未结项「094715 臂的争用源未定位」**｜🟢 **两臂争用源＝reviewer 侧 EXT replay 作业（实物证据）**｜🔴 **锁丢失根因＝reviewer 脚本 `finally` 无条件 `Remove-Item $lock`**｜🟢 **验收 harness 锁获取改 fail-closed（原 fail-open ⇒ 静默覆盖他人锁）**｜**未打包／零客户包写入／零产品代码改动**
> 🔴 **本节正文已整块逐字落 companion** ⇒ `status/app/STATUS_APP_sec215_detail_20261117.md`（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
