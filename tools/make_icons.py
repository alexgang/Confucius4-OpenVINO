"""make_icons.py — 生成扩展图标（EXT-018）

**为什么需要**：EXT-001 的 P2 待办里明写着「扩展图标」这一项；
而 `extension/manifest.json` 此前**没有 `icons` 字段**
⇒ 浏览器/工具栏显示的是默认占位图（灰底 puzzle 块），
用户一眼看不出这是「实时翻译配音」插件。

**为什么不引第三方库**：本机 venv 里没有 PIL；图标是 16/32/48/128 的
小方块 ⇒ 用标准库 `zlib` + `struct` 直接写 PNG 即可（无依赖、可复现）。

**图案**：深色圆角方块 + 三条浅蓝色声波竖条（中间最高）
⇒ 一眼能认出是「音频/配音」类插件，且在小尺寸（16px）仍可辨认。

⚠️ **不改 manifest 的 `key`** —— 扩展 ID 由 key 决定
（`ext/extension_id.py` 算出的 `kekgmfkijphpfndbbpakjaokamkeooib`，
EXT-017④ 的 Origin 校验依赖它）⇒ 只加 `icons` 字段，绝不碰 `key`。

运行：
    python tools/make_icons.py
"""
from __future__ import annotations

import json
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(ROOT, "extension", "icons")
SIZES = (16, 32, 48, 128)

BG = (22, 27, 34, 255)          # #161b22 深色底
FG = (88, 166, 255, 255)        # #58a6ff 浅蓝声波
CLEAR = (0, 0, 0, 0)            # 圆角外透明


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return (struct.pack(">I", len(data)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def render(size: int) -> bytes:
    """画一张 `size`×`size` 的 RGBA 图标，返回 PNG 字节。"""
    px = [[CLEAR] * size for _ in range(size)]

    # ① 圆角方块底（半径 = size/8，最小 2px）
    radius = max(2, size // 8)
    for y in range(size):
        for x in range(size):
            cx = min(max(x, radius), size - 1 - radius)
            cy = min(max(y, radius), size - 1 - radius)
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                px[y][x] = BG

    # ② 三条声波竖条（中间最高）—— 坐标用**比例**算，别再乘两次 size。
    bars = ((0.30, 0.42), (0.45, 0.66), (0.60, 0.42))
    bar_w = max(1, size // 12)
    for fx, fh in bars:
        bx = int(size * fx)
        bh = int(size * fh)
        top = (size - bh) // 2
        for y in range(max(0, top), min(size, top + bh)):
            for x in range(bx, min(size, bx + bar_w)):
                px[y][x] = FG

    raw = b""
    for y in range(size):
        raw += b"\x00"  # 每行的 filter 字节（0 = None）
        raw += b"".join(struct.pack("BBBB", *px[y][x]) for x in range(size))

    out = b"\x89PNG\r\n\x1a\n"
    out += _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    out += _chunk(b"IDAT", zlib.compress(raw, 9))
    out += _chunk(b"IEND", b"")
    return out


def main() -> int:
    os.makedirs(ICON_DIR, exist_ok=True)
    for s in SIZES:
        path = os.path.join(ICON_DIR, "icon%d.png" % s)
        data = render(s)
        with open(path, "wb") as f:
            f.write(data)
        print("[icons] %s（%d 字节）" % (path, len(data)))

    # ★ 把 icons 挂进 manifest —— **只加 icons / action.default_icon，
    #   绝不碰 `key`**（扩展 ID 必须保持 kek... 不变）。
    mpath = os.path.join(ROOT, "extension", "manifest.json")
    with open(mpath, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    key_before = manifest.get("key")
    manifest["icons"] = {
        "16": "icons/icon16.png",
        "32": "icons/icon32.png",
        "48": "icons/icon48.png",
        "128": "icons/icon128.png",
    }
    action = manifest.setdefault("action", {})
    action["default_icon"] = {
        "16": "icons/icon16.png",
        "32": "icons/icon32.png",
        "48": "icons/icon48.png",
        "128": "icons/icon128.png",
    }
    assert manifest.get("key") == key_before, "manifest 的 key 被动过！"
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("[icons] manifest.json 已挂 icons（key 未变）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
