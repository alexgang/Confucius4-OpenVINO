#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ext029_spk_ab.py — ★ EXT-029③ 的**确定性** A/B（旁路开 / 关，各同一段 60 s）

## 为什么浏览器路径**不能**做这个 A/B

实测（2026-11-01 15:20，`.tmp/ext028_029_e2e/20261101_152011_25632/`）：
浏览器自动化下 `tabCapture` 不可用（`Extension has not been invoked for the
current page (see activeTab permission)`）⇒ **两臂都退化成 `getDisplayMedia`**
= **整机系统声音** ⇒ 两臂听到的根本不是同一段音频：

    A_off: ASR='Big mouth and I frequently ans…'   B_on: ASR='Big milestone in our 28'

⇒ 那个「ASR 墙钟差异 6.343%」比较的是**两份不同负载**，不是旁路的代价
⇒ **不能**用来判 EXT-029③。
⇒ EXT-029③ 原文要求「开/关旁路各跑一次**同一段 60 s**」
⇒ 必须喂**逐字节相同的 PCM** ⇒ 本脚本用 WS 直喂
（`tools/p1_pipeline.py` 按 100 ms 帧节拍上行**同一份 WAV 文件**）
⇒ 两臂的**唯一差异**是 `--spk-bypass`。

## 流程

1. 把源 WAV 切成**恰好 N 秒**（16 kHz / 单声道 / PCM16）⇒ `slice.wav`
   （**只切一次** ⇒ 两臂吃的是同一个文件 ⇒ 逐字节相同）；
2. **持共享机器锁**（`tools/machine_lock.hold`；锁存在就**等**，绝不抢）；
3. 两臂各起一个 bridge（真实三引擎 ASR=R2T2 / MT=Hy-MT2 / TTS=Qwen3-TTS）：
   * A 臂 `--no-spk-bypass` ／ B 臂 `--spk-bypass`；
   两臂跑完各读自己的 `margin.json`；
4. 按 EXT-029③ 的口径算差异，落 `summary.json`。

## 判定口径（与 EXT-029③ 原文一致）

* ASR **墙钟**：`margin.json → pipeline.stage_wall_sec.asr`
  （**含等 GPU 锁**；`per_segment[].asr_sec` 只是**纯引擎调用**、不含排队
  ⇒ 拿它判定会**低估**旁路影响 = 假通过）；
* `feed_lag`：服务端逐段实测的「音频到达时刻 − 该句应播时刻」之和；
* 两者差异都 ≤ **5%** ⇒ PASS；并记 `spk_queue_drop` / `spk_worker_busy_ms`。

## 用法

    python tests/smoke/ext029_spk_ab.py --out .tmp/ext029_ab/<ts>
    python tests/smoke/ext029_spk_ab.py --out ... --order B,A   # 交换顺序做对照
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import wave
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

PY = sys.executable                      # 本脚本/喂帧器用的解释器（有 websockets）
SR = 16000                               # 服务端 ASR 采样率

# ★ 与 reviewer 已验收的 60 s 素材互为交叉校验
EXT026_SLICE = os.path.join(ROOT, ".tmp", "ext026_spe_60s.wav")


# ══════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════
def _log(msg: str) -> None:
    print("[ext029-ab] %s" % msg, flush=True)


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        _log("读 JSON 失败：%s（%s）" % (path, e))
        return {}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_evidence(d: str) -> dict:
    """产物证据：文件数 / mtime / 字节数（EXT 铁律：列产物必须给三项）。"""
    out = {"dir": d, "n_files": 0, "total_bytes": 0, "files": []}
    if not d or not os.path.isdir(d):
        return out
    for root, _dirs, names in os.walk(d):
        for n in sorted(names):
            p = os.path.join(root, n)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out["files"].append({
                "name": os.path.relpath(p, d).replace("\\", "/"),
                "bytes": st.st_size,
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                      time.localtime(st.st_mtime)),
            })
            out["n_files"] += 1
            out["total_bytes"] += st.st_size
    return out


def _slice_wav(src: str, dst: str, sec: float) -> dict:
    """切出**恰好** `sec` 秒的 16 kHz / 单声道 / PCM16 WAV。

    ★ 校验格式：服务端 ASR 只吃 16 kHz 单声道 PCM16
      ⇒ 格式不符**直接失败**（不做隐式重采样 ⇒ 避免「悄悄换了音频」）。
    """
    with wave.open(src, "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        fr = w.getframerate()
        n_total = w.getnframes()
        if (nch, sw, fr) != (1, 2, SR):
            raise SystemExit(
                "源 WAV 格式不符（需要 16kHz/单声道/PCM16，实际 %dHz/%dch/%dB）"
                " ⇒ 拒绝隐式重采样：%s" % (fr, nch, sw * 8, src))
        want = int(round(sec * fr))
        if want > n_total:
            raise SystemExit("源 WAV 只有 %.2f s，不足 %.2f s ⇒ 退出"
                             % (n_total / fr, sec))
        w.setpos(0)
        raw = w.readframes(want)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(raw)
    return {
        "src": os.path.abspath(src),
        "src_bytes": os.path.getsize(src),
        "slice": os.path.abspath(dst),
        "slice_bytes": os.path.getsize(dst),
        "slice_sha256": _sha256(dst),
        "sec": round(len(raw) / 2.0 / SR, 4),
        "n_samples": len(raw) // 2,
    }


def _port_ready(port: int, timeout: float = 90.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _pct_diff(a_: Optional[float], b_: Optional[float]) -> Optional[float]:
    if a_ is None or b_ is None or a_ == 0:
        return None
    return round(abs(b_ - a_) / abs(a_) * 100.0, 3)


# ══════════════════════════════════════════════════════════════
# 单臂：起 bridge → 喂同一份 WAV → 收
# ══════════════════════════════════════════════════════════════
def _run_arm(arm: str, *, wav: str, sec: float, port: int, delay: float,
             target_lang: str, out_dir: str, app_python: str,
             spk_bypass: bool) -> dict:
    """跑一臂（旁路开或关），返回该臂的结果摘要。"""
    os.makedirs(out_dir, exist_ok=True)
    margin_out = os.path.join(out_dir, "margin.json")
    bridge_log = os.path.join(out_dir, "bridge.log")
    pipe_log = os.path.join(out_dir, "pipeline.log")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, os.path.join(ROOT, ".runtime_deps")] +
        ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONIOENCODING"] = "utf-8"

    flag = "--spk-bypass" if spk_bypass else "--no-spk-bypass"
    bridge_cmd = [app_python, "-m", "ext.bridge",
                  "--host", "127.0.0.1", "--port", str(port),
                  "--delay", str(delay), "--real",
                  "--target-lang", target_lang,
                  "--margin-out", margin_out, flag]
    _log("%s：起 bridge（%s，port=%d）" % (arm, flag, port))

    rec: dict = {"arm": arm, "spk_bypass": spk_bypass, "flag": flag,
                 "port": port, "out_dir": out_dir,
                 # ★ 本臂**实际喂进去**的音频指纹（事后从磁盘重算，
                 #   不是把入参抄一遍）⇒ 两臂的 sha256 互证「同一段音频」。
                 "wav_path": os.path.abspath(wav),
                 "wav_sha256": _sha256(wav) if os.path.isfile(wav) else None,
                 "wav_bytes": (os.path.getsize(wav)
                               if os.path.isfile(wav) else None)}

    bridge = None
    try:
        with open(bridge_log, "w", encoding="utf-8") as lf:
            bridge = subprocess.Popen(bridge_cmd, cwd=ROOT, stdout=lf,
                                      stderr=subprocess.STDOUT, env=env)
        rec["bridge_pid"] = bridge.pid
        if not _port_ready(port):
            rec["ok"] = False
            rec["error"] = "bridge 端口未就绪"
            rec["bridge_log"] = bridge_log
            return rec
        rec["bridge_ready"] = True

        # ★ 喂帧器：**同一份 WAV 文件**、**同一节拍**、**同一端口协议**
        pipe_cmd = [PY, os.path.join(ROOT, "tools", "p1_pipeline.py"),
                    "--wav", wav, "--port", str(port),
                    "--delay", str(delay), "--target-lang", target_lang,
                    "--out", out_dir, "--no-lock", "--max-sec", str(sec)]
        t0 = time.time()
        with open(pipe_log, "w", encoding="utf-8") as plf:
            rc = subprocess.run(pipe_cmd, cwd=ROOT, stdout=plf,
                                stderr=subprocess.STDOUT).returncode
        rec["pipeline_rc"] = rc
        rec["pipeline_wall_sec"] = round(time.time() - t0, 2)
        rec["pipeline_log"] = pipe_log
        rec["bridge_log"] = bridge_log
        rec["ok"] = (rc == 0)
    finally:
        if bridge is not None:
            try:
                bridge.terminate()
                bridge.wait(timeout=20)
            except Exception:
                try:
                    bridge.kill()
                except Exception:
                    pass
            rec["bridge_returncode"] = bridge.poll()

    rec["margin_json"] = margin_out
    rec["margin_exists"] = os.path.isfile(margin_out)
    rec["evidence"] = {
        "bridge_log": _file_evidence(bridge_log) if os.path.isfile(bridge_log)
        else {"n_files": 0},
        "pipeline_log": _file_evidence(pipe_log) if os.path.isfile(pipe_log)
        else {"n_files": 0},
    }
    return rec


# ══════════════════════════════════════════════════════════════
# 指标口径
# ══════════════════════════════════════════════════════════════
def _wall_clock(m: dict) -> dict:
    """从 margin.json 抽 EXT-029③ 要比的两个量。"""
    segs = m.get("per_segment") or []
    pure = [float(s.get("asr_sec") or 0.0) for s in segs]
    stage_wall = ((m.get("pipeline") or {}).get("stage_wall_sec") or {})
    asr_wall = stage_wall.get("asr")
    metric = ("pipeline.stage_wall_sec.asr（含等 GPU 锁）"
              if asr_wall is not None else
              "per_segment[].asr_sec（纯引擎调用，不含排队）")
    fl = [float(s.get("feed_lag_sec") or 0.0) for s in segs]
    return {
        "n_segments": len(segs),
        "asr_wall_sec": round(float(asr_wall), 4) if asr_wall is not None else None,
        "asr_wall_metric": metric,
        "asr_wall_is_pure_engine": asr_wall is None,
        "asr_pure_engine_sec": round(sum(pure), 4),
        "asr_pure_max_sec": round(max(pure), 4) if pure else None,
        "feed_lag_sum_sec": round(sum(fl), 4),
        "feed_lag_mean_sec": (round(sum(fl) / len(fl), 4) if fl else None),
        "feed_lag_max_sec": round(max(fl), 4) if fl else None,
        "stage_wall_sec": stage_wall,
        "spk_bypass": m.get("spk_bypass") or {},
        "spk_table_rows": len(m.get("spk_table") or []),
        "applied_target_lang": m.get("applied_target_lang"),
    }


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT-029③ 确定性 A/B")
    ap.add_argument("--wav", default=os.path.join(
        os.path.expanduser("~"), "shared", "SPE_0000_0500.wav"))
    ap.add_argument("--sec", type=float, default=60.0)
    ap.add_argument("--out", default=os.path.join(ROOT, ".tmp", "ext029_ab"))
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--target-lang", default="en")
    ap.add_argument("--port-a", type=int, default=8791)
    ap.add_argument("--port-b", type=int, default=8792)
    ap.add_argument("--order", default="A,B",
                    help="两臂的跑序：A,B / B,A（交换顺序可排除顺序效应）")
    ap.add_argument("--lock-wait", type=float, default=7200.0)
    ap.add_argument("--no-lock", action="store_true",
                    help="⚠ 仅用于本机自检；正式跑必须持锁")
    args = ap.parse_args(argv)

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    summary: dict = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool": "tests/smoke/ext029_spk_ab.py",
        "out_dir": out_dir,
        "sec": args.sec,
        "order": args.order,
        "target_lang": args.target_lang,
        "delay_sec": args.delay,
    }

    # ── 1. 切同一段音频（**只切一次**） ────────────────────────
    slice_path = os.path.join(out_dir, "slice_%ds.wav" % int(args.sec))
    try:
        wav_info = _slice_wav(args.wav, slice_path, args.sec)
    except SystemExit as e:
        summary["verdict"] = "FAIL"
        summary["error"] = str(e)
        _dump(summary, out_dir)
        return 1
    wav_info["matches_ext026_slice"] = (
        os.path.isfile(EXT026_SLICE)
        and _sha256(EXT026_SLICE) == wav_info["slice_sha256"])
    if os.path.isfile(EXT026_SLICE):
        wav_info["ext026_slice_sha256"] = _sha256(EXT026_SLICE)
    summary["wav"] = wav_info
    _log("同一段音频：%s（%s s，sha256=%s…，与 EXT-026 已验收切片一致=%s）"
         % (wav_info["slice"], wav_info["sec"],
            wav_info["slice_sha256"][:16],
            wav_info["matches_ext026_slice"]))

    # ── 2. App 解释器（真实三引擎只在那里） ───────────────────
    from ext.app_root import resolve_app_root
    app_root = resolve_app_root()
    if not app_root:
        summary["verdict"] = "FAIL"
        summary["error"] = "找不到 App 安装目录（真实引擎不可用）"
        _dump(summary, out_dir)
        return 1
    app_python = os.path.join(app_root, "python", "python.exe")
    summary["app_root"] = app_root
    summary["app_python"] = app_python

    arms_meta = [
        ("A_off", False, args.port_a, "--no-spk-bypass"),
        ("B_on", True, args.port_b, "--spk-bypass"),
    ]
    by_name = {a[0]: a for a in arms_meta}
    # ★ 口径统一：臂名**只有** "A_off" / "B_on" 两种（`arms_meta` 的键）
    #   —— 别名表只做归一，**绝不**引入第三种写法（上一版就是在这里
    #   把 "A" 映成了 "A_OFF"，与 "A_off" 不匹配 ⇒ KeyError）。
    alias = {"A": "A_off", "B": "B_on",
             "A_OFF": "A_off", "B_ON": "B_on",
             "A_OFF_": "A_off", "B_ON_": "B_on"}
    order = [alias.get(s.strip().upper()) for s in args.order.split(",")
             if s.strip()]
    order = [o for o in order if o]
    if sorted(order) != sorted(by_name.keys()) or len(order) != len(by_name):
        _log("⚠ --order 只接受 A,B / B,A ⇒ 按 A,B 跑")
        order = ["A_off", "B_on"]
    # ★ 加锁**之前**自检：臂名必须都能在 `by_name` 里找到
    #   ⇒ 绝不因为拼写错而白占机器锁（本轮已踩过一次）。
    missing = [o for o in order if o not in by_name]
    if missing:
        raise SystemExit("臂名无法解析：%r（可用：%r）"
                         % (missing, sorted(by_name.keys())))

    from machine_lock import hold

    lock_ctx = (nullcontext() if args.no_lock
                else hold("EXT-029-ab", wait_timeout=args.lock_wait))
    with lock_ctx:
        if not args.no_lock:
            _log("已取得共享机器锁（整段 A/B 持一把锁）")
        results: Dict[str, dict] = {}
        for nm in order:
            name, spk, port, flag = by_name[nm]
            arm_dir = os.path.join(out_dir, name)
            rec = _run_arm(name, wav=slice_path, sec=args.sec, port=port,
                           delay=args.delay, target_lang=args.target_lang,
                           out_dir=arm_dir, app_python=app_python,
                           spk_bypass=spk)
            results[name] = rec
            _log("%s 跑完：rc=%s，耗时 %s s"
                 % (name, rec.get("pipeline_rc"), rec.get("pipeline_wall_sec")))

    summary["arms"] = results

    # ── 3. 指标与判定 ─────────────────────────────────────────
    ma = _read_json(os.path.join(out_dir, "A_off", "margin.json"))
    mb = _read_json(os.path.join(out_dir, "B_on", "margin.json"))
    wa, wb = _wall_clock(ma), _wall_clock(mb)

    asr_diff = _pct_diff(wa.get("asr_wall_sec"), wb.get("asr_wall_sec"))
    feed_diff = _pct_diff(wa.get("feed_lag_sum_sec"), wb.get("feed_lag_sum_sec"))
    pure_diff = _pct_diff(wa.get("asr_pure_engine_sec"),
                          wb.get("asr_pure_engine_sec"))
    spk_b = wb.get("spk_bypass") or {}
    audio_sec_ms = args.sec * 1000.0

    checks = []

    def _ck(name: str, cond, detail: str = "") -> bool:
        checks.append({"name": name, "ok": bool(cond), "detail": detail})
        return bool(cond)

    _ck("两臂都跑完（pipeline rc=0）",
        results.get("A_off", {}).get("pipeline_rc") == 0
        and results.get("B_on", {}).get("pipeline_rc") == 0,
        "A rc=%s / B rc=%s"
        % (results.get("A_off", {}).get("pipeline_rc"),
           results.get("B_on", {}).get("pipeline_rc")))
    _ck("两臂都产出段", (wa.get("n_segments") or 0) > 0
        and (wb.get("n_segments") or 0) > 0,
        "A=%s 段 / B=%s 段" % (wa.get("n_segments"), wb.get("n_segments")))
    sha_a = results.get("A_off", {}).get("wav_sha256")
    sha_b = results.get("B_on", {}).get("wav_sha256")
    _ck("★ 同一段音频（两臂各自实测的 sha256 互证，且等于切片指纹）",
        bool(sha_a) and sha_a == sha_b == wav_info["slice_sha256"],
        "A=%s / B=%s / 切片=%s"
        % ((sha_a or "?")[:16], (sha_b or "?")[:16],
           wav_info["slice_sha256"][:16]))
    _ck("两臂段数一致（同音频 ⇒ 同分段）",
        wa.get("n_segments") == wb.get("n_segments"),
        "A=%s / B=%s" % (wa.get("n_segments"), wb.get("n_segments")))
    _ck("EXT-029③ ASR 墙钟差异 ≤ 5%%（口径：%s）" % wa.get("asr_wall_metric"),
        asr_diff is not None and asr_diff <= 5.0,
        "%s %%（A=%s s / B=%s s）" % (asr_diff, wa.get("asr_wall_sec"),
                                     wb.get("asr_wall_sec")))
    _ck("EXT-029③ feed_lag 差异 ≤ 5%", feed_diff is not None and feed_diff <= 5.0,
        "%s %%（A=%s s / B=%s s）" % (feed_diff, wa.get("feed_lag_sum_sec"),
                                     wb.get("feed_lag_sum_sec")))
    _ck("EXT-029③ summary.json 记了 spk_queue_drop",
        "spk_queue_drop" in spk_b, str(spk_b.get("spk_queue_drop")))
    _ck("EXT-029③ summary.json 记了 spk_worker_busy_ms",
        "spk_worker_busy_ms" in spk_b, str(spk_b.get("spk_worker_busy_ms")))
    _ck("EXT-029① 旁路未反压（worker 忙时 < 音频时长）",
        (spk_b.get("spk_worker_busy_ms") or 0.0) < audio_sec_ms,
        "%s ms < %s ms" % (spk_b.get("spk_worker_busy_ms"), audio_sec_ms))
    _ck("EXT-029④ ASR 额外延迟上界已实测（spk_gpu_lock_held_ms）",
        "spk_gpu_lock_held_ms" in spk_b,
        "%s ms（旁路持 ASR 同一把 device_lock 的总时长）"
        % spk_b.get("spk_gpu_lock_held_ms"))

    summary["ab"] = {
        "A_off": wa, "B_on": wb,
        "asr_wall_diff_pct": asr_diff,
        "asr_pure_engine_diff_pct": pure_diff,
        "feed_lag_diff_pct": feed_diff,
        "asr_wall_metric": wa.get("asr_wall_metric"),
        "spk_bypass_B": spk_b,
        "spk_bypass_A": wa.get("spk_bypass"),
        "checks": checks,
        "n_pass": sum(1 for c in checks if c["ok"]),
        "n_fail": sum(1 for c in checks if not c["ok"]),
    }
    summary["verdict"] = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    summary["evidence"] = {
        "out_dir": _file_evidence(out_dir),
        "A_off": _file_evidence(os.path.join(out_dir, "A_off")),
        "B_on": _file_evidence(os.path.join(out_dir, "B_on")),
    }

    _dump(summary, out_dir)
    _log("判定：%s（PASS %d / FAIL %d）"
         % (summary["verdict"], summary["ab"]["n_pass"], summary["ab"]["n_fail"]))
    for c in checks:
        _log("  [%s] %s —— %s" % ("PASS" if c["ok"] else "FAIL", c["name"],
                                  c["detail"]))
    return 0 if summary["verdict"] == "PASS" else 2


class nullcontext(object):           # noqa: N801（避免额外 import）
    """极简 nullcontext（`--no-lock` 自检用）。"""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _dump(summary: dict, out_dir: str) -> str:
    path = os.path.join(out_dir, "summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    _log("summary 已落盘：%s" % path)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
