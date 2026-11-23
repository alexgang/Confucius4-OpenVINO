"""Restore tts_engine.py / tts_worker.py from the pre-APP-123 backups."""
import ast
import glob
import os
import shutil

TEMP = os.environ.get("TEMP", r"C:\Users\Trekker-PTL\AppData\Local\Temp")
DEV = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"

for name in ("tts_engine.py", "tts_worker.py"):
    pat = os.path.join(TEMP, name + ".bak_app123_*")
    baks = sorted(glob.glob(pat), key=os.path.getmtime)
    if not baks:
        raise SystemExit("no backup for " + name)
    src = baks[-1]
    dst = os.path.join(DEV, name)
    shutil.copy2(src, dst)
    raw = open(dst, "rb").read()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    print("restored %s <- %s  bytes=%d crlf=%d lone_lf=%d"
          % (name, os.path.basename(src), len(raw), crlf, lf))
    ast.parse(raw.decode("utf-8"))
    print("   AST OK")
