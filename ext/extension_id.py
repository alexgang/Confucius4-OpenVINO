"""extension_id.py — ★ EXT-017④：从 manifest 的 `key` 推导**本插件**的扩展 ID

## 为什么需要（EXT-017 明文）

> ④ 确认 /pair（8766）只响应 Origin 为 `chrome-extension://<本插件 id>` 的请求，
>    其他本地网页拿不到 token。

## 原实现的问题

`ext/pair_server.py` 原来只检查：

```python
origin.startswith("chrome-extension://")
```

⇒ **任何**已安装的 Chrome 扩展都能拿到 token（只要它肯发这个请求）。
这比 EXT-001 的原始口径（`chrome-extension://<本插件 id>`）**放宽了**。

⚠️ 注意 `Origin` 头**不可**被网页 JS 伪造（浏览器自动设置），
所以「普通网页」本来就拿不到 ⇒ EXT-017 关心的其实是
「**别的扩展**能不能拿」以及「本插件 id 到底对不对」。

## 解法

Chrome 扩展的 ID 由 manifest 里的 `key` 字段**确定性地**算出：

    id = 前 128 位（16 字节）of SHA256(DER 编码的公钥)，转成 a–p 的十六进制

⇒ 本模块从 `extension/manifest.json` 的 `key` 现场算出本插件的 id，
   写进 `ext/config.py` 的 `EXTENSION_ID` 常量（也可用环境变量覆盖）。
⇒ `/pair` 与 WebSocket 握手**都**按**精确 id** 校验。

## 铁律

* 只读 `extension/manifest.json`（本模块自己的文件）；
* 算不出 id ⇒ **不静默放宽**：返回 ``None``，调用方按「拒绝」处理；
* 不改任何其他模块的文件。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Optional

#: 项目根（`ext/` 的上一级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: manifest 的路径
MANIFEST_PATH = os.path.join(ROOT, "extension", "manifest.json")

#: Chrome 扩展 id 的字符表（a–p，每个字符 4 bit）
_ALPHA = "abcdefghijklmnop"


def compute_extension_id(manifest_path: str = MANIFEST_PATH) -> Optional[str]:
    """从 manifest 的 `key` 算出扩展 ID。

    Returns
    -------
    str | None
        32 位小写扩展 id；manifest 不存在 / 没有 `key` / key 非法 ⇒ ``None``
        （**不静默放宽**，调用方须按「拒绝」处理）。
    """
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return None
    key = manifest.get("key")
    if not key or not isinstance(key, str):
        return None
    try:
        der = base64.b64decode(key, validate=True)
    except Exception:
        return None
    digest = hashlib.sha256(der).digest()
    # 只取前 16 字节（128 bit）⇒ 每个字符 4 bit ⇒ 32 个字符。
    nibbles = digest[:16]
    return "".join(_ALPHA[b >> 4] + _ALPHA[b & 0x0F] for b in nibbles)


def resolve_extension_id() -> Optional[str]:
    """解析本插件的扩展 id。

    优先级：

    1. 环境变量 ``EXT_EXTENSION_ID``（显式覆盖永远优先，便于测试/CI）；
    2. 从 manifest 的 `key` 现场计算。
    """
    env = os.environ.get("EXT_EXTENSION_ID")
    if env and env.strip():
        return env.strip()
    return compute_extension_id()


def origin_is_this_extension(origin: Optional[str],
                             extension_id: Optional[str] = None) -> bool:
    """Origin 是否是**本插件**？

    * ``extension_id`` 为 ``None`` ⇒ 现场解析（解析不出 ⇒ 一律拒绝）；
    * Origin 必须精确等于 ``chrome-extension://<本插件 id>``。
    """
    if not origin:
        return False
    eid = extension_id if extension_id is not None else resolve_extension_id()
    if not eid:
        # ★ 解析不出本插件 id ⇒ **不静默放宽成 startswith**（那正是要修的漏洞）。
        return False
    return origin.strip() == "chrome-extension://%s" % eid


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps({
        "manifest": MANIFEST_PATH,
        "manifest_exists": os.path.isfile(MANIFEST_PATH),
        "extension_id": resolve_extension_id(),
        "env_override": os.environ.get("EXT_EXTENSION_ID"),
    }, ensure_ascii=False, indent=2))
