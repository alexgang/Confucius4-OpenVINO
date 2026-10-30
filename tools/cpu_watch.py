"""cpu_watch.py — ★ EXT-011 / EXT-013：采集**进程树**的 CPU 占用（核数口径）

## 为什么需要（EXT-011 明文）

> ASR 实测 CPU 7.8 核 → 1 核，RTF 0.644 → 0.530

⇒ 光看 RTF 说不清「是不是真的少用核了」；必须**独立**测出
  桥接服务进程树在同一时刻**实际占了多少核**。

## ★★ EXT-013 ①：启动自检（**这是本轮修掉的真实缺陷**）

reviewer 09:50 的证据：

> 限制组 p1_ext011 在 09:33–09:41 运行 …… 而且 cpu_watch.log 全程
> cores=0.000（pids=1），监视器没有跟到服务进程。

### 根因（实测取证，不是推测）

`psutil` 的 `Process.cpu_percent()` 把「上次采样时刻」记在 **Process 对象**上：

* 每次都 `psutil.Process(pid).cpu_percent(None)` ⇒ 每次都是**第一次采样**
  ⇒ 返回值恒为 **0.0**；
* ⇒ 必须**复用同一个 `Process` 对象**才能拿到真实的百分比。

（EXT-011 那轮跑的就是这个写法 ⇒ 全程 `cores=0.000`。）

### ★ 但「修好采样」**不等于**「测对了」

即使采样代码正确，**目标进程本身**也可能没被跟到
（PID 记错 / PID 被复用 / 进程已退出 / 权限不足）。
⇒ 本工具现在带**启动自检（self-check）**：

1. 采样开始后，`--self-check-sec` 秒内（默认 45 s）持续观察；
2. 用**累计 CPU 时间（cpu_times）的增量**判定「这棵树真的在消耗 CPU」：
   `tree_cputime_sec` 的增量 > 0 ⇒ 机制**工作正常**；
3. 自检窗口结束时若增量仍为 0 ⇒ **判定 FAIL**（而不是把 0.000 默默写进产物）：
   * `self_check.ok = False`
   * 打印**明确的失败原因**（PID 不存在 / 不是 python / 没有子进程 / 空闲）
   * 退出码 **3**（⇒ 调用方 `run_p1_real.py` 能直接判 FAIL）

⇒ 这样「采样器坏了」和「进程真的空闲」就不会再混为一谈。

## 口径

* 采样对象 = **根 PID + 其全部子进程（递归）**（`psutil.children(recursive=True)`）；
* `cpu_percent()` 返回**单核百分比**（100 = 1 核）⇒ **核数 = 百分比 / 100**；
* 同时记录 `cpu_percent`（瞬时）、`tree_cputime_sec`（累计，user+system）、
  `mean_cores`（累计 CPU 秒 ÷ 墙钟秒，**最稳的口径**）、`peak_cores`；
* 子进程会变（引擎可能起/退）⇒ **每轮刷新**对象缓存，但**同一个 pid 复用同一个对象**；
* 采样间隔默认 1.0 s。

## 用法

    # 采一个已知的 PID（前台运行直到 Ctrl-C，或用 --duration）
    python tools\\cpu_watch.py --pid 22504 --duration 600 --out .tmp\\cpu.json

    # 按命令行关键字匹配（拿不到 PID 时的兜底）
    python tools\\cpu_watch.py --match "ext.bridge" --duration 600 --out .tmp\\cpu.json

    # ★ 校验目标 PID 确实是预期的进程（防 PID 复用）
    python tools\\cpu_watch.py --pid 1234 --expect-cmd "ext.bridge" --out .tmp\\cpu.json

## 退出码

* `0` —— 正常结束（或自检通过后被 duration 截断）；
* `2` —— 参数错误；
* `3` —— ★ **启动自检 FAIL**（整段采样期间这棵树没有任何 CPU 时间增量）。

⚠️ 本工具**只读**进程信息，**不**改任何进程、**不**占设备、**不**需要共享锁。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional

try:
    import psutil
except Exception as e:  # pragma: no cover
    print("[cpu-watch] 需要 psutil：%s" % e, file=sys.stderr)
    raise SystemExit(2)


# ── 采样口径常量 ────────────────────────────────────────────────────
#: `cpu_percent()` 的单核百分比 → 核数的换算（100 % = 1 核）
PERCENT_PER_CORE = 100.0

#: 单次采样允许的最大「进程刚出现」预热占比（用于剔除子进程刚起时的假 0）
_NEW_PID_GRACE = 0


def _tree_pids(root_pid: int) -> List[int]:
    """root_pid + 其全部子进程（递归）。**根进程查不到时返回空列表**。"""
    out: List[int] = []
    try:
        p = psutil.Process(root_pid)
    except Exception:
        return out
    out.append(root_pid)
    try:
        for c in p.children(recursive=True):
            out.append(c.pid)
    except Exception:
        pass
    return out


def _match_pids(pattern: str) -> List[int]:
    """按命令行关键字匹配进程（返回 PID 列表）。

    ⚠️ 只认**真正的 python.exe**（`name == 'python.exe'`）——
       否则会把 bash 包装进程（命令行里也含 'ext.bridge'）当成目标
       （EXT-011 那轮实测踩到：匹配到 bash.exe，测出 0 核）。
    """
    hits = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (p.info.get("name") or "").lower() != "python.exe":
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if pattern in cmd:
                hits.append(p.info["pid"])
        except Exception:
            continue
    return hits


def _tree_cputimes(pids: List[int]) -> float:
    """整棵树的累计 CPU 秒数（user + system）。"""
    total = 0.0
    for pid in pids:
        try:
            t = psutil.Process(pid).cpu_times()
            total += float(t.user) + float(t.system)
        except Exception:
            continue
    return total


def _tree_percent(procs: Dict[int, "psutil.Process"]) -> float:
    """整棵树的瞬时 CPU 百分比（单核百分比：100 = 1 核）。

    ⚠️⚠️ **psutil 的 `cpu_percent()` 把上次采样时刻记在 `Process` 对象上**
       ⇒ **必须复用同一个 `Process` 对象**，每次新建对象读到的永远是 0.0。
       （EXT-011 那轮实测踩到过这个坑：`psutil.Process(pid).cpu_percent(None)`
        每次新建 ⇒ 恒为 0.0；改成缓存对象后立刻读到真实值。）

    ⇒ 这里接收**已缓存**的 `Process` 对象字典。
    """
    total = 0.0
    for proc in procs.values():
        try:
            total += proc.cpu_percent(None)
        except Exception:
            continue
    return total


def _tree_procs(root_pid: int) -> Dict[int, "psutil.Process"]:
    """root_pid + 其全部子进程 ⇒ {pid: Process 对象}（**复用**对象，见上）。"""
    out: Dict[int, "psutil.Process"] = {}
    for pid in _tree_pids(root_pid):
        try:
            out[pid] = psutil.Process(pid)
        except Exception:
            continue
    return out


def _describe(pid: int) -> dict:
    """取一个 PID 的可读信息（名字 + 命令行前 200 字），用于报告。"""
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            name = p.name()
            try:
                cmd = " ".join(p.cmdline())
            except Exception:
                cmd = ""
        return {"pid": pid, "name": name, "cmdline": cmd[:200]}
    except Exception as e:
        return {"pid": pid, "name": None, "cmdline": None, "error": str(e)[:120]}


def _check_identity(root_pid: int, expect_cmd: Optional[str]) -> dict:
    """校验根 PID 确实是**预期**的那个进程（防 PID 复用）。

    Returns a dict with keys: ``ok`` / ``reason`` / ``info``。
    """
    info = _describe(root_pid)
    if not info.get("name"):
        return {"ok": False, "reason": "目标 PID %d 不存在（或无权限读取）" % root_pid,
                "info": info}
    if not expect_cmd:
        return {"ok": True, "reason": "未指定 --expect-cmd，跳过身份校验", "info": info}
    cmd = info.get("cmdline") or ""
    if expect_cmd.lower() not in cmd.lower():
        return {"ok": False,
                "reason": ("目标 PID %d 的命令行里没有 %r（可能 PID 被复用）"
                           % (root_pid, expect_cmd)),
                "info": info}
    return {"ok": True, "reason": "身份校验通过", "info": info}


def _write_json(path: str, samples: List[dict], summary: dict) -> None:
    """把采样**增量**写到磁盘（原子替换，避免读到半个文件）。"""
    try:
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        data = dict(summary)
        data["samples"] = samples
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print("[cpu-watch] 落盘失败：%s" % e, file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT 进程树 CPU 占用采集（EXT-011 / EXT-013）")
    ap.add_argument("--pid", type=int, default=None, help="根进程 PID")
    ap.add_argument("--match", default=None,
                    help="按命令行关键字匹配根进程（与 --pid 二选一）")
    ap.add_argument("--expect-cmd", default=None,
                    help="★ 校验目标 PID 的命令行里应包含该子串（防 PID 复用）")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="采样时长（秒）；0 = 一直采到 Ctrl-C")
    ap.add_argument("--interval", type=float, default=1.0, help="采样间隔（秒）")
    ap.add_argument("--self-check-sec", type=float, default=45.0,
                    help="★ 启动自检窗口（秒）：窗口内必须观察到 CPU 时间增量，"
                         "否则判 FAIL（退出码 3）。0 = 关闭自检")
    ap.add_argument("--out", default=None, help="把结果写成 JSON")
    args = ap.parse_args(argv)

    if args.pid is None and not args.match:
        print("[cpu-watch] 需要 --pid 或 --match", file=sys.stderr)
        return 2

    root_pid = args.pid
    if root_pid is None:
        hits = _match_pids(args.match)
        if not hits:
            print("[cpu-watch] 没有匹配 %r 的进程" % args.match, file=sys.stderr)
            return 3
        root_pid = hits[0]
        print("[cpu-watch] 匹配到 PID：%s（取 %d）" % (hits, root_pid))

    # ★ 身份校验（防 PID 复用）
    ident = _check_identity(root_pid, args.expect_cmd)
    print("[cpu-watch] 目标进程：%s（%s）"
          % (ident.get("info", {}).get("name"), ident.get("reason")))
    if not ident.get("ok"):
        print("[cpu-watch] ❌ 身份校验 FAIL：%s" % ident.get("reason"),
              file=sys.stderr)
        if args.out:
            _write_json(args.out, [], {
                "root_pid": root_pid, "match": args.match,
                "expect_cmd": args.expect_cmd,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "wall_sec": 0.0, "tree_cputime_sec": 0.0,
                "mean_cores": 0.0, "peak_cores": 0.0, "n_samples": 0,
                "interval_sec": args.interval,
                "self_check": {"ok": False, "reason": ident.get("reason"),
                               "window_sec": 0.0, "cputime_delta_sec": 0.0},
                "identity": ident,
                "samples": [],
                "failed": True,
                "definition": ("cores = psutil cpu_percent/100（100 % = 1 核）；"
                               "mean_cores = 进程树累计 CPU 秒 / 墙钟秒。"),
            })
        return 3

    samples: List[dict] = []
    t_start = time.time()
    cputimes0 = _tree_cputimes(_tree_pids(root_pid))
    wall0 = time.time()
    peak_cores = 0.0
    # ★★ 自检状态
    self_check_ok = None            # None = 还在自检窗口内
    self_check_delta = 0.0          # 自检窗口内观察到的 CPU 时间增量
    self_check_window = max(0.0, float(args.self_check_sec))

    # ★★ 缓存 `Process` 对象 —— psutil 的 `cpu_percent()` 把上次采样时刻
    #   记在**对象**上 ⇒ 每次新建对象读到的永远是 0.0（EXT-011 那轮踩过）。
    procs = _tree_procs(root_pid)
    for proc in procs.values():
        try:
            proc.cpu_percent(None)      # 预热（丢弃返回值）
        except Exception:
            pass
    time.sleep(min(args.interval, 0.5))
    try:
        while True:
            if not psutil.pid_exists(root_pid):
                print("[cpu-watch] 根进程 %d 已退出 ⇒ 结束采样" % root_pid)
                break
            # 子进程会变（引擎可能起/退）⇒ 每轮刷新一次对象缓存，
            # 但**同一个 pid 复用同一个对象**（否则 cpu_percent 恒 0）
            for pid in _tree_pids(root_pid):
                if pid not in procs:
                    try:
                        np = psutil.Process(pid)
                        np.cpu_percent(None)
                        procs[pid] = np
                    except Exception:
                        pass
            for pid in list(procs.keys()):
                if not psutil.pid_exists(pid):
                    procs.pop(pid, None)
            pct = _tree_percent(procs)
            cores = pct / PERCENT_PER_CORE
            peak_cores = max(peak_cores, cores)
            ct = _tree_cputimes(list(procs.keys()))
            last = {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "elapsed_sec": round(time.time() - t_start, 2),
                "n_pids": len(procs),
                "pids": sorted(procs.keys()),
                "cpu_percent": round(pct, 2),
                "cores": round(cores, 4),
                "tree_cputime_sec": round(ct, 3),
            }
            samples.append(last)
            print("[cpu-watch] %6.1fs  pids=%d  cpu=%7.1f%%  cores=%.3f"
                  % (last["elapsed_sec"], last["n_pids"], pct, cores),
                  flush=True)

            # ★★ 自检：窗口内累计 CPU 时间必须有增量
            if self_check_ok is None and self_check_window > 0:
                self_check_delta = max(self_check_delta,
                                       ct - cputimes0)
                if (time.time() - t_start) >= self_check_window:
                    self_check_ok = self_check_delta > 0.0
                    if self_check_ok:
                        print("[cpu-watch] ✅ 启动自检通过：自检窗口 %.1f s 内"
                              "观测到 CPU 时间增量 %.3f s ⇒ 采样器工作正常"
                              % (self_check_window, self_check_delta))
                    else:
                        print("[cpu-watch] ❌ 启动自检 FAIL：自检窗口 %.1f s 内"
                              "这棵树的 CPU 时间增量为 0 ⇒ 采样器没跟到目标进程"
                              "（或目标真的完全空闲）"
                              % self_check_window, file=sys.stderr)

            # ★★ 增量落盘：进程被 terminate 时（编排器 finally 里就是 terminate）
            #   末尾的写盘**不会执行** ⇒ 数据会全丢（EXT-011 那轮踩到）。
            if args.out:
                _write_json(args.out, samples, {
                    "root_pid": root_pid, "match": args.match,
                    "expect_cmd": args.expect_cmd,
                    "started_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                                time.localtime(wall0)),
                    "wall_sec": round(time.time() - wall0, 3),
                    "tree_cputime_sec": round(
                        _tree_cputimes(list(procs.keys())) - cputimes0, 3),
                    "mean_cores": round(
                        (_tree_cputimes(list(procs.keys())) - cputimes0)
                        / max(1e-6, time.time() - wall0), 4),
                    "peak_cores": round(peak_cores, 4),
                    "n_samples": len(samples),
                    "interval_sec": args.interval,
                    "partial": True,
                    "identity": ident,
                    "self_check": {
                        "ok": self_check_ok,
                        "reason": ("自检窗口内观测到 CPU 时间增量 %.3f s"
                                   % self_check_delta) if self_check_ok
                                  else ("自检窗口 %.1f s 内 CPU 时间增量为 0"
                                        % self_check_window),
                        "window_sec": self_check_window,
                        "cputime_delta_sec": round(self_check_delta, 3),
                    },
                    "definition": ("cores = psutil cpu_percent/100"
                                   "（100 % = 1 核）；mean_cores = 进程树累计 "
                                   "CPU 秒 / 墙钟秒。"),
                })
            if args.duration and (time.time() - t_start) >= args.duration:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("[cpu-watch] 被中断")

    wall = max(1e-6, time.time() - wall0)
    ct_total = _tree_cputimes(_tree_pids(root_pid)) - cputimes0
    # 自检窗口在进程提前退出时可能没走到判定点 ⇒ 这里兜底判一次
    if self_check_ok is None and self_check_window > 0:
        self_check_ok = self_check_delta > 0.0
    summary = {
        "root_pid": root_pid,
        "match": args.match,
        "expect_cmd": args.expect_cmd,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(wall0)),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "wall_sec": round(wall, 3),
        "tree_cputime_sec": round(ct_total, 3),
        # ★ 平均核数（累计 CPU 秒 / 墙钟秒）—— 最稳的口径
        "mean_cores": round(ct_total / wall, 4),
        "peak_cores": round(peak_cores, 4),
        "n_samples": len(samples),
        "interval_sec": args.interval,
        "identity": ident,
        "self_check": {
            "ok": self_check_ok,
            "reason": ("自检窗口内观测到 CPU 时间增量 %.3f s" % self_check_delta)
                      if self_check_ok else
                      ("自检窗口 %.1f s 内 CPU 时间增量为 0 ⇒ 没跟到目标进程"
                       % self_check_window),
            "window_sec": self_check_window,
            "cputime_delta_sec": round(self_check_delta, 3),
        },
        "definition": ("cores = psutil cpu_percent/100（100 % = 1 核）；"
                       "mean_cores = 进程树累计 CPU 秒 / 墙钟秒。"),
        "samples": samples,
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "samples"},
                     ensure_ascii=False, indent=2))
    if args.out:
        _write_json(args.out, samples, summary)
        print("[cpu-watch] 已落盘：%s" % args.out)

    # ★ 自检 FAIL ⇒ 退出码 3（调用方据此判 FAIL，而不是默默接受 0.000）
    if self_check_ok is False:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
