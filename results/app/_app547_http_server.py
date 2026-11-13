import hashlib, os, re, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND = "192.168.2.189"
PORT = int(os.environ.get("APP546_PORT", "8899"))
TOKEN = os.environ.get("APP546_TOKEN", "")
FILES = {
    "Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip":
        r"C:\Users\Trekker-PTL\shared\specialmvp\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip",
}
LOG = r"C:\Users\Trekker-PTL\AppData\Local\Temp\_app546_http.log"
PIDFILE = r"C:\Users\Trekker-PTL\AppData\Local\Temp\_app546_http.pid"


def logline(s):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%H:%M:%S"), s))


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _resolve(self):
        p = self.path.split("?")[0].lstrip("/")
        if not p.startswith(TOKEN + "/"):
            return None
        name = p[len(TOKEN) + 1:]
        if name not in FILES:
            return None
        return name, FILES[name]

    def do_HEAD(self):
        r = self._resolve()
        if not r:
            self.send_error(404); return
        name, path = r
        st = os.stat(path)
        self.send_response(200)
        self.send_header("Content-Length", str(st.st_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()

    def do_GET(self):
        r = self._resolve()
        if not r:
            self.send_error(404); return
        name, path = r
        total = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, total - 1
        partial = False
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if m:
                partial = True
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                if m.group(1) == "":
                    # suffix range: last N bytes
                    start = max(0, total - int(m.group(2)))
                    end = total - 1
        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, total))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        t0 = time.time(); sent = 0
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    b = f.read(min(4 << 20, remaining))
                    if not b:
                        break
                    self.wfile.write(b)
                    sent += len(b); remaining -= len(b)
        except (BrokenPipeError, ConnectionResetError) as e:
            logline("client aborted after %d bytes: %s" % (sent, e))
            return
        logline("GET %s start=%d len=%d %.2f MB/s" % (name, start, length, sent / max(time.time() - t0, 1e-6) / 1e6))


if __name__ == "__main__":
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    srv = ThreadingHTTPServer((BIND, PORT), H)
    srv.daemon_threads = True
    logline("serving on %s:%d token=%s" % (BIND, PORT, TOKEN))
    print("serving on %s:%d" % (BIND, PORT), flush=True)
    srv.serve_forever()
