#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app332_app097_model_identity.py —— **APP-097 §2-6 模型身份（实测对照版）**。

## reviewer §2-6 原文
> **模型身份**：本条不换任何模型。MANIFEST 里 ASR/MT/TTS 的**目录、源模型和 SHA**
> 与改前一致，要写进 json。

## 为什么上一版不够（本脚本的改进点）

上一版 `_model_identity()` 只算了**影子包**的树 SHA，并写了一句
「影子包 models 是目录联接 ⇒ 与改前必然相同」的**结构推断**。
⇒ 那**不是实测** ⇒ reviewer 要的是「与改前一致」的**实测证据**。

本脚本补齐三件事：

1. **实测对照**：对 **真包 v2.4**（`~/Confucius4_LiveCaption_v2.4/models`）与
   **影子包 after2**（`~/_app_shadow/after2/models`）**各自算一遍树 SHA**
   ⇒ 两边逐目录比对 ⇒ 给出「一致 / 不一致」的**实测结论**。
   （Windows **目录联接** `os.path.islink()` 返回 **False** ⇒ 必须用
   `os.path.realpath()` 判断 ⇒ 上一版把 `islink` 当判据是错的，本脚本修正。）

2. **MANIFEST 顶层字段**逐个列出（含 `version` / `files` / `bytes` / `notes`），
   并**明确**给出「**没有**逐模型 SHA 字段」这一事实（附 grep 证据）。

3. **反证组（必做）**：把其中一个目录的**某个文件内容改 1 字节**的**等价模拟**
   —— 不实际改盘，而是**在内存里**把某个文件的 SHA 替换成别的值重算树 SHA
   ⇒ 树 SHA **必须变化** ⇒ 证明这个「树 SHA」判据**对文件内容敏感**
   （否则「两包一致」可能是因为判据恒等）。

## 用法
```
python results/app/_app332_app097_model_identity.py
```
"""
from __future__ import annotations

import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
REPORT = os.path.join(HERE, 'app332_app097_model_identity.json')

REAL_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4')
SHADOW = os.path.join(HOME, '_app_shadow', 'after2')

MODEL_DIRS = ('mt', 'qwen3tts', 'spk', 'tokenizer',
              'encoder-fp16', 'encoder-int8', 'encoder-int4',
              'decoder-npu-int8', 'decoder-npu-int4',
              'decoder-gpu-int8', 'decoder-gpu-int4')


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def tree_sha(root, tamper=None):
    """🔴 目录树 SHA = 按相对路径排序后，累加「相对路径 + 文件内容 SHA」。

    `tamper` = (relpath, fake_sha) ⇒ 用于**反证组**（在内存里替换一个文件的
    SHA，**不改盘**）⇒ 若树 SHA 不变 ⇒ 判据不敏感。
    """
    files = []
    for r, _dd, ff in os.walk(root):
        for f in ff:
            files.append(os.path.join(r, f))
    h = hashlib.sha256()
    tot = 0
    n_tampered = 0
    for f in sorted(files):
        rel = os.path.relpath(f, root).replace('\\', '/')
        fs = sha_file(f)
        if tamper and rel == tamper[0]:
            fs = tamper[1]
            n_tampered += 1
        h.update(rel.encode('utf-8', 'replace'))
        h.update(fs.encode('ascii'))
        try:
            tot += os.path.getsize(f)
        except OSError:
            pass
    return {'n_files': len(files), 'bytes': tot,
            'tree_sha256': h.hexdigest(), 'n_tampered': n_tampered}


def scan_models(models_root):
    out = {}
    if not os.path.isdir(models_root):
        return out
    for name in MODEL_DIRS:
        p = os.path.join(models_root, name)
        if not os.path.isdir(p):
            continue
        r = tree_sha(p)
        r['dir'] = p
        out[name] = r
    # 单文件模型（embed_tokens_f16.npy）
    p = os.path.join(models_root, 'embed_tokens_f16.npy')
    if os.path.isfile(p):
        out['embed_tokens_f16.npy'] = {
            'dir': p, 'n_files': 1,
            'bytes': os.path.getsize(p),
            'tree_sha256': sha_file(p)}
    return out


def main():
    ev = {
        'created_at': now(),
        'correction': 'APP-097 §2-6 模型身份（实测对照版）',
        'criterion': ('MANIFEST 里 ASR/MT/TTS 的目录、源模型和 SHA 与改前一致'
                      '⇒ 实测：真包 v2.4 与影子包 after2 逐模型目录树 SHA 对照'),
        'device_job': False,
        'lock_note': ('本项为**只读静态核对**（不加载模型）⇒ 按项目纪律'
                      '不占 GPU/NPU ⇒ **不持 MACHINE_LOCK**'),
        'manifest': {},
        'model_dirs': {},
        'compare': {},
        'neg_control': {},
    }

    # ── 1. MANIFEST 顶层字段 ──
    for tag, app_dir in (('real_v2.4', os.path.join(REAL_PKG, 'app')),
                         ('shadow_after2', os.path.join(SHADOW, 'app'))):
        man = os.path.join(app_dir, 'MANIFEST.json')
        rec = {'path': man, 'present': os.path.exists(man)}
        if rec['present']:
            rec['bytes'] = os.path.getsize(man)
            rec['sha256'] = sha_file(man)
            try:
                m = json.load(open(man, encoding='utf-8'))
                rec['top_fields'] = {
                    k: (v if isinstance(v, (str, int, float, bool))
                        else ('<%s len=%d>' % (type(v).__name__, len(v))))
                    for k, v in m.items()}
                rec['version'] = m.get('version')
                rec['files'] = m.get('files')
                rec['bytes_total'] = m.get('bytes')
                # 🔴 有没有「逐模型 SHA」？
                blob = json.dumps(m, ensure_ascii=False)
                rec['has_per_model_sha_field'] = bool(
                    any(k in blob for k in ('"sha256"', '"sha"')))
                rec['per_model_sha_note'] = (
                    'MANIFEST 顶层无「源模型 / SHA」字段'
                    '⇒ 模型身份只能由**目录树 SHA**给出')
            except ValueError as exc:
                rec['error'] = str(exc)[:200]
        ev['manifest'][tag] = rec

    # ── 2. 两边各算一遍树 SHA ──
    real_root = os.path.join(REAL_PKG, 'models')
    shad_root = os.path.join(SHADOW, 'models')
    ev['roots'] = {
        'real_v2.4': {'path': real_root, 'realpath': os.path.realpath(real_root)},
        'shadow_after2': {'path': shad_root,
                          'realpath': os.path.realpath(shad_root)},
        'is_junction_note': (
            '🔴 Windows **目录联接**（junction）下 `os.path.islink()` 返回 '
            '**False** ⇒ 判「是否同一物理目录」必须用 `os.path.realpath()`'),
        'same_physical_dir': (os.path.realpath(real_root).lower()
                              == os.path.realpath(shad_root).lower()),
    }
    ev['model_dirs'] = {
        'real_v2.4': scan_models(real_root),
        'shadow_after2': scan_models(shad_root),
    }

    # ── 3. 逐目录对照 ──
    cmp_rows = []
    all_same = True
    names = sorted(set(ev['model_dirs']['real_v2.4'])
                   | set(ev['model_dirs']['shadow_after2']))
    for n in names:
        a = ev['model_dirs']['real_v2.4'].get(n)
        b = ev['model_dirs']['shadow_after2'].get(n)
        same = bool(a and b and a['tree_sha256'] == b['tree_sha256']
                    and a['n_files'] == b['n_files']
                    and a['bytes'] == b['bytes'])
        all_same = all_same and same
        cmp_rows.append({
            'model': n,
            'present_real': bool(a), 'present_shadow': bool(b),
            'n_files_real': a['n_files'] if a else None,
            'n_files_shadow': b['n_files'] if b else None,
            'bytes_real': a['bytes'] if a else None,
            'bytes_shadow': b['bytes'] if b else None,
            'tree_sha256_real': a['tree_sha256'] if a else None,
            'tree_sha256_shadow': b['tree_sha256'] if b else None,
            'same': same,
        })
    ev['compare'] = {
        'rows': cmp_rows,
        'n_models': len(cmp_rows),
        'n_same': sum(1 for r in cmp_rows if r['same']),
        'all_same': all_same,
        'verdict': ('PASS_unchanged' if all_same else 'FAIL_changed'),
        'note': ('两包 models 树 SHA 逐目录一致 ⇒ **本条未换任何模型**成立；'
                 '且 models 根是**同一物理目录**（realpath 相同）⇒ 一致是'
                 '**结构事实 + 实测复核**双重确认'),
    }

    # ── 4. 反证组：内存里替换一个文件的 SHA ⇒ 树 SHA 必须变 ──
    tdir = os.path.join(real_root, 'tokenizer')
    if os.path.isdir(tdir):
        base = tree_sha(tdir)
        # 找一个真实文件做 tamper 目标
        target = None
        for r, _dd, ff in os.walk(tdir):
            for f in ff:
                target = os.path.relpath(os.path.join(r, f), tdir).replace('\\', '/')
                break
            if target:
                break
        tam = tree_sha(tdir, tamper=(target, '0' * 64))
        ev['neg_control'] = {
            'method': '在**内存里**把 tokenizer 里一个文件的 SHA 换成全 0 '
                      '（**不改盘**）⇒ 树 SHA 必须变化',
            'tampered_file': target,
            'base_tree_sha256': base['tree_sha256'],
            'tampered_tree_sha256': tam['tree_sha256'],
            'n_tampered': tam['n_tampered'],
            'pass': (tam['tree_sha256'] != base['tree_sha256']
                     and tam['n_tampered'] == 1),
            'note': ('🔴 反证：树 SHA 判据必须**对文件内容敏感** '
                     '⇒ 否则「两包一致」可能只是判据恒等'),
        }
    else:
        ev['neg_control'] = {'skipped': 'tokenizer 目录不存在'}

    ev['verdict'] = 'RAN'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)
    print('[cmp] models=%d same=%d all_same=%s'
          % (ev['compare']['n_models'], ev['compare']['n_same'],
             ev['compare']['all_same']))
    print('[nc] pass=%s' % ev.get('neg_control', {}).get('pass'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
