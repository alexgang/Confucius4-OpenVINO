# -*- coding: utf-8 -*-
"""App §85 落盘脚本：只追加章节 + 改头部 4 字段行。

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
SECTION = r"C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app85_status_section.md"

TS = "2026-10-28 16:27"  # Get-Date 实测值（非推算）
LAST_ACK = "APP-033"


def main():
    with io.open(STATUS, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    assert "\r\n" not in text, "STATUS 出现 CRLF，脚本假设 LF"

    # --- 前置校验：确认 §85 尚未落盘（幂等保护）---
    if re.search(r"^## §85\b", text, re.M):
        print("[SKIP] §85 已存在于 STATUS_APP.md，本次不重复追加")
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
        "当前任务: **§85 🔴🔴 客户包 `NOTICE` / `THIRD_PARTY.md` 许可不实表述已修正"
        "（原称「所有组件均为 Apache License 2.0」且 `num2words MIT` ⇒ 实测 `num2words` 为 **LGPL-2.1**；"
        "两文件合计只覆盖包内 47 个 vendored 分发包的 10/28 个 ⇒ 已逐包实测重写为 **47/47 全覆盖**，"
        "每包附随包许可证全文真实路径）＋ ASR 的 WeSpeaker CC BY 4.0 署名义务判定为**免除**"
        "（包内 0 个 wespeaker/权重文件、site-packages 无 torch/pyannote/speechbrain ⇒ 走「不带」分支）"
        "⇒ 已回告 ASR（`shared/NOTICE_app_to_asr_wespeaker_license_reply_20261028.md`）"
        "＋ 验收 `app124` **12 PASS / 0 FAIL** ＋ 反证 `app125` **10 PASS / 0 FAIL**"
        "（反证中抓出**判据自身 2 处缺陷**：G7 过弱致假通过 / G7 过严致误伤说明句）"
        "⇒ ✅ **本条已完成**（客户包文件侧 + 回告侧）⇒ 🔴 **本条需等 reviewer 复核**"
        "（旧 NOTICE 是否已随 v1.6 zip 分发出去、`tokenizers` 无随包许可证是否补全文、"
        "`pillow` 多许可口径、多许可第三方条款是否逐条摘录）"
        "＋ ⛔ **zip 未重打 ⇒ 不写「已交付」**（`NOTICE` 在 zip 内 ⇒ 本次修改进入下次打包；"
        "APP-031 要求 APP-027 的 V1–V4 合打，V4 用户实听未做）"
    )
    lines = set_field(lines, "当前任务:", task_line)

    block_line = (
        "阻塞 / 待用户决定: ① 🔴 **§84 的 APP-027 V3（克隆）机器判据已过**"
        "（CUDA 20 PASS / 0 FAIL、NPU 20 PASS / 0 FAIL；两组各 76 句 wav、逐句含音色来源字段、"
        "隐私判据 `clone_leaks` / `tmp_clone_residue` 均空；独立复核 wav↔id 76/76、SHA256 76/76 两组全中）"
        "⇒ 【本模块侧已完成】；② 🔴 **V3-CER（MiniMax 回转写）与 V3-CAMPPlus（CAMPPlus 余弦）仍归 reviewer**"
        "（§84 判据标 `[NO-EVIDENCE]`）⇒ APP-027 **仍未完**；③ 🔴 **V4 用户实听未做**"
        "（本轮是 CLI 回放 + 真实播放路径，走声卡，机器判据 `consumed=True` 76/76 + `read_delta ≥ n_samples` + 无 `consumed=False`，"
        "**但人耳未确认** ⇒ 「用户听得到」仍不成立）；④ 🔴 **§85 的 `NOTICE` 修正已进入「下次打包」**"
        "（`NOTICE` 在 zip 内）⇒ **旧的 v1.6 zip 若已分发，即带过不实许可声明** ⇒ "
        "**是否需要重打并重新分发，待 reviewer 裁定**（App 不自行决定，受 APP-031 合打约束）；"
        "⑤ ⛔ **zip 未重打**（APP-031 明文「三项做完后合在一起重打一次包」）⇒ 按 §66 口径 **不写「已交付」**"
        "（准确表述：**代码侧已入库、已同步到包目录；zip 未重打**）；⑥ 🔴 **§84 缺陷②的连带影响**："
        "V1/V2 两轮报告（真实播放路径）的 `lang`/`end_reason` 字段原本缺失 ⇒ 若要补「按语言分组」的字段"
        "需用修好后的代码重跑（本轮**未重跑**）；⑦ 🔴 **§83.5 的 4 项裁定仍然有效**"
        "（RTF 归因边界 / 「首包」指标定义 / app062 A/B 是否重做 / 不变式是否改三段式）"
        "⇒ 本轮**未自行推进**；⑧ 🔴 **MT notice 15 §3.4 的真实时序「草稿行计数」端到端证据缺口** 仍是 App 侧遗留项；"
        "⑨ 🔴 **本轮未修改 `CORRECTIONS_APP.md`**（只读、零改动）、未向 MiniMax、未开 FTP、"
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
        "%s §85 🔴🔴 **客户包 `NOTICE`/`THIRD_PARTY.md` 许可不实表述已修正（num2words 实为 **LGPL-2.1** 非 MIT；"
        "原「所有组件均为 Apache-2.0」不实；覆盖 10/28 ⇒ **47/47 全覆盖**）＋ ASR WeSpeaker 署名义务判定**免除**并回告**"
        "⇒ ✅ `app124` 12 PASS/0 FAIL ＋ `app125` 反证 10 PASS/0 FAIL（抓出判据自身 2 处缺陷）"
        "⇒ ⛔ `NOTICE` 在 zip 内 ⇒ 修改进入下次打包、**本轮 zip 未重打 ⇒ 不写「已交付」**" % TS[11:16]
    )
    blines.insert(0, new_entry)
    while len(blines) > 15:
        blines.pop()
    text = text[: m.start(2)] + "\n".join(blines) + "\n\n" + text[m.end(2):]

    # --- 追加 §85 章节到文件末尾 ---
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + sec.rstrip("\n") + "\n"

    with io.open(STATUS, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    # --- 写后复核 ---
    with io.open(STATUS, "r", encoding="utf-8", newline="") as f:
        chk = f.read()
    assert "\r\n" not in chk, "写盘后出现 CRLF"
    assert re.search(r"^## §85\b", chk, re.M), "§85 未落盘"
    assert re.search(r"^last_ack: APP-033$", chk, re.M), "last_ack 不对"
    assert re.search(r"^更新时间: %s$" % re.escape(TS), chk, re.M), "更新时间不对"
    n_sec = len(re.findall(r"^## §", chk, re.M))
    m2 = re.search(r"(^## 最近更新\n)(.*?)(?=^## )", chk, re.S | re.M)
    bl2 = [l for l in m2.group(2).split("\n") if l.strip()]
    print("[OK] §85 已追加 | 章节总数 = %d | 最近更新行数 = %d | 字节 = %d" % (n_sec, len(bl2), len(chk.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
