"""run_p1_real.py — EXT-006 P1 实测编排器（**持共享机器锁**）

## 流程

1. 等 `shared/MACHINE_LOCK`（`machine_lock.hold()` ⇒ 排队等待，绝不抢）；
2. **冒烟**：先用一小段音频跑通 ASR → MT → TTS，确认链路真的通
   （`tools/engine_smoke.py`），落盘 `.tmp/p1/smoke.json`；
3. **端到端**：起 `--real` 桥接服务（用 App 自带解释器），跑
   `tools/p1_pipeline.py` 把 SPE 前 5 分钟喂进去，落盘：
   * `.tmp/p1/p1_report.json`（P1 指标）
   * `.tmp/p1/p1_timeline.json`（逐句时间表）
   * `.tmp/p1/dub/*.wav`（每句配音，供 reviewer 回转写）
   * `.tmp/p1/margin.json`（服务端侧余量统计）
4. 关桥接服务，确认**无残留进程**（EXT-005 第 2 点）。

## 为什么要有这个编排器

* 真实引擎**必须**用 App 解释器（openvino / babelvox 只在那里）；
* 桥接服务与流水线客户端是**两个进程**，需要串起来；
* 铁律：整段作业**持一把锁**，且**不抢**别人的锁。

用法：
    python tools\\run_p1_real.py --wav <wav> --target-lang en --port 8765
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

# ★ 缺陷 22：**不再硬编码 App 版本号** —— 按目录实际存在情况解析
#   （实测 2026-10-29 App 升级到 v1.7、v1.6 目录已被删除 ⇒ 硬编码全线失效）
from ext.app_root import resolve_app_root as _resolve_app_root

_APP_ROOT = _resolve_app_root()
if not _APP_ROOT:
    raise RuntimeError(
        "找不到实时字幕 App 的安装目录；可用环境变量 EXT_APP_ROOT 显式指定。")
APP_ROOT = _APP_ROOT
APP_PYTHON = os.path.join(APP_ROOT, "python", "python.exe")
PY = sys.executable


def _run(cmd, **kw):
    print("[p1-run] $ %s" % " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, **kw)


def _pid_alive(pid: int) -> bool:
    """PID 是否存活。

    ★ 与铁律一致：**探测失败一律视为存活**（宁可多等，也不误杀活进程）。
    """
    if pid <= 0:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        pass
    # psutil 不可用 ⇒ 退回 ctypes OpenProcess + GetExitCodeProcess
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            # ERROR_INVALID_PARAMETER(87) ⇒ PID 不存在
            return False
        try:
            code = ctypes.c_ulong()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return True      # 探测失败 ⇒ 视为存活
            return code.value != 0
        finally:
            k.CloseHandle(h)
    except Exception:
        return True              # 探测失败 ⇒ 视为存活


def _single_instance_guard(pid_file: str):
    """单实例守卫。返回 (ok, message)。

    * 若 `pid_file` 里的 PID **仍存活** ⇒ 已有实例在跑 ⇒ (False, 说明)
    * 否则（无文件 / PID 已死）⇒ 写入本次 PID ⇒ (True, 说明)
    """
    me = os.getpid()
    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            old = int((f.read() or "0").strip() or 0)
    except Exception:
        old = 0
    if old and old != me and _pid_alive(old):
        return False, ("已有实例在跑（PID=%d，存活）⇒ 拒绝重复启动" % old)
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(me))
    return True, ("单实例守卫就绪（本次 PID=%d）" % me)


def _request_margin_dump(port: int, token_file: Optional[str] = None,
                         timeout: float = 8.0) -> bool:
    """请服务端**主动**把余量统计写盘（缺陷 14 修复 / 缺陷 15 后的双保险）。

    为什么需要：服务端停服务时收到 SIGTERM ⇒ 进程直接退出 ⇒
    Python 的 `finally` **不会执行** ⇒ `margin.json` 永远不落盘。
    ⇒ 这里走正常的 WebSocket 通道发一条 `dump_margin`，
      服务端收到后立刻写盘（不依赖进程退出路径）。

    ★ 缺陷 15：这条连接**不会**顶替真会话 —— 服务端 `handle_ws` 现在
      遇到已有活跃会话时不再改写 `session_holder["session"]`，
      而 `dump_margin` 落盘读的是 `session_holder["session"]`（= 真会话）
      ⇒ 这条「双保险」路**既能落盘、又不会把真数据清空**
      （实测 .tmp/p1_run6/：「已有活跃会话 ⇒ 本连接不顶替」，
        「余量统计已落盘（19 段）」）。
    """
    try:
        import json as _json
        import websockets
        import asyncio
    except Exception:
        return False

    token = ""
    try:
        if token_file and os.path.isfile(token_file):
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
    except Exception:
        token = ""

    async def _do():
        uri = "ws://127.0.0.1:%d" % port
        async with websockets.connect(
                uri,
                origin="chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib",
                additional_headers={"X-Bridge-Token": token},
                max_size=8 * 1024 * 1024,
                ping_interval=None) as ws:
            await ws.send(_json.dumps({"type": "hello", "role": "p1_dumper",
                                       "token": token}))
            await asyncio.wait_for(ws.recv(), timeout=timeout)  # hello_ack
            await ws.send(_json.dumps({"type": "dump_margin"}))
            try:
                await asyncio.wait_for(ws.recv(), timeout=timeout)
            except Exception:
                pass

    try:
        asyncio.run(_do())
        return True
    except Exception as e:
        print("[p1-run] dump_margin 请求异常：%s" % e, flush=True)
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT P1 真实引擎实测编排器")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--target-lang", default="en")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--out", default=os.path.join(ROOT, ".tmp", "p1"))
    ap.add_argument("--max-sec", type=float, default=None)
    ap.add_argument("--smoke-sec", type=float, default=20.0)
    ap.add_argument("--lock-wait", type=float, default=7200.0)
    ap.add_argument("--skip-smoke", action="store_true")
    args = ap.parse_args(argv)

    # ★★ 单实例守卫（本轮修掉的真实工程缺陷 12）。
    #   实测现象：本脚本被**重复启动**时，会同时起多个实例
    #   （本轮实测过 4 个匹配进程，其中 2 个是独立根实例）⇒
    #   它们抢**同一个端口**、写**同一个输出目录** ⇒
    #   桥接服务起不来（端口占用）或产物互相覆盖 ⇒ P1 实测结论无效。
    #   根因：编排器没有任何「已经在跑」的判据。
    #   修法：写一个 PID 文件（`<out>/orchestrator.pid`），里面记本次 PID；
    #   启动时若发现该文件里的 PID **仍存活**（psutil 复核）⇒
    #   直接退出（rc=5），绝不第二个实例再跑一遍。
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    pid_file = os.path.join(out_dir, "orchestrator.pid")
    _pid_ok, _pid_msg = _single_instance_guard(pid_file)
    if not _pid_ok:
        print("[p1-run] %s ⇒ 退出（不重复跑）" % _pid_msg, flush=True)
        return 5

    summary: dict = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "wav": os.path.abspath(args.wav),
        "target_lang": args.target_lang,
        "out": out_dir,
        "steps": [],
    }

    from machine_lock import hold

    # ★ 整段作业持一把锁
    with hold("EXT-p1-real", wait_timeout=args.lock_wait):
        print("[p1-run] 已取得共享锁", flush=True)

        # ── 1. 冒烟 ──────────────────────────────────────────
        if not args.skip_smoke:
            smoke_out = os.path.join(out_dir, "smoke.json")
            cmd = [APP_PYTHON, os.path.join(ROOT, "tools", "engine_smoke.py"),
                   "--wav", args.wav, "--target-lang", args.target_lang,
                   "--max-sec", str(args.smoke_sec),
                   "--out", smoke_out,
                   "--dump-wav", os.path.join(out_dir, "smoke_dub.wav")]
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(
                [ROOT, os.path.join(ROOT, ".runtime_deps")] +
                ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
            env["PYTHONIOENCODING"] = "utf-8"
            log_path = os.path.join(out_dir, "smoke.log")
            with open(log_path, "w", encoding="utf-8") as lf:
                rc = _run(cmd, cwd=ROOT, stdout=lf,
                          stderr=subprocess.STDOUT, env=env).returncode
            summary["steps"].append({"step": "smoke", "rc": rc,
                                      "log": log_path, "json": smoke_out})
            print("[p1-run] 冒烟 rc=%d（日志：%s）" % (rc, log_path), flush=True)

        # ── 2. 端到端 ────────────────────────────────────────
        margin_out = os.path.join(out_dir, "margin.json")
        bridge_log = os.path.join(out_dir, "bridge.log")
        bridge_cmd = [APP_PYTHON, "-m", "ext.bridge",
                      "--host", "127.0.0.1", "--port", str(args.port),
                      "--delay", str(args.delay),
                      "--real", "--target-lang", args.target_lang,
                      "--margin-out", margin_out]
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [ROOT, os.path.join(ROOT, ".runtime_deps")] +
            ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        env["PYTHONIOENCODING"] = "utf-8"

        bridge = None
        try:
            lf = open(bridge_log, "w", encoding="utf-8")
            bridge = subprocess.Popen(bridge_cmd, cwd=ROOT, stdout=lf,
                                      stderr=subprocess.STDOUT, env=env)
            summary["steps"].append({"step": "bridge_start", "pid": bridge.pid,
                                      "log": bridge_log})
            print("[p1-run] 桥接服务 pid=%d" % bridge.pid, flush=True)

            # 等端口就绪
            import socket
            ready = False
            for _ in range(120):
                if bridge.poll() is not None:
                    break
                with socket.socket() as s:
                    s.settimeout(0.5)
                    if s.connect_ex(("127.0.0.1", args.port)) == 0:
                        ready = True
                        break
                time.sleep(0.5)
            if not ready:
                summary["steps"].append({"step": "bridge_ready", "ok": False,
                                          "rc": bridge.poll()})
                print("[p1-run] ❌ 桥接服务未就绪", flush=True)
                return 1
            summary["steps"].append({"step": "bridge_ready", "ok": True})
            print("[p1-run] 桥接服务已就绪", flush=True)

            # 跑流水线（**不持锁**——外层已持锁，避免二次抢锁死等）
            pipe_cmd = [PY, os.path.join(ROOT, "tools", "p1_pipeline.py"),
                        "--wav", args.wav, "--port", str(args.port),
                        "--delay", str(args.delay),
                        "--target-lang", args.target_lang,
                        "--out", out_dir, "--no-lock"]
            if args.max_sec:
                pipe_cmd += ["--max-sec", str(args.max_sec)]
            pipe_log = os.path.join(out_dir, "pipeline.log")
            with open(pipe_log, "w", encoding="utf-8") as plf:
                rc = _run(pipe_cmd, cwd=ROOT, stdout=plf,
                          stderr=subprocess.STDOUT).returncode
            summary["steps"].append({"step": "pipeline", "rc": rc,
                                      "log": pipe_log})
            print("[p1-run] 流水线 rc=%d（日志：%s）" % (rc, pipe_log), flush=True)
        finally:
            if bridge is not None:
                # ★★ 缺陷 14 修复：停服务**之前**先请服务端把余量统计写盘。
                #   `bridge.terminate()`（SIGTERM）会让进程直接退出 ⇒
                #   Python 的 `finally` 不执行 ⇒ margin.json 永远缺失。
                #   ⇒ 先发一条 `dump_margin`（走正常的 WebSocket 通道），
                #     让服务端主动落盘；再 terminate。
                try:
                    _request_margin_dump(
                        args.port,
                        token_file=os.path.join(ROOT, "bridge_token.txt"))
                except Exception as e:
                    print("[p1-run] 请求余量落盘失败（不影响已落盘产物）：%s" % e,
                          flush=True)
                try:
                    bridge.terminate()
                    bridge.wait(timeout=15)
                except Exception:
                    try:
                        bridge.kill()
                    except Exception:
                        pass
                summary["steps"].append({"step": "bridge_stop",
                                          "returncode": bridge.poll()})
            try:
                lf.close()
            except Exception:
                pass

    summary["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(out_dir, "p1_run_summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
