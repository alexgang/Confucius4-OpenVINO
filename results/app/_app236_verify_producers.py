#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 逐条甄别（**AST 优先**）：把 app236_producer_sweep.json 的候选逐条判为
「真生产者」还是「只是提到文件名」。

🔴 判据的坑（初版踩了，已修）：
  ① `^` 不带 re.M 只匹配首行 ⇒ 多行赋值（`OUT = os.path.join(\n  'x.json')`）全漏
  ⇒ 本版改用 **ast** 解析：找「Assign 的值里含该文件名常量」→ 再看该变量
     是否出现在写出调用（json.dump / write_text / to_csv / open(...,'w')）里
  ② AST 解析失败（语法错/非 py）⇒ 退回正则启发式，并标注 verdict=HEURISTIC

判据：
  PRODUCER     ⇒ 该证据文件名是某个输出路径变量的来源，且该变量被写出
  NOT_PRODUCER ⇒ 名字只出现在注释/docstring/普通字符串引用里

🔴 反证组（判据须有鉴别力，不是恒 PASS）：
  R1 注释里的文件名            ⇒ 必须 NOT_PRODUCER
  R2 docstring 里的文件名      ⇒ 必须 NOT_PRODUCER
  R3 json.dump 的输出变量      ⇒ 必须 PRODUCER
  R4 多行 os.path.join 赋值     ⇒ 必须 PRODUCER
  R5 变量赋值但**从不写出**     ⇒ 必须 NOT_PRODUCER
"""
import ast
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WRITE_FUNCS = {'dump', 'writerow', 'writerows', 'write_text', 'write_bytes', 'to_csv'}


def git_ls(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def ast_classify(src, ev_base):
    """返回 (verdict, reason)"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None, 'AST_PARSE_FAILED'
    # 1) 收集：变量名 -> 该赋值语句里是否含 ev_base 常量
    var_with_name = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        consts = [n.value for n in ast.walk(node.value)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        if not any(ev_base in c for c in consts):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                var_with_name[tgt.id] = node
            elif isinstance(tgt, ast.Attribute):
                var_with_name['<attr>.' + tgt.attr] = node
    # 1b) 文件名**字面量**直接出现在 open(...,'w') 的路径参数里
    #     （形如 open(sys.argv[1] if ... else 'x.json', 'w')）
    #     ⇒ 这条必须在 var_with_name 为空的早退**之前**判，否则会漏
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
            mode = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            if mode and ('w' in mode or 'a' in mode):
                for arg in node.args:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                                and ev_base in sub.value:
                            return 'PRODUCER', 'AST：open() 路径参数里直接出现文件名（字面量）'
    if not var_with_name:
        return 'NOT_PRODUCER', 'AST 里没有把该文件名赋给任何变量'
    # 2) 该变量是否出现在写出调用里
    written_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else '')
            if name in WRITE_FUNCS:
                for arg in list(node.args) + [k.value for k in node.keywords]:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Name):
                            written_vars.add(sub.id)
                        elif isinstance(sub, ast.Attribute):
                            written_vars.add(sub.attr)
    hit = [v for v in var_with_name if v in written_vars]
    if hit:
        return 'PRODUCER', 'AST：输出变量 %s 被写出' % ','.join(sorted(hit))
    # 3) 有 `open(x, 'w')` 形式
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
            mode = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            if mode and ('w' in mode or 'a' in mode):
                for arg in node.args:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Name) and sub.id in var_with_name:
                            return 'PRODUCER', 'AST：open(%s, %r) 写出' % (sub.id, mode)
                # 3b) 文件名**字面量**直接出现在 open() 的路径参数里
                #     （形如 open(sys.argv[1] if ... else 'x.json', 'w')）
                for arg in node.args:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                                and ev_base in sub.value:
                            return 'PRODUCER', 'AST：open() 路径参数里直接出现文件名（字面量）'
    return 'NOT_PRODUCER', 'AST：变量 %s 赋值了但从未写出' % ','.join(sorted(var_with_name))


def heuristic_classify(src, ev_base):
    code = []
    in_doc = False
    doc_q = None
    for ln in src.split('\n'):
        s = ln.strip()
        if in_doc:
            if doc_q in s:
                in_doc = False
            continue
        m = re.match(r'^[rRuUbBfF]{0,2}("""|\'\'\')', s)
        if m:
            doc_q = m.group(1)
            in_doc = True
            continue
        if s.startswith('#'):
            continue
        code.append(ln)
    code_nc = re.sub(r'(?<![\'"])#(?![!]).*$', '', '\n'.join(code), flags=re.M)
    if ev_base not in code_nc:
        return 'NOT_PRODUCER', '名字只出现在注释/docstring 里'
    m = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^;]{0,400}?' + re.escape(ev_base),
                  code_nc, re.S)
    if m:
        v = m.group(1)
        if len(re.findall(r'\b' + re.escape(v) + r'\b', code_nc)) >= 2:
            return 'PRODUCER', '启发式：输出变量 %s' % v
    return 'NOT_PRODUCER', '启发式：名字在代码里但不是输出目标'


def classify(src, ev_base):
    v, r = ast_classify(src, ev_base)
    if v is None:
        v2, r2 = heuristic_classify(src, ev_base)
        return v2, r2 + '（AST 失败退回正则）'
    return v, r


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_py_base = {os.path.basename(f) for f in tracked if f.endswith('.py')}

    sweep = json.load(open(os.path.join(REPO, 'results/app/app236_producer_sweep.json'),
                           encoding='utf-8'))
    cands = sweep['detail']
    real, notreal = [], []
    for c in cands:
        p = c['producer'].replace('\\', '/')
        full = os.path.join(REPO, p)
        if not os.path.isfile(full):
            notreal.append({'evidence': c['evidence'], 'producer': p,
                            'producer_committed': False,
                            'verdict': 'SCRIPT_MISSING', 'reason': '磁盘上不存在'})
            continue
        src = open(full, encoding='utf-8', errors='replace').read()
        v, r = classify(src, c['evidence'])
        row = {'evidence': c['evidence'], 'producer': p,
               'producer_committed': os.path.basename(p) in tracked_py_base,
               'verdict': v, 'reason': r}
        (real if v == 'PRODUCER' else notreal).append(row)

    print("=== 真生产者（脚本确实写出该证据文件） ===")
    for r in sorted(real, key=lambda x: x['evidence']):
        flag = 'COMMITTED  ' if r['producer_committed'] else 'NOT_COMMITTED'
        print("  [%s] %s <- %s\n              (%s)" % (flag, r['evidence'], r['producer'], r['reason']))
    gaps = [r for r in real if not r['producer_committed']]
    print()
    print("真生产者且未入库 =", len(gaps))
    for r in gaps:
        print("    ", r['evidence'], "->", r['producer'])

    print()
    print("=== 不是真生产者（只是提到文件名） ===")
    for r in sorted(notreal, key=lambda x: x['evidence']):
        print("  ", r['evidence'], "->", r['producer'], "|", r['verdict'], "|", r['reason'])

    print()
    print("--- counterproof ---")
    cp = []
    cases = [
        ('R1_comment_only', 'NOT_PRODUCER',
         "# 产出 app999_cmt_only.json\nimport json\nprint('hello')\n", 'app999_cmt_only.json'),
        ('R2_docstring_only', 'NOT_PRODUCER',
         '"""产出 app999_doc.json"""\nimport json\nprint(1)\n', 'app999_doc.json'),
        ('R3_json_dump_output', 'PRODUCER',
         "import json\nOUT='app999_dump.json'\nwith open(OUT,'w') as f:\n    json.dump({'a':1}, f)\n",
         'app999_dump.json'),
        ('R4_multiline_join', 'PRODUCER',
         "import os, json\nOUT = os.path.join(os.path.dirname(__file__),\n"
         "                'app999_join.json')\nwith open(OUT,'w') as f:\n    json.dump({'b':2}, f)\n",
         'app999_join.json'),
        ('R5_assigned_but_never_written', 'NOT_PRODUCER',
         "NAME='app999_nowrite.json'\nprint(NAME)\n", 'app999_nowrite.json'),
    ]
    for nm, exp, src, base in cases:
        got, reason = classify(src, base)
        ok = got == exp
        cp.append({'name': nm, 'expect': exp, 'got': got, 'reason': reason, 'ok': ok})
        print("    %-34s 须判 %-13s ⇒ %s (got %s)" % (nm, exp, 'PASS' if ok else 'FAIL', got))
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'real_producers': real, 'not_producers': notreal,
            'real_producer_not_committed': gaps,
            'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_producer_verdict.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_producer_verdict.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
