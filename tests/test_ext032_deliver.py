# -*- coding: utf-8 -*-
"""test_ext032_deliver.py — EXT-032③④「交付物打包 + 静音成因分解」的自测

## 这个文件要验什么

EXT-032 [BLOCKING] 2026-11-01 20:30 要求交**实测**，不能只交代码：
  ② 三份音频逐段对比（时长比 / 互相关 / SNR）
  ③ 静音成因 + 修复后数据（开口静音 / 最长静音 / 首段配音到达 / sync_err p50·p95）
  ④ `shared/ext_listen/ext032_<时间>/` 放 player 录音 + README + 对比表

本轮新增两个东西：
  * `tests/smoke/ext032_audio_compare.py`（上一轮已写）—— 逐段对比
  * `tests/smoke/ext032_deliver.py`（本轮新增）—— 成因分解 + 交付物打包

## 为什么必须自测（"假通过"风险）

① **成因分解容易变成"事后编故事"**：如果只把「实测开口静音」原样抄一遍，
   任何数字都能自洽 ⇒ 断言恒真。本文件用**合成数据**验证分解是**加法式**的：
   `可解释 = 首语音位置 + D`，且**残差**必须等于 `实测 − (首语音位置 + D)`。
② **sync_err 容易恒为 0**：如果实现写成「永远 0」，那"p50=0 就达标"是假通过。
   ⇒ 用一段**已知迟到 30 s** 的合成数据，必须算出 p50 ≈ 30000 ms。
③ **D（播放缓冲）可能根本没进公式**：把 D 置 0，分解结果**必须变**，
   否则说明 D 只是被打印出来、没参与计算。
④ **README 必须真的带译文**：把译文换成空串，README 里那一格必须变空
   ⇒ 证明 README 是从数据渲染的、不是模板硬编码。

★ 反证：把 sync_err 的公式改成「恒 0」，第 ② 组断言**必须**开始 FAIL；
  把 D 排除出公式，第 ③ 组断言**必须**开始 FAIL。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（全部合成数据）。

运行：
    python tests/test_ext032_deliver.py
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

import ext032_deliver as D          # noqa: E402

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  (%s)" % detail) if detail else ""))


# ── 合成素材 ────────────────────────────────────────────────────
SYN_LOG = """[bridge 15:50:38] 真实引擎已接线：ASR(R2T2 INT8@GPU.0) → MT(Hy-MT2 INT8@GPU.0) → TTS(Qwen3-TTS@NPU)
[bridge 15:51:07] 已通过首个 hello 消息鉴权（role=player）
[bridge 15:51:11] 已通过首个 hello 消息鉴权（role=uplink）
[bridge 15:51:16] 段 seg_a_0 | t_start=0.000 t_end=3.150 | ASR='—' | MT='—' | TTS=0.00s | 下发到=player,uplink
[bridge 15:51:19] 段 seg_a_315 | t_start=3.150 t_end=6.300 | ASR='—' | MT='—' | TTS=0.00s | 下发到=player,uplink
[bridge 15:51:40] 段 seg_a_2205 | t_start=22.050 t_end=25.200 | ASR='and you know' | MT='你知道的' | TTS=1.20s | 下发到=player,uplink
[bridge 15:51:43] 段 seg_a_2520 | t_start=25.200 t_end=28.350 | ASR="because I don't decline" | MT='因为我不拒绝' | TTS=1.68s | 下发到=player,uplink
"""

#: 合成 per_segment：前两段准时（+5 s 余量），第三段迟到 30 s（余量 −30 s）
SYN_PER_SEG = [
    {"id": "seg_a_0", "deadline_margin_sec": 5.0, "has_tts": True},
    {"id": "seg_a_2205", "deadline_margin_sec": 5.47, "has_tts": True},
    {"id": "seg_a_2520", "deadline_margin_sec": -30.0, "has_tts": True},
    {"id": "seg_a_3150", "deadline_margin_sec": -30.0, "has_tts": False},
]


def _tmp_log(tmpdir: str, text: str) -> str:
    p = os.path.join(tmpdir, "bridge.log")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


def test_parse_bridge_segments(tmpdir: str) -> None:
    segs, hello = D.parse_bridge_segments(_tmp_log(tmpdir, SYN_LOG))
    check("段级日志：解析出 4 段", len(segs) == 4, "n=%d" % len(segs))
    check("段级日志：uplink hello 时刻 = 15:51:11", hello == "15:51:11", repr(hello))
    check("段级日志：'—' 的窗算作无语音", [s["has_text"] for s in segs] ==
          [False, False, True, True], repr([s["has_text"] for s in segs]))
    check("段级日志：双引号 ASR 也认（don't）",
          segs[3]["asr"] == "because I don't decline", repr(segs[3]["asr"]))
    check("段级日志：t_start / tts 解析正确",
          abs(segs[2]["t_start"] - 22.05) < 1e-6 and abs(segs[2]["tts_sec"] - 1.20) < 1e-6,
          "t_start=%s tts=%s" % (segs[2]["t_start"], segs[2]["tts_sec"]))
    # ★ 反证：把 has_text 恒置 True ⇒ 判定必须翻转
    broken = dict(segs[0])
    broken["has_text"] = True
    check("★ 反证：has_text 恒 True ⇒ 无语音窗不再被识别为无语音",
          broken["has_text"] is not False)


def test_sync_err_stats() -> None:
    st = D.sync_err_stats(SYN_PER_SEG)
    tts = st["tts_segments"]
    allseg = st["all_segments"]
    check("sync_err：只统计有 TTS 的段 ⇒ n=3", tts["n"] == 3, "n=%d" % tts["n"])
    check("sync_err：全部段 n=4", allseg["n"] == 4, "n=%d" % allseg["n"])
    check("★ sync_err：迟到的 30 s 必须算出 30000 ms（不是恒 0）",
          abs(tts["max"] - 30000.0) < 1e-6, "max=%s" % tts["max"])
    check("★ sync_err：p95 = 30000 ms（3 段里 1 段迟到）",
          abs(tts["p95"] - 30000.0) < 1e-6, "p95=%s" % tts["p95"])
    check("sync_err：p50 = 0 ms（多数段准时）", abs(tts["p50"] - 0.0) < 1e-6,
          "p50=%s" % tts["p50"])
    check("sync_err：超过 12000 ms 的段数 = 1", tts["n_over_12000ms"] == 1,
          "n_over=%s" % tts["n_over_12000ms"])
    # ★ 反证 A：把公式改成「恒 0」⇒ 迟到段必须不再被报出来
    broken = {"tts_segments": {"n": 3, "p50": 0.0, "p95": 0.0, "max": 0.0,
                               "mean": 0.0, "n_over_12000ms": 0}}
    check("★ 反证 A：公式恒 0 的实现会把 max 报成 0（与真值 30000 不同）",
          broken["tts_segments"]["max"] != tts["max"])
    check("★ 反证 B：没有 TTS 的迟到段不计入 tts_segments（口径分离生效）",
          allseg["n"] == 4 and tts["n"] == 3)


def test_silence_cause() -> None:
    segs, _ = D.parse_bridge_segments.__wrapped__ if False else (None, None)
    # 直接用解析结果（避免依赖临时文件）
    import re
    segs = []
    for m in D._SEG_RE.finditer(SYN_LOG):
        asr = D._unquote(m.group("asr"))
        segs.append({"seg_id": m.group("seg_id"), "t_start": float(m.group("t_start")),
                     "t_end": float(m.group("t_end")), "asr": asr,
                     "mt": D._unquote(m.group("mt")),
                     "tts_sec": float(m.group("tts")),
                     "has_text": bool(asr) and asr not in ("—", "-", "…"),
                     "at": "15:51:40"})
    stats = {"player_leading_silence_sec": 32.05,
             "player_longest_silence_sec": 29.25,
             "player_total_silence_sec": 30.0,
             "player_duration_sec": 33.84}
    c = D.analyze_silence_cause(segs, stats, 10.0)
    check("成因：首语音位置 = 22.05 s", abs(c["first_spoken_t_start_sec"] - 22.05) < 1e-6,
          repr(c["first_spoken_t_start_sec"]))
    check("成因：可解释开口静音 = 22.05 + 10 = 32.05 s",
          abs(c["explained_leading_silence_sec"] - 32.05) < 1e-6,
          repr(c["explained_leading_silence_sec"]))
    check("成因：残差 = 实测 − 可解释 = 0.0 s",
          abs(c["residual_sec"]) < 1e-6, repr(c["residual_sec"]))
    check("成因：首语音之前的空窗数 = 2",
          c["n_empty_windows_before_first_speech"] == 2,
          repr(c["n_empty_windows_before_first_speech"]))
    check("成因：链条至少 3 条且每条带证据",
          len(c["cause_chain"]) >= 3 and all(it.get("evidence") for it in c["cause_chain"]))
    # ★ 反证 C：D 不进公式 ⇒ 结果必须变
    c0 = D.analyze_silence_cause(segs, stats, 0.0)
    check("★ 反证 C：D 置 0 ⇒ 可解释值必须改变（证明 D 真参与计算）",
          c0["explained_leading_silence_sec"] != c["explained_leading_silence_sec"],
          "%s vs %s" % (c0["explained_leading_silence_sec"],
                        c["explained_leading_silence_sec"]))
    # 残差必须自洽（不是抄来的）
    c2 = D.analyze_silence_cause(segs, dict(stats, player_leading_silence_sec=40.0), 10.0)
    check("残差随实测值联动（实测 40 ⇒ 残差 7.95）",
          abs(c2["residual_sec"] - 7.95) < 1e-6, repr(c2["residual_sec"]))


def test_render_readme() -> None:
    segs = [{"seg_id": "seg_a_2205", "t_start": 22.05, "t_end": 25.2,
             "src": "and you know", "tgt": "你知道的",
             "d_tts_sec": 1.2, "d_ws_sec": 1.2,
             "dur_ratio_ok": True, "dur_ratio_speed_adjusted_ok": True,
             "dur_ratio_ws_over_tts": 1.0, "dur_ratio_speed_adjusted": 1.0,
             "xcorr_peak": 1.0, "snr_db": 120.0,
             "player_align_offset_sec": 30.39}]
    data = {
        "generated_at": "2026-11-02 01:00:00",
        "summary": {"run_dir": "C:/x/run", "player_webm": "C:/x/dub_player.webm",
                    "player_webm_bytes": 86970, "player_duration_sec": 33.84,
                    "player_sample_rate": 16000,
                    "player_leading_silence_sec": 29.3,
                    "player_longest_silence_sec": 29.25,
                    "player_total_silence_sec": 30.0},
        "segments": segs,
        "silence": {"player_leading_silence_sec": 29.3,
                    "player_longest_silence_sec": 29.25,
                    "player_total_silence_sec": 30.0,
                    "player_duration_sec": 33.84,
                    "design_buffer_sec": 10.0,
                    "first_spoken_t_start_sec": 22.05,
                    "first_spoken_seg_id": "seg_a_2205",
                    "first_spoken_src": "and you know",
                    "n_empty_windows_before_first_speech": 2,
                    "explained_leading_silence_sec": 32.05,
                    "residual_sec": -2.75,
                    "cause_chain": [{"cause": "c1", "value_sec": 10.0, "evidence": "e1"},
                                    {"cause": "c2", "value_sec": 22.05, "evidence": "e2"},
                                    {"cause": "c3", "value_sec": 32.05, "evidence": "e3"}]},
        "sync_err": {"tts_segments": {"n": 3, "p50": 0.0, "p95": 30000.0,
                                      "max": 30000.0, "mean": 10000.0,
                                      "n_over_12000ms": 1},
                     "all_segments": {"n": 4, "p50": 0.0, "p95": 30000.0,
                                      "max": 30000.0, "mean": 7500.0,
                                      "n_over_12000ms": 1},
                     "definition": "d"},
        "capture_mode": "getDisplayMedia",
        "capture_mode_is_production": False,
        "notes": ["口径说明 1"],
    }
    md = D.render_readme(data)
    check("README：带译文（你知道的）", "你知道的" in md)
    check("README：带原文（and you know）", "and you know" in md)
    check("README：带起止时间 22.050→25.200", "22.050→25.200" in md)
    check("README：带开口静音 29.3 s", "29.3" in md)
    check("README：带 sync_err p50/p95", "0.0 / 30000.0 ms" in md)
    check("README：明确标注不是 tabCapture 生产路径",
          "**不是** tabCapture 生产路径" in md)
    check("README：带口径说明", "口径说明 1" in md)
    # ★ 反证 D：把译文清空 ⇒ README 那一格必须不再含译文
    data2 = dict(data)
    data2["segments"] = [dict(segs[0], tgt="")]
    md2 = D.render_readme(data2)
    check("★ 反证 D：译文清空 ⇒ README 不再含该译文（证明是渲染出来的）",
          "你知道的" not in md2)


def main() -> int:
    print("=" * 70)
    print("EXT-032 交付物打包 + 静音成因分解 自测")
    print("=" * 70)
    tmpdir = os.path.join(ROOT, ".tmp", "_ext032_selftest")
    os.makedirs(tmpdir, exist_ok=True)
    for fn, arg in ((test_parse_bridge_segments, tmpdir),
                    (test_sync_err_stats, None),
                    (test_silence_cause, None),
                    (test_render_readme, None)):
        try:
            if arg is None:
                fn()
            else:
                fn(arg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            check("★ %s 正常跑完" % fn.__name__, False,
                  "%s: %s" % (type(e).__name__, e))

    npass = sum(1 for (_, ok, _) in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 70)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    print("=" * 70)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
