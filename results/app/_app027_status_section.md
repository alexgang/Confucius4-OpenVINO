## §27 巡检（无新纠偏条目，第 11 次同一口径）+ ✅ **交付 zip 重打闭环**（持共享机器锁 → 原子写 → 内容级 PASS → 独立复核 → FTP_Share 重发）（2026-10-25 02:08）

### §27.0 巡检结论：无新条目，`last_ack` 不变

- `status/app/CORRECTIONS_APP.md`（**只读**，本轮**未改**）：SHA256 `8ccf661c7f1ef5c527871011ed898ae6b9c44855793749105a4461e3f10de8cf`、
  **27 413 B**、mtime `2026-10-24 17:01:54.766142900 +0800`。
- `## APP-xxx` 条目 **10** 条：APP-001 / 002 / 003 / 004 / 005 / 006 / 007 / 008 / 009 / 010（行号 1/27/35/60/77/98/114/134/142/154）。
- `STATUS_APP.md` 头部 `last_ack: APP-010` ⇒ **无编号更大的新条目** ⇒ **本轮不执行任何 APP 条目**，
  `last_ack` **保持 APP-010** 不变（巡检口径第 **11** 次一致）。

### §27.1 ✅ 本轮核心：把 §26 头部「交付 zip 是坏的」这条**阻塞项真正闭环**

§26.8 记的是「⏳ **未重打**交付 zip（共享锁被 MT 持有 ⇒ 等，不抢锁）」。
本轮 **共享机器锁已释放**（`shared/` 下**无** `MACHINE_LOCK`）⇒ 按 §26.8 指定的顺序执行并全部落盘。

#### §27.1.1 打包前的事实核对（先查再打，不盲打）

| # | 核对项 | 实测 |
|---|---|---|
| 1 | `shared/MACHINE_LOCK` | **不存在** ⇒ 锁空闲（`shared/` 下仅 `README_LOCK.md` / `NOTICE_mt_to_app_20261024.md` / `NOTICE_tts_to_app_20261024.md`） |
| 2 | 仓库 ⇄ 客户包关键 .py（归一化换行） | **4/4 一致**：`translator.py` `11deb2b6…` ｜ `live_caption_app.py` `47357762…` ｜ `tts_worker.py` `3c78cce8…` ｜ `tts_service.py` `9349e408…`（字节差**仅** CRLF/LF 差异） |
| 3 | `pack_v13.py --dry-run` | **PASS** —— 将打包 **13 977 文件 / 13 667 889 883 B（12.73 GB）**；排除 `__pycache__` 4 个 / `.bak_*` 2 个；关键文件 **40 项全 [OK]**（含 INT8-CW / INT4-CW / Qwen3-TTS 全部 IR 与 `preset_A.wav`）；**内部素材闸门命中 0**；`results/` 下 `*_spoken.*` **0 条命中** |
| 4 | 磁盘余量 | C: 1.9 T 总 / 1.4 T 已用 / **476 G 可用**（76%）⇒ 空间充裕 |

#### §27.1.2 持共享机器锁重打（`pack_v13.py` 自带锁）

- 锁记录（`shared/MACHINE_LOCK` 实测内容）：
  ```
  module: app-pack
  pid: 21324
  started: 2026-10-25 01:47:44
  host: LAPTOP-0GDQGD3I
  ```
- `pack_v13.py` 默认即取锁（`machine_lock_app.LockHeld(module='app-pack', timeout=3600)`，L490），
  `--dry-run` 刻意**不持锁**（只读统计）⇒ 本轮**未用 `--no-lock`**，**未抢锁、未回收他人锁**。
- 打包耗时 **14 min 39 s**（01:47:44 → 02:02 前后），结束后脚本自行 `[lock] 已释放`。
- 🔴 **原子写生效**：§24 修的「先写 `ZIP + '.tmp'` → 校验通过 → `os.replace()` 原子改名」这条路径**真实跑通**
  ⇒ 本轮**没有**再出现「好包被截断覆盖」的事故形态。

#### §27.1.3 打包结果（原始输出字段）

| 校验项 | 结果 |
|---|---|
| MANIFEST | `version = 1.4` ｜ `files=13977` ｜ `bytes=13667889883` |
| zip 条目 | **13 978**（不含 MANIFEST 自身；含则 13 978）**== MANIFEST files 13 977** ✔ |
| zip 原始体积 | **13 667 907 045** == MANIFEST bytes 13 667 889 883 + MANIFEST 自身 17 162 ✔ |
| 旧产物清理 | 9 条精确路径 `[已移除]`（含 `results/mt2_memory.json`、各 `.bak_c105/c106/c108/c109`） |
| 缓存目录清理 | 20 条目录前缀 `[已移除]`（含 `app/tts_npu_cache/`、`app/npu_cache/`、`app/ov_cache/`、`app/mt_cache/`、`_backup_c111/`…） |
| 内部会议内容 | `*_spoken.*` **0 条命中**；点名文件 **0 条命中** |
| TTS 音色素材 | 音色 B/C/克隆素材 **0 条命中** |
| 内容一致性（zip ⇄ 包目录，逐文件 SHA256） | **13 978 个文件全部逐字节一致** |
| 打包结论 | **PASS** `md5=1ccdb73982dc4f8d1077fb55b956ad86` |

#### §27.1.4 ✅ 独立复核（`live_caption/verify_pkg_zip.py`，与打包脚本**分离**）

```
[1] zip ⇄ 包目录：比对 13978 个文件
  ✓ 全部逐字节一致
[2] 仓库 ⇄ 包目录（关键 .py，换行符归一）：一致 16 / 不一致 0
结论：PASS
```

> ⇒ **交付判据 = 「zip 内容级 PASS」**已满足（不是「包目录对」）。

#### §27.1.5 ✅ FTP_Share 重发（`publish_ftp.py`，持锁 `app-ftppub`）

- 复制 **11 216 047 396 字节 / 9.0 s（1 188.9 MB/s）**（流式 + 临时名原子改名）。
- 源 SHA256 `01ebfebec0f6fe8ea47e0826ad7d65d647f8bbed86be8eaf56815eb859d99428`
  == 副本 SHA256 `01ebfebec0f6fe8ea47e0826ad7d65d647f8bbed86be8eaf56815eb859d99428` ⇒ **PASS**。
- 🔴 **APP-009③ 遵守**：只往 `FTP_Share/` 目录**放文件**（zip + SHA256），**没有重新开启 FTP 服务**
  （`ftp_share.py` 未启动、未改配置、未共享整个用户目录）。

#### §27.1.6 ✅ 交付物最终状态（实测，本轮复核）

| 文件 | 字节 | mtime | SHA256 |
|---|---|---|---|
| `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4.zip` | **11 216 047 396** | 2026-10-25 01:59:18 | `01ebfebec0f6fe8ea47e0826ad7d65d647f8bbed86be8eaf56815eb859d99428` |
| `C:\Users\Trekker-PTL\FTP_Share\Confucius4_LiveCaption_v1.4.zip` | **11 216 047 396** | 2026-10-25 02:04:11 | `01ebfebec0f6fe8ea47e0826ad7d65d647f8bbed86be8eaf56815eb859d99428` |

- 两份 **字节数与 SHA256 双一致** ⇒ FTP 副本 = 主包。
- 🔴 **`.tmp` 残包已消失**（§26.7 第 2 项那个 8 271 022 632 B 的坏残包本轮被 `pack_v13.py`
  「已清理上次残留的临时 zip」路径删除）⇒ 磁盘上**不再有**第二个半成品 zip。
- zip 结构独立复核：`entries=13978`、`testzip()=None`（无坏条目）、尾 64 KB 内 **`PK\x05\x06` EOCD 签名存在**。
- 🔴 **§26.7 第 1 项「主包是坏的」在本节更正**（**不改** §26 原文）：本包**完好**。

### §27.2 ✅ 客户包内容合规复核（本轮逐项实测，全部只读）

| # | 检查项 | 实测结果 |
|---|---|---|
| 1 | 内部会议转写（`*_spoken.*`） | **0 个文件**（全目录递归扫描） |
| 2 | 包内音频素材 | 共 23 个 `.wav/.flac/.mp3/.m4a`，其中 **22 个是 scipy 自带测试数据**（`python/Lib/site-packages/scipy/io/tests/data/`），**非测试数据只有 1 个**：`models/qwen3tts/voices/preset_A.wav` ⇒ **无会议录音、无克隆音色、无同事音色 B** |
| 3 | TTS 音色目录 | `models/qwen3tts/voices/` **只有 `preset_A.wav`** ⇒ 无 `preset_B`/`preset_C`/`clone_*` |
| 4 | 翻译模型目录 | 只有 `mt2-int8sym-cw-q`（默认）+ `mt2-int4sym-cw-q`（可选）；**无旧量化目录**（`int8sym-cw-q`/`int4sym-cw-q`）⇒ APP-005② 收口状态保持 |
| 5 | APP-008①「新切段规则待质量复核」 | ✅ 包内 `README_zh.md` **L392** 标注「**新切段规则待质量复核**」；**L394** 写明退回开关 **`LIVECAP_GUARD_REL=0`** |
| 6 | APP-008① 三个相对判据开关 | ✅ 包内 `app/live_caption_app.py` L175 `LIVECAP_SIL_REL` / L192 `LIVECAP_SPK_REL`（及 `GUARD_REL`）**均在** |
| 7 | APP-010「TTS 实验性 / 默认关闭」 | ✅ 包内 `README_zh.md` **L42 / L44 / L390** 标「**实验性功能**」「**默认关闭**」；L47 写明需在界面手动开启 |
| 8 | 仓库 ⇄ 包目录关键 .py | **16/16 一致**（`verify_pkg_zip.py` 口径）；本轮另单独核 4 个核心文件 `4/4` 一致（归一化换行） |

### §27.3 ✅ 本轮落盘产物（附字节 / mtime / SHA256）

| 文件 | 字节 | mtime | 说明 |
|---|---|---|---|
| `results/app/app027_delivery_evidence.json` | **2 731 B** | 2026-10-25 02:08:26 | 交付侧证据汇总（zip 指纹 / 结构 / MANIFEST / 素材扫描 / 仓库⇄包 / README 标注行号） |
| `results/app/_app027_delivery_evidence.py` | 新增 | 2026-10-25 02:07 | 上述汇总脚本（只读；不跑推理/测速/占 GPU） |
| `results/app/_app027_cmp_repo_pkg.py` | 新增 | 2026-10-25 01:50 | 仓库 ⇄ 包目录 4 文件逐字比对（含 diff 打印） |
| `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4.zip` | **11 216 047 396 B** | 2026-10-25 01:59:18 | **交付主包**（14 978 条目，内容级 PASS） |
| `C:\Users\Trekker-PTL\FTP_Share\Confucius4_LiveCaption_v1.4.zip` | **11 216 047 396 B** | 2026-10-25 02:04:11 | **FTP_Share 副本**（与主包 SHA256 一致） |

### §27.4 ✅ 纪律自检

- 🔴 **未改/未提交** `status/app/CORRECTIONS_APP.md`（只读；本轮复核 SHA256 仍 `8ccf661c7f1ef5c…` / 27 413 B / mtime `2026-10-24 17:01:54`）。
- 🔴 **未吞** ASR/MT/TTS 的未提交改动（`git status` 里 `status/CORRECTIONS.md`、`status/app/CORRECTIONS_APP.md`、
  一大批 `live_caption/diag_c111_*`、`reports/**` 等**别的模块**的改动**一律未 `git add`**）。
- 🔴 **未改产品代码**（本轮 `live_caption/translator.py` / `live_caption_app.py` / `tts_worker.py` / `tts_service.py` **零改动**）。
- 🔴 **未 import 被测模块**（脚本只读文件/JSON、只走 `zipfile`/`hashlib`/`os`）。
- 🔴 **未跑推理 / 测速 / 占 GPU**；🔴 **未开 FTP 服务**（APP-009③）。
- ✅ **共享机器锁**：本轮**取了自己的锁**（`module: app-pack` / `pid: 21324` / 01:47:44），
  脚本结束时**自动释放**（收尾实测 `shared/MACHINE_LOCK` **已不存在**）；**未抢锁、未回收他人锁**。
- ⚠️ **计时窗口内的自我污染**：打包窗口（01:47–02:02）内**未执行任何会启动 `python.exe` 的操作**，
  只做了 `Read`/`grep` 等只读核查 ⇒ 打包耗时数字**未被自己的操作污染**。

### §27.5 ⛔ 本轮**未做**的事（边界，与 §26 一致）

- 🔴 **未改渲染层三处**（`_mt_of` / `_save_text` / CLI `run_cli` 改按 `mt_units()`）⇒ 仍**等 reviewer 裁定**
  （§26.6 的三问：① 字幕「按 ASR 段 → 按完整句」行数 3.3× 是否可接受；② 重复句「字幕 2 次 / 语音 1 次」是否接受；
  ③ `flush()` 补翻的 `seg=None` 句单元挂在最后一段还是单列）。
- 🔴 **未做** GitHub 旧 SHA 的 gc（待用户决定）；🔴 **未做** 包体 12.73 GB 优化。
- ⛔ **APP-006 第 3~7 步**（历史改写 + force push）—— §11.2 清单**等 reviewer 复核**（该条第 2 步明确要求停下）。
- ⛔ **v1.4 TTS 音质**未达标（TTS-009/TTS-010）⇒ TTS 保持**实验性、默认关闭**（包内 README 已标注）。
- ⛔ **V7 残句代价**待用户确认（链首段半句残句 12 段语料 5 行/58 字 ⇒ 需 App 做「同段二选一」）。

**ack: APP-010**（本轮**无新纠偏条目**；巡检口径第 **11** 次一致；**交付 zip 重打闭环已完成** ——
持共享锁 → 原子写 → 内容级 PASS（13 978 文件逐字节一致）→ 独立复核 PASS → FTP_Share 重发（SHA256 一致）；
客户包合规逐项复核通过（无会议录音/无音色 B·C/无克隆素材）；产品代码零改动；
渲染层三处仍等 reviewer 裁定）
