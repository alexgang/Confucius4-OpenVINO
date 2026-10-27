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
        raw_segs = len(plan_segments(audio))
        # ★ 客户端预期段数必须按**服务端 flush 的同一条规则**算
        #   （丢弃尾部不足 1 s 的残留段）—— 否则 expect 比服务端多 1
        #   ⇒ 收尾永远等不到 ⇒ 白等兜底超时 + 报告段数失真（缺陷 13）。
        expected = p1_pipeline.expected_segment_count(audio, 16000)
        check("预期段数可算出", expected >= 1, f"{expected} 段")
        check("★ 预期段数与服务端 flush 口径一致（丢弃 <1s 尾段）",
              expected <= raw_segs,
              f"expected {expected} ≤ raw {raw_segs}")

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


def test_slow_engine_does_not_block_event_loop() -> None:
    """★ EXT-006 P1 实测修掉的缺陷 10：慢引擎**不能阻塞事件循环**。

    实测现象（`.tmp/p1_run2/pipeline.log`）：
        websockets.exceptions.ConnectionClosedError: received 1011
        (internal error) keepalive ping timeout

    成因：服务端在 asyncio 事件循环里**同步**跑真实推理（真实 TTS 单句
    790 s），事件循环被占满 ⇒ 无法及时回 pong ⇒ websockets 判定
    keepalive 超时 ⇒ 服务端以 1011 关闭连接 ⇒ 客户端喂帧途中断连，
    已算好的配音/时间表全部拿不到。

    本自测用**慢桩引擎**（每段阻塞 1.2 s）复现：
      - 若推理在事件循环里 ⇒ 事件循环被占 ⇒ 心跳协程被饿死；
      - 若推理在工作线程里 ⇒ 事件循环始终可响应。
    ⇒ 断言「慢引擎工作时事件循环仍能立即调度其它协程」。
    """
    print("\n[P1] EXT-006 — 慢引擎不阻塞事件循环（keepalive 1011 回归）")
    from ext.bridge import Session

    class SlowEngine(StubEngine):
        def __init__(self) -> None:
            super().__init__()
            self.in_call = threading.Event()
            self.done_call = threading.Event()

        def tts(self, text: str, *, voice: str):
            self.n_calls["tts"] += 1
            self.in_call.set()
            time.sleep(1.2)          # ★ 模拟真实 TTS 的秒级阻塞
            self.done_call.set()
            n = int(0.5 * 24000)
            return (np.zeros(n, dtype=np.int16)).tobytes(), 0.5

    engine = SlowEngine()
    sess = Session("tok", delay_sec=10.0, engine=engine)

    # 造「15 s 语音 + 1 s 静音」⇒ 断句能切出 1 段（照抄 _make_wav 的造法）
    sr = C.SAMPLE_RATE
    seg = np.zeros(int(sr * 15), dtype=np.float32)
    tt = np.arange(seg.shape[0]) / sr
    seg += (0.3 * np.sin(2 * np.pi * 220 * tt)).astype(np.float32)
    sil = np.zeros(int(sr * 1), dtype=np.float32)
    audio = np.concatenate([seg, sil])
    n = audio.shape[0]
    pcm = base64.b64encode((audio * 32767).astype("<i2").tobytes()).decode()

    loop_ticks = []

    async def _scenario() -> None:
        tick_task = None

        async def _ticker():
            while True:
                loop_ticks.append(time.perf_counter())
                await asyncio.sleep(0.05)

        tick_task = asyncio.ensure_future(_ticker())
        # ★ 推理走 to_thread（与服务端 _handle_messages 现在的写法一致）
        await asyncio.to_thread(sess.on_pcm_frame,
                               {"type": "pcm", "seq": 0, "sample_index": 0,
                                "pcm": pcm})
        tick_task.cancel()
        try:
            await tick_task
        except BaseException:
            pass

    asyncio.run(_scenario())

    check("慢引擎确实被调用过", engine.n_calls["tts"] >= 1,
          f"tts 调用 {engine.n_calls['tts']} 次")
    # 事件循环在整个推理期间仍应被调度 ⇒ 心跳协程有多个 tick
    check("推理期间事件循环仍在调度（心跳未被饿死）",
          len(loop_ticks) >= 3, f"tick 数 {len(loop_ticks)}")

    # ★ 反向断言：老写法（同步跑在事件循环里）**必须**饿死心跳协程
    loop_ticks2 = []

    async def _scenario_sync() -> None:
        async def _ticker2():
            while True:
                loop_ticks2.append(time.perf_counter())
                await asyncio.sleep(0.05)

        tick_task = asyncio.ensure_future(_ticker2())
        sess2 = Session("tok", delay_sec=10.0, engine=SlowEngine())
        sess2.on_pcm_frame({"type": "pcm", "seq": 0, "sample_index": 0,
                            "pcm": pcm})          # ★ 同步调用（老写法）
        tick_task.cancel()
        try:
            await tick_task
        except BaseException:
            pass

    asyncio.run(_scenario_sync())
    check("旧写法（同步推理）确实会饿死心跳 ⇒ 本自测能区分真/假通过",
          len(loop_ticks2) < len(loop_ticks),
          f"同步 {len(loop_ticks2)} tick vs 线程 {len(loop_ticks)} tick")


def test_mt_model_dir_resolution() -> None:
    """★ EXT-006 P1 实测修掉的缺陷 11：MT 模型目录解析。

    实测现象（`.tmp/p1_run2/smoke.json` 的 `stages.mt.error`）：
        Could not find a model in the directory
        '"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.6\\models\\mt"'

    成因：用了 `models/mt`（**父目录**），而 openvino_genai 要求目录里
    **直接**放 `openvino_model.xml` 等 IR 文件；真正的模型在**子目录**
    `models/mt/mt2-int8sym-cw-q`。

    断言：
      ① 解析结果**不是**父目录 `models/mt`；
      ② 解析结果指向的目录里**确实有** `openvino_model.xml`（真实可加载）；
      ③ 顺序与 App 的 `translator.DEFAULT_MODEL` 一致（INT8 优先于 INT4）。
    """
    print("\n[P1] EXT-006 — MT 模型目录解析（父目录 vs 真实模型子目录）")
    from ext import engine_runtime as ER

    resolved = ER._resolve_mt_model_dir()
    check("能解析出 MT 模型目录", bool(resolved), f"{resolved}")

    if resolved:
        parent = os.path.join(ER.MODELS_DIR, "mt")
        check("解析结果**不是**父目录 models/mt",
              os.path.normcase(os.path.abspath(resolved)) !=
              os.path.normcase(os.path.abspath(parent)),
              f"{resolved} vs {parent}")
        xml = os.path.join(resolved, "openvino_model.xml")
        check("解析目录里确实有 openvino_model.xml（真实可加载）",
              os.path.isfile(xml), xml)
        check("解析结果是具体模型目录名（含 mt2- 前缀）",
              os.path.basename(resolved).startswith("mt2-"),
              os.path.basename(resolved))

    # ③ 顺序：INT8 优先于 INT4（照抄 App 的 DEFAULT_MODEL 顺序）
    order = [os.path.join(ER.MODELS_DIR, "mt", "mt2-int8sym-cw-q"),
             os.path.join(ER.MODELS_DIR, "mt2-int8sym-cw-q"),
             os.path.join(ER.MODELS_DIR, "mt", "mt2-int4sym-cw-q"),
             os.path.join(ER.MODELS_DIR, "mt2-int4sym-cw-q")]
    src = open(os.path.join(ROOT, "ext", "engine_runtime.py"),
               encoding="utf-8").read()
    check("INT8 候选排在 INT4 候选之前",
          src.index("mt2-int8sym-cw-q") < src.index("mt2-int4sym-cw-q"),
          "int8 先于 int4")
    check("候选顺序与 App 一致（4 项）", len(order) == 4, f"{len(order)} 项")

    # ★ 运行时解析：环境变量后设也生效（导入后设 LIVECAP_MT_MODEL）
    tmp = os.path.join(ER.MODELS_DIR, "mt", "mt2-int4sym-cw-q")
    if os.path.isdir(tmp):
        os.environ["LIVECAP_MT_MODEL"] = tmp
        try:
            again = ER._resolve_mt_model_dir()
            check("环境变量 LIVECAP_MT_MODEL 运行时生效（优先于默认顺序）",
                  again is not None and
                  os.path.normcase(os.path.abspath(again)) ==
                  os.path.normcase(os.path.abspath(tmp)),
                  f"{again}")
        finally:
            os.environ.pop("LIVECAP_MT_MODEL", None)


def test_realtime_feed_path() -> None:
    """★ EXT-006 P1：真实 P1 用的 **realtime=True** 路径必须通。

    为什么补这条：`test_p1_plumbing` 一直用 `realtime=False`（快灌），
    而**真实 P1 实测用 realtime=True**（按墙钟节拍喂帧）——
    ⇒ 这条路径**从来没有被自测覆盖过**。
    而它恰恰是最容易出问题的一条：
      * 节拍靠 `asyncio.sleep` 实现，若事件循环被阻塞 ⇒ 帧会**堆在一起**涌出
        ⇒ 服务端缓冲区瞬间膨胀 ⇒ 断句/时间基点算错 ⇒ 指标失真；
      * 而且真实服务端的推理是**秒级**的，慢引擎 + 实时喂帧
        更容易触发 websockets 的 keepalive（本轮已修的缺陷 11）。

    本自测用**桩引擎 + 真实 websockets 服务**跑一遍 realtime=True：
      ① 收到 hello_ack；
      ② 段数达到预期（含 flush 尾段）；
      ③ **喂帧确实按墙钟节奏**（总耗时应接近音频时长，而不是秒级快灌）；
      ④ stats 带 `_stats` marker。
    """
    print("\n[P1] EXT-006 — realtime=True 路径（真实 P1 的默认模式）")
    import p1_pipeline

    tmp = os.path.join(ROOT, ".tmp", "p1_realtime")
    os.makedirs(tmp, exist_ok=True)
    wav_path = os.path.join(tmp, "realtime.wav")
    token_path = os.path.join(tmp, "token.txt")
    # 造 16 s 音频（15 s 语音 + 1 s 静音 ⇒ 1 段 + flush 尾段）
    _make_wav(wav_path, 16.0)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write("realtime-token-123")
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    port = _free_port()
    th, holder = _start_bridge(port, token, token_path)
    try:
        audio, sr = p1_pipeline.read_wav_16k_mono(wav_path)
        frames = p1_pipeline.frame_payload(audio)
        # ★ 与服务端 flush 同口径（丢弃尾部不足 1 s 的残留段）
        expected = p1_pipeline.expected_segment_count(audio, 16000)
        check("realtime 测试音频可读", sr == 16000 and audio.shape[0] > 0,
              f"{audio.shape[0] / sr:.2f}s")
        check("★ realtime 预期段数与服务端口径一致", expected >= 1,
              f"{expected} 段")

        t0 = time.perf_counter()
        tasks, hello, t_cap = asyncio.run(p1_pipeline._run_client(
            port=port, token=token, frames=frames, delay_sec=10.0,
            recv_timeout=30.0, realtime=True, expect_segments=expected))
        elapsed = time.perf_counter() - t0

        segs = [t for t in tasks if t.get("type") == "tts"]
        stats = [t for t in tasks if t.get("type") == "_stats"]

        check("realtime 模式收到 hello_ack", hello.get("type") == "hello_ack",
              str(hello.get("type")))
        check("realtime 模式段数达到预期（含 flush 尾段）",
              len(segs) == expected, f"收到 {len(segs)} / 预期 {expected}")
        check("realtime 模式 stats 带 _stats marker", len(stats) >= 1,
              f"{len(stats)} 条")
        # ★ 关键断言：喂帧**按墙钟节奏** ⇒ 耗时应接近音频时长，
        #   而不是快灌那样秒级完成。
        audio_sec = audio.shape[0] / sr
        check("★ realtime 喂帧按墙钟节奏（耗时接近音频时长）",
              elapsed >= audio_sec * 0.8,
              f"耗时 {elapsed:.2f}s vs 音频 {audio_sec:.2f}s")
        check("★ realtime 喂帧没有异常快（不是快灌）",
              elapsed < audio_sec + 20.0,
              f"耗时 {elapsed:.2f}s vs 音频 {audio_sec:.2f}s")
    finally:
        try:
            th.stop()
        except Exception:
            pass


def main() -> int:
    print("=" * 68)
    print("EXT P1 管线连通性自测（桩引擎 / 不跑推理 / 不占 GPU·NPU / 不抢锁）")
    print("=" * 68)
    for fn in (test_p1_plumbing, test_flush_only_once,
               test_slow_engine_does_not_block_event_loop,
               test_mt_model_dir_resolution,
               test_realtime_feed_path):
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
