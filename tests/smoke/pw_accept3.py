"""pw_accept3.py — 冒烟③：player 页能否加载、能否读到设置、storage.onChanged 是否接上

跑法（在仓库根）：
    python tests/smoke/pw_accept3.py
"""
from __future__ import annotations

import time

from _smoke_common import profile_dir
import browser_harness as H

with H.BrowserSession(profile_dir("accept3")) as bs:
    errs = []
    pg = bs.open_ext_page("player.html")
    pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
    pg.on("console",
          lambda m: errs.append(f"{m.type}: {m.text}")
          if m.type in ("error", "warning") else None)
    time.sleep(4)
    print("PLAYER title:", pg.title())
    print("mQueue:", pg.inner_text("#mQueue"), "| mCodec:", pg.inner_text("#mCodec"),
          "| mDelay:", pg.inner_text("#mDelay"), "| mMem:", pg.inner_text("#mMem"))
    print("ERRS:", errs[:10])
    # 检查 player 读到的设置
    print("player storage:", pg.evaluate("() => chrome.storage.local.get(null)"))
    # 检查 storage.onChanged 是否真的接上（改 duckDb 看 player metrics）
    pg.evaluate("() => chrome.storage.local.set({duckDb: -30})")
    time.sleep(2)
    print("after duckDb change, extLog tail:",
          pg.evaluate("() => chrome.storage.local.get({extLog: []})"
                      ".then(s => (s.extLog||[]).slice(-4))"))
