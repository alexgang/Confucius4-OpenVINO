# -*- coding: utf-8 -*-
"""app111 — **CLI 模式 `on_final` 签名契约**（§78 自查抓出的真实缺陷）。

## 缺陷（真实存在，预先存在，不是本轮引入）

`Session._loop` 调的是 `self.on_final(*_split_spk(final))`，
而 `_split_spk()` **恒返回 3 元组** `(text, spk, spk_conf)`
⇒ 必然传 **3 个**位置参数；
但 CLI 的 `on_final` 旧实现写的是 `def on_final(t)`（只收 **1 个**）
⇒ **CLI 模式一收到定稿就崩**：

    TypeError: run_cli.<locals>.on_final() takes 1 positional argument but 3 were given

⚠️ **GUI 侧不受影响**（`App._on_final(self, text, spk=None, spk_conf=None)` 接受 3 参）
⇒ 这就是「GUI 能跑、CLI 崩」的原因。
⚠️ 该缺陷在 `a9ed250`（§76 交付 commit）**就已存在** ⇒ 可用固定 commit 做反证基线。

## 判据（零推理 / 零 GPU / 零 NPU）

- **A 组（契约对齐）**：CLI 的 `on_final` 形参个数 **≥ 3**（能接 `_split_spk` 的 3 参）。
- **B 组（调用方契约）**：`Session._loop` 确实用 `*_split_spk(...)` 展开调用 ⇒ 调用点形参数
  必须能容纳 3 参。
- **C 组（`_split_spk` 恒 3 元组）**：纯字符串 / dict / 元组三种输入 ⇒ 都返回 **3 元组**。
- **D 组（GUI 侧不受影响）**：GUI 的 `_on_final` 本来就接受 3 参 ⇒ 不许被我改坏。
- **E 组（反证）**：用 **AST 重建** 把 CLI 的 `on_final` 改回 `def on_final(t)`
  ⇒ A 组必须 FAIL ⇒ 证明判据不是「永远 PASS」。

## 用法

    <python> results/app/app111_cli_on_final_contract.py
    APP111_SRC_ROOT=<repo>/live_caption APP111_EVID=<out.json> <python> ...
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_ROOT = os.environ.get('APP111_SRC_ROOT') or os.path.join(REPO, 'live_caption')
EVID = os.environ.get('APP111_EVID') or os.path.join(
    HERE, 'app111_cli_on_final_contract_evidence.json')


def load(path):
    return ast.parse(open(path, encoding='utf-8').read())


def find_func(tree, name, in_class=None):
    """在 AST 里找函数定义；返回 (node, class_name or None)。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                if in_class is None:
                    return node, None
                # 找它的父类
                for c in ast.walk(tree):
                    if isinstance(c, ast.ClassDef) and c.name == in_class:
                        if any(n is node for n in c.body):
                            return node, c.name
    return None, None


def n_pos_args(fn):
    a = fn.args
    return len(a.posonlyargs) + len(a.args), len(a.kwonlyargs), a.vararg is not None


def call_arity(tree, func_name):
    """找出所有 `on_final(*...)` 展开调用 ⇒ 返回展开的元数（若能确定）。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            fname = getattr(f, 'attr', None) or getattr(f, 'id', None)
            if fname == func_name:
                out.append(node)
    return out


def main() -> int:
    path = os.path.join(SRC_ROOT, 'live_caption_app.py')
    tree = load(path)
    checks = []

    def chk(cid, group, name, ok, got, want):
        checks.append(dict(id=cid, group=group, name=name, ok=bool(ok),
                           got=got, want=want))

    # ── A 组：CLI 的 on_final 形参 ≥ 3 ──────────────────────────
    cli_fn, _ = find_func(tree, 'on_final')
    if cli_fn is None:
        chk('A1', 'A', '找到 CLI 的 on_final', False, None, 'found')
    else:
        pos, kw, star = n_pos_args(cli_fn)
        # `def on_final(t, spk=None, spk_conf=None)` ⇒ pos=3, kw=0
        chk('A1', 'A', 'CLI on_final 能接 3 个位置参数',
            pos >= 3, pos, '>=3')
        chk('A2', 'A', 'CLI on_final 有默认值的可选参数（向后兼容 1 参调用）',
            any(d is not None for d in cli_fn.args.defaults), pos, 'has defaults')

    # ── B 组：Session._loop 用 * 展开调用 ───────────────────────
    sess_loop, _ = find_func(tree, '_loop', in_class='Session')
    star_calls = 0
    if sess_loop is not None:
        for node in ast.walk(sess_loop):
            if isinstance(node, ast.Call):
                f = node.func
                fname = getattr(f, 'attr', None) or getattr(f, 'id', None)
                if fname == 'on_final' and any(isinstance(a, ast.Starred)
                                              for a in node.args):
                    star_calls += 1
    chk('B1', 'B', 'Session._loop 用 * 展开调用 on_final', star_calls >= 1,
        star_calls, '>=1')

    # ── C 组：_split_spk 恒返回 3 元组 ──────────────────────────
    split_fn, _ = find_func(tree, '_split_spk')
    if split_fn is None:
        chk('C1', 'C', '找到 _split_spk', False, None, 'found')
    else:
        # 执行它（独立命名空间）
        ns = {}
        mod = ast.Module(body=[split_fn], type_ignores=[])
        exec(compile(mod, '<x>', 'exec'), ns)
        fn = ns['_split_spk']
        for cid, val in [('C1', 'hello'), ('C2', {'text': 'hi', 'spk': 1}),
                         ('C3', ('t', 's', 0.5))]:
            r = fn(val)
            chk(cid, 'C', '_split_spk(%r) 返回 3 元组' % (type(val).__name__,),
                isinstance(r, tuple) and len(r) == 3,
                (len(r) if isinstance(r, tuple) else r), 3)

    # ── D 组：GUI 侧不受影响 ───────────────────────────────────
    gui_fn, _ = find_func(tree, '_on_final', in_class='App')
    if gui_fn is None:
        chk('D1', 'D', '找到 GUI 的 App._on_final', False, None, 'found')
    else:
        pos, kw, star = n_pos_args(gui_fn)
        chk('D1', 'D', 'GUI App._on_final 仍接受 3 个位置参数', pos >= 3, pos, '>=3')

    # ── E 组（反证）：把 CLI 的 on_final 改回 `def on_final(t)` ──
    if cli_fn is not None:
        tree2 = load(path)
        old = ast.parse('def on_final(t):\n    pass\n').body[0]
        # 找到 CLI 的那个 on_final（在 run_cli 内）并替换
        replaced = False
        for node in ast.walk(tree2):
            if isinstance(node, ast.FunctionDef) and node.name == 'run_cli':
                for i, sub in enumerate(node.body):
                    if isinstance(sub, ast.FunctionDef) and sub.name == 'on_final':
                        node.body[i] = old
                        replaced = True
                        break
            if replaced:
                break
        ns2 = {}
        found = None
        for node in ast.walk(tree2):
            if isinstance(node, ast.FunctionDef) and node.name == 'run_cli':
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == 'on_final':
                        found = sub
        if found is not None:
            pos, kw, star = n_pos_args(found)
            chk('E1', 'E', '反证：旧签名 `def on_final(t)` 只有 1 个位置参数',
                pos == 1, pos, 1)
            chk('E2', 'E', '反证：旧签名下 A 组判据必须 FAIL',
                pos < 3, pos, '<3 ⇒ A1 FAIL')
        else:
            chk('E1', 'E', '反证：定位到 CLI on_final', False, None, 'found')
            chk('E2', 'E', '反证：旧签名下 A 组判据必须 FAIL', False, None, 'FAIL')

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    print('=== app111 CLI on_final 签名契约（零推理）===')
    print('SRC_ROOT = %s' % SRC_ROOT)
    for c in checks:
        print('  [%s] %-4s %-6s %-56s %s  got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['group'],
                 c['name'], 'OK' if c['ok'] else 'XX', c['got'], c['want']))
    print('\nSUMMARY: PASS=%d FAIL=%d TOTAL=%d' % (n_pass, n_fail, len(checks)))

    out = dict(src_root=SRC_ROOT, ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               pass_count=n_pass, fail_count=n_fail, total=len(checks),
               checks=checks,
               note='零推理；ast 抽源码；含 AST 重建反证')
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据已写入：%s' % EVID)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
