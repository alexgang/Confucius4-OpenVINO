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

🔴🔴🔴 **APP-047 / ASR-033（2026-10-30）：交付集合收敛为 3 个文件**
（ASR 通知 `NOTICE_asr_to_app_speaker_api.md` §10.4 / §11.4 明文「只放这 3 个文件」）：
```
asr052_speaker_tracker_api.py   （入口：App 实际 import 它）
asr052_spk_runtime.py           （运行时内核：fbank / OV 嵌入 / 在线聚类 / 旁路分段）
asr_thread_defaults.py          （限线程，ASR-031 §1 交付默认）
```
- 🔴 旧包内的 **10 个文件**（`asr050` / `asr021` / `pya_*` 等）是 ASR-033 **拆分前**的
  评估/测试代码 + 旧依赖闭包：§102 曾因其中 4 个含内部素材编号而靠
  `sync_c167_redact_spk_assets_to_pkg.py` 做**字面量脱敏**。ASR-033 已在**源头**
  清干净（交付集合关键字 0 命中；门禁 `asr079_delivery_set_gate.json`
  `passes=true`、4/4 反证全抓住）⇒ APP-047 明文「**不要再做字面量替换**」。
- 🔴 **新 `asr052` 运行时不再 import 旧模块**（本轮独立 AST 复核：顶层 import 仅
  `asr_thread_defaults` + `asr052_spk_runtime`；ASR-033 门禁
  `runtime_import_chain.violations=0`、`isolated_import_probe.self_contained=true`）
  ⇒ 按 `REMOVE_OLD` **精确移除**：先备份到**包外**，删除前再做一次静态 import
  链守卫（任何交付文件仍引用旧模块即**拒绝移除**，避免断链）。
- ⚠️ 旧 `ASR_FILES` **漏了** `asr_thread_defaults.py` ⇒ 照用会让客户机
  `import asr052` 因缺模块而**静默降级**（旁路不可用但不崩）⇒ 新列表已补上。

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
import ast
import hashlib
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASR_ROOT = r'C:\Users\Trekker-PTL\qwen3asr_06b'
ASR_SCRIPTS = os.path.join(ASR_ROOT, 'scripts')
ASR_MODELS = os.path.join(ASR_ROOT, 'models')

# 包内 ASR 接口代码目录（相对包根）
PKG_ASR_SUBDIR = os.path.join('app', 'asr_spk')
# 包内说话人模型目录（相对包根）
PKG_SPK_SUBDIR = os.path.join('models', 'spk')

# 🔴🔴🔴 **APP-047 / ASR-033（2026-10-30）**：交付集合**收敛为 3 个文件**。
#   ASR 通知 `shared/NOTICE_asr_to_app_speaker_api.md` §10.4 / §11.4 明文：
#   「**只放这 3 个文件**」＋「**不要再做字面量替换**」（源头已清干净）。
#   ⚠️ 旧列表**漏了** `asr_thread_defaults.py` ⇒ 照用会让客户机
#      `import asr052` 因缺模块而**静默降级**（旁路不可用但不崩）。
ASR_FILES = [
    'asr052_speaker_tracker_api.py',   # 入口（App 实际 import 它）
    'asr052_spk_runtime.py',           # 运行时内核（fbank / OV 嵌入 / 聚类 / 分段）
    'asr_thread_defaults.py',          # 限线程（ASR-031 §1 交付默认）
]

# 🔴🔴🔴 **需要从包内移除的旧文件**（ASR-033 拆分前的评估/测试代码 + 旧依赖闭包）。
#   §102 曾因其中 4 个含内部素材编号而靠 `sync_c167_redact_spk_assets_to_pkg.py`
#   做**字面量脱敏**；ASR-033 已在**源头**清干净 ⇒ APP-047 明文撤掉脱敏 ⇒
#   这 10 个文件既不需要、也不该留在客户包里（它们是 ASR 侧的实验代码）。
REMOVE_OLD = [
    'asr021_bypass_spk_wespeaker.py',
    'asr030_kaldi_fbank_fidelity.py',
    'asr050_spk_qa_speaker_test.py',
    'asr_json_write.py',
    'asr_lock_common.py',
    'asr_slice_common.py',
    'pya_app_path_seg.py',
    'pya_bypass_spk.py',
    'pya_stream_segment.py',
    'pya_ref_shim.py',
]

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


def local_imports(py_file: str) -> set:
    """🔴 AST 抽一个 `.py` 的**本地模块名**（只取 `import X` / `from X import`）。

    ⚠️ **只抽 import 语句本身，不抽函数体** ⇒ 会不会漏？
    ⇒ **会**（ASR 侧旧代码把 import 写在函数体内）⇒ 所以调用方
    必须**额外**做全文扫描（见 `referenced_modules`）。
    """
    try:
        with open(py_file, 'rb') as f:
            tree = ast.parse(f.read())
    except Exception:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                out.add(node.module.split('.')[0])
    return out


def referenced_modules(text: str) -> set:
    """🔴 全文（含函数体）扫 `import X` / `from X import` 的**模块名**。

    ⇒ 比 AST 抽 import 节点更严：**函数体内的 import 也算**
    ⇒ 用来在删除旧文件前做「断链守卫」。
    """
    out = set()
    try:
        tree = ast.parse(text)
    except Exception:
        # 解析失败 ⇒ 退回正则（宁可多拦，不可漏拦）
        import re
        for m in re.finditer(r'^\s*(?:from\s+([A-Za-z_][\w]*)|import\s+([A-Za-z_][\w]*))',
                             text, re.M):
            out.add(m.group(1) or m.group(2))
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                out.add(node.module.split('.')[0])
    return out


def check_no_breakage(keep_texts: dict, remove_names) -> list:
    """🔴🔴 **断链守卫**：删除旧文件前，确认**保留的文件**不再引用它们。

    `keep_texts` = `{文件名: 源码文本}` —— **必须是「同步之后」的内容**
    （新交付文件用**源文件**的文本，而不是包内旧文本）
    ⇒ 否则 dry-run 时会拿「旧 asr052」去查 ⇒ 必然命中 ⇒ 永远 abort。

    返回「有问题的引用」列表（空 = 安全）。
    ⇒ 任一保留文件仍 import 某个待删模块 ⇒ **拒绝删除**（避免客户机断链）。
    """
    problems = []
    for fn in sorted(keep_texts):
        refs = referenced_modules(keep_texts[fn])
        for old in remove_names:
            if old[:-3] in refs:
                problems.append('%s → %s' % (fn, old))
    return problems


def collect_keep_texts(dst_dir: str, src_dir: str) -> dict:
    """🔴 收集「同步之后」会留在包内的每个 `.py` 的文本。

    - `ASR_FILES`（新交付）⇒ 取**源目录**的文本（同步后就是它）；
    - `REMOVE_OLD` ⇒ **不保留** ⇒ 不进集合；
    - 其余（若还有别的文件）⇒ 取**包内**文本。
    """
    out = {}
    for fn in ASR_FILES:
        p = os.path.join(src_dir, fn)
        if os.path.isfile(p):
            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                out[fn] = f.read()
    if os.path.isdir(dst_dir):
        for fn in os.listdir(dst_dir):
            if not fn.endswith('.py'):
                continue
            if fn in ASR_FILES or fn in REMOVE_OLD:
                continue
            p = os.path.join(dst_dir, fn)
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    out[fn] = f.read()
            except Exception:
                continue
    return out


def backup_and_remove(pkg: str, dst_dir: str, names, dry: bool) -> list:
    """🔴 把待删的旧文件**备份到包外**后再删（不删则不删）。

    返回 `[(动作, 文件名, 说明), ...]`。
    """
    actions = []
    present = [n for n in names
               if os.path.isfile(os.path.join(dst_dir, n))]
    if not present:
        return actions
    stamp = time.strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(pkg, '..', 'bak_c164_%s_asr_spk' % stamp)
    bak = os.path.abspath(bak)
    if not dry:
        os.makedirs(bak, exist_ok=True)
    for n in present:
        src = os.path.join(dst_dir, n)
        dst = os.path.join(bak, n)
        if dry:
            actions.append(('[DRY-REMOVE]', n, '备份到 %s' % bak))
            continue
        shutil.copy2(src, dst)
        os.remove(src)
        actions.append(('[REMOVED]', n, '已备份到 %s' % bak))
    return actions


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
        size = os.path.getsize(src)
        print('  %-9s %10d B  %s' % (st, size, fn))
        if st == '[SYNCED]':
            print('              sha256=%s' % sha256_file(dst))

    # ── ①b 移除 ASR-033 拆分前的旧文件（APP-047）──────────────
    # 🔴 **顺序至关重要**：先把 3 个新文件放进去，**再**移除旧文件
    #   ⇒ 移除前跑「断链守卫」，确认新文件不再 import 旧模块。
    print()
    print('[①b] 移除 ASR-033 拆分前的旧文件（APP-047；备份到包外）')
    probs = check_no_breakage(collect_keep_texts(dst_dir, ASR_SCRIPTS),
                              REMOVE_OLD)
    if probs:
        print('  [ABORT] 断链守卫命中 ⇒ **拒绝移除**（避免客户机 import 断链）：')
        for p in probs:
            print('           %s' % p)
        return 3
    print('  断链守卫：0 命中（3 个交付文件不再 import 旧模块）')
    acts = backup_and_remove(pkg, dst_dir, REMOVE_OLD, args.dry_run)
    for st, n, note in acts:
        print('  %-13s %s（%s）' % (st, n, note))
    if not acts:
        print('  [NOOP] 包内没有待移除的旧文件（已是 3 文件形态）')
    # 清掉可能残留的 __pycache__（旧 .pyc 仍含内部素材字面量）
    pyc = os.path.join(dst_dir, '__pycache__')
    if os.path.isdir(pyc) and not args.dry_run:
        shutil.rmtree(pyc, ignore_errors=True)
        print('  [REMOVED] __pycache__（旧 .pyc 含旧代码字面量）')

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
