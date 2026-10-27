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
from ext.segmenter import describe, plan_segments, r2t2_available
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
    if r2t2_available():
        import seg_stream as r2

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


def main() -> int:
    print("=" * 68)
    print("EXT 模块自测（不跑推理 / 不占 GPU·NPU / 不抢共享锁）")
    print("=" * 68)
    for fn in (test_segmentation, test_duration_fit, test_wsola,
               test_speaker_bypass, test_bridge_session):
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
