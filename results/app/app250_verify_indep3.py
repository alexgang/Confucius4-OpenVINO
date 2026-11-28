# -*- coding: utf-8 -*-
"""§250 **独立复核 v3**（最终版；修正 v1/v2 的判据缺陷，从零重算，不复用死会话产物）。

🔴 本脚本的判据演进（每一版都修了上一版的**判据缺陷**，不是产品缺陷）：
 - **v1 缺陷①**：还原映射用「全局 idx→原句」，但同一 idx 在不同文件对应**不同原句**
   ⇒ 还原后对不上 ⇒ 假 FAIL。⇒ v2/v3 改为**逐文件**建映射。
 - **v1 缺陷②**：跑脚本会写自己的 evidence 文件 ⇒ v1 没备份/复原 ⇒ 污染工作树。
   ⇒ v2/v3 加**备份 + 跑后复原**。
 - **v1 缺陷③**：对需要 numpy 的脚本用系统 py 3.13 ⇒ 崩溃 ⇒ before/after 都 rc=1
   ⇒ 「rc 相同」变**空洞恒真**（假 PASS）。⇒ v2/v3 用**包内 .venv python 3.12**。
 - **v2 缺陷④**：evidence 要求**逐字节相等** ⇒ 假 FAIL。真相：evidence 里记的是
   **由语料长度派生的数字**（如 ``src_chars``）⇒ 占位符比原句短 ⇒ 数字必然差
   （本例 −9 ＝ 替换处字符数差）⇒ **这是脱敏的预期后果，不是行为变化**。
   ⇒ v3 改为判**「断言判定（ok 标志 ＋ verdict ＋ n_pass/n_total）」完全相同**，
     并**单独核验**残余数字差**是否恰好等于替换引入的字符数差**（可解释）。
 - **v2 缺陷⑤**：把「脚本崩溃」一律判 FAIL。真相：`diag_c111_half.py` 在**脱敏前后
   都**在同一行抛同一个 AssertionError（**既有缺陷**，与脱敏无关）⇒
   「before/after 行为一致」才是判据 ⇒ v3 改为：崩溃必须**两边完全一致**
   （同 rc ＋ 同末行 traceback），并**如实登记**该既有缺陷。

🔴 §1 口径：**用 reviewer 权威基线句**（73 条）扫**全部 tracked 文件**（子串粒度）；
   GT 源文件按定义含原句 ⇒ **单独统计**，不算「残留」（APP-144 ① 的对象）。

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
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
REDACT = os.path.join(REPO, "results", "app", "app250_redact.json")
BACKUP = r"C:\Users\Trekker-PTL\shared\app250_desen_backup"
VENV_PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
OUT = os.path.join(REPO, "results", "app", "app250_verify_indep3.json")

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")

# §3 登记的豁免点：功能性字面量（改了 ⇒ 断言空洞恒真 ⇒ 假绿）
# 🔴 RULES §0：**这里也不得写会议原句** ⇒ 用「GT 句 len/sha8」指代。
EXEMPT = {
    "results/app/app053_draft_prefix_boundary_probe.py":
        "断言比较操作数：`(finals[fi].get('src') or '') == <GT 句>`"
        "（GT 句 len=15 sha8=9726b63b）"
        "⇒ 换成占位符后恒不等 ⇒ ok_wrong 恒 False ⇒ 空洞恒真（假绿）⇒ 不改",
}

JOBS = [
    ("results/app/app053_draft_prefix_boundary_probe.py", "py",
     "results/app/app053_draft_prefix_boundary_evidence.json"),
    ("results/app/test_app015_caption_render.py", "py",
     "results/app/app015_caption_render_evidence.json"),
    ("results/app/app127_c111_real_timing_draft_lines.py", "venv",
     "results/app/app127_c111_real_timing_draft_lines_evidence.json"),
    ("live_caption/diag_c111_half.py", "venv",
     "results/app/diag_c111_half_evidence.json"),
]


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s: str) -> str:
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def norm_with_map(s: str):
    out, idx = [], []
    i, n = 0, len(s)
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
    return "".join(out), idx


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return [l for l in out.stdout.splitlines() if l.strip()]


def baseline_sents(gt):
    s = set()
    for rel, hs in gt["hits"].items():
        for h in hs:
            t = h.get("text")
            if isinstance(t, str) and t.strip():
                n = norm(t)
                if len(n) >= gt["min_len"]:
                    s.add(n)
    return s


def scan_residual(sents, skip=()):
    hits, n_scanned = {}, 0
    for rel in tracked_files():
        if rel in skip:
            continue
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            text = open(p, "rb").read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        n_scanned += 1
        fh = []
        for ln, line in enumerate(text.splitlines(), 1):
            nl, _ = norm_with_map(line)
            if not nl:
                continue
            for s in sents:
                if s in nl:
                    fh.append({"line": ln, "len": len(s), "sha8": sha8(s)})
                    break
        if fh:
            hits[rel] = fh
    return n_scanned, hits


def diff_check(rel, sents):
    r = subprocess.run(["git", "diff", "--", rel], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    minus, plus = [], []
    for line in r.stdout.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            minus.append(line[1:])
        elif line.startswith("+"):
            plus.append(line[1:])
    if not minus and not plus:
        return {"changed": False}
    m_ok, p_ok = True, True
    md, pd = [], []
    for m in minus:
        nm = norm(m)
        hit = any(s in nm for s in sents)
        md.append({"len": len(m), "sha8": sha8(m), "has_gt": hit})
        if not hit:
            m_ok = False
    for p in plus:
        np_ = norm(p)
        hit = any(s in np_ for s in sents)
        pd.append({"len": len(p), "sha8": sha8(p), "has_gt": hit})
        if hit:
            p_ok = False
    return {"changed": True, "n_minus": len(minus), "n_plus": len(plus),
            "minus_all_have_gt": m_ok, "plus_no_gt": p_ok,
            "minus": md, "plus": pd}


def strip_volatile(txt):
    if txt is None:
        return None
    t = txt
    for pat in (r'"generated_at"\s*:\s*"[^"]*"',
                r'"elapsed_sec"\s*:\s*[0-9.]+',
                r'"elapsed_s"\s*:\s*[0-9.]+',
                r'"elapsed"\s*:\s*[0-9.]+'):
        t = re.sub(pat, '"VOLATILE":0', t)
    return t


def restore(txt, mapping):
    if txt is None:
        return None
    t = txt
    for ph, orig in mapping.items():
        if ph in t:
            t = t.replace(ph, orig)
    return t


def build_file_map(rel, red):
    mapping = {}
    for c in red["changed"]:
        if c["file"] != rel:
            continue
        bak = os.path.join(BACKUP, rel.replace("/", os.sep))
        cur = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(bak) or not os.path.isfile(cur):
            continue
        cur_lines = io.open(cur, encoding="utf-8").read().splitlines()
        bak_lines = io.open(bak, encoding="utf-8").read().splitlines()
        for a in c.get("applied", []):
            idx = a.get("idx")
            if idx is None:
                continue
            ln = a["line"]
            if ln - 1 >= len(cur_lines) or ln - 1 >= len(bak_lines):
                continue
            cl, bl = cur_lines[ln - 1], bak_lines[ln - 1]
            ph = "[会议句 idx %d]" % idx
            if ph not in cl:
                continue
            pre = 0
            while pre < min(len(cl), len(bl)) and cl[pre] == bl[pre]:
                pre += 1
            suf = 0
            while (suf < min(len(cl), len(bl)) - pre
                   and cl[len(cl) - 1 - suf] == bl[len(bl) - 1 - suf]):
                suf += 1
            orig = bl[pre:len(bl) - suf] if suf else bl[pre:]
            if orig.strip():
                mapping.setdefault(ph, orig)
    return mapping


def interp_cmd(kind):
    return [VENV_PY] if kind == "venv" else [sys.executable]


def run_capture(script_rel, kind, evidence_rel):
    r = subprocess.run(interp_cmd(kind) + [script_rel], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    ev = os.path.join(REPO, evidence_rel.replace("/", os.sep))
    ev_txt = None
    if os.path.isfile(ev):
        try:
            ev_txt = io.open(ev, encoding="utf-8").read()
        except Exception:
            ev_txt = None
    return {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
            "evidence": ev_txt}


# ── §4 辅助：evidence 的「断言判定」抽取 ＋ 数字差可解释性核验 ──────
def verdicts_of(ev_txt):
    """抽 evidence 里的**判定**：ok 标志列表 ＋ summary 的 verdict/计数。"""
    if not ev_txt:
        return None
    try:
        d = json.loads(ev_txt)
    except Exception:
        return None
    oks, names = [], []
    for key in ("results", "checks"):
        for r in d.get(key) or []:
            if isinstance(r, dict) and "ok" in r:
                oks.append(bool(r["ok"]))
                names.append(str(r.get("name", ""))[:80])
    summ = d.get("summary") or {}
    keep = {k: v for k, v in summ.items()
            if k in ("verdict", "n_pass", "n_total", "real_pass", "real_fail",
                     "real_total", "bug_total", "bug_hit", "bug_miss")}
    return {"oks": oks, "names": names, "summary": keep}


def numeric_deltas(b_txt, a_txt):
    """比对两个 evidence 的**全部数字**：找出哪些数字变了、变了多少。"""
    if not b_txt or not a_txt:
        return []
    def nums(t):
        return [int(x) for x in re.findall(r'(?<![\w.])(\d+)(?![\w.])', t)]
    bn, an = nums(b_txt), nums(a_txt)
    if len(bn) != len(an):
        return [{"note": "数字个数不同", "n_before": len(bn), "n_after": len(an)}]
    out = []
    for i, (x, y) in enumerate(zip(bn, an)):
        if x != y:
            out.append({"pos": i, "before": x, "after": y, "delta": y - x})
    return out


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    red = json.load(open(REDACT, encoding="utf-8"))
    base = baseline_sents(gt)
    print("reviewer 权威基线句（归一化去重后）: %d 条" % len(base))

    changed = [c["file"] for c in red["changed"]]
    gt_files = set(gt["gt_files"])

    # ── §1 ────────────────────────────────────────────────────
    n_scanned, residual = scan_residual(base, skip=gt_files)
    in_gt = {}
    for rel in gt_files:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            t = open(p, "rb").read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        nl, _ = norm_with_map(t)
        n = sum(1 for s in base if s in nl)
        if n:
            in_gt[rel] = n
    resid_ex = {k: v for k, v in residual.items() if k not in EXEMPT}
    resid_exempt = {k: v for k, v in residual.items() if k in EXEMPT}
    print("§1 扫 %d 个 tracked 文件（排除 %d 个 GT 源）⇒ 残留 %d（豁免外 %d）"
          % (n_scanned, len(gt_files), len(residual), len(resid_ex)))

    # ── §2 ────────────────────────────────────────────────────
    d2 = {rel: diff_check(rel, base) for rel in changed}
    n_d2 = sum(1 for v in d2.values() if v.get("changed")
               and v.get("minus_all_have_gt") and v.get("plus_no_gt"))
    print("§2 diff 法: %d/%d 通过" % (n_d2, len(changed)))

    # ── §3 ────────────────────────────────────────────────────
    d3 = {}
    for rel in changed:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        raw = open(p, "rb").read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            d3[rel] = {"ok": False, "err": "not-utf8"}
            continue
        if rel.endswith(".json"):
            try:
                json.loads(text)
                d3[rel] = {"ok": True, "kind": "json"}
            except Exception as e:
                d3[rel] = {"ok": False, "kind": "json", "err": str(e)[:120]}
        elif rel.endswith(".py"):
            try:
                ast.parse(text)
                d3[rel] = {"ok": True, "kind": "py"}
            except Exception as e:
                d3[rel] = {"ok": False, "kind": "py", "err": str(e)[:120]}
        else:
            d3[rel] = {"ok": True, "kind": "other"}
    n_d3 = sum(1 for v in d3.values() if v.get("ok"))
    print("§3 语法/JSON: %d/%d 通过" % (n_d3, len(changed)))

    # ── §4 行为等价 ────────────────────────────────────────────
    d4, n_d4 = [], 0
    evbak = os.path.join(BACKUP, "_app250_verify_indep3_evbak")
    os.makedirs(evbak, exist_ok=True)
    for rel, kind, ev_rel in JOBS:
        rec = {"script": rel, "interp": kind}
        cur_p = os.path.join(REPO, rel.replace("/", os.sep))
        bak_p = os.path.join(BACKUP, rel.replace("/", os.sep))
        ev_p = os.path.join(REPO, ev_rel.replace("/", os.sep))
        ev_bak = os.path.join(evbak, os.path.basename(ev_rel))
        if os.path.isfile(ev_p):
            shutil.copy2(ev_p, ev_bak)

        have_bak = os.path.isfile(bak_p)
        if have_bak:
            keep = cur_p + ".v3keep"
            shutil.copy2(cur_p, keep)
            shutil.copy2(bak_p, cur_p)
            try:
                before = run_capture(rel, kind, ev_rel)
            finally:
                shutil.copy2(keep, cur_p)
                os.remove(keep)
        else:
            before = None
        after = run_capture(rel, kind, ev_rel)
        if os.path.isfile(ev_bak):
            shutil.copy2(ev_bak, ev_p)

        mapping = build_file_map(rel, red)
        rec.update({"have_backup": have_bak, "n_restore_map": len(mapping)})
        if not have_bak:
            rec.update({"ok": True, "rc_before": None, "rc_after": after["rc"],
                        "note": "文件未被改动（§3 豁免）⇒ 行为必然等价"})
            n_d4 += 1
            d4.append(rec)
            continue

        rec["rc_before"] = before["rc"]
        rec["rc_after"] = after["rc"]
        rec["rc_same"] = before["rc"] == after["rc"]

        b_trace = "Traceback" in (before["stderr"] or "")
        a_trace = "Traceback" in (after["stderr"] or "")
        rec["crashed_before"] = b_trace
        rec["crashed_after"] = a_trace
        # 崩溃必须**两边完全一致**（同 rc ＋ 同末行）
        b_last = (before["stderr"] or "").strip().splitlines()[-1:] or [""]
        a_last = (after["stderr"] or "").strip().splitlines()[-1:] or [""]
        rec["crash_last_line_same"] = (b_last == a_last)
        if b_trace or a_trace:
            rec["crash_pre_existing"] = bool(b_trace and a_trace
                                             and b_last == a_last
                                             and before["rc"] == after["rc"])

        b_out = strip_volatile(before["stdout"])
        a_out = strip_volatile(after["stdout"])
        rec["stdout_equal_raw"] = (b_out == a_out)
        rec["stdout_equal_restored"] = (b_out == restore(a_out, mapping))
        b_err = strip_volatile(before["stderr"])
        a_err = strip_volatile(after["stderr"])
        rec["stderr_equal_restored"] = (b_err == restore(a_err, mapping))

        # evidence：判**断言判定**相同（不是逐字节）
        vb = verdicts_of(before["evidence"])
        va = verdicts_of(after["evidence"])
        rec["evidence_verdicts_same"] = (vb == va)
        if vb and va:
            rec["n_assertions"] = len(vb["oks"])
            rec["n_ok_true_before"] = sum(1 for x in vb["oks"] if x)
            rec["n_ok_true_after"] = sum(1 for x in va["oks"] if x)
        # 残余数字差 ⇒ 必须**恰好**等于替换引入的字符数差（可解释）
        # 🔴 先**还原占位符**再比数字：占位符自带数字（`idx 55`）⇒ 不还原会把
        #    「占位符的数字」误当成「数字个数变化」⇒ 假 FAIL（app127 实测）。
        b_ev = strip_volatile(before["evidence"])
        a_ev_r = restore(strip_volatile(after["evidence"]), mapping)
        deltas = numeric_deltas(b_ev, a_ev_r)
        # 替换引入的**净字符数减少量**＝（原句长度 − 占位符长度）之和
        exp_shrink = 0
        for ph, orig in mapping.items():
            exp_shrink += len(orig) - len(ph)
        uniq_deltas = sorted({d.get("delta") for d in deltas if "delta" in d})
        rec["evidence_numeric_deltas"] = deltas[:20]
        rec["expected_char_shrink"] = exp_shrink
        # 判据：① 还原后**完全没有**数字差 ⇒ 最强证据；或
        #       ② 每个数字差都**恰好**等于 −exp_shrink（即字符数减少量）
        rec["numeric_deltas_explainable"] = (
            (not deltas)
            or (exp_shrink != 0 and uniq_deltas == [-exp_shrink]))
        rec["ok"] = bool(rec["rc_same"] and rec["stdout_equal_restored"]
                         and rec["stderr_equal_restored"]
                         and rec["evidence_verdicts_same"]
                         and rec["numeric_deltas_explainable"]
                         and (not b_trace or rec.get("crash_pre_existing")))
        if rec["ok"]:
            n_d4 += 1
        d4.append(rec)
        print("   §4 %-58s ok=%s rc=%s/%s" % (rel[-58:], rec["ok"],
                                             rec["rc_before"], rec["rc_after"]))

    result = {
        "script": "app250_verify_indep3.py",
        "note": "独立复核 v3（最终版）：修正 v1/v2 的 5 处判据缺陷；从零重算，不复用死会话产物",
        "n_baseline_sents": len(base),
        "n_tracked": len(tracked_files()),
        "sec1_residual": {
            "criterion": "reviewer 权威基线句 × 全部 tracked 文件（子串粒度）；GT 源文件按定义含原句⇒单独统计",
            "n_scanned": n_scanned,
            "n_gt_source_files": len(gt_files),
            "n_gt_source_still_with_sents": len(in_gt),
            "gt_source_detail": in_gt,
            "n_residual_all": len(residual),
            "n_residual_wo_exempt": len(resid_ex),
            "files_wo_exempt": resid_ex,
            "residual_in_exempt": resid_exempt,
            "exempt": EXEMPT,
            "pass": len(resid_ex) == 0,
        },
        "sec2_diff": {"per_file": d2, "n_pass": n_d2, "n_total": len(changed),
                      "pass": n_d2 == len(changed)},
        "sec3_syntax": {"per_file": d3, "n_pass": n_d3, "n_total": len(changed),
                        "pass": n_d3 == len(changed)},
        "sec4_behavior": {
            "criterion": "① rc 相同 ② stdout/stderr 占位符还原后逐字节相等 "
                         "③ evidence 的断言判定（ok 标志/verdict/计数）全同 "
                         "④ 残余数字差恰等于替换引入的字符数差 "
                         "⑤ 崩溃须 before/after 完全一致（既有缺陷如实登记）",
            "rows": d4, "n_pass": n_d4, "n_total": len(JOBS),
            "pass": n_d4 == len(JOBS)},
    }
    result["all_pass"] = all(result[k]["pass"] for k in
                              ("sec1_residual", "sec2_diff", "sec3_syntax",
                               "sec4_behavior"))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print("\n总判定：", "ALL PASS" if result["all_pass"] else "HAS FAIL")
    print("写出:", OUT)


if __name__ == "__main__":
    main()
