"""compare_ext011_cores.py — ★ EXT-013 ②：限制组 vs 对照组，同一张表

## 干什么

把 **EXT-011 A/B 对照**的两臂（限制组 / 对照组）产物解析成**一张表**：

| 指标 | 限制组（thread limit ON） | 对照组（thread limit OFF） |
|---|---|---|
| 核数 mean（cores） | … | … |
| 核数 peak（cores） | … | … |
| TTS 稳态 RTF | … | … |
| 末句滞后（lag_sec） | … | … |
| 滞后斜率（lag_growth_slope） | … | … |

## 口径（**必须**写进产物，reviewer 逐项核对）

* **核数**：`cores = psutil cpu_percent / 100`（100 % = 1 核）。
  * 采样对象 = **服务进程及其全部子进程的 PID 树**（EXT-013 ① 修好的口径）。
  * `mean_cores` = 整段采样点的算术平均；`peak_cores` = 最大值。
* **TTS 稳态 RTF**：TTS 阶段**稳态区间**（剔除首段冷启动）的
  `wall_sec / audio_sec`。稳态区间取 `per_segment` 里 tts 阶段的
  **后 50 %** 段（冷启动只影响开头）。
* **末句滞后**：报告 `adaptive_speed.lag_curve.end_sec`。
* **滞后斜率**：`adaptive_speed.lag_growth_slope`（线性回归斜率，s/s）。

## 用法

```
python tools/compare_ext011_cores.py \
    --lim  .tmp/p1_ext013_lim \
    --ctl  .tmp/p1_ext011_ctl \
    --out  .tmp/p1_ext013_lim/compare_ext011.json
```

退出码：0 = 两臂都读到数据并成功落盘；3 = 某一臂缺数据（**判 FAIL**，
不写「已交付」）。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import statistics
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# cpu_watch.log 的行格式（**旧版** cpu_watch 也在用同一格式）：
#   [cpu-watch]    0.5s  pids=1  cpu=    0.0%  cores=0.000
_LOG_RE = re.compile(
    r"\[\s*cpu-watch\]\s+([0-9.]+)s\s+pids=(\d+)\s+cpu=\s*([0-9.]+)%\s+cores=([0-9.]+)")


def _read_json(path: str) -> Optional[Any]:
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_text(path: str) -> str:
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


# ── 核数 ──────────────────────────────────────────────────────────────
def parse_cores(out_dir: str) -> Dict[str, Any]:
    """从一臂的产物目录里解析核数。

    优先用 `cpu_usage.json`（**新版** cpu_watch 的落盘口径，含
    `identity` / `self_check`）；没有就退回解析 `cpu_watch.log`。
    """
    out: Dict[str, Any] = {"source": None, "mean_cores": None,
                           "peak_cores": None, "n_samples": 0,
                           "self_check": None, "identity": None}

    j = _read_json(os.path.join(out_dir, "cpu_usage.json"))
    if isinstance(j, dict) and j.get("samples"):
        samples = j["samples"]
        cores = [float(s.get("cores") or 0.0) for s in samples]
        out.update({
            "source": "cpu_usage.json",
            "mean_cores": round(statistics.mean(cores), 4),
            "peak_cores": round(max(cores), 4),
            "n_samples": len(samples),
            "self_check": j.get("self_check"),
            "identity": (j.get("identity") or {}).get("ok"),
            "wall_sec": j.get("wall_sec"),
        })
        return out

    # 退回：解析 cpu_watch.log
    txt = _read_text(os.path.join(out_dir, "cpu_watch.log"))
    rows = _LOG_RE.findall(txt)
    if not rows:
        return out
    cores = [float(r[3]) for r in rows]
    out.update({
        "source": "cpu_watch.log",
        "mean_cores": round(statistics.mean(cores), 4),
        "peak_cores": round(max(cores), 4),
        "n_samples": len(rows),
    })
    return out


# ── TTS 稳态 RTF ──────────────────────────────────────────────────────
def parse_tts_steady_rtf(out_dir: str, report: Dict[str, Any]) -> Dict[str, Any]:
    """TTS 稳态 RTF = 后 50% 段的 sum(tts_sec) / sum(speech_sec)。

    **数据来源**：`margin.json` 的 `per_segment`，每段有
    `tts_sec`（TTS 阶段墙钟）与 `speech_sec`（该段配音音频时长）。

    * 逐段 RTF = tts_sec / speech_sec；
    * **稳态** = 丢掉冷启动的前半段，只用**后 50 %** 的段算总 RTF
      （模型首段加载/首段预热只影响开头）；
    * 取的是**总 RTF**（总墙钟 / 总音频时长），不是逐段 RTF 的平均 ——
      后者会让短段被过度加权。
    """
    margin = _read_json(os.path.join(out_dir, "margin.json"))
    rows: List[Dict[str, Any]] = []
    if isinstance(margin, dict):
        for s in (margin.get("per_segment") or []):
            tts = s.get("tts_sec")
            aud = s.get("speech_sec")
            if tts is None or not aud:
                continue
            rows.append({"id": s.get("id"), "tts_sec": float(tts),
                         "speech_sec": float(aud),
                         "rtf": round(float(tts) / float(aud), 4)})
    if not rows:
        return {"tts_steady_rtf": None, "n_segments_used": 0,
                "note": "margin.json 的 per_segment 里没有 tts_sec/speech_sec"}

    # 按 id 里的起始毫秒排序（seg_<ms>）⇒ 保证「后 50%」是**时间上靠后**的段
    def _key(r):
        try:
            return int(str(r["id"]).split("_")[-1])
        except Exception:
            return 0

    rows.sort(key=_key)
    half = rows[len(rows) // 2:]
    w = sum(r["tts_sec"] for r in half)
    a = sum(r["speech_sec"] for r in half)
    per_rtf = [r["rtf"] for r in half]
    return {
        "tts_steady_rtf": round(w / a, 4) if a else None,
        "n_segments_used": len(half),
        "n_segments_total": len(rows),
        "steady_window": "后 50% 段（按 id 起始毫秒排序）",
        "tts_sec_sum_steady": round(w, 4),
        "speech_sec_sum_steady": round(a, 4),
        "per_segment_rtf_min": round(min(per_rtf), 4),
        "per_segment_rtf_max": round(max(per_rtf), 4),
        "per_segment_rtf_mean": round(statistics.mean(per_rtf), 4),
        "definition": ("TTS 稳态 RTF = 后 50% 段的 sum(tts_sec)/"
                       "sum(speech_sec)（剔除冷启动）"),
    }


# ── 滞后 ──────────────────────────────────────────────────────────────
def parse_lag(out_dir: str, report: Dict[str, Any]) -> Dict[str, Any]:
    """末句滞后 + 滞后斜率。

    * **末句滞后** = `metrics.lag.last_segment_lag_sec`
      （= max(0, −末句排程余量)）。
    * **滞后斜率** = `metrics.lag.lag_growth_slope_sec_per_sec`
      （对 (t_start, 排程余量) 线性拟合；负数 = 滞后随时间累积）。
    """
    lag = ((report.get("metrics") or {}).get("lag") or {})
    out = {
        "lag_end_sec": lag.get("last_segment_lag_sec"),
        "lag_peak_sec": lag.get("max_lag_sec"),
        "lag_growth_slope": lag.get("lag_growth_slope_sec_per_sec"),
        "lag_growth_r2": lag.get("lag_growth_r2"),
        "lag_n_fit_points": lag.get("n_fit_points"),
    }
    if out["lag_end_sec"] is None:
        # 兜底：margin.json 的 margin_summary
        margin = _read_json(os.path.join(out_dir, "margin.json"))
        ms = ((margin or {}).get("margin_summary") or {})
        out["lag_end_sec"] = ms.get("last_segment_lag_sec")
        out["lag_peak_sec"] = ms.get("max_lag_sec")
        out["lag_growth_slope"] = ms.get("lag_growth_slope_sec_per_sec")
        out["lag_growth_r2"] = ms.get("lag_growth_r2")
    return out


def collect(out_dir: str) -> Dict[str, Any]:
    report = _read_json(os.path.join(out_dir, "p1_report.json"))
    if not isinstance(report, dict):
        report = {}
    row: Dict[str, Any] = {
        "out_dir": os.path.abspath(out_dir),
        "report_present": bool(report),
        "cores": parse_cores(out_dir),
        "tts": parse_tts_steady_rtf(out_dir, report),
    }
    row.update(parse_lag(out_dir, report))
    timing = report.get("timing") or {}
    row["timing"] = {
        "feed_sec": timing.get("feed_sec"),
        "drain_sec": timing.get("drain_sec"),
        "total_sec": timing.get("total_sec"),
        "feed_speed_x": timing.get("feed_speed_x"),
    }
    pl = ((report.get("bridge_stats") or {}).get("pipeline") or {})
    row["stage_wall_sec"] = pl.get("stage_wall_sec")
    row["n_dropped_dub"] = (pl.get("n_dropped_dub"))
    ad = report.get("adaptive_speed") or {}
    if row["n_dropped_dub"] is None:
        row["n_dropped_dub"] = ad.get("n_dropped_dub")
    row["speed_time_share"] = ad.get("speed_time_share")
    row["thread_limits"] = (report.get("bridge_stats") or {}).get("thread_limits")
    row["started_at"] = report.get("started_at")
    row["finished_at"] = report.get("finished_at")
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT-013 ②：限制组 vs 对照组对比表")
    ap.add_argument("--lim", required=True, help="限制组产物目录")
    ap.add_argument("--ctl", required=True, help="对照组产物目录")
    ap.add_argument("--out", required=True, help="对比表落盘路径（json）")
    args = ap.parse_args(argv)

    lim = collect(args.lim)
    ctl = collect(args.ctl)

    table = {
        "generated_at": None,   # 由调用方填实测时间（本脚本不推算）
        "metric_definitions": {
            "cores": "cores = psutil cpu_percent/100（100% = 1 核）；"
                     "采样对象 = 服务进程及其全部子进程的 PID 树",
            "mean_cores": "整段采样点的算术平均",
            "peak_cores": "采样点最大值",
            "tts_steady_rtf": "TTS 稳态 RTF = 后 50% 段的 "
                              "sum(tts_sec)/sum(speech_sec)（剔除冷启动；"
                              "数据来自 margin.json 的 per_segment）",
            "lag_end_sec": "末句滞后 = metrics.lag.last_segment_lag_sec",
            "lag_growth_slope": "滞后斜率 = "
                                "metrics.lag.lag_growth_slope_sec_per_sec",
        },
        "limitation": {
            "name": "限制组（EXT_THREAD_LIMIT 生效，OMP/MKL/OPENBLAS/"
                    "NUMEXPR = 1）",
            **lim,
        },
        "control": {
            "name": "对照组（线程限制关闭）",
            **ctl,
        },
    }

    missing = []
    for side in ("limitation", "control"):
        r = table[side]
        if r["cores"]["mean_cores"] is None:
            missing.append("%s 缺核数" % side)
        if r["tts"]["tts_steady_rtf"] is None:
            missing.append("%s 缺 TTS 稳态 RTF" % side)
        if r.get("lag_end_sec") is None:
            missing.append("%s 缺末句滞后" % side)
    table["missing"] = missing

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(table, ensure_ascii=False, indent=2))
    print("已写出对比表：%s" % args.out)
    print(json.dumps(table, ensure_ascii=False, indent=2))

    if missing:
        print("★ 缺数据（判 FAIL）：%s" % "; ".join(missing), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
