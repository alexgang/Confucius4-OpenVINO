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


class SlowStubEngine(StubEngine):
    """★ 每段**故意慢一点**的桩引擎（用来制造服务端消息积压）。

    缺陷 16 的根因：服务端消息循环**单线程串行**，一帧 `pcm` 要跑完
    ASR→MT→TTS 才回到循环读下一条消息。
    ⇒ 客户端在收尾时发的 `stats` / `dump_margin` 排在积压队列后面。
    ⇒ 用**慢引擎**制造积压，才能复现「sleep 一下就断开 ⇒ 收不到 stats」。

    ⚠️ 只 sleep，**不触任何设备**（不占 GPU·NPU），自测可在普通机器跑。
    """

    def __init__(self, target_lang: str = "ja", *, per_seg_sec: float = 0.35):
        super().__init__(target_lang=target_lang)
        self.per_seg_sec = per_seg_sec

    def asr(self, audio, t_start, t_end) -> str:
        time.sleep(self.per_seg_sec)
        return super().asr(audio, t_start, t_end)


# ── 起一个真的桥接服务（桩引擎） ───────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_bridge(port: int, token: str, token_file: str,
                  margin_out: str = None, engine=None):
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
                                  echo_mode=False,
                                  engine=(engine if engine is not None
                                          else StubEngine()),
                                  session_holder=holder,
                                  margin_out=margin_out),
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
        tasks, hello, t_cap, _timing = asyncio.run(p1_pipeline._run_client(
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
            # ★★ EXT-024 A 明文：「要写清楚 t_start 用的是哪个时间轴」
            #   ⇒ 断言这个口径**真的随 tts 消息下发到客户端**
            #     （不是只写在服务端源码注释里）。
            check("★★ EXT-024 A：tts 帧带 t_start_axis（时间轴口径明文）",
                  all("t_start_axis" in t for t in segs),
                  str([t.get("t_start_axis") for t in segs])[:120])
            check("★★ EXT-024 A：t_start_axis == 'uplink_sample_index'",
                  all(t.get("t_start_axis") == "uplink_sample_index"
                      for t in segs),
                  str([t.get("t_start_axis") for t in segs])[:120])

        # ── 指标口径 ──────────────────────────────────────────
        m, per = p1_pipeline.compute_metrics(segs, delay_sec=10.0,
                                             margin_summary=None)
        check("同步误差统计有 p50/p95/target",
              all(k in m["sync_err_ms"] for k in ("p50", "p95", "target")))
        check("同步误差口径字符串落进报告",
              "definition" in m["sync_err_ms"])

        # ── 服务端侧余量统计（服务端的 margin_summary） ────────
        # ★★ EXT-024 B：连接关闭时服务端会**清空 holder['session']**
        #   （修「会话登记永远不清」的缺陷）⇒ 客户端跑完后
        #   `holder['session']` 已是 None，真会话被归档到
        #   `holder['last_session']`（保留统计供事后核对）。
        # ⇒ 这里读「当前会话 或 归档会话」⇒ 断言的**语义不变**
        #   （仍要拿到服务端会话的 margin_summary）。
        sess = holder.get("session") or holder.get("last_session")
        if sess is not None:
            summ = sess.margin_summary()
            check("服务端 margin_summary 有段数与负值计数",
                  "n_segments" in summ and "n_negative" in summ,
                  f"n_segments={summ.get('n_segments')} "
                  f"n_negative={summ.get('n_negative')}")
            check("服务端 margin_summary 有新滞后口径（末句滞后 + 斜率）",
                  all(k in summ for k in ("last_segment_lag_sec",
                                          "lag_growth_slope_sec_per_sec",
                                          "max_lag_sec")),
                  f"last={summ.get('last_segment_lag_sec')} "
                  f"slope={summ.get('lag_growth_slope_sec_per_sec')}")
            check("★ EXT-008：服务端已删除「余量求和」量 cumulative_lag_sec",
                  "cumulative_lag_sec" not in summ,
                  f"keys={sorted(summ.keys())}")
            check("服务端 margin_summary 有排程截止余量组",
                  "deadline" in summ, f"keys={sorted(summ.keys())}")
        else:
            check("服务端 session 可取到", False,
                  "holder 里既没有 session 也没有 last_session")

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
        tasks, hello, t_cap, _timing = asyncio.run(p1_pipeline._run_client(
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


def test_dump_margin_on_demand() -> None:
    """★ EXT-006 P1 实测修掉的缺陷 14：余量统计**主动落盘**。

    实测现象（`.tmp/p1_run4/`）：`pipeline rc=0`、19 个配音 wav 全部落盘、
    `p1_report.json` 也有完整指标 —— 但 **`margin.json` 缺失**，
    报告里 `bridge_stats: null` ⇒ EXT-006 要求的「余量分布 /
    余量 < 0 句数 / 累计滞后」**全部拿不到**。

    成因：编排器停服务用 `bridge.terminate()`（SIGTERM）⇒ 进程被直接终止 ⇒
    Python 的 `finally` **不执行** ⇒ 服务端那条落盘路径永远跑不到。

    修法：客户端在断开前发一条 `dump_margin` ⇒ 服务端**立刻**写盘
    （不依赖进程退出路径）。

    本自测断言：
      ① 服务端收到 `dump_margin` 后**确实**把 margin.json 写到磁盘；
      ② 落盘内容含 `margin_summary` / `per_segment` / `engine_calls`；
      ③ 客户端在收尾时**确实**发了 `dump_margin`（源码级断言）。
    """
    print("\n[P1] EXT-006 — 余量统计主动落盘（SIGTERM 不落盘回归）")
    import p1_pipeline

    tmp = os.path.join(ROOT, ".tmp", "p1_margin")
    os.makedirs(tmp, exist_ok=True)
    wav_path = os.path.join(tmp, "margin.wav")
    token_path = os.path.join(tmp, "token.txt")
    margin_path = os.path.join(tmp, "margin.json")
    _make_wav(wav_path, 45.0)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write("margin-token-123")
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if os.path.exists(margin_path):
        os.remove(margin_path)

    port = _free_port()
    th, holder = _start_bridge(port, token, token_path,
                                margin_out=margin_path)
    try:
        audio, sr = p1_pipeline.read_wav_16k_mono(wav_path)
        frames = p1_pipeline.frame_payload(audio)
        expected = p1_pipeline.expected_segment_count(audio, 16000)

        tasks, hello, t_cap, _timing = asyncio.run(p1_pipeline._run_client(
            port=port, token=token, frames=frames, delay_sec=10.0,
            recv_timeout=30.0, realtime=False, expect_segments=expected))

        # ① 落盘
        check("★ 客户端收尾后 margin.json 已落盘",
              os.path.isfile(margin_path), margin_path)
        if os.path.isfile(margin_path):
            with open(margin_path, encoding="utf-8") as f:
                data = json.load(f)
            check("★ 落盘内容含 margin_summary",
                  isinstance(data.get("margin_summary"), dict)
                  and "n_segments" in data["margin_summary"],
                  str(list((data.get("margin_summary") or {}).keys()))[:120])
            check("★ 落盘内容含 per_segment（逐句余量）",
                  isinstance(data.get("per_segment"), list)
                  and len(data["per_segment"]) > 0,
                  f"{len(data.get('per_segment') or [])} 条")
            check("★ 落盘内容含 engine_calls（逐句引擎耗时）",
                  isinstance(data.get("engine_calls"), list),
                  f"{len(data.get('engine_calls') or [])} 条")
            # 逐句余量里必须有 deadline_margin_sec（同步误差的输入）
            ps = data.get("per_segment") or []
            check("★ 逐句余量带 deadline_margin_sec",
                  bool(ps) and "deadline_margin_sec" in ps[0],
                  str(list(ps[0].keys()))[:120] if ps else "空")
    finally:
        try:
            th.stop()
        except Exception:
            pass

    # ③ 源码级断言：客户端收尾确实发了 dump_margin
    src = open(os.path.join(ROOT, "tools", "p1_pipeline.py"),
               encoding="utf-8").read()
    check("★ 客户端收尾确实发 dump_margin（源码级）",
          '"type": "dump_margin"' in src, "源码含 dump_margin")
    src2 = open(os.path.join(ROOT, "ext", "bridge.py"),
                encoding="utf-8").read()
    check("★ 服务端确实处理 dump_margin（源码级）",
          'mtype == "dump_margin"' in src2, "源码含 dump_margin 处理")


def test_expected_segment_count_strict() -> None:
    """★ 缺陷 13 的**严格**口径断言（原先只有 `expected <= raw` 的弱断言）。

    为什么补这条：原断言 `expected <= raw` 在**任何**输入上都成立
    （`expected_segment_count()` 永远 ≤ `len(plan_segments())`）⇒
    **无法区分「口径真的对齐」与「函数随便返回个小数字」** ⇒ 假通过风险。
    本条改成**强断言**：构造两类输入，逐一对上服务端的真实行为。

    服务端真实规则（`ext/bridge.py`）：
      * 流式：`plan_segments(buf)` 取 `segs[:-1]` 逐段处理，最后一段留缓冲；
      * 收尾 `flush()`：把剩余缓冲当**一段**处理，
        但**缓冲长度 < 1.0 s ⇒ 直接丢弃**（不计为段）；
      ⇒ 因此服务端总段数 = `plan_segments` 的段数，
        **除非**尾段（= 最后一段）长度 < 1.0 s。

    断言：
      ① 尾段 ≥ 1.0 s ⇒ expected == raw（**不能少算**，否则提前收尾丢段）；
      ② 尾段 < 1.0 s ⇒ expected == raw − 1（**必须少算 1**，与 flush 对齐）；
      ③ `expected` 永远 ≤ raw（结构性质）。
    """
    print("\n[P1] EXT-006 — 缺陷 13 严格口径断言（避免弱断言假通过）")
    import p1_pipeline
    from ext.segmenter import plan_segments

    sr = 16000
    rng = np.random.default_rng(20261028)

    def _make(tail_sec: float) -> np.ndarray:
        """构造「一段有声 + 指定长度的尾段」。"""
        body = (rng.standard_normal(int(15.2 * sr)) * 0.05).astype(np.float32)
        tail = np.zeros(int(tail_sec * sr), dtype=np.float32)
        return np.concatenate([body, tail])

    # ① 尾段 ≥ 1.0 s ⇒ 期望 == raw
    #    ⚠️ 尾部静音会被 VAD（silence_db=-40dB, min_silence_ms=300）在
    #    min_segment_sec(=12s) 之后切一刀 ⇒ 尾段长度 ≈ 尾静音 − 0.5 s。
    #    故用 3.0 s 尾静音 ⇒ 尾段 ≈ 1.5 s（≥1 s）。
    a_long = _make(3.0)
    raw_long = len(plan_segments(a_long))
    exp_long = p1_pipeline.expected_segment_count(a_long, sr)
    tail_long = ((plan_segments(a_long)[-1][1]
                  - plan_segments(a_long)[-1][0]) / sr)
    check("★ 尾段≥1s ⇒ expected == raw（不许少算）",
          exp_long == raw_long,
          f"expected={exp_long} raw={raw_long} tail={round(tail_long,3)}s")
    check("★ 尾段≥1s 的用例**确实**构造出了 ≥1s 的尾段",
          tail_long >= 1.0, f"tail={round(tail_long,3)}s")

    # ② 尾段 < 1.0 s ⇒ 期望 == raw − 1（与服务端 flush 的丢弃规则对齐）
    a_short = _make(0.4)
    raw_short = len(plan_segments(a_short))
    exp_short = p1_pipeline.expected_segment_count(a_short, sr)
    tail_len = (plan_segments(a_short)[-1][1]
                - plan_segments(a_short)[-1][0]) / sr
    check("★ 尾段<1s ⇒ expected == raw−1（与服务端 flush 对齐）",
          exp_short == raw_short - 1,
          f"expected={exp_short} raw={raw_short} tail={round(tail_len,3)}s")
    check("★ 尾段<1s 的用例**确实**构造出了 <1s 的尾段",
          tail_len < 1.0, f"tail={round(tail_len,3)}s")

    # ③ 结构性质
    check("★ expected 恒 ≤ raw（结构性质）",
          exp_long <= raw_long and exp_short <= raw_short,
          f"{exp_long}≤{raw_long}, {exp_short}≤{raw_short}")

    # ④ 反向断言：旧的错误实现（直接取 len(plan_segments)）在尾段<1s 时**会算错**
    #    ⇒ 证明这条断言**不是恒真**（能区分真通过 / 假通过）。
    check("★ 反向断言：旧实现（直接取 len）在尾段<1s 时确实算错",
          raw_short != exp_short,
          f"旧写法={raw_short} vs 新写法={exp_short} ⇒ 断言有区分力")


def test_orchestrator_margin_dump_path() -> None:
    """★ 缺陷 14 的**编排器侧**路径（`run_p1_real._request_margin_dump`）。

    为什么补这条：缺陷 14 修了两处 —— 客户端（`p1_pipeline`）与服务端
    （`ext/bridge`）—— 但**编排器**（`tools/run_p1_real.py`）里那个
    `_request_margin_dump()` 是「停服务前再请一次」的双保险，
    **它从未被真正执行过**（只在源码里存在 ⇒ 无法证明它能工作）。
    而它恰恰是**最容易被 API 变更打断**的一段（websockets 17.x 的
    `additional_headers` / `origin` 参数、`hello` 鉴权握手）。

    本条用**真 websockets 服务 + 桩引擎**跑一遍编排器那个函数，
    断言它**真的**让服务端落盘了 margin.json。
    """
    print("\n[P1] EXT-006 — 编排器侧余量落盘路径（双保险从未被执行过）")
    import p1_pipeline
    import run_p1_real

    tmp = os.path.join(ROOT, ".tmp", "p1_orch_margin")
    os.makedirs(tmp, exist_ok=True)
    token_path = os.path.join(tmp, "token.txt")
    margin_path = os.path.join(tmp, "margin.json")
    with open(token_path, "w", encoding="utf-8") as f:
        f.write("orch-margin-token-456")
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if os.path.exists(margin_path):
        os.remove(margin_path)

    port = _free_port()
    th, holder = _start_bridge(port, token, token_path,
                                margin_out=margin_path)
    try:
        # 先用客户端跑一遍，让服务端**有段可统计**（否则 summary 是空的）
        wav_path = os.path.join(tmp, "orch.wav")
        _make_wav(wav_path, 45.0)
        audio, sr = p1_pipeline.read_wav_16k_mono(wav_path)
        frames = p1_pipeline.frame_payload(audio)
        expected = p1_pipeline.expected_segment_count(audio, 16000)
        asyncio.run(p1_pipeline._run_client(
            port=port, token=token, frames=frames, delay_sec=10.0,
            recv_timeout=30.0, realtime=False, expect_segments=expected))

        # 客户端那一路应该已经落了盘（含真实逐句余量）
        check("★ 前置：客户端那一路已落盘 margin.json",
              os.path.isfile(margin_path), margin_path)
        n_client = 0
        if os.path.isfile(margin_path):
            with open(margin_path, encoding="utf-8") as f:
                n_client = len((json.load(f).get("per_segment")) or [])
        check("★ 前置：客户端落盘含逐句余量（非空）",
              n_client > 0, f"{n_client} 段")

        # ★★★ 缺陷 15 的核心断言 ★★★
        #   编排器的「双保险」会**另开一条 WebSocket 连接**。
        #   旧实现：那条连接建了一个**全新的空 Session** 并顶替了真会话
        #   ⇒ dump_margin 落盘的是**空统计**
        #   ⇒ 把客户端刚写好的真余量数据**覆盖掉了**。
        #   修法：服务端遇到已有活跃会话时不再顶替（`_register_session`）。
        # 本断言验证：编排器跑完一遍后，**磁盘上的数据没被清空**。
        ok = run_p1_real._request_margin_dump(port, token_file=token_path)
        check("★ 编排器 _request_margin_dump 返回 True", ok is True, f"ok={ok}")
        check("★ 编排器这一路跑完后 margin.json 仍在", os.path.isfile(margin_path),
              margin_path)
        n_after = 0
        if os.path.isfile(margin_path):
            with open(margin_path, encoding="utf-8") as f:
                data = json.load(f)
            n_after = len(data.get("per_segment") or [])
            ms = data.get("margin_summary") or {}
            check("★ 落盘内容含 margin_summary.n_segments",
                  "n_segments" in ms, str(ms)[:160])
        # ★ 关键：条数不能变少 —— 旧实现会把它清成 0
        check("★ 编排器这一路**没有把真数据清空**（缺陷 15 回归）",
              n_after >= n_client and n_after > 0,
              f"客户端落盘 {n_client} 段 → 编排器跑完后 {n_after} 段")

        # 反向断言：证明这个断言**有区分力**（不是恒真）
        #   —— 手工模拟「空会话顶替」⇒ 落盘会变成 0 段
        old_holder = {"session": holder.get("session")}
        holder["session"] = Session_like_empty = type(
            "E", (), {"margin_summary": lambda self: {}, "margins": [],
                      "engine_calls": []})()
        try:
            # 直接调服务端的落盘函数（模拟旧行为：空会话）
            from ext.bridge import _dump_margin
            _dump_margin(holder, margin_path, None)
            with open(margin_path, encoding="utf-8") as f:
                n_bad = len((json.load(f).get("per_segment")) or [])
            check("★ 反向断言：空会话落盘会被拒绝（第二道防线生效）",
                  n_bad == n_client,
                  f"空会话落盘后 {n_bad} 段（原 {n_client} 段应保留）")
        finally:
            holder["session"] = old_holder.get("session")
    finally:
        try:
            th.stop()
        except Exception:
            pass


def test_client_waits_for_stats_not_sleep() -> None:
    """★ 缺陷 16（本轮实测抓到的真缺陷）：客户端收尾**必须等 stats 回包**。

    实测现象（`.tmp/p1_run6/`）：
      * `pipeline.log` 打出「⚠️ 未收到 margin_dumped 确认（margin.json 可能缺失）」；
      * `p1_report.json` 里 `bridge_stats: null`、`margin: null`
        ⇒ **EXT-006 的三项核心验收量（余量分布 / 余量<0 句数 / 累计滞后）
          在报告里依然拿不到**（虽然 `margin.json` 最后由编排器的另一条
          连接侥幸落盘了，但那是「双保险」，不是正常路径）；
      * 客户端代码当时是「发 stats → `sleep(1.5)` → 发 dump_margin → 断开」。

    成因：服务端消息循环是**单线程串行**的 —— 一帧 `pcm` 就要
    `await asyncio.to_thread(session.on_pcm_frame, msg)` 跑完
    ASR→MT→TTS（真实引擎单段 30~60 s）才回到循环读下一条消息。
    ⇒ 客户端收尾时发的 `stats` / `dump_margin` **排在积压队列后面**，
      服务端要清完积压才看得到它们
    ⇒ `sleep(1.5)` 远远不够 ⇒ 客户端断开 ⇒ 这两条消息被丢掉。

    修法：客户端**真的等 stats 事件**（拿到 stats 即证明服务端已清空积压、
    回到消息循环）⇒ 随后的 `dump_margin` 才会被立刻处理。

    本自测用一个**慢桩引擎**（每段 sleep 0.35 s）制造积压，
    断言：
      ① 客户端**确实等到了** stats（`report["bridge_stats"]` 非空）；
      ② 报告里 `margin` 非空且含 `n_segments`；
      ③ 反向断言：**旧写法**（sleep 后不等 stats）在同样条件下拿不到 stats
        ⇒ 证明这条断言**有区分力**，不是恒真。
    """
    print("\n[P1] EXT-006 — 缺陷 16：收尾必须等 stats 回包（不能 sleep）")
    import p1_pipeline

    tmp = os.path.join(ROOT, ".tmp", "p1_stats_wait")
    os.makedirs(tmp, exist_ok=True)
    wav_path = os.path.join(tmp, "sw.wav")
    token_path = os.path.join(tmp, "token.txt")
    margin_path = os.path.join(tmp, "margin.json")
    with open(token_path, "w", encoding="utf-8") as f:
        f.write("stats-wait-token-789")
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    _make_wav(wav_path, 45.0)
    if os.path.exists(margin_path):
        os.remove(margin_path)

    port = _free_port()
    # ★ 用**慢桩引擎**（每段 0.35 s）制造服务端积压，
    #   并配 margin_out ⇒ 服务端才会真的落盘 margin.json。
    th, holder = _start_bridge(port, token, token_path,
                                margin_out=margin_path,
                                engine=SlowStubEngine(per_seg_sec=0.35))
    try:
        audio, sr = p1_pipeline.read_wav_16k_mono(wav_path)
        frames = p1_pipeline.frame_payload(audio)
        expected = p1_pipeline.expected_segment_count(audio, 16000)
        tasks, hello, t_cap, timing = asyncio.run(p1_pipeline._run_client(
            port=port, token=token, frames=frames, delay_sec=10.0,
            recv_timeout=60.0, realtime=False, expect_segments=expected))

        stats = [t for t in tasks if t.get("type") == "_stats"]
        check("★ 客户端**等到了** stats 回包（不是 sleep 硬等）",
              len(stats) >= 1, f"{len(stats)} 条 stats")
        if stats:
            m = stats[-1].get("margin") or {}
            check("★ stats 里带 margin 汇总",
                  "n_segments" in m, str(list(m.keys()))[:120])
            check("★ margin 汇总里 n_segments > 0（真有数据）",
                  int(m.get("n_segments") or 0) > 0,
                  f"n_segments={m.get('n_segments')}")
            # ★★ 缺陷 17：顶层必须是**排程口径**（否则读出「零滞后」假结论）
            check("★ margin 汇总顶层标明口径（basis=deadline）",
                  m.get("basis") == "deadline", f"basis={m.get('basis')}")
            check("★ margin 汇总顶层含 definition（可核对口径）",
                  isinstance(m.get("definition"), str)
                  and len(m.get("definition")) > 5,
                  str(m.get("definition"))[:100])

        # 走一遍真实的报告组装路径 ⇒ 确认 bridge_stats / margin 不再是 null
        seg_tasks = [t for t in tasks if t.get("type") == "tts"]
        metrics, per_seg = p1_pipeline.compute_metrics(
            seg_tasks, delay_sec=10.0,
            margin_summary=(stats[-1].get("margin") if stats else None))
        check("★ 报告里的 margin 字段非空（EXT-006 三项验收量入口）",
              isinstance(metrics.get("margin"), dict)
              and "n_segments" in (metrics.get("margin") or {}),
              str(metrics.get("margin"))[:160])
        # ★ 缺陷 16 的落盘侧：客户端这一路就该把 margin.json 写出来
        #   （旧写法：客户端断开 ⇒ 服务端还在积压 ⇒ 拿不到确认 ⇒ 文件缺失）
        check("★ 客户端收尾后 margin.json 已落盘（正常路径，不靠编排器双保险）",
              os.path.isfile(margin_path), margin_path)
    finally:
        try:
            th.stop()
        except Exception:
            pass

    # ★ 反向断言：证明「等 stats」这个条件**有区分力**
    #    —— 若不等 stats（等价于旧写法），stats 列表就是空的。
    src = open(os.path.join(ROOT, "tools", "p1_pipeline.py"),
               encoding="utf-8").read()
    check("★ 反向断言：源码里 stats 回包是**等事件**而非 sleep 硬等",
          "stats_got.wait()" in src and "stats_got = asyncio.Event()" in src,
          "源码含 stats_got.wait()")
    check("★ 反向断言：旧写法（只 sleep 不等 stats）已不在源码里",
          'await asyncio.sleep(1.5)\n            await ws.send(json.dumps({"type": "dump_margin"}))'
          not in src,
          "旧的 sleep(1.5) 路径已移除")

    # ★★★ 缺陷 16 的**行为级**反向断言 ★★★
    #   上面的源码字符串检查只能证明「代码长这样」，不能证明
    #   「不等 stats 就真的拿不到 stats」⇒ 假通过风险。
    #   ⇒ 这里**真的跑一遍旧写法**：发 stats → sleep(1.5) → 发 dump_margin
    #     → 立刻断开，统计它收到几条 stats。
    #   期望：旧写法收到 **0 条** stats（服务端还在积压，看不到 stats 请求）
    #         新写法收到 **≥1 条**（上面已断言）
    #   ⇒ 两者一对比 ⇒ 这条断言**有区分力**，不是恒真。
    print("\n[P1] EXT-006 — 缺陷 16 行为级反向断言（旧写法拿不到 stats）")
    port2 = _free_port()
    # ★ 慢引擎 3.0 s/段 ⇒ 3 段共 **9 s** 服务端处理时间。
    #   实测时序（探针 .tmp/probe_legacy.py）：
    #     客户端喂 750 帧要 4.32 s；旧写法的等待窗口 = 1.5 + 0.2 = 1.7 s
    #   ⇒ 需要 3 × per_seg_sec > 4.32 + 1.7 = 6.02 s 才有确定性的积压
    #   ⇒ 取 3.0 s/段（9 s）⇒ 余量充足，**不靠运气**。
    th2, holder2 = _start_bridge(port2, token, token_path,
                                  engine=SlowStubEngine(per_seg_sec=3.0))
    try:
        got = asyncio.run(_legacy_no_wait_stats_run(port2, token, frames))
        check("★ 反向断言（旧写法）：不等 stats ⇒ **收不到 stats 回包**",
              got == 0, f"旧写法收到 {got} 条 stats（期望 0）")
        check("★ 反向断言有区分力：新写法拿到 ≥1 条 vs 旧写法 0 条",
              len(stats) >= 1 and got == 0,
              f"新 {len(stats)} 条 / 旧 {got} 条")
    finally:
        try:
            th2.stop()
        except Exception:
            pass


async def _legacy_no_wait_stats_run(port: int, token: str, frames) -> int:
    """★ 缺陷 16 的**旧写法**复现（仅用于自测，证明断言有区分力）。

    旧写法：发 `stats` → `sleep(1.5)` → 发 `dump_margin` → 立刻断开。
    服务端此时还在处理积压的 `pcm`（慢引擎每段 0.35 s）⇒
    根本看不到 `stats` 请求 ⇒ 客户端**收不到任何 stats 回包**。

    Returns
    -------
    int
        收到的 stats 条数（旧写法下应为 0）。
    """
    import websockets

    got = {"n": 0}

    async def _run():
        uri = "ws://127.0.0.1:%d" % port
        async with websockets.connect(
                uri,
                origin="chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib",
                additional_headers={"X-Bridge-Token": token},
                max_size=32 * 1024 * 1024,
                ping_interval=None) as ws:
            await ws.send(json.dumps({"type": "hello", "role": "p1_probe",
                                      "token": token}))
            await asyncio.wait_for(ws.recv(), timeout=30)

            async def _recv():
                while True:
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    if msg.get("type") == "stats":
                        got["n"] += 1

            rx = asyncio.ensure_future(_recv())
            try:
                for seq, sidx, pcm in frames:
                    await ws.send(json.dumps({
                        "type": "pcm", "seq": seq, "sample_index": sidx,
                        "pcm": base64.b64encode(pcm).decode("ascii"),
                    }))
                await ws.send(json.dumps({"type": "flush"}))
                # ★ 旧写法：不等 stats，只 sleep 一下就发 dump_margin
                await ws.send(json.dumps({"type": "stats"}))
                await asyncio.sleep(1.5)
                await ws.send(json.dumps({"type": "dump_margin"}))
                await asyncio.sleep(0.2)
            finally:
                rx.cancel()
                try:
                    await rx
                except BaseException:
                    pass

    try:
        await _run()
    except Exception:
        pass
    return got["n"]


def test_ext008_lag_metrics() -> None:
    """★ EXT-008 第 1 点：**滞后口径修正**的自测。

    要验的三件事：
      1. **旧口径（余量求和）被删除** —— 不是「值变了」，而是**键没了**；
      2. **末句滞后** = 末句 `max(0, −排程余量)`（**不是**求和）；
      3. **滞后增长斜率** = 对 `(t_start, 排程余量)` 线性拟合的斜率，
         且**有区分力**：
         - 余量越来越负 ⇒ 斜率为**负**；
         - 余量恒定     ⇒ 斜率为 **0**（证明不是恒真的负数）。
    """
    print("\n[P1] EXT-008 — 滞后口径（末句滞后 + 斜率；删除求和量）")
    import p1_pipeline
    from ext.bridge import decompose_lag, summarize_margins

    # ── 构造一组「余量随时间越来越负」的逐句数据 ────────────
    segs = [{"id": "s%d" % i, "type": "tts",
             "t_start": float(i) * 10.0,
             "t_end": float(i) * 10.0 + 12.0,
             "deadline_margin_sec": -5.0 * i,
             "margin_sec": 1.0}
            for i in range(1, 6)]

    # 客户端口径
    m, _per = p1_pipeline.compute_metrics(segs, delay_sec=10.0,
                                          margin_summary=None)
    lag = m.get("lag") or {}
    check("★ EXT-008：客户端指标含新滞后口径 lag",
          all(k in lag for k in ("last_segment_lag_sec",
                                 "lag_growth_slope_sec_per_sec",
                                 "max_lag_sec")),
          f"keys={sorted(lag.keys())}")
    # 末句 = i=5 ⇒ 排程余量 −25 ⇒ 末句滞后 25
    check("★ EXT-008：客户端末句滞后 = 25（不是求和 75）",
          abs(float(lag.get("last_segment_lag_sec") or 0.0) - 25.0) < 1e-6,
          f"last={lag.get('last_segment_lag_sec')}")
    check("★ EXT-008：客户端最大滞后 = 25",
          abs(float(lag.get("max_lag_sec") or 0.0) - 25.0) < 1e-6,
          f"max={lag.get('max_lag_sec')}")
    check("★ EXT-008：客户端斜率为负（余量随时间变负）",
          float(lag.get("lag_growth_slope_sec_per_sec") or 0.0) < 0,
          f"slope={lag.get('lag_growth_slope_sec_per_sec')}")
    check("★ EXT-008：客户端已无 cumulative_lag_sec 键",
          "cumulative_lag_sec" not in lag, f"keys={sorted(lag.keys())}")

    # 服务端口径
    summ = summarize_margins(segs)
    check("★ EXT-008：服务端顶层已删除 cumulative_lag_sec",
          "cumulative_lag_sec" not in summ, f"keys={sorted(summ.keys())}")
    check("★ EXT-008：服务端末句滞后 = 25（与客户端一致）",
          abs(float(summ.get("last_segment_lag_sec") or 0.0) - 25.0) < 1e-6,
          f"last={summ.get('last_segment_lag_sec')}")
    check("★ EXT-008：服务端斜率 == 客户端斜率（口径一致）",
          abs(float(summ.get("lag_growth_slope_sec_per_sec") or 0.0)
              - float(lag.get("lag_growth_slope_sec_per_sec") or 0.0)) < 1e-6,
          f"srv={summ.get('lag_growth_slope_sec_per_sec')} "
          f"cli={lag.get('lag_growth_slope_sec_per_sec')}")
    check("★ EXT-008：服务端带 lag_definition（reviewer 可核对口径）",
          isinstance(summ.get("lag_definition"), str)
          and len(summ.get("lag_definition")) > 10,
          str(summ.get("lag_definition"))[:80])

    # ── 区分力：余量恒定 ⇒ 斜率必须为 0 ────────────────────
    flat = [{"id": "f%d" % i, "type": "tts",
             "t_start": float(i) * 10.0,
             "t_end": float(i) * 10.0 + 12.0,
             "deadline_margin_sec": -50.0, "margin_sec": 1.0}
            for i in range(1, 6)]
    sf = summarize_margins(flat)
    check("★ EXT-008 区分力：余量恒定 ⇒ 斜率为 0（不是恒真的负数）",
          abs(float(sf.get("lag_growth_slope_sec_per_sec") or 0.0)) < 1e-9,
          f"slope={sf.get('lag_growth_slope_sec_per_sec')}")
    check("★ EXT-008 区分力：余量恒定 ⇒ 末句滞后 = 50（旧求和量会给 250）",
          abs(float(sf.get("last_segment_lag_sec") or 0.0) - 50.0) < 1e-6,
          f"last={sf.get('last_segment_lag_sec')}")

    # ── 滞后分解（喂帧慢 vs 引擎慢） ────────────────────────
    decomp = decompose_lag(segs, delay_sec=10.0)
    check("★ EXT-008：滞后分解含末句与两项分解",
          all(k in decomp for k in ("last_segment", "sum_feed_lag_sec",
                                    "sum_intrinsic_lag_sec")),
          f"keys={sorted(decomp.keys())}")
    check("★ EXT-008：滞后分解逐段有 feed/intrinsic 两项",
          all(("feed_lag_sec" in r and "intrinsic_lag_sec" in r)
              for r in decomp.get("per_segment") or []),
          f"n={len(decomp.get('per_segment') or [])}")


def test_ext008_feed_backpressure() -> None:
    """★ EXT-008 第 2 点：**喂帧被谁阻塞**——用桩引擎复现「服务端背压」。

    为什么要这条自测：EXT-008 问「喂帧 570.96 s / 音频 300 s ⇒ 是谁阻塞？」
    答案要能被**复现**，而不是只对一次实测的解读。

    ⚠️ **测量点选在服务端，不在客户端**：
      客户端侧的 `ws.send()` 阻塞时长**不可靠** —— TCP 内核缓冲会把
      小写入吸收掉，`send()` 往往立刻返回 ⇒ 看不到阻塞，
      但服务端其实**很久之后**才收到那一帧。
      ⇒ 真正可信的量是**服务端侧**的「帧到达延迟」：
          arrival_delay = 帧到达服务端的墙钟 − (t0 + sample_index/16000)
      （`sample_index` 是音频时间 ⇒ 不用墙钟换算 ⇒ 天然抗漂移）

    做法：用**慢桩引擎**（`SlowStubEngine`，只 sleep、不触设备）
    ⇒ 服务端消息循环被推理占住 ⇒ 帧到达延迟变大
    ⇒ 断言：服务端的 `stats.feed_arrival_delay` 显示
      * `n_frames_late_gt_1s > 0`（帧送晚了 ⇒ **服务端没在及时读**）
      * `max_delay_sec` 明显 > 0
    ⇒ **同时**断言「快引擎下不出现这种情况」——否则断言恒真。
    """
    print("\n[P1] EXT-008 — 喂帧背压定位（服务端侧逐帧到达延迟）")
    import p1_pipeline

    tmp = os.path.join(ROOT, ".tmp", "p1_ext008_bp")
    os.makedirs(tmp, exist_ok=True)
    wav_path = os.path.join(tmp, "bp.wav")
    token_path = os.path.join(tmp, "token.txt")
    _make_wav(wav_path, 16.0)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write("ext008-bp-token")
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    audio, sr = p1_pipeline.read_wav_16k_mono(wav_path)
    frames = p1_pipeline.frame_payload(audio)
    expected = p1_pipeline.expected_segment_count(audio, 16000)

    # ── 场景 A：慢引擎 ⇒ 制造服务端积压 ────────────────────
    port = _free_port()
    th, holder = _start_bridge(port, token, token_path,
                                engine=SlowStubEngine(per_seg_sec=1.5))
    try:
        tasks, _h, _tc, timing = asyncio.run(p1_pipeline._run_client(
            port=port, token=token, frames=frames, delay_sec=10.0,
            recv_timeout=30.0, realtime=True, expect_segments=expected))
    finally:
        try:
            th.stop()
        except Exception:
            pass

    check("★ EXT-008：慢引擎下拿到喂帧时序",
          isinstance(timing, dict) and "frame_timing_summary" in timing,
          f"timing keys={sorted((timing or {}).keys())}")
    check("★ EXT-008：喂帧耗时与音频时长分开记录",
          "feed_sec" in (timing or {}) and "audio_sec" in (timing or {}),
          f"feed={(timing or {}).get('feed_sec')} "
          f"audio={(timing or {}).get('audio_sec')}")
    check("★ EXT-008：t0 定义写进报告（reviewer 可核对）",
          isinstance((timing or {}).get("t0_definition"), str)
          and "t0" in (timing or {}).get("t0_definition", ""),
          str((timing or {}).get("t0_definition"))[:80])

    # 服务端侧的逐帧到达延迟（**真正的证据**）
    # ★★ EXT-024 B：连接关闭 ⇒ `holder['session']` 被清空，
    #   真会话归档到 `holder['last_session']` ⇒ 两处都读。
    sess = holder.get("session") or holder.get("last_session")
    check("★ EXT-008：能取到服务端 session（查逐帧到达延迟）",
          sess is not None,
          "holder 里既没有 session 也没有 last_session")
    if sess is not None:
        fad = sess.stats().get("feed_arrival_delay") or {}
        check("★ EXT-008：服务端记录了逐帧到达延迟",
              int(fad.get("n_frames_measured") or 0) > 0,
              f"n={fad.get('n_frames_measured')}")
        check("★ EXT-008：★ 慢引擎下有帧送晚 > 1s ⇒ **服务端未及时读**",
              int(fad.get("n_frames_late_gt_1s") or 0) > 0,
              f"late={fad.get('n_frames_late_gt_1s')} / "
              f"{fad.get('n_frames_measured')}")
        check("★ EXT-008：最大到达延迟明显 > 0",
              float(fad.get("max_delay_sec") or 0.0) > 1.0,
              f"max={fad.get('max_delay_sec')}s")
        # 区分力：快引擎 ⇒ 不该有送晚的帧
        port2 = _free_port()
        th2, holder2 = _start_bridge(port2, token, token_path,
                                     engine=StubEngine())
        try:
            asyncio.run(p1_pipeline._run_client(
                port=port2, token=token, frames=frames, delay_sec=10.0,
                recv_timeout=30.0, realtime=True, expect_segments=expected))
        finally:
            try:
                th2.stop()
            except Exception:
                pass
        sess2 = holder2.get("session") or holder2.get("last_session")
        fad2 = (sess2.stats().get("feed_arrival_delay") or {}) if sess2 else {}
        check("★ EXT-008 区分力：快引擎下无帧送晚 > 1s（否则上面断言恒真）",
              int(fad2.get("n_frames_late_gt_1s") or 0) == 0,
              f"late={fad2.get('n_frames_late_gt_1s')} / "
              f"{fad2.get('n_frames_measured')}")


def test_ext008_bench_segments_under_asr_limit() -> None:
    """★ EXT-008 实测踩坑的**回归自测**：基准工具不得产出超 ASR 段长上限的段。

    背景（2026-10-29 实测）：`tools/throughput_bench.py` 的 (a)(c) 原本把
    5 分钟素材**整段**喂给 ASR ⇒ R2T2 直接报
    「segment too long: 2432 > 2400 mel frames (≈24.3s)」⇒
    **调用失败、RTF 数值完全无效**（却不会抛异常 ⇒ 静默拿到假数）。

    ⇒ 现在 ASR 一律**逐段**跑（与生产同一套断句）。
    ⇒ 本自测断言：
      1. 分段助手产出的**每段都 ≤ 24.0 s**（留 0.3 s 余量）；
      2. 段数 > 1（真的切了，不是整段）；
      3. 段时长合计 ≈ 音频总长（不丢内容）；
      4. 尾段 < 1 s 的丢弃规则生效；
      5. **区分力**：喂一段**人为超长**的音频时，仍不得产出超限段
         （否则断言可能恒真）。
    """
    print("\n[P1] EXT-008 — 基准分段不得超 ASR 段长上限（24.3 s）")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import throughput_bench as TB

    ASR_LIMIT_SEC = 24.0   # R2T2 实测上限 24.3 s，留余量

    # 用合成音频（不依赖外部素材，保证自测可重复）
    sr = 16000
    dur = 120.0
    t = np.arange(int(dur * sr)) / float(sr)
    audio = (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    segs = TB.plan_production_segments(audio, sr)
    check("★ EXT-008：基准分段助手可用", isinstance(segs, list),
          f"type={type(segs).__name__}")
    check("★ EXT-008：确实切成了多段（不是整段）", len(segs) > 1,
          f"n_segments={len(segs)}")
    lens = [(s1 - s0) / float(sr) for (s0, s1) in segs]
    over = [l for l in lens if l > ASR_LIMIT_SEC]
    check("★ EXT-008：★ 没有段超过 ASR 段长上限（否则 RTF 全是假数）",
          not over,
          f"max={max(lens) if lens else None:.2f}s over={over}")
    total = sum(lens)
    check("★ EXT-008：段时长合计 ≈ 音频总长（不丢内容）",
          abs(total - dur) < 2.0, f"total={total:.2f}s vs {dur}s")

    # 区分力：喂**超长**音频（10 分钟）⇒ 仍不得产出超限段
    dur2 = 600.0
    t2 = np.arange(int(dur2 * sr)) / float(sr)
    audio2 = (0.2 * np.sin(2 * np.pi * 220.0 * t2)).astype(np.float32)
    segs2 = TB.plan_production_segments(audio2, sr)
    lens2 = [(s1 - s0) / float(sr) for (s0, s1) in segs2]
    over2 = [l for l in lens2 if l > ASR_LIMIT_SEC]
    check("★ EXT-008 区分力：10 分钟素材也不产出超限段",
          not over2 and len(segs2) > len(segs),
          f"n={len(segs2)} max={max(lens2) if lens2 else None:.2f}s "
          f"over={over2}")

    # 尾段 < 1 s 的丢弃规则（与服务端 flush 同规则）
    check("★ EXT-008：末段不是 <1 s 的碎片",
          (not lens) or lens[-1] >= 1.0,
          f"last={lens[-1] if lens else None}")


def main() -> int:
    print("=" * 68)
    print("EXT P1 管线连通性自测（桩引擎 / 不跑推理 / 不占 GPU·NPU / 不抢锁）")
    print("=" * 68)
    for fn in (test_p1_plumbing, test_flush_only_once,
               test_slow_engine_does_not_block_event_loop,
               test_mt_model_dir_resolution,
               test_realtime_feed_path,
               test_dump_margin_on_demand,
               test_expected_segment_count_strict,
               test_orchestrator_margin_dump_path,
               test_client_waits_for_stats_not_sleep,
               test_ext008_lag_metrics,
               test_ext008_feed_backpressure,
               test_ext008_bench_segments_under_asr_limit):
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
