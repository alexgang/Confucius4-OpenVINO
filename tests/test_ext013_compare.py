"""test_ext013_compare.py — ★ EXT-013 ② 自测：限制组 vs 对照组对比表

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

EXT-013 原文要的第二点：

> ② 持锁重跑限制组，和对照组放进**同一张表**（核数、TTS 稳态 RTF、
>    末句滞后、斜率）

本自测验证：

  1. **对比脚本存在且口径写进产物**（metric_definitions 逐项核对）；
  2. **★ 核数解析**：能从 `cpu_usage.json`（新版口径，含 identity /
     self_check）**和** `cpu_watch.log`（旧版口径）两条路都解析出核数；
     并有**反向对照** —— 解析一个**空目录**必须返回 None（不能编数）。
  3. **★ TTS 稳态 RTF 口径**：从 `margin.json` 的 `per_segment` 取
     `tts_sec` / `speech_sec`，用**后 50%** 段算总 RTF；
     **反向对照** —— 拿「全段」与「后 50%」两个口径做**数值不同**的断言，
     证明「稳态」确实排除了冷启动，而不是恒等于全段。
  4. **★ 滞后口径**：`metrics.lag.last_segment_lag_sec` 与
     `lag_growth_slope_sec_per_sec` 能被正确读出；
     **反向对照** —— 缺字段时返回 None 而不是 0。
  5. **★ 真实产物比对**：限制组 `.tmp/p1_ext013_lim` 与对照组
     `.tmp/p1_ext011_ctl` 的实测数据能生成一张表，且**两臂都有全部四项指标**
     （缺任何一项 ⇒ 脚本 rc=3 ⇒ 判 FAIL，不写「已交付」）。

运行：
    python tests/test_ext013_compare.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

import compare_ext011_cores as cmp_mod  # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                           (" — " + detail) if (detail and not ok) else ""))
    return bool(ok)


# ── ① 脚本与口径 ──────────────────────────────────────────────────────
def test_script_and_definitions() -> None:
    print("\n[1] ★ 对比脚本 + 指标口径")
    path = os.path.join(ROOT, "tools", "compare_ext011_cores.py")
    check("对比脚本存在", os.path.isfile(path), path)
    src = open(path, encoding="utf-8").read()

    for key in ("metric_definitions", "mean_cores", "peak_cores",
                "tts_steady_rtf", "lag_end_sec", "lag_growth_slope"):
        check("★ 口径里声明了 %s" % key, key in src)
    check("★ 核数口径写明 100% = 1 核", "100% = 1 核" in src)
    check("★ 核数口径写明采样对象是 PID 树", "PID 树" in src)
    check("★ 缺数据时 rc=3（不写「已交付」）", "return 3" in src)

    # 脚本能 import 且暴露四个解析函数
    for fn in ("parse_cores", "parse_tts_steady_rtf", "parse_lag", "collect"):
        check("★ 暴露函数 %s" % fn, hasattr(cmp_mod, fn))


# ── ② 核数解析（含反向对照） ──────────────────────────────────────────
def test_cores_parsing() -> None:
    print("\n[2] ★ 核数解析（两条数据源 + 反向对照）")
    tmp = tempfile.mkdtemp(prefix="ext013_cores_")
    try:
        # 空目录 ⇒ 必须返回 None（不能编数）
        r = cmp_mod.parse_cores(tmp)
        check("★ 反向对照：空目录解析不出核数（返回 None）",
              r["mean_cores"] is None and r["peak_cores"] is None,
              json.dumps(r, ensure_ascii=False))

        # cpu_watch.log 路径
        with open(os.path.join(tmp, "cpu_watch.log"), "w",
                  encoding="utf-8") as f:
            f.write("[cpu-watch] 目标进程：python.exe（身份校验通过）\n")
            f.write("[cpu-watch]    0.5s  pids=1  cpu=    0.0%  cores=0.000\n")
            f.write("[cpu-watch]    1.5s  pids=1  cpu=  100.0%  cores=1.000\n")
            f.write("[cpu-watch]    2.5s  pids=1  cpu=  300.0%  cores=3.000\n")
        r = cmp_mod.parse_cores(tmp)
        check("★ 能从 cpu_watch.log 解析核数",
              r["mean_cores"] is not None and r["source"] == "cpu_watch.log",
              json.dumps(r, ensure_ascii=False))
        check("★ log 口径 mean 正确（(0+1+3)/3=1.3333）",
              r["mean_cores"] == 1.3333, str(r["mean_cores"]))
        check("★ log 口径 peak 正确（3.0）", r["peak_cores"] == 3.0,
              str(r["peak_cores"]))

        # cpu_usage.json 路径（新版口径，优先）
        with open(os.path.join(tmp, "cpu_usage.json"), "w",
                  encoding="utf-8") as f:
            json.dump({
                "samples": [{"cores": 0.5}, {"cores": 1.5}, {"cores": 2.5}],
                "self_check": {"ok": True, "reason": "x"},
                "identity": {"ok": True},
                "wall_sec": 10.0,
            }, f)
        r = cmp_mod.parse_cores(tmp)
        check("★ 优先用 cpu_usage.json（含 identity/self_check）",
              r["source"] == "cpu_usage.json", str(r["source"]))
        check("★ json 口径 mean 正确（1.5）", r["mean_cores"] == 1.5,
              str(r["mean_cores"]))
        check("★ json 口径 peak 正确（2.5）", r["peak_cores"] == 2.5,
              str(r["peak_cores"]))
        check("★ json 口径带回 self_check", r["self_check"] is not None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── ③ TTS 稳态 RTF 口径（含反向对照） ─────────────────────────────────
def test_tts_rtf() -> None:
    print("\n[3] ★ TTS 稳态 RTF 口径（反向对照：稳态 ≠ 全段）")
    tmp = tempfile.mkdtemp(prefix="ext013_rtf_")
    try:
        # 构造 4 段：前 2 段是「冷启动」（tts_sec 大），后 2 段是稳态
        segs = []
        for i, (tts, aud) in enumerate([(60.0, 10.0), (60.0, 10.0),
                                        (10.0, 10.0), (10.0, 10.0)]):
            segs.append({"id": "seg_%d" % (i * 1000), "tts_sec": tts,
                         "speech_sec": aud})
        with open(os.path.join(tmp, "margin.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"per_segment": segs}, f)

        r = cmp_mod.parse_tts_steady_rtf(tmp, {})
        check("★ 能算出 TTS 稳态 RTF",
              r["tts_steady_rtf"] is not None, json.dumps(r, ensure_ascii=False))
        check("★ 稳态 RTF = 1.0（后 2 段：10/10）",
              r["tts_steady_rtf"] == 1.0, str(r["tts_steady_rtf"]))
        check("★ 稳态窗口是后 50% 段（2/4）",
              r["n_segments_used"] == 2 and r["n_segments_total"] == 4,
              json.dumps(r, ensure_ascii=False))
        check("★ 口径写明「后 50%」",
              "后 50%" in r["definition"], r["definition"])

        # ★ 反向对照：全段 RTF = (60+60+10+10)/(10+10+10+10) = 1.75，
        #   稳态 RTF = 1.0 ⇒ 两者**不同** ⇒ 证明稳态真的排除了冷启动
        all_rtf = sum(s["tts_sec"] for s in segs) / sum(s["speech_sec"]
                                                        for s in segs)
        check("★ 反向对照：稳态 RTF ≠ 全段 RTF（冷启动被排除）",
              abs(all_rtf - r["tts_steady_rtf"]) > 0.1,
              "all=%.4f steady=%.4f" % (all_rtf, r["tts_steady_rtf"]))

        # ★ 缺数据 ⇒ None，不是 0
        empty = tempfile.mkdtemp(prefix="ext013_rtf_empty_")
        try:
            r2 = cmp_mod.parse_tts_steady_rtf(empty, {})
            check("★ 反向对照：缺数据返回 None（不是 0）",
                  r2["tts_steady_rtf"] is None,
                  json.dumps(r2, ensure_ascii=False))
        finally:
            shutil.rmtree(empty, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── ④ 滞后口径 ────────────────────────────────────────────────────────
def test_lag() -> None:
    print("\n[4] ★ 末句滞后 + 斜率口径")
    tmp = tempfile.mkdtemp(prefix="ext013_lag_")
    try:
        report = {"metrics": {"lag": {
            "last_segment_lag_sec": 117.0879,
            "max_lag_sec": 134.0408,
            "lag_growth_slope_sec_per_sec": -0.269455,
            "lag_growth_r2": 0.814857,
            "n_fit_points": 22,
        }}}
        r = cmp_mod.parse_lag(tmp, report)
        check("★ 末句滞后读对", r["lag_end_sec"] == 117.0879,
              str(r["lag_end_sec"]))
        check("★ 斜率读对", r["lag_growth_slope"] == -0.269455,
              str(r["lag_growth_slope"]))
        check("★ r² 读对", r["lag_growth_r2"] == 0.814857)
        check("★ 拟合点数读对", r["lag_n_fit_points"] == 22)

        # ★ 反向对照：缺字段 ⇒ None（不是 0）
        r2 = cmp_mod.parse_lag(tmp, {})
        check("★ 反向对照：缺字段返回 None（不是 0）",
              r2["lag_end_sec"] is None and r2["lag_growth_slope"] is None,
              json.dumps(r2, ensure_ascii=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── ⑤ 真实产物 → 一张表 ───────────────────────────────────────────────
def test_real_compare() -> None:
    print("\n[5] ★ 真实产物比对（限制组 vs 对照组 → 一张表）")
    lim = os.path.join(ROOT, ".tmp", "p1_ext013_lim")
    ctl = os.path.join(ROOT, ".tmp", "p1_ext011_ctl")
    have_lim = os.path.isfile(os.path.join(lim, "p1_report.json"))
    have_ctl = os.path.isfile(os.path.join(ctl, "p1_report.json"))
    if not (have_lim and have_ctl):
        print("  [SKIP] 真实产物尚未落盘（限制组=%s / 对照组=%s）—— "
              "本项在实测跑完后才会生效" % (have_lim, have_ctl))
        return

    out = os.path.join(ROOT, ".tmp", "_ext013_compare_selftest.json")
    rc = cmp_mod.main(["--lim", lim, "--ctl", ctl, "--out", out])
    check("★ 对比脚本对真实产物 rc=0", rc == 0, "rc=%s" % rc)
    if not os.path.isfile(out):
        check("★ 对比表落盘", False, out)
        return
    d = json.load(open(out, encoding="utf-8"))

    check("★ 表里有 metric_definitions", "metric_definitions" in d)
    check("★ 表里没有 missing 项", not d.get("missing"),
          str(d.get("missing")))

    for side, label in (("limitation", "限制组"), ("control", "对照组")):
        s = d[side]
        check("★ %s 有核数 mean" % label,
              s["cores"]["mean_cores"] is not None, json.dumps(s["cores"]))
        check("★ %s 有核数 peak" % label,
              s["cores"]["peak_cores"] is not None)
        check("★ %s 有 TTS 稳态 RTF" % label,
              s["tts"]["tts_steady_rtf"] is not None,
              json.dumps(s["tts"], ensure_ascii=False))
        check("★ %s 有末句滞后" % label, s["lag_end_sec"] is not None,
              str(s["lag_end_sec"]))
        check("★ %s 有滞后斜率" % label, s["lag_growth_slope"] is not None,
              str(s["lag_growth_slope"]))
        check("★ %s 有线程限制结论" % label,
              s.get("thread_limits") is not None)

    # ★ 线程限制真的一个开一个关
    check("★ 限制组线程限制 enabled=true",
          d["limitation"]["thread_limits"]["enabled"] is True,
          json.dumps(d["limitation"]["thread_limits"], ensure_ascii=False))
    check("★ 对照组线程限制 enabled=false",
          d["control"]["thread_limits"]["enabled"] is False,
          json.dumps(d["control"]["thread_limits"], ensure_ascii=False))

    # ★ 限制组确实比对照组省 CPU（这是 EXT-011 的目的）
    lm = d["limitation"]["cores"]["mean_cores"]
    cm = d["control"]["cores"]["mean_cores"]
    check("★ 限制组平均核数 < 对照组", lm < cm,
          "lim=%.4f ctl=%.4f" % (lm, cm))

    try:
        os.remove(out)
    except Exception:
        pass


def main() -> int:
    print("=" * 72)
    print("EXT-013 自测：限制组 vs 对照组对比表")
    print("=" * 72)
    test_script_and_definitions()
    test_cores_parsing()
    test_tts_rtf()
    test_lag()
    test_real_compare()

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 72)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    if n_fail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f" - {name} — {detail}")
    print("=" * 72)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
