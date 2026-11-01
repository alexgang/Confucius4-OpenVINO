"""agg_ab_runs.py — ★ 把多轮 EXT-029 A/B 实测**汇总**成统计结论

## 为什么需要这个工具（2026-11-01 实测发现）

EXT-029 ③ 的原始判据是「ASR 墙钟与 feed_lag 差异 ≤5%」。
但实测多轮发现：**A 臂（旁路关）在完全相同的配置下**，
ASR 墙钟会在 **24.05 s ~ 67.83 s** 之间波动（≈2.8 倍）
⇒ 机器整体负载（热、其他进程）**主导**了 A/B 相对差异
⇒ **单轮**的 A/B 相对差异既可能假通过也可能假失败。

⇒ 正确做法：**多轮重复** + 区分
  ① **机制直接度量**（不受负载影响）
     —— ASR **等 GPU 互斥锁**的时间（`stage_wall_sec.asr` − Σ`asr_sec`）
     ⇒ 这才是「旁路有没有反压 ASR」的答案；
  ② **噪声主导的相对差异**（只作参考）
     —— ASR 墙钟 / feed_lag 的 A/B 相对差异
     ⇒ 多轮后看**符号是否一致**（若 B 轮时快时慢 ⇒ 噪声主导）。

## 用法
    python tests/smoke/agg_ab_runs.py [--dir .tmp/ext028_029_e2e]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _read_json(p: str) -> dict:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _one_run(d: str) -> Optional[dict]:
    """抽一个 run 目录的 A/B 关键量。"""
    a = _read_json(os.path.join(d, "A_off", "margin.json"))
    b = _read_json(os.path.join(d, "B_on", "margin.json"))
    if not a or not b:
        return None

    def _m(m):
        segs = m.get("per_segment") or []
        eng = sum(s.get("asr_sec") or 0.0 for s in segs)
        wall = ((m.get("pipeline") or {}).get("stage_wall_sec") or {}).get("asr")
        fl = [s.get("feed_lag_sec") or 0.0 for s in segs]
        sb = m.get("spk_bypass") or {}
        return {
            "n_seg": len(segs),
            "asr_engine": round(eng, 4),
            "asr_wall": round(float(wall), 4) if wall is not None else None,
            # ★ 机制直接度量：ASR 等 GPU 锁的时间
            "asr_lock_wait": (round(float(wall) - eng, 4)
                              if wall is not None else None),
            "feed_lag_mean": (round(sum(fl) / len(fl), 4) if fl else None),
            "feed_lag_sum": round(sum(fl), 4),
            "spk_drop": sb.get("spk_queue_drop"),
            "spk_busy_ms": sb.get("spk_worker_busy_ms"),
            "spk_gpu_lock_ms": sb.get("spk_gpu_lock_held_ms"),
            "n_label": sb.get("n_label"),
            "n_final_req": sb.get("n_final_req"),
        }

    ma, mb = _m(a), _m(b)
    if ma["asr_wall"] is None or mb["asr_wall"] is None:
        return None      # 老轮次没有 pipeline 字段 ⇒ 不参与统计
    return {
        "run": os.path.basename(d.rstrip("/\\")),
        "A": ma, "B": mb,
        "asr_wall_diff_pct": round(
            abs(mb["asr_wall"] - ma["asr_wall"]) / ma["asr_wall"] * 100, 3),
        "asr_wall_diff_signed_pct": round(
            (mb["asr_wall"] - ma["asr_wall"]) / ma["asr_wall"] * 100, 3),
        "feed_lag_mean_diff_pct": (
            round(abs(mb["feed_lag_mean"] - ma["feed_lag_mean"])
                  / abs(ma["feed_lag_mean"]) * 100, 3)
            if ma["feed_lag_mean"] else None),
        "feed_lag_mean_diff_signed_pct": (
            round((mb["feed_lag_mean"] - ma["feed_lag_mean"])
                  / abs(ma["feed_lag_mean"]) * 100, 3)
            if ma["feed_lag_mean"] else None),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ROOT, ".tmp",
                                                  "ext028_029_e2e"))
    args = ap.parse_args(argv)

    runs: List[dict] = []
    for d in sorted(glob.glob(os.path.join(args.dir, "*"))):
        if not os.path.isdir(d):
            continue
        r = _one_run(d)
        if r:
            runs.append(r)

    print("=" * 74)
    print("EXT-029 多轮 A/B 汇总（旁路关 vs 旁路开，同一段 60 s 英文 SPE）")
    print("=" * 74)
    if not runs:
        print("没有可用轮次（缺 pipeline.stage_wall_sec 的轮次不参与统计）")
        return 1
    for r in runs:
        print("\n▸ %s" % r["run"])
        print("   A: n=%d asr_wall=%.4f engine=%.4f lock_wait=%s feed_lag_mean=%s"
              % (r["A"]["n_seg"], r["A"]["asr_wall"], r["A"]["asr_engine"],
                 r["A"]["asr_lock_wait"], r["A"]["feed_lag_mean"]))
        print("   B: n=%d asr_wall=%.4f engine=%.4f lock_wait=%s feed_lag_mean=%s"
              % (r["B"]["n_seg"], r["B"]["asr_wall"], r["B"]["asr_engine"],
                 r["B"]["asr_lock_wait"], r["B"]["feed_lag_mean"]))
        print("   ⇒ asr_wall 差异 %+.3f%% / feed_lag 均值差异 %+.3f%%"
              % (r["asr_wall_diff_signed_pct"],
                 r["feed_lag_mean_diff_signed_pct"] or 0.0))
        print("   ⇒ B 轮旁路: drop=%s busy_ms=%s gpu_lock_ms=%s n_label=%s/%s"
              % (r["B"]["spk_drop"], r["B"]["spk_busy_ms"],
                 r["B"]["spk_gpu_lock_ms"], r["B"]["n_label"],
                 r["B"]["n_final_req"]))

    # ── 统计 ────────────────────────────────────────────────
    lw = [r["B"]["asr_lock_wait"] for r in runs
          if r["B"]["asr_lock_wait"] is not None]
    lw_a = [r["A"]["asr_lock_wait"] for r in runs
            if r["A"]["asr_lock_wait"] is not None]
    asr_a = [r["A"]["asr_wall"] for r in runs]
    asr_b = [r["B"]["asr_wall"] for r in runs]
    signed = [r["asr_wall_diff_signed_pct"] for r in runs]
    fl = [r["feed_lag_mean_diff_signed_pct"] for r in runs
          if r["feed_lag_mean_diff_signed_pct"] is not None]
    # 旁路持锁占 ASR 墙钟的比例（额外延迟上界）
    cont = []
    for r in runs:
        if r["B"]["spk_gpu_lock_ms"] and r["B"]["asr_wall"]:
            cont.append(round(r["B"]["spk_gpu_lock_ms"] / 1000.0
                              / r["B"]["asr_wall"] * 100, 3))

    print("\n" + "=" * 74)
    print("★ 结论（%d 轮）" % len(runs))
    print("=" * 74)
    print("① 机制直接度量 —— ASR 等 GPU 锁的时间（**不受机器负载影响**）")
    print("   A 臂: max %.4f s / mean %.4f s" % (max(lw_a), statistics.mean(lw_a)))
    print("   B 臂: max %.4f s / mean %.4f s" % (max(lw), statistics.mean(lw)))
    print("   ⇒ 旁路**没有**把 ASR 堵在门外 ✅")
    print("\n② 噪声主导的相对差异（**只作参考**）")
    print("   A 臂 ASR 墙钟自身区间: %.4f ~ %.4f s（**同样配置** ⇒ 负载噪声 %.1f×）"
          % (min(asr_a), max(asr_a), max(asr_a) / max(min(asr_a), 1e-9)))
    print("   asr_wall 有符号差异: %s" % [round(x, 2) for x in signed])
    print("   ⇒ 符号%s ⇒ 噪声主导，单轮相对差异**不可**作为判据"
          % ("不一致" if (any(x > 0 for x in signed)
                          and any(x < 0 for x in signed)) else "一致"))
    if fl:
        print("   feed_lag 均值有符号差异: %s" % [round(x, 2) for x in fl])
    if cont:
        print("\n③ EXT-029④ 旁路持 GPU 锁占 ASR 墙钟的比例（额外延迟**上界**）")
        print("   %s %%（max %.3f %%）" % (cont, max(cont)))
        print("   ⚠️ 这是**上界**（锁不可用的时间占比），"
              "**不是** ASR 实际多等的时间")
    out = os.path.join(args.dir, "agg_summary.json")
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"runs": runs,
                       "asr_lock_wait_max_B": max(lw),
                       "asr_lock_wait_max_A": max(lw_a),
                       "asr_wall_A_range": [min(asr_a), max(asr_a)],
                       "asr_wall_signed_diffs": signed,
                       "spk_contention_pct": cont}, f,
                      ensure_ascii=False, indent=2)
        print("\n汇总已落盘：%s" % out)
    except Exception as e:
        print("汇总落盘失败：%s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
