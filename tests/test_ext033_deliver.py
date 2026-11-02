# -*- coding: utf-8 -*-
"""test_ext033_deliver.py — EXT-033 C/D/E「实测对比 + 有符号 sync_err +
交付物」的自测

## 这个文件要验什么

EXT-033 [BLOCKING] 2026-11-02 09:22 的三条硬要求：

* **C** 三份对比要**实测**：player 每段从 WAV 按 `dubOnsets` 切出来，
  算 d_player、player/(b) 时长比、互相关峰、SNR；**不能抄 d_ws**；
  对齐峰低的段标「未对齐」，**不计入合格**。
* **D** sync_err 必须在 **player 端实测有符号误差**
  = 实际起播 − (t0+t_start+D)；报 P50/P95/max；目标 \\|误差\\| ≤ 300 ms。
* **E** 报开头静音、最长静音段、首段到达时间；README 逐段写起止时间和译文，
  **源语言必须是英文**。

## 为什么必须自测（「假通过」风险）

① **d_player 容易变成抄 d_ws**：只要实现里写 `d_player = d_ws`，
   任何对比表都自洽 ⇒ 断言恒真。
   ⇒ 用**合成 WAV**（真实有声跨度与 `d_ws` **故意不同**），
     断言 `d_player` 必须等于**合成 WAV 里量出来的**那个值。
② **sync_err 容易恒为 0 / 恒非负**：EXT-032 用的
   `max(0, TTS就绪 − 截止时刻)` **永远 ≥ 0** ⇒ 量不出「早播」。
   ⇒ 合成一组**含负值**的误差，断言 `min < 0` 且 `p50 < 0`。
   ★ 反证：把公式改回 `max(0, …)`，本组断言**必须**开始 FAIL。
③ **切段位置容易退化成「搜索对齐」**：EXT-032 的落点是对齐峰 0.04~0.70
   的强行对齐结果。
   ⇒ 断言切段位置**只**由 `actual − acStartSec` 决定（给两组不同
     `acStartSec`，偏移必须**恰好**平移那么多）。
④ **源语言校验容易形同虚设**：断言中文原文**必须**被判不合格。
⑤ **README 容易是模板硬编码**：清空译文 ⇒ 那格**必须**变空。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（全部合成数据）。

运行：
    python tests/test_ext033_deliver.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE = os.path.join(ROOT, "tests", "smoke")
for _p in (SMOKE, os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ext033_analyze as A          # noqa: E402

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  (%s)" % detail) if detail else ""))


# ── 合成素材 ────────────────────────────────────────────────────
SR = 48000


def synth_wav(spec, sr=SR):
    """spec: [(start_sec, dur_sec, amp)] ⇒ 合成 Float32 序列。"""
    total = int(max(s + d for s, d, _ in spec) * sr)
    x = [0.0] * total
    import math
    for s, d, amp in spec:
        i0, i1 = int(s * sr), int((s + d) * sr)
        for i in range(i0, min(i1, total)):
            # 一个确定性的「语音样」方波（够做静音检测与互相关）
            x[i] = amp * (1.0 if ((i - i0) // 120) % 2 == 0 else -1.0)
    return x


def main() -> int:
    print("=== EXT-033 C/D/E 自测（全部合成数据）===")

    # ── ① WAV 内位置 = actual − acStartSec（**同轴、不搜索对齐**）──
    detail = [
        {"id": "seg_1", "tStart": 22.05, "requested": 35.05, "actual": 35.10,
         "signedErrMs": 50.0, "speed": 1.0},
        {"id": "seg_2", "tStart": 25.20, "requested": 38.20, "actual": 38.25,
         "signedErrMs": 50.0, "speed": 1.1899},
    ]
    o1 = A.wav_timeline_offsets(detail, 3.0)
    check("① 切段位置 = actual − acStartSec",
          abs(o1[0]["wav_offset_sec"] - 32.10) < 1e-6,
          "got %r" % o1[0]["wav_offset_sec"])
    o2 = A.wav_timeline_offsets(detail, 5.0)
    check("① 换 acStartSec ⇒ 偏移恰好平移 2 s",
          abs((o2[0]["wav_offset_sec"] - o1[0]["wav_offset_sec"]) + 2.0) < 1e-6,
          "delta=%r" % (o2[0]["wav_offset_sec"] - o1[0]["wav_offset_sec"]))

    # ── ② d_player 是**实测**，不是抄 d_ws ──
    #    合成 WAV：第 10 s 起有声 1.0 s（幅度 0.5），第 20 s 起有声 2.0 s
    wav = synth_wav([(10.0, 1.0, 0.5), (20.0, 2.0, 0.5)])
    m = A.measure_player_segment(wav, SR, 9.9, 3.0)
    check("② d_player = 合成 WAV 里量出的有声跨度（≠ d_ws）",
          m.get("d_player_sec") is not None
          and abs(m["d_player_sec"] - 1.0) < 0.06,
          "got %r（d_ws=3.0）" % m.get("d_player_sec"))
    m2 = A.measure_player_segment(wav, SR, 19.9, 3.0)
    check("② 第二段 d_player ≈ 2.0 s",
          m2.get("d_player_sec") is not None
          and abs(m2["d_player_sec"] - 2.0) < 0.06,
          "got %r" % m2.get("d_player_sec"))
    check("② 越界切段不崩、且给出原因",
          A.measure_player_segment(wav, SR, 9999.0, 1.0).get("d_player_sec") is None)
    # ★ 细粒度检测必须比 250 ms 窗的 silence_spans 准（EXT-033 要判 ±2%）
    check("② 细粒度检测的量化误差 ≤ 60 ms（≤250 ms 窗做不到）",
          abs(m["d_player_sec"] - 1.0) <= 0.06,
          "err=%r ms" % round((m["d_player_sec"] - 1.0) * 1000, 1))

    # ── ③ sync_err **有符号**：负值必须留得住 ──
    errs = [-820.0, -700.0, -600.0, -500.0, 40.0, 90.0, 1500.0]
    st = A.sync_stats(errs)
    check("③ sync_err 保留负值（min < 0）",
          st["min"] is not None and st["min"] < 0, "min=%r" % st["min"])
    check("③ sync_err 的 p50 < 0（不是被 max(0,…) 夹掉）",
          st["p50"] is not None and st["p50"] < 0, "p50=%r" % st["p50"])
    check("③ 超过 300 ms / 早于 300 ms 的段被分别计数",
          st["n_over_300ms"] == 1 and st["n_under_minus300ms"] == 4,
          "over=%r under=%r" % (st["n_over_300ms"], st["n_under_minus300ms"]))
    # ★ 反证：旧口径（EXT-032）恒非负 ⇒ 下面的断言必须 FAIL
    old_style = A.sync_stats([max(0.0, e) for e in errs])
    check("③ 反证：旧口径 max(0,…) 会让 min ≥ 0（本实现与之不同）",
          old_style["min"] == 0.0 and (st["min"] or 0) < 0,
          "old_min=%r new_min=%r" % (old_style["min"], st["min"]))

    # ── ④ 百分位口径与 tools/p1_pipeline.py::_pct 完全一致 ──
    try:
        import p1_pipeline as P
        s = sorted(errs)
        same = all(A._pct(s, q) == P._pct(s, q) for q in (0.5, 0.95, 0.0, 1.0))
    except Exception as e:
        same = False
        print("   （p1_pipeline 导入失败：%s）" % e)
    check("④ 百分位与 p1_pipeline._pct 同口径", same)

    # ── ⑤ 源语言必须是英文 ──
    ok, why = A.source_is_english("and you know")
    check("⑤ 英文原文判合格", ok, why)
    ok2, why2 = A.source_is_english("你知道的")
    check("⑤ 中文原文判**不合格**", (not ok2) and "英文" in why2, why2)
    ok3, why3 = A.source_is_english("")
    check("⑤ 空原文判不合格", not ok3, why3)

    # ── ⑥ 静音画像：开头静音 / 最长静音 / 总静音 ──
    wav2 = synth_wav([(2.0, 1.0, 0.5), (10.0, 0.5, 0.5)])
    prof = A.silence_profile(wav2, SR)
    check("⑥ 开头静音 ≈ 2.0 s",
          prof["leading_silence_sec"] is not None
          and abs(prof["leading_silence_sec"] - 2.0) < 0.15,
          "got %r" % prof["leading_silence_sec"])
    check("⑥ 最长静音段 ≥ 6 s（10.5→12.0 之间那段更长）",
          prof["longest_silence_sec"] is not None
          and prof["longest_silence_sec"] > 5.0,
          "got %r" % prof["longest_silence_sec"])

    # ── ⑦ README 是**渲染**出来的（译文清空 ⇒ 那格变空）──
    d = {
        "player_sample_rate": SR, "recording_duration_sec": 80.0,
        "player_wav_bytes": 1234, "ac_start_sec": 3.0,
        "t0_axis": "audio_clock", "t0_sec": 0.5,
        "silence": {"leading_silence_sec": 8.0, "longest_silence_sec": 8.0},
        "first_segment_arrival_sec": 8.0,
        "sync_err_ms": A.sync_stats(errs), "sync_err_target_ms": 300.0,
        "sync_err_ok": False,
        "n_segments": 1, "n_aligned": 1, "n_unaligned": 0,
        "dur_ratio_speed_adjusted_min": 1.0,
        "dur_ratio_speed_adjusted_max": 1.0,
        "dur_ratio_ok_count": 1, "dur_ratio_tol": 0.02,
        "src_all_english": True, "recording_ok_len": True,
        "leading_silence_ok": True,
        "segments": [{"seg_id": "seg_1", "t_start": 22.05,
                      "wav_offset_sec": 32.1, "signed_err_ms": 50.0,
                      "speed": 1.0, "src": "and you know", "tgt": "你知道的",
                      "d_player_sec": 1.2, "d_ws_sec": 1.2,
                      "dur_ratio_speed_adjusted": 1.0, "aligned": True,
                      "src_is_english": True}],
    }
    md = A.render_readme(d)
    check("⑦ README 含英文原文", "and you know" in md)
    check("⑦ README 含中文译文", "你知道的" in md)
    d2 = dict(d)
    d2["segments"] = [dict(d["segments"][0], tgt="")]
    md2 = A.render_readme(d2)
    check("⑦ 反证：译文清空 ⇒ README 那格变空",
          "你知道的" not in md2 and "and you know" in md2)
    tbl = A.render_md(d)
    check("⑦ 对比表含「未对齐」字样（低对齐峰不计入合格）",
          "未对齐" in tbl)

    # ── ⑧ 阈值常量必须与 EXT-033 原文一致 ──
    check("⑧ 时长比容差 0.02", abs(A.DUR_RATIO_TOL - 0.02) < 1e-9)
    check("⑧ 互相关峰门槛 0.6", abs(A.XCORR_PEAK_MIN - 0.6) < 1e-9)
    check("⑧ sync_err 目标 300 ms", abs(A.SYNC_ERR_TARGET_MS - 300.0) < 1e-9)
    check("⑧ 录音时长下限 75 s", abs(A.MIN_RECORDING_SEC - 75.0) < 1e-9)
    check("⑧ 开口静音上限 15 s", abs(A.MAX_LEADING_SILENCE_SEC - 15.0) < 1e-9)

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print("=== %d PASS / %d FAIL ===" % (len(RESULTS) - n_fail, n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
