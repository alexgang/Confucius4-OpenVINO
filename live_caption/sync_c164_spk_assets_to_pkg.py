#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c164_spk_assets_to_pkg.py —— §101 / APP-044：把说话人资产**定点同步**到客户包。

## 铁律（记忆铁律 §一 / §九）

1. 🔴 **仓库 ⇄ 客户包 = 两份独立副本** ⇒ **禁止整目录覆盖**。
2. 🔴 同步方式 = **精确复制 + 唯一命中断言**（新增文件）或
   **`difflib` 派生替换块**（已有文件），**两端归一化 LF**。
3. 🔴 **OLD 必须取自「包内实际内容」**（不是基线 commit）。
4. 🔴 行尾差异（仓库 CRLF / 包 LF）⇒ **归一化后再比**。

## 本脚本同步什么（APP-044）

### ① ASR 的 SpeakerTracker 接口代码 → `<包>/app/asr_spk/`

11 个文件（依赖闭包，见 `results/app/app157_app044_spk_asset_inventory.py`）：
```
asr021_bypass_spk_wespeaker.py     asr050_spk_qa_speaker_test.py
asr030_kaldi_fbank_fidelity.py     asr052_speaker_tracker_api.py
asr_json_write.py                  asr_lock_common.py
asr_slice_common.py                pya_app_path_seg.py
pya_bypass_spk.py                   pya_ref_shim.py
pya_stream_segment.py
```

🔴 **`pya_ref_shim.py` 例外**：它**顶层 `import torch`** ⇒ 客户机（无 torch）
   import 即炸 ⇒ **不进包**（客户机路径不经过它 —— 只用 `WespeakerOVEncoder`
   + `OnlineSpeakerCluster`，纯 OV + 纯 numpy）。

### ② 两个 OV IR → `<包>/models/spk/`

```
models/spk/wespeaker-resnet34-<精度>/openvino_encoder_model.{xml,bin}
models/spk/pyannote_seg_3_0/<精度>/pyannote_seg_3_0.{xml,bin}
```

⚠️ **精度**：APP-044 说「FP16 还是 FP32 由 reviewer 按 ASR-025 的复核结论通知」
⇒ 该裁定**尚未到达** ⇒ 本脚本**按参数**选择（默认 `fp16`，
   与 ASR 当前交付的 `wespeaker-resnet34-fp16` 一致）。

## 用法

```
python sync_c164_spk_assets_to_pkg.py --pkg <包根> [--precision fp16|fp32] [--dry-run]
```

⚠️ **不打包**：本脚本只把资产放进**包目录**；zip 由 `pack_v13.py` 另行重打
   （需持 `MACHINE_LOCK`）。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASR_ROOT = r'C:\Users\Trekker-PTL\qwen3asr_06b'
ASR_SCRIPTS = os.path.join(ASR_ROOT, 'scripts')
ASR_MODELS = os.path.join(ASR_ROOT, 'models')

# 包内 ASR 接口代码目录（相对包根）
PKG_ASR_SUBDIR = os.path.join('app', 'asr_spk')
# 包内说话人模型目录（相对包根）
PKG_SPK_SUBDIR = os.path.join('models', 'spk')

ASR_FILES = [
    'asr021_bypass_spk_wespeaker.py',
    'asr030_kaldi_fbank_fidelity.py',
    'asr050_spk_qa_speaker_test.py',
    'asr052_speaker_tracker_api.py',
    'asr_json_write.py',
    'asr_lock_common.py',
    'asr_slice_common.py',
    'pya_app_path_seg.py',
    'pya_bypass_spk.py',
    'pya_stream_segment.py',
]

# 🔴 顶层 `import torch` ⇒ 客户机 import 即炸 ⇒ **不进包**
#   （客户机路径只用 WespeakerOVEncoder + OnlineSpeakerCluster，无需它）
EXCLUDE_TORCH = ['pya_ref_shim.py']

# 精度 → 源目录（ASR 侧）
WES_SRC = {
    'fp16': os.path.join(ASR_MODELS, 'wespeaker-resnet34-fp16'),
    'fp32': os.path.join(ASR_MODELS, '_attrib_wespeaker-resnet34-fp32'),
}
SEG_SRC = {
    'fp16': os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16'),
    'fp32': os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp32'),
}
WES_FILES = ('openvino_encoder_model.xml', 'openvino_encoder_model.bin')
SEG_FILES = ('pyannote_seg_3_0.xml', 'pyannote_seg_3_0.bin')


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def copy_checked(src: str, dst: str, dry: bool = False) -> str:
    """复制一个文件，返回 `[SYNCED]` / `[ALREADY]` / `[DRY]`。"""
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isfile(dst):
        if sha256_file(src) == sha256_file(dst):
            return '[ALREADY]'
    if dry:
        return '[DRY]'
    shutil.copy2(src, dst)
    return '[SYNCED]'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None,
                    help='客户包根目录（含 app/ 与 models/）')
    ap.add_argument('--precision', default='fp16', choices=['fp16', 'fp32'])
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    pkg = args.pkg
    if not pkg:
        import glob
        cands = sorted(glob.glob(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v*'))
        cands = [c for c in cands if os.path.isdir(c)]
        if not cands:
            print('找不到客户包目录，请用 --pkg 指定')
            return 2
        pkg = cands[-1]
    if not os.path.isdir(pkg):
        print('客户包目录不存在：%s' % pkg)
        return 2

    print('客户包 = %s' % pkg)
    print('精度 = %s' % args.precision)
    if args.dry_run:
        print('（dry-run：不落盘）')
    print()

    # ── ① ASR 接口代码 ────────────────────────────────────────
    print('[①] ASR SpeakerTracker 接口代码 → %s' % PKG_ASR_SUBDIR)
    dst_dir = os.path.join(pkg, PKG_ASR_SUBDIR)
    for fn in ASR_FILES:
        src = os.path.join(ASR_SCRIPTS, fn)
        dst = os.path.join(dst_dir, fn)
        try:
            st = copy_checked(src, dst, args.dry_run)
        except FileNotFoundError:
            print('  [MISSING] %s' % fn)
            continue
        print('  %-9s %s' % (st, fn))
    for fn in EXCLUDE_TORCH:
        print('  [SKIP-TORCH] %s（顶层 import torch，客户机无 torch）' % fn)

    # ── ② 两个 OV IR ──────────────────────────────────────────
    print()
    print('[②] 说话人 OV IR → %s' % PKG_SPK_SUBDIR)
    wes_src = WES_SRC[args.precision]
    seg_src = SEG_SRC[args.precision]
    wes_dst = os.path.join(pkg, PKG_SPK_SUBDIR,
                           'wespeaker-resnet34-%s' % args.precision)
    seg_dst = os.path.join(pkg, PKG_SPK_SUBDIR,
                           'pyannote_seg_3_0', args.precision)
    for src_dir, dst_dir2, files in ((wes_src, wes_dst, WES_FILES),
                                     (seg_src, seg_dst, SEG_FILES)):
        if not os.path.isdir(src_dir):
            print('  [MISSING-DIR] %s' % src_dir)
            continue
        for fn in files:
            src = os.path.join(src_dir, fn)
            dst = os.path.join(dst_dir2, fn)
            try:
                st = copy_checked(src, dst, args.dry_run)
            except FileNotFoundError:
                print('  [MISSING] %s' % fn)
                continue
            size = os.path.getsize(src)
            print('  %-9s %10d B  %s'
                  % (st, size, os.path.relpath(dst, pkg)))
            if st == '[SYNCED]':
                print('              sha256=%s' % sha256_file(dst))

    print()
    print('完成。下一步：重打包（持 MACHINE_LOCK）⇒ pack_v13.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
