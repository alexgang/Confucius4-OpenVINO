"""test_ext012_user_guide.py — ★ EXT-012 自测：用户使用说明 + 一键启动 + popup 状态

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

EXT-012 明文要交付四件事：

  ① `USER_GUIDE.md`（中文）：加载插件 / 启动桥接 / **首次配对（用户不手动复制 token）** /
     网页视频与本地 mp4 怎么配音 / 目标语言·延迟 D·音色·原声音量怎么调 /
     怎么停止 / 常见报错；
  ② 一键启动：桌面快捷方式（pythonw、默认 `--real --pipeline`、启用线程限制、
     日志写到 %LOCALAPPDATA%）、启动后显示状态、互斥时给明确提示；
  ③ popup 显示桥接连接状态 / 当前延迟 / 语速倍率 + 一个「打开说明」链接；
  ④ 说明里写清当前限制（5 分钟滞后增长到约 70 s；tabCapture 生产路径未实测 +
     getDisplayMedia 回退时怎么选）。

本自测覆盖：**交付物存在性 + 关键内容口径 + 可执行性 + 安全口径不放宽**。

运行：
    python tests/test_ext012_user_guide.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""), flush=True)
    RESULTS.append((name, bool(cond), detail))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── ① USER_GUIDE.md：存在 + 覆盖明文要求的每一项 ────────────────────
def test_guide_exists_and_covers() -> None:
    print("\n[1] ★ USER_GUIDE.md：存在 + 覆盖 EXT-012 明文各项")

    path = os.path.join(ROOT, "USER_GUIDE.md")
    check("USER_GUIDE.md 存在于项目根", os.path.isfile(path), path)
    if not os.path.isfile(path):
        return
    s = _read(path)

    check("① 说明了怎么在 Chrome 里加载插件",
          "chrome://extensions" in s and "加载已解压的扩展程序" in s
          and "开发者模式" in s)
    check("① 指明了要选的目录是 live_dub_ext\\extension",
          "live_dub_ext\\extension" in s or "live_dub_ext/extension" in s)
    check("① 说明了怎么启动桥接服务",
          "实时配音桥接" in s and "启动" in s)
    check("① ★ 首次配对：**用户不需要手动复制 token**",
          ("不需要手动复制" in s or "不手动复制" in s)
          and "自动配对" in s)
    check("① 说明了网页视频怎么配音", "网页视频" in s)
    check("① 说明了本地文件（mp4）怎么配音",
          "mp4" in s and "本地" in s)
    check("① 说明了目标语言怎么调", "目标语言" in s)
    check("① 说明了延迟 D 怎么调", "延迟 D" in s or "延迟 D（秒" in s)
    check("① 说明了音色怎么调", "音色" in s)
    check("① 说明了原声音量怎么调", "原声压低" in s)
    check("① 说明了怎么停止", "怎么停止" in s or "停止配音" in s)
    check("① ★ 常见报错含 DRM 黑屏",
          "DRM" in s and "黑屏" in s)
    check("① ★ 常见报错含「桥接没启动」",
          "桥接服务没启动" in s or "自动配对失败" in s)
    check("① ★ 常见报错含「App 正在运行导致互斥」",
          "互斥" in s and ("拒绝启动" in s or "实时字幕 App" in s))

    # ★★ 防回归：说明里**不能写死** App 的版本号（会随 App 升级失效）
    #    ⇒ 必须用 <版本号> 占位 + 说明「自动找版本」。
    import re as _re
    hard_ver = _re.findall(r"Confucius4_LiveCaption_v\d+(?:\.\d+)+", s)
    check("① ★ 说明里没写死 App 版本号（会随升级失效）",
          not hard_ver, str(hard_ver))
    check("① ★ 说明里讲了版本号会变 + 自动适配",
          ("版本号" in s or "版本" in s)
          and ("升级" in s or "自动" in s))
    check("① ★ 给了查看实际目录名的命令",
          "dir C:" in s or "dir " in s)

    check("④ ★ 写清当前限制：5 分钟滞后增长到约 70 s",
          "70" in s and "滞后" in s)
    check("④ ★ 写清 tabCapture 生产路径还没实测",
          "tabCapture" in s and ("还没实测" in s or "没有在真实用户点击的场景下验证过" in s))
    check("④ ★ 写清 getDisplayMedia 回退时会弹「选择要共享的标签页」",
          "选择要共享的标签页" in s)
    check("④ ★ 写清了用户该怎么选（选正在播放的标签页 + 勾上共享音频）",
          "也共享标签页音频" in s)

    check("文档是中文", bool(re.search(r"[\u4e00-\u9fff]", s)))
    check("文档是 UTF-8 且无 BOM",
          not open(path, "rb").read().startswith(b"\xef\xbb\xbf"))


# ── ② 一键启动 ────────────────────────────────────────────────────
def test_launcher() -> None:
    print("\n[2] ★ 一键启动（ext_launcher.py）")

    path = os.path.join(ROOT, "tools", "ext_launcher.py")
    check("tools/ext_launcher.py 存在", os.path.isfile(path))
    if not os.path.isfile(path):
        return
    s = _read(path)

    check("★ 默认启用真实引擎（--real）", '"--real"' in s)
    check("★ 默认启用流水线（--pipeline）", '"--pipeline"' in s)
    check("★ 默认目标语言是 zh", 'DEFAULT_LANG = "zh"' in s)
    check("★ 启用了线程限制（不继承 EXT_THREAD_LIMIT=0）",
          "EXT_THREAD_LIMIT" in s)
    check("★ 日志写到 %LOCALAPPDATA%",
          "LOCALAPPDATA" in s and "LiveDubEXT" in s)
    check("★ 互斥时给出明确提示（中文人话）",
          "互斥" in s and "实时字幕 App" in s)
    check("★ 有 GUI 状态显示（tkinter）",
          "tkinter" in s and "state_var" in s)
    check("★ 支持创建桌面快捷方式",
          "--install-shortcut" in s and "Desktop" in s)
    check("★ 桥接服务用 App 自带解释器",
          "resolve_app_root" in s and "python.exe" in s)

    # AST 可解析
    try:
        ast.parse(s)
        check("★ ext_launcher.py 语法正确（AST 可解析）", True)
    except SyntaxError as e:
        check("★ ext_launcher.py 语法正确（AST 可解析）", False, str(e))

    # ★ 快捷方式创建器**真的能跑**（会写桌面 ⇒ 只测到临时目录）
    #    ⇒ 这里直接测 _make_shortcut 函数本身，输出到 .tmp，不污染桌面。
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import ext_launcher
        tmp_dir = os.path.join(ROOT, ".tmp", "_ext012_shortcut")
        os.makedirs(tmp_dir, exist_ok=True)
        # 用**真实**的 launcher 路径当 args（与 --install-shortcut 的真实入参一致）
        launcher_py = os.path.abspath(os.path.join(ROOT, "tools",
                                                   "ext_launcher.py"))
        out = ext_launcher._make_shortcut(
            tmp_dir, r"C:\Python\pythonw.exe", '"%s"' % launcher_py,
            "实时翻译配音 —— 桥接服务（EXT-012）")
        check("★ _make_shortcut 能生成快捷方式文件", bool(out) and os.path.isfile(out),
              str(out))
        if out and os.path.isfile(out):
            # ★ EXT-017①：`.cmd` 现在按 **GBK（cp936）** 写
            #   （.cmd 默认按 OEM 代码页解读 ⇒ UTF-8 会变乱码）。
            #   ⇒ 读端也要按 GBK 读；同时验证「按 GBK 读得出来、
            #     且按 UTF-8 读**读不出来**」（证明编码确实是 GBK 而非 UTF-8）。
            with open(out, "rb") as f:
                raw = f.read()
            content = raw.decode("gbk", errors="replace")
            check("★ 快捷方式能按 GBK 正确解码（中文不乱码）",
                  "实时翻译配音" in content, content[:60])
            try:
                raw.decode("utf-8")
                utf8_decodable = True
            except UnicodeDecodeError:
                utf8_decodable = False
            check("★ 快捷方式确实是 GBK 编码（不是 UTF-8）", not utf8_decodable,
                  "按 UTF-8 也能解码 ⇒ 可能被误写成 UTF-8")
            check("★ 快捷方式内容含 pythonw 目标", "pythonw.exe" in content)
            # ★ 断言「内容含传入的启动脚本路径」（不是写死某个字符串）
            check("★ 快捷方式内容含启动脚本路径", launcher_py in content,
                  launcher_py)
            check("★ 快捷方式内容含说明文字", "EXT-012" in content)
            # ★ 反向对照：内容里**不该**出现别的东西（防止写死模板）
            check("★ 快捷方式内容与传入 args 一致（不是写死模板）",
                  ('start "" "%s" "%s"' % (r"C:\Python\pythonw.exe",
                                         launcher_py)) in content)
            # ★★ EXT-017①：必须切控制台代码页 + 设 UTF-8 环境变量
            check("★ ★ 快捷方式切了控制台代码页（chcp 65001）",
                  "chcp 65001" in content, content[:200])
            check("★ ★ 快捷方式设了 PYTHONUTF8=1",
                  "set PYTHONUTF8=1" in content)
            check("★ ★ 快捷方式设了 PYTHONIOENCODING=utf-8",
                  "set PYTHONIOENCODING=utf-8" in content)
        # 清理
        try:
            os.remove(out)
        except Exception:
            pass
        try:
            os.rmdir(tmp_dir)
        except Exception:
            pass
    except Exception as e:
        check("★ _make_shortcut 可调用", False, str(e)[:160])


# ── ③ popup 状态显示 + 「打开说明」链接 ─────────────────────────────
def test_popup() -> None:
    print("\n[3] ★ popup：连接状态 / 延迟 / 倍率 / 「打开说明」")

    html = _read(os.path.join(ROOT, "extension", "popup.html"))
    js = _read(os.path.join(ROOT, "extension", "popup.js"))

    check("popup 有连接状态徽章（#conn）", 'id="conn"' in html)
    check("popup 显示当前延迟（#mDelay）", 'id="mDelay"' in html)
    check("popup 显示语速倍率（#mSpeed）", 'id="mSpeed"' in html)
    check("popup 显示滞后（#mLag）", 'id="mLag"' in html)
    check("popup 有「打开说明」按钮", 'id="btnGuide"' in html)
    check("★ popup.js 实现了自动取 token（fetchToken）",
          "fetchToken" in js and "/pair" in js)
    check("★ popup.js 里 token 输入框说明「留空即可」",
          "留空" in html or "自动配对" in html)
    check("★ popup.js 轮询 /status 拿实时状态",
          "/status" in js and "pollPairStatus" in js)
    check("★ popup.js 的「打开说明」指向 USER_GUIDE.md",
          "USER_GUIDE.md" in js)

    # ★ 说明文档必须**在扩展目录里**（否则 chrome.runtime.getURL 打不开）
    check("★ extension/USER_GUIDE.md 存在（popup 能打开）",
          os.path.isfile(os.path.join(ROOT, "extension", "USER_GUIDE.md")))

    # ★ popup.js 的语法（用 node 检查）
    node = shutil_which_node()
    if node:
        r = subprocess.run([node, "--check", os.path.join(ROOT, "extension", "popup.js")],
                           capture_output=True, text=True, timeout=60)
        check("★ popup.js 语法正确（node --check）", r.returncode == 0,
              r.stderr.strip()[-200:])
    else:
        check("★ popup.js 语法正确（node --check）", True, "跳过：node 不可用")


def shutil_which_node() -> str:
    """找一个 node 可执行文件（找不到返回空串）。"""
    import shutil
    return shutil.which("node") or ""


# ── ④ 配对端点：安全口径不放宽 ─────────────────────────────────────
def test_pair_server() -> None:
    print("\n[4] ★ 配对端点：用户免手工复制，但**安全口径不放宽**")

    sys.path.insert(0, ROOT)
    from ext.pair_server import PairServer

    port = 18799
    ps = PairServer(port=port, token_provider=lambda: "SECRET-TOKEN-XYZ",
                    status_provider=lambda: {"has_session": True,
                                            "delay_sec": 10.0,
                                            "lag_sec": 71.2})
    ok, msg = ps.start()
    check("★ 配对端点能启动", ok, msg)
    if not ok:
        return
    try:
        time.sleep(0.4)

        # (a) 带扩展 Origin ⇒ 拿到 token
        req = urllib.request.Request(
            "http://127.0.0.1:%d/pair" % port,
            headers={"Origin": "chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib"})
        body = json.loads(urllib.request.urlopen(req, timeout=8).read().decode())
        check("★ 带扩展 Origin ⇒ 拿到 token（用户不用手工复制）",
              body.get("ok") is True and body.get("token") == "SECRET-TOKEN-XYZ",
              json.dumps(body, ensure_ascii=False)[:120])

        # (b) ★ 无 Origin（普通网页）⇒ 必须被拒
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/pair" % port, timeout=8)
            check("★ 无 Origin 的请求被拒（网页拿不到 token）", False,
                  "居然返回了 200")
        except urllib.error.HTTPError as e:
            check("★ 无 Origin 的请求被拒（网页拿不到 token）", e.code == 403,
                  "HTTP %s" % e.code)

        # (c) ★ 非扩展 Origin ⇒ 必须被拒
        try:
            req2 = urllib.request.Request(
                "http://127.0.0.1:%d/pair" % port,
                headers={"Origin": "https://evil.example.com"})
            urllib.request.urlopen(req2, timeout=8)
            check("★ 非扩展 Origin 被拒", False, "居然返回了 200")
        except urllib.error.HTTPError as e:
            check("★ 非扩展 Origin 被拒", e.code == 403, "HTTP %s" % e.code)

        # (c2) ★★ EXT-017④：**别的**扩展（前缀对、id 不对）⇒ 必须被拒
        #   旧口径 `startswith("chrome-extension://")` 会放行 ⇒ 这里必须 403。
        try:
            req3 = urllib.request.Request(
                "http://127.0.0.1:%d/pair" % port,
                headers={"Origin": "chrome-extension://"
                                   "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"})
            urllib.request.urlopen(req3, timeout=8)
            check("★★ 别的扩展（id 不对）被拒", False, "居然返回了 200")
        except urllib.error.HTTPError as e:
            check("★★ 别的扩展（id 不对）被拒", e.code == 403, "HTTP %s" % e.code)

        # (d) status 端点可用（只读诊断，不含 secret）
        st = json.loads(urllib.request.urlopen(
            "http://127.0.0.1:%d/status" % port, timeout=8).read().decode())
        check("★ /status 返回实时状态（延迟/滞后）",
              st.get("ok") is True
              and st["status"].get("delay_sec") == 10.0
              and st["status"].get("lag_sec") == 71.2,
              json.dumps(st, ensure_ascii=False)[:140])
        check("★ /status 不泄露 token", "SECRET-TOKEN-XYZ" not in json.dumps(st))
    finally:
        ps.stop()


# ── ⑤ bridge 接线 ─────────────────────────────────────────────────
def test_bridge_integration() -> None:
    print("\n[5] ★ bridge 接线（配对端点 + 状态摘要）")

    src = _read(os.path.join(ROOT, "ext", "bridge.py"))

    check("★ bridge 有 --pair-port 参数", "--pair-port" in src)
    check("★ bridge 启动了 PairServer", "PairServer(" in src)
    check("★ bridge 把 token_provider 接到了同一个 TokenStore",
          "token_provider=lambda: (_tokens.token if _tokens else \"\")" in src)
    check("★ bridge 暴露了 _pair_status（给 popup 的状态摘要）",
          "def _pair_status(" in src)
    for field in ("delay_sec", "lag_sec", "speed_time_share", "n_dropped_dub"):
        check("★ _pair_status 含 %s" % field, field in src)
    check("★ config.py 定义了 PAIR_PORT", "PAIR_PORT" in _read(
        os.path.join(ROOT, "ext", "config.py")))

    # ★ 配对端点用的是**同一个** token ⇒ 插件拿到的 token 必须能通过
    #   WebSocket 鉴权（用 TokenStore.verify 验证）
    sys.path.insert(0, ROOT)
    from ext.bridge import TokenStore
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tp = os.path.join(td, "tok.txt")
        ts = TokenStore(tp)
        ts2 = TokenStore(tp)
        check("★ 同一个 token 文件 ⇒ 两个 TokenStore 拿到同一个 token",
              ts.token == ts2.token)
        check("★ TokenStore.verify 能验证自己的 token", ts.verify(ts.token))
        check("★ TokenStore.verify 拒绝错误 token", not ts.verify("wrong"))


def main() -> int:
    print("=" * 72)
    print("EXT-012 自测：用户说明 + 一键启动 + popup 状态 + 自动配对")
    print("=" * 72)
    test_guide_exists_and_covers()
    test_launcher()
    test_popup()
    test_pair_server()
    test_bridge_integration()

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 72)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    if n_fail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f" - {name} — {detail}")
    print("=" * 72)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
