# STATUS_APP 归档（§109…§113 章节正文，只读）

> 本文件是 `status/app/STATUS_APP.md` 的**只读归档**（内容一字未删）。
> 归档原因：**APP-049 限额**（STATUS ≤ 40 KB / ≤ 300 行 / 每节 ≤ 60 行）⇒ §114 追加前把 §112 正文移到这里。
> 归档时间：2026-10-30 23:20｜归档时 STATUS = 33971 B / 204 行 / SHA256 528e66bef3c24b8a7a75c130813fb474935265c6c94996c443c1a0df11c504f6

### §112 ✅ **客户包「运行时可加载性」独立验收：21 PASS / 0 FAIL（含 3 条反证）｜ 发现并修掉「宿主 PYTHONPATH 污染」使旧结论变假通过** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **巡检口径**：`status/app/CORRECTIONS_APP.md` SHA256 `bb07c52697ecb5aa954169cf32d389095e60b2b35dd4f8ae99752292505d5ec3` / **118 903 B** / mtime `2026-10-30 12:49:16` ⇒ `## APP-xxx` **49** 条、最大 **APP-049** = `last_ack` ⇒ **无新纠偏条目**（**第 31 次**同一口径复核）⇒ `last_ack` **保持 APP-049**；该文件**只读零改动**。按 **APP-046**「追平后仍有未完成项 ⇒ 继续做，不空转」推进本节。
- 🔴 **开工自查（半交付四层，§104 归纳）**：① zip 旧（v1.12 zip 生成于 **11:20**，**不含** APP-045/047/048 任何改动）② 包目录内容合规 ✔ ③ 包目录代码 ⇄ 仓库 **28/28 归一化后逐字节一致**（`MISMATCH=0`）④ 产物入库 ✔（`status/archive/` 6 个文件 + `app164/165/166` 证据均 `git ls-files` 在册）。
- 🔴 **锁**：`shared/MACHINE_LOCK` 被 **TTS 持有**（`module: tts` / `pid: 41364` / `started: 2026-10-30 20:13:40`）⇒ 本轮**未取锁**、**未抢锁**、**未打包**、**未重打 zip**、**未发 FTP**（守 **APP-035** FTP 永久关闭）；本轮全部工作为**只读 + 离线判据**（不计时 ⇒ 不需要锁）。
- 🔴 **并发会话**：工作区有 `results/app/app167_*`（20:23:36）与 `live_caption/sync_c171_*`（20:21:10）**未跟踪在制品** ⇒ 判定**并发 App 会话正在作业** ⇒ 本轮**不吞、不提交**这 3 个文件；`status/app/CORRECTIONS_APP.md`（`M`）亦**未暂存**。
- ✅ **本轮实质产出 = 新增 `results/app/app168_pkg_runtime_import_probe.py`**：**用客户包自带 `python/python.exe`（3.12.10）在包内真实 import 包内模块**，把「包目录对（静态字节一致）」升级成「**包内运行时真的能加载**」。

| 判据组 | 内容 | 结果 |
|---|---|---|
| R1 | 包内自带 python 存在 + 版本可读 | **PASS**（3.12.10） |
| R2 | 包内 `gui_status.py`（APP-048 新增）可 import；`build_sections()` 返 **3** 区（`asr`/`mt`/`tts`）；三区 `render()` 可执行 | **PASS** |
| R3 | 包内 `live_caption_app.py`（APP-048 改后）可 import，`App` 存在 | **PASS** |
| R4 | 包内 `asr_spk/` 3 个资产在**真实加载路径**（`sys.path.insert`）下可 import | **PASS** |
| R5 | `EMBED_RANGE_LO/HI == [100, 2048]`（ASR-031 §11.2） | **PASS** |
| R6 | `THREAD_VARS` 含 `OMP_NUM_THREADS`/`MKL_NUM_THREADS`/`OPENBLAS_NUM_THREADS`（APP-043 线程限制） | **PASS** |
| R7 | `speaker_assets.resolve()` ⇒ `ok=true`；wespeaker / pyannote_seg OV IR 目录**真实存在**（APP-044） | **PASS** |
| R9 | 包内 python 的 `sys.path` **不含包外路径**（无宿主 `PYTHONPATH` 污染） | **PASS**（`foreign=[]`） |
| R8 | 包内 `torch`/`qwen_asr` 存在性（**只记录事实**） | `torch=ModuleNotFoundError`、`qwen_asr=ModuleNotFoundError` |
| B1 反证 | 不在 `sys.path` 时 `asr052_speaker_tracker_api` **必须** ImportError | **命中**（证明 R4 非恒真） |
| B2 反证 | **影子目录**（无 `models/spk`）⇒ `resolve().ok` **必须** false（**真包零改动**） | **命中**（证明 R7 非恒真） |
| B3 反证 | **注入**包外 `PYTHONPATH` ⇒ R9 **必须** FAIL | **命中**（证明 R9 非恒真） |

- 🔴🔴🔴 **本轮抓到的真缺陷（验收环境级）**：宿主 WorkBuddy 自设
  `PYTHONPATH=C:\Program Files\WorkBuddy\resources\app.asar.unpacked\cli\vendor\shim`
  ⇒ **被继承进包内 python** ⇒ 包内 `sys.path` 多出一条**客户机上根本不存在**的路径
  ⇒ ① `import torch` 会「成功」但 `torch.__file__ is None`（**namespace package 假阳性**）
  ⇒ ② 任何模块可能从 shim 加载 ⇒ **验收结论会假通过**。
  ⇒ 修法：验收子进程**置空 `PYTHONPATH`/`PYTHONHOME`** + 临时脚本放在**包内 cwd**（使 `sys.path[0]` = 包 app 目录，模拟真实启动形态）；并**新增 R9 + B3** 把「环境洁净度」变成**可判据项**。
- 🔴 **由此更正的旧记录**：**§46.5「包内 site-packages `torch`/`qwen_asr` ABSENT」被证实**（此前 `torch=PRESENT` 是宿主 `PYTHONPATH` 造成的假阳性）；**§46.5「交付路径不走那两个类，当前客户启动路径不受影响」的结论仍然成立**（本轮 `app168` 实测 `live_caption_app.py` 在包内 python 下 import 成功 ⇒ 无 `ModuleNotFoundError`）。
- ✅ **判据鉴别力实测（拿「已知有缺陷的旧产物」跑一遍）**：对旧包 **v1.5**（无 `gui_status.py` / 无 `asr_spk/` 3 资产 / 无 `models/spk`）跑同一套 ⇒ **9 PASS / 12 FAIL / verdict=FAIL** ⇒ 判据**能识破**、不是恒真。
- 🔴 **自踩坑（本轮踩了两次，均已修）**：① **版本号解析**用 `tail.split('.')[0]` ⇒ `v1.12` 只取到 `'1'` ⇒ 所有包版本都成 `(1,)` ⇒ 验收跑在**备份目录** `v1.0.bak_20261020` 上 ⇒ 满屏 FAIL ⇒ 改用正则取完整数字段 + **排除 `.bak_*`/`*_backup`** + **元组比较**（`1.9 < 1.10`）；② **B2 反证硬依赖 `speaker_assets.py` 存在** ⇒ 对旧包抛 `FileNotFoundError` ⇒ 脚本崩、证据不落盘 ⇒ 改为**优雅降级**（前提不存在 ⇒ 记「不适用」但仍 PASS，**且脚本不崩**）。
- ✅ **本条已完成**（离线部分全部闭环）｜ **本条需等 reviewer 复核**：① 「包内运行时可加载」这条新判据的口径；② 宿主 `PYTHONPATH` 污染对**历史验收结论**的影响范围（§109/§110 只做了静态字节比对，未受污染影响，但需 reviewer 确认）。
- ✅ **独立复核 `results/app/app169_status_selfcheck.py`** ⇒ **14 PASS / 0 FAIL / verdict=PASS**（**不复用写入器逻辑**，另起一套实现重算）：V1 限额（22 435 B / 145 行）｜V2 **自指大小一致**（文内 `22435 B / 145 行` == 实际）｜V3 头部 5 个字段**各只出现一次**｜V4 `last_ack=APP-049` == CORRECTIONS 最大编号（**49** 条）｜V5 章节连续无重号（§109…§112）｜V6 每节 ≤ 60 行（最长 §112 = **38** 行）｜V7「最近更新」≤ 15 行（**5**）｜V8 **CORRECTIONS_APP.md 零改动**（SHA256 `bb07c52697ecb5aa…` 与 §112 开工实测一致）｜V9 归档 6 文件可读｜V10 头部阻塞栏非空。
  - 产物：`results/app/app169_status_selfcheck.py` — **6133 B** / SHA256 `8271941e2477c1174fd2029c13d0a36180ddab3cbf8dc7332af2b38945df03b6` / mtime `2026-10-30 20:43:45`；`results/app/app169_status_selfcheck_evidence.json` — **2813 B** / SHA256 `3b88c284a152e3c7a6b3e4e0ccc75c758f383a5c8cd4ab8c0817ca269c664179` / mtime `2026-10-30 20:45:36`（`n_pass=14` / `n_fail=0` / `verdict=PASS`）
- 🔴 **仍未推进（需真机 / 用户）**：APP-043 真机验收（`pythonw.exe` 冷启动 ＋ SPE Q&A 双说话人 ＋ GUI 加速播放 ＋ 3 段 1.2–1.3× 配音实听）｜ APP-045③（验收通过后才更新桌面快捷方式，**当前仍指向 v1.5**）｜ **v1.13 打包**（守用户 11:30 指令「不通知不打包」）｜ APP-048「和 v1.13 一起交付」排期 ｜ MiniMax 回转写错误率对比（本模块不自做）。
- ✅ **产物（均已落盘，附指纹）**：
  - `results/app/app168_pkg_runtime_import_probe.py` — **21 392 B** / SHA256 `21b8545310b1934352e27e15df4f6e332ac6a802526289cfff9b412cc565601e` / mtime `2026-10-30 20:41:41`
  - `results/app/app168_pkg_runtime_import_probe_evidence.json` — **4 534 B** / SHA256 `e63ef5b214a59c2458387e8b83d94be2fc87cd65468c71918a35dfb1470a79e9` / mtime `2026-10-30 20:41:47`（`n_pass=21` / `n_fail=0` / `verdict=PASS`）
