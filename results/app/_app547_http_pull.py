import json, os, time
import paramiko

HOST = "192.168.2.194"
USER = "test"
PW = os.environ.get("WB_SSH_PASS")
TOKEN = open(r"C:\Users\Trekker-PTL\AppData\Local\Temp\_app546_token.txt").read().strip().split("=", 1)[1]
ZIPNAME = "Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip"
REMOTE = r"C:\Users\63446\Desktop\\" + ZIPNAME
URL = "http://192.168.2.189:8899/%s/%s" % (TOKEN, ZIPNAME)
OUT = r"C:\Users\Trekker-PTL\confucius4-openvino\results\app\app547_target_pull_result.json"


def run(t, cmd, timeout=3600):
    ch = t.open_session()
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    out = b""
    err = b""
    try:
        while True:
            if ch.recv_ready():
                out += ch.recv(65536)
            if ch.recv_stderr_ready():
                err += ch.recv_stderr(65536)
            if ch.exit_status_ready() and not ch.recv_ready() and not ch.recv_stderr_ready():
                break
            time.sleep(0.2)
    except Exception as e:
        err += str(e).encode()
    return out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


ev = {"host": HOST, "url": URL, "remote": REMOTE, "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
t = paramiko.Transport((HOST, 22)); t.banner_timeout = 30; t.connect(); t.auth_password(USER, PW)

# ── 0. clean up my own test artifacts on the target (free disk) ──
so, se = run(t, 'del /q "C:\\Users\\63446\\Desktop\\_speedtest.bin" 2>nul & del /q "C:\\Users\\63446\\Desktop\\_speedtest.ps1" 2>nul & echo CLEANED')
ev["cleanup"] = (so + se).strip()

# ── 1. free space before ──
so, _ = run(t, 'powershell -NoProfile -Command "(Get-PSDrive C).Free/1GB" 2>&1')
try:
    ev["free_gb_before"] = round(float(so.strip().splitlines()[-1]), 2)
except Exception:
    ev["free_gb_before"] = None

# ── 2. pull the zip (overwrite from scratch; resume-able with -C -) ──
cmd = ('curl.exe -L --retry 3 --retry-delay 2 -o "%s" -w "code=%%{http_code} size=%%{size_download} speed=%%{speed_download} time=%%{time_total}" "%s"'
       % (REMOTE, URL))
t0 = time.time()
so, se = run(t, cmd, timeout=3600)
ev["curl_seconds"] = round(time.time() - t0, 1)
ev["curl_out"] = (so + se).strip()[-600:]
print("CURL:", ev["curl_out"], "secs", ev["curl_seconds"], flush=True)

# ── 3. remote size + sha256 (certutil) ──
so, se = run(t, 'for %I in ("%s") do @echo SIZE=%%~zI' % REMOTE)
ev["remote_size"] = (so + se).strip()
print("SIZE:", ev["remote_size"], flush=True)

so, se = run(t, 'certutil -hashfile "%s" SHA256 2>&1' % REMOTE, timeout=3600)
import re
txt = so + se
m = re.search(r'\b([0-9a-fA-F]{64})\b', txt)
ev["sha256_remote"] = m.group(1).lower() if m else None
ev["certutil_raw_tail"] = txt.strip()[-400:]
print("REMOTE SHA256:", ev["sha256_remote"], flush=True)

so, _ = run(t, 'powershell -NoProfile -Command "(Get-PSDrive C).Free/1GB" 2>&1')
try:
    ev["free_gb_after"] = round(float(so.strip().splitlines()[-1]), 2)
except Exception:
    ev["free_gb_after"] = None

ev["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
t.close()

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print("WROTE", OUT)
