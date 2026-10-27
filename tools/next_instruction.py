"""next_instruction.py — 解析纠偏文件，取**最新一条**指令并与 last_ack 比对

这是本模块定时任务的**幂等闸门**：把「取最新编号 + 判断是否已执行」
从「靠人读」变成「靠代码判」，避免重复执行与无限循环。

用法：
    python tools/next_instruction.py            # 打印判定结果（退出码 0=有未执行的新指令）
    python tools/next_instruction.py --json     # 机器可读输出

退出码：
    0  → 有未执行的新指令（应执行本轮）
    1  → 无新指令（已执行过，跳过本轮）
    2  → 文件不存在 / 为空 / 无法解析（跳过本轮，不做任何改动）

规则：
  * 指令条目形如 `## EXT-002 [NORMAL] 2026-10-27 15:48 — 标题`；
  * 取**编号最大**的一条为最新（编号即时间序）；
  * 编号 ≤ `STATUS_EXT.md` 头部的 `last_ack` ⇒ 已执行过 ⇒ 跳过。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORRECTIONS = os.path.join(ROOT, "status", "CORRECTIONS_EXT.md")
STATUS = os.path.join(ROOT, "status", "STATUS_EXT.md")

# `## EXT-002 [NORMAL] 2026-10-27 15:48 — 标题`
ENTRY_RE = re.compile(
    r"^##\s+(EXT-(\d+))\s*(\[[^\]]*\])?\s*"
    r"(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)?\s*[—\-–:：]?\s*(.*)$",
    re.MULTILINE,
)
LAST_ACK_RE = re.compile(r"^last_ack:\s*EXT-(\d+)\s*$", re.MULTILINE)


def parse_entries(text: str) -> list[dict]:
    """解析所有 EXT-xxx 条目，按编号升序返回。"""
    out = []
    for m in ENTRY_RE.finditer(text):
        out.append({
            "id": m.group(1),
            "num": int(m.group(2)),
            "priority": (m.group(3) or "").strip(),
            "ts": (m.group(4) or "").strip(),
            "title": m.group(5).strip(),
            "start": m.start(),
            "end": m.end(),
        })
    out.sort(key=lambda e: e["num"])
    return out


def parse_last_ack(text: str):
    """从 STATUS 头部解析 last_ack 编号；解析不到返回 None。"""
    head = text.split("\n## ", 1)[0]
    m = LAST_ACK_RE.search(head)
    return int(m.group(1)) if m else None


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="取最新一条 EXT 指令并判幂等")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # ── 文件存在性 / 空文件检查 ──────────────────────────────
    if not os.path.isfile(CORRECTIONS):
        msg = f"纠偏文件不存在：{CORRECTIONS} ⇒ 跳过本轮，不做任何改动"
        if args.json:
            print(json.dumps({"action": "skip", "reason": "missing_file",
                              "path": CORRECTIONS}, ensure_ascii=False))
        else:
            print(msg)
        return 2

    try:
        text = read(CORRECTIONS)
    except Exception as e:
        msg = f"纠偏文件读取失败：{e} ⇒ 跳过本轮，不做任何改动"
        if args.json:
            print(json.dumps({"action": "skip", "reason": "read_error",
                              "detail": str(e)}, ensure_ascii=False))
        else:
            print(msg)
        return 2

    if not text.strip():
        msg = "纠偏文件为空 ⇒ 跳过本轮，不做任何改动"
        if args.json:
            print(json.dumps({"action": "skip", "reason": "empty"},
                             ensure_ascii=False))
        else:
            print(msg)
        return 2

    entries = parse_entries(text)
    if not entries:
        msg = "无法从纠偏文件解析出任何 EXT-xxx 条目 ⇒ 跳过本轮，不做任何改动"
        if args.json:
            print(json.dumps({"action": "skip", "reason": "unparsable"},
                             ensure_ascii=False))
        else:
            print(msg)
        return 2

    latest = entries[-1]

    # ── last_ack ────────────────────────────────────────────
    last_ack = None
    if os.path.isfile(STATUS):
        try:
            last_ack = parse_last_ack(read(STATUS))
        except Exception:
            last_ack = None
    if last_ack is None:
        msg = ("STATUS_EXT.md 的 last_ack 解析不到 ⇒ 视为「尚未执行任何指令」，"
               "按最新条目执行")
        if args.json:
            print(json.dumps({"action": "execute", "latest": latest,
                              "last_ack": None, "note": msg},
                             ensure_ascii=False))
        else:
            print(msg)
            print(f"最新指令：{latest['id']} {latest['ts']} {latest['title']}")
        return 0

    if latest["num"] <= last_ack:
        msg = (f"最新指令 {latest['id']} 已被执行过（last_ack=EXT-{last_ack:03d}）"
               f" ⇒ 跳过本轮，不做任何改动")
        if args.json:
            print(json.dumps({"action": "skip", "reason": "already_executed",
                              "latest": latest, "last_ack": last_ack},
                             ensure_ascii=False))
        else:
            print(msg)
        return 1

    if args.json:
        print(json.dumps({"action": "execute", "latest": latest,
                          "last_ack": last_ack,
                          "n_entries": len(entries)},
                         ensure_ascii=False))
    else:
        print(f"最新指令：{latest['id']} {latest['priority']} {latest['ts']} "
              f"— {latest['title']}")
        print(f"last_ack = EXT-{last_ack:03d} ⇒ 本轮需执行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
