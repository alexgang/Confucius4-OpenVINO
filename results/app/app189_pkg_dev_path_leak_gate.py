#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app189_pkg_dev_path_leak_gate.py —— 「客户包内**代码**泄漏开发机绝对路径」闸门。

背景（§119 之后本轮实测，2026-11-01）
------------------------------------
`app187`（§118）覆盖「STATUS 引用的产物是否入库」；
`app188`（§119）覆盖「客户包 `app/` 与仓库 `live_caption/` 的**模块集合**是否一致」；
`app049`（§48）覆盖「**仓库里**的代码有没有写死**客户包名**」。

🔴🔴🔴 **三者都不覆盖这一维**：**客户包 `app/` 里那些**真正会被客户机执行**的生产模块，
其**代码内容**里有没有写死**开发机家目录**（`C:\Users\Trekker-PTL\...`）。

🔴🔴🔴 **本轮实测抓到的真实案例**（交付 zip `Confucius4_LiveCaption_v1.13.zip`
内 `app/*.py` 共 31 个，其中 **6 个**的**代码行**里写着开发机家目录）：

| 文件 | 行 | 内容 | 客户机后果 |
|---|---|---|---|
| `speaker_assets.py` | L116 | `DEV_ASR_SCRIPTS = r'C:\Users\Trekker-PTL\qwen3asr_06b\scripts'` | 🟡 回退路径（仅研发机有）⇒ 客户机走不到，但**泄漏本机用户名** |
| `speaker_tracker.py` | L59 | `_ASR_SCRIPTS = r'C:\Users\Trekker-PTL\qwen3asr_06b\scripts'` | 🟡 同上 |
| `tts_cuda.py` | L30 | `os.environ.get('LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')` | 🔴 **默认指向开发机 venv** ⇒ 客户机必须自己设 `LIVECAP_CUDA_PY`，否则 CUDA 路径**必然不可用** |
| `tts_engine.py` | L321 | `r'C:\Users\Trekker-PTL\qwen3tts_eval\qwen3tts_patch.py'` | 🟡 回退候选（包内 `tts_engine_patch.py` 优先） |
| `tts_worker.py` | L1413 / L1473 | `r'C:\Users\Trekker-PTL\confucius4-tts'` | 🟡 OV 路径回退候选 |
| `_probe_tts_cuda.py` | L20 | `REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"` | 🟡 **已被 `pkg_exclude` 排除出 zip** ⇒ 交付 zip 内无此文件（包目录里有） |

⇒ 🔴 **这在「客户机形态」下是真实缺陷**，不只是卫生问题：
`tts_cuda.py` 的 `ENV_PY` **默认值就是开发机路径** ⇒ 客户机上
`available()` 恒 `False`（`os.path.isfile(ENV_PY)` 为假）
⇒ **CUDA TTS 在客户机上必然不可用**，除非用户自己设环境变量。
⇒ 修复方向：**默认值改为「按包内相对位置推导」或「留空 + 明确报错」**。

🔴 **判据设计（必须能识破已知有缺陷的旧产物 ⇒ §四纪律）**
---------------------------------------------------------
* **P1 开发机家目录泄漏（🔴 阻断）**：包 `app/` 下的**生产模块**（非开发专用）
  的**代码行**里出现 `C:\Users\<开发机用户名>\...` ⇒ 阻断。
* **P2 开发专用文件（🟡 提醒，不阻断）**：命中但文件被 `pkg_exclude` 判为开发专用
  ⇒ 不进 zip ⇒ 不阻断。
* **P3 仓库侧同口径清点（⬜ 不判负）**：仓库 `live_caption/` 里的同类命中
  ⇒ 绝大多数是**一次性诊断脚本** ⇒ 只列清单，不阻断。

🔴🔴🔴 **「代码行」的判定必须用 AST，不能用正则** ——
否则**注释与 docstring**里提到的路径会被误判（`app049` 的 §86 已经踩过这个坑：
docstring 在 AST 里是 `Expr(Constant(str))` **两层**，外层 `ast.Expr` **不是** `Constant`
⇒ 单纯 `continue` 掉 `ast.Constant` **挡不住** docstring）。
⇒ 本脚本照抄 `app049.code_lines_with_pkg_name()` 的**已修正**实现：
   **显式跳过「裸字符串表达式」**（`ast.Expr` 且其 value 是字符串常量）。

用法
----
    python results/app/app189_pkg_dev_path_leak_gate.py
    python results/app/app189_pkg_dev_path_leak_gate.py --json <out.json>
    python results/app/app189_pkg_dev_path_leak_gate.py --selftest
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **开发机家目录的绝对路径前缀**（Windows 原生 + 正斜杠两种写法都要覆盖）
DEV_HOME_RE = re.compile(r'[A-Za-z]:[\\/]Users[\\/][^\\/\'"\s]+[\\/]', re.IGNORECASE)

#: 🔴 **兜底正则必须与 `pkg_exclude.APP_DEV_ONLY_FILE_RE` 逐字一致**（同 `app188` 的理由）
_DEV_ONLY_RE_FALLBACK = re.compile(r'^_[A-Za-z0-9_]+\.(py|ps1|bat|sh)$', re.I)


def _load_pkg_exclude(repo_root):
    """加载 `pkg_exclude.py`（开发专用文件的**权威判定**）。

    🔴 **不 import 被测模块**（§四纪律）⇒ 这里 import 的是**规则表**。
    """
    path = os.path.join(repo_root, 'pkg_exclude.py')
    if not os.path.isfile(path):
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_app189_pkg_exclude', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _pkg_app_dir(repo_root):
    """客户包 `app/` 目录（**不写死版本号** ⇒ 自动发现最大版本）。"""
    try:
        sys.path.insert(0, repo_root)
        import pkg_paths
        app = pkg_paths.pkg_app_dir()
        if app and os.path.isdir(app):
            return app
    except Exception:
        pass
    root = r'C:\Users\Trekker-PTL'
    prefix = 'Confucius4_LiveCaption_v'
    best = None
    best_key = None
    if os.path.isdir(root):
        for name in os.listdir(root):
            if not name.startswith(prefix):
                continue
            app = os.path.join(root, name, 'app')
            if not os.path.isdir(app):
                continue
            try:
                key = tuple(int(x) for x in name[len(prefix):].split('.'))
            except ValueError:
                continue
            if best_key is None or key > best_key:
                best_key = key
                best = app
    return best


def _is_dev_only(name, pkg_exclude):
    """判断包目录里的某个 `.py` 是否**开发专用**（不进 zip）。"""
    if pkg_exclude is not None:
        try:
            return bool(pkg_exclude.is_app_dev_only('app/' + name))
        except Exception:
            pass
    return bool(_DEV_ONLY_RE_FALLBACK.match(name))


def code_lines_with_dev_home(path):
    """返回该文件里**代码行**中出现「开发机家目录绝对路径」的地方。

    🔴 用 `ast` 判定「哪些行属于代码」⇒ 自动跳过注释与文档字符串。
    （与 `app049.code_lines_with_pkg_name()` 同源实现，已含 §86 的修正。）
    """
    try:
        src = open(path, 'r', encoding='utf-8', errors='replace').read()
    except OSError:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # 语法错误 ⇒ 退回文本扫描（保守：整文件都当代码行）
        hits = []
        for i, ln in enumerate(src.split('\n'), 1):
            if DEV_HOME_RE.search(ln) and not ln.strip().startswith('#'):
                hits.append({'line': i, 'text': ln.strip()[:200]})
        return hits

    code_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            continue                          # 字符串字面量（作为值使用时）
        if isinstance(node, ast.Expr):
            v = getattr(node, 'value', None)
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                continue                      # 🔴🔴 裸字符串表达式 = docstring ⇒ 不算代码
        lineno = getattr(node, 'lineno', None)
        if lineno is None:
            continue
        end = getattr(node, 'end_lineno', None) or lineno
        for n in range(lineno, end + 1):
            code_lines.add(n)

    hits = []
    for i, ln in enumerate(src.split('\n'), 1):
        if i not in code_lines:
            continue
        s = ln.strip()
        if s.startswith('#'):
            continue
        if DEV_HOME_RE.search(ln):
            hits.append({'line': i, 'text': s[:200]})
    return hits


def collect(pkg_app, repo_live, pkg_exclude):
    """收集「代码行里的开发机家目录路径」命中。"""
    leaked = []          # 🔴 阻断：包内**生产**模块
    dev_only = []        # 🟡 提醒：包内开发专用文件
    repo_hits = []       # ⬜ 不判负：仓库侧存量

    if pkg_app and os.path.isdir(pkg_app):
        for name in sorted(os.listdir(pkg_app)):
            if not name.endswith('.py'):
                continue
            hits = code_lines_with_dev_home(os.path.join(pkg_app, name))
            if not hits:
                continue
            rec = {'file': name, 'n_hits': len(hits), 'hits': hits}
            if _is_dev_only(name, pkg_exclude):
                dev_only.append(rec)
            else:
                leaked.append(rec)

    if repo_live and os.path.isdir(repo_live):
        for name in sorted(os.listdir(repo_live)):
            if not name.endswith('.py'):
                continue
            hits = code_lines_with_dev_home(os.path.join(repo_live, name))
            if hits:
                repo_hits.append({'file': name, 'n_hits': len(hits), 'hits': hits})

    return {
        'leaked': leaked,
        'dev_only': dev_only,
        'repo_hits': repo_hits,
        'n_leaked': len(leaked),
        'n_leaked_lines': sum(r['n_hits'] for r in leaked),
        'n_dev_only': len(dev_only),
        'n_repo_hit_files': len(repo_hits),
        'n_repo_hit_lines': sum(r['n_hits'] for r in repo_hits),
    }


def _selftest():
    """🔴🔴🔴 **鉴别力实测**（§四纪律）。

    在**临时副本**里构造 5 个已知状态 ⇒ 期望各自的判据结论。
    ⚠️ 注入组必须建在**干净基线**上（§118 的教训：建在原产物上会混入真缺陷）。
    """
    tmp = tempfile.mkdtemp(prefix='app189_selftest_')
    try:
        pkg_app = os.path.join(tmp, 'pkg', 'app')
        repo_live = os.path.join(tmp, 'repo', 'live_caption')
        os.makedirs(pkg_app)
        os.makedirs(repo_live)

        def w(d, n, c='x = 1\n'):
            with open(os.path.join(d, n), 'w', encoding='utf-8') as f:
                f.write(c)

        # ---- 干净基线：两个干净文件 ----
        w(pkg_app, 'clean.py')
        w(repo_live, 'clean.py')

        r0 = collect(pkg_app, repo_live, None)
        ok = []
        ok.append(('T0 干净基线无泄漏',
                   r0['n_leaked'] == 0 and r0['n_dev_only'] == 0))

        # ---- T1：docstring / 注释里的路径**不得**判成泄漏 ----
        w(pkg_app, 'doc.py',
          'r"""\n示例：C:\\Users\\SomeOne\\foo\n"""\n'
          '# 注释：C:\\Users\\SomeOne\\bar\n'
          'VALUE = 1\n')
        r1 = collect(pkg_app, repo_live, None)
        ok.append(('T1 docstring/注释里的路径不判泄漏',
                   'doc.py' not in [x['file'] for x in r1['leaked']]
                   and 'doc.py' not in [x['file'] for x in r1['dev_only']]))

        # ---- T2：代码行里的开发机路径 ⇒ 必须进 leaked ----
        w(pkg_app, 'leak.py',
          'P = r"C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts"\n')
        r2 = collect(pkg_app, repo_live, None)
        ok.append(('T2 代码行里的开发机路径 ⇒ leaked',
                   [x['file'] for x in r2['leaked']] == ['leak.py']))

        # ---- T3：开发专用文件（`_` 前缀）⇒ 只进 dev_only，不进 leaked ----
        w(pkg_app, '_probe.py',
          'REPO = r"C:\\Users\\Trekker-PTL\\confucius4-openvino"\n')
        r3 = collect(pkg_app, repo_live, None)
        ok.append(('T3 开发专用文件 ⇒ 只进 dev_only',
                   [x['file'] for x in r3['leaked']] == ['leak.py']
                   and [x['file'] for x in r3['dev_only']] == ['_probe.py']))

        # ---- T4：正斜杠写法也要抓到 ----
        w(pkg_app, 'slash.py',
          'P = "C:/Users/Trekker-PTL/somewhere"\n')
        r4 = collect(pkg_app, repo_live, None)
        ok.append(('T4 正斜杠写法也能抓到',
                   'slash.py' in [x['file'] for x in r4['leaked']]))

        # ---- T5：兜底正则必须与**真实** `pkg_exclude` 一致 ----
        pe = _load_pkg_exclude(REPO)
        if pe is None:
            ok.append(('T5 兜底规则与 pkg_exclude 一致', False))
        else:
            pat = getattr(pe, 'APP_DEV_ONLY_FILE_RE', None)
            same = (pat is not None
                    and pat.pattern == _DEV_ONLY_RE_FALLBACK.pattern
                    and bool(pat.flags & re.IGNORECASE)
                    == bool(_DEV_ONLY_RE_FALLBACK.flags & re.IGNORECASE))
            ok.append(('T5 兜底规则与 pkg_exclude 一致', same))

        n_pass = sum(1 for _, v in ok if v)
        n_fail = len(ok) - n_pass

        print('== app189 鉴别力自检 ==')
        for name, v in ok:
            print('  [%s] %s' % ('PASS' if v else 'FAIL', name))
        print('  结论: %s（PASS %d / FAIL %d）'
              % ('PASS' if n_fail == 0 else 'FAIL', n_pass, n_fail))
        return 0 if n_fail == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(
        description='客户包内代码泄漏开发机绝对路径闸门')
    ap.add_argument('--json', default=None, help='证据落盘路径')
    ap.add_argument('--selftest', action='store_true', help='只跑鉴别力自检')
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    pkg_exclude = _load_pkg_exclude(REPO)
    pkg_app = _pkg_app_dir(REPO)
    repo_live = os.path.join(REPO, 'live_caption')

    res = collect(pkg_app, repo_live, pkg_exclude)

    n_fail = res['n_leaked']
    res['n_fail'] = n_fail
    res['n_pass'] = 1 if n_fail == 0 else 0
    res['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    res['pkg_app'] = pkg_app
    res['repo_live'] = repo_live
    res['pkg_exclude_loaded'] = pkg_exclude is not None
    res['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    res['script'] = os.path.basename(__file__)
    res['purpose'] = ('§119 之后的第三维：客户包 app/ 内**生产模块的代码内容**里'
                       '不得写死开发机家目录绝对路径 ⇒ 否则客户机上'
                       '相关路径必然不可用（如 tts_cuda.ENV_PY 默认指向开发机 venv）')

    print('== 客户包内代码「开发机绝对路径」泄漏闸门 ==')
    print('  包 app/ 目录 : %s' % pkg_app)
    print('  仓库 live_caption : %s' % repo_live)
    print('  pkg_exclude 已加载 : %s' % res['pkg_exclude_loaded'])
    print('  🔴 包内生产模块泄漏 : %d 个文件 / %d 行'
          % (res['n_leaked'], res['n_leaked_lines']))
    for r in res['leaked']:
        print('    LEAK  %s（%d 行）' % (r['file'], r['n_hits']))
        for h in r['hits']:
            print('        L%d: %s' % (h['line'], h['text']))
    print('  (🟡 开发专用文件，已被排除出 zip ⇒ 不阻断): %d' % res['n_dev_only'])
    for r in res['dev_only']:
        print('    DEV-ONLY  %s（%d 行）' % (r['file'], r['n_hits']))
    print('  (⬜ 仓库侧存量，只列清单不判负): %d 文件 / %d 行'
          % (res['n_repo_hit_files'], res['n_repo_hit_lines']))
    print('  结论: %s（PASS %d / FAIL %d）'
          % (res['verdict'], res['n_pass'], res['n_fail']))

    if args.json:
        outp = args.json if os.path.isabs(args.json) else os.path.join(REPO, args.json)
        d = os.path.dirname(outp)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(outp, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print('  证据已落盘: %s' % outp)

    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
