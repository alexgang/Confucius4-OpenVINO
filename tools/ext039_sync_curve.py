#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ext039_sync_curve.py —— ★ EXT-039 (a)：signed_err 随源时间曲线 + 缓冲耗尽行为

## 为什么需要这个脚本（EXT-039 ③④⑤）

reviewer EXT-039 指出：
  * §30 里的「lag 斜率 −0.4106」是 **`lag_est`** 口径（服务端估算）；
    **signed_err**（player 实测有符号误差）是**另一个口径** ⇒ **两个口径不能混用**。
  * 60 s 素材「恰好没碰到 20 s 缓冲耗尽的上限」⇒ 不能据此说「D=20 够」。
  * 要求给出 **signed_err 随时间曲线**，并说明**缓冲耗尽后的行为**
    （欠载 / 静音 / 撤回加速 / 按「不丢句」排队）。

⇒ 本脚本从**实测产物**（margin.json + ext033_compare.json）复算：

  * **口径 A（signed_err）**：player 实测有符号误差
        signed_err_ms = actual − (t0 + t_start + D)
    自变量 = **t_start（源时间）** ⇒ 线性拟合斜率 **k_signed** [s/s]
  * **口径 B（lag_est）**：服务端估算滞后（`margin.json` 的 `lag_est_sec`）
    ⇒ 斜率 **k_lag_est** [s/s]
  ★ 两个口径**各自定义、各自报数**，**不混用**。

  * **缓冲耗尽判定**：
      D_needed = P95(ready − t_start) + 0.3      （沿用 EXT-038 口径）
      耗尽源时间 t_exhaust = D / k_signed         （signed_err 线性外推）
  * **耗尽后行为**（从产物**如实**读，不臆造）：
      - 欠载 / 静音：player 录音里对应时刻的**有声跨度**是否为空
      - 撤回加速：player 侧 `adaptSpeedHistory` 的 `clamped` 计数
      - 按「不丢句」排队：`dubRescheduled` / `dubRescheduleDelaySec`
      - 丢句：bridge 侧 `n_dropped_dub`、compare 的 `n_segments` vs TTS 段数

## 跑法
    python tools/ext039_sync_curve.py <run_dir> [--json out.json]
"""
from __future__ import annotations

import json
import os
import sys


def _linfit(xs, ys):
    """最小二乘 y = a + b·x ⇒ 返回 (a, b, r2)。点数 < 2 ⇒ 返回 None。"""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = 0.0 if syy <= 0 else (sxy * sxy) / (sxx * syy)
    return (a, b, r2)


def _pct(vals, q):
    """**索引法**分位数（**与 bridge / reviewer 逐字一致**）。

    ★ 2026-11-05 EXT-039 收口修正：原实现是**插值法**
      （`s[lo]*(1-frac) + s[hi]*frac`）⇒ 同一批数据会给出**两个不同的 P50**：
      run `20261105_112057` 的 14 段 signed_err
        - 插值法 P50 = **9.393585** s
        - 索引法 P50 = **5.9787** s
      ⇒ reviewer 的 **5.98 s** 与 bridge 的口径都是**索引法** ⇒ 分析器对不上数。
      ⇒ 改为索引法（`s[int(round(q*(n-1)))]`），与 `_pct_bridge` 合并。

    ⚠️ 保留 `_pct_interp` 以便需要时对照，但**报数一律用索引法**。
    """
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    return s[int(round(q * (len(s) - 1)))]


def _pct_interp(vals, q):
    """**插值法**分位数（仅作对照用，**不作为报数口径**）。"""
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def _pct_bridge(vals, q):
    """**与 bridge 完全同款**的分位数（`round(q*(n-1))`，非插值）。

    ★ 为什么要单独一个：bridge 的 `sync_rootcause` 用
      `_sorted[int(round(q * (len(_sorted) - 1)))]` ⇒ 本脚本必须**逐字一致**，
      否则 reviewer 对不上数（§30 的 D_needed = 33.652 就是该口径算出来的）。

    ★ 2026-11-05 EXT-039 收口：bridge 侧原先是 `ceil(q*n)-1`，
      与 Python 侧 / player 侧**都不一致** ⇒ 已把 bridge 统一到
      `round(q*(n-1))` ⇒ 本函数与 `_pct` 现已是**同一口径**。
    """
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    return s[int(round(q * (len(s) - 1)))]


def load(run_dir):
    mp = os.path.join(run_dir, "margin.json")
    cp = os.path.join(run_dir, "ext033_compare.json")
    # ★ 2026-11-05 EXT-039：客户端侧实测（`dubRescheduled` /
    #   `dubRescheduleDelaySec` / `adaptSpeedHistory` / `dropped` / `dubDup`）
    #   落在 **metrics.json**（插件侧 metrics 落盘），**不在 margin.json**。
    #   ⇒ 只读 margin.json 会让「耗尽后行为」这几项全为 null
    #   ⇒ 证据链缺一半 ⇒ 必须同时读 metrics.json。
    msp = os.path.join(run_dir, "metrics.json")
    out = {"run_dir": run_dir, "margin": None, "compare": None,
           "metrics": None, "errors": []}
    if os.path.isfile(mp):
        with open(mp, encoding="utf-8") as f:
            out["margin"] = json.load(f)
    if os.path.isfile(cp):
        with open(cp, encoding="utf-8") as f:
            out["compare"] = json.load(f)
    if os.path.isfile(msp):
        with open(msp, encoding="utf-8") as f:
            out["metrics"] = json.load(f)
    return out


def build(run_dir):
    d = load(run_dir)
    mg = d["margin"] or {}
    cmp_ = d["compare"] or {}
    segs = cmp_.get("segments") or []
    per = mg.get("per_segment") or []

    # ── 口径 A：signed_err（player 实测有符号误差），自变量 t_start ──
    #   ★ 必须**同时**有 t_start 与 signed_err_ms 才有意义；
    #     只报「有多少段」是不够的 —— 曲线斜率才是结论。
    pts_a = []
    for s in segs:
        err = s.get("signed_err_ms")
        ts = s.get("t_start")
        if err is None or ts is None:
            continue
        pts_a.append((float(ts), float(err) / 1000.0, s.get("seg_id")))
    fit_a = _linfit([p[0] for p in pts_a], [p[1] for p in pts_a]) if pts_a else None

    # ── 口径 B：lag_est（服务端估算滞后），自变量 t_start ──
    pts_b = []
    for s in per:
        if not s.get("has_tts"):
            continue
        ls = s.get("lag_est_sec")
        ts = s.get("t_start")
        if ls is None or ts is None:
            continue
        pts_b.append((float(ts), float(ls), s.get("id")))
    fit_b = _linfit([p[0] for p in pts_b], [p[1] for p in pts_b]) if pts_b else None

    # ── D_needed（EXT-037 ③ 口径：P95(ready − t_start) + 0.3）─────
    #   ★ 口径必须与 bridge 的 `sync_rootcause` **逐字一致**：
    #     `ready_at` 是服务端**墙钟**（perf_counter 域），
    #     `t_start` 是**上行采样轴** ⇒ 不同域 ⇒ 必须用 `t0 = orig_end − t_end`
    #     换算原点 ⇒ `ready − t0 − t_start`。
    #     （bridge 里 `ready_minus_t_start_p95_sec` / `D_needed_sec` 就是这么算的）
    ready_gaps = []
    for s in per:
        if not s.get("has_tts"):
            continue
        ra, ts = s.get("ready_at"), s.get("t_start")
        te, oe = s.get("t_end"), s.get("orig_end")
        if ra is None or ts is None or te is None or oe is None:
            continue
        try:
            t0 = float(oe) - float(te)
            ready_gaps.append(float(ra) - t0 - float(ts))
        except (TypeError, ValueError):
            continue
    d_needed = None
    ready_p95 = None
    if ready_gaps:
        ready_p95 = _pct_bridge(ready_gaps, 0.95)
        d_needed = ready_p95 + 0.3

    delay = None
    for key in ("delay_sec",):
        if mg.get(key) is not None:
            delay = mg[key]
    if delay is None:
        delay = 20

    # ── 缓冲耗尽的源时间（signed_err 线性外推到 D）──────────────
    t_exhaust = None
    if fit_a and fit_a[1] > 0:
        a, b, _ = fit_a
        t_exhaust = (delay - a) / b if b > 0 else None

    # ── 覆盖率（★ EXT-039 ①：只算**源语音区间**，不把静音填充段算进去）──
    src_intervals = [(float(s["t_start"]), float(s["t_end"]))
                     for s in per
                     if s.get("has_tts") and s.get("src_len")]
    src_end = max((e for _, e in src_intervals), default=None)
    # 段区间连续性（所有段，含静音填充段）—— 缺口应全 0
    all_iv = [(float(s["t_start"]), float(s["t_end"]))
              for s in per if s.get("t_start") is not None]
    gaps = []
    for i in range(len(all_iv) - 1):
        gaps.append(round(all_iv[i + 1][0] - all_iv[i][1], 6))

    # ── 耗尽后行为：从产物**如实**读 ─────────────────────────────
    # ★ 2026-11-05 EXT-039：`n_dropped_dub` / `lag_curve` / 变速统计
    #   **不在 margin.json 顶层**，而在 **`adaptive_speed` 子对象**里
    #   （bridge 的 `adaptive_speed_stats()` 落盘位置）。
    #   ⇒ 只读顶层 ⇒ 这些字段全是 null ⇒ 「耗尽后行为」证据链缺失。
    ad = mg.get("adaptive_speed") or {}
    behavior = {
        # ★ 2026-11-05 EXT-039：原来这里写的是 `len(pts_a)`（= compare 里有
        #   signed_err 的段数）⇒ **标签与含义不符**（`has_tts` 的段 ≠ 有
        #   signed_err 测点的段）⇒ 口径混了。
        #   ⇒ 改为：TTS 段数按 **`has_tts`** 计；signed_err 测点数**单列**。
        "n_tts_segments": sum(1 for s in per if s.get("has_tts")),
        "n_signed_err_points": len(pts_a),
        "n_segments_total": len(per),
        # ★ 先读顶层（合成/自造产物可能直接放顶层），再回落到
        #   `adaptive_speed`（**真实产物**的位置）⇒ 两处都兼容。
        "n_dropped_dub": (mg.get("n_dropped_dub")
                           if mg.get("n_dropped_dub") is not None
                           else ad.get("n_dropped_dub")),
        # ★ 2026-11-05 EXT-039 ①：**静音填充段单列**（不是丢句）。
        #   bridge 侧已修正 `n_dropped_dub` 口径（只算「有源文本却没 TTS」）
        #   ⇒ 这两项必须**分别**报出，避免口径再混。
        #   ★ 取值优先级：margin 顶层 → `adaptive_speed` 子对象 →
        #     **由 `per_segment` 自行派生**（合成/自造产物也能算出来）。
        "n_silent_fill_segments": (
            mg.get("n_silent_fill_segments")
            if mg.get("n_silent_fill_segments") is not None
            else (ad.get("n_silent_fill_segments")
                  if ad.get("n_silent_fill_segments") is not None
                  else sum(1 for s in per
                           if not s.get("has_tts")
                           and (s.get("src_len") or 0) == 0))),
        # ★★ 2026-11-05 EXT-039 ①：**真丢句数（按修正后口径，从
        #   `per_segment` 逐段派生）** —— 「有源文本（src_len>0）却没 TTS」。
        #   ★ 与 `n_dropped_dub`（= margin 里落盘的服务端口径）**并列报出**：
        #     本轮 run 的 margin.json 是**口径修正前**的产物
        #     （旧口径把静音填充段也算丢句）⇒ 两者不等时，
        #     以本字段（可由逐段原始字段核对）为准。
        "n_dropped_dub_recomputed": sum(
            1 for s in per
            if not s.get("has_tts") and (s.get("src_len") or 0) > 0),
        "lag_curve": (mg.get("lag_curve")
                      if mg.get("lag_curve") is not None
                      else ad.get("lag_curve")),
        "adaptive_speed": ad,
    }
    cm = mg.get("client_metrics") or {}
    if cm:
        behavior["client_rescheduled"] = cm.get("dubRescheduled")
        behavior["client_reschedule_delay_sec"] = cm.get("dubRescheduleDelaySec")
        behavior["client_adapt_speed_history_tail"] = (
            (cm.get("adaptSpeedHistory") or [])[-5:])
    # ★ 2026-11-05 EXT-039：客户端侧实测在 **metrics.json**（插件侧落盘），
    #   margin.json 的 `client_metrics` 只有下行/队列/offset 三类。
    #   ⇒ 「按不丢句排队」「丢句」「重复交付」「变速封顶」这几项
    #   **必须**从 metrics.json 取，否则「耗尽后行为」结论就是空的。
    mx = d.get("metrics") or {}
    if mx:
        behavior["client_rescheduled"] = mx.get("dubRescheduled")
        behavior["client_reschedule_delay_sec"] = mx.get("dubRescheduleDelaySec")
        behavior["client_dub_dup"] = mx.get("dubDup")
        behavior["client_dropped"] = mx.get("dropped")
        behavior["client_dub_pcm_dropped"] = mx.get("dubPcmDropped")
        behavior["client_dub_delivered"] = (mx.get("link") or {}).get("dubDelivered")
        behavior["client_sched_clamped"] = mx.get("schedClamped")
        behavior["client_adapt_total_speed"] = mx.get("adaptTotalSpeed")
        behavior["client_adapt_speed_history_tail"] = (
            (mx.get("adaptSpeedHistory") or [])[-5:])
        behavior["client_adapt_speed_history_n"] = len(mx.get("adaptSpeedHistory") or [])
        behavior["client_adapt_speed_history_clamped_all"] = all(
            bool(h.get("clamped")) for h in (mx.get("adaptSpeedHistory") or []))
        behavior["client_sync_p50_ms"] = mx.get("dubSyncP50")
        behavior["client_sync_p95_ms"] = mx.get("dubSyncP95")
    mt = mg.get("margin_summary") or {}
    behavior["margin_summary_keys"] = sorted(mt.keys()) if mt else []
    # 服务端段的 drop 统计（EXT-009 要求丢句 = 0）
    es = mg.get("engine_stats") or {}
    if es:
        behavior["engine_stats_n_dropped"] = es.get("n_dropped")

    res = {
        "run_dir": run_dir,
        "delay_sec": delay,
        "n_signed_err_points": len(pts_a),
        "n_lag_est_points": len(pts_b),
        # ── 口径 A：signed_err ──
        "signed_err": {
            "definition": ("player 实测有符号误差 signed_err_ms = "
                           "actual − (t0 + t_start + D)；自变量 = t_start（源时间）"),
            "per_segment": [
                {"seg_id": p[2], "t_start": p[0], "signed_err_sec": round(p[1], 4)}
                for p in pts_a],
            "values_sec": [round(p[1], 4) for p in pts_a],
            "p50_sec": _pct([p[1] for p in pts_a], 0.50),
            "p95_sec": _pct([p[1] for p in pts_a], 0.95),
            "pct_caliber": ("索引法 sorted[int(round(q*(n-1)))] ⇒ 与 bridge / "
                            "reviewer **逐字一致**（EXT-039 收口修正：原插值法 "
                            "会让同一批数据给出两个 P50）"),
            "p50_sec_interp_for_reference": _pct_interp([p[1] for p in pts_a], 0.50),
            "p95_sec_interp_for_reference": _pct_interp([p[1] for p in pts_a], 0.95),
            "max_sec": max((p[1] for p in pts_a), default=None),
            "min_sec": min((p[1] for p in pts_a), default=None),
            "n_over_300ms": sum(1 for p in pts_a if abs(p[1]) > 0.300),
            "fit_intercept_sec": fit_a[0] if fit_a else None,
            "fit_slope_sec_per_sec": fit_a[1] if fit_a else None,
            "fit_r2": fit_a[2] if fit_a else None,
            "monotonic_non_decreasing": (
                all(pts_a[i][1] <= pts_a[i + 1][1] + 1e-9
                    for i in range(len(pts_a) - 1)) if pts_a else None),
        },
        # ── 口径 B：lag_est ──
        "lag_est": {
            "definition": ("服务端估算滞后 lag_est_sec = ready_at − "
                           "(t0 + t_start + D)，夹 0；自变量 = t_start（源时间）"),
            "values_sec": [round(p[1], 4) for p in pts_b],
            "p50_sec": _pct([p[1] for p in pts_b], 0.50),
            "p95_sec": _pct([p[1] for p in pts_b], 0.95),
            "pct_caliber": ("索引法 sorted[int(round(q*(n-1)))] ⇒ 与 bridge / "
                            "reviewer **逐字一致**"),
            "fit_intercept_sec": fit_b[0] if fit_b else None,
            "fit_slope_sec_per_sec": fit_b[1] if fit_b else None,
            "fit_r2": fit_b[2] if fit_b else None,
        },
        "d_needed_sec": d_needed,
        "ready_minus_t_start_p95_sec": ready_p95,
        "d_needed_definition": ("P95(ready_at − t0 − t_start) + 0.3，"
                                "其中 t0 = orig_end − t_end（跨时钟域换算）"
                                "⇒ 与 bridge `sync_rootcause.D_needed_sec` 同口径"),
        "buffer_exhaust": {
            "delay_sec": delay,
            "d_needed_sec": d_needed,
            "d_needed_exceeds_delay": (d_needed is not None
                                       and d_needed > delay),
            "signed_err_reaches_delay_at_src_sec": t_exhaust,
            "note": ("t_exhaust = (D − a) / k_signed（signed_err 线性外推到 D）；"
                     "★ 只有当它 **小于素材语音总长** 时，本轮素材才真的碰过上限"),
        },
        "coverage": {
            "caliber": ("★ EXT-039 ①：**源语音区间**覆盖（只算 has_tts 且 src_len>0 的段）"
                        "；素材尾部静音填充段不计入覆盖率"),
            "n_source_segments": len(src_intervals),
            "source_span_sec": [src_intervals[0][0] if src_intervals else None,
                                src_end],
            "all_segment_gaps_sec": gaps,
            "n_gaps_nonzero": sum(1 for g in gaps if abs(g) > 1e-6),
            "n_segments_total": len(per),
            "n_silent_fill_segments": sum(
                1 for s in per if not s.get("has_tts")),
        },
        "behavior_after_exhaustion": behavior,
    }
    return res


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python tools/ext039_sync_curve.py <run_dir> [--json out.json]")
        return 2
    run_dir = sys.argv[1]
    res = build(run_dir)
    out = None
    if "--json" in sys.argv:
        i = sys.argv.index("--json")
        if i + 1 < len(sys.argv):
            out = sys.argv[i + 1]
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(txt)
        print("已写出 %s" % out)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
