"""src_server.py — EXT 测试用「源页面」服务器

提供三个资源：
  /        —— 1080p30 canvas 动画 + 真实 WAV 音轨（autoplay loop），每 2 s 白闪
               ⇒ 用于 **P0① 音频上行连续性**（有持续的真实语音）
  /sync    —— 唇音同步**测试片**：白闪与「嘀」声在**同一源时刻**同时出现
               ⇒ 用于 **P0② 唇音同步误差**（白闪画-白 vs 嘀声听-声，严格同源）
  /spe.wav —— 共享目录里的 SPE 前 5 分钟（16 kHz 单声道 PCM16）

★ /sync 的关键点：白闪与 beep 由**同一个计数器**触发，
  所以「画面事件时刻」与「声音事件时刻」在源时间轴上完全重合；
  两条链路（画面走编码-解码-画布，声音走 DelayNode(D)）引入的差异
  就是我们要测的**唇音同步误差**。

只监听 127.0.0.1。纯静态资源，不跑推理、不占 GPU·NPU。

用法：
    python tools/src_server.py --port 8891
"""
from __future__ import annotations

import argparse
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SRC_WAV = r"C:\Users\Trekker-PTL\shared\SPE_0000_0500.wav"
SRC_TITLE = "EXTSRCPAGE"

# ── / 页面：持续语音 + 白闪（给 P0① 用） ─────────────────────────
SRC_HTML = """<!doctype html><meta charset=utf-8><title>%s</title>
<body style="margin:0;background:#000">
<audio id="a" src="/spe.wav" autoplay loop></audio>
<canvas id="c" width="1920" height="1080"></canvas>
<script>
const g = document.getElementById('c').getContext('2d');
let n = 0;
setInterval(() => {
  n++;
  g.fillStyle = 'hsl(' + (n %% 360) + ',70%%,50%%)';
  g.fillRect(0, 0, 1920, 1080);
  g.fillStyle = '#fff';
  g.font = '80px sans-serif';
  g.fillText('FRAME ' + n, 100, 200);
  // 每 2 秒一次「白闪」
  if (n %% 60 === 0) { g.fillStyle = '#fff'; g.fillRect(0, 0, 1920, 1080); }
}, 1000/30);
</script></body>""" % SRC_TITLE

# ── /sync 页面：唇音同步测试片（白闪 + 嘀声 同源） ───────────────
SYNC_HTML = """<!doctype html><meta charset=utf-8><title>%s</title>
<body style="margin:0;background:#000">
<canvas id="c" width="1920" height="1080"></canvas>
<script>
const g = document.getElementById('c').getContext('2d');
const actx = new (window.AudioContext || window.webkitAudioContext)();
actx.resume();
// beep 增益总线（直接进 destination ⇒ 能被标签页捕获）
const beepBus = actx.createGain();
beepBus.gain.value = 1.0;
beepBus.connect(actx.destination);

function beep() {
  const t = actx.currentTime;
  const o = actx.createOscillator();
  o.type = 'sine';
  o.frequency.value = 3000;
  const g2 = actx.createGain();
  // 4 ms 上升沿 ⇒ 明确的 onset；60 ms 后归零
  g2.gain.setValueAtTime(0.0001, t);
  g2.gain.linearRampToValueAtTime(0.9, t + 0.004);
  g2.gain.setValueAtTime(0.9, t + 0.040);
  g2.gain.linearRampToValueAtTime(0.0001, t + 0.060);
  o.connect(g2); g2.connect(beepBus);
  o.start(t); o.stop(t + 0.08);
}

let n = 0;
setInterval(() => {
  n++;
  const flash = (n %% 60 === 0);
  g.fillStyle = 'hsl(' + (n %% 360) + ',70%%,45%%)';
  g.fillRect(0, 0, 1920, 1080);
  g.fillStyle = '#fff';
  g.font = '80px sans-serif';
  g.fillText('SYNC ' + n, 100, 200);
  // ★ 白闪与 beep 在**同一个源时刻**发生 ⇒ 天然同源
  if (flash) {
    g.fillStyle = '#fff'; g.fillRect(0, 0, 1920, 1080);
    beep();
  }
}, 1000/30);
</script></body>""" % SRC_TITLE


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/spe.wav":
            if not os.path.isfile(SRC_WAV):
                self.send_response(404)
                self.end_headers()
                return
            with open(SRC_WAV, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        body = (SYNC_HTML if self.path == "/sync" else SRC_HTML).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve(port: int = 8891):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8891)
    args = ap.parse_args()
    srv = serve(args.port)
    print(f"serving http://127.0.0.1:{args.port}/ (title={SRC_TITLE})", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
