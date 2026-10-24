# -*- coding: utf-8 -*-
"""APP §26：STATUS_APP.md 追加 §26 章节 + 改头部 4 个字段 + 「最近更新」插入条目。

🔴 纪律：
  - **只追加**章节到文件末尾（不回头改旧章节）。
  - 头部只改 4 个字段行（last_ack / 更新时间 / 当前任务 / 阻塞）。
  - 用「首个章节锚点」切片：`i_s1` = 第一个 `## §1 ` 的下标，`lines[i_s1:]` 原样保留。
  - 「最近更新」块：新条目插在**最上面**，裁剪回 ≤15 行。
"""
import io
import os
import re
import shutil
import time

P = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
BAK = r'C:\Users\Trekker-PTL\pkg_backup_app014\STATUS_APP.md.pre_app26.bak'

NOW = '2026-10-25 00:45'

HEADER_TASK = (
    '**巡检（无新纠偏条目，第 10 次同一口径）+ 🔴🔴 把「渲染层仍是按段粒度 ⇒ UNIT 收益拿不到」'
    '这件事从「等 review」推进到「有实测数字可裁定」**（MT 通知 4.3 点名的三处 `_mt_of`/`_save_text`/'
    'CLI `run_cli` ⇒ 真实 61 分钟会议语料上**离线量化**：现状一行最多塞 **10 句**、'
    '**7 段**永远没有〔译〕行、**1 个句单元 `seg=None` 取不到译文；候选（按 `mt_units()` 逐句）'
    '每行 1 句、守恒 **41895/41895 OK**、重复句逐次显示，但输出行数 **436 → 1424（3.3×）** ⇒ '
    '**字幕显示粒度属产品行为变更 ⇒ 本轮仍不改，提请 reviewer 裁定**）**：APP-007/008/009/010 已闭环'
    '（`last_ack` = **APP-010**，本轮**无新条目待执行**）⇒ 本轮做「巡检 + 渲染层离线量化 + '
    '交付侧事实复核」；⏳ **交付 zip 仍未重打**（共享机器锁被 MT 持有，PID 16080 实测 exitcode 259 '
    '= 存活 ⇒ 等，**未抢锁**）⇒ **下一轮第一件事：取锁 ⇒ 重打 zip ⇒ `verify_pkg_zip.py` 内容级复核 '
    '⇒ `publish_ftp.py` 重发**'
)

HEADER_BLOCK = (
    '阻塞 / 待用户决定: ① 🔴 **交付 zip 是坏的**：`Confucius4_LiveCaption_v1.4.zip` = 3 513 053 709 B '
    '**非有效 zip**（17:19 写坏，本轮用 EOCD 签名复核：尾 66 KB 内 `PK\\x05\\x06` **找不到**）；'
    '残留 `Confucius4_LiveCaption_v1.4.zip.tmp` = 8 271 022 632 B（21:20，同样无 EOCD ⇒ 也是残包）；'
    '`FTP_Share/` 副本 11 216 038 195 B **EOCD 正常 / 13 978 条目**（完好但过时，09:10，**不含** '
    'APP-008①/APP-010 标注，也不含本轮 §25.1/25.2 的修复）⇒ **下一轮取锁后重打 + 重发**'
    '（§24 已修 `pack_v13.py` 原子写）；② 🔴 **渲染层改按 `mt_units()` 逐句渲染**（MT §4.3 三处）—— '
    '**本轮仍未改**，但已把风险量化成实测数字（现状 1 行 ≤10 句 / 7 段无〔译〕行 / 候选行数 3.3×）'
    '⇒ **等 reviewer 裁定**（§26.6）；③ 🟢 **`shared/GIT_FREEZE` 已释放**（本轮实测 `shared/` 下'
    '**无** FREEZE 文件，MT §60.5 亦确认「冻结已解除」）⇒ §25 头部写的「未释放」**在本节更正**；'
    '④ ⛔ **GitHub 旧 SHA 的 gc** 未做 ⇒ 待用户决定；⑤ ⛔ **APP-009② 的 MT UNIT 方案 A/B/C/D 结论**'
    '仍在 v4 复算（7 臂，本轮观测进度 **3/7**，A_T3 在跑）⇒ 本轮只合入已落码的 3 处缺陷修复；'
    '⑥ ⛔ **v1.4 TTS 音质**未达标（TTS-009/TTS-010）⇒ TTS 保持实验性、默认关闭；'
    '⑦ ⛔ **包体 13 GB** 优化未做。'
)

RECENT = [
    '00:45 §26 🔴🔴 **把「渲染层仍是按段粒度」从「等 review」推进到「有实测数字可裁定」**：'
    '用 MT 已落盘的 v4 **BASE_unit 臂**（真实 61 分钟会议，225 段 / 712 句单元 / chrF 89.7225 / '
    '守恒 41895/41895）**离线复刻**现状渲染与候选渲染 ⇒ 现状 **1 行最多塞 10 句**、**7 段永远没有'
    '〔译〕行**、**1 个句单元 `seg=None`（`flush()` 收尾补翻）现状根本取不到译文**；候选（按 '
    '`mt_units()` 逐句）每行 1 句、守恒 OK、重复句逐次显示（38 次）⇒ 产物 '
    '`results/app/render_units_candidate_eval.json`。',
    '00:45 §26 ⛔ **渲染层三处本轮仍不改**：`_mt_of`/`_save_text`/CLI `run_cli` 改按 `mt_units()` ⇒ '
    '**字幕显示粒度变更属产品行为**（输出行数 436 → 1424，3.3×）⇒ **提请 reviewer 裁定**，'
    '证据已备齐（§26.6），不自行推进。',
    '00:45 §26 ✅ **交付侧事实复核（本轮实测）**：① 三个 zip 的 **EOCD 签名**——主包**坏**（无 '
    '`PK\\x05\\x06`）、`.tmp` 残留**也是坏的**、FTP_Share 副本**结构完好但过时**（13 978 条目）；'
    '② 仓库 ⇄ 客户包三文件（`translator.py`/`live_caption_app.py`/`tts_worker.py`）**仍逐字一致**'
    '（归一化换行）⇒ §25 的同步没被后续改动破坏；③ `shared/GIT_FREEZE` **已释放**（§25 头部的'
    '「未释放」在本节更正）；④ APP-008① 的退回开关 `LIVECAP_GUARD_REL=0` **包内 README 已写明**、'
    '三个相对判据开关（`SIL_REL`/`SPK_REL`/`GUARD_REL`）**包内代码均在**；⑤ APP-010 的 TTS 实验性'
    '标注**包内 README_zh.md L42-44 / L390** 已在。',
    '00:45 §26 ⏳ **交付 zip 仍未重打**：共享机器锁被 MT 持有（`module: mt` / `pid: 16080` / '
    '00:07:24），本轮用 `ctypes` `OpenProcess`+`GetExitCodeProcess` 实测 **exitcode 259 = 存活** ⇒ '
    '等，**未抢锁、未回收**；MT v4 进度观测 **3/7 臂**（BASE_unit ✓ / A_T2 ✓ / A_T3 在跑）⇒ '
    '**未写「已重打」**。',
    '00:45 §26 ✅ **纪律**：**未改/未提交** `status/app/CORRECTIONS_APP.md`（本轮复核 SHA256 仍 '
    '`8ccf661c7f1ef5c…` / 27 413 B / mtime `2026-10-24 17:01:54`）；**未吞** ASR/MT/TTS 的未提交改动；'
    '**未改产品代码**（`live_caption_app.py` 本轮零改动）；**未 import 被测模块**（脚本全走 `ast`/读 JSON）；'
    '**未跑推理/测速/占 GPU**；**未取/未抢/未回收**任何机器锁。',
]

SECTION = """
## §26 巡检（无新纠偏条目，第 10 次同一口径）+ 🔴🔴 渲染层「按段 vs 按句」**实测量化**（提请 reviewer 裁定）+ 交付侧事实复核（2026-10-25 00:45）

### §26.0 巡检结论：无新条目

- `status/app/CORRECTIONS_APP.md`（**只读**，本轮**未改**）：SHA256 `8ccf661c7f1ef5c527871011ed898ae6b9c44855793749105a4461e3f10de8cf`、
  **27 413 B**、mtime `2026-10-24 17:01:54.766142900 +0800`。
- `## APP-xxx` 条目 **10** 条：APP-001 / 002 / 003 / 004 / 005 / 006 / 007 / 008 / 009 / 010（行号 1/27/35/60/77/98/114/134/142/154）。
- `STATUS_APP.md` 头部 `last_ack: APP-010` ⇒ **无编号更大的新条目** ⇒ **本轮不执行任何 APP 条目**，`last_ack` **保持 APP-010** 不变。

### §26.1 🔴🔴 核心发现：渲染层三处的缺口已被**实测量化**（不再只是「等 review」）

§25.8-1 记的是「等 MT v4 复算 + reviewer 裁定」。本轮 **v4 的 BASE_unit 臂已落盘**
（`hy_bench/runs/c111_half/c111_variants_v4_SPE.json`，875 123 B，mtime `2026-10-25 00:33`），
⇒ 渲染层缺口可以**用真实 61 分钟会议语料离线量化**了。

- 🔴 **方法纪律**：**不 import 被测模块**（`import translator` ⇒ 连带 numpy/OpenBLAS ⇒ 内存占满时 import 阶段就 abort）
  ⇒ 两个脚本都**只读 JSON 产物**、**不碰产品代码**、**不跑推理/测速/占 GPU/取锁**。
- 参照臂：`BASE_unit` —— `n_units=712`、`n_formal=712`、`n_translate_calls=674`、`n_final=674`、
  `miss_rate=0.0`、`n_unit_missing=0`、`n_timeout=0`、`src_chars=41895`、`orig_chars=41895`、`src_kept=True`、
  `coverage.coverage_rate=1.0`、`quality.chrf_vs_ref=89.7225`（n=391）。

### §26.2 Q1：`mt_of_seg(seg)` —— 有多少段拿不到任何〔译〕行？

**问题**：UNIT 下「一句原文对一句译文」要靠 `mt_units()`；而 App 现状只用 `mt_of_seg(seg)`。

| 指标（实测） | 值 |
|---|---|
| 语料段数（`product_n_seg`） | **225** |
| 出现在句单元里的**唯一段号** | **218** |
| **没有任何句单元的段** | **7** |
| 其中 `mt_of_seg()` 返回 `None` 的段 | **0**（218 段都有句单元 ⇒ 都有译文） |
| 句单元里 `seg` 为 **`None`** 的 | **1**（来自 `flush()` 收尾补翻，`translator.py` L1130-1150） |

- 🔴 **两个独立的缺口**：
  ① **7 段**：该段原文**整段是半句** ⇒ 它的文字被并入**下一段**的句单元
     ⇒ 该段在 `_save_text()` / `_render()` 里**永远不输出〔译〕行**（现状本来就没这行，UNIT 下会**持续**为空）。
  ② **1 个 `seg=None` 的句单元**：`flush()` 收尾时补翻的末句，`seg` 为 `None`
     ⇒ 现状 `mt_of_seg()`（按段号查）**根本取不到它的译文** ⇒ 这一句在字幕里**没有译文**。
- ⚠️ **但原文没丢**：全部句单元 `src` 拼接 = **41 895** 字 = `orig_chars` **41 895** ⇒ **守恒成立**
  ⇒ 这不是「翻译丢了」，是**渲染层没把跨段合成的句子按句拆出来显示**。

### §26.3 Q2：`_save_text()` 的「原文行 : 〔译〕行」配比 —— 现状一行塞多少句？

| 指标（实测） | 现状（按段） | 候选（按句单元） |
|---|---|---|
| 原文行数 | **218** | **712** |
| 〔译〕行数 | **218** | **712** |
| 无译文的行 | 0 | 0（待译单元显示「译文生成中…」） |
| **一行里最多的句数** | **10** | **1** |
| 句数/行分布（现状） | 1句×23 / 2句×62 / 3句×54 / 4句×51 / 5句×17 / 6句×6 / 7句×2 / 8句×1 / 9句×1 / **10句×1** | — |
| **输出总行数** | **436** | **1424（3.3×）** |
| 原文守恒（去空白口径） | — | **41 895 / 41 895 OK** |

- ⇒ **结论**：现状**拿不到** UNIT 的收益（MT 通知 4.3 的核心诉求）；候选能做到「每行 1 句」。
- ⚠️ **代价**：输出行数 **436 → 1424（3.3×）** ⇒ 屏幕字幕会明显变长 ⇒ **属产品行为变更**。

### §26.4 Q3/Q4：屏幕字幕 overlay 与 TTS 链

- **overlay**（`live_caption_app.py` L2499-2502，取「最近 3 段的译文」）：实测最近 3 段（221/222/223）**都有译文** ⇒ 该处**当前无缺口**。
- **TTS 链**：`outbox` 实测是**三元列表** `[kind, src, mt]`，`kind_counter = {'final': 674}`、**非 final = 0**
  ⇒ 「要朗读的译文必须以 `'final'` 出 outbox」**成立**（`live_caption_app.py` L2314 只提交 `kind == 'final'`）。

### §26.5 🔴 重复句：「翻译去重」≠「显示去重」—— 候选实现必须逐次显示

| 指标（实测） | 值 |
|---|---|
| 唯一 `src` 数 | **674** |
| 句单元数（= 显示次数） | **712** |
| 出现过 >1 次的 `src` | **14** |
| **因重复而多出的显示次数** | **38** |
| 同一句最多重复 | **9** 次（`"three, three, three, …"`） |
| 候选实现是否逐次显示 | **是（`candidate_shows_every_occurrence = true`）** |

- 🔴 **产品行为问题（本轮只报不改）**：翻译调用 **674** 条 `final` ⇒ 重复句**只朗读一次**；
  但字幕**显示 712 次** ⇒ **「字幕说两遍、语音只播一遍」**。
  ⇒ 这正是 MEMORY 铁律「翻译去重 ≠ 显示去重」的另一面：**省了调用，但朗读次数也少了** ⇒ **需 reviewer 裁定**
  （可选：① 朗读也逐次；② 字幕按句但重复句标注；③ 保持现状）。

### §26.6 ⛔ 本轮**不改**渲染层三处 —— 提请 reviewer 裁定（含证据清单）

- **待改的三处**（MT 移交说明 §4.3 表）：
  | 位置 | 现状 | UNIT 下应改为 |
  |---|---|---|
  | `live_caption_app.py` L2334-2336 `_mt_of(seg)` | `return self.mt.mt_of_seg(seg)` | 按 `mt_units()` 过滤 `seg == i` |
  | L2395-2410 `_save_text()` | 按 `self.blocks`（ASR 段）逐段渲染 | 按 `mt_units()` 逐单元渲染 |
  | L2790-2799 CLI `run_cli()` | `m = mt.mt_of_seg(i)` | 同上 |
- **本轮不改的三条理由**：
  ① **属产品行为变更**（字幕显示粒度：1 行 ≤10 句 → 每行 1 句；总行数 3.3×）⇒ 需 reviewer 裁定；
  ② **MT v4 的 A/B/C/D 方案结论尚未出齐**（7 臂，本轮观测 3/7）⇒ UNIT 方案本身还没最终定案；
  ③ **本轮 MT 正持共享机器锁**（PID 16080 存活）⇒ 不在同机抢资源做重活。
- **给 reviewer 的证据清单**（全部已落盘，可直接复核）：
  | 产物 | 字节 | 内容 |
  |---|---|---|
  | `results/app/diag_render_layer_units.py` | — | Q1/Q2/Q3/Q4 的离线量化脚本（只读 JSON） |
  | `results/app/render_layer_units_diag.json` | 6 218 B | Q1–Q4 原始字段 |
  | `results/app/test_render_units_candidate.py` | — | 现状 vs 候选的**逐项对比**脚本 |
  | `results/app/render_units_candidate_eval.json` | 3 873 B | 对比结论（行数 / 守恒 / 重复句 / TTS 差异） |
- **裁定时建议回答的三问**：
  ① 字幕从「按 ASR 段」改成「按完整句」是否可接受？（行数 3.3×）
  ② 重复句「字幕显示 2 次 / 语音播 1 次」是否接受？还是要朗读也逐次？
  ③ `flush()` 补翻的那 1 个 `seg=None` 句单元，字幕上挂在**最后一段**还是单列一行？

### §26.7 ✅ 交付侧事实复核（本轮实测，均为**读操作**，未改任何交付物）

| # | 核查项 | 实测结果 |
|---|---|---|
| 1 | `Confucius4_LiveCaption_v1.4.zip`（3 513 053 709 B，17:19） | 🔴 **坏**：尾 66 KB 内**找不到** `PK\\x05\\x06`（EOCD）⇒ 截断 |
| 2 | `Confucius4_LiveCaption_v1.4.zip.tmp`（8 271 022 632 B，21:20） | 🔴 **也是残包**（同样无 EOCD）⇒ 是上次中断留下的，**不是**可用包 |
| 3 | `FTP_Share/Confucius4_LiveCaption_v1.4.zip`（11 216 038 195 B，09:10） | 🟡 **结构完好**（EOCD 正常 / **13 978** 条目）但**过时**（不含 APP-008①/APP-010 标注、不含 §25.1/25.2 修复） |
| 4 | 仓库 ⇄ 客户包三文件一致性 | ✅ **仍逐字一致**（归一化换行）：`translator.py` `11deb2b6…` 69 519 B ｜ `live_caption_app.py` `47357762…` 157 641 B ｜ `tts_worker.py` `3c78cce8…` 41 109 B ⇒ §25 的同步**未被后续改动破坏** |
| 5 | `shared/GIT_FREEZE` | 🟢 **已释放**（`shared/` 下**无**该文件；MT §60.5 亦确认「冻结已解除」）⇒ **更正** §25 头部「未释放」的记述（**不改** §25 原文，只在本节说明） |
| 6 | APP-008① 要求的**退回开关** | ✅ 包内 README_zh.md L394 已写明 `LIVECAP_GUARD_REL=0`；包内 `app/live_caption_app.py` L175/192/256 三个相对判据开关（`SIL_REL`/`SPK_REL`/`GUARD_REL`）**均在** |
| 7 | APP-010 的 TTS「实验性 / 默认关闭」 | ✅ 包内 README_zh.md L42-44 + L390 已在 |
| 8 | `pack_v13.py` 是否持机器锁 | ✅ 已持（`machine_lock_app.LockHeld(module='app-pack', timeout=3600)`，L490）；`--dry-run` 刻意**不持锁**（只读统计） |

### §26.8 ⏳ 本轮**未做**的事（边界）

- 🔴 **未重打交付 zip**：共享机器锁被 MT 持有（`module: mt` / `pid: 16080` / `started: 2026-10-25 00:07:24`），
  本轮用 `ctypes` `OpenProcess(SYNCHRONIZE)` + `GetExitCodeProcess` 实测 **exitcode = 259（STILL_ACTIVE）= 存活**
  ⇒ **等，不抢锁、不回收**。MT v4 进度观测：**3/7 臂**（BASE_unit ✓ / A_T2 ✓ / A_T3 在跑）。
  ⇒ **未写「已重打」**（没落盘的东西不能写「已交付」）。
- 🔴 **未改**渲染层三处（§26.6）—— 等 reviewer 裁定。
- 🔴 **未改** `status/app/CORRECTIONS_APP.md`（只读）。
- 🔴 **未改**产品代码（`live_caption/live_caption_app.py` / `translator.py` 本轮**零改动**）。
- ⛔ **未做** GitHub 旧 SHA gc（待用户决定）；⛔ **未做** 包体 13 GB 优化；⛔ **未开** FTP（APP-009③）。
- 🔴 **未**跑推理 / 测速 / 占 GPU；🔴 **未取/未抢/未回收**任何机器锁；🔴 **未 import 被测模块**。

### §26.9 本轮落盘产物（附字节 / mtime / SHA256）

| 文件 | 字节 | mtime | 说明 |
|---|---|---|---|
| `results/app/diag_render_layer_units.py` | 新增 | 2026-10-25 00:42 | Q1–Q4 离线量化（只读 JSON，不 import 被测模块） |
| `results/app/render_layer_units_diag.json` | **6 218 B** | 2026-10-25 00:43 | Q1–Q4 原始字段 |
| `results/app/test_render_units_candidate.py` | 新增 | 2026-10-25 00:44 | 现状 vs 候选逐项对比 |
| `results/app/render_units_candidate_eval.json` | **3 873 B** | 2026-10-25 00:44 | 对比结论 |
| `results/app/_lock_probe.py` | 新增 | 2026-10-25 00:39 | ctypes fail-closed 判活探针 |

**ack: APP-010**（本轮**无新条目**；巡检口径第 10 次一致；渲染层缺口已实测量化并**提请 reviewer 裁定**，
未自行改动产品行为；交付 zip **未重打**（等锁）；`GIT_FREEZE` 已释放的事实已在 §26.7 更正）
"""


def main():
    with io.open(P, encoding='utf-8', newline='') as f:
        text = f.read()
    lines = text.split('\n')

    # ---- 定位首个章节锚点 ----
    i_s1 = None
    for i, ln in enumerate(lines):
        if ln.startswith('## §1 '):
            i_s1 = i
            break
    if i_s1 is None:
        raise SystemExit('找不到首个章节锚点 ## §1')
    head = lines[:i_s1]
    body = lines[i_s1:]           # 原样保留

    # ---- 头部 4 字段 ----
    def set_field(head, key, value):
        pat = re.compile(r'^(%s:\s*).*$' % re.escape(key), re.M)
        found = False
        for i, ln in enumerate(head):
            if ln.startswith(key + ':'):
                head[i] = '%s%s' % (key + ': ', value)
                found = True
                break
        if not found:
            raise SystemExit('头部字段未找到: ' + key)
        return head

    head = set_field(head, 'last_ack', 'APP-010')
    head = set_field(head, '更新时间', NOW)
    head = set_field(head, '当前任务', HEADER_TASK)
    head = set_field(head, '阻塞 / 待用户决定', HEADER_BLOCK)

    # ---- 「最近更新」块：新条目插最上面 + 裁剪 ≤15 行 ----
    i_rec = None
    for i, ln in enumerate(head):
        if ln.strip() == '## 最近更新':
            i_rec = i
            break
    if i_rec is None:
        raise SystemExit('找不到「## 最近更新」块')
    j = i_rec + 1
    while j < len(head) and head[j].strip() != '':
        j += 1
    old_items = [ln for ln in head[i_rec + 1:j] if ln.strip()]
    new_items = ['- ' + s for s in RECENT]
    merged = (new_items + old_items)[:15]
    head = head[:i_rec + 1] + merged + head[j:]

    # ---- 追加 §26 到末尾 ----
    out_lines = head + body
    while out_lines and out_lines[-1].strip() == '':
        out_lines.pop()
    out_lines.append('')
    out_lines.extend(SECTION.strip('\n').split('\n'))
    out_lines.append('')
    new_text = '\n'.join(out_lines)

    os.makedirs(os.path.dirname(BAK), exist_ok=True)
    shutil.copy2(P, BAK)
    with io.open(P, 'w', encoding='utf-8', newline='') as f:
        f.write(new_text)

    print('backup:', BAK, os.path.getsize(BAK), 'B')
    print('written:', P, os.path.getsize(P), 'B')
    print('sections (grep -c "^## §"):', sum(1 for ln in new_text.split('\n') if ln.startswith('## §')))
    print('tail:', new_text.split('\n')[-3:])


if __name__ == '__main__':
    main()
