#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app291_build_minimvp_rc4.py —— **MiniMVP v1.0-rc4 构建器**（补 NPU ASR 模型）。

## 用户需求（2026-11-10）

> MiniMVP rc3 缺 NPU ASR 模型，请补打包（新版本号，例如 MiniMVP v1.0-rc4，
> 不要改已交付的 rc3）
> 1. rc3 包的 models/ 里只有 GPU 版 ASR（encoder-int8、decoder-gpu-int8）。
>    全 NPU 交付后端 app/npu_delivery_backend.py 需要的模型没有打进去：
>    - models/ov-encoder-segment-reviewer（fp16 encoder）
>    - models/qwen3-lm-int8sym-cleanie-ov（inputs_embeds 因果 LM，NPU decoder INT8）
>    - models/c089_int4/R4（NPU decoder INT4）
>    _MODEL_ALIASES 对应的 encoder-fp16、decoder-npu-int8、decoder-npu-int4
>    都找不到，只剩 embed_tokens_f16.npy。
> 2. 要求：把以上三个 NPU IR 补进包，--check 必须显示
>    「Intel NPU · INT8 模型齐全」。iGPU 版模型保留。

## 为什么是 rc4（不是改 rc3）

rc3 是**已交付**的包（`shared/minimvp/*_perftest_rev2.zip`）⇒ **一字节不改**。
本脚本**新建** `Confucius4_LiveCaption_MiniMVP_v1.0-rc4` 目录。

## 本脚本做什么（**只加东西，不动别的**）

| # | 动作 | 依据 |
|---|---|---|
| ① | **以 rc3 目录为基底**复制出新目录（不是从 v2.2 重搭）⇒ rc3 的所有修正（APP-069/070、G4 白名单、NOTICE、README 计数）**逐字保留** | rc3 已验收 |
| ② | 补 3 个 NPU IR 目录：`encoder-fp16` / `decoder-npu-int8` / `decoder-npu-int4` | 用户需求 1 |
| ③ | iGPU 版模型（`encoder-int8` / `decoder-gpu-int8`）**保留** | 用户需求 2 |
| ④ | 版本号 rc3 → rc4（README_zh / README_en / NOTICE / MANIFEST） | 新版本号要求 |
| ⑤ | README_perftest.txt 同步 rc4 + 补「NPU ASR 已可用」说明 | 交付一致性 |
| ⑥ | **不写任何预编译 NPU 缓存进包**（实测包内 0 个 blob）⇒ 目标机首次运行现编 | 用户要求 4 |

## 🔴 关键：`NPUW` 属性（app289/app290 探针结论）

* **decoder 必须走 `NPU_USE_NPUW` + `NPUW_LLM`**：
  实测 plain（不开 NPUW）编不过 ⇒ `to_shape was called on a dynamic shape`。
* **encoder 必须先冻结形状**（`_freeze_encoder_for_npu`）⇒ 走 plain 即可，
  **不需要 NPUW**（NPUW 会把 encoder 当 LLM ⇒ `StatefulToStateless` 报错）。
* ⇒ **目标机（Meteor Lake）风险面**：NPUW 是 GenAI 插件能力，
  若目标机 NPU 驱动/NPUW 不支持 decoder，NPU ASR 起不来。
  本脚本**不改属性口径**（改属性＝改行为，需 reviewer 裁定），
  只在 STATUS/README 里**如实记录该风险 + 回落建议**。

## 用法
```
.venv/Scripts/python.exe results/app/_app291_build_minimvp_rc4.py --dry-run
.venv/Scripts/python.exe results/app/_app291_build_minimvp_rc4.py --run
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

#: 🔴 **基底**＝已交付的 rc3（逐字复制 ⇒ rc3 的修正全部保留）
BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
#: 🔴 **新目录**（rc3 一字节不改）
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
#: NPU IR 的**源**＝开发机完整包（v2.4；与 v2.2 逐字节一致，已用 SHA 核过）
SRC_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4')

VERSION = '1.0-rc4'
REPORT = os.path.join(HERE, 'app291_minimvp_rc4_build_evidence.json')

#: 🔴 **要补的 3 个 NPU IR**（用户需求 1 的原名 → 包内别名）
NPU_MODEL_DIRS = (
    # (开发机/源目录名, 包内目录名, 逻辑名(_MODEL_ALIASES 的 key))
    ('encoder-fp16', 'encoder-fp16', 'ov-encoder-segment-reviewer'),
    ('decoder-npu-int8', 'decoder-npu-int8',
     'qwen3-lm-int8sym-cleanie-ov'),
    ('decoder-npu-int4', 'decoder-npu-int4', 'c089_int4/R4'),
)

#: 🔴 iGPU 版模型**保留**（用户需求 2）⇒ 逐个核对它们在 rc4 里还在
IGPU_MODEL_DIRS = ('encoder-int8', 'decoder-gpu-int8')


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def dir_bytes(d: str) -> int:
    tot = 0
    for dp, _dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.isfile(p):
                tot += os.path.getsize(p)
    return tot


def copy_tree(s: str, d: str) -> None:
    """🔴 硬链接复制（同卷 ⇒ 零拷贝）—— 与 rc2/rc3 构建器**同一口径**。

    ⚠️⚠️⚠️ **写穿陷阱（本脚本第一版的真实事故）**：
    硬链接 ⇒ rc4 的每个文件与 rc3 **共享 inode** ⇒
    后续**原地写** rc4 的文件（`open(p,'w')`）会**同时改掉 rc3**！
    实测事故：改 rc4 的 NOTICE/README_zh/README_en ⇒ **rc3 的这 3 个文件
    被一起改成「rc4」字样** ⇒ 违反「不改已交付的 rc3」。
    ⇒ **凡是「要改写的文件」，必须先断链**（见 `unlink_then_write`）。
    ⇒ **只读的模型目录**保持硬链接（省 6.7 GB 磁盘）✔
    """
    shutil.copytree(s, d, copy_function=os.link)


def unlink_then_write(p: str, data: bytes) -> None:
    """🔴 **断链后写** ⇒ 只改这个文件，不动任何共享 inode 的兄弟。

    （先写到临时文件，再 `os.replace` ⇒ 原子替换 + 新 inode。）
    """
    tmp = p + '.unlink_tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)


def patch_text(p: str, pairs) -> list:
    """定点替换（唯一命中断言）。返回实际改动列表。

    🔴 **必须先断链**（硬链接 ⇒ 原地写会改到 rc3！见 `copy_tree` 的警告）。
    """
    if not os.path.isfile(p):
        return []
    with open(p, 'rb') as f:
        raw = f.read()
    try:
        txt = raw.decode('utf-8')
    except UnicodeDecodeError:
        return []
    orig = txt
    hits = []
    for old, new in pairs:
        n = txt.count(old)
        if n != 1:
            hits.append({'old': old[:60], 'count': n, 'applied': False,
                         'why': '不是唯一命中 ⇒ 不改'})
            continue
        txt = txt.replace(old, new, 1)
        hits.append({'old': old[:60], 'count': 1, 'applied': True})
    if txt != orig:
        # 🔴 断链后写 ⇒ rc3 不受影响
        unlink_then_write(p, txt.encode('utf-8'))
    return hits


def build(dry_run: bool) -> dict:
    res = {'script': os.path.basename(__file__), 'ts': now(),
           'version': VERSION, 'base': BASE_PKG, 'dst': DST_PKG,
           'dry_run': bool(dry_run)}
    if not os.path.isdir(BASE_PKG):
        res['verdict'] = 'BASE_MISSING'
        print('!! 基底不存在：%s' % BASE_PKG)
        return res

    # ── ① 基底逐字复制 ───────────────────────────────────────
    if os.path.exists(DST_PKG):
        print('!! 目标已存在 ⇒ 中止（不覆盖）：%s' % DST_PKG)
        res['verdict'] = 'DST_EXISTS_ABORT'
        return res
    if dry_run:
        res['would'] = ['copy %s -> %s' % (BASE_PKG, DST_PKG)]
        res['verdict'] = 'DRY_RUN'
        return res

    t0 = time.perf_counter()
    copy_tree(BASE_PKG, DST_PKG)
    res['base_copy_s'] = round(time.perf_counter() - t0, 2)
    print('✔ 基底已复制：%s' % DST_PKG, flush=True)

    # ── ② 补 3 个 NPU IR ─────────────────────────────────────
    added = {}
    for src_name, dst_name, logical in NPU_MODEL_DIRS:
        s = os.path.join(SRC_PKG, 'models', src_name)
        d = os.path.join(DST_PKG, 'models', dst_name)
        if not os.path.isdir(s):
            added[dst_name] = {'ok': False, 'why': '源不存在 %s' % s}
            continue
        if os.path.exists(d):
            added[dst_name] = {'ok': False, 'why': '目标已存在（不覆盖）'}
            continue
        t1 = time.perf_counter()
        copy_tree(s, d)
        files = {}
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                files[f] = {'bytes': os.path.getsize(p), 'sha256': sha(p)}
        added[dst_name] = {
            'ok': True, 'logical_name': logical, 'src': s,
            'bytes': dir_bytes(d), 'n_files': len(files), 'files': files,
            'copy_s': round(time.perf_counter() - t1, 2)}
        print('✔ 补 NPU IR：%s（%d 文件 / %.1f MB）'
              % (dst_name, len(files), dir_bytes(d) / 1048576.0), flush=True)
    res['npu_models_added'] = added

    # ── ③ iGPU 模型保留核对 ───────────────────────────────────
    kept = {}
    for d0 in IGPU_MODEL_DIRS:
        p = os.path.join(DST_PKG, 'models', d0)
        kept[d0] = {'exists': os.path.isdir(p),
                    'bytes': dir_bytes(p) if os.path.isdir(p) else 0}
    res['igpu_models_kept'] = kept
    print('✔ iGPU 模型保留核对：%s'
          % {k: v['exists'] for k, v in kept.items()}, flush=True)

    # ── ④ 版本号 rc3 → rc4 ───────────────────────────────────
    # ⚠️ 只在**文档**里改；app/*.py 不含版本号（已 grep 确认）
    doc_pairs = [('MiniMVP v1.0-rc3', 'MiniMVP v1.0-rc4'),
                 ('MiniMVP_v1.0-rc3', 'MiniMVP_v1.0-rc4')]
    ver_hits = {}
    for rel in ('README_zh.md', 'README_en.md', 'NOTICE', 'README_perftest.txt'):
        p = os.path.join(DST_PKG, rel)
        if os.path.isfile(p):
            ver_hits[rel] = patch_text(p, doc_pairs)
    res['version_patch'] = ver_hits

    # ── ⑤ MANIFEST 版本号（若存在）──────────────────────────
    mp = os.path.join(DST_PKG, 'app', 'MANIFEST.json')
    if os.path.isfile(mp):
        m = json.load(open(mp, encoding='utf-8'))
        m['version'] = VERSION
        models = m.setdefault('models', {})
        if isinstance(models, dict):
            models['npu_asr_models'] = [
                'encoder-fp16（= ov-encoder-segment-reviewer，fp16 encoder）',
                'decoder-npu-int8（= qwen3-lm-int8sym-cleanie-ov，'
                'inputs_embeds 因果 LM，INT8）',
                'decoder-npu-int4（= c089_int4/R4，INT4 实验档）']
            models['npu_asr_note'] = (
                '全 NPU ASR（--engine npu_int8 / npu_int4）所需 IR 已随包；'
                '编译缓存写在 %LOCALAPPDATA%\\Confucius4LiveCaption\\npu_cache，'
                '**不在包内** ⇒ 目标机首次运行现编（不含任何预编译 blob）。')
        # 🔴 断链后写（硬链接 ⇒ 原地写会改到 rc3！见 `copy_tree` 警告）
        unlink_then_write(mp, (json.dumps(m, ensure_ascii=False, indent=2)
                               + '\n').encode('utf-8'))
        res['manifest_patched'] = True
    else:
        res['manifest_patched'] = False

    # ── ⑥ 包内预编译缓存扫描（目标机可移植性）────────────────
    cache_hits = []
    for dp, _dn, fn in os.walk(DST_PKG):
        for f in fn:
            low = f.lower()
            if low.endswith('.blob') or low.endswith('.ovc') \
                    or 'npu_cache' in low or 'compilations' in low:
                cache_hits.append(os.path.relpath(os.path.join(dp, f), DST_PKG))
    res['precompiled_cache_in_pkg'] = cache_hits
    res['pkg_no_precompiled_npu_cache'] = (not cache_hits)
    print('✔ 包内预编译 NPU 缓存：%d 个' % len(cache_hits), flush=True)

    # ── ⑦ 体积 ───────────────────────────────────────────────
    res['base_bytes'] = dir_bytes(BASE_PKG)
    res['dst_bytes'] = dir_bytes(DST_PKG)
    res['delta_bytes'] = res['dst_bytes'] - res['base_bytes']
    res['n_files'] = sum(len(fn) for _dp, _dn, fn in os.walk(DST_PKG))
    print('✔ 体积：rc3 %.2f GB → rc4 %.2f GB（+%.2f GB）'
          % (res['base_bytes'] / 1073741824.0,
             res['dst_bytes'] / 1073741824.0,
             res['delta_bytes'] / 1073741824.0), flush=True)

    res['verdict'] = 'BUILT'
    return res


def _write(obj: dict) -> None:
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()
    dry = not args.run
    res = build(dry)
    _write(res)
    print(json.dumps({'out': REPORT, 'verdict': res.get('verdict'),
                      'delta_bytes': res.get('delta_bytes')},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
