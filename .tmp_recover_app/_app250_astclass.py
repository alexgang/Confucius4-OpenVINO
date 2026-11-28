# -*- coding: utf-8 -*-
"""§250 AST 分类：把 12 个文件 / 18 处命中，按**语法位置**分类。

分类：
  docstring      ⇒ 纯文档（改它不影响任何运行行为）
  comment        ⇒ 注释（不影响运行行为）
  string-literal ⇒ **运行期字符串字面量**（改它会改变程序输出/比较结果）
  code-other     ⇒ 代码表达式里的片段

🔴 用途：决定「哪些可以直接脱敏、哪些会改行为」。
🔴 RULES §0：不输出原句，只输出 sha8/len/分类。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
PYGAP = os.path.join(REPO, "results", "app", "app250_pygap.json")
OUT = os.path.join(REPO, "results", "app", "app250_astclass.json")


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def main():
    gap = json.load(open(PYGAP, encoding="utf-8"))
    rows = []
    for rel in sorted(gap["hits"]):
        p = os.path.join(REPO, rel.replace("/", os.sep))
        src = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            print("  [PARSE FAIL] %s: %s" % (rel, e))
            continue

        # 收集每个字符串字面量的位置
        docstrings = set()
        lit_lines = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                ln = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None)
                if ln is None:
                    continue
                # docstring 判定：该节点是 Module/ClassDef/FunctionDef 的第一个语句
                for holder in (tree,):
                    pass
                lit_lines.setdefault((ln, end), []).append(node.value)
        # 标出 docstring
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)) and body:
                first = body[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstrings.add((first.value.lineno, first.value.end_lineno))

        for h in gap["hits"][rel]:
            ln = h["line"]
            # 找包含该行的字符串字面量
            found = None
            for (a, b), vals in lit_lines.items():
                if a <= ln <= (b or a):
                    found = (a, b, vals)
                    break
            if found:
                a, b, vals = found
                kind = "docstring" if (a, b) in docstrings else "string-literal"
                # 该字面量是否**包含**命中的 GT 句（而非被 GT 句包含）
                gt_sha = h["gt_sha8"]
                exact = any(sha8(v) == gt_sha for v in vals)
                rows.append({"file": rel, "line": ln, "kind": kind,
                             "lit_lines": [a, b], "n_lit": len(vals),
                             "gt_sha8": gt_sha, "gt_len": h["gt_len"],
                             "lit_exact_gt": exact,
                             "lit_lens": [len(v) for v in vals]})
            else:
                rows.append({"file": rel, "line": ln, "kind": "comment",
                             "lit_lines": None, "n_lit": 0,
                             "gt_sha8": h["gt_sha8"], "gt_len": h["gt_len"],
                             "lit_exact_gt": False, "lit_lens": []})

    print("=== AST 分类结果 ===")
    from collections import Counter
    print(dict(Counter(r["kind"] for r in rows)))
    print()
    for r in rows:
        print("  %-56s L%-5d %-16s lit=%-9s gt_len=%-3d lit_exact_gt=%s"
              % (r["file"][:56], r["line"], r["kind"],
                 str(r["lit_lines"]), r["gt_len"], r["lit_exact_gt"]))

    dst = OUT
    tmp = dst + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"script": "_app250_astclass.py", "rows": rows}, fh,
                  ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    print("\n写出:", dst)


if __name__ == "__main__":
    main()
