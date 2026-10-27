## §67 ✅ **§65 + §66 已落盘并 push** + 🔴 **「替代校验」脚本 `app067` 已建**（等锁重打包中）（2026-10-27 11:09）

### §67.1 ✅ 已提交 + 已 push（普通 push，未 force）
- `2d19402 feat(app): APP-024① 首包拆两段（queued_s/synth_s）+ §64`
- `2913a53 docs(app): §65 + §66 —— §64 落盘 + 用户新口径（不做一致性校验 / 不开 FTP）` ⇒ push **`0d1be9d..2913a53`** ⇒ 远端 `origin/main` = `2913a53` ✅。
- ✅ **未提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占；其工作区实测 **+268 / −0** 行 = reviewer 自己写的，**未入库、未还原**）；✅ **未吞**其它模块改动（提交前实测 **479** 项全部保留）。

### §67.2 ✅ 「替代校验」脚本 `results/app/app067_repack_after_lock.py`（**新口径的落地工具**）
🔴 用户新口径取消的是「一致性校验 + FTP」⇒ **不能什么都不做地交付** ⇒ 用一道**只读本地**、**秒级**的检查替代那 4 min 42 s 的全量 SHA256 复核：

| 检查 | 内容 | 成本 |
|---|---|---|
| ① **zip ⇄ 包目录 `.py` 逐字节 diff** | 只读 zip 的 central directory + 22 个 `.py` 的字节 | 秒级 |
| ② **`HEAD` ⇄ 包目录 关键 `.py`** | 归一化换行后逐字节比（22 个） | 秒级 |

🔴🔴 **脚本自身踩了一个「假差异」并已修**：初版把 `app/_probe_tts_cuda.py` 报成「zip 内缺失」⇒ 查证：该文件是 **10-25 的开发期探测脚本**（`_` 前缀 ⇒ `pkg_exclude.is_app_dev_only` 判定为**开发专用** ⇒ **本来就不该进包**）⇒ 「zip 内缺失」是**正确行为**，**不是差异** ⇒ 修法 = **跳过 `_` 前缀文件**并单独列出（`skipped_dev`）。
⇒ 🔴 **教训**：**任何「zip ⇄ 包目录」比对，都必须用 `pkg_exclude` 的排除口径**，否则会把「按规则被排除的文件」误报成「缺失」。
✅ **干跑实测**（当前旧 zip）：`py_diff = 2`（**精确指向** `tts_service.py` / `tts_worker.py` 两个真实代差）、`HEAD ⇄ 包 = 22/22`、`skipped_dev = ['app/_probe_tts_cuda.py']` ⇒ **判据可用**。

### §67.3 🔴 **重打包在等 ASR 活锁**（后台任务 `yteoQA`）
- 锁：`asr PID 34724` / `pya_app_baseline_base61` / exit=259 ⇒ **活锁** ⇒ **不抢、不删**。
- ✅ 后台任务 `app067_repack_after_lock.py --max-wait 5400` **已在跑**：等锁 → 调 `pack_v13.py`（**自带** `machine_lock_app.LockHeld(module='app-pack')` 取锁 + **安静窗口**双闸门）→ 打包 → 跑上面两道**只读本地**检查 ⇒ **不跑** `verify_pkg_zip.py`、**不跑** `publish_ftp.py`、**不开** FTP。
- 🔴 **打包当前状态（未完成）**：zip 仍是 **10:28:15** 的旧版（**11 216 287 107 B**）⇒ **仍不写「已交付」**。
- 包目录（已同步 APP-024①）：`app/tts_service.py` **90 869 B** / SHA256 `8d8f0779616aefa3bb90c6c61e1550912b51cb9b4aa75aa7fd5d036c5e0a12a0`；`app/tts_worker.py` **94 173 B** / SHA256 `a152ce19202866a98dac0792c4c7fe03ac631da3d92a5abb70c9fdc97d4b68bc`。
- ⚠️ **打包**会写 `results/app/pack_v15_log.txt` 等日志；**这些是打包副产物，不单独构成「已交付」**。

### §67.4 ⚠️ 本轮纪律自检
✅ 未跑推理/测速｜✅ 未调 MiniMax｜✅ 未改 `CORRECTIONS_APP.md`｜✅ 未吞他模块改动｜✅ **未抢锁、未删活锁**｜✅ 仓库⇄包只做**定点替换**｜✅ 提交**逐文件 `git add`**｜✅ **普通 push，未 force**｜✅ **未开 FTP 服务**（新口径）｜✅ **未跑全量一致性复核**（新口径）｜🔴 **zip 尚未重打 ⇒ 不写「已交付」**。
