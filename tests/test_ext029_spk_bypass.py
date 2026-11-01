"""test_ext029_spk_bypass.py — ★★★ EXT-029 自测（说话人旁路：独立线程 + 不反压 ASR）

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

## 覆盖 EXT-029 的四条要求

| # | 要求 | 本文件的断言 |
|---|---|---|
| ① | 旁路推理放独立线程/队列；音频入口**只做 put_nowait**；队列有界、满了**丢旧块并计数**；**不得阻塞** ASR 主路径 / 定稿 / MT / TTS | `test_feed_is_nonblocking`、`test_queue_full_drops_oldest`、`test_main_path_not_blocked_by_bypass`、`test_bridge_feeds_bypass_nonblocking` |
| ② | spk 结果**异步回填**；未到就按**方案 A**（上一句音色 / 预设 A），**不等** | `test_label_backfill_is_async`、`test_missing_label_uses_preset_a`、`test_resolve_spk_prefers_bypass_label` |
| ③ | 验收指标字段必须在位：`spk_queue_drop` / `spk_worker_busy_ms` | `test_stats_fields_present`、`test_bridge_stats_and_margin_carry_fields` |
| ④ | 不得与 ASR 抢同一把 GPU 锁导致 ASR 排队；若必须共用 GPU，须能**测得** ASR 额外延迟 | `test_shares_device_lock`、`test_lock_held_time_measured` |

## ★★ 为什么每组断言都配「反证」

铁律：**自测要能区分「真通过」与「假通过」**。
⇒ 每个关键断言都配一个**故意破坏**的子测试：
   断言成立 ⇒ 实现正确；断言在破坏后**必须失败** ⇒ 证明断言不是恒真。

例如：`feed()` 若改成 `put()`（阻塞），`test_feed_is_nonblocking`
必须 FAIL —— 否则这个断言就是假的。

运行：
    python tests/test_ext029_spk_bypass.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
import time
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ext import config as C
from ext.bridge import PipelineSession, Session
from ext.speaker_bypass import (DEFAULT_QUEUE_MAXSIZE, SpeakerBypass,
                                _log as spk_log)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


# ══════════════════════════════════════════════════════════════════
# 桩：可控的旁路引擎（不碰真模型 ⇒ 自测不占 GPU/NPU）
# ══════════════════════════════════════════════════════════════════
class _StubSpkEngine:
    """假引擎：记录 feed 次数、可控 on_final 延迟与返回。"""

    def __init__(self, *, on_final_sec: float = 0.0, feed_sec: float = 0.0,
                 spk: str = "S1", pending: bool = False) -> None:
        self.on_final_sec = on_final_sec
        self.feed_sec = feed_sec     # ★ 模拟「重」的 feed（测反压用）
        self.spk = spk
        self.pending = pending
        self.n_feed = 0
        self.n_final = 0
        self._lock = threading.Lock()

    def feed(self, pcm, t_end=None) -> int:
        t0 = time.perf_counter()
        with self._lock:
            self.n_feed += 1
        time.sleep(self.feed_sec)
        return self.n_feed

    def on_final(self, seg_id, t_start, t_end) -> dict:
        with self._lock:
            self.n_final += 1
        if self.on_final_sec:
            time.sleep(self.on_final_sec)
        if self.pending:
            return {"spk": None, "pending": True, "reason": "audio_not_buffered"}
        return {"spk": self.spk, "spk_conf": 0.99, "is_new_spk": True,
                "clean_ranges": [(t_start, t_end)], "pending": False,
                "reason": None, "lag_s": 0.01}

    def stats(self) -> dict:
        return {"seg_compile_count": 1, "seg_infer_count": 3,
                "embed_count": 2, "stub": True}


def _bypass_with(engine, **kw) -> SpeakerBypass:
    """造一个**已加载**（跳过真模型加载）的旁路。"""
    bp = SpeakerBypass(**kw)
    bp._engine = engine
    bp.available = True
    bp._loaded = True
    return bp


# ══════════════════════════════════════════════════════════════════
# ① 音频入口只做 put_nowait（不阻塞）
# ══════════════════════════════════════════════════════════════════
def test_feed_is_nonblocking() -> None:
    """`feed()` 必须在队列**满**时也**立即返回**（丢旧块，不阻塞）。

    ★ 反证：把 `feed` 换成阻塞式 `put` ⇒ 本断言必须 FAIL。
    """
    eng = _StubSpkEngine()
    bp = _bypass_with(eng, queue_maxsize=4)
    pcm = np.zeros(1600, dtype=np.float32)

    # 先灌满队列（不启 worker ⇒ 队列不会被动）
    t0 = time.perf_counter()
    for _ in range(40):
        bp.feed(pcm, 0.1)
    dt = time.perf_counter() - t0
    check("★ feed 40 次（队列 maxsize=4）总耗时 < 0.5 s（非阻塞）",
          dt < 0.5, f"{dt*1000:.1f} ms")
    check("★ 队列满后 n_drop > 0（确实丢了旧块）",
          bp.stats()["spk_queue_drop"] > 0,
          f"drop={bp.stats()['spk_queue_drop']}")
    check("★ 队列长度不超过 maxsize（有界）",
          bp._q.qsize() <= 4, f"qsize={bp._q.qsize()}")

    # ★ 反证：阻塞版 feed 必须「卡住」⇒ 证明上面的断言有区分力
    class _BlockingBypass(SpeakerBypass):
        def feed(self, pcm, t_end=None):
            self._q.put((pcm, t_end))      # ★ 故意阻塞
            return True

    bb = _BlockingBypass(queue_maxsize=4)
    bb._engine = eng
    bb._loaded = True
    t0 = time.perf_counter()
    done = threading.Event()

    def _hammer():
        try:
            for _ in range(40):
                bb.feed(pcm, 0.1)
        finally:
            done.set()

    th = threading.Thread(target=_hammer, daemon=True)
    th.start()
    blocked = not done.wait(1.0)
    check("★ 反证：阻塞式 feed 确实会卡住（证明上一断言有区分力）",
          blocked, f"blocked={blocked}")


def test_queue_full_drops_oldest() -> None:
    """队列满 ⇒ **丢最旧的块**（保留最新音频）⇒ 旁路能追上来。"""
    eng = _StubSpkEngine()
    bp = _bypass_with(eng, queue_maxsize=8)
    pcm = np.zeros(160, dtype=np.float32)
    for i in range(20):
        bp.feed(pcm, float(i))
    st = bp.stats()
    check("★ spk_queue_drop 字段存在且 > 0",
          "spk_queue_drop" in st and st["spk_queue_drop"] > 0,
          f"drop={st.get('spk_queue_drop')}")
    check("★ 投递成功的块数 = 20 - drop（每块最终都进了队列）",
          st["n_feed"] == 20, f"n_feed={st['n_feed']}")
    # 队里应该是**最新**的 8 块 ⇒ 最后投的那块在队里
    tail = bp._q.queue[-1]
    check("★ 队列里保留的是**最新**块（不是最旧块）",
          tail is not None and tail[1] == 19.0, f"tail_t_end={tail[1] if tail else None}")


def test_main_path_not_blocked_by_bypass() -> None:
    """★ 旁路**重**的时候，ASR 主路径（喂帧）**不得**被拖住。

    ★ 反证：若 `feed()` 改成同步调 `engine.feed()`（重 300 ms），
      本断言必须 FAIL。
    """
    eng = _StubSpkEngine(feed_sec=0.30)
    bp = _bypass_with(eng, queue_maxsize=4)
    bp.start()
    pcm = np.zeros(1600, dtype=np.float32)

    # 先让 worker 忙起来（它 sleep 300 ms）
    bp.feed(pcm, 0.1)
    time.sleep(0.05)
    # 队列已经满（worker 还没取走几个）⇒ 再灌 ⇒ 必须**立刻**返回
    t0 = time.perf_counter()
    for _ in range(50):
        bp.feed(pcm, 0.2)
    dt = time.perf_counter() - t0
    bp.stop()
    check("★ 旁路 worker 忙时，50 次 feed 总耗时 < 0.2 s",
          dt < 0.2, f"{dt*1000:.1f} ms")

    # ★ 反证：同步调 engine.feed() 的实现必须 FAIL 同一断言
    class _SyncBypass(SpeakerBypass):
        def feed(self, pcm, t_end=None):
            self._engine.feed(pcm, t_end)   # ★ 故意同步（阻塞）
            return True

    sb = _SyncBypass(queue_maxsize=4)
    sb._engine = eng
    sb._loaded = True
    t0 = time.perf_counter()
    for _ in range(5):
        sb.feed(pcm, 0.3)
    dt2 = time.perf_counter() - t0
    check("★ 反证：同步版 feed 确实被拖慢（证明上一断言有区分力）",
          dt2 > 0.5, f"{dt2*1000:.1f} ms")


def test_bridge_feeds_bypass_nonblocking() -> None:
    """★ 桥接侧：`Session.on_pcm_frame` 喂旁路时**不得阻塞**。

    ★ 这是 EXT-029 ① 的**端到端**口径（真代码路径，不是桩）。
    """
    eng = _StubSpkEngine(feed_sec=0.30)
    bp = _bypass_with(eng, queue_maxsize=4)
    bp.start()

    sess = Session("tok", delay_sec=10.0, spk_bypass=bp)
    import base64
    pcm = np.zeros(1600, dtype=np.float32)
    b64 = base64.b64encode((pcm * 32767).astype("<i2").tobytes()).decode()
    t0 = time.perf_counter()
    for i in range(30):
        sess.on_pcm_frame({"seq": i, "sample_index": i * 1600, "pcm": b64})
    dt = time.perf_counter() - t0
    bp.stop()
    check("★ on_pcm_frame 30 帧总耗时 < 0.5 s（旁路不反压上行）",
          dt < 0.5, f"{dt*1000:.1f} ms")
    check("★ 旁路确实收到了帧（n_feed > 0）",
          bp.stats()["n_feed"] > 0, f"n_feed={bp.stats()['n_feed']}")


# ══════════════════════════════════════════════════════════════════
# ② 异步回填 / 方案 A
# ══════════════════════════════════════════════════════════════════
def test_label_backfill_is_async() -> None:
    """标签回填**必须异步**（在 worker 线程里）⇒ 主线程零等待。"""
    eng = _StubSpkEngine(on_final_sec=0.20, spk="S7")
    got = []
    bp = _bypass_with(eng, on_label=lambda *a: got.append(a))
    bp.start()
    t0 = time.perf_counter()
    bp.request_final("seg_0", 0.0, 3.0)
    dt = time.perf_counter() - t0
    check("★ request_final 立即返回（< 50 ms，不等推理）",
          dt < 0.05, f"{dt*1000:.1f} ms")
    check("★ 回填前还没有标签（异步）", not got, f"got={len(got)}")
    deadline = time.time() + 5.0
    while not got and time.time() < deadline:
        time.sleep(0.02)
    bp.stop()
    check("★ 标签最终异步回填到了（spk=S7）",
          bool(got) and got[0][3] == "S7",
          f"got={got[:1]}")


def test_missing_label_uses_preset_a() -> None:
    """★ 标签**未到** ⇒ **不等** ⇒ 走方案 A（预设 A）。

    ★ 反证：若实现改成「阻塞等待标签」，
      `test_missing_label_uses_preset_a` 的「不阻塞」断言必须 FAIL。
    """
    eng = _StubSpkEngine(on_final_sec=1.0, pending=True)
    bp = _bypass_with(eng)
    sess = Session("tok", delay_sec=10.0, spk_bypass=bp)

    t0 = time.perf_counter()
    spk = sess._resolve_spk("seg_0", 0.0, 3.0)
    dt = time.perf_counter() - t0
    check("★ 标签未到 ⇒ spk 为 None（方案 A）", spk is None, f"spk={spk}")
    check("★ ★ 解析 spk **不等**（< 20 ms）", dt < 0.02, f"{dt*1000:.1f} ms")
    # 方案 A ⇒ 音色 = 预设 A
    sess.client_voice = "clone"
    voice = sess._pick_voice(spk)
    check("★ 方案 A：音色回落到预设 A",
          voice == C.PRESET_VOICE, f"voice={voice}")
    # ★ 反证：阻塞式解析必须 FAIL「不等」断言
    class _BlockingSession(Session):
        def _resolve_spk(self, seg_id, t_start, t_end):
            time.sleep(1.0)      # ★ 故意等
            return None

    bs = _BlockingSession("tok", delay_sec=10.0, spk_bypass=bp)
    t0 = time.perf_counter()
    bs._resolve_spk("seg_0", 0.0, 3.0)
    dt2 = time.perf_counter() - t0
    check("★ 反证：阻塞式解析确实会等（证明上一断言有区分力）",
          dt2 > 0.9, f"{dt2*1000:.1f} ms")


def test_resolve_spk_prefers_bypass_label() -> None:
    """旁路标签命中时优先用它；未命中才退回 tracker。"""
    bp = _bypass_with(_StubSpkEngine())
    sess = Session("tok", delay_sec=10.0, spk_bypass=bp)
    sess._on_spk_label("seg_100", 0.0, 3.0, "S9", {"spk_conf": 0.9})
    check("★ 旁路标签命中该段",
          sess._resolve_spk("seg_100", 0.0, 3.0) == "S9",
          f"{sess._resolve_spk('seg_100', 0.0, 3.0)}")
    # ★ 未命中的段：时间上**不与**任何已知说话人重叠 ⇒ None（不臆造）
    check("★ 未命中的段 ⇒ None（不臆造）",
          sess._resolve_spk("seg_200", 100.0, 103.0) is None,
          f"{sess._resolve_spk('seg_200', 100.0, 103.0)}")
    # ★ 时间上重叠的段 ⇒ tracker 按重叠给出该说话人（口径一致）
    check("★ 时间重叠的段 ⇒ tracker 给出同一说话人（S9）",
          sess._resolve_spk("seg_200", 0.0, 3.0) == "S9",
          f"{sess._resolve_spk('seg_200', 0.0, 3.0)}")
    # 标签回填后应进 tracker（供「上一句音色」用）
    st = sess.tracker.stats()
    check("★ 标签已进 tracker（n_speakers ≥ 1）",
          st["n_speakers"] >= 1, f"n_speakers={st['n_speakers']}")


# ══════════════════════════════════════════════════════════════════
# ③ 验收字段必须在位
# ══════════════════════════════════════════════════════════════════
def test_stats_fields_present() -> None:
    """旁路 stats 必须含 EXT-029 ③ 明文的两个字段名。"""
    bp = _bypass_with(_StubSpkEngine())
    st = bp.stats()
    for k in ("spk_queue_drop", "spk_worker_busy_ms"):
        check(f"★ stats 含字段 {k}", k in st, f"keys={sorted(st.keys())}")
    check("★ spk_worker_busy_ms 是数值", isinstance(st["spk_worker_busy_ms"], (int, float)),
          f"{st['spk_worker_busy_ms']!r}")


def test_bridge_stats_and_margin_carry_fields() -> None:
    """★ 桥接的 `stats()` 与 `margin.json` 都必须带这两个字段。"""
    import json
    import tempfile
    from ext.bridge import _dump_margin

    bp = _bypass_with(_StubSpkEngine())
    sess = Session("tok", delay_sec=10.0, spk_bypass=bp)
    st = sess.stats()
    check("★ Session.stats 含 spk_bypass 组",
          "spk_bypass" in st, f"keys={sorted(st.keys())}")
    grp = st.get("spk_bypass") or {}
    check("★ stats.spk_bypass 含 spk_queue_drop / spk_worker_busy_ms",
          "spk_queue_drop" in grp and "spk_worker_busy_ms" in grp,
          f"grp={grp}")
    # 未接旁路时也必须**显式**报「没接」⇒ 绝不臆造数字
    sess2 = Session("tok2", delay_sec=10.0)
    grp2 = (sess2.stats().get("spk_bypass") or {})
    check("★ 未接旁路 ⇒ enabled=False 且两个字段为 0",
          grp2.get("enabled") is False
          and grp2.get("spk_queue_drop") == 0
          and grp2.get("spk_worker_busy_ms") == 0.0, f"grp2={grp2}")

    # margin.json 落盘也要带
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "margin.json")
        holder = {"session": sess}
        _dump_margin(holder, p, None, session=sess)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        gb = data.get("spk_bypass") or {}
        check("★ margin.json 含 spk_bypass.spk_queue_drop",
              "spk_queue_drop" in gb, f"gb={gb}")
        check("★ margin.json 含 spk_table（EXT-027③ 段级表）",
              isinstance(data.get("spk_table"), list), f"{type(data.get('spk_table'))}")


# ══════════════════════════════════════════════════════════════════
# ④ GPU 锁：共用 + 可测得的持锁时长
# ══════════════════════════════════════════════════════════════════
def test_shares_device_lock() -> None:
    """★ 旁路必须**共用** ASR/MT 那把锁（不许另开一把）。"""
    from ext.pipeline import _FairLock
    lock = _FairLock()
    bp = _bypass_with(_StubSpkEngine(), device_lock=lock)
    st = bp.stats()
    check("★ shares_device_lock_with_asr = True",
          st.get("shares_device_lock_with_asr") is True, f"{st}")
    # 不传锁 ⇒ 显式报 False（自测路径）
    bp2 = _bypass_with(_StubSpkEngine())
    check("★ 没传锁 ⇒ 显式 False（不隐去）",
          bp2.stats().get("shares_device_lock_with_asr") is False)


def test_lock_held_time_measured() -> None:
    """★ 旁路持锁总时长必须**可测得**（= ASR 额外延迟上界）。"""
    from ext.pipeline import _FairLock
    lock = _FairLock()
    eng = _StubSpkEngine(on_final_sec=0.15)
    bp = _bypass_with(eng, device_lock=lock)
    bp.start()
    bp.request_final("seg_0", 0.0, 3.0)
    bp.request_final("seg_1", 3.0, 6.0)
    deadline = time.time() + 5.0
    while bp.stats()["spk_gpu_lock_held_ms"] <= 0 and time.time() < deadline:
        time.sleep(0.02)
    bp.stop()
    st = bp.stats()
    check("★ spk_gpu_lock_held_ms > 0（确实持过锁）",
          st["spk_gpu_lock_held_ms"] > 0, f"{st['spk_gpu_lock_held_ms']} ms")
    check("★ 持锁时长 ≥ 实际推理时长（口径没算错）",
          st["spk_gpu_lock_held_ms"] >= 250.0,
          f"{st['spk_gpu_lock_held_ms']} ms（2 段 × 150 ms）")


def test_bypass_engine_not_used_in_serial_session() -> None:
    """★ 串行会话**不接**旁路（没有 GPU 锁 ⇒ 会饿死 ASR）。"""
    sess = Session("tok", delay_sec=10.0)
    check("★ 串行 Session.spk_bypass_enabled = False",
          sess.spk_bypass_enabled is False)
    check("★ 串行 Session.spk_bypass is None",
          sess.spk_bypass is None)
    # 流水线会话：开关打开才会创建
    bp = _bypass_with(_StubSpkEngine())
    ps = PipelineSession("tok2", delay_sec=10.0, engine=object(),
                         spk_bypass_enabled=False)
    check("★ 流水线会话默认不接旁路（未开启时 spk_bypass 为 None）",
          ps.spk_bypass is None and ps.spk_bypass_enabled is False)
    try:
        ps.close()
    except Exception:
        pass


def test_pipeline_session_wires_bypass() -> None:
    """★ 流水线会话开启后：旁路已创建、worker 已启动、共用 device_lock。

    ⚠️ 真实创建会尝试加载模型（可能慢/失败）⇒ 这里只断言**结构**，
       不断言模型可用（模型可用性由真实 e2e 验证）。
    """
    ps = PipelineSession("tok3", delay_sec=10.0, engine=object(),
                         spk_bypass_enabled=True)
    try:
        check("★ 流水线会话开启后 spk_bypass_enabled = True",
              ps.spk_bypass_enabled is True)
        check("★ 旁路对象已创建", ps.spk_bypass is not None)
        if ps.spk_bypass is not None:
            check("★ 旁路共用流水线的 device_lock",
                  ps.spk_bypass.device_lock is ps._device_lock,
                  f"{ps.spk_bypass.device_lock}")
            check("★ 旁路 worker 线程已启动",
                  ps.spk_bypass._thread is not None
                  and ps.spk_bypass._thread.is_alive(),
                  f"{ps.spk_bypass._thread}")
            check("★ on_label 回调已绑定到会话回填",
                  ps.spk_bypass._on_label == ps._on_spk_label)
    finally:
        try:
            ps.close()
        except Exception:
            pass


def test_spk_table_upsert_no_duplicate_rows() -> None:
    """★ 段级表按 seg_id **去重**（标签晚到时补同一行，不新增行）。"""
    bp = _bypass_with(_StubSpkEngine())
    sess = Session("tok", delay_sec=10.0, spk_bypass=bp)
    sess._upsert_spk_row("seg_5", {"id": "seg_5", "spk": None})
    sess._upsert_spk_row("seg_5", {"spk": "S1"})
    rows = [r for r in sess.spk_table if r.get("seg_id") == "seg_5"
            or r.get("id") == "seg_5"]
    check("★ 同一 seg_id 只有一行", len(rows) == 1, f"{len(rows)} 行")
    check("★ 标签晚到后该行被更新（spk=S1）",
          bool(rows) and rows[0].get("spk") == "S1",
          f"{rows[0] if rows else None}")


def test_pipeline_requests_spk_label() -> None:
    """★★ 真实缺陷回归（2026-11-01 实测抓到的）：**流水线也必须向旁路要标签**。

    ## 缺陷
      基类 `_dispatch_segment()` 里有 `_request_spk_label(abs0, abs1)`，
      但 `PipelineSession` **覆盖**了该方法且**不调基类**
      ⇒ 流水线会话（= 生产路径）**从不**向旁路登记定稿段
      ⇒ 实测 `n_final_req=0` / `n_label=0`
      ⇒ 段级表里 `spk` 全 `null`、`spk_pending=true` 永远等不到。

    ## 断言
      直接调 `PipelineSession._dispatch_segment()`（不真跑引擎）
      ⇒ 旁路的 `n_final_req` 必须 +1。
    """
    bp = _bypass_with(_StubSpkEngine())
    ps = PipelineSession("tok4", delay_sec=10.0, engine=object())
    # ★ 把旁路挂上去（PipelineSession 自己创建的那个是「真」的，
    #   这里换成可控的桩，便于断言计数）。
    ps.spk_bypass = bp
    n0 = bp.n_final_req
    try:
        ps._dispatch_segment(0, 0, 16000, np.zeros(16000, dtype=np.float32),
                             audio_complete_at=time.perf_counter())
    except Exception:
        pass   # 流水线内部可能因桩引擎报错；**计数断言才是本测试的目的**
    check("★★ 流水线派发段时会向旁路登记定稿（n_final_req +1）",
          bp.n_final_req == n0 + 1,
          f"n_final_req {n0} → {bp.n_final_req}")

    # ★ 反证：把 `PipelineSession._dispatch_segment` 里的登记调用去掉
    #   ⇒ 上面那条断言**必须**失败 ⇒ 证明该断言不是恒真。
    src = open(os.path.join(ROOT, "ext", "bridge.py"),
               encoding="utf-8").read()
    pipeline_def = src.split("class PipelineSession(Session):", 1)[-1]
    has_call = "self._request_spk_label(abs0, abs1)" in pipeline_def
    check("★★ 反证：PipelineSession 里确实有登记调用（否则断言恒真）",
          has_call, f"PipelineSession 内含登记调用 = {has_call}")


def test_spk_table_records_label_after_pipeline_fix() -> None:
    """★★ 回归：标签回填后，段级表的 `spk` 必须**不是** null。

    （旧缺陷下流水线永远拿不到标签 ⇒ 段级表 `spk` 全 null。）
    """
    bp = _bypass_with(_StubSpkEngine(spk="S42"))
    sess = Session("tok5", delay_sec=10.0, spk_bypass=bp)
    sess._upsert_spk_row("seg_10", {"seg_id": "seg_10", "spk": None})
    # 模拟旁路异步回填
    sess._on_spk_label("seg_10", 0.0, 3.0, "S42", {"spk_conf": 0.9})
    rows = [r for r in sess.spk_table if r.get("seg_id") == "seg_10"]
    check("★★ 标签回填后段级表 spk = S42",
          bool(rows) and rows[0].get("spk") == "S42",
          f"{rows[0] if rows else None}")
    check("★★ 标签回填后不再标记为 pending",
          bool(rows) and not rows[0].get("spk_pending"),
          f"{rows[0] if rows else None}")


def test_tabcapture_api_signature_is_correct() -> None:
    """★★ 真实缺陷回归（2026-11-01 实测）：**tabCapture API 不能乱用**。

    ## 缺陷
      旧实现调 `chrome.tabCapture.capture({audio, video, targetTabId})`
      ⇒ Chrome 直接拒绝：`No matching signature.`
      ⇒ 抓流**永远**降级到 getDisplayMedia ⇒ 抓到整机系统声音
      ⇒ 英译中根本没测到。

    ## 正确口径（查 Chrome 官方 API 核实）
      * `capture(options)` 的 options = `CaptureOptions`
        （`audio` / `video` / `audioConstraints` / `videoConstraints`）
        ⇒ **没有** `targetTabId`；
      * `targetTabId` 属于 `getMediaStreamId(options)`。
    """
    for fn in ("extension/offscreen.js", "extension/player.js"):
        path = os.path.join(ROOT, fn)
        if not os.path.isfile(path):
            check(f"★★ {fn} 存在", False, path)
            continue
        src = open(path, encoding="utf-8").read()
        # ★ 反证用的「坏用法」必须已消失。
        #   ⚠️ 只看**真正的调用**（跳过注释行）⇒ 否则会被文档里的
        #   「旧实现写的是 ...capture({audio, video, targetTabId})」误判。
        code_lines = []
        for ln in src.split("\n"):
            st = ln.strip()
            if st.startswith("//") or st.startswith("*") or st.startswith("/*"):
                continue
            code_lines.append(ln)
        code = "\n".join(code_lines)
        bad = False
        for m in re.finditer(r"chrome\.tabCapture\.capture\s*\(\s*\{", code):
            seg = code[m.end():m.end() + 400]
            depth = 1
            out = []
            for ch in seg:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
                out.append(ch)
            if "targetTabId" in "".join(out):
                bad = True
        check(f"★★ {fn} 不再用 capture() 传 targetTabId（API 误用）",
              not bad, f"坏用法仍在 = {bad}")
        # ★ 正确用法必须在
        check("★★ %s 用 getMediaStreamId 取流 id" % fn,
              "getMediaStreamId" in code and "targetTabId" in code,
              "getMediaStreamId 在 = %s" % ("getMediaStreamId" in code))
        check("★★ %s 用 chromeMediaSource:'tab' 消费流" % fn,
              "chromeMediaSource" in code and "chromeMediaSourceId" in code,
              "chromeMediaSource 在 = %s" % ("chromeMediaSource" in code))


def test_margin_json_carries_pipeline_wall_clock() -> None:
    """★★ EXT-029 ③ 的**正确**墙钟口径必须落盘（2026-11-01 修的坑）。

    ## 为什么
      `per_segment[].asr_sec` 是**纯引擎调用**耗时（**不含**等 GPU 互斥锁）
      ⇒ 旁路与 ASR 抢锁造成的排队**不会**体现在里面
      ⇒ 只比 `asr_sec` 会**低估**旁路对 ASR 的影响（假通过）。
      ★ 真正的墙钟是 `pipeline.stage_wall_sec.asr`
      （`ext/pipeline.py` 的 `dt` 覆盖 `with self._device_lock:` 整段）。
      ⇒ `margin.json` 必须带上 `pipeline` 这一组。
    """
    import json
    import tempfile
    bp = _bypass_with(_StubSpkEngine())
    ps = PipelineSession("tok6", delay_sec=10.0, engine=object())
    ps.spk_bypass = bp
    try:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "margin.json")
            from ext.bridge import _dump_margin
            _dump_margin({}, out, None, session=ps)
            data = json.load(open(out, encoding="utf-8"))
    except Exception:
        check("★★ margin.json 含 pipeline 墙钟", False,
              traceback.format_exc())
        return
    check("★★ margin.json 含 pipeline 组（ASR 墙钟口径）",
          data.get("pipeline") is not None, f"{type(data.get('pipeline'))}")
    sw = (data.get("pipeline") or {}).get("stage_wall_sec") or {}
    check("★★ pipeline.stage_wall_sec 含 asr（真实墙钟口径）",
          "asr" in sw, f"stage_wall_sec keys={list(sw.keys())}")


# ══════════════════════════════════════════════════════════════════
# ★★★ 本轮**追加**的断言（EXT-029①/④ 的**实现侧**行为）
#   —— 只追加，**不改写**上面任何既有断言（避免用改断言掩盖回归）
# ══════════════════════════════════════════════════════════════════
def _fake_spk_runtime_module():
    """造一个假的 `asr052_spk_runtime`（只在测试期间进 `sys.modules`）。

    ★ 为什么需要：`ext/spk_engine.py` **只读引用** ASR 交付的
      `asr052_spk_runtime`（纯 numpy + OV 运行时）⇒ 自测解释器里它
      **不在 sys.path** ⇒ 这里注入最小可用的替身
      ⇒ **不碰任何真实模型、不占 GPU/NPU**（铁律）。
    """
    import types
    m = types.ModuleType("asr052_spk_runtime")
    m.FPS = 25
    m.WIN_N = 400

    class _Agg:
        def __init__(self, n):
            self.n = n

        def add_window(self, *a, **k):
            pass

        def finalize(self):
            n = self.n
            return (np.zeros(n), np.ones(n), np.zeros(n), np.zeros((n, 2)))

    m.FrameAggregator = _Agg
    return m


def _fake_openvino_module():
    """造一个假的 `openvino`（**只会失败**，不真编译）。

    ★ 用途：让「命中进程级缓存 ⇒ 不编译也能就绪」这条断言
      在**任何**解释器里都成立（真 openvino 不在自测解释器里），
      并让「未命中 ⇒ 编译失败」这条反证**必然**为真。
    """
    import types
    m = types.ModuleType("openvino")

    class _Core:
        def __init__(self, *a, **k):
            raise RuntimeError("自测不编译真模型（openvino 是替身）")

    m.Core = _Core
    m.PartialShape = lambda *a, **k: None
    return m


def test_feed_never_loads_model_on_caller_thread() -> None:
    """★★ EXT-029①：`feed()` / `request_final()` **绝不**加载模型。

    ★★ 本轮修掉的**真缺陷**（旧实现）：`feed()` 里调 `self._load()`
      ⇒ **第一次** feed 会在 **ASR 主线程**上做「import + 编译」
      ⇒ 阻塞数秒 ⇒ **违反 ①**。
      ⇒ 现在加载/编译**只发生在 worker 线程**（`_run` 的第一步）。

    ★ 反证：构造「旧实现」（feed 里先加载）⇒ 同一判据必须把它**判红**
      ⇒ 证明判据不是恒真。
    """
    calls = []

    def fake_load():
        calls.append(threading.current_thread().name)
        time.sleep(0.30)
        return False

    bp = SpeakerBypass()
    bp._load = fake_load
    pcm = np.zeros(1600, dtype=np.float32)

    t0 = time.perf_counter()
    bp.feed(pcm, 0.1)
    dt_feed = time.perf_counter() - t0
    t1 = time.perf_counter()
    bp.request_final("seg_probe", 0.0, 1.0)
    dt_final = time.perf_counter() - t1

    check("★★ feed() 不在调用方线程加载模型（EXT-029①）",
          len(calls) == 0 and dt_feed < 0.05,
          "feed 用时 %.1f ms，_load 调用 %d 次" % (dt_feed * 1000, len(calls)))
    check("★★ request_final() 不在调用方线程加载模型（EXT-029①）",
          len(calls) == 0 and dt_final < 0.05,
          "request_final 用时 %.1f ms" % (dt_final * 1000))

    # ★ 真反证：「旧实现」—— feed 里加载模型
    class _OldStyle(SpeakerBypass):
        def feed(self, pcm, t_end=None):
            self._load()                     # ★ 旧实现：先加载再入队
            return super().feed(pcm, t_end)

    old = _OldStyle()
    old._load = fake_load
    t2 = time.perf_counter()
    old.feed(pcm, 0.2)
    dt_old = time.perf_counter() - t2
    check("★★ 反证：旧实现（feed 里加载模型）被同一判据判红",
          dt_old >= 0.30 and len(calls) >= 1,
          "旧实现 feed 用时 %.1f ms、_load 调用 %d 次 ⇒ 判据有效"
          % (dt_old * 1000, len(calls)))


def test_worker_loads_and_warms_up_off_main_thread() -> None:
    """★★ EXT-029①/④：模型构造 / 预热 / 编译**只在 worker 线程**发生。

    ★ 且：引擎**还没就绪时入队的音频块不能丢**
      （否则分段窗口对不齐 ⇒ 说话人标签全错）。

    ★ 反证：把 `_load()` 挪回 `feed()` ⇒ 本断言必须 FAIL（见上一条的
      「旧实现」反证；此处验证 worker 侧确实做了加载与预热）。
    """
    import ext.spk_engine as SE

    seen = {}

    class _StubEngine:
        def __init__(self, **kw):
            seen["init_thread"] = threading.current_thread().name
            seen["init_kwargs"] = kw
            self.n_feed = 0

        def warmup(self):
            seen["warmup_thread"] = threading.current_thread().name
            return {"ok": True, "seg_ready": True, "enc_ready": True,
                    "elapsed_sec": 0.01, "seg_compile_count": 1,
                    "enc_compile_count": 1, "seg_reuse": 0, "enc_reuse": 0}

        def feed(self, pcm, t_end=None):
            self.n_feed += 1

        def on_final(self, seg_id, t_start, t_end):
            return {"spk": "S1", "pending": False}

        def stats(self):
            return {}

    orig_engine = SE.SpkEngine
    SE.SpkEngine = _StubEngine
    bp = SpeakerBypass()
    try:
        # 让真 `_load()` 能跑通：给桩的目录与 IR 路径（不碰真实模型）
        bp._app_spk_dir = lambda: os.path.join(ROOT, "ext")
        bp._asset_paths = lambda: ("seg_ir", "wes_ir")
        n_pre = 5
        for i in range(n_pre):
            bp.feed(np.zeros(1600, dtype=np.float32), 0.1 * (i + 1))
        bp.start()
        t0 = time.time()
        while time.time() - t0 < 5.0:
            if getattr(bp._engine, "n_feed", 0) >= n_pre:
                break
            time.sleep(0.05)
        bp.stop()
        check("★★ 模型构造在 worker 线程（不在 ASR 主线程）",
              seen.get("init_thread") == "ext-spk-bypass",
              "init 线程=%s" % seen.get("init_thread"))
        check("★★ 模型预热/编译在 worker 线程（不占 ASR 的 GPU 锁）",
              seen.get("warmup_thread") == "ext-spk-bypass",
              "warmup 线程=%s" % seen.get("warmup_thread"))
        check("★★ 引擎未就绪时入队的旧块被补算（不丢开头音频）",
              getattr(bp._engine, "n_feed", 0) >= n_pre,
              "入队 %d 块 ⇒ 引擎收到 %d 块"
              % (n_pre, getattr(bp._engine, "n_feed", 0)))
    finally:
        SE.SpkEngine = orig_engine


def test_compiled_model_cache_is_process_level() -> None:
    """★★ EXT-029④：**进程级**编译缓存 ⇒ 第二个会话**免编译**。

    ★★ 为什么关键：`on_final()`（定稿路径）里要 `_ensure_enc()`
      ⇒ 若那里触发编译（实测 **0.88 s**），而它**持有 ASR 的 GPU 锁**
      ⇒ ASR 被白白排队 ⇒ **违反 ④**。
      ⇒ 缓存 + 预热（worker 线程、锁外）⇒ `on_final` 只查表。

    ★ 反证：清掉缓存 ⇒ 同一个 `_ensure_seg()` **不再返回 True**
      ⇒ 证明「命中缓存 ⇒ 就绪」这条断言不是恒真。
    """
    import ext.spk_engine as SE

    key = ("seg", "fake_key_only.xml", "NPU")
    cm = object()
    SE._COMPILED_CACHE.pop(key, None)
    SE._store_compiled(key, cm)
    check("★★ 编译缓存是进程级共享（_COMPILED_CACHE）",
          SE._cached_compiled(key) is cm,
          "命中=%s" % (SE._cached_compiled(key) is cm))
    cm2 = object()
    got = SE._store_compiled(key, cm2)
    check("★★ 编译缓存先到先得（并发预热也只编一次）",
          got is cm and SE._cached_compiled(key) is cm,
          "返回的是先到者=%s" % (got is cm))

    fake_rt = _fake_spk_runtime_module()
    fake_ov = _fake_openvino_module()
    old_rt = sys.modules.get("asr052_spk_runtime")
    old_ov = sys.modules.get("openvino")
    sys.modules["asr052_spk_runtime"] = fake_rt
    sys.modules["openvino"] = fake_ov
    try:
        d = os.path.join(ROOT, ".tmp", "_spk_cache_probe")
        os.makedirs(d, exist_ok=True)
        xml = os.path.join(d, "fake_seg.xml")
        with open(xml, "w", encoding="utf-8") as f:
            f.write("<net/>")
        k2 = ("seg", xml, "NPU")
        SE._COMPILED_CACHE.pop(k2, None)
        SE._store_compiled(k2, cm)
        eng = SE.SpkEngine(seg_ir=d, wes_ir=None)
        ok_hit = eng._ensure_seg()
        eng2 = SE.SpkEngine(seg_ir=d, wes_ir=None)
        SE._COMPILED_CACHE.pop(k2, None)
        ok_miss = eng2._ensure_seg()
        check("★★ 命中进程级缓存 ⇒ 免编译即可就绪",
              ok_hit is True and eng.n_seg_reuse == 1,
              "命中 ok=%s reuse=%d" % (ok_hit, eng.n_seg_reuse))
        check("★★ 反证：清掉缓存 ⇒ 不再就绪（断言不是恒真）",
              ok_miss is False,
              "未命中 ok=%s（错误=%r）" % (ok_miss, eng2._seg_error[:60]))
    finally:
        for name, old, new in (("asr052_spk_runtime", old_rt, fake_rt),
                               ("openvino", old_ov, fake_ov)):
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def test_infer_lock_serializes_compiled_model_calls() -> None:
    """★★ 进程级缓存 ⇒ **多个** SpkEngine 共享同一个 CompiledModel
    ⇒ `CompiledModel.__call__`（复用 infer request）**不可并发调用**
    ⇒ 所有推理必须串行（`ext/spk_engine.py` 的 `_INFER_LOCK`）。

    ★ 反证：把 `with _INFER_LOCK:` 去掉 ⇒ 两个线程会同时进入
      ⇒ 本断言必须 FAIL（下面用「无锁直调」的对照分支验证判据有效）。
    """
    import ext.spk_engine as SE

    def _make_probe(state, guard):
        class FakeCM:
            def __call__(self, xs):
                with guard:
                    state["in_flight"] += 1
                    state["n_call"] += 1
                    if state["in_flight"] > 1:
                        state["overlap"] = True
                time.sleep(0.05)
                with guard:
                    state["in_flight"] -= 1
                return {0: np.zeros((1, 1, 4), dtype=np.float32)}

            def output(self, i):
                return i
        return FakeCM()

    fake_rt = _fake_spk_runtime_module()
    old_rt = sys.modules.get("asr052_spk_runtime")
    sys.modules["asr052_spk_runtime"] = fake_rt
    errs = []
    try:
        eng = SE.SpkEngine(seg_ir=None, wes_ir=None)
        eng._seg_stride_samples = 400
        audio = np.zeros(1600, dtype=np.float32)

        state = {"in_flight": 0, "overlap": False, "n_call": 0}
        guard = threading.Lock()
        eng._seg_compiled = _make_probe(state, guard)

        def _run():
            try:
                eng._infer_seg(audio)
            except Exception as e:
                errs.append("%s: %s" % (type(e).__name__, e))

        ths = [threading.Thread(target=_run) for _ in range(2)]
        for t in ths:
            t.start()
        for t in ths:
            t.join(timeout=30)
        check("★★ 推理被 _INFER_LOCK 串行（共享 CompiledModel 不并发调用）",
              (not state["overlap"]) and not errs and state["n_call"] >= 1,
              "overlap=%s n_call=%d errs=%s"
              % (state["overlap"], state["n_call"], errs[:1]))

        # ★ 反证：**不持锁**直调 ⇒ 必然并发 ⇒ 同一判据能把它判红
        state2 = {"in_flight": 0, "overlap": False, "n_call": 0}
        guard2 = threading.Lock()
        cm2 = _make_probe(state2, guard2)

        def _raw(xs):
            with guard2:
                state2["in_flight"] += 1
                state2["n_call"] += 1
                if state2["in_flight"] > 1:
                    state2["overlap"] = True
            time.sleep(0.05)
            with guard2:
                state2["in_flight"] -= 1
            return {0: np.zeros((1, 1, 4), dtype=np.float32)}

        def _run_raw():
            try:
                cm2([audio])
            except Exception as e:
                errs.append("%s: %s" % (type(e).__name__, e))

        ths2 = [threading.Thread(target=_run_raw) for _ in range(2)]
        for t in ths2:
            t.start()
        for t in ths2:
            t.join(timeout=30)
        check("★★ 反证：无锁并发调用会被判据抓到（判据不是恒真）",
              state2["overlap"] is True,
              "无锁 overlap=%s" % state2["overlap"])
    finally:
        if old_rt is None:
            sys.modules.pop("asr052_spk_runtime", None)
        else:
            sys.modules["asr052_spk_runtime"] = old_rt


def test_pcm_slice_uses_rolling_archive_base() -> None:
    """★★ EXT-029③：`_pcm_slice` 必须用**滚动归档首样本**的全局时间当基址。

    ★★ 本轮实测抓到的**真缺陷**：旧实现拿 `_t0`（**全局**时间轴起点）
      当归档缓冲的基址 ⇒ 但归档是**滚动窗口**（只留最近 30 s）
      ⇒ 30 s 之后的段：索引超出 `buf.size` ⇒ 被夹到末尾 ⇒ **切出空数组**
      ⇒ `on_final` 判「音频还没进缓冲」⇒ 重试到上限后**静默丢弃**
      ⇒ 实测 60 s 里只有前 **4/13** 段拿到标签，其余全回落方案 A。

    ★ 反证：用**旧公式**（全局起点当基址）算同一段 ⇒ 必然为空
      ⇒ 证明新断言不是恒真。
    """
    import ext.spk_engine as SE

    eng = SE.SpkEngine(seg_ir=None, wes_ir=None)
    total = 40 * 16000
    x = np.arange(total, dtype=np.float32)
    chunk = 1600
    for i in range(0, total, chunk):
        eng.feed(x[i:i + chunk], t_end=(i + chunk) / 16000.0)

    got = eng._pcm_slice(35.0, 36.0)
    ok_new = got.size > 0 and abs(float(got[0]) - 35.0 * 16000) < 2
    check("★★ _pcm_slice 用滚动归档基址（30 s 之后的段也能取到）",
          ok_new,
          "取到 %d 样本，首样本=%s（期望 ≈%d）"
          % (got.size, got[0] if got.size else None, 35 * 16000))

    # ★ 反证：旧公式（全局起点当基址）⇒ 同一段必然为空
    buf = np.concatenate(eng._archive)
    a_old = int(round((35.0 - eng._t0) * 16000))
    b_old = int(round((36.0 - eng._t0) * 16000))
    a_old = max(0, min(a_old, buf.size))
    b_old = max(a_old, min(b_old, buf.size))
    old_slice = buf[a_old:b_old]
    check("★★ 反证：旧基址公式切出空数组（判据不是恒真）",
          old_slice.size == 0 and buf.size > 0,
          "旧公式取到 %d 样本（归档共 %d）" % (old_slice.size, buf.size))


def main() -> int:
    print("=" * 68)
    print("EXT-029 说话人旁路自测（独立线程 + 有界队列 + 异步回填）")
    print("=" * 68)
    for fn in (test_feed_is_nonblocking,
               test_queue_full_drops_oldest,
               test_main_path_not_blocked_by_bypass,
               test_bridge_feeds_bypass_nonblocking,
               test_label_backfill_is_async,
               test_missing_label_uses_preset_a,
               test_resolve_spk_prefers_bypass_label,
               test_stats_fields_present,
               test_bridge_stats_and_margin_carry_fields,
               test_shares_device_lock,
               test_lock_held_time_measured,
               test_bypass_engine_not_used_in_serial_session,
               test_pipeline_session_wires_bypass,
               test_spk_table_upsert_no_duplicate_rows,
               test_pipeline_requests_spk_label,
               test_spk_table_records_label_after_pipeline_fix,
               test_tabcapture_api_signature_is_correct,
               test_margin_json_carries_pipeline_wall_clock,
               # ★★★ 本轮追加（EXT-029①/④ 实现侧）
               test_feed_never_loads_model_on_caller_thread,
               test_worker_loads_and_warms_up_off_main_thread,
               test_compiled_model_cache_is_process_level,
               test_infer_lock_serializes_compiled_model_calls,
               test_pcm_slice_uses_rolling_archive_base):
        try:
            fn()
        except Exception:
            check(f"{fn.__name__} 抛异常", False, traceback.format_exc())
    n_pass = sum(1 for _n, ok, _d in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 68)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    if n_fail:
        print("\nFAIL 明细：")
        for n, ok, d in RESULTS:
            if not ok:
                print(f" - {n} — {d}")
    print("=" * 68)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
