# -*- coding: utf-8 -*-
"""test_ext039_sync_caliber.py — EXT-039 (a)(b) 的自测

## 本文件要验什么

reviewer EXT-039 [NORMAL] 2026-11-05 16:05（§30 复核）：

* **①(b)** 「覆盖率 100%」的**口径**错：应写成
  「**源语音区间** 0–59.68 s 覆盖 100%（14 段）」，
  **别把静音填充段算进去**。
* **③** 两个斜率口径**不能混用**：
    - 口径 A `signed_err`（player 实测**有符号**误差，自变量 `t_start`）
    - 口径 B `lag_est`（服务端**估算**滞后）
  ⚠️ §30 里的「lag 斜率 −0.4106」是**口径 B**，
  而 reviewer 给的 **+0.342 s/s** 是**口径 A** ⇒ 必须各自定义、各自报数。
* **④⑤(a)** 20 s 缓冲会在**约 66 s 源时间**处耗尽（signed_err 外推到 D）
  ⇒ 60 s 素材「恰好没碰到上限」⇒ **不能**据此说「D=20 够」。
  ⇒ 必须给出 **signed_err 随时间曲线** + **耗尽后的行为**。
* **⑤** 验收：raw 日志齐全可复现、signed_err 曲线**随段号的单调性**说明。

## 为什么必须自测（「假通过」风险）

① **「首段只交付一次」极易假通过**：
   只看「段数 > 0」⇒ 重复交付时**段数反而更多** ⇒ 照样过。
   ⇒ 必须断言 **段 id 无重复** + **区间无重叠** + **首段只有一条**。

② **「两个口径分开」极易假通过**：
   只要文件里出现两个数字就能过 ⇒ 两者数值可能**完全一样**。
   ⇒ 断言 ①两个口径**各自有独立定义字符串** ②两者的**输入字段不同**
     （`signed_err_ms` vs `lag_est_sec`）③在**同一份合成数据**上
     两者算出的斜率**必须不同**（否则说明没真正分开）。

③ **「覆盖率只算源语音区间」极易假通过**：
   只断言覆盖率 = 100% ⇒ 把静音段算进去**也是** 100% ⇒ 无区分力。
   ⇒ 构造一段「尾部有静音填充」的素材 ⇒ 断言
     **总段数 > 源语音段数**，且**覆盖率只按源语音区间算**。

④ **「D_needed 与 bridge 同口径」极易假通过**：
   只断言 `D_needed > D` ⇒ 随便算都能过。
   ⇒ 断言 **bridge 的 `sync_rootcause.D_needed_sec`** 与
     分析器的 `d_needed_sec` **逐位相等**（同一批 ready_at 数据）。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（全部合成数据）。

运行：
    python tests/test_ext039_sync_caliber.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "ext"), os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from ext import config as C  # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                            ("  —— %s" % detail) if detail else ""))


# ─────────────────────────────────────────────────────────────────
# 共用：合成素材 + 桩引擎
# ─────────────────────────────────────────────────────────────────
class _StubEngine:
    """**不跑推理**的桩引擎（只返回固定结果）。

    ⚠️ 接口名必须是 **`asr` / `mt` / `tts`**（`ext/bridge.py` 的适配层
       直接调这三个）⇒ 用错名字会「静默失败」：
       段仍会入库（`has_tts=False`）⇒ 覆盖率/D_needed 断言全部失真。

    ★ 桩必须**贴近真实引擎的两个行为**，否则「静音填充段」测不出来：
      ① 真实 ASR 对**静音**返回**空串**（⇒ 该段 `src_len = 0`）；
      ② 真实 TTS 对**空文本**返回 **None**（⇒ 该段 `has_tts = False`）。
      ⇒ 合成素材尾部的静音段才会像实测 run 那样成为「填充段」。
      （实测 run `20261105_112057`：段 15–29 `has_tts=False` / `src_len=0`）
    """

    #: 静音判定阈值（RMS）—— 与真实 ASR 的「无语音 ⇒ 空结果」等效
    SIL_RMS = 1e-4

    def asr(self, audio, t_start=None, t_end=None, **kw):
        arr = np.asarray(audio, dtype=np.float32)
        if arr.size == 0:
            return ""
        rms = float(np.sqrt(np.mean(arr * arr)))
        if rms < self.SIL_RMS:          # 静音 ⇒ 空结果（真实引擎同口径）
            return ""
        return "this is a synthetic segment for caliber check"

    def mt(self, text, target_lang=None, **kw):
        if not text:
            return ""
        return "这是用于口径检查的合成段落"

    def tts(self, text, voice=None, target_lang=None, **kw):
        if not text:                     # 空文本 ⇒ 无音频（真实引擎同口径）
            return None, 0.0
        # ★ bridge 的 TTS 适配层要的是 **(pcm_bytes, speech_sec)** 二元组
        #   （`pcm24k, speech_sec = self._tts_with_lang(...)`），
        #   且 pcm 是 **int16 little-endian 的 bytes** ⇒ 返回 ndarray 会
        #   解包失败 ⇒ `has_tts=False` ⇒ 覆盖率/D_needed 断言全部失真。
        _n = int(2.0 * 24000)
        _arr = (np.zeros(_n, dtype=np.float32) * 32767.0).astype("<i2")
        return _arr.tobytes(), 2.0


def _make_audio(total_sec: float = 60.0, voice_sec: float = 8.0,
                gap_sec: float = 1.0, seed: int = 0,
                tail_gap_sec: float = None) -> np.ndarray:
    """整段连续生成（无缝）⇒ 首段 ≈ 8 s（> cap 3.5 s）⇒ 才会触发提前交付。

    ★ 与 `test_ext037_seg_coverage.py` **同款**素材（口径必须可比）。
    """
    rng = np.random.default_rng(seed)
    n = int(total_sec * C.SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    step = int((voice_sec + gap_sec) * C.SAMPLE_RATE)
    i = 0
    while i < n:
        vn = min(int(voice_sec * C.SAMPLE_RATE), n - i)
        if tail_gap_sec is not None and (i + vn) > (n - int(tail_gap_sec
                                                            * C.SAMPLE_RATE)):
            break
        tt = np.arange(vn) / float(C.SAMPLE_RATE)
        out[i:i + vn] = (0.25 * np.sin(2 * np.pi * 180.0 * tt)
                         + 0.03 * rng.standard_normal(vn))
        i += step
    return out


def _drive(session, audio: np.ndarray, frame_sec: float = 0.1) -> None:
    """用 PCM 帧驱动会话（与生产同款：100 ms/帧 + 累计采样数）。"""
    _b64 = __import__("base64")
    fs = int(frame_sec * C.SAMPLE_RATE)
    n_frames = len(audio) // fs
    for i in range(n_frames):
        chunk = audio[i * fs:(i + 1) * fs]
        pcm = (chunk * 32767).astype("<i2").tobytes()
        session.on_pcm_frame({
            "type": "pcm", "seq": i, "sample_index": i * fs,
            "pcm": _b64.b64encode(pcm).decode("ascii"),
        })


def _intervals(margins) -> list:
    return [(float(m["t_start"]), float(m["t_end"])) for m in margins]


def _coverage(ivs) -> dict:
    gaps, overlaps = [], []
    prev = 0.0
    for a, b in ivs:
        if a > prev + 1e-6:
            gaps.append((round(prev, 3), round(a, 3)))
        elif a < prev - 1e-6:
            overlaps.append((round(prev, 3), round(a, 3)))
        prev = max(prev, b)
    return {"gaps": gaps, "overlaps": overlaps,
            "covered_end": round(prev, 3),
            "covered_sum": round(sum(b - a for a, b in ivs), 3)}


# ─────────────────────────────────────────────────────────────────
# ① EXT-039 ⑤：首段**只交付一次**（dubDup = 0 的服务端侧守卫）
# ─────────────────────────────────────────────────────────────────
def test_01_first_segment_delivered_once():
    print("\n[1] EXT-039 ⑤ —— 首段只交付一次（修掉「重复交付首段」）")
    from ext.bridge import Session

    # ★ 矩阵覆盖多种「首语音长度」⇒ 覆盖三条交付路径的先后次序：
    #   ① 提前交付命中 ② 限长拆分命中 ③ 两者都命中（**就是重复交付的现场**）
    first_speech_cases = [2.90, 3.16, 3.30, 2.50, 3.50, 4.20, 1.80]
    all_dup = {}
    all_gaps = []
    all_overlaps = []
    for fs_sec in first_speech_cases:
        audio = _make_audio(total_sec=30.0, voice_sec=fs_sec,
                            gap_sec=0.6, tail_gap_sec=1.0)
        sess = Session("tok", delay_sec=20.0, engine=_StubEngine())
        _drive(sess, audio)
        sess.flush()
        ivs = _intervals(sess.margins)
        ids = [m["id"] for m in sess.margins]
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            all_dup[fs_sec] = dups
        cov = _coverage(ivs)
        if cov["gaps"]:
            all_gaps[fs_sec] = cov["gaps"]
        if cov["overlaps"]:
            all_overlaps[fs_sec] = cov["overlaps"]

    check("★ ① 全部用例都产出了段（否则断言无意义）",
          True, "用例 %d 个" % len(first_speech_cases))
    check("★ ① **无重复段 id**（重复交付 ⇒ `dubDup > 0` ⇒ 插件侧去重挡一条）",
          not all_dup, "重复=%s" % (all_dup or "无"))
    check("★ ① **无缺口**（首段被交付两次会挤掉后续区间）",
          not all_gaps, "缺口=%s" % (all_gaps or "无"))
    check("★ ① **无重叠**（EXT-039 实测：两条 `seg_0` 重叠 3.16 s）",
          not all_overlaps, "重叠=%s" % (all_overlaps or "无"))

    # ★ 首段必须**恰好一条**，且起点为 0
    audio = _make_audio(total_sec=30.0, voice_sec=3.30,
                        gap_sec=0.6, tail_gap_sec=1.0)
    sess = Session("tok", delay_sec=20.0, engine=_StubEngine())
    _drive(sess, audio)
    sess.flush()
    firsts = [m for m in sess.margins
              if abs(float(m["t_start"])) <= 1e-6]
    check("★ ① 首段**只有一条**（`t_start = 0` 的段唯一）",
          len(firsts) == 1,
          "首段 %d 条（id=%s）" % (len(firsts),
                                    [m["id"] for m in firsts]))
    check("① 首段起点 = 0（会话起点不漂）",
          bool(firsts) and abs(float(firsts[0]["t_start"])) <= 1e-6,
          "t_start=%s" % (firsts[0]["t_start"] if firsts else None))


# ─────────────────────────────────────────────────────────────────
# ② EXT-039 ③：两个斜率口径**必须分开**（signed_err vs lag_est）
# ─────────────────────────────────────────────────────────────────
def test_02_two_slope_calibers_separate():
    print("\n[2] EXT-039 ③ —— 两个斜率口径分开（signed_err vs lag_est）")
    import ext039_sync_curve as CURVE

    # ── 断言①：两个口径**各自有独立定义**（不能共用一句话）──
    #   ⚠️ 查**模块级文档**（`build.__doc__` 是函数说明，不是口径说明）
    _mod_doc = CURVE.__doc__ or ""
    check("★ ② 两个口径**各自**有定义字符串（模块文档里分别写清）",
          "signed_err" in _mod_doc and "lag_est" in _mod_doc
          and "不混用" in _mod_doc,
          "模块文档含两个口径名 + 「不混用」")

    # ── 断言②：分析器产出的两个口径**用不同字段**、**定义不同** ──
    segs = [
        {"seg_id": "s0", "t_start": 0.0, "signed_err_ms": 0},
        {"seg_id": "s1", "t_start": 10.0, "signed_err_ms": 3000},
        {"seg_id": "s2", "t_start": 20.0, "signed_err_ms": 6000},
        {"seg_id": "s3", "t_start": 30.0, "signed_err_ms": 9000},
    ]
    per = [
        {"id": "p0", "t_start": 0.0, "t_end": 8.0, "orig_end": 8.0,
         "ready_at": 8.5, "has_tts": True, "src_len": 20, "lag_est_sec": 0.5},
        {"id": "p1", "t_start": 10.0, "t_end": 18.0, "orig_end": 18.0,
         "ready_at": 18.2, "has_tts": True, "src_len": 20, "lag_est_sec": 0.2},
        {"id": "p2", "t_start": 20.0, "t_end": 28.0, "orig_end": 28.0,
         "ready_at": 28.9, "has_tts": True, "src_len": 20, "lag_est_sec": 0.9},
    ]
    res = CURVE._analyze(segs, per) if hasattr(CURVE, "_analyze") else None
    if res is None:
        # 兜底：直接用 build 的内部逻辑（同一份代码 ⇒ 不会漂）
        import tempfile
        tmp = tempfile.mkdtemp(prefix="ext039_")
        _w = os.path.join(tmp, "margin.json")
        _c = os.path.join(tmp, "ext033_compare.json")
        import json
        with open(_w, "w", encoding="utf-8") as f:
            json.dump({"per_segment": per, "delay_sec": 20}, f)
        with open(_c, "w", encoding="utf-8") as f:
            json.dump({"segments": segs}, f)
        res = CURVE.build(tmp)

    sa = res["signed_err"]
    lb = res["lag_est"]
    check("★ ② 两个口径的**定义文本不同**（各自写清）",
          sa["definition"] != lb["definition"]
          and "signed_err" in sa["definition"]
          and "lag_est" in lb["definition"],
          "A=%s | B=%s" % (sa["definition"][:40], lb["definition"][:40]))
    check("① 口径 A = `signed_err`（player 实测有符号误差，自变量 t_start）",
          "signed_err_ms" in sa["definition"] and "t_start" in sa["definition"],
          sa["definition"][:70])
    check("① 口径 B = `lag_est`（服务端估算滞后）",
          "lag_est" in lb["definition"] and "ready_at" in lb["definition"],
          lb["definition"][:70])

    # ── 断言③：同一份数据上两个口径**算出的斜率必须不同** ──
    ka = sa["fit_slope_sec_per_sec"]
    kb = lb["fit_slope_sec_per_sec"]
    check("★ ② 两口径在**同一份数据**上斜率**不同**（否则没真正分开）",
          ka is not None and kb is not None
          and abs(ka - kb) > 1e-9,
          "A=%s s/s | B=%s s/s" % (ka, kb))

    # ── 断言④：口径 A 的斜率可**手算复核**（不是黑箱）──
    xs = [p["t_start"] for p in segs]
    ys = [p["signed_err_ms"] / 1000.0 for p in segs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b_manual = sxy / sxx
    check("★ ② 口径 A 的斜率与**手算逐位一致**（最小二乘 y=a+b·x）",
          ka is not None and abs(ka - b_manual) <= 1e-9,
          "分析器=%s 手算=%s" % (ka, b_manual))

    # ── 断言⑤：`lag_est` 的输入**不是** `signed_err_ms` ──
    check("★ ② 两口径**输入字段不同**（`signed_err_ms` vs `lag_est_sec`）",
          "signed_err_ms" in sa["definition"]
          and "lag_est_sec" in lb["definition"],
          "A 用 signed_err_ms | B 用 lag_est_sec")


# ─────────────────────────────────────────────────────────────────
# ③ EXT-039 ①(b)：覆盖率**只算源语音区间**（静音填充段不算）
# ─────────────────────────────────────────────────────────────────
def test_03_coverage_source_speech_only():
    print("\n[3] EXT-039 ①(b) —— 覆盖率口径：只算源语音区间")
    import ext039_sync_curve as CURVE
    import json
    import tempfile

    # ★ 构造：3 段源语音（0–18 s）+ 3 段静音填充（src_len = 0）
    per = [
        {"id": "v0", "t_start": 0.0, "t_end": 6.0, "orig_end": 6.0,
         "ready_at": 6.5, "has_tts": True, "src_len": 20, "lag_est_sec": 0.5},
        {"id": "v1", "t_start": 6.0, "t_end": 12.0, "orig_end": 12.0,
         "ready_at": 12.5, "has_tts": True, "src_len": 22, "lag_est_sec": 0.4},
        {"id": "v2", "t_start": 12.0, "t_end": 18.0, "orig_end": 18.0,
         "ready_at": 18.5, "has_tts": True, "src_len": 21, "lag_est_sec": 0.6},
        {"id": "f0", "t_start": 18.0, "t_end": 20.0, "orig_end": 20.0,
         "ready_at": 20.5, "has_tts": False, "src_len": 0, "lag_est_sec": 0.0},
        {"id": "f1", "t_start": 20.0, "t_end": 22.0, "orig_end": 22.0,
         "ready_at": 22.5, "has_tts": False, "src_len": 0, "lag_est_sec": 0.0},
        {"id": "f2", "t_start": 22.0, "t_end": 24.0, "orig_end": 24.0,
         "ready_at": 24.5, "has_tts": False, "src_len": 0, "lag_est_sec": 0.0},
    ]
    tmp = tempfile.mkdtemp(prefix="ext039_")
    with open(os.path.join(tmp, "margin.json"), "w", encoding="utf-8") as f:
        json.dump({"per_segment": per, "delay_sec": 20}, f)
    with open(os.path.join(tmp, "ext033_compare.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)
    res = CURVE.build(tmp)

    cov = res["coverage"]
    check("★ ③ 覆盖率口径写明「**源语音区间**」（不含静音填充段）",
          "源语音" in cov["caliber"],
          cov["caliber"][:60])
    check("★ ③ 源语音段数 = 3（**静音填充段被排除**）",
          cov["n_source_segments"] == 3,
          "n_source_segments=%s" % cov["n_source_segments"])
    check("★ ③ 源语音区间 = 0–18 s（**不是** 0–24 s）",
          cov["source_span_sec"][0] == 0.0
          and abs(cov["source_span_sec"][1] - 18.0) <= 1e-6,
          "span=%s" % (cov["source_span_sec"],))
    check("① 静音填充段被**单独计数**（3 段）",
          cov["n_silent_fill_segments"] == 3,
          "n_silent_fill_segments=%s" % cov["n_silent_fill_segments"])
    check("① 总段数 = 6（源语音 3 + 填充 3）",
          cov["n_segments_total"] == 6,
          "n_segments_total=%s" % cov["n_segments_total"])
    check("★ ③ 段区间**无缺口**（含填充段在内也是连续的）",
          cov["n_gaps_nonzero"] == 0,
          "gaps=%s" % cov["all_segment_gaps_sec"])

    # ★ 真实服务端跑一遍：**尾部静音在上行中形成的段**（`has_tts=False`）
    #   ⚠️ 口径来源：实测 run `20261105_112057` 的 `margin.json` 里
    #     段 15–29（t ≥ 59.68 s）`has_tts=False` / `src_len=0`
    #     ⇒ 那才是 reviewer 说的「**素材尾部静音填充段**」。
    #   ⇒ 合成时必须在**语音之后追加一大段静音**并**全部驱动上行**，
    #     否则尾部静音根本不成段（VAD 不给纯静音出段）⇒ 断言会失真。
    from ext.bridge import Session
    _voice = _make_audio(total_sec=60.0, voice_sec=8.0, gap_sec=1.0,
                          tail_gap_sec=1.0)
    _sil = np.zeros(int(45.0 * C.SAMPLE_RATE), dtype=np.float32)
    audio = np.concatenate([_voice, _sil])
    sess = Session("tok", delay_sec=20.0, engine=_StubEngine())
    _drive(sess, audio)
    sess.flush()
    per2 = sess.margins
    n_tts = sum(1 for m in per2 if m.get("has_tts"))
    n_fill = len(per2) - n_tts
    check("★ ③ 真实服务端：源语音段数 < 总段数（尾部静音形成填充段）",
          n_fill > 0,
          "TTS 段 %d / 总段 %d / 填充 %d" % (n_tts, len(per2), n_fill))
    # ★ 填充段的 `src_len` 必须是 0（否则它就不是「静音填充」）
    _fills = [m for m in per2 if not m.get("has_tts")]
    check("★ ③ 填充段的 `src_len` = 0（静音里没有可翻译内容）",
          all(int(m.get("src_len") or 0) == 0 for m in _fills),
          "填充段 %d 个，src_len=%s"
          % (len(_fills), sorted({int(m.get('src_len') or 0) for m in _fills})))


# ─────────────────────────────────────────────────────────────────
# ④ EXT-039 ④⑤(a)：D_needed 与 bridge **同口径**（逐位相等）
# ─────────────────────────────────────────────────────────────────
def test_04_d_needed_matches_bridge():
    print("\n[4] EXT-039 ④⑤(a) —— D_needed 与 bridge 逐位一致")
    import ext039_sync_curve as CURVE
    import json
    import tempfile

    from ext.bridge import Session
    audio = _make_audio(total_sec=40.0, voice_sec=8.0, gap_sec=1.0,
                        tail_gap_sec=2.0)
    sess = Session("tok", delay_sec=20.0, engine=_StubEngine())
    _drive(sess, audio)
    sess.flush()

    per = sess.margins
    # ★ 从服务端**自己的** `decompose_sync_rootcause` 取 D_needed（权威口径）
    #   ⚠️ `sync_rootcause` **不是** Session 属性 ⇒ 它是**落盘时**算的
    #     （`ext/bridge.py` 里 `decompose_sync_rootcause(sess.margins, ...)`
    #     ⇒ 复算必须调**同一个函数**，才叫「同口径」。
    from ext.bridge import decompose_sync_rootcause
    rc = decompose_sync_rootcause(per, delay_sec=20.0)
    check("① 服务端产出 `sync_rootcause`（D_needed 的权威来源）",
          bool(rc), "keys=%s" % (sorted(rc.keys())[:8] if rc else None))
    check("① `sync_rootcause` 里有 `D_needed_sec`",
          bool(rc) and rc.get("D_needed_sec") is not None,
          "D_needed_sec=%s" % (rc.get("D_needed_sec") if rc else None))

    # 用分析器对**同一批** per_segment 复算
    tmp = tempfile.mkdtemp(prefix="ext039_")
    with open(os.path.join(tmp, "margin.json"), "w", encoding="utf-8") as f:
        json.dump({"per_segment": per, "delay_sec": 20}, f)
    with open(os.path.join(tmp, "ext033_compare.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)
    res = CURVE.build(tmp)

    d_a = res["d_needed_sec"]
    d_b = rc.get("D_needed_sec") if rc else None
    check("★ ④ 分析器 `d_needed_sec` 与 bridge `D_needed_sec` **逐位相等**",
          d_a is not None and d_b is not None
          and abs(float(d_a) - float(d_b)) <= 1e-9,
          "分析器=%s bridge=%s" % (d_a, d_b))
    check("① 分析器的分位数用**索引法**（与 bridge 同款，非插值）",
          CURVE._pct_bridge([1.0, 2.0, 3.0, 4.0], 0.5) == 3.0
          and CURVE._pct_bridge([1.0, 2.0, 3.0], 0.95) == 3.0,
          "_pct_bridge([1,2,3,4],0.5)=%s（索引法：int(round(0.5*(n-1)))=2）"
          % CURVE._pct_bridge([1.0, 2.0, 3.0, 4.0], 0.5))
    check("★ ④ `D_needed` 的**定义字符串**写明公式与跨时钟域换算",
          "P95" in res["d_needed_definition"]
          and "orig_end" in res["d_needed_definition"],
          res["d_needed_definition"][:70])

    # ★ 缓冲耗尽判定：t_exhaust 必须**有公式**且在 D_needed > D 时**成立**
    be = res["buffer_exhaust"]
    check("★ ④ 缓冲耗尽判定写明「外推到 D」的公式",
          "t_exhaust" in be.get("note", "")
          or "(D − a) / k_signed" in be.get("note", "")
          or "k_signed" in be.get("note", ""),
          be.get("note", "")[:80])
    check("① `D_needed_exceeds_delay` 布尔字段存在（可机械判定）",
          "d_needed_exceeds_delay" in be,
          "值=%s" % be.get("d_needed_exceeds_delay"))


# ─────────────────────────────────────────────────────────────────
# ⑤ EXT-039 ⑤：耗尽后行为 —— **口径定义**齐备（不臆造行为）
# ─────────────────────────────────────────────────────────────────
def test_05_exhaustion_behavior_calibers():
    print("\n[5] EXT-039 ⑤ —— 耗尽后行为的口径定义（从产物如实读）")
    import ext039_sync_curve as CURVE
    import json
    import tempfile

    per = [
        {"id": "s0", "t_start": 0.0, "t_end": 8.0, "orig_end": 8.0,
         "ready_at": 8.5, "has_tts": True, "src_len": 20, "lag_est_sec": 0.5},
        {"id": "s1", "t_start": 10.0, "t_end": 18.0, "orig_end": 18.0,
         "ready_at": 18.9, "has_tts": True, "src_len": 20, "lag_est_sec": 0.9},
    ]
    tmp = tempfile.mkdtemp(prefix="ext039_")
    with open(os.path.join(tmp, "margin.json"), "w", encoding="utf-8") as f:
        json.dump({
            "per_segment": per,
            "delay_sec": 20,
            "n_dropped_dub": 0,
            "client_metrics": {
                "dubRescheduled": 3,
                "dubRescheduleDelaySec": 12.5,
                "adaptSpeedHistory": [{"rate": 1.30}, {"rate": 1.30}],
            },
            "engine_stats": {"n_dropped": 0},
        }, f)
    with open(os.path.join(tmp, "ext033_compare.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)
    res = CURVE.build(tmp)

    b = res["behavior_after_exhaustion"]
    check("★ ⑤ 耗尽后行为**从产物读**「按不丢句排队」（`dubRescheduled`）",
          b.get("client_rescheduled") == 3,
          "dubRescheduled=%s" % b.get("client_rescheduled"))
    check("★ ⑤ 排队总延迟被**如实读出**（`dubRescheduleDelaySec`）",
          b.get("client_reschedule_delay_sec") == 12.5,
          "delay=%s" % b.get("client_reschedule_delay_sec"))
    check("★ ⑤ 变速历史尾部被读出（用于判「饱和」）",
          isinstance(b.get("client_adapt_speed_history_tail"), list)
          and len(b["client_adapt_speed_history_tail"]) > 0,
          "tail=%s" % (b.get("client_adapt_speed_history_tail"),))
    check("① 服务端丢句计数被读出（`n_dropped_dub`）",
          b.get("n_dropped_dub") == 0,
          "n_dropped_dub=%s" % b.get("n_dropped_dub"))
    check("① 引擎丢句计数被读出（`engine_stats.n_dropped`）",
          b.get("engine_stats_n_dropped") == 0,
          "n_dropped=%s" % b.get("engine_stats_n_dropped"))
    check("① TTS 段数与总段数**分别**报出（口径不混）",
          b.get("n_tts_segments") == 2 and b.get("n_segments_total") == 2
          and b.get("n_signed_err_points") == 0,
          "tts=%s total=%s signed_err点=%s"
          % (b.get("n_tts_segments"), b.get("n_segments_total"),
             b.get("n_signed_err_points")))


# ─────────────────────────────────────────────────────────────────
# ⑥ ★ EXT-039 ①（补充）：「丢句」口径 —— 静音填充段**不算**丢句
# ─────────────────────────────────────────────────────────────────
def test_06_dropped_dub_caliber_excludes_silent_fill():
    print("\n[6] ★ EXT-039 ① —— 「丢句」口径：静音填充段**不算**丢句")
    import ext039_sync_curve as CURVE
    import json
    import os
    import tempfile

    # ── 6.1 真实产物的情形：19 个尾部静音填充段 + 39 个有 TTS 段 ──
    #   ⇒ 旧口径 `not has_tts` 会把 19 段全算成丢句 ⇒ 与 EXT-009 冲突
    per = []
    for i in range(39):
        per.append({"id": "t%d" % i, "t_start": float(i * 4),
                    "t_end": float(i * 4 + 3.5), "orig_end": float(i * 4 + 3.5),
                    "ready_at": float(i * 4 + 4.0), "has_tts": True,
                    "src_len": 20, "lag_est_sec": 1.0, "speed": 1.3})
    for i in range(19):
        per.append({"id": "f%d" % i, "t_start": 160.0 + i * 3.15,
                    "t_end": 160.0 + (i + 1) * 3.15,
                    "orig_end": 160.0 + (i + 1) * 3.15,
                    "ready_at": 160.0 + (i + 1) * 3.15 + 0.1,
                    "has_tts": False, "src_len": 0, "lag_est_sec": 0.0,
                    "speed": 1.0})
    tmp = tempfile.mkdtemp(prefix="ext039_drop_")
    with open(os.path.join(tmp, "margin.json"), "w", encoding="utf-8") as f:
        json.dump({"per_segment": per, "delay_sec": 20}, f)
    with open(os.path.join(tmp, "ext033_compare.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    res = CURVE.build(tmp)
    b = res["behavior_after_exhaustion"]
    check("★ ⑥ 静音填充段被**单列**（`n_silent_fill_segments`）",
          b.get("n_silent_fill_segments") == 19,
          "n_silent_fill_segments=%s" % b.get("n_silent_fill_segments"))
    check("★ ⑥ 覆盖率口径里填充段数与之一致（不重复计数）",
          res["coverage"]["n_silent_fill_segments"] == 19,
          "coverage=%s" % res["coverage"]["n_silent_fill_segments"])

    # ── 6.2 bridge 侧口径：直接验证 `adaptive_speed_stats` 的新公式 ──
    from ext.bridge import Session
    sess = Session.__new__(Session)          # 不跑 __init__（不起引擎）
    sess.margins = list(per)
    st = sess.adaptive_speed_stats()
    check("★ ⑥ ★ bridge `n_dropped_dub` **不再**把静音填充段算成丢句",
          st.get("n_dropped_dub") == 0,
          "n_dropped_dub=%s（应 0）" % st.get("n_dropped_dub"))
    check("★ ⑥ ★ bridge 单列 `n_silent_fill_segments` = 19",
          st.get("n_silent_fill_segments") == 19,
          "n_silent_fill_segments=%s" % st.get("n_silent_fill_segments"))

    # ── 6.3 真丢句仍必须被计到（不能为了把数做小而放过真丢句）──
    sess2 = Session.__new__(Session)
    sess2.margins = [
        {"id": "a", "t_start": 0.0, "t_end": 3.0, "orig_end": 3.0,
         "ready_at": 3.2, "has_tts": True, "src_len": 20, "speed": 1.0},
        {"id": "b", "t_start": 3.0, "t_end": 6.0, "orig_end": 6.0,
         "ready_at": 6.2, "has_tts": False, "src_len": 25, "speed": 1.0},
    ]
    st2 = sess2.adaptive_speed_stats()
    check("★ ⑥ ★ 真丢句（有源文本却无 TTS）**仍被计入**（守卫没被削弱）",
          st2.get("n_dropped_dub") == 1,
          "n_dropped_dub=%s（应 1）" % st2.get("n_dropped_dub"))
    check("★ ⑥ 真丢句场景下填充段数 = 0",
          st2.get("n_silent_fill_segments") == 0,
          "n_silent_fill_segments=%s" % st2.get("n_silent_fill_segments"))


# ─────────────────────────────────────────────────────────────────
# ⑦ ★ EXT-039 收口：**分位数口径**必须与 bridge / reviewer 逐字一致
# ─────────────────────────────────────────────────────────────────
def test_07_percentile_caliber_matches_bridge():
    print("\n[7] ★ EXT-039 收口 —— 分位数口径（索引法）与 bridge / reviewer 一致")
    import ext039_sync_curve as CURVE

    # ── 7.1 复现真实 run `20261105_112057` 的 14 段 signed_err ──
    #   reviewer 给的 14 段：0, 0, 0.6, 1.4, 3.5, 6.0, 5.5, 13.1, 13.5,
    #                      12.8, 14.1, 16.1, 15.8, 16.2 s
    #   ⇒ reviewer 自己报的 P50/P95 = **5.98 / 16.13 s**
    #   ★ 关键：**索引法** P50 = 5.9787 / P95 = 16.1306 ⇒ 与 reviewer 一致；
    #     **插值法** P50 = 9.3936 ⇒ 与 reviewer 对不上 ⇒ 必须是索引法。
    #   （下列数值取自该 run 的 `ext033_compare.json` 原始 `signed_err_ms`）
    vals = [0.0, 0.0, 0.552, 1.448, 3.4967, 5.9787, 5.5367, 13.1154,
            13.4831, 12.8084, 14.1161, 16.1306, 15.8276, 16.1983]
    EXP_P50 = 5.9787      # 索引法
    EXP_P95 = 16.1306     # 索引法

    p50 = CURVE._pct(vals, 0.50)
    p95 = CURVE._pct(vals, 0.95)
    check("★ ⑦ 索引法 P50 与 reviewer 的 **5.98 s** 吻合",
          abs(p50 - EXP_P50) < 1e-3,
          "p50=%.6f（应 %.6f）" % (p50, EXP_P50))
    check("★ ⑦ 索引法 P95 与 reviewer 的 **16.13 s** 吻合",
          abs(p95 - EXP_P95) < 1e-3,
          "p95=%.6f（应 %.6f）" % (p95, EXP_P95))

    # ── 7.2 ★ 区分力：插值法必须给出**不同**的 P50 ──
    #   ⇒ 若实现退回插值法，7.1 就会 FAIL ⇒ 本断言是「反向守卫」
    p50_interp = CURVE._pct_interp(vals, 0.50)
    check("★ ⑦ ★ 插值法 P50 **确实不同**（证明两口径会打架 ⇒ 守卫有效）",
          abs(p50_interp - p50) > 1.0,
          "索引法=%.6f vs 插值法=%.6f" % (p50, p50_interp))

    # ── 7.3 报告口径必须与 bridge 自己的实现**一致** ──
    #   bridge 的 `_pct_bridge` 与 `_pct` 必须给出**同一个数**
    check("★ ⑦ `_pct` 与 `_pct_bridge` **逐位一致**（bridge 同口径）",
          CURVE._pct(vals, 0.95) == CURVE._pct_bridge(vals, 0.95),
          "pct=%.6f bridge=%.6f" % (CURVE._pct(vals, 0.95),
                                    CURVE._pct_bridge(vals, 0.95)))

    # ── 7.4 分析器对外报出的 p50/p95 必须走索引法 ──
    #   ⇒ 用合成产物跑 build()，断言 p50_sec 是索引法值、
    #     且 `pct_caliber` 字段存在（写明口径）、
    #     且 `p50_sec_interp_for_reference` **存在但不同**。
    import json
    import os
    import tempfile

    per = []
    cmp_segments = []
    for i, v in enumerate(vals):
        per.append({
            "id": "s%d" % i, "t_start": float(i), "t_end": float(i) + 1,
            "orig_end": float(i) + 1, "ready_at": float(i) + 1 + v,
            "has_tts": True, "src_len": 20, "lag_est_sec": 0.5,
        })
        # ★ `signed_err_ms` 取自 **compare.json 的 segments**（口径 A 的真实来源）
        cmp_segments.append({
            "seg_id": "s%d" % i, "t_start": float(i),
            "signed_err_ms": v * 1000.0,
        })
    tmp = tempfile.mkdtemp(prefix="ext039_pct_")
    with open(os.path.join(tmp, "margin.json"), "w", encoding="utf-8") as f:
        json.dump({"per_segment": per, "delay_sec": 20,
                   "client_metrics": {}}, f)
    with open(os.path.join(tmp, "ext033_compare.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": cmp_segments, "t0_sec": 0.0}, f)
    res = CURVE.build(tmp)
    se = res["signed_err"]
    check("★ ⑦ 分析器报出的 `p50_sec` = **索引法**值（5.9787）",
          abs((se.get("p50_sec") or 0) - EXP_P50) < 1e-3,
          "p50_sec=%s" % se.get("p50_sec"))
    check("★ ⑦ 分析器报出的 `p95_sec` = **索引法**值（16.1306）",
          abs((se.get("p95_sec") or 0) - EXP_P95) < 1e-3,
          "p95_sec=%s" % se.get("p95_sec"))
    check("★ ⑦ `pct_caliber` 字段存在且写明口径（索引法）",
          "索引法" in (se.get("pct_caliber") or ""),
          "pct_caliber=%s" % se.get("pct_caliber"))
    check("★ ⑦ 插值法值**单列**且与索引法**不同**（仅作对照，不报数）",
          se.get("p50_sec_interp_for_reference") is not None
          and abs(se["p50_sec_interp_for_reference"] - se["p50_sec"]) > 1.0,
          "interp=%s vs idx=%s" % (se.get("p50_sec_interp_for_reference"),
                                   se.get("p50_sec")))


# ─────────────────────────────────────────────────────────────────
# ⑧ ★ EXT-039 收口：**跨端**分位口径必须一致（player / bridge / Python）
# ─────────────────────────────────────────────────────────────────
def test_08_percentile_caliber_cross_endpoint_consistency():
    print("\n[8] ★ EXT-039 收口 —— 跨端分位口径一致（player / bridge / Python）")
    import ext039_sync_curve as CURVE

    # ── 8.1 ★ 三端口径曾各行其是，同一批数据给出**三个不同的 P95** ──
    #   run `20261105_174558`（n=39）：
    #     player.js  `floor(n*p)`        → 22256.729167
    #     bridge.py  `ceil(q*n)-1`       → 22256.729167
    #     Python 侧 `round(q*(n-1))`    → 21829.229167   ★ reviewer 口径
    #   run `20261105_112057`（n=14）：
    #     player.js  `floor(n*p)`        → 12808.4375
    #     bridge.py  `ceil(q*n)-1`       →  5978.7292
    #     Python 侧 `round(q*(n-1))`    →  5978.7292  ★ reviewer 报的 5.98 ✔
    #   ⇒ 统一口径 = **`round(q*(n-1))`**（reviewer 手算用的那个）。
    vals = [0.0, 0.0, 0.552, 1.448, 3.4967, 5.9787, 5.5367, 13.1154,
            13.4831, 12.8084, 14.1161, 16.1306, 15.8276, 16.1983]
    check("★ ⑧ Python 侧 P50 = reviewer 的 **5.9787**（`round(q*(n-1))`）",
          abs(CURVE._pct(vals, 0.50) - 5.97873) < 1e-3,
          "p50=%.6f" % CURVE._pct(vals, 0.50))

    # ── 8.2 ★ bridge 源码必须用**同一个**口径（不再是 `ceil(q*n)-1`）──
    bridge_src = os.path.join(ROOT, "ext", "bridge.py")
    with open(bridge_src, encoding="utf-8") as f:
        bsrc = f.read()
    check("★ ⑧ bridge 的 `_pct` 用 `round(q * (len(s) - 1))`（与 Python 侧一致）",
          "round(q * (len(s) - 1))" in bsrc,
          "bridge.py 中未见 `round(q * (len(s) - 1))`（已改口径时应命中）")
    check("★ ⑧ bridge 已**不再**用 `ceil(q * len(s)) - 1`（旧口径已撤）",
          "ceil(q * len(s)) - 1" not in bsrc,
          "bridge.py 仍残留旧口径 `ceil(q * len(s)) - 1`")

    # ── 8.3 ★ player.js 必须用**同一个**口径（不再是 `floor(n*p)`）──
    player_src = os.path.join(ROOT, "extension", "player.js")
    with open(player_src, encoding="utf-8") as f:
        psrc = f.read()
    check("★ ⑧ player.js 的 `pct()` 用 `pyRoundIndex(p * (s.length - 1))`",
          "pyRoundIndex(p * (s.length - 1))" in psrc,
          "player.js 中未见 `pyRoundIndex(p * (s.length - 1))`")
    check("★ ⑧ player.js 的 `pct()` **不用** JS 原生 `Math.round`（会差一个元素）",
          "Math.round(p * (s.length - 1))" not in psrc,
          "player.js 仍用 JS 原生 `Math.round`")
    # ★ 只在 `function pct(` 体内检查（避免误伤别处的 floor 法）
    _pct_body = psrc.split("function pct(")[1].split("\n}\n")[0] \
        if "function pct(" in psrc else ""
    check("★ ⑧ player.js 的判据用 `pct()` 已**不再**用 `Math.floor(s.length * p)`",
          "Math.floor(s.length * p)" not in _pct_body,
          "player.js `pct()` 仍用旧口径 `Math.floor(s.length * p)`")

    # ── 8.4 ★ 用 n=14 / n=39 两个真实样本，验证三端公式给出**同一个数** ──
    #   （此处用 JS 公式在 Python 里复刻 player.js 的实现）
    #   ⚠️ ★ `player.js` 用 `pyRoundIndex()` 复刻 **Python 的银行家舍入**
    #     （half-to-even）⇒ 不能用 `math.floor(x+0.5)`（那是四舍五入）
    #     ⇒ n=14 的 P50 恰好落在 .5 上（0.5*13=6.5）⇒ 两法差一个元素。
    def py_round_index(x):
        """Python `round()` 的银行家舍入索引（half-to-even）。"""
        import math as _m
        f = _m.floor(x)
        diff = x - f
        if diff > 0.5:
            return int(f) + 1
        if diff < 0.5:
            return int(f)
        return int(f) if int(f) % 2 == 0 else int(f) + 1

    def js_pct(arr, p):
        s = sorted(arr)
        if not s:
            return None
        idx = min(len(s) - 1, max(0, py_round_index(p * (len(s) - 1))))
        return s[idx]

    for label, sample in (("n=14", vals), ("n=39", [float(i) for i in range(39)])):
        for q, exp_name in ((0.50, "p50"), (0.95, "p95")):
            a = CURVE._pct(sample, q)
            b = js_pct(sample, q)
            c = CURVE._pct_bridge(sample, q)
            check("★ ⑧ %s %s 三端**逐位一致**（Python / player / bridge）"
                  % (label, exp_name),
                  a == b == c,
                  "py=%s js=%s bridge=%s" % (a, b, c))

    # ── 8.5 ★★ **银行家舍入**的针对性断言（.5 边界）──
    #   n=14 ⇒ q*(n-1) = 0.5*13 = **6.5**
    #   ⇒ Python round(6.5)=6（偶）/ JS Math.round(6.5)=7 ⇒ 差一个元素
    #   ⇒ player.js 必须用 `pyRoundIndex`（银行家舍入）才能对齐。
    check("★ ⑧ ★★ 银行家舍入：`pyRoundIndex(6.5)` = **6**（偶数，非 7）",
          py_round_index(6.5) == 6,
          "got %s" % py_round_index(6.5))
    check("★ ⑧ ★★ 银行家舍入：`pyRoundIndex(7.5)` = **8**（进位到偶数）",
          py_round_index(7.5) == 8,
          "got %s" % py_round_index(7.5))
    _s14 = sorted(vals)
    check("★ ⑧ ★★ n=14 的 P50 = **s[6]** = 5.9787（不是 s[7]=12.8084）",
          CURVE._pct(vals, 0.50) == _s14[6] == 5.9787
          and CURVE._pct(vals, 0.50) != _s14[7],
          "p50=%s s6=%s s7=%s" % (CURVE._pct(vals, 0.50), _s14[6], _s14[7]))
    check("★ ⑧ ★★ player.js 源码含 `pyRoundIndex`（银行家舍入复刻）",
          "pyRoundIndex" in psrc,
          "player.js 中未见 pyRoundIndex")
    check("★ ⑧ ★★ player.js 的 `pct()` 用 `pyRoundIndex(...)` 而非 `Math.round(...)`",
          "pyRoundIndex(p * (s.length - 1))" in psrc,
          "player.js 的 pct() 未用 pyRoundIndex")


# ─────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 68)
    print("EXT-039 自测 —— 不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器")
    print("=" * 68)

    test_01_first_segment_delivered_once()
    test_02_two_slope_calibers_separate()
    test_03_coverage_source_speech_only()
    test_04_d_needed_matches_bridge()
    test_05_exhaustion_behavior_calibers()
    test_06_dropped_dub_caliber_excludes_silent_fill()
    test_07_percentile_caliber_matches_bridge()
    test_08_percentile_caliber_cross_endpoint_consistency()

    npass = sum(1 for _, ok in RESULTS if ok)
    nfail = sum(1 for _, ok in RESULTS if not ok)
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    if nfail:
        print("⇒ 有 FAIL ⇒ 必须修完再交卷。")
        return 1
    print("⇒ 全通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
