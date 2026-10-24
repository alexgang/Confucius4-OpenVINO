"""更新 STATUS_APP.md 头部 + 追加 §27（只用 §1 锚点切片；新章节追加在文件末尾）。"""
import io, os, re, subprocess, sys

P = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
SEC = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app027_status_section.md'

b = open(P, 'rb').read()
crlf = b'\r\n' in b
text = b.decode('utf-8')
lines = text.split('\r\n') if crlf else text.split('\n')

# ── 1. 找第一个章节锚点（§1）──
i_s1 = None
for i, l in enumerate(lines):
    if l.startswith('## §1 '):
        i_s1 = i
        break
assert i_s1 is not None, '找不到 §1 锚点'
header = lines[:i_s1]
body = lines[i_s1:]
print('锚点 i_s1 =', i_s1, ' header行数 =', len(header), ' body行数 =', len(body))

# ── 2. 改头部 4 个字段（只改值，行数不变）──
NEW_TASK = ('**巡检（无新纠偏条目，第 11 次同一口径）+ ✅ 交付 zip 重打闭环（§27）**'
            '：`last_ack` = **APP-010**（本轮**无新条目待执行**）⇒ 本轮闭环 §26 头部遗留的**阻塞项①**'
            '—— 🔴 **交付 zip 已重打并复核通过**（持共享机器锁 `app-pack` PID 21324 / 14 min 39 s / '
            '原子写 `os.replace` ⇒ **没有**再出现「好包被截断覆盖」）⇒ zip **11 216 047 396 B** / '
            '**13 978** 条目 / `testzip()=None` / EOCD 签名在 / 内容级复核 **13 978 文件逐字节一致** / '
            '独立脚本 `verify_pkg_zip.py` **PASS** / 仓库⇄包 **16/16** ⇒ FTP_Share 已重发（'
            '**11 216 047 396 B**，SHA256 `01ebfebe…` 与主包**一致**）⇒ 🔴 `.tmp` 坏残包**已消失**；'
            '客户包合规逐项实测通过（**0** 个 `*_spoken.*`、音色目录**只有 `preset_A.wav`**、'
            '无会议录音/克隆素材/同事音色 B、APP-008① 标注 L392/L394 **在**、APP-010 实验性标注 L42/L44/L390 **在**）；'
            '⏳ **仍等 reviewer 裁定**：渲染层三处（`_mt_of`/`_save_text`/CLI `run_cli` 改按 `mt_units()`）'
            '⇒ 字幕粒度属**产品行为变更**（行数 3.3×）⇒ 本轮**仍未改**（§26.6 三问已备齐证据）')

NEW_BLOCK = ('① 🟢 **交付 zip 阻塞项已闭环**：`Confucius4_LiveCaption_v1.4.zip` = **11 216 047 396 B**'
             '（2026-10-25 01:59:18，SHA256 `01ebfebe…`）**13 978** 条目 / `testzip()=None` / EOCD 在 / '
             '内容级 **13 978 文件逐字节一致** / 独立复核 PASS / 仓库⇄包 16/16；'
             '`FTP_Share/` 副本**同字节同 SHA256**（02:04:11）⇒ **§26 头部「交付 zip 是坏的」已在 §27.1.6 更正**；'
             '② 🔴 **渲染层改按 `mt_units()` 逐句渲染**（MT §4.3 三处）—— **本轮仍未改**，'
             '等 reviewer 裁定（§26.6 三问；行数 436 → 1424，3.3×）；'
             '③ ⛔ **GitHub 旧 SHA 的 gc** 未做 ⇒ 待用户决定；'
             '④ ⛔ **APP-009② 的 MT UNIT 方案 A/B/C/D 结论**仍在 v4 复算 ⇒ 渲染层改动还等它定案；'
             '⑤ ⛔ **v1.4 TTS 音质**未达标（TTS-009/TTS-010）⇒ TTS 保持实验性、默认关闭（包内已标注）；'
             '⑥ ⛔ **包体 12.73 GB** 优化未做；'
             '⑦ ⛔ **V7 残句代价**待用户确认（链首段半句残句 12 段语料 5 行/58 字）')

NEW_TIME = '2026-10-25 02:08'


def set_field(lines, key, value):
    """替换 `key: ...` 这一行的值；断言前缀只出现一次。"""
    idx = [i for i, l in enumerate(lines) if l.startswith(key + ':')]
    assert len(idx) == 1, (key, idx)
    i = idx[0]
    assert value.count(key + ':') == 0, 'value 不得重复前缀'
    lines[i] = key + ': ' + value
    return lines


header = set_field(header, 'last_ack', 'APP-010')
header = set_field(header, '更新时间', NEW_TIME)
header = set_field(header, '当前任务', NEW_TASK)
header = set_field(header, '阻塞 / 待用户决定', NEW_BLOCK)

# ── 3. 「最近更新」区块：新的写在最上面，最多 15 行 ──
i_ru = None
for i, l in enumerate(header):
    if l.strip() == '## 最近更新':
        i_ru = i
        break
assert i_ru is not None
NEW_ROWS = [
    '- 02:08 §27 ✅ **交付 zip 重打闭环（本轮核心）**：持共享机器锁（`app-pack` / PID 21324 / 01:47:44）'
    '→ `pack_v13.py` 14 min 39 s → **原子写**（`ZIP.tmp` → 校验 → `os.replace`）⇒ **没有**再出现「好包被截断覆盖」；'
    '内容级校验 **13 978 文件逐字节一致**、MANIFEST `version=1.4`/`files=13977`、`testzip()=None`、EOCD 签名在 ⇒ **PASS**。',
    '- 02:08 §27 ✅ **独立复核 + FTP_Share 重发**：`verify_pkg_zip.py` **PASS**（zip⇄包 13 978 一致、仓库⇄包 **16/16**）；'
    '`publish_ftp.py` 持锁 `app-ftppub` 复制 **11 216 047 396 B**（9.0 s / 1 188.9 MB/s），'
    '源⇄副本 SHA256 `01ebfebe…` **一致** ⇒ **PASS**；🔴 **未重开 FTP 服务**（守 APP-009③）。',
    '- 02:08 §27 ✅ **客户包合规逐项实测**：`*_spoken.*` **0** 个；包内音频 23 个里 **22 个是 scipy 自带测试数据**，'
    '非测试数据**只有** `models/qwen3tts/voices/preset_A.wav` ⇒ **无会议录音 / 无克隆音色 / 无同事音色 B**；'
    'APP-008① 标注 `README_zh.md` **L392**（待质量复核）**L394**（`LIVECAP_GUARD_REL=0`）**在**；'
    'APP-010 实验性标注 **L42/L44/L390** **在**。',
    '- 02:08 §27 ✅ **§26 头部「交付 zip 是坏的」已更正**（在本节更正，不改 §26 原文）：本包**完好**；'
    '🔴 §26 记录的 **8 271 022 632 B `.tmp` 坏残包已被删除**（`pack_v13.py` 清理路径）⇒ 磁盘上不再有第二个半成品 zip。',
    '- 02:08 §27 ⏳ **渲染层三处本轮仍不改**（`_mt_of`/`_save_text`/CLI `run_cli` 改按 `mt_units()`）'
    '⇒ 字幕显示粒度属**产品行为变更**（行数 436 → 1424，3.3×）⇒ **仍等 reviewer 裁定**（§26.6 三问，证据已备齐）。',
    '- 02:08 §27 ✅ **纪律**：**未改/未提交** `status/app/CORRECTIONS_APP.md`（SHA256 仍 `8ccf661c…` / 27 413 B）；'
    '**未吞** ASR/MT/TTS 的未提交改动；**未改产品代码**（4 个核心 .py 本轮零改动）；'
    '**未 import 被测模块**；**未跑推理/测速/占 GPU**；打包窗口内**未启动任何 `python.exe`** ⇒ 耗时数字未被自己污染。',
]
# 去掉旧的第一行（保持 ≤15 行）
old_rows = []
for l in header[i_ru + 1:]:
    if l.startswith('- '):
        old_rows.append(l)
    else:
        break
keep = old_rows[:max(0, 15 - len(NEW_ROWS))]
header = header[:i_ru + 1] + NEW_ROWS + keep + header[i_ru + 1 + len(old_rows):]

# ── 4. 追加新章节到文件末尾 ──
new_body = open(SEC, encoding='utf-8').read().split('\n')
while new_body and new_body[-1] == '':
    new_body.pop()
out = header + body + [''] + new_body + ['']
final = '\r\n'.join(out) if crlf else '\n'.join(out)

open(P, 'wb').write(final.encode('utf-8'))
print('写入完成；CRLF =', crlf, ' 总行数 =', len(out))
