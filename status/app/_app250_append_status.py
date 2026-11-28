# -*- coding: utf-8 -*-
"""§250：把指针行**字节层**追加到 status/app/STATUS_APP.md（🔴 该文件是**混合行尾**
71 CRLF + 43 LF ⇒ **不能用 Edit 工具**（§236 坑⑥：Edit 会规整行尾）⇒ 必须字节层重建）。

🔴 写前不变量（任一 FAIL ⇒ **零改动**）：
 ① 原文件**逐字节**不变（只追加在末尾）
 ② 追加后仍**混合行尾**（不引入新的 CRLF/LF 组合变化 ⇒ 沿用原末尾那行的行尾）
 ③ 追加内容**不含**会议原句（RULES §0）
 ④ 追加后 ≤ 40 000 B / ≤ 300 行（APP-052④ 限额）

🔴 追加后另起脚本复核 ＋ `git diff --numstat`。
"""
from __future__ import annotations

import hashlib
import io
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
P = os.path.join(REPO, "status", "app", "STATUS_APP.md")

POINTER = (
    "## §250 六通道复核（**无新 App 纠偏**，`last_ack` 仍 **APP-157**）"
    "｜🔴 **接续上一会话（TAKEOVER）** ⇒ 闭合 §250 断点"
    "｜🔴 **§249 终检的 4 处判据缺陷**（「残留 0」是范围受限的假绿）\r\n"
    "> 🔴 正文全文 ⇒ `status/app/STATUS_APP_sec250_detail_20261128.md`"
    "（§0 顺序、§1 六通道证据、§2 死会话断点「行为等价通过」**无落盘证据**、"
    "§3 §249 的 4 处判据缺陷 D-1…D-4、§4 独立复核 **4/4 判据全 PASS**"
    "（§1 残留扫描豁免外 **0**／§2 diff 法 **11/11**／§3 语法 JSON **11/11**／"
    "§4 行为等价还原式 **4/4**）＋ 逐文件不变量 **11/11** ＋ 反证组 **3/3**"
    "（判据有鉴别力）＋ 本轮自身修掉 **5 处判据缺陷**、§5 脱敏成立（11 文件/19 处）"
    "＋ **1 处豁免如实登记**、§5.1 🔴 **新发现：39 个 GT 源文件 tracked 且 25 个仍含原句**"
    "（＝ APP-144 ① 的对象，**需 reviewer 放行**）、§6 提交与交付面、§7 纪律与收尾指纹、§8 待办）\r\n"
)


def main():
    b0 = open(P, "rb").read()
    sha0 = hashlib.sha256(b0).hexdigest()
    size0 = len(b0)
    lines0 = b0.count(b"\n")
    crlf0 = b0.count(b"\r\n")
    lf0 = b0.count(b"\n") - crlf0
    print("写前: bytes=%d sha256=%s crlf=%d lf=%d lines=%d"
          % (size0, sha0, crlf0, lf0, lines0))

    # ② 追加内容必须用**原文件末尾那行的行尾**（保持混合行尾特征不变）
    tail_eol = b"\r\n" if b0.endswith(b"\r\n") else (b"\n" if b0.endswith(b"\n") else b"\r\n")
    body = POINTER.replace("\r\n", "\r\n" if tail_eol == b"\r\n" else "\n")
    b1 = b0 + body.encode("utf-8")
    body_b = body.encode("utf-8")

    # ── 写前不变量自检 ──────────────────────────────────────
    assert b1.startswith(b0), "① 违反：原文件被改动"
    assert b1.count(b"\n") == lines0 + body_b.count(b"\n"), "① 违反：行数增量异常"
    crlf1 = b1.count(b"\r\n")
    lf1 = b1.count(b"\n") - crlf1
    assert (crlf1, lf1) == (crlf0 + body_b.count(b"\r\n"),
                            lf0 + body_b.count(b"\n") - body_b.count(b"\r\n")), "② 违反：行尾风格变化"
    assert len(b1) <= 40000, "④ 违反：超过 40 000 B 限额"
    assert b1.count(b"\n") <= 300, "④ 违反：超过 300 行限额"

    # ③ 内容不得含会议原句（**用 GT 基线句做归一化子串判定**，不把原句写进本文件）
    import importlib.util
    _sp = importlib.util.spec_from_file_location(
        "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
    _v3 = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(_v3)
    _gt = json.load(open(os.path.join(REPO, "results", "app",
                                      "app155_desens_ground_truth.json"),
                         encoding="utf-8"))
    _base = _v3.baseline_sents(_gt)
    _nl, _ = _v3.norm_with_map(body.decode("utf-8"))
    _hit = [s for s in _base if s in _nl]
    assert not _hit, "③ 违反：追加内容含会议原句（命中 %d 句）" % len(_hit)

    with io.open(P, "wb") as fh:
        fh.write(b1)
    print("写出: bytes=%d (Δ=%d) lines=%d" % (len(b1), len(b1) - size0,
                                              b1.count(b"\n")))


if __name__ == "__main__":
    main()
