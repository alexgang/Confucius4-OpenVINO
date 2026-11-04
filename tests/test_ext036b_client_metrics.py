# -*- coding: utf-8 -*-
"""test_ext036b_client_metrics.py — EXT-036 补测：客户端实测数据的**上报闭环**

## 背景（这一组为什么必须存在）

§28（EXT-036 交卷）时，两条验收因 `MACHINE_LOCK` 被别的模块占用而**没跑完**：

* ① `|plyReady − srvReady − 上行延迟|` 的 **P95 ≤ 0.3 s**
* ⑤ `|wav 时长 − durationSec|` **≤ 0.2 s**

补测已用真实三引擎 e2e（`20261104_194608`）实测通过。

但补测**同时暴露了一个真缺陷**（不是测出来的好消息，是漏出来的坑）：

    客户端**测得到**这三项 —— `ply_wall_ms − srv_wall_ms`（真实下行耗时）、
    `readyToStartSec`（就绪→起播）、`t0UpPlayerOffsetSec`（轴偏移），
    也都落进了 `dub_sync.json`；
    ⇒ 但**只留在插件本地**，**从不上报服务端**
    ⇒ `margin.json` 的 `sync_rootcause` 里
      `server_to_player_sec` / `downlink_latency_sec` /
      `player_queue_sec_mean` **三项全为 null**
    ⇒ 「非 TTS 固定项」只加得上其中一部分 ⇒ **归因不完整**
      （reviewer EXT-036 ② 要求的是**逐项分解**）。

且更糟：`non_tts_fixed_detail` 把这些 null **强转成 `0.0`**
⇒ 读起来像「**实测为零**」⇒ **假数据**。

## 本文件要验什么

1. 客户端把实测值**上报**了（`client_metrics` 消息 + 上报函数）。
2. 服务端**收下并记住**这些值（`note_client_metrics`）。
3. 服务端落盘时这三项**不再是 null**（`margin.json` 能直接核对）。
4. ★ **未实测项不许被写成 0**：`non_tts_fixed_detail` 里 null 的项
   必须仍是 `None`，且**不计入** `non_tts_fixed_sec` 合计
   ⇒ 合计是**下界**，并用 `non_tts_fixed_is_lower_bound` 标明。
5. ★ **反向守卫**：如果把「null ⇒ 0.0」的强转改回来（= 回到旧行为），
   本组断言**必须 FAIL** ⇒ 证明这道守卫**抓得住**。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（全部合成数据）。

运行：
    python tests/test_ext036b_client_metrics.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "ext"), os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                            ("  —— %s" % detail) if detail else ""))


# ══════════════════════════════════════════════════════════════════
# ① 客户端确实在上报
# ══════════════════════════════════════════════════════════════════
def test_01_client_reports() -> None:
    print("\n--- ① 客户端上报（player.js）---")
    psrc = open(os.path.join(ROOT, "extension", "player.js"),
                "r", encoding="utf-8").read()

    check("① 上报函数存在（`reportClientMetrics`）",
          "function reportClientMetrics()" in psrc)
    check("① 发的是 `client_metrics` 消息",
          "type: 'client_metrics'" in psrc)
    check("① 上报**逐段下行耗时**（downlink_ms）",
          "downlink_ms:" in psrc)
    check("① 上报**播放端排队**（player_queue_sec）",
          "player_queue_sec:" in psrc)
    check("① 上报**轴偏移**（t0_up_player_offset_sec）",
          "t0_up_player_offset_sec:" in psrc)

    # ★ 上报必须**有界** ⇒ 不制造「内存不持续增长」那类回归
    check("★ 上报列表有界（≤200）",
          ".slice(-200)" in psrc)

    # ★ 上报值必须**来自实测**（不能是硬编码常量）
    check("★ 下行耗时取自 `dubDownlinkMs`（实测值，非硬编码）",
          "dubDownlinkMs.entries()" in psrc)
    check("★ 播放端排队取自 `dubSyncDetail`（实测值，非硬编码）",
          "metrics.dubSyncDetail" in psrc)

    # ★ margin dump **之前**必须先上报 ⇒ 否则落盘时还是没有
    check("★ `requestMarginDump` 里先上报再 dump",
          psrc.index("reportClientMetrics()")
          < psrc.index("type: 'dump_margin'"))

    # ★ 没测到就不报（绝不用 0 冒充「实测为零」）
    check("★ 未测到的轴偏移报 null（不报 0）",
          "typeof off === 'number' && isFinite(off) ? off : null" in psrc)


# ══════════════════════════════════════════════════════════════════
# ② 服务端收下并记住
# ══════════════════════════════════════════════════════════════════
def test_02_server_receives() -> None:
    print("\n--- ② 服务端接收（bridge.py）---")
    bsrc = open(os.path.join(ROOT, "ext", "bridge.py"),
                "r", encoding="utf-8").read()

    check("② 服务端处理 `client_metrics` 消息",
          'mtype == "client_metrics"' in bsrc)
    check("② 有 `note_client_metrics` 方法",
          "def note_client_metrics(" in bsrc)
    check("② 有 `client_metrics_summary` 汇总方法",
          "def client_metrics_summary(" in bsrc)
    check("② 汇总结果落进 `margin.json`（`client_metrics` 键）",
          '"client_metrics":' in bsrc)

    # ★ 客户端数据必须记到**生产者会话**（uplink）⇒ 与 per_segment 同源
    check("★ 记到生产者会话（`_producer_session`）而非仅 player 会话",
          "_cms = _producer_session(" in bsrc
          and "_cms.note_client_metrics(msg)" in bsrc)

    # ★ 负值无效（下行耗时不可能为负）⇒ 必须过滤
    check("★ 负值视为无效（不记）",
          "if f < 0.0:" in bsrc and "continue" in bsrc)

    # ★ 有界（防无界增长）
    check("★ 客户端数据有界（≤200）",
          "self.client_downlink_ms = vals[-200:]" in bsrc
          and "self.client_player_queue_sec = vals[-200:]" in bsrc)


# ══════════════════════════════════════════════════════════════════
# ③ 落盘时不再是 null
# ══════════════════════════════════════════════════════════════════
def test_03_values_reach_margin() -> None:
    print("\n--- ③ 落盘不再是 null（合成数据）---")
    from ext.bridge import Session, decompose_sync_rootcause

    sess = Session.__new__(Session)
    # 手工初始化客户端实测字段（绕开引擎初始化，不占设备）
    sess.client_downlink_ms = [16.0, 39.0, 34.0, 121.0, 48.0,
                               27.0, 29.0, 25.0, 4.0, 11.0]
    sess.client_player_queue_sec = [1.719, 0.5, 2.25, 0.3]
    sess.client_t0_up_player_offset_sec = -3.1786666666666665

    cm = sess.client_metrics_summary()
    check("③ 下行耗时 P95 有值（不是 null）",
          cm.get("downlink_p95_ms") is not None,
          "p95=%s ms" % cm.get("downlink_p95_ms"))
    check("③ 下行耗时 P95 = 121 ms（最近秩口径）",
          abs(float(cm["downlink_p95_ms"]) - 121.0) < 1e-6,
          "实算=%s" % cm.get("downlink_p95_ms"))
    check("③ 播放端排队有值",
          cm.get("player_queue_p50_sec") is not None,
          "p50=%s s" % cm.get("player_queue_p50_sec"))
    check("③ 轴偏移有值（**有符号**，原样保留）",
          cm.get("t0_up_player_offset_sec") is not None
          and float(cm["t0_up_player_offset_sec"]) < 0.0,
          "offset=%s s" % cm.get("t0_up_player_offset_sec"))

    # ★ 没报 ⇒ None（不臆造）
    sess2 = Session.__new__(Session)
    sess2.client_downlink_ms = []
    sess2.client_player_queue_sec = []
    sess2.client_t0_up_player_offset_sec = None
    cm2 = sess2.client_metrics_summary()
    check("★ 没上报 ⇒ 全部 None（**不臆造**）",
          cm2.get("downlink_p95_ms") is None
          and cm2.get("player_queue_p50_sec") is None
          and cm2.get("t0_up_player_offset_sec") is None)


# ══════════════════════════════════════════════════════════════════
# ④ ★ 核心守卫：未实测项不许被写成 0
# ══════════════════════════════════════════════════════════════════
def test_04_null_not_coerced_to_zero() -> None:
    print("\n--- ④ ★ 未实测项不许被写成 0（核心守卫）---")
    from ext.bridge import decompose_sync_rootcause

    margins = [
        {"id": "seg_0", "t_start": 0.0, "asr_sec": 2.0, "speed": 1.0,
         "has_tts": True, "tts_sec": 2.0},
        {"id": "seg_1", "t_start": 3.5, "asr_sec": 3.0, "speed": 1.0,
         "has_tts": True, "tts_sec": 2.0},
    ]

    # ── 情形 A：**什么都没报** ⇒ 三项都应是 None，且不计入合计 ──
    out = decompose_sync_rootcause(margins, delay_sec=10.0)
    det = out.get("non_tts_fixed_detail", {})

    check("④ A：轴缺口是 None（不是 0.0）",
          det.get("axis_gap_sec") is None,
          "实算=%r" % det.get("axis_gap_sec"))
    check("④ A：下行耗时是 None（不是 0.0）",
          det.get("downlink_latency_sec") is None,
          "实算=%r" % det.get("downlink_latency_sec"))
    check("④ A：播放端排队是 None（不是 0.0）",
          det.get("player_queue_sec") is None,
          "实算=%r" % det.get("player_queue_sec"))
    check("④ A：列出了**哪些项没测到**（`unmeasured`）",
          isinstance(det.get("unmeasured"), list)
          and "axis_gap_sec" in det.get("unmeasured", []),
          "unmeasured=%r" % det.get("unmeasured"))
    check("④ A：合计标明是**下界**",
          out.get("non_tts_fixed_is_lower_bound") is True)

    # ★ 关键断言：合计**只**由已实测项构成
    #   ASR 均值 = (2.0 + 3.0) / 2 = 2.5；上行 feed_lag 夹到 0
    #   ⇒ 合计应为 2.5（**不是** 2.5 + 三个 0，那也一样）
    #   ⇒ 真正要验的是：**没测到的项没被偷偷加进去**
    expect = 2.5
    check("④ A：合计 = 已实测项之和（未测项不计入）",
          abs(float(out["non_tts_fixed_sec"]) - expect) < 1e-6,
          "实算=%s 手算=%s" % (out.get("non_tts_fixed_sec"), expect))

    # ── 情形 B：**报了**三项 ⇒ 合计应当把它们**加进去** ──────────
    out_b = decompose_sync_rootcause(
        margins, delay_sec=10.0,
        downlink_latency_sec=0.121,
        server_to_player_sec=3.1786666666666665,
        player_detail=[{"readyToStartSec": 1.0},
                       {"readyToStartSec": 3.0}])
    det_b = out_b.get("non_tts_fixed_detail", {})
    expect_b = 2.5 + 0.121 + 3.1786666666666665 + 2.0
    # ★ 合计按**毫秒精度**落盘（`round(..., 3)`）⇒ 容差取 1e-3
    check("④ B：报了三项 ⇒ 合计含这三项",
          abs(float(out_b["non_tts_fixed_sec"]) - expect_b) < 1e-3,
          "实算=%s 手算=%.6f" % (out_b.get("non_tts_fixed_sec"), expect_b))
    check("④ B：不再是下界（全测到了）",
          out_b.get("non_tts_fixed_is_lower_bound") is False)
    check("④ B：下行耗时被记成 0.121 s（**秒**，不是毫秒）",
          abs(float(det_b.get("downlink_latency_sec")) - 0.121) < 1e-9,
          "实算=%r" % det_b.get("downlink_latency_sec"))
    check("④ B：播放端排队均值 = 2.0 s",
          abs(float(det_b.get("player_queue_sec")) - 2.0) < 1e-9,
          "实算=%r" % det_b.get("player_queue_sec"))

    # ── 情形 C：**只报一部分** ⇒ 仍是下界，且只加报的那部分 ──────
    out_c = decompose_sync_rootcause(
        margins, delay_sec=10.0, downlink_latency_sec=0.121)
    det_c = out_c.get("non_tts_fixed_detail", {})
    check("④ C：只报一项 ⇒ 仍是下界",
          out_c.get("non_tts_fixed_is_lower_bound") is True)
    check("④ C：只加了报的那一项（2.5 + 0.121）",
          abs(float(out_c["non_tts_fixed_sec"]) - 2.621) < 1e-6,
          "实算=%s" % out_c.get("non_tts_fixed_sec"))
    check("④ C：没报的两项仍是 None",
          det_c.get("axis_gap_sec") is None
          and det_c.get("player_queue_sec") is None)


# ══════════════════════════════════════════════════════════════════
# ⑤ 服务端把客户端数据喂进分解的接线
# ══════════════════════════════════════════════════════════════════
def test_05_wiring() -> None:
    print("\n--- ⑤ 接线（喂进分解的入参）---")
    from ext.bridge import Session, _client_rootcause_kwargs

    sess = Session.__new__(Session)
    sess.client_downlink_ms = [16.0, 39.0, 34.0, 121.0]
    sess.client_player_queue_sec = [1.0, 3.0]
    sess.client_t0_up_player_offset_sec = -3.1786666666666665

    kw = _client_rootcause_kwargs(sess)
    check("⑤ 下行耗时按 **P95/1000** 传（判据是 P95 ≤ 0.3 s）",
          abs(float(kw.get("downlink_latency_sec")) - 0.121) < 1e-9,
          "实算=%r" % kw.get("downlink_latency_sec"))
    check("⑤ 轴缺口取**绝对值**（实测是有符号的 −3.18）",
          abs(float(kw.get("server_to_player_sec")) - 3.1786666666666665)
          < 1e-6,
          "实算=%r" % kw.get("server_to_player_sec"))
    check("⑤ 播放端排队逐段传入",
          isinstance(kw.get("player_detail"), list)
          and len(kw["player_detail"]) == 2)

    # ★ 什么都没报 ⇒ **一个参数都不传**（⇒ 分解里是 None，不是 0）
    sess2 = Session.__new__(Session)
    sess2.client_downlink_ms = []
    sess2.client_player_queue_sec = []
    sess2.client_t0_up_player_offset_sec = None
    kw2 = _client_rootcause_kwargs(sess2)
    check("★ 没报 ⇒ 不传任何参数（不留 0 值）",
          "downlink_latency_sec" not in kw2
          and "server_to_player_sec" not in kw2
          and "player_detail" not in kw2,
          "实算=%r" % kw2)


def main() -> int:
    print("=" * 68)
    print("EXT-036 补测自测 —— 客户端实测数据的上报闭环")
    print("（不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器）")
    print("=" * 68)
    for fn in (test_01_client_reports, test_02_server_receives,
               test_03_values_reach_margin,
               test_04_null_not_coerced_to_zero, test_05_wiring):
        try:
            fn()
        except Exception as e:          # noqa: BLE001
            check("★ %s 抛异常" % fn.__name__, False, repr(e))

    npass = sum(1 for _, ok in RESULTS if ok)
    nfail = sum(1 for _, ok in RESULTS if not ok)
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    if nfail:
        print("FAIL 明细：")
        for name, ok in RESULTS:
            if not ok:
                print("  [FAIL] %s" % name)
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
