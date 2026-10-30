#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c165_spk_license_to_pkg.py —— §101 / APP-044：把说话人模型的**许可署名**加进客户包。

## 为什么必须做（APP-044 原文）

> 许可：pyannote/segmentation-3.0 是 MIT，wespeaker 是 CC-BY-4.0，
> **必须在包里的 NOTICE 或第三方许可清单里署名**（来源、作者、许可证全文或链接）。
> ASR 已经交过 NOTICE 草稿，合并进包里的 third-party 清单。

🔴 记忆铁律 §八：**客户包 `NOTICE`/`THIRD_PARTY.md` 的许可声明必须逐包实测**
⇒ 禁止笼统写「所有组件均为 Apache-2.0」。

## 🔴 署名义务的「触发条件」变化（重要）

ASR 通知（2026-10-28）说：**包内不带权重 ⇒ 署名义务免除**（App 已回告）。
APP-044（2026-10-30 08:50）**决定带上** wespeaker 与 pyannote 的 OV IR
⇒ ⇒ **署名义务重新成立** ⇒ 必须补上。

## 署名文本的来源

- **wespeaker**：直接采用 ASR 通知 `NOTICE_asr_to_app_wespeaker_license_20261028.md`
  §三 的**原样署名文本**（含 HF repo id / revision sha / license / 数据集 / 版权）。
- **pyannote**：ASR 侧**没有**交许可草稿 ⇒ 本脚本按公开来源取证后写入：
  - repo：`pyannote/segmentation-3.0`（MIT，模型卡 `license: mit`）
  - 作者/版权：Hervé Bredin 与 pyannote.audio 贡献者（MIT 许可声明）
  - 训练数据（模型卡自述）：AISHELL、AliMeeting、AMI、AVA-AVD、DIHARD、
    Ego4D、MSDWild、REPERE、VoxConverse

## 同步方式（铁律：定点替换 + 唯一命中断言）

对 `NOTICE` 与 `THIRD_PARTY.md` 各做**一次唯一命中**的字符串插入
⇒ 幂等（已插入则报 `[ALREADY]`）。

## 用法

```
python sync_c165_spk_license_to_pkg.py --pkg <包根> [--dry-run]
```
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 署名文本 ────────────────────────────────────────────────────
# wespeaker：ASR 通知 §三 的**原样**署名文本（不得改写）
WES_TEXT = """pyannote/wespeaker-voxceleb-resnet34-LM (WeSpeaker ResNet34)
  https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM
  revision: 837717ddb9ff5507820346191109dc79c958d614
  License: Creative Commons Attribution 4.0 International (CC BY 4.0)
           https://creativecommons.org/licenses/by/4.0/
  Training data: VoxCeleb
  Copyright (c) the VoxCeleb authors / respective contributors
  本包内形态：OpenVINO IR（models/spk/wespeaker-resnet34-<精度>/）
  使用范围限制：wespeaker 向量**只用于说话人聚类**（把段归到 spk id）；
                绝不用于 TTS 克隆音色（克隆必须用 Qwen3-TTS 自己的 x-vector）。
"""

# pyannote：ASR 侧未交草稿 ⇒ 按公开来源取证后写入
PYANNOTE_TEXT = """pyannote/segmentation-3.0 (PyanNet 说话人分段)
  https://huggingface.co/pyannote/segmentation-3.0
  License: MIT
  Authors: Herve Bredin and the pyannote.audio contributors
  Copyright (c) the pyannote.audio project contributors
  License text: https://opensource.org/licenses/MIT
  Training data (per model card): AISHELL, AliMeeting, AMI, AVA-AVD,
    DIHARD, Ego4D, MSDWild, REPERE, VoxConverse
  本包内形态：OpenVINO IR（models/spk/pyannote_seg_3_0/<精度>/）
"""

NOTICE_ANCHOR = """------------------------------------------------------------------------
目录说明
------------------------------------------------------------------------"""

NOTICE_NEW = """------------------------------------------------------------------------
说话人识别模型（APP-044：随包分发，须署名）
------------------------------------------------------------------------
""" + WES_TEXT + """
""" + PYANNOTE_TEXT + """
------------------------------------------------------------------------
目录说明
------------------------------------------------------------------------"""

TP_ANCHOR = """Model weights:
"""

TP_NEW = """Model weights:

- WeSpeaker ResNet34 (`pyannote/wespeaker-voxceleb-resnet34-LM`, CC BY 4.0) — bundled in `models\\spk\\wespeaker-resnet34-<precision>\\` as OpenVINO IR; used **only** for speaker clustering (assigning segments to spk ids), never for TTS voice cloning.
- pyannote/segmentation-3.0 (PyanNet speaker segmentation, MIT) — bundled in `models\\spk\\pyannote_seg_3_0\\<precision>\\` as OpenVINO IR; used for the speaker-diarization sidecar (speech/speaker-change/overlap frames).
"""

# 判定「已插入」的标记（幂等用）
NOTICE_MARK = '说话人识别模型（APP-044：随包分发，须署名）'
TP_MARK = 'models\\spk\\wespeaker-resnet34-<precision>\\'


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def patch_one(path: str, anchor: str, new_block: str, mark: str,
              dry: bool = False) -> str:
    """在 `anchor` 处**唯一命中**地插入 `new_block`。

    🔴 **行尾无关**：包内两个许可文件的行尾**不同**
    （实测 `NOTICE` = 纯 LF 128 行；`THIRD_PARTY.md` = 纯 CRLF 67 行）
    ⇒ 若用固定 `\\n` 锚点去匹配 CRLF 文件，`text.count(anchor)` 恒为 0
    ⇒ 会误报「锚点命中 0 次」。

    做法：**读入后统一归一化为 `\\n`** 再计数/替换，
    **写回时按原文件行尾还原** ⇒ 既不改动既有行的行尾，也不破坏文件原貌。
    """
    with open(path, 'rb') as f:
        raw = f.read()
    use_crlf = b'\r\n' in raw
    text = raw.decode('utf-8')
    if use_crlf:
        text = text.replace('\r\n', '\n')

    if mark in text:
        return '[ALREADY]'
    n = text.count(anchor)
    if n != 1:
        raise RuntimeError('锚点命中 %d 次（要求恰好 1 次）：%s' % (n, path))
    patched = text.replace(anchor, new_block, 1)
    if dry:
        return '[DRY]'
    if use_crlf:
        patched = patched.replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(patched.encode('utf-8'))
    return '[SYNCED]'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    pkg = args.pkg
    if not pkg:
        import glob
        cands = [c for c in sorted(
            glob.glob(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v*'))
            if os.path.isdir(c)]
        if not cands:
            print('找不到客户包目录，请用 --pkg 指定')
            return 2
        pkg = cands[-1]

    print('客户包 = %s' % pkg)
    if args.dry_run:
        print('（dry-run：不落盘）')
    print()

    jobs = [
        ('NOTICE', NOTICE_ANCHOR, NOTICE_NEW, NOTICE_MARK),
        ('THIRD_PARTY.md', TP_ANCHOR, TP_NEW, TP_MARK),
    ]
    for name, anchor, block, mark in jobs:
        p = os.path.join(pkg, name)
        if not os.path.isfile(p):
            print('  [MISSING] %s' % name)
            continue
        try:
            st = patch_one(p, anchor, block, mark, args.dry_run)
        except RuntimeError as e:
            print('  [FAIL] %s：%s' % (name, e))
            return 1
        size = os.path.getsize(p)
        print('  %-9s %-16s %8d B  sha256=%s'
              % (st, name, size, sha256_file(p)))

    print()
    print('完成。⚠️ NOTICE/THIRD_PARTY.md **在 zip 内** ⇒ 需重打包才生效。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
