#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ext033_e2e.py — ★ EXT-033 的真实三引擎 e2e 一轮

## 本轮要同时满足 EXT-033 的 A/B/C/D/E

| 项 | 做法 |
|---|---|
| **A 输入** | ★ **只抓页面元素音频**：`createMediaElementSource(<audio>)` → `MediaStreamDestination` ⇒ 送进**扩展已有的上行链路**（`window.__ext.startUplink(stream, …)`）⇒ **不碰系统声音**（EXT-033 A 第三条路，明确允许） |
| **B 录音** | webm（MediaRecorder，timeslice 分片）+ **WAV**（AudioWorklet 并联静音支路抓无损 PCM）；stop 后**等 `dataavailable` + `onstop`** 才落盘 ⇒ 文件完整 |
| **C 对比** | 见 `ext033_analyze.py`：player 每段从 WAV 按 `dubOnsets` 切出，实测 d_player / 时长比 / 互相关峰 / SNR |
| **D sync_err** | player 端**实测有符号误差** = 实际起播 − (t0+t_start+D) ⇒ P50/P95/max |
| **E 交付** | `shared/ext_listen/ext033_<时间>/`（录音 + WAV + README + 对比表） |

## 为什么输入走「页面元素」而不是 tabCapture
EXT-032/§25.3 已把 tabCapture 的失败钉死（`getMediaStreamId` 拿不到 ⇒ 降级
getDisplayMedia ⇒ 整机声）。EXT-033 A 给了三条路，本轮**实测**结论：

* `--allowlisted-extension-id=<插件ID>` —— **不是 tabCapture 的开关**
  （它是 `chrome.automation` 的开关）；实测 activeTab 门槛没解除。
* `commands._execute_action` + SendInput —— **技术上可行**（已修好
  `SendInput` 的 `INPUT` 结构体尺寸 bug，快捷键能送达页面），
  但 Edge 把常用组合键（Ctrl+Shift+Y 等）**保留**给浏览器 ⇒ 扩展命令不触发。
* ★ **页面元素 WebAudio 抓取** —— **本轮采用**：只抓页面元素，不抓整机。

⇒ 三条路的**原始错误**都写在 `status/notes/sec26_ext033.md` 里，不藏。

## 跑法
    python tests/smoke/ext033_e2e.py
"""
from __future__ import annotations

import base64
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import traceback

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import browser_harness as H          # noqa: E402
import machine_lock as ML            # noqa: E402
from ext028_029_e2e import (start_bridge, wait_bridge_ready,   # noqa: E402
                            _free_port)


def wait_bridge_ready_ext033(proc, pair_port: int, *, real: bool,
                              timeout: float = 300.0) -> dict:
    """等 bridge 就绪。

    ★ 回声模式（`real=False`）没有引擎 ⇒ `mode` 是 `'echo'`、
      `engine_state` 不是 `'ready'` ⇒ 不能用 ext028_029_e2e 的那个判据
      （否则会**干等 300 s** 超时）。这里只要求 /status 能应答。
    """
    import urllib.request
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError("bridge 进程已退出，rc=%s" % proc.returncode)
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/status" % pair_port, timeout=3) as r:
                j = json.loads(r.read().decode("utf-8"))
            st = j.get("status") or {}
            last = st
            if real:
                if st.get("mode") == "real" and st.get("engine_state") == "ready":
                    _log("bridge 就绪：engine_state=%s" % st.get("engine_state"))
                    return st
            else:
                if st.get("mode") in ("echo", "real"):
                    _log("bridge 就绪（回声模式）：mode=%s" % st.get("mode"))
                    return st
        except Exception as e:
            last = {"error": str(e)}
        time.sleep(2.0)
    raise RuntimeError("bridge 未在 %.0fs 内就绪，最后状态=%r" % (timeout, last))


def start_bridge_ext033(log_path: str, *, audio_dump_dir: str,
                        real: bool = True):
    """起 bridge。★ `real=False` ⇒ **回声模式**（不加载任何引擎、不碰 NPU/GPU）。

    回声模式用来**先验管道**（元素抓取 / 录音完整性 / WAV / 时间轴 / sync_err），
    避免在真实引擎跑之前把 5 分钟浪费在 plumbing 错误上。
    """
    if real:
        return start_bridge(log_path, spk_bypass=False,
                            audio_dump_dir=audio_dump_dir)
    from ext.app_root import resolve_app_root
    app_root = resolve_app_root()
    if not app_root:
        raise RuntimeError("找不到实时字幕 App 安装目录")
    app_py = os.path.join(app_root, "python", "python.exe")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, os.path.join(ROOT, ".runtime_deps")] +
        ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    ws_port, pair_port = _free_port(), _free_port()
    cmd = [
        app_py, "-m", "ext.bridge",
        "--host", "127.0.0.1", "--port", str(ws_port),
        "--pair-port", str(pair_port),
        "--delay", "10",
        "--target-lang", "zh",
        "--margin-out", os.path.join(os.path.dirname(log_path), "margin.json"),
    ]
    if audio_dump_dir:
        cmd += ["--audio-dump-out", audio_dump_dir]
    _log("起 bridge（回声模式，不加载引擎）：%s" % " ".join(cmd))
    lf = open(log_path, "wb")
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=lf,
                            stderr=subprocess.STDOUT)
    proc._e2e_logfile = lf                       # noqa: SLF001
    proc._e2e_ports = (ws_port, pair_port)      # noqa: SLF001
    return proc

OUT_DIR = os.path.join(ROOT, ".tmp", "ext033_e2e")

#: 素材：英文 SPE 60 s（EXT-033 A：「素材用英文 SPE 0–60 s」）
SRC_WAV = (r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
           r"\test_en_60s.wav")

#: 录音**至少**要这么长（EXT-033 B：「≥75 s」）
MIN_REC_SEC = 75.0
#: 多久没有新配音段 ⇒ 认为「最后一段播完了」
QUIET_SEC = 12.0
#: 硬上限（防止无限跑）
MAX_REC_SEC = 240.0
#: 收尾再加的秒数（EXT-033 B：「最后一段播完再加 3 s」）
TAIL_SEC = 3.0


def _log(msg: str) -> None:
    print("[ext033-e2e] %s" % msg, flush=True)


# ══════════════════════════════════════════════════════════════════
# ① 本地 http 服务（**带 CORS** ⇒ 扩展页里的 <audio> 能被 WebAudio 处理）
# ══════════════════════════════════════════════════════════════════
class _AudioHandler(http.server.SimpleHTTPRequestHandler):
    wav_path = ""
    page_html = ""

    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        # ★ 扩展页（chrome-extension://）要跨源读这段音频
        #   ⇒ 没有 ACAO 时 `createMediaElementSource` 会得到**静音**（tainted）。
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")

    def do_GET(self):
        if self.path.startswith("/audio.wav"):
            try:
                with open(self.wav_path, "rb") as f:
                    data = f.read()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self._cors()
            self.end_headers()
            self.wfile.write(data)
            return
        body = self.page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)


class _QuietTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_http_server(wav_path: str, title: str):
    _AudioHandler.wav_path = wav_path
    _AudioHandler.page_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>%s</title></head>
<body style="background:#111;color:#eee;font:16px sans-serif">
<h1 id="t">%s</h1>
<audio id="a" src="/audio.wav" autoplay controls style="width:90%%"></audio>
<p id="s">loading</p>
<script>
  const a = document.getElementById('a');
  a.addEventListener('timeupdate', () => {
    document.getElementById('s').textContent = 't=' + a.currentTime.toFixed(1);
  });
</script>
</body></html>""" % (title, title)
    port = _free_port()
    srv = _QuietTCPServer(("127.0.0.1", port), _AudioHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port, "http://127.0.0.1:%d/index.html" % port, title


# ══════════════════════════════════════════════════════════════════
# ② 扩展页里的「页面元素音频抓取」⇒ 送进扩展已有的上行链路
# ══════════════════════════════════════════════════════════════════
JS_ELEMENT_UPLINK = """
() => new Promise(async (res) => {
  try {
    const url = %r, wsUrl = %r, token = %r;
    const a = new Audio(url);
    a.crossOrigin = 'anonymous';     // ★ 没有 CORS 头就是静音（tainted）
    a.loop = false;
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    const src = ctx.createMediaElementSource(a);   // ★ 只抓这个元素
    const dest = ctx.createMediaStreamDestination();
    src.connect(dest);                // ⇒ 抓取流
    src.connect(ctx.destination);     // ⇒ 保持可听
    window.__elemCtx = ctx;
    window.__elemAudio = a;
    await a.play();
    const st = await window.__ext.startUplink(dest.stream, wsUrl, token,
                                              'element');
    res({ok:true, start: st, ctxState: ctx.state,
         sampleRate: ctx.sampleRate,
         currentTime: a.currentTime});
  } catch (e) {
    res({ok:false, error: String((e && e.message) || e),
         stack: String((e && e.stack) || '')});
  }
})
"""


def _write_b64(path: str, b64: str) -> int:
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    with open(path, "wb") as f:
        f.write(raw)
    return len(raw)


# ══════════════════════════════════════════════════════════════════
# ③ 一轮
# ══════════════════════════════════════════════════════════════════
def run_round(tag: str, *, wav_path: str, no_lock: bool = False,
              real: bool = True, min_rec_sec: float = MIN_REC_SEC,
              quiet_sec: float = QUIET_SEC) -> dict:
    out_dir = os.path.join(OUT_DIR, tag)
    os.makedirs(out_dir, exist_ok=True)
    audio_dump_dir = os.path.join(out_dir, "audio_dump")
    bridge_log = os.path.join(out_dir, "bridge.log")

    proc = None
    srv = None
    bs = None
    summary: dict = {
        "tag": tag, "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "out_dir": out_dir, "src_wav": wav_path,
        "min_rec_sec": min_rec_sec, "quiet_sec": quiet_sec,
        "real": real, "tail_sec": TAIL_SEC,
    }
    rc = 1

    import contextlib
    lock_cm = (contextlib.nullcontext() if no_lock
               else ML.hold("ext", wait_timeout=1800.0, poll_sec=5.0, log=_log))
    try:
        with lock_cm:
            proc = start_bridge_ext033(bridge_log,
                                      audio_dump_dir=audio_dump_dir,
                                      real=real)
            ws_port, pair_port = proc._e2e_ports              # noqa: SLF001
            summary["bridge_ws_port"] = ws_port
            summary["bridge_pair_port"] = pair_port
            status = wait_bridge_ready_ext033(proc, pair_port, real=real)
            summary["bridge_status"] = status

            title = "EXT033 element %s" % tag
            srv, http_port, page_url, title = start_http_server(wav_path, title)
            summary["page_url"] = page_url
            summary["audio_url"] = "http://127.0.0.1:%d/audio.wav" % http_port

            extra = [
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--allow-running-insecure-content",
                "--disable-features=MediaFoundationVideoCapture",
            ]
            profile = os.path.join(ROOT, ".tmp", "pw_ext",
                                   "ext033_%s" % tag)
            with H.BrowserSession(profile, extra_args=extra,
                                  reuse_profile=True) as bs:
                if not bs.ext_sw_alive():
                    raise RuntimeError("扩展 SW 没起来")

                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:%d/pair" % pair_port,
                    headers={"Origin": "chrome-extension://%s" % H.EXT_ID})
                with urllib.request.urlopen(req, timeout=5) as r:
                    token = json.loads(r.read().decode("utf-8"))["token"]

                player = bs.open_ext_page("player.html")
                time.sleep(4.0)

                # ★★ A：**页面元素音频** ⇒ 送进扩展的上行链路
                el = player.evaluate(
                    JS_ELEMENT_UPLINK % (summary["audio_url"],
                                         "ws://127.0.0.1:%d/" % ws_port,
                                         token))
                summary["element_capture"] = el
                _log("元素抓取：%r" % json.dumps(el, ensure_ascii=False)[:300])
                if not el.get("ok"):
                    raise RuntimeError("元素抓取失败：%r" % el)

                # ★★ B：开始录音（webm + WAV 同时开始）
                rec = player.evaluate(
                    "() => window.__ext.startDubRecording(0)")
                summary["record_start"] = rec
                _log("开始录音：%r" % rec)

                # 等上行真的跑起来
                ok = False
                for _ in range(30):
                    time.sleep(1.0)
                    m = player.evaluate("() => window.__ext.metrics()")
                    up = m.get("uplink") or {}
                    n_frames = up.get("frameCount", up.get("frames", 0))
                    # ★ 用 `uplink.running` 判定（本轮走 startUplink，
                    #   不是 startCapture ⇒ metrics.captureStarted 一直是 false）
                    if (m.get("uplink") or {}).get("running") and n_frames > 0:
                        ok = True
                        summary["capture_ok"] = ok
                        summary["capture_mode"] = m.get("captureMode")
                        summary["uplink_frame_count"] = n_frames
                        break
                summary["capture_ok"] = ok
                _log("上行起来了：%s（mode=%r frames=%r）"
                     % (ok, summary.get("capture_mode"),
                        summary.get("uplink_frame_count")))

                # ★ 等「最后一段播完」
                t_start_rec = time.time()
                last_tts = 0
                last_change = time.time()
                n_delivered = 0
                while True:
                    time.sleep(1.0)
                    m = player.evaluate("() => window.__ext.metrics()")
                    link = m.get("link") or {}
                    n_delivered = link.get("dubDelivered") or 0
                    # ★★ 停止判据必须用 **ttsSegments**（**有 TTS 的段数**），
                    #   **不能**用 dubDelivered ——
                    #   素材播完后上游仍在推**静音**（ASR='—'），
                    #   那些段也被算进 dubDelivered ⇒ 永远等不到「安静」。
                    #   （本轮实测：71 个 dubDelivered 里只有 **13** 个真有 TTS。）
                    n_tts = link.get("ttsSegments") or 0
                    if n_tts != last_tts:
                        last_tts = n_tts
                        last_change = time.time()
                        _log("有 TTS 的配音段 %d（t=%.0fs；含空段共 %d）"
                             % (n_tts, time.time() - t_start_rec, n_delivered))
                    elapsed = time.time() - t_start_rec
                    quiet = time.time() - last_change
                    if elapsed >= min_rec_sec and quiet >= quiet_sec:
                        _log("收尾：已录 %.1fs，静默 %.1fs，TTS 段 %d"
                             % (elapsed, quiet, n_tts))
                        break
                    if elapsed >= MAX_REC_SEC:
                        _log("⚠️ 到达硬上限 %.0fs，强制收尾（TTS 段 %d）"
                             % (MAX_REC_SEC, n_tts))
                        break
                summary["rec_elapsed_sec"] = round(time.time() - t_start_rec, 3)
                summary["n_dub_delivered"] = n_delivered
                summary["n_tts_segments"] = last_tts

                # ★★ B：停录音并**等 onstop**（保证文件完整）
                time.sleep(TAIL_SEC)
                stop = player.evaluate(
                    "() => window.__ext.stopDubRecordingAsync()")
                summary["record_stop"] = stop
                # ★ 落盘「录音起点」⇒ 分析脚本能把 player 的实际起播
                #   换算成 WAV 里的位置（同一时钟轴）。
                with open(os.path.join(out_dir, "record_stop.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(stop, f, ensure_ascii=False, indent=2)
                _log("停止录音：%r" % json.dumps(stop, ensure_ascii=False)[:300])

                blob = player.evaluate("() => window.__ext.dubRecordingBlob()")
                if blob and blob.get("ok"):
                    p = os.path.join(out_dir, "dub_player.webm")
                    n = _write_b64(p, str(blob.get("base64") or ""))
                    summary["dub_recording"] = {
                        "path": p, "bytes": n, "mime": blob.get("mime"),
                        "durationSec": blob.get("durationSec"),
                    }
                    _log("webm 落盘：%d 字节" % n)
                else:
                    summary["dub_recording_error"] = blob

                wav = player.evaluate("() => window.__ext.dubRecordingWav()")
                if wav and wav.get("ok"):
                    p = os.path.join(out_dir, "dub_player.wav")
                    n = _write_b64(p, str(wav.get("b64") or ""))
                    summary["dub_wav"] = {
                        "path": p, "bytes": n, "rate": wav.get("rate"),
                        "samples": wav.get("samples"),
                        "durationSec": wav.get("durationSec"),
                    }
                    _log("WAV 落盘：%d 字节（%s Hz / %s 样本 / %.3f s）"
                         % (n, wav.get("rate"), wav.get("samples"),
                            wav.get("durationSec") or 0))
                else:
                    summary["dub_wav_error"] = wav

                # ★★ D：player 端实测的同步误差
                sync = player.evaluate("() => window.__ext.dubSyncStats()")
                with open(os.path.join(out_dir, "dub_sync.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(sync, f, ensure_ascii=False, indent=2)
                summary["dub_sync"] = {
                    "axis": sync.get("axis"), "t0Sec": sync.get("t0Sec"),
                    "p50": sync.get("p50"), "p95": sync.get("p95"),
                    "max": sync.get("max"), "min": sync.get("min"),
                    "n": len(sync.get("errs") or []),
                }
                _log("sync_err（player 实测，有符号）：%r" % summary["dub_sync"])

                m = player.evaluate("() => window.__ext.metrics()")
                with open(os.path.join(out_dir, "metrics.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(m, f, ensure_ascii=False, indent=2)
                summary["metrics_key"] = {
                    "captureMode": m.get("captureMode"),
                    "captureModeDetail": m.get("captureModeDetail"),
                    "t0Axis": m.get("t0Axis"), "t0Sec": m.get("t0Sec"),
                    "pcmRateLast": m.get("pcmRateLast"),
                    "pcmRateAssumed": m.get("pcmRateAssumed"),
                    "dubDelivered": (m.get("link") or {}).get("dubDelivered"),
                    "dubRescheduled": m.get("dubRescheduled"),
                    "lastFrameAt": m.get("lastFrameAt"),
                    "dubSyncP50": m.get("dubSyncP50"),
                    "dubSyncP95": m.get("dubSyncP95"),
                    "dubPcmTapped": m.get("dubPcmTapped"),
                }
                _log("metrics：%r" % summary["metrics_key"])

                try:
                    player.screenshot(path=os.path.join(out_dir, "player.png"))
                except Exception as e:
                    _log("截图失败：%s" % e)

                # 收口尾段 + margin.json 落盘
                try:
                    fl = player.evaluate("() => window.__ext.flushUplink()")
                    _log("flush：%r" % fl)
                    time.sleep(4.0)
                    md = player.evaluate(
                        "() => window.__ext.requestMarginDump(120000)")
                    summary["margin_dump"] = md
                    _log("margin dump：%r" % md)
                except Exception as e:
                    summary["margin_dump_error"] = \
                        "%s: %s" % (type(e).__name__, e)

                time.sleep(8)
                rc = 0

    except Exception as e:
        _log("❌ 失败：%s: %s" % (type(e).__name__, e))
        traceback.print_exc()
        summary["error"] = "%s: %s" % (type(e).__name__, e)
        rc = 1
    finally:
        if bs is not None:
            try:
                bs.__exit__(None, None, None)
            except Exception:
                pass
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(15)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc._e2e_logfile.close()          # noqa: SLF001
            except Exception:
                pass
    summary["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    summary["rc"] = rc
    return summary


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    tag = time.strftime("%Y%m%d_%H%M%S")
    real = not (len(sys.argv) > 1 and sys.argv[1] == "--echo")
    min_rec = MIN_REC_SEC if real else 20.0
    quiet = QUIET_SEC if real else 6.0
    s = run_round(tag, wav_path=SRC_WAV, real=real, min_rec_sec=min_rec,
                  quiet_sec=quiet)
    p = os.path.join(OUT_DIR, "summary_%s.json" % tag)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    _log("轮次摘要：%s" % p)
    _log("结果：%r" % json.dumps(s.get("metrics_key") or s.get("error"),
                                 ensure_ascii=False))
    return int(s.get("rc") or 0)


if __name__ == "__main__":
    sys.exit(main())
