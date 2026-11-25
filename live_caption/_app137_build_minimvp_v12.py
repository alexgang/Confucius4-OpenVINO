#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_build_minimvp_v12.py — **APP-137 §2：生成 MiniMVP v1.2 候选目录**。

## reviewer APP-137 §2 原文
> **生成候选目录** `Confucius4_LiveCaption_MiniMVP_v1.2.candidate\`
> （**不打 zip，不签 ACCEPTED**）。

## 本脚本裁剪什么（**来源 = 完整版 v2.6**，与 v1.1.1 的来源 v2.5 不同）

🔴 **来源必须是 v2.6**：v1.1.1 是从 v2.5 裁的，而 v2.6 才带
① EXT `b2a4978`（v0.4.21）② `models/bgsep`（Demucs）③ APP-130 的
`cp NPU 自检 + NaN 守卫`（v2.6 的 `tts_engine.py` / `tts_worker.py`）。

## 裁剪口径（= dev 树 `package_profiles.py` 的 minimvp 规则 + APP-137 追加项）

| 内容 | v1.2 | 依据 |
|---|---|---|
| ASR | 只 Qwen3-ASR 0.6B（去 R2T2 1.7B） | minimvp profile |
| MT | 只 Hy-MT2 INT8-CW（**留好切 MT3 的开关**） | APP-137 §1 |
| TTS | 只 OpenVINO（**无 CUDA**） | minimvp profile |
| **EXT** | **与 v2.6 一致**（`b2a4978` / v0.4.21） | APP-137 §1 |
| **`models/bgsep`** | **带**（Demucs OV IR，GPU.0 FP32） | APP-137 §1 |
| **`models/spk`** | **带**（pyannote 分段 + wespeaker x-vector） | APP-137 §1 |
| 克隆音色 | **包内目录必须为空**（首次使用现场采集） | APP-137 §1「铁律」 |
| CUDA | **不带**（`cuda_env/` + `models/tts_cuda/`） | minimvp profile |
| 出厂默认 | **ASR=GPU.0 / MT=GPU.0 / TTS=NPU**（**不变**） | APP-137 §1 |
| c13 | **不进 MiniMVP**（还没验收） | APP-137 §1 |

## 🔴 纪律
* **不删任何东西**（本机有「安全删除 shim」⇒ 删除会被拦）⇒ 裁剪 = **挑文件进清单**；
* **不打 zip、不签 ACCEPTED**（reviewer 复核通过后才出 zip）；
* 目标目录**已存在就拒绝**（不覆盖）；
* **客户包铁律**：包内**不得**有 `.wav/.ogg/.mp3/.mp4` 等媒体文件
  （`preset_A.wav` 是**内置音色**，不在禁列 —— 见下）；
* `--dry-run` **不写任何文件**。

## 用法
```
python live_caption/_app137_build_minimvp_v12.py --dry-run
python live_caption/_app137_build_minimvp_v12.py --apply
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

SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.candidate')
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app137_build_minimvp_v12.json')

VERSION = '1.2'

#: 🔴 **在 APP-137 改造后的 minimvp profile 之上追加的排除项**
#: （`package_profiles.py` 已去掉 `models/spk` / `models/bgsep` 的排除）
EXTRA_EXCLUDE = [
    # ① R2T2 的 tokenizer（MiniMVP 只用 asr06b-tokenizer）
    'models/tokenizer',
    # ② ext/.runtime_deps：**与包根 .runtime_deps 逐字节重复** ⇒ 按 rc11 口径排除
    'ext/.runtime_deps',
    # ③ CUDA 文档（MiniMVP 无 CUDA）
    'docs/CUDA_TTS.md',
    # ④ v2.6 的 ACCEPTED.json 是**别的版本的副本** ⇒ 绝不拷贝
    #    （🔴 v1.2 **不签 ACCEPTED** ⇒ 候选目录里也**不该有**它）
    'ACCEPTED.json',
    # ⑤ 🔴 **克隆音色目录**：v2.6 的 `models/qwen3tts/voices/` 里只有
    #    `preset_A.wav`（**内置音色**⇒ 必须留），但**任何**克隆出来的音色/
    #    录音/同事声音/样例都在这个目录下 ⇒ 逐个文件白名单（见 `VOICE_ALLOW`）
    #    ⇒ 其余**一律不带**。
    #    ⚠️ **这里不能用目录级排除**（会把 `preset_A.wav` 也排掉）⇒
    #    改由 `is_blacklist()` 的白名单逐文件判定。
]

#: 🔴 `models/qwen3tts/voices/` 里**唯一允许**进包的文件（内置音色 A）
VOICE_ALLOW = {'preset_A.wav'}

#: 🔴 **客户包铁律**：包内**不得**有的媒体文件扩展名
#: （`preset_A.wav` 是内置音色 ⇒ 由上面的白名单单独放行）
MEDIA_EXTS = ('.wav', '.ogg', '.mp3', '.mp4', '.m4a', '.flac', '.aac', '.wma')


def is_blacklist(rel: str) -> str:
    """返回命中原因；不命中返回空串。"""
    parts = rel.split('/')
    name = parts[-1]
    if any(p == '__pycache__' for p in parts):
        return 'pycache'
    if name == 'bridge_token.txt':
        return 'bridge_token'
    if name.endswith(('.pid', '.log')):
        return 'runtime_file'
    if name.endswith(('.bak', '.pyc')):
        return 'bak_or_pyc'
    if name.startswith('.superseded-'):
        return 'superseded'
    # 🔴 编译缓存 blob 不进包（客户机基本不命中）
    if name.endswith('.blob') and parts[0] == 'models':
        return 'compiled_blob_cache'
    # 🔴 **克隆音色目录**：只放行 `preset_A.wav`
    #    （⚠️ 这一条**必须**在下面的「媒体文件铁律」**之前**判 ——
    #      否则 `preset_A.wav` 会先被 `.wav` 规则拦掉 ⇒ 内置音色丢失。）
    if rel.startswith('models/qwen3tts/voices/'):
        if name not in VOICE_ALLOW:
            return 'voice_not_allowed'
        return ''          # ← 内置音色 A：**放行**（不走媒体铁律）
    return ''


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def plan():
    """遍历来源 ⇒ 返回 (keep, drop, excludes)。"""
    excludes = list(PROFILE_RULES['minimvp']['exclude']) + EXTRA_EXCLUDE
    keep, drop = [], []
    for dp, dns, fns in os.walk(SRC):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, SRC).replace(os.sep, '/')
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            if is_excluded(rel, excludes):
                drop.append((rel, size, 'profile_exclude'))
                continue
            why = is_blacklist(rel)
            if why:
                drop.append((rel, size, why))
                continue
            # 🔴 **媒体文件铁律**（`preset_A.wav` 是内置音色 ⇒ 白名单放行）
            if rel.lower().endswith(MEDIA_EXTS):
                if not (rel.startswith('models/qwen3tts/voices/')
                        and os.path.basename(rel) in VOICE_ALLOW):
                    drop.append((rel, size, 'media_file'))
                    continue
            keep.append((rel, size, full))
    keep.sort()
    drop.sort()
    return keep, drop, excludes


def write_profile_marker(dst: str):
    """写 `package_profile.json`（**APP-137 改造后的 minimvp 标记**）。"""
    marker = dict(PROFILE_RULES['minimvp']['marker'])
    marker['note'] = (
        'MiniMVP v1.2（APP-137，2026-11-25，用户决定）：EXT 的全部功能'
        '（含「保留背景音」bgkeep）＋ 音色克隆并入 MiniMVP；'
        '仍只有 iGPU/NPU（无 CUDA）；出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU；'
        'MT 暂时用 Hy-MT2（切 MT3 的开关已留好）；'
        'APP-123 的 c13 尚未验收 ⇒ 本包不启用 c13。'
        '包内不含任何录音、克隆音色、同事声音或测试媒体；'
        '克隆音色在首次使用时现场采集。')
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
        'asr_recipe': ('stateful INT8 with KV cache（KV cache，'
                       'NPU 档 prompt 上界 320 + 超长前缀按 token 左截断）'),
        'asr_engines': ['gpu_int8', 'npu_int8'],
        'package_profile': 'package_profile.json',
        'ext': {'version': ext_version,
                'note': '与完整版一致（EXT v0.4.21）：桥接 + 插件（含「保留背景音」）'},
        'corrections': ['APP-137'],
        'v1.2_changes': [
            '并入 EXT 的全部功能（含「保留背景音」）：带分离模型，'
            '默认开启，与完整版一致',
            '并入音色克隆：克隆所需的模型与代码全部带上；'
            '包内克隆音色目录为空，首次使用时现场采集',
            '仍只有 iGPU/NPU（无 CUDA）；出厂默认设备不变：'
            'ASR=GPU.0 / MT=GPU.0 / TTS=NPU',
            '翻译模型暂时沿用上一版；切换到新版翻译模型的开关已预留',
            '声码器仍用上一版的窗口口径（新窗口方案尚未验收，暂不启用）',
        ],
    }
    p = os.path.join(dst, 'release.json')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return rel


def update_manifest(dst: str):
    """更新 `app/MANIFEST.json`：version → 1.2，files/bytes 重算。"""
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
    man['notes'] = (
        'MiniMVP v1.2（APP-137，2026-11-25）：并入 EXT 全部功能（含「保留背景音」）'
        '与音色克隆；ASR=Qwen3-ASR 0.6B stateful INT8、MT=Hy-MT2 INT8-CW、'
        'TTS=OpenVINO（无 CUDA）、10 语种、'
        '出厂默认 ASR=GPU.0/MT=GPU.0/TTS=NPU；'
        '包内不含任何录音、克隆音色或测试媒体。')
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
    print('[APP-137] MiniMVP v1.2 候选目录裁剪（来源 %s）' % src)
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
    for row in top_dirs([(r, s) for r, s, _ in keep], limit=99):
        print('  %-18s %8d 文件  %14d B  %8.3f GiB'
              % (row['name'], row['files'], row['bytes'], row['gib']))
    print()

    # 🔴 **关键内容核对**（构建前就能看出来）
    def has(prefix):
        return any(rel.startswith(prefix) for rel, _s, *_ in keep)
    print('关键内容核对：')
    for label, prefix, want in [
        ('EXT 桥接', 'ext/bridge/bridge.py', True),
        ('EXT 插件', 'ext/extension/popup.js', True),
        ('Demucs 分离模型', 'models/bgsep/htdemucs_core.xml', True),
        ('克隆链 IR（x-vector）', 'models/spk/wespeaker-resnet34-fp16', True),
        ('克隆链 IR（说话人分段）', 'models/spk/pyannote_seg_3_0', True),
        ('内置音色 A', 'models/qwen3tts/voices/preset_A.wav', True),
        ('CUDA 运行时', 'cuda_env/', False),
        ('CUDA TTS 模型', 'models/tts_cuda/', False),
        ('R2T2 编码器', 'models/encoder-fp16', False),
        ('R2T2 解码器', 'models/decoder-npu-int8', False),
        ('MT INT4', 'models/mt/mt2-int4sym-cw-q', False),
        ('旧包 ACCEPTED', 'ACCEPTED.json', False),
    ]:
        got = has(prefix)
        ok = (got == want)
        print('  [%s] %-24s 期望存在=%s 实测=%s'
              % ('OK' if ok else 'XX', label, want, got))
        if not ok:
            print('FAIL: 关键内容核对不通过 ⇒ 零改动')
            return 3
    # 🔴 克隆音色目录**必须只有** preset_A.wav
    voices = sorted(rel for rel, _s, *_ in keep
                     if rel.startswith('models/qwen3tts/voices/'))
    print('  克隆音色目录内容：%s' % voices)
    if voices != ['models/qwen3tts/voices/preset_A.wav']:
        print('FAIL: 克隆音色目录不只含 preset_A.wav ⇒ 零改动')
        return 3
    print()

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    if os.path.exists(dst):
        print('FAIL: 目标目录已存在 %s ⇒ 不覆盖（APP-055）' % dst)
        return 2

    t0 = time.time()
    n = 0
    for rel, size, full in keep:
        d = os.path.join(dst, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(full, d)
        n += 1
        if n % 5000 == 0:
            print('  … %d/%d（%.1f min）' % (n, len(keep), (time.time() - t0) / 60),
                  flush=True)
    print('拷贝完成：%d 文件 / %.1f min' % (n, (time.time() - t0) / 60))

    ext_ver = '0.4.21'
    ep = os.path.join(dst, 'ext', 'release.json')
    if os.path.isfile(ep):
        try:
            with open(ep, 'r', encoding='utf-8') as f:
                ext_ver = json.load(f).get('version') or ext_ver
        except Exception:
            pass
    marker = write_profile_marker(dst)
    release = write_release_json(dst, ext_ver)
    man = update_manifest(dst)

    ev = {
        'script': '_app137_build_minimvp_v12.py',
        'task': 'APP-137 §2：生成 MiniMVP v1.2 候选目录（不打 zip、不签 ACCEPTED）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'src': src, 'dst': dst, 'version': VERSION,
        'excludes': excludes,
        'extra_exclude': EXTRA_EXCLUDE,
        'kept_files': len(keep), 'kept_bytes': kb,
        'dropped_files': len(drop), 'dropped_bytes': db,
        'drop_reasons': by,
        'marker': marker,
        'release': release,
        'manifest': man,
        'ext_version': ext_ver,
        'voices_in_pkg': voices,
        'top_dirs': top_dirs([(r, s) for r, s, _ in keep], limit=99),
        'signed_accepted': False,
        'zip_built': False,
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('构建证据：%s' % EVIDENCE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
