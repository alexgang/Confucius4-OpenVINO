#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app103_write_status.py —— §103：把 §103 章节**追加**到 `status/app/STATUS_APP.md`。

## 铁律（记忆 §一）

1. 🔴 **只追加**到文件末尾；**不改**任何旧章节正文（§102 已入库推送 ⇒ 本轮不回头改它）。
2. 🔴 `STATUS_APP.md` 工作区是**纯 CRLF** ⇒ 必须 **bytes 级定点替换**
   ⇒ 绝不能用 `read().split('\n') + '\n'.join()`。
3. 🔴 头部字段替换**必须限定在头部区**（第一个 `## §N` 之前）
   ⇒ 正文里也可能出现字面文本 `## 最近更新` / `last_ack:`。
4. 🔴 头部 `set_field` 正则用 `[^\r\n]*`（`.` 会吞掉行尾 `\r`）。
5. 🔴 「最近更新」≤15 行 ⇒ 超了**裁最旧**。
6. 🔴 写后验：「原有章节一个不少」＋「旧正文逐字未变」＋「纯 CRLF」。
"""
from __future__ import annotations

import os
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'

NOW = '2026-10-30 10:19'

APPEND_BODY = r'''## §103 🔴🔴🔳 **「app160 判据恒真」自查 ⇒ 修掉 ＋ 干跑旧版暴露 §100 只查到 zip 层；等锁守候器在跑，zip 半交付仍待锁** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 10:19）
### 103.1 🔴🔴🔴 **「判据 PASS」不等于「判据正确」：干跑 v1.11 缺陷版 ⇒ 首版 V7 恒真 ⇒ 已修**

- 🔴 **背景**：`app160_app102_zip_verify.py` 是 §102 新增的 **zip 层复核**脚本
  （在 `app156` 基础上扩展 V1~V6 ＋ **V7 §101 模式感知** ＋ **V8 §102 脱敏** ＋
  **V9/V9b APP-044 资产** ＋ **V10 APP-044 许可** ＋ **V11 zip 内 asr_spk 语法**）。
- 🔴🔴🔴 **自查动作（双向反证的第 4 类：拿「已知有缺陷的旧产物」跑判据）**：
  用 **v1.11 zip**（= §101 修复**之前**的缺陷版）干跑 `app160`。
  ⇒ **首版 V7 判 PASS**（3 个标记全在）——**但 v1.11 里是缺陷版**：
  第 1670 行 `self._fallback_to_preset('no_spk_label')` 是**无条件回落**，**无模式感知**。
- 🔴 **根因**：首版 V7 只查三个**弱标记**
  （`_fallback_to_preset('no_spk_label')` / `self.clone_mode` / `self._spk_voices`）
  ⇒ 三者**缺陷版也有** ⇒ **判据恒真**。
- ✅ **修复**：增加三个**模式感知分支本体**特征：

  ```python
  S101_MARKERS = (
      "_fallback_to_preset('no_spk_label')",
      'self.clone_mode',
      'self._spk_voices',
  )
  # 🔴 弱标记不够：缺陷版也全在 ⇒ 必须查「模式感知分支本体」
  S101_MODE_AWARE = (
      'clone_mode and not',
      'bool(self._spk_voices)',
      'voice_kind',
  )
  ```

- ✅ **复核（修复后同一干跑）**：
  - v1.11 zip（缺陷版）⇒ **FAIL**：`缺模式感知特征 ['clone_mode and not', 'bool(self._spk_voices)']`
  - v1.12 包目录（正确版）⇒ **6 个特征全在**
  ⇒ **判据现在能识破缺陷版** ⇒ 不再恒真。

### 103.2 🔴 **`app160` 干跑 v1.11 的完整结果：4 PASS / 10 FAIL**（证据已落盘）

- 证据：`results/app/app160_app102_zip_evidence_v1.11.json`
  （**3 054 B** / SHA256(16) `78221a91608b4d95` / mtime 2026-10-30）。
- 原始字段（摘录）：`ver=1.11`、`zip_bytes=11 218 213 281`、
  `zip_sha256=72068c32c19ff4166f0875888bbc018d0fff9e3565c51d2a0f83c715b1217a20`、
  `n_entries=14 203`、`testzip=null`、`manifest_version=1.11`、`manifest_files=14 202`、
  `pass=4`、`fail=10`、`verdict=FAIL`。
- 🔴 **FAIL 项逐条归因（全部是「干跑旧版本」的预期现象，不是脚本崩）**：

  | 判据 | 结果 | 归因 |
  |---|---|---|
  | V1 zip 存在 | ✅ 11 218 213 281 B | — |
  | V2 `testzip()` 无 CRC 错 | ✅ `testzip=None` | — |
  | V5 MANIFEST version | ✅ `version='1.11' files=14202` | — |
  | V6 版本号三处一致 | ✅ dir=1.11 zip=1.11 manifest=1.11 | — |
  | V3 zip ⇄ 包目录 .py 一致 | ❌ 一致 0 / 差异 0 | **v1.11 目录已不存在**（被外部会话改名成 v1.12）⇒ `os.path.exists` 全 False ⇒ 不计入 |
  | V4 §100 修复在 zip 内 | ❌ NOT ON DISK | 同上（走的是「磁盘目录」分支）|
  | V7 §101 模式感知 | ❌ 缺 2 个模式感知特征 | **v1.11 是缺陷版 ⇒ 正确 FAIL**（判据有效的证明）|
  | V8 zip 内 asr_spk 无内部编号 | ❌ 0 个 .py / 0 命中 | v1.11 无 `app/asr_spk/`（APP-044 资产是 §101 才加的）|
  | V9 APP-044 说话人资产 | ❌ 0 个 IR / 0 字节 | 同上（0.00 MB）|
  | V9b APP-044 接口代码 | ❌ 0 个 .py | 同上 |
  | V10 APP-044 许可署名 | ❌ NOTICE/third_party 均含 wespeaker CC BY 4.0 + pyannote | v1.11 的 NOTICE 8 289 B / THIRD_PARTY 3 310 B，**均不含** wespeaker/pyannote |
  | V11 zip 内 asr_spk 语法 | ❌ 0 文件全合法 | 同 V8（0 文件）|

- ⇒ **结论**：v1.11 是 **§100/§101/§102 三轮修复之前**的产物 ⇒ 10 项 FAIL 全部是
  「旧 zip 缺新内容」的正常表现；**唯一有判据价值的是 V7**（它证明判据不恒真）。

### 103.3 🔴🔴🔴 **「半交付」的三层判据（本轮教训）**

| 层 | 现象 | 查出它的手段 |
|---|---|---|
| ① zip 旧 | 包目录对，但 zip 没重打 | `app156` / `app160` |
| ② **包目录内容不合规** | 包里**有内部素材**（§102 查出：`app/asr_spk/` 4 文件含 `260902`）| `pack_v13.py --dry-run` 触发**内部素材闸门** |
| ③ 包目录代码 ≠ 仓库 | 两份独立副本漂移 | 逐字节 SHA256 对比 |

⇒ 🔴 **只查 ① 就写「已交付」是错的**：本轮 §102 就是先查出 ② 才没白打一个不合规的 zip。

### 103.4 ✅ **本轮新产物（均已入库）**

| 产物 | 字节 | SHA256(16) | 说明 |
|---|---|---|---|
| `results/app/app160_app102_zip_verify.py` | 12 863 | `0878a10f84bada19` | zip 层复核 V1~V11 |
| `results/app/app160_app102_zip_evidence_v1.11.json` | 3 054 | `78221a91608b4d95` | 干跑 v1.11 的证据（**判据自检用**）|
| `live_caption/sync_c167_redact_spk_assets_to_pkg.py` | 8 435 | `461cb63cfc2d87b1` | §102 脱敏同步脚本 |
| `results/app/app159_app044_spk_redaction_evidence.json` | 2 130 | `491683b7f15551b3` | §102 脱敏合规验收 12/12 |

⇒ commit：`27d5b41`（app160 新增）→ `f13fd89`（V7 判据恒真修复）⇒ **均已普通 push**。

### 103.5 🔴 **锁仍被 TTS 持有 ⇒ 本轮仍不写「已交付」**

- 🔴 **实测（本轮复查）**：`shared/MACHINE_LOCK` =
  `module: tts` / `pid: 32856` / `started: 2026-10-30 09:50:29` / `host: LAPTOP-0GDQGD3I`
  ⇒ ctypes `OpenProcess` + `GetExitCodeProcess` 判 **alive, exit code 259**（STILL_ACTIVE）
  ⇒ **TTS 模块正在计时** ⇒ **本模块不抢锁、不杀进程**（铁律：别人活只能等）。
- ✅ **等锁守候器仍在运行**（`/tmp/app102_lockwait.py`，后台 task `d5UrW7`）：
  **只探测、不写任何文件** ⇒ 等锁期间 **0 次文件创建 / 0 次删除**
  ⇒ 不会触发宿主「批量删除保护」（铁律 §二）。
- ⚠️ **打包口径（不变）**：**必须显式 `--version 1.12`**
  （`discover_max_version()` = **1.12** ⇒ 默认 `bump_version()` 会推到 **1.13** ⇒ 白建一个目录）。
- 🔴 **锁一释放要做的事（未做）**：
  1. `pack_v13.py --version 1.12 --lock-timeout 7200`（持锁）；
  2. `results/app/app160_app102_zip_verify.py 1.12` 跑到 **0 FAIL**；
  3. 记录 zip 的 **文件数 / mtime / 字节数 / SHA256 / `testzip()` / MANIFEST `version`+`files`**，
     并确认「目录版本 == zip 版本 == MANIFEST version」三者一致；
  4. 才可在 STATUS 写「已交付」。

### 103.6 ✅ **记忆维护（本轮）**

- `MEMORY.md` **19 595 → 18 039 B**（明细移入 ARCHIVE，只留指针）。
- `MEMORY_ARCHIVE.md` **20 365 → 27 396 B**（新增「九·补 §102 巡检补充」与
  「九 守卫/半交付/许可合规（完整版）」⇒ 避免「移走即丢失」）。
- `.workbuddy/memory/2026-10-30.md` 追加 §102 段。
- ⚠️ 记忆目录**不被 git 跟踪** ⇒ 不需提交。

### 103.7 🔴 **reviewer 复核清单（本轮增量）**

1. 🔴 **§103.1 的判据修复请复核**：V7 由「3 个弱标记」改为「3 个弱标记 ＋ 3 个模式感知分支本体特征」
   ⇒ 请确认这 3 个特征（`clone_mode and not` / `bool(self._spk_voices)` / `voice_kind`）
   **不会被无关重构误伤**（若 reviewer 认为过脆，可指定更稳的特征集）。
2. 🔴 **§103.3 的「半交付三层判据」请复核**：是否把「打包前必跑 dry-run」固化为 App 打包的**常驻前置**。
3. 🔴 **§103.5 的 zip 闭环仍未做** ⇒ 等锁后重打 v1.12 ＋ `app160` 0 FAIL 才成立。
4. 🔴 **§102.6 的 6 条清单继续有效**（APP-043 真机 / APP-041 `pythonw` 冷启动 /
   GUI 路径 APP-042 / 3 段 1.2–1.3× 配音 / MiniMax 回转写 / APP-044 精度裁定）。
5. 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读；工作区该文件的 modified 是
   reviewer 独占写入的长期状态，HEAD 里只有 4 条 ⇒ **绝不入库**）。
'''


def main() -> int:
    with open(STATUS, 'rb') as f:
        raw = f.read()

    marker = b'## \xc2\xa7'
    idx = raw.find(marker)
    if idx < 0:
        print('!! 找不到任何 ## §N 章节 ⇒ 拒绝写入')
        return 1
    head_raw = raw[:idx]
    body_old = raw[idx:]

    old_sections = re.findall(rb'(?m)^## \xc2\xa7(\d+)', body_old)
    n_sec_old = len(old_sections)

    head = head_raw.replace(b'\r\n', b'\n').decode('utf-8')

    def set_field(text: str, key: str, value: str) -> str:
        pat = re.compile(r'(?m)^%s: [^\r\n]*' % re.escape(key))
        new, n = pat.subn('%s: %s' % (key, value), text, count=1)
        if n != 1:
            raise SystemExit('[FATAL] 头部字段 `%s` 命中 %d 次（应为 1）' % (key, n))
        return new

    head = set_field(head, '更新时间', NOW)
    head = set_field(
        head, '当前任务',
        '**§103 🔴🔴🔳 「app160 判据恒真」自查 ⇒ 修掉；干跑 v1.11 缺陷版 4 PASS / 10 FAIL '
        '（V7 正确 FAIL）⇒ zip 半交付仍待锁**'
        '（巡检：`CORRECTIONS_APP.md` 44 条 = `last_ack: APP-044` ⇒ **无新纠偏条目**，'
        '第 29 次同一口径复核）'
        '⇒ 🔴🔴🔴 **判据 PASS ≠ 判据正确**：用 v1.11 缺陷版干跑 ⇒ 首版 V7 恒真（弱标记缺陷版也有）'
        '⇒ ✅ **已修**：加 3 个「模式感知分支本体」特征 ⇒ 修后 v1.11 判 **FAIL**（缺 2 个特征）、'
        'v1.12 包目录 6 特征全在'
        '⇒ ✅ 证据落盘 `results/app/app160_app102_zip_evidence_v1.11.json`（3 054 B）'
        '⇒ 🔴 **10 项 FAIL 逐条归因**（v1.11 目录已不存在 / 无 APP-044 资产 / 无许可署名）'
        '⇒ ✅ **归纳「半交付三层判据」**：① zip 旧 ② **包目录内容不合规** ③ 包目录代码 ≠ 仓库'
        '⇒ ✅ 4 产物已入库（`27d5b41` → `f13fd89`，均已普通 push）'
        '⇒ 🔴 **锁仍被 TTS 持有**（pid 32856 / `OpenProcess` 判 alive exit 259）⇒ **不抢锁**'
        '⇒ ✅ 等锁守候器仍在跑（只探测不写文件）'
        '⇒ 🔴 **本轮不写「已交付」**（zip 层面）⇒ 🔴 **本条需等 reviewer 复核**')

    blk_pat = re.compile(r'(?m)^阻塞 / 待用户决定: [^\r\n]*')
    blk_new = (
        '阻塞 / 待用户决定: ① 🔴 **zip 半交付仍未闭环**：需等 TTS 释放锁后重打 v1.12 '
        '（含 §100 修复 ＋ §101 回归修复 ＋ APP-044 的 16 MB 资产 ＋ §102 脱敏）'
        '⇒ **必须显式 `--version 1.12`** ⇒ **本轮不抢锁、不写「已交付」**；'
        '② 🔴 **锁被 TTS 持有**（pid 32856 / 09:50:29 / `OpenProcess` 判 alive exit 259）'
        '⇒ 等锁守候器在跑（只探测不写文件）；'
        '③ 🔴 **§103.1 的 V7 特征集请 reviewer 确认**（`clone_mode and not` / '
        '`bool(self._spk_voices)` / `voice_kind` 是否会被无关重构误伤）；'
        '④ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
        '⑤ 🔴 **用户实听 3 段 1.2–1.3× 配音未做**；'
        '⑥ 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
        'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
        '⑦ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）；'
        '⑧ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/'
        '`app157`/`app159`）；'
        '⑨ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读）'
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
        '2026-10-30 10:19 §103 🔴🔴🔳 **「app160 判据恒真」自查 ⇒ 修掉**：干跑 v1.11 缺陷版 '
        '⇒ 首版 V7 恒真 ⇒ 改查 3 个「模式感知分支本体」特征 ⇒ 修后 v1.11 判 **FAIL**、'
        'v1.12 包目录 6 特征全在'
        '⇒ 🔴 **「半交付三层判据」**：① zip 旧 ② **包目录内容不合规** ③ 包目录代码 ≠ 仓库'
        '⇒ ✅ 4 产物已入库（`27d5b41` → `f13fd89`）'
        '⇒ 🔴 **锁仍被 TTS 持有**（pid 32856 alive）⇒ **不抢锁**、等锁守候器在跑'
        '⇒ 🔴 **zip 仍半交付 ⇒ 不写「已交付」** ⇒ 🔴 **本条需等 reviewer 复核**'
    )
    entries.insert(0, new_entry)
    while len(entries) > 15:
        entries.pop()          # 裁最旧
    new_lines = lines[:ri + 1] + [''] + entries + [''] + lines[j:]
    head = '\n'.join(new_lines)

    # ── 组装：头部（转回 CRLF）＋ 旧正文（**一个字节不动**）＋ 新章节 ──
    head_crlf = head.replace('\n', '\r\n').encode('utf-8')
    head_crlf = head_crlf.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

    body_new = APPEND_BODY.replace('\n', '\r\n').encode('utf-8')
    if not body_new.endswith(b'\r\n'):
        body_new += b'\r\n'

    out = head_crlf + body_old + body_new

    # ── 写盘前校验 ─────────────────────────────────────────────
    if b'\r\n' not in out:
        raise SystemExit('[FATAL] 输出不是 CRLF')
    assert out.count(b'\n') == out.count(b'\r\n'), '存在裸 LF'
    assert out[len(head_crlf):len(head_crlf) + len(body_old)] == body_old, '旧正文被改动'
    secs_new = re.findall(rb'(?m)^## \xc2\xa7(\d+)', out)
    old_nums = [int(x) for x in old_sections]
    new_nums = [int(x) for x in secs_new]
    for n_ in old_nums:
        if n_ not in new_nums:
            raise SystemExit('[FATAL] 原有章节 §%d 丢失' % n_)
    # §103 唯一
    assert new_nums.count(103) == 1, '§103 出现 %d 次' % new_nums.count(103)

    with open(STATUS, 'wb') as f:
        f.write(out)

    print('✅ 已追加 §103')
    print('   字节 %d → %d' % (len(raw), len(out)))
    print('   章节数 %d → %d' % (n_sec_old, len(new_nums)))
    print('   纯 CRLF: True')
    print('   旧正文逐字未变: True')
    print('   原有章节一个不少: True')
    print('   §103 唯一: True')
    print('   最近更新条目数: %d（≤15）' % len(entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
