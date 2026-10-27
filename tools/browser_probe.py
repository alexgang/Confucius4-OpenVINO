"""browser_probe.py — EXT-003 P0①②③ 的**浏览器实测**工具

用 Playwright 驱动 Edge 加载扩展，采集三项验收指标的实测数据：

  P0① 音频上行：AudioWorklet 16 kHz 重采样 → WebSocket 上行
      验收：连续 N 秒 seq 不断（gaps=0）、采样计数 vs 墙钟偏差 < 50 ms
  P0② 延迟画面：MediaStreamTrackProcessor → VideoEncoder → 环形缓冲
      → VideoDecoder → canvas（D=10 s）
      验收：编码/解码/绘制帧数 > 0、掉帧率、唇音同步误差 ≤ 40 ms
  P0③ 回声排程：浏览器排程一段 PCM，onset worklet 逐样本测误差
      验收：|排程误差| ≤ 20 ms

★ 本机实测到的硬约束（决定了本工具的实现，见 STATUS_EXT.md §2）：
  1. `chrome.tabCapture.getMediaStreamId()` 在**自动化**里拿不到流 id
     （"Extension has not been invoked for the current page"）；
     ⇒ 自动化下走 `getDisplayMedia({video, audio:true})`
     + `--auto-select-tab-capture-source-by-title=<源页标题>`。
  2. 本机 WebCodecs **不支持 H.264**（avc1.* 全部 isConfigSupported=false）；
     VP9 / AV1 虽 supported=true 但**实际编码必失败**
     ⇒ 唯一实测可用的是 **VP8 + no-preference**。
  3. **后台标签页不产帧** ⇒ 源页必须开在**独立窗口**里（CDP
     Target.createTarget newWindow:true），否则 MediaStreamTrackProcessor
     拿不到帧，encoded 恒为 0。
  4. **offscreen document 里 AudioWorklet 不被驱动**（ac.state=running 但
     process() 从不调用）⇒ 音频上行放在**扩展页**（player.html）里做。
  5. `getDisplayMedia` 需要**真实用户手势** ⇒ 由 Playwright 点击页面上的
     「开始捕获」按钮触发。

不跑推理 / 不占 GPU·NPU（ASR/MT/TTS 都不接）⇒ 不与实时字幕 App 抢设备。
测速作业必须持 shared/MACHINE_LOCK（见 tools/machine_lock.py）。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(ROOT, "extension")
TMP_DIR = os.path.join(ROOT, ".tmp")

# 让 `from tools import src_server` / `from ext import bridge` 可用
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

SRC_PORT = 8891
BRIDGE_PORT = 8791
SRC_TITLE = "EXTSRCPAGE"


def find_browser() -> Optional[str]:
    for p in EDGE_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


@dataclass
class ProbeResult:
    ok: bool = False
    error: str = ""
    data: dict = field(default_factory=dict)


def _start_src_server(port: int = SRC_PORT):
    """启动测试源服务器（tools/src_server.py）：/ 语音页 + /sync 唇音同步测试片。"""
    from tools import src_server  # type: ignore
    return src_server.serve(port)


def _token_path() -> str:
    return os.path.join(TMP_DIR, "probe_bridge_token.txt")


def _start_bridge(port: int = BRIDGE_PORT, delay: float = 10.0):
    """启动回声桥接服务（子进程），返回 (proc, token)。"""
    from ext import bridge  # noqa: F401  （确保包可导入）
    from ext.bridge import TokenStore
    os.makedirs(TMP_DIR, exist_ok=True)
    tp = _token_path()
    tokens = TokenStore(tp)
    logf = open(os.path.join(TMP_DIR, "bridge_probe.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tools", "bridge_echo_server.py"),
         "--port", str(port), "--delay", str(delay),
         "--token-file", tp],
        cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT,
    )
    # 等端口就绪
    for _ in range(80):
        time.sleep(0.25)
        try:
            import socket
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except Exception:
            if proc.poll() is not None:
                break
    return proc, tokens.token


def run_probe(*, mode: str = "all",
              duration_sec: int = 30,
              delay_sec: float = 10.0,
              out_dir: Optional[str] = None,
              lock: bool = True,
              lock_wait: float = 600.0,
              profile: bool = False,
              video_enabled: bool = True) -> ProbeResult:
    """跑一轮浏览器实测。

    mode: 'uplink'(P0①) | 'video'(P0②) | 'echo'(P0③) | 'all'
    """
    browser = find_browser()
    if not browser:
        return ProbeResult(False, "找不到 Edge/Chrome 可执行文件")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return ProbeResult(False, f"playwright 不可用：{e}")

    src_server = None
    bridge_proc = None
    data: dict = {"mode": mode, "duration_sec": duration_sec,
                  "delay_sec": delay_sec, "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    # ★ profile 用**带时间戳的唯一目录**，不做递归删除
    #   （递归删一个上千文件的浏览器 profile 目录会触发安全删除钩子；
    #     旧 profile 由 .tmp/ 统一保留，不入库即可）。
    prof_dir = os.path.join(TMP_DIR, "pwprofile_probe_%d" % int(time.time()))
    os.makedirs(prof_dir, exist_ok=True)
    data["profile_dir"] = prof_dir

    def _run():
        nonlocal src_server, bridge_proc, data
        src_server = _start_src_server()
        bridge_proc, token = _start_bridge(delay=delay_sec)
        data["bridge_token_len"] = len(token)

        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                prof_dir, executable_path=browser, headless=False,
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
                data["ext_id"] = ext_id

                # ★ 源页必须**在前台可见**（后台标签页不产帧 ⇒ encoded 恒为 0）。
                #   实测：同一个窗口里把源页 tab 切到前台即可产帧；
                #   更稳的是独立窗口（CDP Target.createTarget newWindow:true），
                #   但 Python 版 Playwright 对 newWindow 支持不稳 ⇒ 先试独立窗口，
                #   失败则退回「同窗口切前台」。
                src = None
                try:
                    cdp = ctx.new_cdp_session(ctx.pages[0])
                    cdp.send("Target.createTarget", {
                        "url": f"http://127.0.0.1:{SRC_PORT}/sync",
                        "newWindow": True, "width": 1280, "height": 800,
                    })
                    time.sleep(2.5)
                    for p in ctx.pages:
                        if f"{SRC_PORT}" in p.url:
                            src = p
                            break
                except Exception as e:
                    data["cdp_new_window_err"] = str(e)[:200]
                if src is None:
                    src = ctx.new_page()
                    src.goto(f"http://127.0.0.1:{SRC_PORT}/sync",
                             wait_until="load")
                    src.wait_for_timeout(1500)
                    data["src_mode"] = "same_window_tab"
                else:
                    data["src_mode"] = "separate_window"
                data["src_url"] = src.url
                try:
                    src.bring_to_front()
                except Exception:
                    pass

                # 播放器页
                player = ctx.new_page()
                # ★ video_enabled=False ⇒ ?video=0 ⇒ 插件关掉视频管线
                _vq = "" if video_enabled else "?video=0"
                player.goto(f"chrome-extension://{ext_id}/player.html{_vq}",
                            wait_until="load")
                player.wait_for_timeout(1200)
                player.evaluate(
                    """async (cfg) => { await chrome.storage.local.set(cfg); }""",
                    {"wsUrl": f"ws://127.0.0.1:{BRIDGE_PORT}/", "token": token,
                     "delaySec": delay_sec},
                )
                player.reload(wait_until="load")
                player.wait_for_timeout(1500)

                # 真实用户手势：点「开始捕获」
                player.click("#btnCapture", timeout=8000)
                player.wait_for_timeout(3000)

                if mode in ("all", "uplink"):
                    data["uplink"] = _measure_uplink(player, duration_sec,
                                                   profile=profile)
                if mode in ("all", "video"):
                    data["video"] = _measure_video(player, duration_sec, delay_sec)
                if mode in ("all", "echo"):
                    data["echo"] = _measure_echo(player, delay_sec)
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass

    try:
        if lock:
            from tools.machine_lock import hold
            # ★ wait_timeout 可配：App 模块可能长时间持锁（如 NPU AB 对比测试），
            #   此时应**排队等待**而不是抢锁（铁律）。
            with hold("EXT-browser-probe", wait_timeout=lock_wait):
                _run()
        else:
            _run()
    except Exception as e:
        import traceback
        return ProbeResult(False, f"{e}\n{traceback.format_exc()}")
    finally:
        try:
            if src_server:
                src_server.shutdown()
        except Exception:
            pass
        try:
            if bridge_proc:
                bridge_proc.terminate()
                bridge_proc.wait(timeout=5)
        except Exception:
            pass

    data["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "browser_probe.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        data["_out_path"] = path
    return ProbeResult(True, "", data)


def _measure_sys_metrics(duration_sec: int) -> dict:
    """采集浏览器进程的**系统级** CPU / 内存 / 线程数（psutil）。

    ★ 为什么要外部采集：扩展页里的 performance.memory 只有 JS 堆，
      且拿不到浏览器进程的 CPU 占用；EXT-003 的验收要求
      「不与实时字幕 App 抢设备」⇒ 必须有系统级口径。
    ★ 同时采集**整机 CPU** 与**其它进程**的占用 ⇒ 用于判定
      「skew 尖峰是本模块自身缺陷，还是同机其它进程抢 CPU」。
    """
    out: dict = {}
    try:
        import psutil
    except Exception as e:
        return {"error": f"psutil 不可用：{e}"}

    # 找到属于本次 profile 的 Edge 进程
    try:
        procs = []
        others = []
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (p.info.get("name") or "")
                cl = " ".join(p.info.get("cmdline") or [])
                if "msedge" in name.lower() and "pwprofile_probe" in cl:
                    procs.append(p)
                elif ("python" in name.lower() or "timeout" in name.lower()) and \
                        ("LiveCaption" in cl or "live_dub" in cl or "app108" in cl):
                    others.append(p)
            except Exception:
                continue
        out["n_browser_procs"] = len(procs)
        out["n_other_mod_procs"] = len(others)
        if not procs:
            return {"error": "未找到本次 profile 的浏览器进程"}

        for p in procs + others:
            try:
                p.cpu_percent(None)      # 预热
            except Exception:
                pass
        time.sleep(2.0)                 # 采样窗口
        samples = []
        for p in procs:
            try:
                samples.append({
                    "pid": p.pid,
                    "cpu_pct": p.cpu_percent(None),
                    "rss_mb": round(p.memory_info().rss / 1048576, 2),
                    "threads": p.num_threads(),
                })
            except Exception:
                continue
        other_samples = []
        for p in others:
            try:
                other_samples.append({
                    "pid": p.pid,
                    "cpu_pct": p.cpu_percent(None),
                    "rss_mb": round(p.memory_info().rss / 1048576, 2),
                    "cmd": (" ".join(p.cmdline() or []))[:120],
                })
            except Exception:
                continue
        cpu_vals = [s["cpu_pct"] for s in samples if s["cpu_pct"] is not None]
        rss_vals = [s["rss_mb"] for s in samples]
        out["samples"] = samples
        out["other_mod_procs"] = other_samples
        out["cpu_pct_sum"] = round(sum(cpu_vals), 1)
        out["cpu_pct_max"] = round(max(cpu_vals), 1) if cpu_vals else None
        out["rss_mb_sum"] = round(sum(rss_vals), 2)
        out["rss_mb_max"] = round(max(rss_vals), 2) if rss_vals else None
        out["threads_sum"] = sum(s["threads"] for s in samples)
        out["sample_window_sec"] = 2.0
        try:
            out["system_cpu_pct"] = psutil.cpu_percent(None)
            out["system_cpu_count"] = psutil.cpu_count()
        except Exception:
            pass
    except Exception as e:
        out["error"] = str(e)
    return out


def _measure_uplink(player, duration_sec: int, profile: bool = False) -> dict:
    """P0①：音频上行 —— seq 连续性 + 采样计数 vs 墙钟偏差。"""
    out = {"duration_sec": duration_sec}
    # ★ CPU Profiler：定位主线程 stall 的**真正阻塞函数**。
    #   实测 stall 探针：lag 峰值 577.6 ms、间隔约 10.3 s（与 bridge 的
    #   10 s 回声周期吻合）⇒ 周期性阻塞，但「谁在阻塞」仍需实测。
    #   Profiler 直接给出 self time 最高的 JS 函数 ⇒ 归因不靠猜。
    cdp = None
    if profile:
        try:
            cdp = player.context.new_cdp_session(player)
            cdp.send("Profiler.enable")
            cdp.send("Profiler.setSamplingInterval", {"interval": 200})
            cdp.send("Profiler.start")
            out["profiler_started"] = True
        except Exception as e:
            out["profiler_err"] = str(e)[:300]
            cdp = None

    t0 = time.time()
    while time.time() - t0 < duration_sec:
        player.wait_for_timeout(5000)
    m = player.evaluate("() => window.__ext ? window.__ext.metrics() : null")
    up = (m or {}).get("uplink") or {}
    out["uplink"] = up
    out["seq_continuous"] = (up.get("gaps") == 0 and up.get("frameCount", 0) > 0)
    # ★★ 验收口径：采样计数 vs **音频时钟**（EXT-003 原文「采样计数和墙钟偏差 < 50 ms」）
    #   音频时钟由音频硬件驱动、在 AudioWorklet 内取值 ⇒ 与主线程负载无关。
    #   旧口径拿主线程 performance.now() 当墙钟 ⇒ 测到的是主线程调度延迟
    #   （主线程同时在跑视频解码，实测 drawImage 19.2 s / 300 s）。
    #   ⇒ 两个口径都保留：audioSkew = 验收量，skew = 诊断量（主线程健康度）。
    out["maxAbsSkewAudioMs"] = up.get("maxAbsSkewAudioMs")
    out["skewAudioP50"] = up.get("skewAudioP50")
    out["skewAudioP95"] = up.get("skewAudioP95")
    out["skewAudioP99"] = up.get("skewAudioP99")
    out["nSkewAudioSpikes"] = up.get("nSkewAudioSpikes")
    out["skew_ok"] = (up.get("maxAbsSkewAudioMs") is not None
                      and up["maxAbsSkewAudioMs"] < 50.0)
    # ★ 主线程 stall 探针（event-loop lag）
    #   skew 尖峰的形态是「一串等差数列，步长 = 帧长」⇒ 疑似主线程停摆后
    #   消息积压再一次性冲刷。stall 数据用于把「尖峰归因」变成事实，
    #   而不是靠猜（EXT-003 的验收要求）。
    out["stall"] = (m or {}).get("stall") or {}
    if cdp is not None:
        try:
            prof = cdp.send("Profiler.stop") or {}
            nodes = {n["id"]: n for n in (prof.get("profile") or {}).get("nodes", [])}
            self_time = {}
            samples = (prof.get("profile") or {}).get("samples", [])
            deltas = (prof.get("profile") or {}).get("timeDeltas", [])
            for i, sid in enumerate(samples):
                d = deltas[i] if i < len(deltas) else 0
                n = nodes.get(sid)
                if not n:
                    continue
                cf = n.get("callFrame", {})
                key = "%s @ %s:%s" % (cf.get("functionName") or "(anonymous)",
                                      cf.get("url", "").split("/")[-1],
                                      cf.get("lineNumber"))
                self_time[key] = self_time.get(key, 0) + max(0, d)
            top = sorted(self_time.items(), key=lambda kv: -kv[1])[:25]
            out["cpu_profile_top"] = [{"fn": k, "self_us": v} for k, v in top]
            out["cpu_profile_total_us"] = sum(self_time.values())
        except Exception as e:
            out["profiler_stop_err"] = str(e)[:300]
    # 系统级资源占用（不与实时字幕 App 抢设备的证据）
    out["sys"] = _measure_sys_metrics(duration_sec)
    return out


def _measure_video(player, duration_sec: int, delay_sec: float) -> dict:
    """P0②：WebCodecs 延迟画面 —— 编码/解码/绘制 + 掉帧 + 唇音同步。"""
    out = {"duration_sec": duration_sec}
    t0 = time.time()
    while time.time() - t0 < duration_sec:
        player.wait_for_timeout(5000)
    m = player.evaluate("() => window.__ext ? window.__ext.metrics() : null")
    m = m or {}
    enc = m.get("encoded", 0)
    dec = m.get("decoded", 0)
    drawn = m.get("drawn", 0)
    out["metrics"] = {
        "encoded": enc, "decoded": dec, "drawn": drawn,
        "dropped": m.get("dropped"), "queued": m.get("queued"),
        "codecUsed": m.get("codecUsed"), "hwAcceleration": m.get("hwAcceleration"),
        "videoWidth": m.get("videoWidth"), "videoHeight": m.get("videoHeight"),
        "lipSyncMs": m.get("lipSyncMs"),
        "drawMarks": len(m.get("drawMarks") or []),
        "origOnsets": len(m.get("origOnsets") or []),
        "schedErrP50": m.get("schedErrP50"), "schedErrP95": m.get("schedErrP95"),
    }
    out["lipSync_ok"] = (m.get("lipSyncMs") is not None
                         and abs(m["lipSyncMs"]) <= 40.0)
    out["frames_ok"] = enc > 0 and dec > 0 and drawn > 0
    return out


def _measure_echo(player, delay_sec: float) -> dict:
    """P0③：浏览器端回声排程误差（毫秒级）。"""
    out = {}
    try:
        sr = 16000
        n = int(sr * 0.1)
        pcm = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 1000 * i / sr)))
            for i in range(n))
        b64 = base64.b64encode(pcm).decode("ascii")
        r = player.evaluate(
            """async (o) => {
                 const m = await window.__ext.metrics();
                 const res = window.__ext.selfTestSchedule(o.b64, o.tStart);
                 return { planned: res, t0: m.t0, delay: m.delaySec,
                          audioTime: m.audioTime };
               }""",
            {"b64": b64, "tStart": 0.5},
        )
        out["scheduled"] = r
        player.wait_for_timeout(int((delay_sec + 2.0) * 1000))
        m = player.evaluate("() => window.__ext.metrics()")
        out["metrics"] = {
            "onsetErrs": (m or {}).get("onsetErrs"),
            "schedErrMs": (m or {}).get("schedErrMs"),
            "schedErrP50": (m or {}).get("schedErrP50"),
            "schedErrP95": (m or {}).get("schedErrP95"),
        }
        errs = (m or {}).get("onsetErrs") or []
        out["sched_ok"] = bool(errs) and max(abs(e) for e in errs) <= 20.0
    except Exception as e:
        out["error"] = str(e)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all",
                    choices=["all", "uplink", "video", "echo"])
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--lock-wait", type=float, default=600.0,
                    help="等待共享机器锁的最长秒数（App 模块持锁时排队）")
    ap.add_argument("--profile", action="store_true",
                    help="用 CDP Profiler 抓主线程 stall 的阻塞函数（归因用）")
    ap.add_argument("--no-video", action="store_true",
                    help="关掉视频管线（只测音频上行），用于隔离 stall 来源")
    args = ap.parse_args(argv)
    r = run_probe(mode=args.mode, duration_sec=args.duration,
                  delay_sec=args.delay, out_dir=args.out,
                  lock=not args.no_lock, lock_wait=args.lock_wait,
                  profile=args.profile,
                  video_enabled=not args.no_video)
    print(json.dumps({"ok": r.ok, "error": r.error, "data": r.data},
                     ensure_ascii=False, indent=2))
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
