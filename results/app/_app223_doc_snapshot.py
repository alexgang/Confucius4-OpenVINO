# -*- coding: utf-8 -*-
"""_app223_doc_snapshot.py —— 抓取文件里**所有 docstring** 的原始字面值。

🔴 目的：把某个 docstring 改成 raw 字符串时，
  - **无效转义**（`\\S` / `\\_` / `\\p` / `\\|` 等）本来就被 Python **原样保留**
    （只是会打印 SyntaxWarning）⇒ 改成 raw 后**渲染文本不变**；
  - **有效转义**（`\\n` / `\\t` / `\\\\` / `\\x` / `\\u`）会变成字面量 ⇒ 渲染文本**会变**。
⇒ 所以改之前必须先确认目标 docstring **没有有效转义**，改之后用 sha256 复核。

用法：
    python results/app/_app223_doc_snapshot.py <file.py> ...
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys

VALID = ('\\n', '\\t', '\\r', '\\\\', '\\x', '\\u', '\\b', '\\f', '\\v',
         '\\a', '\\0')


def docstrings(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if not (isinstance(node, (ast.Module, ast.FunctionDef,
                                  ast.AsyncFunctionDef, ast.ClassDef))):
            continue
        body = getattr(node, 'body', None)
        if not body:
            continue
        first = body[0]
        if not (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        if isinstance(node, ast.Module):
            name = '<module>'
        else:
            name = getattr(node, 'name', '?')
        d = first.value.value
        out.setdefault(name, []).append(dict(
            lineno=first.lineno,
            chars=len(d),
            sha256=hashlib.sha256(d.encode('utf-8')).hexdigest(),
            valid_escapes=[e for e in VALID if e in d],
        ))
    return out


def main():
    out = {}
    for p in sys.argv[1:]:
        out[p] = docstrings(p)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
