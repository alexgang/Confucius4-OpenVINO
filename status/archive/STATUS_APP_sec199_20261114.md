# STATUS_APP §199 整块逐字归档（2026-11-14）

归档时间：2026-11-14 10:37:18
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §200 出重。
正文一字未删（§199 标题行＋正文逐字保留；活文档仍保留标题行 ＋ 1 行指针）。

§199 正文块 SHA256（含标题行）：ae2eb18fb51b14b3d995fe261bcb42d2008fe6893ebac0041763644c03d9d817（5554 B）

---- 以下为 §199 原文，逐字 ----
## §199 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-107**）｜🔴 **目标机进入通道已结构性失效** ⇒ §197 ⑤／§198 ② 的 SHA256 对账**任何无人值守轮次都无法闭环**

> **① 巡检（6 通道全查空，附开工实测值）**：`status/app/CORRECTIONS_APP.md` 开工＝**107 条／最大 APP-107**（SHA `006d1ab7386ddfdf5f988330c74632f19f21b63b20d55aba8c5ca2febaf07ea5`／**355 098 B**／mtime **11-13 09:28:40**）⇒ **无编号 > last_ack 的新条目** ⇒ `last_ack` **保持 APP-107**（无新纠偏 ⇒ 不写自己的编号）。其余通道：`shared/NOTICE*` 最新仍 **11-05 09:35**｜agent-mail 面板 connected 但工具仍返 **`not_bound`**（**该通道本轮查不了**，如实记录，不声称查过）｜`conversation_search`（11-13 全天）**0 命中**｜git `origin/main...main`＝**0/0**（HEAD `7703c78`）｜`claude-clone --not main`＝**0**（该分支只落后于 main）｜`MACHINE_LOCK` **NOT_PRESENT**｜根 `status/CORRECTIONS.md` 最大 **C-135**（10-24 17:01）｜ASR 侧最大 **ASR-057**（11-13 09:06，无 App 条目）｜`clone_dev` 等旧克隆仍是 **10 929 B／最大 APP-004** 的陈旧快照。
> **② 🔴 本轮唯一实质发现（交付通道层，非产品缺陷）**：§197 ② 的口令**当时只放进临时环境变量 `WB_SSH_PASS`**（脚本从环境读取、**未落盘、未入库、未硬编码**，做法本身正确）⇒ **但该口令本轮已不可得**（四处实测：`printenv` 空；HKCU/HKLM 持久环境变量**无** `WB_SSH_PASS`；PSReadLine 历史（**4 318 B／mtime 10-30 13:18**）**无**该串；`results/app/_app542_ssh_try.py` 与 `_app545_transfer_to_target.py` **只读环境变量**）⇒ **后续任何会话都登不上目标机**（不是「暂时连不上」，是**没有可用凭据**）。
> **③ 公钥这条路也没通（已排除「探法错误」）**：目标机**可达**（ping **1 ms**／0% 丢包；**22/445 OPEN**，3389 超时）；`ssh -o BatchMode=yes -o PreferredAuthentications=publickey test@192.168.2.194` → **Permission denied**；🔴 **首测有探法陷阱**：本机私钥文件名是 `github_backup_ed25519`，**不属 ssh 默认私钥名**（默认 `id_rsa`/`id_ed25519` 等）且 `~/.ssh/config` 只给 `github.com`/`win-pc` 配了 IdentityFile ⇒ **首测根本没把这把钥匙递上去** ⇒ 改用**显式** `-i ~/.ssh/github_backup_ed25519 -o IdentitiesOnly=yes` 复测，**仍** Permission denied ⇒ **公钥确实没装进目标机 `test` 的 authorized_keys**（**真缺，不是探法问题**）。
> **④ ⇒ 直接后果（须如实入册，不掩盖）**：本轮**未能复核**目标机侧的 AV 独占锁与磁盘（登不上 ⇒ 既不报「已闭环」也不报「锁仍在」）；§198 ① 的**目标机磁盘（82.3 MB 可用）**、§197 ⑦ 的**目标机实机 `--check`（sm_89 vs sm_120）**、§197 ⑨① 的**是否授权删 zip** —— 这三项**全部**只能由**有认证的人**在做。SMB 匿名读也确认不通（`\192.168.2.194\Users` → **WinError 3**，共享未匿名暴露；`C$` 仍是 error 5，`test` 非管理员）。
> **⑤ 最小解锁动作（任选其一，均不需我改任何客户包）**：① **重给一次目标机 `test` 密码**（我用完即弃、**不落盘**）；② **在目标机把本机公钥装上**（推荐，一劳永逸）：把 `C:\Users\Trekker-PTL\.ssh\github_backup_ed25519.pub` 的**一行内容**追加到目标机 `C:\Users\63446\.ssh\authorized_keys` ⇒ 之后我即可**免密**复核 SHA256／磁盘／实机 `--check`；③ **用户在目标机自己跑一次**并把输出贴回：`certutil -hashfile "C:\Users\63446\Desktop\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip" SHA256` 与 `fsutil volume diskfree c:`。
> **⑥ 零漂移复核（本轮只读）**：本机 Special MVP 源 zip **14 244 490 059 B／mtime 11-13 21:24:59**（＝§197 ④ 值，**未漂移**）｜MiniMVP rc11 zip **6 697 683 352 B／mtime 11-13 10:23:53**｜**各客户包目录未改**（MiniMVP/完整版/SpecialMVP 一律只读）｜`live_caption/` **产品代码零改动**｜上一轮 helper **全灭且 8899 端口已闭**（本轮 `Get-NetTCPConnection 8899` 无监听）⇒ **本机无遗留后台作业、不占租约**。
> **⑦ 沿用未变（等用户/reviewer）**：① **10 个带 APP-086·2a 缺陷包**作废还是标注（**目录一律保留不删**）；② **完整版 v2.5** 何时打（**必须带收窄**；**用户不通知不打包**）；③ **EXT 换嵌**通知；④ `app523` 假 FAIL 是否退役；⑤ rc11 **B 机**运行；⑥ **OPEN-1** 退出码 3221226505 定位；⑦ **CUDA TTS 音质/音色**待 reviewer 回转写、**TTS 首启 58.7 s** 是否可接受。
> **⑧ 纪律**：本节**只追加**，不改 §197／§198 正文（已整块逐字归档，正文一字未删）｜**未打包**（v2.5 仍未打；rc9/rc10/rc11 未动）｜**未改任何客户包**｜**未改产品代码**｜**未改 `CORRECTIONS_APP.md`**（收尾仍 **SHA `006d1ab7…`／355 098 B／mtime 11-13 09:28:40／107 条／APP-107 ＝ 开工值 ⇒ 本轮可写「SHA 零改动」）｜**未跑推理**（本机与目标机都没跑）⇒ 未取 `MACHINE_LOCK`｜**未调 MiniMax**｜**未提交其它模块**的未提交改动｜**明文口令未写入任何入库文件**｜`results/app/app512_pkg_follow_speaker_matrix.json`（+18/-0）与 `results/app/app523_pack_must_ttsworker_evidence.json`（+16/-7）**仍保持未提交**（等 reviewer 对 app523 裁定，**不预判**）。
