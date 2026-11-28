# -*- coding: utf-8 -*-
"""定位「已发规范化正文」与「入库正文」的差异（逐字符）。"""
import difflib
import html
import io
import re

DISK = "results/app/app250_status_email_body.txt"
SENT = "results/app/app250_status_email_sent.html"


def denorm(h):
    t = h.replace("<br  />", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = t.replace("&nbsp;", " ")
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t)


d = io.open(DISK, encoding="utf-8").read().strip("\n")
s = denorm(io.open(SENT, encoding="utf-8").read()).strip("\n")
print("disk=%d sent=%d" % (len(d), len(s)))
sm = difflib.SequenceMatcher(None, d, s, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    print("--- %s disk[%d:%d] sent[%d:%d]" % (tag, i1, i2, j1, j2))
    print("    disk:", repr(d[max(0, i1 - 40):i2 + 40]))
    print("    sent:", repr(s[max(0, j1 - 40):j2 + 40]))
