# -*- coding: utf-8 -*-
"""从**当前会话的 JSONL** 里提取「已发邮件正文」（🔴 禁人工转写 ⇒ 从工具结果落盘）。

🔴 纪律（§222／§224）：「工具结果落盘 → 脚本扫命中才写出」⇒ 本脚本从会话
   JSONL 的 ``mcp__qq-mail__GetMessage`` 工具结果里**原样**取出 body 字段
   ⇒ 不经人手 ⇒ 无转写错误风险。
"""
from __future__ import annotations

import glob
import io
import json
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
OUT = os.path.join(REPO, "results", "app", "app250_status_email_sent.html")
MSG_ID = "msg_5HRy9Otzn3Z1mIOHmfkqQK95fuoWagBZII5U-gE0OGow7Q"

PROJ = os.path.expanduser(
    r"~/.workbuddy/projects/c-Users-Trekker-PTL-confucius4-openvino")


def walk(o):
    """递归找出所有含 MSG_ID 的 dict，取其 body。"""
    hits = []
    if isinstance(o, dict):
        blob = json.dumps(o, ensure_ascii=False)
        if MSG_ID in blob and "body" in o:
            b = o.get("body")
            if isinstance(b, str) and len(b) > 500:
                hits.append(b)
        for v in o.values():
            hits += walk(v)
    elif isinstance(o, list):
        for v in o:
            hits += walk(v)
    elif isinstance(o, str):
        if MSG_ID in o:
            try:
                hits += walk(json.loads(o))
            except Exception:
                pass
    return hits


def main():
    cands = sorted(glob.glob(os.path.join(PROJ, "*.jsonl")),
                   key=os.path.getmtime, reverse=True)
    bodies = []
    for f in cands[:6]:
        try:
            raw = io.open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if MSG_ID not in raw:
            continue
        for ln in raw.splitlines():
            if MSG_ID not in ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            bodies += walk(o)
        if bodies:
            break
    if not bodies:
        print("!! 未在会话 JSONL 里找到已发邮件正文")
        raise SystemExit(1)
    # 取**最长**的那个（GetMessage 的完整结果）
    body = max(bodies, key=len)
    print("从会话 JSONL 提取：%d B（候选 %d 个）" % (len(body), len(bodies)))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    print("写出:", OUT)


if __name__ == "__main__":
    main()
