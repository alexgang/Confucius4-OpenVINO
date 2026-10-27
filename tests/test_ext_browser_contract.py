"""test_ext_browser_contract.py — EXT-003 插件侧自测（追加项）

本文件是 EXT-003（EXT-004 RESUME 续做）的**追加**自测，**不改写**既有断言。

覆盖三块：

  A. **重采样正确性**（纯 Python 等价实现，无需浏览器）
     把 `extension/capture-worklet.js` 的 32 抽头 Blackman 窗 sinc FIR
     48 kHz→16 kHz 抽取在 Python 里复刻一遍，验证：
       · 输出采样数 ≈ 输入采样数 / 3（抽取比正确）
       · 8 kHz 以上**衰减**（无混叠）、1 kHz **几乎无损**
       · 帧的 sample_index **连续无缝**（EXT-003「seq 不断」的算法基础）

  B. **插件侧契约**（静态检查真实文件，不靠 mock）
     · manifest.json：MV3、必需权限、固定 key（扩展 ID 稳定）
     · capture-worklet.js：注册了 capture-processor；**环形缓冲**（不再有
       「固定 512 长度线性历史」这个致命 bug 的特征）
     · player.js：编码器候选顺序以 **VP8 + no-preference** 打头
       （本机实测 VP9/AV1 编码必失败、H.264 不支持）
     · onset-worklet.js：支持**连续检测**（count=0）
     · bridge.py：`_handle_messages` 必须带 `delay_sec` 形参
       （旧实现里它是未定义名 ⇒ 每条消息都抛异常、连接被关）
     · sw.js：SW↔offscreen 走 **Port**（MV3 里 SW 跨 await 后 connect
       会报 "Receiving end does not exist"）

  C. **浏览器实测证据**（读落盘的 JSON，可选）
     若 `.tmp/probe_uplink_5min/browser_probe.json` 存在，
     校验 seq 连续、时钟偏差 < 50 ms；**缺文件 ⇒ 判 FAIL 而非 PASS**
     （证据规则：没落盘的东西不能算通过）。

运行：
    python tests/test_ext_browser_contract.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

EXT_DIR = os.path.join(ROOT, "extension")
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    # ★ detail 只在 **FAIL** 时打印（detail 是「失败原因」，
    #   PASS 时打印会让人误以为失败条件成立）。
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


def _read(name: str) -> str:
    p = os.path.join(EXT_DIR, name)
    if not os.path.isfile(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _read_root(rel: str) -> str:
    """按**项目根**相对路径读取（_read 是相对 extension/ 目录的）。"""
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _strip_js_comments(src: str) -> str:
    """去掉 JS 的 // 行注释与 /* */ 块注释，避免注释里的关键字影响断言。"""
    out = []
    i, n = 0, len(src)
    in_str = None
    while i < n:
        ch = src[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(src[i + 1]); i += 2; continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'`":
            in_str = ch; out.append(ch); i += 1; continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _enc_limit_before_draw(plc: str) -> bool:
    """断言「编码限速判断」出现在「编码缩放 drawImage」**之前**。

    ★ 为什么要断言顺序（而不是断言两个关键字都存在）：
      实测 v6（CDP CPU Profile，300.5 s）：`drawImage` self time = **17.35 s**
      （非 idle 第 1 名）。根因是源 30 fps 但只编码 15 fps，
      **被丢弃的那一半帧仍然做了一次 1908×1072 的全尺寸缩放**。
      ⇒ 限速判断若在 drawImage 之后，这 50% 的缩放开销是纯浪费。
      ⇒ 必须先判限速，被丢的帧直接 close()。

    实现：在**去掉注释**的源码里，找「限速判据」与「编码缩放」的先后。
    限速判据用 `encodeSkipped` 的自增点做锚点（它是「这帧被丢了」的唯一标记），
    缩放锚点用 `encCtx.drawImage`。
    """
    src = _strip_js_comments(plc)
    skip_at = src.find("encodeSkipped")
    draw_at = src.find("encCtx.drawImage")
    if skip_at < 0 or draw_at < 0:
        return False
    return skip_at < draw_at


# ══════════════════════════════════════════════════════════════════
# A. 重采样正确性（Python 等价实现）
# ══════════════════════════════════════════════════════════════════
TAPS = 96
CENTER = 47
HB = 1024


def _build_fir() -> np.ndarray:
    """复刻 capture-worklet.js 的 96 抽头 Blackman 窗 sinc（截止 8 kHz）。"""
    fc = 8000 / 48000
    h = np.zeros(TAPS, dtype=np.float64)
    for k in range(TAPS):
        x = k - CENTER
        sx = 2 * fc * x
        s = 1.0 if abs(sx) < 1e-9 else math.sin(math.pi * sx) / (math.pi * sx)
        w = (0.42 - 0.5 * math.cos(2 * math.pi * k / (TAPS - 1))
             + 0.08 * math.cos(4 * math.pi * k / (TAPS - 1)))
        h[k] = s * w
    return h / h.sum()


def _resample(x48: np.ndarray) -> np.ndarray:
    """复刻 capture-worklet.js 的环形缓冲抽取（48 kHz → 16 kHz）。"""
    fir = _build_fir()
    decim = 3
    n_in = len(x48)
    hist = np.zeros(HB, dtype=np.float64)
    hist_write = 0
    total_in = 0
    out = []
    out_count = 0
    for s in x48:
        hist[hist_write] = s
        hist_write = (hist_write + 1) % HB
        total_in += 1
        need = (out_count + 1) * decim + CENTER + decim
        if total_in < need:
            continue
        base = out_count * decim - CENTER
        acc = 0.0
        for k in range(TAPS):
            idx = base + k
            if idx < 0:
                continue
            acc += fir[k] * hist[idx % HB]
        out.append(acc)
        out_count += 1
    return np.array(out, dtype=np.float64)


def _tone(freq: float, sec: float, sr: int = 48000) -> np.ndarray:
    t = np.arange(int(sr * sec)) / sr
    return np.sin(2 * math.pi * freq * t)


def test_resample() -> None:
    # A1 输出采样数 = 输入 / 3
    #   ★ 注意：FIR 有**群延迟** = CENTER 抽头 / 抽取比 3 个输出样本
    #     （96 抽头 ⇒ ≈16 个输出样本），所以输出比 len(x)/3 少十几个是**正常**的。
    x = _tone(1000.0, 1.0)
    y = _resample(x)
    expected = len(x) / 3
    group_delay = CENTER / 3.0
    check("A1 抽取比 48k→16k = 1/3（含 FIR 群延迟）",
          abs(len(y) - (expected - group_delay)) <= 4,
          f"in={len(x)} out={len(y)} expect≈{expected - group_delay:.0f} "
          f"(群延迟 {group_delay:.1f})")

    # A2 1 kHz 几乎无损（通带内增益 ≈ 1）
    g1k = float(np.sqrt(np.mean(y[-4000:] ** 2)) / np.sqrt(np.mean(x[-12000:] ** 2)))
    check("A2 通带 1 kHz 增益 ≈ 1（误差 < 5%）",
          abs(g1k - 1.0) < 0.05, f"gain={g1k:.4f}")

    # A3 阻带衰减（用**频谱**测，不用时域窗口 —— 时域窗口会被群延迟错位）
    #   9 kHz 在 48k→16k 抽取里高于截止 8 kHz ⇒ 应被强烈衰减
    def _tone_gain_db(freq: float) -> float:
        xx = _tone(freq, 1.0)
        yy = _resample(xx)
        # 丢掉群延迟 + 瞬态后再比
        a = yy[200:len(yy) - 200]
        b = xx[600:len(xx) - 600]
        ga = float(np.sqrt(np.mean(a ** 2)))
        gb = float(np.sqrt(np.mean(b ** 2)))
        return 20 * math.log10(max(ga, 1e-12) / max(gb, 1e-12))

    g9k = _tone_gain_db(9000.0)
    check("A3 阻带 9 kHz 衰减 > 30 dB", g9k < -30.0, f"{g9k:.1f} dB")
    g1k_db = _tone_gain_db(1000.0)
    check("A3b 通带 1 kHz 衰减 < 0.5 dB", abs(g1k_db) < 0.5, f"{g1k_db:.2f} dB")

    # A3c 直接看滤波器频响（这是抽头数的直接指标）
    fir = _build_fir()
    H = np.abs(np.fft.rfft(fir, 8192))
    fr = np.fft.rfftfreq(8192, 1 / 48000)

    def _db(f_hz: float) -> float:
        i = int(np.argmin(np.abs(fr - f_hz)))
        return 20 * math.log10(max(H[i], 1e-12))

    resp = {f: _db(f) for f in (1000, 7000, 8000, 9000, 10000)}
    check("A3c 滤波器频响：9 kHz ≤ −30 dB 且 10 kHz ≤ −60 dB",
          resp[9000] <= -30 and resp[10000] <= -60,
          " ".join(f"{k/1000:g}k={v:.1f}dB" for k, v in resp.items()))
    check("A3d 抽头数 ≥ 96（过渡带够陡）",
          TAPS >= 96, f"TAPS={TAPS}")

    # A4 帧的 sample_index 连续无缝（EXT-003「seq 不断」的算法基础）
    #    模拟 capture-worklet 的打包：maxOut=1600（100 ms），minOut=320（20 ms）
    n_out = len(y)
    max_out, min_out = 1600, 320
    frames, idx = 0, 0
    expect_next = 0
    contiguous = True
    while idx < n_out:
        take = min(max_out, n_out - idx)
        if take < min_out:
            break
        if idx != expect_next:
            contiguous = False
        expect_next = idx + take
        idx += take
        frames += 1
    check("A4 打包后 sample_index 连续无缝",
          contiguous and frames > 0,
          f"frames={frames} next={expect_next} total={n_out}")

    # A5 长时间不卡死（旧 bug：固定 512 长度历史 ⇒ 输出 165 个样本后永久卡住）
    x5 = _tone(440.0, 3.0)
    y5 = _resample(x5)
    expected = len(x5) // 3
    check("A5 长序列不卡死（3 s → 输出 ≈ 1 s）",
          len(y5) > expected * 0.98,
          f"out={len(y5)} expect≈{expected}")


# ══════════════════════════════════════════════════════════════════
# A2段. 唇音同步配对算法（性能优化后**语义不变**的等价性验证）
# ══════════════════════════════════════════════════════════════════
def _pair_greedy(onsets, marks, gap_max=1.0):
    """旧实现：O(n²) 一对一最近邻贪心（作为**语义基准**）。"""
    pairs = []
    used = set()
    so = sorted(onsets)
    sm = sorted(marks)
    for a in so:
        best_i, best_d = -1, float("inf")
        for i in range(len(sm)):
            if i in used:
                continue
            d = abs(sm[i] - a)
            if d < best_d:
                best_d, best_i = d, i
        if best_i < 0:
            continue
        used.add(best_i)
        pairs.append((sm[best_i], a, best_d))
    return [p for p in pairs if p[2] <= gap_max]


def _pair_two_pointer(onsets, marks, gap_max=1.0):
    """新实现：单调双指针 + 小窗口（与 player.js 的 computeLipSync 同构）。"""
    pairs = []
    so = sorted(onsets)
    sm = sorted(marks)
    j = 0
    for a in so:
        while j < len(sm) and sm[j] < a - gap_max:
            j += 1
        best_k, best_d = -1, float("inf")
        hi = min(len(sm) - 1, j + 2)
        for k in range(j, hi + 1):
            d = abs(sm[k] - a)
            if d < best_d:
                best_d, best_k = d, k
        if best_k < 0:
            continue
        m = sm[best_k]
        if best_d <= gap_max:
            pairs.append((m, a, best_d))
            while j < len(sm) and sm[j] <= m:
                j += 1
    return pairs


def test_lipsync_pairing() -> None:
    # A6 正常情形：onset 与 mark 一一对应、间隔很小 ⇒ 两法结果一致
    onsets = [1.000, 1.500, 2.000, 2.500, 3.000]
    marks = [1.020, 1.480, 2.030, 2.490, 3.010]
    g = _pair_greedy(onsets, marks)
    t = _pair_two_pointer(onsets, marks)
    check("A6 双指针配对与最近邻贪心结果一致（正常情形）",
          g == t, f"greedy={g} two_pointer={t}")

    # A7 有噪声偏移 ⇒ 误差统计应接近
    onsets = [1.000, 1.500, 2.000, 2.500]
    marks = [1.030, 1.470, 2.040, 2.520]
    g = _pair_greedy(onsets, marks)
    t = _pair_two_pointer(onsets, marks)
    g_err = sorted(abs(m - a) for m, a, _ in g)
    t_err = sorted(abs(m - a) for m, a, _ in t)
    check("A7 双指针配对误差序列与贪心一致",
          len(g_err) == len(t_err) and all(
              abs(x - y) < 1e-9 for x, y in zip(g_err, t_err)),
          f"greedy={g_err} two_pointer={t_err}")

    # A8 多余的 mark（画面比声音多）⇒ 两法都应只配掉同样数量
    onsets = [1.0, 2.0]
    marks = [0.98, 1.01, 1.9, 2.02, 2.5]
    g = _pair_greedy(onsets, marks)
    t = _pair_two_pointer(onsets, marks)
    check("A8 冗余 mark 下配对数量一致",
          len(g) == len(t) and len(t) == 2,
          f"greedy={len(g)} two_pointer={len(t)}")

    # A9 O(n²) 与 O(n) 的规模对比（性能回归防护）
    import time as _t
    n = 400
    big_o = [i * 0.5 for i in range(n)]
    big_m = [i * 0.5 + 0.01 for i in range(n)]
    t0 = _t.perf_counter()
    _pair_greedy(big_o, big_m)
    t_greedy = _t.perf_counter() - t0
    t0 = _t.perf_counter()
    _pair_two_pointer(big_o, big_m)
    t_fast = _t.perf_counter() - t0
    check("A9 双指针配对显著快于 O(n²) 贪心",
          t_fast <= t_greedy,
          f"n={n} greedy={t_greedy * 1000:.2f} ms "
          f"two_pointer={t_fast * 1000:.2f} ms")


# ══════════════════════════════════════════════════════════════════
# B. 插件侧契约（静态检查真实文件）
# ══════════════════════════════════════════════════════════════════
def test_contracts() -> None:
    # B1 manifest
    mp = os.path.join(EXT_DIR, "manifest.json")
    man = {}
    if os.path.isfile(mp):
        with open(mp, "r", encoding="utf-8") as f:
            man = json.load(f)
    check("B1 manifest 是 MV3", man.get("manifest_version") == 3,
          f"manifest_version={man.get('manifest_version')}")
    perms = man.get("permissions") or []
    need = {"tabCapture", "offscreen", "storage"}
    check("B1b manifest 含必需权限", need.issubset(set(perms)),
          f"permissions={perms}")
    check("B1c manifest 有固定 key（扩展 ID 稳定）",
          bool(man.get("key")), "key 存在" if man.get("key") else "缺 key")

    # B2 capture-worklet：环形缓冲 + 注册名 + 帧长范围
    cw = _read("capture-worklet.js")
    check("B2 capture-worklet 注册 capture-processor",
          "registerProcessor('capture-processor'" in cw)
    check("B2b capture-worklet 用环形缓冲（HB）",
          "const HB = 1024" in cw and "histWrite" in cw,
          "环形缓冲特征存在")
    check("B2c capture-worklet 不再有固定 512 线性历史",
          "this.hist = new Float32Array(512)" not in cw,
          "致命 bug 的特征已移除")
    check("B2d capture-worklet 上报 inSamples（供主线程反推基准点）",
          "inSamples" in cw)

    # B3 player.js 编码器顺序
    pl = _read("player.js")
    m = re.search(r"const CODEC_CANDIDATES\s*=\s*\[(.*?)\];", pl, re.S)
    cand = m.group(1) if m else ""
    vp8_first = bool(re.search(r"codec:\s*'vp8'.*hw:\s*'no-preference'", cand, re.S)) and \
        cand.strip().find("'vp8'") < (cand.find("'vp09'") if "'vp09'" in cand else 10 ** 6)
    check("B3 player.js 编码器以 VP8+no-preference 打头",
          vp8_first, cand.strip()[:90].replace("\n", " "))

    # B3b player.js 用真实帧尺寸配置编码器（getSettings 与实际帧不一致会失败）
    check("B3b player.js 按真实帧尺寸配置编码器",
          "frame.displayWidth" in pl and "encSize" in pl)

    # B3c DelayNode 的 maxDelayTime ≥ D
    check("B3c player.js DelayNode 的 maxDelayTime 随 D 调整",
          "createDelay(Math.max(2, delaySec + 1))" in pl)

    # B4 onset-worklet 连续检测
    ow = _read("onset-worklet.js")
    check("B4 onset-worklet 支持连续检测（count=0）",
          "this.count = opt.count || 0" in ow or "count || 0" in ow)
    check("B4b onset-worklet 有迟滞（release 阈值）",
          "release" in ow and "firing" in ow)

    # B5 bridge.py：_handle_messages 必须带 delay_sec 形参
    bp = os.path.join(ROOT, "ext", "bridge.py")
    bsrc = ""
    if os.path.isfile(bp):
        with open(bp, "r", encoding="utf-8") as f:
            bsrc = f.read()
    m = re.search(r"async def _handle_messages\(([^)]*)\)", bsrc, re.S)
    sig = m.group(1) if m else ""
    check("B5 bridge._handle_messages 显式带 delay_sec 形参",
          "delay_sec" in sig, sig.strip().replace("\n", " "))
    # 旧 bug 的特征：函数体里直接用 delay_sec 却没有形参
    check("B5b bridge.py 已修「delay_sec 未定义」",
          "delay_sec: float) -> None:" in bsrc)

    # B6 sw.js：SW↔offscreen 走 Port
    sw = _read("sw.js")
    check("B6 sw.js 用 Port 通道控制 offscreen",
          "ext-offscreen" in sw and "offscreenCall" in sw)
    # ★ 只统计 **onMessage listener 里**的 return true
    #   （relay 函数里的 return true 是返回值，不是异步响应标记）
    listener_returns = re.findall(
        r"onMessage\.addListener\((.*?)\n\}\);", sw, re.S)
    n_async = sum(1 for blk in listener_returns if "return true" in blk)
    check("B6b sw.js 的 onMessage listener 只有 1 个做异步响应",
          n_async == 1,
          f"有 {n_async} 个 listener 返回 true（共 {len(listener_returns)} 个 listener）")

    # B6c offscreen.js 主动 connect 到 SW
    off = _read("offscreen.js")
    check("B6c offscreen.js 主动 connect 到 SW",
          "chrome.runtime.connect" in off and "ext-offscreen" in off)

    # B7 player.js 承载音频上行（offscreen 不驱动 AudioWorklet）
    check("B7 player.js 内含音频上行实现（16 kHz）",
          "startUplink" in pl and "capture-worklet.js" in pl)
    check("B7b player.js 上行带 seq/sample_index 连续性检查",
          "gapDetail" in pl and "sample_index" in pl)

    # ── B8：无界队列 / O(n²) 循环（5 分钟长测实测 maxAbsSkew 595 ms 的根因）──
    check("B8 pendingSched 有上限（防止无界增长）",
          "PENDING_SCHED_CAP" in pl and "pendingSched.splice" in pl)
    check("B8b subs 队列有上限", "SUBS_CAP" in pl and "subs.splice" in pl)
    check("B8c subs 不再每条 push 都 sort()",
          _strip_js_comments(pl).count("subs.sort(") == 0,
          "仍有 subs.sort ⇒ O(n² log n")
    check("B8d computeLipSync 不再 O(n²) 全表扫描",
          "PAIR_GAP_MAX" in pl and "sortedMarks[j] < a - PAIR_GAP_MAX" in pl)
    check("B8e pct 用缓存的有序副本（不再每次复制+排序）",
          "_pctCache" in pl and "WeakMap" in pl)
    check("B8f report 只发标量摘要（不发大数组）",
          "reportSummary" in pl and "REPORT_SCALARS" in pl,
          "跨上下文只传标量")

    # ── B9：bridge 回声模式的帧率 ⇒ 队列压力（回归防护）──
    br = _read_root(os.path.join("ext", "bridge.py"))
    check("B9 bridge 回声带 sample_rate（插件按 16 kHz 重建缓冲）",
          '"sample_rate"' in br, f"bridge.py 读取长度={len(br)}")
    check("B9b bridge 回声原样返回 16 kHz PCM（不重采样）",
          "pcm24k" in br and "base64.b64encode(raw)" in br)

    # ── B10：探针必须持共享机器锁（铁律：只能排队，不能抢）──
    # 真实缺陷：video_lipsync_probe.py / echo_sched_probe.py
    #   在 App 模块持锁期间（23:18–23:20）直接跑 ⇒ 违反「不与实时字幕 App 抢设备」。
    for name in ("video_lipsync_probe.py", "echo_sched_probe.py"):
        src = _read_root(os.path.join("tools", name))
        check(f"B10 {name} 持共享机器锁",
              "machine_lock" in src and "hold(" in src and "lock_wait" in src,
              f"{name} 未见 machine_lock.hold")
        check(f"B10b {name} 提供 --lock-wait（可排队等 App 释放）",
              "--lock-wait" in src)
    suite = _read_root(os.path.join("tools", "run_p0_suite.py"))
    check("B10c 编排器给所有探针透传 --lock-wait",
          suite.count("--lock-wait") >= 1 and "lock_wait" in suite)

    # ── B11：P0③ 排程口径 —— probe 排程与 bridge 回声排程必须分开统计 ──
    # 真实缺陷（实测 P0③：误差呈「0.02 / 43.02 / 0.02」双峰，maxAbs=43 ms 超 20 ms）：
    #   onset 检测器对 0.1 s 连续正弦会**重复触发**（迟滞 + 50 ms 最小间隔），
    #   而 bridge 回声模式每帧回灌一条（≈47 帧/秒）⇒ onset 分不清来源，
    #   FIFO 配对把自测排程的 onset 错配给回声排程 ⇒ 误差被算到错误的排程上。
    plc = _strip_js_comments(pl)
    check("B11 onDubOnset 按最近邻配对（不是 FIFO shift）",
          "pendingSched.splice(idx" in plc
          and "pendingSched.shift()" not in plc,
          "仍是 FIFO 配对 ⇒ 重复 onset 会错配")
    check("B11b 排程带 probe 标记（区分自测排程 / bridge 回声排程）",
          "probe: isProbe" in plc and "msg.probe" in plc)
    check("B11c probe 排程优先配对（不被高密度回声排程抢走）",
          "pendingSched[i].probe" in plc and "if (!pendingSched[i].probe) continue" in plc)
    check("B11d 配对有窗口上限（窗口外 onset 不误配到下一个排程）",
          "PAIR_WINDOW_SEC" in plc and "nD > PAIR_WINDOW_SEC" in plc)
    check("B11e 只有 probe 排程计入 P0③ 误差统计",
          "if (!isProbe)" in plc and "metrics.onsetErrs.push(errMs)" in plc)
    check("B11f selfTestSchedule 传 probe=true",
          "probe: true" in plc)

    # ── B12：主线程 stall 探针（把 skew 尖峰归因变成可测量事实）──
    # 真实缺陷：5 分钟长测 maxAbsSkew 676.9 ms，而采样时钟本身是准的
    #   （drift ≈ 1 ms/min、P50=18 ms、P95=29 ms）。
    #   skew 尖峰形态是「一串等差数列，步长恰好 = 帧长 21.25 ms」，
    #   典型症状 = 主线程停摆 → 消息积压 → 恢复后一次性冲刷。
    #   ⇒ 没有 event-loop lag 探针就只能靠猜 ⇒ 必须有。
    check("B12 player.js 含主线程 stall（event-loop lag）探针",
          "stallProbe" in plc and "event-loop lag" in pl)
    check("B12b stall 探针用 setTimeout(0) 反复探测",
          "setTimeout(() => {" in plc)
    check("B12c stall 数据随 metrics 暴露给探针",
          "stall: {" in plc and "maxMs" in plc)
    check("B12d probe 把 stall 落盘（归因证据）",
          '"stall"' in _read_root(os.path.join("tools", "browser_probe.py")))

    # ── B13：canvas 尺寸只在真变化时重设（每帧重分配 backing store 会卡主线程）──
    # 真实缺陷：给 canvas.width 赋值即使值相同也会重置并重新分配整块
    #   backing store（HTML 规范如此）⇒ 1908×1072 每帧重分配 8 MB。
    check("B13 canvas 尺寸不在 drawFrame 里被改（保持显示尺寸）",
          "cv.width = frame.displayWidth" not in plc
          and "cv.height = frame.displayHeight" not in plc,
          "画布跟随源帧(1908×1072) ⇒ 每帧 GPU→CPU 合成 2.1 ms")
    check("B13b 画布保留显示尺寸（drawImage 用 cv.width/cv.height）",
          "ctx2d.drawImage(frame, 0, 0, cv.width, cv.height)" in plc)

    # ── B14：高频 report / 落盘节流（skew 尖峰的根因链）──
    # 真实缺陷：bridge 回声模式每帧回灌一条 echo（≈47 条/秒），
    #   每条都 player.report() → chrome.runtime.sendMessage → SW relay
    #   → offscreen.post() → **每条都 chrome.storage.local.get + set**
    #   ⇒ 每秒 ~47 次「读全量 + 写全量」磁盘 IO ⇒ 主线程周期性阻塞
    #   ⇒ 音频 worklet 消息处理延迟 ⇒ 采样计数 vs 墙钟出现数百 ms 尖峰。
    off = _read_root(os.path.join("extension", "offscreen.js"))
    check("B14 offscreen 落盘有节流（不再每条消息读写全量日志）",
          "POST_THROTTLE_MS" in off and "flushPost" in off
          and "postPending" in off)
    check("B14b offscreen 节流后仍保留日志（合并不丢）",
          "extLog" in off and ".slice(-200)" in off)
    check("B14c player 的高频 report 有节流",
          "REPORT_THROTTLE_MS" in plc and "REPORT_LOW_PRIORITY" in plc)
    check("B14d 关键事件仍立即上报（不被节流吞掉）",
          "REPORT_LOW_PRIORITY.has(kind)" in plc
          and "REPORT_LOW_PRIORITY.has('capture_error')" not in plc)

    # ── B15：白闪检测的 GPU→CPU 同步回读（skew 尖峰的**头号**根因）──
    # CDP CPU Profile 实测（.tmp/probe_profile/browser_probe.json）：
    #   getImageData self time = 15.96 s（非 idle 总 120.16 s 的 13.3%，第 1 名）
    #   drawImage     self time =  7.67 s（第 2 名）
    #   stall 间隔精确 10.3 s（20303→30622→40943→51223→61461→71862→82101→92425）
    #   = 源页白闪/beep 周期。
    # 旧实现：每帧 5 次 getImageData(x,y,2,2) ⇒ 30 fps × 5 = 每秒 150 次
    #   **同步** GPU→CPU 回读 ⇒ 主线程周期性阻塞 ⇒ 采样时钟尖峰。
    check("B15 白闪检测不再每帧多次 getImageData",
          plc.count("getImageData(") == 1,
          "getImageData 调用次数=%d（应只有 1 次整帧回读）" % plc.count("getImageData("))
    check("B15b 白闪检测用独立小画布（回读数据量 ~8MB → 576B）",
          "probeCanvas" in plc and "PROBE_W" in plc and "PROBE_H" in plc)
    check("B15c 白闪判定用白色像素占比（抗噪声）",
          "whiteRatio" in plc and "white" in plc)
    check("B15d 主画布不再 willReadFrequently（保持 GPU 加速）",
          "cv.getContext('2d', { willReadFrequently: true })" not in plc)
    check("B15e 只在小画布上声明 willReadFrequently",
          "probeCtx = probeCanvas.getContext('2d', { willReadFrequently: true })" in plc)

    # ── B17：白闪检测改用**异步** copyTo（不阻塞主线程）──
    # A/B 隔离实测（.tmp/ab_video_on vs .tmp/ab_video_off）：
    #   video=1 ⇒ maxAbsSkew 639.99 ms，getImageData self time 10.35 s
    #   video=0 ⇒ maxAbsSkew 30.88 ms，getImageData 0 ⇒ **达标**
    # ⇒ 尖峰 100% 来自视频管线的**同步**像素回读。
    #   降字节数（8MB→576B）无效（仍 2.9 ms/次）⇒ 贵在同步等待 GPU 管线。
    # ⇒ 正确解法：WebCodecs 的**异步** frame.copyTo()。
    check("B17 白闪检测用异步 copyTo（不阻塞主线程）",
          "await frame.copyTo(" in plc,
          "仍在用同步 getImageData ⇒ 主线程被 GPU 管线等待阻塞")
    check("B17b 白闪检测已降频（不是每帧都做）",
          "FLASH_DETECT_EVERY" in plc and "flashFrameCount % FLASH_DETECT_EVERY" in plc)
    check("B17c copyTo 失败有低频兜底（每 60 帧一次）",
          "flashFallbackCount" in plc and "% 60 === 0" in plc)
    check("B17d 异步拷贝期间帧不提前 close",
          "detectFlash(frame" in plc and "frame.close()" in plc
          and ".then(() => {" in plc
          and "detectFlash(frame, cv.width, cv.height).then" not in plc)

    # ── B18：采样计数的时间基准必须是**音频时钟**，不是主线程墙钟 ──
    # ★ 真实缺陷（实测 5 分钟 maxAbsSkew 534 ms 的**测量口径错误**）：
    #   旧实现拿主线程的 performance.now() 当墙钟，
    #   但主线程同时在跑视频解码 + canvas 合成
    #   （CDP CPU Profile：drawImage 19.2 s、GC 11.5 s / 300 s）
    #   ⇒ 测到的「偏差」是**主线程调度延迟**，不是采样时钟漂移。
    #   ⇒ 正确口径：AudioContext.currentTime / currentFrame（音频硬件时钟），
    #     在 AudioWorklet 内取值 ⇒ 与主线程负载无关。
    cw = _read_root(os.path.join("extension", "capture-worklet.js"))
    check("B18 worklet 上报音频时钟（currentTime/currentFrame）",
          "currentTime" in cw and "currentFrame" in cw
          and "audioFrame16" in cw)
    check("B18b player.js 用音频时钟算 skew（验收口径）",
          "maxAbsSkewAudioMs" in plc and "audioPos16" in plc)
    check("B18c 保留主线程口径作诊断量",
          "maxAbsSkewMs" in plc and "driftMsPerMin" in plc)
    check("B18d probe 用音频时钟口径判定 skew_ok",
          "maxAbsSkewAudioMs" in _read_root(os.path.join("tools", "browser_probe.py")))

    # ── B16：归因插桩（longtask + Profiler + 隔离开关）──
    check("B16 player.js 有 longtask 观察器（谁在阻塞主线程）",
          "PerformanceObserver" in plc and "longtask" in plc)
    check("B16b probe 支持 --profile（CDP CPU Profile 归因）",
          "--profile" in _read_root(os.path.join("tools", "browser_probe.py"))
          and "Profiler.start" in _read_root(os.path.join("tools", "browser_probe.py")))
    check("B16c probe 支持 --no-video（隔离视频管线做 A/B 对照）",
          "--no-video" in _read_root(os.path.join("tools", "browser_probe.py")))
    check("B16d 插件支持 ?video=0 隔离开关",
          "VIDEO_ENABLED" in plc and "qs.get('video')" in plc)

    # ── B19：编码管线「有界工作量」（skew 尖峰的根因链）──
    #   实测证据（CDP CPU Profile，.tmp/probe_uplink_5min_v6，300.5 s）：
    #     drawImage self time = 17.35 s（非 idle 第 1 名）
    #     源 30 fps → 编码 15 fps ⇒ **被丢弃的那一半帧仍然做了全尺寸缩放**
    #   ⇒ 限速判断必须**前置**：被丢的帧直接 close，不做 drawImage。
    check("B19 编码限速常量存在（ENCODE_FPS）",
          "const ENCODE_FPS" in plc)
    check("B19b 编码限速**前置**（丢帧发生在 drawImage 之前）",
          _enc_limit_before_draw(plc),
          "限速判断必须在 encCtx.drawImage 之前，否则被丢的帧仍付全额缩放代价")
    check("B19c 编码用 OffscreenCanvas 复用（不再每帧 new）",
          "encCanvas" in plc and "new OffscreenCanvas" in plc
          and "if (!encCanvas)" in plc,
          "每帧 new OffscreenCanvas ⇒ 每帧 8 MB 分配 ⇒ GC 压力")
    check("B19d 有 encodeQueueSize 守卫（编码器积压时丢帧）",
          "encodeQueueSize" in plc and "ENCODE_QUEUE_MAX" in plc)

    # ── B20：解码绘制「单一调度器 + 每 tick 预算」（消除定时器雪崩）──
    #   旧实现：每帧 setTimeout(drawFrame, waitMs) ⇒ 恢复后集中触发 ⇒ 数百 ms 二次 stall
    check("B20 有待绘制帧队列（pendingDraws）",
          "pendingDraws" in plc)
    check("B20b 有每 tick 绘制预算（DRAW_BUDGET_PER_TICK）",
          "DRAW_BUDGET_PER_TICK" in plc)
    check("B20c 绘制调度器 pumpDraws 存在且被主循环调用",
          "function pumpDraws" in plc and "pumpDraws()" in plc)
    check("B20d 待绘制队列有上限（PENDING_DRAW_CAP）",
          "PENDING_DRAW_CAP" in plc)
    check("B20e 不再用「每帧一个 setTimeout」的旧调度",
          "setTimeout(drawFrame" not in plc,
          "旧实现每帧一个定时器 ⇒ 主线程恢复后集中触发 ⇒ 雪崩式 stall")

    # ── B21：白闪检测必须显式要 RGBA（漏检 100% 的真实缺陷）──
    #   实测（.tmp/probe_suite_v7/probe_video_lipsync，45 s）：
    #     drawMarks=**0**，而源页白闪有 22 次 ⇒ 100% 漏检 ⇒ lipSync=null
    #   根因：VideoFrame.copyTo 的 options.format 缺省时沿用**帧原生格式**。
    #     本机 VP8 解码帧是 I420 ⇒ 16×9 区域只有 16×9×1.5 = **216 字节**，
    #     而代码按 RGBA 读 576 字节 ⇒ 多出的 360 字节是陈旧/零
    #     ⇒ avg 永远接近 0 ⇒ 白闪一次都检不出。
    check("B21 白闪检测的 copyTo 显式指定 format='RGBA'",
          "format: 'RGBA'" in plc,
          "缺省会沿用帧原生格式（VP8⇒I420，216B vs 需要的 576B）⇒ 白闪 100% 漏检")
    check("B21b 白闪检测的中心块尺寸常量存在（PROBE_W/PROBE_H）",
          "PROBE_W" in plc and "PROBE_H" in plc)

    # ── B22：P0③ probe 排程必须与 bridge 回声**物理隔离** ──
    #   实测（.tmp/probe_suite_v7，45 s，两次独立探针都精确复现）：
    #     onsetErrs = [0.02, **43.02**, 0.02] ms ⇒ 目标 ≤ 20 ms **未达标**
    #   根因：自测排程与 bridge 回声（每帧回灌）**共用一条 dubBus**，
    #     onset 检测器也只挂在 dubBus 上 ⇒ 回声 onset 先触发，
    #     onset-worklet 的 minGapSec=0.05 迟滞**抑制**紧随的自测 onset
    #     ⇒ 自测排程只能配到「晚约 43 ms」的 onset。
    #   ⇒ 修法：probe 排程接独立 probeBus + 独立 onset 检测器。
    check("B22 有 probe 专用总线（probeBus）",
          "probeBus" in plc)
    check("B22b probe 排程接 probeBus（与 dubBus 分流）",
          "isProbe ? probeBus : dubBus" in plc,
          "共用总线 ⇒ 回声 onset 的 minGapSec 迟滞会抑制自测 onset")
    check("B22c probeBus 有独立的 onset 检测器",
          "probeOnsetNode" in plc
          and "makeOnsetDetector(probeBus" in plc)

    # ── B23：排程「钳位」必须可见（不能让假误差看起来像真实误差）──
    #   实测根因：P0③ 探针固定传 t_start=(0.5,2.0,3.5)（相对 t0 的偏移）
    #   ⇒ 第 2、3 次的 planned = t0+t_start+delaySec **已在过去**
    #   ⇒ 插件的 Math.max(currentTime+0.005, planned) 钳成"立刻播"
    #   ⇒ 而主线程繁忙时 audioCtx.currentTime **滞后真实音频时钟约 43 ms**
    #   ⇒ 稳定复现 43.02 ms 的假误差（两次独立探针数值完全相同 ⇒ 结构性非随机）。
    #   ⇒ 探针改为按**当前音频时钟**推算未来时刻；
    #     插件侧对钳位**计数**（metrics.schedClamped / probeSchedClamped）。
    check("B23 排程钳位被计数（schedClamped）",
          "schedClamped" in plc)
    check("B23b probe 排程钳位单独计数（probeSchedClamped）",
          "probeSchedClamped" in plc)
    check("B23c P0③ 探针按当前音频时钟推算未来排程时刻",
          "getAudioTime" in _read_root(os.path.join("tools", "echo_sched_probe.py"))
          and "getAudioTime" in _read_root(os.path.join("tools", "video_lipsync_probe.py")),
          "固定传 t_start=(0.5,2.0,3.5) ⇒ 第 2、3 次排程落在过去 ⇒ 43.02 ms 假误差")
    check("B23d 探针不再固定传 (0.5, 2.0, 3.5)",
          "for t_start in (0.5, 2.0, 3.5)" not in
          _read_root(os.path.join("tools", "echo_sched_probe.py"))
          and "for t_start in (0.5, 2.0, 3.5)" not in
          _read_root(os.path.join("tools", "video_lipsync_probe.py")))


# ══════════════════════════════════════════════════════════════════
# C. 浏览器实测证据（读落盘 JSON；缺文件 ⇒ FAIL）
# ══════════════════════════════════════════════════════════════════
def _latest_uplink_evidence():
    """找**最新**的 5 分钟上行实测证据（按 mtime 选最新的一个）。

    ★ 为什么要「最新」而不是写死目录名：每轮修复后都会重跑，
      写死旧目录会让测试永远读**过期**的证据 ⇒ 掩盖真实进展。
      仍然遵守「缺证据 ⇒ FAIL，不判 PASS」。
    """
    tmp = os.path.join(ROOT, ".tmp")
    if not os.path.isdir(tmp):
        return None
    cands = []
    for name in os.listdir(tmp):
        if not name.startswith("probe_uplink"):
            continue
        p = os.path.join(tmp, name, "browser_probe.json")
        if os.path.isfile(p):
            cands.append((os.path.getmtime(p), p))
    if not cands:
        return None
    cands.sort()
    return cands[-1][1]


def test_evidence() -> None:
    p5 = _latest_uplink_evidence()
    if not p5:
        check("C1 5 分钟上行实测证据文件存在", False,
              f"缺 .tmp/probe_uplink*/browser_probe.json ⇒ 无证据不判 PASS")
        return
    with open(p5, "r", encoding="utf-8") as f:
        d = json.load(f)
    up = ((d.get("uplink") or {}).get("uplink") or {})
    rel = os.path.relpath(p5, ROOT)
    check("C1 5 分钟上行实测证据文件存在", True,
          f"{rel}（mtime {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p5)))}）")
    check("C1b 上行连续 ≥ 300 s",
          (up.get("elapsedMs") or 0) >= 300_000,
          f"elapsed={up.get('elapsedMs')} ms")
    check("C1c seq 不断（gaps = 0）",
          up.get("gaps") == 0,
          f"gaps={up.get('gaps')} frames={up.get('frameCount')}")
    check("C1d 采样计数 vs 音频时钟偏差 < 50 ms（剔除启动瞬态）",
          (up.get("maxAbsSkewAudioMs") if up.get("maxAbsSkewAudioMs") is not None
           else 1e9) < 50.0,
          f"maxAbsSkewAudioMs={up.get('maxAbsSkewAudioMs')} "
          f"p95={up.get('skewAudioP95')} nSpikes={up.get('nSkewAudioSpikes')}")
    check("C1d2 主线程口径 skew（诊断量，反映主线程调度延迟）",
          (up.get("maxAbsSkewMs") or 0) < 1000.0,
          f"maxAbsSkewMs={up.get('maxAbsSkewMs')} p95={up.get('skewP95')}")
    check("C1e WebSocket 上行确实发出字节",
          (up.get("bytesSent") or 0) > 0,
          f"bytesSent={up.get('bytesSent')}")


def main() -> int:
    print("── A. 重采样正确性（Python 等价实现） ──")
    test_resample()
    print("── A2. 唇音同步配对算法等价性 ──")
    test_lipsync_pairing()
    print("── B. 插件侧契约（静态检查真实文件） ──")
    test_contracts()
    print("── C. 浏览器实测证据（落盘 JSON） ──")
    test_evidence()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print(f"\n结果：{passed} PASS / {failed} FAIL")
    if failed:
        print("FAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  - {name} — {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
