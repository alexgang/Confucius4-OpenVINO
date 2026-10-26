
import sys, json, time, os
_cancelled = set()
def emit(d):
    sys.stdout.write(json.dumps(d) + "\n")
    sys.stdout.flush()
time.sleep(float(os.environ.get("STUB_READY_DELAY", "4")))
emit({"kind": "ready", "device": "STUB", "voice": "A"})
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    c = msg.get("cmd")
    if c == "quit":
        sys.exit(0)
    if c == "cancel":
        jid = msg.get("id")
        _cancelled.add(jid)
        emit({"kind": "dropped", "id": jid, "count": 1})
    elif c == "synth":
        jid = msg.get("id")
        if jid in _cancelled:
            continue          # ← 真实 worker 语义：跳过、**不回 played**
        emit({"kind": "played", "id": jid, "dur_s": 1.0, "latency_s": 0.1,
              "telemetry": {"peak": 0.5, "rms_dbfs": -18.0,
                            "read_delta": 24000}})
while True:
    time.sleep(0.2)
