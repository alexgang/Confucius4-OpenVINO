# STATUS_APP §196 整块逐字归档（2026-11-13）

归档时间：2026-11-13 22:48:21
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §197 出陠。
正文一字未删（标题行仍留在活文档）。

§196 正文块 SHA256（含标题行）：ead1629fca3f6d3fd484fca3e1728df8b132d3f1c0181719ddc180bbd899841a（3790 B）

---- 以下为 §196 原文，逐字 ----
## §196 Special MVP **目标机拷贝：被凭据挡住**（目标 `192.168.2.194` = `laptop-vqsjm79a`）｜**包已就绪，待一条可用认证**

> **① 现状**：Special MVP 已出包（§195），**zip 已算好校验值**：`shared\specialmvp\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip` = **14,244,490,059 B**／SHA256 **`72d2727ad73ff6b0cf0aa8a39c449047f69aa8aedbf41ece83cadd0c5d3fa5a8`**（证据 `results/app/app544_specialmvp_zip_sha256.json`）。用户 2026-11-13 要求「直接拷到目标机」⇒ 本轮做了**目标机可达性与认证全探测**。
> **② 目标机探测（只读、无破坏）**：ping **9 ms / 0% 丢包** ⇒ 机器在；**只开 22(SSH) 与 445(SMB)**（21/80/443/3389/5985/8080 等**全部关闭**）⇒ 没有 Web/FTP 等旁路；NetBIOS/名称解析不可用，ARP MAC `F4-A8-0D-2E-D3-73`（本地随机化 ⇒ 无厂商线索）。
> **③ 认证全部被拒（如实记录）**：**SSH**（服务端允许 `password`/`keyboard-interactive`/`publickey`）—— `user=test` 用 `Intel123` 走 password / interactive **均 "Authentication failed"**；`user=laptop-vqsjm79a\test` 被**直接重置连接**（Windows OpenSSH 对不存在用户的典型行为）；本机唯一私钥 `github_backup_ed25519`（注释 `alexgang@superclaw-bench-B`）对 4 个用户名做 publickey **全失败**。**SMB** —— `net use \\192.168.2.194\IPC$ /user:test|192.168.2.194\test|.\test` **均报 1326（用户名或密码不正确）**；匿名(guest)试 7 个共享名 **全部 1223**；`net view` **报 5（拒绝访问）**。**Tailscale**（ssh config 里的 `win-pc` = 100.70.84.17）—— 本机 tailscaled **服务在跑但状态 `NoState`**（连不上协调服务器）⇒ 该路不通。
> **④ 🔴 一个必须说清的风险（Windows 账号锁定）**：本轮对 `test` 账号累计发起过 **≥8 次**失败认证（SSH password 3 次 + interactive 1 次 + SMB 4 次）⇒ **Windows 默认策略（失败 5 次锁 5 分钟）很可能已把该账号锁住** ⇒ **我已停止一切重试**，避免把账号彻底锁死 ⇒ **请在目标机确认/解锁 `test` 账号**（或改用新账号），否则后续任何认证都会继续失败。
> **⑤ 已把交付做成「拿到就能走」**：① 包旁放了 `_DELIVERY_SPECIALMVP.txt`（SHA256、三后端落点、GPU 前置条件、自检命令、OPEN-1 说明）；② **桌面**放了 `SpecialMVP 1.0-sp1 - 拷贝说明.txt`（含公钥、一条命令的传输法、手工拷贝路径与核对方法）；③ **传输工具已备好** `results/app/_app545_transfer_to_target.py`（paramiko SFTP：**断点续传**＋进度＋**两端 SHA256 对账**＋传完在目标机自动跑 `nvidia-smi` 与包内 `--check`）—— **只要有一条可用认证，一条命令即可完成**：`python results\app\_app545_transfer_to_target.py --host 192.168.2.194 --user test --key C:\Users\Trekker-PTL\.ssh\github_backup_ed25519`。
> **⑥ 目标机 GPU 仍待确认**：本包按 **RTX 5050 / sm_120** 配 cu128 wheel ⇒ **目标机若无 NVIDIA 独显，CUDA TTS 在那台跑不了**（ASR/MT 两条 Intel 侧不受影响）⇒ 传输工具里已内置 `nvidia-smi` 预检 ⇒ **连上后第一件事就是验它**（不用你猜）。
> **⑦ 纪律**：**未改目标机任何东西**（全程只读探测）｜**未改本机已有包/zip**｜**未调 MiniMax**｜**未跑推理于 CPU**｜**未通知用户**（本节即说明）｜**未提交** `CORRECTIONS_APP.md`｜**未提交**其它模块未提交改动。
> **⑧ 本条需等用户/reviewer**：① 目标机的**可用认证**（装公钥／给可用账号密码／自行拷贝）；② 目标机**有没有 NVIDIA 显卡**（工具会自动验）；③ **OPEN-1**（长跑退出码 3221226505）仍待定位。
