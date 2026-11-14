# STATUS_APP 「最近更新」较旧 3 条整块逐字归档（2026-11-14）

归档时间：2026-11-14 17:17:05
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §202 出空。
正文一字未删（原文逐字保留在本文件）。

正文块 SHA256：b2dc9eda06cc8a2d3d9c53f43d3eebdcf618322f65f18da1c5e9e6f7620b6324（1881 B）

---- 以下为「最近更新」较旧 3 条原文，逐字 ----
> 🔴 2026-11-13 22:48:21 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）＋ 目标机拷贝已实际完成**：用户补的凭据 → SSH 认证通过；🔴 **大文件弃用 SFTP（0.3 MB/s）改走 HTTP+curl（73.0 MB/s / 3 min 06 s）**；zip **14 244 490 059 B** 落到目标机 `C:\Users\63446\Desktop\`（**大小逐字节相等**）；🔴 **两端 SHA256 对账被目标机 AV 独占锁挡住**（ERROR_SHARING_VIOLATION）⇒ 只报大小一致；🔴 **目标机 C: 仅 1.55 GiB 可用 ⇒ 删 zip 才能解压运行**（未删，等授权）；🔴 **目标机 RTX 4050 sm_89 vs 包基线 sm_120** ⇒ 须实机 `--check`；未打包/未改客户包/未改产品代码/未调 MiniMax
> 🔴 2026-11-13 22:21:35 ｜ **Special MVP 目标机拷贝被凭据挡住**（§196）：目标 `192.168.2.194`(`laptop-vqsjm79a`) 可达（9 ms）但**只开 22/445**，`test/Intel123` 在 SSH(password/interactive/publickey) 与 SMB(1326) 上**全被拒** ⇒ **已停止重试**（防 Windows 账号锁死，≥8 次失败认证）｜**传输工具已备好**（断点续传 + 两端 SHA256 对账 + 目标机 nvidia-smi/--check 预检）＋**公钥已给出** ＋ **桌面拷贝说明**＋ 包旁 `_DELIVERY_SPECIALMVP.txt`｜zip SHA256 `72d2727a…`｜未改目标机任何东西
> 🔴 2026-11-13 21:27:28 ｜ **Special MVP 出包**（用户 2026-11-13 决定）：**TTS 仅用 CUDA**（NV5050 环境**随包**）／**ASR 用 iGPU**／**MT 用 NPU**｜包 `Confucius4_LiveCaption_SpecialMVP_v1.0-sp1`（**41,374 文件 / 13.25 GiB**）｜包上验收 **PASS（13/13）**｜整链实测：ASR RTF **0.522**（集显）／翻译落点 **NPU**（中位 898.8 ms）／TTS 由 **?** 合成（加载 ? s、预热 ? s）｜**新包形态** `profile=specialmvp`（MiniMVP/完整版行为**一字不变**，已回归）｜未改旧包、未调 MiniMax、未通知用户
