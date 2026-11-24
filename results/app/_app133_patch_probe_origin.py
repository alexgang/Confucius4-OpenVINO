#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：修 §3.4 降级检查的 **hello 探针**（缺 Origin ⇒ 被桥接拒连）。

## 实测到的真缺陷（本轮首跑）

`_app129_clips_v26.py::hello_probe` 的探针脚本用

    websockets.connect("ws://127.0.0.1:<port>")

⇒ **不发 `Origin` 头** ⇒ 桥接 `ext/bridge.py` 的 `check_origin()` 判
`origin` 为空 ⇒ `check_origin()` 返回 **False** ⇒ 桥接
`await websocket.close(code=1008, reason="bad origin")`
⇒ 探针只拿到 `ConnectionClosedError`（实测 `hello_ack.raw=""`、
`err` 里是 `.../websockets/asyncio/connection.py ... recv`）⇒
**§3.4 的降级判定拿不到 `bg_state`/`bg_reason`**。

⇒ 对照：整链用的 `tools/bgkeep_e2e.py`（EXT 官方）**是带 Origin 的**：

    origin = "chrome-extension://" + str(resolve_extension_id())
    websockets.connect(url, ..., origin=origin)

⇒ 修法：**照官方 e2e 的口径**补 Origin（不改 EXT 代码、不放宽桥接校验）。

## 纪律

- **只改探针脚本里的一行**（加 `origin=` ＋ 取 id 的两行）；
  **判定逻辑与降级语义一行不改**；
- 定点替换 ＋ 唯一命中断言 ＋ 写前不变量 ＋ **还原式复核** ＋ 写后逐字节复核。
"""
from __future__ import annotations

import ast
import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'results/app/_app129_clips_v26.py'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


OLD = """        '    async with websockets.connect("ws://127.0.0.1:%d") as ws:\\n'
        % PORT +
        '        await ws.send(json.dumps({"type": "hello", "role": "uplink",\\n'
        '            "bg_keep": True, "bg_sample_rate": 48000, "bg_channels": 2,\\n'
        '            "target_lang": "zh", "voice": "A", "token": tok}))\\n'"""

NEW = """        '    async with websockets.connect("ws://127.0.0.1:%d", origin=origin) as ws:\\n'
        % PORT +
        '        await ws.send(json.dumps({"type": "hello", "role": "uplink",\\n'
        '            "bg_keep": True, "bg_sample_rate": 48000, "bg_channels": 2,\\n'
        '            "target_lang": "zh", "voice": "A", "token": tok}))\\n'"""

OLD2 = """        'import asyncio, json, base64, os, sys\\n'
        'import websockets\\n'
        'async def main():\\n'
        '    tok = open(sys.argv[1], encoding="utf-8").read().strip()\\n'"""

NEW2 = """        'import asyncio, json, base64, os, sys\\n'
        'import websockets\\n'
        'async def main():\\n'
        '    tok = open(sys.argv[1], encoding="utf-8").read().strip()\\n'
        '    # 🔴🔴 APP-133：**必须带 Origin** ⇒ 否则桥接 `check_origin()`\\n'
        '    #   判空 ⇒ `close(code=1008, reason="bad origin")` ⇒ 探针拿不到\\n'
        '    #   `hello_ack`（本轮首跑实测：`hello_ack.raw=""`）。\\n'
        '    #   ⇒ 口径与 EXT 官方 `tools/bgkeep_e2e.py` **完全一致**。\\n'
        '    sys.path.insert(0, sys.argv[2])\\n'
        '    from ext.extension_id import resolve_extension_id\\n'
        '    origin = "chrome-extension://" + str(resolve_extension_id())\\n'"""

OLD3 = """        p = subprocess.run([PKG_PY, '-X', 'utf8', tp,
                            os.path.join(cwd, 'bridge_token.txt')],
                           capture_output=True, text=True, timeout=120,
                           cwd=cwd, env=env)"""

NEW3 = """        p = subprocess.run([PKG_PY, '-X', 'utf8', tp,
                            os.path.join(cwd, 'bridge_token.txt'), PKG],
                           capture_output=True, text=True, timeout=120,
                           cwd=cwd, env=env)"""


def main():
    p = os.path.join(REPO, TARGET)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    crlf = '\r\n' in src

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133e'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    subs = [(OLD, NEW), (OLD2, NEW2), (OLD3, NEW3)]

    out = src
    for old, new in subs:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != 1:
            raise SystemExit('FAIL：命中 %d 次（要求 1）：%r' % (c, old[:80]))
        out = out.replace(o, nw)

    # 真不变量
    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = sum(norm(b).count('\n') - norm(a).count('\n')
                        for a, b in subs)
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d'
                         % (delta_got, delta_expect))
    red = out
    for old, new in subs:
        red = red.replace(norm(new), norm(old))
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133e'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL：写后逐字节复核失败')
    ast.parse(after.decode('utf-8'))
    print('OK %s  %d B -> %d B  sha %s -> %s  (AST OK)'
          % (TARGET, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))


if __name__ == '__main__':
    main()
