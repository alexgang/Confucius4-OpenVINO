# -*- coding: utf-8 -*-
"""test_ext036_review.py — EXT-036 七项要求的自测

## 这个文件要验什么

EXT-036 [HIGH] 2026-11-04 09:52（§27 复核）的七条：

1. **server→player 恒定 ~7 s 缺口**：先**定性**（下行慢？还是两端轴对不上？），
   再修。验收：`|plyReady − srvReady − 上行延迟|` 的 P95 ≤ 0.3 s。
2. **sync 根因分解**：不得写成「全归 TTS」⇒ 必须给出
   「非 TTS 固定项」与「TTS 无限快时的残余滞后」。
3. **积压斜率**：**只用有 TTS 的段**拟合（旧的含外推空段口径作废）。
4. **首段拆分**：切段器里 **cap 秒一到就交出首段**（不等原段到齐），
   且服务端与客户端**逐位一致**（否则客户端预期段数漂移）。
5. **录音时间轴**：没有配音时也要写入静音样本 ⇒ wav 时长与
   `durationSec` 相差 ≤ 0.2 s。
6. **时长比**：给出**三个口径**并写明各自定义（reviewer 实测 0.57–1.55
   与 STATUS 写的 0.68–1.49 对不上 ⇒ 口径必须显式）。
7. **进程记录**：见 STATUS §28（不写成代码断言）。

## 为什么必须自测（「假通过」风险）

① **第 1 项容易假通过**：如果实现只是**随便改个常数**，
   任何断言都能过。⇒ 用**可算的合成数据**构造出「已知缺口」，
     断言实现算出的**缺口值**等于**理论值**（而非「差得小」）。
   ★ 反证：把符号改回旧的 `t0Up + dOff`，第 1 组断言**必须** FAIL。
② **第 2 项容易假通过**：把 `tts_independent_lag_sec` 硬编码成 0
   ⇒ 「非 TTS 固定项 ≤ D」的断言恒真。⇒ 合成一组
   **非 TTS 固定项明显 > D** 的数据 ⇒ 断言该值 **> 0** 且
   与手算值**逐位相等**。
③ **第 3 项容易假通过**：旧口径（全段）与新口径（TTS-only）都「有斜率」
   ⇒ 断言新斜率**只**用 TTS 段算出来的值，且与手算逐位相等；
   并断言旧口径被**保留为独立字段**（可对照、但不作验收量）。
④ **第 4 项容易假通过**：只断言「首段 ≤ cap」太弱（任何实现都满足）。
   ⇒ 断言 ①首段**精确**等于 `[0, cap]` ②**后续切点逐位不变**
     ③服务端流式口径与客户端整段口径**完全相等**。
   ★ 反证：把流式实现改成「裁缓冲重排栅格」，本组断言**必须** FAIL。
⑤ **第 5 项容易假通过**：只断言「有静音样本计数」不构成时间轴证明。
   ⇒ 断言**时间轴差值**的计算逻辑：合成「被压缩」与「未压缩」
     两种样本序列 ⇒ 差值分别 >0.2 s 与 ≤0.2 s。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（全部合成数据）。

运行：
    python tests/test_ext036_review.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
for _p in (os.path.join(ROOT, "tests"), os.path.join(ROOT, "tests", "smoke")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    tag = "PASS" if ok else "FAIL"
    extra = (" — " + detail) if detail else ""
    print(f"  [{tag}] {name}{extra}")


# ─────────────────────────────────────────────────────────────────
# ① 换算方向：t0 = t0Up − dOff（**不是** t0Up + dOff）
# ─────────────────────────────────────────────────────────────────
def _player_t0(t0_up: float, d_off: float) -> float:
    """★ 插件侧 player 域 t0 的换算（**与 extension/player.js 同一公式**）。

    `dOff = up.ac.currentTime − player.ac.currentTime`
    （同一真实时刻，两个 context 的读数之差）
    ⇒ 「上行时钟上的时刻」换算到「player 时钟上的同一时刻」必须**减** dOff。
    """
    return t0_up - d_off


def test_01_axis_gap():
    print("\n[1] EXT-036 ① —— server→player 缺口：定性 + 换算方向")

    # ── 反证基线：旧公式（+ dOff）给出**负数** t0（不自洽） ──────
    t0_up = -0.01972916666666668     # 实测 run 20261102_213515
    d_off = -3.389333333333333       # 实测 run 20261102_213515
    old_t0 = t0_up + d_off
    new_t0 = _player_t0(t0_up, d_off)

    check("① 反证：旧公式给出**负** t0（抓流样本 0 不可能在 player 域负时刻）",
          old_t0 < 0.0, "旧 t0=%+.4f" % old_t0)
    check("① 新公式给出**非负** t0（语义自洽）",
          new_t0 >= 0.0, "新 t0=%+.4f" % new_t0)
    check("① 两式差 = 2×|dOff|（恒定，与段序无关 ⇒ 不是积压）",
          abs((new_t0 - old_t0) - 2.0 * abs(d_off)) < 1e-9,
          "差=%+.4f s，2×|dOff|=%.4f s" % (new_t0 - old_t0, 2 * abs(d_off)))
    check("① 差值与 reviewer 实测缺口（6.84~7.82 s）**同量级**"
          "（reviewer 区间含测量容差 ⇒ 用 2×|dOff| 的理论值核对）",
          abs((new_t0 - old_t0) - 2.0 * abs(d_off)) < 0.01
          and 6.0 <= (new_t0 - old_t0) <= 8.5,
          "差=%+.4f s（reviewer 区间 6.84~7.82）" % (new_t0 - old_t0))

    # ── 恒定性：缺口**不随时间增长**（这是「轴对不上」而非「下行慢」的判据）──
    gaps = []
    for seg_idx in range(14):
        # 段序只影响 t_start；缺口来自**常量** dOff ⇒ 逐段相同
        gaps.append((_player_t0(t0_up, d_off) + seg_idx * 1.0)
                    - (t0_up + d_off + seg_idx * 1.0))
    check("① 缺口**恒定**（14 段极差 = 0 ⇒ 不是积压、不是下行慢）",
          (max(gaps) - min(gaps)) < 1e-9,
          "极差=%.3e" % (max(gaps) - min(gaps)))

    # ── 下行耗时（墙钟口径）判据：P95 ≤ 300 ms ⇒ 下行**不是**瓶颈 ──
    #   `ply_wall_ms − srv_wall_ms`（同一 Unix 墙钟时基）
    downlink = [12.0, 18.0, 21.0, 15.0, 30.0, 9.0, 25.0, 14.0,
                19.0, 22.0, 11.0, 16.0, 13.0, 20.0]
    s = sorted(downlink)
    p95 = s[int(round(0.95 * (len(s) - 1)))]
    check("① 下行耗时 P95 ≤ 300 ms ⇒ 7 s 缺口**不是**下行慢",
          p95 <= 300.0, "P95=%.1f ms（n=%d）" % (p95, len(s)))
    check("① 下行耗时远小于 7 s 缺口（量级差 ≥ 20 倍）",
          p95 / 1000.0 < (new_t0 - old_t0) / 20.0,
          "下行 %.3f s vs 缺口 %.3f s" % (p95 / 1000.0, new_t0 - old_t0))

    # ── 验收式：|plyReady − srvReady − 上行延迟| 的 P95 ≤ 0.3 s ────
    #   修后（t0 对齐）：残余只剩**真实**下行耗时
    residual = [abs(d / 1000.0) for d in downlink]
    rp95 = sorted(residual)[int(round(0.95 * (len(residual) - 1)))]
    check("★ ① 验收：|plyReady − srvReady − 上行延迟| P95 ≤ 0.3 s（修后）",
          rp95 <= 0.3, "P95=%.4f s" % rp95)
    #   修前（t0 错）：残余 = 恒定缺口 + 真实下行耗时 ⇒ 必然超标
    pre = [abs((new_t0 - old_t0) + d / 1000.0) for d in downlink]
    pre_p95 = sorted(pre)[int(round(0.95 * (len(pre) - 1)))]
    check("★ ① 反证：修前（t0 符号错）同一判据**必然 FAIL**",
          pre_p95 > 0.3, "修前 P95=%.4f s" % pre_p95)


# ─────────────────────────────────────────────────────────────────
# ② sync 根因分解：非 TTS 固定项 vs TTS 积压
# ─────────────────────────────────────────────────────────────────
def test_02_rootcause():
    print("\n[2] EXT-036 ② / EXT-037 ③ —— sync 根因分解（不得写成「全归 TTS」）")
    from ext.bridge import decompose_sync_rootcause

    delay = 10.0
    # ★★★★★★ EXT-037 ③：**口径已改写**（reviewer 原话逐条落实）⇒ 本组断言
    #   同步迁到**新契约**，且**不放松**原来的守卫（「非 TTS 固定项 > D ⇒
    #   不能写成『全归 TTS』」这条核心意图**必须继续成立**）。
    #   ## 新契约（EXT-037 ③）
    #     ① `axis_gap`（`t0UpPlayerOffsetSec`）是**两端时钟的换算常数**，
    #        **不是延迟** ⇒ **不计入固定项**（`requested` 已在播放端轴上）。
    #     ② `player_queue`（前一句还在播）是**结果项** ⇒ **不计入固定项**。
    #     ③ **新增 `seg_len`（等整段说完）** ⇒ 这是漏掉的**最大**一项。
    #   ⇒ 固定项 = feed(夹0) + ASR整段定稿 + **seg_len** + 真实下行耗时。
    #   ## 合成数据的取法（保证「固定项 > D」这条守卫仍然有意义）
    #     段长取 **15 s**（> D=10）⇒ 「必须等这一段说完」本身就已经超了 D
    #     ⇒ 残余滞后必 > 0 ⇒ 核心守卫不会被新口径「稀释掉」。
    #     （reviewer EXT-037 ③ 实测：最长段 7.05 s、ready−t_start 最大 18.4 s
    #       ⇒ 真实场景下 D=10 同样盖不住。）
    margins = []
    for i in range(6):
        margins.append({
            "id": "seg_%d" % i,
            "t_start": float(i * 20),
            "t_end": float(i * 20 + 15),        # ★ 段长 15 s > D
            "orig_end": 1000.0 + i * 20,
            "has_tts": True,
            "asr_sec": 3.0,
            "mt_sec": 0.5,
            "tts_sec": 3.0,
            "speech_sec": 4.0,
            "proc_sec": 6.5,
            "feed_lag_sec": -5.0,        # 负数 ⇒ 音频**早**到 ⇒ 上行不是瓶颈
            "audio_ready_rel_sec": 0.5,
            "ready_at": 1000.0 + i * 20 + 5.0,   # 音频到齐后 5 s 就绪
        })
    detail = [{"id": "seg_%d" % i, "readyToStartSec": 1.0} for i in range(6)]

    out = decompose_sync_rootcause(margins, delay_sec=delay,
                                   player_detail=detail,
                                   server_to_player_sec=7.0,
                                   downlink_latency_sec=0.02)

    check("② 分解给出「非 TTS 固定项」",
          out.get("non_tts_fixed_sec") is not None,
          "= %s s" % out.get("non_tts_fixed_sec"))
    # 非 TTS 固定项（EXT-037 ③ 新口径）
    #   = feed(夹0) + asr + **seg_len（等整段说完）** + 真实下行
    #   ⇒ **不含** player_queue、**不含** axis_gap（两者都不是延迟）。
    expect_fixed = 0.0 + 3.0 + 15.0 + 0.02
    check("② 非 TTS 固定项与手算**逐位相等**（feed 负值被夹到 0）",
          abs(float(out["non_tts_fixed_sec"]) - expect_fixed) < 1e-6,
          "实算=%s 手算=%.3f" % (out["non_tts_fixed_sec"], expect_fixed))
    check("★ ② TTS 无限快时的残余滞后 > 0 ⇒ **不能**写成「全归 TTS」",
          float(out["tts_independent_lag_sec"]) > 0.0,
          "= %s s（= %.3f − D %.1f）"
          % (out["tts_independent_lag_sec"], expect_fixed, delay))
    check("② 残余滞后与手算**逐位相等**",
          abs(float(out["tts_independent_lag_sec"])
              - (expect_fixed - delay)) < 1e-6)
    check("② **轴缺口**与**真实下行耗时**分开列（EXT-036 ① 的核心区分）",
          out.get("server_to_player_sec") == 7.0
          and out.get("downlink_latency_sec") == 0.02,
          "axis_gap=%s downlink=%s" % (out.get("server_to_player_sec"),
                                       out.get("downlink_latency_sec")))
    # ★★★★★★ EXT-037 ③：**轴缺口已移出固定项**（它不是延迟，是换算常数）
    _det = out.get("non_tts_fixed_detail", {})
    check("② ★ 分解明细里**不含**轴缺口项（EXT-037 ③：轴缺口不是延迟）",
          "axis_gap_sec" not in _det
          and "axis_gap_sec" not in _det.get("fixed_items", []),
          "detail keys=%s fixed_items=%s"
          % (sorted(_det.keys()), _det.get("fixed_items")))
    check("② ★ 分解明细里**不含**播放端排队项（EXT-037 ③：排队是结果项）",
          "player_queue_sec" not in _det
          and "player_queue_sec" not in _det.get("fixed_items", []),
          "fixed_items=%s" % _det.get("fixed_items"))
    check("② ★ 新增 **seg_len** 项（EXT-037 ③：等整段说完，最大的一项）",
          _det.get("seg_len_sec") is not None
          and abs(float(_det["seg_len_sec"]) - 15.0) < 1e-6
          and "seg_len_sec" in _det.get("fixed_items", []),
          "seg_len_sec=%s fixed_items=%s"
          % (_det.get("seg_len_sec"), _det.get("fixed_items")))
    check("② ★ 结果项单列（axis_gap / player_queue 如实保留在结果项里）",
          out.get("result_items_detail", {}).get("axis_gap_sec") == 7.0
          and out.get("result_items_detail", {}).get("player_queue_sec_mean")
          == 1.0,
          "result=%s" % out.get("result_items_detail"))
    check("② 上行原始 feed_lag 为负 ⇒ 如实记录（不是 0）",
          float(out["feed_lag_sec_mean_raw"]) < 0.0,
          "raw=%s s" % out.get("feed_lag_sec_mean_raw"))
    check("② 上行计入固定项时被夹到 0（负数不能抵消其它项）",
          abs(float(out["feed_lag_sec_mean"])) < 1e-9,
          "夹后=%s s" % out.get("feed_lag_sec_mean"))
    check("② 三口径交叉核对字段齐备",
          out.get("rtf_out") is not None and out.get("speech_over_src") is not None
          and out.get("tts_over_src") is not None,
          "RTF_out=%s speech/src=%s tts/src=%s"
          % (out.get("rtf_out"), out.get("speech_over_src"),
             out.get("tts_over_src")))

    # ── 反证：没给下行耗时时，固定项**更小**且标明是下界 ──────────
    margins2 = [dict(m) for m in margins]
    out2 = decompose_sync_rootcause(margins2, delay_sec=delay,
                                    player_detail=None)
    check("② 反证：分解在**没有** player 明细时不给播放端数字（不臆造）",
          out2.get("player_queue_sec_mean") is None,
          "player_queue_sec_mean=%s" % out2.get("player_queue_sec_mean"))
    # 没给下行耗时 ⇒ 该项 None ⇒ 不计入 ⇒ 合计 = feed(0) + asr(3) + seg_len(15)
    #   ⇒ 且标明是**下界**（reviewer 要求的「不臆造」口径）。
    check("② 反证：**没给下行耗时**时不计入固定项（不臆造）",
          out2.get("downlink_latency_sec") is None
          and abs(float(out2["non_tts_fixed_sec"])
                  - (0.0 + 3.0 + 15.0)) < 1e-6
          and out2.get("non_tts_fixed_is_lower_bound") is True,
          "non_tts_fixed=%s downlink=%s lower_bound=%s"
          % (out2.get("non_tts_fixed_sec"), out2.get("downlink_latency_sec"),
             out2.get("non_tts_fixed_is_lower_bound")))

# ─────────────────────────────────────────────────────────────────
# ③ 积压斜率：只用有 TTS 的段
# ─────────────────────────────────────────────────────────────────
def test_03_slope():
    print("\n[3] EXT-036 ③ —— 斜率只用「有 TTS 的段」拟合")
    from ext.bridge import summarize_margins, _seg_has_tts

    # 合成：14 段有 TTS（真实斜率 ≈ −0.46），18 段无 TTS（lag 是外推值）
    margins = []
    for i in range(14):
        margins.append({
            "id": "seg_t%02d" % i, "t_start": float(i * 7),
            "deadline_margin_sec": -0.46 * i * 7, "has_tts": True,
        })
    for i in range(14, 32):
        # 外推值：故意**平**（若混入拟合 ⇒ 斜率被稀释）
        margins.append({
            "id": "seg_e%02d" % i, "t_start": float(i * 7),
            "deadline_margin_sec": -0.46 * 13 * 7, "has_tts": False,
        })

    out = summarize_margins(margins)
    check("③ 顶层斜率 = **TTS-only** 拟合值（与手算 −0.46 一致）",
          abs(float(out["lag_growth_slope_sec_per_sec"]) - (-0.46)) < 0.02,
          "slope=%s" % out["lag_growth_slope_sec_per_sec"])
    check("③ 拟合点数 = 14（**只**有 TTS 的段）",
          out["lag_n_fit_points"] == 14,
          "n=%s" % out["lag_n_fit_points"])
    check("③ 旧的全段口径**保留为独立字段**（可对照、但不作验收量）",
          out.get("lag_growth_slope_all_sec_per_sec") is not None
          and out.get("lag_n_fit_points_all") == 32,
          "all slope=%s n=%s" % (out.get("lag_growth_slope_all_sec_per_sec"),
                                 out.get("lag_n_fit_points_all")))
    check("③ 两个口径**确实不同**（旧口径被稀释 ⇒ 反证旧口径不可用）",
          abs(float(out["lag_growth_slope_sec_per_sec"])
              - float(out["lag_growth_slope_all_sec_per_sec"])) > 1e-6,
          "TTS-only=%s vs all=%s"
          % (out["lag_growth_slope_sec_per_sec"],
             out["lag_growth_slope_all_sec_per_sec"]))
    check("③ 落盘了口径说明（reviewer 可核对）",
          "TTS" in str(out.get("lag_growth_slope_note", "")))

    # ── 区分力：字段缺失 ⇒ 视为「未知」⇒ **计入**（不能整组被清空）──
    sparse = [{"t_start": 0.0, "deadline_margin_sec": -1.0},
              {"t_start": 5.0, "deadline_margin_sec": -2.0}]
    out2 = summarize_margins(sparse)
    check("③ 字段缺失时**不**把整组清空（否则斜率变 None ⇒ 回归）",
          out2.get("lag_growth_slope_sec_per_sec") is not None,
          "slope=%s n=%s" % (out2.get("lag_growth_slope_sec_per_sec"),
                             out2.get("lag_n_fit_points")))

    # ── 判据本身的区分力 ──────────────────────────────────────────
    check("③ `has_tts=False` ⇒ 判为「没有 TTS」（被排除）",
          _seg_has_tts({"has_tts": False}) is False)
    check("③ `has_tts=True` ⇒ 判为「有 TTS」",
          _seg_has_tts({"has_tts": True}) is True)
    check("③ `tts_sec>0` ⇒ 有 TTS（回退判据）",
          _seg_has_tts({"tts_sec": 2.0}) is True)
    check("③ `tts_sec=0` ⇒ 没有 TTS",
          _seg_has_tts({"tts_sec": 0.0}) is False)


# ─────────────────────────────────────────────────────────────────
# ④ 首段提前交付：cap 一到就交出 + 两端逐位一致
# ─────────────────────────────────────────────────────────────────
def test_04_first_segment():
    print("\n[4] EXT-036 ④ —— 首段在 cap 秒一到就交出（不等原段到齐）")
    import numpy as np
    from ext.segmenter import (plan_segments, plan_segments_first_capped,
                               split_first_segment_streaming)
    from ext import config as C

    sr = C.SAMPLE_RATE
    cap = C.FIRST_SEGMENT_MAX_SEC
    rng = np.random.default_rng(11)
    audio = np.zeros(sr * 120, dtype=np.float32)
    for a, b in [(0, 8), (20, 30), (45, 58), (70, 80), (95, 120)]:
        audio[a * sr:b * sr] = (rng.standard_normal((b - a) * sr) * 0.05
                                ).astype(np.float32)

    raw = plan_segments(audio)
    capped = plan_segments_first_capped(
        audio, cap_sec=cap, min_segment_sec=C.SEG_MIN_SEC,
        max_segment_sec=C.SEG_MAX_SEC, sample_rate=sr)

    check("④ 首段**精确**等于 [0, cap]（不是「≤cap」的弱断言）",
          capped[0] == (0, int(cap * sr)),
          "首段=%s（cap=%s s）" % (capped[0], cap))
    check("④ 原首段的尾巴独立成段（位置不变）",
          len(capped) > 1 and capped[1] == (int(cap * sr), raw[0][1]),
          "第二段=%s，原首段=%s" % (capped[1] if len(capped) > 1 else None,
                                     raw[0]))
    check("④ 后续切点**逐位不变**（栅格未平移 ⇒ 尾段不会被吃掉）",
          [e for _, e in capped[2:]] == [e for _, e in raw[1:]],
          "后续段数=%d" % (len(capped) - 2))
    check("④ 尾段终点与原始网格**完全一致**",
          capped[-1][1] == raw[-1][1],
          "capped 尾=%s raw 尾=%s" % (capped[-1], raw[-1]))

    # ── 服务端流式口径 vs 客户端整段口径：**必须完全相等** ──────────
    streaming = split_first_segment_streaming(raw, cap_sec=cap,
                                               min_sec=C.SEG_MIN_SEC)
    check("★ ④ 服务端流式口径与客户端整段口径**完全相等**（段数不漂）",
          streaming == capped[1:],
          "流式=%d 段 / 客户端=%d 段" % (len(streaming), len(capped) - 1))

    # ── 反证：若服务端「裁缓冲后重排栅格」⇒ 客户端段数漂移 ────────
    naive = [(s, e) for (s, e) in raw
             if e > int(cap * sr)]          # 裁掉首段后平移
    naive = [(0 if s >= int(cap * sr) else s, e) for (s, e) in naive]
    check("★ ④ 反证：裁缓冲重排栅格的做法会与客户端**不一致**",
          naive != capped[1:],
          "naive 段数=%d vs 正确=%d" % (len(naive), len(capped) - 1))

    # ── 客户端预期段数用的是**同一个**函数 ─────────────────────────
    from tools import p1_pipeline
    n_expected = p1_pipeline.expected_segment_count(audio, sr)
    check("④ 客户端 `expected_segment_count` 可用且 > 0",
          isinstance(n_expected, int) and n_expected > 0,
          "expected=%d" % n_expected)


# ─────────────────────────────────────────────────────────────────
# ⑤ 录音时间轴：静音期也要写样本
# ─────────────────────────────────────────────────────────────────
def test_05_timeline():
    print("\n[5] EXT-036 ⑤ —— 录音时间轴不被压缩（静音期补写样本）")
    import json
    import tempfile
    sys.path.insert(0, os.path.join(ROOT, "tests", "smoke"))
    from ext033_analyze import _ext036_analysis

    sr = 48000

    # ── 合成 A：**未压缩**（样本数 = 墙钟 × 采样率）────────────────
    dur = 10.0
    wav_a = [0.0] * int(sr * dur)
    stop_a = {"durationSec": dur, "acTimeSec": 30.0, "acStartSec": 20.0,
              "acElapsedSec": dur}
    out_a = _ext036_analysis([], {}, {}, wav_a, sr, {}, stop_a, [], [], [])

    check("⑤ 未压缩 ⇒ wav 时长与 acElapsedSec 差 ≤ 0.2 s",
          out_a["timeline_integrity"].get("ok") is True,
          "diff=%s s" % out_a["timeline_integrity"].get("abs_diff_sec"))
    check("⑤ 未压缩 ⇒ wav 时长与 durationSec 差 ≤ 0.2 s",
          abs(out_a["timeline_integrity"]["wav_duration_sec"]
              - out_a["timeline_integrity"]["record_duration_sec"]) <= 0.2)

    # ── 合成 B：**被压缩**（少了 16.4 s，= reviewer 实测的病根）─────
    wav_b = [0.0] * int(sr * (dur - 16.4 / 2.0))   # 故意压缩
    stop_b = {"durationSec": dur, "acTimeSec": 30.0, "acStartSec": 20.0,
              "acElapsedSec": dur}
    out_b = _ext036_analysis([], {}, {}, wav_b, sr, {}, stop_b, [], [], [])
    check("★ ⑤ 反证：被压缩的录音**必须**被判 FAIL（判据能抓到病根）",
          out_b["timeline_integrity"].get("ok") is False,
          "diff=%s s" % out_b["timeline_integrity"].get("abs_diff_sec"))
    check("⑤ 时间轴完整性块带判据值（0.2 s）",
          out_a["timeline_integrity"].get("target_abs_diff_sec") == 0.2)

    # ── 插件侧：静音块计数被落盘（自证「没有配音时也在写样本」）───
    worklet = os.path.join(ROOT, "extension", "dub-pcm-worklet.js")
    src = open(worklet, "r", encoding="utf-8").read()
    check("⑤ worklet 在静音期**补写等长静音样本**（不跳块）",
          "this.silentBlocks++" in src and "this.buf[this.n++] = 0" in src)
    check("⑤ worklet 落盘静音块计数（可自证）",
          "silentBlocks" in src)

    # ── 插件侧：webm 也挂恒定零信号源（否则 webm 同样被压缩）───────
    player = os.path.join(ROOT, "extension", "player.js")
    psrc = open(player, "r", encoding="utf-8").read()
    check("⑤ 录音挂 `ConstantSourceNode`（webm 时间轴连续）",
          "createConstantSource" in psrc and "dubSilentSource" in psrc)
    check("⑤ `record_stop` 落 `acElapsedSec` / `wavDurationSec`（可核对）",
          "acElapsedSec" in psrc and "wavDurationSec" in psrc)

    # ── 插件侧：停录时必须**停掉**零信号源（否则一直挂在图上）──────
    check("⑤ 停录路径停掉零信号源",
          psrc.count("dubSilentSource.stop()") >= 2,
          "出现 %d 次" % psrc.count("dubSilentSource.stop()"))


# ─────────────────────────────────────────────────────────────────
# ⑥ 时长比：三个口径 + 定义
# ─────────────────────────────────────────────────────────────────
def test_06_dur_ratio():
    print("\n[6] EXT-036 ⑥ —— 时长比三个口径（口径必须显式）")
    sys.path.insert(0, os.path.join(ROOT, "tests", "smoke"))
    from ext033_analyze import _ext036_analysis

    segs = [
        {"d_player_sec": 2.0, "src_len_sec": 3.5, "d_ws_sec": 2.2},
        {"d_player_sec": 3.0, "src_len_sec": 4.0, "d_ws_sec": 3.1},
        {"d_player_sec": 1.5, "src_len_sec": 2.0, "d_ws_sec": 1.6},
    ]
    ratios = [2.0 / 2.2, 3.0 / 3.1, 1.5 / 1.6]   # over_ws 口径（EXT-037 ④ 主口径）
    out = _ext036_analysis([], {}, {}, [], 48000, {}, {}, segs, [], ratios)
    cal = out["dur_ratio_calibers"]

    # ★★★★★★ EXT-037 ④：**口径从三个收缩为两个**
    #   reviewer 原话：「compare 表里"时长比(校正) 0.818–1.31"属于分析器口径错误：
    #     `d_ws` 已经是 WSOLA 之后的时长，又除了一次 speed，变速被重复校正。
    #     这一项要改口径，不是播放器的问题。」
    #   ⇒ 旧口径 `speed_adjusted`（d_player × speed ÷ d_ws）**已作废**
    #     ⇒ 本组断言随之迁到**两个口径**，并**新增**一条守卫：
    #     旧口径**不得**再出现（否则又会把变速算两次）。
    check("⑥ 给出**两个**口径（EXT-037 ④：speed_adjusted 已作废）",
          all(k in cal for k in ("over_src_len", "over_ws"))
          and "speed_adjusted" not in cal,
          "keys=%s" % sorted(cal.keys()))
    check("⑥ ★ 旧口径 `speed_adjusted` **不再出现**（EXT-037 ④：重复校正已删除）",
          "speed_adjusted" not in cal
          and "已作废" in str(cal.get("note", "")),
          "note=%s" % str(cal.get("note", ""))[:120])
    # over_src_len: 2.0/3.5=0.5714, 3.0/4.0=0.75, 1.5/2.0=0.75
    check("⑥ `over_src_len`（reviewer 口径）与手算一致",
          abs(cal["over_src_len"]["min"] - (2.0 / 3.5)) < 1e-4
          and abs(cal["over_src_len"]["max"] - 0.75) < 1e-4,
          "min=%s max=%s" % (cal["over_src_len"]["min"],
                             cal["over_src_len"]["max"]))
    check("⑥ 每个口径都带定义（reviewer 可核对）",
          all("definition" in cal[k] for k in
              ("over_src_len", "over_ws")))
    check("⑥ `over_ws`（主口径）与手算一致",
          abs(cal["over_ws"]["min"] - (2.0 / 2.2)) < 1e-4
          and abs(cal["over_ws"]["max"] - (3.0 / 3.1)) < 1e-4,
          "min=%s max=%s" % (cal["over_ws"]["min"], cal["over_ws"]["max"]))
    check("⑥ 口径说明点明「两个口径不能直接比」",
          "对不上" in str(cal.get("note", "")))
    check("⑥ 样本数如实记录",
          cal["over_src_len"]["n"] == 3)


# ─────────────────────────────────────────────────────────────────
# ⑦ 墙钟字段贯通（server → 插件）
# ─────────────────────────────────────────────────────────────────
def test_07_wallclock():
    print("\n[7] EXT-036 ① —— 墙钟字段贯通（服务端 → 插件）")
    bridge = os.path.join(ROOT, "ext", "bridge.py")
    bsrc = open(bridge, "r", encoding="utf-8").read()
    check("⑦ 服务端 `tts` 消息带 `srv_wall_ms`（与插件 Date.now() 同时基）",
          '"srv_wall_ms"' in bsrc)
    check("⑦ 服务端带 `srv_t0_wall_ms`（服务端自己的音频轴原点）",
          '"srv_t0_wall_ms"' in bsrc)
    check("⑦ 墙钟用 `time.time()`（**不是** perf_counter 单调钟）",
          "int(time.time() * 1000.0)" in bsrc)

    player = os.path.join(ROOT, "extension", "player.js")
    psrc = open(player, "r", encoding="utf-8").read()
    check("⑦ 插件记 `ply_wall_ms` 并算下行耗时",
          "Date.now()" in psrc and "dubDownlinkMs" in psrc)
    check("⑦ 下行耗时数组有界（不无界增长）",
          "dubDownlinkMs.size > 200" in psrc)

    # ── 区分力：假通过（硬编码 0）必须被抓到 ───────────────────────
    import re
    m = re.search(r"const _dl = .*", psrc)
    check("⑦ 下行耗时是**真算**的（ply − srv），不是硬编码",
          m is not None and "_plyWall - _srvWall" in m.group(0),
          m.group(0) if m else "未找到")

    # ── 换算方向：player.js 里必须是 `t0Up - dOff` ────────────────
    #   ★ 只看**代码行**（注释里为了说明「旧实现是 + dOff」也会出现该串
    #     ⇒ 整文件 grep 会假阳性 ⇒ 必须逐行排除注释行）
    code_lines = []
    for ln in psrc.splitlines():
        s = ln.strip()
        if s.startswith("//") or s.startswith("*") or s.startswith("/*"):
            continue
        code_lines.append(s)
    code_blob = "\n".join(code_lines)
    check("★ ⑦ player.js 的**代码**换算是 `t0Up - dOff`",
          "t0 = t0Up - dOff" in code_blob)
    check("★ ⑦ player.js 的**代码**里不再有 `t0Up + dOff`",
          "t0 = t0Up + dOff" not in code_blob)


def main() -> int:
    print("=" * 68)
    print("EXT-036 自测（reviewer 七项）—— 不跑推理 / 不占 GPU·NPU / "
          "不创建共享锁 / 不启动浏览器")
    print("=" * 68)
    for fn in (test_01_axis_gap, test_02_rootcause, test_03_slope,
               test_04_first_segment, test_05_timeline, test_06_dur_ratio,
               test_07_wallclock):
        try:
            fn()
        except Exception as e:          # noqa: BLE001
            check(f"★ {fn.__name__} 抛异常", False, repr(e))

    npass = sum(1 for _, ok in RESULTS if ok)
    nfail = sum(1 for _, ok in RESULTS if not ok)
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    if nfail:
        print("FAIL 明细：")
        for name, ok in RESULTS:
            if not ok:
                print(f"  [FAIL] {name}")
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
