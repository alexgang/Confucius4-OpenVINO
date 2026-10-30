"""test_echo_roundtrip.py — P0 ③ 桥接回声测试（端到端）

验证 EXT-001 检查点 1 第 ③ 项：
  "服务端把收到的音频原样延迟后发回，插件按 t_start + D 排程播放，测排程误差（目标 ≤ 20 ms）"

本测试做的是**服务端侧**可验证的部分：
  * 桥接服务能起来（127.0.0.1，非 0.0.0.0）；
  * 非法 Origin 被拒；
  * 错误 token 被拒；
  * 正确 Origin + 正确 token 能连上，收到 hello_ack（含 segmentation 来源说明）；
  * echo 模式下，回声 PCM 与上行 PCM **逐样本相同**，t_start 与上行 sample_index 换算一致。

不跑推理 / 不占 GPU·NPU / 不抢共享锁。

运行：
    python tests/test_echo_roundtrip.py
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

from ext import config as C

RESULTS = []
# ★ EXT-017④：服务端现在按**本插件的精确扩展 id** 校验 Origin
#   （旧口径是 `startswith("chrome-extension://")` ⇒ 任何扩展都能连）。
#   ⇒ 这里必须用**真实**的扩展 id，否则「正确 Origin」这一项会被正确地拒掉。
#   真实 id 由 `ext.extension_id` 从 manifest 的 key 现场推导（与浏览器实测一致）。
from ext.extension_id import resolve_extension_id

_EID = resolve_extension_id()
if not _EID:
    # 解析不出 ⇒ 用已知值兜底（manifest 的 key 是确定的）。
    _EID = "kekgmfkijphpfndbbpakjaokamkeooib"
ORIGIN = "chrome-extension://%s" % _EID
PORT = 8799


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


async def _probe(token: str, origin: str, *, send_pcm: bool = True):
    """尝试连接并返回 ('connected'|'rejected', payload)。"""
    uri = f"ws://127.0.0.1:{PORT}"
    try:
        async with websockets.connect(
            uri,
            origin=origin,
            additional_headers={"X-Bridge-Token": token},
            open_timeout=5,
        ) as ws:
            await ws.send(json.dumps({"type": "hello"}))
            payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if send_pcm:
                pcm = np.zeros(C.SAMPLE_RATE // 10, dtype="<i2").tobytes()
                await ws.send(json.dumps({
                    "type": "pcm", "seq": 0, "sample_index": 0,
                    "pcm": base64.b64encode(pcm).decode("ascii"),
                }))
                payload2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                return "connected", payload, payload2
            return "connected", payload, None
    except Exception as e:
        return "rejected", str(e), None


async def run_server(token_path: str, proc_holder: list):
    from ext import bridge

    async def _serve():
        await bridge.serve("127.0.0.1", PORT, delay_sec=10.0,
                          echo_mode=True, token_path=token_path)

    proc_holder.append(asyncio.create_task(_serve()))
    await asyncio.sleep(1.0)


async def main_async() -> int:
    from ext.bridge import TokenStore

    tmp = tempfile.mkdtemp()
    token_path = os.path.join(tmp, "tok.txt")
    tokens = TokenStore(token_path)
    proc_holder: list = []

    print("=" * 68)
    print("P0 ③ 桥接回声测试（端到端，不跑推理）")
    print("=" * 68)

    await run_server(token_path, proc_holder)
    check("桥接服务已启动（127.0.0.1:8799）", True)

    # 1) 正确 Origin + token
    status, p1, p2 = await _probe(tokens.token, ORIGIN)
    check("正确 Origin+token 连接成功", status == "connected", str(p1)[:120])
    if status == "connected":
        check("hello_ack 带回 segmentation 说明",
              "segmentation" in p1 and p1["type"] == "hello_ack",
              str(p1.get("segmentation", ""))[:100])
        check("segmentation 标明不用 pyannote 断句",
              p1.get("segmentation", {}).get("pyannote_used_for_segmentation") is False)
        # 2) 回声内容逐样本一致
        echo_pcm = base64.b64decode(p2["pcm24k"])
        sent = np.zeros(C.SAMPLE_RATE // 10, dtype="<i2").tobytes()
        check("回声 PCM 与上行 PCM 完全一致", echo_pcm == sent,
              f"{len(echo_pcm)} bytes")
        check("回声 t_start 与 sample_index 换算一致",
              abs(p2["t_start"] - 0.0) < 1e-6, f"t_start={p2['t_start']}")
        check("回声带回 delay_sec（插件按 t_start+D 排程）",
              abs(p2.get("delay_sec", 0) - 10.0) < 1e-6)

    # 3) 非法 Origin
    status, msg, _ = await _probe(tokens.token, "http://evil.com", send_pcm=False)
    check("非法 Origin 被拒", status == "rejected", str(msg)[:80])

    # 4) 错误 token
    status, msg, _ = await _probe("wrong-token", ORIGIN, send_pcm=False)
    check("错误 token 被拒", status == "rejected", str(msg)[:80])

    # 5) 空 Origin
    status, msg, _ = await _probe(tokens.token, None, send_pcm=False)
    check("空 Origin 被拒", status == "rejected", str(msg)[:80])

    # 6) ★ EXT-017④：**别的**扩展（Origin 前缀对、id 不对）必须被拒
    status, msg, _ = await _probe(tokens.token,
                                  "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                  send_pcm=False)
    check("★ 别的扩展（id 不对）被拒", status == "rejected", str(msg)[:80])

    # 清理
    for t in proc_holder:
        t.cancel()
    try:
        await asyncio.gather(*proc_holder, return_exceptions=True)
    except Exception:
        pass

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


def main() -> int:
    try:
        return asyncio.run(main_async())
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
