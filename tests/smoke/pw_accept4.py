"""pw_accept4.py — 冒烟④：插件 ↔ 桥接服务 端到端（**回声模式**，不占 GPU/NPU）

跑法（在仓库根）：
    python tests/smoke/pw_accept4.py

★ 用**回声模式**（`--echo`）：不加载任何引擎 ⇒ **不占 GPU/NPU**、
  也不需要机器锁。目的是验证「插件的 hello 真的到了服务端、
  服务端真的记下了 language/voice/capture_mode」。
★ 端口**动态分配**（避免与用户自己开着的桥接服务撞端口）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

from _smoke_common import ROOT, profile_dir
import browser_harness as H


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


BRIDGE_PORT = _free_port()
PAIR_PORT = _free_port()

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join(
    [ROOT, os.path.join(ROOT, ".runtime_deps")] +
    ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
env["PYTHONIOENCODING"] = "utf-8"

# 起回声模式桥接（不加载引擎，不占 GPU/NPU）
proc = subprocess.Popen(
    [sys.executable, "-m", "ext.bridge", "--echo",
     "--host", "127.0.0.1", "--port", str(BRIDGE_PORT),
     "--pair-port", str(PAIR_PORT), "--no-warmup"],
    cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

try:
    time.sleep(4)
    with H.BrowserSession(profile_dir("accept4")) as bs:
        # 先在 storage 里写好设置（模拟用户在 popup 选好了）
        pg = bs.open_ext_page("popup.html")
        time.sleep(1.5)
        pg.evaluate("""() => chrome.storage.local.set({
            targetLang: 'ja', voice: 'clone', duckDb: -22, delaySec: 12, subsOn: false
        })""")
        time.sleep(0.8)
        print("storage now:", pg.evaluate("() => chrome.storage.local.get(null)"))
        pg.close()

        # 打开 player（它会读设置并上报 hello）
        p2 = bs.open_ext_page("player.html")
        time.sleep(5)
        try:
            st = json.load(urllib.request.urlopen(
                "http://127.0.0.1:%d/status" % PAIR_PORT, timeout=3))
            print("BRIDGE STATUS:", json.dumps(st, ensure_ascii=False)[:900])
        except Exception as e:
            print("status err:", str(e)[:200])
finally:
    proc.terminate()
    try:
        proc.wait(8)
    except Exception:
        proc.kill()
    try:
        out = proc.stdout.read(20000).decode("utf-8", "replace")
        print("---- bridge log ----")
        print(out[-3000:])
    except Exception:
        pass
