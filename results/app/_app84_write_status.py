# -*- coding: utf-8 -*-
"""App §84 落盘脚本：只追加章节 + 改头部 4 字段行。

纪律：
  - 只追加 `## §N ...` 章节，不回头改旧章节；
  - 头部只改 4 字段行（last_ack / 更新时间 / 当前任务 / 阻塞），「阻塞」行按前缀找，不写死索引；
  - STATUS 是 LF ⇒ 写盘 newline=''；
  - 「最近更新」区块保持 <= 15 行（加一行 ⇒ 删最旧一行）。
"""
import io
import os
import re
import sys

STATUS = r"C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md"
SECTION = r"C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app84_status_section.md"

TS = "2026-10-28 16:18"  # Get-Date 实测值（非推算）
LAST_ACK = "APP-033"


def main():
    with io.open(STATUS, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    assert "\r\n" not in text, "STATUS 出现 CRLF，脚本假设 LF"

    # --- 前置校验：确认 §84 尚未落盘（幂等保护）---
    if re.search(r"^## §84\b", text, re.M):
        print("[SKIP] §84 已存在于 STATUS_APP.md，本次不重复追加")
        return 0

    with io.open(SECTION, "r", encoding="utf-8", newline="") as f:
        sec = f.read()
    if "\r\n" in sec:
        sec = sec.replace("\r\n", "\n")
    # 章节时间戳换成实测值
    sec = sec.replace("（2026-10-28 14:56）", "（%s）" % TS)
    sec = sec.replace("「更新时间」= **2026-10-28 14:56**", "「更新时间」= **%s**" % TS)

    # --- 头部 4 字段行 ---
    lines = text.split("\n")

    def set_field(lines, prefix, new_value):
        hit = 0
        for i, ln in enumerate(lines):
            if ln.startswith(prefix):
                lines[i] = new_value
                hit += 1
        assert hit == 1, "字段 %s 命中数 = %d（应为 1）" % (prefix, hit)
        return lines

    lines = set_field(lines, "last_ack:", "last_ack: %s" % LAST_ACK)
    lines = set_field(lines, "更新时间:", "更新时间: %s" % TS)

    task_line = (
        "当前任务: **§84 🔴🔴 APP-027 V3（克隆）实测已跑完（CUDA + NPU 两组，各 20 PASS / 0 FAIL；"
        "机器判据层面）＋ 自查抓出并修掉 2 个真实缺陷（① CLI 路径根本没有克隆链路 ⇒ V3 客观做不了；"
        "② 真实播放路径的逐句遥测整组字段丢失 ⇒ 连 APP-030⑤ 的逐句语言字段也不可用）＋ "
        "客户包定点同步完成（sha_disk == sha_cand，3/3 PASS）＋ 独立复核（wav↔id 76/76、SHA256 76/76 两组全中）"
        "＋ §85 客户包 NOTICE/THIRD_PARTY 许可不实表述已修正（num2words 实为 LGPL-2.1；47 个 vendored 包署名全覆盖）"
        "＋ ASR 的 wespeaker 署名义务判定回告（包内不带权重 ⇒ 可免除）"
        "⇒ ✅ **本条已完成**（代码侧 + 机器判据）⇒ 🔴 **本条需等 reviewer 复核**"
        "（V3-CER MiniMax 回转写、V3-CAMPPlus 余弦、V4 用户实听、CUDA 组无预设对照是否补跑、"
        "NPU 前 6 句是否算缺陷、§83.5 四项裁定）＋ ⛔ **zip 未重打 ⇒ 不写「已交付」**"
        "（APP-027 的 V4 未做；APP-031 要求三项合打）"
    )
    lines = set_field(lines, "当前任务:", task_line)

    block_line = (
        "阻塞 / 待用户决定: ① 🔴 **APP-027 V3（克隆）机器判据已过**（§84：CUDA 20 PASS / 0 FAIL、NPU 20 PASS / 0 FAIL；"
        "两组各 76 句 wav 落盘、逐句含音色来源字段、隐私判据 clone_leaks/tmp_clone_residue 均空）"
        "⇒ 【本模块侧已完成】；② 🔴 **V3-CER（MiniMax 回转写）与 V3-CAMPPlus（CAMPPlus 余弦）仍归 reviewer**"
        "（§84 判据标 [NO-EVIDENCE]）⇒ APP-027 **仍未完**；③ 🔴 **V4 用户实听未做**"
        "（本轮是 CLI 回放 + 真实播放路径，走声卡，机器判据 `consumed=True` 76/76 + `read_delta ≥ n_samples` + 无 `consumed=False`，"
        "**但人耳未确认** ⇒ 「用户听得到」仍不成立）；④ ⛔ **zip 未重打**（APP-031 明文「三项做完后合在一起重打一次包」）"
        "⇒ 按 §66 口径 **不写「已交付」**（准确表述：**代码侧已入库、已同步到包目录；zip 未重打**）；"
        "⑤ 🔴 **§84 缺陷②的连带影响**：V1/V2 两轮报告（真实播放路径）的 `lang`/`end_reason` 字段原本缺失 ⇒ "
        "若要补「按语言分组」的字段需用修好后的代码重跑（本轮**未重跑**）；⑥ 🔴 **§83.5 的 4 项裁定仍然有效**"
        "（RTF 归因边界 / 「首包」指标定义 / app062 A/B 是否重做 / 不变式是否改三段式）"
        "⇒ 本轮**未自行推进**；⑦ 🔴 **本轮未修改 `CORRECTIONS_APP.md`**（只读、零改动）、未向 MiniMax、未开 FTP、"
        "未跑 `verify_pkg_zip.py`、**未用 `git add -A`**（逐文件 add）"
    )
    lines = set_field(lines, "阻塞 / 待用户决定:", block_line)

    text = "\n".join(lines)

    # --- 最近更新区块：加一行，删最旧一行，保持 <= 15 ---
    m = re.search(r"(^## 最近更新\n)(.*?)(?=^## )", text, re.S | re.M)
    assert m, "未找到「## 最近更新」区块"
    block = m.group(2).rstrip("\n")
    blines = [l for l in block.split("\n") if l.strip()]
    new_entry = (
        "%s §84 🔴🔴 **APP-027 V3（克隆）实测跑完（CUDA + NPU 两组，各 20 PASS / 0 FAIL）＋ "
        "自查抓出并修掉 2 个真实缺陷（CLI 路径根本没有克隆链路 / 真实播放路径逐句遥测整组字段丢失）"
        "＋ 客户包定点同步完成** ⇒ ✅ 两组各 76 句 wav、逐句带音色来源、隐私判据空 ⇒ "
        "✅ 独立复核 wav↔id 76/76、SHA256 76/76 ⇒ ⛔ **CER/CAMPPlus 归 reviewer、V4 用户实听未做 "
        "⇒ APP-027 未完 ⇒ zip 不重打 ⇒ 不写「已交付」**" % TS[11:16]
    )
    blines.insert(0, new_entry)
    while len(blines) > 15:
        blines.pop()
    text = text[: m.start(2)] + "\n".join(blines) + "\n\n" + text[m.end(2):]

    # --- 追加 §84 章节到文件末尾 ---
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + sec.rstrip("\n") + "\n"

    with io.open(STATUS, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    # --- 写后复核 ---
    with io.open(STATUS, "r", encoding="utf-8", newline="") as f:
        chk = f.read()
    assert "\r\n" not in chk, "写盘后出现 CRLF"
    assert re.search(r"^## §84\b", chk, re.M), "§84 未落盘"
    assert re.search(r"^last_ack: APP-033$", chk, re.M), "last_ack 不对"
    assert re.search(r"^更新时间: %s$" % re.escape(TS), chk, re.M), "更新时间不对"
    n_sec = len(re.findall(r"^## §", chk, re.M))
    m2 = re.search(r"(^## 最近更新\n)(.*?)(?=^## )", chk, re.S | re.M)
    bl2 = [l for l in m2.group(2).split("\n") if l.strip()]
    print("[OK] §84 已追加 | 章节总数 = %d | 最近更新行数 = %d | 字节 = %d" % (n_sec, len(bl2), len(chk.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
