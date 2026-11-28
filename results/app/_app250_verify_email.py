# -*- coding: utf-8 -*-
"""§250：核对**已发邮件**与**入库正文**逐字节等价（服务端转 HTML ⇒ 先反向规范化）。

🔴 纪律（§224）：长邮件正文会截断 ⇒ 必须核「首/中/尾三地标」都命中同一 message_id。
🔴 通道会把 PLAIN 转成 HTML（``&nbsp;`` / ``<br  />``）⇒ 核对前**反向规范化**：
   ① ``&nbsp;`` → 空格　② ``<br  />`` → ``\\n``　③ 其余 HTML 实体反转义
   ④ 去首尾空白　⇒ 再与入库正文比 sha256。
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
BODY = os.path.join(REPO, "results", "app", "app250_status_email_body.txt")
OUT = os.path.join(REPO, "results", "app", "app250_status_email_sent.json")

MSG_ID = "msg_2hYbcrP4Lv8IOLc4dEe1rhAprUncWnY7aVgyR4YKgz6EBA"
SENT_AT = "2026-11-28T05:32:21Z"

# 🔴 从已发箱回读到的正文（服务端 HTML 形态）——落盘备查，避免手工转写出错
SENT_HTML = os.path.join(REPO, "results", "app", "app250_status_email_sent.html")


def denorm(h):
    """服务端 HTML → 原始纯文本。"""
    t = h
    t = t.replace("<br  />", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = t.replace("&nbsp;", " ")
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return t


def main():
    disk = io.open(BODY, encoding="utf-8").read()
    h = io.open(SENT_HTML, encoding="utf-8").read()
    t = denorm(h)
    # 🔴 服务端把结尾的最后一个换行变成 `<br  />` ⇒ 反向规范化后会多出一个 \n
    #    ⇒ 比对前统一去掉**所有**末尾空白（正文内容本身无尾随空白差异）。
    disk_c = disk.rstrip("\r\n")
    t_c = t.rstrip("\r\n")

    sha_disk = hashlib.sha256(disk_c.encode("utf-8")).hexdigest()
    sha_sent = hashlib.sha256(t_c.encode("utf-8")).hexdigest()

    marks = {
        "head": "【地标-首】APP 线程 §250 回报。",
        "mid": "═══ 四、独立复核结果（4/4 判据全 PASS）═══",
        "tail": "【地标-尾】§250 结束。last_ack 仍 APP-157。",
    }
    mk = {k: (v in t_c) for k, v in marks.items()}

    res = {
        "script": "_app250_verify_email.py",
        "message_id": MSG_ID,
        "sent_at": SENT_AT,
        "to": "alexchen7694@agent.qq.com",
        "subject_prefix": "[C4][A][STATUS][APP] §250",
        "bytes_disk": len(disk.encode("utf-8")),
        "bytes_disk_compared": len(disk_c.encode("utf-8")),
        "sha256_disk": sha_disk,
        "bytes_sent_normalized": len(t_c.encode("utf-8")),
        "sha256_sent_normalized": sha_sent,
        "identical_after_denorm": sha_disk == sha_sent,
        "landmarks": mk,
        "all_landmarks_hit": all(mk.values()),
        "truncated": (not all(mk.values())) or (len(t_c) < len(disk_c) * 0.95),
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("入库正文  : %d B  sha256 %s" % (res["bytes_disk"], sha_disk[:16]))
    print("已发规范化: %d B  sha256 %s" % (res["bytes_sent_normalized"], sha_sent[:16]))
    print("逐字节等价:", res["identical_after_denorm"])
    print("三地标    :", mk)
    print("截断      :", res["truncated"])
    print("写出:", OUT)


if __name__ == "__main__":
    main()
