#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app049_pkg_path_hardcode_gate.py —— 「客户包路径写死」缺陷类别的**闸门**。

背景（STATUS §48）
------------------
真实事故：`results/app/test_tts_close_gui_quit_pkg.py` 把客户包版本**写死**成
`Confucius4_LiveCaption_v1.4`。包一升到 v1.5，这个「包内验收脚本」就指着
**旧包**跑 ⇒ 报出 3 项 FAIL ⇒ 看起来像**真回归**，实际只是**脚本过期**。

🔴 **「修掉一处」≠「这一类不会再来」** ⇒ 缺陷类别必须**进闸门**。

本闸门覆盖**两条**类别：

| 类别 | 判据 |
|---|---|
| **A** 活跃验收/回归脚本里写死客户包**版本** | `test_*` / `*_gate*` / `*_check*` / `*_verify*` / `*_probe*` 里出现 `Confucius4_LiveCaption_v<数字>` 的**代码行** |
| **B** 会进包的生产模块里写死客户包**路径** | 包内 `app/*.py` 对应的仓库模块里，出现 `Confucius4_LiveCaption_v<数字>` 的**代码行** |

🔴 **只判「代码行」**（跳过注释与文档字符串）⇒ 不误报「文档里举例写个路径」。
🔴 **白名单**：FTP 上的 zip 文件名（那是「要下载哪个包」的业务参数，不是路径推导）
   与**一次性历史诊断脚本**（写死旧版本是**有意的**，为了复现当时状态）。
   白名单必须**写明理由** ⇒ 不允许「无声放过」。

用法
----
    python results/app/app049_pkg_path_hardcode_gate.py
    python results/app/app049_pkg_path_hardcode_gate.py --json <out.json>
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **扫描根可被环境变量覆盖**（供闸门自检在临时副本里跑）
#:   自检脚本要证明「闸门能抓到真缺陷」⇒ 必须能在**注入缺陷的副本**上运行闸门
#:   ⇒ 不能让闸门死认自己的 `__file__` 所在仓库。
REPO = os.environ.get('APP049_REPO_ROOT', REPO)

#: 客户包目录名的固定前缀
PKG_PREFIX = 'Confucius4_LiveCaption_v'

#: 包目录名（含版本）的匹配
PKG_NAME_RE = re.compile(re.escape(PKG_PREFIX) + r'\d+(?:\.\d+)*')

#: 判定「活跃验收/回归脚本」的文件名模式
ACTIVE_RE = re.compile(r'(^test_|_gate|_check|_verify|_probe)', re.I)

#: 扫描根（相对仓库）
SCAN_ROOTS = ('results/app', 'live_caption')

#: 🔴 白名单：**每条都必须写明理由**（不许无声放过）
#:
#: 🔴 §86 修正：**删掉 2 条已过期的白名单** ——
#:   `app014b_v15_preship_check.py` / `app049_pkg_path_hardcode_gate.py`
#:   之前进白名单，**唯一原因是闸门把 docstring 误判成代码**
#:   （`ast.Expr` 包着字符串常量 ⇒ 外层节点不是 `ast.Constant` ⇒ 被标成代码行）
#:   ⇒ 闸门修好后这两条**已不再命中** ⇒ 留着就成了「永远绿的逃逸口」⇒ 删除。
#:   （闸门现在会**主动报告过期白名单条目**。）
#:
#: ⚠️ 但 `app049_gate_selftest.py` **必须保留** ——
#:   它的命中是**真实代码行**（把「真缺陷形态」的字面量**写进临时文件**）
#:   ⇒ 不是 docstring 误判 ⇒ 白名单理由依然成立。
#:   （实测：误把它一并删掉 ⇒ 闸门在**干净仓库**上也 FAIL ⇒ 自检 S1/S2/S7 全红。）
WHITELIST = {
    # FTP 上的 **zip 文件名** —— 这是「要下载哪个包」的业务参数，
    # **不是**本地包目录的路径推导 ⇒ 写死不算缺陷。
    'results/app/ftp_probe.py': 'FTP 远端 zip 文件名（业务参数，非本地路径）',
    'results/app/ftp_probe2.py': 'FTP 远端 zip 文件名（业务参数，非本地路径）',
    # **一次性历史诊断脚本** —— 对应 C-111 那个已结束的历史事件，
    # 写死 v1.3 是**有意的**（就是要复现当时的状态）⇒ 不是缺陷。
    'live_caption/diag_c111_revert_verify.py': '一次性历史诊断（复现 C-111 当时状态），有意写死',
    'live_caption/diag_c111_v3_verify.py': '一次性历史诊断（复现 C-111 当时状态），有意写死',
    # 🔴 **闸门自检脚本** —— 它**必须**包含「真缺陷形态」的样例字符串才能自检
    #    （这里是**真实代码行**：把样例字面量写进临时文件，不是 docstring）。
    'results/app/app049_gate_selftest.py': '闸门自检脚本（含「真缺陷形态」样例，用于自检）',
}


def code_lines_with_pkg_name(path):
    """返回该文件里**代码行**中出现客户包名的地方。

    🔴 用 `ast` 判定「哪些行属于代码」⇒ 自动跳过注释与文档字符串。
    """
    src = open(path, 'r', encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # 语法错误 ⇒ 退回文本扫描（保守：整文件都当代码行）
        hits = []
        for i, ln in enumerate(src.split('\n'), 1):
            if PKG_NAME_RE.search(ln) and not ln.strip().startswith('#'):
                hits.append((i, ln.strip()))
        return hits

    # 收集「非注释、非字符串」的行号
    #
    # 🔴🔴 §86 修正（原实现有**真实缺陷**）：
    #   原来的写法是「跳过 `ast.Constant`（字符串字面量）」，但 **docstring 在 AST 里是
    #   `Expr(Constant(str))` 两层** ⇒ 外层的 `ast.Expr` 节点**不是** Constant
    #   ⇒ `ast.walk` 照样会把它整个 `lineno..end_lineno` 区间标成「代码行」
    #   ⇒ **模块/函数/类的 docstring 全部被误判成代码** ⇒ 闸门对**文档里提到包名**
    #   的文件一律报错。
    #   ⇒ 实证：`results/app/_app81_check_pkg_match.py` 的修复说明写在 docstring 里
    #      （第 5 行）⇒ 被判成「代码行里的包名」⇒ 闸门 FAIL ⇒ 打包被拒。
    #   ⇒ 修法：**显式跳过「裸字符串表达式」**（`ast.Expr` 且其 value 是字符串常量）
    #      —— 这才是 docstring 的精确形态；
    #      ⚠️ 不能跳过所有 `ast.Expr`（`f(x)` 这种调用表达式也是 Expr）。
    #   ⇒ 注意：**赋值语句里的字符串**（`X = "...Confucius4..."`）**仍然要判**
    #      —— 那才是真缺陷（真路径常量）。
    code_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            continue                      # 字符串字面量（作为值使用时）
        if isinstance(node, ast.Expr):
            v = getattr(node, 'value', None)
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                continue                  # 🔴🔴 裸字符串表达式 = docstring ⇒ 不算代码
        lineno = getattr(node, 'lineno', None)
        if lineno is None:
            continue                      # 例：`ast.Module` 没有 lineno
        end = getattr(node, 'end_lineno', None) or lineno
        for n in range(lineno, end + 1):
            code_lines.add(n)

    hits = []
    for i, ln in enumerate(src.split('\n'), 1):
        if not PKG_NAME_RE.search(ln):
            continue
        s = ln.strip()
        if s.startswith('#'):
            continue                      # 🔴 纯注释行 ⇒ 不判（说明历史缺陷用）
        if i not in code_lines:
            continue                      # 文档字符串 ⇒ 不判
        hits.append((i, s))
    return hits


def pkg_module_names():
    """包内 `app/` 的模块名（从**实际包目录**取，单一数据源）。"""
    sys.path.insert(0, REPO)
    try:
        import pkg_paths
        app = pkg_paths.pkg_app_dir()
    except Exception:
        return set()
    try:
        return {n for n in os.listdir(app) if n.endswith('.py')}
    except OSError:
        return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=None, help='证据落盘路径')
    args = ap.parse_args()

    pkg_mods = pkg_module_names()
    violations = []
    checked = 0
    # 🔴 §86：记录「白名单里已经不再命中」的条目 ⇒ 防止白名单**悄悄腐烂**
    #   （修好闸门的 docstring 误判后，原先靠误判才需要的三条白名单就失效了）
    #   ⇒ 白名单条目失效后应当**删掉**（否则「白名单」会变成一个永远绿的逃逸口）。
    stale_whitelist = []

    for root in SCAN_ROOTS:
        root_abs = os.path.join(REPO, root.replace('/', os.sep))
        if not os.path.isdir(root_abs):
            continue
        for dirpath, dirnames, filenames in os.walk(root_abs):
            dirnames[:] = [d for d in dirnames if d not in ('__pycache__', '.git')]
            for fn in filenames:
                if not fn.endswith('.py'):
                    continue
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, REPO).replace(os.sep, '/')
                hits = code_lines_with_pkg_name(fp)
                if rel in WHITELIST:
                    if not hits:
                        # 🔴 白名单条目已不再命中 ⇒ 记为「过期」，提示删除
                        stale_whitelist.append(rel)
                    continue
                if not hits:
                    continue
                checked += 1

                is_pkg_mod = fn in pkg_mods and root == 'live_caption'
                is_active = bool(ACTIVE_RE.search(fn))
                if not (is_pkg_mod or is_active):
                    continue                     # 历史一次性脚本 ⇒ 只登记不算缺陷

                cat = 'B' if is_pkg_mod else 'A'
                violations.append(dict(
                    category=cat, file=rel,
                    lines=[h[0] for h in hits[:5]],
                    n_lines=len(hits),
                    samples=[h[1][:100] for h in hits[:3]],
                ))

    print('=' * 72)
    print('§48 闸门：客户包路径「写死版本」缺陷类别')
    print('=' * 72)
    print('包内 app/*.py 实测 = %d 个' % len(pkg_mods))
    print('扫描根 = %s' % ', '.join(SCAN_ROOTS))
    print('白名单 = %d 条（每条带理由）' % len(WHITELIST))
    for k, v in WHITELIST.items():
        print('   - %-44s %s' % (k, v))
    print()
    if stale_whitelist:
        print('⚠️ 白名单**已过期**（不再命中）= %d 条 ⇒ 应当删除，'
              '否则白名单会变成永远绿的逃逸口：' % len(stale_whitelist))
        for k in stale_whitelist:
            print('   - %s' % k)
        print()
    print('命中「代码行里有客户包名」的文件数 = %d' % checked)

    if violations:
        print()
        print('🔴 违规 %d 处：' % len(violations))
        for v in violations:
            print('   [%s] %-50s 行%s' % (v['category'], v['file'], v['lines']))
            for s in v['samples']:
                print('        %s' % s)
        print()
        print('修法：用 `pkg_paths.discover_pkg_dir()` / `pkg_paths.pkg_app_dir()`'
              '（单一数据源），**不写死版本号**。')
    else:
        print()
        print('✅ 0 处违规')

    ok = not violations
    verdict = 'PASS' if ok else 'FAIL'
    print()
    print('总判定：%s' % verdict)

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(dict(verdict=verdict, n_violations=len(violations),
                           violations=violations, whitelist=WHITELIST,
                           stale_whitelist=stale_whitelist,
                           pkg_module_count=len(pkg_mods)),
                      f, ensure_ascii=False, indent=2)
        print('证据已落盘：%s' % args.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
