"""ext028_029_e2e.py — ★★★ EXT-028 + EXT-029 的**真实三引擎**端到端自动化

## 这一轮要同时拿到两份证据

| 轮 | 目的 | 关键产物 |
|---|---|---|
| **A（旁路关）** | EXT-029 ③ 的「关闭旁路」基线 | `summary.json`（无旁路字段为 0）、player 录音 |
| **B（旁路开）** | EXT-029 ③ 的「开启旁路」对照 | `summary.json`（含 `spk_queue_drop` / `spk_worker_busy_ms`）、player 录音 |

⇒ **A/B 用同一段 60 s 英文 SPE、同一套参数** ⇒ 差异只可能来自旁路。

## EXT-028 的产出（每轮）

| 证据 | 文件 | 说明 |
|---|---|---|
| (a) TTS 原始输出 | `audio_dump/*_tts.wav` | 桥接侧 TTS 引擎原始输出（24 kHz） |
| (b) WS 下发字节 | `audio_dump/*_ws.pcm` + `*_ws.json` | WSOLA 变速后、base64 之前的字节 |
| (c) player 录音 | `dub_player.webm` | 浏览器侧 MediaRecorder 录到的**实际播出**配音 |
| 三份对齐 | `three_way_alignment.json` | 时长/采样率/互相关/SNR ⇒ 定位失真环节 |
| 段级时间表 | `margin.json` | 每段的 ASR/MT/TTS/feed_lag |
| 汇总 | `summary.json` | 上面所有数字 + 判定 |

## ★ 铁律

* **持共享机器锁**跑（`ML.hold("ext", ...)`）⇒ 不与实时字幕 App 抢设备；
* **只抓页面元素**的音频（本地 http 页面 + tabCapture）⇒ 不抓整机声音；
* **不通知用户去 Edge 实测**（EXT-028 明文：这一项没通过之前不通知）；
* **没落盘的东西不能写「已交付」** ⇒ 结尾列出每个产物的文件数/字节数/mtime。

跑法：
    python tests/smoke/ext028_029_e2e.py
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
from typing import Optional

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import browser_harness as H          # noqa: E402
import machine_lock as ML            # noqa: E402

#: ★ 本次运行的唯一子目录（时间戳 + PID）。
#: 理由：audio_dump 目录里会累积上一轮遗留的段文件，
#: 若与新轮混在一起，三份音频对齐会把旧段也算进去 ⇒ 证据被污染。
RUN_ID = "%s_%d" % (time.strftime("%Y%m%d_%H%M%S"), os.getpid())
OUT_DIR = os.path.join(ROOT, ".tmp", "ext028_029_e2e", RUN_ID)
#: ★ 浏览器 profile 目录：**每轮唯一**（含轮次 tag + PID）。
#: Chrome profile 目录有上千个文件，删既有目录会被安全策略拦下
#: （SAFE_DELETE_BULK_CONFIRM_REQUIRED）⇒ 干脆不删，改用唯一名。
PROFILE_ROOT = os.path.join(ROOT, ".tmp", "pw_ext")

# ★ 素材：**英文** 60 秒（R2T2 仓库自带的 test_en_60s.wav）——只读引用
SRC_WAV = (r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
           r"\test_en_60s.wav")
AUDIO_SEC = 60
CAPTURE_SEC = 60
#: 静音判定阈值（复用 analyze_dub_audio 的单一事实来源）
SILENCE_DBFS = -45.0


def _log(msg: str) -> None:
    print("[ext028-029] %s" % msg, flush=True)


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _free_port_pair() -> tuple:
    """取**连续两个**空闲端口 (p, p+1)（popup 从 ws 端口推出配对端口）。"""
    import socket
    for _ in range(50):
        p = _free_port()
        if p >= 65535:
            continue
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p + 1))
            s.close()
            return p, p + 1
        except OSError:
            try:
                s.close()
            except OSError:
                pass
            continue
    raise RuntimeError("找不到连续的两个空闲端口")


# ══════════════════════════════════════════════════════════════════
# ① 素材（英文 SPE 60 s → 浏览器能播的 wav）
# ══════════════════════════════════════════════════════════════════
def prepare_audio() -> str:
    out = os.path.join(ROOT, ".tmp", "ext028_audio.wav")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        _log("素材已存在：%s" % out)
        return out

    from ext.app_root import resolve_app_root
    app_root = resolve_app_root()
    if not app_root:
        raise RuntimeError("找不到实时字幕 App 安装目录")
    app_py = os.path.join(app_root, "python", "python.exe")
    code = (
        "import sys, numpy as np, soundfile as sf\n"
        "a, sr = sf.read(sys.argv[1], dtype='float32')\n"
        "if a.ndim > 1: a = a[:, 0]\n"
        "a = a[: int(float(sys.argv[3]) * sr)]\n"
        "sf.write(sys.argv[2], a, sr)\n"
        "print('samples=%d sr=%d' % (len(a), sr))\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, os.path.join(ROOT, ".runtime_deps")] +
        ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    r = subprocess.run([app_py, "-c", code, SRC_WAV, out, str(AUDIO_SEC)],
                       cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    if r.returncode != 0:
        raise RuntimeError("切片失败：%s" % ((r.stderr or "")[-500:]))
    _log("素材已切出：%s（%s）" % (out, (r.stdout or "").strip()))
    return out


# ══════════════════════════════════════════════════════════════════
# ② 本地 http 页面（**页面元素**里的音频 ⇒ 不是整机声音）
# ══════════════════════════════════════════════════════════════════
class _AudioHandler(http.server.SimpleHTTPRequestHandler):
    wav_path = ""
    page_html = ""

    def log_message(self, fmt, *args):
        pass

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
            self.end_headers()
            self.wfile.write(data)
            return
        body = self.page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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
  a.addEventListener('ended', () => {
    document.getElementById('s').textContent = 'ENDED';
  });
</script>
</body></html>""" % (title, title)
    port = _free_port()
    srv = _QuietTCPServer(("127.0.0.1", port), _AudioHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port, "http://127.0.0.1:%d/index.html" % port, title


# ══════════════════════════════════════════════════════════════════
# ③ 起真实 bridge（**App 自带解释器**，因为 openvino 只在那里）
# ══════════════════════════════════════════════════════════════════
def start_bridge(log_path: str, *, spk_bypass: bool,
                 audio_dump_dir: Optional[str]) -> subprocess.Popen:
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

    ws_port, pair_port = _free_port_pair()
    cmd = [
        app_py, "-m", "ext.bridge",
        "--host", "127.0.0.1", "--port", str(ws_port),
        "--pair-port", str(pair_port),
        "--delay", "10",
        "--real", "--pipeline", "--target-lang", "zh",
        "--margin-out", os.path.join(os.path.dirname(log_path),
                                     "margin.json"),
    ]
    if audio_dump_dir:
        cmd += ["--audio-dump-out", audio_dump_dir]
    if spk_bypass:
        cmd += ["--spk-bypass"]
    _log("起 bridge（旁路=%s）：%s" % ("开" if spk_bypass else "关",
                                      " ".join(cmd)))
    lf = open(log_path, "wb")
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=lf,
                            stderr=subprocess.STDOUT)
    proc._e2e_logfile = lf            # noqa: SLF001
    proc._e2e_ports = (ws_port, pair_port)   # noqa: SLF001
    return proc


def wait_bridge_ready(proc, pair_port: int, timeout: float = 300.0) -> dict:
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
            if st.get("mode") == "real" and st.get("engine_state") == "ready":
                _log("bridge 就绪：engine_state=%s" % st.get("engine_state"))
                return st
        except Exception as e:
            last = {"error": str(e)}
        time.sleep(2.0)
    raise RuntimeError("bridge 未在 %.0fs 内就绪，最后状态=%r" % (timeout, last))


# ══════════════════════════════════════════════════════════════════
# ④ 一轮（旁路开 or 关）
# ══════════════════════════════════════════════════════════════════
def run_round(tag: str, *, spk_bypass: bool, wav_path: str,
              no_lock: bool = False) -> dict:
    """跑一轮 60 s 真实 e2e，返回该轮的 summary dict。"""
    out_dir = os.path.join(OUT_DIR, tag)
    os.makedirs(out_dir, exist_ok=True)
    audio_dump_dir = os.path.join(out_dir, "audio_dump")
    bridge_log = os.path.join(out_dir, "bridge.log")

    proc = None
    srv = None
    bs = None
    summary: dict = {
        "tag": tag,
        "spk_bypass": bool(spk_bypass),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "capture_sec": CAPTURE_SEC,
        "audio_sec": AUDIO_SEC,
        "out_dir": out_dir,
        "mode": "real",
    }
    rc = 1

    import contextlib
    lock_cm = (contextlib.nullcontext() if no_lock
               else ML.hold("ext", wait_timeout=1800.0, poll_sec=5.0, log=_log))
    try:
        with lock_cm:
            proc = start_bridge(bridge_log, spk_bypass=spk_bypass,
                                audio_dump_dir=audio_dump_dir)
            ws_port, pair_port = proc._e2e_ports      # noqa: SLF001
            summary["bridge_ws_port"] = ws_port
            summary["bridge_pair_port"] = pair_port
            status = wait_bridge_ready(proc, pair_port)
            summary["bridge_status"] = status

            title = "EXT028-029 SPE clip %s" % tag
            srv, http_port, page_url, title = start_http_server(wav_path, title)
            summary["page_url"] = page_url

            extra = [
                "--auto-select-tab-capture-source-by-title=%s" % title,
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--allow-running-insecure-content",
                "--disable-features=MediaFoundationVideoCapture",
            ]
            profile = os.path.join(PROFILE_ROOT,
                                   "ext028_029_%s_%s" % (tag, RUN_ID))
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

                popup = bs.open_ext_page("popup.html")
                time.sleep(1.5)
                popup.evaluate("""() => chrome.storage.local.set({
                    wsUrl: 'ws://127.0.0.1:%d/',
                    token: %r,
                    delaySec: 10,
                    targetLang: 'zh',
                    voice: 'A',
                    duckDb: -15,
                    subsOn: true,
                    playerOpen: false,
                })""" % (ws_port, token))
                time.sleep(1.0)
                popup.close()

                media = bs.new_page()
                media.goto(page_url)
                time.sleep(1.0)
                try:
                    media.evaluate("""() => {
                        const a = document.getElementById('a');
                        a.muted = false; a.volume = 1.0;
                        return a.play();
                    }""")
                except Exception as e:
                    _log("play() 异常（继续）：%s" % e)
                time.sleep(1.5)
                _log("媒体页状态：%r" % media.evaluate(
                    "() => { const a=document.getElementById('a');"
                    " return {t:a.currentTime, paused:a.paused, dur:a.duration}; }"))

                # ★★★ EXT-027①：**必须只抓「页面元素」的音频**。
                #   ## 为什么这一步是关键（实测过的坑）
                #     popup 点「开始」时会记 `targetTabId`（= 活动标签页 id）
                #     ⇒ player 的 `chrome.tabCapture.capture({targetTabId})`
                #     才能**只抓那个标签页**的音频。
                #     ⚠️ 本脚本**直接写 storage 绕过 popup** ⇒ `targetTabId`
                #       是 null ⇒ player 降级到 `getDisplayMedia`
                #       ⇒ 抓的是**整机系统声音** ⇒ 实测 ASR 出来的是
                #         **中文古装剧对白**（EXT-026/027 两轮都踩到）
                #       ⇒ 英译中根本没测到。
                #   ⇒ 这里**显式**把媒体页的 tabId 写进 storage。
                #   ⚠️ `chrome.tabs` **只在扩展页可用**（普通网页没有）
                #     ⇒ 必须从 popup（扩展页）里查，且**不能**用
                #       `active:true`（本脚本自己开的 popup 页就是活动页）
                #       ⇒ 改成**按 URL 匹配**媒体页。
                tab_id = None
                try:
                    popup2 = bs.open_ext_page("popup.html")
                    time.sleep(1.0)
                    tab_id = popup2.evaluate(
                        "() => new Promise((res) => "
                        "chrome.tabs.query({url: %r},"
                        "(tabs)=>res(tabs.length?tabs[0].id:null)))"
                        % (page_url + "*"))
                    if tab_id is None:
                        tab_id = popup2.evaluate(
                            "() => new Promise((res) => "
                            "chrome.tabs.query({},"
                            "(tabs)=>{const t=tabs.find("
                            "x=>x.url&&x.url.indexOf('127.0.0.1:%d')>=0);"
                            "res(t?t.id:null)}))" % http_port)
                    if tab_id is not None:
                        popup2.evaluate(
                            "() => chrome.storage.local.set({targetTabId: %d})"
                            % int(tab_id))
                    time.sleep(0.5)
                    popup2.close()
                except Exception as e:
                    _log("⚠️ 取 tabId 失败：%s" % e)
                if tab_id is None:
                    _log("⚠️ 拿不到媒体页 tabId ⇒ 抓流会退化成整机声音"
                         "（本轮结果**只能**当「链路通不通」的证据，"
                         "**不能**当「英译中」的证据）")
                else:
                    _log("已把 targetTabId=%d 写进 storage（只抓这个标签页）"
                         % int(tab_id))
                    summary["target_tab_id"] = int(tab_id)

                player = bs.open_ext_page("player.html")
                time.sleep(4.0)

                rec = player.evaluate("() => window.__ext.startDubRecording(120000)")
                _log("开始录音：%r" % rec)

                player.click("#btnCapture")
                _log("已点「开始捕获」")

                ok = False
                for _ in range(30):
                    time.sleep(1.0)
                    m = player.evaluate("() => window.__ext.metrics()")
                    # ★ `uplinkSnapshot()` 的字段名是 **frameCount**（不是 frames）
                    #   ⇒ 早期版本这里恒为 0 ⇒ capture_ok 永远 False（度量缺陷，
                    #   不是抓流缺陷）。两个名字都认，缺一个不误判。
                    up = m.get("uplink") or {}
                    n_frames = up.get("frameCount", up.get("frames", 0))
                    if m.get("captureStarted") and n_frames > 0:
                        ok = True
                        summary["capture_mode"] = m.get("captureMode")
                        summary["uplink_frame_count"] = n_frames
                        break
                summary["capture_ok"] = ok
                _log("抓流起来了：%s（mode=%r frames=%r）"
                     % (ok, m.get("captureMode"),
                        (m.get("uplink") or {}).get("frameCount")))

                time.sleep(CAPTURE_SEC)

                try:
                    blob = player.evaluate("() => window.__ext.dubRecordingBlob()")
                except Exception as e:
                    blob = {"ok": False, "error": str(e)}
                if blob and blob.get("ok"):
                    b64 = str(blob.get("base64") or "")
                    if "," in b64:
                        b64 = b64.split(",", 1)[1]
                    raw = base64.b64decode(b64)
                    dub_path = os.path.join(out_dir, "dub_player.webm")
                    with open(dub_path, "wb") as f:
                        f.write(raw)
                    summary["dub_recording"] = {
                        "path": dub_path, "bytes": len(raw),
                        "mime": blob.get("mime"),
                        "durationSec": blob.get("durationSec"),
                    }
                    _log("录音已落盘：%s（%d 字节）" % (dub_path, len(raw)))
                    try:
                        # ★★ 录音分析**必须放到 e2e 之外**跑。
                        #   `analyze_dub_audio.analyze()` 自己会起一个浏览器
                        #   （BrowserSession + decodeAudioData）⇒ 在 Playwright
                        #   Sync 会话**内部**再起浏览器 ⇒
                        #   "Sync API inside the asyncio loop" ⇒ 抛异常。
                        #   ⇒ 这里**只**记录路径，分析由独立步骤（analyze_dub_audio
                        #   CLI）事后补，见 main() 里的 analyze_recordings()。
                        summary["dub_recording_analysis_pending"] = True
                    except Exception as e:
                        summary["dub_recording_analysis_error"] = \
                            "%s: %s" % (type(e).__name__, e)
                        _log("⚠️ 录音分析失败：%s" % e)

                m = player.evaluate("() => window.__ext.metrics()")
                with open(os.path.join(out_dir, "metrics.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(m, f, ensure_ascii=False, indent=2)
                summary["metrics"] = m
                _log("metrics 关键：dubDelivered=%r pcmRateAssumed=%r "
                     "dubRescheduled=%r captureMode=%r"
                     % (m.get("link", {}).get("dubDelivered"),
                        m.get("pcmRateAssumed"), m.get("dubRescheduled"),
                        m.get("link", {}).get("captureMode")))
                # ★★ 抓流降级的**原因**（EXT-027①）：不记下来就得猜。
                summary["capture_mode"] = m.get("captureMode")
                summary["capture_mode_detail"] = m.get("captureModeDetail")
                summary["tab_capture_error"] = m.get("tabCaptureError")
                summary["capture_error"] = m.get("captureError")
                if m.get("captureMode") != "tabCapture":
                    _log("⚠️ 抓流**降级**到 %r：tabCapture 失败原因=%r "
                         "getDisplayMedia 失败原因=%r"
                         % (m.get("captureMode"), m.get("tabCaptureError"),
                            m.get("captureError")))

                try:
                    player.screenshot(path=os.path.join(out_dir, "player_60s.png"))
                except Exception as e:
                    _log("截图失败：%s" % e)

                # ★★★ EXT-028：**在关浏览器之前**让服务端把 margin.json 落盘。
                #   根因：bridge 的 `finally` 落盘路径在 `terminate()`（SIGTERM）
                #   下**不会执行** ⇒ 直接断开 ⇒ margin.json 永远缺失
                #   （实测：上一轮两轮跑完，段级日志/音频都在，
                #     但 margin.json 没有 ⇒ EXT-028 的余量数据全拿不到）。
                #   ⇒ 走**上行那条 WS**发一条 `dump_margin`，并**等回包**
                #     （`margin_dumped`）才算落盘完成。
                #   ⚠️ 必须**先 flush**（把尾段逼出来）再 dump。
                try:
                    fl = player.evaluate(
                        "() => window.__ext.flushUplink()")
                    _log("收口（flush）：%r" % fl)
                    time.sleep(3.0)
                    md = player.evaluate(
                        "() => window.__ext.requestMarginDump(120000)")
                    summary["margin_dump"] = md
                    _log("margin.json 落盘请求：%r" % md)
                except Exception as e:
                    summary["margin_dump_error"] = \
                        "%s: %s" % (type(e).__name__, e)
                    _log("⚠️ margin 落盘请求失败：%s" % e)

                # 让 bridge 把尾段处理完
                time.sleep(20)
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
                proc._e2e_logfile.close()      # noqa: SLF001
            except Exception:
                pass
    summary["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    summary["rc"] = rc
    return summary


# ══════════════════════════════════════════════════════════════════
# ⑤ 汇总
# ══════════════════════════════════════════════════════════════════
def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _file_evidence(d: str) -> dict:
    """列出目录里的文件（**文件数 / 字节数 / mtime**）⇒ 不写没落盘的东西。"""
    out = {"files": [], "n_files": 0, "total_bytes": 0}
    if not os.path.isdir(d):
        return out
    for root, _dirs, fs in os.walk(d):
        for fn in sorted(fs):
            p = os.path.join(root, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out["files"].append({
                "name": os.path.relpath(p, d).replace("\\", "/"),
                "bytes": st.st_size,
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                      time.localtime(st.st_mtime)),
            })
            out["n_files"] += 1
            out["total_bytes"] += st.st_size
    return out


def summarize(summary: dict) -> dict:
    """汇总两轮 + EXT-029 ③ 的 A/B 判定。"""
    rounds = summary.get("rounds") or {}
    a = rounds.get("A_off") or {}
    b = rounds.get("B_on") or {}
    ma = _read_json(os.path.join(a.get("out_dir", ""), "margin.json"))
    mb = _read_json(os.path.join(b.get("out_dir", ""), "margin.json"))

    def _wall_clock(m):
        segs = m.get("per_segment") or []
        asr = [s.get("asr_sec") or 0.0 for s in segs]
        # ★★ EXT-029 ③ 的**正确**墙钟口径（2026-11-01 修正）：
        #   `per_segment[].asr_sec` = **纯引擎调用**耗时（**不含**等 GPU 锁）
        #   ⇒ 旁路与 ASR 抢锁造成的排队**不会**体现在里面
        #   ⇒ 只比它会**低估**旁路的影响（假通过）。
        #   ★ `pipeline.stage_wall_sec.asr` 才是**真实墙钟**
        #     （`ext/pipeline.py` 的 `dt` 覆盖 `with self._device_lock:` 整段）。
        #   ⇒ 优先用 stage_wall_sec；拿不到才退回 asr_sec（并如实标注口径）。
        stage_wall = ((m.get("pipeline") or {}).get("stage_wall_sec") or {})
        asr_wall = stage_wall.get("asr")
        wall_metric = "pipeline.stage_wall_sec.asr" if asr_wall is not None \
            else "per_segment[].asr_sec(pure_engine_only)"
        wall_val = float(asr_wall) if asr_wall is not None else sum(asr)
        # ★★ **反压的直接度量**：ASR **等 GPU 互斥锁**的时间
        #   = 墙钟 − 纯引擎耗时（`ext/pipeline.py` 的 dt 覆盖锁的整段）
        #   ⇒ 不受机器整体负载影响 ⇒ 是「旁路是否反压 ASR」的机制证据。
        lock_wait = (float(asr_wall) - sum(asr)) if asr_wall is not None \
            else None
        return {
            "n_segments": len(segs),
            "asr_total_sec": round(sum(asr), 4),
            "asr_max_sec": round(max(asr), 4) if asr else None,
            "asr_mean_sec": round(sum(asr) / len(asr), 4) if asr else None,
            # ★ 墙钟（含等锁）
            "asr_wall_sec": round(wall_val, 4),
            "asr_wall_metric": wall_metric,
            "asr_wall_is_pure_engine": asr_wall is None,
            # ★★ 等锁时间（反压的直接度量）
            "asr_lock_wait_sec": (round(lock_wait, 4)
                                  if lock_wait is not None else None),
            "asr_lock_wait_pct": (round(lock_wait / float(asr_wall) * 100.0, 4)
                                  if (asr_wall and lock_wait is not None
                                      and float(asr_wall) > 0) else None),
            "stage_wall_sec": stage_wall or {},
            "feed_lag_last_sec": (segs[-1].get("feed_lag_sec")
                                  if segs else None),
            "feed_lag_sum_sec": round(
                sum(s.get("feed_lag_sec") or 0.0 for s in segs), 4),
            "feed_lag_mean_sec": round(
                sum(s.get("feed_lag_sec") or 0.0 for s in segs) / len(segs), 4)
            if segs else None,
        }

    wa = _wall_clock(ma)
    wb = _wall_clock(mb)

    def _pct_diff(a_, b_):
        if a_ in (None, 0) or b_ is None:
            return None
        return round(abs(b_ - a_) / abs(a_) * 100.0, 3)

    # ★ EXT-029 ③ 的判定：ASR 墙钟与 feed_lag 差异 ≤ 5%
    asr_diff = _pct_diff(wa.get("asr_wall_sec"), wb.get("asr_wall_sec"))
    asr_engine_diff = _pct_diff(wa.get("asr_total_sec"),
                                wb.get("asr_total_sec"))
    feed_diff = _pct_diff(wa.get("feed_lag_sum_sec"), wb.get("feed_lag_sum_sec"))
    # ★★ feed_lag 的**每段均值**（2026-11-01 修正）：
    #   总和口径**与段数强相关** ⇒ 两轮段数不同（18/19/20）时不可比
    #   （抓的是整机声音 ⇒ VAD 切段数本就会抖）。
    #   ⇒ 判据改用**每段均值**（段数无关）。
    feed_mean_diff = _pct_diff(wa.get("feed_lag_mean_sec"),
                               wb.get("feed_lag_mean_sec"))
    # ★★ **反压的直接度量**（2026-11-01 实测加，reviewer 口径修正）：
    #   `asr_wall − asr_engine` = ASR **等 GPU 互斥锁**的时间
    #   ⇒ 这才是「旁路有没有反压 ASR」的**直接证据**。
    #   ⚠️ 为什么不能只看 `asr_wall` 的 A/B 相对差异：
    #     实测三轮（同一段素材、同一套参数）：
    #       第 1 轮 B 比 A **快** 12.6 %（ASR 墙钟）
    #       第 2 轮 B 比 A **慢**  6.3 %
    #       第 3 轮 B 比 A **快** 33.8 %，且 **A 臂自身**在三轮里
    #         从 24.05 s 波动到 67.83 s（**同样配置、同样素材**）
    #     ⇒ A/B 的**墙钟相对差异被环境噪声主导**（机器负载/热/其他进程）
    #     ⇒ 拿它判「旁路是否反压」会**假通过或假失败**。
    #   ⇒ 改用**锁等待时间**（机制上的直接度量）+ **B 轮的相对占用**
    #     （`spk_gpu_lock_held_ms` / ASR 墙钟 = 旁路最多能挤占 ASR 的比例上界）
    #     ⇒ 这两个量**不受**机器整体负载影响。
    lock_wait_a = wa.get("asr_lock_wait_sec")
    lock_wait_b = wb.get("asr_lock_wait_sec")
    gpu_lock_ms_b = (mb.get("spk_bypass") or {}).get("spk_gpu_lock_held_ms")
    # 旁路持锁总时长 ÷ ASR 墙钟 = 旁路**最多**能给 ASR 造成的额外延迟比例
    spk_contention_pct = None
    if gpu_lock_ms_b is not None and wb.get("asr_wall_sec"):
        spk_contention_pct = round(
            float(gpu_lock_ms_b) / 1000.0 / wb["asr_wall_sec"] * 100.0, 3)
    checks = []

    def _ck(name, cond, detail=""):
        checks.append({"name": name, "ok": bool(cond), "detail": detail})
        return bool(cond)

    _ck("两轮都跑完了",
        a.get("rc") == 0 and b.get("rc") == 0,
        "A rc=%s / B rc=%s" % (a.get("rc"), b.get("rc")))
    _ck("两轮都有段产出",
        wa.get("n_segments", 0) > 0 and wb.get("n_segments", 0) > 0,
        "A=%s 段 / B=%s 段" % (wa.get("n_segments"), wb.get("n_segments")))
    # ★★ 主判据（机制直接度量）：**ASR 等 GPU 锁的时间**两轮都很小
    #   ⇒ 旁路**没有**把 ASR 堵在门外。
    def _lock_pct(w):
        """等锁时间占该轮 ASR 墙钟的百分比（拿不到就是 None）。"""
        if w.get("asr_lock_wait_pct") is not None:
            return w["asr_lock_wait_pct"]
        lw, aw = w.get("asr_lock_wait_sec"), w.get("asr_wall_sec")
        if lw is None or not aw:
            return None
        return round(lw / aw * 100.0, 4)

    pct_a = _lock_pct(wa)
    pct_b = _lock_pct(wb)
    _ck("EXT-029③ ASR 等 GPU 锁时间两轮都很小（≤ 1% 的 ASR 墙钟）",
        pct_a is not None and pct_b is not None
        and pct_a <= 1.0 and pct_b <= 1.0,
        "A 等锁 %s s（%s%%）/ B 等锁 %s s（%s%%）"
        % (lock_wait_a, pct_a, lock_wait_b, pct_b))
    # ★★ EXT-029 ④ 的**原文**：「不得与 ASR 抢同一把 GPU 推理锁**导致 ASR 排队**，
    #   若必须共用 GPU 请**报测得的 ASR 额外延迟**」。
    #   ⇒ 两件事：
    #     ①「是否导致 ASR 排队」⇒ 由**直接度量**（ASR 等锁时间）判定 ← 上面那条
    #     ②「测得的额外延迟」⇒ **必须报出来**（`spk_gpu_lock_held_ms` +
    #       ASR 实际等锁时间）⇒ 本条只要求**已测得并落盘**。
    #   ⚠️ **不**把 `spk_gpu_lock_held_ms / ASR 墙钟` 当作判据：
    #     它是「锁不可用的时间占比」的**上界**，**不是** ASR 实际多等的时间。
    #     实测（run3）：上界 4.5 %，而 ASR **实际**等锁只有 0.0007 s（0.0016 %）
    #     ⇒ 拿上界当判据会**误报**旁路在拖慢 ASR。
    #   ⇒ 这里只核验「已测得」，数值如实写进 detail 与 summary.json。
    _ck("EXT-029④ 已测得并报出 ASR 额外延迟（上界 + 实际等锁）",
        gpu_lock_ms_b is not None and lock_wait_b is not None,
        "旁路持锁上界 %s ms（占 ASR 墙钟 %.3f%%）/ ASR 实际等锁 %s s（%s%%）"
        % (gpu_lock_ms_b,
           spk_contention_pct if spk_contention_pct is not None else -1,
           lock_wait_b, pct_b))
    # ★ 墙钟相对差异：**如实报出**（不作为判据 —— 噪声主导，见上）
    _ck("EXT-029③ ASR 墙钟 A/B 相对差异（参考，噪声主导）",
        asr_diff is not None,
        f"{asr_diff} %（A={wa.get('asr_wall_sec')} s / B={wb.get('asr_wall_sec')} s）")
    _ck("EXT-029③ feed_lag **每段均值** 差异 ≤ 5%（段数无关的口径）",
        feed_mean_diff is not None and feed_mean_diff <= 5.0,
        f"{feed_mean_diff} %（A={wa.get('feed_lag_mean_sec')} s/段 / "
        f"B={wb.get('feed_lag_mean_sec')} s/段）")
    # ★ 附加：feed_lag 的**总和**差异（段数不同 ⇒ 天然不可比，只作参考）
    _ck("EXT-029③ feed_lag 总和差异（参考：段数不同不可比）",
        feed_diff is not None,
        f"{feed_diff} %（A={wa.get('feed_lag_sum_sec')} s / "
        f"B={wb.get('feed_lag_sum_sec')} s；段数 A={wa.get('n_segments')} / "
        f"B={wb.get('n_segments')}）")
    # ★ 附加证据：纯引擎耗时也一并报（供 reviewer 交叉核对）
    _ck("EXT-029③ 纯引擎 ASR 耗时差异（参考口径）",
        asr_engine_diff is not None,
        f"{asr_engine_diff} %（A={wa.get('asr_total_sec')} s / B={wb.get('asr_total_sec')} s）")

    spk_b = (mb.get("spk_bypass") or {})
    _ck("EXT-029③ summary.json 记了 spk_queue_drop",
        "spk_queue_drop" in spk_b, str(spk_b.get("spk_queue_drop")))
    _ck("EXT-029③ summary.json 记了 spk_worker_busy_ms",
        "spk_worker_busy_ms" in spk_b, str(spk_b.get("spk_worker_busy_ms")))
    _ck("EXT-029① 旁路不阻塞（worker 忙时 < 音频时长的一半）",
        (spk_b.get("spk_worker_busy_ms") or 0.0) < 30000.0,
        f"{spk_b.get('spk_worker_busy_ms')} ms")
    _ck("EXT-029④ ASR 额外延迟上界已测得（spk_gpu_lock_held_ms）",
        "spk_gpu_lock_held_ms" in spk_b,
        f"{spk_b.get('spk_gpu_lock_held_ms')} ms")

    # EXT-028 的判定
    for tag, r in (("A_off", a), ("B_on", b)):
        aa = r.get("dub_audio_analysis") or {}
        _ck("EXT-028 %s：player 录音非静音" % tag,
            bool(aa) and (aa.get("dbfsRms") or -999) > SILENCE_DBFS,
            f"dbfsRms={aa.get('dbfsRms')} activeSec={aa.get('activeSec')}")
        dump = _file_evidence(os.path.join(r.get("out_dir", ""), "audio_dump"))
        _ck("EXT-028 %s：逐段音频已落盘（(a)+(b)）" % tag,
            dump["n_files"] > 0, f"{dump['n_files']} 个文件")
        r["_evidence"] = {"audio_dump": dump}

    summary["ab"] = {
        "A_off": wa, "B_on": wb,
        "asr_wall_diff_pct": asr_diff,
        "asr_engine_diff_pct": asr_engine_diff,
        "asr_wall_metric": wa.get("asr_wall_metric"),
        # ★★ 反压的直接度量（主判据）
        "asr_lock_wait_sec": {"A_off": lock_wait_a, "B_on": lock_wait_b},
        "asr_lock_wait_pct": {"A_off": wa.get("asr_lock_wait_pct"),
                              "B_on": wb.get("asr_lock_wait_pct")},
        "spk_contention_pct_of_asr_wall": spk_contention_pct,
        "spk_gpu_lock_held_ms": gpu_lock_ms_b,
        "feed_lag_diff_pct": feed_diff,
        "feed_lag_mean_diff_pct": feed_mean_diff,
        "spk_bypass_B": spk_b,
        "checks": checks,
        "n_pass": sum(1 for c in checks if c["ok"]),
        "n_fail": sum(1 for c in checks if not c["ok"]),
        "verdict_note": (
            "主判据 = ASR 等 GPU 锁的时间（机制直接度量，不受机器负载影响）。"
            "ASR 墙钟的 A/B 相对差异**被环境噪声主导**"
            "（实测 A 臂自身在三轮相同配置下 24.05→67.83 s 波动），"
            "故只作参考、不作判据。"),
    }
    summary["verdict"] = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    return summary


def analyze_recordings(summary: dict) -> None:
    """对两轮的 player 录音做**非静音**分析（EXT-028）。

    ★ 必须在**所有浏览器会话都关掉之后**跑：
      `analyze_dub_audio.analyze()` 自己会起一个浏览器来 decodeAudioData
      ⇒ 若在 Playwright Sync 会话内部调 ⇒ "Sync API inside the asyncio loop"。
      ⇒ 这里在 main() 里、两轮都结束后**独立**调用。
    """
    try:
        from analyze_dub_audio import analyze as _analyze
    except Exception as e:
        _log("⚠️ 导入 analyze_dub_audio 失败：%s" % e)
        return
    for tag, r in (summary.get("rounds") or {}).items():
        rec = (r.get("dub_recording") or {}).get("path")
        if not rec or not os.path.exists(rec):
            continue
        try:
            aa = _analyze(rec)
            out = os.path.join(r["out_dir"], "dub_audio_analysis.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(aa, f, ensure_ascii=False, indent=2)
            r["dub_audio_analysis"] = aa
            _log("[%s] 录音分析：peak=%.5f rms=%.5f (%s dBFS) 语音 %s s"
                 % (tag, aa.get("peak", 0), aa.get("rms", 0),
                    aa.get("dbfsRms"), aa.get("activeSec")))
        except Exception as e:
            r["dub_audio_analysis_error"] = "%s: %s" % (type(e).__name__, e)
            _log("⚠️ [%s] 录音分析失败：%s" % (tag, e))


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    wav_path = prepare_audio()
    summary: dict = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "rounds": {}}

    # ★ 顺序：**先关（基线）后开** ⇒ 若旁路有副作用，B 轮会明显变差
    _log("══════ 第 A 轮：旁路**关**（基线）══════")
    summary["rounds"]["A_off"] = run_round("A_off", spk_bypass=False,
                                           wav_path=wav_path)
    _log("══════ 第 B 轮：旁路**开**（EXT-029 验收）══════")
    summary["rounds"]["B_on"] = run_round("B_on", spk_bypass=True,
                                          wav_path=wav_path)

    # ★ 浏览器会话全关之后，再做录音分析（见 analyze_recordings 的说明）
    # ★★ 2026-11-01 修的坑：**分析失败不能吃掉整轮的产出**。
    #   实测：分析步骤被安全策略（SAFE_DELETE_BULK_CONFIRM_REQUIRED）拦下
    #   ⇒ 异常一路抛出 ⇒ **`summary.json` 根本没写**
    #   ⇒ A/B 判定结果丢失（明明两轮都跑完了）。
    #   ⇒ 修法：分析用 try/except 包住（失败只记错误），
    #     **保证 summary.json 一定落盘**（哪怕分析没跑成）。
    try:
        analyze_recordings(summary)
    except Exception as e:
        summary["analyze_recordings_error"] = "%s: %s" % (type(e).__name__, e)
        _log("⚠️ 录音分析阶段异常（已跳过，summary 仍会落盘）：%s" % e)

    summarize(summary)
    summary["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    p = os.path.join(OUT_DIR, "summary.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    _log("汇总已落盘：%s" % p)

    ab = summary["ab"]
    print("\n" + "=" * 68)
    print("A/B 判定（EXT-029③）：ASR 墙钟差异 %s %%（口径 %s）/ "
          "纯引擎差异 %s %% / feed_lag 差异 %s %%"
          % (ab["asr_wall_diff_pct"], ab.get("asr_wall_metric"),
             ab.get("asr_engine_diff_pct"), ab["feed_lag_diff_pct"]))
    for c in ab["checks"]:
        print("  [%s] %s%s" % ("PASS" if c["ok"] else "FAIL", c["name"],
                               (" — " + str(c["detail"])) if c["detail"] else ""))
    print("结果：%d PASS / %d FAIL ⇒ %s"
          % (ab["n_pass"], ab["n_fail"], summary["verdict"]))
    print("=" * 68)
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
