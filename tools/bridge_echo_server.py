"""bridge_echo_server.py — 启动一个回声模式的桥接服务（给浏览器实测用）

EXT-003 的 P0①③ 实测需要桥接服务在 127.0.0.1 上跑回声模式：
  服务端把收到的音频原样延迟 D 后发回，插件按 t_start + D 排程播放。

用法：
    python tools/bridge_echo_server.py --port 8790 --delay 10 --token <token>
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ext import bridge  # noqa: E402
from ext.bridge import TokenStore  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--token-file", default=None)
    ap.add_argument("--print-token", action="store_true")
    args = ap.parse_args(argv)

    token_path = args.token_file or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".tmp", "probe_bridge_token.txt")
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    tokens = TokenStore(token_path)
    if args.print_token:
        print(tokens.token, flush=True)

    async def _run():
        await bridge.serve("127.0.0.1", args.port, delay_sec=args.delay,
                          echo_mode=True, token_path=token_path)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
