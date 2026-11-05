#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app254 — **AST 导入闭包**分析：算出一个包到底需要**哪些本地模块**。

## 为什么（🔴 本轮实测的真缺陷）
MiniMVP `v1.0-rc1` **打不开**：
> `ModuleNotFoundError: No module named 'segment_encoder_backend'`

而上一轮的构建闸门 G1「导入冒烟 17/17 ✅」**是假 PASS** ——
因为 `from segment_encoder_backend import ...` 写在**类的 `__init__` 里**
⇒ **模块级 import 不会执行** ⇒ 冒烟测试根本碰不到它。

⇒ 修法：**不靠运行、靠 AST** 把每个模块里的
`import X` / `from X import ...`（**含函数内、类内、try 内的**）全抓出来
⇒ 算���**闭包** ⇒ 与包里实际有的模块对账。

## 输出
* 缺失的模块（**必须补**）
* 引用了但包里没有、且**不在闭包里**的（说明是可选/被裁掉的）
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEV = os.path.join(REPO, 'live_caption')

STDLIB_OK = {
    'os', 'sys', 're', 'json', 'time', 'math', 'io', 'shutil', 'hashlib',
    'subprocess', 'threading', 'queue', 'queue as q', 'tempfile', 'glob',
    'wave', 'struct', 'array', 'collections', 'collections as c',
    'itertools', 'functools', 'dataclasses', 'typing', 'enum', 'abc',
    'logging', 'traceback', 'copy', 'random', 'statistics', 'pickle',
    'csv', 'textwrap', 'unicodedata', 'warnings', 'contextlib', 'uuid',
    'socket', 'selectors', 'http', 'urllib', 'xml', 'html', 'base64',
    'zlib', 'gzip', 'bz2', 'lzma', 'platform', 'ctypes', 'importlib',
    'multiprocessing', 'concurrent', 'asyncio', 'signal', 'errno', 'glob',
    'fnmatch', 'codecs', 'locale', 'gettext', 'calendar', 'datetime',
    'decimal', 'fractions', 'numbers', 'operator', 'pickle', 'posixpath',
    'ntpath', 'genericpath', 'shlex', 'ssl', 'ipaddress', 'weakref',
    'types', 'inspect', 'ast', 'tokenize', 'keyword', 'heapq', 'bisect',
    'array', 'binascii', 'codecs', 'sqlite3', 'secrets', 'string',
    'difflib', 'filecmp', 'pprint', 'reprlib', 'sysconfig', 'site',
}

#: 🔴 明确**不属于**本地模块闭包的前缀/名字（第三方库 ⇒ 包内 site-packages 提供）
THIRD_PARTY_PREFIX = ('numpy', 'np', 'soundcard', 'sounddevice', 'scipy',
                      'torch', 'torchaudio', 'soundfile', 'openvino', 'ov',
                      'transformers', 'tokenizers', 'huggingface_hub', 'hf',
                      'PIL', 'tkinter', 'tk', 'ctypes', 'winsound',
                      'sentencepiece', 'librosa', 'soundfile', 'requests',
                      'aiohttp', 'httpx', 'yaml', 'regex', 'tqdm', 'packaging',
                      'setuptools', 'pip', 'pkg_resources', 'six', 'dateutil',
                      'jinja2', 'filelock', 'psutil', 'numpy_typing')


def local_imports(path):
    """抓一个文件里的**全部** import（含函数内/类内/try 内）⇒ 模块名列表。"""
    src = open(path, 'r', encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.append((a.name.split('.')[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:      # 相对 import ⇒ 本地
                if node.module:
                    mods.append((node.module.split('.')[0], node.lineno))
                continue
            if node.module:
                mods.append((node.module.split('.')[0], node.lineno))
    return mods


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', default=DEV)
    ap.add_argument('--pkg', default=os.path.join(
        HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc1'))
    ap.add_argument('--out', default=os.path.join(
        HERE, 'app254_minimvp_import_closure_evidence.json'))
    args = ap.parse_args()

    dev_files = {fn[:-3]: os.path.join(args.dev, fn)
                 for fn in os.listdir(args.dev) if fn.endswith('.py')}
    pkg_dir = os.path.join(args.pkg, 'app')
    pkg_files = {}
    if os.path.isdir(pkg_dir):
        pkg_files = {fn[:-3]: os.path.join(pkg_dir, fn)
                     for fn in os.listdir(pkg_dir) if fn.endswith('.py')}

    out = {'script': 'app254_minimvp_import_closure.py',
           'dev': args.dev, 'pkg': args.pkg,
           'n_dev_modules': len(dev_files), 'n_pkg_modules': len(pkg_files)}

    def closure(seed):
        """从种子模块出发，算**本地模块**闭包。"""
        seen, stack, edges = set(), list(seed), []
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            p = dev_files.get(name)
            if not p:
                continue
            seen.add(name)
            for m, ln in local_imports(p):
                edges.append({'from': name, 'imports': m, 'line': ln})
                if m in dev_files and m not in seen:
                    stack.append(m)
        return seen, edges

    # ① 从包里**已有**的模块出发 ⇒ 闭包里**缺**的（必须补）
    seed = sorted(pkg_files.keys())
    closure_pkg, edges_pkg = closure(seed)
    missing = sorted(m for m in closure_pkg if m not in pkg_files)
    out['pkg_seed_modules'] = seed
    out['closure_of_pkg_seed'] = sorted(closure_pkg)
    out['missing_from_pkg'] = missing
    out['n_missing'] = len(missing)

    # ② 引用了但既不在包里、也不在闭包里的（说明是**被裁掉的可选**模块）
    referenced = sorted({e['imports'] for e in edges_pkg})
    not_local = [m for m in referenced
                 if m not in dev_files and m not in STDLIB_OK
                 and not m.startswith(THIRD_PARTY_PREFIX)]
    out['referenced_not_local'] = not_local

    # ③ 完整闭包（从 live_caption_app.py 起）⇒ 应该带哪些
    full, edges_full = closure(['live_caption_app.py'])
    out['full_closure_from_app'] = sorted(full)
    out['full_closure_missing_in_pkg'] = sorted(
        m for m in full if m not in pkg_files)

    # ④ 逐条证据（缺失模块被谁引用、在第几行）
    ev = []
    for e in edges_pkg:
        if e['imports'] in missing:
            ev.append(e)
    out['missing_evidence'] = ev

    print('开发树模块 %d 个 / 包内 %d 个' % (len(dev_files), len(pkg_files)))
    print('\n包内已有模块的**导入闭包**缺 %d 个：%s'
          % (len(missing), missing))
    for e in ev:
        print('  %-26s → %-26s (第 %d 行)' % (e['from'], e['imports'], e['line']))
    print('\n完整闭包（从 live_caption_app.py 起）= %d 个：%s'
          % (len(full), sorted(full)))
    print('其中包内缺：%s' % out['full_closure_missing_in_pkg'])
    print('\n引用了但既不在开发树也不是标准库/第三方：%s' % not_local)

    out['verdict'] = 'PASS' if not missing else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nverdict =', out['verdict'])
    print('[evidence] %s' % args.out)
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
