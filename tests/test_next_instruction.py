"""test_next_instruction.py — 幂等闸门自测（取最新条目 + last_ack 比对）

验证本模块定时任务的**防重复触发**机制：
  * 解析出所有 EXT-xxx 条目，取编号最大的为最新；
  * 编号 ≤ last_ack ⇒ 判「已执行」；
  * 编号 > last_ack ⇒ 判「需执行」；
  * 文件缺失 / 空 / 不可解析 ⇒ 判「跳过」。

不碰真实文件，全部用临时目录跑。

运行：python tests/test_next_instruction.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_spec = importlib.util.spec_from_file_location(
    "next_instruction",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "tools", "next_instruction.py"))
ni = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ni)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


SAMPLE = """# EXT 模块

## EXT-001 [HIGH] 2026-10-27 15:23 — 启动交接：需求、架构、阶段计划

正文……

## EXT-002 [NORMAL] 2026-10-27 15:48 — FYI：pyannote 只做说话人识别

正文……
"""


def test_parse():
    print("\n[1] 条目解析")
    es = ni.parse_entries(SAMPLE)
    check("解析出 2 条", len(es) == 2, f"{len(es)}")
    check("按编号升序", [e["num"] for e in es] == [1, 2])
    check("最新 = 编号最大 = EXT-002", es[-1]["id"] == "EXT-002", es[-1]["id"])
    check("能取到优先级标签", es[-1]["priority"] == "[NORMAL]", es[-1]["priority"])
    check("能取到时间戳", es[-1]["ts"] == "2026-10-27 15:48", es[-1]["ts"])
    check("能取到标题", "pyannote" in es[-1]["title"], es[-1]["title"])


def test_last_ack():
    print("\n[2] last_ack 解析")
    s = "# STATUS_EXT\nlast_ack: EXT-002\n更新时间: 2026-10-27 16:48\n\n## §1 x\n"
    check("解析 last_ack", ni.parse_last_ack(s) == 2)
    s2 = "# STATUS_EXT\n更新时间: x\n\n## §1 y\nlast_ack: EXT-005\n"
    check("正文里的 last_ack 不被误读（只看头部）", ni.parse_last_ack(s2) is None)
    check("无 last_ack 返回 None", ni.parse_last_ack("# x\n") is None)


def test_gate():
    print("\n[3] 幂等闸门")
    tmp = tempfile.mkdtemp()
    corr = os.path.join(tmp, "CORRECTIONS_EXT.md")
    stat = os.path.join(tmp, "STATUS_EXT.md")
    ni.CORRECTIONS = corr
    ni.STATUS = stat

    # 文件缺失
    check("文件缺失 → skip/exit2", ni.main([]) == 2)

    # 空文件
    open(corr, "w", encoding="utf-8").write("   \n")
    check("空文件 → skip/exit2", ni.main([]) == 2)

    # 不可解析
    open(corr, "w", encoding="utf-8").write("这里没有任何条目\n")
    check("不可解析 → skip/exit2", ni.main([]) == 2)

    # 有条目但无 last_ack → 需执行
    open(corr, "w", encoding="utf-8").write(SAMPLE)
    check("无 last_ack → 判需执行 (exit0)", ni.main([]) == 0)

    # last_ack = 002 → 已执行
    open(stat, "w", encoding="utf-8").write(
        "# STATUS_EXT\nlast_ack: EXT-002\n更新时间: x\n\n## §1 y\n")
    check("last_ack=002 且最新=002 → 已执行 (exit1)", ni.main([]) == 1)

    # last_ack = 001 → 需执行
    open(stat, "w", encoding="utf-8").write(
        "# STATUS_EXT\nlast_ack: EXT-001\n更新时间: x\n")
    check("last_ack=001 且最新=002 → 需执行 (exit0)", ni.main([]) == 0)

    # 新增 EXT-003 → 需执行
    open(corr, "w", encoding="utf-8").write(
        SAMPLE + "\n## EXT-003 [LOW] 2026-10-27 17:00 — 新的指令\n\n正文\n")
    check("新增 EXT-003 → 需执行 (exit0)", ni.main([]) == 0)

    # last_ack 推进到 003 → 已执行
    open(stat, "w", encoding="utf-8").write(
        "# STATUS_EXT\nlast_ack: EXT-003\n更新时间: x\n")
    check("last_ack=003 → 已执行 (exit1)", ni.main([]) == 1)


def test_real_files():
    print("\n[4] 真实文件当前状态")
    ni.CORRECTIONS = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "status", "CORRECTIONS_EXT.md")
    ni.STATUS = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "status", "STATUS_EXT.md")
    rc = ni.main([])
    check("真实项目当前应判「已执行/跳过」（本轮已做完 EXT-002）", rc == 1,
          f"exit={rc}")


def main() -> int:
    print("=" * 68)
    print("幂等闸门自测（不碰真实数据以外的文件）")
    print("=" * 68)
    for fn in (test_parse, test_last_ack, test_gate, test_real_files):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            RESULTS.append((fn.__name__, False, str(e)))
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
