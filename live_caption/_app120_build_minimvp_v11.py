#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §1：**从 v2.5 全集裁剪出 MiniMVP v1.1 客户包目录**。

## 目标（reviewer APP-120 §1 原文要点）
- ASR：只带 Qwen3-ASR 0.6B stateful INT8；不带 R2T2 1.7B
- MT：只带 Hy-MT2 INT8-CW
- TTS：只带 OpenVINO 版（不带 cuda_env / models/tts_cuda）
- 音色：只有预设 A（预设 B 不在包）；无克隆（allow_clone_voice=false）
- 10 语种；APP-116/117 界面改动全带（⇒ app/ 取 v2.5 的）
- 出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU；设备自由配置、无 NPU 互斥（APP-119）
- EXT：照 rc11 的口径（**从 v2.5 取 v0.4.18**；去掉与根目录逐字节重复的
  `ext/.runtime_deps` ⇒ 与 rc11 的 ext 布局一致）⇒ §2 再冒烟，如实写 README
- **bridge_token.txt / *.pid / *.log 一律不得进包**

## 纪律
🔴 **不删任何东西**（本机有安全删除 shim）⇒ 裁剪 = 「挑文件进清单」；
🔴 **不改** rc11 / v2.5 / sp5（只读来源）；
🔴 **不写 ACCEPTED.json**（验收通过后才签，见 `_app120_sign_accepted.py`）。

## 用法
```
python live_caption/_app120_build_minimvp_v11.py --dry-run
python live_caption/_app120_build_minimvp_v11.py --apply
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
sys.path.insert(0, HERE)

from package_profiles import PROFILE_RULES, is_excluded, top_dirs  # noqa: E402

SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1')
RESULTS = os.path.join(REPO, 'results', 'app')

VERSION = '1.1'

#: 🔴 **在 APP-118 minimvp profile 之上追加的排除项**（照 rc11 口径 + APP-120 §1）
EXTRA_EXCLUDE = [
    # ① 说话人模型：rc11 的 models/ 里**没有** spk/（MiniMVP 不带音色克隆/说话人旁路）
    'models/spk',
    # ② R2T2 的 tokenizer（rc11 没有；MiniMVP 只用 asr06b-tokenizer）
    'models/tokenizer',
    # ③ ext/.runtime_deps：**与包根 .runtime_deps 逐字节重复**（82 文件全等）
    #    且 ext/bridge **不引用**它 ⇒ 按 rc11 的 ext 布局排除
    'ext/.runtime_deps',
    # ④ CUDA 文档（MiniMVP 无 CUDA）
    'docs/CUDA_TTS.md',
    # ⑤ v2.5 的 ACCEPTED.json 是 **v2.4 的逐字节副本** ⇒ 绝不拷贝
    'ACCEPTED.json',
]

#: 🔴 **文件级黑名单**（APP-120 §1 明令 + APP-105 §2 黑名单）
BLACKLIST_NAMES = ('bridge_token.txt',)
BLACKLIST_EXTS = ('.pid', '.log')
BLACKLIST_SUFFIX = ('.bak', '.pyc')
BLACKLIST_DIR_PARTS = ('__pycache__',)


def is_blacklist(rel: str) -> str:
    """返回命中原因；不命中返回空串。"""
    parts = rel.split('/')
    name = parts[-1]
    if any(p in BLACKLIST_DIR_PARTS for p in parts):
        return 'pycache'
    if name in BLACKLIST_NAMES:
        return 'blacklist_name'
    if name.endswith(BLACKLIST_SUFFIX):
        return 'blacklist_suffix'
    if name.lower().endswith(BLACKLIST_EXTS):
        return 'blacklist_ext'
    if name.startswith('.superseded-'):
        return 'superseded'
    # 🔴 **编译缓存 blob 不进包**（铁律：「编译缓存绝不写包内」）
    #   `models/qwen3tts/*.blob` 是 OpenVINO **已编译二进制**
    #   （文件头 `<?xml version="1.0"?><compiled_blob ie_v…>`），
    #   GPU blob 头写死 ie_version、oneDNN kernel 绑 CPU 微架构 ⇒ 客户机基本不命中；
    #   **包内代码无任何一处按名加载 `*.blob`**（已 grep 确认只有注释提到），
    #   且 **rc11（已交付的 MiniMVP）里也没有它们** ⇒ 照 rc11 口径排除。
    if name.endswith('.blob') and parts[0] == 'models':
        return 'compiled_blob_cache'
    return ''


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def plan():
    """遍历来源 ⇒ 返回 (keep 清单, drop 清单)。"""
    excludes = list(PROFILE_RULES['minimvp']['exclude']) + EXTRA_EXCLUDE
    keep, drop = [], []
    for dp, dns, fns in os.walk(SRC):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, SRC).replace(os.sep, '/')
            size = os.path.getsize(full)
            if is_excluded(rel, excludes):
                drop.append((rel, size, 'profile_exclude'))
                continue
            why = is_blacklist(rel)
            if why:
                drop.append((rel, size, why))
                continue
            keep.append((rel, size))
    keep.sort()
    drop.sort()
    return keep, drop, excludes


def write_profile_marker(dst: str):
    marker = {
        'profile': 'minimvp',
        'allow_cuda': False,
        'allow_clone_voice': False,
        'target_langs': 10,
        'note': ('APP-120 §1（2026-11-22）：从 v2.5 全集按 minimvp profile 裁出的'
                 'MiniMVP v1.1。ASR 只带 Qwen3-ASR 0.6B stateful INT8（含 ASR-065/066 '
                 '优化：NPUW MAX_PROMPT_LEN=320 + 前缀左截断 + asr_enc_tiers 默认 off）；'
                 'MT 只带 INT8-CW；TTS 只带 OpenVINO（无 CUDA）；音色只有预设 A；'
                 '无克隆；出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU（APP-119 自由配置）。'),
    }
    p = os.path.join(dst, 'package_profile.json')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(marker, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return marker


def write_release_json(dst: str, ext_version: str):
    rel = {
        'release': True,
        'version': VERSION,
        'asr_model': 'Qwen3-ASR-0.6B',
        'asr_recipe': ('stateful INT8 with KV cache (NPUW_LLM on NPU)；'
                       'ASR-065/066 优化：NPUW_LLM_MAX_PROMPT_LEN=320 + '
                       '超长前缀按 token 左截断（prefix_truncations 计数）'),
        'asr_engines': ['gpu_int8', 'npu_int8'],
        'package_profile': 'package_profile.json',
        'ext': {'version': ext_version,
                'note': '照 rc11 口径：EXT 嵌在包内 ext/（ASR 在 MiniMVP 里'
                        '是否可用见 README「已知问题」）'},
        'corrections': ['APP-120'],
        'v1.1_changes': [
            'APP-120 §0：ASR-065/066 优化接入（pml 320 + 前缀左截断 + '
            'asr_enc_tiers 默认 off + 分档失败自动退回 2400 单档）',
            'APP-120 §1：从 v2.5 全集按 minimvp profile 裁剪（ASR 只 0.6B / '
            'MT 只 INT8-CW / TTS 只 OV / 只预设 A / 无克隆）',
            'APP-120 §1：出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU（APP-119 自由配置）',
            'APP-120 §1：APP-116/117 界面改动（耳机输出修复、去掉 4 个选项、'
            '去掉总状态灯）全部带上',
            'APP-120 §2：验收（自检 + 洁净度 + 模型身份 + 10 分钟整链 + 10 语种 + '
            '设备切换 + 全新目录/旧配置迁移）',
        ],
    }
    p = os.path.join(dst, 'release.json')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return rel


def update_manifest(dst: str):
    """更新 app/MANIFEST.json：version → 1.1，files/bytes 重算。"""
    mp = os.path.join(dst, 'app', 'MANIFEST.json')
    with open(mp, 'r', encoding='utf-8') as f:
        man = json.load(f)
    n_files = 0
    n_bytes = 0
    for dp, dns, fns in os.walk(dst):
        if os.path.basename(dp) == '__pycache__':
            dns[:] = []
            continue
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                n_bytes += os.path.getsize(p)
            except OSError:
                pass
            n_files += 1
    man['version'] = VERSION
    man['files'] = n_files
    man['bytes'] = n_bytes
    man['notes'] = ('MiniMVP v1.1（APP-120，2026-11-22）：从 v2.5 全集按 minimvp '
                    'profile 裁剪。ASR=Qwen3-ASR 0.6B stateful INT8（含 ASR-065/066）、'
                    'MT=Hy-MT2 INT8-CW、TTS=OpenVINO（无 CUDA）、音色只有预设 A、'
                    '无克隆、10 语种、出厂默认 ASR=GPU.0/MT=GPU.0/TTS=NPU。')
    tmp = mp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    os.replace(tmp, mp)
    return {'version': man['version'], 'files': n_files, 'bytes': n_bytes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正拷贝（默认 dry-run）')
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--dst', default=DST)
    args = ap.parse_args()
    src, dst = args.src, args.dst

    if not os.path.isdir(src):
        print('FAIL: 来源包不存在 %s' % src)
        return 2

    print('PID=%d' % os.getpid(), flush=True)
    print('BUILD_SRC=%s' % src, flush=True)
    print('BUILD_DST=%s' % dst, flush=True)
    print('BUILD_TS=%s' % time.strftime('%Y-%m-%d %H:%M:%S'), flush=True)

    keep, drop, excludes = plan()
    kb = sum(s for _r, s, *_ in keep)
    db = sum(s for _r, s, *_ in drop)
    print('=' * 72)
    print('[APP-120] MiniMVP v1.1 裁剪（来源 %s）' % src)
    print('=' * 72)
    print('保留：%d 文件 / %d B（%.3f GiB）'
          % (len(keep), kb, kb / 1024 ** 3))
    print('排除：%d 文件 / %d B（%.3f GiB）'
          % (len(drop), db, db / 1024 ** 3))
    by = {}
    for r, s, why in drop:
        by[why] = by.get(why, 0) + 1
    print('排除原因分布：%s' % by)
    print()
    print('体积构成（保留部分，按顶层）：')
    for r in top_dirs([(r, s) for r, s, *_ in keep], limit=99):
        print('  %-18s %8d 文件  %14d B  %8.3f GiB'
              % (r['name'], r['files'], r['bytes'], r['gib']))
    print()

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    if os.path.exists(dst):
        print('FAIL: 目标目录已存在 %s ⇒ 不覆盖（APP-055）' % dst)
        return 2

    t0 = time.time()
    n = 0
    for rel, size in keep:
        s = os.path.join(src, rel.replace('/', os.sep))
        d = os.path.join(dst, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        n += 1
        if n % 5000 == 0:
            print('  … %d/%d（%.1f min）' % (n, len(keep), (time.time() - t0) / 60),
                  flush=True)
    print('拷贝完成：%d 文件 / %.1f min' % (n, (time.time() - t0) / 60))

    ext_ver = '0.4.18'
    ep = os.path.join(dst, 'ext', 'release.json')
    if os.path.isfile(ep):
        try:
            with open(ep, 'r', encoding='utf-8') as f:
                ext_ver = json.load(f).get('version') or ext_ver
        except Exception:
            pass
    write_profile_marker(dst)
    write_release_json(dst, ext_ver)
    man = update_manifest(dst)

    ev = {
        'script': '_app120_build_minimvp_v11.py',
        'task': 'APP-120 §1：从 v2.5 全集裁剪 MiniMVP v1.1',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'src': src, 'dst': dst,
        'version': VERSION,
        'excludes': excludes,
        'extra_exclude': EXTRA_EXCLUDE,
        'kept_files': len(keep), 'kept_bytes': kb,
        'dropped_files': len(drop), 'dropped_bytes': db,
        'drop_reasons': by,
        'manifest': man,
        'ext_version': ext_ver,
        'top_dirs': top_dirs([(r, s) for r, s, *_ in keep], limit=99),
    }
    os.makedirs(RESULTS, exist_ok=True)
    op = os.path.join(RESULTS, 'app120_build_minimvp_v11.json')
    tmp = op + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(tmp, op)
    print('构建证据：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
