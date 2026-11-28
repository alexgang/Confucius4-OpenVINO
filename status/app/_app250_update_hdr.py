# -*- coding: utf-8 -*-
"""§250：更新 STATUS_APP.md 头部的「更新时间」（字节层精确替换，🔴 不用 Edit）。

🔴 写前不变量：
 ① 只替换**唯一一处** `更新时间: <旧值>`（锚点唯一 ⇒ 命中数必须 == 1）
 ② 其余部分**逐字节**不变（长度变化 == 新旧时间串长度差）
 ③ 行尾风格/行数不变
 ④ `last_ack` 字段**不动**（无新纠偏 ⇒ 仍 APP-157）
"""
from __future__ import annotations

import hashlib
import io
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
P = os.path.join(REPO, "status", "app", "STATUS_APP.md")

OLD = b"\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4: 2026-11-27 21:40"  # 更新时间: 2026-11-27 21:40
NEW = b"\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4: 2026-11-28 13:24"  # 更新时间: 2026-11-28 13:24


def main():
    b0 = open(P, "rb").read()
    n = b0.count(OLD)
    print("写前: bytes=%d sha256=%s" % (len(b0),
                                       hashlib.sha256(b0).hexdigest()))
    assert n == 1, "① 违反：锚点命中数 = %d（必须 == 1）" % n
    crlf0 = b0.count(b"\r\n")
    lf0 = b0.count(b"\n") - crlf0
    lines0 = b0.count(b"\n")
    b1 = b0.replace(OLD, NEW, 1)
    assert len(b1) - len(b0) == len(NEW) - len(OLD), "② 违反：长度变化异常"
    assert b1.count(b"\r\n") == crlf0 and (b1.count(b"\n") - crlf0) == lf0, "③ 违反：行尾变化"
    assert b1.count(b"\n") == lines0, "③ 违反：行数变化"
    assert b"last_ack: APP-157" in b1, "④ 违反：last_ack 被改动"
    assert b"last_ack: APP-157" in b0, "④ 违反：写前 last_ack 就不是 APP-157"
    with io.open(P, "wb") as fh:
        fh.write(b1)
    print("写出: bytes=%d (Δ=%d)" % (len(b1), len(b1) - len(b0)))


if __name__ == "__main__":
    main()
