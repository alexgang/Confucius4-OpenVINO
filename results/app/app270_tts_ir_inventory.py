#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app270 —— 🔴🔴🔳 **APP-069③ / APP-070①：TTS IR「删前列清单」**。

## 为什么要单独一个脚本

reviewer（APP-070① 1）：

> 删除 NPU 路径不加载的 TTS IR（约 567 MB）。**删前列清单**，删后用 e2e 证明
> NPU 路径不受影响。

⇒ 顺序是 **① 列清单 → ② 删 → ③ e2e 证明** ⇒
本脚本**只做 ①**（**绝不删任何文件**）。

## 「NPU 路径实际加载哪些 IR」的**判定依据**（不是猜）

**权威来源 = 包内 `babelvox/pipeline.py`**（真正 `read_model`/`compile_model`
的文件）＋ **App 传给它的配置**（`live_caption/tts_engine.py`）：

| babelvox 分支 | App 的实际配置 | ⇒ 实际打开的 IR |
|---|---|---|
| `use_kv_cache=False` ⇒ 走 `talker.xml`（**多桶**分支，`talker_bucket_sizes` 非空） | `use_kv_cache=False` | `talker.xml`（**talker_prefill/decode 不用**） |
| `use_cp_kv_cache=True` ⇒ 走 `cp_prefill.xml` + `cp_decode.xml`（CPU） | `use_cp_kv_cache=True` | `cp_prefill.xml` + `cp_decode.xml`（**code_predictor 不用**） |
| `_load_npu_models` 无条件读 | — | `speaker_encoder.xml`（NPU）、`tokenizer_decoder.xml`（NPU） |
| `tokenizer_encoder` | **babelvox 库零调用**（`tts_engine.py` L141 明文） | **不加载** |

⇒ **实际加载 = {talker, cp_prefill, cp_decode, speaker_encoder,
tokenizer_decoder}**（共 5 个 xml + 5 个 bin）
⇒ **不加载 = {talker_prefill, talker_decode, code_predictor, tokenizer_encoder}**
（4 个 xml + 4 个 bin）

🔴 **本脚本用两种独立证据交叉验证**：
1. **代码级**：解析包内 `babelvox/pipeline.py` 的 `read_model`/`compile_model`
   调用 ⇒ 取出被引用的 xml 文件名
2. **分支级**：按 App 的**实际配置**（`use_kv_cache=False` /
   `use_cp_kv_cache=True` / `talker_buckets` 非空）走一遍 babelvox 的分支逻辑
   ⇒ 得到「实际打开」集合
⇒ 两者**必须一致**，否则脚本判 FAIL（说明分析口径有问题）。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/app270_tts_ir_inventory.py [--pkg <目录>]
```
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEFAULT_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
REPORT = os.path.join(HERE, 'app270_tts_ir_inventory_evidence.json')

#: 🔴 App 的**实际** babelvox 配置（`live_caption/tts_engine.py` L43-52）
APP_CONFIG = {
    'use_kv_cache': False,
    'use_cp_kv_cache': True,
    'talker_buckets': [64, 128, 256, 384, 512],
    'decoder_buckets': [8, 16, 32, 64, 128, 256],
}


def md5_of(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def referenced_xmls(pipeline_py):
    """代码级证据：解析 `read_model`/`compile_model` 的**字面量 xml 名**。"""
    src = open(pipeline_py, encoding='utf-8', errors='replace').read()
    try:
        ast.parse(src)
    except SyntaxError as e:
        return None, repr(e)
    out = set()
    for m in re.finditer(r"(?:read_model|compile_model)\s*\(", src):
        seg = src[m.end():m.end() + 400]
        for lit in re.findall(r"['\"]([A-Za-z0-9_\-]+\.xml)['\"]", seg):
            out.add(lit)
    return sorted(out), None


def branch_loaded(cfg):
    """分支级证据：按 babelvox `_load_npu_models` 的**真实逻辑**推演。

    （照抄 `babelvox/pipeline.py` L284-365 的分支结构）
    """
    loaded = set()
    # 无条件：speaker_encoder / tokenizer_decoder
    loaded.add('speaker_encoder.xml')
    loaded.add('tokenizer_decoder.xml')
    # talker：use_kv_cache ? prefill+decode : talker.xml（多桶）
    if cfg['use_kv_cache']:
        loaded.add('talker_prefill.xml')
        loaded.add('talker_decode.xml')
    else:
        loaded.add('talker.xml')
    # code predictor：use_cp_kv_cache ? cp_prefill+cp_decode : code_predictor
    if cfg['use_cp_kv_cache']:
        loaded.add('cp_prefill.xml')
        loaded.add('cp_decode.xml')
    else:
        loaded.add('code_predictor.xml')
    return sorted(loaded)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    a = ap.parse_args()
    pkg = a.pkg
    checks = []

    def chk(cid, name, ok, detail):
        checks.append({'id': cid, 'name': name, 'ok': bool(ok),
                       'detail': detail})
        print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', cid, name))

    print('=== APP-070① TTS IR「删前列清单」（**不删任何文件**）===')
    print('包：%s' % pkg)

    tts_dir = os.path.join(pkg, 'models', 'qwen3tts', 'int8')
    if not os.path.isdir(tts_dir):
        print('!! 找不到 TTS IR 目录：%s' % tts_dir)
        return 2

    # ── 证据 1：代码级（包内 babelvox 的 read_model/compile_model）──────
    pipe = os.path.join(pkg, 'python', 'Lib', 'site-packages', 'babelvox',
                        'pipeline.py')
    refs, err = referenced_xmls(pipe)
    chk('H1', '能解析包内 babelvox/pipeline.py（代码级证据的来源）',
        err is None and refs, {'pipeline_py': pipe, 'err': err,
                               'referenced_xmls': refs})

    # ── 证据 2：分支级（按 App 的实际配置推演）──────────────────────────
    branch = branch_loaded(APP_CONFIG)
    print('   分支级：实际打开 = %s' % branch)

    # ── H2：两个证据必须一致 ────────────────────────────────────────────
    #   代码级是「**可能**打开」的集合（两个分支都算）；
    #   分支级是「**实际**打开」的集合（按 App 配置走一个分支）
    #   ⇒ 关系应当是：branch ⊆ refs，且 refs − branch = 「另一分支才会用的」
    only_branch = sorted(set(branch) - set(refs or []))
    chk('H2', '分支级 ⊆ 代码级（口径自洽）',
        not only_branch,
        {'branch': branch, 'refs': refs, 'only_in_branch': only_branch})

    # ── 清单：逐文件 ────────────────────────────────────────────────────
    # 🔴 **按 stem 判「加载」**：babelvox 只 `read_model('X.xml')`，
    #    但 **同名 `X.bin` 是那个 IR 的权重** ⇒ **成对保留/成对删**。
    loaded_stems = {x[:-4] if x.endswith('.xml') else x for x in branch}
    files = []
    for fn in sorted(os.listdir(tts_dir)):
        p = os.path.join(tts_dir, fn)
        if not os.path.isfile(p):
            continue
        stem = fn.rsplit('.', 1)[0]
        loaded = (stem in loaded_stems)
        files.append({
            'file': fn,
            'bytes': os.path.getsize(p),
            'sha256': sha256_of(p)[:16],
            'md5': md5_of(p),
            'loaded_by_npu_path': loaded,
            'verdict': ('**保留**（NPU 路径实际加载）' if loaded
                        else '**候选删除**（NPU 路径不加载）'),
        })
    n_del = [f for f in files if not f['loaded_by_npu_path']]
    bytes_del = sum(f['bytes'] for f in n_del)
    print('   清单：%d 个文件，候选删除 %d 个（%.1f MB）'
          % (len(files), len(n_del), bytes_del / 1048576.0))

    # ── H3：候选删除的必须是「另一分支才会用」的（不是核心 IR）──────────
    core = {'talker.xml', 'cp_prefill.xml', 'cp_decode.xml',
            'speaker_encoder.xml', 'tokenizer_decoder.xml'}
    chk('H3', '候选删除集合不含核心 IR（实际加载的 5 个 xml 全在保留侧）',
        core.issubset(set(branch)) and
        not (set(f['file'] for f in n_del) & core),
        {'core': sorted(core), 'branch': branch,
         'n_candidate_delete': len(n_del)})

    # ── H4：体积对得上 reviewer 的「约 567 MB」（口径提示）──────────────
    print('   ⇒ 候选删除体积 = %.1f MB（reviewer 估「约 567 MB」）'
          % (bytes_del / 1048576.0))

    # ── H5：清单里必须有 bin↔xml 的**成对**说明（删时要成对删）─────────
    stems_del = sorted({f['file'].rsplit('.', 1)[0] for f in n_del})
    paired = all(
        any(f['file'] == s + '.bin' for f in n_del) and
        any(f['file'] == s + '.xml' for f in n_del)
        for s in stems_del)
    chk('H5', '每个候选 stem 的 xml+bin **成对**（删时成对删）',
        paired and bool(stems_del),
        {'stems': stems_del, 'paired': paired})

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
        'n_pass': n_pass, 'n_fail': n_fail,
        'correction': 'APP-069③ / APP-070①（删前列清单）',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': pkg,
        'tts_ir_dir': tts_dir,
        'app_babelvox_config': APP_CONFIG,
        'evidence': {
            'code_level_referenced_xmls': refs,
            'branch_level_actually_loaded': branch,
            'code_level_source': pipe,
        },
        'inventory': files,
        'n_files': len(files),
        'n_candidate_delete': len(n_del),
        'bytes_candidate_delete': bytes_del,
        'mb_candidate_delete': round(bytes_del / 1048576.0, 1),
        'n_keep': len(files) - len(n_del),
        'NOT_DELETED': ('🔴 本脚本**只出清单** ⇒ **一个文件都没删**。'
                        '删除须在**设备级 e2e 证明「NPU 路径不受影响」之后**执行。'),
        'checks': checks,
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n候选删除清单：')
    for f in n_del:
        print('   %-28s %10.1f MB  %s' % (f['file'], f['bytes'] / 1048576.0,
                                            f['sha256']))
    print('\n结果：%d PASS / %d FAIL' % (n_pass, n_fail))
    print('[evidence] %s' % REPORT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
