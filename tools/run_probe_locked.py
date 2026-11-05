"""run_probe_locked.py — 在**共享机器锁**保护下跑浏览器实测

铁律：计时或测速作业开始前创建 shared/MACHINE_LOCK，结束后删除；
锁已存在就等待；回收锁前必须用 ctypes 确认 PID 真死。

用法：
    python tools/run_probe_locked.py --mode all --duration 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from browser_probe import run_browser_probe  # noqa: E402
from machine_lock import hold  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all",
                    choices=["all", "capture", "video", "echo"])
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--bridge-port", type=int, default=8791)
    ap.add_argument("--delay", type=float, default=20.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    os.environ.setdefault("EXT_BRIDGE_WS", f"ws://127.0.0.1:{args.bridge_port}/")
    tok_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".tmp", "probe_bridge_token.txt")
    if os.path.isfile(tok_path):
        with open(tok_path, "r", encoding="utf-8") as f:
            os.environ["EXT_BRIDGE_TOKEN"] = f.read().strip()

    with hold("EXT-browser-probe"):
        r = run_browser_probe(mode=args.mode, duration_sec=args.duration,
                              bridge_port=args.bridge_port,
                              delay_sec=args.delay, out_dir=args.out)

    payload = {"ok": r.ok, "error": r.error, "data": r.data}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("ok:", r.ok)
        if r.error:
            print("error:", r.error)
        print(json.dumps(r.data, ensure_ascii=False, indent=2)[:6000])
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
