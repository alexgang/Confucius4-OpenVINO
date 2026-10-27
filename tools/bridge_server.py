"""bridge_server.py — 用 **App 自带解释器** 启动 EXT 桥接服务（EXT-006 P1）

## 为什么需要这个包装脚本

真实引擎依赖 `openvino` / `openvino_genai` / `babelvox` / `transformers`，
这些**只在** `Confucius4_LiveCaption_v1.6/python/` 这个运行时里存在
（普通 venv 里 `import openvino` 直接 ModuleNotFoundError，实测过）。

⇒ 桥接服务在 `--real` 模式下**必须**用那个解释器跑。
   本脚本做两件事：
     1. 检查 App 运行时是否可用（不可用就**明确失败**，不静默回落到回声模式）；
     2. 用 App 解释器重新拉起 `python -m ext.bridge --real ...`。

## 用法

    python tools\\bridge_server.py --real --target-lang zh --port 8765 \\
        --delay 10 --margin-out .tmp\\p1\\margin.json

（用普通 venv 的 python 跑本脚本即可 —— 它只负责转发给 App 解释器。）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.environ.get("EXT_APP_ROOT",
                          r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6")
APP_PYTHON = os.path.join(APP_ROOT, "python", "python.exe")

# ★ 本模块自带的第三方依赖（装在**项目本地目录**，不污染 App 的 site-packages）
#   起因：App 自带运行时里有 openvino / openvino_genai / babelvox / transformers，
#   但**没有 websockets**（实测 ModuleNotFoundError）⇒ 桥接服务起不来。
#   ⛔ 不改 App 的任何文件 ⇒ 用 `--target` 装到本项目 `.runtime_deps/`，
#      启动时通过 PYTHONPATH 注入。
RUNTIME_DEPS = os.path.join(ROOT, ".runtime_deps")


def runtime_available() -> tuple:
    """检查 App 运行时是否可用。

    Returns
    -------
    (ok: bool, detail: str)
    """
    if not os.path.isfile(APP_PYTHON):
        return False, "找不到 App 解释器：%s" % APP_PYTHON
    env = dict(os.environ)
    env["PYTHONPATH"] = RUNTIME_DEPS + os.pathsep + env.get("PYTHONPATH", "")
    try:
        r = subprocess.run(
            [APP_PYTHON, "-c",
             "import openvino, openvino_genai, babelvox, transformers, websockets; "
             "print('OK')"],
            capture_output=True, text=True, timeout=120, env=env)
    except Exception as e:
        return False, "调用 App 解释器失败：%s: %s" % (type(e).__name__, e)
    if r.returncode != 0:
        return False, "App 运行时依赖缺失：%s" % (r.stderr or r.stdout)[-400:]
    return True, r.stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT 桥接服务启动器（真实引擎）")
    ap.add_argument("--real", action="store_true", help="接入真实引擎")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--target-lang", default="en")
    ap.add_argument("--token-file", default="bridge_token.txt")
    ap.add_argument("--margin-out", default=None)
    ap.add_argument("--check-only", action="store_true",
                    help="只检查 App 运行时是否可用，不启动服务")
    ap.add_argument("--log", default=None, help="把服务输出重定向到这个文件")
    args = ap.parse_args(argv)

    ok, detail = runtime_available()
    print("[bridge_server] App 运行时：%s（%s）" % ("可用" if ok else "不可用", detail))
    if args.check_only:
        return 0 if ok else 1
    if not ok:
        print("[bridge_server] ❌ 真实引擎模式无法启动：%s" % detail)
        return 2

    cmd = [APP_PYTHON, "-m", "ext.bridge",
           "--host", args.host, "--port", str(args.port),
           "--delay", str(args.delay), "--token-file", args.token_file]
    if args.real:
        cmd += ["--real", "--target-lang", args.target_lang]
    if args.margin_out:
        cmd += ["--margin-out", args.margin_out]
    print("[bridge_server] 启动：%s" % " ".join(cmd))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, RUNTIME_DEPS] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONIOENCODING"] = "utf-8"

    if args.log:
        os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
        with open(args.log, "w", encoding="utf-8") as lf:
            p = subprocess.Popen(cmd, cwd=ROOT, stdout=lf,
                                 stderr=subprocess.STDOUT, env=env)
            print("[bridge_server] pid=%d，日志：%s" % (p.pid, args.log))
            try:
                rc = p.wait()
            except KeyboardInterrupt:
                p.terminate()
                rc = p.wait(timeout=10)
            return rc
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
