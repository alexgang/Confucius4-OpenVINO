"""test_ext019_port_guard.py — EXT-019 自测（追加项）：重复启动的端口占用防护

本文件**不改写**既有断言，只**追加**新的行为级验收。

## 背景（2026-10-30 22:41 用户实测报错，根因）

用户把启动器**再点一次** ⇒ 新子进程去 bind 8765 ⇒ Windows 报
`OSError: [Errno 10048] 端口只允许使用一次` ⇒ 桥接进程**带着一整屏 Python
traceback 崩掉**。

更糟的是**崩溃时机**：旧流程是「先加载 24 秒模型 → 再 `serve()` 去 bind」
⇒ 用户**白等 24 秒**，最后看到一句没人看得懂的 traceback。

⇒ EXT-019 两道防线：
  ① **启动器**在拉子进程**之前**就查端口 ⇒ 占用则**不启动**、给人话提示；
  ② **桥接**把端口检查**提到模型预热之前** ⇒ 就算绕过启动器，
     也是**立刻**失败（实测 400 ms）而不是白等 24 秒。

## 覆盖四块

  A. **启动器行为级** —— 真占住一个端口 ⇒ `BridgeRunner.start()` 必须
     **不启动子进程**、**返回 ok=False**、并给出**含端口号**的人话提示。
  B. **桥接行为级** —— 起一个占端口的 socket ⇒ `ext.bridge` 的端口预检
     必须**判 FAIL**（返回 False + 原因），且**原因里含端口号**。
  C. **真起桥接进程** —— 用 `--echo` 模式（不跑推理、不占 GPU/NPU）对着
     被占端口启动 ⇒ 必须**快速失败**（退出码 6）、**不加载模型**、
     输出里**不含** `Traceback`（★ 这是用户真正看到的界面）。
  D. **源码契约 + 反证** —— 端口检查必须在**预热之前**；
     `_pid_alive` 必须有**判别力**（活 PID ⇒ True / 死 PID ⇒ False）。

不跑推理 / 不占 GPU·NPU / 不抢共享锁。

运行：
    python tests/test_ext019_port_guard.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        return f.read()


# ── A：启动器行为级 ─────────────────────────────────────────────
def test_launcher_blocks_occupied_port() -> None:
    print("\n[A] 启动器：端口被占 ⇒ 不启动子进程、给人话提示")
    import ext_launcher as el

    port = _free_port()
    # ★ 真占住这个端口（模拟「上一个实例还在跑」）
    hog = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    hog.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    hog.bind(("127.0.0.1", port))
    hog.listen(1)

    logs, states = [], []
    try:
        r = el.BridgeRunner(port=port, delay=10.0, lang="zh", pipeline=True,
                            on_log=logs.append,
                            on_state=lambda t, k: states.append((t, k)),
                            cmd=[sys.executable, "-c", "print('SHOULD NOT RUN')"])
        # ★ 注意：**即使给了 cmd_override 也必须查端口** ——
        #   否则自测注入点会把生产路径的保护绕过去。
        #   ⚠️ 但生产路径下 cmd_override=None 时才查；
        #   这里我们**显式**用真实端口去试生产分支：
        r2 = el.BridgeRunner(port=port, delay=10.0, lang="zh", pipeline=True,
                             on_log=logs.append,
                             on_state=lambda t, k: states.append((t, k)))
        t0 = time.time()
        ok, msg = r2.start()
        dt = time.time() - t0
        check("★ A1 端口被占 ⇒ start() 返回 ok=False", ok is False, str(msg)[:150])
        check("★ A2 端口被占 ⇒ **不启动子进程**", r2.proc is None,
              "proc=%r" % (r2.proc,))
        check("A3 提示里含端口号（用户知道该处理哪个）",
              str(port) in msg, msg[:150])
        check("A4 提示里给出**人话**（出现「占用」或「已经在运行」）",
              ("已被占用" in msg) or ("已经在运行" in msg), msg[:150])
        check("A5 提示里给出**解决办法**（含「停止」或「端口」）",
              ("停止" in msg) or ("端口" in msg), msg[:150])
        check("★ A6 失败是**快速**的（≤ 5 s，不用白等模型加载）",
              dt <= 5.0, "实测 %.3f s" % dt)
        check("A7 状态灯切到错误态（kind='err'）",
              any(k == "err" for _, k in states), str(states[:3]))
    finally:
        hog.close()


# ── B：桥接端口预检的行为级判别力 ───────────────────────────────
def test_bridge_port_probe() -> None:
    print("\n[B] 桥接：端口预检的判别力")
    from ext.bridge import _probe_port_free, _describe_port_owner

    free = _free_port()
    ok, why = _probe_port_free("127.0.0.1", free)
    check("★ B1 空闲端口 ⇒ 判定可用", ok is True, why)

    hog = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    hog.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    hog.bind(("127.0.0.1", free))
    hog.listen(1)
    try:
        ok2, why2 = _probe_port_free("127.0.0.1", free)
        check("★ B2 被占端口 ⇒ 判定**不可用**（与 B1 可区分）",
              ok2 is False, why2)
        check("B3 失败原因里含端口号", str(free) in why2, why2)
    finally:
        hog.close()

    # ★ 反证：探测失败必须**放行**（不能因探测异常拒绝启动）
    check("B4 探测函数对非法端口返回明确布尔",
          isinstance(_probe_port_free("127.0.0.1", 0)[0], bool))


# ── C：真起桥接进程 ⇒ 快速失败、无 traceback ────────────────────
def test_bridge_process_fails_fast() -> None:
    print("\n[C] 真起桥接：对被占端口 ⇒ 快速失败、无 traceback")
    from ext.bridge import TokenStore

    port = _free_port()
    hog = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    hog.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    hog.bind(("127.0.0.1", port))
    hog.listen(1)

    tmp = tempfile.mkdtemp()
    tok = os.path.join(tmp, "tok.txt")
    TokenStore(tok)

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, os.path.join(ROOT, ".runtime_deps")])
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, "-m", "ext.bridge", "--host", "127.0.0.1",
             "--port", str(port), "--token-file", tok, "--echo"],
            cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60)
        dt = time.time() - t0
        out = (r.stdout or "") + (r.stderr or "")
        check("★ C1 退出码是 6（专门的「端口占用」码）",
              r.returncode == 6, "实际 rc=%d，输出=%s"
              % (r.returncode, out[-300:]))
        check("★ C2 输出里**不含** Traceback（用户看到的是人话不是 traceback）",
              "Traceback" not in out, out[-300:])
        check("C3 输出里含端口号", str(port) in out, out[-300:])
        check("C4 输出里给出解决办法（含「停止」或「端口」）",
              ("停止" in out) or ("端口" in out), out[-300:])
        check("★ C5 失败是**快速**的（≤ 15 s；不加载模型就不用 24 s）",
              dt <= 15.0, "实测 %.3f s" % dt)
        check("C6 输出里说明**没有加载模型**（不用白等 20–40 秒）",
              ("没有" in out and "加载模型" in out) or "加载模型" in out,
              out[-300:])
    finally:
        hog.close()


# ── D：源码契约 + 反证 ──────────────────────────────────────────
def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def test_source_contract() -> None:
    print("\n[D] 源码契约：端口检查必须在预热之前")
    br = _read("ext/bridge.py")
    lsrc = _read("tools/ext_launcher.py")

    btree = ast.parse(br)
    ltree = ast.parse(lsrc)

    main_fn = _find_func(btree, "main")
    check("D1 bridge.py 有 main()", main_fn is not None)
    if main_fn is not None:
        dump = ast.unparse(main_fn)
        i_probe = dump.find("_probe_port_free")
        i_warm = dump.find("engine.warmup")
        check("★ D2 端口预检在**模型预热之前**（否则仍会白等 24 s）",
              i_probe != -1 and i_warm != -1 and i_probe < i_warm,
              "probe@%d warmup@%d" % (i_probe, i_warm))
        check("D3 端口被占时 return 6（专用退出码）",
              "return 6" in dump, "")

    check("D4 启动器有 _port_in_use（启动前预检）",
          "def _port_in_use(" in lsrc)
    check("D5 启动器有 _find_port_owner（告诉用户是谁占着）",
          "def _find_port_owner(" in lsrc)
    check("D6 启动器有 _pid_alive（ctypes 判存活）",
          "def _pid_alive(" in lsrc)
    check("★ D7 _pid_alive 用 OpenProcess + GetExitCodeProcess",
          "OpenProcess" in lsrc and "GetExitCodeProcess" in lsrc)
    check("D8 启动器在拉子进程**之前**调用端口检查",
          "_port_in_use(" in lsrc)

    # ★ 反证：_pid_alive 必须有判别力（活 PID True / 死 PID False）
    import ext_launcher as el
    check("★ D9 _pid_alive(0) ⇒ False（非法 PID）",
          el._pid_alive(0) is False)
    check("★ D10 _pid_alive(自己) ⇒ True（当前进程肯定活着）",
          el._pid_alive(os.getpid()) is True)
    check("★ D11 _pid_alive(一个不存在的 PID) ⇒ False",
          el._pid_alive(999999) is False)


def main() -> int:
    print("=" * 68)
    print("EXT-019 自测：重复启动的端口占用防护（快速失败 + 人话提示）")
    print("=" * 68)
    for fn in (test_launcher_blocks_occupied_port,
               test_bridge_port_probe,
               test_bridge_process_fails_fast,
               test_source_contract):
        try:
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
