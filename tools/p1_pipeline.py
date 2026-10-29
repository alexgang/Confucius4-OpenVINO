"""p1_pipeline.py — EXT-006 P1 端到端流水线实测（**真实引擎**）

## 它做什么

把一段 16 kHz 单声道 PCM（默认 SPE 前 5 分钟）按**插件同款的帧格式**喂给
正在运行的 `--real` 桥接服务，收集服务端下发的配音任务，然后：

1. 把每句配音落成 **24 kHz wav**（供 reviewer 回转写）；
2. 落一份**时间表**（每句的 t_start / t_end / src / tgt / 变速 / 顺延 / 余量）；
3. 计算 EXT-001 P1 条款要求的指标：
   * 每句同步误差 P50/P95（目标 |误差| ≤ 300 ms）；
   * 变速比例分布；
   * 顺延句数；
   * 每句「原声结束 → TTS 就绪」的余量分布；
   * 余量 < 0 的句数；
   * 5 分钟结束时的累计滞后。

## 与插件的关系（口径一致性）

插件上行帧：`{type:'pcm', seq, sample_index, pcm(base64 PCM16 16k mono)}`，
帧长 20–100 ms。**本工具逐字节复刻这个格式** ⇒
服务端看到的输入与插件完全一致 ⇒ 服务端产出的段划分与时间表可直接用于插件。

## 用法

    # 1) 先起桥接服务（真实引擎，必须用 App 自带解释器）：
    python tools\\bridge_server.py --real --target-lang en --port 8765 \
        --delay 10 --margin-out .tmp\\p1\\margin.json --log .tmp\\p1\\bridge.log
    # 2) 再跑本工具：
    python tools\\p1_pipeline.py --wav C:\\Users\\Trekker-PTL\\shared\\SPE_0000_0500.wav \
        --port 8765 --out .tmp\\p1 --target-lang en

⚠️ **必须持共享机器锁**：本工具默认走 `tools.machine_lock.hold()`；
   锁被别的模块持有时**排队等待**，绝不抢占。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
import wave
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import numpy as np  # noqa: E402

from ext import config as C  # noqa: E402

# 帧长（与插件一致：20–100 ms）
FRAME_MS = 60
# P1 验收目标（EXT-001）
SYNC_ERR_TARGET_MS = 300.0


# ── 输入 ────────────────────────────────────────────────────────────
def read_wav_16k_mono(path: str):
    """读 16 kHz 单声道 PCM16 wav → (float32, sample_rate)。"""
    with wave.open(path, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("只支持 PCM16（sampwidth=%d）" % sw)
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if nch > 1:
        a = a.reshape(-1, nch).mean(axis=1)
    return a, sr


def frame_payload(audio: np.ndarray, frame_ms: int = FRAME_MS):
    """切成插件同款的帧 → [(seq, sample_index, pcm_bytes), ...]。"""
    n = int(frame_ms * C.SAMPLE_RATE / 1000)
    out = []
    seq = 0
    sidx = 0
    for i in range(0, audio.shape[0], n):
        chunk = audio[i:i + n]
        if chunk.shape[0] == 0:
            break
        pcm = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        out.append((seq, sidx, pcm))
        seq += 1
        sidx += chunk.shape[0]
    return out


# ── 客户端 ──────────────────────────────────────────────────────────
async def _run_client(*, port: int, token: str, frames, delay_sec: float,
                      recv_timeout: float, realtime: bool = True,
                      frame_ms: int = FRAME_MS, expect_segments: int = 0,
                      flush: bool = True,
                      stats_timeout: float = 300.0,
                      dump_timeout: float = 60.0):
    """连桥接服务、喂帧、收配音任务。返回 (tasks, hello_ack, t_capture)。

    ★ `realtime=True`（P1 验收必须）：按**墙钟节拍**逐帧上行，模拟插件真实行为。
      为什么必须这样：EXT-006 要测「原声结束 → TTS 就绪」的余量与**累计滞后**。
      若一次性把 5 分钟音频灌进去，服务端会在几秒内处理完 ⇒ 余量恒为巨大正值、
      滞后恒为 0 ⇒ 指标**失去意义**（拿到的是假数据）。
      只有按真实速率喂，服务端才会像线上一样「边收边做」，滞后才会显现。

    ★ `stats_timeout` / `dump_timeout`（缺陷 16）：服务端消息循环是**单线程串行**的，
      一帧 `pcm` 就要跑完 ASR→MT→TTS（真实引擎单段 30~60 s）。
      ⇒ 收尾时客户端发的 `stats` / `dump_margin` 会排在积压队列后面，
      服务端要清完积压才看得到 ⇒ 必须**真的等回包**（事件），
      不能 sleep 一下就当拿到（详见函数体内「缺陷 16」注释）。
      默认 300 s / 60 s：够跑完最后几段的推理。
    """
    import websockets

    tasks: List[dict] = []
    hello: dict = {}
    timing: dict = {}
    uri = "ws://127.0.0.1:%d" % port

    async with websockets.connect(
            uri,
            # ★ Origin 必须是 chrome-extension://（EXT-001 安全口径）
            origin="chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib",
            additional_headers={"X-Bridge-Token": token},
            max_size=32 * 1024 * 1024,
            ping_interval=None) as ws:
        await ws.send(json.dumps({"type": "hello", "role": "p1_probe",
                                  "token": token}))
        # 先收 hello_ack
        raw = await asyncio.wait_for(ws.recv(), timeout=30)
        hello = json.loads(raw)

        margin_dumped = asyncio.Event()
        stats_got = asyncio.Event()

        async def _recv_loop():
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("type") == "tts":
                    tasks.append(msg)
                elif msg.get("type") == "margin_dumped":
                    # ★ 服务端确认余量统计已写盘（缺陷 14）
                    margin_dumped.set()
                elif msg.get("type") == "stats":
                    # ★ 必须把 marker 放在**展开之后**，否则内层的
                    #   `type: "stats"` 会把 `"_stats"` 覆盖掉
                    #   （`{"type": "_stats", **msg}` ⇒ msg 的 type 赢）
                    #   ⇒ 下游 `get("type") == "_stats"` 永远不成立
                    #   ⇒ EXT-006 的核心验收量（margin 余量统计）**全部丢失**，
                    #   且收尾循环永远等不到 stats 只能干等 recv_timeout。
                    tasks.append({**msg, "type": "_stats"})
                    stats_got.set()

        rx = asyncio.ensure_future(_recv_loop())
        t_capture = time.perf_counter()
        # ★★ EXT-008 第 2 点：**逐帧**记录「本该发的时刻」与「实际发的时刻」
        #   ⇒ 直接定位「是谁阻塞了喂帧」：
        #     * 若某一帧的 `late_sec` 突然跳到几十秒 ⇒ 服务端在那一刻
        #       **没在读 socket**（服务端消息循环是单线程串行的，
        #       跑 ASR→MT→TTS 时不读 ⇒ 客户端 `ws.send()` 被**反压**卡住）
        #       ⇒ **阻塞方 = 服务端推理（背压）**，不是客户端、也不是网络。
        #     * 若所有帧都均匀落后 ⇒ 客户端自己的问题。
        frame_timing: List[dict] = []
        try:
            # ── 喂帧 ─────────────────────────────────────────────
            for seq, sidx, pcm in frames:
                target = t_capture + (seq + 1) * frame_ms / 1000.0
                if realtime:
                    now = time.perf_counter()
                    if target > now:
                        await asyncio.sleep(target - now)
                t_before_send = time.perf_counter()
                await ws.send(json.dumps({
                    "type": "pcm", "seq": seq, "sample_index": sidx,
                    "pcm": base64.b64encode(pcm).decode("ascii"),
                }))
                t_after_send = time.perf_counter()
                # late_sec = 实际开始发这一帧的时刻 − 本该发的时刻
                # send_dur_sec = `ws.send()` 本身阻塞了多久（**反压的直接证据**）
                frame_timing.append({
                    "seq": seq,
                    "late_sec": round(t_before_send - target, 4),
                    "send_dur_sec": round(t_after_send - t_before_send, 4),
                })
            t_sent = time.perf_counter()

            # ── 收尾：让服务端把尾段也处理掉 ────────────────────
            #   流式服务默认把最后一段留在缓冲区里（等后续音频）。
            #   P1 要求「配音 wav 和时间表落盘」⇒ 尾段也必须出，
            #   否则时间表缺最后一段，reviewer 回转写时对不上。
            if flush:
                await ws.send(json.dumps({"type": "flush"}))
                print("[p1] 已发 flush（请求服务端处理尾段）", flush=True)

            # ── 等所有段落地 ────────────────────────────────────
            #   判据：收到的 tts 段数达到预期（服务端分段数由同一套
            #   plan_segments 决定）⇒ 立即收尾；否则等到超时。
            #   ★ 不能只看「收到过 stats」：stats 只有在客户端主动
            #     请求时才回，而请求时的服务端可能还在处理中。
            deadline = time.time() + recv_timeout
            last_n = -1
            stable_rounds = 0
            while time.time() < deadline:
                await asyncio.sleep(0.5)
                n_seg = sum(1 for t in tasks if t.get("type") == "tts")
                if expect_segments and n_seg >= expect_segments:
                    break
                # 连续两轮没有新增 ⇒ 认为处理完了（兜底）
                if n_seg == last_n:
                    stable_rounds += 1
                    if stable_rounds >= 4 and n_seg > 0:
                        break
                else:
                    stable_rounds = 0
                last_n = n_seg
            # 主动要一份 stats（服务端回包里带 margin 汇总）
            # ★★ 缺陷 16（本轮实测抓到的真缺陷）：**不能 sleep 一下就当拿到 stats**。
            #   服务端的消息循环是**单线程串行**的：每来一帧 `pcm`，
            #   它要 `await asyncio.to_thread(session.on_pcm_frame, msg)`
            #   跑完 ASR→MT→TTS（真实引擎单段要 30~60 s！）才回到循环读下一条消息。
            #   ⇒ 客户端在收尾时发的 `stats` / `dump_margin` 会**排在积压队列后面**，
            #     服务端要先把积压的 pcm 全处理完才会看到它们。
            #   ⇒ 实测（.tmp/p1_run6/）：客户端 sleep 1.5 s 后就发 dump_margin 并断开
            #     ⇒ 报「⚠️ 未收到 margin_dumped 确认」
            #     ⇒ 报告里 `bridge_stats: null`、`report.margin: null`
            #     ⇒ 最后是**编排器另开一条连接**才把 margin.json 落盘
            #       （靠那条「新连接」侥幸成功，不是正常路径）。
            #   修法：**真的等 stats 回来**（事件），拿到 stats 说明服务端
            #     已经把积压处理完、回到了消息循环 ⇒ 随后的 dump_margin
            #     才**立刻**被处理 ⇒ margin_dumped 确认能及时到达。
            await ws.send(json.dumps({"type": "stats"}))
            try:
                await asyncio.wait_for(stats_got.wait(), timeout=stats_timeout)
            except Exception:
                print("[p1] ⚠️ 未收到 stats 回包（服务端积压未清空？）",
                      flush=True)
            # ★★ 缺陷 14 修复：让服务端**主动把余量统计写盘**。
            #   服务端的 `finally` 落盘路径在 SIGTERM 下**不会执行**
            #   （编排器停服务用 terminate ⇒ 进程直接死 ⇒ finally 跳过）
            #   ⇒ margin.json 永远缺失 ⇒ EXT-006 要求的
            #   「余量分布 / 余量<0 句数 / 累计滞后」全部拿不到
            #   （实测 p1_run4：pipeline rc=0、19 个 wav 都在，
            #     但 margin.json 缺失、报告 `bridge_stats: null`）。
            #   ⇒ 客户端在断开前发一条 `dump_margin`，服务端立刻写盘。
            await ws.send(json.dumps({"type": "dump_margin"}))
            # ★ 等服务端**确认**落盘（服务端回 `margin_dumped`），
            #   不能只 sleep 一下就断开 —— 服务端此刻可能还在处理
            #   最后一段推理，连接一断消息就丢了 ⇒ margin.json 又缺失。
            try:
                await asyncio.wait_for(margin_dumped.wait(),
                                       timeout=dump_timeout)
            except Exception:
                print("[p1] ⚠️ 未收到 margin_dumped 确认"
                      "（margin.json 可能缺失）", flush=True)
            t_done = time.perf_counter()
            # ★ EXT-008 第 2 点：喂帧耗时与音频时长**分开报**，
            #   并算「喂帧倍速」⇒ 直接暴露「被反压拖慢到 0.5 倍速」这类问题。
            audio_sec = len(frames) * frame_ms / 1000.0
            feed_sec = t_sent - t_capture
            # ── 逐帧时序 → 谁阻塞了喂帧 ──────────────────────
            late = [f["late_sec"] for f in frame_timing]
            sdur = [f["send_dur_sec"] for f in frame_timing]
            n_blocked = sum(1 for v in sdur if v > 1.0)
            timing = {
                "feed_sec": feed_sec,
                "drain_sec": t_done - t_sent,
                "total_sec": t_done - t_capture,
                # 音频本身的时长（按帧长算，不依赖文件）
                "audio_sec": round(audio_sec, 3),
                # ★ 喂帧倍速：>1 = 比实时快；<1 = 比实时慢（被反压拖慢）
                "feed_speed_x": round(audio_sec / feed_sec, 4)
                if feed_sec > 1e-9 else None,
                # ★ 喂帧超出音频时长的部分（= 被拖慢的绝对量）
                "feed_overrun_sec": round(feed_sec - audio_sec, 3),
                # ★★ 阻塞方定位（EXT-008 第 2 点的直接证据）
                "frame_timing_summary": {
                    "n_frames": len(frame_timing),
                    # `send_dur_sec` = `ws.send()` 本身阻塞的时长
                    #   ⇒ **服务端背压**的直接证据（客户端写不进去）
                    "send_dur_total_sec": round(sum(sdur), 3),
                    "send_dur_max_sec": round(max(sdur), 3) if sdur else 0.0,
                    "n_frames_send_blocked_gt_1s": n_blocked,
                    "send_blocked_frames_ratio": (round(n_blocked / len(sdur), 4)
                                                  if sdur else None),
                    # `late_sec` = 实际发这一帧的时刻 − 本该发的时刻
                    "late_max_sec": round(max(late), 3) if late else 0.0,
                    "late_final_sec": round(late[-1], 3) if late else 0.0,
                    "interpretation": (
                        "n_frames_send_blocked_gt_1s > 0 ⇒ 客户端的 ws.send() "
                        "被**服务端背压**卡住 ⇒ 阻塞方 = **服务端推理**"
                        "（消息循环单线程串行，跑 ASR→MT→TTS 时不读 socket）。"
                        "若该值为 0 而 late_sec 仍大 ⇒ 阻塞在客户端自身。"),
                },
                # t0 的定义（EXT-008 明确要求写清）
                "t0_definition": (
                    "t0 = 服务端 Session 创建时刻（time.perf_counter()），"
                    "即第一条 PCM 帧被服务端接收前的会话起点；"
                    "客户端 t_capture = 连接建立后开始喂帧的时刻，"
                    "两者不同源 ⇒ 客户端的墙钟不能直接与服务端的 t0 相减，"
                    "所有服务端侧时刻都以 t0 为基准。"),
            }
            print("[p1] 喂帧 %.1f s（音频 %.1f s，倍速 %.3f×），收尾 %.1f s，共 %d 段"
                  % (timing["feed_sec"], timing["audio_sec"],
                     (timing["feed_speed_x"] or 0.0), timing["drain_sec"],
                     sum(1 for t in tasks if t.get("type") == "tts")),
                  flush=True)
            print("[p1] 喂帧阻塞诊断：%d/%d 帧的 send() 被卡 >1s（合计 %.1f s）"
                  % (n_blocked, len(sdur), sum(sdur)), flush=True)
        finally:
            rx.cancel()
            try:
                await rx
            except BaseException:
                # ★ 必须捕获 BaseException，不能只捕 Exception：
                #   `asyncio.CancelledError` 在 Python 3.8+ 继承自 **BaseException**
                #   （不是 Exception）⇒ `except Exception` **捕不到它**
                #   ⇒ 取消接收协程后 `await rx` 抛出的 CancelledError 会
                #   **穿透出 _run_client**，把整个 P1 流水线在**最后一步**打崩
                #   ⇒ 已经算好的配音 wav / 时间表 / 指标**全部拿不到**
                #   （本轮用桩引擎自测实测复现：连接以 1011 收尾、进程 traceback）。
                pass
    return tasks, hello, t_capture, timing


# ── 指标 ────────────────────────────────────────────────────────────
def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def compute_metrics(tasks: List[dict], *, delay_sec: float,
                    margin_summary: Optional[dict]) -> dict:
    """算 EXT-001 P1 条款要求的指标。

    ★ 同步误差口径（EXT-001 P1 原文）：
        「每句同步误差（**实际播放起点** − 原声起点 + D，P50/P95，
          目标 |误差| ≤ 300 ms）」

      插件把第 N 句配音排在 `t0 + t_start + D`（EXT-001 A 节）⇒
      计划播放起点 = `t0 + t_start + D`。
      但配音**必须先就绪**才能播 ⇒
          实际播放起点 = max(计划播放起点, TTS 就绪时刻)
      ⇒ 同步误差 = 实际播放起点 − 计划播放起点
                = max(0, TTS 就绪时刻 − (t0 + t_start + D))
                = max(0, −deadline_margin_sec)

      ★ 旧实现用 `defer_sec`（顺延量）当同步误差 —— 那是**时长适配**的
        另一个量（语音放不进窗口），与「实际播放起点」无关 ⇒ 口径错了。
        本轮改为上面的定义，并**同时**保留顺延量作为独立指标。

    ★★ EXT-008 第 1 点：**「累计滞后」口径修正**。
      客户端自己再算一遍「末句滞后」与「滞后增长斜率」
      （与服务端 `summarize_margins()` 同口径），⇒ 两边可交叉核对。
    """
    segs = [t for t in tasks if t.get("type") == "tts"]
    per_seg = []
    sync_errs = []
    rates = []
    n_defer = 0
    n_no_tts = 0

    for t in segs:
        fit = t.get("fit") or {}
        rate = float(fit.get("rate", 1.0) or 1.0)
        defer = float(fit.get("defer_sec", 0.0) or 0.0)
        if defer > 0:
            n_defer += 1
        rates.append(rate)
        if not t.get("pcm24k"):
            n_no_tts += 1

        # 同步误差 = max(0, −排程截止余量)
        #   deadline_margin_sec 由服务端算出：
        #     = (t0 + t_start + D) − TTS 就绪时刻
        #   ⇒ 负数 = 配音**赶不上**自己的播放时刻 ⇒ 播放会晚 = 同步误差。
        dm = t.get("deadline_margin_sec")
        if dm is None:
            err_ms = 0.0
        else:
            err_ms = max(0.0, -float(dm)) * 1000.0
        sync_errs.append(err_ms)

        per_seg.append({
            "id": t.get("id"),
            "t_start": t.get("t_start"),
            "t_end": t.get("t_end"),
            "src": t.get("src"),
            "tgt": t.get("tgt"),
            "spk": t.get("spk"),
            "voice": t.get("voice"),
            "rate": rate,
            "defer_sec": defer,
            "extend_sec": fit.get("extend_sec"),
            "feasible": fit.get("feasible"),
            "deadline_margin_sec": dm,
            "sync_err_ms": round(err_ms, 3),
            # ★ EXT-009：自适应加速的逐段字段
            #   `speed` = 最终倍率（时长适配 × 自适应加速，封顶 1.30×）
            #   `adapt_speed` = 自适应加速那一层（1.0 ~ 1.30）
            #   `lag_est_sec` = 服务端估计的滞后
            #   `stretch_sec` = WSOLA 变速耗时
            "speed": t.get("speed"),
            "adapt_speed": (t.get("adapt") or {}).get("speed"),
            "adapt_reason": (t.get("adapt") or {}).get("reason"),
            "lag_est_sec": t.get("lag_est_sec"),
            "stretch_sec": t.get("stretch_sec"),
            "defer_total_sec": t.get("defer_total_sec"),
            "pcm_bytes": (len(base64.b64decode(t["pcm24k"]))
                          if t.get("pcm24k") else 0),
        })

    s = sorted(sync_errs)
    rs = sorted(rates)
    out = {
        "n_segments": len(segs),
        "n_without_tts": n_no_tts,
        "n_deferred": n_defer,
        "sync_err_ms": {
            "target": SYNC_ERR_TARGET_MS,
            "definition": "max(0, TTS就绪时刻 − (t0 + t_start + D)) × 1000",
            "p50": _pct(s, 0.50),
            "p95": _pct(s, 0.95),
            "max": (s[-1] if s else None),
            "mean": (sum(sync_errs) / len(sync_errs)) if sync_errs else None,
            "n_over_target": sum(1 for v in sync_errs if v > SYNC_ERR_TARGET_MS),
        },
        "rate_distribution": {
            "p50": _pct(rs, 0.50),
            "p95": _pct(rs, 0.95),
            "max": (rs[-1] if rs else None),
            "min": (rs[0] if rs else None),
            "histogram": {
                "1.00": sum(1 for r in rates if r <= 1.001),
                "1.00-1.25": sum(1 for r in rates if 1.001 < r <= 1.25),
                ">1.25": sum(1 for r in rates if r > 1.25),
            },
        },
    }
    # ★★ EXT-008 第 1 点：客户端自算「末句滞后 + 滞后增长斜率」
    #   （与服务端同口径 ⇒ 可交叉核对；**不再**有「余量求和」量）。
    out["lag"] = compute_lag_metrics(per_seg)
    if margin_summary:
        out["margin"] = margin_summary
    return out, per_seg


def compute_lag_metrics(per_seg: List[dict]) -> dict:
    """★ EXT-008 第 1 点：**修正后的滞后口径**。

    旧口径（`cumulative_lag_sec`）= 22 段余量**求和** ⇒ 数值随段数线性放大，
    **没有物理含义** ⇒ EXT-008 要求删除。

    新口径（两个**有物理含义**的量）：
      1. `last_segment_lag_sec` = 末句 `max(0, −排程余量)`
         （末句「TTS 就绪时刻 − 它应播的时刻」）；
      2. `lag_growth_slope_sec_per_sec` = 对 `(t_start, 排程余量)`
         **线性拟合**的斜率（负数 = 滞后随时间在累积）。
    """
    pairs = [(float(p.get("t_start") or 0.0),
              float(p.get("deadline_margin_sec")))
             for p in per_seg if p.get("deadline_margin_sec") is not None]
    if not pairs:
        return {"n_fit_points": 0,
                "last_segment_lag_sec": None,
                "max_lag_sec": None,
                "lag_growth_slope_sec_per_sec": None,
                "lag_growth_intercept_sec": None,
                "lag_growth_r2": None}
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        slope, intercept = 0.0, my
        r2 = 0.0
    else:
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        intercept = my - slope * mx
        ss_tot = sum((y - my) ** 2 for y in ys)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
        r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    return {
        "n_fit_points": n,
        "last_segment_lag_sec": round(max(0.0, -ys[-1]), 4),
        "max_lag_sec": round(max(0.0, -min(ys)), 4),
        "lag_growth_slope_sec_per_sec": round(slope, 6),
        "lag_growth_intercept_sec": round(intercept, 4),
        "lag_growth_r2": round(r2, 6),
        "definition": ("末句滞后 = max(0, −末句排程余量)；"
                       "滞后增长斜率 = 对 (t_start, 排程余量) 线性拟合的斜率"
                       "（负数 = 滞后随时间累积）。"
                       "⚠️ 不再有「余量求和」量（EXT-008 判定无物理含义，已删除）。"),
    }


# ── 落盘 ────────────────────────────────────────────────────────────
def write_dub_wavs(tasks: List[dict], out_dir: str) -> List[dict]:
    """每句配音落一个 24 kHz wav（供 reviewer 回转写）。"""
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for t in tasks:
        if t.get("type") != "tts" or not t.get("pcm24k"):
            continue
        pcm = base64.b64decode(t["pcm24k"])
        seg_id = str(t.get("id") or "seg")
        path = os.path.join(out_dir, "%s.wav" % seg_id)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        made.append({"id": seg_id, "path": path, "bytes": len(pcm),
                     "speech_sec": round(len(pcm) / 2.0 / 24000.0, 3),
                     "t_start": t.get("t_start"), "t_end": t.get("t_end")})
    return made


def pick_accelerated_segments(tasks: List[dict], wavs: List[dict],
                              *, lo: float = 1.20, hi: float = 1.30,
                              n: int = 3) -> List[dict]:
    """★ EXT-009 验收：挑出 1.2–1.3× 的配音单独落盘，供 reviewer 抽听。

    EXT-009 原文：
    > 挑 3 段 1.2–1.3× 的配音落盘，供用户抽听，确认**不变调、可懂**。

    ⇒ 这里只做「挑 + 拷贝」，**不做任何质量判定**
      （质量判定由 reviewer 用 MiniMax 回转写，不自己调用 MiniMax）。

    Returns
    -------
    list of dict
        每项含 `id` / `path` / `speed` / `adapt_speed` / `lag_est_sec`
        / `speech_sec` / `tgt`。
    """
    by_id = {w["id"]: w for w in wavs}
    picks = []
    for t in tasks:
        if t.get("type") != "tts" or not t.get("pcm24k"):
            continue
        sp = float(t.get("speed", 1.0) or 1.0)
        if not (lo - 1e-6 <= sp <= hi + 1e-6):
            continue
        w = by_id.get(str(t.get("id") or ""))
        if not w:
            continue
        picks.append({
            "id": str(t.get("id")),
            "path": w["path"],
            "speed": round(sp, 4),
            "adapt_speed": round(float(t.get("adapt", {}).get("speed", 1.0)
                                       or 1.0), 4),
            "lag_est_sec": t.get("lag_est_sec"),
            "speech_sec": w.get("speech_sec"),
            "t_start": t.get("t_start"),
            "tgt": t.get("tgt"),
        })
    # 取倍率最高的前 n 段（最接近 1.30× ⇒ 变调风险最高 ⇒ 最值得抽听）
    picks.sort(key=lambda d: -float(d["speed"]))
    return picks[:n]


def copy_accelerated_wavs(picks: List[dict], out_dir: str) -> List[dict]:
    """把挑出的加速段配音拷到独立目录（方便 reviewer 直接找）。"""
    import shutil
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for p in picks:
        dst = os.path.join(out_dir, "%s_x%.2f.wav" % (p["id"], p["speed"]))
        try:
            shutil.copyfile(p["path"], dst)
        except Exception:
            continue
        made.append({**p, "picked_path": dst,
                     "bytes": os.path.getsize(dst)
                     if os.path.isfile(dst) else None})
    return made


def expected_segment_count(audio, sample_rate: int = 16000) -> int:
    """算**服务端会吐出几段**（客户端 `expect_segments` 用）。

    ★ 与服务端 `ext/bridge.py` 的 `Session.flush()` **同一口径**：
      服务端 flush 有「尾部不足 1.0 s ⇒ 丢弃」的规则
      ⇒ 客户端也必须把**尾部不足 1 s 的残留段**从预期里去掉，
      否则 `expect_segments` 比服务端实际产出多 1 ⇒ 收尾永远等不到
      ⇒ 白等兜底超时，且报告里的段数与实际不符 ⇒ 指标失真。

    （这是本轮实测抓到的缺陷 13，见 STATUS §5.8.2。）
    """
    from ext.segmenter import plan_segments
    segs = plan_segments(audio)
    if not segs:
        return 0
    tail_len = (segs[-1][1] - segs[-1][0]) / float(sample_rate)
    if tail_len >= 1.0:
        return len(segs)
    return max(0, len(segs) - 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT P1 端到端流水线实测（真实引擎）")
    ap.add_argument("--wav", required=True, help="16 kHz 单声道 PCM16 wav")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--target-lang", default="en")
    ap.add_argument("--token-file", default="bridge_token.txt")
    ap.add_argument("--out", default=os.path.join(ROOT, ".tmp", "p1"))
    ap.add_argument("--max-sec", type=float, default=None,
                    help="只用音频前 N 秒（默认全量）")
    ap.add_argument("--recv-timeout", type=float, default=180.0)
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--lock-wait", type=float, default=5400.0)
    ap.add_argument("--fast", action="store_true",
                    help="不按真实速率喂帧（离线快灌）。⚠️ 只供调试；"
                         "P1 验收必须用默认的实时模式，否则余量/滞后指标失真")
    args = ap.parse_args(argv)

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    report: dict = {
        "ok": False,
        "wav": os.path.abspath(args.wav),
        "target_lang": args.target_lang,
        "delay_sec": args.delay,
        "port": args.port,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    token_path = args.token_file
    if not os.path.isabs(token_path):
        token_path = os.path.join(ROOT, token_path)
    if not os.path.isfile(token_path):
        print("[p1] ❌ 找不到 token 文件：%s" % token_path)
        report["error"] = "token 文件不存在"
        _dump(os.path.join(out_dir, "p1_report.json"), report)
        return 2
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    audio, sr = read_wav_16k_mono(args.wav)
    if sr != C.SAMPLE_RATE:
        print("[p1] ❌ 期望 %d Hz，实际 %d" % (C.SAMPLE_RATE, sr))
        report["error"] = "采样率不符"
        _dump(os.path.join(out_dir, "p1_report.json"), report)
        return 2
    if args.max_sec:
        audio = audio[:int(args.max_sec * C.SAMPLE_RATE)]
    frames = frame_payload(audio)
    report["audio_sec"] = round(audio.shape[0] / C.SAMPLE_RATE, 3)
    report["n_frames"] = len(frames)
    print("[p1] 音频 %.2f s → %d 帧（%d ms/帧）"
          % (report["audio_sec"], len(frames), FRAME_MS))

    # ★ 预期段数：用**与服务端同一套**断句逻辑算 ⇒ 收尾时能立刻判断
    #   「服务端是否已处理完全部段」，不必干等 recv_timeout。
    #   （服务端按 min=12s / max=20s + VAD 静音切；尾段由 flush 触发）
    #
    # ⚠️★ 本轮实测抓到的口径错位（缺陷 13）：
    #   `plan_segments()` 会把**尾部不足 1 s 的静音**也算成一段
    #   （例：16 s 音频 = 15 s 语音 + 1 s 静音 ⇒ plan_segments 给 2 段，
    #   第二段只有 0.8 s 的纯静音尾巴）；
    #   但服务端 `Session.flush()` 有一条「尾部不足 1.0 s ⇒ 丢弃」的规则
    #   （见 ext/bridge.py 的 flush()）⇒ 服务端只会吐出 1 段。
    #   ⇒ 客户端 `expect_segments=2` 而服务端只给 1 段 ⇒ 收尾循环
    #     **永远等不到预期段数**，只能靠「连续 4 轮无新增」的兜底超时退出
    #     ⇒ 每轮实测**白等**（5 分钟音频 ⇒ 多等 2 s），
    #     而且报告里的 `expected_segments` 会与实际段数不符 ⇒ **指标失真**。
    #   ⇒ 修法：见 `expected_segment_count()`（与服务端 flush 同一条规则）。
    expected_segs = expected_segment_count(audio, 16000)
    report["expected_segments"] = expected_segs
    print("[p1] 预期段数（与服务端同一套断句，且与服务端同样丢弃 <1s 尾段）：%d"
          % expected_segs)

    # ★ 持共享机器锁（铁律）
    #   `--no-lock` 只用于「外层编排器已经持锁」的场景
    #   （run_p1_real.py 持锁跑整段作业，流水线是它的一个子步骤 ⇒
    #     若流水线再抢一次锁 ⇒ 同进程二次抢锁 ⇒ 死等）。
    from machine_lock import hold

    realtime = not args.fast
    if args.no_lock:
        tasks, hello, t_capture, timing = asyncio.run(_run_client(
            port=args.port, token=token, frames=frames,
            delay_sec=args.delay, recv_timeout=args.recv_timeout,
            realtime=realtime, expect_segments=expected_segs))
    else:
        lock_ctx = hold("EXT-p1-pipeline", wait_timeout=args.lock_wait)
        try:
            with lock_ctx:
                print("[p1] 已取得共享锁")
                tasks, hello, t_capture, timing = asyncio.run(_run_client(
                    port=args.port, token=token, frames=frames,
                    delay_sec=args.delay, recv_timeout=args.recv_timeout,
                    realtime=realtime, expect_segments=expected_segs))
        except Exception as e:
            report["error"] = "%s: %s" % (type(e).__name__, e)
            print("[p1] ❌ 失败：%s" % e)
            _dump(os.path.join(out_dir, "p1_report.json"), report)
            return 1

    seg_tasks = [t for t in tasks if t.get("type") == "tts"]
    stats_msgs = [t for t in tasks if t.get("type") == "_stats"]
    margin_summary = (stats_msgs[-1].get("margin") if stats_msgs else None)
    margin_source = ("stats" if margin_summary else None)
    # ★ EXT-009：自适应加速统计（滞后曲线 / 各倍率时间占比 / 丢句数）
    #   优先从 stats 回包拿；拿不到就从磁盘的 margin.json 读回。
    adaptive_stats = (stats_msgs[-1].get("adaptive_speed")
                      if stats_msgs else None)
    adaptive_source = ("stats" if adaptive_stats else None)
    # ★★ 兜底：stats 没到（例如服务端还在积压、客户端提前断开）时，
    #   服务端**可能已经把 margin.json 写盘了** ⇒ 从磁盘读回来，
    #   避免 EXT-006 的三项核心验收量在报告里是 null。
    #   （实测 p1_run6：报告 bridge_stats=null / margin=null，
    #     但 margin.json 里有 19 段真数据。）
    if not margin_summary or not adaptive_stats:
        _mjson = os.path.join(out_dir, "margin.json")
        if os.path.isfile(_mjson):
            try:
                with open(_mjson, "r", encoding="utf-8") as f:
                    _d = json.load(f)
                _ms = _d.get("margin_summary") or {}
                if not margin_summary and _ms.get("n_segments"):
                    margin_summary = _ms
                    margin_source = "margin.json"
                _ad = _d.get("adaptive_speed") or {}
                if not adaptive_stats and _ad.get("n_segments"):
                    adaptive_stats = _ad
                    adaptive_source = "margin.json"
            except Exception:
                pass

    metrics, per_seg = compute_metrics(seg_tasks, delay_sec=args.delay,
                                       margin_summary=margin_summary)
    wavs = write_dub_wavs(seg_tasks, os.path.join(out_dir, "dub"))
    # ★ EXT-009 验收：挑 3 段 1.2–1.3× 的配音单独落盘（供 reviewer 抽听）
    acc_picks = pick_accelerated_segments(seg_tasks, wavs)
    acc_made = copy_accelerated_wavs(acc_picks, os.path.join(out_dir, "accel"))

    report.update({
        "ok": True,
        "hello_ack": hello,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": metrics,
        "n_dub_wavs": len(wavs),
        "dub_wavs": wavs,
        # ★ EXT-009 验收：加速段清单（1.2–1.3×）
        "accelerated_segments": acc_made,
        "n_accelerated_segments": len(acc_made),
        "per_segment": per_seg,
        "bridge_stats": (stats_msgs[-1] if stats_msgs else None),
        # ★ margin_summary 的来源（"stats" = 收到 stats 回包；
        #   "margin.json" = 从磁盘兜底读回；None = 都没有 ⇒ 真拿不到）
        "margin_source": margin_source,
        # ★ EXT-009 验收：自适应加速统计（滞后曲线 + 倍率占比 + 丢句）
        "adaptive_speed": adaptive_stats,
        "adaptive_source": adaptive_source,
        # ★ 喂帧 / 收尾两段耗时分开记（缺陷 16）：
        #   `feed_sec` ≈ 音频时长（证明按墙钟节拍喂、不是快灌）；
        #   `drain_sec` = 等服务端清积压（stats/dump_margin 回包）的时长
        #   ⇒ 真实引擎下单段推理 30~60 s，这个值会很大（不是异常）。
        "timing": timing,
    })
    _dump(os.path.join(out_dir, "p1_report.json"), report)
    _dump(os.path.join(out_dir, "p1_timeline.json"), {
        "delay_sec": args.delay,
        "target_lang": args.target_lang,
        "per_segment": per_seg,
    })
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("[p1] 报告：%s" % os.path.join(out_dir, "p1_report.json"))
    print("[p1] 配音 wav：%d 个 → %s" % (len(wavs), os.path.join(out_dir, "dub")))
    return 0


def _dump(path, data) -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[p1] 落盘失败：%s" % e)


if __name__ == "__main__":
    raise SystemExit(main())
