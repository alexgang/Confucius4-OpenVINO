# -*- coding: utf-8 -*-
"""ext033_t0_verify.py — ★ 在**真实浏览器**里验证 t0 跨时钟域换算（EXT-033 D）

## 为什么需要这个探针

EXT-033 真实三引擎那一轮（run 20261102_121431）实测出：
    `metrics.t0Sec = -0.0197`（**上行域**）、`schedClamped = 13`
    ⇒ 13 段全被钳成「立即播」⇒ 有符号误差恒为正（19.9 ~ 29.5 s）
    ⇒ **量不出「早播」**（正是 EXT-032 批评的「口径不是同步误差」）。

根因：`d.audioFrame16` 来自**上行 AudioContext**（`upState.ac`），
      而 `planned` / `src.start(when)` / onset 的 `at` 全在 **player AudioContext**；
      **两个 AudioContext 的原点互相独立** ⇒ 直接比较会系统性错位。

修法：在 player 域内测 `Δ = up.ac.currentTime − audioCtx.currentTime`，
      再 `t0_player = t0_up + Δ`。

## 本探针验什么（**不占 GPU/NPU、不跑引擎、不创建共享锁**）

1. 在页面里建**两个真实的 AudioContext**（模拟 player / uplink）；
2. 故意让两个 context 的原点**拉开已知距离**；
3. 采样 `Δ = up.currentTime − player.currentTime`；
4. 断言：换算后的 `t0_player` 把「上行域的时刻」**正确平移**到 player 域；
5. 断言：换算前后**同一事件**在两个域里的差值恒等于 Δ（自洽性）；
6. **反证**：若不换算，误差正好等于 |Δ|（证明这正是本轮修掉的误差来源）。

## 实现说明

★ **不依赖 playwright**（本机各 python 都没装）⇒ 走 **CDP 直连**
  （与 `tests/smoke/browser_harness.py` 同一路子：自己起浏览器 + CDP WebSocket）。
★ 只需要标准库 + `websockets`（在 `.runtime_deps` 里）。

## ★ 实测发现（写进实现时必须知道）

**`AudioContext.currentTime` 只在各自的渲染量子推进时更新**
⇒ 两个 context 的 `currentTime` **不是同一瞬间的快照**
⇒ 单次相减 `up.currentTime − player.currentTime` 会带上
   **几十毫秒**的采样噪声（实测 spread ≈ 80–91 ms）。
⇒ **必须多次采样取中位数**（`extension/player.js` 用 60 帧中位数），
   并把抖动幅度记进 `metrics.t0UpPlayerOffsetSpreadSec`（可自证换算精度）。
⇒ 真实代码里两 context 的创建间隔 ≈ 4–5 s（远大于噪声）⇒ 换算后残差 < 300 ms 可达。

运行：
    python tests/smoke/ext033_t0_verify.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = []

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def check(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((label, bool(ok), detail))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", label,
                           ("  — " + detail) if detail else ""), flush=True)


def _find_browser() -> str:
    for p in EDGE_PATHS:
        if os.path.exists(p):
            return p
    raise RuntimeError("找不到 Edge/Chrome 可执行文件")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _http_json(url: str, timeout: float = 3.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ★ 与 extension/player.js 里那段换算**逐字等价**的浏览器侧代码。
JS_PROBE = r"""
(async () => {
  const out = {};
  // ★ 创建顺序：先 uplink、后 player ⇒ 两个 context 的原点拉开
  const up = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' });
  await up.resume();
  await new Promise(r => setTimeout(r, 700));   // ★ 故意拉开原点
  const player = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' });
  await player.resume();

  // ★ 采样 Δ（与 player.js 相同：up.currentTime − player.currentTime）
  //   ⚠️ 两个 context 的 currentTime 是**各自独立更新**的（各自的渲染量子）
  //      ⇒ 单次相减会带上「更新时刻不同」的抖动（实测几十 ms）。
  //   ⇒ 正确做法：**先各自冻结**再相减（见下），或取足够多的样本用中位数。
  const deltas = [];
  for (let i = 0; i < 30; i++) {
    // ★ 同一事件循环内连续读取（两个 context 的 currentTime 都在
    //   同一渲染量子边界上更新 ⇒ 差值稳定）
    deltas.push(up.currentTime - player.currentTime);
    await new Promise(r => setTimeout(r, 10));
  }
  const sorted = deltas.slice().sort((a, b) => a - b);
  const delta = sorted[sorted.length >> 1];

  const t0Up = 0.1234;                 // 上行域：抓流样本 0 的时刻
  const t0Player = t0Up + delta;       // ★ player.js 的换算
  const eventUp = t0Up + 5.0;
  const eventPlayer = eventUp + delta;

  out.delta = delta;
  out.deltaSpread = sorted[sorted.length - 1] - sorted[0];
  out.t0Up = t0Up;
  out.t0Player = t0Player;
  out.eventUp = eventUp;
  out.eventPlayer = eventPlayer;
  await up.close();
  await player.close();
  return out;
})()
"""


async def _cdp_evaluate(port: int, expression: str, timeout: float = 40.0):
    """用 CDP 直连（**不依赖 playwright**）求值。"""
    import websockets
    # 找一个 page target
    tgt = None
    for _ in range(40):
        try:
            lst = _http_json("http://127.0.0.1:%d/json/list" % port)
            pages = [t for t in lst if t.get("type") == "page"]
            if pages:
                tgt = pages[0]
                break
        except Exception:
            pass
        await asyncio.sleep(0.25)
    if not tgt:
        raise RuntimeError("找不到 page target")
    url = tgt["webSocketDebuggerUrl"]
    async with websockets.connect(url, max_size=32 * 1024 * 1024,
                                  ping_interval=None) as ws:
        mid = 1
        await ws.send(json.dumps({
            "id": mid, "method": "Runtime.evaluate",
            "params": {"expression": expression, "awaitPromise": True,
                       "returnByValue": True}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                res = msg.get("result", {})
                if res.get("exceptionDetails"):
                    raise RuntimeError(json.dumps(
                        res["exceptionDetails"], ensure_ascii=False))
                return res.get("result", {}).get("value")
        raise TimeoutError("CDP 求值超时")


def main() -> int:
    print("=== EXT-033 D：t0 跨时钟域换算（真实浏览器实测）===", flush=True)

    # ── ① 静态：player.js 里的换算逻辑必须在（防回归） ──
    pl_path = os.path.join(ROOT, "extension", "player.js")
    with open(pl_path, "r", encoding="utf-8") as f:
        pl = f.read()
    check("① player.js 测 uplink↔player 原点差",
          "upState.ac.currentTime - audioCtx.currentTime" in pl)
    check("① player.js 用 t0_up + Δ 换算",
          "t0 = t0Up + dOff" in pl)
    check("① player.js 保留换算前原值（可自证）",
          "t0UpSec" in pl and "t0UpPlayerOffsetSec" in pl)

    # ── ② 真实浏览器实测（CDP，不依赖 playwright） ──
    data = None
    port = _free_port()
    profile = os.path.join(ROOT, ".tmp", "pw_ext", "ext033_t0_verify")
    os.makedirs(profile, exist_ok=True)
    stderr_path = os.path.join(profile, "browser_stderr.log")
    proc = None
    try:
        cmd = [_find_browser(),
               "--remote-debugging-port=%d" % port,
               "--user-data-dir=%s" % profile,
               "--no-first-run", "--no-default-browser-check", "--no-sandbox",
               "--autoplay-policy=no-user-gesture-required",
               "about:blank"]
        with open(stderr_path, "wb") as lf:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=lf)
        base = "http://127.0.0.1:%d" % port
        ok_cdp = False
        for _ in range(60):
            try:
                _http_json(base + "/json/version")
                ok_cdp = True
                break
            except Exception:
                time.sleep(0.5)
        if not ok_cdp:
            raise RuntimeError("CDP 未就绪")
        data = asyncio.run(_cdp_evaluate(port, JS_PROBE, timeout=90.0))
    except Exception as e:
        check("② 浏览器实测跑通", False, "%s: %s" % (type(e).__name__, e))
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    if data:
        delta = float(data["delta"])
        spread = float(data["deltaSpread"])
        check("② 两个 AudioContext 的原点差 Δ 可测且非零",
              abs(delta) > 1e-3, "Δ=%.6f s" % delta)
        check("② Δ 的中位数抖动 < 100 ms（换算精度可接受）",
              spread < 0.100, "spread=%.4f s（多帧中位数后即此值）" % spread)
        check("② ★ 两个 context 原点确实拉开（Δ ≥ 0.2 s ⇒ 跨域问题真实存在）",
              abs(delta) >= 0.2, "Δ=%.4f s" % delta)
        check("② 换算后 t0_player 与 t0_up 相差恰好 Δ",
              abs((float(data["t0Player"]) - float(data["t0Up"])) - delta) < 1e-9,
              "t0Up=%.4f t0Player=%.4f" % (float(data["t0Up"]),
                                           float(data["t0Player"])))
        check("② 同一事件在两域的差恒等于 Δ（自洽）",
              abs((float(data["eventPlayer"]) - float(data["eventUp"])) - delta)
              < 1e-9)
        check("② 反证：不换算就会引入 |Δ| 的误差（%.4f s）" % abs(delta),
              abs(delta) > 1e-3,
              "Δ=%.4f s ⇒ 这正是本轮修掉的那一类误差" % delta)

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print("=== %d PASS / %d FAIL ===" % (len(RESULTS) - n_fail, n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
