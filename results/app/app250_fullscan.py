# -*- coding: utf-8 -*-
"""§250 全范围残留扫描（独立复核用；**不改任何文件**）。

§249 的终检只扫了 6 个文本扩展名（.md/.json/.txt/.tsv/.csv/.jsonl）且跳过
`.mt.txt/.tts.jsonl/.transcript.txt` ⇒「残留 0」是**范围受限的假绿**。
本脚本扫**全部 tracked 文件、任意扩展名**，并把命中按性质分类：

  1. ``gt_source``   —— reviewer 的「逐句产物」语料（GT 的来源），按设计含原句
  2. ``reviewer_owned`` —— reviewer 独占文件（只读，绝不修改）
  3. ``doc``         —— 文档/正文类（.md/.txt/.json/... ）⇒ 可定点脱敏
  4. ``code``        —— 源码类（.py 等）⇒ 需逐处判定能否安全改
  5. ``other``       —— 其余扩展名（.bak 等）

两套口径同时给：
  * ``baseline`` —— **reviewer 权威基线**（GT json 的 ``hits`` 里 reviewer 自己记的
    85 条原句）⇒ 判「是不是会议原句」以此为准
  * ``rebuilt``  —— §249 重建的 571 条句（含短通用短语）⇒ 只作补充，不单独定罪

🔴 RULES §0：证据只写 len + sha256 前 8 位 + 分类，**不写原句**。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import subprocess

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
OUT = os.path.join(REPO, "results", "app", "app250_fullscan.json")

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s: str) -> str:
    """§249 apply 逐字同口径：strip → lower → 合并空白 → 去标点。"""
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def norm_map(t: str):
    """归一化字符流 + 每个归一化字符对应的原文下标。

    🔴 **必须逐字复刻 §249 apply 的 ``norm_with_map``**（L78-107）：
    它只丢弃 **PUNCT_RE 里的标点**（逐字符 match），**保留** ``→`` ``**`` `` ` `` 等
    其它符号 ⇒ 若改用「丢掉所有非 \\w 字符」的口径，会把
    ``| ` good` → ` morning` → ` everyone` |`` 这种**表格里被箭头隔开的词**
    错拼成连续短语 ⇒ **假阳性**（本轮实测踩到，见 §250 坑①）。
    """
    out, idx = [], []
    i = 0
    n = len(t)
    while i < n:
        c = t[i]
        if c.isspace() or c == "　":
            j = i
            while j < n and (t[j].isspace() or t[j] == "　"):
                j += 1
            out.append(" ")
            idx.append(i)
            i = j
            continue
        if PUNCT_RE.match(c):
            i += 1
            continue
        out.append(c.lower())
        idx.append(i)
        i += 1
    idx.append(n)          # 哨兵
    return "".join(out), idx


def build_gt(gt):
    """§249 apply 同口径：39 个逐句产物 → 归一化句集合（min_len 过滤）。"""
    sents = set()
    for rel in gt["gt_files"]:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        if rel.endswith(".jsonl"):
            for line in t.splitlines():
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                for k in ("text", "tgt", "src", "zh", "en"):
                    if isinstance(o.get(k), str):
                        sents.add(norm(o[k]))
            continue
        for s in re.split(r"[。！？\n]+|(?<=[.!?])\s+", t):
            if s and s.strip():
                sents.add(norm(s.strip()))
    return {s for s in sents if len(s) >= gt["min_len"]}


def find_spans(text, sents):
    """§249 apply 逐字同口径的命中定位。

    🔴 §249 的 apply 是**逐行**做的（``splitlines(keepends=True)`` 后逐行
    ``norm_with_map(body)``）⇒ 扫描也必须逐行，否则口径不同、比出来的差异无意义。

    返回 [(line_no, start_in_line, end_in_line, sent), ...]（原文坐标，不重叠）。
    """
    out = []
    ordered = sorted(sents, key=len, reverse=True)
    for ln_no, raw in enumerate(text.splitlines(keepends=True), 1):
        m = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", raw, re.S)
        body = m.group(1)
        if not body:
            continue
        nl, imap = norm_map(body)
        if not nl:
            continue
        taken = [False] * len(nl)
        spans = []
        for s in ordered:
            pos = 0
            while True:
                j = nl.find(s, pos)
                if j < 0:
                    break
                end = j + len(s)
                if not any(taken[j:end]):
                    for k in range(j, end):
                        taken[k] = True
                    spans.append((j, end, s))
                pos = j + 1
        if not spans:
            continue
        spans.sort(key=lambda x: x[0])
        for j, end, s in spans:
            a = imap[j]
            b = imap[end - 1] + 1
            while b > a and (body[b - 1].isspace() or body[b - 1] == "　"):
                b -= 1
            while a < b and (body[a].isspace() or body[a] == "　"):
                a += 1
            if a >= b:
                continue
            out.append((ln_no, a, b, s))
    return out


def py_ctx(src, line_no):
    """AST 判定该行所属的语法位置：docstring / comment / string-literal / other。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return "parse-error"
    doc_lines = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and body:
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                a = first.value.lineno
                b = first.value.end_lineno or a
                doc_lines.update(range(a, b + 1))
    lit_lines = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            a = node.lineno
            b = node.end_lineno or a
            lit_lines[(a, b)] = node.value
    covered = [(a, b) for (a, b) in lit_lines if a <= line_no <= b]
    if not covered:
        return "comment"
    a, b = min(covered, key=lambda x: x[1] - x[0])
    if line_no in doc_lines:
        return "docstring"
    return "string-literal"


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    rebuilt = build_gt(gt)

    # reviewer 权威基线：GT json 的 hits 里 reviewer 自己记下的原句
    baseline = {}
    for rel, lst in gt["hits"].items():
        for h in lst:
            t = (h.get("text") or "").strip()
            if t:
                baseline.setdefault(norm(t), []).append((rel, h.get("line")))

    gtset = set(gt["gt_files"])
    reviewer_owned = set(gt.get("reviewer_owned", []))

    tracked = [x for x in subprocess.run(
        ["git", "-C", REPO, "ls-files"], capture_output=True, text=True,
        encoding="utf-8", errors="replace").stdout.splitlines() if x.strip()]

    DOC_EXT = (".md", ".json", ".txt", ".tsv", ".csv", ".jsonl")
    CODE_EXT = (".py", ".pyw", ".sh", ".bat", ".ps1", ".cfg", ".ini", ".toml")

    rows = []
    n_scanned = 0
    for rel in tracked:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        except Exception:
            continue
        if not t:
            continue
        n_scanned += 1
        ext = os.path.splitext(rel)[1].lower()
        if rel in reviewer_owned:
            kind = "reviewer_owned"
        elif rel in gtset:
            kind = "gt_source"
        elif ext in CODE_EXT:
            kind = "code"
        elif ext in DOC_EXT:
            kind = "doc"
        else:
            kind = "other"

        hits = []
        # 口径 A：reviewer 权威基线
        spans = find_spans(t, set(baseline.keys()))
        base_hit = {s[3] for s in spans}
        # 口径 B：§249 重建的 571 条
        spans2 = find_spans(t, rebuilt)
        reb_hit = {s[3] for s in spans2}

        if base_hit or reb_hit:
            # 每条 GT 句取其首次命中的行号
            first_line = {}
            for ln_no, a, b, s in spans + spans2:
                first_line.setdefault(s, ln_no)
            for s in sorted(base_hit | reb_hit, key=len, reverse=True):
                ln = first_line.get(s)
                hits.append({
                    "len": len(s),
                    "sha8": sha8(s),
                    "in_baseline": s in base_hit,
                    "in_rebuilt": s in reb_hit,
                    "line": ln,
                    "ctx": (py_ctx(t, ln) if (kind == "code" and ln) else None),
                })
            rows.append({"file": rel, "kind": kind, "ext": ext,
                         "n_hits": len(hits), "hits": hits})

    # ---- 汇总 ----
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["kind"], {"files": 0, "hits": 0})
        by_kind[r["kind"]]["files"] += 1
        by_kind[r["kind"]]["hits"] += r["n_hits"]

    n_base_files = sum(1 for r in rows if any(h["in_baseline"] for h in r["hits"]))
    n_base_hits = sum(1 for r in rows for h in r["hits"] if h["in_baseline"])
    n_reb_files = sum(1 for r in rows if any(h["in_rebuilt"] for h in r["hits"]))
    n_reb_hits = sum(1 for r in rows for h in r["hits"] if h["in_rebuilt"])

    print("=== §250 全范围扫描 ===")
    print("tracked 文件 %d / 实读 %d" % (len(tracked), n_scanned))
    print("reviewer 权威基线：%d 条原句 / %d 个文件命中 / %d 处"
          % (len(baseline), n_base_files, n_base_hits))
    print("§249 重建口径：%d 条句 / %d 个文件命中 / %d 处"
          % (len(rebuilt), n_reb_files, n_reb_hits))
    print()
    print("按性质分类：")
    for k, v in sorted(by_kind.items()):
        print("  %-16s %4d 文件 / %4d 处" % (k, v["files"], v["hits"]))
    print()
    print("=== 逐文件（只列有命中的）===")
    for r in sorted(rows, key=lambda x: (x["kind"], -x["n_hits"], x["file"])):
        print("  %-16s %-64s %d 处" % (r["kind"], r["file"][:64], r["n_hits"]))

    out = {
        "script": "app250_fullscan.py",
        "method": "全范围（所有 tracked 文件、任意扩展名）＋ reviewer 权威基线/重建双口径",
        "n_tracked": len(tracked),
        "n_scanned": n_scanned,
        "n_baseline_sents": len(baseline),
        "n_baseline_files": n_base_files,
        "n_baseline_hits": n_base_hits,
        "n_rebuilt_sents": len(rebuilt),
        "n_rebuilt_files": n_reb_files,
        "n_rebuilt_hits": n_reb_hits,
        "by_kind": by_kind,
        "rows": rows,
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print("\n写出:", OUT)


if __name__ == "__main__":
    main()
