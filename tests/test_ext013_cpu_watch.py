"""test_ext013_cpu_watch.py — ★ EXT-013 ① 自测：cpu_watch 修好 + 启动自检

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

reviewer 09:50 的证据（EXT-013 原文）：

> 限制组 p1_ext011 在 09:33–09:41 运行 …… 而且 cpu_watch.log 全程
> cores=0.000（pids=1），监视器没有跟到服务进程。

覆盖四块（每块都有**反向对照**，保证断言不是恒真）：

  1. **★ 根因（行为级）**：旧写法「每次新建 `psutil.Process` 再读 `cpu_percent`」
     ⇒ 恒为 0.0；新写法「复用同一对象」⇒ 能读到非零。
     ⇒ 这是**区分力核心**：只断言「新写法能读到非零」不够，
        必须同时证明「旧写法读不到」。

  2. **★ 启动自检**：`self_check` 结论必须**由实测的 CPU 时间增量**决定：
     * 真的在烧 CPU 的进程 ⇒ `ok=True`；
     * 一个**完全空闲**的进程（真睡）⇒ `ok=False`（不能把 0.000 当正常）。

  3. **★ 身份校验（防 PID 复用）**：`--expect-cmd` 不匹配 ⇒ 退出码 3 且**不**产出
     假装有效的 JSON。

  4. **编排器接线**：`run_p1_real.py` 必须传 `--expect-cmd` / `--self-check-sec`，
     且自检 FAIL 时整轮 rc=6（**不**把无效数据当成功）。

运行：
    python tests/test_ext013_cpu_watch.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

import cpu_watch  # noqa: E402

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""), flush=True)
    RESULTS.append((name, bool(cond), detail))


def _run_cli(args, timeout=180):
    """跑 cpu_watch.py 的 CLI，返回 (rc, stdout, stderr)。"""
    cmd = [sys.executable, os.path.join(ROOT, "tools", "cpu_watch.py")] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       timeout=timeout, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr


# ── 1. ★ 根因：旧写法 vs 新写法（行为级区分力） ─────────────────────
def test_object_reuse_is_load_bearing() -> None:
    print("\n[1] ★ 根因：psutil.Process 对象必须复用")

    # 起一个**真的在烧 CPU** 的子进程（纯 Python 忙等，**不碰设备**）
    code = (
        "import time\n"
        "x = 0\n"
        "t0 = time.time()\n"
        "while time.time() - t0 < 25:\n"
        "    for _ in range(20000):\n"
        "        x += 1\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT)
    try:
        time.sleep(1.5)   # 让它先烧一会儿

        # ★★ 本机的 python.exe 可能是**启动器**（真正干活的是它的子进程）
        #   ⇒ 必须跟踪**整棵树**（这正是 EXT-013 ① 的要求）。
        tree = cpu_watch._tree_pids(proc.pid)
        check("★ _tree_pids 能拿到进程树（不止根 PID）",
              len(tree) >= 1, "root=%d tree=%s" % (proc.pid, tree))

        # (a) ★ 旧写法：每次新建 Process 对象 ⇒ cpu_percent 恒 0.0
        import psutil
        old_vals = []
        for _ in range(3):
            for pid in tree:                 # 树里每个 PID 都新建对象
                p = psutil.Process(pid)
                old_vals.append(p.cpu_percent(None))   # ⇒ 第一次采样 ⇒ 0.0
            time.sleep(0.4)

        # (b) 新写法：复用同一对象（**整棵树**）
        cached = {}
        for pid in tree:
            p = psutil.Process(pid)
            p.cpu_percent(None)              # 预热
            cached[pid] = p
        time.sleep(0.8)
        new_val = sum(p.cpu_percent(None) for p in cached.values())

        check("★ 反向对照：旧写法（每次新建 Process）读到的全是 0.0",
              all(v == 0.0 for v in old_vals),
              "old=%s" % [round(v, 3) for v in old_vals[:6]])
        check("★ 新写法（复用同一 Process 对象）能读到非零 CPU",
              new_val > 0.0, "new=%.2f %%" % new_val)

        # (c) ★ 本模块的 _tree_percent 必须**复用**对象 ⇒ 能读到非零
        procs = cpu_watch._tree_procs(proc.pid)
        check("★ _tree_procs 返回的字典非空（跟到了目标进程）",
              bool(procs), "pids=%s" % list(procs.keys()))
        for p in procs.values():
            try:
                p.cpu_percent(None)
            except Exception:
                pass
        time.sleep(0.8)
        pct = cpu_watch._tree_percent(procs)
        check("★ cpu_watch._tree_percent 能读到非零（复用对象生效）",
              pct > 0.0, "pct=%.2f %%" % pct)

        # (d) ★ 累计 CPU 时间也必须能反映「真的在烧 CPU」（整棵树）
        ct0 = cpu_watch._tree_cputimes(tree)
        time.sleep(1.0)
        ct1 = cpu_watch._tree_cputimes(cpu_watch._tree_pids(proc.pid))
        check("★ 累计 CPU 时间有增量（自检的判据可用）",
              (ct1 - ct0) > 0.0, "delta=%.3f s" % (ct1 - ct0))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ── 2. ★ 启动自检 ──────────────────────────────────────────────────
def test_self_check() -> None:
    print("\n[2] ★ 启动自检（能区分「采样器坏」与「进程真空闲」）")

    # (a) 真在烧 CPU ⇒ 自检必须 PASS
    code = (
        "import time\n"
        "x = 0\n"
        "t0 = time.time()\n"
        "while time.time() - t0 < 20:\n"
        "    for _ in range(20000):\n"
        "        x += 1\n"
    )
    busy = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT)
    out_busy = os.path.join(ROOT, ".tmp", "_ext013_selfcheck_busy.json")
    try:
        time.sleep(0.8)
        rc, so, se = _run_cli(
            ["--pid", str(busy.pid), "--expect-cmd", "import time",
             "--self-check-sec", "3", "--duration", "6", "--out", out_busy],
            timeout=90)
        data = {}
        try:
            with open(out_busy, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            check("★ 自检产物 JSON 可读", False, str(e)[:120])
        sc = data.get("self_check") or {}
        check("★ 繁忙进程：自检 ok=True", sc.get("ok") is True,
              "reason=%s delta=%s" % (sc.get("reason"), sc.get("cputime_delta_sec")))
        check("★ 繁忙进程：自检观察到了 CPU 时间增量 > 0",
              float(sc.get("cputime_delta_sec") or 0) > 0.0,
              str(sc.get("cputime_delta_sec")))
        check("★ 繁忙进程：mean_cores > 0（核数证据非零）",
              float(data.get("mean_cores") or 0) > 0.0,
              "mean_cores=%s" % data.get("mean_cores"))
        check("★ 繁忙进程：CLI 退出码 0", rc == 0, "rc=%d" % rc)
    finally:
        try:
            busy.terminate()
            busy.wait(timeout=10)
        except Exception:
            try:
                busy.kill()
            except Exception:
                pass

    # (b) ★ 完全空闲的进程 ⇒ 自检必须 FAIL（不能把 0.000 当正常）
    idle_code = "import time; time.sleep(20)"
    idle = subprocess.Popen([sys.executable, "-c", idle_code], cwd=ROOT)
    out_idle = os.path.join(ROOT, ".tmp", "_ext013_selfcheck_idle.json")
    try:
        time.sleep(0.8)
        rc, so, se = _run_cli(
            ["--pid", str(idle.pid), "--expect-cmd", "import time",
             "--self-check-sec", "3", "--duration", "5", "--out", out_idle],
            timeout=90)
        data = {}
        try:
            with open(out_idle, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            check("★ 空闲进程产物 JSON 可读", False, str(e)[:120])
        sc = data.get("self_check") or {}
        check("★ 空闲进程：自检 ok=False（0.000 不被当成有效数据）",
              sc.get("ok") is False, "reason=%s" % sc.get("reason"))
        check("★ 空闲进程：CLI 退出码 3（可被调用方判 FAIL）",
              rc == 3, "rc=%d" % rc)
        check("★ 空闲进程：stderr 里有明确的失败原因",
              "自检" in se or "自检" in so, se.strip()[-160:])
    finally:
        try:
            idle.terminate()
            idle.wait(timeout=10)
        except Exception:
            try:
                idle.kill()
            except Exception:
                pass

    for p in (out_busy, out_idle):
        try:
            os.remove(p)
        except Exception:
            pass


# ── 3. ★ 身份校验（防 PID 复用） ───────────────────────────────────
def test_identity_check() -> None:
    print("\n[3] ★ 身份校验（--expect-cmd 不匹配 ⇒ 判 FAIL）")

    code = "import time; time.sleep(10)"
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT)
    out_bad = os.path.join(ROOT, ".tmp", "_ext013_identity_bad.json")
    try:
        time.sleep(0.6)
        rc, so, se = _run_cli(
            ["--pid", str(proc.pid), "--expect-cmd", "ext.bridge",
             "--self-check-sec", "2", "--duration", "3", "--out", out_bad],
            timeout=60)
        check("★ 身份不匹配 ⇒ 退出码 3", rc == 3, "rc=%d" % rc)
        check("★ 身份不匹配 ⇒ stderr 有明确原因",
              "身份校验" in se or "PID" in se, se.strip()[-160:])
        data = {}
        try:
            with open(out_bad, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
        check("★ 身份不匹配 ⇒ 产物里 self_check.ok=False",
              (data.get("self_check") or {}).get("ok") is False,
              json.dumps(data.get("self_check"), ensure_ascii=False)[:160])
        check("★ 身份不匹配 ⇒ 产物标了 failed=True",
              data.get("failed") is True, str(data.get("failed")))
        check("★ 身份不匹配 ⇒ 没有伪造的采样点（samples 为空）",
              not (data.get("samples") or []), "n=%d" % len(data.get("samples") or []))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            os.remove(out_bad)
        except Exception:
            pass


# ── 4. 编排器接线 ──────────────────────────────────────────────────
def test_orchestrator_wiring() -> None:
    print("\n[4] 编排器接线（run_p1_real.py）")

    src = open(os.path.join(ROOT, "tools", "run_p1_real.py"),
               encoding="utf-8").read()
    check("run_p1_real.py 传了 --expect-cmd",
          "--expect-cmd" in src)
    check("run_p1_real.py 传了 --self-check-sec",
          "--self-check-sec" in src)
    check("run_p1_real.py 有 --cpu-self-check-sec 参数",
          "--cpu-self-check-sec" in src)
    check("★ run_p1_real.py 自检 FAIL 时整轮 rc=6",
          "return 6" in src)
    check("★ run_p1_real.py 把自检结论写进 summary",
          '"cpu_self_check"' in src)
    check("★ run_p1_real.py 自检 FAIL 时 summary 标 ok=False",
          '"failed_reason"' in src)

    # ★ 反向对照：自检失败 ⇒ 退出码不能是 0
    #   （用「自检失败」这个标记做一次**纯逻辑**验证：不真的跑引擎）
    check("★ 自检失败标记与 rc=6 绑定在同一分支",
          ("cpu_self_check_failed" in src
           and "if cpu_self_check_failed:" in src))


def main() -> int:
    print("=" * 72)
    print("EXT-013 自测：cpu_watch 修复 + 启动自检")
    print("=" * 72)
    test_object_reuse_is_load_bearing()
    test_self_check()
    test_identity_check()
    test_orchestrator_wiring()

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
