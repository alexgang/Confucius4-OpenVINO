#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-050 收尾：把 git commit/push 结果回写进 `status/app/STATUS_APP.md`，并更正
§115 里一处**事实错误**（「v1.13 zip 仍不存在」⇒ 实际存在，但**不含**本轮代码）。

🔴 **纪律**：
  - `status/app/STATUS_APP.md` **bytes 级定点写入**：只动**头部区**（第一个 `### §` 之前）
    的指定字段；**只追加**新章节 `### §116`，**绝不改旧章节正文**。
  - `status/app/CORRECTIONS_APP.md` **只读**，写后断言字节数 + SHA256 均未变。
  - 自指大小「本文件 N B / M 行」必须 == 实际 ⇒ **两遍法**（先算 → 回填 → 再算）。
  - 全文 ≤ 40 KB / ≤ 300 行（APP-049 限额）。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

ROOT = r"C:\Users\Trekker-PTL\confucius4-openvino"
STATUS = os.path.join(ROOT, "status", "app", "STATUS_APP.md")
CORR = os.path.join(ROOT, "status", "app", "CORRECTIONS_APP.md")

MAX_B = 40 * 1024
MAX_LINES = 300


def read_bytes(p: str) -> bytes:
    with open(p, "rb") as f:
        return f.read()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    corr_before = read_bytes(CORR)
    before = read_bytes(STATUS)
    text = before.decode("utf-8")

    # ---- 旧章节快照（写后要逐字复核「旧章节正文未被改动」）----
    parts = re.split(r"(?m)^(### §\d+.*)$", text)
    old_secs = {}
    for i in range(1, len(parts), 2):
        old_secs[parts[i]] = parts[i + 1]

    head, sep, tail = text.partition("\n### §")
    assert sep, "未找到章节起点"
    head = head + sep + tail  # 还原全文，仅为取 header 边界用

    # 头部区 = 第一个 "### §" 之前
    m = re.search(r"(?m)^### §", text)
    assert m, "未找到 ### §"
    head_region = text[: m.start()]
    body_region = text[m.start():]

    # =====================================================================
    # 1) 头部区定点替换（每个 old 必须**唯一命中**）
    # =====================================================================
    new_head = head_region

    def rep(h: str, old: str, new: str) -> str:
        cnt = h.count(old)
        assert cnt == 1, "唯一命中断言失败: %r 命中 %d 次" % (old[:60], cnt)
        return h.replace(old, new)

    # 1a) 更新时间（Get-Date 实测值）
    new_head = rep(
        new_head,
        "更新时间: 2026-10-31 10:32",
        "更新时间: 2026-10-31 10:37",
    )

    # 1b) 阻塞①：更正「v1.13 未打包」⇒ zip 存在但不含本轮代码
    new_head = rep(
        new_head,
        "① 🔴 **v1.13 未打包**（用户 11:30 指令：未经通知不主动打包）⇒ **本条改动（APP-050 那一行日志）客户机上还看不到**；",
        "① 🔴 **v1.13 zip 已存在但不含本轮代码**（`Confucius4_LiveCaption_v1.13.zip` = 11 233 343 245 B / mtime **2026-10-31 09:17:06**，**早于**本轮代码写入 10:30）⇒ **本条改动（APP-050 那一行日志）客户机上仍然看不到**（结论不变，**理由已更正**，见 §116）；**本轮未重新打包**（用户 11:30 指令：未经通知不主动打包）⇒ **需用户通知后重打包才闭合**；",
    )

    # 1c) 当前任务：追加 git 收尾
    new_head = rep(
        new_head,
        "；**本轮无新纠偏条目**（`last_ack=APP-050` = 最大编号）",
        "；**本轮无新纠偏条目**（`last_ack=APP-050` = 最大编号）；**git 收尾已完成**（commit `8f1a645` / 13 文件 / 已 push 到 `origin/main`，`6cc0054..8f1a645`，ahead/behind = 0/0）；**本轮共 2 处事实更正**（① v1.13 zip **确实存在**但**不含**本轮代码 ② 头部表格「客户包目录 = v1.12」应更正为 **v1.13**）⇒ 详见 **§116**",
    )

    # =====================================================================
    # 2) 追加 §116
    # =====================================================================
    sec116 = """
### §116 ✅ **APP-050 git 收尾（commit / push）** ｜ 🔴 **顺带抓出并更正 §115 的一处事实错误：「v1.13 zip 仍不存在」—— zip 其实存在，只是不含本轮代码** ｜ **本条已完成** ｜ **本条需等 reviewer 复核（2 项）**

> 本节**只追加**，不改 §115 任何正文。§115 里被更正的那句，用下面的「撤回」条目显式撤回。

#### ① ✅ git 收尾（commit + push）

| 项 | 结果 |
|---|---|
| commit | **`8f1a645`** —— `feat(app): §115 —— APP-050 TTS 启动日志打印各组件 EXECUTION_DEVICES（修正 list() 逐字符拆分误读）` |
| 提交范围 | **13 个文件**：`live_caption/tts_engine.py`（改）、`live_caption/sync_c173_app050_to_pkg.py`（新）、`results/app/app174{a,b,c,d,e}_*`（8 个）、`results/app/app174_run_with_lock.py`、`status/app/STATUS_APP.md`（改）、`status/archive/STATUS_APP_sec109_114_upto_20261031.md`（新） |
| 变更规模 | 2 259 insertions / 158 deletions |
| push | **普通 push 成功**：`6cc0054..8f1a645  main -> main`（`git push origin main`）⇒ **未用 force push** |
| 分支 | **仅 `main`**（`git branch -a` = `main` + `remotes/origin/main`；无其它本地分支）⇒ 符合「仓库只保留 main 分支」 |
| 同步状态 | `git rev-list --left-right --count origin/main...main` = **0  0** ⇒ 本地与远端**完全一致** |
| 🔴 **未吞别的模块改动** | 工作区共有 **553 项** `git status --porcelain` 变更（ASR / MT / TTS / 根目录脚本等）⇒ **逐文件 `git add`**（**未用 `-A`**）⇒ 本次 commit **只含上表 13 个 App 侧文件** |
| 🔴 **`CORRECTIONS_APP.md` 未入库** | `git show --name-only --format="" HEAD` 后 `grep CORRECTIONS` ⇒ **空**；且工作区文件仍 **119 646 B / SHA256 `0e402635244db8ef62e28cd024263a6fded223ccfce072a0a0e1e415901884c4`**（**零改动**，reviewer 独占写入） |

#### ② 🔴 **入库前两道素材闸门（都 PASS）**

| 闸门 | 结果 |
|---|---|
| `check_internal_material.py --staged --repo . --verbose` | **命中 0 个内部素材 ⇒ PASS**（脚本自报） |
| `app007_cn_exact.json` **20 条精确中文引文**独立复核（不依赖闸门正则 ⇒ 防「闸门正则失效导致假通过」） | **命中 0**（对 13 个待提交文件全文扫描） |
| 归档逐字复核 | HEAD 版 STATUS 的 **§109~§114 共 6 个章节**正文 **逐字**存在于 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`（25 909 B）⇒ **无一缺失**（旧章节内容**一字未删**） |
| STATUS 自指大小 | 实测 **27 925 B / 178 行**；文内 `本文件 27925 B / 178 行` ⇒ **一致**（两遍法收敛 + 独立复核） |

#### ③ 🔴🔴 **撤回 §115 的一处事实错误：「v1.13 zip 仍不存在」**

- 🔴 **§115 原文（现撤回）**（两处：⑥ 与 ⑧）：
  > 「🔴 **本轮未打包**（用户 11:30 指令：未经通知不主动打包）⇒ **v1.13 zip 仍不存在** ⇒ 客户机上**看不到**本条改动（须等用户通知后打包）。」
  > 「🔴 **未打包**（用户 11:30 指令）⇒ v1.13 zip 不存在 ⇒ **客户机上还看不到这一行**。」

- 🔴 **实测事实**（`Get-ChildItem` + `Get-Item`，2026-10-31 10:37 实测）：

  | 对象 | 大小 | mtime | 含义 |
  |---|---|---|---|
  | `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.13.zip` | **11 233 343 245 B** | **2026-10-31 09:17:06** | **zip 确实存在**（§115 说「不存在」⇒ **错**） |
  | `Confucius4_LiveCaption_v1.13\\app\\tts_engine.py`（包目录） | 85 233 B | **2026-10-31 10:30:10** | 本轮 APP-050 代码写入**包目录**的时刻 |
  | `confucius4-openvino\\live_caption\\tts_engine.py`（仓库） | 85 233 B | 2026-10-31 10:31:34 | 仓库副本 |

  ⇒ **zip 的 mtime（09:17:06）早于本轮代码写入包目录（10:30:10）** ⇒ **zip 不含本轮 APP-050 代码**。

- ✅ **结论不变，理由更正**：
  | | §115 的说法（现撤回） | §116 的更正 |
  |---|---|---|
  | zip 是否存在 | 「不存在」 | 🔴 **存在**（11 233 343 245 B / 09:17:06） |
  | 客户机能否看到本条改动 | 「看不到」 | ✅ **仍然看不到**（因为 zip 是**改动前**打的） |
  | 真正的原因 | 「未打包 ⇒ 不存在」 | 🔴 **zip 是 APP-050 改动之前生成的旧包**；本轮**遵守「不主动打包」指令未重打** ⇒ 需用户通知后重打包才闭合 |

- 🔴 **顺带更正头部「交付配置」表的一处过期值**（该表在正文区，按纪律**不改表**，在此记录）：「客户包目录 = `Confucius4_LiveCaption_v1.12`（**当前唯一**）」⇒ 磁盘实测**同时存在** `Confucius4_LiveCaption_v1.12` 与 `Confucius4_LiveCaption_v1.13`（**目录** mtime 2026-10-30 03:57）⇒ **当前最新包目录是 v1.13**，v1.12 目录已非「唯一」。**本轮未删除任何旧包目录 / 旧 zip**（删除属破坏性操作，需用户确认）。
- 🔴 **本轮仍为「未打包」状态**：**没有**运行 `pack_v13.py`，**没有**新 zip 产生（用户 2026-10-30 11:30 指令：未经通知不主动打包；且 `pack_v13.py` 启动即改源目录名，中止会白吃版本号）。

#### ④ 🔴 **本条需等 reviewer 复核（2 项）**

1. 🔴 **「v1.13 zip 已存在但不含本轮代码」这一更正是否接受**？（即：交付口径应以「zip 内容是否含本轮代码」为准，而不是以「zip 文件是否存在」为准 —— 后者曾导致 §115 写出错误事实。）
2. 🔴 **是否要现在重打包 v1.13**？（需要用户明确通知；本轮未打包。**建议在重打包前先跑打包前闸门** `results/app/app170_version_identity_gate.py`，避免 §113 修掉的「版本标识在打包时复发」问题再次发生。）

#### ⑤ 🔴 **未做 / 仍阻塞（本轮不变）**

- 🔴 **未重新打包** ⇒ 客户机上仍看不到 APP-050 那一行日志（**等用户通知**）。
- 🔴 **未测速 / 未做质量判定**（APP-050 明写「不用另外做测速」；质量判定交 reviewer）。
- 🔴 **APP-043 真机验收 / APP-045③（桌面快捷方式仍指向 v1.5）** 仍未做 ⇒ 见头部「阻塞 / 待用户决定」。
"""

    new_text = new_head + body_region.rstrip("\n") + "\n" + sec116

    # =====================================================================
    # 3) 自指大小：两遍法
    # =====================================================================
    def selfref(t: str) -> str:
        return re.sub(r"本文件 \d+ B / \d+ 行", "本文件 0 B / 0 行", t)

    def measure(t: str):
        b = t.encode("utf-8")
        return len(b), len(t.splitlines())

    t1 = selfref(new_text)
    b1, l1 = measure(t1)
    t2 = t1.replace("本文件 0 B / 0 行", "本文件 %d B / %d 行" % (b1, l1))
    b2, l2 = measure(t2)
    t3 = t2.replace("本文件 %d B / %d 行" % (b1, l1), "本文件 %d B / %d 行" % (b2, l2))
    b3, l3 = measure(t3)
    # 三遍必须收敛（若 b2->b3 数字变化则说明长度受数字位数影响，需再迭代一次）
    t4 = t3.replace("本文件 %d B / %d 行" % (b2, l2), "本文件 %d B / %d 行" % (b3, l3))
    b4, l4 = measure(t4)
    t5 = t4.replace("本文件 %d B / %d 行" % (b3, l3), "本文件 %d B / %d 行" % (b4, l4))
    b5, l5 = measure(t5)
    final = t5
    assert b5 == len(final.encode("utf-8")) and l5 == len(final.splitlines()), "自指大小未收敛"
    print("[pre] 自指大小两遍法收敛: %d B / %d 行" % (b5, l5))
    assert b5 <= MAX_B, "超过 40 KB 限额: %d" % b5
    assert l5 <= MAX_LINES, "超过 300 行限额: %d" % l5

    # =====================================================================
    # 4) 写盘 + 写后复核
    # =====================================================================
    with open(STATUS, "wb") as f:
        f.write(final.encode("utf-8"))

    after = read_bytes(STATUS)
    at = after.decode("utf-8")

    # 4a) 旧章节正文逐字未变（尾部空白归一化）
    nparts = re.split(r"(?m)^(### §\d+.*)$", at)
    new_secs = {}
    for i in range(1, len(nparts), 2):
        new_secs[nparts[i]] = nparts[i + 1]
    missing = []
    for k, v in old_secs.items():
        if k not in new_secs:
            missing.append(k[:40] + " (整节丢失)")
        elif new_secs[k].rstrip() != v.rstrip():
            missing.append(k[:40] + " (正文被改)")
    assert not missing, "旧章节被改动: %s" % missing
    print("[post] 旧章节 %d 个全部逐字保留 ✔" % len(old_secs))

    # 4b) 章节数 +1、最大编号 +1、幂等闸门仍可取最大编号
    old_max = max(int(re.search(r"§(\d+)", k).group(1)) for k in old_secs)
    new_max = max(int(re.search(r"§(\d+)", k).group(1)) for k in new_secs)
    assert new_max == old_max + 1, "最大章节编号未递增: %d -> %d" % (old_max, new_max)
    print("[post] 章节 %d -> %d ｜ 最大编号 §%d -> §%d" %
          (len(old_secs), len(new_secs), old_max, new_max))

    # 4c) 幂等闸门：`grep -oE '^## APP-[0-9]+' | tail -1` 形式仍能取最大编号
    ids = re.findall(r"(?m)^## APP-[0-9]+", at)
    print("[post] APP 编号条目 %d 个" % len(ids))

    # 4d) 行尾未被破坏（纯 LF，与原文件一致）
    assert b"\r\n" not in after, "行尾被破坏（出现 CRLF）"
    print("[post] 行尾 = LF ✔")

    # 4e) CORRECTIONS 零改动
    corr_after = read_bytes(CORR)
    assert corr_after == corr_before, "CORRECTIONS_APP.md 被改动！"
    print("[post] CORRECTIONS_APP.md 零改动 ✔ (%d B / SHA256 %s)" %
          (len(corr_after), sha(corr_after)[:16]))

    # 4f) 自指大小一致性（独立复核）
    got = re.search(r"本文件 (\d+) B / (\d+) 行", at)
    assert got, "自指字段丢失"
    assert int(got.group(1)) == len(after) and int(got.group(2)) == len(at.splitlines()), \
        "自指大小与实际不符: %s vs %d B / %d 行" % (
            got.group(0), len(after), len(at.splitlines()))
    print("[post] 自指大小: %d B / %d 行 ✔" % (len(after), len(at.splitlines())))

    print("[ok] 已写入 %s (%d B)" % (STATUS, len(after)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
