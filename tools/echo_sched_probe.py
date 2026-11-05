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
from contextlib import ExitStack
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(ROOT, "extension")
TMP_DIR = os.path.join(ROOT, ".tmp")
sys.path.insert(0, ROOT)
# ★ Chrome profile 统一管理（EXT-005 第 2、3 点）
sys.path.insert(0, os.path.join(ROOT, "tools"))
import chrome_profile  # noqa: E402

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
                    port: int = 8793, lock: bool = True,
                    lock_wait: float = 600.0) -> dict:
    # ★ 铁律：计时/测速作业必须持共享机器锁。
    #   本探针要拉起浏览器 + 桥接服务，属设备占用型作业。
    #   锁已存在 ⇒ **排队等待**，绝不抢。
    stack = ExitStack()
    try:
        if lock:
            from tools.machine_lock import hold
            stack.enter_context(
                hold("EXT-echo-sched-probe", wait_timeout=lock_wait))
        return _run_sched_probe(delay_sec=delay_sec, out_dir=out_dir, port=port)
    finally:
        try:
            stack.close()      # 释放共享机器锁
        except Exception:
            pass


def _run_sched_probe(*, delay_sec: float = 10.0, out_dir: Optional[str] = None,
                     port: int = 8793) -> dict:
    from playwright.sync_api import sync_playwright

    browser = _find_browser()
    if not browser:
        return {"ok": False, "error": "找不到浏览器"}

    os.makedirs(TMP_DIR, exist_ok=True)
    token_path = os.path.join(TMP_DIR, "sched_probe_token.txt")
    # ★ 先建好 profile 上下文（在 try 之前，避免 finally 里 NameError）
    prof_ctx = chrome_profile.probe_profile("sched")
    prof_ctx.__enter__()          # 建目录（退出时由 finally 里的 __exit__ 清理）
    logf = open(os.path.join(TMP_DIR, "sched_probe_bridge.log"), "w", encoding="utf-8")
    bridge = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tools", "bridge_echo_server.py"),
         "--port", str(port), "--delay", str(delay_sec),
         "--token-file", token_path],
        cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
    # ★ out 必须**在 try 之前**初始化：否则 try 内抛异常时，
    #   finally 里的 out["cleanup"] = ... 会抛 NameError，把真实异常盖掉。
    out: dict = {"ok": False, "delay_sec": delay_sec,
                 "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "profile_dir": prof_ctx.path}
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

        # ★ Chrome user-data-dir 统一放 chrome_profile/<名称>/（EXT-005 第 3 点）
        prof = prof_ctx.path
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

                # ★★ 排程时刻必须落在**未来**（真实缺陷，实测双峰 0.02 / 43.02 / 0.02 ms）：
                #   selfTestSchedule 的 t_start 是**相对 t0（页面加载时刻）**的偏移，
                #   插件算 planned = t0 + t_start + delaySec。
                #   旧写法固定传 (0.5, 2.0, 3.5)：
                #     第 1 次 currentTime≈1.5  ⇒ planned=10.5  未来 ✓
                #     第 2 次 currentTime≈12.7 ⇒ planned=12.0  **已在过去** ✗
                #     第 3 次 currentTime≈23.9 ⇒ planned=13.5  **远在过去** ✗
                #   ⇒ 插件里的 Math.max(currentTime+0.005, planned) 把过去时刻钳到"立刻播"
                #     而主线程读到的 audioCtx.currentTime 在繁忙时**滞后真实音频时钟约 43 ms**
                #     ⇒ 稳定复现 **43.02 ms** 的假误差（两次独立探针数值完全相同）。
                #   ⇒ 修法：用**当前音频时钟**推算未来的排程时刻（每次 +0.6 s 间隔）。
                for k in range(3):
                    t_start = page.evaluate(
                        """() => {
                             const t0 = window.__ext.getT0();
                             const now = window.__ext.getAudioTime();
                             // planned = t0 + t_start + delaySec ⇒
                             // 要 planned = now + lead ⇒ t_start = now + lead − t0 − delaySec
                             const delay = (window.__ext.metrics().delaySec) || 10;
                             return (now - t0) + 0.6 - delay;
                           }""")
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
        # ★ kill 浏览器进程树 + 删 profile 目录 + 确认无残留（EXT-005 第 2 点 (a)）
        try:
            out["cleanup"] = prof_ctx.close()
        except Exception as e:
            out["cleanup_error"] = str(e)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, "echo_sched_probe.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        out["_out_path"] = p
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=20.0)
    ap.add_argument("--port", type=int, default=8793)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-lock", action="store_true",
                    help="不持共享机器锁（默认持；铁律：只能排队，不能抢）")
    ap.add_argument("--lock-wait", type=float, default=600.0,
                    help="等待共享锁的最长秒数")
    args = ap.parse_args(argv)
    r = run_sched_probe(delay_sec=args.delay, out_dir=args.out, port=args.port,
                        lock=not args.no_lock, lock_wait=args.lock_wait)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
