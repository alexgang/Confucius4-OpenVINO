# -*- coding: utf-8 -*-
"""§250 定点脱敏补丁：**修掉 §249 的「残留 0」假绿**（范围只扫 6 个文本扩展名）。

§249 的终检 §1 判据是「逐行子串扫描（1 251 个文件）」，但它的
``TEXT_EXT = ('.md','.json','.txt','.tsv','.csv','.jsonl')`` ⇒
**``.py`` / ``.bak`` 从未被扫过** ⇒「残留 0」是**范围受限的假绿**。
本轮用**全范围扫描**（所有 tracked 文件、任意扩展名）拿到真实残留清单，
再按下面的三类处置逐处处理。

## 三类处置（判据 = 「改了会不会让判据失去鉴别力」）

1. **改（纯文档）**：命中落在 **docstring / comment** ⇒ 零行为影响。
2. **改（文档生成器）**：命中落在 **STATUS/companion 生成器**的文本字面量
   ⇒ 产物已脱敏而生成器未脱敏 ⇒ **重跑会回灌原句**（§234/§249 同类缺陷）。
3. **不改 + 如实登记**：命中落在**功能性字面量**
   （测试语料 / **断言比较操作数**）⇒ 改了会让断言**空洞恒真**（假绿）
   或改掉测试语义 ⇒ 登记理由 + 证据。

## 替换算法：**逐字复用 §249 apply 的 ``norm_with_map`` + 逐行 taken[] 标记**
⇒ 与仓里已有的 1 991 个占位符**同口径同编号**（``[会议句 idx N]``）。

🔴 写前不变量（任一 FAIL ⇒ 该文件**零改动**）：
  ① 行尾风格不变（CRLF/LF 计数不变且不混用）；
  ② 行数不变；
  ③ 非替换部分**逐字节**不变（把占位符按序还原后应与改前逐字节相等）；
  ④ ``.py`` 改后仍能 ``ast.parse``；``.json`` 改后仍能 ``json.loads``。

🔴 RULES §0：证据只写 len + sha256 前 8 位，**不写原句**。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
FULLSCAN = os.path.join(REPO, "results", "app", "app250_fullscan.json")
OUT = os.path.join(REPO, "results", "app", "app250_patch.json")
BACKUP = r"C:\Users\Trekker-PTL\shared\app250_desen_backup"

# 🔴 逐字复刻 §249 apply 的 PUNCT_RE（只丢这些标点；``→`` ``**`` `` ` `` 保留）
PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")
PLACEHOLDER_RE = re.compile(r"\[会议句 idx (\d+)\]")

# ── 处置清单（由本轮逐处判读得出，理由逐条写在 reasons 里）──────────────
#   "doc"   ⇒ 改（docstring / comment / 纯文档文件）
#   "gen"   ⇒ 改（STATUS/companion 生成器的文本字面量）
#   "func"  ⇒ **不改**（功能性字面量：测试语料 / 断言比较操作数）
DECISIONS = {
    # ── 1. docstring / comment（零行为影响）────────────────────────────
    ".tmp_recover_app/_app249_desen_analyze.py": ("doc",
        "docstring：§249 方法说明里列举「会误伤」的通用短语示例；纯文档 ⇒ 可改"),
    ".tmp_recover_app/_app249_desen_apply_full.py": ("doc",
        "docstring：说明「raw form 会漏标点变体」的示例；纯文档 ⇒ 可改"),
    ".tmp_recover_app/_app249_desen_scan_full.py": ("doc",
        "docstring：说明「嵌在更大句子里」的示例；纯文档 ⇒ 可改"),
    ".tmp_recover_app/_app249_verify_desen_final.py": ("doc",
        "comment：说明「词级对齐」的示例；纯文档 ⇒ 可改"),
    # ── 2. 文档生成器（产物已脱敏 ⇒ 重跑会回灌原句）──────────────────
    "live_caption/_app121_sec221_body.py": ("gen",
        "§221 companion 生成器：产物 status/app/STATUS_APP_sec221_detail_20261123.md "
        "已被 §249 脱敏，生成器未脱敏 ⇒ 重跑会回灌原句 ⇒ 一并脱敏"),
    "results/app/_app330_write_status167.py": ("gen",
        "§167 正文生成器：产物 status/archive/STATUS_APP_sec167_20261110.md "
        "已被 §249 脱敏，生成器未脱敏 ⇒ 重跑会回灌原句 ⇒ 一并脱敏"),
    # ── 3. 纯文档备份文件 ────────────────────────────────────────────
    "status/STATUS.md.c027bak": ("doc",
        "纯文档备份文件（tracked ⇒ 会随仓库推 GitHub）⇒ 可改"),
    # ── 4. 功能性字面量 ⇒ **不改** ───────────────────────────────────
    "results/app/app053_draft_prefix_boundary_probe.py": ("func",
        "断言比较操作数：`(finals[fi].get('src') or '') == '<会议句>'` "
        "⇒ 换成占位符后恒不等 ⇒ ok_wrong 恒 False ⇒ 「OKay 不再被错配」"
        "变成**空洞恒真**（假绿）⇒ 判据失去鉴别力 ⇒ 不改"),
    "results/app/app127_c111_real_timing_draft_lines.py": ("func",
        "测试语料（CORPORA['chain_close'] 首句）⇒ 语料本身是被测对象，"
        "改了会改测试语义 ⇒ 不改"),
    "results/app/test_app015_caption_render.py": ("func",
        "测试语料（BLOCKS 首句）⇒ 语料本身是被测对象 ⇒ 不改"),
    "live_caption/diag_c111_half.py": ("func",
        "诊断脚本的**输入语料**（segs[0] / submit(...)）⇒ 改了会改诊断语义 ⇒ 不改"),
}


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s: str) -> str:
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def norm_with_map(s: str):
    """🔴 逐字复刻 §249 apply L78-107。"""
    out, idx = [], []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace() or c == "　":
            j = i
            while j < n and (s[j].isspace() or s[j] == "　"):
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
    """§249 apply L110-129 逐字同口径。"""
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


def py_line_kinds(src):
    """AST 判定每一行属于 docstring / string-literal / comment。"""
    kinds = {}
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return kinds, "parse-error:%s" % e
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
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            a = node.lineno
            b = node.end_lineno or a
            for ln in range(a, b + 1):
                kinds.setdefault(ln, "string-literal")
    for ln in doc_lines:
        kinds[ln] = "docstring"
    return kinds, None


def eol(b: bytes):
    crlf = b.count(b"\r\n")
    return crlf, b.count(b"\n") - crlf


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    fs = json.load(open(FULLSCAN, encoding="utf-8"))
    sents = build_gt(gt)
    idx_map = {s: i + 1 for i, s in enumerate(sorted(sents))}
    ordered = sorted(sents, key=len, reverse=True)

    os.makedirs(BACKUP, exist_ok=True)
    changed, deferred = [], []

    # 目标 = 全范围扫描里 kind != gt_source / reviewer_owned 的文件
    targets = [r["file"] for r in fs["rows"]
               if r["kind"] not in ("gt_source", "reviewer_owned")]

    for rel in sorted(targets):
        decision, reason = DECISIONS.get(rel, (None, "🔴 未列入处置清单 ⇒ 默认不改"))
        p = os.path.join(REPO, rel.replace("/", os.sep))
        before_b = open(p, "rb").read()
        text = before_b.decode("utf-8")
        lines = text.splitlines(keepends=True)

        # ── 定位该文件里所有 GT 命中 span（§249 同口径：逐行 + taken[] 标记）──
        hits = []          # (line_idx, a, b, sent)
        for i, raw in enumerate(lines):
            m = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", raw, re.S)
            body, term = m.group(1), m.group(2)
            if not body:
                continue
            nl, imap = norm_with_map(body)
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
                hits.append((i, a, b, s))

        if not hits:
            deferred.append({"file": rel, "action": "no_hit", "reason": reason})
            continue

        if decision is None or decision == "func":
            deferred.append({
                "file": rel, "action": "keep", "decision": decision or "none",
                "n_hits": len(hits),
                "hits": [{"line": i + 1, "len": len(s), "sha8": sha8(s)}
                         for i, a, b, s in hits],
                "reason": reason,
            })
            print("  保留 %-56s %d 处（%s）" % (rel[:56], len(hits), decision))
            continue

        # ── 应用（逐行内从后往前替换 ⇒ 下标不失效）─────────────────────
        new_lines = list(lines)
        applied = []
        # 每行记录 (新行内起点, 新行内终点, 原文本) ⇒ 用于**精确**复原校验
        splice = {}
        for i, a, b, s in hits:
            raw = new_lines[i]
            m = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", raw, re.S)
            body, term = m.group(1), m.group(2)
            old_body = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", lines[i], re.S).group(1)
            ph = "[会议句 idx %d]" % idx_map[s]
            new_body = body[:a] + ph + body[b:]
            new_lines[i] = new_body + term
            splice.setdefault(i, []).append((a, a + len(ph), old_body[a:b]))
            applied.append({"line": i + 1, "len": len(s), "sha8": sha8(s),
                            "idx": idx_map[s]})
        data = "".join(new_lines).encode("utf-8")

        # ── 写前不变量 ────────────────────────────────────────────────
        checks = {}
        b_crlf, b_lf = eol(before_b)
        a_crlf, a_lf = eol(data)
        checks["eol_style_same"] = ((b_crlf > 0) == (a_crlf > 0)
                                    and (b_lf > 0) == (a_lf > 0))
        checks["no_mixed_eol"] = (a_crlf == 0 or a_lf == 0)
        checks["line_count_same"] = (len(lines) == len(new_lines))
        # ③ 非替换部分逐字节不变：把新行里被替换的区间**按原文本拼回**，
        #    复原结果必须与改前**逐字节**相等（精确到偏移，不靠 find 猜）
        rebuilt = []
        for i, raw in enumerate(new_lines):
            if i not in splice:
                rebuilt.append(raw)
                continue
            m = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", raw, re.S)
            body, term = m.group(1), m.group(2)
            out = body
            for ns, ne, orig in sorted(splice[i], key=lambda x: -x[0]):
                out = out[:ns] + orig + out[ne:]
            rebuilt.append(out + term)
        checks["non_replaced_bytes_identical"] = ("".join(rebuilt) == text)
        if rel.endswith(".py"):
            try:
                ast.parse(data.decode("utf-8"))
                checks["py_still_parses"] = True
            except SyntaxError as e:
                checks["py_still_parses"] = False
                checks["py_error"] = str(e)
        if rel.endswith(".json"):
            try:
                json.loads(data.decode("utf-8"))
                checks["json_still_parseable"] = True
            except Exception as e:
                checks["json_still_parseable"] = False
                checks["json_error"] = str(e)

        bad = [k for k, v in checks.items()
               if k.endswith(("_same", "_identical", "_parses", "_parseable")) and v is not True]
        if bad:
            deferred.append({"file": rel, "action": "invariant_failed",
                             "failed": bad, "checks": checks, "reason": reason})
            print("  ⛔ 不变量失败 %-40s %s" % (rel[:40], bad))
            continue

        # ── 备份 + 原子落盘 ───────────────────────────────────────────
        bkp = os.path.join(BACKUP, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(bkp), exist_ok=True)
        shutil.copy2(p, bkp)
        tmp = p + ".app250tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(data.decode("utf-8"))
        os.replace(tmp, p)

        # ── 写后独立读回复核 ─────────────────────────────────────────
        rb = open(p, "rb").read()
        checks["readback_identical"] = (rb == data)
        changed.append({
            "file": rel, "decision": decision, "reason": reason,
            "n_repl": len(applied), "applied": applied,
            "bytes_before": len(before_b), "bytes_after": len(data),
            "checks": checks, "backup": bkp,
        })
        print("  改 %-56s %d 处" % (rel[:56], len(applied)))

    print()
    print("已改 %d 个文件 / %d 处；保留或登记 %d 项"
          % (len(changed), sum(c["n_repl"] for c in changed), len(deferred)))
    out = {
        "script": "app250_patch_desen.py",
        "method": "全范围扫描 + §249 apply 同口径（逐行 norm_with_map + taken[] 标记）"
                  " ⇒ 精确替换命中 span；占位符 [会议句 idx N] 沿用 §249 编号",
        "n_gt": len(sents),
        "n_changed_files": len(changed),
        "n_replacements": sum(c["n_repl"] for c in changed),
        "changed": changed,
        "deferred": deferred,
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print("写出:", OUT)


if __name__ == "__main__":
    main()
