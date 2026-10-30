"""pair_server.py — ★ EXT-012：给插件提供**自动配对**（用户不手动复制 token）

## 为什么需要（EXT-012 明文）

> 首次配对（token）怎么做，**用户不需要手动复制 token**
> （由 popup 自动从本机读取，或用一次性配对码）

## 方案：本机 HTTP「配对端点」

桥接服务在 **`127.0.0.1` 的另一个端口**上开一个极小的 HTTP 服务：

| 端点 | 作用 |
|---|---|
| `GET /pair` | 返回配对 token（**仅限扩展**） |
| `GET /status` | 返回桥接状态（是否已连会话、延迟 D、语速倍率、滞后） |

### 安全口径（**不放宽**）

* 只绑定 `127.0.0.1`（外网不可达）；
* **必须**带 `Origin: chrome-extension://` 头才能拿到 token
  ⇒ **网页脚本伪造不了这个头**（浏览器自动设置 Origin，
    `fetch` 的 `Origin` 头**不可**由 JS 覆盖）⇒ 恶意网页拿不到 token；
* token 本身仍要通过 WebSocket 鉴权（`ext.bridge` 的 `TokenStore.verify`），
  ⇒ 这里的端点只是**省掉手工复制**，**不是**新增一条绕过鉴权的路。

⇒ 与原有安全口径一致：token 必须正确 + Origin 必须是 chrome-extension://。

## 端口

默认 `桥接端口 + 1`（8765 ⇒ 8766）。插件的 `host_permissions` 里已有
`http://127.0.0.1/*` ⇒ 覆盖该端口，**不需要**改 manifest 的权限。
"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

DEFAULT_PAIR_PORT = 8766


def _make_handler(token_provider: Callable[[], str],
                  status_provider: Callable[[], dict]):
    """构造请求处理类。

    * `token_provider` —— 返回当前 token 的函数；
    * `status_provider` —— 返回状态字典的函数（可返回空 dict）。
    """

    class Handler(BaseHTTPRequestHandler):
        # ★ 安静一点：BaseHTTPRequestHandler 默认往 stderr 打访问日志，
        #   在 pythonw 下会弹黑窗 ⇒ 覆写掉。
        def log_message(self, fmt, *args):  # noqa: A003
            return

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin") or ""
            return origin.startswith("chrome-extension://")

        def _send_json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass

        def do_GET(self):  # noqa: N802
            path = (self.path or "/").split("?")[0]
            if path == "/pair":
                if not self._origin_ok():
                    # ★ 非扩展来源 ⇒ 明确拒绝（不放宽安全口径）
                    self._send_json(403, {"ok": False,
                                          "error": "只有扩展（Origin: chrome-extension://）"
                                                   "可以读取配对 token"})
                    return
                try:
                    token = token_provider() or ""
                except Exception as e:
                    self._send_json(500, {"ok": False, "error": str(e)[:200]})
                    return
                if not token:
                    self._send_json(404, {"ok": False, "error": "尚未生成 token"})
                    return
                self._send_json(200, {"ok": True, "token": token,
                                      "generated_at": time.strftime(
                                          "%Y-%m-%d %H:%M:%S")})
                return

            if path == "/status":
                # 状态**不需要**扩展身份（只是只读诊断信息，不含 secret）
                try:
                    st = status_provider() or {}
                except Exception as e:
                    st = {"error": str(e)[:200]}
                self._send_json(200, {"ok": True, "status": st})
                return

            if path == "/health":
                self._send_json(200, {"ok": True})
                return

            self._send_json(404, {"ok": False, "error": "not found"})

    return Handler


class PairServer:
    """配对 HTTP 服务（后台线程跑）。"""

    def __init__(self, *, port: int = DEFAULT_PAIR_PORT, host: str = "127.0.0.1",
                 token_provider: Callable[[], str],
                 status_provider: Optional[Callable[[], dict]] = None):
        self.port = port
        self.host = host
        self.token_provider = token_provider
        self.status_provider = status_provider or (lambda: {})
        self._srv: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> tuple[bool, str]:
        try:
            handler = _make_handler(self.token_provider, self.status_provider)
            self._srv = ThreadingHTTPServer((self.host, self.port), handler)
            self._srv.daemon_threads = True
            self._thread = threading.Thread(target=self._srv.serve_forever,
                                            kwargs={"poll_interval": 0.5},
                                            daemon=True)
            self._thread.start()
            return True, "配对端点已启动：http://%s:%d/pair" % (self.host, self.port)
        except Exception as e:
            self._srv = None
            return False, "配对端点启动失败：%s" % e

    def stop(self) -> None:
        if self._srv is not None:
            try:
                self._srv.shutdown()
            except Exception:
                pass
            try:
                self._srv.server_close()
            except Exception:
                pass
            self._srv = None


if __name__ == "__main__":  # pragma: no cover
    p = PairServer(port=int(os.environ.get("EXT_PAIR_PORT", DEFAULT_PAIR_PORT)),
                   token_provider=lambda: "demo-token")
    ok, msg = p.start()
    print(msg)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        p.stop()
