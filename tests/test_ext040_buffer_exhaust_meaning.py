# -*- coding: utf-8 -*-
"""test_ext040_buffer_exhaust_meaning.py — EXT-040 ② 的自测

## EXT-040 原文（2026-11-06 08:10，[NORMAL]）

> ② signed_err 在 128–157 s 间已 >20 s，最大 22.7 s，之后随源语音结束回落到 16.7 s。
>    "20 s 缓冲耗尽"在数据里的物理含义没有写清：
>    signed_err = actual − (t0 + tStart + D) 是配音相对"已延迟 D 的画面"晚了多少；>0 即配音落后画面。
>    请在 STATUS 用一句话写明：耗尽后**画面是否继续按 D 播放而配音落后**（口型/语义不同步，如实现状），
>    还是**画面会被暂停/再缓冲**；现数据只证明"配音落后画面、不丢句、不静音"。
> **要求**：仅 ② 的一句话说明（≤1 条 STATUS 记录），不需要新 e2e。验收：STATUS 有该说明。

## 本文件要验什么

① **STATUS 确实有那句话**（且口径不与代码矛盾）；
② **那句话依赖的代码不变量仍然成立**（否则 STATUS 会悄悄变成假话）：
   - `delaySec`（= D）是**常量**：运行期没有 `+=`/`-=` 之类改写，且 `setDelay()` **无调用者**
     ⇒ D 永远不会自动变大；
   - 画面侧目标时刻 = `(t0 + 帧时刻) + D` ⇒ **画面时间轴固定在 D**；
   - 原声侧 `DelayNode.delayTime.value = D` ⇒ **原声也固定在 D**；
   - **全仓无 `.pause()` / rebuffer / stall 逻辑** ⇒ 「画面不会被暂停或再缓冲」成立；
   - 配音侧只有「钳位（clamp）」与「顺延（reschedule）」，**没有丢弃分支** ⇒ 「不丢句」成立；
③ ★ **区分力**：把 STATUS 里那句话的**任一必需措辞**替换掉 ⇒ 判定必须转为 FAIL
   （否则就是一个"永远 PASS"的假守卫）；
④ 数字与**落盘产物**逐位对齐（产物在 `.tmp/`（不入库）；不存在时明确报 SKIP，**不**判 PASS）。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器 / 不需要 e2e。

运行：
    python tests/test_ext040_buffer_exhaust_meaning.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(ROOT, "status", "STATUS_EXT.md")
PLAYER = os.path.join(ROOT, "extension", "player.js")
EXT_DIR = os.path.join(ROOT, "extension")
PY_DIR = os.path.join(ROOT, "ext")
RUN_DIR = os.path.join(ROOT, ".tmp", "ext033_e2e", "20261105_174558")

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                            ("  -- %s" % detail) if detail else ""))


def skip(name: str, detail: str = "") -> None:
    print("  [SKIP] %s%s" % (name, ("  -- %s" % detail) if detail else ""))


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── 那句话的「必需措辞」清单（缺一条 ⇒ 判定 FAIL）──────────────
#   评审原话要求写明的是**二选一**：画面继续按 D 播 + 配音落后，
#   **还是**画面被暂停/再缓冲 ⇒ 必须同时出现"不会暂停/不再缓冲"与"落后画面"。
REQUIRED_TOKENS = (
    "耗尽",            # 主题词
    "落后画面",        # 配音相对「已延迟 D 的画面」落后
    "不丢句",          # 现数据只证明的部分
    "不静音",          # 现数据只证明的部分
    "排队",            # 耗尽后的实际行为：不丢句地排队
    "不会暂停",        # 画面侧**不是**暂停
    "不会再缓冲",      # 画面侧**不是**再缓冲
)

# 产物核对用的期望值（来自 run `20261105_174558` 的 metrics.json）
EXPECT_ARTIFACT = {
    "delaySec": 20,
    "dubPcmDropped": 0,
    "dubDup": 0,
    "dubRescheduled": 23,
    "dubRescheduleDelaySec": 37.129,
}


# ── ① STATUS 的那句话 ────────────────────────────────────────
def status_sentence_ok(text: str):
    """判定 STATUS 里是否存在 EXT-040 ② 要求的那句话。

    返回 (ok, detail)。**必须**能被"篡改措辞"打掉（见 ③ 的区分力测试），
    所以这里用**逐个必需措辞**判定，而不是"有没有一段像样的话"。
    """
    head = text.split("\n## ", 1)[0]
    if "last_ack: EXT-040" not in head:
        return False, "头部 last_ack 未推进到 EXT-040"
    if "## §33" not in text:
        return False, "没有 §33 章节"
    missing = [t for t in REQUIRED_TOKENS if t not in text]
    if missing:
        return False, "缺少必需措辞 %s" % missing
    if "20261105_174558" not in text:
        return False, "没有引用本轮的 run 目录（结论无来源）"
    return True, "必需措辞齐全（%d 项）" % len(REQUIRED_TOKENS)


def test_status_sentence() -> None:
    check("STATUS_EXT.md 存在", os.path.isfile(STATUS))
    if not os.path.isfile(STATUS):
        return
    text = read(STATUS)
    ok, detail = status_sentence_ok(text)
    check("STATUS 里有 EXT-040 ② 要求的那句说明", ok, detail)
    check("STATUS §33 引用了 run `20261105_174558`",
          "20261105_174558" in text)
    check("STATUS 头部 last_ack = EXT-040",
          re.search(r"^last_ack:\s*EXT-040\s*$", text.split("\n## ", 1)[0],
                    re.MULTILINE) is not None)
    # 那句话必须**明确否认**「画面暂停/再缓冲」，否则与代码矛盾。
    #   ⇒ 若出现「画面**会/将/被**暂停」这类**肯定式**表述 ⇒ FAIL。
    #   ⚠️ 否定式「**不**会暂停」是**要求的内容**，不能被误判。
    #   ⇒ 用**否定 tempered pattern**：`画面` 与 `会/将/被` 之间**不许出现「不」**，
    #     这样「画面照旧按固定 D 播放（不会暂停…」不会命中，
    #     而「画面会被暂停」会命中。
    contradiction = re.search(r"画面[^。；\n不]{0,20}(会|将|被)暂停", text)
    check("STATUS 未出现与代码矛盾的「画面会被暂停」表述",
          contradiction is None,
          ("命中：%s" % contradiction.group(0)) if contradiction else "")
    contradiction2 = re.search(r"画面[^。；\n不]{0,20}(会|将|被)再缓冲", text)
    check("STATUS 未出现与代码矛盾的「画面会被再缓冲」表述",
          contradiction2 is None,
          ("命中：%s" % contradiction2.group(0)) if contradiction2 else "")


# ── ② 那句话依赖的代码不变量 ────────────────────────────────
def test_code_invariants() -> None:
    check("extension/player.js 存在", os.path.isfile(PLAYER))
    if not os.path.isfile(PLAYER):
        return
    src = read(PLAYER)

    # ── D 是常量：运行期没有 `delaySec +=` / `-=` 之类改写 ──
    mutating = re.findall(r"delaySec\s*(?:\+=|-=|\*=|/=)", src)
    check("delaySec 没有运行期自增/自减（%s）" % (mutating or "无"),
          not mutating, "源码里出现改写 D 的写法")

    # ── setDelay() 没有调用者（D 不会被人为调大）──
    callers = []
    for dirpath, _dirs, files in os.walk(EXT_DIR):
        for fn in files:
            if not fn.endswith(".js"):
                continue
            p = os.path.join(dirpath, fn)
            if os.path.abspath(p) == os.path.abspath(PLAYER):
                continue
            if re.search(r"setDelay\s*\(", read(p)):
                callers.append(os.path.relpath(p, ROOT))
    # player.js 内部：只有定义处，没有调用处
    inner = re.findall(r"setDelay\s*\(", src)
    # 定义处是 `setDelay: (d) => {...}`，不含 `setDelay(` ⇒ inner 即调用点数
    check("setDelay() 在 extension/ 内无调用者（%d 处调用）" % len(inner),
          not inner and not callers,
          "调用点：%s" % (inner or callers))

    # ── 画面侧目标时刻含 + D ──
    check("画面侧目标时刻 = (t0 + 帧时刻) + delaySec",
          re.search(r"const\s+target\s*=\s*\(\s*t0\s*\+\s*[\w.]+\s*/\s*1e6\s*\)\s*\+\s*delaySec",
                    src) is not None,
          "找不到 onDecodedFrame 里的 target 公式")

    # ── 原声侧 DelayNode 固定在 D ──
    check("原声 DelayNode.delayTime.value = delaySec",
          re.search(r"origDelay\.delayTime\.value\s*=\s*delaySec", src) is not None)

    # ── 全仓无 .pause() / rebuffer ⇒ 画面不会被暂停或再缓冲 ──
    hits = []
    for base in (EXT_DIR, PY_DIR):
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if not (fn.endswith(".js") or fn.endswith(".py")):
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, ROOT)
                for i, line in enumerate(read(p).split("\n"), 1):
                    code = line.split("//")[0] if not line.strip().startswith("#") else ""
                    if ".pause(" in code or re.search(r"\brebuffer\b", code, re.I):
                        hits.append("%s:%d" % (rel, i))
    check("extension/ 与 ext/ 内无 .pause() / rebuffer 代码（%s）" % (hits or "无"),
          not hits, "命中：%s" % hits)

    # ── 配音侧只有钳位 / 顺延，没有丢弃分支 ──
    #   ⚠️ 判据必须**排除** `pendingSched` 的裁剪：那是**排程记账表**
    #     （记录"计划何时播"以便事后量误差）的有界化，
    #     **不丢音频** —— 音频在 `src.start(when)` 那一刻就已经交给
    #     WebAudio 播放队列了，裁剪记账表不影响已排程的音频。
    #     ⇒ 只看**会真正影响播放**的丢弃信号：
    #        `metrics.dubPcmDropped`（PCM 搬运丢包）/ `dubDup`（重复丢弃）/
    #        `dropped`（上行丢帧）。
    m = re.search(r"function\s+scheduleDub\s*\(msg\)\s*\{", src)
    check("能找到 scheduleDub()", m is not None)
    if m:
        body = src[m.start():m.start() + 6000]
        body = body.split("\nfunction ", 1)[0]
        has_clamp = "schedClamped" in body
        has_resched = "dubRescheduled" in body
        # ★ 真正的"丢弃"信号：**丢音频/丢段**，而不是丢记账表的条目。
        #   `dubPcmDropped` = PCM 搬运丢包；`dubDup` = 重复段被去重丢掉；
        #   `metrics.dropped` = 上行丢帧。
        #   ⚠️ 必须排除 `pendingSched` / `adaptSpeedHistory` 的有界化裁剪：
        #     那是**事后量误差用的记账表**，音频在 `src.start(when)` 那一刻
        #     就已交给 WebAudio 播放队列 ⇒ 裁剪记账表**不丢音频**。
        scan = body
        for var in ("pendingSched", "adaptSpeedHistory"):
            scan = re.sub(r"if\s*\(\s*" + var + r"\.length[^)]*\)\s*\{[^}]*\}",
                          "", scan, flags=re.S)
        drop_signals = re.findall(
            r"dubPcmDropped|dubDup\b|metrics\.dropped\b|"
            r"metrics\.\w*[Dd]rop\w*\s*=", scan)
        check("scheduleDub 有钳位路径（schedClamped）", has_clamp)
        check("scheduleDub 有顺延路径（dubRescheduled）", has_resched)
        check("scheduleDub 无真正的丢弃分支（%s）" % (drop_signals or "无"),
              not drop_signals, "命中：%s" % drop_signals)
        # ★ 反向守卫：scheduleDub 必须**真的**调用 src.start()
        #   （否则「不丢句」就无从谈起）
        check("scheduleDub 调用 src.start()（音频真的交给播放队列）",
              re.search(r"src\.start\s*\(", body) is not None)
        # ★ 且 src.start 的时刻必须是 when（顺延后的实际时刻），不是 planned
        check("src.start() 用的是顺延后的 when（而非原定 planned）",
              re.search(r"src\.start\s*\(\s*when\s*\)", body) is not None)
        # ★ 排除掉记账表裁剪后，body 里应当**一次都没有** drop 动词的赋值
        check("排除记账表裁剪后 scheduleDub 无任何 drop 赋值",
              re.search(r"\b\w*[Dd]rop\w*\s*=\s*(?!0\b)[^=]", scan) is None,
              "命中：%s" % re.findall(r"\b\w*[Dd]rop\w*\s*=[^;\n]*", scan))


# ── ④ 数字与落盘产物逐位对齐 ────────────────────────────────
def test_artifact_alignment() -> None:
    mpath = os.path.join(RUN_DIR, "metrics.json")
    if not os.path.isfile(mpath):
        skip("落盘产物核对",
             "%s 不存在（.tmp/ 不入库）⇒ 本项不判定" % RUN_DIR)
        return
    m = json.loads(read(mpath))
    m = m.get("metrics", m)
    for k, want in EXPECT_ARTIFACT.items():
        got = m.get(k)
        ok = (got is not None) and (abs(float(got) - float(want)) < 1e-6)
        check("产物 metrics.json 的 %s == %s（实测 %s）" % (k, want, got), ok)
    # STATUS 里引用的数字必须与产物一致
    text = read(STATUS)
    check("STATUS §33 引用的顺延总时长 37.129 s 与产物一致",
          "37.129" in text)
    check("STATUS §33 引用的顺延次数 23 与产物一致",
          re.search(r"(?<!\d)23(?!\d)", text) is not None)


# ── ③ 区分力：篡改措辞 ⇒ 必须 FAIL ──────────────────────────
def test_discrimination() -> None:
    text = read(STATUS)
    base_ok, _ = status_sentence_ok(text)
    if not base_ok:
        check("区分力前置条件（原始 STATUS 判定为通过）", False,
              "原始 STATUS 就不通过，无法做变异测试")
        return
    # ⚠️ 必须替换**全部**出现（`replace` 不加 count）——
    #   只换第一个的话，同一措辞在别处仍存在 ⇒ 判定仍是 PASS
    #   ⇒ 这种变异测试**测不出守卫的有效性**（假通过）。
    for token in REQUIRED_TOKENS:
        mutated = text.replace(token, "「已被篡改」")
        ok, _detail = status_sentence_ok(mutated)
        check("变异：把「%s」全部改掉后必须判 FAIL" % token, not ok)
    # 再测一次"篡改 run 目录"⇒ 也必须 FAIL
    mutated = text.replace("20261105_174558", "20990101_000000")
    ok, _detail = status_sentence_ok(mutated)
    check("变异：把 run 目录全部改掉后必须判 FAIL", not ok)
    # ★ 负向对照：把 last_ack 改回去 ⇒ 必须 FAIL（否则闸门会重复认领）
    mutated = text.replace("last_ack: EXT-040", "last_ack: EXT-039", 1)
    ok, _detail = status_sentence_ok(mutated)
    check("变异：把 last_ack 改回 EXT-039 后必须判 FAIL", not ok)


def main() -> int:
    print("=" * 72)
    print("EXT-040 自测：缓冲耗尽的物理含义（STATUS 那句话 + 代码不变量 + 产物对齐）")
    print("=" * 72)
    for fn in (test_status_sentence, test_code_invariants,
               test_artifact_alignment, test_discrimination):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            RESULTS.append((fn.__name__, False, str(e)))
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 72)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    if nfail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(" - %s -- %s" % (name, detail))
    print("=" * 72)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
