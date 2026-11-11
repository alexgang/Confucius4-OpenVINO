#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_write_status178.py —— 写 STATUS §178（活文档追加 + 归档件落盘）。

🔴 定点写入纪律：
  ① 活文档**只追加** `## §178 …` 章节（旧章节正文一字不改）；
  ② 为腾出体积（≤40 000 B／≤300 行），把 **§175 的活文档块索引化**
     （正文逐字已全在 write-once 归档件 `sec175` 里 ⇒ 归档件**逐字节不动**）；
  ③ 头部**只改 4 行**（last_ack／更新时间／当前任务／阻塞）；
  ④ `status/app/CORRECTIONS_APP.md` **只读，绝对不改**。
写前自检不通过 ⇒ **源文件零改动**（不落盘任何东西）。
"""
from __future__ import annotations

import datetime
import hashlib
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec178_20261111.md')

LIMIT_BYTES = 40000
LIMIT_LINES = 300
NOW = '2026-11-11 18:55:00'   # Get-Date 实测值

# ── §178 正文（归档件全文；活文档只放指针 + 速查）─────────────────────────
ARCHIVE_BODY = """# STATUS_APP §178（归档件 · write-once）

> 🔴 **归档件 = write-once**：本文件落盘后**逐字节不再改**；活文档 `status/app/STATUS_APP.md`
> 只保留 ≤3 行索引（APP-052 ④）。任何更正都写进**新章节**，不改本文件。

## §178 巡检（last_ack=APP-100，2026-11-11 18:55:00）｜**无新 reviewer 纠偏**（100 条／最大 APP-100，SHA `219ef841…`／308 340 B／mtime 11-11 10:38:52，**开工＝收尾逐字一致 ⇒ SHA 零改动**）；查出并修掉 **6 处 git 半交付**（STATUS 引用的归档件／证据产物**在磁盘上却从没进过 git**）＋ 新增「**git 半交付**」判据（177 行／**0 FAIL**＋反证 **3/3**）｜**本条需等 reviewer 复核**

---

### 一、本轮基线（磁盘实测，非沿用旧结论）

| 项 | 实测值 |
|---|---|
| `status/app/CORRECTIONS_APP.md` | SHA256 `219ef841fc2c11a56fe8117774633c86d4ef8110e1e089b27e5d5608de9ce199`／**308 340 B**／mtime **2026-11-11 10:38:52**／`## APP-xxx` **100 条**／最大 **APP-100** |
| `status/app/STATUS_APP.md` 头部 | `last_ack: APP-100`（**本轮无编号更大的新条目 ⇒ 无新纠偏需执行**） |
| 租约 | 本轮 token `26c4e830`；`acquire` 时命中 **TAKEOVER**（上一会话 token `3face6f5` 死于 11-11 17:29，note=`收尾复核`，`live_pids=[8256,33704,34300]`）⇒ 按断点续做，未从头重做 |
| 上一会话遗留 PIDs | `OpenProcess` err=**87**（PID 不存在）⇒ **三个全死**（判定用 `ctypes.WinDLL('kernel32', use_last_error=True)`，`GetExitCodeProcess` ⇒ 259 才是活） |
| 设备占用 | **全程未占设备**（纯 CPU 静态 + git 操作）⇒ 未创建 `MACHINE_LOCK`；`MACHINE_LOCK` 全程 NOT_PRESENT |
| 其它通道 | `shared/NOTICE*` 最新仍 **11-05**；agent-mail 工具回 **`not_bound`**（面板显示 connected 但实际未开通）；`conversation_search` 命中 **0**；git `origin/main..main=0` 且 `main..origin/main=0`；`claude-clone` 相对 main **无新提交** ⇒ **无遗漏指令** |

🔴 **上一会话（`3face6f5`）的交接点**：它已完成 §177（APP-100：`2f0f597` ＋ 已 push，ahead=0/behind=0）
⇒ **§177 的结论全部成立、本轮未推翻任何结论**；它死在「**收尾复核**」中途，
**留下 3 处未收尾的 git 半交付**（见第三节）⇒ 本轮从该断点继续。

---

### 二、🔴 根因：§173 的「归档指针可核对性」判据**查不出 git 半交付**

`_app429_status_pointer_audit.py`（§173 新增）只查两件事：
**① 归档件在磁盘上在不在 ② SHA256 对不对** ⇒ 报「**30 OK / 0 FAIL**」。

🔴 **但它查不出「文件在磁盘上、却从没进过 git」** ⇒ **典型的「PASS ≠ 正确」**
（弱标记恒真：把判据的输入换成「磁盘上存在但未入库」，它照样 PASS）。

**实测**：§177 的指针行引用 `status/archive/STATUS_APP_sec176_20261111.md`（SHA `7c43b365…`），
该文件**在磁盘上**、**SHA 完全对得上** ⇒ §173 的判据 PASS；
但它**从未出现在任何 commit 里**（`git log --all -- <path>` 为空）⇒
**换一个 clone 的人，STATUS 里这条指针直接断链**。

⇒ 本轮新增第 3 个维度：**`git_tracked`（已跟踪）＋ `git_committed`（已提交到 HEAD 树）**。
🔴 **查「已提交」而不是「已暂存」**——项目铁律「**「包里对」≠「已交付」**」
⇒ `git add` 之后（只在索引里）**不算交付** ⇒ 判据查 `git ls-tree -r HEAD`。

---

### 三、🔴 本轮查出并修掉的 **6 处 git 半交付**（**全部只补交、未改内容**）

| # | 路径 | 字节 | 被谁引用 | 处置 |
|---|---|---|---|---|
| 1 | `status/archive/STATUS_APP_sec159_20261109.md` | 11 156 | 活文档 §159 指针行（SHA `da8241c0…`） | 补交（commit `14531d0`） |
| 2 | `status/archive/STATUS_APP_sec176_20261111.md` | 13 851 | 活文档 §177 指针行（SHA `7c43b365…`） | 补交（commit `14531d0`） |
| 3 | `results/app/app326_app097_lang_out/mt.json` | 122 674 | 归档件 `sec169`／`recent_updates` | 补交（commit `fe6f1bc`） |
| 4 | `results/app/app326_app097_lang_out/tts.json` | 214 657 | 归档件 `sec172`／`sec174`（`_SEC_PER_CHAR` 回填的**数据源**） | 补交（commit `fe6f1bc`） |
| 5 | `results/app/app372_app091_subtitle_shot/subtitle_layout.json` | 386 | 归档件 `sec171`（§171 GUI 布局证据） | 补交（commit `fe6f1bc`） |
| 6 | `results/app/app458_app100_device.json` ＋ 目录内 8 份非忽略产物 | 5 991 ＋ ~440 K | 归档件 `sec176` §八（§176 的 canonical 片段两臂设备作业） | 补交（commit `fe6f1bc`） |

🔴 **为什么 #4 特别要紧**：`results/app/app326_app097_lang_out/tts.json` 是
**APP-097 §2-4「`_SEC_PER_CHAR` 实测校准」回填的唯一数据源**（§172 明写「复算不手抄」）
⇒ 它没进 git ⇒ **§172 的回填结论无法被第三方复算**（数字成立，但**证据链断**）。

**未补交的部分（有意为之，如实登记）**：
- `results/app/app458_app100_device/*.log`（2 份，285 186 B）与 `*.wav`（20 545 964 B）
  ⇒ 被 `.gitignore`（`*.log` / `*.wav`）排除 ⇒ **有意不入库**，判据记为 `OK_GITIGNORED`；
- `results/app/app437_app099_device/gpu_control_asr_npu.log`、`results/app/_app458_run.log`
  ⇒ 同上（`OK_GITIGNORED`）；
- `test_audio/clip_10min_0_600.wav`（19 200 044 B）⇒ `test_audio/` 整目录被 gitignore（**§176 已写明**「**gitignored**，与本仓库其它 wav 一致」）
  ⇒ 其 SHA/字节由 §176 归档件与 `app456` 判据（`file_sha256` 字段）承载；
- `status/archive/STATUS_APP_sec160_20261109.md` ⇒ 与已入库的 `sec160_20261110.md` **逐字节相同**
  （同 SHA `82c35e22…`）⇒ 是改名时留下的**孤儿重复件**，无任何引用 ⇒ **未补交、未删**（留档说明）。

---

### 四、新判据：`results/app/_app468_status_git_halfdelivery.py`（**只读**）

**判据要回答的问题**：活文档（及它引用的归档件）里引用的每个产物，
读者**能不能在 clone 之后**把它取回来核对？

**三个维度**：① 磁盘上存在 ② **已进 git（跟踪 ＋ 已提交到 HEAD 树）** ③ 字节数/SHA256 对得上。

**四种可接受形态**（前 3 种沿用 §173；**第 4 种是本轮新发现的**）：

| 形态 | 含义 | 命中者 |
|---|---|---|
| `raw` | 磁盘字节原样 | 多数证据文件 |
| `rstrip` | 去掉尾部换行 | §169 §170 |
| `body` | 归档件自带 `#` 抬头时，正文块（`## §…` 起） | §162 |
| **`lf` / `crlf`** | **互推行尾** | **§172 的 6 288 B、§177 的 2 138 B** |

🔴🔴 **第 4 种形态的发现过程（本轮最值得记的一条）**：
本仓库 `core.autocrlf=true` 且**无 `.gitattributes`** ⇒ **git 存 LF、工作区是 CRLF**
⇒ 旧章节引用产物时算的是**工作区 CRLF 字节** ⇒ 拿 git 里的 LF 字节去比 ⇒ **3 个假 FAIL**
（`assert_sec_per_char_calibrated.json` 6 288→5 992 B／`_app427_app109_regression.json` 6 079→5 798 B／
`app465_late_drop_ledger.json` 2 138→2 072 B，**差值恰好等于行数** ⇒ 反推确认）。
⇒ 🔴 **教训：引用里的字节数必须先确认它指的是「LF 存储」还是「CRLF 工作区」**，
否则会把「正确的引用」判成缺陷（**假 FAIL 比漏检更费时间**）。

**反证组（判据必须有鉴别力，不能恒真）**：

| 反证 | 做法 | 结果 |
|---|---|---|
| **A** | 把一个归档件从 `git ls-files` 名单剔除 | `OK → FAIL`（`NOT_GIT_TRACKED`）⇒ **触发** |
| **B** | 篡改一个归档件 1 字节（临时副本，不动原文件） | 声明的 SHA **失配** ⇒ **触发** |
| **C（非空自证）** | 用 `git ls-tree <修复前的 ref>` **重建**修复前的仓库状态再判一次 | 修复前抓到 **6 处**（7 条路径，含目录型）、修复后 **0 处** ⇒ **触发** |

🔴 **反证 C 的实现要点**：**不用手工保存的快照**（快照会随判据演进而失真 ⇒ **假自证**），
而是**从 git 历史重建**（`APP468_PREFIX_REF=<ref>` 环境变量）⇒ 对照永远可比。

**判据结果**：`results/app/app468_status_git_halfdelivery.json`
⇒ **177 行／OK 173／FAIL 0／MISSING 0／OK_GITIGNORED 3／KNOWN_ERRATA 1／无 SHA 声明 143／反证 3/3 全触发 ⇒ PASS**。

**已登记但**不判 FAIL**的项**（各 1 条，只记不报）：
- `results/app/_app429_self_ref_clone_gate.py` ⇒ **§175 已登记的笔误**（真名 `_app432_self_ref_clone_gate.py`），
  归档件 write-once 不可回改 ⇒ 不重复报警；
- 143 条「引用未声明 SHA」⇒ 按 §173 教训，**「没写 SHA」是信息、不是缺陷**
  ⇒ 但它们**仍查 git 半交付**（这 6 处里就有 4 处属此类）。

---

### 五、本轮自踩的 5 个坑（**都是真跑暴露，非静态推断**）

1. **判据自身有 3 处「假 FAIL」**（初版）：
   ① 只比**整文件长度**⇒ §162 写「5 052 B」指的是 **body 块**（整文件 5 347 B）⇒ 假 FAIL
   ⇒ 改成「命中形态的形态长度」；
   ② **SHA 以省略号截断**（`7c43b365e3f958a9…`，§177 指针行）⇒ 正则要求反引号紧邻 ⇒ **漏检**（假阴性）
   ⇒ 放宽为「反引号内允许省略号」；
   ③ **字节数须跟形态走**，而 §169/§170 写的是**整文件长度**（`rstrip` 形态只差 1 B）
   ⇒ 改成「命中任一形态的长度即算对」。
2. **CRLF 形态漏了**（见第四节）⇒ **3 个假 FAIL**；根因 = `core.autocrlf=true` 且无 `.gitattributes`。
3. **裸文件名被当路径**（`` `tts_engine.py` `` 只是正文提及）⇒ 假 MISSING ⇒ 改为「只认含 `/` 的仓库相对路径」。
4. **目录型引用漏检**（§176 引的是 `results/app/app458_app100_device/` **目录**，不是文件）
   ⇒ 补「查该目录下**非 gitignore** 文件是否入库」。
5. **反证 C 一度用「手工快照」**⇒ 快照只含 2 处（判据演进后失真）⇒ 假自证风险
   ⇒ 改成**从 git 历史重建**（`APP468_PREFIX_REF`）⇒ 修复前稳定抓到 6 处。

---

### 六、既有闸门复跑（**纯 CPU 静态，未占设备**）

| 闸门 | 结果 |
|---|---|
| `assert_sec_per_char_calibrated.py` | **27/27 PASS**（含反证 3/3） |
| `app109_lang_key_guard.py` | **34/34 PASS** |
| `assert_window_same_source.py`（对 v2.4） | **PASS**（含 2 条负控） |
| `assert_pkg_clean.py`（对 v2.4） | **0 违规** |
| `app456_app100_segment_gate.py` | **26/26 PASS**（A 9／B 7／C 4／反证 6/6 全触发） |
| `app465_late_drop_ledger.py` | **8/8 PASS**（REAL 4/4 ＋ 反证 4/4 全触发） |
| `_app429_status_pointer_audit.py` | **30 OK／0 FAIL／0 头部矛盾／反证 3/3** |
| `_app468_status_git_halfdelivery.py`（新） | **177 行／0 FAIL／反证 3/3 ⇒ PASS** |

🔴 复跑产生的 evidence JSON **仅时间戳变** ⇒ 已用 `git cat-file blob HEAD:<path>` **逐字节还原**
（**不用 `git checkout --`**——`core.autocrlf=true` 下它会把 LF 落成 CRLF，见 §173 教训）⇒ **不留噪声 diff**。

---

### 七、⏳ 待 reviewer 复核（本条）

1. **§174 的 self_ref 克隆闸门** ＋ **`assert_*.py` 排除规则**（上一轮，仍在等）
2. **§175 的 rc7 六臂冒烟 ＋ MANIFEST 84/84**（仍在等）
3. **§177 的 APP-100 canonical 片段口径 ＋ 两臂都自然退出（PASS）** ＋ `late_drop` 缺陷修复（仍在等）
4. **本轮**：APP-100 已是 `last_ack` ⇒ **无新纠偏需执行**；
   **6 处 git 半交付已补交**（只补交、未改内容）＋ **新增「git 半交付」判据**（含 CRLF 形态这个新发现）
5. **倍率地板** 与 **`tts_late_drop_sec`**：用户 11-11 定「下次再定」⇒ 仍未裁定
6. **GUI 布局修复**仍未同步客户包（v2.5 未打包）
7. **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972）＋ **§3.6 切段开销不可测** ⇒ 仍需 reviewer 裁定
8. **§4.6(a)(b) 阈值四臂** 暂缓（用户决定）＋ **`xv_reg_*` 阻塞**
"""

# ── 活文档 §178 块（≤3 行索引 + 速查）────────────────────────────────────
LIVE_SECTION = """
## §178 巡检（last_ack=APP-100，2026-11-11 18:55:00）｜**无新 reviewer 纠偏**；查出并修掉 **6 处 git 半交付**（STATUS 引用的归档件／证据产物**在磁盘上却从没进过 git**）＋ 新增「**git 半交付**」判据（177 行／**0 FAIL**＋反证 **3/3**）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec178_20261111.md`（__ARCH_B__ B／SHA256 `__ARCH_SHA__`）｜**归档件逐字节未动**（write-once）｜**上一会话（token `3face6f5`）死于「收尾复核」中途** ⇒ 本轮从其断点续做，**未推翻任何 §177 结论**。
> 🔴 **速查①根因**：§173 的「归档指针可核对性」判据只查**磁盘存在 + SHA** ⇒ **查不出 git 半交付**（它报「30 OK／0 FAIL」，而实测 **6 处引用在磁盘上却从未进过 git** ⇒ 换 clone 即断链）⇒ 新判据加第 3 维度：**已跟踪 ＋ 已提交到 HEAD 树**（查 `git ls-tree HEAD`，不查暂存区 ⇒ 铁律「「包里对」≠「已交付」」）。
> 🔴 **速查②已修 6 处半交付**（只补交、未改内容）：`sec159`（11 156 B）／`sec176`（13 851 B）／`app326_app097_lang_out/mt.json`（122 674 B）／`app326_app097_lang_out/tts.json`（214 657 B，**§172 `_SEC_PER_CHAR` 回填的唯一数据源**）／`app372…/subtitle_layout.json`（386 B）／`app458_app100_device.json` ＋ 8 份产物 ⇒ git `14531d0` ＋ `fe6f1bc`。
> 🔴 **速查③新发现第 4 种形态 `lf`/`crlf`**：本仓库 `core.autocrlf=true` 且**无 `.gitattributes`** ⇒ git 存 LF、工作区 CRLF ⇒ 旧章节引用算的是**工作区 CRLF 字节**（§172 的 6 288 B、§177 的 2 138 B，**差值恰等于行数**）⇒ 拿 LF 比 ⇒ **3 个假 FAIL** ⇒ 🔴 **教训：引用里的字节数须先确认指的是 LF 还是 CRLF**（**假 FAIL 比漏检更费时间**）。
> 🔴 **速查④判据** `results/app/_app468_status_git_halfdelivery.py`（只读）⇒ **177 行／OK 173／FAIL 0／MISSING 0／反证 3/3 全触发 ⇒ PASS**；反证 C 用 `git ls-tree <修复前 ref>` **从历史重建**修复前状态（抓到 6 处）⇒ **不用手工快照**（快照会随判据演进失真 ⇒ 假自证）。
> 🔴 **证据**：`results/app/app468_status_git_halfdelivery.json`（本轮判据产物）＋`results/app/_app468_status_git_halfdelivery.py`（判据脚本）＋`status/archive/STATUS_APP_sec178_20261111.md`（§178 正文全文）｜**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未改任何默认值或产品判据／未占设备／未持锁**｜**纠偏文件全程只读**（开工＝收尾 SHA `219ef841…`／308 340 B／100 条 ⇒ **SHA 零改动**）。
"""

HEADER_OLD = {
    'last_ack': 'last_ack: APP-100',
    'ts': '更新时间: 2026-11-11 17:28:39',
}

HEADER_NEW = {
    'last_ack': 'last_ack: APP-100',
    'ts': '更新时间: ' + NOW,
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    corr_before = open(CORR, 'rb').read()
    orig = open(STATUS, 'rb').read()
    text = orig.decode('utf-8')

    # ── ① 归档件先落盘（正文全文）────────────────────────────────────────
    arch_bytes = ARCHIVE_BODY.encode('utf-8')
    arch_sha = sha(arch_bytes)
    if os.path.exists(ARCH):
        print('ABORT: 归档件已存在（write-once）')
        return 1
    live = LIVE_SECTION.replace('__ARCH_B__', '{:,}'.format(len(arch_bytes)).replace(',', ' ')) \
                        .replace('__ARCH_SHA__', arch_sha)

    # ── ② §175 活文档块索引化（腾体积；正文逐字已在 write-once 归档件里）──
    m175 = re.search(r'(?m)^## §175 .*?(?=^## |\Z)', text, re.S)
    if not m175:
        print('ABORT: 找不到 §175 块')
        return 1
    old175 = m175.group(0)
    a175 = open(os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec175_20261111.md'),
                encoding='utf-8').read()
    # 归档件必须含 §175 的全部关键事实，否则不许压缩
    need = ['六臂', '冒烟', '84/84', 'PARTIAL', 'app432', '594.986', 'app437',
            'timing_valid', 'rc6', 'SEPARABLE', 'NOT_RUN_BLOCKED']
    missing = [k for k in need if k not in a175]
    if missing:
        print('ABORT: sec175 归档件缺事实，不压缩:', missing)
        return 1
    new175 = ('## §175 执行 APP-099（last_ack=APP-099）｜rc7 六臂冒烟重做 + A 机 GPU 同占复现 + '
              'dev 树修正 + MANIFEST｜**本条需等 reviewer 复核**\n\n'
              '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec175_20261111.md`'
              '（10 537 B／块 SHA256 `fd7f36a293539ffd460d6d613822192d0909c6a4acd12ded9067936322ce2622`）'
              '｜**归档件逐字节未动**（write-once）｜**正文全文（含第 4 节 8 项逐项结论、判据修正、'
              '§174 勘误、rc6 删除、锁/计时记录）逐字见该归档件**，活文档只留指针。\n')

    new_text = text.replace(old175, new175, 1)
    if new_text == text:
        print('ABORT: §175 替换未生效')
        return 1

    # ── ③ 头部只改 4 行 ─────────────────────────────────────────────────
    for old, new in ((HEADER_OLD['last_ack'], HEADER_NEW['last_ack']),
                     (HEADER_OLD['ts'], HEADER_NEW['ts'])):
        if old not in new_text:
            print('ABORT: 头部行未找到:', old)
            return 1
        new_text = new_text.replace(old, new, 1)

    old_task = re.search(r'(?m)^当前任务: .*$', new_text)
    if not old_task:
        print('ABORT: 找不到「当前任务」行')
        return 1
    new_task = ('当前任务: **巡检无新纠偏**（`last_ack=APP-100`；纠偏文件 **100 条 / 最大 APP-100**'
                '（SHA `219ef841…`／308 340 B）⇒ 无编号更大的新条目）｜**本轮修掉 6 处 git 半交付**'
                '（STATUS 引用的归档件／证据产物在磁盘上却从没进过 git ⇒ 换 clone 即断链）'
                '＋ **新增「git 半交付」判据**（177 行／0 FAIL／反证 3/3）｜**未打包 v2.5／未打 rc8／'
                '未通知用户／未调 MiniMax／未占设备**｜结果见 §178 归档件')
    new_text = new_text[:old_task.start()] + new_task + new_text[old_task.end():]

    old_blk = re.search(r'(?m)^阻塞 / 待用户决定: .*$', new_text)
    if not old_blk:
        print('ABORT: 找不到「阻塞」行')
        return 1
    new_blk = ('阻塞 / 待用户决定: 🔴 **本轮 6 处 git 半交付已补交**（只补交、未改内容）'
               '⇒ 换 clone 的读者不再断链｜🔴 **`late_drop` 修复未进任何客户包**（只改 dev 树）'
               '⇒ APP-055 须打新版本号；且 MiniMVP 按用户决定**暂不打包** ⇒ **等 reviewer 裁定何时随 '
               'v2.5 / rc8 出**｜🔴 **该缺陷正落在 `tts_late_drop_sec` 阈值上**（用户 11-11 定「下次再定」）'
               '⇒ 修好后影响面会变｜🔴 **GUI 布局修复仍未同步客户包**（v2.5 未打包）⇒ **请 reviewer 裁定**：'
               '立刻修还是随 v2.5 一起出｜🔴 **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972）'
               '⇒ 未自行换判据｜🔴 **§3.6 切段开销不可测**（质心恒 1）⇒ 需 reviewer 裁定｜'
               '**倍率地板** 与 **`tts_late_drop_sec`** 仍未裁定｜🔴 **新发现：引用字节数须区分 LF/CRLF**'
               '（`core.autocrlf=true` 且无 `.gitattributes`）⇒ 已加进判据')
    new_text = new_text[:old_blk.start()] + new_blk + new_text[old_blk.end():]

    # ── ④ 追加 §178 章节 ────────────────────────────────────────────────
    new_text = new_text.rstrip('\n') + '\n' + live

    # ── 写前自检（不过 ⇒ 源文件零改动）──────────────────────────────────
    nb = new_text.encode('utf-8')
    nl = nb.count(b'\n') + 1
    checks = [
        ('bytes<=40000', len(nb) <= LIMIT_BYTES, '%d' % len(nb)),
        ('lines<=300', nl <= LIMIT_LINES, '%d' % nl),
        ('no CRLF', nb.count(b'\r\n') == 0, str(nb.count(b'\r\n'))),
        ('old 21 sections kept', len(re.findall(r'(?m)^## §', new_text)) >= 21,
         str(len(re.findall(r'(?m)^## §', new_text)))),
        ('§178 present', '## §178 ' in new_text, ''),
        ('last_ack=APP-100', 'last_ack: APP-100' in new_text, ''),
        ('ts updated', ('更新时间: ' + NOW) in new_text, ''),
        ('CORR untouched', sha(open(CORR, 'rb').read()) == sha(corr_before), ''),
        ('§175 pointer kept', 'STATUS_APP_sec175_20261111.md' in new_text, ''),
        ('sections after 175 intact',
         new_text.count('## §175 ') == 1 and new_text.count('## §177 ') == 1, ''),
    ]
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print('  %-26s %s %s' % (name, 'OK' if ok else 'FAIL', detail))
    if bad:
        print('ABORT: 写前自检未过 ⇒ 源文件零改动')
        return 1

    # ── 落盘 ────────────────────────────────────────────────────────────
    with io.open(ARCH, 'wb') as f:
        f.write(arch_bytes)
    with io.open(STATUS, 'wb') as f:
        f.write(nb)
    print('WROTE archive: %s (%d B, sha %s)' % (ARCH, len(arch_bytes), arch_sha))
    print('WROTE status  : %s (%d B, %d lines)' % (STATUS, len(nb), nl))
    return 0


if __name__ == '__main__':
    sys.exit(main())
