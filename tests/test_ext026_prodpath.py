"""test_ext026_prodpath.py — ★ EXT-026 **生产路径**新行为的自测（Python 载体）

## 这个文件要验什么

EXT-026 指令第 2 条要求的真实用户路径是：

    用户点插件图标 → popup「开始」→ SW `chrome.tabCapture.getMediaStreamId()`
      → offscreen 文档抓流 → offscreen 自己的上行 WS
      → 服务端把 tts 下发给 offscreen 那条 WS
      → offscreen `forwardToPlayer()` → SW runtime 广播 → player 页
      → `handleBridgeMessage()` → 排程配音

⇒ 这条链上有 **EXT-024 A 新加的转发环节**（offscreen → SW → player），
   而**那条转发链从来没有在真实三引擎上跑过**。

★ 本轮（2026-10-31 20:5x）**真的跑了**这条路径（`tests/smoke/ext026_prodpath.py`）
⇒ 抓到 **3 个只有这条路径才会暴露的真缺陷**：

  P1 **生产路径下状态条段数恒为 0**
     `pollStats()` 只认 `upState.ws`（player 自己抓流时的那条上行 WS）；
     生产路径下上行在 **offscreen** 里 ⇒ player 的 `upState.ws` 是 null
     ⇒ stats 永远发不出去 ⇒ `asrSegments/mtSegments/ttsSegments` 恒为 0。
     ⇒ 修法：回落用 player 自己那条 WS。

  P2 **生产路径没有 flush ⇒ 尾段永远丢**
     `sw.js` / `offscreen.js` 都没有 flush 命令
     ⇒ 生产路径永远收不了口 ⇒ 用户点「停止」时最后一句永远没配音。

  P3 **popup 的桥接地址只写 storage 不够**
     `popup.js` 的 `loadCfg()` 在页面加载时把 storage 读进 **DOM 输入框**
     ⇒ 加载**之后**再写 storage，输入框仍是旧值（8765）
     ⇒ 点「开始」时 `saveCfg()` 把旧值写回 ⇒ 连不上桥接。

## ★ 可证伪（铁律：自测要能区分「真通过」与「假通过」）

本文件跑 `tests/ext026_prodpath_harness.js`（node 沙箱跑**真源码**的**真函数**），
其中有 **4 组反证**：把实现改坏 ⇒ 对应断言**必须变红**。

不跑推理 / 不占 GPU·NPU / **不创建共享锁**（纯逻辑 + node 沙箱）。

运行：
    python tests/test_ext026_prodpath.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(ROOT, "tests", "ext026_prodpath_harness.js")

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  — " + detail) if (detail and not cond) else ""))


def _node_exe() -> str:
    """找 node（WorkBuddy 自带的那个优先）。"""
    cands = [
        r"C:\Users\Trekker-PTL\.workbuddy\binaries\node\versions\22.22.2-6\node.exe",
        "node",
    ]
    for c in cands:
        if os.path.isabs(c) and os.path.isfile(c):
            return c
        try:
            subprocess.run([c, "--version"], capture_output=True, timeout=20)
            return c
        except Exception:
            continue
    return "node"


def test_harness_passes() -> None:
    print("\n[A] ★ 生产路径 harness（node 沙箱跑真源码）")
    node = _node_exe()
    try:
        res = subprocess.run([node, HARNESS], capture_output=True,
                             text=True, timeout=180, cwd=ROOT)
    except Exception as e:
        check("★ harness 能跑起来", False, "%s: %s" % (type(e).__name__, e))
        return
    out = (res.stdout or "") + (res.stderr or "")
    print("\n".join("    " + ln for ln in out.splitlines()[-40:]))

    check("★ harness 退出码为 0", res.returncode == 0,
          "rc=%s\n%s" % (res.returncode, out[-800:]))
    m = re.search(r"harness 结果：(\d+) PASS / (\d+) FAIL / 共 (\d+)", out)
    check("★ harness 解析出结果行", m is not None, out[-400:])
    if m:
        npass, nfail, ntot = int(m.group(1)), int(m.group(2)), int(m.group(3))
        check("★ harness 至少 15 项断言", ntot >= 15, "共 %d 项" % ntot)
        check("★ harness 0 FAIL", nfail == 0, "FAIL %d 项" % nfail)
        check("★ harness 的 PASS 数与总数一致", npass + nfail == ntot,
              "%d + %d != %d" % (npass, nfail, ntot))


def test_harness_has_counter_examples() -> None:
    print("\n[B] ★ 反证：断言必须能变红（防「恒真」）")
    node = _node_exe()
    try:
        res = subprocess.run([node, HARNESS], capture_output=True,
                             text=True, timeout=180, cwd=ROOT)
    except Exception as e:
        check("★ harness 能跑起来", False, "%s: %s" % (type(e).__name__, e))
        return
    out = (res.stdout or "") + (res.stderr or "")
    check("★ harness 里有多组反证（改坏实现 ⇒ 断言变红）",
          "反证" in out, out[-300:])
    # 反证本身是「PASS」⇒ 说明「如期变红」被观察到了
    n_ce = len(re.findall(r"\[PASS\] ★ 反证 [A-Z]", out))
    check("★ 至少 4 组反证全部生效", n_ce >= 4, "实测 %d 组" % n_ce)


def test_source_contracts() -> None:
    print("\n[C] ★ 产品源码契约（生产路径的接线）")
    def read(p):
        with open(os.path.join(ROOT, p), "r", encoding="utf-8") as f:
            return f.read()

    off = read("extension/offscreen.js")
    sw = read("extension/sw.js")
    popup = read("extension/popup.js")
    popup_html = read("extension/popup.html")
    player = read("extension/player.js")

    check("★ offscreen.js 有 flushUplink（生产路径能收口尾段）",
          "function flushUplink" in off)
    check("★ offscreen.js 的 flush 发的是 {\"type\":\"flush\"}",
          re.search(r"JSON\.stringify\(\{\s*type:\s*'flush'\s*\}\)", off) is not None)
    check("★ offscreen.js 的 handleOffscreen 支持 flush 命令",
          re.search(r"case\s+'flush'\s*:", off) is not None)
    check("★ sw.js 中转 flush 到 offscreen",
          re.search(r"case\s+'flush'\s*:", sw) is not None
          and "offscreenCall('flush'" in sw)
    check("★ popup.html 有「停止并收尾」按钮",
          'id="btnFlush"' in popup_html)
    check("★ popup.js 绑定 btnFlush 并先 flush 再 stop",
          "btnFlush" in popup and re.search(r"cmd:\s*'flush'", popup) is not None)
    check("★ ★ pollStats 有「回落 player 自己那条 WS」（生产路径段数非零）",
          re.search(r"const w = \(typeof ws !== 'undefined'\) \? ws : null;", player)
          is not None)


def main() -> int:
    print("=" * 70)
    print("EXT-026 生产路径自测：真实用户路径（popup→tabCapture→offscreen→SW→player）")
    print("=" * 70)
    for fn in (test_harness_passes, test_harness_has_counter_examples,
               test_source_contracts):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check("★ %s 正常跑完" % fn.__name__, False,
                  "%s: %s" % (type(e).__name__, e))

    npass = sum(1 for (_, ok, _) in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 70)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    print("=" * 70)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
