#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_pkg_translator_fixes.py — 对**客户包内那份** `translator.py` 验证 MT §56 三处修复。

🔴 **纪律**：
- **不 import 被测模块**（`import translator` ⇒ 连带 numpy/OpenBLAS ⇒ 别的模块占满内存时
  进程在 import 阶段就 abort，连 try/except 都接不住）⇒ 用 `ast` 抽源码 + `exec`
  到独立命名空间；
- **不跑推理、不跑测速、不占 GPU/NPU**（纯 CPU，只测纯逻辑）；
- 质量判定交 reviewer（MiniMax 回转写），本脚本**不判质量**。

## 判据（对包内那份文件逐项验证）

| # | 判据 | 期望 |
|---|---|---|
| 1 | `CACHE_MAX` == 4000（不是 400） | ✅ |
| 2 | `submit()` 里重复句**保留显示单元**（不再 `continue` 掉） | ✅ |
| 3 | `flush()` 里重复句**保留显示单元** | ✅ |
| 4 | `load_mt_tokenizer()` 存在且传 `fix_mistral_regex=False` | ✅ |
| 5 | `HunyuanTranslator.__init__` 调用 `load_mt_tokenizer` | ✅ |
| 6 | **行为级**：驱动真实 `submit()`/`flush()` ⇒ 复读句产生**两个**显示单元、翻译入队**只一次** | ✅ |
| 7 | **行为级**：重复句的 `src` 文本**完整保留**（守恒） | ✅ |
| 8 | 幂等：重复调用 `submit()` 同一句两次 ⇒ units=2、queue=1 | ✅ |

## 用法
    python results/app/test_pkg_translator_fixes.py [--pkg <客户包 app 目录>]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import textwrap
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'


def discover_pkg_app() -> str:
    root = r'C:\Users\Trekker-PTL'
    best, best_key = None, None
    for name in os.listdir(root):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        app = os.path.join(root, name, 'app')
        if not os.path.isdir(app):
            continue
        ver = name.rsplit('_v', 1)[-1]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best_key, best = key, app
    if best is None:
        raise SystemExit('[客户包] 未找到 Confucius4_LiveCaption_vX.Y/app')
    return best


def load_service(path: str):
    """从源码里抽出纯逻辑部分并 exec（不 import 被测模块）。

    抽出的部分：模块级纯函数（`norm_key` / `split_sentences` / `ends_sentence` /
    `MAX_SEG_WORDS`）+ `_Job` 类 + `TranslationService` 里**不引用 numpy/torch/ov**
    的方法（`__init__` / `submit` / `flush` / `mt_of_seg` / `mt_units` / `carry`）。
    """
    src = open(path, 'r', encoding='utf-8', newline='').read().replace('\r\n', '\n')
    tree = ast.parse(src)
    lines = src.split('\n')

    # ── 模块级纯函数 + 常量 ──
    # ⚠️ 顶层函数的**定义顺序**要保留（`_first_existing` 在 `DEFAULT_MODEL` 之前）
    #    ⇒ 严格按源码顺序收集。
    top_funcs = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue          # 模块 docstring（不是代码）
        if isinstance(node, ast.FunctionDef):
            # 排除重依赖函数（会 import numpy/torch/ov）
            seg = '\n'.join(lines[node.lineno - 1:node.end_lineno])
            if any(k in seg for k in ('np.', 'numpy', 'torch', 'og.', 'ov.')):
                continue
            top_funcs.append(seg)
        elif isinstance(node, ast.Assign):
            # ⚠️ **所有**模块级常量都要带上（`_SENT_END` / `_MT_CANDIDATES` /
            #    `MODELS` / `_HY_ROOT` …）⇒ 否则纯函数在运行时 NameError。
            #    只排除含重依赖表达式的（numpy/torch/ov）。
            seg = '\n'.join(lines[node.lineno - 1:node.end_lineno])
            if any(k in seg for k in ('np.', 'numpy', 'torch', 'og.', 'ov.')):
                continue
            top_funcs.append(seg)
        elif isinstance(node, ast.ClassDef) and node.name == '_Job':
            top_funcs.append('\n'.join(lines[node.lineno - 1:node.end_lineno]))

    # ── TranslationService 的目标方法（按源码文本过滤 numpy/torch/ov 引用）──
    WANT = ('__init__', 'submit', 'flush', 'mt_of_seg', 'mt_units', 'carry')
    svc_methods = []
    class_attrs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'TranslationService':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in WANT:
                    seg = '\n'.join(lines[sub.lineno - 1:sub.end_lineno])
                    if any(k in seg for k in ('np.', 'numpy', 'torch', 'og.', 'ov.')):
                        continue
                    svc_methods.append(seg)
                elif isinstance(sub, ast.Assign):
                    # 类属性（如 `CACHE_MAX = 4000`）必须带上
                    class_attrs.append('\n'.join(lines[sub.lineno - 1:sub.end_lineno]))
            break

    # ⚠️ 必须**重建类定义**（方法体在类里是缩进的 ⇒ 单独 exec 会 IndentationError）
    #    ⇒ 把类头 + 类属性 + 目标方法重新拼成一个类源码。
    cls_src = ['class TranslationService:']
    for a in class_attrs:
        cls_src.append(textwrap.indent(a, '    '))
    for m in svc_methods:
        cls_src.append(textwrap.indent(m, '    '))
    cls_body = '\n\n'.join(cls_src)

    body = ('import os\nimport re\nimport json\nimport time\nimport queue\nimport threading\n'
            'from collections import OrderedDict\n'
            f'__file__ = {path!r}\n\n'
            + textwrap.dedent('\n\n'.join(top_funcs)) + '\n\n\n' + cls_body)
    ns = {}
    exec(compile(body, path, 'exec'), ns)
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包 app 目录（默认自动发现）')
    ap.add_argument('--report', default=os.path.join(
        REPO, 'results', 'app', 'pkg_translator_fixes_test.json'))
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg_app()
    tpath = os.path.join(pkg, 'translator.py')
    print(f'被测文件（客户包内）: {tpath}')
    print(f'  SHA256: {hashlib.sha256(open(tpath, "rb").read()).hexdigest()}')
    print(f'  字节  : {os.path.getsize(tpath)}')
    print()

    ns = load_service(tpath)
    results = []

    def check(name, ok, detail=''):
        results.append(dict(name=name, pass_=bool(ok), detail=detail))
        print(f'[{"PASS" if ok else "FAIL"}] {name}' + (f' — {detail}' if detail else ''))

    TS = ns['TranslationService']

    # ── ① CACHE_MAX ───────────────────────────────────────────────────
    check('① CACHE_MAX == 4000（不是 400）',
          TS.CACHE_MAX == 4000, f'CACHE_MAX={TS.CACHE_MAX}')

    # ── ②③④ submit/flush 的重复句处理（行为级）────────────────────────
    import queue as _q
    import threading as _th
    from collections import OrderedDict

    svc = TS.__new__(TS)
    svc.active = True
    svc.q = _q.Queue()
    svc.lock = _th.Lock()
    svc.done = OrderedDict()
    svc.done_fix = OrderedDict()
    svc.units = []
    svc.outbox = []
    svc._seen = set()
    svc._pend = ''
    svc._half = None
    svc.seg_keys = {}
    svc.seg_carry = {}
    svc.seg_half = {}
    svc.draft = ''
    svc._last_src = ''
    svc.state = 'ready'

    SENT = 'The final word.'   # 带句末标点 ⇒ 会被当成完整句
    svc.submit(SENT, seg=0)
    svc.submit(SENT, seg=1)    # 同一句，第二次出现（ASR 复读）
    check('② submit() 复读句产生两个显示单元（不再丢弃）',
          len(svc.units) == 2, f'units={len(svc.units)}')
    check('②b 复读句翻译入队只一次（不增调用）',
          svc.q.qsize() == 1, f'queue={svc.q.qsize()}')
    check('②c 两段各自登记了自己的 key',
          svc.seg_keys.get(0) and svc.seg_keys.get(1),
          f'seg_keys={ {k: v for k, v in svc.seg_keys.items()} }')
    check('③ 复读句的 src 完整保留（守恒）',
          all(u['src'] == SENT for u in svc.units) and len(svc.units) == 2,
          f'srcs={[u["src"] for u in svc.units]}')

    # flush() 的收尾句也要保留显示单元
    svc2 = TS.__new__(TS)
    svc2.active = True
    svc2.q = _q.Queue()
    svc2.lock = _th.Lock()
    svc2.done = OrderedDict()
    svc2.done_fix = OrderedDict()
    svc2.units = []
    svc2.outbox = []
    svc2._seen = set()
    svc2._pend = 'A trailing half sentence'
    svc2._half = None
    svc2.seg_keys = {}
    svc2.seg_carry = {}
    svc2.seg_half = {}
    svc2.draft = ''
    svc2._last_src = ''
    svc2.state = 'ready'
    svc2.submit('A trailing half sentence', seg=0)   # 先让它进 _pend（无句末标点）
    n_before = len(svc2.units)
    svc2.flush(seg=0)
    check('③b flush() 收尾句进显示单元',
          len(svc2.units) == n_before + 1,
          f'units {n_before} -> {len(svc2.units)}')

    # flush() 重复句：先 submit 再 flush 同一句
    svc3 = TS.__new__(TS)
    svc3.active = True
    svc3.q = _q.Queue()
    svc3.lock = _th.Lock()
    svc3.done = OrderedDict()
    svc3.done_fix = OrderedDict()
    svc3.units = []
    svc3.outbox = []
    svc3._seen = set()
    svc3._pend = ''
    svc3._half = None
    svc3.seg_keys = {}
    svc3.seg_carry = {}
    svc3.seg_half = {}
    svc3.draft = ''
    svc3._last_src = ''
    svc3.state = 'ready'
    svc3.submit('Done already.', seg=0)
    n3 = len(svc3.units)
    svc3._pend = 'Done already.'      # 收尾时又出现同一句
    svc3.flush(seg=1)
    check('③c flush() 复读句保留显示单元（不丢弃）',
          len(svc3.units) == n3 + 1,
          f'units {n3} -> {len(svc3.units)}')

    # ── ④⑤ load_mt_tokenizer ─────────────────────────────────────────
    src_text = open(tpath, 'r', encoding='utf-8', newline='').read().replace('\r\n', '\n')
    check('④ load_mt_tokenizer() 存在', 'load_mt_tokenizer' in ns)
    check('④b load_mt_tokenizer 传 fix_mistral_regex=False',
          'fix_mistral_regex=False' in src_text)
    check('⑤ HunyuanTranslator.__init__ 调用 load_mt_tokenizer',
          'self.tok = load_mt_tokenizer(' in src_text)

    # ── ⑥ 幂等：再调一次 submit 同一句，units 只 +1、queue 不增 ─────────
    n_units = len(svc.units)
    n_queue = svc.q.qsize()
    svc.submit(SENT, seg=2)
    check('⑥ 幂等：重复 submit 同一句 ⇒ units 只 +1、翻译入队不增',
          len(svc.units) == n_units + 1 and svc.q.qsize() == n_queue,
          f'units {n_units}->{len(svc.units)}, queue {n_queue}->{svc.q.qsize()}')

    # ── ⑦ 守恒：3 次出现 ⇒ 3 个单元、原文总字数不变 ──────────────────
    total_src = sum(len(u['src']) for u in svc.units)
    check('⑦ 守恒：3 次出现的原文总字数 == 3 × 单句字数',
          total_src == 3 * len(SENT), f'total_src={total_src}')

    n_pass = sum(1 for r in results if r['pass_'])
    n_fail = len(results) - n_pass
    print()
    print(f'==== {n_pass}/{len(results)} PASS' + (f'，{n_fail} FAIL' if n_fail else '') + ' ====')

    report = dict(
        pkg=pkg, target=tpath,
        target_sha256=hashlib.sha256(open(tpath, 'rb').read()).hexdigest(),
        target_bytes=os.path.getsize(tpath),
        target_mtime=os.path.getmtime(tpath),
        mtime=time.strftime('%Y-%m-%d %H:%M:%S'),
        total=len(results), n_pass=n_pass, n_fail=n_fail,
        all_pass=(n_fail == 0), checks=results,
    )
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'报告已写: {args.report}')
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
