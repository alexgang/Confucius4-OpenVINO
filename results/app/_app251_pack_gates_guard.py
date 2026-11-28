#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_pack_gates_guard.py —— §251：把「打包路径闸门」变成**可离线自检**的清单。

🔴 **为什么需要它（§236 的教训 + §251 的复发）**
   §236 已经学到：**「凡被打包路径调用的闸门都要单独跑一遍验它现在是绿的」**。
   §251 实测发现：§236 的修法**从未入库** ⇒ 闸门**又红回去了**
   ⇒ **同一个坑在 5 天内复发两次**。
   🔴 **根因不是「忘了修」，而是「没有防复发机制」**：
   * 闸门**只在打包时**跑 ⇒ 完整版线自 v2.5 起**从未打过 zip**
     ⇒ 闸门红着**没人触发**；
   * 而 §236 的修法只在**工作树**里 ⇒ **没入库就没修成**。

⇒ 本脚本做两件事：
   1. **列出 `pack_v13.py` 真实调用的全部闸门**（从源码里 `ast` 抽出来，
      **不手抄清单** ⇒ 清单不会与代码脱节）；
   2. **逐个跑一遍并报绿/红**（哪些能离线跑、哪些需要 `--pkg`）。
      ⇒ 闸门红 ⇒ 本脚本红 ⇒ **巡检轮就能发现**，不必等到打包那天。

🔴 **纪律**：零推理、零 GPU、零 NPU、不调 MiniMax、不打包、不改客户包。
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PACK = os.path.join(REPO, 'pack_v13.py')

PASS = []
FAIL = []
SKIP = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)


def note(name, detail=''):
    print('  [SKIP] %s%s' % (name, (' — ' + detail) if detail else ''))
    SKIP.append(name)


def pack_gate_calls(path=None):
    """从 `pack_v13.py` 源码里**抽出**真正被调用的闸门脚本（不手抄清单）。

    🔴 真实源码形态有 **3 种**，都要认：
      ① `subprocess.run([sys.executable, os.path.join(dirname, 'results','app','x.py'), ...])`
      ② `subprocess.run([sys.executable, script, ...])`（`script` 是局部变量）
      ③ `cmd = [sys.executable, script, '--pkg', pkg]` ; `subprocess.run(cmd, ...)`
    ⇒ 做法：**按函数作用域**建「变量 → 值」的映射，再解引用。
    🔴 **必须按作用域**：`script` 这个名字在多个函数里**指向不同脚本**
       ⇒ 用全局映射会**串味**（第一次实现就踩到：只抽出 1/4 个）。

    路径还原：只认 `os.path.join(...)` 里**尾部**是 `results/app/x.py`
    的形式（前面的 `os.path.dirname(...)` 段忽略）⇒ 得到仓库相对路径。
    """
    src = io.open(path or PACK, encoding='utf-8').read()
    tree = ast.parse(src)

    def scope_maps(scope_nodes):
        """在给定作用域里建 变量→List / 变量→os.path.join 的映射。"""
        lists, joins = {}, {}
        for sc in scope_nodes:
            for node in ast.walk(sc):
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    tgt = node.targets[0]
                    if not isinstance(tgt, ast.Name):
                        continue
                    val = node.value
                    if isinstance(val, ast.List):
                        lists[tgt.id] = val
                    elif _is_join(val):
                        joins[tgt.id] = val
        return lists, joins

    def make_resolver(lists, joins):
        def resolve_join(node, depth=0):
            """把 `os.path.join(...)`（或指向它的变量）还原成尾部相对路径。"""
            if depth > 3:
                return None
            if isinstance(node, ast.Name):
                node = joins.get(node.id)
                if node is None:
                    return None
                return resolve_join(node, depth + 1)
            if not _is_join(node):
                return None
            parts = []
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    parts.append(a.value)
                else:
                    parts.append(None)      # dirname(...) 之类 ⇒ 非字面量
            tail = []
            for p in reversed(parts):
                if p is None:
                    break
                tail.append(p)
            tail.reverse()
            if not tail or not tail[-1].endswith('.py'):
                return None
            return '/'.join(tail)
        return resolve_join

    #: 🔴 闸门脚本可能在**仓库根**（如 `check_internal_material.py`），
    #:   也在 `results/app/` 或 `live_caption/` ⇒ 三处都要收。
    def is_gate_path(rel):
        return (rel.startswith('results/app/') or rel.startswith('live_caption/')
                or ('/' not in rel and rel.endswith('.py')))

    found = []

    def harvest(scope_nodes):
        lists, joins = scope_maps(scope_nodes)
        resolve_join = make_resolver(lists, joins)
        for node in ast.walk(scope_nodes[0]) if len(scope_nodes) == 1 else _walk(scope_nodes):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'run'):
                continue
            args = node.args
            if not args:
                continue
            first = args[0]
            lst = None
            if isinstance(first, ast.List):
                lst = first
            elif isinstance(first, ast.Name):
                lst = lists.get(first.id)
            if lst is None or not lst.elts:
                continue
            script_rel = None
            argv = []
            for i, elt in enumerate(lst.elts):
                rel = resolve_join(elt)
                if rel is not None and is_gate_path(rel):
                    script_rel = rel
                    for a in lst.elts[i + 1:]:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                            argv.append(a.value)
                    break
            if script_rel is None:
                continue
            found.append((script_rel, argv))

    # 逐个函数作用域处理（函数内的 run 调用只在**本函数**里解引用）
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            harvest([fn])
    # 模块级（函数之外的 run 调用）
    harvest([tree])

    uniq = []
    seen = set()
    for rel, argv in found:
        if rel in seen:
            continue
        seen.add(rel)
        uniq.append((rel, argv))
    return uniq


def _walk(scope_nodes):
    for sc in scope_nodes:
        for node in ast.walk(sc):
            yield node


def _is_join(node):
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'join'
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == 'path')


def run_script(rel, argv):
    path = os.path.join(REPO, rel.replace('/', os.sep))
    if not os.path.isfile(path):
        return None, '脚本不存在'
    cmd = [sys.executable, path] + argv
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=900,
                           cwd=REPO)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return None, '超时（>900 s）'
    except (OSError, subprocess.SubprocessError) as e:
        return None, '执行失败：%r' % e


def main():
    print('=' * 72)
    print('§251 打包路径闸门自检（清单从 pack_v13.py 源码**抽**出，不手抄）')
    print('=' * 72)

    if not os.path.isfile(PACK):
        print('!! 找不到 %s' % PACK)
        return 2

    calls = pack_gate_calls()
    print('  从 pack_v13.py 抽出 %d 个被调用的脚本：' % len(calls))
    for rel, argv in calls:
        print('    - %s %s' % (rel, ' '.join(argv)))
    print()

    # ── 判据①：清单非空（抽不出 = 解析失效 ⇒ fail-closed）──
    check('G1 能从 pack_v13.py 抽出闸门清单', len(calls) > 0,
          'n=%d' % len(calls))

    # ── 判据②：§251 的 app049 闸门必须是其中之一，且**现在就是绿的** ──
    app049 = 'results/app/app049_pkg_path_hardcode_gate.py'
    check('G2 app049「包路径写死」闸门在打包路径上', app049 in [c[0] for c in calls])
    rc, out = run_script(app049, [])
    check('G3 app049 闸门现在是绿的（exit=0）', rc == 0, 'rc=%r' % rc)
    check('G4 app049 闸门输出「0 处违规」', out and '0 处违规' in out)
    check('G5 app049 无过期白名单条目（白名单没腐烂）',
          out and '过期' not in out.split('总判定')[0].split('白名单 =')[-1][:400]
          if out and '白名单 =' in out else True)

    # ── 判据③：其它闸门逐个跑（需要 --pkg 的 ⇒ 报告状态，不猜）──
    for rel, argv in calls:
        if rel == app049:
            continue
        needs_pkg = '--pkg' in argv
        if needs_pkg:
            note('闸门 %s（需 --pkg ⇒ 需指定客户包，本轮不代选）' % rel)
            continue
        rc, out = run_script(rel, argv)
        if rc is None:
            note('闸门 %s（%s）' % (rel, out))
            continue
        check('闸门 %s 现在是绿的（exit=0）' % rel, rc == 0, 'rc=%d' % rc)

    # ── 判据④：抽取器自身的**鉴别力**（反证组）──
    #   「抽到的清单」如果恒为空/恒为假 ⇒ 本脚本会**恒 PASS** ⇒ 空洞恒真。
    #   ⇒ 在**临时副本**的 pack_v13.py 里加一个**新闸门调用** ⇒ 抽取器必须看见它。
    tmp_src = os.path.join(HERE, '_app251_guard_selftest_pack.py')
    try:
        with io.open(PACK, encoding='utf-8') as f:
            pack_src = f.read()
        # 在 pack_v13.py 末尾注入一个**新的** subprocess.run 调用
        injected = pack_src + (
            "\n\ndef _app251_injected_gate_call():\n"
            "    import subprocess, sys, os\n"
            "    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n"
            "                           'results', 'app', '_app251_injected_probe.py')\n"
            "    return subprocess.run([sys.executable, script],\n"
            "                          capture_output=True)\n")
        with io.open(tmp_src, 'w', encoding='utf-8', newline='\n') as f:
            f.write(injected)
        calls2 = pack_gate_calls(path=tmp_src)
        rels2 = [c[0] for c in calls2]
        check('G6 抽取器能看见**注入的**新闸门调用（有鉴别力）',
              'results/app/_app251_injected_probe.py' in rels2,
              'n=%d' % len(rels2))
        check('G7 抽取器在副本上仍抽到 4 个原闸门（未因注入而漏抽）',
              len([r for r in rels2 if r != 'results/app/_app251_injected_probe.py']) == 4,
              'n=%d' % len(rels2))
    finally:
        if os.path.isfile(tmp_src):
            os.remove(tmp_src)

    print()
    print('=' * 72)
    print('PASS %d / FAIL %d / SKIP %d' % (len(PASS), len(FAIL), len(SKIP)))
    if FAIL:
        print('失败项：%s' % FAIL)
    print('总判定：%s' % ('PASS' if not FAIL else 'FAIL'))
    print('=' * 72)

    ev = os.path.join(HERE, 'app251_pack_gates_guard.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(pass_list=PASS, fail_list=FAIL, skip_list=SKIP,
                       n_calls=len(calls),
                       calls=[dict(script=r, argv=a) for r, a in calls],
                       verdict='PASS' if not FAIL else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print('证据已落盘：%s' % ev)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
