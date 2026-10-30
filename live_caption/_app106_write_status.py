#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app106_write_status.py —— §106：把 §106 章节**追加**到 `status/app/STATUS_APP.md`。

## 铁律（记忆 §一 / §九）

1. 🔴 **只追加**到文件末尾；**不改**任何旧章节正文。
2. 🔴 `STATUS_APP.md` 是**纯 CRLF** ⇒ **bytes 级定点替换**。
3. 🔴 头部字段替换**限定在头部区**（第一个 `## §N` 之前）。
4. 🔴 `set_field` 正则用 `[^\r\n]*`；value **不能自带 `key: ` 前缀**。
5. 🔴 「最近更新」≤15 行 ⇒ 超了裁最旧。
6. 🔴 🔴 **旧正文末尾可能没有换行** ⇒ 拼接时必须补 CRLF 分隔，否则新章节标题
   会被拼到旧行尾 ⇒ `(?m)^## §N` 匹配不到 ⇒ 章节计数为 0。
7. 🔴 写后验：「原有章节一个不少」＋「旧正文逐字未变」＋「纯 CRLF」＋「本节唯一」。
"""
from __future__ import annotations

import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
NOW = '2026-10-30 11:25'

APPEND_BODY = r'''## §106 ✅✅ **v1.12 客户包 zip 闭环：持锁重打完成（14 218 文件 / 11 233 373 363 B）＋ `app160` 复核 14 PASS / 0 FAIL ⇒ zip 半交付解除** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 11:25）
### 106.1 ✅ **持锁重打 v1.12（完整链路全过）**

- 🔴 **等锁**：TTS 持锁 **2 220 s** ⇒ 本模块**不抢锁**（铁律：别人活只能等）
  ⇒ 打包作业**自己**等锁（第 **113** 次尝试取得），**未另起守候器**（避免 §105.1 的「白拿白放」）。
- 🔴 **持锁时段**：`module: app-pack / pid: 37168 / started: 2026-10-30 11:03:55`
  ⇒ 安静窗口（45 s，CPU 增量分类器判定「0 个在算的外部 python」）⇒ 开始打包。
- 🔴 **打包前两道闸门（实跑输出）**：
  - ✅ **包路径写死闸门（§48）**：「命中『代码行里有客户包名』的文件数 = 82」⇒「✅ **0 处违规**」⇒ 总判定 **PASS**
  - ✅ **内部素材闸门（APP-006 第 6 步）**：「**命中 0 个内部素材**」⇒ **PASS**（§102 脱敏的成果）
- ✅ **MANIFEST 刷新**：`files 14202 -> 14217`、`bytes 13 673 001 756 -> 13 689 695 552`（12.75 GB）、
  **`version: '1.11' -> '1.12'`**（= §102.5 预判的自动刷新，**已实证**）。
- ✅ **压缩**：`文件数 14218` / `原始字节 13 689 718 134` / `压缩后字节 11 233 373 363 (10.46 GB)`
  / `压缩率 82.1%` / `耗时 758 s`。
- ✅ **`testzip()` 校验**：「**Everything is Ok**」⇒ `testzip=None`。
- ✅ **关键文件抽查**：36 项全 `[OK]`（`app/live_caption_app.py` 300 750 B /
  `app/MANIFEST.json` 22 582 B / `THIRD_PARTY.md` 3 784 B /
  `models/mt/mt2-int8sym-cw-q/openvino_model.bin` 1 792 991 738 B /
  `models/qwen3tts/int8/*.bin` 15 项 / `preset_A.wav` 192 044 B …）。
- ✅ **旧产物 / 缓存 / 内部会议内容 / 第三方音色 / 开发脚本** 全部 `[已移除]`（各 0 条命中）。
- ✅ **包内本地模块导入完整性**：「zip 内 app/*.py = 37 个；**确定缺失 0 条**」（90 条疑似第三方依赖不判负）。
- ✅ **内容一致性（zip ⇄ 包目录，逐文件 SHA256）**：「比对 **14 218** 个文件」⇒「**全部逐字节一致**」。
- ✅ **原子改名**：「[info] 校验通过 ⇒ 已原子改名到正式路径」⇒ `结论：PASS` ⇒ **`[lock] 已释放`**。

### 106.2 ✅ **`app160` 复核：14 PASS / 0 FAIL ⇒ verdict=PASS（zip 半交付解除）**

- 证据：`results/app/app160_app102_zip_evidence_v1.12.json`
  （**3 037 B** / SHA256(16) `9b217b40a82fc73b` / mtime 2026-10-30 11:25:30）—— **已落盘**。

  | 判据 | 结果 |
  |---|---|
  | V1 zip 存在 | ✅ 11 233 373 363 字节 |
  | V2 `testzip()` 无 CRC 错误 | ✅ `testzip=None` |
  | V3 zip ⇄ 包目录 .py 逐字一致 | ✅ **一致 6 603 / 差异 0** |
  | V4 §100 修复在 zip 内（3 文件）| ✅ `live_caption_app.py` `e5440190eadc`｜`tts_worker.py` `73c756420fd1`｜`speaker_tracker.py` `4b03f19fbaf1` —— **zip 与 pkg 双侧同值** |
  | V5 MANIFEST version == 1.12 | ✅ `version='1.12' files=14217` |
  | V6 版本号三处一致 | ✅ **dir=1.12 / zip=1.12 / manifest=1.12** |
  | V7 §101 模式感知修复在 zip 内 | ✅ **3 弱标记 + 3 模式感知特征全在**（`miss=[]` / `miss_mode_aware=[]` / `ok=True`）|
  | V8 zip 内 `app/asr_spk/` 无内部编号 | ✅ **10 个 .py，0 命中** |
  | V9 APP-044 说话人资产在 zip 内 | ✅ **4 个 IR / 16 479 887 字节（15.72 MB）** |
  | V9b APP-044 接口代码在 zip 内 | ✅ **10 个 .py** |
  | V10 APP-044 许可署名在 zip 内 | ✅ `NOTICE`（9 643 B）与 `THIRD_PARTY.md`（3 784 B）**均含** wespeaker + CC BY 4.0 + pyannote + MIT |
  | V11 zip 内 `asr_spk` 语法全合法 | ✅ **10 文件全合法** |

- ✅ **原始字段**：`ver=1.12`｜`zip_bytes=11233373363`｜`zip_mtime=2026-10-30 11:20:14`｜
  `zip_sha256=28cf34de3514680e12440c11b63ad9c95d34e827b1a64bea8808bcd1d08a72b6`｜
  `n_entries=14218`｜`testzip=None`｜`manifest_version=1.12`｜`manifest_files=14217`｜
  `pass=14`｜`fail=0`｜`verdict=PASS`。

### 106.3 ✅ **交付物清单（附文件数 / mtime / 字节数 / SHA256）**

| 交付物 | 文件数 | mtime | 字节 | SHA256 |
|---|---|---|---|---|
| `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12.zip` | 14 218 条目 | 2026-10-30 11:20:14 | **11 233 373 363** | `28cf34de3514680e12440c11b63ad9c95d34e827b1a64bea8808bcd1d08a72b6` |
| `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12\`（包目录）| — | — | 13 689 718 134（原始）| 与 zip **14 218 文件逐字节一致** |
| `results/app/app160_app102_zip_evidence_v1.12.json` | 1 | 2026-10-30 11:25:30 | 3 037 | `9b217b40a82fc73b`（前 16 位） |

- ✅ **「已交付」判据全部满足**：包目录 ✅ ＋ zip ✅ ＋ 代码已入库 ✅（`git show HEAD:` 可取）
  ⇒ **「包里代码对」＋「zip 是最新的」＋「证据已入库」三者同时成立**。
- 🔴 **本轮仍未做（不属 zip 层）**：APP-043 真机验收、APP-041 `pythonw` 冷启动、
  GUI 路径 APP-042、3 段 1.2–1.3× 配音给用户实听、reviewer 的 MiniMax 回转写对比、
  APP-044 精度形态裁定（FP16/FP32）⇒ **见 §106.5**。

### 106.4 🔴 **本轮额外修掉的一个写入器隐患（供其它模块复用）**

- 🔴🔴🔴 **「旧正文末尾没有换行」** ⇒ 追加新章节时**新标题被拼到旧行尾**
  ⇒ `(?m)^## §N` **匹配不到** ⇒ **章节计数为 0** ⇒ 表现为「写入器 assert `§N 出现 0 次`」。
- ✅ **修法**：`sep = b'' if body_old.endswith(b'\r\n') else b'\r\n'`；拼接 `head + body_old + sep + new_body`。
  （本轮 §105 首次触发、§106 已带上修复。）
- 🔴 **教训**：**章节计数为 0 不一定是「写错了」，也可能是「没换行」** ⇒ 先查拼接边界。

### 106.5 🔴 **reviewer 复核清单（zip 已闭环，剩余项）**

1. 🔴 **§106.1/106.2/106.3 的 zip 交付**：请复核 14 218 文件 / 11 233 373 363 B /
   SHA256 `28cf34de…08a72b6` / `app160` 14 PASS 0 FAIL ⇒ **zip 半交付是否可判定解除**。
2. 🔴 **§106.4 的写入器修法**请复核（供 App/ASR/MT/TTS 共用纪律）。
3. 🔴 **§102.6 / §103.7 / §104.9 / §105.6 的其余清单继续有效**：
   APP-043 真机验收（SPE Q&A densest_5min）｜APP-041 `pythonw` 冷启动｜
   GUI 路径 APP-042 真机｜3 段 1.2–1.3× 配音用户实听｜MiniMax 回转写 WER（**本模块不得自做**）｜
   APP-044 精度形态（FP16/FP32）裁定。
4. 🔴 **§104.3 的 2 个「复跑产物」**（`app158_..._pkg.json` / `app154_...json`）是否入库，仍待 reviewer 裁定。
5. 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读；工作区 modified 是 reviewer 独占写入的长期状态）。
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
        '**§106 ✅✅ v1.12 客户包 zip 闭环：持锁重打完成 ＋ `app160` 14 PASS / 0 FAIL '
        '⇒ zip 半交付解除**'
        '（巡检：`CORRECTIONS_APP.md` 44 条 = `last_ack: APP-044` ⇒ **无新纠偏条目**，'
        '第 32 次同一口径复核）'
        '⇒ ✅ **持锁重打 v1.12**（等锁 2 220 s 不抢；打包作业自己等锁，第 113 次尝试取得）'
        '⇒ ✅ **打包前两道闸门全过**（包路径写死 **0 处违规** ＋ 内部素材 **0 命中**）'
        '⇒ ✅ **MANIFEST 自动刷新** `version 1.11 -> 1.12` / `files 14202 -> 14217`'
        '⇒ ✅ **压缩** 14 218 文件 / 13 689 718 134 B -> **11 233 373 363 B**（82.1% / 758 s）'
        '⇒ ✅ **`testzip()` = Everything is Ok** ＋ **zip ⇄ 包目录 14 218 文件逐字节一致**'
        '⇒ ✅ **原子改名到正式路径** ⇒ 锁已释放'
        '⇒ ✅ **`app160` 14 PASS / 0 FAIL**（证据 `app160_app102_zip_evidence_v1.12.json`）'
        '⇒ ✅ **版本三处一致** dir=1.12 / zip=1.12 / manifest=1.12'
        '⇒ ✅ **交付物**：zip 11 233 373 363 B / SHA256 `28cf34de…08a72b6` / mtime 11:20:14'
        '⇒ ✅ **「已交付」判据满足**（包目录 ＋ zip ＋ 代码已入库 ＋ 证据已落盘）'
        '⇒ 🔴 **真机项仍未做**（APP-043 / APP-041 / GUI APP-042 / 3 段配音实听 / MiniMax 回转写 / '
        'APP-044 精度裁定）⇒ 🔴 **本条需等 reviewer 复核**')

    blk_pat = re.compile(r'(?m)^阻塞 / 待用户决定: [^\r\n]*')
    blk_new = (
        '阻塞 / 待用户决定: ① ✅ **zip 半交付已解除**（v1.12：14 218 文件 / '
        '11 233 373 363 B / SHA256 `28cf34de…08a72b6` / `app160` 14 PASS 0 FAIL）'
        '⇒ **待 reviewer 确认可否判定「已交付」**；'
        '② 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
        'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
        '③ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
        '④ 🔴 **用户实听 3 段 1.2–1.3× 配音未做**；'
        '⑤ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）；'
        '⑥ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/'
        '`app157`/`app159`）；'
        '⑦ 🔴 **§104.3 的 2 个「复跑产物」**（`app158_..._pkg.json` / `app154_...json`）是否入库待裁定；'
        '⑧ 🔴 **§104.6 起的 zip 相关清单已由本节闭环**，其余遗留继续有效；'
        '⑨ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读）'
    )
    head, n = blk_pat.subn(blk_new, head, count=1)
    if n != 1:
        raise SystemExit('[FATAL] 「阻塞 / 待用户决定」行命中 %d 次' % n)

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
        if not lines[j].strip():
            break
        entries.append(lines[j])
        j += 1
    new_entry = (
        '2026-10-30 11:25 §106 ✅✅ **v1.12 客户包 zip 闭环**'
        '⇒ ✅ **持锁重打完成**（等锁 2 220 s 不抢；两道闸门全过：包路径 **0 违规** ＋ 内部素材 **0 命中**）'
        '⇒ ✅ **14 218 文件 / 11 233 373 363 B**（82.1% / 758 s）＋ `testzip()` OK '
        '＋ **zip ⇄ 包目录逐字节一致** ＋ 原子改名'
        '⇒ ✅ **`app160` 14 PASS / 0 FAIL**（V7 模式感知特征全在 / V8 内部编号 0 命中 / '
        'V9 15.72 MB 资产 / V10 许可署名 / V11 语法全合法）'
        '⇒ ✅ **版本三处一致** dir/zip/manifest = 1.12 ⇒ **zip 半交付解除**'
        '⇒ 🔴 **真机项仍未做**（APP-043 / APP-041 / GUI APP-042 / 3 段配音 / MiniMax / APP-044 精度）'
        '⇒ 🔴 **本条需等 reviewer 复核**'
    )
    entries.insert(0, new_entry)
    while len(entries) > 15:
        entries.pop()
    head = '\n'.join(lines[:ri + 1] + [''] + entries + [''] + lines[j:])

    head_crlf = head.replace('\n', '\r\n').encode('utf-8')
    head_crlf = head_crlf.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

    body_new = APPEND_BODY.replace('\n', '\r\n').encode('utf-8')
    if not body_new.endswith(b'\r\n'):
        body_new += b'\r\n'

    body_old_orig = body_old
    sep = b'' if body_old.endswith(b'\r\n') else b'\r\n'
    out = head_crlf + body_old + sep + body_new

    if b'\r\n' not in out:
        raise SystemExit('[FATAL] 输出不是 CRLF')
    assert out.count(b'\n') == out.count(b'\r\n'), '存在裸 LF'
    assert out[len(head_crlf):len(head_crlf) + len(body_old_orig)] == body_old_orig, '旧正文被改动'
    secs_new = re.findall(rb'(?m)^## \xc2\xa7(\d+)', out)
    old_nums = [int(x) for x in old_sections]
    new_nums = [int(x) for x in secs_new]
    for n_ in old_nums:
        if n_ not in new_nums:
            raise SystemExit('[FATAL] 原有章节 §%d 丢失' % n_)
    assert new_nums.count(106) == 1, '§106 出现 %d 次' % new_nums.count(106)

    with open(STATUS, 'wb') as f:
        f.write(out)

    print('✅ 已追加 §106')
    print('   字节 %d → %d' % (len(raw), len(out)))
    print('   章节数 %d → %d' % (n_sec_old, len(new_nums)))
    print('   纯 CRLF / 旧正文逐字未变 / 原有章节一个不少 / §106 唯一: True')
    print('   最近更新条目数: %d（≤15）' % len(entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
