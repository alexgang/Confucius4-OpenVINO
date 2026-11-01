# -*- coding: utf-8 -*-
"""ext032_deliver.py — ★★ EXT-032③④：把逐段对比结果**打包成 reviewer 可拉回的交付物**

★ 背景（EXT-032 [BLOCKING] 2026-11-01 20:30）：
  reviewer 要求 EXT-028 必须交**实测**：
    ② 每段三份音频（① TTS 原始 / ② 桥接下发 PCM / ③ player 录音）逐段对比表
    ③ 静音成因 + 修复后的数据（开头静音 / 最长静音 / 首段配音到达 / sync_err p50·p95）
    ④ `C:\\Users\\Trekker-PTL\\shared\\ext_listen\\ext032_<时间>\\` 放
       player 录音 + README（每段起止时间与对应译文）+ 对比表

★ 本脚本做的事（**纯离线分析，不跑推理、不占 GPU/NPU、不创建共享锁**）：
  1. 复用 `ext032_audio_compare.py`（上一轮已写好）算出逐段对比；
  2. 再读同一轮的 `margin.json` / `metrics.json` / `bridge.log`，
     把**静音成因**拆成可核对的加法式分解（不是一句推测）；
  3. 把交付物写到 `shared/ext_listen/ext032_<时间>/`：
       dub_player.webm（player 端录音原样拷贝）
       ext032_compare.md / .json（逐段对比表）
       ext032_deliver.json（本脚本算出的全部数字）
       README.md（每段起止时间 + 对应译文 + 静音画像 + 口径说明）

★ 用法：
    python tests/smoke/ext032_deliver.py <e2e轮次目录> [--listen-dir 输出目录]
    例：python tests/smoke/ext032_deliver.py \
          .tmp/ext028_029_e2e/20261101_155037_13840/A_off

★ 纯函数（`parse_bridge_segments` / `sync_err_stats` / `analyze_silence_cause` /
  `render_readme`）**不依赖浏览器**，可离线自测 ⇒ `tests/test_ext032_deliver.py`。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import time

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for _p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: 共享交付目录（EXT-032④ 指定的路径）
LISTEN_ROOT = r"C:\Users\Trekker-PTL\shared\ext_listen"

#: 段级日志行：[bridge 15:51:40] 段 seg_x | t_start=0.000 t_end=3.150 | ASR='—' | MT='—' | TTS=0.00s | 下发到=player,uplink
_SEG_RE = re.compile(
    r"\[bridge (?P<hh>\d{2}):(?P<mm>\d{2}):(?P<ss>\d{2})\]\s*段\s+(?P<seg_id>\S+)\s*\|\s*"
    r"t_start=(?P<t_start>-?[\d.]+)\s+t_end=(?P<t_end>-?[\d.]+)\s*\|\s*"
    r"ASR=(?P<asr>'(?:[^']*)'|\"(?:[^\"]*)\")\s*\|\s*"
    r"MT=(?P<mt>'(?:[^']*)'|\"(?:[^\"]*)\")\s*\|\s*"
    r"TTS=(?P<tts>[\d.]+)s",
)

#: 上行 hello（= 会话 t0 的锚点）
_HELLO_RE = re.compile(r"\[bridge (?P<hh>\d{2}):(?P<mm>\d{2}):(?P<ss>\d{2})\].*hello")


def _unquote(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s


def _pct(sorted_vals, q: float):
    """百分位 —— **与 tools/p1_pipeline.py::_pct 完全同口径**（最近秩，不插值）。

    ★ 为什么不用 numpy 的线性插值：EXT-032③ 要的 sync_err p50/p95 必须能
      和 `tools/p1_pipeline.py` 的 `sync_err_ms` 块**直接对比**
      （那是 reviewer 已在看的口径）⇒ 两边必须同一种算法，
      否则会出现「同一批数据两个 p95」的不可比结论。
    """
    if not sorted_vals:
        return None
    k = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return float(sorted_vals[k])


# ── 纯函数 ①：段级日志 ──────────────────────────────────────────
def parse_bridge_segments(log_path: str):
    """解析 bridge.log ⇒ (段列表, 首个 uplink hello 的 HH:MM:SS)。

    段列表每项：{seg_id, t_start, t_end, asr, mt, tts_sec, has_text, at}
    `has_text` = ASR 是否给出了**非空**识别文本（'—' 表示这一窗没有语音）。
    """
    segs = []
    hello_at = None
    with io.open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if hello_at is None and _HELLO_RE.search(line) and "uplink" in line:
                hello_at = "%s:%s:%s" % (_HELLO_RE.search(line).group("hh"),
                                        _HELLO_RE.search(line).group("mm"),
                                        _HELLO_RE.search(line).group("ss"))
            m = _SEG_RE.search(line)
            if not m:
                continue
            asr = _unquote(m.group("asr"))
            mt = _unquote(m.group("mt"))
            segs.append({
                "seg_id": m.group("seg_id"),
                "t_start": float(m.group("t_start")),
                "t_end": float(m.group("t_end")),
                "asr": asr,
                "mt": mt,
                "tts_sec": float(m.group("tts")),
                "has_text": bool(asr) and asr not in ("—", "-", "…"),
                "at": "%s:%s:%s" % (m.group("hh"), m.group("mm"), m.group("ss")),
            })
    return segs, hello_at


# ── 纯函数 ②：sync_err ─────────────────────────────────────────
def sync_err_stats(per_segment):
    """按 tools/p1_pipeline.py 的口径算同步误差分布。

    同步误差 = max(0, TTS就绪时刻 − (t0 + t_start + D)) × 1000 ms
             = max(0, −deadline_margin_sec) × 1000
    ★ **只统计有 TTS 的段**（`has_tts=True`）才说明「配音没赶上」；
      没有 TTS 的段是「那一窗没有语音」，不是同步误差。
    """
    allv, ttsv = [], []
    for s in per_segment or []:
        dm = s.get("deadline_margin_sec")
        if dm is None:
            continue
        err = max(0.0, -float(dm)) * 1000.0
        allv.append(err)
        if s.get("has_tts"):
            ttsv.append(err)
    def _dist(v):
        v = sorted(v)
        return {
            "n": len(v),
            "p50": round(_pct(v, 0.50), 3) if v else None,
            "p95": round(_pct(v, 0.95), 3) if v else None,
            "max": round(v[-1], 3) if v else None,
            "mean": round(sum(v) / len(v), 3) if v else None,
            "n_over_12000ms": sum(1 for x in v if x > 12000.0),
        }
    return {"all_segments": _dist(allv), "tts_segments": _dist(ttsv),
            "definition": "max(0, TTS就绪时刻 − (t0 + t_start + D)) × 1000 ms（与 tools/p1_pipeline.py 同口径）"}


# ── 纯函数 ③：静音成因分解 ─────────────────────────────────────
def analyze_silence_cause(segs, player_stats, design_buffer_sec, source_windows=None):
    """把「开头静音」拆成**可核对的加法式分解**。

    player_stats: {"player_leading_silence_sec", "player_longest_silence_sec",
                   "player_total_silence_sec", "player_duration_sec"}
    design_buffer_sec: 插件的播放缓冲 D（EXT-009 约定的约 10 s）
    source_windows: 素材侧每窗 RMS（list of (t_start, rms_dbfs)）⇒ 用来说明
                     「素材本身是不是前面就有长静音」

    返回：分解 + 成因链（每条都带证据字段）。
    """
    spoken = [s for s in (segs or []) if s.get("has_text")]
    first = spoken[0] if spoken else None
    first_t = first["t_start"] if first else None
    # ★ 只数**首语音位置之前**的空窗（首语音之后的空窗与开口静音无关）
    empty = [s for s in (segs or [])
             if not s.get("has_text")
             and (first_t is None or s["t_start"] < first_t)]
    leading = player_stats.get("player_leading_silence_sec")
    D = float(design_buffer_sec or 0.0)

    explained = None
    residual = None
    if leading is not None and first_t is not None:
        explained = round(first_t + D, 3)
        residual = round(float(leading) - explained, 3)

    src_first_speech = None
    if source_windows:
        for t, db in source_windows:
            if db > -45.0:
                src_first_speech = t
                break

    chain = []
    chain.append({
        "cause": "播放缓冲 D（EXT-009 约定的设计缓冲）",
        "value_sec": D,
        "evidence": "metrics.json: delaySec / STATUS §17（EXT-009）",
    })
    if first_t is not None:
        chain.append({
            "cause": "上行时间轴上**第一窗有语音**的位置（此前各窗 ASR 为空 ⇒ 无配音可播）",
            "value_sec": first_t,
            "evidence": "bridge.log 段级日志：首段有文本 = %s（t_start=%.3f）；"
                        "**该位置之前** %d 窗 ASR='—'（无语音 ⇒ 无配音可播）"
                        % (first["seg_id"], first_t, len(empty)),
        })
    if explained is not None:
        chain.append({
            "cause": "⇒ 合计可解释的开口静音 = 首语音位置 + D",
            "value_sec": explained,
            "evidence": "%.3f + %.3f = %.3f s；实测开口静音 %.3f s；残差 %.3f s"
                        % (first_t, D, explained, float(leading), residual),
        })
    return {
        "player_leading_silence_sec": leading,
        "player_longest_silence_sec": player_stats.get("player_longest_silence_sec"),
        "player_total_silence_sec": player_stats.get("player_total_silence_sec"),
        "player_duration_sec": player_stats.get("player_duration_sec"),
        "design_buffer_sec": D,
        "first_spoken_t_start_sec": first_t,
        "first_spoken_seg_id": first["seg_id"] if first else None,
        "first_spoken_src": first["asr"] if first else None,
        "n_empty_windows_before_first_speech": len(empty),
        "explained_leading_silence_sec": explained,
        "residual_sec": residual,
        "source_first_speech_window_sec": src_first_speech,
        "source_windows_rms_dbfs": list(source_windows) if source_windows else None,
        "cause_chain": chain,
    }


# ── 纯函数 ④：README ───────────────────────────────────────────
def analyze_source_windows(wav_path: str, win_sec: float = 3.15):
    """素材 wav ⇒ [(t_start, rms_dbfs)]（每个上行窗的音量）。

    ★ 用途：**证明「ASR 空的那些窗，素材里其实是有语音的」**
      ⇒ 空窗不是素材的问题、也不是 ASR 的问题 ⇒ 只能是被抓流侧丢掉了。
    ★ 纯标准库（wave + array），不引入 numpy。
    """
    import array
    import math
    import wave
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        n = w.getnframes()
        raw = w.readframes(n)
    a = array.array("h")
    a.frombytes(raw[:len(raw) - (len(raw) % 2)])
    if nch > 1:
        a = a[::nch]
    win = max(1, int(win_sec * sr))
    out = []
    for i in range(0, len(a), win):
        ch = a[i:i + win]
        if not ch:
            break
        r = math.sqrt(sum(float(v) * v for v in ch) / len(ch)) / 32768.0
        db = 20 * math.log10(r) if r > 0 else -99.0
        out.append((round(i / float(sr), 3), round(db, 2)))
    return out


def render_readme(data: dict) -> str:
    """生成交付目录里的 README.md（每段起止时间 + 对应译文 + 静音画像）。"""
    s = data["summary"]
    c = data["silence"]
    sync = data["sync_err"]
    L = ["# EXT-032 交付：player 配音录音 + 逐段三份音频对比", ""]
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 生成时间 | %s |" % data["generated_at"])
    L.append("| 轮次目录 | `%s` |" % s["run_dir"])
    L.append("| player 录音 | `dub_player.webm`（%d B，%s s @ %d Hz） |"
             % (s["player_webm_bytes"], s["player_duration_sec"], s["player_sample_rate"]))
    L.append("| **抓流方式** | **%s**%s |"
             % (data["capture_mode"],
                "" if data.get("capture_mode_is_production")
                else "（★ **不是** tabCapture 生产路径 ⇒ 见下方「口径说明」）"))
    L.append("| 逐段对比表 | `ext032_compare.md`（机器可读：`ext032_compare.json`） |")
    L.append("| 全部数字 | `ext032_deliver.json` |")
    L.append("")
    L.append("## ★ 静音画像（EXT-032③）")
    L.append("")
    L.append("| 项 | 实测 |")
    L.append("|---|---|")
    L.append("| **录音开头静音**（到首段配音） | **%s s** |" % c["player_leading_silence_sec"])
    L.append("| **最长静音段** | **%s s** |" % c["player_longest_silence_sec"])
    L.append("| 总静音 | %s s |" % c["player_total_silence_sec"])
    L.append("| **首段配音到达**（上行时间轴） | t_start = **%s s**（段 %s） |"
             % (c["first_spoken_t_start_sec"], c["first_spoken_seg_id"]))
    L.append("| **sync_err p50 / p95** | **%s / %s ms**（%s 段口径：%s） |"
             % (sync["tts_segments"]["p50"], sync["tts_segments"]["p95"],
                sync["tts_segments"]["n"], "有 TTS 的段"))
    L.append("| 计划缓冲 D | %s s |" % c["design_buffer_sec"])
    L.append("")
    L.append("### 开口静音的成因分解（逐条带证据）")
    L.append("")
    for i, item in enumerate(c["cause_chain"], 1):
        L.append("%d. **%s** = **%s s**  \n   证据：%s"
                 % (i, item["cause"], item["value_sec"], item["evidence"]))
    L.append("")
    L.append("## ★ 逐段对照（每段起止时间 + 对应译文 + 三份音频）")
    L.append("")
    L.append("| 段 | 上行 t_start→t_end | 原文（ASR） | 译文（MT） | TTS 时长 | 桥接 PCM 时长 | 时长比(原始/变速校正) | 互相关峰 | SNR(dB) | player 落点(s) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for g in data["segments"]:
        if "dur_ratio_ws_over_tts" not in g:
            L.append("| %s | - | - | - | - | - | - | - | - | %s |"
                     % (g["seg_id"], g.get("error")))
            continue
        L.append("| %s | %.3f→%.3f | %s | %s | %.3f | %.3f | %.4f / **%.4f** | %.4f | %.1f | %s |"
                 % (g["seg_id"], g["t_start"], g["t_end"],
                    g.get("src") or "", g.get("tgt") or "",
                    g["d_tts_sec"], g["d_ws_sec"],
                    g["dur_ratio_ws_over_tts"], g["dur_ratio_speed_adjusted"],
                    g["xcorr_peak"], g["snr_db"], g.get("player_align_offset_sec")))
    L.append("")
    L.append("## 口径说明（reviewer 复核用）")
    L.append("")
    for line in data["notes"]:
        L.append("- %s" % line)
    L.append("")
    return "\n".join(L)


# ── 主流程 ──────────────────────────────────────────────────────
def build_delivery(run_dir: str, listen_dir: str = None, notes=None,
                   reuse_compare: bool = False, source_wav: str = None) -> dict:
    """分析一轮 e2e 产物 ⇒ 写交付目录 ⇒ 返回交付摘要。

    `reuse_compare=True` ⇒ 直接读轮次目录里已有的 `ext032_compare.json`
    （webm 解码要起浏览器、实测约 9 min ⇒ 重跑分析时复用，避免重复解码）。
    """
    import ext032_audio_compare as C

    run_dir = os.path.abspath(run_dir)
    cached = os.path.join(run_dir, "ext032_compare.json")
    if reuse_compare and os.path.isfile(cached):
        cmp_data = json.load(io.open(cached, encoding="utf-8"))
    else:
        cmp_data = C.compare_run(run_dir)
    s = cmp_data["summary"]

    margin = {}
    mp = os.path.join(run_dir, "margin.json")
    if os.path.isfile(mp):
        margin = json.load(io.open(mp, encoding="utf-8"))
    metrics = {}
    mtp = os.path.join(run_dir, "metrics.json")
    if os.path.isfile(mtp):
        metrics = json.load(io.open(mtp, encoding="utf-8"))

    segs, hello_at = ([], None)
    bp = os.path.join(run_dir, "bridge.log")
    if os.path.isfile(bp):
        segs, hello_at = parse_bridge_segments(bp)

    delay_sec = metrics.get("delaySec") or (metrics.get("link") or {}).get("delaySec") or 10.0
    sync = sync_err_stats(margin.get("per_segment"))
    player_stats = {
        "player_leading_silence_sec": s.get("player_leading_silence_sec"),
        "player_longest_silence_sec": s.get("player_longest_silence_sec"),
        "player_total_silence_sec": s.get("player_total_silence_sec"),
        "player_duration_sec": s.get("player_duration_sec"),
    }
    silence = analyze_silence_cause(segs, player_stats, delay_sec,
                                    source_windows=(
                                        analyze_source_windows(source_wav)
                                        if source_wav and os.path.isfile(source_wav)
                                        else None))
    if source_wav and os.path.isfile(source_wav):
        silence["source_wav"] = os.path.abspath(source_wav)
        silence["source_windows_rms_dbfs"] = silence.get("source_windows_rms_dbfs")
        sw = silence.get("source_windows_rms_dbfs") or []
        silence["source_n_windows"] = len(sw)
        silence["source_windows_with_speech"] = sum(1 for _, db in sw if db > -45.0)

    capture_mode = (metrics.get("captureMode")
                    or (metrics.get("link") or {}).get("captureMode")
                    or (metrics.get("captureModeDetail")))
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": s,
        "segments": cmp_data["segments"],
        "silence": silence,
        "sync_err": sync,
        "capture_mode": capture_mode,
        "capture_mode_is_production": (capture_mode == "tabCapture"),
        "bridge_hello_uplink_at": hello_at,
        "notes": notes or [],
        "margin_source": mp,
        "metrics_source": mtp,
    }

    out_dir = listen_dir or os.path.join(
        LISTEN_ROOT, "ext032_%s" % time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    # ① player 录音（原样拷贝，不转码 ⇒ 保留原始证据）
    webm_dst = os.path.join(out_dir, "dub_player.webm")
    if os.path.abspath(s["player_webm"]) != os.path.abspath(webm_dst):
        shutil.copyfile(s["player_webm"], webm_dst)
    # ② 逐段对比表
    with io.open(os.path.join(out_dir, "ext032_compare.json"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(cmp_data, ensure_ascii=False, indent=2))
    with io.open(os.path.join(out_dir, "ext032_compare.md"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write(C.render_md(cmp_data))
    # ③ README
    with io.open(os.path.join(out_dir, "README.md"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write(render_readme(data))
    # ④ 全部数字
    data["listen_dir"] = out_dir
    with io.open(os.path.join(out_dir, "ext032_deliver.json"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="EXT-032③④ 交付物打包")
    ap.add_argument("run_dir", help="e2e 轮次目录")
    ap.add_argument("--listen-dir", default=None, help="交付目录（默认 shared/ext_listen/ext032_<时间>）")
    ap.add_argument("--note", action="append", default=[], help="写入 README 的口径说明（可重复）")
    ap.add_argument("--reuse-compare", action="store_true",
                    help="复用轮次目录里已有的 ext032_compare.json（不再起浏览器解码 webm）")
    ap.add_argument("--source-wav", default=None,
                    help="上行素材 wav（用于证明「ASR 空的窗在素材里是有语音的」）")
    a = ap.parse_args()
    data = build_delivery(a.run_dir, a.listen_dir, a.note,
                          reuse_compare=a.reuse_compare, source_wav=a.source_wav)
    s = data["summary"]
    c = data["silence"]
    print("=" * 70)
    print("EXT-032 交付物")
    print("=" * 70)
    print("交付目录：%s" % data["listen_dir"])
    print("抓流方式：%s（生产路径=%s）" % (data["capture_mode"], data["capture_mode_is_production"]))
    print("开口静音 %s s；最长静音 %s s；首段配音 t_start=%s s"
          % (c["player_leading_silence_sec"], c["player_longest_silence_sec"],
             c["first_spoken_t_start_sec"]))
    print("可解释 %s s，残差 %s s"
          % (c["explained_leading_silence_sec"], c["residual_sec"]))
    print("sync_err（有 TTS 段）p50=%s ms p95=%s ms max=%s ms"
          % (data["sync_err"]["tts_segments"]["p50"],
             data["sync_err"]["tts_segments"]["p95"],
             data["sync_err"]["tts_segments"]["max"]))
    print("时长比 原始 %s~%s；变速校正 %s~%s"
          % (s["dur_ratio_min"], s["dur_ratio_max"],
             s["dur_ratio_speed_adjusted_min"], s["dur_ratio_speed_adjusted_max"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
