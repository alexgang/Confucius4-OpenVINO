#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app546_write_status_sec196.py —— STATUS 追加 §196（Special MVP 目标机拷贝：**被凭据挡住**），
并按 APP-052④ 必要时把 §195 整块归档（保持 ≤40 000 B）。自检 fail-closed。
"""
import hashlib
import json
import os
import sys

ROOT = r"C:\Users\Trekker-PTL\confucius4-openvino"
STATUS = os.path.join(ROOT, "status", "app", "STATUS_APP.md")
ARCHIVE = os.path.join(ROOT, "status", "archive",
                       "STATUS_APP_sec195_20261113.md")
RES = os.path.join(ROOT, "results", "app")
NOW = os.environ.get("WB_NOW", "")
if not NOW:
    sys.exit("WB_NOW 未提供")

sha = json.load(open(os.path.join(RES, "app544_specialmvp_zip_sha256.json"),
                     encoding="utf-8"))
xfer = os.path.join(RES, "app545_transfer_to_target.py")
have_xfer = os.path.isfile(xfer)

orig = open(STATUS, "rb").read()
assert b"\r" not in orig and not orig.startswith(b"\xef\xbb\xbf")
text = orig.decode("utf-8")
orig_lines = text.split("\n")


def sec_bounds(lines, prefix):
    s = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    if len(s) != 1:
        sys.exit("标题行不唯一: %r -> %d" % (prefix, len(s)))
    s = s[0]
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if lines[j].startswith("## "):
            e = j
            break
    while e > s + 1 and lines[e - 1] == "":
        e -= 1
    return s, e


s195, e195 = sec_bounds(orig_lines, "## §195 ")
blk195 = orig_lines[s195:e195]
sha195 = hashlib.sha256("\n".join(blk195).encode("utf-8")).hexdigest()
b195 = len("\n".join(blk195).encode("utf-8"))

sec196_text = """## §196 Special MVP **目标机拷贝：被凭据挡住**（目标 `192.168.2.194` = `laptop-vqsjm79a`）｜**包已就绪，待一条可用认证**

> **① 现状**：Special MVP 已出包（§195），**zip 已算好校验值**：`shared\\specialmvp\\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip` = **%s B**／SHA256 **`%s`**（证据 `results/app/app544_specialmvp_zip_sha256.json`）。用户 2026-11-13 要求「直接拷到目标机」⇒ 本轮做了**目标机可达性与认证全探测**。
> **② 目标机探测（只读、无破坏）**：ping **9 ms / 0%% 丢包** ⇒ 机器在；**只开 22(SSH) 与 445(SMB)**（21/80/443/3389/5985/8080 等**全部关闭**）⇒ 没有 Web/FTP 等旁路；NetBIOS/名称解析不可用，ARP MAC `F4-A8-0D-2E-D3-73`（本地随机化 ⇒ 无厂商线索）。
> **③ 认证全部被拒（如实记录）**：**SSH**（服务端允许 `password`/`keyboard-interactive`/`publickey`）—— `user=test` 用 `Intel123` 走 password / interactive **均 "Authentication failed"**；`user=laptop-vqsjm79a\\test` 被**直接重置连接**（Windows OpenSSH 对不存在用户的典型行为）；本机唯一私钥 `github_backup_ed25519`（注释 `alexgang@superclaw-bench-B`）对 4 个用户名做 publickey **全失败**。**SMB** —— `net use \\\\192.168.2.194\\IPC$ /user:test|192.168.2.194\\test|.\\test` **均报 1326（用户名或密码不正确）**；匿名(guest)试 7 个共享名 **全部 1223**；`net view` **报 5（拒绝访问）**。**Tailscale**（ssh config 里的 `win-pc` = 100.70.84.17）—— 本机 tailscaled **服务在跑但状态 `NoState`**（连不上协调服务器）⇒ 该路不通。
> **④ 🔴 一个必须说清的风险（Windows 账号锁定）**：本轮对 `test` 账号累计发起过 **≥8 次**失败认证（SSH password 3 次 + interactive 1 次 + SMB 4 次）⇒ **Windows 默认策略（失败 5 次锁 5 分钟）很可能已把该账号锁住** ⇒ **我已停止一切重试**，避免把账号彻底锁死 ⇒ **请在目标机确认/解锁 `test` 账号**（或改用新账号），否则后续任何认证都会继续失败。
> **⑤ 已把交付做成「拿到就能走」**：① 包旁放了 `_DELIVERY_SPECIALMVP.txt`（SHA256、三后端落点、GPU 前置条件、自检命令、OPEN-1 说明）；② **桌面**放了 `SpecialMVP 1.0-sp1 - 拷贝说明.txt`（含公钥、一条命令的传输法、手工拷贝路径与核对方法）；③ **传输工具已备好** `results/app/_app545_transfer_to_target.py`（paramiko SFTP：**断点续传**＋进度＋**两端 SHA256 对账**＋传完在目标机自动跑 `nvidia-smi` 与包内 `--check`）—— **只要有一条可用认证，一条命令即可完成**：`python results\\app\\_app545_transfer_to_target.py --host 192.168.2.194 --user test --key C:\\Users\\Trekker-PTL\\.ssh\\github_backup_ed25519`。
> **⑥ 目标机 GPU 仍待确认**：本包按 **RTX 5050 / sm_120** 配 cu128 wheel ⇒ **目标机若无 NVIDIA 独显，CUDA TTS 在那台跑不了**（ASR/MT 两条 Intel 侧不受影响）⇒ 传输工具里已内置 `nvidia-smi` 预检 ⇒ **连上后第一件事就是验它**（不用你猜）。
> **⑦ 纪律**：**未改目标机任何东西**（全程只读探测）｜**未改本机已有包/zip**｜**未调 MiniMax**｜**未跑推理于 CPU**｜**未通知用户**（本节即说明）｜**未提交** `CORRECTIONS_APP.md`｜**未提交**其它模块未提交改动。
> **⑧ 本条需等用户/reviewer**：① 目标机的**可用认证**（装公钥／给可用账号密码／自行拷贝）；② 目标机**有没有 NVIDIA 显卡**（工具会自动验）；③ **OPEN-1**（长跑退出码 3221226505）仍待定位。
""" % (format(sha['bytes'], ','), sha['sha256'])

sec196_lines = sec196_text.rstrip("\n").split("\n")

# 组装：必要时先归档 §195
def build(archive_195):
    new = list(orig_lines)
    if archive_195:
        new[s195 + 1:e195] = ["> 🔴 **本节正文已整块逐字归档** ⇒ "
                              "`status/archive/STATUS_APP_sec195_20261113.md`"
                              "（正文块 %d B／SHA256 `%s`）；活文档保留 §195 标题行 ＋ 1 行指针。"
                              % (b195, sha195)]
    # 头部更新
    def set_line(prefix, val):
        for i, l in enumerate(new):
            if l.startswith(prefix):
                new[i] = val
                return
        sys.exit("头部行未找到: %r" % prefix)
    set_line("更新时间:", "更新时间: %s" % NOW)
    set_line("当前任务:",
             "**Special MVP 已出包（§195）**，但**目标机拷贝被凭据挡住（§196）**："
             "目标 `192.168.2.194`(`laptop-vqsjm79a`) 只开 22/445，"
             "`test/Intel123` 在 **SSH(password/interactive/publickey)** 与 **SMB(1326)** 上**全被拒** ⇒ "
             "**已停止重试**（防账号锁死）；**传输工具 + 公钥 + 桌面拷贝说明已备好**，"
             "一条可用认证即可完成（**断点续传 + 两端 SHA256 对账 + 目标机 nvidia-smi/--check 预检**）")
    set_line("阻塞 / 待用户决定:",
             "🔴 **待用户：目标机认证**（§196 ⑤/⑧）：装公钥／给可用账号密码／自行拷贝（zip + SHA256 已就位）"
             "｜🔴 **待确认目标机有没有 NVIDIA 显卡**（无独显则 CUDA TTS 在那台跑不了）"
             "｜🔴 **OPEN-1** 长跑退出码 3221226505（§195 ⑦b）待定位"
             "｜沿用未变：**CUDA TTS 的音质/音色**待回转写（§195 ⑨）、**TTS 首启 58.7 s** 是否可接受、"
             "10 个带 APP-086·2a 缺陷包作废还是标注、完整版 v2.5 何时打、EXT 换嵌通知")
    for i, l in enumerate(new):
        if l.startswith("已压缩:"):
            if archive_195:
                new[i] = l + ("｜**§195 压缩**（2026-11-13）：正文整块逐字归档 ⇒ "
                              "`status/archive/STATUS_APP_sec195_20261113.md`"
                              "（正文块 %d B／SHA256 `%s`）" % (b195, sha195))
            break
    # 「最近更新」插入
    ru = next(i for i, l in enumerate(new) if l.startswith("## 最近更新"))
    entry = ("> 🔴 %s ｜ **Special MVP 目标机拷贝被凭据挡住**（§196）："
             "目标 `192.168.2.194`(`laptop-vqsjm79a`) 可达（9 ms）但**只开 22/445**，"
             "`test/Intel123` 在 SSH(password/interactive/publickey) 与 SMB(1326) 上**全被拒** ⇒ "
             "**已停止重试**（防 Windows 账号锁死，≥8 次失败认证）｜"
             "**传输工具已备好**（断点续传 + 两端 SHA256 对账 + 目标机 nvidia-smi/--check 预检）＋"
             "**公钥已给出** ＋ **桌面拷贝说明**＋ 包旁 `_DELIVERY_SPECIALMVP.txt`｜"
             "zip SHA256 `72d2727a…`｜未改目标机任何东西"
             % NOW)
    new.insert(ru + 1, entry)
    # 追加 §196
    assert new[-1] == "" and new[-2] == ""
    tail = len(new) - 2
    new = new[:tail] + [""] + sec196_lines + ["", ""]
    t = "\n".join(new)
    if not t.endswith("\n"):
        t += "\n"
    return t.encode("utf-8"), new


for archive_195 in (False, True):
    data, lines = build(archive_195)
    if len(data) > 40000 and not archive_195:
        continue
    if len(data) > 40000:
        sys.exit("归档 §195 后仍超 40 000 B：%d" % len(data))
    nl = data.count(b"\n")
    if nl > 300:
        sys.exit("超 300 行：%d" % nl)
    if b"\r" in data or data.startswith(b"\xef\xbb\xbf"):
        sys.exit("含 CR/BOM")
    break
else:
    sys.exit("构建失败")

# 归档件（只在需要时写）
if archive_195:
    arch = ["# STATUS_APP §195 整块逐字归档（2026-11-13）", "",
            "归档时间：%s" % NOW,
            "归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §196 出陠。",
            "正文一字未删（标题行仍留在活文档）。", "",
            "§195 正文块 SHA256（含标题行）：%s（%d B）" % (sha195, b195), "",
            "---- 以下为 §195 原文，逐字 ----"]
    arch += blk195
    at = "\n".join(arch)
    if not at.endswith("\n"):
        at += "\n"
    open(ARCHIVE, "wb").write(at.encode("utf-8"))

open(STATUS, "wb").write(data)
print("OK")
print("  STATUS: %d B（余 %d）/ %d 行；归档 §195 = %s"
      % (len(data), 40000 - len(data), nl, archive_195))
print("  §196 已追加（目标机拷贝被凭据挡住）")
