#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 §3.1 + APP-131：**在包内 python / 包内 EXT 上**跑离线一致性测试。

- `tests/test_ext0419_bgkeep.py`（reviewer 口径：**14/14**）
- `tests/ext0419_bg_harness.js`（reviewer 口径：**18/18**）
- `tests/test_ext0420_clone_gender.py`（**APP-131** 追加，reviewer 口径：**12/12**）

## 为什么 python 侧要做两处**最小适配**（其余逐字不动）

包内 EXT 的布局与源码仓不同：

| | 源码仓 `live_dub_ext/` | 包内 `<包根>/ext/` |
|---|---|---|
| 模块 | `ext/bridge.py`（**模块**） | `ext/bridge/bridge.py`（**包** `ext.bridge` 里的模块） |

⇒ ① 测试里的 `ROOT` 改成**可由环境变量指定**（`EXT_TEST_ROOT`）
   ⇒ 这样测试文件**不用放进包里**（包内不留测试产物）。
⇒ ② `from ext import bridge as Bm` 在包内解析到**包** `ext.bridge`
   （`__init__.py` 只有 docstring ⇒ 没有 `PipelineSession`）
   ⇒ 加 3 行兜底：若取到的对象没有 `PipelineSession`，
   就改用 `from ext.bridge import bridge as Bm`（同一个模块，只是多一层包）。

🔴 **测试逻辑一行未改**；适配只在 import / ROOT 两处，且**逐行记录**在证据里。

## 用法

    python results/app/_app129_run_pkg_tests.py --pkg <包根>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
SRC_EXT = os.path.join(HOME, 'live_dub_ext')
RESULTS = os.path.join(REPO, 'results', 'app')

#: 🔴🔴 **测试文件也必须按 commit 取**（不是工作树）——与
#:   `_app129_build_v26.py` 的成包口径**同一条纪律**：
#:   2026-11-24 12:3x 实测：`live_dub_ext` 工作树的
#:   `tests/test_ext0420_clone_gender.py` 已被 reviewer 加到 **v0.4.21 在制品**
#:   （多出「4. split at gender changes」一节 ⇒ 用到 `CV.split_by_gender`
#:   ⇒ 而本包按 APP-131 装的是 **4740b06（v0.4.20）** ⇒ 该属性不存在
#:   ⇒ **AttributeError ⇒ rc=1**（假 FAIL：不是包缺陷，是测试取错了版本）。
#:   ⇒ 一律 `git show <commit>:<path>` 取**被测的那个版本**的测试。
EXT_COMMIT = '4740b06'


def git_show(relpath):
    """按 EXT_COMMIT 取文件内容（不是工作树）。"""
    p = subprocess.run(['git', '-C', SRC_EXT, 'show',
                        '%s:%s' % (EXT_COMMIT, relpath)],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('git show %s:%s 失败：%s'
                           % (EXT_COMMIT, relpath,
                              (p.stderr or b'').decode('utf-8', 'replace')[-300:]))
    return p.stdout.decode('utf-8')


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, 'app129_pkg_tests.log'), 'a',
                  encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def adapt_py_test(src_text: str):
    """把源码仓的测试适配成「可在包内布局下跑」的版本。返回 (新文本, 适配说明)。"""
    notes = []
    out = src_text

    old_root = ("ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))")
    new_root = ("ROOT = (os.environ.get('EXT_TEST_ROOT')\n"
                "        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))")
    if out.count(old_root) != 1:
        raise SystemExit('FAIL: ROOT 行命中 %d 次（要求 1 次）' % out.count(old_root))
    out = out.replace(old_root, new_root, 1)
    notes.append('ROOT ← EXT_TEST_ROOT 环境变量')

    # 🔴 包内布局适配：包里 EXT 是**包** `ext/bridge/`（源码仓是模块 `ext/bridge.py`）
    #   ⇒ 把 `sys.modules['ext']` 指向 `ext.bridge` 这个包
    #   ⇒ 源码仓的 `from ext import bridge / spk_engine / config / …`
    #     在包内**原样可用**（`ext.bridge` 的 `__path__` 就是 `ext/bridge/`）
    #   ⇒ **测试正文一行不改**，只多了这一段适配。
    old_imp = 'sys.path.insert(0, ROOT)'
    new_imp = (
        'sys.path.insert(0, ROOT)\n'
        '# 🔴 包内布局适配（打包侧加，测试正文未改）：\n'
        '#   源码仓 `ext/bridge.py` 是**模块**；包内 `ext/bridge/` 是**包**\n'
        '#   ⇒ 把 `sys.modules["ext"]` 指向 `ext.bridge`\n'
        '#   ⇒ `from ext import bridge / spk_engine / config / …` 原样可用。\n'
        'import importlib as _il, sys as _sys\n'
        'try:\n'
        '    _pkg = _il.import_module("ext.bridge")\n'
        'except Exception:\n'
        '    _pkg = None\n'
        'if _pkg is not None and not hasattr(_pkg, "PipelineSession"):\n'
        '    _sys.modules["ext"] = _pkg')
    if out.count(old_imp) != 1:
        raise SystemExit('FAIL: sys.path 行命中 %d 次（要求 1 次）' % out.count(old_imp))
    out = out.replace(old_imp, new_imp, 1)
    notes.append('sys.modules["ext"] ← ext.bridge（包内布局）')

    return out, notes


def count_checks(text: str):
    """数一下测试里有多少个 check(...)（14/14 的分母）。"""
    return len(re.findall(r'^\s*check\(', text, re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True, help='包根目录')
    args = ap.parse_args()
    pkg = args.pkg
    pkg_py = os.path.join(pkg, 'python', 'python.exe')
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': pkg, 'pkg_python': pkg_py, 'results': {}}

    if not os.path.isfile(pkg_py):
        log('FAIL: 包内 python 不存在：%s' % pkg_py)
        return 2
    log('包内 python：%s' % pkg_py)

    tmp = tempfile.mkdtemp(prefix='app129_pkg_tests_')
    try:
        # ── ① python 侧 ────────────────────────────────────────────
        src_py = 'tests/test_ext0419_bgkeep.py'
        text = git_show(src_py)
        adapted, notes = adapt_py_test(text)
        tmp_py = os.path.join(tmp, 'test_ext0419_bgkeep.py')
        with open(tmp_py, 'w', encoding='utf-8', newline='\n') as f:
            f.write(adapted)
        log('① 适配 %d 处：%s' % (len(notes), '；'.join(notes)))
        log('   测试源码 check() 条数：%d' % count_checks(text))

        env = dict(os.environ)
        env['EXT_TEST_ROOT'] = pkg
        env['PYTHONPATH'] = pkg
        env['PYTHONIOENCODING'] = 'utf-8'
        p = subprocess.run([pkg_py, tmp_py], capture_output=True, text=True,
                           timeout=600, cwd=tmp, env=env)
        out = (p.stdout or '') + (p.stderr or '')
        with open(os.path.join(RESULTS, 'app129_pkg_test_py.log'), 'w',
                  encoding='utf-8') as f:
            f.write(out)
        n_pass = out.count('[PASS]')
        n_fail = out.count('[FAIL]')
        log('① python 侧：PASS=%d FAIL=%d rc=%d' % (n_pass, n_fail, p.returncode))
        print(out[-4000:])
        rep['results']['python'] = {
            'src': src_py, 'adaptations': notes,
            'n_check_in_src': count_checks(text),
            'n_pass': n_pass, 'n_fail': n_fail, 'rc': p.returncode,
            'ok': (n_fail == 0 and n_pass > 0 and p.returncode == 0),
            'log': 'results/app/app129_pkg_test_py.log',
        }

        # ── ② node 侧 ──────────────────────────────────────────────
        harness_rel = 'tests/ext0419_bg_harness.js'
        harness = os.path.join(tmp, 'ext0419_bg_harness.js')
        with open(harness, 'w', encoding='utf-8', newline='\n') as f:
            f.write(git_show(harness_rel))
        player = os.path.join(pkg, 'ext', 'extension', 'player.js')
        log('② node 侧：harness=%s  player=%s' % (harness, player))
        try:
            node_v = subprocess.run(['node', '--version'], capture_output=True,
                                    text=True, timeout=60).stdout.strip()
        except Exception as e:
            node_v = 'NOT FOUND (%r)' % (e,)
        log('   node 版本：%s' % node_v)
        p2 = subprocess.run(['node', harness, player], capture_output=True,
                            text=True, timeout=600, cwd=SRC_EXT)
        out2 = (p2.stdout or '') + (p2.stderr or '')
        with open(os.path.join(RESULTS, 'app129_pkg_test_node.log'), 'w',
                  encoding='utf-8') as f:
            f.write(out2)
        # node harness 的收尾行形如 `18/18 PASS`
        m = re.findall(r'(\d+)\s*/\s*(\d+)\s+(PASS|FAIL)', out2)
        if m:
            tot_pass = int(m[-1][0])
            den = int(m[-1][1])
            tot_fail = 0 if m[-1][2] == 'PASS' else (den - tot_pass)
        else:
            tot_pass = out2.count('[PASS]')
            tot_fail = out2.count('[FAIL]')
            den = tot_pass + tot_fail
        n_check_lines = out2.count('[PASS]') + out2.count('[FAIL]')
        log('② node 侧：PASS=%d FAIL=%d（明细行 %d）rc=%d'
            % (tot_pass, tot_fail, n_check_lines, p2.returncode))
        print(out2[-4000:])
        rep['results']['node'] = {
            'harness': harness, 'player_js': player, 'node_version': node_v,
            'n_pass': tot_pass, 'n_fail': tot_fail, 'denominator': den,
            'n_check_lines': n_check_lines, 'rc': p2.returncode,
            'ok': (tot_fail == 0 and tot_pass > 0 and p2.returncode == 0),
            'log': 'results/app/app129_pkg_test_node.log',
        }

        # ── ③ python 侧（APP-131 追加）：clone 音色性别守门 ─────────
        #   reviewer APP-131 明文：「验收第 1 项再加
        #   `python tests/test_ext0420_clone_gender.py`（应 **12/12**）」
        src_py2 = 'tests/test_ext0420_clone_gender.py'
        log('③ APP-131 侧：%s@%s' % (src_py2, EXT_COMMIT))
        try:
            text2 = git_show(src_py2)
            adapted2, notes2 = adapt_py_test(text2)
            tmp_py2 = os.path.join(tmp, 'test_ext0420_clone_gender.py')
            with open(tmp_py2, 'w', encoding='utf-8', newline='\n') as f:
                f.write(adapted2)
            log('   适配 %d 处：%s' % (len(notes2), '；'.join(notes2)))
            log('   测试源码 check() 条数：%d' % count_checks(text2))
            p3 = subprocess.run([pkg_py, tmp_py2], capture_output=True, text=True,
                                timeout=600, cwd=tmp, env=env)
            out3 = (p3.stdout or '') + (p3.stderr or '')
            with open(os.path.join(RESULTS, 'app129_pkg_test_py2.log'), 'w',
                      encoding='utf-8') as f:
                f.write(out3)
            n_pass3 = out3.count('[PASS]')
            n_fail3 = out3.count('[FAIL]')
            log('③ python 侧（0420）：PASS=%d FAIL=%d rc=%d'
                % (n_pass3, n_fail3, p3.returncode))
            print(out3[-4000:])
            # 🔴 0420 的 `check()` 有 **5 处在 for 循环里** ⇒ 源码 call site 8 个
            #   ⇒ 运行时实际 **12** 个断言（reviewer 口径 12/12）
            #   ⇒ 分母取**运行时 PASS+FAIL**，不取源码 call site 数。
            den3 = n_pass3 + n_fail3
            rep['results']['python_clone_gender'] = {
                'src': src_py2, 'adaptations': notes2,
                'n_check_call_sites_in_src': count_checks(text2),
                'n_check_runtime': den3,
                'n_pass': n_pass3, 'n_fail': n_fail3, 'rc': p3.returncode,
                'ok': (n_fail3 == 0 and n_pass3 > 0 and p3.returncode == 0
                       and den3 == 12),
                'required_by': 'APP-131',
                'expected': '12/12',
                'log': 'results/app/app129_pkg_test_py2.log',
            }
        except Exception as e:
            log('③ APP-131 侧失败：%r' % (e,))
            rep['results']['python_clone_gender'] = {
                'src': src_py2, 'ok': False, 'error': repr(e),
                'required_by': 'APP-131',
            }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    outp = os.path.join(RESULTS, 'app129_pkg_tests_evidence.json')
    with open(outp, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % outp)
    allok = all(v.get('ok') for v in rep['results'].values())
    log('总结：%s' % ('ALL PASS' if allok else 'FAIL'))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
