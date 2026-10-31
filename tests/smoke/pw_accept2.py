"""pw_accept2.py — 冒烟②：popup 的设置写入与回填

跑法（在仓库根）：
    python tests/smoke/pw_accept2.py
"""
from __future__ import annotations

import time

from _smoke_common import profile_dir
import browser_harness as H

with H.BrowserSession(profile_dir("accept2")) as bs:
    # 第一次打开 popup：改设置，不点「开始」
    pg = bs.open_ext_page("popup.html")
    time.sleep(2)
    pg.select_option("#lang", "ja")
    pg.select_option("#voice", "clone")
    pg.fill("#duck", "-40")
    pg.fill("#delay", "17")
    pg.uncheck("#subs")
    time.sleep(1.0)
    st1 = pg.evaluate("() => chrome.storage.local.get(null)")
    print("① 改完立即读 storage:",
          {k: st1.get(k) for k in ("targetLang", "voice", "duckDb",
                                   "delaySec", "subsOn")})
    pg.close()
    time.sleep(0.8)
    # 重新打开 popup：看回填
    pg2 = bs.open_ext_page("popup.html")
    time.sleep(2)
    st2 = pg2.evaluate("() => chrome.storage.local.get(null)")
    print("② 重开 popup 后 storage:",
          {k: st2.get(k) for k in ("targetLang", "voice", "duckDb",
                                   "delaySec", "subsOn")})
    print("② 重开 popup 后界面值:", {
        "lang": pg2.eval_on_selector("#lang", "e=>e.value"),
        "voice": pg2.eval_on_selector("#voice", "e=>e.value"),
        "duck": pg2.eval_on_selector("#duck", "e=>e.value"),
        "delay": pg2.eval_on_selector("#delay", "e=>e.value"),
        "subs": pg2.eval_on_selector("#subs", "e=>e.checked"),
    })
