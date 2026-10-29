"""recompute_lag.py — ★ EXT-008：用**新的滞后口径**重算已有实测数据

## 为什么需要这个工具

EXT-008 第 1 点判定：旧口径的 `cumulative_lag_sec` = 22 段余量**求和**
（run7 实测 `-3969.5098`）**不是累计滞后** ⇒ 要求删除，并改成：
  1. **末句滞后**（`last_segment_lag_sec`）
  2. **滞后增长斜率**（对 `(t_start, 排程余量)` 线性拟合）

⇒ run7 的 `margin.json` **已经有**逐段的 `t_start` / `deadline_margin_sec`
   ⇒ 不需要重跑 5 分钟实测（不必再占设备），直接重算即可。

## 用法

    python tools\\recompute_lag.py --margin .tmp\\p1_run7\\margin.json \\
        --out .tmp\\p1_run7\\lag_recompute.json

只读输入、只写新文件 ⇒ **不改原始实测产物**。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT-008 滞后口径重算")
    ap.add_argument("--margin", required=True,
                    help="服务端的 margin.json（含 per_segment）")
    ap.add_argument("--out", default=None, help="重算结果落盘路径")
    args = ap.parse_args(argv)

    with open(args.margin, "r", encoding="utf-8") as f:
        data = json.load(f)

    per_seg = data.get("per_segment") or []
    if not per_seg:
        print("[recompute] ❌ margin.json 里没有 per_segment ⇒ 无法重算")
        return 2

    # 客户端口径（与 p1_pipeline.compute_lag_metrics 同算法）
    from p1_pipeline import compute_lag_metrics
    client_like = [{"t_start": p.get("t_start"),
                    "deadline_margin_sec": p.get("deadline_margin_sec")}
                   for p in per_seg]
    lag_client = compute_lag_metrics(client_like)

    # 服务端口径（与 ext.bridge.summarize_margins 同算法）
    from ext.bridge import decompose_lag, summarize_margins
    summ = summarize_margins(per_seg)
    decomp = decompose_lag(per_seg, delay_sec=10.0)

    out = {
        "source_margin_file": os.path.abspath(args.margin),
        "n_segments": len(per_seg),
        "lag_metrics": lag_client,
        "margin_summary_new": summ,
        "lag_decomposition": decomp,
        "old_cumulative_lag_sec_RETRACTED": (
            (data.get("margin_summary") or {}).get("cumulative_lag_sec")),
        "note": ("旧口径 cumulative_lag_sec 是「22 段余量求和」，"
                 "EXT-008 判定无物理含义 ⇒ 本文件只给新口径，"
                 "旧值仅作对照列出。"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("[recompute] 已落盘：%s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
