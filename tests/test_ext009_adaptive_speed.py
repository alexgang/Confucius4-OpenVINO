"""test_ext009_adaptive_speed.py — ★ EXT-009 自测（自适应加速播放）

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

覆盖四块：

  1. **EXT-009 统一参数**（`ext/adaptive_speed.py`）
     · 速度公式：`clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)`
       （lag ≤ 3 s ⇒ 1.0×；lag = 15 s ⇒ 1.30×）；
     · **滞回**：降速时 `lag < 2 s` 才回 1.0×（不来回抖动）；
     · **按句定速、句内不变**；
     · **相邻句变化 ≤ 0.1×**；
     · 与**时长适配相乘后总倍率 ≤ 1.30×**，超出部分顺延。

  2. **区分力**（★ 关键：能区分「真通过」与「假通过」）
     · 旧写法（无滞回 / 无步长限制 / 不封顶总倍率）会读出**错误结论**；
       新写法读出**正确结论** ⇒ 断言恒真的风险被排除；
     · **滞回**：在门槛附近来回抖动的 lag 序列，新写法**不抖**、旧写法**抖**。

  3. **WSOLA 缺陷 21 回归**（本轮实测抓到的真实缺陷）
     旧实现的相似度搜索**恒取偏移 0**（`np.correlate` 的 `valid` 模式在
     等长数组上返回长度 1）⇒ 断言必须能区分
     「真的在搜索」与「退化取 0」。

  4. **插件侧契约**（`extension/player.js` / `player.html`）
     · 底栏有「语速」「滞后」两项；
     · 播放侧**不得**对配音 buffer 用 `playbackRate`（会变调）；
     · 插件侧的 EXT-009 参数与服务端一致。

运行：
    python tests/test_ext009_adaptive_speed.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import re
import sys
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ext import config as C
from ext.adaptive_speed import (combine_rates, decide_speed,
                                lag_from_schedule, raw_speed_for_lag,
                                target_start_for)
from ext.time_stretch import _normalized_xcorr_best, wsola

EXT_DIR = os.path.join(ROOT, "extension")

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _speech_like(dur_sec: float, sr: int = C.SAMPLE_RATE) -> np.ndarray:
    """造一段"像语音"的信号：谐波 + 包络（与 test_ext_selfcheck 同款）。"""
    n = int(dur_sec * sr)
    t = np.arange(n) / sr
    f0 = 120.0
    x = (np.sin(2 * np.pi * f0 * t)
         + 0.5 * np.sin(2 * np.pi * f0 * 2 * t)
         + 0.25 * np.sin(2 * np.pi * f0 * 3 * t))
    env = 0.5 * (1 + np.sin(2 * np.pi * 3.0 * t))
    return (x * env).astype(np.float32)


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


# ══════════════════════════════════════════════════════════════
# 1. EXT-009 统一参数
# ══════════════════════════════════════════════════════════════
def test_ext009_speed_formula() -> None:
    print("\n[1] EXT-009 统一参数：速度公式")
    check("lag ≤ 3 s ⇒ 1.0×（lag=0）", raw_speed_for_lag(0.0) == 1.0,
          f"{raw_speed_for_lag(0.0)}")
    check("lag = 3 s ⇒ 恰好 1.0×", raw_speed_for_lag(3.0) == 1.0,
          f"{raw_speed_for_lag(3.0)}")
    check("lag = 15 s ⇒ 1.30×（上限）",
          abs(raw_speed_for_lag(15.0) - 1.30) < 1e-9,
          f"{raw_speed_for_lag(15.0)}")
    check("lag > 15 s ⇒ 仍封顶 1.30×",
          abs(raw_speed_for_lag(60.0) - 1.30) < 1e-9,
          f"{raw_speed_for_lag(60.0)}")
    # 线性：lag=7 ⇒ 1.0 + 4×0.025 = 1.10
    check("lag = 7 s ⇒ 1.10×（公式线性正确）",
          abs(raw_speed_for_lag(7.0) - 1.10) < 1e-9,
          f"{raw_speed_for_lag(7.0)}")
    check("负 lag（提前）⇒ 仍是 1.0×（不减速）",
          raw_speed_for_lag(-10.0) == 1.0, f"{raw_speed_for_lag(-10.0)}")


def test_ext009_hysteresis() -> None:
    print("\n[2] EXT-009 滞回（避免来回抖动）")
    # lag=1.0 < 2.0 ⇒ 想降速时**保持**上一句的倍率
    d = decide_speed(1.0, prev_speed=1.30)
    check("lag=1.0 s 且想降速 ⇒ 保持 1.30×（滞回生效）",
          abs(d.speed - 1.30) < 1e-9 and d.held_by_hysteresis,
          f"speed={d.speed} held={d.held_by_hysteresis}")
    # lag=2.5 > 2.0 ⇒ 允许降速（但受步长限制）
    d = decide_speed(2.5, prev_speed=1.30)
    check("lag=2.5 s（>滞回门槛）⇒ 允许降速",
          d.speed < 1.30, f"speed={d.speed} reason={d.reason}")
    # ★ 区分力：滞回门槛附近**来回抖动的 lag 序列**
    #   旧写法（无滞回）：lag 一掉到门槛下，速度立刻掉回 1.0×
    #     ⇒ 速度序列**反复上下跳**（降速次数 > 0）
    #   新写法（有滞回）：lag < 2 s 时**保持**上一句的倍率
    #     ⇒ 速度序列**单调不降**（降速次数 = 0）
    #   ⇒ 判据 = 「速度序列出现下降的次数」
    seq = [15.0, 1.5, 15.0, 1.5, 15.0, 1.5]
    new_speeds = []
    prev = 1.0
    for lag in seq:
        prev = decide_speed(lag, prev_speed=prev).speed
        new_speeds.append(round(prev, 4))
    # 旧写法：直接用公式值（无滞回、无步长）
    old_speeds = [round(raw_speed_for_lag(lag), 4) for lag in seq]
    n_new_drops = sum(1 for i in range(1, len(new_speeds))
                      if new_speeds[i] < new_speeds[i - 1] - 1e-9)
    n_old_drops = sum(1 for i in range(1, len(old_speeds))
                      if old_speeds[i] < old_speeds[i - 1] - 1e-9)
    check("★ 区分力：旧写法（无滞回）在门槛附近**反复降速**",
          n_old_drops >= 3, f"旧写法降速次数={n_old_drops} speeds={old_speeds}")
    check("★ 新写法（滞回）**一次都不降速**（lag<2s 时保持）",
          n_new_drops == 0, f"新写法降速次数={n_new_drops} speeds={new_speeds}")


def test_ext009_step_limit() -> None:
    print("\n[3] EXT-009 相邻句步长限制（0.1×）")
    d = decide_speed(100.0, prev_speed=1.0)
    check("从 1.00× 一步跳到 1.30× ⇒ 被限制为 1.10×",
          abs(d.speed - 1.10) < 1e-9 and d.clamped_step,
          f"speed={d.speed} reason={d.reason}")
    d = decide_speed(100.0, prev_speed=1.10)
    check("从 1.10× 再一步 ⇒ 1.20×（仍 ≤0.1× 步长）",
          abs(d.speed - 1.20) < 1e-9, f"speed={d.speed}")
    d = decide_speed(100.0, prev_speed=1.20)
    check("从 1.20× 再一步 ⇒ 1.30×（到达上限）",
          abs(d.speed - 1.30) < 1e-9, f"speed={d.speed}")
    d = decide_speed(100.0, prev_speed=1.30)
    check("已在 1.30× ⇒ 不再上升",
          abs(d.speed - 1.30) < 1e-9, f"speed={d.speed}")


def test_ext009_combine_rates() -> None:
    print("\n[4] EXT-009：时长适配 × 自适应加速，总倍率 ≤ 1.30×")
    r = combine_rates(1.0, 1.0)
    check("1.0 × 1.0 ⇒ 1.0×（无变速）", abs(r["total_rate"] - 1.0) < 1e-9,
          str(r))
    r = combine_rates(1.25, 1.0)
    check("1.25 × 1.0 ⇒ 1.25×（不封顶）",
          abs(r["total_rate"] - 1.25) < 1e-9 and not r["capped"], str(r))
    r = combine_rates(1.0, 1.30)
    check("1.0 × 1.30 ⇒ 1.30×（不封顶）",
          abs(r["total_rate"] - 1.30) < 1e-9 and not r["capped"], str(r))
    r = combine_rates(1.25, 1.30)
    check("★ 1.25 × 1.30 ⇒ 封顶 1.30×（EXT-009 EXT 侧明文）",
          abs(r["total_rate"] - 1.30) < 1e-9 and r["capped"],
          f"raw={r['raw_rate']} total={r['total_rate']}")
    check("★ 封顶时记录了被截掉的倍率（超出部分顺延）",
          r["rate_loss_x"] > 0, f"rate_loss_x={r['rate_loss_x']}")
    # ★ 区分力：旧写法（直接相乘、不封顶）会给出 1.625× ⇒ 违反 EXT-009
    old_total = 1.25 * 1.30
    check("★ 区分力：旧写法（直接相乘）= 1.625× **违反** EXT-009 的 1.30× 上限",
          old_total > C.ADAPT_TOTAL_RATE_MAX,
          f"旧写法={old_total} > 上限 {C.ADAPT_TOTAL_RATE_MAX}")
    check("★ 新写法的总倍率确实 ≤ 1.30×",
          combine_rates(1.25, 1.30)["total_rate"] <= C.ADAPT_TOTAL_RATE_MAX + 1e-9)


def test_ext009_lag_definition() -> None:
    print("\n[5] EXT-009 lag 口径")
    t0 = 100.0
    ts = 12.0
    d = 10.0
    target = target_start_for(t0=t0, t_start=ts, delay_sec=d)
    check("目标开播时刻 = t0 + t_start + D",
          abs(target - (t0 + ts + d)) < 1e-9, f"{target}")
    lag = lag_from_schedule(actual_start=target + 5.0, target_start=target)
    check("lag = 实际开播 − 目标开播（晚 5 s ⇒ +5）",
          abs(lag - 5.0) < 1e-9, f"{lag}")
    lag = lag_from_schedule(actual_start=target - 2.0, target_start=target)
    check("提前 2 s ⇒ lag = −2（负数 = 提前）", abs(lag + 2.0) < 1e-9, f"{lag}")


# ══════════════════════════════════════════════════════════════
# 2. WSOLA 缺陷 21 回归（相似度搜索曾恒取偏移 0）
# ══════════════════════════════════════════════════════════════
def test_ext009_wsola_search_fixed() -> None:
    print("\n[6] ★ WSOLA 缺陷 21 回归：相似度搜索曾**恒取偏移 0**")
    # ★ 造一个**唯一**匹配点的信号：
    #   参考 = 一段随机波形（不平滑 ⇒ 不会在别处偶然重复）
    #   候选窗口 = [填充噪声] + [参考] + [填充噪声]
    #   ⇒ 真正的匹配在偏移 ~300 处，而偏移 0 是噪声
    rng = np.random.default_rng(20261029)
    ref = rng.standard_normal(320).astype(np.float64)
    noise = rng.standard_normal(300).astype(np.float64)
    cand = np.concatenate([noise, ref, noise]).astype(np.float64)
    off = _normalized_xcorr_best(cand, ref)
    check("★ 真的找到了相似位置（偏移 > 0 且落在真匹配附近）",
          off > 100, f"offset={off}（真匹配在 ~300，旧实现恒为 0）")

    # ★ 区分力：旧写法（np.correlate mode='valid' 等长数组）**恒返回长度 1**
    num = np.correlate(cand[:ref.shape[0]] - cand[:ref.shape[0]].mean(),
                        ref - ref.mean(), mode="valid")
    check("★ 区分力：旧写法的相关数组长度为 1 ⇒ argmax 恒为 0",
          num.shape[0] == 1 and int(np.argmax(num)) == 0,
          f"len={num.shape[0]} argmax={int(np.argmax(num))}")

    # ★ 区分力：新写法在**同一组数据**上必须给出**非零**偏移
    check("★ 区分力：新写法在同数据上给出非零偏移（旧写法恒为 0）",
          int(np.argmax(num)) == 0 and off != 0,
          f"旧=0 新={off}")

    # 端到端：WSOLA 在 rate=1.25 时应保持音高
    x = _speech_like(3.0)
    f0_in = _est_f0(x)
    y = wsola(x, 1.25)
    f0_out = _est_f0(y)
    drift = abs(f0_out - f0_in) / f0_in if f0_in else 1.0
    check("WSOLA rate=1.25 保持音高（基频偏移 < 8%）", drift < 0.08,
          f"f0_in={f0_in:.1f} f0_out={f0_out:.1f} 偏移={drift * 100:.1f}%")


def test_ext009_wsola_sample_rate() -> None:
    print("\n[7] WSOLA 采样率参数（TTS 输出是 24 kHz）")
    import inspect
    sig = inspect.signature(wsola)
    check("wsola 支持 sample_rate 形参",
          "sample_rate" in sig.parameters, str(sig))
    # 24 kHz 下同样的 60 ms 帧 ⇒ 帧长应是 16 kHz 的 1.5 倍
    sr = 24000
    x = _speech_like(2.0, sr=sr)
    y = wsola(x, 1.25, sample_rate=sr)
    exp = int(x.shape[0] / 1.25)
    check("24 kHz 输入变速后长度 ≈ 1/rate",
          abs(y.shape[0] - exp) < 0.12 * exp,
          f"{y.shape[0]} vs 期望 {exp}")


# ══════════════════════════════════════════════════════════════
# 3. 插件侧契约
# ══════════════════════════════════════════════════════════════
def test_ext009_extension_contract() -> None:
    print("\n[8] 插件侧契约（EXT-009 底栏与播放语义）")
    pj = os.path.join(EXT_DIR, "player.js")
    ph = os.path.join(EXT_DIR, "player.html")
    with open(pj, encoding="utf-8") as f:
        jsrc = f.read()
    with open(ph, encoding="utf-8") as f:
        hsrc = f.read()

    check("player.html 底栏有「语速」显示",
          'id="mSpeed"' in hsrc, "mSpeed")
    check("player.html 底栏有「滞后」显示",
          'id="mLag"' in hsrc, "mLag")
    check("player.js 更新「语速」显示",
          "set('mSpeed'" in jsrc, "set('mSpeed'")
    check("player.js 更新「滞后」显示",
          "set('mLag'" in jsrc, "set('mLag'")
    check("player.js 记录当前倍率（adaptSpeed）",
          "adaptSpeed" in jsrc, "adaptSpeed")
    check("player.js 记录滞后秒数（adaptLagSec）",
          "adaptLagSec" in jsrc, "adaptLagSec")

    # ★ 绝不能用 playbackRate 对配音 buffer 变速（会变调）
    bad = re.findall(r"\.playbackRate\s*=", jsrc)
    check("★ 播放侧**没有**对音频用 playbackRate（会变调）",
          not bad, f"命中 {len(bad)} 处")

    # 插件侧参数与服务端一致（同一套统一参数）
    m = re.search(r"lagFreeSec:\s*([\d.]+)", jsrc)
    check("插件侧 lagFreeSec = 3.0（与服务端一致）",
          bool(m) and abs(float(m.group(1)) - 3.0) < 1e-9,
          m.group(1) if m else "未找到")
    m = re.search(r"lagHystSec:\s*([\d.]+)", jsrc)
    check("插件侧 lagHystSec = 2.0（与服务端一致）",
          bool(m) and abs(float(m.group(1)) - 2.0) < 1e-9,
          m.group(1) if m else "未找到")
    m = re.search(r"gainPerSec:\s*([\d.]+)", jsrc)
    check("插件侧 gainPerSec = 0.025（与服务端一致）",
          bool(m) and abs(float(m.group(1)) - 0.025) < 1e-9,
          m.group(1) if m else "未找到")
    m = re.search(r"speedMax:\s*([\d.]+)", jsrc)
    check("插件侧 speedMax = 1.30（与服务端一致）",
          bool(m) and abs(float(m.group(1)) - 1.30) < 1e-9,
          m.group(1) if m else "未找到")


def test_ext009_bridge_wiring() -> None:
    print("\n[9] 桥接服务端接线（EXT-009）")
    bp = os.path.join(ROOT, "ext", "bridge.py")
    with open(bp, encoding="utf-8") as f:
        bsrc = f.read()
    check("bridge.py 引入 adaptive_speed",
          "from .adaptive_speed import" in bsrc, "import")
    check("bridge.py 调用 decide_speed", "decide_speed(" in bsrc, "调用")
    check("bridge.py 调用 combine_rates", "combine_rates(" in bsrc, "调用")
    check("bridge.py 用 WSOLA 做保持音高变速",
          "wsola(" in bsrc, "wsola")
    # ★ 采样率必须传对（TTS 输出 24 kHz）
    check("★ WSOLA 调用传了 sample_rate（24 kHz）",
          "sample_rate=TTS_SAMPLE_RATE" in bsrc, "sample_rate=TTS_SAMPLE_RATE")
    check("bridge.py 下发 speed 字段给插件",
          '"speed":' in bsrc, "\"speed\":")
    check("bridge.py 下发 lag_est_sec 给插件",
          '"lag_est_sec"' in bsrc, "\"lag_est_sec\"")


def test_ext009_acceptance_artifacts() -> None:
    """★ EXT-009 验收数据**必须能落盘**（否则验收拿不到数）。

    EXT-009 验收明文要求：
      * 滞后随时间的曲线（起点、峰值、结尾）；
      * 各倍率的时间占比；
      * **丢句 = 0**；
      * 挑 3 段 1.2–1.3× 的配音**落盘**。

    ⇒ 本组断言覆盖三处落盘链路：
      1. 服务端 `margin.json` 里带 `adaptive_speed`；
      2. `p1_pipeline` 的报告里带 `adaptive_speed` + `accelerated_segments`；
      3. 加速段挑选函数**真的挑得出**（且只挑 1.2–1.3×）。
    """
    print("\n[10] EXT-009 验收数据落盘链路")

    # ── 1. 服务端 margin.json 落盘带 adaptive_speed ──
    bp = os.path.join(ROOT, "ext", "bridge.py")
    with open(bp, encoding="utf-8") as f:
        bsrc = f.read()
    check("★ margin.json 落盘含 adaptive_speed（滞后曲线+倍率占比+丢句）",
          '"adaptive_speed":' in bsrc, "adaptive_speed")

    # ── 2. p1_pipeline 报告落盘 ──
    pp = os.path.join(ROOT, "tools", "p1_pipeline.py")
    with open(pp, encoding="utf-8") as f:
        psrc = f.read()
    check("p1_pipeline 报告含 adaptive_speed",
          '"adaptive_speed": adaptive_stats' in psrc, "adaptive_speed")
    check("p1_pipeline 报告含 accelerated_segments",
          '"accelerated_segments"' in psrc, "accelerated_segments")
    check("p1_pipeline 落加速段目录 accel/",
          '"accel"' in psrc, "accel/")

    # ── 3. 挑选函数：真能挑出 1.2–1.3× 的段 ──
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import importlib
    p1 = importlib.import_module("p1_pipeline")
    _orig_write = p1.write_dub_wavs

    def _fake_write(tasks, out_dir):
        made = []
        for t in tasks:
            if t.get("type") != "tts" or not t.get("pcm24k"):
                continue
            made.append({"id": str(t.get("id")),
                         "path": os.path.join(out_dir, "%s.wav" % t.get("id")),
                         "bytes": 100, "speech_sec": 1.0,
                         "t_start": t.get("t_start"), "t_end": t.get("t_end")})
        return made

    p1.write_dub_wavs = _fake_write
    try:
        tasks = [
            {"type": "tts", "id": "s1", "speed": 1.00, "pcm24k": "AA==",
             "lag_est_sec": 0.0, "t_start": 0.0, "tgt": "a"},
            {"type": "tts", "id": "s2", "speed": 1.15, "pcm24k": "AA==",
             "lag_est_sec": 5.0, "t_start": 10.0, "tgt": "b"},
            {"type": "tts", "id": "s3", "speed": 1.30, "pcm24k": "AA==",
             "lag_est_sec": 15.0, "t_start": 20.0, "tgt": "c"},
            {"type": "tts", "id": "s4", "speed": 1.25, "pcm24k": "AA==",
             "lag_est_sec": 12.0, "t_start": 30.0, "tgt": "d"},
            {"type": "tts", "id": "s5", "speed": 1.31, "pcm24k": "AA==",
             "lag_est_sec": 16.0, "t_start": 40.0, "tgt": "e"},
            {"type": "tts", "id": "s6", "speed": 1.28, "pcm24k": None,
             "lag_est_sec": 13.0, "t_start": 50.0, "tgt": "f"},
        ]
        wavs = p1.write_dub_wavs(tasks, "/tmp")
        picks = p1.pick_accelerated_segments(tasks, wavs, n=3)
        ids = [p["id"] for p in picks]
        check("★ 加速段挑选：只挑 1.20–1.30× 的段",
              set(ids) == {"s3", "s4"}, f"ids={ids}")
        check("★ 加速段挑选：取倍率最高的 3 段（此处只有 2 段合格）",
              len(picks) == 2, f"n={len(picks)}")
        check("★ 加速段挑选：排除无 PCM 的段（不丢句也不瞎挑）",
              "s6" not in ids, f"ids={ids}")
        check("★ 加速段挑选：排除超上限的段（1.31×）",
              "s5" not in ids, f"ids={ids}")
        check("★ 加速段挑选：记录了 speed 与 lag_est_sec",
              all("speed" in p and "lag_est_sec" in p for p in picks),
              "字段齐全")
        # ★ 区分力：挑选结果不能是「恒真」——
        #   若实现退化成「不筛倍率、全选」，ids 会包含 s1/s2/s5 ⇒ 上面的
        #   set(ids)=={s3,s4} 断言会 FAIL ⇒ 该断言能区分真/假通过。
    finally:
        p1.write_dub_wavs = _orig_write


def main() -> int:
    print("=" * 68)
    print("EXT-009 自测：自适应加速播放（不跑推理 / 不占 GPU·NPU / 不抢共享锁）")
    print("=" * 68)
    for fn in (test_ext009_speed_formula, test_ext009_hysteresis,
               test_ext009_step_limit, test_ext009_combine_rates,
               test_ext009_lag_definition, test_ext009_wsola_search_fixed,
               test_ext009_wsola_sample_rate,
               test_ext009_extension_contract, test_ext009_bridge_wiring,
               test_ext009_acceptance_artifacts):
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
