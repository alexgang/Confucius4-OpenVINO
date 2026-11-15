#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app570_minimvp_acceptance_gate_matrix.py —— MiniMVP 出包闸门**鉴别力矩阵**。

🔴 **为什么要有这个脚本**（2026-11-15 巡检，§207）：
  MiniMVP 的出包闸门（`_app524_build_minimvp_rc11.py::make_zip`）改前只做了
  ① 证据文件存在 ② `verdict == 'PASS'`（精确字符串）⇒
     **不绑包身份**（别的包的 PASS 证据也能出包）＋
     **不绑包内容**（验收后改包照样能出包）＋
     **口径脆**（reviewer 的「PASS（有 1 项未结：…）」会被误判成 FAIL）。
  §205／§206 在 **Special MVP** 路径上修过同类缺陷，但**没碰 MiniMVP 路径**。

🔴 **鉴别力怎么做的**（不是「我写了个判据」）：
  · **改前臂** = `git cat-file blob HEAD:results/app/_app524_build_minimvp_rc11.py`
    的**逐字原文** ⇒ 用 AST 抽出 `make_zip` 开头那三条闸门语句，
    **原样 unparse 后 exec**（不 import 被测模块、不执行模块主体）；
  · **改后臂** = 工作树里修好的 `check_acceptance_evidence` ＋
    `check_pkg_content_binding`（同样用 AST 抽取 exec）；
  · 两臂都在**临时目录假包**上真跑 ⇒ **零写客户包、不出 zip、不加载模型**。

输出：`results/app/app570_minimvp_acceptance_gate_matrix.json`
"""
import ast
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
REL = "results/app/_app524_build_minimvp_rc11.py"
BUILD = os.path.join(REPO, REL.replace("/", os.sep))
ACCEPT_REL = "results/app/_app526_app107_rc11_acceptance.py"
REAL_PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc11"
REAL_EV = os.path.join(REPO, "results", "app",
                       "app526_app107_rc11_acceptance.json")
OUT = os.path.join(REPO, "results", "app",
                   "app570_minimvp_acceptance_gate_matrix.json")

CONST_NAMES = ("CONTENT_ROOT_FILES", "CONTENT_EXCLUDE_ROOT",
               "CONTENT_SKIP_SUFFIX", "CONTENT_SKIP_DIRS",
               "CONTENT_SKIP_NAMES")
AFTER_FNS = ("sha256_file", "content_binding_files", "_content_skip",
             "_norm_pkg_path", "check_acceptance_evidence",
             "check_pkg_content_binding")


# ── AST 抽取工具（不 import 被测模块）──────────────────────────────
def _src_of(text, name):
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError("找不到函数 %s" % name)


def _consts(text, names):
    tree = ast.parse(text)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in names:
                ns = {}
                exec(compile(ast.parse(ast.unparse(node)), "<c>", "exec"), ns)
                out[t.id] = ns[t.id]
    return out


def before_gate_source(text):
    """从**改前原文**抽出 make_zip 开头那三条闸门语句（逐字保留语义）。"""
    tree = ast.parse(text)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "make_zip":
            fn = node
    assert fn is not None, "改前脚本里没有 make_zip"
    picked = []
    for st in fn.body:
        s = ast.unparse(st)
        if ("ACCEPT_REPORT" in s) or ("smoke.get('verdict')" in s):
            picked.append(st)
        if len(picked) == 3:
            break
    assert len(picked) == 3, "改前闸门语句数不对：%d" % len(picked)
    mod = ast.Module(body=picked, type_ignores=[])
    body = ast.unparse(mod)
    lines = ["def _before_gate():"] + ["    " + l for l in body.split("\n")]
    lines.append("    return 'ALLOW'")
    return "\n".join(lines) + "\n", [ast.unparse(s) for s in picked]


def make_before_runner(src):
    ns = {"json": json, "os": os}
    exec(compile(src, "<before>", "exec"), ns)
    return ns


def make_after_runner(text):
    ns = {"os": os, "json": json, "hashlib": hashlib}
    ns.update(_consts(text, CONST_NAMES))
    for fn in AFTER_FNS:
        exec(compile(ast.parse(_src_of(text, fn)), "<fn>", "exec"), ns)
    return ns


# ── 判据：期望表（改前臂 / 改后臂）───────────────────────────────
#: (case, expect_before_blocked, expect_after_blocked, expect_after_reason)
ARMS = [
    ("T1_correct_evidence",        False, False, "OK"),
    ("T2_other_package",            False, True,  "PKG_MISMATCH"),
    ("T3_verdict_with_open_issues", True,  False, "OK"),
    ("T4_verdict_fail",             True,  True,  "VERDICT_NOT_PASS"),
    ("T5_no_evidence",              True,  True,  "NO_EVIDENCE"),
    ("T6_content_changed",          False, True,  "CONTENT_MISMATCH"),
    ("T7_extra_file",               False, True,  "CONTENT_SET_MISMATCH"),
    ("T8_no_content_binding",       False, True,  "NO_CONTENT_BINDING"),
    ("T9_verdict_skipped",          True,  True,  "VERDICT_NOT_PASS"),
    ("T10_deleted_file",            False, True,  "CONTENT_MISMATCH"),
    ("T11_pkg_path_variant",        False, False, "OK"),
    ("T12_malformed_json",          True,  True,  "BAD_JSON"),
]


def build_fixtures(td):
    pkg = os.path.join(td, "Confucius4_LiveCaption_MiniMVP_v1.0-rcXX")
    os.makedirs(os.path.join(pkg, "app"))
    open(os.path.join(pkg, "app", "a.py"), "w").write("x = 1\n")
    open(os.path.join(pkg, "app", "b.py"), "w").write("y = 2\n")
    open(os.path.join(pkg, "release.json"), "w").write('{"v": "rcXX"}')
    other = os.path.join(td, "Confucius4_LiveCaption_MiniMVP_v1.0-rcYY")
    os.makedirs(other)
    return pkg, other


def run_arm(case, td, before_ns, after_ns, pkg, other):
    """跑一臂：改前臂 + 改后臂，各自带自己的假包/假证据（互不干扰）。"""
    def fresh():
        d = tempfile.mkdtemp(dir=td)
        p = os.path.join(d, "Confucius4_LiveCaption_MiniMVP_v1.0-rcXX")
        os.makedirs(os.path.join(p, "app"))
        open(os.path.join(p, "app", "a.py"), "w").write("x = 1\n")
        open(os.path.join(p, "app", "b.py"), "w").write("y = 2\n")
        open(os.path.join(p, "release.json"), "w").write('{"v": "rcXX"}')
        return p

    def binding(p):
        return {rel: after_ns["sha256_file"](
            os.path.join(p, rel.replace("/", os.sep)))
            for rel in after_ns["content_binding_files"](p)}

    def write_ev(p, d, name):
        fp = os.path.join(p, "..", name)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        return fp

    p = fresh()
    good = {"pkg": p, "verdict": "PASS", "pkg_content": binding(p)}
    ev_path = None

    if case == "T1_correct_evidence":
        ev_path = write_ev(p, good, "ev.json")
    elif case == "T2_other_package":
        d = dict(good)
        d["pkg"] = os.path.join(td, "OTHER-PKG")
        ev_path = write_ev(p, d, "ev.json")
    elif case == "T3_verdict_with_open_issues":
        d = dict(good)
        d["verdict"] = "PASS（有 1 项未结：退出码异常）"
        ev_path = write_ev(p, d, "ev.json")
    elif case == "T4_verdict_fail":
        d = dict(good)
        d["verdict"] = "FAIL"
        ev_path = write_ev(p, d, "ev.json")
    elif case == "T5_no_evidence":
        ev_path = os.path.join(p, "..", "no_such_evidence.json")
    elif case == "T6_content_changed":
        ev_path = write_ev(p, good, "ev.json")
        open(os.path.join(p, "app", "a.py"), "w").write("x = 999\n")
    elif case == "T7_extra_file":
        ev_path = write_ev(p, good, "ev.json")
        open(os.path.join(p, "app", "c.py"), "w").write("z = 3\n")
    elif case == "T8_no_content_binding":
        ev_path = write_ev(p, {"pkg": p, "verdict": "PASS"}, "ev.json")
    elif case == "T9_verdict_skipped":
        d = dict(good)
        d["verdict"] = "SKIPPED_LOCK_BUSY"
        ev_path = write_ev(p, d, "ev.json")
    elif case == "T10_deleted_file":
        ev_path = write_ev(p, good, "ev.json")
        os.remove(os.path.join(p, "app", "b.py"))
    elif case == "T11_pkg_path_variant":
        d = dict(good)
        d["pkg"] = p + os.sep
        ev_path = write_ev(p, d, "ev.json")
    elif case == "T12_malformed_json":
        ev_path = os.path.join(p, "..", "ev_bad.json")
        open(ev_path, "w").write("{not json")
    else:
        raise AssertionError(case)

    # ── 改前臂（逐字原文）──
    bns = {"json": json, "os": os, "ACCEPT_REPORT": ev_path}
    exec(compile(BEFORE_SRC, "<before>", "exec"), bns)
    try:
        before_res = bns["_before_gate"]()
        before = {"blocked": False, "reason": str(before_res)}
    except Exception as e:
        before = {"blocked": True, "reason": type(e).__name__}

    # ── 改后臂（修好的闸门）──
    try:
        ok, reason, detail = after_ns["check_acceptance_evidence"](ev_path, p)
        if not ok:
            after = {"blocked": True, "reason": reason}
        else:
            ok2, reason2, detail2 = after_ns["check_pkg_content_binding"](
                ev_path, p, detail.get("evidence"))
            after = {"blocked": (not ok2), "reason": reason2}
    except Exception as e:
        after = {"blocked": True, "reason": "EXCEPTION:%s" % type(e).__name__}
    return before, after


def main():
    # ── 改前原文：git cat-file blob HEAD:（不是工作树！）──
    blob = subprocess.run(["git", "-C", REPO, "cat-file", "blob",
                           "HEAD:" + REL],
                          capture_output=True, check=True).stdout
    before_text = blob.decode("utf-8")
    global BEFORE_SRC, BEFORE_STMTS
    BEFORE_SRC, BEFORE_STMTS = before_gate_source(before_text)

    after_text = open(BUILD, "rb").read().decode("utf-8")
    after_ns = make_after_runner(after_text)

    rows = []
    n_pass = n_fail = 0
    with tempfile.TemporaryDirectory() as td:
        for case, exp_b, exp_a, exp_reason in ARMS:
            before, after = run_arm(case, td, None, after_ns, None, None)
            good = (before["blocked"] == exp_b
                    and after["blocked"] == exp_a
                    and (not exp_a or after["reason"] == exp_reason))
            rows.append({"case": case, "expect_before_blocked": exp_b,
                         "expect_after_blocked": exp_a,
                         "expect_after_reason": exp_reason,
                         "before": before, "after": after, "pass": good})
            if good:
                n_pass += 1
            else:
                n_fail += 1

    # ── 真包只读复验（零写入）──
    real = {}
    if os.path.isdir(REAL_PKG):
        bns = {"json": json, "os": os, "ACCEPT_REPORT": REAL_EV}
        exec(compile(BEFORE_SRC, "<before>", "exec"), bns)
        try:
            bns["_before_gate"]()
            real["before"] = {"blocked": False, "reason": "ALLOW"}
        except Exception as e:
            real["before"] = {"blocked": True, "reason": type(e).__name__}
        ok, reason, detail = after_ns["check_acceptance_evidence"](REAL_EV,
                                                                    REAL_PKG)
        real["after_identity"] = {"ok": ok, "reason": reason,
                                  "evidence_pkg": detail.get("evidence_pkg"),
                                  "verdict": detail.get("verdict")}
        ok2, reason2, detail2 = after_ns["check_pkg_content_binding"](
            REAL_EV, REAL_PKG, detail.get("evidence"))
        real["after_content"] = {"ok": ok2, "reason": reason2,
                                 "n_bound": detail2.get("n_bound"),
                                 "n_candidates": detail2.get("n_candidates"),
                                 "note": detail2.get("note")}
        st = os.stat(REAL_PKG)
        real["pkg_mtime"] = datetime.datetime.fromtimestamp(
            st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        real["pkg_path"] = REAL_PKG

    fail_open = [r["case"] for r in rows
                 if r["expect_before_blocked"] is False
                 and r["before"]["blocked"] is False
                 and r["expect_after_blocked"] is True]
    false_fail = [r["case"] for r in rows
                  if r["expect_before_blocked"] is True
                  and r["before"]["blocked"] is True
                  and r["expect_after_blocked"] is False]

    ev = {
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "correction": "§207（巡检自查；reviewer 无新纠偏）",
        "what": ("MiniMVP 出包闸门鉴别力矩阵：改前臂 = HEAD blob 逐字原文，"
                 "改后臂 = 修好的闸门；两臂在临时假包上真跑"),
        "before_source": {
            "how": "git cat-file blob HEAD:" + REL,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
            "gate_statements": BEFORE_STMTS,
        },
        "after_source": {
            "path": REL,
            "bytes": len(after_text.encode("utf-8")),
            "sha256": hashlib.sha256(
                after_text.encode("utf-8")).hexdigest(),
        },
        "arms": rows,
        "n_arms": len(rows),
        "n_pass": n_pass,
        "n_fail": n_fail,
        "before_fail_open_arms": fail_open,
        "before_false_fail_arms": false_fail,
        "real_pkg_readonly": real,
        "discipline": {
            "wrote_customer_package": 0,
            "produced_zip": False,
            "loaded_model": False,
            "gpu_used": False,
            "machine_lock_taken": False,
            "note": "两臂都在临时目录假包上跑；真包只读（仅 stat + 读证据）",
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print("改前 fail-open 臂:", fail_open)
    print("改前 假 FAIL 臂:", false_fail)
    print("矩阵: %d/%d PASS -> %s" % (n_pass, len(rows), OUT))
    for r in rows:
        print("  %-30s before=%-22s after=%-22s pass=%s"
              % (r["case"], r["before"]["reason"], r["after"]["reason"],
                 r["pass"]))
    print("\n真包只读复验:", json.dumps(real, ensure_ascii=False, indent=1))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
