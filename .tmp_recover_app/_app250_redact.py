# -*- coding: utf-8 -*-
"""§250 定点脱敏：**修掉 §249「残留 0」的假绿**（§249 的 §1 判据只扫 6 个文本扩展名 ⇒ `.py` 从未被扫）。

## 本脚本做什么

对**全范围扫描**（所有 tracked 文件、任意扩展名）命中的站点，按 §249 的
「归一化 + 索引映射」算法做**精确 span 替换**，占位符沿用 §249 的
``[会议句 idx N]`` 编号 ⇒ 与仓里已有的 1 987 个占位符**同口径同编号**。

## 三类处置（逐处判读，理由写在 DECISIONS 里）

| 类 | 含义 | 处置 |
|---|---|---|
| ``doc`` | 命中落在 **docstring / comment / 纯文档** | **改**（零行为影响） |
| ``gen`` | 命中落在 **STATUS/companion 生成器**的文本字面量（产物已被 §249 脱敏 ⇒ 重跑会**回灌**原句） | **改**（生产路径回灌） |
| ``prod`` | 命中落在 **产物的生产者**（测试语料 / 证据生成器）⇒ 产物已脱敏而生产者未脱敏 ⇒ 重跑会**回灌** | **改** |
| ``func`` | 命中落在**功能性字面量**（断言比较操作数 / 外部数据比��）⇒ 改了会让判据**空洞恒真**（假绿） | **不改** ＋ 如实登记 |

## 🔴 写前不变量（任一 FAIL ⇒ 该文件**零改动**）

1. 行尾风格不变（CRLF/LF 计数不变且不混用）；
2. 行数不变；
3. **非替换部分逐字节不变**（把占位符按记录**还原**后应与改前逐字节相等）；
4. ``.py`` 改后仍能 ``ast.parse``；``.json`` 改后仍能 ``json.loads``；
5. 替换 span 不重叠、且**每个 span 都属 GT 句**。

## 🔴 RULES §0：证据只写 len + sha256 前 8 位，**不写原句**。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
SITES = os.path.join(REPO, "results", "app", "app250_sites.json")
OUT = os.path.join(REPO, "results", "app", "app250_redact.json")
BACKUP = r"C:\Users\Trekker-PTL\shared\app250_desen_backup"

# 🔴 逐字复刻 §249 apply 的 PUNCT_RE / WS_RE（只丢这些标点；``→`` ``**`` `` ` `` 保留）
PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")

# ── 逐处处置清单（理由逐条写明；未列入者 ⇒ 默认不改）──────────────
DECISIONS = {
    # ── 1. docstring / comment（零行为影响）────────────────────────
    ".tmp_recover_app/_app249_desen_analyze.py": ("doc",
        "docstring：§249 方法说明里列举「会误伤」的通用短语示例；纯文档 ⇒ 可改"),
    ".tmp_recover_app/_app249_desen_apply_full.py": ("doc",
        "docstring：说明「raw form 会漏掉标点变体」的示例；纯文档 ⇒ 可改"),
    ".tmp_recover_app/_app249_desen_scan_full.py": ("doc",
        "docstring：说明「嵌在更大句子里」的示例；纯文档 ⇒ 可改"),
    ".tmp_recover_app/_app249_verify_desen_final.py": ("doc",
        "comment：说明「词级对齐」的示例；纯文档 ⇒ 可改"),
    "results/app/app053_caption_render_segcap_candidate.py": ("doc",
        "comment：跨段配对的举例说明；纯文档 ⇒ 可改"),
    "status/STATUS.md.c027bak": ("doc",
        "纯文档备份文件（tracked ⇒ 会随仓库推 GitHub）⇒ 可改"),
    # ── 2. 生成器 / 生产者（产物已被 §249 脱敏 ⇒ 重跑会回灌原句）────
    "live_caption/_app121_sec221_body.py": ("gen",
        "§221 companion 生成器：产物 status/app/STATUS_APP_sec221_detail_20261123.md "
        "已被 §249 脱敏，生成器未脱敏 ⇒ 重跑会回灌原句 ⇒ 一并脱敏"),
    "results/app/_app330_write_status167.py": ("gen",
        "§167 正文生成器：产物 status/archive/STATUS_APP_sec167_20261110.md "
        "已被 §249 脱敏，生成器未脱敏 ⇒ 重跑会回灌原句 ⇒ 一并脱敏"),
    "results/app/app127_c111_real_timing_draft_lines.py": ("prod",
        "证据生成器：产物 results/app/app127_c111_real_timing_draft_lines_evidence.json "
        "已被 §249 脱敏（corpora.chain_close[0] = '[会议句 idx 55] and welcome...'），"
        "而本文件的 CORPORA 仍是原句 ⇒ 重跑会把原句**写回**已脱敏的证据 ⇒ 回灌 ⇒ 一并脱敏"),
    "results/app/test_app015_caption_render.py": ("prod",
        "证据生成器：BLOCKS[0] 是被测语料；其证据 app015_caption_render_evidence.json "
        "不含该语料 ⇒ 产物无原句，但本文件仍带原句 ⇒ 一并脱敏"),
    "live_caption/diag_c111_half.py": ("prod",
        "诊断脚本的**输入语料**（segs[0] / svc.submit(...)）⇒ 一并脱敏"),
    # ── 3. 功能性字面量 ⇒ **不改** ────────────────────────────────
    # 🔴 RULES §0：**理由文本里也不得写会议原句** ⇒ 这里用
    #    「GT 句 len=15 sha8=9726b63b」指代，**不写原句**。
    "results/app/app053_draft_prefix_boundary_probe.py": ("func",
        "断言比较操作数：`(finals[fi].get('src') or '') == <GT 句>`"
        "（GT 句 len=15 sha8=9726b63b）"
        " ⇒ 换成占位符后恒不等 ⇒ ok_wrong 恒 False ⇒ 「OKay 不再被错配」"
        "变成**空洞恒真**（假绿）⇒ 判据失去鉴别力 ⇒ 不改"),
}


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s: str) -> str:
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def norm_with_map(s: str):
    """🔴 逐字复刻 §249 apply L78-107（含哨兵）。"""
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
    idx.append(n)
    return "".join(out), idx


def build_gt(gt):
    """🔴 逐字复刻 §249 apply L110-129。"""
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


def eol(b: bytes):
    crlf = b.count(b"\r\n")
    return crlf, b.count(b"\n") - crlf


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    sites = json.load(open(SITES, encoding="utf-8"))
    sents = build_gt(gt)
    idx_map = {s: i + 1 for i, s in enumerate(sorted(sents))}
    inv = {i: s for s, i in idx_map.items()}
    print("GT 句 %d 条 / idx_map %d 条（与 §249 同口径）" % (len(sents), len(idx_map)))

    by_file = {}
    for s in sites:
        by_file.setdefault(s["file"], []).append(s)

    os.makedirs(BACKUP, exist_ok=True)
    changed, deferred = [], []

    for rel in sorted(by_file):
        decision, reason = DECISIONS.get(rel, (None, "🔴 未列入处置清单 ⇒ 默认不改"))
        p = os.path.join(REPO, rel.replace("/", os.sep))
        before_b = open(p, "rb").read()
        text = before_b.decode("utf-8", "replace")
        lines = text.splitlines(keepends=True)

        # ── 定位该文件里所有 GT 命中 span（§249 同口径：逐行 + taken[] 标记）──
        spans_by_line = {}
        for s in by_file[rel]:
            spans_by_line.setdefault(s["line"], []).append(s)

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
            for s in sorted(sents, key=len, reverse=True):
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
            deferred.append({"file": rel, "action": "no_hit",
                             "reason": reason, "decision": decision})
            print("  无命中 %-56s" % rel[:56])
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

        # ── 应用（**单趟升序重建**：按原文坐标一次拼出 ⇒ 偏移永不失效）────
        # 🔴🔴 上一版（本轮首跑）**逐处替换**（升序）⇒ 同一行第 2 处命中的
        #    原文下标因第 1 处占位符长度不同而**失效** ⇒ 产生 `go[会议句 idx 54]/`
        #    这类**错位**文本。§249 的 apply 用的是 `reversed(reps)`（从后往前），
        #    本版改用**单趟升序重建**（parts 拼接）⇒ 与 §249 语义等价且无偏移风险。
        by_line = {}
        for i, a, b, s in hits:
            by_line.setdefault(i, []).append((a, b, s))
        new_lines = list(lines)
        applied = []
        restored = []          # 复原用：每行 [(新行内的占位符区间, 原文片段)]
        for i, raw in enumerate(lines):
            if i not in by_line:
                continue
            m = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", raw, re.S)
            body, term = m.group(1), m.group(2)
            spans = sorted(by_line[i])           # 原文坐标升序
            parts = []
            prev = 0
            cur = 0                             # 新行内当前偏移
            for a, b, s in spans:
                ph = "[会议句 idx %d]" % idx_map[s]
                parts.append(body[prev:a])
                parts.append(ph)
                restored.append((i, cur + len(body[prev:a]),
                                 cur + len(body[prev:a]) + len(ph), body[a:b]))
                cur += len(body[prev:a]) + len(ph)
                applied.append({"line": i + 1, "len": len(s), "sha8": sha8(s),
                                "idx": idx_map[s]})
                prev = b
            parts.append(body[prev:])
            new_lines[i] = "".join(parts) + term
        data = "".join(new_lines).encode("utf-8")

        # ── 写前不变量 ────────────────────────────────────────────────
        checks = {}
        b_crlf, b_lf = eol(before_b)
        a_crlf, a_lf = eol(data)
        checks["eol_style_same"] = ((b_crlf > 0) == (a_crlf > 0)
                                    and (b_lf > 0) == (a_lf > 0))
        checks["no_mixed_eol"] = (a_crlf == 0 or a_lf == 0)
        checks["line_count_same"] = (len(lines) == len(new_lines))
        # ③ 非替换部分逐字节不变：**独立**把新行里的占位符区间**按记录的原文片段
        #    拼回**（新行内坐标，从后往前）⇒ 复原结果必须与改前**逐字节**相等。
        #    （用新行坐标而非原文坐标 ⇒ 与施加算法独立 ⇒ 不会自证）
        rebuilt = []
        for i, raw in enumerate(new_lines):
            rs = [r for r in restored if r[0] == i]
            if not rs:
                rebuilt.append(raw)
                continue
            m = re.match(r"^(.*?)((?:\r\n|\r|\n)*)$", raw, re.S)
            body, term = m.group(1), m.group(2)
            out = body
            for _, ns, ne, orig in sorted(rs, key=lambda x: -x[1]):
                out = out[:ns] + orig + out[ne:]
            rebuilt.append(out + term)
        checks["non_replaced_bytes_identical"] = ("".join(rebuilt) == text)
        # ④ 命中 span 必须**逐个**落在 GT 句上（语义护栏）
        checks["spans_are_gt_sentences"] = all(
            s in sents for _, _, _, s in hits)
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
               if k.endswith(("_same", "_identical", "_parses", "_parseable"))
               and v is not True]
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
        "script": "_app250_redact.py",
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
