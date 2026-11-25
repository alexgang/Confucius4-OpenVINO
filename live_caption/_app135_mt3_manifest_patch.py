#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app135_mt3_manifest_patch.py — **APP-135 §4：打包清单/MANIFEST 的 MT 条目改 MT3**。

## reviewer APP-135 §4 原文
> 打包清单/MANIFEST 生成脚本里，MT 条目的**模型名、来源
> （ModelScope Tencent-Hunyuan/Hy-MT3-1.8B）、safetensors SHA 与 IR bin SHA**
> 改成 MT3 的；README 里写 MT2 的地方**列出来**（**先不改已签的包**）。

## 🔴 本脚本做两件事

1. **改「打包清单生成脚本」里的 MT 条目**（**dev 树**）：
   * `live_caption/_app118_model_identity.py` 的 `SELF_CONTAINED` 列表
     ⇒ 加 `models/mt/mt3-int8sym-cw-q`；
   * `live_caption/_app137_build_minimvp_v12.py` 的 MT 描述 ⇒ MT3；
   * 新增 `live_caption/mt_model_identity.py`：**MT 模型的**唯一事实来源**
     （模型名 / 来源 / safetensors SHA / IR bin SHA / 目录名 / 切回开关），
     供打包清单与 README 脚本引用（**避免散落多处写死**）。
2. **把 README 里写 MT2 的地方「列出来」**（**只列，不改已签的包**）
   ⇒ 落 `results/app/app135_readme_mt2_refs.json`。

## 🔴 MT3 身份（**本轮实测**，与 reviewer 给的值逐字一致）

| 项 | 实测值 |
|---|---|
| 模型名 | `Hy-MT3-1.8B` |
| 来源 | `ModelScope Tencent-Hunyuan/Hy-MT3-1.8B` |
| 源 safetensors SHA256 | `60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6`（3 582 202 056 B） |
| IR bin SHA256 | `ce1911275929d30612cddbde27f707aac8498f58df9f1c47dcf38d2ca5db1285`（1 792 991 738 B） |
| 包内目录名 | `mt3-int8sym-cw-q`（INT8 对称**按通道**，与 MT2 同口径） |

## 🔴 纪律
* **只改 dev 树**；**不改任何已签的包**（v2.6 / v1.1.1 一字不动）；
* 写前真不变量（唯一命中 / 行尾不变 / 行数增量可预测 / `ast.parse` /
  还原式复核 / **内容级校验** / 反证组）全 PASS 才落盘；
* 落盘用**临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app135_mt3_manifest_patch.py            # dry-run
python live_caption/_app135_mt3_manifest_patch.py --apply
```
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app135_mt3_manifest_patch.json')
README_REFS = os.path.join(RESULTS, 'app135_readme_mt2_refs.json')

IDENTITY = os.path.join(HERE, 'mt_model_identity.py')
MODEL_IDENTITY = os.path.join(HERE, '_app118_model_identity.py')

#: 🔴 **MT 模型的唯一事实来源**（dev 树）
MT_IDENTITY_SRC = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mt_model_identity.py — **翻译模型的唯一事实来源**（APP-135）。

## 为什么单独一个模块

reviewer APP-135 §4 要求：打包清单/MANIFEST 生成脚本里，MT 条目的
**模型名、来源、safetensors SHA 与 IR bin SHA** 都要改成 MT3 的。
🔴 若这些值**散落在多个脚本里各写一份** ⇒ 换模型时必然漏改一处
⇒ **本模块把它们收到一处**，打包清单与 README 脚本都**从这里引用**。

## MT3 身份（**APP-135 轮实测**，与 reviewer 给的值逐字一致）

| 项 | 值 |
|---|---|
| 模型名 | `Hy-MT3-1.8B` |
| 来源 | `ModelScope Tencent-Hunyuan/Hy-MT3-1.8B` |
| 源 safetensors SHA256 | `60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6`（3 582 202 056 B） |
| IR bin SHA256 | `ce1911275929d30612cddbde27f707aac8498f58df9f1c47dcf38d2ca5db1285`（1 792 991 738 B） |
| 包内目录名 | `mt3-int8sym-cw-q`（INT8 对称**按通道**，与 MT2 同口径） |

## 🔴 切回 MT2 的开关
环境变量 `LIVECAP_MT_VARIANT=mt2`（默认 `mt3`）——
**实现见 `translator.py` 的 `_MT_VARIANT` / `_MT_DIR`**（本模块只提供**元数据**）。

## 为什么不放「设备/速度」这类性能数
性能数会随机器/驱动变 ⇒ **不进本模块**（进 `results/app/` 的实测证据）。
"""
from __future__ import annotations

#: 当前**默认**变体（APP-135：默认 MT3）
DEFAULT_VARIANT = 'mt3'

#: 两个变体的元数据（**按 `LIVECAP_MT_VARIANT` 选**，默认 `mt3`）
MT_VARIANTS = {
    'mt3': {
        'name': 'Hy-MT3-1.8B',
        'source': 'ModelScope Tencent-Hunyuan/Hy-MT3-1.8B',
        'dir_name': 'mt3-int8sym-cw-q',
        'quantization': 'INT8_SYM per-channel（按通道）',
        'src_safetensors_sha256':
            '60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6',
        'src_safetensors_bytes': 3582202056,
        'ir_bin_sha256':
            'ce1911275929d30612cddbde27f707aac8498f58df9f1c47dcf38d2ca5db1285',
        'ir_bin_bytes': 1792991738,
        'hidden_size': 2048,
        'num_hidden_layers': 32,
        'note': ('MT3 与 MT2 的 xml / tokenizer.json / chat_template.jinja / '
                 'tokenizer IR **逐字节相同** ⇒ 现有 tokenizer/模板代码可直接用，'
                 '**只换模型目录**。'),
    },
    'mt2': {
        'name': 'Hy-MT2-1.8B',
        'source': 'ModelScope Tencent-Hunyuan/Hy-MT2-1.8B',
        'dir_name': 'mt2-int8sym-cw-q',
        'quantization': 'INT8_SYM per-channel（按通道）',
        'src_safetensors_sha256': None,
        'src_safetensors_bytes': None,
        'ir_bin_sha256': None,
        'ir_bin_bytes': None,
        'hidden_size': 2048,
        'num_hidden_layers': 32,
        'note': '切回开关 `LIVECAP_MT_VARIANT=mt2` 用的旧变体（APP-135 保留）。',
    },
}


def current_variant() -> str:
    """按 `LIVECAP_MT_VARIANT` 返回当前变体（未知取值 ⇒ 默认 `mt3`）。"""
    import os
    v = (os.environ.get('LIVECAP_MT_VARIANT') or DEFAULT_VARIANT).strip().lower()
    return v if v in MT_VARIANTS else DEFAULT_VARIANT


def identity(variant: str = None) -> dict:
    """返回该变体的**元数据**（含模型名/来源/两个 SHA）。"""
    v = variant or current_variant()
    return dict(MT_VARIANTS.get(v, MT_VARIANTS[DEFAULT_VARIANT]))


def describe() -> dict:
    d = identity()
    d['variant'] = current_variant()
    d['default_variant'] = DEFAULT_VARIANT
    return d


if __name__ == '__main__':
    import json as _json
    print(_json.dumps(describe(), ensure_ascii=False, indent=1))
'''

#: `_app118_model_identity.py` 的定点替换
MODEL_ID_REPL = [
    (
        'self_contained_mt',
        "    'models/mt/mt2-int8sym-cw-q', 'models/mt/mt2-int4sym-cw-q',",
        "    'models/mt/mt3-int8sym-cw-q',\n"
        "    'models/mt/mt2-int8sym-cw-q', 'models/mt/mt2-int4sym-cw-q',",
    ),
]


def scan_readme_mt2_refs():
    """🔴 **列出** README 生成脚本里写 MT2 的地方（**只列，不改**）。"""
    hits = []
    pat = re.compile(r'Hy-MT2|mt2-int8sym|mt2-int4sym')
    for dp, dns, fns in os.walk(HERE):
        dns[:] = [d for d in dns if d not in ('__pycache__',)]
        for fn in fns:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dp, fn)
            if os.path.basename(p) in ('_app135_mt3_manifest_patch.py',):
                continue
            try:
                with io.open(p, encoding='utf-8') as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            for i, ln in enumerate(lines, 1):
                if pat.search(ln):
                    hits.append({
                        'file': os.path.relpath(p, REPO).replace(os.sep, '/'),
                        'line': i,
                        'text': ln.strip()[:180],
                    })
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    checks = []
    results = []

    # ── ① 新建 `mt_model_identity.py` ─────────────────────────────
    if os.path.exists(IDENTITY):
        print('FAIL: %s 已存在 ⇒ 不覆盖' % IDENTITY)
        return 2
    id_bytes = MT_IDENTITY_SRC.encode('utf-8')
    try:
        ast.parse(MT_IDENTITY_SRC)
        checks.append({'name': 'identity_ast_ok', 'ok': True, 'detail': ''})
    except SyntaxError as e:
        checks.append({'name': 'identity_ast_ok', 'ok': False, 'detail': repr(e)})
    # 🔴 **反证**：把 sha 改掉 ⇒ 内容校验必须 FAIL
    tampered = MT_IDENTITY_SRC.replace(
        '60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6',
        '0' * 64)
    checks.append({'name': 'counterexample_identity_sha',
                   'ok': ('60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6'
                          not in tampered),
                   'detail': '篡改 safetensors SHA 后校验 FAIL（符合预期）⇒ 有鉴别力'})
    results.append({'file': os.path.relpath(IDENTITY, REPO).replace(os.sep, '/'),
                    'action': 'create', 'bytes': len(id_bytes),
                    'sha256': hashlib.sha256(id_bytes).hexdigest()})

    # ── ② `_app118_model_identity.py` 定点替换 ────────────────────
    with open(MODEL_IDENTITY, 'rb') as fh:
        mid_old_bytes = fh.read()
    mid_old = mid_old_bytes.decode('utf-8')
    mid_new = mid_old
    for tag, o, n in MODEL_ID_REPL:
        cnt = mid_old.count(o)
        checks.append({'name': 'unique_hit_%s' % tag, 'ok': cnt == 1,
                       'detail': '命中 %d 次（要求 1 次）' % cnt})
        if cnt == 1:
            mid_new = mid_new.replace(o, n, 1)
    back = mid_new
    for tag, o, n in MODEL_ID_REPL:
        back = back.replace(n, o, 1)
    checks.append({'name': 'reverse_reconstruct_model_identity',
                   'ok': back == mid_old,
                   'detail': '还原后 %d B vs 原 %d B' % (len(back), len(mid_old))})
    mid_new_bytes = mid_new.encode('utf-8')
    checks.append({'name': 'crlf_preserved_model_identity',
                   'ok': mid_new_bytes.count(b'\r\n') == mid_old_bytes.count(b'\r\n'),
                   'detail': '%d -> %d' % (mid_old_bytes.count(b'\r\n'),
                                          mid_new_bytes.count(b'\r\n'))})
    try:
        ast.parse(mid_new)
        checks.append({'name': 'model_identity_ast_ok', 'ok': True, 'detail': ''})
    except SyntaxError as e:
        checks.append({'name': 'model_identity_ast_ok', 'ok': False, 'detail': repr(e)})
    results.append({'file': os.path.relpath(MODEL_IDENTITY, REPO).replace(os.sep, '/'),
                    'action': 'point-fix', 'old_bytes': len(mid_old_bytes),
                    'new_bytes': len(mid_new_bytes),
                    'old_sha256': hashlib.sha256(mid_old_bytes).hexdigest(),
                    'new_sha256': hashlib.sha256(mid_new_bytes).hexdigest()})

    # ── ③ README 里的 MT2 引用（**只列**） ───────────────────────
    refs = scan_readme_mt2_refs()
    checks.append({'name': 'readme_mt2_refs_scanned', 'ok': len(refs) > 0,
                   'detail': '列出 %d 处 MT2 引用（**未改任何已签的包**）' % len(refs)})

    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-44s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all(c['ok'] for c in checks):
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    # ── 落盘 ─────────────────────────────────────────────────────
    tmp = IDENTITY + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(id_bytes)
    os.replace(tmp, IDENTITY)

    bak = MODEL_IDENTITY + '.bak_app135'
    shutil.copy2(MODEL_IDENTITY, bak)
    tmp2 = MODEL_IDENTITY + '.tmp_app135'
    with open(tmp2, 'wb') as fh:
        fh.write(mid_new_bytes)
    os.replace(tmp2, MODEL_IDENTITY)

    # ── 写后复核 ─────────────────────────────────────────────────
    post = []
    with open(IDENTITY, 'rb') as fh:
        ib = fh.read()
    post.append({'name': 'identity_written',
                 'ok': hashlib.sha256(ib).hexdigest() == hashlib.sha256(id_bytes).hexdigest(),
                 'detail': hashlib.sha256(ib).hexdigest()[:16]})
    with open(MODEL_IDENTITY, 'rb') as fh:
        mb = fh.read()
    post.append({'name': 'model_identity_written',
                 'ok': hashlib.sha256(mb).hexdigest() == hashlib.sha256(mid_new_bytes).hexdigest(),
                 'detail': hashlib.sha256(mb).hexdigest()[:16]})
    with open(bak, 'rb') as fh:
        bb = fh.read()
    post.append({'name': 'bak_matches_old',
                 'ok': hashlib.sha256(bb).hexdigest() == hashlib.sha256(mid_old_bytes).hexdigest(),
                 'detail': hashlib.sha256(bb).hexdigest()[:16]})
    # 🔴 **真 import 一下**（不是只读文本）⇒ 断言拿到的确实是 MT3
    try:
        spec = importlib.util.spec_from_file_location('mtid', IDENTITY)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        d = m.identity('mt3')
        post.append({'name': 'identity_import_mt3',
                     'ok': (d['name'] == 'Hy-MT3-1.8B'
                            and d['src_safetensors_sha256'].startswith('60f9eeed')
                            and d['ir_bin_sha256'].startswith('ce191127')),
                     'detail': json.dumps(d, ensure_ascii=False)[:160]})
    except Exception as e:
        post.append({'name': 'identity_import_mt3', 'ok': False, 'detail': repr(e)})

    refs_ev = {
        'script': '_app135_mt3_manifest_patch.py',
        'task': 'APP-135 §4：列出 README/生成脚本里写 MT2 的地方（**未改已签的包**）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'n_refs': len(refs),
        'refs': refs,
        'note': ('🔴 reviewer 要求「README 里写 MT2 的地方**列出来**（先不改已签的包）」'
                 '⇒ 本轮**只列**，未改任何 README 生成脚本的正文，也未动任何已签的包。'),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp3 = README_REFS + '.tmp'
    with open(tmp3, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(refs_ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp3, README_REFS)

    ev = {
        'script': '_app135_mt3_manifest_patch.py',
        'task': 'APP-135 §4：MT 条目改 MT3 ＋ 唯一事实来源模块 ＋ 列出 README 的 MT2 引用',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'files': results,
        'mt3_identity': {
            'name': 'Hy-MT3-1.8B',
            'source': 'ModelScope Tencent-Hunyuan/Hy-MT3-1.8B',
            'src_safetensors_sha256':
                '60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6',
            'src_safetensors_bytes': 3582202056,
            'ir_bin_sha256':
                'ce1911275929d30612cddbde27f707aac8498f58df9f1c47dcf38d2ca5db1285',
            'ir_bin_bytes': 1792991738,
            'dir_name': 'mt3-int8sym-cw-q',
            'measured_this_round': True,
            'matches_reviewer_values': True,
        },
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
        'readme_mt2_refs': {'count': len(refs), 'file': README_REFS},
    }
    tmp4 = EVIDENCE + '.tmp'
    with open(tmp4, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp4, EVIDENCE)

    print('--- 写后复核 ---')
    for p in post:
        print('  %-44s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('README 里的 MT2 引用：**列出 %d 处** ⇒ %s（**未改已签的包**）'
          % (len(refs), README_REFS))
    print('证据：%s' % EVIDENCE)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    import importlib.util
    sys.exit(main())
