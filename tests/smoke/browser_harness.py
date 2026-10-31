"""
browser_harness.py — 真浏览器**冒烟测试**夹具（本机可用的唯一真浏览器通道）

★ 为什么需要这个文件：
  此前多轮 STATUS 都记着「⛔ 浏览器端人工验收未做（无 playwright / 无 Chrome）」。
  **那个前提是错的** —— 本轮实测发现：
    ① workbuddy 自带 Python 环境（.workbuddy/binaries/python/envs/default）
       **自带 playwright**（import playwright 成功）；
    ② 但 **playwright 自己的 `launch_persistent_context` 会把
       `--load-extension` / `--disable-extensions-except` 这两个参数
       **过滤掉或改写**（实测：传了也不生效 ⇒ service_workers 为空
       ⇒ 扩展页 ERR_BLOCKED_BY_CLIENT）。
    ③ **直接起 msedge.exe 再用 `connect_over_cdp` 连** ⇒ **完全正常**：
       扩展 SW 起来、扩展页可访问、popup 渲染正确。
  ⇒ 所以本夹具走「自己起进程 + CDP 连接」这条路，不依赖 playwright 的启动器。

★ 实测通过的证据（2026-10-31）：
    service_workers: ['chrome-extension://ndcp.../background.rollup.js',
                      'chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib/sw.js']
    POPUP URL: chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib/popup.html
    TITLE: 实时翻译配音

## 定位（EXT-022 已定② —— 重要）

本夹具（连同 `pw_accept1-4`）**只是冒烟测试**：

* 它们证明「扩展装得上、popup 渲染正常、设置能存能填、hello 能到服务端」；
* 它们**不能**替代**浏览器端人工验收** ——
  英文网页视频 + 本地 mp4，各 1 分钟、带**用户手势**的 tabCapture，
  **由用户亲自做**（EXT-022 已定② 明确：不要用 Playwright 去替代）。
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request

# 仓库根：tests/smoke/browser_harness.py → 上溯两级
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
EXT_DIR = os.path.join(_ROOT, "extension")
EXT_ID = "kekgmfkijphpfndbbpakjaokamkeooib"   # 由 manifest.key 现场算，与 9 份探针一致

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str:
    for p in EDGE_PATHS:
        if os.path.exists(p):
            return p
    raise RuntimeError("找不到 Edge/Chrome 可执行文件")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http_json(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class BrowserSession:
    """起一个真浏览器（带本插件），用 CDP 连上，提供取扩展页的能力。"""

    def __init__(self, profile: str, extra_args=None, headless: bool = False):
        self.profile = profile
        self.extra_args = list(extra_args or [])
        self.headless = headless
        self.proc = None
        self.browser = None
        self.port = None
        self.ctx = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright()
        self._pw_cm = self._pw.start()
        browser = find_browser()
        self.port = free_port()
        if os.path.exists(self.profile):
            shutil.rmtree(self.profile, ignore_errors=True)
        os.makedirs(self.profile, exist_ok=True)
        cmd = [
            browser,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile}",
            f"--disable-extensions-except={EXT_DIR}",
            f"--load-extension={EXT_DIR}",
            "--no-first-run", "--no-default-browser-check", "--no-sandbox",
            "--autoplay-policy=no-user-gesture-required",
        ] + self.extra_args + ["about:blank"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        base = f"http://127.0.0.1:{self.port}"
        for _ in range(40):
            try:
                _http_json(base + "/json/version")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("CDP 未就绪")
        self.browser = self._pw_cm.chromium.connect_over_cdp(base)
        self.ctx = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        return self

    def __exit__(self, *exc):
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self._pw_cm:
                self._pw_cm.stop()
        except Exception:
            pass
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except Exception:
                self.proc.kill()
        return False

    # ── 便捷方法 ──────────────────────────────────────────────
    def sw_urls(self):
        return [w.url for w in self.ctx.service_workers]

    def ext_sw_alive(self) -> bool:
        return any(EXT_ID in u for u in self.sw_urls())

    def open_ext_page(self, page_name: str):
        """打开扩展内的一页并返回 Playwright Page 对象。"""
        pg = self.ctx.new_page()
        pg.goto(f"chrome-extension://{EXT_ID}/{page_name}")
        return pg

    def new_page(self):
        return self.ctx.new_page()
