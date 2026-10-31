"""test_ext024_dl_routing.py — ★ EXT-024 自测：下行路由 / 会话生命周期 / 模式与语言

本文件**不改写**既有断言，只**追加**新的行为级验收。

## 为什么需要这个文件（reviewer EXT-024 验收第 5 条明文）

> 单测：模拟一条连接只发 pcm、另一条只收（或合并后的单连接）——
> 断言 tts 一定能到达有 onmessage 的那一端；关闭连接后 holder 被清空。

⇒ 本文件做三件事：

  A. **服务端下行路由（行为级）** —— 起一个**回声**桥接（不跑推理、
     不占 GPU/NPU），开**两条** WS：
       · 一条 `role='uplink'`（只发 pcm，不读下行）；
       · 一条 `role='player'`（只读下行）。
     ⇒ 断言：**上行会话产出的 `echo`/`tts` 一定到达 player 那条**。
     ★ 这是 EXT-024 的根因修复（以前只发回「本连接」⇒ 玩家端全丢）。

  B. **会话生命周期（行为级）** ——
     · 关闭 uplink 连接 ⇒ holder 里的 session / producer_session 被清空；
     · 新 uplink 连接**接管**旧的 uplink 会话（旧会话的流水线被停掉）；
     · **player 连接不顶替** uplink 会话（EXT-024 B 明文）。

  C. **模式字段 + 语言映射** ——
     · `hello_ack` 带 `mode` / `engines_ready` / `pipeline`（只新增、不改旧字段）；
     · `targetLang='Chinese'` ⇒ 服务端映射成 `zh`（EXT-024 G）。

不跑推理 / 不占 GPU·NPU / **不创建共享锁**（回声模式不计时不测速）。

运行：
    python tests/test_ext024_dl_routing.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import tempfile
import traceback

import numpy as np
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from ext import config as C
from ext.extension_id import resolve_extension_id

_EID = resolve_extension_id() or "kekgmfkijphpfndbbpakjaokamkeooib"
ORIGIN = "chrome-extension://%s" % _EID
PORT = 8797

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


def _pcm(sec: float = 0.1) -> bytes:
    n = int(C.SAMPLE_RATE * sec)
    return np.zeros(n, dtype="<i2").tobytes()


async def _recv_until(ws, want: str, timeout: float = 6.0):
    """收到一条 `type == want` 的消息就返回它（中间的消息丢掉）。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remain = deadline - asyncio.get_event_loop().time()
        if remain <= 0:
            return None
        raw = await asyncio.wait_for(ws.recv(), timeout=remain)
        m = json.loads(raw)
        if m.get("type") == want:
            return m


# ══════════════════════════════════════════════════════════════
# A：下行路由 —— tts/echo 一定到达「有 onmessage 的那一端」
# ══════════════════════════════════════════════════════════════
async def test_downlink_reaches_player() -> None:
    print("\n[A] ★★★ 下行路由：上行的产出必须到达 player 连接")
    from ext import bridge
    from ext.bridge import TokenStore

    tmp = tempfile.mkdtemp()
    token_path = os.path.join(tmp, "tok.txt")
    tokens = TokenStore(token_path)

    holder: dict = {}
    tasks = []

    async def _serve():
        await bridge.serve("127.0.0.1", PORT, delay_sec=10.0,
                           echo_mode=True, token_path=token_path,
                           session_holder=holder)
    tasks.append(asyncio.create_task(_serve()))
    await asyncio.sleep(1.2)

    uri = f"ws://127.0.0.1:{PORT}"
    try:
        # ── 连接 ①：uplink（只发 pcm，不读下行） ──────────────
        up = await websockets.connect(uri, origin=ORIGIN,
                                      additional_headers={"X-Ext-Token": tokens.token})
        await up.send(json.dumps({
            "type": "hello", "token": tokens.token, "role": "uplink",
            "source": "player", "sample_rate": 16000,
            "target_lang": "zh", "voice": "A",
        }))
        up_ack = await _recv_until(up, "hello_ack", timeout=6.0)
        check("A1 uplink 连接收到 hello_ack", up_ack is not None)
        if up_ack:
            check("★ A2 hello_ack 带 mode 字段（EXT-024 F 的数据源）",
                  up_ack.get("mode") == "echo",
                  "实测 mode=%r" % up_ack.get("mode"))
            check("★ A3 hello_ack 带 engines_ready（回声恒 True）",
                  up_ack.get("engines_ready") is True,
                  "实测 %r" % up_ack.get("engines_ready"))
            check("★ A4 hello_ack 带 pipeline 字段",
                  "pipeline" in up_ack, str(up_ack.keys())[:120])
            check("★ A5 hello_ack **保留**了旧字段（向后兼容）",
                  "segmentation" in up_ack and "delay_sec" in up_ack,
                  str(up_ack.keys())[:150])

        # ── 连接 ②：player（只读下行） ────────────────────────
        pl = await websockets.connect(uri, origin=ORIGIN,
                                      additional_headers={"X-Ext-Token": tokens.token})
        await pl.send(json.dumps({
            "type": "hello", "token": tokens.token, "role": "player",
            "source": "player", "sample_rate": 16000,
            "target_lang": "zh", "voice": "A",
        }))
        pl_ack = await _recv_until(pl, "hello_ack", timeout=6.0)
        check("A6 player 连接收到 hello_ack", pl_ack is not None)

        # 等一下，让服务端把 player 注册进 registry
        await asyncio.sleep(0.6)

        # ── 上行发 pcm（产出回声） ────────────────────────────
        await up.send(json.dumps({
            "type": "pcm", "seq": 0, "sample_index": 0,
            "pcm": base64.b64encode(_pcm(0.2)).decode("ascii"),
        }))

        got = await _recv_until(pl, "echo", timeout=8.0)
        check("★★★ A7 上行会话产出的 echo **到达了 player 连接**",
              got is not None,
              "player 没收到任何 echo（EXT-024 根因未修复）")
        if got:
            check("A8 echo 带 id（插件按 id 去重）", bool(got.get("id")),
                  str(got)[:120])
            check("A9 echo 带 pcm24k（能播）",
                  bool(got.get("pcm24k")), str(got.keys())[:120])

        # ── 反证：uplink 那条**也**能收到（服务端会广播给产生者） ──
        up_got = await _recv_until(up, "echo", timeout=4.0)
        check("A10 产生者连接也收到广播（服务端按 token 广播）",
              up_got is not None, "uplink 未收到 echo")
    finally:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# B：会话生命周期 —— 连接关闭清 holder；新 uplink 接管旧 uplink
# ══════════════════════════════════════════════════════════════
async def test_session_lifecycle() -> None:
    print("\n[B] ★ 会话生命周期：连接关闭 ⇒ 清 holder；新 uplink 接管旧的")
    from ext import bridge
    from ext.bridge import TokenStore

    tmp = tempfile.mkdtemp()
    token_path = os.path.join(tmp, "tok.txt")
    tokens = TokenStore(token_path)

    holder: dict = {}
    tasks = []

    async def _serve():
        await bridge.serve("127.0.0.1", PORT, delay_sec=10.0,
                           echo_mode=True, token_path=token_path,
                           session_holder=holder)
    tasks.append(asyncio.create_task(_serve()))
    await asyncio.sleep(1.2)

    uri = f"ws://127.0.0.1:{PORT}"
    try:
        # ── ① uplink 连接建立 ⇒ holder 里有会话 ───────────────
        up = await websockets.connect(uri, origin=ORIGIN,
                                      additional_headers={"X-Ext-Token": tokens.token})
        await up.send(json.dumps({
            "type": "hello", "token": tokens.token, "role": "uplink",
            "sample_rate": 16000, "target_lang": "zh", "voice": "A",
        }))
        await _recv_until(up, "hello_ack", timeout=6.0)
        await asyncio.sleep(0.4)
        check("★ B1 uplink 连上 ⇒ holder 里有会话",
              holder.get("session") is not None
              or holder.get("producer_session") is not None,
              "holder keys=%r" % sorted(holder.keys()))

        # ── ② player 连接**不顶替** uplink 会话 ───────────────
        pl = await websockets.connect(uri, origin=ORIGIN,
                                      additional_headers={"X-Ext-Token": tokens.token})
        await pl.send(json.dumps({
            "type": "hello", "token": tokens.token, "role": "player",
            "sample_rate": 16000,
        }))
        await _recv_until(pl, "hello_ack", timeout=6.0)
        await asyncio.sleep(0.4)
        prod_before = holder.get("producer_session")
        check("★ B2 player 连接**没有顶替** uplink 的产出会话",
              prod_before is not None
              and getattr(prod_before, "client_role", None) == "uplink",
              "producer_session role=%r"
              % getattr(prod_before, "client_role", None))

        # ── ③ 关闭 uplink ⇒ holder 被清空 ────────────────────
        await up.close()
        await asyncio.sleep(1.2)
        check("★★★ B3 uplink 关闭 ⇒ holder['session'] 被清空",
              holder.get("session") is None,
              "实测 session=%r" % type(holder.get("session")).__name__)
        check("★★★ B4 uplink 关闭 ⇒ holder['producer_session'] 被清空",
              holder.get("producer_session") is None,
              "实测 producer=%r" % type(holder.get("producer_session")).__name__)
        check("B5 旧会话被归档到 last_session（便于事后查）",
              holder.get("last_session") is not None,
              "last_session=%r" % type(holder.get("last_session")).__name__)

        await pl.close()
        await asyncio.sleep(0.6)

        # ── ④ 新 uplink 能重新建立会话（接管旧 uplink 的路径） ─
        up2 = await websockets.connect(uri, origin=ORIGIN,
                                       additional_headers={"X-Ext-Token": tokens.token})
        await up2.send(json.dumps({
            "type": "hello", "token": tokens.token, "role": "uplink",
            "sample_rate": 16000, "target_lang": "zh", "voice": "A",
        }))
        ack2 = await _recv_until(up2, "hello_ack", timeout=6.0)
        check("B6 新 uplink 连接成功", ack2 is not None)
        await asyncio.sleep(0.4)
        check("★ B7 新 uplink 建立了**新的**产出会话",
              holder.get("producer_session") is not None
              and getattr(holder.get("producer_session"),
                          "client_role", None) == "uplink",
              "producer=%r" % type(holder.get("producer_session")).__name__)
        await up2.close()
    finally:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# C：语言映射（EXT-024 G）+ 模式字段（EXT-024 F）
# ══════════════════════════════════════════════════════════════
def test_lang_mapping_and_mode() -> None:
    print("\n[C] ★ 语言映射（EXT-024 G）+ 模式字段（EXT-024 F）")
    from ext.config import normalize_lang_code

    check("★ C1 'Chinese' ⇒ 'zh'（EXT-024 G 明确要求）",
          normalize_lang_code("Chinese") == "zh",
          "实测 %r" % normalize_lang_code("Chinese"))
    check("C2 'English' ⇒ 'en'", normalize_lang_code("English") == "en",
          "实测 %r" % normalize_lang_code("English"))
    check("C3 'Japanese' ⇒ 'ja'", normalize_lang_code("Japanese") == "ja",
          "实测 %r" % normalize_lang_code("Japanese"))
    check("C4 'Korean' ⇒ 'ko'", normalize_lang_code("Korean") == "ko",
          "实测 %r" % normalize_lang_code("Korean"))
    check("C5 'zh' ⇒ 'zh'（已是码则原样）",
          normalize_lang_code("zh") == "zh")
    check("★ C6 未知语种 ⇒ None（**不臆造**）",
          normalize_lang_code("Klingon") is None,
          "实测 %r" % normalize_lang_code("Klingon"))
    check("C7 空串 ⇒ None", normalize_lang_code("") is None)
    check("C8 None ⇒ None", normalize_lang_code(None) is None)

    # ★ 会话层：note_client 走的是 normalize_lang_code ⇒ 面板存
    #   "Chinese" 也能被服务端认成 zh。
    from ext.bridge import Session
    s = Session(token="t")
    s.note_client({"target_lang": "Chinese", "voice": "A"})
    check("★ C9 会话把 'Chinese' 认成 zh",
          getattr(s, "client_target_lang", None) == "zh",
          "实测 %r" % getattr(s, "client_target_lang", None))

    s2 = Session(token="t")
    s2.note_client({"target_lang": "Klingon", "voice": "A"})
    check("★ C10 会话把未知语种记成 None（不臆造）",
          getattr(s2, "client_target_lang", None) is None,
          "实测 %r" % getattr(s2, "client_target_lang", None))

    # ★★ EXT-024 A（reviewer 明文）：「要写清楚 t_start 用的是哪个时间轴」
    #   ⇒ 断言这个口径**落盘**到 margin.json（reviewer 可直接核对文件）。
    # ⚠️ 这组是**行为级**（真调 _dump_margin 真写文件），不是看源码字符串。
    _tmp = tempfile.mkdtemp()
    _margin = os.path.join(_tmp, "margin.json")
    _holder = {"session": Session(token="t")}
    from ext.bridge import _dump_margin
    _dump_margin(_holder, _margin, None)
    check("★★ EXT-024 A：margin.json 落盘 t_start_axis（可从文件核对）",
          os.path.isfile(_margin)
          and json.load(open(_margin, encoding="utf-8")).get("t_start_axis")
          == "uplink_sample_index",
          _margin)
    check("★★ EXT-024 A：margin.json 附时间轴口径说明",
          bool(json.load(open(_margin, encoding="utf-8"))
               .get("t_start_axis_note")))


# ══════════════════════════════════════════════════════════════
# D：源码契约 —— 服务端必须有 registry / 角色分类 / 广播
# ══════════════════════════════════════════════════════════════
def test_source_contract() -> None:
    print("\n[D] 源码契约：服务端有连接登记表与角色分类")
    src = open(os.path.join(ROOT, "ext", "bridge.py"),
               "r", encoding="utf-8").read()

    check("D1 有 ConnectionRegistry 类",
          "class ConnectionRegistry" in src)
    check("★ D2 有 downlink_targets（按 token 广播给 player）",
          "def downlink_targets(" in src)
    check("★ D3 有 classify_role（识别 player / uplink）",
          "def classify_role(" in src)
    check("★ D4 未报角色的连接**不会**被当成 player",
          "info.get(\"role\") == \"player\"" in src)
    check("★ D5 有 _release_session（连接关闭清 holder）",
          "def _release_session(" in src)
    check("★ D6 有 _producer_session（读产出会话而不是 player 会话）",
          "def _producer_session(" in src)
    check("★ D7 有 _propagate_client_settings（面板设置双向同步）",
          "def _propagate_client_settings(" in src)
    check("D8 hello_ack 含 mode / engines_ready / pipeline",
          '"mode": mode' in src and '"engines_ready"' in src
          and '"pipeline"' in src)
    check("★ D9 有段级日志 _log_segment",
          "def _log_segment(" in src)
    # ★★ EXT-024 A 明文：「要写清楚 t_start 用的是哪个时间轴」
    #   ⇒ 断言这个口径**落进产物**（不是只写在注释里）。
    check("★ D9b tts 任务带 t_start_axis（时间轴口径明文）",
          '"t_start_axis"' in src)
    check("★ D9c margin.json 也落盘 t_start_axis（可从文件核对）",
          '"t_start_axis": "uplink_sample_index"' in src)

    # ── 插件侧契约 ──────────────────────────────────────────
    pjs = open(os.path.join(ROOT, "extension", "player.js"),
               "r", encoding="utf-8").read()
    check("★ D10 player.js 的上行 WS **有** onmessage（根因修复的插件侧一半）",
          "upState.ws" in pjs and "ws.onmessage" in pjs)
    check("★ D11 player.js 有统一的下行处理函数 handleBridgeMessage",
          "function handleBridgeMessage(" in pjs)
    check("★ D12 player.js 按 id 去重（seenDubIds）",
          "seenDubIds" in pjs and "SEEN_DUB_CAP" in pjs)
    check("★ D13 player.js 订阅了 SW 广播（offscreen 路径）",
          "'ext-dub'" in pjs and "listenSwBroadcast" in pjs)

    osjs = open(os.path.join(ROOT, "extension", "offscreen.js"),
                "r", encoding="utf-8").read()
    check("★ D14 offscreen.js 把下行**转发**给 player（不再只计数）",
          "forwardToPlayer" in osjs)

    php = open(os.path.join(ROOT, "extension", "popup.js"),
               "r", encoding="utf-8").read()
    check("★ D15 popup.js 有模式门禁 startGate",
          "function startGate(" in php)
    check("★ D16 popup.js 显示模式（setMode）",
          "function setMode(" in php)

    phh = open(os.path.join(ROOT, "extension", "popup.html"),
               "r", encoding="utf-8").read()
    check("★ D17 popup.html 有模式元素 #mMode",
          'id="mMode"' in phh)

    phl = open(os.path.join(ROOT, "extension", "player.html"),
               "r", encoding="utf-8").read()
    check("★ D18 player.html 有链路状态条 #linkBar / #linkReason",
          'id="linkBar"' in phl and 'id="linkReason"' in phl)

    lsrc = open(os.path.join(ROOT, "tools", "ext_launcher.py"),
                "r", encoding="utf-8").read()
    check("★ D19 启动器有单实例守卫 _alive_instance",
          "def _alive_instance(" in lsrc)
    check("★ D20 启动器提示语含「已有桥接服务在运行（PID」",
          "已有桥接服务在运行（PID=" in lsrc)


# ══════════════════════════════════════════════════════════════
# E：插件侧行为级（node 沙箱跑 player.js / popup.js 的**真函数**）
# ══════════════════════════════════════════════════════════════
def test_plugin_behavior_harness() -> None:
    print("\n[E] ★ 插件侧行为级：node harness（diagnoseLink / 去重 / startGate）")
    import shutil
    import subprocess

    harness = os.path.join(ROOT, "tests", "ext024_link_harness.js")
    check("E1 harness 文件存在", os.path.isfile(harness), harness)
    if not os.path.isfile(harness):
        return
    node = shutil.which("node") or ""
    if not node:
        check("E2 node 可用（跳过本组）", True, "node 不可用")
        return
    r = subprocess.run([node, harness], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    out = r.stdout or ""
    check("★★★ E3 node harness 全部通过（rc=0）",
          r.returncode == 0,
          "rc=%d；输出尾部：%s" % (r.returncode, out[-800:]))
    check("★★★ E4 harness 至少跑了 30 项断言",
          out.count("[PASS]") >= 30,
          "PASS 数=%d" % out.count("[PASS]"))
    check("E5 harness 里没有 FAIL", "[FAIL]" not in out,
          out[-400:])


def main() -> int:
    print("=" * 68)
    print("EXT-024 自测：下行路由 / 会话生命周期 / 模式与语言")
    print("=" * 68)
    for fn in (test_downlink_reaches_player,
               test_session_lifecycle,
               test_lang_mapping_and_mode,
               test_source_contract,
               test_plugin_behavior_harness):
        try:
            if asyncio.iscoroutinefunction(fn):
                asyncio.run(fn())
            else:
                fn()
        except Exception:
            traceback.print_exc()
            check("★ %s 未抛异常" % fn.__name__, False, "见上方 traceback")

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
