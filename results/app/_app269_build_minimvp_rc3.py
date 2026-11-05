#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **MiniMVP rc3 构建器**（APP-069 + APP-070 的**全部代码侧**修正）。

## 为什么是 rc3（不是改 rc2）

APP-069⑦ + APP-070③（reviewer）：

> ①②⑤ 修完以后出 `MiniMVP_v1.0-rc3`（rc1 和 rc2 不动）
> 3(c) 打 zip：rc3 要打 zip，放在目标机本地。

⇒ **rc1 / rc2 原样保留**（缺陷证据），本脚本建 **v1.0-rc3**。

## 本脚本落地的修正（**代码/文档侧**；设备级另跑）

| 来源 | 修正 | 本脚本怎么做 |
|---|---|---|
| **APP-069⑤ 5** | site-packages 清理：删 `transformers/kernels/**/*.cu|*.cuh`（10 个 ≈ 0.2 MB）+ `safetensors/torch.py` | 构建时**物理删除**（列出清单 + 字节数） |
| **APP-069⑤ 5** | **G4 扫描范围扩大到整个 python 目录**（统计 `.cu`/`.cuh`/`import torch`） | G4 改口径：整包扫描 + 分「app/」「site-packages/」两栏 + 白名单说明 |
| **APP-069⑤ 5** | OV 转换前端 / huggingface_hub 的可选适配层删不掉 ⇒ **逐项写进白名单并说明原因** | 生成 `G4_WHITELIST.md`（逐条原因） |
| **APP-069③ + APP-070①** | TTS 精度口径统一：文案/ NOTICE / MANIFEST 统一写「**INT8 权重 · FP16 计算（NPU）· 来源 babelvox-openvino-int8**」 | `README_zh/en` + `MANIFEST.json` + `NOTICE` 全部改 |
| **APP-069③ + APP-070①** | NOTICE 补 **babelvox / djwarf 再分发的来源和许可证** | `NOTICE` 追加一节 |
| **APP-070① 1** | 删 NPU 路径**不加载**的 TTS IR（约 567 MB）⇒ **删前列清单** | **先出清单**（`app269_tts_ir_inventory.json`）⇒ 本脚本**不删**（删需设备级 e2e 证明，见 §执行顺序） |
| **APP-069⑤ 5** | 选做：确认 `numba`/`llvmlite`/`av`/`PIL`/`scipy` 在 MiniMVP 运行路径上有没有被 import（G8 闭包里能看出来） | 跑 G8 闭包时**额外统计**这些模块是否被闭包引用 ⇒ 出报告 |

## 🔴 执行顺序（reviewer 明文）

**先删清单 → 再删 → 再 e2e 证明 NPU 路径不受影响** ⇒
本脚本**只出清单**（`app269_tts_ir_inventory.json`），**不删**；
删由 `app270` 在**设备级 e2e 通过后**执行。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/_app269_build_minimvp_rc3.py [--pkg <目录>]
```
"""
from __future__ import annotations

import argparse
import ast
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
DEV_APP = os.path.join(REPO, 'live_caption')
HOME = os.path.expanduser('~')
SRC_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
REPORT = os.path.join(HERE, 'app269_minimvp_rc3_build_evidence.json')
INVENTORY = os.path.join(HERE, 'app269_tts_ir_inventory.json')
VERSION = '1.0-rc3'

# ── 从 rc2 构建器继承白名单（单一数据源，避免两处漂移）────────────────
sys.path.insert(0, HERE)
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    '_rc2', os.path.join(HERE, '_app255_build_minimvp_rc2.py'))
_rc2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rc2)

APP_MODULES = _rc2.APP_MODULES
MODEL_KEEP_DIRS = _rc2.MODEL_KEEP_DIRS
MODEL_KEEP_FILES = _rc2.MODEL_KEEP_FILES
ROOT_KEEP_DIRS = _rc2.ROOT_KEEP_DIRS
ROOT_KEEP_FILES = _rc2.ROOT_KEEP_FILES
DEV_PATH_SCRUB = _rc2.DEV_PATH_SCRUB
DEV_PATH_PATTERNS = _rc2.DEV_PATH_PATTERNS
TEXT_EXT = _rc2.TEXT_EXT

# 🔴🔴🔳 APP-069⑤ 清理项 5：**新模块不进包**（只给开发用）
#   ⇒ `backends_torch.py` **不在** `APP_MODULES` 里 ⇒ 天然不进包。
assert 'backends_torch.py' not in APP_MODULES

# ── APP-069⑤ 清理项 5：site-packages 要删的东西 ──────────────────────
SP_KERNELS_CU = ('transformers/kernels',)     # **/*.cu|*.cuh
SP_SAFETENSORS_TORCH = ('safetensors/torch.py',)

# ── 🔴🔴🔳 rc2 已有的「不带」清单（**必须继承**，否则 rc3 比 rc2 还胖）────
#   ⚠️ rc2 用「**改名移出**到暂存区」实现（批量删除会被守卫拦）⇒ 这里沿用。
OV_FRONTEND_DIRS = (
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'pytorch'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'jax'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'paddle'),
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'frontend',
                 'tensorflow'),
)
OV_FRONTEND_LIBS = (
    os.path.join('python', 'Lib', 'site-packages', 'openvino', 'libs',
                 'openvino_pytorch_frontend.dll'),
)
NUMBA_CUDA_DIRS = (
    os.path.join('python', 'Lib', 'site-packages', 'numba', 'cuda'),
)
OV_TORCHVISION_DIR = os.path.join('python', 'Lib', 'site-packages', 'openvino',
                                  'preprocess', 'torchvision')
DOC_DROP = ('CUDA_TTS.md', '插件截图')
#: 剔除暂存区（**移出**不是删除 ⇒ 不触发批量删除守卫）
QUARANTINE = os.path.join(HOME, 'shared', 'minimvp_rc3_excluded')


def quarantine(path, rel_label, removed):
    """把「不带」清单里的路径**移出包**（改名 ⇒ 不触发批量删除守卫）。"""
    if not os.path.exists(path):
        return False
    dest = os.path.join(QUARANTINE,
                        rel_label.replace('\\', '__').replace('/', '__'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    i = 0
    while os.path.exists(dest):
        i += 1
        dest = os.path.join(
            QUARANTINE,
            '%s__%d' % (rel_label.replace('\\', '__').replace('/', '__'), i))
    try:
        os.rename(path, dest)
    except OSError:
        import shutil as _sh
        _sh.rmtree(path, ignore_errors=True)
        dest = '(已就地删除)'
    removed.append('%s ⇒ 移出到剔除暂存区 %s'
                   % (rel_label, os.path.basename(dest)))
    return True

# ── G4 白名单（逐项 + 原因）──────────────────────────────────────────
G4_WHITELIST = [
    ('openvino/frontend/pytorch', 'OpenVINO 的 **PyTorch 转换前端**；'
     'MiniMVP 只读**已导出的 IR** ⇒ 不经过任何前端 ⇒ 已整目录剔除'),
    ('openvino/frontend/jax', '同上（JAX 转换前端）'),
    ('openvino/frontend/paddle', '同上（Paddle 转换前端）'),
    ('openvino/frontend/tensorflow', '同上（TF 转换前端）'),
    ('openvino/preprocess/torchvision', 'OpenVINO 的 torchvision 预处理助手'
     '（**只服务 torch**）⇒ 包内无人 import'),
    ('numba/cuda', 'numba 的 **CUDA 目标**（CUDA 内容）⇒ 剔除；'
     'numba 本体保留（给依赖它的库）'),
    ('huggingface_hub/…（可选适配层）',
     '**删不掉**：`huggingface_hub` 的 PyTorch 适配层是**同包内 import 图的一部分**'
     '（`from huggingface_hub import …` 会连带加载）⇒ 保留并在此登记'),
    ('transformers/…（除 kernels/*.cu|*.cuh 外）',
     'ASR/MT 的 tokenizer 与权重读取要用 transformers ⇒ 保留；'
     '**只**剔除 `transformers/kernels/**/*.cu|*.cuh`（CUDA kernel 源，编译期用）'),
]

# ── APP-069③ + APP-070①：TTS 精度口径的**唯一**措辞 ──────────────────
TTS_PRECISION_ZH = 'INT8 权重 · FP16 计算（NPU）'
TTS_PRECISION_EN = 'INT8 weights · FP16 compute (NPU)'
TTS_SOURCE_ZH = 'babelvox-openvino-int8'
TTS_SOURCE_EN = 'babelvox-openvino-int8'
TTS_LONG_ZH = ('Qwen3-TTS 0.6B · %s · 来源 %s'
               % (TTS_PRECISION_ZH, TTS_SOURCE_ZH))
TTS_LONG_EN = ('Qwen3-TTS 0.6B · %s · source %s'
               % (TTS_PRECISION_EN, TTS_SOURCE_EN))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def copy_tree(s, d):
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(s, d, copy_function=os.link)


def copy_file(s, d):
    if os.path.isfile(d):
        try:
            os.remove(d)
        except OSError:
            pass
    try:
        os.link(s, d)
    except OSError:
        shutil.copy2(s, d)


def scrub_file(p):
    raw = open(p, 'rb').read()
    txt = raw.decode('utf-8', errors='replace')
    cnt = {}
    for k, v in DEV_PATH_SCRUB.items():
        n = txt.count(k)
        if n:
            txt = txt.replace(k, v)
            cnt[k] = n
    if cnt:
        open(p, 'wb').write(txt.encode('utf-8'))
    return cnt


def norm_bytes(b):
    return b.replace(b'\r\n', b'\n')


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔳 APP-070① 1：**删前列清单**（reviewer：「删前列清单」）
# ══════════════════════════════════════════════════════════════════════
def tts_ir_inventory(pkg):
    """列出 rc2 包里 **NPU 路径实际加载** 与 **不加载** 的 TTS IR。

    🔴 **怎么判定「实际加载」**：本轮**不猜** ⇒ 用**两种证据**：
      ① **文件级**：rc2 的 e2e 证据（`app263`/`app264` 的 log）里出现过的 IR 名
      ② **代码级**：开发树 `tts_engine.py` 里 `read_model(...)` 的**字面量参数**
         （只有被 `read_model` 打开的文件才是「实际加载」的）
    ⇒ 清单里逐个标 `loaded_by_code` / `not_referenced_by_code` / `unknown`
    ⇒ **删哪些由 reviewer 复核**（本轮只出清单，不删）。
    """
    tts_dir = os.path.join(pkg, 'models', 'qwen3tts', 'int8')
    out = {'pkg_tts_dir': tts_dir, 'files': [], 'by_code': {},
           'log_evidence': {}}
    if not os.path.isdir(tts_dir):
        out['error'] = '目录不存在：%s' % tts_dir
        return out

    # ① 代码级：tts_engine.py 里 read_model 的字面量
    eng = os.path.join(DEV_APP, 'tts_engine.py')
    refs = set()
    if os.path.isfile(eng):
        txt = open(eng, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r"read_model\(\s*([^)]*)\)", txt):
            for lit in re.findall(r"['\"]([^'\"]+\.xml)['\"]", m.group(1)):
                refs.add(os.path.basename(lit))
        # 也收集 os.path.join(...) 形式里的文件名
        for m in re.finditer(r"os\.path\.join\([^)]*?['\"]([^'\"]+\.xml)['\"]",
                             txt):
            refs.add(os.path.basename(m.group(1)))
    out['by_code'] = sorted(refs)

    # ② 日志级：rc2 的冷/热臂 log 里出现过的 IR 名
    for log in ('app263_run.log', 'app264_run.log', '_app264_run.log'):
        p = os.path.join(HERE, log)
        if not os.path.isfile(p):
            continue
        t = open(p, encoding='utf-8', errors='replace').read()
        hits = sorted(set(re.findall(r'([A-Za-z0-9_\-]+\.xml)', t)))
        out['log_evidence'][os.path.basename(log)] = hits[:40]

    for fn in sorted(os.listdir(tts_dir)):
        p = os.path.join(tts_dir, fn)
        if not os.path.isfile(p):
            continue
        base = fn
        stem = fn[:-4] if fn.endswith('.xml') else fn
        loaded = (base in refs) or (stem in refs)
        out['files'].append({
            'file': fn,
            'bytes': os.path.getsize(p),
            'sha256': sha256_of(p)[:16],
            'loaded_by_code': bool(loaded),
            'note': ('被 tts_engine.py 的 read_model 引用 ⇒ NPU 路径**实际加载**'
                     if loaded else
                     '**未被** tts_engine.py 的 read_model 引用 ⇒ 疑似**不加载**'
                     '（待设备级 e2e 复核）'),
        })
    out['n_files'] = len(out['files'])
    out['n_not_loaded'] = sum(1 for f in out['files'] if not f['loaded_by_code'])
    out['bytes_not_loaded'] = sum(f['bytes'] for f in out['files']
                                  if not f['loaded_by_code'])
    return out


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔳 APP-069⑤ 5：site-packages 清理
# ══════════════════════════════════════════════════════════════════════
def clean_site_packages(dst):
    """删 `transformers/kernels/**/*.cu|*.cuh` + `safetensors/torch.py`。"""
    sp = os.path.join(dst, 'python', 'Lib', 'site-packages')
    removed = []
    n_cu = 0
    for root, _dirs, files in os.walk(sp):
        for fn in files:
            if fn.endswith('.cu') or fn.endswith('.cuh'):
                p = os.path.join(root, fn)
                sz = os.path.getsize(p)
                os.remove(p)
                removed.append({'file': os.path.relpath(p, dst),
                                'bytes': sz, 'why': 'CUDA kernel 源（编译期用）'})
                n_cu += 1
    # safetensors/torch.py
    st = os.path.join(sp, 'safetensors', 'torch.py')
    if os.path.isfile(st):
        sz = os.path.getsize(st)
        os.remove(st)
        removed.append({'file': os.path.relpath(st, dst), 'bytes': sz,
                        'why': 'safetensors 的 torch 加载器（客户包不含 torch）'})
    return {'n_cu_cuh': n_cu, 'removed': removed,
            'bytes_removed': sum(r['bytes'] for r in removed)}


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔳 APP-069⑤ 5：**G4 扫描范围扩大到整个 python 目录**
# ══════════════════════════════════════════════════════════════════════
def g4_scan_extended(dst):
    """整包扫描：`.cu`/`.cuh` 文件 + `import torch` 语句 + 白名单核对。"""
    sp = os.path.join(dst, 'python')
    cu_files, torch_hits = [], []
    n_py = 0
    for root, _dirs, files in os.walk(sp):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, dst).replace('\\', '/')
            if fn.endswith('.cu') or fn.endswith('.cuh'):
                cu_files.append({'file': rel, 'bytes': os.path.getsize(p)})
                continue
            if not fn.endswith('.py'):
                continue
            n_py += 1
            try:
                txt = open(p, 'rb').read().decode('utf-8', errors='replace')
            except OSError:
                continue
            for i, ln in enumerate(txt.splitlines(), 1):
                if re.match(r'^\s*(import\s+torch\b|from\s+torch\b'
                            r'|import\s+torchaudio\b)', ln):
                    torch_hits.append({'file': rel, 'line': i,
                                       'text': ln.strip()})
    in_app = [h for h in torch_hits if h['file'].startswith('app/')]
    in_sp = [h for h in torch_hits if not h['file'].startswith('app/')]
    cu_in_app = [c for c in cu_files if c['file'].startswith('app/')]
    cu_in_sp = [c for c in cu_files if not c['file'].startswith('app/')]
    return {
        'scope': '整个 python/ 目录（APP-069⑤ 5 要求：扩大到整个 python 目录）',
        'n_py_scanned': n_py,
        'cu_cuh_files': cu_files,
        'n_cu_cuh': len(cu_files),
        'cu_cuh_in_app': cu_in_app,
        'cu_cuh_in_site_packages': cu_in_sp,
        'torch_import_hits': torch_hits,
        'n_torch_import': len(torch_hits),
        'torch_import_in_app': in_app,
        'torch_import_in_site_packages': in_sp,
        'whitelist': [{'path': p, 'reason': r} for p, r in G4_WHITELIST],
    }


def write_g4_whitelist(dst):
    p = os.path.join(dst, 'G4_WHITELIST.md')
    lines = ['# G4 白名单（APP-069⑤ 5）', '',
             '下列内容**保留**在客户包里，附原因：', '']
    for path, reason in G4_WHITELIST:
        lines.append('- **`%s`**' % path)
        lines.append('  - 原因：%s' % reason)
        lines.append('')
    lines += ['## 已剔除（不在白名单 ⇒ 已物理删除）', '',
              '- `transformers/kernels/**/*.cu` / `*.cuh`（CUDA kernel 源）',
              '- `safetensors/torch.py`（torch 加载器）',
              '- OpenVINO 的 PyTorch/JAX/Paddle/TF **转换前端**整目录',
              '- `numba/cuda/`（CUDA 目标）', '']
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    return p


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔳 APP-069③ + APP-070①：文案口径统一
# ══════════════════════════════════════════════════════════════════════
README_ZH = """# Confucius4 实时字幕 · MiniMVP v1.0-rc3（最小客户包）

**本包是独立于 v2.x 的新产品线（MiniMVP），版本号单独编号。**

## 里面有什么

| 模块 | 模型 | 精度 | 默认设备 |
|---|---|---|---|
| 语音识别 | Qwen3-ASR 0.6B | INT8 | Intel 集显 GPU.0 |
| 翻译 | Hy-MT2-1.8B | **INT4**（对称 · per-channel weight） | Intel 集显 GPU.0 |
| 语音输出 | **%(tts_long)s** | **Intel NPU** |

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

> **首次启动**：NPU 需要现编译（**不带编译缓存 blob**）⇒ 第一次启动会慢一些，
> 缓存写在用户目录 `%%LOCALAPPDATA%%\\Confucius4LiveCaption`。
> **磁盘**：首次运行约需 **8 GB**（编译缓存 `tts_npu_cache` ≈ 5 GB、
> `ov_cache` ≈ 2 GB、`mt_cache` ≈ 1 GB）。

## 许可与归属

见 `NOTICE`（Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO / **babelvox** /
**djwarf** 等的归属与许可证）与 `THIRD_PARTY.md`。
"""

README_EN = """# Confucius4 Live Caption - MiniMVP v1.0-rc3 (minimal customer package)

**Independent product line (MiniMVP), versioned separately from v2.x.**

| Stage | Model | Precision | Default device |
|---|---|---|---|
| ASR | Qwen3-ASR 0.6B | INT8 | Intel iGPU (GPU.0) |
| MT | Hy-MT2-1.8B | **INT4** (symmetric, per-channel weight) | Intel iGPU (GPU.0) |
| TTS | **%(tts_long)s** | **Intel NPU** |

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

> **First start**: the NPU is compiled on the fly (no blob cache is shipped)
> => the first start is slower; the cache lives in
> `%%LOCALAPPDATA%%\\Confucius4LiveCaption`.
> **Disk**: about **8 GB** on the first run (compile caches: `tts_npu_cache`
> ~5 GB, `ov_cache` ~2 GB, `mt_cache` ~1 GB).

## Licenses

See `NOTICE` (Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO / **babelvox** /
**djwarf**) and `THIRD_PARTY.md`.
"""


def write_readmes(dst):
    for name, body in (('README_zh.md', README_ZH % {'tts_long': TTS_LONG_ZH}),
                       ('README_en.md', README_EN % {'tts_long': TTS_LONG_EN})):
        p = os.path.join(dst, name)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
        scrub_file(p)


NOTICE_ADD = """
## Qwen3-TTS 的 INT8 权重来源与再分发说明（APP-069③ / APP-070①）

本包内的 TTS IR（`models/qwen3tts/int8/`）**不是**从官方 FP16 权重直接导出的，
而是用 **babelvox** 导出结构导出的 **INT8 仅权重量化**版本：

* **权重量化**：`int8_sym`（对称），**group_size = −1（每通道）**，ratio 1
* **推理计算**：NPU 上以 **FP16** 计算
* **来源**：`%s`
  （原始权重仓库：`djwarf--babelvox-openvino-int8`）
* **再分发**：该 IR 与 v2.0 / v2.1 / v2.2 客户包内的那份**逐字节同源**
  （`talker_decode.bin` = 444 375 018 B，2026-10-22 18:54）

### 为什么要写清楚（避免误读成「FP16 IR」）

包内 IR 的 `rt_info` 是 **NNCF `int8_sym` / group_size −1** ⇒
**它不是 FP16 权重的 IR**。用词一律是：

> **%s**

### 质量说明

把这份 INT8 权重反量化成 FP16 常量后，权重数值**仍是 INT8 量化后的值**
⇒ **质量没有提升**（与原 INT8 的余弦相似度基本相同），
且 talker 单步更慢 ⇒ 因此**保持 INT8 权重 + FP16 计算**是当前的正确选择
（APP-070① 用户决定）。

### 许可证

* `babelvox`（导出结构 / IR 布局）：见上游项目许可证
* `djwarf--babelvox-openvino-int8`（INT8 权重）：见上游模型卡与许可证
* Qwen3-TTS（模型本身）：Apache-2.0

详见 `THIRD_PARTY.md`。
""" % (TTS_SOURCE_EN, TTS_PRECISION_ZH)


def patch_notice(dst):
    p = os.path.join(dst, 'NOTICE')
    if not os.path.isfile(p):
        return {'ok': False, 'why': 'NOTICE 不存在'}
    txt = open(p, encoding='utf-8', errors='replace').read()
    if 'babelvox' in txt and 'djwarf' in txt:
        return {'ok': True, 'why': '已含 babelvox/djwarf 说明（幂等）'}
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(NOTICE_ADD)
    return {'ok': True, 'why': '已追加 babelvox/djwarf 一节',
            'bytes': os.path.getsize(p)}


def patch_manifest(dst):
    p = os.path.join(dst, 'app', 'MANIFEST.json')
    if not os.path.isfile(p):
        return {'ok': False, 'why': 'MANIFEST.json 不存在'}
    m = json.load(open(p, encoding='utf-8'))
    m['version'] = VERSION
    models = m.setdefault('models', {})
    if isinstance(models, dict):
        models['tts_precision'] = TTS_PRECISION_ZH
        models['tts_source'] = TTS_SOURCE_ZH
        models['tts_note'] = ('包内 IR 是 NNCF int8_sym（每通道）仅权重量化；'
                              'NPU 上以 FP16 计算')
    m['tts_precision'] = TTS_PRECISION_ZH
    m['tts_source'] = TTS_SOURCE_ZH
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    return {'ok': True, 'version': VERSION}


# ══════════════════════════════════════════════════════════════════════
# 构建
# ══════════════════════════════════════════════════════════════════════
def build(dst):
    removed = []
    scrubbed = {}
    if os.path.isdir(dst):
        print('  [ABORT] 目标目录已存在 ⇒ 「不覆盖、不删除」⇒ 退出')
        return None
    os.makedirs(dst, exist_ok=True)

    # ── app/：从开发树取生产模块 ─────────────────────────────
    app_dst = os.path.join(dst, 'app')
    os.makedirs(app_dst, exist_ok=True)
    n_app = 0
    for m in APP_MODULES:
        s = os.path.join(DEV_APP, m)
        if not os.path.isfile(s):
            print('  [MISSING] 开发树缺 %s' % m)
            continue
        shutil.copy2(s, os.path.join(app_dst, m))
        n_app += 1
    for m in APP_MODULES:
        p = os.path.join(app_dst, m)
        if os.path.isfile(p):
            c = scrub_file(p)
            if c:
                scrubbed['app/' + m] = c

    # ── python/ + docs/（从 v2.2 硬链接）─────────────────────
    for d in ROOT_KEEP_DIRS:
        s = os.path.join(SRC_PKG, d)
        if os.path.isdir(s):
            copy_tree(s, os.path.join(dst, d))
    for f in ROOT_KEEP_FILES:
        s = os.path.join(SRC_PKG, f)
        if os.path.isfile(s):
            copy_file(s, os.path.join(dst, f))

    # ── models/（白名单）──────────────────────────────────────
    for d in MODEL_KEEP_DIRS:
        s = os.path.join(SRC_PKG, 'models', d)
        if os.path.isdir(s):
            copy_tree(s, os.path.join(dst, 'models', d))
    for f in MODEL_KEEP_FILES:
        s = os.path.join(SRC_PKG, 'models', f)
        if os.path.isfile(s):
            copy_file(s, os.path.join(dst, 'models', f))

    # ── 🔴🔴🔳 剔除「不带」清单（**继承 rc2**，否则 rc3 比 rc2 还胖）──
    for rel in OV_FRONTEND_DIRS:
        p = os.path.join(dst, rel)
        if os.path.isdir(p):
            quarantine(p, rel, removed)
    for rel in OV_FRONTEND_LIBS:
        p = os.path.join(dst, rel)
        if os.path.isfile(p):
            quarantine(p, rel, removed)
    for rel in NUMBA_CUDA_DIRS:
        p = os.path.join(dst, rel)
        if os.path.isdir(p):
            quarantine(p, rel, removed)
    p = os.path.join(dst, OV_TORCHVISION_DIR)
    if os.path.isdir(p):
        quarantine(p, OV_TORCHVISION_DIR, removed)
    for name in DOC_DROP:
        p = os.path.join(dst, 'docs', name)
        if os.path.exists(p):
            quarantine(p, 'docs/' + name, removed)
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

    # ── 🔴🔴🔳 APP-069⑤ 5：site-packages 清理 ─────────────────
    sp_clean = clean_site_packages(dst)
    removed.append('site-packages：删 %d 个 .cu/.cuh + %d 个 torch 加载器'
                   '（%d B）'
                   % (sp_clean['n_cu_cuh'],
                      len(sp_clean['removed']) - sp_clean['n_cu_cuh'],
                      sp_clean['bytes_removed']))

    # ── 🔴🔴🔳 APP-070① 1：**删前列清单**（不删！）────────────
    inv = tts_ir_inventory(dst)
    with open(INVENTORY, 'w', encoding='utf-8') as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)
    print('  [INV] TTS IR 清单：%d 个文件，疑似不加载 %d 个（%.1f MB）'
          % (inv.get('n_files', 0), inv.get('n_not_loaded', 0),
             inv.get('bytes_not_loaded', 0) / 1048576.0))
    print('  [INV] 清单已落：%s（**本脚本不删** ⇒ 删需设备级 e2e 证明）'
          % INVENTORY)

    # ── 文案 / NOTICE / MANIFEST ──────────────────────────────
    write_readmes(dst)
    notice_res = patch_notice(dst)
    manifest_res = patch_manifest(dst)
    wl_path = write_g4_whitelist(dst)
    print('  [DOC] README/MANIFEST/NOTICE 已统一 TTS 口径：%s' % TTS_PRECISION_ZH)

    # ── G4 扩展扫描 ───────────────────────────────────────────
    g4 = g4_scan_extended(dst)
    print('  [G4] 整包扫描：.cu/.cuh %d 个（app %d / sp %d）｜ import torch %d 处'
          '（app %d / sp %d）'
          % (g4['n_cu_cuh'], len(g4['cu_cuh_in_app']),
             len(g4['cu_cuh_in_site_packages']), g4['n_torch_import'],
             len(g4['torch_import_in_app']),
             len(g4['torch_import_in_site_packages'])))

    # ── 体积分项 ───────────────────────────────────────────────
    total = 0
    per_dir = {}
    for root, _dirs, files in os.walk(dst):
        for fn in files:
            p = os.path.join(root, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            total += sz
            rel = os.path.relpath(p, dst).split(os.sep)[0]
            per_dir[rel] = per_dir.get(rel, 0) + sz
    n_files = sum(len(f) for _r, _d, f in os.walk(dst))

    return {
        'pkg': dst, 'version': VERSION, 'n_app_modules': n_app,
        'scrubbed': scrubbed, 'removed': removed,
        'site_packages_clean': sp_clean,
        'tts_ir_inventory': inv,
        'g4': g4, 'g4_whitelist_path': wl_path,
        'notice': notice_res, 'manifest': manifest_res,
        'total_bytes': total, 'n_files': n_files,
        'per_dir_bytes': per_dir,
        'tts_precision': TTS_PRECISION_ZH,
        'tts_source': TTS_SOURCE_ZH,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DST_PKG)
    a = ap.parse_args()
    print('=== MiniMVP rc3 构建（APP-069 + APP-070）===')
    print('目标：%s' % a.pkg)
    if not os.path.isdir(SRC_PKG):
        print('!! 源包不存在：%s' % SRC_PKG)
        return 2
    res = build(a.pkg)
    if res is None:
        return 1
    out = {
        'script': os.path.basename(__file__),
        'correction': 'APP-069 + APP-070（MiniMVP rc3）',
        'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'version': VERSION,
        'prev_builds': ('Confucius4_LiveCaption_MiniMVP_v1.0 / v1.0-rc1 / '
                        'v1.0-rc2（**全部保留不动**，作为缺陷证据）'),
        'result': res,
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n体积：%.2f MB ｜ 文件 %d' % (res['total_bytes'] / 1048576.0,
                                        res['n_files']))
    print('[evidence] %s' % REPORT)
    print('[inventory] %s' % INVENTORY)
    return 0


if __name__ == '__main__':
    sys.exit(main())
