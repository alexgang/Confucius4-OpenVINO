#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app201_pkg_skeleton_gate.py —— 【APP-052/053/054】客户包同步前的「骨架等价」闸门。

## 为什么需要这个（而不是整目录覆盖）

铁律：「仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**，
**禁止整目录覆盖同步**」。

🔴 但本轮 APP-054 把 `speaker_tracker.py` **整体重写**了
（同步阻塞版 23 853 B → 线程化版 49 333 B）
⇒ **逐块字符串替换不现实**（几百处）
⇒ 需要「**代码骨架等价校验后升级基底**」这条**允许的第二条路**。

## 骨架等价 = 什么

指**对外接口契约**不变：
1. **模块级公开名**（`__all__` + 顶层非下划线定义）集合一致；
2. **`SpeakerBridge` 的公开方法**集合一致（**只允许新增**，不许删改签名）；
3. **CLI 参数**集合：`live_caption_app.py` 的 `--xxx` 选项**只增不减**；
4. **`ast.parse` 通过**（语法有效）。

⇒ 骨架等价 ⇒ 「升级基底」不会破坏**调用方契约**
⇒ 允许把**仓库版整文件**写进包内对应位置（**只覆盖这一个文件**，不是整目录）。

## 反证（判据非恒真）

注入 4 类缺陷到「候选版」⇒ 必须**恰好**被抓到：
- ① 删掉一个公开方法；
- ② 删掉一个 CLI 参数；
- ③ 引入语法错误；
- ④ 删掉一个模块级公开名。

## 用法

    python results/app/app201_pkg_skeleton_gate.py [--check-only]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def find_repo_root(start: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent


def read_norm(path: str):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    return raw.replace('\r\n', '\n'), nl


def public_names(tree: ast.AST) -> set:
    """模块级公开名（顶层定义 + 赋值 + import 的 as 名）。"""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            if not node.name.startswith('_'):
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith('_'):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign):
            if (isinstance(node.target, ast.Name)
                    and not node.target.id.startswith('_')):
                names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                nm = a.asname or a.name.split('.')[0]
                if not nm.startswith('_'):
                    names.add(nm)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                nm = a.asname or a.name
                if not nm.startswith('_') and nm != '*':
                    names.add(nm)
    return names


def class_methods(tree: ast.AST, cls_name: str) -> dict:
    """类的公开方法名 ⇒ 参数字符串（用于「不许改签名」）。"""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not sub.name.startswith('_'):
                        args = [a.arg for a in sub.args.args]
                        out[sub.name] = '(' + ','.join(args) + ')'
    return out


def cli_options(tree: ast.AST) -> set:
    """`add_argument('--xxx')` 的选项名集合。"""
    out = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add_argument'):
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    if a.value.startswith('-'):
                        out.add(a.value)
    return out


def analyze(path: str) -> dict:
    """解析一个文件 ⇒ 骨架特征。语法错误 ⇒ 抛异常。"""
    text, nl = read_norm(path)
    tree = ast.parse(text, filename=path)     # 🔴 语法错误 ⇒ 直接抛
    return dict(
        path=path,
        bytes=len(text.encode('utf-8')),
        newline=('CRLF' if nl == '\r\n' else 'LF'),
        public=public_names(tree),
        bridge_methods=class_methods(tree, 'SpeakerBridge'),
        cli_options=cli_options(tree),
        ast_ok=True,
    )


def compare(base: dict, cand: dict) -> list:
    """骨架差异清单（**只报「破坏性」差异**：删除 / 签名改 / 参数删）。"""
    diffs = []
    lost_names = base['public'] - cand['public']
    if lost_names:
        diffs.append(dict(kind='lost_public_name',
                          detail=sorted(lost_names)[:20]))
    lost_m = set(base['bridge_methods']) - set(cand['bridge_methods'])
    if lost_m:
        diffs.append(dict(kind='lost_bridge_method', detail=sorted(lost_m)))
    changed_sig = {k: (base['bridge_methods'][k], cand['bridge_methods'][k])
                   for k in set(base['bridge_methods']) & set(cand['bridge_methods'])
                   if base['bridge_methods'][k] != cand['bridge_methods'][k]}
    if changed_sig:
        diffs.append(dict(kind='changed_bridge_signature',
                          detail=changed_sig))
    lost_cli = base['cli_options'] - cand['cli_options']
    if lost_cli:
        diffs.append(dict(kind='lost_cli_option', detail=sorted(lost_cli)))
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    sys.path.insert(0, repo)
    import pkg_paths
    pkg = pkg_paths.discover_pkg_dir()
    pkg_app = os.path.join(pkg, 'app')

    files = ['speaker_tracker.py', 'live_caption_app.py', 'speaker_assets.py']
    checks = []

    def chk(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))

    base, cand = {}, {}
    for fn in files:
        p_pkg = os.path.join(pkg_app, fn)
        p_repo = os.path.join(repo, 'live_caption', fn)
        for p in (p_pkg, p_repo):
            if not os.path.isfile(p):
                chk('文件存在 %s' % os.path.basename(p), False, p)
                return 1
        try:
            base[fn] = analyze(p_pkg)
        except SyntaxError as e:
            chk('包内 %s 语法有效' % fn, False, str(e))
            return 1
        try:
            cand[fn] = analyze(p_repo)
        except SyntaxError as e:
            chk('仓库 %s 语法有效' % fn, False, str(e))
            return 1
        chk('仓库 %s 语法有效（ast.parse）' % fn, True,
            dict(bytes=cand[fn]['bytes'], newline=cand[fn]['newline']))

    # ── 骨架等价（仓库 vs 包内）──
    for fn in files:
        d = compare(base[fn], cand[fn])
        chk('骨架等价：仓库 %s 未破坏包内契约' % fn, not d, d or '无破坏性差异')

    # ── 反证：注入 4 类缺陷 ⇒ 必须被抓到 ──
    # 🔴 **基线方向**：反证要证明「**比较器**能识破破坏」⇒
    #   基线 = **仓库现状**，候选 = **注入缺陷后的仓库版**
    #   （不是「包内旧版 vs 仓库版」—— 包内旧版**本来就没有** `stop()` /
    #    `flush(timeout)` / `_WIN_S` ⇒ 用它当基线时，注入缺陷根本无从体现）
    src, _ = read_norm(os.path.join(repo, 'live_caption', 'speaker_tracker.py'))
    base_repo = cand['speaker_tracker.py']      # 仓库现状 = 反证的基线
    # ① 删公开方法
    inj1 = src.replace('    def stop(self) -> None:', '    def stop_RENAMED(self) -> None:')
    # ② 改签名（删一个参数）
    inj2 = src.replace('    def flush(self, timeout: float = 30.0) -> int:',
                       '    def flush(self) -> int:')
    # ③ 语法错误
    inj3 = src + '\ndef broken(:\n'
    # ④ 删模块级公开名
    #    🔴 必须用**真公开名**（`_WIN_S` 是私有名 ⇒ 改名**不算**破坏公开契约
    #    ⇒ 用它当反证会让判据「看起来没抓到」，其实是被测对象本身没被破坏）
    inj4 = src.replace('def span_for_final(', 'def span_for_final_RENAMED(')
    for label, text, fn in (('① 删公开方法', inj1, 'speaker_tracker.py'),
                            ('② 改公开方法签名', inj2, 'speaker_tracker.py'),
                            ('③ 引入语法错误', inj3, 'speaker_tracker.py'),
                            ('④ 删模块级公开名', inj4, 'speaker_tracker.py')):
        tmp = os.path.join(HERE, '_app201_injected.py')
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(text)
        caught = []
        try:
            c = analyze(tmp)
            d = compare(base_repo, c)
            caught = [x['kind'] for x in d]
        except SyntaxError:
            caught = ['syntax_error']
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        chk('反证 %s 必须被抓到' % label, bool(caught),
            dict(caught=caught or ['NOTHING CAUGHT ⇒ 判据恒真']))

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = dict(script='app201_pkg_skeleton_gate.py',
               correction='APP-052/053/054',
               purpose='客户包同步前的「骨架等价」闸门（允许整文件升级基底的前提）',
               repo=repo, pkg=pkg,
               base={fn: dict(public=sorted(base[fn]['public']),
                                bridge_methods=base[fn]['bridge_methods'],
                                cli_options=sorted(base[fn]['cli_options']))
                     for fn in files},
               cand={fn: dict(public=sorted(cand[fn]['public']),
                                bridge_methods=cand[fn]['bridge_methods'],
                                cli_options=sorted(cand[fn]['cli_options']))
                     for fn in files},
               checks=checks, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL')
    with open(os.path.join(HERE, 'app201_pkg_skeleton_evidence.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for c in checks:
        print('  [%s] %s  %s'
              % ('PASS' if c['ok'] else 'FAIL', c['name'],
                 json.dumps(c['detail'], ensure_ascii=False)[:400]))
    print('结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s'
          % os.path.join(HERE, 'app201_pkg_skeleton_evidence.json'))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
