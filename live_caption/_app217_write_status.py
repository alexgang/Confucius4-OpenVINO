#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 §217 写进 `status/app/STATUS_APP.md`（活文档）。

纪律（APP-052④ + §185 归档纪律）：
- 活文档逼近 40 000 B ⇒ **先归档**（把较旧的「最近更新」条目**整块逐字**归档到
  `status/archive/` 的**新文件**）⇒ 再追加 §217；
- 归档件 **write-once**（已存在就中止）；
- **只追加，不回改旧正文**；头部只动 `last_ack` 与「更新时间」两行；
- **写前自检 + 还原式复核**（把本轮每一处增量**逐一逆向还原** ⇒ 必须回到原字节）
  ⇒ **自检 FAIL ⇒ 源文件零改动**；
- 一律「临时文件 → `os.replace`」；写后再独立复核（UTF-8 **文本**比对）。
"""
import hashlib
import os
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
LIVE = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive',
                    'STATUS_APP_recent_updates_20261115_20261117.md')
TS = '2026-11-20 18:28:18'   # ← Get-Date 实测

# ── 要归档的 5 条较旧「最近更新」条目的**锚点**（唯一命中） ──
OLD_ENTRIES = [
    '> 🔴 2026-11-20 10:29 ｜ **开始执行 APP-116**',
    '> 🔴 2026-11-17 10:33 ｜ **执行 APP-114**',
    '> 🔴 2026-11-16 21:00:08 ｜ **执行 APP-113**',
    '> 🔴 2026-11-16 14:48 ｜ **执行 APP-112**',
    '> 🔴 2026-11-15 12:16 ｜ **执行 APP-110 / APP-111**',
]

NEW_RU = (
    '> 🔴 2026-11-20 18:28 ｜ **执行 APP-116 / APP-117 / APP-118**'
    '（last_ack=APP-116 → **APP-118**）：**v2.5 = 全集**'
    '（CUDA TTS ＋ Qwen3-ASR 0.6B ＋ EXT v0.4.18 ＋ 10 语种 ＋ '
    'APP-096～117 全部修复）｜**一份代码三形态**（`package_profiles.py` 的 '
    '`full`/`minimvp`/`specialmvp`，dry-run 清单已出）｜🟢 **10 语种真跑 '
    '10/10 配音 ＋ 10/10 字幕**（连修 **3 处「判据自身」缺陷**）｜🟢 **EXT '
    'v0.4.18 冒烟 7/7**｜🟢 **预设 B（男声）CER 0.0048／WER 0.0，与预设 A '
    '逐项相等**，抽听样本 4 条已落盘｜🟢 **整包 24.26 GiB / 48 789 文件**｜'
    '🟢 **CUDA 档 10 分钟整链 PASS**（150==150 / 丢弃 0 / RTF P90 0.6314）｜'
    '🔴 **完整版**出厂默认**（ASR+MT+TTS 全 GPU.0）10 分钟整链 **FAIL**'
    '（OV 集显 RTF≈4.4 ⇒ 积压 917 s ⇒ **既有局限，非 v2.5 回归**）｜'
    '🔴 **未打 zip**（用户规则：不通知不打包）｜**本条需等 reviewer 复核**'
)

NEW_ROW = (
    '| **完整版 v2.5（本轮交付，「全集」形态）** | '
    '🔴 **目录已出、**未打 zip**（用户长期规则：**不通知 ⇒ 不打包**）：'
    'ASR＝R2T2 1.7B **＋** Qwen3-ASR 0.6B stateful INT8（可选）｜'
    'MT＝Hy-MT2 **INT8-CW**（默认，INT4 保留可选）｜'
    'TTS＝**OV（出厂默认，未改）＋ NVIDIA CUDA（手动选）**｜**10 语种**｜'
    'EXT **v0.4.18**（`live_dub_ext@ee45ce5`）｜`preset_A.wav` **在包**、'
    '**`preset_B.wav` 不在包**（等用户抽听点头，APP-116 §2；回转写 CER 0.0048／WER 0.0，与预设 A 逐项相等）｜'
    '**24.26 GiB / 48 789 文件**｜**不含**录音/同事音色/克隆音色/babelvox 样本｜'
    '🔴 **出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL**（OV 集显追不上）'
    '⇒ **等用户裁定**默认摆放 | '
    '`results/app/app118_pkg_size.json` → `total_bytes=26048403469` / '
    '`total_files=48789`；`app118_model_identity_evidence.json`；'
    '`app118_lang10_evidence.json` → `pass=10 fail=0`；'
    '`app118_ext_smoke_evidence.json` → `pass=7 fail=0`；'
    '`app116_preset_eval/preset_eval.json` → `summary.B.cer_zh=0.0048`；'
    '`app591_acceptance_app118_v25_zh_cuda_run20261120-164527.json`；'
    '本文件 §217 |'
)

NEW_SEC = """
## §217 执行 **APP-116 / APP-117 / APP-118**（last_ack=APP-118，2026-11-20 18:28）｜🟢 **v2.5 = 全集**（CUDA＋0.6B＋EXT v0.4.18＋10 语种）｜🟢 **10 语种真跑 10/10 配音＋10/10 字幕**｜🟢 **EXT 冒烟 7/7**｜🟢 **预设 B（男声）CER 0.0048／WER 0.0 ＝ 与预设 A 逐项相等**｜🟢 **整包 24.26 GiB**｜🔴 **完整版出厂默认 10 分钟整链 FAIL（OV 集显追不上 ⇒ 既有局限，非 v2.5 回归）**｜🔴 **未打 zip**
> 🔴 **本节正文已整块逐字落 companion** ⇒ `status/app/STATUS_APP_sec217_detail_20261120.md`（**32 797 B**／SHA `8c2cc27e…`；APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
"""


def main():
    orig = open(LIVE, encoding='utf-8').read()
    orig_bytes = orig.encode('utf-8')
    print('开工：%d B / %d 行' % (len(orig_bytes), orig.count('\n') + 1))

    if os.path.exists(ARCH):
        print('ABORT: 归档件已存在 ⇒ write-once 纪律：%s' % ARCH)
        return 1

    # ── 定位要归档的 4 条（逐条唯一命中） ─────────────────────
    lines = orig.split('\n')
    picked = []
    for anchor in OLD_ENTRIES:
        hits = [i for i, l in enumerate(lines) if l.startswith(anchor)]
        if len(hits) != 1:
            print('ABORT: 锚点命中 %d 次（%s）' % (len(hits), anchor[:40]))
            return 1
        picked.append((hits[0], lines[hits[0]]))
    picked.sort()
    print('归档条目：%s' % [p[1][:22] for p in picked])

    # ── 组装归档件（逐字，含原锚点行） ───────────────────────
    arch_body = ('# STATUS_APP 「最近更新」逐字归档（2026-11-15 12:16 ～ '
                 '2026-11-17 10:33 共 4 条）\n\n'
                 '> 🔴 本文件是 `status/app/STATUS_APP.md` 里「最近更新」一节'
                 '**较早 4 条条目**的**整块逐字归档**（write-once）。\n'
                 '> 活文档对应位置只留**一行指针**；**原文一字未删、未改**。\n\n')
    for _, line in picked:
        arch_body += line + '\n\n'
    arch_bytes = arch_body.encode('utf-8')
    arch_sha = hashlib.sha256(arch_bytes).hexdigest()

    pointer = (
        '> 🔴 本节 5 条较旧「最近更新」条目（🔴 2026-11-20 10:29／'
        '🔴 2026-11-17 10:33／🔴 2026-11-16 21:00:08／🔴 2026-11-16 14:48／'
        '🔴 2026-11-15 12:16）原文已**整块逐字归档** ⇒ `status/archive/'
        'STATUS_APP_recent_updates_20261115_20261117.md`（%d B／块 SHA256 `%s`）；'
        '**原文一字未删、未改**。活文档本节只留本行 ＋ 最新 1 条。'
        % (len(arch_bytes), arch_sha))

    # ── 逐处增量（记下来，后面逐一逆向还原） ─────────────────
    edits = []          # [(old, new, 说明)]

    # T1/T2：头部两行
    old_ack = 'last_ack: APP-116'
    new_ack = 'last_ack: APP-118'
    if orig.count(old_ack) != 1:
        print('ABORT: last_ack 行命中 %d 次' % orig.count(old_ack))
        return 1
    edits.append((old_ack, new_ack, '头部 last_ack'))

    old_ts = '更新时间: 2026-11-20 11:21:33'
    if orig.count(old_ts) != 1:
        print('ABORT: 更新时间行命中 %d 次' % orig.count(old_ts))
        return 1
    new_ts = '更新时间: %s' % TS
    edits.append((old_ts, new_ts, '头部 更新时间'))

    # T3：归档 4 条 ⇒ 1 行指针
    arch_block = '\n'.join(p[1] for p in picked)
    if orig.count(arch_block) != 1:
        print('ABORT: 归档块命中 %d 次' % orig.count(arch_block))
        return 1
    edits.append((arch_block, pointer, '最近更新 4 条 ⇒ 指针行'))

    # T4：新增「最近更新」条目（插在 ## 最近更新 之后）
    anchor_ru = '## 最近更新\n'
    if orig.count(anchor_ru) != 1:
        print('ABORT: 「## 最近更新」命中 %d 次' % orig.count(anchor_ru))
        return 1
    edits.append((anchor_ru, anchor_ru + NEW_RU + '\n', '新增最近更新条目'))

    # T5：新增交付配置表行（插在「客户包目录」行之后）
    row_lines = [l for l in orig.split('\n') if l.startswith('| 客户包目录 |')]
    if len(row_lines) != 1:
        print('ABORT: 「客户包目录」行命中 %d 次' % len(row_lines))
        return 1
    edits.append((row_lines[0], row_lines[0] + '\n' + NEW_ROW, '新增 v2.5 交付行'))

    # T6：追加 §217
    edits.append(('', NEW_SEC, '追加 §217'))

    # ── 正向生成 ─────────────────────────────────────────────
    new = orig
    for old, new_, _why in edits:
        if old:
            if new.count(old) != 1:
                print('ABORT: 正向替换命中 %d 次（%s）' % (new.count(old), _why))
                return 1
            new = new.replace(old, new_, 1)
        else:
            new = new + new_
    new_bytes = new.encode('utf-8')

    # ── 还原式复核：把每一处增量**逆向还原** ⇒ 必须回到原字节 ──
    undo = new
    for old, new_, _why in reversed(edits):
        if old:
            if undo.count(new_) != 1:
                print('ABORT: 逆向还原命中 %d 次（%s）' % (undo.count(new_), _why))
                return 1
            undo = undo.replace(new_, old, 1)
        else:
            if not undo.endswith(new_):
                print('ABORT: 逆向还原（追加块）失败')
                return 1
            undo = undo[:-len(new_)]
    if undo.encode('utf-8') != orig_bytes:
        print('ABORT: 还原式复核 FAIL ⇒ 源文件零改动')
        return 1
    print('还原式复核：PASS（逆向还原 == 原字节 %d B）' % len(orig_bytes))

    # ── 写前自检 ─────────────────────────────────────────────
    # 🔴 「旧正文逐字未变」**不能**用 `new.startswith(orig)` 判
    #   （新「最近更新」条目插在**文档前部** ⇒ 原文不是新文本的前缀）
    #   ⇒ 改判：**orig 的每一行**（除被替换的块外）都必须**原样出现在 new 里**。
    replaced_blocks = set()
    for old, _new_, _w in edits:
        if old:
            replaced_blocks.add(old)
    untouched_lines = []
    for ln in orig.split('\n'):
        if any(ln in blk for blk in replaced_blocks):
            continue
        untouched_lines.append(ln)
    lost = [ln for ln in untouched_lines if ln and ln not in new]
    checks = [
        ('旧正文每一行都还在（未被替换的行逐行核对）', not lost),
        ('§217 已追加', '## §217 执行 **APP-116 / APP-117 / APP-118**' in new),
        ('last_ack = APP-118', 'last_ack: APP-118' in new),
        ('旧 last_ack 已不在', 'last_ack: APP-116' not in new),
        ('归档指针行已写入', 'STATUS_APP_recent_updates_20261115_20261117.md' in new),
        ('4 条旧条目已不在活文档',
         all(a not in new for a in OLD_ENTRIES)),
        ('新交付行已写入', '完整版 v2.5（本轮交付' in new),
        ('≤ 40 000 B 限额', len(new_bytes) <= 40000),
        ('≤ 300 行限额', new.count('\n') + 1 <= 300),
    ]
    print('新大小 %d B（%+d）／%d 行' % (len(new_bytes),
                                          len(new_bytes) - len(orig_bytes),
                                          new.count('\n') + 1))
    if lost:
        print('丢失的行（前 3）：%s' % lost[:3])
    bad = [n for n, ok in checks if not ok]
    if bad:
        print('写前自检 FAIL：%s ⇒ 源文件零改动' % bad)
        return 1
    print('写前自检 %d/%d PASS；新大小 %d B / %d 行'
          % (len(checks), len(checks), len(new_bytes), new.count('\n') + 1))

    # ── 落盘（临时文件 → os.replace） ─────────────────────────
    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.bak_20261120_1824.md')
    shutil.copyfile(LIVE, bak)
    print('备份：%s（%d B）' % (bak, os.path.getsize(bak)))

    tmp_arch = ARCH + '.tmp'
    with open(tmp_arch, 'w', encoding='utf-8', newline='') as f:
        f.write(arch_body)
    os.replace(tmp_arch, ARCH)

    tmp_live = LIVE + '.tmp'
    with open(tmp_live, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp_live, LIVE)

    # ── 写后复核（独立再读，UTF-8 **文本**比对） ───────────────
    back = open(LIVE, encoding='utf-8').read()
    arch_back = open(ARCH, encoding='utf-8').read()
    post = [
        ('活文档字节数 = 写前计算',
         len(back.encode('utf-8')) == len(new_bytes)),
        ('活文档可被 UTF-8 解码', True),
        ('旧正文**除被替换块外**逐行仍在', not lost),
        ('归档件逐字命中（含全部锚点行）',
         all(a in arch_back for a in OLD_ENTRIES)),
        ('归档件字节数 = 写前计算',
         len(arch_back.encode('utf-8')) == len(arch_bytes)),
        ('归档件 SHA256 = 写前计算',
         hashlib.sha256(arch_back.encode('utf-8')).hexdigest() == arch_sha),
        ('§217 在活文档', '## §217 执行' in back),
        ('last_ack = APP-118', 'last_ack: APP-118' in back),
        ('≤ 40 000 B', len(back.encode('utf-8')) <= 40000),
    ]
    bad = [n for n, ok in post if not ok]
    if bad:
        print('写后复核 FAIL：%s' % bad)
        return 1
    print('写后复核 %d/%d PASS' % (len(post), len(post)))
    print('活文档：%d B → %d B（SHA %s）'
          % (len(orig_bytes), len(back.encode('utf-8')),
             hashlib.sha256(back.encode('utf-8')).hexdigest()[:16]))
    print('归档件：%s（%d B／SHA %s）'
          % (ARCH, len(arch_bytes), arch_sha[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
