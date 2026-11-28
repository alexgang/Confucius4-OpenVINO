# -*- coding: utf-8 -*-
"""§250 落盘不变量终检 v3（**修正 v1/v2 的还原算法缺陷**）。

🔴 缺陷演进（都是**判据自身**的缺陷，不是产品缺陷）：
 - **v1**：用「公共前后缀」定位原句 ⇒ **同一行多个占位符**时前后缀互相干扰
   ⇒ 还原错位 ⇒ 假 FAIL（v1 实测 1/11）。
 - **v2**：改成「顺序对齐」⇒ 但**字面量在备份行里找不到**时（占位符整段替换了
   一个反引号包裹的短语 ⇒ 后续字面量被吞掉）⇒ 锚点错位 ⇒ 还原出「重复前缀」
   ⇒ 假 FAIL（v2 实测 0/11）。
 - **v3**：改用**哨兵 + difflib 字符级对齐**：把每个占位符换成**唯一哨兵字符**
   ⇒ 再与备份行做 SequenceMatcher ⇒ `equal` 段必须**逐字节相等**，
   `replace` 段的备份侧就是该占位符的**原句** ⇒ 还原后与备份**逐字节相等**。
   ⇒ 天然支持「一行多个占位符」「占位符吞掉整段」两种形态。

四项不变量（任一 FAIL ⇒ 该文件的脱敏**不成立**）：
 ① 行尾风格不变（CRLF/LF 计数不变且不混用）
 ② 行数不变
 ③ **非替换部分逐字节不变**（哨兵还原后与备份**逐字节相等**）
 ④ 占位符个数 == applied 记录数（无漏改/无多改）
"""
import difflib
import io
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
BACKUP = r"C:\Users\Trekker-PTL\shared\app250_desen_backup"
REDACT = os.path.join(REPO, "results", "app", "app250_redact.json")
OUT = os.path.join(REPO, "results", "app", "app250_invariants.json")

PH_RE = re.compile(r"\[会议句 idx \d+\]")
SENT_BASE = 0xE000


def eol(b):
    crlf = b.count(b"\r\n")
    return crlf, b.count(b"\n") - crlf


def restore_line(cur_line, bak_line):
    """哨兵 + difflib 对齐还原 ⇒ (restored, n_sentinels, equal_ok)；失败 (None,0,False)。"""
    phs = PH_RE.findall(cur_line)
    if not phs:
        if cur_line == bak_line:
            return cur_line, 0, True
        return None, 0, False
    sent_map = {}
    s = cur_line
    for i, ph in enumerate(phs):
        ch = chr(SENT_BASE + i)
        sent_map[ch] = ph
        s = s.replace(ph, ch, 1)
    sm = difflib.SequenceMatcher(None, bak_line, s, autojunk=False)
    out = []
    n_sent_used = 0
    equal_ok = True
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            if bak_line[i1:i2] != s[j1:j2]:
                equal_ok = False
            out.append(bak_line[i1:i2])
        elif tag == "replace":
            cur_seg = s[j1:j2]
            bak_seg = bak_line[i1:i2]
            sent_in = [c for c in cur_seg if c in sent_map]
            if len(sent_in) != 1:
                return None, 0, False
            out.append(bak_seg)
            n_sent_used += 1
        elif tag == "delete":
            return None, 0, False
        elif tag == "insert":
            cur_seg = s[j1:j2]
            if len(cur_seg) != 1 or cur_seg not in sent_map:
                return None, 0, False
            out.append(sent_map[cur_seg])
            n_sent_used += 1
    restored = "".join(out)
    return restored, n_sent_used, equal_ok


def main():
    red = json.load(open(REDACT, encoding="utf-8"))
    rows = []
    for c in red["changed"]:
        rel = c["file"]
        cur_p = os.path.join(REPO, rel.replace("/", os.sep))
        bak_p = os.path.join(BACKUP, rel.replace("/", os.sep))
        cb = open(cur_p, "rb").read()
        bb = open(bak_p, "rb").read()
        c_crlf, c_lf = eol(cb)
        b_crlf, b_lf = eol(bb)
        c_lines = cb.decode("utf-8").splitlines()
        b_lines = bb.decode("utf-8").splitlines()
        n_ph_actual = len(PH_RE.findall(cb.decode("utf-8")))
        n_applied = len(c.get("applied", []))

        restored_lines, n_fail, n_sent_used, eq_ok = [], 0, 0, True
        for i, cl in enumerate(c_lines):
            bl = b_lines[i] if i < len(b_lines) else ""
            r, ns, e_ok = restore_line(cl, bl)
            if r is None:
                r = cl
                n_fail += 1
            else:
                n_sent_used += ns
                eq_ok = eq_ok and e_ok
            restored_lines.append(r)
        # 🔴 v3 缺陷：`"\n".join(...)` **丢掉文件末尾的换行** ⇒ 与备份恒差 1 字节
        #    ⇒ 假 FAIL。⇒ 改为**逐行列表**比较（末尾换行单独记 flag）。
        restored_text = "\n".join(restored_lines)
        if b_crlf and not b_lf:
            restored_text = restored_text.replace("\n", "\r\n")
        bak_text = bb.decode("utf-8")
        b_trailing_nl = bak_text.endswith("\n")
        c_trailing_nl = cb.decode("utf-8").endswith("\n")
        if b_trailing_nl and not restored_text.endswith("\n"):
            restored_text += "\r\n" if (b_crlf and not b_lf) else "\n"

        row = {
            "file": rel,
            "bytes_before": len(bb), "bytes_after": len(cb),
            "eol_before": {"crlf": b_crlf, "lf": b_lf},
            "eol_after": {"crlf": c_crlf, "lf": c_lf},
            "eol_same": (b_crlf == c_crlf and b_lf == c_lf),
            "no_mixed_eol": not (c_crlf and c_lf),
            "lines_before": len(b_lines), "lines_after": len(c_lines),
            "line_count_same": len(b_lines) == len(c_lines),
            "n_applied": n_applied,
            "n_placeholders_actual": n_ph_actual,
            "placeholder_count_match": (n_ph_actual == n_applied),
            "n_lines_restore_failed": n_fail,
            "n_sentinels_matched": n_sent_used,
            "equal_segments_byte_identical": eq_ok,
            "restored_equals_backup": (restored_text == bb.decode("utf-8")),
        }
        row["ok"] = bool(row["eol_same"] and row["no_mixed_eol"]
                         and row["line_count_same"]
                         and row["placeholder_count_match"]
                         and row["n_lines_restore_failed"] == 0
                         and row["equal_segments_byte_identical"]
                         and row["restored_equals_backup"])
        rows.append(row)

    n_pass = sum(1 for r in rows if r["ok"])
    res = {"script": "_app250_chk_invariants3.py",
           "note": "对照 §250 备份目录的逐文件不变量终检（哨兵 + difflib 字符级对齐还原）",
           "n_files": len(rows), "n_pass": n_pass,
           "all_pass": n_pass == len(rows), "rows": rows}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    for r in rows:
        print("  %-58s %s" % (r["file"][-58:], "PASS" if r["ok"] else "FAIL"))
    print("\n不变量终检：%d/%d PASS" % (n_pass, len(rows)))
    print("写出:", OUT)


if __name__ == "__main__":
    main()
