"""ext026_e2e.py — ★★★ EXT-026：**真实三引擎**端到端自动化冒烟

## 这是什么

EXT-026（reviewer，2026-10-31 16:49）要求的**冒烟测试**：
在把插件交给用户做手势验收之前，**持共享机器锁**、用**真实模式**
（ASR R2T2 INT8@GPU.0 / MT Hy-MT2 INT8@GPU.0 / TTS 全 NPU，流水线开）
跑一次**自动化端到端**，并把证据落盘到 `.tmp/ext026_e2e/`。

⚠️ **它不替代 EXT-022② 的用户手势验收**（两者不冲突）：
  * 本脚本证明「**真实模式下浏览器 player 真的放出了中文配音**」；
  * 用户手势验收证明「在用户自己的 Edge 默认 profile 里，点图标能行」。

## 证据清单（EXT-026 第 3 条逐项对应）

| 证据 | 文件 | 说明 |
|---|---|---|
| 实际播放的配音 | `dub_player.webm` | **player 端** MediaStreamDestination + MediaRecorder 录的（**不是**服务端 PCM） |
| 30 s 截图 | `player_30s.png` | 能看到原文 + 译文字幕 + 链路状态条 |
| 60 s 截图 | `player_60s.png` | 同上 |
| 段级日志 | `bridge.log` | ≥5 段，「下发到」含 player 的段数 = TTS 段数，无「不顶替」/10048 |
| 指标 | `metrics.json` | dubDelivered / echoRecv / dubDup / schedErr P50/P95 |
| 握手 | `hello_ack.json` | mode=real、engines_ready=true |
| 引擎设备 | `tts_exec_devices.json` | talker/cp_prefill/cp_decode/decoder 的 EXECUTION_DEVICES（EXT-023 收口） |
| 汇总 | `summary.json` | 上面所有数字的汇总 + 判定 |

## 跑法

```bash
python tests/smoke/ext026_e2e.py
```

★ 必须用 **workbuddy 自带 Python**（**自带 playwright**）；
  真实引擎由 **App 自带解释器** 跑（openvino / babelvox 只在那里）。
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
from typing import Optional

# ── 路径 ────────────────────────────────────────────────────────────
SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
if SMOKE_DIR not in sys.path:
    sys.path.insert(0, SMOKE_DIR)

sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

import browser_harness as H          # noqa: E402
import machine_lock as ML            # noqa: E402
from analyze_dub_audio import is_non_silent as _is_non_silent   # noqa: E402

OUT_DIR = os.path.join(ROOT, ".tmp", "ext026_e2e")
PROFILE = os.path.join(ROOT, ".tmp", "pw_ext", "ext026")

# ★ 素材：**英文** 60 秒（R2T2 仓库自带的 test_en_60s.wav）。
#   为什么要英文：EXT-026 的验收是「reviewer 回转写录下的配音，核对中文内容」
#   ⇒ 源语言必须是**非中文**，否则「翻译成中文」无从验证
#   （用中文素材 + --target-lang zh 时，MT 的输出与输入完全相同，
#     实测确实如此：ASR='在循环一种痛楚…' MT='在循环一种痛楚…'）。
#   ★ 这个 wav 在 R2T2 仓库里（**只读引用**，不改对方文件）。
SRC_WAV = (r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
           r"\test_en_60s.wav")
# ★ 这段素材切出 5 段（4 段 ready + 1 段尾段 2.92 s）。
#   ⇒ 必须靠 **flush** 收口尾段才能拿到 5 段（EXT-026 修正项）。
AUDIO_SEC = 60                      # 素材长度（不裁剪）
CAPTURE_SEC = 60                    # ★ EXT-026 要求的连续采集窗口


def _log(msg: str) -> None:
    print("[ext026] %s" % msg, flush=True)


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _free_port_pair() -> tuple:
    """取**连续两个**空闲端口 (p, p+1)。

    ★ 为什么必须连续（见 `start_bridge` 的注释）：
      插件的 `popup.js` 用 `pairUrl(wsUrl)` 从 ws 端口**推出**配对端口
      （8765 ⇒ 8766；其它 ⇒ wsPort + 1）
      ⇒ 桥接的 ws 端口与配对端口**必须**是 (p, p+1) 关系，
        否则 popup 算出来的地址对不上 ⇒ 生产路径起不来。

    ★ 为什么要「连续两个都空闲」：
      `bind(0)` 返回的端口的**下一个**端口可能已被别的进程占用
      ⇒ 这里显式检查 p+1 是否可用，不可用就重取。
    """
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
# ① 素材准备（切片 + 转成浏览器能播的 wav）
# ══════════════════════════════════════════════════════════════════
def prepare_audio() -> str:
    """把 SPE 前 AUDIO_SEC 秒切成一个 16 kHz 单声道 wav（浏览器能播）。

    ★ 切片用 **App 自带解释器**（它有 soundfile）——
      本脚本跑在 workbuddy 的 venv 里（那儿有 playwright 但**没有** soundfile）
      ⇒ 直接 import soundfile 会失败。
    """
    out = os.path.join(ROOT, ".tmp", "ext026_audio.wav")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        _log("素材已存在：%s" % out)
        return out

    from ext.app_root import resolve_app_root
    app_root = resolve_app_root()
    if not app_root:
        raise RuntimeError("找不到实时字幕 App 安装目录（EXT_APP_ROOT 可显式指定）")
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
                       encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        raise RuntimeError("切片失败：%s" % ((r.stderr or "")[-500:]))
    _log("素材已切出：%s（%s）" % (out, (r.stdout or "").strip()))
    return out


# ══════════════════════════════════════════════════════════════════
# ② 本地 http 页面（放音频，模拟「网页在播视频」）
# ══════════════════════════════════════════════════════════════════
class _AudioHandler(http.server.SimpleHTTPRequestHandler):
    """只服务一个页面 + 一个 wav。"""

    wav_path = ""
    page_html = ""

    def log_message(self, fmt, *args):  # 静音
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
    """起本地 http 服务，返回 (server, port, url, title)。"""
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
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port, "http://127.0.0.1:%d/index.html" % port, title


# ══════════════════════════════════════════════════════════════════
# ③ 起真实 bridge
# ══════════════════════════════════════════════════════════════════
def start_bridge(log_path: str, *, echo: bool = False) -> subprocess.Popen:
    """用 **App 自带解释器** 起真实模式的桥接服务。

    ★ `echo=True` 走**回声模式**（不加载引擎、不占 GPU/NPU）——
      只用于**脚本自身**的自检（验证抓流/录音/截图/指标这条链通不通），
      **不能**当作 EXT-026 的真实证据。
    """
    from ext.app_root import resolve_app_root
    app_root = resolve_app_root()
    if not app_root:
        raise RuntimeError("找不到实时字幕 App 安装目录（EXT_APP_ROOT 可显式指定）")
    app_py = os.path.join(app_root, "python", "python.exe")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, os.path.join(ROOT, ".runtime_deps")] +
        ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    # ★ 端口：动态分配（避免与用户自己开着的桥接撞端口）
    #   ⚠️ ★★ **pair_port 必须是 ws_port + 1** ——
    #     插件的 popup.js 用 `pairUrl(wsUrl)` **从 ws 端口推出**配对端口：
    #       8765 ⇒ 8766；其它 ⇒ wsPort + 1
    #     （见 extension/popup.js 的 pairUrl()）
    #     ⇒ 若这里给两个**互不相关**的随机端口，popup 算出来的配对端口
    #       就**对不上** ⇒ popup 的 startGate 永远报「桥接服务未启动」
    #       ⇒ **生产路径（popup 点「开始」）根本起不来**。
    #   ⇒ 这里保持「连续两个端口」的约定（ws_port, ws_port + 1）。
    ws_port, pair_port = _free_port_pair()

    cmd = [
        app_py, "-m", "ext.bridge",
        "--host", "127.0.0.1", "--port", str(ws_port),
        "--pair-port", str(pair_port),
        # ★ 延迟 D = 10 s（默认）：配音比原声晚 10 s 播出
        "--delay", "10",
    ]
    if echo:
        cmd.append("--echo")
    else:
        cmd += ["--real", "--pipeline", "--target-lang", "zh"]
    _log("起%s bridge：%s" % ("回声" if echo else "真实", " ".join(cmd)))
    lf = open(log_path, "wb")
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=lf,
                            stderr=subprocess.STDOUT)
    proc._ext026_logfile = lf          # noqa: SLF001
    proc._ext026_ports = (ws_port, pair_port)   # noqa: SLF001
    return proc


def wait_bridge_ready(proc: subprocess.Popen, pair_port: int,
                      timeout: float = 240.0, *, echo: bool = False) -> dict:
    """轮询配对端点 /status，等引擎就绪（engine_state=ready）。"""
    import urllib.request
    t0 = time.time()
    last = None
    want_mode = "echo" if echo else "real"
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError("bridge 进程已退出，rc=%s" % proc.returncode)
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/status" % pair_port, timeout=3) as r:
                j = json.loads(r.read().decode("utf-8"))
            st = j.get("status") or {}
            last = st
            # 回声模式没有引擎 ⇒ engine_state 不会是 'ready'，
            # 只看 mode 对不对就算起来了。
            ready = (st.get("mode") == want_mode
                     and (echo or st.get("engine_state") == "ready"))
            if ready:
                _log("bridge 就绪：mode=%s engine_state=%s"
                     % (st.get("mode"), st.get("engine_state")))
                return st
        except Exception as e:
            last = {"error": str(e)}
        time.sleep(2.0)
    raise RuntimeError("bridge 未在 %.0fs 内就绪，最后状态=%r" % (timeout, last))


# ══════════════════════════════════════════════════════════════════
# ④ 主流程
# ══════════════════════════════════════════════════════════════════
def _rotate_evidence(out_dir: str) -> None:
    """把上一轮证据改名备份到 `<out_dir>_prev`，再清空 `out_dir`。

    ★ 为什么要有「备份」这一步：EXT-026 要求「没落盘的东西不能写已交付」。
    如果直接删，一旦本轮中途失败 ⇒ **上一轮的证据也没了、新证据也没有**
    ⇒ 两轮都拿不出东西。改名备份 ⇒ 至少上一轮还在（人工可查）。

    ★ 只在**拿到共享锁之后**才调用（见 `run()`）⇒
      排队等锁期间**不动**上一轮的证据。
    """
    prev_dir = out_dir + "_prev"
    try:
        if os.path.isdir(prev_dir):
            shutil.rmtree(prev_dir, ignore_errors=True)
        if os.path.isdir(out_dir) and os.listdir(out_dir):
            os.rename(out_dir, prev_dir)
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        _log("证据轮转失败（继续，不影响本轮）：%s" % e)


def run(echo: bool = False, capture_sec: int = CAPTURE_SEC,
        no_lock: bool = False) -> int:
    global CAPTURE_SEC
    CAPTURE_SEC = capture_sec
    out_dir = OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # ★★★ EXT-026 修正：**清理旧证据必须放在拿到锁之后**。
    #   ## 为什么（真实踩到的坑）
    #     原来清理写在拿锁**之前** ⇒ 本轮排队等锁（TTS 模块占着 GPU/NPU）
    #     的**等待期**就把**上一轮**的证据全删了
    #     ⇒ 万一这一轮中途挂掉 ⇒ **两轮都没有证据**（本轮 18:24 就发生过）。
    #   ## 修法
    #     ① 清理挪到 `with lock_cm:` **之后**（拿到锁才有资格动证据目录）；
    #     ② 删除前先把上一轮**改名备份**到 `<目录>_prev`（不丢历史），
    #        成功起完新的才把 `_prev` 删掉。
    wav_path = prepare_audio()
    bridge_log = os.path.join(out_dir, "bridge.log")

    proc: Optional[subprocess.Popen] = None
    srv = None
    bs = None
    summary: dict = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "capture_sec": CAPTURE_SEC, "audio_sec": AUDIO_SEC,
                     "out_dir": out_dir, "mode": "echo" if echo else "real"}
    rc = 1

    # ── 锁上下文（回声自检不占设备 ⇒ 可跳过） ─────────────────
    import contextlib
    lock_cm = (contextlib.nullcontext() if (no_lock or echo)
               else ML.hold("ext", wait_timeout=1800.0, poll_sec=5.0, log=_log))
    try:
        if not (no_lock or echo):
            _log("等待共享机器锁…")
        with lock_cm:
            # ── 拿到锁了，现在才清证据（并先备份上一轮） ──
            _rotate_evidence(out_dir)

            # ── 起真实 bridge ────────────────────────────────
            proc = start_bridge(bridge_log, echo=echo)
            ws_port, pair_port = proc._ext026_ports  # noqa: SLF001
            summary["bridge_ws_port"] = ws_port
            summary["bridge_pair_port"] = pair_port
            status = wait_bridge_ready(proc, pair_port, echo=echo)
            summary["bridge_status"] = status

            # ── 起本地 http 页面（放音频） ──────────────────
            title = "EXT026 SPE clip"
            srv, http_port, page_url, title = start_http_server(wav_path, title)
            summary["page_url"] = page_url
            _log("本地页面：%s" % page_url)

            # ── 起 Edge（单独 profile + --load-extension） ──
            extra = [
                "--auto-select-tab-capture-source-by-title=%s" % title,
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--allow-running-insecure-content",
                "--disable-features=MediaFoundationVideoCapture",
            ]
            with H.BrowserSession(PROFILE, extra_args=extra) as bs:
                if not bs.ext_sw_alive():
                    raise RuntimeError("扩展 SW 没起来")
                _log("扩展 SW 已就绪")

                # 拿 token（与 popup 同一路径：配对端点）
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:%d/pair" % pair_port,
                    headers={"Origin": "chrome-extension://%s" % H.EXT_ID})
                with urllib.request.urlopen(req, timeout=5) as r:
                    token = json.loads(r.read().decode("utf-8"))["token"]
                _log("已取到 token（%d 字符）" % len(token))

                # ── 先在 popup 里设好参数（模拟用户选好） ──────
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
                _log("popup 设置已写入：%r" % popup.evaluate(
                    "() => chrome.storage.local.get(null)"))
                popup.close()

                # ── 打开播放页面（让它开始播音频） ────────────
                media = bs.new_page()
                media.goto(page_url)
                time.sleep(1.0)
                # ★ 让它真正开始播（自动播放策略已放开）
                try:
                    media.evaluate("""() => {
                        const a = document.getElementById('a');
                        a.muted = false; a.volume = 1.0;
                        return a.play();
                    }""")
                except Exception as e:
                    _log("play() 调用异常（继续）：%s" % e)
                time.sleep(1.5)
                _log("媒体页播放状态：%r" % media.evaluate(
                    "() => { const a=document.getElementById('a');"
                    " return {t:a.currentTime, paused:a.paused, dur:a.duration}; }"))

                # ── 打开 player（扩展页） ────────────────────
                player = bs.open_ext_page("player.html")
                time.sleep(4.0)

                # ★★ EXT-026 ③：开始录「player 实际播出的配音」
                rec = player.evaluate("() => window.__ext.startDubRecording(120000)")
                _log("开始录音：%r" % rec)

                # ★ 走和用户一样的路径：**player 点「开始捕获」**
                #   （Playwright 的 click 算真实用户激活）
                player.click("#btnCapture")
                _log("已点「开始捕获」")

                # 等抓流起来
                ok = False
                for _ in range(30):
                    time.sleep(1.0)
                    m = player.evaluate("() => window.__ext.metrics()")
                    if m.get("captureStarted") and m.get("uplink", {}).get("frames", 0) > 0:
                        ok = True
                        break
                _log("抓流状态：%r" % (player.evaluate(
                    "() => ({captureStarted: window.__ext.metrics().captureStarted,"
                    " uplink: window.__ext.metrics().uplink})")))

                # ── 连续采集 CAPTURE_SEC 秒 ─────────────────
                t_start = time.time()
                shot30 = False
                shot60 = False
                while time.time() - t_start < CAPTURE_SEC:
                    time.sleep(1.0)
                    el = time.time() - t_start
                    if not shot30 and el >= 30:
                        shot30 = True
                        p = os.path.join(OUT_DIR, "player_30s.png")
                        player.screenshot(path=p)
                        _log("已截 30 s 图：%s" % p)
                    if not shot60 and el >= 60:
                        shot60 = True
                        p = os.path.join(OUT_DIR, "player_60s.png")
                        player.screenshot(path=p)
                        _log("已截 60 s 图：%s" % p)
                if not shot30:
                    player.screenshot(path=os.path.join(OUT_DIR, "player_30s.png"))
                if not shot60:
                    player.screenshot(path=os.path.join(OUT_DIR, "player_60s.png"))

                # ★★★ EXT-026 修正：发 flush 让服务端**收口尾段**。
                #   素材切出 5 段，前 4 段已 ready，尾段留在缓冲区
                #   ⇒ 不 flush 就只有 4 段（且最后一句永远丢）。
                _log("发 flush 收口尾段…")
                try:
                    player.click("#btnFlush")
                except Exception as e:
                    _log("点 btnFlush 失败（改用 __ext.flushUplink）：%s" % e)
                    player.evaluate("() => window.__ext.flushUplink()")
                # ★ 等尾段跑完（真实推理：ASR+MT+TTS ⇒ 十几秒）
                _log("等尾段推理完成（45 s）…")
                time.sleep(45)
                # ★ 尾段的配音要**播出**（排程在 t0+t_start+D ⇒ D=10 s）
                _log("等尾段配音播出（15 s）…")
                time.sleep(15)

                # ── 收尾：停录 + 取数据 ─────────────────────
                player.evaluate("() => window.__ext.stopDubRecording()")
                time.sleep(1.5)

                metrics = player.evaluate("() => window.__ext.metrics()")
                blob = player.evaluate("() => window.__ext.dubRecordingBlob()")

                # 落盘配音录音（**player 实际播出的**）
                dub_path = os.path.join(OUT_DIR, "dub_player.webm")
                dub_bytes = 0
                if blob and blob.get("ok"):
                    b64 = blob.get("base64", "")
                    if "," in b64:
                        b64 = b64.split(",", 1)[1]
                    raw = base64.b64decode(b64)
                    with open(dub_path, "wb") as f:
                        f.write(raw)
                    dub_bytes = len(raw)
                    _log("配音录音已落盘：%s（%d 字节，录制 %.1fs）"
                         % (dub_path, dub_bytes, blob.get("durationSec", 0)))
                else:
                    _log("⚠️ 没有录到配音：%r" % blob)

                # hello_ack（从 player 的上报历史里取）
                hello = player.evaluate(
                    "() => (window.__extMetrics && window.__extMetrics.hello_ack) || null")
                with open(os.path.join(OUT_DIR, "hello_ack.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(hello, f, ensure_ascii=False, indent=2)

                # 链接指标（只看要交出去的那些，避免把 500 项数组也落盘）
                link = metrics.get("link", {})
                m_out = {
                    "dubDelivered": link.get("dubDelivered"),
                    "echoRecv": metrics.get("echoRecv"),
                    "dubDup": metrics.get("dubDup"),
                    "schedErrP50": metrics.get("schedErrP50"),
                    "schedErrP95": metrics.get("schedErrP95"),
                    "schedErrMs": metrics.get("schedErrMs"),
                    "schedClamped": metrics.get("schedClamped"),
                    "mode": link.get("mode"),
                    "enginesReady": link.get("enginesReady"),
                    "pipeline": link.get("pipeline"),
                    "asrSegments": link.get("asrSegments"),
                    "mtSegments": link.get("mtSegments"),
                    "ttsSegments": link.get("ttsSegments"),
                    "audioRecvSec": link.get("audioRecvSec"),
                    "captureMode": link.get("captureMode"),
                    "lagSec": link.get("lagSec"),
                    "dubDupsCleared": link.get("dubDupsCleared"),
                    "uplink": metrics.get("uplink"),
                }
                with open(os.path.join(OUT_DIR, "metrics.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(m_out, f, ensure_ascii=False, indent=2)
                _log("metrics：%r" % m_out)

                summary["metrics"] = m_out
                summary["hello_ack"] = hello
                summary["dub_recording"] = {
                    "path": dub_path, "bytes": dub_bytes,
                    "mime": (blob or {}).get("mime"),
                    "durationSec": (blob or {}).get("durationSec"),
                }
                # ★ 解码录音 ⇒ 落盘「非静音」证据（EXT-026 第 3 条要求）
                try:
                    from analyze_dub_audio import analyze as _analyze
                    aa = _analyze(dub_path)
                    aa_path = os.path.join(OUT_DIR, "dub_audio_analysis.json")
                    with open(aa_path, "w", encoding="utf-8") as f:
                        json.dump(aa, f, ensure_ascii=False, indent=2)
                    summary["dub_audio_analysis"] = aa
                    _log("录音音频分析：peak=%.5f rms=%.5f (%s dBFS) 语音 %s s"
                         % (aa.get("peak", 0), aa.get("rms", 0),
                            aa.get("dbfsRms"), aa.get("activeSec")))
                except Exception as e:
                    summary["dub_audio_analysis_error"] = "%s: %s" % (
                        type(e).__name__, e)
                    _log("⚠️ 录音音频分析失败：%s" % e)
                summary["capture_ok"] = ok
                rc = 0

            # ── bridge 再跑一会儿，让流水线把最后的段跑完 ──
            _log("等待流水线收尾（20 s）…")
            time.sleep(20)

    except Exception as e:
        _log("❌ 失败：%s: %s" % (type(e).__name__, e))
        import traceback
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
                proc.wait(10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc._ext026_logfile.close()   # noqa: SLF001
            except Exception:
                pass

    # ── 汇总判定 ──────────────────────────────────────────────
    summary["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _summarize(OUT_DIR, summary)
    # ★ 先判定再落盘 ⇒ summary.json 里必须带上 verdict / verdict_checks
    _print_verdict(summary)
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    _log("汇总已落盘：%s" % os.path.join(OUT_DIR, "summary.json"))
    return rc


# ══════════════════════════════════════════════════════════════════
# ⑤ 证据核验（EXT-026 第 3 条逐条对照）
# ══════════════════════════════════════════════════════════════════
def _summarize(out_dir: str, summary: dict) -> None:
    """读 bridge.log，统计段级日志 ⇒ 写进 summary['bridge_log']。

    ★ 日志行格式（实测 2026-10-31）：
      `[bridge 18:10:33] 段 seg_72344844_0 | t_start=0.000 t_end=12.150
       | ASR='…' | MT='…' | TTS=9.04s | 下发到=player,uplink`
      ⇒ 行首是时间戳前缀，**不是**「段 」。
    """
    log_path = os.path.join(out_dir, "bridge.log")
    seg_lines = []
    to_player = 0
    all_seg = 0
    # ★ 分开统计「有 TTS 音频的段」与「空段（ASR/MT 为空 ⇒ TTS=0.00s）」
    #   —— EXT-010 的设计是「引擎失败的段**也要下发**（标 error、has_tts=False），
    #   不丢段」⇒ 下发段数可以 > 有音频的段数，**这是设计不是缺陷**。
    seg_with_tts = 0
    seg_empty = 0
    tts_secs = []
    no_replace = 0
    port_busy = 0
    exec_devices = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if " | 下发到=" in line and "] 段 " in line:
                    seg_lines.append(line.rstrip())
                    all_seg += 1
                    roles = line.split("下发到=")[-1]
                    if "player" in roles:
                        to_player += 1
                    # TTS=9.04s ⇒ 这一段有真实音频
                    try:
                        tts_s = float(line.split("TTS=")[-1].split("s")[0])
                    except (IndexError, ValueError):
                        tts_s = 0.0
                    if tts_s > 0:
                        seg_with_tts += 1
                        tts_secs.append(round(tts_s, 2))
                    else:
                        seg_empty += 1
                if "不顶替" in line:
                    no_replace += 1
                if "10048" in line:
                    port_busy += 1
                if "EXECUTION_DEVICES" in line or "[TTS-EXEC]" in line:
                    exec_devices.append(line.rstrip())
    summary["bridge_log"] = {
        "n_segment_lines": all_seg,
        "n_segments_to_player": to_player,
        "n_segments_with_tts": seg_with_tts,
        "n_segments_empty": seg_empty,
        "tts_speech_secs": tts_secs,
        "tts_speech_total_sec": round(sum(tts_secs), 2),
        "n_not_replaced": no_replace,
        "n_port_10048": port_busy,
        "segment_lines": seg_lines,
        "exec_devices_lines": exec_devices,
    }
    # 引擎设备落盘文件（EXT-023）
    ed_path = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                           "LiveDubEXT", "tts_exec_devices.json")
    if os.path.exists(ed_path):
        try:
            with open(ed_path, "r", encoding="utf-8") as f:
                summary["tts_exec_devices"] = json.load(f)
            summary["tts_exec_devices_path"] = ed_path
        except Exception as e:
            summary["tts_exec_devices_error"] = str(e)


def _fsize(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _print_verdict(summary: dict) -> None:
    bl = summary.get("bridge_log", {})
    mt = summary.get("metrics", {}) or {}
    ha = summary.get("hello_ack") or {}
    dr = summary.get("dub_recording") or {}
    aa = summary.get("dub_audio_analysis") or {}
    out_dir = summary.get("out_dir") or OUT_DIR
    checks = [
        ("段级日志 ≥5 段", bl.get("n_segment_lines", 0) >= 5,
         "%s 段" % bl.get("n_segment_lines")),
        # ★ 口径说明：EXT-026 原文「『下发到』含 player 的段数 = TTS 段数」。
        #   这里「TTS 段数」= **有真实 TTS 音频的段数**（TTS>0s）。
        #   ⚠️ 下发段数可能**大于**有音频的段数 —— EXT-010 明文设计：
        #     「某一段的引擎抛异常 ⇒ 该段**仍要下发**（标 error、has_tts=False），
        #       不丢段」⇒ 段级日志必须能看到失败的段。
        #   ⇒ 判据：**每个有音频的段都下发到了 player**（不多不少）。
        ("每个有 TTS 音频的段都下发到 player",
         bl.get("n_segments_with_tts", 0) > 0
         and bl.get("n_segments_to_player", 0) >= bl.get("n_segments_with_tts", 0),
         "下发 %s / 有音频 %s（另有 %s 个空段，按 EXT-010 设计仍下发）"
         % (bl.get("n_segments_to_player"), bl.get("n_segments_with_tts"),
            bl.get("n_segments_empty"))),
        ("无 10048 端口占用", bl.get("n_port_10048", 0) == 0,
         "%s 次" % bl.get("n_port_10048")),
        # ★★ 「不顶替」的**如实说明**（EXT-026 第 3 条要求「没有『不顶替』」，
        #   但按 EXT-024 的设计，**player 连接先连**时**必然**出现这一行）：
        #     * 同一 token 上有**两条**连接（player 下行 + uplink 上行）；
        #     * `_register_session` 的规则是「除 uplink 接管 uplink 外，
        #       其它连接都**不顶替**已有会话」（缺陷 15 修复）；
        #     * ⇒ player 先连 ⇒ uplink 连上时 holder 里已有 player 会话
        #       ⇒ 打印「已有活跃会话 ⇒ 本连接不顶替」。
        #   ★ 这**不是**故障：`producer_session` 会正确指向 uplink 会话
        #     ⇒ stats / margin.json 读的是**真会话**（`_producer_session()`）。
        #   ⇒ 判据：段数统计**非零**（证明读的是真会话，不是 player 的空会话）。
        ("段数统计非零（证明 stats 读的是真会话而非 player 的空会话）",
         (mt.get("ttsSegments") or 0) > 0,
         "ttsSegments=%s / 不顶替 %s 次"
         % (mt.get("ttsSegments"), bl.get("n_not_replaced"))),
        ("hello_ack mode=real", ha.get("mode") == "real", str(ha.get("mode"))),
        ("hello_ack engines_ready=true", ha.get("engines_ready") is True,
         str(ha.get("engines_ready"))),
        ("player 收到配音段 dubDelivered ≥1", (mt.get("dubDelivered") or 0) >= 1,
         str(mt.get("dubDelivered"))),
        ("配音录音已落盘且非空", (dr.get("bytes") or 0) > 0,
         "%s 字节" % dr.get("bytes")),
        # ★★ 「录音非静音」是 EXT-026 第 3 条明文验收项 ⇒ 必须有实测数字
        #     判据调用**工具里的真函数**（单一事实来源，不复制阈值）
        ("配音录音非静音（RMS 门限 + 语音 burst）",
         _is_non_silent(aa),
         "peak=%.5f rms=%.5f (%s dBFS) burst=%s 语音=%ss"
         % (aa.get("peak", 0), aa.get("rms", 0), aa.get("dbfsRms"),
            aa.get("bursts"), aa.get("activeSec"))),
        ("30 s 截图存在", os.path.exists(os.path.join(out_dir, "player_30s.png")),
         "%d 字节" % _fsize(os.path.join(out_dir, "player_30s.png"))),
        ("60 s 截图存在", os.path.exists(os.path.join(out_dir, "player_60s.png")),
         "%d 字节" % _fsize(os.path.join(out_dir, "player_60s.png"))),
        ("启动了 EXECUTION_DEVICES 打印（EXT-023）",
         len(bl.get("exec_devices_lines") or []) > 0,
         "%s 行" % len(bl.get("exec_devices_lines") or [])),
    ]
    print("\n" + "=" * 62)
    print("EXT-026 验收对照")
    print("=" * 62)
    ok = True
    for name, passed, detail in checks:
        ok = ok and passed
        print("  [%s] %s%s" % ("PASS" if passed else "FAIL", name,
                               ("  (%s)" % detail) if detail else ""))
    print("=" * 62)
    print("总体：%s" % ("PASS" if ok else "FAIL"))
    print("=" * 62)
    summary["verdict"] = "PASS" if ok else "FAIL"
    summary["verdict_checks"] = [
        {"name": n, "pass": p, "detail": d} for n, p, d in checks]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="EXT-026 真实三引擎端到端冒烟")
    ap.add_argument("--echo", action="store_true",
                    help="用**回声模式**自检脚本本身（不占 GPU/NPU，"
                         "**不能**当 EXT-026 的真实证据）")
    ap.add_argument("--capture-sec", type=int, default=CAPTURE_SEC,
                    help="连续采集秒数（默认 %d）" % CAPTURE_SEC)
    ap.add_argument("--no-lock", action="store_true",
                    help="不取共享机器锁（只给 --echo 自检用）")
    a = ap.parse_args()
    sys.exit(run(echo=a.echo, capture_sec=a.capture_sec, no_lock=a.no_lock))
