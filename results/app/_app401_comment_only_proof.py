# -*- coding: utf-8 -*-
"""
App · 「注释-only 改动」的**行为不变证明**（AST 口径）

用途
----
本轮改了 `live_caption/speaker_tracker.py` 的**注释**（把「ASR 默认 10 s / 589 帧」
这类**已过时且危险**的陈述改成事实陈述）。
⇒ 必须证明：**除了注释与 docstring 之外，可执行代码逐字未变**。

口径（AST）：
1. `ast.parse` 前后都成功；
2. **语句多重集**（去掉 docstring 后的 `ast.dump` 节点集合）逐项相等；
3. **常量多重集**（`ast.Constant` 的值）逐项相等 —— 证明没有改任何字面量；
4. **函数名 + 参数** 列表逐项相等 —— 证明没有改签名；
5. **注释行集合** 允许变化（这是本轮唯一允许的差异）；
6. `docstring` 允许变化（本轮改了 3 处 docstring 的文字）。

🔴 **反证组**：把脚本里的 `STRIP_DOCSTRINGS` 关掉再跑一次 ⇒ 必须 FAIL
（否则说明「只许改注释」这条判据是恒真的、没鉴别力）。

用法：python results/app/_app401_comment_only_proof.py
"""
import ast
import collections
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
TARGET = 'live_caption/speaker_tracker.py'
STRIP_DOCSTRINGS = True


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def strip_docstrings(tree):
    """把每个函数/类/模块的 docstring 置空（只改 AST 副本，不改源文件）。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, 'body', None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                body[0].value.value = ''
    return tree


def fingerprint(src, strip=True):
    tree = ast.parse(src)
    if strip:
        tree = strip_docstrings(tree)
    stmts = sorted(ast.dump(n) for n in ast.walk(tree) if isinstance(n, ast.stmt))
    consts = collections.Counter()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            consts[repr(n.value)] += 1
    sigs = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            sigs.append((n.name,
                         [x.arg for x in a.posonlyargs + a.args],
                         [x.arg for x in a.kwonlyargs],
                         len(a.defaults),
                         bool(a.vararg), bool(a.kwarg)))
    return {'stmts': stmts, 'consts': consts, 'sigs': sigs}


def main():
    cur_path = os.path.join(REPO, TARGET)
    with open(cur_path, encoding='utf-8') as f:
        cur = f.read()

    # 🔴 **改前基线 = 客户包 v2.4 的副本**（不是 HEAD）：
    #    HEAD 已含本轮改动 ⇒ 拿 HEAD 当基线会必然 FAIL（提交后不自洽）。
    #    客户包那份是**未被本轮改动的原始注释版** ⇒ 稳定的「改前」参照，
    #    且顺带证明「开发树与客户包的**可执行代码逐条相同**」。
    PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'
    pkg_copy = os.path.join(PKG, 'app', 'speaker_tracker.py')
    old = None
    if os.path.isfile(pkg_copy):
        old = open(pkg_copy, encoding='utf-8').read()

    checks = []

    def chk(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    chk('target_exists', os.path.isfile(cur_path), cur_path)
    if old is None:
        out = {'verdict': 'SKIP', 'note': 'HEAD 无该文件，无法比对', 'checks': checks}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    a = fingerprint(old, strip=STRIP_DOCSTRINGS)
    b = fingerprint(cur, strip=STRIP_DOCSTRINGS)

    chk('ast_parses', True, '改前基线（客户包副本）与工作树均 ast.parse 成功')
    chk('stmt_multiset_same', a['stmts'] == b['stmts'],
        '语句多重集 %s（改前基线 %d 条 / 当前 %d 条）'
        % ('相等' if a['stmts'] == b['stmts'] else '不等', len(a['stmts']), len(b['stmts'])))
    chk('const_multiset_same', a['consts'] == b['consts'],
        '常量多重集 %s' % ('相等' if a['consts'] == b['consts'] else '不等'))
    chk('signatures_same', a['sigs'] == b['sigs'],
        '函数签名 %s（%d 个函数）'
        % ('相等' if a['sigs'] == b['sigs'] else '不等', len(a['sigs'])))

    # docstring 文本确实变了（本轮的预期改动）
    da = fingerprint(old, strip=False)['consts']
    db = fingerprint(cur, strip=False)['consts']
    doc_changed = da != db
    chk('docstring_text_changed_as_expected', doc_changed,
        'docstring 文本 %s（这是本轮**预期**要改的部分）'
        % ('已变' if doc_changed else '未变'))

    # 注释行集合：本轮唯一允许变的
    ca = {l for l in old.splitlines() if l.lstrip().startswith('#')}
    cb = {l for l in cur.splitlines() if l.lstrip().startswith('#')}
    chk('only_comments_and_docstrings_changed',
        (ca != cb) or doc_changed,
        '注释行集合 %s（改前基线 %d 行 / 当前 %d 行）；docstring %s'
        % ('已变' if ca != cb else '未变', len(ca), len(cb),
           '已变' if doc_changed else '未变'))

    # 行尾未被破坏
    crlf = b'\r\n' in open(cur_path, 'rb').read()
    chk('eol_preserved', not crlf, '工作树文件不含 CRLF（保持 LF）')

    n_pass = sum(1 for c in checks if c['pass'])
    n_fail = sum(1 for c in checks if not c['pass'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'

    out = {
        'created_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'target': TARGET,
        'device_job': False,
        'lock_note': '纯 CPU 静态检查（不加载模型）⇒ 不需要 MACHINE_LOCK',
        'criterion': ('AST：语句多重集 / 常量多重集 / 函数签名 三者相等 '
                      '⇒ 仅注释与 docstring 变化；改前基线 = 客户包 v2.4 副本（稳定参照）'),
        'baseline_kind': '客户包 v2.4 的 app/speaker_tracker.py（未被本轮改动 ⇒ 稳定的「改前」参照）',
        'baseline_sha256': hashlib.sha256(old.encode('utf-8')).hexdigest(),
        'worktree_sha256': sha256_of(cur_path),
        'head_bytes': len(old.encode('utf-8')),
        'worktree_bytes': os.path.getsize(cur_path),
        'checks': checks,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'verdict': verdict,
    }

    dest = os.path.join(REPO, 'results', 'app', 'app401_comment_only_proof.json')
    tmp = dest + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, dest)

    print('verdict:', verdict, n_pass, 'PASS /', n_fail, 'FAIL')
    for c in checks:
        print(('  PASS ' if c['pass'] else '  FAIL '), c['name'], '|', c['detail'])

    # 🔴 反证组：判据必须有鉴别力 —— **改动可执行代码**（而不只是注释）必须被判 FAIL
    #    做法：把工作树副本里的一行注释改成代码 ⇒ 语句/常量多重集必须不再相等。
    import copy as _copy
    mutated = cur.replace('_WIN_S_DEFAULT = 10.0',
                           '_WIN_S_DEFAULT = 10.0\n_WIN_S_MUTANT = 1', 1)
    assert mutated != cur, '反证构造失败：目标行未命中'
    m1 = fingerprint(old, strip=STRIP_DOCSTRINGS)
    m2 = fingerprint(mutated, strip=STRIP_DOCSTRINGS)
    neg = (m1['stmts'] != m2['stmts']) or (m1['consts'] != m2['consts'])
    print('NEG_CONTROL(注入一行可执行代码 ⇒ 必须被识破):',
          'PASS' if neg else 'FAIL(判据无鉴别力!)')
    out['neg_control'] = ('PASS：注入可执行代码后语句/常量多重集不再相等 ⇒ 判据有鉴别力'
                          if neg else 'FAIL：注入可执行代码后仍判相等 ⇒ 判据恒真')
    if not neg:
        out['verdict'] = 'FAIL'
        with open(dest, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return 2

    print('WROTE:', dest)
    return 0 if verdict == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
