### §125 ✅ **APP-059 —— 口径 B 定为唯一口径 ＋ README 说话人标签局限说明 ＋ 两处表述更正 ＋ MANIFEST SHA 三元组 ＋ EXT-028 状态 ＋ HOWTO** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。
> 开工基线：`CORRECTIONS_APP.md` SHA256 `ccdb7712e893c6d20df0fe09c0e438d2f596410db458c5f5c7debb8654b213f8` / **150 636 B** / mtime **2026-11-01 20:56:19** / **59** 条（APP-001…APP-059）⇒ `last_ack` APP-058 → **APP-059**（reviewer：「开始处理时写 last_ack=APP-059」）。

#### ① APP-059 ①：口径 A 作废，**口径 B（文本对齐）为唯一口径**；召回率仍 **FAIL（差 1 个点）**

* **口径 A 作废**（reviewer 判定为**判据实现缺陷**，不算换口径）：拿 App 的行号（48 行）直接对参照的段号（46 段）**没有做对齐**；且检出点记「新说话人的第一行」、参照记「旧说话人的最后一段」⇒ 两者**系统性差 1 段**。
* **唯一口径 = 口径 B（文本对齐）**。原始字段（源 `results/app/app210_app058_recall_diagnosis_evidence.json` → `method_B_text_aligned`）：
  `n_ref_switches=12`｜`n_meas_switches=7`｜`n_hit=7`｜`recall=0.5833333333333334`（**7/12 = 58.33 %**）｜`n_false_positive=0`｜`false_positives=[]`
  命中明细（参照段号 → 实测行号）：`[[2,2],[22,22],[35,35],[36,36],[38,38],[41,42],[44,44]]`
* **结论**：按 APP-058 标准（需 ≥ 8/12）仍 **FAIL，差 1 个点** ⇒ 已按 reviewer 指示记为「**已知局限**」；**App 侧未为凑满 60 % 调阈值、未改参照**。
* 上限参照：`reference_self_consistency` = `n_ref_label_switches=11` vs `n_manual_switches=12`，`manual_only=[19]` ⇒ **参照自身与人工标注就差 1 处 ⇒ 上限 91.7 %**。
* 治本在 **ASR 侧**（说话人切换判定）⇒ **由主会话转达**；App 侧不自行处理。

#### ② APP-059 ①：README_zh/en 已写明说话人标签局限（v2.1 包内实测）

* `Confucius4_LiveCaption_v2.1/README_zh.md` **L92-94**（原文）：
  ```
  * 字幕上的说话人标签（`S1 / S2 …`）属**实验功能**：旁路**默认关闭**；
    开启后若**换人**（说话人切换）**可能漏标**（内部实测：12 个人工标注的换人点
    只检出 7 个）⇒ 标签仅作参考，**不影响**字幕内容与翻译。
  ```
* `Confucius4_LiveCaption_v2.1/README_en.md` **L111-115**（原文）：
  ```
  * Speaker labels on the subtitles (`S1 / S2 …`) are an **experimental feature**:
    the bypass is **off by default**; once enabled, a **speaker change may be
    missed** (internal measurement: 7 of 12 hand-labelled switch points were
    detected) ⇒ labels are for reference only and do **not** affect the caption
    text or the translation.
  ```
* 落地方式（`results/app/app215_readme_speaker_note.py` ⇒ `results/app/app215_readme_speaker_note_evidence.json`）：**定点替换 + 唯一命中断言 + 包外备份 + 写后逐字节复核**（旧正文操作 delete=0，只许改「许可证那 1 行」＋「插入局限说明」）。

  | 文件 | 改前 | 改后 | 旧正文操作（del/rep/ins） |
  |---|---|---|---|
  | `README_zh.md` | 47 497 B / `1b022c33d04f7eca…` | 47 786 B / `6300285e9d7c51bd…`（mtime 21:05:26） | 0 / 1 / 3 |
  | `README_en.md` | 52 950 B / `42cdd5a146a8fb87…` | 53 291 B / `91cbca2ef1096b41…`（mtime 21:05:37） | 0 / 2 / 5 |
  （全量 SHA256 见 `results/app/app215_readme_speaker_note_evidence.json`）

* **ACCEPTED 绑定未受影响**：只动包根**两个文档文件**，`app/` 生产模块未动 ⇒ 按 `app191` 口径重算指纹（**28 个生产模块**）= `b96b6725944c8d19aa9a4a980dee2ac370c6922a19fe7204abae7270b8a9b421` = `ACCEPTED.json` 的 `code_fingerprint` ⇒ **MATCH**。
* 🔴 **zip 未动**（reviewer：「都不用重打包」）⇒ `Confucius4_LiveCaption_v2.1.zip`（20:38，11 233 135 359 B）内 README 仍是**改前**版本 ⇒ **下一版本号打包时带入**；本轮**未打包**（用户未授权打包）。

#### ③ APP-059 ②：更正 §124 的两处表述错误

* **(a) 许可证写反了 —— 撤回 §124③④ 的写法**：以包内 `NOTICE` 为准 ⇒ **pyannote/segmentation-3.0 = MIT**（`NOTICE` L47）、**wespeaker = CC BY 4.0**（`NOTICE` L37）；`THIRD_PARTY.md` L65-66 同（reviewer §1 已核实 NOTICE 正确）。
  **顺带发现并订正**：v2.1 包内 `README_zh.md` L89 / `README_en.md` L106-107 **也把两者写反**（与 NOTICE 矛盾）⇒ 本轮已一并订正（见 ② 的 replace 行：zh 1 行 / en 2 行）。
* **(b)「v2.1 与 v1.13 的差异只有 `speaker_assets` 注释」不成立 —— 撤回该说法**：实测 v2.1 与 v1.13 的 `app/` 有 **5 个 py 文件不同**（共同 28 个 py；**只差注释的是 v2.1 与 v2.0**（仅 `speaker_assets.py`））。逐文件 SHA256（截断 16 位）：

  | 文件 | v1.13 目录 | v1.13.zip 内 | v2.0 | v2.1 |
  |---|---|---|---|---|
  | `live_caption_app.py` | `9f37a399b2b375e2` | `b65e311f9a931442` | `b65e311f9a931442` | `b65e311f9a931442` |
  | `speaker_assets.py` | `1576ac8559e1a634` | `17c1f39c945ae2bf` | `17c1f39c945ae2bf` | `a3690e54892f6bdc` |
  | `speaker_tracker.py` | `ecb3bd6b7f094fae` | `5dd215f4ea03e433` | `5dd215f4ea03e433` | `5dd215f4ea03e433` |
  | `tts_cuda.py` | `bfde75221a040643` | `7d0d886d85cb7ca1` | `7d0d886d85cb7ca1` | `7d0d886d85cb7ca1` |
  | `tts_cuda_sidecar.py` | `269d02f319906a6c` | `84110917d44c13a5` | `84110917d44c13a5` | `84110917d44c13a5` |

#### ④ APP-059 ③：补全 APP-055 的 `app/MANIFEST.json` SHA 三元组 ＋ `v1.13.zip` 与目录不一致

* `app207` 的证据 JSON **只列了 6 个文件**，未列 `app/MANIFEST.json`（它在 **17:09:10** 被重写）⇒ 本轮补齐：

  | 项 | SHA256 | 字节 | 依据 / 实测字段 |
  |---|---|---|---|
  | **改前**（= `v1.13.zip` 内那一份） | `dc62caabd5b9a2cf4f518332db96b6b75a68ff3c737a08dc182405139f1c278c` | 23 422 | zip 内条目 `Confucius4_LiveCaption_v1.13/app/MANIFEST.json`（zip 内时间戳 **2026-11-01 14:53:30**）；内容 `files=14191` / `bytes=13687238157`，notes **含（18）（19）** |
  | **改后**（app207 §⑥ 重写后的落盘值） | `24a45d19d3499fd0aeeaa86068b9846fc45df6c086fa33d1de79964389981749` | 22 937 | mtime **2026-11-01 17:09:10**；内容 `files=14212` / `bytes=13689629685`，notes **无（18）（19）** |
  | **还原后**（写后逐字节复核 ⇒ 与「改后」一致） | `24a45d19d3499fd0aeeaa86068b9846fc45df6c086fa33d1de79964389981749` | 22 937 | 本轮磁盘实测仍为此 SHA ⇒ app207 的还原**未被后续改动覆盖** |

* **依据**：app207 §⑥「MANIFEST 改回 06:08 口径（files=14212 / bytes=13689629685 / notes 去掉（18）（19）两条）」＋ 写后复核 payload 重算 `files=14212` / `bytes=13689629685` 与 06:08 记录**完全一致**。
* 🔴 **`v1.13.zip` 与 `v1.13` 目录不一致**：现存 `Confucius4_LiveCaption_v1.13.zip`（mtime **2026-11-01 15:02:24**，**11 232 363 846 B**，SHA256 `a13bee66c602496cbcefaa6df7b823ae10829ecaf61056ea0cf57820f4647db8`，本轮实测 `results/app/app215_v113_zip_hash.json`）装的是 **14:33 的代码**（zip 内 5 个 py 的 SHA = 上表「v1.13.zip 内」列 ⇒ **不是** 06:08 还原态），且 zip 内条目共 **14 192**（MANIFEST 自称 `files=14191`）而目录 payload 为 **14 212** ⇒ **任何人都不要再从这个 zip 安装 v1.13**。**zip 本身不删、不改名**（只读保留）。

#### ⑤ APP-059 ④：EXT-028 状态（一行）＋ `shared\ext_listen\v21\HOWTO.txt`

* **EXT-028 未通过**：EXT 模块 `live_dub_ext/status/CORRECTIONS_EXT.md` 的 **EXT-032（2026-11-01 20:30，BLOCKING）** 写明「EXT-028 只修了代码，没有交实录」，且当时 `shared\ext_listen\` **目录不存在**；EXT 模块 `STATUS_EXT.md` 的 `last_ack` 仍是 **EXT-031** ⇒ **EXT-032 未执行、EXT-028 的验收一项未交** ⇒ **⑤(b) 的前置条件不满足**。
  （采样率根因与 `resolvePcmSampleRate()` 修复已被 reviewer 认可；EXT-032 要求的 ①tabCapture 生产路径实录 ②三份音频逐段对比（互相关/SNR）③静音成因与 `sync_err` p50/p95 ④`ext032_<时间>\` 目录＋逐段译文 README **均未交**。）
* **HOWTO 已写好（≤ 6 步）**：`C:\Users\Trekker-PTL\shared\ext_listen\v21\HOWTO.txt`（**3 418 B**，SHA256 `99d5079fdd478fc0fa137567ebb1864eaaccea5519a490707c1f56cdcbefd17a`，mtime **2026-11-01 21:16:16**，UTF-8 无 BOM / CRLF / 20 行）。全文如下：

```
<<<HOWTO>>>
```

* 步骤摘要见上方全文（6 步：起桥接 → 加载扩展 → 播英文页 → 点扩展「开始」→ player「开始捕获」跑满 60 s → 保持 player 页开着让线程取录音）。

#### ⑥ APP-059 ⑤：未通知安装 / 未改包 / 未动旧链

* **未通知用户安装**（⑤(b) 完成且用户抽听通过之前）。
* **`start_bridge.cmd` 的「V2.0 发行版」注释未改**（reviewer：留到下一版，不为它重打包）；`README_插件.md` 里的「V2.0 发行版」同理未动。
* **桌面 `实时配音桥接服务 v2.0.lnk` 保留未删**（reviewer 要求，等用户决定）。COM 读回（`results/app/_app215_shortcuts.py` ⇒ `results/app/app215_shortcuts.json`）：
  * `实时配音桥接服务 v2.0.lnk` → 目标 `…\Confucius4_LiveCaption_v2.0\python\pythonw.exe`、工作目录 `…\v2.0\ext\bridge`、2 511 B、SHA256 `416509664e9b4525…`、mtime **2026-11-01 17:56:16**（**存在，未删**）
  * `实时配音桥接服务 v2.1.lnk` → 目标 `…\Confucius4_LiveCaption_v2.1\python\pythonw.exe`、工作目录 `…\v2.1\ext\bridge`、2 511 B、SHA256 `60afd1667573a3e2…`、mtime **2026-11-01 20:42:58**
  * ⇒ 两者**并存**，等用户/reviewer 决定是否清理旧的。（**21:10 reviewer 已删除 v2.0.lnk** ⇒ 见 §126 ②）

#### ⑦ 本轮对仓库的改动（**只有 App 侧**）

* 新增：`results/app/app215_readme_speaker_note.py` ＋ `app215_readme_speaker_note_evidence.json`、`results/app/_app215_shortcuts.py` ＋ `app215_shortcuts.json`、`results/app/app215_v113_zip_hash.json`
* 改：`status/app/STATUS_APP.md`（本节 ＋ 头部 ＋ 归档压缩）
* **客户包 v2.1 内改动（不在仓库）**：`README_zh.md` / `README_en.md` 两个**文档**文件
* **未改**：`status/app/CORRECTIONS_APP.md`（全程只读）、`app/` 生产模块、任何 zip、`start_bridge.cmd`、`live_dub_ext/**`（EXT 模块的文件一个都没碰）

#### ⑧ 收尾复核（`CORRECTIONS_APP.md` 全程只读）

* 开工基线：SHA256 `ccdb7712e893c6d20df0fe09c0e438d2f596410db458c5f5c7debb8654b213f8` / **150 636 B** / mtime **2026-11-01 20:56:19** / 条目 **59**（APP-001…APP-059）
* 🔴 **收尾实测：该文件在本轮中途被 reviewer 追加了新条目**（**不是**「SHA 零改动」）⇒ 收尾值 = SHA256 `4aab04746e9356d552af2455ff7ebe3ae2d195205ef39437c772cfd3d2dadade` / **151 541 B** / **21:09:20** / **60 条（新增 APP-060）** ⇒ 追加内容见 **§126**；**本模块全程只读，未写入**。
* 本轮**未打包**（reviewer：「都不用重打包」；用户未授权打包）⇒ 旧目录与旧 zip **一个都没覆盖、没删除**

#### ⑨ 待 reviewer 复核 / 未达成（不粉饰）

① ⛔ **APP-058 判据④ 召回率仍未达标**：唯一口径 B = **58.33 %（7/12）**，需 ≥ 8/12 ⇒ **差 1 个点** ⇒ 已按 reviewer 指示记为「已知局限」＋ README 写明；**未调阈值、未改参照**；治本在 ASR 侧（请主会话转达）。
② ⛔ **⑤(b) 仍未做**：EXT-028 未通过（EXT-032 未执行）⇒ 本轮只把**用户操作步骤**准备好（HOWTO.txt），等 EXT 侧交出实录后由用户手势执行。
③ ⛔ **v2.1 的 zip 与目录 README 现已不一致**（zip 内为改前版本）⇒ 下一个版本号打包时须带上新 README；**本轮未打包**。
④ ℹ️ **请 reviewer 确认 v2.1 即交付版**（v2.0 首包违反「旧 zip 不覆盖」，v2.0 目录与 zip 已原样保留）。
⑤ ℹ️ **桌面两个桥接快捷方式并存**（v2.0 / v2.1）⇒ 是否清理旧的请用户/reviewer 定。
⑥ ℹ️ **本轮只补证据与表述，未新增功能**；`app/` 生产模块 **0 改动** ⇒ ACCEPTED 绑定不受影响（已重算核验）。
