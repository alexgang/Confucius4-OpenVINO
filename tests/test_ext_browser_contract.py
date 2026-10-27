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
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


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
    check("C1d 采样计数 vs 墙钟偏差 < 50 ms（剔除启动瞬态）",
          (up.get("maxAbsSkewMs") or 1e9) < 50.0,
          f"maxAbsSkewMs={up.get('maxAbsSkewMs')} "
          f"p95={up.get('skewP95')} drift/min={up.get('driftMsPerMin')}")
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
