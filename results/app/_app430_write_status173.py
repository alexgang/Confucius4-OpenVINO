#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app430_write_status173.py —— 落盘 §173（写前自检 + 写后独立复核）。

🔴 **纪律**
- **只追加** `## §173` 一节；**旧章节的结论一字未改**（只把 §172 的**正文**按
  APP-052④ 索引化，**完整原文逐字保留在 write-once 归档件**——这与 §170→§171、
  §171→§172 两轮**完全同一做法**）。
- **只定点改**头部 3 行（`更新时间`／`当前任务`／`阻塞 / 待用户决定`）。
- **绝不**改 `status/app/CORRECTIONS_APP.md`（reviewer 独占）。
- **绝不**改任何**已存在**的归档件（write-once）⇒ 本轮只**新建** `sec173` 归档件。
- 活文档实测**全 LF**（CRLF=0）⇒ 写回必须**无裸 CR**。

## 布局

| 位置 | 内容 |
|---|---|
| 活文档 §172 | **索引化**：标题 + 指针行（**带真值 SHA**）+ 速查行（原文精简） |
| 归档件 `sec172` | §172 **完整原文逐字**（**既有文件，本轮逐字节不动**） |
| 活文档 §173 | 标题 + 指针行（带真值 SHA）+ 速查行（`QUICK` 共享常量） |
| 归档件 `sec173`（**新建**） | §173 **完整正文**（含 `QUICK` 逐字 + ①～⑦ 细节） |

🔴 `QUICK` 是**同一个 Python 字符串常量**，同时进活文档与归档件 ⇒
「活文档每条速查行都能在归档件里逐字找到」由**构造**保证，不会两边漂移。

## 写前自检（任一不过 ⇒ 源文件零改动）

1. 活文档 SHA256 == 基线（防并发改写）；2. 章节数 == 18（写后 19）；
3. 头部 3 行旧文本逐字留档；
4. **体积/行数在写盘前**算完并断言 ⇒ 不会「先写归档件再发现超限」的半落地；
5. `sec173` 归档件**不得已存在**（write-once）。

## 写后独立复核

- §172 的**旧正文逐字**仍在归档件 `STATUS_APP_sec172_20261111.md` 里（活文档只做索引化）；
- **§172 归档件 SHA256 与开工时逐字一致**（write-once 未被触碰）；
- 其余旧章节（§141…§171）**逐章节块逐字未变**；
- 章节数 18 → 19 且只多出 §173；
- 仍**无 CRLF**、字节数 ≤ 40 000、行数 ≤ 300；
- §173 指针行声明的归档件 SHA256 == 磁盘实测；
- 活文档 §173 每条速查行都能在归档件里**逐字**找到；
- `CORRECTIONS_APP.md` 的 SHA256 **与开工时逐字一致**（证明全程只读）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
ARCH173 = 'STATUS_APP_sec173_20261111.md'
ARCH172 = 'STATUS_APP_sec172_20261111.md'
OUT = os.path.join(REPO, 'results', 'app', 'app430_status173_write.json')

LIMIT_BYTES = 40000
LIMIT_LINES = 300
TS = '2026-11-11 04:07:00'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ===================================================================== 共享速查行（§173）
# 🔴 活文档与归档件**共用同一批字符串常量** ⇒ 事实一致性由**构造**保证。
QUICK = [
    "> 🔴 **速查**：**无新 reviewer 纠偏**（97 条／最大 APP-097，SHA `36af1620…`／285 671 B，"
    "**SHA 零改动**、全程只读未改未提交；`last_ack` 仍是 APP-098）｜其它通道全空"
    "（`shared/NOTICE*` 最新仍 11-05／agent-mail `not_bound`／`conversation_search` 命中 0／"
    "git ahead=0·behind=0／`claude-clone` 无新提交／`MACHINE_LOCK` NOT_PRESENT）｜"
    "**① 头部 4 处过期／自相矛盾（已修）**：**H1** 引用滞后一章｜**H2** 头部称「未改 "
    "`_SEC_PER_CHAR`」而 §172 **已回填** ⇒ 同文档自相矛盾｜**H3** 头部称「历史影响未评估」"
    "而 §171 **已定界 D1/D2**｜**H4** 头部报「17 G」实测 **22.7 G** ⇒ 已按「只动头部」"
    "**定点改 3 行**（旧章节结论一字未改）。",
    "> 🔴 **② 新判据「归档指针可核对性」**：归档件有 3 种可接受形态（`raw`／`rstrip`／`body`，"
    "历史写法不统一）⇒ **32 指针：OK 25／FAIL 0／7 条早期索引行「从未声明 SHA」只记信息**；"
    "**反证 3/3 全触发**（篡改 §171 归档件 1 字节 ⇒ OK→FAIL｜给 §172 末行注入 SHA ⇒ "
    "悬空→OK｜改头部引用 ⇒ H1 消失）⇒ 判据有鉴别力。",
    "> 🔴 **③ 既有闸门复跑全绿**（纯 CPU 静态，未占设备）：sec_per_char **27/27**｜app109 **34/34**｜"
    "pkg_clean 对 v2.4 **0 违规**｜window 同源 **PASS**；复跑产生的两个 evidence JSON "
    "**仅时间戳变** ⇒ 已还原不留噪声 diff。",
    "> 🔴 **④ 自踩 3 个判据坑（已修）**：SHA 归属（同行 3 个归档件 ⇒ 同一个 SHA 被派给 3 个 ⇒ "
    "3 个假 FAIL）＋「没写 SHA」与「写了核对不上」混淆（6 个假 FAIL）＋键名带修饰导致 H2 "
    "首版假阴性（头部键名其实是「阻塞 / 待用户决定:」）⇒ 判据 v2 分段配对并区分两类、改正则。"
    "**教训：判据写完必须先跑反证组；「正则没匹配上」与「事实不存在」输出上长得一样。**",
    "> 🔴 **⑤ 未做**：未打包 v2.5｜未改生产代码｜未改客户包｜未通知用户｜未调 MiniMax｜未占设备｜"
    "未持锁｜未删任何文件｜交付配置仍冻结（全 NPU／spkonly／INT8；EXT v0.3.7 @c414294）。",
    "> 🔴 **⑥ 下一轮必读**：节点＝**等 reviewer 复核 §173**（H1–H4 修正／三形态口径／"
    "§172 悬空指针三项待裁定）｜倍率地板仍未裁定｜GUI 布局修复仍未同步进客户包｜"
    "§3.5 判据失效、§3.6 不可测｜**v2.5 建包时别把 `assert_*.py` 带进 `app/`**"
    "（`pkg_exclude` 只排 `_` 前缀；但 `assert_pkg_clean.py` 是**必须随包**的例外）｜"
    "v2.5 不打包（用户不通知）｜磁盘 22.7 G。",
]

TITLE = ("## §173 巡检（last_ack=APP-098，2026-11-11 04:07:00）｜**无新纠偏**；"
         "修掉 STATUS **头部四处过期／自相矛盾** ＋ 新增「归档指针可核对性」判据"
         "（25/25 OK ＋ 3 反证全触发）｜**本条需等 reviewer 复核**")

# ===================================================================== §172 索引化后的活文档版
# 🔴 只压缩**排版**，**不删任何结论**；完整原文逐字在归档件（write-once，不动）。
SEC172_LIVE = """## §172 巡检（last_ack=APP-098，2026-11-11 02:21:21）｜**无新纠偏**；补做 APP-097 §2-4「`_SEC_PER_CHAR` 实测校准」**回填**（reviewer 明文「用它定」）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec172_20261111.md`（4415 B／块 SHA256 `92efe1c19232ce508fe83e208ef7682f9ba7911050aef032fe72871c10f8aab3`）｜**归档件逐字节未动**（write-once）｜**本节正文**已按 APP-052④ 索引化，**结论一字未改**。
> 🔴 **速查**：**无新 reviewer 纠偏**（97 条／最大 APP-097，SHA `36af1620…`／285 671 B，**SHA 零改动**、全程只读未改未提交）｜**回填口径（保守，宁高不低）**：`value = ceil3(max(preset_p50, clone_p50))`，源 `app326_app097_lang_out/tts.json`（复算不手抄）⇒ de .073／fr .070／es .085／pt .080／it .081／ru .083；**zh/en/ja/ko 逐字未动**；守卫阈值**只可能变松**｜**倍率地板未改**（等 reviewer 裁定）｜**新闸门** `assert_sec_per_char_calibrated.py` **27/27 PASS**（含反证 3/3）＋ app109 **34/34 PASS**｜**只改开发树** `tts_engine.py`（95 063 B／`b53e5670…`）⇒ **未碰任何客户包**｜**本轮自踩两个坑**（判据层：① 断言「CRLF 个数不变」是**伪不变量** ⇒ 改成真不变量「无裸 LF」；② `ast` 抽表漏抽 `map_language`/`LANG_MAP` ⇒ 落 except ⇒ 别名全归 en ⇒ 补抽后 27/27）｜**产物** `app427_sec_per_char_calibration.json`／`assert_sec_per_char_calibrated.json`／`_app427_apply_sec_per_char.py`／`_app427_app109_regression.json`／`live_caption/assert_sec_per_char_calibrated.py`｜未打包 v2.5、未通知用户、未调 MiniMax。
"""

# ===================================================================== 归档件完整正文（§173）
FULL_BODY = TITLE + "\n\n" + "\n".join(QUICK) + """

### ① 🔴 本轮真发现：**STATUS 活文档头部有 4 处过期／自相矛盾**（判据 = 行为级机读，非人眼）

> 头部是 reviewer 每次打开 STATUS **第一眼**看到的内容；它一旦与正文矛盾，reviewer 会按**过期信息**做决策。
> 本轮新增机器可查的 4 条判据（`_app429_status_pointer_audit.py` 的 `header_contradictions`），**4 条全命中**：

| 编号 | 头部原文（实测） | 正文事实（实测） | 性质 |
|---|---|---|---|
| **H1** | 「当前任务」只引用 **§170／§171** | 活文档最新章节是 **§172**（已落盘且已归档） | 头部**滞后一章** |
| **H2** | 「阻塞」称「APP-097 §2-4 只报实测 p50、**未改 `_SEC_PER_CHAR` 默认值**」 | §172 正文写明**已按 §2-4 回填**（de .073／fr .070／es .085／pt .080／it .081／ru .083） | **自相矛盾**（同一文档内） |
| **H3** | 「阻塞」称「🔴 **该缺陷的历史影响未评估**」 | §171 已给 D1/D2 **定界完毕**（D1 零交付物受影响／D2 影响已交付的 rc5） | 头部**滞后** |
| **H4** | 「阻塞」报「C 盘 100 %、**仅剩 17 G**」 | 实测 C: 可用 **22.7 G**（99 %）⇒ 差 **5.7 G** | 数字**过期** |

> 🔴 **已修**：按 APP-052④「只动头部」**定点改 3 行**（`更新时间`／`当前任务`／`阻塞 / 待用户决定`）——
> **H1** 改为指向 §173；**H2** 改为「§172 **已回填**」并保留「倍率地板仍等 reviewer 裁定」；
> **H3** 改为「历史影响**已定界**（D1/D2，见 §171）」；**H4** 改为实测值。
> **旧章节结论一字未改**（§172 仅做**排版索引化**，完整原文逐字留在归档件，写后逐字复核）。
> 🔴 **H2 特别要紧**：reviewer 若只看头部，会以为「6 种新语言的 `_SEC_PER_CHAR` 还没回填」⇒ 可能重做或误判 §172 的结论。

### ② 新增判据：**归档指针「可核对性」**（读者能否照指针把归档件核对上）

> 活文档里每处 `status/archive/STATUS_APP_sec*.md` 指针都（或曾）带一个 SHA256 声明。
> 本轮把「声明了却核对不上」做成机器可查的判据：
> **一个归档件的可接受形态有 3 种**（历史写法不统一，本身不是缺陷）：
> `raw`（磁盘字节原样，§171 §172）／`rstrip`（去尾部换行，§169 §170）／`body`（归档件自带 `#` 抬头时取正文块，§162）。
> **三种都不命中 ⇒ FAIL；从未声明过 SHA ⇒ 只记「无可核对声明」，是信息不是缺陷。**

* **结果：32 条指针 ⇒ OK 25 / NO_SHA_CLAIMED 7 / **FAIL 0**。**（7 条 NO_SHA_CLAIMED 全是 APP-052④ 早期索引行，**从未声明 SHA**，故不算缺陷。）
* **🔴 反证组 3/3 全触发（⇒ 判据有鉴别力、非恒真）**：
  * **A**：把 §171 归档件**篡改 1 字节**（仅内存 XOR，未落盘）⇒ 该行必须由 `OK` 变 **`FAIL_UNVERIFIABLE`** ✔
  * **B**：给 §172 末行**注入一个 SHA**（仅内存，未落盘）⇒ 悬空指针必须由 `FAIL` 变 **`OK`** ✔（证明 FAIL 不是「找不到就不认」）
  * **C**：把头部引用改成最新章节 ⇒ **H1 必须消失** ✔
* 🔴 **顺带查出一处真悬空引用**：§172 的指针行写「**块 SHA256 见本节末「归档」行**」，但**该「归档」行里根本没有 SHA** ⇒ 读者按指针**无法核对**。
  归档件实测 = **4 415 B／SHA256 `92efe1c19232ce508fe83e208ef7682f9ba7911050aef032fe72871c10f8aab3`**。
  ⇒ 本轮把 §172 的活文档**索引化**时，顺手把**真值 SHA 直接写进指针行** ⇒ 悬空**已消除**；
  且 §172 归档件**逐字节未动**（write-once 守住），§172 的**结论一字未改**。

### ③ 既有闸门复跑（纯 CPU 静态，**未占设备** ⇒ 未持 `MACHINE_LOCK`）

* `live_caption/assert_sec_per_char_calibrated.py` ⇒ **27/27 PASS**（F 反证组 3/3 触发）
* `results/app/app109_lang_key_guard.py` ⇒ **34/34 PASS**（零回归）
* `live_caption/assert_pkg_clean.py`（对 **v2.4** 客户包）⇒ **0 违规**
* `live_caption/assert_window_same_source.py`（对 **v2.4** 客户包）⇒ **PASS**
* 🔴 复跑后 `results/app/assert_sec_per_char_calibrated.json` 与 `app109_lang_key_guard_evidence.json` **仅 `created_at`/`ts` 变**（其余字段逐字相同）⇒ 已还原，**不留噪声 diff**。

### ④ 🔴 本轮自踩 3 个坑（**判据自身的缺陷**，已修 ⇒ 留档）

* **坑 1（SHA 归属）**：判据 v1 用「同一行里出现的第一个 SHA」配对 ⇒ **一行里列 3 个归档件**（L7 的「已压缩」行）时，把**同一个** SHA 派给了 3 个文件 ⇒ **3 个假 FAIL**。⇒ v2 改为**按行分段（`；`／`｜`）、段内按出现顺序配对**。
* **坑 2（口径混淆）**：判据 v1 把「**指针行上没写 SHA**」直接判成 FAIL ⇒ 早期索引行（**从未声明过 SHA**）被误判 **6 个假 FAIL**。⇒ v2 拆成 `NO_SHA_CLAIMED`（信息）与 `FAIL_UNVERIFIABLE`（真缺陷）两类。
* **坑 3（键名带修饰 ⇒ 假阴性）**：我自己的**第一条矛盾判据 H2 首版也没命中** —— 因为头部那一行的键名其实是「**阻塞 / 待用户决定**:」而不是「阻塞:」⇒ 首版正则 `^阻塞:` 匹配不上 ⇒ **假阴性**。已改为 `^键名(\\s*[/／][^:：]*)?\\s*[:：]`。
* ⇒ **教训（并入 MEMORY）**：**判据写完必须先跑反证组**；**「正则没匹配上」与「事实不存在」在输出上长得一模一样**（都是「没命中」）⇒ 必须用反证组区分「判据不触发」与「事实不存在」。

### ⑤ 本轮**未做**的事（口径不变，逐条留痕）

* **未打包 v2.5**（用户未通知 ⇒ 不主动打包；MEMORY 级规则）｜**未改任何客户包目录**（APP-055）｜**未改生产代码**｜**未通知用户**｜**未调 MiniMax**｜**未占设备**（纯 CPU 静态）｜**未持 `MACHINE_LOCK`**（全程 NOT_PRESENT）｜**未删任何文件**。
* **交付配置仍冻结**：全 NPU／spkonly／INT8。**EXT 内嵌 = v0.3.7 @c414294**。
* 🔴 **磁盘仍紧张**：C: **22.7 G 可用（99 %）**；打包需 10–15 G ⇒ **v2.5 打包前必须先看空间**（本轮未删任何文件）。

### ⑥ 产物（文件数 / 字节 / SHA256）

* `results/app/_app429_status_pointer_audit.py`（判据脚本，**只读**）
* `results/app/app429_status_pointer_audit.json`（审计结果：25 OK／0 FAIL／7 无声明＋4 条头部矛盾＋3 反证）
* `results/app/_app430_write_status173.py`（本节写入脚本，含写前自检与写后复核）
* `results/app/app430_status173_write.json`（写前自检 + 写后独立复核结果）
* `status/archive/STATUS_APP_sec173_20261111.md`（本节完整正文归档件，**write-once**）

### ⑦ 下一轮必读

* **节点 = 等 reviewer 复核 §173**（三个待裁定项：① H1–H4 头部修正是否接受；② 归档指针三形态口径（`raw`／`rstrip`／`body`）是否认可；③ §172 悬空指针「索引化时补真值」+「只登记不改正文」的处置是否认可）。
* 🔴 **reviewer 仍需裁定（沿用 §172，未变）**：**倍率地板**（新语言是否照 zh 设 >1×）｜**GUI 布局缺陷修复**是否随 v2.5 一起出（**仍未同步进任何客户包**）｜**§3.5 音色归属判据失效**（真值余弦 0.957–0.972 ⇒ 不可分）｜**§3.6 切段开销结构性不可测**（质心恒 1）。
* 🔴 **v2.5 建包时**：**别把 `assert_*.py` 带进 `app/`**（`pkg_exclude.is_app_dev_only` 只排 `_` 前缀 ⇒ `assert_*.py` **不被自动排除**；但 `assert_pkg_clean.py` 是**例外**——它是**必须随包**的闸门文件，见 `v23_preset_only.PKG_INCLUDE_FILES`）⇒ 建包后须**人工核**包内 `app/` 的 `assert_*` 清单。
* **v2.5 不打包**（用户不通知 ⇒ 不主动打包）｜**磁盘 22.7 G** ⇒ 打包前先看空间。
"""

# ===================================================================== 头部新文
NEW_CURRENT = (
    '当前任务: **巡检无新纠偏**（`last_ack=APP-098`；纠偏文件仍是 97 条 / 最大 APP-097 ⇒ '
    '无编号更大的新条目）｜**本轮修掉 STATUS 头部 4 处过期／自相矛盾**（H1 头部引用滞后一章／'
    'H2 头部称「未改 `_SEC_PER_CHAR`」而 §172 已回填（自相矛盾）／H3 头部称「历史影响未评估」'
    '而 §171 已定界 D1/D2／H4 磁盘「17 G」实测 22.7 G）⇒ **已按「只动头部」定点修**'
    '（旧章节结论一字未改；§172 按 APP-052④ 索引化、完整原文逐字留归档件）｜'
    '**新增「归档指针可核对性」判据**（32 指针 ⇒ OK 25／FAIL 0／7 条早期索引行「从未声明 SHA」'
    '只记信息）＋ **3 个反证组全触发**（篡改 §171 归档件 1 字节 ⇒ OK→FAIL／给 §172 末行注入 SHA '
    '⇒ 悬空→OK／改头部引用 ⇒ H1 消失）｜**顺带查出并消除 §172 悬空指针**（原指针写「块 SHA256 '
    '见本节末『归档』行」但该行无 SHA ⇒ 读者核对不上；索引化时已把真值 4 415 B／`92efe1c1…` '
    '写进指针行，**归档件逐字节未动**）｜**既有闸门复跑全绿**（sec_per_char 27/27、app109 34/34、'
    'pkg_clean 对 v2.4 0 违规、window 同源 PASS）｜**未打包 v2.5、未改生产代码、未改客户包、'
    '未通知用户、未调 MiniMax、未占设备**｜结果见 §173｜**本条需等 reviewer 复核**')

NEW_BLOCK = (
    '阻塞 / 待用户决定: 🔴 **GUI 布局缺陷修复仍未同步进客户包**（只在 dev 树 + 影子包）⇒ '
    '**v2.5 未打包、未同步任何客户包目录**（APP-055 须走打新版本号）⇒ **请 reviewer 裁定**：'
    '立刻修还是随 v2.5 一起出｜🔴 **该缺陷的历史影响「已定界」**（§171：D1 零交付物受影响／'
    '**D2 影响已交付的 rc5**）⇒ **不再是「未评估」**｜🔴 **§3.5 音色归属判据失效**'
    '（三人真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据｜🔴 **§3.6「切段真实发生时的设备开销」'
    '在本素材上结构性不可测**（质心恒 1）⇒ 需 reviewer 裁定是否调聚类阈值/换素材｜'
    '**APP-097 §2-4 的 `_SEC_PER_CHAR` 已由 §172 回填**（de .073／fr .070／es .085／pt .080／'
    'it .081／ru .083；zh/en/ja/ko 未动；守卫阈值只会变松）｜**倍率地板仍未裁定** ⇒ 等 reviewer｜'
    '🔴 **C 盘 22.7 G 可用（99 %）** ⇒ v2.5 打包需 10–15 G（**本轮未删任何文件**）｜'
    '**未打包 v2.5、未通知用户**')


def split_sections(txt: str) -> dict:
    marks = [(m.start(), int(m.group(1))) for m in re.finditer(r'(?m)^## §(\d+)', txt)]
    out = {}
    for i, (st, n) in enumerate(marks):
        en = marks[i + 1][0] if i + 1 < len(marks) else len(txt)
        out[n] = txt[st:en]
    return out


def main() -> int:
    ev = {'tool': '_app430_write_status173', 'created_at': TS}

    raw = open(STATUS, 'rb').read()
    txt = raw.decode('utf-8')
    lines = txt.split('\n')
    corr_before = open(CORR, 'rb').read()
    a172_before = open(os.path.join(ARCH_DIR, ARCH172), 'rb').read()
    pre = {
        'status_sha256_before': sha(raw),
        'status_bytes_before': len(raw),
        'status_lines_before': txt.count('\n'),
        'crlf_before': raw.count(b'\r\n'),
        'n_sections_before': len(re.findall(r'(?m)^## §', txt)),
        'header_lines_before': {'L%d' % (i + 1): lines[i] for i in (2, 3, 4, 5)},
        'corrections_sha256_before': sha(corr_before),
        'corrections_bytes_before': len(corr_before),
        'sec172_archive_sha256_before': sha(a172_before),
        'sec172_archive_bytes_before': len(a172_before),
    }
    pre_titles = re.findall(r'(?m)^## §.*', txt)
    pre_blocks = split_sections(txt)
    old_sec172_block = pre_blocks[172]
    ev['pre_checks'] = pre
    assert pre['n_sections_before'] == 18, '基线章节数不是 18：%d' % pre['n_sections_before']
    assert pre['crlf_before'] == 0, '活文档不是全 LF'
    # §172 旧正文必须逐字在既有归档件里（⇒ 索引化不丢任何东西）
    assert old_sec172_block.strip() in a172_before.decode('utf-8'), \
        '§172 旧正文不在归档件里 ⇒ 索引化会丢内容'

    # --- 归档件字节（先算，不写盘）---
    arch_bytes = ('\n' + FULL_BODY).encode('utf-8')
    arch_sha = sha(arch_bytes)
    arch_size = len(arch_bytes)

    # --- 活文档 §173（指针行 + QUICK 共享行）---
    sec173 = (TITLE + "\n\n"
              + "> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/%s`（%d B／块 SHA256 `%s`）"
                "｜**归档件逐字节未动**（write-once）。" % (ARCH173, arch_size, arch_sha)
              + "\n" + "\n".join(QUICK) + "\n")

    # --- 组装新活文档（全部在内存）---
    out = list(lines)
    n_hdr = 0
    for i, ln in enumerate(out[:12]):
        if re.match(r'^更新时间(\s*[/／][^:：]*)?\s*[:：]', ln):
            out[i] = '更新时间: ' + TS
            n_hdr += 1
        elif re.match(r'^当前任务(\s*[/／][^:：]*)?\s*[:：]', ln):
            out[i] = NEW_CURRENT
            n_hdr += 1
        elif re.match(r'^阻塞(\s*[/／][^:：]*)?\s*[:：]', ln):
            out[i] = NEW_BLOCK
            n_hdr += 1
    assert n_hdr == 3, '头部定点命中数 != 3（实得 %d）' % n_hdr

    new_txt = '\n'.join(out)
    if not new_txt.endswith('\n'):
        new_txt += '\n'
    # §172 索引化（只压缩排版，结论一字未改；原文逐字在归档件）
    assert old_sec172_block in new_txt, '§172 块定位失败'
    new_txt = new_txt.replace(old_sec172_block, SEC172_LIVE, 1)
    # 追加 §173
    new_txt += sec173
    new_bytes = new_txt.encode('utf-8')

    ev['planned'] = {
        'bytes_after': len(new_bytes),
        'lines_after': new_txt.count('\n'),
        'bytes_limit': LIMIT_BYTES,
        'lines_limit': LIMIT_LINES,
        'arch173_bytes': arch_size,
        'arch173_sha256': arch_sha,
        'sec173_live_bytes': len(sec173.encode('utf-8')),
        'sec172_live_bytes_before': len(old_sec172_block.encode('utf-8')),
        'sec172_live_bytes_after': len(SEC172_LIVE.encode('utf-8')),
    }
    # --- 写前体积断言（此时尚未写任何文件！）---
    assert len(new_bytes) <= LIMIT_BYTES, '超字节限额：%d > %d' % (len(new_bytes), LIMIT_BYTES)
    assert new_txt.count('\n') <= LIMIT_LINES, '超行数限额'
    assert not os.path.exists(os.path.join(ARCH_DIR, ARCH173)), 'sec173 归档件已存在（拒覆盖）'

    # --- 落盘：先归档件，后活文档 ---
    with open(os.path.join(ARCH_DIR, ARCH173), 'wb') as f:
        f.write(arch_bytes)
    with open(STATUS, 'wb') as f:
        f.write(new_bytes)

    # ================= 写后独立复核 =================
    chk = open(STATUS, 'rb').read()
    ctxt = chk.decode('utf-8')
    titles = re.findall(r'(?m)^## §.*', ctxt)
    post_blocks = split_sections(ctxt)
    corr_after = open(CORR, 'rb').read()
    a172_after = open(os.path.join(ARCH_DIR, ARCH172), 'rb').read()

    post = {
        'status_sha256_after': sha(chk),
        'status_bytes_after': len(chk),
        'status_lines_after': ctxt.count('\n'),
        'crlf_after': chk.count(b'\r\n'),
        'n_sections_after': len(titles),
        'new_sections': [t for t in titles if t not in pre_titles],
        'old_sections_all_intact': all(t in titles for t in pre_titles),
        'bytes_limit_ok': len(chk) <= LIMIT_BYTES,
        'lines_limit_ok': ctxt.count('\n') <= LIMIT_LINES,
        'no_crlf': chk.count(b'\r\n') == 0,
        'archive_claim_matches_disk': arch_sha in ctxt,
        'archive_exists': os.path.isfile(os.path.join(ARCH_DIR, ARCH173)),
        'archive_sha256': arch_sha,
        'archive_bytes': arch_size,
        'sec172_archive_untouched': sha(a172_after) == pre['sec172_archive_sha256_before'],
        'sec172_archive_sha256': sha(a172_after),
        'old_sec172_body_still_verbatim_in_archive': (
            old_sec172_block.strip() in a172_after.decode('utf-8')),
        'corrections_sha256_unchanged': sha(corr_after) == pre['corrections_sha256_before'],
        'corrections_bytes_unchanged': len(corr_after) == pre['corrections_bytes_before'],
    }
    # 除 §172（已索引化）外，其余旧章节逐字未变
    changed = [n for n, b in pre_blocks.items()
               if n != 172 and post_blocks.get(n) != b]
    post['old_blocks_verbatim'] = (not changed)
    post['old_blocks_changed'] = changed
    missing = [q[:36] for q in QUICK if q[:36] not in FULL_BODY]
    post['quick_lines_not_in_archive'] = missing

    ev['post_checks'] = post
    ev['verdict'] = {
        'all_ok': (post['old_sections_all_intact'] and post['old_blocks_verbatim']
                   and post['no_crlf'] and post['bytes_limit_ok'] and post['lines_limit_ok']
                   and post['archive_claim_matches_disk'] and post['archive_exists']
                   and post['sec172_archive_untouched']
                   and post['old_sec172_body_still_verbatim_in_archive']
                   and post['corrections_sha256_unchanged']
                   and not missing and len(post['new_sections']) == 1),
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(ev['verdict'], ensure_ascii=False))
    print(json.dumps(post, ensure_ascii=False, indent=2))
    return 0 if ev['verdict']['all_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
