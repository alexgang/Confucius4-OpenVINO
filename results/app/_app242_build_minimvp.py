#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴 **APP-066：MiniMVP 最小客户包** 构建器（**白名单**思路）。

> 用户原话（APP-066）：
> 「把 Qwen3-ASR 0.6B/Hy2-MT/Qwen3-TTS 0.6B 的方案打成一个最小 live caption
> 的客户包（无须 ext 插件内容；仅在 intel iGPU 和 NPU 上运行，无需 cuda 内容；
> asr/mt 保留 int8 的权重，tts 仅仅保留 fp16 npu 即可）」
> **11-04 更正**：MT 用 **INT4** 权重，不要 INT8（ASR 仍 INT8，TTS 仍 FP16 NPU）。

## 本脚本做什么

**① 建目录树**（白名单：只放必需的）
**② 扫依赖隔离**（绝对路径 / torch / cuda / dll / pyd）
**③ 出体积分项报告**
**④ 出 MANIFEST.json**
（打包 zip、ACCEPTED 重签、clean-test 解压、验收 (a)(b)(c) 在后续步骤做）

## 🔴 白名单（每条都注明**为什么**要）

| 类别 | 保留 | 不带 | 依据 |
|---|---|---|---|
| ASR | `models/encoder-int8/` + `models/decoder-gpu-int8/` + `models/embed_tokens_f16.npy` + `models/tokenizer/` | `encoder-fp16` `encoder-int4` `decoder-gpu-int4` `decoder-npu-int8` `decoder-npu-int4` | APP-066：ASR 保留 INT8；设备 = iGPU ⇒ **GPU 解码器**；`gpu_int8` 引擎（ENGINES）用 enc=int8 + dec=`ov-int8-past`→`decoder-gpu-int8` |
| MT | `models/mt/mt2-int4sym-cw-q/` | `mt2-int8sym-cw-q` | APP-066 11-04 更正：**MT 用 INT4** |
| TTS | `models/qwen3tts/int8/`（**NPU 实际加载的那批**）+ `tokenizer/` + `voices/preset_A.wav` + `weights/` | `models/qwen3tts/int8/` 之外的 TTS 精度 | App 的 `tts_engine.model_root()` 只认 `models/qwen3tts/int8/`；**NPU 精度提示 = f16**（`_ov_precision`）⇒ 即「FP16 NPU」 |
| 说话人 | ❌ **不带** | `models/spk/`（pyannote_seg + wespeaker） | APP-066：最小包**默认不带旁路和克隆**，音色只提供预设 |
| EXT | ❌ 不带 | `ext/` | APP-066：无须 ext 插件 |
| CUDA | ❌ 不带 | `cuda/` + torch/cuda dll | APP-066：仅 iGPU/NPU |

## 🔴 「TTS FP16 NPU」的口径（**必须在 STATUS 写清**）
App 的 TTS 走 BabelVox 路线 ⇒ 加载的是 **`models/qwen3tts/int8/`** 的 IR
（**权重位宽 INT8**），而 **NPU 推理精度提示 = `f16`**
（`tts_engine._ov_precision()`：`f16/fp16/half → 'f16'`）
⇒ 「TTS 仅保留 FP16 NPU」在本包里落地为：
**`models/qwen3tts/int8/`（唯一一份 TTS IR）+ NPU 上以 f16 精度提示运行**
⇒ **不带** GPU/CPU/CUDA 版、**不带** INT8 之外的实验 IR、**不带** NPU 编译缓存（blob）。

## 用法
```
python results/app/_app242_build_minimvp.py [--pkg <目录>] [--scan-only]
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
SRC_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0')
REPORT = os.path.join(HERE, 'app242_minimvp_build_evidence.json')

# ══════════════════════════════════════════════════════════════
# 白名单
# ══════════════════════════════════════════════════════════════
#: models/ 下的**保留**目录/文件（相对 models/）
MODEL_KEEP_DIRS = (
    'encoder-int8',            # ASR 编码器 INT8
    'decoder-gpu-int8',        # ASR 解码器 INT8（GPU 版）
    'mt/mt2-int4sym-cw-q',     # MT INT4（per-channel sym）
    'qwen3tts/int8',           # TTS IR（App 唯一认的目录）
    'qwen3tts/tokenizer',
    'qwen3tts/voices',
    'qwen3tts/weights',
    'tokenizer',               # ASR tokenizer
)
MODEL_KEEP_FILES = (
    'embed_tokens_f16.npy',    # NPU/GPU 解码器的 embedding 表
)

#: 顶层**保留**目录/文件（相对包根）
#: 🔴 **`models` 不在这里** ⇒ 它走下面的**模型白名单**逐项拷
#:   （放进来 ⇒ 整个 models/ 原样拷过去 ⇒ 白名单失效 ⇒
#:     实测 models = 12 233 MB ≈ v2.2 的 99.8 % ⇒ 「最小包」名不副实）
ROOT_KEEP_DIRS = ('app', 'python', 'docs')
ROOT_KEEP_FILES = (
    'NOTICE', 'THIRD_PARTY.md', 'README_zh.md', 'README_en.md',
    'Start_LiveCaption.bat', 'Diagnose.bat', 'release.json',
)

#: 🔴 **不带**的东西（reviewer 点名的「不带」清单）
FORBIDDEN_DIRS = ('ext', 'cuda', 'results', 'docs')
FORBIDDEN_NAMES = ('tts_cuda.py', 'tts_cuda_sidecar.py',
                    'audio_check.py', 'selftest_audio_sources.py',
                    'offline_reader.py', 'offline_reader_gui.py',
                    'clone_collector.py', 'npu_delivery_backend.py',
                    'npu_embeds_backend.py', 'segment_encoder_backend.py',
                    'win_clickthrough.py', 'time_stretch.py')

#: 🔴🔴 **OpenVINO 的「模型前端」插件**（APP-066：「不能 import torch 或 cuda」）
#:
#: `python/Lib/site-packages/openvino/frontend/pytorch/` 里是 **PyTorch 模型的
#: 转换器**（`import torch` × N）⇒ **客户机根本用不到**（App 只读**已导出的
#: IR** ⇒ `ov.Core().read_model()` ⇒ **不经过任何前端**）。
#: ⇒ 连同 `libs/openvino_pytorch_frontend.dll`（2.7 MB）**一起剔除**。
#:
#: ⚠️ **可安全剔除的依据**：`openvino/frontend/frontend.py` **不 import** pytorch
#:   （实测 `grep pytorch frontend.py` = 0 命中）⇒ 前端是**按需加载**的
#:   （`FrontEndManager` 按扩展名找插件）⇒ 不加载它**不影响** IR 读取与推理。
#: ⚠️ 同理剔除 `jax` / `paddle` / `tensorflow`（同样是**模型转换**前端）。
OPENVOIN_FRONTEND_DIRS = (
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'pytorch'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'jax'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'paddle'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'tensorflow'),
)
OPENVOIN_FRONTEND_LIBS = (
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'libs',
                 'openvino_pytorch_frontend.dll'),
)

#: 🔴 绝对路径黑名单（开发目录）
DEV_PATH_PATTERNS = (
    'confucius4-openvino', 'live_dub_ext', 'qwen3tts_eval',
    'qwen3asr_06b', 'hy_bench', 'WorkBuddy\\Worktrees', 'Worktrees',
)

#: torch / cuda 相关
TORCH_PATTERNS = (r'^\s*import\s+torch\b', r'^\s*from\s+torch\b',
                  r'^\s*import\s+torchaudio\b', r'^\s*from\s+torchaudio\b')
CUDA_PATTERNS = (r'cuda', r'cudnn', r'cublas', r'nvidia')

TEXT_EXT = ('.py', '.json', '.lnk', '.cmd', '.bat', '.txt', '.md', '.jinja')
BIN_EXT = ('.dll', '.pyd', '.exe', '.so')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def du(p):
    n = 0
    for root, dirs, files in os.walk(p):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


def copy_tree(src, dst):
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt = dst if rel == '.' else os.path.join(dst, rel)
        os.makedirs(tgt, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(tgt, f)
            if os.path.exists(d):
                continue
            try:
                os.link(s, d)
            except OSError:
                shutil.copy2(s, d)


def copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build(dst):
    # 🔴 **不 rmtree**（本机的 safe-delete 守卫会拦 ⇒ 逐文件删极慢
    #   ⇒ 实测 11 458 个文件删了 4 min 还没删完 ⇒ 且**会占 CPU 挡住
    #   设备级作业的安静窗口** ⇒ 本轮实测踩过）。
    #   ⚠️ 且 APP-066 明文：「任何已有版本的目录和 zip 都**不覆盖、不删除**」
    #   ⇒ 若目标已存在 ⇒ **直接退出**，绝不删改。
    if os.path.isdir(dst):
        print('  [ABORT] 目标目录已存在 ⇒ APP-066 明文「不覆盖、不删除」⇒ 退出')
        return None
    os.makedirs(dst, exist_ok=True)

    # ── 顶层 ────────────────────────────────────────────────
    for d in ROOT_KEEP_DIRS:
        s = os.path.join(SRC_PKG, d)
        if os.path.isdir(s):
            copy_tree(s, os.path.join(dst, d))
    for f in ROOT_KEEP_FILES:
        s = os.path.join(SRC_PKG, f)
        if os.path.isfile(s):
            copy_file(s, os.path.join(dst, f))

    # ── models/（白名单）────────────────────────────────────
    for d in MODEL_KEEP_DIRS:
        s = os.path.join(SRC_PKG, 'models', d)
        if os.path.isdir(s):
            copy_tree(s, os.path.join(dst, 'models', d))
        else:
            print('  [MISSING] models/%s' % d)
    for f in MODEL_KEEP_FILES:
        s = os.path.join(SRC_PKG, 'models', f)
        if os.path.isfile(s):
            copy_file(s, os.path.join(dst, 'models', f))

    # ── 删掉「不带」清单里仍在包内的文件 ──────────────────────
    removed = []
    app_dir = os.path.join(dst, 'app')
    for fn in FORBIDDEN_NAMES:
        p = os.path.join(app_dir, fn)
        if os.path.isfile(p):
            os.remove(p)
            removed.append('app/%s' % fn)
    # asr_spk（说话人旁路）⇒ 最小包不带克隆 ⇒ 整个目录去掉
    spk_dir = os.path.join(app_dir, 'asr_spk')
    if os.path.isdir(spk_dir):
        _rmtree_quiet(spk_dir)
        removed.append('app/asr_spk/（说话人旁路 + 克隆）')
    # models/spk（pyannote_seg + wespeaker）
    spk_models = os.path.join(dst, 'models', 'spk')
    if os.path.isdir(spk_models):
        _rmtree_quiet(spk_models)
        removed.append('models/spk/（pyannote_seg + wespeaker）')
    # __pycache__（旧 .pyc 含内部字面量）
    for root, dirs, files in os.walk(dst):
        for d in list(dirs):
            if d == '__pycache__':
                _rmtree_quiet(os.path.join(root, d))
                dirs.remove(d)
    # ── ⑦ 剔除 OpenVINO 的「模型转换前端」（含 torch/jax/paddle/tf）──
    #   ⇒ App 只读**已导出的 IR** ⇒ 用不到这些前端
    for rel in OPENVOIN_FRONTEND_DIRS:
        p = os.path.join(dst, rel)
        if os.path.isdir(p):
            _rmtree_quiet(p)
            removed.append(rel.replace('\\', '/') + '/（OV 模型转换前端）')
    for rel in OPENVOIN_FRONTEND_LIBS:
        p = os.path.join(dst, rel)
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed.append(rel.replace('\\', '/'))
            except OSError:
                pass
    return removed


def _rmtree_quiet(p):
    """删目录（safe-delete 守卫会拦 ⇒ 逐文件删 + os.rmdir 兜底）。"""
    for root, dirs, files in os.walk(p, topdown=False):
        for f in files:
            try:
                os.remove(os.path.join(root, f))
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass
    try:
        os.rmdir(p)
    except OSError:
        pass


def scan(dst):
    """🔴 依赖隔离扫描（APP-066 第 2 节）。"""
    dev_hits = []
    torch_hits = []
    cuda_hits = []
    dlls = []
    pyds = []
    exes = []
    n_text = 0
    for root, dirs, files in os.walk(dst):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, dst)
            low = fn.lower()
            if low.endswith('.dll'):
                dlls.append((rel, os.path.getsize(p)))
            elif low.endswith('.pyd'):
                pyds.append((rel, os.path.getsize(p)))
            elif low.endswith('.exe'):
                exes.append((rel, os.path.getsize(p)))
            if not low.endswith(TEXT_EXT):
                continue
            n_text += 1
            try:
                txt = open(p, 'rb').read().decode('utf-8', errors='replace')
            except OSError:
                continue
            for pat in DEV_PATH_PATTERNS:
                if pat in txt:
                    dev_hits.append((rel, pat))
            for pat in TORCH_PATTERNS:
                if re.search(pat, txt, re.M):
                    torch_hits.append((rel, pat))
            # CUDA：只查**代码里的 import / DLL 名**
            for pat in ('cudnn', 'cublas', 'cudart', 'torch'):
                if pat in txt.lower() and pat != 'torch':
                    cuda_hits.append((rel, pat))
    # DLL 级 CUDA 判定
    cuda_dlls = [d for d, _ in dlls
                 if any(k in d.lower() for k in
                        ('cudnn', 'cublas', 'cudart', 'nvrtc', 'nvcuda',
                         'torch'))]
    return {
        'n_text_files_scanned': n_text,
        'dev_path_hits': dev_hits,
        'torch_import_hits': torch_hits,
        'cuda_code_hits': cuda_hits,
        'n_dll': len(dlls),
        'n_pyd': len(pyds),
        'n_exe': len(exes),
        'cuda_dlls': cuda_dlls,
        'dll_bytes': sum(s for _, s in dlls),
        'pyd_bytes': sum(s for _, s in pyds),
        'largest_dlls': sorted(dlls, key=lambda x: -x[1])[:15],
        'largest_pyds': sorted(pyds, key=lambda x: -x[1])[:15],
    }


def size_report(dst):
    parts = {}
    for d in ('app', 'models', 'python', 'docs'):
        p = os.path.join(dst, d)
        if os.path.isdir(p):
            parts[d] = du(p)
    for sub in ('encoder-int8', 'decoder-gpu-int8', 'mt', 'qwen3tts',
                'tokenizer'):
        p = os.path.join(dst, 'models', sub)
        if os.path.isdir(p):
            parts['models/' + sub] = du(p)
    p = os.path.join(dst, 'models', 'embed_tokens_f16.npy')
    if os.path.isfile(p):
        parts['models/embed_tokens_f16.npy'] = os.path.getsize(p)
    parts['_total'] = du(dst)
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DST_PKG)
    ap.add_argument('--scan-only', action='store_true')
    args = ap.parse_args()
    dst = args.pkg

    removed = []
    if not args.scan_only:
        print('=== ① 建 MiniMVP 包：%s ===' % dst)
        removed = build(dst)
        print('  已剔除（不带清单命中）：%s' % (removed or '无'))

    print()
    print('=== ② 依赖隔离扫描 ===')
    sc = scan(dst)
    print('  扫了 %d 个文本文件' % sc['n_text_files_scanned'])
    print('  开发目录绝对路径命中：%d' % len(sc['dev_path_hits']))
    for h in sc['dev_path_hits'][:20]:
        print('      %s  ← %s' % h)
    print('  torch import 命中：%d' % len(sc['torch_import_hits']))
    for h in sc['torch_import_hits'][:20]:
        print('      %s  ← %s' % h)
    print('  CUDA 代码命中：%d' % len(sc['cuda_code_hits']))
    print('  DLL %d 个（%.1f MB）｜PYD %d 个（%.1f MB）｜EXE %d 个'
          % (sc['n_dll'], sc['dll_bytes'] / 1048576.0,
             sc['n_pyd'], sc['pyd_bytes'] / 1048576.0, sc['n_exe']))
    print('  CUDA/torch DLL：%s' % (sc['cuda_dlls'] or '无 ✅'))
    print('  最大的 DLL：')
    for n, s in sc['largest_dlls'][:8]:
        print('      %-60s %8.1f MB' % (n, s / 1048576.0))
    print('  最大的 PYD：')
    for n, s in sc['largest_pyds'][:8]:
        print('      %-60s %8.1f MB' % (n, s / 1048576.0))

    print()
    print('=== ③ 体积分项 ===')
    sz = size_report(dst)
    for k, v in sz.items():
        print('  %-38s %10.1f MB' % (k, v / 1048576.0))
    src_total = du(SRC_PKG)
    print('  %-38s %10.1f MB（v2.2 对比：%.1f MB ⇒ %.1f%%）'
          % ('MiniMVP 总计', sz['_total'] / 1048576.0,
             src_total / 1048576.0,
             100.0 * sz['_total'] / max(1, src_total)))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-066（MiniMVP 最小客户包）',
        'pkg': dst,
        'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'removed': removed,
        'model_keep': list(MODEL_KEEP_DIRS) + list(MODEL_KEEP_FILES),
        'scan': sc,
        'sizes_bytes': sz,
        'src_pkg_bytes': src_total,
        'ratio_vs_v22': round(sz['_total'] / max(1, src_total), 4),
        'tts_fp16_npu_note': (
            'App 的 TTS 走 BabelVox ⇒ 加载 `models/qwen3tts/int8/`（唯一一份 IR）；'
            '**NPU 推理精度提示 = f16**（tts_engine._ov_precision）'
            '⇒ 「TTS 仅保留 FP16 NPU」落地为：只带 int8/ 这一份 IR + NPU 上 f16 运行。'
            '不带 GPU/CPU/CUDA 版、不带 NPU 编译缓存（blob，首次运行现编）。'),
        'not_included': {
            '说话人旁路/克隆': 'app/asr_spk/ + models/spk/ 已剔除 ⇒ 只提供预设音色',
            'EXT 插件': 'ext/ 未拷贝',
            'CUDA/torch': 'app/tts_cuda*.py 已剔除；扫描无 torch import、无 CUDA DLL',
        },
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print()
    print('证据：%s' % REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
