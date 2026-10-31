"""pw_accept1.py — 冒烟①：扩展是否装上、popup 页是否正常渲染

跑法（在仓库根）：
    python tests/smoke/pw_accept1.py

⚠️ 本机**没有 Chrome**（只有 Edge 126）⇒ `browser_harness.find_browser()`
   找不到 Chrome 时会直接用 Edge。**这不是**浏览器端人工验收
   （人工验收由用户亲自做，见 EXT-022 已定②）。
"""
from __future__ import annotations

import time

from _smoke_common import profile_dir
import browser_harness as H

with H.BrowserSession(profile_dir("accept1")) as bs:
    print("SW:", bs.sw_urls())
    print("EXT SW ALIVE:", bs.ext_sw_alive())
    # popup
    errs = []
    pg = bs.open_ext_page("popup.html")
    pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    time.sleep(2.5)
    print("POPUP title:", pg.title())
    print("STATUS:", repr(pg.inner_text("#status")))
    print("lang:", pg.eval_on_selector("#lang", "e=>e.value"))
    print("voice:", pg.eval_on_selector("#voice", "e=>e.value"))
    print("duck:", pg.eval_on_selector("#duck", "e=>e.value"))
    print("delay:", pg.eval_on_selector("#delay", "e=>e.value"))
    print("subs:", pg.eval_on_selector("#subs", "e=>e.checked"))
    print("storage:", pg.evaluate("() => chrome.storage.local.get(null)"))
    print("ERRS:", errs[:8])
