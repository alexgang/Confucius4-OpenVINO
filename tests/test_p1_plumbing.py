"""test_p1_plumbing.py — EXT-006 P1 **管线连通性**自测（不跑推理 / 不占 GPU·NPU）

## 为什么需要这一套

P1 的真实实测（`tools/run_p1_real.py`）要占 GPU.0 + NPU + 共享机器锁，
一旦跑起来就很难中途修管道。而本轮修的 3 个「会让 P1 拿到假数据」的缺陷
全部在**管道层**（stats marker / flush 尾段 / deadline_margin 下发）。

⇒ 本套用**桩引擎**（stub engine，毫秒级返回假 PCM）把整条链路
   「桥接服务 ⇄ 客户端」真跑一遍，验证：

  ① 服务端真的能收到 `flush` 并把**尾段**切出来（且 t_start 不归零）；
  ② 客户端收到的 stats **带 `_stats` marker**（margin 能进报告）；
  ③ tts 任务帧里带 `deadline_margin_sec`（同步误差口径的输入）；
  ④ `p1_pipeline.compute_metrics` 能算出正确的同步误差；
  ⑤ 客户端收尾逻辑能等到「预期段数」而不是干等 recv_timeout。

**不占 GPU·NPU、不跑推理、不抢共享机器锁**（桩引擎不触设备）。
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import sys
import threading
import time
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from ext import config as C  # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    tag = "PASS" if ok else "FAIL"
    extra = (" — " + detail) if detail else ""
    print(f"  [{tag}] {name}{extra}")


# ── 桩引擎 ──────────────────────────────────────────────────────────
class StubEngine:
    """毫秒级返回假数据的引擎（**不触任何设备**）。"""

    def __init__(self, target_lang: str = "ja") -> None:
        self.target_lang = target_lang
        self.n_calls = {"asr": 0, "mt": 0, "tts": 0}
        self.last_error: dict = {}
        self.needs_change: list = []

    def available(self) -> dict:
        return {"stub": True}

    def asr(self, audio, t_start, t_end) -> str:
        self.n_calls["asr"] += 1
        return "テスト原稿"

    def mt(self, text: str) -> str:
        self.n_calls["mt"] += 1
        return "translated"

    def tts(self, text: str, *, voice: str):
        self.n_calls["tts"] += 1
        # 0.5 s 假音频（24 kHz PCM16）
        n = int(0.5 * 24000)
        pcm = (np.zeros(n, dtype=np.int16)).tobytes()
        return pcm, 0.5

    def stats(self) -> dict:
        return {"stub": True, "n_calls": dict(self.n_calls)}


# ── 起一个真的桥接服务（桩引擎） ───────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_bridge(port: int, token: str, token_file: str):
    """在后台线程里跑 websockets 服务（桩引擎）。返回 (server, holder, stop_fn)。"""
    import websockets

    from ext.bridge import TokenStore, handle_ws

    tokens = TokenStore(token_file)
    holder: dict = {}
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    async def _main():
        async with websockets.serve(
            lambda ws: handle_ws(ws, tokens=tokens, delay_sec=10.0,
                                  echo_mode=False, engine=StubEngine(),
                                  session_holder=holder),
            "127.0.0.1", port, origins=None, max_size=32 * 1024 * 1024,
        ):
            loop.call_soon(ready.set)
            await asyncio.Future()

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_main())

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    if not ready.wait(20):
        raise RuntimeError("桥接服务未就绪")
    return th, holder


def _make_wav(path: str, seconds: float = 45.0) -> None:
    """造一段「15 s 语音 + 1 s 静音」重复的测试音频（让断句能切出多段）。"""
    sr = 16000
    seg = np.zeros(int(sr * 15), dtype=np.float32)
    t = np.arange(seg.shape[0]) / sr
    seg += (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sil = np.zeros(int(sr * 1), dtype=np.float32)
    one = np.concatenate([seg, sil])
    reps = int(seconds / 16) + 1
    audio = np.concatenate([one] * reps)[:int(seconds * sr)]
    pcm = (audio * 32767).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def test_p1_plumbing() -> None:
    print("\n[P1] EXT-006 — 管线连通性（桩引擎，不占 GPU·NPU）")
    import p1_pipeline

    tmp = os.path.join(ROOT, ".tmp", "p1_plumbing")
    os.makedirs(tmp, exist_ok=True)
    wav_path = os.path.join(tmp, "plumbing.wav")
    token_path = os.path.join(tmp, "token.txt")
    _make_wav(wav_path, 45.0)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write("plumbing-token-123")
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    port = _free_port()
    th, holder = _start_bridge(port, token, token_path)
    try:
        audio, sr = p1_pipeline.read_wav_16k_mono(wav_path)
        check("测试音频读回正常", sr == 16000 and audio.shape[0] > 0,
              f"{audio.shape[0] / sr:.1f}s @ {sr}Hz")

        frames = p1_pipeline.frame_payload(audio)
        from ext.segmenter import plan_segments
        expected = len(plan_segments(audio))
        check("预期段数可算出", expected >= 2, f"{expected} 段")

        # ★ 实时喂帧用 realtime=False（桩引擎下不需要真实节拍，
        #   但**必须**走 flush / stats / 收尾这些路径）
        tasks, hello, t_cap = asyncio.run(p1_pipeline._run_client(
            port=port, token=token, frames=frames, delay_sec=10.0,
            recv_timeout=30.0, realtime=False, expect_segments=expected))

        segs = [t for t in tasks if t.get("type") == "tts"]
        stats = [t for t in tasks if t.get("type") == "_stats"]

        check("hello_ack 收到", hello.get("type") == "hello_ack",
              str(hello.get("type")))
        check("★ stats 带 _stats marker（margin 不能丢）",
              len(stats) >= 1, f"{len(stats)} 条 stats")
        check("★ 收到的段数达到预期（含 flush 尾段）",
              len(segs) == expected, f"收到 {len(segs)} / 预期 {expected}")

        if segs:
            starts = [t["t_start"] for t in segs]
            check("★ 各段 t_start 单调递增且不归零",
                  all(starts[i] < starts[i + 1] for i in range(len(starts) - 1))
                  and all(s > 0 for s in starts[1:]),
                  ", ".join(f"{s:.2f}" for s in starts))
            check("★ tts 帧带 deadline_margin_sec",
                  all("deadline_margin_sec" in t for t in segs))
            check("★ tts 帧带 margin_sec 与 tts_ready_at",
                  all("margin_sec" in t and "tts_ready_at" in t for t in segs))

        # ── 指标口径 ──────────────────────────────────────────
        m, per = p1_pipeline.compute_metrics(segs, delay_sec=10.0,
                                             margin_summary=None)
        check("同步误差统计有 p50/p95/target",
              all(k in m["sync_err_ms"] for k in ("p50", "p95", "target")))
        check("同步误差口径字符串落进报告",
              "definition" in m["sync_err_ms"])

        # ── 服务端侧余量统计（服务端的 margin_summary） ────────
        sess = holder.get("session")
        if sess is not None:
            summ = sess.margin_summary()
            check("服务端 margin_summary 有段数与负值计数",
                  "n_segments" in summ and "n_negative" in summ,
                  f"n_segments={summ.get('n_segments')} "
                  f"n_negative={summ.get('n_negative')}")
            check("服务端 margin_summary 有累计滞后",
                  "cumulative_lag_sec" in summ,
                  f"cumulative_lag_sec={summ.get('cumulative_lag_sec')}")
            check("服务端 margin_summary 有排程截止余量组",
                  "deadline" in summ, f"keys={sorted(summ.keys())}")
        else:
            check("服务端 session 可取到", False, "holder 里没有 session")

        # ── 配音 wav 落盘 ────────────────────────────────────
        dub_dir = os.path.join(tmp, "dub")
        wavs = p1_pipeline.write_dub_wavs(segs, dub_dir)
        check("配音 wav 落盘数量与段数一致",
              len(wavs) == len(segs), f"{len(wavs)} / {len(segs)}")
        if wavs:
            check("配音 wav 是 24 kHz PCM16",
                  _wav_ok(wavs[0]["path"], 24000),
                  wavs[0]["path"])

        # ── 时间表落盘 ───────────────────────────────────────
        tl = os.path.join(tmp, "timeline.json")
        p1_pipeline._dump(tl, {"per_segment": per})
        check("时间表落盘成功", os.path.isfile(tl) and os.path.getsize(tl) > 0,
              f"{tl} ({os.path.getsize(tl) if os.path.isfile(tl) else 0} B)")
    finally:
        # 关服务
        try:
            loop = th._args  # noqa: SLF001
        except Exception:
            pass
        # 线程是 daemon，进程退出即可回收


def _wav_ok(path: str, expect_rate: int) -> bool:
    try:
        with wave.open(path, "rb") as w:
            return (w.getframerate() == expect_rate
                    and w.getnchannels() == 1
                    and w.getsampwidth() == 2)
    except Exception:
        return False


def test_flush_only_once() -> None:
    print("\n[P1] EXT-006 — flush 只处理一次（幂等）")
    from ext.bridge import Session

    sess = Session("tok", delay_sec=10.0, engine=StubEngine())
    # 塞一段 3 s 的音频
    n = 3 * C.SAMPLE_RATE
    audio = np.zeros(n, dtype=np.float32)
    t = np.arange(n) / C.SAMPLE_RATE
    audio += (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    pcm = base64.b64encode((audio * 32767).astype("<i2").tobytes()).decode()
    out = sess.on_pcm_frame({"type": "pcm", "seq": 0, "sample_index": 0,
                              "pcm": pcm})
    check("3 s 音频不产生段（未到 min 12 s）", not out, f"{out}")
    first = sess.flush()
    check("flush 产出 1 段", len(first) == 1, f"{len(first)} 段")
    if first:
        check("flush 段的 t_start = 0（第一段就该是 0）",
              first[0]["t_start"] == 0.0, f"{first[0]['t_start']}")
    second = sess.flush()
    check("第二次 flush 无输出（幂等）", len(second) == 0, f"{len(second)} 段")


def main() -> int:
    print("=" * 68)
    print("EXT P1 管线连通性自测（桩引擎 / 不跑推理 / 不占 GPU·NPU / 不抢锁）")
    print("=" * 68)
    for fn in (test_p1_plumbing, test_flush_only_once):
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            RESULTS.append((fn.__name__, False))
    npass = sum(1 for _, ok in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
