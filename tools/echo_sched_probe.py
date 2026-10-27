"""echo_sched_probe.py — P0③ 浏览器端回声排程误差的**独立**实测

与 browser_probe.py 的区别：
  * 用**独立端口**（默认 8793），可与其它实测并行；
  * 只测 P0③：浏览器排程一段 PCM → onset worklet 逐样本测
    「实际出声时刻 − 计划时刻」；
  * 结果落盘 JSON（含每一次的 planned / actual / errMs）。

不跑推理、不占 GPU·NPU。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import struct
import subprocess
import sys
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(ROOT, "extension")
TMP_DIR = os.path.join(ROOT, ".tmp")
sys.path.insert(0, ROOT)

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def _find_browser() -> Optional[str]:
    for p in EDGE_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def run_sched_probe(*, delay_sec: float = 10.0, out_dir: Optional[str] = None,
                    port: int = 8793) -> dict:
    from playwright.sync_api import sync_playwright

    browser = _find_browser()
    if not browser:
        return {"ok": False, "error": "找不到浏览器"}

    os.makedirs(TMP_DIR, exist_ok=True)
    token_path = os.path.join(TMP_DIR, "sched_probe_token.txt")
    logf = open(os.path.join(TMP_DIR, "sched_probe_bridge.log"), "w", encoding="utf-8")
    bridge = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tools", "bridge_echo_server.py"),
         "--port", str(port), "--delay", str(delay_sec),
         "--token-file", token_path],
        cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
    try:
        import socket
        for _ in range(80):
            time.sleep(0.25)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except Exception:
                pass
        token = ""
        if os.path.isfile(token_path):
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()

        prof = os.path.join(TMP_DIR, "pwprofile_sched_%d" % int(time.time()))
        os.makedirs(prof, exist_ok=True)
        out: dict = {"ok": False, "delay_sec": delay_sec,
                     "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                prof, executable_path=browser, headless=False,
                args=[f"--disable-extensions-except={EXT_DIR}",
                      f"--load-extension={EXT_DIR}",
                      "--no-first-run", "--no-default-browser-check",
                      "--autoplay-policy=no-user-gesture-required"])
            try:
                sw = ctx.service_workers[0] if ctx.service_workers else \
                    ctx.wait_for_event("serviceworker", timeout=20000)
                ext_id = sw.url.split("/")[2]
                page = ctx.new_page()
                page.goto(f"chrome-extension://{ext_id}/player.html?d={delay_sec}",
                          wait_until="load")
                page.wait_for_timeout(1500)

                # 排程 3 次，取多个样本
                sr = 16000
                n = int(sr * 0.1)
                pcm = b"".join(
                    struct.pack("<h",
                                int(12000 * math.sin(2 * math.pi * 1000 * i / sr)))
                    for i in range(n))
                b64 = base64.b64encode(pcm).decode("ascii")

                for t_start in (0.5, 2.0, 3.5):
                    page.evaluate(
                        """(o) => { window.__ext.selfTestSchedule(o.b64, o.tStart); }""",
                        {"b64": b64, "tStart": t_start})
                    page.wait_for_timeout(int((delay_sec + 1.2) * 1000))

                m = page.evaluate("() => window.__ext.metrics()")
                errs = m.get("onsetErrs") or []
                out["ok"] = True
                out["ext_id"] = ext_id
                out["onsetErrs"] = errs
                out["schedErrMs"] = m.get("schedErrMs")
                out["schedErrP50"] = m.get("schedErrP50")
                out["schedErrP95"] = m.get("schedErrP95")
                out["n_samples"] = len(errs)
                out["maxAbsErrMs"] = max((abs(e) for e in errs), default=None)
                out["passed"] = bool(errs) and out["maxAbsErrMs"] <= 20.0
                out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    finally:
        try:
            bridge.terminate()
            bridge.wait(timeout=5)
        except Exception:
            pass

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, "echo_sched_probe.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        out["_out_path"] = p
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--port", type=int, default=8793)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    r = run_sched_probe(delay_sec=args.delay, out_dir=args.out, port=args.port)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
