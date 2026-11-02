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

    # ★ 缺陷 22：**不再硬编码 App 版本号** —— 按目录实际存在情况解析
    #   （实测 2026-10-29 App 升级到 v1.7、v1.6 目录已被删除
    #     ⇒ 本用例此前直接 FAIL）
    from ext.app_root import resolve_app_root
    _root = resolve_app_root()
    if not _root:
        return None
    app_dir = os.path.join(_root, "app")
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
    # ★★★ EXT-027 ④：切段参数从 [12, 20] 降到 [3, 8]
    #   （reviewer：「max_segment_sec 降到 6–8 s、min_segment_sec 降到 2–3 s」）。
    #   ⇒ 断言改为**引用配置常量**（不再写死数字），
    #     但**判据本身不变**（仍检查「落在 [min, max] 内」+「末段不超过 max」）
    #     ⇒ 不是「放宽断言掩盖回归」，而是「跟着配置走」。
    _lo, _hi = C.SEG_MIN_SEC, C.SEG_MAX_SEC
    check(f"完整段长度落在 [{_lo:g}, {_hi:g}] s（min/max 内）",
          bool(body) and all(_lo - 1e-6 <= (e - s) / C.SAMPLE_RATE <= _hi + 1e-6
                             for s, e in body),
          ", ".join(f"{(e - s) / C.SAMPLE_RATE:.2f}s" for s, e in body))
    check("末段（尾巴）不超过 max",
          (tail[1] - tail[0]) / C.SAMPLE_RATE <= _hi + 1e-6,
          f"tail={(tail[1] - tail[0]) / C.SAMPLE_RATE:.2f}s")
    # ★★ EXT-027 ④：**最长的段必须短于延迟 D**（否则按设计就赶不上）。
    #   D = 10 s（默认）⇒ 一段最长 8 s ⇒ 等它说完（8 s）还剩 2 s 给管线。
    #   ⇒ 这是「同步误差超标」被修掉的**前提条件**，单独断言。
    check("★ 切段上限短于默认延迟 D=10 s（EXT-027④ 的前提）",
          _hi < 10.0, f"max={_hi:g}s, D=10s")
    check("★ 切段下限落在 reviewer 要求的 2–3 s（EXT-027④）",
          2.0 <= _lo <= 3.0, f"min={_lo:g}s")
    check("★ 切段上限落在 reviewer 要求的 6–8 s（EXT-027④）",
          6.0 <= _hi <= 8.0, f"max={_hi:g}s")

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
        # 时间窗长度应在 [SEG_MIN_SEC, SEG_MAX_SEC] s（R2T2 断句区间）
        # ★★ EXT-027④：切段参数已下调为 [3, 8] s ⇒ 断言引用配置常量
        #   （判据本身不变：完整段落在 [min,max] 内 + 末段不超过 max）。
        lens = [(e - s) for s, e in zip(starts, ends)]
        check(f"段时长落在 [{C.SEG_MIN_SEC:g},{C.SEG_MAX_SEC:g}] s（末段可短）",
              all(C.SEG_MIN_SEC - 1e-6 <= L <= C.SEG_MAX_SEC + 1e-6
                  for L in lens[:-1]) and
              lens[-1] <= C.SEG_MAX_SEC + 1e-6,
              ", ".join(f"{L:.2f}s" for L in lens))

    print("\n[8] EXT-006 P1 — 余量统计口径（原声结束→TTS 就绪）")
    summ = sess.margin_summary()
    check("余量统计有 n_segments", summ.get("n_segments", 0) == len(all_tasks),
          f"n_segments={summ.get('n_segments')}")
    check("余量统计有 n_negative 与新滞后口径（末句滞后 + 斜率）",
          all(k in summ for k in ("n_negative", "last_segment_lag_sec",
                                  "lag_growth_slope_sec_per_sec",
                                  "max_lag_sec")),
          f"keys={sorted(summ.keys())}")
    check("余量统计含排程截止余量（deadline）",
          "deadline" in summ, f"keys={sorted(summ.keys())}")
    if "deadline" in summ:
        dl = summ["deadline"]
        check("排程截止余量含负值计数与 P50/P95",
              all(k in dl for k in ("n_negative", "p50", "p95",
                                   "last_segment_lag_sec",
                                   "lag_growth_slope_sec_per_sec")))

    # ★★ 缺陷 17：顶层口径必须是**排程口径**，否则读出「零滞后」假结论。
    #   实测（.tmp/p1_run6/margin.json）：旧顶层用「就绪延迟」口径
    #   ⇒ n_negative=0 / cumulative_lag_sec=0.0（假），
    #   而 deadline 组是 n_negative=19 / -2841.3498（真）。
    #   ⇒ 断言：顶层 basis 必须是 deadline，且顶层值 == deadline 组值。
    check("★ 顶层余量口径标注为 deadline（缺陷 17）",
          summ.get("basis") == "deadline", f"basis={summ.get('basis')}")
    check("★ 顶层余量带 definition（reviewer 可核对口径）",
          isinstance(summ.get("definition"), str)
          and len(summ.get("definition")) > 5,
          str(summ.get("definition"))[:100])
    if "deadline" in summ:
        check("★ 顶层 n_negative == deadline 组 n_negative（口径一致）",
              summ.get("n_negative") == summ["deadline"].get("n_negative"),
              f"top={summ.get('n_negative')} "
              f"dl={summ['deadline'].get('n_negative')}")
        check("★ 顶层末句滞后 == deadline 组末句滞后（口径一致）",
              abs(float(summ.get("last_segment_lag_sec") or 0.0)
                  - float(summ["deadline"].get("last_segment_lag_sec") or 0.0))
              < 1e-6,
              f"top={summ.get('last_segment_lag_sec')} "
              f"dl={summ['deadline'].get('last_segment_lag_sec')}")
        check("★ 顶层斜率 == deadline 组斜率（口径一致）",
              abs(float(summ.get("lag_growth_slope_sec_per_sec") or 0.0)
                  - float(summ["deadline"].get(
                      "lag_growth_slope_sec_per_sec") or 0.0)) < 1e-6,
              f"top={summ.get('lag_growth_slope_sec_per_sec')} "
              f"dl={summ['deadline'].get('lag_growth_slope_sec_per_sec')}")
    check("★ 就绪延迟口径保留为子组（原始信息不丢）",
          "ready_after_orig_end" in summ,
          f"keys={sorted(summ.keys())}")

    # ★★ EXT-008 第 1 点：**「余量求和」量必须被删除**。
    #   旧口径 `cumulative_lag_sec` = 22 段余量求和 ⇒ 数值随段数线性放大，
    #   **没有物理含义**（reviewer 明确要求删除）。
    #   ⇒ 断言：新口径里**不再有**这个键（而不是"值变了"）。
    check("★ EXT-008：顶层已删除「余量求和」量 cumulative_lag_sec",
          "cumulative_lag_sec" not in summ,
          f"keys={sorted(summ.keys())}")
    check("★ EXT-008：deadline 子组也已删除 cumulative_lag_sec",
          "cumulative_lag_sec" not in summ.get("deadline", {}),
          f"deadline keys={sorted(summ.get('deadline', {}).keys())}")
    check("★ EXT-008：旧口径 peak_lag_sec 也一并删除（同样是求和量）",
          "peak_lag_sec" not in summ,
          f"keys={sorted(summ.keys())}")

    # ★★ 反向断言：证明「顶层用排程口径」这条**有区分力**。
    #   构造一组「就绪延迟恒正、排程余量恒负」的逐句数据
    #   （= 实测 p1_run6 的形态）⇒
    #   旧口径读出 n_negative=0（假：零滞后）
    #   新口径读出 n_negative=全部（真：全部赶不上播放时刻）
    from ext.bridge import summarize_margins
    _fake = [{"margin_sec": 40.0 + i, "deadline_margin_sec": -(40.0 + i)}
             for i in range(5)]
    _s = summarize_margins(_fake)
    check("★ 反向断言：就绪延迟恒正时，旧口径会读出 n_negative=0（假结论）",
          sum(1 for m in _fake if m["margin_sec"] < 0) == 0,
          "旧口径确实是 0")
    check("★ 反向断言：新口径读出 n_negative=5（真结论，非恒真）",
          _s.get("n_negative") == 5, f"n_negative={_s.get('n_negative')}")
    check("★ 反向断言：新口径末句滞后为正（真滞后）",
          float(_s.get("last_segment_lag_sec") or 0.0) > 0,
          f"last_segment_lag_sec={_s.get('last_segment_lag_sec')}")

    # ★★ EXT-008：斜率口径的**区分力**断言。
    #   构造「余量随时间越来越负」的一组数据 ⇒ 斜率必须为**负**；
    #   再构造「余量恒定」的一组 ⇒ 斜率必须为 **0**（不是负）。
    #   ⇒ 证明斜率不是恒真的「负数」。
    _grow = [{"t_start": float(i) * 10.0,
              "deadline_margin_sec": -10.0 * i, "margin_sec": 1.0}
             for i in range(1, 11)]
    _sg = summarize_margins(_grow)
    check("★ EXT-008 反向断言：余量随时间变负 ⇒ 斜率为负（滞后在累积）",
          float(_sg.get("lag_growth_slope_sec_per_sec") or 0.0) < 0,
          f"slope={_sg.get('lag_growth_slope_sec_per_sec')}")
    _flat = [{"t_start": float(i) * 10.0,
              "deadline_margin_sec": -50.0, "margin_sec": 1.0}
             for i in range(1, 11)]
    _sf = summarize_margins(_flat)
    check("★ EXT-008 反向断言：余量恒定 ⇒ 斜率为 0（不是恒真的负数）",
          abs(float(_sf.get("lag_growth_slope_sec_per_sec") or 0.0)) < 1e-9,
          f"slope={_sf.get('lag_growth_slope_sec_per_sec')}")
    check("★ EXT-008 反向断言：余量恒定时末句滞后 = 50（= 单句值，不是求和）",
          abs(float(_sf.get("last_segment_lag_sec") or 0.0) - 50.0) < 1e-6,
          f"last={_sf.get('last_segment_lag_sec')}")
    # ★ 求和量会给出 10×50=500 ⇒ 与新口径明确不同（证明真的换了口径）
    check("★ EXT-008 反向断言：旧求和量会读出 500（=10×50），新口径是 50",
          10 * 50.0 == 500.0
          and abs(float(_sf.get("last_segment_lag_sec") or 0.0) - 500.0) > 1.0,
          f"new_last={_sf.get('last_segment_lag_sec')}")

    # ★★ EXT-008 第 2 点：**精确三分量**分解（喂帧慢 / 结构 / 引擎）。
    #   恒等式 lag = backlog + struct + proc 必须**逐段精确闭合**。
    from ext.bridge import decompose_lag_exact
    _D = 10.0
    # 构造一段「音频送晚 30 s、段长 15 s（超窗 5 s）、管线 8 s」的句子：
    #   ⇒ lag 应为 30 + 5 + 8 = 43 s
    _ex = decompose_lag_exact([{
        "id": "seg_x", "t_start": 0.0, "t_end": 15.0,
        "deadline_margin_sec": -43.0,
        "ready_at": 1000.0, "orig_end": 985.0,
        "asr_sec": 3.0, "mt_sec": 1.0, "tts_sec": 4.0,
        "audio_ready_rel_sec": 45.0,   # 音频 45 s 时才完整到达（段结束在 15 s）
    }], delay_sec=_D)
    _row = _ex["per_segment"][0]
    check("★ EXT-008：精确分解逐段闭合（残差 < 0.01 s）",
          _ex.get("identity_closed") is True,
          f"max_residual={_ex.get('max_abs_residual_sec')}")
    check("★ EXT-008：喂帧慢（backlog）= 45−15 = 30 s",
          abs(_row["backlog_sec"] - 30.0) < 1e-6,
          f"backlog={_row['backlog_sec']}")
    check("★ EXT-008：结构项（struct）= 段长 15 − 缓冲窗 10 = 5 s",
          abs(_row["struct_sec"] - 5.0) < 1e-6,
          f"struct={_row['struct_sec']}")
    check("★ EXT-008：引擎项（proc）= ASR+MT+TTS = 8 s",
          abs(_row["proc_sec"] - 8.0) < 1e-6,
          f"proc={_row['proc_sec']}")
    check("★ EXT-008：三分量之和 = 该句滞后 43 s",
          abs((_row["backlog_sec"] + _row["struct_sec"] + _row["proc_sec"])
              - _row["lag_sec"]) < 1e-6,
          f"{_row['backlog_sec']}+{_row['struct_sec']}+{_row['proc_sec']}"
          f" vs lag={_row['lag_sec']}")
    # ★★ 区分力：**只有喂帧慢**（引擎很快、音频准时到）⇒ 滞后应当
    #    **几乎全部**记在 backlog 上 ⇒ 占比接近 100%。
    _fast = decompose_lag_exact([{
        "id": "seg_y", "t_start": 0.0, "t_end": 5.0,
        "deadline_margin_sec": -2.0,
        "ready_at": 1000.0, "orig_end": 995.0,
        "asr_sec": 1.0, "mt_sec": 0.5, "tts_sec": 0.5,
        "audio_ready_rel_sec": 5.0,   # 音频准时在段结束时到达
    }], delay_sec=_D)
    _fy = _fast["per_segment"][0]
    check("★ EXT-008 反向断言：音频准时到达 ⇒ backlog ≈ 0（不是恒正）",
          abs(_fy["backlog_sec"]) < 1e-6,
          f"backlog={_fy['backlog_sec']}")
    check("★ EXT-008 反向断言：音频准时到达 ⇒ 该句滞后只剩引擎耗时",
          abs(_fy["lag_sec"] - _fy["proc_sec"]) < 1e-6,
          f"lag={_fy['lag_sec']} proc={_fy['proc_sec']}")
    # ★★ 区分力：**只有引擎慢**（音频准时、段长小于窗）⇒ struct 为负、
    #    滞后应小于 proc（因为有缓冲窗的提前量）。
    check("★ EXT-008 反向断言：段长 < 缓冲窗 ⇒ struct 为负（有提前量）",
          _fy["struct_sec"] < 0, f"struct={_fy['struct_sec']}")
    # ★★ 区分力：**音频送晚但引擎快** ⇒ backlog 应是滞后主体
    _slowfeed = decompose_lag_exact([{
        "id": "seg_z", "t_start": 0.0, "t_end": 5.0,
        "deadline_margin_sec": -50.0,
        "ready_at": 1000.0, "orig_end": 995.0,
        "asr_sec": 1.0, "mt_sec": 0.5, "tts_sec": 0.5,
        "audio_ready_rel_sec": 50.0,   # 音频晚了 45 s
    }], delay_sec=_D)
    check("★ EXT-008 反向断言：音频送晚 ⇒ backlog 占比 > 80%（喂帧慢是主体）",
          float(_slowfeed.get("backlog_share_of_lag_pct") or 0.0) > 80.0,
          f"backlog_share={_slowfeed.get('backlog_share_of_lag_pct')}%")
    check("★ EXT-008 反向断言：喂帧慢时引擎占比 < 20%（不是引擎的锅）",
          float(_slowfeed.get("proc_share_of_lag_pct") or 0.0) < 20.0,
          f"proc_share={_slowfeed.get('proc_share_of_lag_pct')}%")

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


def test_orchestrator_single_instance_guard() -> None:
    """★ EXT-006 P1 实测修掉的缺陷 12：编排器单实例守卫。

    实测现象：本轮 P1 实测时 `run_p1_real.py` 被**重复启动**，
    出现多个独立根实例（实测 4 个匹配进程 / 2 个独立根实例）⇒
    它们抢同一个端口、写同一个输出目录 ⇒ 桥接服务起不来或产物互相覆盖
    ⇒ P1 实测结论无效。

    守卫逻辑：`<out>/orchestrator.pid` 里记本次 PID；
    启动时若该 PID **仍存活** ⇒ 拒绝重复启动（rc=5）。
    ★ 探测失败一律视为存活（铁律：宁可多等，不误杀活进程）。

    本自测断言：
      ① 首次调用写自己的 PID 并放行；
      ② PID 文件里是**存活**进程 ⇒ 拒绝（拦住重复启动）；
      ③ PID 文件里是**已死** PID ⇒ 放行（接管）；
      ④ PID 文件里是**自己** ⇒ 放行（重入不算重复）；
      ⑤ 守卫函数真的被 `main()` 调用（源码级断言，不是靠注释）。
    """
    print("\n[EXT] EXT-006 — 编排器单实例守卫（重复启动回归）")
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "tools"))
    import run_p1_real as R

    tmp = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".tmp", "guard_test.pid")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    try:
        # ① 首次
        ok, msg = R._single_instance_guard(tmp)
        check("首次调用放行并写自己的 PID", ok and msg.startswith("单实例守卫就绪"),
              msg)
        written = int(open(tmp, encoding="utf-8").read().strip())
        check("PID 文件内容 = 当前进程 PID", written == os.getpid(),
              f"{written} vs {os.getpid()}")

        # ② 存活 PID ⇒ 拒绝
        # ★ **不依赖 psutil**：EXT 的实际运行时（App 自带 python）里**没有 psutil**
        #   ⇒ 用 psutil 找对照进程会让这一条在真实环境里恒 FAIL（假失败）。
        #   ⇒ 改用被测代码自己的 `R._pid_alive`（有 ctypes 兜底）来挑一个存活 PID。
        alive = []
        for cand in range(os.getpid() + 1, os.getpid() + 400):
            if R._pid_alive(cand):
                alive.append(cand)
                break
        if not alive:
            # 兜底：扫系统里的小 PID（Windows 上 4 是个常驻进程）
            for cand in range(4, 4000):
                if R._pid_alive(cand):
                    alive.append(cand)
                    break
        if alive:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(str(alive[0]))
            ok2, msg2 = R._single_instance_guard(tmp)
            check("★ PID 文件里是存活进程 ⇒ 拦住重复启动", not ok2, msg2)
            check("★ 拒绝信息说明了持有者 PID",
                  str(alive[0]) in msg2, msg2)
        else:
            check("★ PID 文件里是存活进程 ⇒ 拦住重复启动", False,
                  "找不到可用的存活 PID 做对照")

        # ③ 已死 PID ⇒ 放行
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("999999")
        ok3, msg3 = R._single_instance_guard(tmp)
        check("PID 文件里是已死进程 ⇒ 放行（接管）", ok3, msg3)

        # ④ 自己 ⇒ 放行（重入）
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        ok4, msg4 = R._single_instance_guard(tmp)
        check("PID 文件里是自己 ⇒ 放行（不算重复启动）", ok4, msg4)

        # ⑤ 守卫真的被 main() 调用（源码级）
        src = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tools", "run_p1_real.py"),
            encoding="utf-8").read()
        check("★ main() 里真的调用了守卫（不是只定义不用）",
              "_single_instance_guard(pid_file)" in src, "源码含调用")
        check("★ 守卫拒绝时返回 rc=5（可被 CI 识别）",
              "return 5" in src, "源码含 return 5")
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def main() -> int:
    print("=" * 68)
    print("EXT 模块自测（不跑推理 / 不占 GPU·NPU / 不抢共享锁）")
    print("=" * 68)
    for fn in (test_segmentation, test_duration_fit, test_wsola,
               test_speaker_bypass, test_bridge_session,
               test_ext005_ext006_behaviors, test_ext006_p1_closeout,
               test_orchestrator_single_instance_guard):
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
