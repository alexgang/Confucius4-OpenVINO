"""run_p0_suite.py — EXT-003 P0 ①②③ 的**串行编排**（每个探针各自持共享锁）

为什么要编排器：
  三个探针都要抢 `shared/MACHINE_LOCK`，而 App 模块会长时间持锁。
  串行编排 + 每步独立持锁 ⇒
    ① 一次只跑一个浏览器会话（不叠加设备占用）；
    ② 每步之间释放锁，让别的模块有机会插队（铁律：只能排队，不能抢）；
    ③ 任一步失败不影响其它步（各自落盘、各自成证据）。

用法：
    python tools/run_p0_suite.py --out .tmp/probe_suite [--skip uplink]
退出码 0 = 全部步骤跑完（不代表全部达标；达标与否看各自 JSON）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PY = sys.executable
STEPS = {
    # name: (script, extra args, out subdir)
    "uplink": ("tools/browser_probe.py",
               ["--mode", "uplink", "--duration", "300"],
               "probe_uplink_5min_v4"),
    "video_lipsync": ("tools/video_lipsync_probe.py",
                      ["--video-sec", "45"],
                      "probe_video_lipsync"),
    "echo_sched": ("tools/echo_sched_probe.py",
                   [],
                   "probe_echo_sched"),
}


def run_step(name: str, out_root: str, lock_wait: float) -> dict:
    script, extra, sub = STEPS[name]
    out_dir = os.path.join(out_root, sub)
    cmd = [PY, os.path.join(ROOT, script)] + extra + ["--out", out_dir]
    if name == "uplink":
        cmd += ["--lock-wait", str(lock_wait)]
    print(f"[suite] ▶ {name}: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, timeout=lock_wait + 1800,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        rc = p.returncode
        tail = (p.stdout or "")[-2000:]
        err = (p.stderr or "")[-2000:]
    except subprocess.TimeoutExpired:
        rc, tail, err = -1, "", "超时"
    return {
        "step": name, "rc": rc, "out_dir": out_dir,
        "elapsed_sec": round(time.time() - t0, 1),
        "stdout_tail": tail, "stderr_tail": err,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, ".tmp", "probe_suite"))
    ap.add_argument("--skip", default="", help="逗号分隔的步骤名，跳过它们")
    ap.add_argument("--only", default="", help="只跑这些步骤（逗号分隔）")
    ap.add_argument("--lock-wait", type=float, default=7200.0)
    args = ap.parse_args(argv)

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    steps = [s for s in ("uplink", "video_lipsync", "echo_sched")
             if s not in skip and (not only or s in only)]
    if not steps:
        print("[suite] 没有要跑的步骤")
        return 0

    os.makedirs(args.out, exist_ok=True)
    results = []
    for name in steps:
        r = run_step(name, args.out, args.lock_wait)
        results.append(r)
        print(f"[suite] ◀ {name} rc={r['rc']} 用时 {r['elapsed_sec']} s", flush=True)

    summary = {
        "started_at": results[0].get("started_at") if results else None,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": results,
    }
    p = os.path.join(args.out, "suite_summary.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[suite] 汇总落盘：{p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
