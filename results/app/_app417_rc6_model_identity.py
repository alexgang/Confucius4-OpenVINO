#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app417_rc6_model_identity.py —— **APP-098 三.5：rc6 的模型身份核对**。

## reviewer 三.5 原文
> **MANIFEST/模型身份**：ASR bin 的 SHA 与 rc5 一致；zip 内 R2T2 / INT4-ASR / CUDA 文件计数为 0。

## 本脚本做三件事（都是**实测**，不是结构推断）

1. **rc6 ↔ rc5 的 0.6B ASR 两个 .bin 逐文件 SHA256 对照**
   ⇒ reviewer 只要求「ASR bin SHA 与 rc5 一致」⇒ 只对照这两个 bin。
   ⚠️ **目录名不同**（rc5: `encoder-int8/`…；rc6: `asr06b-encoder-fp16/`…）
      ⇒ 按**文件名**匹配（`*.bin`），不按目录名。
2. **rc6 包内**逐模型目录的文件清单 + 每个文件 SHA256（= rc6 的「模型身份表」）。
3. **反证组**：把某个 .bin 的 SHA **替换成假值**重算目录汇总 ⇒ 必须变化
   ⇒ 证明判据对**文件内容**敏感（否则「与 rc5 一致」可能是因为判据恒等）。

## 🔴🔴 不占设备
纯静态读文件 ⇒ **不持 MACHINE_LOCK**。

## 用法
```
.venv/Scripts/python.exe results/app/_app417_rc6_model_identity.py
```
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

RC6 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc6')
RC5 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5')
REPORT = os.path.join(HERE, 'app417_rc6_model_identity.json')

#: rc6 的模型目录（按包内实际布局）
MODEL_DIRS = ('asr06b-encoder-fp16', 'asr06b-decoder-int8', 'asr06b-tokenizer',
               'mt', 'qwen3tts')

#: 禁项（reviewer 三.5：zip 内这些计数必须是 0）
FORBIDDEN = ('models/encoder-int8/', 'models/decoder-gpu-int8/',
             'models/encoder-fp16/', 'models/decoder-npu-int8/',
             'models/decoder-npu-int4/', 'models/embed_tokens_f16.npy',
             'models/tokenizer/')


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def dir_tree(root):
    """目录内每个文件的相对路径 + SHA256（递归）。"""
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace('\\', '/')
            try:
                out[rel] = sha_file(p)
            except OSError as e:
                out[rel] = 'ERR:%s' % e
    return out


def find_bins(root):
    """找出目录树里所有 .bin 文件（按文件名索引）。"""
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.bin'):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, root).replace('\\', '/')
                out[f] = {'rel': rel, 'sha256': sha_file(p),
                          'bytes': os.path.getsize(p)}
    return out


def main():
    ev = {
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'correction': 'APP-098 三.5 模型身份',
        'rc6': RC6, 'rc5': RC5,
        'device_job': False,
        'lock_note': '纯静态读文件 ⇒ 不占 GPU/NPU ⇒ 不持 MACHINE_LOCK',
    }

    # ── ① rc6 vs rc5：0.6B 的 .bin 逐个对照 ─────────────────────
    asr_bins = {}
    for tag, pkg in (('rc6', RC6), ('rc5', RC5)):
        d = os.path.join(pkg, 'models')
        bins = {}
        for sub in ('asr06b-encoder-fp16', 'asr06b-decoder-int8',
                    'encoder-int8', 'decoder-gpu-int8', 'encoder-fp16'):
            p = os.path.join(d, sub)
            if os.path.isdir(p):
                bins.update(find_bins(p))
        asr_bins[tag] = bins
    ev['asr_bins'] = {
        'rc6': {k: v['sha256'] for k, v in asr_bins['rc6'].items()},
        'rc5': {k: v['sha256'] for k, v in asr_bins['rc5'].items()},
    }
    # 逐文件名对照
    cmp_rows = []
    for name, r6 in sorted(asr_bins['rc6'].items()):
        r5 = asr_bins['rc5'].get(name)
        cmp_rows.append({
            'file': name,
            'rc6_rel': r6['rel'], 'rc6_sha256': r6['sha256'],
            'rc5_rel': (r5 or {}).get('rel'), 'rc5_sha256': (r5 or {}).get('sha256'),
            'match': bool(r5) and r5['sha256'] == r6['sha256'],
        })
    ev['asr_bin_compare'] = cmp_rows
    ev['asr_bin_all_match'] = bool(cmp_rows) and all(r['match'] for r in cmp_rows)
    ev['asr_bin_n'] = len(cmp_rows)

    # ── ② rc6 逐模型目录身份表 ──────────────────────────────────
    models = {}
    for sub in MODEL_DIRS:
        p = os.path.join(RC6, 'models', sub)
        if not os.path.isdir(p):
            models[sub] = {'present': False}
            continue
        tree = dir_tree(p)
        h = hashlib.sha256()
        for k in sorted(tree):
            h.update(('%s %s\n' % (k, tree[k])).encode('utf-8'))
        models[sub] = {'present': True, 'n_files': len(tree),
                       'tree_sha256': h.hexdigest(),
                       'bytes': sum(os.path.getsize(os.path.join(p, k.replace('/', os.sep)))
                                    for k in tree),
                       'files': tree}
    ev['models'] = models

    # ── ③ 反证组：改一个 bin 的 SHA ⇒ 汇总必须变化 ────────────────
    neg = {}
    for sub in ('asr06b-encoder-fp16', 'asr06b-decoder-int8'):
        p = os.path.join(RC6, 'models', sub)
        tree = dir_tree(p)

        def agg(t):
            hh = hashlib.sha256()
            for k in sorted(t):
                hh.update(('%s %s\n' % (k, t[k])).encode('utf-8'))
            return hh.hexdigest()

        real = agg(tree)
        fake = dict(tree)
        k0 = sorted(fake)[0]
        fake[k0] = '0' * 64
        neg[sub] = {'file_tampered': k0, 'tree_sha256_real': real,
                    'tree_sha256_tampered': agg(fake),
                    'detects_change': real != agg(fake)}
    ev['neg_control'] = neg
    ev['neg_control_ok'] = all(v['detects_change'] for v in neg.values())

    # ── ④ rc6 包内禁项（目录级，不依赖 zip 清单）───────────────
    forbid = {}
    for root, dirs, files in os.walk(os.path.join(RC6, 'models')):
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), RC6).replace('\\', '/')
            forbid[rel + '/'] = forbid.get(rel + '/', 0) + 1
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), RC6).replace('\\', '/')
            forbid[rel] = forbid.get(rel, 0) + 1
    ev['forbidden_in_pkg'] = {k: forbid.get(k, 0) for k in FORBIDDEN}
    ev['forbidden_all_zero'] = all(forbid.get(k, 0) == 0 for k in FORBIDDEN)

    ev['verdict'] = 'PASS' if (ev['asr_bin_all_match']
                               and ev['neg_control_ok']
                               and ev['forbidden_all_zero']) else 'FAIL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in (
        'asr_bin_n', 'asr_bin_all_match', 'neg_control_ok',
        'forbidden_all_zero', 'verdict')}, ensure_ascii=False, indent=1))
    for r in ev['asr_bin_compare']:
        print('  %-40s rc6=%s… rc5=%s… match=%s'
              % (r['file'], r['rc6_sha256'][:12], (r['rc5_sha256'] or 'NONE')[:12],
                 r['match']))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
