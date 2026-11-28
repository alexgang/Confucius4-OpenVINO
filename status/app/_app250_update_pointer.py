# -*- coding: utf-8 -*-
"""§250：把 STATUS_APP.md 里的 §250 指针行**字节层**替换为最终版（🔴 不用 Edit）。

🔴 写前不变量：
 ① 锚点（旧指针行）**唯一命中**（命中数必须 == 1）
 ② 其余部分**逐字节**不变
 ③ 行尾风格不变、行数不变（1 行换 1 行）
 ④ 新指针行不含会议原句（用 GT 基线句归一化子串判定）
"""
from __future__ import annotations

import io
import json
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
P = os.path.join(REPO, "status", "app", "STATUS_APP.md")

OLD_MARK = b"## \xc2\xa7250 \xe5\x85\xad\xe9\x80\x9a\xe9\x81\x93"  # "## §250 六通道"

NEW = (
    "## §250 六通道复核（**无新 App 纠偏**，`last_ack` 仍 **APP-157**）"
    "｜🔴 **接续上一会话（TAKEOVER）** ⇒ 闭合 §250 断点"
    "｜🔴 **§249 终检的 4 处判据缺陷**（「残留 0」是范围受限的假绿）\r\n"
    "> 🔴 正文全文 ⇒ `status/app/STATUS_APP_sec250_detail_20261128.md`"
    "（§0 顺序、§1 六通道证据、§2 死会话断点「行为等价通过」**无落盘证据**、"
    "§3 §249 的 4 处判据缺陷 D-1…D-4、§4 独立复核 **4/4 判据全 PASS**"
    "（§1 残留扫描豁免外 **0**／§2 diff 法 **11/11**／§3 语法 JSON **11/11**／"
    "§4 行为等价还原式 **4/4**）＋ 逐文件不变量 **11/11** ＋ 反证组 **3/3**"
    "（判据有鉴别力）＋ 本轮自身修掉 **5 处判据缺陷**、§5.1 **7 处泄漏**（含我自己 3 处）已修"
    "＋ **重跑生产脚本 ⇒ 逐字节相等（可复现）**、§5.3 **发信正文与入库件不一致（15 B 差）已改走直连 API**（正文从磁盘读 ⇒ 逐字节等价 `ce252ee…`）、"
    "§5.4 入库前泄漏自查 **确定性候选集/泄漏 0**、"
    "§5.5 🔴 **新发现：39 个 GT 源文件 tracked 且 25 个仍含原句**"
    "（＝ APP-144 ① 的对象，**需 reviewer 放行**）、§6 提交与交付面、§7 纪律与收尾指纹、§8 待办）\r\n"
)


def main():
    b0 = open(P, "rb").read()
    n = b0.count(OLD_MARK)
    assert n == 1, "① 违反：锚点命中数 = %d（必须 == 1）" % n
    # 旧指针行 = 从 §250 行首到该行行尾（含下一行的指针行）
    i = b0.index(OLD_MARK)
    j = b0.index(b"\r\n", i) + 2          # §250 标题行行尾
    k = b0.index(b"\r\n", j) + 2          # 指针行行尾
    old_block = b0[i:k]
    print("旧块 %d B（%d 行）" % (len(old_block), old_block.count(b"\n")))

    body = NEW.encode("utf-8")
    b1 = b0[:i] + body + b0[k:]

    assert b1 != b0, "① 违反：无变化"
    assert b1.count(b"\n") == b0.count(b"\n"), "③ 违反：行数变化"
    crlf0 = b0.count(b"\r\n")
    lf0 = b0.count(b"\n") - crlf0
    assert b1.count(b"\r\n") == crlf0 and (b1.count(b"\n") - crlf0) == lf0, "③ 违反：行尾变化"
    assert b1[:i] == b0[:i] and b1[len(b1) - (len(b0) - k):] == b0[k:], "② 违反：块外字节被改"

    # ④ 新指针行不含会议原句
    import importlib.util
    _sp = importlib.util.spec_from_file_location(
        "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
    _v3 = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(_v3)
    _gt = json.load(open(os.path.join(REPO, "results", "app",
                                      "app155_desens_ground_truth.json"),
                         encoding="utf-8"))
    _nl, _ = _v3.norm_with_map(body.decode("utf-8"))
    _hit = [s for s in _v3.baseline_sents(_gt) if s in _nl]
    assert not _hit, "④ 违反：新指针行含会议原句（%d 句）" % len(_hit)

    with io.open(P, "wb") as fh:
        fh.write(b1)
    print("写出: bytes %d → %d（Δ=%d）" % (len(b0), len(b1), len(b1) - len(b0)))


if __name__ == "__main__":
    main()
