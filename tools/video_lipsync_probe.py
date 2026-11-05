"""video_lipsync_probe.py — EXT-003 P0② + P0③ 的联合实测

一次浏览器会话里同时测两项，减少启动开销：

  P0② 延迟画面（WebCodecs）
      抓流 → MediaStreamTrackProcessor → VideoEncoder(VP8) → 环形缓冲
      → VideoDecoder → canvas（延迟 D）
      验收：encoded/decoded/drawn > 0、掉帧率、**唇音同步误差 ≤ 40 ms**
  P0③ 回声排程误差
      浏览器排程一段 PCM → onset worklet 逐样本测
      「实际出声时刻 − 计划时刻」
      验收：|排程误差| ≤ 20 ms

★ 唇音同步测量的物理前提（见 tools/src_server.py 的 /sync 页）：
  白闪（画面）与 3 kHz beep（声音）在**同一个源时刻**发生
  ⇒ 画面链路与音频链路的延迟差就是唇音同步误差。

★ 本机硬约束（决定实现，见 STATUS_EXT.md §2）：
  * 源页必须开在**前台可见**（后台标签页不产帧 ⇒ encoded 恒为 0）
  * 编码器只能用 **VP8 + no-preference**
  * `getDisplayMedia` 需要真实手势 ⇒ 由 Playwright 点「开始捕获」按钮

不跑推理、不占 GPU·NPU（ASR/MT/TTS 都不接）⇒ 不与实时字幕 App 抢设备。
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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ★ Chrome profile 统一管理（EXT-005 第 2、3 点）：目录放 chrome_profile/，
#   探针结束 kill 浏览器进程树 + 删目录 + 确认无残留。
sys.path.insert(0, os.path.join(ROOT, "tools"))
import chrome_profile  # noqa: E402

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

SRC_PORT = 8894
BRIDGE_PORT = 8794
SRC_TITLE = "EXTSRCPAGE"


def _find_browser() -> Optional[str]:
    for p in EDGE_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def _start_src_server(port: int):
    from tools import src_server  # type: ignore
    return src_server.serve(port)


def _start_bridge(port: int, delay: float, token_path: str):
    os.makedirs(TMP_DIR, exist_ok=True)
    logf = open(os.path.join(TMP_DIR, "vlp_bridge.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tools", "bridge_echo_server.py"),
         "--port", str(port), "--delay", str(delay),
         "--token-file", token_path],
        cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
    import socket
    for _ in range(80):
        time.sleep(0.25)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except Exception:
            if proc.poll() is not None:
                break
    return proc


def _read_token(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def run_probe(*, delay_sec: float = 10.0, video_sec: int = 45,
              out_dir: Optional[str] = None,
              src_port: int = SRC_PORT, bridge_port: int = BRIDGE_PORT,
              lock: bool = True, lock_wait: float = 600.0) -> dict:
    from playwright.sync_api import sync_playwright

    browser = _find_browser()
    if not browser:
        return {"ok": False, "error": "找不到浏览器"}

    out: dict = {"ok": False, "delay_sec": delay_sec,
                 "video_sec": video_sec,
                 "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    src_server = None
    bridge_proc = None
    token_path = os.path.join(TMP_DIR, "vlp_token.txt")
    # ★ Chrome user-data-dir 统一放 chrome_profile/<名称>/（EXT-005 第 3 点）
    #   旧做法在 .tmp\pwprofile_vlp_* ⇒ 残留几十个目录、约 996 MB。
    #   现在：唯一子目录 + 探针结束即删（见 chrome_profile.probe_profile）。
    prof_ctx = chrome_profile.probe_profile("vlp")
    prof_ctx.__enter__()          # 建目录（退出时由 finally 里的 __exit__ 清理）
    prof = prof_ctx.path
    out["profile_dir"] = prof

    # ★ 铁律：计时/测速作业必须持共享机器锁。
    #   本探针要拉起浏览器 + 抓标签页音视频，属设备占用型作业。
    #   锁已存在 ⇒ **排队等待**，绝不抢。
    stack = ExitStack()
    try:
        if lock:
            from tools.machine_lock import hold
            stack.enter_context(
                hold("EXT-lipsync-probe", wait_timeout=lock_wait))
        src_server = _start_src_server(src_port)
        bridge_proc = _start_bridge(bridge_port, delay_sec, token_path)
        token = _read_token(token_path)
        out["token_len"] = len(token)

        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                prof, executable_path=browser, headless=False,
                args=[
                    f"--disable-extensions-except={EXT_DIR}",
                    f"--load-extension={EXT_DIR}",
                    "--no-first-run", "--no-default-browser-check",
                    "--autoplay-policy=no-user-gesture-required",
                    f"--auto-select-tab-capture-source-by-title={SRC_TITLE}",
                ],
            )
            try:
                sw = ctx.service_workers[0] if ctx.service_workers else \
                    ctx.wait_for_event("serviceworker", timeout=20000)
                ext_id = sw.url.split("/")[2]
                out["ext_id"] = ext_id

                # 源页开在**独立窗口**（后台标签页不产帧）
                src = None
                try:
                    cdp = ctx.new_cdp_session(ctx.pages[0])
                    cdp.send("Target.createTarget", {
                        "url": f"http://127.0.0.1:{src_port}/sync",
                        "newWindow": True, "width": 1280, "height": 800,
                    })
                    time.sleep(2.5)
                    for p in ctx.pages:
                        if f"{src_port}" in p.url:
                            src = p
                            break
                except Exception as e:
                    out["cdp_new_window_err"] = str(e)[:200]
                if src is None:
                    src = ctx.new_page()
                    src.goto(f"http://127.0.0.1:{src_port}/sync", wait_until="load")
                    src.wait_for_timeout(1500)
                    out["src_mode"] = "same_window_tab"
                else:
                    out["src_mode"] = "separate_window"
                out["src_url"] = src.url
                try:
                    src.bring_to_front()
                except Exception:
                    pass

                player = ctx.new_page()
                player.goto(f"chrome-extension://{ext_id}/player.html",
                            wait_until="load")
                player.wait_for_timeout(1200)
                player.evaluate(
                    """async (cfg) => { await chrome.storage.local.set(cfg); }""",
                    {"wsUrl": f"ws://127.0.0.1:{bridge_port}/", "token": token,
                     "delaySec": delay_sec},
                )
                player.reload(wait_until="load")
                player.wait_for_timeout(1500)

                # 真实手势：点「开始捕获」
                player.click("#btnCapture", timeout=8000)
                player.wait_for_timeout(4000)

                # ── P0②：视频管线 + 唇音同步 ──────────────────────
                t0 = time.time()
                while time.time() - t0 < video_sec:
                    player.wait_for_timeout(5000)
                m = player.evaluate("() => window.__ext ? window.__ext.metrics() : null")
                m = m or {}
                out["video_metrics"] = {
                    "encoded": m.get("encoded"), "decoded": m.get("decoded"),
                    "drawn": m.get("drawn"), "dropped": m.get("dropped"),
                    "queued": m.get("queued"),
                    "codecUsed": m.get("codecUsed"),
                    "hwAcceleration": m.get("hwAcceleration"),
                    "videoWidth": m.get("videoWidth"),
                    "videoHeight": m.get("videoHeight"),
                    "encWidth": m.get("encWidth"), "encHeight": m.get("encHeight"),
                    "encoderError": m.get("encoderError"),
                    "decoderError": m.get("decoderError"),
                    "drawMarks": len(m.get("drawMarks") or []),
                    "origOnsets": len(m.get("origOnsets") or []),
                }
                lip = m.get("lipSync")
                out["lipSync"] = lip
                out["lipSync_ok"] = bool(lip) and abs(lip.get("meanErrMs", 1e9)) <= 40.0
                out["frames_ok"] = (m.get("encoded", 0) > 0
                                    and m.get("decoded", 0) > 0
                                    and m.get("drawn", 0) > 0)
                out["drop_rate_pct"] = (
                    round(100.0 * (m.get("dropped") or 0) /
                          max(1, (m.get("encoded") or 0)), 3)
                )

                # ── P0③：排程误差（3 次取样） ────────────────────
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
                #   旧写法固定传 (0.5, 2.0, 3.5) ⇒ 第 2、3 次的 planned **已在过去**
                #     ⇒ 插件的 Math.max(currentTime+0.005, planned) 把它钳成"立刻播"
                #     ⇒ 而主线程的 audioCtx.currentTime 在繁忙时滞后真实音频时钟约 43 ms
                #     ⇒ 稳定复现 **43.02 ms** 的假误差（两次独立探针数值完全相同）。
                #   ⇒ 修法：用**当前音频时钟**推算未来的排程时刻。
                for k in range(3):
                    t_start = player.evaluate(
                        """() => {
                             const t0 = window.__ext.getT0();
                             const now = window.__ext.getAudioTime();
                             const delay = (window.__ext.metrics().delaySec) || 10;
                             return (now - t0) + 0.6 - delay;
                           }""")
                    player.evaluate(
                        """(o) => { window.__ext.selfTestSchedule(o.b64, o.tStart); }""",
                        {"b64": b64, "tStart": t_start})
                    player.wait_for_timeout(int((delay_sec + 1.5) * 1000))
                m2 = player.evaluate("() => window.__ext.metrics()") or {}
                out["sched_debug"] = player.evaluate(
                    "() => window.__ext.schedDebug ? window.__ext.schedDebug() : null")
                errs = m2.get("onsetErrs") or []
                out["sched"] = {
                    "onsetErrs": errs,
                    "n_samples": len(errs),
                    "schedErrMs": m2.get("schedErrMs"),
                    "schedErrP50": m2.get("schedErrP50"),
                    "schedErrP95": m2.get("schedErrP95"),
                    "maxAbsErrMs": max((abs(e) for e in errs), default=None),
                }
                out["sched_ok"] = bool(errs) and out["sched"]["maxAbsErrMs"] <= 20.0
                out["ok"] = True
                out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception as e:
        import traceback
        out["error"] = f"{e}\n{traceback.format_exc()}"
    finally:
        for closer in (lambda: src_server and src_server.shutdown(),
                       lambda: bridge_proc and (bridge_proc.terminate(),
                                                bridge_proc.wait(timeout=5))):
            try:
                closer()
            except Exception:
                pass
        try:
            stack.close()      # 释放共享机器锁
        except Exception:
            pass
        # ★ kill 浏览器进程树 + 删 profile 目录 + 确认无残留（EXT-005 第 2 点 (a)）
        try:
            out["cleanup"] = prof_ctx.close()
        except Exception as e:
            out["cleanup_error"] = str(e)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, "video_lipsync_probe.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        out["_out_path"] = p
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=20.0)
    ap.add_argument("--video-sec", type=int, default=45)
    ap.add_argument("--out", default=None)
    ap.add_argument("--src-port", type=int, default=SRC_PORT)
    ap.add_argument("--bridge-port", type=int, default=BRIDGE_PORT)
    ap.add_argument("--no-lock", action="store_true",
                    help="不持共享机器锁（默认持；铁律：只能排队，不能抢）")
    ap.add_argument("--lock-wait", type=float, default=600.0,
                    help="等待共享锁的最长秒数")
    args = ap.parse_args(argv)
    r = run_probe(delay_sec=args.delay, video_sec=args.video_sec,
                  out_dir=args.out, src_port=args.src_port,
                  bridge_port=args.bridge_port,
                  lock=not args.no_lock, lock_wait=args.lock_wait)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
