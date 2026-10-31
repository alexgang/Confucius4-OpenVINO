"""test_t1_capture_mode_stats.py — 自发任务 T-1 自测（capture_mode 上报进 stats）

本文件**不改写**既有断言，只**追加**新的行为级验收。

## 背景（为什么做这件事）

EXT-005 ① / EXT-008 都要求一条铁律：**「tabCapture 生产路径到底有没有被
实测过」必须能从数据核对**，而不是靠人读日志猜。

但实测发现：**插件侧早就知道自己走的是哪条抓流路**
（`offscreen.js` 的 `state.captureMode`、`player.js` 的 `upState.captureMode`，
取值 `'tabCapture' | 'getDisplayMedia'`），
**却从来没有上报给桥接服务** ⇒ 服务端 `stats()` 与落盘的 `margin.json`
里根本没有这个字段 ⇒ reviewer 拿到 P1 产物时**无法判断**
「这轮跑的到底是生产路径(tabCapture) 还是兜底路径(getDisplayMedia 兜底)」
⇒ 只能人工翻日志 —— 正是 EXT-005 ① 想避免的「宣称已验证但没法证明」。

⇒ T-1 的最小改动：插件把 `capture_mode` 报上来 ⇒ 服务端记进会话
⇒ `stats()` 回包 + `margin.json` 都带上它。

## 覆盖三块

  A. **行为级（服务端）** —— 真起一个桥接服务（回声模式，不跑推理），
     用真 WebSocket 发 hello / capture_info / stats，
     断言 **stats 回包真的带上了 capture_mode**。
     ⚠️ **必须有「旧写法拿不到」的对照**（防假通过）：
     先用一个**不带** capture_mode 的 hello 建连接 ⇒ 断言 stats 里
     `capture_mode` 是 `None`（不是 'tabCapture'）⇒
     再用带 capture_mode 的连接 ⇒ 断言 stats 里是 'tabCapture'。
     ⇒ 两条断言合起来才能证明「字段是真的从客户端来的，不是服务端编的」。

  B. **落盘产物** —— 断言 `margin.json`（`_dump_margin` 写的）也带
     `capture_mode` ⇒ reviewer 直接看落盘文件即可核对。

  C. **插件侧源码契约** —— `player.js` 的 hello 带 `capture_mode`；
     `offscreen.js` 在抓流成功后补发 `capture_info`；
     `sw.js` 的**计划值**不能被当成**实际值**上报（降级陷阱）。

  D. **扩展图标** —— `manifest.json` 有 `icons` 字段且四个文件**真实存在**
     且是**合法 PNG**（不是 0 字节占位）；
     ⚠️ 且 `manifest.key` **必须没变**（扩展 ID 由 key 决定，
     EXT-017④ 的 Origin 校验依赖它）⇒ 断言算出来的扩展 id 仍是
     `kekgmfkijphpfndbbpakjaokamkeooib`。

不跑推理 / 不占 GPU·NPU / 不抢共享锁。

运行：
    python tests/test_t1_capture_mode_stats.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ext.extension_id import resolve_extension_id

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(ROOT, "extension")
RESULTS = []

EXPECTED_EXT_ID = "kekgmfkijphpfndbbpakjaokamkeooib"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


# ── A/B：行为级（真起服务 + 真 WebSocket）────────────────────────
async def _probe_capture_mode(port: int, token: str, *,
                              hello_extra: dict,
                              send_capture_info: bool,
                              capture_info_mode: str = "getDisplayMedia"):
    """连上桥接 → 发 hello(+capture_mode) → 可选补发 capture_info
    → 发 stats → 返回 (hello_ack, stats_msg)。

    ★ `capture_info_mode` 与 hello 里的 capture_mode 是**两个独立来源**
      —— 真实场景就是这样：hello 时还不知道走哪条路（offscreen），
      抓流成功后才补报实际值。
    ★ 返回 None 表示连接失败（调用方据此判 FAIL，不当 PASS）。
    """
    import websockets

    from ext.extension_id import resolve_extension_id as _rid
    origin = "chrome-extension://%s" % (_rid() or EXPECTED_EXT_ID)

    async with websockets.connect(
        "ws://127.0.0.1:%d" % port,
        origin=origin,
        additional_headers={"X-Bridge-Token": token},
        open_timeout=10,
    ) as ws:
        hello = dict(hello_extra)
        hello.update({"type": "hello", "token": token})
        await ws.send(json.dumps(hello))
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        hello_ack = json.loads(raw)

        if send_capture_info:
            await ws.send(json.dumps({
                "type": "capture_info",
                "capture_mode": capture_info_mode,
                "source_rate": 48000,
            }))
            # 服务端对 capture_info 不回包 ⇒ 不用等回包，直接要 stats。

        await ws.send(json.dumps({"type": "stats"}))
        raw2 = await asyncio.wait_for(ws.recv(), timeout=20)
        stats = json.loads(raw2)
        return hello_ack, stats


async def _run_behavior() -> None:
    from ext import bridge
    from ext.bridge import TokenStore

    # 动态端口（历史经验：固定端口 + 固定超时 = 假 FAIL 的常见来源）
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    tmp = tempfile.mkdtemp()
    token_path = os.path.join(tmp, "tok.txt")
    tokens = TokenStore(token_path)

    tasks = []
    holder = {}

    async def _serve():
        await bridge.serve("127.0.0.1", port, delay_sec=10.0,
                           echo_mode=True, token_path=token_path,
                           session_holder=holder)

    tasks.append(asyncio.create_task(_serve()))
    await asyncio.sleep(1.5)

    try:
        # ── 对照组：**不带** capture_mode 的 hello ⇒ stats 里必须是 None
        #    （★ 关键：证明服务端**不会自己编**一个 'tabCapture'）
        h1, s1 = await _probe_capture_mode(
            port, tokens.token,
            hello_extra={"role": "p1_probe", "source": "p1_probe"},
            send_capture_info=False)
        check("★ 对照组：不带 capture_mode ⇒ stats 里是 None（服务端不编造）",
              s1.get("capture_mode") is None,
              "实际=%r" % (s1.get("capture_mode"),))
        check("对照组：hello_ack 仍正常返回（向后兼容）",
              h1.get("type") == "hello_ack", str(h1)[:120])
        check("对照组：hello_ack 里的 capture_mode 为 None",
              h1.get("capture_mode") is None,
              "实际=%r" % (h1.get("capture_mode"),))
        check("对照组：client_source 记下了客户端身份",
              s1.get("client_source") == "p1_probe",
              "实际=%r" % (s1.get("client_source"),))

        # ── 实验组：hello 里带 capture_mode ⇒ stats 里必须是它
        h2, s2 = await _probe_capture_mode(
            port, tokens.token,
            hello_extra={"role": "uplink", "source": "offscreen",
                         "capture_mode": "tabCapture", "source_rate": 48000},
            send_capture_info=False)
        check("★ 实验组：hello 带 capture_mode ⇒ stats 回包带 'tabCapture'",
              s2.get("capture_mode") == "tabCapture",
              "实际=%r" % (s2.get("capture_mode"),))
        check("实验组：hello_ack 回显服务端记到的 capture_mode",
              h2.get("capture_mode") == "tabCapture",
              "实际=%r" % (h2.get("capture_mode"),))
        check("实验组：source_rate 一并记下（48000）",
              s2.get("source_rate") == 48000,
              "实际=%r" % (s2.get("source_rate"),))

        # ── 第三条路径：hello 之后补发 capture_info（offscreen 的真实时序）
        #    ★ 断言**补报能覆盖 hello 里的值** —— 因为 offscreen 的 hello
        #      里 capture_mode 是 null，补报才是唯一来源。
        h3, s3 = await _probe_capture_mode(
            port, tokens.token,
            hello_extra={"role": "uplink", "source": "offscreen"},
            send_capture_info=True,
            capture_info_mode="getDisplayMedia")
        check("★ 第三条路径：hello 后补发 capture_info ⇒ stats 拿到 'getDisplayMedia'",
              s3.get("capture_mode") == "getDisplayMedia",
              "实际=%r" % (s3.get("capture_mode"),))
        check("第三条路径：补报后 source_rate 也被记下",
              s3.get("source_rate") == 48000,
              "实际=%r" % (s3.get("source_rate"),))

        # ── 白名单：未知取值必须被丢弃（不记成未知字符串）
        h4, s4 = await _probe_capture_mode(
            port, tokens.token,
            hello_extra={"role": "uplink", "capture_mode": "someBogusMode"},
            send_capture_info=False)
        check("★ 白名单：未知 capture_mode 被丢弃（不写进 stats）",
              s4.get("capture_mode") is None,
              "实际=%r" % (s4.get("capture_mode"),))

        # ── B：落盘产物 margin.json 也带 capture_mode
        margin_path = os.path.join(tmp, "margin.json")
        sess = holder.get("session")
        check("会话已登记（session_holder 里拿得到）", sess is not None)
        if sess is not None:
            # 让真会话的 capture_mode 变成 tabCapture（模拟客户端上报过）
            sess.note_client({"capture_mode": "tabCapture", "source": "offscreen"})
            bridge._dump_margin(holder, margin_path, None)
            ok = os.path.isfile(margin_path)
            check("★ B：margin.json 落盘成功", ok, margin_path)
            if ok:
                with open(margin_path, "r", encoding="utf-8") as f:
                    mj = json.load(f)
                check("★ B：margin.json 里带 capture_mode='tabCapture'",
                      mj.get("capture_mode") == "tabCapture",
                      "实际=%r" % (mj.get("capture_mode"),))
                check("B：margin.json 里带 client_source",
                      mj.get("client_source") == "offscreen",
                      "实际=%r" % (mj.get("client_source"),))

    finally:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass


# ── C：插件侧源码契约 ───────────────────────────────────────────
def _read(name: str) -> str:
    with open(os.path.join(EXT_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def _check_plugin_contract() -> None:
    pl = _read("player.js")
    off = _read("offscreen.js")
    sw = _read("sw.js")

    check("C1 player.js 的 hello 带 capture_mode",
          "capture_mode" in pl and "type: 'hello'" in pl)
    check("C2 player.js 上报的是 upState.captureMode（实际值）",
          "capture_mode: upState.captureMode" in pl)
    check("C3 offscreen.js 抓流成功后补发 capture_info",
          "capture_info" in off and "reportCaptureMode" in off)
    check("C4 offscreen.js 的 capture_info 报的是 state.captureMode（实际值）",
          "capture_mode: state.captureMode" in off)
    # ★ 降级陷阱：sw.js 里 captureMode 是**计划值**（拿不到 stream id 时
    #   会被降级成 getDisplayMedia）⇒ 不能把它当成实际值上报。
    check("★ C5 sw.js 的计划值不被当成实际值上报（降级陷阱有防护）",
          "capture_mode: sw.js 计划值" not in off
          and "capture_mode: captureMode" not in off
          and "capture_mode: sessionState" not in off,
          "offscreen.js 里不该出现 sw 的计划值")

    # ★ 服务端必须认 capture_info 消息
    br = _read_bridge()
    check("C6 服务端处理 capture_info 消息",
          '"capture_info"' in br)
    check("C7 服务端 stats() 输出 capture_mode",
          '"capture_mode": self.capture_mode' in br)
    check("C8 服务端落盘 margin.json 时输出 capture_mode",
          '"capture_mode": (getattr(sess, "capture_mode", None) if sess else None)' in br)


def _read_bridge() -> str:
    with open(os.path.join(ROOT, "ext", "bridge.py"), "r", encoding="utf-8") as f:
        return f.read()


# ── D：扩展图标 ─────────────────────────────────────────────────
def _png_info(path: str):
    """返回 (width, height, bytes) 或 None（不是合法 PNG）。"""
    try:
        with open(path, "rb") as f:
            d = f.read()
        if len(d) < 8 or d[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        w, h = struct.unpack(">II", d[16:24])
        return (w, h, len(d))
    except Exception:
        return None


def _check_icons() -> None:
    mpath = os.path.join(EXT_DIR, "manifest.json")
    with open(mpath, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    icons = manifest.get("icons") or {}
    check("D1 manifest.json 有 icons 字段", bool(icons), str(icons)[:120])
    for s in ("16", "32", "48", "128"):
        rel = icons.get(s)
        if not rel:
            check("D2 manifest icons[%s] 存在" % s, False, "缺 %s" % s)
            continue
        p = os.path.join(EXT_DIR, rel.replace("/", os.sep))
        exists = os.path.isfile(p)
        check("D2 icons[%s] 文件真实存在（%s）" % (s, rel), exists, p)
        if not exists:
            continue
        info = _png_info(p)
        check("D3 icons[%s] 是合法 PNG 且尺寸=%s" % (s, s),
              info is not None and info[0] == int(s) and info[1] == int(s),
              "实际=%r" % (info,))
        check("D4 icons[%s] 不是 0 字节占位" % s,
              info is not None and info[2] > 0, "实际=%r" % (info,))

    action = manifest.get("action") or {}
    check("D5 manifest action 有 default_icon",
          bool(action.get("default_icon")), str(action)[:120])

    # ★ 扩展 ID 必须不变（key 没被动过）
    eid = resolve_extension_id()
    check("★ D6 扩展 ID 未变（manifest.key 未被改动）",
          eid == EXPECTED_EXT_ID, "实际=%r 期望=%r" % (eid, EXPECTED_EXT_ID))

    # ★ 图标生成脚本可复现（不是手工塞进去的一次性文件）
    check("D7 图标由 tools/make_icons.py 生成（脚本在库）",
          os.path.isfile(os.path.join(ROOT, "tools", "make_icons.py")))


def main() -> int:
    print("=" * 68)
    print("T-1 自测：captureMode 上报进 stats + 扩展图标")
    print("=" * 68)

    print("\n[A/B] 行为级：真起桥接服务 + 真 WebSocket")
    try:
        asyncio.run(_run_behavior())
    except Exception:
        traceback.print_exc()
        check("★ 行为级自测未抛异常", False, "见上方 traceback")

    print("\n[C] 插件侧源码契约")
    try:
        _check_plugin_contract()
    except Exception:
        traceback.print_exc()
        check("插件契约检查未抛异常", False)

    print("\n[D] 扩展图标")
    try:
        _check_icons()
    except Exception:
        traceback.print_exc()
        check("图标检查未抛异常", False)

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
