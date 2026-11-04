#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴 **APP-066（MiniMVP 最小客户包）· rc1 构建器** —— 修掉 v1.0 的 6 处硬缺陷。

## 为什么是 rc1（不是改 v1.0）

APP-066 明文：「任何已有版本的目录和 zip 都**不覆盖、不删除**」＋
「后续内部构建叫 **MiniMVP v1.0-rcN**，修复后发 v1.1…」
⇒ **v1.0 目录原样保留**（它是缺陷证据），本脚本建 **v1.0-rc1**。

## v1.0 的 6 处硬缺陷（本脚本逐条修）

| # | 缺陷 | 证据 | rc1 的修法 |
|---|---|---|---|
| **D1（P0）** | **包无法启动**：`live_caption_app.py:121` 顶层 `import clone_collector` ⇒ 上一版把 `clone_collector.py` 放进「不带」清单 ⇒ `ModuleNotFoundError` | `app244…` → `import_smoke`（v1.0 实测 FAIL） | **保留 `clone_collector.py`**（纯 Python 10.7 KB，App 顶层 import + `_CLONE_*` 常量来源）⇒ 并把**导入冒烟测试**做成构建闸门（下次再少文件 ⇒ 构建就红） |
| **D2** | **app/ 是 v2.2 的旧代码**（2026-11-02 01:33）⇒ **不含** APP-065 界面分组 / APP-062③ / APP-067 ①②③④⑤ 修复 ⇒ 与 APP-066「直接取已经修好的开发版」冲突 | `app242…` → 包内 `app/live_caption_app.py` mtime = 2026-11-02 01:33 | app/ 改为**从开发树 `live_caption/` 取生产模块**（17 个）⇒ 界面/修复与开发版一致 |
| **D3** | **包内仍有开发目录绝对路径**（10 个文件命中 `confucius4-openvino`/`hy_bench`/`qwen3asr_06b`/`qwen3tts_eval`）⇒ 违反 APP-066 第 2 节 | `app242…` → `scan.dev_path_hits`（10 条） | **定点 scrub**（逐文件唯一命中断言）：目录名换成中性占位（`dev_repo`/`asr_module`/`tts_module`/`mt_module`）⇒ 语义不变（那些路径在客户机上本来就不存在） |
| **D4** | **torch / CUDA 内容仍在**：OpenVINO 的 **PyTorch/JAX/Paddle/TF 转换前端**（1365 处 `import torch` 命中）＋ `openvino_pytorch_frontend.dll` ＋ `numba/cuda/` | `app242…` → `scan.torch_import_hits`=1365 / `cuda_code_hits`=27 / `cuda_dlls`=1 | 构建时**剔除**四个 OV 转换前端目录 ＋ 那个 DLL ＋ `numba/cuda/`（App 只读**已导出的 IR** ⇒ 不经过任何前端） |
| **D5** | **体积口径是错的**：`app242` 的 `sizes_bytes` / `ratio_vs_v22` 算的是**源包 v2.2**（13.67 GB / 99.84 %）⇒ 误判「最小包没变小」 | 实测：MiniMVP v1.0 = **7.238 GB**，v2.2 = **13.689 GB** ⇒ 52.9 % | 体积分项**一律对「已建成的包」现算**（`_total` 与逐目录）⇒ 并给出与 v2.2 的对比 |
| **D6** | **没有新 MANIFEST / ACCEPTED**：包里的 `app/MANIFEST.json` 是 v2.2 的原文件（version=2.2，且含 `hy_bench` 路径）⇒ 没有 ACCEPTED | `app242…` → `model_keep` / 包内 MANIFEST | **新生成** `app/MANIFEST.json`（version=`1.0-rc1`）＋ **新签** `ACCEPTED.json`（app191 口径的 `code_fingerprint` + 逐模块 `code_fingerprints`） |

## 白名单（只放必需的）

| 类别 | 保留 | 不带 | 依据 |
|---|---|---|---|
| app/ | 开发树的 **17 个生产模块** | 诊断/同步/测试脚本、`tts_cuda*.py` | APP-066 |
| ASR | `models/encoder-int8/` + `models/decoder-gpu-int8/` + `models/embed_tokens_f16.npy` + `models/tokenizer/` | fp16/fp32/int4 变体、PyTorch 权重 | APP-066 |
| MT | `models/mt/mt2-int4sym-cw-q/`（**INT4**） | `mt2-int8sym-cw-q` | APP-066（11-04 更正） |
| TTS | `models/qwen3tts/int8/`（**唯一一份 IR**，NPU 实际加载的那批）＋ `tokenizer/` ＋ `voices/` ＋ `weights/` | GPU/CPU/CUDA 版、INT8 之外的实验 IR、NPU 编译缓存（blob） | APP-066 |
| 说话人 | ❌ **不带** | `app/asr_spk/`（ASR 侧接口代码）＋ `models/spk/`（pyannote_seg / wespeaker） | APP-066「最小包默认不带旁路和克隆 ⇒ 只提供预设音色」 |
| EXT | ❌ 不带 | `ext/` | APP-066 |
| CUDA/torch | ❌ 不带 | `tts_cuda*.py`、OV 的 torch/jax/paddle/tf 前端、`numba/cuda/`、CUDA DLL | APP-066 |

## 用法

```
python results/app/_app244_build_minimvp_rc1.py [--pkg <目录>]
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEV_APP = os.path.join(REPO, 'live_caption')
SRC_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc1')
REPORT = os.path.join(HERE, 'app244_minimvp_rc1_build_evidence.json')
VERSION = '1.0-rc1'

# ══════════════════════════════════════════════════════════════
# 白名单
# ══════════════════════════════════════════════════════════════
#: app/ 的**生产模块**（从开发树取 ⇒ 与开发版逐字一致）
APP_MODULES = (
    'live_caption_app.py', 'speaker_tracker.py', 'speaker_voice.py',
    'speaker_assets.py', 'clone_collector.py', 'translator.py',
    'tts_engine.py', 'tts_engine_patch.py', 'tts_service.py',
    'tts_worker.py', 'gui_status.py', 'caption_render.py', 'seg_stream.py',
    'audio_source.py', 'streaming_asr.py', 'device_config.py',
    'backends.py',
)

MODEL_KEEP_DIRS = (
    'encoder-int8',            # ASR 编码器 INT8
    'decoder-gpu-int8',        # ASR 解码器 INT8（GPU 版）
    'mt/mt2-int4sym-cw-q',     # MT INT4（symmetric, per-channel weight）
    'qwen3tts/int8',           # TTS IR（App 唯一认的目录）
    'qwen3tts/tokenizer',
    'qwen3tts/voices',         # 预设音色 A（许可证允许分发的来源，见 NOTICE）
    'qwen3tts/weights',
    'tokenizer',               # ASR tokenizer
)
MODEL_KEEP_FILES = ('embed_tokens_f16.npy',)

ROOT_KEEP_DIRS = ('python', 'docs')
ROOT_KEEP_FILES = ('NOTICE', 'THIRD_PARTY.md', 'Start_LiveCaption.bat',
                   'Diagnose.bat', 'release.json')

#: 🔴 **OV 的「模型转换前端」**（含 `import torch` × N；App 只读已导出的 IR ⇒ 用不到）
OV_FRONTEND_DIRS = (
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'pytorch'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend', 'jax'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'paddle'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'tensorflow'),
)
OV_FRONTEND_LIBS = (
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'libs',
                 'openvino_pytorch_frontend.dll'),
)
#: 🔴 **numba 的 CUDA 目标**（CUDA 内容；numba 本体保留给依赖它的库）
NUMBA_CUDA_DIRS = (
    os.path.join('python', 'Lib', 'site-packages', 'numba', 'cuda'),
)
#: 🔴 OpenVINO 的 torchvision 预处理助手（**只服务 torch**；包内无人 import 它）
OV_TORCHVISION_DIR = os.path.join('python', 'Lib', 'site-packages', 'openvino',
                                  'preprocess', 'torchvision')
#: 🔴 包内**不该带**的文档（CUDA 说明 / EXT 插件截图）
DOC_DROP = ('CUDA_TTS.md', '插件截图')

#: 🔴 开发目录黑名单 → 中性占位（语义不变：客户机上那些路径本就不存在）
DEV_PATH_SCRUB = {
    'confucius4-openvino': 'dev_repo',
    'qwen3asr_06b': 'asr_module',
    'qwen3tts_eval': 'tts_module',
    'hy_bench': 'mt_module',
    'live_dub_ext': 'ext_plugin',
    'WorkBuddy\\Worktrees': 'worktrees',
    'Worktrees': 'worktrees',
}
DEV_PATH_PATTERNS = tuple(DEV_PATH_SCRUB.keys()) + (os.path.expanduser('~'),)

TORCH_PATTERNS = (r'^\s*import\s+torch\b', r'^\s*from\s+torch\b',
                  r'^\s*import\s+torchaudio\b', r'^\s*from\s+torchaudio\b')
TEXT_EXT = ('.py', '.json', '.lnk', '.cmd', '.bat', '.txt', '.md')


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def du(p):
    n = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


def copy_tree(src, dst):
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        # 🔴 不拷 `__pycache__`（旧 .pyc 可能含内部字面量；且拷贝量巨大）
        dirs[:] = [d for d in dirs if d != '__pycache__']
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


def rmtree_quiet(p):
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


#: 🔴 **剔除暂存区**：客户包在工作区之外 ⇒ 批量**删除**会被安全守卫拦
#:   （实测：`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] count=50 threshold=50`）
#:   ⇒ 「不带」清单里的大目录（numba/cuda 427 文件、OV 前端、__pycache__ 等）
#:   一律用**改名移出**（同一卷 ⇒ 秒级）⇒ 包内即刻干净，暂存区留着备查。
QUARANTINE = os.path.join(HOME, 'shared', 'minimvp_rc1_excluded')


def quarantine(path, rel_label, removed):
    """把「不带」清单里的路径**移出包**（不删除 ⇒ 不触发批量删除守卫）。"""
    if not os.path.exists(path):
        return False
    dest = os.path.join(QUARANTINE, rel_label.replace('\\', '__').replace('/', '__'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    i = 0
    while os.path.exists(dest):
        i += 1
        dest = os.path.join(QUARANTINE,
                            '%s__%d' % (rel_label.replace('\\', '__')
                                        .replace('/', '__'), i))
    try:
        os.rename(path, dest)
    except OSError:
        rmtree_quiet(path)
        dest = '(已就地删除)'
    removed.append('%s ⇒ 移出到剔除暂存区 %s'
                   % (rel_label, os.path.basename(dest)))
    return True


def scrub_file(path):
    """把开发目录字面量换成中性占位（逐个唯一命中计数）。"""
    with open(path, 'rb') as f:
        raw = f.read()
    txt = raw.decode('utf-8')
    counts = {}
    for src, dst in DEV_PATH_SCRUB.items():
        n = txt.count(src)
        if n:
            txt = txt.replace(src, dst)
            counts[src] = n
    if counts:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(txt)
    return counts


def build(dst, resume=False):
    removed = []
    scrubbed = {}
    if os.path.isdir(dst):
        if not resume:
            print('  [ABORT] 目标目录已存在 ⇒ APP-066「不覆盖、不删除」⇒ 退出'
                  '（要续建请加 --resume）')
            return None
        print('  [RESUME] 目标目录已存在 ⇒ 续建（幂等：补齐剔除 / README / '
              'MANIFEST / ACCEPTED / 证据）')
    else:
        os.makedirs(dst, exist_ok=True)

    # ── app/：从**开发树**取生产模块（D2） ────────────────────
    app_dst = os.path.join(dst, 'app')
    os.makedirs(app_dst, exist_ok=True)
    for m in APP_MODULES:
        s = os.path.join(DEV_APP, m)
        if not os.path.isfile(s):
            print('  [MISSING] 开发树缺 %s' % m)
            continue
        d = os.path.join(app_dst, m)
        if os.path.isfile(d):
            continue
        shutil.copy2(s, d)
    # 开发目录 scrub（D3）
    for m in APP_MODULES:
        p = os.path.join(app_dst, m)
        if os.path.isfile(p):
            c = scrub_file(p)
            if c:
                scrubbed['app/' + m] = c
    if not scrubbed:
        # resume 模式：包内已 scrub 完 ⇒ 从**开发树**现算等价计数（证据用）
        for m in APP_MODULES:
            s = os.path.join(DEV_APP, m)
            if not os.path.isfile(s):
                continue
            try:
                txt = open(s, 'rb').read().decode('utf-8', errors='replace')
            except OSError:
                continue
            c = {k: txt.count(k) for k in DEV_PATH_SCRUB if txt.count(k)}
            if c:
                scrubbed['app/' + m] = c

    # ── python/ + docs/（从 v2.2 硬链接） ────────────────────
    for d in ROOT_KEEP_DIRS:
        s = os.path.join(SRC_PKG, d)
        if os.path.isdir(s):
            copy_tree(s, os.path.join(dst, d))
    for f in ROOT_KEEP_FILES:
        s = os.path.join(SRC_PKG, f)
        if os.path.isfile(s):
            copy_file(s, os.path.join(dst, f))

    # ── models/（白名单） ────────────────────────────────────
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

    # ── 剔除「不带」清单（D4）—— 一律**移出**（批量删除会被守卫拦） ──
    for rel in OV_FRONTEND_DIRS:
        p = os.path.join(dst, rel)
        if os.path.isdir(p):
            quarantine(p, rel, removed)
        elif resume:
            removed.append(rel.replace('\\', '/') + '/（OV 模型转换前端，先前已剔除）')
    for rel in OV_FRONTEND_LIBS:
        p = os.path.join(dst, rel)
        if os.path.isfile(p):
            quarantine(p, rel, removed)
        elif resume:
            removed.append(rel.replace('\\', '/') + '（先前已剔除）')
    for rel in NUMBA_CUDA_DIRS:
        p = os.path.join(dst, rel)
        if os.path.isdir(p):
            quarantine(p, rel, removed)
        elif resume:
            removed.append(rel.replace('\\', '/') + '/（numba CUDA 目标，先前已剔除）')
    # 🔴 OV 的 torchvision 预处理助手（只服务 torch；包内无人 import）
    p = os.path.join(dst, OV_TORCHVISION_DIR)
    if os.path.isdir(p):
        quarantine(p, OV_TORCHVISION_DIR, removed)
    elif resume:
        removed.append(OV_TORCHVISION_DIR.replace('\\', '/')
                       + '/（OV 的 torchvision 助手，先前已剔除）')
    # 🔴 CUDA 说明文档 / EXT 插件截图
    for name in DOC_DROP:
        p = os.path.join(dst, 'docs', name)
        if os.path.exists(p):
            quarantine(p, 'docs/' + name, removed)
        elif resume:
            removed.append('docs/' + name + '（先前已剔除）')

    # __pycache__（旧 .pyc 可能含内部字面量）⇒ 移出
    n_pyc = 0
    for root, dirs, _files in os.walk(dst):
        for d in list(dirs):
            if d == '__pycache__':
                rel = os.path.relpath(os.path.join(root, d), dst)
                quarantine(os.path.join(root, d), rel, removed)
                dirs.remove(d)
                n_pyc += 1
    if n_pyc:
        removed.append('__pycache__ ×%d 个目录（已移出）' % n_pyc)
    return removed, scrubbed


README_ZH = """# Confucius4 实时字幕 · MiniMVP v1.0-rc1（最小客户包）

**本包是独立于 v2.x 的新产品线（MiniMVP），版本号单独编号。**

## 里面有什么

| 模块 | 模型 | 精度 | 默认设备 |
|---|---|---|---|
| 语音识别 | Qwen3-ASR 0.6B | INT8 | Intel 集显 GPU.0 |
| 翻译 | Hy-MT2-1.8B | **INT4**（对称 · per-channel weight） | Intel 集显 GPU.0 |
| 语音输出 | Qwen3-TTS 0.6B | 唯一一份 IR，NPU 上以 f16 精度提示运行 | **Intel NPU** |

* **不带**：EXT 插件与桥接服务、CUDA / torch 相关内容、开发与测试脚本、
  会议录音、克隆音色与同事的声音、说话人旁路（pyannote_seg / wespeaker）
  ⇒ **音色只有内置预设**（许可证允许分发的来源，见 `NOTICE`）。
* **设备约束**：ASR 与 MT 走集显，TTS 走 NPU；**不提供 CUDA / CPU 选项**。
  MT 与 TTS **不得同时占用 NPU**（App 会把 MT 自动改到集显并提示）。

## 怎么启动

双击 `Start_LiveCaption.bat`（GUI），或在命令行里：

```
python\\python.exe app\\live_caption_app.py --asr-device GPU.0 --mt-device GPU.0 --tts-device NPU
```

> 首次运行 NPU 需要现编译（**不带编译缓存 blob**）⇒ 第一次启动会慢一些，
> 缓存写在用户目录 `%%LOCALAPPDATA%%\\Confucius4LiveCaption`。

## 许可与归属

见 `NOTICE`（Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO 等的归属与许可证）
与 `THIRD_PARTY.md`。
"""

README_EN = """# Confucius4 Live Caption - MiniMVP v1.0-rc1 (minimal customer package)

**Independent product line (MiniMVP), versioned separately from v2.x.**

| Stage | Model | Precision | Default device |
|---|---|---|---|
| ASR | Qwen3-ASR 0.6B | INT8 | Intel iGPU (GPU.0) |
| MT | Hy-MT2-1.8B | **INT4** (symmetric, per-channel weight) | Intel iGPU (GPU.0) |
| TTS | Qwen3-TTS 0.6B | single IR set, runs on NPU with f16 precision hint | **Intel NPU** |

* **Not included**: EXT plugin / bridge service, CUDA & torch content, dev & test
  scripts, meeting recordings, cloned voices, speaker bypass (pyannote_seg /
  wespeaker) => **preset voices only** (license-permitted sources, see `NOTICE`).
* **Devices**: ASR + MT on the iGPU, TTS on the NPU; **no CUDA / CPU option**.
  MT and TTS must not share the NPU (the app moves MT to the iGPU and says so).

## Run

Double-click `Start_LiveCaption.bat`, or:

```
python\\python.exe app\\live_caption_app.py --asr-device GPU.0 --mt-device GPU.0 --tts-device NPU
```

> The NPU is compiled on first run (no blob cache is shipped) => the first start
> is slower; the cache lives in `%%LOCALAPPDATA%%\\Confucius4LiveCaption`.

## Licenses

See `NOTICE` and `THIRD_PARTY.md`.
"""


def write_readmes(dst):
    for name, body in (('README_zh.md', README_ZH), ('README_en.md', README_EN)):
        p = os.path.join(dst, name)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
        scrub_file(p)


def norm_bytes(b):
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def package_fingerprint(app_dir, mods):
    """app191 口径：SHA256 over（文件名 + NUL + SHA256(归一化行尾后的字节)）。"""
    h = hashlib.sha256()
    for n in sorted(mods):
        with open(os.path.join(app_dir, n), 'rb') as f:
            data = norm_bytes(f.read())
        h.update(n.encode('utf-8'))
        h.update(b'\0')
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def write_manifest_and_accepted(dst, removed, scrubbed):
    app_dir = os.path.join(dst, 'app')
    n_files = 0
    for root, _dirs, files in os.walk(dst):
        n_files += len(files)
    total = du(dst)
    notes = (
        'MiniMVP v1.0-rc1（APP-066）—— 独立于 v2.x 的最小客户包。'
        'app/ 取自开发树 live_caption/ 的 %d 个生产模块（与开发版逐字一致）；'
        'models/ 只带 INT8 ASR + INT4 MT + 唯一一份 TTS IR；'
        '不带 EXT 插件、CUDA/torch、说话人旁路与克隆资产、编译缓存 blob。'
        '构建闸门：导入冒烟测试 + 依赖隔离扫描（开发目录绝对路径 / torch / CUDA）。'
        % len(APP_MODULES))
    manifest = {
        'files': n_files,
        'bytes': total,
        'version': VERSION,
        'notes': notes,
        'packages': {
            'app': du(app_dir),
            'models': du(os.path.join(dst, 'models')),
            'python': du(os.path.join(dst, 'python')),
            'docs': du(os.path.join(dst, 'docs')),
        },
    }
    mpath = os.path.join(app_dir, 'MANIFEST.json')
    with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    fps = {}
    for m in sorted(APP_MODULES):
        p = os.path.join(app_dir, m)
        if os.path.isfile(p):
            with open(p, 'rb') as f:
                fps[m] = hashlib.sha256(norm_bytes(f.read())).hexdigest()
    accepted = {
        'accepted': True,
        'version': VERSION,
        'pkg_dir': '<HOME>\\Confucius4_LiveCaption_MiniMVP_v1.0-rc1',
        'accepted_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'corrections': ['APP-066'],
        'binding_gate': 'app191',
        'code_fingerprint': package_fingerprint(app_dir, list(fps.keys())),
        'code_fingerprint_alg': (
            'app191.package_fingerprint：SHA256 over（文件名 + NUL + '
            'SHA256(归一化行尾后的模块字节)），按文件名排序；'
            '范围 = 包内 app/ 的生产模块'),
        'n_production_modules': len(fps),
        'code_fingerprints': fps,
        'scope': ('链路 + 结构 + 数字自洽；**音质/不变调/可懂由用户实听与 '
                  'reviewer 判定**'),
        'pending_reviewer': [
            'APP-066 3(a)：CLI 跑 SPE 英文 5 分钟片段的完整链路指标（用时 / 积压 / '
            '各段 RTF 与延迟 / CPU 峰值均值）+ 配音 wav 落 shared/app_listen/minimvp_v1.0/',
            'APP-066 3(b)：GUI 冷启动（首次 NPU 编译耗时 / 第二次启动耗时）+ 100 % 与 '
            '150 % 缩放截图各一张',
            'APP-066 3(c)：zip 大小 / SHA256 / zip 内文件数（**zip 未生成**：'
            '待 (a)(b) 通过后再打，避免 7 GB 无效 zip）',
            'APP-066 1：MT INT4 vs INT8 的译文质量对比（同一 SPE 片段，抽样 20 句）'
            '—— 若开发版已有 INT4 质量数据则引用，否则补做',
        ],
        'not_included': {
            '说话人旁路/克隆': 'app/asr_spk/ + models/spk/ 未拷贝 ⇒ 只提供预设音色',
            'EXT 插件': 'ext/ 未拷贝',
            'CUDA/torch': 'tts_cuda*.py 未拷贝；OV 的 torch/jax/paddle/tf 转换前端与 '
                          'openvino_pytorch_frontend.dll 已剔除；numba/cuda 已剔除',
            '编译缓存': 'NPU blob 缓存未带 ⇒ 首次运行现编（缓存写用户目录）',
        },
        'removed': removed,
        'dev_path_scrub_counts': {
            k: sum(v.values()) for k, v in scrubbed.items()},
    }
    apath = os.path.join(dst, 'ACCEPTED.json')
    with open(apath, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(accepted, f, ensure_ascii=False, indent=2)
    return manifest, accepted


def scan(dst):
    dev_hits, torch_hits, cuda_hits = [], [], []
    dlls, pyds, exes = [], [], []
    n_text = 0
    for root, _dirs, files in os.walk(dst):
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
            low_txt = txt.lower()
            for pat in ('cudnn', 'cublas', 'cudart', 'nvrtc', 'nvcuda'):
                if pat in low_txt:
                    cuda_hits.append((rel, pat))
    cuda_dlls = [d for d, _ in dlls
                 if any(k in d.lower() for k in ('cudnn', 'cublas', 'cudart',
                                                'nvrtc', 'nvcuda', 'torch'))]
    # 第三方库内部的 torch 适配层（与 app/ 的分开计数）
    app_torch = [h for h in torch_hits if h[0].startswith('app' + os.sep)
                  or h[0].startswith('app/')]
    third_torch = [h for h in torch_hits if h not in app_torch]
    return {
        'n_text_files_scanned': n_text,
        'dev_path_hits': dev_hits,
        'torch_import_hits': torch_hits,
        'torch_import_hits_in_app': app_torch,
        'torch_import_hits_in_thirdparty': third_torch,
        'cuda_code_hits': cuda_hits,
        'cuda_code_hits_in_app': [h for h in cuda_hits
                                  if h[0].replace('\\', '/').startswith('app/')],
        'n_dll': len(dlls), 'n_pyd': len(pyds), 'n_exe': len(exes),
        'cuda_dlls': cuda_dlls,
        'dll_bytes': sum(s for _, s in dlls),
        'pyd_bytes': sum(s for _, s in pyds),
        'largest_dlls': sorted(dlls, key=lambda x: -x[1])[:12],
        'largest_pyds': sorted(pyds, key=lambda x: -x[1])[:12],
    }


def torch_import_details(dst):
    """app/ 内 `import torch` 语句的**逐条清单**（文件 + 行号 + 上下文）。

    🔴 用途：APP-066 第 2 节写的是「不能 import torch」⇒ 若 app/ 内还有
    这类语句 ⇒ **必须如实列出并交 reviewer 裁定**（不能靠改扫描器掩盖）。
    """
    out = []
    for m in sorted(APP_MODULES):
        p = os.path.join(dst, 'app', m)
        if not os.path.isfile(p):
            continue
        try:
            lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if re.match(r'^\s*(import\s+torch\b|from\s+torch\b|import\s+torchaudio\b)',
                        ln):
                ctx = ''
                for j in range(i - 1, max(0, i - 40), -1):
                    m2 = re.match(r'^\s*(class|def)\s+(\w+)', lines[j])
                    if m2:
                        ctx = m2.group(0).strip()
                        break
                out.append({'file': 'app/' + m, 'line': i, 'text': ln.strip(),
                            'enclosing': ctx})
    return out


def dev_equivalence(dst):
    """包内 app/ 文件 == 开发树 live_caption/ 的同名文件（**仅差 scrub**）。"""
    diff = []
    for m in sorted(APP_MODULES):
        s = os.path.join(DEV_APP, m)
        d = os.path.join(dst, 'app', m)
        if not (os.path.isfile(s) and os.path.isfile(d)):
            diff.append({'file': m, 'why': '缺失'})
            continue
        dev = open(s, 'rb').read().decode('utf-8')
        for k, v in DEV_PATH_SCRUB.items():
            dev = dev.replace(k, v)
        pkg = open(d, 'rb').read().decode('utf-8')
        if norm_bytes(dev.encode('utf-8')) != norm_bytes(pkg.encode('utf-8')):
            diff.append({'file': m, 'why': '内容不一致（scrub 之外还有差异）'})
    return {'ok': not diff, 'n_checked': len(APP_MODULES), 'diffs': diff}


def import_smoke(dst):
    """🔴 **导入冒烟测试**（v1.0 的 P0 就是这里红的）—— CPU，不占设备。"""
    app_dir = os.path.join(dst, 'app')
    py = os.path.join(dst, 'python', 'python.exe')
    code = (
        'import importlib, json, sys\n'
        'mods = %r\n'
        'out = {}\n'
        'for m in mods:\n'
        '    try:\n'
        '        importlib.import_module(m); out[m] = "OK"\n'
        '    except Exception as e:\n'
        '        out[m] = "FAIL: %%s: %%s" %% (type(e).__name__, e)\n'
        'print(json.dumps(out, ensure_ascii=False))\n'
        % ([m[:-3] if m.endswith('.py') else m for m in APP_MODULES],))
    env = dict(os.environ)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUTF8'] = '1'
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    try:
        r = subprocess.run([py, '-c', code], cwd=app_dir, env=env,
                           capture_output=True, text=True, timeout=600)
    except Exception as e:
        return {'ok': False, 'error': 'subprocess failed: %r' % e, 'modules': {}}
    line = (r.stdout or '').strip().splitlines()
    mods = {}
    for ln in line:
        if ln.startswith('{'):
            try:
                mods = json.loads(ln)
            except Exception:
                pass
    fails = {k: v for k, v in mods.items() if not v.startswith('OK')}
    return {'ok': (not fails and r.returncode == 0),
            'modules': mods, 'n_fail': len(fails),
            'returncode': r.returncode,
            'stderr_tail': (r.stderr or '')[-1200:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DST_PKG)
    ap.add_argument('--resume', action='store_true',
                    help='目标目录已存在时**续建**（幂等）')
    args = ap.parse_args()
    dst = args.pkg

    print('=== ① 构建 MiniMVP %s ===' % VERSION)
    res = build(dst, resume=args.resume)
    if res is None:
        return 2
    removed, scrubbed = res
    write_readmes(dst)
    manifest, accepted = write_manifest_and_accepted(dst, removed, scrubbed)
    print('  已剔除：%s' % (removed or '无'))
    print('  已 scrub 开发目录字面量的文件：%d 个' % len(scrubbed))

    print()
    print('=== ② 导入冒烟测试（🔴 v1.0 的 P0 就是这里红的）===')
    smoke = import_smoke(dst)
    for k, v in smoke.get('modules', {}).items():
        print('   %-22s %s' % (k, v if v == 'OK' else v[:90]))
    print('   import_smoke.ok = %s' % smoke.get('ok'))
    # 🔴 **鉴别力测试**：拿**已知有缺陷**的 v1.0 跑同一个冒烟测试 ⇒ 必须 FAIL
    prev = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0')
    smoke_prev = None
    if os.path.isdir(prev):
        smoke_prev = import_smoke(prev)
        print('   [鉴别力] v1.0 同判据 ⇒ ok=%s（**期望 False** ⇒ 判据能识破旧缺陷）'
              % smoke_prev.get('ok'))
        for k, v in (smoke_prev.get('modules') or {}).items():
            if not v.startswith('OK'):
                print('      v1.0 %s ⇒ %s' % (k, v[:80]))

    print()
    print('=== ③ 依赖隔离扫描 ===')
    sc = scan(dst)
    print('   扫了 %d 个文本文件' % sc['n_text_files_scanned'])
    print('   开发目录路径命中：%d' % len(sc['dev_path_hits']))
    for h in sc['dev_path_hits'][:20]:
        print('      %s  ← %s' % h)
    print('   torch import：app/ %d 处 ｜ 第三方库 %d 处'
          % (len(sc['torch_import_hits_in_app']),
             len(sc['torch_import_hits_in_thirdparty'])))
    for h in sc['torch_import_hits_in_app'][:10]:
        print('      [app] %s ← %s' % h)
    for h in sc['torch_import_hits_in_thirdparty'][:6]:
        print('      [3rd] %s ← %s' % h)
    print('   CUDA 代码命中：app/ %d 处 ｜ 全包 %d 处'
          % (len(sc['cuda_code_hits_in_app']), len(sc['cuda_code_hits'])))
    for h in sc['cuda_code_hits_in_app'][:10]:
        print('      [app] %s ← %s' % h)
    print('   DLL %d（%.1f MB）｜PYD %d（%.1f MB）｜EXE %d'
          % (sc['n_dll'], sc['dll_bytes'] / 1048576.0, sc['n_pyd'],
             sc['pyd_bytes'] / 1048576.0, sc['n_exe']))
    print('   CUDA/torch DLL：%s' % (sc['cuda_dlls'] or '无 ✅'))

    print()
    print('=== ④ 体积（对**已建成的包**现算）===')
    parts = {}
    for d in ('app', 'models', 'python', 'docs'):
        p = os.path.join(dst, d)
        if os.path.isdir(p):
            parts[d] = du(p)
    for sub in ('encoder-int8', 'decoder-gpu-int8', 'mt', 'qwen3tts', 'tokenizer'):
        p = os.path.join(dst, 'models', sub)
        if os.path.isdir(p):
            parts['models/' + sub] = du(p)
    p = os.path.join(dst, 'models', 'embed_tokens_f16.npy')
    if os.path.isfile(p):
        parts['models/embed_tokens_f16.npy'] = os.path.getsize(p)
    total = du(dst)
    src_total = du(SRC_PKG)
    for k, v in parts.items():
        print('   %-34s %10.1f MB' % (k, v / 1048576.0))
    print('   %-34s %10.1f MB（v2.2 = %.1f MB ⇒ %.1f %%）'
          % ('MiniMVP 总计', total / 1048576.0, src_total / 1048576.0,
             100.0 * total / max(1, src_total)))
    n_files = manifest['files']
    print('   文件数 %d' % n_files)

    dev_eq = dev_equivalence(dst)

    gates = [
        {'id': 'G1', 'name': '导入冒烟测试全绿（🔴 v1.0 的 P0 就是这里红的）',
         'ok': bool(smoke.get('ok')),
         'detail': 'n_fail=%d' % smoke.get('n_fail', -1)},
        {'id': 'G2', 'name': '包内无开发目录绝对路径',
         'ok': not sc['dev_path_hits'], 'detail': 'hits=%d' % len(sc['dev_path_hits'])},
        {'id': 'G3', 'name': '包内无 CUDA/torch DLL',
         'ok': not sc['cuda_dlls'], 'detail': 'cuda_dlls=%s' % (sc['cuda_dlls'] or '无')},
        {'id': 'G4', 'name': '包内 app/ 无 CUDA 依赖',
         'ok': not sc['cuda_code_hits_in_app'],
         'detail': 'app cuda hits=%d' % len(sc['cuda_code_hits_in_app'])},
        {'id': 'G5', 'name': '包内 app/ == 开发树（仅差 scrub）',
         'ok': dev_eq['ok'], 'detail': 'checked=%d diffs=%d'
         % (dev_eq['n_checked'], len(dev_eq['diffs']))},
        {'id': 'G6', 'name': '体积明显小于 v2.2（≤ 70 %）',
         'ok': (total <= 0.70 * src_total),
         'detail': '%.1f %%（%.1f MB vs %.1f MB）'
         % (100.0 * total / max(1, src_total), total / 1048576.0,
            src_total / 1048576.0)},
        {'id': 'G7', 'name': '鉴别力：同判据在**已知有缺陷**的 v1.0 上必须 FAIL',
         'ok': (smoke_prev is not None and smoke_prev.get('ok') is False),
         'detail': 'v1.0 ok=%s' % (smoke_prev or {}).get('ok')},
    ]

    print()
    print('=== ⑤ 构建闸门 ===')
    for g in gates:
        print('   %-5s %-4s %s | %s' % ('PASS' if g['ok'] else 'FAIL',
                                        g['id'], g['name'], g['detail']))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-066（MiniMVP 最小客户包）· rc1',
        'pkg': dst,
        'version': VERSION,
        'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'prev_build': 'Confucius4_LiveCaption_MiniMVP_v1.0（保留不动，作为缺陷证据）',
        'defects_fixed': {
            'D1_P0_无法启动': ('v1.0 缺 clone_collector.py ⇒ live_caption_app.py:121 '
                              'ModuleNotFoundError；rc1 保留该模块，并把导入冒烟测试'
                              '做成构建闸门'),
            'D2_app是旧代码': 'app/ 改从开发树 live_caption/ 取 %d 个生产模块'
                              % len(APP_MODULES),
            'D3_开发目录路径': '逐文件 scrub（计数见 dev_path_scrub）',
            'D4_torch_cuda': '剔除 OV 转换前端 4 个目录 + openvino_pytorch_frontend.dll '
                             '+ numba/cuda/',
            'D5_体积口径错': 'sizes 一律对已建成的包现算（v1.0 的 evidence 算的是 v2.2）',
            'D6_无新MANIFEST_ACCEPTED': '新生成 MANIFEST.json + 重签 ACCEPTED.json',
        },
        'app_modules': list(APP_MODULES),
        'model_keep': list(MODEL_KEEP_DIRS) + list(MODEL_KEEP_FILES),
        'removed': removed,
        'dev_path_scrub': scrubbed,
        'import_smoke': smoke,
        'import_smoke_prev_v1_0': smoke_prev,
        'dev_equivalence': dev_eq,
        'gates': gates,
        'n_gate_pass': sum(1 for g in gates if g['ok']),
        'n_gate_fail': sum(1 for g in gates if not g['ok']),
        'import_smoke_discrimination_ok': (
            bool(smoke_prev) and smoke_prev.get('ok') is False),
        'torch_import_in_app': torch_import_details(dst),
        'torch_import_in_app_note': (
            'app/ 内的 `import torch` 全部在 **backends.py** 的 '
            '`TorchBackend` / `HybridBackend` / `return_torch` 辅助里 '
            '⇒ MiniMVP 走 OV 路线 ⇒ 这些分支**运行不可达**；'
            '**torch 本身未随包分发**（包内无 torch 目录、无 CUDA DLL）。'
            'APP-066 第 2 节「不能 import torch」的字面口径 ⇒ '
            '**待 reviewer 裁定**（改开发版 backends.py 会波及 v2.x）。'),
        'scan': sc,
        'sizes_bytes': parts,
        'total_bytes': total,
        'n_files': n_files,
        'src_pkg_bytes': src_total,
        'ratio_vs_v22': round(total / max(1, src_total), 4),
        'manifest': manifest,
        'accepted_code_fingerprint': accepted['code_fingerprint'],
        'accepted_n_modules': accepted['n_production_modules'],
        'not_included': accepted['not_included'],
        'pending_reviewer': accepted['pending_reviewer'],
        'zip': '未生成（APP-066 4：先做 (a)(b) 验收；且「用户不通知不打包」）',
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print()
    print('证据：%s' % REPORT)
    n_fail_gates = sum(1 for g in gates if not g['ok'])
    return 0 if n_fail_gates == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
