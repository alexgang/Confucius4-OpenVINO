#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-231：把本轮（接续上一会话）的可复用知识写进**项目记忆**。

## 为什么本脚本存在

上一会话（token `47796b43`）在 §230 做完、提交推送、发完信之后**死在写记忆
这一步**（它的 `results/app/_app133_write_memory.py` 存在但**从未运行**，
且那个脚本**漏了 MEMORY.md 的 9 700 字符上限校验**）。
⇒ 本轮（TAKEOVER 接续）**闭合这个遗留项**。

## 本轮写什么（三个文件，各有各的纪律）

| 文件 | 纪律 | 本轮内容 |
|---|---|---|
| `.workbuddy/memory/2026-11-24.md` | **append-only**（不回头改旧段） | 第 126 轮（本轮）巡检记录 |
| `.workbuddy/memory/MEMORY.md` | **≤ 9 700 字符**（注入预算） | 🔴**只加一行指针**（机器锁必须原子创建）＋ 顺带把 §十二 的**过期 `last_ack=APP-128` 修正为 APP-133** |
| `.workbuddy/memory/MEMORY_MODULES.md` | 追加新小节（模块细节） | APP-132 的**生产路径补漏**全过程 + 两个新判据坑 |

## 🔴 纪律（照抄自已验证的三件套）

- 🔴 **定点写入三件套**：① 备份（`%TEMP%/*.bak`）② 写前在**内存新文本**跑
  真不变量 ＋ **还原式复核**（改回须逐字节同）③ 临时文件 → `os.replace`
  ⇒ 写后**另起脚本**独立复核 ＋ `numstat`。
- 🔴 `open(p,'w')` 先截断 ⇒ 0 B ⇒ 一律走临时文件 + `os.replace`。
- 🔴 **`MEMORY.md` 的 9 700 字符上限必须断言**（上一轮脚本漏了 ⇒ 本轮补上）
  ⇒ 超限 ⇒ **零改动**（fail-closed）。
- 🔴 **`.workbuddy/memory/automations/*/memory.md` 只许追加、禁覆盖**
  （本脚本**不碰**它 ⇒ 由调用方另行追加）。
- 🔴 `MEMORY_MODULES.md` 的**旧正文逐字未变**（只追加新小节）。
"""
from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MEM = os.path.join(REPO, '.workbuddy', 'memory')
MEM_MD = os.path.join(MEM, 'MEMORY.md')
LOG_MD = os.path.join(MEM, '2026-11-24.md')
MODULES = os.path.join(MEM, 'MEMORY_MODULES.md')
TMP = os.environ.get('TEMP', '/tmp')

MEMORY_CAP = 9700          # 🔴 注入预算（MEMORY.md 自声明上限）


def read(p):
    if not os.path.isfile(p):
        return None
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_atomic(p, text):
    tmp = p + '.tmp_app231'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(tmp, p)


# ── ① MEMORY.md：本轮进活文档的**一行指针**（不抄状态）────────────
# 🔴 **零余量**：`MEMORY.md` 当前 **恰好 9 700 字符 = 自声明上限**
#   ⇒ 加一行指针**必须同时压掉同等字数**（否则超限 ⇒ 零改动）。
#   本轮压缩来源 = **§十二 的三条已过期状态行**（§226/§227 轮的历史轮次细节
#   **已逐字归档**在 `status/archive/` 与 `MEMORY_MODULES.md` 附录·四十九
#   ⇒ 压它们**不丢信息**，只降密度）。
# 🔴 **修正一处过期事实**：§十二 首行写 `last_ack=APP-128`（**已过期**，
#   实际 APP-133）⇒ 改正；这是"状态更新"，**不删任何判据**。
MEM_LINE = (
    '-🔴**机器锁必须原子创建**（tmp 写全＋os.link／O_CREAT|O_EXCL）⇒别人 CreateNew '
    '必失败；🔴**禁 os.replace(tmp, LOCK)**（会**覆盖**别人的锁⇒双方都以为拿到）｜'
    '🔴**看门狗被抢即放弃⇒锁丢了无人知晓**⇒须记 lock_lost 事件｜'
    '🔴**修锁要修生产路径**（只修 harness 等于没修）⇒⇒MODULES 五十\n'
)

# §十二 的三条压缩（**逐条对应，不删判据，只压从句**）
# 🔴 **锚点写法**：**不手抄长串**（手抄必错——本轮实测 B4 因 `**` 位置差一
#   处就命中失败）⇒ 改为「**定位小节 → 取行 → 断言前缀**」再按行替换。
#   前缀短且唯一 ⇒ 等价于唯一命中断言，且不会因全角/加粗标记差一处而误判。
SEC12_HEAD = '## 十二、App 当前状态'
SEC12_TAIL = '## 十二之补'
# (行索引, 前缀断言, 新内容)
SEC12_EDITS = [
    (1, '-🔴`last_ack=APP-128`',
     '-🔴`last_ack=APP-133`（APP-131/132/133 已执行⇒§230/§231）｜🟢**v2.6 已签 '
     'ACCEPTED**（EXT v0.4.21 `b2a4978`）｜🟢reviewer 判 APP-128 通过；'
     '`clone_s2` 的 `n_speakers=0` 判为正常｜🔴**待裁定**：默认分离设备／v2.6 交接。'),
    (2, '-🟢**APP-128 补充已执行（§225）**',
     '-🟢**APP-128 补充已执行（§225）**：已单独补发 e2e7 三臂表（正文截断）⇒ '
     '邮件 `msg_52Ta35…`（462 B）｜提交 `b7507cb`。'),
    (4, '-🟢**§226（11-24 00:4x）待命轮＋TAKEOVER**',
     '-🟢**§226（11-24 00:4x）待命轮＋TAKEOVER**：无新纠偏｜🟢已修「reviewer 复算底本'
     '入库字节不一致」（3/3＋反证组 3/3）｜提交 `73a2e22`…`58439ba` 已推｜🔴**更大面未修**：'
     '全仓 **854** 个 `i/lf+w/crlf` ⇒ **须 reviewer 裁定**｜🔴**未进 v2.6／未打包**'
     '（APP-126 §7）。'),
]

# ── ② 当日日志段（append-only）──────────────────────────────────
LOG_ENTRY = """
### 第 126 轮巡检（2026-11-24 19:5x–20:3x）— **接续上一会话（TAKEOVER）**｜**无新 App 纠偏**（六通道复核干净）｜🟢**闭合上一会话遗留的「记忆写入未落盘」**｜🟢**补上 APP-132 的生产路径补漏**
- **租约**：`acquire app` ⇒ exit 0 / **TAKEOVER**（上一会话 token `47796b43`，17:06:53 起、
  last_beat 18:34:37＝**78 min 前** ⇒ 死会话；note=`已提交 19d9369 并推送（origin/main 0/0）；
  邮件 2 封已发（含 3 个 OGG）；写记忆文件`；live_pids=[] alive=False）⇒ 本轮 token **`377715be`**，
  beats ×N ⇒ 收尾 `release`。
- **纠偏（六通道全空 ⇒ 无新 App 纠偏）**：局域网 `status/app/CORRECTIONS_APP.md`
  **130 条／max APP-133**／SHA `2db65bf13f23a701…`／**440 181 B**／mtime **2026-11-24 13:56:42**；
  QQ 收件箱最新 App 封仍 = **APP-133**（`msg_HbiVRXlg…`，11-24 05:56:40Z）；spam **0**；trash **1**（无关旧件）；
  根 `status/CORRECTIONS.md` max **C-135**（已冻结）；`shared/NOTICE*` 仍 ≤11-05；agent-mail `not_bound`。
  ⇒ **`last_ack` 仍 APP-133**（本地 max ＝ QQ max ＝ last_ack ⇒ 无新条目）。
- **🟢 本轮主发现：APP-132 的修法只落在**侧写 harness**，**生产打包路径的缺陷原封不动**：
  上一轮 §230 写的是「`results/app/_app132_lock.py`」这个**专供 v2.6 整链三臂**的 harness；
  而**真正成包的路径** `live_caption/_app116_build_v25.py`
  （⇒ `live_caption/_app129_build_v26.py` 第 216 行 `B.acquire_lock(...)`）**仍是旧代码**：
  ① `os.replace(tmp, LOCK)` **不是原子创建** ⇒ 两个进程可同时"拿到"锁、且**会覆盖别人刚建的锁**；
  ② 看门狗条件 `own is None or own.get('pid') == os.getpid()` ⇒ 锁被抢后**彻底放弃写回**，
  且写回用 `os.replace` ⇒ **静默覆盖别人的锁** ⇒ 链**继续跑但不再持锁**且**无人知晓**。
  ⇒ **已修**（`results/app/_app231_patch_lock.py`）：取锁走 **tmp 写全 + `os.link`**（原子 + 独占）、
  探测与创建**合并进同一 while 循环**（消除 TOCTOU 窗口）、看门狗改为**只自检不盲写**
  （锁被删 ⇒ **独占地补建**；被抢 ⇒ 记 `lock_lost` 事件）、新增 `results/app/app231_pack_lock_events.jsonl`。
- **🟢 独立行为级复核 9/9 PASS**（`results/app/_app231_verify_lock.py`，**纯 CPU 逻辑测试**、
  **不跑推理·不测速**、**用临时目录做锁 ⇒ 不碰真 `shared\\MACHINE_LOCK`**）：
  判据①**确定性**（6 进程经文件栅栏同瞬间并发建锁 ⇒ **恰好 1 个**成功）；
  🔴**反证组**（同测试跑在旧 `os.replace` 实现上 ⇒ **2 个**成功 ⇒ 缺陷可复现 ⇒ **判据能识破有缺陷的旧代码**，
  证明不是"判据恒 PASS"的假 PASS）；判据②端到端（两进程走完 `acquire_lock`，持锁期间轮询锁内容 ⇒
  **无"两把锁并存"**）；＋别人先建锁 ⇒ 我方创建失败且**不覆盖**；＋看门狗 ⇒ 记 `lock_lost` 且**不覆盖**；
  ＋放锁**只删自己的**。
- 🔴 **本轮新学的两个判据坑**：① **「两个进程都拿到锁」≠「两把锁并存」** —— 进程 A 可能**先放锁再轮到 B**
  ⇒ 那是**合法串行**；⇒ 判据必须测「**持锁期间锁内容被别人改写**」这个**重叠**现象，不能数「拿到锁的进程数」。
  ② **判据写文本计数 ⇒ 必假 FAIL**：`os.replace(tmp, LOCK)` 这个串在新 docstring 里**本来就要出现**（解释旧缺陷）
  ⇒ 文本计数命中 ⇒ **改用 AST 判定「代码里不得有 `os.replace` 调用」**（语义精确、注释/文档串不误伤）。
- **🟢 上一会话遗留项已闭合**：它的 `results/app/_app133_write_memory.py` **从未运行**
  ⇒ 当日日志无「第 126 轮」、`MEMORY.md` 无机器锁指针且 §十二 仍写 **`last_ack=APP-128`**（**已过期**）
  ⇒ 本轮**补写**（并**补上它漏掉的 9 700 字符上限断言**）。
- **纪律**：🟢 **未打包 zip**（用户级纪律「不通知 ⇒ 不打包」）｜🟢 **未覆盖/未删除任何旧版本目录与 zip**｜
  🟢 **未通知用户**｜🟢 **未连 B 机**｜🟢 **未调 MiniMax**｜🟢 **未跑推理·未测速**（纯逻辑测试，不占机器锁）｜
  🟢 **未改 `status/app/CORRECTIONS_APP.md`**（只读）｜🟢 **未进 MiniMVP 包**。
- **下一轮**：last_ack 仍 **APP-133**；⏭ 等 reviewer 复核 **§230**（APP-131/132/133）与**§231**（本轮补漏）；
  🔴 **待裁定**：仓库根 `.gitattributes` 根治（跨模块）／默认分离设备／`n_speakers=0` 口径／
  **v2.6 交接与是否出 zip**／**v2.5 重签 ACCEPTED**。
"""

# ── ③ MEMORY_MODULES.md：追加新小节（模块细节）──────────────────
MODULES_ENTRY = """
## 五十、机器锁的「原子创建」与「生产路径」判据（2026-11-24 §231 轮，展开版）

### 五十.0 事件：APP-132 的修法只落在侧写 harness，生产路径原封不动

- 🔴 **APP-132（reviewer 11-24 05:26Z）**：我方 v2.6 链在臂与臂之间**没持住**
  `shared\\MACHINE_LOCK` ⇒ reviewer 的排队脚本（**只用 CreateNew 原子创建、绝不抢锁**）
  在 **12:44:18 成功建锁** ⇒ 我方当时**实际没在持锁** ⇒ 两边同时占 GPU.0/NPU/CUDA
  ⇒ 13:08 起那一臂的计时作废。
- 🔴 **reviewer 的要求**：「整条链（所有臂、默认值检查、抽听样片）**一次持锁到底**，中途不删；
  锁内容写明起止。结束后再删（只删自己的）。」
- 🔴 **上一轮（§230）做的事**：新写 `results/app/_app132_lock.py`（**侧写 harness**，
  专供 v2.6 整链三臂跑）⇒ 改用 `O_CREAT|O_EXCL` 原子创建 ＋ 10 s 复核 ＋ 丢锁记事件
  ⇒ 整链一次持锁到底（17:45:04→18:25:10，`lock_lost` **0** 条）✅ **该轮的验收目标确实达成**。
- 🔴🔴 **但生产打包路径没被修**（**本轮 §231 补上的漏**）：
  `live_caption/_app116_build_v25.py`（v2.5/v2.6 成包都走它）
  ⇒ `live_caption/_app129_build_v26.py` 第 216 行 `B.acquire_lock('app build v2.6 copy')`。
  该文件里**两处原缺陷原封不动**：
  | # | 位置 | 缺陷 | 后果 |
  |---|---|---|---|
  | ① | `acquire_lock()` 末行 `os.replace(tmp, LOCK)` | **不是原子创建** | 两个进程可同时"拿到"锁；且**会覆盖别人刚建的锁**（TOCTOU） |
  | ② | `start_lock_watchdog()` | 条件 `own is None or own.get('pid') == os.getpid()` ⇒ 被抢即放弃写回；写回又用 `os.replace` | 链**继续跑但不再持锁**且**无人知晓**；写回还**静默覆盖别人的锁** |
- 🔴 **通用判据**：**「修了 harness」≠「修了产品」** ⇒ 交付路径与验收路径是**两条路**，
  修锁/修闸门/修格式时**必须问：「生产上真正跑的是哪个文件？」**（本例：
  `import _app116_build_v25 as B` ⇒ 生产走的是 **B**，不是 harness）。

### 五十.1 正解：机器锁必须「tmp 写全 + `os.link`」（原子 + 独占 + 不露半成品）

- 🔴 **三种写法对比**（仓库根 `machine_lock_app.py` 第 405~420 行有逐字论证 + 实测事故）：
  | 写法 | 原子？ | 独占？ | 别的模块会看到半成品锁？ |
  |---|---|---|---|
  | `os.replace(tmp, LOCK)` | 🔴 **否**（覆盖） | 🔴 **否**（可覆盖别人） | 否 |
  | `os.open(O_CREAT\\|O_EXCL)` **再写内容** | ✅ 是 | ✅ 是 | 🔴 **会**（先建空文件、之后才写内容 ⇒ 窗口里别人读锁**解析不出 pid** ⇒ 判成"陈旧锁" ⇒ `os.remove` **删掉我们的活锁** ⇒ 两模块同时跑） |
  | ✅ **tmp 写全 + `os.link(tmp, LOCK)`** | ✅ **是**（硬链接原子建立） | ✅ **是**（目标已存在 ⇒ `FileExistsError`） | ✅ **不会**（内容要么完整、要么文件不存在） |
- 🔴 依据：`shared/NOTICE_tts_lock_atomic_20261026.md`；仓库根 `machine_lock_app._write_lock_atomically`
  与 `write_lock_atomic()`（**公开入口** ⇒ 「App 侧所有计时脚本**统一走这里** ⇒ 不再各写一份
  （逻辑漂移的根源）」—— 本轮教训正是**逻辑漂移**）。
- 🔴 **配套**：**看门狗被抢即放弃 ⇒ 锁丢了却无人知晓** ⇒ 必须**记事件**
  （`results/app/app231_pack_lock_events.jsonl`，JSONL 一行一条）⇒ 计时结论据此作废。

### 五十.2 🔴 两个新判据坑（写进判据工程，防复发）

- 🔴 **坑①：「两个进程都拿到锁」≠「两把锁并存」** —— 进程 A 可能**先放锁再轮到 B**
  ⇒ 那是**合法串行**，不是违规（**本轮实测**：初版判据数「拿到锁的进程数」⇒ 报 FAIL，
  实际是**判据错**，不是代码错）。
  ⇒ ✅ 判据必须测「**持锁期间锁内容被别人改写**」这个**重叠**现象
  （持锁方每 100 ms 读一次锁内容 ⇒ 与自己内容不符 ⇒ 重叠），**不能数进程数**。
- 🔴 **坑②：判据写文本计数 ⇒ 必假 FAIL** —— `os.replace(tmp, LOCK)` 这个串在**新 docstring 里
  本来就要出现**（解释旧缺陷）⇒ 文本计数命中 ⇒ 误报「旧的非原子写仍在」。
  ⇒ ✅ **改用 AST 判定**：「代码里不得存在对 `os.replace` 的调用」（`ast.walk` 找
  `Call(func=Attribute(attr='replace', value=Name('os')))`）⇒ **语义精确、注释/docstring 不误伤**。
  ⇒ 与 MEMORY §四「**判据里写死的常量 = 假 FAIL 源**」同族：**判据要绑语义，不绑字面**。
- 🔴 **坑③（Python）**：`multiprocessing` 的 **`spawn`** 上下文**不能 pickle 局部函数**
  ⇒ 子进程目标函数必须在**模块级**（否则 `AttributeError: Can't get local object`）。
  ⇒ 并发竞态测试要用**文件栅栏**（子进程等 `GO` 文件出现再一起冲）才**确定性**复现，
  否则"两边都拿到"可能根本没发生（**时序运气 ⇒ 判据不可靠**）。

### 五十.3 本轮的落地（可复核）

- `live_caption/_app116_build_v25.py`：**10 820 B / SHA256 `49c879e1…` ⇒ 15 749 B / SHA256 `8d1c9b5e…`**
  （`ast.parse` OK，纯 LF；**只改这一个文件** ⇒ 未碰客户包、未碰其它模块）。
- `results/app/_app231_patch_lock.py`（补丁，**幂等守卫**「已打过补丁 ⇒ 拒」）＋
  `results/app/_app231_verify_lock.py`（独立复核，§222：**证据 json 入库 ⇒ 其产生脚本也要入库**）＋
  `results/app/app231_lock_verify.json`（**9/9 PASS**，含反证组：新=1 / 旧=2）。
- 🔴 **本轮是纯 CPU 逻辑测试**：**不跑推理·不测速**、**用临时目录做锁** ⇒ **不碰真
  `shared\\MACHINE_LOCK`** ⇒ 与其它模块零干扰（按纪律「纯静态检查／不载模型的 CPU 单测不锁」）。
"""


def main():
    os.makedirs(MEM, exist_ok=True)
    out = []

    # ── ① 当日日志（append-only）──────────────────────────────
    old = read(LOG_MD)
    if old is None:
        old = ''
    if '第 126 轮巡检（2026-11-24 19:5x–20:3x）' in old:
        out.append('当日日志：已存在 ⇒ 零改动')
    else:
        new = old.rstrip('\n') + '\n' + LOG_ENTRY
        assert new.startswith(old.rstrip('\n')), '当日日志不是纯追加'
        assert new.count('### 第 ') == old.count('### 第 ') + 1, '轮次增量不对'
        write_atomic(LOG_MD, new)
        out.append('当日日志：%d B → %d B（append-only）'
                   % (len(old.encode('utf-8')), len(new.encode('utf-8'))))

    # ── ② MEMORY.md（活文档）：① 压缩三条过期状态行 ② 加一行指针 ──
    m = read(MEM_MD)
    if m is None:
        out.append('MEMORY.md 不存在 ⇒ 零改动')
    else:
        before_lines = m.count('\n')
        before_marks = m.count('🔴') + m.count('🟢')
        before_len = len(m)

        if '机器锁必须原子创建' in m:
            out.append('MEMORY.md：已含本轮指针 ⇒ 零改动')
        else:
            # ②① 压缩 §十二 的三条（**按行索引 + 前缀断言**；只压从句，不删判据）
            assert m.count(SEC12_HEAD) == 1, '§十二 标题命中数 != 1'
            assert m.count(SEC12_TAIL) == 1, '§十二之补 标题命中数 != 1'
            i0 = m.index(SEC12_HEAD)
            i1 = m.index(SEC12_TAIL)
            sec_lines = m[i0:i1].split('\n')
            old_lines = list(sec_lines)
            for idx, prefix, new_b in SEC12_EDITS:
                assert idx < len(sec_lines), '§十二 行索引越界：%d' % idx
                assert sec_lines[idx].startswith(prefix), (
                    '§十二 第 %d 行前缀不符：%r != %r'
                    % (idx, sec_lines[idx][:40], prefix))
                sec_lines[idx] = new_b
            new = m[:i0] + '\n'.join(sec_lines) + m[i1:]

            # ②② 机器锁指针：**插到「二、机器锁」小节的最后一行 bullet 之后**
            #     🔴 **off-by-one 坑**（本轮踩到）：`j = find('\n## ')` 指向的是
            #     「下一节标题前的那个 \n」⇒ 用 `new[:j].rstrip('\n')` 会**吃掉
            #     小节末尾的空行** ⇒ 行数增量变 0（断言失败）。
            #     ✅ 正确做法：把新行插在**该小节最后一个 bullet 的换行之后**，
            #     即 `new[:j_end].rstrip('\n') + '\n' + MEM_LINE + '\n' + new[j_end:]`
            #     —— `j_end` = 下一个 `\n## ` **之前**的那个换行位置。
            anchor = '## 二、机器锁（`shared/MACHINE_LOCK`）＋ 模块租约\n'
            assert new.count(anchor) == 1, 'MEMORY.md 锚点命中数 != 1'
            i = new.index(anchor) + len(anchor)
            j = new.find('\n## ', i)          # 下一个 `## ` 之前的换行位置
            assert j > i, '机器锁小节结构异常'
            # 该小节的正文 = new[i:j]（不含 j 处那个换行）
            sect = new[i:j]
            assert sect.endswith('\n'), '机器锁小节末尾结构异常'
            # 🔴 **只去掉**最后一个换行（用 `[:-1]` 而非 `rstrip('\n')`：
            #    rstrip 会把**多个**尾换行一起吃掉 ⇒ 行数增量算错）
            sect_body = sect[:-1]
            # 🔴 **保留小节之间的空行**：`new[j:]` 本身就是「空行 + 下一个
            #    `## `」⇒ **不能**用 `new[j+1:]`（那会把空行吃掉 ⇒ 行数 +0）
            new = (new[:i] + sect_body + '\n' + MEM_LINE.rstrip('\n') + '\n'
                   + new[j:])
            # 真不变量
            assert new.count('\n') == before_lines + 1, '行数增量不对'
            assert (new.count('🔴') + new.count('🟢')) >= before_marks, '标记数减少'
            # 🔴 上限断言（**上一轮脚本漏了这条** ⇒ 本轮补上）
            assert len(new) <= MEMORY_CAP, (
                'MEMORY.md 会超上限：%d > %d ⇒ 零改动' % (len(new), MEMORY_CAP))
            # 还原式复核：把改动改回去 ⇒ 必须逐字节等于原文
            restored = new
            r0 = restored.index(SEC12_HEAD)
            r1 = restored.index(SEC12_TAIL)
            r_lines = restored[r0:r1].split('\n')
            for idx, prefix, new_b in SEC12_EDITS:
                assert r_lines[idx] == new_b, '还原时行内容不符：%d' % idx
                r_lines[idx] = old_lines[idx]
            restored = restored[:r0] + '\n'.join(r_lines) + restored[r1:]
            restored = restored.replace(
                MEM_LINE.rstrip('\n') + '\n', '', 1)
            assert restored == m, '还原式复核失败'
            write_atomic(MEM_MD, new)
            out.append('MEMORY.md：%d → %d 字符（+1 行指针；上限 %d，余 %d）'
                       % (before_len, len(new), MEMORY_CAP, MEMORY_CAP - len(new)))

    # ── ③ MEMORY_MODULES.md（追加新小节）──────────────────────
    mo = read(MODULES)
    if mo is None:
        out.append('MEMORY_MODULES.md 不存在 ⇒ 零改动')
    else:
        if '## 五十、机器锁的「原子创建」与「生产路径」判据' in mo:
            out.append('MEMORY_MODULES.md：已含本轮小节 ⇒ 零改动')
        else:
            # 🔴 只在**最后一个 ``` 围栏之后**追加（保持既有围栏配对）
            assert mo.rstrip().endswith('```'), 'MODULES 末尾结构与预期不符'
            new = mo.rstrip('\n') + '\n' + MODULES_ENTRY
            assert new.startswith(mo.rstrip('\n')), 'MODULES 不是纯追加'
            write_atomic(MODULES, new)
            out.append('MEMORY_MODULES.md：%d B → %d B（追加「五十」小节）'
                       % (len(mo.encode('utf-8')), len(new.encode('utf-8'))))

    for line in out:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
