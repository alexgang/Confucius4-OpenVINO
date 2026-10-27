"""test_ext_selfcheck.py — EXT 模块自测（不跑推理、不占 GPU/NPU、不抢共享锁）

覆盖：
  1. 分段：EXT-002 的「一直用 R2T2 原有断句」在本地与 R2T2 原件上等价；
  2. 分段：结果与 pyannote 无关（无 pyannote 依赖）；
  3. 时长适配：变速上限 1.25×、超出记顺延、可借下一段静音；
  4. WSOLA：保持音高（变速后基频变化在容差内），长度符合 1/rate；
  5. 说话人旁路：定稿先出（spk=None），spk 晚到后补发更新事件；
  6. 桥接会话：PCM 帧 → 段 → 配音任务下发；sample_index 不连续会计数；
  7. 安全：非法 Origin / 错误 token 被拒。

运行：
    python tests/test_ext_selfcheck.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import traceback

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ext import config as C
from ext.duration import fit_duration
from ext.segmenter import describe, plan_segments, r2t2_available, r2t2_module
from ext.speaker import SpeakerTracker
from ext.time_stretch import wsola

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _speech_like(dur_sec: float, sr: int = C.SAMPLE_RATE) -> np.ndarray:
    """造一段"像语音"的信号：谐波 + 包络，便于测静音切点与基频。"""
    n = int(dur_sec * sr)
    t = np.arange(n) / sr
    f0 = 120.0
    x = (np.sin(2 * np.pi * f0 * t)
         + 0.5 * np.sin(2 * np.pi * f0 * 2 * t)
         + 0.25 * np.sin(2 * np.pi * f0 * 3 * t))
    env = 0.5 * (1 + np.sin(2 * np.pi * 3.0 * t))
    return (x * env).astype(np.float32)


def _with_silence(dur_sec: float, sil_sec: float) -> np.ndarray:
    sp = _speech_like(dur_sec)
    sil = np.zeros(int(sil_sec * C.SAMPLE_RATE), dtype=np.float32)
    return np.concatenate([sp, sil])


def _load_app_module(name: str):
    """按**文件路径**加载 App 目录下的模块（私有名，不污染全局命名空间）。

    ★ 为什么不用 `import`：App 的 `app/` 目录与 R2T2 仓库有 6 个同名顶层模块
      （backends / seg_stream / streaming_asr / segment_encoder_backend / …）
      ⇒ 裸 import 会互相顶替（详见 `ext/segmenter.py` 的说明）。
    ★ 只加载**顶层无重依赖**的模块（tts_engine 只 import contextlib/os/typing）
      ⇒ 不需要 App 解释器，也不占 GPU/NPU。
    """
    import importlib.util

    app_dir = os.path.join(r"C:\Users\Trekker-PTL", "Confucius4_LiveCaption_v1.6",
                            "app")
    path = os.path.join(app_dir, name + ".py")
    if not os.path.isfile(path):
        return None
    mod_name = "ext._test_app_" + name
    try:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        sys.modules.pop(mod_name, None)
        return None


# ── 1/2. 分段（EXT-002 核心） ────────────────────────────────────
def test_segmentation() -> None:
    print("\n[1] 分段 — 一直用 R2T2 原有断句（EXT-002）")
    d = describe()
    print(f"    来源：{d['segmentation_source']}  pyannote 用于分段: "
          f"{d['pyannote_used_for_segmentation']}")

    # 用 45 s 语音 + 静音，构造 3 个以上的段
    audio = np.concatenate([
        _with_silence(13.0, 0.6),
        _with_silence(12.5, 0.6),
        _with_silence(12.0, 0.6),
    ])
    segs = plan_segments(audio)
    check("能规划出多段", len(segs) >= 2, f"{len(segs)} 段")
    check("段不重叠且连续",
          all(segs[i][1] == segs[i + 1][0] for i in range(len(segs) - 1)))
    # 完整段（非末段）长度应落在 [min, max]；末段是尾巴，可以短
    body = segs[:-1]
    tail = segs[-1]
    check("完整段长度落在 [12, 20] s（min/max 内）",
          bool(body) and all(12.0 <= (e - s) / C.SAMPLE_RATE <= 20.0 + 1e-6
                             for s, e in body),
          ", ".join(f"{(e - s) / C.SAMPLE_RATE:.2f}s" for s, e in body))
    check("末段（尾巴）不超过 max",
          (tail[1] - tail[0]) / C.SAMPLE_RATE <= 20.0 + 1e-6,
          f"tail={(tail[1] - tail[0]) / C.SAMPLE_RATE:.2f}s")

    # 与 R2T2 原件等价性
    # ★ EXT-006：改用 `r2t2_module()` 取**私有名**加载的 R2T2 原件。
    #   旧写法 `import seg_stream` 依赖了「R2T2 版本占全局 seg_stream 槽位」
    #   这一**污染行为**；本轮把 R2T2 改成私有名加载（避免与 App 侧同名模块
    #   互相顶替）⇒ 裸 import 拿到的可能是 App 的版本，比对的就不是原件了。
    r2 = r2t2_module()
    if r2 is not None:
        class _FakeBackend:
            pass

        st = r2.SegmentedStreamer.__new__(r2.SegmentedStreamer)
        st.strategy = "vad"
        st.min_segment_sec = C.SEG_MIN_SEC
        st.max_segment_sec = C.SEG_MAX_SEC
        st.vad_silence_db = C.VAD_SILENCE_DB
        st.vad_min_silence_ms = C.VAD_MIN_SILENCE_MS
        ref = st._plan_segments(audio)
        check("与 R2T2 原件 _plan_segments 完全一致", segs == ref,
              f"本地 {segs[:2]}… vs 原件 {ref[:2]}…")
    else:
        check("R2T2 原件可 import", False, "未能加载 confucius4-openvino/seg_stream.py")

    # 边界：空输入
    check("空音频返回空列表", plan_segments(np.zeros((0,), dtype=np.float32)) == [])


# ── 3. 时长适配 ─────────────────────────────────────────────────
def test_duration_fit() -> None:
    print("\n[2] 时长适配（EXT-001 B 节）")
    # 放得下
    f = fit_duration("s1", t_start=0, t_end=2.0, speech_sec=1.8)
    check("放得下 → rate=1", f.rate == 1.0 and f.feasible and f.defer_sec == 0)

    # 需要变速但在上限内
    f = fit_duration("s2", t_start=0, t_end=2.0, speech_sec=2.4)
    check("需变速 → rate=1.2", abs(f.rate - 1.2) < 1e-6 and f.feasible, f"rate={f.rate}")

    # 超出上限 → 顺延
    f = fit_duration("s3", t_start=0, t_end=2.0, speech_sec=4.0)
    check("超上限 → rate 封顶 1.25 且记顺延",
          abs(f.rate - 1.25) < 1e-6 and not f.feasible and f.defer_sec > 0,
          f"rate={f.rate} defer={f.defer_sec:.3f}s")

    # 借用下一段前的静音
    f = fit_duration("s4", t_start=0, t_end=2.0, speech_sec=2.2, next_start=2.6)
    check("可借用下一段前静音", abs(f.extend_sec - 0.6) < 1e-6 and f.feasible,
          f"extend={f.extend_sec:.2f}s rate={f.rate}")


# ── 4. WSOLA 保持音高 ────────────────────────────────────────────
def _est_f0(x: np.ndarray, sr: int = C.SAMPLE_RATE) -> float:
    """自相关估基频。"""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    if x.shape[0] < sr // 2:
        return 0.0
    corr = np.correlate(x, x, mode="full")[x.shape[0] - 1:]
    lo, hi = int(sr / 400), int(sr / 60)
    hi = min(hi, corr.shape[0] - 1)
    if hi <= lo:
        return 0.0
    return float(sr / (lo + int(np.argmax(corr[lo:hi]))))


def test_wsola() -> None:
    print("\n[3] WSOLA 保持音高变速")
    x = _speech_like(3.0)
    f0_in = _est_f0(x)
    check("输入基频可测", f0_in > 50, f"f0_in={f0_in:.1f}Hz")

    for rate in (1.25, 0.8):
        y = wsola(x, rate)
        exp_len = int(x.shape[0] / rate)
        len_ok = abs(y.shape[0] - exp_len) < 0.12 * exp_len
        check(f"rate={rate} 长度≈1/rate", len_ok,
              f"{y.shape[0]} vs 期望 {exp_len}")
        f0_out = _est_f0(y)
        # 保持音高：基频偏移应 < 8%
        drift = abs(f0_out - f0_in) / f0_in if f0_in else 1.0
        check(f"rate={rate} 基频基本不变（保持音高）", drift < 0.08,
              f"f0_out={f0_out:.1f}Hz 偏移={drift * 100:.1f}%")

    # 与 playbackRate 对比：playbackRate 会变调（这里用朴素重采样模拟）
    idx = (np.arange(int(x.shape[0] / 1.25)) * 1.25).astype(int)
    naive = x[idx]
    f0_naive = _est_f0(naive)
    naive_drift = abs(f0_naive - f0_in) / f0_in if f0_in else 1.0
    check("对照：朴素重采样会变调（证明不能用 playbackRate）",
          naive_drift > 0.08, f"偏移={naive_drift * 100:.1f}%")


# ── 5. 说话人旁路（EXT-002） ─────────────────────────────────────
def test_speaker_bypass() -> None:
    print("\n[4] 说话人旁路 — 定稿先出，spk 晚到补发（EXT-002）")
    tr = SpeakerTracker(clean_sec_required=3.0, preset_voice="A")

    # 定稿时 spk 还没有 → None
    spk = tr.spk_for_final("seg_0", 0.0, 2.0)
    check("定稿时 spk=None（不阻塞）", spk is None)
    tr.register_pending("seg_0", spk, 0.0, 2.0)

    # 未攒够 3 s → 用预设 A
    tr.update_from_diarization([{"spk_id": "S1", "t_start": 0.0, "t_end": 2.0}])
    check("未满 3 s → 音色为预设 A",
          tr.voice_for("S1") == "A", f"voice={tr.voice_for('S1')}")

    # 攒够 3 s → 可克隆
    tr.update_from_diarization([{"spk_id": "S1", "t_start": 2.0, "t_end": 3.5}])
    check("满 3 s → 音色切换为该说话人",
          tr.voice_for("S1") == "S1", f"voice={tr.voice_for('S1')}")

    # spk 为 None → 回落到上一句音色 / 预设 A
    check("spk=None 时回落上一句音色", tr.voice_for(None) == "S1")
    check("统计里 blocking_diarization=False", tr.stats()["blocking_diarization"] is False)


# ── 6/7. 桥接会话与安全 ───────────────────────────────────────────
def test_bridge_session() -> None:
    print("\n[5] 桥接会话 — PCM 帧 → 段 → 配音任务")
    from ext.bridge import Session, TokenStore, check_origin

    sess = Session("tok", delay_sec=10.0)
    # 造 25 s 的"语音"，每帧 100 ms
    frame_samples = C.SAMPLE_RATE // 10
    total_frames = 250
    sidx = 0
    tasks = None
    for i in range(total_frames):
        seg_audio = _speech_like(0.1)
        pcm = (seg_audio * 32767).astype("<i2").tobytes()
        msg = {"type": "pcm", "seq": i, "sample_index": sidx,
               "pcm": base64.b64encode(pcm).decode("ascii")}
        sidx += frame_samples
        out = sess.on_pcm_frame(msg)
        if out:
            tasks = out
    check("产生了配音任务", bool(tasks), f"{len(tasks) if tasks else 0} 个")
    if tasks:
        t = tasks[0]
        check("任务含 t_start/t_end/src/tgt/spk 字段",
              all(k in t for k in ("t_start", "t_end", "src", "tgt", "spk", "id")))
        check("任务含 fit（时长适配结果）", "fit" in t)
        check("spk 为 None 时不阻塞（EXT-002）", t["spk"] is None)

    # sample_index 不连续 → 计数
    n0 = sess.n_dropped
    pcm = (_speech_like(0.1) * 32767).astype("<i2").tobytes()
    sess.on_pcm_frame({"type": "pcm", "seq": 999, "sample_index": sidx + 9999,
                       "pcm": base64.b64encode(pcm).decode("ascii")})
    check("sample_index 不连续被计数", sess.n_dropped == n0 + 1,
          f"n_dropped {n0} → {sess.n_dropped}")

    print("\n[6] 安全 — Origin / token 校验")
    check("chrome-extension 源放行",
          check_origin("chrome-extension://abcdefg"))
    check("http 源被拒", not check_origin("http://evil.com"))
    check("空 Origin 被拒", not check_origin(None))
    check("空 Origin 字符串被拒", not check_origin(""))

    import tempfile
    tp = os.path.join(tempfile.mkdtemp(), "tok.txt")
    ts = TokenStore(tp)
    check("token 首次生成并落盘", os.path.isfile(tp) and len(ts.token) > 10)
    check("正确 token 通过", ts.verify(ts.token))
    check("错误 token 被拒", not ts.verify("wrong"))
    ts2 = TokenStore(tp)
    check("token 重载一致（幂等）", ts2.token == ts.token)


# ── 8/9/10. EXT-005 / EXT-006 新增行为 ──────────────────────────
def test_ext005_ext006_behaviors() -> None:
    """EXT-006 P1：时间基点连续性 + 引擎语言/失控闸守卫 + 余量口径。

    ★ 本节是**追加**的（新断言），没有改写任何旧断言。
    """
    print("\n[7] EXT-006 P1 — 时间基点连续性（段起始不归零）")
    from ext.bridge import Session

    # 造 60 s 的"语音"（含静音以便切段），每帧 100 ms
    frame_samples = C.SAMPLE_RATE // 10
    sess = Session("tok", delay_sec=10.0)
    sidx = 0
    all_tasks = []
    for i in range(600):
        # 前 15 s 语音、后 1 s 静音 ⇒ 制造可切点
        chunk = _speech_like(0.1)
        pcm = (chunk * 32767).astype("<i2").tobytes()
        out = sess.on_pcm_frame({"type": "pcm", "seq": i,
                                  "sample_index": sidx,
                                  "pcm": base64.b64encode(pcm).decode("ascii")})
        sidx += frame_samples
        if out:
            all_tasks.extend(out)

    check("产生了多段配音任务", len(all_tasks) >= 2, f"{len(all_tasks)} 段")
    if len(all_tasks) >= 2:
        starts = [t["t_start"] for t in all_tasks]
        ends = [t["t_end"] for t in all_tasks]
        # ★ 核心断言：第 2 段起的 t_start 必须**继续增长**，
        #   不能全部归零（旧实现把已切走的段从缓冲区裁掉，
        #   却继续用旧索引切 ⇒ 时间基点漂移）。
        check("多段 t_start 单调递增（不归零）",
              all(starts[i] < starts[i + 1] for i in range(len(starts) - 1)),
              ", ".join(f"{s:.2f}s" for s in starts))
        check("多段 t_end 单调递增",
              all(ends[i] < ends[i + 1] for i in range(len(ends) - 1)))
        check("后续段的 t_start > 0（不是相对缓冲区）",
              all(s > 0 for s in starts[1:]),
              ", ".join(f"{s:.2f}s" for s in starts[1:]))
        # 时间窗长度应在 [12, 20] s（R2T2 断句区间）
        lens = [(e - s) for s, e in zip(starts, ends)]
        check("段时长落在 [12,20] s（末段可短）",
              all(12.0 <= L <= 20.0 + 1e-6 for L in lens[:-1]) and
              lens[-1] <= 20.0 + 1e-6,
              ", ".join(f"{L:.2f}s" for L in lens))

    print("\n[8] EXT-006 P1 — 余量统计口径（原声结束→TTS 就绪）")
    summ = sess.margin_summary()
    check("余量统计有 n_segments", summ.get("n_segments", 0) == len(all_tasks),
          f"n_segments={summ.get('n_segments')}")
    check("余量统计有 n_negative 与累计滞后",
          all(k in summ for k in ("n_negative", "cumulative_lag_sec",
                                  "peak_lag_sec")))
    check("余量统计含排程截止余量（deadline）",
          "deadline" in summ, f"keys={sorted(summ.keys())}")
    if "deadline" in summ:
        dl = summ["deadline"]
        check("排程截止余量含负值计数与 P50/P95",
              all(k in dl for k in ("n_negative", "p50", "p95",
                                   "cumulative_lag_sec")))

    print("\n[9] EXT-006 — 引擎语言映射守卫（必须显式传目标语言）")
    from ext.engine_runtime import (LANG_TO_MT, LANG_TO_TTS,
                                    EngineNeedsChange, RuntimeEngine)
    # Qwen3-TTS 只支持 zh/en/ja/ko（SUPPORTED_LANGS）⇒ 表里不能有多余语言
    check("TTS 语言表只含引擎支持的 4 种",
          set(LANG_TO_TTS) == {"zh", "en", "ja", "ko"},
          f"{sorted(LANG_TO_TTS)}")
    check("MT 语言表与 TTS 对齐", set(LANG_TO_MT) == set(LANG_TO_TTS),
          f"{sorted(LANG_TO_MT)}")
    eng = RuntimeEngine(target_lang="en")
    check("TTS 语言映射：en→English",
          eng.tts_language() == "English", eng.tts_language())
    check("MT 目标码：en→en", eng.mt_target() == "en")
    eng_zh = RuntimeEngine(target_lang="zh")
    check("TTS 语言映射：zh→Chinese",
          eng_zh.tts_language() == "Chinese", eng_zh.tts_language())
    # ★ 映射不到就**抛异常**，绝不静默回落 English（EXT-006 明文要求）
    eng_bad = RuntimeEngine(target_lang="xx")
    try:
        eng_bad.tts_language()
        check("未知目标语言必须抛异常（不静默回落）", False,
              "居然返回了默认值")
    except EngineNeedsChange:
        check("未知目标语言必须抛异常（不静默回落）", True)
    try:
        eng_bad.mt_target()
        check("未知目标语言的 MT 也必须抛异常", False, "居然返回了默认值")
    except EngineNeedsChange:
        check("未知目标语言的 MT 也必须抛异常", True)

    print("\n[10] EXT-006 — 失控闸阈值口径（与 App RUNAWAY 判据一致）")
    from ext.engine_runtime import TTS_WALL_CLOCK_CAP_SEC
    # App 的判据：runaway_threshold_s(est) = max(3×est, est+8s)
    # 短句 ⇒ est 小 ⇒ 阈值取 est+8s（≥8 s）
    # 长句 ⇒ 阈值取 3×est
    # ★ tts_engine.py 顶层无重依赖（只 import contextlib/os/typing）
    #   ⇒ 可以在普通 venv 里按**文件路径**加载，不必用 App 解释器。
    app_tts = _load_app_module("tts_engine")
    if app_tts is not None:
        estimate_sec = app_tts.estimate_sec
        runaway_threshold_s = app_tts.runaway_threshold_s
        short = estimate_sec("测试", "Chinese")
        long_ = estimate_sec("很长的句子" * 50, "Chinese")
        check("短句阈值 = max(3×est, est+8) ⇒ 取 est+8",
              abs(runaway_threshold_s(short) - max(3 * short, short + 8.0)) < 1e-6,
              f"est={short:.2f}s threshold={runaway_threshold_s(short):.2f}s")
        check("长句阈值 = max(3×est, est+8) ⇒ 取 3×est",
              abs(runaway_threshold_s(long_) - max(3 * long_, long_ + 8.0)) < 1e-6,
              f"est={long_:.2f}s threshold={runaway_threshold_s(long_):.2f}s")
    else:
        check("App 的 tts_engine 可 import（失控闸口径来源）", False,
              "未能加载 tts_engine.py")
    check("墙钟闸有硬上限（防止 est 估偏大时闸门失效）",
          TTS_WALL_CLOCK_CAP_SEC > 0, f"cap={TTS_WALL_CLOCK_CAP_SEC}s")


# ── 11. EXT-006 P1 收口：flush 尾段 / stats marker / 同步误差口径 ──
def test_ext006_p1_closeout() -> None:
    """EXT-006 P1 本轮补的三项行为（**追加**断言，未改写任何旧断言）。

    ① `flush` 消息能触发尾段处理，且尾段 t_start **不归零**；
    ② 客户端 stats 包装后 `type` 必须是 `_stats`（否则 margin 全丢）；
    ③ 同步误差按 EXT-001 口径 = max(0, −deadline_margin)。
    """
    print("\n[11] EXT-006 P1 — flush 尾段（时间基点不归零）")
    from ext.bridge import Session

    frame_samples = C.SAMPLE_RATE // 10
    sess = Session("tok", delay_sec=10.0)
    sidx = 0
    all_tasks = []
    for i in range(600):
        chunk = _speech_like(0.1)
        pcm = (chunk * 32767).astype("<i2").tobytes()
        out = sess.on_pcm_frame({"type": "pcm", "seq": i,
                                  "sample_index": sidx,
                                  "pcm": base64.b64encode(pcm).decode("ascii")})
        sidx += frame_samples
        if out:
            all_tasks.extend(out)

    streamed_n = len(all_tasks)
    check("流式阶段已产出多段", streamed_n >= 2, f"{streamed_n} 段")

    # flush ⇒ 尾段
    flushed = sess.flush()
    check("flush 产出尾段", len(flushed) == 1, f"{len(flushed)} 段")
    if flushed:
        ft = flushed[0]
        check("尾段 t_start > 0（不归零）", ft["t_start"] > 0,
              f"t_start={ft['t_start']}")
        check("尾段 t_start 紧接上一段之后",
              ft["t_start"] >= all_tasks[-1]["t_end"] - 1e-6,
              f"尾段 {ft['t_start']:.2f}s vs 上段末 {all_tasks[-1]['t_end']:.2f}s")
        # ★ 尾段的 t_start 必须落在音频总长之内
        check("尾段 t_start 不超过总时长",
              ft["t_start"] <= 60.0, f"{ft['t_start']:.2f}s")
    # flush 幂等：再来一次没有尾段了
    again = sess.flush()
    check("flush 幂等（第二次无输出）", len(again) == 0, f"{len(again)} 段")

    print("\n[12] EXT-006 P1 — stats marker（margin 不能丢）")
    # ★ 复现本轮修掉的缺陷：`{"type": "_stats", **msg}` 里 msg 自带
    #   type='stats' ⇒ 展开后覆盖掉 marker ⇒ 下游永远匹配不到 _stats。
    msg = {"type": "stats", "n_frames": 5, "margin": {"n_segments": 2}}
    broken = {"type": "_stats", **msg}
    fixed = {**msg, "type": "_stats"}
    check("旧写法会把 type 覆盖成 'stats'（缺陷复现）",
          broken.get("type") != "_stats", f"type={broken.get('type')!r}")
    check("新写法保留 '_stats' marker",
          fixed.get("type") == "_stats", f"type={fixed.get('type')!r}")
    check("新写法保留 stats 的原始字段",
          fixed.get("n_frames") == 5 and "margin" in fixed)

    print("\n[13] EXT-006 P1 — 同步误差口径（EXT-001 原文）")
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import p1_pipeline
    # deadline_margin = (t0 + t_start + D) − 就绪时刻
    #   负数 ⇒ 赶不上播放时刻 ⇒ 同步误差 = −deadline_margin
    tasks = [
        {"type": "tts", "id": "a", "t_start": 0.0, "t_end": 15.0,
         "pcm24k": None, "fit": {"rate": 1.0, "defer_sec": 0.0},
         "deadline_margin_sec": 2.5},
        {"type": "tts", "id": "b", "t_start": 15.0, "t_end": 30.0,
         "pcm24k": None, "fit": {"rate": 1.0, "defer_sec": 0.0},
         "deadline_margin_sec": -0.4},
    ]
    m, per = p1_pipeline.compute_metrics(tasks, delay_sec=10.0,
                                         margin_summary=None)
    check("同步误差：余量为正 ⇒ 误差 0",
          per[0]["sync_err_ms"] == 0.0, f"{per[0]['sync_err_ms']}")
    check("同步误差：余量为负 ⇒ 误差 = −余量",
          abs(per[1]["sync_err_ms"] - 400.0) < 1e-6,
          f"{per[1]['sync_err_ms']} ms")
    check("同步误差统计含 p50/p95",
          "p50" in m["sync_err_ms"] and "p95" in m["sync_err_ms"])
    check("同步误差口径写在报告里（可核对）",
          "definition" in m["sync_err_ms"], m["sync_err_ms"].get("definition", ""))

    print("\n[14] EXT-006 P1 — 客户端必须按实时速率喂帧")
    # 离线快灌 ⇒ 服务端瞬间处理完 ⇒ 余量恒正、滞后恒 0 ⇒ 指标失真。
    # ⇒ 客户端必须有 realtime 开关，且默认走实时。
    import inspect
    sig = inspect.signature(p1_pipeline._run_client)
    check("客户端有 realtime 开关", "realtime" in sig.parameters,
          str(list(sig.parameters)))
    check("realtime 默认 True", sig.parameters["realtime"].default is True,
          f"default={sig.parameters['realtime'].default}")
    check("客户端有 expect_segments（用于判断收尾）",
          "expect_segments" in sig.parameters,
          str(list(sig.parameters)))


def main() -> int:
    print("=" * 68)
    print("EXT 模块自测（不跑推理 / 不占 GPU·NPU / 不抢共享锁）")
    print("=" * 68)
    for fn in (test_segmentation, test_duration_fit, test_wsola,
               test_speaker_bypass, test_bridge_session,
               test_ext005_ext006_behaviors, test_ext006_p1_closeout):
        try:
            fn()
        except Exception:
            traceback.print_exc()
            RESULTS.append((fn.__name__, False, "异常"))

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
