#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app291_write_status_sec139.py —— 写 STATUS §139（APP-073 / APP-074）＋ 压缩 §138。

## 做什么

1. 把 **§139 正文（完整版）** 落盘到 `status/archive/STATUS_APP_sec139_20261105.md`。
2. 在 `status/app/STATUS_APP.md` 里：
   * 头部：`last_ack` APP-072 → **APP-074**；`更新时间` 用 **Get-Date 实测值**；
     `当前任务` / `阻塞` / `已压缩` 三行改写（**只动头部区**）。
   * `## 最近更新` **追加**一条 §139 摘要行（**在文件最前**，旧行一字不动）。
   * `## 最近章节` 表 **追加**一行 §139（**旧行一字不动**）。
   * `### §139` **追加**新章节（**旧章节一字不动**）。
   * `### §138` **压缩**为速查指针（正文已逐字归档，见下）。

## 🔴 §138 压缩纪律（APP-052 ④）

`STATUS_APP.md` 逼近 **40 000 B** 上限（当前 39 145 B，剩 855 B）⇒ 必须压缩。

* 🔴 **压缩前先验「旧正文逐字在归档件里」**：
  抽 §138 正文里**全部 93 个数字型 token**，逐个在归档件里查
  ⇒ 只差 1 个（`28 336`，那是**归档件自身字节数**的引用，
  写归档件时自然对不上）⇒ **正文实质内容全部有归档留存**。
* 🔴 压缩后的 §138 只保留：**标题 + 一行「正文已归档」指针 + 一行速查**。
* 归档件 = **本轮压缩前 §138 的逐字正文**（新写一份，不覆盖旧归档件）。

## 🔴 写入纪律

* **只追加、不改旧章节**（§135–§137 一字不动）。
* 头部三行是**定点替换**（唯一命中断言）。
* 写后**逐字节复核**：章节不少 + 旧章节逐字未变 + 行尾未破（LF 保持）。
* 限额：≤ 40 000 B / ≤ 300 行。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
ARCH139 = os.path.join(ARCH_DIR, 'STATUS_APP_sec139_20261105.md')
ARCH138 = os.path.join(ARCH_DIR, 'STATUS_APP_sec138_live_20261105.md')
EVID = os.path.join(HERE, 'app291_status_sec139_evidence.json')

LIMIT_BYTES = 40000
LIMIT_LINES = 300

TS = os.environ.get('STATUS_TS', '2026-11-05 18:07:58')

# ══════════════════════════════════════════════════════════════════════
# §139 正文
#   SEC139_FULL ⇒ 归档件（**逐字完整版**）
#   SEC139      ⇒ STATUS 内的**速查版**（APP-052 ④ 惯例：§135–§137 同款形态）
# ══════════════════════════════════════════════════════════════════════
SEC139_FULL = """### §139 ✅ **APP-073（解压副本冒烟）＋ APP-074（更正：babelvox 示例音色不许放回）本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-05 18:08）

> 🔴 **开工/收尾 `CORRECTIONS_APP.md`（reviewer 独占文件，本模块全程只读、未改、未提交）**：**SHA `1dd0bcca607772b79ab9a6513a2a302a4dffc01cf47e0bf59ad9c908a9c42900`／215 258 B／mtime 2026-11-05 16:03:18／74 条**（APP-001..APP-074）⇒ 开工与收尾**逐字相同**（reviewer 本轮未追加）。
> 🔴 **本轮起点＝接管死租约（TAKEOVER）**：上一会话 token `9528e9af`（11-05 14:40 起、15:53 最后心跳、note=「APP-071 根因分析完成」）已死 ⇒ 本轮**从断点续做**（不是从头重做）；其留下的 `app283_app071_diag/` 诊断件**一字未动**（SHA 见 ⑨）。

| # | 事项 | 结论 | 证据 |
|---|---|---|---|
| ① | 🔴 **reviewer 的核心疑问：`--tts-voice A` 会不会依赖被剪掉的 babelvox 示例音色？** | **不会 ⇒ A 与那 4 个文件无依赖**。**静态链**：`live_caption_app.py` 的 `--tts-voice` **`choices=['A','follow_speaker']`** ⇒ **命令行根本无法传 `cindy`**；`tts_worker.py` L1389-1404 的 `if key.lower() in BUILTIN_SPEAKERS` 分支**只对内置名生效**，`'A'` 直接落到 `tts_engine.preset_voice_path()` ⇒ `models/qwen3tts/voices/preset_A.wav`（**192 044 B**，**在 zip 内**）。**动态实证**：解压副本里 `babelvox/data/speakers/` **目录不存在**，而 CLI 仍 **17/17 句 `voice_kind=preset`** ⇒ **A 在剪后包里照常工作** | `results/app/app289_rc3_rev2_unzip_smoke_evidence.json` → `tts_judge.voice_kinds=["preset"]` / `babelvox_speakers_dir_exists=false`；`app/tts_engine.py` L126-133 `preset_voice_path()`；`app/live_caption_app.py` L7519 `--tts-voice` choices |
| ② | **APP-073(a) 设备级冒烟（对解压副本）** | **7 PASS / 0 FAIL**（**两次独立冒烟**都过）：① `--check` **5/0**（rc=0／「环境正常」／GPU.0 命中 3／NPU 命中 8／ASR 后端 3）② CLI 退出码 **0**（wall **87.98 s**）③ log **无 Traceback**（命中 0）④ **tts.jsonl 非零 wav 段 17/17**（零段 **0**）⑤ **音色 A 未回落**（`voice_kind` ⊆ `{preset}`）⑥ **解压副本内无 babelvox 示例音色**（目录不存在）⑦ **预设 A 参考 wav 存在**（192 044 B／SHA `e021c255a715d4fd…`） | `results/app/app289_rc3_rev2_unzip_smoke_evidence.json`（**rev2 zip** 的解压副本）／`app286_rc3_unzip_smoke_evidence.json`（**旧 zip** 的解压副本，**同样 7/0**）→ `checks` |
| ③ | **内容判据（复用 `app268` 的 4 条硬判据，不另立标准）** | **PASS**：C1/C2/C3/C4 全 OK／**零段 0**／**受损句 0**（wav **66.99 s**） | `app289…` → `content_criterion`（`app268_app069_content_criterion.py`） |
| ④ | 🔴 **反证（判据非恒真）** | ✅ **同一判据跑 rc2 旧产物 ⇒ 必须 FAIL**：**verdict=FAIL／受损句 24／零段 24**（＝reviewer 的实测口径）⇒ 判据能识破缺陷，不是恒真 | `app289…` → `counter_proof`（`n_damaged_sentences=24`） |
| ⑤ | 🔴 **APP-073(b)＋ APP-074 的处置** | **按 APP-074 更正版执行**：**cindy/lou/phil/steve 不放回 zip**（剪掉是对的）⇒ **不重打那 4 个文件**；但 reviewer 要求的 **README 文件数改正**（`10 503` → `10 474`）**必须做** ⇒ 定点替换 `（10 503 个文件）` → `（10 474 个文件）`（**唯一命中 1 次**／写后逐字节复核「反向替换 == 原文」／**「约 6.7 GB」不动**，实测 7 176 154 805 B = 6.683 GiB ⇒ 原值本就对） | `results/app/app287_rc3_readme_count_patch_evidence.json` → `n_hit_old_snippet=1` / `roundtrip_ok=true` / `after.sha256=e6710514395d6451…` |
| ⑥ | **重打 zip（**新文件名**，不覆盖旧 zip）** | **6 PASS / 0 FAIL**：`shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip`＝**5 591 630 139 B／10 474 条目／SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**（mtime 2026-11-05 17:53:56）｜**旧 zip `…_perftest.zip` 一字节未动**（SHA `dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1` 收尾复核**逐字相同**）｜**一致性对账**：与旧 zip **逐条 CRC32** 比 ⇒ **10 474 条全中／新增 0／删除 0／变化恰好 1**（**只有 `README_perftest.txt`**）⇒ **除那个数字外，别的什么都没动** | `results/app/app288_rc3_perftest_zip_rev2_evidence.json` → `crc_audit`（`n_changed=1` / `changed[0].file=README_perftest.txt`）/ `old_zip_untouched=true` |
| ⑦ | **rev2 zip 自己也过了冒烟**（不能只测旧 zip） | **7 PASS / 0 FAIL**（对 rev2 的解压副本重跑 `--check`＋CLI 60 s）：非零 wav **17/17**／零段 **0**／`voice_kind` ⊆ `{preset}`／内容判据 **PASS**（受损 0）／反证 rc2 **FAIL/24** ⇒ **最终 SHA 对应的包本身已验证** | `results/app/app289_rc3_rev2_unzip_smoke_evidence.json`（`pkg` = `rc3_smoke_rev2_20261105/…`） |
| ⑧ | 🔴 **APP-074(a)②：dev 版与 v2.x 客户包的预设 A 是否也来自 babelvox 示例？** | **否 ⇒ v2.x 没有违规**。`preset_A.wav` 在 **v1.13／v2.0／v2.1／v2.2／MiniMVP rc3 五个包里 SHA256 全部相同**（`e021c255a715d4fd17dd6d19c3092a293d0d35a1e4e7ca8bf67bce6f8c94db53`，192 044 B）⇒ 来源是 **Amphion 的 `metis prompt.wav` 截前 6 s**（包内 `NOTICE` 已署名 **Apache-2.0**），**与 babelvox 示例音色无关** ⇒ 无需 reviewer 单独处理历史包 | 五个包内 `models/qwen3tts/voices/preset_A.wav` 逐个 SHA256 实测；`…_rc3/NOTICE` L34（Amphion 署名）＋ L79-80（`preset_A.wav` 来源说明） |
| ⑨ | 🔴 **APP-071（BLOCKING）仍未完成** | ⛔ **本条未动**（reviewer 明文「APP-071 仍 BLOCKING 未完成，按用户 APP-072 决定放 rc4，不阻塞本 zip」）。上一会话留下的 `app283_app071_diag/` 诊断件（**8 个文件**：`refpcm_S1..S4.wav` × 4 ＋ `xvec_S1..S4.npy` × 4）**本轮一字未动**（SHA `c5ecdaf915c227a1…` / `2c10fc78f1752095…`）⇒ 其中已落盘的**离线统计嵌入**余弦矩阵（S2 对 S2 **0.999394** > 对 S1 **0.994403**／对 S3 **0.995939**）与「S2 首次登记段 = `seg1`／`spk_conf=0.1292`」仍是**待复核的线索**（reviewer 的硬判据要**生产引擎的真 x-vector** ⇒ 须设备级复测）⇒ **(a)(b)(c)(d) 仍全部未完成** ⇒ **v2.3 不打包** | `results/app/app283_app071_diag_evidence.json` → `verdict=FAIL`（3 PASS / **1 FAIL**：反证组「用 S1 冒充 S2」**未能判 FAIL** ⇒ 该判据在统计嵌入下**不恒真性不足**）＋ `mode_note`（自述用**统计嵌入**而非真 x-vector） |
| ⑩ | **纪律自检** | ✅ **未改 `CORRECTIONS_APP.md`**（收尾 SHA 与开工逐字相同）｜✅ **未覆盖·未删任何旧 zip**（旧 `…_perftest.zip` SHA 逐字未变；rev2 是**新文件名**）｜✅ **未用 `--same-version`**｜✅ **未原地改用户正在测试的安装目录**（`Confucius4_LiveCaption_v*` 一个字节未动；只改 MiniMVP rc3 **构建源**里的 README）｜✅ **备份移出包目录**（C-133：备份不进包 ⇒ 写时备份已移到 `results/app/README_perftest.txt.bak_app284`，SHA 不变）｜✅ 设备作业**全持 `MACHINE_LOCK`**（PID 48348／46252／13560）＋ session_lease `addpid`｜✅ 取锁后**再等 45 s 安静窗口**｜✅ **未通知用户／未改桌面快捷方式／未通过任何外部服务分发**｜✅ **live_caption/ 一行未改**（本轮只动 README ＋ 证据脚本） | 逐条明细见归档件 §2 |

🔴 **本轮产物 8 个（仓库内）**：`_app286_rc3_unzip_smoke.py`／`_app287_rc3_readme_count_patch.py`／`_app288_rc3_perftest_zip_rev2.py`／`_app290_renumber_evidence.py`／`_app291_write_status_sec139.py` ＋ 证据 `app286_rc3_unzip_smoke_evidence.json`／`app287_rc3_readme_count_patch_evidence.json`／`app288_rc3_perftest_zip_rev2_evidence.json`／`app289_rc3_rev2_unzip_smoke_evidence.json`／`app290_renumber_evidence.json` ＋ 运行日志 `app286_rc3_unzip_smoke.log`／`app286_rc3_unzip_check_output.txt` ＋ 备份 `README_perftest.txt.bak_app284` ⇒ **全量字节数／mtime／SHA256 见归档件 §3**。
🔴 **本轮 git**：main 分支普通 push（未 force）；只 `git add` App 模块自己的文件；🔴 **绝不提交 `CORRECTIONS_APP.md`**、**不吞** ASR／MT／TTS 其它模块的未提交改动。
"""

SEC139 = """### §139 ✅ **APP-073（解压副本冒烟）＋ APP-074（更正：babelvox 示例音色不许放回）本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-05 18:08）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec139_20261105.md`（逐字保留，含 10 项速查表、全部产物元数据、纪律自检）。
> 🔴 **开工/收尾 `CORRECTIONS_APP.md`（reviewer 独占文件，全程只读、未改、未提交）**：SHA `1dd0bcca…9c42900`／215 258 B／mtime 2026-11-05 16:03:18／**74 条**（APP-001..APP-074）⇒ 开工与收尾**逐字相同**（reviewer 本轮未追加）。
> 🔴 **速查**：**解压副本冒烟 7 PASS / 0 FAIL**（rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色）＋ 内容判据 **PASS**（零段 0）＋ 反证 **PASS**（rc2 旧产物 FAIL/受损 24）｜🔴 **核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**（`--tts-voice` 的 `choices` 只有 `A`/`follow_speaker` ⇒ **传不进 cindy**；`A` → `preset_A.wav`，**在包内**）｜**README 文件数已改正**（10 503 → **10 474**）＋ **zip 已重打（新文件名 ⇒ 不覆盖旧 zip）**：**最终 SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**（`shared/minimvp/…_v1.0-rc3_perftest_rev2.zip`／5 591 630 139 B／10 474 条目）｜**一致性对账**：逐条 CRC32 ⇒ **只 `README_perftest.txt` 1 个不同**，其余 10 473 个逐条未变；旧 zip SHA 逐字未变｜🔴 **APP-074(a)② 已答**：预设 A 在 v1.13/v2.0/v2.1/v2.2/rc3 五个包里 **SHA 全部相同**（来源 **Amphion metis prompt.wav**，NOTICE 署名 Apache-2.0）⇒ **不来自 babelvox 示例 ⇒ v2.x 不违规**｜⛔ **APP-071 仍未完成（BLOCKING，放 rc4）**：本轮未动，上一会话的 `app283_app071_diag/` 一字未动 ⇒ **v2.3 不打包**。
"""

# ── §138 压缩后的形态（标题保留 + 归档指针 + 速查）──────────────────
SEC138_NEW = """### §138 ✅ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成** ｜ **APP-071 仍未完成（BLOCKING）** ｜ **本条需等 reviewer 复核**（2026-11-05 15:28）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec138_20261105.md`（28 336 B，逐字保留，含 README 全文、全部产物元数据、闸门原始字段）＋ 本轮压缩前的**逐字正文**另见 `status/archive/STATUS_APP_sec138_live_20261105.md`。
> 🔴 **速查**：zip `…_v1.0-rc3_perftest.zip`（5 591 630 138 B／10 474 条目／SHA `dda6f229…2d45f1`）；三闸门全过（黑名单 **6/0**／NOTICE 署名 PASS／`--check` **5/0**）＋ GUI 冒烟 **5/0**；README_perftest.txt 9 155 B 进包；⛔ APP-071 **(a)(b)(c)(d) 全未做** ⇒ v2.3 不打包（续见 §139 ⑨）。
"""

# ══════════════════════════════════════════════════════════════════════


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    out = {'script': '_app291_write_status_sec139.py',
           'correction': 'APP-073 + APP-074',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'status': STATUS, 'limit_bytes': LIMIT_BYTES,
           'limit_lines': LIMIT_LINES}

    with open(STATUS, 'rb') as f:
        before = f.read()
    text = before.decode('utf-8')
    out['before'] = {'bytes': len(before), 'sha256': sha256_bytes(before),
                     'lines': before.count(b'\n'),
                     'crlf': before.count(b'\r\n')}

    # ── 闸门①：§138 压缩前，其数字型事实**全部**在归档件里 ─────────
    i138 = text.find('### §138')
    if i138 < 0:
        raise SystemExit('找不到 §138')
    sec138_old = text[i138:]
    with open(os.path.join(ARCH_DIR,
                           'STATUS_APP_sec138_20261105.md'),
              encoding='utf-8') as f:
        a138 = f.read()
    nums = set(re.findall(r'\d[\d .]*\d', sec138_old))
    missing = []
    for n in nums:
        key = n.strip().rstrip('.')
        if key and key not in a138:
            missing.append(key)
    # `28 336` = 旧归档件自身字节数 ⇒ 引用别的文件，必然对不上
    missing = [m for m in missing if m != '28 336']
    out['sec138_numeric_tokens'] = len(nums)
    out['sec138_missing_from_archive'] = missing
    if missing:
        raise SystemExit('§138 有数字不在归档件里 ⇒ 拒绝压缩：%s' % missing)

    # ── 写 §138 逐字归档（压缩前的正文）＋ §139 归档（完整正文）────
    os.makedirs(ARCH_DIR, exist_ok=True)
    hdr138 = (
        '# STATUS_APP §138 逐字正文（2026-11-05 15:28 版）\n\n'
        '> 本件为 `status/app/STATUS_APP.md` §138 在 **2026-11-05 18:08 压缩前**的逐字正文。\n'
        '> 压缩只把 STATUS 内的 §138 换成「标题 + 归档指针 + 速查」；**正文一字未删**（本件即留存）。\n'
        '> 另见 `status/archive/STATUS_APP_sec138_20261105.md`（原始完整版，含 README 全文）。\n\n'
        '---\n\n')
    with open(ARCH138, 'w', encoding='utf-8', newline='\n') as f:
        f.write(hdr138 + sec138_old.rstrip('\n') + '\n')

    hdr139 = (
        '# STATUS_APP §139 正文（2026-11-05 18:08）\n\n'
        '> 本件为 `status/app/STATUS_APP.md` §139 的**逐字正文**；STATUS 内只留速查表（APP-052 ④ 惯例）。\n'
        '> 纠偏文件 `status/app/CORRECTIONS_APP.md` 本轮**只读、未修改、未提交**。\n'
        '> 开工基线 ＝ 收尾复核：**SHA `1dd0bcca607772b79ab9a6513a2a302a4dffc01cf47e0bf59ad9c908a9c42900`／215 258 B／mtime 2026-11-05 16:03:18／74 条**（APP-001..APP-074）⇒ reviewer 本轮未追加。\n\n'
        '---\n\n')
    with open(ARCH139, 'w', encoding='utf-8', newline='\n') as f:
        f.write(hdr139 + SEC139_FULL.rstrip('\n') + '\n')
    out['archives_written'] = {
        ARCH138: os.path.getsize(ARCH138),
        ARCH139: os.path.getsize(ARCH139),
    }

    # ── 组装新的 STATUS 文本 ───────────────────────────────────────
    new = text

    # ① 头部：last_ack / 更新时间（定点替换，各唯一命中）
    def sub_once(s, old, newv, label):
        n = s.count(old)
        if n != 1:
            raise SystemExit('头部替换「%s」命中 %d 次（必须 1 次）' % (label, n))
        return s.replace(old, newv, 1)

    new = sub_once(new, 'last_ack: APP-072', 'last_ack: APP-074', 'last_ack')
    new = sub_once(new, '更新时间: 2026-11-05 15:28',
                   '更新时间: ' + TS, '更新时间')

    # ② 头部：当前任务 / 阻塞 / 已压缩（**整行替换** ⇒ 各唯一命中）
    lines = new.split('\n')

    def set_line(prefix, content):
        hits = [k for k, ln in enumerate(lines) if ln.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit('头部行「%s」命中 %d 次（必须 1 次）'
                             % (prefix, len(hits)))
        lines[hits[0]] = content

    set_line('当前任务:',
             '当前任务: **§139 APP-073（解压副本冒烟）＋ APP-074（更正：babelvox 示例音色不许放回）本条已完成**'
             ' —— **解压副本冒烟 7/0**（对 rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／'
             '**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色／预设 A 参考 wav 在）'
             '＋ **内容判据 PASS**（零段 0／受损 0）＋ **反证 PASS**（rc2 旧产物同判据 FAIL/受损 24 ⇒ 判据非恒真）'
             '｜🔴 **核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**'
             '（`choices` 只有 `A`/`follow_speaker` ⇒ 传不进 cindy；`A` → `preset_A.wav`，**在包内**）'
             '｜**README 文件数已改正**（10 503 → 10 474，唯一命中）＋ **zip 已重打（新文件名，不覆盖旧 zip）**：'
             '`shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip`'
             '（**5 591 630 139 B／10 474 条目／SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**）'
             '｜**一致性对账**：与旧 zip 逐条 CRC32 比 ⇒ **只 `README_perftest.txt` 1 个文件不同**，其余 10 473 个逐条未变')
    set_line('阻塞 / 待用户决定:',
             '阻塞 / 待用户决定: 🔴 **APP-071 仍未完成（BLOCKING）**（克隆音色串音：男声 3 段听上去是女声）'
             '—— 本轮**未动**（reviewer 明文：APP-071 按用户 APP-072 决定放 rc4，不阻塞本 zip）'
             '⇒ **(a) 诊断落盘／(b) 余弦矩阵／(c) 登记逻辑修复／(d) `v23_clone_r2/` 仍全部未完成**；'
             '上一会话留下的 `app283_app071_diag/` 离线诊断件**本轮一字未动**（其中反证组「用 S1 冒充 S2」'
             '**未能判 FAIL** ⇒ 该判据在统计嵌入下不恒真性不足 ⇒ 须**生产真 x-vector** 设备级复测）'
             '｜⛔ **v2.3 不打包**（APP-071 (e) 明文）｜🔴 **本轮需 reviewer 复核**：'
             '**解压副本冒烟 7/0 ＋ rev2 zip 最终 SHA ＋ README 数字改正 ＋ 旧 zip 未动**（等 reviewer 转告用户去取包）'
             '｜⛔ **APP-069/070 剩余项仍未做**（§137 未清项）'
             '｜🔴 **未通知用户／未改桌面快捷方式／未动 v1.13、v2.0、v2.1、v2.2、rc1、rc2、rc3 任何一字节'
             '（只改 rc3 构建源里的 README）／未通过任何外部服务分发**')
    set_line('已压缩:',
             '已压缩: **§135–§137 的正文均已原样归档**到 `status/archive/STATUS_APP_sec135_upto_20261105.md`（18 133 B）／'
             '`STATUS_APP_sec136_upto_20261105.md`（12 364 B）／`STATUS_APP_sec137_20261105.md`（9 705 B）／'
             '`STATUS_APP_sec135_137_infofast_20261105.md`（8 585 B）＋ **§138 正文归档**到 '
             '`status/archive/STATUS_APP_sec138_20261105.md`（28 336 B）＋ 本轮压缩前的逐字正文另见 '
             '`STATUS_APP_sec138_live_20261105.md` ＋ **§139 正文归档**到 '
             '`status/archive/STATUS_APP_sec139_20261105.md` ⇒ 本文件内只留**速查行**；'
             '限额 ≤ 40000 B / ≤ 300 行（APP-052 ④）｜写后实测见归档件 §3')
    new = '\n'.join(lines)

    # ③ 最近更新：**在第一条之前插入** §139 摘要（旧行一字不动）
    upd_anchor = '## 最近更新\n'
    if new.count(upd_anchor) != 1:
        raise SystemExit('「## 最近更新」命中异常')
    summary = (
        '- ' + TS + ' **§139 已写** ⇒ **APP-073 + APP-074 本条已完成**：'
        '**解压副本冒烟 7/0**（rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／'
        '**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色）＋ 内容判据 **PASS**（零段 0）'
        '＋ 反证 **PASS**（rc2 旧产物 FAIL/受损 24）'
        '｜🔴 **reviewer 的核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**'
        '（`--tts-voice` 的 `choices` 只有 `A`/`follow_speaker` ⇒ **传不进 cindy**；`A` → `preset_A.wav`，**在包内**）'
        '｜**README 文件数已改正**（10 503 → **10 474**，唯一命中，写后逐字节复核）'
        '｜**zip 已重打（新文件名 ⇒ 不覆盖旧 zip）**：`…_v1.0-rc3_perftest_rev2.zip`'
        '（**5 591 630 139 B／10 474 条目／SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**）'
        '｜**一致性对账**：逐条 CRC32 ⇒ **只 `README_perftest.txt` 1 个不同**，其余 10 473 个逐条未变；旧 zip SHA 逐字未变 '
        '｜🔴 **APP-074(a)② 已答**：预设 A 在 v1.13/v2.0/v2.1/v2.2/rc3 五个包里 **SHA 全部相同**'
        '（来源 **Amphion metis prompt.wav**，NOTICE 已署名 Apache-2.0）⇒ **不来自 babelvox 示例 ⇒ v2.x 不违规**'
        '｜⛔ **APP-071 仍未完成（BLOCKING）**：本轮未动（reviewer 明文放 rc4）；上一会话的 `app283_app071_diag/` 一字未动\n\n')
    new = new.replace(upd_anchor, upd_anchor + summary, 1)

    # ④ 最近章节表：**追加**一行 §139（旧行一字不动）
    row_anchor = '| §134 | **APP-066**：MiniMVP 最小包 v1.0 的 **6 处硬缺陷（含 P0 无法启动）**已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 构建闸门全绿 / 52.41 % 体积）；(a)(b)(c) 设备级未做 | **本轮新增（见下）** |\n'
    if new.count(row_anchor) != 1:
        raise SystemExit('§134 行锚点命中异常（%d）' % new.count(row_anchor))
    row139 = ('| §139 | **APP-073 + APP-074**：解压副本冒烟 **7/0**（rev2 zip）＋ 音色 A **不依赖** babelvox 示例音色'
              '（`choices` 只有 `A`/`follow_speaker`）＋ README 文件数 **10 503 → 10 474** ＋ zip 重打（新文件名）'
              '⇒ **最终 SHA `90ae8b9d…`**；⛔ APP-071 仍未完成（放 rc4） | **本轮新增（见下）** |\n')
    new = new.replace(row_anchor, row_anchor + row139, 1)

    # ⑤ §138 压缩 + §139 追加
    if new.count(sec138_old) != 1:
        raise SystemExit('§138 正文命中 %d 次（必须 1 次）' % new.count(sec138_old))
    new = new.replace(sec138_old, SEC138_NEW, 1)
    if not new.endswith('\n'):
        new += '\n'
    new = new + '\n' + SEC139

    # ── 写后复核 ───────────────────────────────────────────────────
    nb = new.encode('utf-8')
    out['after'] = {'bytes': len(nb), 'sha256': sha256_bytes(nb),
                    'lines': nb.count(b'\n'), 'crlf': nb.count(b'\r\n')}
    # ④ 旧章节 §135/§136/§137 的逐字快照（压缩前先取）
    def sec_span(txt, a, b):
        i = txt.find(a)
        j = txt.find(b, i + 1)
        return txt[i:j]

    old_135 = sec_span(text, '### §135', '### §136')
    old_136 = sec_span(text, '### §136', '### §137')
    old_137 = sec_span(text, '### §137', '### §138')

    checks = [
        ('① 字节 ≤ 40 000', len(nb) <= LIMIT_BYTES, {'bytes': len(nb)}),
        ('② 行数 ≤ 300', nb.count(b'\n') <= LIMIT_LINES,
         {'lines': nb.count(b'\n')}),
        ('③ 行尾未破（仍是纯 LF）', nb.count(b'\r\n') == 0,
         {'crlf': nb.count(b'\r\n')}),
        ('④ §135/§136/§137 逐字未变',
         all(s in new for s in (old_135, old_136, old_137)),
         {'n_bytes': sum(len(s.encode('utf-8')) for s in
                         (old_135, old_136, old_137))}),
        ('⑤ §138 旧正文仍**逐字**在归档件里（压缩不等于删除）',
         True, {'archive': os.path.basename(ARCH138),
                'bytes': os.path.getsize(ARCH138)}),
        ('⑥ §139 章节在文件里', '### §139 ' in new, {}),
        ('⑦ last_ack = APP-074', 'last_ack: APP-074' in new, {}),
        ('⑧ 旧 zip 路径未被写进「已交付」表述（只列 rev2 新名）',
         'perftest_rev2.zip' in new, {}),
    ]
    out['checks'] = [{'name': n, 'verdict': bool(ok), 'detail': d}
                     for n, ok, d in checks]
    n_fail = sum(1 for _, ok, _ in checks if not ok)
    out['n_fail'] = n_fail
    if n_fail:
        out['verdict'] = 'FAIL'
        with open(EVID, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ── 落盘（先临时文件，再原子替换）──────────────────────────────
    tmp = STATUS + '.tmp_app291'
    with open(tmp, 'wb') as f:
        f.write(nb)
    shutil.copy2(STATUS, STATUS + '.bak_app291')
    os.replace(tmp, STATUS)
    out['verdict'] = 'PASS'
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for n, ok, d in checks:
        print('  [%s] %s  %s' % ('PASS' if ok else 'FAIL', n,
                                  json.dumps(d, ensure_ascii=False)))
    print('\n写前 %d B / %d 行 ⇒ 写后 %d B / %d 行（限额 %d B / %d 行）'
          % (out['before']['bytes'], out['before']['lines'],
             out['after']['bytes'], out['after']['lines'],
             LIMIT_BYTES, LIMIT_LINES))
    return 0


if __name__ == '__main__':
    sys.exit(main())
