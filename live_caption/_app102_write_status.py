#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app102_write_status.py —— §102：把 §102 章节**追加**到 `status/app/STATUS_APP.md`。

## 铁律（记忆 §一）

1. 🔴 **只追加**到文件末尾；**不改**任何旧章节正文。
2. 🔴 `STATUS_APP.md` 工作区是**纯 CRLF** ⇒ 必须 **bytes 级定点替换**
   ⇒ 绝不能用 `read().split('\n') + '\n'.join()`（会把整文件行尾改掉）。
3. 🔴 头部字段替换**必须限定在头部区**（第一个 `## §N` 之前）
   ⇒ 正文里也可能出现字面文本 `## 最近更新` / `last_ack:`。
4. 🔴 头部 `set_field` 正则用 `[^\r\n]*`（`.` 会吞掉行尾 `\r` ⇒ 该行变裸 LF）。
5. 🔴 「最近更新」≤15 行 ⇒ 超了**裁最旧**。
6. 🔴 写后验：「原有章节一个不少」＋「旧正文逐字未变」＋「纯 CRLF」。
"""
from __future__ import annotations

import os
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
SECTION_FILE = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app102_section.md'

# 本轮追加的正文（§102）
APPEND_BODY = r'''## §102 🔴🔴🔳 **开工即查出「APP-044 包内容含内部会议素材」⇒ 脱敏后闸门 PASS（12/12）＋ 客户包 v1.12 目录已就位 ⇒ zip 半交付仍待锁** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 10:09）
### 102.1 🔴🔴🔴 **开工巡检：APP-044 的包内容本身不合规 ⇒ 不是「zip 没重打」，是「包里有内部会议素材」**

- 🔴 **巡检口径**：`CORRECTIONS_APP.md` = **44 条**（APP-001…APP-044），
  `STATUS_APP.md` 头部 `last_ack: APP-044` ⇒ **无新纠偏条目**（第 28 次同一口径复核）。
  ⇒ 本轮做的是**收尾闭环**（§100.12 遗留的 zip 半交付）+ **开工即查出的合规缺陷**。
- 🔴 **外部会话已把 v1.11 目录改名为 v1.12**（实测：v1.11 目录**不存在**，
  `Confucius4_LiveCaption_v1.12` 目录在位）⇒ §100.12.2 记录的「同卷改名 `WinError 5`」
  **已被外部解除**；`discover_max_version()` 由 1.11 变 **1.12**。
- 🔴🔴🔴 **但 dry-run 暴露一个此前从未暴露的阻塞 —— 内部素材闸门 FAIL**：

  ```
  $ python pack_v13.py --version 1.12 --dry-run
  ======================================================================
  内部素材闸门（APP-006 第 6 步）
  ======================================================================
  [待打包目录] C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12
    命中 4 个内部素材
      ⚠️ app/asr_spk/asr050_spk_qa_speaker_test.py  (内容关键词：会议音频编号 [REDACTED])
      ⚠️ app/asr_spk/asr_slice_common.py  (内容关键词：会议音频编号 [REDACTED])
      ⚠️ app/asr_spk/pya_app_path_seg.py  (内容关键词：会议音频编号 [REDACTED])
      ⚠️ app/asr_spk/pya_stream_segment.py  (内容关键词：会议音频编号 [REDACTED])

  结论：FAIL —— 存在内部素材，禁止打包/提交
  ```

  ⇒ **§101 同步进包的 `app/asr_spk/`（APP-044 要求的「ASR 的 SpeakerTracker 接口代码」）
  自身含内部会议音频编号 `260902`** ⇒ **包内容不合规** ⇒ **即使拿到锁也打不出合规包**。
  ⇒ ⇒ **这是比「zip 半交付」更靠前的一道阻塞**（§100.12 只查到 zip 层，没查到这一层）。

#### 102.1.1 🔴 **为什么不能直接删这 4 个文件**（AST 实测：运行时 import 链）

`asr052_speaker_tracker_api.py`（运行时入口）在**函数体内**真实 import 了它们：

| 位置 | import |
|---|---|
| `asr052:322` | `from asr050_spk_qa_speaker_test import WespeakerOVEncoder` |
| `asr052:323` | `from asr021_bypass_spk_wespeaker import OnlineSpeakerCluster` |
| `asr052:338` | `import pya_bypass_spk as PB` |
| `asr052:339` / `:365` / `:391` | `import pya_stream_segment as P` |

⇒ **删掉任何 4 个之一 ⇒ 客户机 import 链断裂 ⇒ 说话人旁路整条挂掉**。
⇒ **只能脱敏**（改字面量，不改结构）。

#### 102.1.2 ✅ **命中点逐条核对：9 处**全部是「测试语料」，无一是运行时逻辑

| 文件 | 行 | 性质 |
|---|---|---|
| `asr_slice_common.py` | 5, 10 | docstring 说明 |
| `asr_slice_common.py` | 26 | `SOURCE_WAV` 常量（测试语料路径）|
| `asr050_spk_qa_speaker_test.py` | 7, 19 | docstring 说明 |
| `asr050_spk_qa_speaker_test.py` | 243 | argparse `--wav` 默认值 |
| `pya_app_path_seg.py` | 9 | docstring 说明 |
| `pya_app_path_seg.py` | 556 | 打印语句里的说明文本 |
| `pya_stream_segment.py` | 60 | `WAV` 常量 → argparse `--wav` 默认值 |

⇒ **全是「测试语料文件的路径 / 说明」**；客户机**没有** `test_audio/` 目录
⇒ 这 9 处**运行时永不被读取** ⇒ 脱敏**行为等价**。

### 102.2 ✅ **脱敏已落盘**（`sync_c167_redact_spk_assets_to_pkg.py`）

- 🔴 **脱敏策略**：**只替换字面量 `260902` → `SPEQA`（等长）**，**其余字节逐字不动**
  ⇒ 路径结构 / argparse 语义 / import 链 / 行数 / 行尾**全部保持**。
- 🔴 **铁律遵守**：
  - 不做整目录覆盖（只动 4 个文件的字面量）；
  - **不手写待插入的源码**（只做定长字面量替换，不生成任何新源码行）；
  - **定点替换行尾无关**（bytes 读入 → 检测 `b'\r\n'` → 归一化 LF 匹配/替换 → 写回按原行尾还原）
    ⇒ 并断言「同步前后行尾不变」；
  - **写盘前 `ast.parse` 校验**（不通过则中止、不落盘）⇒ 杜绝「客户机启动即崩」。
- ✅ **产物实测**（脱敏前 → 后；备份在**包外** `C:\Users\Trekker-PTL\bak_c167_20261030_asr_spk\`）：

  | 文件 | before B | after B | before SHA256(16) | after SHA256(16) |
  |---|---|---|---|---|
  | `asr050_spk_qa_speaker_test.py` | 27 642 | 27 639 | `53375602932a6196` | `487a28a45eef7355` |
  | `asr_slice_common.py` | 2 991 | 2 988 | `a22f7ac3667adc6b` | `9a68d4c0ca4c1bd6` |
  | `pya_app_path_seg.py` | 31 099 | 31 097 | `ddc22e78807256b6` | `a27d3097f554ca06` |
  | `pya_stream_segment.py` | 20 102 | 20 101 | `6dd208c8a0e6a034` | `9f89c60b8fc382fa` |

  ⇒ 命中合计 **9 处**；每文件字节差 = 命中数（等长替换 ⇒ 差 3 / 3 / 2 / 1）。

### 102.3 ✅ **`app159` 脱敏合规验收：12/12 PASS**（6 条反证全命中）

- 证据：`results/app/app159_app044_spk_redaction_evidence.json`（**已落盘**）。
- 判据：

  | 组 | 判据 | 结果 |
  |---|---|---|
  | R1 | 包内 `app/asr_spk/` **0 个**文件含内部编号（**扫全目录**，不只扫 4 个目标文件）| ✅ 0 命中 |
  | R2 | 全部 `.py` 语法合法（`ast.parse`）| ✅ 10 文件全合法 |
  | R3 | `asr052` 运行时 import 链完整（5 个依赖全在）| ✅ |
  | R4 | 除编号外**字节逐字未变**（与备份比）| ✅ 4 文件 |
  | R5 | **行数不变** | ✅ |
  | R6 | 客户包**内部素材闸门 PASS**（`check_internal_material.py` exit=0）| ✅ 「命中 0 个内部素材」|

- ✅ **双向反证 6 条全部命中**（判据不恒真）：
  D-1 注入编号 ⇒ R1 FAIL｜D-2 注入语法错 ⇒ R2 FAIL｜D-3 删运行时依赖 ⇒ R3 FAIL｜
  D-4 篡改非编号字节 ⇒ R4 FAIL｜D-5 删一行 ⇒ R5 FAIL｜D-6 闸门返非 0 ⇒ R6 FAIL。
- 🔴 **修掉 2 处「我自己写的判据缺陷」**（首跑 10/12 FAIL ⇒ 复跑 12/12）：
  ① **R4**：备份里是 `260902`、现文件里是 `SPEQA` ⇒ 「抹掉 SECRET 再比」抹掉的是**不同串**
     ⇒ 「脱敏本身」被误判成「有别的字节被改了」⇒ 改为**两边各自抹掉各自的敏感串**再比；
  ② **D-5**：反证原在**备份**上删行（备份本就没动）⇒ 恒不 FAIL ⇒ 改为在**现文件**上删行。

### 102.4 ✅ **包目录层面复核（脱敏后）**

- ✅ **4 个 App 文件与仓库逐字节一致**（归一化 LF 后 SHA256 前 16 位）：
  `live_caption_app.py` `e5440190eadcef1f`｜`tts_worker.py` `73c756420fd1c1ee`｜
  `speaker_tracker.py` `4b03f19fbaf127e8`｜`speaker_assets.py` `e4d655a69e7dfdcd`
  ⇒ **§100 断链 G/H/I/J ＋ §101 回归修复 ＋ APP-044 资产**全部在包目录内。
- ✅ `app157_follow_speaker_regression_test.py` 复跑 **11/11 PASS**（4 条反证全命中）。
- ✅ **APP-044 许可合规复核**：`NOTICE`（9 643 B / SHA256 `96ff747b21ff59e…`）
  与 `THIRD_PARTY.md`（3 784 B / SHA256 `a3ebb8df47ff11ba…`）**均含**
  wespeaker（`Creative Commons Attribution 4.0 International (CC BY 4.0)`，**含署名 + 链接**）
  与 pyannote/segmentation-3.0（MIT，**含 Authors / Copyright**）⇒ **APP-044 许可义务已履行**。

### 102.5 🔴 **zip 仍未闭环：锁被 TTS 持有 ⇒ 本轮不抢锁**

- 🔴 **实测**：`shared/MACHINE_LOCK` = `module: tts / pid: 32856 / started: 2026-10-30 09:50:29`
  ⇒ ctypes `OpenProcess` + `GetExitCodeProcess` 判 **alive, exit code 259**
  ⇒ **TTS 模块正在计时** ⇒ **本模块不抢锁**（铁律：别人活只能等不能杀）。
- ✅ **等锁守候器已启动**（`/tmp/app102_lockwait.py`）：
  **只探测、不写任何文件** ⇒ 等锁期间 **0 次文件创建 / 0 次删除**
  ⇒ 不会触发宿主「批量删除保护」（铁律 §二）。
  ⇒ 锁一释放即自动取得（`module=app-pack`）。
- ⚠️ **打包口径已定案**：**必须显式 `--version 1.12`**
  （`discover_max_version()` = **1.12** ⇒ 默认 `bump_version()` 会推到 **1.13** ⇒ 白建一个目录）。
- ⚠️ **MANIFEST 现状**：`v1.12/app/MANIFEST.json`（22 582 B）仍称 `version=1.11`
  ⇒ 打包时会由 `refresh_manifest()` 自动改成 `1.12` ⇒ 「目录版本 == zip 版本 == MANIFEST version」
  三者一致由打包器保证。
- 🔴 **本轮不写「已交付」**（zip 层面）⇒ 等锁 + 打包 + `app156` 复核到 0 FAIL 才成立。

### 102.6 🔴 **reviewer 复核清单**

1. 🔴 **zip 半交付仍未闭环**：需等 TTS 释放锁后重打 v1.12（含 §100 修复 ＋ §101 回归修复
   ＋ APP-044 的 16 MB 资产 ＋ 本轮脱敏）⇒ 复核点：`app156` 必须 **0 FAIL**。
2. 🔴 **本轮新查出「包内容含内部会议素材」这一层**（§100 只查到 zip 层）
   ⇒ 请复核「脱敏而非删除」的取舍（4 文件在 `asr052` 运行时 import 链内，删了会断链）。
3. 🔴 **APP-043 真机验收**（SPE Q&A densest_5min 走 App 实时路径，按 APP-039 的 4 项指标）
   ＋ APP-041 `pythonw` 冷启动 ＋ GUI 路径 APP-042 ＋ 3 段 1.2–1.3× 配音
   ⇒ **本轮仍未做**（归 §101 会话／需真机）。
4. 🔴 **APP-044 精度形态**（FP16 还是 FP32）待 reviewer 按 ASR-025 裁定
   ⇒ **代码无需改**，只需换目录重打。
5. 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）。
6. 🔴 **用户实听 3 段 1.2–1.3× 配音未做**。
'''


def main() -> int:
    with open(STATUS, 'rb') as f:
        raw = f.read()

    # ── 记录旧正文（用于「逐字未变」校验）──────────────────────
    marker = b'## \xc2\xa7'
    idx = raw.find(marker)
    if idx < 0:
        print('!! 找不到任何 ## §N 章节 ⇒ 拒绝写入')
        return 1
    head_raw = raw[:idx]
    body_old = raw[idx:]

    old_sections = re.findall(rb'(?m)^## \xc2\xa7(\d+)', body_old)
    n_sec_old = len(old_sections)

    # ── 头部区归一化（只改头部，不碰正文一个字节）───────────────
    head = head_raw.replace(b'\r\n', b'\n').decode('utf-8')

    def set_field(text: str, key: str, value: str) -> str:
        # 🔴 用 [^\r\n]* 而非 .* ⇒ 不会吞掉行尾的 \r
        pat = re.compile(r'(?m)^%s: [^\r\n]*' % re.escape(key))
        new, n = pat.subn('%s: %s' % (key, value), text, count=1)
        if n != 1:
            raise SystemExit('[FATAL] 头部字段 `%s` 命中 %d 次（应为 1）' % (key, n))
        return new

    head = set_field(head, '更新时间', '2026-10-30 10:09')
    head = set_field(
        head, '当前任务',
        '**§102 🔴🔴🔴 开工即查出「APP-044 包内容含内部会议素材」⇒ 脱敏后闸门 PASS（12/12）'
        '＋ §100.12 遗留的 zip 半交付仍待锁**'
        '（巡检：`CORRECTIONS_APP.md` 44 条 = `last_ack: APP-044` ⇒ **无新纠偏条目**，'
        '第 28 次同一口径复核）'
        '⇒ 🔴 **外部会话已把 v1.11 改名为 v1.12**（§100.12.2 的 `WinError 5` 已解除）'
        '⇒ 🔴🔴🔴 **但 dry-run 暴露内部素材闸门 FAIL**：§101 同步进包的 `app/asr_spk/` '
        '**4 个文件含内部会议音频编号 `260902`** ⇒ **包内容本身不合规**（不是「zip 没重打」那一层）'
        '⇒ ✅ **不能删**（AST 实测 `asr052:322/323/338/339/365/391` 真实 import 它们 ⇒ 删了断链）'
        '⇒ ✅ **已脱敏**（`sync_c167`，只替字面量 `260902`→`SPEQA`，9 处，其余字节逐字不动，'
        '写盘前 `ast.parse` 校验）⇒ ✅ **`app159` 12/12 PASS**（6 条反证全命中）'
        '⇒ ✅ **修掉 2 处我自己写的判据缺陷**（R4 抹错敏感串 / D-5 反证改错了对象）'
        '⇒ ✅ 闸门复跑 **PASS（0 命中）**'
        '⇒ ✅ 包目录 4 文件与仓库**逐字节一致** ＋ `app157` 复跑 **11/11**'
        '⇒ ✅ **APP-044 许可合规复核通过**（NOTICE/THIRD_PARTY 均含 wespeaker CC BY 4.0 署名+链接、'
        'pyannote MIT Authors/Copyright）'
        '⇒ 🔴 **锁被 TTS 持有**（pid 32856 / 09:50:29 / `OpenProcess` 判 alive）⇒ **不抢锁**'
        '⇒ ✅ **等锁守候器已启动**（只探测不写文件 ⇒ 等锁期间 0 次创建/删除）'
        '⇒ 🔴 **本轮不写「已交付」**（zip 层面）⇒ 🔴 **本条需等 reviewer 复核**')

    # 「阻塞 / 待用户决定」行：整行替换（该行以「阻塞 / 待用户决定」开头）
    blk_pat = re.compile(r'(?m)^阻塞 / 待用户决定: [^\r\n]*')
    blk_new = (
        '阻塞 / 待用户决定: ① 🔴 **zip 半交付仍未闭环**：需等 TTS 释放锁后重打 v1.12 '
        '（含 §100 修复 ＋ §101 回归修复 ＋ APP-044 的 16 MB 资产 ＋ 本轮脱敏）'
        '⇒ **本轮不抢锁、不写「已交付」**；'
        '② 🔴 **锁被 TTS 持有**（pid 32856 / 09:50:29 / `OpenProcess` 判 alive）'
        '⇒ 等锁守候器已启动（只探测不写文件）；'
        '③ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
        '④ 🔴 **用户实听 3 段 1.2–1.3× 配音未做**；'
        '⑤ 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
        'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
        '⑥ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）；'
        '⑦ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/'
        '`app157`/`app159`）；'
        '⑧ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读）'
    )
    head, n = blk_pat.subn(blk_new, head, count=1)
    if n != 1:
        raise SystemExit('[FATAL] 「阻塞 / 待用户决定」行命中 %d 次' % n)

    # ── 「最近更新」：插入新行 + 超 15 行裁最旧 ──────────────────
    lines = head.split('\n')
    ri = None
    for i, ln in enumerate(lines):
        if ln.replace('#', '').strip() == '最近更新':
            ri = i
            break
    if ri is None:
        raise SystemExit('[FATAL] 头部找不到「最近更新」标题')
    # 找该标题下的条目行区间
    j = ri + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    entries = []
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            break
        entries.append(lines[j])
        j += 1
    new_entry = (
        '2026-10-30 10:09 §102 🔴🔴🔳 **开工即查出「APP-044 包内容含内部会议素材」这一层**'
        '（§100 只查到 zip 层）⇒ **4 文件在 `asr052` 运行时 import 链内 ⇒ 不能删、已脱敏**'
        '（`260902`→`SPEQA`，9 处，其余字节逐字不动）⇒ ✅ **`app159` 12/12 PASS**'
        '（6 条反证全命中；并修掉 2 处我自己写的判据缺陷）⇒ ✅ **闸门复跑 PASS（0 命中）**'
        '⇒ ✅ 包目录 4 文件与仓库逐字节一致 ＋ `app157` 11/11 ＋ APP-044 许可署名合规'
        '⇒ 🔴 **锁被 TTS 持有**（pid 32856 alive）⇒ **不抢锁**、等锁守候器已启动'
        '⇒ 🔴 **zip 仍半交付 ⇒ 不写「已交付」** ⇒ 🔴 **本条需等 reviewer 复核**'
    )
    entries.insert(0, new_entry)
    while len(entries) > 15:
        entries.pop()          # 裁最旧
    new_lines = lines[:ri + 1] + [''] + entries + [''] + lines[j:]
    head = '\n'.join(new_lines)

    # ── 组装：头部（转回 CRLF）＋ 旧正文（**一个字节不动**）＋ 新章节 ──
    head_crlf = head.replace('\n', '\r\n').encode('utf-8')
    # 🔴 头部区裸 LF 归一化（只对头部区做，正文区一个字节不动）
    head_crlf = head_crlf.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

    body_new = APPEND_BODY.replace('\n', '\r\n').encode('utf-8')
    # 章节之间无空行 + 结尾换行
    if not body_new.endswith(b'\r\n'):
        body_new += b'\r\n'

    out = head_crlf + body_old + body_new

    # ── 写盘前校验 ─────────────────────────────────────────────
    if b'\r\n' not in out:
        raise SystemExit('[FATAL] 输出不是 CRLF')
    assert out.count(b'\n') == out.count(b'\r\n'), '存在裸 LF'
    # 旧正文逐字未变
    assert out[len(head_crlf):len(head_crlf) + len(body_old)] == body_old, '旧正文被改动'
    # 原有章节一个不少
    secs_new = re.findall(rb'(?m)^## \xc2\xa7(\d+)', out)
    old_nums = [int(x) for x in old_sections]
    new_nums = [int(x) for x in secs_new]
    for n_ in old_nums:
        if n_ not in new_nums:
            raise SystemExit('[FATAL] 原有章节 §%d 丢失' % n_)

    with open(STATUS, 'wb') as f:
        f.write(out)

    print('✅ 已追加 §102')
    print('   字节 %d → %d' % (len(raw), len(out)))
    print('   章节数 %d → %d' % (n_sec_old, len(new_nums)))
    print('   纯 CRLF: True')
    print('   旧正文逐字未变: True')
    print('   原有章节一个不少: True')
    print('   最近更新条目数: %d（≤15）' % len(entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
